"""Aggregate Dukascopy tick CSVs (time,bid,ask,bidvol,askvol) into M1 bid/ask bars.
Usage: python -I convert_ticks.py <root_dir> <out_npz>
Prices in the FX-Data repo are scaled 1/100 (13.486 == 1348.6); fixed here."""
import sys, os, glob
import numpy as np
import pandas as pd

root, out = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(os.path.join(root, "**", "*_ticks.csv"), recursive=True))
print("files:", len(files), flush=True)
parts = []
for k, f in enumerate(files):
    try:
        df = pd.read_csv(f, header=None, usecols=[0, 1, 2], names=["t", "bid", "ask"],
                         dtype={"bid": "float64", "ask": "float64"})
    except Exception as e:
        print("skip", f, e); continue
    if len(df) == 0: continue
    t = pd.to_datetime(df["t"], format="%Y.%m.%d %H:%M:%S.%f", errors="coerce")
    df = df[~t.isna()].copy(); df["t"] = t[~t.isna()]
    df["m"] = df["t"].dt.floor("min")
    g = df.groupby("m", sort=True)
    bar = pd.DataFrame({
        "bo": g["bid"].first(), "bh": g["bid"].max(), "bl": g["bid"].min(), "bc": g["bid"].last(),
        "ao": g["ask"].first(), "ah": g["ask"].max(), "al": g["ask"].min(), "ac": g["ask"].last(),
        "n": g["bid"].size()})
    parts.append(bar)
    if k % 500 == 0: print(k, f, flush=True)
bars = pd.concat(parts).sort_index()
bars = bars[~bars.index.duplicated(keep="last")]
scale = 100.0 if bars["bc"].median() < 100 else 1.0
for c in ["bo","bh","bl","bc","ao","ah","al","ac"]:
    bars[c] = bars[c] * scale
t = (bars.index.values.astype("datetime64[s]").astype(np.int64))
np.savez_compressed(out, t=t, **{c: bars[c].values.astype(np.float64) for c in ["bo","bh","bl","bc","ao","ah","al","ac"]}, n=bars["n"].values.astype(np.int32))
print("bars:", len(bars), "from", bars.index[0], "to", bars.index[-1], "scale", scale,
      "median spread", float((bars["ac"]-bars["bc"]).median()), flush=True)
