"""Python replica of AMVI_FGF_Inverted_XAUUSD_15m.pine as TradingView runs it with
Script executions = "On bar close" (the closed-candle engine):

  1. trigger    an enabled timeframe's AMVI crosses above High Vol on this chart bar while
                at least `conf` enabled timeframes are above it;
  2. direction  the FlashGold filter's zone of this chart bar (BUY ZONE / SELL ZONE / none),
                optionally inverted;
  3. orders     decided at the bar close, market fill at the next bar's open; ATR stop,
                target and trailing stop filled inside later bars, on the 1-minute bars
                (each walked open -> nearer extreme -> other extreme -> close);
  4. costs      commission as a fraction of each fill's value, slippage in ticks on market
                and stop fills.

A result is a list of trades in R (1 R = Stop Loss x the exit ATR at the signal), so it does
not depend on position size. Times are bar OPEN times in ms. Timeframes are in minutes.
"""
import math

import numpy as np
from numba import njit

import pineta as ta
from bars import MIN_MS

MINTICK = 0.1  # BTCUSDT perpetual (Binance and Bitget)

DEFAULTS = dict(
    # AMVI (defaults of the Pine file; `tfs` = enabled timeframes in minutes)
    fast=7, slow=100, sd=20, cr=20, norm=200, wA=0.35, wV=0.25, wS=0.25, wC=0.15,
    high=60.0, low=30.0, conf=1, tfs=(15, 60, 240),
    # FlashGold direction filter
    f_tf=60, lv_mode="close", band=0.5, against=True, allow_buy=True, allow_sell=True,
    use_burst=False, any_combo=True, burst_atr=0.5, entry_dist_atr=0.25,
    use_drift=False, drift_bars=60, use_zones=True, parent_tf=60, rsi_len=14, fast_len=2,
    min_aligned=0, zones=(60, 120, 240), spread_pts=25.0,
    perm_candles=0,        # "Permission lasts": 0 = until next signal, n = "Candles" with n candles
    check_open=False,      # "Check price on" = "Level at candle open" (always used when the filter is not above the chart)
    # trade direction
    inverted=True,
    # exits
    exit_atr=14, sl=1.0, tp=0.0, trail=False, trail_act=1.5, trail_off=1.0,
    vol_exit=False, max_bars=0,
    # closed-candle engine
    wait=0,
)

# "price has reached a level" is tested with this tolerance: levels such as entry +- n ticks
# are exact on the tick grid but not in binary floating point
EPS = 1e-7

# exit reasons
X_STOP, X_TP, X_TRAIL, X_REV, X_VOL, X_TIME, X_END = 1, 2, 3, 4, 5, 6, 7


def P(**kw):
    """Parameter dict: the Pine file's defaults with overrides."""
    d = dict(DEFAULTS)
    for k in kw:
        if k not in d:
            raise KeyError(k)
    d.update(kw)
    return d


# ----------------------------------------------------------------------------------------
# timeframe alignment: which requested-timeframe bar a context bar reads
# ----------------------------------------------------------------------------------------
def idx_amvi(ctx_t, ctx_tf, req_t, req_tf):
    """get_mtf() with Non-Repainting on. Index into the requested timeframe's bars for every
    context bar (-1 = no value yet):
      higher  the bar before the one containing the context bar ([1] with lookahead on);
      equal   the previous bar;
      lower   the last intrabar of the context bar (its value at the context bar's close)."""
    if req_tf > ctx_tf:
        return np.searchsorted(req_t, ctx_t, side="right") - 2
    if req_tf == ctx_tf:
        return np.arange(ctx_t.size, dtype=np.int64) - 1
    return np.searchsorted(req_t, ctx_t + ctx_tf * MIN_MS, side="left") - 1


def idx_zone(ctx_t, ctx_tf, req_t, req_tf):
    """fgfZoneDir() with fgfHtfClosed on, for a filter candle:
      higher  the previous closed bar of the requested timeframe;
      equal   the candle itself;
      lower   the last intrabar of the candle."""
    if req_tf > ctx_tf:
        return np.searchsorted(req_t, ctx_t, side="right") - 2
    if req_tf == ctx_tf:
        return np.arange(ctx_t.size, dtype=np.int64)
    return np.searchsorted(req_t, ctx_t + ctx_tf * MIN_MS, side="left") - 1


def idx_arm(chart_t, chart_tf, f_t, f_tf, at_open=False):
    """The filter candle whose arm is in force on a closed chart bar, and whether that candle
    closes exactly at the judging clock.
      "Tick" with the filter above the chart: latest filter candle closed by the chart bar's CLOSE;
      "Level at candle open" (always when the filter is not above the chart): latest filter
      candle closed by the chart bar's OPEN."""
    f_ms = f_tf * MIN_MS
    clock = chart_t if (at_open or f_tf <= chart_tf) else chart_t + chart_tf * MIN_MS
    kc = np.searchsorted(f_t, clock - f_ms, side="right") - 1
    at_clock = np.zeros(chart_t.size, np.bool_)
    ok = kc >= 0
    at_clock[ok] = f_t[kc[ok]] + f_ms == clock[ok]
    return kc, at_clock


def gather(arr, idx):
    out = arr[np.maximum(idx, 0)]
    out[idx < 0] = np.nan
    return out


# ----------------------------------------------------------------------------------------
# features
# ----------------------------------------------------------------------------------------
class Features:
    """Per-timeframe indicator arrays, computed once and shared (fork) by the sweep workers."""

    def __init__(self, market):
        self.mk = market
        self.c = {}

    def _get(self, key, fn):
        v = self.c.get(key)
        if v is None:
            v = fn()
            self.c[key] = v
        return v

    def atr(self, tf, n):
        b = self.mk.tf(tf)
        return self._get(("atr", tf, n), lambda: ta.atr(b.h, b.l, b.c, n))

    def natr(self, tf, fast, norm):
        return self._get(("natr", tf, fast, norm), lambda: ta.normalize(self.atr(tf, fast), norm))

    def nvr(self, tf, fast, slow):
        def f():
            fa, sa = self.atr(tf, fast), self.atr(tf, slow)
            # Pine: sATR > 0 ? min(2, max(0.5, fATR / sATR)) : 1.0 -- while the slow ATR is
            # still na the comparison is false and the ratio is 1.0, not na
            with np.errstate(invalid="ignore", divide="ignore"):
                vr = np.where(sa > 0, np.minimum(2.0, np.maximum(0.5, fa / sa)), 1.0)
            return ((vr - 0.5) / 1.5)
        return self._get(("nvr", tf, fast, slow), f)

    def nsd(self, tf, sd, norm):
        b = self.mk.tf(tf)
        return self._get(("nsd", tf, sd, norm), lambda: ta.normalize(ta.stdev(b.c, sd), norm))

    def ncr(self, tf, cr, norm):
        b = self.mk.tf(tf)
        return self._get(("ncr", tf, cr, norm), lambda: ta.normalize(ta.sma(b.h - b.l, cr), norm))

    def amvi(self, tf, p):
        """calc_amvi() on timeframe tf (not cached: a weighted sum of cached parts)."""
        a = (p["wA"] * self.natr(tf, p["fast"], p["norm"])
             + p["wV"] * self.nvr(tf, p["fast"], p["slow"])
             + p["wS"] * self.nsd(tf, p["sd"], p["norm"])
             + p["wC"] * self.ncr(tf, p["cr"], p["norm"]))
        return a * 100.0

    def tdi(self, tf, rsi_len, fast_len):
        """fgfTdiDir(): +1 / -1 / 0 as the fast line (SMA of RSI) rises / falls / else."""
        def f():
            b = self.mk.tf(tf)
            fl = ta.sma_exact(ta.rsi(b.c, rsi_len), fast_len)
            d = np.zeros(fl.size, np.int8)
            d[1:][fl[1:] > fl[:-1]] = 1
            d[1:][fl[1:] < fl[:-1]] = -1
            return d
        return self._get(("tdi", tf, rsi_len, fast_len), f)

    def idx(self, kind, ctx_tf, req_tf):
        def f():
            a, b = self.mk.tf(ctx_tf), self.mk.tf(req_tf)
            if kind == "amvi":
                return idx_amvi(a.t, ctx_tf, b.t, req_tf)
            if kind == "zone":
                return idx_zone(a.t, ctx_tf, b.t, req_tf)
            return idx_arm(a.t, ctx_tf, b.t, req_tf, at_open=(kind == "arm_open"))
        return self._get(("idx", kind, ctx_tf, req_tf), f)


# ----------------------------------------------------------------------------------------
# trigger
# ----------------------------------------------------------------------------------------
def trigger_arrays(ft, chart_tf, p):
    """(trigger, vol_collapse, hot_count) per chart bar."""
    n = len(ft.mk.tf(chart_tf))
    any_cross = np.zeros(n, np.bool_)
    hot = np.zeros(n, np.int16)
    s = np.zeros(n)
    cnt = np.zeros(n, np.int16)
    hi = p["high"]
    for tf in p["tfs"]:
        v = gather(ft.amvi(tf, p), ft.idx("amvi", chart_tf, tf))
        ok = ~np.isnan(v)
        above = ok & (v > hi)
        prev_le = np.zeros(n, np.bool_)
        prev_le[1:] = ok[:-1] & (v[:-1] <= hi)
        any_cross |= above & prev_le
        hot += above
        s += np.where(ok, v, 0.0)
        cnt += ok
    trig = any_cross & (hot >= p["conf"])
    with np.errstate(invalid="ignore", divide="ignore"):
        avg = np.where(cnt > 0, s / np.maximum(cnt, 1), np.nan)
    lo = p["low"]
    volc = np.zeros(n, np.bool_)
    volc[1:] = (avg[1:] < lo) & (avg[:-1] >= lo)
    return trig, volc, hot


# ----------------------------------------------------------------------------------------
# FlashGold filter
# ----------------------------------------------------------------------------------------
def filter_arms(ft, p):
    """fgfSignal() + fgfArm() on the filter timeframe. Returns (arm_idx, level, direction, atr):
    arm_idx[k] = index of the latest signal candle at or before candle k (-1 = none);
    level / direction / atr are per candle and meaningful at signal candles."""
    F = p["f_tf"]
    b = ft.mk.tf(F)
    c = b.c
    n = c.size
    atr_f = ft.atr(F, 14)
    half = p["spread_pts"] * MINTICK * 0.5

    def seen(tf):
        ix = ft.idx("zone", F, tf)
        d = ft.tdi(tf, p["rsi_len"], p["fast_len"])
        out = d[np.maximum(ix, 0)].copy()
        valid = ix >= 0
        out[~valid] = 0
        return out, valid

    pside, _ = seen(p["parent_tf"])
    active = np.zeros(n, np.int16)
    aligned = np.zeros(n, np.int16)
    for z in p["zones"]:
        zd, zv = seen(z)
        active += zv
        aligned += zv & (zd == pside) & (pside != 0)
    required = np.minimum(p["min_aligned"], active)
    zone_ready = (active == 0) | (aligned >= required)
    if p["use_zones"]:
        tz_buy = (pside == 1) & zone_ready
        tz_sell = (pside == -1) & zone_ready
    else:
        tz_buy = np.ones(n, np.bool_)
        tz_sell = np.ones(n, np.bool_)

    burst = np.full(n, np.nan)
    burst[1:] = c[1:] - c[:-1]
    thr = p["burst_atr"] * atr_f
    with np.errstate(invalid="ignore"):
        burst_buy = burst >= thr
        burst_sell = burst <= -thr
    if p["any_combo"]:
        if p["use_burst"]:
            raw_buy = tz_buy & (burst_buy | (pside == 1))
            raw_sell = tz_sell & (burst_sell | (pside == -1))
        else:
            raw_buy, raw_sell = tz_buy, tz_sell
    else:
        raw_buy, raw_sell = tz_buy & burst_buy, tz_sell & burst_sell
    if p["use_drift"]:
        k = p["drift_bars"]
        drift = np.full(n, np.nan)
        drift[k:] = c[k:] - c[:-k]
        with np.errstate(invalid="ignore"):
            raw_buy = raw_buy & (drift > 0)
            raw_sell = raw_sell & (drift < 0)
    sig = raw_buy | raw_sell
    direction = np.where(raw_buy, 1, -1).astype(np.int8)
    if p["lv_mode"] == "close":
        level = c
    else:
        dist = p["entry_dist_atr"] * atr_f
        level = np.where(raw_buy, c + half + dist, c - half - dist)
        level = np.where(np.isnan(level), c, level)
    arm_idx = np.maximum.accumulate(np.where(sig, np.arange(n, dtype=np.int64), -1))
    return arm_idx, level, direction, atr_f


def zone_array(ft, chart_tf, p, arms=None):
    """+1 = BUY ZONE only, -1 = SELL ZONE only, 0 = no direction, per closed chart bar."""
    F = p["f_tf"]
    arm_idx, level, direction, atr_f = arms if arms is not None else filter_arms(ft, p)
    kc, at_clock = ft.idx("arm_open" if (p["check_open"] or F <= chart_tf) else "arm", chart_tf, F)
    value = ft.mk.tf(chart_tf).c
    a = np.where(kc >= 0, arm_idx[np.maximum(kc, 0)], -1)
    armed = a >= 0
    ai = np.maximum(a, 0)
    lvl = level[ai]
    d = direction[ai]
    band = p["band"] * np.nan_to_num(atr_f[ai])
    on_sig = at_clock & (a == kc)
    mt = MINTICK
    has_band = band > 0
    up = np.ceil((lvl + band) / mt - 1e-9) * mt
    dn = np.floor((lvl - band) / mt + 1e-9) * mt
    in_up = np.where(has_band, value > up + mt / 2, (value > lvl) | (on_sig & (d > 0) & (value >= lvl)))
    in_dn = np.where(has_band, value < dn - mt / 2, (value < lvl) | (on_sig & (d < 0) & (value <= lvl)))
    if not p["against"]:
        in_up = in_up & (d > 0)
        in_dn = in_dn & (d < 0)
    is_open = armed
    if p["perm_candles"] > 0:
        # "Candles": the permission covers n filter candles counted from the signal candle
        # (fgfIdx < fgfSigBar + fgfBars; fgfIdx = the filter candle the clock falls in)
        is_open = armed & ((kc + (~at_clock) - a) < p["perm_candles"])
    buy_ok = is_open & in_up & p["allow_buy"]
    sell_ok = is_open & in_dn & p["allow_sell"]
    z = np.zeros(value.size, np.int8)
    z[buy_ok & ~sell_ok] = 1
    z[sell_ok & ~buy_ok] = -1
    return z


# ----------------------------------------------------------------------------------------
# orders
# ----------------------------------------------------------------------------------------
@njit(cache=True)
def _round_half_up(x):
    return math.floor(x + 0.5)


@njit(cache=True)
def simulate(ct, co, cc, ci0, ci1, catr, mt, mo, mh, ml, mc, trig, zone, volc,
             inverted, sl, tp, use_trail, trail_act, trail_off, use_vol_exit, max_bars, wait,
             fee, slip_ticks, mintick, i_start, i_end, tf_ms):
    """Bar-by-bar order simulation over chart bars [i_start, i_end).

    ct, co, cc      chart bar open time / open / close;  ci0, ci1  its 1-minute rows [ci0, ci1)
    catr            exit ATR on the chart timeframe;     mt, mo..mc  1-minute time and OHLC
    trig, zone, volc  per chart bar: volatility trigger, filter zone (+1 / -1 / 0), vol collapse

    Returns per trade: entry time, exit time, direction, entry price, exit price, risk distance
    (Stop Loss x ATR at the signal), net R, exit reason, signal bar index."""
    cap = 2 * (i_end - i_start) + 4
    e_t = np.empty(cap, np.int64)
    x_t = np.empty(cap, np.int64)
    dr = np.empty(cap, np.int8)
    e_px = np.empty(cap)
    x_px = np.empty(cap)
    risk = np.empty(cap)
    r_net = np.empty(cap)
    why = np.empty(cap, np.int8)
    sbar = np.empty(cap, np.int64)
    nt = 0

    slip = slip_ticks * mintick
    pos = 0
    entry_px = 0.0
    entry_time = 0
    entry_bar = -1
    sig_bar = -1
    entry_atr = np.nan    # the Pine `var float entryAtr`
    risk_dist = 1.0
    stop = np.nan
    limit = np.nan
    act_px = np.nan
    off_dist = 0.0
    trail_on = False
    best = 0.0
    pend_dir = 0          # market entry waiting for the next open
    pend_close = 0        # close order waiting for the next open (its exit reason, 0 = none)
    pend_ref = 0.0        # the signal bar's close: the bracket's reference price until the bar after the fill
    last_sig = -1         # bar of the last entry signal (wait rule)

    for i in range(i_start, i_end):
        # ---- market orders created at the previous close fill at this open ----
        o = co[i]
        if pos != 0 and (pend_close != 0 or pend_dir == -pos):
            px = o - pos * slip
            e_t[nt] = entry_time
            x_t[nt] = ct[i]
            dr[nt] = pos
            e_px[nt] = entry_px
            x_px[nt] = px
            risk[nt] = risk_dist
            r_net[nt] = (pos * (px - entry_px) - fee * (px + entry_px)) / risk_dist
            why[nt] = X_REV if pend_dir == -pos else pend_close
            sbar[nt] = sig_bar
            nt += 1
            pos = 0
        if pend_dir != 0 and pos == 0:
            pos = pend_dir
            entry_px = o + pos * slip
            entry_time = ct[i]
            entry_bar = i
            sig_bar = i - 1
            risk_dist = sl * entry_atr
            stop = pend_ref - pos * entry_atr * sl if sl > 0 else np.nan
            limit = pend_ref + pos * entry_atr * tp if tp > 0 else np.nan
            trail_on = False
            if use_trail:
                a_t = max(1.0, _round_half_up(entry_atr * trail_act / mintick))
                o_t = max(1.0, _round_half_up(entry_atr * trail_off / mintick))
                act_px = entry_px + pos * a_t * mintick
                off_dist = o_t * mintick
        pend_dir = 0
        pend_close = 0

        # ---- stop / target / trailing stop inside the bar, on its 1-minute bars ----
        if pos != 0:
            for j in range(ci0[i], ci1[i]):
                bo = mo[j]
                done = False
                xp = 0.0
                reason = 0
                # the open tick: an order whose price is already passed fills at the open
                s_eff = stop
                is_trail = False
                if trail_on:
                    ts = best - pos * off_dist
                    if np.isnan(s_eff) or pos * (ts - s_eff) > 0:
                        s_eff = ts
                        is_trail = True
                if not np.isnan(s_eff) and pos * (bo - s_eff) <= EPS:
                    xp = bo - pos * slip
                    reason = X_TRAIL if is_trail else X_STOP
                    done = True
                elif not np.isnan(limit) and pos * (bo - limit) >= -EPS:
                    xp = bo
                    reason = X_TP
                    done = True
                if not done:
                    if use_trail and pos * (bo - act_px) >= -EPS:
                        if not trail_on:
                            trail_on = True
                            best = bo
                        elif pos * (bo - best) > 0:
                            best = bo
                    bh = mh[j]
                    bl = ml[j]
                    high_first = (bh - bo) < (bo - bl) - EPS   # open -> nearer extreme -> other extreme -> close
                    p0 = bo
                    for seg in range(3):
                        if seg == 0:
                            p1 = bh if high_first else bl
                        elif seg == 1:
                            p1 = bl if high_first else bh
                        else:
                            p1 = mc[j]
                        if p1 == p0:
                            continue
                        if pos * (p1 - p0) > 0:
                            # towards profit: the target, then the trailing stop's activation / ratchet
                            if not np.isnan(limit) and pos * (p1 - limit) >= -EPS:
                                xp = limit
                                reason = X_TP
                                done = True
                                break
                            if use_trail and pos * (p1 - act_px) >= -EPS:
                                if not trail_on:
                                    trail_on = True
                                    best = p1
                                elif pos * (p1 - best) > 0:
                                    best = p1
                        else:
                            s_eff = stop
                            is_trail = False
                            if trail_on:
                                ts = best - pos * off_dist
                                if np.isnan(s_eff) or pos * (ts - s_eff) > 0:
                                    s_eff = ts
                                    is_trail = True
                            if not np.isnan(s_eff) and pos * (p1 - s_eff) <= EPS:
                                xp = s_eff - pos * slip
                                reason = X_TRAIL if is_trail else X_STOP
                                done = True
                                break
                        p0 = p1
                if done:
                    e_t[nt] = entry_time
                    x_t[nt] = mt[j]
                    dr[nt] = pos
                    e_px[nt] = entry_px
                    x_px[nt] = xp
                    risk[nt] = risk_dist
                    r_net[nt] = (pos * (xp - entry_px) - fee * (xp + entry_px)) / risk_dist
                    why[nt] = reason
                    sbar[nt] = sig_bar
                    nt += 1
                    pos = 0
                    break

        # ---- the script's single execution at this bar's close ----
        want = 0
        z = zone[i]
        if trig[i] and z != 0 and (wait == 0 or last_sig < 0 or i - last_sig > wait):
            want = -z if inverted else z
        go = 0
        if want > 0 and pos <= 0:
            go = 1
        elif want < 0 and pos >= 0:
            go = -1
        a = catr[i]
        if go != 0:
            if sl > 0 and not np.isnan(a) and a > 0:
                entry_atr = a
                last_sig = i
                pend_dir = go
                pend_ref = cc[i]
            elif pos == -go:
                pend_close = X_REV    # "Reverse (qty 0)": no entry, the opposite position is closed
        if pos != 0:
            # the bracket is re-issued from the average entry price (entryAtr may just have
            # been replaced by a reversal signal, as in the script; that position is then
            # closed at the next open before any tick)
            if not np.isnan(entry_atr):
                if sl > 0:
                    stop = entry_px - pos * entry_atr * sl
                if tp > 0:
                    limit = entry_px + pos * entry_atr * tp
            if use_vol_exit and volc[i]:
                pend_close = X_VOL
            if max_bars > 0 and i - entry_bar >= max_bars:
                pend_close = X_TIME

    # an open position is marked at the last close
    if pos != 0:
        last = i_end - 1
        px = cc[last]
        e_t[nt] = entry_time
        x_t[nt] = ct[last] + tf_ms
        dr[nt] = pos
        e_px[nt] = entry_px
        x_px[nt] = px
        risk[nt] = risk_dist
        r_net[nt] = (pos * (px - entry_px) - fee * (px + entry_px)) / risk_dist
        why[nt] = X_END
        sbar[nt] = sig_bar
        nt += 1
    return e_t[:nt], x_t[:nt], dr[:nt], e_px[:nt], x_px[:nt], risk[:nt], r_net[:nt], why[:nt], sbar[:nt]


def run(ft, chart_tf, p, fee=0.0006, slip_ticks=1, start_ms=None, end_ms=None, signals=None):
    """Backtest one parameter set on chart timeframe `chart_tf` (minutes).
    fee = commission per side as a fraction of the fill's value (0.0006 = 0.06 %).
    Entries fill from start_ms on (the signal may be the bar before). Returns trade arrays."""
    ch = ft.mk.tf(chart_tf)
    m1 = ft.mk.m1
    if signals is None:
        trig, volc, _ = trigger_arrays(ft, chart_tf, p)
        zone = zone_array(ft, chart_tf, p)
    else:
        trig, volc, zone = signals
    i0 = 0 if start_ms is None else int(np.searchsorted(ch.t, start_ms, side="left"))
    i1 = len(ch) if end_ms is None else int(np.searchsorted(ch.t, end_ms, side="left"))
    i0 = max(i0 - 1, 0)
    out = simulate(ch.t, ch.o, ch.c, ch.i0, ch.i1, ft.atr(chart_tf, p["exit_atr"]),
                   m1.t, m1.o, m1.h, m1.l, m1.c, trig, zone, volc,
                   bool(p["inverted"]), float(p["sl"]), float(p["tp"]), bool(p["trail"]),
                   float(p["trail_act"]), float(p["trail_off"]), bool(p["vol_exit"]),
                   int(p["max_bars"]), int(p["wait"]), float(fee), float(slip_ticks), MINTICK,
                   i0, i1, chart_tf * MIN_MS)
    keys = ("entry_t", "exit_t", "dir", "entry_px", "exit_px", "risk", "r", "why", "sig_bar")
    return dict(zip(keys, out))
