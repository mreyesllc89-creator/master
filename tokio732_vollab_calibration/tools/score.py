"""Evaluate one gene on a set of years. Every year is run from 1000 USD at two start dates (start of
year and 1 July). The EA is evaluated once per M1 bar at the recorded close: no intrabar path is
assumed, so nothing can be earned from price movement the data does not contain.
Score = mean log growth (floored at 50 USD, capped at x20) - 2 * (worst equity drawdown)^2."""
import datetime as dt
import numpy as np
import common as C, space as S

SPLIT = {"XAUUSD": dict(IS=[2011, 2012, 2013, 2014], OOS=[2015, 2016, 2017, 2018], Y26=[2026]),
         "BTCUSD": dict(IS=[2015, 2016, 2017], OOS=[2018, 2019], Y26=[2026])}

STEPS = (0.05, 0.5, 1.5)


def to_symbol(p, sym):
    if sym != "BTCUSD":
        return p
    q = dict(p)
    for k in C.PRICE_KEYS:
        q[k] = p[k] * C.K_BTC
    q["LotsWithTrend"] = p["LotsWithTrend"] * 100.0 / C.K_BTC
    q["LotsAgainstTrend"] = p["LotsAgainstTrend"] * 100.0 / C.K_BTC
    return q


def starts(year):
    if year == 2026:
        return [None]
    return [None, int(dt.datetime(year, 7, 1, tzinfo=dt.timezone.utc).timestamp())]


def evaluate(g, sym, yrs, **kw):
    p = to_symbol(S.to_params(g, C.SHIPPED), sym)
    gs, dds, nets, nb, ruin, rr = [], [], [], 0, 0, []
    for y in yrs:
        for st in starts(y):
            if st is not None and st > C.load(sym, y)["t"][-1] - 30 * 86400:
                continue
            k = C.K_BTC if sym == "BTCUSD" else 1.0
            rs = [C.backtest(p, sym, y, t_from=st, coarse=True, **kw)]
            r = min(rs, key=lambda x: x["final"])
            gs.append(np.log(min(max(r["final"], 50.0), 20000.0) / 1000.0)); dds.append(max(x["dd"] for x in rs))
            nets.append(r["net"]); nb += r["n"]; ruin += r["final"] < 300; rr.append(r["r"])
    rr = np.concatenate(rr) if rr else np.zeros(0)
    t = rr.mean() / rr.std() * np.sqrt(len(rr)) if len(rr) > 5 and rr.std() > 0 else 0.0
    return dict(score=float(np.mean(gs) - 2 * (max(dds) / 100) ** 2), growth=float(np.mean(gs)),
                worst_dd=float(max(dds)), mean_dd=float(np.mean(dds)), ruined=int(ruin), runs=len(gs),
                baskets=int(nb), median_net=float(np.median(nets)), worst_net=float(min(nets)), t=float(t))
