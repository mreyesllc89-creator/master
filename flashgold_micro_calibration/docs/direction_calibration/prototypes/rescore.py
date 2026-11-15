"""PLAN prototype of the offline direction re-scorer: score, winner, flow votes, router action and scenario key for
every logged decision row under ANY value of the direction inputs, computed from the log + the feed (+ the flow
series), with the same float64 operations in the same order as engine.run_chunk (lines 1048-1203 of the original).
State-free only: no lockout, caps, hold automaton (those need the replay)."""
import numpy as np

import engine as E

PT = 0.01
A_BS, A_SS, A_BM, A_SM, A_BL, A_SL = 1, 2, 3, 4, 5, 6


def rescore_direction(li, lf, T, B, A, th, flow=None):
    """li, lf: kind-0 rows of one chunk. th: dict of inputs (EA names). flow = (fl_ix, fl_t, fl_ok, fl_v) of the chunk or None."""
    mid_all = (B + A) * 0.5
    i = li[:, E.LI_TICK].astype(np.int64)
    n = len(i)
    t = T[i]
    mid = mid_all[i]
    spread = (A[i] - B[i]) / PT
    stable = spread <= th["MaxSpreadPoints"]
    buy = np.where(stable, th["SpreadStableScore"], 0.0)
    sell = buy.copy()
    sd = li[:, E.LI_SPDIR].astype(np.int64)
    buy = np.where(sd > 0, buy + th["SpeedDirectionScore"], buy)
    sell = np.where(sd < 0, sell + th["SpeedDirectionScore"], sell)
    # candle (forming M1 bar: bid open / high / low, mid as the close)
    bar_open = B[li[:, E.LI_IBAROPEN]]
    bar_hi = B[li[:, E.LI_IBARHI]]
    bar_lo = B[li[:, E.LI_IBARLO]]
    body_signed = (mid - bar_open) / PT
    body = np.abs(body_signed)
    up_wick = (bar_hi - np.maximum(bar_open, mid)) / PT
    lo_wick = (np.minimum(bar_open, mid) - bar_lo) / PT
    big = body >= th["MinCandleBodyPoints"]
    body_dir = np.where(big & (body_signed > 0.0), 1, np.where(big & (body_signed < 0.0), -1, 0))
    buy = np.where(body_dir == 1, buy + th["CandleBodyScore"], buy)
    sell = np.where(body_dir == -1, sell + th["CandleBodyScore"], sell)
    # micro break
    q = int(np.flatnonzero(E.LG_MICRO_L == int(th["MicroBreakLookbackSeconds"] * 1000))[0])
    hi_i = li[:, E.LI_MHI + q]
    lo_i = li[:, E.LI_MLO + q]
    has = hi_i >= 0
    hi = mid_all[np.maximum(hi_i, 0)]
    lo = mid_all[np.maximum(lo_i, 0)]
    buf = th["MicroBreakBufferPoints"] * PT
    mu = has & (mid > hi + buf)
    md = has & (mid < lo - buf)
    micro_dir = np.where(mu, 1, np.where(md, -1, 0))
    buy = np.where(mu, buy + th["MicroBreakScore"], buy)
    sell = np.where(md, sell + th["MicroBreakScore"], sell)
    # order flow
    fl_dir = np.zeros(n, np.int64)
    fresh = np.zeros(n, bool)
    if flow is not None and len(flow[0]) > 0 and th["UseOrderFlow"]:
        fl_ix, fl_t, fl_ok, fl_v = flow
        k = li[:, E.LI_FLK].astype(np.int64)
        ks = np.maximum(k, 0)
        fresh = (k >= 0) & (fl_ok[ks] != 0) & ((t - fl_t[ks]) <= th["MaxFlowAgeMs"])
        vb = np.zeros(n, np.int64)
        vs = np.zeros(n, np.int64)
        for c in range(3):
            v = fl_v[ks, c]
            voted = fresh & (np.abs(v) >= th["MinFlowImbalance"])
            up = voted & (v > 0.0)
            dn = voted & ~(v > 0.0)
            buy = np.where(up, buy + th["FlowComponentScore"], buy)
            sell = np.where(dn, sell + th["FlowComponentScore"], sell)
            vb += up
            vs += dn
        fl_dir = np.where(vb >= 2, 1, np.where(vs >= 2, -1, 0))
    win = np.where((buy >= th["MinDirectionScore"]) & ((buy - sell) >= th["MinScoreEdge"]), 1,
                   np.where((sell >= th["MinDirectionScore"]) & ((sell - buy) >= th["MinScoreEdge"]), -1, 0))
    fa = (win != 0) & (fl_dir == win)
    fd = (win != 0) & (fl_dir == -win)
    # follow flags and alert extremes
    istart = li[:, E.LI_ISTART].astype(np.int64)
    start_mid = mid_all[istart]
    mv = sd * (mid - start_mid) / PT
    el = t - T[istart]
    f21 = (mv >= th["MarketFollow21Points"]) & (el <= th["MarketFollow21Seconds"] * 1000)
    f37 = (mv >= th["MarketFollow37Points"]) & (el <= th["MarketFollow37Seconds"] * 1000)
    s_mfe = lf[:, E.LF_MFE].astype(np.float64)
    s_mae = lf[:, E.LF_MAE].astype(np.float64)
    # opposite pressure on the winner's side
    qw = int(np.flatnonzero(E.LG_OPP_W == int(th["OppositePressureSeconds"] * 1000))[0])
    ref = mid_all[li[:, E.LI_OREF + qw]]
    ext = np.where(win > 0, mid_all[li[:, E.LI_OMIN + qw]], mid_all[li[:, E.LI_OMAX + qw]])
    ma = win * (ref - ext) / PT
    worst = np.maximum(0.0, ma)
    opp = (win != 0) & (worst >= th["OppositePressurePoints"])
    snap = (sd != 0) & (start_mid > 0.0) & ((sd * (start_mid - mid) / PT) >= th["RetestFailPoints"])
    speed_with = (win != 0) & (sd == win)
    has_follow = speed_with & (f21 | f37)
    good_mm = speed_with & (s_mfe > np.abs(s_mae))
    cont = (win != 0) & stable & (has_follow | good_mm) & ~opp & ((body_dir == win) | (micro_dir == win))
    wick = ((up_wick > np.maximum(20.0, body * 1.25)) & (sd > 0)) | ((lo_wick > np.maximum(20.0, body * 1.25)) & (sd < 0))
    exh = wick | snap | opp | ~stable
    body_with = (body_dir != 0) & (win == body_dir)
    router = int(th["EntryRouterMode"])
    # DecideAction
    action = np.zeros(n, np.int64)
    skip = ~stable
    if th["BlockStrongFlowAgainst"]:
        skip = skip | fd
    exh_route = ~skip & exh & (router >= 2) & (sd != 0)
    action = np.where(exh_route, np.where(sd > 0, A_SL, A_BL), action)
    other = ~skip & ~exh_route & (win != 0)
    neutral = ~fresh | (fl_dir == 0)
    mkt = other & (sd == win) & (f21 | f37) & (router >= 1)
    score = np.where(win > 0, buy, sell)
    weak_ok = ((body_dir == win) & (body >= th["MinCandleBodyPoints"]) & (micro_dir == win)
               & (score >= th["WeakFlowMarketMinScore"]) & (np.abs(buy - sell) >= th["WeakFlowMarketMinScoreEdge"]))
    market = mkt.copy()
    if th["DowngradeNeutralSellMarketToStop"]:
        market = np.where((win < 0) & neutral, False, market)
        down = (win < 0) & neutral
    else:
        down = np.zeros(n, bool)
    if th["WeakFlowMarketNeedsBodyAndMicro"]:
        market = np.where(mkt & ~down & (neutral | fd), weak_ok, market)
    act_other = np.where(market, np.where(win > 0, A_BM, A_SM), np.where(win > 0, A_BS, A_SS))
    action = np.where(other, act_other, action)
    # scenario key (EA 3159-3186)
    S = E
    scn = np.full(n, S.S_OTHER, np.int64)
    # build bottom-up so earlier branches of the EA's chain win
    scn = np.where(exh, S.S_EXH, scn)
    scn = np.where(cont, S.S_CONT, scn)
    scn = np.where(~exh & ~cont & body_with, S.S_BODY, scn)
    scn = np.where(body_with & fa, S.S_BFA, scn)
    scn = np.where(body_with & ~opp, S.S_BNO, scn)
    scn = np.where(body_with & fa & ~opp, S.S_BFNO, scn)
    scn = np.where(body_with & stable & (good_mm | has_follow), S.S_QUAL, scn)
    scn = np.where(body_with & stable & ~opp & (has_follow | good_mm | fa), S.S_FLXQ, scn)
    scn = np.where(body_with & fa & ~opp & has_follow, S.S_BFNF, scn)
    scn = np.where((action == A_BL) | (action == A_SL), S.S_EXHL, scn)
    scn = np.where((action == A_BM) | (action == A_SM), S.S_FOLM, scn)
    fl_lab = np.where(fa, 1, np.where(fd, -1, 0))
    return dict(buy=buy, sell=sell, winner=win, action=action, scn=scn, fl_lab=fl_lab, fl_dir=fl_dir, body_dir=body_dir,
                micro_dir=micro_dir, opp=opp, fresh=fresh)
