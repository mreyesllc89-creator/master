"""Does a never-resolving engine run (MinDirectionScore 99, router 0, i.e. only time expiry ends an alert) cover the evaluations of other input sets?"""
import os, sys, json
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
import engine as E, params, sim, sweep, ticks, flowproto
month = sys.argv[1]
feed = ticks.Feed("../data", 12.0, months=[month])
S = sim.Sim(feed, workers=2)
ref = sweep.base("FlashGold_NativeReference")
center = json.load(open("../results/center_final.json"))
cal = dict(ref); cal.update(center["set"])
flow = flowproto.FlowSeries(feed, period_ms=1000, seed=1)
def run_log(p, fl=flow):
    df0, c0, ex0 = S.run(p, flow=fl, by_chunk=True)
    caps = [int(c[E.C_DECISIONS] + c[E.C_HOLD_ARMED] + 16) for c in ex0["cnt_by_chunk"]]
    df1, c1, ex1 = S.run(p, flow=fl, log=caps)
    return df1, c1, [(li[li[:, E.LI_KIND] == 0], lf[li[:, E.LI_KIND] == 0]) for li, lf in ex1["logs"]]
def keys(logs, c, n, with_ep):
    li = logs[c][0]
    k = li[:, E.LI_TICK].astype(np.int64)
    if with_ep:
        k = (k * (n + 1) + li[:, E.LI_ISTART]) * 3 + (li[:, E.LI_SPDIR] + 1)
    return k
for alert_name, base_p in (("shipped alert x7.5", ref), ("calibrated alert x30", cal)):
    sh = dict(base_p); sh.update({"MinDirectionScore": 99.0, "EntryRouterMode": 0})
    _, csh, shadow = run_log(sh)
    nrows = sum(len(l[0]) for l in shadow)
    print(f"\n[{alert_name}] shadow log (never resolves): {nrows:,} rows; engine decisions of the base set below")
    variants = {"base theta0": {}, "MinDirectionScore 3, MinScoreEdge 1": {"MinDirectionScore": 3.0, "MinScoreEdge": 1.0}, "MinDirectionScore 5": {"MinDirectionScore": 5.0},
                "MaxSpreadPoints 12": {"MaxSpreadPoints": 12.0}, "MinFlowImbalance 8, FlowComponentScore 1.5": {"MinFlowImbalance": 8.0, "FlowComponentScore": 1.5},
                "EntryRouterMode 1": {"EntryRouterMode": 1}, "InpUseEntryHold 0": {"InpUseEntryHold": 0}, "FG filter off": {"UseFlashGoldDirectionFilter": 0}}
    for name, ch in variants.items():
        p = dict(base_p); p.update(ch)
        df1, c1, eng = run_log(p)
        tot = cov_t = cov_e = 0
        for c, (a, b) in enumerate(feed.chunks):
            n = b - a
            kt_e = keys(eng, c, n, False); kt_s = np.unique(keys(shadow, c, n, False))
            ke_e = keys(eng, c, n, True); ke_s = np.unique(keys(shadow, c, n, True))
            tot += len(kt_e); cov_t += int(np.isin(kt_e, kt_s).sum()); cov_e += int(np.isin(ke_e, ke_s).sum())
        print(f"   {name:46s} engine rows {tot:>9,d}  tick covered {100 * cov_t / tot:6.2f}%   (tick, alert start, direction) covered {100 * cov_e / tot:6.2f}%")
