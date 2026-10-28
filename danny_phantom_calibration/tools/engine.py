"""Bar-close replica of DannyPhantom V10.21.1 (DPFXCore/DPFXRules/DPFXProtection).

Execution model = TradingView broker emulator on historical bars:
  * the script evaluates on each bar close (calc_on_every_tick has no effect on history);
  * market entries / reversals / forced CLOSEs fill at the next bar open;
  * strategy.exit stop/limit are live from the fill bar (calc_on_order_fills) and resolve
    on the OHLC path (open -> nearer extreme -> farther extreme -> close), gaps fill at open.
Prices: signals on bid OHLC; longs buy the ask and sell the bid, shorts the reverse,
so the recorded spread is the trading cost. `extra_slip` adds price slippage per fill and
`comm_pct` a percentage commission per side.
"""
import numpy as np
from numba import njit

# Resolved parameter vector layout.
NAMES = [
    "zone_len", "delta_thr", "ema_len", "atr_len", "use_ema", "zone_trend", "invalidate",
    "min_retest", "max_age", "entry_close_beyond",
    "exit_atr", "sl_pts", "tp_pts", "sl_atr", "tp_r", "use_trail", "trail_act_pts", "trail_pts",
    "trail_act_atr", "trail_dst_atr", "time_stop",
    "dead_on", "dead_bars", "be_on", "be_trig", "buffer_on", "buffer_min", "sunday_on",
    "window_on", "win_start", "win_end", "one_per_zone", "cooldown_on", "cooldown_bars",
    "session_on", "ses_start", "ses_end",
    "preset_xau", "robust_hour", "micro", "v105", "v1010",
    "loss_on", "loss_count", "loss_pause",
    "cost_on", "min_stop_cost", "slip_ticks", "mintick",
    "weekend_on", "daily_on", "close_lead", "trade_original",
    "qty_risk", "fixed_qty", "risk_pct", "max_qty", "qty_step", "cap_margin", "margin_pct",
    "initial_capital", "point_value", "extra_slip", "comm_pct", "fill_close",
]
IDX = {n: i for i, n in enumerate(NAMES)}
NP = len(NAMES)
for _n, _i in IDX.items():
    globals()["P_" + _n.upper()] = _i

R_STOP, R_TARGET, R_DEAD, R_TIME, R_BLACKOUT, R_REVERSE, R_END = range(7)


@njit(cache=True, inline="always")
def _in_session(m, s, e):
    if s == e:
        return True
    if s < e:
        return m >= s and m < e
    return m >= s or m < e


@njit(cache=True)
def run(bo, bh, bl, bc, ao, ah, al, ac, vol, dow, hour, minute, P,
        t_in, t_out, t_side, t_pnl, t_r, t_reason):
    n = bc.shape[0]
    maxt = t_in.shape[0]
    zl = int(P[0]); thr = P[1]; ema_len = P[2]; atr_len = int(P[3])
    use_ema = P[4] > 0; zone_trend = P[5] > 0; invalidate = P[6] > 0
    min_retest = P[7]; max_age = P[8]; close_beyond = P[9] > 0
    exit_atr = P[10] > 0; mt = P[48]
    use_trail = P[15] > 0; time_stop = P[20]
    dead_on = P[21] > 0; dead_bars = P[22]; be_on = P[23] > 0; be_trig = P[24]
    buffer_on = P[25] > 0; buffer_min = P[26]; sunday_on = P[27] > 0
    window_on = P[28] > 0; win_s = P[29]; win_e = P[30]; one_zone = P[31] > 0
    cd_on = P[32] > 0; cd_bars = P[33]; ses_on = P[34] > 0; ses_s = P[35]; ses_e = P[36]
    xau = P[37] > 0; f_robust = P[38] > 0; f_micro = P[39] > 0; f_105 = P[40] > 0; f_1010 = P[41] > 0
    loss_on = P[42] > 0; loss_cnt = P[43]; loss_pause = P[44]
    cost_on = P[45] > 0; min_sc = P[46]; slip_t = P[47]
    wk_on = P[49] > 0; dl_on = P[50] > 0; lead = P[51]; orig = P[52] > 0
    qty_risk = P[53] > 0; fixed_q = P[54]; risk = P[55]; max_q = P[56]; step = P[57]
    cap_m = P[58] > 0; m_pct = P[59]; equity0 = P[60]; pv = P[61]; xs = P[62]; comm = P[63] / 100.0
    fill_close = P[64] > 0  # process_orders_on_close: market orders fill at the signal bar's close

    alpha = 2.0 / (ema_len + 1.0)
    ring = np.zeros(zl); dsum = 0.0; dcount = 0; cur = 0
    ema = np.nan; atr = np.nan; trseed = 0.0; trcount = 0; prev = np.nan
    d_top = 0.0; d_bot = 0.0; d_kt = 0.0; d_kb = 0.0; d_idx = 0; d_act = False
    s_top = 0.0; s_bot = 0.0; s_kt = 0.0; s_kb = 0.0; s_idx = 0; s_act = False
    side = 0; qty = 0.0; avg = 0.0; e_idx = -1; e_atr = np.nan; e_sl = np.nan; e_tp = np.nan
    stop = np.nan; target = np.nan; armed = False; trail = np.nan; be = False; e_cost = 0.0
    p_kind = 0; p_side = 0; p_qty = 0.0; p_atr = 0.0; p_sl = 0.0; p_tp = 0.0
    consec = 0; pause_until = -1; cd_until = -1
    realized = equity0
    nt = 0
    closed_pnls = np.zeros(4); n_closed = 0

    for i in range(n):
        # ---- 1. orders submitted at the previous close fill at this open
        if p_kind != 0:
            fb = bo[i]; fa = ao[i]; fbar = i
            if side != 0 and (p_kind != 1 or p_side != side):
                px = (fb - xs) if side > 0 else (fa + xs)
                pnl = (px - avg) * side * qty * pv - comm * px * qty * pv - e_cost
                realized += pnl
                if nt < maxt:
                    t_in[nt] = e_idx; t_out[nt] = fbar; t_side[nt] = side; t_pnl[nt] = pnl
                    t_r[nt] = pnl / (e_sl * qty * pv) if e_sl > 0 else 0.0
                    t_reason[nt] = p_kind if p_kind > 2 else R_REVERSE
                    nt += 1
                closed_pnls[n_closed] = pnl; n_closed += 1
                side = 0
            if p_kind == 1 and side == 0 and p_qty > 0:
                side = p_side; qty = p_qty
                avg = (fa + xs) if side > 0 else (fb - xs)
                e_cost = comm * avg * qty * pv
                e_idx = fbar; e_atr = p_atr; e_sl = p_sl; e_tp = p_tp
                armed = False; trail = np.nan; be = False
                stop = avg - side * e_sl if e_sl > 0 else np.nan
                target = avg + side * e_tp if e_tp == e_tp else np.nan
            p_kind = 0
        # ---- 2. protective stop / limit on this bar's path
        if side != 0:
            if side > 0:
                o = bo[i]; h = bh[i]; l = bl[i]
            else:
                o = ao[i]; h = ah[i]; l = al[i]
            hit = 0; px = 0.0
            st = stop; tg = target
            if side > 0:
                if st == st and o <= st:
                    hit = R_STOP + 1; px = o - xs
                elif tg == tg and o >= tg:
                    hit = R_TARGET + 1; px = o
                elif (bh[i] - bo[i]) < (bo[i] - bl[i]):  # high first
                    if tg == tg and h >= tg:
                        hit = R_TARGET + 1; px = tg
                    elif st == st and l <= st:
                        hit = R_STOP + 1; px = st - xs
                else:
                    if st == st and l <= st:
                        hit = R_STOP + 1; px = st - xs
                    elif tg == tg and h >= tg:
                        hit = R_TARGET + 1; px = tg
            else:
                if st == st and o >= st:
                    hit = R_STOP + 1; px = o + xs
                elif tg == tg and o <= tg:
                    hit = R_TARGET + 1; px = o
                elif (bh[i] - bo[i]) < (bo[i] - bl[i]):
                    if st == st and h >= st:
                        hit = R_STOP + 1; px = st + xs
                    elif tg == tg and l <= tg:
                        hit = R_TARGET + 1; px = tg
                else:
                    if tg == tg and l <= tg:
                        hit = R_TARGET + 1; px = tg
                    elif st == st and h >= st:
                        hit = R_STOP + 1; px = st + xs
            if hit:
                pnl = (px - avg) * side * qty * pv - comm * px * qty * pv - e_cost
                realized += pnl
                if nt < maxt:
                    t_in[nt] = e_idx; t_out[nt] = i; t_side[nt] = side; t_pnl[nt] = pnl
                    t_r[nt] = pnl / (e_sl * qty * pv) if e_sl > 0 else 0.0
                    t_reason[nt] = hit - 1
                    nt += 1
                if n_closed < 4:
                    closed_pnls[n_closed] = pnl; n_closed += 1
                side = 0
        # ---- 3. closed trades feed the loss-cluster pause (DPFClosedTrade)
        for k in range(n_closed):
            if closed_pnls[k] < 0:
                consec += 1
            else:
                consec = 0
            if loss_on and consec >= loss_cnt:
                pause_until = i + int(loss_pause); consec = 0
        n_closed = 0
        # ---- 4. DPFEngine.Push on the closed bar
        o = bo[i]; h = bh[i]; l = bl[i]; c = bc[i]
        dw = dow[i]; hr = hour[i]; mi = minute[i]; mny = hr * 60 + mi
        rng = h - l; up = 0.5
        if rng != 0:
            up = (c - l) / rng
        elif prev == prev and c > prev:
            up = 1.0
        elif prev == prev and c < prev:
            up = 0.0
        delta = vol[i] * up - vol[i] * (1.0 - up)
        dsum -= ring[cur]; ring[cur] = abs(delta); dsum += ring[cur]
        cur = (cur + 1) % zl; dcount += 1
        avg_d = dsum / zl if dcount >= zl else np.nan
        ema = c if ema != ema else alpha * c + (1 - alpha) * ema
        tr = rng
        if prev == prev:
            tr = max(rng, max(abs(h - prev), abs(l - prev)))
        trcount += 1
        if trcount <= atr_len:
            trseed += tr
            if trcount == atr_len:
                atr = trseed / atr_len
        else:
            atr = tr / atr_len + (1.0 - 1.0 / atr_len) * atr
        if exit_atr:
            sl_d = atr * P[13]
            tp_d = sl_d * P[14] if P[14] > 0 else np.nan
            t_act = atr * P[18]
            t_dst = max(atr * P[19], mt)
        else:
            sl_d = P[11] * mt
            tp_d = P[12] * mt if P[12] > 0 else np.nan
            t_act = P[16] * mt
            t_dst = P[17] * mt
        costs = 2.0 * slip_t * mt + c * 0.00002
        cost_block = cost_on and sl_d == sl_d and sl_d / costs < min_sc

        # time gates (DPFTimeFilters)
        robust = f_robust and xau and (hr == 3 or hr == 14 or hr == 18)
        l_micro = f_micro and xau and hr == 4 and mi < 15
        s_micro = f_micro and xau and hr == 9 and mi < 15
        l105 = f_105 and xau and ((hr == 10 and mi >= 15 and mi < 30) or (hr == 11 and mi >= 30))
        l1010 = f_1010 and xau and ((hr == 1 and mi >= 15 and mi < 30) or (hr == 4 and mi >= 15 and mi < 30))
        s1010 = f_1010 and xau and hr == 4 and mi >= 45
        ds = 16 * 60 + 55; de = 18 * 60
        wk = wk_on and ((dw == 6 and mny >= ds) or dw == 7 or (dw == 1 and mny < de))
        dly = dl_on and dw >= 2 and dw <= 5 and mny >= ds and mny < de
        blackout = wk or dly
        pre_close = (wk_on and dw == 6 and mny >= ds - lead and mny < ds) or \
                    (dl_on and dw >= 2 and dw <= 5 and mny >= ds - lead and mny < ds)
        near = buffer_on and dw >= 2 and dw <= 6 and mny >= ds - buffer_min and mny < de
        sunday = sunday_on and dw == 1

        held = i - e_idx if side != 0 else -1
        long_red = side > 0 and c <= avg
        short_red = side < 0 and c >= avg
        dead = dead_on and (long_red or short_red) and held >= dead_bars
        time_exit = time_stop > 0 and side != 0 and held >= time_stop
        bl_exit = (blackout or pre_close) and side != 0
        forced = dead or time_exit or bl_exit
        allowed = (not ses_on or _in_session(mny, ses_s, ses_e)) and \
                  (not window_on or _in_session(mny, win_s, win_e)) and \
                  not blackout and not near and not sunday and not robust and \
                  not (cd_on and cd_until >= 0 and i < cd_until) and \
                  not (loss_on and pause_until >= 0 and i < pause_until) and not forced
        if invalidate:
            if d_act and c < d_bot:
                d_act = False
            if s_act and c > s_top:
                s_act = False
        d_valid = d_act and i - d_idx >= min_retest and i - d_idx <= max_age
        s_valid = s_act and i - s_idx >= min_retest and i - s_idx <= max_age
        d_touch = d_valid and l <= d_kt and c >= d_kb
        s_touch = s_valid and h >= s_kb and c <= s_kt
        in_d = d_touch and c > d_kt if close_beyond else d_touch
        in_s = s_touch and c < s_kb if close_beyond else s_touch
        o_buy = in_d and c > o and prev == prev and c > prev and (not use_ema or c > ema) and allowed and not cost_block
        o_sell = in_s and c < o and prev == prev and c < prev and (not use_ema or c < ema) and allowed and not cost_block
        buy = (o_buy if orig else o_sell) and not l_micro and not l105 and not l1010
        sell = (o_sell if orig else o_buy) and not s_micro and not s1010
        if avg_d == avg_d:
            if delta > avg_d * thr and c > o and (not zone_trend or c > ema):
                d_top = h; d_bot = l; d_kt = c; d_kb = o; d_idx = i; d_act = True
            if delta < -avg_d * thr and c < o and (not zone_trend or c < ema):
                s_top = h; s_bot = l; s_kt = o; s_kb = c; s_idx = i; s_act = True
        intent = 1 if (buy and side <= 0) else (-1 if (sell and side >= 0) else 0)
        prev = c

        # ---- 5. decisions (submitted now, filled next open)
        eq = realized
        if side != 0:
            eq += ((bc[i] if side > 0 else ac[i]) - avg) * side * qty * pv
        submitted = False
        if intent != 0 and atr == atr and i + 1 < n:
            if qty_risk:
                sc = sl_d * pv
                q = eq * risk / 100.0 / sc if sc > 0 else 0.0
            else:
                q = fixed_q
            q = min(q, max_q)
            if cap_m and m_pct > 0:
                q = min(q, eq / (c * pv * m_pct / 100.0))
            q = np.floor(q / step + 1e-9) * step
            if q > 0:
                p_kind = 1; p_side = intent; p_qty = q; p_atr = atr; p_sl = sl_d; p_tp = tp_d
                submitted = True
                if one_zone:
                    if (intent > 0) == orig:
                        d_act = False
                    else:
                        s_act = False
        if not submitted and side != 0 and forced and i + 1 < n:
            if bl_exit:
                p_kind = R_BLACKOUT
            elif dead:
                p_kind = R_DEAD
            else:
                p_kind = R_TIME
            if p_kind == R_DEAD or p_kind == R_TIME:
                cd_until = i + int(cd_bars)
        # ---- 5b. process_orders_on_close: the order just submitted fills at this bar's close
        if fill_close and p_kind != 0:
            fb = bc[i]; fa = ac[i]; fbar = i
            if side != 0 and (p_kind != 1 or p_side != side):
                px = (fb - xs) if side > 0 else (fa + xs)
                pnl = (px - avg) * side * qty * pv - comm * px * qty * pv - e_cost
                realized += pnl
                if nt < maxt:
                    t_in[nt] = e_idx; t_out[nt] = fbar; t_side[nt] = side; t_pnl[nt] = pnl
                    t_r[nt] = pnl / (e_sl * qty * pv) if e_sl > 0 else 0.0
                    t_reason[nt] = p_kind if p_kind > 2 else R_REVERSE
                    nt += 1
                if n_closed < 4:
                    closed_pnls[n_closed] = pnl; n_closed += 1
                side = 0
                # a close in the same bar feeds the loss cluster on the next bar (handled by step 3 ordering)
            if p_kind == 1 and side == 0 and p_qty > 0:
                side = p_side; qty = p_qty
                avg = (fa + xs) if side > 0 else (fb - xs)
                e_cost = comm * avg * qty * pv
                e_idx = fbar; e_atr = p_atr; e_sl = p_sl; e_tp = p_tp
                armed = False; trail = np.nan; be = False
                stop = avg - side * e_sl if e_sl > 0 else np.nan
                target = avg + side * e_tp if e_tp == e_tp else np.nan
                submitted = False  # calc_on_order_fills: protection is evaluated for the new position now
            p_kind = 0
        # ---- 6. DPFProtectionEvaluate for the open position
        if side != 0 and not submitted:
            st = avg - side * e_sl if e_sl > 0 else np.nan
            if use_trail:
                if t_act == t_act and (c - avg) * side >= t_act:
                    armed = True
                if armed:
                    nx = c - side * t_dst
                    if trail != trail:
                        trail = nx
                    elif side > 0:
                        trail = max(trail, nx)
                    else:
                        trail = min(trail, nx)
                    if st != st:
                        st = trail
                    elif side > 0:
                        st = max(st, trail)
                    else:
                        st = min(st, trail)
            if be_on:
                if (c - avg) * side >= e_atr * be_trig:
                    be = True
                if be:
                    st = max(st, avg) if side > 0 else min(st, avg)
            stop = st
    # close anything still open at the last close
    if side != 0 and nt < maxt:
        px = bc[n - 1] if side > 0 else ac[n - 1]
        pnl = (px - avg) * side * qty * pv - comm * px * qty * pv - e_cost
        t_in[nt] = e_idx; t_out[nt] = n - 1; t_side[nt] = side; t_pnl[nt] = pnl
        t_r[nt] = pnl / (e_sl * qty * pv) if e_sl > 0 else 0.0
        t_reason[nt] = R_END
        nt += 1
    return nt


def backtest(bars, P, maxt=None):
    n = len(bars["bc"])
    maxt = maxt or max(1000, n // 2)
    t_in = np.zeros(maxt, np.int64); t_out = np.zeros(maxt, np.int64); t_side = np.zeros(maxt, np.int64)
    t_pnl = np.zeros(maxt); t_r = np.zeros(maxt); t_reason = np.zeros(maxt, np.int64)
    nt = run(bars["bo"], bars["bh"], bars["bl"], bars["bc"], bars["ao"], bars["ah"], bars["al"], bars["ac"],
             bars["v"], bars["dow"], bars["hour"], bars["minute"], np.asarray(P, np.float64),
             t_in, t_out, t_side, t_pnl, t_r, t_reason)
    return dict(i=t_in[:nt], o=t_out[:nt], side=t_side[:nt], pnl=t_pnl[:nt], r=t_r[:nt], reason=t_reason[:nt])
