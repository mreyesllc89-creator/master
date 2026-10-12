"""Exploratory: every G2 input as a one-feature score on broker candles (pooled 2024H2-2025H2), sign chosen in-sample
(oracle, most favourable to the single feature), vs G2; 7-day block bootstrap of G2 - best single. Aggregates only.
Usage (from calib/): python wf/verify_g2/allsingles.py <broker_csv> [tfs]"""
import sys, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
BROKER = sys.argv[1]
TFS = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "5,15,30").split(",")]
sys.argv = [sys.argv[0], BROKER, "5"]          # stress.py's argv parsing runs on import; TFS unused there
import importlib.util
src = open(os.path.join(HERE, "stress.py")).read()
src = src[:src.index("t0 = time.time()")]   # definitions only
G = {"__file__": os.path.join(HERE, "stress.py"), "__name__": "stress_defs"}
exec(compile(src, "stress.py", "exec"), G)
W, features, label, fit, score, auc, ts, boot, ci = (G[k] for k in ("W", "features", "label", "fit", "score", "auc", "ts", "boot", "ci"))
PERIODS, HS = G["PERIODS"], W.HS
DAY = 86400

BS = W.load("server")
BK, _ = G["G"]["load_broker_warm"](BROKER, BS)
rows, boots = [], []
for tf in TFS:
    name = W.NAMES[tf]
    fb = features(BS, tf); fk = features(BK, tf)
    cols = fk["cols"]
    D = {H: {k: [] for k in ["y", "P0", "G2", "G2P", "t", "pi", "X"]} for H in HS}
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
            d["t"].append(fk["t"][ev].astype(np.int64)); d["pi"].append(np.full(ev.sum(), pi)); d["X"].append(fk["X"][ev])
    D = {H: {k: np.concatenate(v) for k, v in D[H].items()} for H in HS}
    res = {}
    for j, c in enumerate(cols):
        per = [auc(D[H]["X"][:, j], D[H]["y"]) for H in HS]
        sgn = -1.0 if np.mean(per) < 0.5 else 1.0                 # one sign for all H, chosen in-sample
        am = np.mean([p if sgn > 0 else 1 - p for p in per])
        res[c] = (sgn, am)
        rows.append(dict(tf=name, feature=c, sign="+" if sgn > 0 else "-", auc_mean_best_sign=am,
                         auc_H1=per[0] if sgn > 0 else 1 - per[0], auc_H3=per[1] if sgn > 0 else 1 - per[1],
                         auc_H10=per[2] if sgn > 0 else 1 - per[2]))
    g2 = np.mean([auc(D[H]["G2"], D[H]["y"]) for H in HS])
    rows.append(dict(tf=name, feature="G2", sign="+", auc_mean_best_sign=g2))
    best = max(res, key=lambda c: res[c][1]); j = cols.index(best); sg = res[best][0]
    for H in HS:
        D[H]["BEST"] = sg * D[H]["X"][:, j]
    pa, A, pc, Ac, nb = boot(D, None, ["G2", "BEST"], 7 * DAY, 2000, 4242 + tf)
    lo, hi = ci(A["G2"] - A["BEST"])
    boots.append(dict(tf=name, best_any_single=("+" if sg > 0 else "-") + best, auc_best=pa["BEST"], auc_G2=pa["G2"],
                      g2_minus_best=pa["G2"] - pa["BEST"], ci_lo_7d=lo, ci_hi_7d=hi))
    print(boots[-1], flush=True)
pd.DataFrame(rows).to_csv(os.path.join(HERE, "allsingles_auc.csv"), index=False, float_format="%.5f")
pd.DataFrame(boots).to_csv(os.path.join(HERE, "allsingles_boot.csv"), index=False, float_format="%.5f")
print("ALL DONE")
