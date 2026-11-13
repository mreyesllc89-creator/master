# TDI Confluence Strategy: stop-mode backtest (v3.0 → v3.1)

**Data:** Binance BTCUSDT, 1-minute bars, 2026-04-01 → 2026-10-31 (308,160 bars). Tick size 0.01, so 100 ticks = $1.
**Costs:** 0.02% commission per side unless stated. Sizing: 1% of equity per trade, as in the script.
**Units:** "bp" is the average trade result in basis points of the position's notional value, after commission. It does not depend on position size: at 1% of equity, +50 bp per trade is +0.005% of the account per trade, and it scales linearly with size.

> **Correction:** the first version of this file, from the first push of this branch, was wrong. The engine's timestamps were in milliseconds while the multi-timeframe mapping assumed nanoseconds, so the 5m, 15m, 30m and 1h TDI and divergence states never reached the chart. That is fixed now, with a regression test in `test_mtf.py`, and every number below comes from the fixed engine.

## v3.0 as written (200/400 ticks, trail 150/50)
| Chart | Trades | Win %, no fees | Profit factor, no fees | bp/trade, no fees | bp/trade, 0.02%/side |
|---|---|---|---|---|---|
| 1m | 468 | 52 | 0.95 | −0.1 | −4.1 |
| 5m | 292 | 49 | 0.91 | −0.4 | −4.4 |
| 15m | 203 | 53 | 1.07 | +0.5 | −3.5 |

Without fees it roughly breaks even, and with fees it loses. A 200-tick stop is $2 on BTC, so every trade is a coin flip that then pays the commission.

## What changed in v3.1 (`TDI_Confluence_Strategy_v3.1.pine`)
- **Stop Mode** input: `ATR` (default), `Percent` or `Ticks`. TP is set as a multiple of the stop distance (R). Trailing activation and offset are fractions of the stop distance.
- **ATR:** `ta.atr(14)` on the chart, or on 15m or 60m using the last **closed** higher-timeframe bar (`[1]` + `lookahead_on`), so it doesn't repaint.
- **Frozen distances:** the stop distance is fixed at the signal bar. The exit is attached on the entry bar, so the position is protected **from the fill bar**. In v3.0 the stop was only placed one bar after the fill.
- **Conflicting signals:** bars that signal both long and short are skipped.
- **New option "TF/Divergence toggles also gate entries"**, off by default. Off keeps v3.0 behaviour, where entries use every timeframe's raw state and ignore the toggles.
- **Commission:** set to 0.02% in `strategy()` so the TradingView report includes costs.
- **Signal logic:** unchanged.

## Method
- **Stage A:** 8,064 input combinations reduce to 1,544 distinct signal sets, of which 1,015 have at least 60 signals. Inputs varied: chart 1/5/15m, pivot strength 3/5/8, swing bars 5–60 or 10–120, day start 00:00 or 13:00, divergence toggles, TF toggles with and without gating, 4th-signal filter, TDI levels off / 38-62 / 30-70 / 45-55.
- **Stage B:** every distinct signal set was run against 468 exit settings, **475,020 backtests** in total:
  - **Ticks:** 200–80,000 ticks × TP 1/2/3R × trail on/off. Each run twice: exits active from the fill bar, and v3.0's one-bar-late placement.
  - **ATR:** ATR on the chart, 15m or 60m × multiple 0.5–12 × TP 1–3R × 3 trail settings.
  - **Percent:** 0.1–2% × TP 1–3R × 3 trail settings.
- **Walk-forward:** each test month (Jul, Aug, Sep, Oct) is traded with the setting that scored best on all earlier months. The concatenated test trades estimate how each mode performs on unseen data.
- **Audit:** the engine was checked by two rounds of independent reviewers against Pine and TradingView semantics, with each claim verified adversarially. Fixed: the MTF time units, the trailing stop at the bar open, the RSI rounding form, reversal sizing, the higher-TF ATR `[1]` alignment (regression-tested), and the conflicting-signal bars.

## Which stop mode works best: ATR
**Across all 1,015 signal sets** (combinations with at least 100 trades, all 7 months):

| Mode | Share of combinations profitable | Median bp | 90th percentile bp |
|---|---|---|---|
| Ticks | 14% | −3.4 | +1.0 |
| **ATR** | **31%** | −2.1 | **+9.2** |
| Percent | 33% | −1.9 | +7.3 |

**Walk-forward**, choosing each month's setting by the t-stat on earlier months:

| Mode | Out-of-sample trades | bp/trade | Positive test months |
|---|---|---|---|
| Ticks | 33 | +7.5 | 3/4 |
| **ATR** | 61 | +3.9 | **4/4** |
| Percent | 36 | −4.1 | 2/4 |

Choosing by in-sample average instead gave ATR +46.9 bp (33 trades, 3/4 months), ticks +37.3 bp (3/4) and percent +15.6 bp (2/4). No mode reaches statistical significance in walk-forward, because there are too few out-of-sample trades. ATR is the only mode that was positive in every test month.

**Where the profitable ATR settings sit:** median bp across all signal sets, with TP 2R:

| Stop distance | chart ATR | 15m ATR | **60m ATR** |
|---|---|---|---|
| 1× | −2.5 | −1.9 | −2.0 |
| 2× | −2.8 | −2.2 | +0.8 |
| 3× | −3.0 | −1.2 | +4.4 |
| **5×** | −1.2 | +2.0 | **+10.9** |
| 8× | +0.5 | +7.2 | +9.2 |
| 12× | +2.5 | +7.6 | +9.8 |

Tight stops lose under every mode. Profit appears once the stop sits beyond the 1-hour noise, at roughly 3× ATR(60m) or more, which is about 1.5–3% on BTC. The percent mode shows the same pattern: 1.5–2% stops are positive and anything under 0.75% is negative. ATR beats percent because the distance adapts to volatility. Trailing helps tight stops a little and adds nothing at 5× ATR(60m), so it is off by default.

## Finalists: stress test
All rows use 5m or 15m charts, all 7 months, and 0.02% per side. The random-entry check places the same number of long and short signals at random times with the same exits, 300 times.

| Setup | Trades | Win % | bp | t | Profit factor | Long / short bp | bp at 0% / 0.05% fees | Months positive | Random entries beat it |
|---|---|---|---|---|---|---|---|---|---|
| **B: v3.1 defaults on a 5m chart** (5× ATR(60m), TP 2R, day start 00:00) | 144 | 56 | +13.6 | 0.8 | 1.18 | +16.5 / +10.5 | +17.6 / +7.6 | 5/7 | 14% |
| A′: same, day start 13:00 | 133 | 62 | +55.9 | 2.9 | 1.89 | +66.3 / +46.0 | +59.9 / +49.9 | 6/7 | <0.3% |
| A: day start 13:00, 8× chart ATR, TP 2R | 153 | 59 | +53.3 | 3.8 | 2.12 | +55.3 / +51.6 | +57.3 / +47.3 | 7/7 | <0.3% |
| C: v3.1 defaults on a 15m chart | 113 | 62 | +38.1 | 1.6 | 1.48 | +32.9 / +43.5 | +42.1 / +32.1 | 5/7 | 1% |
| D: 15m scalp, 0.5× ATR, TP 3R, trail | 154 | 66 | +6.8 | 3.8 | 2.31 | +6.4 / +7.1 | +10.8 / **+0.8** | 6/7 | <0.3% |
| v3.0 ticks 200/400, protected | 292 | 0 | −3.8 | — | 0 | — | +0.2 / −9.8 | 0/7 | — |

**Neighbourhood check** for the 60m ATR on the 5m defaults, bp per trade:
- **Day start 00:00:** every stop from 3× to 8× and every TP from 1.5R to 3R is positive, from +5 to +24.
- **Day start 13:00:** the same grid ranges from +28 to +62.

So it is a broad plateau, not a single lucky point.

**Day-start hour (5m chart, 5× ATR(60m), TP 2R, all 24 hours):** all 24 hours are profitable, averaging +22 bp. On a 15m chart, 20 of 24 are profitable, averaging +19 bp. 13:00 UTC is the best on 5m, at +56 bp with t = 2.9. Other hours mostly fall between +4 and +41 bp with t ≈ 0.2–2.2. The **ATR stop is the robust part. 13:00 is probably a lucky pick**, so I originally kept 00:00; the default is now 13:00 at the user's request (see the update below). Full table: `dayhour_out.txt`.

**Avoid D:** its edge is about 7 bp per trade before costs above 0.02%, and it disappears at 0.05% per side.

## Update: day start 13:00 UTC is now the default

At your request, v3.1 now defaults to a 13:00 UTC day start. Re-test of the full defaults (5× ATR(60m) stop, TP 2R, no trail, 0.02% per side), from `day13.py`; full output in `day13_out.txt`.

**April–October (the period the settings were chosen on):**

| Chart | Trades | Win % | bp/trade | t | Profit factor | Random entries beat it |
|---|---|---|---|---|---|---|
| 1m | 167 | 59 | +22.4 | 1.5 | 1.35 | 1% |
| **5m** | 134 | 62 | **+55.5** | 2.9 | 1.89 | <0.3% |
| 15m | 102 | 60 | +37.0 | 1.5 | 1.45 | 5% |

On the 5m chart (including the November trades below): longs +62.5 bp, shorts +40.2 bp; 6 of 7 full months positive (May was −543 bp in total); +45 bp per trade at 0.05% fees; worst drawdown about 12% of the position's notional.

**November 1–12 (new data, not used to choose anything):**

| Chart | Trades | Won | bp/trade |
|---|---|---|---|
| 1m | 6 | 3 | −94.6 |
| 5m | 3 | 1 | −146.8 |
| 15m | 4 | 0 | −97.4 |

The first unseen stretch lost on every chart. Three to six trades is far too few to judge the strategy, and one losing trade at this stop size costs about 150–250 bp, so a start like this is within normal variation. It is still the only truly out-of-sample evidence so far, and it is negative. The 00:00 day start also lost on 1m and 5m in the same window.

**How sensitive the 5m result is to other inputs** (all data, default exits):

| Change from default | Trades | bp/trade |
|---|---|---|
| none | 137 | +51.1 |
| Stop 3× to 8× ATR(60m), TP 1R to 3R | 131–166 | +21 to +62 |
| Stop 2× ATR(60m) | 179–194 | 0 to +23 |
| Trailing on (1R / 0.5R) | 144 | +50.2 |
| Divergence toggles (any) | 137 | +51.1 (no effect on entries) |
| TDI levels 45/55 | 101 | +43.4 |
| TDI levels 38/62 | 80 | +34.1 |
| Toggles gate entries, no 1m | 68 | +67.5 |
| Swing bars 10–120 | 97 | +28.0 |
| **Pivot strength 3** | 142 | **+7.8** |
| **Pivot strength 8** | 93 | **−23.3** |
| Require 4th signal | 3 | too few trades |

The stop and target settings are robust. The result depends heavily on pivot strength staying at 5: 3 is roughly break-even and 8 loses. Together with 13:00 being the single best of 24 hours, that means the +55 bp figure is probably optimistic; expect less going forward.

## Recommendation
- **Use the v3.1 defaults on a 5m chart:**
  - Stop Mode = ATR, ATR 14 on 60m, SL = 5× ATR, TP = 2R, trailing off.
  - Expected result is roughly +10 to +25 bp per trade after fees, depending on the day-start hour. It is positive on both sides and beats random entries. This is a modest edge.
- **If you trust the 13:00 UTC day start**, roughly the US-session open, results improve a lot (+56 bp), but treat that as possibly overfit until it holds on new data.
- **Don't use tick-based stops on BTC.** If you trade another symbol, ATR mode scales automatically.
- **Caveats:**
  - one symbol (BTCUSDT) and 7 months;
  - about 135–150 trades per setup;
  - Binance data, while TradingView may chart a different BTC feed;
  - the Python engine reproduces TradingView's broker emulator closely, but not tick-for-tick.
  - Re-check in TradingView's Strategy Tester, and forward-test before trading real money.

## Reproduce
```bash
./fetch_data.sh        # Binance BTCUSDT 1m into ./data (Apr-Oct + Nov 1-12)
python3 test_mtf.py    # MTF / ATR alignment regression tests
python3 sweep3.py      # stages A+B, ~5 min on 4 cores
python3 wf31.py        # mode comparison + walk-forward + plateaus
python3 finalists.py   # stress tests
python3 dayhour.py     # day-start hour sweep
python3 day13.py       # 13:00 default re-test incl. November
```
`v31_top_results.csv` lists the top 3,000 combinations, by t-stat, that have at least 100 trades.
