# TDI Confluence Strategy v3.0: input sweep backtest

**Data:** Binance BTCUSDT 1-minute bars, 2026-04-01 → 2026-10-31 (308,160 bars). Tick size is 0.01, so 100 ticks = $1.
**In-sample:** Apr–Aug. **Out-of-sample:** Sep–Oct.
**Costs:** 0.02% per side, unless a table says otherwise. Sizing follows the script: 1% of equity per trade.
**Units:** "bp" means the average trade result in basis points of the position's notional value, which makes the number independent of the 1% sizing. Net-profit % on the account is tiny for every configuration, because each trade puts only 1% of equity at risk.

## How it was tested
`engine.py` is a bar-for-bar Python port of the script plus a TradingView-style broker emulator:
- `request.security` uses the closed-bar historical semantics (lookahead off). A lower timeframe returns the last intrabar value.
- Market entries fill at the next bar's open. Orders reverse the position, and pyramiding is 1.
- `strategy.exit` only starts working one bar after the fill bar, because the script creates it only once `position_size != 0`.
- SL, TP and trailing exits follow TradingView's open→high/low→close intrabar path rule. Gaps at the open fill at the open.

The port was audited by four independent reviewers: indicators, MTF mapping, chart logic, and broker fills. Every claim was then checked by a separate skeptic. Three confirmed issues were fixed:
- the trailing stop did not activate at the bar open;
- the RSI used a different rounding form than Pine's RMA;
- reversal sizing ignored open profit.

Re-running the sweep after the fixes changed the results by less than 1 bp.

Sweep size:
- **Stage 1:** 8,064 signal configurations × 25 exits = 201,600 backtests. Inputs varied: chart timeframe 1/5/15m, pivot strength 3/5/8, min/max swing bars, day start 00:00 or 13:00 UTC, divergence toggles, TF toggles, 4th-signal filter, and TDI level filter off / 38-62 / 30-70 / 45-55.
- **Stage 2:** the 60 best distinct signal sets plus the defaults × 270 exits. SL ran from 200 to 80,000 ticks ($2–$800), TP from 0.5 to 5R, and trailing was off or used 4 activation/offset settings.

## 1. Defaults lose money
| Chart | Trades (7 mo) | Win % | Profit factor (no fees) | Avg/trade, no fees | Avg/trade, 0.05%/side |
|---|---|---|---|---|---|
| 1m | 115 | 50 | 0.55 | −1.7 bp | −11.7 bp (win rate 3%) |
| 5m | 50 | 44 | 0.68 | −2.2 bp | −12.2 bp |
| 15m | 16 | 44 | 0.36 | −9.3 bp | −19.3 bp |

A stop of 200 ticks is **$2 on BTC**, which is about 0.002% of price, so it sits inside the bar noise. On BTC the default trailing settings (150/50 ticks) make no measurable difference. The exits are also unprotected for the whole fill bar, so the real loss on many trades is larger than the $2 stop.

## 2. Most inputs don't change entries
- `combinedLongRaw` / `combinedShortRaw` use the raw `t1l…d60hr` values from every timeframe, not the `show…` toggles. The five **TF toggles and four divergence toggles only matter when "Require 4th Signal" is on.** Of the 8,064 configurations, only **81 produced different trade sets**.
- `breakLow` checks `high[1] >= dayLow[1]`, which is always true, and `breakHigh` checks `low[1] <= dayHigh[1]`, which is also always true. That makes the entry gate simply "this bar made a new custom-day low or high".
- **Require 4th Signal:** no configuration reached 30 trades in 5 months.
- **15m chart:** too few trades to judge.

## 3. Exit sizing dominates everything
Median result per trade over all data, default signals, by stop size:

| SL | 1m | 5m | 15m |
|---|---|---|---|
| $2 (default) | −5.7 bp | −6.2 bp | −13.3 bp |
| $20 | −5.7 | −5.6 | −13.3 |
| $100 | −4.1 | −2.0 | −14.3 |
| $200 | −2.9 | +3.4 | −14.5 |
| $400 | +2.2 | +4.9 | −13.8 |
| $800 | +7.7 | +12.5 | −7.3 |

Only very wide exits get positive. A $400–$800 stop with a $1,200–$4,000 target amounts to holding a swing trade for hours, so the result mostly reflects BTC's direction during those hours.

## 4. Best configurations, and whether they are real
Top configurations by the worse of in-sample and out-of-sample bp (all on the 1m chart):

| Pivot | Day start | Divergences | Levels | TF toggles (fix variant) | SL / TP (ticks) | IS trades / bp / PF | OOS trades / bp / PF |
|---|---|---|---|---|---|---|---|
| 3 | 13:00 | all 4 | 45/55 | 15–60m | 40000 / 200000 | 48 / +23.6 / 1.52 | 15 / +64.8 / 3.30 |
| 3 | 13:00 | all 4 | off | 60m only | 80000 / 160000 | 44 / +30.9 / 1.46 | 15 / +22.9 / 1.42 |
| 3 | 13:00 | all 4 | off | all (as written) | 80000 / 160000 | 46 / +26.8 / 1.40 | 15 / +22.9 / 1.42 |
| 3 | 00:00 | none | 38/62 | all (as written) | 40000 / 200000 | 50 / +47.1 / 2.18 | 23 / +18.5 / 1.47 |

The "fix variant" makes the TF toggles also gate entries, which the original script does not do.

These do not look like a reliable edge:
- **Too few trades.** Each has about 60 trades in 7 months and only 15–23 out-of-sample. The t-statistics are 1.2–1.8, below the usual significance threshold of about 2.
- **Random entries get close.** Random entries with the same exits and trade count beat them 1–5% of the time. However, they were picked as the best of about 22,000 (signal × exit) combinations, so p ≈ 0.01–0.05 is what chance alone would produce.
- **In-sample rank barely predicts out-of-sample rank.** Spearman correlation is 0.22. Of 2,589 in-sample-profitable combinations, 1,187 (46%) were also profitable out-of-sample, which is roughly a coin flip.
- **Picking the in-sample winner fails.** The top configuration in-sample (+54.6 bp) returned −24.7 bp out-of-sample.

## Takeaways
1. Don't trade the default inputs on BTC. Tick-based stops of 200/400 ticks are sized for instruments like gold or FX, not BTC.
2. If you keep the strategy, express SL and TP in ATR or percent of price instead of ticks, and protect the position from the fill bar onward, for example by passing `stop`/`limit` prices on the entry bar.
3. Decide whether the TF toggles should also gate entries. As written they are display-only unless "Require 4th Signal" is on.
4. "Day start 13:00 UTC + pivot strength 3 + wide stops" was the most consistent cluster. It still needs more data, more history and other symbols before it can be trusted.

## Reproduce
```bash
./fetch_data.sh
python3 run_defaults.py
python3 sweep.py 1 && python3 pick_stage2.py && python3 sweep.py 2
python3 an2.py
python3 perm.py
```
`stage2_results.csv` holds the top 1,500 stage-2 rows with at least 30 trades.
