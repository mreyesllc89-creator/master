# XPW Shape Map v0.6 — MT5 EA

`XPW_ShapeMap_EA.mq5` is a port of `xpw_shape_map_v0.6_strategy.pine` (Turn ▲/▼ entries,
Predict timing). Copy it to `MQL5/Experts/`, compile it in MetaEditor (F7), then attach it
to an **XAUUSD** or **BTCUSD** chart on the timeframe of the preset you choose.

The EA computes everything on closed bars. Each bar it re-derives the BOT/TOP square arming,
the predicted cross price and the ATR, then holds a **virtual** stop at the cross price. The
first tick that reaches it (Ask for buys, Bid for sells) sends a market order with a
broker-side SL. The trailing stop moves that SL. This mirrors the tick calibration and
behaves the same on hedging and netting accounts.

## Presets (calibrated on VT Markets MT5 ticks, RAW ECN)

Data: XAUUSD-ECNc 2026-07-01 → 08-07, BTCUSD.c 2026-07-01 → 08-13.
Costs: real bid/ask on every tick, one-tick latency, commission $3 per lot per side.
Train / test = first 60% / last 40%.

| Preset | TF | RSI / fast / slow | wait after square | cross-failed exit | SL | trail start / distance | max spread |
|---|---|---|---|---|---|---|---|
| **Gold M30** (default) | M30 | 14 / 2 / 7 | 12 bars | on (2 bars) | 3 × ATR | 1 / 1.5 × ATR | $0.30 |
| Gold M15 | M15 | 21 / 2 / 5 | 6 bars | off | 2 × ATR | 1 / 0.5 × ATR | $0.30 |
| BTC M30 | M30 | 21 / 2 / 5 | 6 bars | off | 3 × ATR | 1.5 / 0.75 × ATR | $25 |

| Gold M30 swing | M30 | 10 / 2 / 10 | 12 bars | on (2 bars) | swing low/high of last 5 bars + 0.1 ATR | 2 / 2 × ATR | $0.30 |
| Gold M15 time | M15 | 21 / 2 / 5 | 6 bars | off | 1.5 × ATR, **time stop 24 bars** | 1 / 0.75 × ATR | $0.30 |
| BTC M15 range | M15 | 10 / 3 / 7 | 6 bars | off | 4 × average range(14) | 2 / 0.5 × range | $25 |
| BTC M30 ATR50 | M30 | 21 / 2 / 5 | 6 bars | off | 4 × ATR(50) | 2 / 0.5 × ATR(50) | $25 |

No take-profit on any preset. ATR = ATR(14) of the signal bar. Alternative units (ATR50, average
range, Donchian width) are rescaled to the median ATR(14) of the last 1500 bars, so "4 ×" means
four typical ATRs.

The last four presets come from the multi-method calibration (`calibration/MULTI_RESULTS.md`):

| Preset | Trades | Win | PF | PF train / test | Expectancy | 0.5% risk return / DD | Neighbours + |
|---|---|---|---|---|---|---|---|
| Gold M30 swing | 68 | 31% | 1.55 | 1.82 / 1.37 | +0.233R | +7.8% / 5.6% | 85% |
| Gold M15 time | 206 | 56% | 1.36 | 1.29 / 1.49 | +0.112R | +10.4% / 3.0% | 58% |
| BTC M15 range | 127 | 65% | 1.52 | 1.31 / 1.81 | +0.100R | +6.1% / 2.3% | 54% |
| BTC M30 ATR50 | 140 | 56% | 1.49 | 1.35 / 1.73 | +0.070R | +4.5% / 1.8% | 47% |

### Results (each trade in R = multiples of the SL distance)

| Preset | Trades | Win rate | Avg win | Avg loss | Expectancy | PF | R train / test | Weeks positive |
|---|---|---|---|---|---|---|---|---|
| Gold M30 | 72 | 32% | +0.63R | −0.17R | +0.087R | 1.78 | +2.6 / +3.7 | 6 / 6 |
| Gold M15 | 192 | 61% | +0.54R | −0.59R | +0.101R | 1.44 | +9.9 / +9.5 | 4 / 6 |
| BTC M30 | 146 | 58% | +0.44R | −0.44R | +0.071R | 1.39 | +4.6 / +5.8 | 4 / 7 |

### Risk per trade ($10,000 account, lots rounded down to the broker step)

| Risk | Gold M30 return / max DD | Gold M15 return / max DD | BTC M30 return / max DD |
|---|---|---|---|
| 0.25% | +0.1% / 0.3% (lot too small: 14 of 72 trades placed) | +4.4% / 0.8% | +2.2% / 1.3% |
| **0.5%** | **+2.3% / 0.5%** | **+9.2% / 1.8%** | **+4.9% / 2.7%** |
| 0.75% | +4.0% / 0.9% | +14.8% / 3.1% | +7.3% / 4.1% |
| 1.0% | +5.1% / 1.3% | +19.9% / 4.3% | +10.3% / 5.5% |
| 2.0% | +11.4% / 3.0% | +41.1% / 8.6% | +22.0% / 10.8% |

Longest losing streaks: Gold M30 8, Gold M15 4, BTC M30 5. The worst single trade lost up to
1.9R (gaps through the SL), so real risk per trade can briefly be about twice the setting.

## How much to trust each preset
* **Gold M30**: chosen before the wide parameter search, positive in all 6 weeks, and all 27
  neighbouring exit settings profitable. The most trustworthy preset.
* **Gold M15 / BTC M30**: best of ~750 entry settings × 3–4 timeframes. Profitable in both
  halves and around their exit settings, but the same entry settings lose on the neighbouring
  timeframes (gold 30m/60m, BTC 15m/60m). Likely partly a fit to this period. Run them on a
  demo first.
* The original Pine defaults rank 23rd of 748 on gold and lose on BTC.

## Recommended start
* Risk **0.5%** per trade (max 1%). Below about $20k at 0.25%, gold M30 lots round to zero.
* Strategy Tester: *Every tick based on real ticks*, then forward-test on demo for 4+ weeks.
* Use one magic number per chart. Turn off "Only trade on the preset's timeframe" only for testing.

Not modelled: swaps, weekend gaps beyond the data, and broker requotes.

## Out-of-sample check (new ticks, never used in calibration)

Data: XAUUSD-ECNc and BTCUSD.c, 2026-09-01 → 09-15 and 09-28 → 10-08 (`calibration/oos_test.py`,
each block run separately). Same costs, $10k at 0.5% risk, lots rounded down.

| Preset | Calibration PF | **Out-of-sample PF** | Trades | Win | Expectancy | 0.5% return / DD | Weeks + |
|---|---|---|---|---|---|---|---|
| Gold M30 swing | 1.55 | **1.83** | 35 | 37% | +0.40R | +6.6% / 2.3% | 3 / 5 |
| Gold M15 | 1.44 | **1.33** | 120 | 60% | +0.08R | +3.9% / 1.2% | 4 / 5 |
| Gold M15 time | 1.36 | **1.31** | 129 | 56% | +0.09R | +5.2% / 2.0% | 4 / 5 |
| BTC M30 ATR50 | 1.49 | **1.22** | 88 | 53% | +0.03R | +1.2% / 1.3% | 3 / 5 |
| Gold M30 | 1.78 | 1.14 | 55 | 36% | +0.02R | +0.1% / 0.9% | 3 / 5 |
| BTC M30 | 1.39 | 1.03 | 94 | 54% | +0.01R | −0.1% / 1.9% | 3 / 5 |
| BTC M15 range | 1.52 | **0.77** | 66 | 55% | −0.07R | −2.1% / 3.2% | 1 / 5 |

Held up: all four gold presets made money, the two M15 gold presets kept PF ≈ 1.3 with 4 / 5
positive weeks. BTC M15 range failed (do not use); BTC M30 is breakeven; BTC M30 ATR50 is the only
BTC preset still positive.

## Swept calibration on all data (EA v1.20)

`calibration/sweep.py`: all ticks Jul 1 – Oct 8 (≈ 9 weeks per symbol), timeframes 5m–2h,
216 entry settings, 7 distance units, swing stops, time stops and exit rules. Scored on
4 time blocks (early Jul / late Jul–Aug / early Sep / late Sep–Oct): 0.5 × worst block +
0.5 × average block, smoothed over neighbouring settings.

| Preset (EA value) | Settings | Trades | Win | PF | PF per block | 0.5% return / DD | Status |
|---|---|---|---|---|---|---|---|
| **BTC H1 range (9)** — new | RSI 14/2/10, wait 6, no cross-fail; SL 1 × avg range, trail 1 / 2 | 50 | 46% | **2.28** | 1.87 / 1.45 / 2.74 / no loss | +14.4% / 3.7% | recommended |
| **Gold M15 (1)** — new default | unchanged | 301 | 60% | 1.35 | 1.32 / 1.39 / 1.25 / 1.44 | +10.9% / 2.4% | recommended |
| **Gold M30 swing (4)** | unchanged | 102 | 33% | 1.71 | 6.56 / 1.22 / 1.20 / 3.03 | +15.2% / 5.8% | recommended |
| **Gold M15 time (5)** | unchanged | 324 | 56% | 1.29 | 1.25 / 1.29 / 1.30 / 1.31 | +12.9% / 3.9% | recommended |
| **BTC M30 ATR50 (7)** | unchanged | 228 | 55% | 1.38 | 1.22 / 1.81 / 1.07 / 1.52 | +5.9% / 1.8% | recommended |
| Gold H1 swing (8) — new | RSI 14/3/7, wait 24, cross-fail on; SL swing 20 bars, trail 0 / 1.5 ATR | 33 | 39% | 3.31 | 0.67 / 5.33 / 8.72 / 1.33 | +9.8% / 1.8% | experimental |
| BTC M15 time (6) — replaced | RSI 21/2/10, wait 6; SL 4 ATR, no trail, time stop 24 | 191 | 43% | 1.46 | 1.14 / 1.57 / 0.98 / 2.94 | +8.7% / 2.7% | experimental |
| Gold M30 (0) | unchanged | 126 | 33% | 1.37 | 1.24 / 1.80 / 0.63 / 2.50 | +2.0% / 0.9% | not recommended |
| BTC M30 (2) | unchanged | 240 | 57% | 1.24 | 1.07 / 1.82 / 1.11 / 0.91 | +5.0% / 2.6% | not recommended |

Preset 6 used to be "BTC M15 range", which failed out of sample (PF 0.77) and is replaced.
Losing everywhere: gold 5m, BTC 5m, BTC 2h. All numbers come from the data they were tuned on,
so expect lower results live; forward-test on demo first.

## Full-period check, all data Jul 1 – Oct 8 (EA v1.21)

New ticks for gold Aug 10–31 and BTC Aug 13–20 were not in the sweep. On them alone the
recommended gold presets lost (Gold M15 PF 0.96, Gold M30 swing 0.79, Gold M15 time 0.89,
Gold H1 swing 0.64), while Gold M30 made PF 1.72; BTC had only one new week (all presets positive
except BTC H1 range, 2 trades). `calibration/full_period.py` then runs every preset over all
the data merged (~14 weeks):

| Preset | Trades | Win | PF | 0.5% return / DD | PF by month (Jul / Aug / Sep / Oct) | Verdict |
|---|---|---|---|---|---|---|
| **BTC H1 range** | 52 | 44% | **2.20** | +14.2% / 3.6% | 1.73 / 1.26 / 2.74 / no loss | every month positive (small sample) |
| **BTC M15 time** | 198 | 44% | **1.51** | +9.9% / 2.8% | 1.35 / 1.57 / 1.11 / 3.40 | every month positive |
| **BTC M30 ATR50** | 247 | 57% | **1.50** | +8.1% / 1.8% | 1.52 / 2.00 / 1.04 / 1.78 | every month positive |
| **Gold M30 swing** (default) | 141 | 31% | **1.43** | +13.3% / 5.8% | 1.65 / 1.05 / 1.05 / 4.15 | every month positive |
| Gold H1 swing | 58 | 33% | 1.68 | +6.8% / 3.0% | 0.38 / 2.23 / 2.13 / 1.33 | July lost |
| Gold M30 | 168 | 36% | 1.47 | +4.1% / 0.9% | 1.32 / 1.90 / 0.87 / 2.06 | Sep lost |
| BTC M30 | 260 | 59% | 1.36 | +7.9% / 2.6% | 1.43 / 1.89 / 1.08 / 0.94 | Oct lost |
| Gold M15 | 403 | 60% | 1.18 | +9.4% / 4.2% | 1.47 / 0.88 / 1.36 / 1.11 | Aug lost |
| Gold M15 time | 431 | 55% | 1.12 | +7.5% / 8.2% | 1.34 / 0.85 / 1.25 / 1.21 | Aug lost |

## EA v1.30: two gold presets from the sweep on all Jul–Oct data

| Preset (EA value) | Settings | Trades | Win | PF | PF by month (Jul / Aug / Sep / Oct) | Return / max DD |
|---|---|---|---|---|---|---|
| Gold M5 swing (10) | M5, RSI 14 / 3 / 7, wait 6, no cross-fail; SL behind 5-bar swing, trail from entry 2 × ATR | 521 | 31% | 1.46 | 1.42 / 2.02 / **0.46** / 2.43 | 0.10%: +16% / 3.8% · **0.25%: +42% / 10.8%** · 0.50%: +96% / 21.4% |
| Gold H1 swing v2 (11) | H1, RSI 14 / 3 / 7, wait 6, cross-fail on; SL behind 20-bar swing, trail from entry 1.5 × ATR | 46 | 33% | 2.24 | **0.65** / 2.42 / 8.40 / 1.34 | 0.25%: +4.0% / 1.0% · 0.50%: +8.6% / 1.8% |

Both were profitable in all four sweep blocks, but the calendar months show one losing month each,
so they are marked experimental. Gold M5 swing has a tight stop, so risk-% sizing takes large
positions: run it at 0.25% or less. The EA now prints a warning (and shows "suggested max" on
the chart) when the risk input is above a preset's suggestion.

## BTC sweep on all Jul–Oct data: no preset change

Best new BTC settings per timeframe (5m and 2h lose or are near flat):

| Setup | Trades | PF | PF by month (Jul / Aug / Sep / Oct) | 0.5% return / DD |
|---|---|---|---|---|
| BTC M30, SL 1.5 ATR, exit on opposite TDI cross | 100 | 1.70 | 1.10 / 4.94 / **0.59** / 1.37 | +12.6% / 4.6% |
| BTC H1, swing-20 SL, trail 1 / 2 ATR | 53 | 1.90 | 2.15 / **0.63** / 1.43 / 24.15 | +7.9% / 3.2% |
| BTC M15 time (current preset 6) | 198 | 1.51 | 1.35 / 1.57 / 1.11 / 3.40 (blocks: one 0.75) | +9.9% / 2.8% |

Each new one has a losing month, while the current BTC M30 ATR50 (PF 1.50) and BTC H1 range
(PF 2.20) presets were profitable in every month, so they stay the top two.

## Set files for the top picks (EA v1.31)

`mt5/sets/` has one MT5 set file per top preset. Each has its own magic number and order comment,
so all four can run on one account.

| File | Chart | Preset | Risk | Magic |
|---|---|---|---|---|
| `XPW_TOP1_GOLD_XAUUSD_M30_swing.set` | XAUUSD M30 | Gold M30 swing (4) | 0.5% | 26060401 |
| `XPW_TOP2_GOLD_XAUUSD_M5_swing.set` | XAUUSD M5 | Gold M5 swing (10) | 0.25% | 26060410 |
| `XPW_TOP1_BTC_BTCUSD_M30_ATR50.set` | BTCUSD M30 | BTC M30 ATR50 (7) | 0.5% | 26060407 |
| `XPW_TOP2_BTC_BTCUSD_H1_range.set` | BTCUSD H1 | BTC H1 range (9) | 0.5% | 26060409 |

Install: copy the files to `MQL5/Presets/` (File → Open Data Folder), attach the EA to the chart
in the table, then **Inputs → Load** and pick the file. In the Strategy Tester use **Load** on the
Inputs tab. Combined, the four can have up to 1.75% of equity at risk at once.
