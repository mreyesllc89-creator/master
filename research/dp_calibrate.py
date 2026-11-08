#!/usr/bin/env python3
"""
Calibration search for the Danny Phantom EA (replica in dp_engine.py), same method as XLZC:
  * choose on 2025 only: score = worst half-year PF (2025H1, 2025H2), each half >= MIN_TRADES,
    smoothed by the median of the grid neighbours (one step on one parameter)
  * 2026 (Jan-May) is out of sample and only reported
Stages:
  A  entry structure x timeframe x direction, shipped exits
  B  exits (SL/TP/time/trailing/dead) and the gold time filters on the best structures
  V  verification of finalists: bar-close model, worst-case fills, wider spread
Usage: python3 dp_calibrate.py <SYMBOL> <stage> <out_dir>
"""
import itertools
import json
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

import dp_engine as D

MIN_TRADES = 30
HALVES = [("h1", "2025-01-01", "2025-07-01"), ("h2", "2025-07-01", "2026-01-01")]
OOS = ("oos", "2026-01-01", "2027-01-01")
MK = None
SYM = None


def init(sym):
    global MK, SYM
    SYM = sym
    MK = D.Market(sym)


def base_profile(sym):
    return D.GOLD_PROFILE if sym == "XAUUSD" else D.BTC_PROFILE


def evaluate(job):
    tf, cfg = job
    df = MK.run(tf, cfg)
    t = df.entry_time.values
    row = {"tf": tf, **{k: v for k, v in cfg.items() if k in VARY}}
    for name, a, b in HALVES + [OOS]:
        m = (t >= np.datetime64(a)) & (t < np.datetime64(b))
        s = D.stats(df.pnl.values[m])
        row[f"{name}_n"] = s["trades"]; row[f"{name}_pf"] = s["pf"]; row[f"{name}_net"] = s["net"]
        row[f"{name}_r"] = float(np.nansum(df.r.values[m]))
    s = D.stats(df.pnl.values)
    row["all_n"] = s["trades"]; row["all_pf"] = s["pf"]; row["all_net"] = s["net"]
    row["all_r"] = float(np.nansum(df.r.values))
    return row


VARY = ["fade", "zlen", "delta", "min_retest", "max_age", "use_ema", "mode", "ztrend", "sl", "tpr",
        "tstop", "trail", "tact", "tdst", "dead", "dead_bars", "be", "gold_filters", "lc", "cost", "intrabar",
        "worst", "window"]

GRID_A = dict(tf=[1, 2, 3, 5, 10, 15, 30], fade=[1, 0], zlen=[20, 50, 100], delta=[1.2, 1.5, 2.0, 3.0],
              min_retest=[1, 3], max_age=[50, 200], use_ema=[0, 1], mode=[0, 1])
GRID_B = dict(sl=[0.8, 1.2, 1.6, 2.0, 3.0], tpr=[1.0, 1.5, 2.0, 3.0, 4.1667], tstop=[0, 20, 50, 100],
              trail=[(0, 4.0, 0.2), (1, 1.0, 0.5), (1, 2.0, 1.0)])


def score(df, keys):
    """Worst 2025 half-year PF, median-smoothed over grid neighbours."""
    ok = (df.h1_n >= MIN_TRADES) & (df.h2_n >= MIN_TRADES)
    raw = np.where(ok, np.minimum(df.h1_pf, df.h2_pf), 0.0)
    df = df.assign(raw=raw)
    levels = {k: sorted(df[k].dropna().unique()) for k in keys}
    idx = {tuple(r): i for i, r in enumerate(df[keys].itertuples(index=False, name=None))}
    sm = np.zeros(len(df))
    for i, r in enumerate(df[keys].itertuples(index=False, name=None)):
        vals = [raw[i]]
        for p, k in enumerate(keys):
            lv = levels[k]; at = lv.index(r[p])
            for d in (-1, 1):
                if 0 <= at + d < len(lv):
                    nb = list(r); nb[p] = lv[at + d]
                    j = idx.get(tuple(nb))
                    if j is not None:
                        vals.append(raw[j])
        sm[i] = np.median(vals)
    return df.assign(score=sm)


def run_jobs(jobs, out_csv):
    with Pool(4, initializer=init, initargs=(SYM_ARG,)) as pool:
        rows = []
        for i, row in enumerate(pool.imap_unordered(evaluate, jobs, chunksize=8)):
            rows.append(row)
            if i % 500 == 0:
                print(i, len(jobs), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    return df


def stage_a(out):
    prof = base_profile(SYM_ARG)
    jobs = []
    for vals in itertools.product(*GRID_A.values()):
        p = dict(zip(GRID_A.keys(), vals))
        tf = p.pop("tf")
        jobs.append((tf, dict(prof, **p)))
    print(len(jobs), "stage A jobs", flush=True)
    df = run_jobs(jobs, os.path.join(out, "stageA.csv"))
    keys = ["tf"] + [k for k in GRID_A if k != "tf"]
    df = score(df, keys).sort_values("score", ascending=False)
    df.to_csv(os.path.join(out, "stageA_scored.csv"), index=False)
    print(df.head(25).to_string())


def stage_b(out, top=int(os.environ.get("DP_TOP", "30"))):
    prof = base_profile(SYM_ARG)
    a = pd.read_csv(os.path.join(out, "stageA_scored.csv"))
    keysA = [k for k in GRID_A if k != "tf"]
    picks = a.head(top)
    jobs = []
    filt = [True, False] if SYM_ARG == "XAUUSD" else [False]
    for _, r in picks.iterrows():
        base = dict(prof, **{k: (type(prof[k])(r[k])) for k in keysA})
        for sl, tpr, ts, tr, gf in itertools.product(GRID_B["sl"], GRID_B["tpr"], GRID_B["tstop"],
                                                     GRID_B["trail"], filt):
            jobs.append((int(r.tf), dict(base, sl=sl, tpr=tpr, tstop=ts, trail=tr[0], tact=tr[1], tdst=tr[2],
                                         gold_filters=gf)))
    print(len(jobs), "stage B jobs", flush=True)
    df = run_jobs(jobs, os.path.join(out, "stageB.csv"))
    df["struct"] = df[["tf"] + keysA].astype(str).agg("|".join, axis=1)
    df["trail_key"] = df[["trail", "tact", "tdst"]].astype(str).agg("|".join, axis=1)
    parts = []
    for (st, gf), g in df.groupby(["struct", "gold_filters"]):
        g = g.copy()
        g["trail_ix"] = g["trail_key"].map({k: i for i, k in enumerate(sorted(g.trail_key.unique()))})
        parts.append(score(g, ["sl", "tpr", "tstop", "trail_ix"]))
    df = pd.concat(parts).sort_values("score", ascending=False)
    df.to_csv(os.path.join(out, "stageB_scored.csv"), index=False)
    cols = ["tf"] + keysA + ["sl", "tpr", "tstop", "trail", "tact", "tdst", "gold_filters", "h1_n", "h1_pf",
                            "h2_n", "h2_pf", "score", "oos_n", "oos_pf", "all_n", "all_pf"]
    print(df[cols].head(30).to_string())


def stage_v(out, top=15):
    prof = base_profile(SYM_ARG)
    b = pd.read_csv(os.path.join(out, "stageB_scored.csv"))
    keys = [k for k in GRID_A if k != "tf"] + ["sl", "tpr", "tstop", "trail", "tact", "tdst", "gold_filters"]
    picks = b.drop_duplicates("struct").head(top)
    jobs = []
    variants = {"base": {}, "barclose": dict(intrabar=0), "worst": dict(worst=1)}
    for i, r in picks.iterrows():
        cfg = dict(prof)
        for k in keys:
            cfg[k] = type(prof[k])(r[k]) if not isinstance(prof[k], bool) else bool(r[k])
        for vn, ch in variants.items():
            jobs.append((int(r.tf), dict(cfg, **ch, _pick=int(i), _variant=vn)))
    rows = []
    with Pool(4, initializer=init, initargs=(SYM_ARG,)) as pool:
        for row, job in zip(pool.map(evaluate, jobs), jobs):
            row["pick"] = job[1]["_pick"]; row["variant"] = job[1]["_variant"]; rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out, "stageV.csv"), index=False)
    print(df.pivot_table(index="pick", columns="variant", values=["h1_pf", "h2_pf", "oos_pf", "all_n"]).to_string())


if __name__ == "__main__":
    SYM_ARG, stage, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    D.Market  # numba compiles on first run in each worker (cached on disk after the first)
    {"A": stage_a, "B": stage_b, "V": stage_v}[stage](out)
