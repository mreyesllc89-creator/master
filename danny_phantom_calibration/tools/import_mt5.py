"""Convert MT5 exports (Symbols window -> Ticks or Bars -> Export) into the per-year M1 npz
files the calibration reads, then the whole pipeline can be rerun.

usage:
  python -I import_mt5.py ticks XAUUSD <server_utc_offset_hours> <out_dir> <csv...>
  python -I import_mt5.py bars  XAUUSD <server_utc_offset_hours> <out_dir> <csv...>

Tick export columns: <DATE> <TIME> <BID> <ASK> <LAST> <VOLUME> <FLAGS> (tab separated, server time).
M1 bar export columns: <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>; bars are bid
prices, ask is rebuilt as bid + SPREAD points (point = 0.001 gold / 0.01 bitcoin).
Server offset: Octa GMT+2 winter / GMT+3 summer -> pass 2 or 3 for the period of the export (a mixed
export is handled automatically when the server follows EET DST; pass "auto").
Output: <out_dir>/<symbol>_m1_<year>.npz (t UTC seconds, bo bh bl bc ao ah al ac, n ticks). Existing
files for the same year are merged, newest data wins.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

POINT = {"XAUUSD": 0.001, "BTCUSD": 0.01}
COLS = ["bo", "bh", "bl", "bc", "ao", "ah", "al", "ac"]


def server_offset(ts, spec):
    if spec != "auto":
        return pd.Timedelta(hours=float(spec))
    # EET/EEST: UTC+2, UTC+3 between the last Sundays of March and October
    local = ts.dt.tz_localize("Europe/Athens", ambiguous="NaT", nonexistent="shift_forward")
    return local.dt.utcoffset()


def read_ticks(path, symbol, spec):
    df = pd.read_csv(path, sep="\t", usecols=["<DATE>", "<TIME>", "<BID>", "<ASK>"])
    df.columns = ["d", "tm", "bid", "ask"]
    df["bid"] = df["bid"].ffill(); df["ask"] = df["ask"].ffill()
    df = df.dropna(subset=["bid", "ask"])
    ts = pd.to_datetime(df["d"] + " " + df["tm"], format="%Y.%m.%d %H:%M:%S.%f")
    df["m"] = (ts - server_offset(ts, spec)).dt.floor("min")
    g = df.groupby("m", sort=True)
    return pd.DataFrame({"bo": g.bid.first(), "bh": g.bid.max(), "bl": g.bid.min(), "bc": g.bid.last(),
                         "ao": g.ask.first(), "ah": g.ask.max(), "al": g.ask.min(), "ac": g.ask.last(),
                         "n": g.bid.size()})


def read_bars(path, symbol, spec):
    df = pd.read_csv(path, sep="\t")
    df.columns = [c.strip("<>").lower() for c in df.columns]
    ts = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S")
    m = (ts - server_offset(ts, spec)).dt.floor("min")
    sp = df["spread"].astype(float) * POINT[symbol]
    out = pd.DataFrame({"bo": df.open, "bh": df.high, "bl": df.low, "bc": df.close,
                        "ao": df.open + sp, "ah": df.high + sp, "al": df.low + sp, "ac": df.close + sp,
                        "n": df.tickvol}, index=m)
    return out[~out.index.duplicated(keep="last")].sort_index()


def main():
    kind, symbol, spec, out_dir, files = sys.argv[1], sys.argv[2].upper(), sys.argv[3], sys.argv[4], sys.argv[5:]
    reader = read_ticks if kind == "ticks" else read_bars
    parts = []
    for pattern in files:
        for f in sorted(glob.glob(pattern)):
            p = reader(f, symbol, spec); parts.append(p)
            print(f"{f}: {len(p)} M1 bars, {p.index[0]} -> {p.index[-1]} UTC, median spread {(p.ac - p.bc).median():.4f}")
    bars = pd.concat(parts).sort_index(); bars = bars[~bars.index.duplicated(keep="last")]
    os.makedirs(out_dir, exist_ok=True)
    for year, b in bars.groupby(bars.index.year):
        path = os.path.join(out_dir, f"{symbol.lower()}_m1_{year}.npz")
        if os.path.exists(path):
            z = np.load(path)
            old = pd.DataFrame({c: z[c] for c in COLS + ["n"]}, index=pd.to_datetime(z["t"], unit="s"))
            b = pd.concat([old, b]); b = b[~b.index.duplicated(keep="last")].sort_index()
        t = b.index.values.astype("datetime64[s]").astype(np.int64)
        np.savez_compressed(path, t=t, **{c: b[c].values.astype(np.float64) for c in COLS}, n=b["n"].values.astype(np.int32))
        print(f"wrote {path}: {len(b)} bars")


if __name__ == "__main__":
    main()
