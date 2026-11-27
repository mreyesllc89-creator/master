# fgds: FlashGold Direction Strategy [Update 1], canonical replica (stage 3): interpretations and limits

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/FlashGold_Direction_Strategy.pine` at HEAD (813 lines; Update 1 = commit `26c8b00`;
`Lnnn` are its lines). Brief: `$W/SPEC_fgds.md`.

| file | content |
|---|---|
| `fgds.py` | canonical module: `prepare`, `simulate` (paths 'tv' / 'mag', costs 'tv' / 'ours' / 'stress'), `trades`, `summary`, `run`; `sub_bars`, `get_sub`, `fake_sub_bars`, `clear_cache`, `_decide`, `run_arrays` |
| `fgds_a.py`, `fgds_b.py` | the two independent builds, unchanged (`reconcile_fgds_orig/` = as delivered) |
| `reconcile_fgds.md` | A against B, trade by trade (0 differences), and the choice of the canonical module |
| `fgds_ref.py` | slow pure-Python reference of L694-813 and the broker on both paths, written for the tests |
| `fgds_cases.py`, `fgds_synth.py`, `reconcile_fgds_cmp.py`, `reconcile_fgds_synth.py`, `reconcile_fgds_run.sh` | the reconcile machinery |
| `tests_fgds.py` | stage-3 tests T1-T9; log `tests_fgds.log`: 226 PASS, 0 FAIL, 62 s, peak 1.79 GB |
| `run_inv_fgds.py` | the 14-cell runner (INV_BT_SPEC item 3); `out/inv_fgds_<PAIR>_<TF>.json`; logs `run_inv_fgds_<PAIR>.log` |
| `inv_tables_fgds.py` -> `inv_tables_fgds.md` | the by-timeframe tables (three triggers) |

## 1. What the module is

`fgds.py` is implementation B after reconciliation. A and B agreed on every trade of 2,600 compared cases, so
neither was changed. The module adds the 1-minute path 'mag'. Path 'tv' gives exactly what `fgds_b.py` gives:
bit-identical on 96 cases checked with `DataFrame.equals`, and equal to 1e-9 in every reconcile round.

## 2. The filter

- The filter block (L101-681) is byte-identical to `FlashGold_Direction_Filter_v1_2.pine` and to the block
  that `fgf.py` replicates (drawing aside). `fgf.py` is used as it is; nothing of the filter is
  re-implemented.
- The strategy section reads six filter series: `fgfBuyOk`, `fgfSellOk`, `fgfOpen`, `fgfSigOk`, `fgfSigDir`
  and `fgfNewSig`. They are `fgf_permissions`' columns `buyOk`, `sellOk`, `open_`, `sigOk`, `sigDir` and
  `newSig`. **No filter series is missing.**
- `[1]` values (L749-750, L754-755) come from the filter row `w0 - 1`: `fgf_permissions` is called from
  `t_close[w0-1]`.
- With `fgfOn` false the filter is not called. Every trigger begins with `fgfOn and`, so nothing trades
  (header: "nothing trades"). This is checked (P4, and the runner's `filter_off_no_trade`).
- The trigger counts of SPEC_fgds section 4 are reproduced in all 14 cells (runner logs).

## 3. `inv` = the script's own input "Trade direction: Inverted"

This input (`dsDirection`, L699; `dsInv`, L760) existed before Update 1. Update 1 changed no code: commit
`26c8b00` changes the header comments, the `strategy()` title and short title, and the text of the `dsTrigger`
tooltip (read-only `git diff 6c59b9f HEAD`). The replica's `inv` is an alias of `dsDirection == "Inverted"`;
both names are accepted, and both given must agree.

What the Pine does with it, exactly:
- L749-759 (triggers) and L764-765 (`dsBuyKeep` / `dsSellKeep`) never read `dsInv`. The filter and the
  triggers stay in the normal frame.
- **L761-762** swap the RAW trigger pair before the Sides test: `dsGoLong = (dsInv ? dsRawSell : dsRawBuy)
  and dsSides != "Short only"`. A buy trigger opens "DS Short" and a sell trigger opens "DS Long". Sides
  filters the REAL orders.
- **L766-767** swap the keep permission: a real long opened by a sell trigger lives on `dsSellKeep`.
- **L785-786** test the real position against the swapped triggers. This is the normal decision on the
  mirrored position.
- **L806-807** swap the opposite-trigger close.
- **L789-803** send market entries with the real side's id, and one `strategy.exit` with the SAME tick values
  (`loss`, `profit`, `trail_points`, `trail_offset`) whatever the side.
- L738-746 (`dsQty`) and L771-777 (bars in trade) have no side in them.

**The Pine mirrors no price.** There is no reference price and no `2R - S` anywhere. TradingView applies the
side-agnostic tick distances to the fill price of the trade that is really open: a short's stop is above and
its target below. The entries are market orders: the normal and the inverted entry of one trigger fill at the
same next open, with slippage 0. So the result EQUALS INVERT_SPEC's M3 mirror about R = the fill price
(stop' = 2R - S, target' = 2R - T), with the stop distance and the target distance kept. M2's stop <-> limit
entry swap has nothing to act on.

The one literal deviation from a strict mirror is the tie-break `and not dsEnterLong` (L786). It favours the
real long where a strict mirror would favour the normal buy. It is unreachable, because the two triggers of a
pair are never both true; `prepare` asserts this on every call.

The inverted run is not the mirrored trade list in general: stops and targets end elsewhere, and Risk % sizes
on another equity. With a symmetric bracket and nothing that reads the P/L, it IS the exact mirror on both paths
(P1, T6: 48 settings x 4 cells x 2 paths). The 'sl' <-> 'tp' swap is exact even where the rule-4 tie decides,
because the path belongs to the bar, not to the side.

## 4. Assumptions about TradingView (history)

F1-F13 of SPEC_fgds section 10 are implemented as stated there. Both builds read them the same way, and the
Pine agrees with the brief everywhere:
- **F1.** One run per bar at its close; `calc_on_every_tick` and `calc_on_order_fills` are false.
- **F2.** Market orders (entries, reversals, `strategy.close`) fill at the next open, at the raw price
  (`process_orders_on_close` false, slippage 0).
- **F3.** The bracket is in ticks of the PLACING bar (its ATR), measured from the fill, and live from the fill
  on the fill bar.
- **F4.** SPEC_AH rule 4 path: O-H-L-C when (high - open) < (open - low), else O-L-H-C, so a tie goes low first.
  A level passed at the open fills at the open; a target fills on touch.
- **F5.** The TradingView trailing stop: armed at fill +/- `trail_points` ticks (at the fill when 0), then
  best -/+ `trail_offset`. On a rising leg the target is tested before arming; the stop in force on an adverse
  leg is the one at the leg's start. With a stop loss, the tighter of the two is the stop, and a tie counts as
  'trail'.
- **F6.** At an open the script's close or reversal fills before a gapped stop. Only the label differs.
- **F7.** A reversal closes the old trade at the open as 'reverse' and opens exactly `qty`.
- **F8.** No rounding of levels to the tick; quantities are rounded only by `dsQtyStep`, with the Pine's
  formula `floor(q / step + 1e-9) * step`.
- **F9.** TradingView's 1 % margin rule (refused entries, margin calls) is not modelled. It is counted instead:
  `qty_capped_margin`, `margin_over`, `max_notional_x`.
- **F10.** `strategy.equity` = cash (closed P/L, costs paid, the open trade's entry cost included) + open P/L
  at the close.
- **F11.** Flat at the first window bar, but that bar's triggers use the real previous filter bar. Orders of
  the last bar are dropped; an open trade closes at the last close as 'end'.
- **F12.** No loss, no profit and no trail means no bracket.
- **F13.** `bool[1]` on the first bar of the data is false (never reached in these windows).

**Path 'mag' (Bar Magnifier)**, added in this stage:
- **MG1.** The market orders fill at the chart bar's open. That open is the first 1-minute sub-bar's open:
  `sub_bars` checks, on every cell, that the chart bar's OHLC equals its sub-bars' first open, highest high,
  lowest low and last close (T8, runner).
- **MG2.** The bracket walks the sub-bars in time order. Each sub-bar gets its own gap test at its open, then
  its own rule-4 path. A level crossed by a jump between two sub-bars fills at the later sub-bar's open.
- **MG3.** The trailing state (armed, best) carries over sub-bars and chart bars.
- **MG4.** The script runs at the chart bar's close, so equity, `dsQty`, ATR ticks and decisions are unchanged.
- **MG5.** `exit_bar` / `exit_time` are those of the chart bar (no sub-bar time is recorded).
- **MG6.** For a trade filled at this open, the first sub-bar's gap test is a no-op (its stop is below and its
  target above the fill), as on 'tv'.
- On chart "1" each chart bar is its own single sub-bar, so 'mag' == 'tv' (T2, runner check on BTC 1 and
  XAU 1).

How much 'mag' changes the default results (Zone start, cost 'tv'):
- 'mag' changes neither entries nor exit bars. A level is touched on the chart bar exactly when one of its
  sub-bars touches it, and P8 makes every trigger trade.
- It changes the exit PRICE of a few trades: a stop or target crossed between two 1-minute bars fills at the
  later bar's open, not at the level. It also swaps sl <-> tp where the 1-minute order differs from rule 4.
- BTC 60: 27 of 3,233 trades differ (3 sl -> tp, 24 other prices; 22 of those worse); net -35.0 % on 'tv' vs
  -31.2 % on 'mag'.
- BTC 5: 558 of 15,568 differ (+101 % vs +61 %).
- XAU 60: 6 of 1,473 differ.
- XAU 15: 10 of 4,257 differ.
- BTC 240: 4 of 1,465 differ.

The difference between the runner's "TradingView view" (tv, no cost) and the "1-minute fills with our costs"
column is therefore almost all COSTS, not the path. Examples:
- BTC 60 normal: tv/script -35.0 %, mag/script -31.2 %, tv/ours -81.7 %, mag/ours -80.6 %;
- XAU 60 normal: +2.0 / +2.0 / -60.0 / -60.0 %.

## 5. Money, sizing, summary

- **Capital and sizing.** Capital is 10,000 (`strategy()`). Sizing follows `dsQty` (L738-746): Risk 0.5 % of
  `strategy.equity` over the stop distance of the placing bar, capped at `dsMaxQty` = 50 and at the script's
  margin cap (equity / (close x 1 %)), then floored to 0.001.
- **Fills and costs.** Every fill pays `qty x (fixed + fraction x price)`:
  - 'tv': (0, 0), the script's Properties;
  - 'ours': XAU (0.15, 0), BTC (0.10, 0.0002);
  - 'stress': XAU (0.26, 0), BTC (0.11, 0.00035).

  Costs reduce the cash and therefore later quantities.
- **Equity curve.** The drawdown curve is 10,000, then the bar-close equity, then the final equity. Half 1 and
  half 2 come from the equity at the middle bar.
- **Fair halves.** `h1r_pct` / `h2r_pct` take the trades ENTERED by / after the middle time and compound
  `pnl / eq_before`.
- **R.** R = the placing bar's stop distance; `net_r` = the sum of `pnl / (sl_dist x qty)`.
- **Recomputation.** T5 rebuilds every summary field, `eq_before`, the costs and the bar-close equity from the
  trade list and the closes alone, for each cost mode, both paths and both directions.
- **`zero_qty`.** It counts decisions where a trigger could not be sized. With cost 'ours' the default account
  is ruined, and stops trading, on BTC 1, BTC 5, BTC 15, XAU 1 and XAU 5. Those rows have `ruined: true` in the
  JSON and "(!)" in the tables.
- **Margin.** `qty_capped_margin` exceeds 1 % of the trades in one runner row only: BTC 1 "New signal", normal,
  cost 'ours', 19 of 1,591 trades, an account that is already ruined. TradingView's own margin call could
  differ there; that row is flagged, not trusted. `margin_over` (notional above 100 x equity) occurs once, in
  BTC 1 "Zone start" normal 'ours', also a ruined account.
- **Notional.** The largest notional / equity over all runs is 101.5x.
- **Cost-free compounding.** On BTC 1 the cost-free account grows +26,274 % (normal) and +63,461 % (inverted).
  `dsMaxQty` = 50 then sets most quantities: 16,071 and 22,781 trades.

## 6. Not reproduced / limits

- Nothing was run in TradingView. F3-F7, F10 and MG1-MG6 are readings of its engine.
- **Margin.** TradingView's margin call and refused entries (F9) are not modelled.
- **Rounding and report limits.**
  - TradingView rounds stop and limit prices to the tick and quantities to the broker's lot step; the replica
    does not. That is at most half a tick per level.
  - TradingView's report stops at about 9,000 trades. The defaults take 29,965 trades on BTC 1, 15,568 on
    BTC 5, 9,756 on BTC 15 and 13,545 on XAU 1.
- **Data.**
  - Bar Magnifier inside TradingView uses its own feed's lower-timeframe data. Path 'mag' uses this data set's
    1-minute bars.
  - There is no data below 1 minute: seconds charts and seconds zones cannot be reproduced (none is in the
    defaults).
  - Gold bars are 18:00-17:00 New York sessions; BTC bars are on a UTC grid. Another feed changes the filter
    candles and so every trigger.
- **Live.** Live trading fills at the first tick with a spread, and a parent timeframe above the filter
  timeframe repaints. History runs once per bar close.
- **`fgf.py`.** Its documented residuals (`reconcile_fgf.md`) are inherited.
- **The header's TEST RESULTS** (other feeds and windows) are not targets.

## 7. Tests (`tests_fgds.py`, log `tests_fgds.log`): 226 PASS, 0 FAIL

| test | content |
|---|---|
| T1 | A == B == canonical ('tv'). Fixed cases and 16 random settings on BTC 60, XAU 60, BTC 240 and XAU 15, full windows, every column, summary field and per-bar array. Plus 480 synthetic-grid cases |
| T2 | 'mag' == 'tv' on chart "1": BTC 1 and XAU 1, 9 settings each, trades and summaries exactly; the sub-bars are the chart bars |
| T3 | 'mag' with one fake sub-bar per chart bar == 'tv': BTC 60, XAU 15, BTC 5, XAU 240, 22 settings each |
| T4 | 'mag' and 'tv' against `fgds_ref.py`. 30 random settings with at least 5 trades, over random 2-month windows of real data with the real 1-minute sub-bars ('mag' differs from 'tv' in 18 of the 30). Plus 240 synthetic cases x 2 paths ('mag' differs from 'tv' in about 150 of them) |
| T5 | Every summary field, the costs, P/L, `eq_before` and the bar-close equity, recomputed from the trade list and the closes. 4 cells x (3 cost modes x 2 directions x 2 paths + random settings) |
| T6 | P1 exact mirror (3 triggers x zone exit x reverse x time stop x ATR / Points, 4 cells, both paths). P2 (5 decisions x 5 states x 2 triggers, through `_decide`). P3, P4, P5, P6 (with `fgfAgainst` independence), P7, P8, P9. Header properties (i)-(iv) on 8 settings x 4 cells x 2 paths |
| T7 | Hand-built sub-bars: which level is met first; a gap between sub-bars through the stop; a short's trailing stop across sub-bars; trailing state across chart bars; inverted; a close request at the chart open |
| T8 | The sub-bars rebuild every chart bar of the 12 cells above "1" |
| T9 | Timing after compilation: one `simulate` on BTC 1 takes 0.08 s ('tv' and 'mag'); BTC 5 'mag' takes 0.04 s; `prepare` BTC 1 takes 1.5-3.1 s |

Two mutants of `fgds.py` in a sandbox (`fgds_s3_mut/`) show that the 'mag' tests can fail:
- one ignores the gaps between sub-bars: T7b and 15 T4 windows fail;
- one sends a tie high first: T7a, T7e and T4 synthetic fail.

## 8. Runner results

`run_inv_fgds.py PAIR TF ...` ran all 14 cells. Each cell has 3 groups x 16 runs: direction x filter x path x
cost. Tables: `inv_tables_fgds.md`.
- **Filter off.** Nothing trades in any cell; these are zero-trade rows by construction.
- **Default "Zone start", TradingView view (no cost).**
  - Inverted beats normal on every cell except BTC 240 (+13.4 % vs +17.4 %).
  - Normal is negative on 10 of 14 cells.
- **With 1-minute fills and our costs**, every default row loses, in both directions:
  - the accounts are ruined below 30 minutes (BTC 1 / 5 / 15, XAU 1 / 5) or lose 92-99.8 % (BTC 30, XAU 15 /
    30);
  - the best rows are XAU 240 inverted (-2.7 %, -3.7 R), BTC 240 normal (-9.2 %) and BTC 240 inverted (-12.0 %).
