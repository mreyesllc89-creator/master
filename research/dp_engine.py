#!/usr/bin/env python3
"""
Python replica of the Danny Phantom "Config C" strategy core (DPFXCore.mqh, DPFXRules.mqh,
DPFXProtection.mqh and the order flow of DPFXMultiMarketEngine.mqh), for calibration.

What the EA does (tester mode, EvaluateEveryTick=true):
  * On every tick it copies the committed state of the last CLOSED bar and pushes the FORMING
    bar (open, high/low so far, the tick as close, volume so far). Signals can therefore fire
    inside a bar. Zones, EMA, ATR and the delta average are only committed when the bar closes.
  * Volume-delta spikes create zones: a bullish spike candle makes a demand zone (key = its
    open..close body), a bearish one a supply zone.
  * A retest of a demand zone by a bullish candle that closes above the previous close and
    the EMA is the "original buy". With tradeOriginalDirection=false (the shipped setting) the
    EA FADES it: original buy -> SELL, original sell -> BUY.
  * An entry is queued and filled on the next tick, with SL = fill -/+ ATR*slMult and
    TP = fill +/- SL*tpR. Time, dead-trade and blackout exits are queued the same way.
  * One decision per bar; an opposite signal reverses an open position.

Tick model here: each M1 bar is one tick. Queued actions fill at the next M1 open; stops and
targets are tested along the M1 path (open, then low/high in candle order, then close); with
intrabar=True signals are evaluated at every M1 close of the forming bar (closest to the EA),
with intrabar=False only at the bar close (TradingView history semantics).
Chart prices are bid; buys fill at the ask (bid + spread), shorts exit at the ask.
"""
import os

import numba as nb
import numpy as np
import pandas as pd

GOLD_DIR = os.environ.get("DP_GOLD_DIR", "/workspace/gianniskas/mt5-m1-bars-us500-eurusd-xauusd")
BTC_DIR = os.environ.get("DP_BTC_DIR", "")

# integer parameter slots
I_ZLEN, I_EMALEN, I_USEEMA, I_MINRET, I_MAXAGE, I_INVAL, I_MODE, I_ZTREND, I_FADE, I_ATRLEN, \
    I_TRAIL, I_TSTOP, I_DEADON, I_DEADBARS, I_BEON, I_OPZ, I_CDON, I_CDBARS, I_LCON, I_LCN, \
    I_LCPAUSE, I_COSTON, I_INTRA, I_WORST, I_PTS, I_LIMDEC, I_LIMFLAT, I_NI = range(28)
# float parameter slots
F_DELTA, F_SL, F_TPR, F_TACT, F_TDST, F_BE, F_COSTMIN, F_MINTICK, F_SLP, F_TPP, F_TACTP, F_TDSTP, F_NF = range(13)


@nb.njit(cache=True)
def _run(o, h, l, c, v, sp, first, last, blk_entry, blk_long, blk_short, blk_exit, P, F):
    nbars = first.shape[0]
    zlen = P[I_ZLEN]; ema_len = P[I_EMALEN]; atr_len = P[I_ATRLEN]
    alpha = 2.0 / (ema_len + 1.0)
    ring = np.zeros(zlen); rsum = 0.0; rcur = 0; dcount = 0
    ema = np.nan; atr = np.nan; tr_seed = 0.0; tr_count = 0; pc = np.nan
    d_top = d_bot = d_kt = d_kb = 0.0; d_idx = 0; d_act = False
    s_top = s_bot = s_kt = s_kb = 0.0; s_idx = 0; s_act = False
    side = 0; avg = 0.0; sl = np.nan; tp = np.nan; e_sl = 0.0; e_tp = np.nan; e_atr = 0.0
    entry_index = -1; trail = np.nan; armed = False; be = False; entry_row = -1
    trail_c = np.nan; armed_c = False; be_c = False   # committed (last closed bar) protection state
    rebase = False                                     # SL/TP still follow the fill bar's ATR
    q_kind = 0; q_side = 0; q_sl = 0.0; q_tp = 0.0; q_atr = 0.0     # queued: 1 entry, 2 close
    q_keep = False                                     # pending distances survive (reversal queued on the final tick)
    last_entry_bar = -1; last_flat_bar = -1
    consec = 0; pause_until = -1; cooldown_until = -1
    pending_closed = 0; closed_pnl = np.zeros(64)
    # trades: entry_row, exit_row, side, pnl, risk, reason
    cap = 2 * o.shape[0] + 16                       # at most two trade records per M1 row
    out = np.empty((cap, 6))
    nt = 0
    for k in range(nbars):
        fo = o[first[k]]; fh = -1e300; fl = 1e300; fv = 0.0
        consume_final = 0
        for j in range(first[k], last[k] + 1):
            bid_o = o[j]; s = sp[j]
            # ---- next tick: dispatch the queued action at this M1 open
            if q_kind != 0 and side != 0:
                # the tester fills the old bracket first; DispatchScheduledEntry then retires the action
                adj = 0.0 if side > 0 else s
                po = bid_o + adj
                g = 0
                if side > 0:
                    if po <= sl: g = 1
                    elif tp == tp and po >= tp: g = 2
                else:
                    if po >= sl: g = 1
                    elif tp == tp and po <= tp: g = 2
                if g != 0:
                    pnl = (po - avg) if side > 0 else (avg - po)
                    out[nt, 0] = entry_row; out[nt, 1] = j; out[nt, 2] = side; out[nt, 3] = pnl
                    out[nt, 4] = e_sl; out[nt, 5] = g - 1
                    nt += 1
                    if pending_closed < 64:
                        closed_pnl[pending_closed] = pnl; pending_closed += 1
                    side = 0; q_kind = 0
            if q_kind != 0:
                if side != 0:
                    px = bid_o if side > 0 else bid_o + s
                    pnl = (px - avg) if side > 0 else (avg - px)
                    out[nt, 0] = entry_row; out[nt, 1] = j; out[nt, 2] = side; out[nt, 3] = pnl
                    out[nt, 4] = e_sl; out[nt, 5] = 2 if q_kind == 2 else 3
                    nt += 1
                    if pending_closed < 64:
                        closed_pnl[pending_closed] = pnl; pending_closed += 1
                    side = 0
                if q_kind == 1:
                    side = q_side
                    avg = bid_o + s if side > 0 else bid_o
                    e_sl = q_sl; e_tp = q_tp; e_atr = q_atr
                    sl = avg - e_sl if side > 0 else avg + e_sl
                    tp = (avg + e_tp if side > 0 else avg - e_tp) if e_tp == e_tp else np.nan
                    entry_index = k; entry_row = j; trail = np.nan; armed = False; be = False
                    trail_c = np.nan; armed_c = False; be_c = False
                    rebase = not q_keep
                q_kind = 0
            # ---- stops / targets along this M1 path (bid chart; shorts exit at the ask)
            if side != 0:
                adj = 0.0 if side > 0 else s
                po = bid_o + adj; ph = h[j] + adj; pl = l[j] + adj; pcl = c[j] + adj
                hit = 0; px = 0.0
                if side > 0:
                    if po <= sl:
                        hit = 1; px = po
                    elif tp == tp and po >= tp:
                        hit = 2; px = po
                    else:
                        slh = pl <= sl; tph = tp == tp and ph >= tp
                        if slh and tph:
                            if P[I_WORST] == 1 or pcl >= po:   # bullish candle: low first
                                hit = 1; px = sl
                            else:
                                hit = 2; px = tp
                        elif slh:
                            hit = 1; px = sl
                        elif tph:
                            hit = 2; px = tp
                else:
                    if po >= sl:
                        hit = 1; px = po
                    elif tp == tp and po <= tp:
                        hit = 2; px = po
                    else:
                        slh = ph >= sl; tph = tp == tp and pl <= tp
                        if slh and tph:
                            if P[I_WORST] == 1 or pcl < po:    # bearish candle: high first
                                hit = 1; px = sl
                            else:
                                hit = 2; px = tp
                        elif slh:
                            hit = 1; px = sl
                        elif tph:
                            hit = 2; px = tp
                if hit != 0:
                    pnl = (px - avg) if side > 0 else (avg - px)
                    out[nt, 0] = entry_row; out[nt, 1] = j; out[nt, 2] = side; out[nt, 3] = pnl
                    out[nt, 4] = e_sl; out[nt, 5] = hit - 1
                    nt += 1
                    if pending_closed < 64:
                        closed_pnl[pending_closed] = pnl; pending_closed += 1
                    side = 0
            # ---- forming bar
            if h[j] > fh: fh = h[j]
            if l[j] < fl: fl = l[j]
            fv += v[j]; fc = c[j]
            if P[I_INTRA] == 0 and j != last[k]:
                continue
            # closed trades are counted before the calculation (DPFClosedTrade, bar = k)
            for t in range(pending_closed):
                if closed_pnl[t] < 0:
                    consec += 1
                else:
                    consec = 0
                if P[I_LCON] == 1 and consec >= P[I_LCN]:
                    pause_until = k + P[I_LCPAUSE]; consec = 0
            pending_closed = 0
            # preview indicators
            ema_f = fc if ema != ema else alpha * fc + (1 - alpha) * ema
            rng = fh - fl
            tr = rng
            if pc == pc:
                tr = max(rng, max(abs(fh - pc), abs(fl - pc)))
            if tr_count + 1 < atr_len:
                atr_f = np.nan
            elif tr_count + 1 == atr_len:
                atr_f = (tr_seed + tr) / atr_len
            else:
                atr_f = tr / atr_len + (1.0 - 1.0 / atr_len) * atr
            if P[I_PTS] == 1:                       # ExitMode = Points (distances in price)
                sl_d = F[F_SLP]
                tp_d = F[F_TPP] if F[F_TPP] > 0 else np.nan
            else:
                sl_d = atr_f * F[F_SL]
                tp_d = sl_d * F[F_TPR] if F[F_TPR] > 0 else np.nan
            cost_block = P[I_COSTON] == 1 and sl_d == sl_d and sl_d < F[F_COSTMIN]
            held = k - entry_index if side != 0 else -1
            long_red = side > 0 and fc <= avg
            short_red = side < 0 and fc >= avg
            dead_l = P[I_DEADON] == 1 and long_red and held >= P[I_DEADBARS]
            dead_s = P[I_DEADON] == 1 and short_red and held >= P[I_DEADBARS]
            t_exit = P[I_TSTOP] > 0 and side != 0 and held >= P[I_TSTOP]
            b_exit = blk_exit[k] and side != 0
            forced = dead_l or dead_s or t_exit or b_exit
            allowed = (not blk_entry[k]) and not (P[I_CDON] == 1 and cooldown_until >= 0 and k < cooldown_until) \
                and not (P[I_LCON] == 1 and pause_until >= 0 and k < pause_until) and not forced
            da = d_act; sa = s_act
            if P[I_INVAL] == 1:
                if da and fc < d_bot: da = False
                if sa and fc > s_top: sa = False
            dv = da and k - d_idx >= P[I_MINRET] and k - d_idx <= P[I_MAXAGE]
            sv = sa and k - s_idx >= P[I_MINRET] and k - s_idx <= P[I_MAXAGE]
            d_touch = dv and fl <= d_kt and fc >= d_kb
            s_touch = sv and fh >= s_kb and fc <= s_kt
            in_d = d_touch and (P[I_MODE] == 0 or fc > d_kt)
            in_s = s_touch and (P[I_MODE] == 0 or fc < s_kb)
            ob = in_d and fc > fo and pc == pc and fc > pc and (P[I_USEEMA] == 0 or fc > ema_f) and allowed and not cost_block
            os_ = in_s and fc < fo and pc == pc and fc < pc and (P[I_USEEMA] == 0 or fc < ema_f) and allowed and not cost_block
            buy = (os_ if P[I_FADE] == 1 else ob) and not blk_long[k]
            sell = (ob if P[I_FADE] == 1 else os_) and not blk_short[k]
            can = (P[I_LIMDEC] == 0 or last_entry_bar != k) and last_flat_bar != k
            intent = 1 if (can and buy and side <= 0) else (-1 if (can and sell and side >= 0) else 0)
            if intent != 0 and q_kind == 0 and atr_f == atr_f and sl_d == sl_d:
                q_kind = 1; q_side = intent; q_sl = sl_d; q_tp = tp_d; q_atr = atr_f
                q_keep = side != 0 and j == last[k]
                last_entry_bar = k
                if P[I_OPZ] == 1 and j == last[k]:
                    from_demand = intent < 0 if P[I_FADE] == 1 else intent > 0
                    consume_final = 1 if from_demand else 2
            # protection: each tick starts from the committed state (DPFProtectionEvaluate on a copy)
            if side != 0:
                if rebase and entry_index == k and atr_f == atr_f:
                    # no pending distances: entry_sl/entry_tp follow this tick's ATR until the fill bar closes
                    e_sl = sl_d; e_tp = tp_d; e_atr = atr_f
                    tp = (avg + e_tp if side > 0 else avg - e_tp) if e_tp == e_tp else np.nan
                base = avg - e_sl if side > 0 else avg + e_sl
                stop = base
                armed = armed_c; trail = trail_c; be = be_c
                if P[I_TRAIL] == 1 and atr_f == atr_f:
                    if P[I_PTS] == 1:
                        act = F[F_TACTP]; dst = F[F_TDSTP]
                    else:
                        act = atr_f * F[F_TACT]; dst = max(atr_f * F[F_TDST], F[F_MINTICK])
                    if side > 0:
                        if fc - avg >= act: armed = True
                        if armed:
                            nx = fc - dst
                            trail = nx if trail != trail else max(trail, nx)
                            stop = max(stop, trail)
                    else:
                        if avg - fc >= act: armed = True
                        if armed:
                            nx = fc + dst
                            trail = nx if trail != trail else min(trail, nx)
                            stop = min(stop, trail)
                if P[I_BEON] == 1:
                    if side > 0 and fc >= avg + e_atr * F[F_BE]: be = True
                    if side < 0 and fc <= avg - e_atr * F[F_BE]: be = True
                    if be: stop = max(stop, avg) if side > 0 else min(stop, avg)
                sl = stop
                if j == last[k]:
                    armed_c = armed; trail_c = trail; be_c = be
            # forced close
            if side != 0 and q_kind == 0 and (P[I_LIMFLAT] == 0 or last_flat_bar != k):
                reason = 0
                if b_exit: reason = 1
                elif dead_l or dead_s: reason = 2
                elif t_exit: reason = 3
                if reason != 0:
                    q_kind = 2; last_flat_bar = k
                    if reason >= 2 and j == last[k]:
                        # losses_current is reset every tick: only a final-tick queue keeps the cooldown
                        cooldown_until = k + P[I_CDBARS]
        # ---- commit the closed bar
        rng = fh - fl; up = 0.5
        if rng != 0:
            up = (fc - fl) / rng
        elif pc == pc and fc > pc:
            up = 1.0
        elif pc == pc and fc < pc:
            up = 0.0
        delta = fv * up - fv * (1 - up)
        rsum -= ring[rcur]; ring[rcur] = abs(delta); rsum += ring[rcur]
        rcur = (rcur + 1) % zlen; dcount += 1
        avg_d = rsum / zlen if dcount >= zlen else np.nan
        ema = fc if ema != ema else alpha * fc + (1 - alpha) * ema
        tr = rng
        if pc == pc:
            tr = max(rng, max(abs(fh - pc), abs(fl - pc)))
        tr_count += 1
        if tr_count <= atr_len:
            tr_seed += tr
            if tr_count == atr_len:
                atr = tr_seed / atr_len
        else:
            atr = tr / atr_len + (1.0 - 1.0 / atr_len) * atr
        if P[I_INVAL] == 1:
            if d_act and fc < d_bot: d_act = False
            if s_act and fc > s_top: s_act = False
        if avg_d == avg_d:
            if delta > avg_d * F[F_DELTA] and fc > fo and (P[I_ZTREND] == 0 or fc > ema):
                d_top = fh; d_bot = fl; d_kt = fc; d_kb = fo; d_idx = k; d_act = True
            if delta < -avg_d * F[F_DELTA] and fc < fo and (P[I_ZTREND] == 0 or fc < ema):
                s_top = fh; s_bot = fl; s_kt = fo; s_kb = fc; s_idx = k; s_act = True
        # Consume runs after Push created this bar's zones (QueueEntry after Push)
        if consume_final == 1: d_act = False
        if consume_final == 2: s_act = False
        pc = fc
    return out[:nt]


# ----------------------------------------------------------------------------- data
def load_m1(symbol):
    """M1 bars with NY time and a per-bar spread in price units."""
    if symbol == "XAUUSD":
        m1 = pd.read_csv(os.path.join(GOLD_DIR, "XAUUSD_m1.csv"), parse_dates=["datetime"])
        server = pd.DatetimeIndex(m1["datetime"])
        ny = server - pd.Timedelta(hours=7)                       # FTMO server = New York + 7h
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        import xlzc_backtest as B
        sp = pd.read_csv(os.path.join(GOLD_DIR, "spreads_summary.csv"))
        sp = sp[sp.symbol == "XAUUSD"].set_index("hour_utc")["mean_spread"].reindex(range(24))
        sp[21] = 60.0
        hourly = sp.interpolate().bfill().ffill().values * 0.01
        spread = hourly[B.server_to_utc_hour(server)]
        spread = spread * float(os.environ.get("DP_SPREAD_MULT", "1"))
        for col in ("open", "high", "low", "close"):          # FTMO bars are mid quotes: chart = bid
            m1[col] = m1[col] - spread / 2
        key = server                                              # bar buckets (whole-hour offset)
    else:
        m1 = pd.read_csv(os.path.join(BTC_DIR, "BTCUSD_m1.csv"), parse_dates=["datetime"])
        utc = pd.DatetimeIndex(m1["datetime"]).tz_localize("UTC")
        ny = utc.tz_convert("America/New_York").tz_localize(None)
        spread = np.full(len(m1), float(os.environ.get("DP_BTC_SPREAD", "10")))
        key = pd.DatetimeIndex(m1["datetime"])
    m1["ny"] = ny
    m1["key"] = key
    m1["spread"] = spread
    return m1.reset_index(drop=True)


def bars_for(m1, tf_min):
    """Bucket M1 rows into tf_min bars: first/last row of each bar and the bar-open NY time."""
    k = m1["key"].values.astype("datetime64[m]").astype(np.int64)
    b = k // tf_min
    starts = np.flatnonzero(np.r_[True, b[1:] != b[:-1]])
    ends = np.r_[starts[1:] - 1, len(b) - 1]
    open_ny = pd.DatetimeIndex(m1["ny"].values[starts]) - pd.to_timedelta(
        (k[starts] - b[starts] * tf_min), unit="m")
    return starts, ends, open_ny


def time_gates(open_ny, cfg):
    """DPFTimeFilters on the bar-open New York time. Returns entry/long/short/exit blocks."""
    dow = ((open_ny.dayofweek.values + 1) % 7) + 1       # Pine: Sunday=1 .. Saturday=7
    hr = open_ny.hour.values; mi = open_ny.minute.values; m = hr * 60 + mi
    gold = cfg.get("gold_filters", False)
    ds, de = 16 * 60 + 55, 18 * 60
    wk = cfg.get("weekend_blackout", True); dl = cfg.get("daily_blackout", True)
    lead = cfg.get("close_lead", 10)
    weekend = wk & (((dow == 6) & (m >= ds)) | (dow == 7) | ((dow == 1) & (m < de)))
    daily = dl & (dow >= 2) & (dow <= 5) & (m >= ds) & (m < de)
    black = weekend | daily
    pre = (wk & (dow == 6) & (m >= ds - lead) & (m < ds)) | (dl & (dow >= 2) & (dow <= 5) & (m >= ds - lead) & (m < ds))
    buf = cfg.get("entry_buffer", 60)
    near = (buf > 0) & (dow >= 2) & (dow <= 6) & (m >= ds - buf) & (m < de)
    sunday = cfg.get("sunday_block", True) & (dow == 1)
    robust = gold & cfg.get("robust_hour", True) & np.isin(hr, [3, 14, 18])
    micro = gold & cfg.get("micro", True)
    v105 = gold & cfg.get("v105", True)
    v1010 = gold & cfg.get("v1010", True)
    long_b = (micro & (hr == 4) & (mi < 15)) | (v105 & (((hr == 10) & (mi >= 15) & (mi < 30)) | ((hr == 11) & (mi >= 30)))) \
        | (v1010 & (((hr == 1) & (mi >= 15) & (mi < 30)) | ((hr == 4) & (mi >= 15) & (mi < 30))))
    short_b = (micro & (hr == 9) & (mi < 15)) | (v1010 & (hr == 4) & (mi >= 45))
    win = cfg.get("window")                               # (start_min, end_min) NY, optional
    outside = np.zeros(len(m), bool)
    if win:
        a, b = win
        outside = ~((m >= a) & (m < b)) if a < b else ~((m >= a) | (m < b))
    custom = np.isin(hr, list(cfg.get("block_hours", ())))     # code-level: recalibrated losing NY hours
    sess = cfg.get("session")                              # useSessionFilter + nySession (start_min, end_min)
    if sess:
        a, b = sess
        outside |= ~((m >= a) & (m < b)) if a < b else ~((m >= a) | (m < b))
    entry = black | near | sunday | robust | outside | custom
    return entry, long_b, short_b, black | pre


DEFAULTS = dict(zlen=50, delta=1.5, ema_len=100, use_ema=1, min_retest=1, max_age=200, inval=1, mode=0,
                ztrend=0, fade=1, atr_len=14, sl=1.2, tpr=4.1667, trail=0, tact=4.0, tdst=0.2,
                tstop=50, dead=0, dead_bars=15, be=0, be_trig=1.0, opz=1, cd=1, cd_bars=10, lc=1,
                lc_n=5, lc_pause=12, cost=1, intrabar=1, worst=0, mintick=0.001, cost_ticks=85,
                cost_ratio=4.0)
GOLD_PROFILE = dict(DEFAULTS, dead=0, lc_n=5, lc_pause=12, cost=1, mintick=0.001, gold_filters=True)
BTC_PROFILE = dict(DEFAULTS, dead=1, dead_bars=15, lc_n=5, lc_pause=12, cost=0, mintick=0.01, gold_filters=False)


def pack(cfg):
    P = np.zeros(I_NI, np.int64); F = np.zeros(F_NF)
    P[I_ZLEN] = cfg["zlen"]; P[I_EMALEN] = cfg["ema_len"]; P[I_USEEMA] = cfg["use_ema"]
    P[I_MINRET] = cfg["min_retest"]; P[I_MAXAGE] = cfg["max_age"]; P[I_INVAL] = cfg["inval"]
    P[I_MODE] = cfg["mode"]; P[I_ZTREND] = cfg["ztrend"]; P[I_FADE] = cfg["fade"]
    P[I_ATRLEN] = cfg["atr_len"]; P[I_TRAIL] = cfg["trail"]; P[I_TSTOP] = cfg["tstop"]
    P[I_DEADON] = cfg["dead"]; P[I_DEADBARS] = cfg["dead_bars"]; P[I_BEON] = cfg["be"]
    P[I_OPZ] = cfg["opz"]; P[I_CDON] = cfg["cd"]; P[I_CDBARS] = cfg["cd_bars"]
    P[I_LCON] = cfg["lc"]; P[I_LCN] = cfg["lc_n"]; P[I_LCPAUSE] = cfg["lc_pause"]
    P[I_COSTON] = cfg["cost"]; P[I_INTRA] = cfg["intrabar"]; P[I_WORST] = cfg["worst"]
    P[I_PTS] = cfg.get("points", 0); P[I_LIMDEC] = cfg.get("lim_dec", 1); P[I_LIMFLAT] = cfg.get("lim_flat", 1)
    mt = cfg["mintick"]
    F[F_SLP] = cfg.get("sl_pts", 5000) * mt; F[F_TPP] = cfg.get("tp_pts", 50000) * mt
    F[F_TACTP] = cfg.get("tact_pts", 1000) * mt; F[F_TDSTP] = max(cfg.get("tdst_pts", 100), 1) * mt
    F[F_DELTA] = cfg["delta"]; F[F_SL] = cfg["sl"]; F[F_TPR] = cfg["tpr"]; F[F_TACT] = cfg["tact"]
    F[F_TDST] = cfg["tdst"]; F[F_BE] = cfg["be_trig"]; F[F_MINTICK] = cfg["mintick"]
    F[F_COSTMIN] = cfg["cost_ratio"] * 2 * cfg["cost_ticks"] * cfg["mintick"]
    return P, F


class Market:
    def __init__(self, symbol):
        self.symbol = symbol
        m1 = load_m1(symbol)
        self.m1 = m1
        self.o = m1["open"].values.astype(float); self.h = m1["high"].values.astype(float)
        self.l = m1["low"].values.astype(float); self.c = m1["close"].values.astype(float)
        self.v = m1["volume"].values.astype(float); self.sp = m1["spread"].values.astype(float)
        self.ny = pd.DatetimeIndex(m1["ny"])
        self.key = pd.DatetimeIndex(m1["key"])
        self._bars = {}

    def bars(self, tf):
        if tf not in self._bars:
            self._bars[tf] = bars_for(self.m1, tf)
        return self._bars[tf]

    def run(self, tf, cfg):
        first, last, open_ny = self.bars(tf)
        entry, lb, sb, ex = time_gates(open_ny, cfg)
        P, F = pack(cfg)
        t = _run(self.o, self.h, self.l, self.c, self.v, self.sp, first, last, entry, lb, sb, ex, P, F)
        df = pd.DataFrame(t, columns=["entry_row", "exit_row", "side", "pnl", "risk", "reason"])
        df["entry_time"] = self.key[df.entry_row.astype(int).values]   # broker/feed time
        df["r"] = df.pnl / df.risk.where(df.risk > 0)
        return df


def stats(pnl):
    pnl = np.asarray(pnl, float)
    if len(pnl) == 0:
        return dict(trades=0, pf=np.nan, net=0.0, win=np.nan)
    w = pnl[pnl > 0].sum(); ls = -pnl[pnl < 0].sum()
    return dict(trades=len(pnl), pf=(w / ls if ls > 0 else np.inf), net=pnl.sum(), win=(pnl > 0).mean())


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"
    mk = Market(sym)
    prof = GOLD_PROFILE if sym == "XAUUSD" else BTC_PROFILE
    for intra in (1, 0):
        df = mk.run(5, dict(prof, intrabar=intra))
        print(sym, "intrabar" if intra else "bar-close", stats(df.pnl), "R-net", round(df.r.sum(), 1))
