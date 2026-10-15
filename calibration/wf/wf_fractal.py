"""Frozen test of the fractal direction score (see PREREG_FRACTAL.md): FDF structure direction, TDI fast-line
direction and TDI level at M5 / M15 / H1 / H4 / D1 / W1, read causally at each M5 candle, fitted as a logistic score
FR; permission FRP and veto FRV; count baseline CNT / CNTV; the zone P0, the option-2 veto R2s and its score G2P on
identical candles. Usage: python wf_fractal.py real|dry"""
import sys, os, json, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore", category=RuntimeWarning)   # nanmean over the graded rules' empty acc / cov

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
_src = open(os.path.join(HERE, "wf_g2_broker.py")).read()
_src = _src[:_src.index('if run == "check":')]
_argv = sys.argv; sys.argv = ["wf_g2_broker.py", "none", "dry"]
G = {"__file__": os.path.join(HERE, "wf_g2_broker.py"), "__name__": "g2_defs"}
exec(compile(_src, "wf_g2_broker.py", "exec"), G)
sys.argv = _argv
W = G["W"]; E = G["E"]; features_g2, label, logit_fit = G["features"], G["label"], G["logit_fit"]

run = sys.argv[1]
assert run in ("real", "dry"), "run must be real or dry"
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
DATA = "btc_1m_2014.parquet"
TF = 5
STACK = [5, 15, 60, 240, 1440, 10080]              # M5 .. W1, read from the small to the big in code, scored big to small
B = 500
SEED = 20261015
Q_LO, Q_HI = 0.415, 0.585
RULES = ["P0", "R2s", "G2P", "FR", "FRP", "FRV", "CNT", "CNTV"]
GRADED = {"FR", "CNT"}                                # continuous scores: AUC only, no accuracy / coverage


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


def fractal_features(S):
    """the 21 fractal inputs at every M5 candle, plus the option-2 feature block (for R2s / G2P on the same rows)"""
    fe = features_g2(S, TF)                            # zone, option-2 features, cols, z, c, t, N (complete candles)
    ch = S.bars(TF); N = fe["N"]
    cols, F = [], {}
    for T in STACK:
        src = S.bars(T)
        fdir = S.fdf(T, 5, 3, 10, 14, 2)[0]
        tdir, fast = S.tdi(T, 14, 2)
        idx = E.map_off(src, ch) if T == TF else E.map_prev_on(src, ch)
        name = W.NAMES[T]
        # every read is sliced to the N complete M5 candles that features_g2 scores
        F[f"fdf_{name}"] = E.take(fdir, idx, np.nan).astype(float)[:N]
        F[f"tdi_{name}"] = E.take(tdir, idx, np.nan).astype(float)[:N]
        fv = E.take(fast, idx, np.nan)[:N]
        F[f"tdilvl_{name}"] = (fv - 50.0) / 50.0
        cols += [f"fdf_{name}", f"tdi_{name}", f"tdilvl_{name}"]
    names = [W.NAMES[T] for T in STACK]
    F["align_fdf"] = sum(F[f"fdf_{n}"] for n in names)
    F["align_tdi"] = sum(F[f"tdi_{n}"] for n in names)
    top = F["fdf_W1"]
    depth = np.zeros(N); agree = np.ones(N, bool)
    for n in reversed(names):                          # W1, D1, H4, H1, M15, M5
        agree &= (F[f"fdf_{n}"] == top) & (top != 0)
        depth += agree
    F["depth"] = depth
    cols += ["align_fdf", "align_tdi", "depth"]
    X = pd.DataFrame(F)[cols].to_numpy(float)
    assert X.shape[0] == N == fe["X"].shape[0]
    return dict(X=X, cols=cols, Xg=fe["X"], colsg=fe["cols"], z=fe["z"], c=fe["c"], t=fe["t"], N=N)


def fit_logit(X, y, tr):
    mu = X[tr].mean(0); sd = X[tr].std(0) + 1e-9
    w = logit_fit((X[tr] - mu) / sd, y[tr])
    s_tr = np.c_[np.ones(tr.sum()), (X[tr] - mu) / sd] @ w
    q_lo, q_hi = np.quantile(s_tr, [Q_LO, Q_HI])
    return dict(w=w, mu=mu, sd=sd, q_lo=float(q_lo), q_hi=float(q_hi), n_train=int(tr.sum()))


def score(X, m):
    return np.c_[np.ones(len(X)), (X - m["mu"]) / m["sd"]] @ m["w"]


def perm(s, lo, hi):
    return np.where(s > hi, 1.0, np.where(s < lo, -1.0, 0.0))


def fit_window(fe, H, p0, train_start):
    ok, y, tH = label(fe, H)
    good = ~np.isnan(fe["X"]).any(axis=1) & ~np.isnan(fe["Xg"]).any(axis=1)
    tr = ok & good & (fe["t"] >= ts(train_start)) & (tH < p0)
    m_fr = fit_logit(fe["X"], y, tr)
    m_fr["train_last_label_end"] = int(tH[tr].max())
    return m_fr


def rules(fe, ev, m_fr, m_g2_3):
    X, Xg, z = fe["X"][ev], fe["Xg"][ev], fe["z"][ev]
    fr = score(X, m_fr); frp = perm(fr, m_fr["q_lo"], m_fr["q_hi"])
    cnt = X[:, fe["cols"].index("align_fdf")] + X[:, fe["cols"].index("align_tdi")]
    cntp = np.sign(cnt)                                   # the count rule: net alignment up / down / 0 -> NO TRADE
    g2 = score(Xg, m_g2_3); g2p = perm(g2, m_g2_3["q_lo"], m_g2_3["q_hi"])
    return dict(P0=z, R2s=np.where((z != 0) & (g2p == z), z, 0.0), G2P=g2p, FR=fr, FRP=frp,
                FRV=np.where((z != 0) & (frp == z), z, 0.0), CNT=cnt, CNTV=np.where((z != 0) & (cntp == z), z, 0.0))


def rank_auc(s, y):
    return W.rank_auc(s, y)


def perm_metrics(p, y):
    """raw accuracy, coverage, calls, balanced precision (mean P(up|BUY), P(down|SELL)), balanced recall
    (mean P(BUY|up), P(SELL|down) among candles with a call)"""
    b, se = p > 0, p < 0; nb, ns = b.sum(), se.sum()
    tb, tse = (b & (y == 1)).sum(), (se & (y == 0)).sum()
    acc = ((tb + tse) / (nb + ns)) if nb + ns else np.nan
    bp = np.nanmean([tb / nb if nb else np.nan, tse / ns if ns else np.nan])
    up_c, dn_c = ((b | se) & (y == 1)).sum(), ((b | se) & (y == 0)).sum()
    br = np.nanmean([tb / up_c if up_c else np.nan, tse / dn_c if dn_c else np.nan])
    return acc, (nb + ns) / len(p), int(nb), int(ns), bp, br


def evaluate_group(fe, gname, train_start, periods, rows, coefs):
    bl = 172800
    pooled = {H: {k: [] for k in ("y", "blk")} | {r: [] for r in RULES} for H in W.HS}
    off = 0
    for pi, (pname, a, b) in enumerate(periods):
        p0, p1 = ts(a), ts(b)
        nb = int(-(-(p1 - p0) // bl))
        per_h = {}
        for H in W.HS:
            m_fr = fit_window(fe, H, p0, train_start)
            coefs.append(dict(group=gname, period=pname, H=H, n_train=m_fr["n_train"],
                              train_last_label_end=pd.to_datetime(m_fr["train_last_label_end"], unit="s", utc=True).isoformat(),
                              **{f"w_{c}": float(v) for c, v in zip(fe["cols"], m_fr["w"][1:])}, b0=float(m_fr["w"][0])))
            ok, y, tH = label(fe, H)
            good = ~np.isnan(fe["X"]).any(axis=1) & ~np.isnan(fe["Xg"]).any(axis=1)
            tr = ok & good & (fe["t"] >= ts(train_start)) & (tH < p0)
            m_g2 = fit_logit(fe["Xg"], y, tr) if H == 3 else None   # the option-2 fixed-H3 model, same training rows
            per_h[H] = dict(m_fr=m_fr, m_g2=m_g2, ok=ok, y=y, tH=tH, good=good)
        m_g2_3 = per_h[3]["m_g2"]
        Th = {}
        for H in W.HS:
            d = per_h[H]
            ev = d["ok"] & d["good"] & (fe["t"] >= p0) & (fe["t"] < p1) & (d["tH"] < p1)
            r = rules(fe, ev, d["m_fr"], m_g2_3)
            blk = (fe["t"][ev] - p0) // bl
            Th[H] = (r, d["y"][ev], blk)
            pooled[H]["y"].append(d["y"][ev]); pooled[H]["blk"].append(blk + off)
            for k in RULES:
                pooled[H][k].append(r[k])
        summarise(Th, nb, SEED + pi, dict(group=gname, period=pname), rows)
        off += nb
    if len(periods) > 1:
        Tp = {H: ({k: np.concatenate(pooled[H][k]) for k in RULES}, np.concatenate(pooled[H]["y"]), np.concatenate(pooled[H]["blk"])) for H in W.HS}
        summarise(Tp, off, SEED + 9999, dict(group=gname, period="pooled"), rows)


def summarise(Th, nb, seed, head, rows):
    """one call per period with every horizon: per-H rows, a mean-of-H row and an 'H = 1 (ci)' row per rule, from one
    paired 48 h block bootstrap (B resamples of block ids shared across horizons and rules)"""
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, nb, size=(B, nb))
    Hs = list(Th)
    point = {k: {"auc": [], "acc": [], "cov": [], "bp": [], "br": []} for k in RULES}
    boot = {k: {"auc": np.full((B, len(Hs)), np.nan), "acc": np.full((B, len(Hs)), np.nan)} for k in RULES}
    for hi, H in enumerate(Hs):
        r, y, blk = Th[H]
        order = np.argsort(blk, kind="stable")
        st = np.searchsorted(blk[order], np.arange(nb)); en = np.searchsorted(blk[order], np.arange(nb), side="right")
        for k in RULES:
            a = rank_auc(r[k], y)
            if k in GRADED:
                acc, cov, nbuy, nsell, bp, br = np.nan, np.nan, 0, 0, np.nan, np.nan
            else:
                acc, cov, nbuy, nsell, bp, br = perm_metrics(r[k], y)
            for m, v in (("auc", a), ("acc", acc), ("cov", cov), ("bp", bp), ("br", br)):
                point[k][m].append(v)
            rows.append(dict(head, H=str(H), rule=k, n=len(y), coverage=cov, acc=acc, auc=a, bal_precision=bp, bal_recall=br,
                             n_buy=nbuy, n_sell=nsell, n_up=int(y.sum()), n_down=int(len(y) - y.sum())))
        for bi in range(B):
            ii = np.concatenate([order[st[q]:en[q]] for q in picks[bi]])
            yy = y[ii]
            for k in RULES:
                boot[k]["auc"][bi, hi] = rank_auc(r[k][ii], yy)
                if k not in GRADED:
                    boot[k]["acc"][bi, hi] = perm_metrics(r[k][ii], yy)[0]

    def emit(label, pt, bt):
        for k in RULES:
            rr = dict(head, H=label, rule=k, coverage=pt[k]["cov"], acc=pt[k]["acc"], auc=pt[k]["auc"],
                      bal_precision=pt[k]["bp"], bal_recall=pt[k]["br"])
            rr["auc_ci_lo"], rr["auc_ci_hi"] = np.nanpercentile(bt[k]["auc"], [2.5, 97.5])
            if k not in GRADED:
                rr["acc_ci_lo"], rr["acc_ci_hi"] = np.nanpercentile(bt[k]["acc"], [2.5, 97.5])
            for ref in ("P0", "R2s", "G2P"):
                if k == ref:
                    continue
                for m in ("auc", "acc"):
                    if m == "acc" and (k in GRADED or ref in GRADED):
                        continue
                    rr[f"{m}_diff_vs_{ref}"] = pt[k][m] - pt[ref][m]
                    rr[f"{m}_diff_vs_{ref}_ci_lo"], rr[f"{m}_diff_vs_{ref}_ci_hi"] = np.nanpercentile(bt[k][m] - bt[ref][m], [2.5, 97.5])
                if k not in GRADED and ref not in GRADED:
                    rr[f"coverage_diff_vs_{ref}"] = pt[k]["cov"] - pt[ref]["cov"]
            rows.append(rr)

    mean_pt = {k: {m: float(np.nanmean(v)) if not all(np.isnan(v)) else np.nan for m, v in point[k].items()} for k in RULES}
    mean_bt = {k: {m: np.nanmean(boot[k][m], axis=1) for m in ("auc", "acc")} for k in RULES}
    emit("mean", mean_pt, mean_bt)
    if 1 in Th:
        h1 = Hs.index(1)
        one_pt = {k: {m: point[k][m][h1] for m in point[k]} for k in RULES}
        one_bt = {k: {m: boot[k][m][:, h1] for m in ("auc", "acc")} for k in RULES}
        emit("1 (ci)", one_pt, one_bt)


def monday_weeks(S):
    """TradingView's W1 opens Monday 00:00 (confirmed on a MEXC BTCUSDT 1W export: bars at 2021-01-18, 2026-10-12);
    wf_common.WSource anchors Sunday for MT5. The fractal score targets Pine, so its W1 is the Monday week. Set before
    any W1 indicator is computed (the fdf / tdi caches key on the timeframe)."""
    t = S.base.index.as_unit("s").asi8.astype(np.int64)
    start = t - ((t - 345600) % 604800)              # 1970-01-05 00:00 was a Monday
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    b = S.base.groupby(start).agg(agg).dropna()
    t_open = b.index.to_numpy().astype(np.int64)
    S._bars[10080] = dict(t_open=t_open, t_close=t_open + 604800, o=b["open"].to_numpy(np.float64),
                          h=b["high"].to_numpy(np.float64), l=b["low"].to_numpy(np.float64),
                          c=b["close"].to_numpy(np.float64), tf=10080, n=len(b))
    assert all(pd.Timestamp(x, unit="s").weekday() == 0 for x in t_open[:50])


S = W.load("utc", DATA)
monday_weeks(S)
fe = fractal_features(S)
rows, coefs = [], []
for gname, train_start, periods in GROUPS:
    evaluate_group(fe, gname, train_start, periods, rows, coefs)
    print("done", gname, flush=True)
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, f"fractal_eval_{run}.csv"), index=False, float_format="%.5f")
pd.DataFrame(coefs).to_csv(os.path.join(OUT, f"fractal_coefs_{run}.csv"), index=False, float_format="%.5f")

if run == "real":
    M = R[(R.group == "fresh 2018-2019") & (R.period == "pooled") & (R.H == "1 (ci)")].set_index("rule")
    frv, frp = M.loc["FRV"], M.loc["FRP"]
    c1 = frv.acc_diff_vs_P0_ci_lo > 0
    c2 = frv.acc_diff_vs_R2s_ci_lo > 0 and abs(frv.coverage_diff_vs_R2s) <= 0.10
    c3 = frp.auc_diff_vs_G2P_ci_lo > 0
    flagged = [p for p, _, _ in GROUPS[0][2]
               if R[(R.group == "fresh 2018-2019") & (R.period == p) & (R.H == "1 (ci)") & (R.rule == "FRV")].iloc[0].acc_diff_vs_R2s < 0]
    verdict = dict(c1_FRV_beats_P0=bool(c1), c2_FRV_beats_R2s_at_comparable_coverage=bool(c2), c3_FRP_beats_G2P_auc=bool(c3),
                   stack_adds_something=bool(c1 and c2 and c3), works_but_restates_local_veto=bool(c1 and not c2),
                   flagged_fresh_halves=";".join(flagged),
                   FRV_minus_P0_acc=float(frv.acc_diff_vs_P0), FRV_minus_R2s_acc=float(frv.acc_diff_vs_R2s),
                   FRV_minus_R2s_acc_ci=[float(frv.acc_diff_vs_R2s_ci_lo), float(frv.acc_diff_vs_R2s_ci_hi)],
                   FRP_minus_G2P_auc=float(frp.auc_diff_vs_G2P), coverage_FRV=float(frv.coverage), coverage_R2s=float(M.loc["R2s"].coverage))
    json.dump(verdict, open(os.path.join(OUT, "fractal_reading_real.json"), "w"), indent=1)
    pd.DataFrame([{k: (";".join(f"{v:.5f}" for v in val) if isinstance(val, list) else val) for k, val in verdict.items()}]).to_csv(
        os.path.join(OUT, "fractal_reading_real.csv"), index=False)
    # export for Pine: the 2026 model (train 2020-01-01 .. labels before 2026-01-01), H = 1 and H = 3
    export = dict(rule="FRV: zone BUY kept only if FRP = BUY, SELL only if FRP = SELL; FRP = BUY if score > q_hi, SELL if < q_lo; "
                       "score = b0 + sum w_i (x_i - mu_i) / sd_i over the 21 fractal inputs",
                  reads="M5 from the closed candle; M15/H1/H4/D1/W1 from the last bar closed by the M5 candle's OPEN ([1] + lookahead_on); W1 = TradingView week, Monday 00:00 UTC",
                  models={})
    for H in W.HS:
        m = fit_window(fe, H, ts("2026-01-01"), "2020-01-01")
        export["models"][str(H)] = dict(features=["b0"] + fe["cols"], w=[float(v) for v in m["w"]], mu=[float(v) for v in m["mu"]],
                                       sd=[float(v) for v in m["sd"]], q_lo=m["q_lo"], q_hi=m["q_hi"], n_train=m["n_train"])
    json.dump(export, open(os.path.join(OUT, "fractal_model_2026.json"), "w"), indent=1)
    print(json.dumps(verdict, indent=1))
print("done fractal", run)
