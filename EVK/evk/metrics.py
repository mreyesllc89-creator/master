"""Trade-list statistics."""
import numpy as np

PF_CAP = 100.0  # a profit factor with no losing trade is reported as this, not infinity


def pf(x):
    x = np.asarray(x, float)
    gw = x[x > 0].sum()
    gl = -x[x < 0].sum()
    if gl <= 0:
        return PF_CAP if gw > 0 else np.nan
    return min(gw / gl, PF_CAP)


def max_drawdown(x):
    eq = np.concatenate(([0.0], np.cumsum(np.asarray(x, float))))
    return float(np.max(np.maximum.accumulate(eq) - eq))


def stats(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return dict(trades=0, pf=np.nan, win=np.nan, expectancy=np.nan, net=0.0, maxdd=0.0)
    return dict(trades=int(len(x)), pf=float(pf(x)), win=float((x > 0).mean()),
                expectancy=float(x.mean()), net=float(x.sum()), maxdd=max_drawdown(x))


def period_pfs(times, x, edges):
    """Profit factor in each [edges[i], edges[i+1]) window of close time."""
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (times >= a) & (times < b)
        out.append((int(m.sum()), pf(x[m]) if m.any() else np.nan))
    return out


def score(times, x, criterion, min_trades, edges=None):
    """Ranking score used to choose a pass on a training window."""
    x = np.asarray(x, float)
    keep = np.isfinite(x)
    x = x[keep]
    times = np.asarray(times)[keep] if times is not None and len(times) == len(keep) else times
    if len(x) < min_trades:
        return -np.inf
    if criterion == "pf":
        return pf(x)
    if criterion == "net":
        return x.sum()
    if criterion == "expectancy":
        return x.mean()
    if criterion == "net_over_dd":
        dd = max_drawdown(x)
        return x.sum() / dd if dd > 0 else (PF_CAP if x.sum() > 0 else 0.0)
    if criterion == "min_period_pf":
        res = period_pfs(times, x, edges)
        if any(n == 0 for n, _ in res):
            return -np.inf
        return min(v for _, v in res)
    raise ValueError(f"unknown criterion {criterion}")
