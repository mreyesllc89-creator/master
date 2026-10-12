"""Markdown tables for the option-2 (score veto) test. Usage: python veto_tables.py <veto_eval_real.csv> <veto_reading_real.csv>"""
import sys
import pandas as pd

d = pd.read_csv(sys.argv[1]); m = d[d.H == "mean"]
rd = pd.read_csv(sys.argv[2])
ORDER = ["M5", "M15", "M30", "H1"]


def ci(lo, hi):
    return f"[{lo:+.4f}, {hi:+.4f}]"


def row(tf, g, per, rule):
    x = m[(m.tf == tf) & (m.group == g) & (m.period == per) & (m.rule == rule)]
    return x.iloc[0] if len(x) else None


print("### Pre-registered reading rule (fresh 2018-2019, pooled, R2 = zone + score agree vs P0 = zone alone)\n")
print("| TF | in rule | P0 acc / cov | R2 acc / cov | R2 - P0 acc [95% CI] | R2 - P0 AUC [95% CI] | flagged half-years | holds? |")
print("|---|---|---|---|---|---|---|---|")
for r in rd.itertuples():
    p0 = row(r.tf, "fresh 2018-2019", "pooled", "P0"); r2 = row(r.tf, "fresh 2018-2019", "pooled", "R2")
    print(f"| {r.tf} | {'yes' if r.in_rule else 'reported only'} | {p0.acc:.4f} / {p0.coverage:.3f} | {r2.acc:.4f} / {r2.coverage:.3f} | "
          f"{r2.acc_diff_vs_P0:+.4f} {ci(r2.acc_diff_ci_lo, r2.acc_diff_ci_hi)} | {r2.auc_diff_vs_P0:+.4f} {ci(r2.auc_diff_ci_lo, r2.auc_diff_ci_hi)} | "
          f"{r.flagged_fresh_periods if isinstance(r.flagged_fresh_periods, str) and r.flagged_fresh_periods else 'none'} | "
          f"**{'yes' if r.holds == True else ('no' if r.holds == False else '-')}** |")

print("\n### All rules, every group (mean of H = 1/3/10; accuracy = share right among BUY / SELL calls)\n")
print("| TF | group | rule | coverage | raw acc [95% CI] | AUC | acc diff vs zone [CI] | AUC diff vs zone [CI] |")
print("|---|---|---|---|---|---|---|---|")
for tf in ORDER:
    for g, per in (("fresh 2018-2019", "pooled"), ("secondary 2021-2022", "pooled"), ("secondary 2026", "2026")):
        for rule in ("P0", "R2", "R2s", "DV", "G2P"):
            x = row(tf, g, per, rule)
            if x is None:
                continue
            dif = "" if rule == "P0" else f"{x.acc_diff_vs_P0:+.4f} {ci(x.acc_diff_ci_lo, x.acc_diff_ci_hi)}"
            dau = "" if rule == "P0" else f"{x.auc_diff_vs_P0:+.4f} {ci(x.auc_diff_ci_lo, x.auc_diff_ci_hi)}"
            print(f"| {tf} | {g} | {rule} | {x.coverage:.3f} | {x.acc:.4f} [{x.acc_ci_lo:.4f}, {x.acc_ci_hi:.4f}] | {x.auc:.4f} | {dif} | {dau} |")

print("\n### R2 against the simple distance veto DV (same number of calls on training data)\n")
print("| TF | group | R2 acc - DV acc [CI] | R2 AUC - DV AUC [CI] |")
print("|---|---|---|---|")
for tf in ORDER:
    for g, per in (("fresh 2018-2019", "pooled"), ("secondary 2021-2022", "pooled"), ("secondary 2026", "2026")):
        x = row(tf, g, per, "R2")
        if x is None:
            continue
        print(f"| {tf} | {g} | {x.acc_diff_vs_DV:+.4f} {ci(x.acc_diff_vs_DV_ci_lo, x.acc_diff_vs_DV_ci_hi)} | {x.auc_diff_vs_DV:+.4f} {ci(x.auc_diff_vs_DV_ci_lo, x.auc_diff_vs_DV_ci_hi)} |")

print("\n### Fresh half-years one by one (R2 vs zone)\n")
print("| TF | half-year | zone acc / cov | R2 acc / cov | acc diff | AUC diff |")
print("|---|---|---|---|---|---|")
for tf in ORDER:
    for per in ("2018H1", "2018H2", "2019H1", "2019H2"):
        p0 = row(tf, "fresh 2018-2019", per, "P0"); r2 = row(tf, "fresh 2018-2019", per, "R2")
        if p0 is None:
            continue
        print(f"| {tf} | {per} | {p0.acc:.4f} / {p0.coverage:.3f} | {r2.acc:.4f} / {r2.coverage:.3f} | {r2.acc_diff_vs_P0:+.4f} | {r2.auc_diff_vs_P0:+.4f} |")

print("\n### By horizon, fresh pooled (raw accuracy zone / R2)\n")
print("| TF | H = 1 | H = 3 | H = 10 |")
print("|---|---|---|---|")
for tf in ORDER:
    cells = []
    for H in ("1", "3", "10"):
        x = d[(d.tf == tf) & (d.group == "fresh 2018-2019") & (d.period == "pooled") & (d.H == H)].set_index("rule")
        if len(x):
            cells.append(f"{x.loc['P0'].acc:.4f} / {x.loc['R2'].acc:.4f}")
    if cells:
        print(f"| {tf} | " + " | ".join(cells) + " |")
