"""xpw23.py: XPW Orientation TDI v2.8 (S2 / S3 exits) + FGF [Update 1], the canonical Python replica.

Ground truth: /home/user/master/xpw_orientation_tdi_v2.8_strategy_FGF.pine at HEAD (Update 1).
Brief: SPEC_xpw23.md and REPLICA_SPEC.md. Notes: xpw23_notes.md. Reconciliation of the two
independent builds (xpw23_a.py, xpw23_b.py; they agree trade for trade): reconcile_xpw23.md.
Tests: tests_xpw23.py. This module is build A plus the Bar Magnifier path and a few summary
fields of build B.

What is reused, and why that is allowed: the signal code of this Pine file (lines 1143-1626,
"// PER-RUNG WINDOWS" .. "nShort := 0") is byte-identical to lines 1001-1484 of the trailing-TP file
that xpw.py replicates (same sha256), the signal inputs (447-508 / 314-375) and the filter block
(547-1127 / 402-982) are byte-identical too. So the signals are xpw.xpw_signals and the filter is
fgf.fgf_permissions. Everything from line 1628 on (the STRATEGY section: gate, closes, S2 exits,
S3 sizing, limit / stop entries with the pending list, the time stop, Update 1) is written here.

    prepare(pair, chart_tf, params=None) -> P      signals, filter permissions, bars (no order input)
    simulate(P, x=None, full=False) -> R           the script's STRATEGY section + TradingView's broker
    trades(P, R) -> DataFrame                      one row per entry fill
    summary(P, R) -> dict
    run(pair, chart_tf, params=None) -> (trades, summary)
    get_sub(P) -> the 1-minute sub-bars of the window's chart bars (path 'mag')

x['path']:
  'tv'   TradingView without Bar Magnifier: one intrabar path per chart bar (open -> the nearer
         extreme -> the other extreme -> close).
  'mag'  Bar Magnifier with the 1-minute data: step 1 of every chart bar (the exit orders: stop
         loss, take profit, trailing stop; and the pending limit / stop ENTRY orders of limit mode)
         walks the 1-minute sub-bars of that chart bar in time order, each sub-bar with its own
         path and its own open test (a level jumped over between two sub-bars fills at the next
         sub-bar's open); the trailing state carries over. The script, its market orders,
         close_all, the time stop and the "fills at the placement close" attempt of a new pending
         entry stay on the chart bar's close. Chart "1": mag == tv.
Both paths are ONE code path (_step1): 'tv' is the walk with the chart bar as its only sub-bar.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from numba import njit

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import fgf   # noqa: E402
import xpw   # noqa: E402

DATA = os.path.join(W, 'data')
MINTICK = 0.01
POINTVALUE = 1.0
INITIAL_CAPITAL = 10000.0          # strategy(initial_capital=10000)
PYRAMIDING = 100                   # strategy(pyramiding=100)
TOL = 1e-8                         # 1e-6 tick, as engine.py
WINDOWS = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}

# per fill, per unit: (fixed, fraction of the fill value)   [SPEC_xpw23 section 7 = hrd.COSTS]
COSTS = {
    'tv': {'XAU': (0.0, 0.0), 'BTC': (0.0, 0.0)},          # no commission / slippage in strategy()
    'ours': {'XAU': (0.15, 0.0), 'BTC': (0.10, 0.0002)},
    'stress': {'XAU': (0.26, 0.0), 'BTC': (0.11, 0.00035)},
}

KINDS = ['', 'sl', 'tp', 'trail', 'time', 'close_all', 'reverse', 'end']
K_SL, K_TP, K_TRAIL, K_TIME, K_CLOSEALL, K_REVERSE, K_END = 1, 2, 3, 4, 5, 6, 7
NEG = -1.0e300

TRADE_DIRS = ("Both", "Long only (buy only)", "Short only (sell only)")
ENTRY_FILLS = ("Signal tick", "Limit at label price")
EXIT_UNITS = ("ATR", "Points")
QTY_MODES = ("Fixed", "Risk")

# ORDER / EXIT inputs (simulate), Pine names and defaults (lines 511-540, 1130)
X_DEFAULTS = dict(
    tradeDir="Both", oppCloses=True, entryFill="Signal tick", limitBars=5, maxOpen=20,
    exitUnit="ATR", slPtsIn=10000.0, tpPtsIn=30000.0, atrLen=14, slAtrMult=3.0, tpRMult=1.0,
    trailOn=True, trActPts=15000.0, trDistPts=10000.0, trActAtr=1.0, trDistAtr=0.75, timeStop=0,
    qtyMode="Fixed", qtyFixed=0.1, riskPct=1.0, qtyMax=2.0, qtyStep=0.01,
    xpwInv=False,
    path='tv', cost='tv',
)
_X_FLOATS = ('slPtsIn', 'tpPtsIn', 'slAtrMult', 'tpRMult', 'trActPts', 'trDistPts', 'trActAtr', 'trDistAtr',
             'qtyFixed', 'riskPct', 'qtyMax', 'qtyStep')
_X_INTS = ('limitBars', 'maxOpen', 'atrLen', 'timeStop')

# SIGNAL inputs (prepare)
_XPW_KEYS = set(xpw.DEFAULTS)
_FGF_KEYS = set(fgf.DEFAULTS)
_INERT_KEYS = {'agreeN', 'agreeMode', 'agreeScope', 'agreeInh'}       # inert while agreeOn is false
_DISPLAY_KEYS = {'showTable', 'tblSize', 'tblPos', 'showLbl', 'lblSizeS', 'lblPrice', 'lblTick',
                 'shL1', 'cL1', 'shL2', 'cL2', 'shS1', 'cS1', 'shS2', 'cS2', 'shDL', 'cDL', 'shDS', 'cDS',
                 'shEnd', 'cEnd', 'lblInfo', 'cInf', 'agreeLbl', 'shAgL', 'cAgL', 'shAgS', 'cAgS'} | set(fgf._DISPLAY_KEYS)
_PREP_KEYS = _XPW_KEYS | _FGF_KEYS | _INERT_KEYS | _DISPLAY_KEYS | {'start', 'end'}
_SIM_KEYS = set(X_DEFAULTS) | {'inv'}

# trade table columns inside the kernel
T_EPX, T_QTY, T_SL, T_TP, T_A, T_OFF, T_SLT, T_BEST, T_XPX, T_EQB, T_EC, T_XC, T_GROSS = range(13)
NTF = 13
I_DIR, I_SD, I_SIG, I_K, I_EB, I_XB, I_XK, I_XBY, I_ACT, I_ECL = range(10)
NTI = 10
# pending list columns
P_PX, P_QTY, P_SLT, P_TPT, P_TRP, P_TRO = range(6)
NPF = 6
Q_SIG, Q_K, Q_DIR, Q_TID = range(4)
NPI = 4
# counters
(C_PLACED, C_SKIP_ROOM, C_SKIP_QTY, C_PEND_PLACED, C_PEND_FILLED, C_PEND_CLOSEFILL, C_PEND_CANCELLED,
 C_PEND_OPEN_END, C_CLOSE_ALL_BARS, C_MAX_OPEN, C_MARGIN, C_EXPO, C_VIOL_SIDE, C_VIOL_PYR, C_OVERFLOW,
 C_RAW_L, C_RAW_S, C_BLK_L, C_BLK_S, C_GHOSTS, C_REV_BARS, C_REV_OVER, C_NTR, C_CANCEL_STALE,
 C_CANCEL_AGAINST, C_VIOL_SUB) = range(26)
NCN = 26
F_FINAL, F_MID, F_DD, F_DDABS, F_MAXEXPO = range(5)
NFS = 5
# per-bar debug columns (full=True)
D_OPENT, D_NPEND, D_ROOM, D_PLACED, D_FLAGS, D_POS = range(6)
ND = 6


# ----------------------------------------------------------------------------------------- data
def read_bars(pair, tf, cols=('open', 'high', 'low', 'close', 't_open', 't_close')):
    """Columns of the whole data/<pair>_<tf>.parquet as numpy arrays. Not cached: the 1-minute files
    have millions of rows and prepare() keeps the window rows only."""
    t = pq.read_table(os.path.join(DATA, '%s_%s.parquet' % (pair, str(tf))), columns=list(cols))
    out = {}
    for k in cols:
        a = t.column(k).to_numpy()
        out[k] = a.astype(np.int64 if k.startswith('t_') else np.float64, copy=False)
    return out


@njit(cache=True)
def _atr(high, low, close, n):
    """ta.atr(n) = ta.rma(ta.tr(true), n) on the whole file from row 0 (SPEC 4.3 (b), to the letter):
    tr[0] = high - low; the seed atr[n-1] = sum(tr[0..n-1]) in index order / n; then
    atr[i] = alpha * tr[i] + (1 - alpha) * atr[i-1], alpha = 1.0 / n; na before row n-1."""
    m = close.shape[0]
    out = np.full(m, np.nan)
    alpha = 1.0 / n
    s = 0.0
    prev = 0.0
    for i in range(m):
        tr = high[i] - low[i]
        if i > 0:
            a = abs(high[i] - close[i - 1])
            b = abs(low[i] - close[i - 1])
            if a > tr:
                tr = a
            if b > tr:
                tr = b
        if i < n:
            s += tr
            if i == n - 1:
                prev = s / n
                out[i] = prev
        else:
            prev = alpha * tr + (1.0 - alpha) * prev
            out[i] = prev
    return out


_ATR_CACHE = {}
_ATR_CACHE_MAX = 8


def atr_window(P, atrLen):
    """ATR(atrLen) of the chart on the window rows, computed on the whole file from row 0 (cached
    per length inside P, and per (pair, tf, length, window) in the module)."""
    atrLen = int(atrLen)
    a = P['_atr'].get(atrLen)
    if a is None:
        if P['tf'] == 'syn':
            raise ValueError('make_P: no ATR(%d) array was given (ATR mode)' % atrLen)
        key = (P['pair'], P['tf'], atrLen, P['w0'], P['w1'])
        a = _ATR_CACHE.get(key)
        if a is None:
            b = read_bars(P['pair'], P['tf'], ('high', 'low', 'close'))
            a = _atr(np.ascontiguousarray(b['high']), np.ascontiguousarray(b['low']),
                     np.ascontiguousarray(b['close']), atrLen)[P['w0']:P['w1']].copy()
            del b
            if len(_ATR_CACHE) >= _ATR_CACHE_MAX:
                _ATR_CACHE.pop(next(iter(_ATR_CACHE)))
            _ATR_CACHE[key] = a
        P['_atr'][atrLen] = a
    return a


# ---------------------------------------------------------------------------------- the broker
@njit(cache=True)
def _walk(w0, w1, w2, w3, s0, a0, chk, act, best, A, off, sl, tp, has_tr, has_sl, has_tp, tol):
    """The exit order of ONE trade (strategy.exit: loss, profit, trail_points / trail_offset) along
    one bar's path, in 'long space' (real prices times the trade's real side).
    w0..w3 = open, first extreme, second extreme, close. s0 / a0: the segment and the point the
    walk starts from (0 / w0 for a trade open before the bar; the fill point for a trade filled
    inside this bar). chk: test the open (only for a trade open before this bar).
    Returns (kind, fill price in long space, armed, best); kind 0 = no exit.
      open:    at / below the stop (the higher of the stop loss and the trailing stop) -> stop at the
               open; else at / above the target -> target at the open; else the open can arm /
               ratchet the trail;
      rising:  reaches the target -> at the target; else arms / ratchets the trail;
      falling: the stop is fixed along the segment; reached -> at the stop.
    Trailing stop >= stop loss -> 'trail', else 'sl'."""
    sv = sl if has_sl else NEG
    if chk:
        ts = (best - off) if (has_tr and act) else NEG
        lvl = ts if ts > sv else sv
        if w0 <= lvl + tol:
            return (K_TRAIL if ts >= sv else K_SL), w0, act, best
        if has_tp and w0 >= tp - tol:
            return K_TP, w0, act, best
        if has_tr:
            if act:
                if w0 > best:
                    best = w0
            elif w0 >= A - tol:
                act = True
                best = w0
    a = a0
    for s in range(s0, 3):
        if s == 0:
            b = w1
        elif s == 1:
            b = w2
        else:
            b = w3
        if b > a:
            if has_tp and b >= tp - tol:
                return K_TP, (tp if tp > a else a), act, best
            if has_tr:
                if act:
                    if b > best:
                        best = b
                elif b >= A - tol:
                    act = True
                    best = b
        elif b < a:
            ts = (best - off) if (has_tr and act) else NEG
            lvl = ts if ts > sv else sv
            if b <= lvl + tol:
                return (K_TRAIL if ts >= sv else K_SL), (lvl if lvl < a else a), act, best
        a = b
    return 0, 0.0, act, best


@njit(cache=True)
def _open_trade(TF, TI, tid, dr, sd, sig, k, eb, px, qty, slT, tpT, trp, tro, eqb, ecl, mt, tol, c_fix, c_pct):
    """A fill of an entry order: the trade row and its exit levels (ticks from the fill, on the
    real side dr; kept in long space e = dr * px). slT / tpT / tro NaN = that exit is not used.
    Returns the entry cost."""
    e = dr * px
    TI[tid, I_DIR] = dr
    TI[tid, I_SD] = sd
    TI[tid, I_SIG] = sig
    TI[tid, I_K] = k
    TI[tid, I_EB] = eb
    TI[tid, I_XB] = -1
    TI[tid, I_XK] = 0
    TI[tid, I_XBY] = -1
    TI[tid, I_ECL] = ecl
    TF[tid, T_EPX] = px
    TF[tid, T_QTY] = qty
    TF[tid, T_SL] = e - slT * mt               # NaN when the stop loss is off
    TF[tid, T_TP] = e + tpT * mt               # NaN when the target is off
    TF[tid, T_SLT] = slT
    TF[tid, T_BEST] = e
    act = 0
    if not math.isnan(tro):
        A = e + trp * mt
        TF[tid, T_A] = A
        TF[tid, T_OFF] = tro * mt
        if e >= A - tol:                       # trail_points 0: armed at the fill
            act = 1
    else:
        TF[tid, T_A] = np.nan
        TF[tid, T_OFF] = np.nan
    TI[tid, I_ACT] = act
    ec = qty * (c_fix + c_pct * px)
    TF[tid, T_EC] = ec
    TF[tid, T_EQB] = eqb
    return ec


@njit(cache=True)
def _close_trade(TF, TI, i, j, px, kind, pv, c_fix, c_pct):
    """A fill that closes trade i at the real price px. Returns (gross - exit cost, exit cost)."""
    q = TF[i, T_QTY]
    g = TI[i, I_DIR] * (px - TF[i, T_EPX]) * q * pv
    xc = q * (c_fix + c_pct * px)
    TF[i, T_XPX] = px
    TF[i, T_XC] = xc
    TF[i, T_GROSS] = g
    TI[i, I_XB] = j
    TI[i, I_XK] = kind
    return g - xc, xc


@njit(cache=True)
def _step1(j, s_lo, s_hi, so, sh, sl_, sc, blo, bhi, eq_prev, inv, useLimit, pyr, mt, pv, c_fix, c_pct, tol,
           n_open, pos_dir, n_tr, n_pend, cash, open_ids, TF, TI, PF, PI, cn):
    """Step 1 of chart bar j (both paths): the intrabar fills along the sub-bars s_lo .. s_hi-1 of
    so / sh / sl_ / sc in time order. Path 'tv': the chart bar itself is the one sub-bar. Path
    'mag': the 1-minute bars inside the chart bar. Each sub-bar is walked open -> nearer extreme
    -> other extreme -> close (tie: low first) and its open is tested as an open: a level passed
    by the jump from the previous sub-bar's close fills AT the open.
      (ii) the exit order of every trade open before the bar (stop loss, target, trailing stop);
      (i)  every live pending entry (limit / stop entry of an earlier bar); the exit order of the
           trade it opens is live from the fill point on: the rest of that sub-bar, then the
           following sub-bars.
    blo / bhi: the lowest low / highest high of the sub-bars, for two exact shortcuts (no path point
    reaches a level). A trade's fills depend only on the path and on its own levels, so trades and
    pending entries are walked one after the other. Returns (n_open, pos_dir, n_tr, cash)."""
    pos0 = pos_dir
    if n_open > 0:
        sg = float(pos_dir)
        if pos_dir > 0:
            wmin = blo
            wmax = bhi
        else:
            wmin = -bhi
            wmax = -blo
        w = 0
        for q in range(n_open):
            i = open_ids[q]
            sl = TF[i, T_SL]
            tp = TF[i, T_TP]
            A = TF[i, T_A]
            has_sl = not math.isnan(sl)
            has_tp = not math.isnan(tp)
            has_tr = not math.isnan(A)
            kind = 0
            px = 0.0
            if has_sl or has_tp or has_tr:
                act = TI[i, I_ACT] != 0
                sv = sl if has_sl else NEG
                # nothing can happen when no path point reaches a level (exact shortcut)
                quiet = False
                if not (has_tr and act):
                    if wmin > sv + tol and (not has_tp or wmax < tp - tol) and (not has_tr or wmax < A - tol):
                        quiet = True
                if not quiet:
                    best = TF[i, T_BEST]
                    off = TF[i, T_OFF]
                    for s in range(s_lo, s_hi):
                        o_ = so[s]
                        h_ = sh[s]
                        l_ = sl_[s]
                        # the same shortcut per sub-bar; with an armed trail: no stop, no target and
                        # no new best price inside this sub-bar
                        if pos_dir > 0:
                            smin = l_
                            smax = h_
                        else:
                            smin = -h_
                            smax = -l_
                        if has_tr and act:
                            ts = best - off
                            lvl = ts if ts > sv else sv
                            if smin > lvl + tol and smax <= best and (not has_tp or smax < tp - tol):
                                continue
                        elif smin > sv + tol and (not has_tp or smax < tp - tol) and (not has_tr or smax < A - tol):
                            continue
                        if (h_ - o_) < (o_ - l_):
                            p1 = h_
                            p2 = l_
                        else:
                            p1 = l_
                            p2 = h_
                        kind, px, act, best = _walk(sg * o_, sg * p1, sg * p2, sg * sc[s], 0, sg * o_, True,
                                                    act, best, A, off, sl, tp, has_tr, has_sl, has_tp, tol)
                        if kind != 0:
                            break
                    TI[i, I_ACT] = 1 if act else 0
                    TF[i, T_BEST] = best
            if kind != 0:
                dc, xc = _close_trade(TF, TI, i, j, sg * px, kind, pv, c_fix, c_pct)
                cash += dc
            else:
                open_ids[w] = i
                w += 1
        n_open = w
        if n_open == 0:
            pos_dir = 0
    if useLimit and n_pend > 0:
        for q in range(n_pend):
            if PI[q, Q_TID] != -1:
                continue                                   # already filled
            d = PI[q, Q_DIR]
            fd = float(d)
            Ppx = PF[q, P_PX]
            dP = fd * Ppx
            # the trigger is d * price <= d * P + tol: no path point of the bar gets there (exact shortcut)
            if fd * (blo if d > 0 else bhi) > dP + tol:
                continue
            seg = -1
            fs = -1
            e_real = 0.0
            p1 = 0.0
            p2 = 0.0
            for s in range(s_lo, s_hi):
                o_ = so[s]
                h_ = sh[s]
                l_ = sl_[s]
                if (h_ - o_) < (o_ - l_):
                    p1 = h_
                    p2 = l_
                else:
                    p1 = l_
                    p2 = h_
                u0 = fd * o_
                if u0 <= dP + tol:
                    seg = 0                                # the (sub-)bar opens through the order: fill at the open
                    e_real = o_
                else:
                    a = u0
                    for g in range(3):
                        if g == 0:
                            b = fd * p1
                        elif g == 1:
                            b = fd * p2
                        else:
                            b = fd * sc[s]
                        if b < a and b <= dP + tol:
                            seg = g
                            e_real = Ppx if dP < a else fd * a
                            break
                        a = b
                if seg >= 0:
                    fs = s
                    break
            if seg < 0:
                continue
            dr = -d if inv else d
            if (pos0 != 0 and pos0 != dr) or (n_open > 0 and pos_dir != dr):
                cn[C_VIOL_SIDE] += 1
            if n_open >= pyr:
                cn[C_VIOL_PYR] += 1
            if n_tr >= TF.shape[0] or n_open >= open_ids.shape[0]:
                cn[C_OVERFLOW] += 1
                continue
            tid = n_tr
            n_tr += 1
            ec = _open_trade(TF, TI, tid, dr, d, PI[q, Q_SIG], PI[q, Q_K], j, e_real, PF[q, P_QTY],
                             PF[q, P_SLT], PF[q, P_TPT], PF[q, P_TRP], PF[q, P_TRO], eq_prev, 0,
                             mt, tol, c_fix, c_pct)
            cash -= ec
            PI[q, Q_TID] = tid
            cn[C_PEND_FILLED] += 1
            # its exit order is live from the fill point on: the rest of sub-bar fs (no open test),
            # then the following sub-bars of this chart bar (each with its open test)
            sl = TF[tid, T_SL]
            tp = TF[tid, T_TP]
            A = TF[tid, T_A]
            has_sl = not math.isnan(sl)
            has_tp = not math.isnan(tp)
            has_tr = not math.isnan(A)
            kind = 0
            px = 0.0
            if has_sl or has_tp or has_tr:
                sg = float(dr)
                off = TF[tid, T_OFF]
                kind, px, act, best = _walk(sg * so[fs], sg * p1, sg * p2, sg * sc[fs], seg, sg * e_real, False,
                                            TI[tid, I_ACT] != 0, TF[tid, T_BEST], A, off,
                                            sl, tp, has_tr, has_sl, has_tp, tol)
                if kind == 0:
                    for s in range(fs + 1, s_hi):
                        o_ = so[s]
                        h_ = sh[s]
                        l_ = sl_[s]
                        if (h_ - o_) < (o_ - l_):
                            p1 = h_
                            p2 = l_
                        else:
                            p1 = l_
                            p2 = h_
                        kind, px, act, best = _walk(sg * o_, sg * p1, sg * p2, sg * sc[s], 0, sg * o_, True,
                                                    act, best, A, off, sl, tp, has_tr, has_sl, has_tp, tol)
                        if kind != 0:
                            break
                TI[tid, I_ACT] = 1 if act else 0
                TF[tid, T_BEST] = best
            if kind != 0:
                dc, xc = _close_trade(TF, TI, tid, j, float(dr) * px, kind, pv, c_fix, c_pct)
                cash += dc
            else:
                open_ids[n_open] = tid
                n_open += 1
                pos_dir = dr
    return n_open, pos_dir, n_tr, cash


@njit(cache=True)
def _kernel(o, h, l, c, nL, nS, exL, exS, buyOk, sellOk, atr,
            allowLong, allowShort, oppCloses, useLimit, limitBars, maxOpen,
            atrMode, slPtsIn, tpPtsIn, slAtrMult, tpRMult, trailOn, trActPts, trDistPts, trActAtr, trDistAtr,
            timeStop, riskMode, qtyFixed, riskPct, qtyMax, qtyStep,
            inv, mt, pv, init, c_fix, c_pct, pyr, tol, cap, mid_j, full,
            mag, ptr, so, sh, sl_, sc, qlo, qhi):
    """The STRATEGY section of the Pine (lines 1628-1799) and the broker, bar by bar (SPEC section 5):
    step 1 intrabar fills, step 2 the script, step 3 the fills at the close in placement order,
    step 4 the bar-close equity and diagnostics. Everything the script DECIDES is in the normal
    frame (xpos = the mirror of the real position when inv); trades carry the REAL side.
    mag: step 1 walks the 1-minute sub-bars [ptr[j], ptr[j+1]) of so / sh / sl_ / sc (qlo / qhi: their
    lowest low / highest high per chart bar); else the chart bar is its own single sub-bar."""
    n = c.shape[0]
    if not mag:
        so = o
        sh = h
        sl_ = l
        sc = c
        qlo = l
        qhi = h
    TF = np.full((cap, NTF), np.nan)
    TI = np.zeros((cap, NTI), np.int64)
    ocap = 256
    open_ids = np.zeros(ocap, np.int64)
    tflag = np.zeros(ocap, np.bool_)
    pcap = maxOpen + 64
    PF = np.full((pcap, NPF), np.nan)
    PI = np.zeros((pcap, NPI), np.int64)
    eq_close = np.empty(n)
    cn = np.zeros(NCN, np.int64)
    fs = np.zeros(NFS)
    dbg = np.zeros((n if full else 1, ND), np.int32)
    n_open = 0
    pos_dir = 0
    n_tr = 0
    n_pend = 0
    cash = init
    eq_prev = init
    peak = init
    max_dd = 0.0
    max_dd_abs = 0.0
    eq_mid = init
    max_expo = 0.0
    for j in range(n):
        cj = c[j]
        # ------------------------------------------------------------------ step 1: intrabar
        if n_open > 0 or (useLimit and n_pend > 0):
            if mag:
                s_lo = ptr[j]
                s_hi = ptr[j + 1]
                if s_hi <= s_lo:
                    cn[C_VIOL_SUB] += 1            # a chart bar without sub-bars (get_sub refuses them)
            else:
                s_lo = j
                s_hi = j + 1
            n_open, pos_dir, n_tr, cash = _step1(j, s_lo, s_hi, so, sh, sl_, sc, qlo[j], qhi[j], eq_prev, inv,
                                                 useLimit, pyr, mt, pv, c_fix, c_pct, tol, n_open, pos_dir, n_tr,
                                                 n_pend, cash, open_ids, TF, TI, PF, PI, cn)
        # ------------------------------------------------------------------ step 2: the script
        nl = nL[j]
        ns = nS[j]
        xl = exL[j]
        xs = exS[j]
        opent = n_open                              # strategy.opentrades
        xpos = -pos_dir if inv else pos_dir         # xpwPos (sign), line 1645
        goL = nl > 0 and allowLong                  # 1655 (doneL != bar_index always true on history)
        goS = ns > 0 and allowShort                 # 1656
        if goL:
            cn[C_RAW_L] += 1                        # FGD funnel, 1796-1799 (normal frame)
            if not buyOk[j]:
                cn[C_BLK_L] += 1
        if goS:
            cn[C_RAW_S] += 1
            if not sellOk[j]:
                cn[C_BLK_S] += 1
        # (a) closes, 1665-1680
        do_close = False
        if xpos != 0:
            oppL = oppCloses and ns > 0 and (not allowShort)
            oppS = oppCloses and nl > 0 and (not allowLong)
            if useLimit:
                closeL = xpos > 0 and (not goL) and (xl or oppL or goS)
                closeS = xpos < 0 and (not goS) and (xs or oppS or goL)
            else:
                closeL = xpos > 0 and (not goL) and (not goS) and (xl or oppL)
                closeS = xpos < 0 and (not goS) and (not goL) and (xs or oppS)
            do_close = closeL or closeS
        # (c) pending list, cancel pass, 1713-1722
        if useLimit and n_pend > 0:
            w = 0
            for q in range(n_pend):
                stale = (j - PI[q, Q_SIG]) >= limitBars
                if PI[q, Q_DIR] > 0:
                    against = xl or goS
                else:
                    against = xs or goL
                if stale or against:
                    tid = PI[q, Q_TID]
                    if tid == -1:
                        cn[C_PEND_CANCELLED] += 1   # strategy.cancel of a live order
                        if against:
                            cn[C_CANCEL_AGAINST] += 1
                        else:
                            cn[C_CANCEL_STALE] += 1
                    elif TI[tid, I_XB] != -1:
                        cn[C_GHOSTS] += 1           # filled and closed before the script saw it open
                else:
                    if w != q:
                        for z in range(NPF):
                            PF[w, z] = PF[q, z]
                        for z in range(NPI):
                            PI[w, z] = PI[q, z]
                    w += 1
            n_pend = w
        # (d) time stop, 1749-1752 (strategy.close per entry id); close_all is placed first (T9)
        n_time = 0
        if timeStop > 0 and opent > 0 and not do_close:
            for q in range(n_open):
                tflag[q] = (j - TI[open_ids[q], I_EB]) >= timeStop
                if tflag[q]:
                    n_time += 1
        # (e) entries, 1758-1780
        room = maxOpen - opent - n_pend
        d = 0
        cnt = 0
        opp = False
        if goL and buyOk[j]:
            d = 1
            cnt = nl
            opp = xpos < 0
        elif goS and sellOk[j]:
            d = -1
            cnt = ns
            opp = xpos > 0
        n_place = 0
        qv = 0.0
        slT = np.nan
        tpT = np.nan
        trp = np.nan
        tro = np.nan
        e_run = 0.0
        have_run = False
        if d != 0:
            # (b) distances for an entry placed now, 1685-1693
            if atrMode:
                atrNow = atr[j]
                slTicks = slAtrMult * atrNow / mt
                tpTicks = tpRMult * slTicks
                trAct = trActAtr * atrNow / mt
                trDist = trDistAtr * atrNow / mt
            else:
                slTicks = slPtsIn
                tpTicks = tpPtsIn
                trAct = trActPts
                trDist = trDistPts
            slUse = slTicks > 0.0                  # a comparison with na is false
            tpUse = tpTicks > 0.0
            trUse = trailOn and trDist > 0.0
            if slUse:
                slT = slTicks
            if tpUse:
                tpT = tpTicks
            if trUse:
                trp = trAct if trAct > 0.0 else 0.0        # math.max(trAct, 0.0)
                tro = trDist if trDist > 1.0 else 1.0      # math.max(trDist, 1.0)
            # strategy.equity seen by the script: realized - costs + open P/L at this close
            opl = 0.0
            for q in range(n_open):
                i = open_ids[q]
                opl += TI[i, I_DIR] * (cj - TF[i, T_EPX]) * TF[i, T_QTY] * pv
            e_run = cash + opl
            have_run = True
            # entryQty(), 1698-1705
            qv = qtyFixed
            if riskMode and slUse:
                riskPerContract = slTicks * mt * pv
                if riskPerContract > 0.0:
                    qv = e_run * riskPct / 100.0 / riskPerContract
                else:
                    qv = 0.0
            if qtyStep > 0.0:
                qv = math.floor(qv / qtyStep + 1e-9) * qtyStep
            if qtyMax < qv:
                qv = qtyMax
            for k in range(cnt):
                if room > 0 or opp:
                    if qv > 0.0:                    # placeEntry returned true
                        n_place += 1
                        room -= 1
                    else:
                        cn[C_SKIP_QTY] += 1
                else:
                    cn[C_SKIP_ROOM] += 1
            if opp and n_place > maxOpen - opent - n_pend and n_place > 0:
                cn[C_REV_OVER] += 1                 # a reversal bar that placed more than room allowed
        if full:
            dbg[j, D_OPENT] = opent
            dbg[j, D_NPEND] = n_pend
            dbg[j, D_ROOM] = maxOpen - opent - n_pend
            dbg[j, D_PLACED] = n_place
            dbg[j, D_POS] = pos_dir
            dbg[j, D_FLAGS] = (1 if do_close else 0) | (2 if n_time > 0 else 0) | (4 if d != 0 else 0)
        # (f) pending list, filled pass, 1783-1791 (the orders placed in this run are pushed below: they
        #     have no open trade at script time, so the pass never removes them)
        if useLimit and n_pend > 0 and opent > 0:
            w = 0
            for q in range(n_pend):
                tid = PI[q, Q_TID]
                if tid >= 0 and TI[tid, I_XB] == -1:
                    continue                        # its trade is open at script time: no longer pending
                if w != q:
                    for z in range(NPF):
                        PF[w, z] = PF[q, z]
                    for z in range(NPI):
                        PI[w, z] = PI[q, z]
                w += 1
            n_pend = w
        # ------------------------------------------------------------------ step 3: fills at the close
        if do_close or n_time > 0 or n_place > 0:
            if not have_run:
                opl = 0.0
                for q in range(n_open):
                    i = open_ids[q]
                    opl += TI[i, I_DIR] * (cj - TF[i, T_EPX]) * TF[i, T_QTY] * pv
                e_run = cash + opl
            eq_now = e_run
            if do_close:                            # strategy.close_all
                for q in range(n_open):
                    dc, xc = _close_trade(TF, TI, open_ids[q], j, cj, K_CLOSEALL, pv, c_fix, c_pct)
                    cash += dc
                    eq_now -= xc
                n_open = 0
                pos_dir = 0
                cn[C_CLOSE_ALL_BARS] += 1
            elif n_time > 0:                        # strategy.close(entry id), newest first as the Pine loop
                for q in range(n_open - 1, -1, -1):
                    if tflag[q]:
                        dc, xc = _close_trade(TF, TI, open_ids[q], j, cj, K_TIME, pv, c_fix, c_pct)
                        cash += dc
                        eq_now -= xc
                w = 0
                for q in range(n_open):
                    if not tflag[q]:
                        open_ids[w] = open_ids[q]
                        w += 1
                n_open = w
                if n_open == 0:
                    pos_dir = 0
            if n_place > 0:
                dr = -d if inv else d               # realLong, 1739
                fd = float(d)
                for kk in range(n_place):
                    cn[C_PLACED] += 1
                    if useLimit:
                        # limit (normal) / stop (inverted) entry at the candle low / high, 1764 / 1775
                        Ppx = l[j] if d > 0 else h[j]
                        if n_pend >= pcap:
                            cn[C_OVERFLOW] += 1
                            continue
                        qi = n_pend
                        n_pend += 1
                        PF[qi, P_PX] = Ppx
                        PF[qi, P_QTY] = qv
                        PF[qi, P_SLT] = slT
                        PF[qi, P_TPT] = tpT
                        PF[qi, P_TRP] = trp
                        PF[qi, P_TRO] = tro
                        PI[qi, Q_SIG] = j
                        PI[qi, Q_K] = kk + 1
                        PI[qi, Q_DIR] = d
                        PI[qi, Q_TID] = -1
                        cn[C_PEND_PLACED] += 1
                        if fd * cj <= fd * Ppx + tol:       # T6: the close satisfies the order
                            if n_open > 0 and pos_dir != dr:
                                cn[C_VIOL_SIDE] += 1
                            if n_open >= pyr:
                                cn[C_VIOL_PYR] += 1
                            if n_tr >= cap or n_open >= ocap:
                                cn[C_OVERFLOW] += 1
                                continue
                            tid = n_tr
                            n_tr += 1
                            ec = _open_trade(TF, TI, tid, dr, d, j, kk + 1, j, cj, qv, slT, tpT, trp, tro,
                                             eq_now, 1, mt, tol, c_fix, c_pct)
                            cash -= ec
                            eq_now -= ec
                            PI[qi, Q_TID] = tid
                            cn[C_PEND_FILLED] += 1
                            cn[C_PEND_CLOSEFILL] += 1
                            open_ids[n_open] = tid
                            n_open += 1
                            pos_dir = dr
                    else:
                        # market order: fills at this close; against the real position it closes ALL
                        # open trades first (T8)
                        if n_tr >= cap:
                            cn[C_OVERFLOW] += 1
                            continue
                        if n_open > 0 and pos_dir != dr:
                            for q in range(n_open):
                                i = open_ids[q]
                                dc, xc = _close_trade(TF, TI, i, j, cj, K_REVERSE, pv, c_fix, c_pct)
                                TI[i, I_XBY] = n_tr
                                cash += dc
                                eq_now -= xc
                            n_open = 0
                            pos_dir = 0
                            cn[C_REV_BARS] += 1
                        if n_open >= pyr:
                            cn[C_VIOL_PYR] += 1
                        if n_open >= ocap:
                            cn[C_OVERFLOW] += 1
                            continue
                        tid = n_tr
                        n_tr += 1
                        ec = _open_trade(TF, TI, tid, dr, d, j, kk + 1, j, cj, qv, slT, tpT, trp, tro,
                                         eq_now, 1, mt, tol, c_fix, c_pct)
                        cash -= ec
                        eq_now -= ec
                        open_ids[n_open] = tid
                        n_open += 1
                        pos_dir = dr
        # ------------------------------------------------------------------ step 4: bar close
        opl = 0.0
        sq = 0.0
        for q in range(n_open):
            i = open_ids[q]
            opl += TI[i, I_DIR] * (cj - TF[i, T_EPX]) * TF[i, T_QTY] * pv
            sq += TF[i, T_QTY]
        eq = cash + opl
        if n_open > 0:
            cn[C_EXPO] += 1
            notional = sq * cj
            if eq <= 0.0:
                max_expo = np.inf
            else:
                r = notional / eq
                if r > max_expo:
                    max_expo = r
            if notional > eq:
                cn[C_MARGIN] += 1
            if n_open > cn[C_MAX_OPEN]:
                cn[C_MAX_OPEN] = n_open
        if j == n - 1:
            # window end: every open trade is closed at this close; unfilled pending orders are dropped
            for q in range(n_pend):
                if PI[q, Q_TID] == -1:
                    cn[C_PEND_OPEN_END] += 1
            if n_open > 0:
                for q in range(n_open):
                    dc, xc = _close_trade(TF, TI, open_ids[q], j, cj, K_END, pv, c_fix, c_pct)
                    cash += dc
                n_open = 0
                pos_dir = 0
                eq = cash
        eq_close[j] = eq
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd
        if peak - eq > max_dd_abs:
            max_dd_abs = peak - eq
        if j == mid_j:
            eq_mid = eq
        eq_prev = eq
    fs[F_FINAL] = eq_prev
    fs[F_MID] = eq_mid
    fs[F_DD] = max_dd
    fs[F_DDABS] = max_dd_abs
    fs[F_MAXEXPO] = max_expo
    cn[C_NTR] = n_tr
    return TF[:n_tr], TI[:n_tr], eq_close, cn, fs, dbg


# ------------------------------------------------------------------------------------ prepare
_SIG_CACHE = {}
_SIG_CACHE_MAX = 2


def _signals(pair, tf, start, end, xp):
    """xpw.xpw_signals reduced to what the STRATEGY section reads (the pos_* / shape_* columns of
    the frame are dropped at once). Label strings go to a table; the lists become CSR codes."""
    key = (pair, tf, start, end, tuple(sorted((k, repr(v)) for k, v in xp.items())))
    S = _SIG_CACHE.get(key)
    if S is not None:
        return S
    sig = xpw.xpw_signals(pair, tf, start, end, xp)
    n = len(sig)
    rows = np.asarray(sig.index, dtype=np.int64)
    S = dict(rows=rows, t_close=sig['t_close'].to_numpy(np.int64).copy(),
             nLong=np.ascontiguousarray(sig['nLong'].to_numpy(np.int64)),
             nShort=np.ascontiguousarray(sig['nShort'].to_numpy(np.int64)),
             nLongRaw=sig['nLongRaw'].to_numpy(np.int64).copy(),
             nShortRaw=sig['nShortRaw'].to_numpy(np.int64).copy(),
             exitL=np.ascontiguousarray(sig['exitL'].to_numpy(bool)),
             exitS=np.ascontiguousarray(sig['exitS'].to_numpy(bool)))
    table = ['']
    code = {'': 0}

    def cd(s):
        v = code.get(s)
        if v is None:
            v = len(table)
            code[s] = v
            table.append(s)
        return v

    for name, col, cnt in (('long', 'longSrc', S['nLongRaw']), ('short', 'shortSrc', S['nShortRaw'])):
        ptr = np.zeros(n + 1, np.int64)
        np.cumsum(cnt, out=ptr[1:])
        codes = np.zeros(int(ptr[-1]), np.int32)
        lists = sig[col].to_numpy()
        for r in np.nonzero(cnt)[0].tolist():
            lst = lists[r]
            if len(lst) != cnt[r]:
                raise RuntimeError('xpw_signals: %s list size differs from its count' % col)
            for z, s in enumerate(lst):
                codes[ptr[r] + z] = cd(s)
        S[name + '_ptr'] = ptr
        S[name + '_code'] = codes
    for name, col, flag in (('exitL_code', 'exitLSrc', S['exitL']), ('exitS_code', 'exitSSrc', S['exitS'])):
        codes = np.zeros(n, np.int32)
        vals = sig[col].to_numpy()
        for r in np.nonzero(flag)[0].tolist():
            codes[r] = cd(vals[r])
        S[name] = codes
    S['src_table'] = table
    del sig
    if len(_SIG_CACHE) >= _SIG_CACHE_MAX:
        _SIG_CACHE.pop(next(iter(_SIG_CACHE)))
    _SIG_CACHE[key] = S
    return S


def _split_prepare(params):
    xp, fp, other = {}, {}, {}
    for k, v in (params or {}).items():
        if k in _SIM_KEYS:
            raise ValueError('%r is an ORDER / EXIT input: give it to simulate(), not to prepare()' % (k,))
        if k not in _PREP_KEYS:
            raise ValueError('unknown input %r' % (k,))
        if k in _XPW_KEYS:
            xp[k] = v
        if k in _FGF_KEYS:
            fp[k] = v
        if k in ('start', 'end'):
            other[k] = v
    return xp, fp, other


def prepare(pair, chart_tf, params=None):
    """Signals (xpw.xpw_signals), filter permissions (fgf.fgf_permissions) and the window bars:
    everything that does not depend on an ORDER / EXIT input. params: the SIGNAL inputs by Pine name
    (xpw.DEFAULTS and fgf.DEFAULTS keys, fgfOn default true), start / end (t_close window; default
    WINDOWS[pair]). Display inputs are accepted and ignored; any other key raises ValueError."""
    chart_tf = str(chart_tf)
    if pair not in WINDOWS:
        raise ValueError('pair %r' % (pair,))
    xp, fp, other = _split_prepare(params)
    start = int(other['start']) if other.get('start') is not None else WINDOWS[pair][0]
    end = int(other['end']) if other.get('end') is not None else WINDOWS[pair][1]
    tc_all = read_bars(pair, chart_tf, ('t_close',))['t_close']
    w0 = int(np.searchsorted(tc_all, start, side='left'))
    w1 = int(np.searchsorted(tc_all, end, side='right'))
    n = w1 - w0
    del tc_all
    if n <= 0:
        raise ValueError('empty window')
    S = _signals(pair, chart_tf, start, end, xp)
    fgf_res = dict(fgf.DEFAULTS)
    fgf_res.update(fp)
    if bool(fgf_res['fgfOn']):
        perm = fgf.fgf_permissions(pair, chart_tf, start, end, fp)
        if len(perm) != n or perm.index[0] != w0:
            raise RuntimeError('fgf_permissions rows do not match the window')
        buyOk = np.ascontiguousarray(perm['buyOk'].to_numpy(bool))
        sellOk = np.ascontiguousarray(perm['sellOk'].to_numpy(bool))
        del perm
    else:
        # line 953-954: fgfBuyOk = not fgfOn or (...): true on every bar
        buyOk = np.ones(n, np.bool_)
        sellOk = np.ones(n, np.bool_)
    # the window bars (read after the signals, so that the whole file is not held meanwhile)
    b = read_bars(pair, chart_tf)
    sl = slice(w0, w1)
    b = {k: np.ascontiguousarray(v[sl]).copy() for k, v in b.items()}
    if len(S['rows']) != n or S['rows'][0] != w0 or not np.array_equal(S['t_close'], b['t_close']):
        raise RuntimeError('xpw_signals rows do not match the window')
    xpw_res = dict(xpw.DEFAULTS)
    xpw_res.update(xp)
    res = dict(xpw_res)
    res.update(fgf_res)
    res.update(start=start, end=end)
    tc = b['t_close']
    mid = start + (end - start) // 2
    P = dict(pair=pair, tf=chart_tf, start=start, end=end, mid=mid,
             mid_j=int(np.searchsorted(tc, mid, side='right')) - 1,
             n=n, w0=w0, w1=w1, rows=np.arange(w0, w1, dtype=np.int64),
             open=b['open'], high=b['high'], low=b['low'], close=b['close'], t_open=b['t_open'], t_close=tc,
             nLong=S['nLong'], nShort=S['nShort'], nLongRaw=S['nLongRaw'], nShortRaw=S['nShortRaw'],
             exitL=S['exitL'], exitS=S['exitS'], buyOk=buyOk, sellOk=sellOk,
             long_ptr=S['long_ptr'], long_code=S['long_code'], short_ptr=S['short_ptr'],
             short_code=S['short_code'], exitL_code=S['exitL_code'], exitS_code=S['exitS_code'],
             src_table=S['src_table'], params=res, _atr={}, sub=None)
    return P


def make_P(o, h, l, c, nLong=None, nShort=None, exitL=None, exitS=None, buyOk=None, sellOk=None,
           atr=None, pair='BTC', t_close=None, row0=0, longSrc=None, shortSrc=None):
    """A P for hand-made bars (unit tests and hand traces). nLong / nShort are the label counts
    AFTER the both-sides zeroing; atr: {atrLen: array} (ATR mode) or None (Points mode only)."""
    o = np.ascontiguousarray(np.asarray(o, np.float64))
    n = len(o)
    z = np.zeros(n, np.int64)
    f = np.zeros(n, np.bool_)
    t = np.ones(n, np.bool_)
    nL = z.copy() if nLong is None else np.ascontiguousarray(np.asarray(nLong, np.int64))
    nS = z.copy() if nShort is None else np.ascontiguousarray(np.asarray(nShort, np.int64))
    tc = (np.arange(n, dtype=np.int64) + 1) * 60 if t_close is None else np.asarray(t_close, np.int64)
    table = ['']
    ptrs, codes = {}, {}
    for name, cnt, src in (('long', nL, longSrc), ('short', nS, shortSrc)):
        ptr = np.zeros(n + 1, np.int64)
        np.cumsum(cnt, out=ptr[1:])
        cd = np.zeros(int(ptr[-1]), np.int32)
        for r in range(n):
            for k in range(int(cnt[r])):
                s = src[r][k] if src is not None else '%s label %d-%d' % (name, r + row0, k + 1)
                table.append(s)
                cd[ptr[r] + k] = len(table) - 1
        ptrs[name], codes[name] = ptr, cd
    start, end = int(tc[0]), int(tc[-1])
    mid = start + (end - start) // 2
    return dict(pair=pair, tf='syn', start=start, end=end, mid=mid,
                mid_j=int(np.searchsorted(tc, mid, side='right')) - 1, n=n, w0=row0, w1=row0 + n,
                rows=np.arange(row0, row0 + n, dtype=np.int64), open=o,
                high=np.ascontiguousarray(np.asarray(h, np.float64)),
                low=np.ascontiguousarray(np.asarray(l, np.float64)),
                close=np.ascontiguousarray(np.asarray(c, np.float64)),
                t_open=tc - 60, t_close=tc, nLong=nL, nShort=nS, nLongRaw=nL.copy(), nShortRaw=nS.copy(),
                exitL=f.copy() if exitL is None else np.ascontiguousarray(np.asarray(exitL, np.bool_)),
                exitS=f.copy() if exitS is None else np.ascontiguousarray(np.asarray(exitS, np.bool_)),
                buyOk=t.copy() if buyOk is None else np.ascontiguousarray(np.asarray(buyOk, np.bool_)),
                sellOk=t.copy() if sellOk is None else np.ascontiguousarray(np.asarray(sellOk, np.bool_)),
                long_ptr=ptrs['long'], long_code=codes['long'], short_ptr=ptrs['short'],
                short_code=codes['short'], exitL_code=np.zeros(n, np.int32), exitS_code=np.zeros(n, np.int32),
                src_table=table, params={}, _atr=dict(atr or {}), sub=None)


# ------------------------------------------------------------------- 1-minute sub-bars (path 'mag')
_NO_SUB = (np.zeros(1, np.int64), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0))


def sub_bars(pair, t_open, t_close, o=None, h=None, l=None, c=None, check=True):
    """The 1-minute sub-bars of chart bars given by their t_open / t_close: the rows of
    data/<pair>_1.parquet with t_open in [chart t_open, chart t_close) (SWEEP_AH_SPEC.md section 2,
    the rule of hrd.sub_bars). Returns (ptr, so, sh, sl, sc, qlo, qhi): ptr int64 (n + 1), the
    sub-bars of chart bar k are [ptr[k], ptr[k+1]) of the contiguous arrays so / sh / sl / sc;
    qlo / qhi = the lowest low / highest high of each chart bar's sub-bars.
    Every chart bar must have at least one sub-bar. With check (and the chart OHLC given), every
    chart bar must equal its sub-bars: first open, highest high, lowest low, last close
    (build_bars.py built the chart files from the 1-minute file), and every sub-bar must have
    low <= open, close <= high."""
    t_open = np.asarray(t_open, np.int64)
    t_close = np.asarray(t_close, np.int64)
    n = len(t_open)
    mt_ = read_bars(pair, '1', ('t_open',))['t_open']
    s = np.searchsorted(mt_, t_open, side='left')
    e = np.searchsorted(mt_, t_close, side='left')
    del mt_
    ln = (e - s).astype(np.int64)
    if n == 0 or (ln <= 0).any():
        raise ValueError('%s: %d chart bars without 1-minute sub-bars' % (pair, int((ln <= 0).sum())))
    ptr = np.zeros(n + 1, np.int64)
    np.cumsum(ln, out=ptr[1:])
    a0, a1 = int(s.min()), int(e.max())
    m = read_bars(pair, '1', ('open', 'high', 'low', 'close'))
    m = {k: v[a0:a1] for k, v in m.items()}
    idx = np.repeat(s - a0 - ptr[:-1], ln) + np.arange(int(ptr[-1]), dtype=np.int64)
    so = np.ascontiguousarray(m['open'][idx])
    sh = np.ascontiguousarray(m['high'][idx])
    sl = np.ascontiguousarray(m['low'][idx])
    sc = np.ascontiguousarray(m['close'][idx])
    del m, idx
    st = ptr[:-1]
    qlo = np.ascontiguousarray(np.minimum.reduceat(sl, st))
    qhi = np.ascontiguousarray(np.maximum.reduceat(sh, st))
    if check:
        if not ((sl <= so) & (sl <= sc) & (sh >= so) & (sh >= sc)).all():
            raise ValueError('%s: 1-minute bars with open / close outside [low, high]' % pair)
        if o is not None:
            ok = ((so[st] == np.asarray(o)) & (sc[ptr[1:] - 1] == np.asarray(c))
                  & (qhi == np.asarray(h)) & (qlo == np.asarray(l)))
            if not ok.all():
                raise ValueError('%s: %d chart bars differ from their 1-minute sub-bars' % (pair, int((~ok).sum())))
    return ptr, so, sh, sl, sc, qlo, qhi


_SUB_CACHE = {}


def get_sub(P):
    """The sub-bars of P's window (built once, kept in P['sub'] and shared by the P's of the same
    pair / chart / window)."""
    sub = P.get('sub')
    if sub is None:
        if P['tf'] == 'syn':
            raise ValueError("make_P: path 'mag' needs P['sub'] (ptr, so, sh, sl, sc, qlo, qhi)")
        key = (P['pair'], P['tf'], P['w0'], P['w1'])
        sub = _SUB_CACHE.get(key)
        if sub is None:
            sub = sub_bars(P['pair'], P['t_open'], P['t_close'], P['open'], P['high'], P['low'], P['close'])
            _SUB_CACHE.clear()                                   # one window at a time (memory)
            _SUB_CACHE[key] = sub
        P['sub'] = sub
    return sub


def fake_sub(P):
    """One sub-bar per chart bar, the chart bar itself (tests: path 'mag' on it must equal 'tv')."""
    n = P['n']
    return (np.arange(n + 1, dtype=np.int64), P['open'], P['high'], P['low'], P['close'], P['low'], P['high'])


# ------------------------------------------------------------------------------------ simulate
def resolve_x(x=None):
    """The ORDER / EXIT inputs with the Pine defaults, validated as the Pine inputs are."""
    X = dict(X_DEFAULTS)
    x = dict(x or {})
    if 'inv' in x:
        v = x.pop('inv')
        if 'xpwInv' in x and bool(x['xpwInv']) != bool(v):
            raise ValueError("'inv' and 'xpwInv' disagree")
        x['xpwInv'] = v
    for k, v in x.items():
        if k not in X_DEFAULTS:
            if k in _PREP_KEYS:
                raise ValueError('%r is a prepare() input: it cannot be given to simulate()' % (k,))
            raise ValueError('unknown input %r' % (k,))
        X[k] = v
    if X['tradeDir'] not in TRADE_DIRS:
        raise ValueError('tradeDir %r not one of %r' % (X['tradeDir'], TRADE_DIRS))
    if X['entryFill'] not in ENTRY_FILLS:
        raise ValueError('entryFill %r not one of %r' % (X['entryFill'], ENTRY_FILLS))
    if X['exitUnit'] not in EXIT_UNITS:
        raise ValueError('exitUnit %r not one of %r' % (X['exitUnit'], EXIT_UNITS))
    if X['qtyMode'] not in QTY_MODES:
        raise ValueError('qtyMode %r not one of %r' % (X['qtyMode'], QTY_MODES))
    if X['cost'] not in COSTS:
        raise ValueError('cost %r not one of %r' % (X['cost'], tuple(COSTS)))
    if X['path'] not in ('tv', 'mag'):
        raise ValueError("path %r not 'tv' or 'mag'" % (X['path'],))
    for k in _X_INTS:
        v = X[k]
        if isinstance(v, bool) or int(v) != v:
            raise ValueError('%s must be an integer, got %r' % (k, v))
        X[k] = int(v)
    for k in _X_FLOATS:
        v = float(X[k])
        if not (v >= 0.0) or math.isinf(v):
            raise ValueError('%s must be a number >= 0, got %r' % (k, X[k]))
        X[k] = v
    if not 1 <= X['maxOpen'] <= 100:
        raise ValueError('maxOpen must be 1..100')
    if not 1 <= X['limitBars'] <= 500:
        raise ValueError('limitBars must be 1..500')
    if X['atrLen'] < 1:
        raise ValueError('atrLen must be >= 1')
    if X['timeStop'] < 0:
        raise ValueError('timeStop must be >= 0')
    for k in ('oppCloses', 'trailOn', 'xpwInv'):
        X[k] = bool(X[k])
    return X


def simulate(P, x=None, full=False):
    """The STRATEGY section + the broker on prepare()'s arrays. x: the ORDER / EXIT inputs by Pine
    name (X_DEFAULTS), plus path ('tv' | 'mag'), cost ('tv' | 'ours' | 'stress'), inv (alias of
    xpwInv). A prepare() key in x raises. full=True adds per-bar debug columns (R['dbg']).
    path 'mag' needs the 1-minute sub-bars: get_sub(P) builds them once and keeps them in P['sub']
    (a test may set P['sub'] itself)."""
    X = resolve_x(x)
    mag = X['path'] == 'mag'
    ptr, so, sh, sl_, sc, qlo, qhi = get_sub(P) if mag else _NO_SUB
    inv = X['xpwInv']
    xpwBuyOk = X['tradeDir'] != "Short only (sell only)"          # 1646
    xpwSellOk = X['tradeDir'] != "Long only (buy only)"           # 1647
    allowLong = xpwSellOk if inv else xpwBuyOk                    # 1648
    allowShort = xpwBuyOk if inv else xpwSellOk                   # 1649
    atrMode = X['exitUnit'] == "ATR"
    if atrMode:
        atr = atr_window(P, X['atrLen'])
    else:
        atr = P['close']                                          # not read in Points mode
    c_fix, c_pct = COSTS[X['cost']][P['pair']]
    nL, nS, buyOk, sellOk = P['nLong'], P['nShort'], P['buyOk'], P['sellOk']
    cap = P.get('_cap')
    if cap is None:
        cap = int(nL[buyOk].sum() + nS[sellOk].sum()) + 1         # every label of a gated bar, at most
        P['_cap'] = cap
    TF, TI, eq, cn, fs, dbg = _kernel(
        P['open'], P['high'], P['low'], P['close'], nL, nS, P['exitL'], P['exitS'], buyOk, sellOk, atr,
        allowLong, allowShort, X['oppCloses'], X['entryFill'] == "Limit at label price", X['limitBars'],
        X['maxOpen'], atrMode, X['slPtsIn'], X['tpPtsIn'], X['slAtrMult'], X['tpRMult'], X['trailOn'],
        X['trActPts'], X['trDistPts'], X['trActAtr'], X['trDistAtr'], X['timeStop'],
        X['qtyMode'] == "Risk", X['qtyFixed'], X['riskPct'], X['qtyMax'], X['qtyStep'],
        inv, MINTICK, POINTVALUE, INITIAL_CAPITAL, c_fix, c_pct, PYRAMIDING, TOL, cap, int(P['mid_j']),
        bool(full), mag, ptr, so, sh, sl_, sc, qlo, qhi)
    if cn[C_VIOL_SUB]:
        raise RuntimeError('path mag: %d chart bars without 1-minute sub-bars' % cn[C_VIOL_SUB])
    if cn[C_OVERFLOW]:
        raise RuntimeError('internal capacity exceeded (%d)' % cn[C_OVERFLOW])
    if cn[C_VIOL_PYR]:
        raise RuntimeError('pyramiding=100 would bind (%d same-side entries beyond it): SPEC T13' % cn[C_VIOL_PYR])
    if cn[C_VIOL_SIDE]:
        raise RuntimeError('a pending entry filled against an open position (%d): SPEC 4.3' % cn[C_VIOL_SIDE])
    R = dict(TF=TF, TI=TI, eq=eq, cn=cn, fs=fs, x=X)
    if full:
        R['dbg'] = dbg
    return R


# ------------------------------------------------------------------------------- trades / summary
def _label_codes(P, sd, sig, k):
    """Table code of the label of each trade: longSrc[k-1] / shortSrc[k-1] of its placement bar."""
    out = np.zeros(len(sd), np.int64)
    lg = sd > 0
    out[lg] = P['long_code'][P['long_ptr'][sig[lg]] + k[lg] - 1]
    out[~lg] = P['short_code'][P['short_ptr'][sig[~lg]] + k[~lg] - 1]
    return out


def trades(P, R, comments=True):
    """One row per entry fill, in fill order (entry_bar, sig_bar, k). dir = the REAL side."""
    TF, TI, X = R['TF'], R['TI'], R['x']
    inv = X['xpwInv']
    nt = len(TI)
    rows, tc = P['rows'], P['t_close']
    d = TI[:, I_DIR]
    sd = TI[:, I_SD]
    sig = TI[:, I_SIG]
    k = TI[:, I_K]
    eb = TI[:, I_EB]
    xb = TI[:, I_XB]
    xk = TI[:, I_XK]
    fdir = d.astype(np.float64)
    tab = P['src_table']
    lc = _label_codes(P, sd, sig, k) if nt else np.zeros(0, np.int64)
    src = [tab[v] for v in lc.tolist()]
    sig_rows = rows[sig] if nt else np.zeros(0, np.int64)
    ids = [('L' if dd > 0 else 'S') + str(r) + '-' + str(kk) for dd, r, kk in zip(d.tolist(), sig_rows.tolist(), k.tolist())]
    cost = TF[:, T_EC] + TF[:, T_XC]
    pnl = TF[:, T_GROSS] - cost
    slt = TF[:, T_SLT]
    with np.errstate(invalid='ignore', divide='ignore'):
        Rm = pnl / (TF[:, T_QTY] * slt * MINTICK * POINTVALUE)
    df = pd.DataFrame({
        'id': ids,
        'dir': d,
        'sig_dir': sd,
        'src': src,
        'sig_bar': sig_rows,
        'k': k,
        'entry_bar': rows[eb] if nt else np.zeros(0, np.int64),
        'entry_time': tc[eb],
        'entry_px': TF[:, T_EPX],
        'qty': TF[:, T_QTY],
        'exit_bar': rows[xb] if nt else np.zeros(0, np.int64),
        'exit_time': tc[xb],
        'exit_px': TF[:, T_XPX],
        'exit_kind': [KINDS[v] for v in xk.tolist()],
        'pnl': pnl,
        'pnl_gross': TF[:, T_GROSS],
        'costs': cost,
        'eq_before': TF[:, T_EQB],
        'R': Rm,
        'sl_px': fdir * TF[:, T_SL],
        'tp_px': fdir * TF[:, T_TP],
        'tr_act_px': fdir * TF[:, T_A],
        'tr_off': TF[:, T_OFF],
        'sl_ticks': TF[:, T_SLT],
        'fill_at_close': TI[:, I_ECL] != 0,
    })
    if comments:
        useLimit = X['entryFill'] == "Limit at label price"
        tag = (' (inv)' if inv else '') + ((' stop @ label' if inv else ' @ label') if useLimit else '')
        ecmt = [('ENTER LONG' if dd > 0 else 'ENTER SHORT') + tag + ' | ' + s for dd, s in zip(d.tolist(), src)]
        xcmt = []
        lp, lcod, sp, scod = P['long_ptr'], P['long_code'], P['short_ptr'], P['short_code']
        for t in range(nt):
            kind = xk[t]
            if kind == K_SL:
                xcmt.append('SL | ' + src[t])
            elif kind == K_TP:
                xcmt.append('TP | ' + src[t])
            elif kind == K_TRAIL:
                xcmt.append('trail | ' + src[t])
            elif kind == K_TIME:
                xcmt.append('time stop | ' + ecmt[t])
            elif kind == K_REVERSE:
                xcmt.append(ecmt[TI[t, I_XBY]])
            elif kind == K_CLOSEALL:
                j = xb[t]
                if sd[t] > 0:              # closeL (the normal-frame long side), line 1678
                    if P['exitL'][j]:
                        xcmt.append('exit | ' + tab[P['exitL_code'][j]])
                    else:
                        xcmt.append('opp ENTER | ' + (tab[scod[sp[j]]] if sp[j + 1] > sp[j] else ''))
                else:                      # closeS, line 1680
                    if P['exitS'][j]:
                        xcmt.append('exit | ' + tab[P['exitS_code'][j]])
                    else:
                        xcmt.append('opp ENTER | ' + (tab[lcod[lp[j]]] if lp[j + 1] > lp[j] else ''))
            else:
                xcmt.append('end')
        df['entry_comment'] = ecmt
        df['exit_comment'] = xcmt
    return df


def _fifo_exits(xb, xk):
    """Trades with exit kind sl / tp / trail / time that have an earlier row (fill order) still open
    when they exit: an earlier row with a larger exit bar, or the same exit bar and a close fill
    (time, close_all, reverse, end) while this row's exit is intrabar (sl, tp, trail)."""
    if len(xb) == 0:
        return 0
    closefill = (xk >= K_TIME).astype(np.int64)
    key = 2 * xb + closefill
    pm = np.maximum.accumulate(key)
    prev = np.empty_like(pm)
    prev[0] = -1
    prev[1:] = pm[:-1]
    return int(((xk <= K_TIME) & (prev > key)).sum())


def summary(P, R):
    """The summary of SPEC_xpw23 section 8, from the kernel arrays (no DataFrame)."""
    TF, TI, X, cn, fs = R['TF'], R['TI'], R['x'], R['cn'], R['fs']
    init = INITIAL_CAPITAL
    nt = len(TI)
    cost = TF[:, T_EC] + TF[:, T_XC]
    pnl = TF[:, T_GROSS] - cost
    d = TI[:, I_DIR]
    eb = TI[:, I_EB]
    xb = TI[:, I_XB]
    xk = TI[:, I_XK]
    final = float(fs[F_FINAL])
    eq_mid = float(fs[F_MID])
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    kc = np.bincount(xk, minlength=len(KINDS)) if nt else np.zeros(len(KINDS), np.int64)
    first = P['t_close'][eb] <= P['mid']
    out = dict(
        pair=P['pair'], tf=P['tf'], start=int(P['start']), end=int(P['end']), bars=int(P['n']),
        trades=nt,
        net_pct=(final - init) / init * 100.0,
        pf=(gp / gl) if gl > 0 else (np.inf if gp > 0 else np.nan),
        win_pct=float((pnl > 0).mean() * 100.0) if nt else np.nan,
        max_dd_pct=float(fs[F_DD] * 100.0),
        max_dd_init_pct=float(fs[F_DDABS] / init * 100.0),
        long=int((d > 0).sum()), short=int((d < 0).sum()),
        raw_long=int(cn[C_RAW_L]), raw_short=int(cn[C_RAW_S]),
        blocked_long=int(cn[C_BLK_L]), blocked_short=int(cn[C_BLK_S]),
    )
    for i, nm in enumerate(KINDS[1:], 1):
        out['exit_' + nm] = int(kc[i])
    out['avg_bars_held'] = float((xb - eb).mean()) if nt else np.nan
    out['exposure'] = float(cn[C_EXPO] / P['n'])
    out['half1_pct'] = (eq_mid - init) / init * 100.0
    out['half2_pct'] = (final - eq_mid) / init * 100.0
    n1 = int(first.sum())
    out['h1_trades'] = n1
    out['h2_trades'] = nt - n1
    risk_stop = X['qtyMode'] == "Risk" and ((X['slAtrMult'] > 0) if X['exitUnit'] == "ATR" else (X['slPtsIn'] > 0))
    if risk_stop:
        out['halves_rule'] = 'compound'
        eqb = TF[:, T_EQB]
        for nm, m in (('h1r_pct', first), ('h2r_pct', ~first)):
            if not m.any():
                out[nm] = 0.0
            elif (eqb[m] <= 0).any():
                out[nm] = np.nan
            else:
                out[nm] = float((np.prod(1.0 + pnl[m] / eqb[m]) - 1.0) * 100.0)
    else:
        out['halves_rule'] = 'additive'
        out['h1r_pct'] = float(100.0 * pnl[first].sum() / init) if n1 else 0.0
        out['h2r_pct'] = float(100.0 * pnl[~first].sum() / init) if nt - n1 else 0.0
    out['final_equity'] = final
    out['costs'] = float(cost.sum())
    slt = TF[:, T_SLT]
    hs = ~np.isnan(slt)
    with np.errstate(invalid='ignore', divide='ignore'):
        Rm = pnl / (TF[:, T_QTY] * slt * MINTICK * POINTVALUE)
    out['net_R'] = float(Rm[hs].sum())
    out['h1_R'] = float(Rm[hs & first].sum())
    out['h2_R'] = float(Rm[hs & ~first].sum())
    out['n_R'] = int(hs.sum())
    out['placed'] = int(cn[C_PLACED])
    out['skipped_room'] = int(cn[C_SKIP_ROOM])
    out['skipped_qty'] = int(cn[C_SKIP_QTY])
    out['pend_placed'] = int(cn[C_PEND_PLACED])
    out['pend_filled'] = int(cn[C_PEND_FILLED])
    out['pend_filled_at_close'] = int(cn[C_PEND_CLOSEFILL])
    out['pend_cancelled'] = int(cn[C_PEND_CANCELLED])
    out['pend_open_end'] = int(cn[C_PEND_OPEN_END])
    out['close_all_bars'] = int(cn[C_CLOSE_ALL_BARS])
    out['max_open'] = int(cn[C_MAX_OPEN])
    out['zero_length'] = int((eb == xb).sum())
    out['max_expo'] = float(fs[F_MAXEXPO])
    out['margin_bars'] = int(cn[C_MARGIN])
    out['fifo_exits'] = _fifo_exits(xb, xk)
    # extra diagnostics (not in the SPEC list)
    out['pend_ghosts'] = int(cn[C_GHOSTS])
    out['pend_cancel_stale'] = int(cn[C_CANCEL_STALE])        # 'against' when both hold
    out['pend_cancel_against'] = int(cn[C_CANCEL_AGAINST])
    out['reverse_bars'] = int(cn[C_REV_BARS])
    out['reverse_over_room'] = int(cn[C_REV_OVER])
    # labels on the bars that keep them (after the both-sides zeroing), as SPEC 4.1 counts them
    out['labels_long'] = int(P['nLong'].sum())
    out['labels_short'] = int(P['nShort'].sum())
    out['both_cancel_bars'] = int(((P['nLongRaw'] > 0) & (P['nShortRaw'] > 0)).sum())
    out['path'] = X['path']
    out['cost'] = X['cost']
    return out


def free_caches(deep=True):
    """Drop every cache this module filled (signals, ATR arrays, sub-bars) and, with deep, the pure
    memo caches of the modules it calls (xpw.clear_cache(), fgf's bar / direction / filter series),
    then hand the freed memory back to the system. Results never change; the next prepare() only
    recomputes. Use it between prepare() calls with DIFFERENT signal inputs on a 1-minute chart:
    one xpw.xpw_signals call there peaks near 2.4 GB by itself, so a process that still holds the
    caches of earlier calls passes 3 GB."""
    import gc
    _SIG_CACHE.clear()
    _ATR_CACHE.clear()
    _SUB_CACHE.clear()
    if deep:
        xpw.clear_cache()
        for nm in ('_BARS', '_DIR', '_FILTER'):
            c = getattr(fgf, nm, None)
            if isinstance(c, dict):
                c.clear()
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL('libc.so.6').malloc_trim(0)
    except Exception:
        pass


def split_params(params):
    """One dict -> (prepare keys, simulate keys). Unknown keys raise ValueError."""
    pp, xx = {}, {}
    for k, v in (params or {}).items():
        if k in _SIM_KEYS:
            xx[k] = v
        elif k in _PREP_KEYS:
            pp[k] = v
        else:
            raise ValueError('unknown input %r' % (k,))
    return pp, xx


def run(pair, chart_tf, params=None):
    """prepare + simulate with one dict. Returns (trades DataFrame, summary dict)."""
    pp, xx = split_params(params)
    P = prepare(pair, chart_tf, pp)
    R = simulate(P, xx)
    return trades(P, R), summary(P, R)


def fmt(s):
    return ("%s %s: bars=%d trades=%d (L %d / S %d) net=%.3f%% pf=%.3f win=%.1f%% maxDD=%.2f%% "
            "raw L/S=%d/%d blocked L/S=%d/%d sl=%d tp=%d trail=%d time=%d close_all=%d reverse=%d end=%d"
            % (s['pair'], s['tf'], s['bars'], s['trades'], s['long'], s['short'], s['net_pct'], s['pf'],
               s['win_pct'], s['max_dd_pct'], s['raw_long'], s['raw_short'], s['blocked_long'],
               s['blocked_short'], s['exit_sl'], s['exit_tp'], s['exit_trail'], s['exit_time'],
               s['exit_close_all'], s['exit_reverse'], s['exit_end']))


if __name__ == '__main__':
    import time as _time
    for _pair in ('BTC', 'XAU'):
        _t0 = _time.time()
        _P = prepare(_pair, '60')
        _t1 = _time.time()
        _R = simulate(_P)
        _t2 = _time.time()
        _R = simulate(_P)
        _t3 = _time.time()
        print(fmt(summary(_P, _R)))
        print('  prepare %.2fs, first simulate %.2fs, simulate %.4fs' % (_t1 - _t0, _t2 - _t1, _t3 - _t2))
