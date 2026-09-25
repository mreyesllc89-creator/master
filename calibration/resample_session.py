"""Build session-aligned N-minute bars from a 1-minute TradingView export of a cash-session symbol
(bars start at the session open of each day, like TradingView's own intraday bars on SPCFD:SPX)."""
import sys, pandas as pd
src, out_prefix = sys.argv[1], sys.argv[2]
tfs = [int(x) for x in sys.argv[3].split(",")]
df = pd.read_csv(src)
t = pd.to_datetime(df["time"], utc=True).dt.tz_convert("America/New_York")
df["t"] = t
day = t.dt.date
open_min = t.dt.hour * 60 + t.dt.minute
for n in tfs:
    key = (open_min - 9 * 60 - 30) // n
    g = df.groupby([day, key], sort=True)
    bars = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), Volume=("Volume", "sum"), t=("t", "first"))
    bars = bars.reset_index(drop=True)
    start = bars["t"].dt.floor("min")
    # anchor the bar time at the slot start
    slot = ((start.dt.hour * 60 + start.dt.minute - 9 * 60 - 30) // n) * n
    bt = start.dt.normalize() + pd.to_timedelta(9 * 60 + 30 + slot, unit="m")
    bars["time"] = bt.dt.strftime("%Y-%m-%dT%H:%M:%S%z").str.replace(r"(\d\d)(\d\d)$", r"\1:\2", regex=True)
    bars[["time", "open", "high", "low", "close", "Volume"]].to_csv(f"{out_prefix}_{n}.csv", index=False)
    print(n, "min:", len(bars), "bars", bars["time"].iloc[0], "->", bars["time"].iloc[-1])
