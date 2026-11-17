"""Python port of FlashGold_v5_Strategy_BTCUSD.mq5 for calibration.

Signals are computed on chart bars built from 1-minute data (same rules as the EA: TDI parent and
child zones with auto timeframes chart / 2x / 4x read from the last closed higher-timeframe bar,
burst gate in ATR units, stop-order entry at ask + distance / bid - distance). Trades are then
simulated minute by minute, which is what the EA does on ticks: entry stops, expiry, OCA, reversal,
broker stop loss, fixed take profit or partial + runner with breakeven and trail, time stop.

Prices: the 1-minute bars are taken as BID. ask = bid + spread. Longs open at ask and close at bid,
shorts open at bid and close at ask, as on a MetaTrader account.

Inside one minute the order of high and low is unknown. The stop is always checked before any
favourable move. For the minute in which an entry fills, `pess=True` counts the trade as stopped
whenever that minute's range reaches the stop (worst case); `pess=False` only when the minute
closes beyond the stop (best case). The truth lies between the two.
"""
import numpy as np
from numba import njit


# ----------------------------------------------------------------------------- indicators
@njit(cache=True)
def rsi_wilder(c, n):
    out = np.full(c.size, np.nan)
    if c.size <= n:
        return out
    g = 0.0
    lo = 0.0
    for i in range(1, n + 1):
        d = c[i] - c[i - 1]
        if d > 0:
            g += d
        else:
            lo -= d
    g /= n
    lo /= n
    out[n] = 100.0 if lo == 0 else 100.0 - 100.0 / (1.0 + g / lo)
    for i in range(n + 1, c.size):
        d = c[i] - c[i - 1]
        g = (g * (n - 1) + (d if d > 0 else 0.0)) / n
        lo = (lo * (n - 1) + (-d if d < 0 else 0.0)) / n
        out[i] = 100.0 if lo == 0 else 100.0 - 100.0 / (1.0 + g / lo)
    return out


@njit(cache=True)
def atr_wilder(h, l, c, n):
    out = np.full(c.size, np.nan)
    if c.size <= n:
        return out
    s = 0.0
    a = 0.0
    for i in range(1, c.size):
        tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        if i <= n:
            s += tr
            if i == n:
                a = s / n
                out[i] = a
        else:
            a = (a * (n - 1) + tr) / n
            out[i] = a
    return out


def resample(o, h, l, c, k):
    """Group consecutive bars k at a time (the data starts at 00:00 UTC and has no gaps)."""
    n = (o.size // k) * k
    return (o[:n].reshape(-1, k)[:, 0].copy(), h[:n].reshape(-1, k).max(1), l[:n].reshape(-1, k).min(1),
            c[:n].reshape(-1, k)[:, -1].copy())


def tdi_dir(c, rsi_len, fast_len):
    """Direction of the fast TDI line: sign(SMA(rsi, fast) - its previous value) = sign(rsi - rsi[fast])."""
    r = rsi_wilder(c, rsi_len)
    d = np.full(c.size, np.nan)
    diff = r[fast_len:] - r[:-fast_len]
    d[fast_len:] = np.sign(diff)
    return d   # nan = no data


MT5_MINUTES = {1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60, 120, 180, 240, 360, 480, 720, 1440}


def make_signals(m1, tf_min, sp, bpm=1, chart=None):
    """sp: dict of signal parameters; bpm = data bars per minute (1 for 1-minute data, 60 for 1-second).
    Returns per-chart-bar arrays."""
    o, h, l, c = chart if chart is not None else resample(m1["o"], m1["h"], m1["l"], m1["c"], tf_min * bpm)
    n = c.size
    rsi_len, fast = sp["rsi_len"], sp["fast_len"]
    parent = tdi_dir(c, rsi_len, fast)
    j = np.arange(n)
    zones = [parent.copy()]                                   # zone 1 = chart timeframe
    for mult in (2, 4):                                        # zones 2 and 3 = 2x and 4x the chart
        if tf_min * mult not in MT5_MINUTES:
            continue                                           # timeframe missing in MetaTrader: zone dropped
        ch = resample(o, h, l, c, mult)[3]
        dh = tdi_dir(ch, rsi_len, fast)
        J = j // mult - 1                                      # last CLOSED higher-timeframe bar
        z = np.full(n, np.nan)
        ok = (J >= 0) & (J < dh.size)
        z[ok] = dh[J[ok]]
        zones.append(z)
    use = sp.get("use_zones", (True, True, True))
    zones = [z for z, u in zip(zones, use[:len(zones)]) if u]
    pside = np.where(np.isnan(parent), 0.0, parent)
    active = np.zeros(n)
    aligned = np.zeros(n)
    for z in zones:
        on = ~np.isnan(z)                                      # "ignore zones without data"
        active += on
        aligned += on & (pside != 0) & (z == pside)
    required = np.minimum(sp["min_aligned"], active)
    ready = (active == 0) | (aligned >= required)
    if sp.get("use_zone_filter", True):
        buy_ok = (pside == 1) & ready
        sell_ok = (pside == -1) & ready
    else:
        buy_ok = np.ones(n, bool)
        sell_ok = np.ones(n, bool)
    atr14 = atr_wilder(h, l, c, 14)
    atrv = atr14 if sp.get("atr_len", 14) == 14 else atr_wilder(h, l, c, sp["atr_len"])
    burst = np.full(n, np.nan)
    burst[1:] = c[1:] - c[:-1]
    thr = sp["burst_atr"] * atr14
    valid = ~np.isnan(atr14) & ~np.isnan(atrv) & ~np.isnan(burst)
    buy = valid & buy_ok & (burst >= thr)
    sell = valid & sell_ok & (burst <= -thr)
    half = 0.5 * sp.get("spread_input", 0.25)
    dist = sp["entry_dist_atr"] * atr14
    warm = 300
    buy[:warm] = False
    sell[:warm] = False
    return dict(buy=buy, sell=sell, ent_b=c + half + dist, ent_s=c - half - dist,
                atr14=np.nan_to_num(atr14), atrv=np.nan_to_num(atrv), n=n)


# ----------------------------------------------------------------------------- trade simulation
@njit(cache=True)
def simulate(o, h, l, c, N, buy, sell, ent_b, ent_s, atr14, atrv,
             spread, fee, pess,
             sl_atr, sl_abs, tp_r, runner, part_pct, run_be, run_atr, run_abs,
             use_trail, act_atr, act_abs, dst_atr, dst_abs,
             valid_bars, allow_rev, exit_opp, direction, max_held):
    """Returns (count, entry_idx, exit_idx, side, ret, r_mult).
    ret = profit / entry price for a constant quantity, costs included; r_mult = profit / initial stop distance.
    direction: 0 both, 1 long only, -1 short only. fee = commission per side as a fraction of notional."""
    n1 = o.size
    nb = buy.size
    cap = 2 * nb + 16
    t_in = np.empty(cap, np.int64)
    t_out = np.empty(cap, np.int64)
    t_side = np.empty(cap, np.int8)
    t_ret = np.empty(cap, np.float64)
    t_r = np.empty(cap, np.float64)
    nt = 0

    pos = 0
    entry = 0.0
    qty = 0.0
    stop = 0.0
    has_stop = False
    sl0 = 0.0
    tpd = 0.0
    rund = 0.0
    actd = 0.0
    dstd = 0.0
    touched = False
    tphit = False
    partdone = False
    ext = 0.0
    ebar = 0
    eidx = 0
    acc = 0.0        # realised profit of the open position, price units x quantity fraction

    pl = False
    pl_price = 0.0
    pl_bar = 0
    pl_sl = 0.0
    pl_tp = 0.0
    pl_run = 0.0
    pl_act = 0.0
    pl_dst = 0.0
    ps = False
    ps_price = 0.0
    ps_bar = 0
    ps_sl = 0.0
    ps_tp = 0.0
    ps_run = 0.0
    ps_act = 0.0
    ps_dst = 0.0

    for i in range(N, n1):
        j = i // N
        if j >= nb + 1:
            break
        # ------------------------------------------------ close out helper is inlined below (numba)
        close_px = 0.0
        do_close = False
        open_side = 0
        open_px = 0.0

        if i % N == 0:
            k = j - 1                      # the chart bar that just closed
            bid0 = o[i]
            ask0 = o[i] + spread
            in_long = pos > 0
            in_short = pos < 0
            flat = pos == 0
            bsig = buy[k]
            ssig = sell[k]
            if exit_opp and pos != 0 and ((ssig and in_long) or (bsig and in_short)):
                px = bid0 if pos > 0 else ask0
                pnl = acc + pos * (px - entry) * qty - fee * (entry + px) * qty
                if nt < cap:
                    t_in[nt] = eidx; t_out[nt] = i; t_side[nt] = pos; t_ret[nt] = pnl / entry
                    t_r[nt] = pnl / sl0 if sl0 > 0 else 0.0
                    nt += 1
                pos = 0
            sl = sl_atr * atrv[k] + sl_abs
            tp = sl * tp_r
            run = max(run_atr * atrv[k] + run_abs, 0.01)
            act = act_atr * atr14[k] + act_abs
            dst = max(dst_atr * atr14[k] + dst_abs, 0.01)
            if bsig and direction >= 0 and not in_long and (flat or allow_rev or exit_opp):
                pl = True; pl_price = ent_b[k]; pl_bar = k
                pl_sl = sl; pl_tp = tp; pl_run = run; pl_act = act; pl_dst = dst
                if pl_price <= ask0:       # already through the market: filled at the open
                    pl = False
                    ps = False
                    if pos < 0:
                        pnl = acc + pos * (ask0 - entry) * qty - fee * (entry + ask0) * qty
                        if nt < cap:
                            t_in[nt] = eidx; t_out[nt] = i; t_side[nt] = pos; t_ret[nt] = pnl / entry
                            t_r[nt] = pnl / sl0 if sl0 > 0 else 0.0
                            nt += 1
                        pos = 0
                    if pos == 0:
                        pos = 1; entry = ask0; qty = 1.0; acc = 0.0; eidx = i; ebar = j
                        sl0 = pl_sl; tpd = pl_tp; rund = pl_run; actd = pl_act; dstd = pl_dst
                        has_stop = sl0 > 0; stop = entry - sl0
                        touched = False; tphit = False; partdone = False; ext = entry
            if ssig and direction <= 0 and not in_short and (flat or allow_rev or exit_opp):
                ps = True; ps_price = ent_s[k]; ps_bar = k
                ps_sl = sl; ps_tp = tp; ps_run = run; ps_act = act; ps_dst = dst
                if ps_price >= bid0:
                    ps = False
                    pl = False
                    if pos > 0:
                        pnl = acc + pos * (bid0 - entry) * qty - fee * (entry + bid0) * qty
                        if nt < cap:
                            t_in[nt] = eidx; t_out[nt] = i; t_side[nt] = pos; t_ret[nt] = pnl / entry
                            t_r[nt] = pnl / sl0 if sl0 > 0 else 0.0
                            nt += 1
                        pos = 0
                    if pos == 0:
                        pos = -1; entry = bid0; qty = 1.0; acc = 0.0; eidx = i; ebar = j
                        sl0 = ps_sl; tpd = ps_tp; rund = ps_run; actd = ps_act; dstd = ps_dst
                        has_stop = sl0 > 0; stop = entry + sl0
                        touched = False; tphit = False; partdone = False; ext = entry
            if valid_bars > 0:
                if pl and pos <= 0 and k - pl_bar >= valid_bars:
                    pl = False
                if ps and pos >= 0 and k - ps_bar >= valid_bars:
                    ps = False
            if pos != 0 and touched and not tphit and eidx < i:
                tphit = True
                if runner and run_be:
                    if pos > 0:
                        if (not has_stop) or entry > stop:
                            stop = entry
                        has_stop = True
                        if bid0 <= stop:
                            do_close = True; close_px = bid0
                    else:
                        if (not has_stop) or entry < stop:
                            stop = entry
                        has_stop = True
                        if ask0 >= stop:
                            do_close = True; close_px = ask0
            if pos != 0 and max_held > 0 and eidx < i and (j - 1) - ebar >= max_held:
                do_close = True
                close_px = bid0 if pos > 0 else ask0
            if do_close and pos != 0:
                pnl = acc + pos * (close_px - entry) * qty - fee * (entry + close_px) * qty
                if nt < cap:
                    t_in[nt] = eidx; t_out[nt] = i; t_side[nt] = pos; t_ret[nt] = pnl / entry
                    t_r[nt] = pnl / sl0 if sl0 > 0 else 0.0
                    nt += 1
                pos = 0
            do_close = False

        # ------------------------------------------------ A. manage the open position on this minute
        if pos > 0 and eidx < i:
            if has_stop and l[i] <= stop:
                do_close = True
                close_px = stop if o[i] > stop else o[i]
            else:
                if h[i] > ext:
                    ext = h[i]
                if tpd > 0 and not touched and ext - entry >= tpd:
                    touched = True
                    tp_px = entry + tpd
                    if o[i] > tp_px:
                        tp_px = o[i]
                    if not runner:
                        do_close = True; close_px = tp_px
                    elif part_pct > 0 and not partdone:
                        part = qty * part_pct
                        acc += (tp_px - entry) * part - fee * (entry + tp_px) * part
                        qty -= part
                        partdone = True
                if not do_close:
                    trail_on = (runner and tpd > 0) or ((not runner) and use_trail)
                    a = tpd if runner else actd
                    d = rund if runner else dstd
                    if trail_on and ext - entry >= a:
                        tr = ext - d
                        if (not has_stop) or tr > stop:
                            stop = tr; has_stop = True
                        if c[i] <= stop:
                            do_close = True; close_px = stop
        elif pos < 0 and eidx < i:
            if has_stop and h[i] + spread >= stop:
                do_close = True
                close_px = stop if o[i] + spread < stop else o[i] + spread
            else:
                if l[i] + spread < ext:
                    ext = l[i] + spread
                if tpd > 0 and not touched and entry - ext >= tpd:
                    touched = True
                    tp_px = entry - tpd
                    if o[i] + spread < tp_px:
                        tp_px = o[i] + spread
                    if not runner:
                        do_close = True; close_px = tp_px
                    elif part_pct > 0 and not partdone:
                        part = qty * part_pct
                        acc += (entry - tp_px) * part - fee * (entry + tp_px) * part
                        qty -= part
                        partdone = True
                if not do_close:
                    trail_on = (runner and tpd > 0) or ((not runner) and use_trail)
                    a = tpd if runner else actd
                    d = rund if runner else dstd
                    if trail_on and entry - ext >= a:
                        tr = ext + d
                        if (not has_stop) or tr < stop:
                            stop = tr; has_stop = True
                        if c[i] + spread >= stop:
                            do_close = True; close_px = stop
        if do_close and pos != 0:
            pnl = acc + pos * (close_px - entry) * qty - fee * (entry + close_px) * qty
            if nt < cap:
                t_in[nt] = eidx; t_out[nt] = i; t_side[nt] = pos; t_ret[nt] = pnl / entry
                t_r[nt] = pnl / sl0 if sl0 > 0 else 0.0
                nt += 1
            pos = 0

        # ------------------------------------------------ B. entry stops
        fl = pl and (h[i] + spread >= pl_price)
        fs = ps and (l[i] <= ps_price)
        if fl and fs:                       # both touched in one minute: take the side the minute closed towards
            if c[i] >= o[i]:
                fs = False
            else:
                fl = False
        if fl:
            px = pl_price if o[i] + spread < pl_price else o[i] + spread
            pl = False
            ps = False                      # OCA
            if pos < 0:                     # reversal: the short is closed at the same price
                pnl = acc + pos * (px - entry) * qty - fee * (entry + px) * qty
                if nt < cap:
                    t_in[nt] = eidx; t_out[nt] = i; t_side[nt] = pos; t_ret[nt] = pnl / entry
                    t_r[nt] = pnl / sl0 if sl0 > 0 else 0.0
                    nt += 1
                pos = 0
            if pos == 0:
                pos = 1; entry = px; qty = 1.0; acc = 0.0; eidx = i; ebar = j
                sl0 = pl_sl; tpd = pl_tp; rund = pl_run; actd = pl_act; dstd = pl_dst
                has_stop = sl0 > 0; stop = entry - sl0
                touched = False; tphit = False; partdone = False; ext = entry
                hit = has_stop and ((l[i] <= stop) if pess else (c[i] <= stop))
                if hit:
                    pnl = (stop - entry) - fee * (entry + stop)
                    if nt < cap:
                        t_in[nt] = i; t_out[nt] = i; t_side[nt] = 1; t_ret[nt] = pnl / entry; t_r[nt] = pnl / sl0
                        nt += 1
                    pos = 0
                elif c[i] > ext:
                    ext = c[i]
        elif fs:
            px = ps_price if o[i] > ps_price else o[i]
            ps = False
            pl = False
            if pos > 0:
                pnl = acc + pos * (px - entry) * qty - fee * (entry + px) * qty
                if nt < cap:
                    t_in[nt] = eidx; t_out[nt] = i; t_side[nt] = pos; t_ret[nt] = pnl / entry
                    t_r[nt] = pnl / sl0 if sl0 > 0 else 0.0
                    nt += 1
                pos = 0
            if pos == 0:
                pos = -1; entry = px; qty = 1.0; acc = 0.0; eidx = i; ebar = j
                sl0 = ps_sl; tpd = ps_tp; rund = ps_run; actd = ps_act; dstd = ps_dst
                has_stop = sl0 > 0; stop = entry + sl0
                touched = False; tphit = False; partdone = False; ext = entry
                hit = has_stop and ((h[i] + spread >= stop) if pess else (c[i] + spread >= stop))
                if hit:
                    pnl = (entry - stop) - fee * (entry + stop)
                    if nt < cap:
                        t_in[nt] = i; t_out[nt] = i; t_side[nt] = -1; t_ret[nt] = pnl / entry; t_r[nt] = pnl / sl0
                        nt += 1
                    pos = 0
                elif c[i] + spread < ext:
                    ext = c[i] + spread
    return nt, t_in[:nt], t_out[:nt], t_side[:nt], t_ret[:nt], t_r[:nt]


# ----------------------------------------------------------------------------- wrappers
EXIT_DEFAULT = dict(sl_atr=0.0, sl_abs=30.0, tp_r=5.0, runner=True, part_pct=0.30, run_be=True,
                    run_atr=0.0, run_abs=600.0, use_trail=False, act_atr=0.0, act_abs=150.0,
                    dst_atr=0.0, dst_abs=600.0, valid_bars=3, allow_rev=True, exit_opp=False,
                    direction=0, max_held=0)
SIG_DEFAULT = dict(rsi_len=14, fast_len=2, min_aligned=2, burst_atr=0.5, entry_dist_atr=0.25, atr_len=14)


def run(m1, tf_min, sig, ex, spread=15.0, fee=0.0, pess=True, signals=None, bpm=1):
    s = signals if signals is not None else make_signals(m1, tf_min, sig, bpm)
    e = dict(EXIT_DEFAULT)
    e.update(ex)
    return simulate(m1["o"], m1["h"], m1["l"], m1["c"], tf_min * bpm, s["buy"], s["sell"], s["ent_b"], s["ent_s"],
                    s["atr14"], s["atrv"], float(spread), float(fee), bool(pess),
                    float(e["sl_atr"]), float(e["sl_abs"]), float(e["tp_r"]), bool(e["runner"]), float(e["part_pct"]),
                    bool(e["run_be"]), float(e["run_atr"]), float(e["run_abs"]), bool(e["use_trail"]),
                    float(e["act_atr"]), float(e["act_abs"]), float(e["dst_atr"]), float(e["dst_abs"]),
                    int(e["valid_bars"]), bool(e["allow_rev"]), bool(e["exit_opp"]), int(e["direction"]), int(e["max_held"]))


def stats(res, t1m, lo=None, hi=None):
    """Metrics for trades whose entry time is in [lo, hi) (unix seconds). ret is per unit of notional."""
    nt, t_in, t_out, side, ret, r = res
    ts = t1m[t_in] if nt else np.empty(0, np.int64)
    m = np.ones(nt, bool)
    if lo is not None:
        m &= ts >= lo
    if hi is not None:
        m &= ts < hi
    ret = ret[m]
    r = r[m]
    n = ret.size
    if n == 0:
        return dict(n=0, net=0.0, pf=0.0, win=0.0, avg_r=0.0, t=0.0, dd=0.0)
    gp = ret[ret > 0].sum()
    gl = -ret[ret < 0].sum()
    eq = np.cumsum(ret)
    dd = float((np.maximum.accumulate(np.maximum(eq, 0.0)) - eq).max())
    sd = ret.std(ddof=1) if n > 1 else 0.0
    return dict(n=int(n), net=float(ret.sum() * 100), pf=float(gp / gl) if gl > 0 else 99.0,
                win=float((ret > 0).mean() * 100), avg_r=float(r.mean()),
                t=float(ret.mean() / sd * np.sqrt(n)) if sd > 0 else 0.0, dd=dd * 100)


def load(path):
    z = np.load(path)
    return {k: np.ascontiguousarray(z[k]) for k in ("t", "o", "h", "l", "c")}
