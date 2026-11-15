"""Per-month replay cost and decision-row volume for the shipped alert (x7.5), a looser alert (x3) and the
calibrated alert (x30). One month of ticks at a time (never the whole feed). Scratch copy of tools/.
usage: python3 -I m2_months.py"""
import json
import os
import sys
import time

W = os.environ["PROTO_TOOLS"]
os.chdir(W)
sys.path.insert(0, W)
sys.dont_write_bytecode = True

import numpy as np

import engine
import sim
import sweep
import ticks

MONTHS = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-10", "2026-11"]
center = json.load(open("../results/center_final.json"))
ref = sweep.base("FlashGold_NativeReference")
cal = dict(ref)
cal.update(center["set"])
mult3 = dict(ref)
mult3["MaxTrailingMultiplier"] = 3.0
cases = {"shipped x7.5": ref, "calibrated x30": cal, "loose x3": mult3}

tot = {k: dict(ticks=0, dec=0, cand=0, sec=0.0, trades=0, alerts=0) for k in cases}
tot_ticks = 0
print(f"{'month':8s} {'ticks':>10s} {'chunks':>6s} | " + " | ".join(f"{k:^34s}" for k in cases))
for m in MONTHS:
    feed = ticks.Feed("../data", 12.0, months=[m])
    S = sim.Sim(feed, workers=2)
    tot_ticks += len(feed.t)
    line = f"{m:8s} {len(feed.t):>10,d} {len(feed.chunks):>6d} | "
    for name, p in cases.items():
        S.run(p)                                   # warm: builds fg / idx / cand caches
        t0 = time.time()
        df, cnt = S.run(p, with_counters=True)
        dt = time.time() - t0
        cand = sum(len(S._cand(c, float(p["SpeedLookbackSeconds"]), float(p["MinSpeedAlertPoints"]), float(p["MaxTrailingMultiplier"])))
                   for c in range(len(feed.chunks)))
        d = tot[name]
        d["ticks"] += len(feed.t); d["dec"] += cnt["decisions"]; d["cand"] += cand; d["sec"] += dt; d["trades"] += len(df)
        d["alerts"] += cnt["alerts"]
        line += f"dec {cnt['decisions']:>9,d} cand {cand:>8,d} {dt:5.2f}s n{len(df):>5d} | "
    print(line, flush=True)
    del S, feed
print()
for name, d in tot.items():
    print(f"{name:16s} total ticks {d['ticks']:,}  decisions {d['dec']:,} ({d['dec'] / d['ticks'] * 100:.1f}% of ticks)  "
          f"candidate ticks {d['cand']:,} ({d['cand'] / d['ticks'] * 100:.2f}%)  alerts {d['alerts']:,}  trades {d['trades']:,}  "
          f"replay wall {d['sec']:.1f}s with 2 threads (per-month, summed)")
