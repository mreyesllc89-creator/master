# SPEC_fgds: FlashGold Direction Strategy [Update 1] (key `fgds`), stage 1 brief

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Read first: `$W/REPLICA_SPEC.md` (stages, interface, data, windows, cost modes), `$W/SPEC_AH.md` (Pine
built-ins, the intrabar path = "rule 4"), `$W/SWEEP_AH_SPEC.md` section 2 (prepare / simulate, 'mag',
'stress', fair halves, the trailing exit), `$W/fgf.py` (docstring, `fgf_permissions`, `filter_signals`) with
`$W/reconcile_fgf.md`, and `$W/hrd.py` as the worked example of the broker (`_walk`, `summary_fast`,
`extra_fields`, `sub_bars`, `COSTS`).

Ground truth: `/home/user/master/FlashGold_Direction_Strategy.pine` at HEAD (813 lines; `Lnnn` below are its
line numbers). Where this brief and the Pine disagree, the Pine wins; say so in your notes. Builders write
`$W/fgds_a.py` / `$W/fgds_b.py` and `$W/fgds_<a|b>_notes.md`, without reading the other build. Never edit an
existing module. Never write inside `/home/user/master`. `python3 -I`, at most 2 processes, under 3 GB each.

The stage-1 probes are in `$W/fgds_spec_tmp/` (`probe_trig.py`, `probe_dims.py`, `probe_ident.py`,
`probe_side.py`, `probe_sim.py`). **Builders must NOT read anything in that directory** (they would make the two builds share their mistakes). Their
numbers are quoted below as "probe, unverified": one implementation, no cross-check. If your two builds
agree with each other and not with a probe number, trust the builds and say so.

Eight facts shape everything below:

1. **This strategy has no signal of its own.** Every trigger is a function of six outputs of the direction
   filter (`fgfBuyOk`, `fgfSellOk`, `fgfOpen`, `fgfSigOk`, `fgfSigDir`, `fgfNewSig`), and `fgf.py` returns
   all six (`buyOk`, `sellOk`, `open_`, `sigOk`, `sigDir`, `newSig`). **No filter series is missing; nothing
   of the filter is reimplemented.** The strategy section itself (L694-813) has no `request.security`, no
   session, no day boundary, no time zone, no cooldown, no daily limit.
2. **With the filter off nothing trades** (every trigger starts with `fgfOn and ...`). There is no unfused
   original: the REPLICA_SPEC self-check "`fgfOn` False reproduces the original" becomes "`fgfOn` False
   gives zero triggers and zero trades" plus kernel tests on injected trigger arrays (section 13).
3. **`inv` IS the script's own input `dsDirection == "Inverted"`** (L699, L760), older than Update 1. Update 1
   changed the title, the header and one tooltip sentence, no code (checked with
   `git diff 6c59b9f HEAD`). Section 8 says exactly what the Pine does with it.
4. **Orders are market orders placed at a bar close and filled at the next open**
   (`process_orders_on_close=false`); the bracket is sent with the entry, in ticks from the FILL price, so a
   trade can open and close inside one bar (probe: about 17 % of the default trades).
5. **`calc_on_order_fills=false` and `calc_on_every_tick=false`**: exactly one script run per bar, on history
   and live. No extra-run question (unlike gvl).
6. **The default trigger "Zone start" trades mostly AGAINST the signal.** A BUY signal puts the level above
   the signal close (entry price = ask + 0.25 ATR), so at the signal candle's close price sits just below the
   band: the SELL ZONE starts there (`fgfAgainst` is on). Probe, BTC 60: 3,233 zone starts, 445 of them on
   the signal's own side and 2,788 against it (all 1,856 that fall on the bar a signal becomes known are
   against it). The three triggers are three different strategies.
7. **Sizing: Risk 0.5 % of equity over the stop, 10,000 account, caps.** `dsMaxQty = 50` binds on gold below
   30 minutes (probe: 99 % of the trigger candles on XAU 1, 83 % on XAU 5, 30 % on XAU 15, 2 % on XAU 30,
   never above); on BTC almost never. With costs 'ours' the default account is ruined on the low timeframes
   (probe: BTC 1, BTC 5, XAU 5: equity so small that the quantity floors to 0 and trading stops; `zero_qty`).
8. **`strategy()` sets `margin_long = 1`, `margin_short = 1`** and the script caps its own quantity with the
   same 1 % (`dsMarginPct`), so TradingView's margin rule can only bite where that cap binds (probe: 0.2 % of
   the BTC 1 trigger candles at the initial equity, nowhere else). Not modelled; counted (F9).

---------------------------------------------------------------------------------------------------

## 1. What the file is made of

| part | lines | replica |
|---|---|---|
| header (Update 1 text, earlier test record) | 1-97 | read it; not a source of numbers (other feeds, other windows) |
| `strategy()` | 98 | section 2 |
| FlashGold Direction Filter block | 101-681 | `$W/fgf.py`, never reimplemented. Checked with `diff`: byte-identical to the block of `FlashGold_Direction_Filter_v1_2.pine`, and to the block `fgf.py` replicates (trailing-TP XPW file) except `FGF_FORCE_OVERLAY = false` (drawing). Every input default equals `fgf.DEFAULTS`, **`fgfOn` = true** included (L107) |
| exported plots | 683-692 | ignored (Data Window) |
| strategy inputs | 697-725 | section 3 |
| exit geometry, `dsQty` | 728-746 | `simulate`, sections 7 and 9 |
| triggers, keep permissions | 749-768 | `prepare` (the trigger and keep series) + `simulate` (the choice by `dsTrigger`, the `dsInv` swap), sections 4 and 7 |
| bars in trade | 771-777 | `simulate`, section 7 |
| orders | 780-813 | `simulate`, sections 6 and 7 |

There are no alerts, no labels, no tables and no plots in the strategy section.

---------------------------------------------------------------------------------------------------

## 2. The `strategy()` call (L98)

```
strategy("FlashGold Direction Strategy [Update 1]", "FG-DS U1", overlay=true, initial_capital=10000,
  default_qty_type=strategy.fixed, default_qty_value=1, pyramiding=0, calc_on_every_tick=false,
  calc_on_order_fills=false, process_orders_on_close=false, commission_type=strategy.commission.percent,
  commission_value=0, slippage=0, margin_long=1, margin_short=1, max_lines_count=500, max_labels_count=500,
  max_bars_back=500)
```

| argument | meaning for the replica |
|---|---|
| `initial_capital=10000` | `INITIAL_CAPITAL = 10000.0` (not the 1,000,000 of SPEC_AH rule 7). Net % depends on it: `dsMaxQty = 50` and `dsQtyStep = 0.001` are absolute |
| `default_qty_type=fixed`, `default_qty_value=1` | never used: both `strategy.entry` calls pass `qty=dsQ` |
| `pyramiding=0` | one entry per side. The script never sends a same-side entry while in a position (`dsEnterLong` needs flat or short). An opposite `strategy.entry` that fills while a position is open closes it and opens the new one (reversal, F7) |
| `calc_on_every_tick=false` | one run per bar at its close, live too |
| `calc_on_order_fills=false` | no extra run after a fill |
| `process_orders_on_close=false` | a market order placed in the run of bar i (entry or `strategy.close`) fills at the OPEN of bar i+1 (SPEC_AH rule 1) |
| `commission_value=0` (percent), `slippage=0` | cost mode 'tv' = NO cost, fills at the raw prices. TradingView's own report of this file is cost-free |
| `margin_long=1`, `margin_short=1` | margin 1 % (leverage 100). Not modelled, counted (F9, section 9) |
| not set: `close_entries_rule` | FIFO; irrelevant (one trade open at a time) |
| not set: `backtest_fill_limits_assumption` | 0: a limit (the target) fills when price touches it |
| not set: `use_bar_magnifier` | false = path 'tv'; path 'mag' (stage 3) = Bar Magnifier on |
| `overlay`, `max_*` | drawing / buffers: ignored |

Symbol constants: `syminfo.mintick = 0.01`, `syminfo.pointvalue = 1`, both pairs. `bar_index` = the row
number in the data file; only differences of it are used.

---------------------------------------------------------------------------------------------------

## 3. Inputs

### 3.1 SIGNAL inputs -> `prepare(pair, chart_tf, params)`

| Pine name (line) | default | used for |
|---|---|---|
| `fgfOn` (107) | **true** | false: every trigger is false, nothing trades. Do not call `fgf` then |
| every other trading input of the filter block (108-117, 131-168): `fgfTf`, `fgfLvMode`, `fgfLast`, `fgfMinutes`, `fgfBars`, `fgfCheck`, `fgfBandAtr`, `fgfAgainst`, `fgfAllowBuy`, `fgfAllowSell`, `fgfSpreadPts`, `fgfEntryDistPts`, `fgfHoldBars`, `fgfHoldFavPts`, `fgfOnePerBar`, `fgfDistUnit`, `fgfBurstAtr`, `fgfEntryDistAtr`, `fgfHoldFavAtr`, `fgfBurstPts`, `fgfUseBurst`, `fgfAnyCombo`, `fgfDriftBars`, `fgfUseDrift`, `fgfUseZones`, `fgfParentTf`, `fgfRsiLen`, `fgfFastLen`, `fgfMinAligned`, `fgfFlatParent`, `fgfIgnoreNa`, `fgfHtfClosed`, `fgfUseZ1..6`, `fgfZTf1..6` | `fgf.DEFAULTS` | passed unchanged to `fgf.fgf_permissions` (its own validation applies). They ARE this strategy's signal inputs |
| replica: `start`, `end` | the pair's window | window by `t_close`, as `hrd._window` |

### 3.2 ORDER / EXIT inputs -> `simulate(P, x)` (also accepted by `prepare` / `run` as defaults)

| Pine name (line) | default | used for |
|---|---|---|
| `dsTrigger` (698) | "Zone start" | "Zone start", "Signal confirmed", "New signal": which of the three trigger pairs of `P` is traded, and which keep pair. By nature a signal input; it is read by `simulate` because `prepare` computes the three pairs together from one filter call (one `prepare` per filter setting instead of three, and `P` depends on no `ds*` input) |
| `dsDirection` (699), alias `inv` | "Follow the filter" (`inv` False) | "Inverted" = `inv` True (section 8). Raise if both are given and disagree |
| `dsSides` (700) | "Both" | "Both", "Long only", "Short only": the REAL orders |
| `dsZoneExit` (701) | true | zone-end close; has no effect with "New signal" (`dsUseZoneExit`, L768) |
| `dsReverse` (702) | true | an opposite entry reverses (true) or only closes (false) |
| `dsExitMode` (705) | "ATR" | "Points" / "ATR" |
| `dsSlPoints`, `dsTpPoints` (706-707) | 1000, 3000 | Points mode, ticks; 0 = none |
| `dsAtrLen` (708) | 14 | `dsAtr = ta.atr(dsAtrLen)` of the CHART: keep an ATR cache per length in `P` (computed from row 0 of the file, on demand) |
| `dsSlAtr`, `dsTpR` (709-710) | 1.0, 3.0 | ATR mode: stop = mult x ATR; target = stop distance x `dsTpR` (0 = no target) |
| `dsUseTrail` (711) | false | trailing stop in the same `strategy.exit` |
| `dsTrActPts`, `dsTrPts` (712-713) | 2000, 500 | Points mode, ticks |
| `dsTrActAtr`, `dsTrDstAtr` (714-715) | 2.0, 0.5 | ATR mode |
| `dsTimeStop` (716) | 0 | time stop, bars; 0 = off |
| `dsQtyMode`, `dsFixedQty`, `dsRiskPct`, `dsMaxQty`, `dsQtyStep`, `dsCapMargin`, `dsMarginPct` (719-725) | "Risk %", 1.0, 0.5, 50, 0.001, true, 1.0 | `dsQty` (section 9) |
| replica: `path` | 'tv' | 'tv'; 'mag' raises `NotImplementedError` until stage 3 |
| replica: `cost` | 'tv' | 'tv' / 'ours' / 'stress' (section 9) |

`simulate` raises if `x` holds a 3.1 key that differs from `P`'s (as `hrd.simulate`). Validate as the Pine
inputs do: option strings exactly as written (else `ValueError`); `dsAtrLen >= 1`, `dsSlAtr >= 0.01`,
`dsTrPts >= 1`, `dsTrDstAtr >= 0.005`, `dsQtyStep >= 0.000001`, `dsTimeStop` an integer `>= 0`, every other
number `>= 0`. Any unknown key: `ValueError`.

### 3.3 Drawing only: listed once, ignored (accepted, no effect)

`fgfShowBg`, `fgfShowLv`, `fgfSigMark`, `fgfShowTbl`, `fgfTblPos`, `fgsShow`, `fgsWin`, `fgsH`,
`FGF_FORCE_OVERLAY`; the nine `plot(...)` exports L684-692; the order comments ("Long", "Short", "Opposite
signal", "Zone ended", "Time stop": they become the exit kinds of section 12).

---------------------------------------------------------------------------------------------------

## 4. `prepare`: the filter call, the three trigger pairs, the keep pairs

Window rows of `$W/data/<PAIR>_<TF>.parquet`: `w0 = searchsorted(t_close, start, 'left')`, `w1 =
searchsorted(t_close, end, 'right')`, `n = w1 - w0`, window bar `j` = file row `w0 + j`.

**The filter call.** The triggers need the previous chart bar, so ask for one row more:

    F = fgf.fgf_permissions(pair, chart_tf, int(t_close[w0 - 1]), end, fgf_params)
    assert F.index[0] == w0 - 1 and len(F) == n + 1

(`fgf` warms every series up from the start of the data and its chart-level values reach back three rows on
its own, so row `w0 - 1` is exact. Do not ask for the whole file: on BTC "1" that is 6.5 M rows.)
`fgf_params` = the keys of `params` that are in `fgf.DEFAULTS`. `x[1]` below = the previous row of `F`.
With `fgfOn` False do not call `fgf`: every array of this section that starts with `fgfOn and` is all False
(the two plain keep arrays `buyOk` / `sellOk` are all True and are never read, because no trade exists).

**The trigger and keep series (L749-759), computed to the letter, for every window bar:**

```
buyEdge   = fgfOn and buyOk  and not buyOk[1]                              # dsBuyEdge
sellEdge  = fgfOn and sellOk and not sellOk[1]                             # dsSellEdge
confBuy   = fgfOn and open_ and sigOk and sigDir > 0 and buyOk             # dsConfBuy  (dsSigOkNow inlined)
confSell  = fgfOn and open_ and sigOk and sigDir < 0 and sellOk            # dsConfSell
confEdgeB = confBuy  and (not confBuy[1]  or newSig)                       # dsConfEdgeB
confEdgeS = confSell and (not confSell[1] or newSig)                       # dsConfEdgeS
newBuy    = fgfOn and newSig and sigDir > 0                                # dsNewBuy
newSell   = fgfOn and newSig and sigDir < 0                                # dsNewSell
```

`buyOk`, `sellOk`, `open_`, `sigOk`, `sigDir`, `newSig` are the `fgf` columns (`fgfBuyOk`, `fgfSellOk`,
`fgfOpen`, `fgfSigOk`, `fgfSigDir`, `fgfNewSig`). All of them were among the 23 columns reconciled between
the two `fgf` builds (0 mismatching cells, reconcile_fgf.md), `sigOk` and `open_` included.

**The pairs `simulate` picks from (L758-759, 764-765):**

| `dsTrigger` | `rawBuy` / `rawSell` | `keepBuy` / `keepSell` |
|---|---|---|
| "Zone start" | `buyEdge` / `sellEdge` | `buyOk` / `sellOk` |
| "Signal confirmed" | `confEdgeB` / `confEdgeS` | `confBuy` / `confSell` |
| "New signal" | `newBuy` / `newSell` | `buyOk` / `sellOk` (never read: `dsUseZoneExit` is false) |

Things to know (each one is a check for your notes):
- With the filter on `buyOk` and `sellOk` are never both true on a bar (band > 0: above the upper edge and
  below the lower one; band 0: above and below the level, and the "at the level" cases need `sigDir > 0` and
  `< 0`). So `rawBuy` and `rawSell` are never both true, for any trigger. **Assert it** in `prepare` for the
  three pairs. (It makes the tie-break `and not dsEnterLong` of L786 unreachable.)
- Identity: `confBuy == (fgfOn and buyOk and sigDir > 0)` and `confSell == (fgfOn and sellOk and sigDir <
  0)` on every row (`buyOk` implies `open_`, and with `sigDir > 0` it implies `sigOk`). Compute the literal
  expression and assert the identity (probe: true on 50 cell x setting cases).
- "Zone start" does NOT re-trigger when a new signal arrives while price stays in the same zone; "Signal
  confirmed" does (`or newSig`), but only for the signal's own side.
- "New signal" does not read `fgfOpen`, the zones, the level, the band, `fgfAgainst`, `fgfAllowBuy`,
  `fgfAllowSell`, `fgfLast`: a signal trades even when the permission has ended or its side is switched off.
  On a chart longer than the filter candle several signals can become known on one chart bar: `newSig` is
  one boolean, and `sigDir` is the direction of the LAST of them.
- History: `fgfCheck` "Tick" and "Candle close" both judge the chart bar's close; "Candle open" judges its
  open (the same decision one bar later, in effect).

**ATR for the exits** (`dsAtr`, L728): `ta.atr(dsAtrLen)` on the chart file from row 0 = `ta.rma(ta.tr(true),
n)`: `tr[0] = high[0] - low[0]`, `tr[i] = max(max(high - low, abs(high - close[i-1])), abs(low -
close[i-1]))`; `atr[n-1]` = the plain mean of `tr[0..n-1]` summed in index order; then `atr[i] = (1.0 / n) *
tr[i] + (1.0 - 1.0 / n) * atr[i-1]`; na before row `n-1`. This is `fgf._atr(high, low, close, n)`; you may
call it.

**What `P` holds:** `pair`, `tf`, `start`, `end`, `mid = start + (end - start) // 2`, `mid_j =
searchsorted(t_close_window, mid, 'right') - 1`, `w0`, `w1`, `n`, window arrays `open high low close t_open
t_close`, the ten boolean arrays above (`buyOk sellOk confBuy confSell buyEdge sellEdge confEdgeB confEdgeS
newBuy newSell`), `sigDir`, `newSig`, an ATR cache per length (window slice), the resolved `prepare`
parameters, and the counts of the six trigger arrays. Nothing in `P` may depend on a 3.2 input. Cache the
bars per `(pair, tf)`; `fgf` caches its own filter series per parameter set (`fgf._FILTER`).

Reference counts, default filter inputs, full windows (probe, unverified; `buyOk` / `sellOk` of BTC 1 equal
the 417,969 / 393,349 of reconcile_fgf.md):

| cell | window bars | `buyEdge` / `sellEdge` | `confEdgeB` / `confEdgeS` | `newBuy` / `newSell` |
|---|---|---|---|---|
| BTC 1 | 1,039,430 | 14,922 / 15,043 | 4,749 / 4,960 | 1,882 / 1,918 |
| BTC 5 | 210,155 | 7,738 / 7,830 | 2,370 / 2,468 | 1,882 / 1,918 |
| BTC 15 | 70,058 | 4,871 / 4,885 | 1,429 / 1,426 | 1,882 / 1,918 |
| BTC 30 | 35,032 | 3,353 / 3,416 | 868 / 870 | 1,882 / 1,918 |
| BTC 60 | 17,518 | 1,604 / 1,629 | 232 / 213 | 1,882 / 1,918 |
| BTC 120 | 8,760 | 1,105 / 1,137 | 151 / 144 | 1,633 / 1,650 |
| BTC 240 | 4,381 | 736 / 729 | 89 / 79 | 1,329 / 1,348 |
| XAU 1 | 493,819 | 6,822 / 6,724 | 1,965 / 1,988 | 851 / 847 |
| XAU 5 | 98,787 | 3,404 / 3,402 | 950 / 958 | 851 / 847 |
| XAU 15 | 32,935 | 2,136 / 2,122 | 565 / 552 | 851 / 847 |
| XAU 30 | 16,471 | 1,503 / 1,493 | 358 / 343 | 851 / 847 |
| XAU 60 | 8,238 | 733 / 741 | 84 / 87 | 851 / 847 |
| XAU 120 | 4,493 | 516 / 526 | 60 / 55 | 760 / 765 |
| XAU 240 | 2,246 | 350 / 353 | 39 / 37 | 646 / 640 |

---------------------------------------------------------------------------------------------------

## 5. How TradingView runs this script on history

History bars: the script runs once per bar at its close (`barstate.isconfirmed` true), nothing else (both
`calc_on_*` flags are false). Orders of that run are processed from the next bar on. Per window bar `j`:

    A. fills at the open of j        (the orders the run of j-1 placed: one close, or one entry)
    B. the bracket of the open trade along the bar's path (also for a trade filled in A)
    C. the script run at the close of j, on the position and equity left by A and B
    D. the bar-close equity point

Same-bar exit: yes (the bracket belongs to the entry order and is live from the fill). Same-bar re-entry:
never (an entry is a market order of a close run; it fills at the next open). A trade stopped inside bar j
leaves the account flat at j's close, so a trigger ON bar j can open a new trade at the open of j+1.

Live-only code: none in the strategy section. The filter's live branches (`fgfLiveBar`, `timenow`) are dead
on history and are not in `fgf.py`.

---------------------------------------------------------------------------------------------------

## 6. The broker inside a bar (path 'tv')

### 6.1 Orders the script can place (all of them)

| call (lines) | type | replica |
|---|---|---|
| `strategy.entry("DS Long", strategy.long, qty=dsQ)` (789) | market buy | order `d = +1` |
| `strategy.entry("DS Short", strategy.short, qty=dsQ)` (797) | market sell | order `d = -1` |
| `strategy.exit("DS Long Exit" / "DS Short Exit", from_entry, loss, profit[, trail_points, trail_offset])` (791 / 793, 799 / 801) | bracket of that entry, in ticks, sent in the same run as the entry and never again | the ticks stored with the order |
| `strategy.cancel("DS Long Exit" / "DS Short Exit")` (795, 803) | only when the entry has no stop, no target and no trail | the order has no bracket (F12) |
| `strategy.close("DS Long" / "DS Short", comment=...)` (811, 813) | market close at the next open | `close_req` with its kind |

Ids: "DS Long" is always a real buy, "DS Short" a real sell, also with Inverted. One run places at most ONE
of: an entry order, or a close (the close block L805 runs only when no entry is placed; `dsEnterLong` and
`dsEnterShort` exclude each other). So at an open there is at most one thing to fill. Assert it.

An order: `{d (real side), sig (normal-frame side of the trigger: +1 BUY trigger, -1 SELL trigger), qty,
slT, tpT, actT, dstT (ticks of the PLACING bar, section 7 C1), useTrail, capf, placed bar}`.

### 6.2 A trade's levels, fixed at its fill at price `e`, real side `d`

```
mintick = 0.01
SL  = e - d * (slT * mintick)        exists if slT > 0      (loss = dsLoss)
TP  = e + d * (tpT * mintick)        exists if tpT > 0      (profit = dsProfit)
if dsUseTrail:  A = e + d * (actT * mintick) ;  off = dstT * mintick      (dstT >= 1 tick by L733)
                armed = (actT <= 0) ;  best = e
```

No rounding to the tick grid, no tolerance, inclusive comparisons (as `hrd._walk`). The stop in force for a
long is `S* = max(SL, best - off if armed)`; for a short `S* = min(SL, best + off if armed)`; a missing
level does not take part. A stop fill is kind 'trail' if the trailing stop is the level hit (long: armed and
`best - off >= SL`, or no `SL`), else 'sl'. The levels never change after the fill except the trailing stop
(the script never calls `strategy.exit` for an open trade).

### 6.3 One bar `j`

**A. The open `o`.**
- A1. `close_req` set (then a position is open): close it at `o`, kind = `close_req` ('opp', 'zone' or
  'time'). Clear `close_req`.
- A2. An entry order waiting: if a position is open it is the opposite side (assert `pos == -d`): close it
  at `o`, kind 'reverse'. Then open the order's trade at `e = o` with the order's own `qty` and ticks
  (6.2). Clear the order.
- A3. A trade that was open before this bar and is still open (neither A1 nor A2 touched it), long (a short
  with the inequalities turned and `min` for `max`): `S*` exists and `o <= S*` -> exit at `o` ('sl' /
  'trail'); else `TP` exists and `o >= TP` -> exit at `o` ('tp'); else, with `dsUseTrail`: if `armed`, `best
  = max(best, o)`, else if `o >= A`: `armed = True`, `best = o`.

**B. The path** for the trade now open (old or just filled). `v1, v2` = `high, low` if `(high - open) <
(open - low)` else `low, high` (a tie goes low first); three legs `o -> v1`, `v1 -> v2`, `v2 -> close`. On a
leg from `a` to `b`, for a long (short mirrored):

```
b > a (rising):   TP exists and b >= TP  -> exit at max(TP, a), 'tp'
                  else with dsUseTrail: if armed: best = max(best, b); elif b >= A: armed = True, best = b
b < a (falling):  S* (as it is at the start of the leg; it does not move on an adverse leg)
                  S* exists and b <= S*  -> exit at min(S*, a), 'sl' / 'trail'
```

On a rising leg the target is tested before the trail arms, so a target at or inside the activation
distance means the trail never acts. A3 followed by B is exactly `hrd._walk` in long space (negate a
short's prices); for a trade filled in A2 the walk starts at `v0 = o = e`, where A3 is a no-op (`SL < e <
TP`, and `armed`, `best` are already set by 6.2).

Worked checks (gold-like numbers):
- Sizing and bracket. Placing bar: equity 10,000, close 1,250.00, ATR(14) 2.00, defaults. `slT = 200`, `tpT
  = 600`, stop distance 2.00, `q = 10000 * 0.5 / 100 / 2.00 = 25.0` (caps 50 and 800 do not bind). Next bar O
  1,250.40 H 1,250.90 L 1,248.10 C 1,248.50: long 25 at 1,250.40, `SL` 1,248.40, `TP` 1,256.40; path O-H-L-C
  (0.50 < 2.30); the fall meets 1,248.40: exit 1,248.40, 'sl', same bar (`entry_bar == exit_bar`), `pnl`
  -50.00 = -0.5 % of the account. Inverted, the same trigger: SHORT 25 at 1,250.40, `SL` 1,252.40, `TP`
  1,244.40; the bar touches neither; held.
- Gap. A long from 1,250.40 (`SL` 1,248.40) that survived its fill bar; the next bar opens at 1,247.90:
  exit 1,247.90, 'sl' (A3).
- Trail. `dsExitMode` "Points", `dsSlPoints` 1000, `dsTpPoints` 0, `dsUseTrail`, `dsTrActPts` 2000,
  `dsTrPts` 500; long from 2,000.00: `SL` 1,990.00, no `TP`, `A` 2,020.00, `off` 5.00. A later bar O 2,012.00
  H 2,026.00 L 2,010.00 C 2,018.00: path O-L-H-C; the rise to 2,026.00 arms it (`best` 2,026.00); the fall
  to 2,018.00 meets 2,021.00: exit 2,021.00, 'trail'.
- Reversal. Long 25 from 1,250.40; the run of bar j sees a SELL trigger (`dsReverse` on) and places a short
  with the quantity and ticks of bar j; bar j+1 opens at 1,251.00: the long closes at 1,251.00 ('reverse',
  `pnl` +15.00) and the short opens at 1,251.00 with its own bracket from 1,251.00.

**Window.** Flat, no order, no `close_req`, `prevPos = 0`, `entryBar = na` at the first window bar; its run
is the first decision, so the first possible fill is at the open of the second window bar. On the last
window bar A, B, C and D run; then an open trade is closed at the last close (kind 'end', exit cost charged,
`exit_time = t_close`); an order or `close_req` placed there is dropped (`orders_unfilled_end`).

**Path 'mag' (stage 3, not built now; keep A3 and B in one function so that it can be swapped).** A1 and A2
stay on the chart bar's open. Then every 1-minute sub-bar of the chart bar (rows of `<PAIR>_1` with `t_open`
in `[t_open[j], t_close[j])`, `hrd.sub_bars`), in time order: A3 at its own open (for a trade filled in A2
the first sub-bar's open is the fill itself), then B on its own open / high / low / close; the trailing
state carries over. C and D stay on the chart bar's close. Chart "1": 'mag' == 'tv'.

---------------------------------------------------------------------------------------------------

## 7. The script run at the close of bar `j` (step C), in the Pine's order

State it reads: the position after A and B (`pos` in 0 / +1 / -1, `qty`, `e`), `cash` (10,000 + the closed
trades' P/L after costs - the entry cost of the open trade), `prevPos` (`strategy.position_size[1]`: the
position at the previous bar's close) and its one `var`, `entryBar` (`dsEntryBar`). `c = close[j]`,
`equity = cash + pos * qty * (c - e)` (`strategy.equity`, F10).

**C1. Exit geometry (L728-736), from this bar.** Operation order to the letter (float64):
```
a = atr[j]                                             # ta.atr(dsAtrLen), may be na only far before the window
Points mode:  slT = dsSlPoints ;  tpT = dsTpPoints ;  actT = dsTrActPts ;  dstT = max(dsTrPts, 1.0)
ATR mode:     slT = nz(dsSlAtr * a / mintick)          # na -> 0
              tpT = slT * dsTpR                        # NOT used in Points mode
              actT = nz(dsTrActAtr * a / mintick)
              dstT = max(nz(dsTrDstAtr * a / mintick), 1.0)
stopDist = slT * mintick                               # dsStopDist; dsLoss / dsProfit exist iff slT > 0 / tpT > 0
```
**C2. Bars in trade (L771-777).**
```
if pos != 0 and (prevPos == 0 or sign(pos) != sign(prevPos)):  entryBar = j
if pos == 0:                                                   entryBar = na
barsIn = j - entryBar  if pos != 0 and entryBar is not na  else na
timeUp = dsTimeStop > 0 and barsIn is not na and barsIn >= dsTimeStop
```
Implement it literally. With this script's orders `entryBar` always equals the fill bar of the open trade (a
fresh fill has `prevPos == 0`, a reversal changes the sign, and two trades of the same side can never be
open at two consecutive closes): assert `entryBar == entry_bar` whenever `pos != 0`. With `dsTimeStop = N` a
trade filled in bar k gets its close order at the close of bar k+N and leaves at the open of bar k+N+1. A
trade that opens and closes inside one bar is never seen here.

**C3. Quantity (L738-746, 780-781)** = `dsQty(stopDist)` with this `equity` and this `c` (section 9), then
```
qtyOk = q > 0 and (dsQtyMode == "Fixed" or stopDist > 0) and (dsExitMode == "Points" or a is not na)
```
**C4. Decisions (L760-768, 782-786).** `rb = rawBuy[j]`, `rs = rawSell[j]` of the chosen trigger.
```
goLong     = (rs if inv else rb) and dsSides != "Short only"
goShort    = (rb if inv else rs) and dsSides != "Long only"
longKeep   = keepSell[j] if inv else keepBuy[j]
shortKeep  = keepBuy[j]  if inv else keepSell[j]
useZoneExit = dsZoneExit and dsTrigger != "New signal"
enterLong  = goLong  and qtyOk and (pos == 0 or (pos < 0 and dsReverse))
enterShort = goShort and qtyOk and (pos == 0 or (pos > 0 and dsReverse)) and not enterLong
```
**C5. Orders (L788-813).**
```
if enterLong:    place order d = +1  (sig = -1 if inv else +1)
elif enterShort: place order d = -1  (sig = +1 if inv else -1)
else:                                                    # L805: only when no entry is placed
    if pos > 0:  opp = (rb if inv else rs) ;  zone = useZoneExit and not longKeep
    if pos < 0:  opp = (rs if inv else rb) ;  zone = useZoneExit and not shortKeep
    if pos != 0 and (opp or zone or timeUp):
        close_req = 'opp' if opp else 'zone' if zone else 'time'       # the comment's priority, L811 / L813
prevPos = pos
```
`place`: the order carries `qty = q`, `slT`, `tpT`, `actT`, `dstT` of C1, `dsUseTrail`, `capf` (section 9).
If `dsUseTrail` is false and `slT <= 0` and `tpT <= 0` the trade has no bracket at all (L795 / L803).

To keep exactly:
- The ticks and the quantity are those of the PLACING bar (its ATR, its equity, its close); the fill is one
  bar later, at another price. The bracket is measured from the fill.
- `opp` reads the RAW trigger: it ignores `dsSides` and `qtyOk`. So an opposite trigger closes the trade
  ('opp') whenever it does not reverse it: `dsReverse` off, or the other side switched off by `dsSides`, or
  `qtyOk` false.
- A trigger on the side of the trade already open does nothing: no order, no close, no new bracket.
- A reversal run places no `strategy.close`: the entry order itself closes the open trade (kind 'reverse').
- The close reasons are tested on every bar while a trade is open, the entry bar included: a trade whose
  keep permission is already false at the close of its fill bar leaves at the next open.
- With "Signal confirmed" the keep permission is `confBuy` / `confSell` (not `buyOk` / `sellOk`): a long
  opened by a BUY signal is closed ('zone') when a new SELL signal replaces it, even if price is still
  high; if that SELL signal is confirmed on the same bar it is an opposite trigger instead ('reverse' /
  'opp').
- `equity` at a reversal run includes the open P/L of the trade about to be closed, at this close.

**D.** Bar-close equity `E[j] = cash + pos * qty * (c - e)`; exposure counts bars with `pos != 0` here.
Funnel counters in C (normal frame): `raw_long += rb`, `raw_short += rs`; `taken_long` / `taken_short` +=
an entry order placed from a BUY / SELL trigger; `zero_qty += 1` when `(goLong and (pos == 0 or (pos < 0
and dsReverse))) or (goShort and (pos == 0 or (pos > 0 and dsReverse)))` holds and `qtyOk` is false.

---------------------------------------------------------------------------------------------------

## 8. `inv` = "Trade direction: Inverted" (`dsInv`), line by line, and against INVERT_SPEC.md

| Pine | what it does | replica |
|---|---|---|
| L699 `dsDirection`, L760 `dsInv = dsDirection == "Inverted"` | the input (existed before Update 1; default "Follow the filter") | `inv` |
| L749-759 triggers, L764-765 `dsBuyKeep` / `dsSellKeep` | never read `dsInv`: the filter and the triggers stay in the normal frame (M1) | `P` is the same for both directions |
| L761-762 `dsGoLong = (dsInv ? dsRawSell : dsRawBuy) and dsSides != "Short only"` (and `dsGoShort`) | the trigger pair is swapped BEFORE the `Sides` test: a BUY trigger opens "DS Short", a SELL trigger "DS Long"; `Sides` restricts the real order (M5) | C4 |
| L766-767 `dsLongKeep = dsInv ? dsSellKeep : dsBuyKeep` (and `dsShortKeep`) | a real long was opened by a SELL trigger, so it lives on the SELL permission | C4 |
| L785-786 `dsEnterLong` / `dsEnterShort` | read the REAL position against the swapped trigger = the normal decision on the mirrored position (M1) | C4 |
| L789-803 | market orders on the real side with the real side's id; `loss`, `profit`, `trail_points`, `trail_offset` are the SAME tick values for either side (M2, M3) | 6.2 with the real `d` |
| L806-807 `dsCloseLongOpp = dsLong and (dsInv ? dsRawBuy : dsRawSell)` (and Short) | the opposite trigger of the mirrored frame | C5 |
| L738-746 `dsQty`, L771-777 bars in trade | no side in them: the real trade's stop distance, the real trade's bars (M4) | C2, C3 |

**How the bracket is "mirrored": the Pine does not mirror any price.** There is no reference price and no
`2R - S` anywhere. The exit is a set of side-agnostic tick distances that TradingView applies to the fill
price of whichever trade is opened: long `SL = fill - loss`, `TP = fill + profit`; short `SL = fill + loss`,
`TP = fill - profit`; the trail arms at `fill +/- trail_points` and follows at `trail_offset`. Because a
normal and an inverted entry from the same trigger are both market orders filled at the same next open
(slippage 0), the result EQUALS INVERT_SPEC's M3 mirror about `R` = the fill price (`stop' = 2R - S`,
`limit' = 2R - T`), with the stop distance still the stop distance and the target distance still the target
distance. M2's stop <-> limit entry swap has nothing to convert (market entries only). So it is the Update 1
definition, reached by re-anchoring, not by a mirroring formula.

Two things that are NOT an exact mirror, both by design:
- The one literal deviation from M1: `dsEnterShort` ends with `and not dsEnterLong` (L786), a tie-break for
  the REAL long, where a strict mirror would favour the normal BUY. Unreachable (`rawBuy` and `rawSell` are
  never both true, section 4).
- The inverted run is not the mirrored trade list in general: a 1 ATR stop / 3 R target long becomes a short
  with the stop above, so trades end elsewhere, equity differs, quantities differ (Risk %), and a trade
  still open in one mode may be closed in the other when the next trigger comes.

There is no other reverse option in this script and no pre-filter flip. `dsSides` is not a reverse option.
The filter's `fgfAllowBuy` / `fgfAllowSell` stay in the normal frame (they choose the zone; "New signal"
ignores them).

Properties (stage 2 self-checks, stage 3 tests):
- P1, exact mirror. With a symmetric bracket and nothing that reads the sign of the P/L (`dsTpR = 1` in ATR
  mode or `dsTpPoints == dsSlPoints` in Points mode, `dsUseTrail` False, `dsQtyMode` "Fixed" with a small
  `dsFixedQty` such as 0.01, `dsCapMargin` False, `dsSides` "Both", cost 'tv'; any trigger, `dsZoneExit`,
  `dsReverse`, `dsTimeStop`): `inv` True gives the trade list of `inv` False with `dir` negated, `sig`
  equal, `pnl`, `pnl_gross` and `r_mult` negated, 'sl' <-> 'tp' swapped, `sl_px` <-> `tp_px` swapped,
  `eq_before - 10000` negated, and every bar, entry / exit price, quantity, flag and other kind equal.
- P2, single decisions: from the same state with the position negated, the order placed with `inv` True is
  the order placed with `inv` False on the other side: same bar, same quantity, same ticks; a close request
  has the same kind.
- P3: the first trade of a run has the same entry bar, entry price and quantity with `inv` False and True,
  opposite `dir` (default inputs).
- P4: `fgfOn` False: all six trigger arrays False, no trade, `net_pct` 0, both directions (the header's
  "nothing trades").
- P5 (`Sides` = the real orders): "Long only": every trade has `dir = +1`; normal: every `sig = +1`;
  inverted: every `sig = -1`; no 'reverse' exit, the opposite trigger gives 'opp'. "Short only" alike.
- P6: "Signal confirmed": at every trigger bar `sig == sigDir`; `dir == sig` normal, `dir == -sig` inverted
  (the header's "never trades against the signal / with Inverted it always does"). Results do not depend on
  `fgfAgainst`.
- P7: "New signal": results do not depend on `fgfBandAtr`, `fgfLvMode`, `fgfAgainst`, `fgfAllowBuy`,
  `fgfAllowSell`, `fgfLast`, `dsZoneExit`.
- P8: "Zone start" with `dsZoneExit` True, `dsReverse` True, `dsSides` "Both" and `zero_qty == 0`: EVERY
  trigger places an entry (`trades == raw_long + raw_short - orders_unfilled_end`), in both directions (a
  same-side edge needs the zone to have ended first, and then the trade was already closed).
- P9: `dsReverse` False: no 'reverse' exit.

---------------------------------------------------------------------------------------------------

## 9. Sizing, money, costs, margin

`dsQty(stopDist)` (L738-746), in this order, float64, evaluated left to right as written:
```
q = dsFixedQty
if dsQtyMode == "Risk %":
    stopCash = stopDist * pointvalue                                   # syminfo.pointvalue = 1.0
    q = equity * dsRiskPct / 100.0 / stopCash  if stopCash > 0  else 0.0
q0 = q
q = min(q, dsMaxQty) ;  q1 = q
if dsCapMargin and dsMarginPct > 0:
    q = min(q, equity / (c * pointvalue * dsMarginPct / 100.0))        # the INPUT dsMarginPct, this bar's close
q2 = q
q = floor(q / dsQtyStep + 1e-9) * dsQtyStep                            # dsQtyStep > 0 always (minval 0.000001)
capf = 2 if q2 < q1 else 1 if q1 < q0 else 0                           # which cap set it (diagnostic)
```
The floor formula is NOT gvl's (`floor((q + 1e-9 * step) / step) * step`): use this one. `equity <= 0` gives
`q <= 0`, so no entry (`qtyOk`). The quantity is fixed at placement.

What the defaults do (probe, unverified; 10,000 account, stop 1 x ATR(14)):
- Gold: risk sizing asks for `50 / ATR` oz: about 210 on "1", 85 on "5", 21 on "60"; `dsMaxQty = 50` caps
  it on 99 % of the trigger candles of XAU 1, 83 % of XAU 5, 30 % of XAU 15, 2 % of XAU 30, none above. A
  capped trade risks less than 0.5 % (median 0.14 % on XAU 1). Notional about 6 accounts where capped.
- BTC: `50 / ATR` coins (0.1 on "60"); notional about 9 accounts on "1", 3.4 on "5", 0.9 on "60", 0.4 on
  "240". `dsMaxQty` never binds at the initial equity; the script's margin cap (100 accounts of notional)
  binds on 0.2 % of the BTC 1 trigger candles and nowhere else.

Money model:
- `cash` starts at 10,000. Cost of a fill = `qty * (fixed + fraction * fill_px)`, charged when the fill
  happens (entry and exit; a reversal = the closing fill and the opening fill), with the pairs `(fixed,
  fraction)` of `gvl.COSTS`: 'tv' `(0, 0)` both pairs; 'ours' XAU `(0.15, 0)`, BTC `(0.10, 0.0002)`;
  'stress' XAU `(0.26, 0)`, BTC `(0.11, 0.00035)`. Fill prices never move (slippage 0; the stress tick is a
  cost). Costs reduce `cash`, so they change later quantities.
- `pnl_gross = dir * qty * (exit_px - entry_px)`; `pnl = pnl_gross - entry cost - exit cost`.
- `eq_before` of a trade = `cash` just before its entry fill (after the closing leg of a reversal, before
  its own entry cost).
- R: `sl_dist` = `stopDist` of the placing bar; `r_mult = pnl / (sl_dist * qty)` (NaN without a stop).
- No floor at zero; an account that cannot afford one `dsQtyStep` simply stops trading (`zero_qty`).

**F9, margin.** TradingView with Margin 1 % refuses an entry whose `qty * fill price * 1 %` exceeds the
available funds and margin-calls a position whose required margin exceeds the equity. The script's own cap
keeps `qty * close * dsMarginPct %` within the equity of the placing bar, so neither can happen unless that
cap binds (then the fill at a higher open may be refused, and the first adverse tick is a margin call) or a
trade loses most of the account in one gap. Replica: no refusal, no margin call. Count `qty_capped_margin`
(entry fills with `capf == 2`), `qty_capped_max` (`capf == 1`), `margin_over` (entry fills with `qty *
entry_px * 0.01 > eq_before`: the 1 % of `strategy()`, not the input) and `max_notional_x` (largest `qty *
entry_px / eq_before`). A result with `qty_capped_margin` above 1 % of its trades is flagged in the notes.

---------------------------------------------------------------------------------------------------

## 10. Assumptions (one each; both builders implement exactly these)

| id | assumption | why |
|---|---|---|
| F1 | One script run per bar, at its close; no other run. | Both `calc_on_*` flags are false; documented behaviour of history bars. |
| F2 | A market order (entry, reversal, `strategy.close`) fills at the next bar's open, raw price. | `process_orders_on_close=false`, slippage 0; SPEC_AH rule 1. |
| F3 | The bracket is live from the entry fill, on the fill bar for the rest of its path; levels = fill price -/+ the ticks of the PLACING bar; it stays in force until the trade closes although `strategy.exit` is called only once, with the entry. | `strategy.exit` is called with the entry order and waits for it; `loss` / `profit` / `trail_points` are relative to the fill; an order lives until filled or cancelled. SPEC_AH rule 3; the Pine header says "they protect the trade from the fill bar on". |
| F4 | Intrabar path = SPEC_AH rule 4 (tie: low first); the first level reached wins; a level already passed at the open fills at the open (stop and target alike); a target fills on touch. | Documented broker emulator. |
| F5 | Trailing stop as SWEEP_AH_SPEC section 1: armed when price reaches fill + `trail_points` ticks (0 = at the fill), then stop = best price - `trail_offset` ticks, moving only in favour; with `loss`, the nearer stop is the one hit; the target is tested before arming. | The verified reading of apex / hrd / xpw / gvl. |
| F6 | At an open: the script's market order first (the close, or the entry / reversal), then the gap test of a trade still open. | A `strategy.close` and a stop gapped through at the same open give the same price and the same flat account: only the label differs ('zone' rather than 'sl'). TradingView's order is not documented; deterministic choice, as gvl G10. |
| F7 | A market `strategy.entry` against the open position closes it at the open (kind 'reverse') and opens exactly its own `qty`; the closed trade's bracket is gone; the new bracket is live from that open. | Documented reversal of `strategy.entry`; `pyramiding = 0` only limits same-side entries. |
| F8 | No rounding: tick distances stay fractional, levels are not rounded to the tick, quantities only by `dsQtyStep`. XAU prices keep their 3 decimals. | As apex / hrd / xpw23 (T12) / gvl (G12). At most half a tick per level. |
| F9 | TradingView's margin rule (1 %) is not modelled: no entry refused, no margin call. Counters. | Section 9: the script's own cap makes it bind only where `capf == 2`; the liquidation rule's timing cannot be checked here. |
| F10 | `strategy.equity` = `cash` + open P/L at the close (costs paid included); `strategy.position_size[1]` = the position at the previous bar's close. | SPEC_AH rule 6. |
| F11 | Trading starts flat with clean variables at the first window bar, but the triggers of that bar use the real previous bar of the filter; orders of the last window bar do not fill; 'end' at the last close. | REPLICA_SPEC; SPEC_AH rule 5. On TradingView the first loaded bar is another one anyway. |
| F12 | A `strategy.exit` whose `loss`, `profit` and trail are all absent is not called; `strategy.cancel` of an order that does not exist does nothing: the trade has no bracket. | Code L792-795; only reachable in Points mode with zeros, or `dsTpR = 0` with a zero stop. |
| F13 | In v6 a `bool[1]` on the first bar of the data is false. | v6 rule (bool is never na). It never matters: nothing is armed on the first rows of a file. |

Not an assumption, a fact of this script: an exit is never re-sent with the same id for an open trade; a
stop and a target touched in one bar are settled by F4; `na` prices only mean "no stop" / "no target" (F12).

---------------------------------------------------------------------------------------------------

## 11. What cannot be reproduced, and what the replica does instead

- TradingView itself: nothing can be compiled or backtested here. F3, F6, F7, F9 are readings of its engine.
- TradingView's margin calls and refused entries (F9): ignored, counted.
- Seconds charts and seconds zones: no data below 1 minute. Nothing in the defaults needs them (zone 5 "1"
  and zone 6 "2" are minutes, both off).
- Bars of another broker: gold bars are 18:00-17:00 New York sessions with 120 / 240-minute bars anchored at
  18:00 (also the "480" / "960" bars `fgf` builds from 1-minute bars); BTC bars are on a UTC grid. Another
  feed changes the filter candles and so every trigger.
- The header's TEST RESULTS (2026-11-07): other feeds and windows (OANDA / VANTAGE gold, Bitfinex 2018-2019)
  and another replica. Not a target for these windows.
- `fgf.py`'s own residuals (reconcile_fgf.md): TDI float ties on 1-minute and 5-minute filter, parent or
  zone timeframes; the `""` timeframe inside the nested request.
- TradingView's rounding of prices to the tick and of quantities to the symbol's lot step (the script's
  0.001 step may be coarser or finer than the broker's), its cap of about 9,000 trades per report (the
  default takes about 30,000 trades on BTC 1, 15,600 on BTC 5, 13,500 on XAU 1), the bars a plan can load.
- Bar Magnifier inside TradingView: path 'mag' is OUR 1-minute walk of the bracket, with decisions, market
  fills and `strategy.close` on the chart bars.
- Live trading: the run is still once per bar close, but the fill is the first tick of the next bar with a
  spread; a parent timeframe above the filter timeframe repaints live (header, REPAINTING).

---------------------------------------------------------------------------------------------------

## 12. Interface, trade record, summary

    prepare(pair, chart_tf, params=None) -> P
    simulate(P, x=None) -> R
    trades(P, R) -> DataFrame
    summary(P, R) -> dict
    run(pair, chart_tf, params=None) -> (trades, summary)        # splits one dict into 3.1 / 3.2 keys

`DEFAULTS` = every Pine default of 3.1 and 3.2 (so `fgfOn = True`, "Zone start", "Follow the filter"), plus
the replica controls (`path` 'tv', `cost` 'tv', `inv` False). `INITIAL_CAPITAL = 10000.0`. One numba kernel
for A, B, C, D over the window bars (no Python object in the loop). Speed: one `simulate` on BTC "1"
(1,039,430 bars) well under 1 s after compilation (probe: 0.04 s); first `prepare` under 2 minutes; under
3 GB.

`KINDS = ['', 'sl', 'tp', 'trail', 'reverse', 'opp', 'zone', 'time', 'end']`.

**Trades**, one row per entry fill, in fill order:

| column | content |
|---|---|
| `dir` | REAL side, +1 / -1 |
| `sig` | normal-frame side of the trigger (+1 BUY trigger); `= dir` with `inv` off, `-dir` with it on |
| `sig_bar`, `entry_bar`, `exit_bar` | file rows: where the order was placed (always `entry_bar - 1`), where it filled, where the trade closed |
| `entry_time`, `exit_time` | `t_open` of the fill bar / of the exit bar (chart bars, also in 'mag'); 'end': `t_close` |
| `entry_px`, `qty`, `exit_px` | fill price, units, exit fill price |
| `exit_kind` | 'sl', 'tp', 'trail' (bracket); 'reverse' (opposite entry, `dsReverse`); 'opp' (`strategy.close`, "Opposite signal"); 'zone' ("Zone ended"); 'time' ("Time stop"); 'end' |
| `pnl`, `pnl_gross`, `costs`, `eq_before` | section 9 |
| `sl_dist`, `sl_px`, `tp_px`, `r_mult` | stop distance of the placing bar, the levels at the fill (NaN if absent), `pnl / (sl_dist * qty)` |
| `rev` | True when the fill that opened the trade also closed the previous one |
| `capf` | 0, 1 (`dsMaxQty` set the quantity), 2 (the margin cap did) |

**Summary.** The common fields exactly as `hrd.summary_fast` + `hrd.extra_fields` compute them, with
`INITIAL_CAPITAL = 10000`: `start, end, bars, trades, net_pct, pf, win_pct, max_dd_pct, max_dd_init_pct,
long, short, raw_long, raw_short, blocked_long, blocked_short, half1_pct, half2_pct, exposure,
final_equity, exit_sl, exit_tp, exit_trail, exit_reverse, exit_opp, exit_zone, exit_time, exit_end,
zero_length, h1r_pct, h2r_pct, h1_trades, h2_trades, avg_bars_held, costs`.
- `long` / `short`: real sides. `raw_long` / `raw_short`: window bars with `rawBuy` / `rawSell` of the
  chosen trigger (normal frame). `blocked_long = blocked_short = 0` always: the filter is the signal, it
  cannot block its own trigger (kept for the common table).
- Equity curve for `max_dd_pct` / `max_dd_init_pct`: 10,000, then `E[0] .. E[n-2]`, then the final equity
  (after the 'end' close and its cost) in place of `E[n-1]`; running peak starts at 10,000. `half1_pct` /
  `half2_pct` from `E[mid_j]` (10,000 if `mid_j < 0`), as `hrd`.
- Fair halves: trades ENTERED in each half by `entry_time <= mid` / `> mid`, `100 * (prod(1 + pnl /
  eq_before) - 1)`, 0 for an empty half. `avg_bars_held = mean(exit_bar - entry_bar)`; `zero_length` =
  trades with `entry_bar == exit_bar`.

Fields of this strategy: `net_r`, `h1_r`, `h2_r` (sum of `r_mult`, NaN rows skipped: all trades / the trades
entered in each half; the Pine header's unit); `trig_zone_buy`, `trig_zone_sell`, `trig_conf_buy`,
`trig_conf_sell`, `trig_new_buy`, `trig_new_sell` (from `P`); `taken_long`, `taken_short`, `orders_placed`
(their sum), `orders_unfilled_end` (1 if the run of the last window bar placed an entry order, else 0),
`zero_qty`, `qty_capped_max`, `qty_capped_margin`, `margin_over`, `max_notional_x`.

Comparing A and B: bars, kinds, flags and counts exactly; prices, quantities, P/L and equity fields to a
relative 1e-9.

---------------------------------------------------------------------------------------------------

## 13. Builders: outputs, self-checks, sanity numbers

- Saved trade lists (cost 'tv', path 'tv', default inputs): `$W/out/fgds_<a|b>_<PAIR>_<TF>.parquet` for BTC
  60, BTC 5, XAU 60, XAU 15, one file per cell with a column `variant` in `on_normal`, `on_inv` (the default
  "Zone start"), `on_normal_conf`, `on_inv_conf` ("Signal confirmed"), `on_normal_new`, `on_inv_new` ("New
  signal"). The filter-off variants `off_normal`, `off_inv` have no rows: record their summaries (and all
  the others) in `$W/out/fgds_<a|b>_summaries.json` instead.
- `fgfOn` False (replaces "reproduces the original"): P4, plus kernel tests on INJECTED arrays, independent
  of `fgf`: build small `P`-like inputs by hand (10 to 40 bars of OHLC, ATR, `rawBuy`, `rawSell`, `keepBuy`,
  `keepSell`) and check the kernel against the bar-by-bar expectation written out in the test, for: an entry
  and its stop in the same bar; a gap through the stop; a target; a reversal; an 'opp' close with
  `dsReverse` off; a 'zone' close on the bar after the fill; a 'time' close; a trigger on the side already
  held (ignored); a trigger with `qtyOk` false while a trade of the other side is open ('opp'); `dsSides`.
- Hand traces from real data with the bars printed, at least 3 trades each: 'sl', 'tp', a same-bar entry and
  exit, 'trail' (`dsUseTrail` with `dsTpR = 0`), 'reverse', 'opp' (`dsReverse` False), 'zone', 'time'
  (`dsTimeStop` 3), 'end'; a "Signal confirmed" re-trigger by `newSig` while flat; a "New signal" entry with
  price on the wrong side of the level; sizing against a direct evaluation of `dsQty` (a gold trade capped at
  50, a BTC trade not capped, a `capf == 2` trade on BTC 1 if one exists).
- The asserts of section 4 (never both triggers; the `confBuy` identity) and of sections 6-7 (at most one
  thing to fill at an open; a reversal order meets the opposite side; `entryBar == entry_bar`).
- P1 to P9 of section 8; the mirror property on 5 single decisions (P2).
- Sanity numbers (probe, plain single implementation, unverified, order of magnitude only; default inputs,
  cost 'tv', path 'tv', direction normal). Trades:

  | cell | "Zone start" | "Signal confirmed" | "New signal" |
  |---|---|---|---|
  | BTC 1 / 5 / 15 / 30 | 29,965 / 15,568 / 9,756 / 6,769 | 9,709 / 4,838 / 2,855 / 1,738 | 3,800 / 3,687 / 3,163 / 2,600 |
  | BTC 60 / 120 / 240 | 3,233 / 2,242 / 1,465 | 445 / 295 / 166 | 2,060 / 1,585 / 1,239 |
  | XAU 1 / 5 / 15 / 30 | 13,545 / 6,805 / 4,257 / 2,995 | 3,953 / 1,908 / 1,117 / 701 | 1,697 / 1,629 / 1,401 / 1,179 |
  | XAU 60 / 120 / 240 | 1,473 / 1,041 / 703 | 171 / 115 / 74 | 945 / 747 / 575 |

  "Zone start" trades = triggers (P8), minus one on the gold cells below 240 minutes, whose last window bar
  carries a trigger. BTC 60 "Zone start": exits sl 1,105 / tp 146 / reverse 803 / zone 1,178 / end 1; 558
  trades open and close in one bar; win rate about 30 %; inverted: the same 3,233 entries, sl 1,188 / tp 200
  / reverse 425 / zone 1,420. "Signal confirmed" has no 'reverse' at the defaults (the opposite signal is
  never confirmed on the bar it appears when chart = filter timeframe). "New signal" takes about half of
  the signals on BTC 60 (a same-side signal while in the trade is ignored). With cost 'ours' the default
  "Zone start" account is ruined on BTC 1 (about 2,400 trades, then `zero_qty` about 27,600), BTC 5 (5,200 /
  10,300) and XAU 5 (4,700 / 2,100), and loses 99.8 % on XAU 15.

Additions for stage 3 (beyond REPLICA_SPEC):
- In `out/inv_fgds_<PAIR>_<TF>.json` keep `runs[...]` = the 16 keys with the defaults ("Zone start"); the 8
  filter-off keys are zero-trade rows by construction (say so in the table, do not drop them); add
  `runs_conf[...]` and `runs_new[...]` (the same 16 with the other two triggers). Print `zero_qty`,
  `qty_capped_max`, `qty_capped_margin` next to every row.
- Tests: P1 (three triggers, with and without `dsZoneExit`, `dsReverse`, a time stop; ATR and Points mode),
  P2 to P9; 'mag' on chart "1" == 'tv'; 'mag' with one fake sub-bar per chart bar == 'tv'; the header
  properties: (i) every 'zone' exit at bar x of a trade filled at bar k: the keep permission of the trigger
  that opened it (`keepBuy` for `sig = +1`, `keepSell` for `sig = -1`, whatever `dir` is) is false at bar
  x-1 and true on every bar k .. x-2; (ii) `sl_px` / `tp_px` of every trade = `entry_px -/+ dir * ticks *
  0.01` with the ticks of `sig_bar`; (iii) `qty` of every trade = `dsQty` evaluated on `sig_bar` with the
  equity recomputed from the trade list and the closes; (iv) every 'time' exit at bar x has `x - entry_bar
  == dsTimeStop + 1`.
- The random reconcile settings must draw the three triggers, both directions, `dsSides`, `dsZoneExit`,
  `dsReverse`, `dsUseTrail`, `dsTimeStop > 0`, both `dsExitMode`s (with `dsSlPoints` 0 and `dsTpPoints` 0
  among them), "Fixed" quantity, `dsCapMargin` off, and filter settings outside the grid: `fgfLast`
  "Candles" / "Minutes", `fgfCheck` "Candle open", `fgfAgainst` off, `fgfAllowBuy` off, `fgfTf` "" and "240".

---------------------------------------------------------------------------------------------------

## 14. Calibration grid proposal (for `$W/CALIB_SPEC.md`)

Scored as CALIB_SPEC says (path 'mag', cost 'ours'). **21,600 settings per cell**, the same in every cell:
108 `prepare` settings; per `prepare` setting 96 `simulate` settings for each of "Zone start" and "Signal
confirmed", and, on the 18 `prepare` settings that differ for it, 48 for "New signal".

| # | dimension (Pine names) | values | kind | side | default |
|---|---|---|---|---|---|
| 1 | `fgfTf` (moves the parent and the zones with it: `fgfParentTf = T`, `fgfZTf1 / 2 / 3 = T / 2T / 4T`) | "15" (15 / 30 / 60), "60" (60 / 120 / 240), "240" (240 / 480 / 960) | ordinal | prepare | "60" |
| 2 | `fgfBurstAtr` | 0.25, 0.5, 1.0 | ordinal | prepare | 0.5 |
| 3 | `fgfBandAtr` | 0.0, 0.25, 0.75 (None for "New signal") | ordinal | prepare | 0.25 |
| 4 | `fgfLvMode` | "Entry price", "Signal close" (None for "New signal") | categorical | prepare | "Entry price" |
| 5 | `fgfUseZones` | True, False | categorical | prepare | True |
| 6 | `dsTrigger` | "Zone start", "Signal confirmed", "New signal" | categorical | simulate | "Zone start" |
| 7 | `inv` (`dsDirection`) | False, True | categorical (the direction control) | simulate | False |
| 8 | `dsZoneExit` | True, False (None for "New signal") | categorical | simulate | True |
| 9 | `dsReverse` | True, False | categorical | simulate | True |
| 10 | `dsSlAtr` | 0.5, 1.0, 2.0 | ordinal | simulate | 1.0 |
| 11 | `exitStyle` = (`dsTpR`, `dsUseTrail`) | 'tp3' = (3.0, False); 'tp1.5' = (1.5, False); 'none' = (0.0, False); 'trail' = (0.0, True with the cell's pair below) | categorical | simulate | 'tp3' |

Count: "Zone start" and "Signal confirmed": 3 x 3 x 3 x 2 x 2 = 108 filter settings x 2 triggers x (2 x 2 x
2 x 3 x 4 = 96) = 20,736. "New signal": 3 x 3 x 2 = 18 filter settings (dimensions 3 and 4 cannot change
it: None) x (2 x 2 x 3 x 4 = 48; dimension 8 is None) = 864. Total **21,600**. The script default is one
grid point: "60", 0.5, 0.25, "Entry price", zones on, "Zone start", normal, zone exit on, reverse on, 1.0,
'tp3'. Everything else at the script defaults (`fgfLast` "Until next signal", `fgfCheck` "Tick",
`fgfAgainst` on, both sides allowed, the signal's other inputs, `dsSides` "Both", `dsExitMode` "ATR",
`dsAtrLen` 14, `dsTimeStop` 0, Risk 0.5 %, `dsMaxQty` 50, margin cap on). `exitStyle` is one categorical
dimension (its members are whole exit rules), with the Pine inputs it sets written as extra columns that do
not start with `p_`; the same for the parent / zone timeframes of dimension 1.

**The filter dimension {off, on} of REPLICA_SPEC does not exist here**: off = no trade at all, in every
cell; the script has no blocked-signal close. The filter is on in all 21,600 rows.

Trailing (`exitStyle` 'trail'): `dsTrActAtr = 2d`, `dsTrDstAtr = d`, with `d` the smallest of {1, 1.75, 2.5,
3.5, 5, 6.5} for which `d x ATR(14) / close` at the 10th percentile of the window is at least the floor
(0.1 % BTC, 0.05 % gold). The percentiles were recomputed for this brief (probe) and agree with SPEC_gvl /
SPEC_danny (same ATR):

| cell | BTC 1 | BTC 5 | BTC 15 - 240 | XAU 1 | XAU 5 | XAU 15 - 240 |
|---|---|---|---|---|---|---|
| 10th percentile of ATR(14) / close, % | 0.0157 | 0.0574 | 0.125 / 0.198 / 0.318 / 0.512 / 0.826 | 0.0101 | 0.0290 | 0.0599 / 0.094 / 0.145 / 0.203 / 0.311 |
| `d` | 6.5 | 1.75 | 1 | 5 | 1.75 | 1 |
| (`dsTrActAtr`, `dsTrDstAtr`) | (13, 6.5) | (3.5, 1.75) | (2, 1) | (10, 5) | (3.5, 1.75) | (2, 1) |

The script's own default trail (2.0, 0.5) is below the floor on the charts of 30 minutes and less; trailing
is off by default, so the default is still a grid point. On the 1-minute charts the floor makes the trail nearly inert ('trail'
is then close to 'none').

Why these dimensions (probe: share of trigger bars a setting has in common with the default setting's,
"overlap", on BTC 60 / XAU 60 / BTC 15 / XAU 240):
- The three triggers are three strategies (fact 6): 3,233 / 445 / 3,800 trigger bars on BTC 60.
- The filter timeframe moves everything (overlap of the zone starts 0.06 to 0.11 for "15" and "240").
- The burst threshold sets how many signals exist (BTC 60: 6,120 / 3,800 / 1,302 signals at 0.25 / 0.5 /
  1.0; overlap 0.23 to 0.57).
- The band and the level decide where a zone starts (probed at band 0 / 0.5 / 1.0: price in a zone on 100 %
  / 46 % / 23 % of the BTC 60 bars against 83 % at 0.25; overlap 0.03 to 0.6; "Signal close": overlap 0.08
  to 0.27).
- The TDI trade-zone filter removes about 40 % of the signals (BTC 60: 6,473 without it).
- `dsZoneExit` and `dsReverse` change which triggers are taken and how trades end (BTC 60 default 3,233
  trades; 2,645 without the zone exit; 2,570 without reversals).
- **Left out although the header's earlier search names "permission"**: `fgfAgainst` off makes "Zone start"
  a near-copy of "Signal confirmed" (BTC 60: 445 trigger bars in both; they differ only by the `newSig`
  re-trigger), so it would add near-duplicate rows; `fgfLast` "Candles" 8 is close to the default (overlap
  0.9) and "Candles" 1 leaves "Signal confirmed" without a single trigger.
- **`fgfCheck` "Candle open" is left out**: on history it is the same decision one bar later.

Notes for the orchestrator:
- **Ruin and caps (fact 7).** Sizing stays the script's, so that the default is literally a grid point. With
  cost 'ours' many low-timeframe rows end with an account too small to trade: the trades stop (`zero_qty`),
  the second half has few trades, and the row leaves the 30-trades-per-half pool. That removes only losing
  rows from the candidates, but it also conditions the hold-out pool of rule C step 4 on first-half
  survival. On gold below 30 minutes `dsMaxQty = 50` turns risk sizing into a fixed 50 oz. If halves that
  do not depend on each other are preferred: run every row with `dsMaxQty = 1e12`, `dsCapMargin = False`,
  `dsQtyStep = 0.000001` (each trade then moves the account by 0.5 % x its net R whatever happened before;
  the account can no longer floor to zero) and report the script-sized default next to the grid. Keep
  `zero_qty`, `qty_capped_max`, `qty_capped_margin`, `net_r`, `h1_r`, `h2_r` in the rows either way.
- **Thin cells.** "Signal confirmed" is thin on the high timeframes: 74 default trades on XAU 240, 115 on
  XAU 120, 166 on BTC 240, 171 on XAU 60 (probe). Its stricter rows there (wide band, burst 1.0) cannot reach
  30 trades per half.
- **Identical rows.** With `dsZoneExit` on, "Signal confirmed" rarely reverses, so `dsReverse` True / False
  rows are often equal; rule C counts equal results once. They are not structural duplicates (band 0 with
  "Signal close", or a chart longer than the filter candle, confirms a signal on the bar it appears).
- **Memory / speed.** 108 `prepare` calls per cell, each one `fgf.fgf_permissions` call (about 1 s on BTC
  1); `fgf._FILTER` grows by one entry per (timeframe set, burst, zones, level) = 36 entries, about 55 MB
  each for the "15" set on BTC: clear that dict between filter settings if needed (it is a cache). The "240"
  set builds "480" and "960" bars from the 1-minute file once per process. One `simulate` on BTC 1 is about
  0.04 s (probe), so the 21,600 rows of BTC 1 fit CALIB_SPEC's 45 minutes with a wide margin.
- **Margin.** A file published from a pick keeps `margin_long = 1`, `margin_short = 1`; rows with
  `qty_capped_margin` above 1 % of their trades (possible with `dsSlAtr` 0.5 on the 1-minute charts) would
  meet TradingView's margin calls and are flagged, not trusted.
- Left out to stay in budget, in order of expected weight: `dsTimeStop` (the default trades already last
  2 to 6 bars on average, probe), `fgfMinAligned` 3, `fgfLast`, `fgfAgainst`, `dsSides`, `dsRiskPct`, a
  second trail, `fgfEntryDistAtr` (close to what `fgfLvMode` does), `fgfRsiLen` / `fgfFastLen`.
