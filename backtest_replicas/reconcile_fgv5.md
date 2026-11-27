# reconcile_fgv5: FlashGold v5 Strategy (BTCUSD) + FGF [Update 1], implementation A against implementation B (stage 3)

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/FlashGold_v5_Strategy_BTCUSD_FGF.pine` at HEAD (1,402 lines, Pine `//@version=5`, Update 1
= input `fgvInv`; `Lnnn` are its lines). Brief: `$W/SPEC_fgv5.md`. The two builds: `$W/fgv5_a.py`, `$W/fgv5_b.py`. Copies as
delivered: `$W/reconcile_fgv5_orig/`. Nothing can be compiled or backtested in TradingView here: "follows the Pine"
means the Pine text plus TradingView's order rules as SPEC_fgv5 states them (V1-V22).

## Result

- **A and B, as delivered, take the same trades in every compared case.** Every trade-list column, every summary
  field and the bar-close equity array were compared:
  - real bars of BTC and XAU, charts 1, 5, 15, 60 and 240, full windows;
  - 1,120 cases over two seeds;
  - 6.17 M trades.

  The only differences were the two items below. Neither is a different reading of the Pine.

  | # | difference | cases (r0) | which follows the Pine | fix |
  |---|---|---|---|---|
  | D1 | `max_notional_x` when no trade has `eq_before > 0` (e.g. the zero-trade filter-on runs on chart 60): A NaN, B 0.0 | 115 | Neither; it is a definition. The maximum over an empty set is undefined, so NaN | B (and the canonical module) now return NaN |
  | D2 | A float rounding difference, only in runs that ruined the account (net -100 %, equity 0.006-0.02 from 100,000) | 8 | A. See the note after this table | B (and the canonical module) now use Q, so their floats equal A's |

  Notes on D2:
  - Before any exit, B valued the open position as `q1 + q2`, with `q1 = Q × partPct / 100` and `q2 = Q - q1`. That
    sum can differ from Q by one ulp. A used Q.
  - In those 8 cases the error reached the 1e-9 relative tolerance in `eq_before`, `h2r_pct`, `max_notional_x` and the
    equity array.
  - The Pine's `strategy.position_size` is the filled quantity Q until an exit order fills, so A is the closer
    reading.
  - Bars, kinds, prices and quantities were equal in all 8 cases.

  After the two fixes, r1 (the same 640 cases) and r2 (480 new cases, new seed) give **0 differences between A, B and
  the canonical module**.
- **No trade-level disagreement, so no reading had to be settled between A and B.** The builds' own hand traces are
  in `fgv5_a_check.log` and `fgv5_b_check_kernel.log` / `fgv5_b_check.log`: at least 3 per exit kind, with the bars
  printed.
- **Where both builds disagree with the stage-1 probe, the probe is wrong.** This is the inverted-BTC trade counts,
  e.g. BTC 60 filter off inverted: 2,976 trades, not 2,962. Hand trace below.
- **The canonical module is `$W/fgv5.py`.** It is B, with fixes D1 and D2, the 1-minute path `'mag'` and `_config`
  factored out of `simulate`. On path `'tv'` it is bit-identical to the fixed B in every r1 and r2 case.
- **A reference written in this stage, `$W/fgv5_ref.py`, agrees with the canonical module on both paths.** It is pure
  Python, written from the Pine with exit-order objects and real prices on each side. It agrees on:
  - 30 random settings over 2-month windows with the real 1-minute sub-bars (tests_fgv5 `ref`);
  - chart 60 defaults: XAU and BTC, normal and inverted, about 6,000 trades per path.

Agreement between two builds only shows that they read the Pine the same way. The readings both builds share, which
this reconcile cannot test, are listed at the end of this file and in `fgv5_notes.md` (stage 4 audits them).

## What was compared

`$W/reconcile_fgv5_cmp.py PAIR TF --mods ... --seed S [--ngrid N --nwild M --fixed 0|1]`, with the cases from
`$W/fgv5_cases.py`. Rounds r0 and r1 ran one process per pair (`$W/reconcile_fgv5_run.sh`). r2 ran as one chain
(`$W/reconcile_fgv5_r2.sh`), which kept the second process slot free for the tests. The comparison handles one
prepare setting at a time:
- every module prepares it. The filter series is computed once by `fgf.fgf_permissions` and shared, because it is the
  verified dependency, not the thing being compared;
- then every simulate setting runs in every module;
- the signal and filter caches are cleared before the next prepare setting.

| cases | content |
|---|---|
| 16 fixed per cell (r0, r1) | **Default inputs** (Pips 30 / 5 R / runner 600, 30 % partial, Fixed 10). Filter on and **off**, `inv` off and **on**, cost **`tv` / `ours` / `stress`**: 12 cases. Plus, with the filter off and `inv` off / on: Fixed-style ATR exits (SL 1 ATR, TP 1.5 R) and the Points exits (3900 / 19500 / 58000): 4 cases. |
| grid | Points of the SPEC_fgv5 section 14 grid, 4 simulate settings per prepare setting, each with a random cost mode. Prepare side: `burstAtrMult` 0.3 / 0.5 / 1.0, `minAlignedZones` 1 / 2 / 3, `fgfOn`. Simulate side: `inv`, `entryDistAtrMult` 0 / 0.25 / 0.5, `allowReverse`, `exitStyle` (pips_default / fixed / part30 / run, with the cell's runner ladder), `slAtrMult` 0.25-2, `tpR` 1.5 / 3 / 5, `maxBarsHeld` 0 / 12, and the grid's "Risk %" sizing (1 %, maxQty 1e9, step 1e-6). |
| wild | A grid point or the defaults, with 1-4 signal / filter inputs and 2-6 order inputs moved outside the grid. These cover the SPEC_fgv5 section 13 list. Signal: `entryHoldBars` 2 (with `holdFavAtrMult` 0 / 0.1 / 0.3), `usePriorFilter` (10 / 60 / 200 bars), `useAnyCombo` (with and without the burst gate), `burstAtrMult` 0 (both signals on one bar, optionally with the zone filter off), `autoTf` off (parent 15 / 60 / 240, zones 15-D including "45"), `htfNoRepaint` off, zones 4-6 on, `DistUnit` "Points", `allowNeutralParent`, `tdiRsiLen` / `tdiFastLen`, `minAlignedZones` 0 / 3, `spreadPoints` 0 / 300. Filter: `fgfTf` 15 / 240 with their parent and zones, `fgfLvMode` "Signal close", `fgfBandAtr` 0, `fgfAgainst` off, `fgfLast` "Candles" / "Minutes", `fgfCheck` "Candle open" / "Candle close", filter off. Order: Points exits (slPoints / tpPoints 0 included, with both styles, `useTrail`), Pips exits with `pipSize` 0.1 / 1 / 10 (XAU 0.01 / 0.1 / 1) and `slPips` 0, Fixed + `useTrail` (activation 0 to 2 ATR, offset 0.005-1 ATR), `partPct` 0 / 30 / 70 / 100, `runBE` off, `tpR` 0 (no target), `maxBarsHeld` 1-10, `exitOnOpposite`, `allowReverse` off, `entryValidBars` 0 / 1 / 10, `Direction` "Long" / "Short", "Risk %" (0-3 %, maxQty 0-1e9, step 1e-6 to 1), Fixed quantities 0-10, `atrLen` 1-50, entry distances, `fgvInv` given by name instead of `inv`. |

| round | modules | per cell | cases | with trades | trades | result | logs |
|---|---|---|---|---|---|---|---|
| r0 | A, B as delivered | 16 fixed + 24 grid + 24 wild (seed 0) | 640 | 525 | 4,685,176 | 123 FAIL: D1 115, D2 8; no trade-level disagreement in bars, kinds, prices or quantities | `reconcile_fgv5_r0_<PAIR>_<TF>.log` |
| r1 | A, B fixed, canonical | the same 640 | 640 | 525 | 4,685,176 | 0 FAIL | `reconcile_fgv5_r1_*.log` |
| r2 | A, B fixed, canonical | 24 grid + 24 wild (seed 1) | 480 | 384 | 1,483,852 | 0 FAIL | `reconcile_fgv5_r2_*.log` |

Exit kinds compared:
- r0 / r1: sl 2,181,553, reverse 803,325, tp 556,788, opp 387,285, time 278,810, trail 278,092, be 143,170,
  runner 55,401, tp_part 575 (final kind), end 177;
- r2: sl 760,500, time 303,918, tp 116,719, reverse 113,194, trail 80,357, be 46,385, runner 41,979, opp 20,566,
  tp_part 125, end 109.

Comparison rules:
- floats to a relative 1e-9, everything else exactly;
- the last element of the bar-close equity array is excluded, because B writes the final equity (after the 'end'
  close) there and A the equity before it. The summary's `final_equity` covers that point;
- the trade lists have the same 30 columns in A and B.

Cases with no trade (r0 115 of 640, r2 96 of 480): the filter-on rows on chart 60 at `minAlignedZones` 2 and the
default burst (the strategy's signal is then the filter's own 60-minute signal and is always blocked: SPEC fact 2),
plus `maxQty` 0 / `fixedQty` 0 / `riskPct` 0 draws (counted in `zero_qty`).

Timing and memory (shared 4-CPU machine, BTC 1 cell, every prepare setting of the cell):
- r1: prepare A 33 s, B 44 s, canonical 45 s; simulate total 13-16 s per module;
- peak RSS: 3.19 GB with two modules (r0), 4.06 GB with three (r1), 3.90 GB (r2). This is above the brief's 3 GB
  per process in these comparison processes. Each module keeps its own copy of the 6.5 M-row BTC 1-minute file and of
  the zone bars. The canonical module alone stays under 3 GB: 2.23 GB peak in the runner's BTC 1 cell
  (`run_inv_fgv5_BTC.log`).

## The probe's inverted-BTC numbers (SPEC_fgv5 section 13): a probe bug

Both builds give 2,976 trades on BTC 60, filter off, inverted. The probe gives 2,962. The first differing trade is
trade 74 (file rows; Pips 30 / 150 / runner 600, cost 'tv'):

```
bar 109760  O 95,541  H 96,301  L 95,421  C 96,032   BUY signal; inverted: sell LIMIT at 96,221.994 ("Short", S locks)
bar 109761  O 96,042  H 96,224  L 95,915  C 96,099   (H-O) 182 >= (O-L) 127 -> path O-L-H-C:
            O -> L 95,915 (nothing: the sell limit needs price >= 96,221.994)
            L -> H 96,224: the limit fills at 96,221.994 (no slippage on a limit); SL 96,251.994, TP 96,071.994
            H -> C 96,099: TP not reached
            close: low 95,915 <= 96,221.994 - 150 -> tpHitS (the low came BEFORE the fill: V18, be_no_tp)
bar 109762  O 96,096  H 96,235  L 95,914  C 95,934   path O-H-L-C (139 < 182):
            O -> H 96,235: XS2 (7) at its breakeven stop 96,221.994 -> 96,222.044 ('be', slipped); XS1 (3) stays
            H -> L 95,914: XS1 at its TP 96,071.994 ('tp_part'): the position is flat
```

The builds close the trade at bar 109762 (exit kind 'tp_part', part 'be', exit_px 96,177.029). The probe books the
same two fills but keeps the trade "open" with quantity 0. In probe_sim.py, after a 'tp1' fill only `q1 = 0` is
set. `finish()` is not called when `q2` is already 0, so `pos` stays -1. That zero-quantity "short" makes the
mirrored read `fgvNL = inShort` true and the probe ignores BUY signals while it lasts; here it ends with a 0-unit
'reverse' at bar 109771. A position of 0 units is flat in TradingView (`strategy.position_size == 0`), so the builds
follow the Pine.

Proof that this is the whole difference: a copy of the probe with that one fix (`$W/s3_fgv5/probe_sim_fixed.py`:
`finish()` when the other part is already 0, in the path and at an open) gives exactly the canonical module's trades
and net % on BTC 60 and BTC 15, inverted, filter off and on:
- 2,976 / -1,188.7501 %;
- 12,496 / -4,541.3423 %;
- 7,310 / -2,578.3578 %.

BTC 240 still differs because the probe builds zone 3 ("960") on fgf's epoch grid, which SPEC section 13 says.

The mechanism exists only where XL2 / XS2 leaves before XL1 / XS1, i.e. in inverted `be_no_tp` trades. That is why
every normal run and every gold run matches the probe exactly, while inverted BTC runs have 0.2-0.5 % more trades
(BTC 5: 38,029 vs 37,994; BTC 1: 160,503 vs 160,486).

Two probe counters follow other definitions than SPEC_fgv5 section 12's text, which both builds implement:
- `tv_rows` counts XL1 and XL2 apart in a joint fill (BTC 60 normal: 4,414; the probe counted one row per joint fill:
  3,565);
- `both_pending_bars` counts after the stale cancel (147; the probe counted before it: 212).

## The choice of the canonical module

Both builds implement the same mechanism. They agree bit for bit after D1 / D2: the same float operations on every
fill, the same tie rules, the same kind rule ('runner' / 'trail' when the trailing stop is at or beyond the own stop).

B was taken because:
- it is the faster one: BTC 1 'tv' simulate 0.24-0.26 s against A's 0.4-0.6 s. Its `_idle` test skips bars where no
  level lies inside the bar's range, and it stays exact on every sub-bar of path 'mag', whose range lies inside the
  chart bar's;
- the script run at the close is one njit function, `_decide`, so the P2 test (single decisions with the position
  negated) calls exactly what the kernel calls;
- `prepare_arrays` runs the kernel on injected arrays, so the 29 hand-built scenarios of `fgv5_b_check_kernel.py`
  run unchanged against the canonical module on both paths;
- `simulate(full=True)` returns the bar-close equity and position arrays;
- it writes the signal side from the Pine itself (TDI, ATR, zone mapping, the signal kernel) and uses fgf only as a
  cross-check. The arrays equal `fgf._filter_series` on every row of every chart file except BTC 240 (whose zone 3
  "960" uses the daily reset, V17), so a misreading in fgf would have shown as a difference.

In `fgv5.py`, B's code was changed only in these places:
- the docstring;
- `_rem` (D2) and `max_notional_x` (D1), the same as in `fgv5_b.py`;
- `sub_bars` / `get_sub` / `fake_sub_bars` / `clear_cache` were added, with the same construction and checks as
  `gvl.py` / `fgds.py`, reading the 1-minute file through the module's own cache;
- the kernel loops B's unchanged `_walk` over the sub-bars when `mag`, with `_idle` per sub-bar;
- `_config` was factored out of `simulate`;
- `simulate` takes `sub=`.

`'tv'` is bit-identical to the fixed B (r1, r2).

## Readings shared by A and B (not testable by this reconcile; for the stage-4 audit)

Both builds were written from SPEC_fgv5, which states these readings of TradingView (section 10). They agree because
they share them:
- V2 / V3: a stop / limit entry placed at a close is live from the next bar. Its exits act from the fill on the rest
  of that leg and path, measured from the booked fill with the placing bar's tick distances.
- V4 / SPEC_AH rule 4: O-H-L-C when (high - open) < (open - low), so a tie goes low first. The first price reached
  wins. At one price, exits fill before entries. XL1 and XL2 stops at one price fill as one joint fill (kind =
  XL2's).
- V5: an exit re-sent with the same id changes nothing. XL2's switch from `loss` to `stop =` keeps its trailing state.
  XL1 takes its partial once.
- V6: XL1 = Q × partPct / 100 exactly, and XL2 (`qty_percent = 100`) covers the rest. Each fills on its own.
- V7: the trailing stop activates at `trail_points` (XL2: the TP level), moves only in favour, and the nearer of own
  stop and trail is in force. The target is tested before the trail arms on a rising leg.
- V8 / V9: a new `strategy.entry` with a pending id replaces it. OCA cancel is immediate. An opposite fill reverses
  at its booked price.
- V10 / V11 / V22: at an open, market close, then exits, then entries. After an entry fill its exits are tested at
  the fill price.
- V12: 'tv' slippage 0.05 on stop and market fills only, commission on the slipped price.
- V13 / V14: `position_avg_price` = the booked (slipped) fill, unchanged by a partial. `strategy.equity` = cash net of
  costs plus the open P/L.
- V15: no margin (v5 default 0). V16: no rounding of levels or quantities. V17: the daily-reset BTC "960".
- V18: the breakeven flag reads the whole bar's high / low (literal L1315-1318; the `be_no_tp` asymmetry).
- V20: flat at the window start, orders of the last bar dropped, 'end' at the last close as a market fill.

Neither build models a TradingView behaviour outside these. The Pine and SPEC_fgv5 disagree nowhere in the trading
logic: both build notes say so, and so did this stage's own reading of L1167-1346. This stage also checked the Pine
text mechanically (tests_fgv5 `inv`):
- the HEAD order code with `fgvInv` = false (ternaries to their else value, `fgvNL` / `fgvNS` to `inLong` /
  `inShort`, `if fgvInv ... else` to the else branch) equals the 6c59b9f text, line for line;
- the 6c59b9f order code equals the unfused original apart from `and fgfBuyOk` / `and fgfSellOk` and the FGD funnel.
