"""Best H6 presets with trend bars aligned to a UTC server (Exness) vs an EET server (VT Markets);
entry hours stay in UTC in both. Every monthly start, 1,000 USD, M1-close model.
usage: TOKIO_SERVER_CLOCK=UTC|EET python broker_clock.py"""
import datetime as dt, json
import numpy as np, pandas as pd
import common as C

SPLIT = {"XAUUSD": dict(IS=[2011, 2012, 2013, 2014], OOS=[2015, 2016, 2017, 2018], Y26=[2026]),
         "BTCUSD": dict(IS=[2015, 2016, 2017], OOS=[2018, 2019], Y26=[2026])}
r = pd.read_csv("../results/timeframes_ranked.csv")
rows = []
for sym in ["XAUUSD", "BTCUSD"]:
    p = json.loads(r[(r.symbol == sym) & (r["rank"] == 1)].iloc[0].inputs)
    for part, yrs in SPLIT[sym].items():
        fin, dds = [], []
        for y in yrs:
            d = C.load(sym, y)
            starts = [None] if y == 2026 else [int(dt.datetime(y, m, 1, tzinfo=dt.timezone.utc).timestamp()) for m in range(1, 13)]
            for ts in starts:
                if ts is not None and not (d["t"][0] - 5 * 86400 <= ts <= d["t"][-1] - 60 * 86400):
                    continue
                x = C.backtest(p, sym, y, t_from=ts, coarse=True); fin.append(x["final"]); dds.append(x["dd"])
        fin = np.array(fin)
        rows.append(dict(clock=C.SERVER_CLOCK, symbol=sym, sample=part, starts=len(fin), ruined_pct=round(100 * (fin < 300).mean()),
                         losing_pct=round(100 * (fin < 1000).mean()), median_final=round(np.median(fin)),
                         p10_final=round(np.percentile(fin, 10)), median_dd=round(np.median(dds), 1), worst_dd=round(max(dds), 1)))
out = pd.DataFrame(rows); print(out.to_string(index=False))
f = "../results/broker_clock.csv"
try:
    prev = pd.read_csv(f); out = pd.concat([prev[prev.clock != C.SERVER_CLOCK], out])
except FileNotFoundError:
    pass
out.to_csv(f, index=False)
