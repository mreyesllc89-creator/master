"""Signal-only mode against a full replay whose state couplings (caps, lockout, speed-exit alert reset) are switched off."""
import os, sys, json, time
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
print({k: ref[k] for k in ("ScenarioIndependentPerformance", "MaxOpenPositions", "MaxPendingOrders", "MaxOpenPositionsPerScenario", "MaxPendingOrdersPerScenario", "UseDefensiveCloseLockout", "UseSpeedProfitExit", "CancelOldPendings")})
def placements(p, fl):
    df0, c0, ex0 = S.run(p, flow=fl, by_chunk=True)
    caps = [int(c[E.C_DECISIONS] + c[E.C_HOLD_ARMED] + 16) for c in ex0["cnt_by_chunk"]]
    df, cnt, ex = S.run(p, flow=fl, log=caps)
    rows = []
    for c, (a, b) in enumerate(feed.chunks):
        li = ex["logs"][c][0]
        m = li[:, E.LI_STAGE] == E.ST_PLACED
        t = feed.t[a] + li[m, E.LI_TOFF].astype(np.int64)
        rows.append(pd.DataFrame(dict(t=t, action=li[m, E.LI_ACTION], scn=li[m, E.LI_SCN], lab=li[m, E.LI_FLLAB])))
    return pd.concat(rows).sort_values(["t", "action"]).reset_index(drop=True), cnt, df
for name, base in (("reference + toy flow", ref), ("calibrated + toy flow", cal)):
    free = dict(base); free.update({"MaxOpenPositions": 0, "MaxPendingOrders": 0, "MaxOpenPositionsPerScenario": 0, "MaxPendingOrdersPerScenario": 0,
                                    "UseDefensiveCloseLockout": 0, "UseSpeedProfitExit": 0})
    sig = dict(free); sig["X_SignalOnly"] = 1
    t0 = time.time(); S.run(free, flow=flow); t_full = time.time() - t0
    t0 = time.time(); S.run(sig, flow=flow); t_sig = time.time() - t0
    pf, cf, dff = placements(free, flow)
    ps, cs, dfs = placements(sig, flow)
    same = pf.equals(ps)
    capped, cc, _ = placements(base, flow)
    print(f"[{name}] full replay (no caps / lockout / speed exit): {len(pf)} placements; signal-only: {len(ps)} placements; identical (time, action, scenario, flow label): {same};"
          f" replay {t_full:.2f}s vs signal-only {t_sig:.2f}s")
    print(f"      the same preset with its real caps, lockout and speed exit places {len(capped)} (cap_skip {cc['cap_skip']}, lockout_skip {cc['lockout_skip']}, "
          f"alert resets by speed exits change the rest); signal-only trades list: {len(dfs)} rows, reasons {dfs.reason.map(E.REASON).value_counts().to_dict()}")
