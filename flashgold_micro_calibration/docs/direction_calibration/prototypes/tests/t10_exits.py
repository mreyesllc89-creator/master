import os, sys, json
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
import engine as E, sim, sweep, ticks, flowproto
feed = ticks.Feed("../data", 12.0, months=["2026-11"])
S = sim.Sim(feed, workers=2)
ref = sweep.base("FlashGold_NativeReference")
mk = dict(ref); mk.update({"WeakFlowMarketMinScore": 4.5, "DowngradeNeutralSellMarketToStop": 0})
for name, mom, p in (("flow leans against price (mom -0.05)", -0.05, ref), ("flow follows price (mom +0.05)", 0.05, ref), ("flow leans against price, market route opened", -0.05, mk)):
    fl = flowproto.FlowSeries(feed, period_ms=1000, seed=3, mom=mom)
    df, cnt = S.run(p, with_counters=True, flow=fl)
    print(f"[{name}] trades {len(df)}  labels {df.flow_label.value_counts().to_dict()}")
    print("   exits:", df.reason.map(E.REASON).value_counts().to_dict())
    print("   scenarios:", df.scenario.map(E.SCENARIO).value_counts().to_dict())
    # switch the four flow-dependent exit branches off one at a time
    for nm, ch in (("UseStopFlowDisagreeDangerClose=0", {"UseStopFlowDisagreeDangerClose": 0}), ("FlowDisagreeMakesDefenseImmediate=0", {"FlowDisagreeMakesDefenseImmediate": 0}),
                   ("FOLMFlowDisagreeDangerLossPoints=0", {"FOLMFlowDisagreeDangerLossPoints": 0.0}), ("V40PreSpeedExecutionShieldNeedsPressureOrFlow=0", {"V40PreSpeedExecutionShieldNeedsPressureOrFlow": 0})):
        q = dict(p); q.update(ch)
        d2 = S.run(q, flow=fl)
        same_entries = np.array_equal(df[["entry_ms", "side", "action"]].to_numpy(), d2[["entry_ms", "side", "action"]].to_numpy())
        print(f"   {nm:52s} trades {len(d2)}  net pts {d2.pts.sum():9.0f} (was {df.pts.sum():9.0f})  exits changed: {int((df.reason.to_numpy()[:min(len(df), len(d2))] != d2.reason.to_numpy()[:min(len(df), len(d2))]).sum())}")
