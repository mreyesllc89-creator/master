# gvl: GVLiveV2 Polymarket Pre-Candle + FGF [Update 1], canonical replica: interpretations and limits (stage 3)

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine` at HEAD (Update 1; `Lnnn` = its
lines). Brief: `$W/SPEC_gvl.md`. There is no TradingView here: nothing below was compared with a TradingView
report. Run everything with `python3 -I`.

| file | content |
|---|---|
| `$W/gvl.py` | the canonical module: `prepare`, `simulate` (paths 'tv' and 'mag', costs 'tv' / 'ours' / 'stress', `inv`), `trades`, `summary`, `run`, `sub_bars` / `get_sub` / `fake_sub_bars`, `split_params` |
| `$W/gvl_a.py`, `$W/gvl_b.py` | the two independent builds (B with two marked fixes); as delivered in `$W/reconcile_gvl_orig/` |
| `$W/reconcile_gvl.md` | A against B: what was compared, the two differences, which one follows the Pine |
| `$W/reconcile_gvl_cmp.py`, `reconcile_gvl_run.sh`, `reconcile_gvl_r0/r1/r2_<PAIR>_<TF>.log` | the comparison on real bars |
| `$W/gvl_cases.py` | the fixed cases and the seeded random settings (grid + outside the grid) |
| `$W/gvl_synth.py`, `reconcile_gvl_synth.py`, `reconcile_gvl_synth*.log`, `reconcile_gvl_trace.py / .log` | synthetic bars on a 0.5 grid (the tie fuzz) and the trace of the one A / B difference |
| `$W/gvl_ref.py` | slow pure-Python reference of the orders and exits, both paths, written for the tests |
| `$W/tests_gvl.py`, `tests_gvl.log` | the stage-3 tests: 54 PASS, 0 FAIL |
| `$W/gvl_s3_mut.py`, `gvl_s3_mut.log`, `gvl_s3_mut_run2.log` | 13 one-line mutants of `gvl.py` against the tests: 13 killed |
| `$W/run_inv_gvl.py`, `run_inv_gvl_BTC.log`, `run_inv_gvl_XAU.log`, `out/inv_gvl_<PAIR>_<TF>.json` | the by-timeframe runner and its 14 result files |
| `$W/inv_tables_gvl.py`, `inv_tables_gvl.md`, `inv_tables_gvl_full.md` | the tables |
| `$W/gvl_s3_tvmag.py / .log` | where the 1-minute view departs from the bar-path view; how far 1-minute bars pass the stop |
| `$W/gvl_s4/` | stage 4 (audit): `aud_ref.py` the auditor's own reference from the Pine (series, arms, signals, gates from the raw bars + a broker by order id), `aud_cmp.py` / `aud_cmp_*.log` / `full2/` against `gvl.py`, `aud_json.py` / `aud_json_*.log` the 14 result files recomputed, `aud_g1.py` / `aud_g1_table.md` the sensitivity to G1, `aud_mut.py` / `aud_mut.log` / `mut/` 11 more mutants, `orig_vs_fused.diff` |

## 1. What the script is, in one paragraph

A candle "arms" when its close sits in the upper (PRE-L) or lower (PRE-S) part of its range (`preCloseLocation`
0.65), the radar vol score is at least 35 and rose by at least 1 from the previous chart candle, and (default)
the close is on the right side of the trend EMA(100). In "Market Next Candle" (default) the arm sends a market
order that fills at the next candle's open; in "Stop Next Candle" a stop order one buffer (0.03 x ATR(14))
beyond the candle's high / low, cancelled after 2 more candles if unfilled. An EMA 8 / 21 cross with the trend,
the DEVMA "expansion" regime and the RSI filter also sends a market order. Each entry carries a bracket in
ticks from its FILL: stop 1 x ATR(14), target 5 x the stop (5 R), optional trailing stop; two optional time
stops. Sizing: 1 % of equity over the stop distance, capped at 50 units and at a 1 % margin figure. Gates: flat
account, the 5-minute Polymarket window rule (binds on a 1-minute chart only), an optional New York session
filter (off), and a daily lock after 3 losing trades per New York calendar day. The FlashGold Direction Filter
(OFF by default in this file, L256) allows a PRE-L / long signal only when its buy permission is on, a PRE-S /
short signal only with its sell permission. Update 1 (`gvInv`) sends every entry on the other side.

## 2. The `strategy()` call (L134)

`initial_capital=100000` (`INITIAL_CAPITAL`; net % depends on it because `maxQty = 50` and `qtyStep = 0.001` are
absolute). `default_qty_type=fixed`, `default_qty_value=1`: never used (every entry passes `qty=entry_qty`).
`commission_value=0`, `slippage=0`: cost 'tv' = NO cost, raw fill prices; TradingView's own report is
cost-free. `process_orders_on_close=false`: a market order of the run of bar j fills at the open of j+1, a stop /
limit order of that run is live from j+1. `pyramiding=0`: one entry per side; the script only enters when flat;
a pending order of the other side that fills against a position reverses it. `calc_on_every_tick=true`: live
only. `calc_on_order_fills=true`: section 3. Not set: margin (Pine v6 default 100 %; section 8), Bar Magnifier
(path 'tv'; 'mag' is ours), `backtest_fill_limits_assumption` (0: a limit fills on touch). mintick 0.01,
pointvalue 1 for both pairs.

## 3. `calc_on_order_fills` on history: the ONE assumption (G1)

Pine reference semantics as known (nothing can be tested here): on history a strategy runs once per bar at its
close; `calc_on_every_tick` changes nothing there. `calc_on_order_fills=true` adds one more execution right
after every order fill, on the bar of the fill; that execution already sees the bar's final open / high / low
/ close, and an order it places is processed at the next of the bar's price points instead of the next open.

**Assumption: one decision run per chart bar, at its close; the extra executions change nothing.** An order
decided on bar j exists from j's close: a market order fills at the open of j+1, a price order can fill from
j+1 on, a cancel takes effect at j's close.

- **Same-bar exit: yes.** The bracket is sent with the entry, in ticks from the fill, so it is live from the
  fill: a trade filled at an open, or by a pending order inside a bar, can be stopped or reach its target
  later in that same bar (default inputs, filter off: 25 % of the BTC 60 trades, 19 % on XAU 60, 21 % on BTC 5,
  7 % on the 240-minute charts).
- **Same-bar re-entry: never.** After an exit in bar j the earliest new entry is decided at j's close and fills
  at the open of j+1 ("Market", EMA-cross signal) or along j+1 ("Stop").
- Where the assumption is exact: after an ENTRY fill the script cannot act (`can_enter` and the cancel block
  need a flat position, the bracket already exists).
- Where TradingView most likely differs: after an EXIT fill the script is flat inside the bar and takes the
  close run's decision early; a market entry would then fill at the next path point of the SAME bar (an
  extreme or the close), not at the next open, and the cancel block would act at once. Counted on every run,
  never modelled: trade column `reentry` (where in the deciding bar the exit was), summary `reentry_same_bar`,
  `reentry_extreme`, `reentry_gap_r` (path 'tv': the sum over those market entries of `dir x (entry_px - that
  path point) / stop distance`; positive = TradingView's fill would have been better for the trade),
  `pend_fill_after_exit`. Size at the defaults, filter off, path 'tv' (`out/inv_gvl_*.json`): normal 5 to 26 %
  of the trades (5 % and 8 % on the two 1-minute charts, 16 to 26 % elsewhere) with a gap estimate between -27
  and +10 R; **inverted 7 to 39 % of the trades (30 to 39 % from 15 minutes up) with a gap estimate of +15 to
  +179 R from 5 to 120 minutes** (BTC 5 +179 R over 685 trades, BTC 15 +170 R, XAU 5 +133 R, BTC 30 +122 R,
  XAU 15 +107 R, BTC 60 +62 R, XAU 60 +40 R; BTC 1 -15 R, XAU 240 +8 R): the inverted re-entry after a stop
  sells / buys at the next open where TradingView would have filled it at the candle's far extreme. Read every
  inverted 'tv' number with that column next to it.

## 4. Signals (`prepare`): what was read how

- Series on the whole data file from row 0, then sliced: `ta.atr` = RMA of the true range seeded with the plain
  mean; `ta.ema` seeded with the first close; `ta.rsi` Wilder; `ta.sma` / `ta.stdev` (population) over the
  window; comparisons with na false; `nz(radarVolScore[1], radarVolScore)`.
- `ta.rising(fastDEVMA, 2)` = `x > x[1] and x > x[2]` (`risingRule` 'any'); 'mono' (`x > x[1] and x[1] >
  x[2]`) is there to measure: it removes about 2 % of the EMA-cross signals and no arm.
- **The radar timeframe.** Default "Chart": the six radar functions run on the chart's own bars; no
  `request.security` value is used. Another timeframe is used only when strictly LOWER than the chart (L899);
  then the function is computed on that timeframe's own bars and the chart bar takes the last radar bar with
  `t_close <=` its own `t_close` (lookahead off); `radarVolRise` still differences against the previous CHART
  bar. "Auto" = "5" on a 60-minute chart, "15" on 240, "3" on 30 (built from the 1-minute file), "1" on 15.
- **The "vol score" contains no volume**: it is `ta.atr(10) / ta.atr(30)` rescaled to 0..100 (L848-852).
  Volume is read by one thing that can change a trade: `f_rvol` behind `preUseRvol` (default OFF, outside the
  calibration grid). So at the defaults nothing changes between BTC (Bitstamp traded volume) and gold
  (Dukascopy TICK COUNT per bar). With `preUseRvol` on, `volume / sma(volume, 20)` is scale-free: on gold it
  measures relative tick activity of this feed, not traded volume (TradingView's gold feeds are tick volume
  too, of another broker), so arms would differ in detail; arms BTC 60 474 / 536 -> 407 / 475, XAU 60 260 /
  190 -> 210 / 160.
- `preMinScore` is inert (an arm has all seven conditions, score 100). No default bar has both arms.
- Clocks at the bar's OPEN, New York time with daylight saving. The 5-minute window rule ("Max Seconds After 5M
  Window Start" 90, one order per window): on charts of 5 minutes or more every bar opens on a window start, so
  it never binds; on chart "1" only the bars opening at second 0 and 60 of a window may place an order, one per
  window (BTC 416,072 of 1,039,430 bars).
- Reference counts (bars, arms, signals, gate bars on chart "1") equal the stage-1 probe table in all 14 cells.

## 5. Orders and the broker (`simulate`), path 'tv'

- Two order slots, id "Long" (a real buy) and id "Short" (a real sell); a new order for an id replaces the one
  in its slot (type, price, quantity, bracket). At most one entry order per run, only when flat.
- "Market Next Candle" / EMA-cross signal: market order, filled at the next open, raw price.
- "Stop Next Candle": a price order at `high + ATR(14) x preStopAtrBuffer` (PRE-L, fires when price >= it) or
  `low - ATR(14) x buffer` (PRE-S, price <= it); fill at that price, or at the open when a bar opens at /
  beyond it. Cancel (L1284): at the close of a bar more than `preCancelAfterBars` after the LAST pre-candle
  placement, only when flat, both ids; the timer is shared, so a new pre-candle order renews it for an older
  one; while a position is open nothing is cancelled, so a pending order of the other id can reverse the trade
  (kind 'reverse'). The filter gates the placement only.
- The bracket: `stop = fill - d x slTicks x 0.01`, `target = fill + d x tpTicks x 0.01`, ticks of the bar that
  PLACED the order (`slTicks = slAtrMult x ATR(atrLen) / mintick`, `tpTicks = slTicks x tpR`; Points mode: the
  inputs); never re-sent, never moved; tick distances and levels are not rounded to the tick.
- Trailing stop (`useTrail`): armed when price reaches `fill + d x trActTicks x 0.01` (at the fill when the
  ticks are <= 0), then stop = best price since arming -/+ `trDstTicks x 0.01` (`math.max(..., 1.0)` tick),
  moving only in favour; the nearer of stop loss and trailing stop is the one hit ('trail' on a tie); on a
  favourable leg the target is tested before the trail arms or moves; the stop is fixed along an adverse leg.
- Inside a bar: at the open, `strategy.close` of the previous run, then market orders, then the bracket of a
  trade open before the bar (a level already passed fills at the open), then pending orders already passed
  (older first); then the path O-H-L-C if `(high - open) < (open - low)` else O-L-H-C: the first level reached
  wins, a tie goes to the exit before the order. **An order sitting on the price where a leg ends fills there
  even when an exit has just filled at that price** (a touched limit / stop fills; the one point where the two
  builds differed, `reconcile_gvl.md` D1).
- Time stops (`maxBarsHeld`, `useMaxBarsExit`): `entryBarIndex` is the bar whose close first shows the
  position; the close order goes out at the close of bar entry + N and fills at the next open ('time',
  'maxbars'). Quirk kept: a trade opened in a bar whose previous close already had a position (a reversal)
  inherits the old `entryBarIndex` (`inherit_ebi`).
- Window: flat with clean variables at the first window bar; orders of the last bar do not fill; an open
  trade is closed at the last close ('end').

## 6. The daily limits: day boundary and timezone

- The day is `ny_day_key` (L1176): the **New York calendar date of the bar's OPEN** (`America/New_York`,
  daylight saving included). It changes at 05:00 UTC in winter and 04:00 UTC in summer (BTC 5: the first bar of
  a day opens at 04:00 UTC on 476 days and 05:00 UTC on 254, test T8). BTC 240 (UTC grid): the 04:00 UTC bar in
  summer, the 08:00 UTC bar in winter. Gold (session 18:00-17:00 New York): the day changes in mid-session
  (XAU 240: at the 02:00 New York bar) and Sunday's 18:00 open starts a short day of its own.
- "Max Losing Trades Per Day" (3, ON by default): the reset comes first in the run, so a trade closed inside
  the first bar of a day counts for the new day; only the LAST closed trade is looked at in a run (+1 at most);
  a P/L of exactly 0 is no loss; with costs 'ours' / 'stress' the P/L is after those costs; the lock ends on
  the next day's first bar. It is the dominant gate on low timeframes: in force on 90 % of the BTC 1-minute
  bars, 68 % on BTC 5, 27 % on 15, 7 % on 30, 2 % on 60 (without it BTC 5 takes 9,041 trades instead of 2,693).
- "Max Daily Loss ($)" (0 = off by default): `strategy.equity - dayStartEquity <= -limit`, where
  `dayStartEquity` is the equity at the CLOSE of the day's first bar (history runs at closes), open P/L
  included. While locked, an open position is closed at the next open ('daily_lock'): at the defaults that
  only happens in "Stop" mode (a pending order filling on a locked day).
- The New York session filter (`useSessionFilter`, off): a bar is in a session iff its open, New York HHMM, is
  in `[start, end)`. Unverifiable here: flag any result that uses it.

## 7. Update 1 (`gvInv`, alias `inv`), line by line

Every decision stays in the normal frame: the arms, the EMA-cross signals, `can_enter`, the window rule,
`preOrderThisBar`, `fgfBuyOk` for a PRE-L / long signal and `fgfSellOk` for a PRE-S / short signal, the cancel
rule (L1223-1319 read only flat / not flat). What changes is what an entry branch PLACES (L1041-1046, L1243,
L1246, L1266, L1269, L1292, L1308): the other id, the other side; a market order stays a market order (same
fill); the buy stop above the candle becomes a SELL LIMIT at the same price, the sell stop below it a BUY
LIMIT at the same price (same trigger, same fill, slippage 0); the same `loss` / `profit` / trail ticks,
attached to the order really placed, so a sell has its stop above and its target below its fill. Sizing, the
time stops, the daily lock and the losing-trade count read the real trade. In the replica: slot = real side
`d = -sig`; `dir` / `long` / `short` are real sides, `sig` and `raw_*` / `blocked_*` the signal's side.
The script has no older reverse option and no Long / Short-only input, so there is no "inverted == reversed"
property to test; the header's statements that are tested (T7): same candle, same price, other side for the
first decision from any clean start, incl. the limit order filling at the stop order's bar and price; a
blocked entry stays blocked; with a symmetric bracket and nothing reading the sign of the P/L the inverted
trade list is the exact mirror; "filter on + Allow buys off" removes the PRE-L / long-signal entries, which
inverted are the SELLS. With the default 5 R target `gvInv` is NOT a mirrored trade list: the trades end
elsewhere, the daily loss count differs and later entries differ.

## 8. Sizing, margin, costs

- `f_get_qty` (L1163-1171) with the equity and close of the placing bar: `equity x 1 % / stop distance`, then
  `min(maxQty 50)`, then `min(equity / (close x 1 %))`, floored to 0.001. A pending order keeps its quantity.
- **Gold: every default trade is 50 oz** (the cap; risk sizing asks for 200 to 4,200 oz), i.e. 0.01 to 0.24 %
  of the account at risk, not 1 %: net % is small and barely compounds; read gold in R (`net_r`).
- **BTC: the default position is larger than the account** on every trade up to the 15-minute chart, 97 % of
  the trades on 30, 90 % on 60, 61 % on 120, 19 % on 240 (`margin_over`; largest notional 6.6 accounts on BTC
  60, 28 on BTC 5, 99 on BTC 1, where `maxQty` 50 coins caps 1,626 of 2,814 fills). `strategy()` sets
  no margin, and Pine v6's default (100 %) would refuse those entries; the script's own cap assumes the user
  set Properties -> Margin to 1 %. `tvMargin = 0` (default) does not model TradingView's rule; `tvMargin =
  100` refuses an entry whose notional exceeds the cash (`runs_m100`: BTC 1 no trade at all, BTC 5 5 trades,
  15 14, 30 41, 60 89, 120 143, 240 131; gold unchanged). The refusal rule is the documentation as
  remembered: indicative.
- Costs: 'tv' none; 'ours' XAU $0.15 per unit per fill, BTC $0.10 + 0.02 % of the fill value per fill;
  'stress' XAU $0.26, BTC $0.11 + 0.035 %. Charged at each fill, so they reduce equity and later sizing; fill
  prices never move. With 'ours' the BTC default account is RUINED on charts 1 and 5 (-100 %, `zero_qty > 0`:
  the quantity floors to 0) and loses 55 to 91 % on 15 to 60 (filter off): a notional of 8 to 23 accounts pays
  0.3 to 1 % of the account per round trip.

## 9. Path 'mag' (built in this stage)

- At the chart bar's open: `strategy.close` of the previous run and market orders, as on 'tv'. Then every
  1-minute sub-bar of the chart bar (rows of `data/<PAIR>_1.parquet` with `t_open` in `[t_open, t_close)`), in
  time order: at its open the bracket of the open trade (a level already passed fills at that open; not for a
  trade market-filled at that very open) and pending orders already passed; then its own O-H-L-C / O-L-H-C
  path. The trailing state and the order slots carry over. The script still runs once, at the chart bar's
  close. `entry_time` / `exit_time` stay chart-bar times.
- `get_sub` checks that every chart bar has sub-bars and that they rebuild its open / high / low / close
  (all 14 cells: yes).
- `reentry` codes on 'mag': 1 = the exit was at the chart open, 2 = later in the bar (on 'tv': 1 open or
  first leg, 2 second leg, 3 third leg); `reentry_gap_r` is 0 on 'mag' by definition. So "chart 1: mag == tv"
  holds for every trade column and summary field except that code and the two fields built on it
  (`reentry_extreme`, `reentry_gap_r`); `reentry > 0` is equal.
- Why the 1-minute view differs from the bar path (`gvl_s3_tvmag.log`, default inputs, no cost): in "Market"
  mode ONLY because a stop / target that a jump between two 1-minute bars passes is filled at the 1-minute
  open instead of the level (BTC 5: 228 of 2,693 trades, net R +334.8 -> +304.6; BTC 60: 13 of 741; gold: 0 to
  6 per cell), plus two cases of stop and target in one bar. With a 1 ATR stop and a 5 R target the bar path
  cannot order them wrongly otherwise. In "Stop" mode also the pending entries fill elsewhere (2 to 13 % of
  the trades of a cell differ).

## 10. Limits: what is not reproduced, and what the numbers cannot carry

- TradingView itself: G1 (section 3), the order of events at one price, the margin rule (section 8), rounding of
  prices to the tick and of quantities to the symbol's lot, margin calls, the ~9,000-trade report cap, the bars
  a plan can load (a 1-minute chart cannot hold two years).
- Seconds charts: the 5-minute-window logic was written for them; chart "1" is the finest here.
- **Stops inside a 1-minute bar are booked at the level.** On chart "1" the stop distance (1 x ATR(14) of
  1-minute bars) is about one bar's range: the 1-minute bar that hits a stop passes it by 0.68 R on average on
  BTC (median 0.47 R), 0.52 R on gold; on chart "5" 0.28 R / 0.25 R; on 60 0.11 R / 0.16 R; on 240 0.05 R /
  0.11 R (`gvl_s3_tvmag.log`). There are no ticks to say where in that bar a stop order would really fill.
  Builder A's control (`gvl_a_control.log`: random entries, the same 1 ATR / 5 R bracket, no cost) hits the
  target 20.6 % of the time on BTC "1" where 16.7 % is break-even, 17.1 % on BTC "5", 17.7 % on BTC "60". So
  **on charts 1 and 5 a zero-cost result is positive in BOTH directions whatever the entry** (BTC 1: +742 R
  normal, +736 R inverted), and that is this fill convention plus zero cost, not the signals. With 'ours'
  costs the same runs lose everything. Do not read a 'tv' / script-cost number of charts 1 or 5 as an edge.
- Volume on gold is a tick count (section 4): only `preUseRvol` reads it.
- Bars of another broker: gold bars are 18:00-17:00 New York with 120 / 240-minute bars anchored at 18:00; BTC
  bars on a UTC grid, with holes where Bitstamp had no trades (bars are taken as they are). Another feed
  changes the bars, the first bar of a New York day and what the session filter sees.
- The unfused original (`GVLiveV2_Polymarket_PreCandle_Strategy.pine`): its entry logic is this file's with
  both gates true; its exits (absolute prices, 2 ATR, a trailing stop) and sizing are other code and are not
  replicated. "`fgfOn` False reproduces the original" therefore means here: the same arms and signals, both
  gates true on every bar (test T7 P4), not the original's trades.
- Live-only: per-tick runs (`calc_on_every_tick`), mid-bar re-entries, the one-bar-early time stop, alerts /
  JSON / webhook, the paper stake, spreads, tables, plots (the file is at the 64-plot limit and has no funnel
  plots: `raw_*` / `blocked_*` are the replica's definition), training capture.
- A pending price that is na (ATR(14) na in the first 13 rows of a file): outside every window.

## 11. Verification

- Reconcile (`reconcile_gvl.md`): A == B == canonical on 1,440 cases of real bars (2,007,627 trades; BTC and
  XAU, charts 1, 5, 15, 60, 240) after one fix in B; as delivered the two already agreed on every real-bar
  trade and differed only on synthetic ties.
- Tests (`tests_gvl.log`, 54 PASS / 0 FAIL, 238 s, peak memory 2.4 GB): T1 A == B == canonical (360 cases, 442,812 trades, 120 random
  settings); T2 the canonical module reproduces both builders' saved stage-2 trade lists; T3 'mag' on chart 1
  == 'tv' (64 settings, 327,599 trades); T4 'mag' with one fake sub-bar per bar == 'tv' (156 settings) and the
  control that real sub-bars differ; T5 'tv' and 'mag' == the pure-Python reference on 30 random settings over
  2-month windows of real bars, 8 months on the 240-minute chart (mag differs from tv in 16 of them), on 48 default runs over longer windows,
  and on 480 synthetic cases (with the seven seeds on which the builds had differed); T6 every summary field, the fair halves, P/L, costs and `eq_before` from the
  trade list and the equity curve (360 runs, both paths, three cost modes) and the cost of one trade spelled
  out; T7 Update 1 (P1 mirror 64 cases / 193,336 trades on both paths, P2 / P3 160 clean starts, P4, the Allow
  buys / Allow sells statement, sides, the alias); T8 the daily lock against a recount of losing trades per
  New York day (tv and mag), the day boundary, the life of pending orders (71,343 fills, 194 later than the
  timer and each a reversal or a fill right after an exit), the window rule on chart 1, the 'mag' codes and
  fill prices; T9 timing.
- Mutants (`gvl_s3_mut.log`): 13 one-line changes of `gvl.py`, each in its own sandbox copy (no gap test on
  later sub-bars, first sub-bar only, tie to the order, the leg-end drop, the inverted trigger flipped, loss
  counted before the day reset, cancel one bar early, trail before target, no entry cost, the 'mag' open code,
  the bracket on the signal's side, the window rule off, no ATR buffer) against T4-T8: **13 of 13 killed**, by 1
  to 6 failing tests each. The leg-end drop was first caught only by the pinned trace; the synthetic fuzz of
  T5 now includes the seeds where it matters and catches it too (`gvl_s3_mut_run2.log`).
- Timing (shared machine, load 4 to 10; the range is over the test runs): BTC "1" (1,039,430 bars): first
  `prepare` 2.5-4.7 s (filter off; about 9 s with the filter), another threshold setting 0.04-0.07 s; one
  `simulate` 0.017-0.05 s at the defaults, 0.05-0.14 s with the lock off (29,538 trades), the same on 'mag'.
  BTC 60: 'tv' 1.5-2.5 ms, 'mag' 69-123 ms (it walks the 1-minute bars of every candle with a position: 43 %
  of 1.04 M); BTC 5 'mag' 21-49 ms; XAU 240 'mag' 36-49 ms. Peak memory of the BTC "1" runner cell 1.9 GB.

## 12. For the auditor (stage 4): the readings every implementation shares

A, B and `gvl_ref.py` were all written from `SPEC_gvl.md`; they cannot expose a misreading of it. The places
worth attacking, with the Pine lines: G1 (section 3; it moves the inverted 'tv' numbers by tens of R); the
window rule on chart "1" (L972-979: `lastSignalPolyWindowStartMs` is set when an order is PLACED, also when
it never fills); the shared cancel timer and "no cancel while a position is open" (L1284); `entryBarIndex`
(L1322-1328) under reversals; `strategy.closedtrades.profit` = net of our costs in the loss count (L1193); no
tick rounding of `loss` / `profit` / `trail_points` (L1212-1215); the trailing rule; `ta.rising` (L880);
`request.security` of a lower timeframe for the radar (L901-906; default unused); the margin question
(section 8); the stop fills inside 1-minute bars (section 10).

## 13. Stage 4 audit (sceptic): what was checked, what was found

`gvl.py` is unchanged by the audit (sha256 47791e15...866341, as tested and as run for the 14 cells): no line of
it was found to depart from the Pine. One weakness of the tests was fixed (T1, below) and these notes extended.

**Pine against module, line by line** (L134, L840-990, L1160-1354 against `prepare` / `_kernel` / `_walk_bar` /
`_fill`): na handling (`nz` of the tick distances, of `radarVolScore[1]`, RSI na compares false, `na(lastPreStop
OrderBar)`, `barsInTrade`), `[1]` offsets (crossover / crossunder, `ta.rising`, vol rise against the previous
CHART bar), every `var` (day key, day start equity, loss count, `lastClosedTrades`, lock, window key, pre-stop
bar, `entryBarIndex`) and `strategy.position_size[1]`, the order of the five order blocks with `preOrderThisBar`
and the cancel block between arms and signals, ids / sides / stop-limit swap of Update 1, ticks and quantity of
the PLACING bar, `f_get_qty` term by term, the four `strategy.close` blocks. The filter block's 45 trading
inputs have the defaults of `fgf.DEFAULTS` except `fgfOn` (handled). The diff of the unfused original against
this file outside the filter block (`gvl_s4/orig_vs_fused.diff`) is what SPEC_gvl section 1 says: same entry
logic, other exits and sizing.

**An own reference, from the Pine alone** (`gvl_s4/aud_ref.py`; not derived from `SPEC_gvl`'s formulas or from
`gvl_ref.py`): ATR / EMA / RSI / SMA / stdev with pandas and numpy windows on the raw bar files, New York time
from the US daylight-saving rule written out (no time-zone library), a broker that holds `strategy.entry` /
`exit` / `cancel` / `close` by id, a trailing stop kept as "extreme since the fill" instead of an armed flag,
the script body call by call. Radar "Chart" only, session filter off, ATR mode.
- Arms, EMA-cross signals, the gate, the 5-minute window key, the New York day changes and ATR(14) / ATR(21):
  equal to `prepare()` on every window bar of the 10 compared cells, 3 signal settings each.
- Trades (bars, sides, order type, prices, quantity, P/L, `eq_before`, exit kind), the bar-close equity curve
  and the lock flag: equal on every run. First round 10 cells (BTC and XAU: 1 (90 / 120 days), 5, 15, 60,
  240), 14 order settings x 2 paths x up to 4 signal / filter settings, 710,576 trades; second round 6 cells
  with 18 order settings (costs with the loss count, `tvMargin`, filter on with the trend off), 210 checks per
  cell, 642,477 trades: 0 FAIL (`gvl_s4/aud_cmp_*.log`, `gvl_s4/full2/`).
- The 14 result files: all 672 summaries (`runs`, `runs_stop`, `runs_m100` x 16) recomputed with this reference:
  trades, long / short, sl / tp, same-bar exits, net %, PF, win %, max DD % identical, net R to 1e-12
  (`gvl_s4/aud_json_*.log`).

**Mutants** (`gvl_s4/aud_mut.py`, 11 new one-line changes, each in a sandbox copy): lock after 4 losers, own
`entryBarIndex` after a reversal, time stop one bar early, path tie high first, UTC day for the lock, long
signal without the trend, no trail arming at an open, loss count before the entry cost, halves by exit bar,
no `maxQty`, a filter-blocked arm setting `preOrderThisBar`. Tests T5-T8 kill 10. The 11th (a change inside
`prepare`) passes T5-T8, which take `prepare()`'s arrays as given; T2 kills it, and so does T1 once fixed:
**T1 as written could not fail for a mutated `gvl.py` in a sandbox copy** (`gvl_b` puts the work dir at the
head of `sys.path` on its first `prepare()`, so the `gvl` imported after it was the unmutated one). T1 now
imports `gvl` first (`--mods gvl,gvl_a,gvl_b`: the same comparison); on the mutant it fails in all 10 cells;
in the work dir the suite is again 54 PASS / 0 FAIL (256 s). The auditor's reference kills 10 of the 11 (the
halves are a summary field it does not compute; T6 kills that one).

**Sanity of the by-timeframe numbers.** Trades per year fall with the chart (BTC 1,408 / 1,347 / 1,054 / 638 /
371 / 180 / 78 from 1 to 240 minutes; gold 1,130 to 58); on charts 1 and 5 the count is set by the lock
(about 3.9 trades per New York day). Win rates 15 to 23 % against 16.7 % break-even for 1 : 5. 'tv' against
'mag', default inputs: BTC 5, 228 of 2,693 trades differ and every one of them only by an exit booked at a
1-minute open that jumped past the level (218 stops worse, 10 targets better: -30.3 R); XAU 15, two wide
candles (ranges of 9.9 and 10.1) hold stop and target and the 1-minute order is target first (+11.8 R with 4
fills at 1-minute opens), then 3 more trades follow. No other cause appears.

**G1, measured** (`gvl_s4/aud_g1.py`, `gvl_s4/aud_g1_table.md`: all 14 cells, both modes, both directions). The
auditor's reference can run the script again right after every fill, on the fill bar, with the bar's final
OHLC, the `var`s rolled back, a market order of that run filled at the next price point of the bar. Two
readings of what such a run may do:
- `barstate.isconfirmed` is false in it (it is not the bar's closing update; the reference text reads that
  way, nothing here can test it): no ARM can fire, only an EMA-cross signal, the cancel block, a close. Then
  G1 is exact for three quarters of the entries; default net R moves by -28 to +14 R (normal) and -11 to +34 R
  (inverted) in "Market" mode, -16 to +46 R in "Stop" mode; two results change sign (XAU 60 "Stop" normal
  -2.2 -> +1.8 R, XAU 30 "Stop" inverted -15.7 -> +30.3 R).
- it is true there: the arms fire inside the bar, 6 to 26 % (normal) and 7 to 42 % (inverted) of the "Market"
  trades are placed by such a run, and net R moves by -28 to +86 R (normal) and -11 to +158 R (inverted; BTC 15
  +165 -> +323, XAU 5 +31 -> +186, BTC 60 +23 -> +77). The replica's `reentry_gap_r` is a first-order estimate
  of this case and has the right size (BTC 60 inverted: +62 estimated, +54 simulated). With a time stop
  instead of the target ('time4') the effect is larger still (BTC 5 normal +452 -> +789 R, BTC 60 normal +13
  -> +98 R): on BTC 60 the 154 entries placed by such a run earn +0.64 R each (the others 0.00), and 96
  time-stop exits come before the 4 bars are over, 42 of them inside the entry bar, because the re-entered
  trade inherits `entryBarIndex`.
Either way these are artefacts of history bars (a fill at a candle's extreme decided with its close); live,
an arm needs the confirmed close and fills at the next open, which is what G1 and 'mag' model. Read a 'tv'
"Market" number, the inverted ones above all, as "TradingView's report may show up to that much more".

**Limits added by the audit**
- Points mode (`ExitMode` "Points", outside the grid) is in ticks of 0.01 here; OANDA gold has a tick of 0.001,
  so the default 16,500 points are $165 on this data and $16.5 there. ATR mode does not depend on the tick.
- The auditor's reference does not cover: a radar timeframe below the chart, the session filter, Points mode,
  the relative-volume / body / slope / breakout conditions. For those the evidence is A == B only.
- TradingView's Margin 100 % default: a strategy whose order needs more money than the account simply places
  no trade (the usual "no trades until the capital is raised" case). `runs_m100` is therefore the likelier
  picture of this file on a BTC chart with untouched Properties; `runs` needs Properties -> Margin at about
  1 to 10 %.

