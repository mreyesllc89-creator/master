"""FlashGold Direction Strategy [Update 1] (key `fgds`): CANONICAL Python replica (stage 3 of REPLICA_SPEC.md,
brief SPEC_fgds.md).

Implementation B (fgds_b.py) after reconciliation with the independent implementation A (fgds_a.py): the two
agree on every trade, every summary field and the per-bar equity / position / quantity arrays of every compared
case, real and synthetic bars (reconcile_fgds.md), and neither needed a fix. Added here: the 1-minute "Bar
Magnifier" path 'mag'. On path 'tv' this module gives exactly what fgds_b.py gives. Ground truth:
/home/user/master/FlashGold_Direction_Strategy.pine at HEAD (813 lines, Update 1); Lnnn below are its line
numbers. Interpretations and limits: fgds_notes.md.

    prepare(pair, chart_tf, params=None) -> P      filter call (fgf.fgf_permissions, never re-implemented),
                                                   the three trigger pairs and keep pairs, the bars
    simulate(P, x=None, full=False, sub=None) -> R the strategy section (L728-813) + TradingView's broker
                                                   on history, one numba kernel
    trades(P, R) -> DataFrame
    summary(P, R) -> dict
    run(pair, chart_tf, params=None) -> (trades, summary)

x: the ORDER / EXIT inputs by Pine name (SPEC_fgds 3.2) plus the replica controls
    inv     the script's own input dsDirection == "Inverted" (L699 / L760, older than Update 1); either name is
            accepted, both given must agree
    path    'tv'  one intrabar path per chart bar (TradingView without Bar Magnifier; SPEC_AH rule 4)
            'mag' the bracket of the open trade (stop loss, target, trailing stop: the only price orders this
                  script places) walks the 1-minute sub-bars of the chart bar in time order (rows of
                  data/<PAIR>_1.parquet with t_open in [t_open, t_close) of the chart bar), each sub-bar with
                  its own rule-4 path and the gap test at its own open, the trailing state carrying over. The
                  market orders (entries, reversals, strategy.close) fill at the chart bar's open and the script
                  runs at the chart bar's close, as on 'tv'. Chart "1": mag == tv.
    cost    'tv' (the strategy() call: commission 0, slippage 0), 'ours', 'stress'
simulate(..., sub=(ptr, o, h, l, c[, t])) replaces the 1-minute sub-bars of path 'mag' (tests: fake_sub_bars,
synthetic bars).

Run as a script for a quick BTC 60 / XAU 60 run:  python3 -I fgds.py
"""
import math
import os
import sys
import time as _time

import numpy as np
import pandas as pd
from numba import njit

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import fgf  # noqa: E402  (the verified filter replica)

MINTICK = 0.01
POINTVALUE = 1.0
INITIAL_CAPITAL = 10000.0          # strategy(initial_capital=10000)
WINDOWS = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}

KINDS = ['', 'sl', 'tp', 'trail', 'reverse', 'opp', 'zone', 'time', 'end']
K_SL, K_TP, K_TRAIL, K_REV, K_OPP, K_ZONE, K_TIME, K_END = 1, 2, 3, 4, 5, 6, 7, 8
NEG = -1.0e300

# per fill, per unit: (fixed $, fraction of the fill value); 'tv' = the strategy() call: commission 0, slippage 0
COSTS = {
    'tv': {'XAU': (0.0, 0.0), 'BTC': (0.0, 0.0)},
    'ours': {'XAU': (0.15, 0.0), 'BTC': (0.10, 0.0002)},
    'stress': {'XAU': (0.25 + 0.01, 0.0), 'BTC': (0.10 + 0.01, 0.00035)},
}

TRIGGERS = ('Zone start', 'Signal confirmed', 'New signal')
DIRECTIONS = ('Follow the filter', 'Inverted')
SIDES = ('Both', 'Long only', 'Short only')
EXIT_MODES = ('Points', 'ATR')
QTY_MODES = ('Fixed', 'Risk %')

# ORDER / EXIT inputs (L697-725) + replica controls
SIM_DEFAULTS = dict(
    dsTrigger='Zone start', dsDirection='Follow the filter', dsSides='Both', dsZoneExit=True, dsReverse=True,
    dsExitMode='ATR', dsSlPoints=1000.0, dsTpPoints=3000.0, dsAtrLen=14, dsSlAtr=1.0, dsTpR=3.0,
    dsUseTrail=False, dsTrActPts=2000.0, dsTrPts=500.0, dsTrActAtr=2.0, dsTrDstAtr=0.5, dsTimeStop=0,
    dsQtyMode='Risk %', dsFixedQty=1.0, dsRiskPct=0.5, dsMaxQty=50.0, dsQtyStep=0.001, dsCapMargin=True,
    dsMarginPct=1.0,
    path='tv', cost='tv', inv=False,
)
# SIGNAL inputs: the filter block's trading inputs (fgf.DEFAULTS, fgfOn = true) + the window
PREP_DEFAULTS = dict(fgf.DEFAULTS)
PREP_DEFAULTS.update(start=None, end=None)
DEFAULTS = dict(PREP_DEFAULTS)
DEFAULTS.update(SIM_DEFAULTS)
_DISPLAY = set(fgf._DISPLAY_KEYS)

_OPTS = {'dsTrigger': TRIGGERS, 'dsDirection': DIRECTIONS, 'dsSides': SIDES, 'dsExitMode': EXIT_MODES,
         'dsQtyMode': QTY_MODES, 'path': ('tv', 'mag'), 'cost': tuple(COSTS)}
_MINV = {'dsSlPoints': 0.0, 'dsTpPoints': 0.0, 'dsAtrLen': 1, 'dsSlAtr': 0.01, 'dsTpR': 0.0, 'dsTrActPts': 0.0,
         'dsTrPts': 1.0, 'dsTrActAtr': 0.0, 'dsTrDstAtr': 0.005, 'dsTimeStop': 0, 'dsFixedQty': 0.0,
         'dsRiskPct': 0.0, 'dsMaxQty': 0.0, 'dsQtyStep': 0.000001, 'dsMarginPct': 0.0}
_BOOLS = ('dsZoneExit', 'dsReverse', 'dsUseTrail', 'dsCapMargin', 'inv')


def _resolve_dir(Q, given):
    """inv <-> dsDirection. `given` = the dict the caller passed (only its keys count)."""
    hi, hd = 'inv' in given, 'dsDirection' in given
    if hd and given['dsDirection'] not in DIRECTIONS:
        raise ValueError(f"dsDirection={given['dsDirection']!r} is not one of {DIRECTIONS}")
    if hi and hd and bool(given['inv']) != (given['dsDirection'] == 'Inverted'):
        raise ValueError(f"inv={given['inv']!r} disagrees with dsDirection={given['dsDirection']!r}")
    if hi:
        Q['inv'] = bool(given['inv'])
        Q['dsDirection'] = 'Inverted' if Q['inv'] else 'Follow the filter'
    elif hd:
        Q['dsDirection'] = given['dsDirection']
        Q['inv'] = given['dsDirection'] == 'Inverted'


def _check_sim(Q):
    for k, opts in _OPTS.items():
        if Q[k] not in opts:
            raise ValueError(f'{k}={Q[k]!r} is not one of {opts}')
    for k, mv in _MINV.items():
        v = Q[k]
        if isinstance(v, bool) or not isinstance(v, (int, float, np.integer, np.floating)) or not np.isfinite(v):
            raise ValueError(f'{k}={v!r} is not a number')
        if v < mv:
            raise ValueError(f'{k}={v!r} is below the Pine minval {mv}')
    for k in ('dsAtrLen', 'dsTimeStop'):
        if int(Q[k]) != Q[k]:
            raise ValueError(f'{k}={Q[k]!r} must be an integer (input.int)')
        Q[k] = int(Q[k])
    for k in _BOOLS:
        Q[k] = bool(Q[k])
    if Q['inv'] != (Q['dsDirection'] == 'Inverted'):
        raise ValueError('inv and dsDirection disagree')


# ----------------------------------------------------------------------------------------------
# prepare
# ----------------------------------------------------------------------------------------------
_ATR_FULL = {}


def _atr_full(pair, tf, length):
    key = (pair, tf, int(length))
    if key not in _ATR_FULL:
        b = fgf._bars(pair, tf)
        _ATR_FULL[key] = fgf._atr(b['high'], b['low'], b['close'], int(length))   # ta.atr from row 0 of the file
    return _ATR_FULL[key]


def atr_window(P, length):
    """dsAtr = ta.atr(dsAtrLen) of the chart, window slice (cached in P)."""
    length = int(length)
    if length not in P['atr']:
        P['atr'][length] = np.ascontiguousarray(_atr_full(P['pair'], P['tf'], length)[P['w0']:P['w1']])
    return P['atr'][length]


def prepare(pair, chart_tf, params=None):
    """Window, bars, the filter outputs (one fgf call, one row before the window for the [1] values), the
    trigger and keep series of L749-765 for the three triggers. Nothing here depends on a ds* input; the
    ds* keys given here become simulate()'s defaults."""
    params = dict(params or {})
    for k in params:
        if k not in DEFAULTS and k not in _DISPLAY:
            raise ValueError(f'unknown param {k!r}')
    prep = dict(PREP_DEFAULTS)
    sim = dict(SIM_DEFAULTS)
    for k, v in params.items():
        if k in PREP_DEFAULTS:
            prep[k] = v
        elif k in SIM_DEFAULTS and k not in ('inv', 'dsDirection'):
            sim[k] = v
    _resolve_dir(sim, params)
    _check_sim(sim)
    fgfp = {k: prep[k] for k in fgf.DEFAULTS}
    fgfp = fgf._params(fgfp)                          # the filter's own validation
    on = bool(fgfp['fgfOn'])
    tf = str(chart_tf)
    b = fgf._bars(pair, tf)
    s0, e0 = WINDOWS[pair]
    start = int(prep['start']) if prep['start'] is not None else s0
    end = int(prep['end']) if prep['end'] is not None else e0
    tcf = b['t_close']
    w0 = int(np.searchsorted(tcf, start, side='left'))
    w1 = int(np.searchsorted(tcf, end, side='right'))
    n = w1 - w0
    if n <= 0:
        raise ValueError('empty window')
    sl = slice(w0, w1)

    if on:
        if w0 >= 1:
            F = fgf.fgf_permissions(pair, tf, int(tcf[w0 - 1]), end, fgfp)
            if F.index[0] != w0 - 1 or len(F) != n + 1:
                raise RuntimeError('filter rows do not match the window')
            col = lambda k: F[k].to_numpy()       # noqa: E731
            bo, so_, op, sk = (col('buyOk').astype(bool), col('sellOk').astype(bool), col('open_').astype(bool),
                               col('sigOk').astype(bool))
            sd, ns = col('sigDir').astype(np.int64), col('newSig').astype(bool)
            lvl = col('level').astype(np.float64)
        else:
            F = fgf.fgf_permissions(pair, tf, start, end, fgfp)
            if F.index[0] != w0 or len(F) != n:
                raise RuntimeError('filter rows do not match the window')
            # F13: bool[1] on the first bar of the data is false (v6); prepend a false row
            pre = lambda a, z: np.concatenate([[z], a])   # noqa: E731
            bo = pre(F['buyOk'].to_numpy(bool), False)
            so_ = pre(F['sellOk'].to_numpy(bool), False)
            op = pre(F['open_'].to_numpy(bool), False)
            sk = pre(F['sigOk'].to_numpy(bool), False)
            sd = pre(F['sigDir'].to_numpy(np.int64), 0)
            ns = pre(F['newSig'].to_numpy(bool), False)
            lvl = pre(F['level'].to_numpy(np.float64), np.nan)
        cur, prv = slice(1, None), slice(0, -1)
        # L749-757, literally (fgfOn is true here)
        buy_edge = bo[cur] & ~bo[prv]                                  # dsBuyEdge
        sell_edge = so_[cur] & ~so_[prv]                               # dsSellEdge
        sig_ok_now = op & sk                                           # dsSigOkNow
        conf_b_all = sig_ok_now & (sd > 0) & bo                        # dsConfBuy
        conf_s_all = sig_ok_now & (sd < 0) & so_                       # dsConfSell
        conf_edge_b = conf_b_all[cur] & (~conf_b_all[prv] | ns[cur])   # dsConfEdgeB
        conf_edge_s = conf_s_all[cur] & (~conf_s_all[prv] | ns[cur])   # dsConfEdgeS
        new_buy = ns[cur] & (sd[cur] > 0)                              # dsNewBuy
        new_sell = ns[cur] & (sd[cur] < 0)                             # dsNewSell
        buy_ok, sell_ok = bo[cur], so_[cur]
        conf_buy, conf_sell = conf_b_all[cur], conf_s_all[cur]
        sig_dir, new_sig = sd[cur], ns[cur]
        diag = dict(open_=op[cur], sigOk=sk[cur], level=lvl[cur])
        # the asserts of the brief, section 4
        for nm, a_, b_ in (('Zone start', buy_edge, sell_edge), ('Signal confirmed', conf_edge_b, conf_edge_s),
                           ('New signal', new_buy, new_sell)):
            if (a_ & b_).any():
                raise AssertionError(f'{nm}: rawBuy and rawSell both true on {int((a_ & b_).sum())} bars')
        if (buy_ok & sell_ok).any():
            raise AssertionError('buyOk and sellOk both true')
        if not np.array_equal(conf_buy, buy_ok & (sig_dir > 0)) or not np.array_equal(conf_sell, sell_ok & (sig_dir < 0)):
            raise AssertionError('confBuy / confSell identity does not hold')
    else:
        F = None
        z = np.zeros(n, np.bool_)
        buy_edge = sell_edge = conf_edge_b = conf_edge_s = new_buy = new_sell = conf_buy = conf_sell = z
        buy_ok = np.ones(n, np.bool_)          # fgfBuyOk = not fgfOn or ... : true; never read (no trade)
        sell_ok = np.ones(n, np.bool_)
        sig_dir = np.zeros(n, np.int64)
        new_sig = z
        diag = dict(open_=z, sigOk=z, level=np.full(n, np.nan))

    tc = np.ascontiguousarray(tcf[sl])
    mid = start + (end - start) // 2
    cc = lambda a: np.ascontiguousarray(a, dtype=np.bool_)   # noqa: E731
    P = dict(pair=pair, tf=tf, start=start, end=end, mid=mid,
             mid_j=int(np.searchsorted(tc, mid, side='right')) - 1,
             w0=w0, w1=w1, n=n,
             o=np.ascontiguousarray(b['open'][sl]), h=np.ascontiguousarray(b['high'][sl]),
             l=np.ascontiguousarray(b['low'][sl]), c=np.ascontiguousarray(b['close'][sl]),
             t_open=np.ascontiguousarray(b['t_open'][sl]), t_close=tc,
             buyOk=cc(buy_ok), sellOk=cc(sell_ok), confBuy=cc(conf_buy), confSell=cc(conf_sell),
             buyEdge=cc(buy_edge), sellEdge=cc(sell_edge), confEdgeB=cc(conf_edge_b), confEdgeS=cc(conf_edge_s),
             newBuy=cc(new_buy), newSell=cc(new_sell),
             sigDir=np.ascontiguousarray(sig_dir), newSig=cc(new_sig),
             diag=diag, atr={}, prep=prep, fgfp=fgfp, sim=sim, sub=None)
    del F           # the full filter frame is not kept (memory: 1-minute charts); diag keeps open_ / sigOk / level
    P['counts'] = dict(trig_zone_buy=int(P['buyEdge'].sum()), trig_zone_sell=int(P['sellEdge'].sum()),
                       trig_conf_buy=int(P['confEdgeB'].sum()), trig_conf_sell=int(P['confEdgeS'].sum()),
                       trig_new_buy=int(P['newBuy'].sum()), trig_new_sell=int(P['newSell'].sum()))
    atr_window(P, sim['dsAtrLen'])
    return P


def trigger_arrays(P, trigger):
    """(rawBuy, rawSell, keepBuy, keepSell) for dsTrigger (L758-759, L764-765)."""
    if trigger == 'Zone start':
        return P['buyEdge'], P['sellEdge'], P['buyOk'], P['sellOk']
    if trigger == 'Signal confirmed':
        return P['confEdgeB'], P['confEdgeS'], P['confBuy'], P['confSell']
    if trigger == 'New signal':
        return P['newBuy'], P['newSell'], P['buyOk'], P['sellOk']
    raise ValueError(trigger)


# ----------------------------------------------------------------------------------------------
# the 1-minute sub-bars of the chart bars (path 'mag')
# ----------------------------------------------------------------------------------------------
def sub_bars(pair, chart_tf, w0, w1, check=True):
    """The 1-minute sub-bars of the chart rows w0..w1-1 of data/<pair>_<chart_tf>.parquet: the rows of
    data/<pair>_1.parquet with t_open in [chart t_open, chart t_close). Returns (ptr, o, h, l, c, t_open): ptr
    int64 (n + 1); the sub-bars of window bar k are the rows [ptr[k], ptr[k+1]) of the five arrays. With check,
    every chart bar has at least one sub-bar, no two chart bars share one, and the chart bar's OHLC equals the
    sub-bars' first open / highest high / lowest low / last close (build_bars.py built the chart bars from
    them), so the market fills at the chart open are the first sub-bar's open."""
    b = fgf._bars(pair, str(chart_tf))
    m = fgf._bars(pair, '1')
    bo = b['t_open'][w0:w1]
    bc = b['t_close'][w0:w1]
    s = np.searchsorted(m['t_open'], bo, side='left')
    e = np.searchsorted(m['t_open'], bc, side='left')
    ln = (e - s).astype(np.int64)
    ptr = np.zeros(len(bo) + 1, np.int64)
    np.cumsum(ln, out=ptr[1:])
    if len(bo) and (ln <= 0).any():
        raise ValueError('%s %s: %d chart bars without 1-minute sub-bars' % (pair, chart_tf, int((ln <= 0).sum())))
    if len(bo) > 1 and (s[1:] < e[:-1]).any():
        raise ValueError('%s %s: chart bars share 1-minute sub-bars' % (pair, chart_tf))
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


_SUB = {}     # sub-bar tables keyed (pair, tf, w0, w1): one per cell and window, shared by every prepare() of it


def get_sub(P):
    """The sub-bar table of P's window: built and checked once per (pair, tf, window), kept in P['sub']."""
    if P.get('sub') is None:
        key = (P['pair'], P['tf'], int(P['w0']), int(P['w1']))
        if key not in _SUB:
            _SUB[key] = sub_bars(P['pair'], P['tf'], P['w0'], P['w1'])
        P['sub'] = _SUB[key]
    return P['sub']


def fake_sub_bars(P):
    """One sub-bar per chart bar, equal to the bar (tests: 'mag' on it == 'tv')."""
    n = P['n']
    return (np.arange(n + 1, dtype=np.int64), P['o'], P['h'], P['l'], P['c'], P['t_open'])


def clear_cache():
    _SUB.clear()
    _ATR_FULL.clear()
    fgf._FILTER.clear()


_NO_SUB = (np.zeros(1, np.int64), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0))


# ----------------------------------------------------------------------------------------------
# the kernel
# ----------------------------------------------------------------------------------------------
@njit(cache=True)
def _walk(v0, v1, v2, v3, armed, best, A, off, SL, TP, has_tr, has_sl, has_tp):
    """Open (A3) + the three legs (B) of one path in LONG space (a short's prices negated).
    Returns (kind, fill price in long space, armed, best); kind 0 = no exit."""
    sv = SL if has_sl else NEG
    ts = (best - off) if (has_tr and armed) else NEG
    stop = ts if ts > sv else sv
    # A3: a level already passed at the open fills at the open
    if v0 <= stop:
        return (K_TRAIL if ts >= sv else K_SL), v0, armed, best
    if has_tp and v0 >= TP:
        return K_TP, v0, armed, best
    if has_tr:
        if armed:
            if v0 > best:
                best = v0
        elif v0 >= A:
            armed = True
            best = v0
    a = v0
    for s in range(3):
        b = v1 if s == 0 else (v2 if s == 1 else v3)
        if b > a:
            if has_tp and b >= TP:
                return K_TP, (TP if TP > a else a), armed, best
            if has_tr:
                if armed:
                    if b > best:
                        best = b
                elif b >= A:
                    armed = True
                    best = b
        elif b < a:
            ts = (best - off) if (has_tr and armed) else NEG
            stop = ts if ts > sv else sv
            if b <= stop:
                return (K_TRAIL if ts >= sv else K_SL), (stop if stop < a else a), armed, best
        a = b
    return 0, 0.0, armed, best


@njit(cache=True)
def _walk_bar(pos, oj, hj, lj, cj, armed, best, A, off, SL, TP, has_tr, has_sl, has_tp):
    """A3 + B of one bar (a chart bar on 'tv', a 1-minute sub-bar on 'mag') for the trade of side pos, in real
    prices: the rule-4 path (O-H-L-C when the high is nearer the open, else O-L-H-C; a tie goes low first), a
    short walked in long space. Returns (kind, fill price, armed, best)."""
    if (hj - oj) < (oj - lj):
        f1 = hj
        f2 = lj
    else:
        f1 = lj
        f2 = hj
    if pos > 0:
        return _walk(oj, f1, f2, cj, armed, best, A, off, SL, TP, has_tr, has_sl, has_tp)
    k, px, armed, bneg = _walk(-oj, -f1, -f2, -cj, armed, -best, -A, off, -SL, -TP, has_tr, has_sl, has_tp)
    return k, -px, armed, -bneg


@njit(cache=True)
def _decide(j, pos, prev_pos, entry_bar, equity, cj, a, rbj, rsj, kbj, ksj,
            inv, allow_long, allow_short, use_zone_exit, reverse, points,
            sl_pts, tp_pts, sl_atr, tp_r, tr_act_pts, tr_pts, tr_act_atr, tr_dst_atr, time_stop,
            fixed_mode, fixed_qty, risk_pct, max_qty, qty_step, cap_margin, margin_pct, mintick, pointvalue):
    """The script run at the close of bar j (L728-813), on the position after the bar's fills and exits.
    pos: -1 / 0 / +1; prev_pos: strategy.position_size[1] sign; entry_bar: var dsEntryBar (-1 = na).
    Returns (od, osig, q, slT, tpT, actT, dstT, capf, close_kind, entry_bar, zero_flag, stop_dist)."""
    # ---- exit geometry (L728-736)
    if points:
        slT = sl_pts
        tpT = tp_pts
        actT = tr_act_pts
        dstT = tr_pts
    else:
        slT = sl_atr * a / mintick
        if slT != slT:
            slT = 0.0
        tpT = slT * tp_r
        actT = tr_act_atr * a / mintick
        if actT != actT:
            actT = 0.0
        dstT = tr_dst_atr * a / mintick
        if dstT != dstT:
            dstT = 0.0
    if dstT < 1.0:
        dstT = 1.0
    stop_dist = slT * mintick
    # ---- bars in trade (L771-777)
    if pos != 0 and (prev_pos == 0 or (pos > 0) != (prev_pos > 0)):
        entry_bar = j
    if pos == 0:
        entry_bar = -1
    time_up = False
    if pos != 0 and entry_bar >= 0:
        bars_in = j - entry_bar
        time_up = time_stop > 0 and bars_in >= time_stop
    # ---- dsQty(dsStopDist) (L738-746)
    q = fixed_qty
    if not fixed_mode:
        stop_cash = stop_dist * pointvalue
        q = equity * risk_pct / 100.0 / stop_cash if stop_cash > 0 else 0.0
    q0 = q
    q = min(q, max_qty)
    q1 = q
    if cap_margin and margin_pct > 0:
        q = min(q, equity / (cj * pointvalue * margin_pct / 100.0))
    q2 = q
    q = np.floor(q / qty_step + 1e-9) * qty_step
    capf = 2 if q2 < q1 else (1 if q1 < q0 else 0)
    qty_ok = q > 0 and (fixed_mode or stop_dist > 0) and (points or not (a != a))
    # ---- decisions (L760-768, L782-786)
    go_long = (rsj if inv else rbj) and allow_long
    go_short = (rbj if inv else rsj) and allow_short
    long_keep = ksj if inv else kbj
    short_keep = kbj if inv else ksj
    enter_long = go_long and qty_ok and (pos == 0 or (pos < 0 and reverse))
    enter_short = go_short and qty_ok and (pos == 0 or (pos > 0 and reverse)) and not enter_long
    want = (go_long and (pos == 0 or (pos < 0 and reverse))) or (go_short and (pos == 0 or (pos > 0 and reverse)))
    zero_flag = want and not qty_ok
    od = 0
    osig = 0
    ck = 0
    if enter_long:
        od = 1
        osig = -1 if inv else 1
    elif enter_short:
        od = -1
        osig = 1 if inv else -1
    else:
        # L805-813
        opp = False
        zone = False
        if pos > 0:
            opp = rbj if inv else rsj
            zone = use_zone_exit and not long_keep
        elif pos < 0:
            opp = rsj if inv else rbj
            zone = use_zone_exit and not short_keep
        if pos != 0 and (opp or zone or time_up):
            ck = K_OPP if opp else (K_ZONE if zone else K_TIME)
    return od, osig, q, slT, tpT, actT, dstT, capf, ck, entry_bar, zero_flag, stop_dist


# trade row columns (float64 matrix)
_T_COLS = ('dir', 'sig', 'ek', 'xk', 'epx', 'qty', 'xpx', 'kind', 'gross', 'cost', 'eqb', 'sld', 'slpx', 'tppx',
           'rev', 'capf', 'slT', 'tpT')
_NT = len(_T_COLS)


@njit(cache=True)
def _kernel(o, h, l, c, rb, rs, kb, ks, atr,
            inv, allow_long, allow_short, use_zone_exit, reverse, points,
            sl_pts, tp_pts, sl_atr, tp_r, use_trail, tr_act_pts, tr_pts, tr_act_atr, tr_dst_atr, time_stop,
            fixed_mode, fixed_qty, risk_pct, max_qty, qty_step, cap_margin, margin_pct,
            mintick, pointvalue, init, c_fix, c_pct, mid_j, cap, full, mag, ptr, sb_o, sb_h, sb_l, sb_c):
    """mag: the bracket walks the sub-bars [ptr[j], ptr[j+1]) of chart bar j (sb_o / sb_h / sb_l / sb_c)
    instead of the chart bar; everything else is the same."""
    n = o.shape[0]
    T = np.zeros((cap, 18))
    nt = 0
    m = n if full else 1
    eq_arr = np.zeros(m)
    pos_arr = np.zeros(m, np.int8)
    ord_arr = np.zeros(m, np.int8)
    ck_arr = np.zeros(m, np.int8)
    q_arr = np.zeros(m)

    cash = init
    # open trade
    pos = 0
    qty = 0.0
    e = 0.0
    ek = -1
    tsig = 0
    t_eqb = 0.0
    t_ecost = 0.0
    t_sld = 0.0
    t_slT = 0.0
    t_tpT = 0.0
    t_rev = 0
    t_capf = 0
    has_sl = False
    has_tp = False
    has_tr = False
    SL = np.nan
    TP = np.nan
    A = 0.0
    off = 0.0
    armed = False
    best = 0.0
    # pending orders (placed by the previous run)
    o_d = 0
    o_sig = 0
    o_q = 0.0
    o_slT = 0.0
    o_tpT = 0.0
    o_actT = 0.0
    o_dstT = 0.0
    o_capf = 0
    o_sld = 0.0
    close_req = 0
    # script state
    prev_pos = 0
    entry_bar = -1
    # counters
    n_pos = 0
    raw_l = 0
    raw_s = 0
    taken_l = 0
    taken_s = 0
    zero_qty = 0
    err = 0
    dd_pk = init
    dd_rel = 0.0
    dd_abs = 0.0
    eq_mid = init
    eq_last = init

    for j in range(n):
        oj = o[j]
        # ---------------- A. the open: the script's market order first (F6)
        if close_req != 0 and o_d != 0:
            err += 1
        if close_req != 0:
            if pos == 0:
                err += 1
            else:
                xc = qty * (c_fix + c_pct * oj)
                gross = pos * qty * (oj - e) * pointvalue
                T[nt, 0] = pos; T[nt, 1] = tsig; T[nt, 2] = ek; T[nt, 3] = j; T[nt, 4] = e; T[nt, 5] = qty
                T[nt, 6] = oj; T[nt, 7] = close_req; T[nt, 8] = gross; T[nt, 9] = t_ecost + xc; T[nt, 10] = t_eqb
                T[nt, 11] = t_sld; T[nt, 12] = SL; T[nt, 13] = TP; T[nt, 14] = t_rev; T[nt, 15] = t_capf
                T[nt, 16] = t_slT; T[nt, 17] = t_tpT
                nt += 1
                cash += gross - xc
                pos = 0
            close_req = 0
        if o_d != 0:
            rev_now = 0
            if pos != 0:
                if pos != -o_d:
                    err += 1
                xc = qty * (c_fix + c_pct * oj)
                gross = pos * qty * (oj - e) * pointvalue
                T[nt, 0] = pos; T[nt, 1] = tsig; T[nt, 2] = ek; T[nt, 3] = j; T[nt, 4] = e; T[nt, 5] = qty
                T[nt, 6] = oj; T[nt, 7] = K_REV; T[nt, 8] = gross; T[nt, 9] = t_ecost + xc; T[nt, 10] = t_eqb
                T[nt, 11] = t_sld; T[nt, 12] = SL; T[nt, 13] = TP; T[nt, 14] = t_rev; T[nt, 15] = t_capf
                T[nt, 16] = t_slT; T[nt, 17] = t_tpT
                nt += 1
                cash += gross - xc
                pos = 0
                rev_now = 1
            # open the order's trade at the open, with its own qty and ticks (6.2)
            t_eqb = cash
            t_ecost = o_q * (c_fix + c_pct * oj)
            cash -= t_ecost
            pos = o_d
            qty = o_q
            e = oj
            ek = j
            tsig = o_sig
            t_sld = o_sld
            t_slT = o_slT
            t_tpT = o_tpT
            t_rev = rev_now
            t_capf = o_capf
            has_sl = o_slT > 0
            has_tp = o_tpT > 0
            SL = e - pos * (o_slT * mintick) if has_sl else np.nan
            TP = e + pos * (o_tpT * mintick) if has_tp else np.nan
            has_tr = use_trail
            A = e + pos * (o_actT * mintick)
            off = o_dstT * mintick
            armed = o_actT <= 0
            best = e
            o_d = 0
        # ---------------- A3 + B. the bracket along the bar's path (rule 4); 'mag': along the sub-bars
        if pos != 0:
            k = 0
            px = 0.0
            if mag:
                # sub-bar ptr[j] opens at the chart open (sub_bars checks it): for a trade filled at this open
                # its gap test is a no-op, as on 'tv'; a level crossed between two sub-bars fills at the open
                # of the later one (its gap test)
                for mm in range(ptr[j], ptr[j + 1]):
                    k, px, armed, best = _walk_bar(pos, sb_o[mm], sb_h[mm], sb_l[mm], sb_c[mm], armed, best, A,
                                                   off, SL, TP, has_tr, has_sl, has_tp)
                    if k != 0:
                        break
            else:
                k, px, armed, best = _walk_bar(pos, oj, h[j], l[j], c[j], armed, best, A, off, SL, TP,
                                               has_tr, has_sl, has_tp)
            if k != 0:
                xc = qty * (c_fix + c_pct * px)
                gross = pos * qty * (px - e) * pointvalue
                T[nt, 0] = pos; T[nt, 1] = tsig; T[nt, 2] = ek; T[nt, 3] = j; T[nt, 4] = e; T[nt, 5] = qty
                T[nt, 6] = px; T[nt, 7] = k; T[nt, 8] = gross; T[nt, 9] = t_ecost + xc; T[nt, 10] = t_eqb
                T[nt, 11] = t_sld; T[nt, 12] = SL; T[nt, 13] = TP; T[nt, 14] = t_rev; T[nt, 15] = t_capf
                T[nt, 16] = t_slT; T[nt, 17] = t_tpT
                nt += 1
                cash += gross - xc
                pos = 0
        # ---------------- C. the script run at the close
        cj = c[j]
        equity = cash + pos * qty * (cj - e) * pointvalue if pos != 0 else cash
        rbj = rb[j]
        rsj = rs[j]
        if rbj:
            raw_l += 1
        if rsj:
            raw_s += 1
        od, osig, q, slT, tpT, actT, dstT, capf, ck, entry_bar, zf, sdist = _decide(
            j, pos, prev_pos, entry_bar, equity, cj, atr[j], rbj, rsj, kb[j], ks[j],
            inv, allow_long, allow_short, use_zone_exit, reverse, points,
            sl_pts, tp_pts, sl_atr, tp_r, tr_act_pts, tr_pts, tr_act_atr, tr_dst_atr, time_stop,
            fixed_mode, fixed_qty, risk_pct, max_qty, qty_step, cap_margin, margin_pct, mintick, pointvalue)
        if pos != 0 and entry_bar != ek:
            err += 1
        if zf:
            zero_qty += 1
        if od != 0:
            o_d = od
            o_sig = osig
            o_q = q
            o_slT = slT
            o_tpT = tpT
            o_actT = actT
            o_dstT = dstT
            o_capf = capf
            o_sld = sdist
            if osig > 0:
                taken_l += 1
            else:
                taken_s += 1
        elif ck != 0:
            close_req = ck
        prev_pos = pos
        # ---------------- D. bar-close equity
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
            ord_arr[j] = od
            ck_arr[j] = ck
            q_arr[j] = q

    unfilled = 1 if o_d != 0 else 0
    if n > 0:
        if pos != 0:
            k = n - 1
            px = c[k]
            xc = qty * (c_fix + c_pct * px)
            gross = pos * qty * (px - e) * pointvalue
            T[nt, 0] = pos; T[nt, 1] = tsig; T[nt, 2] = ek; T[nt, 3] = k; T[nt, 4] = e; T[nt, 5] = qty
            T[nt, 6] = px; T[nt, 7] = K_END; T[nt, 8] = gross; T[nt, 9] = t_ecost + xc; T[nt, 10] = t_eqb
            T[nt, 11] = t_sld; T[nt, 12] = SL; T[nt, 13] = TP; T[nt, 14] = t_rev; T[nt, 15] = t_capf
            T[nt, 16] = t_slT; T[nt, 17] = t_tpT
            nt += 1
            cash += gross - xc
            pos = 0
            eq_last = cash
            if full:
                eq_arr[k] = cash
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
    stats = np.array([eq_last, eq_mid, dd_rel, dd_abs, float(n_pos), float(raw_l), float(raw_s),
                      float(taken_l), float(taken_s), float(zero_qty), float(unfilled), float(err), cash])
    return T[:nt].copy(), stats, eq_arr, pos_arr, ord_arr, ck_arr, q_arr


# ----------------------------------------------------------------------------------------------
# public interface
# ----------------------------------------------------------------------------------------------
def kernel_args(Q):
    """The scalar inputs of _kernel / _decide from a resolved parameter dict."""
    return (bool(Q['inv']), Q['dsSides'] != 'Short only', Q['dsSides'] != 'Long only',
            bool(Q['dsZoneExit']) and Q['dsTrigger'] != 'New signal', bool(Q['dsReverse']),
            Q['dsExitMode'] == 'Points',
            float(Q['dsSlPoints']), float(Q['dsTpPoints']), float(Q['dsSlAtr']), float(Q['dsTpR']),
            bool(Q['dsUseTrail']), float(Q['dsTrActPts']), float(Q['dsTrPts']), float(Q['dsTrActAtr']),
            float(Q['dsTrDstAtr']), int(Q['dsTimeStop']),
            Q['dsQtyMode'] == 'Fixed', float(Q['dsFixedQty']), float(Q['dsRiskPct']), float(Q['dsMaxQty']),
            float(Q['dsQtyStep']), bool(Q['dsCapMargin']), float(Q['dsMarginPct']))


def run_arrays(o, h, l, c, rb, rs, kb, ks, atr, Q, pair='XAU', mid_j=-1, full=False, sub=None):
    """The kernel on arbitrary arrays (also used by the injected-array tests). Q: resolved params. sub: the
    sub-bar table (ptr, o, h, l, c[, t]) of path 'mag' (required when Q['path'] == 'mag')."""
    c_fix, c_pct = COSTS[Q['cost']][pair]
    a = kernel_args(Q)
    cap = int(np.count_nonzero(rb) + np.count_nonzero(rs)) + 4
    bb = lambda x: np.ascontiguousarray(x, dtype=np.bool_)   # noqa: E731
    ff = lambda x: np.ascontiguousarray(x, dtype=np.float64)  # noqa: E731
    mag = Q['path'] == 'mag'
    if mag:
        if sub is None:
            raise ValueError("path 'mag' needs the sub-bar table")
        ptr = np.ascontiguousarray(sub[0], dtype=np.int64)
        if len(ptr) != len(o) + 1 or (np.diff(ptr) <= 0).any() or ptr[0] != 0 or ptr[-1] != len(sub[1]):
            raise ValueError('sub-bar table does not match the chart bars')
        S = (ptr, ff(sub[1]), ff(sub[2]), ff(sub[3]), ff(sub[4]))
    else:
        S = _NO_SUB
    out = _kernel(ff(o), ff(h), ff(l), ff(c), bb(rb), bb(rs), bb(kb), bb(ks), ff(atr),
                  a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], a[9], a[10], a[11], a[12], a[13], a[14],
                  a[15], a[16], a[17], a[18], a[19], a[20], a[21], a[22],
                  MINTICK, POINTVALUE, INITIAL_CAPITAL, c_fix, c_pct, int(mid_j), cap, bool(full),
                  mag, S[0], S[1], S[2], S[3], S[4])
    T, stats, eq, pos, od, ck, q = out
    if stats[11] != 0:
        raise AssertionError(f'kernel invariant violated {int(stats[11])} times (one fill per open, reversal '
                             f'meets the opposite side, entryBar == entry_bar)')
    R = {k: T[:, i] for i, k in enumerate(_T_COLS)}
    R['stats'] = stats
    if full:
        R.update(eq=eq, pos=pos, ord=od, ck=ck, q=q)
    R['Q'] = Q
    return R


def resolve(P, x=None):
    """simulate()'s parameter dict: prepare()'s ds* defaults overridden by x (3.2 keys only)."""
    Q = dict(P['sim'])
    x = dict(x or {})
    for k, v in x.items():
        if k in _DISPLAY:
            continue
        if k in PREP_DEFAULTS:
            pv = P['prep'][k]
            if not (v == pv or (isinstance(v, str) and isinstance(pv, str) and v.strip() == pv.strip())):
                raise ValueError(f'{k!r} is a prepare() (signal) input: {v!r} != {pv!r}')
            continue
        if k not in SIM_DEFAULTS:
            raise ValueError(f'unknown param {k!r}')
        if k not in ('inv', 'dsDirection'):
            Q[k] = v
    _resolve_dir(Q, x)
    _check_sim(Q)
    return Q


def simulate(P, x=None, full=False, sub=None):
    """x: order / exit inputs + inv / path / cost. sub: replaces the 1-minute sub-bars of path 'mag'."""
    Q = resolve(P, x)
    rb, rs, kb, ks = trigger_arrays(P, Q['dsTrigger'])
    atr = atr_window(P, Q['dsAtrLen'])
    S = None
    if Q['path'] == 'mag':
        S = sub if sub is not None else get_sub(P)
    return run_arrays(P['o'], P['h'], P['l'], P['c'], rb, rs, kb, ks, atr, Q, P['pair'], P['mid_j'], full, S)


def trades(P, R):
    w0 = P['w0']
    ek = R['ek'].astype(np.int64)
    xk = R['xk'].astype(np.int64)
    kind = R['kind'].astype(np.int64)
    qty = R['qty']
    pnl = R['gross'] - R['cost']
    sld = R['sld']
    with np.errstate(divide='ignore', invalid='ignore'):
        r_mult = np.where(sld > 0, pnl / (sld * qty), np.nan)
    return pd.DataFrame({
        'dir': R['dir'].astype(np.int64),
        'sig': R['sig'].astype(np.int64),
        'sig_bar': ek - 1 + w0,
        'entry_bar': ek + w0,
        'exit_bar': xk + w0,
        'entry_time': P['t_open'][ek],
        'exit_time': np.where(kind == K_END, P['t_close'][xk], P['t_open'][xk]),
        'entry_px': R['epx'],
        'qty': qty,
        'exit_px': R['xpx'],
        'exit_kind': [KINDS[k] for k in kind],
        'pnl': pnl,
        'pnl_gross': R['gross'],
        'costs': R['cost'],
        'eq_before': R['eqb'],
        'sl_dist': sld,
        'sl_px': R['slpx'],
        'tp_px': R['tppx'],
        'r_mult': r_mult,
        'rev': R['rev'].astype(bool),
        'capf': R['capf'].astype(np.int64),
        'sl_ticks': R['slT'],
        'tp_ticks': R['tpT'],
    })


def summary(P, R):
    init = INITIAL_CAPITAL
    st = R['stats']
    pnl = R['gross'] - R['cost']
    nt = len(pnl)
    final = float(st[0])
    eq_mid = float(st[1])
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    d = R['dir']
    kind = R['kind'].astype(np.int64)
    kc = np.bincount(kind, minlength=len(KINDS)) if nt else np.zeros(len(KINDS), np.int64)
    ek = R['ek'].astype(np.int64)
    xk = R['xk'].astype(np.int64)
    first = P['t_open'][ek] <= P['mid'] if nt else np.zeros(0, bool)
    eqb = R['eqb']
    g = 1.0 + pnl / eqb if nt else np.zeros(0)
    sld = R['sld']
    with np.errstate(divide='ignore', invalid='ignore'):
        rm = np.where(sld > 0, pnl / (sld * R['qty']), np.nan)
    capf = R['capf'].astype(np.int64)
    out = dict(
        start=int(P['start']), end=int(P['end']), bars=int(P['n']),
        trades=nt,
        net_pct=(final - init) / init * 100,
        pf=(gp / gl) if gl > 0 else (np.inf if gp > 0 else np.nan),
        win_pct=float((pnl > 0).mean() * 100) if nt else np.nan,
        max_dd_pct=float(st[2] * 100),
        max_dd_init_pct=float(st[3] / init * 100),
        long=int((d > 0).sum()), short=int((d < 0).sum()),
        raw_long=int(st[5]), raw_short=int(st[6]), blocked_long=0, blocked_short=0,
        half1_pct=(eq_mid - init) / init * 100,
        half2_pct=(final - eq_mid) / init * 100,
        exposure=float(st[4] / P['n']),
        final_equity=final,
    )
    for i, nm in enumerate(KINDS[1:], 1):
        out['exit_' + nm] = int(kc[i])
    out['zero_length'] = int((ek == xk).sum())
    n1 = int(first.sum())
    out.update(h1r_pct=(float(np.prod(g[first])) - 1.0) * 100.0, h2r_pct=(float(np.prod(g[~first])) - 1.0) * 100.0,
               h1_trades=n1, h2_trades=nt - n1,
               avg_bars_held=float((xk - ek).mean()) if nt else np.nan,
               costs=float(R['cost'].sum()))
    out.update(net_r=float(np.nansum(rm)) if nt else 0.0,
               h1_r=float(np.nansum(rm[first])) if nt else 0.0,
               h2_r=float(np.nansum(rm[~first])) if nt else 0.0)
    out.update(P['counts'])
    out.update(taken_long=int(st[7]), taken_short=int(st[8]), orders_placed=int(st[7] + st[8]),
               orders_unfilled_end=int(st[10]), zero_qty=int(st[9]),
               qty_capped_max=int((capf == 1).sum()), qty_capped_margin=int((capf == 2).sum()),
               margin_over=int((R['qty'] * R['epx'] * 0.01 > eqb).sum()) if nt else 0,
               max_notional_x=float((R['qty'] * R['epx'] / eqb).max()) if nt else 0.0)
    return out


def run(pair, chart_tf, params=None):
    params = dict(params or {})
    P = prepare(pair, chart_tf, {k: v for k, v in params.items() if k in PREP_DEFAULTS or k in _DISPLAY})
    x = {k: v for k, v in params.items() if k not in PREP_DEFAULTS and k not in _DISPLAY}
    R = simulate(P, x)
    return trades(P, R), summary(P, R)


def fmt(s):
    return (f"trades={s['trades']} (L {s['long']} / S {s['short']}) net={s['net_pct']:.3f}% pf={s['pf']:.3f} "
            f"win={s['win_pct']:.1f}% dd={s['max_dd_pct']:.2f}% netR={s['net_r']:.1f} "
            f"sl/tp/tr/rev/opp/zone/time/end={s['exit_sl']}/{s['exit_tp']}/{s['exit_trail']}/{s['exit_reverse']}/"
            f"{s['exit_opp']}/{s['exit_zone']}/{s['exit_time']}/{s['exit_end']} raw={s['raw_long']}/{s['raw_short']} "
            f"zero_qty={s['zero_qty']} capped max/margin={s['qty_capped_max']}/{s['qty_capped_margin']}")


if __name__ == '__main__':
    for pair in ('BTC', 'XAU'):
        t0 = _time.time()
        P = prepare(pair, '60')
        t1 = _time.time()
        for path in ('tv', 'mag'):
            for inv in (False, True):
                t2 = _time.time()
                R = simulate(P, {'inv': inv, 'path': path})
                s = summary(P, R)
                print(pair, '60', path, 'inv' if inv else 'normal', fmt(s),
                      f'prepare {t1 - t0:.1f}s simulate {_time.time() - t2:.3f}s', flush=True)
