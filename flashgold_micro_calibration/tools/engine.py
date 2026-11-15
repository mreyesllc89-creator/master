"""Tick replay of SpeedAlert_FlashGold_Micro.mq5 v1.501 (the "SpeedAlert DirectionRouter" EA).

Ported function by function from the MQL5 source; names in comments are the MQL functions.
One call replays one chunk of ticks (a trading week) with one set of inputs and returns the trades.

Order of work per tick, as in OnTick():
  broker side   stop loss / take profit of open positions, then pending order triggers
  CP_RecheckPendings      continuation filter may cancel resting orders (4 checks per second)
  UpdateSpeedAlert        |mid move over SpeedLookbackSeconds| >= max(MinSpeedAlertPoints, spread * MaxTrailingMultiplier)
  ManagePendingExpiry     EA-side expiry in whole seconds
  ManagePosition          exit gate (6.8 pips), speed profit exit, post-entry validation, post-fill hold, trailing
  entry                   defensive lockout, entry hold, direction score, router, FlashGold gate, 60 minute drift,
                          burst gate, scenario caps, order placement through the continuation filter

Execution model: market orders and EA closes fill at the current bid/ask. Stop orders and stop
losses fill at the market when touched (gaps slip), except that a touch within X_FillSnapPts of the
level fills at the level (the Dukascopy top of book flickers by several points between ticks; the
author's real fills are exact 74% of the time). With X_LimitAtMarket = 1 limit orders and take
profits fill at the market price when touched (price improvement, as on the author's "market
execution" ECN symbol); with 0 they fill at their own price. A stop loss that is not filled at its
level slips X_StopLossSlipMult times as far as the quote shows (the author's 1,363 real stop-loss
fills slip about 1.5 times as far as the Dukascopy quotes do; stop entries need no such factor).
X_SlipPts adds a fixed adverse slip to
every market, stop and stop-loss fill; X_CommissionPts is charged per round trip. X_LatencyMs is the
round trip of an order the EA sends: a market entry or a market close fills at the first quote at
least that much later, a pending order starts resting that much later and is refused if the market
has passed its price by then. Server-side events (stop loss, take profit, pending triggers) have no
latency. 0 = the Strategy Tester without a delay.

Not replayed (see REPORT.md): the order-flow feed (global variables written by a separate program do
not exist in the Strategy Tester either, so flow is neutral exactly as in a tester run), PERCENTILE
threshold modes, CandleIndexToCheck other than 0, frozen-order retry paths, all telemetry.
"""
import numpy as np
from numba import njit

from flashgold import gate as fg_gate

PT = 0.01
PIP = 0.10                      # TrailingPipSizePrice() for gold
BIG = 1.0e9

NAMES = [
    # general
    "EntryRouterMode", "MaxOpenPositions", "MaxPendingOrders", "ScenarioIndependentPerformance",
    "MaxOpenPositionsPerScenario", "MaxPendingOrdersPerScenario", "CancelOnlySameScenarioPendings",
    "CancelOldPendings", "PendingExpirySeconds", "UseDefensiveCloseLockout", "DefensiveLockoutCloseCount",
    "DefensiveLockoutSeconds", "DefensiveLockoutCancelPendings",
    # speed alert
    "MaxTrailingMultiplier", "SpeedLookbackSeconds", "MinSpeedAlertPoints", "SpeedAlertHoldSeconds",
    "InpUseHighBurstGate", "InpBurstThresholdPts", "SpeedDirectionScore", "UsePreSpeedRadar",
    "PreSpeedEarlyRatio", "PreSpeedStrongRatio", "UsePreSpeedAgainstDefense", "PreSpeedAgainstDefenseMinLossPoints",
    "PreSpeedAgainstDefenseHardClose", "PreSpeedAgainstDefenseHardMaxLossPoints", "EXHLPreSpeedDangerClose",
    "EXHLPreSpeedDangerLossPoints", "EXHLPreSpeedDangerNeedsOppositePressure", "FOLMMarketDangerClose",
    "FOLMMarketDangerLossPoints", "FOLMMarketDangerNeedsOppositePressure", "FOLMMarketHardClose",
    "FOLMMarketHardMaxLossPoints", "FOLMSellMarketEarlyDangerClose", "FOLMSellMarketEarlyDangerLossPoints",
    "FOLMSellMarketEarlyDangerNeedsOppositePressure", "PreSpeedAgainstDefenseNoFollowSeconds",
    "PreSpeedAgainstDefenseNeedsOppositePressure", "PreSpeedAgainstDefenseCloseOnPreSpeed50",
    "PreSpeedAgainstDefenseCloseOnPreSpeed70", "FLXQSellStopFastPreSpeedDefense",
    "FLXQSellStopPreSpeedDefenseNoFollowSeconds", "FLXQSellStopFastPreSpeedDefenseLossPoints",
    "FLXQSellStopFastPreSpeedDefenseNeedsOppositePressure", "FLXQSellStopPressureDangerClose",
    "FLXQSellStopPressureDangerLossPoints", "PreSpeedAgainstDefenseMaxSignalAgeMs",
    # direction score
    "MinDirectionScore", "MinScoreEdge", "MinCandleBodyPoints", "CandleBodyScore", "MicroBreakLookbackSeconds",
    "MicroBreakBufferPoints", "MicroBreakScore", "MaxSpreadPoints", "SpreadStableScore",
    # flow routing switches that still matter with neutral flow
    "DowngradeNeutralSellMarketToStop", "WeakFlowMarketNeedsBodyAndMicro", "WeakFlowMarketMinScore",
    "WeakFlowMarketMinScoreEdge",
    # entry routing
    "StopEntryDistancePoints", "LimitRetestDistancePoints", "MarketFollow21Points", "MarketFollow21Seconds",
    "MarketFollow37Points", "MarketFollow37Seconds", "StopSLPoints", "StopTPPoints", "MarketSLPoints",
    "MarketTPPoints", "LimitSLPoints", "LimitTPPoints", "InpUseEntryHold", "InpEntryHoldMs",
    "InpEntryHoldMinFavPoints", "InpUsePrior60Filter", "InpUse1000msHold", "InpHoldMinFavPts",
    # post entry validation
    "UsePostEntryValidation", "OppositePressurePoints", "OppositePressureSeconds", "CloseIfNoFollowThrough",
    "ValidationSeconds", "CloseOnRetestFailure", "RetestFailPoints", "RetestFailCloseMinLossPoints",
    "RetestFailedEarlyClose", "RetestFailedEarlyLossPoints", "RetestFailedEarlyBypassHold",
    "FOLMAfterFollowRetestDangerClose", "FOLMAfterFollowRetestDangerLossPoints", "FOLMAfterFollowRetestBypassHold",
    "RetestFailConfirmSeconds", "UseEmergencyRetestCollapseClose", "RetestCollapseMinLossPoints",
    "RetestCollapseVelocityPointsPerSec", "RetestCollapseJumpPoints", "RetestCollapseLookbackMs",
    "RetestCollapseConfirmTicks", "RetestCollapseConfirmMs", "RetestCollapseHoldNormalCloseMs",
    "RetestCollapseHardMaxLossPoints", "NoFollowEarlyClose", "NoFollowEarlySeconds", "NoFollowEarlyLossPoints",
    "NoFollowEarlyNeedsOppositePressure", "NoFollowCloseMinLossPoints", "UseSpeedProfitExit",
    "SpeedProfitExitPoints", "RequireProfitSideSpeed", "UsePredictiveSpeedProfitExit",
    "PredictiveExitMinProfitPoints", "PredictiveExitMinProjectedNetPoints", "PredictiveExitLatencyMs",
    "PredictiveExitVelocityLookbackMs", "PredictiveExitVelocityMultiplier", "PredictiveExitExtraBufferPoints",
    "PredictiveExitMinRiskBufferPoints", "PredictiveExitMaxRiskBufferPoints", "BlockSpeedExitIfProjectedNegative",
    # trailing
    "UseTrailing", "TrailStartPoints", "TrailBehindPoints", "TrailStepPoints", "InpWaitForBurstSettle",
    "InpBurstSettleQuietMs", "InpBurstSettleSpeedFraction", "InpBurstSettleMaxSpeedPipsSec",
    "InpBurstSettlePullbackPips",
    # trail layer
    "InpUseTrailLayer", "internalOrderDistance", "internalMinTrailing", "internalMaxTrailing",
    "InpReferenceSpreadPts", "InpTrailOuterCapPts", "InpStopBufferPts", "InpModifyMinIntervalMs", "InpArmOnFavPts",
    "InpTrailArmFavPts", "InpArmOnCostDigested", "InpArmOnTimeMs", "InpTrailArmTimeMs", "InpCommissionPts",
    "InpExitSlipReservePts", "InpCostLockInPts",
    # v36 / v40 active closes
    "UseFOLMPreHardWarnActiveClose", "FOLMPreHardWarnActiveClosePoints", "UseV40ExecutionShield",
    "V40PreSpeedExecutionShield", "V40PreSpeedExecutionShieldLossPoints",
    "V40PreSpeedExecutionShieldNeedsPressureOrFlow", "V40FLXQSellStopPressureShield",
    "V40FLXQSellStopPressureShieldLossPoints", "V40FLXQSellStopPressureShieldNeedsPressure",
    "V40RetestExecutionShield", "V40RetestExecutionShieldLossPoints", "V40RetestExecutionShieldMinWarningAgeMs",
    "V40RetestExecutionShieldMinVelocityPointsPerSec", "V40RetestExecutionShieldMinJumpPoints",
    "V40RetestExecutionShieldNeedsPressure",
    # continuation filter
    "InpCPMode", "InpCPPriceUnit", "InpCPMinTickRate60", "InpCPMaxMedianGapMs", "InpCPMinRange60",
    "InpCPMinRange300", "InpCPRequireCostCoverage", "InpCPGrossFloor", "InpCPSlipReserve", "InpCPCommission",
    "InpCPCancelBadPendings",
    # FlashGold gate (the filter series itself is precomputed in flashgold.py)
    "UseFlashGoldDirectionFilter", "FG_Resolution", "FG_IntervalMs", "FG_MicroWarmupBars", "FG_InpLast",
    "FG_InpMinutes", "FG_InpSeconds", "FG_InpMilliseconds", "FG_InpBars", "FG_InpAllowBuy", "FG_InpAllowSell",
    "FG_InpBandAtr", "FG_InpAgainst",
    # replay-only switches (not EA inputs)
    "X_ExitGatePips",          # hard-coded 6.8 in TrailingActivationProfitReached(); 0 = no gate
    "X_SlipPts",               # extra adverse slip on market / stop / stop-loss fills
    "X_CommissionPts",         # round-trip commission in points
    "X_StopsLevelPts",         # SYMBOL_TRADE_STOPS_LEVEL
    "X_MicroRestart",          # used by flashgold.py
    "X_TradeBuys", "X_TradeSells",   # 1/1 = both sides (what-if only)
    "X_FillSnapPts",           # stop / stop-loss fills within this many points of their level fill at the level
    "X_LimitAtMarket",         # 1 = limit orders and take profits fill at the market (price improvement), 0 = at their price
    "X_LatencyMs",             # round trip of an order sent by the EA (market entry, market close, pending placement)
    "X_StopLossSlipMult",      # a stop loss filled beyond its level slips this many times the quoted distance
]
I = {n: k for k, n in enumerate(NAMES)}
for _n, _k in I.items():
    globals()["I_" + _n] = _k
NP = len(NAMES)

# RouterAction
A_BS, A_SS, A_BM, A_SM, A_BL, A_SL = 1, 2, 3, 4, 5, 6
# scenario keys (ScenarioKeyForAction)
S_FOLM, S_EXHL, S_BFNF, S_FLXQ, S_QUAL, S_BFOL, S_BFNO, S_BNO, S_BFA, S_BODY, S_CONT, S_EXH, S_OTHER = range(1, 14)
SCENARIO = {1: "FOLM", 2: "EXHL", 3: "BFNF", 4: "FLXQ", 5: "QUAL", 6: "BFOL", 7: "BFNO", 8: "BNO", 9: "BFA",
            10: "BODY", 11: "CONT", 12: "EXH", 13: "OTHER"}
ACTION = {1: "BS", 2: "SS", 3: "BM", 4: "SM", 5: "BL", 6: "SL"}
# exit reasons
(R_SL, R_TP, R_TRAIL_SL, R_LAYER_SL, R_SPEED_TARGET, R_SPEED_PREDICTIVE, R_RETEST_FAILED, R_RETEST_EARLY,
 R_RETEST_COLLAPSE, R_RETEST_HARD, R_V40_RETEST, R_FLXQ_SS, R_HOLD_KILL, R_FOLM_SM_EARLY, R_FOLM_WARN,
 R_FOLM_HARD, R_FOLM_RETEST, R_PRE_SPEED, R_NO_FOLLOW_EARLY, R_NO_FOLLOW, R_END) = range(1, 22)
REASON = {1: "SL", 2: "TP", 3: "TRAIL_SL", 4: "LAYER_SL", 5: "SA_PROFIT_EXIT", 6: "SA_PROFIT_EXIT(predictive)",
          7: "SA_RETEST_FAILED", 8: "SA_RETEST_EARLY", 9: "SA_RETEST_COLLAPSE", 10: "SA_RETEST_HARD_FLOOR",
          11: "SA_V40_RETEST_SHIELD", 12: "SA_FLXQ_SS_PRESSURE/V40", 13: "SAR_HOLD_KILL", 14: "SA_FOLM_SM_EARLY",
          15: "SA_FOLM_WARN24", 16: "SA_FOLM_MARKET_HARD", 17: "SA_FOLM_RETEST_DANGER", 18: "SA_PRE_SPEED_DEFENSE",
          19: "SA_NO_FOLLOW_EARLY", 20: "SA_NO_FOLLOW", 21: "END_OF_WEEK"}
TRADE_COLS = ["entry_ms", "exit_ms", "side", "action", "scenario", "entry", "exit", "reason", "pts", "mfe", "mae",
              "decision_ms", "requested", "released", "sl_moved", "opp_pressure", "alert_pts", "spread_pts"]
NC = len(TRADE_COLS)
MAXP = 12
MAXO = 12

# counters returned for diagnostics
(C_ALERTS, C_DECISIONS, C_SKIP_MIXED, C_SKIP_SPREAD, C_SKIP_BODY, C_FG_BLOCK, C_HOLD_ARMED, C_HOLD_FAIL,
 C_HOLD_SAME_BAR, C_PRIOR60_BLOCK, C_BURST_BLOCK, C_CAP_SKIP, C_CP_BLOCK, C_PLACED, C_EXPIRED, C_CP_CANCEL,
 C_LOCKOUT_SKIP, C_LOCKOUT_ARMED, C_FILLED, C_ALERT_EXPIRED, C_REJECTED) = range(21)
COUNTERS = ["alerts", "decisions", "skip_mixed", "skip_spread", "skip_body_against", "flashgold_block", "hold_armed",
            "hold_fail", "hold_same_bar", "prior60_block", "burst_block", "cap_skip", "continuation_block", "placed",
            "pending_expired", "continuation_cancel", "lockout_skip", "lockout_armed", "filled", "alert_expired",
            "pending_rejected_price_passed"]


@njit(cache=True, nogil=True)
def _first_at_or_after(T, i, ms):
    """FirstTickAtOrAfter(): first stored tick with time >= ms, searching back from tick i."""
    j = i
    while j > 0 and T[j - 1] >= ms:
        j -= 1
    return j


@njit(cache=True, nogil=True)
def _cp_stats(T, B, A, i, unit):
    """CP_Compute(): 60 s / 300 s tape statistics before the current second.
    Returns complete60, complete300, count60, median_gap_ms, range60, range300, median_spread."""
    cutoff = (T[i] // 1000) * 1000
    e = np.searchsorted(T[: i + 1], cutoff)                     # ticks [.., e) are before the cutoff
    j360 = np.searchsorted(T[: i + 1], cutoff - 360000)
    if e <= j360:
        return False, False, 0, -1.0, -1.0, -1.0, -1.0
    min_source = T[j360]
    complete60 = min_source <= cutoff - 60000
    complete300 = min_source <= cutoff - 300000
    j300 = np.searchsorted(T[: i + 1], cutoff - 300000)
    j60 = np.searchsorted(T[: i + 1], cutoff - 60000)
    count60 = e - j60
    lo3 = 1e18
    hi3 = -1e18
    for k in range(j300, e):
        m = (B[k] + A[k]) * 0.5
        if m < lo3:
            lo3 = m
        if m > hi3:
            hi3 = m
    range300 = (hi3 - lo3) / unit if e > j300 else -1.0
    if count60 <= 0:
        return complete60, complete300, 0, -1.0, -1.0, range300, -1.0
    lo = 1e18
    hi = -1e18
    spreads = np.empty(count60)
    for k in range(j60, e):
        m = (B[k] + A[k]) * 0.5
        if m < lo:
            lo = m
        if m > hi:
            hi = m
        spreads[k - j60] = (A[k] - B[k]) / unit
    med_spread = np.median(spreads)
    med_gap = -1.0
    if count60 >= 2:
        gaps = np.empty(count60 - 1)
        for k in range(j60 + 1, e):
            gaps[k - j60 - 1] = T[k] - T[k - 1]
        med_gap = np.median(gaps)
    return complete60, complete300, count60, med_gap, (hi - lo) / unit, range300, med_spread


@njit(cache=True, nogil=True)
def run_chunk(T, B, A, P, idxL, cand, ep_start,
              fg_time, fg_end, fg_li, fg_aat, fg_abar, fg_aprice, fg_adir, fg_aatr,
              ext_i, ext_side, ext_act, ext_scn, ext_entry, ext_sl, ext_tp, ext_id,
              out, cnt):
    """Replay one chunk. T ms, B bid, A ask; P inputs; idxL[i] = FirstTickAtOrAfter(t - lookback);
    cand = indices where the alert condition holds; ep_start[i] = time of the first tick after the
    last quote gap > 1 s (burst epoch). Trades are written to `out`; returns their count.

    ext_* = externally supplied fills (used to replay real trades with other exit inputs): at tick
    ext_i[k] a position opens at ext_entry[k] with the given stop and target. Their trades carry
    ext_id in the decision_ms column. Pass empty arrays for a normal run."""
    n = len(T)
    nt = 0
    maxt = out.shape[0]

    # ---- inputs -------------------------------------------------------------------------------
    router = int(P[I_EntryRouterMode])
    hold_ms_alert = P[I_SpeedAlertHoldSeconds] * 1000.0
    exit_gate_pts = P[I_X_ExitGatePips] * PIP / PT
    slip = P[I_X_SlipPts] * PT
    commission = P[I_X_CommissionPts]
    stops_level = P[I_X_StopsLevelPts]
    snap = P[I_X_FillSnapPts] * PT + PT * 1e-6
    slmult = P[I_X_StopLossSlipMult]
    latency = int(P[I_X_LatencyMs])
    lim_mkt = P[I_X_LimitAtMarket] > 0.5
    min_dist = max(stops_level * PT, PT)
    fg_on = P[I_UseFlashGoldDirectionFilter] > 0.5
    fg_micro = P[I_FG_Resolution] > 0.5
    fg_interval = int(P[I_FG_IntervalMs])
    fg_warm = int(P[I_FG_MicroWarmupBars])
    fg_last = int(P[I_FG_InpLast])
    fg_wm = fg_last if fg_last <= 2 else 0
    fg_dur = 0
    if fg_last == 3:
        fg_dur = int(P[I_FG_InpSeconds]) * 1000
    elif fg_last == 4:
        fg_dur = int(P[I_FG_InpMilliseconds])
    nfg = len(fg_time)
    cp_on = P[I_InpCPMode] > 0.5
    cp_unit = P[I_InpCPPriceUnit]
    cost_digested = P[I_InpCommissionPts] + P[I_InpExitSlipReservePts] + P[I_InpCostLockInPts]
    min_legal = stops_level + P[I_InpStopBufferPts]

    # ---- EA state -----------------------------------------------------------------------------
    speed_active = False
    speed_start_ms = 0
    speed_start_mid = 0.0
    speed_dir = 0
    speed_pts = 0.0
    speed_idx = 0
    al_mfe = 0.0
    al_mae = 0.0
    al_last = 0
    pre_ms = 0
    pre_dir = 0
    pre_level = 0
    hold_armed = False
    hold_sig_ms = 0
    hold_sig_mid = 0.0
    hold_action = 0
    hold_scn = 0
    hold_op = False
    hold_failed_bar = -1
    streak = 0
    lockout_until = 0
    cp_sec = -1
    cp_c60 = False
    cp_c300 = False
    cp_n60 = 0
    cp_gap = -1.0
    cp_r60 = -1.0
    cp_r300 = -1.0
    cp_msp = -1.0
    cp_pending_check = -1
    bar_min = -1
    bar_i = -1
    bar_open = 0.0
    bar_hi = 0.0
    bar_lo = 0.0

    # positions
    p_on = np.zeros(MAXP, np.bool_)
    p_side = np.zeros(MAXP, np.int64)
    p_entry = np.zeros(MAXP)
    p_sl = np.zeros(MAXP)
    p_tp = np.zeros(MAXP)
    p_fill = np.zeros(MAXP, np.int64)
    p_scn = np.zeros(MAXP, np.int64)
    p_act = np.zeros(MAXP, np.int64)
    p_slmod = np.zeros(MAXP, np.int64)
    p_dec = np.zeros(MAXP, np.int64)
    p_req = np.zeros(MAXP)
    p_op = np.zeros(MAXP, np.bool_)
    p_alert = np.zeros(MAXP)
    p_spread = np.zeros(MAXP)
    p_trk = np.zeros(MAXP, np.bool_)
    p_trk_ms = np.zeros(MAXP, np.int64)
    p_mfe = np.zeros(MAXP)
    p_mae = np.zeros(MAXP)
    p_h21 = np.zeros(MAXP, np.bool_)
    p_h37 = np.zeros(MAXP, np.bool_)
    p_rheld = np.zeros(MAXP, np.bool_)
    p_rfail = np.zeros(MAXP, np.bool_)
    p_rfail_ms = np.zeros(MAXP, np.int64)
    p_rfail_fav = np.zeros(MAXP)
    p_coll_ms = np.zeros(MAXP, np.int64)
    p_coll_ticks = np.zeros(MAXP, np.int64)
    p_lastfav = np.zeros(MAXP)
    p_lastfav_ms = np.zeros(MAXP, np.int64)
    p_rel = np.zeros(MAXP, np.bool_)
    p_se_pend = np.zeros(MAXP, np.bool_)
    p_se_last = np.zeros(MAXP, np.int64)
    p_se_n = np.zeros(MAXP, np.int64)
    p_tl_init = np.zeros(MAXP, np.bool_)
    p_tl_peak = np.zeros(MAXP)
    p_tl_armed = np.zeros(MAXP, np.bool_)
    p_tl_eval = np.zeros(MAXP, np.int64)
    p_hold_eval = np.zeros(MAXP, np.bool_)
    p_bs_init = np.zeros(MAXP, np.bool_)
    p_bs_first = np.zeros(MAXP, np.int64)
    p_bs_last = np.zeros(MAXP, np.int64)
    p_bs_bmid = np.zeros(MAXP)
    p_bs_bbid = np.zeros(MAXP)
    p_bs_bask = np.zeros(MAXP)
    p_bs_peak = np.zeros(MAXP)
    p_bs_quiet = np.zeros(MAXP, np.int64)
    p_bs_ok = np.zeros(MAXP, np.bool_)
    p_cl_ms = np.zeros(MAXP, np.int64)          # > 0: a market close was sent, it fills at the first quote at or after this time
    p_cl_reason = np.zeros(MAXP, np.int64)
    npos = 0
    # market entries on their way to the server (only with X_LatencyMs > 0)
    m_on = np.zeros(MAXO, np.bool_)
    m_ms = np.zeros(MAXO, np.int64)
    m_side = np.zeros(MAXO, np.int64)
    m_sl = np.zeros(MAXO)
    m_tp = np.zeros(MAXO)
    m_scn = np.zeros(MAXO, np.int64)
    m_act = np.zeros(MAXO, np.int64)
    m_dec = np.zeros(MAXO, np.int64)
    m_req = np.zeros(MAXO)
    m_op = np.zeros(MAXO, np.bool_)
    m_alert = np.zeros(MAXO)
    m_spread = np.zeros(MAXO)
    nmk = 0
    # pending orders
    o_on = np.zeros(MAXO, np.bool_)
    o_type = np.zeros(MAXO, np.int64)
    o_price = np.zeros(MAXO)
    o_sl = np.zeros(MAXO)
    o_tp = np.zeros(MAXO)
    o_sec = np.zeros(MAXO, np.int64)
    o_scn = np.zeros(MAXO, np.int64)
    o_dec = np.zeros(MAXO, np.int64)
    o_op = np.zeros(MAXO, np.bool_)
    o_alert = np.zeros(MAXO)
    o_spread = np.zeros(MAXO)
    o_live = np.zeros(MAXO, np.int64)           # the order rests at the server from this time on
    o_ok = np.zeros(MAXO, np.bool_)             # the server has accepted it
    npend = 0

    cp = 0
    ncand = len(cand)
    xp = 0
    next_ = len(ext_i)
    i = 0
    while i < n:
        if (not speed_active) and npos == 0 and npend == 0 and nmk == 0 and (not hold_armed):
            # idle: nothing can change until the alert condition is next true (or an external fill arrives)
            while cp < ncand and cand[cp] < i:
                cp += 1
            nxt = n
            if cp < ncand:
                nxt = cand[cp]
            if xp < next_ and ext_i[xp] < nxt:
                nxt = max(ext_i[xp], i)
            if nxt >= n:
                break
            i = nxt
        t = T[i]
        bid = B[i]
        ask = A[i]
        mid = (bid + ask) * 0.5
        spread = (ask - bid) / PT

        # =========================== broker side ===============================================
        if npos > 0:
            for s in range(MAXP):
                if not p_on[s]:
                    continue
                reason = 0
                px = 0.0
                if p_side[s] > 0:
                    if bid <= p_sl[s]:
                        gap = p_sl[s] - bid
                        px = (p_sl[s] if gap <= snap else p_sl[s] - np.floor(gap / PT * slmult + 0.5) * PT) - slip
                        reason = R_SL if p_slmod[s] == 0 else (R_TRAIL_SL if p_slmod[s] == 1 else R_LAYER_SL)
                    elif bid >= p_tp[s]:
                        px = bid if lim_mkt else p_tp[s]
                        reason = R_TP
                else:
                    if ask >= p_sl[s]:
                        gap = ask - p_sl[s]
                        px = (p_sl[s] if gap <= snap else p_sl[s] + np.floor(gap / PT * slmult + 0.5) * PT) + slip
                        reason = R_SL if p_slmod[s] == 0 else (R_TRAIL_SL if p_slmod[s] == 1 else R_LAYER_SL)
                    elif ask <= p_tp[s]:
                        px = ask if lim_mkt else p_tp[s]
                        reason = R_TP
                if reason == 0 and p_cl_ms[s] > 0 and t >= p_cl_ms[s]:
                    px = (bid - slip) if p_side[s] > 0 else (ask + slip)
                    reason = p_cl_reason[s]
                if reason != 0:
                    if nt < maxt:
                        out[nt, 0] = p_fill[s]; out[nt, 1] = t; out[nt, 2] = p_side[s]; out[nt, 3] = p_act[s]
                        out[nt, 4] = p_scn[s]; out[nt, 5] = p_entry[s]; out[nt, 6] = px; out[nt, 7] = reason
                        out[nt, 8] = p_side[s] * (px - p_entry[s]) / PT - commission
                        cur = bid if p_side[s] > 0 else ask
                        fv = p_side[s] * (cur - p_entry[s]) / PT
                        out[nt, 9] = max(p_mfe[s], fv); out[nt, 10] = min(p_mae[s], fv)
                        out[nt, 11] = p_dec[s]; out[nt, 12] = p_req[s]; out[nt, 13] = 1.0 if p_rel[s] else 0.0
                        out[nt, 14] = p_slmod[s]; out[nt, 15] = 1.0 if p_op[s] else 0.0
                        out[nt, 16] = p_alert[s]; out[nt, 17] = p_spread[s]
                        nt += 1
                    p_on[s] = False
                    npos -= 1
        if npend > 0:
            for q in range(MAXO):
                if not o_on[q] or t < o_live[q]:
                    continue
                fill = 0.0
                side = 0
                ty = o_type[q]
                if not o_ok[q]:
                    # the request reaches the server now: a stop or limit price the market has already
                    # passed is refused ("invalid price"), it does not turn into a market order
                    o_ok[q] = True
                    if latency > 0 and ((ty == A_BS and ask >= o_price[q]) or (ty == A_SS and bid <= o_price[q])
                                        or (ty == A_BL and ask <= o_price[q]) or (ty == A_SL and bid >= o_price[q])):
                        o_on[q] = False
                        npend -= 1
                        cnt[C_REJECTED] += 1
                        continue
                if ty == A_BS and ask >= o_price[q]:
                    fill = (o_price[q] if ask - o_price[q] <= snap else ask) + slip
                    side = 1
                elif ty == A_SS and bid <= o_price[q]:
                    fill = (o_price[q] if o_price[q] - bid <= snap else bid) - slip
                    side = -1
                elif ty == A_BL and ask <= o_price[q]:
                    fill = ask if lim_mkt else o_price[q]
                    side = 1
                elif ty == A_SL and bid >= o_price[q]:
                    fill = bid if lim_mkt else o_price[q]
                    side = -1
                if side != 0:
                    o_on[q] = False
                    npend -= 1
                    for s in range(MAXP):
                        if not p_on[s]:
                            p_on[s] = True
                            npos += 1
                            p_side[s] = side; p_entry[s] = fill; p_sl[s] = o_sl[q]; p_tp[s] = o_tp[q]
                            p_fill[s] = t; p_scn[s] = o_scn[q]; p_act[s] = ty; p_slmod[s] = 0
                            p_dec[s] = o_dec[q]; p_req[s] = o_price[q]; p_op[s] = o_op[q]
                            p_alert[s] = o_alert[q]; p_spread[s] = o_spread[q]
                            p_trk[s] = False; p_rel[s] = False; p_tl_init[s] = False; p_bs_init[s] = False
                            p_cl_ms[s] = 0
                            cnt[C_FILLED] += 1
                            break

        if nmk > 0:
            for q in range(MAXO):
                if m_on[q] and t >= m_ms[q]:
                    m_on[q] = False
                    nmk -= 1
                    for s in range(MAXP):
                        if not p_on[s]:
                            p_on[s] = True
                            npos += 1
                            p_side[s] = m_side[q]
                            p_entry[s] = (ask + slip) if m_side[q] > 0 else (bid - slip)
                            p_sl[s] = m_sl[q]; p_tp[s] = m_tp[q]
                            p_fill[s] = t; p_scn[s] = m_scn[q]; p_act[s] = m_act[q]; p_slmod[s] = 0
                            p_dec[s] = m_dec[q]; p_req[s] = m_req[q]; p_op[s] = m_op[q]
                            p_alert[s] = m_alert[q]; p_spread[s] = m_spread[q]
                            p_trk[s] = False; p_rel[s] = False; p_tl_init[s] = False; p_bs_init[s] = False
                            p_cl_ms[s] = 0
                            cnt[C_FILLED] += 1
                            break
        while xp < next_ and ext_i[xp] <= i:
            for s in range(MAXP):
                if not p_on[s]:
                    p_on[s] = True
                    npos += 1
                    p_side[s] = ext_side[xp]; p_entry[s] = ext_entry[xp]; p_sl[s] = ext_sl[xp]; p_tp[s] = ext_tp[xp]
                    p_fill[s] = t; p_scn[s] = ext_scn[xp]; p_act[s] = ext_act[xp]; p_slmod[s] = 0
                    p_dec[s] = ext_id[xp]; p_req[s] = ext_entry[xp]; p_op[s] = False
                    p_alert[s] = 0.0; p_spread[s] = spread
                    p_trk[s] = False; p_rel[s] = False; p_tl_init[s] = False; p_bs_init[s] = False
                    p_cl_ms[s] = 0
                    break
            xp += 1

        # =========================== CP_RecheckPendings ========================================
        if npend > 0 and cp_on and P[I_InpCPCancelBadPendings] > 0.5:
            if not (cp_pending_check >= 0 and t >= cp_pending_check and t - cp_pending_check < 250):
                cp_pending_check = t
                sec = t // 1000
                if sec != cp_sec:
                    cp_c60, cp_c300, cp_n60, cp_gap, cp_r60, cp_r300, cp_msp = _cp_stats(T, B, A, i, cp_unit)
                    cp_sec = sec
                ok = True
                uses60 = (P[I_InpCPMinTickRate60] > 0 or P[I_InpCPMaxMedianGapMs] > 0 or P[I_InpCPMinRange60] > 0
                          or P[I_InpCPRequireCostCoverage] > 0.5)
                if uses60 and not cp_c60:
                    ok = False
                elif P[I_InpCPMinRange300] > 0 and not cp_c300:
                    ok = False
                elif P[I_InpCPMinTickRate60] > 0 and cp_n60 / 60.0 < P[I_InpCPMinTickRate60]:
                    ok = False
                elif P[I_InpCPMaxMedianGapMs] > 0 and (cp_gap < 0 or cp_gap > P[I_InpCPMaxMedianGapMs]):
                    ok = False
                elif P[I_InpCPMinRange60] > 0 and cp_r60 < P[I_InpCPMinRange60]:
                    ok = False
                elif P[I_InpCPMinRange300] > 0 and cp_r300 < P[I_InpCPMinRange300]:
                    ok = False
                elif P[I_InpCPRequireCostCoverage] > 0.5:
                    cur_sp = (ask - bid) / cp_unit
                    cost = max(P[I_InpCPGrossFloor], max(cur_sp, cp_msp) + P[I_InpCPSlipReserve] + P[I_InpCPCommission])
                    req = np.ceil(cost * cp_unit / PT - 1e-9) * PT / cp_unit
                    if cp_msp < 0 or cp_r60 + 1e-8 < req:
                        ok = False
                if not ok:
                    for q in range(MAXO):
                        if o_on[q]:
                            o_on[q] = False
                            npend -= 1
                            cnt[C_CP_CANCEL] += 1

        # =========================== UpdateSpeedAlert ==========================================
        if speed_active:
            if t - speed_start_ms > hold_ms_alert:
                speed_active = False
                cnt[C_ALERT_EXPIRED] += 1
        else:
            idx = idxL[i]
            move = (mid - (B[idx] + A[idx]) * 0.5) / PT
            thr = max(P[I_MinSpeedAlertPoints], spread * P[I_MaxTrailingMultiplier])
            gate_v = abs(move)
            gdir = 1 if move > 0.0 else -1
            if gate_v < thr:
                if (P[I_UsePreSpeedRadar] > 0.5 or P[I_UsePreSpeedAgainstDefense] > 0.5) and thr > 0.0 and gate_v > 0.0:
                    ratio = gate_v / thr
                    lvl = 0
                    if ratio >= P[I_PreSpeedStrongRatio]:
                        lvl = 70
                    elif ratio >= P[I_PreSpeedEarlyRatio]:
                        lvl = 50
                    if lvl > 0:
                        pre_ms = t
                        pre_dir = gdir
                        pre_level = lvl
            else:
                speed_active = True
                speed_start_ms = T[idx]
                speed_start_mid = (B[idx] + A[idx]) * 0.5
                speed_dir = gdir
                speed_pts = gate_v
                speed_idx = idx
                al_mfe = -BIG
                al_mae = BIG
                al_last = idx - 1
                cnt[C_ALERTS] += 1

        # =========================== ManagePendingExpiry =======================================
        if npend > 0 and P[I_PendingExpirySeconds] > 0:
            sec = t // 1000
            for q in range(MAXO):
                if o_on[q] and sec - o_sec[q] >= P[I_PendingExpirySeconds]:
                    o_on[q] = False
                    npend -= 1
                    cnt[C_EXPIRED] += 1

        # =========================== ManagePosition ============================================
        if npos > 0:
            # one-second path length for the burst-settle rule (BurstSettleMeasureSpeed)
            bs_valid = False
            bs_speed = 0.0
            if P[I_InpWaitForBurstSettle] > 0.5:
                start_ms = t - 1000
                dist = 0.0
                k = i
                okk = True
                while k > 0 and T[k] > start_ms:
                    g = T[k] - T[k - 1]
                    if g > 1000:
                        okk = False
                        break
                    dist += abs((B[k] + A[k]) * 0.5 - (B[k - 1] + A[k - 1]) * 0.5)
                    k -= 1
                if okk and T[k] <= start_ms:
                    bs_valid = True
                    bs_speed = dist / PIP
            for s in range(MAXP - 1, -1, -1):
                if not p_on[s] or p_cl_ms[s] > 0:
                    continue
                side = p_side[s]
                entry = p_entry[s]
                sl0 = p_sl[s]
                # ---- ObserveBurstSettlePosition / BurstSettleStep
                if P[I_InpWaitForBurstSettle] > 0.5:
                    if not p_bs_init[s]:
                        p_bs_init[s] = True
                        p_bs_first[s] = t; p_bs_last[s] = t; p_bs_bmid[s] = mid; p_bs_bbid[s] = bid
                        p_bs_bask[s] = ask; p_bs_peak[s] = 0.0; p_bs_quiet[s] = 0; p_bs_ok[s] = False
                    if p_bs_first[s] <= 0 or t < p_bs_last[s] or t - p_bs_last[s] > 1000:
                        p_bs_first[s] = t; p_bs_bmid[s] = mid; p_bs_bbid[s] = bid; p_bs_bask[s] = ask
                        p_bs_peak[s] = 0.0; p_bs_quiet[s] = 0; p_bs_ok[s] = False
                    p_bs_last[s] = t
                    new_ext = side * (mid - p_bs_bmid[s]) > PIP * 1e-6
                    if new_ext:
                        p_bs_bmid[s] = mid; p_bs_bbid[s] = bid; p_bs_bask[s] = ask
                    if bs_valid:
                        if bs_speed > p_bs_peak[s]:
                            p_bs_peak[s] = bs_speed
                    retr = min(side * (p_bs_bbid[s] - bid), side * (p_bs_bask[s] - ask)) / PIP
                    max_quiet = min(p_bs_peak[s] * P[I_InpBurstSettleSpeedFraction], P[I_InpBurstSettleMaxSpeedPipsSec])
                    calm = (bs_valid and (not new_ext) and t - p_bs_first[s] >= 1000 and p_bs_peak[s] > 0.0
                            and bs_speed <= max_quiet + 1e-9 and retr + 1e-9 >= P[I_InpBurstSettlePullbackPips])
                    if not calm:
                        p_bs_quiet[s] = 0
                        p_bs_ok[s] = False
                    else:
                        if p_bs_quiet[s] == 0:
                            p_bs_quiet[s] = t
                        p_bs_ok[s] = t - p_bs_quiet[s] >= P[I_InpBurstSettleQuietMs]
                settle_ok = (P[I_InpWaitForBurstSettle] < 0.5) or p_bs_ok[s]
                # ---- tracker
                if not p_trk[s]:
                    p_trk[s] = True
                    p_trk_ms[s] = t
                    p_mfe[s] = 0.0; p_mae[s] = 0.0; p_h21[s] = False; p_h37[s] = False
                    p_rheld[s] = False; p_rfail[s] = False; p_rfail_ms[s] = 0; p_rfail_fav[s] = 0.0
                    p_coll_ms[s] = 0; p_coll_ticks[s] = 0; p_lastfav[s] = 0.0; p_lastfav_ms[s] = t
                    p_se_pend[s] = False; p_se_last[s] = 0; p_se_n[s] = 0
                cur = bid if side > 0 else ask
                fav = side * (cur - entry) / PT
                if fav > p_mfe[s]:
                    p_mfe[s] = fav
                if fav < p_mae[s]:
                    p_mae[s] = fav
                # ---- PositionExitProfitReleased (EXIT_GATE_68)
                if not p_rel[s]:
                    if exit_gate_pts <= 0.0 or fav * PT > exit_gate_pts * PT + PT * 1e-6:
                        p_rel[s] = True
                released = p_rel[s]
                use_tl_state = P[I_InpUseTrailLayer] > 0.5 or P[I_InpUse1000msHold] > 0.5
                if use_tl_state:
                    if not p_tl_init[s]:
                        p_tl_init[s] = True
                        p_tl_peak[s] = cur; p_tl_armed[s] = False; p_tl_eval[s] = 0; p_hold_eval[s] = False
                    if side > 0:
                        if cur > p_tl_peak[s]:
                            p_tl_peak[s] = cur
                    else:
                        if cur < p_tl_peak[s]:
                            p_tl_peak[s] = cur
                if (not p_h21[s]) and fav >= P[I_MarketFollow21Points]:
                    p_h21[s] = True
                if (not p_h37[s]) and fav >= P[I_MarketFollow37Points]:
                    p_h37[s] = True

                close_reason = 0
                defensive = False
                held = t - p_trk_ms[s]
                pressure = p_mae[s] <= -P[I_OppositePressurePoints]
                # ---- TrySpeedProfitExit
                if released and P[I_UseSpeedProfitExit] > 0.5:
                    target_ready = fav >= P[I_SpeedProfitExitPoints]
                    pred_ready = False
                    proj_net = fav
                    if P[I_UsePredictiveSpeedProfitExit] > 0.5:
                        # PredictiveSpeedExitRiskPoints
                        lb = max(1.0, P[I_PredictiveExitVelocityLookbackMs])
                        j = _first_at_or_after(T, i, t - lb)
                        if j >= i:
                            j = max(0, i - 1)
                        if i < 1:
                            risk = P[I_PredictiveExitMinRiskBufferPoints] + P[I_PredictiveExitExtraBufferPoints]
                        else:
                            old_mid = (B[j] + A[j]) * 0.5
                            dts = max(0.001, (t - T[j]) / 1000.0)
                            abs_vel = abs((mid - old_mid) / PT) / dts
                            peak = mid; trough = mid; peak_ms = t; trough_ms = t
                            for k in range(j, i + 1):
                                mk = (B[k] + A[k]) * 0.5
                                if mk > peak:
                                    peak = mk; peak_ms = T[k]
                                if mk < trough:
                                    trough = mk; trough_ms = T[k]
                            adv_vel = 0.0
                            if side > 0:
                                adv = max(0.0, (peak - mid) / PT)
                                if adv > 0.0:
                                    adv_vel = adv / max(0.001, (t - peak_ms) / 1000.0)
                            else:
                                adv = max(0.0, (mid - trough) / PT)
                                if adv > 0.0:
                                    adv_vel = adv / max(0.001, (t - trough_ms) / 1000.0)
                            vel = max(abs_vel, adv_vel)
                            vrisk = vel * max(0.0, P[I_PredictiveExitLatencyMs] / 1000.0) * max(0.0, P[I_PredictiveExitVelocityMultiplier])
                            risk = max(0.0, spread) + P[I_PredictiveExitExtraBufferPoints] + max(P[I_PredictiveExitMinRiskBufferPoints], vrisk)
                            if P[I_PredictiveExitMaxRiskBufferPoints] > 0.0:
                                risk = min(risk, P[I_PredictiveExitMaxRiskBufferPoints])
                            risk = max(0.0, risk)
                        proj_net = fav - risk
                        side_speed = speed_active and (P[I_RequireProfitSideSpeed] < 0.5 or speed_dir == side)
                        pred_ready = (side_speed and fav >= P[I_PredictiveExitMinProfitPoints]
                                      and proj_net >= P[I_PredictiveExitMinProjectedNetPoints])
                    pend = p_se_pend[s]
                    go = pend or target_ready or pred_ready
                    if go and not pend:
                        if not speed_active:
                            go = False
                        elif P[I_RequireProfitSideSpeed] > 0.5 and speed_dir != side:
                            go = False
                    if go and P[I_UsePredictiveSpeedProfitExit] > 0.5 and P[I_BlockSpeedExitIfProjectedNegative] > 0.5 and proj_net < 0.0:
                        p_se_pend[s] = False
                        go = False
                    if go:
                        # in the tester the close succeeds at once, so no retry bookkeeping is needed
                        close_reason = R_SPEED_PREDICTIVE if (pred_ready and not target_ready) else R_SPEED_TARGET
                        speed_active = False
                        if P[I_UseDefensiveCloseLockout] > 0.5:
                            streak = 0
                            lockout_until = 0

                # ---- ValidatePosition
                if close_reason == 0 and released and P[I_UsePostEntryValidation] > 0.5:
                    scn = p_scn[s]
                    act = p_act[s]
                    folm = scn == S_FOLM
                    # TryFOLMSellMarketEarlyDangerClose
                    if (P[I_FOLMSellMarketEarlyDangerClose] > 0.5 and folm and act == A_SM
                            and P[I_FOLMSellMarketEarlyDangerLossPoints] > 0.0 and fav <= -P[I_FOLMSellMarketEarlyDangerLossPoints]
                            and (P[I_FOLMSellMarketEarlyDangerNeedsOppositePressure] < 0.5 or pressure)):
                        close_reason = R_FOLM_SM_EARLY
                    # TryFOLMPreHardWarnActiveClose
                    elif (P[I_UseFOLMPreHardWarnActiveClose] > 0.5 and folm and P[I_FOLMPreHardWarnActiveClosePoints] > 0.0
                          and fav <= -P[I_FOLMPreHardWarnActiveClosePoints]):
                        close_reason = R_FOLM_WARN
                    # TryFOLMMarketHardCapClose
                    elif (P[I_FOLMMarketHardClose] > 0.5 and folm and P[I_FOLMMarketHardMaxLossPoints] > 0.0
                          and fav <= -P[I_FOLMMarketHardMaxLossPoints]):
                        close_reason = R_FOLM_HARD
                    # TryFLXQSellStopPressureDangerClose
                    elif P[I_FLXQSellStopPressureDangerClose] > 0.5 and scn == S_FLXQ and act == A_SS:
                        v40 = (P[I_UseV40ExecutionShield] > 0.5 and P[I_V40FLXQSellStopPressureShield] > 0.5
                               and P[I_V40FLXQSellStopPressureShieldLossPoints] > 0.0
                               and fav <= -P[I_V40FLXQSellStopPressureShieldLossPoints]
                               and (P[I_V40FLXQSellStopPressureShieldNeedsPressure] < 0.5 or pressure))
                        normal = P[I_FLXQSellStopPressureDangerLossPoints] > 0.0 and fav <= -P[I_FLXQSellStopPressureDangerLossPoints]
                        if (v40 or normal) and not ((not pressure) and ((not v40) or P[I_V40FLXQSellStopPressureShieldNeedsPressure] > 0.5)):
                            close_reason = R_FLXQ_SS
                    # (TryStopFlowDisagreeDangerClose needs a FLOW_DISAGREES label: never with neutral flow)
                    if close_reason == 0:
                        if p_h21[s] and (not p_rheld[s]) and fav >= 0.0:
                            p_rheld[s] = True
                        if P[I_CloseOnRetestFailure] > 0.5 and p_h21[s] and fav <= -P[I_RetestFailPoints]:
                            if not p_rfail[s]:
                                p_rfail[s] = True
                                p_rfail_ms[s] = t
                                p_rfail_fav[s] = fav
                                p_coll_ms[s] = 0
                                p_coll_ticks[s] = 0
                            # RetestCollapseVelocity
                            cvel = 0.0
                            if p_lastfav_ms[s] > 0 and t > p_lastfav_ms[s]:
                                w = p_lastfav[s] - fav
                                if w > 0.0:
                                    cvel = w / max(0.001, (t - p_lastfav_ms[s]) / 1000.0)
                            cjump = p_rfail_fav[s] - fav
                            wage = t - p_rfail_ms[s]
                            deep = fav <= -P[I_RetestFailCloseMinLossPoints]
                            v_ok = P[I_V40RetestExecutionShieldMinVelocityPointsPerSec] <= 0.0 or cvel >= P[I_V40RetestExecutionShieldMinVelocityPointsPerSec]
                            j_ok = P[I_V40RetestExecutionShieldMinJumpPoints] <= 0.0 or cjump >= P[I_V40RetestExecutionShieldMinJumpPoints]
                            v40r = (P[I_UseV40ExecutionShield] > 0.5 and P[I_V40RetestExecutionShield] > 0.5
                                    and P[I_V40RetestExecutionShieldLossPoints] > 0.0
                                    and fav <= -P[I_V40RetestExecutionShieldLossPoints]
                                    and wage >= P[I_V40RetestExecutionShieldMinWarningAgeMs]
                                    and (P[I_V40RetestExecutionShieldNeedsPressure] < 0.5 or pressure)
                                    and (v_ok or j_ok))
                            folm_after = (P[I_FOLMAfterFollowRetestDangerClose] > 0.5 and folm and (p_h21[s] or p_h37[s])
                                          and P[I_FOLMAfterFollowRetestDangerLossPoints] > 0.0
                                          and fav <= -P[I_FOLMAfterFollowRetestDangerLossPoints])
                            if v40r:
                                close_reason = R_V40_RETEST
                            elif folm_after and P[I_FOLMAfterFollowRetestBypassHold] > 0.5:
                                close_reason = R_FOLM_RETEST
                            else:
                                cand_c = (P[I_UseEmergencyRetestCollapseClose] > 0.5 and fav <= -P[I_RetestCollapseMinLossPoints]
                                          and (cvel >= P[I_RetestCollapseVelocityPointsPerSec]
                                               or (P[I_RetestCollapseLookbackMs] > 0 and wage <= P[I_RetestCollapseLookbackMs]
                                                   and cjump >= P[I_RetestCollapseJumpPoints])))
                                if cand_c:
                                    if p_coll_ticks[s] <= 0:
                                        p_coll_ms[s] = t
                                        p_coll_ticks[s] = 1
                                    else:
                                        p_coll_ticks[s] += 1
                                    cms = t - p_coll_ms[s]
                                    if ((P[I_RetestCollapseConfirmTicks] <= 1 or p_coll_ticks[s] >= P[I_RetestCollapseConfirmTicks])
                                            and (P[I_RetestCollapseConfirmMs] <= 0 or cms >= P[I_RetestCollapseConfirmMs])):
                                        close_reason = R_RETEST_COLLAPSE
                                elif p_coll_ticks[s] > 0:
                                    p_coll_ticks[s] = 0
                                if close_reason == 0:
                                    hold_active = False
                                    if P[I_RetestCollapseHoldNormalCloseMs] > 0 and p_coll_ms[s] > 0:
                                        hold_active = (t - p_coll_ms[s]) < P[I_RetestCollapseHoldNormalCloseMs]
                                    confirm = P[I_RetestFailConfirmSeconds] <= 0 or t - p_rfail_ms[s] >= P[I_RetestFailConfirmSeconds] * 1000
                                    hard = P[I_RetestCollapseHardMaxLossPoints] > 0.0 and fav <= -P[I_RetestCollapseHardMaxLossPoints]
                                    early = (P[I_RetestFailedEarlyClose] > 0.5 and P[I_RetestFailedEarlyLossPoints] > 0.0
                                             and fav <= -P[I_RetestFailedEarlyLossPoints]
                                             and (P[I_RetestFailedEarlyBypassHold] > 0.5 or not hold_active))
                                    if confirm and hard:
                                        close_reason = R_RETEST_HARD
                                    elif confirm and early:
                                        close_reason = R_RETEST_EARLY
                                    elif confirm and deep and not hold_active:
                                        close_reason = R_RETEST_FAILED
                        else:
                            if p_rfail[s] and fav > -P[I_RetestFailPoints]:
                                p_rfail[s] = False
                                p_rfail_ms[s] = 0
                                p_rfail_fav[s] = 0.0
                                p_coll_ms[s] = 0
                                p_coll_ticks[s] = 0
                            # TryPreSpeedAgainstDefenseClose
                            if P[I_UsePreSpeedAgainstDefense] > 0.5 and not (p_h21[s] or p_h37[s]):
                                flxq_ss = P[I_FLXQSellStopFastPreSpeedDefense] > 0.5 and scn == S_FLXQ and act == A_SS
                                v40p = (P[I_UseV40ExecutionShield] > 0.5 and P[I_V40PreSpeedExecutionShield] > 0.5
                                        and P[I_V40PreSpeedExecutionShieldLossPoints] > 0.0
                                        and fav <= -P[I_V40PreSpeedExecutionShieldLossPoints]
                                        and (P[I_V40PreSpeedExecutionShieldNeedsPressureOrFlow] < 0.5 or pressure))
                                dmin = P[I_PreSpeedAgainstDefenseMinLossPoints]
                                if flxq_ss and P[I_FLXQSellStopFastPreSpeedDefenseLossPoints] > 0.0:
                                    dmin = min(dmin, P[I_FLXQSellStopFastPreSpeedDefenseLossPoints])
                                if v40p:
                                    dmin = min(dmin, P[I_V40PreSpeedExecutionShieldLossPoints])
                                if not (fav > -dmin):
                                    exhl_d = (P[I_EXHLPreSpeedDangerClose] > 0.5 and scn == S_EXHL
                                              and P[I_EXHLPreSpeedDangerLossPoints] > 0.0 and fav <= -P[I_EXHLPreSpeedDangerLossPoints])
                                    folm_d = (P[I_FOLMMarketDangerClose] > 0.5 and folm and P[I_FOLMMarketDangerLossPoints] > 0.0
                                              and fav <= -P[I_FOLMMarketDangerLossPoints])
                                    flxq_h = (flxq_ss and P[I_FLXQSellStopFastPreSpeedDefenseLossPoints] > 0.0
                                              and fav <= -P[I_FLXQSellStopFastPreSpeedDefenseLossPoints])
                                    okd = True
                                    if (P[I_PreSpeedAgainstDefenseNeedsOppositePressure] > 0.5 and (not pressure) and (not v40p)
                                            and not (exhl_d and P[I_EXHLPreSpeedDangerNeedsOppositePressure] < 0.5)
                                            and not (folm_d and P[I_FOLMMarketDangerNeedsOppositePressure] < 0.5)
                                            and not (flxq_h and P[I_FLXQSellStopFastPreSpeedDefenseNeedsOppositePressure] < 0.5)):
                                        okd = False
                                    if exhl_d and P[I_EXHLPreSpeedDangerNeedsOppositePressure] > 0.5 and not pressure:
                                        okd = False
                                    if folm_d and P[I_FOLMMarketDangerNeedsOppositePressure] > 0.5 and not pressure:
                                        okd = False
                                    if flxq_h and P[I_FLXQSellStopFastPreSpeedDefenseNeedsOppositePressure] > 0.5 and not pressure:
                                        okd = False
                                    if okd:
                                        wait_s = P[I_FLXQSellStopPreSpeedDefenseNoFollowSeconds] if flxq_ss else P[I_PreSpeedAgainstDefenseNoFollowSeconds]
                                        wait_ok = wait_s <= 0 or held >= wait_s * 1000
                                        n_hard = (P[I_PreSpeedAgainstDefenseHardClose] > 0.5 and P[I_PreSpeedAgainstDefenseHardMaxLossPoints] > 0.0
                                                  and fav <= -P[I_PreSpeedAgainstDefenseHardMaxLossPoints])
                                        hard_c = n_hard or flxq_h
                                        if v40p or exhl_d or folm_d or hard_c or wait_ok:
                                            # RecentPreSpeedAgainstTrade
                                            rec = pre_dir != 0 and pre_ms > 0 and pre_dir == -side
                                            if rec:
                                                if pre_level >= 70:
                                                    rec = P[I_PreSpeedAgainstDefenseCloseOnPreSpeed70] > 0.5
                                                else:
                                                    rec = P[I_PreSpeedAgainstDefenseCloseOnPreSpeed50] > 0.5
                                            if rec:
                                                max_age = P[I_PreSpeedAgainstDefenseMaxSignalAgeMs]
                                                if max_age <= 0:
                                                    max_age = max(1.0, P[I_SpeedAlertHoldSeconds] + P[I_PreSpeedAgainstDefenseNoFollowSeconds]) * 1000.0
                                                age = t - pre_ms
                                                rec = 0 <= age <= max_age
                                            if rec:
                                                close_reason = R_PRE_SPEED
                            # NoFollowEarlyClose
                            if close_reason == 0 and P[I_NoFollowEarlyClose] > 0.5:
                                if ((not p_h21[s]) and (not p_h37[s])
                                        and (P[I_NoFollowEarlySeconds] <= 0 or held >= P[I_NoFollowEarlySeconds] * 1000)
                                        and P[I_NoFollowEarlyLossPoints] > 0.0 and fav <= -P[I_NoFollowEarlyLossPoints]
                                        and (P[I_NoFollowEarlyNeedsOppositePressure] < 0.5 or pressure)):
                                    close_reason = R_NO_FOLLOW_EARLY
                            # CloseIfNoFollowThrough
                            if close_reason == 0 and P[I_CloseIfNoFollowThrough] > 0.5 and held >= P[I_ValidationSeconds] * 1000:
                                if (not p_h21[s]) and (not p_h37[s]) and pressure and fav <= -P[I_NoFollowCloseMinLossPoints]:
                                    close_reason = R_NO_FOLLOW
                    if close_reason != 0:
                        defensive = True

                if close_reason == 0:
                    # TrackFavSnapshot
                    p_lastfav[s] = fav
                    p_lastfav_ms[s] = t
                    # ProcessPostFillHold
                    if released and use_tl_state and P[I_InpUse1000msHold] > 0.5 and not p_hold_eval[s]:
                        if t - p_fill[s] >= 1000:
                            p_hold_eval[s] = True
                            if not (fav >= P[I_InpHoldMinFavPts]):
                                close_reason = R_HOLD_KILL

                if close_reason != 0:
                    if latency > 0:
                        p_cl_ms[s] = t + latency
                        p_cl_reason[s] = close_reason
                    else:
                        px = cur - side * slip
                        if nt < maxt:
                            out[nt, 0] = p_fill[s]; out[nt, 1] = t; out[nt, 2] = side; out[nt, 3] = p_act[s]
                            out[nt, 4] = p_scn[s]; out[nt, 5] = entry; out[nt, 6] = px; out[nt, 7] = close_reason
                            out[nt, 8] = side * (px - entry) / PT - commission
                            out[nt, 9] = p_mfe[s]; out[nt, 10] = p_mae[s]; out[nt, 11] = p_dec[s]; out[nt, 12] = p_req[s]
                            out[nt, 13] = 1.0 if p_rel[s] else 0.0; out[nt, 14] = p_slmod[s]
                            out[nt, 15] = 1.0 if p_op[s] else 0.0; out[nt, 16] = p_alert[s]; out[nt, 17] = p_spread[s]
                            nt += 1
                        p_on[s] = False
                        npos -= 1
                    if defensive and P[I_UseDefensiveCloseLockout] > 0.5:
                        # UpdateDefensiveLockoutAfterClose
                        streak += 1
                        trig = P[I_DefensiveLockoutCloseCount] if P[I_DefensiveLockoutCloseCount] > 1 else 1
                        if streak >= trig:
                            lock = (P[I_DefensiveLockoutSeconds] if P[I_DefensiveLockoutSeconds] > 1 else 1) * 1000
                            if t + lock > lockout_until:
                                lockout_until = int(t + lock)
                            cnt[C_LOCKOUT_ARMED] += 1
                            if P[I_DefensiveLockoutCancelPendings] > 0.5:
                                for q in range(MAXO):
                                    if o_on[q]:
                                        o_on[q] = False
                                        npend -= 1
                            streak = 0
                    continue

                # ---- TrailPosition ("Simple Test Trailing")
                if P[I_UseTrailing] > 0.5:
                    if (exit_gate_pts <= 0.0 or fav * PT > exit_gate_pts * PT + PT * 1e-6) and fav >= P[I_TrailStartPoints]:
                        tdist = P[I_TrailBehindPoints]
                        if side > 0:
                            new_sl = round((cur - tdist * PT) / PT) * PT
                            if not (sl0 > 0.0 and new_sl <= sl0 + P[I_TrailStepPoints] * PT):
                                if settle_ok and bid - new_sl >= stops_level * PT:
                                    p_sl[s] = new_sl
                                    p_slmod[s] = 1
                        else:
                            new_sl = round((cur + tdist * PT) / PT) * PT
                            if not (sl0 > 0.0 and new_sl >= sl0 - P[I_TrailStepPoints] * PT):
                                if settle_ok and new_sl - ask >= stops_level * PT:
                                    p_sl[s] = new_sl
                                    p_slmod[s] = 1
                # ---- ManageTrailLayer ("Spread-Scaled Broker Trail Layer")
                if P[I_InpUseTrailLayer] > 0.5:
                    go = True
                    if not p_tl_armed[s]:
                        if not (exit_gate_pts <= 0.0 or fav * PT > exit_gate_pts * PT + PT * 1e-6):
                            go = False
                        elif P[I_InpArmOnCostDigested] > 0.5 and fav >= cost_digested:
                            pass
                        elif P[I_InpArmOnFavPts] > 0.5 and fav >= P[I_InpTrailArmFavPts]:
                            pass
                        elif P[I_InpArmOnTimeMs] > 0.5 and (t - p_fill[s]) >= P[I_InpTrailArmTimeMs]:
                            pass
                        else:
                            go = False
                        if go:
                            p_tl_armed[s] = True
                    elif p_tl_eval[s] > 0 and t - p_tl_eval[s] < P[I_InpModifyMinIntervalMs]:
                        go = False
                    if go:
                        p_tl_eval[s] = t
                        eff = max(spread, P[I_InpReferenceSpreadPts])
                        activation = P[I_internalOrderDistance] * eff
                        outer = min(P[I_internalMaxTrailing] * eff, P[I_InpTrailOuterCapPts])
                        inner = min(P[I_internalMinTrailing] * eff, outer)
                        applied = max(inner, min(outer, activation))
                        old = p_sl[s]
                        if side > 0:
                            new_sl = np.floor((p_tl_peak[s] - applied * PT) / PT + 1e-9) * PT
                            better = old <= 0.0 or new_sl > old + PT * 0.5
                            legal = (bid - new_sl) / PT
                        else:
                            new_sl = np.ceil((p_tl_peak[s] + applied * PT) / PT - 1e-9) * PT
                            better = old <= 0.0 or new_sl < old - PT * 0.5
                            legal = (new_sl - ask) / PT
                        if better and legal + 1e-9 >= min_legal and settle_ok:
                            p_sl[s] = new_sl
                            p_slmod[s] = 2

        # =========================== entry side ================================================
        if not speed_active:
            if hold_armed:
                hold_armed = False
            i += 1
            continue
        if P[I_UseDefensiveCloseLockout] > 0.5 and lockout_until > t:
            speed_active = False
            cnt[C_LOCKOUT_SKIP] += 1
            i += 1
            continue

        action = 0
        scn = 0
        opp = False
        from_hold = False
        if P[I_InpUseEntryHold] > 0.5 and hold_armed:
            # ---- ProcessArmedEntryHold
            el = t - hold_sig_ms
            if el < max(0.0, P[I_InpEntryHoldMs]):
                i += 1
                continue
            action = hold_action
            scn = hold_scn
            opp = hold_op
            from_hold = True
        else:
            # ---- BuildDirectionState
            cnt[C_DECISIONS] += 1
            spread_stable = spread <= P[I_MaxSpreadPoints]
            buy = 0.0
            sell = 0.0
            if spread_stable:
                buy += P[I_SpreadStableScore]
                sell += P[I_SpreadStableScore]
            if speed_dir > 0:
                buy += P[I_SpeedDirectionScore]
            elif speed_dir < 0:
                sell += P[I_SpeedDirectionScore]
            # ScoreCandle on the forming M1 bar (bid open/high/low, mid as the close)
            minute = t // 60000
            if minute != bar_min or bar_i > i:
                j = i
                while j > 0 and T[j - 1] // 60000 == minute:
                    j -= 1
                bar_min = minute
                bar_open = B[j]
                bar_hi = B[j]
                bar_lo = B[j]
                for k in range(j + 1, i + 1):
                    if B[k] > bar_hi:
                        bar_hi = B[k]
                    if B[k] < bar_lo:
                        bar_lo = B[k]
                bar_i = i
            else:
                for k in range(bar_i + 1, i + 1):
                    if B[k] > bar_hi:
                        bar_hi = B[k]
                    if B[k] < bar_lo:
                        bar_lo = B[k]
                bar_i = i
            body_signed = (mid - bar_open) / PT
            body = abs(body_signed)
            up_wick = (bar_hi - max(bar_open, mid)) / PT
            lo_wick = (min(bar_open, mid) - bar_lo) / PT
            body_dir = 0
            if body >= P[I_MinCandleBodyPoints]:
                if body_signed > 0.0:
                    body_dir = 1
                    buy += P[I_CandleBodyScore]
                elif body_signed < 0.0:
                    body_dir = -1
                    sell += P[I_CandleBodyScore]
            # ScoreMicroBreak
            micro_dir = 0
            j = _first_at_or_after(T, i, t - P[I_MicroBreakLookbackSeconds] * 1000)
            if i - 1 >= j:
                hi = (B[j] + A[j]) * 0.5
                lo = hi
                for k in range(j, i):
                    mk = (B[k] + A[k]) * 0.5
                    if mk > hi:
                        hi = mk
                    if mk < lo:
                        lo = mk
                buf = P[I_MicroBreakBufferPoints] * PT
                if mid > hi + buf:
                    micro_dir = 1
                    buy += P[I_MicroBreakScore]
                if mid < lo - buf:
                    micro_dir = -1
                    sell += P[I_MicroBreakScore]
            # ScoreFollowAndMfeMae (running extremes of the move since the alert's start tick)
            for k in range(al_last + 1, i + 1):
                fv = speed_dir * ((B[k] + A[k]) * 0.5 - speed_start_mid) / PT
                if fv > al_mfe:
                    al_mfe = fv
                if fv < al_mae:
                    al_mae = fv
            al_last = i
            s_mfe = al_mfe if al_mfe > -BIG else 0.0
            s_mae = al_mae if al_mae < BIG else 0.0
            mv = speed_dir * (mid - speed_start_mid) / PT
            el = t - speed_start_ms
            f21 = mv >= P[I_MarketFollow21Points] and el <= P[I_MarketFollow21Seconds] * 1000
            f37 = mv >= P[I_MarketFollow37Points] and el <= P[I_MarketFollow37Seconds] * 1000
            # WinnerSide
            winner = 0
            if buy >= P[I_MinDirectionScore] and (buy - sell) >= P[I_MinScoreEdge]:
                winner = 1
            elif sell >= P[I_MinDirectionScore] and (sell - buy) >= P[I_MinScoreEdge]:
                winner = -1
            # DetectOppositePressure
            if winner != 0:
                j = _first_at_or_after(T, i, t - P[I_OppositePressureSeconds] * 1000)
                ref = (B[j] + A[j]) * 0.5
                worst = 0.0
                for k in range(j, i + 1):
                    ma = winner * (ref - (B[k] + A[k]) * 0.5) / PT
                    if ma > worst:
                        worst = ma
                opp = worst >= P[I_OppositePressurePoints]
            # DetectSpeedSnapback
            snapback = speed_dir != 0 and speed_start_mid > 0.0 and (speed_dir * (speed_start_mid - mid) / PT) >= P[I_RetestFailPoints]
            speed_with = winner != 0 and speed_dir == winner
            has_follow = speed_with and (f21 or f37)
            good_mm = speed_with and s_mfe > abs(s_mae)
            continuation = (winner != 0 and spread_stable and (has_follow or good_mm) and (not opp)
                            and (body_dir == winner or micro_dir == winner))
            wick = ((up_wick > max(20.0, body * 1.25) and speed_dir > 0)
                    or (lo_wick > max(20.0, body * 1.25) and speed_dir < 0))
            exhaustion = wick or snapback or opp or (not spread_stable)
            body_with = body_dir != 0 and winner == body_dir
            # ---- DecideAction
            if not spread_stable:
                cnt[C_SKIP_SPREAD] += 1
                i += 1
                continue
            if exhaustion and router >= 2 and speed_dir != 0:
                action = A_SL if speed_dir > 0 else A_BL
            elif winner == 0:
                cnt[C_SKIP_MIXED] += 1
                i += 1
                continue
            else:
                market = False
                if speed_dir == winner and (f21 or f37) and router >= 1:
                    # MarketEntryAllowedByFlow with neutral flow
                    market = True
                    if winner < 0 and P[I_DowngradeNeutralSellMarketToStop] > 0.5:
                        market = False
                    elif P[I_WeakFlowMarketNeedsBodyAndMicro] > 0.5:
                        sc = buy if winner > 0 else sell
                        market = (body_dir == winner and body >= P[I_MinCandleBodyPoints] and micro_dir == winner
                                  and sc >= P[I_WeakFlowMarketMinScore] and abs(buy - sell) >= P[I_WeakFlowMarketMinScoreEdge])
                if market:
                    action = A_BM if winner > 0 else A_SM
                else:
                    action = A_BS if winner > 0 else A_SS
            if (action == A_BS or action == A_SS) and winner != 0 and body_dir != 0 and body_dir == -winner:
                cnt[C_SKIP_BODY] += 1
                i += 1
                continue
            # ScenarioKeyForAction
            if action == A_BM or action == A_SM:
                scn = S_FOLM
            elif action == A_BL or action == A_SL:
                scn = S_EXHL
            elif body_with and spread_stable and (not opp) and (has_follow or good_mm):
                scn = S_FLXQ
            elif body_with and spread_stable and (good_mm or has_follow):
                scn = S_QUAL
            elif body_with and not opp:
                scn = S_BNO
            elif (not exhaustion) and (not continuation) and body_with:
                scn = S_BODY
            elif continuation:
                scn = S_CONT
            elif exhaustion:
                scn = S_EXH
            else:
                scn = S_OTHER

        aside = 1 if (action == A_BS or action == A_BM or action == A_BL) else -1
        if (aside > 0 and P[I_X_TradeBuys] < 0.5) or (aside < 0 and P[I_X_TradeSells] < 0.5):
            speed_active = False
            hold_armed = False
            i += 1
            continue
        # ---- FlashGoldAllowsEntry
        fg_ok = True
        if fg_on:
            fg_ok = False
            fi = -1
            bar_time = 0
            bar_end = 0
            if fg_micro:
                bucket = (t // fg_interval) * fg_interval
                fi = np.searchsorted(fg_time, bucket)
                if fi >= nfg or fg_time[fi] != bucket or fg_li[fi] < fg_warm:
                    fi = -1
                bar_time = bucket
                bar_end = bucket + fg_interval
            else:
                m1 = (t // 60000) * 60000
                fi = np.searchsorted(fg_time, m1, side="right") - 1
                bar_time = m1
                bar_end = m1 + 60000
            if fi >= 0 and fg_li[fi] >= 1:
                fq = fi - 1
                clock = t
                if bar_end - 1 < clock:
                    clock = bar_end - 1
                if fg_end[fi] - 1 < clock:
                    clock = fg_end[fi] - 1
                if clock < bar_time:
                    clock = bar_time
                index = fg_li[fi] - 1 if clock == fg_end[fq] else fg_li[fi]
                z = fg_gate(fg_aat[fq], fg_abar[fq], fg_aprice[fq], fg_adir[fq], fg_aatr[fq], clock, index, bid,
                            fg_wm, int(P[I_FG_InpMinutes]), int(P[I_FG_InpBars]), P[I_FG_InpBandAtr],
                            P[I_FG_InpAgainst] > 0.5, P[I_FG_InpAllowBuy] > 0.5, P[I_FG_InpAllowSell] > 0.5)
                fg_ok = z == aside
                if fg_ok and fg_dur > 0:
                    at = fg_aat[fq]
                    fg_ok = at >= 0 and t >= at and t < at + fg_dur
        if not fg_ok:
            cnt[C_FG_BLOCK] += 1
            speed_active = False
            hold_armed = False
            i += 1
            continue

        hold_move = 0.0
        if P[I_InpUseEntryHold] > 0.5:
            if not from_hold:
                if hold_failed_bar == t // 60000:
                    cnt[C_HOLD_SAME_BAR] += 1
                    speed_active = False
                    i += 1
                    continue
                hold_armed = True
                hold_sig_ms = t
                hold_sig_mid = mid
                hold_action = action
                hold_scn = scn
                hold_op = opp
                cnt[C_HOLD_ARMED] += 1
                i += 1
                continue
            hold_move = aside * (mid - hold_sig_mid) / PT
            if not (hold_move >= P[I_InpEntryHoldMinFavPoints]):
                hold_failed_bar = t // 60000
                hold_armed = False
                speed_active = False
                cnt[C_HOLD_FAIL] += 1
                i += 1
                continue

        # ---- EntryPrior60Approved (drift over the previous 60 minutes must agree)
        need_prior = P[I_InpUsePrior60Filter] > 0.5
        if need_prior:
            target = t - 3600000
            lo_i = np.searchsorted(T[: i + 1], target - 5000)
            hi_i = np.searchsorted(T[: i + 1], target + 5000, side="right")
            ok60 = False
            if hi_i > lo_i:
                best = lo_i
                bd = abs(T[lo_i] - target)
                for k in range(lo_i + 1, hi_i):
                    d = abs(T[k] - target)
                    if d < bd:
                        bd = d
                        best = k
                drift = (mid - (B[best] + A[best]) * 0.5) / PT
                ok60 = (aside > 0 and drift > 0.0) or (aside < 0 and drift < 0.0)
            if not ok60:
                cnt[C_PRIOR60_BLOCK] += 1
                hold_armed = False
                speed_active = False
                i += 1
                continue
        # ---- GateDecisionAllowsEntry: one-second burst gate
        if P[I_InpUseHighBurstGate] > 0.5:
            okb = False
            if t - ep_start[i] >= 1000:
                j = _first_at_or_after(T, i, t - 1000)
                if j < i and t > T[j]:
                    b1 = ((mid - (B[j] + A[j]) * 0.5) / PT) / ((t - T[j]) / 1000.0)
                    okb = abs(b1) >= P[I_InpBurstThresholdPts] and ((aside > 0 and b1 > 0.0) or (aside < 0 and b1 < 0.0))
            if not okb:
                cnt[C_BURST_BLOCK] += 1
                hold_armed = False
                speed_active = False
                i += 1
                continue
        # ---- ScenarioCanPlace
        can = True
        if P[I_ScenarioIndependentPerformance] < 0.5:
            if P[I_MaxOpenPositions] > 0 and npos + nmk >= P[I_MaxOpenPositions]:
                can = False
            elif P[I_MaxPendingOrders] > 0 and npend >= P[I_MaxPendingOrders]:
                can = False
        else:
            cp_ = 0
            co_ = 0
            for s in range(MAXP):
                if p_on[s] and p_scn[s] == scn:
                    cp_ += 1
            for q in range(MAXO):
                if o_on[q] and o_scn[q] == scn:
                    co_ += 1
                if m_on[q] and m_scn[q] == scn:
                    cp_ += 1
            if P[I_MaxOpenPositionsPerScenario] > 0 and cp_ >= P[I_MaxOpenPositionsPerScenario]:
                can = False
            elif P[I_MaxPendingOrdersPerScenario] > 0 and co_ >= P[I_MaxPendingOrdersPerScenario]:
                can = False
        if not can:
            cnt[C_CAP_SKIP] += 1
            hold_armed = False          # speedActive stays true, as in the EA
            i += 1
            continue
        if P[I_CancelOldPendings] > 0.5:
            for q in range(MAXO):
                if o_on[q] and (o_scn[q] == scn or not (P[I_ScenarioIndependentPerformance] > 0.5 and P[I_CancelOnlySameScenarioPendings] > 0.5)):
                    o_on[q] = False
                    npend -= 1

        # ---- PlaceAction -> CContinuationTrade::OrderSend
        send = True
        if cp_on:
            sec = t // 1000
            if sec != cp_sec:
                cp_c60, cp_c300, cp_n60, cp_gap, cp_r60, cp_r300, cp_msp = _cp_stats(T, B, A, i, cp_unit)
                cp_sec = sec
            uses60 = (P[I_InpCPMinTickRate60] > 0 or P[I_InpCPMaxMedianGapMs] > 0 or P[I_InpCPMinRange60] > 0
                      or P[I_InpCPRequireCostCoverage] > 0.5)
            if uses60 and not cp_c60:
                send = False
            elif P[I_InpCPMinRange300] > 0 and not cp_c300:
                send = False
            elif P[I_InpCPMinTickRate60] > 0 and cp_n60 / 60.0 < P[I_InpCPMinTickRate60]:
                send = False
            elif P[I_InpCPMaxMedianGapMs] > 0 and (cp_gap < 0 or cp_gap > P[I_InpCPMaxMedianGapMs]):
                send = False
            elif P[I_InpCPMinRange60] > 0 and cp_r60 < P[I_InpCPMinRange60]:
                send = False
            elif P[I_InpCPMinRange300] > 0 and cp_r300 < P[I_InpCPMinRange300]:
                send = False
            elif P[I_InpCPRequireCostCoverage] > 0.5:
                cur_sp = (ask - bid) / cp_unit
                cost = max(P[I_InpCPGrossFloor], max(cur_sp, cp_msp) + P[I_InpCPSlipReserve] + P[I_InpCPCommission])
                req = np.ceil(cost * cp_unit / PT - 1e-9) * PT / cp_unit
                if cp_msp < 0 or cp_r60 + 1e-8 < req:
                    send = False
        if not send:
            cnt[C_CP_BLOCK] += 1
        else:
            cnt[C_PLACED] += 1
            if (action == A_BM or action == A_SM) and latency > 0:
                ref = ask if action == A_BM else bid
                for q in range(MAXO):
                    if not m_on[q]:
                        m_on[q] = True
                        nmk += 1
                        m_ms[q] = t + latency; m_side[q] = aside
                        m_sl[q] = round((ref - aside * P[I_MarketSLPoints] * PT) / PT) * PT
                        m_tp[q] = round((ref + aside * P[I_MarketTPPoints] * PT) / PT) * PT
                        m_scn[q] = scn; m_act[q] = action; m_dec[q] = t; m_req[q] = ref; m_op[q] = opp
                        m_alert[q] = speed_pts; m_spread[q] = spread
                        break
            elif action == A_BM or action == A_SM:
                fill = ask + slip if action == A_BM else bid - slip
                ref = ask if action == A_BM else bid
                for s in range(MAXP):
                    if not p_on[s]:
                        p_on[s] = True
                        npos += 1
                        p_side[s] = aside; p_entry[s] = fill
                        p_sl[s] = round((ref - aside * P[I_MarketSLPoints] * PT) / PT) * PT
                        p_tp[s] = round((ref + aside * P[I_MarketTPPoints] * PT) / PT) * PT
                        p_fill[s] = t; p_scn[s] = scn; p_act[s] = action; p_slmod[s] = 0
                        p_dec[s] = t; p_req[s] = ref; p_op[s] = opp; p_alert[s] = speed_pts; p_spread[s] = spread
                        p_trk[s] = False; p_rel[s] = False; p_tl_init[s] = False; p_bs_init[s] = False
                        p_cl_ms[s] = 0
                        cnt[C_FILLED] += 1
                        break
            else:
                if action == A_BS:
                    price = max(ask + P[I_StopEntryDistancePoints] * PT, ask + min_dist)
                    slp = P[I_StopSLPoints]; tpp = P[I_StopTPPoints]
                elif action == A_SS:
                    price = min(bid - P[I_StopEntryDistancePoints] * PT, bid - min_dist)
                    slp = P[I_StopSLPoints]; tpp = P[I_StopTPPoints]
                elif action == A_BL:
                    price = min(bid - P[I_LimitRetestDistancePoints] * PT, ask - min_dist)
                    slp = P[I_LimitSLPoints]; tpp = P[I_LimitTPPoints]
                else:
                    price = max(ask + P[I_LimitRetestDistancePoints] * PT, bid + min_dist)
                    slp = P[I_LimitSLPoints]; tpp = P[I_LimitTPPoints]
                price = round(price / PT) * PT
                for q in range(MAXO):
                    if not o_on[q]:
                        o_on[q] = True
                        npend += 1
                        o_type[q] = action; o_price[q] = price
                        o_sl[q] = round((price - aside * slp * PT) / PT) * PT
                        o_tp[q] = round((price + aside * tpp * PT) / PT) * PT
                        o_sec[q] = t // 1000; o_scn[q] = scn; o_dec[q] = t; o_op[q] = opp
                        o_alert[q] = speed_pts; o_spread[q] = spread
                        o_live[q] = t + latency
                        o_ok[q] = False
                        break
        hold_armed = False
        speed_active = False
        i += 1

    # positions still open at the end of the week are closed at the last quote
    if npos > 0:
        bid = B[n - 1]
        ask = A[n - 1]
        for s in range(MAXP):
            if p_on[s] and nt < maxt:
                cur = bid if p_side[s] > 0 else ask
                out[nt, 0] = p_fill[s]; out[nt, 1] = T[n - 1]; out[nt, 2] = p_side[s]; out[nt, 3] = p_act[s]
                out[nt, 4] = p_scn[s]; out[nt, 5] = p_entry[s]; out[nt, 6] = cur; out[nt, 7] = R_END
                out[nt, 8] = p_side[s] * (cur - p_entry[s]) / PT - commission
                out[nt, 9] = p_mfe[s]; out[nt, 10] = p_mae[s]; out[nt, 11] = p_dec[s]; out[nt, 12] = p_req[s]
                out[nt, 13] = 1.0 if p_rel[s] else 0.0; out[nt, 14] = p_slmod[s]
                out[nt, 15] = 1.0 if p_op[s] else 0.0; out[nt, 16] = p_alert[s]; out[nt, 17] = p_spread[s]
                nt += 1
    return nt
