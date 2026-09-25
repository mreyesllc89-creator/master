"""Join trade exits to exported chart bars and measure how close each exit is to the exit bar's
favorable extreme (high for longs, low for shorts).

Usage: python3 analysis/join_check.py
"""
import csv, pathlib, sys
from datetime import datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analyze_trades import load

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAIRS = [
    ("OANDA 1m",    "GVLiveV2_OANDA_XAUUSD_1m.csv",    "OANDA_XAUUSD_1m.csv"),
    ("VANTAGE 1m",  "GVLiveV2_VANTAGE_XAUUSD_1m.csv",  "VANTAGE_XAUUSD_1m.csv"),
    ("VANTAGE 5m",  "GVLiveV2_VANTAGE_XAUUSD_5m.csv",  "VANTAGE_XAUUSD_5m.csv"),
    ("VANTAGE 30m", "GVLiveV2_VANTAGE_XAUUSD_30m.csv", "VANTAGE_XAUUSD_30m.csv"),
    ("VANTAGE 60m", "GVLiveV2_VANTAGE_XAUUSD_60m.csv", "VANTAGE_XAUUSD_60m.csv"),
    ("VANTAGE 240m","GVLiveV2_VANTAGE_XAUUSD_240m.csv","VANTAGE_XAUUSD_240m.csv"),
    ("VANTAGE 1D",  "GVLiveV2_VANTAGE_XAUUSD_1D.csv",  "VANTAGE_XAUUSD_1D.csv"),
]

def bar_time(raw):
    raw = raw[:16]
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M") if "T" in raw else datetime.strptime(raw[:10], "%Y-%m-%d")

for name, tl, bars in PAIRS:
    B = {}
    for r in csv.DictReader(open(ROOT / "data" / "bars" / bars)):
        B[bar_time(r["time"])] = dict(h=float(r["high"]), l=float(r["low"]), c=float(r["close"]))
    tr = [t for t in load(str(ROOT / "data" / "backtests" / tl)) if t["exit_time"] in B]
    win1 = [t for t in tr if t["pnl"] > 0 and t["bars"] == 1]
    gaps, rel = [], []
    for t in win1:
        eb = B[t["exit_time"]]
        ext = eb["h"] if t["side"] == "long" else eb["l"]
        gaps.append(abs(ext - t["exit_price"]))
        rng = eb["h"] - eb["l"]
        rel.append(gaps[-1] / rng if rng > 0 else 0.0)
    if not win1:
        print(f"{name:12s}: {len(tr)} trades overlap the bar export, no 1-bar winners to check"); continue
    gaps.sort(); rel.sort()
    within = sum(1 for r in rel if r <= 0.10)
    print(f"{name:12s}: {len(tr):4d} trades overlap bar export | 1-bar winners {len(win1):4d} | "
          f"exit within 10% of the exit bar's range from its favorable extreme: {within:4d} ({100*within/len(win1):5.1f}%) | "
          f"median gap ${gaps[len(gaps)//2]:.3f} = {100*rel[len(rel)//2]:.1f}% of bar range")
