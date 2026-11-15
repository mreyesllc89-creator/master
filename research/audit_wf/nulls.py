"""Year-label reshuffles on the stored arrays, with my walk-forward (wfcore) and the protocol's pass rule.

SETUP  (no selection skill): for every condition and every year, the setups' results of that year are exchanged
       at random among setups of similar activity (setups sorted by their base trade count in that year and
       condition, permuted inside consecutive blocks of 40). Market-wide year effects of a condition and the
       activity of a setup are kept; the link between a setup's calibration years and its test year is gone.
ORDER  (chronology): the non-final years are put in a random order (the final year stays last and stays out of the
       pass rule); every setup keeps all its results. Calibration years can then lie after the test year.
Usage: python3 nulls.py <work> <sym> <n_setup_perm> <n_order_perm> <out_json>
"""
import json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wfcore as M

work, sym, nperm_s, nperm_o, out_json = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
ONLY = sys.argv[6].split(",") if len(sys.argv) > 6 else None
BLOCK = 40
rng = np.random.default_rng(4242 + (1 if sym == "btc" else 0) + (7 if ONLY else 0))
res = dict(sym=sym, block=BLOCK, tfs={})
for tf in ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]:
    if not os.path.exists(os.path.join(work, f"wf_{tf}.npy")) or (ONLY and tf not in ONLY):
        continue
    t0 = time.time()
    A, d = M.load(work, tf)
    A = np.array(A)
    P, years, keys = d["params"], d["years"], d["keys"]
    fam = M.fam_codes(P)
    N, V, _, Y, _ = A.shape
    real = M.cells(A, fam, years)
    r_tf = dict(keys=keys, real_pass=[bool(real[v]["passes"]) for v in range(V)], setup=[], order=[], orders=[])
    nbase = A[:, :, 0, :, 0]                                        # [N, V, Y] base trade counts
    B = np.empty_like(A)
    blk = np.arange(N) // BLOCK
    for k in range(nperm_s):
        for v in range(V):
            for y in range(Y):
                o = np.lexsort((rng.random(N), nbase[:, v, y]))     # by activity, random among equals
                perm = o[np.lexsort((rng.random(N), blk))]          # a random order inside every block of 40
                src = np.empty(N, np.int64); src[o] = perm          # setup o[j] takes the results of setup perm[j]
                B[:, v, :, y, :] = A[src, v, :, y, :]
        if k == 0:                                                  # the permutation keeps every year's results and activity
            assert np.allclose(np.sort(B[:, :, 0, :, 0], axis=0), np.sort(A[:, :, 0, :, 0], axis=0))
            assert np.allclose(B.sum(axis=0), A.sum(axis=0), rtol=1e-4)
        c = M.cells(B, fam, years)
        r_tf["setup"].append([bool(c[v]["passes"]) for v in range(V)])
    del B
    for k in range(nperm_o):
        order = list(rng.permutation(Y - 1)) + [Y - 1]
        c = M.cells(A, fam, years, order=order)
        r_tf["order"].append([bool(c[v]["passes"]) for v in range(V)])
        r_tf["orders"].append([int(x) for x in order])
    res["tfs"][tf] = r_tf
    s = np.array(r_tf["setup"]) if r_tf["setup"] else np.zeros((0, V)); o = np.array(r_tf["order"]) if r_tf["order"] else np.zeros((0, V))
    print(f"{sym} {tf}: real passes {sum(r_tf['real_pass'])}; SETUP null mean passes/perm {s.sum(axis=1).mean() if len(s) else float('nan'):.2f}; "
          f"ORDER mean passes/perm {o.sum(axis=1).mean() if len(o) else float('nan'):.2f}; {time.time() - t0:.0f}s", flush=True)
    json.dump(res, open(out_json, "w"))
    del A
print("NULLS_DONE", sym, flush=True)
