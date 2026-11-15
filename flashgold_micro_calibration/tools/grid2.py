"""Grid over a few inputs on top of a centre set. usage: python -I grid2.py <center.json> <grid.json> <out csv>"""
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # scripts are run with python -I

import pandas as pd

import oat
import sim
import sweep
import ticks


def main():
    spec = json.load(open(sys.argv[1]))
    grid = json.load(open(sys.argv[2]))
    out = sys.argv[3]
    feed = ticks.Feed("../data", float(grid.get("_spread", 12.0)))
    S = sim.Sim(feed)
    names = [k for k in grid if not k.startswith("_")]
    rows = []
    for combo in itertools.product(*[grid[k] for k in names]):
        p = sweep.base(spec.get("preset", "FlashGold_NativeReference"))
        p.update(spec["set"])
        p.update(grid.get("_set", {}))
        p.update(dict(zip(names, combo)))
        df = S.run(p)
        m = sim.metrics(df)
        m.update(oat.split_row(df))
        m.update(dict(zip(names, combo)))
        rows.append(m)
        print(" ".join(f"{k}={v}" for k, v in zip(names, combo)), f"n {m['n']} pf {m['pf']:.3f} ({m['pf_is']:.3f}/{m['pf_val']:.3f}/{m['pf_test']:.3f}) avg {m['avg']:+.1f}", flush=True)
        pd.DataFrame(rows).to_csv(out, index=False)


if __name__ == "__main__":
    main()
