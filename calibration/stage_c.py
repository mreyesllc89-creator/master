"""Stage C: exits and re-entry by simulation (ATR-unit exits, fees), per timeframe, for a chosen entry config."""
import sys, json, time, itertools
import numpy as np
import pandas as pd
import fgengine as E
import fgrun as R
from calib import zones_for, IS_END

import os
FEE = 0.0005      # per side, fraction of price (0.05%)
MAG = os.environ.get("MAG") == "1"   # 1-minute intrabar paths
MIN_TRADES = 80


def apply_filters(ctx, S, tf, p, f):
    """Entry filters of stage B applied as masks on the raw signals (the Pine gates)."""
    ch = ctx["ch"]
    c = ch["c"]
    fast = S.tdi(tf, 14, 2)[1]
    par = S.bars(p["parent_tf"])
    pfast = E.take(S.tdi(p["parent_tf"], 14, 2)[1], R.parent_index(S, tf, p), np.nan)
    atr = ctx["atr14"]
    areg = atr / pd.Series(atr).rolling(100).mean().to_numpy()
    burst = (c - np.roll(c, 1)) / atr
    okb = (fast >= f.get("bmin", 0)) & (fast <= f.get("bmax", 100)) & (pfast >= f.get("pbmin", 0)) & (burst >= f.get("burst", 0.5))
    oks = (fast <= f.get("smax", 100)) & (fast >= f.get("smin", 0)) & (pfast <= f.get("psmax", 100)) & (-burst >= f.get("burst", 0.5))
    if f.get("areg", 0) > 0:
        okb &= areg >= f["areg"]; oks &= areg >= f["areg"]
    if f.get("hurst", 0) == 1:
        okb &= ctx["fh"] >= 0.5; oks &= ctx["fh"] >= 0.5
    elif f.get("hurst", 0) == 2:
        okb &= ctx["fh"] < 0.5; oks &= ctx["fh"] < 0.5
    # re-entry permission: the same gates without the burst (a re-entry bar has no burst), plus the zone side
    rb = (fast >= f.get("bmin", 0)) & (fast <= f.get("bmax", 100)) & (pfast >= f.get("pbmin", 0))
    rs = (fast <= f.get("smax", 100)) & (fast >= f.get("smin", 0)) & (pfast <= f.get("psmax", 100))
    if f.get("areg", 0) > 0:
        rb &= areg >= f["areg"]; rs &= areg >= f["areg"]
    if f.get("hurst", 0) == 1:
        rb &= ctx["fh"] >= 0.5; rs &= ctx["fh"] >= 0.5
    elif f.get("hurst", 0) == 2:
        rb &= ctx["fh"] < 0.5; rs &= ctx["fh"] < 0.5
    out = dict(ctx)
    out["re_ok_l"] = ctx["fd_buy_ok"] & rb & ctx["zbuy"]
    out["re_ok_s"] = ctx["fd_sell_ok"] & rs & ctx["zsell"]
    out["fd_buy_ok"] = ctx["fd_buy_ok"] & okb
    out["fd_sell_ok"] = ctx["fd_sell_ok"] & oks
    return out


def metrics(tr, atr_at_entry, split_ts, t_entry):
    r = {}
    pnl = tr.pnl.to_numpy() / atr_at_entry
    is_ = t_entry < split_ts
    for name, m in (("is", is_), ("oos", ~is_)):
        x = pnl[m]
        n = len(x)
        r[name + "_n"] = n
        if n < 3:
            r[name + "_mean"] = np.nan; r[name + "_t"] = np.nan; r[name + "_pf"] = np.nan; r[name + "_dd"] = np.nan; r[name + "_win"] = np.nan
            continue
        r[name + "_mean"] = x.mean()
        r[name + "_t"] = x.mean() / x.std() * np.sqrt(n)
        g = x[x > 0].sum(); l = -x[x <= 0].sum()
        r[name + "_pf"] = g / l if l > 0 else np.inf
        eq = np.cumsum(x)
        r[name + "_dd"] = (np.maximum.accumulate(eq) - eq).max()
        r[name + "_win"] = (x > 0).mean()
        r[name + "_sum"] = x.sum()
    return r


def run_grid(tf, S, entry, filt, out_path):
    p0 = R.params(parent_tf=tf * entry["pm"], zones=zones_for(tf, entry.get("zk", 0)), min_aligned=entry["ma"],
                  burst_atr=0.5, fd_tf=tf * entry.get("fm", 1), fd_trade=bool(filt.get("parent", 0)),
                  fd_div_on=False, fd_pull_on=False, fd_hurst_on=False, exit_mode="ATR",
                  fee_pct=FEE, slip_ticks=0.0)
    ctx0 = R.context(S, tf, p0)
    ctx = apply_filters(ctx0, S, tf, p0, filt)
    split = int(IS_END.timestamp())
    atr = ctx["atr14"]
    rows = []
    mag = S.bars(1) if MAG else None
    if MAG:
        G = list(itertools.product((1.0, 1.5, 2.0, 3.0), (0.0, 4.0, 8.0), (1.0, 2.0, 4.0, 0.0), (0.5, 1.0, 2.0),
                                   ((0, 0), (1, 2), (1, 5), (2, 2), (2, 5)), (False, True), (False, True)))
    else:
        G = list(itertools.product((1.0, 1.5, 2.0, 3.0), (0.0, 2.0, 4.0, 8.0), (1.0, 2.0, 4.0, 0.0), (0.5, 1.0, 2.0),
                                   ((0, 0), (1, 2), (1, 5), (2, 2), (2, 5)), (False, True), (False, True)))
    t0 = time.time()
    for i, (sl, tpr, act, dst, (rm, rmax), xopp, xbrk) in enumerate(G):
        if act == 0.0 and dst != 1.0:
            continue        # trail off: one distance only
        p = dict(p0)
        p.update(sl_atr=sl, tp_r=tpr, trail_act_atr=act, trail_dst_atr=dst, use_trail=act > 0, re_mode=rm, re_max=rmax,
                 exit_opp=xopp, fd_exit_break=xbrk, fd_on=True, re_dist_atr=0.25, use_mag=MAG)
        tr = R.run(S, tf, p, ctx, mag=mag)
        if len(tr) < 3:
            continue
        r = dict(tf=tf, sl=sl, tpr=tpr, act=act, dst=dst, rm=rm, rmax=rmax, xopp=xopp, xbrk=xbrk)
        r.update(metrics(tr, atr[tr.ebar.to_numpy()], split, ctx["ch"]["t_open"][tr.ebar.to_numpy()]))
        r["n_re"] = int(tr.reentry.sum())
        rows.append(r)
        if i % 400 == 0:
            print(f"[C tf={tf}] {i}/{len(G)} {time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(out_path)
    return df


if __name__ == "__main__":
    tf = int(sys.argv[1])
    cfg = json.load(open(sys.argv[2]))[str(tf)]
    base = pd.read_parquet("btc_1m.parquet")
    S = R.Source(base, 1)
    run_grid(tf, S, cfg["entry"], cfg["filter"], f"results/C_{tf}{'_mag' if MAG else ''}.parquet")
    print("C done", tf)
