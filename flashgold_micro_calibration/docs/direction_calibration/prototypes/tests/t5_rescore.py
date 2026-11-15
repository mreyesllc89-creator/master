"""Does the logged raw input set re-score the direction verdict exactly?  Engine(theta') vs rescore(log(theta0), theta')."""
import os, sys, time, json
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
import engine as E, params, sim, sweep, ticks, flowproto, rescore

month = sys.argv[1]
feed = ticks.Feed("../data", 12.0, months=[month])
S = sim.Sim(feed, workers=2)
ref = sweep.base("FlashGold_NativeReference")
flow = flowproto.FlowSeries(feed, period_ms=1000, seed=1)


def run_log(p, fl):
    df0, c0, ex0 = S.run(p, flow=fl, by_chunk=True)
    caps = [int(c[E.C_DECISIONS] + c[E.C_HOLD_ARMED] + 16) for c in ex0["cnt_by_chunk"]]
    df1, c1, ex1 = S.run(p, flow=fl, log=caps)
    assert np.array_equal(df0.to_numpy(), df1.to_numpy())
    return df1, c1, ex1["logs"]


def kind0(logs):
    out = []
    for li, lf in logs:
        m = li[:, E.LI_KIND] == 0
        out.append((li[m], lf[m]))
    return out


def compare(logs_base, th, logs_eng, fl, label):
    """Re-score the base log under th and compare with the engine's own rows (same tick, same alert start, same alert direction)."""
    tot = dict(rows=0, shared=0, winner=0, action=0, scn=0, lab=0)
    for c, (a, b) in enumerate(feed.chunks):
        T, B, A = feed.t[a:b], feed.bid[a:b], feed.ask[a:b]
        lb, fb = logs_base[c]
        le, fe = logs_eng[c]
        rs = rescore.rescore_direction(lb, fb, T, B, A, th, flow=fl.chunk(c) if fl is not None else None)
        kb = (lb[:, E.LI_TICK].astype(np.int64) * (len(T) + 1) + lb[:, E.LI_ISTART]) * 3 + (lb[:, E.LI_SPDIR] + 1)
        ke = (le[:, E.LI_TICK].astype(np.int64) * (len(T) + 1) + le[:, E.LI_ISTART]) * 3 + (le[:, E.LI_SPDIR] + 1)
        common, ib, ie = np.intersect1d(kb, ke, return_indices=True)
        tot["rows"] += len(le); tot["shared"] += len(common)
        tot["winner"] += int((rs["winner"][ib] == le[ie, E.LI_WIN]).sum())
        tot["action"] += int((rs["action"][ib] == le[ie, E.LI_ACTION]).sum())
        st = le[ie, E.LI_STAGE]
        has_scn = ~np.isin(st, [E.ST_SPREAD, E.ST_FLOWBLK, E.ST_MIXED, E.ST_BODYAG])
        tot["scn"] += int(((rs["scn"][ib] == le[ie, E.LI_SCN]) | ~has_scn).sum())
        tot["lab"] += int(((rs["fl_lab"][ib] == le[ie, E.LI_FLLAB]) | ~has_scn).sum())
    sh = tot["shared"]
    ok = all(tot[k] == sh for k in ("winner", "action", "scn", "lab"))
    print(f"{label:62s} engine rows {tot['rows']:>9,d} shared {sh:>9,d}  winner/action/scenario/flow-label equal: "
          f"{tot['winner']}/{tot['action']}/{tot['scn']}/{tot['lab']} of {sh}  -> {'EXACT' if ok else 'MISMATCH'}", flush=True)
    return ok


th0 = dict(ref)
df0, c0, logs0 = run_log(ref, flow)
base = kind0(logs0)
print(f"base log: {sum(len(l[0]) for l in base):,} kind-0 rows, trades {len(df0)}")
allok = compare(base, th0, base, flow, "theta0 re-scored against its own log (toy flow)")

variants = {
    "MinCandleBodyPoints 40": {"MinCandleBodyPoints": 40.0},
    "MicroBreakLookbackSeconds 5, MicroBreakBufferPoints 6": {"MicroBreakLookbackSeconds": 5, "MicroBreakBufferPoints": 6.0},
    "MicroBreakLookbackSeconds 60": {"MicroBreakLookbackSeconds": 60},
    "MinDirectionScore 3, MinScoreEdge 1": {"MinDirectionScore": 3.0, "MinScoreEdge": 1.0},
    "MinDirectionScore 5": {"MinDirectionScore": 5.0},
    "MaxSpreadPoints 12": {"MaxSpreadPoints": 12.0},
    "OppositePressureSeconds 3, OppositePressurePoints 35": {"OppositePressureSeconds": 3, "OppositePressurePoints": 35.0},
    "RetestFailPoints 25, MarketFollow21Points 40": {"RetestFailPoints": 25.0, "MarketFollow21Points": 40.0},
    "EntryRouterMode 0": {"EntryRouterMode": 0},
    "EntryRouterMode 1 + market route open": {"EntryRouterMode": 1, "WeakFlowMarketMinScore": 4.5, "DowngradeNeutralSellMarketToStop": 0},
    "MinFlowImbalance 8, FlowComponentScore 1.5": {"MinFlowImbalance": 8.0, "FlowComponentScore": 1.5},
    "MaxFlowAgeMs 800": {"MaxFlowAgeMs": 800},
    "BlockStrongFlowAgainst": {"BlockStrongFlowAgainst": 1},
    "SpeedDirectionScore 2, CandleBodyScore 1, MicroBreakScore 2": {"SpeedDirectionScore": 2.0, "CandleBodyScore": 1.0, "MicroBreakScore": 2.0},
}
for name, ch in variants.items():
    p = dict(ref); p.update(ch)
    df1, c1, logs1 = run_log(p, flow)
    allok &= compare(base, p, kind0(logs1), flow, name)
print("ALL EXACT" if allok else "SOME MISMATCH")
