# danny: final notes of the canonical replica (stage 3)

Strategy: Danny Phantom FX V10.21.1 LiveSafe + FlashGold Direction Filter [Update 1].
Ground truth: `/home/user/master/DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine` at HEAD (`Lnnn` = its lines).
Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
There is no TradingView here: every statement about TradingView's engine below is a reading, not a
measurement. The readings that move the numbers are E2 and E3; each has a counter in every result.

## Files

| file | what |
|---|---|
| `$W/danny.py` | the canonical module: `prepare`, `simulate`, `trades`, `summary`, `run`; paths 'tv' and 'mag'; costs 'tv', 'ours', 'stress' |
| `$W/danny_a.py`, `$W/danny_b.py` | the two stage-2 builds after the reconciliation (equal to the canonical on the 'tv' path); as delivered: `$W/reconcile_danny_orig/` |
| `$W/reconcile_danny.md` | what the two builds disagreed on, who followed the Pine, the hand traces |
| `$W/tests_danny.py`, `$W/tests_danny.log` | the tests (T1-T8) and their last full run |
| `$W/danny_s3_mut.py`, `$W/danny_s3_mut.log` | 12 one-line mutants of `danny.py` against the tests |
| `$W/run_inv_danny.py`, `$W/out/inv_danny_<PAIR>_<TF>.json` | the by-timeframe runner and its 14 result files |
| `$W/inv_tables_danny.py` | the result files as markdown tables (`--aw`, `--manual`, `--full`) |
| `$W/danny_s3_trace_zero.py`, `.log` | hand traces of the zero-quantity corner |
| `$W/danny_s3_martingale.py`, `danny_s3_martingale.log`, `danny_s3_martingale_600.log` | the kernel on a driftless random walk (section 10) |
| `$W/reconcile_danny_cmp.py`, `$W/reconcile_danny_zeroqty.py` | A / B / canonical trade by trade on one cell; the zero-quantity corner against builder A's literal reference |

## 1. The `strategy()` call (L75) and the broker

`pyramiding=0`, `initial_capital=2000`, `default_qty_*` unused (every entry passes `qty=f_qty(...)`),
`calc_on_every_tick=false` (live only), `calc_on_order_fills=true`, `process_orders_on_close=true`,
`commission_type=percent, commission_value=0.001`, `slippage=75`, `margin_long/short=0.2` (not modelled:
counter `margin_breach`, 0 in every one of the 14 cells' runs).

One candle = three phases (E1):
- A. The bracket sent at the previous close (`strategy.exit` stop / limit) is walked along the candle
  ('tv': the candle's own 4-point path; 'mag': its 1-minute sub-bars). Never on the entry candle.
- B. The bar-close run on the position left by A: loss cluster, cooldown, distances, cost filter, forced
  exits, zones and signals, the Update 1 decision, at most ONE market order (entry / reversal, or a dead /
  time / blackout close), filled at this close.
- C. The run after that fill: closed-trade accounting on this `bar_index`, the new trade's entry state and
  its first bracket, active from the next candle's open.

## 2. Cost 'tv' = the script's Properties as TradingView applies them; what 75 ticks mean

- Slippage 75 ticks x mintick 0.01 = **0.75 in price per fill**, against the order, on every MARKET fill
  (entries, reversals, dead / time / blackout / window-end closes: a buy fills at close + 0.75, a sell at
  close - 0.75) and every STOP fill (the stop price, or the open on a gap, - 0.75 for a long, + 0.75 for a
  short). LIMIT fills (the target) get none.
- It is inside the fill PRICE, not a fee: `strategy.position_avg_price` is the slipped price, so the stop,
  the target, the breakeven level, the dead-trade test (`close <= avg`) and the sizing all move with it. That
  is why a 'tv' run and an 'ours' run of the same cell do not have the same trades.
- Commission 0.001 % = `1e-5 x fill price x quantity` on every fill (a reversal = two fills).
- Gold: $0.75 per ounce per fill, $1.50 + about $0.026 per round trip; our cost is $0.30 per round trip.
  One fill costs 2.5 times our whole round trip. The default stop (1.2 ATR) is $0.28 / $0.71 / $1.32 / $1.97 /
  $2.86 / $3.91 / $5.70 at the median of charts 1 / 5 / 15 / 30 / 60 / 120 / 240, so the Property alone is
  5.4 / 2.1 / 1.15 / 0.78 / 0.53 / 0.39 / 0.27 R per round trip. Measured on the default runs (filter on,
  normal, $2,000 account): slippage paid $1,845 (XAU 15), $1,970 (XAU 30), $1,854 (XAU 60), $950 (XAU 120),
  $486 (XAU 240), commission $9 to $33. On charts 1, 5 and 15 the slippage of one fill exceeds or nears the
  stop distance: the stop of a long is above the close right after the fill and the trade is stopped at the
  next open. In the TradingView view no gold cell is positive in either direction; with the default direction
  every cell up to 120 minutes loses 75 to 100 % of the account (XAU 240: 35 to 55 %), by the Property, not
  by the signals: the same cells with our costs lose 15 to 45 % on charts 60 to 240.
- BTC: $0.75 per coin is 0.0009 % of the price; with the commission a round trip costs about $3.3 per coin
  against about $35.5 with our costs. TradingView's report is close to cost-free there: BTC 60 default pays
  $33 of slippage and $39 of commission in two years where our costs charge $671. BTC "1", filter off, shows
  +195,422 % (33,518 trades) in the TradingView view and -99.97 % with our costs.
- 'ours': XAU $0.15 per unit per fill; BTC 0.02 % of the fill value + $0.10 per unit per fill; no slippage.
  'stress': XAU $0.26 per unit per fill; BTC 0.035 % + $0.11 per unit per fill (the tick is a fee there, the
  prices are unshifted, as in apex / hrd).

## 3. Two direction inputs, kept separate

- `signalDirection` (L85, the older "Signal direction"): "Inverted (V10 design)" (default) or "Original
  (un-inverted)". It maps the zone signals to the normal BUY / SELL BEFORE the directional time windows and
  the filter (L1172-1175).
- `dpInv` (alias `inv`, L832, Update 1): flips the ORDER after the gate (L1291-1296). The decisions are made
  on `dpPosN = -position`; a normal BUY needs `fgfBuyOk` and is placed as a SELL; a normal SELL needs
  `fgfSellOk`, is tried only when the BUY is not taken, and is placed as a BUY; the one-entry-per-zone reset
  clears the zone that gave the signal (`dpLongFromDemand`). Everything after the entry reads the real
  position. `raw_*`, `blocked_*` and the trades column `sig` stay on the signal's side; `dir`, `long`,
  `short` are the real side.
- Header property, tested on every cell by the runner: with the filter off and no directional window in
  force, `(dpInv on, X)` gives the trades of `(dpInv off, the other signalDirection)` on every column
  (`sig` mirrored). With the filter on it does not (BTC 60: 632 against 434 trades), nor on the XAUUSD 5m
  preset cell (directional windows).

## 4. Readings of TradingView (the spec's E1-E14, as implemented)

| id | reading | effect / counter |
|---|---|---|
| E1 | three phases per candle; a bracket placed or re-sent at candle i is active from the open of i+1 | section 1 |
| E2 | `varRollback` True (default): before every further run on one bar the `var` variables go back to the end of the previous bar (`varip` do not). Consequences: (i) the one-entry-per-zone reset of the entry run is lost, (ii) `cooldownUntilBar` is lost, (iii) a same-side entry on the candle where the bracket closed the previous trade keeps that trade's `atrE, slE, tpE, trailArmed, beArmed, trailStop` | `inherited`; `runs_aw` = the same runs with `varRollback` False |
| E3 | an entry on the candle where the bracket just closed the old trade is decided and filled at the candle's CLOSE (TradingView most likely decides it in the run after the intrabar fill and fills at its next tick) | `reentry_same_bar`, `reentry_leg1` |
| E4 | stop and limit touched in one bar: the first along open -> nearer extreme -> other extreme -> close; open test first (stop before limit); inclusive comparisons; no rounding | |
| E5 | `strategy.exit` re-sent with the same id replaces the levels from the next candle; no hidden trailing state | |
| E6 | `math.max / math.min` with na = na; a bracket with both prices na does not exist | Points mode with `slPointsIn = 0` |
| E7 | `strategy.entry` with `qty <= 0` places no order | `zero_qty`; see section 6 for what the Pine then does |
| E8 | a market order placed in a post-fill run at the close fills at that close (C3: entry from flat on a `preBlackoutClose` candle is closed there, kind 'blackout') | `zero_length`; unreachable with the defaults |
| E9 | `strategy.equity` = cash after every cost paid + open P/L at the close (a reversal is sized on an equity that still holds the trade being closed); `strategy.closedtrades.profit` = P/L net of both costs, in every cost mode; a loss is `pnl < 0` | |
| E10 | orders of the last candle fill at its close; a trade still open is closed there as a market fill, kind 'end' | `exit_end` |
| E11 | ticker XAUUSD / BTCUSD, mintick 0.01, pointvalue 1 | |
| E12 | `time(timeframe.period, sess)`: the bar OPEN in the exchange time zone (XAU New York, BTC UTC) in `[start, end)`, wrapping over midnight, every day unless the string has a `:days` suffix | both session inputs are off by default |
| E13 | no price / quantity rounding beyond `qtyStepS3`; no margin calls; no order-count trimming | `margin_breach` |
| E14 | trading starts flat at the window start with clean counters; only the zones carry over (seed from row 0 of the data file) | |

How much rests on E2 and E3 (default inputs, TradingView view, the 14 cells, 4 runs each): 131,129 trades,
of which 19,480 (14.9 %) are same-candle re-entries; 17,359 of those inherit the closed trade's entry state;
1,779 follow an exit at the open or on the first leg (TradingView would then fill them at an extreme of
the candle, not at the close). `varRollback` False removes (i)-(iii): BTC 60 default 779 -> 648 trades,
-42.4 % -> -39.2 %; inverted 632 -> 563, +47.7 % -> +60.7 %. Both views are in every result file.

`varRollback` False means "one run per candle, the code read top to bottom". It is NOT a several-runs
emulation without rollback: there the run after the entry fill would create again a zone that the reset had
just cleared when the entry candle is itself a spike (about 40 % of the entries). Three models exist; the
replica offers the first two.

## 5. Replica choices where the Pine is silent

- Stop label: 'trail' when the trailing stop is strictly beyond the fixed stop (or there is none), 'be' when
  breakeven moved the stop, else 'sl'. `strategy.exit` has one stop price; the label is ours.
- `qty_capped` counts ORDERS PLACED whose quantity `maxQtyS3` or the margin cap reduced; a decision that ends
  at zero is `zero_qty` only. `net_r` sums `pnl / (sl_dist x qty)` over the trades that have a stop.
- `reentry`: 0, or where the bracket filled: 1 = at the open or on the first leg, 2 = second leg, 3 = third
  leg. On the 'mag' path it is 2 / 3 only when the fill is in the LAST 1-minute sub-bar of the candle, else
  1: 1 always means "TradingView's next tick is not this candle's close". (SPEC_danny section 11 says "2 for
  any re-entry on 'mag'"; that would make chart "1" differ between 'mag' and 'tv' in this column.)
- Exit time of a bracket fill: `t_open` of the candle ('tv') or of the 1-minute sub-bar ('mag'); every other
  exit: `t_close`.
- Summary as `hrd.summary_fast`: drawdown on the bar-close equity incl. open P/L; fair halves by
  `entry_time <= mid`, `prod(1 + pnl / eq_before) - 1`.
- A filter input (`fgf*`) or a SIGNAL input passed to `simulate` must equal what `prepare` used.

## 6. Where the canonical module follows the Pine and not SPEC_danny.md

Both only act after a decision sized to zero (`zero_qty > 0`: an account that can no longer afford the
0.001 step), and both stage-2 builds had followed the brief. Traces: `$W/danny_s3_trace_zero.log`.

1. **The reset of a zero-quantity decision on a candle where the bracket filled** (brief, B12: the reset
   persists whenever `q <= 0`). Under the brief's own E3 that decision is made in the run that follows the
   intrabar fill; the bar-close run comes after it, starts from the previous bar's variables (the reset is
   gone) and cannot decide again (`varip` lock, L1241-1243). Rule in the module: the reset persists if
   `not varRollback or (q <= 0 and no bracket fill on this candle)`.
2. **`pending*` after a zero-quantity decision** (brief, E7: not replicated). L1304-1307 / L1329-1332 write
   `pendingLongAtr / pendingShortAtr / pendingSlDist / pendingTpDist` whatever the quantity. With no fill no
   further run rolls them back. `pendingSlDist / pendingTpDist` are cleared on every flat candle (L1400-1401),
   the two pending ATRs are not: the next filled entry on that side takes the stale ATR as `longAtrAtEntry /
   shortAtrAtEntry` (L1372 / L1384), which only the breakeven trigger reads; a stale `pendingSlDist` survives
   only while a position stays open (a reversal decision sized to zero) and then sets `slDistAtEntry /
   tpDistAtEntry` of the reversal that follows. Replicated with `varRollback` True on candles without a
   bracket fill. With `varRollback` False the entry run overwrites all four before they are read, so nothing
   changes there.

Also beyond the brief: a window that reaches the first `atrLenS2 - 1` rows of the data file runs as the Pine
does (ATR na: every distance na, `f_qty` returns 0 in Risk mode, a Fixed-quantity trade has no bracket).

## 7. Path 'mag'

The bracket of the open trade walks the 1-minute sub-bars of the chart candle in time order (rows of
`data/<PAIR>_1.parquet` with `t_open` in `[candle t_open, candle t_close)`); each sub-bar gets the open test
and its own 4-point path; the levels are constant during the candle (the script re-sends them once per
candle, at its close: there is no intrabar trailing in this script). Entries, reversals, dead / time /
blackout closes and all the bar-close logic stay on the chart candle. Chart "1": 'mag' == 'tv' on every
column (tested). The sub-bar table is checked against the chart bars (same open / high / low / close); 2,099
of the candles tested start with a hole in the 1-minute data, their first sub-bar opens later at the same
price.

On this script the path matters little: the bracket is two fixed levels, so 'mag' only changes which of
stop / target comes first in a candle that touches both, and gap fills at sub-bar opens. BTC 60 default:
-42.361 % ('tv') against -42.361 % ('mag') with the script's costs, 779 trades both. The cost mode is what
separates the TradingView view from the 1-minute view with our costs.

Not the Bar Magnifier of TradingView: there a same-candle re-entry would fill at the next 1-minute tick
after the exit; here it fills at the chart candle's close (E3).

## 8. Presets, inputs

- `presetMode` "Auto" = the XAUUSD 5m preset on XAU "5" only; "XAUUSD 5m" forces it; "Manual" also honours
  `manualZoneTrend`. The five other presets raise `NotImplementedError` (other markets; NAS100 would need
  `strategy.opentrades.max_runup`).
- XAU "5" with the defaults takes NO trade: the preset's cost filter needs a stop of about $6.10 (4 x (2 x 75
  ticks + 0.002 % of price)); 1.2 ATR(14) of 5-minute gold never exceeds $3.3 in the window (0 of 98,787
  candles pass). The result file adds `runs_manual` (`presetMode` "Manual").
- Accepted without effect: `limitOneFlatExitPerBar` (the flat-exit stamp is a `varip` whatever the switch
  says, and a flat position has no forced exit to repeat), `useV106GrowthSlTp` (never read by the Pine),
  `useV1021NasAdaptiveDead`, `nasAdaptiveRunupAtr` (NAS100 preset); with `varRollback` True also
  `useOnePerZone`, `useCooldown`, `cooldownIn` (unless `zero_qty > 0`). Drawing and alert inputs are ignored.
- `limitOneDecisionPerBar` (default True) has ONE effect on history (stage-4 audit, section 12): off, a
  decision sized to zero on a candle where the bracket filled is repeated by the bar-close run, so its zone
  reset and `pending*` writes stay. Only reachable when `zero_qty > 0`.

## 9. Not implemented / cannot be reproduced

- TradingView itself: E1-E3 and E8 cannot be tested here. The fill price of a same-candle re-entry in
  TradingView's report (the close, or an extreme of the candle) is unknown; the trades concerned are counted.
- Live behaviour (a re-entry inside a forming candle, the locks, alerts, webhook delivery).
- Volume: the signal is built on volume. Gold = Dukascopy tick count, BTC = Bitstamp volume; another feed
  gives other spikes. Sessions: gold bars are 18:00-17:00 New York; another broker's session changes the
  bars, the Sunday bars and the blackout candles.
- TradingView's margin calls, rounding of prices / quantities to the symbol, the order-count limit, the bars
  a plan can load (two years of 1-minute bars do not fit a chart: the BTC "1" and XAU "1" rows are the
  replica's, not something TradingView could show).
- Data Window "FGD raw ..." on a candle where an entry fills: TradingView shows the last run (0); the
  replica counts the decision run.
- A ruined account (equity too small for the 0.001 step) stops trading: `zero_qty`, flagged `ruined` in
  the result files and "(!)" in the tables. XAU 1, XAU 15 and XAU 5 Manual in the TradingView view; BTC 1,
  BTC 5 and XAU 1 with our costs.

## 10. Does the kernel create P/L by itself? (`$W/danny_s3_martingale.py`, logs next to it)

BTC "1" in the TradingView view is positive in BOTH directions (+195,422 % normal, +167,030 % inverted,
filter off; +0.066 and +0.068 R per trade after the script's costs), which no directional signal can
explain. Check: the candles of BTC "1" replaced by a driftless random walk (open = previous close), the
cell's spike frequency, zero costs, fixed quantity, default exits and trail + breakeven, option off and on,
both `varRollback`:
- walk of 600 Gaussian steps per candle: mean R per trade between -0.001 and +0.008, every one within 1.7
  standard errors of 0 (47,000 to 79,000 trades per run): the kernel has no look-ahead and no fill bias on
  a fine path;
- the same candle volatility in 60 coarse steps: +0.02 to +0.04 R per trade (6 to 12 standard errors). That
  is the stop "filling at its level" while the path jumps over it.
So a bracket fill at its exact level is worth money whenever the stop distance is of the size of the path's
jumps. On BTC "1" the default stop ($46 at the median) is about one candle's range, and the script's
Properties charge 0.07 R per round trip. This is offered as the likely reason for the both-directions
profit on BTC "1" and "5" in the TradingView view; it was measured on synthetic candles only. Our costs
(0.77 R per round trip on BTC "1", 0.26 R on BTC "5") remove it. Those two rows are not results.

## 11. Tests (`python3 -I tests_danny.py`; last full run in `tests_danny.log`)

T1 A == B == canonical on 10 cells (BTC, XAU x 1, 5, 15, 60, 240): 728 cases, 1.6 million trades, every
column and every summary field (80 random calibration-grid settings, 250 off-grid, 70 edge windows).
T2 'mag' on chart "1" == 'tv' (bitwise). T3 'mag' with one fake sub-bar per candle == 'tv'. T4 30 'mag' + 10
'tv' random settings on 2-month windows against a slow pure-Python reference of the exits written for the
test. T5 fair halves, costs, slippage, net of each cost mode recomputed from the trade list. T6 the Update 1
properties (header P1 and its two counter-examples, Allow buys / sells, mirror P2, unfused original P3,
`varRollback` independence P4). T7 the kernel against builder A's literal several-runs transliteration of
the Pine (12 runs, 15,765 decisions sized to zero among them); the sub-bar table. T8 timing (BTC "1",
1,039,430 candles: `simulate` 0.03 s on both paths; `prepare` with the filter 2 s there, and the whole
BTC "1" cell of the runner, two `prepare` and 40 `simulate`, 8.4 s in a fresh process, peak memory 2.39 GB).
Last full run: 28 tests, 28 PASS.

Mutants (`python3 -I danny_s3_mut.py`, log `danny_s3_mut.log`): 12 one-line changes of `danny.py` (the
'mag' loop, the path rule, slippage on a limit fill, the sign of the stop slippage, the Update 1 gate, the
zone the reset clears under `dpInv`, the inherited state, a cost constant, the 'mag' exit time, the pending
ATR, the reset rule of section 6.1, the fair-half split): all 12 make at least one test fail. Three are
caught by one test only: the 'mag' exit time (T4), the pending ATR and the reset rule (T7).

## 12. Stage-4 audit (2026-11-26)

One change to `danny.py`; the default results are untouched (the 14 result files were re-run and are identical:
600 runs; `tests_danny.py` 28 PASS). `limitOneDecisionPerBar` was listed as "no effect". The literal
several-runs emulation shows one: with the switch off, a decision sized to zero on a candle where the bracket
filled is taken again by the bar-close run (no `varip` lock), and nothing rolls that run back, so its zone
reset and pending ATR stay. The kernel now does that (B12). Against the emulation, switch off:
- 12 settings, most with a ruined account (`$W/danny_s4b/lock4b.py`): before the change 8 of them differed
  (16 of 24 runs; counters in most, trades in two: XAU 30 filter off 1,330 against 1,337; XAU 5 Manual, our
  costs, 2,770 against 2,762);
- 24 settings with a coarse quantity step, where decisions floor to zero while the account lives
  (`$W/danny_s4b/lock4c.py`, breakeven on): before the change all 24 differed, 12 in the trades (BTC 15, step
  0.08: 1,225 against 1,001);
- after the change none differs in either probe. With the switch on (the default) there was no difference
  before or after (the same settings). `tests_danny.py` never switches it off: the two probes are its only test.

What was compared, all with 0 differences (scripts and logs in `$W/danny_s4/` and `$W/danny_s4b/`):
- a literal several-runs emulation of L1016-1486 written from the Pine alone (`danny_s4/ref4.py`: the script
  body is one function, `var` restored before every run on a bar, `varip` and the broker never; nothing
  about "inherited state" or "lost reset" is coded). 'tv': 43 settings on each of the 12 cells from 5 minutes
  up, 11 on each 1-minute cell; 'mag': 11 settings on 4 cells. Repeated after the change on BTC 60, XAU 5
  Manual, XAU 15, XAU 30 (43 each) and 'mag' BTC 15, XAU 60 (`danny_s4b/cmp4_after.log`);
- the zone / signal layer by backward search from each candle, no state machine (`danny_s4b/own_zone.py`:
  spikes, EMA flags, the zone and its keys seen by every candle, both original signals), 8 runs;
- the New York clock gates with `zoneinfo` per candle and the loss-cluster pause replayed from the trade list
  (`danny_s4b/own_gates.py`), 9 runs; the bar-close equity curve and 27 summary fields rebuilt from the trade
  list (`danny_s4b/own_summary.py`), 9 runs (`exposure` differs by one candle when a trade is closed at the
  window end: the module counts that candle as held).
Mutants: 32 one-line changes (`danny_s4/mut4.log`, `danny_s4b/mut4b.log`). 28 fail the stage-3 tests in the
reduced harness of `danny_s3_mut.py`; dropping the same-close blackout close (C3) fails only the full T1 (the
off-grid inputs, which that harness leaves out); the two mutants of the new lines fail only the two probes
above; one (`sell_go` without `not buy_go`) cannot change anything, a candle cannot give both signals.

Limits a reader of the results must know:
- **E3 decides the sign of several 'tv' rows.** If TradingView fills a same-candle re-entry at the next point
  of its 4-point path instead of the close (`ref4.py`, `reentry='leg'`; simplified: the new bracket is not
  walked on the rest of that candle), the default direction gains a lot and the inverted one does not:
  BTC 60 filter off, normal -10.4 % -> +159.7 % (281 such fills of 1,179 trades), inverted +41.8 % -> +30.6 %;
  BTC 60 filter on, normal -42.4 % -> -11.4 %, inverted +47.7 % -> +45.5 %; BTC 240 filter on, normal
  +15.2 % -> +44.6 %, inverted +14.8 % -> +7.9 %; XAU 60 stays between -73 % and -89 %
  (`danny_s4/sens4_*.log`, `danny_s4b/sens_recheck.log`). The other untestable point, a stop already beyond
  the close when it is placed, never occurs on the cells probed (BTC 15, 60, 240; XAU 30 to 240: 0 cases).
- **The 'tv' view is for a 0.01 tick on both pairs.** The Property is 75 TICKS. On a whole-dollar BTC symbol
  it is $75 per fill: BTC 60 filter on, normal -42.4 % -> -89.9 %, inverted +47.7 % -> -64.4 %. On a
  0.001-tick gold symbol it is $0.075: XAU 60 filter on, normal -84.5 % -> +3.7 %, inverted -77.5 % -> +9.8 %,
  and the XAUUSD 5m preset then trades (filter on: 1,108 trades, -88 %) instead of taking none
  (`danny_s4/tick4_*.log`, `danny_s4b/tick_recheck.log`).
- **BTC "1" and "5" in the 'tv' view measure the fill model, not the signals.** Random entries on a random
  side with the script's exits (stop 1.2 ATR, target 4.1667 R, dead exit, time stop), no costs, own bracket
  engine: +0.15 R per trade on BTC "1" (640,000 trades, 8 runs between +0.13 and +0.15), +0.04 R on BTC "5",
  +0.035 R on BTC "15", within noise from 60 minutes up; gold "1" +0.014 R (`danny_s4b/placebo.log`). The
  script's own BTC "1" rows show +0.04 to +0.07 R after its costs of 0.07 R: the same amount. Our costs
  (0.77 R per round trip on BTC "1") remove it.
- In the 'mag' rows `reentry_leg1` is nearly every re-entry (there the label 1 means "not in the candle's
  last minute"); it is comparable between cells only on 'tv' rows.
