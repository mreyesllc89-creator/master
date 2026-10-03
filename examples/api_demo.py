"""Use pychart from Python instead of the CLI.

Run:  python examples/api_demo.py
"""

from pathlib import Path

import pandas as pd

from pychart import Chart, SyntheticProvider, compute
from pychart.data import resample

# 1. Get candles. Swap SyntheticProvider for YahooProvider() or your own DataFrame.
df = SyntheticProvider(seed=42).fetch("DEMO", "1h", "60d")

# 2. Indicators are plain pandas, so you can use them outside the chart too.
rsi = compute(df, "rsi:14")["RSI 14"]
print("last RSI:", round(rsi.iloc[-1], 2))

# 3. A custom indicator is any function df -> {name: Series}.
def my_signal(frame: pd.DataFrame) -> dict[str, pd.Series]:
    fast = frame["close"].ewm(span=9, adjust=False).mean()
    slow = frame["close"].ewm(span=21, adjust=False).mean()
    return {"Cross": fast - slow}

print("fast-slow:", round(my_signal(df)["Cross"].iloc[-1], 4))

# 4. Resample and chart.
daily = resample(df, "1D")
chart = Chart(daily, symbol="DEMO", timeframe="1d").add("ema:9").add("ema:21").add("macd")
out = chart.save(Path("charts") / "api_demo.html", open_browser=False)
print("wrote", out)
