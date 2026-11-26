"""How fine must the price path be? The pick of every timeframe, and the same pick with a
tight trailing stop (activation 0.5 x ATR, offset 0.5 x ATR: the hardest case), with the
orders walked on the chart's candles, on 1-minute bars, on 15-second, 5-second and 1-second
bars. If the 5-second and 1-second results agree, a finer path would not change them.

usage: python convergence.py [results_dir]      (after report.py; reads final_<tf>m.json)
Search window, net of 0.05 % per side, 1 tick and funding. Writes results/convergence.json.
"""
import json
import os
import sys

import numpy as np
from numba import njit

import amvi_engine as E
import bars
import final_eval as F
import make_pine
import space
import sweep


@njit(cache=True)
def _buckets(mt, mo, mh, ml, mc, s0, s1, sec, so, sh, sl, sc, mult, k):
    """Every minute as bars of k seconds (a minute without seconds stays one bar)."""
    n = mt.size
    cap = 0
    for j in range(n):
        cap += max(1, min(s1[j] - s0[j], 60 // k))
    T = np.empty(cap, np.int64)
    O = np.empty(cap)
    H = np.empty(cap)
    L = np.empty(cap)
    C = np.empty(cap)
    a = np.empty(n, np.int64)
    b = np.empty(n, np.int64)
    q = 0
    for j in range(n):
        a[j] = q
        if s1[j] > s0[j]:
            cur = -1
            for i in range(s0[j], s1[j]):
                bk = (sec[i] - mt[j] // 1000) // k
                if bk != cur:
                    cur = bk
                    T[q] = (mt[j] // 1000 + bk * k) * 1000
                    O[q] = so[i] / mult
                    H[q] = sh[i] / mult
                    L[q] = sl[i] / mult
                    q += 1
                else:
                    if sh[i] / mult > H[q - 1]:
                        H[q - 1] = sh[i] / mult
                    if sl[i] / mult < L[q - 1]:
                        L[q - 1] = sl[i] / mult
                C[q - 1] = sc[i] / mult
        else:
            T[q], O[q], H[q], L[q], C[q] = mt[j], mo[j], mh[j], ml[j], mc[j]
            q += 1
        b[j] = q
    return T[:q], O[:q], H[:q], L[:q], C[:q], a, b


def run_k(ft, fund, chart_tf, p, k, flat):
    """Net R over the search window with the orders walked on k-second bars."""
    ep = E.P(**space.engine_params(p))
    ch = ft.mk.tf(chart_tf)
    T, O, H, L, C, a, b = flat
    trig, volc, _ = E.trigger_arrays(ft, chart_tf, ep)
    zone = E.zone_array(ft, chart_tf, ep)
    i0 = max(int(np.searchsorted(ch.t, sweep.ms(F.SEARCH[0]), side="left")) - 1, 0)
    out = E.simulate(ch.t, ch.o, ch.c, a[ch.i0], b[ch.i1 - 1], ft.atr(chart_tf, ep["exit_atr"]), T, O, H, L, C, trig, zone, volc,
                     bool(ep["inverted"]), float(ep["sl"]), float(ep["tp"]), bool(ep["trail"]), float(ep["trail_act"]), float(ep["trail_off"]),
                     bool(ep["vol_exit"]), int(ep["max_bars"]), int(ep["wait"]), 0.0, 1.0, E.MINTICK, i0, len(ch), chart_tf * bars.MIN_MS,
                     *E.NO_SECONDS, False)
    tr = dict(zip(("entry_t", "exit_t", "dir", "entry_px", "exit_px", "risk", "r", "why", "sig_bar"), out))
    keep = tr["entry_t"] >= sweep.ms(F.SEARCH[0])
    tr = {key: v[keep] for key, v in tr.items()}
    fu = (tr["entry_px"] + tr["exit_px"]) / tr["risk"]
    fd = fund.paid(tr["entry_t"], tr["exit_t"], tr["dir"].astype(np.float64), tr["entry_px"], tr["risk"])
    return float((tr["r"] - F.BASE_FEE * fu - fd).sum()), int(tr["r"].size)


def total(ft, fund, chart_tf, p, walk):
    tr = F.trades_for(ft, fund, chart_tf, p, *F.SEARCH, fee=F.BASE_FEE, slip=1, walk=walk)
    return float(tr["r"].sum()), int(tr["r"].size)


def run(res_dir):
    ft, fund = sweep.load_context()
    mk = ft.mk
    m1, s = mk.m1, mk.sec
    flats = {k: _buckets(m1.t, m1.o, m1.h, m1.l, m1.c, s.s0, s.s1, s.sec, s.o, s.h, s.l, s.c, s.mult, k) for k in (15, 5)}
    out = []
    for tf in space.CHART_TFS:
        fp = os.path.join(res_dir, f"final_{tf}m.json")
        if not os.path.exists(fp):
            continue
        pick = space.normalize(json.load(open(fp))["setting"])
        tight = dict(pick)
        tight["trail"], tight["trail_act"], tight["trail_off"] = True, 0.5, 0.5
        row = dict(tf=tf, name=make_pine.TF_NAME[tf], pick_uses_trailing=bool(pick["trail"]))
        for tag, p in (("pick", pick), ("tight", tight)):
            r = {}
            r["chart"], _ = total(ft, fund, tf, p, "chart")
            r["1m"], _ = total(ft, fund, tf, p, "1m")
            for k in (15, 5):
                r[f"{k}s"], _ = run_k(ft, fund, tf, p, k, flats[k])
            r["1s"], r["n"] = total(ft, fund, tf, p, "fine")
            row[tag] = r
        out.append(row)
        print(f"{row['name']}: pick chart {row['pick']['chart']:+.1f} / 1m {row['pick']['1m']:+.1f} / 15s {row['pick']['15s']:+.1f} / 5s {row['pick']['5s']:+.1f} / 1s {row['pick']['1s']:+.1f}R"
              f" | with a 0.5/0.5 trailing stop: chart {row['tight']['chart']:+.1f} / 1m {row['tight']['1m']:+.1f} / 15s {row['tight']['15s']:+.1f} / 5s {row['tight']['5s']:+.1f} / 1s {row['tight']['1s']:+.1f}R",
              flush=True)
    json.dump(out, open(os.path.join(res_dir, "convergence.json"), "w"))
    md = ["| Chart | Setting | Chart candles | 1-minute bars | 15-second bars | 5-second bars | 1-second bars |", "|---|---|---|---|---|---|---|"]
    for row in out:
        for tag, label in (("pick", "the pick" + (" (uses the trailing stop)" if row["pick_uses_trailing"] else "")), ("tight", "the pick with a 0.5 / 0.5 trailing stop")):
            r = row[tag]
            md.append(f"| {row['name']} | {label} | {r['chart']:+.1f}R | {r['1m']:+.1f}R | {r['15s']:+.1f}R | {r['5s']:+.1f}R | {r['1s']:+.1f}R |")
    open(os.path.join(res_dir, "convergence.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
