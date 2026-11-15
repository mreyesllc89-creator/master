"""Run the replay over a whole feed (all weeks, in parallel) and summarise the trades."""
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

import engine
import flashgold
import params
import ticks

PT = 0.01


class Sim:
    def __init__(self, feed, workers=None):
        self.feed = feed
        self.workers = workers or os.cpu_count()
        self.bar_cache = {}
        self.fg_cache = {}
        self.idx_cache = {}
        self.cand_cache = {}
        self.ep = []
        for a, b in feed.chunks:
            t = feed.t[a:b]
            s = np.zeros(len(t), np.int64)
            s[1:][np.diff(t) > 1000] = np.flatnonzero(np.diff(t) > 1000) + 1
            self.ep.append(t[np.maximum.accumulate(s)])
        self.pool = ThreadPoolExecutor(self.workers)

    def _fg(self, p):
        key = flashgold.fg_key(p)
        if key not in self.fg_cache:
            while len(self.fg_cache) >= 3:            # a micro series is ~1 GB on a year of ticks
                self.fg_cache.pop(next(iter(self.fg_cache)))
            self.fg_cache[key] = flashgold.FilterSeries(self.feed, p, self.bar_cache)
        return self.fg_cache[key]

    def _idx(self, c, lookback):
        key = (c, lookback)
        if key not in self.idx_cache:
            a, b = self.feed.chunks[c]
            t = self.feed.t[a:b]
            self.idx_cache[key] = np.searchsorted(t, t - int(lookback * 1000), side="left").astype(np.int64)
        return self.idx_cache[key]

    def _cand(self, c, lookback, minpts, mult):
        key = (c, lookback, minpts, mult)
        if key not in self.cand_cache:
            if len(self.cand_cache) > 400:
                self.cand_cache.clear()
            a, b = self.feed.chunks[c]
            mid = self.feed.mid[a:b]
            idx = self._idx(c, lookback)
            move = np.abs(mid - mid[idx]) / PT
            thr = np.maximum(minpts, (self.feed.ask[a:b] - self.feed.bid[a:b]) / PT * mult)
            self.cand_cache[key] = np.flatnonzero(move >= thr - 1e-7).astype(np.int64)
        return self.cand_cache[key]

    def run(self, p, with_counters=False, external=None):
        """external = DataFrame of fills to inject (columns ms, side, action, scenario, entry, sl, tp, id);
        each opens a position at the first tick at or after `ms`."""
        fg = self._fg(p)
        vec = params.vector(p)
        lookback = float(p["SpeedLookbackSeconds"])
        minpts = float(p["MinSpeedAlertPoints"])
        mult = float(p["MaxTrailingMultiplier"])

        def one(c):
            a, b = self.feed.chunks[c]
            out = np.zeros((20000, engine.NC))
            cnt = np.zeros(len(engine.COUNTERS), np.int64)
            if external is not None and len(external):
                t = self.feed.t[a:b]
                e = external[(external.ms >= t[0]) & (external.ms <= t[-1])].sort_values("ms")
                xi = np.searchsorted(t, e.ms.to_numpy()).astype(np.int64)
                ext = (xi, e.side.to_numpy(np.int64), e.action.to_numpy(np.int64), e.scenario.to_numpy(np.int64),
                       e.entry.to_numpy(np.float64), e.sl.to_numpy(np.float64), e.tp.to_numpy(np.float64),
                       e.id.to_numpy(np.int64))
            else:
                z = np.zeros(0, np.int64)
                f = np.zeros(0, np.float64)
                ext = (z, z, z, z, f, f, f, z)
            n = engine.run_chunk(self.feed.t[a:b], self.feed.bid[a:b], self.feed.ask[a:b], vec,
                                 self._idx(c, lookback), self._cand(c, lookback, minpts, mult), self.ep[c],
                                 fg.time, fg.end, fg.li, fg.a_at, fg.a_bar, fg.a_price, fg.a_dir, fg.a_atr,
                                 ext[0], ext[1], ext[2], ext[3], ext[4], ext[5], ext[6], ext[7], out, cnt)
            return out[:n], cnt

        res = list(self.pool.map(one, range(len(self.feed.chunks))))
        tr = np.concatenate([r[0] for r in res]) if res else np.zeros((0, engine.NC))
        df = pd.DataFrame(tr, columns=engine.TRADE_COLS)
        df = df.sort_values("entry_ms").reset_index(drop=True)
        if with_counters:
            cnt = np.sum([r[1] for r in res], axis=0)
            return df, dict(zip(engine.COUNTERS, cnt.tolist()))
        return df


def metrics(df):
    """Profit factor and friends, in points per 0.01 lot (1 point = 0.01 USD per 0.01 lot)."""
    n = len(df)
    if n == 0:
        return dict(n=0, net=0.0, pf=np.nan, win=np.nan, avg=np.nan, avg_win=np.nan, avg_loss=np.nan, dd=0.0, weeks_pos=np.nan)
    pts = df["pts"].to_numpy()
    w = pts[pts > 0].sum()
    l = -pts[pts < 0].sum()
    eq = np.cumsum(pts)
    dd = float(np.max(np.maximum.accumulate(np.maximum(eq, 0.0)) - eq)) if n else 0.0
    week = (df["entry_ms"].to_numpy() // (7 * 86400000))
    wk = pd.Series(pts).groupby(week).sum()
    return dict(n=n, net=float(pts.sum()), pf=float(w / l) if l > 0 else np.inf, win=float((pts > 0).mean()),
                avg=float(pts.mean()), avg_win=float(pts[pts > 0].mean()) if (pts > 0).any() else np.nan,
                avg_loss=float(pts[pts < 0].mean()) if (pts < 0).any() else np.nan, dd=dd,
                weeks_pos=float((wk > 0).mean()))


def label(df):
    out = df.copy()
    if len(out) == 0:
        for c in ("entry_time", "exit_time", "route", "exit_reason", "hold_s"):
            out[c] = pd.Series(dtype="object")
        return out
    out["entry_time"] = pd.to_datetime(out["entry_ms"], unit="ms")
    out["exit_time"] = pd.to_datetime(out["exit_ms"], unit="ms")
    out["route"] = out["scenario"].map(lambda s: engine.SCENARIO.get(int(s), "?")) + ":" + out["action"].map(lambda a: engine.ACTION.get(int(a), "?"))
    out["exit_reason"] = out["reason"].map(lambda r: engine.REASON.get(int(r), "?"))
    out["hold_s"] = (out["exit_ms"] - out["entry_ms"]) / 1000.0
    return out
