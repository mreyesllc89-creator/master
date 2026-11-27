"""ApexForge Flow Resonance Strategy + FlashGold Direction Filter (FGF build):
CANONICAL Python replica (a copy of implementation B, apex_b.py, after the
reconciliation in reconcile_apex.md: apex_a.py and apex_b.py agree on 100% of
trades, every column, on BTC / XAU charts 1..240 and six parameter sets),
extended for the trailing sweep (SWEEP_AH_SPEC.md section 2): the optional
trailing take profit of the Pine, the Bar Magnifier path 'mag', the 'stress'
cost mode, the fair halves, and a prepare / simulate split.

Ground truth: /home/user/master/ApexForge_Flow_Resonance_Strategy_FGF.pine
(with "Enable filter" off it trades like ApexForge_Flow_Resonance_Strategy.pine).
Spec: SPEC_AH.md and SWEEP_AH_SPEC.md in this directory. Interpretations:
apex_b_notes.md, and the TRAILING notes below.

    run(pair, chart_tf, params=None) -> (trades: DataFrame, summary: dict)
    S = prepare(pair, chart_tf, params)            signals, gate, brackets: once
    out, summary = simulate(S, exit_params)        one exit setting (fast kernel)
    trades = trades_frame(S, out)

Pipeline
  1. Signals on the chart TF's whole history (numba, one pass): HTF high / low
     ("15", lookahead off = last 15m bar with t_close <= chart t_close), swing
     pivots (ta.pivothigh / ta.pivotlow(zoneLookback, zoneLookback), tie rule
     `pivotTies`), the demand / supply boxes (replaced on each new pivot),
     flow, volume spike, bull / bear resonance.
  2. The filter gate from fgf.fgf_permissions (buyOk / sellOk per chart bar).
  3. The TradingView broker (history, orders fill at the next open,
     strategy.exit brackets checked along the open->high/low->close path, or
     with path 'mag' along the 1-minute sub-bars), bar by bar over the window
     (numba), flat at the window start.

Exit parameters (simulate / run): trailOn, trailAct, trailOff (percent; the Pine
names apxTrailOn / apxTrailAct / apxTrailOff are accepted too), useTarget
(apxUseTarget), blkClose (apxBlkClose), cost ('tv' | 'ours' | 'stress'), path
('tv' | 'mag'), inv (apxInv, Update 1: see INVERTED DIRECTION below). Defaults
(trail off, useTarget True, path 'tv', inv False) = the reconciled replica: every
saved result of run_apex.py is reproduced exactly.

TRAILING (Pine lines "STRATEGY EXECUTION", apxTrail*):
  - On the bar where apxGoLong is true and strategy.position_size <= 0 (the entry
    opens a new trade: flat, or a reversal of a short), the script stores
    apxTrPtsL = max(close * act / 100 / mintick, 0) and apxTrOfsL =
    max(close * off / 100 / mintick, 1) (fractional ticks, NOT rounded); every
    later strategy.exit("Exit Long") (the same-side re-send while long) passes the
    stored values unchanged. Shorts mirrored. Trailing off: na (no trailing).
  - The limit is na only when trailing is on and apxUseTarget is off
    (`apxTrailOn and not apxUseTarget ? na : targetPrice`): with trailing off
    "Keep the target" has no effect.
  - Broker: activation = entry fill price +/- trail_points x mintick; once price
    reaches it the stop = best price since activation -/+ trail_offset x mintick,
    moving only in the trade's favour; filled at the stop, or at the open if a
    (sub-)bar opens beyond it; trail_points 0 = armed at the fill (the fill bar's
    open) with best = the fill price. With the zone stop and the target in the
    same exit, the first level touched along the path wins (on a falling segment
    (long) the higher of the two stops; equal stops are reported as 'trail').
    Arming and trailing-stop touches use a tolerance of 1e-6 tick (as engine.py
    _walk); the zone stop and target keep the exact comparisons of the
    reconciled replica.
  - ASSUMPTION (TradingView's handling cannot be checked here): when a
    same-side signal re-sends the exit, the new stop / limit apply from the next
    bar on, and the trailing state (armed, best price) and distances are kept.
    The state is reset only when a new trade opens.
  - Path 'mag' (Bar Magnifier, 1-minute data): every exit order is evaluated
    along the 1-minute sub-bars of the chart bar (rows of data/<PAIR>_1.parquet
    with t_open in [t_open, t_close) of the chart bar), in time order, each with
    its own open->high/low->close path; the trailing state carries; a level
    crossed between two sub-bars fills at the next sub-bar's open. Entries,
    strategy.close and reversals still fill at the chart bar open (= the first
    sub-bar's open), the script still runs at the chart bar close. Chart "1":
    'mag' == 'tv'. exit_time stays the chart bar's t_open.

INVERTED DIRECTION (Update 1 of the Pine, input apxInv, replica alias `inv`, default False;
INV_BT_SPEC.md, notes in inv_apex_notes.md):
  - An exit-side parameter (simulate / run; prepare() does not depend on it): signals, the
    filter gate and the per-bar zone stop / target arrays stay those of the normal script.
  - Only the script step of the broker changes, exactly as the Pine: the script decides on
    apxPosN (the MIRROR of the real position when inverted) and sends every order on the
    other side: a BUY signal the gate allows places strategy.entry("Apex Short", short), a
    SELL signal "Apex Long"; strategy.close of the blocked-opposite rule names apxIdBuy /
    apxIdSell (the trade that kind of signal opened); the same-kind re-send re-sets
    apxExBuy / apxExSell ("Exit Short" for the BUY signal's short) with the bracket mirrored
    about the signal close (stop = 2.0 * close - stopPrice, limit = 2.0 * close -
    targetPrice, the Pine's own float expressions); the trailing ticks apxTrPtsL / apxTrOfsL
    stay per SIGNAL kind (fixed when apxPosN <= 0) and are passed to the exit of the trade
    really open. The broker itself (fills, pyramiding, reversal, exits along the path, costs,
    sizing) is untouched and works on REAL sides: trades report the real `dir`, summary
    long / short count real sides; raw / blocked counts keep the SIGNAL's side (the FGD rows).
  - inv False: the script step is the previous one (codes 1 / -1 / 2 / -2, Exit Long from
    the BUY block), so every earlier result is reproduced bit for bit.
  - `reverse` (replica-only: swap the signals BEFORE the gate) is independent and composes
    with it; with the filter off, inv equals reverse + reverseStops 'mirror' (same trades;
    the two bracket formulas are algebraically equal, not always bit-equal).

Run as a script for the spec's self-checks:  python3 -I apex.py
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
if W not in sys.path:
    sys.path.insert(0, W)
import fgf  # noqa: E402  (verified direction-filter replica; not reimplemented here)

DATA = os.path.join(W, 'data')
MINTICK = 0.01
POINTVALUE = 1.0
INIT_CAPITAL = 1_000_000.0          # Pine default (strategy() sets no initial_capital)
TRAIL_TOL = 1e-6 * MINTICK          # touch / arm tolerance of the trailing stop (engine.py _walk)
WINDOWS = {
    'BTC': (1731801600, 1794873600),   # 2024-11-17 .. 2026-11-17 by t_close
    'XAU': (1483315200, 1529366400),   # 2017-01-02 .. 2018-06-19 by t_close
}

DEFAULTS = dict(
    # Pine inputs (ApexForge part)
    htfTimeframe="15", zoneLookback=20, minBodyStr=0.65, volMultiplier=1.7, rrRatio=3.0,
    showZones=True, showRangeNote=True,          # display only
    apxBlkClose=True,
    # Pine inputs: trailing take profit (group "Trailing take profit", off by default)
    apxTrailOn=False, apxTrailAct=1.0, apxTrailOff=0.5, apxUseTarget=True,
    # Pine input of Update 1 (group "Inverted direction (Update 1)", off by default)
    apxInv=False,
    # replica controls
    fgfOn=True, blkClose=None, cost='tv', reverse=False, pivotTies='strict',
    reverseStops='literal',      # 'literal' | 'mirror' (only used with reverse=True)
    trailOn=None, trailAct=None, trailOff=None, useTarget=None,   # replica names of apxTrail* /
    #                              apxUseTarget; an explicit value wins (like blkClose)
    path='tv',                   # 'tv' | 'mag' (Bar Magnifier, 1-minute sub-bars)
    inv=None,                    # replica name of apxInv; an explicit value wins (like blkClose)
    start=None, end=None,        # window override (t_close bounds); default WINDOWS[pair]
)
_KINDS = ('sl', 'tp', 'reverse', 'blocked_close', 'time', 'hybrid', 'end', 'trail')
K_SL, K_TP, K_REV, K_BLK, K_TIME, K_HYB, K_END, K_TRAIL = range(8)
# _broker(..., want_state=True): stats[4:] = the final state, in this order. pos = the REAL
# position; xl_* = the order "Exit Long" (of "Apex Long"), xs_* = "Exit Short": on, stop, limit,
# trail_points, trail_offset; pts / ofs _buy / _sell = the Pine vars apxTrPtsL / apxTrOfsL /
# apxTrPtsS / apxTrOfsS (per SIGNAL kind, also when inverted).
STATE_KEYS = ('pos', 'xl_on', 'xl_stop', 'xl_limit', 'xl_pts', 'xl_ofs', 'xs_on', 'xs_stop', 'xs_limit',
              'xs_pts', 'xs_ofs', 'pts_buy', 'ofs_buy', 'pts_sell', 'ofs_sell')

# exit-side parameters (simulate); everything else is fixed by prepare()
EXIT_KEYS = ('trailOn', 'trailAct', 'trailOff', 'useTarget', 'blkClose', 'cost', 'path', 'inv')
_EXIT_ALIASES = {'apxTrailOn': 'trailOn', 'apxTrailAct': 'trailAct', 'apxTrailOff': 'trailOff',
                 'apxUseTarget': 'useTarget', 'apxBlkClose': 'blkClose', 'apxInv': 'inv'}
COSTS = ('tv', 'ours', 'stress')
PATHS = ('tv', 'mag')


def cost_rates(pair, cost):
    """(rate of the fill value, $ per unit) charged on every fill."""
    if cost == 'tv':
        return 0.0004, 0.0                        # commission_value = 0.04 (%), per fill
    if cost == 'ours':
        if pair == 'XAU':
            return 0.0, 0.15                      # $0.30 per ounce round trip
        return 0.0002, 0.10                       # 0.02% per fill + $0.20 per coin round trip
    if cost == 'stress':
        if pair == 'XAU':
            return 0.0, 0.25 + 0.01               # $0.50 per ounce round trip + 1 tick per fill
        return 0.00035, 0.10 + 0.01               # 0.035% per fill + $0.10 per unit + 1 tick per fill
    raise ValueError("cost must be one of %r" % (COSTS,))


def _check_exit(X):
    X['trailOn'] = bool(X['trailOn'])
    X['useTarget'] = bool(X['useTarget'])
    X['blkClose'] = bool(X['blkClose'])
    X['inv'] = bool(X['inv'])
    X['trailAct'] = float(X['trailAct'])
    X['trailOff'] = float(X['trailOff'])
    if X['cost'] not in COSTS:
        raise ValueError("cost must be one of %r" % (COSTS,))
    if X['path'] not in PATHS:
        raise ValueError("path must be one of %r" % (PATHS,))
    if not (X['trailAct'] >= 0.0):
        raise ValueError('apxTrailAct minval is 0')
    if not (X['trailOff'] >= 0.0):
        raise ValueError('apxTrailOff minval is 0')
    return X


def _params(params):
    P = dict(DEFAULTS)
    fgf_p = {}
    for k, v in (params or {}).items():
        if k in DEFAULTS:
            P[k] = v
        elif k.startswith('fgf') or k.startswith('fgs') or k == 'FGF_FORCE_OVERLAY':
            fgf_p[k] = v
        else:
            raise KeyError(f'unknown param {k!r}')
    # blkClose is the replica name of apxBlkClose; an explicit blkClose wins (same for the trail)
    if P['blkClose'] is None:
        P['blkClose'] = bool(P['apxBlkClose'])
    for rep, pine in (('trailOn', 'apxTrailOn'), ('trailAct', 'apxTrailAct'), ('trailOff', 'apxTrailOff'),
                      ('useTarget', 'apxUseTarget'), ('inv', 'apxInv')):
        if P[rep] is None:
            P[rep] = P[pine]
    _check_exit(P)
    if P['pivotTies'] not in ('strict', 'left_strict'):
        raise ValueError("pivotTies must be 'strict' or 'left_strict'")
    if P['reverseStops'] not in ('literal', 'mirror'):
        raise ValueError("reverseStops must be 'literal' or 'mirror'")
    if int(P['zoneLookback']) < 5:
        raise ValueError('zoneLookback minval is 5')
    if not (0.1 <= float(P['minBodyStr']) <= 1.0):
        raise ValueError('minBodyStr must be in [0.1, 1.0]')
    if float(P['rrRatio']) < 1.5:
        raise ValueError('rrRatio minval is 1.5')
    P['zoneLookback'] = int(P['zoneLookback'])
    fgf_p['fgfOn'] = bool(P['fgfOn'])
    P['_fgf'] = fgf_p
    return P


def _exit_params(base, ex):
    """The exit setting: base (resolved params) overridden by `ex` (replica or Pine names)."""
    X = {k: base[k] for k in EXIT_KEYS}
    for k, v in (ex or {}).items():
        k2 = _EXIT_ALIASES.get(k, k)
        if k2 not in X:
            raise KeyError(f'not an exit param {k!r} (one of {EXIT_KEYS} or {tuple(_EXIT_ALIASES)})')
        X[k2] = v
    return _check_exit(X)


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
_CACHE = {}


def _tf_name(tf):
    return fgf._tf_name(tf)


def _load_bars(pair, tf):
    """open, high, low, close (float64), t_open, t_close (int64) of a timeframe."""
    name = _tf_name(tf)
    key = ('bars', pair, name)
    if key in _CACHE:
        return _CACHE[key]
    f = os.path.join(DATA, f'{pair}_{name}.parquet')
    cols = ['open', 'high', 'low', 'close', 't_open', 't_close']
    if os.path.exists(f):
        t = pq.read_table(f, columns=cols)
        d = {c: np.ascontiguousarray(t.column(c).to_numpy(),
                                     dtype=np.float64 if c in cols[:4] else np.int64) for c in cols}
    else:
        b = fgf._bars(pair, tf, tuple(cols))
        if b is None:
            raise ValueError(f'timeframe {tf!r} has no data')
        d = {c: np.ascontiguousarray(b[c]) for c in cols}
    _CACHE[key] = d
    return d


def _load_volume(pair, tf, bars):
    name = _tf_name(tf)
    key = ('vol', pair, name)
    if key in _CACHE:
        return _CACHE[key]
    f = os.path.join(DATA, f'{pair}_{name}_vol.parquet')
    if os.path.exists(f):
        v = np.ascontiguousarray(pq.read_table(f, columns=['volume']).column('volume').to_numpy(),
                                 dtype=np.float64)
    else:
        # sum of the 1-minute volumes whose t_open lies in [t_open, t_close) (as build_vol.py)
        b1 = _load_bars(pair, '1')
        v1 = _load_volume(pair, '1', b1)
        cum = np.concatenate([[0.0], np.cumsum(v1)])
        lo = np.searchsorted(b1['t_open'], bars['t_open'], 'left')
        hi = np.searchsorted(b1['t_open'], bars['t_close'], 'left')
        v = cum[hi] - cum[lo]
    if len(v) != len(bars['t_close']):
        raise ValueError(f'volume rows {len(v)} != bar rows {len(bars["t_close"])}')
    _CACHE[key] = v
    return v


def _map_off(src_tclose, dst_tclose):
    """request.security lookahead off: last source bar with t_close <= target t_close (-1 = none)."""
    return np.searchsorted(src_tclose, dst_tclose, side='right') - 1


# ----------------------------------------------------------------------------
# Signals (numba, whole history)
# ----------------------------------------------------------------------------
@njit(cache=True)
def _signals(o, h, l, c, vol, htf_h, htf_l, L, min_body, vol_mult, left_strict, w0, w1):
    """Returns, for chart rows w0..w1-1: bull, bear (resonance), demand top / bottom,
    supply top / bottom (box state after this bar's update, NaN = no box), volume SMA,
    body strength, and two flags: a new swing low / high was found on this bar."""
    n = len(c)
    m = w1 - w0
    bull = np.zeros(m, np.bool_)
    bear = np.zeros(m, np.bool_)
    dtop = np.full(m, np.nan)
    dbot = np.full(m, np.nan)
    stop_ = np.full(m, np.nan)
    sbot = np.full(m, np.nan)
    vsma = np.full(m, np.nan)
    bstr = np.full(m, np.nan)
    newpl = np.zeros(m, np.bool_)
    newph = np.zeros(m, np.bool_)
    d_top = np.nan
    d_bot = np.nan
    s_top = np.nan
    s_bot = np.nan
    R = L
    for i in range(w1):
        # ---- pivots: ta.pivothigh(high, L, L) / ta.pivotlow(low, L, L) on bar i
        sw_h = np.nan
        sw_l = np.nan
        if i >= L + R:
            ci = i - R
            hv = h[ci]
            lv = l[ci]
            okh = True
            okl = True
            for j in range(i - L - R, i + 1):
                if j == ci:
                    continue
                if j < ci or not left_strict:
                    if not (hv > h[j]):
                        okh = False
                    if not (lv < l[j]):
                        okl = False
                else:
                    if not (hv >= h[j]):
                        okh = False
                    if not (lv <= l[j]):
                        okl = False
                if not okh and not okl:
                    break
            if okh:
                sw_h = hv
            if okl:
                sw_l = lv
        # ---- boxes (demand first, then supply, as the Pine)
        if not np.isnan(sw_l):
            d_top = sw_l * 1.008
            d_bot = sw_l * 0.992
        if not np.isnan(sw_h):
            s_top = sw_h * 1.008
            s_bot = sw_h * 0.992
        if i < w0:
            continue
        k = i - w0
        # ---- flow
        rng = h[i] - l[i]
        body = np.nan
        clo = np.nan
        chi = np.nan
        if rng != 0.0:
            body = abs(c[i] - o[i]) / rng
            clo = (c[i] - l[i]) / rng
            chi = (h[i] - c[i]) / rng
        bull_flow = body >= min_body and c[i] > o[i] and clo > 0.65
        bear_flow = body >= min_body and c[i] < o[i] and chi > 0.65
        # ---- ta.sma(volume, 20) (current bar included; na before 20 bars)
        sma = np.nan
        if i >= 19:
            s = 0.0
            for j in range(i - 19, i + 1):
                s += vol[j]
            sma = s / 20.0
        vspike = vol[i] > sma * vol_mult
        # ---- resonance
        bu = (bull_flow and vspike and not np.isnan(d_top) and l[i] <= d_top
              and c[i] > d_bot and c[i] > htf_l[i])
        be = (bear_flow and vspike and not np.isnan(s_top) and h[i] >= s_bot
              and c[i] < s_top and c[i] < htf_h[i])
        bull[k] = bu
        bear[k] = be
        dtop[k] = d_top
        dbot[k] = d_bot
        stop_[k] = s_top
        sbot[k] = s_bot
        vsma[k] = sma
        bstr[k] = body
        newpl[k] = not np.isnan(sw_l)
        newph[k] = not np.isnan(sw_h)
    return bull, bear, dtop, dbot, stop_, sbot, vsma, bstr, newpl, newph


# ----------------------------------------------------------------------------
# Broker (numba, window only)
# ----------------------------------------------------------------------------
@njit(cache=True)
def _walk(v0, v1, v2, v3, sv, has_s, lv, has_l, has_t, A, off, armed, best, tol):
    """One bar (or one 1-minute sub-bar) of the open trade's exit order, in 'long space'
    (a short's prices, levels and fills are negated, which is exact in IEEE arithmetic).

    v0..v3: the path open -> first extreme -> second extreme -> close.
    sv: zone stop, lv: target (limit), has_*: the level exists.
    has_t: trailing on; A: activation price, off: trail offset (price);
    armed / best: trailing state (best price since activation).
    Returns (kind, fill price, armed, best), kind -1 = no exit.
    With trailing off this is exactly _exit_long of the reconciled replica:
    stop gap, limit gap, then the first level reached along the path."""
    # gap at the open: a stop (zone or trailing) at or above the open, or the limit at or below it
    ts = best - off
    hit_t = has_t and armed and v0 <= ts + tol
    hit_s = has_s and v0 <= sv
    if hit_t or hit_s:
        if hit_t and (not hit_s or ts >= sv):
            return K_TRAIL, v0, armed, best
        return K_SL, v0, armed, best
    if has_l and v0 >= lv:
        return K_TP, v0, armed, best
    # the open itself can arm / ratchet the trail
    if has_t:
        if armed:
            if v0 > best:
                best = v0
        elif v0 >= A - tol:
            armed = True
            best = v0
    a = v0
    for seg in range(3):
        if seg == 0:
            b = v1
        elif seg == 1:
            b = v2
        else:
            b = v3
        if b > a:
            # rising: the target can be reached; the trail arms / ratchets; no stop can be touched
            if has_l and b >= lv:
                return K_TP, (lv if lv > a else a), armed, best
            if has_t:
                if armed:
                    if b > best:
                        best = b
                elif b >= A - tol:
                    armed = True
                    best = b
        elif b < a:
            # falling: both stops are fixed along the segment; the higher one is touched first
            ts = best - off
            hit_t = has_t and armed and b <= ts + tol
            hit_s = has_s and b <= sv
            if hit_t or hit_s:
                if hit_t and (not hit_s or ts >= sv):
                    return K_TRAIL, (ts if ts < a else a), armed, best
                return K_SL, (sv if sv < a else a), armed, best
        a = b
    return -1, np.nan, armed, best


@njit(cache=True)
def _broker(o, h, l, c, sig_l, sig_s, buy_ok, sell_ok, stp_l, lim_l, stp_s, lim_s,
            blk_close, rate, fee_unit, init, qty_pct,
            trail_on, tr_act, tr_off, mt, tol,
            use_mag, ptr, so, sh, sl_, sc, cap, im, want_curves, inv=False, want_state=False):
    """The TradingView broker (steps 1-3, REAL sides) and the script (step 4).
    inv: the Pine's apxInv (Update 1): only step 4 reads it. want_state (tests): append the
    final script / exit-order state to `stats` (STATE_KEYS, from index 4)."""
    n = len(c)
    # trades
    t_dir = np.zeros(cap, np.int64)
    t_eb = np.zeros(cap, np.int64)
    t_epx = np.zeros(cap)
    t_qty = np.zeros(cap)
    t_xb = np.zeros(cap, np.int64)
    t_xpx = np.zeros(cap)
    t_kind = np.zeros(cap, np.int64)
    t_pnl = np.zeros(cap)
    t_ecom = np.zeros(cap)
    t_xcom = np.zeros(cap)
    t_sigb = np.zeros(cap, np.int64)
    t_eqb = np.zeros(cap)
    nt = 0
    nc = n if want_curves else 1
    eq_curve = np.zeros(nc)
    pos_curve = np.zeros(nc, np.int64)
    # bar-close equity statistics (= the reconciled summary's curve formulas)
    peak = init
    mxdd = 0.0
    npos = 0
    eq_mid = init
    # position
    pos = 0
    qty = 0.0
    epx = 0.0
    ecom = 0.0
    ebar = 0
    esig = 0
    eqb = init
    closed = 0.0
    # trailing state of the open trade (long space)
    tr_armed = False
    tr_best = 0.0
    # Pine var floats apxTrPtsL / apxTrOfsL / apxTrPtsS / apxTrOfsS (na = no trailing)
    trp_l = np.nan
    tro_l = np.nan
    trp_s = np.nan
    tro_s = np.nan
    # brackets: Exit Long (for Apex Long trades) / Exit Short: stop, limit, trail ticks
    xl_on = False
    xl_s = np.nan
    xl_l = np.nan
    xl_tp = np.nan
    xl_to = np.nan
    xs_on = False
    xs_s = np.nan
    xs_l = np.nan
    xs_tp = np.nan
    xs_to = np.nan
    # pending market orders placed on the previous bar (in placement order)
    # code: 1 entry long, -1 entry short, 2 close long, -2 close short
    pend = np.zeros(4, np.int64)
    pend_q = np.zeros(4)
    pend_b = np.zeros(4, np.int64)
    npend = 0
    eq = init
    for k in range(n):
        # ---- 1. market orders from bar k-1 fill at this open
        for p in range(npend):
            code = pend[p]
            px = o[k]
            if code == 1 or code == -1:
                d = code
                if pos == d:
                    continue                      # pyramiding = 0: same-direction entry ignored
                if pos == -d:                     # reversal: close the open trade in the same fill
                    xc = rate * qty * px + fee_unit * qty
                    pnl = pos * (px - epx) * qty - ecom - xc
                    t_dir[nt] = pos; t_eb[nt] = ebar; t_epx[nt] = epx; t_qty[nt] = qty
                    t_xb[nt] = k; t_xpx[nt] = px; t_kind[nt] = K_REV; t_pnl[nt] = pnl
                    t_ecom[nt] = ecom; t_xcom[nt] = xc; t_sigb[nt] = esig; t_eqb[nt] = eqb
                    nt += 1
                    closed += pnl
                    if pos > 0:
                        xl_on = False
                    else:
                        xs_on = False
                    pos = 0
                q = pend_q[p]
                if q > 0.0:
                    pos = d
                    qty = q
                    epx = px
                    ecom = rate * qty * px + fee_unit * qty
                    ebar = k
                    esig = pend_b[p]
                    eqb = init + closed           # equity just before this entry fill
                    tr_armed = False              # a new trade: fresh trailing state
                    tr_best = d * px
            else:
                d = 1 if code == 2 else -1
                if pos == d:                      # strategy.close of that entry's open trade
                    xc = rate * qty * px + fee_unit * qty
                    pnl = pos * (px - epx) * qty - ecom - xc
                    t_dir[nt] = pos; t_eb[nt] = ebar; t_epx[nt] = epx; t_qty[nt] = qty
                    t_xb[nt] = k; t_xpx[nt] = px; t_kind[nt] = K_BLK; t_pnl[nt] = pnl
                    t_ecom[nt] = ecom; t_xcom[nt] = xc; t_sigb[nt] = esig; t_eqb[nt] = eqb
                    nt += 1
                    closed += pnl
                    if pos > 0:
                        xl_on = False
                    else:
                        xs_on = False
                    pos = 0
        npend = 0
        # ---- 2. bracket (+ trailing stop) of the open trade along the bar path / sub-bars
        if pos != 0:
            if pos > 0:
                on = xl_on
                sv0 = xl_s
                lv0 = xl_l
                tp0 = xl_tp
                to0 = xl_to
            else:
                on = xs_on
                sv0 = xs_s
                lv0 = xs_l
                tp0 = xs_tp
                to0 = xs_to
            if on:
                sg = 1.0 if pos > 0 else -1.0
                has_s = not np.isnan(sv0)
                has_l = not np.isnan(lv0)
                has_t = not np.isnan(tp0)
                sv = sg * sv0 if has_s else 0.0
                lv = sg * lv0 if has_l else 0.0
                A = 0.0
                off = 0.0
                if has_t:
                    A = sg * epx + tp0 * mt
                    off = to0 * mt
                kind = -1
                x = np.nan
                if use_mag:
                    for s in range(ptr[k], ptr[k + 1]):
                        if (sh[s] - so[s]) < (so[s] - sl_[s]):
                            p1 = sh[s]
                            p2 = sl_[s]
                        else:
                            p1 = sl_[s]
                            p2 = sh[s]
                        kind, x, tr_armed, tr_best = _walk(sg * so[s], sg * p1, sg * p2, sg * sc[s],
                                                           sv, has_s, lv, has_l, has_t, A, off,
                                                           tr_armed, tr_best, tol)
                        if kind >= 0:
                            break
                else:
                    if (h[k] - o[k]) < (o[k] - l[k]):      # open -> high -> low -> close
                        p1 = h[k]
                        p2 = l[k]
                    else:                                  # open -> low -> high -> close
                        p1 = l[k]
                        p2 = h[k]
                    kind, x, tr_armed, tr_best = _walk(sg * o[k], sg * p1, sg * p2, sg * c[k],
                                                       sv, has_s, lv, has_l, has_t, A, off,
                                                       tr_armed, tr_best, tol)
                if kind >= 0:
                    xpx = sg * x
                    xc = rate * qty * xpx + fee_unit * qty
                    pnl = pos * (xpx - epx) * qty - ecom - xc
                    t_dir[nt] = pos; t_eb[nt] = ebar; t_epx[nt] = epx; t_qty[nt] = qty
                    t_xb[nt] = k; t_xpx[nt] = xpx; t_kind[nt] = kind; t_pnl[nt] = pnl
                    t_ecom[nt] = ecom; t_xcom[nt] = xc; t_sigb[nt] = esig; t_eqb[nt] = eqb
                    nt += 1
                    closed += pnl
                    if pos > 0:
                        xl_on = False
                    else:
                        xs_on = False
                    pos = 0
        # ---- 3. equity at this close (closed P/L + open P/L - commission paid on the open trade)
        eq = init + closed
        if pos != 0:
            eq += pos * (c[k] - epx) * qty - ecom
            npos += 1
        if want_curves:
            eq_curve[k] = eq
            pos_curve[k] = pos
        if k == n - 1:
            break                                  # orders on the last bar never fill
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > mxdd:
            mxdd = dd
        if k == im:
            eq_mid = eq
        # ---- 4. the script at this close
        sl_k = sig_l[k]
        ss_k = sig_s[k]
        go_l = sl_k and buy_ok[k]
        go_s = ss_k and sell_ok[k]
        bk_l = sl_k and not buy_ok[k]
        bk_s = ss_k and not sell_ok[k]
        # Update 1 (apxInv). The script DECIDES on posn = apxPosN, the mirror of the real position
        # when inverted, and SENDS on the other side: side_b = the real side of the trade a BUY
        # signal opens (apxIdBuy: "Apex Long" +1, inverted "Apex Short" -1; apxIdSell = -side_b).
        if inv:
            posn = -pos
            side_b = -1
        else:
            posn = pos
            side_b = 1
        if blk_close and bk_s and posn > 0:        # strategy.close(apxIdBuy)
            pend[npend] = 2 * side_b; pend_q[npend] = 0.0; pend_b[npend] = k; npend += 1
        if blk_close and bk_l and posn < 0:        # strategy.close(apxIdSell)
            pend[npend] = -2 * side_b; pend_q[npend] = 0.0; pend_b[npend] = k; npend += 1
        if go_l:                                   # strategy.entry(apxIdBuy, inv ? short : long)
            pend[npend] = side_b; pend_q[npend] = qty_pct / 100.0 * eq / c[k]; pend_b[npend] = k; npend += 1
            if posn <= 0:                          # a new trade: the trailing ticks are fixed now
                if trail_on:
                    trp_l = max(c[k] * tr_act / 100.0 / mt, 0.0)
                    tro_l = max(c[k] * tr_off / 100.0 / mt, 1.0)
                else:
                    trp_l = np.nan
                    tro_l = np.nan
        if go_l or (sl_k and posn > 0):            # strategy.exit(apxExBuy, apxIdBuy, ...)
            if inv:                                # "Exit Short" of "Apex Short": the BUY block's bracket
                xs_on = True                       # mirrored about the signal close (apxStopBuy / apxTgtBuy)
                xs_s = 2.0 * c[k] - stp_l[k]
                xs_l = 2.0 * c[k] - lim_l[k]
                xs_tp = trp_l
                xs_to = tro_l
            else:
                xl_on = True
                xl_s = stp_l[k]
                xl_l = lim_l[k]
                xl_tp = trp_l
                xl_to = tro_l
        if go_s:                                   # strategy.entry(apxIdSell, inv ? long : short)
            pend[npend] = -side_b; pend_q[npend] = qty_pct / 100.0 * eq / c[k]; pend_b[npend] = k; npend += 1
            if posn >= 0:
                if trail_on:
                    trp_s = max(c[k] * tr_act / 100.0 / mt, 0.0)
                    tro_s = max(c[k] * tr_off / 100.0 / mt, 1.0)
                else:
                    trp_s = np.nan
                    tro_s = np.nan
        if go_s or (ss_k and posn < 0):            # strategy.exit(apxExSell, apxIdSell, ...)
            if inv:                                # "Exit Long" of "Apex Long": apxStopSell / apxTgtSell
                xl_on = True
                xl_s = 2.0 * c[k] - stp_s[k]
                xl_l = 2.0 * c[k] - lim_s[k]
                xl_tp = trp_s
                xl_to = tro_s
            else:
                xs_on = True
                xs_s = stp_s[k]
                xs_l = lim_s[k]
                xs_tp = trp_s
                xs_to = tro_s
    # ---- open trade at the end: closed at the last close
    k = n - 1
    last = eq
    if pos != 0:
        px = c[k]
        xc = rate * qty * px + fee_unit * qty
        pnl = pos * (px - epx) * qty - ecom - xc
        t_dir[nt] = pos; t_eb[nt] = ebar; t_epx[nt] = epx; t_qty[nt] = qty
        t_xb[nt] = k; t_xpx[nt] = px; t_kind[nt] = K_END; t_pnl[nt] = pnl
        t_ecom[nt] = ecom; t_xcom[nt] = xc; t_sigb[nt] = esig; t_eqb[nt] = eqb
        nt += 1
        closed += pnl
        last = init + closed
        if want_curves:
            eq_curve[k] = last
    if last > peak:
        peak = last
    dd = (peak - last) / peak
    if dd > mxdd:
        mxdd = dd
    if im == n - 1:
        eq_mid = last
    stats = np.empty(19 if want_state else 4)
    stats[0] = last                     # final equity
    stats[1] = mxdd                     # max drawdown (fraction) on the bar-close curve
    stats[2] = eq_mid                   # equity at the half split
    stats[3] = npos                     # bars with a position (exposure numerator)
    if want_state:                      # STATE_KEYS (tests): the state after the last bar, before
        stats[4] = pos                  # the end-of-window close. A closed trade only clears `on`.
        stats[5] = 1.0 if xl_on else 0.0
        stats[6] = xl_s
        stats[7] = xl_l
        stats[8] = xl_tp
        stats[9] = xl_to
        stats[10] = 1.0 if xs_on else 0.0
        stats[11] = xs_s
        stats[12] = xs_l
        stats[13] = xs_tp
        stats[14] = xs_to
        stats[15] = trp_l
        stats[16] = tro_l
        stats[17] = trp_s
        stats[18] = tro_s
    return (t_dir[:nt], t_eb[:nt], t_epx[:nt], t_qty[:nt], t_xb[:nt], t_xpx[:nt], t_kind[:nt],
            t_pnl[:nt], t_ecom[:nt], t_xcom[:nt], t_sigb[:nt], eq_curve, pos_curve, t_eqb[:nt], stats)


# ----------------------------------------------------------------------------
# prepare / simulate
# ----------------------------------------------------------------------------
def _window(pair, P):
    start, end = WINDOWS[pair]
    if P['start'] is not None:
        start = int(P['start'])
    if P['end'] is not None:
        end = int(P['end'])
    return start, end


def _signal_arrays(pair, chart_tf, P, w0, w1):
    """Signals and boxes on rows w0..w1-1 (cached: independent of the gate / exits)."""
    key = ('sig', pair, _tf_name(chart_tf), w0, w1, P['htfTimeframe'], P['zoneLookback'],
           float(P['minBodyStr']), float(P['volMultiplier']), P['pivotTies'])
    if key in _CACHE:
        return _CACHE[key]
    cb = _load_bars(pair, chart_tf)
    vol = _load_volume(pair, chart_tf, cb)
    tc = cb['t_close']
    hb = _load_bars(pair, P['htfTimeframe'])
    j = _map_off(hb['t_close'], tc[:w1])
    htf_h = np.where(j >= 0, hb['high'][np.maximum(j, 0)], np.nan)
    htf_l = np.where(j >= 0, hb['low'][np.maximum(j, 0)], np.nan)
    o, h, l, c = cb['open'][:w1], cb['high'][:w1], cb['low'][:w1], cb['close'][:w1]
    res = _signals(o, h, l, c, vol[:w1], htf_h, htf_l, P['zoneLookback'], float(P['minBodyStr']),
                   float(P['volMultiplier']), P['pivotTies'] == 'left_strict', w0, w1)
    out = (res, htf_h, htf_l)
    _CACHE[key] = out
    return out


def _gate(pair, chart_tf, P, start, end, tcw):
    if not P['fgfOn']:
        n = len(tcw)
        return np.ones(n, np.bool_), np.ones(n, np.bool_)    # fgfBuyOk = not fgfOn or (...)
    key = ('perm', pair, _tf_name(chart_tf), start, end, tuple(sorted((k, repr(v)) for k, v in P['_fgf'].items())))
    if key not in _CACHE:
        perm = fgf.fgf_permissions(pair, chart_tf, start, end, P['_fgf'])
        if len(perm) != len(tcw) or not np.array_equal(perm['t_close'].to_numpy(), tcw):
            raise RuntimeError('fgf permissions not aligned with the chart window')
        _CACHE[key] = (perm['buyOk'].to_numpy().astype(np.bool_), perm['sellOk'].to_numpy().astype(np.bool_))
    return _CACHE[key]


def prepare(pair, chart_tf, params=None):
    """Everything that does not depend on the exit setting: window, chart OHLC, signals,
    boxes, the filter gate and the zone stop / target per bar. Returns a dict S for
    simulate(S, exit_params). `params` may hold exit params too: they become the
    defaults of simulate()."""
    P = _params(params)
    start, end = _window(pair, P)
    cb = _load_bars(pair, chart_tf)
    vol = _load_volume(pair, chart_tf, cb)
    tc = cb['t_close']
    w0 = int(np.searchsorted(tc, start, side='left'))
    w1 = int(np.searchsorted(tc, end, side='right'))
    if w1 <= w0:
        raise ValueError('empty window')
    (bull, bear, dtop, dbot, stop_, sbot, vsma, bstr, newpl, newph), htf_h, htf_l = \
        _signal_arrays(pair, chart_tf, P, w0, w1)
    o, h, l, c = cb['open'], cb['high'], cb['low'], cb['close']
    ow, hw, lw, cw = o[w0:w1], h[w0:w1], l[w0:w1], c[w0:w1]
    rr = float(P['rrRatio'])
    # the Pine's stop / target formulas (long uses the demand box, short the supply box)
    stp_l = dbot * 0.995
    lim_l = cw + (cw - stp_l) * rr
    stp_s = stop_ * 1.005
    lim_s = cw - (stp_s - cw) * rr
    if P['reverse']:
        sig_l, sig_s = bear.copy(), bull.copy()
        if P['reverseStops'] == 'mirror':
            dist_s = stop_ * 1.005 - cw          # the bear signal's own risk, mirrored
            dist_l = cw - dbot * 0.995
            stp_l = cw - dist_s
            lim_l = cw + dist_s * rr
            stp_s = cw + dist_l
            lim_s = cw - dist_l * rr
    else:
        sig_l, sig_s = bull, bear
    tcw = tc[w0:w1]
    buy_ok, sell_ok = _gate(pair, chart_tf, P, start, end, tcw)
    tow = cb['t_open'][w0:w1]
    mid = start + (end - start) // 2
    S = dict(P=P, pair=pair, tf=str(chart_tf), start=int(start), end=int(end), w0=w0, w1=w1,
             o=ow, h=hw, l=lw, c=cw, t_open=tow, t_close=tcw,
             sig_l=np.ascontiguousarray(sig_l), sig_s=np.ascontiguousarray(sig_s),
             buy_ok=buy_ok, sell_ok=sell_ok,
             stp_l=stp_l, lim_l=lim_l, stp_s=stp_s, lim_s=lim_s, no_lim=np.full(w1 - w0, np.nan),
             mid=int(mid), im=int(np.searchsorted(tcw, mid, side='right')) - 1,
             cap=int((sig_l | sig_s).sum()) + 2,
             diag=dict(volume=vol[w0:w1], vol_sma=vsma, body=bstr, htfHigh=htf_h[w0:w1], htfLow=htf_l[w0:w1],
                       dTop=dtop, dBot=dbot, sTop=stop_, sBot=sbot, newPL=newpl, newPH=newph,
                       bull=bull, bear=bear),
             raw_long=int(sig_l.sum()), raw_short=int(sig_s.sum()),
             blocked_long=int((sig_l & ~buy_ok).sum()), blocked_short=int((sig_s & ~sell_ok).sum()))
    return S


def sub_bars(S, check=True):
    """1-minute sub-bars of the window's chart bars (Bar Magnifier): the rows of
    data/<PAIR>_1.parquet with t_open in [t_open, t_close) of each chart bar.
    Returns (ptr int64 (n+1), open, high, low, close); chart bar k = [ptr[k], ptr[k+1]).
    With check, every chart bar must have >= 1 sub-bar and equal their first open /
    max high / min low / last close (build_bars.py built it from them). Cached in S."""
    if S.get('sub') is not None:
        return S['sub']
    key = ('sub', S['pair'], _tf_name(S['tf']), S['w0'], S['w1'])
    if key not in _CACHE:
        m = _load_bars(S['pair'], '1')
        mto = m['t_open']
        s = np.searchsorted(mto, S['t_open'], side='left')
        e = np.searchsorted(mto, S['t_close'], side='left')
        ln = (e - s).astype(np.int64)
        ptr = np.zeros(len(ln) + 1, np.int64)
        np.cumsum(ln, out=ptr[1:])
        idx = np.repeat(s - ptr[:-1], ln) + np.arange(int(ptr[-1]), dtype=np.int64)
        so = np.ascontiguousarray(m['open'][idx])
        sh = np.ascontiguousarray(m['high'][idx])
        sl = np.ascontiguousarray(m['low'][idx])
        sc = np.ascontiguousarray(m['close'][idx])
        if check:
            if (ln <= 0).any():
                raise ValueError('%s %s: %d chart bars without 1-minute sub-bars'
                                 % (S['pair'], S['tf'], int((ln <= 0).sum())))
            st = ptr[:-1]
            ok = ((so[st] == S['o']) & (sc[ptr[1:] - 1] == S['c'])
                  & (np.maximum.reduceat(sh, st) == S['h']) & (np.minimum.reduceat(sl, st) == S['l']))
            if not ok.all():
                raise ValueError('%s %s: %d chart bars differ from their 1-minute sub-bars'
                                 % (S['pair'], S['tf'], int((~ok).sum())))
        _CACHE[key] = (ptr, so, sh, sl, sc)
    S['sub'] = _CACHE[key]
    return S['sub']


def fake_sub_bars(S):
    """Every chart bar is its own single sub-bar (test R3)."""
    n = len(S['c'])
    return (np.arange(n + 1, dtype=np.int64), S['o'].copy(), S['h'].copy(), S['l'].copy(), S['c'].copy())


_NO_SUB = (np.zeros(1, np.int64), np.zeros(1), np.zeros(1), np.zeros(1), np.zeros(1))


def simulate(S, exit_params=None, sub=None, want_curves=False):
    """One exit setting on prepared inputs. Returns (out, summary): out = the broker arrays
    (t_dir, t_eb, t_epx, t_qty, t_xb, t_xpx, t_kind, t_pnl, t_ecom, t_xcom, t_sigb,
    eq_curve, pos_curve, t_eqb, stats); bar indices are window positions (row - w0).
    `sub` overrides the 1-minute sub-bar table of path 'mag' (tests)."""
    t0 = _time.time()
    X = _exit_params(S['P'], exit_params)
    rate, fee = cost_rates(S['pair'], X['cost'])
    use_mag = X['path'] == 'mag'
    if use_mag:
        ptr, so, sh, sl, sc = sub if sub is not None else sub_bars(S)
        if len(ptr) != len(S['c']) + 1:
            raise ValueError('sub-bar table does not match the window')
    else:
        ptr, so, sh, sl, sc = _NO_SUB
    lim_l = S['lim_l']
    lim_s = S['lim_s']
    if X['trailOn'] and not X['useTarget']:      # limit = apxTrailOn and not apxUseTarget ? na : target
        lim_l = S['no_lim']
        lim_s = S['no_lim']
    out = _broker(S['o'], S['h'], S['l'], S['c'], S['sig_l'], S['sig_s'], S['buy_ok'], S['sell_ok'],
                  S['stp_l'], lim_l, S['stp_s'], lim_s, X['blkClose'], rate, fee, INIT_CAPITAL, 1.0,
                  X['trailOn'], X['trailAct'], X['trailOff'], MINTICK, TRAIL_TOL,
                  use_mag, ptr, so, sh, sl, sc, S['cap'], S['im'], want_curves, X['inv'], False)
    return out, _summary(S, X, out, t0)


def _summary(S, X, out, t0):
    (t_dir, t_eb, t_epx, t_qty, t_xb, t_xpx, t_kind, t_pnl, t_ecom, t_xcom, t_sigb,
     eq_curve, pos_curve, t_eqb, stats) = out
    P = S['P']
    init = INIT_CAPITAL
    final = float(stats[0])
    n = len(S['c'])
    wins = t_pnl[t_pnl > 0].sum()
    losses = -t_pnl[t_pnl < 0].sum()
    kc = np.bincount(t_kind, minlength=len(_KINDS)) if len(t_kind) else np.zeros(len(_KINDS), np.int64)
    # fair halves: trades ENTERED in each half, compounded on the equity before each entry fill
    et = S['t_open'][t_eb] if len(t_eb) else np.zeros(0, np.int64)
    first = et <= S['mid']
    r = 1.0 + t_pnl / t_eqb if len(t_pnl) else np.zeros(0)
    nt = int(len(t_pnl))
    s = {
        'pair': S['pair'], 'tf': S['tf'], 'start': S['start'], 'end': S['end'], 'bars': int(n),
        'trades': nt,
        'net_pct': float(100.0 * (final - init) / init),
        'pf': float(wins / losses) if losses > 0 else (float('inf') if wins > 0 else float('nan')),
        'win_pct': float(100.0 * (t_pnl > 0).mean()) if nt else float('nan'),
        'max_dd_pct': float(100.0 * stats[1]),
        'long': int((t_dir > 0).sum()), 'short': int((t_dir < 0).sum()),
        'raw_long': S['raw_long'], 'raw_short': S['raw_short'],
        'blocked_long': S['blocked_long'], 'blocked_short': S['blocked_short'],
        'half1_pct': float(100.0 * (stats[2] - init) / init),
        'half2_pct': float(100.0 * (final - stats[2]) / init),
        'exposure': float(stats[3] / n),
        'exit_kinds': {k: int(kc[i]) for i, k in enumerate(_KINDS) if kc[i] > 0},
        'costs': float(t_ecom.sum() + t_xcom.sum()),
        'final_equity': final,
        'params': {k: (X[k] if k in X else P[k])
                   for k in ('fgfOn', 'blkClose', 'cost', 'reverse', 'pivotTies', 'reverseStops',
                             'htfTimeframe', 'zoneLookback', 'minBodyStr', 'volMultiplier', 'rrRatio')},
        'exit_params': {k: X[k] for k in ('trailOn', 'trailAct', 'trailOff', 'useTarget', 'path')},
        'h1r_pct': float(100.0 * (np.prod(r[first]) - 1.0)),
        'h2r_pct': float(100.0 * (np.prod(r[~first]) - 1.0)),
        'h1_trades': int(first.sum()), 'h2_trades': int(nt - first.sum()),
        'inv': bool(X['inv']),           # apxInv (Update 1): long / short above are REAL sides
    }
    for i, k in enumerate(_KINDS):
        s['exit_' + k] = int(kc[i])
    s['avg_bars_held'] = float((t_xb - t_eb).mean()) if nt else float('nan')
    s['stopped_at_fill_open'] = int(((t_eb == t_xb) & (t_kind == K_SL) & (t_xpx == t_epx)).sum())
    s['seconds'] = round(_time.time() - t0, 3)
    return s


def trades_frame(S, out):
    (t_dir, t_eb, t_epx, t_qty, t_xb, t_xpx, t_kind, t_pnl, t_ecom, t_xcom, t_sigb,
     eq_curve, pos_curve, t_eqb, stats) = out
    to = S['t_open']
    tcl = S['t_close']
    w0 = S['w0']
    kinds = np.array(_KINDS, dtype=object)
    exit_time = np.where(t_kind == K_END, tcl[t_xb], to[t_xb]) if len(t_xb) else np.zeros(0, np.int64)
    return pd.DataFrame({
        'dir': t_dir.astype(np.int64),
        'entry_time': to[t_eb] if len(t_eb) else np.zeros(0, np.int64),
        'entry_px': t_epx,
        'qty': t_qty,
        'exit_time': exit_time.astype(np.int64),
        'exit_px': t_xpx,
        'exit_kind': kinds[t_kind] if len(t_kind) else np.zeros(0, object),
        'pnl': t_pnl,
        'entry_bar': (t_eb + w0).astype(np.int64),
        'exit_bar': (t_xb + w0).astype(np.int64),
        'signal_bar': (t_sigb + w0).astype(np.int64),
        'entry_cost': t_ecom,
        'exit_cost': t_xcom,
        'eq_before': t_eqb,
    })


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------
def compute(pair, chart_tf, params=None):
    """Everything per window bar (signals, boxes, gate, stop / target, equity, position)
    plus the broker output (diagnostics)."""
    S = prepare(pair, chart_tf, params)
    out, _ = simulate(S, None, want_curves=True)
    d = S['diag']
    bars = pd.DataFrame({
        'row': np.arange(S['w0'], S['w1']), 't_open': S['t_open'], 't_close': S['t_close'],
        'open': S['o'], 'high': S['h'], 'low': S['l'], 'close': S['c'], 'volume': d['volume'],
        'vol_sma': d['vol_sma'], 'body': d['body'], 'htfHigh': d['htfHigh'], 'htfLow': d['htfLow'],
        'dTop': d['dTop'], 'dBot': d['dBot'], 'sTop': d['sTop'], 'sBot': d['sBot'],
        'newPL': d['newPL'], 'newPH': d['newPH'], 'bull': d['bull'], 'bear': d['bear'],
        'sigL': S['sig_l'], 'sigS': S['sig_s'], 'buyOk': S['buy_ok'], 'sellOk': S['sell_ok'],
        'stpL': S['stp_l'], 'limL': S['lim_l'], 'stpS': S['stp_s'], 'limS': S['lim_s'],
        'equity': out[11], 'pos': out[12],
    })
    return S['P'], S['start'], S['end'], S['w0'], S['w1'], bars, out


def run(pair, chart_tf, params=None):
    t0 = _time.time()
    S = prepare(pair, chart_tf, params)
    out, summary = simulate(S, None)
    trades = trades_frame(S, out)
    summary['seconds'] = round(_time.time() - t0, 2)
    return trades, summary


# ----------------------------------------------------------------------------
# Self-checks (python3 -I apex.py) -- the detailed checks live in apex_b_check.py
# and sweep_ah_tests.py
# ----------------------------------------------------------------------------
def _fmt(s):
    keys = ('bars', 'trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'long', 'short', 'raw_long',
            'raw_short', 'blocked_long', 'blocked_short', 'half1_pct', 'half2_pct', 'exposure', 'exit_kinds',
            'seconds')
    return ' '.join(f'{k}={round(s[k], 3) if isinstance(s[k], float) else s[k]}' for k in keys)


if __name__ == '__main__':
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '1')):
        tr, s = run(pair, tf)
        print(pair, tf, _fmt(s), flush=True)
