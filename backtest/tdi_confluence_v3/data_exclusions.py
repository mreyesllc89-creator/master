"""Pre-registered data-quality exclusion (Amendment 1): a calendar month is excluded for a coin when more than 1% of
its 1-minute bars have zero traded volume (stale prices: the 1-minute indicators see artificial flat stretches and
fills cannot be simulated realistically). Indicators still run through excluded months; only trades ENTERED in an
excluded month are dropped from the statistics. Uses only the volume column of the Binance zips - no prices,
no strategy, no returns. Writes data_exclusions.json."""
import glob, json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
THRESHOLD_PCT = 1.0
SYMS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"]
out = dict(rule=f"exclude a calendar month for a coin if more than {THRESHOLD_PCT}% of its 1-minute bars have zero volume",
           threshold_pct=THRESHOLD_PCT, excluded={}, zero_volume_pct_by_month={})
for sym in SYMS:
    parts = []
    for f in sorted(glob.glob(os.path.join(HERE, "data", "full", sym, f"{sym}-1m-*.zip"))):
        d = pd.read_csv(f, header=None, usecols=[0, 5])
        t = d[0].to_numpy().astype("int64"); t = np.where(t > 10 ** 14, t // 1000, t)
        parts.append(pd.DataFrame({"m": pd.to_datetime(t, unit="ms").to_period("M").astype(str), "z": d[5].to_numpy() == 0}))
    P = pd.concat(parts)
    pct = P.groupby("m").z.mean().mul(100)
    out["zero_volume_pct_by_month"][sym] = {k: round(float(v), 4) for k, v in pct.items()}
    out["excluded"][sym] = [k for k, v in pct.items() if v > THRESHOLD_PCT]
    print(f"{sym}: {len(out['excluded'][sym])} months excluded: {', '.join(out['excluded'][sym])}")
json.dump(out, open(os.path.join(HERE, "data_exclusions.json"), "w"), indent=1)
