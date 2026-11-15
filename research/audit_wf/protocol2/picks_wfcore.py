#!/usr/bin/env python3
"""The picks of every window of five cells with the audit's independent selection (audit_wf/wfcore.py, written from the
docstring) on the protocol-2 calibration columns 4-7, against the stored evaluations; the test-year sums from the
stored columns (0-3, and 4-7 for 2025) against the stored evaluation. The 2026 window only for the cell that passed,
and only its calibration years (2023-2025): who would be picked and the best score; no 2026 result column is read.
Arrays read with mmap_mode='r', one condition slice at a time."""
import json, sys
sys.path.insert(0, "/workspace/master/research/audit_wf")
import numpy as np
import wfcore as M

S = "/tmp/claude-0/-workspace-master/53e0ea5b-b347-50b9-8f48-3f5cae086c17/scratchpad/"
cells = [("us500", "M2", "trend_h4"), ("us500", "M5", "adx_h4_20"), ("us500", "M30", "tdr_ge40"),
         ("eurusd", "M15", "pd_break"), ("eurusd", "H1", "htf_macd_2")]
ev = {s: {(r["tf"], r["condition"]): r for r in json.load(open(S + f"wf/{s}_wf.json"))["rows"]} for s in ("us500", "eurusd")}
out = []
for sym, tf, key in cells:
    A, d = M.load(S + f"wfx/{sym}", tf)
    P, years, keys = d["params"], d["years"], list(d["keys"])
    v = keys.index(key)
    X = np.asarray(A[:, v:v + 1], dtype=np.float64)                   # [N, 1, 2, Y, 8]
    del A
    fam = M.fam_codes(P)
    n, pf, c = M.per_year(X[..., 4:8])                                  # calibration: trades that close in the year
    row = ev[sym][(tf, key)]
    final = len(years) - 1
    rec = dict(sym=sym, tf=tf, key=key, windows=[])
    ok_all = True
    for ty in range(3, final + (1 if row["passes"] else 0)):
        cal = [ty - 3, ty - 2, ty - 1]
        sc, elig, cpt = M.scores(n, pf, c, cal)
        pk = M.picks_of(sc[:, 0], fam)
        stored = row["final"] if ty == final else [y for y in row["by_year"] if y["year"] == years[ty]][0]
        w = dict(year=years[ty], picks=pk, same_picks=pk == stored["picks"], best_score=float(sc[:, 0].max()),
                 n_score_ge_1_3=int((sc[:, 0] >= 1.3).sum()), eligible=int(elig[:, 0].sum()),
                 eligible_after_cost=int((elig[:, 0] & (cpt[:, 0] <= M.MAX_COST)).sum()))
        w["same_eligible"] = (w["eligible"], w["eligible_after_cost"]) == (stored["eligible"], stored["eligible_after_cost_rule"])
        if ty < final:                                                  # test sums (never the final year)
            tc = 4 if ty == final - 1 else 0
            s = X[pk, 0][:, :, ty, tc:tc + 4].sum(axis=0) if pk else np.zeros((2, 4))
            w["n"] = int(s[0, 0]); w["pf"] = M.pf1(s[0, 1], s[0, 2]); w["stress_pf"] = M.pf1(s[1, 1], s[1, 2])
            w["same_sums"] = bool(int(s[0, 0]) == stored["n"] and int(s[1, 0]) == stored["stress_n"]
                                  and abs(s[0, 1] - stored["win"]) < 1e-6 and abs(s[0, 2] - stored["loss"]) < 1e-6
                                  and abs(s[1, 1] - stored["stress_win"]) < 1e-6 and abs(s[1, 2] - stored["stress_loss"]) < 1e-6)
        else:                                                           # the 2026 window: who scored best on 2023-2025
            top = np.argsort(-sc[:, 0], kind="stable")[:5]
            w["top5"] = [dict(setup=int(i), score=round(float(sc[i, 0]), 4), cost_r=round(float(cpt[i, 0]), 4),
                              family=[P[i]["sides"], P[i]["session"], P[i]["htf"]]) for i in top]
        ok_all &= w["same_picks"] and w["same_eligible"] and w.get("same_sums", True)
        rec["windows"].append(w)
    rec["all_match"] = bool(ok_all)
    out.append(rec)
    print(sym, tf, key, "all windows match the stored evaluation:", ok_all)
    for w in rec["windows"]:
        if w["picks"] or w["year"] == years[final]:
            print("  ", w["year"], "picks", w["picks"], "best score %.4f" % w["best_score"], "n>=1.3", w["n_score_ge_1_3"],
                  "eligible", w["eligible"], w["eligible_after_cost"], {k: w[k] for k in ("n", "pf", "stress_pf") if k in w}, w.get("top5", ""))
json.dump(out, open(S + "fxeval/detail/picks_wfcore.json", "w"), indent=1)
