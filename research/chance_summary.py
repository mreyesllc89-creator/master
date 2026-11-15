#!/usr/bin/env python3
"""
How many year-by-year passes chance alone produces, from the independent audit of hump_wf.py (scripts in
research/audit_wf/, outputs in research/results/wf/audit/), in one file the guides and the report quote:
research/results/wf/chance_check.json.

  placebo     cells built like the real ones but cut loose from the signals (a condition's mask read 10-90% of the
              series earlier, timing windows moved by random hours, random masks with a condition's keep share),
              run through the same selection and pass rule: passes per cell, scaled to the symbol's 472 cells
  no skill    every year, the setups' results are swapped among setups of similar activity: the link between a
              setup's calibration years and its test year is gone, the market-wide effect of a condition stays
  year order  the years before the final one in a random order (calibration years can then lie after the test year)
  thin        the passing BTC cell's trades collapsed to distinct signals (several picks often take the same one)

Usage (from research/): python3 chance_summary.py
"""
import json, os
import numpy as np

A = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "wf", "audit")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "wf", "chance_check.json")


def nulls(*files):
    sp = op = None; cell = {}
    for f in files:
        d = json.load(open(os.path.join(A, f)))
        for tf, v in d["tfs"].items():
            s = np.array(v["setup"], bool); o = np.array(v["order"], bool)
            sp = s.sum(1) if sp is None else sp + s.sum(1)
            op = o.sum(1) if op is None else op + o.sum(1)
            for j, k in enumerate(v["keys"]):
                if v["real_pass"][j]:
                    cell[f"{tf} {k}"] = dict(no_skill_share=float(s[:, j].mean()), year_order_share=float(o[:, j].mean()))
    q = lambda a: dict(mean=float(a.mean()), p05=float(np.percentile(a, 5)), p95=float(np.percentile(a, 95)),
                       at_least_2=float((a >= 2).mean()), permutations=int(len(a)))
    return dict(no_skill=q(sp), year_order=q(op), real_passes_in_nulls=cell)


out = {}
for sym, summ, nfiles in (("BTCUSD", "summary_btc2.json", ("nulls_btc2.json",)),
                          ("XAUUSD", "summary_gold2.json", ("nulls_gold2.json", "nulls_gold2_new.json"))):
    s = json.load(open(os.path.join(A, summ)))
    e = s["expected_false_from_placebo"]
    out[sym] = dict(cells=s["cells"], real_passes=[dict(tf=t, condition=c, pf=pf, trades=n) for t, c, pf, n in s["real_passes"]],
                    controls=dict(cells=s["control_cells"], passed=len(s["control_passes"])),
                    placebo=dict(cells=s["placebo_cells"], timeframes=s["placebo_tfs"], passed=len(s["placebo_passes"]),
                                 expected_passes=e["point"], ci95=e["ci95"],
                                 passes=[dict(tf=t, cell=c, pf=pf, trades=n) for t, c, pf, n in s["placebo_passes"]]),
                    **nulls(*nfiles))
t = json.load(open(os.path.join(A, "thin_btc2.json")))["M30:xlzc_stoch"]
w, f = t["walk_forward"], t["final"]
out["BTCUSD"]["thin_M30_xlzc_stoch"] = dict(
    walk_forward=dict(trades=w["n"], signals=w["unique_signals"], pf=w["pf"], pf_signals=w["pf_unique"],
                      bootstrap_signals=dict(p05=w["bootstrap_weeks_unique_signals"]["p05"], p95=w["bootstrap_weeks_unique_signals"]["p95"],
                                             below_1_3=w["bootstrap_weeks_unique_signals"]["below_1_3"])),
    final=dict(trades=f["n"], signals=f["unique_signals"], pf=f["pf"], pf_signals=f["pf_unique"], net_share_of_10_largest=f["net_share_of_10_largest"]),
    by_year={y: dict(trades=v["n"], signals=v["unique_signals"], pf=v["pf"], pf_signals=v["pf_unique"]) for y, v in t["by_year"].items()})
import pandas as pd
rng = np.random.default_rng(1)


def spear(a, b):
    return float(pd.Series(a).rank().corr(pd.Series(b).rank()))


for sym in ("BTCUSD", "XAUUSD"):       # does a cell's walk-forward result predict its 2026 result? (cells with 100+ unseen and 50+ 2026 trades)
    d = json.load(open(os.path.join(os.path.dirname(A), f"{sym.lower()}_wf_summary.json")))
    rows = [r for r in d["rows"] if r["n"] >= 100 and r["final"]["n"] >= 50]
    a_, b_ = [r["pf"] for r in rows], [r["final"]["pf"] for r in rows]
    rho = spear(a_, b_); perm = [spear(a_, rng.permutation(b_)) for _ in range(2000)]
    out[sym]["walk_forward_vs_2026"] = dict(cells=len(rows), rank_correlation=rho, permutation_p=float(np.mean(np.abs(perm) >= abs(rho))))
# the liquidity sweep of xlzc_both holds on almost every signal (features audit: 95.3% of BTC M30 signals), so
# xlzc_both is xlzc_stoch minus about 5% of its signals: the two BTC passes are one result
out["BTCUSD"]["sweep_share_of_signals_M30"] = 0.953
json.dump(out, open(OUT, "w"), indent=1)
b = out["BTCUSD"]
print(f"BTC: {len(b['real_passes'])} real passes of {b['cells']}; placebo {b['placebo']['passed']}/{b['placebo']['cells']} -> "
      f"{b['placebo']['expected_passes']:.1f} expected ({b['placebo']['ci95'][0]:.2f}-{b['placebo']['ci95'][1]:.1f}); no skill {b['no_skill']['mean']:.1f} per run "
      f"({b['no_skill']['p05']:.1f}-{b['no_skill']['p95']:.1f}), 2+ in {b['no_skill']['at_least_2']:.0%}; M30 xlzc_stoch passes in "
      f"{b['real_passes_in_nulls']['M30 xlzc_stoch']['no_skill_share']:.0%} of the no-skill runs")
th = b["thin_M30_xlzc_stoch"]["walk_forward"]
print(f"     M30 xlzc_stoch: {th['trades']} trades = {th['signals']} signals, PF {th['pf']:.2f} -> {th['pf_signals']:.2f} per signal; "
      f"bootstrap {th['bootstrap_signals']['p05']:.2f}-{th['bootstrap_signals']['p95']:.2f}, below 1.3 in {th['bootstrap_signals']['below_1_3']:.0%}")
g = out["XAUUSD"]
print(f"gold: {len(g['real_passes'])} real passes; placebo {g['placebo']['expected_passes']:.2f} expected; no skill {g['no_skill']['mean']:.2f}; year order {g['year_order']['mean']:.2f}")
