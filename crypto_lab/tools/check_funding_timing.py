"""Entry/exit timing check for funding_time_premium: prints entry and exit times of day and counts trades held
through a funding print (must be 0). usage: python -I check_funding_timing.py <tools_dir> <data_dir>"""
import sys
sys.path.insert(0, sys.argv[1])
import pandas as pd
import perpbt as bt, strategies as st
data = sys.argv[2]
for sym, tf, b in [("SOLUSDT", "1h", 1), ("SOLUSDT", "1h", 2), ("BTCUSDT", "1h", 2), ("SOLUSDT", "5m", 1), ("SOLUSDT", "5m", 2)]:
    df = bt.load(data, sym, tf); f = bt.load_funding(data, sym)
    t, _ = bt.run(df, st.funding_time_premium(df, f, thresh=0.0001, bars_before=b), f, sym)
    hm = lambda s: s.dt.strftime("%H:%M").value_counts().sort_index().to_dict()
    prints = f.index.floor("min")
    # a trade holds through a print if a funding timestamp falls in [entry_time, exit_time)
    ei = prints.searchsorted(pd.DatetimeIndex(t.entry_time), "left"); xi = prints.searchsorted(pd.DatetimeIndex(t.exit_time), "left")
    print(f"{sym} {tf} bars_before={b}: {len(t)} trades")
    print("  entry times", hm(t.entry_time)); print("  exit times ", hm(t.exit_time))
    print("  bars held", t.bars.value_counts().sort_index().to_dict(), "| exit reason", t.reason.value_counts().to_dict(),
          "| trades holding through a print:", int((xi > ei).sum()))
