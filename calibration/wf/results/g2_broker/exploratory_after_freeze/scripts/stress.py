"""Exploratory skeptic stress test of the frozen G2 broker result (after the frozen run). Reuses the frozen script's
definitions by exec'ing its source up to the run section (no file is modified). Writes aggregate numbers only.
Usage (from calib/): python wf/verify_g2/stress.py <broker_csv> [tfs comma-separated]"""
import sys, os, time, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "wf_g2_broker.py")
BROKER = sys.argv[1]
TFS = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "5,15,30").split(",")]
src = open(SRC).read()
code = src[:src.index('if run == "check":')] + src[src.index("def evaluate("):src.index('BS = W.load("server")')]
sys.argv = [SRC, BROKER, "real"]
sys.path.insert(0, os.path.dirname(SRC))
G = {"__file__": SRC, "__name__": "g2src"}
exec(compile(code, SRC, "exec"), G)
W, features, label, fit, score, auc, perm, ts = G["W"], G["features"], G["label"], G["fit"], G["score"], G["auc"], G["perm"], G["ts"]
PERIODS, HS, SEED = G["PERIODS"], G["W"].HS, G["SEED"]
REF = pd.read_csv(os.path.join(os.path.dirname(HERE), "out", "g2_broker_eval_real.csv"))
SINGLES = ["r1", "r5", "r20", "fdir", "side", "dist"]
BIG = 2000
DAY = 86400


# ---------- weighted (bootstrap-multiplicity) AUC, exact equivalent of AUC on concatenated resampled blocks ----------
def prep_auc(s, y):
    o = np.argsort(s, kind="stable"); ss = s[o]
    st = np.r_[0, np.flatnonzero(np.diff(ss) != 0) + 1]
    return o, y[o], st, len(st) < len(s)


def wauc(p, Wm):
    o, yo, st, ties = p
    Ws = Wm[:, o]
    pos = Ws * yo; neg = Ws - pos
    if ties:
        pos = np.add.reduceat(pos, st, axis=1); neg = np.add.reduceat(neg, st, axis=1)
    P = pos.sum(1); N = neg.sum(1)
    cn = np.cumsum(neg, axis=1) - neg
    with np.errstate(invalid="ignore", divide="ignore"):
        return (pos * (cn + 0.5 * neg)).sum(1) / (P * N)


def blocks(t, pi, bl):
    """per-period blocks as the frozen script builds them (offset by the earlier periods' block counts)"""
    off, b = 0, np.zeros(len(t), np.int64)
    for k, (_, a, e) in enumerate(PERIODS):
        p0, p1 = ts(a), ts(e)
        m = pi == k
        b[m] = (t[m] - p0) // bl + off
        off += int(-(-(p1 - p0) // bl))
    return b, off


def boot(D, mask, scores, bl, B, seed, chunk=100):
    """paired block bootstrap: returns point and (B,) replicate arrays of the mean-over-H AUC per score and the mean-over-H
    raw accuracy for P0 / G2P. blocks shared across H and scores (same picks)."""
    nb = blocks(D[HS[0]]["t"], D[HS[0]]["pi"], bl)[1]
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, nb, size=(B, nb))
    mult = np.stack([np.bincount(p, minlength=nb) for p in picks]).astype(float)
    A = {sc: np.full((B, len(HS)), np.nan) for sc in scores}
    Ac = {sc: np.full((B, len(HS)), np.nan) for sc in ("P0", "G2P")}
    pa = {sc: np.zeros(len(HS)) for sc in scores}; pc = {sc: np.zeros(len(HS)) for sc in ("P0", "G2P")}
    for hi, H in enumerate(HS):
        d = D[H]; m = mask[H] if mask is not None else np.ones(len(d["y"]), bool)
        blk = blocks(d["t"], d["pi"], bl)[0][m]; y = d["y"][m]
        pr = {sc: prep_auc(d[sc][m], y) for sc in scores}
        one = np.ones((1, m.sum()))
        for sc in scores:
            pa[sc][hi] = wauc(pr[sc], one)[0]
        for c0 in range(0, B, chunk):
            Wm = mult[c0:c0 + chunk][:, blk]
            for sc in scores:
                A[sc][c0:c0 + chunk, hi] = wauc(pr[sc], Wm)
        for sc in ("P0", "G2P"):
            s = d[sc][m]
            hit = ((s > 0) & (y == 1)) | ((s < 0) & (y == 0)); cov = s != 0
            hb = np.bincount(blk, weights=hit.astype(float), minlength=nb); cb = np.bincount(blk, weights=cov.astype(float), minlength=nb)
            with np.errstate(invalid="ignore", divide="ignore"):
                Ac[sc][:, hi] = (mult @ hb) / (mult @ cb)
            pc[sc][hi] = hit.sum() / cov.sum()
    return ({sc: v.mean() for sc, v in pa.items()}, {sc: np.nanmean(v, 1) for sc, v in A.items()},
            {sc: v.mean() for sc, v in pc.items()}, {sc: np.nanmean(v, 1) for sc, v in Ac.items()}, nb)


def ci(x):
    lo, hi = np.nanpercentile(x, [2.5, 97.5]); return float(lo), float(hi)


t0 = time.time()
BS = W.load("server")
BK, BK_START = G["load_broker_warm"](BROKER, BS)
print("loaded", round(time.time() - t0), "s", flush=True)
R1, R2, R3, R4, R5, R6 = [], [], [], [], [], []
for tf in TFS:
    name = W.NAMES[tf]
    fb = features(BS, tf); fk = features(BK, tf)
    assert fb["cols"] == fk["cols"]
    ci_ = {c: i for i, c in enumerate(fk["cols"])}
    D = {H: {k: [] for k in ["y", "P0", "G2", "G2P", "t", "pi", "vol"] + SINGLES} for H in HS}
    for pi, (pname, a, b) in enumerate(PERIODS):
        p0, p1 = ts(a), ts(b)
        for H in HS:
            m = fit(fb, H, p0)
            ok, y, tH = label(fk, H)
            good = ~np.isnan(fk["X"]).any(axis=1)
            ev = ok & good & (fk["t"] >= p0) & (fk["t"] < p1) & (tH < p1)
            s = score(fk, m)[ev]
            d = D[H]
            d["y"].append(y[ev]); d["P0"].append(fk["z"][ev]); d["G2"].append(s)
            d["G2P"].append(np.where(s > m["q_hi"], 1.0, np.where(s < m["q_lo"], -1.0, 0.0)))
            d["t"].append(fk["t"][ev].astype(np.int64)); d["pi"].append(np.full(ev.sum(), pi))
            d["vol"].append(fk["X"][ev, ci_["vol"]])
            for f in SINGLES:
                d[f].append(-fk["X"][ev, ci_[f]])          # contrarian one-feature score
    D = {H: {k: np.concatenate(v) for k, v in D[H].items()} for H in HS}
    # ---- reproduction check against the frozen CSV (pooled broker, per H point AUC; 48h CI with the script's seed)
    ref = REF[(REF.tf == name) & (REF.source == "broker") & (REF.period == "pooled 2024H2-2025H2")]
    for H in HS:
        for sc in ("P0", "G2", "G2P"):
            mine = auc(D[H][sc], D[H]["y"]); theirs = float(ref[(ref.H == str(H)) & (ref.score == sc)].auc.iloc[0])
            assert abs(mine - theirs) < 1e-4, (tf, H, sc, mine, theirs)
    pa, A, pc, Ac, nb = boot(D, None, ["P0", "G2", "G2P"], G["block_seconds"](tf), 500, SEED + tf + 9000)
    rg2 = ref[(ref.H == "mean") & (ref.score == "G2")].iloc[0]; rgp = ref[(ref.H == "mean") & (ref.score == "G2P")].iloc[0]
    rep = dict(tf=name, auc_diff=pa["G2"] - pa["P0"], ref_auc_diff=rg2.auc_diff_vs_P0, ci48=ci(A["G2"] - A["P0"]),
               ref_ci48=(rg2.auc_diff_ci_lo, rg2.auc_diff_ci_hi), acc_ci48=ci(Ac["G2P"] - Ac["P0"]),
               ref_acc_ci48=(rgp.acc_diff_ci_lo, rgp.acc_diff_ci_hi))
    print("REPRO", rep, flush=True)
    # ---- (3) single-feature point AUCs (pooled, per H and mean)
    sing = {}
    for sc in ["P0", "G2", "G2P"] + SINGLES:
        per = [auc(D[H][sc], D[H]["y"]) for H in HS]
        sing[sc] = np.mean(per)
        R3.append(dict(tf=name, score=sc if sc in ("P0", "G2", "G2P") else "-" + sc, auc_H1=per[0], auc_H3=per[1], auc_H10=per[2],
                       auc_mean=np.mean(per), oracle_sign_auc_mean=np.mean([max(p, 1 - p) for p in per])))
    best = max(SINGLES, key=lambda f: sing[f])
    # per-H best single (in-sample choice per H, most favourable to the singles)
    best_h = {H: max(SINGLES, key=lambda f: max(auc(D[H][f], D[H]["y"]), 1 - auc(D[H][f], D[H]["y"]))) for H in HS}
    # ---- (1) paired block bootstrap with 48h / 7d / 28d blocks, B=2000, plus G2 - best single
    for lab, bl in (("48h", 2 * DAY), ("7d", 7 * DAY), ("28d", 28 * DAY)):
        pa, A, pc, Ac, nb = boot(D, None, ["P0", "G2", "G2P", best], bl, BIG, 777 + tf)
        r = dict(tf=name, block=lab, n_blocks=nb, B=BIG, auc_G2=pa["G2"], auc_P0=pa["P0"], auc_diff=pa["G2"] - pa["P0"])
        r["auc_diff_ci_lo"], r["auc_diff_ci_hi"] = ci(A["G2"] - A["P0"])
        r["p_auc_diff_le0"] = float(np.mean(A["G2"] - A["P0"] <= 0))
        r["acc_diff"] = pc["G2P"] - pc["P0"]; r["acc_diff_ci_lo"], r["acc_diff_ci_hi"] = ci(Ac["G2P"] - Ac["P0"])
        r["p_acc_diff_le0"] = float(np.mean(Ac["G2P"] - Ac["P0"] <= 0))
        r["best_single"] = "-" + best; r["auc_best_single"] = pa[best]
        r["g2_minus_best"] = pa["G2"] - pa[best]; r["g2_minus_best_ci_lo"], r["g2_minus_best_ci_hi"] = ci(A["G2"] - A[best])
        R1.append(r); print("BOOT", {k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
    # ---- (2) month by month (candle open time, broker server clock)
    mon = {H: W.month_id(D[H]["t"]) for H in HS}
    for mm in sorted(np.unique(mon[HS[0]])):
        a_g2, a_p0, a_b, ac_g, ac_p, n = [], [], [], [], [], []
        for H in HS:
            m = mon[H] == mm; y = D[H]["y"][m]
            a_g2.append(auc(D[H]["G2"][m], y)); a_p0.append(auc(D[H]["P0"][m], y)); a_b.append(auc(D[H][best][m], y))
            ac_g.append(perm(D[H]["G2P"][m], y)[0]); ac_p.append(perm(D[H]["P0"][m], y)[0]); n.append(m.sum())
        c = fk["c"]; tt = fk["t"]; mk = W.month_id(tt) == mm
        lr = np.diff(np.log(c[mk]))
        R2.append(dict(tf=name, month=W.mid_name(int(mm)), n=int(np.mean(n)), auc_G2=np.mean(a_g2), auc_P0=np.mean(a_p0),
                       auc_diff=np.mean(a_g2) - np.mean(a_p0), g2_minus_best=np.mean(a_g2) - np.mean(a_b),
                       acc_diff=np.mean(ac_g) - np.mean(ac_p),
                       rv_ann=float(np.std(lr) * np.sqrt(365 * 1440 / tf))))
    # ---- (4) volatility split at the median of the vol feature (pooled eval rows, H=1 median used for all H)
    med = float(np.median(D[HS[0]]["vol"]))
    res = {}
    for half in ("low", "high"):
        mask = {H: (D[H]["vol"] > med) if half == "high" else (D[H]["vol"] <= med) for H in HS}
        pa, A, pc, Ac, nb = boot(D, mask, ["P0", "G2", "G2P", best], 7 * DAY, BIG, 999 + tf)
        res[half] = (A, Ac)
        r = dict(tf=name, half=half, n=int(np.mean([mask[H].sum() for H in HS])), auc_G2=pa["G2"], auc_P0=pa["P0"],
                 auc_best_single=pa[best], auc_diff=pa["G2"] - pa["P0"])
        r["auc_diff_ci_lo"], r["auc_diff_ci_hi"] = ci(A["G2"] - A["P0"])
        r["acc_diff"] = pc["G2P"] - pc["P0"]; r["acc_diff_ci_lo"], r["acc_diff_ci_hi"] = ci(Ac["G2P"] - Ac["P0"])
        r["g2_minus_best"] = pa["G2"] - pa[best]; r["g2_minus_best_ci_lo"], r["g2_minus_best_ci_hi"] = ci(A["G2"] - A[best])
        R4.append(r)
    (Ah, Ach), (Al, Acl) = res["high"], res["low"]
    dd = (Ah["G2"] - Ah["P0"]) - (Al["G2"] - Al["P0"]); da = (Ach["G2P"] - Ach["P0"]) - (Acl["G2P"] - Acl["P0"])
    R4.append(dict(tf=name, half="high-low", auc_diff=float(np.nanmean(dd)), auc_diff_ci_lo=ci(dd)[0], auc_diff_ci_hi=ci(dd)[1],
                   acc_diff=float(np.nanmean(da)), acc_diff_ci_lo=ci(da)[0], acc_diff_ci_hi=ci(da)[1]))
    # ---- per-H G2 - P0 and per-H best single (context for item 3)
    for H in HS:
        f = best_h[H]; a_f = auc(D[H][f], D[H]["y"])
        R5.append(dict(tf=name, H=H, auc_G2=auc(D[H]["G2"], D[H]["y"]), auc_P0=auc(D[H]["P0"], D[H]["y"]),
                       best_single_oracle_sign=("-" if a_f >= 0.5 else "+") + f, auc_best_single=max(a_f, 1 - a_f)))
    print("done", name, round(time.time() - t0), "s", flush=True)

for nm, R in (("boot_blocks", R1), ("monthly", R2), ("singles", R3), ("vol_split", R4), ("per_h_best", R5)):
    pd.DataFrame(R).to_csv(os.path.join(HERE, f"stress_{nm}.csv"), index=False, float_format="%.5f")
print("ALL DONE", round(time.time() - t0), "s")
