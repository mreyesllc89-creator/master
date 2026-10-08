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

No take-profit on any preset. ATR = ATR(14) of the signal bar.

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
