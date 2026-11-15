"""Compile the prototype engine (first call) and check neutral-flow parity against the pristine engine copy.
usage: python3 -I t1_compile.py <month>"""
import os, sys, time
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.dont_write_bytecode = True
import numpy as np, pandas as pd
import engine, engine_orig, params, sim, sweep, ticks, json

month = sys.argv[1]
feed = ticks.Feed("../data", 12.0, months=[month])
S = sim.Sim(feed, workers=2)
center = json.load(open("../results/center_final.json"))
ref = sweep.base("FlashGold_NativeReference")
cal = dict(ref); cal.update(center["set"])
mk = dict(ref); mk.update({"WeakFlowMarketMinScore": 4.5, "DowngradeNeutralSellMarketToStop": 0})
fgoff = dict(ref); fgoff["UseFlashGoldDirectionFilter"] = 0
micro = sweep.base("FlashGold_Micro1s")
cases = {"reference": ref, "calibrated": cal, "market route open": mk, "FlashGold off": fgoff, "micro1s": micro}

def run_orig(p):
    fg = S._fg(p); vec = params.vector(p)[: len(engine_orig.NAMES)]
    lookback = float(p["SpeedLookbackSeconds"]); outs = []; cn = np.zeros(len(engine_orig.COUNTERS), np.int64)
    z = np.zeros(0, np.int64); f = np.zeros(0, np.float64)
    for c, (a, b) in enumerate(feed.chunks):
        out = np.zeros((20000, engine_orig.NC)); cnt = np.zeros(len(engine_orig.COUNTERS), np.int64)
        n = engine_orig.run_chunk(feed.t[a:b], feed.bid[a:b], feed.ask[a:b], vec, S._idx(c, lookback),
                                  S._cand(c, lookback, float(p["MinSpeedAlertPoints"]), float(p["MaxTrailingMultiplier"])), S.ep[c],
                                  fg.time, fg.end, fg.li, fg.a_at, fg.a_bar, fg.a_price, fg.a_dir, fg.a_atr,
                                  z, z, z, z, f, f, f, z, out, cnt)
        outs.append(out[:n]); cn += cnt
    tr = np.concatenate(outs)
    return tr[np.argsort(tr[:, 0], kind="stable")], cn

t0 = time.time()
for name, p in cases.items():
    t1 = time.time()
    old, cn_old = run_orig(p)
    t2 = time.time()
    df, cnt = S.run(p, with_counters=True)
    t3 = time.time()
    new = df[engine_orig.TRADE_COLS].to_numpy()
    # the old path sorts per chunk then entry_ms; compare after the same ordering
    old_df = pd.DataFrame(old, columns=engine_orig.TRADE_COLS).sort_values("entry_ms").reset_index(drop=True)
    same = np.array_equal(old_df.to_numpy(), new)
    cnt_old = dict(zip(engine_orig.COUNTERS, cn_old.tolist()))
    same_cnt = all(cnt[k] == cnt_old[k] for k in engine_orig.COUNTERS)
    print(f"{name:18s} trades {len(df):5d}  old {t2 - t1:5.1f}s new {t3 - t2:5.1f}s  trades bit-identical: {same}  counters identical: {same_cnt}", flush=True)
print("total", round(time.time() - t0, 1), "s")
