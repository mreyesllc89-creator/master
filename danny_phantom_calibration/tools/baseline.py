"""Shipped Tester preset on every timeframe of both symbols."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from data import load_bars, with_spread
from engine import backtest, R_END
from params import resolve
from stats import summarize, yearly

DATA = os.environ.get("DP_DATA", "/tmp/claude-0/-home-user-master/5fd8d858-05df-5949-bac4-7341515d4eed/scratchpad/data/m1")
CACHE = os.environ.get("DP_CACHE", "/tmp/claude-0/-home-user-master/5fd8d858-05df-5949-bac4-7341515d4eed/scratchpad/cache")
TFS = [1, 2, 3, 5, 10, 15, 30, 60, 240]

if __name__ == "__main__":
    syms = sys.argv[1:] or ["XAUUSD", "BTCUSD"]
    rows = []
    for sym in syms:
        for tf in TFS:
            for seg, raw in load_bars(DATA, sym, tf, CACHE):
                for model in ("modern", "recorded", "mid"):
                  bars = with_spread(raw, sym, model)
                  for preset in (["XAUUSD 5m"] if sym == "XAUUSD" else ["XAUUSD 5m", "Manual"]):
                    t0 = time.time()
                    P = resolve(dict(presetMode=preset), sym, tf)
                    tr = backtest(bars, P)
                    s = summarize(tr, bars, 10000.0)
                    reasons = np.bincount(tr["reason"], minlength=7)
                    print(f"{sym} M{tf:<3} {seg:<9} {model:<8} {preset:<10} trades={s['trades']:5d} ret={s['ret_pct']:8.1f}% "
                          f"pf={s['pf']:.2f} win={s['win']:.0f}% dd={s['maxdd_pct']:.1f}% avgR={s['avg_r']:+.3f} "
                          f"exits[stop,tp,dead,time,blk,rev]={reasons[:6].tolist()} ({time.time()-t0:.1f}s)")
