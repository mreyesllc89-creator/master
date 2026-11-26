"""The picks themselves against the two independent reference versions (tools/ref).

usage: python replicate_picks.py [results_dir] [start] [end]

difftest.py compares random settings; this compares the settings that were actually picked,
over one long slice (default 2025-08-01 to 2026-05-01): the signal arrays bar for bar, and the
trades of the 1-minute walk trade for trade. A pick that uses "Level at candle open" with a
filter above the chart, or the Candles permission, is skipped: the reference versions do not
implement those two modes (they were checked by a separate literal copy of the filter).
"""
import json
import os
import sys

import numpy as np

import amvi_engine as E
import bars
import difftest
import make_pine
import space

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref"))


def run(res_dir, start="2025-08-01", end="2026-05-01"):
    import ref_orders
    import ref_signals
    m1 = bars.load_1m(start=start, end=end)
    ft = E.Features(bars.Market(m1))
    md = difftest.m1_dict(m1)
    bad = done = 0
    for tf in space.CHART_TFS:
        pp = os.path.join(res_dir, f"plateau_{tf}m.json")
        if not os.path.exists(pp):
            continue
        picks = json.load(open(pp))["picks"]
        if not picks:
            continue
        p = space.normalize(picks[0]["setting"])
        name = make_pine.TF_NAME[tf]
        if p["perm_candles"] > 0 or (p["check_open"] and p["f_tf"] > tf):
            print(f"{name}: skipped (uses a filter mode the reference versions do not implement)")
            continue
        ep = E.P(**space.engine_params(p))
        trig, volc, _ = E.trigger_arrays(ft, tf, ep)
        zone = E.zone_array(ft, tf, ep)
        ref = ref_signals.reference_signals(md, tf, ep)
        ch = ft.mk.tf(tf)
        msgs = []
        if ref["chart_t"].size != ch.t.size or not np.array_equal(ref["chart_t"], ch.t):
            msgs.append("chart bars differ")
        else:
            for nm, mine, theirs in (("trigger", trig, ref["trig"]), ("vol collapse", volc, ref["volc"]), ("zone", zone, ref["zone"])):
                d = int((np.asarray(mine) != np.asarray(theirs)).sum())
                if d:
                    msgs.append(f"{nm}: {d} of {ch.t.size} bars differ")
        mine = E.run(ft, tf, ep, fee=0.0005, slip_ticks=1, signals=(trig, volc, zone), walk="1m")
        rt = ref_orders.reference_trades(md, tf, np.asarray(trig), np.asarray(zone), np.asarray(volc), ep, 0.0005, 1)
        if mine["r"].size != len(rt):
            msgs.append(f"trade count {mine['r'].size} against {len(rt)}")
        for i in range(min(mine["r"].size, len(rt))):
            r = rt[i]
            same = (int(mine["entry_t"][i]) == int(r["entry_t"]) and int(mine["dir"][i]) == int(r["dir"])
                    and abs(mine["entry_px"][i] - r["entry_px"]) < 1e-6 and abs(mine["exit_px"][i] - r["exit_px"]) < 1e-6
                    and abs(mine["r"][i] - r["r"]) < 1e-6)
            if not same:
                msgs.append(f"trade {i} differs")
                break
        done += 1
        if msgs:
            bad += 1
            print(f"{name}: MISMATCH - " + "; ".join(msgs))
        else:
            print(f"{name}: identical ({ch.t.size:,} chart bars, {int(np.asarray(trig).sum())} triggers, {mine['r'].size} trades, {mine['r'].sum():+.2f}R)")
    print(f"picks against the reference versions, {start} to {end}: {done - bad} of {done} identical")
    return 1 if bad else 0


if __name__ == "__main__":
    rd = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    sys.exit(run(rd, *(sys.argv[2:4])))
