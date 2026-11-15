"""Tokio732_VolLab (engine 3614, version 7.32) ported from Tokio732_VolLab.mq5 to numba.

Only the code paths that the shipped preset can reach are ported (StrategyTick732, ExitSignal,
NewOrderGuard zone rule, VolFactor732, BaseScale732/VolScale732, EntryWindow732, TargetLots732).
Modules that are off in the preset and were not swept are not ported: paired seeds, pyramiding,
resolutions, cash stop, TP, recovery, big-order SL/BE/trail/clock, news filter, recycle, trims,
funded pairs, inventory guard, hazard exit, strict zones, spread cap, idle/flat close.

Tick models: STEP < 0 evaluates the EA once per M1 bar at the recorded close (no assumed
intrabar path). Otherwise every M1 bar is walked open -> first extreme -> second extreme -> close on bid and
ask, each leg interpolated in steps of `STEP` price units, so basket trailing and the basket
stop trigger close to their level instead of at the bar extremes.
"""
import numpy as np
from numba import njit

# parameter vector layout
(LOTS_WITH, LOTS_AGAINST, CROSS_ABOVE, CROSS_BELOW, MIN_MOVE, TRAIL_ON, TRAIL_ARM, TRAIL_GIVE,
 TRAIL_FLOOR, VOL_LOT_ON, VOL_GAMMA, VOL_DIST_ON, VOL_REF, VF_MIN, VF_MAX, MIN_VF, CUSHION_ON,
 CUSHION_BASE, REF_BAL, LOT_MULT, COOLDOWN_MIN, HOUR_FROM, HOUR_TO, MAX_AGE_MIN, LOSS_ON,
 LOSS_PCT, ZONES_ON, ZONE_PAD, RESERVE, UPDATE_TREND, PVL, LOT_MIN, LOT_STEP, START_BAL,
 LEVERAGE, STEP, SLIP, NP) = range(38)

R_STOP, R_AGE, R_TRAIL, R_END, R_STOPOUT = 0, 1, 2, 3, 4
REASONS = ["STOP_PCT_CESTA", "EDAD_MAXIMA", "TRAIL", "FIN_DATOS", "STOP_OUT"]


@njit(cache=True)
def _q(raw, lot_min, lot_step):
    if raw <= 0:
        return 0.0
    v = np.floor((raw + 1e-9) / lot_step) * lot_step
    if v < lot_min - 1e-8:
        return 0.0
    return v


@njit(cache=True)
def run(t, bo, bh, bl, bc, ao, ah, al, ac, trend, atr, P, out):
    """out: (maxb, 8) array -> start, end, reason, net, mae, mfe, vf, balance_before.
    Returns (n_baskets, final_balance, max_dd_pct, min_equity, orders)."""
    n = len(t)
    pvl = P[PVL]; lot_min = P[LOT_MIN]; lot_step = P[LOT_STEP]
    balance = P[START_BAL]
    peak_eq = balance; max_dd = 0.0; min_eq = balance
    active = False
    buys = 0.0; sells = 0.0; buy_cost = 0.0; sell_cost = 0.0
    center = 0.0; zone_h = 0.0; zone_l = 0.0; last_fill = 0.0
    last_order = 0.0; started = 0.0; cooldown = 0.0
    basket_trend = 0; price_side = 0
    scale = 1.0; vol_dist = 1.0; trail_mult = 1.0; vf0 = 1.0
    risk_base = 0.0; peak_net = 0.0; low_net = 0.0; bal0 = 0.0
    nb = 0; orders = 0
    maxb = out.shape[0]
    pb = np.empty(4); pa = np.empty(4)
    dead = False

    for i in range(n):
        if dead:
            break
        tr_i = trend[i]
        a_i = atr[i]
        if a_i > 0:
            vf = min(P[VF_MAX], max(P[VF_MIN], a_i / P[VOL_REF]))
        else:
            vf = 1.0
        if P[VOL_LOT_ON] == 0 and P[VOL_DIST_ON] == 0:
            vf = 1.0
        if not active:
            # cheap bar-level screen: a basket can only start if these hold at the bar open
            if tr_i == 0 or t[i] < cooldown:
                continue
            if P[MIN_VF] > 0 and vf < P[MIN_VF]:
                continue
            if P[HOUR_TO] - P[HOUR_FROM] < 24:
                hr = (t[i] % 86400) / 3600.0
                if P[HOUR_FROM] <= P[HOUR_TO]:
                    if not (hr >= P[HOUR_FROM] and hr < P[HOUR_TO]):
                        continue
                elif not (hr >= P[HOUR_FROM] or hr < P[HOUR_TO]):
                    continue
        # bar path
        pb[0] = bo[i]; pa[0] = ao[i]; pb[3] = bc[i]; pa[3] = ac[i]
        if bc[i] >= bo[i]:
            pb[1] = bl[i]; pa[1] = al[i]; pb[2] = bh[i]; pa[2] = ah[i]
        else:
            pb[1] = bh[i]; pa[1] = ah[i]; pb[2] = bl[i]; pa[2] = al[i]
        close_only = P[STEP] < 0
        for seg in range(-1, 3):
            if dead:
                break
            if close_only and seg != 2:
                continue
            if close_only:
                steps = 1
            elif seg < 0:
                steps = 1
            else:
                steps = int(np.ceil(abs(pb[seg + 1] - pb[seg]) / P[STEP]))
                if steps < 1:
                    steps = 1
            for j in range(1, steps + 1):
                if seg < 0:
                    bid = pb[0]; ask = pa[0]; now = float(t[i])
                else:
                    f = j / steps
                    bid = pb[seg] + (pb[seg + 1] - pb[seg]) * f
                    ask = pa[seg] + (pa[seg + 1] - pa[seg]) * f
                    now = t[i] + 20.0 * (seg + f)
                if ask < bid:
                    ask = bid
                mid = 0.5 * (bid + ask)
                # ---------------- one tick ----------------
                if active:
                    floating = (buys * bid * pvl - buy_cost) + (sell_cost - sells * ask * pvl)
                    net = floating - (buys + sells) * P[RESERVE] * pvl
                    if net < low_net:
                        low_net = net
                    if net > peak_net:
                        peak_net = net
                    eq = balance + floating
                    if eq > peak_eq:
                        peak_eq = eq
                    if eq < min_eq:
                        min_eq = eq
                    dd = (peak_eq - eq) / peak_eq * 100.0
                    if dd > max_dd:
                        max_dd = dd
                    reason = -1
                    if eq <= 0:
                        reason = R_STOPOUT
                    elif P[LOSS_ON] > 0 and net <= -risk_base * P[LOSS_PCT] / 100.0:
                        reason = R_STOP
                    elif P[MAX_AGE_MIN] > 0 and now - started >= P[MAX_AGE_MIN] * 60.0:
                        reason = R_AGE
                    elif (P[TRAIL_ON] > 0 and peak_net >= P[TRAIL_ARM] * trail_mult and
                          net <= max(P[TRAIL_FLOOR] * trail_mult, peak_net - P[TRAIL_GIVE] * trail_mult)):
                        reason = R_TRAIL
                    if reason >= 0:
                        realized = floating - (buys + sells) * P[SLIP] * pvl
                        balance += realized
                        if nb < maxb:
                            out[nb, 0] = started; out[nb, 1] = now; out[nb, 2] = reason
                            out[nb, 3] = realized; out[nb, 4] = low_net; out[nb, 5] = peak_net
                            out[nb, 6] = vf0; out[nb, 7] = bal0
                        nb += 1
                        if (reason == R_STOP or reason == R_AGE) and P[COOLDOWN_MIN] > 0:
                            cooldown = now + P[COOLDOWN_MIN] * 60.0
                        active = False
                        buys = 0.0; sells = 0.0; buy_cost = 0.0; sell_cost = 0.0
                        if balance > peak_eq:
                            peak_eq = balance
                        if balance < min_eq:
                            min_eq = balance
                        if reason == R_STOPOUT or balance <= 0:
                            dead = True
                            break
                        continue  # the EA returns after flattening
                if not active:
                    if tr_i == 0 or now < cooldown:
                        continue
                    if P[MIN_VF] > 0 and vf < P[MIN_VF]:
                        continue
                    if P[HOUR_TO] - P[HOUR_FROM] < 24:
                        hr = (now % 86400.0) / 3600.0
                        if P[HOUR_FROM] <= P[HOUR_TO]:
                            if not (hr >= P[HOUR_FROM] and hr < P[HOUR_TO]):
                                continue
                        elif not (hr >= P[HOUR_FROM] or hr < P[HOUR_TO]):
                            continue
                    if P[CUSHION_ON] > 0:
                        s = P[LOT_MULT] * P[CUSHION_BASE] / P[REF_BAL]
                    else:
                        s = P[LOT_MULT] * max(0.0, balance) / P[REF_BAL]
                    if P[VOL_LOT_ON] > 0 and P[VOL_GAMMA] > 0:
                        s *= vf ** (-P[VOL_GAMMA])
                    if _q(P[LOTS_WITH] * s, lot_min, lot_step) < lot_min - 1e-8:
                        continue
                    risk_base = balance; bal0 = balance
                    zone_h = mid; zone_l = mid; center = mid; last_fill = mid
                    active = True; peak_net = 0.0; low_net = 0.0
                    started = now; last_order = 0.0
                    basket_trend = tr_i; price_side = tr_i
                    scale = s; vf0 = vf
                    vol_dist = vf if P[VOL_DIST_ON] > 0 else 1.0
                    trail_mult = vol_dist
                if P[UPDATE_TREND] > 0 and tr_i != 0:
                    basket_trend = tr_i
                if mid >= center + P[CROSS_ABOVE] * vol_dist:
                    price_side = 1
                elif mid <= center - P[CROSS_BELOW] * vol_dist:
                    price_side = -1
                if now - last_order < 1.0:
                    continue
                if P[MIN_MOVE] > 0 and abs(mid - last_fill) < P[MIN_MOVE] * vol_dist:
                    continue
                size = P[LOTS_WITH] if price_side == basket_trend else P[LOTS_AGAINST]
                desired = price_side * _q(size * scale, lot_min, lot_step)
                diff = desired - (buys - sells)
                if abs(diff) < lot_min - 1e-8:
                    continue
                side = 1 if diff > 0 else -1
                v = _q(abs(diff), lot_min, lot_step)
                if v < lot_min - 1e-8:
                    continue
                if P[ZONES_ON] > 0:
                    if side > 0 and mid < zone_h + P[ZONE_PAD] * vol_dist:
                        continue
                    if side < 0 and mid > zone_l - P[ZONE_PAD] * vol_dist:
                        continue
                # margin: net exposure after the order must be covered by equity
                floating = (buys * bid * pvl - buy_cost) + (sell_cost - sells * ask * pvl)
                need = abs(buys - sells + side * v) * pvl * mid / P[LEVERAGE]
                if need > balance + floating:
                    continue
                if side > 0:
                    buys += v; buy_cost += v * (ask + P[SLIP]) * pvl
                else:
                    sells += v; sell_cost += v * (bid - P[SLIP]) * pvl
                orders += 1
                if mid > zone_h:
                    zone_h = mid
                if mid < zone_l:
                    zone_l = mid
                last_order = now; last_fill = mid
    if active and not dead:
        bid = bc[n - 1]; ask = ac[n - 1]
        floating = (buys * bid * pvl - buy_cost) + (sell_cost - sells * ask * pvl)
        balance += floating
        if nb < maxb:
            out[nb, 0] = started; out[nb, 1] = t[n - 1]; out[nb, 2] = R_END
            out[nb, 3] = floating; out[nb, 4] = low_net; out[nb, 5] = peak_net
            out[nb, 6] = vf0; out[nb, 7] = bal0
        nb += 1
    return nb, balance, max_dd, min_eq, orders
