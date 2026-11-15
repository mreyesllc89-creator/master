# MetaTrader 5 trading EAs: Loma and XLZC

## Loma TrendPullback EA (v1.34): XAUUSD and BTCUSD

Download a zip, unpack it and read its `START_HERE.md`:

| Zip | Contents |
|---|---|
| [`dist/Loma_XAUUSD_v1_34.zip`](dist/Loma_XAUUSD_v1_34.zip) | The EA, the six gold presets, a summary table and the out-of-sample report. |
| [`dist/Loma_BTCUSD_v1_34.zip`](dist/Loma_BTCUSD_v1_34.zip) | The same EA and the four BTCUSD presets with their summary table. |

**Status: not recommended for live trading.** The presets were fitted to January 2025 – May 2026.
- **Gold:** on the months after that, the six presets together lost money on VT Markets real ticks (June – 6 November 2026, 247 trades): profit factor 0.74 before commission and 0.67 at VT's $0.60 per lot. Dukascopy prices agree.
- **BTC:** the four new M5 presets passed the unseen months of 2026 (profit factor 1.42 on 133 trades, 16 May – 13 November) and lost on the two years before the calibration data (0.79 in 2024, 0.83 in 2023): unproven, demo only. The earlier `Loma_BTC01`–`BTC04` presets are withdrawn; they were fitted on a price file with a wrong clock.
- **Re-calibration per timeframe:** every timeframe from M1 to H1 was re-calibrated on the same period with 23 trailing systems and tested on the months after it. Gold: no timeframe holds a profit factor of 1.3 on unseen data (0.67–1.08, or 0.61–1.01 at VT's costs). BTC: M5 passes the 2026 months, with the EA's own trailing (1.42 on 133 trades) and with all 23 systems (1.48 on 377 trades), but the same setups scored 0.79 and 1.00 in 2024 and 0.83 and 0.69 in 2023: it did not hold on earlier data. No other BTC timeframe passes. See `research/reports/loma_oos_review.html`, section 5.
- **The EA itself** reproduces the backtest's trades.

| Where | What |
|---|---|
| `XAUUSD_Loma_TrendPullback.mq5` | The EA source (runs on XAUUSD and BTCUSD). |
| `presets/top10/`, `presets/btc/` | Gold and BTC presets with summary CSVs (in-sample and out-of-sample figures). |
| `packages/loma_xauusd/`, `packages/loma_btcusd/` | The guides that go into the zips. |
| `LOMA_START_HERE.md` | Full guide: rules, every preset set, calibration and stress history. |
| `research/reports/loma_oos_review.html` | Out-of-sample review: VT Markets MT5 run, Dukascopy cross-check, walk-forward test. |
| `research/` | Python backtest engine (`hump_engine.py`), calibration, walk-forward and out-of-sample scripts and results. `hump_tf_recal.py` and `hump_trail.py` are the per-timeframe re-calibration with every trailing family (`results/recal/`). `package_loma.py` builds the zips. |

## XLZC Bearish EA (v1.21): XAUUSD

`XAUUSD_M1_LiquidityZeroCross_Bearish.mq5` (and the `_FGF` variant with the FlashGold direction filter), with `START_HERE.md`, `XAUUSD_M1_LiquidityZeroCross_Bearish.md`, the `presets/XLZC_*.set` presets and the TradingView port `XLZC_Liquidity_ZeroCross_Bearish_Strategy.pine`.

## EA Validation Kit

`EVK/` records every trade in the MT5 Strategy Tester and analyses optimization results. Both EAs include `EVK/MQL5/Include/EVK/EVK.mqh`. See `EVK/README.md`.
