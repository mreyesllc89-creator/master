"""One input at a time: how does the profit factor respond to each trade-affecting input?

usage: python -I oat.py <preset name> <out csv> [spread_pts] [main|micro]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # scripts are run with python -I

import numpy as np
import pandas as pd

import engine
import params
import sim
import sweep
import ticks

GRID = {
    # speed alert
    "MaxTrailingMultiplier": [3, 4, 5, 6, 7.5, 9, 11, 13, 16, 20, 25],
    "MinSpeedAlertPoints": [20, 37, 60, 80, 100, 120, 150, 200, 250, 300],
    "SpeedLookbackSeconds": [2, 3, 5, 7, 10, 15, 20, 30],
    "SpeedAlertHoldSeconds": [11, 13, 15, 20, 30, 45, 60],
    "InpUseHighBurstGate": [0, 1],
    "InpBurstThresholdPts": [40, 80, 145, 172, 250],
    # direction score
    "MinDirectionScore": [2.0, 2.5, 3.0, 4.0, 4.5],
    "MinScoreEdge": [0.5, 1.0, 1.5, 2.5, 4.0],
    "MinCandleBodyPoints": [0, 10, 21, 40, 60, 80, 100, 150],
    "MicroBreakLookbackSeconds": [2, 5, 10, 20, 30, 60],
    "MicroBreakBufferPoints": [0, 3, 6, 10, 20],
    "MaxSpreadPoints": [12, 14, 16, 20, 31, 60],
    # routing
    "EntryRouterMode": [0, 1, 2],
    "StopEntryDistancePoints": [5, 10, 20, 35, 50, 70, 100],
    "LimitRetestDistancePoints": [10, 20, 35, 50, 70, 100, 150],
    "PendingExpirySeconds": [2, 3, 5, 8, 12, 20, 45, 120],
    "StopSLPoints": [40, 60, 75, 90, 110, 130, 160, 200, 300],
    "StopTPPoints": [60, 80, 100, 130, 180, 250, 400, 1000],
    "LimitSLPoints": [40, 60, 90, 130, 200],
    "LimitTPPoints": [60, 100, 160, 250, 400],
    "MarketFollow21Points": [10, 21, 40, 70, 110],
    "MarketFollow37Points": [20, 37, 60, 100],
    "DowngradeNeutralSellMarketToStop": [0, 1],
    "WeakFlowMarketMinScore": [4.5, 5.0],
    "InpUseEntryHold": [0, 1],
    "InpEntryHoldMs": [250, 500, 800, 1100, 1500, 2000, 3000],
    "InpEntryHoldMinFavPoints": [-20, 0, 5, 10, 20, 35],
    "InpUsePrior60Filter": [0, 1],
    "InpUse1000msHold": [0, 1],
    "ScenarioIndependentPerformance": [0, 1],
    # lockout
    "UseDefensiveCloseLockout": [0, 1],
    "DefensiveLockoutCloseCount": [1, 2, 3, 5],
    "DefensiveLockoutSeconds": [30, 90, 300, 900],
    # post entry validation / exits
    "UsePostEntryValidation": [0, 1],
    "CloseOnRetestFailure": [0, 1],
    "RetestFailPoints": [5, 10, 20, 35],
    "RetestFailedEarlyLossPoints": [10, 15, 25, 40],
    "RetestFailConfirmSeconds": [0, 1, 2, 4],
    "OppositePressurePoints": [10, 21, 35, 50],
    "UseV40ExecutionShield": [0, 1],
    "V40RetestExecutionShieldLossPoints": [10, 21, 35],
    "FLXQSellStopPressureDangerClose": [0, 1],
    "UseSpeedProfitExit": [0, 1],
    "SpeedProfitExitPoints": [50, 70, 85, 100, 120, 140, 170],
    "RequireProfitSideSpeed": [0, 1],
    "UsePredictiveSpeedProfitExit": [0, 1],
    "PredictiveExitMinProfitPoints": [70, 100, 370],
    # trailing
    "UseTrailing": [0, 1],
    "TrailStartPoints": [69, 80, 100, 130, 270],
    "TrailBehindPoints": [20, 30, 40, 60, 80],
    "TrailStepPoints": [1, 5, 10, 20],
    "InpWaitForBurstSettle": [0, 1],
    "InpUseTrailLayer": [0, 1],
    # continuation filter
    "InpCPMode": [0, 2],
    "InpCPMinTickRate60": [0, 2.0, 3.0, 3.8, 5.0, 6.5, 8.0],
    "InpCPMaxMedianGapMs": [0, 100, 150, 215, 300],
    "InpCPRequireCostCoverage": [0, 1],
    "InpCPGrossFloor": [16, 40, 80, 150, 250, 400],
    "InpCPMinRange60": [0, 50, 100, 200, 400],
    "InpCPMinRange300": [0, 200, 400, 800],
    "InpCPCancelBadPendings": [0, 1],
    # FlashGold gate
    "UseFlashGoldDirectionFilter": [0, 1],
    "FG_InpBandAtr": [0, 0.1, 0.25, 0.5, 1.0, 2.0],
    "FG_InpAgainst": [0, 1],
    "FG_InpBurstAtr": [0.25, 0.5, 1.0, 1.5, 2.5],
    "FG_InpEntryDistAtr": [0, 0.25, 0.5, 1.0],
    "FG_InpMinAligned": [0, 1, 2, 3],
    "FG_InpUseZones": [0, 1],
    "FG_InpLast": [0, 1, 3],
    "FG_InpMinutes": [5, 15, 60],
    "FG_InpSeconds": [5, 30, 120],
    "FG_InpTf": [1, 5, 15, 16385],
    "FG_InpParentTf": [5, 15, 16385],
    # what-if (not inputs)
    "X_ExitGatePips": [0, 2, 4, 6.8, 10],
}


# FlashGold inputs around a micro preset (quote-bucket filter bars)
GRID_MICRO = {
    "UseFlashGoldDirectionFilter": [0, 1],
    "FG_IntervalMs": [100, 250, 500, 1000, 2000, 5000, 15000, 60000],
    "FG_MicroWarmupBars": [20, 100, 400, 1500],
    "FG_MicroMaxGapMs": [5000, 60000, 300000],
    "FG_InpLast": [0, 1, 2, 3, 4],
    "FG_InpSeconds": [1, 2, 5, 15, 60],
    "FG_InpMilliseconds": [100, 250, 500, 2000],
    "FG_InpMinutes": [1, 5, 60],
    "FG_InpBars": [1, 5, 30],
    "FG_InpBandAtr": [0, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0],
    "FG_InpAgainst": [0, 1],
    "FG_InpDistUnit": [0, 1],
    "FG_InpBurstAtr": [0.1, 0.25, 0.5, 1.0, 2.0, 4.0],
    "FG_InpEntryDistAtr": [0, 0.25, 0.5, 1.0, 2.0],
    "FG_InpSpreadPts": [0, 12, 25, 50],
    "FG_InpHoldBars": [0, 1, 3],
    "FG_InpUseZones": [0, 1],
    "FG_InpMinAligned": [0, 1, 2, 3],
    "FG_InpFlatParent": [0, 1],
    "FG_InpAnyCombo": [0, 1],
    "FG_InpUseDrift": [0, 1],
    "FG_InpDriftBars": [5, 20, 60, 300],
    "FG_InpParentTf": [1, 5, 15, 16385],
    "FG_InpRsiLen": [7, 14, 28],
    "FG_InpFastLen": [2, 5],
    "FG_InpAllowBuy": [0, 1],
    "FG_InpAllowSell": [0, 1],
    "X_MicroRestart": [0, 1],
}

SPLITS = {"is": ("2025-11-01", "2026-03-01"), "val": ("2026-03-01", "2026-06-01"), "test": ("2026-06-01", "2027-01-01")}


def split_row(df):
    """Profit factor, trades and average points per split (calibration / validation / hold-out)."""
    out = {}
    for name, (a, b) in SPLITS.items():
        lo = pd.Timestamp(a).value // 10**6
        hi = pd.Timestamp(b).value // 10**6
        m = sim.metrics(df[(df.entry_ms >= lo) & (df.entry_ms < hi)])
        out[f"pf_{name}"] = m["pf"]
        out[f"n_{name}"] = m["n"]
        out[f"avg_{name}"] = m["avg"]
    return out


def main():
    preset = sys.argv[1]
    out = sys.argv[2]
    spread = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0
    grid = GRID_MICRO if (len(sys.argv) > 4 and sys.argv[4] == "micro") else GRID
    feed = ticks.Feed("../data", spread)
    S = sim.Sim(feed)
    p0 = sweep.base(preset)
    df = S.run(p0)
    b = sim.metrics(df)
    print("base", {k: round(v, 3) for k, v in b.items()}, {k: round(v, 3) for k, v in split_row(df).items()}, flush=True)
    rows = []
    for name, values in grid.items():
        for v in values:
            p = dict(p0)
            p[name] = v
            df = S.run(p)
            m = sim.metrics(df)
            m.update(split_row(df))
            m.update(input=name, value=v, is_base=float(p0[name]) == float(v))
            rows.append(m)
        cur = pd.DataFrame([r for r in rows if r["input"] == name])
        print(name, " | ".join(f"{r.value:g}{'*' if r.is_base else ''}: {r.pf:.2f} ({r.pf_is:.2f}/{r.pf_val:.2f}/{r.pf_test:.2f}) n{int(r.n)}"
                               for r in cur.itertuples()), flush=True)
        pd.DataFrame(rows).to_csv(out, index=False)


if __name__ == "__main__":
    main()
