#!/usr/bin/env python3
"""
Exposure of the year-by-year presets (the picks of one cell for the year ahead, chosen on the last three years of the
data, as research/make_v135_presets.py wf writes them), on those three years at base costs:
  stops        the stop distance in dollars per unit (1 BTC), by year and together
  balance      the equity a trade needs at RiskPercent 0.1 with a 0.01 minimum lot and SkipIfBelowMinLot (10 x its stop)
  overlap      entry minutes shared by two or more presets, positions open at once
  leverage     position value / equity at RiskPercent 0.1, per trade and of all open positions together
  holding      minutes held, the share held over the server midnight, the longest hold
Usage (from research/): HUMP_SYMBOL=BTCUSD python3 wf_exposure.py <work> <TF> <condition> <out_json>
"""
import json, os, pickle, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_wf as W

work, tf, key, out_json = sys.argv[1:5]
RISK = 0.1                     # percent of equity per trade, as the presets set it
MIN_LOT = 0.01                 # BTC contract: 1 BTC per lot
W.MK = W.Mk(work)
A = np.load(os.path.join(work, f"wf_{tf}.npy")).astype(np.float64)
d = pickle.load(open(os.path.join(work, f"wf_{tf}_params.pkl"), "rb"))
P, years = d["params"], d["years"]; v = d["keys"].index(key)
cal = list(range(len(years) - 3, len(years)))
picks, *_ = W.window_pick(A, P, v, cal)
frames = []
for k, i in enumerate(picks, 1):
    df = W.trades_of(P[i], key, W.COSTS[0])
    df = df[df.entry_time.dt.year.isin([years[y] for y in cal])]
    frames.append(df.assign(preset=k))
t = pd.concat(frames).sort_values("entry_time").reset_index(drop=True)
t["year"] = t.entry_time.dt.year
t["price"] = W.MK.o[t.entry_row.values]
t["exit_time"] = W.MK.t[t.exit_row.values]
t["lev"] = (RISK / 100.0) * t.price / t.risk                       # position value / equity
t["need"] = MIN_LOT * t.risk / (RISK / 100.0)                      # equity the minimum lot needs
t["hold_min"] = (t.exit_time - t.entry_time).dt.total_seconds() / 60.0
t["overnight"] = t.exit_time.dt.normalize() > t.entry_time.dt.normalize()


def stops(x):
    return dict(trades=int(len(x)), price_low=float(x.price.min()), price_high=float(x.price.max()), stop_median=float(x.risk.median()),
                stop_p90=float(x.risk.quantile(0.9)), stop_max=float(x.risk.max()), equity_for_90pct=float(x.need.quantile(0.9)),
                lev_median=float(x.lev.median()), lev_p90=float(x.lev.quantile(0.9)), lev_max=float(x.lev.max()))


# positions open at the same time, and their value together
ev = sorted([(a, 1, l) for a, l in zip(t.entry_row, t.lev)] + [(b, -1, l) for b, l in zip(t.exit_row, t.lev)], key=lambda e: (e[0], e[1]))
n_open = lev_open = max_open = 0; max_lev = 0.0
for _, s, l in ev:
    n_open += s; lev_open += s * l
    max_open = max(max_open, n_open); max_lev = max(max_lev, lev_open)
minutes = t.groupby("entry_time").preset.nunique()
res = dict(symbol=W.SYM, tf=tf, condition=key, picked_on=[years[y] for y in cal], presets=len(picks), risk_percent=RISK, min_lot=MIN_LOT,
           all_years=stops(t), by_year={int(y): stops(x) for y, x in t.groupby("year")},
           entry_minutes=int(len(minutes)), shared_minutes=int((minutes >= 2).sum()), max_open=int(max_open), together_max_lev=float(max_lev),
           hold_median_minutes=float(t.hold_min.median()), hold_p90_minutes=float(t.hold_min.quantile(0.9)), hold_max_days=float(t.hold_min.max() / 1440.0),
           overnight_share=float(t.overnight.mean()),
           max_hold_minutes_of_picks=[int(P[i]["max_hold"]) for i in picks], eod_of_picks=[int(P[i]["eod"]) for i in picks])
json.dump(res, open(out_json, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "by_year"}, indent=1))
for y, s in res["by_year"].items():
    print(y, {k: round(v, 2) for k, v in s.items()})
