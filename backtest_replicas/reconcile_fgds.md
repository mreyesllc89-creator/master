# reconcile_fgds: FlashGold Direction Strategy [Update 1], implementation A against implementation B (stage 3)

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/FlashGold_Direction_Strategy.pine` at HEAD (813 lines, Update 1 = commit
`26c8b00`; `Lnnn` are its lines). Brief: `$W/SPEC_fgds.md`. The two builds: `$W/fgds_a.py`, `$W/fgds_b.py`. Copies
as delivered: `$W/reconcile_fgds_orig/`. Nothing can be compiled or backtested in TradingView here. "Follows the
Pine" means the Pine text plus TradingView's documented order rules, as SPEC_fgds states them (F1-F13).

## Result

- **A and B, as delivered, take the same trades in every compared case.** That covers:
  - real bars: BTC and XAU, charts 1, 5, 15, 60 and 240, full windows;
  - every column of the trade list, every summary field, and the per-bar arrays (bar-close equity, position,
    and the `dsQty` value of every bar);
  - synthetic bars on a coarse price grid, where stops, targets and trailing levels fall exactly on path
    points.

  There were 0 differences in 2,600 cases (1,804,377 trades on real bars, 37,752 synthetic).
- **No disagreement, so no fix.** `fgds_a.py` and `fgds_b.py` are unchanged: `diff` against
  `reconcile_fgds_orig/` is empty for both. No reading had to be settled by hand-tracing bars against the Pine.
  The builds' own traces are in `fgds_a_check.log` and `fgds_b_check.log`: at least 3 per exit kind, with the
  bars printed.
- **The canonical module is `$W/fgds.py`.** It is B with the 1-minute path `'mag'` added. On path `'tv'` it
  equals A and B in every case of the later rounds:
  - r1: the same 800 cases as r0;
  - r2: 960 new cases with a new seed and 80 random settings per cell (2,041,144 trades);
  - the synthetic set.
- **A pure-Python reference written in this stage** (`$W/fgds_ref.py`) agrees with the canonical module on the
  1,800 synthetic cases, on both paths. It uses real prices, spells out each side's inequalities, has one order
  slot per run, and looks up its own sub-bars. It also agrees on 30 random 2-month windows of real data with
  the real 1-minute sub-bars (tests T4).

Agreement between two builds only shows that they read the Pine the same way. Readings both builds share, and
that this reconcile cannot test, are listed at the end of this file and in `fgds_notes.md` (stage 4 audits them).

## What was compared

`$W/reconcile_fgds_cmp.py PAIR TF --mods ... --seed S [--ngrid N --nwild M]`, with the cases from
`$W/fgds_cases.py`. It runs one process per cell (`$W/reconcile_fgds_run.sh`), at most two processes at a time.
It handles one filter setting at a time:
- every module prepares it. The filter series is computed once by `fgf.fgf_permissions` and shared. That is
  the verified dependency, not the thing being compared;
- then every simulate setting of that filter setting runs in every module;
- `fgf`'s cache is cleared before the next filter setting.

| cases | content |
|---|---|
| 16 fixed per cell | Default inputs ("Zone start"), filter on and off, `inv` off and on, cost `tv` / `ours` / `stress` (12 cases). Plus "Signal confirmed" and "New signal", filter on, `inv` off and on (4 cases). This covers default inputs, filter off, inv on with the filter on and off, and each cost mode. |
| grid | Points of the SPEC_fgds section 14 grid, 4 simulate settings per filter setting. Filter side: `fgfTf` set 15 / 60 / 240 (with its parent and zone timeframes), `fgfBurstAtr`, `fgfBandAtr`, `fgfLvMode`, `fgfUseZones`. Simulate side: `dsTrigger`, `inv`, `dsZoneExit`, `dsReverse`, `dsSlAtr`, and an exit style (tp3 / tp1.5 / none / trail with the cell's trail pair). Each draw has a random cost mode. |
| wild | A grid point, or the defaults, with 1-4 filter inputs and 2-6 order inputs moved outside the grid. Filter inputs: `fgfLast` "Candles" 1 / 2 / 3 / 8 and "Minutes" 30 / 90 / 240; `fgfCheck` "Candle open" / "Candle close"; `fgfAgainst` off; `fgfAllowBuy` off or `fgfAllowSell` off; `fgfTf` "" / "240" / "30"; `fgfMinAligned` 1 / 3; `fgfFlatParent`; `fgfBurstAtr` 0.35 / 0.75; filter off. Order inputs: `dsSides` "Long only" / "Short only"; trail with activation 0 to 4 ATR and offsets down to 0.005 ATR; `dsTimeStop` 1 / 2 / 3 / 5 / 10; Points mode with `dsSlPoints` 0 and `dsTpPoints` 0 among the values, trail in points; "Fixed" quantity (0 included); `dsCapMargin` off; `dsMaxQty` 0 / 0.05 / 5 / 1e9; `dsQtyStep` 1e-6 to 1; `dsAtrLen` 1 / 5 / 21 / 50; `dsRiskPct` 0 to 3; `dsMarginPct` 0 to 50; `dsTpR` 0 to 5; `dsDirection` given by name instead of `inv` |

| round | modules | per cell | cases | trades | result | logs |
|---|---|---|---|---|---|---|
| r0 | A, B as delivered | 16 fixed + 32 grid + 32 wild (seed 0) | 800 | 1,804,377 | 0 FAIL | `reconcile_fgds_r0_<PAIR>_<TF>.log` |
| r1 | A, B, canonical | the same 800 | 800 | 1,804,377 | 0 FAIL | `reconcile_fgds_r1_*.log` |
| r2 | A, B, canonical | 16 fixed + 40 grid + 40 wild (seed 1) | 960 | 2,041,144 | 0 FAIL | `reconcile_fgds_r2_*.log` |
| synthetic, as delivered | A, B | 150 seeds x 12 settings | 1,800 | 37,752 | 0 FAIL | `reconcile_fgds_synth_orig.log` |
| synthetic, final | A, B, canonical; canonical 'tv' and 'mag' against `fgds_ref.py` | the same 1,800 | 1,800 | 113,318 | 0 FAIL | `reconcile_fgds_synth.log` |

Exit kinds on real bars:
- r0: sl 752,070, zone 294,183, tp 215,095, reverse 182,105, trail 158,060, opp 115,575, time 87,167, end 122;
- r2: sl 893,493, zone 372,279, tp 229,524, reverse 171,427, trail 181,023, opp 156,885, time 36,367, end 146.

Synthetic bars (`fgds_synth.py`):
- a 0.25 price grid; Points distances that are multiples of 25 ticks; ties where high - open == open - low;
  gaps between sub-bars;
- 6,416 exits at a price equal to the bar's high or low;
- 'mag' differs from 'tv' in about two thirds of the synthetic cases. Counted on 480 of them: 317.

Comparison rules:
- floats to a relative 1e-9 (no difference reached it), everything else exactly;
- the last element of the per-bar equity array is excluded: B writes the cash after the 'end' close there, A
  the equity before it; the summary's final equity covers that point;
- columns present in only one build are not compared (B's `sl_ticks` / `tp_ticks`). The tests check them
  against the bars instead (T6 ii).

Not every random case trades:
- r0: 106 of 640 random cases have no trade, r2: 145 of 800. Causes: filter-off draws; filter settings that
  never start a zone, e.g. `fgfAgainst` off with band 0.75 and burst 0.25 (a new signal on almost every bar);
  quantity 0;
- 181 / 233 random cases ran an account down to `zero_qty` (costs 'ours' / 'stress' on the low timeframes);
- so 534 + 655 random cases with trades were compared, more than 100 per cell over the two seeds.

Timing and memory (shared 4-CPU machine, BTC 1 cell, all filter settings of the cell):
- prepare: A 36-64 s, B 21-38 s, canonical 17-33 s; simulate total 5-12 s;
- peak RSS 2.74 GB with two modules, 3.10 GB with three in r1 (A loads its own copy of the 6.5 M-row 1-minute
  file; B and the canonical module share `fgf`'s). The canonical module alone stays under 1.8 GB in every test
  and runner process (runner BTC 1: 1.43 GB).

## The choice of the canonical module

Both builds are the same mechanism, written differently. Everything below is equal: the number and order of
float operations on each path, the tie rule, the kind rule ('trail' when the trailing stop is at or beyond the
stop loss), and the floor formula.

B was taken because:
- the script run at the close is one njit function, `_decide`, so the P2 test (single decisions with the
  position negated) calls exactly what the kernel calls;
- `run_arrays` runs the kernel on injected arrays;
- it reads the bars through `fgf`'s cache, so there is one copy of the 1-minute file in memory;
- its trade list also carries the tick distances of the placing bar.

In `fgds.py`, B's code was changed in only these places:
- the docstring;
- `P` no longer keeps the full filter frame (`del F`, memory);
- `sub_bars` / `get_sub` / `fake_sub_bars` / `clear_cache` were added (the same construction and checks as
  `gvl.py`);
- `_walk_bar` was added: B's own rule-4 path and short negation, moved out of the kernel unchanged;
- the kernel's bracket step loops `_walk_bar` over the sub-bars when `mag`;
- `run_arrays` / `simulate` take the sub-bar table.

`'tv'` is bit-identical to B (r1, r2, synthetic).

## Readings shared by A and B (not testable by this reconcile; for the stage-4 audit)

Both builds were written from SPEC_fgds, which states these readings of TradingView. They agree because they
share them:
- F3: the bracket is live on the fill bar and measured from the fill price with the placing bar's ticks.
- F4 / SPEC_AH rule 4: O-H-L-C when (high - open) < (open - low), so a tie goes low first. A level passed at
  the open fills at the open.
- F5: on a rising leg the target is tested before the trail arms. The stop in force on a falling leg is the
  one at the leg's start.
- F6: at an open the script's market order (close or reversal) fills before a stop gapped through at the same
  open. Price and account are the same; only the label differs.
- F7: a reversal closes at the open as 'reverse' and opens exactly `qty`.
- F8: no rounding of levels to the tick.
- F9: TradingView's margin rule is not modelled, only counted.
- F10: `strategy.equity` = cash net of costs paid, plus the open P/L at the close.
- F11: flat at the window start; orders of the last bar dropped.

Neither build models a TradingView behaviour outside these. The Pine and SPEC_fgds disagree nowhere: both build
notes say so, and so did this stage's own reading of L694-813.
