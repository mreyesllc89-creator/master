"""Frozen purged walk-forward selection and evaluation (see PREREG.md) on the counts written by wf_grid.py.
Usage: python wf_select.py <tf> <clock> <read> <run real|dry>"""
import sys, os, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wf_common as W

tf = int(sys.argv[1]); clock = sys.argv[2]; read = sys.argv[3]; run = sys.argv[4]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
tag = f"{tf}_{clock}_{read}_{run}_all"
Z = np.load(f"{OUT}/cnt_{tag}.npz")
cnt = Z["cnt"].astype(np.float64)                     # (C, H, M, cross, zone, label)
m0 = int(Z["m0"]); m1 = int(Z["m1"]); nM = m1 - m0 + 1
ties = Z["ties"]
cand = pd.read_csv(f"{OUT}/cands_{tag}.csv")
C = len(cand)
GRID = np.where(cand.kind == "grid")[0]
REF = int(np.where(cand.kind == "native_default")[0][0])
BASE = {k: int(np.where(cand.kind == k)[0][0]) for k in ("native_default", "tv_default_x124", "input_default_H1_H1H2H4", "zones_off")}
nz = cand.zones.astype(str).str.count("/").to_numpy() + 1
nz[~cand.use_zones.to_numpy()] = 0
TIE = np.lexsort((cand.ma.to_numpy(), cand.parent.to_numpy(), nz))   # tie-break order: fewer zones, lower parent, lower min
RANK_TB = np.empty(C, int); RANK_TB[TIE] = np.arange(C)

B_TRAIN = 500
B_TEST = 2000
SEED = 20261012

# ---- folds: half-year test blocks; expanding training window from the first evaluation month, purged
def half_starts():
    if run == "dry":
        return [2019 * 12 + 0, 2019 * 12 + 6]
    return [y * 12 + h for y in range(2021, 2027) for h in (0, 6)]


def group_of(ms):
    if run == "dry":
        return "dry"
    if ms < 2023 * 12:
        return "fresh_2021_2022"
    if ms < 2025 * 12 + 6:
        return "inspected_2023_2025H1"
    return "inspected_final_2025H2_2026"


FOLDS = []
for s in half_starts():
    e = min(s + 5, m1)
    if s > m1:
        continue
    FOLDS.append(dict(start=s, end=e, group=group_of(s), name=f"{s // 12}H{1 if s % 12 == 0 else 2}"))


def train_counts(start):
    """training counts per month (C, H, m, zone, label) for months m0 .. start-1; the last month keeps only candles
    whose label ends inside it (purge of labels reaching into the test block)"""
    k = start - m0
    T = cnt[:, :, :k].sum(axis=3)                    # both cross parts
    T[:, :, k - 1] = cnt[:, :, k - 1, 0]             # purge
    return T


def test_counts(s, e):
    return cnt[:, :, s - m0:e - m0 + 1].sum(axis=3)  # (C, H, months, zone, label)


def mean_auc(T):
    """mean over H of the AUC of pooled counts; T (..., H, zone, label)"""
    a = W.auc_table(T[..., 1], T[..., 0])            # label 1 = up, 0 = down -> nu, nd over zones
    return np.nanmean(a, axis=-1)


def halfyears_in(start):
    hs = []
    m = m0
    while m < start:
        hs.append((m, min(m + 5, start - 1)))
        m += 6
    return hs


def select(start, fold_i):
    T = train_counts(start)                          # (C, H, k, zone, label)
    pooled = T.sum(axis=2)
    tr_auc = mean_auc(pooled)
    # R1: best training AUC on the grid
    g = GRID[np.lexsort((RANK_TB[GRID], -np.round(tr_auc[GRID], 12)))]
    r1 = int(g[0])
    # R2: conservative - consistent half-year wins over the native default + bootstrap lower bound > 0
    k = T.shape[2]
    hy = halfyears_in(start)
    wins = np.zeros(C); nh = 0
    for a, b in hy:
        Th = T[:, :, a - m0:b - m0 + 1].sum(axis=2)
        d = mean_auc(Th) - mean_auc(Th[REF:REF + 1])[0]
        wins += d > 0; nh += 1
    share = wins / max(nh, 1)
    rng = np.random.default_rng(SEED + fold_i)
    idx = rng.integers(0, k, size=(B_TRAIN, k))
    Wb = np.zeros((B_TRAIN, k))
    for b in range(B_TRAIN):
        Wb[b] = np.bincount(idx[b], minlength=k)
    flat = T.transpose(2, 0, 1, 3, 4).reshape(k, -1)
    boot = (Wb @ flat).reshape(B_TRAIN, C, len(W.HS), 3, 2)
    ba = mean_auc(boot)                              # (B, C)
    diff = ba - ba[:, REF:REF + 1]
    lo5 = np.nanpercentile(diff, 5, axis=0)
    elig = np.zeros(C, bool); elig[GRID] = True
    elig &= (share >= 2 / 3) & (lo5 > 0) & (tr_auc > 0.5) & (np.arange(C) != REF)
    if elig.any():
        e = np.where(elig)[0]
        r2 = int(e[np.lexsort((RANK_TB[e], -np.round(tr_auc[e], 12)))][0])
    else:
        r2 = REF
    # pick stability of R1 over the bootstrap samples
    bpick = GRID[np.nanargmax(ba[:, GRID], axis=1)]
    freq = pd.Series(bpick).value_counts() / B_TRAIN
    return dict(r1=r1, r2=r2, tr_auc=tr_auc, share=share, lo5=lo5, n_elig=int(elig.sum()), r1_freq=float(freq.get(r1, 0.0)),
                top_freq=[(int(i), float(f)) for i, f in freq.head(5).items()])


def metrics_row(T):
    """T (H, zone, label) -> dict of per-H permission metrics and the mean AUC"""
    out = {}
    for j, H in enumerate(W.HS):
        m = W.perm_metrics(T[j, :, 1], T[j, :, 0])
        for kk, v in m.items():
            out[f"{kk}_H{H}"] = v
    out["auc_mean"] = float(np.nanmean([out[f"auc_H{H}"] for H in W.HS]))
    out["acc_mean"] = float(np.nanmean([out[f"acc_H{H}"] for H in W.HS]))
    out["bal_acc_mean"] = float(np.nanmean([out[f"bal_acc_H{H}"] for H in W.HS]))
    out["coverage_mean"] = float(np.nanmean([out[f"coverage_H{H}"] for H in W.HS]))
    return out


METHODS = ["R1_greedy", "R2_conservative"] + list(BASE)
fold_rows, grid_rows = [], []
per_month = {mth: np.zeros((nM, len(W.HS), 3, 2)) for mth in METHODS}
month_group = np.array([""] * nM, dtype=object)
for fi, f in enumerate(FOLDS):
    sel = select(f["start"], fi)
    Tt = test_counts(f["start"], f["end"])           # (C, H, months, zone, label)
    te_auc = mean_auc(Tt.sum(axis=2))
    pick = dict(R1_greedy=sel["r1"], R2_conservative=sel["r2"], **BASE)
    for mth, cid in pick.items():
        per_month[mth][f["start"] - m0:f["end"] - m0 + 1] = Tt[cid].transpose(1, 0, 2, 3)
        r = dict(tf=tf, clock=clock, read=read, fold=f["name"], group=f["group"],
                 train=f"{W.mid_name(m0)}..{W.mid_name(f['start'] - 1)} (last month purged)",
                 test=f"{W.mid_name(f['start'])}..{W.mid_name(f['end'])}", method=mth, cid=cid, setting=cand.label[cid],
                 train_auc_mean=float(sel["tr_auc"][cid]))
        r.update(metrics_row(Tt[cid].sum(axis=1)))
        if mth == "R1_greedy":
            r["pick_freq_bootstrap"] = sel["r1_freq"]
        if mth == "R2_conservative":
            r["n_eligible"] = sel["n_elig"]
        fold_rows.append(r)
    month_group[f["start"] - m0:f["end"] - m0 + 1] = f["group"]
    ok = np.isfinite(sel["tr_auc"][GRID]) & np.isfinite(te_auc[GRID])
    rc = pd.Series(sel["tr_auc"][GRID][ok]).rank().corr(pd.Series(te_auc[GRID][ok]).rank())
    for cid in GRID:
        grid_rows.append(dict(fold=f["name"], group=f["group"], cid=int(cid), train_auc_mean=float(sel["tr_auc"][cid]),
                              test_auc_mean=float(te_auc[cid]), halfyear_win_share=float(sel["share"][cid]),
                              boot_lo5_diff_vs_default=float(sel["lo5"][cid])))
    for r in fold_rows[-len(pick):]:
        r["rank_corr_train_test_grid"] = float(rc)

folds = pd.DataFrame(fold_rows)

# ---- pooled walk-forward results per group with a paired block bootstrap over test months
pool_rows = []
rng = np.random.default_rng(SEED + 999)
groups = sorted(set(f["group"] for f in FOLDS))
for gname in groups + (["all_2021_2025H1"] if run != "dry" else []):
    if gname == "all_2021_2025H1":
        ms = np.where((month_group == "fresh_2021_2022") | (month_group == "inspected_2023_2025H1"))[0]
    else:
        ms = np.where(month_group == gname)[0]
    if len(ms) == 0:
        continue
    idx = rng.integers(0, len(ms), size=(B_TEST, len(ms)))
    Wb = np.zeros((B_TEST, len(ms)))
    for b in range(B_TEST):
        Wb[b] = np.bincount(idx[b], minlength=len(ms))
    boot = {}
    for mth in METHODS:
        P = per_month[mth][ms]                       # (months, H, zone, label)
        flat = P.reshape(len(ms), -1)
        bt = (Wb @ flat).reshape(B_TEST, len(W.HS), 3, 2)
        boot[mth] = bt
    for mth in METHODS:
        P = per_month[mth][ms].sum(axis=0)
        r = dict(tf=tf, clock=clock, read=read, group=gname, months=len(ms), method=mth)
        r.update(metrics_row(P))
        a = mean_auc(boot[mth])
        r["auc_mean_ci_lo"], r["auc_mean_ci_hi"] = np.nanpercentile(a, [2.5, 97.5])
        d = a - mean_auc(boot["native_default"])
        r["diff_vs_native_default"] = r["auc_mean"] - float(mean_auc(per_month["native_default"][ms].sum(axis=0)))
        r["diff_ci_lo"], r["diff_ci_hi"] = np.nanpercentile(d, [2.5, 97.5])
        r["p_diff_le_0"] = float(np.mean(d <= 0))
        ba = np.array([np.nanmean([W.perm_metrics(boot[mth][b, j, :, 1], boot[mth][b, j, :, 0])["bal_acc"] for j in range(len(W.HS))])
                       for b in range(0, B_TEST, 4)])
        r["bal_acc_mean_ci_lo"], r["bal_acc_mean_ci_hi"] = np.nanpercentile(ba, [2.5, 97.5])
        r["ties_dropped"] = int(ties[:, ms].sum())
        pool_rows.append(r)
pooled = pd.DataFrame(pool_rows)

# ---- final frozen pick: training 2020-01 .. 2025-06 (purged), never the 2025H2-2026 period
final = {}
if run != "dry":
    fstart = 2025 * 12 + 6
    sel = select(fstart, 777)
    Tt = test_counts(fstart, m1).sum(axis=2)
    for nm, cid in (("R1_greedy", sel["r1"]), ("R2_conservative", sel["r2"]), ("native_default", REF)):
        final[nm] = dict(cid=int(cid), setting=cand.label[cid], parent=int(cand.parent[cid]), zones=cand.zones[cid],
                         min_aligned=int(cand.ma[cid]), use_zones=bool(cand.use_zones[cid]),
                         train_auc_mean_2020_2025H1=float(sel["tr_auc"][cid]),
                         exploratory_2025H2_2026=metrics_row(Tt[cid]))
    final["R1_bootstrap_pick_frequency"] = sel["r1_freq"]
    final["R1_bootstrap_top5"] = [dict(cid=i, setting=cand.label[i], freq=f) for i, f in sel["top_freq"]]
    final["R2_eligible_count"] = sel["n_elig"]

suffix = f"{tf}_{clock}_{read}_{run}"
folds.to_csv(f"{OUT}/wf_folds_{suffix}.csv", index=False, float_format="%.5f")
pooled.to_csv(f"{OUT}/wf_pooled_{suffix}.csv", index=False, float_format="%.5f")
pd.DataFrame(grid_rows).to_csv(f"{OUT}/wf_gridfolds_{suffix}.csv", index=False, float_format="%.5f")
json.dump(final, open(f"{OUT}/wf_final_{suffix}.json", "w"), indent=1, default=str)
print("done", suffix, len(FOLDS), "folds")
