"""MT5 tick export (DATE TIME BID ASK LAST VOLUME FLAGS, tab separated, server time)
-> M1 bid/ask npz in UTC.  Usage: convert_mt5_ticks.py <server_utc_offset_hours> <out.npz> <csv...>"""
import sys, numpy as np, pandas as pd
off_h = float(sys.argv[1]); out = sys.argv[2]; files = sys.argv[3:]
parts = []
for f in files:
    df = pd.read_csv(f, sep="\t", usecols=["<DATE>", "<TIME>", "<BID>", "<ASK>"])
    df.columns = ["d", "tm", "bid", "ask"]
    df["bid"] = df["bid"].ffill(); df["ask"] = df["ask"].ffill()
    df = df.dropna(subset=["bid", "ask"])
    t = pd.to_datetime(df["d"] + " " + df["tm"], format="%Y.%m.%d %H:%M:%S.%f") - pd.Timedelta(hours=off_h)
    df["m"] = t.dt.floor("min")
    g = df.groupby("m", sort=True)
    parts.append(pd.DataFrame({"bo": g["bid"].first(), "bh": g["bid"].max(), "bl": g["bid"].min(), "bc": g["bid"].last(),
                               "ao": g["ask"].first(), "ah": g["ask"].max(), "al": g["ask"].min(), "ac": g["ask"].last(),
                               "n": g["bid"].size()}))
    print(f, len(df), "ticks ->", len(parts[-1]), "M1 bars", flush=True)
bars = pd.concat(parts).sort_index(); bars = bars[~bars.index.duplicated(keep="last")]
t = bars.index.values.astype("datetime64[s]").astype(np.int64)
np.savez_compressed(out, t=t, **{c: bars[c].values.astype(np.float64) for c in ["bo","bh","bl","bc","ao","ah","al","ac"]}, n=bars["n"].values.astype(np.int32))
print("bars:", len(bars), "UTC from", bars.index[0], "to", bars.index[-1], "median spread", float((bars["ac"]-bars["bc"]).median()))
