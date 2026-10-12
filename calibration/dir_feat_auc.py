"""Does adding information to the filter's zone raise the direction AUC? Per filter timeframe, with the chosen parent /
child zones (results_auc2/auc_pick.json), every candidate feature is known at the close of filter candle t (higher
timeframes from their last CLOSED bar); the label is the close H candles later higher / lower (ties dropped).
Nested feature sets, a logistic score (portable to Pine / MQL5) and a gradient-boosted tree model (a ceiling).
Fit on train (2023), pick the feature set by validation AUC (2024-01 .. 2025-06), refit on train + validation, and
only then score the final test (2025-07 .. 2026-10). The final test never takes part in a choice."""
import sys, json, time
import numpy as np
import pandas as pd
import fgengine as E
import fgrun as R
import dir_auc as A
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

HS = (1, 3, 10)
T_TRAIN = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp())
T_VALID = int(pd.Timestamp("2025-07-01", tz="UTC").timestamp())
NAMES = {5: "5m", 15: "15m", 30: "30m", 60: "1H", 120: "2H", 240: "4H", 480: "8H", 1440: "1D"}
SETS = {
    "F0 zone": ["zone"],
    "F1 distance from level": ["dist"],
    "F2 + signal side": ["dist", "side"],
    "F3 + TDI fast x1": ["dist", "side", "f1", "s1"],
    "F4 + TDI fast x4, x16 (closed)": ["dist", "side", "f1", "s1", "f4", "s4", "f16", "s16"],
    "F5 + returns 1/5/20": ["dist", "side", "f1", "s1", "f4", "s4", "f16", "s16", "r1", "r5", "r20"],
    "F6 + volatility, age": ["dist", "side", "f1", "s1", "f4", "s4", "f16", "s16", "r1", "r5", "r20", "vol", "age", "zone_vol", "dist_vol"],
    "F7 + FDF trend": ["dist", "side", "f1", "s1", "f4", "s4", "f16", "s16", "r1", "r5", "r20", "vol", "age", "zone_vol", "dist_vol", "fdir"],
}


def tdi_closed(S, tf, mult, ch):
    """TDI fast line (SMA2 of RSI14) of tf*mult, from its last CLOSED bar at the chart candle (x1: the candle itself)"""
    src = S.bars(tf * mult)
    f = S.tdi(tf * mult, 14, 2)[1]
    idx = E.map_off(src, ch) if mult == 1 else E.map_prev_on(src, ch)
    fv = E.take(f, idx, np.nan)
    fp = E.take(f, idx - 1, np.nan)
    return (fv - 50.0) / 50.0, (fv - fp) / 10.0


def features(S, tf, pk):
    zs = tuple(int(x[1:]) for x in pk["zones"].split("/"))
    p = R.params(parent_tf=tf * pk["pm"], zones=A.zones(tf, zs), min_aligned=pk["ma"], use_zones=True, burst_atr=0.5, fd_tf=tf)
    ctx = R.context(S, tf, p)
    ch = ctx["ch"]; c = ch["c"]; atr = ctx["atr14"]
    L, At, D = A.held(c, atr, ctx["buy"], ctx["sell"], ctx["bpx"], ctx["spx"])
    b = A.BAND * np.nan_to_num(At)
    zone = np.where(c > L + b, 1, np.where(c < L - b, -1, 0)).astype(float); zone[np.isnan(L)] = 0
    dist = np.clip((c - L) / At, -5, 5); dist[np.isnan(dist)] = 0
    F = dict(zone=zone, dist=dist, side=D.astype(float))
    for m, k in ((1, "1"), (4, "4"), (16, "16")):
        fl, sl = tdi_closed(S, tf, m, ch)
        F["f" + k] = fl; F["s" + k] = sl
    for n in (1, 5, 20):
        r = np.full(len(c), np.nan); r[n:] = (c[n:] - c[:-n]) / atr[n:]
        F[f"r{n}"] = np.clip(r, -10, 10)
    vol = atr / pd.Series(atr).rolling(100).mean().to_numpy()
    F["vol"] = np.clip(vol, 0, 5)
    sig = ctx["buy"] | ctx["sell"]
    last = np.where(sig, np.arange(len(c)), -1); last = np.maximum.accumulate(last)
    F["age"] = np.where(last >= 0, np.log1p(np.arange(len(c)) - last), np.nan)
    F["zone_vol"] = zone * F["vol"]; F["dist_vol"] = dist * F["vol"]
    F["fdir"] = ctx["fdir"].astype(float)
    df = pd.DataFrame(F)
    df["t"] = ch["t_open"]; df["c"] = c
    return df


def logit_fit(X, y, l2=1.0, it=30):
    Xb = np.c_[np.ones(len(X)), X]; w = np.zeros(Xb.shape[1])
    for _ in range(it):
        z = np.clip(Xb @ w, -30, 30); p = 1 / (1 + np.exp(-z))
        g = Xb.T @ (p - y) / len(y) + l2 * np.r_[0, w[1:]] / len(y)
        Hm = (Xb.T * (p * (1 - p))) @ Xb / len(y) + l2 * np.eye(len(w)) / len(y)
        w -= np.linalg.solve(Hm, g)
    return w


def score_logit(w, X):
    return np.c_[np.ones(len(X)), X] @ w


def run(tf, pick, S):
    df = features(S, tf, pick[str(tf)])
    c = df.c.to_numpy(); t = df.t.to_numpy(); N = len(c)
    warm = np.arange(N) >= 300
    rows = []
    for H in HS:
        fwd = np.full(N, np.nan); fwd[:-H] = c[H:] - c[:-H]
        ok = warm & ~np.isnan(fwd) & (fwd != 0)
        y = (fwd > 0).astype(float)
        tr = ok & (t < T_TRAIN); va = ok & (t >= T_TRAIN) & (t < T_VALID); te = ok & (t >= T_VALID); tv = tr | va
        for sname, cols in SETS.items():
            X = df[cols].to_numpy(float)
            good = ~np.isnan(X).any(axis=1)
            trm, vam, tem, tvm = tr & good, va & good, te & good, tv & good
            if sname == "F0 zone":
                s = X[:, 0]
                res = dict(model="zone as is", auc_train=roc_auc_score(y[trm], s[trm]), auc_valid=roc_auc_score(y[vam], s[vam]),
                           auc_test=roc_auc_score(y[tem], s[tem]), auc_test_refit=roc_auc_score(y[tem], s[tem]))
                rows.append(dict(tf=NAMES[tf], H=H, set=sname, **res, n_test=int(tem.sum()), weights=""))
                continue
            mu = X[trm].mean(0); sd = X[trm].std(0) + 1e-9
            Z = (X - mu) / sd
            w = logit_fit(Z[trm], y[trm])
            s = score_logit(w, Z)
            mu2 = X[tvm].mean(0); sd2 = X[tvm].std(0) + 1e-9
            Z2 = (X - mu2) / sd2
            w2 = logit_fit(Z2[tvm], y[tvm])
            s2 = score_logit(w2, Z2)
            rows.append(dict(tf=NAMES[tf], H=H, set=sname, model="logistic", auc_train=roc_auc_score(y[trm], s[trm]),
                             auc_valid=roc_auc_score(y[vam], s[vam]), auc_test=roc_auc_score(y[tem], s[tem]),
                             auc_test_refit=roc_auc_score(y[tem], s2[tem]), n_test=int(tem.sum()),
                             weights=json.dumps({k: round(float(v), 4) for k, v in zip(["b0"] + cols, w2)})))
            if sname in ("F5 + returns 1/5/20", "F7 + FDF trend"):
                gb = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05, l2_regularization=1.0, random_state=0)
                gb.fit(X[trm], y[trm])
                sg = gb.predict_proba(X)[:, 1]
                gb2 = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05, l2_regularization=1.0, random_state=0)
                gb2.fit(X[tvm], y[tvm])
                sg2 = gb2.predict_proba(X)[:, 1]
                rows.append(dict(tf=NAMES[tf], H=H, set=sname, model="gradient boosting", auc_train=roc_auc_score(y[trm], sg[trm]),
                                 auc_valid=roc_auc_score(y[vam], sg[vam]), auc_test=roc_auc_score(y[tem], sg[tem]),
                                 auc_test_refit=roc_auc_score(y[tem], sg2[tem]), n_test=int(tem.sum()), weights=""))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    tf = int(sys.argv[1])
    pick = json.load(open("results_auc2/auc_pick.json"))
    S = R.Source(pd.read_parquet("btc_1m.parquet"), 1)
    t0 = time.time()
    out = run(tf, pick, S)
    out.to_csv(f"results_auc2/feat_auc_{tf}.csv", index=False, float_format="%.5f")
    print("done", tf, f"{time.time()-t0:.0f}s")
