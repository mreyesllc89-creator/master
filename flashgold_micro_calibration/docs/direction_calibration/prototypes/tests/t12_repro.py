import os, sys, hashlib
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
import numpy as np
import engine as E, sim, sweep, ticks, flowproto
feed = ticks.Feed("../data", 12.0, months=["2026-11"])
ref = sweep.base("FlashGold_NativeReference")
def digest(workers, seed):
    S = sim.Sim(feed, workers=workers)
    fl = flowproto.FlowSeries(feed, period_ms=1000, seed=seed)
    df0, c0, ex0 = S.run(ref, flow=fl, by_chunk=True)
    caps = [int(c[E.C_DECISIONS] + c[E.C_HOLD_ARMED] + 16) for c in ex0["cnt_by_chunk"]]
    df, cnt, ex = S.run(ref, flow=fl, log=caps)
    h = hashlib.sha256()
    h.update(df.to_numpy().tobytes())
    for li, lf in ex["logs"]:
        h.update(li.tobytes()); h.update(lf.tobytes())
    hf = hashlib.sha256()
    for c in range(len(feed.chunks)):
        for a in fl.chunk(c):
            hf.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()[:16], hf.hexdigest()[:16]
for workers, seed in ((1, 1), (3, 1), (2, 1), (2, 2)):
    print(f"workers {workers} seed {seed}: trades+log sha256 {digest(workers, seed)[0]}  flow series sha256 {digest(workers, seed)[1]}")
