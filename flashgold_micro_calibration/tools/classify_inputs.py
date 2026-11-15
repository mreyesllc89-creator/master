"""Every EA input with what it does in a Strategy Tester run and how far the profit factor moved when
it was varied. usage: python -I classify_inputs.py <results_dir>   -> inputs_classification.csv"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

import engine
import flashgold
import params

FLOW = {"UseOrderFlow", "FlowGVPrefix", "MaxFlowAgeMs", "MinFlowImbalance", "FlowComponentScore", "BlockStrongFlowAgainst",
        "FlowDisagreeMakesDefenseImmediate", "UseStopFlowDisagreeDangerClose", "StopFlowDisagreeDangerLossPoints",
        "StopFlowDisagreeDangerMinHoldMs", "StopFlowDisagreeDangerNeedsOppositePressure", "FOLMFlowDisagreeDangerLossPoints"}
SIZING = {"FixedLot", "BodyOnlyLotFactor", "ContinuationStopLotFactor", "FollowThroughMarketLotFactor", "ExhaustionLimitLotFactor",
          "InpUseTrueStopRiskSizing", "InpCalibrationRiskPercent", "InpUseSplitStopFloor"}
NOT_REPLAYED = {"InpSpeedThresholdMode": "PERCENTILE threshold mode (FIXED in every preset)", "InpSpeedPercentile": "PERCENTILE mode only",
                "InpSpeedWindowSamples": "PERCENTILE mode only", "InpBurstThresholdMode": "PERCENTILE mode only",
                "InpBurstPercentile": "PERCENTILE mode only", "InpBurstWindowSamples": "PERCENTILE mode only",
                "CandleIndexToCheck": "0 (forming candle) in every preset", "SlippagePoints": "deviation of market orders; the replay fills at the quote",
                "SpeedProfitExitRetrySeconds": "close retry after a rejected close", "SpeedProfitExitMaxRetries": "close retry after a rejected close",
                "PreSpeedLogCooldownSeconds": "log throttle", "CloseDuplicateMemoryMs": "duplicate close guard",
                "RetestFailedEarlyBypassHold": "replayed", "FG_InpCheck": "Tick mode in every preset", "FG_InpTickSize": "compatibility check",
                "FG_InpMaxBars": "legacy", "FG_InpWarmup": "legacy", "InpCPMaxSilenceMs": "always satisfied in the tester (simulated clock)",
                "TradingEnabled": "must be true for the tester to trade", "MagicNumber": "identifier",
                "FG_InpHtfClosed": "replayed (native mode)",
                "internalMultiplier": "consistency check only (internalMaxTrailing must equal internalMinTrailing x internalMultiplier)",
                "InpAIHardGateEnabled": "recorded only, the code says it has no execution authority",
                "InpAIRiskAdjustEnabled": "recorded only, the code says it has no execution authority"}


def main(res):
    replayed = {n for n in engine.NAMES if not n.startswith("X_")}
    fg_series = {"FG_Resolution", "FG_IntervalMs", "FG_MicroMaxBars", "FG_MicroMaxGapMs", "FG_InpTf", "FG_InpLvMode", "FG_InpSpreadPts",
                 "FG_InpEntryDistPts", "FG_InpHoldBars", "FG_InpHoldFavPts", "FG_InpOnePerBar", "FG_InpDistUnit", "FG_InpBurstAtr",
                 "FG_InpEntryDistAtr", "FG_InpHoldFavAtr", "FG_InpBurstPts", "FG_InpUseBurst", "FG_InpAnyCombo", "FG_InpDriftBars",
                 "FG_InpUseDrift", "FG_InpUseZones", "FG_InpParentTf", "FG_InpRsiLen", "FG_InpFastLen", "FG_InpMinAligned",
                 "FG_InpFlatParent", "FG_InpIgnoreNa", "FG_InpHtfClosed"} | {f"FG_InpUseZ{z}" for z in range(1, 7)} | {f"FG_InpZTf{z}" for z in range(1, 7)}
    oat = {}
    for name in ("oat_native_all.csv", "oat_micro1s_fg.csv"):
        path = os.path.join(res, name)
        if os.path.exists(path):
            o = pd.read_csv(path)
            o = o[o.n >= 2000]
            for k, g in o.groupby("input"):
                oat.setdefault(k, (round(g.pf.min(), 3), round(g.pf.max(), 3), ", ".join(f"{v:g}" for v in g.value)))
    rows = []
    for r in params.SPEC:
        k = r["name"]
        if r["kind"] == "string" or r["kind"] == "color":
            cls = "label, file name, comment or colour"
        elif k in FLOW:
            cls = "order-flow feed: no effect in the Strategy Tester (the feed's global variables do not exist there)"
        elif k in SIZING:
            cls = "position sizing: does not change the profit factor at the fixed 0.01 lot"
        elif k in replayed or k in fg_series:
            cls = "replayed"
        elif k in NOT_REPLAYED:
            cls = "not replayed: " + NOT_REPLAYED[k]
        else:
            cls = "telemetry, logging, visuals or shadow scorecards: no effect on orders"
        lo, hi, vals = oat.get(k, ("", "", ""))
        rows.append(dict(input=k, section=r["section"], type=r["type"], source_default=r["default"], tester_effect=cls,
                         pf_min=lo, pf_max=hi, values_tested=vals))
    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(res, "inputs_classification.csv"), index=False)
    print(d.tester_effect.str.split(":").str[0].value_counts().to_string())


if __name__ == "__main__":
    main(sys.argv[1])
