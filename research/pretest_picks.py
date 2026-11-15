#!/usr/bin/env python3
"""
Second independent test of the re-calibration picks, on data from BEFORE the calibration period
(Jan 2025 - May 15 2026), never used for anything:
  BTCUSD  Binance BTCUSDT M1 of 2023 and 2024 (monthly zips)
  XAUUSD  Dukascopy M1 of July - December 2024 (bi5 files), FTMO hourly spread table

Every pick set of hump_tf_recal.py is run unchanged on the earlier period, base costs and harsh stress:
  "timeframe <TF>"        the protocol's picks of a timeframe (all trailing systems together)
  "trailing <kind>"       the picks of one trailing system over all timeframes
  "<TF> + <kind>"         every timeframe-and-trailing combination that reached PF 1.3 on at least 100
                          unseen trades in 2026 (the leads)
and the pooled profit factor is reported next to the 2026 out-of-sample figure.

Usage: [HUMP_SYMBOL=BTCUSD] python3 pretest_picks.py <recal_work_dir> <pre_data_dir> <out_json> [prefix]
"""
import glob, io, json, os, pickle, sys, zipfile
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_tf_recal as R
import hump_trail2 as T2
import hump_search as X
import xlzc_backtest as B

WORK, PRE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PREFIX = sys.argv[4] if len(sys.argv) > 4 else "candx+candy"

if R.SYM == "BTCUSD":
    parts = []
    for z in sorted(glob.glob(os.path.join(PRE, "BTCUSDT-1m-*.zip"))):
        with zipfile.ZipFile(z) as f:
            raw = pd.read_csv(io.BytesIO(f.read(f.namelist()[0])), header=None)
        t = raw[0].astype("int64")
        parts.append(pd.DataFrame(dict(datetime=pd.to_datetime(t, unit="us" if t.iloc[0] > 1e14 else "ms"),
                                       open=raw[1], high=raw[2], low=raw[3], close=raw[4])))
    m1 = pd.concat(parts).drop_duplicates("datetime").sort_values("datetime")
    utc = pd.DatetimeIndex(m1["datetime"]).tz_localize("UTC")
    m1.index = utc.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
    m1 = m1[~m1.index.duplicated()].sort_index()[["open", "high", "low", "close"]].astype(float)
    hs = np.full(len(m1), R.H.BTC_SPREAD / 2.0)
    PERIODS = {"2023": (np.datetime64("2023-01-15"), np.datetime64("2024-01-01")),
               "2024": (np.datetime64("2024-01-01"), np.datetime64("2025-01-01"))}
else:
    import duk_to_m1 as D
    m1, _ = D.load(PRE)
    m1 = m1[["open", "high", "low", "close"]].astype(float)
    _, hourly = B.load(R.H.DATA)
    hs = hourly[B.server_to_utc_hour(m1.index)] / 2.0
    first = m1.index[0] + pd.Timedelta(days=14)                    # two weeks of warm-up left out
    PERIODS = {"2024H2": (np.datetime64(first), np.datetime64("2025-01-01"))}
mk = T2.MarketY(m1=m1, half_spread=hs)
print("pre-period data", m1.index[0], "..", m1.index[-1], len(m1), "bars")


def trades(p, extra=None):
    c = dict(X.BASE); c.update(p)
    if extra:
        c.update(extra)
    df = mk.run_y(X.engine_cfg(c)) if "trail_kind" in p else mk.run(X.engine_cfg(c))
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


groups, cells = {}, {}
for tf in R.TFS:
    loaded = R.load_cands(WORK, PREFIX, tf)
    if loaded is None:
        continue
    P, Bs, Ss = loaded
    sc = np.array([R.is_score(Bs[i], Ss[i]) for i in range(len(P))])
    allidx = np.arange(len(P))
    for i in pick(P, sc, allidx):
        groups.setdefault(f"timeframe {tf}", []).append((P[i], R.split(*Bs[i])[2], R.split(*Ss[i])[2]))
    for kind in dict.fromkeys(p.get("trail_kind", "R") for p in P):
        idx = np.array([i for i in allidx if P[i].get("trail_kind", "R") == kind])
        for i in pick(P, sc, idx):
            item = (P[i], R.split(*Bs[i])[2], R.split(*Ss[i])[2])
            groups.setdefault(f"trailing {kind}", []).append(item)
            cells.setdefault(f"{tf} + {kind}", []).append(item)
for name, items in cells.items():                                   # the leads: PF >= 1.3 on >= 100 unseen trades
    r = np.concatenate([x[1] for x in items])
    if len(r) >= R.PASS_N and R.pf(r) >= R.PASS_PF:
        groups[name] = items

rows = []
for name, items in groups.items():
    row = dict(group=name, setups=len(items), oos2026_n=int(sum(len(x[1]) for x in items)),
               oos2026_pf=R.pf(np.concatenate([x[1] for x in items])), oos2026_stress_pf=R.pf(np.concatenate([x[2] for x in items])))
    base = [trades(x[0]) for x in items]; stress = [trades(x[0], R.STRESS) for x in items]
    for y, (a, b) in PERIODS.items():
        rb = np.concatenate([r[(t >= a) & (t < b)] for t, r in base]); rs = np.concatenate([r[(t >= a) & (t < b)] for t, r in stress])
        row[f"y{y}_n"] = int(len(rb)); row[f"y{y}_pf"] = R.pf(rb); row[f"y{y}_stress_pf"] = R.pf(rs); row[f"y{y}_net_r"] = float(rb.sum())
    rows.append(row)
json.dump(dict(symbol=R.SYM, prefix=PREFIX, data=[str(m1.index[0]), str(m1.index[-1])],
               periods={k: [str(a), str(b)] for k, (a, b) in PERIODS.items()}, groups=rows), open(OUT, "w"), indent=1, default=float)
pd.set_option("display.width", 250)
print(pd.DataFrame(rows).round(2).to_string(index=False))
