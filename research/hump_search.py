#!/usr/bin/env python3
"""
Calibration of the hump method (hump_engine.py). Chosen on 2025 only (worst half-year PF in R,
>= MIN_TRADES per half); 2026 Jan-May is out of sample. Random sample of the whole space, then
coordinate refinement of the best points with a one-step-neighbour median.
Usage: python3 hump_search.py R <out> [n]   |   python3 hump_search.py L <out>
"""
import json, os, random, sys
from multiprocessing import Pool
import numpy as np, pandas as pd
import hump_engine as H

MIN_TRADES = 40
SPACE = dict(
    tf=["M1", "M2", "M3", "M5"], sides=[0, -1, 1],
    big_mult=[1.0, 1.25, 1.5, 2.0, 2.5, 3.0], hist=[10, 20, 40], big_min_bars=[3, 5, 8, 12],
    stoch_req=[1, 0], pb_min_bars=[1, 2, 3, 4, 6], pb_max_ratio=[0.25, 0.4, 0.6, 0.8, 1.0, 1.5],
    break_ratio=[0.6, 0.8, 1.0, 1.5, 99.0], max_signals=[1, 2, 3, 99], trend_max_bars=[40, 80, 120, 240, 100000],
    session=list(H.SESSIONS), htf=["none", "H1", "H4"],
    buf=[0.1, 0.3, 0.6, 1.0, 1.5], anticip=[0.0, 0.1, 0.2, 0.35], min_rr=[0.3, 0.6, 0.8, 1.0, 1.5],
    tp_mode=[0, 1], tp_rr=[1.0, 1.5, 2.0, 3.0], trail_start=[0.0, 0.5, 1.0, 1.5], trail_dist=[0.3, 0.5, 1.0],
    min_risk=[0.3, 0.5, 1.0, 2.0],
)
if H.SYMBOL == "BTCUSD":          # price distances in BTC dollars; the market trades through the weekend
    SPACE.update(buf=[5, 10, 20, 35, 50], min_risk=[10, 20, 35, 70], tf=["M1", "M2", "M3", "M5", "M10", "M15"])
BASE = dict(skip_big_pb=1, max_spread=1e9) if H.SYMBOL == "BTCUSD" else {}
if os.environ.get("HUMP_SPACE") == "2":      # second gold pass: v1.31 rules on, plus what the first pass held fixed
    BASE = dict(skip_big_pb=1, weekend_close=1)
    SPACE.update(tf=["M1", "M2", "M3", "M5", "M10", "M15"], htf=["none", "M15", "M30", "H1", "H4", "D1"],
                 htf_ema=[20, 50, 100, 200], macd=["12-26", "8-17", "10-22", "16-35"], stoch_k=[5, 7, 10, 14],
                 stoch_lv=["20-80", "25-75", "15-85"], max_hold=[0, 60, 120, 240, 480, 1440],
                 eod=[-1, 1260, 1320, 1380])
CATEGORICAL = ("tf", "sides", "session", "htf", "tp_mode", "stoch_req", "macd", "stoch_lv", "eod")


def engine_cfg(c):
    """Translate the combined search keys into engine settings."""
    c = dict(c)
    if "macd" in c:
        f, sl = c.pop("macd").split("-"); c["macd_fast"], c["macd_slow"] = int(f), int(sl)
    if "stoch_lv" in c:
        lo, hi = c.pop("stoch_lv").split("-"); c["stoch_lo"], c["stoch_hi"] = float(lo), float(hi)
    return c
MK = None


def init():
    global MK
    MK = H.Market()


def measure(p, extra=None):
    c = dict(BASE); c.update(p)
    if extra: c.update(extra)
    df = MK.run(engine_cfg(c))
    t = df.entry_time.values; r = df.r.values
    row = {}
    for name, a, b in [("h1", "2025-01-01", "2025-07-01"), ("h2", "2025-07-01", "2026-01-01"),
                       ("oos", "2026-01-01", "2027-01-01"), ("oos_fm", "2026-02-01", "2027-01-01"),
                       ("all", "2000-01-01", "2100-01-01")]:
        m = (t >= np.datetime64(a)) & (t < np.datetime64(b))
        s = H.stats(r[m])
        row[f"{name}_n"] = s["n"]; row[f"{name}_pf"] = s["pf"]; row[f"{name}_net"] = s["net"]; row[f"{name}_dd"] = s["dd"]
    ok = row["h1_n"] >= MIN_TRADES and row["h2_n"] >= MIN_TRADES
    row["raw"] = float(min(row["h1_pf"], row["h2_pf"])) if ok else 0.0
    return row


def ev(p):
    return {**p, **measure(p)}


def refine(p):
    seen = {}
    def sc(q):
        k = json.dumps(q, sort_keys=True)
        if k not in seen: seen[k] = measure(q)
        return seen[k]["raw"]
    best = dict(p); bs = sc(best)
    for rnd in range(2):
        imp = False
        keys = list(SPACE); random.Random(rnd).shuffle(keys)
        for k in keys:
            for v in SPACE[k]:
                if v == best[k]: continue
                q = dict(best); q[k] = v; s = sc(q)
                if s > bs + 0.01: best, bs, imp = q, s, True
        if not imp: break
    nb = []
    for k, lv in SPACE.items():
        if k in CATEGORICAL: continue
        if k == "tp_rr" and best["tp_mode"] == 0: continue                              # inert
        if k in ("anticip",) and best["tp_mode"] == 1: continue
        if k == "trail_dist" and best["trail_start"] == 0: continue
        i = lv.index(best[k])
        for d in (-1, 1):
            if 0 <= i + d < len(lv):
                q = dict(best); q[k] = lv[i + d]; nb.append(sc(q))
    res = {**best, **seen[json.dumps(best, sort_keys=True)]}
    res["nb_median"] = float(np.median(nb + [bs])); res["nb_min"] = float(min(nb)); res["nb_n"] = len(nb)
    return res


def cast(v, lv):
    for x in lv:
        if str(x) == str(v) or (not isinstance(x, str) and float(x) == float(v)): return x
    raise ValueError((v, lv))


if __name__ == "__main__":
    ph, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    if ph == "R":
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 20000
        rng = random.Random(7)
        pts = [{k: rng.choice(v) for k, v in SPACE.items()} for _ in range(n)]
        rows = []
        with Pool(4, initializer=init) as pool:
            for i, r in enumerate(pool.imap_unordered(ev, pts, chunksize=16)):
                rows.append(r)
                if i % 2000 == 0:
                    print(i, n, flush=True)
        df = pd.DataFrame(rows).sort_values("raw", ascending=False)
        df.to_csv(os.path.join(out, "R.csv"), index=False)
    else:
        df = pd.read_csv(os.path.join(out, "R.csv"))
        starts = [{k: cast(r[k], SPACE[k]) for k in SPACE} for _, r in df.head(24).iterrows()]
        with Pool(4, initializer=init) as pool:
            rows = pool.map(refine, starts, chunksize=1)
        pd.DataFrame(rows).sort_values("nb_median", ascending=False).to_csv(os.path.join(out, "L.csv"), index=False)
    print("done")
