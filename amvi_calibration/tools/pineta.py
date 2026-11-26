"""Pine Script built-ins used by the AMVI strategy, reproduced bar for bar (numba).

Every function takes float64 arrays with NaN for Pine's `na` and returns arrays of the
same length. Definitions follow the Pine v6 reference implementations:

  ta.sma     simple mean of the last n values, na until n values exist (any na in the window -> na)
  ta.rma     seeded with ta.sma(src, n) on the first bar where that exists, then
             alpha * src + (1 - alpha) * prev with alpha = 1 / n
  ta.tr(true) high - low on the first bar, else max(h - l, |h - c[1]|, |l - c[1]|)
  ta.atr     ta.rma(ta.tr(true), n)
  ta.stdev   population standard deviation (biased = true), from ta.sma
  ta.highest / ta.lowest  rolling extremes over the last n bars, na until n bars exist
  ta.rsi     u = max(x - x[1], 0), d = max(x[1] - x, 0), rs = rma(u) / rma(d),
             100 - 100 / (1 + rs)
"""
import numpy as np
from numba import njit

NAN = np.nan


@njit(cache=True)
def sma(x, n):
    out = np.full(x.size, NAN)
    s = 0.0
    bad = 0  # NaNs currently inside the window
    for i in range(x.size):
        v = x[i]
        if np.isnan(v):
            bad += 1
        else:
            s += v
        if i >= n:
            w = x[i - n]
            if np.isnan(w):
                bad -= 1
            else:
                s -= w
        if i >= n - 1 and bad == 0:
            out[i] = s / n
    return out


@njit(cache=True)
def sma_exact(x, n):
    """ta.sma recomputed from scratch per bar (no running-sum drift); used where a
    comparison of two consecutive values decides a direction (the TDI fast line)."""
    out = np.full(x.size, NAN)
    for i in range(n - 1, x.size):
        s = 0.0
        ok = True
        for k in range(i - n + 1, i + 1):
            v = x[k]
            if np.isnan(v):
                ok = False
                break
            s += v
        if ok:
            out[i] = s / n
    return out


@njit(cache=True)
def rma(x, n):
    out = np.full(x.size, NAN)
    alpha = 1.0 / n
    s = 0.0
    cnt = 0  # consecutive non-NaN values seen while unseeded
    seeded = False
    prev = NAN
    for i in range(x.size):
        v = x[i]
        if not seeded:
            if np.isnan(v):
                s = 0.0
                cnt = 0
            else:
                s += v
                cnt += 1
                if cnt > n:
                    s -= x[i - n]
                    cnt = n
                if cnt == n:
                    prev = s / n
                    out[i] = prev
                    seeded = True
        else:
            if np.isnan(v):
                # Pine: alpha * na + ... = na, and the next bar re-seeds from sma
                seeded = False
                s = 0.0
                cnt = 0
                prev = NAN
            else:
                prev = alpha * v + (1.0 - alpha) * prev
                out[i] = prev
    return out


@njit(cache=True)
def true_range(h, l, c):
    out = np.empty(h.size)
    for i in range(h.size):
        if i == 0 or np.isnan(c[i - 1]):
            out[i] = h[i] - l[i]
        else:
            a = h[i] - l[i]
            b = abs(h[i] - c[i - 1])
            d = abs(l[i] - c[i - 1])
            out[i] = max(a, max(b, d))
    return out


@njit(cache=True)
def atr(h, l, c, n):
    return rma(true_range(h, l, c), n)


@njit(cache=True)
def stdev(x, n):
    """Population standard deviation over the last n bars (Pine ta.stdev, biased)."""
    out = np.full(x.size, NAN)
    for i in range(n - 1, x.size):
        s = 0.0
        ok = True
        for k in range(i - n + 1, i + 1):
            v = x[k]
            if np.isnan(v):
                ok = False
                break
            s += v
        if not ok:
            continue
        m = s / n
        q = 0.0
        for k in range(i - n + 1, i + 1):
            d = x[k] - m
            q += d * d
        out[i] = np.sqrt(q / n)
    return out


@njit(cache=True)
def highest(x, n):
    out = np.full(x.size, NAN)
    for i in range(n - 1, x.size):
        m = -np.inf
        ok = True
        for k in range(i - n + 1, i + 1):
            v = x[k]
            if np.isnan(v):
                ok = False
                break
            if v > m:
                m = v
        if ok:
            out[i] = m
    return out


@njit(cache=True)
def lowest(x, n):
    out = np.full(x.size, NAN)
    for i in range(n - 1, x.size):
        m = np.inf
        ok = True
        for k in range(i - n + 1, i + 1):
            v = x[k]
            if np.isnan(v):
                ok = False
                break
            if v < m:
                m = v
        if ok:
            out[i] = m
    return out


@njit(cache=True)
def rolling_minmax(x, n):
    """(lowest, highest) over the last n bars with monotonic deques: O(len). NaN in the
    window -> NaN, as ta.lowest / ta.highest."""
    size = x.size
    lo = np.full(size, NAN)
    hi = np.full(size, NAN)
    dq_min = np.empty(size, np.int64)
    dq_max = np.empty(size, np.int64)
    h_min = 0
    t_min = 0
    h_max = 0
    t_max = 0
    last_nan = -1
    for i in range(size):
        v = x[i]
        if np.isnan(v):
            last_nan = i
            h_min = t_min = 0
            h_max = t_max = 0
            continue
        while t_min > h_min and x[dq_min[t_min - 1]] >= v:
            t_min -= 1
        dq_min[t_min] = i
        t_min += 1
        while t_max > h_max and x[dq_max[t_max - 1]] <= v:
            t_max -= 1
        dq_max[t_max] = i
        t_max += 1
        start = i - n + 1
        while dq_min[h_min] < start:
            h_min += 1
        while dq_max[h_max] < start:
            h_max += 1
        if start >= 0 and last_nan < start:
            lo[i] = x[dq_min[h_min]]
            hi[i] = x[dq_max[h_max]]
    return lo, hi


@njit(cache=True)
def normalize(x, n):
    """AMVI normalize(): (val - lowest) / (highest - lowest) over n bars, 0 when flat."""
    lo, hi = rolling_minmax(x, n)
    out = np.full(x.size, NAN)
    for i in range(x.size):
        if np.isnan(lo[i]) or np.isnan(hi[i]) or np.isnan(x[i]):
            continue
        if hi[i] <= lo[i]:
            out[i] = 0.0
        else:
            out[i] = (x[i] - lo[i]) / (hi[i] - lo[i])
    return out


@njit(cache=True)
def rsi(x, n):
    size = x.size
    u = np.full(size, NAN)
    d = np.full(size, NAN)
    for i in range(1, size):
        if np.isnan(x[i]) or np.isnan(x[i - 1]):
            continue
        ch = x[i] - x[i - 1]
        u[i] = ch if ch > 0.0 else 0.0
        d[i] = -ch if ch < 0.0 else 0.0
    ru = rma(u, n)
    rd = rma(d, n)
    out = np.full(size, NAN)
    for i in range(size):
        if np.isnan(ru[i]) or np.isnan(rd[i]):
            continue
        if rd[i] == 0.0:
            # rs = +inf -> 100; 0 / 0 is na in Pine
            out[i] = 100.0 if ru[i] > 0.0 else NAN
        else:
            out[i] = 100.0 - 100.0 / (1.0 + ru[i] / rd[i])
    return out
