"""Markdown tables for the handoff from the published CSVs. Usage: python wf_tables.py <results_dir>"""
import sys
import numpy as np
import pandas as pd


def esc(x):
    return str(x).replace(" | ", "; ")

R = sys.argv[1]
P = pd.read_csv(f"{R}/wf_pooled_permission.csv")
D = pd.read_csv(f"{R}/wf_decision.csv")
GR = {"fresh_2021_2022": "fresh 2021-22", "inspected_2023_2025H1": "inspected 2023-25H1",
      "inspected_final_2025H2_2026": "expl. 2025H2-26"}


def f(x, n=4):
    return "" if pd.isna(x) else f"{x:.{n}f}"


def ci(lo, hi, n=4):
    return f"[{lo:+.{n}f}, {hi:+.{n}f}]"


print("### Decision (frozen rule, primary run: UTC, MT5 reads, all labels)\n")
print("| TF | fresh AUC default -> R2 | fresh diff 95% CI | (a) | inspected diff (b) | bal. precision R2 / default (c) | server fresh diff (d) | decision | R2 final pick (train 2020-01..2025-06) |")
print("|---|---|---|---|---|---|---|---|---|")
for r in D.itertuples():
    print(f"| {r.filter_tf} | {f(r.fresh_default_auc)} -> {f(r.fresh_R2_auc)} | {ci(r.fresh_diff_ci_lo, r.fresh_diff_ci_hi)} | {'yes' if r.a_fresh_ci_lo_gt_0 else 'no'} | "
          f"{r.inspected_diff:+.4f} {'yes' if r.b_inspected_diff_ge_0 else 'no'} | {f(r.fresh_R2_bal_precision)} / {f(r.fresh_default_bal_precision)} {'yes' if r.c_fresh_balprecision_ge_default else 'no'} | "
          f"{r.server_fresh_diff:+.4f} {'yes' if r.d_server_fresh_diff_gt_0 else 'no'} | **{r.decision}** | {esc(r.R2_final_pick_2020_2025H1)} |")

print("\n### Raw accuracy and coverage next to AUC (extra evidence, not part of the frozen rule)\n")
print("| TF | fresh raw acc default -> R2 | fresh acc diff 95% CI | fresh coverage diff | fresh bal. recall default -> R2 | endpoint-purged fresh AUC diff (CI low) | inspected acc diff | expl. 2025H2-26 AUC diff / acc diff |")
print("|---|---|---|---|---|---|---|---|")
for r in D.itertuples():
    print(f"| {r.filter_tf} | {f(r.fresh_default_acc)} -> {f(r.fresh_R2_acc)} | {ci(r.fresh_acc_diff_ci_lo, r.fresh_acc_diff_ci_hi)} | {r.fresh_coverage_diff:+.4f} | "
          f"{f(r.fresh_default_bal_recall)} -> {f(r.fresh_R2_bal_recall)} | {r.fresh_endpoint_purged_diff:+.4f} ({r.fresh_endpoint_purged_diff_ci_lo:+.4f}) | {r.inspected_acc_diff:+.4f} | "
          f"{r.expl_final_R2_auc_diff:+.4f} / {r.expl_final_R2_acc_diff:+.4f} |")

print("\n### Native default and R2 per group (primary run)\n")
print("| TF | group | months | native default AUC [95% CI] | R2 AUC [95% CI] | R1 AUC | default raw acc / coverage | R2 raw acc / coverage | labels up / down at H=10 / ties dropped (H=1,3,10) |")
print("|---|---|---|---|---|---|---|---|---|")
pp = P[(P.clock == "utc") & (P.read == "mt5") & (P.labels == "all") & P.group.isin(GR)]
for tf in pp.filter_tf.unique():
    for g in GR:
        x = pp[(pp.filter_tf == tf) & (pp.group == g)].set_index("method")
        if "native_default" not in x.index:
            continue
        d, r2, r1 = x.loc["native_default"], x.loc["R2_conservative"], x.loc["R1_greedy"]
        print(f"| {tf} | {GR[g]} | {int(d.months)} | {f(d.auc_mean)} [{f(d.auc_mean_ci_lo)}, {f(d.auc_mean_ci_hi)}] | {f(r2.auc_mean)} [{f(r2.auc_mean_ci_lo)}, {f(r2.auc_mean_ci_hi)}] | {f(r1.auc_mean)} | "
              f"{f(d.acc_mean)} / {f(d.coverage_mean, 3)} | {f(r2.acc_mean)} / {f(r2.coverage_mean, 3)} | {int(d.n_up_H10)} / {int(d.n_down_H10)} / {int(d.ties_dropped)} |")

for clock, read, title in (("server", "mt5", "server clock (NY+7)"), ("utc", "closed_prev", "closed_prev reads")):
    s = P[(P.clock == clock) & (P.read == read) & (P.labels == "all") & (P.group == "fresh_2021_2022")]
    if len(s) == 0:
        continue
    print(f"\n### Sensitivity: {title}, fresh 2021-22\n")
    print("| TF | default AUC | R2 AUC | R2 diff 95% CI | R1 AUC |")
    print("|---|---|---|---|---|")
    for tf in s.filter_tf.unique():
        x = s[s.filter_tf == tf].set_index("method")
        print(f"| {tf} | {f(x.loc['native_default'].auc_mean)} | {f(x.loc['R2_conservative'].auc_mean)} | {ci(x.loc['R2_conservative'].diff_ci_lo, x.loc['R2_conservative'].diff_ci_hi)} | {f(x.loc['R1_greedy'].auc_mean)} |")

try:
    G = pd.read_csv(f"{R}/wf_graded_pooled.csv")
    print("\n### Graded scores vs the permission (primary run, mean of H=1/3/10, pooled)\n")
    print("| TF | group | P0 permission AUC | G1 distance AUC | G2 logistic AUC [mean CI] |")
    print("|---|---|---|---|---|")
    G = G[G.group.isin(GR)]
    m = G.groupby(["filter_tf", "tf", "group", "score"]).agg(auc=("auc", "mean"), lo=("ci_lo", "mean"), hi=("ci_hi", "mean")).reset_index()
    for tf in sorted(m.tf.unique()):
        for g in GR:
            x = m[(m.tf == tf) & (m.group == g)].set_index("score")
            if len(x) == 0:
                continue
            print(f"| {x.filter_tf.iloc[0]} | {GR[g]} | {f(x.loc['P0 permission'].auc)} | {f(x.loc['G1 distance'].auc)} | {f(x.loc['G2 logistic'].auc)} [{f(x.loc['G2 logistic'].lo)}, {f(x.loc['G2 logistic'].hi)}] |")
except FileNotFoundError:
    pass

B = pd.read_csv(f"{R}/broker_eval.csv")
print("\n### Broker BTCUSD.c vs Bitstamp (server clock), same settings, mean of H=1/3/10, paired 48-hour block CIs\n")
print("| TF | period | setting | sample | broker AUC diff vs default [CI] | broker raw acc diff [CI] | broker coverage diff | Bitstamp AUC diff / acc diff |")
print("|---|---|---|---|---|---|---|---|")
for r in B[(B.source == "broker") & (B.kind != "native_default") & ~B.kind.isin(["tv_default_x124", "input_default_H1_H1H2H4", "zones_off", "frozen_R1_greedy", "wf_fold_R1_greedy"])].itertuples():
    s2 = B[(B.tf == r.tf) & (B.period == r.period) & (B.kind == r.kind) & (B.source == "bitstamp_server_clock")].iloc[0]
    print(f"| {r.tf} | {r.period} | {r.kind}: {esc(r.setting)} | {r.sample} | {r.diff_vs_native_default:+.4f} {ci(r.diff_ci_lo, r.diff_ci_hi)} | "
          f"{r.acc_diff_vs_native_default:+.4f} {ci(r.acc_diff_ci_lo, r.acc_diff_ci_hi)} | {r.coverage_diff_vs_native_default:+.4f} | "
          f"{s2.diff_vs_native_default:+.4f} / {s2.acc_diff_vs_native_default:+.4f} |")
print("\nNative default on broker candles (AUC / raw acc / coverage):\n")
print("| TF | 2024H2 | 2025H1 | 2025H2 |")
print("|---|---|---|---|")
for tf in B.tf.unique():
    cells = []
    for per in ("2024H2", "2025H1", "2025H2"):
        x = B[(B.tf == tf) & (B.period == per) & (B.kind == "native_default") & (B.source == "broker")]
        cells.append(f"{x.auc_mean.iloc[0]:.4f} / {x.acc_mean.iloc[0]:.4f} / {x.coverage_mean.iloc[0]:.3f}" if len(x) else "")
    print(f"| {tf} | " + " | ".join(cells) + " |")
