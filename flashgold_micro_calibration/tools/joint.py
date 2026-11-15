"""Joint random search over the inputs that matter, scored on the calibration months only.

usage: python -I joint.py <preset> <n> <seed> <out csv> [spread_pts] [wide|focus]

Every sampled input set is replayed on the whole feed; the calibration (is), validation (val) and
hold-out (test) results are stored side by side so that selection can be done on `is` alone.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # scripts are run with python -I

import numpy as np
import pandas as pd

import engine
import oat
import sim
import sweep
import ticks

SPACE = {
    "EntryRouterMode": [1, 2],
    "MaxSpreadPoints": [13, 14, 16, 20, 31],
    "MaxTrailingMultiplier": [5, 7.5, 9, 11, 13],
    "MinSpeedAlertPoints": [37, 80, 120],
    "SpeedLookbackSeconds": [5, 10, 15],
    "StopEntryDistancePoints": [10, 20, 35, 50, 70],
    "PendingExpirySeconds": [3, 5, 10, 20],
    "InpUseEntryHold": [0, 1],
    "InpEntryHoldMs": [500, 1100, 2000],
    "InpUsePrior60Filter": [0, 1],
    "UseFlashGoldDirectionFilter": [0, 1],
    "InpCPMinTickRate60": [0, 3.8, 6.5],
    "ScenarioIndependentPerformance": [0, 1],
    "_sl": [60, 90, 130, 200, 300, 450],
    "_tp": [180, 300, 600, 1500],
    "UseSpeedProfitExit": [0, 1],
    "SpeedProfitExitPoints": [70, 100, 150, 250],
    "_trail": ["none", "simple", "layer"],
    "TrailStartPoints": [69, 100, 160, 250],
    "TrailBehindPoints": [30, 60, 110, 200],
    "internalMinTrailing": [2.0, 3.3333333, 5.0, 8.0],
    "UsePostEntryValidation": [0, 1],
    "_market": [0, 1],
}


# second pass: the region the first pass points to (no fade route, tight spread cap, wide stop, far
# target, no fixed-profit exit), entry inputs still free
FOCUS = {
    "EntryRouterMode": [1],
    "MaxSpreadPoints": [11, 12, 13, 14, 15],
    "MaxTrailingMultiplier": [5, 7.5, 9, 11, 13, 16],
    "MinSpeedAlertPoints": [37, 80, 120, 160],
    "SpeedLookbackSeconds": [5, 10, 15],
    "StopEntryDistancePoints": [10, 20, 35, 50, 70],
    "PendingExpirySeconds": [3, 5, 10, 20],
    "InpUseEntryHold": [0, 1],
    "InpEntryHoldMs": [500, 1100, 2000],
    "InpUsePrior60Filter": [0, 1],
    "UseFlashGoldDirectionFilter": [0, 1],
    "InpCPMinTickRate60": [0, 3.8, 6.5],
    "ScenarioIndependentPerformance": [0, 1],
    "_sl": [200, 300, 450],
    "_tp": [600, 1500],
    "UseSpeedProfitExit": [0],
    "SpeedProfitExitPoints": [100],
    "_trail": ["none", "simple", "layer"],
    "TrailStartPoints": [100, 160, 250],
    "TrailBehindPoints": [60, 110, 200],
    "internalMinTrailing": [3.3333333, 5.0, 8.0],
    "UsePostEntryValidation": [0, 1],
    "_market": [0, 1],
}


def sample(rng, space=None):
    v = {k: vals[rng.integers(len(vals))] for k, vals in (space or SPACE).items()}
    sl, tp = v.pop("_sl"), v.pop("_tp")
    for k in ("StopSLPoints", "LimitSLPoints", "MarketSLPoints"):
        v[k] = sl
    for k in ("StopTPPoints", "LimitTPPoints", "MarketTPPoints"):
        v[k] = tp
    trail = v.pop("_trail")
    v["InpWaitForBurstSettle"] = 0
    v["UseTrailing"] = 1 if trail == "simple" else 0
    v["InpUseTrailLayer"] = 1 if trail == "layer" else 0
    v["TrailStepPoints"] = 10
    mn = v["internalMinTrailing"]
    v["internalMaxTrailing"] = mn * 2.0
    v["internalMultiplier"] = 2.0
    v["internalOrderDistance"] = mn
    if v.pop("_market"):                      # follow-through market entries without the order-flow feed
        v["WeakFlowMarketMinScore"] = 4.5
        v["DowngradeNeutralSellMarketToStop"] = 0
    return v


def main():
    preset, n, seed, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    spread = float(sys.argv[5]) if len(sys.argv) > 5 else 12.0
    space = FOCUS if (len(sys.argv) > 6 and sys.argv[6] == "focus") else SPACE
    feed = ticks.Feed("../data", spread)
    S = sim.Sim(feed)
    p0 = sweep.base(preset)
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n):
        v = sample(rng, space)
        p = dict(p0)
        p.update(v)
        df = S.run(p)
        m = sim.metrics(df)
        m.update(oat.split_row(df))
        m.update(v)
        rows.append(m)
        if (k + 1) % 25 == 0:
            pd.DataFrame(rows).to_csv(out, index=False)
            best = max(rows, key=lambda r: (r["pf_is"] if r["n_is"] >= 300 else 0))
            print(k + 1, "best is", round(best["pf_is"], 3), "val", round(best["pf_val"], 3), "test", round(best["pf_test"], 3), "n", best["n"], flush=True)
    pd.DataFrame(rows).to_csv(out, index=False)


if __name__ == "__main__":
    main()
