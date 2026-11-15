"""Prototype checks: log on vs off, row counts against the engine counters, trade linkage, flow plumbing.
usage: python3 -I t2_log.py <month>"""
import os, sys, time, json
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else ".")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
import engine, params, sim, sweep, ticks
import flowproto

month = sys.argv[1]
feed = ticks.Feed("../data", 12.0, months=[month])
S = sim.Sim(feed, workers=2)
center = json.load(open("../results/center_final.json"))
ref = sweep.base("FlashGold_NativeReference")
cal = dict(ref); cal.update(center["set"])

STAGE = {engine.ST_MIXED: "skip_mixed", engine.ST_SPREAD: "skip_spread", engine.ST_FLOWBLK: "skip_flow_block",
         engine.ST_BODYAG: "skip_body_against", engine.ST_TRADESIDE: "skip_tradeside", engine.ST_FGBLOCK: "flashgold_block",
         engine.ST_HOLDBAR: "hold_same_bar", engine.ST_HOLDARM: "hold_armed", engine.ST_PRIOR60: "prior60_block",
         engine.ST_BURST: "burst_block", engine.ST_CAP: "cap_skip", engine.ST_CPBLOCK: "continuation_block",
         engine.ST_PLACED: "placed", engine.ST_HOLDFAIL: "hold_fail"}


def check_log(name, p, flow=None):
    t0 = time.time()
    df0, cnt0, ex0 = S.run(p, flow=flow, by_chunk=True)
    t_off = time.time() - t0
    caps = [int(c[engine.C_DECISIONS] + c[engine.C_HOLD_ARMED] + 16) for c in ex0["cnt_by_chunk"]]
    t0 = time.time()
    df1, cnt1, ex1 = S.run(p, flow=flow, log=caps)
    t_on = time.time() - t0
    same_tr = np.array_equal(df0.to_numpy(), df1.to_numpy())
    same_cnt = all(cnt0[k] == cnt1[k] for k in cnt0 if not k.startswith("log_"))
    rows = sum(len(l[0]) for l in ex1["logs"])
    kind0 = sum(int((l[0][:, engine.LI_KIND] == 0).sum()) for l in ex1["logs"])
    kind1 = sum(int((l[0][:, engine.LI_KIND] == 1).sum()) for l in ex1["logs"])
    bytes_ = sum(l[0].nbytes + l[1].nbytes for l in ex1["logs"])
    print(f"[{name}] trades {len(df1)}  log-off {t_off:.2f}s  log-on {t_on:.2f}s  trades identical {same_tr}  counters identical {same_cnt}")
    print(f"   rows {rows:,} = kind0 {kind0:,} (decisions {cnt1['decisions']:,}) + kind1 {kind1:,} (hold_pass {cnt1['hold_pass_rows']:,});"
          f" {bytes_ / 1e6:.0f} MB = {bytes_ / max(rows, 1):.0f} B/row; dropped {cnt1['log_rows_dropped']}")
    assert kind0 == cnt1["decisions"], "kind-0 rows must equal C_DECISIONS"
    stg = pd.Series(np.concatenate([l[0][:, engine.LI_STAGE] for l in ex1["logs"]])).value_counts()
    bad = []
    for code, cname in STAGE.items():
        if int(stg.get(code, 0)) != cnt1[cname]:
            bad.append((cname, int(stg.get(code, 0)), cnt1[cname]))
    print("   stage rows vs counters:", "all equal" if not bad else bad)
    return df1, ex1, cnt1


# 1. neutral flow: shipped reference preset and the calibrated preset
df, ex, cnt = check_log("reference, neutral flow", ref)
# trade linkage: every trade's signal_ms is a kind-0 row with the same action / scenario / flow label
T0 = [feed.t[a] for a, b in feed.chunks]
sig = {}
for c, (li, lf) in enumerate(ex["logs"]):
    k0 = li[li[:, engine.LI_KIND] == 0]
    ms = T0[c] + k0[:, engine.LI_TOFF].astype(np.int64)
    for m, act, scn, fl in zip(ms, k0[:, engine.LI_ACTION], k0[:, engine.LI_SCN], k0[:, engine.LI_FLLAB]):
        sig[int(m)] = (int(act), int(scn), int(fl))
ok = [sig.get(int(r.signal_ms)) == (int(r.action), int(r.scenario), int(r.flow_label)) for r in df.itertuples()]
print(f"   trade -> log linkage by signal_ms: {sum(ok)}/{len(ok)} trades match action/scenario/flow label")
df, ex, cnt = check_log("calibrated, neutral flow", cal)

# 2. a toy flow series
fl = flowproto.FlowSeries(feed, period_ms=1000, seed=1)
dfn, cntn = S.run(ref, with_counters=True)
dff, cntf = S.run(ref, with_counters=True, flow=fl)
off = dict(ref); off["UseOrderFlow"] = 0
dfo, cnto = S.run(off, with_counters=True, flow=fl)
print(f"\ntoy flow on the reference preset: trades neutral {len(dfn)}, flow {len(dff)}; UseOrderFlow=false with the series present "
      f"-> identical to neutral: {np.array_equal(dfn.to_numpy(), dfo.to_numpy())}")
print("  flow labels of trades:", dff.flow_label.value_counts().to_dict(), " scenarios:", dff.scenario.map(engine.SCENARIO).value_counts().to_dict())
print("  exits:", dff.reason.map(engine.REASON).value_counts().head(8).to_dict())
blk = dict(ref); blk["BlockStrongFlowAgainst"] = 1
dfb, cntb = S.run(blk, with_counters=True, flow=fl)
print(f"  BlockStrongFlowAgainst=1: trades {len(dfb)}, skip_flow_block {cntb['skip_flow_block']}")
check_log("reference, toy flow", ref, flow=fl)
