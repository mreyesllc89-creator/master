"""Download BTCUSDT SPOT 1-second klines from data.binance.vision (the perpetual has no 1-second archive).

usage: python fetch_1s.py <out.npz> <start YYYY-MM> <end YYYY-MM>
Seconds without a kline are filled with the previous close (flat bar), so the grid has no gaps.
Output arrays: t (unix seconds, UTC), o, h, l, c as float32-safe float64.
"""
import io
import sys
import time
import zipfile

import numpy as np
import pandas as pd
import requests

URL = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1s/BTCUSDT-1s-{}.zip"


def get(ym, tries=5):
    for k in range(tries):
        try:
            r = requests.get(URL.format(ym), timeout=600)
            r.raise_for_status()
            break
        except requests.exceptions.RequestException:
            if k == tries - 1:
                raise
            time.sleep(2 ** k)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=None, usecols=[0, 1, 2, 3, 4])
    df.columns = ["t", "o", "h", "l", "c"]
    div = 1_000_000 if df.t.iloc[0] > 10 ** 14 else 1000      # microseconds since 2025, milliseconds before
    df["t"] = df.t // div
    return df


def main(out, start, end):
    y, m = map(int, start.split("-"))
    y2, m2 = map(int, end.split("-"))
    parts = []
    while (y, m) <= (y2, m2):
        df = get(f"{y:04d}-{m:02d}")
        parts.append(df)
        print(f"{y:04d}-{m:02d} {len(df)}", flush=True)
        m += 1
        if m == 13:
            y, m = y + 1, 1
    df = pd.concat(parts).drop_duplicates("t").set_index("t").sort_index()
    grid = np.arange(df.index[0], df.index[-1] + 1)
    missing = len(grid) - len(df)
    df = df.reindex(grid)
    df["c"] = df.c.ffill()
    for k in ("o", "h", "l"):
        df[k] = df[k].fillna(df.c)
    np.savez_compressed(out, t=grid.astype(np.int64), o=df.o.values, h=df.h.values, l=df.l.values, c=df.c.values)
    print("rows", len(grid), "filled seconds", missing)


if __name__ == "__main__":
    main(*sys.argv[1:4])
