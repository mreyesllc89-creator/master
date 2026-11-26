# SPEC_xpw23: XPW Orientation TDI v2.8 (S2 / S3 exits) + FGF, strategy brief for the two builders

Key `xpw23`. Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Common brief: `$W/REPLICA_SPEC.md` (read it first; this file is its stage 1 output).

Ground truth: `/home/user/master/xpw_orientation_tdi_v2.8_strategy_FGF.pine` at HEAD (1893 lines, Update 1
included). Line numbers below are that file's. The unfused original is
`/home/user/master/xpw_orientation_tdi_v2.8_strategy.pine`. Where this brief and the Pine disagree, the Pine
wins; say so in your notes.

Builders write `$W/xpw23_a.py` / `$W/xpw23_b.py` and `$W/xpw23_<a|b>_notes.md`. You may read `xpw.py`, `fgf.py`,
`engine.py`, `sweep_core.py`, `hrd.py`, `apex.py` and their notes (worked examples). You may not read the other
build of `xpw23`. Never edit an existing module. Probes used for this brief: `$W/xpw23_spec_tmp/` (`code.diff`,
`probe_atr.py`, `probe_sig.py`, `probe_grid.py`).

---------------------------------------------------------------------------------------------------------

## 1. What is shared with the trailing-TP file, and what is new (from the diff of the two Pine files)

Compared: this file against `/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine` (the file
`xpw.py` / `engine.py` replicate).

| part | this file | trailing-TP file | result |
|---|---|---|---|
| filter block, BEGIN..END FLASHGOLD DIRECTION FILTER | lines 547-1127 | 402-982 | byte-identical (`cmp`) |
| signal inputs `rsiLen` .. `cAgS` | 447-508 | 314-375 | byte-identical |
| `// PER-RUNG WINDOWS` .. `nShort := 0` (ladder, rung fetch, assembly, chart anchor, READ HERE, agreement, labels, `rungEvents`, `labelAction`, SIGNAL RUNGS, AGREE entries, the "both sides cancel" zeroing) | 1143-1626 | 1001-1484 | byte-identical, 484 lines, sha256 `4bab5288344d0426d22cc67b10e9d72866050edc02c45a3dc2fbb2adfb64aab7` on both |
| `reverseAll` (512 / 379), `tradeAgree` (514 / 381) | default false / true | same defaults | only the tooltips differ |

The signal section reads no variable declared in the parts that differ except `useLimit` (via `entryPx`,
which only feeds `putLbl`, drawing), `reverseAll`, `tradeAgree`, and `tickPx` / `tickBar` (label text only).
So the signal code is identical. **Use `xpw.xpw_signals` for the signals and `fgf.fgf_permissions` for the
filter. Do not reimplement either.**

Everything from line 1628 on is different code. `engine._run` cannot be reused. What differs:

1. `strategy()`: `default_qty_type=strategy.fixed, default_qty_value=0.1` (trailing-TP: 10% of equity).
2. Inputs: the trailing-TP inputs (`trailUnit`, `trailAct`, `trailOff`, `slOn`, `slDist`) are replaced by
   groups "S2. Exits" (518-529) and "S3. Sizing" (532-536). There is no `fgfBlkClose` input here.
3. Gate: here `goLong` / `goShort` are the signals BEFORE the filter (1655-1656). The filter is applied only
   where the order is placed (`if goLong and fgfBuyOk`, 1759; `if goShort and fgfSellOk`, 1770). There is no
   blocked-entry close and no `fgfLimOk` price test.
4. Limit prices are the plain candle `low` / `high` (the trailing-TP file clamps them to the zone edges and
   cancels on `not fgfBuyOk` / `moved`; none of that exists here).
5. Exits: `loss`, `profit`, `trail_points`, `trail_offset` in ticks from ATR or Points (1685-1693, 1745). A
   take profit exists. A time stop exists (1749-1752, `strategy.close` per entry id).
6. Sizing: every `strategy.entry` passes `qty = entryQty()` (1698-1705). `placeEntry` returns false when the
   quantity rounds to 0, and then nothing is placed and `room` is not reduced.
7. FGD funnel: raw = `goLong` / `goShort`, blocked = raw and not `fgfBuyOk` / `fgfSellOk` (1796-1799).

Fusion check (`git show 6c59b9f:...FGF.pine` against the unfused original, code after `strategy(`): the only
code differences are `max_bars_back=500`, the filter block and its plots, the two gates of item 3 and the FGD
plots. With `fgfOn` false, `fgfBuyOk = fgfSellOk = true` (line 953-954), so the fused script trades exactly
like the original. With `xpwInv` false the HEAD file is the pre-Update-1 file expression for expression.

---------------------------------------------------------------------------------------------------------

## 2. The `strategy()` call (line 444)

    strategy("XPW Orientation TDI v2.8 Strategy [Update 1]", shorttitle="XPW-OTDI8 S U1", overlay=false,
             max_labels_count=500, max_lines_count=500, max_bars_back=500, pyramiding=100,
             initial_capital=10000, default_qty_type=strategy.fixed, default_qty_value=0.1,
             process_orders_on_close=true, calc_on_every_tick=true)

| argument | meaning for the replica |
|---|---|
| title, shorttitle, `overlay`, `max_labels_count`, `max_lines_count` | display, ignored |
| `max_bars_back=500` | history buffer size; no effect (every series is warmed up from the start of the data) |
| `pyramiding=100` | up to 100 entries on one side. It can never bind: see T13 |
| `initial_capital=10000` | the account starts at 10,000 (NOT the 1,000,000 of SPEC_AH.md rule 7) |
| `default_qty_type=strategy.fixed`, `default_qty_value=0.1` | never used: every entry passes `qty` |
| `process_orders_on_close=true` | orders the script places on a bar are processed at THAT bar's close: market orders fill at the close; price orders (limit / stop entries) fill there only if the close satisfies them. SPEC_AH.md rule 1 (fill at the next open) does NOT apply; SPEC.md rules 1 and 3 do |
| `calc_on_every_tick=true` | live only. On history the script runs once per bar, at its close |
| not set: `calc_on_order_fills` | false: no extra script runs |
| not set: `commission_*`, `slippage` | 0. Cost mode 'tv' = no costs |
| not set: `margin_long`, `margin_short` | Pine v6 default 100%. NOT modelled: see T11 |
| not set: `close_entries_rule` | default "FIFO". The replica pairs each exit with its own entry: see T10 |
| not set: `backtest_fill_limits_assumption` | 0: a limit fills when price touches it |
| not set: `use_bar_magnifier` | false = path 'tv'; path 'mag' (stage 3) = Bar Magnifier on |

Symbol constants: `syminfo.mintick` 0.01, `syminfo.pointvalue` 1, both pairs.

---------------------------------------------------------------------------------------------------------

## 3. Inputs

### 3.1 SIGNAL inputs (parameters of `prepare`)

Passed to `xpw.xpw_signals` (its `DEFAULTS` keys):

| Pine name | default | note |
|---|---|---|
| `rsiLen`, `fastLen`, `bbLen` | 13, 2, 34 | TDI core used by `rungState` |
| `slowLen`, `bbMult` | 7, 1.6185 | accepted, NO effect on signals (`_slow`, `_up`, `_lo` are discarded in `rungState`; they only draw the pane) |
| `scaleWin`, `flatWin`, `areaLen`, `areaFrac`, `trendLen` | true, 20, 5, 0.45, 20 | structure |
| `sigRung` | "chart rung (*)" | or "every rung (1 Sec to 1 Month)" or a rung name |
| `lblRead` | true | READ HERE rung on top |
| `actL1`, `actL2`, `actS1`, `actS2`, `actDL`, `actDS`, `actEnd`, `actInf` | all "enter" | "off" / "enter" / "enter opposite" / "exit only" |
| `reverseAll` | false | the older reverse option: flips every "enter" label BEFORE the filter |
| `agreeOn` | false | only false is supported (`xpw.py` raises `NotImplementedError` on true); `agreeN`, `agreeMode`, `agreeScope`, `agreeInh`, `tradeAgree` are then inert |

Passed to `fgf.fgf_permissions` (its `DEFAULTS` keys): `fgfOn` (default true) and every other `fgf*` input of
the block. `fgfOn` false gives `buyOk = sellOk = True` on every bar.

Also `start`, `end` (window by `t_close`, default the pair's window of REPLICA_SPEC.md).

### 3.2 ORDER / EXIT inputs (parameters of `simulate`, dict `x`)

| Pine name | line | default | meaning |
|---|---|---|---|
| `tradeDir` | 511 | "Both" | "Both" / "Long only (buy only)" / "Short only (sell only)": the orders REALLY placed |
| `oppCloses` | 513 | true | one-side mode: the entry signal that is held back closes the position |
| `entryFill` | 537 | "Signal tick" | or "Limit at label price" (`useLimit`, 539). BOTH modes must be implemented |
| `limitBars` | 538 | 5 | bars a pending entry stays valid (1..500) |
| `maxOpen` | 540 | 20 | "Max open entries" (1..100) |
| `exitUnit` | 518 | "ATR" | or "Points" |
| `slPtsIn`, `tpPtsIn` | 519, 520 | 10000, 30000 | Points mode, ticks. 0 = off |
| `atrLen` | 521 | 14 | chart ATR length |
| `slAtrMult` | 522 | 3.0 | ATR mode stop, multiples of ATR. 0 = off |
| `tpRMult` | 523 | 1.0 | ATR mode target = this many times the STOP distance. 0 = off |
| `trailOn` | 524 | true | trailing stop |
| `trActPts`, `trDistPts` | 525, 526 | 15000, 10000 | Points mode trail activation / distance, ticks |
| `trActAtr`, `trDistAtr` | 527, 528 | 1.0, 0.75 | ATR mode trail activation / distance |
| `timeStop` | 529 | 0 | bars; 0 = off |
| `qtyMode` | 532 | "Fixed" | or "Risk" |
| `qtyFixed`, `riskPct`, `qtyMax`, `qtyStep` | 533-536 | 0.1, 1.0, 2.0, 0.01 | sizing |
| `xpwInv` (alias `inv`) | 1130 | false | Update 1, Inverted direction |
| replica: `path` | | 'tv' | 'mag' raises `NotImplementedError` until stage 3 |
| replica: `cost` | | 'tv' | 'tv' / 'ours' / 'stress' (section 7) |

Replica constants (not inputs): `mintick` 0.01, `pointvalue` 1.0, `initial_capital` 10000.0, `pyramiding` 100.
`atrLen` is a `simulate` input: cache the ATR array per length inside `P`. Validate as the Pine inputs do:
the option strings exactly as written above (else `ValueError`), `maxOpen` 1..100, `limitBars` 1..500,
`atrLen >= 1`, every other number `>= 0`.

### 3.3 Display or alert only (accepted, ignored)

`showTable`, `tblSize`, `tblPos`, `showLbl`, `lblSizeS`, `lblPrice`, `lblTick`, `shL1`, `cL1`, `shL2`, `cL2`,
`shS1`, `cS1`, `shS2`, `cS2`, `shDL`, `cDL`, `shDS`, `cDS`, `shEnd`, `cEnd`, `lblInfo`, `cInf`, `agreeLbl`,
`shAgL`, `cAgL`, `shAgS`, `cAgS`, and the filter's display inputs (`fgf._DISPLAY_KEYS`). An event exists whether
or not its label is shown. The script has no `alert()` call. Any other unknown key: raise `ValueError`.

---------------------------------------------------------------------------------------------------------

## 4. The logic, in order of execution on a chart bar

History: one script run per chart bar, at its close. `bar_index` = the row number of the bar in
`data/<PAIR>_<TF>.parquet` (use it in ids).

### 4.1 Signals (lines 1143-1626) = `xpw.xpw_signals(pair, chart_tf, start, end, params)`

Thirteen `request.security(..., lookahead_off)` calls (rungs M, W, D, 240, 60, 30, 15, 5, 1, 30S, 15S, 5S, 1S):
the rule of SPEC.md (the last rung bar with `t_close <=` the chart bar's `t_close`; seconds rungs have no data
= na). `var` state: `posA`, `shapeA`, `orientA`, `inhA`, `prevPosA`, `prevReadAt`, `voteA`, `prevLongN`,
`prevShortN`. All of it is inside `xpw.py`. Columns you need, per window bar:

- `nLong`, `nShort`: label counts AFTER the "both sides cancel" zeroing (1622-1626). Every use of `nLong` /
  `nShort` below is the zeroed value.
- `longSrc`, `shortSrc`: the raw lists (order = rung 0..12). `firstLong` / `firstShort` (1671-1676) come from
  the raw lists; they only feed comments.
- `exitL`, `exitS`, `exitLSrc`, `exitSSrc`: "exit only" rows. `exitL` = close longs.

Drop the other columns of the frame at once (the `pos_*`, `shape_*` string columns of a 1-minute chart are
several hundred MB). Reference counts with default inputs, full windows (probe; `raw` = bars with
`nLong > 0` / `nShort > 0`, `blocked` = of those, bars with `buyOk` / `sellOk` false):

| cell | bars | raw long / short | blocked long / short | labels long / short | both-cancel bars |
|---|---|---|---|---|---|
| BTC 60 | 17518 | 1841 / 1961 | 961 / 1070 | 1882 / 2004 | 70 |
| BTC 5 | 210155 | 12141 / 11369 | 7445 / 7323 | 12288 / 11501 | 439 |
| XAU 240 | 2246 | 273 / 258 | 151 / 141 | 275 / 269 | 9 |
| XAU 15 | 32935 | 2775 / 2525 | 1654 / 1470 | 2814 / 2585 | 85 |

Your `raw_*` / `blocked_*` summary fields must equal these with `tradeDir` "Both".

### 4.2 Filter = `fgf.fgf_permissions(pair, chart_tf, start, end, params)`

`buyOk` = `fgfBuyOk`, `sellOk` = `fgfSellOk`. Every timezone, session and day boundary of the script is inside
the filter block and inside the data files. The strategy section itself has none: no session, no daily
limit, no cooldown. Its only clocks are `bar_index` differences (`limitBars`, `timeStop`).

### 4.3 The STRATEGY section (1628-1791), one script run on bar `j`

State the script sees: `strategy.position_size`, `strategy.opentrades` and `strategy.equity` as they are AFTER
bar `j`'s intrabar fills (section 5, step 1) and BEFORE the orders of this run fill.

    pos      = strategy.position_size                      (real)
    xpwPos   = xpwInv ? -pos : pos                         (1645) the position in the normal frame
    xpwBuyOk = tradeDir != "Short only (sell only)"        (1646)
    xpwSellOk= tradeDir != "Long only (buy only)"          (1647)
    allowLong  = xpwInv ? xpwSellOk : xpwBuyOk             (1648)
    allowShort = xpwInv ? xpwBuyOk  : xpwSellOk            (1649)
    goLong   = nLong  > 0 and allowLong                    (1655; doneL != bar_index is always true on history)
    goShort  = nShort > 0 and allowShort                   (1656)
    oppL     = oppCloses and nShort > 0 and not allowShort (1665)
    oppS     = oppCloses and nLong  > 0 and not allowLong  (1666)
    closeL   = xpwPos > 0 and not goLong  and (useLimit ? (exitL or oppL or goShort)
                                                         : not goShort and (exitL or oppL))    (1669)
    closeS   = xpwPos < 0 and not goShort and (useLimit ? (exitS or oppS or goLong)
                                                         : not goLong  and (exitS or oppS))    (1670)

`goLong` and `goShort` are never both true (the zeroing). `closeL` and `closeS` are never both true.

Orders, in the order the script places them:

**(a) Close** (1677-1680). `closeL or closeS` -> `strategy.close_all`. Comment: `"exit | " + exitLSrc` when
`exitL` (for `closeL`; `exitSSrc` / `exitS` for `closeS`), else `"opp ENTER | " + firstShort` (`firstLong`).

Consequences of the gate being pre-filter, to keep exactly:
- Market mode: on a bar with `goLong` or `goShort` true there is NO close, even when the filter then blocks the
  entry and even when an "exit only" label sits on the same bar. A blocked entry does nothing at all.
- Limit mode: `goShort` (pre-filter) closes an open normal-frame long and cancels pending long entries even
  when `fgfSellOk` is false and no short order is placed. Mirror for `goLong`.

**(b) Distances** (1685-1693), computed on bar `j`:

    atrNow  = ta.atr(atrLen)                       chart timeframe
    atrMode = exitUnit == "ATR"
    slTicks = atrMode ? slAtrMult * atrNow / mintick : slPtsIn
    tpTicks = atrMode ? tpRMult * slTicks            : tpPtsIn
    trAct   = atrMode ? trActAtr  * atrNow / mintick : trActPts
    trDist  = atrMode ? trDistAtr * atrNow / mintick : trDistPts
    slUse = slTicks > 0;  tpUse = tpTicks > 0;  trUse = trailOn and trDist > 0

In ATR mode a stop of 0 also switches the target off (`tpTicks = tpRMult * 0`). A comparison with na is false.

`ta.atr(n)` = `ta.rma(ta.tr(true), n)`, on the whole chart file from row 0: `tr[0] = high[0] - low[0]`,
`tr[i] = max(high - low, |high - close[i-1]|, |low - close[i-1]|)`; `atr[n-1]` = the plain mean of
`tr[0..n-1]` summed in index order; then, with `alpha = 1.0 / n`, exactly
`atr[i] = alpha * tr[i] + (1.0 - alpha) * atr[i-1]`; na before row `n-1`. Use this recursion to the letter
(both builds must be bit-equal). ATR is never na inside the windows (the data start years earlier).

**(c) Pending list, cancel pass** (1713-1722), limit mode only, over the script's list (`pendId`, `pendBar`,
`pendDir`; `pendDir` is the normal-frame side, +1 = from a long entry):

    stale   = bar_index - pendBar >= limitBars
    against = pendDir > 0 ? (exitL or goShort) : (exitS or goLong)
    stale or against  ->  strategy.cancel(id) and remove from the list

**(d) Time stop** (1749-1752): `timeStop > 0`: for every open trade (newest first) with
`bar_index - entry_bar_index >= timeStop`: `strategy.close(entry id, comment="time stop | " + entry comment)`.
`entry_bar_index` is the bar where the entry FILLED.

**(e) Entries** (1758-1780).

    room = maxOpen - strategy.opentrades - size(pendId)        (after the cancel pass (c); the trades being
                                                                 closed by (a) / (d) still count)
    if goLong and fgfBuyOk:
        for k = 0 .. nLong-1:
            if room > 0 or xpwPos < 0:
                id = (xpwInv ? "S" : "L") + bar_index + "-" + (k+1)
                if placeEntry(id, true, useLimit ? low : na, longSrc[k]):
                    room -= 1
                    if useLimit: push (id, bar_index, +1)
    if goShort and fgfSellOk:    the same with xpwPos > 0, id (xpwInv ? "L" : "S"), high, shortSrc, -1

`placeEntry(id, isLong, lim, src)` (1727-1746):

    q = entryQty();  placed = q > 0
    if placed:
        realLong = xpwInv ? not isLong : isLong
        strategy.entry(id, realLong ? long : short, qty=q, limit = xpwInv ? na : lim, stop = xpwInv ? lim : na,
                       comment = (realLong ? "ENTER LONG" : "ENTER SHORT") + (xpwInv ? " (inv)" : "")
                                 + (na(lim) ? "" : xpwInv ? " stop @ label" : " @ label") + " | " + src)
        if slUse or tpUse or trUse:
            strategy.exit("X " + id, from_entry=id, loss = slUse ? slTicks : na, profit = tpUse ? tpTicks : na,
                          trail_points = trUse ? max(trAct, 0) : na, trail_offset = trUse ? max(trDist, 1) : na,
                          comment_loss="SL | "+src, comment_profit="TP | "+src, comment_trailing="trail | "+src)
    return placed

`entryQty()` (1698-1705), evaluated once per label (same value for every label of the bar):

    q = qtyFixed
    if qtyMode == "Risk" and slUse:
        riskPerContract = slTicks * mintick * pointvalue
        q = riskPerContract > 0 ? strategy.equity * riskPct / 100.0 / riskPerContract : 0.0
    if qtyStep > 0:  q = floor(q / qtyStep + 1e-9) * qtyStep
    return min(q, qtyMax)

Order of operations as written. Risk with no stop falls back to Fixed. The cap is applied after the rounding.
Equity <= 0 in Risk mode gives `q <= 0`: nothing is placed.

**(f) Pending list, filled pass** (1783-1791), limit mode, only if the list is not empty and
`strategy.opentrades > 0`: remove every list entry whose id is the entry id of a trade open at script time.

Facts that follow from the code (check them in your notes):
- A pending entry that filled during bar `j` is counted twice in `room` on bar `j` (once in `opentrades`, once
  in the list): (f) runs after (e).
- A pending entry that filled AND whose trade closed before the script sees it open stays in the list as a
  ghost until `stale` or `against` removes it, and holds one unit of `room` meanwhile. `strategy.cancel` on a
  filled order does nothing.
- `closeL` through `oppL` (one-side mode) does not cancel pending long entries (`against` does not read
  `oppL`); they stay live.
- All live pending entries have the same `pendDir`, and an open position always has that same normal-frame
  side: a `goLong` bar closes normal-frame shorts (`closeS`, limit mode) and cancels pending shorts before
  it places anything. So a pending entry never fills against an open position. Assert it.
- Market mode, `room <= 0`, `xpwPos < 0`, `goLong and fgfBuyOk`: every label is placed; the first one
  reverses, the others stack. "Max open entries" does not hold on a reversal bar.

FGD funnel (1796-1799), normal frame: `raw_long` = bars with `goLong`, `raw_short` = bars with `goShort`,
`blocked_long` = `goLong and not fgfBuyOk`, `blocked_short` = `goShort and not fgfSellOk`.

Live-only code, inert on history: `varip doneL / doneS`, `tickPx`, `tickBar`, `entryPx`, `barstate.islast`
(the table), every label / line / plot.

### 4.4 Update 1 (Inverted direction), line by line

| Pine | effect | replica |
|---|---|---|
| 1645 `xpwPos` | every decision that reads the position SIDE reads the mirror of the real position | `closeL` / `closeS`, `room > 0 or xpwPos < 0` |
| 1646-1649 `allowLong` / `allowShort` | "Trade direction" restricts the orders really placed: inverted, a normal long is a real sell and needs `xpwSellOk` | swap the two tests when `inv` |
| 1655-1656, 1665-1666 | unchanged expressions on the new flags: the entry held back by "Long only" still closes the real long through `oppS` | same |
| 1739-1743 `realLong`, `limPx`, `stopPx` | the order goes in on the other side. Market stays market. The buy limit at `low` becomes a SELL STOP at `low`; the sell limit at `high` a BUY STOP at `high` | trade `dir` = real side; the pending order has the same trigger price and the same fill (T7) |
| 1745 `strategy.exit` | unchanged tick distances, attached to the trade really open: a real short has its stop above, target below, trail arming below | lay the levels out from the real fill on the real side |
| 1763, 1774 ids | the letter is the side really placed (`S` = a sell) | `id` |
| 1710-1722, 1767-1769 | the pending list, `pendDir`, `stale`, `against` stay in the normal frame | same |
| 1749-1752 time stop, 1698-1705 sizing | read the real trades / the real equity; unchanged | same |
| 1796-1799 FGD | normal frame: a "raw long" is the entry placed as a sell, blocked by `fgfBuyOk` | `raw_*` / `blocked_*` normal frame; `long` / `short` trade counts real |

Mirror property (self-check on single decisions): from the same bar inputs, the run with `inv` true from real
position `p` takes the mirror of the decisions of the run with `inv` false from real position `-p` and
`tradeDir` swapped (Long only <-> Short only): the same close, the same number of orders on the other side,
ids with the other letter, the same quantities, the same tick distances mirrored, the same pending list.

### 4.5 The older reverse option, and how it differs

`reverseAll` (1584, 1604-1613, inside `xpw.py`) flips the label BEFORE the filter: `dd := -dd`, AGREE entries
swap lists, "exit only" rows are not flipped. A reversed LONG label is a SHORT entry: it needs `fgfSellOk`,
and in limit mode it is a sell LIMIT at the candle `high`. `xpwInv` flips the ORDER after the filter: the LONG
label still needs `fgfBuyOk`, is sold, in limit mode by a sell STOP at the candle `low`, and "exit only" rows
close the mirrored side. Properties the header states (stage 3 tests them):
- Filter off, Signal tick, no row on "exit only": `inv` alone and `reverseAll` alone give the same real
  trades (same ids, prices, quantities, exits); both on = both off.
- One-side modes: inverted entries are those of the other one-side mode without the option, on the opposite
  side.

---------------------------------------------------------------------------------------------------------

## 5. The broker on a chart bar (path 'tv'), and every assumption about TradingView

Per window bar `j`, in this order:

**Step 1, intrabar.** Path (SPEC_AH.md rule 4): if `(high - open) < (open - low)`: open -> high -> low -> close,
else open -> low -> high -> close. Along it: (i) every live pending entry order (limit mode) can fill; (ii)
every open trade's exit order (stop loss, take profit, trailing stop) is evaluated, including for a trade
that fills in this same step, from its fill point to the end of the bar.

**Step 2, the script** (section 4.3) with the position, open trades and equity left by step 1.

**Step 3, fills at the close `c`**, in the order the orders were placed: `close_all`; the time-stop closes;
then the entries: market entries fill at `c` (the first one against the real position closes it first, kind
`reverse`); a pending entry placed in this run fills at `c` only if `c` satisfies it (T6).

**Step 4.** Bar-close equity (realized + open P/L at `c`), exposure and the diagnostics of section 8.

Window: flat and an empty pending list at the first window bar. At the last window bar, after step 3, every
open trade is closed at that close (kind `end`, exit cost charged); unfilled pending orders are dropped. An
entry filled at the last close is closed there as `end` (as `engine.py` does).

### The exit walk of one trade (long space: multiply prices by the trade's real `dir`)

Levels, fixed when the entry fills at price `e` (use these formulas to the letter, ticks first):

    SL  = e - loss * mintick              if slUse      loss  = slTicks
    TP  = e + profit * mintick            if tpUse      profit = tpTicks
    A   = e + max(trAct, 0) * mintick     if trUse      (activation)
    off = max(trDist, 1) * mintick        if trUse
    armed = trUse and e >= A - tol        (trail_points 0: armed at the fill),  best = e

`tol = 1e-8` (1e-6 tick), as in `engine.py`. The tick values are those computed on the bar where the order was
PLACED (for a pending entry that is an earlier bar than the fill). Semantics = `hrd._walk` (stop + limit +
trail) with the tolerance of `engine._walk`:

1. At the bar open `v0` (only for a trade open before this bar): stop level `lvl` = the higher of `SL` and the
   trailing stop `best - off` if armed. `v0 <= lvl + tol` -> exit at `v0` (kind `trail` if the trailing stop
   is >= `SL`, else `sl`). Else `v0 >= TP - tol` -> exit at `v0`, kind `tp`. Else the open can arm
   (`v0 >= A - tol`: armed, `best = v0`) or ratchet (`best = max(best, v0)`) the trail.
2. Rising segment `a -> b`: `b >= TP - tol` -> exit at `TP` (at `a` if `TP <= a`), kind `tp`. Else the trail
   arms (`b >= A - tol`: `best = b`) or ratchets (`best = max(best, b)`).
3. Falling segment `a -> b`: `lvl` is fixed along it. `b <= lvl + tol` -> exit at `lvl` (at `a` if
   `lvl >= a`), kind `trail` if the trailing stop is >= `SL`, else `sl`.
4. A trade that fills inside the bar at point `e` on a segment: start with the rest of that segment
   (`a = e`), without step 1.

Worked checks, each from a fresh long with `e` 100.00, `loss` 300, `profit` 300, `trail_points` 100,
`trail_offset` 75 (SL 97.00, TP 103.00, activation 101.00, offset 0.75), on the bar after the fill:
- O 100.20 H 101.60 L 99.90 C 100.50: path O-L-H-C; the rise to 101.60 arms the trail, the fall to 100.50
  meets 101.60 - 0.75 = 100.85: exit 100.85, `trail`.
- O 100.20 H 103.40 L 100.10 C 103.20: path O-L-H-C; the rise reaches 103.00: exit 103.00, `tp`.
- O 96.50 (never armed): the open is below the stop: exit 96.50, `sl`.
- O 100.20 H 100.90 L 99.00 C 99.50, then a bar O 99.40 H 99.60 L 98.00 C 98.20, with `timeStop` 2 and a fill
  at the close of bar `i`: nothing is touched on bars `i+1`, `i+2`; the run of bar `i+2` closes it at 98.20,
  `time`.

### A pending entry (limit mode), `pendDir = d`, price `P` (`low` for d = +1, `high` for d = -1), real side `dr = inv ? -d : d`

Trigger in "d-space" (`u = d * price`): `u <= d * P + tol`. At the open of a later bar: `u0 <= d*P + tol` ->
fill at the OPEN. Else on the first d-space falling segment that reaches `d*P`: fill at `P`. Normal: a buy
limit / sell limit. Inverted: a sell stop / buy stop. Same trigger, same price (T7). The trade then has real
side `dr`, quantity and tick distances from the placement bar, `entry_bar` = the fill bar, and its exit walk
starts at the fill point (rule 4 above). Normal mode: the rest of the segment runs against the new trade
(its stop can fill in the same bar). Inverted: the rest of the segment runs in its favour (its target can
fill in the same bar).

A trade's fills depend only on the path and its own levels, so the trades and pending orders of a bar can be
walked independently of each other.

### Assumptions (T = TradingView behaviour that cannot be checked here; one reading for both builders)

- **T1 One run per bar.** History: the script runs once, at the close. `calc_on_every_tick` and the `varip`
  variables only matter live. Why: documented behaviour of historical bars.
- **T2 Orders fill at the close of the bar that places them**, in placement order (`process_orders_on_close`).
  Why: the documented meaning of the flag; the same reading as `engine.py`.
- **T3 Exits start on the next bar** for a trade filled at a close: at the fill price none of its levels can
  be touched (`loss`, `profit` > 0, `trail_offset` >= 1 tick). **A trade filled inside a bar has its exit
  live from the fill point on, along the rest of that bar.** Why: the exit was placed with the entry order,
  so TradingView creates it at the fill (SPEC_AH.md rule 3).
- **T4 First level touched along the path wins**; a level already passed at the open fills at the open (stop
  and limit alike); a limit fills at a touch (`backtest_fill_limits_assumption` 0); a stop fills at its price
  (slippage 0). Why: SPEC_AH.md rule 4, the documented broker emulator.
- **T5 Trailing stop** as SPEC.md rule 4 / SWEEP_AH_SPEC.md section 1: armed when price reaches the fill +
  `trail_points` ticks, then the stop = best price - `trail_offset` ticks, moving only in favour; together
  with `loss` the higher stop is the one hit; `trail_points` 0 = armed at the fill. A target at or inside the
  activation distance means the trail never acts.
- **T6 A pending entry placed at the close fills at that same close when the close satisfies it**, i.e. when
  `close == low` (pendDir +1) or `close == high` (pendDir -1), at the close. Why: the documentation of
  `process_orders_on_close` ("price-dependent orders are filled only if the price conditions are met" on that
  extra attempt). It is not rare: the close equals the label price on about 10% of BTC 5-minute signal bars
  (1176 of 12141 long, 1292 of 11369 short), about 2% on BTC 60 (34 / 46), almost never on XAU 15 (21 / 50).
  Count these fills (`pend_filled_at_close`). The header's sentence "a fill at the candle's low on the label
  candle itself is impossible" describes a candle that closes above its low; when the close IS the low, the
  fill at the close is at the label price at the moment the label exists, so the two do not conflict. On
  every later bar the order is live along the whole path, up to and including the bar whose close cancels it
  (`stale` at `pendBar + limitBars`): the cancel is placed in the run, after that bar's path.
- **T7 Inverted, the stop entry fills exactly where the limit would**: at `P` when the path reaches it, at the
  open when a bar opens through it, at the placement close when `close == P`. Why: a sell stop at `P` and a buy
  limit at `P` are both triggered by price <= `P`; slippage and "verify price for limit orders" are 0.
- **T8 Reversal at fill time.** A market `strategy.entry` against the real position closes ALL open trades at
  `c` (kind `reverse`) and opens the new trade with its own `q`; later same-side entries of the bar add `q`
  each. The quantity to close is whatever is open when the order fills, so trades already closed at this
  close by the time stop are kind `time`, the rest `reverse`. Why: SPEC.md rule 6, the reading verified for
  the trailing-TP engine; the same price either way.
- **T9 `close_all` first.** On a bar with `close_all` and time-stop orders every trade is kind `close_all`
  (placed first, same price). `close_all` does not cancel pending ENTRY orders; only pass (c) does.
- **T10 Each exit closes its own entry** (as if `close_entries_rule = "ANY"`), although the script leaves the
  default "FIFO". Why this deviation is the reading to build: with FIFO TradingView still gives every exit
  order the quantity of its own entry and fires it at its own level (that is how its documentation's FIFO
  example behaves; it cannot be checked here); only the PAIRING in the List of Trades changes (the oldest
  open trade is the one closed). So the fills, the cash
  flows, the equity curve, net profit and drawdown are the same under both rules whenever the time stop is
  off, exactly so with equal quantities (Fixed, the default). What FIFO would change: which entry each exit
  row is paired with (profit factor, win rate, bars held, the fair halves' attribution), and, with the time
  stop on or with Risk quantities, the ages and count of open trades the script reads, where TradingView's
  order bookkeeping is not documented well enough to copy. Per-entry pairing is also what the script's own
  comments describe and what the verified trailing-TP engine does. Report `fifo_exits` (section 8) so the
  size of the difference is known.
- **T11 No margin.** Margin calls and insufficient-funds checks are NOT modelled (as if "Margin for long /
  short positions" were 0%); the account may go below zero and keeps trading. With TradingView's default 100%
  margin this script on BTC is dominated by margin calls: one default entry (0.1 BTC) costs more than the
  10,000 account on 29.5% of the window's 60-minute bars, and two stacked entries always do. Report
  `margin_bars` and `max_expo` (section 8). Why not modelled: the liquidation rule's timing and rounding
  cannot be checked here, the other replicas ignore margin too, and it is an account setting, not strategy
  logic.
- **T12 Levels are not rounded to the tick grid**, quantities are not rounded beyond `qtyStep`. TradingView
  may round a stop / target to the tick (at most 0.005 per level). XAU prices have 3 decimals; kept as they
  are.
- **T13 `pyramiding` never binds.** Outside reversal bars `opentrades + pending <= maxOpen <= 100`; a reversal
  bar restarts the count at no more than the labels of one bar (at most 13, one per rung). If a same-side
  entry would be the 101st, raise.
- **T14 Time stop.** `entry_bar_index` = the fill bar. A trade filled at the close of bar `i` is closed at the
  close of bar `i + timeStop` if still open; a trade filled inside bar `i`, the same.
- **T15 The script reads state before its own orders fill**: `strategy.opentrades`, `position_size`, `equity`
  in `room`, `closeL` / `closeS`, the time stop, `entryQty` and pass (f).
- **T16 Path tie** `high - open == open - low` -> open -> low -> high -> close (rule 4's "else").

---------------------------------------------------------------------------------------------------------

## 6. What cannot be reproduced, and what the replica does instead

| item | replica |
|---|---|
| Seconds rungs (30S, 15S, 5S, 1S): no data | na on every bar (`xpw.py`): READ HERE never lands there, "every rung" has 9 live rungs |
| Rung agreement (`agreeOn` true) | not implemented in `xpw.py`: raise `NotImplementedError` |
| Live behaviour: entries on the first tick a label appears, on higher-rung states still forming; `varip`; label redraws | history only: one run per bar at its close |
| TradingView margin (default 100%) and insufficient-funds rules | none (T11), diagnostics instead |
| FIFO pairing in the List of Trades | per-entry pairing (T10), `fifo_exits` |
| Tick rounding of levels, TradingView's own price feed and sessions, real gold volume | data files as they are; volume is not used by this script |
| Bar Magnifier's own choice of lower timeframe | stage 3 uses the 1-minute bars for every chart |
| Monthly / weekly rung history before the data start | the data start in 2011 (XAU) / 2012 (BTC): enough warm-up for the windows |

---------------------------------------------------------------------------------------------------------

## 7. Money model

- Account: 10,000 at the window start. `qty` per entry from `entryQty()` (section 4.3 (e)); default Fixed 0.1
  units (0.1 BTC is about 5,800 to 12,600 USD in the window; 0.1 ounce of gold about 130 USD).
- Costs per fill, per unit, `(fixed, fraction of the fill value)`, the table of `hrd.py`:
  'tv' `(0, 0)` both pairs (the script sets no commission and no slippage);
  'ours' XAU `(0.15, 0)`, BTC `(0.10, 0.0002)`;
  'stress' XAU `(0.26, 0)`, BTC `(0.11, 0.00035)` (the tick is charged as a cost; fill prices never change).
  `cost of a fill = qty * (fixed + fraction * fill price)`, charged when the fill happens (entry and exit).
- `pnl_gross = dir * (exit_px - entry_px) * qty * pointvalue`; `pnl = pnl_gross - entry cost - exit cost`.
- `strategy.equity` seen by the script on bar `j` (`E_run[j]`) = 10,000 + realized `pnl_gross` of closed
  trades - every cost charged so far (entry costs of open trades included) + open P/L of the open trades at
  `close[j]`. Risk sizing uses it. No floor at zero.
- Bar-close equity `E_close[j]` = the same after step 3.
- `eq_before` of a trade: filled at a close (market, or a pending order filled at its placement close):
  `E_run[j]` minus the costs of the fills of this close that come before it (the exits of `close_all`, time
  stop and reversal, the entry costs of earlier entries of the bar). Filled inside a bar: `E_close[j-1]`
  (10,000 on the first window bar).
- `R` of a trade with a stop: `pnl / (qty * slTicks * mintick * pointvalue)` with the `slTicks` of its
  placement bar; NaN without a stop.

---------------------------------------------------------------------------------------------------------

## 8. Interface, trade record, summary

    prepare(pair, chart_tf, params=None) -> P
    simulate(P, x=None) -> R
    trades(P, R) -> DataFrame
    summary(P, R) -> dict
    run(pair, chart_tf, params=None) -> (trades, summary)       # splits one dict into prepare / simulate keys

`prepare`: call `xpw.xpw_signals(pair, chart_tf, start, end, <the xpw keys>)` and
`fgf.fgf_permissions(pair, chart_tf, start, end, <the fgf keys>)`; both warm themselves up and return the
window rows indexed by file row. `P` must expose at least `pair`, `tf`, `start`, `end`, `mid`, `n`, `rows`
(file row numbers of the window bars), `open`, `high`, `low`, `close`, `t_open`, `t_close`, `nLong`, `nShort`,
`exitL`, `exitS`, `buyOk`, `sellOk` and `params` (the resolved `prepare` parameters). Nothing in `P` may depend
on an ORDER / EXIT input (`goLong`, `allowLong` and the like are built in `simulate`).

`simulate` must not accept a `prepare` key (raise); `inv` is an alias of `xpwInv` (raise if both are given and
disagree). Speed: one `simulate` on BTC "1" (1,039,430 bars) well under 1 s after compilation (numba; no
Python objects in the loop: label strings are joined in `trades`); `prepare` under 2 minutes; under 3 GB.

Stage 3 note (path 'mag', not built now): step 1 walks the 1-minute sub-bars of the chart bar in time order,
each with its own rule-4 path and its own open test, for exits AND pending entries, the trailing state
carrying over; steps 2-4 and the close attempt of T6 stay on the chart bar. Keep step 1 in one function so
that it can be swapped.

**Trade record**, one row per entry fill, rows in fill order `(entry_bar, sig_bar, k)`:

| column | meaning |
|---|---|
| `id` | the Pine id: real-side letter + `sig_bar` + "-" + `k` |
| `dir` | REAL side, +1 / -1 |
| `sig_dir` | normal-frame side (+1 = from `longSrc`); `= -dir` when `inv` |
| `src` | the label source string (`longSrc[k-1]` / `shortSrc[k-1]` of `sig_bar`) |
| `sig_bar`, `k` | file row where the order was placed; 1-based label index |
| `entry_bar`, `entry_time`, `entry_px`, `qty` | file row of the fill; `t_close` of that bar; fill price; quantity |
| `exit_bar`, `exit_time`, `exit_px` | file row; `t_close` of that bar; fill price |
| `exit_kind` | `sl`, `tp`, `trail`, `time`, `close_all`, `reverse`, `end` |
| `pnl`, `pnl_gross`, `costs` | after costs; before; entry + exit cost |
| `eq_before`, `R` | section 7 |
| `sl_px`, `tp_px`, `tr_act_px`, `tr_off` | real prices of the levels (NaN when unused); `tr_off` a distance |

Optional: `entry_comment`, `exit_comment` (the Pine strings; a reversal's exit comment is the reversing
entry's comment; `end` -> "end").

**Summary.** Common fields as `hrd.summary_fast` defines them: `trades`, `net_pct` (final equity against
10,000), `pf`, `win_pct` (on `pnl`), `max_dd_pct` (peak-to-trough of the bar-close equity, % of the running
peak, the curve starting at 10,000; may exceed 100), `max_dd_init_pct`, `long`, `short` (real sides),
`raw_long`, `raw_short`, `blocked_long`, `blocked_short` (normal frame, bars), `exit_<kind>` for the seven
kinds, `avg_bars_held` (`exit_bar - entry_bar`), `exposure` (share of window bars with an open trade after
step 3), `half1_pct`, `half2_pct` (change of `E_close` in each half, % of 10,000; `mid = start + (end -
start) // 2`, the half-1 curve ends at the last bar with `t_close <= mid`), `h1_trades`, `h2_trades` (trades
with `entry_time <= mid` / `> mid`), `final_equity`, `costs`.

Fair halves `h1r_pct`, `h2r_pct` (trades ENTERED in each half), with `halves_rule` in the summary:
- `'additive'` when the quantity does not depend on equity (`qtyMode` "Fixed", or "Risk" without a stop):
  `100 * sum(pnl) / 10000`. A fixed-size trade does not compound, so a fresh start changes nothing. This is
  the default, and the only formula that survives a negative account (T11).
- `'compound'` when `qtyMode` is "Risk" with a stop: `100 * (prod(1 + pnl / eq_before) - 1)`; NaN if an
  `eq_before` of that half is <= 0.
- 0 when the half has no trade.

Fields of this strategy:
- `net_R`, `h1_R`, `h2_R`, `n_R`: sum of `R` over all trades / the trades entered in each half; trades with a stop.
- `placed` (orders placed), `skipped_room` (labels of a gated bar not placed because `room <= 0`),
  `skipped_qty` (`placeEntry` returned false).
- `pend_placed`, `pend_filled`, `pend_filled_at_close`, `pend_cancelled` (unfilled, removed by `stale` or
  `against`), `pend_open_end`; all 0 in Signal tick mode.
- `close_all_bars`, `max_open` (most open trades after step 3), `zero_length` (`entry_bar == exit_bar`).
- `max_expo`: the largest `sum(qty) * close / E_close` over window bars with a position (`inf` if a position
  is held with `E_close <= 0`). `margin_bars`: window bars with `sum(qty) * close > E_close` (where the
  default 100% margin would have stepped in).
- `fifo_exits`: trades with `exit_kind` in `sl`, `tp`, `trail`, `time` that have an earlier row (fill order)
  still open when they exit: an earlier row with a larger `exit_bar`, or with the same `exit_bar` and a close
  fill (`time`, `close_all`, `reverse`, `end`) while this row's exit is intrabar (`sl`, `tp`, `trail`). These
  are the rows TradingView's FIFO list would pair differently.

Comparing A and B: bars, kinds, ids, counts exactly; prices, quantities, `pnl`, equity fields to a relative
1e-9.

Saved trade lists (stage 2): `$W/out/xpw23_<a|b>_<PAIR>_<TF>.parquet` for BTC 60, BTC 5, XAU 60, XAU 15,
default inputs, cost 'tv', one file per cell with a column `variant` in `on_normal`, `off_normal`, `on_inv`,
`off_inv` (filter on / off, `inv` off / on).

Self-checks beyond REPLICA_SPEC.md stage 2: the reference counts of section 4.1; hand traces with the bars
printed for every exit kind (`sl`, `tp`, `trail`, `time`, `close_all`, `reverse`, `end`), for a reversal bar
that ignores `maxOpen`, and in limit mode for a fill at the placement close, a gap fill at an open, a
same-bar entry and exit, a `stale` cancel, an `against` cancel and a ghost entry holding `room`; `inv` on
with the filter off equal to `reverseAll` on with `inv` off (default rows, Signal tick); Risk sizing against
a direct evaluation of `entryQty`.

---------------------------------------------------------------------------------------------------------

## 9. Calibration grid proposal (for `$W/CALIB_SPEC.md`)

16,200 settings per cell, the same product in every cell. Everything not listed stays at the script
default (`entryFill` "Signal tick", `qtyMode` "Fixed" 0.1, `exitUnit` "ATR", `atrLen` 14, `tradeDir` "Both",
`sigRung` chart rung, `lblRead` on, leg rows and End-of-leg "enter", `reverseAll` off). The script has no
blocked-close switch, so the filter has two values.

| dimension (Pine name) | values | kind | stage |
|---|---|---|---|
| `actDL_actDS` (both divergence rows together) | "enter", "off", "exit only" | categorical | prepare |
| `actInf` | "enter", "off", "exit only" | categorical | prepare |
| `fgfOn` | false, true | categorical | prepare |
| `xpwInv` | false, true | categorical | simulate |
| `slAtrMult` | 1.5, 3.0, 6.0 | ordinal | simulate |
| `tpRMult` | 1.0, 2.0, 4.0, 0.0 (0 = no target, ordered last) | ordinal | simulate |
| `trailOn` | false, true | categorical | simulate |
| `trActAtr` | 1.0, 3.0 (None with the trail off) | ordinal | simulate |
| `trDistAtr` | 0.75, 1.5, 3.0 (None with the trail off) | ordinal | simulate |
| `timeStop` | 0, 24 | ordinal | simulate |
| `maxOpen` | 1, 3, 20 | ordinal | simulate |

Count: stop x target = 12; trail off 1 + on 2 x 3 = 7 per pair = 84; a trail that can never arm before the
target fills (`tpRMult > 0` and `trActAtr >= tpRMult * slAtrMult`: the pairs (1.5, 1), (1.5, 2), (3, 1) with
activation 3.0) is the same run as trail off and is listed once: 84 - 9 = 75. x `timeStop` 2 x `maxOpen` 3 x
`xpwInv` 2 = 900 `simulate` settings per `prepare`; x 18 `prepare` settings (3 x 3 x 2) = **16,200**. The
defaults are a grid point (enter, enter, filter on, normal, 3.0, 1.0, trail on 1.0 / 0.75, 0, 20). In the
three equality cases (activation 3.0 = target distance 3.0 ATR) the activation price equals the target price
bit for bit with the formulas of section 5, and the target is tested first, so the trail never acts; the
calibration tests should confirm that such a run equals its trail-off run. Compute: 18 `prepare` calls and
16,200 `simulate` calls per cell; BTC 1 stays inside CALIB_SPEC.md's 45 minutes with 3 workers as long as one
`simulate` there takes under 0.5 s.

Why these: the Pine header's own calibration record names the direction, the trail on / off, the target
multiple, the divergence rows, the Info row, the filter and "Max open entries" as the inputs that moved its
results most, the stop width and the time stop as secondary. With the filter off and no "exit only" row,
`xpwInv` equals `reverseAll`, so the direction dimension covers the header's "reverse" finding.

Noise floor (trailing offsets not below 0.1% of price on BTC, 0.05% on gold). The offset is `trDistAtr` x the
chart ATR, so the floor depends on the cell. Rule: a trail-on row is in the pool only if `trDistAtr x median
over the window of ATR(14) / close >= the floor`; the runner computes the median from the data and writes a
column `floor_ok`. Rows below the floor are still computed (the product, the dims file and the default row
stay the same in every cell) and the rule's pool takes `floor_ok` rows only.

| cell | median ATR(14) / close | `trDistAtr` values in the pool | pool |
|---|---|---|---|
| BTC 1 | 0.0433% | 3.0 | 7,128 |
| BTC 5 | 0.1281% | 1.5, 3.0 | 11,664 |
| BTC 15, 30, 60, 120, 240 | 0.2547, 0.3810, 0.5621, 0.8126, 1.1730% | all | 16,200 |
| XAU 1 | 0.0185% | 3.0 | 7,128 |
| XAU 5 | 0.0461% | 1.5, 3.0 | 11,664 |
| XAU 15, 30, 60, 120, 240 | 0.0859, 0.1278, 0.1863, 0.2539, 0.3712% | all | 16,200 |

The default trail (0.75 ATR) is below the floor on the 1- and 5-minute charts of both pairs: there the
default row is reported but is not a candidate. Adding `trDistAtr` 6.0 would lift the 1-minute pools to
11,664 at 20,736 computed rows; not proposed, because on the higher timeframes a 6-ATR trail mostly
duplicates trail off.

Scoring note for the rule: with Fixed quantity the fair halves are additive sums in % of 10,000 (section
8), so within a cell the ranking is by money earned per 0.1 unit; `h1_R` / `h2_R` give the same halves in R
for a risk-normalised look. Left out to stay inside the budget: `entryFill` (it would double the grid; a
variant that swaps `timeStop` for `entryFill` {"Signal tick", "Limit at label price"} also has 16,200
settings), `sigRung`, `qtyMode`.
