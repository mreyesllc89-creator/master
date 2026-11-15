#!/usr/bin/env python3
"""
The decision of research/results/wf/protocol2_decision.md applied to EURUSD and US500, from the result files:
  rule 1  the pass rule                   research/results/wf/{eurusd,us500}_wf_summary.json (make_wf_html.py)
  rule 2  the same rule once per signal   research/results/wf/fx_eval/<sym>_<TF>_<cond>_detail.json (hump_wf.py detail)
  rule 3  not chance (no-skill reshuffle) research/results/wf/fx_eval/nulls_<sym>.json (audit_wf/protocol2/nulls2.py)
  rule 4  the 2026 months                 the detail json's final year (run only for cells that pass)
Writes research/results/wf/fx_decision.json. Usage (from research/): python3 fx_decision.py
"""
import json, os

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "wf")
out = {}
for sym in ("EURUSD", "US500"):
    summ = json.load(open(os.path.join(D, f"{sym.lower()}_wf_summary.json")))
    nulls = json.load(open(os.path.join(D, "fx_eval", f"nulls_{sym.lower()}.json")))["headline"]
    passed = [r for r in summ["rows"] if r["passes"]]
    cells = []
    for r in passed:
        det = json.load(open(os.path.join(D, "fx_eval", f"{sym.lower()}_{r['tf']}_{r['condition']}_detail.json")))
        sig = det["distinct_signals"]["walk_forward"]
        fy = det["distinct_signals"]["final_year"]
        key = f"{r['tf']} {r['condition']}"
        share = nulls["setup"]["real_cells_pass_share"].get(key)
        rule3 = bool(share is not None and share < 0.05 and len(passed) > nulls["setup"]["p95"])
        final_n = det["final_year"].get("n", 0) if isinstance(det.get("final_year"), dict) else 0
        final_pf = det["final_year"].get("pf") if final_n else None
        rule4 = ("confirmed" if final_n and final_pf >= 1.3 else "not confirmed" if final_n and final_pf >= 1.0
                 else "failed" if final_n else "no setups qualified for 2026")
        cells.append(dict(
            tf=r["tf"], condition=r["condition"], text=r["text"],
            rule1=dict(trades=r["n"], pf=r["pf"], stress_pf=r["stress_pf"], years_with_50=r["years_with_50_trades"],
                       by_year={y["year"]: dict(trades=y["n"], pf=y["pf"]) for y in r["by_year"] if y["n"]}, met=True),
            rule2=dict(signals=sig["signals"], pf=sig["pf"], stress_pf=sig["stress_pf"], years_with_50=sig["years_with_50_signals"],
                       losing_years=sig["losing_years"], met=bool(sig["passes"])),
            rule3=dict(cell_share_of_no_skill_runs=share, symbol_passes=len(passed), no_skill_p95=nulls["setup"]["p95"],
                       no_skill_mean=nulls["setup"]["mean_passes_per_run"], share_runs_with_as_many=nulls["setup"]["share_runs_at_least_real"],
                       runs=nulls["setup"]["runs"], met=rule3),
            rule4=dict(trades=final_n, pf=final_pf, signals=fy.get("signals", 0), outcome=rule4),
            result=bool(sig["passes"] and rule3 and rule4 == "confirmed")))
    out[sym] = dict(cells=len(summ["rows"]), passes=len(passed), no_skill=nulls["setup"], order=nulls["order"], passing_cells=cells,
                    results=[f"{c['tf']} {c['condition']}" for c in cells if c["result"]])
json.dump(out, open(os.path.join(D, "fx_decision.json"), "w"), indent=1, default=float)
for sym, v in out.items():
    print(f"{sym}: {v['passes']} of {v['cells']} cells met the pass rule; no-skill reshuffle {v['no_skill']['mean_passes_per_run']:.2f} passes per run "
          f"(95th percentile {v['no_skill']['p95']:.0f}); results: {v['results'] or 'none'}")
    for c in v["passing_cells"]:
        print(f"  {c['tf']} {c['condition']}: rule 1 {c['rule1']['pf']:.3f} on {c['rule1']['trades']}; rule 2 {c['rule2']['pf']:.3f} on {c['rule2']['signals']} signals "
              f"(met {c['rule2']['met']}); rule 3 cell share {c['rule3']['cell_share_of_no_skill_runs']}, count {c['rule3']['symbol_passes']} vs p95 "
              f"{c['rule3']['no_skill_p95']} (met {c['rule3']['met']}); rule 4 {c['rule4']['outcome']}")
