"""Evaluate the arrays written by resim.py with my walk-forward (wfcore): placebo cells, the boundary-free re-run
(picks of every window and pass flags against the stored array), or an anchor re-run (pass flags against stored).
Usage: python3 evalpl.py <work> <tf> <resim_dir> <sym> <kind: placebo|anchor:<p0>> [--keep]"""
import json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wfcore as M

work, tf, rdir, sym, kind = sys.argv[1:6]
keep = "--keep" in sys.argv
t0 = time.time()
S, d = M.load(work, tf)
S = np.array(S)
P, years, keys = d["params"], d["years"], d["keys"]
fam = M.fam_codes(P)
ref = M.cells(S, fam, years, keep_scores=True)


def slim(c):
    return dict(n=c["n"], pf=c["pf"], stress_pf=c["stress_pf"], years_with_50_trades=c["years_with_50_trades"], losing_years=c["losing_years"],
                passes=c["passes"], by_year=[{k: w[k] for k in ("year", "picks", "n", "win", "loss", "stress_n", "stress_win", "stress_loss", "pf")} for w in c["by_year"]],
                final={k: c["final"][k] for k in ("year", "picks", "n", "win", "loss", "pf", "stress_pf")})


out = dict(sym=sym, tf=tf, kind=kind, years=years)
if kind == "placebo":
    info = json.load(open(os.path.join(rdir, f"resim_{sym}_{tf}_placebo.json")))
    names = info["placebo_names"]
    fpl = os.path.join(rdir, f"placebo_{sym}_{tf}.npy"); fnb = os.path.join(rdir, f"noboundary_{sym}_{tf}.npy")
    PL = np.array(np.load(fpl, mmap_mode="r"))
    assert PL.shape[:2] == (len(P), len(names))
    pres = M.cells(PL, fam, years)
    out["placebo"] = [dict(name=names[v], **slim(pres[v])) for v in range(len(names))]
    del PL, pres
    NB = np.array(np.load(fnb, mmap_mode="r"))
    nres = M.cells(NB, fam, years)
    cmp = dict(windows=0, picks_changed=0, changed=[], pass_changed=[], final_picks_changed=[])
    for v, key in enumerate(keys):
        for a, b in zip(ref[v]["by_year"] + [ref[v]["final"]], nres[v]["by_year"] + [nres[v]["final"]]):
            cmp["windows"] += 1
            if a["picks"] != b["picks"]:
                cmp["picks_changed"] += 1
                cmp["changed"].append((key, a["year"], len(set(a["picks"]) ^ set(b["picks"]))))
                if a["year"] == years[-1]:
                    cmp["final_picks_changed"].append(key)
        if ref[v]["passes"] != nres[v]["passes"]:
            cmp["pass_changed"].append((key, ref[v]["passes"], nres[v]["passes"], ref[v]["pf"], nres[v]["pf"]))
    # what the boundary trades are: per year of the stored array minus the boundary-free array (base condition, base cost)
    diff_n = (S[:, :, 0, :, 0].astype(np.float64) - NB[:, :, 0, :, 0]).sum(axis=0)       # [V, Y]
    cmp["boundary_trades_per_entry_year_base_condition"] = dict(zip(map(str, years), diff_n[0].tolist()))
    cmp["boundary_trade_share_all_conditions"] = float(diff_n.sum() / S[:, :, 0, :, 0].astype(np.float64).sum())
    out["noboundary"] = cmp
    del NB
    if not keep:
        os.remove(fpl); os.remove(fnb)
else:
    fan = os.path.join(rdir, f"anchor_{sym}_{tf}.npy")
    AN = np.array(np.load(fan, mmap_mode="r"))
    ares = M.cells(AN, fam, years)
    out["anchor"] = [dict(condition=keys[v], ref=slim(ref[v]), alt=slim(ares[v])) for v in range(len(keys))]
    same_picks = sum(a["picks"] == b["picks"] for v in range(len(keys)) for a, b in zip(ref[v]["by_year"] + [ref[v]["final"]], ares[v]["by_year"] + [ares[v]["final"]]))
    out["anchor_summary"] = dict(windows=sum(len(ref[v]["by_year"]) + 1 for v in range(len(keys))), same_picks=int(same_picks),
                                 passes_ref=[keys[v] for v in range(len(keys)) if ref[v]["passes"]], passes_alt=[keys[v] for v in range(len(keys)) if ares[v]["passes"]])
    del AN
    if not keep:
        os.remove(fan)
out["real"] = [dict(condition=keys[v], **slim(ref[v])) for v in range(len(keys))]
json.dump(out, open(os.path.join(rdir, f"eval_{sym}_{tf}_{kind.replace(':', '_')}.json"), "w"), default=float)
s = {k: v for k, v in out.get("noboundary", {}).items() if k != "changed"} if kind == "placebo" else out["anchor_summary"]
print(f"EVAL_DONE {sym} {tf} {kind} {time.time() - t0:.0f}s", json.dumps(s, default=float)[:1500], flush=True)
if kind == "placebo":
    print("placebo passes:", [r["name"] for r in out["placebo"] if r["passes"]], flush=True)
