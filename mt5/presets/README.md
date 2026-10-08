# MT5 presets

## Asia London Breakout (recommended for demo testing)

EA: `mt5/AsiaLondonBreakout.mq5`. Presets:

| Preset | Symbol | Days | Magic | TradingView script |
|---|---|---|---|---|
| `AsiaLondonBreakout_XAUUSD.set` | XAUUSD-ECN | Mon-Fri | 60601 | `asia_london_breakout_xauusd.pine` |
| `AsiaLondonBreakout_XAUUSD_FridayOff.set` | XAUUSD-ECN | Mon-Thu | 60603 | `asia_london_breakout_xauusd_fridayoff.pine` |
| `AsiaLondonBreakout_BTCUSD.set` | BTCUSD.c | Mon-Fri | 60602 | `asia_london_breakout_btcusd.pine` |

The two gold presets have different magic numbers, so both can run side by side (e.g. two demo accounts, or
two charts on one account) and their trades stay separate.

**Rule (VT Markets server time, GMT+3):** Asia range = bid high/low 03:00-10:00. At 10:00 place a buy stop at
the range high and a sell stop at the range low; the first fill cancels the other (one trade per day). Stop =
range size from the fill (opposite side). Exit at 19:00 (or a take profit if set). Monday-Friday.

**Test:** VT Markets tick data, Jul 1 - Oct 8 2026 (real bid/ask, real spreads; gold commission
$3/lot/side assumed), simulated tick by tick, 0.10 lot:

| | XAUUSD Mon-Fri (preset) | XAUUSD Mon-Thu (InpFri=false) | BTCUSD Mon-Fri (preset) |
|---|---|---|---|
| Net | +$4,277 | +$5,805 | +$1,388 |
| Profit factor | 1.72 | 2.87 | 1.65 |
| Win rate | 61% | 67% | 48% |
| Trades | 56 | 45 | 65 |
| Max drawdown | $1,878 | $740 | $649 |
| Jul 1-Aug 19 / Aug 20-Oct 8 | +$5,819 / -$1,542 | +$4,576 / +$1,230 | +$236 / +$1,152 |
| Range/exit hours shifted +-1-2 h (27 combinations) | 27/27 profitable | 27/27 profitable | 27/27 profitable |

Gold by weekday (Jul 20 - Oct 8): Mon -$241, Tue -$228, Wed +$2,685, Thu +$1,841, Fri -$1,476. Fridays
lost on gold; the Friday-off figures are a finding on the same data, not a separate out-of-sample test.
Early July (Jul 1-14), not used when the rule was chosen: gold +$1,696 (8 trades), BTC -$77 (7 trades).

Correction: the first version of this README reported gold +$4,056 / PF 2.43 for Mon-Fri. A weekday bug in
the test skipped Fridays on gold (and traded Sunday instead of Friday on BTC). The table above is the
corrected result.

Caveats: about 3 months of one market phase, 45-65 trades; gold was positive in about 10 of 15 weeks, so
losing weeks are normal. Demo-test before live trading. If your broker's server is not GMT+3, shift the hours so the
range is 00:00-07:00 UTC and the exit 16:00 UTC.

## Position sizing: 1% risk per trade (all presets)

All presets use `Risk %` = 1.0: the lot size is set so that the stop loss costs 1% of equity (breakout: stop =
Asia range size; FlashGold: stop = 80 pips). Same VT ticks, Jul 1 - Oct 8 2026, results in % of the account:

| Preset | Trades | Total | Avg per trade | Max drawdown | Min equity for 0.01 lot at 1% |
|---|---|---|---|---|---|
| AsiaLondonBreakout_XAUUSD (Mon-Fri) | 56 | +10.6% | +0.19% | 3.8% | ~$6,000 |
| AsiaLondonBreakout_XAUUSD_FridayOff | 45 | +13.7% | +0.30% | 2.0% | ~$6,000 |
| AsiaLondonBreakout_BTCUSD | 65 | +16.3% | +0.25% | 5.9% | ~$1,500 |
| FlashGoldV5_XAUUSD_H1 | 75 | +40.9% | +0.55% | 9.7% | ~$800 |

With a smaller account the lot rounds down to 0 and the EA skips the trade ("lot size 0"). Running several
presets on one account adds their risk (e.g. 2-3% at once).

## FlashGold v5

EA: `mt5/FlashGoldV5_XAUUSD.mq5` + `mt5/FlashGoldV5_Core.mqh` (both in `MQL5/Experts/`). Preset:
`FlashGoldV5_XAUUSD_H1.set` (= the EA's built-in gold defaults), XAUUSD-ECN H1 chart.

VT Markets ticks Jul 1 - Oct 8 2026, tick by tick, 0.10 lot:

| FlashGold v5 settings | XAUUSD | BTCUSD |
|---|---|---|
| Current default (gold: H1, SL 80 pips, 30% at TP 5R, runner 315 pips, min 3) | +$3,273, PF 1.72, max DD $778 | H4 version: -$192, PF 0.93 |
| Original (gold: ATR SL 2, TP 2R, trail 1.0/0.75 ATR; BTC: $50 SL, $10 trail) | +$1,851, PF 1.12, max DD $1,769 | -$427, PF 0.68 |
| Pip calibration (tight stops) | -$916, PF 0.69 | -$472, PF 0.62 |

(An earlier figure of +$2,186 / PF 1.39 for the gold default included one -$1,087 trade that was an artifact of a
23-hour hole between two tick export files, Jul 29 17:46 - Jul 30 17:00; it is excluded above.)

Use FlashGold v5 on gold only. On BTCUSD every version lost (VT's $17 spread). Exit and entry re-calibrations
on single periods did not hold up on later weeks, so keep the defaults and judge on demo.
