#!/usr/bin/env python3
"""Diagnostics next to the protocol-2 reshuffles of nulls2.py (not part of the pre-registered rule).

For the real walk and for samples of each reshuffle: per cell the pooled unseen trades, the windows with picks, and
the number of cells with >= 100 trades (a pass needs them), so that the reshuffles' pass counts can be read against how
much the selection still finds in them.
TESTONLY (supplementary no-skill reshuffle): the picks of every window are the real ones (calibration untouched); only
the test-year results of each pick are those of a random setup of similar activity in that test year and condition
(the SETUP permutation of nulls.py, applied to the test year alone). Under "no selection skill" the picks' test results
are exchangeable with their activity block-mates', so this asks how often random choices of comparable setups pass.
Usage: python3 diag2.py <eurusd|us500> <n_setup> <n_order> <n_testonly> <out_json> [TF,TF,...]
"""
import json, os, sys, time
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nulls2 as N2
M = N2.M


def cell_stats(wins_by_v):
    vd = [M.verdict(w) for w in wins_by_v]
    n = np.array([d["n"] for d in vd]); wp = np.array([sum(1 for w in ws if w["picks"]) for ws in wins_by_v])
    npk = np.array([sum(len(w["picks"]) for w in ws) for ws in wins_by_v])
    return dict(n=n, wp=wp, npk=npk, passes=np.array([d["passes"] for d in vd]), full2=np.array([d["years_with_50_trades"] >= 2 for d in vd]))


def main():
    sym, ns, no, nt, out_json = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    only = sys.argv[6].split(",") if len(sys.argv) > 6 else None
    res = dict(symbol=sym, runs=dict(setup=ns, order=no, testonly=nt), seed=N2.SEED[sym] + 777,
               seed_note="rng = default_rng([seed, timeframe index]) per timeframe", tfs={})
    for ti, tf in enumerate(N2.TFS):
        if only and tf not in only:
            continue
        t0 = time.time()
        D = N2.load_tf(N2.WORK[sym], tf)
        V, Yn, Nn = D["V"], D["Y"], D["N"]
        rng = np.random.default_rng([N2.SEED[sym] + 777, ti])
        acc = {}
        real = cell_stats(N2.walk(D, list(range(Yn))))
        acc["real"] = [real]
        base = (np.arange(V * Yn) * Nn)[:, None]
        for kind, k_runs in (("setup", ns), ("order", no), ("testonly", nt)):
            acc[kind] = []
            for k in range(k_runs):
                if kind == "setup":
                    src = N2.setup_src(D["nact"], rng)
                    flat = (base + src.reshape(V * Yn, Nn)).ravel()
                    P = tuple(np.take(a.reshape(-1), flat).reshape(V, Yn, Nn) for a in D["cal"])
                    w = N2.walk(D, list(range(Yn)), cal_arrays=P, src=src)
                    del P, src, flat
                elif kind == "order":
                    w = N2.walk(D, [int(x) for x in rng.permutation(Yn - 1)] + [Yn - 1])
                else:
                    src = N2.setup_src(D["nact"], rng)
                    w = N2.walk(D, list(range(Yn)), src=src)               # real picks, test results of block-mates
                    del src
                acc[kind].append(cell_stats(w))
        r_tf = {}
        for kind, L in acc.items():
            if not L:
                continue
            r_tf[kind] = dict(runs=len(L), mean_trades_per_cell=float(np.mean([x["n"].mean() for x in L])),
                              cells_with_100_trades=float(np.mean([(x["n"] >= 100).sum() for x in L])),
                              cells_with_2_full_years=float(np.mean([x["full2"].sum() for x in L])),
                              windows_with_picks_per_cell=float(np.mean([x["wp"].mean() for x in L])),
                              picks_per_cell=float(np.mean([x["npk"].mean() for x in L])),
                              passes_per_run=float(np.mean([x["passes"].sum() for x in L])),
                              pass_idx=[[int(i) for i in np.flatnonzero(x["passes"])] for x in L] if kind == "testonly" else None)
        r_tf["keys"] = D["keys"]
        res["tfs"][tf] = r_tf
        print(f"{sym} {tf}: " + "; ".join(f"{k} trades/cell {v['mean_trades_per_cell']:.1f} cells>=100 {v['cells_with_100_trades']:.1f} "
                                          f"win/picks {v['windows_with_picks_per_cell']:.2f} passes/run {v['passes_per_run']:.3f}"
                                          for k, v in r_tf.items() if k != "keys") + f" ({time.time() - t0:.0f}s)", flush=True)
        json.dump(res, open(out_json, "w"))
        del D
    print("DIAG2_DONE", sym, flush=True)


if __name__ == "__main__":
    main()
