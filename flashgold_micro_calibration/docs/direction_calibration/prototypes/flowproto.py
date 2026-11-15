"""Toy flow series for the plumbing test (NOT a model of the real feed): FORCE / NEAR / BOOK on a regular grid,
loosely tied to the last seconds of price, quantised to 1/8 so float32 and float64 comparisons agree.
Interface the engine needs per chunk: fl_ix int32[n_ticks], fl_t int64[nu], fl_ok uint8[nu], fl_v float64[nu, 3]."""
import numpy as np


class FlowSeries:
    def __init__(self, feed, period_ms=1000, seed=1, scale=6.0, mom=0.05, dropout=0.0, ok_prob=1.0):
        self.feed = feed
        self.key = ("toy", period_ms, seed, scale, mom, dropout)
        self.period = int(period_ms)
        self.seed = seed
        self.scale = scale
        self.mom = mom
        self.dropout = dropout
        self.cache = {}

    def chunk(self, c):
        if c in self.cache:
            return self.cache[c]
        a, b = self.feed.chunks[c]
        t = self.feed.t[a:b]
        mid = self.feed.mid[a:b]
        rng = np.random.default_rng([self.seed, int(t[0]) % (2**31)])
        grid = np.arange(t[0], t[-1] + 1, self.period, dtype=np.int64)
        j = np.searchsorted(t, grid, side="right") - 1
        j3 = np.searchsorted(t, grid - 3000, side="right") - 1
        ret = (mid[j] - mid[np.maximum(j3, 0)]) / 0.01                        # last 3 s, points
        nu = len(grid)
        v = np.empty((nu, 3))
        v[:, 0] = self.mom * ret + rng.normal(0, self.scale, nu)               # FORCE follows price
        v[:, 1] = 0.6 * self.mom * ret + rng.normal(0, self.scale, nu)         # NEAR weaker
        v[:, 2] = -0.4 * self.mom * ret + rng.normal(0, self.scale, nu)        # BOOK leans against
        v = np.round(v * 8.0) / 8.0
        ok = np.ones(nu, np.uint8)
        if self.dropout > 0:                                                  # feed outages: OK = 0 for a while
            gaps = rng.random(nu) < self.dropout
            ok[gaps] = 0
        ix = (np.searchsorted(grid, t, side="right") - 1).astype(np.int32)
        out = (ix, grid, ok, np.ascontiguousarray(v))
        self.cache[c] = out
        return out
