"""Exploratory feature attribution of the frozen G2 broker models (exported weights). Reuses the frozen script's
definitions by exec'ing its source up to the run section; no existing file is modified. Aggregates only."""
import sys, os, json, time
import numpy as np, pandas as pd
from scipy.stats import rankdata, spearmanr

CAL = "/tmp/claude-0/-home-user-master/45f02379-b185-5950-93cd-49fdbd504cfc/scratchpad/calib"
WF = CAL + "/wf"; OUTD = WF + "/verify_g2"
SCRIPT = WF + "/wf_g2_broker.py"
BROKER = sys.argv[1]
os.chdir(CAL); sys.path.insert(0, CAL); sys.path.insert(0, WF)
src = open(SCRIPT).read()
ns = {"__file__": SCRIPT, "__name__": "g2x"}
argv0 = sys.argv; sys.argv = ["x", BROKER, "real"]
exec(compile(src[:src.index('if run == "check"')], SCRIPT, "exec"), ns)
sys.argv = argv0
features, load_broker_warm, label, auc, W, ts, PERIODS = (ns[k] for k in ("features", "load_broker_warm", "label", "auc", "W", "ts", "PERIODS"))
HS = W.HS
TFS = [5, 15, 30, 60]
WJ = json.load(open(WF + "/out/g2_broker_weights_real.json"))
EV = pd.read_csv(WF + "/out/g2_broker_eval_real.csv")

t0 = time.time()
BS = W.load("server")
BK, bk0 = load_broker_warm(BROKER, BS)
print("loaded", round(time.time() - t0), "s", flush=True)


def generic(tf, f):
    """f5/s10/... -> fZ1/sZ2/... (child zone 1 = filter tf, 2 = next, 3 = slowest)"""
    zs = list(W.NATIVE_DEFAULT[tf])
    if f[0] in "fs" and f[1:].isdigit():
        return f"{f[0]}Z{zs.index(int(f[1:])) + 1}({W.NAMES[int(f[1:])]})"
    return f


coef_rows, abl_rows, opp_rows, corr_rows, chk_rows = [], [], [], [], []
for tf in TFS:
    nm = W.NAMES[tf]
    fk = features(BK, tf); cols = fk["cols"]; nf = len(cols)
    # ---------- (a) coefficients ----------
    Wm = np.array([[WJ[f"{nm} {pn}"][str(H)]["w"][1:] for H in HS] for pn, _, _ in PERIODS])   # (3 periods, 3 H, nf)
    for pn, _, _ in PERIODS:
        for H in HS:
            assert WJ[f"{nm} {pn}"][str(H)]["features"] == ["b0"] + cols
    flat = Wm.reshape(-1, nf)
    for j, f in enumerate(cols):
        v = flat[:, j]; mw = v.mean()
        coef_rows.append(dict(tf=nm, feature=generic(tf, f), mean_w=mw, abs_mean_w=abs(mw), mean_abs_w=np.abs(v).mean(),
                              n_same_sign_as_mean=int((np.sign(v) == np.sign(mw)).sum()), n_pos=int((v > 0).sum()),
                              n_neg=int((v < 0).sum()), w_min=v.min(), w_max=v.max(),
                              **{f"mean_w_H{H}": Wm[:, k, j].mean() for k, H in enumerate(HS)}))
    # ---------- broker evaluation set: standardized terms per H, pooled over periods ----------
    D = {}
    for H in HS:
        ok, y, tH = label(fk, H)
        good = ~np.isnan(fk["X"]).any(axis=1)
        parts = {k: [] for k in ("y", "Z", "w", "b0", "qlo", "qhi", "P0", "pi", "X")}
        for pi, (pn, a, b) in enumerate(PERIODS):
            p0, p1 = ts(a), ts(b); m = WJ[f"{nm} {pn}"][str(H)]
            ev = ok & good & (fk["t"] >= p0) & (fk["t"] < p1) & (tH < p1)
            Z = (fk["X"][ev] - np.array(m["mu"])) / np.array(m["sd"])
            n = ev.sum()
            parts["y"].append(y[ev]); parts["Z"].append(Z); parts["X"].append(fk["X"][ev])
            parts["w"].append(np.tile(np.array(m["w"][1:]), (n, 1))); parts["b0"].append(np.full(n, m["w"][0]))
            parts["qlo"].append(np.full(n, m["q_lo"])); parts["qhi"].append(np.full(n, m["q_hi"]))
            parts["P0"].append(fk["z"][ev]); parts["pi"].append(np.full(n, pi))
        d = {k: np.concatenate(v) for k, v in parts.items()}
        d["T"] = d["Z"] * d["w"]                      # per-candle contribution of each feature
        d["s"] = d["b0"] + d["T"].sum(1)
        d["G2P"] = np.where(d["s"] > d["qhi"], 1, np.where(d["s"] < d["qlo"], -1, 0))
        D[H] = d
    # consistency with the frozen eval csv (pooled AUC per H)
    for H in HS:
        ref = EV[(EV.tf == nm) & (EV.period == "pooled 2024H2-2025H2") & (EV.source == "broker") & (EV.H == str(H))]
        chk_rows.append(dict(tf=nm, H=H, auc_G2=auc(D[H]["s"], D[H]["y"]), ref_G2=float(ref[ref.score == "G2"].auc.iloc[0]),
                             auc_P0=auc(D[H]["P0"], D[H]["y"]), ref_P0=float(ref[ref.score == "P0"].auc.iloc[0]),
                             n=len(D[H]["y"]), ref_n=int(ref[ref.score == "G2"].n.iloc[0])))

    def mean_auc(fn, sub=None):
        out = []
        for H in HS:
            d = D[H]; s = fn(d)
            m = np.ones(len(s), bool) if sub is None else (d["pi"] == sub)
            out.append(auc(s[m], d["y"][m]))
        return out

    full = mean_auc(lambda d: d["s"])
    full_p = [np.mean(mean_auc(lambda d: d["s"], sub=k)) for k in range(3)]
    p0auc = np.mean(mean_auc(lambda d: d["P0"].astype(float)))
    # ---------- (b) drop-one ablation (all features; table keeps the top 6 by |mean w|) ----------
    groups = {f: [j] for j, f in enumerate(cols)}
    zs = list(W.NATIVE_DEFAULT[tf])
    groups.update({"[returns r1,r5,r20]": [cols.index(c) for c in ("r1", "r5", "r20")],
                   "[TDI levels f*]": [cols.index(f"f{z}") for z in zs], "[TDI slopes s*]": [cols.index(f"s{z}") for z in zs],
                   "[filter state zone,dist,side,zone_vol,dist_vol,fdir]": [cols.index(c) for c in ("zone", "dist", "side", "zone_vol", "dist_vol", "fdir")],
                   "[vol,age]": [cols.index(c) for c in ("vol", "age")]})
    for g, js in groups.items():
        ab = mean_auc(lambda d: d["s"] - d["T"][:, js].sum(1))
        only = mean_auc(lambda d: d["b0"] + d["T"][:, js].sum(1))
        abp = [np.mean(mean_auc(lambda d: d["s"] - d["T"][:, js].sum(1), sub=k)) for k in range(3)]
        abl_rows.append(dict(tf=nm, feature=generic(tf, g) if len(js) == 1 else g, group=len(js) > 1, auc_full=np.mean(full),
                             auc_P0=p0auc, auc_without=np.mean(ab), loss=np.mean(full) - np.mean(ab),
                             **{f"loss_H{H}": full[k] - ab[k] for k, H in enumerate(HS)},
                             **{f"loss_{PERIODS[k][0]}": full_p[k] - abp[k] for k in range(3)},
                             auc_only=np.mean(only)))
    # ---------- (c) G2P vs the filter's zone ----------
    for H in HS:
        d = D[H]; g, z, y = d["G2P"], d["P0"], d["y"]
        call = g != 0
        opp = call & (z == -g); agr = call & (z == g); neu = call & (z == 0)
        hit = ((g > 0) & (y == 1)) | ((g < 0) & (y == 0))
        zc = z != 0; zhit = ((z > 0) & (y == 1)) | ((z < 0) & (y == 0))
        opp_rows.append(dict(tf=nm, H=H, n=len(y), cov_G2P=call.mean(), share_buy=(g > 0).sum() / call.sum(),
                             opp_share=opp.sum() / call.sum(), agree_share=agr.sum() / call.sum(), neutral_share=neu.sum() / call.sum(),
                             opp_share_of_buys=(opp & (g > 0)).sum() / (g > 0).sum(), opp_share_of_sells=(opp & (g < 0)).sum() / (g < 0).sum(),
                             acc_opp=hit[opp].mean(), acc_agree=hit[agr].mean(), acc_neutral=hit[neu].mean() if neu.any() else np.nan,
                             acc_G2P=hit[call].mean(), acc_P0=zhit[zc].mean(), cov_P0=zc.mean(),
                             acc_P0_where_G2P_no_trade=zhit[zc & ~call].mean(), share_P0_zone_vetoed=(zc & ~call).sum() / zc.sum(),
                             share_P0_zone_flipped=(zc & opp).sum() / zc.sum(),
                             acc_opp_buy=hit[opp & (g > 0)].mean(), acc_opp_sell=hit[opp & (g < 0)].mean(),
                             n_opp=int(opp.sum()), n_agree=int(agr.sum()), n_neutral=int(neu.sum()),
                             spearman_G2_P0=spearmanr(d["s"], z)[0]))
    # ---------- descriptive: rank correlation of G2 with each raw feature; strong feature collinearity ----------
    for H in HS:
        d = D[H]
        for j, f in enumerate(cols):
            corr_rows.append(dict(tf=nm, H=H, feature=generic(tf, f), spearman_G2_x=spearmanr(d["s"], d["X"][:, j])[0],
                                  auc_x_alone=auc(d["X"][:, j], d["y"])))
    C = np.corrcoef(D[3]["Z"].T)
    hi = [(generic(tf, cols[i]), generic(tf, cols[j]), C[i, j]) for i in range(nf) for j in range(i + 1, nf) if abs(C[i, j]) > 0.6]
    print(nm, "collinear pairs |r|>0.6 (broker, H3 set):", [(a, b, round(c, 2)) for a, b, c in hi], flush=True)
    print("done", nm, round(time.time() - t0), "s", flush=True)

pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
K = pd.DataFrame(chk_rows); K.to_csv(OUTD + "/attrib_check.csv", index=False)
print("\n== consistency with frozen csv ==\n", K.round(5).to_string(index=False))
A = pd.DataFrame(coef_rows); A.to_csv(OUTD + "/attrib_coef.csv", index=False)
B_ = pd.DataFrame(abl_rows); B_.to_csv(OUTD + "/attrib_ablation.csv", index=False)
O = pd.DataFrame(opp_rows); O.to_csv(OUTD + "/attrib_opposition.csv", index=False)
R = pd.DataFrame(corr_rows); R.to_csv(OUTD + "/attrib_corr.csv", index=False)
for nm in [W.NAMES[t] for t in TFS]:
    a = A[A.tf == nm].sort_values("abs_mean_w", ascending=False)
    print(f"\n== (a) {nm} coefficients ==\n", a.drop(columns=["tf", "abs_mean_w"]).round(4).to_string(index=False))
    top6 = list(a.feature[:6])
    b = B_[(B_.tf == nm)]
    print(f"\n== (b) {nm} drop-one ==\n", pd.concat([b[b.feature.isin(top6)].set_index("feature").loc[top6].reset_index(), b[b.group]]).drop(columns=["tf", "group"]).round(5).to_string(index=False))
    print(f"\n   all singles by loss:\n", b[~b.group].sort_values("loss", ascending=False)[["feature", "loss", "auc_only"]].round(5).to_string(index=False))
    r = R[R.tf == nm].groupby("feature", sort=False)[["spearman_G2_x", "auc_x_alone"]].mean()
    print(f"\n   spearman(G2, x) mean H:\n", r.reindex(r.spearman_G2_x.abs().sort_values(ascending=False).index).round(3).to_string())
print("\n== (c) opposition per H ==\n", O.round(4).to_string(index=False))
OM = O.drop(columns=["H"]).groupby("tf", sort=False).mean(); OM.to_csv(OUTD + "/attrib_opposition_meanH.csv")
print("\n== (c) mean over H ==\n", OM.round(4).to_string())
