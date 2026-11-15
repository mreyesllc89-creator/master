"""Replay a list of named input sets (JSON) on the whole feed and print per-split results.

usage: python -I combo.py <preset> <variants.json> <out csv> [spread_pts]
variants.json = [{"name": "...", "set": {input: value, ...}}, ...]; "cumulative": true applies each
set on top of the previous ones.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # scripts are run with python -I

import numpy as np
import pandas as pd

import engine
import oat
import sim
import sweep
import ticks


def main():
    preset, spec_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    spread = float(sys.argv[4]) if len(sys.argv) > 4 else 12.0
    spec = json.load(open(spec_path))
    feed = ticks.Feed("../data", spread)
    S = sim.Sim(feed)
    rows = []
    acc = {}
    for item in spec["variants"]:
        if spec.get("cumulative"):
            acc.update(item["set"])
            over = dict(acc)
        else:
            over = dict(item["set"])
        fills = {"strict": sweep.STRICT_FILLS, "tester": sweep.TESTER_FILLS}.get(item.get("fills", ""), sweep.REAL_FILLS)
        p = sweep.base(item.get("preset", preset), fills=fills)
        p.update(over)
        df = S.run(p)
        m = sim.metrics(df)
        m.update(oat.split_row(df))
        m["name"] = item["name"]
        m["exits"] = " ".join(f"{a}:{b}" for a, b in df["reason"].map(engine.REASON).value_counts().items())
        rows.append(m)
        print(f"{item['name'][:70]:70s} n {m['n']:6d} pf {m['pf']:.3f} (is {m['pf_is']:.3f} val {m['pf_val']:.3f} test {m['pf_test']:.3f}) "
              f"avg {m['avg']:.1f} net {m['net']:.0f}", flush=True)
        pd.DataFrame(rows).to_csv(out, index=False)


if __name__ == "__main__":
    main()
