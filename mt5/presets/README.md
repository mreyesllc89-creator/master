# MT5 presets

## Asia London Breakout (recommended for demo testing)

EA: `mt5/AsiaLondonBreakout.mq5`. Presets: `AsiaLondonBreakout_XAUUSD.set`, `AsiaLondonBreakout_BTCUSD.set`.

**Rule (VT Markets server time, GMT+3):** Asia range = bid high/low 03:00-10:00. At 10:00 place a buy stop at
the range high and a sell stop at the range low; the first fill cancels the other (one trade per day). Stop =
range size from the fill (opposite side). Exit at 19:00 (or a take profit if set). Monday-Friday.

**Test:** VT Markets tick data (real bid/ask, real spreads; gold commission $3/lot/side assumed), simulated
tick by tick, 0.10 lot:

| | XAUUSD-ECN | BTCUSD.c |
|---|---|---|
| Period | Jul 20 - Oct 8 2026 | Jul 13 - Oct 8 2026 |
| Net | +$4,056 | +$1,241 |
| Profit factor | 2.43 | 1.83 |
| Trades | 38 | 55 |
| Jul-Aug / Sep-Oct | +$2,242 / +$1,815 | +$637 / +$603 |
| Range/exit hours shifted +-1-2 h (27 combinations) | 27/27 profitable, 27/27 in both halves | 27/27 profitable, 25/27 in both halves |

Out-of-sample checks: a setup picked on Jul-Aug made money on Sep-Oct and the reverse, on both symbols;
the week-by-week walk-forward was positive (gold +$2,214, BTC +$468).

Caveats: 12 weeks of one market phase, 38-55 trades; gold was positive in 6-7 of 12 weeks, so losing weeks
are normal. Demo-test before live trading. If your broker's server is not GMT+3, shift the hours so the
range is 00:00-07:00 UTC and the exit 16:00 UTC.

## FlashGold v5 (not recommended)

The FlashGold v5 EA (`FlashGoldV5_*.mq5`) and its earlier presets were tested on the same VT Markets ticks
(Jul 13 - Oct 8 2026, M1 to H4, exits, entries, inverted signal, market-phase filter). No version held up on
unseen weeks: every setting that looked profitable on one period lost on a later one. Its presets were
removed. The EA is kept for reference only.
