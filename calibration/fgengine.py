"""FlashGold v5 + Fractal Direction Framework: a Python/numba replica of
flashgold_v5_fdf_strategy.pine for calibration.

Bars are UTC-aligned OHLC built from 1-minute data. Higher-timeframe reads follow
TradingView's historical request.security semantics:
  lookahead_off  -> the latest bar of that timeframe closed by the chart bar's close
  [1] + lookahead_on (last CLOSED bar) -> the bar before the one containing the chart bar's open
Order fills: stop entries / market orders from the bar after the signal, exits (SL, TP, trailing)
evaluated along an intrabar price path: every 1-minute bar inside the chart bar with TradingView's
4-point rule (open -> nearer extreme -> other extreme -> close), or the chart bar itself (magnifier off).
(TradingView's own bar magnifier uses coarser intrabars from 15m charts up: 15m -> 2m, 30m -> 5m,
1H / 2H -> 10m, 4H / 8H -> 30m, 1D -> 60m, at most 200,000 of them.)
"""
import numpy as np
import numba as nb
import pandas as pd

NA = -99999          # int na
PT = 0.01            # syminfo.mintick of BTCUSD / BTCUSDT (prices with 2 decimals)

# ----------------------------------------------------------------------------- data
_BARS = {}
_BASE = None


def tf_minutes(tf):
    return 1440 if tf == "1D" else int(tf)


def load_base(path):
    global _BASE
    df = pd.read_parquet(path)
    _BASE = df
    _BARS.clear()
    return df


def bars(tf_min):
    """OHLC arrays of a timeframe in minutes (resampled from 1m, cached)."""
    if tf_min in _BARS:
        return _BARS[tf_min]
    if tf_min == 1:
        b = _BASE
    else:
        rule = "1D" if tf_min == 1440 else f"{tf_min}min"
        b = _BASE.resample(rule, label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    t_open = (b.index.asi8 // 1_000_000_000).astype(np.int64) if b.index.asi8.max() > 1e12 else b.index.asi8.astype(np.int64)
    d = dict(t_open=t_open, t_close=t_open + tf_min * 60,
             o=b["open"].to_numpy(np.float64), h=b["high"].to_numpy(np.float64),
             l=b["low"].to_numpy(np.float64), c=b["close"].to_numpy(np.float64), tf=tf_min)
    _BARS[tf_min] = d
    return d


def bars_from_frame(df, tf_min):
    """Bars from an arbitrary OHLC frame (e.g. a TradingView export), no resampling."""
    t_open = (df.index.asi8 // 1_000_000_000).astype(np.int64)
    return dict(t_open=t_open, t_close=t_open + tf_min * 60, o=df["open"].to_numpy(np.float64),
                h=df["high"].to_numpy(np.float64), l=df["low"].to_numpy(np.float64),
                c=df["close"].to_numpy(np.float64), tf=tf_min)


# ----------------------------------------------------------------------------- Pine built-ins
@nb.njit(cache=True)
def rsi_pine(c, n):
    N = len(c)
    out = np.full(N, np.nan)
    up = np.nan
    dn = np.nan
    a = 1.0 / n
    for i in range(N):
        if i < n:
            continue
        if np.isnan(up):
            su = 0.0
            sd = 0.0
            for j in range(i - n + 1, i + 1):
                ch = c[j] - c[j - 1]
                su += max(ch, 0.0)
                sd += max(-ch, 0.0)
            up = su / n
            dn = sd / n
        else:
            ch = c[i] - c[i - 1]
            up = a * max(ch, 0.0) + (1.0 - a) * up
            dn = a * max(-ch, 0.0) + (1.0 - a) * dn
        out[i] = 100.0 if dn == 0.0 else (0.0 if up == 0.0 else 100.0 - 100.0 / (1.0 + up / dn))
    return out


@nb.njit(cache=True)
def sma_pine(x, n):
    """ta.sma: na unless the last n values are all present."""
    N = len(x)
    out = np.full(N, np.nan)
    s = 0.0
    cnt = 0
    for i in range(N):
        if not np.isnan(x[i]):
            s += x[i]
            cnt += 1
        if i >= n:
            if not np.isnan(x[i - n]):
                s -= x[i - n]
                cnt -= 1
        if i >= n - 1 and cnt == n:
            out[i] = s / n
    return out


@nb.njit(cache=True)
def atr_pine(h, l, c, n):
    N = len(c)
    out = np.full(N, np.nan)
    a = 1.0 / n
    prev = np.nan
    for i in range(N):
        tr = h[i] - l[i] if i == 0 else max(max(h[i] - l[i], abs(h[i] - c[i - 1])), abs(l[i] - c[i - 1]))
        if i < n - 1:
            continue
        if np.isnan(prev):
            s = 0.0
            for j in range(i - n + 1, i + 1):
                s += h[j] - l[j] if j == 0 else max(max(h[j] - l[j], abs(h[j] - c[j - 1])), abs(l[j] - c[j - 1]))
            prev = s / n
        else:
            prev = a * tr + (1.0 - a) * prev
        out[i] = prev
    return out


@nb.njit(cache=True)
def tdi_dir(c, rsi_len, fast_len):
    f = sma_pine(rsi_pine(c, rsi_len), fast_len)
    N = len(c)
    d = np.zeros(N, np.int64)
    for i in range(1, N):
        if not np.isnan(f[i]) and not np.isnan(f[i - 1]):
            d[i] = 1 if f[i] > f[i - 1] else (-1 if f[i] < f[i - 1] else 0)
    return d, f


@nb.njit(cache=True)
def pivots(h, l, L, R):
    """ta.pivothigh / ta.pivotlow: at bar i, bar i-R is a pivot when it is strictly
    beyond the L bars on its left and not exceeded by the R bars on its right."""
    N = len(h)
    ph = np.full(N, np.nan)
    pl = np.full(N, np.nan)
    for i in range(L + R, N):
        c = i - R
        okh = True
        okl = True
        for k in range(1, L + 1):
            if not (h[c] > h[c - k]):
                okh = False
            if not (l[c] < l[c - k]):
                okl = False
        for k in range(1, R + 1):
            if not (h[c] >= h[c + k]):
                okh = False
            if not (l[c] <= l[c + k]):
                okl = False
        if okh:
            ph[i] = h[c]
        if okl:
            pl[i] = l[c]
    return ph, pl


@nb.njit(cache=True)
def lowest_pine(x, n):
    N = len(x)
    out = np.full(N, np.nan)
    for i in range(n - 1, N):
        m = x[i]
        for j in range(i - n + 1, i + 1):
            if x[j] < m:
                m = x[j]
        out[i] = m
    return out


@nb.njit(cache=True)
def highest_pine(x, n):
    N = len(x)
    out = np.full(N, np.nan)
    for i in range(n - 1, N):
        m = x[i]
        for j in range(i - n + 1, i + 1):
            if x[j] > m:
                m = x[j]
        out[i] = m
    return out


def hurst_pine(c, W):
    """[h(2), h(-2) - h(2)] per bar, exactly as fdK2 / fdKm2 / fdSlope / fdHurst."""
    x = np.log(c)
    lt = np.log(np.array([2.0, 4.0, 8.0, 16.0]))
    y2 = []
    ym2 = []
    for tau in (2, 4, 8, 16):
        dx = np.full(len(x), np.nan)
        dx[tau:] = x[tau:] - x[:-tau]
        m = sma_pine(dx, W)
        k2 = np.maximum(sma_pine(dx * dx, W) - m * m, 1e-20)
        k2[np.isnan(m)] = np.nan
        d = np.abs(dx - m)
        fl = 0.25 * sma_pine(d, W)
        km2 = sma_pine(np.power(d + fl, -2.0), W)
        y2.append(np.log(k2) / 2.0)
        ym2.append(np.log(km2) / -2.0)

    def slope(ys):
        Y = np.vstack(ys)
        sx = lt.sum()
        sxx = (lt * lt).sum()
        return (4.0 * (lt[:, None] * Y).sum(0) - sx * Y.sum(0)) / (4.0 * sxx - sx * sx)
    h2 = slope(y2)
    return h2, slope(ym2) - h2


# ----------------------------------------------------------------------------- MTF mapping
def map_off(src, ctx):
    """lookahead_off (history): latest src bar whose close <= the chart bar's close."""
    return np.searchsorted(src["t_close"], ctx["t_close"], side="right") - 1


def map_prev_on(src, ctx):
    """[1] + lookahead_on: the src bar before the one that contains the chart bar's open."""
    return np.searchsorted(src["t_open"], ctx["t_open"], side="right") - 2


def take(arr, idx, fill):
    out = np.full(len(idx), fill, dtype=arr.dtype)
    ok = (idx >= 0) & (idx < len(arr))
    out[ok] = arr[idx[ok]]
    return out


# ----------------------------------------------------------------------------- FlashGold signal
@nb.njit(cache=True)
def flashgold_signal(c, atr14, parent_dir, zdir, zuse, pt, spread_pts, entry_dist_pts, hold_bars,
                     hold_fav_pts, one_per_bar, atr_unit, burst_atr, entry_dist_atr, hold_fav_atr,
                     burst_pts_in, use_burst, any_combo, drift_bars, use_drift, use_zones, min_aligned,
                     flat_parent, ignore_na):
    N = len(c)
    buy = np.zeros(N, np.bool_)
    sell = np.zeros(N, np.bool_)
    bpx = np.full(N, np.nan)
    spx = np.full(N, np.nan)
    zbuy = np.zeros(N, np.bool_)
    zsell = np.zeros(N, np.bool_)
    pside = np.zeros(N, np.int64)
    half = spread_pts * pt * 0.5
    hold_active = False
    hold_is_buy = False
    hold_bar = NA
    hold_mid = np.nan
    last_entry = NA
    for k in range(N):
        bid = c[k] - half
        ask = c[k] + half
        mid = (bid + ask) * 0.5
        pd_ = parent_dir[k]
        active = 0
        zon = np.zeros(6, np.bool_)
        for z in range(6):
            zon[z] = zuse[z] and ((not ignore_na) or zdir[z, k] != NA)
            if zon[z]:
                active += 1
        ps = 0 if pd_ == NA else (1 if pd_ > 0 else (-1 if pd_ < 0 else 0))
        pside[k] = ps
        aligned = 0
        for z in range(6):
            if zon[z] and ps != 0 and zdir[z, k] == ps:
                aligned += 1
        req = min(min_aligned, active)
        flat_ok = flat_parent and ps == 0
        ready = active == 0 or aligned >= req
        tzb = (not use_zones) or ((ps == 1 or flat_ok) and ready)
        tzs = (not use_zones) or ((ps == -1 or flat_ok) and ready)
        zbuy[k] = tzb
        zsell[k] = tzs
        thr_ok = (not atr_unit) or (not np.isnan(atr14[k]))
        atr_pts = atr14[k] / pt if (atr_unit and thr_ok) else 0.0
        burst_thr = burst_atr * atr_pts if atr_unit else burst_pts_in
        edist = entry_dist_atr * atr_pts if atr_unit else entry_dist_pts
        hfav = hold_fav_atr * atr_pts if atr_unit else hold_fav_pts
        burst_ok = k >= 1
        bpts = ((mid - ((c[k - 1] - half + c[k - 1] + half) * 0.5)) / pt) if burst_ok else 0.0
        drift_ok = k >= drift_bars
        dpts = ((mid - ((c[k - drift_bars] - half + c[k - drift_bars] + half) * 0.5)) / pt) if drift_ok else 0.0
        bb = burst_ok and thr_ok and bpts >= burst_thr
        bs = burst_ok and thr_ok and bpts <= -burst_thr
        pbok = (not use_drift) or (drift_ok and dpts > 0)
        psok = (not use_drift) or (drift_ok and dpts < 0)
        rb = (tzb and ((not use_burst) or bb or ps == 1)) if any_combo else (tzb and bb)
        rs = (tzs and ((not use_burst) or bs or ps == -1)) if any_combo else (tzs and bs)
        bc = rb and pbok
        sc = rs and psok
        can_fire = (not one_per_bar) or last_entry == NA or last_entry != k
        if bc and can_fire:
            if hold_bars == 0:
                bpx[k] = ask + edist * pt if thr_ok else np.nan
                buy[k] = True
                last_entry = k
            elif not hold_active:
                hold_active = True
                hold_is_buy = True
                hold_bar = k
                hold_mid = mid
            elif hold_is_buy:
                if k - hold_bar >= hold_bars and thr_ok and (mid - hold_mid) / pt >= hfav:
                    bpx[k] = ask + edist * pt
                    buy[k] = True
                    last_entry = k
                    hold_active = False
        if sc and can_fire:
            if hold_bars == 0:
                spx[k] = bid - edist * pt if thr_ok else np.nan
                sell[k] = True
                last_entry = k
            elif not hold_active:
                hold_active = True
                hold_is_buy = False
                hold_bar = k
                hold_mid = mid
            elif not hold_is_buy:
                if k - hold_bar >= hold_bars and thr_ok and (hold_mid - mid) / pt >= hfav:
                    spx[k] = bid - edist * pt
                    sell[k] = True
                    last_entry = k
                    hold_active = False
        if hold_active and ((hold_is_buy and not tzb) or ((not hold_is_buy) and not tzs)):
            hold_active = False
            hold_bar = NA
            hold_mid = np.nan
    return buy, sell, bpx, spx, zbuy, zsell, pside


# ----------------------------------------------------------------------------- FDF structure
@nb.njit(cache=True)
def fdf_structure(h, l, c, mom, ph, pl, lo_piv, hi_piv, piv_r, div_bars):
    N = len(c)
    o_dir = np.zeros(N, np.int64)
    o_pl = np.full(N, np.nan)
    o_ph = np.full(N, np.nan)
    o_wu = np.zeros(N, np.bool_)
    o_wd = np.zeros(N, np.bool_)
    lo_since_h = np.nan
    hi_since_l = np.nan
    lastH = np.nan
    prevH = np.nan
    lastHM = np.nan
    prevHM = np.nan
    lastL = np.nan
    prevL = np.nan
    lastLM = np.nan
    prevLM = np.nan
    d = 0
    protL = np.nan
    protH = np.nan
    div_dir = 0
    div_age = 0
    for i in range(N):
        lo_since_h = l[i] if np.isnan(lo_since_h) else min(lo_since_h, l[i])
        hi_since_l = h[i] if np.isnan(hi_since_l) else max(hi_since_l, h[i])
        div_age += 1
        if not np.isnan(ph[i]):
            prevH = lastH
            prevHM = lastHM
            lastH = ph[i]
            lastHM = mom[i - piv_r] if i - piv_r >= 0 else np.nan
            lo_since_h = lo_piv[i]
            if (not np.isnan(prevH)) and lastH > prevH:
                if (not np.isnan(prevHM)) and lastHM < prevHM and d != -1:
                    div_dir = -1
                    div_age = 0
                elif div_dir == -1:
                    div_dir = 0
            if d == -1 and (np.isnan(protH) or ph[i] < protH):
                protH = ph[i]
        if not np.isnan(pl[i]):
            prevL = lastL
            prevLM = lastLM
            lastL = pl[i]
            lastLM = mom[i - piv_r] if i - piv_r >= 0 else np.nan
            hi_since_l = hi_piv[i]
            if (not np.isnan(prevL)) and lastL < prevL:
                if (not np.isnan(prevLM)) and lastLM > prevLM and d != 1:
                    div_dir = 1
                    div_age = 0
                elif div_dir == 1:
                    div_dir = 0
            if d == 1 and (np.isnan(protL) or pl[i] > protL):
                protL = pl[i]
        if d == 1 and (not np.isnan(protL)) and c[i] < protL:
            d = -1
            protH = lastH if np.isnan(hi_since_l) else hi_since_l
            protL = np.nan
            div_dir = 0
        elif d == -1 and (not np.isnan(protH)) and c[i] > protH:
            d = 1
            protL = lastL if np.isnan(lo_since_h) else lo_since_h
            protH = np.nan
            div_dir = 0
        elif d == 0:
            if (not np.isnan(lastH)) and c[i] > lastH:
                d = 1
                protL = lastL if np.isnan(lo_since_h) else lo_since_h
            elif (not np.isnan(lastL)) and c[i] < lastL:
                d = -1
                protH = lastH if np.isnan(hi_since_l) else hi_since_l
        o_dir[i] = d
        o_pl[i] = protL
        o_ph[i] = protH
        o_wu[i] = d == 1 and div_dir == -1 and div_age < div_bars
        o_wd[i] = d == -1 and div_dir == 1 and div_age < div_bars
    return o_dir, o_pl, o_ph, o_wu, o_wd


@nb.njit(cache=True)
def fdf_pullback(h, l, c, fdir):
    """fdDepth before each bar (the chart-side sub-trend), as the Pine code."""
    N = len(c)
    depth = np.zeros(N)
    ext = np.nan
    ctr = np.nan
    prev = 0
    for k in range(N):
        d = fdir[k]
        if d != prev:
            ext = np.nan
            ctr = np.nan
        depth[k] = 0.0 if (np.isnan(ext) or np.isnan(ctr)) else abs(ext - ctr)
        if d == 1:
            if np.isnan(ext) or h[k] > ext:
                ext = h[k]
                ctr = c[k]
            else:
                ctr = min(ctr, l[k])
        elif d == -1:
            if np.isnan(ext) or l[k] < ext:
                ext = l[k]
                ctr = c[k]
            else:
                ctr = max(ctr, h[k])
        prev = d
    return depth


# ----------------------------------------------------------------------------- order simulation
# exit reasons
R_SL, R_TP, R_TRAIL, R_CLOSE, R_REV, R_END = 1, 2, 3, 4, 5, 6


@nb.njit(cache=True)
def allow_rev_ok(flag):
    return flag

@nb.njit(cache=True)
def _path(o, h, l, c):
    """TradingView's 4-point intrabar path of one bar."""
    if h - o <= o - l:
        return o, h, l, c
    return o, l, h, c


@nb.njit(cache=True)
def simulate(t_open, ch_o, ch_h, ch_l, ch_c, m_o, m_h, m_l, m_c, m_start, m_end, use_mag,
             buy, sell, bpx, spx, fd_buy_ok, fd_sell_ok, flip_up, flip_dn, fd_on, fd_exit_break,
             sl_t, tp_t, act_t, dst_t, use_trail, entry_valid, allow_rev, exit_opp, allow_l, allow_s,
             max_bars_held, re_mode, re_max, re_ok_l, re_ok_s, re_dist, pt, slip_ticks, fee_pct):
    """Returns trades as arrays: dir, entry bar, entry px, exit bar, exit px, reason, pnl (per 1 unit, after fees)."""
    N = len(ch_c)
    cap = N // 2 + 16
    t_dir = np.zeros(cap, np.int64)
    t_eb = np.zeros(cap, np.int64)
    t_ep = np.zeros(cap)
    t_xb = np.zeros(cap, np.int64)
    t_xp = np.zeros(cap)
    t_rs = np.zeros(cap, np.int64)
    t_pnl = np.zeros(cap)
    t_re = np.zeros(cap, np.bool_)
    nt = 0
    slip = slip_ticks * pt
    pos = 0
    epx = 0.0
    ebar = 0
    e_re = False
    x_sl = np.nan
    x_tp = np.nan
    x_act = np.nan
    x_dst = np.nan
    tr_on = False
    best = 0.0
    # pending entry stops (long / short) with their locked exits
    pl_on = False
    pl_px = 0.0
    pl_bar = NA
    ps_on = False
    ps_px = 0.0
    ps_bar = NA
    lk_l = np.full(4, np.nan)
    lk_s = np.full(4, np.nan)
    pl_re = False
    ps_re = False
    # market orders for the next open
    mk_close_l = False
    mk_close_s = False
    mk_enter = 0
    mk_lock = np.full(4, np.nan)
    re_count = 0
    exit_dir = 0          # side closed by trail / TP during the bar (for re-entry)
    for k in range(N):
        exit_dir = 0
        if use_mag:
            a0 = m_start[k]
            a1 = m_end[k]
        else:
            a0 = 0
            a1 = 1
        first = True
        prev_px = ch_c[k - 1] if k > 0 else ch_o[k]
        for mi in range(a0, a1):
            if use_mag:
                p0, p1, p2, p3 = _path(m_o[mi], m_h[mi], m_l[mi], m_c[mi])
            else:
                p0, p1, p2, p3 = _path(ch_o[k], ch_h[k], ch_l[k], ch_c[k])
            pts = (p0, p1, p2, p3)
            for si in range(4):
                target = pts[si]
                gap = si == 0
                if gap and first:
                    # the bar opens: market orders of the previous close fill here
                    first = False
                    if (mk_close_l and pos == 1) or (mk_close_s and pos == -1):
                        xp = target - slip if pos == 1 else target + slip
                        pnl = pos * (xp - epx) - fee_pct * (epx + xp)
                        t_dir[nt] = pos; t_eb[nt] = ebar; t_ep[nt] = epx; t_xb[nt] = k; t_xp[nt] = xp
                        t_rs[nt] = R_CLOSE; t_pnl[nt] = pnl; t_re[nt] = e_re; nt += 1
                        pos = 0
                    mk_close_l = False
                    mk_close_s = False
                    if mk_enter != 0:
                        d = mk_enter
                        if pos == -d:
                            xp = target + slip if pos == -1 else target - slip
                            pnl = pos * (xp - epx) - fee_pct * (epx + xp)
                            t_dir[nt] = pos; t_eb[nt] = ebar; t_ep[nt] = epx; t_xb[nt] = k; t_xp[nt] = xp
                            t_rs[nt] = R_REV; t_pnl[nt] = pnl; t_re[nt] = e_re; nt += 1
                            pos = 0
                        if pos == 0:
                            pos = d
                            epx = target + slip if d == 1 else target - slip
                            ebar = k
                            e_re = True
                            x_sl = mk_lock[0]; x_tp = mk_lock[1]; x_act = mk_lock[2]; x_dst = mk_lock[3]
                            tr_on = False
                            best = epx
                            pl_on = False     # OCA: the fill cancels the pending entry stops
                            ps_on = False
                            pl_bar = NA
                            ps_bar = NA
                        mk_enter = 0
                # walk from prev_px to target; on the first point of a 1m bar the move is a gap:
                # anything crossed fills at the target price
                cur = prev_px
                guard = 0
                while guard < 8:
                    guard += 1
                    up = target > cur
                    dn = target < cur
                    lvl = np.nan
                    ev = 0
                    if pos == 1:
                        if up:
                            if (not np.isnan(x_tp)) and x_tp > 0:
                                L = epx + x_tp * pt
                                if L <= target and (np.isnan(lvl) or L < lvl):
                                    lvl = L; ev = 2
                            if use_trail and (not tr_on) and (not np.isnan(x_act)) and (not np.isnan(x_dst)):
                                L = epx + x_act * pt
                                if L <= target and (np.isnan(lvl) or L < lvl):
                                    lvl = L; ev = 5
                        if dn:
                            if (not np.isnan(x_sl)) and x_sl > 0:
                                L = epx - x_sl * pt
                                if L >= target and (np.isnan(lvl) or L > lvl):
                                    lvl = L; ev = 1
                            if use_trail and tr_on:
                                L = best - x_dst * pt
                                if L >= target and (np.isnan(lvl) or L > lvl):
                                    lvl = L; ev = 3
                            if ps_on and allow_rev_ok(allow_rev):
                                L = ps_px
                                if L >= target and (np.isnan(lvl) or L > lvl):
                                    lvl = L; ev = 7
                    elif pos == -1:
                        if dn:
                            if (not np.isnan(x_tp)) and x_tp > 0:
                                L = epx - x_tp * pt
                                if L >= target and (np.isnan(lvl) or L > lvl):
                                    lvl = L; ev = 2
                            if use_trail and (not tr_on) and (not np.isnan(x_act)) and (not np.isnan(x_dst)):
                                L = epx - x_act * pt
                                if L >= target and (np.isnan(lvl) or L > lvl):
                                    lvl = L; ev = 5
                        if up:
                            if (not np.isnan(x_sl)) and x_sl > 0:
                                L = epx + x_sl * pt
                                if L <= target and (np.isnan(lvl) or L < lvl):
                                    lvl = L; ev = 1
                            if use_trail and tr_on:
                                L = best + x_dst * pt
                                if L <= target and (np.isnan(lvl) or L < lvl):
                                    lvl = L; ev = 3
                            if pl_on and allow_rev_ok(allow_rev):
                                L = pl_px
                                if L <= target and (np.isnan(lvl) or L < lvl):
                                    lvl = L; ev = 6
                    else:
                        if up and pl_on:
                            L = pl_px
                            if L <= target:
                                lvl = L; ev = 6
                        if dn and ps_on:
                            L = ps_px
                            if L >= target and (np.isnan(lvl) or L > lvl):
                                lvl = L; ev = 7
                    # a level already behind the current price (placed beyond it) fills now
                    if ev == 0:
                        # trailing high / low water mark follows the move
                        if pos == 1 and tr_on and target > best:
                            best = target
                        if pos == -1 and tr_on and target < best:
                            best = target
                        break
                    fill_at = target if gap else (lvl if ((up and lvl >= cur) or (dn and lvl <= cur)) else cur)
                    if ev == 5:
                        tr_on = True
                        best = fill_at
                        cur = fill_at
                        continue
                    if ev == 1 or ev == 3 or ev == 2:
                        if ev == 2:
                            xp = fill_at
                        else:
                            xp = fill_at - slip if pos == 1 else fill_at + slip
                        pnl = pos * (xp - epx) - fee_pct * (epx + xp)
                        t_dir[nt] = pos; t_eb[nt] = ebar; t_ep[nt] = epx; t_xb[nt] = k; t_xp[nt] = xp
                        t_rs[nt] = R_SL if ev == 1 else (R_TP if ev == 2 else R_TRAIL)
                        t_pnl[nt] = pnl; t_re[nt] = e_re; nt += 1
                        # the bar's LAST close decides the re-entry (a later stop-loss exit cancels it)
                        exit_dir = 0 if ev == 1 else pos
                        pos = 0
                        cur = fill_at
                        continue
                    if ev == 6 or ev == 7:
                        d = 1 if ev == 6 else -1
                        fp = fill_at + slip if d == 1 else fill_at - slip
                        if pos == -d:
                            pnl = pos * (fp - epx) - fee_pct * (epx + fp)
                            t_dir[nt] = pos; t_eb[nt] = ebar; t_ep[nt] = epx; t_xb[nt] = k; t_xp[nt] = fp
                            t_rs[nt] = R_REV; t_pnl[nt] = pnl; t_re[nt] = e_re; nt += 1
                        pos = d
                        epx = fp
                        ebar = k
                        tr_on = False
                        best = fp
                        if d == 1:
                            x_sl = lk_l[0]; x_tp = lk_l[1]; x_act = lk_l[2]; x_dst = lk_l[3]
                            e_re = pl_re
                        else:
                            x_sl = lk_s[0]; x_tp = lk_s[1]; x_act = lk_s[2]; x_dst = lk_s[3]
                            e_re = ps_re
                        if not e_re:
                            re_count = 0
                        pl_on = False     # OCA: one side filled, both stops are cancelled
                        ps_on = False
                        cur = fill_at
                        continue
                    break
                prev_px = target
            if not use_mag:
                break
        # ---------------- the strategy at the close of bar k
        in_l = pos == 1
        in_s = pos == -1
        flat = pos == 0
        if exit_opp and sell[k] and in_l:
            mk_close_l = True
        if exit_opp and buy[k] and in_s:
            mk_close_s = True
        if fd_on and fd_exit_break and flip_dn[k]:
            if in_l:
                mk_close_l = True
            pl_on = False
            pl_bar = NA
        if fd_on and fd_exit_break and flip_up[k]:
            if in_s:
                mk_close_s = True
            ps_on = False
            ps_bar = NA
        placed_l = False
        placed_s = False
        if buy[k] and allow_l and fd_buy_ok[k] and (not in_l) and (flat or allow_rev or exit_opp):
            if not np.isnan(bpx[k]):
                lk_l[0] = sl_t[k]; lk_l[1] = tp_t[k]; lk_l[2] = act_t[k]; lk_l[3] = dst_t[k]
                pl_on = True
                pl_px = bpx[k]
                pl_bar = k
                pl_re = False
                placed_l = True
        if sell[k] and allow_s and fd_sell_ok[k] and (not in_s) and (flat or allow_rev or exit_opp):
            if not np.isnan(spx[k]):
                lk_s[0] = sl_t[k]; lk_s[1] = tp_t[k]; lk_s[2] = act_t[k]; lk_s[3] = dst_t[k]
                ps_on = True
                ps_px = spx[k]
                ps_bar = k
                ps_re = False
                placed_s = True
        if entry_valid > 0:
            if pl_bar != NA and (not in_l) and k - pl_bar >= entry_valid:
                pl_on = False
                pl_bar = NA
            if ps_bar != NA and (not in_s) and k - ps_bar >= entry_valid:
                ps_on = False
                ps_bar = NA
        if max_bars_held > 0 and (not flat) and k - ebar >= max_bars_held:
            if in_l:
                mk_close_l = True
            if in_s:
                mk_close_s = True
        # re-entry: a trail / TP exit this bar while the opportunity continues
        if re_mode > 0 and exit_dir != 0 and pos == 0 and (re_max == 0 or re_count < re_max):
            d = exit_dir
            ok = (re_ok_l[k] and allow_l) if d == 1 else (re_ok_s[k] and allow_s)
            if ok and not (placed_l if d == 1 else placed_s):
                re_count += 1
                if re_mode == 1:
                    mk_enter = d
                    mk_lock[0] = sl_t[k]; mk_lock[1] = tp_t[k]; mk_lock[2] = act_t[k]; mk_lock[3] = dst_t[k]
                else:
                    if d == 1:
                        lk_l[0] = sl_t[k]; lk_l[1] = tp_t[k]; lk_l[2] = act_t[k]; lk_l[3] = dst_t[k]
                        pl_on = True
                        pl_px = re_dist[k] + ch_c[k]
                        pl_bar = k
                        pl_re = True
                    else:
                        lk_s[0] = sl_t[k]; lk_s[1] = tp_t[k]; lk_s[2] = act_t[k]; lk_s[3] = dst_t[k]
                        ps_on = True
                        ps_px = ch_c[k] - re_dist[k]
                        ps_bar = k
                        ps_re = True
    if pos != 0:
        xp = ch_c[N - 1]
        pnl = pos * (xp - epx) - fee_pct * (epx + xp)
        t_dir[nt] = pos; t_eb[nt] = ebar; t_ep[nt] = epx; t_xb[nt] = N - 1; t_xp[nt] = xp
        t_rs[nt] = R_END; t_pnl[nt] = pnl; t_re[nt] = e_re; nt += 1
    return t_dir[:nt], t_eb[:nt], t_ep[:nt], t_xb[:nt], t_xp[:nt], t_rs[:nt], t_pnl[:nt], t_re[:nt]



# ----------------------------------------------------------------------------- signal quality
@nb.njit(cache=True)
def label_signals(h, l, c, atr, sig, d, x_atr, horizon):
    """1 = the move went +x ATR before -x ATR within the horizon (a real signal), 0 = it went
    against first (the end of the move), -1 = neither (undecided)."""
    N = len(c)
    out = np.full(N, -2, np.int64)
    for k in range(N):
        if not sig[k] or np.isnan(atr[k]):
            continue
        up = c[k] + x_atr * atr[k]
        dn = c[k] - x_atr * atr[k]
        res = -1
        for j in range(k + 1, min(N, k + 1 + horizon)):
            hu = h[j] >= up
            hd = l[j] <= dn
            if hu and hd:
                res = 0
                break
            if hu:
                res = 1 if d == 1 else 0
                break
            if hd:
                res = 1 if d == -1 else 0
                break
        out[k] = res
    return out
