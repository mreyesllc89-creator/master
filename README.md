# MetaTrader 5 trading EAs: Loma and XLZC

## Loma TrendPullback EA (v1.35): XAUUSD and BTCUSD

Download a zip, unpack it and read its `START_HERE.md`:

| Zip | Contents |
|---|---|
| [`dist/Loma_XAUUSD_v1_35.zip`](dist/Loma_XAUUSD_v1_35.zip) | The EA, the six gold Top presets, the 16 gold trailing presets, summary tables and the report. |
| [`dist/Loma_BTCUSD_v1_35.zip`](dist/Loma_BTCUSD_v1_35.zip) | The same EA, the 10 BTC presets of the year-by-year result, the four BTC M5 presets, the 38 BTC trailing presets, summary tables and the report. |

**Status: not recommended for live trading.** The gold, BTC M5 and trailing presets were fitted to January 2025 – May 2026; the BTC year-by-year presets to 2024 – 13 November 2026.
- **Gold:** on the months after that, the six presets together lost money on VT Markets real ticks (June – 6 November 2026, 247 trades): profit factor 0.74 before commission and 0.67 at VT's $0.60 per lot. Dukascopy prices agree.
- **BTC:** the four new M5 presets passed the unseen months of 2026 (profit factor 1.42 on 133 trades, 16 May – 13 November) and lost on the two years before the calibration data (0.79 in 2024, 0.83 in 2023): unproven, demo only. The earlier `Loma_BTC01`–`BTC04` presets are withdrawn; they were fitted on a price file with a wrong clock.
- **Re-calibration per timeframe:** every timeframe from M1 to H1 was re-calibrated on the same period with 23 trailing systems and tested on the months after it. Gold: no timeframe holds a profit factor of 1.3 on unseen data (0.67–1.08, or 0.61–1.01 at VT's costs). BTC: M5 passes the 2026 months, with the EA's own trailing (1.42 on 133 trades) and with all 23 systems (1.48 on 377 trades), but the same setups scored 0.79 and 1.00 in 2024 and 0.83 and 0.69 in 2023: it did not hold on earlier data. No other BTC timeframe passes. See `research/reports/loma_oos_review.html`, section 5.
- **Year by year (15 November 2026):** the method was set up on three years and traded on the next, rolling forward (gold 2016 – 2025, BTC 2021 – 2025), with 58 entry conditions tried one at a time. Gold: nothing passed. BTC: M30 with the Stochastic turn rule met the pass rule (1.22 in 2023, 1.39 in 2024, 1.87 in 2025), but it does not hold up: the 2026 months, kept back, gave 1.26 on 267 trades, under 1.3; with 472 cells tested, chance alone produces one or two such passes (about 1.2 expected); counted once per signal its profit factor is 1.42, not 1.60. Its picks for the year ahead are in the BTC zip as unproven presets (EA v1.35), demo only. See `research/reports/loma_oos_review.html`, section 6.
- **Trailing presets:** the 15 combinations of timeframe and trailing system whose setups together reached a profit factor of 1.3 on the 2026 months (4 gold, 11 BTC) are in the zips as presets (v1.35). None reached 1.3 on the earlier data. The gold figures are at FTMO's spread without commission: at VT's costs 2 of the 4 fall under 1.3 (M5 chandelier 1.23, M10 percent 1.24). Unproven: Strategy Tester and demo only.
- **The EA itself** reproduces the backtest's trades.

| Where | What |
|---|---|
| `XAUUSD_Loma_TrendPullback.mq5` | The EA source (runs on XAUUSD and BTCUSD). |
| `presets/top10/`, `presets/btc/`, `presets/btc_wf/`, `presets/trailing15/` | Gold and BTC presets with summary CSVs: the Top presets, the BTC M5 presets, the BTC year-by-year presets and the trailing presets. |
| `packages/loma_xauusd/`, `packages/loma_btcusd/` | The guides that go into the zips. |
| `LOMA_START_HERE.md` | Full guide: rules, every preset set, calibration and stress history. |
| `research/reports/loma_oos_review.html` | Out-of-sample review: VT Markets MT5 run, Dukascopy cross-check, walk-forward test, re-calibration (section 5), year-by-year test (section 6). |
| `research/results/recal/*_successful_trailing.json` | Every trailing result that reached PF 1.3 on the unseen months, with the settings of each setup and its result on earlier data (`research/successful_trailing.py`). |
| `LOMA_NEXT_PROMPT.md` | The research prompt behind the year-by-year test (more history, new entry conditions, the same honest test). |
| `research/` | Python backtest engine (`hump_engine.py`), calibration, walk-forward and out-of-sample scripts and results. `hump_tf_recal.py`, `hump_trail.py` and `hump_trail2.py` are the per-timeframe re-calibration with the 23 trailing systems (`results/recal/`); `hump_trail2.py` is the backtest behind the trailing presets. `hump_wf.py` is the year-by-year test on long history (`results/wf/`); `audit_wf/` and `results/wf/audit/` are its independent audit, summarised in `results/wf/chance_check.json`. `package_loma.py` builds the zips. |

## XLZC Bearish EA (v1.21): XAUUSD

`XAUUSD_M1_LiquidityZeroCross_Bearish.mq5` (and the `_FGF` variant with the FlashGold direction filter), with `START_HERE.md`, `XAUUSD_M1_LiquidityZeroCross_Bearish.md`, the `presets/XLZC_*.set` presets and the TradingView port `XLZC_Liquidity_ZeroCross_Bearish_Strategy.pine`.

## EA Validation Kit

`EVK/` records every trade in the MT5 Strategy Tester and analyses optimization results. Both EAs include `EVK/MQL5/Include/EVK/EVK.mqh`. See `EVK/README.md`.
