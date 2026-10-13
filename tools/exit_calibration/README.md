# Exit calibration for XPW ShapeMap v8 on VT Markets (XAUUSD, BTCUSD)

This folder holds the procedure and the ranking tool used to pick the exit
settings of `XPW_ShapeMap_v8_EA.mq5` (SL distance, time stop, trailing / TP)
on a VT Markets account that charges 0.6 per lot commission.

The EA's exit logic lives in `XPW/ShapeMapV8Execution.mqh` and
`XPW/ShapeMapV8Inputs.mqh` (the ATR-capped SL in `XpwV8ExitDistances`, the
bar-count time stop in `XpwV8HeldTimeStop`, trailing in `CXpwV8Runtime::Manage`).
Those includes are not in this repository, so the calibration has to run in
the MT5 Strategy Tester on the VT Markets server data and the results are
ranked here.

## 1. Cost floor (what an exit must clear)

Commission is charged per lot. Spread is paid once per round turn. Verify the
contract size, tick size and the live raw spread in MT5
(right-click the symbol -> Specification) before trusting these numbers.

| Symbol | Contract | Tick | Commission 0.6/lot/side, round turn | Typical raw spread | Round-turn cost per 1.0 lot | Cost in price units |
|---|---|---|---|---|---|---|
| XAUUSD | 100 oz | 0.01 (= $1 per 1.0 lot) | $1.20 | 0.10 - 0.20 ($10 - $20) | $11 - $21 | about 0.11 - 0.21 (11 - 21 ticks) |
| BTCUSD | 1 BTC | 0.01 | $1.20 | $15 - $40 | $16 - $41 | about 16 - 41 |

If VT Markets quoted 0.6 as the round-turn charge, halve the commission column
(`--sides 1` in the ranker). On both symbols spread dominates commission by an
order of magnitude, so exit calibration is really spread calibration. The
commission only matters for the time stop and any scratch exit, because those
produce many trades with tiny gross results.

Rule of thumb for an exit to survive live costs:

- Average winner must be at least 5x the round-turn cost in price units:
  XAUUSD >= 1.00 (100 ticks), BTCUSD >= 150 - 200.
- Trailing offset must never be smaller than 2x the spread, otherwise the
  trail is stopped by spread noise: XAUUSD >= 0.30, BTCUSD >= 60.
- Net expectancy per trade after costs (the ranker's `edge` column) must be
  >= 1.0x the round-turn cost in-sample and >= 0.5x out-of-sample.

## 2. Tester setup

1. Symbol: the VT Markets `XAUUSD` and `BTCUSD` from the live or demo server
   you will trade on, so spreads and session times match. Use
   "Every tick based on real ticks". A model built on M1 OHLC does not see the
   spread widening at the open and misprices intrabar stops.
2. Period: the chart period the EA is run on. Use at least 12 months of data,
   split as 9 months in-sample, 3 months forward (Tester -> Forward 1/4).
3. Lot size: fixed, e.g. 0.10. Do not optimize with risk-based sizing; the
   commission is then not proportional to the pass result and the ranking is
   wrong.
4. Commission: check the Deals tab of a single run. If the commission column is
   non-zero, the tester already charges the broker rate and you pass
   `--tester-has-commission` to the ranker. If it is zero, the ranker adds
   0.6 x sides x lots per trade.
5. Optimize exit inputs only (leave signal inputs at the supplied defaults).
   Optimization criterion: Custom (the EA returns `STAT_PROFIT` from
   `OnTester`, the ranker re-scores anyway). Use Complete (slow) for grids of
   this size; the genetic optimizer hides neighbourhood information.

## 3. Search grids

Exit inputs are named in `XPW/ShapeMapV8Inputs.mqh`; the grid values below are
in the units the EA uses (ATR multiples, bars, ticks). Keep the three grids
coarse first, then refine around the winner.

XAUUSD (tick 0.01)

| Exit input | Grid | Note |
|---|---|---|
| SL distance (ATR multiple) | 1.0, 1.5, 2.0, 2.5, 3.0 | ATR length as supplied (14) |
| Time stop (bars) | off, 20, 40, 60, 90 | the commission-sensitive one |
| Trailing / TP distance (ticks) | 30, 50, 80, 120, 180 | never below 30 ticks (2x raw spread) |

BTCUSD (tick 0.01, prices in whole dollars matter)

| Exit input | Grid | Note |
|---|---|---|
| SL distance (ATR multiple) | 1.0, 1.5, 2.0, 2.5, 3.0 | |
| Time stop (bars) | off, 20, 40, 60, 90 | weekend bars are thin; keep off as a candidate |
| Trailing / TP distance ($) | 60, 100, 150, 250, 400 | never below 2x the spread you measured |

5 x 5 x 5 = 125 passes per symbol, fine for a complete optimization.

## 4. Rank the export

```
python3 tools/exit_calibration/rank_exits.py in_sample.xml --oos forward.xml \
    --symbol XAUUSD --lots 0.10 --commission 0.6 --sides 2 \
    --exit-params "SlAtr,TimeStop,TrailTicks" --min-trades 100 --csv-out xau_scored.csv
```

Replace the three names after `--exit-params` with the exact input names as
they appear as column headers in the exported XML.

The ranker:

- recomputes net profit and net expectancy after the 0.6/lot commission,
- expresses the edge as a multiple of the round-turn cost,
- averages each pass with its grid neighbours (one step on each exit input),
  so an isolated spike loses to a plateau,
- drops passes below `--min-trades`,
- shows the forward-period result next to each in-sample pass.

Pick the top robust pass whose out-of-sample edge is positive and whose
neighbours are all positive. If the top in-sample pass has a negative
out-of-sample edge, the grid is overfitting; coarsen the grid or lengthen
the sample.

## 5. Reading the result

- `edge` >= 1.0 in-sample, >= 0.5 out-of-sample: tradeable exit.
- `edge` between 0 and 0.5: the signal has an edge but the exit gives most of
  it to spread; widen the trailing distance before anything else.
- `edge` < 0 with positive raw tester profit: the pass only looked good
  because the tester did not charge commission; typical for short time stops.
