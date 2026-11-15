"""Micro-benchmark of the log-mode helpers (ns per call) on sampled decision-like ticks of one month."""
import os, sys, time
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.dont_write_bytecode = True
import numpy as np
from numba import njit
import engine, ticks, sweep, sim

feed = ticks.Feed("../data", 12.0, months=["2026-11"])
a, b = feed.chunks[0]
T = feed.t[a:b]; B = feed.bid[a:b]; A = feed.ask[a:b]
S = sim.Sim(feed, workers=1)
p = sweep.base("FlashGold_NativeReference")
cand = S._cand(0, 10.0, 37.0, 7.5)
rng = np.random.default_rng(5)
# decision-like ticks: candidate ticks (alert condition true) after the first 2 hours of the chunk
pool = cand[T[cand] > T[0] + 7200000]
idx = np.sort(rng.choice(pool, 100000, replace=False)).astype(np.int64)
print("sampled", len(idx), "ticks; mean tick spacing around them (ms):", float(np.mean(T[idx + 1] - T[idx])))

NLI = engine.NLI

@njit(cache=False)
def bench_micro(T, B, A, idx, rowi):
    for q in range(len(idx)):
        i = idx[q]; engine._lg_micro_grid(T, B, A, i, T[i], rowi)

@njit(cache=False)
def bench_opp(T, B, A, idx, rowi):
    for q in range(len(idx)):
        i = idx[q]; engine._lg_opp_grid(T, B, A, i, T[i], rowi)

@njit(cache=False)
def bench_drift(T, idx, rowi):
    for q in range(len(idx)):
        i = idx[q]; engine._lg_drift(T, i, T[i], rowi)

@njit(cache=False)
def bench_cp(T, B, A, idx):
    s = 0
    for q in range(len(idx)):
        r = engine._cp_stats(T, B, A, idx[q], 0.01)
        s += r[2]
    return s

@njit(cache=False)
def bench_fb(T, idx):
    s = 0
    for q in range(len(idx)):
        i = idx[q]
        j = engine._first_at_or_after(T, i, T[i] - 1000)
        s += j
    return s

rowi = np.zeros(NLI, np.int32)
for name, fn, args, n in [("micro grid (6 lookbacks, 60 s max)", bench_micro, (T, B, A, idx, rowi), len(idx)),
                           ("opposite-pressure grid (2/3/5/10 s)", bench_opp, (T, B, A, idx, rowi), len(idx)),
                           ("prior drift, 4 horizons", bench_drift, (T, idx, rowi), len(idx)),
                           ("_cp_stats (60 s + 300 s tape)", bench_cp, (T, B, A, idx[:20000]), 20000),
                           ("1 s burst lookback", bench_fb, (T, idx), len(idx))]:
    fn(*args)                                  # compile
    t0 = time.perf_counter(); fn(*args); dt = time.perf_counter() - t0
    print(f"{name:40s} {dt / n * 1e9:9.0f} ns per call")
