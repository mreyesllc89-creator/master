"""AMVI Full MTF Strategy + FGF [Update 1] (key `amvi`): Python replica, CANONICAL module (stage 3).

Ground truth: /home/user/master/AMVI_Full_MTF_Strategy_FGF.pine at HEAD (Lnnn = its lines) and, for
dirSource='orig', /home/user/master/AMVI_Full_MTF_Strategy.pine (Onnn). Brief: SPEC_amvi.md.
Interpretations and limits: amvi_notes.md (stage 3), amvi_b_notes.md / amvi_a_notes.md (the two builds),
reconcile_amvi.md (how the two builds were compared and what was fixed).

This file is implementation B (amvi_b.py) after the stage-3 reconciliation, plus the Bar Magnifier path
'mag': the open trade's bracket (stop, limit, trailing stop; this script has no other price order) walks
the 1-minute sub-bars of the chart bar in time order, each sub-bar with its own open test and its own
rule-4 path, the trailing state carried over, the levels those of the chart bar; market entries,
reversals, the close_all orders and the bar-close run stay on the chart bars. Chart "1": mag == tv.
With path 'tv' the trades are bit-for-bit those of amvi_b.py.

    prepare(pair, chart_tf, params=None) -> P       signals: AMVI per timeframe, the 12 requests, crosses,
                                                    trigger, direction (the filter's zones or the original's bias)
    simulate(P, x=None, full=False, sub=None) -> R  orders and exits (numba kernel), path 'tv' | 'mag'
                                                    (sub: a sub-bar table to use instead of the 1-minute data)
    trades(P, R) -> DataFrame
    summary(P, R) -> dict
    run(pair, chart_tf, params=None) -> (trades, summary)
    sub_bars / get_sub / fake_sub_bars              the 1-minute sub-bars of the window ('mag')

What the script is (history: one run per bar at its close, market orders fill at the next open):
  trigger   = one enabled timeframe's AMVI crosses above highVolThreshold while >= minConfluence are above it
  direction = the FlashGold Direction Filter (fgf.py, never reimplemented): buyOk and not sellOk -> up,
              sellOk and not buyOk -> down, else no trade. With fgfOn False nothing trades (L777-778).
              dirSource='orig' (replica control) = the unfused original's EMA / candle / Donchian bias.
  inv       = the script's own input amviTradeDir == "Inverted" (L108, L779): the signal sides are swapped
              AFTER the filter (L780-781); the bracket is not "mirrored" by a formula, it is recomputed for
              the real side from the same reference price and the same ATR distances (L814-826).
  exits     = strategy.exit bracket (stop / limit at absolute prices + trail ticks), sent with the entry
              from the SIGNAL close and re-sent on every bar from position_avg_price; close_all on the
              volatility collapse and on the time stop; an opposite trigger reverses.
Seconds timeframes (1S .. 45S) have no data: their values are na on every bar = switched off.
"""
import math
import os
import sys
from collections import OrderedDict

import numpy as np
import pandas as pd
from numba import njit

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import fgf  # noqa: E402  (the verified direction filter; also bars, ta.atr, timeframe helpers)

MINTICK = 0.01
POINTVALUE = 1.0
INITIAL_CAPITAL = 10000.0          # strategy(initial_capital=10000)
QTY_FRAC = 0.10                    # default_qty_type=percent_of_equity, default_qty_value=10
WINDOWS = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}

KINDS = ['', 'sl', 'tp', 'trail', 'reverse', 'vol', 'time', 'end']
K_SL, K_TP, K_TRAIL, K_REV, K_VOL, K_TIME, K_END = 1, 2, 3, 4, 5, 6, 7

# the seven requested timeframes that have data, in the Pine's order (L740-741), and their toggles
TFS = ('1', '5', '15', '30', '60', '240', 'D')
EN_KEYS = ('en1', 'en5', 'en15', 'en30', 'en60', 'en240', 'enD')
SEC_KEYS = ('en1s', 'en5s', 'en15s', 'en30s', 'en45s')          # "1S" "5S" "15S" "30S" "45S": no data

# per fill, per unit: (fixed $, fraction of the fill value, slippage in price)
COSTS = {
    'tv': {'XAU': (0.0, 0.0004, MINTICK), 'BTC': (0.0, 0.0004, MINTICK)},     # commission 0.04 %, slippage 1 tick
    'ours': {'XAU': (0.15, 0.0, 0.0), 'BTC': (0.10, 0.0002, 0.0)},
    'stress': {'XAU': (0.25 + 0.01, 0.0, 0.0), 'BTC': (0.10 + 0.01, 0.00035, 0.0)},
}

DEFAULTS = dict(
    # --- SIGNAL inputs (prepare) ---
    fastATRPeriod=14, slowATRPeriod=50, stdDevPeriod=20, candleRangePeriod=10, normalizationPeriod=200,
    noRepaint=True,
    aatrWeight=0.35, vrWeight=0.25, nsdWeight=0.25, acrWeight=0.15,
    highVolThreshold=70.0, minConfluence=3,
    en1s=True, en5s=True, en15s=True, en30s=True, en45s=True,
    en1=True, en5=True, en15=True, en30=True, en60=True, en240=True, enD=True,
    useDateRange=False, startTime=1577836800, endTime=4102358400,       # epoch SECONDS (UTC)
    dirSource='fgf',                                                    # replica: 'fgf' | 'orig'
    dirMode="Trend (EMA)", emaLen=50, dcLen=20,                         # original only (O55-57)
    ltfRule='first',                                                    # replica: 'first' | 'last' (A2)
    start=None, end=None,                                               # window override (t_close, epoch s)
    # --- ORDER / EXIT inputs (simulate) ---
    amviTradeDir="Follow the filter", inv=False,
    exitAtrLen=14, slMult=1.5, tpMult=3.0, useTrail=False, trailActMul=1.5, trailOffMul=1.0,
    useVolExit=True, lowVolThreshold=30.0, maxBars=0,
    tradeDir="Both", allowReverse=True,                                 # original only (O53, O58)
    revClose='void',                                                    # replica: 'void' | 'closes' (A11)
    path='tv', cost='tv',
)
_FGF_KEYS = tuple(fgf.DEFAULTS.keys())
DEFAULTS.update(fgf.DEFAULTS)                                           # fgfOn = True, fgfTf = "60", ...

SIM_KEYS = frozenset(('amviTradeDir', 'inv', 'exitAtrLen', 'slMult', 'tpMult', 'useTrail', 'trailActMul',
                      'trailOffMul', 'useVolExit', 'lowVolThreshold', 'maxBars', 'tradeDir', 'allowReverse',
                      'revClose', 'path', 'cost'))
PREP_KEYS = frozenset(k for k in DEFAULTS if k not in SIM_KEYS)
# drawing-only inputs: accepted, ignored
IGNORED_KEYS = frozenset(('showOverlay', 'showLabels', 'showLevels', 'showL1s', 'showL5s', 'showL15s', 'showL30s',
                          'showL45s', 'showL1', 'showL5', 'showL15', 'showL30', 'showL60', 'showL240', 'showLD')
                         ) | frozenset(fgf._DISPLAY_KEYS)

_OPTIONS = {
    'amviTradeDir': ("Follow the filter", "Inverted"),
    'dirSource': ('fgf', 'orig'),
    'dirMode': ("Trend (EMA)", "Candle", "Breakout (Donchian)"),
    'tradeDir': ("Both", "Long Only", "Short Only"),
    'ltfRule': ('first', 'last'),
    'revClose': ('void', 'closes'),
    'path': ('tv', 'mag'),
    'cost': tuple(COSTS),
}
_INT_MIN1 = ('fastATRPeriod', 'slowATRPeriod', 'stdDevPeriod', 'candleRangePeriod', 'normalizationPeriod',
             'exitAtrLen', 'emaLen', 'dcLen')
_WEIGHTS = ('aatrWeight', 'vrWeight', 'nsdWeight', 'acrWeight')
_NONNEG = ('slMult', 'tpMult', 'trailActMul', 'trailOffMul')
_BOOLS = ('noRepaint', 'useDateRange', 'useTrail', 'useVolExit', 'allowReverse', 'inv') + EN_KEYS + SEC_KEYS


# ---------------------------------------------------------------------------------------------------
# parameters
# ---------------------------------------------------------------------------------------------------
def _as_int(k, v):
    if isinstance(v, (bool, np.bool_)):
        raise ValueError('%s=%r must be an integer' % (k, v))
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)) and float(v).is_integer():
        return int(v)
    raise ValueError('%s=%r must be an integer' % (k, v))


def _merge(base, given):
    """base (a resolved dict) overridden by the given keys; 'inv' and 'amviTradeDir' are one input."""
    Q = dict(base)
    g = {}
    for k, v in (given or {}).items():
        if k in IGNORED_KEYS:
            continue
        if k not in DEFAULTS:
            raise ValueError('unknown param %r' % (k,))
        g[k] = v
    has_inv, has_td = 'inv' in g, 'amviTradeDir' in g
    if has_td and g['amviTradeDir'] not in _OPTIONS['amviTradeDir']:
        raise ValueError('amviTradeDir=%r is not one of %r' % (g['amviTradeDir'], _OPTIONS['amviTradeDir']))
    if has_inv and has_td and bool(g['inv']) != (g['amviTradeDir'] == 'Inverted'):
        raise ValueError("inv=%r and amviTradeDir=%r disagree" % (g['inv'], g['amviTradeDir']))
    Q.update(g)
    if has_inv:
        Q['inv'] = bool(g['inv'])
    elif has_td:
        Q['inv'] = g['amviTradeDir'] == 'Inverted'
    Q['amviTradeDir'] = 'Inverted' if Q['inv'] else 'Follow the filter'
    return Q


def _check(Q):
    for k, opts in _OPTIONS.items():
        if Q[k] not in opts:
            raise ValueError('%s=%r is not one of %r' % (k, Q[k], opts))
    for k in _INT_MIN1:
        Q[k] = _as_int(k, Q[k])
        if Q[k] < 1:
            raise ValueError('%s=%r is below the Pine minval 1' % (k, Q[k]))
    for k in _WEIGHTS:
        Q[k] = float(Q[k])
        if not (0.0 <= Q[k] <= 1.0):
            raise ValueError('%s=%r is outside [0, 1]' % (k, Q[k]))
    Q['minConfluence'] = _as_int('minConfluence', Q['minConfluence'])
    if not (1 <= Q['minConfluence'] <= 12):
        raise ValueError('minConfluence=%r is outside 1..12' % (Q['minConfluence'],))
    for k in _NONNEG:
        Q[k] = float(Q[k])
        if not (Q[k] >= 0.0):
            raise ValueError('%s=%r is below the Pine minval 0' % (k, Q[k]))
    Q['maxBars'] = _as_int('maxBars', Q['maxBars'])
    if Q['maxBars'] < 0:
        raise ValueError('maxBars=%r is below the Pine minval 0' % (Q['maxBars'],))
    for k in ('highVolThreshold', 'lowVolThreshold'):
        Q[k] = float(Q[k])
        if math.isnan(Q[k]):
            raise ValueError('%s is nan' % k)
    for k in ('startTime', 'endTime'):
        Q[k] = _as_int(k, Q[k])
    for k in _BOOLS:
        if not isinstance(Q[k], (bool, np.bool_)) and Q[k] not in (0, 1):
            raise ValueError('%s=%r must be a bool' % (k, Q[k]))
        Q[k] = bool(Q[k])
    if Q['dirSource'] == 'fgf' and (Q['tradeDir'] != 'Both' or not Q['allowReverse']):
        raise ValueError("tradeDir / allowReverse are inputs of the unfused original only: with dirSource='fgf' "
                         "they must stay 'Both' / True (the fused file has no such inputs)")
    fgf._params({k: Q[k] for k in _FGF_KEYS})          # the filter's own validation
    return Q


def _fgf_params(Q):
    return {k: Q[k] for k in _FGF_KEYS}


# ---------------------------------------------------------------------------------------------------
# series (numba): the built-ins calc_amvi() uses, on ONE timeframe's own bars
# ---------------------------------------------------------------------------------------------------
@njit(cache=True)
def _sma(x, length):
    """ta.sma: (sum of the window, oldest first) / length; na before row length-1 (and while the window
    holds an na: the sum carries it)."""
    n = x.shape[0]
    out = np.full(n, np.nan)
    for i in range(length - 1, n):
        s = 0.0
        for k in range(i - length + 1, i + 1):
            s += x[k]
        out[i] = s / length
    return out


@njit(cache=True)
def _stdev(x, length):
    """ta.stdev (population): m = (sum of the window, oldest first) / length;
    sqrt((sum of (x - m)^2, oldest first) / length); na before row length-1."""
    n = x.shape[0]
    out = np.full(n, np.nan)
    for i in range(length - 1, n):
        s = 0.0
        for k in range(i - length + 1, i + 1):
            s += x[k]
        m = s / length
        q = 0.0
        for k in range(i - length + 1, i + 1):
            d = x[k] - m
            q += d * d
        out[i] = math.sqrt(q / length)
    return out


@njit(cache=True)
def _roll_ext(x, length, want_max):
    """ta.highest / ta.lowest over x[i-length+1 .. i]: na before row length-1 and while the window holds an
    na (A4). Monotonic queue: exact."""
    n = x.shape[0]
    out = np.full(n, np.nan)
    dq = np.empty(n, np.int64)
    head = 0
    tail = 0
    last_na = -1
    for i in range(n):
        v = x[i]
        if v != v:
            last_na = i
            head = 0
            tail = 0
            continue
        if want_max:
            while tail > head and x[dq[tail - 1]] <= v:
                tail -= 1
        else:
            while tail > head and x[dq[tail - 1]] >= v:
                tail -= 1
        dq[tail] = i
        tail += 1
        lo = i - length + 1
        while dq[head] < lo:
            head += 1
        if lo >= 0 and lo > last_na:
            out[i] = x[dq[head]]
    return out


def _normalize(x, length):
    """normalize(val, len) (L719-721): lo = ta.lowest, hi = ta.highest (the current bar included);
    hi <= lo ? 0.0 : (val - lo) / (hi - lo); a comparison with na is false, so na lo / hi give na."""
    lo = _roll_ext(x, length, False)
    hi = _roll_ext(x, length, True)
    with np.errstate(invalid='ignore', divide='ignore'):
        return np.where(hi <= lo, 0.0, (x - lo) / (hi - lo))


@njit(cache=True)
def _ema(x, length):
    """ta.ema: seeded with the first value; alpha = 2 / (length + 1)."""
    n = x.shape[0]
    out = np.empty(n)
    a = 2.0 / (length + 1)
    for i in range(n):
        if i == 0:
            out[i] = x[i]
        else:
            out[i] = a * x[i] + (1.0 - a) * out[i - 1]
    return out


# ---------------------------------------------------------------------------------------------------
# caches (layered: parts -> v_T on the chart -> counts -> direction)
# ---------------------------------------------------------------------------------------------------
_PARTS = OrderedDict()
_PARTS_CAP = 700 * 2 ** 20
_VT = OrderedDict()
_VT_CAP = 4
_CNT = OrderedDict()
_CNT_CAP = 6
_DIR = OrderedDict()
_DIR_CAP = 12
_ATRC = OrderedDict()
_ATRC_CAP = 8


def clear_caches():
    for c in (_PARTS, _VT, _CNT, _DIR, _ATRC):
        c.clear()


def _put(cache, key, val, cap):
    cache[key] = val
    cache.move_to_end(key)
    while len(cache) > cap:
        cache.popitem(last=False)
    return val


def _get(cache, key):
    v = cache.get(key)
    if v is not None:
        cache.move_to_end(key)
    return v


def _bars(pair, tf):
    b = fgf._bars(pair, tf)
    if b is None:
        raise ValueError('timeframe %r has no data' % (tf,))
    return b


def amvi_parts(pair, T, per):
    """The four normalised parts of calc_amvi() (L723-729) on the bars of data/<pair>_<T>.parquet, from
    row 0: (nATR, nVR, nSD, nCR). per = (fastATRPeriod, slowATRPeriod, stdDevPeriod, candleRangePeriod,
    normalizationPeriod)."""
    key = (pair, T) + tuple(per)
    hit = _get(_PARTS, key)
    if hit is not None:
        return hit
    fast, slow, sdl, crl, nml = per
    b = _bars(pair, T)
    h, l, c = b['high'], b['low'], b['close']
    f_atr = fgf._atr(h, l, c, fast)
    s_atr = fgf._atr(h, l, c, slow)
    with np.errstate(invalid='ignore', divide='ignore'):
        vr = np.minimum(2.0, np.maximum(0.5, f_atr / s_atr))        # na propagates
        vr = np.where(s_atr > 0, vr, 1.0)                            # sATR na or 0 -> 1.0
    n_vr = (vr - 0.5) / 1.5
    del vr, s_atr
    n_atr = _normalize(f_atr, nml)
    del f_atr
    sd = _stdev(c, sdl)
    n_sd = _normalize(sd, nml)
    del sd
    cr = _sma(h - l, crl)
    n_cr = _normalize(cr, nml)
    del cr
    out = (n_atr, n_vr, n_sd, n_cr)
    _PARTS[key] = out
    tot = sum(a.nbytes for v in _PARTS.values() for a in v)
    while tot > _PARTS_CAP and len(_PARTS) > 1:
        _, v0 = _PARTS.popitem(last=False)
        tot -= sum(a.nbytes for a in v0)
    return out


def amvi_series(pair, T, per, wts):
    """calc_amvi() on every bar of T (diagnostics / checks)."""
    n_atr, n_vr, n_sd, n_cr = amvi_parts(pair, T, per)
    aw, vw, sw, cw = wts
    return (aw * n_atr + vw * n_vr + sw * n_sd + cw * n_cr) * 100.0


def request_index(pair, chart_tf, T, r0, r1, noRepaint, ltfRule):
    """Row of T's file that get_mtf(T) reads on chart file rows r0 .. r1-1 (L733-736), -1 = na.
    noRepaint (expr[1], lookahead on): the last T bar closed by the chart bar's OPEN, for higher, equal and
    lower timeframes; ltfRule 'last' (control, T lower than the chart only): [1] of the LAST intrabar of
    the chart bar. noRepaint off (expr[0], lookahead off): the last T bar closed by the chart bar's CLOSE."""
    cb = _bars(pair, chart_tf)
    tb = _bars(pair, T)
    if noRepaint:
        if ltfRule == 'last' and fgf.tf_seconds(T) < fgf.tf_seconds(chart_tf):
            return np.searchsorted(tb['t_close'], cb['t_close'][r0:r1], side='right') - 2
        return np.searchsorted(tb['t_close'], cb['t_open'][r0:r1], side='right') - 1
    return np.searchsorted(tb['t_close'], cb['t_close'][r0:r1], side='right') - 1


def _v_on_chart(pair, chart_tf, w0, w1, per, wts, noRepaint, ltfRule, T):
    """v_T on chart file rows w0-1 .. w1-1 (n + 1 values; the first is na when w0 == 0)."""
    key = (pair, chart_tf, w0, w1, tuple(per), tuple(wts), bool(noRepaint), ltfRule)
    d = _get(_VT, key)
    if d is None:
        d = _put(_VT, key, {}, _VT_CAP)
    v = d.get(T)
    if v is None:
        r0 = max(w0 - 1, 0)
        k = request_index(pair, chart_tf, T, r0, w1, noRepaint, ltfRule)
        n_atr, n_vr, n_sd, n_cr = amvi_parts(pair, T, per)
        aw, vw, sw, cw = wts
        kk = np.maximum(k, 0)
        v = (aw * n_atr[kk] + vw * n_vr[kk] + sw * n_sd[kk] + cw * n_cr[kk]) * 100.0
        v[k < 0] = np.nan
        if w0 == 0:
            v = np.concatenate([[np.nan], v])
        d[T] = v
    return v


def _counts(pair, chart_tf, w0, w1, per, wts, noRepaint, ltfRule, H, enabled):
    """hotCount, enCount, avgAmvi (n + 1 values: rows w0-1 .. w1-1) and anyCross (n values: window rows),
    L744-747, L760-769. enabled: the seven toggles en1 .. enD (the seconds timeframes are na)."""
    key = (pair, chart_tf, w0, w1, tuple(per), tuple(wts), bool(noRepaint), ltfRule, float(H), tuple(enabled))
    hit = _get(_CNT, key)
    if hit is not None:
        return hit
    m = w1 - w0 + 1
    hot = np.zeros(m, np.int64)
    en = np.zeros(m, np.int64)
    ssum = np.zeros(m)
    anyx = np.zeros(m - 1, np.bool_)
    na_in_window = 0
    for T, on in zip(TFS, enabled):
        if not on:
            continue                                   # on ? v : na
        v = _v_on_chart(pair, chart_tf, w0, w1, per, wts, noRepaint, ltfRule, T)
        ok = ~np.isnan(v)
        with np.errstate(invalid='ignore'):
            gt = v > H                                 # na compares false
            le = v <= H
        hot += gt                                      # hot(v): not na(v) and v > H
        en += ok                                       # cnt(v)
        ssum = ssum + np.where(ok, v, 0.0)             # val(v), in the Pine's order
        anyx |= gt[1:] & le[:-1]                       # ta.crossover(v, H)
        na_in_window += int((~ok[1:]).sum())
    with np.errstate(invalid='ignore', divide='ignore'):
        avg = np.where(en > 0, ssum / np.where(en > 0, en, 1), np.nan)
    out = dict(hot=hot, en=en, avg=avg, anyx=anyx, na_in_window=na_in_window)
    return _put(_CNT, key, out, _CNT_CAP)


def _direction(pair, chart_tf, start, end, w0, w1, Q):
    """Normal-frame direction per window bar: (dirUp, dirDn)."""
    n = w1 - w0
    if Q['dirSource'] == 'fgf':
        if not Q['fgfOn']:
            # amviDirUp / amviDirDn start with "fgfOn and" (L777-778): no direction, the filter is not called
            return np.zeros(n, np.bool_), np.zeros(n, np.bool_)
        fp = _fgf_params(Q)
        key = ('fgf', pair, chart_tf, start, end) + tuple((k, str(fp[k])) for k in _FGF_KEYS)
        hit = _get(_DIR, key)
        if hit is not None:
            return hit
        F = fgf.fgf_permissions(pair, chart_tf, start, end, fp)
        if len(F) != n or (n and F.index[0] != w0):
            raise RuntimeError('filter rows do not match the window')
        buy = F['buyOk'].to_numpy(np.bool_)
        sell = F['sellOk'].to_numpy(np.bool_)
        if (buy & sell).any():
            raise AssertionError('buyOk and sellOk both true with the filter on')
        up = np.ascontiguousarray(buy & ~sell)         # amviDirUp = fgfOn and fgfBuyOk and not fgfSellOk
        dn = np.ascontiguousarray(sell & ~buy)         # amviDirDn = fgfOn and fgfSellOk and not fgfBuyOk
        return _put(_DIR, key, (up, dn), _DIR_CAP)
    mode = Q['dirMode']
    key = ('orig', pair, chart_tf, w0, w1, mode, Q['emaLen'] if mode == 'Trend (EMA)' else 0,
           Q['dcLen'] if mode == 'Breakout (Donchian)' else 0)
    hit = _get(_DIR, key)
    if hit is not None:
        return hit
    b = _bars(pair, chart_tf)
    sl = slice(w0, w1)
    c = b['close'][sl]
    with np.errstate(invalid='ignore'):
        if mode == 'Trend (EMA)':                      # O144, O148, O152
            ema = _ema(b['close'], Q['emaLen'])[sl]
            up, dn = c > ema, c < ema
        elif mode == 'Candle':                         # O149, O153
            o = b['open'][sl]
            up, dn = c > o, c < o
        else:                                          # O145-146, O150, O154: highest / lowest of the dcLen bars before
            L = Q['dcLen']
            hi = _roll_ext(b['high'], L, True)
            lo = _roll_ext(b['low'], L, False)
            dchi = np.full(len(hi), np.nan)
            dclo = np.full(len(lo), np.nan)
            dchi[1:] = hi[:-1]
            dclo[1:] = lo[:-1]
            up, dn = c > dchi[sl], c < dclo[sl]
    return _put(_DIR, key, (np.ascontiguousarray(up), np.ascontiguousarray(dn)), _DIR_CAP)


def _chart_atr(pair, chart_tf, length):
    key = (pair, chart_tf, int(length))
    hit = _get(_ATRC, key)
    if hit is not None:
        return hit
    b = _bars(pair, chart_tf)
    return _put(_ATRC, key, fgf._atr(b['high'], b['low'], b['close'], int(length)), _ATRC_CAP)


# ---------------------------------------------------------------------------------------------------
# broker + strategy (numba)
# ---------------------------------------------------------------------------------------------------
NCOL = 22
(C_DIR, C_SIG, C_SB, C_EB, C_XB, C_EPX, C_QTY, C_XPX, C_KIND, C_GROSS, C_COST, C_EQB, C_ATR, C_SL0, C_TP0,
 C_SLR, C_TPR, C_HOT, C_REV, C_ACTT, C_OFFT, C_XSUB) = range(NCOL)
# C_XSUB: 'mag' only, the row (in the sub-bar arrays) of the 1-minute sub-bar in which a bracket exit filled
NEG = -1.0e300


@njit(cache=True)
def _walk(v0, v1, v2, v3, sl, has_sl, tp, has_tp, has_tr, armed, best, act, off):
    """The bracket of the open trade along one bar, in LONG space (a short is passed with every price
    negated: its stop is then below and its target above). v0 = open, v1 / v2 = the two extremes in path
    order, v3 = close. Returns (kind, fill price in long space before slippage, armed, best); kind 0 =
    still open.
      open:    the stop in force S* = max(sl, best - off if armed); v0 <= S* -> stop at the open;
               else v0 >= tp -> target at the open; else the open can arm / ratchet the trail.
      rising:  reaches tp -> target at max(tp, start of the leg); else arms / ratchets the trail.
      falling: S* as it is at the start of the leg; reached -> stop at min(S*, start of the leg).
    'trail' when the trailing stop is the level hit (armed and best - off >= sl, or no sl), else 'sl'.
    Inclusive comparisons, no tolerance, no rounding."""
    lvl = NEG
    is_tr = False
    if has_sl:
        lvl = sl
    if has_tr and armed:
        ts = best - off
        if (not has_sl) or ts >= sl:
            lvl = ts
            is_tr = True
    if v0 <= lvl:
        return (K_TRAIL if is_tr else K_SL), v0, armed, best
    if has_tp and v0 >= tp:
        return K_TP, v0, armed, best
    if has_tr:
        if armed:
            if v0 > best:
                best = v0
        elif v0 >= act:
            armed = True
            best = v0
    p = v0
    for s in range(3):
        if s == 0:
            b = v1
        elif s == 1:
            b = v2
        else:
            b = v3
        if b > p:
            if has_tp and b >= tp:
                return K_TP, (tp if tp > p else p), armed, best
            if has_tr:
                if armed:
                    if b > best:
                        best = b
                elif b >= act:
                    armed = True
                    best = b
        elif b < p:
            lvl = NEG
            is_tr = False
            if has_sl:
                lvl = sl
            if has_tr and armed:
                ts = best - off
                if (not has_sl) or ts >= sl:
                    lvl = ts
                    is_tr = True
            if b <= lvl:
                return (K_TRAIL if is_tr else K_SL), (lvl if lvl < p else p), armed, best
        p = b
    return 0, 0.0, armed, best


@njit(cache=True)
def _bar_walk(pos, oj, hj, lj, cj, sl, has_sl, tp, has_tp, has_tr, armed, best, act, off):
    """The bracket of a trade of real side pos along ONE bar (a chart bar on 'tv', a 1-minute sub-bar on
    'mag'): the rule-4 path order of THAT bar ((high - open) < (open - low) -> high first; a tie goes low
    first), a short in long space (every price negated). Returns (kind, fill price before slippage in REAL
    prices, armed, best); the trailing state stays in long space."""
    if (hj - oj) < (oj - lj):
        v1 = hj
        v2 = lj
    else:
        v1 = lj
        v2 = hj
    if pos > 0:
        kind, px, armed, best = _walk(oj, v1, v2, cj, sl, has_sl, tp, has_tp, has_tr,
                                      armed, best, act, off)
    else:
        kind, px, armed, best = _walk(-oj, -v1, -v2, -cj, -sl, has_sl, -tp, has_tp, has_tr,
                                      armed, best, act, off)
        px = -px
    return kind, px, armed, best


@njit(cache=True)
def _decide(pos, equity, cj, up, dn, a, inv, allow_long, allow_short, allow_rev,
            sl_mult, tp_mult, use_trail, act_mul, off_mul, mintick, qty_frac):
    """The entry decision of one script run (L779-783, L800-809; original O157-163), from the position after
    this bar's fills. Returns (flag, d, sig, qty, sl0, tp0, actT, offT):
    flag 0 = no signal, 1 = order placed, 2 = signal ignored (side already held / reverse not allowed),
    3 = quantity <= 0 (no order). d = REAL side of the order, sig = normal-frame side of the trigger."""
    long_sig = (dn if inv else up) and allow_long           # L780 (O157: tradeDir != "Short Only")
    short_sig = (up if inv else dn) and allow_short         # L781 (O158: tradeDir != "Long Only")
    go_long = long_sig and pos <= 0 and (allow_rev or pos >= 0)       # L782 (O160, O162)
    go_short = short_sig and pos >= 0 and (allow_rev or pos <= 0)     # L783 (O161, O163)
    if not (go_long or go_short):
        if long_sig or short_sig:
            return 2, 0, 0, 0.0, np.nan, np.nan, 0.0, 0.0
        return 0, 0, 0, 0.0, np.nan, np.nan, 0.0, 0.0
    d = 1 if go_long else -1
    sig = 1 if up else -1
    q = qty_frac * equity / cj                              # percent_of_equity 10, at this close
    if not (q > 0.0):
        return 3, d, sig, 0.0, np.nan, np.nan, 0.0, 0.0
    sl0 = np.nan
    tp0 = np.nan
    if sl_mult > 0.0:
        sl0 = cj - d * (a * sl_mult)                        # L816 / L823 with ep = close
    if tp_mult > 0.0:
        tp0 = cj + d * (a * tp_mult)                        # L817 / L824
    act_t = 0.0
    off_t = 0.0
    if use_trail:                                           # L808-809: math.max(1, math.round(...))
        act_t = max(1.0, math.floor(a * act_mul / mintick + 0.5))
        off_t = max(1.0, math.floor(a * off_mul / mintick + 0.5))
    return 1, d, sig, q, sl0, tp0, act_t, off_t


@njit(cache=True)
def _close_decision(pos, bars_in, use_vol, collapse, max_bars):
    """The close_all calls of one run (L829-835): 'vol' first, then 'time' (one close; the first names it)."""
    if pos == 0:
        return 0
    if use_vol and collapse:
        return K_VOL
    if max_bars > 0 and bars_in >= max_bars:
        return K_TIME
    return 0


@njit(cache=True)
def _kernel(o, h, l, c, trig_up, trig_dn, hot, atr, collapse,
            inv, allow_long, allow_short, allow_rev,
            sl_mult, tp_mult, use_trail, act_mul, off_mul, use_vol, max_bars, rev_closes,
            c_fix, c_pct, slip, mintick, init_cap, qty_frac, mid_j, cap, full,
            mag, ptr, so, sh, sl_, sc):
    """mag: the bracket walks the sub-bars [ptr[j], ptr[j+1]) of so / sh / sl_ / sc (1-minute bars of chart
    bar j) instead of the chart bar; everything else is the same on both paths."""
    n = o.shape[0]
    T = np.full((cap, NCOL), np.nan)
    nt = 0
    eq_arr = np.empty(n if full else 0)
    pos_arr = np.zeros(n if full else 0, np.int8)

    has_sl = sl_mult > 0.0
    has_tp = tp_mult > 0.0
    has_br = has_sl or has_tp or use_trail                 # hasBracket (L812)

    cash = init_cap
    pos = 0                 # real side of the open trade
    q = 0.0                 # its quantity
    e = 0.0                 # its entry fill price (strategy.position_avg_price)
    eb = -1                 # its fill bar (strategy.opentrades.entry_bar_index(0))
    a_t = 0.0               # the ATR stored with it (entryAtr of its order)
    ecost = 0.0
    sl = 0.0                # levels in force (real prices)
    tp = 0.0
    armed = False           # trailing state, LONG space
    best = 0.0
    act = 0.0
    off = 0.0

    od = 0                  # pending entry order (real side; 0 = none)
    osig = 0
    oq = 0.0
    oa = 0.0
    osl = np.nan
    otp = np.nan
    oact = 0.0
    ooff = 0.0
    ohot = 0
    obar = -1
    creq = 0                # pending close_all (K_VOL / K_TIME; 0 = none)

    taken_up = 0
    taken_dn = 0
    ignored = 0
    zero_qty = 0
    rev_close = 0
    unfilled = 0
    bad = 0
    slip_paid = 0.0
    n_pos = 0
    dd_pk = init_cap
    dd_rel = 0.0
    dd_abs = 0.0
    eq_mid = init_cap
    eq_last = init_cap

    for j in range(n):
        oj = o[j]
        cj = c[j]
        # ---------------- A. fills at the open: the entry (reversal) first, then the close_all ----------
        if od != 0:
            rev = 0.0
            if pos != 0:
                if pos != -od:
                    bad += 1
                fill = oj - pos * slip
                gross = pos * q * (fill - e)
                xc = q * (c_fix + c_pct * fill)
                cash += gross - xc
                slip_paid += slip * q
                T[nt, C_XB] = j
                T[nt, C_XPX] = fill
                T[nt, C_KIND] = K_REV
                T[nt, C_GROSS] = gross
                T[nt, C_COST] = ecost + xc
                nt += 1
                rev = 1.0
            pos = od
            q = oq
            e = oj + od * slip
            eb = j
            a_t = oa
            sl = osl                                   # the fill bar's levels: from the signal close
            tp = otp
            armed = False
            best = pos * e
            act = pos * e + oact * mintick             # A = e + d * (actT * mintick), in long space
            off = ooff * mintick
            ecost = q * (c_fix + c_pct * e)
            slip_paid += slip * q
            T[nt, C_DIR] = pos
            T[nt, C_SIG] = osig
            T[nt, C_SB] = obar
            T[nt, C_EB] = j
            T[nt, C_EPX] = e
            T[nt, C_QTY] = q
            T[nt, C_EQB] = cash
            T[nt, C_ATR] = a_t
            T[nt, C_SL0] = osl
            T[nt, C_TP0] = otp
            T[nt, C_HOT] = ohot
            T[nt, C_REV] = rev
            T[nt, C_ACTT] = oact
            T[nt, C_OFFT] = ooff
            cash -= ecost
            if creq != 0:
                rev_close += 1
                if rev_closes:                         # 'closes': the close_all closes the NEW trade
                    fill = oj - pos * slip
                    gross = pos * q * (fill - e)
                    xc = q * (c_fix + c_pct * fill)
                    cash += gross - xc
                    slip_paid += slip * q
                    T[nt, C_XB] = j
                    T[nt, C_XPX] = fill
                    T[nt, C_KIND] = creq
                    T[nt, C_GROSS] = gross
                    T[nt, C_COST] = ecost + xc
                    nt += 1
                    pos = 0
            od = 0
            creq = 0
        elif creq != 0:
            if pos != 0:
                fill = oj - pos * slip
                gross = pos * q * (fill - e)
                xc = q * (c_fix + c_pct * fill)
                cash += gross - xc
                slip_paid += slip * q
                T[nt, C_XB] = j
                T[nt, C_XPX] = fill
                T[nt, C_KIND] = creq
                T[nt, C_GROSS] = gross
                T[nt, C_COST] = ecost + xc
                nt += 1
                pos = 0
            creq = 0

        # ---------------- A3 + B. the bracket along the bar's path ---------------------------------------
        if pos != 0 and has_br:
            xsub = -1
            if mag:
                # the 1-minute sub-bars of this chart bar in time order: each its own open test and path,
                # the trailing state carried over, the levels those of the chart bar
                kind = 0
                px = 0.0
                for s in range(ptr[j], ptr[j + 1]):
                    kind, px, armed, best = _bar_walk(pos, so[s], sh[s], sl_[s], sc[s], sl, has_sl, tp, has_tp,
                                                      use_trail, armed, best, act, off)
                    if kind != 0:
                        xsub = s
                        break
            else:
                kind, px, armed, best = _bar_walk(pos, oj, h[j], l[j], cj, sl, has_sl, tp, has_tp, use_trail,
                                                  armed, best, act, off)
            if kind != 0:
                T[nt, C_XSUB] = xsub
                if kind == K_TP:
                    fill = px                          # limit: no slippage
                else:
                    fill = px - pos * slip             # stop: 1 tick against
                    slip_paid += slip * q
                gross = pos * q * (fill - e)
                xc = q * (c_fix + c_pct * fill)
                cash += gross - xc
                T[nt, C_XB] = j
                T[nt, C_XPX] = fill
                T[nt, C_KIND] = kind
                T[nt, C_GROSS] = gross
                T[nt, C_COST] = ecost + xc
                nt += 1
                pos = 0

        # ---------------- C. the script run at the close --------------------------------------------------
        equity = cash
        if pos != 0:
            equity = cash + pos * q * (cj - e)
        flag, d, sig, oq_, sl0, tp0, act_t, off_t = _decide(
            pos, equity, cj, trig_up[j], trig_dn[j], atr[j], inv, allow_long, allow_short, allow_rev,
            sl_mult, tp_mult, use_trail, act_mul, off_mul, mintick, qty_frac)
        if flag == 1:
            od = d
            osig = sig
            oq = oq_
            oa = atr[j]
            osl = sl0
            otp = tp0
            oact = act_t
            ooff = off_t
            ohot = hot[j]
            obar = j
            if sig > 0:
                taken_up += 1
            else:
                taken_dn += 1
        elif flag == 2:
            ignored += 1
        elif flag == 3:
            zero_qty += 1
        # re-anchor: the first run after the fill (L815-817 / L822-824 with ep = position_avg_price)
        if pos != 0 and eb == j and has_br:
            if has_sl:
                sl = e - pos * (a_t * sl_mult)
                T[nt, C_SLR] = sl
            if has_tp:
                tp = e + pos * (a_t * tp_mult)
                T[nt, C_TPR] = tp
        creq = _close_decision(pos, j - eb, use_vol, collapse[j], max_bars)

        # ---------------- D. bar-close equity --------------------------------------------------------------
        if pos != 0:
            n_pos += 1
        if j < n - 1:
            if equity > dd_pk:
                dd_pk = equity
            x = (dd_pk - equity) / dd_pk
            if x > dd_rel:
                dd_rel = x
            x = dd_pk - equity
            if x > dd_abs:
                dd_abs = x
            if j == mid_j:
                eq_mid = equity
        else:
            eq_last = equity
        if full:
            eq_arr[j] = equity
            pos_arr[j] = pos

    # ---- the end of the window: pending orders are dropped, the open trade is closed at the last close
    if od != 0:
        unfilled += 1
    if creq != 0:
        unfilled += 1
    if n > 0 and pos != 0:
        j = n - 1
        fill = c[j] - pos * slip
        gross = pos * q * (fill - e)
        xc = q * (c_fix + c_pct * fill)
        cash += gross - xc
        slip_paid += slip * q
        T[nt, C_XB] = j
        T[nt, C_XPX] = fill
        T[nt, C_KIND] = K_END
        T[nt, C_GROSS] = gross
        T[nt, C_COST] = ecost + xc
        nt += 1
        pos = 0
        eq_last = cash
        if full:
            eq_arr[j] = cash
    if n > 0:
        if eq_last > dd_pk:
            dd_pk = eq_last
        x = (dd_pk - eq_last) / dd_pk
        if x > dd_rel:
            dd_rel = x
        x = dd_pk - eq_last
        if x > dd_abs:
            dd_abs = x
        if mid_j == n - 1:
            eq_mid = eq_last
    stats = np.array([eq_last, eq_mid, dd_rel, dd_abs, float(n_pos), float(taken_up), float(taken_dn),
                      float(ignored), float(unfilled), float(zero_qty), float(rev_close), slip_paid, cash,
                      float(bad)])
    return T[:nt], stats, eq_arr, pos_arr


# ---------------------------------------------------------------------------------------------------
# public interface
# ---------------------------------------------------------------------------------------------------
def _finish_P(P):
    trig = P['trigger'] & P['inRange']
    up = P['dirUp']
    dn = P['dirDn']
    if (up & dn).any():
        raise AssertionError('dirUp and dirDn both true')
    P['trigUp'] = np.ascontiguousarray(trig & up)
    P['trigDn'] = np.ascontiguousarray(trig & dn)
    P['triggers'] = int(trig.sum())
    P['trig_up'] = int(P['trigUp'].sum())
    P['trig_dn'] = int(P['trigDn'].sum())
    P['trig_none'] = P['triggers'] - P['trig_up'] - P['trig_dn']
    P['cap'] = P['trig_up'] + P['trig_dn'] + 2
    P['atr_cache'] = P.get('atr_cache') or {}
    P['vc_cache'] = {}
    return P


def prepare(pair, chart_tf, params=None):
    """Everything that does not depend on the ORDER / EXIT inputs. ORDER / EXIT keys given here are kept as
    the defaults of simulate(P)."""
    Q = _check(_merge(DEFAULTS, params))
    tf = str(chart_tf)
    b = _bars(pair, tf)
    s0, e0 = WINDOWS[pair]
    start = int(Q['start']) if Q['start'] is not None else s0
    end = int(Q['end']) if Q['end'] is not None else e0
    tc_all = b['t_close']
    w0 = int(np.searchsorted(tc_all, start, side='left'))
    w1 = int(np.searchsorted(tc_all, end, side='right'))
    n = w1 - w0
    if n <= 0:
        raise ValueError('empty window')
    sl = slice(w0, w1)
    per = (Q['fastATRPeriod'], Q['slowATRPeriod'], Q['stdDevPeriod'], Q['candleRangePeriod'],
           Q['normalizationPeriod'])
    wts = (Q['aatrWeight'], Q['vrWeight'], Q['nsdWeight'], Q['acrWeight'])
    enabled = tuple(Q[k] for k in EN_KEYS)
    # with noRepaint off the request is expr[0] / lookahead off: ltfRule has nothing to choose
    ltf = Q['ltfRule'] if Q['noRepaint'] else 'first'
    C = _counts(pair, tf, w0, w1, per, wts, Q['noRepaint'], ltf, Q['highVolThreshold'], enabled)
    if C['na_in_window']:
        raise AssertionError('%d na AMVI values of enabled timeframes inside the window' % C['na_in_window'])
    hot = C['hot'][1:]
    trigger = C['anyx'] & (hot >= Q['minConfluence'])                # L770
    t_open = b['t_open'][sl]
    if Q['useDateRange']:                                            # L776 (time = the bar's open)
        in_range = (t_open >= Q['startTime']) & (t_open <= Q['endTime'])
    else:
        in_range = np.ones(n, np.bool_)
    up, dn = _direction(pair, tf, start, end, w0, w1, Q)
    mid = start + (end - start) // 2
    tc = tc_all[sl]
    P = dict(pair=pair, tf=tf, start=start, end=end, mid=mid,
             mid_j=int(np.searchsorted(tc, mid, side='right')) - 1,
             w0=w0, w1=w1, n=n,
             open=b['open'][sl], high=b['high'][sl], low=b['low'][sl], close=b['close'][sl],
             t_open=t_open, t_close=tc,
             trigger=np.ascontiguousarray(trigger), inRange=np.ascontiguousarray(in_range),
             anyCross=C['anyx'], dirUp=up, dirDn=dn,
             hotCount=np.ascontiguousarray(hot), enCount=C['en'][1:], avgAmvi=C['avg'],
             params=Q, seconds_ignored=int(sum(Q[k] for k in SEC_KEYS)), injected=False)
    return _finish_P(P)


def prepare_injected(o, h, l, c, trigUp, trigDn, avgAmvi, atr, hot=None, t_open=None, t_close=None,
                     params=None, pair='XAU', atr_len=14):
    """A P built from hand-made arrays (kernel tests, independent of fgf and of AMVI). avgAmvi has n + 1
    values (the row before the first bar first); atr is the ATR of exitAtrLen = atr_len."""
    Q = _check(_merge(DEFAULTS, params))
    o = np.ascontiguousarray(o, np.float64)
    n = len(o)
    t_open = np.arange(n, dtype=np.int64) * 60 if t_open is None else np.asarray(t_open, np.int64)
    t_close = t_open + 60 if t_close is None else np.asarray(t_close, np.int64)
    up = np.ascontiguousarray(trigUp, np.bool_)
    dn = np.ascontiguousarray(trigDn, np.bool_)
    start, end = int(t_close[0]), int(t_close[-1])
    mid = start + (end - start) // 2
    P = dict(pair=pair, tf='inj', start=start, end=end, mid=mid,
             mid_j=int(np.searchsorted(t_close, mid, side='right')) - 1, w0=0, w1=n, n=n,
             open=o, high=np.ascontiguousarray(h, np.float64), low=np.ascontiguousarray(l, np.float64),
             close=np.ascontiguousarray(c, np.float64), t_open=t_open, t_close=t_close,
             trigger=up | dn, inRange=np.ones(n, np.bool_), anyCross=up | dn, dirUp=up, dirDn=dn,
             hotCount=(np.zeros(n, np.int64) if hot is None else np.ascontiguousarray(hot, np.int64)),
             enCount=np.full(n, 7, np.int64), avgAmvi=np.ascontiguousarray(avgAmvi, np.float64),
             params=Q, seconds_ignored=int(sum(Q[k] for k in SEC_KEYS)), injected=True,
             atr_cache={int(atr_len): np.ascontiguousarray(atr, np.float64)})
    return _finish_P(P)


def _sim_params(P, x):
    Q = P['params']
    if x:
        for k, v in x.items():
            if k in IGNORED_KEYS:
                continue
            if k not in DEFAULTS:
                raise ValueError('unknown param %r' % (k,))
            if k in PREP_KEYS and v != Q[k]:
                raise ValueError('%r is fixed by prepare()' % (k,))
        Q = _check(_merge(Q, {k: v for k, v in x.items() if k in SIM_KEYS}))
    return Q


def _atr_window(P, length):
    a = P['atr_cache'].get(length)
    if a is None:
        if P['injected']:
            raise ValueError('no injected ATR for exitAtrLen=%d' % length)
        a = np.ascontiguousarray(_chart_atr(P['pair'], P['tf'], length)[P['w0']:P['w1']])
        P['atr_cache'][length] = a
    return a


def vol_collapse(P, low):
    """volCollapse = ta.crossunder(avgAmvi, lowVolThreshold) on the window bars (L829)."""
    vc = P['vc_cache'].get(low)
    if vc is None:
        avg = P['avgAmvi']
        with np.errstate(invalid='ignore'):
            vc = np.ascontiguousarray((avg[1:] < low) & (avg[:-1] >= low))
        if len(P['vc_cache']) > 16:
            P['vc_cache'].clear()
        P['vc_cache'][low] = vc
    return vc


def sub_bars(pair, chart_tf, w0, w1, check=True):
    """The 1-minute sub-bars of the chart rows w0..w1-1 of data/<pair>_<chart_tf>.parquet: the rows of
    data/<pair>_1.parquet with t_open in [chart t_open, chart t_close) (SWEEP_AH_SPEC.md section 2).
    Returns (ptr, o, h, l, c, t_open): ptr int64 (n + 1); the sub-bars of window bar j are the rows
    [ptr[j], ptr[j+1]) of the five contiguous arrays. With check, every chart bar has at least one sub-bar
    and its OHLC equals the sub-bars' first open / highest high / lowest low / last close (build_bars.py built
    the chart bars from them)."""
    b = _bars(pair, str(chart_tf))
    m = _bars(pair, '1')
    bo = b['t_open'][w0:w1]
    bc = b['t_close'][w0:w1]
    s = np.searchsorted(m['t_open'], bo, side='left')
    e = np.searchsorted(m['t_open'], bc, side='left')
    ln = (e - s).astype(np.int64)
    ptr = np.zeros(len(bo) + 1, np.int64)
    np.cumsum(ln, out=ptr[1:])
    if len(bo) and (ln <= 0).any():
        raise ValueError('%s %s: %d chart bars without 1-minute sub-bars' % (pair, chart_tf, int((ln <= 0).sum())))
    idx = np.repeat(s - ptr[:-1], ln) + np.arange(int(ptr[-1]), dtype=np.int64)
    ca = np.ascontiguousarray
    so = ca(m['open'][idx])
    sh = ca(m['high'][idx])
    sl = ca(m['low'][idx])
    sc = ca(m['close'][idx])
    st = ca(m['t_open'][idx])
    if check and len(bo):
        a = ptr[:-1]
        ok = ((so[a] == b['open'][w0:w1]) & (sc[ptr[1:] - 1] == b['close'][w0:w1])
              & (np.maximum.reduceat(sh, a) == b['high'][w0:w1])
              & (np.minimum.reduceat(sl, a) == b['low'][w0:w1]))
        if not ok.all():
            raise ValueError('%s %s: %d chart bars differ from their sub-bars' % (pair, chart_tf, int((~ok).sum())))
    return ptr, so, sh, sl, sc, st


def get_sub(P):
    """The sub-bar table of P's window, built (and checked) once and kept in P['sub']."""
    if P.get('sub') is None:
        if P.get('injected'):
            raise ValueError("an injected P has no 1-minute data: pass sub= (e.g. fake_sub_bars(P))")
        P['sub'] = sub_bars(P['pair'], P['tf'], P['w0'], P['w1'])
    return P['sub']


def fake_sub_bars(P):
    """One sub-bar per chart bar, equal to the bar (tests: 'mag' on it == 'tv')."""
    n = P['n']
    return (np.arange(n + 1, dtype=np.int64), np.ascontiguousarray(P['open'], np.float64),
            np.ascontiguousarray(P['high'], np.float64), np.ascontiguousarray(P['low'], np.float64),
            np.ascontiguousarray(P['close'], np.float64), np.ascontiguousarray(P['t_open'], np.int64))


_NO_SUB = (np.zeros(1, np.int64), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0, np.int64))


def simulate(P, x=None, full=False, sub=None):
    """Orders and exits on prepare()'s arrays. x: the ORDER / EXIT inputs by Pine name (SPEC 3.2), plus
    path ('tv' | 'mag'), cost ('tv' | 'ours' | 'stress'), inv (= amviTradeDir "Inverted"), revClose; a SIGNAL
    key in x raises unless it repeats the prepared value. full=True adds the bar-close equity and position.
    sub: on path 'mag', a sub-bar table (ptr, o, h, l, c, t_open) to use instead of the 1-minute data
    (tests: fake_sub_bars(P))."""
    Q = _sim_params(P, x)
    mag = Q['path'] == 'mag'
    if mag:
        S = sub if sub is not None else get_sub(P)
        if len(S[0]) != P['n'] + 1:
            raise ValueError('the sub-bar table does not match the window')
    else:
        S = _NO_SUB
    atr = _atr_window(P, Q['exitAtrLen'])
    if np.isnan(atr).any():
        raise AssertionError('na ATR inside the window')
    vc = vol_collapse(P, Q['lowVolThreshold'])
    c_fix, c_pct, slip = COSTS[Q['cost']][P['pair']]
    td = Q['tradeDir']
    T, stats, eq, pos = _kernel(
        P['open'], P['high'], P['low'], P['close'], P['trigUp'], P['trigDn'], P['hotCount'], atr, vc,
        bool(Q['inv']), td != 'Short Only', td != 'Long Only', bool(Q['allowReverse']),
        float(Q['slMult']), float(Q['tpMult']), bool(Q['useTrail']), float(Q['trailActMul']),
        float(Q['trailOffMul']), bool(Q['useVolExit']), int(Q['maxBars']), Q['revClose'] == 'closes',
        float(c_fix), float(c_pct), float(slip), MINTICK, INITIAL_CAPITAL, QTY_FRAC,
        int(P['mid_j']), int(P['cap']), bool(full),
        mag, S[0], S[1], S[2], S[3], S[4])
    if stats[13] != 0:
        raise AssertionError('a reversal order met a position of its own side')
    xs = T[:, C_XSUB]
    xsub = np.where(np.isnan(xs), -1, xs).astype(np.int64)
    return dict(T=T, stats=stats, eq=eq, pos=pos, params=Q, xsub=xsub,
                sub_t_open=(S[5] if mag else None))


def _cols(P, R):
    T = R['T']
    Q = R['params']
    w0 = P['w0']
    kind = T[:, C_KIND].astype(np.int64)
    eb = T[:, C_EB].astype(np.int64)
    xb = T[:, C_XB].astype(np.int64)
    pnl_gross = T[:, C_GROSS]
    costs = T[:, C_COST]
    pnl = pnl_gross - costs
    atr = T[:, C_ATR]
    qty = T[:, C_QTY]
    sl_dist = atr * Q['slMult'] if Q['slMult'] > 0 else np.full(len(T), np.nan)
    tp_dist = atr * Q['tpMult'] if Q['tpMult'] > 0 else np.full(len(T), np.nan)
    with np.errstate(invalid='ignore', divide='ignore'):
        r_mult = pnl / (sl_dist * qty)
    return dict(kind=kind, eb=eb, xb=xb, pnl=pnl, pnl_gross=pnl_gross, costs=costs, atr=atr, qty=qty,
                sl_dist=sl_dist, tp_dist=tp_dist, r_mult=r_mult, w0=w0)


def trades(P, R):
    T = R['T']
    X = _cols(P, R)
    to = P['t_open']
    tc = P['t_close']
    kind, eb, xb = X['kind'], X['eb'], X['xb']
    return pd.DataFrame({
        'dir': T[:, C_DIR].astype(np.int64),
        'sig': T[:, C_SIG].astype(np.int64),
        'sig_bar': T[:, C_SB].astype(np.int64) + X['w0'],
        'entry_bar': eb + X['w0'],
        'exit_bar': xb + X['w0'],
        'entry_time': to[eb],
        'exit_time': np.where(kind == K_END, tc[xb], to[xb]),
        'entry_px': T[:, C_EPX],
        'qty': X['qty'],
        'exit_px': T[:, C_XPX],
        'exit_kind': [KINDS[k] for k in kind],
        'pnl': X['pnl'],
        'pnl_gross': X['pnl_gross'],
        'costs': X['costs'],
        'eq_before': T[:, C_EQB],
        'atr': X['atr'],
        'sl_dist': X['sl_dist'],
        'tp_dist': X['tp_dist'],
        'r_mult': X['r_mult'],
        'sl0': T[:, C_SL0],
        'tp0': T[:, C_TP0],
        'sl_px': T[:, C_SLR],
        'tp_px': T[:, C_TPR],
        'hot': T[:, C_HOT].astype(np.int64),
        'rev': T[:, C_REV] > 0,
    })


def summary(P, R):
    T = R['T']
    Q = R['params']
    st = R['stats']
    X = _cols(P, R)
    init = INITIAL_CAPITAL
    pnl = X['pnl']
    nt = len(pnl)
    final = float(st[0])
    eq_mid = float(st[1])
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    d = T[:, C_DIR]
    kc = np.bincount(X['kind'], minlength=len(KINDS)) if nt else np.zeros(len(KINDS), np.int64)
    out = dict(
        start=int(P['start']), end=int(P['end']), bars=int(P['n']),
        trades=nt,
        net_pct=(final - init) / init * 100,
        pf=(gp / gl) if gl > 0 else (np.inf if gp > 0 else np.nan),
        win_pct=float((pnl > 0).mean() * 100) if nt else np.nan,
        max_dd_pct=float(st[2] * 100),
        max_dd_init_pct=float(st[3] / init * 100),
        long=int((d > 0).sum()), short=int((d < 0).sum()),
        raw_long=int(P['trig_up']), raw_short=int(P['trig_dn']), blocked_long=0, blocked_short=0,
        half1_pct=(eq_mid - init) / init * 100,
        half2_pct=(final - eq_mid) / init * 100,
        exposure=float(st[4] / P['n']),
        final_equity=final,
    )
    for i, nm in enumerate(KINDS[1:], 1):
        out['exit_' + nm] = int(kc[i])
    out['zero_length'] = int((X['eb'] == X['xb']).sum())
    # fair halves: the trades ENTERED in each half, prod(1 + pnl / eq_before) - 1
    first = P['t_open'][X['eb']] <= P['mid']
    r = 1.0 + pnl / T[:, C_EQB]
    n1 = int(first.sum())
    out.update(h1r_pct=(float(np.prod(r[first])) - 1.0) * 100.0, h2r_pct=(float(np.prod(r[~first])) - 1.0) * 100.0,
               h1_trades=n1, h2_trades=nt - n1,
               avg_bars_held=float((X['xb'] - X['eb']).mean()) if nt else np.nan,
               costs=float(X['costs'].sum()))
    rm = X['r_mult']
    okr = ~np.isnan(rm)
    out.update(
        triggers=int(P['triggers']), trig_up=int(P['trig_up']), trig_dn=int(P['trig_dn']),
        trig_none=int(P['trig_none']),
        taken_up=int(st[5]), taken_dn=int(st[6]), ignored_held=int(st[7]), orders_unfilled_end=int(st[8]),
        zero_qty=int(st[9]), rev_close_same_run=int(st[10]), slippage_paid=float(st[11]),
        net_r=float(rm[okr].sum()), h1_r=float(rm[okr & first].sum()), h2_r=float(rm[okr & ~first].sum()),
        min_trail_off_pct=(float(np.min(T[:, C_OFFT] * MINTICK / T[:, C_EPX] * 100.0))
                           if (Q['useTrail'] and nt) else np.nan),
        seconds_ignored=int(P['seconds_ignored']),
    )
    return out


def run(pair, chart_tf, params=None):
    """prepare + simulate with one dict (split into SIGNAL and ORDER / EXIT keys)."""
    params = dict(params or {})
    Q = _check(_merge(DEFAULTS, params))            # validates; resolves inv / amviTradeDir once
    pp = {k: v for k, v in params.items() if k in PREP_KEYS}
    xx = {k: Q[k] for k in params if k in SIM_KEYS}
    P = prepare(pair, chart_tf, pp)
    R = simulate(P, xx)
    return trades(P, R), summary(P, R)


def fmt(s):
    return ("trades=%d (L %d / S %d) net=%.3f%% netR=%.2f pf=%.3f win=%.1f%% maxDD=%.3f%% expo=%.3f | "
            "sl %d tp %d trail %d rev %d vol %d time %d end %d | zero-len %d | trig %d (up %d / dn %d / none %d)"
            % (s['trades'], s['long'], s['short'], s['net_pct'], s['net_r'], s['pf'], s['win_pct'],
               s['max_dd_pct'], s['exposure'], s['exit_sl'], s['exit_tp'], s['exit_trail'], s['exit_reverse'],
               s['exit_vol'], s['exit_time'], s['exit_end'], s['zero_length'], s['triggers'], s['trig_up'],
               s['trig_dn'], s['trig_none']))


if __name__ == '__main__':
    import time as _time
    for pair_, tf_ in (('BTC', '60'), ('XAU', '60')):
        t0 = _time.time()
        P_ = prepare(pair_, tf_)
        t1 = _time.time()
        for nm, src in (('on', 'fgf'), ('off', 'orig')):
            Pv = P_ if src == 'fgf' else prepare(pair_, tf_, {'dirSource': 'orig'})
            for inv_ in (False, True):
                R_ = simulate(Pv, {'inv': inv_})
                print(pair_, tf_, 'filter', nm, 'inv', inv_, fmt(summary(Pv, R_)))
        print('  prepare %.2f s' % (t1 - t0))
