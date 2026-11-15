"""How the result depends on the broker's spread: rebuild the feed at several median spreads.

usage: python -I spread_study.py <variants.json> <out csv> <spread> [<spread> ...]
variants.json as for combo.py (not cumulative).
"""
import gc
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
    out = sys.argv[2]
    rows = []
    for sp in [float(x) for x in sys.argv[3:]]:
        feed = ticks.Feed("../data", sp)
        S = sim.Sim(feed)
        for item in spec["variants"]:
            p = sweep.base(item.get("preset", "FlashGold_NativeReference"))
            p.update(item["set"])
            df = S.run(p)
            m = sim.metrics(df)
            m.update(oat.split_row(df))
            m.update(name=item["name"], spread_target=sp, spread_median=feed.describe()["spread_median"])
            rows.append(m)
            print(f"spread {sp:5.1f} {item['name'][:50]:50s} n {m['n']:6d} pf {m['pf']:.3f} avg {m['avg']:.1f}", flush=True)
            pd.DataFrame(rows).to_csv(out, index=False)
        S.pool.shutdown()
        del S, feed
        gc.collect()


if __name__ == "__main__":
    main()
