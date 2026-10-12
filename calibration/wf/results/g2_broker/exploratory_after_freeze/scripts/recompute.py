"""Independent recomputation of broker pooled 2024H2-2025H2 mean-H numbers for G2 (M5, M30, H1). Aggregates only."""
import sys, os, json, time
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score

CAL = "/tmp/claude-0/-home-user-master/45f02379-b185-5950-93cd-49fdbd504cfc/scratchpad/calib"
WF = CAL + "/wf"
SCRIPT = WF + "/wf_g2_broker.py"
BROKER = "/root/.claude/uploads/45f02379-b185-5950-93cd-49fdbd504cfc/14199be3-BTCUSD_broker_M5_2024_2025.csv"
os.chdir(CAL); sys.path.insert(0, CAL); sys.path.insert(0, WF)

# extract only the definitions before the 'check' branch (no fit/auc/perm/evaluate used below)
src = open(SCRIPT).read()
head = src[:src.index('if run == "check"')]
ns = {"__file__": SCRIPT, "__name__": "g2x"}
argv0 = sys.argv; sys.argv = ["x", BROKER, "real"]
exec(compile(head, SCRIPT, "exec"), ns)
sys.argv = argv0
features, load_broker_warm, W = ns["features"], ns["load_broker_warm"], ns["W"]

TFS = [5, 30, 60]; HS = (1, 3, 10)
PER = [("2024H2", "2024-07-01", "2025-01-01"), ("2025H1", "2025-01-01", "2025-07-01"), ("2025H2", "2025-07-01", "2026-01-01")]
ts = lambda s: int(pd.Timestamp(s, tz="UTC").timestamp())
TRAIN_START = ts("2020-01-01")
WJ = json.load(open(WF + "/out/g2_broker_weights_real.json"))
EV = pd.read_csv(WF + "/out/g2_broker_eval_real.csv")

t0 = time.time()
BS = W.load("server")
BK, bk_start = load_broker_warm(BROKER, BS)
print("loaded", round(time.time() - t0), "s; broker first candle <= 2024-07-01:", bk_start <= ts("2024-07-01"), flush=True)


def lab(S, fe, tf, H):
    """own label: sign(c[i+H]-c[i]); end time = close time of candle i+H (from the bar table, not fe['t'])"""
    N = fe["N"]; c = fe["c"]
    tcl = S.bars(tf)["t_close"][:N].astype(np.int64)
    assert np.array_equal(S.bars(tf)["t_open"][:N].astype(np.int64), fe["t"].astype(np.int64))
    d = np.full(N, np.nan); d[:N - H] = c[H:] - c[:N - H]
    end = np.full(N, np.iinfo(np.int64).max); end[:N - H] = tcl[H:]
    valid = np.isfinite(d) & (d != 0)
    return valid, (d > 0).astype(int), end, tcl


def acc_cov(s, y):
    m = s != 0
    return float(((s[m] > 0) == (y[m] == 1)).mean()), float(m.mean())


mism, rows, trainrep = [], [], []
for tf in TFS:
    nm = W.NAMES[tf]
    fb = features(BS, tf); fk = features(BK, tf)
    assert fb["cols"] == fk["cols"]
    # ---------- training-set checks (Bitstamp server clock) ----------
    for H in HS:
        vb, yb, endb, tclb = lab(BS, fb, tf, H)
        goodb = np.isfinite(fb["X"]).all(1)
        prev_n = -1
        for pn, a, b in PER:
            p0 = ts(a); m = WJ[f"{nm} {pn}"][str(H)]
            assert m["features"] == ["b0"] + fb["cols"]
            tr = vb & goodb & (fb["t"] >= TRAIN_START) & (endb <= p0)
            Xt = fb["X"][tr]; mu = Xt.mean(0); sd = Xt.std(0) + 1e-9
            s_tr = m["w"][0] + ((Xt - np.array(m["mu"])) / np.array(m["sd"])) @ np.array(m["w"][1:])
            qlo, qhi = np.quantile(s_tr, [0.415, 0.585])
            gap_min = (p0 - endb[tr].max()) / 60
            trainrep.append(dict(tf=nm, H=H, period=pn, n_train_recomp=int(tr.sum()), n_train_json=m["n_train"],
                                 grows=int(tr.sum()) > prev_n, last_label_end_gap_min=gap_min,
                                 last_label_end_before_p0=bool(endb[tr].max() <= p0),
                                 any_feature_row_at_or_after_p0=bool((fb["t"][tr] >= p0).any()),
                                 max_rel_mu=float(np.max(np.abs(mu - m["mu"]) / (np.abs(np.array(m["sd"])) + 1e-12))),
                                 max_rel_sd=float(np.max(np.abs(sd / np.array(m["sd"]) - 1))),
                                 dq_lo=float(qlo - m["q_lo"]), dq_hi=float(qhi - m["q_hi"]),
                                 up_rate_diff=float(yb[tr].mean() - m["up_rate_train"])))
            prev_n = int(tr.sum())
    # ---------- broker evaluation ----------
    for H in HS:
        vk, yk, endk, tclk = lab(BK, fk, tf, H)
        goodk = np.isfinite(fk["X"]).all(1)
        pool = {k: [] for k in ("y", "P0", "G2", "G2P")}
        for pn, a, b in PER:
            p0, p1 = ts(a), ts(b); m = WJ[f"{nm} {pn}"][str(H)]
            ev = vk & goodk & (fk["t"] >= p0) & (fk["t"] < p1) & (endk <= p1)
            s = m["w"][0] + ((fk["X"][ev] - np.array(m["mu"])) / np.array(m["sd"])) @ np.array(m["w"][1:])
            g2p = np.where(s > m["q_hi"], 1, np.where(s < m["q_lo"], -1, 0))
            for k, v in (("y", yk[ev]), ("P0", fk["z"][ev]), ("G2", s), ("G2P", g2p)):
                pool[k].append(v)
            # sanity: label end and the script's open-time criterion coincide
            alt = vk & goodk & (fk["t"] >= p0) & (fk["t"] < p1)
            tH_open = np.full(fk["N"], np.iinfo(np.int64).max); tH_open[:fk["N"] - H] = fk["t"][H:]
            n_diff = int(((alt & (tH_open < p1)) != ev).sum())
            rows.append(dict(tf=nm, period=pn, H=H, y=yk[ev], P0=fk["z"][ev], G2=s, G2P=g2p, crit_diff=n_diff))
        rows.append(dict(tf=nm, period="pooled 2024H2-2025H2", H=H, crit_diff=0,
                         **{k: np.concatenate(v) for k, v in pool.items()}))
    print("done", nm, round(time.time() - t0), "s", flush=True)

# ---------- metrics and comparison ----------
out = []
for r in rows:
    y = r["y"]
    a = dict(tf=r["tf"], period=r["period"], H=r["H"], n=len(y), up_rate=y.mean(),
             auc_P0=roc_auc_score(y, r["P0"]), auc_G2=roc_auc_score(y, r["G2"]), auc_G2P=roc_auc_score(y, r["G2P"]))
    a["acc_P0"], a["cov_P0"] = acc_cov(r["P0"], y)
    a["acc_G2P"], a["cov_G2P"] = acc_cov(r["G2P"], y)
    a["crit_diff"] = r["crit_diff"]
    out.append(a)
O = pd.DataFrame(out)
M = O.groupby(["tf", "period"], sort=False)[["auc_P0", "auc_G2", "auc_G2P", "acc_P0", "cov_P0", "acc_G2P", "cov_G2P"]].mean().reset_index()
M["H"] = "mean"; M["n"] = O.groupby(["tf", "period"], sort=False)["n"].mean().astype(int).values
ALL = pd.concat([O.assign(H=O.H.astype(str)), M], ignore_index=True)

E = EV[EV.source == "broker"].copy(); E["H"] = E.H.astype(str)
checks = [("auc_P0", "P0", "auc"), ("auc_G2", "G2", "auc"), ("auc_G2P", "G2P", "auc"), ("acc_P0", "P0", "acc"),
          ("cov_P0", "P0", "coverage"), ("acc_G2P", "G2P", "acc"), ("cov_G2P", "G2P", "coverage")]
cmp_rows = []
for _, r in ALL.iterrows():
    for mine, sc, col in checks:
        e = E[(E.tf == r.tf) & (E.period == r.period) & (E.H == r.H) & (E.score == sc)]
        assert len(e) == 1, (r.tf, r.period, r.H, sc)
        ref = float(e[col].iloc[0]); d = r[mine] - ref
        cmp_rows.append(dict(tf=r.tf, period=r.period, H=r.H, metric=mine, mine=r[mine], csv=ref, diff=d, ok=abs(d) <= 1e-4))
    e = E[(E.tf == r.tf) & (E.period == r.period) & (E.H == r.H) & (E.score == "P0")]
    cmp_rows.append(dict(tf=r.tf, period=r.period, H=r.H, metric="n", mine=r.n, csv=float(e.n.iloc[0]), diff=r.n - float(e.n.iloc[0]), ok=r.n == int(e.n.iloc[0])))
C = pd.DataFrame(cmp_rows)
C.to_csv(WF + "/verify_g2/compare.csv", index=False)
T = pd.DataFrame(trainrep); T.to_csv(WF + "/verify_g2/train_checks.csv", index=False)
pd.set_option("display.width", 250)
print("\n== pooled mean-H (recomputed) ==")
P = ALL[(ALL.period == "pooled 2024H2-2025H2") & (ALL.H == "mean")]
P = P.assign(dAUC=P.auc_G2 - P.auc_P0, dACC=P.acc_G2P - P.acc_P0, dCOV=P.cov_G2P - P.cov_P0)
print(P[["tf", "n", "auc_P0", "auc_G2", "auc_G2P", "acc_P0", "cov_P0", "acc_G2P", "cov_G2P", "dAUC", "dACC", "dCOV"]].round(5).to_string(index=False))
print("\ncomparisons:", len(C), "mismatches(>1e-4):", int((~C.ok).sum()), "max|diff| (excl n):", C[C.metric != "n"]["diff"].abs().max())
print(C[~C.ok].to_string(index=False))
print("pooled-mean max|diff|:", C[(C.period.str.startswith("pooled")) & (C.H == "mean")]["diff"].abs().max())
print("label-end criterion differences vs open-time criterion:", int(O.crit_diff.sum()))
print("\n== training checks ==")
print(T.round(6).to_string(index=False))
