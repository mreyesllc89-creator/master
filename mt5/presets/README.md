# MT5 presets

## Asia London Breakout (recommended for demo testing)

EA: `mt5/AsiaLondonBreakout.mq5`. Presets:

| Preset | Symbol | Days | Magic | TradingView script |
|---|---|---|---|---|
| `AsiaLondonBreakout_XAUUSD.set` | XAUUSD-ECN(c) | Mon-Fri | 60601 | `asia_london_breakout_xauusd.pine` |
| `AsiaLondonBreakout_XAUUSD_FridayOff.set` | XAUUSD-ECN(c) | Mon-Thu | 60603 | `asia_london_breakout_xauusd_fridayoff.pine` |
| `AsiaLondonBreakout_BTCUSD.set` | BTCUSD.c | Mon-Fri | 60602 | `asia_london_breakout_btcusd.pine` |
| `AsiaLondonBreakout_BTCUSD_Candidate.set` (midpoint stop) | BTCUSD.c | Mon-Fri | 60606 | - |
| **`AsiaLondonBreakout_XAUUSD_Optimized.set`** (optimizer: midpoint stop, Friday off, skip narrow ranges) | XAUUSD-ECN(c) | Mon-Thu | 60607 | - |
| `AsiaLondonBreakout_XAUUSD_Candidate.set` (superseded: midpoint stop, Monday off) | XAUUSD-ECN(c) | Tue-Fri | 60604 | - |
| `AsiaLondonBreakout_XAUUSD_Candidate_Trail.set` (+ trailing) | XAUUSD-ECN(c) | Tue-Fri | 60605 | - |

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

## MT5 Strategy Tester check (VT Markets, XAUUSD-ECNc, 9 months)

Your tester run (Dec 29 2025 - Sep 30 2026, every tick based on real ticks, Mon-Fri, fixed 0.1 lot) matches this
simulation trade by trade (51 shared days: same direction 51/51, correlation 0.995). Results:

| XAUUSD-ECNc, 178 trades | Before commission | After commission ($3/lot/side) |
|---|---|---|
| Per 1 oz traded | +$1,254, PF 1.51 | +$186 |
| At 1% risk per trade | +25.6%, max DD 4.5% | +4.0%, max DD 8.1% |

By month before commission ($/oz): Jan +251, Feb -206, Mar +143, Apr +183, May +174, Jun +95, Jul +135, Aug +244,
Sep +138. By weekday: Mon -207, Tue +244, Wed +473, Thu +569, Fri +175 (Friday-off does not hold over 9 months).

**Costs decide the result.** On XAUUSD-ECNc 1 lot = 1 oz and the $3/lot/side commission is $6 per oz per round
trip, about 85% of the average trade (+$7.04/oz). With a 100-oz contract at $3/lot (~$0.06/oz) or a commission-free
account (~$0.25/oz spread) the 1%-risk result stays around +25%. Check Market Watch > XAUUSD-ECNc > Specification
(contract size, commission) and ask VT Markets for the lowest-cost gold symbol / account type.

All presets use InpMaxLots = 200 so the 1% risk is not capped on 1-oz contracts.

## XAUUSD: MT5 optimizer result (recommended gold preset)

`AsiaLondonBreakout_XAUUSD_Optimized.set` (magic 60607): stop at the range MIDPOINT, Friday OFF, exit 19:00, no TP, no
buffer, SKIP NARROW RANGES (< 0.5x the 10-day median), 1% risk. From your MT5 optimization (576 runs, XAUUSD-ECNc,
real ticks, commission included, first ~6 months as the optimization period):

| Period | Optimized preset | Current preset | Old candidate (midpoint, Monday off) |
|---|---|---|---|
| First ~6 months (MT5 optimizer) | +11.9%, PF 1.29, DD 7.7% | +0.1% | -4.4% |
| Jul 1 - Sep 30 forward (not used by the optimizer) | +11.6%, DD 6.5% | +4.7% | +11.3% |

Of the optimizer's top-40 settings, 39 were also profitable in the forward months (average +5.3%). Average effect over
all 576 runs: skip-narrow filter +1.7% vs none -2.9%; exit 19:00 +0.3% vs 17:00 -5.3%; Friday off -0.3% vs on -3.9%.
With the midpoint stop, narrow ranges give tiny stops, so the $6/oz commission is a large share of 1R; skipping them
removes those trades. The old candidate failed the first 6 months, so it is superseded.

## Calibration for XAUUSD-ECNc costs (candidate, to verify)

432 settings tested on VT gold ticks (Jul 1 - Oct 8), 1% risk, with the $6/oz XAUUSD-ECNc commission:

| Settings | XAUUSD-ECNc | Low-cost account | Max DD |
|---|---|---|---|
| Current preset (stop opposite side, Mon-Fri, exit 19:00) | +2.9% | +10.6% | 7.5% |
| Stop at range MIDPOINT, Mon-Thu, exit 19:00 | +11.2% | +23.3% | 6.5% |
| Stop at range MIDPOINT, Tue-Fri (Monday off), exit 19:00 = `AsiaLondonBreakout_XAUUSD_Candidate.set` | +11.0% | +23.5% | 5.9% |

Trailing stop (EA inputs InpTrailStartR / InpTrailDistR, off by default), 60 settings tested on the candidate: none
beat no trailing (+11.0%); starting after +2x the stop with a 0.25x trail gave +9.9% with max DD 4.0% instead of 5.9%
(`AsiaLondonBreakout_XAUUSD_Candidate_Trail.set`). On the current preset an early tight trail (start 0.5x, 0.25x)
gave +3.8% vs +2.9%, DD 2.6%, win 70%.

The midpoint stop halves the stop, so at 1% risk the position is twice as large and the fixed commission weighs
half as much. Monday was also the weakest day in the 9-month MT5 test. Found on 3 months: verify with
`AsiaLondonBreakout_XAUUSD_OPTIMIZE.set` (MT5 optimizer, 576 runs, forward test 1/3) before using it.

## BTCUSD.c: MT5 tester (9 months) and calibration

VT BTCUSD.c: 1 lot = 0.01 BTC, no commission (~$17 spread). Your tester run (Dec 29 2025 - Sep 30 2026, 192 trades,
61% real ticks) hit the old 5-lot cap on every trade (~$53 risk instead of $500). Scaled to 1% risk with each
trade's real stop: +21.3%, max DD 6.7%, PF 1.31. By month: Feb +4.5, Apr -2.1, May -4.3, Aug +11.4, Sep +6.8;
by weekday: Mon +4.6, Tue +1.9, Wed -1.1, Thu +4.5, Fri +11.4. BTC presets now use MaxLots 1000.

270 BTC settings on VT ticks (Jul 1 - Oct 8), 1% risk: 96% profitable. Best: stop at the range MIDPOINT, Mon-Fri,
exit 19:00, no trail, no TP: +37.0% (halves +15.9% / +21.1%), DD 7.2% vs +16.3% for the current preset
(`AsiaLondonBreakout_BTCUSD_Candidate.set`). Verify on 9 months with `AsiaLondonBreakout_BTCUSD_OPTIMIZE.set`.

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
