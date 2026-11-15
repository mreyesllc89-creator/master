"""Compare wf2 (independent protocol-2 recomputation) with the `hump_wf.py wf` JSON: every cell, every window.
Usage: python3 compare2.py <work> <ref_json> <out_json>
2026 is computed only for cells that pass (in the reference or here); nothing else about 2026 is computed."""
import json, math, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wf2 as M

work, ref_json, out_json = sys.argv[1:4]
ref = json.load(open(ref_json))
assert (ref["min_n"], ref["topk"], ref["pass_pf"], ref["pass_stress_pf"], ref["pass_n"], ref["year_n"], ref["max_cost_r"]) == \
    (M.MIN_N, M.TOPK, M.PASS_PF, M.PASS_STRESS, M.PASS_N, M.YEAR_N, M.MAX_COST), "constants differ from the docstring"
assert ref.get("protocol") == 2
rrows = {(r["tf"], r["condition"]): r for r in ref["rows"]}


def same(a, b, tol=1e-6):
    if a is None or b is None:
        return (a is None or (isinstance(a, float) and a != a)) and (b is None or (isinstance(b, float) and b != b))
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(same(x, y, tol) for x, y in zip(a, b))
    a = float(a); b = float(b)
    if a != a or b != b:
        return a != a and b != b
    if math.isinf(a) or math.isinf(b):
        return a == b
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def rel(a, b):
    try:
        a = float(a); b = float(b)
    except (TypeError, ValueError):
        return 0.0
    if a != a or b != b or math.isinf(a) or math.isinf(b):
        return 0.0
    return abs(a - b) / max(1.0, abs(a), abs(b))


WF = ("n", "win", "loss", "cost_r", "stress_n", "stress_win", "stress_loss", "pf", "stress_pf", "eligible", "eligible_after_cost_rule")
CF = ("n", "pf", "stress_pf", "net_r", "cost_r_per_trade", "years_with_50_trades", "losing_years", "passes")
cnt = dict(tfs=[], cells=0, windows=0, windows_with_picks_ref=0, picks_total_ref=0, final_windows=0, pick_order_diff=0,
           pick_set_diff=0, field_diff=0, score_diff=0, cell_diff=0, pass_diff=0, final_presence_diff=0, missing=0,
           tie_windows=0, f32_candidate_flips=0, near_threshold_windows=0)
maxrel = {f: 0.0 for f in WF + ("net_r", "cost_r_per_trade", "cell_pf", "cell_stress_pf")}
diffs, cells_out, sanity, near = [], [], {}, []
ONLY = os.environ.get("ONLY_TFS", "").split(",") if os.environ.get("ONLY_TFS") else None
for tf in ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]:
    if ONLY and tf not in ONLY:
        continue
    t0 = time.time()
    A, d = M.load(work, tf)
    Am = np.array(A, dtype=np.float32)                     # one TF in memory (634 MB); nothing written to disk
    P, years, keys = d["params"], list(d["years"]), d["keys"]
    assert years == list(range(2013, 2027)) and Am.shape[:2] == (len(P), len(keys))
    fam = M.fam_codes(P)
    # layout sanity: same-year sums can only be part of the entry-year sums
    E, S = Am[..., 0], Am[..., 4]
    cross = (E - S)                                         # trades that close after their entry year
    sanity[tf] = dict(same_gt_entry_trades=int((S > E + 1e-3).sum()),
                      same_gt_entry_win=int((Am[..., 5] > Am[..., 1] + 1e-3).sum()),
                      same_gt_entry_loss=int((Am[..., 6] > Am[..., 2] + 1e-3).sum()),
                      cross_year_trades_base_cond_by_entry_year={str(y): float(cross[:, 0, 0, i].sum()) for i, y in enumerate(years)},
                      cross_share_all=float(cross[:, :, 0].sum() / max(1.0, float(E[:, :, 0].astype(np.float64).sum()))))
    del E, S, cross
    cnt["tfs"].append(tf)
    for v, key in enumerate(keys):
        cnt["cells"] += 1
        r = rrows.get((tf, key))
        if r is None:
            cnt["missing"] += 1; diffs.append(("missing", tf, key)); continue
        Av = Am[:, v]                                       # [N, 2, Y, 8]
        n, pf, c = M.cond_stats(Av)
        # float32 PFs, to see whether the precision of the division could move a setup across the 1.3 line
        S32 = Av[:, :, :, M.SAME]
        with np.errstate(divide="ignore", invalid="ignore"):
            pf32 = np.where(S32[..., 2] > 0, S32[..., 1] / S32[..., 2], np.where(S32[..., 1] > 0, np.inf, np.nan)).astype(np.float32)
        wins = []
        for t in range(3, len(years) - 1):                  # test years 2016..2025
            cal = [t - 3, t - 2, t - 1]
            score, elig, cpt, ok, worst = M.score_window(n, pf, c, cal)
            pk = M.picks_of(score, fam)
            s, cols = M.test_sums(Av, pk, t, years)
            w = M.window_dict(years[t], pk, s, score, elig, cpt, cols)
            if M.tie_info(score, fam, pk):
                cnt["tie_windows"] += 1
            # precision check of the selection threshold
            pc32 = pf32[:, :, cal]
            worst32 = np.where(np.isnan(pc32), np.inf, pc32).min(axis=(1, 2))
            flips = int(((worst32 >= np.float32(M.SEL_PF)) != (worst >= M.SEL_PF))[ok].sum())
            cnt["f32_candidate_flips"] += flips
            okw = worst[ok & np.isfinite(worst)]
            if len(okw):
                dmin = float(np.min(np.abs(okw - M.SEL_PF)))
                if dmin < 1e-6:
                    cnt["near_threshold_windows"] += 1; near.append((tf, key, years[t], dmin))
            wins.append(w)
        ver = M.verdict(wins)
        final = None
        if ver["passes"] or r["passes"]:
            t = len(years) - 1
            cal = [t - 3, t - 2, t - 1]
            score, elig, cpt, ok, worst = M.score_window(n, pf, c, cal)
            pk = M.picks_of(score, fam)
            s, cols = M.test_sums(Av, pk, t, years)
            final = M.window_dict(years[t], pk, s, score, elig, cpt, cols)
        # ---- compare windows
        assert r["unseen_years"] == [w["year"] for w in wins], (tf, key)
        pairs = list(zip(wins, r["by_year"]))
        if ("final" in r) != (final is not None and r["passes"]):
            cnt["final_presence_diff"] += 1; diffs.append(("final_presence", tf, key, "final" in r, final is not None))
        if "final" in r and final is not None:
            pairs.append((final, r["final"])); cnt["final_windows"] += 1
        for a, b in pairs:
            cnt["windows"] += 1
            assert a["year"] == b["year"]
            if b["picks"]:
                cnt["windows_with_picks_ref"] += 1; cnt["picks_total_ref"] += len(b["picks"])
            if a["picks"] != b["picks"]:
                cnt["pick_order_diff"] += 1
                if sorted(a["picks"]) != sorted(b["picks"]):
                    cnt["pick_set_diff"] += 1
                diffs.append(("picks", tf, key, a["year"], a["picks"], b["picks"]))
            for f in WF:
                maxrel[f] = max(maxrel[f], rel(a[f], b[f]))
                if not same(a[f], b[f]):
                    cnt["field_diff"] += 1; diffs.append(("field", tf, key, a["year"], f, a[f], b[f]))
            if [round(x, 3) for x in a["scores"]] != list(b.get("scores", [])):
                cnt["score_diff"] += 1; diffs.append(("scores", tf, key, a["year"], a["scores"], b.get("scores")))
        # ---- compare the cell
        for f in CF:
            a, b = ver[f], r[f]
            if f in ("pf", "stress_pf"):
                maxrel["cell_" + f] = max(maxrel["cell_" + f], rel(a, b))
            elif f in ("net_r", "cost_r_per_trade"):
                maxrel[f] = max(maxrel[f], rel(a, b))
            if f == "passes":
                if bool(a) != bool(b):
                    cnt["pass_diff"] += 1; diffs.append(("pass", tf, key, a, b))
            elif not same(a, b):
                cnt["cell_diff"] += 1; diffs.append(("cell", tf, key, f, a, b))
        cells_out.append(dict(tf=tf, condition=key, n=ver["n"], pf=ver["pf"], stress_pf=ver["stress_pf"], passes=ver["passes"],
                              years_with_50_trades=ver["years_with_50_trades"], losing_years=ver["losing_years"],
                              picks_by_year={str(w["year"]): w["picks"] for w in wins if w["picks"]},
                              final_picks=(final["picks"] if final is not None else None)))
    print(f"{tf}: {len(keys)} cells, {time.time() - t0:.0f}s; diffs so far {len(diffs)}", flush=True)
    del Am, A
cnt["ref_cells"] = len(ref["rows"])
cnt["passes_mine"] = [(c["tf"], c["condition"]) for c in cells_out if c["passes"]]
cnt["passes_ref"] = [(r["tf"], r["condition"]) for r in ref["rows"] if r["passes"]]
print(json.dumps(cnt))
print(json.dumps(maxrel))
for x in diffs[:40]:
    print("DIFF", x)
json.dump(dict(symbol=ref["symbol"], count=cnt, max_rel_diff=maxrel, diffs=diffs[:500], near_threshold=near[:200],
               layout_sanity=sanity, cells=cells_out), open(out_json, "w"), default=float)
print("COMPARE_DONE", ref["symbol"], flush=True)
