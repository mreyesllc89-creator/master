"""Summary of the (exploratory) feature-score run: per filter timeframe, the feature set / model with the best mean
validation AUC (2024-01 .. 2025-06; fitted on 2023), and its refitted score on 2025-07 .. 2026-10 (an already inspected
period), next to the zone as is. Usage: python feat_report.py <out_csv>"""
import sys, glob
import pandas as pd

rows = []
for p in sorted(glob.glob("results_auc2/feat_auc_*.csv")):
    d = pd.read_csv(p)
    m = d.groupby(["tf", "set", "model"], sort=False)[["auc_train", "auc_valid", "auc_test", "auc_test_refit"]].mean().reset_index()
    z = m[m.set == "F0 zone"].iloc[0]
    cand = m[m.set != "F0 zone"]
    best = cand.loc[cand.auc_valid.idxmax()]
    for kind, r in (("zone as is", z), ("best by validation", best)):
        rows.append(dict(tf=r.tf, kind=kind, set=r.set, model=r.model, auc_train=r.auc_train, auc_valid=r.auc_valid,
                         auc_test_refit_exploratory=r.auc_test_refit))
    for _, r in cand.iterrows():
        rows.append(dict(tf=r.tf, kind="all", set=r.set, model=r.model, auc_train=r.auc_train, auc_valid=r.auc_valid,
                         auc_test_refit_exploratory=r.auc_test_refit))
out = pd.DataFrame(rows)
out.to_csv(sys.argv[1], index=False, float_format="%.5f")
print(out[out.kind != "all"].to_string())
