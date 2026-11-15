"""Size of the shadow tick table: every tick that lies in a potential alert window (candidate tick .. start of its lookback window + hold),
i.e. every tick the engine COULD evaluate under some direction/gate input set with the same alert inputs."""
import os, sys, json
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.dont_write_bytecode = True
import numpy as np
import engine as E, sim, sweep, ticks

MONTHS = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-10", "2026-11"]
center = json.load(open("../results/center_final.json"))
ref = sweep.base("FlashGold_NativeReference")
cal = dict(ref); cal.update(center["set"])
mult = {"x3": 3.0, "x7.5 shipped": 7.5, "x15": 15.0, "x20": 20.0, "x30 calibrated": 30.0}
tot = {k: dict(ticks=0, union=0, dec=0, cand=0) for k in mult}
for m in MONTHS:
    feed = ticks.Feed("../data", 12.0, months=[m])
    S = sim.Sim(feed, workers=2)
    for name, mu in mult.items():
        p = dict(ref); p["MaxTrailingMultiplier"] = mu
        if name.startswith("x30"):
            p = dict(cal)
        hold_ms = int(p["SpeedAlertHoldSeconds"] * 1000)
        union = 0; dec_est = 0; ncand = 0
        for c, (a, b) in enumerate(feed.chunks):
            T = feed.t[a:b]
            idx = S._idx(c, float(p["SpeedLookbackSeconds"]))
            cand = S._cand(c, float(p["SpeedLookbackSeconds"]), float(p["MinSpeedAlertPoints"]), float(p["MaxTrailingMultiplier"]))
            ncand += len(cand)
            if len(cand) == 0:
                continue
            st = T[cand]
            en = T[idx[cand]] + hold_ms
            # merge (starts sorted, ends non-decreasing)
            new = np.ones(len(cand), bool)
            new[1:] = st[1:] > en[:-1]
            grp = np.cumsum(new) - 1
            gs = st[new]
            ge = np.maximum.reduceat(en, np.flatnonzero(new))
            i0 = np.searchsorted(T, gs, side="left"); i1 = np.searchsorted(T, ge, side="right")
            union += int((i1 - i0).sum())
        tot[name]["ticks"] += len(feed.t); tot[name]["union"] += union; tot[name]["cand"] += ncand
    del S, feed
for name, d in tot.items():
    print(f"{name:16s} ticks {d['ticks']:,}  candidate ticks {d['cand']:,}  union of potential alert windows {d['union']:,} ticks = {100 * d['union'] / d['ticks']:.1f}% of all ticks")
