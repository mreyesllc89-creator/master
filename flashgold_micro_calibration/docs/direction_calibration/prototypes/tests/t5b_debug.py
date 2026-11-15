import os, sys, json
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
import engine as E, params, sim, sweep, ticks, flowproto, rescore
feed = ticks.Feed("../data", 12.0, months=["2026-11"])
S = sim.Sim(feed, workers=2)
ref = sweep.base("FlashGold_NativeReference")
flow = flowproto.FlowSeries(feed, period_ms=1000, seed=1)
def run_log(p):
    df0, c0, ex0 = S.run(p, flow=flow, by_chunk=True)
    caps = [int(c[E.C_DECISIONS] + c[E.C_HOLD_ARMED] + 16) for c in ex0["cnt_by_chunk"]]
    df1, c1, ex1 = S.run(p, flow=flow, log=caps)
    return ex1["logs"]
base = run_log(ref)
for name, ch in {"EntryRouterMode 0": {"EntryRouterMode": 0}, "MinFlowImbalance 8, FlowComponentScore 1.5": {"MinFlowImbalance": 8.0, "FlowComponentScore": 1.5}}.items():
    p = dict(ref); p.update(ch)
    eng = run_log(p)
    for c, (a, b) in enumerate(feed.chunks):
        T, B, A = feed.t[a:b], feed.bid[a:b], feed.ask[a:b]
        lb, fb = base[c]; le, fe = eng[c]
        m = lb[:, E.LI_KIND] == 0; lb, fb = lb[m], fb[m]
        m = le[:, E.LI_KIND] == 0; le, fe = le[m], fe[m]
        rs = rescore.rescore_direction(lb, fb, T, B, A, p, flow=flow.chunk(c))
        kb = lb[:, E.LI_TICK].astype(np.int64) * (len(T) + 1) + lb[:, E.LI_ISTART]
        ke = le[:, E.LI_TICK].astype(np.int64) * (len(T) + 1) + le[:, E.LI_ISTART]
        common, ib, ie = np.intersect1d(kb, ke, return_indices=True)
        bad = np.flatnonzero((rs["winner"][ib] != le[ie, E.LI_WIN]) | (rs["action"][ib] != le[ie, E.LI_ACTION]) | ((rs["scn"][ib] != le[ie, E.LI_SCN]) & ~np.isin(le[ie, E.LI_STAGE], [E.ST_SPREAD, E.ST_FLOWBLK, E.ST_MIXED, E.ST_BODYAG])))
        for q in bad[:3]:
            r = le[ie[q]]; f = fe[ie[q]]; rb = lb[ib[q]]; fbb = fb[ib[q]]
            print(name, "chunk", c, "tick", r[E.LI_TICK], "engine: winner", r[E.LI_WIN], "action", r[E.LI_ACTION], "scn", r[E.LI_SCN], "stage", r[E.LI_STAGE],
                  "buy/sell", f[E.LF_BUY], f[E.LF_SELL], "mfe/mae(engine row)", f[E.LF_MFE], f[E.LF_MAE], "| base-row mfe/mae", fbb[E.LF_MFE], fbb[E.LF_MAE],
                  "| rescored winner", rs["winner"][ib[q]], "action", rs["action"][ib[q]], "scn", rs["scn"][ib[q]], "buy/sell", rs["buy"][ib[q]], rs["sell"][ib[q]])
            # exact mfe / mae from the feed
            i0 = rb[E.LI_ISTART]; i1 = rb[E.LI_TICK]; sd = rb[E.LI_SPDIR]
            mid = (B + A) * 0.5
            fv = sd * (mid[i0:i1 + 1] - mid[i0]) / 0.01
            print("   exact mfe/mae from feed:", fv.max(), fv.min(), "float32 of them:", np.float32(fv.max()), np.float32(fv.min()))
