"""Frozen test of option 2, the score veto (see PREREG_VETO.md): keep the filter's zone (BUY ZONE / SELL ZONE) only
where the logistic score G2 agrees with it, otherwise NO TRADE. The model and its thresholds are fitted only on data
before each test period; the rule never reverses the zone.
Rules on identical candles (rows with every feature defined):
  P0  the zone alone (native default)
  R2  option 2: the zone where G2P (G2 above its training 58.5% quantile = BUY, below 41.5% = SELL) has the same side
  R2s option 2 with one model for every horizon (the H = 3 model), the simpler version to port
  DV  baseline veto: the zone where |distance from the level| / ATR >= k, k set on training rows so that DV covers as
      many training candles as R2 does
  G2P the score as a permission (reference)
Usage: python wf_veto.py real|dry
       python wf_veto.py apply <broker_csv> <start YYYY-MM-DD> <end YYYY-MM-DD> <veto_model_2026.json>
Only aggregate numbers are written."""
import sys, os, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
# reuse the frozen G2 definitions (features, labels, fit, metrics) of wf_g2_broker.py without running its main part
_src = open(os.path.join(HERE, "wf_g2_broker.py")).read()
_src = _src[:_src.index('if run == "check":')]
_argv = sys.argv
sys.argv = ["wf_g2_broker.py", "none", "dry"]
G = {"__file__": os.path.join(HERE, "wf_g2_broker.py"), "__name__": "g2_defs"}
exec(compile(_src, "wf_g2_broker.py", "exec"), G)
sys.argv = _argv
W = G["W"]; features, label, logit_fit = G["features"], G["label"], G["logit_fit"]

run = sys.argv[1]
assert run in ("real", "dry", "apply"), "run must be real, dry or apply"
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
DATA = "btc_1m_2014.parquet"
B = 500
SEED = 20261014
TFS = [5, 15, 30, 60]          # M5, M15, M30 = the rule; H1 = reported only
PRIMARY = ("M5", "M15", "M30")
RULES = ["P0", "R2", "R2s", "DV", "G2P"]
Q_LO, Q_HI = 0.415, 0.585


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


def halves(y0, y1):
    return [(f"{y}H{h}", f"{y}-{'01' if h == 1 else '07'}-01", f"{y if h == 1 else y + 1}-{'07' if h == 1 else '01'}-01")
            for y in range(y0, y1 + 1) for h in (1, 2)]


if run == "dry":
    GROUPS = [("dry 2017H2", "2015-01-01", [("2017H2", "2017-07-01", "2018-01-01")])]
else:
    GROUPS = [("fresh 2018-2019", "2015-01-01", halves(2018, 2019)),
              ("secondary 2021-2022", "2020-01-01", halves(2021, 2022)),
              ("secondary 2026", "2020-01-01", [("2026", "2026-01-01", "2026-10-11")])]


def block_seconds(tf):
    return max(172800, 4 * 10 * tf * 60)


def fit(fe, H, p0, train_start):
    ok, y, tH = label(fe, H)
    good = ~np.isnan(fe["X"]).any(axis=1)
    tr = ok & good & (fe["t"] >= ts(train_start)) & (tH < p0)
    mu = fe["X"][tr].mean(0); sd = fe["X"][tr].std(0) + 1e-9
    w = logit_fit((fe["X"][tr] - mu) / sd, y[tr])
    s_tr = np.c_[np.ones(tr.sum()), (fe["X"][tr] - mu) / sd] @ w
    q_lo, q_hi = np.quantile(s_tr, [Q_LO, Q_HI])
    z_tr = fe["z"][tr]
    g_tr = np.where(s_tr > q_hi, 1.0, np.where(s_tr < q_lo, -1.0, 0.0))
    cov_r2 = float(((z_tr != 0) & (g_tr == z_tr)).mean())
    ad = np.abs(fe["X"][tr][:, fe["cols"].index("dist")])
    zc = z_tr != 0
    frac = min(1.0, cov_r2 / max(zc.mean(), 1e-12))
    k = float(np.quantile(ad[zc], 1 - frac)) if zc.any() else 0.0
    return dict(w=w, mu=mu, sd=sd, q_lo=float(q_lo), q_hi=float(q_hi), k_dist=k, n_train=int(tr.sum()),
                train_cov_R2=cov_r2, train_last_label_end=int(tH[tr].max()))


def g2p(X, m):
    s = np.c_[np.ones(len(X)), (X - m["mu"]) / m["sd"]] @ m["w"]
    return np.where(s > m["q_hi"], 1.0, np.where(s < m["q_lo"], -1.0, 0.0))


def rules(fe, ev, m, m3):
    X = fe["X"][ev]; z = fe["z"][ev]
    gp = g2p(X, m); gp3 = g2p(X, m3)
    dist = X[:, fe["cols"].index("dist")]
    return dict(P0=z, R2=np.where((z != 0) & (gp == z), z, 0.0), R2s=np.where((z != 0) & (gp3 == z), z, 0.0),
                DV=np.where((z != 0) & (np.abs(dist) >= m["k_dist"]), z, 0.0), G2P=gp)


def tables(r, y, blk, nb):
    """count tables (block, rule, value -1/0/+1, label down/up)"""
    T = np.zeros((nb, len(RULES), 3, 2))
    for i, k in enumerate(RULES):
        key = (blk * 3 + (r[k].astype(int) + 1)) * 2 + y.astype(int)
        T[:, i] = np.bincount(key, minlength=nb * 6).reshape(nb, 3, 2)
    return T


def metrics(T):
    """T (..., 3, 2) -> acc, auc, coverage, bal_precision, bal_recall"""
    nu, nd = T[..., 1], T[..., 0]
    with np.errstate(invalid="ignore", divide="ignore"):
        buy = nu[..., 2] + nd[..., 2]; sell = nu[..., 0] + nd[..., 0]; allc = nu.sum(-1) + nd.sum(-1)
        acc = (nu[..., 2] + nd[..., 0]) / (buy + sell)
        NU, ND = nu.sum(-1), nd.sum(-1)
        gt = nu[..., 1] * nd[..., 0] + nu[..., 2] * (nd[..., 0] + nd[..., 1])
        auc = (gt + 0.5 * (nu * nd).sum(-1)) / (NU * ND)
        cov = (buy + sell) / allc
        bp = np.nanmean(np.stack([nu[..., 2] / buy, nd[..., 0] / sell]), axis=0)
        br = np.nanmean(np.stack([nu[..., 2] / (nu[..., 0] + nu[..., 2]), nd[..., 0] / (nd[..., 0] + nd[..., 2])]), axis=0)
    return acc, auc, cov, bp, br


def summarise(Th, nb, seed, head, rows):
    """Th: {H: tables (nb, rules, 3, 2)} -> per-H rows and mean-of-H rows with paired block-bootstrap CIs"""
    for H, T in Th.items():
        tot = T.sum(0)
        acc, auc, cov, bp, br = metrics(tot)
        for i, k in enumerate(RULES):
            rows.append(dict(head, H=str(H), rule=k, n=int(tot[i].sum()), coverage=cov[i], acc=acc[i], auc=auc[i],
                             bal_precision=bp[i], bal_recall=br[i], n_buy=int(tot[i, 2].sum()), n_sell=int(tot[i, 0].sum()),
                             n_up=int(tot[i, :, 1].sum()), n_down=int(tot[i, :, 0].sum())))
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, nb, size=(B, nb))
    Wb = np.stack([np.bincount(p, minlength=nb) for p in pick]).astype(float)
    point = {m: [] for m in ("acc", "auc", "cov", "bp", "br")}
    boot = {m: [] for m in ("acc", "auc")}
    for H, T in Th.items():
        a, u, c, p_, r_ = metrics(T.sum(0))
        point["acc"].append(a); point["auc"].append(u); point["cov"].append(c); point["bp"].append(p_); point["br"].append(r_)
        bt = np.einsum("bk,krzy->brzy", Wb, T)
        a2, u2 = metrics(bt)[:2]
        boot["acc"].append(a2); boot["auc"].append(u2)
    P = {m: np.nanmean(np.stack(v), axis=0) for m, v in point.items()}          # (rules,)
    Bt = {m: np.nanmean(np.stack(v), axis=0) for m, v in boot.items()}          # (B, rules)
    i0, idv = RULES.index("P0"), RULES.index("DV")
    for i, k in enumerate(RULES):
        r = dict(head, H="mean", rule=k, coverage=P["cov"][i], acc=P["acc"][i], auc=P["auc"][i],
                 bal_precision=P["bp"][i], bal_recall=P["br"][i])
        r["acc_ci_lo"], r["acc_ci_hi"] = np.nanpercentile(Bt["acc"][:, i], [2.5, 97.5])
        r["auc_ci_lo"], r["auc_ci_hi"] = np.nanpercentile(Bt["auc"][:, i], [2.5, 97.5])
        if k != "P0":
            for m in ("acc", "auc"):
                r[f"{m}_diff_vs_P0"] = P[m][i] - P[m][i0]
                r[f"{m}_diff_ci_lo"], r[f"{m}_diff_ci_hi"] = np.nanpercentile(Bt[m][:, i] - Bt[m][:, i0], [2.5, 97.5])
            r["coverage_diff_vs_P0"] = P["cov"][i] - P["cov"][i0]
        if k in ("R2", "R2s"):
            for m in ("acc", "auc"):
                r[f"{m}_diff_vs_DV"] = P[m][i] - P[m][idv]
                r[f"{m}_diff_vs_DV_ci_lo"], r[f"{m}_diff_vs_DV_ci_hi"] = np.nanpercentile(Bt[m][:, i] - Bt[m][:, idv], [2.5, 97.5])
        rows.append(r)


def evaluate_group(fe, gname, train_start, periods, tf, rows, models_out=None, given=None):
    bl = block_seconds(tf)
    pooled = {H: [] for H in W.HS}
    off = 0
    for pi, (pname, a, b) in enumerate(periods):
        p0, p1 = ts(a), ts(b)
        nb = int(-(-(p1 - p0) // bl))
        if given is None:
            ms = {H: fit(fe, H, p0, train_start) for H in W.HS}
        else:
            ms = given
        if models_out is not None:
            models_out[pname] = ms
        Th = {}
        for H in W.HS:
            ok, y, tH = label(fe, H)
            good = ~np.isnan(fe["X"]).any(axis=1)
            ev = ok & good & (fe["t"] >= p0) & (fe["t"] < p1) & (tH < p1)
            r = rules(fe, ev, ms[H], ms[3])
            blk = (fe["t"][ev] - p0) // bl
            Th[H] = tables(r, y[ev], blk, nb)
            pooled[H].append(Th[H])
        summarise(Th, nb, SEED + tf + 100 * pi, dict(group=gname, period=pname, tf=W.NAMES[tf], block_hours=bl / 3600), rows)
        off += nb
    if len(periods) > 1:
        Tp = {H: np.concatenate(pooled[H], axis=0) for H in W.HS}
        summarise(Tp, Tp[1].shape[0], SEED + tf + 9999, dict(group=gname, period="pooled", tf=W.NAMES[tf], block_hours=bl / 3600), rows)


def model_json(ms, cols):
    return {str(H): dict(features=["b0"] + cols, w=[float(v) for v in m["w"]], mu=[float(v) for v in m["mu"]],
                         sd=[float(v) for v in m["sd"]], q_lo=m["q_lo"], q_hi=m["q_hi"], k_dist=m["k_dist"],
                         n_train=m["n_train"], train_cov_R2=m["train_cov_R2"]) for H, m in ms.items()}


if run == "apply":
    # for the MT5 study: the frozen 2026 model on new broker candles (no fitting)
    path, a, b, mpath = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
    spec = json.load(open(mpath))
    BS = W.load("server", DATA)
    BK, BK_START = G["load_broker_warm"](path, BS)
    # the window must lie inside the broker's own candles and after the exported model's training cutoff
    assert ts(a) >= max(BK_START, ts("2026-01-01")), "apply window must start at or after the first broker candle and 2026-01-01"
    assert ts(b) > ts(a)
    rows = []
    for tf in TFS:
        fe = features(BK, tf)
        ms = {}
        for H in W.HS:
            d = spec["models"][W.NAMES[tf]][str(H)]
            assert d["features"][1:] == fe["cols"]
            ms[H] = dict(w=np.array(d["w"]), mu=np.array(d["mu"]), sd=np.array(d["sd"]), q_lo=d["q_lo"], q_hi=d["q_hi"], k_dist=d["k_dist"])
        evaluate_group(fe, "apply", None, [(f"{a}..{b}", a, b)], tf, rows, given=ms)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "veto_apply.csv"), index=False, float_format="%.5f")
    print("done apply"); sys.exit(0)

S = W.load("utc", DATA)
rows, models = [], {}
for tf in TFS:
    fe = features(S, tf)
    for gname, train_start, periods in GROUPS:
        mo = {}
        evaluate_group(fe, gname, train_start, periods, tf, rows, models_out=mo)
        models[f"{W.NAMES[tf]} {gname}"] = {p: {str(H): dict(n_train=m["n_train"], q_lo=m["q_lo"], q_hi=m["q_hi"], k_dist=m["k_dist"],
                                                             train_cov_R2=m["train_cov_R2"],
                                                             train_last_label_end=pd.to_datetime(m["train_last_label_end"], unit="s", utc=True).isoformat())
                                                for H, m in ms.items()} for p, ms in mo.items()}
    print("done", tf, flush=True)
R = pd.DataFrame(rows)
R.to_csv(os.path.join(OUT, f"veto_eval_{run}.csv"), index=False, float_format="%.5f")
json.dump(models, open(os.path.join(OUT, f"veto_models_{run}.json"), "w"), indent=1)

if run == "real":
    # pre-registered reading rule (PREREG_VETO.md): fresh 2018-2019 pooled, R2 vs P0
    M = R[R.H == "mean"]
    out = []
    for tf in PRIMARY + ("H1",):
        x = M[(M.tf == tf) & (M.group == "fresh 2018-2019") & (M.period == "pooled") & (M.rule == "R2")].iloc[0]
        c1, c2 = x.acc_diff_ci_lo > 0, x.auc_diff_ci_lo > 0
        flagged = []
        for pname, _, _ in GROUPS[0][2]:
            y = M[(M.tf == tf) & (M.group == "fresh 2018-2019") & (M.period == pname) & (M.rule == "R2")].iloc[0]
            if y.acc_diff_vs_P0 < 0 or y.auc_diff_vs_P0 < 0:
                flagged.append(pname)
        sec = []
        for g in ("secondary 2021-2022", "secondary 2026"):
            per = "pooled" if g == "secondary 2021-2022" else "2026"
            y = M[(M.tf == tf) & (M.group == g) & (M.period == per) & (M.rule == "R2")].iloc[0]
            sec.append(f"{g}: acc {y.acc_diff_vs_P0:+.4f}, auc {y.auc_diff_vs_P0:+.4f}")
        out.append(dict(tf=tf, in_rule=tf in PRIMARY, acc_diff=x.acc_diff_vs_P0, acc_diff_ci_lo=x.acc_diff_ci_lo,
                        auc_diff=x.auc_diff_vs_P0, auc_diff_ci_lo=x.auc_diff_ci_lo, coverage_R2=x.coverage,
                        c1_acc_ci_above_0=c1, c2_auc_ci_above_0=c2, holds=bool(c1 and c2) if tf in PRIMARY else None,
                        flagged_fresh_periods=";".join(flagged), secondary="; ".join(sec)))
    pd.DataFrame(out).to_csv(os.path.join(OUT, "veto_reading_real.csv"), index=False, float_format="%.5f")
    # frozen 2026 model for the MT5 study: Bitstamp on the broker server clock, labels ending before 2026-01-01
    BS = W.load("server", DATA)
    export = dict(rule="BUY allowed only if zone = BUY ZONE and G2P = BUY; SELL allowed only if zone = SELL ZONE and G2P = SELL; "
                       "otherwise NO TRADE. G2 = b0 + sum w_i (x_i - mu_i) / sd_i; G2P = BUY if G2 > q_hi, SELL if G2 < q_lo. "
                       "R2s uses the H = 3 model for every horizon. DV (baseline) keeps the zone where |dist| >= k_dist.",
                  trained_on="Bitstamp BTC/USD re-stamped to New York + 7h, 2020-01-01 .. labels ending before 2026-01-01",
                  models={})
    for tf in TFS:
        fe = features(BS, tf)
        ms = {H: fit(fe, H, ts("2026-01-01"), "2020-01-01") for H in W.HS}
        export["models"][W.NAMES[tf]] = model_json(ms, fe["cols"])
    json.dump(export, open(os.path.join(OUT, "veto_model_2026.json"), "w"), indent=1)
print("done veto", run)
