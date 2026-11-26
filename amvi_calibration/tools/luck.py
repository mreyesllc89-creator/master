"""How much of what the search found would luck alone produce?

usage: python luck.py <chart_tf_minutes> [results_dir] [n_worlds=300]

A no-skill world is built from the real sweep of a timeframe: calendar months are drawn with
replacement, and in every drawn month the gross R of ALL settings is multiplied by one random
sign. Before costs no setting has an edge in such a world (its expected gross R is zero), while
fees, funding, trade counts, fat tails and the dependence between settings stay as they are.
36 drawn months stand for the search window, 34 further ones for the untouched period.

In every world the same things are counted as on the real data:

  share_both     share of the settings (enough trades in both halves) positive after costs in
                 both halves of the search window
  candidates     settings positive in both halves at base and stressed costs
  gap            share_both of the with-the-filter settings minus that of the inverted ones
  hold-out tests the three transfer tests of holdout.py: how often does luck pass them?
  pick           the steadiest candidate: how often is it positive on the "untouched" months at
                 base and stressed costs with at least 50 trades?
  group test     untouched_check.py's test (candidates against random settings on the untouched
                 months): how often does luck pass it?

Writes results/luck_<tf>m.json. A real count inside the luck-only range is no evidence of an
edge; a real count far above it is.
"""
import json
import os
import sys

import numpy as np

import holdout as H

NS, NU = 36, 34          # months of the search window and of the untouched period
DRAWS = 1000


def counts(net, net_s, cnt, inv, hashes, rng, with_tests=True):
    """The statistics of one world (or of the real data) on its first NS months."""
    S, Ss, C = net[:, :NS], net_s[:, :NS], cnt[:, :NS]
    M = H.split_masks(NS)
    seg = {k: S[:, m].sum(1) for k, m in M.items()}
    seg_s = {k: Ss[:, m].sum(1) for k, m in M.items()}
    n_seg = {k: C[:, m].sum(1) for k, m in M.items()}
    act = {k: (C[:, m] > 0).mean(1) for k, m in M.items()}
    tst = {k: H.month_t(S[:, m]) for k, m in M.items()}

    def elig(a, b):
        return (n_seg[a] >= 30) & (act[a] >= 0.6) & (n_seg[b] >= 1)
    both = elig("h1", "h2") & elig("h2", "h1")
    pos2 = (seg["h1"] > 0) & (seg["h2"] > 0)
    cand = both & pos2 & (seg_s["h1"] > 0) & (seg_s["h2"] > 0)
    out = dict(eligible=int(both.sum()), share_both=float(pos2[both].mean()) if both.any() else 0.0, candidates=int(cand.sum()),
               share_both_with=float(pos2[both & ~inv].mean()) if (both & ~inv).any() else 0.0,
               share_both_inv=float(pos2[both & inv].mean()) if (both & inv).any() else 0.0)
    out["gap"] = out["share_both_with"] - out["share_both_inv"]
    if not with_tests:
        return out, both, cand, tst

    def ok(t):
        return bool(t and t["top_mean"] > 0 and t["top_mean"] > t["null_p95"] and t["boot_pos"] is not None and t["boot_pos"] >= 0.95)
    out["pass_h1_to_h2"] = ok(H.transfer(tst["h1"], seg["h2"], elig("h1", "h2"), hashes, rng, S[:, M["h2"]], draws=DRAWS))
    out["pass_h2_to_h1"] = ok(H.transfer(tst["h2"], seg["h1"], elig("h2", "h1"), hashes, rng, S[:, M["h1"]], draws=DRAWS))
    out["pass_walk_forward"] = ok(H.transfer(tst["t12"], seg["t3"], elig("t12", "t3"), hashes, rng, S[:, M["t3"]], draws=DRAWS))
    return out, both, cand, tst


def run(chart_tf, res_dir, n_worlds=300, seed=2026):
    d, settings = H.load(os.path.join(res_dir, "sweeps"), chart_tf)
    g = d["gross"].astype(np.float64)
    fu = d["feeu"].astype(np.float64)
    fd = d["fund"].astype(np.float64)
    cnt = d["cnt"]
    hashes = d["h"]
    inv = np.array([bool(s["inverted"]) for s in settings])
    nm = g.shape[1]
    rng = np.random.default_rng(seed + chart_tf)
    real, _, _, _ = counts(g - H.BASE_FEE * fu - fd, g - H.STRESS_FEE * fu - fd, cnt, inv, hashes, rng, with_tests=False)
    W = []
    for _ in range(n_worlds):
        idx = rng.integers(0, nm, NS + NU)
        sg = rng.choice(np.array([-1.0, 1.0]), NS + NU)
        gw = g[:, idx] * sg
        net = gw - H.BASE_FEE * fu[:, idx] - fd[:, idx]
        net_s = gw - H.STRESS_FEE * fu[:, idx] - fd[:, idx]
        cw = cnt[:, idx]
        o, both, cand, tst = counts(net, net_s, cw, inv, hashes, rng)
        # the pick (steadiest candidate) and the group test on the "untouched" months
        U, Us, nU = net[:, NS:], net_s[:, NS:], cw[:, NS:].sum(1)
        o["pick_ok"] = False
        o["group_pass"] = False
        if cand.any():
            worst_t = np.minimum(tst["h1"], tst["h2"])
            order = np.nonzero(cand)[0]
            order = order[np.argsort(-worst_t[order], kind="stable")]
            top = H.distinct_top(order, hashes, 25)
            p = top[0]
            o["pick_ok"] = bool(U[p].sum() > 0 and Us[p].sum() > 0 and nU[p] >= 50)
            pool = np.nonzero(both)[0]
            if pool.size >= 400:
                rnd = rng.choice(pool, 400, replace=False)
                rt = U[rnd].sum(1)
                ct = U[top].sum(1)
                null = np.array([rt[rng.choice(400, top.size, replace=False)].mean() for _ in range(DRAWS)])
                basket = U[top].mean(0)
                boot = (basket[rng.integers(0, NU, size=(DRAWS, NU))].sum(1) > 0).mean()
                o["group_pass"] = bool(ct.mean() > 0 and ct.mean() > np.percentile(null, 95) and boot >= 0.95)
        W.append(o)

    def dist(key):
        v = np.array([w[key] for w in W], dtype=float)
        return dict(real=real[key], median=float(np.median(v)), p05=float(np.percentile(v, 5)), p95=float(np.percentile(v, 95)),
                    worlds_at_least=float((v >= real[key]).mean()))
    res = dict(chart_tf=chart_tf, worlds=n_worlds, real=real,
               share_both=dist("share_both"), candidates=dist("candidates"), gap=dist("gap"),
               gap_abs_at_least=float(np.mean([abs(w["gap"]) >= abs(real["gap"]) for w in W])),
               luck_pass=dict(h1_to_h2=float(np.mean([w["pass_h1_to_h2"] for w in W])), h2_to_h1=float(np.mean([w["pass_h2_to_h1"] for w in W])),
                              walk_forward=float(np.mean([w["pass_walk_forward"] for w in W])), group=float(np.mean([w["group_pass"] for w in W])),
                              any=float(np.mean([w["pass_h1_to_h2"] or w["pass_h2_to_h1"] or w["pass_walk_forward"] or w["group_pass"] for w in W])),
                              pick_ok=float(np.mean([w["pick_ok"] for w in W])),
                              usable=float(np.mean([w["pick_ok"] and (w["pass_h1_to_h2"] or w["pass_h2_to_h1"] or w["pass_walk_forward"] or w["group_pass"]) for w in W]))))
    json.dump(res, open(os.path.join(res_dir, f"luck_{chart_tf}m.json"), "w"))
    s, c, gp, lp = res["share_both"], res["candidates"], res["gap"], res["luck_pass"]
    print(f"chart {chart_tf}m, {n_worlds} no-skill worlds")
    print(f"  positive in both halves: real {s['real'] * 100:.1f}%; luck alone {s['median'] * 100:.1f}% (5%..95%: {s['p05'] * 100:.1f}..{s['p95'] * 100:.1f}%); "
          f"{s['worlds_at_least'] * 100:.0f}% of the worlds have at least as many")
    print(f"  candidates: real {c['real']}; luck alone {c['median']:.0f} ({c['p05']:.0f}..{c['p95']:.0f}); {c['worlds_at_least'] * 100:.0f}% of the worlds have at least as many")
    print(f"  with the filter minus inverted: real {gp['real'] * 100:+.1f} points; luck alone {gp['p05'] * 100:+.1f}..{gp['p95'] * 100:+.1f}; "
          f"a gap at least this large either way in {res['gap_abs_at_least'] * 100:.0f}% of the worlds")
    print(f"  luck passes: first->second {lp['h1_to_h2'] * 100:.1f}%, second->first {lp['h2_to_h1'] * 100:.1f}%, walk-forward {lp['walk_forward'] * 100:.1f}%, "
          f"group test on the untouched months {lp['group'] * 100:.1f}%, at least one of the four {lp['any'] * 100:.1f}%")
    print(f"  the steadiest candidate is positive on the untouched months at base and stressed costs with 50+ trades in {lp['pick_ok'] * 100:.0f}% of the worlds; "
          f"that and at least one test: {lp['usable'] * 100:.1f}%", flush=True)


if __name__ == "__main__":
    ctf = int(sys.argv[1])
    rd = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    run(ctf, rd, int(sys.argv[3]) if len(sys.argv) > 3 else 300)
