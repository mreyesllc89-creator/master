"""Stage 1: random search. usage: python sweep.py <n_signal_sets_per_tf> <n_exit_sets_per_signal> [seed]
Every run is scored on the in-sample years (whole, first half, second half) and on the held-out year.
The held-out columns (oos_*) are stored but must not be used to pick settings."""
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

import engine as E
from space import *

M1 = None
CH = {}


def init():
    global M1
    M1 = E.load("../data/BTCUSDT_1m.npz")
    for tf in TIMEFRAMES:
        CH[tf] = E.resample(M1["o"], M1["h"], M1["l"], M1["c"], tf)


def job(a):
    tf, seed, n_exit = a
    rng = np.random.default_rng(seed)
    sig = sample_signal(rng)
    s = E.make_signals(M1, tf, sig, chart=CH[tf])
    rows = []
    for _ in range(n_exit):
        ex = sample_exit(rng)
        r = E.run(M1, tf, sig, ex, spread=BASE_SPREAD, pess=True, signals=s)
        row = dict(tf=tf, **sig, **ex)
        for name, lo, hi in (("is", IS_START, IS_END), ("h1", IS_START, IS_MID), ("h2", IS_MID, IS_END), ("oos", IS_END, OOS_END)):
            st = E.stats(r, M1["t"], lo, hi)
            for k in ("n", "net", "pf", "t", "dd", "win"):
                row[f"{name}_{k}"] = st[k]
        rows.append(row)
    return rows


if __name__ == "__main__":
    n_sig, n_exit = int(sys.argv[1]), int(sys.argv[2])
    seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    jobs = [(tf, seed0 * 1_000_000 + tf * 10_000 + i, n_exit) for tf in TIMEFRAMES for i in range(n_sig)]
    out = []
    with Pool(4, initializer=init) as pool:
        for k, rows in enumerate(pool.imap_unordered(job, jobs, chunksize=4)):
            out.extend(rows)
            if k % 200 == 0:
                print(k, "/", len(jobs), flush=True)
    df = pd.DataFrame(out)
    df.to_csv(f"../results/sweep_seed{seed0}.csv", index=False)
    print("runs", len(df))
