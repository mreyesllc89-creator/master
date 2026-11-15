"""FlashGold gate verdict re-scored offline from the log (tick, bid) with other gate inputs vs the engine's own log at those inputs."""
import os, sys, json
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
import numpy as np
from numba import njit
import engine as E, sim, sweep, ticks
feed = ticks.Feed("../data", 12.0, months=["2026-11"])
S = sim.Sim(feed, workers=2)
ref = sweep.base("FlashGold_NativeReference")
@njit(cache=False)
def fg_rows(T, B, rows, micro, interval, warm, wm, minutes, bars, band, against, buy, sell, fg_time, fg_end, fg_li, fg_aat, fg_abar, fg_aprice, fg_adir, fg_aatr):
    out = np.zeros(len(rows), np.int64)
    for q in range(len(rows)):
        i = rows[q]
        z, fi, fq = E._fg_z(T[i], B[i], micro, interval, warm, wm, minutes, bars, band, against, buy, sell, fg_time, fg_end, fg_li, fg_aat, fg_abar, fg_aprice, fg_adir, fg_aatr)
        out[q] = z
    return out
def run_log(p):
    df0, c0, ex0 = S.run(p, by_chunk=True)
    caps = [int(c[E.C_DECISIONS] + c[E.C_HOLD_ARMED] + 16) for c in ex0["cnt_by_chunk"]]
    df1, c1, ex1 = S.run(p, log=caps)
    return [(li[li[:, E.LI_KIND] == 0], lf[li[:, E.LI_KIND] == 0]) for li, lf in ex1["logs"]]
base = run_log(ref)
for name, ch in (("theta0", {}), ("FG_InpBandAtr 1.0", {"FG_InpBandAtr": 1.0}), ("FG_InpAgainst 1", {"FG_InpAgainst": 1}), ("FG_InpLast 3 (timed 5 s), FG_InpSeconds 5", {"FG_InpLast": 3, "FG_InpSeconds": 5}),
                 ("FG_InpAllowSell 0", {"FG_InpAllowSell": 0}), ("FG_InpBandAtr 0, FG_InpLast 2, FG_InpBars 2", {"FG_InpBandAtr": 0.0, "FG_InpLast": 2, "FG_InpBars": 2})):
    p = dict(ref); p.update(ch)
    fg = S._fg(p)
    fg_last = int(p["FG_InpLast"]); wm = fg_last if fg_last <= 2 else 0
    eng = run_log(p)
    tot = same = 0
    for c, (a, b) in enumerate(feed.chunks):
        T, B = feed.t[a:b], feed.bid[a:b]
        lb = base[c][0]; le = eng[c][0]
        kb = (lb[:, E.LI_TICK].astype(np.int64) * (len(T) + 1) + lb[:, E.LI_ISTART]) * 3 + (lb[:, E.LI_SPDIR] + 1)
        ke = (le[:, E.LI_TICK].astype(np.int64) * (len(T) + 1) + le[:, E.LI_ISTART]) * 3 + (le[:, E.LI_SPDIR] + 1)
        common, ib, ie = np.intersect1d(kb, ke, return_indices=True)
        rows = lb[ib, E.LI_TICK].astype(np.int64)
        z = fg_rows(T, B, rows, bool(p["FG_Resolution"] > 0.5), int(p["FG_IntervalMs"]), int(p["FG_MicroWarmupBars"]), wm, int(p["FG_InpMinutes"]), int(p["FG_InpBars"]),
                    float(p["FG_InpBandAtr"]), bool(p["FG_InpAgainst"]), bool(p["FG_InpAllowBuy"]), bool(p["FG_InpAllowSell"]), fg.time, fg.end, fg.li, fg.a_at, fg.a_bar, fg.a_price, fg.a_dir, fg.a_atr)
        tot += len(rows); same += int((z == le[ie, E.LI_FGZ]).sum())
    print(f"{name:44s} shared rows {tot:>9,d}: offline gate verdict == engine's {same:>9,d}  -> {'EXACT' if same == tot else 'MISMATCH'}")
