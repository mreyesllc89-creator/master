"""Direction accuracy, stage 2: holding the direction. For the best signal gates of stage 1, every hold rule, and
the precision of the held direction candle by candle: when the filter says UP, how often the close H candles later
is higher; when it says DOWN, how often it is lower; balanced = the mean of the two (BTC's drift does not count).
Rules: 0 = the last accepted signal's direction until the next one; 1 = the same, but only while price has not gone
back through the signal's level by k ATR; 2 = the existing filter: above the level UP, below it DOWN."""
import sys, json, os
import numpy as np
import numba as nb
import pandas as pd
import fgengine as E
import fgrun as R
from calib import zones_for, IS_END

OUT = "results_dir"
YEARS = (2023, 2024, 2025)
HS = (1, 3, 10)
NMIN = {1: 3000, 5: 1500, 15: 600, 30: 400, 60: 250, 120: 150, 240: 100, 480: 60, 1440: 40}
RULES = [(0, 0.0), (1, 0.0), (1, 0.5), (1, 1.0), (1, 2.0), (2, 0.0)]
GATE_KEYS = ["parent", "bmin", "bmax", "smax", "smin", "burst", "hurst", "areg", "pbmin", "psmax"]


@nb.njit(cache=True)
def hold_dir(c, atr, acc_b, acc_s, bpx, spx, rule, k):
    N = len(c)
    d = np.zeros(N, np.int8)
    lv = np.full(N, np.nan)
    sd = np.zeros(N, np.int8)      # the held signal's direction (before the rule)
    age = np.full(N, -1, np.int64)
    cur = 0
    L = np.nan
    A = np.nan
    t0 = -1
    for t in range(N):
        if acc_b[t]:
            cur = 1; L = bpx[t] if not np.isnan(bpx[t]) else c[t]; A = atr[t]; t0 = t
        elif acc_s[t]:
            cur = -1; L = spx[t] if not np.isnan(spx[t]) else c[t]; A = atr[t]; t0 = t
        lv[t] = L
        sd[t] = cur
        if cur == 0:
            continue
        age[t] = t - t0
        if rule == 0:
            d[t] = cur
        elif rule == 1:
            kk = k * (A if not np.isnan(A) else 0.0)
            if cur == 1 and c[t] > L - kk:
                d[t] = 1
            elif cur == -1 and c[t] < L + kk:
                d[t] = -1
        else:
            d[t] = 1 if c[t] > L else (-1 if c[t] < L else 0)
    return d, lv, sd, age


def gates(S, tf, p, ctx, g):
    """the quality gate per candle (stage 1's masks, at candle level)"""
    ch = ctx["ch"]
    c = ch["c"]
    fast = S.tdi(tf, 14, 2)[1]
    pfast = E.take(S.tdi(p["parent_tf"], 14, 2)[1], R.parent_index(S, tf, p), np.nan)
    atr = ctx["atr14"]
    areg = atr / pd.Series(atr).rolling(100).mean().to_numpy()
    burst = (c - np.roll(c, 1)) / atr
    fdir = ctx["fdir"]
    ob = (fast >= g["bmin"]) & (fast <= g["bmax"]) & (pfast >= g["pbmin"]) & (burst >= g["burst"])
    os_ = (fast <= g["smax"]) & (fast >= g["smin"]) & (pfast <= g["psmax"]) & (-burst >= g["burst"])
    if g["areg"] > 0:
        ob &= areg >= g["areg"]; os_ &= areg >= g["areg"]
    if g["hurst"] == 1:
        ob &= ctx["fh"] >= 0.5; os_ &= ctx["fh"] >= 0.5
    elif g["hurst"] == 2:
        ob &= ctx["fh"] < 0.5; os_ &= ctx["fh"] < 0.5
    if g["parent"] == 1:
        ob &= fdir == 1; os_ &= fdir == -1
    return ob, os_


def metrics(c, d, t_open, split, warm):
    r = {}
    yr = pd.to_datetime(t_open, unit="s", utc=True).year.to_numpy()
    N = len(c)
    idx = np.arange(N)
    base = idx >= warm
    for H in HS:
        fwd = np.full(N, np.nan)
        fwd[:-H] = c[H:] - c[:-H]
        ok = base & ~np.isnan(fwd) & (fwd != 0)
        for name, m in (("is", t_open < split), ("oos", t_open >= split)):
            mu = ok & m & (d == 1); md = ok & m & (d == -1)
            pu = (fwd[mu] > 0).mean() if mu.any() else np.nan
            pdn = (fwd[md] < 0).mean() if md.any() else np.nan
            r[f"{name}_up{H}"] = pu; r[f"{name}_dn{H}"] = pdn
            r[f"{name}_bal{H}"] = 0.5 * (pu + pdn)
            r[f"{name}_base_up{H}"] = (fwd[ok & m] > 0).mean()
        if H == 10:
            ys = []
            for y in YEARS:
                m = (t_open < split) & (yr == y)
                mu = ok & m & (d == 1); md = ok & m & (d == -1)
                if mu.sum() < 20 or md.sum() < 20:
                    ys.append(np.nan); continue
                ys.append(0.5 * ((fwd[mu] > 0).mean() + (fwd[md] < 0).mean()))
            r["is_y_min10"] = np.nanmin(ys) if not np.all(np.isnan(ys)) else np.nan
    for name, m in (("is", t_open < split), ("oos", t_open >= split)):
        mm = base & m
        r[f"{name}_cov"] = (d[mm] != 0).mean()
        flips = (d[mm][1:] != d[mm][:-1]) & (d[mm][1:] != 0)
        r[f"{name}_hold"] = (d[mm] != 0).sum() / max(1, flips.sum())   # candles per held stretch
        r[f"{name}_acc"] = np.nanmean([r[f"{name}_bal{H}"] for H in HS])
    return r


def candidates(tf, top_n=25):
    D = pd.read_parquet(f"{OUT}/D1_{tf}.parquet")
    n = NMIN[tf]
    Dn = D[(D.is_n >= n) & (D.is_nb >= n // 4) & (D.is_ns >= n // 4) & (D.is_y_nan == 0) & (D.is_y_min20 > 0.5)]
    if len(Dn) < top_n:
        Dn = D[(D.is_n >= n) & (D.is_nb >= n // 4) & (D.is_ns >= n // 4)]
    top = Dn.sort_values("is_bal20", ascending=False).head(top_n)
    cands = [dict(pm=int(r.pm), ma=int(r.ma), fm=int(r.fm), **{k: (float(r[k]) if k not in ("parent", "hurst") else int(r[k])) for k in GATE_KEYS}) for _, r in top.iterrows()]
    # the plateau (modal) gate of the top sets too
    mode = {k: top[k].mode().iloc[0] for k in ["pm", "ma", "fm"] + GATE_KEYS}
    cands.append(dict(pm=int(mode["pm"]), ma=int(mode["ma"]), fm=int(mode["fm"]), **{k: (float(mode[k]) if k not in ("parent", "hurst") else int(mode[k])) for k in GATE_KEYS}))
    # no gate: the existing filter (parent = filter timeframe, zones x1/x2/x4 with 2 aligned) = baseline 1, and the
    # other parent / zone choices = baseline 2; and the burst alone
    for pm in (1, 4, 8):
        for ma in (1, 2):
            for burst in (0.5, 1.0, 2.0):
                cands.append(dict(pm=pm, ma=ma, fm=1, parent=0, bmin=0.0, bmax=100.0, smax=100.0, smin=0.0, burst=burst, hurst=0,
                                  areg=0.0, pbmin=0.0, psmax=100.0, baseline=1 if (pm == 1 and ma == 2 and burst == 0.5) else 2))
    return cands


def run(tf, S):
    split = int(IS_END.timestamp())
    rows = []
    for ci, g in enumerate(candidates(tf)):
        p = R.params(parent_tf=tf * g["pm"], zones=zones_for(tf, 0), min_aligned=g["ma"], burst_atr=0.5,
                     fd_tf=tf * g["fm"], fd_trade=False, fd_div_on=False, fd_pull_on=False, fd_hurst_on=False)
        ctx = R.context(S, tf, p)
        ob, os_ = gates(S, tf, p, ctx, g)
        acc_b = ctx["buy"] & ob
        acc_s = ctx["sell"] & os_
        ch = ctx["ch"]
        for rule, k in RULES:
            d, lv, sd, age = hold_dir(ch["c"], ctx["atr14"], acc_b, acc_s, ctx["bpx"], ctx["spx"], rule, k)
            r = dict(ci=ci, rule=rule, k=k, baseline=int(g.get("baseline", 0)), **{kk: g[kk] for kk in ["pm", "ma", "fm"] + GATE_KEYS})
            r.update(metrics(ch["c"], d, ch["t_open"], split, warm=300))
            r["n_sig_is"] = int((acc_b | acc_s)[ch["t_open"] < split].sum())
            rows.append(r)
        print(f"[D2 tf={tf}] cand {ci}", flush=True)
    D2 = pd.DataFrame(rows)
    D2["tf"] = tf
    D2.to_parquet(f"{OUT}/D2_{tf}.parquet")
    return D2


if __name__ == "__main__":
    tf = int(sys.argv[1])
    base = pd.read_parquet("btc_1m.parquet")
    S = R.Source(base, 1)
    run(tf, S)
    print("D2 done", tf)
