"""Write MT5 .set presets (UTF-16LE, like the shipped Tester preset) for a calibrated config."""
import os

from params import TESTER_SET

ENUMS = {
    "presetMode": ["Auto", "AUDJPY 2m", "EURGBP 3m", "USDCAD 5m", "XAGUSD 5m", "XAUUSD 5m", "NAS100 5m", "Manual"],
    "v2Source": ["Auto Optimized Profile", "Manual V2 Toggles"],
    "manualEntryMode": ["Normal Retest Touch", "Close Beyond Key Zone"],
    "ExitMode": ["Points", "ATR"],
    "QtyMode": ["Fixed", "Risk %"],
}
# full input order of the shipped preset, with the shipped values for everything we do not touch
ORDER = """presetMode v2Source lockAutoProfile useV106GrowthSlTp useV1021NasAdaptiveDead nasAdaptiveRunupAtr
limitOneDecisionPerBar limitOneFlatExitPerBar appendLiveSafeId appendExitReason useDeadExit deadBarsIn useBreakeven
beTriggerAtr useEntryBuffer entryBufferIn useSundayBlock useEntryWindow entryWindowIn useOnePerZone useCooldown cooldownIn
manualShowZones manualZoneLength manualDeltaThreshold manualMinRetestBars manualMaxZoneAge manualInvalidate
manualUseEmaFilter manualEmaLength manualZoneTrend manualEntryMode ExitMode slPointsIn tpPointsIn atrLenS2 slAtrMultS2
tpRS2 useTrailS2 trailActPts trailPts trailActAtr trailDstAtr timeStopBars QtyMode fixedQtyS3 riskPctS3 maxQtyS3 qtyStepS3
capMarginS3 marginPctS3 useSessionFilter nySession useRobustHourFilter useDirectionalMicroFilter useV105DirectionalFilter
useV1010PfFilter useV1011LossClusterPause manualLossClusterCount manualLossClusterPauseBars useV1013VolCostFilter
minStopToCostRatio modeledSlippageTicksOverride useWeekendBlackout useDailyBlackout closeLeadMin webhookPointSizeInput
useLotInAlert mt4Balance mt4RiskPct lotStep minLot maxLot contractOverride quoteUsd demandColor demandKeyColor supplyColor
supplyKeyColor buySignalColor sellSignalColor showOriginalSignals showRawActiveSignals tradeOriginalDirection Execution
EvaluateEveryTick EvaluateAfterFills ServerUtcOffsetMinutes ExchangeClock ReferenceTickSize ReferencePointValue WarmupBars
MagicNumber MaxDeviationPoints RecoverySession""".split()
EXTRA = dict(
    useV106GrowthSlTp=True, useV1021NasAdaptiveDead=True, nasAdaptiveRunupAtr=2.0, limitOneDecisionPerBar=True,
    limitOneFlatExitPerBar=True, appendLiveSafeId=False, appendExitReason=False, manualShowZones=True,
    webhookPointSizeInput=0.0, useLotInAlert=True, mt4Balance=10000.0, mt4RiskPct=1.0, lotStep=0.01, minLot=0.01,
    maxLot=2.0, contractOverride=0.0, quoteUsd=1.0, demandColor=8493320, demandKeyColor=8493320, supplyColor=4536050,
    supplyKeyColor=4536050, buySignalColor=8493320, sellSignalColor=4536050, showOriginalSignals=False,
    showRawActiveSignals=False, Execution=1, EvaluateEveryTick=True, EvaluateAfterFills=True, ServerUtcOffsetMinutes=0,
    ExchangeClock=1, ReferenceTickSize=0.001, ReferencePointValue=1, WarmupBars=5000, MagicNumber=102110202610260 + 2,
    MaxDeviationPoints=10, RecoverySession="DPFX_CALIB_RUN01",
)


def fmt(k, v):
    if k in ENUMS:
        return str(ENUMS[k].index(v))
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v) if v != int(v) else f"{v:.1f}"
    return str(v)


def write_set(path, cfg, symbol, note=""):  # note kept for API compatibility; .set files carry no comments
    full = dict(TESTER_SET); full.update(EXTRA); full.update(cfg)
    if symbol == "BTCUSD":
        full["ReferenceTickSize"] = 0.01
        full["contractOverride"] = 1.0
    full["RecoverySession"] = "DPFX_CALIB_" + os.path.splitext(os.path.basename(path))[0][:40]
    lines = [f"{k}={fmt(k, full[k])}" for k in ORDER]
    with open(path, "wb") as f:
        f.write(b"\xff\xfe" + ("\r\n".join(lines) + "\r\n").encode("utf-16-le"))
