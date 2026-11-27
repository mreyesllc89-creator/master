# Reconciliation: ApexForge Flow Resonance + FGF (apex_a.py vs apex_b.py)

Ground truth: `/home/user/master/ApexForge_Flow_Resonance_Strategy_FGF.pine`. The trading logic is on lines 687-747; the filter permissions come from `fgf.py`.

**Result.** There was one disagreement, **R1**: the `exit_time` of trades closed at the window end (kind `end`). It is a labelling convention, not a trading difference. After the fix to `apex_a.py`, the two implementations agree on **147,555 of 147,555 trade rows (100%)**. That covers every column and every summary field, over 84 runs:
- pairs BTC and XAU;
- charts 1, 5, 15, 30, 60, 120 and 240 (the task asked for 1, 5, 60 and 240; I added 15, 30 and 120);
- full windows;
- six parameter sets: default, `fgfOn=False`, `blkClose=False`, `cost='ours'`, `reverse=True` and `pivotTies='left_strict'`.

Before the fix, 147,515 rows agreed. The 40 that differed were exactly the 40 `end` trades, and only in `exit_time`.

The canonical module is **`apex.py`, a copy of `apex_b.py`**. The reasons are in the section "Canonical module" below.

## How the comparison was made

Script: `reconcile_apex_cmp.py PAIR [TF ...]`. Logs:
- `reconcile_apex_cmp_{BTC,XAU}.log` (before the fix, TFs 1/5/60/240);
- `reconcile_apex_cmp_{BTC,XAU}_extra.log` (before the fix, TFs 15/30/120);
- `reconcile_apex_after_{BTC,XAU}.log` (after the fix, all 7 TFs).

JSON: `out/reconcile_apex_{BTC,XAU}{,_extra,_after}.json`.

- **Trades are compared row by row, in order.**
  - Integer columns must be equal: dir, entry_time, exit_time, entry_bar, exit_bar, signal_bar.
  - exit_kind must be equal.
  - Float columns must match within rtol 1e-10 and atol 1e-9: entry_px, qty, exit_px, pnl, cost. Cost is `cost` in A and `entry_cost + exit_cost` in B.
  - The largest float differences were 8.5e-12 in absolute terms, and 6.3e-13 relative for values above 1e-3. They come from summation order: equity is accumulated differently in A and B, which moves qty in the last digits. This was measured on 1/5/60/240 with four of the parameter sets.
- **Summary fields** must match to 1e-9: trades, net_pct, pf, win_pct, max_dd_pct, long, short, raw_long, raw_short, blocked_long, blocked_short, half1_pct, half2_pct, exposure, final_equity, and the exit-kind counts.

## R1. exit_time of a window-end close (apex_a fixed)

- **What disagreed.** A trade still open on the last window bar is closed at that bar's close (SPEC broker rule 5, kind `end`).
  - A stamped it with the last bar's **t_open**.
  - B stamped it with the last bar's **t_close**.
  - Price, qty, pnl, costs and every summary field were identical. One row per run had an `end` trade (40 runs).
- **Which side follows the Pine.** Neither, strictly. TradingView does not close the trade at all: it lists it as open. The `end` close is a replica convention, so the timestamp is a convention too. I chose B's **t_close**, for three reasons:
  1. Every real fill is stamped with the t_open of its bar, as TradingView's List of Trades does. All of those fills happen at the open or inside the bar.
  2. The `end` exit price is the last close, which exists only at t_close. Stamping it at t_open would date the exit before its price existed.
  3. Holding times then run to the moment the position is marked.
- **Fix.** In `apex_a.py` `run()`, the line now reads `'exit_time': np.where(t_kind == K_END, S['t_close'][w0 + t_xk], to[w0 + t_xk])`. I updated `apex_a_notes.md` item 8 to match. Neither `apex_a_check.py` nor `apex_b_check.py` uses exit_time, so their checks still hold.
- **Hand trace.** XAU 60, defaults, trade #39. This is one of the 40 disputed rows. Full output in `reconcile_apex_trace.log`.
  - **Signal bar 39975** [2018-06-07 13:00..14:00]: O 1301.601 H 1302.042 L 1295.049 C 1296.449.
    - body 0.7367 (>= 0.65); (H-C)/(H-L) 0.7998 (> 0.65); C < O, so bearFlow.
    - volume 8684 > 1.7 x SMA20 3422.90 = 5818.93.
    - Supply box: pivot high 1306.652 at bar 39859, reported on 39879. Top 1317.105216, bottom 1296.198784. H 1302.042 >= bottom, and C 1296.449 < top.
    - 15m bar closing 14:00: htfHigh 1297.848, and C < htfHigh.
    - So bearResonance is true, and sellOk is true.
  - **Entry.** A long was open (qty 7.71175261, entry 1295.232), so the short entry is a reversal at the open of bar 39976, 1296.449.
    - qty = 1% x equity 998,863.2060 / 1296.449 = 7.70460856.
    - The equity includes the long's open P/L, minus the entry cost already paid.
    - Stop = 1317.105216 x 1.005 = 1323.690742. Limit = C - 3 x (stop - C) = 1214.723774.
  - **Bracket updates.** Same-side bear resonances on bars 40085 and 40106 replace Exit Short from the next bar on. On both bars sellOk is false: the update is exit management and is not gated (Pine lines 345-348).
    - 40085: stop 1319.512965, limit 1256.105105.
    - 40106: stop 1326.577906, limit 1190.218282.
  - **End.** Nothing touches the bracket. Bar 40138 [2018-06-18 23:00 .. 2018-06-19 00:00] is the last window bar, and the trade is closed at its close, 1281.511.
    - pnl = -1 x (1281.511 - 1296.449) x 7.70460856 - 3.995453 - 3.949416 = **107.146574**, the same in A and B.
    - exit_time = 1529366400 (2018-06-19 00:00), the t_close of bar 40138. A had 1529362800 (its t_open).

## Interpretations both replicas share (checked against the Pine)

The two implementations agreed everywhere else, so I checked the interpretations they share against the Pine. They were built independently, and either could have repeated the other's mistake. Each item cites the trace in `reconcile_apex_trace.log` that shows it on real bars.

| # | Point | Pine / SPEC | Both replicas | Verdict, evidence |
|---|---|---|---|---|
| 1 | htfHigh/htfLow on "15" | request.security, lookahead off, which per SPEC means the last 15m bar with t_close <= chart t_close | same | ok. Trace 7 (BTC 1m, bar closing 13:06): the levels come from the 15m bar closing 13:00, not from the forming one. |
| 2 | Pivots | `ta.pivothigh(high, 20, 20)`: bar i-20 over i-40..i, reported on bar i, strict by default | same; left_strict as the option | ok. Trace 2, bar 109803: the demand box is the 93590 low of bar 109772, reported on 109792 and not before. |
| 3 | Box timing | the box code (lines 299-309) comes before the resonance line (718), so a pivot reported on bar i is used by bar i's test | same | ok |
| 4 | Flow on a bar with H == L | division by zero gives na, and na comparisons are false | no flow | ok |
| 5 | volSpike | `ta.sma(volume, 20)` includes the current bar | same | ok. Every trace prints SMA20 over the last 20 bars, the current one included. |
| 6 | Statement order | blocked close (329-332), entry long, Exit Long, entry short, Exit Short | same | ok. Bull and bear resonance exclude each other (C > O vs C < O), so there is at most 1 market order per bar. |
| 7 | Exit update while in the position | `apxGoLong or (bullResonance and position_size > 0)`: also when the BUY is blocked | same | ok. Traces 2, 3 and 4 show updates with the filter blocking that side. |
| 8 | Blocked-opposite close | strategy.close at the next open, only when apxBlkClose and the position is on the other side | same | ok. Trace 3: XAU 60 short closed at the 1199.741 open after the blocked BUY on bar 32176. |
| 9 | Market order vs the old bracket at the same open | SPEC rule 1 (orders fill at the open) and rule 3 (an exit is cancelled when its trade closes) | market order first, bracket cancelled | ok. A counted 0 cases where the old bracket was also beyond that open, on TFs 1-240, both pairs, filter on and off. The label could never differ. |
| 10 | Bracket on the fill bar | checked after the open fill | same | ok. Trace 5: BTC 60 #1 is stopped on its own fill bar, path O-H-L-C. |
| 11 | Gap through the stop | fills at the open | same | ok. Trace 6: BTC 15 #152, short stop 83351.92, bar opens 83360, fills at 83360. |
| 12 | Sizing | 1% x strategy.equity at the signal close / close. Equity includes open P/L and is net of costs paid. | same | ok. Every trace recomputes qty. |
| 13 | Costs | 0.04% of the value of each fill, both legs of a reversal | same | ok. Every trace recomputes pnl. |
| 14 | `reverse` | SPEC: swap the long and short signals before the gate | literal swap: brackets stay tied to the trade direction | ok, as the spec words it. Trace 8 shows a reversed short from a bull signal with its supply-box bracket. Trace 9 shows the rare degenerate case: a long whose stop is above its fill open, stopped at that open. |

## Reconciler's hand traces

Script: `reconcile_apex_trace.py`, log: `reconcile_apex_trace.log`. Each trace recomputes the claimed trade from the raw parquet files with pandas and plain loops, and uses no code from either replica. It recomputes the signal bar, the boxes and the pivot that made each one, the 15m level, the filter verdict (from fgf.py), the qty from equity, the fill, each bracket update along the way, the exit along the intrabar path, and the pnl. **46 checks, 0 mismatches.**

| # | Cell | Trade | What it shows |
|---|---|---|---|
| 1 | XAU 60 | #39 short, end | R1. A reversal entry with an open long at the signal close, two blocked same-side updates, and the window-end close |
| 2 | BTC 60 | #2 long, reverse | A blocked same-side update (limit 97373 -> 99889), then an allowed SELL reverses at the 97877 open |
| 3 | XAU 60 | #0 short, blocked_close | A same-side update, then a blocked BUY closes the short at the next open |
| 4 | BTC 60 | #15 long, tp | Two blocked same-side updates, then the target at 91139.9728 on an O-L-H-C bar |
| 5 | BTC 60 | #1 long, sl | Stopped on its own fill bar (O-H-L-C, low 95964 <= stop 95975.82) |
| 6 | BTC 15 | #152 short, sl | The bar opens beyond the stop, so it fills at the open, 83360 |
| 7 | BTC 1 | #143 long, sl | A 1m signal inside a 15m bar: the 15m level is from the last completed 15m bar. A same-side update on the fill bar. |
| 8 | BTC 60 reverse | #0 short, blocked_close | A short from a BULL signal with the supply-box bracket, two same-side updates, then a blocked close |
| 9 | BTC 60 reverse | #58 long, sl | Literal reversed bracket on the wrong side: stop 74497 > fill 74055.96, stopped at the fill open, pnl = -2 x commission |

## Agreement table (rows that agree / rows, every column)

Before the fix. Cells marked (exit_time) differ only in the exit_time of the `end` row.

| pair | TF | default | fgfOff | blkOff | ours | reverse | leftStrict |
|---|---|---|---|---|---|---|---|
| BTC | 1 | 17220/17221 (exit_time) | 34601/34602 (exit_time) | 4424/4425 (exit_time) | 17220/17221 (exit_time) | 13222/13222 | 17381/17382 (exit_time) |
| BTC | 5 | 3075/3076 (exit_time) | 4954/4955 (exit_time) | 1822/1823 (exit_time) | 3075/3076 (exit_time) | 1777/1777 | 3151/3152 (exit_time) |
| BTC | 15 | 861/861 | 1180/1180 | 694/694 | 861/861 | 393/393 | 867/867 |
| BTC | 30 | 274/274 | 359/359 | 248/248 | 274/274 | 135/135 | 278/278 |
| BTC | 60 | 76/76 | 131/131 | 74/74 | 76/76 | 59/59 | 76/76 |
| BTC | 120 | 26/26 | 52/52 | 26/26 | 26/26 | 24/25 (exit_time) | 26/26 |
| BTC | 240 | 10/10 | 31/31 | 10/10 | 10/10 | 14/14 | 10/10 |
| XAU | 1 | 2163/2164 (exit_time) | 3650/3651 (exit_time) | 1005/1006 (exit_time) | 2163/2164 (exit_time) | 1365/1365 | 2163/2164 (exit_time) |
| XAU | 5 | 605/606 (exit_time) | 874/875 (exit_time) | 414/415 (exit_time) | 605/606 (exit_time) | 318/318 | 607/608 (exit_time) |
| XAU | 15 | 228/229 (exit_time) | 289/290 (exit_time) | 187/188 (exit_time) | 228/229 (exit_time) | 108/109 (exit_time) | 228/229 (exit_time) |
| XAU | 30 | 138/138 | 193/194 (exit_time) | 105/105 | 138/138 | 88/89 (exit_time) | 139/139 |
| XAU | 60 | 39/40 (exit_time) | 73/74 (exit_time) | 28/29 (exit_time) | 39/40 (exit_time) | 49/50 (exit_time) | 39/40 (exit_time) |
| XAU | 120 | 17/17 | 36/37 (exit_time) | 13/14 (exit_time) | 17/17 | 22/23 (exit_time) | 17/17 |
| XAU | 240 | 2/2 | 9/10 (exit_time) | 2/2 | 2/2 | 5/6 (exit_time) | 2/2 |

Total before the fix: 147,515 / 147,555. No summary field differed in any run.

After the fix: **every cell agrees fully**, 147,555 / 147,555 rows and all summary fields.

| pair | TF | default | fgfOff | blkOff | ours | reverse | leftStrict |
|---|---|---|---|---|---|---|---|
| BTC | 1 | 17221/17221 | 34602/34602 | 4425/4425 | 17221/17221 | 13222/13222 | 17382/17382 |
| BTC | 5 | 3076/3076 | 4955/4955 | 1823/1823 | 3076/3076 | 1777/1777 | 3152/3152 |
| BTC | 15 | 861/861 | 1180/1180 | 694/694 | 861/861 | 393/393 | 867/867 |
| BTC | 30 | 274/274 | 359/359 | 248/248 | 274/274 | 135/135 | 278/278 |
| BTC | 60 | 76/76 | 131/131 | 74/74 | 76/76 | 59/59 | 76/76 |
| BTC | 120 | 26/26 | 52/52 | 26/26 | 26/26 | 25/25 | 26/26 |
| BTC | 240 | 10/10 | 31/31 | 10/10 | 10/10 | 14/14 | 10/10 |
| XAU | 1 | 2164/2164 | 3651/3651 | 1006/1006 | 2164/2164 | 1365/1365 | 2164/2164 |
| XAU | 5 | 606/606 | 875/875 | 415/415 | 606/606 | 318/318 | 608/608 |
| XAU | 15 | 229/229 | 290/290 | 188/188 | 229/229 | 109/109 | 229/229 |
| XAU | 30 | 138/138 | 194/194 | 105/105 | 138/138 | 89/89 | 139/139 |
| XAU | 60 | 40/40 | 74/74 | 29/29 | 40/40 | 50/50 | 40/40 |
| XAU | 120 | 17/17 | 37/37 | 14/14 | 17/17 | 23/23 | 17/17 |
| XAU | 240 | 2/2 | 10/10 | 2/2 | 2/2 | 6/6 | 2/2 |

## Canonical module

`apex.py` is `apex_b.py` with only its header docstring changed and its `__main__` output renamed to `out/apex_<PAIR>_<TF>.parquet`. It has the same interface: `run(pair, chart_tf, params=None) -> (trades, summary)`. I checked that `apex.run` returns trade frames identical to `apex_b.run` (DataFrame.equals) on BTC and XAU 60, with defaults and with reverse plus cost 'ours'.

I picked B over A for four reasons; both are correct.
- **Speed.** BTC 1m in a fresh process takes about 5 s, against about 8 s for A (the builders' timings). In my comparison run it was 3.7 s against 8.7 s.
- **Strict parameters.** An unknown parameter raises a KeyError instead of being ignored silently.
- **Diagnostics.** `compute()` returns the per-bar frame of signals, boxes, gate, bracket and equity.
- **Extras.** Separate entry_cost and exit_cost columns, and the `reverseStops='mirror'` sensitivity option.

A's extras (`original=True`, and the exit_stop / exit_limit columns) stay available in `apex_a.py`.

## Open points (not settled by the Pine or this data)

- **Rounding.** Neither replica rounds quantities, or stop and limit prices to the mintick. TradingView may round order prices to 0.01. The XAU data has 3 decimals, so a bracket fill could differ from TradingView by up to 0.005.
- **`reverse` brackets.** The literal swap is what the spec says, and both replicas made it. `reverseStops='mirror'` is reported as a sensitivity in `out/apex_report.md`. Fewer than 3% of reversed trades hit the degenerate case.
- **`end` exit_time** is a replica convention (R1).
