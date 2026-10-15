"""Per-signal feature table: what separates a real signal from the end of the move."""
import sys
import numpy as np
import pandas as pd
import fgengine as E
import fgrun as R
from calib import zones_for, HORIZON, IS_END


def leg_features(fdir, buy, sell):
    """bars since the parent flip and the signal's rank within the leg (same direction as the parent)."""
    N = len(fdir)
    age = np.zeros(N, np.int64)
    rank = np.zeros(N, np.int64)
    last_flip = 0
    nb = 0
    ns = 0
    prev = 0
    for k in range(N):
        if fdir[k] != prev:
            last_flip = k
            nb = 0
            ns = 0
        age[k] = k - last_flip
        if buy[k]:
            nb += 1
            rank[k] = nb
        if sell[k]:
            ns += 1
            rank[k] = ns
        prev = fdir[k]
    return age, rank


def build(tf, S, pm=4, zk=0, ma=2, burst=0.5, fd_mult=1):
    p = R.params(parent_tf=tf * pm, zones=zones_for(tf, zk), min_aligned=ma, burst_atr=burst, fd_tf=tf * fd_mult,
                 fd_trade=False, fd_div_on=False, fd_pull_on=False, fd_hurst_on=False)
    ctx = R.context(S, tf, p)
    ch = ctx["ch"]
    h, l, c, atr = ch["h"], ch["l"], ch["c"], ctx["atr14"]
    N = len(c)
    d_f, fast = S.tdi(tf, 14, 2)
    slow = E.sma_pine(E.rsi_pine(c, 14), 7)
    par = S.bars(tf * pm)
    pfast = E.take(S.tdi(tf * pm, 14, 2)[1], R.parent_index(S, tf, p), np.nan)
    # momentum streak of the chart fast line
    streak = np.zeros(N, np.int64)
    for k in range(1, N):
        streak[k] = streak[k - 1] + 1 if d_f[k] == d_f[k - 1] and d_f[k] != 0 else 1
    atr_reg = atr / pd.Series(atr).rolling(100).mean().to_numpy()
    hi20 = E.highest_pine(h, 20)
    lo20 = E.lowest_pine(l, 20)
    rng_pos = (c - lo20) / np.where(hi20 - lo20 > 0, hi20 - lo20, np.nan)
    hi50 = E.highest_pine(h, 50)
    lo50 = E.lowest_pine(l, 50)
    rng_pos50 = (c - lo50) / np.where(hi50 - lo50 > 0, hi50 - lo50, np.nan)
    burst_atr = (c - np.roll(c, 1)) / atr
    age, rank = leg_features(ctx["fdir"], ctx["buy"], ctx["sell"])
    sig_b = ctx["buy"]
    sig_s = ctx["sell"]
    # cluster: same-direction signals within the previous 10 bars
    cb = pd.Series(sig_b.astype(int)).rolling(10).sum().shift(1).fillna(0).to_numpy()
    cs = pd.Series(sig_s.astype(int)).rolling(10).sum().shift(1).fillna(0).to_numpy()
    # aligned zones count
    zd = ctx["zdir"]
    ps = ctx["pside"]
    aligned = np.zeros(N, np.int64)
    for z in range(6):
        if p["zones"][z][0]:
            aligned += (zd[z] == ps) & (ps != 0)
    # labels / forward
    lab_b1 = E.label_signals(h, l, c, atr, sig_b, 1, 1.0, HORIZON)
    lab_s1 = E.label_signals(h, l, c, atr, sig_s, -1, 1.0, HORIZON)
    lab_b2 = E.label_signals(h, l, c, atr, sig_b, 1, 2.0, HORIZON)
    lab_s2 = E.label_signals(h, l, c, atr, sig_s, -1, 2.0, HORIZON)
    fwd = {}
    for n in (5, 20, 50):
        f = np.full(N, np.nan)
        f[:-n] = (c[n:] - c[:-n]) / atr[:-n]
        fwd[n] = f
    # max favourable / adverse excursion over 20 bars, in ATR
    mfe = np.full(N, np.nan); mae = np.full(N, np.nan)
    for k in range(N - 20):
        if sig_b[k] or sig_s[k]:
            hh = h[k + 1:k + 21].max(); ll = l[k + 1:k + 21].min()
            if sig_b[k]:
                mfe[k] = (hh - c[k]) / atr[k]; mae[k] = (c[k] - ll) / atr[k]
            else:
                mfe[k] = (c[k] - ll) / atr[k]; mae[k] = (hh - c[k]) / atr[k]
    rows = []
    idx = np.where(sig_b | sig_s)[0]
    df = pd.DataFrame(dict(
        k=idx, t=pd.to_datetime(ch["t_open"][idx], unit="s", utc=True), dir=np.where(sig_b[idx], 1, -1),
        fast=fast[idx], slow=slow[idx], pfast=pfast[idx], aligned=aligned[idx], burst=burst_atr[idx] * np.where(sig_b[idx], 1, -1),
        streak=streak[idx], atr_reg=atr_reg[idx], rng20=rng_pos[idx], rng50=rng_pos50[idx],
        fdir=ctx["fdir"][idx], age=age[idx], rank=rank[idx], depth=ctx["depth"][idx] / atr[idx],
        hurst=ctx["fh"][idx], width=ctx["fw"][idx], warn=np.where(sig_b[idx], ctx["fwu"][idx], ctx["fwd"][idx]),
        dprot=np.where(sig_b[idx], (c[idx] - ctx["fpl"][idx]) / atr[idx], (ctx["fph"][idx] - c[idx]) / atr[idx]),
        cluster=np.where(sig_b[idx], cb[idx], cs[idx]),
        lab1=np.where(sig_b[idx], lab_b1[idx], lab_s1[idx]), lab2=np.where(sig_b[idx], lab_b2[idx], lab_s2[idx]),
        f5=fwd[5][idx] * np.where(sig_b[idx], 1, -1), f20=fwd[20][idx] * np.where(sig_b[idx], 1, -1), f50=fwd[50][idx] * np.where(sig_b[idx], 1, -1),
        mfe=mfe[idx], mae=mae[idx]))
    df["with_parent"] = np.where(df.fdir == 0, 0, np.where(df.fdir == df.dir, 1, -1))
    df["tf"] = tf
    df["is"] = df.t < IS_END
    return df


if __name__ == "__main__":
    tf = int(sys.argv[1])
    base = pd.read_parquet("btc_1m.parquet")
    S = R.Source(base, 1)
    out = []
    for pm, ma in ((4, 2), (4, 1), (1, 2)):
        for fm in (1, 4):
            df = build(tf, S, pm=pm, ma=ma, fd_mult=fm)
            df["pm"] = pm; df["ma"] = ma; df["fm"] = fm
            out.append(df)
    pd.concat(out).to_parquet(f"results/F_{tf}.parquet")
    print("done", tf)
