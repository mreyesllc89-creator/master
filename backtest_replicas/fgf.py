"""FlashGold Direction Filter (the block between BEGIN / END FLASHGOLD DIRECTION
FILTER in xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine, identical to
FlashGold_Direction_Filter_v1_2.pine): Python replica, CANONICAL module.

This file is a copy of fgf_b.py (implementation B, the faster of the two
implementations, which agree on every row of every reconcile case; see
reconcile_fgf.md). Only this docstring header differs from fgf_b.py.

    fgf_permissions(pair, chart_tf, start, end, params=None) -> DataFrame

History only: the Pine runs once per chart bar at its close (every bar is
confirmed), request.security follows the rules of SPEC.md. Interpretations are
listed in fgf_b_notes.md.

Pipeline
  1. TDI direction (fgfTdiDir) on the parent / child-zone timeframes' own
     series, mapped onto the FILTER timeframe's bars (nested request.security:
     the inner "chart" is the filter series).
  2. fgfSignal + fgfArm, bar by bar on the filter series (numba), giving the
     tuple fgfRead() returns ([0] and [1] values).
  3. That tuple mapped onto the chart bars (last filter bar with
     t_close <= chart t_close) and the chart-level logic (clock, pick, level,
     band, zones, permission window, gates), vectorised.

Run as a script for the spec's self-checks:  python3 -I fgf_b.py
"""
import math
import os
import sys
import time as _time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from numba import njit

W = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(W, 'data')
MINTICK = 0.01            # syminfo.mintick for both pairs (SPEC)

DEFAULTS = dict(
    fgfOn=True, fgfTf="60", fgfLvMode="Entry price", fgfLast="Until next signal",
    fgfMinutes=60, fgfBars=1, fgfCheck="Tick", fgfBandAtr=0.25, fgfAgainst=True,
    fgfAllowBuy=True, fgfAllowSell=True,
    # FlashGold signal: core
    fgfSpreadPts=25.0, fgfEntryDistPts=50.0, fgfHoldBars=0, fgfHoldFavPts=5.0, fgfOnePerBar=True,
    # burst / direction
    fgfDistUnit="ATR", fgfBurstAtr=0.5, fgfEntryDistAtr=0.25, fgfHoldFavAtr=0.1, fgfBurstPts=172.0,
    fgfUseBurst=True, fgfAnyCombo=False, fgfDriftBars=60, fgfUseDrift=False,
    # TDI trade zone
    fgfUseZones=True, fgfParentTf="60", fgfRsiLen=14, fgfFastLen=2, fgfMinAligned=2,
    fgfFlatParent=False, fgfIgnoreNa=True, fgfHtfClosed=True,
    fgfUseZ1=True, fgfZTf1="60", fgfUseZ2=True, fgfZTf2="120", fgfUseZ3=True, fgfZTf3="240",
    fgfUseZ4=False, fgfZTf4="480", fgfUseZ5=False, fgfZTf5="1", fgfUseZ6=False, fgfZTf6="2",
)
# display-only inputs of the block: accepted and ignored
_DISPLAY_KEYS = {'fgfShowBg', 'fgfShowLv', 'fgfSigMark', 'fgfShowTbl', 'fgfTblPos',
                 'fgsShow', 'fgsWin', 'fgsH', 'FGF_FORCE_OVERLAY'}
_OPTIONS = {
    'fgfLvMode': ("Entry price", "Signal close"),
    'fgfLast': ("Until next signal", "Minutes", "Candles"),
    'fgfCheck': ("Tick", "Candle open", "Candle close"),
    'fgfDistUnit': ("ATR", "Points"),
}
_MINVAL = {'fgfMinutes': 1, 'fgfBars': 1, 'fgfBandAtr': 0.0, 'fgfSpreadPts': 0.0, 'fgfEntryDistPts': 0.0,
           'fgfHoldBars': 0, 'fgfHoldFavPts': 0.0, 'fgfBurstAtr': 0.0, 'fgfEntryDistAtr': 0.0,
           'fgfHoldFavAtr': 0.0, 'fgfBurstPts': 0.0, 'fgfDriftBars': 1, 'fgfRsiLen': 2, 'fgfFastLen': 1,
           'fgfMinAligned': 0}


def _params(params):
    P = dict(DEFAULTS)
    for k, v in (params or {}).items():
        if k in DEFAULTS:
            P[k] = v
        # other keys (display inputs, other components' inputs) are ignored
    for k, opts in _OPTIONS.items():
        if P[k] not in opts:
            raise ValueError(f'{k}={P[k]!r} is not one of {opts}')
    for k, mv in _MINVAL.items():
        if P[k] < mv:
            raise ValueError(f'{k}={P[k]!r} is below the Pine minval {mv}')
    if P['fgfMinAligned'] > 6:
        raise ValueError('fgfMinAligned maxval is 6')
    for k in ('fgfMinutes', 'fgfBars', 'fgfHoldBars', 'fgfDriftBars', 'fgfRsiLen', 'fgfFastLen', 'fgfMinAligned'):
        P[k] = int(P[k])
    return P


# ----------------------------------------------------------------------------
# Timeframes and bars
# ----------------------------------------------------------------------------
def _parse_tf(tf):
    """Pine timeframe string -> (unit, n). Units: 'S' seconds, 'm' minutes,
    'D', 'W', 'M' (months)."""
    s = str(tf).strip()
    if s == '':
        raise ValueError('empty timeframe must be resolved by the caller')
    u = s.upper()
    if u[-1] in 'SDWMH' and not u.isdigit():
        unit, num = u[-1], u[:-1]
        n = int(num) if num else 1
        if unit == 'H':
            return ('m', n * 60)
        return (unit, n)
    return ('m', int(s))


def _tf_name(tf):
    unit, n = _parse_tf(tf)
    if unit == 'm':
        return str(n)
    if unit == 'S':
        return f'{n}S'
    return unit if n == 1 else f'{n}{unit}'


def tf_seconds(tf):
    """timeframe.in_seconds()"""
    unit, n = _parse_tf(tf)
    return n * {'S': 1, 'm': 60, 'D': 86400, 'W': 604800, 'M': 2628003}[unit]


_BARS = {}


def _read(pair, name, cols):
    key = (pair, name)
    have = _BARS.get(key)
    if have is not None and all(c in have for c in cols):
        return have
    f = os.path.join(DATA, f'{pair}_{name}.parquet')
    t = pq.read_table(f, columns=[c for c in cols if not (have and c in have)])
    d = dict(have or {})
    for c in t.column_names:
        a = t.column(c).to_numpy()
        d[c] = np.ascontiguousarray(a, dtype=np.float64 if c in ('open', 'high', 'low', 'close') else np.int64)
    _BARS[key] = d
    return d


def _build_minutes(pair, m):
    """Minute-multiple bars that have no file (e.g. "480", "2"), built from the
    1-minute file exactly as build_bars.py builds the others."""
    b = _read(pair, '1', ['open', 'high', 'low', 'close', 't_open', 't_close', 'sess'])
    to = b['t_open']
    s = m * 60
    if pair == 'XAU':
        sess = b['sess']
        us = np.unique(sess)
        sdate = pd.to_datetime(us, unit='D')
        st = (sdate - pd.Timedelta(days=1) + pd.Timedelta(hours=18)).tz_localize(
            'America/New_York', ambiguous='NaT', nonexistent='shift_forward').tz_convert('UTC')
        en = (sdate + pd.Timedelta(hours=17)).tz_localize(
            'America/New_York', ambiguous='NaT', nonexistent='shift_forward').tz_convert('UTC')
        ep = pd.Timestamp('1970-01-01', tz='UTC')
        st = np.asarray((st - ep) // pd.Timedelta(seconds=1), dtype=np.int64)
        en = np.asarray((en - ep) // pd.Timedelta(seconds=1), dtype=np.int64)
        pos = np.searchsorted(us, sess)
        s_start, s_end = st[pos], en[pos]
        o = s_start + ((to - s_start) // s) * s
        c = np.minimum(o + s, s_end)
    else:
        o = (to // s) * s
        c = o + s
    brk = np.flatnonzero(np.diff(o) != 0) + 1
    st_i = np.concatenate([[0], brk])
    en_i = np.concatenate([brk, [len(o)]]) - 1
    d = {
        'open': b['open'][st_i].copy(), 'close': b['close'][en_i].copy(),
        'high': np.maximum.reduceat(b['high'], st_i), 'low': np.minimum.reduceat(b['low'], st_i),
        't_open': o[st_i].copy(), 't_close': c[st_i].copy(), 'sess': b['sess'][st_i].copy(),
    }
    return d


def _bars(pair, tf, cols=('open', 'high', 'low', 'close', 't_open', 't_close')):
    """Bars of a timeframe, or None when it has no data (seconds)."""
    unit, n = _parse_tf(tf)
    if unit == 'S':
        return None
    name = _tf_name(tf)
    f = os.path.join(DATA, f'{pair}_{name}.parquet')
    if os.path.exists(f):
        return _read(pair, name, list(cols))
    if unit == 'm':
        key = (pair, name)
        if key not in _BARS:
            _BARS[key] = _build_minutes(pair, n)
        return _BARS[key]
    raise ValueError(f'no data for timeframe {tf!r} ({f}) and it cannot be built from 1m bars')


# ----------------------------------------------------------------------------
# Indicators (numba)
# ----------------------------------------------------------------------------
@njit(cache=True)
def _tdi_dir(close, rsi_len, fast_len):
    """fgfTdiDir(): r = ta.rsi(close, rsiLen); f = ta.sma(r, fastLen);
    f > f[1] ? 1 : f < f[1] ? -1 : 0  (na comparisons are false -> 0)."""
    n = close.shape[0]
    r = np.full(n, np.nan)
    if n > rsi_len:
        alpha = 1.0 / rsi_len
        su = 0.0
        sd = 0.0
        for i in range(1, rsi_len + 1):          # u, d are na at bar 0 -> rma seed = sma(bars 1..len)
            su += max(close[i] - close[i - 1], 0.0)
            sd += max(close[i - 1] - close[i], 0.0)
        up = su / rsi_len
        dn = sd / rsi_len
        for i in range(rsi_len, n):
            if i > rsi_len:
                u = max(close[i] - close[i - 1], 0.0)
                d = max(close[i - 1] - close[i], 0.0)
                up = alpha * u + (1.0 - alpha) * up
                dn = alpha * d + (1.0 - alpha) * dn
            if dn == 0.0:
                r[i] = 100.0
            elif up == 0.0:
                r[i] = 0.0
            else:
                r[i] = 100.0 - 100.0 / (1.0 + up / dn)
    f = np.full(n, np.nan)
    for i in range(fast_len - 1, n):
        s = 0.0
        ok = True
        for k in range(i - fast_len + 1, i + 1):
            if np.isnan(r[k]):
                ok = False
                break
            s += r[k]
        if ok:
            f[i] = s / fast_len
    d = np.zeros(n, np.float64)
    for i in range(1, n):
        if f[i] > f[i - 1]:
            d[i] = 1.0
        elif f[i] < f[i - 1]:
            d[i] = -1.0
    return d


@njit(cache=True)
def _atr(high, low, close, length):
    """ta.atr(length) = ta.rma(ta.tr(true), length)."""
    n = close.shape[0]
    out = np.full(n, np.nan)
    tr = np.empty(n)
    for i in range(n):
        hl = high[i] - low[i]
        if i == 0:
            tr[i] = hl
        else:
            tr[i] = max(max(hl, abs(high[i] - close[i - 1])), abs(low[i] - close[i - 1]))
    if n >= length:
        s = 0.0
        for i in range(length):
            s += tr[i]
        v = s / length
        out[length - 1] = v
        alpha = 1.0 / length
        for i in range(length, n):
            v = alpha * tr[i] + (1.0 - alpha) * v
            out[i] = v
    return out


@njit(cache=True)
def _signal_arm(close, tclose, atr, tz_buy, tz_sell, parent_side,
                pt, spread_pts, unit_atr, burst_atr, entry_atr, holdfav_atr,
                burst_pts_in, entry_pts_in, holdfav_pts_in,
                use_burst, any_combo, drift_bars, use_drift,
                hold_bars, one_per_bar, lv_entry):
    """fgfSignal() then fgfArm(), bar by bar on the filter series."""
    n = close.shape[0]
    buy_sig = np.zeros(n, np.bool_)
    sell_sig = np.zeros(n, np.bool_)
    sig_px = np.full(n, np.nan)
    a_at = np.full(n, np.nan)
    a_bar = np.full(n, np.nan)
    a_px = np.full(n, np.nan)
    a_dir = np.zeros(n)
    a_id = np.zeros(n)
    a_atr = np.full(n, np.nan)

    half = spread_pts * pt * 0.5
    mid = np.empty(n)
    for i in range(n):
        mid[i] = ((close[i] - half) + (close[i] + half)) * 0.5

    hold_active = False
    hold_is_buy = False
    hold_bar = -1
    hold_mid = np.nan
    last_entry = -1           # na
    s_at = np.nan
    s_bar = np.nan
    s_px = np.nan
    s_dir = 0.0
    s_id = 0.0
    s_atr = np.nan
    for i in range(n):
        ask = close[i] + half
        bid = close[i] - half
        atr_pts = atr[i] / pt
        if unit_atr:
            burst_thr = burst_atr * atr_pts
            entry_dist = entry_atr * atr_pts
            hold_fav = holdfav_atr * atr_pts
        else:
            burst_thr = burst_pts_in
            entry_dist = entry_pts_in
            hold_fav = holdfav_pts_in
        burst = (mid[i] - mid[i - 1]) / pt if i >= 1 else np.nan
        drift = (mid[i] - mid[i - drift_bars]) / pt if i >= drift_bars else np.nan
        burst_buy = burst >= burst_thr
        burst_sell = burst <= -burst_thr
        prior_buy = (not use_drift) or drift > 0
        prior_sell = (not use_drift) or drift < 0
        if any_combo:
            raw_buy = tz_buy[i] and ((not use_burst) or burst_buy or parent_side[i] == 1)
            raw_sell = tz_sell[i] and ((not use_burst) or burst_sell or parent_side[i] == -1)
        else:
            raw_buy = tz_buy[i] and burst_buy
            raw_sell = tz_sell[i] and burst_sell
        buy_cand = raw_buy and prior_buy
        sell_cand = raw_sell and prior_sell

        buy_px = np.nan
        sell_px = np.nan
        b_sig = False
        s_sig = False
        can_fire = (not one_per_bar) or last_entry < 0 or last_entry != i
        if buy_cand and can_fire:
            if hold_bars == 0:
                buy_px = ask + entry_dist * pt
                b_sig = True
                last_entry = i
            elif not hold_active:
                hold_active = True
                hold_is_buy = True
                hold_bar = i
                hold_mid = mid[i]
            elif hold_is_buy:
                elapsed = i - hold_bar
                move = (mid[i] - hold_mid) / pt
                if elapsed >= hold_bars and move >= hold_fav:
                    buy_px = ask + entry_dist * pt
                    b_sig = True
                    last_entry = i
                    hold_active = False
        if sell_cand and can_fire:
            if hold_bars == 0:
                sell_px = bid - entry_dist * pt
                s_sig = True
                last_entry = i
            elif not hold_active:
                hold_active = True
                hold_is_buy = False
                hold_bar = i
                hold_mid = mid[i]
            elif not hold_is_buy:
                elapsed = i - hold_bar
                move = (hold_mid - mid[i]) / pt
                if elapsed >= hold_bars and move >= hold_fav:
                    sell_px = bid - entry_dist * pt
                    s_sig = True
                    last_entry = i
                    hold_active = False
        if hold_active and ((hold_is_buy and not tz_buy[i]) or ((not hold_is_buy) and not tz_sell[i])):
            hold_active = False
            hold_bar = -1
            hold_mid = np.nan
        px = buy_px if b_sig else (sell_px if s_sig else np.nan)
        buy_sig[i] = b_sig
        sell_sig[i] = s_sig
        sig_px[i] = px
        # fgfArm
        if b_sig or s_sig:
            s_at = float(tclose[i])
            s_bar = float(i)
            if lv_entry:
                s_px = close[i] if np.isnan(px) else px
            else:
                s_px = close[i]
            s_dir = 1.0 if b_sig else -1.0
            s_id += 1.0
            s_atr = atr[i]
        a_at[i] = s_at
        a_bar[i] = s_bar
        a_px[i] = s_px
        a_dir[i] = s_dir
        a_id[i] = s_id
        a_atr[i] = s_atr
    return buy_sig, sell_sig, sig_px, a_at, a_bar, a_px, a_dir, a_id, a_atr


# ----------------------------------------------------------------------------
# request.security mapping
# ----------------------------------------------------------------------------
def _take(arr, idx):
    """arr[idx] with na where idx < 0 (float)."""
    out = np.asarray(arr, dtype=np.float64)[np.maximum(idx, 0)]
    out[idx < 0] = np.nan
    return out


def _map_off(src_tclose, dst_tclose):
    """lookahead_off: the last source bar with t_close <= the target bar's t_close."""
    return np.searchsorted(src_tclose, dst_tclose, side='right') - 1


def _map_on_prev(src_topen, dst_topen):
    """lookahead_on with expr[1]: the source bar containing the target bar's
    open (t_open <= target t_open < t_close), minus one."""
    k = np.searchsorted(src_topen, dst_topen, side='right') - 1
    return np.where(k >= 0, k - 1, -1)


_DIR = {}


def _dir_series(pair, tf, rsi_len, fast_len):
    key = (pair, _tf_name(tf), rsi_len, fast_len)
    if key not in _DIR:
        b = _bars(pair, tf)
        if b is None:
            _DIR[key] = None
        else:
            _DIR[key] = (b['t_open'], b['t_close'], _tdi_dir(b['close'], rsi_len, fast_len))
    return _DIR[key]


def _zone_dir(pair, tf, ctx_sec, fb, P):
    """fgfZoneDir(tf, ctxSec) on the filter series fb (float, NaN = na)."""
    ds = _dir_series(pair, tf, P['fgfRsiLen'], P['fgfFastLen'])
    if ds is None:
        return np.full(len(fb['t_close']), np.nan)
    to, tc, d = ds
    if P['fgfHtfClosed'] and tf_seconds(tf) > ctx_sec:
        return _take(d, _map_on_prev(to, fb['t_open']))           # dPrev
    return _take(d, _map_off(tc, fb['t_close']))                  # dNow


_FILTER = {}
_FILTER_KEYS = ('fgfLvMode', 'fgfSpreadPts', 'fgfEntryDistPts', 'fgfHoldBars', 'fgfHoldFavPts', 'fgfOnePerBar',
                'fgfDistUnit', 'fgfBurstAtr', 'fgfEntryDistAtr', 'fgfHoldFavAtr', 'fgfBurstPts', 'fgfUseBurst',
                'fgfAnyCombo', 'fgfDriftBars', 'fgfUseDrift', 'fgfUseZones', 'fgfParentTf', 'fgfRsiLen',
                'fgfFastLen', 'fgfMinAligned', 'fgfFlatParent', 'fgfIgnoreNa', 'fgfHtfClosed',
                'fgfUseZ1', 'fgfZTf1', 'fgfUseZ2', 'fgfZTf2', 'fgfUseZ3', 'fgfZTf3',
                'fgfUseZ4', 'fgfZTf4', 'fgfUseZ5', 'fgfZTf5', 'fgfUseZ6', 'fgfZTf6')


def _filter_series(pair, ftf, P):
    """fgfRead() on every bar of the filter timeframe (all history). Returns a
    dict of float arrays (NaN = na), or None when the filter TF has no data."""
    key = (pair, _tf_name(ftf)) + tuple(P[k] for k in _FILTER_KEYS)
    if key in _FILTER:
        return _FILTER[key]
    fb = _bars(pair, ftf)
    if fb is None:
        _FILTER[key] = None
        return None
    ctx_sec = tf_seconds(ftf)
    n = len(fb['t_close'])

    def ctx_tf(tf):          # "" inside the nested request = the filter (context) timeframe
        return ftf if str(tf).strip() == '' else tf

    # parent: request.security(parentTf, fgfTdiDir(), lookahead_off)
    ds = _dir_series(pair, ctx_tf(P['fgfParentTf']), P['fgfRsiLen'], P['fgfFastLen'])
    parent = np.full(n, np.nan) if ds is None else _take(ds[2], _map_off(ds[1], fb['t_close']))
    parent_side = np.where(parent > 0, 1, np.where(parent < 0, -1, 0)).astype(np.int64)

    active = np.zeros(n, np.int64)
    aligned = np.zeros(n, np.int64)
    for z in range(1, 7):
        use = bool(P[f'fgfUseZ{z}'])
        if not use:          # fgfZoneOn(false, .) = false, fgfAlign = 0
            continue
        zd = _zone_dir(pair, ctx_tf(P[f'fgfZTf{z}']), ctx_sec, fb, P)
        on = np.ones(n, bool) if not P['fgfIgnoreNa'] else ~np.isnan(zd)
        active += on
        aligned += (on & (parent_side != 0) & (zd == parent_side))
    required = np.minimum(P['fgfMinAligned'], active)
    flat_ok = P['fgfFlatParent'] & (parent_side == 0)
    zone_ready = (active == 0) | (aligned >= required)
    if P['fgfUseZones']:
        tz_buy = ((parent_side == 1) | flat_ok) & zone_ready
        tz_sell = ((parent_side == -1) | flat_ok) & zone_ready
    else:
        tz_buy = np.ones(n, bool)
        tz_sell = np.ones(n, bool)

    atr = _atr(fb['high'], fb['low'], fb['close'], 14)
    bs, ss, spx, a_at, a_bar, a_px, a_dir, a_id, a_atr = _signal_arm(
        fb['close'], fb['t_close'], atr, tz_buy, tz_sell, parent_side,
        MINTICK, float(P['fgfSpreadPts']), P['fgfDistUnit'] == 'ATR', float(P['fgfBurstAtr']),
        float(P['fgfEntryDistAtr']), float(P['fgfHoldFavAtr']), float(P['fgfBurstPts']),
        float(P['fgfEntryDistPts']), float(P['fgfHoldFavPts']),
        bool(P['fgfUseBurst']), bool(P['fgfAnyCombo']), int(P['fgfDriftBars']), bool(P['fgfUseDrift']),
        int(P['fgfHoldBars']), bool(P['fgfOnePerBar']), P['fgfLvMode'] == 'Entry price')
    out = dict(
        t_open=fb['t_open'], t_close=fb['t_close'],
        at=a_at, bar=a_bar, px=a_px, dir=a_dir, id=a_id, atr=a_atr,
        par=parent_side.astype(np.float64), al=aligned.astype(np.float64), ac=active.astype(np.float64),
        buy=bs, sell=ss, sigpx=spx,
    )
    _FILTER[key] = out
    return out


def _shift(x):
    """x[1] along the computed chart range (na before the first element)."""
    y = np.empty(np.shape(x), dtype=np.float64)
    if y.size:
        y[0] = np.nan
        y[1:] = x[:-1]
    return y


# ----------------------------------------------------------------------------
# Public interface
# ----------------------------------------------------------------------------
def fgf_permissions(pair, chart_tf, start, end, params=None):
    P = _params(params)
    cb = _bars(pair, chart_tf, ('open', 'close', 't_open', 't_close'))
    if cb is None:
        raise ValueError(f'chart timeframe {chart_tf!r} has no data')
    ctc = cb['t_close']
    w0 = int(np.searchsorted(ctc, start, side='left'))
    w1 = int(np.searchsorted(ctc, end, side='right'))          # exclusive
    # chart-level values reach back two bars (x[1] of values that use y[1]):
    # compute from three bars before the window (or the first bar of the data)
    lo = max(w0 - 3, 0)
    sl = slice(lo, w1)
    t_open = cb['t_open'][sl].astype(np.float64)
    t_close = ctc[sl].astype(np.float64)
    c_open = cb['open'][sl]
    c_close = cb['close'][sl]
    m = w1 - lo

    ftf = chart_tf if str(P['fgfTf']).strip() == '' else P['fgfTf']
    F = _filter_series(pair, ftf, P)

    nanv = np.full(m, np.nan)
    if F is None or m == 0:
        fp = {k: nanv for k in ('at', 'bar', 'px', 'dir', 'id', 'atr', 'par', 'al', 'ac', 'close', 'idx')}
        fq = dict(fp)
    else:
        j = _map_off(F['t_close'], ctc[sl])
        jq = np.where(j >= 1, j - 1, -1)
        fp = {k: _take(F[k], j) for k in ('at', 'bar', 'px', 'dir', 'id', 'atr', 'par', 'al', 'ac')}
        fq = {k: _take(F[k], jq) for k in ('at', 'bar', 'px', 'dir', 'id', 'atr', 'par', 'al', 'ac')}
        fp['close'] = _take(F['t_close'], j)         # nz(time_close, time)
        fq['close'] = _take(F['t_close'], jq)        # nz(time_close[1], time[1])
        fp['idx'] = np.where(j >= 0, j, np.nan).astype(np.float64)

    check = P['fgfCheck']
    at_open = check == 'Candle open'          # history: every bar is confirmed (fgfLiveBar = false)
    clock_c = t_close                         # nz(time_close, time)
    clock = t_open if at_open else clock_c

    sel_c1 = clock_c >= fp['close']                      # fgfSelC == 1 (na -> 2)
    if at_open:
        sel = np.where(fp['close'] <= t_open, 1, np.where(fq['close'] <= t_open, 2, 0))
    else:
        sel = np.where(sel_c1, 1, 2)

    def pick_c(k):
        return np.where(sel_c1, fp[k], fq[k])

    C = {k: pick_c(k) for k in ('at', 'bar', 'px', 'dir', 'id', 'atr', 'par', 'al', 'ac')}
    fp_idx = fp['idx']
    c_idx = np.where(sel_c1, np.where(clock_c == fp['close'], fp_idx, fp_idx + 1),
                     np.where(clock_c == fq['close'], fp_idx - 1, fp_idx))
    c_k = np.where(sel_c1, fp_idx, fp_idx - 1)
    c_kclose = np.where(sel_c1, fp['close'], fq['close'])

    def pick(k):
        return np.where(sel == 1, fp[k], np.where(sel == 2, fq[k], _shift(C[k])))

    sig_at = pick('at')
    sig_bar = pick('bar')
    level = pick('px')
    sig_dir = np.nan_to_num(pick('dir'), nan=0.0)
    sig_atr = pick('atr')
    sig_id = np.nan_to_num(pick('id'), nan=0.0)
    par = pick('par')
    al = pick('al')
    ac = pick('ac')
    if not at_open:
        idx = c_idx
    else:
        idx = np.where(sel == 1, np.where(t_open == fp['close'], fp_idx, fp_idx + 1),
                       np.where(sel == 2, np.where(t_open == fq['close'], fp_idx - 1, fp_idx),
                                np.where(t_open == _shift(c_kclose), _shift(c_k), _shift(c_k) + 1)))

    value = c_open if check == 'Candle open' else c_close     # 'Candle close' on a confirmed bar: close

    armed = ~np.isnan(sig_at) & (clock >= sig_at)
    last = P['fgfLast']
    if last == 'Minutes':
        f_end = np.where(armed, sig_at + P['fgfMinutes'] * 60, np.nan)    # seconds (Pine: ms)
        is_open = armed & (clock < f_end)
    elif last == 'Candles':
        f_end_bar = np.where(armed, sig_bar + P['fgfBars'], np.nan)
        is_open = armed & (idx < f_end_bar)
    else:
        is_open = armed.copy()

    on_sig_bar = armed & (idx == sig_bar)
    at_buy_lv = on_sig_bar & (sig_dir > 0) & (value >= level)
    at_sell_lv = on_sig_bar & (sig_dir < 0) & (value <= level)

    mt = MINTICK
    band = P['fgfBandAtr'] * np.nan_to_num(sig_atr, nan=0.0)
    has_band = band > 0
    with np.errstate(invalid='ignore'):
        up_lv = np.where(has_band, np.ceil((level + band) / mt - 1e-9) * mt, level)
        dn_lv = np.where(has_band, np.floor((level - band) / mt + 1e-9) * mt, level)
        in_up = np.where(has_band, value > up_lv + mt / 2, (value > level) | at_buy_lv)
        in_dn = np.where(has_band, value < dn_lv - mt / 2, (value < level) | at_sell_lv)
    sig_ok = armed & np.where(sig_dir > 0, in_up, np.where(sig_dir < 0, in_dn, False))
    up_now = in_up & (P['fgfAgainst'] | (sig_dir > 0))
    dn_now = in_dn & (P['fgfAgainst'] | (sig_dir < 0))
    if P['fgfOn']:
        buy_ok = is_open & bool(P['fgfAllowBuy']) & up_now
        sell_ok = is_open & bool(P['fgfAllowSell']) & dn_now
    else:
        buy_ok = np.ones(m, bool)
        sell_ok = np.ones(m, bool)
    new_sig = sig_id > _shift(sig_id)                    # na on the first bar of the data -> false
    zone = np.where(not P['fgfOn'], 2, np.where(buy_ok, 1, np.where(sell_ok, -1, 0)))
    ended = armed & ~is_open
    is_first = (np.arange(lo, w1) == 0)
    expired = bool(P['fgfOn']) & ended & ~(_shift(ended) == 1) & ~is_first

    k0 = w0 - lo
    s = slice(k0, m)
    df = pd.DataFrame({
        't_close': ctc[w0:w1],
        'buyOk': buy_ok[s].astype(bool),
        'sellOk': sell_ok[s].astype(bool),
        'level': level[s],
        'upLv': up_lv[s],
        'dnLv': dn_lv[s],
        'open_': is_open[s].astype(bool),
        'sigDir': sig_dir[s].astype(np.int64),
        'newSig': new_sig[s].astype(bool),
        'band': band[s],
        # extras (diagnostics)
        'zone': zone[s].astype(np.int64),
        'armed': armed[s].astype(bool),
        'sigOk': sig_ok[s].astype(bool),
        'expired': expired[s].astype(bool),
        'sigId': sig_id[s].astype(np.int64),
        'sigAt': sig_at[s],
        'sigBar': sig_bar[s],
        'idx': idx[s],
        'value': value[s],
        'sigAtr': sig_atr[s],
        'par': par[s],
        'al': al[s],
        'ac': ac[s],
    }, index=pd.RangeIndex(w0, w1))
    return df


def filter_signals(pair, filter_tf="60", params=None):
    """The FlashGold signals on the filter timeframe's own bars (diagnostics)."""
    P = _params(params)
    F = _filter_series(pair, filter_tf, P)
    if F is None:
        return None
    return pd.DataFrame({k: F[k] for k in ('t_open', 't_close', 'buy', 'sell', 'sigpx', 'at', 'bar', 'px',
                                           'dir', 'id', 'atr', 'par', 'al', 'ac')})


# ----------------------------------------------------------------------------
# Self-checks
# ----------------------------------------------------------------------------
def _summary(df):
    return (f"rows={len(df)} newSig={int(df.newSig.sum())} (buy {int((df.newSig & (df.sigDir > 0)).sum())}, "
            f"sell {int((df.newSig & (df.sigDir < 0)).sum())}) open={int(df.open_.sum())} "
            f"buyOk={int(df.buyOk.sum())} sellOk={int(df.sellOk.sum())} "
            f"neither={int((~df.buyOk & ~df.sellOk).sum())} level_na={int(df.level.isna().sum())}")


def _selfcheck():
    os.makedirs(os.path.join(W, 'out'), exist_ok=True)
    runs = [('BTC', '60', 1735689600, 1740787200), ('BTC', '5', 1735689600, 1736899200)]
    for pair, tf, a, b in runs:
        t0 = _time.time()
        df = fgf_permissions(pair, tf, a, b)
        dt = _time.time() - t0
        print(f'{pair} {tf} {a}->{b}: {_summary(df)}  time {dt:.2f}s', flush=True)
        if tf == '60':
            p = os.path.join(W, 'out', f'{_MODNAME}_{pair}_{tf}.parquet')
            df.to_parquet(p)
            print('saved', p)
    # 2-year 1m window
    a, b = 1672531200, 1735689600     # 2023-01-01 .. 2025-01-01
    t0 = _time.time()
    df = fgf_permissions('BTC', '1', a, b)
    dt = _time.time() - t0
    print(f'BTC 1 {a}->{b}: {_summary(df)}  time {dt:.2f}s', flush=True)


_MODNAME = os.path.splitext(os.path.basename(__file__))[0]     # fgf_b, or fgf (the canonical copy)

if __name__ == '__main__':
    # run through the importable module so numba's on-disk cache (keyed on the
    # module) is shared with callers that `import` it
    import importlib
    sys.path.insert(0, W)
    _m = importlib.import_module(_MODNAME)
    _m._selfcheck()
