"""Broker transfer test of the G2 logistic graded score (see PREREG_G2_BROKER.md). The model is fitted on Bitstamp
candles re-stamped to the broker's server clock (New York + 7h) with every label ending before the broker period starts,
then its coefficients, standardisation and thresholds are applied unchanged to broker candles (as a fixed MQL5 port
would) and, for comparison, to Bitstamp server-clock candles of the same period. No setting is chosen here.
Scores on identical candles: P0 = the filter's zone (native default), G2 = the logistic score, G2P = G2 turned into a
permission at the zone's coverage (BUY above the training 58.5% quantile, SELL below the 41.5% quantile).
Only aggregate numbers are written; broker candles stay outside the repository.
Usage: python wf_g2_broker.py <broker_csv> <run real|dry|check>
check = parity with wf_graded.py on UTC Bitstamp (fold 2025H1), no broker data used."""
import sys, os, json
import numpy as np
import pandas as pd
from scipy.stats import rankdata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wf_common as W
import fgengine as E

path, run = sys.argv[1], sys.argv[2]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
READ = "mt5"
B = 500
SEED = 20261013
COVER = 0.83
Q_LO, Q_HI = 0.5 - (1 - COVER) / 2, 0.5 + (1 - COVER) / 2      # 0.415 / 0.585: 17% NO TRADE in the middle
FEATS = ["zone", "dist", "side", "r1", "r5", "r20", "vol", "age", "zone_vol", "dist_vol", "fdir"]
TRAIN_START = int(pd.Timestamp("2020-01-01", tz="UTC").timestamp())


def block_seconds(tf):
    """bootstrap block: at least 48 hours and at least 4 x the longest label span (10 candles)"""
    return max(172800, 4 * 10 * tf * 60)
if run == "dry":
    PERIODS = [("dry 2024-03..06", "2024-03-01", "2024-07-01")]
else:
    PERIODS = [("2024H2", "2024-07-01", "2025-01-01"), ("2025H1", "2025-01-01", "2025-07-01"), ("2025H2", "2025-07-01", "2026-01-01")]


def load_broker_warm(path, BS):
    """broker M5 candles, preceded (warm-up only, never evaluated) by Bitstamp server-clock 5-minute candles before the
    broker's first candle, so slow indicators (W1 RSI) are seeded as a terminal with full history would seed them"""
    bk = pd.read_csv(path)
    bk.index = pd.to_datetime(bk["time"], unit="s", utc=True)
    bk = bk[["open", "high", "low", "close"]].astype("float64")
    bk = bk[~bk.index.duplicated(keep="last")].sort_index()
    b5 = BS.base.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    pre = b5[b5.index < bk.index[0]]
    return W.WSource(pd.concat([pre, bk]), 5), int(bk.index[0].timestamp())


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


def features(S, tf):
    """identical to wf_graded.py: native-default zones, MT5 reads; complete candles only"""
    ch = S.bars(tf)
    last_ts = int(S.base.index[-1].timestamp()) + (60 if S.base_tf == 1 else S.base_tf * 60)
    N = int(np.searchsorted(ch["t_close"], last_ts, side="right"))
    r = [b for b in W.baselines(tf) if b["kind"] == "native_default"][0]
    z, g, ctx = W.zone_of(S, tf, r, READ)
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
            idx = E.map_prev_on(src, ch) if W.READS[READ]["htf_no_repaint"] else E.map_off(src, ch)
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
    return dict(X=X, cols=cols, z=z[:N].astype(float), c=c[:N], t=ch["t_open"][:N], N=N)


def logit_fit(Xt, y, l2=1.0, it=30):
    Xb = np.c_[np.ones(len(Xt)), Xt]; w = np.zeros(Xb.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-np.clip(Xb @ w, -30, 30)))
        gr = Xb.T @ (p - y) / len(y) + l2 * np.r_[0, w[1:]] / len(y)
        Hm = (Xb.T * (p * (1 - p))) @ Xb / len(y) + l2 * np.eye(len(w)) / len(y)
        w -= np.linalg.solve(Hm, gr)
    return w


def label(fe, H):
    c, t, N = fe["c"], fe["t"], fe["N"]
    fwd = np.full(N, np.nan); fwd[:-H] = c[H:] - c[:-H]
    tH = np.full(N, np.iinfo(np.int64).max); tH[:-H] = t[H:]
    ok = ~np.isnan(fwd) & (fwd != 0)
    return ok, (fwd > 0).astype(float), tH


def auc(s, y):
    n1 = y.sum(); n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    r = rankdata(s)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def perm(s, y):
    """raw accuracy, balanced precision, balanced recall, coverage of a -1 / 0 / +1 permission"""
    b, se = s > 0, s < 0
    nb, ns = b.sum(), se.sum()
    acc = ((b & (y == 1)).sum() + (se & (y == 0)).sum()) / (nb + ns) if nb + ns else np.nan
    pb = (y[b] == 1).mean() if nb else np.nan
    ps = (y[se] == 0).mean() if ns else np.nan
    up, dn = (y == 1) & (s != 0), (y == 0) & (s != 0)
    ru = (s[up] > 0).mean() if up.any() else np.nan
    rd = (s[dn] < 0).mean() if dn.any() else np.nan
    return acc, np.nanmean([pb, ps]), np.nanmean([ru, rd]), (nb + ns) / len(s)


def fit(fe, H, p0):
    """the model for a period starting at p0: Bitstamp candles from 2020-01-01 whose label ends before p0"""
    ok, y, tH = label(fe, H)
    good = ~np.isnan(fe["X"]).any(axis=1)
    tr = ok & good & (fe["t"] >= TRAIN_START) & (tH < p0)
    mu = fe["X"][tr].mean(0); sd = fe["X"][tr].std(0) + 1e-9
    w = logit_fit((fe["X"][tr] - mu) / sd, y[tr])
    s_tr = np.c_[np.ones(tr.sum()), (fe["X"][tr] - mu) / sd] @ w
    q_lo, q_hi = np.quantile(s_tr, [Q_LO, Q_HI])
    return dict(w=w, mu=mu, sd=sd, q_lo=float(q_lo), q_hi=float(q_hi), n_train=int(tr.sum()), up_rate_train=float(y[tr].mean()))


def score(fe, m):
    return np.c_[np.ones(fe["N"]), (fe["X"] - m["mu"]) / m["sd"]] @ m["w"]


if run == "check":
    # parity with wf_graded.py (UTC Bitstamp, fold 2025H1: train months 2020-01 .. 2024-12, test 2025-01 .. 2025-06)
    S = W.load("utc")
    g = []
    for tf in W.FILTER_TFS:
        fe = features(S, tf)
        rp = f"{OUT}/graded_folds_{tf}_utc_mt5_real.csv"
        ref = pd.read_csv(rp) if os.path.exists(rp) else pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "wf_graded_folds.csv"))
        ref = ref[ref.tf == tf] if "tf" in ref.columns else ref
        for H in W.HS:
            p0, p1 = ts("2025-01-01"), ts("2025-07-01")
            m = fit(fe, H, p0)
            ok, y, tH = label(fe, H)
            mon = W.month_id(fe["t"]); good = ~np.isnan(fe["X"]).any(axis=1)
            te = ok & good & (fe["t"] >= p0) & (mon <= 2025 * 12 + 5) & (fe["t"] < p1)
            mine = auc(score(fe, m)[te], y[te])
            theirs = float(ref[(ref.H == H) & (ref.fold == "2025H1") & (ref.score == "G2 logistic")].auc.iloc[0])
            g.append(dict(tf=tf, H=H, auc_here=mine, auc_wf_graded=theirs, diff=mine - theirs))
    d = pd.DataFrame(g); print(d.to_string()); d.to_csv(f"{OUT}/g2_parity_check.csv", index=False)
    sys.exit(0)

def evaluate(per_h, nb, seed, head, rows):
    """point estimates per H and for the mean of H, with a paired block bootstrap (block_seconds(tf); blocks shared
    across H and scores) of the AUCs, the raw accuracies and their differences vs P0"""
    for H in W.HS:
        d = per_h[H]
        for sc in ("P0", "G2", "G2P"):
            r = dict(head, H=str(H), score=sc, n=len(d["y"]), up_rate=float(d["y"].mean()), auc=auc(d[sc], d["y"]))
            if sc != "G2":
                r["acc"], r["bal_precision"], r["bal_recall"], r["coverage"] = perm(d[sc], d["y"])
            rows.append(r)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, nb, size=(B, nb))
    idx_by_h = {}
    for H in W.HS:
        blk = per_h[H]["blk"]
        order = np.argsort(blk, kind="stable")
        st = np.searchsorted(blk[order], np.arange(nb)); en = np.searchsorted(blk[order], np.arange(nb), side="right")
        idx_by_h[H] = (order, st, en)
    bs = {k: np.zeros(B) for k in ("auc_P0", "auc_G2", "auc_G2P", "acc_P0", "acc_G2P")}
    for bi in range(B):
        vals = {k: [] for k in bs}
        for H in W.HS:
            order, st, en = idx_by_h[H]
            ii = np.concatenate([order[st[q]:en[q]] for q in picks[bi]])
            d = per_h[H]; yy = d["y"][ii]
            vals["auc_P0"].append(auc(d["P0"][ii], yy)); vals["auc_G2"].append(auc(d["G2"][ii], yy))
            vals["auc_G2P"].append(auc(d["G2P"][ii], yy))
            vals["acc_P0"].append(perm(d["P0"][ii], yy)[0]); vals["acc_G2P"].append(perm(d["G2P"][ii], yy)[0])
        for k in bs:
            bs[k][bi] = np.nanmean(vals[k])
    pt = {f"auc_{sc}": np.nanmean([auc(per_h[H][sc], per_h[H]["y"]) for H in W.HS]) for sc in ("P0", "G2", "G2P")}
    for sc in ("P0", "G2P"):
        pm = [perm(per_h[H][sc], per_h[H]["y"]) for H in W.HS]
        pt[f"acc_{sc}"], pt[f"bp_{sc}"], pt[f"br_{sc}"], pt[f"cov_{sc}"] = (np.nanmean([m[k] for m in pm]) for k in range(4))
    for sc in ("P0", "G2", "G2P"):
        r = dict(head, H="mean", score=sc, n=int(np.mean([len(per_h[H]["y"]) for H in W.HS])), auc=pt[f"auc_{sc}"])
        r["auc_ci_lo"], r["auc_ci_hi"] = np.nanpercentile(bs[f"auc_{sc}"], [2.5, 97.5])
        if sc != "P0":
            dd = bs[f"auc_{sc}"] - bs["auc_P0"]
            r["auc_diff_vs_P0"] = pt[f"auc_{sc}"] - pt["auc_P0"]
            r["auc_diff_ci_lo"], r["auc_diff_ci_hi"] = np.nanpercentile(dd, [2.5, 97.5])
        if sc != "G2":
            r["acc"], r["bal_precision"], r["bal_recall"], r["coverage"] = pt[f"acc_{sc}"], pt[f"bp_{sc}"], pt[f"br_{sc}"], pt[f"cov_{sc}"]
            r["acc_ci_lo"], r["acc_ci_hi"] = np.nanpercentile(bs[f"acc_{sc}"], [2.5, 97.5])
        if sc == "G2P":
            da = bs["acc_G2P"] - bs["acc_P0"]
            r["acc_diff_vs_P0"] = pt["acc_G2P"] - pt["acc_P0"]
            r["acc_diff_ci_lo"], r["acc_diff_ci_hi"] = np.nanpercentile(da, [2.5, 97.5])
            r["coverage_diff_vs_P0"] = pt["cov_G2P"] - pt["cov_P0"]
        rows.append(r)


BS = W.load("server")
BK, BK_START = load_broker_warm(path, BS)
assert BK_START <= ts(PERIODS[0][1])
rows, weights = [], {}
for tf in W.FILTER_TFS:
    fb = features(BS, tf); fk = features(BK, tf)
    assert fb["cols"] == fk["cols"]
    pooled = {src: {H: [] for H in W.HS} for src in ("broker", "bitstamp_server_clock")}
    nb_total = 0
    for pi, (pname, a, b) in enumerate(PERIODS):
        p0, p1 = ts(a), ts(b)
        bl = block_seconds(tf)
        nb = int(-(-(p1 - p0) // bl))
        models = {H: fit(fb, H, p0) for H in W.HS}
        weights[f"{W.NAMES[tf]} {pname}"] = {str(H): dict(features=["b0"] + fb["cols"], w=[float(v) for v in m["w"]],
                                                        mu=[float(v) for v in m["mu"]], sd=[float(v) for v in m["sd"]],
                                                        q_lo=m["q_lo"], q_hi=m["q_hi"], n_train=m["n_train"],
                                                        up_rate_train=m["up_rate_train"],
                                                        score="b0 + sum(w_i * (x_i - mu_i) / sd_i); BUY if > q_hi, SELL if < q_lo")
                                             for H, m in models.items()}
        for src, fe in (("broker", fk), ("bitstamp_server_clock", fb)):
            per_h = {}
            for H in W.HS:
                ok, y, tH = label(fe, H)
                good = ~np.isnan(fe["X"]).any(axis=1)
                ev = ok & good & (fe["t"] >= p0) & (fe["t"] < p1) & (tH < p1)       # labels end inside the period
                s = score(fe, models[H])[ev]
                g2p = np.where(s > models[H]["q_hi"], 1.0, np.where(s < models[H]["q_lo"], -1.0, 0.0))
                per_h[H] = dict(y=y[ev], P0=fe["z"][ev], G2=s, G2P=g2p, blk=(fe["t"][ev] - p0) // bl)
                pooled[src][H].append(dict(per_h[H], blk=per_h[H]["blk"] + nb_total))
            evaluate(per_h, nb, SEED + tf + 1000 * pi, dict(tf=W.NAMES[tf], period=pname, source=src), rows)
        nb_total += nb
    if len(PERIODS) > 1:
        for src in pooled:
            per_h = {H: {k: np.concatenate([d[k] for d in pooled[src][H]]) for k in ("y", "P0", "G2", "G2P", "blk")} for H in W.HS}
            evaluate(per_h, nb_total, SEED + tf + 9000, dict(tf=W.NAMES[tf], period="pooled 2024H2-2025H2", source=src), rows)
    print("g2 broker done", tf, flush=True)

R = pd.DataFrame(rows)
R.to_csv(f"{OUT}/g2_broker_eval_{run}.csv", index=False, float_format="%.5f")
if len(PERIODS) > 1:
    # pre-registered reading rule (PREREG_G2_BROKER.md), broker candles only
    M = R[(R.H == "mean") & (R.source == "broker")]
    verdict = []
    for tf in W.FILTER_TFS:
        n = W.NAMES[tf]
        g2 = M[(M.tf == n) & (M.period == "pooled 2024H2-2025H2") & (M.score == "G2")].iloc[0]
        gp = M[(M.tf == n) & (M.period == "pooled 2024H2-2025H2") & (M.score == "G2P")].iloc[0]
        c1, c2, c3 = g2.auc_diff_ci_lo > 0, gp.acc_diff_ci_lo > 0, abs(gp.coverage_diff_vs_P0) <= 0.10
        neg = []
        for pname, _, _ in PERIODS:
            a = M[(M.tf == n) & (M.period == pname) & (M.score == "G2")].iloc[0].auc_diff_vs_P0
            b = M[(M.tf == n) & (M.period == pname) & (M.score == "G2P")].iloc[0].acc_diff_vs_P0
            if a < 0 or b < 0:
                neg.append(pname)
        verdict.append(dict(tf=n, auc_diff=g2.auc_diff_vs_P0, auc_diff_ci_lo=g2.auc_diff_ci_lo, acc_diff=gp.acc_diff_vs_P0,
                            acc_diff_ci_lo=gp.acc_diff_ci_lo, coverage_diff=gp.coverage_diff_vs_P0, c1_auc_ci_above_0=c1,
                            c2_acc_ci_above_0=c2, c3_coverage_within_010=c3, transfers=bool(c1 and c2 and c3),
                            flagged_periods=";".join(neg), block_hours=block_seconds(tf) / 3600))
    pd.DataFrame(verdict).to_csv(f"{OUT}/g2_broker_reading_{run}.csv", index=False, float_format="%.5f")
json.dump(weights, open(f"{OUT}/g2_broker_weights_{run}.json", "w"), indent=1)
print("done g2 broker", run)
