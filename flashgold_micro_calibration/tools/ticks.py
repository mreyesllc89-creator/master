"""Tick store: Dukascopy mid path + a broker-like spread, on a 2-digit price grid.

The EA is written for a 2-digit XAUUSD symbol (the author's chart is XAUUSD-ECN, digits=2, and the
2026 Octa export in this repository is on the 0.01 grid with an 11-13 point spread). Dukascopy quotes
3 digits with a top-of-book spread of about 55 points, which the EA's own spread caps (31 / 25
points) would reject outright. So the replay keeps the Dukascopy *mid* path and tick times and
rebuilds bid/ask around it:

  spread_pts = max(1, round(dukascopy_spread_pts * scale))      scale = target_median / 54.6
  bid = round(mid - spread/2, 2)     ask = bid + spread

`scale` keeps the relative widening of the real spread around news and thin hours. Consecutive
ticks whose rebuilt bid and ask are both unchanged are dropped (a 2-digit feed would not emit them).

One point = 0.01 everywhere, as in the EA.
"""
import glob
import os

import numpy as np

POINT = 0.01
DUKA_MEDIAN_SPREAD_PTS = 54.6      # median of the raw feed, Oct-Nov 2026 (points of 0.01)


def load_raw(data_dir, symbol="XAUUSD", months=None):
    """Concatenate monthly npz files -> t (ms), bid, ask as float64 prices (3 digits)."""
    files = sorted(glob.glob(os.path.join(data_dir, "ticks", f"{symbol}_*.npz")))
    if months is not None:
        files = [f for f in files if os.path.basename(f)[len(symbol) + 1:-4] in months]
    ts, bs, as_ = [], [], []
    for f in files:
        z = np.load(f)
        ts.append(z["t"]); bs.append(z["bid"]); as_.append(z["ask"])
    if not ts:
        raise FileNotFoundError(f"no tick files in {data_dir}/ticks")
    t = np.concatenate(ts)
    bid = np.concatenate(bs).astype(np.float64) / 1000.0
    ask = np.concatenate(as_).astype(np.float64) / 1000.0
    order = np.argsort(t, kind="stable")
    return t[order], bid[order], ask[order]


def broker_feed(t, bid, ask, target_spread_pts=12.0, fixed=False, extra_pts=0.0):
    """Rebuild a 2-digit bid/ask around the Dukascopy mid. Returns t, bid, ask (float64, 0.01 grid)."""
    mid = (bid + ask) * 0.5
    raw_pts = (ask - bid) / POINT
    if fixed:
        sp = np.full(len(t), max(1.0, round(target_spread_pts)))
    else:
        sp = np.maximum(1.0, np.round(raw_pts * (target_spread_pts / DUKA_MEDIAN_SPREAD_PTS)))
    sp = sp + extra_pts
    b = np.round((mid - sp * POINT * 0.5) / POINT)          # integer points
    a = b + sp
    keep = np.ones(len(t), dtype=np.bool_)
    keep[1:] = (b[1:] != b[:-1]) | (a[1:] != a[:-1])
    return t[keep], b[keep] * POINT, a[keep] * POINT


def chunks(t, gap_ms=6 * 3600 * 1000):
    """Split at long quote gaps (weekends) -> list of (start, stop) index pairs.

    Each chunk is replayed independently, like an EA restarted for the week: indicators that need
    history (60 s tape, 60 minute drift) are simply unavailable at the start, as in MT5 on Monday."""
    cut = np.flatnonzero(np.diff(t) > gap_ms) + 1
    edges = np.concatenate(([0], cut, [len(t)]))
    return [(int(edges[i]), int(edges[i + 1])) for i in range(len(edges) - 1) if edges[i + 1] - edges[i] > 1000]


class Feed:
    """A rebuilt feed plus its weekly chunks. Arrays are shared by every run."""

    def __init__(self, data_dir, target_spread_pts=12.0, fixed=False, extra_pts=0.0, months=None, symbol="XAUUSD"):
        rt, rb, ra = load_raw(data_dir, symbol, months)
        self.t, self.bid, self.ask = broker_feed(rt, rb, ra, target_spread_pts, fixed, extra_pts)
        self.mid = (self.bid + self.ask) * 0.5
        self.chunks = chunks(self.t)
        self.target_spread_pts = target_spread_pts

    def describe(self):
        sp = (self.ask - self.bid) / POINT
        d = np.diff(self.t)
        d = d[d < 60000]
        return dict(ticks=len(self.t), chunks=len(self.chunks),
                    first=str(np.datetime64(int(self.t[0]), "ms")), last=str(np.datetime64(int(self.t[-1]), "ms")),
                    spread_median=float(np.median(sp)), spread_p90=float(np.percentile(sp, 90)),
                    spread_p99=float(np.percentile(sp, 99)), ticks_per_sec=float(1000.0 / d.mean()),
                    median_gap_ms=float(np.median(d)))
