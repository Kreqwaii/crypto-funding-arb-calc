# Crypto Funding Rate Arbitrage Calculator (Delta-Neutral Perp APR & Breakeven CLI)

Zero-dependency Python CLI calculator for **delta-neutral perpetual funding rate arbitrage** across Bybit, Binance, OKX, Gate, and MEXC.

Calculates **net funding spread**, **Gross APR**, **Net APR** (after 4x entry/exit fees + slippage), **exact breakeven intervals/hours**, and **7/30/90-day projected PnL** — plus batch CSV ranking.

---

## Quick Start

```bash
# Single pair calculation (8h funding interval, $10,000 notional per leg)
python funding_calc.py --long-rate 0.01 --short-rate 0.05 --notional 10000 --entry-mode taker

# Maker execution with 1h funding interval
python funding_calc.py --long-rate -0.002 --short-rate 0.008 --interval 1 --notional 25000 --entry-mode maker --slippage 0.5

# Batch rank pairs from CSV
python funding_calc.py --batch sample_pairs.csv --notional 10000

# Run built-in self-test
python funding_calc.py --self-test
```

---

## Lite CLI vs Pro 24/7 Live Scanner

| Feature | Lite CLI (Free MIT) | Pro 24/7 Live Scanner |
|---|---|---|
| **Price** | Free (Open Source) | [Available on FunPay](https://funpay.com/lots/offer?id=82597241) |
| **Spread, Net APR & Breakeven Math** | Yes | Yes |
| **Batch CSV Ranking** | Manual CSV | **Auto-Ranking every 60s** |
| **Live Exchange APIs** | No (manual input) | **Bybit + OKX + Binance + Gate + MEXC** |
| **Telegram Alerts** | No | **Instant TG Alerts on high-APR spreads** |
| **Spread History & Stability Filter** | No | **24h/7d Funding Stability & OI Filter** |

> **Want 24/7 automated multi-exchange scanning + Telegram alerts?**  
> Get the **Pro 24/7 Live Funding Arbitrage Scanner** here: **https://funpay.com/lots/offer?id=82597241**

---

## Русский (краткое описание)

Бесплатный CLI-калькулятор на чистом Python (без внешних библиотек) для расчёта **дельта-нейтрального арбитража фандинга** на бессрочных фьючерсах:
- Считает чистый спред за период (`1h` / `4h` / `8h`), **Gross APR** и **Net APR** с учётом комиссий входа/выхода (`taker`/`maker`) и проскальзывания (`bps`).
- Показывает точное время выхода в безубыток (`breakeven_intervals` и `breakeven_hours`) и прогноз PnL на 7/30/90 дней.
- Поддерживает пакетное ранжирование пар из CSV (`--batch sample_pairs.csv`).
- Нужен **полный 24/7 Live-сканер** по Bybit, OKX, Binance, Gate, MEXC с историей спредов и **Telegram-алертами**? Доступен на FunPay: https://funpay.com/lots/offer?id=82597241

---

## License

MIT License — see [LICENSE](LICENSE).
