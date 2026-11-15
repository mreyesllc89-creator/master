#!/usr/bin/env python3
"""
SUPERSEDED by pretest_picks.py. The picks this script tested came from a BTC series with a clock error (see
hump_tf_recal.clock_check), so results/recal/btcusd_picks_on_2023_2024.json is invalid.

Second independent test of the BTC re-calibration picks: Binance BTCUSDT M1 of 2023 and 2024, which
come BEFORE the calibration data (Jan 2025 - May 15 2026) and were never used for anything.

For every pick set of hump_tf_recal.py (per timeframe, and per trailing family over all timeframes) the
picked setups are run unchanged on 2023 and on 2024, base costs and harsh stress, and the pooled profit
factor is reported next to the out-of-sample figure of 2026 (May 16 - Nov 13).

Note on comparability: the setups use fixed dollar distances and an assumed 10 USD spread. BTC traded at
17-44 thousand USD in 2023 and 39-108 thousand in 2024, against 60-125 thousand in the calibration period,
so 2024 is the closer test; in 2023 a 10 USD spread is relatively two to four times more expensive.

Usage: HUMP_SYMBOL=BTCUSD python3 btc_pretest.py <recal_work_dir> <zip_dir_2023_2024> <out_json>
"""
import glob, io, json, os, pickle, sys, zipfile
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_tf_recal as R
import hump_trail as T
import hump_search as X

assert R.SYM == "BTCUSD"
WORK, ZIPS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

parts = []
for z in sorted(glob.glob(os.path.join(ZIPS, "BTCUSDT-1m-*.zip"))):
    with zipfile.ZipFile(z) as f:
        raw = pd.read_csv(io.BytesIO(f.read(f.namelist()[0])), header=None)
    t = raw[0].astype("int64")
    unit = "us" if t.iloc[0] > 1e14 else "ms"
    parts.append(pd.DataFrame(dict(datetime=pd.to_datetime(t, unit=unit), open=raw[1], high=raw[2], low=raw[3], close=raw[4])))
m1 = pd.concat(parts).drop_duplicates("datetime").sort_values("datetime")
utc = pd.DatetimeIndex(m1["datetime"]).tz_localize("UTC")
m1.index = utc.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)      # broker server time, as load_btc
m1 = m1[~m1.index.duplicated()].sort_index()[["open", "high", "low", "close"]].astype(float)
mk = T.MarketX(m1=m1, half_spread=np.full(len(m1), R.H.BTC_SPREAD / 2.0))
print("pre-period data", m1.index[0], "..", m1.index[-1], len(m1), "bars; largest gap (min)",
      int(pd.Series(m1.index).diff().dt.total_seconds().div(60).max()))
Y = {"2023": (np.datetime64("2023-01-15"), np.datetime64("2024-01-01")),       # two weeks of warm-up left out
     "2024": (np.datetime64("2024-01-01"), np.datetime64("2025-01-01"))}


def trades(p, extra=None):
    c = dict(X.BASE); c.update(p)
    if extra:
        c.update(extra)
    df = mk.run_x(X.engine_cfg(c))
    return df.entry_time.values.astype("datetime64[m]"), df.r.values.astype(float)


def pick(P, sc, idx, k=R.TOPK):
    elig = idx[sc[idx] > 0]
    order = elig[np.argsort(-sc[elig], kind="stable")]
    out, fams = [], set()
    for i in order:
        if sc[i] < R.PASS_PF or len(out) >= k:
            break
        fam = (P[i]["sides"], P[i]["session"], P[i]["htf"])
        if fam in fams:
            continue
        fams.add(fam); out.append(int(i))
    return out


groups = {}                                   # name -> list of (params, oos_r, oos_stress_r)
for tf in R.TFS:
    fn = os.path.join(WORK, f"candx_{tf}.pkl")
    if not os.path.exists(fn):
        continue
    d = pickle.load(open(fn, "rb"))
    P, Bs, Ss = d["params"], d["base"], d["stress"]
    sc = np.array([R.is_score(Bs[i], Ss[i]) for i in range(len(P))])
    allidx = np.arange(len(P))
    for i in pick(P, sc, allidx):
        groups.setdefault(f"timeframe {tf}", []).append((P[i], R.split(*Bs[i])[2], R.split(*Ss[i])[2]))
    for kind in R.trail_space():
        idx = np.array([i for i in allidx if P[i]["trail_kind"] == kind])
        for i in pick(P, sc, idx):
            groups.setdefault(f"trailing {kind}", []).append((P[i], R.split(*Bs[i])[2], R.split(*Ss[i])[2]))
            if kind == "ema" and tf == "M10":
                groups.setdefault("M10 + ema trailing", []).append((P[i], R.split(*Bs[i])[2], R.split(*Ss[i])[2]))

rows = []
for name, items in groups.items():
    row = dict(group=name, setups=len(items), oos2026_n=int(sum(len(x[1]) for x in items)),
               oos2026_pf=R.pf(np.concatenate([x[1] for x in items])), oos2026_stress_pf=R.pf(np.concatenate([x[2] for x in items])))
    base = [trades(x[0]) for x in items]; stress = [trades(x[0], R.STRESS) for x in items]
    for y, (a, b) in Y.items():
        rb = np.concatenate([r[(t >= a) & (t < b)] for t, r in base]); rs = np.concatenate([r[(t >= a) & (t < b)] for t, r in stress])
        row[f"y{y}_n"] = int(len(rb)); row[f"y{y}_pf"] = R.pf(rb); row[f"y{y}_stress_pf"] = R.pf(rs); row[f"y{y}_net_r"] = float(rb.sum())
    rows.append(row)
json.dump(rows, open(OUT, "w"), indent=1, default=float)
pd.set_option("display.width", 250)
print(pd.DataFrame(rows).round(2).to_string(index=False))
