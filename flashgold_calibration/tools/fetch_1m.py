"""Download BTCUSDT USDT-M perpetual 1-minute klines from data.binance.vision.

usage: python fetch_1m.py <out.npz> <start YYYY-MM> <end YYYY-MM-DD>
Monthly archives are used where they exist, daily archives for the rest. Nothing is interpolated.
Output arrays: t (bar open, unix seconds, UTC), o, h, l, c, v.
"""
import io
import sys
import time
import zipfile
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests

BASE = "https://data.binance.vision/data/futures/um"
SYM = "BTCUSDT"
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
        "trades", "taker_buy_base", "taker_buy_quote", "ignore"]


def get(url, tries=5):
    for k in range(tries):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            break
        except requests.exceptions.RequestException:
            if k == tries - 1:
                raise
            time.sleep(2 ** k)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        raw = z.read(z.namelist()[0])
    has_header = not raw[:20].decode().split(",")[0].strip().isdigit()
    return pd.read_csv(io.BytesIO(raw), header=0 if has_header else None, names=None if has_header else COLS)


def main(out, start, end):
    y, m = map(int, start.split("-"))
    end_d = date.fromisoformat(end)
    frames = []
    d = date(y, m, 1)
    while d <= end_d:
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        df = get(f"{BASE}/monthly/klines/{SYM}/1m/{SYM}-1m-{d:%Y-%m}.zip") if nxt - timedelta(days=1) <= end_d else None
        if df is not None:
            frames.append(df)
            print(f"{d:%Y-%m} monthly {len(df)}", flush=True)
        else:
            day = d
            n = 0
            while day < nxt and day <= end_d:
                dd = get(f"{BASE}/daily/klines/{SYM}/1m/{SYM}-1m-{day:%Y-%m-%d}.zip")
                if dd is not None:
                    frames.append(dd)
                    n += len(dd)
                day += timedelta(days=1)
            print(f"{d:%Y-%m} daily {n}", flush=True)
        d = nxt
    df = pd.concat(frames).drop_duplicates("open_time").sort_values("open_time")
    np.savez_compressed(out, t=(df.open_time.values // 1000).astype(np.int64),
                        o=df.open.values.astype(np.float64), h=df.high.values.astype(np.float64),
                        l=df.low.values.astype(np.float64), c=df.close.values.astype(np.float64),
                        v=df.volume.values.astype(np.float64))
    print("rows", len(df), "from", pd.to_datetime(df.open_time.min(), unit="ms"), "to", pd.to_datetime(df.open_time.max(), unit="ms"))


if __name__ == "__main__":
    main(*sys.argv[1:4])
