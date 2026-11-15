"""Leakage tests on the module's own selection code (hump_wf.window_pick and hump_wf.wf_tf), every timeframe.
 1. For every condition and every test year: the picks, scores and costs of window_pick are unchanged when the
    test year and every later year are replaced by noise, and unchanged when the years before the window are.
 2. wf_tf on a copy of the array whose last year (2026) is noise: every field of every cell except `final` is
    unchanged (so the last year plays no part in the pass flag), and the final window's picks are unchanged.
Usage: [HUMP_SYMBOL=BTCUSD] python3 leak.py <work> <tmp_dir> <out_json>   (run from research/)"""
import json, os, pickle, shutil, sys, time
import numpy as np
work, tmp, out_json = sys.argv[1:4]
ONLY = sys.argv[4].split(",") if len(sys.argv) > 4 else None
sys.path.insert(0, "/workspace/master/research")
import hump_wf as W

os.makedirs(tmp, exist_ok=True)
rng = np.random.default_rng(99)
cnt = dict(tfs=[], windows=0, future_changed=0, past_windows=0, past_changed=0, score_or_cost_changed=0, cells=0, cells_changed_besides_final=0,
           final_picks_changed=0, final_field_changed=0)


def noise(shape):
    x = rng.random(shape) * 400.0
    x[..., 0] = np.floor(x[..., 0])                  # trade counts
    return x


for tf in W.TFS:
    fn = os.path.join(work, f"wf_{tf}.npy")
    if not os.path.exists(fn) or (ONLY and tf not in ONLY):
        continue
    t0 = time.time()
    A32 = np.load(fn, mmap_mode="r")
    d = pickle.load(open(os.path.join(work, f"wf_{tf}_params.pkl"), "rb"))
    P, years = d["params"], d["years"]; Y = len(years)
    for v in range(A32.shape[1]):
        A1 = np.asarray(A32[:, v:v + 1], dtype=np.float64)
        for ty in range(3, Y):
            cal = [ty - 3, ty - 2, ty - 1]
            p0, s0, c0, e0, f0 = W.window_pick(A1, P, 0, cal)
            A2 = A1.copy(); A2[:, :, :, ty:, :] = noise(A2[:, :, :, ty:, :].shape)
            p1, s1, c1, e1, f1 = W.window_pick(A2, P, 0, cal)
            cnt["windows"] += 1
            cnt["future_changed"] += int(p0 != p1)
            cnt["score_or_cost_changed"] += int(not (np.array_equal(s0, s1, equal_nan=True) and np.array_equal(c0, c1, equal_nan=True) and (e0, f0) == (e1, f1)))
            if ty > 3:
                A3 = A1.copy(); A3[:, :, :, :ty - 3, :] = noise(A3[:, :, :, :ty - 3, :].shape)
                p2 = W.window_pick(A3, P, 0, cal)[0]
                cnt["past_windows"] += 1; cnt["past_changed"] += int(p0 != p2)
    # 2. the last year replaced by noise, through wf_tf
    ref = W.wf_tf(work, tf)
    A = np.array(A32)
    A[:, :, :, Y - 1, :] = noise(A[:, :, :, Y - 1, :].shape).astype(np.float32)
    np.save(os.path.join(tmp, f"wf_{tf}.npy"), A)
    shutil.copy(os.path.join(work, f"wf_{tf}_params.pkl"), os.path.join(tmp, f"wf_{tf}_params.pkl"))
    del A
    alt = W.wf_tf(tmp, tf)
    for r, a in zip(ref, alt):
        cnt["cells"] += 1
        ra = json.dumps({k: v for k, v in r.items() if k != "final"}, sort_keys=True, default=str)
        aa = json.dumps({k: v for k, v in a.items() if k != "final"}, sort_keys=True, default=str)
        cnt["cells_changed_besides_final"] += int(ra != aa)
        cnt["final_picks_changed"] += int(r["final"]["picks"] != a["final"]["picks"])
        cnt["final_field_changed"] += int(json.dumps(r["final"], default=str) != json.dumps(a["final"], default=str))
    os.remove(os.path.join(tmp, f"wf_{tf}.npy")); os.remove(os.path.join(tmp, f"wf_{tf}_params.pkl"))
    cnt["tfs"].append(tf)
    print(tf, f"{time.time() - t0:.0f}s", json.dumps(cnt), flush=True)
json.dump(cnt, open(out_json, "w"))
print("LEAK_DONE", json.dumps(cnt))
