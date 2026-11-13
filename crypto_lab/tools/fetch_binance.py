"""Pull Binance USDT-M perpetual history from the public bulk archive (data.binance.vision).

usage: python -I fetch_binance.py <out_dir> <start YYYY-MM> <end YYYY-MM> [symbols...]
Writes parquet: <out_dir>/<SYM>_<tf>.parquet (klines 5m and 1h), <SYM>_funding.parquet,
<SYM>_metrics.parquet (daily OI / long-short ratios, 5-minute rows). Every row keeps its source URL
in the file's metadata; nothing is interpolated. Re-runs skip months already on disk.
"""
import io
import os
import sys
import time
import zipfile
from datetime import date

import pandas as pd
import requests

BASE = "https://data.binance.vision/data/futures/um"
_t = date.today()
CURRENT_MONTHS = (f"{_t.year - (1 if _t.month == 1 else 0):04d}-{12 if _t.month == 1 else _t.month - 1:02d}", f"{_t.year:04d}-{_t.month:02d}")
KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
         "trades", "taker_buy_base", "taker_buy_quote", "ignore"]


def months(start, end):
    y, m = map(int, start.split("-")); y2, m2 = map(int, end.split("-"))
    while (y, m) <= (y2, m2):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def get_zip_csv(url, names=None, tries=5):
    for attempt in range(tries):
        try:
            r = requests.get(url, timeout=120)
            break
        except requests.exceptions.RequestException as e:  # transient proxy/TLS hiccups
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        with z.open(z.namelist()[0]) as f:
            head = f.read(200).decode(); f.seek(0) if hasattr(f, "seek") else None
        with z.open(z.namelist()[0]) as f:
            has_header = not head.split(",")[0].strip().isdigit()
            return pd.read_csv(f, header=0 if has_header else None, names=None if has_header else names)


def klines(sym, tf, start, end, out):
    cache = os.path.join(out, "raw", f"{sym}_{tf}")
    os.makedirs(cache, exist_ok=True)
    frames = []
    for ym in months(start, end):
        p = os.path.join(cache, f"{ym}.parquet")
        if not os.path.exists(p) or ym >= CURRENT_MONTHS[0]:
            url = f"{BASE}/monthly/klines/{sym}/{tf}/{sym}-{tf}-{ym}.zip"
            df = get_zip_csv(url, KCOLS)
            if df is None:  # month not closed yet: stitch the daily files
                y, m = map(int, ym.split("-")); d = date(y, m, 1); parts = []
                while d < date.today() and d.month == m:
                    durl = f"{BASE}/daily/klines/{sym}/{tf}/{sym}-{tf}-{d}.zip"
                    dd = get_zip_csv(durl, KCOLS)
                    if dd is not None:
                        dd.columns = KCOLS[:len(dd.columns)]; dd["source"] = durl; parts.append(dd)
                    d = date.fromordinal(d.toordinal() + 1)
                if not parts:
                    print(f"  missing {url}"); continue
                df = pd.concat(parts); url = "daily files " + ym
            df.columns = KCOLS[:len(df.columns)] if "source" not in df.columns else df.columns
            df = df[["open_time", "open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_buy_base"]].copy()
            df["source"] = url
            df.to_parquet(p)
        frames.append(pd.read_parquet(p))
    df = pd.concat(frames).drop_duplicates("open_time").sort_values("open_time")
    unit = "us" if df.open_time.iloc[-1] > 1e14 else "ms"
    df["time"] = pd.to_datetime(df.open_time, unit=unit, utc=True)
    df.to_parquet(os.path.join(out, f"{sym}_{tf}.parquet"))
    print(f"{sym} {tf}: {len(df)} bars {df.time.iloc[0]} -> {df.time.iloc[-1]}")


def funding(sym, start, end, out):
    cache = os.path.join(out, "raw", f"{sym}_funding"); os.makedirs(cache, exist_ok=True)
    frames = []
    for ym in months(start, end):
        p = os.path.join(cache, f"{ym}.parquet")
        if not os.path.exists(p) or ym >= CURRENT_MONTHS[0]:
            url = f"{BASE}/monthly/fundingRate/{sym}/{sym}-fundingRate-{ym}.zip"
            df = get_zip_csv(url, ["calc_time", "funding_interval_hours", "last_funding_rate"])
            if df is None:
                print(f"  missing {url} (current month: funding lags a month in the archive)"); continue
            df.columns = ["calc_time", "funding_interval_hours", "last_funding_rate"][:len(df.columns)]
            df["source"] = url; df.to_parquet(p)
        frames.append(pd.read_parquet(p))
    df = pd.concat(frames).drop_duplicates("calc_time").sort_values("calc_time")
    df["time"] = pd.to_datetime(df.calc_time, unit="ms", utc=True)
    df.to_parquet(os.path.join(out, f"{sym}_funding.parquet"))
    print(f"{sym} funding: {len(df)} rows {df.time.iloc[0]} -> {df.time.iloc[-1]}")


def metrics(sym, start, end, out):
    """Daily files with 5-minute open interest and long/short ratios (exist from ~2021-12).
    Cached per month as hourly rows (raw/<sym>_metrics/<ym>.parquet); daily downloads kept in
    raw/<sym>_metrics_daily (git-ignored) so an interrupted month resumes."""
    mcache = os.path.join(out, "raw", f"{sym}_metrics"); dcache = os.path.join(out, "raw", f"{sym}_metrics_daily")
    os.makedirs(mcache, exist_ok=True); os.makedirs(dcache, exist_ok=True)
    frames = []
    for ym in months(start, end):
        mp = os.path.join(mcache, f"{ym}.parquet")
        if not os.path.exists(mp) or ym >= CURRENT_MONTHS[0]:
            y, m = map(int, ym.split("-")); d = date(y, m, 1); days = []
            while d < date.today() and d.month == m:
                p = os.path.join(dcache, f"{d}.parquet")
                if not os.path.exists(p):
                    url = f"{BASE}/daily/metrics/{sym}/{sym}-metrics-{d}.zip"
                    df = get_zip_csv(url)
                    if df is not None:
                        df["source"] = url; df.to_parquet(p)
                if os.path.exists(p):
                    days.append(pd.read_parquet(p))
                d = date.fromordinal(d.toordinal() + 1)
            if not days:
                continue
            df = pd.concat(days)
            df["time"] = pd.to_datetime(df.create_time, utc=True)
            num = [c for c in df.columns if c not in ("time", "create_time", "symbol", "source")]
            df = df.drop_duplicates("time").set_index("time")[num].astype(float).resample("1h", label="right", closed="right").last().dropna(how="all").reset_index()
            df["source"] = f"{BASE}/daily/metrics/{sym}/ (hourly last of 5-minute rows)"
            df.to_parquet(mp)
        frames.append(pd.read_parquet(mp))
    if frames:
        df = pd.concat(frames).drop_duplicates("time").sort_values("time")
        df.to_parquet(os.path.join(out, f"{sym}_metrics.parquet"))
        print(f"{sym} metrics: {len(df)} hourly rows {df.time.iloc[0]} -> {df.time.iloc[-1]}")


if __name__ == "__main__":
    out, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
    syms = sys.argv[4:] or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    os.makedirs(out, exist_ok=True)
    for s in syms:
        for tf in ("1h", "4h"):
            klines(s, tf, start, end, out)
        funding(s, start, end, out)
        metrics(s, start, end, out)
