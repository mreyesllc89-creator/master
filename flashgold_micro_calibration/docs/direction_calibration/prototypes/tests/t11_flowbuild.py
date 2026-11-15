import os, sys, time
W = os.environ["PROTO_TOOLS"]
os.chdir(W); sys.path.insert(0, W); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.dont_write_bytecode = True
import numpy as np
import ticks, flowproto
tot_t = tot_u = tot_b = tot_n = 0
for m in ["2026-03", "2026-11"]:
    feed = ticks.Feed("../data", 12.0, months=[m])
    for period in (1000, 250):
        fl = flowproto.FlowSeries(feed, period_ms=period, seed=1)
        t0 = time.perf_counter()
        for c in range(len(feed.chunks)):
            ix, t, ok, v = fl.chunk(c)
            tot_u += len(t); tot_b += ix.nbytes + t.nbytes + ok.nbytes + v.nbytes
        dt = time.perf_counter() - t0
        n = len(feed.t)
        print(f"{m} period {period:4d} ms: {n:,} ticks, {sum(len(fl.chunk(c)[1]) for c in range(len(feed.chunks))):,} updates, build {dt:.2f}s ({dt / n * 1e9:.0f} ns/tick), "
              f"{sum(sum(a.nbytes for a in fl.chunk(c)) for c in range(len(feed.chunks))) / 1e6:.0f} MB = {sum(sum(a.nbytes for a in fl.chunk(c)) for c in range(len(feed.chunks))) / n:.1f} B/tick")
