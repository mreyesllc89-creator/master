"""Profit factor against order delay for named input sets. usage: python -I latency_study.py <variants.json> <out csv> <ms> [<ms> ...]"""
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
    feed = ticks.Feed("../data", 12.0)
    S = sim.Sim(feed)
    rows = []
    for item in spec["variants"]:
        for ms in [float(x) for x in sys.argv[3:]]:
            p = sweep.base(item.get("preset", "FlashGold_NativeReference"))
            p.update(item["set"])
            p["X_LatencyMs"] = ms
            df = S.run(p)
            m = sim.metrics(df)
            m.update(oat.split_row(df))
            slip = (df.side * (df.entry - df.requested) / 0.01)
            m.update(name=item["name"], latency_ms=ms, entry_slip=float(slip.mean()) if len(df) else 0.0)
            # market entries of October-November 2026 (the months next to the real trades): fill against the price at the decision
            recent = df.entry_ms >= pd.Timestamp("2026-10-01").value // 10**6
            mk = slip[df.action.isin([engine.A_BM, engine.A_SM]) & recent].to_numpy()
            m["mk_n"] = int(len(mk))
            for q in (5, 25, 50, 75, 90):
                m[f"mk_p{q:02d}"] = float(np.percentile(mk, q)) if len(mk) else np.nan
            m["mk_mean"] = float(mk.mean()) if len(mk) else np.nan
            rows.append(m)
            print(f"{item['name'][:50]:50s} delay {ms:4.0f} ms n {m['n']:6d} pf {m['pf']:.3f} ({m['pf_is']:.3f}/{m['pf_val']:.3f}/{m['pf_test']:.3f}) avg {m['avg']:+.1f}", flush=True)
            pd.DataFrame(rows).to_csv(out, index=False)


if __name__ == "__main__":
    main()
