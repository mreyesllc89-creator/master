#!/usr/bin/env python3
"""Out-of-sample check of the four Loma BTCUSD presets on Binance BTCUSDT M1 after the calibration data
(which ended 2026-05-15 23:59 UTC). Appends the new monthly/daily Binance zips to the calibration CSV so the
warm-up is identical, then reports in-sample (to compare with presets/btc/BTC_PRESETS_SUMMARY.csv) and
out-of-sample results, base and harsh stress, plus a monthly breakdown.
Usage: python3 btc_oos_check.py <calibration_csv_dir> <new_zip_dir> <work_dir>"""
import glob, io, json, os, sys, zipfile
import numpy as np, pandas as pd

CAL, NEW, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(WORK, exist_ok=True)
cal = pd.read_csv(os.path.join(CAL, "BTCUSD_m1.csv"), parse_dates=["datetime"])
cut = cal.datetime.max()
parts = []
for z in sorted(glob.glob(os.path.join(NEW, "BTCUSDT-1m-*.zip"))):
    with zipfile.ZipFile(z) as f:
        raw = pd.read_csv(io.BytesIO(f.read(f.namelist()[0])), header=None)
    t = raw[0].astype("int64")
    unit = "us" if t.iloc[0] > 1e14 else "ms"          # Binance spot files use microseconds from 2025
    parts.append(pd.DataFrame(dict(datetime=pd.to_datetime(t, unit=unit), open=raw[1], high=raw[2], low=raw[3],
                                   close=raw[4], volume=raw[5])))
new = pd.concat(parts)
new = new[new.datetime > cut].drop_duplicates("datetime").sort_values("datetime")
full = pd.concat([cal, new], ignore_index=True)
gaps = full.datetime.diff().dt.total_seconds().div(60).fillna(1)
full.to_csv(os.path.join(WORK, "BTCUSD_m1.csv"), index=False, date_format="%Y-%m-%d %H:%M:%S")
print(f"calibration data to {cut}, appended {len(new)} bars to {new.datetime.max()}, largest gap {gaps.max():.0f} min", flush=True)

os.environ.update(HUMP_SYMBOL="BTCUSD", HUMP_BTC_DATA=WORK, HUMP_SPACE="2")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_engine as H, hump_search as X, make_loma_presets as M

STRESS = dict(trail_worst=1, delay=1, slip=3.0, comm=2.0, max_spread=1e9)
oos_start = (pd.Timestamp(cut).tz_localize("UTC") + pd.Timedelta(minutes=1)).tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
d = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results/hump_btc_pool_ranked.csv")) \
      .sort_values("allround", ascending=False).drop_duplicates("fam")
for c in ["pf", "w25", "pf26", "st_pf", "st_w25", "st_pf26"]:
    d = d[d[c] >= 1.3]
mk = H.Market()


def pf(x):
    x = np.asarray(x, float); w = x[x > 0].sum(); l = -x[x < 0].sum()
    return float(w / l) if l > 0 else None


rows, monthly, trades = [], [], []
for rank, (_, r) in enumerate(d.iterrows(), 1):
    p = {k: X.cast(r[k], X.SPACE[k]) for k in X.SPACE if k in r.index}
    c = X.engine_cfg(dict(X.BASE, **p))
    for label, cfg in (("base", c), ("stress", dict(c, **STRESS))):
        df = mk.run(cfg); ins = df[df.entry_time < oos_start]; oos = df[df.entry_time >= oos_start]
        rows.append(dict(preset=f"BTC{rank:02d}", tf=p["tf"], variant=label, is_n=len(ins), is_pf=pf(ins.r),
                         oos_n=len(oos), oos_pf=pf(oos.r), oos_netR=round(float(oos.r.sum()), 2),
                         oos_win=round(float((oos.r > 0).mean()), 3) if len(oos) else None))
        if label == "base":
            o = oos.assign(month=oos.entry_time.dt.strftime("%Y-%m"))
            for mo, g in o.groupby("month"):
                monthly.append(dict(preset=f"BTC{rank:02d}", month=mo, n=len(g), netR=round(float(g.r.sum()), 2), pf=pf(g.r)))
            trades.append(oos.assign(preset=f"BTC{rank:02d}")[["preset", "entry_time", "side", "r"]] if "side" in oos else
                          oos.assign(preset=f"BTC{rank:02d}")[["preset", "entry_time", "r"]])
res = pd.DataFrame(rows); mon = pd.DataFrame(monthly)
allt = pd.concat(trades)
out = dict(calibration_end_utc=str(cut), oos_start_server=str(oos_start), data_end_utc=str(new.datetime.max()),
           presets=res.to_dict("records"), monthly=mon.to_dict("records"),
           all_four_base=dict(n=len(allt), pf=pf(allt.r), netR=round(float(allt.r.sum()), 2)))
os.makedirs("results/btc_oos", exist_ok=True)
suffix = "" if H.BTC_SPREAD == 10 else f"_spread{H.BTC_SPREAD:g}"
out["spread_usd"] = H.BTC_SPREAD
json.dump(out, open(f"results/btc_oos/btc_oos_2026{suffix}.json", "w"), indent=1, default=float)
allt.to_csv(f"results/btc_oos/btc_oos_trades{suffix}.csv", index=False)
pd.set_option("display.width", 250)
print(res.to_string(index=False)); print(mon.pivot_table(index="month", columns="preset", values="netR").round(1).to_string())
print("all four, base:", out["all_four_base"])
