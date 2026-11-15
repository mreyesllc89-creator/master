"""Compare my re-implementation (wfcore) with the module's `hump_wf.py wf` JSON, every cell and every window.
Usage: python3 compare.py <work> <ref_json> <out_json>"""
import json, math, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wfcore as M

work, ref_json, out_json = sys.argv[1:4]
ref = json.load(open(ref_json))
assert (ref["min_n"], ref["topk"], ref["pass_pf"], ref["pass_stress_pf"], ref["pass_n"], ref["year_n"], ref["max_cost_r"]) == \
    (M.MIN_N, M.TOPK, M.PASS_PF, M.PASS_STRESS, M.PASS_N, M.YEAR_N, M.MAX_COST), "constants differ from the docstring"
rrows = {(r["tf"], r["condition"]): r for r in ref["rows"]}


def same(a, b, tol=1e-9):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same(x, y, tol) for x, y in zip(a, b))
    a = float(a); b = float(b)
    if a != a or b != b:
        return a != a and b != b
    if math.isinf(a) or math.isinf(b):
        return a == b
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


cnt = dict(tfs=[], cells=0, windows=0, final_windows=0, pick_diff=0, field_diff=0, cell_diff=0, pass_diff=0, missing=0)
diffs = []
mine_rows = []
WFIELDS = ("n", "win", "loss", "cost_r", "stress_n", "stress_win", "stress_loss", "pf", "stress_pf", "eligible", "eligible_after_cost_rule")
for tf in ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]:
    if not os.path.exists(os.path.join(work, f"wf_{tf}.npy")):
        continue
    t0 = time.time()
    A, d = M.load(work, tf)
    A = np.array(A)                                           # float32 in memory
    P, years, keys = d["params"], d["years"], d["keys"]
    fam = M.fam_codes(P)
    res = M.cells(A, fam, years, keep_scores=True)
    cnt["tfs"].append(tf)
    for v, key in enumerate(keys):
        cnt["cells"] += 1
        r = rrows.get((tf, key))
        if r is None:
            cnt["missing"] += 1; diffs.append(("missing", tf, key)); continue
        m = res[v]
        assert r["unseen_years"] == [w["year"] for w in m["by_year"]], (tf, key)
        for a, b in zip(m["by_year"] + [m["final"]], r["by_year"] + [r["final"]]):
            cnt["windows"] += 1
            if a["year"] == years[-1]:
                cnt["final_windows"] += 1
            assert a["year"] == b["year"]
            if a["picks"] != b["picks"]:
                cnt["pick_diff"] += 1; diffs.append(("picks", tf, key, a["year"], a["picks"], b["picks"]))
            for f in WFIELDS:
                if not same(a[f], b[f]):
                    cnt["field_diff"] += 1; diffs.append(("field", tf, key, a["year"], f, a[f], b[f]))
            if not same([round(s, 3) for s in a["scores"]], b["scores"], 1e-12):
                cnt["field_diff"] += 1; diffs.append(("scores", tf, key, a["year"], a["scores"], b["scores"]))
        net = m["win"] - m["loss"]
        cpt = (sum(w["cost_r"] for w in m["by_year"]) / m["n"]) if m["n"] else None
        for f, a, b in (("n", m["n"], r["n"]), ("pf", m["pf"], r["pf"]), ("stress_pf", m["stress_pf"], r["stress_pf"]), ("net_r", net, r["net_r"]),
                        ("cost_r_per_trade", cpt, r["cost_r_per_trade"]), ("years_with_50_trades", m["years_with_50_trades"], r["years_with_50_trades"]),
                        ("losing_years", m["losing_years"], r["losing_years"])):
            if not same(a, b):
                cnt["cell_diff"] += 1; diffs.append(("cell", tf, key, f, a, b))
        if m["passes"] != r["passes"]:
            cnt["pass_diff"] += 1; diffs.append(("pass", tf, key, m["passes"], r["passes"]))
        mine_rows.append(dict(tf=tf, condition=key, **{k: m[k] for k in ("n", "win", "loss", "pf", "stress_pf", "years_with_50_trades", "losing_years", "passes")},
                              by_year=m["by_year"], final=m["final"]))
    print(f"{tf}: {len(keys)} cells, {time.time() - t0:.0f}s", flush=True)
    del A
cnt["ref_cells"] = len(ref["rows"])
cnt["passes_mine"] = [(r["tf"], r["condition"]) for r in mine_rows if r["passes"]]
cnt["passes_ref"] = [(r["tf"], r["condition"]) for r in ref["rows"] if r["passes"]]
print(json.dumps(cnt))
for x in diffs[:40]:
    print("DIFF", x)
json.dump(dict(count=cnt, diffs=diffs[:500], rows=mine_rows), open(out_json, "w"), default=float)
