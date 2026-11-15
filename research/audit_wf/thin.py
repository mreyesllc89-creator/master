"""How much evidence is behind a passing cell: the trade lists of its picks (hump_wf.unseen_trades, which asserts
that they equal the stored sums), duplicates across picks (the same signal taken by several picks), the profit
factor per unique signal, a weekly block bootstrap, and the share of the result in the largest trades.
Usage: [HUMP_SYMBOL=BTCUSD] python3 thin.py <work> <out_json> <TF:cond> [<TF:cond> ...]   (run from research/)"""
import json, os, sys
import numpy as np, pandas as pd
work, out_json = sys.argv[1:3]
cells = [c.split(":") for c in sys.argv[3:]]
sys.path.insert(0, "/workspace/master/research")
import hump_wf as W


def pf(r):
    r = np.asarray(r, float); w = r[r > 0].sum(); l = -r[r <= 0].sum()
    return float(w / l) if l > 0 else (float("inf") if w > 0 else float("nan"))


def boot(times, r, reps=5000, seed=1):
    wk = pd.DatetimeIndex(times).to_period("W").astype(str).values
    keys, inv = np.unique(wk, return_inverse=True)
    win = np.bincount(inv, weights=np.where(r > 0, r, 0.0), minlength=len(keys))
    los = np.bincount(inv, weights=np.where(r <= 0, -r, 0.0), minlength=len(keys))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(keys), (reps, len(keys)))
    W_ = win[idx].sum(axis=1); L_ = los[idx].sum(axis=1)
    p = np.where(L_ > 0, W_ / np.maximum(L_, 1e-300), np.inf)
    return dict(weeks=int(len(keys)), p05=float(np.percentile(p, 5)), p50=float(np.percentile(p, 50)), p95=float(np.percentile(p, 95)),
                below_1_0=float((p < 1.0).mean()), below_1_3=float((p < 1.3).mean()))


def describe(df):
    if not len(df):
        return dict(n=0)
    r = df.r.values.astype(float)
    g = df.groupby([df.entry_time, df.side]).r.mean()                    # one result per signal (mean over the picks that took it)
    srt = np.sort(r)[::-1]
    return dict(n=int(len(r)), unique_signals=int(len(g)), dup_share=float(1 - len(g) / len(r)), pf=pf(r), pf_unique=pf(g.values),
                net_r=float(r.sum()), win_rate=float((r > 0).mean()), picks=int(df.pick.nunique()),
                max_picks_on_one_signal=int(df.groupby([df.entry_time, df.side]).size().max()),
                pf_without_5_largest=pf(np.r_[srt[5:]]) if len(srt) > 5 else None,
                net_share_of_10_largest=float(srt[:10].sum() / r.sum()) if r.sum() > 0 else None)


res = {}
for tf, key in cells:
    (base, stress), P = W.unseen_trades(work, tf, key)
    last = int(max(base.year.max(), stress.year.max())) if len(base) else None
    wf_ = base[base.year < last]; fin = base[base.year == last]
    d = dict(walk_forward=describe(wf_), final=describe(fin), stress_walk_forward=describe(stress[stress.year < last]),
             by_year={int(y): describe(g) for y, g in base.groupby("year")})
    if len(wf_) > 30:
        d["walk_forward"]["bootstrap_weeks_all_trades"] = boot(wf_.entry_time.values, wf_.r.values.astype(float))
        u = wf_.groupby([wf_.entry_time, wf_.side]).r.mean().reset_index()
        d["walk_forward"]["bootstrap_weeks_unique_signals"] = boot(u.entry_time.values, u.r.values.astype(float))
    # the same signals across picks of different windows: which setups were picked, and in how many windows
    d["picks"] = {int(y): sorted(int(i) for i in g.pick.unique()) for y, g in base.groupby("year")}
    d["setups"] = {int(i): {k: P[i][k] for k in ("sides", "session", "htf", "htf_ema", "macd", "tp_mode", "tp_rr", "trail_start", "trail_dist",
                                                  "max_hold", "eod", "buf", "min_risk", "min_rr")} for i in sorted(set(base.pick.unique()))}
    res[f"{tf}:{key}"] = d
    print(tf, key, json.dumps({k: d[k] for k in ("walk_forward", "final")}, default=float), flush=True)
    print("   by year:", {y: (v["n"], v.get("unique_signals"), round(v["pf"], 3) if v["n"] else None, round(v["pf_unique"], 3) if v["n"] else None, v.get("picks")) for y, v in d["by_year"].items()}, flush=True)
json.dump(res, open(out_json, "w"), indent=1, default=float)
print("THIN_DONE")
