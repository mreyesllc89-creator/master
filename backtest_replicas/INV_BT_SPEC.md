# Backtest replicas: add the Update 1 "Inverted direction" option

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Python 3 with numpy, pandas, numba, pyarrow. Run Python as `python3 -I`. Shared 4-CPU machine:
at most 2 processes at a time.

## Context

The repository `/home/user/master` (HEAD `d28ba97`, read-only for you) holds Pine strategies
that carry the FlashGold Direction Filter. "Update 1" added to each of them an input
`"Inverted direction: opposite side at the same entries"` (off by default; read
`/home/user/master/UPDATES.md` and the `UPDATE 1` block at the top of each `.pine`). With it on,
every entry the script would take is placed on the OPPOSITE side, on the same candle and at the
same price; all decisions (signals, the filter gate `fgfBuyOk` / `fgfSellOk` for the normal
side, blocked-signal handling, position tests) are made in the normal frame as if the script held
the mirror of its real position; exits keep their distances, mirrored.

`$W` holds verified Python replicas of three of those strategies AS THEY WERE BEFORE Update 1
(the Pine at commit `6c59b9f`): each was built twice independently, reconciled trade by trade,
audited against the Pine, and extended with a 1-minute "Bar Magnifier" path:

| strategy | Pine (ground truth, at HEAD) | replica | specs / notes |
|---|---|---|---|
| xpw | xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine | `xpw.py` (signals), `fgf.py` (filter), `engine.py` (orders, `_run`), `sweep_core.py` (`prep`, `run_cfg`, `_run_mag` = 1-minute path, `metrics_fast`), `run_tf.py` (`metrics`, windows) | `SPEC.md`, `SWEEP_SPEC.md`, `SWEEP_SPEC_2.md`, `sweep_tests.py`, `mag_ref.py` |
| apex | ApexForge_Flow_Resonance_Strategy_FGF.pine | `apex.py` (`prepare`, `simulate`, paths 'tv' / 'mag', costs 'tv' / 'ours' / 'stress') | `SPEC_AH.md`, `SWEEP_AH_SPEC.md`, `sweep_ah_tests.py`, `verify_trail_apex.py` |
| hrd | HRD_Full_Divergence_Strategy_v1_03_FGF.pine | `hrd.py` (`prepare`, `simulate`, `summary_fast`) | `SPEC_AH.md`, `SWEEP_AH_SPEC.md`, `sweep_ah_tests.py`, `verify_trail_hrd.py` |

Use `git -C /home/user/master diff 6c59b9f d28ba97 -- <pine>` to see exactly what Update 1
changed in the Pine: that diff is what the replica must now reproduce.

## Task per strategy

1. **Add the option to the replica** as a parameter (`xpwInv` / `apxInv` / `hrdInv`, alias `inv`,
   default False). With it False the replica must give exactly what it gave before (every
   saved result and every existing test must still pass; do not change default behaviour).
   With it True it must reproduce the Pine at HEAD with the option on: the same decisions, the
   order on the other side, exits as the Pine now computes them, for both fill paths ('tv' and
   the 1-minute 'mag' path) and every cost mode. The trade list must report the REAL side of
   each trade. Keep the numba kernels fast.
   - xpw: only the "Signal tick" (market) entry mode is implemented in the replica; keep that.
     `engine._run` and `sweep_core._run_mag` are kept in sync by `sweep_core.check_mag_sync()`:
     change both consistently and keep that check passing.
   - apex: the bracket of an inverted trade is the normal one mirrored about the signal candle's
     close (`stop = 2*close - S`, `limit = 2*close - T`); the same-side re-send and the blocked
     close act on the mirrored position; trailing ticks are per signal side as in the Pine.
     The replica already has a replica-only control `reverse` (swap signals before the gate)
     with `reverseStops` 'literal' / 'mirror': leave it as it is.
   - hrd: the replica already has `reverse` (= the Pine's "Reverse Trading", before the gate).
     The new option flips after the gate (see the Pine: `hrdPos`, `hrdDirOkL/S`, ids, SL / TP).
2. **Regression and property tests** in `$W/inv_tests_<strategy>.py` (print PASS / FAIL per
   test, exit non-zero on failure):
   - R1: option off reproduces the saved results: xpw `out/run_<PAIR>_<TF>.json` (tv path) and
     a sample of `out/sweep_<PAIR>_<TF>.parquet` rows (tv and mag); apex / hrd every variant in
     `out/apex_<PAIR>_<TF>.json` / `out/hrd_<PAIR>_<TF>.json` and a sample of
     `out/swah_<strategy>_<PAIR>_<TF>.parquet` rows.
   - R2: the properties the Pine header states for the filter OFF (read the header's section on
     Inverted vs the existing reverse option): where it says the two give the same real trades,
     the replica's `inv` run must equal the existing verified `reverse` / reversed-labels run
     trade by trade; where it states an exception (e.g. HRD's double-signal candle while flat),
     show that every difference is of that kind.
   - R3: mirror property on single decisions: for a sample of bars, the decision taken with the
     option on from real position p equals the mirror of the decision with it off from -p.
   - R4: 'mag' on chart "1" equals 'tv' with the option on.
3. **Runner** `$W/run_inv_<strategy>.py PAIR TF [TF ...]`: for the full windows (BTC
   1731801600..1794873600, XAU 1483315200..1529366400) and default inputs, runs
   direction {normal, inverted} x filter {off, on} x path {tv, mag} x cost {script, ours} and
   writes `$W/out/inv_<strategy>_<PAIR>_<TF>.json`: for each combination the full summary
   (trades, net_pct, pf, win_pct, max_dd_pct, the fair halves `h1r_pct` / `h2r_pct` and their
   trade counts, long / short counts, exit-kind counts, avg_bars_held, exposure where the
   module has it). "script" cost = what TradingView shows with the script's own Properties
   (xpw: none; apex: 0.04% per side; hrd: none); "ours" = XAU $0.30 per ounce per round trip,
   BTC 0.02% per side + $0.20 per round trip (the modules' existing cost modes). For xpw use
   the money model of `run_tf.metrics` / `sweep_core.metrics_fast` (10% of closed equity per
   entry). Also store, for reference, the existing reversed-label runs (filter off and on).
   Run it on BTC 60 and XAU 240 and report the numbers; the orchestrator runs the rest.
4. Write `$W/inv_<strategy>_notes.md`: what you changed, how each Pine line of the Update 1
   diff maps to the replica, every interpretation, and anything not reproduced.

Do not write inside /home/user/master. Do not edit another strategy's modules.
