"""Staged calibration of the FlashGold v5 + FDF strategy on BTC/USD, per chart timeframe."""
import sys, time, itertools, json
import numpy as np
import pandas as pd
import fgengine as E
import fgrun as R

TFS = [1, 5, 15, 30, 60, 120, 240, 480, 1440]
IS_END = pd.Timestamp("2025-07-01", tz="UTC")
HORIZON = 100
OUT = "results"


def zones_for(tf, kind):
    mult = {0: (1, 2, 4), 1: (1, 2, 4, 8), 2: (2, 4, 8), 3: (1, 2)}[kind]
    z = [(True, tf * m) for m in mult]
    while len(z) < 6:
        z.append((False, tf))
    return tuple(z)


def fwd_stats(ctx, S, tf, x_atr=1.0):
    """Per-signal labels and forward moves (in ATR) for buys (+1) and sells (-1)."""
    ch = ctx["ch"]
    h, l, c, atr = ch["h"], ch["l"], ch["c"], ctx["atr14"]
    lab_b1 = E.label_signals(h, l, c, atr, ctx["buy"], 1, 1.0, HORIZON)
    lab_s1 = E.label_signals(h, l, c, atr, ctx["sell"], -1, 1.0, HORIZON)
    lab_b2 = E.label_signals(h, l, c, atr, ctx["buy"], 1, 2.0, HORIZON)
    lab_s2 = E.label_signals(h, l, c, atr, ctx["sell"], -1, 2.0, HORIZON)
    N = len(c)
    f20 = np.full(N, np.nan)
    f20[:-20] = (c[20:] - c[:-20]) / atr[:-20]
    return lab_b1, lab_s1, lab_b2, lab_s2, f20


def summarize(ctx, S, tf, split_ts):
    ch = ctx["ch"]
    t = ch["t_open"]
    is_mask = t < split_ts
    lab_b1, lab_s1, lab_b2, lab_s2, f20 = fwd_stats(ctx, S, tf)
    out = {}
    for name, m in (("is", is_mask), ("oos", ~is_mask)):
        b = ctx["buy"] & m
        s = ctx["sell"] & m
        n = b.sum() + s.sum()
        dec1 = np.concatenate((lab_b1[b], lab_s1[s]))
        dec2 = np.concatenate((lab_b2[b], lab_s2[s]))
        d1 = dec1[dec1 >= 0]
        d2 = dec2[dec2 >= 0]
        fwd = np.concatenate((f20[b], -f20[s]))
        fwd = fwd[~np.isnan(fwd)]
        out[name + "_n"] = int(n)
        out[name + "_p1"] = float(d1.mean()) if len(d1) else np.nan
        out[name + "_p2"] = float(d2.mean()) if len(d2) else np.nan
        out[name + "_f20"] = float(fwd.mean()) if len(fwd) else np.nan
        out[name + "_f20_t"] = float(fwd.mean() / (fwd.std() / np.sqrt(len(fwd)))) if len(fwd) > 2 else np.nan
    return out


def stage_a(tf, S):
    """Signal grid without the framework: parent multiple x zone set x aligned x burst x drift."""
    rows = []
    split = int(IS_END.timestamp())
    grid = list(itertools.product((1, 2, 4, 8), (0, 1, 2, 3), (1, 2, 3), (0.3, 0.5, 0.75, 1.0, 1.5), ((False, 60), (True, 20), (True, 60))))
    t0 = time.time()
    for i, (pm, zk, ma, burst, (ud, db)) in enumerate(grid):
        p = R.params(parent_tf=tf * pm, zones=zones_for(tf, zk), min_aligned=ma, burst_atr=burst,
                     use_drift=ud, drift_bars=db, fd_on=False)
        ctx = R.context(S, tf, p)
        r = dict(tf=tf, pm=pm, zk=zk, ma=ma, burst=burst, drift=db if ud else 0)
        r.update(summarize(ctx, S, tf, split))
        rows.append(r)
        if i % 100 == 0:
            print(f"[A tf={tf}] {i}/{len(grid)} {time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(f"{OUT}/A_{tf}.parquet")
    return df


if __name__ == "__main__":
    stage = sys.argv[1]
    tf = int(sys.argv[2])
    base = pd.read_parquet("btc_1m.parquet")
    S = R.Source(base, 1)
    if stage == "A":
        stage_a(tf, S)
