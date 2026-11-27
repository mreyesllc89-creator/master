"""verify_inv_xpw.py: INDEPENDENT verification of the Update 1 option "Inverted direction: opposite
side at the same entries" (Pine xpwInv) in the xpw replica (engine.py + sweep_core.py).

The reference below is a plain pure-Python transcription of the STRATEGY section of
/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine AT HEAD (lines 1480-1628,
"Signal tick" entry mode, history = one script run per chart bar at its close) plus a plain broker
(SPEC.md rules 1-10, SWEEP_SPEC.md 'mag' paragraph). It was written before reading the option's
code in engine.py / sweep_core.py and uses none of their order / exit code:

  taken from the replica (inputs only)   the xpw_signals frame (longSrc / shortSrc lists, exitL /
                                         exitS, their sources) and the fgf_permissions frame
                                         (buyOk / sellOk), via sweep_core.load_inputs / load_sig or
                                         xpw.xpw_signals; the chart OHLC and 1-minute data files
  written here from the Pine             nLong / nShort and the cancel rule, allowLong / allowShort
                                         (with xpwInv), sigLong / sigShort, fgfBlkL / fgfBlkS,
                                         goLong / goShort, oppL / oppS, xpwPosN, closeL / closeS and
                                         their comments, room, `room > 0 or xpwPosN < 0`, the ids,
                                         placeEntry (realLong, comments, tick distances), and the
                                         broker: market fills at the close, reversal, close_all,
                                         pyramiding, trailing stop / stop loss per REAL side (longs
                                         and shorts written out separately, no negation), both fill
                                         paths ('tv' = one O-H-L-C / O-L-H-C path per chart bar,
                                         'mag' = the 1-minute sub-bars, rebuilt here from
                                         data/<PAIR>_1.parquet), the money model (10% of closed
                                         equity per entry) with the three cost modes.

Modes:
  python3 -I verify_inv_xpw.py compare PAIR TF [START END] [--n 12] [--seed S]
        filter off / on x option off / on x paths tv / mag x (default exits + corner settings + n
        random exit settings): reference vs sweep_core.run_cfg (trade arrays) and its metrics_raw
        (tv0 / cost / stress), and vs engine.backtest (full trade table: ids, real side, comments,
        levels, P/L, funnel summary) + run_tf.metrics.
  python3 -I verify_inv_xpw.py extra PAIR TF [START END]
        engine.backtest with other inputs (Trade direction, Opposite ENTER closes, Blocked entry
        still closes, Max open entries, Reverse every label, "exit only" rows), option on and off.
  python3 -I verify_inv_xpw.py json PAIR TF
        the runner's out/inv_xpw_<PAIR>_<TF>.json against the reference.
  python3 -I verify_inv_xpw.py trace
        hand traces of 5 inverted trades (bars printed).
  python3 -I verify_inv_xpw.py sens
        sensitivity of the comparison: the reference with one line of the option broken at a time
        (a mutated copy of this file's reference section) must be told apart from the replica.
Exit status 1 on any mismatch. Windows: the full ones of run_tf.WINDOWS, except BTC 15 = 2025-09-01 ..
2025-12-01 (3 months) unless START END are given. Logs of the runs made: vix_*.log next to this file.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)

MT = 0.01                       # syminfo.mintick (both pairs)
TOL = MT * 1e-6                 # touch tolerance of the replica (SPEC / engine docstring)
LONG_ONLY = 'Long only (buy only)'
SHORT_ONLY = 'Short only (sell only)'
PYRAMIDING = 100                # strategy(..., pyramiding=100)
CAP0 = 10000.0                  # initial_capital
FRAC = 0.10                     # default_qty_value 10 (% of equity)

# Pine input defaults (lines 377-390, 408, 996, 999)
PINE = dict(tradeDir='Both', oppCloses=True, fgfOn=True, fgfBlkClose=True, maxOpen=20,
            trailOn=True, trailUnit='price', trailAct=2.0, trailOff=1.0, slOn=False, slDist=3.0,
            xpwInv=False)

FULL = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}
BTC15_3M = (1756684800, 1764547200)        # 2025-09-01 .. 2025-12-01 UTC


# =============================================================================== inputs
def _lists(col):
    return [list(x) if x is not None and not (isinstance(x, float) and math.isnan(x)) else [] for x in col]


def minute_table(pair, tf, rows):
    """Per chart row: the list of (open, high, low, close, t_open) 1-minute bars with chart t_open <=
    minute t_open < chart t_close (each minute goes to the last chart bar opened at or before it)."""
    ch = pd.read_parquet(os.path.join(W, 'data', '%s_%s.parquet' % (pair, tf)),
                         columns=['open', 'high', 'low', 'close', 't_open', 't_close']).reset_index(drop=True)
    ch = ch.iloc[np.asarray(rows)]
    bo = ch['t_open'].to_numpy(np.int64)
    bc = ch['t_close'].to_numpy(np.int64)
    m = pd.read_parquet(os.path.join(W, 'data', '%s_1.parquet' % pair),
                        columns=['open', 'high', 'low', 'close', 't_open'])
    mt_ = m['t_open'].to_numpy(np.int64)
    sel = (mt_ >= bo[0]) & (mt_ < bc[-1])
    m = m[sel]
    mt_ = mt_[sel]
    owner = np.searchsorted(bo, mt_, side='right') - 1
    keep = (owner >= 0) & (mt_ < bc[np.clip(owner, 0, len(bc) - 1)])
    out = [[] for _ in range(len(bo))]
    mo, mh, ml, mc = (m[k].to_numpy(np.float64).tolist() for k in ('open', 'high', 'low', 'close'))
    own = owner.tolist()
    mts = mt_.tolist()
    for j in np.nonzero(keep)[0].tolist():
        out[own[j]].append((mo[j], mh[j], ml[j], mc[j], mts[j]))
    co, chh, cl, cc = (ch[k].to_numpy(np.float64) for k in ('open', 'high', 'low', 'close'))
    for r, sb in enumerate(out):
        if not sb:
            raise ValueError('%s %s: chart bar %d has no 1-minute bars' % (pair, tf, r))
        if not (sb[0][0] == co[r] and sb[-1][3] == cc[r] and max(x[1] for x in sb) == chh[r]
                and min(x[2] for x in sb) == cl[r]):
            raise ValueError('%s %s: chart bar %d differs from its 1-minute bars' % (pair, tf, r))
    return out


def build_D(pair, tf, sig, perm, with_sub=True):
    """Everything the reference reads, as plain Python lists. sig / perm: frames on the same rows."""
    rows = np.asarray(sig.index, dtype=np.int64)
    ch = pd.read_parquet(os.path.join(W, 'data', '%s_%s.parquet' % (pair, tf)),
                         columns=['open', 'high', 'low', 'close', 't_open', 't_close']).reset_index(drop=True)
    ch = ch.iloc[rows]
    if not np.array_equal(ch['t_close'].to_numpy(np.int64), sig['t_close'].to_numpy(np.int64)):
        raise ValueError('sig rows do not match the data file')
    if perm is not None and not perm.index.equals(sig.index):
        raise ValueError('perm rows differ from sig rows')
    D = dict(pair=pair, tf=str(tf), rows=rows.tolist(),
             o=ch['open'].tolist(), h=ch['high'].tolist(), l=ch['low'].tolist(), c=ch['close'].tolist(),
             t_open=ch['t_open'].tolist(), t_close=ch['t_close'].tolist(),
             longSrc=_lists(sig['longSrc']), shortSrc=_lists(sig['shortSrc']),
             exitL=[bool(x) for x in sig['exitL']], exitS=[bool(x) for x in sig['exitS']],
             exitLSrc=sig['exitLSrc'].tolist(), exitSSrc=sig['exitSSrc'].tolist(),
             buyOk=None if perm is None else [bool(x) for x in perm['buyOk']],
             sellOk=None if perm is None else [bool(x) for x in perm['sellOk']])
    D['sub'] = minute_table(pair, tf, rows) if with_sub else None
    return D


def window(sig, perm, start, end):
    tc = sig['t_close'].to_numpy(np.int64)
    m = (tc >= start) & (tc <= end)
    return sig[m], (None if perm is None else perm[m])


# =============================================================================== the Pine, per bar
def to_ticks(d, ref, unit):
    # toTicks(float d, float ref) => trailUnit == "ticks" ? d : trailUnit == "price" ? d / syminfo.mintick
    #                                                         : ref * d / 100.0 / syminfo.mintick
    if unit == 'ticks':
        return d
    if unit == 'price':
        return d / MT
    return ref * d / 100.0 / MT


class Trade:
    __slots__ = ('id', 'dir', 'isLong', 'k', 'row', 'epx', 'src', 'ecmt', 'has_tr', 'A', 'off', 'has_sl', 'sl',
                 'armed', 'best', 'trPts', 'trOff', 'slPts', 'xrow', 'xpx', 'xkind', 'xcmt', 'xsub', 'arm_at')

    def __init__(self):
        self.has_tr = self.has_sl = self.armed = False
        self.A = self.off = self.sl = self.best = None
        self.trPts = self.trOff = self.slPts = None
        self.xrow = -1
        self.xpx = math.nan
        self.xkind = ''
        self.xcmt = ''
        self.xsub = -1
        self.arm_at = None


# ---- strategy.exit("X id", from_entry=id, trail_points, trail_offset, loss) on the REAL side
def _stop_long(t):
    ts = (t.best - t.off) if (t.has_tr and t.armed) else None
    sl = t.sl if t.has_sl else None
    if ts is None and sl is None:
        return None, ''
    if sl is None or (ts is not None and ts >= sl):
        return ts, 'trail'                      # the higher stop is the one price meets first
    return sl, 'sl'


def _stop_short(t):
    ts = (t.best + t.off) if (t.has_tr and t.armed) else None
    sl = t.sl if t.has_sl else None
    if ts is None and sl is None:
        return None, ''
    if sl is None or (ts is not None and ts <= sl):
        return ts, 'trail'                      # the lower stop is the one price meets first
    return sl, 'sl'


def _fav_long(t, p):
    if not t.has_tr:
        return
    if t.armed:
        if p > t.best:
            t.best = p
    elif p >= t.A - TOL:
        t.armed = True
        t.best = p


def _fav_short(t, p):
    if not t.has_tr:
        return
    if t.armed:
        if p < t.best:
            t.best = p
    elif p <= t.A + TOL:
        t.armed = True
        t.best = p


def exit_on_bar(t, bo, bh, bl, bc):
    """One price bar (a chart bar on 'tv', a 1-minute bar on 'mag') of trade t's exit order.
    SPEC rule 2: open -> high -> low -> close if (high - open) < (open - low), else open -> low ->
    high -> close. Returns (kind, fill price) or None."""
    seq = (bh, bl, bc) if (bh - bo) < (bo - bl) else (bl, bh, bc)
    if t.dir > 0:                                               # a real LONG: stops below
        stop, kind = _stop_long(t)
        if stop is not None and bo <= stop + TOL:
            return kind, bo                                     # opened at / through the stop
        _fav_long(t, bo)
        a = bo
        for b in seq:
            if b > a:
                _fav_long(t, b)
            elif b < a:
                stop, kind = _stop_long(t)
                if stop is not None and b <= stop + TOL:
                    return kind, (stop if stop < a else a)
            a = b
        return None
    stop, kind = _stop_short(t)                                 # a real SHORT: stops above
    if stop is not None and bo >= stop - TOL:
        return kind, bo
    _fav_short(t, bo)
    a = bo
    for b in seq:
        if b < a:
            _fav_short(t, b)
        elif b > a:
            stop, kind = _stop_short(t)
            if stop is not None and b >= stop - TOL:
                return kind, (stop if stop > a else a)
        a = b
    return None


def run_ref(D, prm, path='tv', declog=None):
    """The strategy on D with the Pine inputs prm (PINE keys). Returns (trades in entry order, info).
    declog: optional dict, filled with the script's decision values on every bar that has a label
    or an exit row (for the traces)."""
    o, h, l, c = D['o'], D['h'], D['l'], D['c']
    rows = D['rows']
    longSrcA, shortSrcA = D['longSrc'], D['shortSrc']
    exitLA, exitSA, exitLSrcA, exitSSrcA = D['exitL'], D['exitS'], D['exitLSrc'], D['exitSSrc']
    n = len(c)
    xpwInv = bool(prm['xpwInv'])
    tradeDir = prm['tradeDir']
    if tradeDir not in ('Both', LONG_ONLY, SHORT_ONLY):
        raise ValueError(tradeDir)
    oppCloses = bool(prm['oppCloses'])
    fgfOn = bool(prm['fgfOn'])
    fgfBlkClose = bool(prm['fgfBlkClose'])
    maxOpen = int(prm['maxOpen'])
    trailOn, slOn, unit = bool(prm['trailOn']), bool(prm['slOn']), prm['trailUnit']
    trailAct, trailOff, slDist = prm['trailAct'], prm['trailOff'], prm['slDist']
    if fgfOn and D['buyOk'] is None:
        raise ValueError('filter on needs the permission arrays')
    buyOkA, sellOkA = D['buyOk'], D['sellOk']
    sub = D['sub'] if path == 'mag' else None
    if path not in ('tv', 'mag'):
        raise ValueError(path)

    trades = []
    open_ = []                      # the open trades (TradingView: all on one side)
    info = dict(raw_long=0, raw_short=0, blocked_long=0, blocked_short=0, go_long_bars=0, go_short_bars=0,
                skipped_room=0, ignored_pyr=0, close_all_bars=0, max_open=0)

    for i in range(n):
        # ---- 1. the broker works the exit orders of the open trades inside bar i
        if open_:
            if sub is None:
                still = []
                for t in open_:
                    if not (t.has_tr or t.has_sl):
                        still.append(t)
                        continue
                    was = t.armed
                    r = exit_on_bar(t, o[i], h[i], l[i], c[i])
                    if t.armed and not was:
                        t.arm_at = (i, 0)
                    if r is None:
                        still.append(t)
                    else:
                        t.xkind, t.xpx, t.xrow, t.xsub = r[0], r[1], i, 0
                        t.xcmt = ('trail TP | ' if r[0] == 'trail' else 'SL | ') + t.src
                open_ = still
            elif any(t.has_tr or t.has_sl for t in open_):
                for m_, (so, sh, sl_, sc_, _ts) in enumerate(sub[i]):
                    still = []
                    for t in open_:
                        if not (t.has_tr or t.has_sl):
                            still.append(t)
                            continue
                        was = t.armed
                        r = exit_on_bar(t, so, sh, sl_, sc_)
                        if t.armed and not was:
                            t.arm_at = (i, m_)
                        if r is None:
                            still.append(t)
                        else:
                            t.xkind, t.xpx, t.xrow, t.xsub = r[0], r[1], i, m_
                            t.xcmt = ('trail TP | ' if r[0] == 'trail' else 'SL | ') + t.src
                    open_ = still
                    if not open_:
                        break

        # ---- 2. the script runs at the close of bar i (Pine lines 1480-1628)
        longSrc, shortSrc = longSrcA[i], shortSrcA[i]
        exitL, exitS = exitLA[i], exitSA[i]
        opentrades = len(open_)                                           # strategy.opentrades
        if opentrades > info['max_open']:
            info['max_open'] = opentrades
        if not longSrc and not shortSrc and not exitL and not exitS:
            continue                                                      # no label: the script places nothing
        position_size = 0 if not open_ else open_[0].dir * len(open_)     # strategy.position_size (sign)
        bar_index = rows[i]
        close = c[i]

        nLong = len(longSrc)
        nShort = len(shortSrc)
        if nLong > 0 and nShort > 0:
            nLong = 0
            nShort = 0
        if xpwInv:
            allowLong = tradeDir != LONG_ONLY
            allowShort = tradeDir != SHORT_ONLY
        else:
            allowLong = tradeDir != SHORT_ONLY
            allowShort = tradeDir != LONG_ONLY
        sigLong = nLong > 0 and allowLong          # doneL != bar_index: always true on history
        sigShort = nShort > 0 and allowShort
        fgfBuyOk = (not fgfOn) or buyOkA[i]
        fgfSellOk = (not fgfOn) or sellOkA[i]
        fgfLimOkL = True                           # not useLimit
        fgfLimOkS = True
        fgfBlkL = sigLong and not (fgfBuyOk and fgfLimOkL)
        fgfBlkS = sigShort and not (fgfSellOk and fgfLimOkS)
        goLong = sigLong and not fgfBlkL
        goShort = sigShort and not fgfBlkS
        oppL = nShort > 0 and ((oppCloses and not allowShort) or (fgfBlkClose and fgfBlkS))
        oppS = nLong > 0 and ((oppCloses and not allowLong) or (fgfBlkClose and fgfBlkL))
        xpwPosN = -position_size if xpwInv else position_size
        closeL = xpwPosN > 0 and not goLong and (not goShort and (exitL or oppL))
        closeS = xpwPosN < 0 and not goShort and (not goLong and (exitS or oppS))
        firstLong = longSrc[0] if len(longSrc) > 0 else ''
        firstShort = shortSrc[0] if len(shortSrc) > 0 else ''
        info['raw_long'] += sigLong
        info['raw_short'] += sigShort
        info['blocked_long'] += fgfBlkL
        info['blocked_short'] += fgfBlkS
        info['go_long_bars'] += goLong
        info['go_short_bars'] += goShort

        orders = []
        if closeL:
            cm = ('exit | ' + exitLSrcA[i]) if exitL else (
                (('filter blocked LONG (inv), close | ' if xpwInv else 'filter blocked SHORT, close | ') + firstShort)
                if fgfBlkS else ('opp ENTER | ' + firstShort))
            orders.append(('close_all', cm))
        if closeS:
            cm = ('exit | ' + exitSSrcA[i]) if exitS else (
                (('filter blocked SHORT (inv), close | ' if xpwInv else 'filter blocked LONG, close | ') + firstLong)
                if fgfBlkL else ('opp ENTER | ' + firstLong))
            orders.append(('close_all', cm))
        room = maxOpen - opentrades - 0            # - array.size(pendId): no pending orders in Signal tick mode
        room0 = room
        if goLong:
            for k in range(nLong):
                if room > 0 or xpwPosN < 0:
                    id_ = ('S' if xpwInv else 'L') + str(bar_index) + '-' + str(k + 1)
                    orders.append(('entry', id_, True, k, longSrc[k]))
                    room -= 1
                else:
                    info['skipped_room'] += 1
        if goShort:
            for k in range(nShort):
                if room > 0 or xpwPosN > 0:
                    id_ = ('L' if xpwInv else 'S') + str(bar_index) + '-' + str(k + 1)
                    orders.append(('entry', id_, False, k, shortSrc[k]))
                    room -= 1
                else:
                    info['skipped_room'] += 1
        if declog is not None:
            declog[i] = dict(position_size=position_size, opentrades=opentrades, nLong=nLong, nShort=nShort,
                             longSrc=longSrc, shortSrc=shortSrc, exitL=exitL, exitS=exitS,
                             allowLong=allowLong, allowShort=allowShort, sigLong=sigLong, sigShort=sigShort,
                             fgfBuyOk=fgfBuyOk, fgfSellOk=fgfSellOk, fgfBlkL=fgfBlkL, fgfBlkS=fgfBlkS,
                             goLong=goLong, goShort=goShort, oppL=oppL, oppS=oppS, xpwPosN=xpwPosN,
                             closeL=closeL, closeS=closeS, room=room0,
                             orders=[x[:2] if x[0] == 'close_all' else (x[0], x[1], 'isLong' if x[2] else 'isShort')
                                     for x in orders])

        # ---- 3. the broker fills the market orders at this close, in the order they were placed
        for od in orders:
            if od[0] == 'close_all':
                if open_:
                    info['close_all_bars'] += 1
                    for t in open_:
                        t.xkind, t.xpx, t.xrow, t.xcmt = 'close_all', close, i, od[1]
                    open_ = []
                continue
            _, id_, isLong, k, src = od
            # placeEntry(id, isLong, na, src)
            ref = close
            trPts = max(to_ticks(trailAct, ref, unit), 0.0) if trailOn else None
            trOff = max(to_ticks(trailOff, ref, unit), 1.0) if trailOn else None
            slPts = max(to_ticks(slDist, ref, unit), 1.0) if slOn else None
            realLong = (not isLong) if xpwInv else isLong
            cmt = ('ENTER LONG' if realLong else 'ENTER SHORT') + (' (inv)' if xpwInv else '') + ' | ' + src
            d = 1 if realLong else -1
            # strategy.entry(id, realLong ? strategy.long : strategy.short, comment=cmt)
            if open_ and open_[0].dir == -d:                    # opposite to the open position: reverse
                for t in open_:
                    t.xkind, t.xpx, t.xrow, t.xcmt = 'reverse', close, i, cmt
                open_ = []
            if len(open_) >= PYRAMIDING:
                info['ignored_pyr'] += 1
                continue
            t = Trade()
            t.id, t.dir, t.isLong, t.k, t.row, t.epx, t.src, t.ecmt = id_, d, isLong, k + 1, i, close, src, cmt
            # strategy.exit("X " + id, from_entry=id, trail_points=trPts, trail_offset=trOff, loss=slPts)
            if trailOn or slOn:
                t.trPts, t.trOff, t.slPts = trPts, trOff, slPts
                if trPts is not None:
                    t.has_tr = True
                    t.off = trOff * MT
                    t.best = close
                    if realLong:
                        t.A = close + trPts * MT
                        t.armed = close >= t.A - TOL
                    else:
                        t.A = close - trPts * MT
                        t.armed = close <= t.A + TOL
                if slPts is not None:
                    t.has_sl = True
                    t.sl = (close - slPts * MT) if realLong else (close + slPts * MT)
            trades.append(t)
            open_.append(t)

    # ---- window end: what is still open is closed at the last close
    for t in open_:
        t.xkind, t.xpx, t.xrow, t.xcmt = 'end', c[n - 1], n - 1, 'end'
    return trades, info


# =============================================================================== money
def cost_unit(pair, mode, e, x):
    if mode == 'tv0':
        return 0.0
    if mode == 'cost':
        return 0.30 if pair == 'XAU' else 0.0002 * (e + x) + 0.20
    if mode == 'stress':
        return (0.50 + 0.02) if pair == 'XAU' else 0.00035 * (e + x) + 0.20 + 0.02
    raise ValueError(mode)


def _simulate(pair, T, mode, cap0=CAP0):
    """10% of the closed equity per entry, compounding; exits before entries at one bar close.
    Returns (qty, realized) per trade (index = position in T)."""
    nT = len(T)
    ev = []
    for j, t in enumerate(T):
        ev.append((t.xrow, 0, t.row, j))        # exit; several at one close: by entry bar, then entry order
        ev.append((t.row, 1, j, j))             # entry
    ev.sort()
    eq = cap0
    qty = [0.0] * nT
    real = [0.0] * nT
    expo = -math.inf
    open_not = {}
    conc = maxc = 0
    for (_r, kind, _a, j) in ev:
        t = T[j]
        if kind == 1:
            qty[j] = FRAC * max(eq, 0.0) / t.epx
            open_not[j] = qty[j] * t.epx
            e = (math.fsum(open_not.values()) / eq) if eq > 0 else math.inf
            if e > expo:
                expo = e
            conc += 1
            if conc > maxc:
                maxc = conc
        else:
            pnl_u = t.dir * (t.xpx - t.epx) - cost_unit(pair, mode, t.epx, t.xpx)
            real[j] = qty[j] * pnl_u
            eq += real[j]
            open_not.pop(j, None)
            conc -= 1
    return qty, real, expo, maxc


def money(pair, T, mode, t_close, start, end):
    """The metrics of run_tf.metrics / sweep_core.metrics_fast, computed independently (unrounded)."""
    nT = len(T)
    if nT == 0:
        return dict(trades=0)
    qty, real, expo, maxc = _simulate(pair, T, mode)
    mid = start + (end - start) // 2
    order = sorted(range(nT), key=lambda j: (T[j].xrow, T[j].row, j))     # by exit, then entry
    eq = peak = CAP0
    dd = -math.inf
    for j in order:
        eq += real[j]
        if eq > peak:
            peak = eq
        dd = max(dd, (peak - eq) / peak)
    wins = math.fsum(r for r in real if r > 0)
    losses = -math.fsum(r for r in real if r < 0)
    h1 = math.fsum(real[j] for j in range(nT) if t_close[T[j].xrow] <= mid)
    h2 = math.fsum(real[j] for j in range(nT) if t_close[T[j].xrow] > mid)
    ret = [(T[j].dir * (T[j].xpx - T[j].epx) - cost_unit(pair, mode, T[j].epx, T[j].xpx)) / T[j].epx for j in range(nT)]
    out = dict(trades=nT, net_pct=100 * math.fsum(real) / CAP0, pf=(wins / losses) if losses > 0 else math.nan,
               win_pct=100 * sum(1 for r in real if r > 0) / nT, max_dd_pct=100 * dd,
               half1_pct=100 * h1 / CAP0, half2_pct=100 * h2 / CAP0, avg_trade_ret_pct=100 * math.fsum(ret) / nT,
               max_concurrent=maxc, max_expo=expo,
               avg_bars_held=sum(t.xrow - t.row for t in T) / nT)
    for kn in ('trail', 'sl', 'close_all', 'reverse', 'end'):
        out['exit_' + kn] = sum(1 for t in T if t.xkind == kn)
    for nm, part in (('h1', [t for t in T if t_close[t.row] <= mid]), ('h2', [t for t in T if t_close[t.row] > mid])):
        out[nm + '_trades'] = len(part)
        if part:
            _q, rl, _e, _m = _simulate(pair, part, mode)
            w = math.fsum(r for r in rl if r > 0)
            ls = -math.fsum(r for r in rl if r < 0)
            out[nm + 'r_pct'] = 100 * math.fsum(rl) / CAP0
            out[nm + 'r_pf'] = (w / ls) if ls > 0 else math.nan
        else:
            out[nm + 'r_pct'] = math.nan
            out[nm + 'r_pf'] = math.nan
    out['long_trades'] = sum(1 for t in T if t.dir > 0)
    out['short_trades'] = sum(1 for t in T if t.dir < 0)
    return out


# =============================================================================== comparisons
KCODE = {'trail': 1, 'sl': 2, 'close_all': 3, 'reverse': 4, 'end': 5}


def _close(a, b, rel=1e-9, ab=1e-9):
    if a is None or b is None:
        return a is None and b is None
    a = float(a)
    b = float(b)
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    if math.isinf(a) or math.isinf(b):
        return a == b
    return abs(a - b) <= ab + rel * max(abs(a), abs(b))


def cmp_runcfg(T, R):
    """Reference trades vs sweep_core.run_cfg arrays (exact): list of mismatch strings."""
    bad = []
    if R['n'] != len(T):
        bad.append('trade count: replica %d, reference %d' % (R['n'], len(T)))
    m = min(R['n'], len(T))
    mine = dict(dir=[t.dir for t in T], erow=[t.row for t in T], k=[t.k for t in T], epx=[t.epx for t in T],
                xrow=[t.xrow for t in T], xpx=[t.xpx for t in T], xkind=[KCODE[t.xkind] for t in T])
    for key, v in mine.items():
        a = np.asarray(R[key][:m]).astype(np.float64)
        b = np.asarray(v[:m], np.float64)
        ne = a != b
        if ne.any():
            j = int(np.argmax(ne))
            bad.append('%s: %d trades differ, first #%d replica %r reference %r' % (key, int(ne.sum()), j, a[j], b[j]))
    return bad


def cmp_metrics_raw(pair, T, raw, t_close, start, end):
    """Reference money model vs sweep_core.metrics_raw (3 cost modes), relative 1e-9."""
    import sweep_core as sc
    bad = []
    slots = dict(trades=sc.M_TRADES, net_pct=sc.M_NET, pf=sc.M_PF, win_pct=sc.M_WIN, max_dd_pct=sc.M_DD,
                 half1_pct=sc.M_H1, half2_pct=sc.M_H2, avg_trade_ret_pct=sc.M_AVG, max_concurrent=sc.M_MAXC,
                 exit_trail=sc.M_TRAIL, exit_sl=sc.M_SL, exit_close_all=sc.M_CLOSEALL, exit_reverse=sc.M_REVERSE,
                 exit_end=sc.M_END, max_expo=sc.M_EXPO, avg_bars_held=sc.M_BARS, h1r_pct=sc.M_H1R, h2r_pct=sc.M_H2R,
                 h1_trades=sc.M_H1N, h2_trades=sc.M_H2N, h1r_pf=sc.M_H1PF, h2r_pf=sc.M_H2PF)
    for mi, mode in enumerate(sc.MODES):
        mine = money(pair, T, mode, t_close, start, end)
        if mine['trades'] == 0:
            if raw[mi, sc.M_TRADES] != 0:
                bad.append('%s trades: replica %r reference 0' % (mode, raw[mi, sc.M_TRADES]))
            continue
        for key, s in slots.items():
            if not _close(raw[mi, s], mine[key]):
                bad.append('%s %s: replica %r reference %r' % (mode, key, raw[mi, s], mine[key]))
    return bad


TABLE_EXACT = ('id', 'dir', 'src', 'entry_row', 'entry_time', 'entry_bar_time', 'entry_px', 'exit_row', 'exit_time',
               'exit_bar_time', 'exit_px', 'exit_kind', 'exit_comment', 'entry_comment', 'trail_act_px', 'trail_off',
               'sl_px', 'pl', 'bars_held')


def ref_table(D, T):
    rows, tc, to = D['rows'], D['t_close'], D['t_open']
    nan = math.nan
    return pd.DataFrame({
        'id': [t.id for t in T], 'dir': [t.dir for t in T], 'src': [t.src for t in T],
        'entry_row': [rows[t.row] for t in T], 'entry_time': [tc[t.row] for t in T],
        'entry_bar_time': [to[t.row] for t in T], 'entry_px': [t.epx for t in T],
        'exit_row': [rows[t.xrow] for t in T], 'exit_time': [tc[t.xrow] for t in T],
        'exit_bar_time': [to[t.xrow] for t in T], 'exit_px': [t.xpx for t in T],
        'exit_kind': [t.xkind for t in T], 'exit_comment': [t.xcmt for t in T],
        'entry_comment': [t.ecmt for t in T],
        'trail_act_px': [t.A if t.has_tr else nan for t in T],
        'trail_off': [t.off if t.has_tr else nan for t in T],
        'sl_px': [t.sl if t.has_sl else nan for t in T],
        'pl': [t.dir * (t.xpx - t.epx) for t in T],
        'bars_held': [t.xrow - t.row for t in T]})


def cmp_table(D, T, tr):
    """Reference vs engine.backtest's trade table, column by column (exact; floats bit for bit)."""
    bad = []
    if len(tr) != len(T):
        bad.append('trade count: replica %d, reference %d' % (len(tr), len(T)))
        return bad
    if not T:
        return bad
    mine = ref_table(D, T)
    for col in TABLE_EXACT:
        if col not in tr.columns:
            bad.append('column %s missing in the replica table' % col)
            continue
        a = tr[col].to_numpy()
        b = mine[col].to_numpy()
        if a.dtype.kind in 'fiu' and b.dtype.kind in 'fiu':
            a = a.astype(np.float64)
            b = b.astype(np.float64)
            ne = ~((a == b) | (np.isnan(a) & np.isnan(b)))
        else:
            ne = np.array([x != y for x, y in zip(a.tolist(), b.tolist())])
        if ne.any():
            j = int(np.argmax(ne))
            bad.append('%s: %d trades differ, first #%d replica %r reference %r' % (col, int(ne.sum()), j, a[j], b[j]))
    if 'sig_dir' in tr.columns:             # the replica adds it with the option on: the label's side
        lab = np.array([1 if t.isLong else -1 for t in T])
        if not np.array_equal(tr['sig_dir'].to_numpy(np.int64), lab):
            bad.append('sig_dir differs from the side of the label that placed the entry')
        if not np.array_equal(tr['sig_dir'].to_numpy(np.int64), -tr['dir'].to_numpy(np.int64)):
            bad.append('sig_dir is not the opposite of the real side')
    return bad


def cmp_summary(T, info, summ):
    """Funnel / count fields of engine.backtest's summary vs the reference."""
    ld = [t for t in T if t.dir > 0]
    sd = [t for t in T if t.dir < 0]
    pl = lambda ts: math.fsum(t.dir * (t.xpx - t.epx) for t in ts)
    mine = dict(raw_long=info['raw_long'], raw_short=info['raw_short'], blocked_long=info['blocked_long'],
                blocked_short=info['blocked_short'], go_long_bars=info['go_long_bars'],
                go_short_bars=info['go_short_bars'], entries=len(T), long_entries=len(ld), short_entries=len(sd),
                entries_skipped_room=info['skipped_room'], entries_ignored_pyramiding=info['ignored_pyr'],
                close_all_bars=info['close_all_bars'],
                exits_trail=sum(t.xkind == 'trail' for t in T), exits_sl=sum(t.xkind == 'sl' for t in T),
                exits_close_all=sum(t.xkind == 'close_all' for t in T),
                exits_reverse=sum(t.xkind == 'reverse' for t in T), exits_end=sum(t.xkind == 'end' for t in T),
                gross_pl=pl(T), gross_pl_long=pl(ld), gross_pl_short=pl(sd),
                wins=sum(t.dir * (t.xpx - t.epx) > 0 for t in T), losses=sum(t.dir * (t.xpx - t.epx) < 0 for t in T),
                max_open=info['max_open'])
    bad = []
    for k, v in mine.items():
        if k not in summ:
            bad.append('summary key %s missing' % k)
        elif not _close(summ[k], v, rel=1e-9, ab=1e-6):
            bad.append('summary %s: replica %r reference %r' % (k, summ[k], v))
    return bad


def cmp_runtf(pair, T, tr, t_close, start, end):
    """run_tf.metrics on the replica's table (tv0 / cost) vs the reference money model (rounded values:
    equal within half a unit of the last printed digit plus float noise)."""
    import run_tf
    bad = []
    for mode, wc in (('tv0', False), ('cost', True)):
        rep = run_tf.metrics(pair, tr, start, end, wc)
        mine = money(pair, T, mode, t_close, start, end)
        if rep.get('trades', 0) != mine['trades']:
            bad.append('run_tf %s trades %r vs %r' % (mode, rep.get('trades'), mine['trades']))
            continue
        if mine['trades'] == 0:
            continue
        for k, dg in (('net_pct', 2), ('pf', 2), ('win_pct', 1), ('max_dd_pct', 2), ('half1_pct', 2), ('half2_pct', 2),
                      ('avg_trade_ret_pct', 4)):
            a = rep[k]
            b = mine[k]
            if a is None:
                if not math.isnan(b):
                    bad.append('run_tf %s %s: replica None reference %r' % (mode, k, b))
            elif abs(a - b) > 0.5 * 10 ** (-dg) + 1e-9:
                bad.append('run_tf %s %s: replica %r reference %r' % (mode, k, a, b))
        if rep['max_concurrent'] != mine['max_concurrent']:
            bad.append('run_tf %s max_concurrent %r vs %r' % (mode, rep['max_concurrent'], mine['max_concurrent']))
        kinds = {kn: mine['exit_' + kn] for kn in KCODE if mine['exit_' + kn]}
        if dict(rep['exit_kinds']) != kinds:
            bad.append('run_tf %s exit_kinds %r vs %r' % (mode, rep['exit_kinds'], kinds))
    return bad


# =============================================================================== settings
def corner_cfgs():
    return [
        dict(trailOn=True, trailUnit='price', trailAct=2.0, trailOff=1.0, slOn=False, slDist=3.0),       # the defaults
        dict(trailOn=True, trailUnit='percent', trailAct=0.0, trailOff=0.01, slOn=False, slDist=1.0),    # armed at the fill
        dict(trailOn=True, trailUnit='percent', trailAct=0.3, trailOff=0.1, slOn=True, slDist=0.25),
        dict(trailOn=False, trailUnit='percent', trailAct=0.0, trailOff=0.1, slOn=True, slDist=0.2),     # stop only
        dict(trailOn=False, trailUnit='percent', trailAct=0.0, trailOff=0.1, slOn=False, slDist=0.1),    # no exit orders
        dict(trailOn=True, trailUnit='ticks', trailAct=0.0, trailOff=0.3, slOn=True, slDist=0.2),        # 1-tick clamps
        dict(trailOn=True, trailUnit='percent', trailAct=0.0, trailOff=0.5, slOn=True, slDist=0.5),      # trail = stop (tie)
        dict(trailOn=True, trailUnit='percent', trailAct=1.0, trailOff=0.5, slOn=True, slDist=2.0),      # long holds
        dict(trailOn=True, trailUnit='percent', trailAct=2.0, trailOff=1.0, slOn=False, slDist=1.0),
    ]


def random_cfg(rng, ref_px):
    unit = str(rng.choice(['percent', 'percent', 'price', 'price', 'ticks']))

    def pct(allow0):
        u = rng.random()
        if allow0 and u < 0.2:
            return 0.0
        if u < 0.55:
            return float(rng.choice([0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]))
        return float(10.0 ** rng.uniform(-2.7, 0.6))

    def conv(p):
        if unit == 'percent':
            return p
        v = p / 100.0 * ref_px
        if unit == 'price':
            return round(v, 2) if rng.random() < 0.5 else v
        v = v / MT
        return float(round(v)) if rng.random() < 0.5 else v

    cfg = dict(trailUnit=unit, trailOn=bool(rng.random() < 0.75), slOn=bool(rng.random() < 0.5))
    cfg['trailAct'] = conv(pct(True))
    cfg['trailOff'] = conv(pct(False))
    cfg['slDist'] = conv(pct(False))
    return cfg


def cfg_str(cfg):
    return 'trail %s %s act %.6g off %.6g | sl %s %.6g' % ('on' if cfg['trailOn'] else 'off', cfg['trailUnit'],
                                                           cfg['trailAct'], cfg['trailOff'],
                                                           'on' if cfg['slOn'] else 'off', cfg['slDist'])


# =============================================================================== compare
def load_case(pair, tf, start, end, labels='normal'):
    import sweep_core as sc
    sig, perm = sc.load_inputs(pair, tf, verbose=False, labels=labels)
    return window(sig, perm, start, end)


def compare(pair, tf, start, end, n_rand=12, seed=20261124):
    import engine
    import sweep_core as sc
    t0 = time.time()
    sig, perm = load_case(pair, tf, start, end)
    D = build_D(pair, tf, sig, perm)
    rows = np.asarray(sig.index, dtype=np.int64)
    sub_sc = sc.sub_bars(pair, tf, rows)
    nsub = sum(len(x) for x in D['sub'])
    print('%s %s %d..%d: %d chart bars, %d 1-minute bars (replica table %d), label bars long %d short %d (%.1fs)'
          % (pair, tf, start, end, len(sig), nsub, int(sub_sc[0][-1]),
             sum(1 for x in D['longSrc'] if x), sum(1 for x in D['shortSrc'] if x), time.time() - t0), flush=True)
    rng = np.random.default_rng(seed + sum(ord(ch) for ch in pair + tf))
    ref_px = float(np.median(D['c']))
    cfgs = corner_cfgs() + [random_cfg(rng, ref_px) for _ in range(n_rand)]
    sc.check_mag_sync()
    nbad = 0
    tot = dict(runs=0, trades=0, inv_trades=0)
    kinds_inv = dict.fromkeys(KCODE, 0)
    differs_from_off = 0
    for filt in (False, True):
        Pn = sc.prep(pair, tf, sig, perm if filt else None, filt)
        for inv in (False, True):
            P = sc.prep(pair, tf, sig, perm if filt else None, filt, inv=inv)
            for ci, cfg in enumerate(cfgs):
                prm = dict(PINE, **cfg)
                prm['fgfOn'] = filt
                prm['xpwInv'] = inv
                res = {}
                for path in ('tv', 'mag'):
                    t1 = time.time()
                    T, info = run_ref(D, prm, path)
                    t2 = time.time()
                    R = sc.run_cfg(P, cfg, path, sub=sub_sc)
                    bad = cmp_runcfg(T, R)
                    raw = sc.metrics_raw(pair, R, P['t_close'], start, end)
                    bad += cmp_metrics_raw(pair, T, raw, D['t_close'], start, end)
                    if inv:                                     # the flag passed to run_cfg instead of prep
                        R2 = sc.run_cfg(Pn, cfg, path, sub=sub_sc, inv=True)
                        b2 = cmp_runcfg(T, R2)
                        bad += ['run_cfg(inv=True) on prep(inv=False): ' + x for x in b2]
                    res[path] = (T, info)
                    tot['runs'] += 1
                    tot['trades'] += len(T)
                    if inv:
                        tot['inv_trades'] += len(T)
                        for t in T:
                            kinds_inv[t.xkind] += 1
                    if bad:
                        nbad += 1
                        print('MISMATCH %s %s filter=%s inv=%s path=%s cfg[%d] %s:\n    %s'
                              % (pair, tf, filt, inv, path, ci, cfg_str(cfg), '\n    '.join(bad[:8])), flush=True)
                    if os.environ.get('VIX_VERBOSE'):
                        print('  filter=%s inv=%s %s cfg[%d] trades %d ref %.1fs' % (filt, inv, path, ci, len(T), t2 - t1),
                              flush=True)
                # engine.backtest: the full trade table on the tv path
                T, info = res['tv']
                ep = dict(prm)
                tr, summ = engine.backtest(pair, tf, sig, perm if filt else None, ep)
                bad = cmp_table(D, T, tr) + cmp_summary(T, info, summ) + cmp_runtf(pair, T, tr, D['t_close'], start, end)
                tot['runs'] += 1
                if bad:
                    nbad += 1
                    print('MISMATCH %s %s filter=%s inv=%s engine.backtest cfg[%d] %s:\n    %s'
                          % (pair, tf, filt, inv, ci, cfg_str(cfg), '\n    '.join(bad[:8])), flush=True)
            print('  filter %s, option %s: %d settings x (tv, mag, engine.backtest) done (%.0fs)'
                  % ('on' if filt else 'off', 'ON' if inv else 'off', len(cfgs), time.time() - t0), flush=True)
    print('%s %s: %d comparisons, %d with a mismatch; %d trades compared (%d with the option on: %s) (%.0fs)'
          % (pair, tf, tot['runs'], nbad, tot['trades'], tot['inv_trades'],
             ', '.join('%s %d' % kv for kv in kinds_inv.items()), time.time() - t0), flush=True)
    return nbad


# =============================================================================== other inputs (tv, engine.backtest)
def extra(pair, tf, start, end, seed=7):
    import engine
    import sweep_core as sc
    import xpw
    t0 = time.time()
    sig, perm = load_case(pair, tf, start, end)
    sig_rev, _ = load_case(pair, tf, start, end, labels='rev')
    # "exit only" rows (the defaults have none): three label rows closing instead of entering
    xo = {'actL2': 'exit only', 'actDS': 'exit only', 'actInf': 'exit only'}
    xo2 = {'actS1': 'exit only', 'actEnd': 'exit only', 'actDL': 'enter opposite', 'reverseAll': True}
    sig_x = sc._trim_sig(xpw.xpw_signals(pair, tf, start, end, dict(xo)))
    sig_x2 = sc._trim_sig(xpw.xpw_signals(pair, tf, start, end, dict(xo2)))
    for s in (sig_rev, sig_x, sig_x2):
        if not s.index.equals(sig.index):
            raise ValueError('signal frames on different rows')
    sigs = {'normal': sig, 'rev': sig_rev, 'exit-only A': sig_x, 'exit-only B (+ reverseAll)': sig_x2}
    Ds = {k: build_D(pair, tf, s, perm, with_sub=False) for k, s in sigs.items()}
    print('%s %s %d..%d: %d bars; exit rows: A exitL %d exitS %d, B exitL %d exitS %d'
          % (pair, tf, start, end, len(sig), int(sig_x['exitL'].sum()), int(sig_x['exitS'].sum()),
             int(sig_x2['exitL'].sum()), int(sig_x2['exitS'].sum())), flush=True)
    rng = np.random.default_rng(seed + sum(ord(ch) for ch in pair + tf))
    ref_px = float(np.median(Ds['normal']['c']))
    exits = [corner_cfgs()[0], corner_cfgs()[2], corner_cfgs()[4], corner_cfgs()[7]] + [random_cfg(rng, ref_px) for _ in range(4)]
    combos = []
    for td in ('Both', LONG_ONLY, SHORT_ONLY):
        for oc in (True, False):
            for bc in (True, False):
                for mo in (20, 1, 2, 3):
                    combos.append(dict(tradeDir=td, oppCloses=oc, fgfBlkClose=bc, maxOpen=mo))
    nbad = 0
    nrun = 0
    ntr = 0
    stats = dict(close_all=0, reverse=0, blk_close=0, opp_close=0, exit_close=0, skipped=0)
    for sname, s in sigs.items():
        D = Ds[sname]
        for filt in (False, True):
            for inv in (False, True):
                for cb in combos:
                    if not filt and not cb['fgfBlkClose']:
                        continue                    # "Has no effect with the filter off"
                    for ei, ex in enumerate(exits):
                        if (cb['maxOpen'] != 20 or not cb['oppCloses'] or not cb['fgfBlkClose']) and ei not in (0, 2, 7):
                            continue                # the full exit list only on the main input combos
                        prm = dict(PINE, **ex)
                        prm.update(cb)
                        prm['fgfOn'] = filt
                        prm['xpwInv'] = inv
                        T, info = run_ref(D, prm, 'tv')
                        tr, summ = engine.backtest(pair, tf, s, perm if filt else None, dict(prm))
                        bad = cmp_table(D, T, tr) + cmp_summary(T, info, summ)
                        nrun += 1
                        ntr += len(T)
                        if inv:
                            stats['skipped'] += info['skipped_room']
                            for t in T:
                                if t.xkind == 'reverse':
                                    stats['reverse'] += 1
                                elif t.xkind == 'close_all':
                                    stats['close_all'] += 1
                                    if t.xcmt.startswith('filter blocked'):
                                        stats['blk_close'] += 1
                                    elif t.xcmt.startswith('opp ENTER'):
                                        stats['opp_close'] += 1
                                    elif t.xcmt.startswith('exit |'):
                                        stats['exit_close'] += 1
                        if bad:
                            nbad += 1
                            print('MISMATCH %s %s sig=%s filter=%s inv=%s %r exits %s:\n    %s'
                                  % (pair, tf, sname, filt, inv, cb, cfg_str(ex), '\n    '.join(bad[:8])), flush=True)
        print('  signals %-28s done (%.0fs)' % (sname, time.time() - t0), flush=True)
    print('%s %s extra: %d engine.backtest runs, %d with a mismatch, %d trades; with the option on: reversals %d, '
          'close_all %d (filter-blocked %d, opp ENTER %d, exit rows %d), entries held back by Max open %d (%.0fs)'
          % (pair, tf, nrun, nbad, ntr, stats['reverse'], stats['close_all'], stats['blk_close'], stats['opp_close'],
             stats['exit_close'], stats['skipped'], time.time() - t0), flush=True)
    return nbad


# =============================================================================== the runner's JSON
def check_json(pair, tf):
    start, end = FULL[pair]
    path = os.path.join(W, 'out', 'inv_xpw_%s_%s.json' % (pair, tf))
    J = json.load(open(path))
    sig, perm = load_case(pair, tf, start, end)
    sig_rev, _ = load_case(pair, tf, start, end, labels='rev')
    D = build_D(pair, tf, sig, perm)
    Dr = dict(D)
    Dr.update(longSrc=_lists(sig_rev['longSrc']), shortSrc=_lists(sig_rev['shortSrc']),
              exitL=[bool(x) for x in sig_rev['exitL']], exitS=[bool(x) for x in sig_rev['exitS']],
              exitLSrc=sig_rev['exitLSrc'].tolist(), exitSSrc=sig_rev['exitSSrc'].tolist())
    nbad = 0
    ncmp = 0
    rounded = dict(net_pct=2, pf=2, win_pct=1, max_dd_pct=2, half1_pct=2, half2_pct=2, avg_trade_ret_pct=4,
                   h1r_pct=2, h2r_pct=2, h1r_pf=2, h2r_pf=2)
    exact = ('trades', 'max_concurrent', 'exit_trail', 'exit_sl', 'exit_close_all', 'exit_reverse', 'exit_end',
             'h1_trades', 'h2_trades', 'long_trades', 'short_trades')
    lines = []

    def one(label, node, DD, filt, inv):
        nonlocal nbad, ncmp
        for pth in ('tv', 'mag'):
            prm = dict(PINE)
            prm['fgfOn'] = filt
            prm['xpwInv'] = inv
            T, info = run_ref(DD, prm, pth)
            for cname, mode in (('script', 'tv0'), ('ours', 'cost')):
                rep = node[pth][cname]
                mine = money(pair, T, mode, DD['t_close'], start, end)
                bad = []
                for k in exact:
                    if k in rep and rep[k] != mine[k]:
                        bad.append('%s: json %r reference %r' % (k, rep[k], mine[k]))
                for k, dg in rounded.items():
                    if k not in rep:
                        continue
                    a, b = rep[k], mine[k]
                    if a is None or (isinstance(a, float) and math.isnan(a)):
                        if not math.isnan(b):
                            bad.append('%s: json %r reference %r' % (k, a, b))
                    elif abs(a - b) > 0.5 * 10 ** (-dg) + 1e-9:
                        bad.append('%s: json %r reference %r' % (k, a, b))
                for k in ('max_expo', 'avg_bars_held'):
                    if k in rep and not _close(rep[k], mine[k]):
                        bad.append('%s: json %r reference %r' % (k, rep[k], mine[k]))
                for k, v in (('entries_skipped_room', info['skipped_room']), ('close_all_bars', info['close_all_bars']),
                             ('max_open', info['max_open'])):
                    if k in rep and rep[k] != v:
                        bad.append('%s: json %r reference %r' % (k, rep[k], v))
                ncmp += 1
                lines.append('%-9s filter %-3s %-3s %-6s trades %5d (L %5d / S %5d)  net %9.2f%%  pf %6.2f  win %5.1f%%  dd %6.2f%%'
                             '  h1r %8.2f%%  h2r %8.2f%%  %s'
                             % (label, 'on' if filt else 'off', pth, cname, mine['trades'], mine['long_trades'],
                                mine['short_trades'], mine['net_pct'], mine['pf'], mine['win_pct'], mine['max_dd_pct'],
                                mine['h1r_pct'], mine['h2r_pct'], 'OK' if not bad else 'MISMATCH'))
                if bad:
                    nbad += 1
                    print('MISMATCH %s %s %s filter=%s %s %s:\n    %s' % (pair, tf, label, filt, pth, cname, '\n    '.join(bad)))

    for dname, inv in (('normal', False), ('inverted', True)):
        for fname, filt in (('off', False), ('on', True)):
            one(dname, J['runs'][dname][fname], D, filt, inv)
    if 'rev_labels' in J:
        for fname, filt in (('off', False), ('on', True)):
            one('rev label', J['rev_labels'][fname], Dr, filt, False)
    print('%s %s: out/inv_xpw_%s_%s.json, reference numbers (unrounded money model, rounded for print):' % (pair, tf, pair, tf))
    for ln in lines:
        print('  ' + ln)
    print('%s %s json: %d leaves compared, %d with a mismatch' % (pair, tf, ncmp, nbad), flush=True)
    return nbad


# =============================================================================== hand traces
def _ts(t):
    return pd.Timestamp(int(t), unit='s').strftime('%Y-%m-%d %H:%M')


def _decision_lines(D, i, dl, inv):
    d = dl[i]
    out = ['  script at the close of row %d (bar_index %d, bar %s .. %s, close %.3f):'
           % (i, D['rows'][i], _ts(D['t_open'][i]), _ts(D['t_close'][i]), D['c'][i]),
           '    labels: longSrc %r shortSrc %r exitL %s exitS %s  -> nLong %d nShort %d'
           % (d['longSrc'], d['shortSrc'], d['exitL'], d['exitS'], d['nLong'], d['nShort']),
           '    filter: fgfBuyOk %s fgfSellOk %s | sigLong %s sigShort %s | fgfBlkL %s fgfBlkS %s | goLong %s goShort %s'
           % (d['fgfBuyOk'], d['fgfSellOk'], d['sigLong'], d['sigShort'], d['fgfBlkL'], d['fgfBlkS'], d['goLong'], d['goShort']),
           '    strategy.position_size sign*count %d, opentrades %d -> xpwPosN %d (xpwInv %s); oppL %s oppS %s; closeL %s closeS %s; room %d'
           % (d['position_size'], d['opentrades'], d['xpwPosN'], inv, d['oppL'], d['oppS'], d['closeL'], d['closeS'], d['room']),
           '    orders placed: %r' % (d['orders'],)]
    return out


def _walk_print(t, bars, first_row, D, upto_row, sub_detail_rows=()):
    """Re-walk trade t's exit order over `bars` (list of (label, o, h, l, c)) printing the state."""
    w = Trade()
    for a in ('dir', 'has_tr', 'A', 'off', 'has_sl', 'sl', 'armed', 'best'):
        setattr(w, a, getattr(t, a))
    w.best = t.epx
    w.armed = False
    if t.has_tr:
        w.armed = (t.epx >= t.A - TOL) if t.dir > 0 else (t.epx <= t.A + TOL)
    for (lab, bo, bh, bl, bc, show) in bars:
        order = 'O-H-L-C' if (bh - bo) < (bo - bl) else 'O-L-H-C'
        r = exit_on_bar(w, bo, bh, bl, bc)
        st, kd = (_stop_long(w) if w.dir > 0 else _stop_short(w))
        if show or r is not None:
            print('    %-22s O %.3f H %.3f L %.3f C %.3f  %s  -> %s'
                  % (lab, bo, bh, bl, bc, order,
                     ('EXIT %s @ %.6f' % (r[0], r[1])) if r is not None else
                     ('armed %s best %s working stop %s' % (w.armed, ('%.3f' % w.best) if w.has_tr else '-',
                                                            ('%.6f (%s)' % (st, kd)) if st is not None else 'none'))))
        if r is not None:
            return r
    return None


def _show_trade(D, t, prm, path, dl, title, rep_row):
    inv = prm['xpwInv']
    print('=' * 118)
    print(title)
    print('  inputs: xpwInv %s, filter %s, path %s, exits: %s' % (inv, 'on' if prm['fgfOn'] else 'off', path, cfg_str(prm)))
    i = t.row
    # the bars before the entry that carried a label (context for "first entry")
    for ln in _decision_lines(D, i, dl, inv):
        print(ln)
    print('  -> entry id %s: the Pine entry is %s, placed as a REAL %s at the close %.3f; comment %r'
          % (t.id, 'LONG (isLong)' if t.isLong else 'SHORT (not isLong)', 'LONG' if t.dir > 0 else 'SHORT', t.epx, t.ecmt))
    if t.has_tr:
        print('     trail_points %.6f ticks -> activation %.6f (%s the entry); trail_offset %.6f ticks = %.6f'
              % (t.trPts, t.A, 'above' if t.dir > 0 else 'below', t.trOff, t.off))
    if t.has_sl:
        print('     loss %.6f ticks -> stop loss %.6f (%s the entry)' % (t.slPts, t.sl, 'below' if t.dir > 0 else 'above'))
    if not (t.has_tr or t.has_sl):
        print('     no strategy.exit order (trailOn and slOn both off)')
    print('  bars after the entry (exit orders work from the next chart bar):')
    bars = []
    last = t.xrow
    for r in range(i + 1, last + 1):
        if path == 'tv':
            bars.append(('row %d %s' % (r, _ts(D['t_open'][r])[5:]), D['o'][r], D['h'][r], D['l'][r], D['c'][r], True))
        else:
            sb = D['sub'][r]
            for m_, (so, sh, sl_, sc_, ts_) in enumerate(sb):
                near = (r == last and (t.xsub < 0 or m_ >= t.xsub - 3)) or (t.arm_at is not None and t.arm_at[0] == r and abs(m_ - t.arm_at[1]) <= 1)
                bars.append(('row %d min %s' % (r, _ts(ts_)[5:]), so, sh, sl_, sc_, near or (r - i <= 1 and m_ < 3)))
    if path == 'mag':
        print('    (1-minute bars; only the first three, those around the arming and the last ones before the exit are printed;')
        print('     chart bars: %s)' % '; '.join('row %d O %.3f H %.3f L %.3f C %.3f' % (r, D['o'][r], D['h'][r], D['l'][r], D['c'][r])
                                            for r in range(i + 1, min(last, i + 6) + 1)))
    r_ = None
    if t.has_tr or t.has_sl:
        r_ = _walk_print(t, bars, i + 1, D, last)
    else:
        for b in bars:
            print('    %-22s O %.3f H %.3f L %.3f C %.3f' % b[:5])
    if t.xkind in ('close_all', 'reverse', 'end'):
        if r_ is not None:
            print('    !! the walk exits earlier than the reference trade')
        if t.xkind != 'end':
            for ln in _decision_lines(D, t.xrow, dl, inv):
                print(ln)
        print('  -> closed by %s at the close of row %d: %.3f, comment %r' % (t.xkind, t.xrow, t.xpx, t.xcmt))
    else:
        print('  -> %s exit in row %d at %.6f, comment %r' % (t.xkind, t.xrow, t.xpx, t.xcmt))
    pl = t.dir * (t.xpx - t.epx)
    print('  reference: real %s  entry row %d @ %.3f  exit row %d @ %.6f  kind %s  P/L per unit %+.6f'
          % ('LONG' if t.dir > 0 else 'SHORT', D['rows'][t.row], t.epx, D['rows'][t.xrow], t.xpx, t.xkind, pl))
    print('  replica  : %s' % rep_row)


def trace():
    import engine
    import sweep_core as sc
    nbad = 0

    def setup(pair, tf, start, end):
        sig, perm = load_case(pair, tf, start, end)
        D = build_D(pair, tf, sig, perm)
        return sig, perm, D

    def rep_tv(pair, tf, sig, perm, prm, j, t):
        nonlocal nbad
        tr, _ = engine.backtest(pair, tf, sig, perm if prm['fgfOn'] else None, dict(prm))
        r = tr.iloc[j]
        ok = (r['id'] == t.id and r['dir'] == t.dir and r['entry_px'] == t.epx and r['exit_px'] == t.xpx
              and r['exit_kind'] == t.xkind and r['exit_comment'] == t.xcmt and r['entry_comment'] == t.ecmt)
        nbad += not ok
        return ('engine.backtest trade #%d: id %s dir %+d entry row %d @ %.3f exit row %d @ %.6f kind %s pl %+.6f\n'
                '             entry comment %r, exit comment %r  => %s'
                % (j, r['id'], r['dir'], r['entry_row'], r['entry_px'], r['exit_row'], r['exit_px'], r['exit_kind'],
                   r['pl'], r['entry_comment'], r['exit_comment'], 'SAME as the reference' if ok else 'DIFFERENT'))

    def rep_mag(pair, tf, sig, perm, prm, j, t, D):
        nonlocal nbad
        filt = prm['fgfOn']
        P = sc.prep(pair, tf, sig, perm if filt else None, filt, inv=prm['xpwInv'])
        cfg = {k: prm[k] for k in ('trailOn', 'trailUnit', 'trailAct', 'trailOff', 'slOn', 'slDist')}
        R = sc.run_cfg(P, cfg, 'mag', sub=sc.sub_bars(pair, tf, P['rows']))
        ok = (int(R['dir'][j]) == t.dir and float(R['epx'][j]) == t.epx and float(R['xpx'][j]) == t.xpx
              and int(R['xkind'][j]) == KCODE[t.xkind] and int(R['erow'][j]) == t.row and int(R['xrow'][j]) == t.xrow)
        nbad += not ok
        return ('run_cfg mag trade #%d: dir %+d entry row %d @ %.3f exit row %d @ %.6f kind %d (%s)  => %s'
                % (j, R['dir'][j], P['rows'][R['erow'][j]], R['epx'][j], P['rows'][R['xrow'][j]], R['xpx'][j], R['xkind'][j],
                   [k for k, v in KCODE.items() if v == R['xkind'][j]][0], 'SAME as the reference' if ok else 'DIFFERENT'))

    def pick(T, ok):
        for j, t in enumerate(T):
            if ok(j, t):
                return j, t
        return None, None

    # ---- 1. first entry (filter on, defaults, tv): the bars with labels before it are shown too
    pair, tf = 'BTC', '60'
    sig, perm, D = setup(pair, tf, *FULL[pair])
    prm = dict(PINE)
    prm['xpwInv'] = True
    dl = {}
    T, info = run_ref(D, prm, 'tv', declog=dl)
    t = T[0]
    print('#' * 118)
    print('TRACE 1: the FIRST entry of the inverted run (BTC 60, filter on, default exits, tv path)')
    print('  label bars before the first entry (blocked by the filter, or labels on both sides = cancelled; flat: nothing happens):')
    for i in sorted(dl):
        if i >= t.row:
            break
        d = dl[i]
        print('    row %d %s close %.3f: longSrc %r shortSrc %r -> nLong %d nShort %d | fgfBuyOk %s fgfSellOk %s | fgfBlkL %s fgfBlkS %s | goLong %s goShort %s | orders %r'
              % (i, _ts(D['t_close'][i]), D['c'][i], d['longSrc'], d['shortSrc'], d['nLong'], d['nShort'], d['fgfBuyOk'], d['fgfSellOk'], d['fgfBlkL'],
                 d['fgfBlkS'], d['goLong'], d['goShort'], d['orders']))
    _show_trade(D, t, prm, 'tv', dl, 'first entry', rep_tv(pair, tf, sig, perm, prm, 0, t))

    # ---- 2. a reversal (filter off, wider exits so that positions live until the opposite label)
    prm = dict(PINE, trailOn=True, trailUnit='percent', trailAct=1.0, trailOff=0.5, slOn=True, slDist=2.0)
    prm['xpwInv'] = True
    prm['fgfOn'] = False
    dl = {}
    T, info = run_ref(D, prm, 'tv', declog=dl)
    j, t = pick(T, lambda j, t: t.xkind == 'reverse' and 1 <= t.xrow - t.row <= 4 and dl[t.row]['position_size'] == 0
                and len([u for u in T if u.xrow == t.xrow and u.xkind == 'reverse']) == 1)
    print('#' * 118)
    print('TRACE 2: a REVERSAL of an inverted position (BTC 60, filter off, tv path)')
    _show_trade(D, t, prm, 'tv', dl, 'reversal', rep_tv(pair, tf, sig, perm, prm, j, t))
    nxt = [u for u in T if u.row == t.xrow]
    print('  the reversing entries on that bar: %s'
          % ', '.join('%s real %s @ %.3f (%r)' % (u.id, 'LONG' if u.dir > 0 else 'SHORT', u.epx, u.ecmt) for u in nxt))

    # ---- 3. blocked-signal close (filter on)
    prm = dict(PINE, trailOn=True, trailUnit='percent', trailAct=1.0, trailOff=0.5, slOn=True, slDist=2.0)
    prm['xpwInv'] = True
    dl = {}
    T, info = run_ref(D, prm, 'tv', declog=dl)
    j, t = pick(T, lambda j, t: t.xkind == 'close_all' and t.xcmt.startswith('filter blocked') and 1 <= t.xrow - t.row <= 4
                and dl[t.row]['position_size'] == 0)
    print('#' * 118)
    print('TRACE 3: a BLOCKED-SIGNAL CLOSE of an inverted position (BTC 60, filter on, tv path)')
    _show_trade(D, t, prm, 'tv', dl, 'blocked-signal close', rep_tv(pair, tf, sig, perm, prm, j, t))

    # ---- 4. stop-loss exit (XAU 60, filter on, tv path)
    pair, tf = 'XAU', '60'
    sig, perm, D = setup(pair, tf, *FULL[pair])
    prm = dict(PINE, trailOn=True, trailUnit='percent', trailAct=0.3, trailOff=0.1, slOn=True, slDist=0.25)
    prm['xpwInv'] = True
    dl = {}
    T, info = run_ref(D, prm, 'tv', declog=dl)
    j, t = pick(T, lambda j, t: t.xkind == 'sl' and 2 <= t.xrow - t.row <= 4 and t.isLong and t.xpx == t.sl)
    print('#' * 118)
    print('TRACE 4: a STOP-LOSS exit of an inverted trade (XAU 60, filter on, tv path): a LONG entry sold short, stop ABOVE')
    _show_trade(D, t, prm, 'tv', dl, 'stop exit', rep_tv(pair, tf, sig, perm, prm, j, t))

    # ---- 5. trailing exit on the 1-minute path (XAU 240, filter on, mag): a SHORT entry bought, trail below
    pair, tf = 'XAU', '240'
    sig, perm, D = setup(pair, tf, *FULL[pair])
    prm = dict(PINE, trailOn=True, trailUnit='percent', trailAct=0.3, trailOff=0.1, slOn=True, slDist=0.25)
    prm['xpwInv'] = True
    dl = {}
    T, info = run_ref(D, prm, 'mag', declog=dl)
    j, t = pick(T, lambda j, t: t.xkind == 'trail' and not t.isLong and t.xrow - t.row == 1 and t.arm_at is not None
                and t.arm_at[0] == t.xrow and 2 <= t.arm_at[1] and t.arm_at[1] + 2 <= t.xsub <= t.arm_at[1] + 30)
    print('#' * 118)
    print('TRACE 5: a TRAILING exit of an inverted trade on the 1-minute path (XAU 240, filter on, mag): a SHORT entry bought, trail BELOW the best price')
    _show_trade(D, t, prm, 'mag', dl, 'trailing exit', rep_mag(pair, tf, sig, perm, prm, j, t, D))
    print('#' * 118)
    print('traces: %d of 5 replica rows differ from the reference' % nbad)
    return nbad


# =============================================================================== sensitivity
# One line of the option broken at a time IN THE REFERENCE (text substitution on the reference
# section of this file); the comparisons must then report differences from the (unchanged) replica.
MUTANTS = [
    ('control', 'the reference as it is', []),
    ('posn', 'decisions read the real position (xpwPosN = strategy.position_size)',
     [('xpwPosN = -position_size if xpwInv else position_size', 'xpwPosN = position_size')]),
    ('side', 'the entry is not sent on the other side (realLong = isLong)',
     [('realLong = (not isLong) if xpwInv else isLong', 'realLong = isLong')]),
    ('tradedir', '"Trade direction" keeps its old tests when inverted',
     [('        if xpwInv:\n            allowLong = tradeDir != LONG_ONLY', '        if False:\n            allowLong = tradeDir != LONG_ONLY')]),
    ('room', '`room > 0 or xpwPosN < 0` reads the real position',
     [('if room > 0 or xpwPosN < 0:', 'if room > 0 or position_size < 0:'),
      ('if room > 0 or xpwPosN > 0:', 'if room > 0 or position_size > 0:')]),
    ('close', 'closeL / closeS read the real position',
     [('closeL = xpwPosN > 0 and', 'closeL = position_size > 0 and'),
      ('closeS = xpwPosN < 0 and', 'closeS = position_size < 0 and')]),
    ('levels', 'trail / stop laid out on the side of the label instead of the side really open',
     [('                    if realLong:\n                        t.A = close + trPts * MT', '                    if isLong:\n                        t.A = close + trPts * MT'),
      ('t.sl = (close - slPts * MT) if realLong else (close + slPts * MT)', 't.sl = (close - slPts * MT) if isLong else (close + slPts * MT)')]),
    ('reversal', 'the reversal is tested on the side of the label',
     [('if open_ and open_[0].dir == -d:', 'if open_ and open_[0].dir == (-d if not xpwInv else d):')]),
    ('blkgate', 'the filter gate judged on the side really traded (buyOk / sellOk swapped when inverted)',
     [('fgfBuyOk = (not fgfOn) or buyOkA[i]', 'fgfBuyOk = (not fgfOn) or (sellOkA[i] if xpwInv else buyOkA[i])'),
      ('fgfSellOk = (not fgfOn) or sellOkA[i]', 'fgfSellOk = (not fgfOn) or (buyOkA[i] if xpwInv else sellOkA[i])')]),
    ('cmt', 'entry comment without " (inv)"',
     [("(' (inv)' if xpwInv else '') + ' | ' + src", "' | ' + src")]),
    ('idletter', 'the id letter is the label side',
     [("id_ = ('S' if xpwInv else 'L') + str(bar_index)", "id_ = 'L' + str(bar_index)"),
      ("id_ = ('L' if xpwInv else 'S') + str(bar_index)", "id_ = 'S' + str(bar_index)")]),
    ('blktext', 'the blocked-close comment keeps the old text',
     [("('filter blocked LONG (inv), close | ' if xpwInv else 'filter blocked SHORT, close | ')", "'filter blocked SHORT, close | '")]),
]


def _mutant(name, subs):
    import types
    src = open(os.path.abspath(__file__)).read()
    mark = '\n# ' + '=' * 79 + ' money\n'
    if src.count(mark) != 1:
        raise RuntimeError('reference section marker not found once')
    ref, rest = src.split(mark)
    for old, new in subs:
        if ref.count(old) != 1:
            raise RuntimeError('mutant %s: %r found %d times in the reference section' % (name, old, ref.count(old)))
        ref = ref.replace(old, new)
    mod = types.ModuleType('vix_mut_' + name)
    mod.__file__ = os.path.abspath(__file__)
    exec(compile(ref + mark + rest, 'verify_inv_xpw[%s]' % name, 'exec'), mod.__dict__)
    return mod


def sens(pair='XAU', tf='240'):
    import engine
    import sweep_core as sc
    import xpw
    start, end = FULL[pair]
    sig, perm = load_case(pair, tf, start, end)
    sig_x = sc._trim_sig(xpw.xpw_signals(pair, tf, start, end, {'actL2': 'exit only', 'actDS': 'exit only', 'actInf': 'exit only'}))
    D = build_D(pair, tf, sig, perm)
    Dx = build_D(pair, tf, sig_x, perm, with_sub=False)
    sub_sc = sc.sub_bars(pair, tf, np.asarray(sig.index, dtype=np.int64))
    cfgs = corner_cfgs()[:8]
    # the replica's side, computed once (option ON everywhere)
    rep = []
    for filt in (False, True):
        P = sc.prep(pair, tf, sig, perm if filt else None, filt, inv=True)
        for cfg in cfgs:
            for path in ('tv', 'mag'):
                rep.append(('run_cfg ' + path, D, dict(PINE, **cfg, fgfOn=filt, xpwInv=True), path,
                            sc.run_cfg(P, cfg, path, sub=sub_sc), None))
            for cat, extra_prm, DD, ss in (('engine Both', {}, D, sig),
                                           ('engine one-side', {'tradeDir': LONG_ONLY}, D, sig),
                                           ('engine one-side', {'tradeDir': SHORT_ONLY, 'oppCloses': False}, D, sig),
                                           ('engine MaxOpen 1-2', {'maxOpen': 1}, D, sig),
                                           ('engine MaxOpen 1-2', {'maxOpen': 2}, D, sig),
                                           ('engine exit-only rows', {}, Dx, sig_x)):
                prm = dict(PINE, **cfg, fgfOn=filt, xpwInv=True)
                prm.update(extra_prm)
                rep.append((cat, DD, prm, 'tv', None, engine.backtest(pair, tf, ss, perm if filt else None, dict(prm))))
    cats = ['run_cfg tv', 'run_cfg mag', 'engine Both', 'engine one-side', 'engine MaxOpen 1-2', 'engine exit-only rows']
    ntot = {c_: sum(1 for r in rep if r[0] == c_) for c_ in cats}
    print('%s %s full window, option ON: %d replica runs (%s)' % (pair, tf, len(rep), ', '.join('%s %d' % kv for kv in ntot.items())))
    print('%-9s %-78s %s' % ('mutant', 'what is broken in the reference', ' | '.join(cats)))
    nfail = 0
    for name, what, subs in MUTANTS:
        M = _mutant(name, subs)
        nb = dict.fromkeys(cats, 0)
        for cat, DD, prm, path, R, bt in rep:
            T, info = M.run_ref(DD, prm, path)
            if R is not None:
                bad = M.cmp_runcfg(T, R)
            else:
                bad = M.cmp_table(DD, T, bt[0]) + M.cmp_summary(T, info, bt[1])
            nb[cat] += bool(bad)
        caught = sum(nb.values())
        ok = (caught == 0) if name == 'control' else (caught > 0)
        nfail += not ok
        print('%-9s %-78s %s  -> %s' % (name, what, ' | '.join('%*d' % (len(c_), nb[c_]) for c_ in cats),
                                       ('no difference (as it must)' if ok else 'DIFFERENCES') if name == 'control'
                                       else ('told apart in %d runs' % caught if ok else 'NOT DETECTED')), flush=True)
    print('sens: %d of %d mutants not handled as expected' % (nfail, len(MUTANTS)))
    return nfail


# =============================================================================== main
def _win(args, pair, tf):
    nums = [a for a in args if a.lstrip('-').isdigit()]
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    if pair == 'BTC' and tf == '15':
        return BTC15_3M
    return FULL[pair]


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(0)
    mode = a[0]
    if mode == 'trace':
        sys.exit(1 if trace() else 0)
    if mode == 'sens':
        sys.exit(1 if sens() else 0)
    pair, tf = a[1], a[2]
    rest = a[3:]
    opt = {}
    pos = []
    k = 0
    while k < len(rest):
        if rest[k].startswith('--'):
            opt[rest[k][2:]] = rest[k + 1]
            k += 2
        else:
            pos.append(rest[k])
            k += 1
    start, end = _win(pos, pair, tf)
    if mode == 'compare':
        sys.exit(1 if compare(pair, tf, start, end, int(opt.get('n', 12)), int(opt.get('seed', 20261124))) else 0)
    if mode == 'extra':
        sys.exit(1 if extra(pair, tf, start, end) else 0)
    if mode == 'json':
        sys.exit(1 if check_json(pair, tf) else 0)
    raise SystemExit('unknown mode %r' % mode)
