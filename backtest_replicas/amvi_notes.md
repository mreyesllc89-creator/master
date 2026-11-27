# amvi: AMVI Full MTF Strategy + FGF [Update 1], canonical replica: interpretations and limits (stage 3)

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/AMVI_Full_MTF_Strategy_FGF.pine` at HEAD (894 lines, `Lnnn`); the unfused original
`/home/user/master/AMVI_Full_MTF_Strategy.pine` (`Onnn`). Brief: `$W/SPEC_amvi.md`. The two builds:
`$W/amvi_a.py` / `$W/amvi_b.py` with `amvi_a_notes.md` / `amvi_b_notes.md` (their readings are not repeated
here unless the stage changed something); the reconciliation: `$W/reconcile_amvi.md`.

## Files

| file | what |
|---|---|
| `amvi.py` | the canonical module: build B + path 'mag' (`prepare`, `simulate(P, x, full=False, sub=None)`, `trades`, `summary`, `run`, `sub_bars`, `get_sub`, `fake_sub_bars`, `prepare_injected`) |
| `amvi_a.py`, `amvi_b.py` | the two builds (A with the D1 fix of reconcile_amvi.md; B unchanged); `reconcile_amvi_orig/` = as delivered |
| `reconcile_amvi_cmp.py`, `reconcile_amvi_r0.sh`, `reconcile_amvi_r1.sh`, `reconcile_amvi_r{0,1}_<PAIR>_<TF>.log` | trade-by-trade comparison A / B / canonical |
| `reconcile_amvi_trace.py`, `.log` | hand traces (D1, 'mag' vs 'tv', the Inverted bracket) |
| `tests_amvi.py`, `tests_amvi.log` | stage-3 tests T1-T9 |
| `amvi_s3_mut.py`, `amvi_s3_mut.sh`, `amvi_s3_mut.log` | mutants of `amvi.py` against the tests |
| `run_inv_amvi.py`, `out/inv_amvi_<PAIR>_<TF>.json`, `out/run_inv_amvi_<PAIR>_<TF>.log` | the 14 cells |
| `inv_tables_amvi.py`, `inv_tables_amvi.md`, `inv_tables_amvi_ltf.md` | the by-timeframe table (and with the `ltfRule` 'last' rows) |

## 1. What the script is

AMVI ("Adaptive Market Volatility Indicator") is a volatility number in [0, 100] computed on up to twelve
timeframes. A TRIGGER is a chart bar on which one enabled timeframe's AMVI crosses above High Vol (70) while at
least `minConfluence` (3) timeframes are above it. The trigger has no direction: in the fused file the direction is
the FlashGold Direction Filter's zone (BUY ZONE long, SELL ZONE short, NO TRADE nothing; L776-778). A market order
fills at the next open with 10 % of the equity; a `strategy.exit` bracket (stop 1.5 x ATR(14), target 3 x ATR,
optional ATR trailing stop) is sent with it at absolute prices from the signal bar's close and re-sent on every
later bar from the real entry price; `strategy.close_all` when the average AMVI crosses below Low Vol (30) and,
optionally, after `maxBars`; a trigger in the other zone reverses.

## 2. The `strategy()` call (L2-4) and the broker

`initial_capital=10000`, `default_qty_type=percent_of_equity`, `default_qty_value=10`, `commission_type=percent`,
`commission_value=0.04`, `slippage=1`, `pyramiding=0`; not set: `process_orders_on_close` (false: market orders
fill at the next open), `calc_on_every_tick` / `calc_on_order_fills` (false: one run per bar at its close),
margins (100 %: a 10 % position never binds), `close_entries_rule` (FIFO, one trade at a time),
`use_bar_magnifier` (false = path 'tv'; path 'mag' = Bar Magnifier on). Cost 'tv' = those Properties: 0.04 % of
the slipped fill value per fill, 1 tick against the order on market and stop fills, none on the target (a limit).
Cost 'ours' / 'stress' replace commission AND slippage (SPEC_amvi section 9). Sizing: `qty = 0.10 x
strategy.equity / close` at the placing bar (A6), equity = cash (every cost paid, the open trade's entry cost
included) + open P/L (A14); not rounded (A13).

## 3. "Trade direction: Inverted" = the replica's `inv` (how the Pine implements it)

The input is `amviTradeDir = input.string("Follow the filter", "Trade direction", options=["Follow the filter",
"Inverted"])` (L108). It was added by commit `9a8d5b4`, before Update 1; Update 1 (`26c8b00`) changed one code
line, the `strategy()` title (`git diff 6c59b9f HEAD`). The Pine implements it in three lines and nothing else:

```
bool amviInv  = amviTradeDir == "Inverted"                                          // L779
bool longSig  = trigger and (amviInv ? amviDirDn : amviDirUp) and inRange           // L780
bool shortSig = trigger and (amviInv ? amviDirUp : amviDirDn) and inRange           // L781
bool goLong   = longSig and strategy.position_size <= 0                             // L782
bool goShort  = shortSig and strategy.position_size >= 0                            // L783
```

- The swap is AFTER the filter: the trigger and the zones (`amviDirUp = fgfOn and fgfBuyOk and not fgfSellOk`)
  never read `amviInv`; the "FGD" Data Window counters stay in the normal frame (L786-795).
- The position test reads the REAL position against the swapped signal = INVERT_SPEC's M1 (the normal decision
  on the mirrored position): a BUY-ZONE trigger is taken when the real position is flat or long and sells; a
  trigger of the side already held is ignored; one of the other zone reverses (the header: "A trigger in the other
  zone still reverses the position").
- Orders are MARKET orders with the real side's id and comment (`strategy.entry("Long" / "Short")`, "AMVI L / S
  nTF"); M2's stop <-> limit entry swap has nothing to convert.
- **The bracket is not mirrored by a `2R - S` expression.** The two `strategy.exit` blocks (L811-826) are written
  per REAL side and recompute that side's levels from a reference price `ep` and the same ATR distances
  (`longSL = ep - entryAtr * slMult`, `shortSL = ep + entryAtr * slMult`, targets likewise); `ep` = the signal
  close while that side is not held (the signal bar), `strategy.position_avg_price` on every later bar. Result:
  - on the fill bar the inverted levels ARE INVERT_SPEC's M3 mirror about R = the signal close (`c + a*k = 2c - (c
    - a*k)`; trace 3 of `reconcile_amvi_trace.log`: both midpoints 1160.599 = the signal close);
  - from the next bar on each run re-anchors on ITS OWN fill. With no slippage (costs 'ours', 'stress') that is
    again the exact mirror (T6 P1: the inverted trade list is the normal one with `dir` negated and 'sl' <->
    'tp', when `slMult == tpMult`); with cost 'tv' the fills are `o + 0.01` and `o - 0.01`, so the two brackets are
    mirror images about the RAW open, 2 ticks away from a literal `2R - S` about either fill (trace 3: 1154.4003
    against 1154.4203);
  - stop distance stays the stop distance, target distance the target distance; the trailing stop keeps its
    ticks (`math.max(1, math.round(entryAtr * mult / mintick))`, side-agnostic) and arms from the real entry
    price; the volatility collapse and the time stop are side-less `close_all` calls (M4).
- M5: the fused file has no Long only / Short only input; the filter's Allow buys / Allow sells choose the ZONE
  (normal frame): with Inverted, "Allow buys" alone trades shorts only (T6 P5).
- There is no older reverse or direction option in the fused file. The original's `tradeDir` (a restriction of
  the real side) and `allowReverse` were removed by the fusion. So "with the filter off, inverted == the script's
  older reverse option" has nothing to compare: with `fgfOn` off the fused file trades nothing in either
  direction (header: "with it off ... nothing trades"; T6 P4).
- Replica: `inv` (alias of `amviTradeDir`; both given and disagreeing -> `ValueError`) is a `simulate` input;
  `P` is the same for both directions. With `dirSource` 'orig' `inv` is a replica-only control (the original has
  no such input): the same swap after its EMA / candle / Donchian bias.

## 4. The direction filter (fgf.py)

The strategy reads three things of the filter block: the input `fgfOn` and the gates `fgfBuyOk`, `fgfSellOk`.
`fgf.fgf_permissions` returns both (`buyOk`, `sellOk`): no filter series is missing and nothing of the filter is
reimplemented. From `fgf.py` the module uses `fgf_permissions`, `_bars` (bar files, shared cache), `_atr`
(`ta.atr`), `tf_seconds`, `DEFAULTS`, `_DISPLAY_KEYS`, `_params` (validation). Every filter input of the fused
file equals `fgf.DEFAULTS` (`fgfOn` true). With `fgfOn` false `fgf` is not called and no order is placed.
"Filter off" in the runner and the calibration = `dirSource` 'orig' = the unfused original (O143-163), which is
byte-identical to the fused file outside the direction lines.

## 5. The timeframes requested, and the seconds timeframes

26 `request.security` calls:
- AMVI, 12 calls `get_mtf` (L733-741): **"1S", "5S", "15S", "30S", "45S", "1", "5", "15", "30", "60", "240",
  "D"**, each `request.security(tf, calc_amvi()[noRepaint ? 1 : 0], gaps_off, lookahead = noRepaint ? on : off)`;
  a disabled one requests `timeframe.period` and its value is discarded (`on ? v : na`).
- The filter (inside `fgf.py`): the outer request on `fgfTfEff` ("60"), inside it the parent `fgfParentTf`
  ("60") and two requests per child zone (`fgfZTf1..6` = "60", "120", "240", "480", "1", "2"; zones 4-6 off by
  default, requested, unused).

Reading (A2, the one untestable reading that moves trades): every requested timeframe gives the value of its last
bar closed by the chart bar's OPEN (`[1]` with lookahead on: for a higher timeframe the bar before the one that
contains the chart bar, for the chart's own timeframe the previous bar, for a lower timeframe `[1]` of the first
intrabar = the last intrabar of the previous chart bar). `ltfRule` 'last' (replica control) reads the lower
timeframes as a live bar would (`[1]` of the LAST intrabar): `runs_ltf_last` of the runner shows its weight
(section 10).

**Seconds timeframes (1s, 5s, 15s, 30s, 45s) cannot be reproduced**: no data below 1 minute. Their toggles
`en1s`, `en5s`, `en15s`, `en30s`, `en45s` (L89-93) are TRUE by default. The replica gives them na on every bar,
which is exactly the Pine with those five inputs switched OFF (`on ? v : na`; na never crosses, is not hot, is
not counted in `enCount` and adds 0.0 to the sum). So the replica reproduces the TradingView run with
`en1s = en5s = en15s = en30s = en45s = false`, and those five inputs are how to switch them off there. The
inputs are accepted, kept at the Pine defaults, ignored, and `summary['seconds_ignored']` says how many were left
on (5 by default). T6 P7: switching them off changes nothing. On TradingView with the defaults the script either
stops with an error (plan without seconds data; the tooltip says so) or reads seconds bars for a short recent
stretch only: not comparable.

## 6. Readings of TradingView (SPEC_amvi A1-A18, as implemented)

All of SPEC_amvi section 10, unchanged by the reconciliation: one run per bar at its close (A1); the request rule
(A2, control `ltfRule`); seconds = na (A3); na rules of `ta.highest` / `ta.lowest` / `ta.sma` / `ta.stdev`
(population), `ta.ema` seeded with the first value (A4); the operation order of AMVI (A5); market fills at the
next open, quantity from the placing close's equity (A6); the bracket live from the fill with the signal-close
levels, a re-sent exit acting from the next open, never backwards (A7); the trailing stop of SWEEP_AH_SPEC
(activation at entry + `trail_points` ticks, stop = best - `trail_offset` ticks, the target tested before arming
on a rising leg, the nearer stop in force) (A8); rule-4 path, tie low first, a level passed at an open fills at
that open, an opposite entry reverses (A9); at an open the entry / reversal first, then the close_all, then the
gap test (A10); a close_all placed in the same run as a reversal is dropped (`revClose` 'void', A11; 'closes' =
the hrd reading); two close_all in one run = one close named 'vol' (A12); no rounding (A13); equity, average
price and entry bar index (A14); `math.round` = floor(x + 0.5) (A15); window start / end (A16); UTC dates (A17);
an exit with no level places nothing (A18, never reached).

Per-trade ATR (brief C3): the Pine re-sends the open trade's exit every bar with the CURRENT `entryAtr`, which
changes while a trade is open only in a run that places a reversal; that trade is closed at the next open before
any price is tested. The kernel keeps each trade's own ATR; the T4 reference keeps the `var` and re-sends both
exits every bar as the Pine does: equal trades (only the RECORDED `sl_px` / `tp_px` of a trade reversed at the
bar after its fill would show the new ATR's levels in TradingView's plot; those levels never act).

## 7. Where the canonical module follows the Pine and not the brief

Nothing in the trading logic. Two statements of the brief were too broad: P8 (`noRepaint` off = on one bar
earlier) holds only between contiguous chart bars (a timeframe's bar can close inside a chart gap); and
`rev_close_same_run` is 0 with the default inputs but not with a time stop alone. One summary detail followed the
brief and hrd in B but not in A (reconcile D1: the mid-window equity when the mid bar is the last bar).

## 8. Path 'mag' (built in this stage)

SWEEP_AH_SPEC.md section 2, SPEC_amvi 6.3: the open trade's bracket (stop loss, target, trailing stop: the only
price orders of this script; there is no stop / limit entry) walks the 1-minute sub-bars of the chart bar in time
order (`sub_bars`: rows of `data/<PAIR>_1.parquet` with `t_open` in `[t_open, t_close)` of the chart bar; built
once per window and checked to rebuild every chart bar's OHLC); each sub-bar gets the open test (a level passed
between two sub-bars fills at the next sub-bar's open) and its own rule-4 path; the trailing state carries over;
the levels are those of the chart bar (the fill bar's `SL0` / `TP0` on all its sub-bars, the re-anchored ones from
the next chart bar). Market entries and reversals, the close_all orders and the bar-close run stay on the chart
bars. `R['xsub']` = the sub-bar of a bracket exit; trade times stay chart-bar times (SPEC 12). Chart "1": mag == tv
(T2, and the runner's check on both pairs). With path 'tv' the canonical module equals `amvi_b.py` bit for bit.

Effect on the default runs (script costs): at most 0.27 % of the account (BTC 30, inverted), 0.00-0.06 % in every
other run. The bracket is 1.5 / 3 ATR(14) wide, so a chart bar rarely holds both levels; the difference comes from
those bars (TradingView's rule-4 guess against the real minute order) and from gaps between 1-minute bars (a
target or stop filled at the next minute's open: trace 2, a BTC 60 short whose target 90,374.13 fills at
90,363.00 on 'mag'). The cost mode weighs far more (section 10).

## 9. Not reproduced / limits

- TradingView itself: nothing can be compiled or backtested here; A2, A6-A11, A14 are readings of its engine.
- Seconds timeframes (section 5). TradingView's limited depth of lower-timeframe intrabars on a long chart (the
  replica has every 1-minute bar; a request below the chart's timeframe returns na on older bars there, and that
  timeframe silently stops counting): a setting with only timeframes at or above the chart's does not depend on
  it.
- Live bars: a lower-timeframe request returns the latest intrabar live: live = `ltfRule` 'last', history =
  'first', although "Non-Repainting" is on.
- Lot step and price rounding (10 % of 10,000 is 0.78 oz of gold: TradingView with a 1-unit minimum would trade
  nothing on such a symbol); no margin call logic.
- Another broker's bars: gold here = 18:00-17:00 New York sessions (240-minute bars anchored at 18:00, daily bar =
  session), BTC = a UTC grid (Bitstamp).
- `fgf.py`'s own residuals (reconcile_fgf.md).
- `/home/user/master/AMVI_by_timeframe/AMVI_FGF_XAUUSD_15m.pine` (XAUUSD 15m, Trade direction Inverted) has the
  same code as the master and other defaults (periods 7 / 100 / 20, High Vol 60, confluence 1, only 15m / 1h / 4h,
  seconds off, stop 1 ATR, no target, no collapse exit, Signal close, band 0.5, burst gate off, any combo, 0
  aligned zones): the replica runs it by passing those inputs (reconcile case `ext/by_tf_xau15_inputs`). Its
  README is an earlier calibration on other data (VANTAGE gold 2025-2026, Bitfinex 2018-2019) with another
  replica: it shows which inputs mattered, its numbers are not comparable and none is used.

## 10. Results by timeframe (default inputs, full windows; `inv_tables_amvi.md`)

See `inv_tables_amvi.md` (TradingView view = path 'tv', the script's costs; 1-minute fills = path 'mag', our
costs). In short:
- Trades: BTC 1,124 (chart 1) to 125 (chart 240), XAU 327 to 49, filter on; 34 to 562 trades a year. Exposure 1 %
  (1-minute charts) to 13 %. Every account moves by a few percent at most (10 % positions).
- With the script's costs nearly every run loses (BTC 1: -7.5 % / -9.0 %; XAU 1: -2.5 % / -2.3 %, normal /
  inverted, filter on). The cost mode is the main effect: our costs add +0.3 % (XAU 240) to +5.0 % (BTC 1).
- Filter on, Inverted against Normal: no consistent sign. The filter-on rows that gain in the TradingView view are
  all BTC: 30 inverted +1.36 %, 60 inverted +2.46 %, 120 normal +2.51 %, 240 normal +0.73 % / inverted +0.52 %;
  the other direction of BTC 30 / 60 / 120 loses (-6.1 %, -5.9 %, -2.9 %); every XAU row and BTC 1 / 5 / 15
  lose. The fair halves (h1r / h2r, 1-minute fills, ours) of the gaining rows do not always share a sign (BTC 30
  inverted +4.59 / -1.18; BTC 60 inverted +1.81 / +1.80 does).
- `ltfRule` 'last' (A2) moves 0 (chart 1) to a third (XAU 240: 59 -> 40) of the triggers and changes signs
  (BTC 60 inverted, TradingView view: +2.46 % -> -1.14 %; BTC 120 normal +2.51 % -> -1.70 %): every lower-
  timeframe reading is a real uncertainty of these numbers on charts above 1 minute.

## 11. Verification

- Reconciliation (reconcile_amvi.md): A and B written independently agree on every trade and summary field in
  952 cases (14 cells, 112 grid settings, the brief's extra and edge inputs), 513,859 trades; the canonical module
  equals B bit for bit on 'tv'.
- `python3 -I tests_amvi.py` (log `tests_amvi.log`): **37 PASS, 0 FAIL in 226 s**: T1 A == B == canonical on the 10 reconcile
  cells; T2 'mag' == 'tv' on chart "1"; T3 'mag' with one fake sub-bar per bar == 'tv'; T4 both paths against a
  slow pure-Python reference written from the Pine (re-sending the exits with the `var` entryAtr every bar, real
  prices for both sides) on 30 random 2-month settings and 24 default full-window runs; T5 costs, slipped prices,
  P/L, eq_before, net, fair halves, R and counters recomputed from the trade lists, every cost mode and both
  paths; T6 the inv properties P1-P10 and the header statements; T7 `revClose`; T8 timing; T9 the sub-bars.
- Mutants (`amvi_s3_mut.log`, `amvi_s3_mut.sh`): 15 copies of `amvi.py` with one line changed, each run against
  T2-T7: the 'mag' walk on the chart bar, the trailing state reset between sub-bars, no stop after a sub-bar exit,
  a slipped limit fill, the Inverted position test on the mirrored position, the re-anchor from the close, the
  fill-bar levels from the entry price, a close_all on a flat account, sizing on cash, the time stop one bar late,
  the path tie high first, the XAU stress cost, the trail armed strictly above its level: all 13 KILLED. Two
  survive and have no observable effect: arming the trail before testing the target on a rising leg (when the
  target is reached the trade closes; an equivalent mutant) and naming an exact tie of the trailing stop and the
  stop loss 'sl' instead of 'trail' (same price; such a float tie never occurs in the tested runs).
- Timing (T8, shared loaded machine): `prepare` BTC "1" 5.5 s cold in a fresh process (peak RSS 1.83 GB; 1.2 s in the full test run, the AMVI parts already cached), a further trigger setting
  0.07 s; `simulate` BTC "1" 0.010 s on 'tv' and on 'mag', BTC "5" 'mag' (1,039,434 sub-bars) 0.027 s. The runner:
  2.4 s (XAU 60) to 11.4 s (BTC 1) per cell for 26 runs, peak RSS 0.67-1.83 GB.
