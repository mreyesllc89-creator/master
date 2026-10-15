"""Supplement to attrib.py: zone x side structure, simple-rule proxies of G2, and a 48h block bootstrap of the G2P
accuracy on opposing / agreeing / neutral candles. Broker pooled 2024H2-2025H2, exported models. Aggregates only."""
import sys, os, json
import numpy as np, pandas as pd
from scipy.stats import rankdata, spearmanr

CAL = "/tmp/claude-0/-home-user-master/45f02379-b185-5950-93cd-49fdbd504cfc/scratchpad/calib"
WF = CAL + "/wf"; OUTD = WF + "/verify_g2"; SCRIPT = WF + "/wf_g2_broker.py"
BROKER = sys.argv[1]
os.chdir(CAL); sys.path.insert(0, CAL); sys.path.insert(0, WF)
src = open(SCRIPT).read(); ns = {"__file__": SCRIPT, "__name__": "g2x"}
argv0 = sys.argv; sys.argv = ["x", BROKER, "real"]
exec(compile(src[:src.index('if run == "check"')], SCRIPT, "exec"), ns); sys.argv = argv0
features, load_broker_warm, label, auc, W, ts, PERIODS = (ns[k] for k in ("features", "load_broker_warm", "label", "auc", "W", "ts", "PERIODS"))
HS = W.HS; TFS = [5, 15, 30, 60]; B = 1000; BL = 172800
WJ = json.load(open(WF + "/out/g2_broker_weights_real.json"))
BS = W.load("server"); BK, _ = load_broker_warm(BROKER, BS)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
xt_rows, rule_rows, boot_rows, per_rows = [], [], [], []
nb_tot = sum(int(-(-(ts(b) - ts(a)) // BL)) for _, a, b in PERIODS)
rng = np.random.default_rng(20261012)
picks = rng.integers(0, nb_tot, size=(B, nb_tot))
for tf in TFS:
    nm = W.NAMES[tf]; fk = features(BK, tf); cols = fk["cols"]; ci = {c: i for i, c in enumerate(cols)}
    zs = list(W.NATIVE_DEFAULT[tf])
    D = {}
    for H in HS:
        ok, y, tH = label(fk, H); good = ~np.isnan(fk["X"]).any(axis=1)
        P = {k: [] for k in ("y", "X", "s", "g", "z", "blk", "pi")}; off = 0
        for pi, (pn, a, b) in enumerate(PERIODS):
            p0, p1 = ts(a), ts(b); m = WJ[f"{nm} {pn}"][str(H)]
            ev = ok & good & (fk["t"] >= p0) & (fk["t"] < p1) & (tH < p1)
            s = m["w"][0] + ((fk["X"][ev] - np.array(m["mu"])) / np.array(m["sd"])) @ np.array(m["w"][1:])
            P["y"].append(y[ev]); P["X"].append(fk["X"][ev]); P["s"].append(s); P["z"].append(fk["z"][ev])
            P["g"].append(np.where(s > m["q_hi"], 1, np.where(s < m["q_lo"], -1, 0)))
            P["blk"].append((fk["t"][ev] - p0) // BL + off); P["pi"].append(np.full(ev.sum(), pi))
            off += int(-(-(p1 - p0) // BL))
        D[H] = {k: np.concatenate(v) for k, v in P.items()}
    # ---- zone x side structure (H=3 set; shares, up-rate mean over H, G2P call mix) ----
    for zv in (-1, 0, 1):
        for sv in (-1, 1):
            r = dict(tf=nm, zone=zv, side=sv)
            ups, buys, sells, sh, gm = [], [], [], [], []
            for H in HS:
                d = D[H]; m = (d["z"] == zv) & (d["X"][:, ci["side"]] == sv)
                sh.append(m.mean()); ups.append(d["y"][m].mean()); buys.append((d["g"][m] > 0).mean()); sells.append((d["g"][m] < 0).mean())
                gm.append(np.median(d["X"][m, ci["fdir"]]))
            r.update(share=np.mean(sh), up_rate=np.mean(ups), g2p_buy=np.mean(buys), g2p_sell=np.mean(sells))
            xt_rows.append(r)
    d3 = D[3]; X = d3["X"]
    print(nm, "spearman(zone,x):", {c: round(spearmanr(d3["z"], X[:, ci[c]])[0], 2) for c in ("side", "fdir", "r1", "r5", "r20", f"f{zs[0]}", "dist")},
          "| spearman(side,x):", {c: round(spearmanr(X[:, ci["side"]], X[:, ci[c]])[0], 2) for c in ("fdir", "r5", "r20", f"f{zs[0]}")},
          "| fdir values:", np.unique(X[:, ci["fdir"]]).tolist(), flush=True)
    # ---- simple-rule proxies (mean-H AUC, pooled) ----
    def mauc(fn):
        return np.mean([auc(fn(D[H]), D[H]["y"]) for H in HS])
    sg = lambda v: np.sign(v)
    rules = {"P0 zone": lambda d: d["z"].astype(float),
             "G2": lambda d: d["s"],
             "-side": lambda d: -d["X"][:, ci["side"]],
             "-fdir": lambda d: -d["X"][:, ci["fdir"]],
             "-fZ1 (TDI fast level, own tf)": lambda d: -d["X"][:, ci[f"f{zs[0]}"]],
             "-r1": lambda d: -d["X"][:, ci["r1"]],
             "zone - side": lambda d: d["z"] - d["X"][:, ci["side"]],
             "zone - side - fdir": lambda d: d["z"] - d["X"][:, ci["side"]] - d["X"][:, ci["fdir"]],
             "zone - side - fdir - sign(fZ1)": lambda d: d["z"] - d["X"][:, ci["side"]] - d["X"][:, ci["fdir"]] - sg(d["X"][:, ci[f"f{zs[0]}"]]),
             "-side - fdir - sign(fZ1)": lambda d: -d["X"][:, ci["side"]] - d["X"][:, ci["fdir"]] - sg(d["X"][:, ci[f"f{zs[0]}"]])}
    for k, fn in rules.items():
        rule_rows.append(dict(tf=nm, rule=k, auc_meanH=mauc(fn),
                              spearman_with_G2=np.mean([spearmanr(fn(D[H]), D[H]["s"])[0] for H in HS]) if k != "G2" else 1.0))
    # ---- G2P accuracy by agreement with the zone: point, per period, 48h block bootstrap (mean over H) ----
    cats = ("opp", "agree", "neutral")
    cnt = {}
    for H in HS:
        d = D[H]; g, z, y = d["g"], d["z"], d["y"]; call = g != 0
        hit = ((g > 0) & (y == 1)) | ((g < 0) & (y == 0))
        mk = dict(opp=call & (z == -g), agree=call & (z == g), neutral=call & (z == 0), p0flip=(z != 0) & call & (z == -g))
        for c in cats:
            cnt[(H, c, "n")] = np.bincount(d["blk"][mk[c]], minlength=nb_tot).astype(float)
            cnt[(H, c, "h")] = np.bincount(d["blk"][mk[c]], weights=hit[mk[c]].astype(float), minlength=nb_tot)
        for pi in range(3):
            for c in cats:
                mm = mk[c] & (d["pi"] == pi)
                per_rows.append(dict(tf=nm, H=H, period=PERIODS[pi][0], cat=c, acc=hit[mm].mean(), n=int(mm.sum())))
    res = {c: np.zeros(B) for c in cats}
    for c in cats:
        for H in HS:
            n = cnt[(H, c, "n")][picks].sum(1); h = cnt[(H, c, "h")][picks].sum(1)
            res[c] += (h / n) / len(HS)
    pt = {c: np.mean([cnt[(H, c, "h")].sum() / cnt[(H, c, "n")].sum() for H in HS]) for c in cats}
    for c in cats:
        boot_rows.append(dict(tf=nm, stat=f"acc_{c}", point=pt[c], ci_lo=np.percentile(res[c], 2.5), ci_hi=np.percentile(res[c], 97.5)))
    for a_, b_ in (("opp", "agree"), ("neutral", "agree")):
        dd = res[a_] - res[b_]
        boot_rows.append(dict(tf=nm, stat=f"acc_{a_}-acc_{b_}", point=pt[a_] - pt[b_], ci_lo=np.percentile(dd, 2.5), ci_hi=np.percentile(dd, 97.5)))
    print("done", nm, flush=True)
XT = pd.DataFrame(xt_rows); RU = pd.DataFrame(rule_rows); BO = pd.DataFrame(boot_rows); PE = pd.DataFrame(per_rows)
for n_, T in (("xt", XT), ("rules", RU), ("boot", BO), ("per_period", PE)):
    T.to_csv(f"{OUTD}/attrib2_{n_}.csv", index=False)
print("\n== zone x side (pooled broker, mean over H) ==\n", XT.round(4).to_string(index=False))
print("\n== rule proxies ==\n", RU.round(5).to_string(index=False))
print("\n== G2P accuracy by agreement, 48h block bootstrap (B=1000), mean over H ==\n", BO.round(4).to_string(index=False))
PM = PE.groupby(["tf", "period", "cat"], sort=False).acc.mean().unstack("cat")
print("\n== per period (mean over H) ==\n", PM.round(4).to_string())
