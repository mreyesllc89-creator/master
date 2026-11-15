"""Joint grid around a centre set, scored on the calibration and validation months only, so that the
hold-out months stay untouched until the sets are ranked.

usage: python -I joint_grid.py <center.json> <grid.json> <out csv> [spread_pts]

grid.json = {"axes": {name: [values...] | {label: {input: value, ...}, ...}}}
An axis is either one input with a list of values, or a set of named bundles of inputs (for example
the trailing variants, which need several inputs each).
"""
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # scripts are run with python -I

import numpy as np
import pandas as pd

import oat
import sim
import sweep
import ticks

HOLDOUT_FROM = pd.Timestamp("2026-06-01").value // 10**6


def main():
    spec = json.load(open(sys.argv[1]))
    grid = json.load(open(sys.argv[2]))["axes"]
    out = sys.argv[3]
    feed = ticks.Feed("../data", float(sys.argv[4]) if len(sys.argv) > 4 else 12.0)
    S = sim.Sim(feed)
    names = list(grid)
    options = []
    for k in names:
        v = grid[k]
        options.append([(str(lab), dict(st)) for lab, st in v.items()] if isinstance(v, dict) else [(x, {k: x}) for x in v])
    rows = []
    for combo in itertools.product(*options):
        p = sweep.base(spec.get("preset", "FlashGold_NativeReference"))
        p.update(spec["set"])
        for _, st in combo:
            p.update(st)
        df = S.run(p)
        m = sim.metrics(df)
        m.update(oat.split_row(df))
        early = sim.metrics(df[df.entry_ms < HOLDOUT_FROM])       # calibration + validation months together
        m.update(pf_early=early["pf"], n_early=early["n"], avg_early=early["avg"], dd_early=early["dd"])
        m.update({k: lab for k, (lab, _) in zip(names, combo)})
        rows.append(m)
        if len(rows) % 20 == 0:
            print(len(rows), flush=True)
            pd.DataFrame(rows).to_csv(out, index=False)
    d = pd.DataFrame(rows)
    d.to_csv(out, index=False)
    ok = d[(d.n_early >= 400) & (d.pf_is >= 1.0) & (d.pf_val >= 1.0)].sort_values("pf_early", ascending=False)
    print(f"{len(d)} sets, {len(ok)} with both early samples at or above 1")
    print(ok.head(25)[names + ["n", "pf", "pf_early", "pf_is", "pf_val", "pf_test", "n_test", "avg", "dd"]].round(3).to_string(index=False))
    top = ok.head(max(10, len(d) // 10))
    print("hold-out profit factor of the top tenth by early profit factor: median %.3f, share above 1: %.2f; of all sets: median %.3f, share above 1: %.2f"
          % (top.pf_test.median(), (top.pf_test > 1).mean(), d.pf_test.median(), (d.pf_test > 1).mean()))


if __name__ == "__main__":
    main()
