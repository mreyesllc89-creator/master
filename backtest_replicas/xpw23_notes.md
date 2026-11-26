# xpw23: XPW Orientation TDI v2.8 (S2 / S3 exits) + FGF [Update 1], final notes of the replica

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.

Ground truth: `/home/user/master/xpw_orientation_tdi_v2.8_strategy_FGF.pine` at HEAD (`d28ba97`, 1893 lines,
Update 1). Line numbers below are that file's. There is no TradingView here: nothing was compiled or
backtested in TradingView. Every statement about TradingView's broker is a reading of its documentation and
is listed in section 4.

| file | what |
|---|---|
| `$W/xpw23.py` | the canonical replica (`prepare`, `simulate`, `trades`, `summary`, `run`; paths 'tv' and 'mag') |
| `$W/SPEC_xpw23.md` | the stage 1 brief (the script line by line, the assumptions T1-T16) |
| `$W/xpw23_a.py`, `$W/xpw23_b.py` | the two independent builds (path 'tv' only) and their notes `xpw23_a_notes.md`, `xpw23_b_notes.md` |
| `$W/reconcile_xpw23.md` | the reconciliation, the Bar Magnifier path, the tests, the results |
| `$W/tests_xpw23.py` -> `$W/tests_xpw23.log` | the tests |
| `$W/run_inv_xpw23.py` -> `$W/out/inv_xpw23_<PAIR>_<TF>.json` | the by-timeframe runner, 14 cells |
| `$W/inv_tables_xpw23.py` -> `$W/inv_tables_xpw23.md` | the tables of those 14 files |

---------------------------------------------------------------------------------------------------------

## 1. What is reused, and the proof

Checked again in stage 3 with `sha256sum` on the line ranges of this file against
`/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine` (the file `xpw.py` replicates):

| part | this file | trailing-TP file | sha256 (both) |
|---|---|---|---|
| signal inputs `rsiLen` .. `cAgS` | 447-508 | 314-375 | `e9bc4ee3...515c3` |
| filter block BEGIN..END FLASHGOLD DIRECTION FILTER | 547-1127 | 402-982 | `5f89deb9...a027d` |
| `// PER-RUNG WINDOWS` .. `nShort := 0` (ladder, rung fetch, READ HERE, labels, label actions, the "both sides cancel" zeroing) | 1143-1626 | 1001-1484 | `4bab5288...4aab7` |

The shared block reads only these names declared outside it: `reverseAll`, `tradeAgree` (same declarations,
only the tooltips differ), and `useLimit`, `tickPx`, `tickBar` through `entryPx`, which goes to `putLbl` only
(label text and position: drawing). So the signal code is the same code and the replica calls
`xpw.xpw_signals` for the signals and `fgf.fgf_permissions` for the filter. Neither is reimplemented.

Everything from line 1628 on (the STRATEGY section) is different code and is written in `xpw23.py`:
the gate, the closes, the S2 exits, the S3 sizing, limit / stop entries with the pending list, the time
stop, Update 1. `engine._run` is not used.

Fusion and Update 1, from `git show 6c59b9f:` (the fused file before Update 1) against the unfused original
`/home/user/master/xpw_orientation_tdi_v2.8_strategy.pine`, code lines only (comments and tooltips removed):
the differences are `max_bars_back=500`, the filter block, the FGF plots, the two gates
`if goLong and fgfBuyOk` / `if goShort and fgfSellOk`, and the FGD plots. Update 1 (6c59b9f -> HEAD) changes
the title, adds the input `xpwInv`, and replaces seven expressions (`xpwPos`, `allowLong` / `allowShort`,
`closeL` / `closeS`, `realLong` / `limPx` / `stopPx` and the comment, the two `room > 0 or ...` tests, the two
id letters) plus one table string. Each of them reduces to the previous expression with `xpwInv` false. With
`fgfOn` false, `fgfBuyOk = fgfSellOk = true` (953-954), so the fused script trades like the original.

---------------------------------------------------------------------------------------------------------

## 2. Interface

    P = prepare(pair, chart_tf, params=None)        signals, filter permissions, window bars
    R = simulate(P, x=None, full=False)             the STRATEGY section + the broker
    trades(P, R, comments=True) -> DataFrame        one row per entry fill, in fill order
    summary(P, R) -> dict
    run(pair, chart_tf, params=None) -> (trades, summary)     one dict, split into the two key sets
    get_sub(P)                                      the 1-minute sub-bars of the window (path 'mag')
    free_caches()                                   drop every memo cache (results never change)

- `prepare` keys: every key of `xpw.DEFAULTS` (`rsiLen`, `fastLen`, `slowLen`, `bbLen`, `bbMult`, `scaleWin`,
  `flatWin`, `areaLen`, `areaFrac`, `trendLen`, `sigRung`, `lblRead`, `actL1` .. `actInf`, `agreeOn`,
  `reverseAll`, `tradeAgree`) and of `fgf.DEFAULTS` (`fgfOn`, default true, and the other filter inputs),
  `start`, `end` (window by `t_close`; default BTC 1731801600..1794873600, XAU 1483315200..1529366400).
  Display inputs and `agreeN`, `agreeMode`, `agreeScope`, `agreeInh` are accepted and ignored. An ORDER / EXIT
  key or an unknown key raises `ValueError`.
- `simulate` keys (Pine names, Pine defaults): `tradeDir` "Both", `oppCloses` true, `entryFill` "Signal tick",
  `limitBars` 5, `maxOpen` 20, `exitUnit` "ATR", `slPtsIn` 10000, `tpPtsIn` 30000, `atrLen` 14, `slAtrMult`
  3.0, `tpRMult` 1.0, `trailOn` true, `trActPts` 15000, `trDistPts` 10000, `trActAtr` 1.0, `trDistAtr` 0.75,
  `timeStop` 0, `qtyMode` "Fixed", `qtyFixed` 0.1, `riskPct` 1.0, `qtyMax` 2.0, `qtyStep` 0.01, `xpwInv` false
  (alias `inv`; both given and different raises), and the replica's `path` ('tv' | 'mag') and `cost`
  ('tv' | 'ours' | 'stress'). Validated as the Pine inputs are (option strings exactly, `maxOpen` 1..100,
  `limitBars` 1..500, `atrLen >= 1`, every number `>= 0`). A `prepare` key (display inputs included) or an
  unknown key raises `ValueError`.
- Nothing in `P` depends on an ORDER / EXIT input. `atrLen` is a `simulate` input: the ATR array is computed
  on the whole chart file from row 0 and cached per length.
- `trades` columns: `id`, `dir` (the REAL side), `sig_dir` (the label's side, `= -dir` when inverted), `src`,
  `sig_bar`, `k`, `entry_bar`, `entry_time`, `entry_px`, `qty`, `exit_bar`, `exit_time`, `exit_px`, `exit_kind`
  (`sl`, `tp`, `trail`, `time`, `close_all`, `reverse`, `end`), `pnl` (after costs), `pnl_gross`, `costs`,
  `eq_before`, `R`, `sl_px`, `tp_px`, `tr_act_px`, `tr_off`, `sl_ticks`, `fill_at_close`, `entry_comment`,
  `exit_comment`. Bars are file row numbers (`bar_index`), times are `t_close` of the bar.
- `summary`: `trades`, `net_pct`, `pf`, `win_pct`, `max_dd_pct`, `max_dd_init_pct`, `long`, `short` (real
  sides), `raw_long`, `raw_short`, `blocked_long`, `blocked_short` (the Pine FGD counts: the label's side),
  `exit_<kind>`, `avg_bars_held`, `exposure`, `half1_pct`, `half2_pct`, `h1_trades`, `h2_trades`, `h1r_pct`,
  `h2r_pct`, `halves_rule`, `final_equity`, `costs`, `net_R`, `h1_R`, `h2_R`, `n_R`, `placed`, `skipped_room`,
  `skipped_qty`, `pend_placed`, `pend_filled`, `pend_filled_at_close`, `pend_cancelled`, `pend_open_end`,
  `close_all_bars`, `max_open`, `zero_length`, `max_expo`, `margin_bars`, `fifo_exits`, and the diagnostics
  `pend_ghosts`, `pend_cancel_stale`, `pend_cancel_against`, `reverse_bars`, `reverse_over_room`,
  `labels_long`, `labels_short`, `both_cancel_bars`, `path`, `cost`.

---------------------------------------------------------------------------------------------------------

## 3. The script, as implemented (Pine line -> kernel)

`strategy()` (444): `pyramiding=100` (never binds; a 101st same-side entry raises), `initial_capital=10000`,
`default_qty_*` unused (every entry passes `qty`), `process_orders_on_close=true`, `calc_on_every_tick=true`
(live only), no commission, no slippage, margin and `close_entries_rule` left at their defaults.

One script run per chart bar, at its close, with the position, the open trades and the equity as they are
after that bar's intrabar fills and before the orders of the run fill:

| Pine | what | kernel (`_kernel`, step 2 / 3) |
|---|---|---|
| 1622-1626 | `nLong`, `nShort`, zeroed when both sides have labels | `xpw.xpw_signals` columns `nLong`, `nShort` |
| 1645 | `xpwPos` = the real position, mirrored when `xpwInv` | `xpos` |
| 1646-1649 | `allowLong` / `allowShort`: "Trade direction" on the orders really placed (swapped when `xpwInv`) | `simulate` |
| 1655-1656 | `goLong` / `goShort` BEFORE the filter (`doneL != bar_index` is always true on history) | `goL`, `goS` |
| 1665-1670 | `oppL` / `oppS`, `closeL` / `closeS`. Market mode: no close on a bar with `goLong` or `goShort`, even when the filter then blocks the entry. Limit mode: `goShort` closes a normal-frame long (blocked or not) | `do_close` |
| 1677-1680 | `strategy.close_all` | kind `close_all`, placed first |
| 1685-1693 | distances in ticks from the chart ATR of this bar, or Points; a stop of 0 in ATR mode also switches the target off | `slT`, `tpT`, `trp`, `tro` |
| 1698-1705 | `entryQty()`: Fixed, or Risk on `strategy.equity`; rounded down to the step, then capped | `qv`, once per bar |
| 1713-1722 | pending list, cancel pass: `stale` or `against` (normal frame, pre-filter flags) | pass (c) |
| 1749-1752 | time stop: `strategy.close` of every trade with `bar_index - entry_bar_index >= timeStop` | kind `time` |
| 1758 | `room = maxOpen - opentrades - size(pendId)`, after the cancel pass, before the filled pass | `room` |
| 1759-1780 | one entry per label while `room > 0 or xpwPos` is on the other side; the filter gate here | `n_place` |
| 1727-1746 | `placeEntry`: nothing placed when the quantity rounds to 0; the order on the real side; limit (normal) / stop (inverted) at the candle low / high; `strategy.exit` with `loss`, `profit`, `trail_points`, `trail_offset` | step 3 |
| 1783-1791 | pending list, filled pass: remove the ids of trades open at script time | pass (f) |
| 1796-1799 | FGD funnel, normal frame | `raw_*`, `blocked_*` |

Consequences kept exactly as the code has them (each has a unit test or a hand trace in the builders' logs):
a filled pending entry is counted twice in `room` on the bar it filled; an entry that filled and closed
before a run saw it open stays in the list as a ghost until `stale` or `against` and holds one unit of
`room`; `closeL` through `oppL` does not cancel pending long entries; on a market reversal bar every label
is placed, "Max open entries" does not hold there.

Update 1 (`xpwInv`): every decision above is taken in the normal frame on `xpos`; the order goes in on the
other side at the same price (market stays market; the buy limit at the low becomes a sell stop at the low,
the sell limit at the high a buy stop at the high); the exit levels are laid out from the real fill on the
real side with the same tick distances; ids carry the letter of the real side; the pending list, `stale`,
`against` and the FGD counts stay in the normal frame; "Trade direction" restricts the orders really placed.

Where the Pine and the brief disagree: nowhere in the trading logic (three readers compared lines 1645-1799
with the brief: both builders and the reconciler). One sentence of the Pine HEADER (127-129, "a fill at the
candle's low on the label candle itself is impossible") does not hold for a candle that closes at its low:
see T6 below. The code decides, not the comment.

---------------------------------------------------------------------------------------------------------

## 4. Interpretations of TradingView (none can be checked here)

T-numbers are those of `SPEC_xpw23.md` section 5.

- **T1** History: one script run per bar, at its close. `calc_on_every_tick` and the `varip` variables
  (`doneL`, `doneS`, `tickPx`, `tickBar`) only matter live.
- **T2** `process_orders_on_close`: the orders of a run fill at that bar's close, in placement order:
  `close_all`, the time-stop closes, then the entries.
- **T3** A trade filled at a close has its exit order live from the next bar on. A trade filled inside a bar
  has it live from the fill point on, along the rest of that bar.
- **T4** Intrabar path of a bar: open -> high -> low -> close when `(high - open) < (open - low)`, else open
  -> low -> high -> close. The first level reached along the path wins; a level already passed at an open
  fills at the open; a level touched exactly is filled (limit and stop alike).
- **T5** Trailing stop: armed when price reaches the fill + `trail_points` ticks (0 = armed at the fill),
  then the stop = best price - `trail_offset` ticks, moving only in the trade's favour; together with `loss`
  the higher stop is the one hit (kind `trail` when the trailing stop is at or above the stop loss).
- **T6** A pending entry placed at a close fills at that same close when the close satisfies it
  (`close == low` for a long label, `close == high` for a short one). This is the documented meaning of
  `process_orders_on_close` for price orders; the Pine header says such a fill is "impossible". Limit mode
  only. Frequency: the close equals the label price on about 10 % of the signal bars of BTC 5 (2 % on BTC 60,
  1 % on XAU 15). Counted in `pend_filled_at_close`, column `fill_at_close`.
- **T7** Inverted, the stop entry fills exactly where the limit would: at the price when the path reaches
  it, at the open when a bar opens through it, at the placement close when the close equals it.
- **T8** A market entry against the real position closes ALL open trades at that close (kind `reverse`) and
  opens its own quantity; further same-side entries of that bar add theirs. TradingView might instead add the
  old position size to each of those orders. Size of the doubt: with the default inputs a reversal bar
  carries two entries on 0 to 8 % of the reversal bars (BTC 60, filter off: 29 of 810 reversal bars, 58 of
  3,886 trades; never more than two labels on a bar).
- **T9** On a bar with `close_all` and time-stop orders every trade is `close_all` (placed first, same
  price). `close_all` does not cancel pending entries.
- **T10** Each exit closes its own entry, although the script leaves `close_entries_rule` at "FIFO". The
  fills and the equity curve are the same under both rules while the time stop is off and the quantities
  are equal (the defaults); the pairing of entries and exits in TradingView's List of Trades differs.
  `fifo_exits` counts the rows FIFO would pair differently (BTC 60 default, filter on: 347 of 1,807).
- **T11** No margin. TradingView's default is 100 % margin; on BTC one default entry (0.1 BTC, 5,800 to 12,600
  USD) is often larger than what the 10,000 account can carry and up to 20 are stacked: `margin_bars` (bars
  with position value above equity) is 3,807 of 17,518 on BTC 60 with the filter on, and the account goes
  below zero in several BTC cells (`max_dd_pct` above 100). A TradingView run with default Properties would
  be cut by margin calls there; the replica is what TradingView should show with the margin set to 0 % (no
  margin checks). On gold 0.1 ounce is about 130 USD and `margin_bars` is 0 in all 112 runs of the seven
  cells.
- **T12** Exit levels are not rounded to the tick grid (at most half a tick per level); quantities are
  rounded by `qtyStep` only.
- **T13** `pyramiding=100` never binds (asserted).
- **T14** Time stop: `entry_bar_index` is the bar of the fill; a trade filled at or inside bar `i` is closed
  at the close of bar `i + timeStop`.
- **T15** The script reads `strategy.opentrades`, `strategy.position_size` and `strategy.equity` before its
  own orders fill.
- **T16** Path tie `high - open == open - low`: low first.

Replica conventions (no Pine counterpart):

1. Window: flat and an empty pending list at the first window bar; indicators and the ATR are warmed up from
   the start of the data. On the last window bar, after its fills, every open trade is closed at that close
   (kind `end`, exit cost charged) and unfilled pending orders are dropped (`pend_open_end`). `exposure`,
   `max_open`, `max_expo`, `margin_bars` of that bar are taken before the `end` closes; the equity curve's
   last point, the drawdown and the halves after them.
2. `strategy.equity` seen by the script = 10,000 + realized P/L - every cost charged so far (entry costs of
   open trades included) + open P/L at that close. Costs are charged at each fill, so with costs they feed
   Risk sizing. No floor at zero; Risk sizing on an equity <= 0 places nothing.
3. `eq_before`: a fill at a close = the script-time equity minus the costs of the fills of that close placed
   before it; a fill inside a bar = the previous bar-close equity.
4. Fair halves (trades ENTERED in each half): `halves_rule` 'additive' when the quantity does not depend on
   equity (Fixed, or Risk without a stop): `100 * sum(pnl) / 10000`; 'compound' for Risk with a stop:
   `100 * (prod(1 + pnl / eq_before) - 1)`, NaN if an `eq_before` of that half is <= 0.
5. `R` of a trade = `pnl / (qty * slTicks * mintick)` with the stop distance of its placement bar; NaN
   without a stop.
6. Costs per fill and unit `(fixed, fraction of the fill value)`: 'tv' none (the script sets no commission
   and no slippage); 'ours' XAU (0.15, 0), BTC (0.10, 0.0002); 'stress' XAU (0.26, 0), BTC (0.11, 0.00035).
   The stress tick is charged as a cost; fill prices never change.
7. Touch tests use a tolerance of 1e-8 (1e-6 tick), as `engine.py`.

---------------------------------------------------------------------------------------------------------

## 5. Path 'mag' (Bar Magnifier with the 1-minute data)

Definition (SWEEP_AH_SPEC.md section 2, REPLICA_SPEC.md stage 3). The sub-bars of a chart bar are the rows
of `data/<PAIR>_1.parquet` with `t_open` in `[chart t_open, chart t_close)`. Step 1 of a chart bar (the
intrabar fills) walks them in time order:

- every exit order (stop loss, take profit, trailing stop) is evaluated on each sub-bar with that sub-bar's
  own T4 path and its own open test: a level passed by the jump between two sub-bars fills at the next
  sub-bar's open; the trailing state (armed, best price) carries over;
- every live pending entry (limit / stop entry of limit mode) fills along the sub-bars in the same way; the
  exit order of the trade it opens runs on the rest of that sub-bar (no open test), then on the following
  sub-bars;
- the script, its market orders, `close_all`, the time stop and the placement-close attempt of T6 stay on
  the chart bar's close.

Both paths are one code path (`_step1`): 'tv' is the walk with the chart bar as its only sub-bar. On chart
"1" the sub-bars are the chart bars, so mag == tv bit for bit. Every chart bar of all 14 cells equals its
sub-bars (first open, highest high, lowest low, last close); `get_sub` refuses a window where that fails.

Limits of the path: TradingView's Bar Magnifier chooses its own lower timeframe per chart; here it is always
1 minute. Inside a 1-minute bar the order of the extremes is still the T4 guess.

---------------------------------------------------------------------------------------------------------

## 6. Not implemented, not reproducible

- Seconds rungs (30 Sec, 15 Sec, 5 Sec, 1 Sec): no data below 1 minute, so they are na on every bar
  (`xpw.py`): READ HERE never lands there and "every rung" has 9 live rungs.
- `agreeOn` true (rung agreement): `xpw.py` raises `NotImplementedError`.
- Live behaviour: entries on the first tick a label appears on a still-forming higher-rung state, `varip`,
  label redraws. History only.
- Margin calls and insufficient-funds rules (T11), FIFO pairing in the List of Trades (T10), tick rounding
  of levels (T12), TradingView's limit on the number of orders outside Deep Backtesting (the 1- and 5-minute
  cells have 4,268 to 63,358 trades).
- TradingView's own price feed, sessions and volume; the data files are used as they are (volume is not
  used by this script).

---------------------------------------------------------------------------------------------------------

## 7. Speed and memory

Measured in the test run (`tests_xpw23.log`), numba cache warm:

- BTC "1" (1,039,430 bars): first `prepare` 8 to 12 s (limit 120 s); one `simulate` 0.03 to 0.05 s with the
  default, inverted and limit settings on both paths, 0.11 to 0.15 s for the heaviest setting tried (trail
  off, no target, stop 6 ATR; limit 1 s); `summary` 6 to 19 ms.
- 60-minute cells: one `simulate` about 2 ms ('tv') to 3 ms ('mag').
- The 14 cells of the runner (16 + 8 runs each): 1.3 to 11 s per gold cell, 3.7 to 22 s per BTC cell.
- Memory: one `xpw.xpw_signals` call on a 1-minute chart peaks near 2.4 GB by itself (its frame of 1.04 M
  rows; the module is not ours to change). A process that prepares several signal settings on chart "1"
  must call `xpw23.free_caches()` between them to stay under 3 GB: the runner does (BTC 1: 2.80 GB), the
  tests do (BTC 1 child: 2.85 GB).

---------------------------------------------------------------------------------------------------------

## 8. Verification, in one place

Details and numbers: `reconcile_xpw23.md`.

- Two independent builds agree on every trade, summary field and equity bar: 1,536 settings, 8,454,045
  trades, 0 differences (two seeds; BTC and XAU; charts 240, 60, 15, 5, 1; full windows).
- The canonical module equals both on every case of the tests (three-way).
- Where the two XPW Pine files place the same orders (filter off, Signal tick, tick exits, no target, no
  time stop) the canonical module equals the verified replica of the trailing-TP file on both paths:
  `engine.py` ('tv') and `sweep_core._run_mag` ('mag'), 240 runs, 850,858 trades.
- Path 'mag': equal to 'tv' on chart "1" and with one fake sub-bar per chart bar; equal to a slow
  pure-Python reference on random settings over 2-month windows; hand-made sub-bars with known answers;
  hand traces with the minutes printed (`reconcile_xpw23_trace.log`).
- Money: every money field recomputed from the trade list; Risk quantities against `entryQty()`.
- Update 1: the properties the Pine header states (inverted == "Reverse every label" with the filter off;
  the mirror with the other one-side mode; the FGD sides).
- Tests (stage 3): 168 PASS, 0 FAIL. Mutation check: 20 one-line mutants of `xpw23.py`, all 20 make the tests
  fail (`xpw23_s3_mutants.log`). Stage 4 added 26 tests: 194 PASS, 0 FAIL (`tests_xpw23.log`); see section 9.

What none of this establishes: that TradingView does what section 4 assumes. The two builds, the references
and the tests all read the broker from the same brief.

---------------------------------------------------------------------------------------------------------

## 9. Stage 4 (audit, 26 Nov)

Files of the audit: `$W/xpw23_s4/` (`audit_ref.py`, `audit_cmp.py`, `mutants.py`, `mutants2.py`, `audit_kill.py`,
`rerun_cells.py`, `sanity_paths.py`, `fifo_view.py` and their logs; `orig/` holds the stage 3 files as they
were).

**Result: no defect found in `xpw23.py`.** The module is unchanged (sha256 `a55af554...6a0e36`), so no result
changed. One defect was found and fixed in the test tooling, and the tests were extended.

- **Pine read again**, lines 444-546 and 1128-1799 against the kernel, and the brief's assumptions against the
  Pine. The three shared line ranges were hashed again (equal), and a scan of the names the shared block
  1143-1626 reads from outside it gives the inputs of 447-508 plus `reverseAll`, `tradeAgree` and `useLimit`
  (drawing only). The fusion and Update 1 diffs hold what the brief lists, nothing else.
- **A fourth reference, written from the Pine alone** (`audit_ref.py`): real prices, an order book, the Pine
  lists kept as lists, its own ATR and its own 1-minute mapping, and ONE joint walk per path segment in which
  every live order is an event taken in price order (the kernel walks each trade by itself). Against
  `xpw23.py`: 342 random settings, 660 runs on both paths, 878,810 trades, all 14 cells (full windows on charts
  240 to 15, 45- and 90-day windows on the 5-minute charts, 10- and 20-day windows on the 1-minute charts):
  every trade, the equity curve and the funnel / pending counters equal. 0 runs differ.
- **Defect in the tooling (fixed):** `reconcile_xpw23_cmp.cmp_frames` returned two values when the two trade
  lists had different lengths, and both callers (`reconcile_xpw23_cmp.py`, `tests_xpw23.three_way`) unpack
  three. A difference in the NUMBER of trades between two builds therefore ended in a `ValueError` instead of
  a reported difference (the tests still failed, through "child ended abnormally"). It never fired in stage
  3 because A and B never differed. Impact on any number: none.
- **Tests extended:** section `audit` of `tests_xpw23.py`, 26 hand-made cases of the script logic (the
  pre-filter gate, the closes, the pending list and its ghosts, the reversal bar, one-side mode, the time
  stop, the trail floors, Risk sizing, the ATR), each answer worked out by hand from the Pine. Reason: of 28
  new one-line mutants, 4 passed the sections unit / fake / ref / money / inv (an exit-only label not
  cancelling pending long / short entries; an exit-only label closing in limit mode on a bar with an entry of
  the side held; `trail_offset` without its 1-tick floor). The new section fails on 27 of the 28 by itself;
  the 28th (a stop passed at the open filled at the stop price) fails section unit. Full run: 194 PASS.
- **The 14 cells run again** with the unchanged module into `xpw23_s4/out/`: 14 x 24 runs, every field of
  every summary equal to the saved files.
- **Why the TradingView view beats the 1-minute view:** only the trailing stop. Default inputs, filter off:
  with the trail on, 15 to 17 % of the trades end differently on the two paths and the 1-minute view is
  worse by 82 % of the account on BTC 60 (56 % on BTC 240; 0.25 % on XAU 60); with the trail off the two
  paths differ on 0 to 0.5 % of the trades and by at most 0.05 % of the account.

Limits to add to sections 4 and 6:

- **FIFO in numbers.** If TradingView pairs FIFO as T10 assumes (same fills, other pairing), its List of
  Trades would show the same net profit, a profit factor within 0.004 and a win rate 1 to 7 points LOWER
  than the tables here (24 default runs on six cells: 10 to 31 % of the rows change partner). The summary
  field `fifo_exits` counts the exits that fire while an older trade is still open; each of them moves at
  least two rows, so it is a lower bound of the rows that change partner (BTC 60, filter off: 628 against
  1,037), not their number. With the time stop on, or Risk sizing, FIFO also changes which trades the
  script sees as open: those settings carry an extra doubt.
- **`syminfo.mintick` is taken as 0.01 on both pairs.** In ATR mode (the default, and the whole calibration
  grid) the tick cancels out, apart from the 1-tick floor of the trail distance. In Points mode every
  distance scales with it: on a gold feed with a 0.001 tick the same "pts" are ten times smaller.
- **Signals are shared code.** The earlier auditor's literal signal reference (`audit_xpw_ref.py`) was run
  again against today's `xpw.py`: 7 of its 8 cases equal on every column; the 8th (BTC daily chart, whole
  history) differs on two bars of 2012 and 2014 in the 1 Min rung's display columns, on no trading column,
  years before the windows used here.

