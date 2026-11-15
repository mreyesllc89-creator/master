"""Rank the 20 per-timeframe calibrations by out-of-sample t-statistic of basket returns (sizing-
independent; July-August 2026 not used), then evaluate the winner per symbol in detail: every
monthly start, both tick models, cost stress, per year. usage: python best_eval.py TEMPLATE.set"""
import datetime as dt, json, shutil, sys
import numpy as np, pandas as pd
import common as C, setfile

template = sys.argv[1]
MODELS = [("M1 close", dict(coarse=True)), ("interpolated", dict())]
SPLIT = {"XAUUSD": dict(IS=[2011, 2012, 2013, 2014], OOS=[2015, 2016, 2017, 2018], Y26=[2026]),
         "BTCUSD": dict(IS=[2015, 2016, 2017], OOS=[2018, 2019], Y26=[2026])}


def month_starts(sym, y):
    d = C.load(sym, y); out = []
    for m in range(1, 13):
        ts = int(dt.datetime(y, m, 1, tzinfo=dt.timezone.utc).timestamp())
        if d["t"][0] - 5 * 86400 <= ts <= d["t"][-1] - 60 * 86400:
            out.append(ts)
    return out


summary, yearly, ranking = [], [], []
for sym in ["XAUUSD", "BTCUSD"]:
    tf = pd.read_csv(f"../results/timeframes_{sym}.csv").sort_values("oos_t", ascending=False)
    tf["rank"] = range(1, len(tf) + 1)
    ranking.append(tf.assign(symbol=sym))
    best = tf.iloc[0]
    p = json.loads(best.inputs)
    shutil.copy(f"../presets/by_timeframe/TOKIO_VolLab_{sym}_{best.timeframe}.set",
                f"../presets/TOKIO_VolLab_{sym}_BEST_{best.timeframe}.set")
    k = C.K_BTC if sym == "BTCUSD" else 1.0
    for part, yrs in SPLIT[sym].items():
        for y in yrs:
            r = C.backtest(p, sym, y, coarse=True); rs = r["reason"]
            yearly.append(dict(symbol=sym, timeframe=best.timeframe, sample=part, year=y, baskets=r["n"],
                               final=round(r["final"]), dd_pct=round(r["dd"], 1), trail=int((rs == 2).sum()),
                               stop=int((rs == 0).sum()), age=int((rs == 1).sum())))
        for model, mk in MODELS:
            fin, dds = [], []
            for y in yrs:
                for ts in ([None] if y == 2026 else month_starts(sym, y)):
                    r = C.backtest(p, sym, y, t_from=ts, **mk); fin.append(r["final"]); dds.append(r["dd"])
            fin = np.array(fin)
            row = dict(symbol=sym, timeframe=best.timeframe, sample=part, ticks=model, starts=len(fin),
                       ruined_pct=round(100 * (fin < 300).mean()), losing_pct=round(100 * (fin < 1000).mean()),
                       median_final=round(np.median(fin)), p10_final=round(np.percentile(fin, 10)),
                       p90_final=round(np.percentile(fin, 90)), median_dd=round(np.median(dds), 1),
                       worst_dd=round(max(dds), 1))
            for label, kw in (("spread x2", dict(spread_mult=2.0)), ("slip 0.25", dict(slip=0.25 * k))):
                row[f"median_final {label}"] = round(np.median([C.backtest(p, sym, y, **mk, **kw)["final"] for y in yrs]))
            summary.append(row); print(row, flush=True)

pd.concat(ranking).to_csv("../results/timeframes_ranked.csv", index=False)
pd.DataFrame(summary).to_csv("../results/best_timeframe_summary.csv", index=False)
pd.DataFrame(yearly).to_csv("../results/best_timeframe_yearly.csv", index=False)
