"""Checks of the port that do not need MetaTrader.

usage: python -I selftest.py [data_dir]

1. micro quote buckets  - the cases of the package's own tests/test_bucket_host.py (seed bucket excluded,
                          OHLC, absent buckets not fabricated, gap epoch, capacity block)
2. continuation filter  - numba statistics against a plain numpy computation on random tapes
3. TDI direction        - against a plain pandas RSI / SMA
4. with tick data       - skipping idle ticks changes nothing; re-injecting the replay's own fills
                          reproduces its exits
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # scripts are run with python -I

import numpy as np
import pandas as pd

import engine
import flashgold
import params
import sim
import sweep
import ticks

checks = 0


def check(cond, name):
    global checks
    checks += 1
    if not cond:
        raise AssertionError(name)


def buckets(seq, width, max_bars, max_gap, restart=False):
    t = np.array([s[0] for s in seq], np.int64)
    p = np.array([s[1] for s in seq], np.float64)
    return flashgold.micro_buckets(t, p, width, max_bars, max_gap, restart)


def test_buckets():
    for width in (1, 250, 1000, 60000):
        seed = 1794670000000 // width * width
        first = seed + width
        seq = [(seed + width - 1, 100.0), (seed + width - 1, 101.0), (first, 100.0), (first, 103.0), (first, 98.0), (first, 101.0)]
        bt, bo, bh, bl, bc, li = buckets(seq, width, 32, 300000)
        check(len(bt) == 1 and bo[0] == 100 and bh[0] == 103 and bl[0] == 98 and bc[0] == 101 and bt[0] == first, "seed excluded, exact OHLC")
        seq += [(first + i * width, 100.0 + i) for i in range(1, 21)]
        bt, bo, bh, bl, bc, li = buckets(seq, width, 32, 300000)
        check(len(bt) == 21 and li[-1] == 20, "20 closed plus forming")
        seq += [(first + 22 * width, 122.0)]
        bt, bo, bh, bl, bc, li = buckets(seq, width, 32, 300000)
        check(len(bt) == 22 and bt[-1] - bt[-2] == 2 * width, "one absent bucket is not fabricated")
    bt, bo, bh, bl, bc, li = buckets([(1001, 100.0), (1250, 101.0), (2250, 102.0)], 250, 32, 1000)
    check(len(bt) == 2, "exact gap limit allowed")
    bt, bo, bh, bl, bc, li = buckets([(1001, 100.0), (1250, 101.0), (2250, 102.0), (3251, 103.0), (3499, 104.0), (3500, 105.0)], 250, 32, 1000)
    check(len(bt) == 3 and li[-1] == 0 and bt[-1] == 3500, "excess gap starts a new epoch whose first bucket is excluded")
    seq = [(0, 1.0)] + [(i, float(i)) for i in range(1, 22)] + [(21, 22.0), (22, 23.0), (23, 24.0), (500, 1.0)]
    bt, bo, bh, bl, bc, li = buckets(seq, 1, 21, 1000)
    check(len(bt) == 21 and bt[0] == 1 and bt[-1] == 21 and bc[-1] == 22.0, "capacity blocks without rolling reseed")
    bt, bo, bh, bl, bc, li = buckets(seq, 1, 21, 1000, restart=True)
    check(len(bt) == 23 and li[21] == 0 and bt[21] == 23, "restart option: new epoch, its first bucket excluded")


def test_cp():
    rng = np.random.default_rng(7)
    for _ in range(200):
        n = int(rng.integers(50, 4000))
        t = np.cumsum(rng.integers(1, 400, n)).astype(np.int64) + 10_000_000
        mid = 4000 + np.cumsum(rng.normal(0, 0.03, n))
        sp = rng.integers(8, 30, n) * 0.01
        b = np.round(mid - sp / 2, 2)
        a = b + sp
        i = n - 1
        c60, c300, n60, gap, r60, r300, msp = engine._cp_stats(t, b, a, i, 0.01)
        cutoff = t[i] // 1000 * 1000
        w = (t < cutoff) & (t >= cutoff - 360000)
        if not w.any():
            check(n60 == 0, "empty tape")
            continue
        w60 = (t < cutoff) & (t >= cutoff - 60000)
        w300 = (t < cutoff) & (t >= cutoff - 300000)
        m = (a + b) / 2
        check(c60 == (t[w].min() <= cutoff - 60000) and c300 == (t[w].min() <= cutoff - 300000), "completeness")
        check(n60 == int(w60.sum()), "tick count")
        if w60.sum() >= 2:
            check(abs(gap - np.median(np.diff(t[w60]))) < 1e-9, "median gap")
        if w60.any():
            check(abs(r60 - (m[w60].max() - m[w60].min()) / 0.01) < 1e-6, "60 s range")
            check(abs(msp - np.median((a - b)[w60] / 0.01)) < 1e-6, "median spread")
        if w300.any():
            check(abs(r300 - (m[w300].max() - m[w300].min()) / 0.01) < 1e-6, "300 s range")


def test_tdi():
    rng = np.random.default_rng(3)
    c = 4000 + np.cumsum(rng.normal(0, 1, 600))
    for rl, fl in ((14, 2), (7, 5)):
        d = flashgold.tdi_dirs(c, rl, fl)
        s = pd.Series(c).diff()
        up, dn = s.clip(lower=0), (-s).clip(lower=0)
        g = up.copy() * np.nan
        l = g.copy()
        g.iloc[rl] = up.iloc[1:rl + 1].mean()
        l.iloc[rl] = dn.iloc[1:rl + 1].mean()
        for i in range(rl + 1, len(c)):
            g.iloc[i] = (g.iloc[i - 1] * (rl - 1) + up.iloc[i]) / rl
            l.iloc[i] = (l.iloc[i - 1] * (rl - 1) + dn.iloc[i]) / rl
        rsi = 100 - 100 / (1 + g / l)
        fast = rsi.rolling(fl).mean()
        ref = np.sign(fast.diff()).fillna(0).to_numpy().astype(int)
        check((d[rl + fl + 1:] == ref[rl + fl + 1:]).all(), "TDI direction")


def test_with_data(data_dir):
    files = sorted(f for f in os.listdir(os.path.join(data_dir, "ticks")) if f.endswith(".npz"))
    month = files[-1][len("XAUUSD_"):-4]
    feed = ticks.Feed(data_dir, 12.0, months=[month])
    S = sim.Sim(feed, workers=1)
    z = np.zeros(0, np.int64)
    f = np.zeros(0, np.float64)
    for preset in ("FlashGold_NativeReference", "FlashGold_Micro1s"):
        p = sweep.base(preset)
        df = S.run(p)
        fg = S._fg(p)
        vec = params.vector(p)
        outs = []
        for c, (a, b) in enumerate(feed.chunks):
            out = np.zeros((20000, engine.NC))
            cnt = np.zeros(len(engine.COUNTERS), np.int64)
            n = engine.run_chunk(feed.t[a:b], feed.bid[a:b], feed.ask[a:b], vec, S._idx(c, 10.0), np.arange(b - a, dtype=np.int64),
                                 S.ep[c], fg.time, fg.end, fg.li, fg.a_at, fg.a_bar, fg.a_price, fg.a_dir, fg.a_atr,
                                 z, z, z, z, f, f, f, z, out, cnt)
            outs.append(out[:n])
        full = pd.DataFrame(np.concatenate(outs), columns=engine.TRADE_COLS).sort_values("entry_ms").reset_index(drop=True)
        check(len(full) == len(df) and np.allclose(full[["entry_ms", "exit_ms", "pts"]], df[["entry_ms", "exit_ms", "pts"]]),
              f"{preset}: idle skipping changes nothing")
        sl = np.where(df.action.isin([3, 4]), 80, 90)
        tp = np.where(df.action.isin([1, 2]), 180, 160)
        ext = pd.DataFrame(dict(ms=df.entry_ms.astype(np.int64), side=df.side.astype(int), action=df.action.astype(int),
                                scenario=df.scenario.astype(int), entry=df.entry, sl=np.round(df.requested - df.side * sl * 0.01, 2),
                                tp=np.round(df.requested + df.side * tp * 0.01, 2), id=np.arange(len(df))))
        q = dict(p, X_TradeBuys=0, X_TradeSells=0)
        dx = S.run(q, external=ext)
        m = df.reset_index().merge(dx, left_on="index", right_on="decision_ms", suffixes=("", "_x"))
        check(len(m) == len(df) and (m.reason == m.reason_x).mean() > 0.98, f"{preset}: re-injected fills reproduce the exits")
        print(f"  {preset} {month}: {len(df)} trades, same exit when re-injected {(m.reason == m.reason_x).mean():.3f}")


if __name__ == "__main__":
    test_buckets()
    test_cp()
    test_tdi()
    print("unit checks passed:", checks)
    if len(sys.argv) > 1:
        test_with_data(sys.argv[1])
        print("data checks passed:", checks)
