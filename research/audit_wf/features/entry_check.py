"""Entry row, entry minute and weekday that the timing conditions use, against my own computation from the
timestamps: entry = first one-minute bar at or after the trigger bar's close, within one trigger bar.
Usage: [HUMP_SYMBOL=BTCUSD] python3 entry_check.py <run folder> <TF,TF..>"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/workspace/master/research")
import hump_wf as W

work, tfs = sys.argv[1], sys.argv[2].split(",")
m1 = pd.read_pickle(os.path.join(work, "m1.pkl"))


class Light(W.H.Market):
    def __init__(self, m):
        super().__init__(m1=m[["open", "high", "low", "close"]], half_spread=np.zeros(len(m)))
        self.vol = m["vol"]


mk = Light(m1)
ts = m1.index
tmin = ts.values.astype("datetime64[m]").astype(np.int64)      # floor to the minute
for tf in tfs:
    mk.tf(tf)
    d = mk._tf[tf]
    T = d["t"].index.values.astype("datetime64[m]").astype(np.int64)
    m = W.B.TF_MIN[tf]
    close = T + m
    # my entry: first M1 bar whose (exact) time is at or after the close, accepted if it starts within m minutes
    exact = ts.values.astype("datetime64[ns]").astype(np.int64)
    cl_ns = close * 60_000_000_000
    r = np.searchsorted(exact, cl_ns, side="left")
    ok = r < len(ts)
    rr = np.clip(r, 0, len(ts) - 1)
    ok &= (exact[rr] - cl_ns) <= m * 60_000_000_000
    mine = np.where(ok, rr, -1)
    mod = d["row"]
    bad = np.flatnonzero(mine != mod)
    # minute and weekday of the entry bar in server time
    e = mod[mod >= 0]
    te_mod = mk.tod[e]; de_mod = mk.dow[e]
    te_me = (tmin[e] % 1440); de_me = ((tmin[e] // 1440) + 3) % 7
    # the entry bar is never inside the signal bar and never before its close
    after = (exact[e] >= cl_ns[mod >= 0]).all()
    print(f"{W.SYM} {tf}: {len(T)} bars, entry rows differ {len(bad)} (first {[str(pd.Timestamp(T[i] * 60_000_000_000)) for i in bad[:3]]}); "
          f"entry minute differs {int((te_mod != te_me).sum())}, weekday differs {int((de_mod != de_me).sum())}; every entry at/after the signal bar's close: {after}; "
          f"entries later than the next bar's first minute: {int(((exact[e] - cl_ns[mod >= 0]) > 0).sum())}", flush=True)
print("ENTRY_DONE", W.SYM)
