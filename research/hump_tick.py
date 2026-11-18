#!/usr/bin/env python3
"""
Tick-by-tick execution of the Loma (hump) trades with the EA's own rules (XAUUSD_Loma_TrendPullback.mq5 v1.35).

simulate_tick() takes the inputs of hump_trail2.simulate_y (signals, entry rows on the one-minute bars, the trigger
bar of every minute, level arrays, ATR) and executes every trade on ticks instead of one-minute bars:

Entry   on the first tick of the entry minute (the first tick of the trigger bar after the signal; after a market gap,
        prepare(ea_rows=True) takes the EA's rule, a first tick inside trigger bar S + P or S + 2P of a signal bar S,
        where simulate_y's rows need it by S + 2P: ea_entry_rows), at the ask for a
        buy and the bid for a sell (+/- slippage), when no position is open after that tick's own fills and exits, the
        tick's minute is inside the session, the spread is at most max_spread (in whole points when a point size is
        given, as SpreadOK) and (weekend close on) it is not Friday from weekend_min on. A position closed on that tick
        by the EA itself (time exit, trailing close at market) blocks the entry, as g_timeExitBar / g_trailExitBar do;
        a stop or target filled by the server on that tick does not (the EA enters then: LOMA_V135_CHANGES.md item 14).
        Stop = the signal's hump extreme -/+ the SL buffer -/+ half the entry tick's spread (the EA's sell stop is the
        bid-chart extreme + buffer + spread, i.e. the mid extreme + half the spread); target: entry +/- tp_rr x risk, or
        the previous hump anticipated as the EA does it (simulate_y's target + anticipation x half the entry spread,
        item 13, computed as BuildTradePlan does from the bid-chart extreme = mid extreme - half the entry spread on the
        tick grid, so that a target on a half tick rounds as the EA's; ea_tp 0 gives simulate_y's). On a tick grid (tick > 0) stop and target as NormalizePrice and trailing
        stops as TrailStopPrice (to the looser side); R = |entry fill - stop sent|. The EA's plan checks: risk > 0, risk
        within min_risk / max_risk, reward >= min_rr x risk, and stop and target on the right side of the price by more
        than the stops level (else no trade; simulate_y would enter and leave at once).
Exits   every tick, before the EA runs on it (the server): buy: bid <= stop or bid >= target; sell: ask >= stop or ask
        <= target. Real ticks (fill_level 0): filled at the tick's price, so a stop is filled worse and a target better
        when the price jumps past them. fill_level 1 (the simulated terminal's four points per bar): at the level itself
        except on the first tick of a minute, where a level already passed is filled at that tick's price (the open).
        Then the EA on that tick, in OnTick's order:
          weekend close (weekend_on): from Friday weekend_min on, and on the first tick after it when the position was
          opened before the Saturday 00:00 after that Friday (the catch-up of WeekendClosePositions);
          time exits: max_hold > 0: the position has been open max_hold one-minute bars after its entry bar (minutes
          without ticks do not count) and max_hold x 60 s of clock time (MaxHoldReached); eod >= 0: the tick is at or
          after today's eod minute and the position was opened before it (TimeExitPositions);
          trailing (ManageOpenPositions):
            R (TrailMode 0)        every tick: once bid - entry >= trail_start x R, stop = bid - trail_dist x R (to
                                   the nearest tick), moved when it gains at least `step` and half a point
            step (4)               every tick: fav = the best of this tick and of the completed minutes from the
                                   entry minute on; stop = entry + (floor(fav / a) - 1) x a, a = trail_start x R;
                                   moved when it gains at least `step`
            breakeven              (not in the EA) every tick, as step: entry + trail_dist x R once fav >= trail_start x R
            points, percent (2),   once per closed minute, on the first tick of the next minute: best = highest bid high
            atr (1), profitlock    (buys) / lowest ask low (sells) of the completed minutes from the entry minute on;
            (3), chandelier (5),   levels from the last trigger (or higher) bar closed when the minute opened; the
            levels (6-13 and the   stop is level - buffer - half the current spread (buys) / + (sells); never in the
            study's other level    entry minute; active from the start or once the best profit of the completed
            kinds), timestop       minutes reaches trail_start x R
          A new stop that is through the price closes the position at market on that tick (trailing close); one closer
          to the price than the stops level is not placed; the stop is only tightened; R = |entry - initial stop|.
        partial (not in the EA): half closed when the price reaches entry + trail_start x R (as a limit), the rest's
        stop to the entry on that tick and (trail_dist > 0) trail_dist x R behind the best completed minute.
Result  rows as simulate_y (entry_row, exit_row, side, R, risk) plus the tick details; R = (exit - entry - comm) /
        risk for a buy, (entry - exit - comm) / risk for a sell.

Tick streams (mode):
  0  tick records: server time in ms, bid, ask (gold).
  1  one-second records (BTC): four points per second at the second's time (open, the extreme nearer to the open,
     the other extreme, close; order=1: the farther extreme first), mid -/+ a constant half spread.
  2  one-minute bars as the simulated terminal feeds them: open, adverse extreme, favourable extreme, close at
     seconds 0, 15, 30, 45 (adverse = the low for a buy and when flat, the high for a sell), mid -/+ the bar's half
     spread. Used by the self-test against simulate_y and for the EA parity on the terminal's own feed.

Self-test: [HUMP_SYMBOL=BTCUSD] python3 hump_tick.py [setups per kind]
  (2) hand-made tick paths, one rule at a time; (1) the simulated terminal's four points per real one-minute bar: with
  the EA's extra rules switched off (fill_level 1, plan_checks 0, server_exit_free 0, trail_open 0, ea_tp 0, no time
  rules) every trade must be simulate_y's or be explained by a named rule (classify()); then each EA rule alone with
  the number of trades it changes. The parity with the EA's own code on real ticks is tick_parity.py.
"""
import os, sys
import numba as nb, numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_engine as H, xlzc_backtest as B
import hump_trail as T
import hump_trail2 as T2

KIND = dict(T2.ALLKIND)            # none 0, R 1, points 2, percent 3, atr 4, breakeven 5, step 6, levels 7,
                                   # chandelier 8, profitlock 9, timestop 10, partial 11
EA_MODE = dict(R=0, atr=1, percent=2, profitlock=3, step=4, chandelier=5, candles=6, ema=7, sma=8, psar=9, bollinger=10,
               htfcandle=11, pivots=12, hump=13)
REASON = {1: "SL", 2: "TP", 3: "TRAIL", 4: "MAXHOLD", 5: "EOD", 6: "WEEKEND", 7: "END"}
COLS = ["entry_row", "exit_row", "side", "r", "risk", "entry_q", "exit_q", "entry_px", "exit_px", "reason", "sl0", "tp",
        "stop_last", "entry_ms", "exit_ms", "nmod", "half_px"]


@nb.njit(cache=True)
def _quote(q, side, mode, at, ab, aa, st, so, sh, sl, sc, sdiv, shs, order, bt, bo, bh, bl, bc, bhs):
    """(time in ms, bid, ask) of tick q."""
    if mode == 0:
        return at[q], ab[q], aa[q]
    s = q >> 2
    sub = q & 3
    if mode == 1:
        o = so[s]; h = sh[s]; l = sl[s]; c = sc[s]
        if order == 0:
            low_first = (o - l) <= (h - o)
        else:
            low_first = (o - l) > (h - o)
        if sub == 0:
            p = o
        elif sub == 1:
            p = l if low_first else h
        elif sub == 2:
            p = h if low_first else l
        else:
            p = c
        px = p / sdiv
        return st[s] * 1000, px - shs, px + shs
    o2 = bo[s]; h2 = bh[s]; l2 = bl[s]; c2 = bc[s]
    low_first = side >= 0
    if sub == 0:
        p2 = o2
    elif sub == 1:
        p2 = l2 if low_first else h2
    elif sub == 2:
        p2 = h2 if low_first else l2
    else:
        p2 = c2
    return bt[s] + sub * 15000, p2 - bhs[s], p2 + bhs[s]


@nb.njit(cache=True)
def _normalize(v, tick):
    """MQL5 NormalizeDouble(v, digits) for the digits of the tick size: the double nearest to the decimal value."""
    inv = np.round(1.0 / tick)
    return np.floor(v * inv + 0.5) / inv


@nb.njit(cache=True)
def _round_near(x, tick):
    """The EA's NormalizePrice: MathRound(price / tick) x tick (half away from zero), normalised."""
    if tick <= 0.0:
        return x
    return _normalize(np.floor(x / tick + 0.5) * tick, tick)


@nb.njit(cache=True)
def _round_loose(x, tick, side):
    """The EA's TrailStopPrice: on the tick grid, down for a buy, up for a sell (1e-7 tick of floating-point noise)."""
    if tick <= 0.0:
        return x
    v = x / tick
    if side > 0:
        return _normalize(np.floor(v + 1e-7) * tick, tick)
    return _normalize(np.ceil(v - 1e-7) * tick, tick)


@nb.njit(cache=True)
def _wk_end(t_s, wk_min):
    """Saturday 00:00 (server seconds) after the most recent Friday weekend_min moment at or before t_s."""
    day = t_s // 86400
    dow = (day + 3) % 7                      # Monday 0 ... Friday 4 ... Sunday 6 (1970-01-01 was a Thursday)
    back = (dow - 4) % 7
    m = (day - back) * 86400 + wk_min * 60
    if m > t_s:
        m -= 7 * 86400
    return (m // 86400 + 1) * 86400


@nb.njit(cache=True)
def simulate_tick(sig, entry_row, rq0, rq1, bar_bh, bar_al,
                  mode, at, ab, aa, st, so, sh, sl_, sc, sdiv, shs, order, bt, bo, bh, bl, bc, bhs,
                  s0, s1, buf, anticip, min_rr, tp_mode, tp_rr, trail_start, trail_dist, max_spread, min_risk, max_risk,
                  slip, comm, delay, max_hold, eod, wk_on, wk_min, trail_kind, tb, lvl_hi, lvl_lo, aux,
                  step, point, tick, stops_level, fill_level, plan_checks, server_exit_free, trail_open, busy_q0, busy_block0,
                  ea_tp):
    """See the module docstring. rq0[j], rq1[j]: tick range of one-minute row j; bar_bh[j]: highest bid of row j;
    bar_al[j]: lowest ask of row j (the sell side's best price of a completed minute). Returns one row per trade with
    the columns of COLS."""
    n = len(rq0)
    out = np.empty((len(sig), 17))
    m = 0
    busy_q = busy_q0                             # exit tick of the last trade (-1: none; a chunked run passes the last one)
    busy_block = busy_block0 == 1                # that exit was the EA's own (time exit, trailing close): no entry on it
    for k in range(len(sig)):
        e = entry_row[k]
        if e < 0:
            continue
        e += delay
        if e >= n:
            continue
        qe = rq0[e]
        if qe < busy_q or (qe == busy_q and busy_block):
            continue
        side = int(sig[k, 1])
        te, bid, ask = _quote(qe, side, mode, at, ab, aa, st, so, sh, sl_, sc, sdiv, shs, order, bt, bo, bh, bl, bc, bhs)
        tod = (te // 60000) % 1440
        if not (s0 <= tod < s1) if s0 < s1 else not (tod >= s0 or tod < s1):
            continue
        spr = ask - bid
        if point > 0.0:                          # SpreadOK: the spread in whole points against MaxSpread_Points
            if np.floor(spr / point + 0.5) > np.floor(max_spread / point + 0.5):
                continue
        elif spr > max_spread + 1e-9:
            continue
        te_s = te // 1000
        if wk_on == 1 and ((te_s // 86400) + 3) % 7 == 4 and tod >= wk_min:
            continue                             # PreWeekendEntryBlock
        hs_e = 0.5 * spr
        atr = sig[k, 5]
        if side > 0:
            entry = ask + slip
            sl0 = _round_near(sig[k, 2] - buf - hs_e, tick)
        else:
            entry = bid - slip
            sl0 = _round_near(sig[k, 2] + buf + hs_e, tick)
        risk = side * (entry - sl0)
        if not (risk == risk):
            continue
        if risk <= 0.0 or risk < min_risk or risk > max_risk:
            continue
        if tp_mode == 0:
            ref = sig[k, 3]
            if ea_tp == 1:                       # the EA anticipates from the bid-chart extreme (item 13: + anticip x
                refb = _round_near(ref - hs_e, tick)     # half spread on both sides), in BuildTradePlan's own arithmetic
                if side > 0:                     # (a target on a half tick rounds as the EA's: TP_Anticipation 0.1 x
                    tp = refb - anticip * (refb - entry)              # an odd number of 5 cents, e.g.)
                else:
                    tp = refb + anticip * (entry - refb) + spr
            elif side > 0:
                tp = ref - anticip * (ref - entry) - hs_e
            else:
                tp = ref + anticip * (entry - ref) + hs_e
        else:
            tp = entry + side * tp_rr * risk
        tp = _round_near(tp, tick)
        if side * (tp - entry) < min_rr * risk:
            continue
        if plan_checks == 1:                     # BuildTradePlan: stop and target beyond the stops level from the price
            if side > 0:
                if bid - sl0 <= stops_level or tp - bid <= stops_level:
                    continue
            else:
                if sl0 - ask <= stops_level or ask - tp <= stops_level:
                    continue
        if trail_kind == 1:
            unit = risk
        elif trail_kind == 2:
            unit = 1.0
        elif trail_kind == 3:
            unit = 0.01 * entry
        else:
            unit = atr
        stop = sl0
        nmod = 0
        part = False
        half_px = np.nan
        hl = entry + side * trail_start * risk   # partial: the half-close level
        act = trail_start <= 0.0
        bestc = np.nan                           # best price of the completed minutes from the entry minute on
        px = np.nan
        reason = 0
        xq = -1
        xrow = e
        block = False
        open_s = te_s
        j = e
        if plan_checks == 0:                     # no plan check: a stop or target already crossed at entry is filled on
            if side * ((bid if side > 0 else ask) - stop) <= 0.0:          # the entry tick itself (as simulate_y at the open)
                px = (bid if side > 0 else ask) - side * slip; reason = 1; xq = qe; j = n + 1
            elif side * ((bid if side > 0 else ask) - tp) >= 0.0:
                px = bid if side > 0 else ask; reason = 2; xq = qe; j = n + 1
        while j < n:
            if j > e:
                pv = bar_bh[j - 1] if side > 0 else bar_al[j - 1]
                if bestc != bestc:
                    bestc = pv
                elif side > 0:
                    if pv > bestc:
                        bestc = pv
                else:
                    if pv < bestc:
                        bestc = pv
                if (not act) and side * (bestc - entry) >= trail_start * risk:
                    act = True
            qa = rq0[j] if j > e else qe + 1
            for q in range(qa, rq1[j]):
                first = q == rq0[j]
                t, bid, ask = _quote(q, side, mode, at, ab, aa, st, so, sh, sl_, sc, sdiv, shs, order, bt, bo, bh, bl, bc, bhs)
                pr = bid if side > 0 else ask    # the price the position is valued and closed at
                # ---- the server: stop, then target (then, partial, the half-close limit)
                if side * (pr - stop) <= 0.0:
                    lvl = pr if (fill_level == 0 or first) else stop
                    px = lvl - side * slip; reason = 1; xq = q; break
                if side * (pr - tp) >= 0.0:
                    px = pr if (fill_level == 0 or first) else tp
                    if trail_kind == 11 and (not part) and side * (pr - hl) >= 0.0 and side * (hl - tp) <= 1e-9 * risk:
                        part = True
                        half_px = pr if (fill_level == 0 or first) else hl
                    reason = 2; xq = q; break
                if trail_kind == 11 and (not part) and side * (pr - hl) >= 0.0:
                    part = True
                    half_px = pr if (fill_level == 0 or first) else hl
                    if side * (entry - stop) > 0.0:
                        stop = entry; nmod += 1  # the rest's stop to breakeven, from the next tick
                t_s = t // 1000
                # ---- the EA: weekend close, time exits, trailing
                if wk_on == 1 and open_s < _wk_end(t_s, wk_min):
                    px = pr - side * slip; reason = 6; xq = q; break
                if max_hold > 0 and (j - e) >= max_hold and (t_s - open_s) >= max_hold * 60:
                    px = pr - side * slip; reason = 4; xq = q; block = True; break
                if eod >= 0:
                    em = (t_s // 86400) * 86400 + eod * 60
                    if t_s >= em and open_s < em:
                        px = pr - side * slip; reason = 5; xq = q; block = True; break
                if trail_kind == 0:
                    continue
                if first and trail_open == 0 and (trail_kind == 1 or trail_kind == 5 or trail_kind == 6):
                    continue                     # test switch: the per-tick systems skip a minute's first tick
                cand = np.nan
                min_step = 0.0
                if trail_kind == 1:
                    if trail_start > 0.0 and side * (pr - entry) >= trail_start * risk:
                        new = _round_near(pr - side * trail_dist * risk, tick)
                        if side > 0:
                            ok = new >= stop + step and new > stop + 0.5 * point and pr - new > stops_level
                        else:
                            ok = new <= stop - step and new < stop - 0.5 * point and new - pr > stops_level
                        if ok:
                            stop = new; nmod += 1
                    continue
                elif trail_kind == 6 or trail_kind == 5:
                    fav = side * (pr - entry)
                    if j > e:
                        fb = side * (bestc - entry)
                        if fb > fav:
                            fav = fb
                    if trail_kind == 6:
                        a = trail_start * risk
                        if a > 0.0 and fav >= a:
                            kk = np.floor(fav / a)
                            cand = entry + side * (kk - 1.0) * a
                            min_step = step
                    else:
                        if trail_start > 0.0 and fav >= trail_start * risk:
                            cand = entry + side * trail_dist * risk
                elif first and j > e:
                    fav = side * (bestc - entry)
                    if trail_kind >= 2 and trail_kind <= 4:
                        if trail_start > 0.0 and fav >= trail_start * unit:
                            cand = bestc - side * trail_dist * unit
                    elif trail_kind == 9:
                        if trail_start > 0.0 and fav >= trail_start * risk:
                            cand = entry + side * trail_dist * fav
                    elif trail_kind == 7 or trail_kind == 8:
                        if act:
                            i = tb[j]
                            if i >= 0:
                                if trail_kind == 8:
                                    av = aux[i]
                                    if av == av:
                                        bb = bestc
                                        if side * (bb - entry) < 0.0:
                                            bb = entry
                                        cand = bb - side * trail_dist * av
                                else:
                                    lv = lvl_lo[i] if side > 0 else lvl_hi[i]
                                    if lv == lv:
                                        cand = lv - side * (buf + 0.5 * (ask - bid))
                    elif trail_kind == 10:
                        frac = (j - e) / trail_dist
                        if frac > 1.0:
                            frac = 1.0
                        cand = sl0 + side * frac * (side * (entry - sl0))
                    elif trail_kind == 11:
                        if part and trail_dist > 0.0:
                            cand = bestc - side * trail_dist * risk
                if cand == cand:                 # TrailApply
                    new = _round_loose(cand, tick, side)
                    if new > 0.0:
                        if side > 0:
                            ok = new >= stop + min_step and new > stop + 0.5 * point
                        else:
                            ok = new <= stop - min_step and new < stop - 0.5 * point
                        if ok:
                            if side * (pr - new) <= 0.0:
                                px = pr - side * slip; reason = 3; xq = q; block = True; break
                            if abs(new - pr) > stops_level:
                                stop = new; nmod += 1
            if xq >= 0:
                xrow = j
                break
            j += 1
        if j == n + 1:
            xrow = e
        if xq < 0:                               # still open at the end of the data: valued at the last tick
            xrow = n - 1
            xq = rq1[n - 1] - 1
            t, bid, ask = _quote(xq, side, mode, at, ab, aa, st, so, sh, sl_, sc, sdiv, shs, order, bt, bo, bh, bl, bc, bhs)
            px = bid if side > 0 else ask
            reason = 7
        else:
            t, bid, ask = _quote(xq, side, mode, at, ab, aa, st, so, sh, sl_, sc, sdiv, shs, order, bt, bo, bh, bl, bc, bhs)
        r = (side * (px - entry) - comm) / risk
        if part:
            r = 0.5 * (side * (half_px - entry) - comm) / risk + 0.5 * r
        out[m, 0] = e; out[m, 1] = xrow; out[m, 2] = side; out[m, 3] = r; out[m, 4] = risk
        out[m, 5] = qe; out[m, 6] = xq; out[m, 7] = entry; out[m, 8] = px; out[m, 9] = reason
        out[m, 10] = sl0; out[m, 11] = tp; out[m, 12] = stop; out[m, 13] = te; out[m, 14] = t; out[m, 15] = nmod
        out[m, 16] = half_px
        m += 1
        busy_q = xq
        busy_block = block or server_exit_free == 0
    return out[:m]


# ----------------------------------------------------------------------------- tick streams
_I32 = np.zeros(1, np.int32)
_I64 = np.zeros(1, np.int64)
_F64 = np.zeros(1, np.float64)


class Stream:
    """A tick stream over the one-minute rows of a bar series (see the module docstring for the modes).
    rq0 / rq1: tick range of every row; bar_bh / bar_al: highest bid and lowest ask of every row."""

    def __init__(self, mode, rq0, rq1, bar_bh, bar_al, at=_I64, ab=_F64, aa=_F64, st=_I64, so=_I32, sh=_I32, sl=_I32,
                 sc=_I32, sdiv=1.0, shs=0.0, order=0, bt=_I64, bo=_F64, bh=_F64, bl=_F64, bc=_F64, bhs=_F64):
        self.mode = int(mode)
        self.rq0 = np.ascontiguousarray(rq0, np.int64); self.rq1 = np.ascontiguousarray(rq1, np.int64)
        self.bar_bh = np.ascontiguousarray(bar_bh, np.float64); self.bar_al = np.ascontiguousarray(bar_al, np.float64)
        self.arr = (np.ascontiguousarray(at, np.int64), np.ascontiguousarray(ab, np.float64), np.ascontiguousarray(aa, np.float64),
                    np.ascontiguousarray(st, np.int64), np.ascontiguousarray(so, np.int32), np.ascontiguousarray(sh, np.int32),
                    np.ascontiguousarray(sl, np.int32), np.ascontiguousarray(sc, np.int32), float(sdiv), float(shs), int(order),
                    np.ascontiguousarray(bt, np.int64), np.ascontiguousarray(bo, np.float64), np.ascontiguousarray(bh, np.float64),
                    np.ascontiguousarray(bl, np.float64), np.ascontiguousarray(bc, np.float64), np.ascontiguousarray(bhs, np.float64))

    def with_order(self, order):
        s = Stream.__new__(Stream)
        s.__dict__.update(self.__dict__)
        a = list(self.arr); a[10] = int(order); s.arr = tuple(a)
        return s

    def quote(self, q, side=1):
        return _quote(int(q), int(side), self.mode, *self.arr)


def bar_stream(bars, hs):
    """Mode 2: the simulated terminal's four points per one-minute bar (mid bars, per-bar half spread)."""
    n = len(bars)
    hs = np.broadcast_to(np.asarray(hs, float), (n,)).copy()
    o, h, l, c = (bars[k].values.astype(float) for k in ("open", "high", "low", "close"))
    t = bars.index.values.astype("datetime64[ms]").astype(np.int64)
    q0 = np.arange(n, dtype=np.int64) * 4
    return Stream(2, q0, q0 + 4, h - hs, l + hs, bt=t, bo=o, bh=h, bl=l, bc=c, bhs=hs)


def second_stream(sec, st_rows, en_rows, half, div=100.0, order=0):
    """Mode 1: BTC seconds (tick_data.BtcSeconds) over the rows of tick_data.btc_m1 (second ranges st_rows, en_rows)."""
    bh_ = np.maximum.reduceat(sec.h, st_rows) / div - half
    al_ = np.minimum.reduceat(sec.l, st_rows) / div + half
    return Stream(1, 4 * np.asarray(st_rows, np.int64), 4 * np.asarray(en_rows, np.int64), bh_, al_,
                  st=sec.t, so=sec.o, sh=sec.h, sl=sec.l, sc=sec.c, sdiv=div, shs=half, order=order)


def tick_stream(t_ms, bid, ask, st_rows, en_rows, sell_best="ask_low"):
    """Mode 0: gold ticks (server ms, bid, ask) over the rows of tick_data.gold_m1. sell_best: the sell side's best price
    of a completed minute, 'ask_low' (lowest ask of the minute) or 'bid_low_min_spread' (lowest bid + the minute's
    smallest spread: MqlRates.spread taken as the bar's minimum spread)."""
    st_rows = np.asarray(st_rows, np.int64)
    bh_ = np.maximum.reduceat(bid, st_rows)
    if sell_best == "ask_low":
        al_ = np.minimum.reduceat(ask, st_rows)
    else:
        al_ = np.minimum.reduceat(bid, st_rows) + np.minimum.reduceat(ask - bid, st_rows)
    return Stream(0, st_rows, np.asarray(en_rows, np.int64), bh_, al_, at=t_ms, ab=bid, aa=ask)


# ----------------------------------------------------------------------------- inputs as run_y prepares them
def ea_entry_rows(mk, tf, ix):
    """The EA's entry row of each signal (trigger bar index ix, open time S, period P): the first one-minute bar at or
    after the signal bar's close S + P, when it opens before S + 3P, else -1. EvaluateSignal calls a signal stale when
    the trigger bar it is evaluated on opens more than 2P after S (XAUUSD_Loma_TrendPullback.mq5, 'is stale (market
    gap)'), so the EA enters when the market reopens inside trigger bar S + P or S + 2P. simulate_y's rows
    (hump_engine.Market.tf) need that bar to open by S + 2P: the two differ when it opens in (S + 2P, S + 3P), which
    only a market gap does (never on M1)."""
    t = mk._tf[tf]["t"].index.values
    P = np.timedelta64(B.TF_MIN[tf], "m")
    nxt = t[ix] + P
    row = np.searchsorted(mk.t, nxt)
    ok = row < len(mk.t)
    late = np.where(ok, mk.t[np.clip(row, 0, len(mk.t) - 1)] - nxt, np.timedelta64(10 ** 9, "m"))
    return np.where(ok & (late < 2 * P), row, -1).astype(np.int64)


def prepare(mk, cfg, ea_rows=False):
    """The arrays hump_trail2.MarketY.run_y passes to simulate_y, for the configuration cfg (engine keys). ea_rows: the
    entry rows by the EA's rule for a signal after a market gap (ea_entry_rows) instead of simulate_y's."""
    c = dict(H.DEFAULT); c.update(cfg)
    assert int(c["sl_mode"]) == 0 and int(c["tp_mode"]) in (0, 1)
    fast, slow = int(c["macd_fast"]), int(c["macd_slow"])
    hi, lo, macd, stk, row, bias, atr = mk.tf(c["tf"], fast, slow, int(c["stoch_k"]))
    sg = H.signals(hi, lo, macd, stk, c["big_mult"], int(c["hist"]), int(c["big_min_bars"]), int(c["stoch_req"]),
                   int(c["pb_min_bars"]), c["pb_max_ratio"], c["break_ratio"], int(c["max_signals"]),
                   int(c["trend_max_bars"]), int(c["sides"]), int(c["classic"]), int(c["skip_big_pb"]),
                   c["stoch_lo"], c["stoch_hi"])
    if c.get("htf", "none") != "none" and len(sg):
        sg = sg[bias[(c["htf"], int(c["htf_ema"]))][sg[:, 0].astype(np.int64)] == sg[:, 1]]
    ix = sg[:, 0].astype(np.int64) if len(sg) else np.zeros(0, np.int64)
    sg = np.column_stack([sg, atr[ix]]) if len(sg) else np.zeros((0, 6))
    er = ea_entry_rows(mk, c["tf"], ix) if ea_rows else row[ix]
    kind = c.get("trail_kind", "R")
    tk = KIND[kind]
    tb = mk._tb(c["tf"])
    if tk == 7:
        lh, ll = mk._levels(c["tf"], kind, c.get("trail_p", 0), fast, slow)
    else:
        lh = ll = np.zeros(1)
    aux = atr if tk == 8 else np.zeros(1)
    ts = 0.0 if tk == 0 else float(c["trail_start"])
    s0, s1 = H.SESSIONS[c["session"]]
    if c["weekend_close"]:
        wk = ((mk.dow == 4) & (mk.tod >= int(c["weekend_min"]))) | mk.pre_gap
    else:
        wk = np.zeros(len(mk.t), np.bool_)
    return dict(c=c, sg=np.ascontiguousarray(sg, np.float64), er=np.ascontiguousarray(er, np.int64), tk=tk, tb=tb,
                lh=np.ascontiguousarray(lh, np.float64), ll=np.ascontiguousarray(ll, np.float64),
                aux=np.ascontiguousarray(aux, np.float64), ts=ts, s0=s0, s1=s1, wk=wk)


def run_y(mk, prep):
    """simulate_y on the prepared arrays, exactly as MarketY.run_y."""
    c = prep["c"]
    tr = T2.simulate_y(prep["sg"], prep["er"], mk.o, mk.h, mk.l, mk.c, mk.hs, mk.tod, prep["s0"], prep["s1"], c["buf"], c["anticip"],
                       c["min_rr"], int(c["tp_mode"]), c["tp_rr"], prep["ts"], float(c["trail_dist"]),
                       c["max_spread"], c["min_risk"], c["max_risk"], c["slip"], c["comm"], int(c["delay"]),
                       int(c["trail_worst"]), prep["wk"], int(c["max_hold"]), int(c["eod"]), prep["tk"], prep["tb"],
                       prep["lh"], prep["ll"], prep["aux"], int(c.get("trail_closed", 1)))
    df = pd.DataFrame(tr, columns=["entry_row", "exit_row", "side", "r", "risk"])
    df["entry_time"] = mk.t[df.entry_row.astype(int).values] if len(df) else pd.Series(dtype="datetime64[ns]")
    return df


EA_DEFAULT = dict(step=0.0, point=0.0, tick=0.0, stops_level=0.0, fill_level=0, plan_checks=1, time_rules=1, server_exit_free=1,
                  trail_open=1, ea_tp=1)


def run_tick(mk, prep, stream, ea=None, sel=None, busy=(-1, 0)):
    """simulate_tick on the prepared arrays and a tick stream. ea: execution settings (EA_DEFAULT keys):
      step         TrailStep_Points as a price (RISK and STEP move the stop only by at least this much)
      point        the symbol's point (a move must also gain half a point); 0 = off
      tick         tick grid of stops and targets (initial stop and target to the nearest tick, trailing stops to the
                   looser side); 0 = unrounded, as simulate_y
      stops_level  broker stops level as a price
      fill_level   0 real ticks (tick price), 1 the simulated terminal's four-point bars (level, open on a gap)
      plan_checks  1: the EA's BuildTradePlan checks of stop and target against the price at entry
      time_rules   1: the EA's time exits and weekend close; 0: none at all (max_hold, eod and the weekend close off)
      server_exit_free  1 (the EA): a stop or target filled by the server on the first tick of an entry minute does not
                   block that entry; 0: no entry on the exit tick of the previous trade (simulate_y's one-position rule)
      trail_open   1 (the EA): RISK, STEP and breakeven also act on the first tick of a minute; 0 (test switch): not on
                   it, which is the order simulate_y gives a bar (the stop is tested on the low before it moves)
      plan_checks  also: with 0, a stop or target already crossed at entry is filled on the entry tick (simulate_y)
      ea_tp        1 (the EA): the previous-hump target is anticipated from the bid-chart extreme, anticip x half the
                   entry spread further than simulate_y's for a buy, nearer for a sell (item 13); 0: simulate_y's"""
    e = dict(EA_DEFAULT); e.update(ea or {})
    c = prep["c"]
    tr_on = int(e["time_rules"]) == 1
    sg, er = (prep["sg"], prep["er"]) if sel is None else (np.ascontiguousarray(prep["sg"][sel]), np.ascontiguousarray(prep["er"][sel]))
    tr = simulate_tick(sg, er, stream.rq0, stream.rq1, stream.bar_bh, stream.bar_al, stream.mode, *stream.arr,
                       prep["s0"], prep["s1"], c["buf"], c["anticip"], c["min_rr"], int(c["tp_mode"]), c["tp_rr"], prep["ts"],
                       float(c["trail_dist"]), c["max_spread"], c["min_risk"], c["max_risk"], c["slip"], c["comm"], int(c["delay"]),
                       int(c["max_hold"]) if tr_on else 0, int(c["eod"]) if tr_on else -1,
                       1 if (tr_on and c["weekend_close"]) else 0, int(c["weekend_min"]), prep["tk"], prep["tb"], prep["lh"],
                       prep["ll"], prep["aux"], float(e["step"]), float(e["point"]), float(e["tick"]), float(e["stops_level"]),
                       int(e["fill_level"]), int(e["plan_checks"]), int(e["server_exit_free"]), int(e["trail_open"]),
                       int(busy[0]), int(busy[1]), int(e["ea_tp"]))
    df = pd.DataFrame(tr, columns=COLS)
    for col in ("entry_row", "exit_row", "side", "entry_q", "exit_q", "reason", "entry_ms", "exit_ms", "nmod"):
        df[col] = df[col].astype(np.int64)
    df["entry_time"] = mk.t[df.entry_row.values] if len(df) else pd.Series(dtype="datetime64[ns]")
    return df


# ----------------------------------------------------------------------------- self-test
def trade_diff(y, t):
    """Trades of simulate_y (y) against simulate_tick (t), matched by entry row and side: counts of trades only on one
    side and of matched trades with another exit row or another R (|dR| > 1e-9)."""
    ky = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(y.entry_row, y.side))}
    kt = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(t.entry_row, t.side))}
    both = set(ky) & set(kt)
    ex = sum(int(y.exit_row.iloc[ky[k]]) != int(t.exit_row.iloc[kt[k]]) for k in both)
    rr = sum(int(y.exit_row.iloc[ky[k]]) == int(t.exit_row.iloc[kt[k]]) and abs(float(y.r.iloc[ky[k]]) - float(t.r.iloc[kt[k]])) > 1e-9
             for k in both)
    return dict(only_y=len(set(ky) - set(kt)), only_tick=len(set(kt) - set(ky)), exit_row=ex, r=rr, n_y=len(y), n_tick=len(t))


def classify(y, t, stream, kind="", ts=0.0):
    """The trades that differ between simulate_y (y) and simulate_tick (t) on the four-point feed, each put under the
    rule that explains it; 'unexplained' must stay empty in the strict test.
      target at the open   the minute opens beyond the target; the tick order fills the target there, simulate_y tests
                           the minute's low (high for a sell) against the stop first and takes the stop
      partial half at the open   (partial only) the half-close level is passed at a minute's open: the tick engine
                           books the half at that open price (a limit filled on a gap), simulate_y at the level"""
    ky = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(y.entry_row, y.side))}
    kt = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(t.entry_row, t.side))}
    out = {"target at the open": 0, "partial half at the open": 0, "unexplained": []}
    for k in sorted(set(ky) | set(kt)):
        if k not in ky or k not in kt:
            out["unexplained"].append(("only one side", k)); continue
        a = y.iloc[ky[k]]; b = t.iloc[kt[k]]
        if int(a.exit_row) == int(b.exit_row) and abs(float(a.r) - float(b.r)) <= 1e-9:
            continue
        if int(b.reason) == 2 and int(b.exit_q) == int(stream.rq0[int(b.exit_row)]) and int(a.exit_row) == int(b.exit_row) and float(a.r) < float(b.r):
            out["target at the open"] += 1; continue
        if kind == "partial" and int(a.exit_row) == int(b.exit_row) and b.half_px == b.half_px:
            hl = float(b.entry_px) + int(b.side) * ts * float(b.risk)
            gain = 0.5 * int(b.side) * (float(b.half_px) - hl) / float(b.risk)
            if gain > 0 and abs(float(b.r) - float(a.r) - gain) < 1e-9:
                out["partial half at the open"] += 1; continue
        out["unexplained"].append((k, int(a.exit_row), int(b.exit_row), float(a.r), float(b.r), int(b.reason)))
    return out


def _setups(rng, n_per_kind, X):
    lv = {"candles": (1, 2, 3, 5, 8, 13), "ema": (8, 13, 21, 34, 50), "psar": (0, 1, 2), "hump": (0,), "supertrend": (0, 1, 2),
          "keltner": (0, 1, 2), "bollinger": (0, 1), "kijun": (13, 26, 52), "pivots": (2, 3, 5), "sma": (10, 20, 50), "donchian": (20, 55),
          "htfcandle": (15, 30, 60, 240)}
    ps, pd_ = ((50, 100, 200, 400), (25, 50, 100, 200)) if H.SYMBOL == "BTCUSD" else ((1, 2, 4, 8), (0.5, 1, 2, 4))
    grid = {"none": [(0.0, 0.5)], "R": [(a, b) for a in (0.5, 1.0, 1.5, 2.0) for b in (0.3, 0.5, 1.0, 1.5)],
            "points": [(a, b) for a in ps for b in pd_], "percent": [(a, b) for a in (0.05, 0.1, 0.2, 0.4) for b in (0.03, 0.05, 0.1, 0.2)],
            "atr": [(a, b) for a in (0.5, 1.0, 2.0, 3.0) for b in (0.5, 1.0, 1.5, 2.5)],
            "breakeven": [(a, b) for a in (0.5, 1.0, 1.5) for b in (0.0, 0.1, 0.3)], "step": [(a, 0.5) for a in (0.5, 1.0, 1.5)],
            "chandelier": [(a, k) for a in (0.0, 0.5, 1.0) for k in (1.5, 2.0, 3.0)],
            "profitlock": [(a, k) for a in (0.5, 1.0, 1.5) for k in (0.3, 0.5, 0.7)], "timestop": [(0.0, float(m)) for m in (30, 60, 120, 240, 480)],
            "partial": [(a, k) for a in (0.5, 1.0, 1.5) for k in (0.0, 0.5, 1.0)]}
    out = []
    for kind in list(grid) + list(lv):
        for _ in range(n_per_kind):
            p = {k: rng.choice(v) for k, v in X.SPACE.items()}
            if kind == "htfcandle":
                p["tf"] = rng.choice(["M1", "M2", "M3", "M5", "M10", "M15"])
                tp_ = rng.choice([m for m in lv[kind] if m > B.TF_MIN[p["tf"]] and m % B.TF_MIN[p["tf"]] == 0])
            else:
                tp_ = rng.choice(lv[kind]) if kind in lv else 0
            a, b = rng.choice(grid[kind]) if kind in grid else (rng.choice([0.0, 0.5, 1.0]), 0.5)
            out.append(dict(X.engine_cfg(dict(X.BASE, **p)), trail_kind=kind, trail_p=tp_, trail_start=a, trail_dist=b))
    return out


def _selftest_synthetic(n_per_kind=6, seed=7):
    """(1) Four points per real one-minute bar (open, adverse extreme, favourable extreme, close; constant spread), fills
    at the level as the simulated terminal makes them: with the EA's extra rules switched off simulate_tick must give the
    trades of simulate_y (closed = 1) for every kind, base and stress costs; then each EA rule is switched on alone and
    the trades it changes are counted."""
    os.environ.setdefault("HUMP_SPACE", "2")
    import hump_search as X
    import random
    btc = H.SYMBOL == "BTCUSD"
    SP = os.environ.get("LOMA_SCRATCH", "/tmp/claude-0/-workspace-master/53e0ea5b-b347-50b9-8f48-3f5cae086c17/scratchpad")
    m1 = pd.read_pickle(os.path.join(SP, "recal", "btc" if btc else "gold", "m1.pkl"))
    m1 = m1[m1.index >= "2025-11-01"]
    half = 5.0 if btc else 0.075
    hs = np.full(len(m1), half)
    mk = T2.MarketY(m1=m1, half_spread=hs)
    stream = bar_stream(m1, hs)
    n = len(m1)
    rng = random.Random(seed)
    setups = _setups(rng, n_per_kind, X)
    strict = dict(fill_level=1, plan_checks=0, server_exit_free=0, time_rules=0, trail_open=0, ea_tp=0)
    stress = dict(delay=1, slip=3.0 if btc else 0.10, comm=2.0 if btc else 0.07)
    ea_step = 2.0 if btc else 0.10
    variants = {                                        # name: (simulate_y settings, simulate_tick settings)
        "plan checks at entry (stop / target already crossed: no trade)": ({}, dict(plan_checks=1)),
        "per-tick trailing (R, step, breakeven) also on a minute's first tick": ({}, dict(trail_open=1)),
        "previous-hump target anticipated from the bid-chart extreme (item 13)": ({}, dict(ea_tp=1)),
        "entry on a tick where the server filled the previous trade (item 14)": ({}, dict(server_exit_free=1)),
        f"TrailStep granularity {ea_step:g} (R, step)": ({}, dict(step=ea_step)),
        "tick grid 0.01: stops and targets rounded as the EA does": ({}, dict(tick=0.01, point=0.01)),
        "time exits and weekend close: EA first tick vs bar close, no pre_gap": (dict(time=1), dict(time_rules=1)),
        "signal after a market gap entered up to two periods late (EvaluateSignal's stale rule)": ({}, dict(ea_rows=1)),
        "stress: simulate_y trail_worst=1 against the real tick order": (dict(trail_worst=1, **stress), dict(**stress)),
    }
    res = {k: {} for k in variants}
    total = 0; identical = 0; ntr = 0; open_tp = {}; half_open = {}
    for c0 in setups:
        kind = c0["trail_kind"]
        for extra in ({}, stress):
            c = dict(c0, max_hold=0, eod=-1, weekend_close=0, **extra)
            prep = prepare(mk, c)
            y = run_y(mk, prep); t = run_tick(mk, prep, stream, strict)
            y = y[y.exit_row < n - 1]; t = t[t.exit_row < n - 1]
            cl = classify(y, t, stream, kind, float(c["trail_start"]))
            same = not cl["unexplained"] and cl["target at the open"] == 0 and cl["partial half at the open"] == 0
            total += 1; identical += same; ntr += len(y)
            open_tp[kind] = open_tp.get(kind, 0) + cl["target at the open"]
            half_open[kind] = half_open.get(kind, 0) + cl["partial half at the open"]
            assert not cl["unexplained"], (kind, c["tf"], extra, cl["unexplained"][:3])
        c_base = dict(c0, max_hold=0, eod=-1, weekend_close=0)
        prep_b = prepare(mk, c_base)
        t_strict = run_tick(mk, prep_b, stream, strict)
        t_strict = t_strict[t_strict.exit_row < n - 1]
        for name, (vy, vt) in variants.items():
            if vy:                                      # rules with a simulate_y side: simulate_y with it against ticks with it
                c = dict(c0) if vy.get("time") else dict(c_base)
                c.update({k: v for k, v in vy.items() if k != "time"})
                prep_y = prepare(mk, c)
                prep_t = prepare(mk, dict(c, trail_worst=0))
                y = run_y(mk, prep_y)
            else:                                       # tick-only rules: the strict tick run against the run with the rule
                prep_t = prepare(mk, c_base, ea_rows=True) if vt.get("ea_rows") else prep_b
                y = t_strict
            t = run_tick(mk, prep_t, stream, dict(strict, **{k: v for k, v in vt.items() if k != "ea_rows"}))
            y = y[y.exit_row < n - 1]; t = t[t.exit_row < n - 1]
            d = trade_diff(y, t)
            r = res[name].setdefault(kind, dict(setups=0, trades=0, changed=0, r_only=0, max_dr=0.0))
            r["setups"] += 1; r["trades"] += d["n_y"]
            r["changed"] += d["only_y"] + d["only_tick"] + d["exit_row"]
            m = y.merge(t, on=["entry_row", "side"], suffixes=("_y", "_t"))
            m = m[m.exit_row_y.astype(int) == m.exit_row_t.astype(int)]
            dr = (m.r_y - m.r_t).abs()
            r["r_only"] += int((dr > 1e-9).sum()); r["max_dr"] = max(r["max_dr"], float(dr.max()) if len(dr) else 0.0)
    n_open = sum(open_tp.values())
    print(f"(1) {H.SYMBOL} synthetic ticks (4 per bar), EA extras off: {identical} of {total} runs identical to simulate_y "
          f"({ntr} trades, {len(setups)} setups of {len({s['trail_kind'] for s in setups})} kinds, base and stress); every other "
          f"difference is simulate_y's bar order: target passed at the open, simulate_y takes the stop on the low: {n_open} trades "
          f"({', '.join(f'{k} {v}' for k, v in open_tp.items() if v)}); partial's half-close level passed at a minute's open, "
          f"half booked at the open: {sum(half_open.values())} trades; unexplained: 0")
    print("    each EA rule alone (tick-only rules: against the strict tick run; time exits and stress: against simulate_y with "
          "the same rule): trades added, dropped or leaving in another minute, by kind; then trades with the same exit minute "
          "and another R, and the largest |dR|:")
    for name, by in res.items():
        tot_c = sum(v["changed"] for v in by.values()); tot_n = sum(v["trades"] for v in by.values())
        kinds = ", ".join(f"{k} {v['changed']}" for k, v in by.items() if v["changed"])
        r_only = sum(v["r_only"] for v in by.values()); mx = max(v["max_dr"] for v in by.values())
        print(f"    - {name}: {tot_c} of {tot_n}" + (f" ({kinds})" if kinds else "") + f"; same minute, other R: {r_only} (max |dR| {mx:.4f})")
    return dict(identical=identical, runs=total, trades=ntr, target_at_open=open_tp, partial_half_at_open=half_open, rules=res)


def _path(ticks, kind="none", side=1, sl_ref=99.0, tp_ref=0.0, tp_mode=1, tp_rr=10.0, ts=0.0, td=0.5, buf=0.0, lvl=None, aux=None,
          tbv=None, max_hold=0, eod=-1, wk=0, step=0.0, entry_rows=(0,), sigs=None, min_rr=0.0, atr=1.0, **ea):
    """A hand-made tick path (mode 0): ticks = [(server time 'YYYY-mm-dd HH:MM:SS(.fff)', bid, ask), ...]. One signal per
    entry row (side, stop reference sl_ref, target tp_rr x risk). Rows are the minutes that have ticks."""
    t = pd.to_datetime([x[0] for x in ticks]).values.astype("datetime64[ms]").astype(np.int64)
    bid = np.array([x[1] for x in ticks], float); ask = np.array([x[2] for x in ticks], float)
    minute = t // 60000
    st_ = np.r_[0, np.where(np.diff(minute) != 0)[0] + 1].astype(np.int64)
    en_ = np.r_[st_[1:], len(t)].astype(np.int64)
    s = tick_stream(t, bid, ask, st_, en_)
    nrow = len(st_)
    if sigs is None:
        sigs = [(side, sl_ref, tp_ref)] * len(entry_rows)
    sig = np.array([[0, sd, a, b, 0.0, atr] for sd, a, b in sigs], float)
    tb = np.arange(nrow, dtype=np.int64) - 1 if tbv is None else np.asarray(tbv, np.int64)
    lv = np.full(nrow, np.nan) if lvl is None else np.asarray(lvl, float)
    ax = np.full(nrow, np.nan) if aux is None else np.asarray(aux, float)
    e = dict(EA_DEFAULT); e.update(ea)
    tr = simulate_tick(sig, np.asarray(entry_rows, np.int64), s.rq0, s.rq1, s.bar_bh, s.bar_al, s.mode, *s.arr, 0, 1440, buf, 0.0,
                       min_rr, tp_mode, tp_rr, ts, td, 1e9, 0.0, 1e9, float(e.get("slip", 0.0)), float(e.get("comm", 0.0)), 0,
                       max_hold, eod, wk, 1380, KIND[kind], tb, lv, lv, ax, step, float(e["point"]), float(e["tick"]),
                       float(e["stops_level"]), int(e["fill_level"]), int(e["plan_checks"]), int(e["server_exit_free"]),
                       int(e["trail_open"]), -1, 0, int(e["ea_tp"]))
    return [dict(zip(COLS, row)) for row in tr]


def _selftest_paths():
    """(2) Hand-made tick paths, one rule at a time (buy: entry at the ask 100.00, stop 99, R = 1, unless said)."""
    D = "2026-06-03 "                                              # a Wednesday
    def tk(hms, bid, sp=0.0):
        return (D + hms, bid - sp / 2, bid + sp / 2)
    n_ok = 0

    def check(cond, what):
        nonlocal n_ok
        assert cond, what
        n_ok += 1

    # gap through the stop: the bid falls from 99.50 to 98.70 inside a minute -> filled at 98.70 (-1.3R), not at 99
    x = _path([tk("10:00:00", 100), tk("10:00:20", 99.5), tk("10:00:30", 98.7), tk("10:01:00", 99.0)])
    check(len(x) == 1 and abs(x[0]["exit_px"] - 98.7) < 1e-12 and abs(x[0]["r"] + 1.3) < 1e-12 and x[0]["reason"] == 1, "stop gap")
    # the same path with level fills (the four-point feed of the simulated terminal): at the stop, 99
    x = _path([tk("10:00:00", 100), tk("10:00:20", 99.5), tk("10:00:30", 98.7)], fill_level=1)
    check(abs(x[0]["exit_px"] - 99.0) < 1e-12, "stop level fill")
    # target jumped over: target 102 (tp_rr 2), the bid jumps from 101.9 to 102.4 -> filled at 102.4 (+2.4R)
    x = _path([tk("10:00:00", 100), tk("10:00:10", 101.9), tk("10:00:11", 102.4)], tp_rr=2.0)
    check(abs(x[0]["exit_px"] - 102.4) < 1e-12 and x[0]["reason"] == 2, "target gap")
    # stop and target in the same minute: the order of the ticks decides
    x = _path([tk("10:00:00", 100), tk("10:00:10", 98.9), tk("10:00:20", 102.2)], tp_rr=2.0)
    check(x[0]["reason"] == 1 and abs(x[0]["exit_px"] - 98.9) < 1e-12, "stop first")
    x = _path([tk("10:00:00", 100), tk("10:00:10", 102.2), tk("10:00:20", 98.9)], tp_rr=2.0)
    check(x[0]["reason"] == 2 and abs(x[0]["exit_px"] - 102.2) < 1e-12, "target first")
    # sell: stopped on the ask. Spread 0.2: entry at the bid 100, stop = 101 + 0 + 0.1 = 101.1; the ask reaches 101.1
    x = _path([tk("10:00:00", 100.1, 0.2), tk("10:00:30", 100.95, 0.2), tk("10:00:40", 101.0, 0.2)], side=-1, sl_ref=101.0)
    check(x[0]["reason"] == 1 and abs(x[0]["sl0"] - 101.1) < 1e-12 and abs(x[0]["exit_px"] - 101.1) < 1e-12, "sell on the ask")
    # ATR trailing (unit = ATR at the signal = 1): start 1, distance 0.5. Minute 10:00 makes a bid high of 101.6; at the
    # first tick of 10:01 the stop goes to 101.1 (the minute's own ticks never move it); a later tick at 101.05 fills at 101.05
    p = [tk("10:00:00", 100), tk("10:00:30", 101.6), tk("10:00:50", 101.15), tk("10:01:00", 101.4), tk("10:01:20", 101.05)]
    x = _path(p, kind="atr", ts=1.0, td=0.5)
    check(x[0]["reason"] == 1 and abs(x[0]["exit_px"] - 101.05) < 1e-12 and abs(x[0]["stop_last"] - 101.1) < 1e-12, "closed-minute trail")
    # ... and when the first tick of 10:01 is already through the new stop: closed at market there (trailing close)
    p2 = [tk("10:00:00", 100), tk("10:00:30", 101.6), tk("10:01:00", 100.9), tk("10:01:20", 101.5)]
    x = _path(p2, kind="atr", ts=1.0, td=0.5)
    check(x[0]["reason"] == 3 and abs(x[0]["exit_px"] - 100.9) < 1e-12 and x[0]["exit_row"] == 1, "trailing close at market")
    # a second signal entering on that tick is refused (no entry on the bar of a trailing close) ...
    x = _path(p2 + [tk("10:02:00", 101.0)], kind="atr", ts=1.0, td=0.5, entry_rows=(0, 1))
    check(len(x) == 1, "no entry on the trailing close tick")
    # ... while a stop filled by the server on that tick lets it in (the EA's OnTick runs after the fill)
    p3 = [tk("10:00:00", 100), tk("10:00:30", 99.5), tk("10:01:00", 98.9), tk("10:01:20", 98.5), tk("10:02:00", 99.0)]
    x = _path(p3, entry_rows=(0, 1), sigs=[(1, 99.0, 0.0), (1, 97.0, 0.0)])
    check(len(x) == 2 and x[0]["exit_q"] == x[1]["entry_q"] == 2, "entry after a server fill on the same tick")
    x = _path(p3, entry_rows=(0, 1), sigs=[(1, 99.0, 0.0), (1, 97.0, 0.0)], server_exit_free=0)
    check(len(x) == 1, "simulate_y's one-position rule")
    # level trailing with activation at +1R: support level 100.5 known from row 1 on; row 0's best (bid high) is 100.8 <
    # 101, so at row 1 the level is not used; row 1 reaches 101.2 -> from row 2 the stop is 100.5 - buffer 0.1
    p = [tk("10:00:00", 100), tk("10:00:30", 100.8), tk("10:01:00", 100.7), tk("10:01:30", 101.2), tk("10:02:00", 100.9),
         tk("10:02:30", 100.35)]
    x = _path(p, kind="candles", ts=1.0, buf=0.1, sl_ref=99.1, lvl=[np.nan, 100.5, 100.5], tbv=[-1, 1, 1])
    check(x[0]["reason"] == 1 and abs(x[0]["stop_last"] - 100.4) < 1e-12 and abs(x[0]["exit_px"] - 100.35) < 1e-12 and x[0]["exit_row"] == 2,
          "level activation")
    x = _path(p[:4] + [tk("10:01:40", 100.45)], kind="candles", ts=1.0, buf=0.1, sl_ref=99.1, lvl=[np.nan, 100.5], tbv=[-1, 1])
    check(x[0]["reason"] == 7, "level not active yet in row 1")
    # the EA's own trailing (R): every tick, start 1R, distance 0.5R, TrailStep 0.10: 101.0 -> stop 100.5; 101.05 ->
    # 100.55 is only 0.05 better (kept at 100.5); 101.2 -> 100.7; then 100.69 fills at 100.69
    p = [tk("10:00:00", 100), tk("10:00:10", 101.0), tk("10:00:20", 101.05), tk("10:00:30", 101.2), tk("10:00:40", 100.69)]
    x = _path(p, kind="R", ts=1.0, td=0.5, step=0.10, point=0.01)
    check(x[0]["nmod"] == 2 and abs(x[0]["exit_px"] - 100.69) < 1e-12 and abs(x[0]["stop_last"] - 100.7) < 1e-9, "R per tick with step")
    # STEP every tick, 0.5R steps: the bid reaches 101.1 (k = 2) inside the entry minute -> stop at entry + 0.5 at once
    p = [tk("10:00:00", 100), tk("10:00:10", 101.1), tk("10:00:20", 100.45)]
    x = _path(p, kind="step", ts=0.5)
    check(abs(x[0]["exit_px"] - 100.45) < 1e-12 and abs(x[0]["stop_last"] - 100.5) < 1e-12, "step inside the entry minute")
    # MaxHoldMinutes 3: entry 10:00:20; rows 10:01, 10:02, 10:03; at 10:03:05 the clock has only 2:45 -> the exit is the
    # first tick at or after 10:03:20
    p = [tk("10:00:20", 100), tk("10:01:00", 100.2), tk("10:02:00", 100.3), tk("10:03:05", 100.4), tk("10:03:25", 100.5), tk("10:04:00", 100.6)]
    x = _path(p, max_hold=3)
    check(x[0]["reason"] == 4 and abs(x[0]["exit_px"] - 100.5) < 1e-12, "max hold on bars and clock")
    # a minute without ticks does not count: rows 10:01, 10:03 (10:02 missing), 10:04 -> exit at 10:04
    p = [tk("10:00:00", 100), tk("10:01:00", 100.2), tk("10:03:00", 100.3), tk("10:04:00", 100.4), tk("10:05:00", 100.6)]
    x = _path(p, max_hold=3)
    check(x[0]["reason"] == 4 and abs(x[0]["exit_px"] - 100.4) < 1e-12, "max hold counts bars with ticks")
    # end of day 22:00 (eod 1320): the first tick at or after 22:00:00
    p = [tk("21:58:00", 100), tk("21:59:59", 100.2), tk("22:00:03", 100.3), tk("22:01:00", 100.4)]
    x = _path(p, eod=1320)
    check(x[0]["reason"] == 5 and abs(x[0]["exit_px"] - 100.3) < 1e-12, "end of day")
    # opened after the day's EndOfDayTime: kept to the next day's
    p = [tk("22:10:00", 100), tk("23:00:00", 100.2), ("2026-06-04 01:00:00", 100.3, 100.3), ("2026-06-04 22:00:00", 100.5, 100.5)]
    x = _path(p, eod=1320)
    check(x[0]["reason"] == 5 and abs(x[0]["exit_px"] - 100.5) < 1e-12, "end of day next day")
    # Friday window 23:00 (2026-06-05 is a Friday): closed at the first tick at or after 23:00
    F = "2026-06-05 "
    p = [(F + "22:58:00", 100, 100), (F + "22:59:30", 100.2, 100.2), (F + "23:00:02", 100.3, 100.3), (F + "23:30:00", 100.5, 100.5)]
    x = _path(p, wk=1)
    check(x[0]["reason"] == 6 and abs(x[0]["exit_px"] - 100.3) < 1e-12, "Friday window")
    # catch-up: no tick between Friday 22:59:30 and Monday -> closed on Monday's first tick
    p = [(F + "22:58:00", 100, 100), (F + "22:59:30", 100.2, 100.2), ("2026-06-08 01:00:00", 100.6, 100.6), ("2026-06-08 01:01:00", 100.7, 100.7)]
    x = _path(p, wk=1)
    check(x[0]["reason"] == 6 and abs(x[0]["exit_px"] - 100.6) < 1e-12, "weekend catch-up")
    # no entry on Friday from 23:00 on; a Monday entry is kept over the next Friday's window only until 23:00 Friday
    x = _path([(F + "23:00:00", 100, 100), (F + "23:01:00", 100.1, 100.1)], wk=1)
    check(len(x) == 0, "pre-weekend entry block")
    # chandelier 2 x ATR(0.4): bid high 102 in row 0; at row 1's first tick the stop is 102 - 0.8 = 101.2
    p = [tk("10:00:00", 100), tk("10:00:30", 102.0), tk("10:01:00", 101.5), tk("10:01:30", 101.19)]
    x = _path(p, kind="chandelier", td=2.0, aux=[0.4, 0.4], tbv=[0, 0])
    check(abs(x[0]["stop_last"] - 101.2) < 1e-12 and abs(x[0]["exit_px"] - 101.19) < 1e-12, "chandelier")
    # profit lock 50% from +1R: best 102 -> stop 101 from the next minute
    x = _path([tk("10:00:00", 100), tk("10:00:30", 102.0), tk("10:01:00", 101.5), tk("10:01:30", 100.98)], kind="profitlock", ts=1.0, td=0.5)
    check(abs(x[0]["stop_last"] - 101.0) < 1e-12 and abs(x[0]["exit_px"] - 100.98) < 1e-12, "profit lock")
    # sell side of the completed-minute best: the lowest ask of the minute (spread 0.2): ask low 98.0 at 10:00:30;
    # percent trailing (1% of 100 = 1.0): start 1%, distance 0.5% -> stop 98.5 from 10:01
    p = [tk("10:00:00", 100.1, 0.2), tk("10:00:30", 97.9, 0.2), tk("10:01:00", 98.2, 0.2), tk("10:01:30", 98.45, 0.2)]
    x = _path(p, kind="percent", side=-1, sl_ref=101.0, ts=1.0, td=0.5)
    check(abs(x[0]["stop_last"] - 98.5) < 1e-12 and abs(x[0]["exit_px"] - 98.55) < 1e-12, "sell best = lowest ask")
    # partial: half at +1R (101), the rest to breakeven, later stopped at 100 -> 0.5 x 1 + 0.5 x 0 = 0.5R
    x = _path([tk("10:00:00", 100), tk("10:00:20", 101.2), tk("10:00:40", 99.95)], kind="partial", ts=1.0, td=0.0)
    check(abs(x[0]["r"] - (0.5 * 1.2 + 0.5 * -0.05)) < 1e-12, "partial (half at the tick price 101.2, rest at 99.95)")
    # tick grid: the initial stop to the nearest tick, a trailing stop to the looser side (a buy's down)
    x = _path([tk("10:00:00", 100), tk("10:00:30", 101.637), tk("10:01:00", 101.5), tk("10:01:30", 100.0)], kind="atr", ts=1.0, td=0.5,
              tick=0.01, point=0.01, sl_ref=99.004)
    check(abs(x[0]["sl0"] - 99.0) < 1e-9 and abs(x[0]["stop_last"] - 101.13) < 1e-9, "tick grid")
    # sells (spread 0.2: entry at the bid 100.0, stop 101 + 0.1 = 101.1, R = 1.1), stops tested on the ask
    # RISK every tick: the ask reaches 98.9 (+1R) -> stop 98.9 + 0.55 = 99.45; an ask of 99.5 fills there
    x = _path([tk("10:00:00", 100.1, 0.2), tk("10:00:10", 98.8, 0.2), tk("10:00:20", 99.4, 0.2)], kind="R", side=-1, sl_ref=101.0,
              ts=1.0, td=0.5)
    check(abs(x[0]["stop_last"] - 99.45) < 1e-9 and abs(x[0]["exit_px"] - 99.5) < 1e-9 and abs(x[0]["r"] - 0.5 / 1.1) < 1e-9, "R sell")
    # STEP every tick, steps of 0.5R = 0.55: the ask reaches 98.85 (k = 2) -> stop entry - 0.55 = 99.45
    x = _path([tk("10:00:00", 100.1, 0.2), tk("10:00:10", 98.75, 0.2), tk("10:00:20", 99.4, 0.2)], kind="step", side=-1, sl_ref=101.0,
              ts=0.5)
    check(abs(x[0]["stop_last"] - 99.45) < 1e-9 and abs(x[0]["exit_px"] - 99.5) < 1e-9, "step sell")
    # level system, sell: resistance (mid) 99.6 from row 1 on, + buffer 0.1 + half the spread 0.1 = 99.8; the ask of row
    # 1's first tick (99.6) is below it -> stop 99.8; a later ask of 99.85 fills there
    x = _path([tk("10:00:00", 100.1, 0.2), tk("10:00:30", 99.9, 0.2), tk("10:01:00", 99.5, 0.2), tk("10:01:30", 99.75, 0.2)],
              kind="ema", side=-1, sl_ref=101.0 - 0.1, buf=0.1, lvl=[np.nan, 99.6, 99.6], tbv=[-1, 1, 1])
    check(x[0]["reason"] == 1 and abs(x[0]["sl0"] - 101.1) < 1e-9 and abs(x[0]["stop_last"] - 99.8) < 1e-9
          and abs(x[0]["exit_px"] - 99.85) < 1e-9, "level sell")
    # a signal after a market gap (EvaluateSignal's stale rule), M5 signal bar 10:00 (its close 10:05): the market reopens
    # at 10:05 or 10:10 (both rules enter there), 10:11 or 10:14 (only the EA's: inside trigger bar 10:10 = S + 2P), 10:15
    # (neither: S + 3P)
    for reopen, ea_in, y_in in (("10:05", 1, 1), ("10:10", 1, 1), ("10:11", 1, 0), ("10:14", 1, 0), ("10:15", 0, 0)):
        idx = pd.date_range(D + "09:00", D + "10:04", freq="1min").append(pd.date_range(D + reopen, periods=30, freq="1min"))
        mk = T2.MarketY(m1=pd.DataFrame(dict(open=100.0, high=100.5, low=99.5, close=100.0), index=idx),
                        half_spread=np.full(len(idx), 0.1))
        row = mk.tf("M5")[4]
        sb = int(np.searchsorted(mk._tf["M5"]["t"].index.values, np.datetime64(D + "10:00")))
        er = ea_entry_rows(mk, "M5", np.array([sb]))[0]
        check((er >= 0) == bool(ea_in) and (row[sb] >= 0) == bool(y_in) and (er < 0 or mk.t[er] == np.datetime64(D + reopen)),
              f"stale signal after a gap, reopen {reopen}")
    print(f"(2) hand-made tick paths: {n_ok} checks passed")
    return n_ok


if __name__ == "__main__":
    os.environ.setdefault("HUMP_SPACE", "2")
    _selftest_paths()
    _selftest_synthetic(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
