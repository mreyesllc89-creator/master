"""Does the walk-forward result of a cell say anything about its next (final) year? Across all cells of the module's
JSON: rank correlation of the pooled unseen-year PF with the final-year PF, and the final-year PF pooled over groups
of cells (passes, PF >= 1.3 with 100+ trades, the rest). Nothing is selected on the final year here.
Usage: python3 predict.py <ref_json> [<ref_json> ...]"""
import json, math, sys
import numpy as np


def ranks(x):
    o = np.argsort(x, kind="stable"); r = np.empty(len(x)); r[o] = np.arange(len(x))
    # average ranks for ties
    xs = np.asarray(x)[o]; i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[i]:
            j += 1
        r[o[i:j + 1]] = (i + j) / 2.0; i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def perm_p(a, b, reps=20000, seed=3):
    rng = np.random.default_rng(seed); r0 = spearman(a, b); ra, rb = ranks(a), ranks(b)
    cnt = 0
    for _ in range(reps):
        if np.corrcoef(ra, rng.permutation(rb))[0, 1] >= r0:
            cnt += 1
    return (cnt + 1) / (reps + 1)


for f in sys.argv[1:]:
    j = json.load(open(f)); rows = j["rows"]
    sym = j["symbol"]
    sel = [r for r in rows if r["n"] >= 100 and r["final"]["n"] >= 50 and not r["condition"].startswith("random_")]
    a = np.array([r["pf"] for r in sel]); b = np.array([r["final"]["pf"] for r in sel])
    ok = np.isfinite(a) & np.isfinite(b); a, b = a[ok], b[ok]
    print(f"{sym}: {len(rows)} cells; {len(a)} with 100+ unseen trades and 50+ final trades")
    if len(a) > 5:
        print(f"  Spearman(unseen PF, final PF) = {spearman(a, b):+.3f}, one-sided permutation p = {perm_p(a, b):.3f}")
    groups = {"passes": [r for r in rows if r["passes"]],
              "unseen PF >= 1.3 on 100+ trades, not passing": [r for r in rows if not r["passes"] and r["n"] >= 100 and r["pf"] >= 1.3],
              "unseen PF 1.1-1.3 on 100+ trades": [r for r in rows if r["n"] >= 100 and 1.1 <= r["pf"] < 1.3],
              "unseen PF < 1.1 on 100+ trades": [r for r in rows if r["n"] >= 100 and r["pf"] < 1.1],
              "fewer than 100 unseen trades": [r for r in rows if r["n"] < 100],
              "all cells": rows}
    for name, g in groups.items():
        w = sum(r["final"]["win"] for r in g); l = sum(r["final"]["loss"] for r in g); n = sum(r["final"]["n"] for r in g)
        k = sum(1 for r in g if r["final"]["n"] >= 50)
        hi = sum(1 for r in g if r["final"]["n"] >= 100 and r["final"]["pf"] >= 1.3)
        print(f"  {name:48s}: {len(g):3d} cells; final year pooled n {n:6d} PF {w / l if l else float('nan'):.3f}; "
              f"cells with 50+ final trades {k}; with final PF >= 1.3 on 100+ trades {hi}")
