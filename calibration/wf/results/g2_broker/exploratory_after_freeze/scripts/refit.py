import sys, os, json
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
CAL = "/tmp/claude-0/-home-user-master/45f02379-b185-5950-93cd-49fdbd504cfc/scratchpad/calib"; WF = CAL + "/wf"
os.chdir(CAL); sys.path.insert(0, CAL); sys.path.insert(0, WF)
src = open(WF + "/wf_g2_broker.py").read(); ns = {"__file__": WF + "/wf_g2_broker.py", "__name__": "g2x"}
sys.argv = ["x", "none", "real"]; exec(compile(src[:src.index('if run == "check"')], "g2", "exec"), ns)
features, W = ns["features"], ns["W"]
ts = lambda s: int(pd.Timestamp(s, tz="UTC").timestamp())
WJ = json.load(open(WF + "/out/g2_broker_weights_real.json"))
BS = W.load("server"); res = []
for tf in (5, 30, 60):
    fe = features(BS, tf); N = fe["N"]; c = fe["c"]; tcl = BS.bars(tf)["t_close"][:N].astype(np.int64)
    for H in (1, 3, 10):
        d = np.full(N, np.nan); d[:N-H] = c[H:] - c[:N-H]; end = np.full(N, np.iinfo(np.int64).max); end[:N-H] = tcl[H:]
        for pn, a in (("2024H2", "2024-07-01"), ("2025H1", "2025-01-01"), ("2025H2", "2025-07-01")):
            m = WJ[f"{W.NAMES[tf]} {pn}"][str(H)]
            tr = np.isfinite(d) & (d != 0) & np.isfinite(fe["X"]).all(1) & (fe["t"] >= ts("2020-01-01")) & (end <= ts(a))
            Z = (fe["X"][tr] - fe["X"][tr].mean(0)) / (fe["X"][tr].std(0) + 1e-9)
            lr = LogisticRegression(C=1.0, tol=1e-10, max_iter=20000).fit(Z, (d[tr] > 0).astype(int))
            wk = np.r_[lr.intercept_, lr.coef_[0]]; wj = np.array(m["w"])
            res.append(dict(tf=W.NAMES[tf], H=H, period=pn, max_abs_dw=np.abs(wk - wj).max(), max_abs_w=np.abs(wj).max(),
                            score_corr=np.corrcoef(np.c_[np.ones(len(Z)), Z] @ wk, np.c_[np.ones(len(Z)), Z] @ wj)[0, 1]))
R = pd.DataFrame(res); print(R.to_string(index=False)); print("max |dw|:", R.max_abs_dw.max(), "min corr:", R.score_corr.min())
