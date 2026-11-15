"""Validate the forward-outcome kernel against the engine's own market-order trades in pure-bracket mode, and time it."""
import os, sys, time, json
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
import numpy as np, pandas as pd
import engine, params, sim, sweep, ticks, fwd

month = sys.argv[1]
feed = ticks.Feed("../data", 12.0, months=[month])
S = sim.Sim(feed, workers=2)
ref = sweep.base("FlashGold_NativeReference")
p = dict(ref)
p.update({"WeakFlowMarketMinScore": 4.5, "DowngradeNeutralSellMarketToStop": 0, "InpUseEntryHold": 0,
          "UsePostEntryValidation": 0, "UseSpeedProfitExit": 0, "UseTrailing": 0, "InpUseTrailLayer": 0,
          "InpWaitForBurstSettle": 0, "InpUse1000msHold": 0})
df = S.run(p)
mk = df[df.action.isin([engine.A_BM, engine.A_SM]) & df.reason.isin([engine.R_SL, engine.R_TP])].reset_index(drop=True)
print("engine pure-bracket run:", len(df), "trades,", len(mk), "market trades ended by SL/TP; reasons", df.reason.map(engine.REASON).value_counts().to_dict())
# per chunk kernel call on the market trades' decision ticks
res = []
for c, (a, b) in enumerate(feed.chunks):
    T, B, A = feed.t[a:b], feed.bid[a:b], feed.ask[a:b]
    sub = mk[(mk.decision_ms >= T[0]) & (mk.decision_ms <= T[-1])]
    rows = np.searchsorted(T, sub.decision_ms.to_numpy()).astype(np.int64)
    assert (T[rows] == sub.decision_ms.to_numpy()).all()
    out = fwd.alloc(len(rows))
    fwd.forward_outcomes(T, B, A, rows, 150, 10.0, 1.5, 0.0, True, 10**12, *out)
    br_pts, br_reason = out[3], out[4]
    sidx = np.where(sub.side.to_numpy() > 0, 0, 1)
    q = 5                                            # (80, 160) = MarketSLPoints / MarketTPPoints
    kp = br_pts[np.arange(len(rows)), sidx, q]
    kr = br_reason[np.arange(len(rows)), sidx, q]
    res.append(pd.DataFrame(dict(eng=sub.pts.to_numpy(), ker=kp, eng_r=sub.reason.to_numpy(), ker_r=kr)))
r = pd.concat(res)
r["ker_reason_mapped"] = np.where(r.ker_r == fwd.R_SL, engine.R_SL, np.where(r.ker_r == fwd.R_TP, engine.R_TP, 0))
exact = (np.abs(r.eng - r.ker) < 1e-3) & (r.eng_r == r.ker_reason_mapped)
print(f"kernel vs engine on {len(r)} market trades: identical points and exit reason {int(exact.sum())}/{len(r)}"
      f"  max |diff| {np.nanmax(np.abs(r.eng - r.ker)):.4f}")
if (~exact).any():
    print(r[~exact].head(10))

# timing over every decision row of the reference preset (neutral flow)
df0, cnt0, ex0 = S.run(ref, by_chunk=True)
caps = [int(c[engine.C_DECISIONS] + c[engine.C_HOLD_ARMED] + 16) for c in ex0["cnt_by_chunk"]]
df1, cnt1, ex1 = S.run(ref, log=caps)
tot_rows = 0; t_k = 0.0
for c, (a, b) in enumerate(feed.chunks):
    T, B, A = feed.t[a:b], feed.bid[a:b], feed.ask[a:b]
    li = ex1["logs"][c][0]
    rows = li[li[:, engine.LI_KIND] == 0][:, engine.LI_TICK].astype(np.int64)
    out = fwd.alloc(len(rows))
    t0 = time.perf_counter()
    fwd.forward_outcomes(T, B, A, rows, 150, 10.0, 1.5, 0.0, True, 300000, *out)
    t_k += time.perf_counter() - t0; tot_rows += len(rows)
print(f"forward outcomes, both sides, {fwd.NH} horizons, {fwd.NM} mfe/mae windows, {fwd.NK} brackets, hmax 300 s: "
      f"{tot_rows:,} rows in {t_k:.1f}s single-thread = {t_k / tot_rows * 1e6:.2f} us/row (out arrays {sum(o.nbytes for o in out) / len(rows):.0f} B/row)")
# bracket outcome sanity
print("share of rows by (90,180) buy-side exit reason:", pd.Series(out[4][:, 0, 0]).value_counts(normalize=True).round(3).to_dict())
