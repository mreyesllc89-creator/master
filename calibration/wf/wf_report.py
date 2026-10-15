"""Collect the walk-forward outputs into the published CSVs and apply the frozen decision rule (PREREG.md section 7).
Usage: python wf_report.py <out_dir>"""
import sys, os, json, glob
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wf_common as W

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
DST = sys.argv[1]
os.makedirs(DST, exist_ok=True)
RUNS = [("utc", "mt5"), ("server", "mt5"), ("utc", "closed_prev")]

pooled, folds, finals, grid = [], [], [], []
for tf in W.FILTER_TFS:
    for clock, read in RUNS:
        sfx = f"{tf}_{clock}_{read}_real"
        p = f"{SRC}/wf_pooled_{sfx}.csv"
        if not os.path.exists(p):
            continue
        d = pd.read_csv(p); d.insert(0, "filter_tf", W.NAMES[tf]); pooled.append(d)
        f = pd.read_csv(f"{SRC}/wf_folds_{sfx}.csv"); f.insert(0, "filter_tf", W.NAMES[tf]); folds.append(f)
        fj = json.load(open(f"{SRC}/wf_final_{sfx}.json"))
        for k in ("R1_greedy", "R2_conservative", "native_default"):
            e = fj[k]; ex = e["exploratory_2025H2_2026"]
            finals.append(dict(filter_tf=W.NAMES[tf], clock=clock, read=read, method=k, setting=e["setting"],
                               train_auc_mean_2020_2025H1=e["train_auc_mean_2020_2025H1"],
                               expl_auc_mean_2025H2_2026=ex["auc_mean"], expl_acc_mean=ex["acc_mean"],
                               expl_bal_precision_mean=ex["bal_acc_mean"], expl_bal_recall_mean=ex["bal_recall_mean"], expl_coverage_mean=ex["coverage_mean"],
                               R1_bootstrap_pick_frequency=fj["R1_bootstrap_pick_frequency"] if k == "R1_greedy" else np.nan,
                               R2_eligible_count=fj["R2_eligible_count"] if k == "R2_conservative" else np.nan,
                               fresh_labels_ending_in_2023_H1_H3_H10="/".join(str(v) for v in fj["fresh_origin_labels_ending_in_2023_per_H"].values()),
                               fresh_labels_total_H1_H3_H10="/".join(str(v) for v in fj["fresh_origin_labels_total_per_H"].values())))
        if clock == "utc" and read == "mt5":
            g = pd.read_csv(f"{SRC}/wf_gridfolds_{sfx}.csv"); g.insert(0, "filter_tf", W.NAMES[tf]); grid.append(g)
P = pd.concat(pooled); F = pd.concat(folds); FN = pd.DataFrame(finals)
keep = ["filter_tf", "clock", "read", "group", "labels", "months", "method", "auc_mean", "auc_mean_ci_lo", "auc_mean_ci_hi",
        "diff_vs_native_default", "diff_ci_lo", "diff_ci_hi", "p_diff_le_0",
        "acc_mean", "acc_mean_ci_lo", "acc_mean_ci_hi", "acc_diff_vs_native_default", "acc_diff_ci_lo", "acc_diff_ci_hi",
        "bal_acc_mean", "bal_acc_mean_ci_lo", "bal_acc_mean_ci_hi", "bal_recall_mean", "bal_recall_mean_ci_lo",
        "bal_recall_mean_ci_hi", "coverage_mean", "coverage_diff_vs_native_default"] + \
       [f"{k}_H{H}" for H in W.HS for k in ("auc", "acc", "bal_acc", "bal_recall", "coverage", "up_rate", "n_up", "n_down", "n_buy", "n_sell", "n_none")] + ["ties_dropped"]
P[keep].rename(columns=lambda c: c.replace("bal_acc", "bal_precision")).to_csv(f"{DST}/wf_pooled_permission.csv", index=False, float_format="%.5f")
F.rename(columns=lambda c: c.replace("bal_acc", "bal_precision")).to_csv(f"{DST}/wf_folds_permission.csv", index=False, float_format="%.5f")
FN.to_csv(f"{DST}/wf_final_picks.csv", index=False, float_format="%.5f")
if grid:
    G = pd.concat(grid)
    rc = G.groupby(["filter_tf", "fold", "group"], sort=False).apply(
        lambda d: pd.Series(dict(rank_corr=d.train_auc_mean.rank().corr(d.test_auc_mean.rank())))).reset_index()
    rc.to_csv(f"{DST}/wf_grid_rank_stability.csv", index=False, float_format="%.4f")

# decision rule
dec = []
for tf in W.FILTER_TFS:
    n = W.NAMES[tf]
    def get(clock, read, group, method, col, labels="all"):
        x = P[(P.filter_tf == n) & (P.clock == clock) & (P.read == read) & (P.group == group) & (P.method == method) & (P.labels == labels)]
        return float(x[col].iloc[0]) if len(x) else np.nan
    a = get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "diff_ci_lo")
    b = get("utc", "mt5", "inspected_2023_2025H1", "R2_conservative", "diff_vs_native_default")
    c1 = get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "bal_acc_mean")
    c0 = get("utc", "mt5", "fresh_2021_2022", "native_default", "bal_acc_mean")
    d = get("server", "mt5", "fresh_2021_2022", "R2_conservative", "diff_vs_native_default")
    ok = dict(a_fresh_ci_lo_gt_0=a > 0, b_inspected_diff_ge_0=b >= 0, c_fresh_balprecision_ge_default=c1 >= c0, d_server_fresh_diff_gt_0=d > 0)
    fin = FN[(FN.filter_tf == n) & (FN.clock == "utc") & (FN.read == "mt5")]
    r2 = fin[fin.method == "R2_conservative"].setting.iloc[0] if len(fin) else ""
    dec.append(dict(filter_tf=n,
                    fresh_R2_auc=get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "auc_mean"),
                    fresh_default_auc=get("utc", "mt5", "fresh_2021_2022", "native_default", "auc_mean"),
                    fresh_diff=get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "diff_vs_native_default"),
                    fresh_diff_ci_lo=a, fresh_diff_ci_hi=get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "diff_ci_hi"),
                    inspected_diff=b, fresh_R2_bal_precision=c1, fresh_default_bal_precision=c0, server_fresh_diff=d, **ok,
                    decision="suggest change (for broker check)" if all(ok.values()) else "keep default",
                    R2_final_pick_2020_2025H1=r2,
                    # extra evidence requested after the freeze (not part of the frozen rule)
                    fresh_endpoint_purged_diff=get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "diff_vs_native_default", "endpoint_purged"),
                    fresh_endpoint_purged_diff_ci_lo=get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "diff_ci_lo", "endpoint_purged"),
                    fresh_R2_acc=get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "acc_mean"),
                    fresh_default_acc=get("utc", "mt5", "fresh_2021_2022", "native_default", "acc_mean"),
                    fresh_acc_diff_ci_lo=get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "acc_diff_ci_lo"),
                    fresh_acc_diff_ci_hi=get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "acc_diff_ci_hi"),
                    fresh_coverage_diff=get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "coverage_diff_vs_native_default"),
                    fresh_R2_bal_recall=get("utc", "mt5", "fresh_2021_2022", "R2_conservative", "bal_recall_mean"),
                    fresh_default_bal_recall=get("utc", "mt5", "fresh_2021_2022", "native_default", "bal_recall_mean"),
                    inspected_acc_diff=get("utc", "mt5", "inspected_2023_2025H1", "R2_conservative", "acc_diff_vs_native_default"),
                    expl_final_R2_auc_diff=get("utc", "mt5", "inspected_final_2025H2_2026", "R2_conservative", "diff_vs_native_default"),
                    expl_final_R2_acc_diff=get("utc", "mt5", "inspected_final_2025H2_2026", "R2_conservative", "acc_diff_vs_native_default")))
pd.DataFrame(dec).to_csv(f"{DST}/wf_decision.csv", index=False, float_format="%.5f")

# graded scores
gp = sorted(glob.glob(f"{SRC}/graded_pooled_*_real.csv"))
if gp:
    G = pd.concat([pd.read_csv(x) for x in gp]); G.insert(0, "filter_tf", G.tf.map(W.NAMES))
    G.to_csv(f"{DST}/wf_graded_pooled.csv", index=False, float_format="%.5f")
    pd.concat([pd.read_csv(x.replace("pooled", "folds")) for x in gp]).to_csv(f"{DST}/wf_graded_folds.csv", index=False, float_format="%.5f")
for name in ("broker_eval_real.csv", "broker_zone_agreement_real.csv", "broker_clock_real.csv", "broker_clock_best_real.csv"):
    if os.path.exists(f"{SRC}/{name}"):
        pd.read_csv(f"{SRC}/{name}").rename(columns=lambda c: c.replace("bal_acc", "bal_precision")).to_csv(
            f"{DST}/{name.replace('_real', '')}", index=False, float_format="%.5f")
print(pd.DataFrame(dec).to_string())
