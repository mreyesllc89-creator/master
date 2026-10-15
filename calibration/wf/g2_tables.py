"""Markdown tables and the pre-registered reading rule for the G2 broker transfer test.
Usage: python g2_tables.py <g2_broker_eval.csv>"""
import sys
import numpy as np
import pandas as pd

d = pd.read_csv(sys.argv[1])
m = d[d.H == "mean"]
ORDER = ["M5", "M15", "M30", "H1", "H2", "H4", "H8", "D1"]
POOL = "pooled 2024H2-2025H2"


def ci(lo, hi):
    return f"[{lo:+.4f}, {hi:+.4f}]"


def row(tf, per, src, sc):
    x = m[(m.tf == tf) & (m.period == per) & (m.source == src) & (m.score == sc)]
    return x.iloc[0] if len(x) else None


print("### Reading rule (broker candles, pooled 2024H2-2025H2)\n")
print("| TF | P0 zone AUC | G2 AUC | G2 - P0 AUC [CI] | P0 raw acc / cov | G2P raw acc / cov | G2P - P0 acc [CI] | flagged periods (AUC or acc diff < 0) | G2 transfers? |")
print("|---|---|---|---|---|---|---|---|---|")
out = []
for tf in ORDER:
    p0, g2, gp = (row(tf, POOL, "broker", s) for s in ("P0", "G2", "G2P"))
    if p0 is None:
        continue
    # pre-registered flag: G2 - P0 mean-AUC or G2P - P0 raw-accuracy point difference negative in a broker period
    neg = [per for per in ("2024H2", "2025H1", "2025H2")
           if row(tf, per, "broker", "G2") is not None
           and (row(tf, per, "broker", "G2").auc_diff_vs_P0 < 0 or row(tf, per, "broker", "G2P").acc_diff_vs_P0 < 0)]
    c1 = g2.auc_diff_ci_lo > 0
    c2 = gp.acc_diff_ci_lo > 0
    c3 = abs(gp.coverage_diff_vs_P0) <= 0.10
    ok = c1 and c2 and c3
    out.append(dict(tf=tf, transfers=ok, flagged=bool(neg)))
    print(f"| {tf} | {p0.auc:.4f} | {g2.auc:.4f} | {g2.auc_diff_vs_P0:+.4f} {ci(g2.auc_diff_ci_lo, g2.auc_diff_ci_hi)} | "
          f"{p0.acc:.4f} / {p0.coverage:.3f} | {gp.acc:.4f} / {gp.coverage:.3f} | {gp.acc_diff_vs_P0:+.4f} {ci(gp.acc_diff_ci_lo, gp.acc_diff_ci_hi)} | "
          f"{', '.join(neg) if neg else 'none'} | **{'yes' if ok else 'no'}**{' (flagged)' if ok and neg else ''} |")

print("\n### Per period, broker vs Bitstamp server clock (mean of H = 1/3/10)\n")
print("| TF | period | broker P0 / G2 / G2P AUC | broker G2 - P0 [CI] | broker G2P - P0 acc [CI] | Bitstamp P0 / G2 AUC | Bitstamp G2 - P0 |")
print("|---|---|---|---|---|---|---|")
for tf in ORDER:
    for per in ("2024H2", "2025H1", "2025H2"):
        b = {s: row(tf, per, "broker", s) for s in ("P0", "G2", "G2P")}
        s_ = {s: row(tf, per, "bitstamp_server_clock", s) for s in ("P0", "G2")}
        if b["P0"] is None:
            continue
        print(f"| {tf} | {per} | {b['P0'].auc:.4f} / {b['G2'].auc:.4f} / {b['G2P'].auc:.4f} | {b['G2'].auc_diff_vs_P0:+.4f} {ci(b['G2'].auc_diff_ci_lo, b['G2'].auc_diff_ci_hi)} | "
              f"{b['G2P'].acc_diff_vs_P0:+.4f} {ci(b['G2P'].acc_diff_ci_lo, b['G2P'].acc_diff_ci_hi)} | {s_['P0'].auc:.4f} / {s_['G2'].auc:.4f} | {s_['G2'].auc_diff_vs_P0:+.4f} |")

print("\n### By horizon, broker pooled (AUC P0 / G2 / G2P)\n")
print("| TF | H = 1 | H = 3 | H = 10 |")
print("|---|---|---|---|")
for tf in ORDER:
    cells = []
    for H in ("1", "3", "10"):
        x = d[(d.tf == tf) & (d.period == POOL) & (d.source == "broker") & (d.H == H)].set_index("score")
        if len(x) == 0:
            continue
        cells.append(f"{x.loc['P0'].auc:.4f} / {x.loc['G2'].auc:.4f} / {x.loc['G2P'].auc:.4f}")
    if cells:
        print(f"| {tf} | " + " | ".join(cells) + " |")
pd.DataFrame(out).to_csv(sys.argv[1].replace(".csv", "_reading.csv"), index=False)
