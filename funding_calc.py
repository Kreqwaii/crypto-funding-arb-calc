#!/usr/bin/env python3
"""
Crypto Funding Rate Arbitrage Calculator (Lite CLI)
100% Python stdlib — zero external dependencies.

Calculates delta-neutral perpetual funding arbitrage metrics:
- Net spread per funding interval
- Gross APR & Net APR (after entry/exit fees + slippage)
- Breakeven intervals & breakeven hours
- 7 / 30 / 90-day projected PnL
- Batch CSV ranking mode (--batch)
- Built-in self-test suite (--self-test)
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import tempfile
from dataclasses import dataclass
from typing import List, Optional


HOURS_PER_YEAR = 24 * 365  # 8760


@dataclass
class ArbResult:
    symbol: str
    long_exchange: str
    short_exchange: str
    long_rate_pct: float
    short_rate_pct: float
    interval_hours: int
    notional_usd: float
    entry_mode: str
    fee_pct_per_side: float
    slippage_bps: float
    net_spread_pct: float
    gross_apr_pct: float
    total_roundtrip_cost_pct: float
    total_roundtrip_cost_usd: float
    net_profit_per_interval_usd: float
    breakeven_intervals: Optional[float]
    breakeven_hours: Optional[float]
    net_apr_pct: float
    pnl_7d_usd: float
    pnl_30d_usd: float
    pnl_90d_usd: float


def calculate_arb(
    long_rate_pct: float,
    short_rate_pct: float,
    interval_hours: int = 8,
    notional_usd: float = 10000.0,
    taker_fee_pct: float = 0.05,
    maker_fee_pct: float = 0.02,
    entry_mode: str = "taker",
    slippage_bps: float = 2.0,
    symbol: str = "PAIR",
    long_exchange: str = "ExchangeA",
    short_exchange: str = "ExchangeB",
) -> ArbResult:
    if interval_hours not in (1, 4, 8):
        raise ValueError(f"Unsupported interval_hours: {interval_hours}. Use 1, 4, or 8.")
    if notional_usd <= 0:
        raise ValueError("notional_usd must be > 0")
    if entry_mode not in ("taker", "maker"):
        raise ValueError("entry_mode must be 'taker' or 'maker'")

    # In delta-neutral funding arb:
    # - Long perp pays funding when rate > 0, receives when rate < 0 -> cashflow = -long_rate_pct
    # - Short perp receives funding when rate > 0, pays when rate < 0 -> cashflow = +short_rate_pct
    net_spread_pct = short_rate_pct - long_rate_pct

    intervals_per_year = HOURS_PER_YEAR / interval_hours
    gross_apr_pct = net_spread_pct * intervals_per_year

    fee_pct_per_side = taker_fee_pct if entry_mode == "taker" else maker_fee_pct
    # Delta-neutral position has 2 legs (Long + Short), each entered AND exited = 4 legs total
    total_fee_pct = fee_pct_per_side * 4.0
    # Slippage in bps (1 bps = 0.01%), applied on entry + exit across 2 legs (or 2x roundtrip)
    # Using 2x roundtrip legs = 4 * (slippage_bps / 100.0)
    total_slippage_pct = (slippage_bps / 100.0) * 4.0
    total_roundtrip_cost_pct = total_fee_pct + total_slippage_pct
    total_roundtrip_cost_usd = notional_usd * (total_roundtrip_cost_pct / 100.0)

    net_profit_per_interval_usd = notional_usd * (net_spread_pct / 100.0)

    if net_spread_pct > 0:
        breakeven_intervals = total_roundtrip_cost_pct / net_spread_pct
        breakeven_hours = breakeven_intervals * interval_hours
    else:
        breakeven_intervals = None
        breakeven_hours = None

    # Net APR: annualized gross yield minus 1x roundtrip cost (assuming 30-day hold amortized, or 1-year hold)
    # Standard convention: 1-year hold net APR = gross_apr_pct - total_roundtrip_cost_pct
    net_apr_pct = gross_apr_pct - total_roundtrip_cost_pct

    def projected_pnl(days: int) -> float:
        intervals = (days * 24) / interval_hours
        return (net_profit_per_interval_usd * intervals) - total_roundtrip_cost_usd

    return ArbResult(
        symbol=symbol,
        long_exchange=long_exchange,
        short_exchange=short_exchange,
        long_rate_pct=long_rate_pct,
        short_rate_pct=short_rate_pct,
        interval_hours=interval_hours,
        notional_usd=notional_usd,
        entry_mode=entry_mode,
        fee_pct_per_side=fee_pct_per_side,
        slippage_bps=slippage_bps,
        net_spread_pct=net_spread_pct,
        gross_apr_pct=gross_apr_pct,
        total_roundtrip_cost_pct=total_roundtrip_cost_pct,
        total_roundtrip_cost_usd=total_roundtrip_cost_usd,
        net_profit_per_interval_usd=net_profit_per_interval_usd,
        breakeven_intervals=breakeven_intervals,
        breakeven_hours=breakeven_hours,
        net_apr_pct=net_apr_pct,
        pnl_7d_usd=projected_pnl(7),
        pnl_30d_usd=projected_pnl(30),
        pnl_90d_usd=projected_pnl(90),
    )


def format_single_result(res: ArbResult) -> str:
    be_int = f"{res.breakeven_intervals:.2f}" if res.breakeven_intervals is not None else "N/A (negative spread)"
    be_hrs = f"{res.breakeven_hours:.1f}h" if res.breakeven_hours is not None else "N/A"
    lines = [
        "=" * 58,
        f"  Funding Rate Arbitrage Report: {res.symbol}",
        f"  Long: {res.long_exchange} ({res.long_rate_pct:+.4f}%/{res.interval_hours}h) | "
        f"Short: {res.short_exchange} ({res.short_rate_pct:+.4f}%/{res.interval_hours}h)",
        "=" * 58,
        f"  Notional Size       : ${res.notional_usd:,.2f} (per leg)",
        f"  Entry Mode          : {res.entry_mode.upper()} ({res.fee_pct_per_side:.3f}%/side + {res.slippage_bps:.1f} bps slip)",
        f"  Net Spread/Interval : {res.net_spread_pct:+.4f}% (${res.net_profit_per_interval_usd:+.2f})",
        f"  Roundtrip Cost (4x) : {res.total_roundtrip_cost_pct:.4f}% (${res.total_roundtrip_cost_usd:.2f})",
        f"  Gross APR           : {res.gross_apr_pct:+.2f}%",
        f"  Net APR (1Y hold)   : {res.net_apr_pct:+.2f}%",
        f"  Breakeven           : {be_int} intervals ({be_hrs})",
        "-" * 58,
        f"  Projected Net PnL   : 7d: ${res.pnl_7d_usd:+,.2f} | 30d: ${res.pnl_30d_usd:+,.2f} | 90d: ${res.pnl_90d_usd:+,.2f}",
        "=" * 58,
    ]
    return "\n".join(lines)


def run_batch(
    csv_path: str,
    notional_usd: float,
    taker_fee_pct: float,
    maker_fee_pct: float,
    entry_mode: str,
    slippage_bps: float,
) -> List[ArbResult]:
    results: List[ArbResult] = []
    with open(csv_path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            res = calculate_arb(
                long_rate_pct=float(row["long_rate_pct"]),
                short_rate_pct=float(row["short_rate_pct"]),
                interval_hours=int(row.get("interval_hours", 8)),
                notional_usd=notional_usd,
                taker_fee_pct=taker_fee_pct,
                maker_fee_pct=maker_fee_pct,
                entry_mode=entry_mode,
                slippage_bps=slippage_bps,
                symbol=row["symbol"].strip(),
                long_exchange=row.get("long_exchange", "ExchangeA").strip(),
                short_exchange=row.get("short_exchange", "ExchangeB").strip(),
            )
            results.append(res)
    results.sort(key=lambda r: r.net_apr_pct, reverse=True)
    return results


def format_batch_table(results: List[ArbResult]) -> str:
    header = (
        f"{'Rank':<5} {'Pair':<10} {'Long -> Short':<20} {'Spread':>9} "
        f"{'Gross APR':>10} {'Net APR':>10} {'BE (hrs)':>9} {'30d PnL':>11}"
    )
    sep = "-" * len(header)
    lines = [sep, header, sep]
    for idx, r in enumerate(results, start=1):
        route = f"{r.long_exchange}->{r.short_exchange}"
        be_str = f"{r.breakeven_hours:.1f}h" if r.breakeven_hours is not None else "N/A"
        lines.append(
            f"{idx:<5} {r.symbol:<10} {route:<20} {r.net_spread_pct:>+8.4f}% "
            f"{r.gross_apr_pct:>+9.2f}% {r.net_apr_pct:>+9.2f}% {be_str:>9} ${r.pnl_30d_usd:>+9,.2f}"
        )
    lines.append(sep)
    return "\n".join(lines)


def run_self_test() -> int:
    checks_passed = 0
    total_checks = 5

    # 1. Basic 8h positive spread calculation
    r1 = calculate_arb(
        long_rate_pct=0.01,
        short_rate_pct=0.05,
        interval_hours=8,
        notional_usd=10000.0,
        taker_fee_pct=0.05,
        maker_fee_pct=0.02,
        entry_mode="taker",
        slippage_bps=2.0,
    )
    assert math.isclose(r1.net_spread_pct, 0.04, rel_tol=1e-9), "Net spread mismatch"
    # 0.04% * (8760 / 8) = 0.04 * 1095 = 43.8%
    assert math.isclose(r1.gross_apr_pct, 43.8, rel_tol=1e-9), "Gross APR mismatch"
    # Roundtrip cost: 4 * 0.05% + 4 * 0.02% = 0.28%
    assert math.isclose(r1.total_roundtrip_cost_pct, 0.28, rel_tol=1e-9), "Cost mismatch"
    assert r1.breakeven_intervals is not None and math.isclose(r1.breakeven_intervals, 7.0, rel_tol=1e-9)
    assert r1.breakeven_hours is not None and math.isclose(r1.breakeven_hours, 56.0, rel_tol=1e-9)
    checks_passed += 1

    # 2. Negative spread handling
    r2 = calculate_arb(long_rate_pct=0.05, short_rate_pct=0.01, interval_hours=8, notional_usd=5000.0)
    assert r2.net_spread_pct < 0
    assert r2.breakeven_intervals is None
    assert r2.breakeven_hours is None
    assert r2.pnl_30d_usd < 0
    checks_passed += 1

    # 3. 1h vs 8h interval scaling
    r_1h = calculate_arb(long_rate_pct=0.0, short_rate_pct=0.005, interval_hours=1)
    r_8h = calculate_arb(long_rate_pct=0.0, short_rate_pct=0.04, interval_hours=8)
    assert math.isclose(r_1h.gross_apr_pct, r_8h.gross_apr_pct, rel_tol=1e-9), "1h vs 8h APR scaling mismatch"
    checks_passed += 1

    # 4. Maker mode lowers roundtrip cost vs Taker mode
    r_maker = calculate_arb(long_rate_pct=0.01, short_rate_pct=0.05, entry_mode="maker", slippage_bps=0.0)
    r_taker = calculate_arb(long_rate_pct=0.01, short_rate_pct=0.05, entry_mode="taker", slippage_bps=0.0)
    assert r_maker.total_roundtrip_cost_usd < r_taker.total_roundtrip_cost_usd
    checks_passed += 1

    # 5. Batch CSV parsing & ranking
    csv_content = (
        "symbol,long_exchange,short_exchange,long_rate_pct,short_rate_pct,interval_hours\n"
        "BTCUSDT,Binance,Bybit,0.0100,0.0350,8\n"
        "SOLUSDT,OKX,Bybit,-0.0100,0.0600,8\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as tmp:
        tmp.write(csv_content)
        tmp_path = tmp.name
    try:
        batch_res = run_batch(tmp_path, 10000.0, 0.05, 0.02, "taker", 2.0)
        assert len(batch_res) == 2
        assert batch_res[0].symbol == "SOLUSDT", "Batch ranking order mismatch"
    finally:
        os.remove(tmp_path)
    checks_passed += 1

    print(f"{checks_passed}/{total_checks} CHECKS PASSED")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crypto Funding Rate Arbitrage Calculator (Lite CLI)"
    )
    parser.add_argument("--long-rate", type=float, help="Long perp funding rate in %% (e.g. 0.01)")
    parser.add_argument("--short-rate", type=float, help="Short perp funding rate in %% (e.g. 0.05)")
    parser.add_argument("--interval", type=int, default=8, choices=[1, 4, 8], help="Funding interval in hours (default: 8)")
    parser.add_argument("--notional", type=float, default=10000.0, help="Position notional in USD per leg (default: 10000)")
    parser.add_argument("--taker-fee", type=float, default=0.05, help="Taker fee %% per side (default: 0.05)")
    parser.add_argument("--maker-fee", type=float, default=0.02, help="Maker fee %% per side (default: 0.02)")
    parser.add_argument("--entry-mode", choices=["taker", "maker"], default="taker", help="Execution mode (default: taker)")
    parser.add_argument("--slippage", type=float, default=2.0, help="Estimated slippage in bps per leg (default: 2.0)")
    parser.add_argument("--symbol", type=str, default="PERP-PAIR", help="Symbol label for single calculation")
    parser.add_argument("--batch", type=str, help="Path to CSV file for batch ranking")
    parser.add_argument("--self-test", action="store_true", help="Run built-in verification suite")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.batch:
        results = run_batch(
            csv_path=args.batch,
            notional_usd=args.notional,
            taker_fee_pct=args.taker_fee,
            maker_fee_pct=args.maker_fee,
            entry_mode=args.entry_mode,
            slippage_bps=args.slippage,
        )
        print(format_batch_table(results))
        return 0

    if args.long_rate is None or args.short_rate is None:
        parser.print_help()
        return 1

    res = calculate_arb(
        long_rate_pct=args.long_rate,
        short_rate_pct=args.short_rate,
        interval_hours=args.interval,
        notional_usd=args.notional,
        taker_fee_pct=args.taker_fee,
        maker_fee_pct=args.maker_fee,
        entry_mode=args.entry_mode,
        slippage_bps=args.slippage,
        symbol=args.symbol,
    )
    print(format_single_result(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
