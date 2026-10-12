"""Measure every frozen candidate (wf_common.candidates + baselines) on one filter timeframe: per calendar month, per
horizon H, the count table zone (SELL / NO TRADE / BUY) x label (down / up), split into candles whose label ends in the
same month and candles whose label ends in a later month (needed to purge the training window at a fold boundary).
Usage: python wf_grid.py <tf> <clock utc|server> <read closed_prev|closed_at_close> <run real|dry> [subset all|baselines]
dry = evaluation months 2018-07 .. 2019-12 only (code check; never used for a choice)."""
import sys, os, time, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wf_common as W

tf = int(sys.argv[1]); clock = sys.argv[2]; read = sys.argv[3]; run = sys.argv[4]
subset = sys.argv[5] if len(sys.argv) > 5 else "all"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
if run == "dry":
    m0 = 2018 * 12 + 6; m1 = 2019 * 12 + 11
else:
    m0 = 2020 * 12 + 0; m1 = 2026 * 12 + 9
nM = m1 - m0 + 1

S = W.load(clock)
ch = S.bars(tf)
last_ts = int(S.base.index[-1].timestamp()) + 60
N = int(np.searchsorted(ch["t_close"], last_ts, side="right"))   # complete candles only
t = ch["t_open"][:N]; c = ch["c"][:N]
mon = W.month_id(t)
cands = (W.candidates(tf) if subset == "all" else []) + W.baselines(tf)

# labels per H (independent of the candidate)
LAB = {}
ties = np.zeros((len(W.HS), nM), np.int64)
for j, H in enumerate(W.HS):
    fwd = np.full(N, np.nan); fwd[:-H] = c[H:] - c[:-H]
    mH = np.full(N, -1); mH[:-H] = mon[H:]
    ok = ~np.isnan(fwd) & (mon >= m0) & (mon <= m1)
    tie = ok & (fwd == 0)
    ties[j] = np.bincount(mon[tie] - m0, minlength=nM)
    ok &= fwd != 0
    cross = (mH != mon).astype(np.int64)
    LAB[H] = (ok, (fwd > 0).astype(np.int64), cross)

cnt = np.zeros((len(cands), len(W.HS), nM, 2, 3, 2), np.int32)
nsig = np.zeros(len(cands), np.int64)
t0 = time.time()
for i, r in enumerate(cands):
    z, g, ctx = W.zone_of(S, tf, r, read)
    z = z[:N].astype(np.int64)
    sig = (ctx["buy"] | ctx["sell"])[:N]
    nsig[i] = int((sig & (mon >= m0) & (mon <= m1)).sum())
    for j, H in enumerate(W.HS):
        ok, y, cross = LAB[H]
        key = ((((mon[ok] - m0) * 2 + cross[ok]) * 3 + (z[ok] + 1)) * 2 + y[ok])
        cnt[i, j] = np.bincount(key, minlength=nM * 12).reshape(nM, 2, 3, 2)
    if i % 100 == 0:
        print(f"[{tf} {clock} {read} {run}] {i}/{len(cands)} {time.time()-t0:.0f}s", flush=True)

tag = f"{tf}_{clock}_{read}_{run}_{subset}"
np.savez_compressed(f"{OUT}/cnt_{tag}.npz", cnt=cnt, ties=ties, m0=m0, m1=m1, hs=np.array(W.HS))
tab = pd.DataFrame([dict(cid=i, kind=r["kind"], parent=r["parent"], zones="/".join(map(str, r["zones"])), ma=r["ma"],
                         use_zones=r["use_zones"], label=W.label(r), n_signals=int(nsig[i])) for i, r in enumerate(cands)])
tab.to_csv(f"{OUT}/cands_{tag}.csv", index=False)
print("done", tag, len(cands), f"{time.time()-t0:.0f}s")
