"""Exploratory, after the frozen fractal result (PREREG_FRACTAL.md promised it): drop-one-timeframe ablation of FR
at H = 1 on the fresh 2018-2019 walk-forward, and the stack-only / local-only / full score AUC at H = 1, 3, 10 and at
longer horizons on M5 candles (12 = 1 h, 48 = 4 h, 288 = 1 day). Point AUCs with n; no bootstrap."""
import sys, os
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "wf_fractal.py")).read(); src = src[:src.index("S = W.load(")]
sys.argv = ["wf_fractal.py", "real"]
ns = {"__file__": os.path.join(HERE, "wf_fractal.py"), "__name__": "fr_defs"}
exec(compile(src, "wf_fractal.py", "exec"), ns)
W, label, fit_logit, score, ts, halves = ns["W"], ns["label"], ns["fit_logit"], ns["score"], ns["ts"], ns["halves"]
S = W.load("utc", ns["DATA"]); ns["monday_weeks"](S); fe = ns["fractal_features"](S)
cols = fe["cols"]; X = fe["X"]; t = fe["t"]; c = fe["c"]; N = fe["N"]
TFS = ["M5", "M15", "H1", "H4", "D1", "W1"]
SETS = {"full 21": cols,
        "stack-only (H1,H4,D1,W1 + depth)": [k for k in cols if any(k.endswith("_" + s) for s in ("H1", "H4", "D1", "W1"))] + ["depth"],
        "M15-and-above": [k for k in cols if any(k.endswith("_" + s) for s in ("M15", "H1", "H4", "D1", "W1"))] + ["depth", "align_fdf", "align_tdi"],
        "local-only (M5, M15)": [k for k in cols if k.endswith("_M5") or k.endswith("_M15")],
        "M5 only": [k for k in cols if k.endswith("_M5")]}
for tf in TFS:
    SETS[f"drop {tf}"] = [k for k in cols if not k.endswith("_" + tf)]

def lab(H):
    fwd = np.full(N, np.nan); fwd[:-H] = c[H:] - c[:-H]
    tH = np.full(N, np.iinfo(np.int64).max); tH[:-H] = t[H:]
    ok = ~np.isnan(fwd) & (fwd != 0) & ~np.isnan(X).any(axis=1)
    return ok, (fwd > 0).astype(float), tH

rows = []
for H in (1, 3, 10, 12, 48, 288):
    ok, y, tH = lab(H)
    pooled = {k: ([], []) for k in SETS}
    for pname, a, b in halves(2018, 2019):
        p0, p1 = ts(a), ts(b)
        tr = ok & (t >= ts("2015-01-01")) & (tH < p0)
        ev = ok & (t >= p0) & (t < p1) & (tH < p1)
        for name, cs in SETS.items():
            if H > 10 and name.startswith("drop"):
                continue
            idx = [cols.index(k) for k in cs]
            m = fit_logit(X[:, idx], y, tr)
            s = score(X[ev][:, idx], m)
            pooled[name][0].append(s); pooled[name][1].append(y[ev])
    for name in SETS:
        if not pooled[name][0]:
            continue
        s = np.concatenate(pooled[name][0]); yy = np.concatenate(pooled[name][1])
        rows.append(dict(H=H, horizon_minutes=5 * H, feature_set=name, n_inputs=len(SETS[name]), n=len(yy), auc=W.rank_auc(s, yy)))
    print("done H", H, flush=True)
R = pd.DataFrame(rows)
full = R[R.feature_set == "full 21"].set_index("H").auc
R["auc_loss_vs_full"] = R.apply(lambda r: full[r.H] - r.auc, axis=1)
out = os.path.join(HERE, "out", "fractal_ablation.csv"); R.to_csv(out, index=False, float_format="%.5f")
print(R.pivot_table(index="feature_set", columns="horizon_minutes", values="auc").round(4).to_string())
