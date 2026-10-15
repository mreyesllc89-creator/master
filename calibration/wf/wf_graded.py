"""Graded-score AUC (reported apart from the buy / sell permission AUC), same purged half-year walk-forward.
Scores, all at the close of filter candle t, computed with the NATIVE DEFAULT parent / child zones:
  P0 permission   : the zone itself (+1 / 0 / -1) - cross-check of wf_select's counts
  G1 distance     : (close - level) / ATR of the signal candle, clipped to +-5 (the graded form of the same zone)
  G2 logistic     : L2 logistic regression on fixed features (below), fitted per fold on the purged training window
                    (standardised on it), scored on the test block
Usage: python wf_graded.py <tf> <clock> <read> <run real|dry>"""
import sys, os, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wf_common as W
import fgengine as E

tf = int(sys.argv[1]); clock = sys.argv[2]; read = sys.argv[3]; run = sys.argv[4]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
B = 500
SEED = 20261012
FEATS = ["zone", "dist", "side", "r1", "r5", "r20", "vol", "age", "zone_vol", "dist_vol", "fdir"]   # + f/s per zone TF

S = W.load(clock)
ch = S.bars(tf)
last_ts = int(S.base.index[-1].timestamp()) + 60
N = int(np.searchsorted(ch["t_close"], last_ts, side="right"))
r = [b for b in W.baselines(tf) if b["kind"] == "native_default"][0]
z, g, ctx = W.zone_of(S, tf, r, read)
c = ch["c"]; atr = ctx["atr14"]
L, A, D = W.held(c, atr, ctx["buy"], ctx["sell"], ctx["bpx"], ctx["spx"])
F = dict(zone=z.astype(float), dist=g, side=D.astype(float))
cols = list(FEATS)
for ztf in r["zones"]:
    src = S.bars(ztf)
    f = S.tdi(ztf, 14, 2)[1]
    if ztf == tf:
        idx = E.map_off(src, ch)
    else:
        idx = E.map_prev_on(src, ch) if W.READS[read]["htf_no_repaint"] else E.map_off(src, ch)
    fv = E.take(f, idx, np.nan); fp = E.take(f, idx - 1, np.nan)
    F[f"f{ztf}"] = (fv - 50.0) / 50.0; F[f"s{ztf}"] = (fv - fp) / 10.0
    cols += [f"f{ztf}", f"s{ztf}"]
for n in (1, 5, 20):
    x = np.full(len(c), np.nan); x[n:] = (c[n:] - c[:-n]) / atr[n:]
    F[f"r{n}"] = np.clip(x, -10, 10)
F["vol"] = np.clip(atr / pd.Series(atr).rolling(100).mean().to_numpy(), 0, 5)
sig = ctx["buy"] | ctx["sell"]
last = np.maximum.accumulate(np.where(sig, np.arange(len(c)), -1))
F["age"] = np.where(last >= 0, np.log1p(np.arange(len(c)) - last), np.nan)
F["zone_vol"] = F["zone"] * F["vol"]; F["dist_vol"] = F["dist"] * F["vol"]
F["fdir"] = ctx["fdir"].astype(float)
X = pd.DataFrame(F)[cols].to_numpy(float)[:N]
z = z[:N]; g = g[:N]; c = c[:N]
t = ch["t_open"][:N]
mon = W.month_id(t)
if run == "dry":
    m0, m1 = 2018 * 12 + 6, 2019 * 12 + 11
    starts = [2019 * 12, 2019 * 12 + 6]
else:
    m0, m1 = 2020 * 12, 2026 * 12 + 9
    starts = [y * 12 + h for y in range(2021, 2027) for h in (0, 6)]


def group_of(ms):
    if run == "dry":
        return "dry"
    return "fresh_2021_2022" if ms < 2023 * 12 else ("inspected_2023_2025H1" if ms < 2025 * 12 + 6 else "inspected_final_2025H2_2026")


def logit_fit(Xt, y, l2=1.0, it=30):
    Xb = np.c_[np.ones(len(Xt)), Xt]; w = np.zeros(Xb.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-np.clip(Xb @ w, -30, 30)))
        gr = Xb.T @ (p - y) / len(y) + l2 * np.r_[0, w[1:]] / len(y)
        Hm = (Xb.T * (p * (1 - p))) @ Xb / len(y) + l2 * np.eye(len(w)) / len(y)
        w -= np.linalg.solve(Hm, gr)
    return w


rows, pool = [], []
for H in W.HS:
    fwd = np.full(N, np.nan); fwd[:-H] = c[H:] - c[:-H]
    mH = np.full(N, 10 ** 9); mH[:-H] = mon[H:]
    ok = ~np.isnan(fwd) & (fwd != 0) & (mon >= m0) & (mon <= m1)
    y = (fwd > 0).astype(float)
    good = ~np.isnan(X).any(axis=1)
    sc = {k: np.full(N, np.nan) for k in ("P0 permission", "G1 distance", "G2 logistic")}
    weights = {}
    for s in starts:
        e = min(s + 5, m1)
        if s > m1:
            continue
        tr = ok & good & (mon < s) & (mH < s)                  # purged: the label must end before the test block
        te = ok & (mon >= s) & (mon <= e)
        mu = X[tr].mean(0); sd = X[tr].std(0) + 1e-9
        w = logit_fit((X[tr] - mu) / sd, y[tr])
        s2 = np.c_[np.ones(N), (X - mu) / sd] @ w
        sc["P0 permission"][te] = z[te]; sc["G1 distance"][te] = g[te]
        tg = te & good
        sc["G2 logistic"][tg] = s2[tg]
        nm = f"{s // 12}H{1 if s % 12 == 0 else 2}"
        weights[nm] = {k: round(float(v), 4) for k, v in zip(["b0"] + cols, w)}
        for k, v in sc.items():
            m = te & ~np.isnan(v)
            rows.append(dict(tf=tf, clock=clock, read=read, H=H, fold=nm, group=group_of(s), score=k, n=int(m.sum()),
                             up_rate=float(y[m].mean()), auc=W.rank_auc(v[m], y[m])))
    # pooled per group + month block bootstrap
    rng = np.random.default_rng(SEED + H)
    for gname in sorted(set(group_of(s) for s in starts if s <= m1)) + (["all_2021_2025H1"] if run != "dry" else []):
        fold_g = {m: group_of(starts[0] + 6 * ((m - starts[0]) // 6)) for m in range(starts[0], m1 + 1)}
        if gname == "all_2021_2025H1":
            sel_m = [m for m, gg in fold_g.items() if gg in ("fresh_2021_2022", "inspected_2023_2025H1")]
        else:
            sel_m = [m for m, gg in fold_g.items() if gg == gname]
        sel_m = np.array(sel_m)
        if len(sel_m) == 0:
            continue
        for k, v in sc.items():
            m = ok & ~np.isnan(v) & np.isin(mon, sel_m)
            vv, yy, mm = v[m], y[m], mon[m]
            a = W.rank_auc(vv, yy)
            order = np.argsort(mm, kind="stable"); vv, yy, mm = vv[order], yy[order], mm[order]
            u, st = np.unique(mm, return_index=True); en = np.r_[st[1:], len(mm)]
            bs = []
            for b in range(B):
                pick = rng.integers(0, len(u), len(u))
                ii = np.concatenate([np.arange(st[p], en[p]) for p in pick])
                bs.append(W.rank_auc(vv[ii], yy[ii]))
            lo, hi = np.nanpercentile(bs, [2.5, 97.5])
            pool.append(dict(tf=tf, clock=clock, read=read, H=H, group=gname, score=k, n=int(m.sum()), auc=a, ci_lo=lo, ci_hi=hi))
    if H == W.HS[-1]:
        json.dump(dict(features=cols, weights_per_fold=weights), open(f"{OUT}/graded_weights_{tf}_{clock}_{read}_{run}.json", "w"), indent=1)

suffix = f"{tf}_{clock}_{read}_{run}"
pd.DataFrame(rows).to_csv(f"{OUT}/graded_folds_{suffix}.csv", index=False, float_format="%.5f")
pd.DataFrame(pool).to_csv(f"{OUT}/graded_pooled_{suffix}.csv", index=False, float_format="%.5f")
print("done graded", suffix)
