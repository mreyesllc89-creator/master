import os, sys, json, time
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
import numpy as np
import engine as E, sim, sweep, ticks, flowproto
month = sys.argv[1]
feed = ticks.Feed("../data", 12.0, months=[month])
S = sim.Sim(feed, workers=2)
ref = sweep.base("FlashGold_NativeReference")
center = json.load(open("../results/center_final.json"))
cal = dict(ref); cal.update(center["set"])
fl = flowproto.FlowSeries(feed, period_ms=1000, seed=1)
for c in range(len(feed.chunks)):
    fl.chunk(c)
def best(f, n=5):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); f(); ts.append(time.perf_counter() - t0)
    return min(ts)
print(f"{month}: {len(feed.t):,} ticks, {len(feed.chunks)} chunks, 2 threads")
for name, p in (("shipped alert x7.5", ref), ("calibrated alert x30", cal)):
    S.run(p); S.run(p, flow=fl)
    sig = dict(p); sig["X_SignalOnly"] = 1
    S.run(sig, flow=fl)
    df0, c0, ex0 = S.run(p, flow=fl, by_chunk=True)
    caps = [int(c[E.C_DECISIONS] + c[E.C_HOLD_ARMED] + 16) for c in ex0["cnt_by_chunk"]]
    print(f"  {name:22s} neutral {best(lambda: S.run(p)):.3f}s | toy flow {best(lambda: S.run(p, flow=fl)):.3f}s | signal-only {best(lambda: S.run(sig, flow=fl)):.3f}s"
          f" | decision log on {best(lambda: S.run(p, flow=fl, log=caps), 3):.3f}s ({sum(caps):,} rows)")
