"""Differential test: the fast engine (amvi_engine.py) against the independent reference
implementations in tools/ref/ (written separately from the Pine source).

usage: python difftest.py signals|orders|both [n_settings] [seed] [start] [end]

signals  trigger / vol-collapse / zone arrays per chart bar, element by element
orders   trade lists (entry and exit time, side, prices, R) for the same signal arrays
"""
import os
import sys
import time

import numpy as np

import amvi_engine as E
import bars
import space

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref"))

DUMP = os.environ.get("DIFF_DUMP")   # folder for the inputs of mismatching cases
WHY = {E.X_STOP: "stop", E.X_TP: "tp", E.X_TRAIL: "trail", E.X_REV: "reverse", E.X_VOL: "vol", E.X_TIME: "time", E.X_END: "end"}


def m1_dict(m1):
    return dict(t=m1.t, o=m1.o, h=m1.h, l=m1.l, c=m1.c)


def short_settings(rng, chart_tf, n):
    """Random settings whose indicators can warm up inside a short slice: the long periods
    are replaced by shorter grid values on the higher timeframes."""
    out = []
    while len(out) < n:
        p = space.draw(rng, chart_tf)
        if max(p["tfs"]) >= 240:
            p["slow"], p["norm"] = 50, 100
        # the reference versions implement "Permission lasts" = Until next signal and
        # "Check price on" = Tick only (the two other modes are covered by the reviewers' tests)
        p["perm_candles"], p["check_open"] = 0, False
        out.append(p)
    return out


def test_signals(ft, m1, chart_tfs, n, seed):
    import ref_signals
    rng = np.random.default_rng(seed)
    md = m1_dict(m1)
    total = bad = 0
    for ctf in chart_tfs:
        for k, p in enumerate(short_settings(rng, ctf, n)):
            ep = E.P(**space.engine_params(p))
            trig, volc, _ = E.trigger_arrays(ft, ctf, ep)
            zone = E.zone_array(ft, ctf, ep)
            t0 = time.time()
            ref = ref_signals.reference_signals(md, ctf, ep)
            dt = time.time() - t0
            total += 1
            msgs = []
            ch_t = ft.mk.tf(ctf).t
            if ref["chart_t"].size != ch_t.size or not np.array_equal(ref["chart_t"], ch_t):
                msgs.append(f"chart bars differ: {ref['chart_t'].size} vs {ch_t.size}")
            else:
                for name, mine, theirs in (("trig", trig, ref["trig"]), ("volc", volc, ref["volc"]), ("zone", zone, ref["zone"])):
                    d = np.nonzero(np.asarray(mine) != np.asarray(theirs))[0]
                    if d.size:
                        i = int(d[0])
                        msgs.append(f"{name}: {d.size} of {ch_t.size} bars differ, first at bar {i} t={ch_t[i]} mine={mine[i]} ref={theirs[i]}")
            tag = f"chart {ctf}m #{k} tfs={ep['tfs']} f_tf={ep['f_tf']} parent={ep['parent_tf']} zones={ep['zones']} minal={ep['min_aligned']} burst={ep['use_burst']} lv={ep['lv_mode']} band={ep['band']} against={ep['against']} drift={ep['use_drift']} usez={ep['use_zones']}"
            if msgs:
                bad += 1
                print("MISMATCH", tag, f"({dt:.1f}s)")
                for m in msgs:
                    print("    ", m)
            else:
                print("ok      ", tag, f"trig={int(trig.sum())} zone+={int((zone == 1).sum())} zone-={int((zone == -1).sum())} ({dt:.1f}s)")
    print(f"signals: {total - bad} of {total} settings identical")
    return bad


def test_orders(ft, m1, chart_tfs, n, seed):
    import ref_orders
    rng = np.random.default_rng(seed + 1000)
    md = m1_dict(m1)
    total = bad = 0
    for ctf in chart_tfs:
        ch = ft.mk.tf(ctf)
        for k, p in enumerate(short_settings(rng, ctf, n)):
            ep = E.P(**space.engine_params(p))
            trig, volc, _ = E.trigger_arrays(ft, ctf, ep)
            zone = E.zone_array(ft, ctf, ep)
            if k % 3 == 2:   # stress the order logic with dense random signals
                trig = rng.random(len(ch)) < 0.08
                zone = rng.choice(np.array([-1, 0, 1], np.int8), size=len(ch))
                volc = rng.random(len(ch)) < 0.02
            fee = float(rng.choice([0.0, 0.0004, 0.0006]))
            slip = int(rng.choice([0, 1, 3]))
            mine = E.run(ft, ctf, ep, fee=fee, slip_ticks=slip, signals=(trig, volc, zone))
            t0 = time.time()
            ref = ref_orders.reference_trades(md, ctf, np.asarray(trig), np.asarray(zone), np.asarray(volc), ep, fee, slip)
            dt = time.time() - t0
            total += 1
            msgs = []
            n_m, n_r = mine["r"].size, len(ref)
            if n_m != n_r:
                msgs.append(f"trade count {n_m} vs ref {n_r}")
            for i in range(min(n_m, n_r)):
                r = ref[i]
                a = (int(mine["entry_t"][i]), int(mine["exit_t"][i]), int(mine["dir"][i]))
                b = (int(r["entry_t"]), int(r["exit_t"]), int(r["dir"]))
                px = (abs(mine["entry_px"][i] - r["entry_px"]) > 1e-6 or abs(mine["exit_px"][i] - r["exit_px"]) > 1e-6
                      or abs(mine["r"][i] - r["r"]) > 1e-6 or WHY[int(mine["why"][i])] != r["why"])
                if WHY[int(mine["why"][i])] == "end" and r["why"] == "end" and a[0] == b[0] and a[2] == b[2] and not (
                        abs(mine["entry_px"][i] - r["entry_px"]) > 1e-6 or abs(mine["exit_px"][i] - r["exit_px"]) > 1e-6 or abs(mine["r"][i] - r["r"]) > 1e-6):
                    continue   # the mark of a still-open position: its time stamp is a labelling choice
                if a != b or px:
                    msgs.append(f"trade {i}: mine {a} e={mine['entry_px'][i]:.2f} x={mine['exit_px'][i]:.2f} r={mine['r'][i]:.4f} {WHY[int(mine['why'][i])]} | "
                                f"ref {b} e={r['entry_px']:.2f} x={r['exit_px']:.2f} r={r['r']:.4f} {r['why']}")
                    break
            tag = (f"chart {ctf}m #{k} sl={ep['sl']} tp={ep['tp']} trail={ep['trail']}({ep['trail_act']},{ep['trail_off']}) vol={ep['vol_exit']} "
                   f"maxbars={ep['max_bars']} wait={ep['wait']} inv={ep['inverted']} fee={fee} slip={slip}")
            if msgs:
                bad += 1
                print("MISMATCH", tag, f"({dt:.1f}s)")
                for m in msgs:
                    print("    ", m)
                if DUMP:
                    import pickle
                    os.makedirs(DUMP, exist_ok=True)
                    pickle.dump(dict(ctf=ctf, p=ep, trig=np.asarray(trig), zone=np.asarray(zone), volc=np.asarray(volc), fee=fee, slip=slip),
                                open(os.path.join(DUMP, f"orders_{ctf}m_{k}.pkl"), "wb"))
            else:
                print("ok      ", tag, f"trades={n_m} ({dt:.1f}s)")
    print(f"orders: {total - bad} of {total} settings identical")
    return bad


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    start = sys.argv[4] if len(sys.argv) > 4 else "2025-02-01"
    end = sys.argv[5] if len(sys.argv) > 5 else "2025-05-01"
    m1 = bars.load_1m(start=start, end=end)
    ft = E.Features(bars.Market(m1))
    tfs = (1, 3, 5, 15, 60, 240)
    bad = 0
    if what in ("signals", "both"):
        bad += test_signals(ft, m1, tfs, n, seed)
    if what in ("orders", "both"):
        bad += test_orders(ft, m1, tfs, n, seed)
    sys.exit(1 if bad else 0)
