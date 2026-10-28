"""EA inputs -> resolved parameter vector (DPFResolve for the XAUUSD 5m / Manual profiles)."""
import numpy as np

from engine import IDX, NP

# The 84 strategy inputs as shipped in DPFX_V10211_USD_Tester_EngineeringClock.set
# (only the ones that influence the calculation).
TESTER_SET = dict(
    presetMode="XAUUSD 5m", lockAutoProfile=True, v2Source="Auto Optimized Profile",
    useDeadExit=True, deadBarsIn=15, useBreakeven=False, beTriggerAtr=1.0,
    useEntryBuffer=True, entryBufferIn=60, useSundayBlock=True, useEntryWindow=False,
    entryWindowIn="0800-1200", useOnePerZone=True, useCooldown=True, cooldownIn=10,
    manualZoneLength=50, manualDeltaThreshold=1.5, manualMinRetestBars=1, manualMaxZoneAge=200,
    manualInvalidate=True, manualUseEmaFilter=False, manualEmaLength=100, manualZoneTrend=False,
    manualEntryMode="Normal Retest Touch",
    ExitMode="ATR", slPointsIn=5000, tpPointsIn=50000, atrLenS2=14, slAtrMultS2=0.5, tpRS2=10,
    useTrailS2=False, trailActPts=1000, trailPts=100, trailActAtr=0.01, trailDstAtr=0.01, timeStopBars=50,
    QtyMode="Risk %", fixedQtyS3=10, riskPctS3=1.0, maxQtyS3=50, qtyStepS3=0.001, capMarginS3=True, marginPctS3=1.0,
    useSessionFilter=False, nySession="0930-1600",
    useRobustHourFilter=True, useDirectionalMicroFilter=True, useV105DirectionalFilter=True, useV1010PfFilter=True,
    useV1011LossClusterPause=True, manualLossClusterCount=5, manualLossClusterPauseBars=12,
    useV1013VolCostFilter=True, minStopToCostRatio=4.0, modeledSlippageTicksOverride=0,
    useWeekendBlackout=True, useDailyBlackout=True, closeLeadMin=10, tradeOriginalDirection=False,
)


def _hhmm(s):
    a, b = s.split("-")
    return int(a[:2]) * 60 + int(a[2:]), int(b[:2]) * 60 + int(b[2:])


def resolve(inputs, symbol="XAUUSD", tf=5, initial_capital=10000.0, mintick=None,
            point_value=1.0, extra_slip=0.0, comm_pct=0.0, fill_close=True):
    c = dict(TESTER_SET); c.update(inputs)
    is_xau = "XAU" in symbol.upper()
    auto = c["presetMode"] == "Auto"
    preset_xau = c["presetMode"] == "XAUUSD 5m" or (auto and is_xau and tf == 5)
    using_fx = preset_xau  # other presets are not usable on these two symbols
    use_profile = using_fx and (c["lockAutoProfile"] or c["v2Source"] == "Auto Optimized Profile")
    P = np.zeros(NP)
    def s(k, v): P[IDX[k]] = float(v)
    s("zone_len", 50 if using_fx else c["manualZoneLength"])
    s("delta_thr", 1.5 if using_fx else c["manualDeltaThreshold"])
    s("ema_len", 100 if using_fx else c["manualEmaLength"])
    s("atr_len", c["atrLenS2"])
    s("use_ema", c["manualUseEmaFilter"])
    s("zone_trend", c["manualZoneTrend"] if c["presetMode"] == "Manual" else False)
    s("invalidate", c["manualInvalidate"])
    s("min_retest", c["manualMinRetestBars"]); s("max_age", c["manualMaxZoneAge"])
    s("entry_close_beyond", (not using_fx) and c["manualEntryMode"] == "Close Beyond Key Zone")
    s("exit_atr", c["ExitMode"] == "ATR")
    s("sl_pts", c["slPointsIn"]); s("tp_pts", c["tpPointsIn"]); s("sl_atr", c["slAtrMultS2"]); s("tp_r", c["tpRS2"])
    s("use_trail", c["useTrailS2"]); s("trail_act_pts", c["trailActPts"]); s("trail_pts", c["trailPts"])
    s("trail_act_atr", c["trailActAtr"]); s("trail_dst_atr", c["trailDstAtr"]); s("time_stop", c["timeStopBars"])
    s("dead_on", (not preset_xau) if use_profile else c["useDeadExit"])
    s("dead_bars", 15 if use_profile else c["deadBarsIn"])
    s("be_on", False if use_profile else c["useBreakeven"]); s("be_trig", 1.0 if use_profile else c["beTriggerAtr"])
    s("buffer_on", True if use_profile else c["useEntryBuffer"]); s("buffer_min", 60 if use_profile else c["entryBufferIn"])
    s("sunday_on", preset_xau if use_profile else c["useSundayBlock"])
    s("window_on", False if use_profile else c["useEntryWindow"])
    ws, we = _hhmm("0800-1200" if use_profile else c["entryWindowIn"]); s("win_start", ws); s("win_end", we)
    s("one_per_zone", True if use_profile else c["useOnePerZone"])
    s("cooldown_on", True if use_profile else c["useCooldown"]); s("cooldown_bars", 10 if use_profile else c["cooldownIn"])
    s("session_on", c["useSessionFilter"]); ss, se = _hhmm(c["nySession"]); s("ses_start", ss); s("ses_end", se)
    s("preset_xau", preset_xau)
    s("robust_hour", c["useRobustHourFilter"]); s("micro", c["useDirectionalMicroFilter"])
    s("v105", c["useV105DirectionalFilter"]); s("v1010", c["useV1010PfFilter"])
    s("loss_on", c["useV1011LossClusterPause"])
    s("loss_count", 5 if preset_xau else c["manualLossClusterCount"])
    s("loss_pause", 12 if preset_xau else c["manualLossClusterPauseBars"])
    s("cost_on", c["useV1013VolCostFilter"] and preset_xau); s("min_stop_cost", c["minStopToCostRatio"])
    s("slip_ticks", c["modeledSlippageTicksOverride"] if c["modeledSlippageTicksOverride"] > 0 else 75)
    s("mintick", mintick if mintick else (0.001 if is_xau else 0.01))
    s("weekend_on", c["useWeekendBlackout"]); s("daily_on", c["useDailyBlackout"]); s("close_lead", c["closeLeadMin"])
    s("trade_original", c["tradeOriginalDirection"])
    s("qty_risk", c["QtyMode"] == "Risk %"); s("fixed_qty", c["fixedQtyS3"]); s("risk_pct", c["riskPctS3"])
    s("max_qty", c["maxQtyS3"]); s("qty_step", c["qtyStepS3"]); s("cap_margin", c["capMarginS3"]); s("margin_pct", c["marginPctS3"])
    s("initial_capital", initial_capital); s("point_value", point_value); s("extra_slip", extra_slip); s("comm_pct", comm_pct)
    s("fill_close", fill_close)
    return P
