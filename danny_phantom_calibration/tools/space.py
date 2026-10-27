"""Search space over the EA's numeric / boolean inputs."""
import random

COMMON = dict(
    atrLenS2=[7, 10, 14, 20, 30, 50],
    slAtrMultS2=[0.3, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0],
    tpRS2=[0, 1.0, 1.5, 2.0, 3.0, 4.1667, 6.0, 8.0, 10.0, 15.0],
    useTrailS2=[False, False, True],
    trailActAtr=[0.5, 1.0, 2.0, 3.0, 4.0],
    trailDstAtr=[0.2, 0.5, 1.0, 1.5, 2.0],
    timeStopBars=[0, 10, 20, 30, 50, 100, 200],
    useRobustHourFilter=[True, False],
    useDirectionalMicroFilter=[True, False],
    useV105DirectionalFilter=[True, False],
    useV1010PfFilter=[True, False],
    useV1011LossClusterPause=[True, False],
    manualLossClusterCount=[3, 5, 8],
    manualLossClusterPauseBars=[6, 12, 24],
    useV1013VolCostFilter=[True, False],
    minStopToCostRatio=[2.0, 4.0, 6.0, 10.0],
    useSessionFilter=[False, False, True],
    nySession=["0930-1600", "0300-1200", "0800-1200", "0200-1700"],
    useWeekendBlackout=[True, False],
    useDailyBlackout=[True, False],
    tradeOriginalDirection=[False, True],
    manualUseEmaFilter=[False, True],
    manualInvalidate=[True, False],
    manualMinRetestBars=[1, 1, 2, 3, 5],
    manualMaxZoneAge=[25, 50, 100, 200, 400],
)
MANUAL = dict(
    manualZoneLength=[20, 30, 40, 50, 75, 100, 150],
    manualDeltaThreshold=[1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0],
    manualEmaLength=[20, 50, 100, 200],
    manualZoneTrend=[False, True],
    manualEntryMode=["Normal Retest Touch", "Close Beyond Key Zone"],
    useDeadExit=[True, False],
    deadBarsIn=[5, 10, 15, 20, 30],
    useBreakeven=[False, True],
    beTriggerAtr=[0.5, 1.0, 1.5, 2.0],
    useEntryBuffer=[True, False],
    useSundayBlock=[True, False],
    useOnePerZone=[True, False],
    useCooldown=[True, False],
    cooldownIn=[3, 5, 10, 20],
    useEntryWindow=[False, False, False, True],
    entryWindowIn=["0800-1200", "0300-1200", "0800-1700", "1800-0200", "0200-1000"],
)
PRESETS = ["XAUUSD 5m", "Manual"]


def sample(rng: random.Random, preset=None):
    cfg = {"presetMode": preset or rng.choice(PRESETS)}
    for k, v in COMMON.items():
        cfg[k] = rng.choice(v)
    if cfg["presetMode"] == "Manual":
        for k, v in MANUAL.items():
            cfg[k] = rng.choice(v)
    return cfg


def neighbours(cfg):
    """One-step moves for the local refinement stage."""
    out = []
    space = dict(COMMON)
    if cfg["presetMode"] == "Manual":
        space.update(MANUAL)
    for k, vals in space.items():
        vals = sorted(set(vals), key=lambda x: (str(type(x)), x))
        if k not in cfg:
            continue
        for v in vals:
            if v != cfg[k]:
                c = dict(cfg); c[k] = v; out.append((k, c))
    return out
