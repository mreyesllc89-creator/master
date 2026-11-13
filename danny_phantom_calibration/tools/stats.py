import numpy as np


def summarize(tr, bars, initial_capital):
    pnl = tr["pnl"]
    n = len(pnl)
    out = dict(trades=n, net=0.0, ret_pct=0.0, pf=0.0, win=0.0, maxdd_pct=0.0, sharpe=0.0,
               avg_r=0.0, exp=0.0, ret_dd=0.0, years=0.0, cagr=0.0)
    years = (bars["utc"][-1] - bars["utc"][0]) / (365.25 * 86400)
    out["years"] = years
    if n == 0:
        return out
    eq = initial_capital + np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[initial_capital], eq]))
    dd = (peak[1:] - eq) / peak[1:]
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    out["net"] = pnl.sum(); out["ret_pct"] = 100 * pnl.sum() / initial_capital
    out["pf"] = gp / gl if gl > 0 else (99.0 if gp > 0 else 0.0)
    out["win"] = 100 * (pnl > 0).mean(); out["maxdd_pct"] = 100 * dd.max()
    out["avg_r"] = tr["r"].mean(); out["exp"] = pnl.mean()
    out["ret_dd"] = out["ret_pct"] / out["maxdd_pct"] if out["maxdd_pct"] > 0 else 0.0
    final = eq[-1]
    out["cagr"] = 100 * ((final / initial_capital) ** (1 / years) - 1) if final > 0 and years > 0 else -100.0
    # per-trade sharpe annualised by trade frequency (rough quality measure)
    if n > 2 and pnl.std() > 0:
        out["sharpe"] = pnl.mean() / pnl.std() * np.sqrt(n / years)
    return out


def yearly(tr, bars, initial_capital):
    yrs = bars["year"][tr["o"]]
    res = {}
    for y in np.unique(yrs):
        m = yrs == y
        res[int(y)] = dict(trades=int(m.sum()), net=float(tr["pnl"][m].sum()))
    return res
