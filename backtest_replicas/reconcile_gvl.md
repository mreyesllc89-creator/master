# reconcile_gvl: GVLiveV2 Polymarket Pre-Candle + FGF, implementation A against implementation B (stage 3)

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine` (HEAD, Update 1; `Lnnn` = its
lines). Brief: `$W/SPEC_gvl.md`. The two builds: `$W/gvl_a.py`, `$W/gvl_b.py` (as delivered:
`$W/reconcile_gvl_orig/`). Nothing can be compiled or backtested in TradingView here: "follows the Pine" below
means the Pine text plus TradingView's documented order rules as SPEC_gvl states them.

## Result

- **Real bars, as delivered: A and B take the same trades in every compared case.** 600 cases (BTC and XAU,
  charts 1, 5, 15, 60, 240, full windows; per cell 24 fixed cases + 36 random settings), 900,577 trades,
  every column of the trade list, every summary field, digests of the bar-close equity / position / lock
  arrays: 0 trade differences, 1 summary difference (D2).
- **Synthetic bars (a 0.5 price grid, where levels meet all the time), as delivered: 7 of 1,800 cases differ**
  (D1). Real bars almost never put an exit and a pending order on the same price; the grid does.
- **B was wrong in D1 and was fixed; D2 was a definition, settled on A's.** `gvl_a.py` is unchanged (`diff`
  against `reconcile_gvl_orig/gvl_a.py` is empty); `gvl_b.py` has two marked edits (`[stage-3 reconcile fix]`).
- After the fixes: A == B == canonical (`gvl.py`, path 'tv') on 600 + 840 cases of real bars (2,007,627
  trades in the two rounds) and on 1,800 synthetic cases (43,358 trades): 100 %.
- A third reading, the pure-Python reference `gvl_ref.py` written in this stage from the Pine (orders by
  type and side, the script calling entry / exit / cancel / close in the Pine's order), agrees with the
  canonical module on the same 1,800 synthetic cases on both paths (trades, equity curve, position, counters),
  and on real bars (tests T5).

## What was compared

`$W/reconcile_gvl_cmp.py PAIR TF --mods ...` (cases from `$W/gvl_cases.py`), one process per cell, the modules
one after the other:

| cases | content |
|---|---|
| 24 fixed | "Market Next Candle" and "Stop Next Candle" x filter off / on x inv off / on x cost tv / ours / stress, everything else at the script defaults (so: default inputs; filter off; inv on with the filter off and on; each cost mode) |
| grid | points of the calibration grid of SPEC_gvl section 14 (EMA pair, trend EMA, min vol score, vol rise, close location, trend direction, filter, pre-candle mode, inv, SL x ATR, exit style tp5 / time4 / trail with the cell's trail pair, daily lock) with a random cost mode |
| wild | a grid point with 2 to 6 inputs outside the grid switched: `useMaxBarsExit`, `maxDailyLossCurrency > 0`, `maxDailyLosses` 1 / 2 / 5, `QtyMode` Fixed (also quantity 0), `ExitMode` Points (also stop 0, target 0, target = stop), trail in points and tight ATR trails, `radarTimeframeMode` Auto / 1 / 3 / 5 / 15 / 240, `preUseRvol`, `preUseBodyAtr`, `preUseMicroBreak`, `preUseEmaSlope`, `useSessionFilter` with each preset and other session strings, `allowWeekendEntries` false, `oneSignalPerPolyWindow` false and other `maxSignalSecondsAfterWindowStart`, "Signal Only", `preStopAtrBuffer` 0 / 0.01 / 0.1 / 0.5, `preCancelAfterBars` 1 / 3 / 5 / 10, `tvMargin` 100 / 10 / 1, `riskPct`, `maxQty`, `capMargin`, `marginPct`, `qtyStep`, point value, `atrLen` 5 / 7 / 21 / 50, `risingRule` 'mono', RSI inputs, `useMaxStopDistance`, `tpR` 0.5 / 1 / 2.5 / 3, VoVix lengths, `preMinScore`, `maxBarsHeld` 1 / 2 / 8 / 30, `allowAnyChartTimeframe` false |

| round | modules | per cell | cases | trades | result | logs |
|---|---|---|---|---|---|---|
| r0 | A, B as delivered | 24 fixed + 16 grid + 20 wild (seed 0) | 600 | 900,577 | trades 100 %; 1 case with a summary difference (D2) | `reconcile_gvl_r0_<PAIR>_<TF>.log` |
| r1 | A, B (fixed), canonical | the same 600 | 600 | 900,577 | 0 FAIL | `reconcile_gvl_r1_*.log` |
| r2 | A, B (fixed), canonical | 24 fixed + 20 grid + 40 wild (seed 1) | 840 | 1,107,050 | 0 FAIL | `reconcile_gvl_r2_*.log` |
| synthetic, as delivered | A, B, canonical, reference | 150 seeds x 12 settings | 1,800 | 43,358 | A != B in 7 cases (D1); everything else equal | `reconcile_gvl_synth_orig.log` |
| synthetic, after the fix | the same | the same | 1,800 | 43,358 | 0 differing | `reconcile_gvl_synth.log` |

Exit kinds met on real bars (r1 + r2): sl 1,234,498, tp 189,126, trail 210,944, time 288,200, maxbars 46,833,
eod 29,394, daily_lock 4,191, reverse 4,168, end 273. Synthetic: 195 pending fills right after an
exit of the same bar, 151 reversals, 2,364 pending orders filled at a bar open, 29,543 same-bar entry + exit.
Floats are compared to a relative 1e-9, everything else exactly.

## D1. A pending order on the price where a path leg ends, right after an exit at that price (B wrong)

Found by `reconcile_gvl_synth.py --orig`; trace `reconcile_gvl_trace.py` -> `reconcile_gvl_trace.log`.
Setting: "Stop Next Candle", `inv` on, `preStopAtrBuffer` 1.0, `preCancelAfterBars` 1, Points mode (stop 50
ticks = 0.50, target 300 ticks = 3.00), no trail, Fixed quantity 1. Synthetic bars, seed 33:

```
 bar      O        H        L        C     path      arm      ATR14   high + ATR x buf   low - ATR x buf
  56    990.00   990.50   988.50   989.50  O-H-L-C   PRE-S    0.50        991.00            988.00
  57    989.00   991.50   989.00   990.50  O-L-H-C   PRE-L (filter blocks it)
  58    990.50   990.50   990.50   990.50  O-L-H-C   PRE-L    0.50        991.00            990.00
  59    990.50   991.00   988.00   988.50  O-H-L-C
  60    989.50   990.50   987.50   989.50  O-H-L-C
```

- Bar 56: PRE-S arm, inverted (L1266): a BUY LIMIT (id "Long") at `preShortStopPrice` = 988.50 - 0.50 = 988.00.
- Bar 57: 57 - 56 = 1 is not > `preCancelAfterBars` 1 (L1284): the order stays.
- Bar 58: PRE-L arm, inverted (L1243): a SELL LIMIT (id "Short") at `preLongStopPrice` = 990.50 + 0.50 = 991.00;
  `lastPreStopOrderBar := 58`, so the buy limit also lives through bar 59.
- Bar 59, path O-H-L-C: the rise to 991.00 touches the sell limit: short at 991.00, stop 991.50, target 988.00.
  The fall 991.00 -> 988.00 reaches the target exactly at the bar's low: exit 'tp' at 988.00. The buy limit sits
  at that same price, 988.00 = the low.
  - **A**: after the exit the order at that price fills: long at 988.00 on bar 59 (`after_exit`), stopped at
    987.50 on bar 60.
  - **B (as delivered)**: its leg loop was `while b != cur`; after the exit `cur == b`, the loop ended and the
    order was not looked at. The long is filled one bar later, on bar 60 (988.00 again, on the way to 987.50).
- The Pine: the order is a limit order (`limit=gvInv ? preShortStopPrice : na`), `strategy()` leaves
  `backtest_fill_limits_assumption` at 0, so it fills when price touches it (the Pine's own comment L1005-1011:
  "both fill when price reaches that price"). Bar 59 trades at 988.00, so it fills on bar 59. B's own code
  filled it there whenever the exit was not on the same price (`b <= p`): the miss depended on an unrelated
  order. SPEC_gvl G4 ("a limit fills on touch") and G10 ("at one price point: ... the exit of the trade
  already open, then pending orders") say the same. **A is right.**
- Fix in `gvl_b.py`, `_walk_bar`: the leg's direction is fixed at its start and the loop runs until nothing
  more is reached (A's structure).
- Impact on real bars: none in any compared case (0 of 2,007,627 trades); it needs an exit level, a pending
  order's price and a bar extreme on one price, which float ATR distances make practically impossible; with
  `preStopAtrBuffer = 0` and Points mode on a coarse grid it happens (7 of 1,800 synthetic cases). The
  canonical module keeps A's rule; test T5 pins the traced case.

## D2. `net_r`, `h1_r`, `h2_r` when the trades have no stop (definition; A kept)

One case (BTC 60, Points mode with `slPoints = 0`): every trade equal, but A reports `net_r = NaN` and B
`0.0`. SPEC_gvl section 12: "`net_r`: sum of `r_mult` over all trades", and `r_mult` is NaN without a stop. A is
the literal sum; B skipped the NaN rows, which reads as "break-even in R" for a run where R is undefined. Not a
Pine question (the field is the replica's). B now sums plainly. The grid always has a stop.

## Places where the two were expected to differ and do not

Listed by the builders as their own readings (`gvl_a_notes.md` section 4 items 9-17, `gvl_b_notes.md` section
2); every one produced identical numbers in all cases above:

- `tvMargin` refusal on a reversal: both test `qty x fill x m / 100 > cash` with the cash before the closing
  leg, remove the order and leave the open trade. After a refusal on a leg A continues from the price where it
  was, B from the order's price: no observable difference (nothing else can lie between the two; the two
  pending orders of a run always have opposite triggers).
- `zero_qty`, `qty_capped_max` / `qty_capped_margin`, `pend_replaced` / `pend_cancelled` / `pend_open_end`,
  `after_exit`, `inherit_ebi`, `locked_bars` / `lock_days`, `exposure`: the same counts everywhere.
- The built "3"-minute radar timeframe and its volume: the same arms.
- Sessions with a `:days` suffix, wrap-around and equal start / end: the same gates.
- Order of trades: A writes a trade when it closes, B when it fills: the same list (one trade open at a time).
- `max_notional_x` with a zero account: A divides, B guards; no case has a fill at zero cash.

## Which one is canonical

`gvl.py` = A's code: A needed no fix, its leg loop is the one the Pine supports, and its kernel computes the
exit geometry and the quantity only on flat bars that carry an arm or a signal (BTC "1": 0.017 s per default
`simulate` against B's 0.025-0.08 s). Added in this stage: `path = 'mag'` (the 1-minute walk), the sub-bar
table (`sub_bars`, `get_sub`, `fake_sub_bars`), an explicit "skip the open test for a trade filled at this
open" argument of the bar walker (needed for sub-bars), permission injection (`prepare(..., _perm=)`, from B),
`split_params`. With `path = 'tv'` the canonical module gives A's output bit for bit (test T2 also re-reads the
trade lists both builders saved in stage 2: 4 cells x 8 variants, equal).

## Where A, B and the reference cannot disagree (for the auditor)

All three were written from the same brief, so they share its readings: assumption G1 (one decision run per
bar; the extra runs of `calc_on_order_fills` change nothing), the order of events at one price (G10), no
rounding of tick distances or levels (G12), TradingView's margin rule left out by default (G14),
`ta.rising` = 'any' (G15), the session rule (G17), the trailing rule (G5), the filter gate acting on the
placement only. `gvl_ref.py` re-derives the trigger of a price order from its type and side (buy stop / sell
limit: price >= P; sell stop / buy limit: price <= P) instead of taking it from the signal side, and the
bracket from the `strategy.exit` call stored per `from_entry` id, and still agrees; that covers G6 and G7, not
the list above.
