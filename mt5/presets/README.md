# MT5 presets

## Asia London Breakout (recommended for demo testing)

EA: `mt5/AsiaLondonBreakout.mq5`. Presets: `AsiaLondonBreakout_XAUUSD.set`, `AsiaLondonBreakout_BTCUSD.set`.

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

## FlashGold v5 (not recommended)

The FlashGold v5 EA (`FlashGoldV5_*.mq5`) and its earlier presets were tested on the same VT Markets ticks
(Jul 13 - Oct 8 2026, M1 to H4, exits, entries, inverted signal, market-phase filter). No version held up on
unseen weeks: every setting that looked profitable on one period lost on a later one. Its presets were
removed. The EA is kept for reference only.
