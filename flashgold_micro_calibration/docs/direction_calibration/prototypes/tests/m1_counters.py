"""Measure, on one month of ticks, how many direction evaluations (C_DECISIONS) the engine does, how many
ticks it touches, and how long a replay takes. Runs on a scratch COPY of tools/ (byte-identical to the repo).
usage: python3 -I m1_counters.py <month> [workers]"""
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
import params
import sim
import sweep
import ticks

month = sys.argv[1]
workers = int(sys.argv[2]) if len(sys.argv) > 2 else 2

t0 = time.time()
feed = ticks.Feed("../data", 12.0, months=[month])
print(f"feed {month}: {len(feed.t):,} ticks, {len(feed.chunks)} chunks, load+rebuild {time.time() - t0:.1f}s")
nbytes = sum(a.nbytes for a in (feed.t, feed.bid, feed.ask, feed.mid))
print(f"feed arrays {nbytes / 1e6:.0f} MB = {nbytes / len(feed.t):.1f} bytes/tick (t,bid,ask,mid)")
S = sim.Sim(feed, workers=workers)
ep_bytes = sum(e.nbytes for e in S.ep)
print(f"ep_start arrays {ep_bytes / 1e6:.0f} MB")

center = json.load(open("../results/center_final.json"))
variants = {
    "reference preset (shipped)": sweep.base("FlashGold_NativeReference"),
}
pc = sweep.base("FlashGold_NativeReference")
pc.update(center["set"])
variants["calibrated preset (center_final)"] = pc
p_f = dict(pc)
p_f["MaxTrailingMultiplier"] = 7.5     # shipped alert (superset of the calibrated alert windows)
variants["calibrated scoring but shipped alert x7.5"] = p_f
p_f2 = dict(sweep.base("FlashGold_NativeReference"))
p_f2["UseFlashGoldDirectionFilter"] = 0
variants["reference preset, FlashGold filter off"] = p_f2

for name, p in variants.items():
    t1 = time.time()
    df, cnt = S.run(p, with_counters=True)
    dt1 = time.time() - t1
    t2 = time.time()
    df, cnt = S.run(p, with_counters=True)
    dt2 = time.time() - t2
    cand = sum(len(S._cand(c, float(p["SpeedLookbackSeconds"]), float(p["MinSpeedAlertPoints"]), float(p["MaxTrailingMultiplier"])))
               for c in range(len(feed.chunks)))
    print(f"\n[{name}] trades {len(df)}  first run {dt1:.1f}s (includes numba load/compile + cand/fg build), second run {dt2:.2f}s")
    print(f"  candidate ticks (alert condition true) {cand:,} = {100.0 * cand / len(feed.t):.2f}% of ticks")
    print("  counters:", {k: int(v) for k, v in cnt.items() if v})
