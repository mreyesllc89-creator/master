"""Robustness of one input set: neighbours of every changed input, and cost stresses.

usage: python -I local.py <center.json> <out csv> [spread_pts]
center.json = {"preset": "...", "set": {...}, "neighbours": {input: [values...]}, "stress": [{"name":..., "set": {...}}]}
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
    spec = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    spread = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0
    feed = ticks.Feed("../data", spread)
    S = sim.Sim(feed)
    rows = []

    def run(name, over, kind):
        p = sweep.base(spec.get("preset", "FlashGold_NativeReference"))
        p.update(spec["set"])
        p.update(over)
        df = S.run(p)
        m = sim.metrics(df)
        m.update(oat.split_row(df))
        m.update(name=name, kind=kind)
        L = sim.label(df)
        m["routes"] = " ".join(f"{a}:{len(g)}/{sim.metrics(g)['pf']:.2f}" for a, g in L.groupby(L.scenario.map(engine.SCENARIO)))
        m["exits"] = " ".join(f"{a}:{b}" for a, b in L.exit_reason.value_counts().items())
        rows.append(m)
        print(f"{kind:9s} {name[:58]:58s} n {m['n']:6d} pf {m['pf']:.3f} ({m['pf_is']:.3f}/{m['pf_val']:.3f}/{m['pf_test']:.3f}) avg {m['avg']:+.1f} dd {m['dd']:.0f}", flush=True)
        pd.DataFrame(rows).to_csv(out, index=False)
        return df

    df = run("center", {}, "center")
    L = sim.label(df)
    L["month"] = L.entry_time.dt.to_period("M").astype(str)
    print(L.groupby("month").apply(lambda g: pd.Series({k: sim.metrics(g)[k] for k in ("n", "pf", "avg", "net")}), include_groups=False).round(2).to_string())
    print("routes:", rows[-1]["routes"])
    print("exits:", rows[-1]["exits"])
    L.to_csv(out.replace(".csv", "_center_trades.csv"), index=False)
    for item in spec.get("stress", []):
        run(item["name"], item["set"], "stress")
    for name, values in spec.get("neighbours", {}).items():
        for v in values:
            run(f"{name}={v}", {name: v}, "neighbour")


if __name__ == "__main__":
    main()
