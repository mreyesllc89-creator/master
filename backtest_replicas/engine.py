"""engine.py: XPW v2.8 trailing-TP strategy + TradingView broker emulator (Component 3, CANONICAL).

Canonical module chosen by the reconciler: a copy of engine_b.py (implementation B), with only
this docstring changed. engine_a.py and engine_b.py agree on every trade row and column on
every reconciliation case; see reconcile_engine.md for the agreement table, the fixes and the
hand traces, and engine_b_notes.md for B's interpretations of the Pine.

Replicates the STRATEGY section of
/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine
(from `int nLong  = array.size(longSrc)` to the end of the limit bookkeeping, plus the
FGD diagnostics funnel) and the strategy() declaration
(process_orders_on_close=true, pyramiding=100, default_qty percent_of_equity 10).

Interface (SPEC.md, component 3):

    backtest(pair, chart_tf, sig, perm, params=None) -> (trades, summary)

`sig`  = xpw_signals(...) output (index = row numbers of data/<pair>_<chart_tf>.parquet).
`perm` = fgf_permissions(...) output on the same rows, or None (filter off).
Only entryFill = "Signal tick" is implemented (market entries at the signal bar close);
"Limit at label price" raises NotImplementedError.

`backtest_bars(bars, sig, perm, params)` is the same engine on an explicit OHLC frame
(columns open, high, low, close, t_open, t_close, same index as `sig`); the unit tests
use it with hand-made bars.

UPDATE 1 ("Inverted direction: opposite side at the same entries", Pine input xpwInv, the
Pine at HEAD d28ba97): params key 'xpwInv' (alias 'inv'), default False = the pre-Update-1
engine, expression for expression. True: allowLong / allowShort swap their "Trade direction"
tests (the option restricts the orders really placed); every decision (the gate, oppL / oppS,
closeL / closeS, room / "Max open entries", `room > 0 or xpwPosN < 0`) is taken in the normal
frame on xpwPosN = -strategy.position_size; each entry is then sent on the OTHER side at the
same close, with the same tick distances for its trailing TP / stop on the trade really open.
The trade table reports the REAL side (`dir`, the id letter, "ENTER LONG / SHORT (inv)") and
adds `sig_dir`, the side of the label / the filter (= -dir); the FGD counts of the summary
(raw_long, blocked_long, go_long_bars, ...) stay on the filter's side, long_entries /
short_entries / gross_pl_long / gross_pl_short are real sides. See inv_xpw_notes.md.

All prices are float; levels are NOT rounded to the tick grid (SPEC rule 4/5 formulas
used literally). Touch tests use a tolerance of 1e-6 ticks so that a level that equals a
price on the 0.01 grid (up to float noise) counts as touched / reached.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd
import numba as nb

W = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(W, 'data')

DEFAULTS = {
    'tradeDir': 'Both',            # "Both" | "Long only (buy only)" | "Short only (sell only)"
    'oppCloses': True,
    'fgfOn': True,
    'fgfBlkClose': True,
    'maxOpen': 20,
    'trailOn': True,
    'trailUnit': 'price',          # "ticks" | "price" | "percent"
    'trailAct': 2.0,
    'trailOff': 1.0,
    'slOn': False,
    'slDist': 3.0,
    'entryFill': 'Signal tick',
    'mintick': 0.01,
    # UPDATE 1: "Inverted direction: opposite side at the same entries" (alias key: 'inv')
    'xpwInv': False,
    # strategy() declaration, not an input; exposed for completeness
    'pyramiding': 100,
}

TRADE_DIRS = ('Both', 'Long only (buy only)', 'Short only (sell only)')
UNITS = {'ticks': 0, 'price': 1, 'percent': 2}

K_NONE, K_TRAIL, K_SL, K_CLOSEALL, K_REVERSE, K_END = 0, 1, 2, 3, 4, 5
KIND_NAMES = {K_TRAIL: 'trail', K_SL: 'sl', K_CLOSEALL: 'close_all', K_REVERSE: 'reverse', K_END: 'end'}

NEG = -1.0e300


def _params(params):
    p = dict(DEFAULTS)
    if params:
        for k, v in params.items():
            if k in p:
                p[k] = v
        if 'inv' in params:                       # alias of xpwInv
            if 'xpwInv' in params and bool(params['xpwInv']) != bool(params['inv']):
                raise ValueError("params 'inv' and 'xpwInv' disagree")
            p['xpwInv'] = params['inv']
    p['xpwInv'] = bool(p['xpwInv'])
    if p['entryFill'] != 'Signal tick':
        raise NotImplementedError('entryFill %r: only "Signal tick" is implemented' % (p['entryFill'],))
    if p['tradeDir'] not in TRADE_DIRS:
        raise ValueError('tradeDir %r not one of %r' % (p['tradeDir'], TRADE_DIRS))
    if p['trailUnit'] not in UNITS:
        raise ValueError('trailUnit %r not one of %r' % (p['trailUnit'], tuple(UNITS)))
    p['maxOpen'] = int(p['maxOpen'])
    p['pyramiding'] = int(p['pyramiding'])
    return p


# --------------------------------------------------------------------- data
_BARS_CACHE: dict = {}


def load_bars(pair: str, chart_tf: str) -> pd.DataFrame:
    key = (pair, str(chart_tf))
    df = _BARS_CACHE.get(key)
    if df is None:
        df = pd.read_parquet(os.path.join(DATA, '%s_%s.parquet' % (pair, chart_tf)),
                             columns=['open', 'high', 'low', 'close', 't_open', 't_close'])
        df = df.reset_index(drop=True)
        _BARS_CACHE[key] = df
    return df


# ------------------------------------------------------------------ kernels
@nb.njit(cache=True, inline='always')
def _to_ticks(d, ref, unit, mt):
    # Pine toTicks(): ticks as is, price / mintick, percent of ref / mintick
    if unit == 0:
        return d
    elif unit == 1:
        return d / mt
    return ref * d / 100.0 / mt


@nb.njit(cache=True)
def _walk(v0, v1, v2, v3, act, best, A, off, sl, has_tr, has_sl, tol):
    """One bar of one trade's exit order, in 'long space' (shorts are negated).

    v0..v3: the intrabar path (open, first extreme, second extreme, close).
    act/best: trailing state (armed, best price since arming). A: activation price,
    off: trail offset (price), sl: stop-loss price.
    Returns (kind, fill_px, act, best); kind 0 = no exit.
    """
    sv = sl if has_sl else NEG
    ts = (best - off) if (has_tr and act) else NEG
    lvl = ts if ts > sv else sv
    # gap at the open: the bar opens at or beyond the stop -> fill at the open
    if v0 <= lvl + tol:
        kind = 1 if (ts >= sv) else 2
        return kind, v0, act, best
    if has_tr:
        if act:
            if v0 > best:
                best = v0
        elif v0 >= A - tol:
            act = True
            best = v0
    a = v0
    for s in range(3):
        if s == 0:
            b = v1
        elif s == 1:
            b = v2
        else:
            b = v3
        if b > a:
            # rising: the trail can arm and ratchet; nothing can be touched
            if has_tr:
                if act:
                    if b > best:
                        best = b
                elif b >= A - tol:
                    act = True
                    best = b
        elif b < a:
            # falling: stops are fixed along the segment; the higher one is hit first
            ts = (best - off) if (has_tr and act) else NEG
            lvl = ts if ts > sv else sv
            if b <= lvl + tol:
                kind = 1 if (ts >= sv) else 2
                px = lvl if lvl < a else a
                return kind, px, act, best
        a = b
    return 0, 0.0, act, best


@nb.njit(cache=True)
def _run(o, h, l, c, goL, goS, nl, ns, cL, cS,
         maxOpen, pyr, trailOn, slOn, unit, trailAct, trailOff, slDist, mt, tol, cap, ocap, inv=False):
    # inv = Pine xpwInv (UPDATE 1). goL / goS / nl / ns / cL / cS are in the normal (decision)
    # frame; t_dir, pos_dir and the exit levels are the REAL side. inv False: the old kernel.
    n = c.shape[0]
    t_dir = np.zeros(cap, np.int8)
    t_row = np.zeros(cap, np.int64)
    t_k = np.zeros(cap, np.int32)
    t_epx = np.zeros(cap, np.float64)
    t_A = np.full(cap, np.nan)          # activation price (long space)
    t_off = np.full(cap, np.nan)        # trail offset, price
    t_sl = np.full(cap, np.nan)         # stop-loss price (long space)
    t_act = np.zeros(cap, np.bool_)
    t_best = np.zeros(cap, np.float64)
    t_xrow = np.full(cap, -1, np.int64)
    t_xpx = np.full(cap, np.nan)
    t_xkind = np.zeros(cap, np.int8)
    t_xby = np.full(cap, -1, np.int64)  # reverse: id of the reversing trade
    bar_close = np.zeros(n, np.int8)    # 1 = closeL fired, 2 = closeS (normal frame: xpwPosN > 0 / < 0)
    bar_skip = np.zeros(n, np.int32)    # entries not placed (room)
    bar_pyr = np.zeros(n, np.int32)     # entries placed but ignored (pyramiding)
    bar_open = np.zeros(n, np.int32)    # strategy.opentrades seen by the script
    bar_pos = np.zeros(n, np.int8)      # sign of strategy.position_size seen by the script
    open_ids = np.empty(ocap, np.int64)
    n_open = 0
    pos_dir = 0
    n_tr = 0
    for i in range(n):
        # 1. pending exit orders of open trades, intrabar along the path
        if n_open > 0:
            sgn = float(pos_dir)
            if (h[i] - o[i]) < (o[i] - l[i]):
                p1 = h[i]
                p2 = l[i]
            else:
                p1 = l[i]
                p2 = h[i]
            v0 = sgn * o[i]
            v1 = sgn * p1
            v2 = sgn * p2
            v3 = sgn * c[i]
            w = 0
            for q in range(n_open):
                j = open_ids[q]
                has_tr = not np.isnan(t_A[j])
                has_sl = not np.isnan(t_sl[j])
                if has_tr or has_sl:
                    kind, px, a2, b2 = _walk(v0, v1, v2, v3, t_act[j], t_best[j], t_A[j],
                                             t_off[j], t_sl[j], has_tr, has_sl, tol)
                    t_act[j] = a2
                    t_best[j] = b2
                else:
                    kind = 0
                    px = 0.0
                if kind != 0:
                    t_xrow[j] = i
                    t_xpx[j] = sgn * px
                    t_xkind[j] = kind
                else:
                    open_ids[w] = j
                    w += 1
            n_open = w
            if n_open == 0:
                pos_dir = 0
        # 2. the script at the close, with the updated position
        pos = pos_dir                    # sign of strategy.position_size (the real position)
        posn = -pos if inv else pos      # Pine xpwPosN: the position in the normal frame
        opent = n_open
        bar_open[i] = opent
        bar_pos[i] = pos
        if (posn > 0 and cL[i]) or (posn < 0 and cS[i]):
            for q in range(n_open):
                j = open_ids[q]
                t_xrow[j] = i
                t_xpx[j] = c[i]
                t_xkind[j] = K_CLOSEALL
            bar_close[i] = 1 if posn > 0 else 2
            n_open = 0
            pos_dir = 0
        room = maxOpen - opent
        for side in range(2):
            if side == 0:
                if not goL[i]:
                    continue
                d = 1
                cnt = nl[i]
            else:
                if not goS[i]:
                    continue
                d = -1
                cnt = ns[i]
            dr = -d if inv else d        # the side really traded (Pine realLong)
            for k in range(cnt):
                if room > 0 or posn == -d:
                    # market order, filled at this close in placement order
                    if pos_dir == -dr:
                        for q in range(n_open):
                            j = open_ids[q]
                            t_xrow[j] = i
                            t_xpx[j] = c[i]
                            t_xkind[j] = K_REVERSE
                            t_xby[j] = n_tr
                        n_open = 0
                        pos_dir = 0
                    if pos_dir == dr and n_open >= pyr:
                        bar_pyr[i] += 1
                    else:
                        j = n_tr
                        n_tr += 1
                        t_dir[j] = dr
                        t_row[j] = i
                        t_k[j] = k + 1
                        t_epx[j] = c[i]
                        e = dr * c[i]
                        ref = c[i]
                        if trailOn:
                            trp = _to_ticks(trailAct, ref, unit, mt)
                            if trp < 0.0:
                                trp = 0.0
                            tro = _to_ticks(trailOff, ref, unit, mt)
                            if tro < 1.0:
                                tro = 1.0
                            t_A[j] = e + trp * mt
                            t_off[j] = tro * mt
                            t_act[j] = e >= t_A[j] - tol      # trail_points 0: armed at the fill
                            t_best[j] = e
                        if slOn:
                            slp = _to_ticks(slDist, ref, unit, mt)
                            if slp < 1.0:
                                slp = 1.0
                            t_sl[j] = e - slp * mt
                        open_ids[n_open] = j
                        n_open += 1
                        pos_dir = dr
                    room -= 1
                else:
                    bar_skip[i] += 1
    # 3. trades still open at the window end
    if n > 0:
        for q in range(n_open):
            j = open_ids[q]
            t_xrow[j] = n - 1
            t_xpx[j] = c[n - 1]
            t_xkind[j] = K_END
    return (n_tr, t_dir, t_row, t_k, t_epx, t_A, t_off, t_sl, t_xrow, t_xpx, t_xkind, t_xby,
            bar_close, bar_skip, bar_pyr, bar_open, bar_pos)


# ------------------------------------------------------------------- driver
def _src_lists(sig, col):
    s = sig[col]
    return [list(x) if x is not None and not (isinstance(x, float) and np.isnan(x)) else [] for x in s]


def backtest_bars(bars: pd.DataFrame, sig: pd.DataFrame, perm: pd.DataFrame | None,
                  params: dict | None = None):
    p = _params(params)
    n = len(sig)
    if len(bars) != n:
        raise ValueError('bars and sig must have the same rows')
    o = np.ascontiguousarray(bars['open'].to_numpy(np.float64))
    h = np.ascontiguousarray(bars['high'].to_numpy(np.float64))
    l = np.ascontiguousarray(bars['low'].to_numpy(np.float64))
    c = np.ascontiguousarray(bars['close'].to_numpy(np.float64))
    t_open = bars['t_open'].to_numpy(np.int64) if 't_open' in bars else np.zeros(n, np.int64)
    t_close = bars['t_close'].to_numpy(np.int64) if 't_close' in bars else np.zeros(n, np.int64)
    rows = np.asarray(sig.index, dtype=np.int64)

    longSrc = _src_lists(sig, 'longSrc')
    shortSrc = _src_lists(sig, 'shortSrc')
    nLraw = np.fromiter((len(x) for x in longSrc), np.int64, n)
    nSraw = np.fromiter((len(x) for x in shortSrc), np.int64, n)
    # "Long and short labels on the same bar cancel out"
    both = (nLraw > 0) & (nSraw > 0)
    nL = np.where(both, 0, nLraw)
    nS = np.where(both, 0, nSraw)
    if 'nLong' in sig and 'nShort' in sig:
        if not (np.array_equal(sig['nLong'].to_numpy(np.int64), nL)
                and np.array_equal(sig['nShort'].to_numpy(np.int64), nS)):
            raise ValueError('sig nLong / nShort disagree with the longSrc / shortSrc lists')
    exitL = sig['exitL'].to_numpy(bool) if 'exitL' in sig else np.zeros(n, bool)
    exitS = sig['exitS'].to_numpy(bool) if 'exitS' in sig else np.zeros(n, bool)
    exitLSrc = sig['exitLSrc'].tolist() if 'exitLSrc' in sig else [''] * n
    exitSSrc = sig['exitSSrc'].tolist() if 'exitSSrc' in sig else [''] * n

    filt = bool(p['fgfOn']) and perm is not None
    if filt:
        if not perm.index.equals(sig.index):
            perm = perm.reindex(sig.index)
            if perm[['buyOk', 'sellOk']].isna().any().any():
                raise ValueError('perm does not cover every sig row')
        buyOk = perm['buyOk'].to_numpy(bool)
        sellOk = perm['sellOk'].to_numpy(bool)
    else:
        buyOk = np.ones(n, bool)
        sellOk = np.ones(n, bool)

    # UPDATE 1: "Trade direction" restricts the orders really placed; inverted, a LONG entry is
    # sent as a SELL, so "Long only (buy only)" holds back the LONG entries (Pine allowLong /
    # allowShort with xpwInv). Everything below, down to the kernel call, is the normal frame.
    inv = bool(p['xpwInv'])
    if inv:
        allowLong = p['tradeDir'] != 'Long only (buy only)'
        allowShort = p['tradeDir'] != 'Short only (sell only)'
    else:
        allowLong = p['tradeDir'] != 'Short only (sell only)'
        allowShort = p['tradeDir'] != 'Long only (buy only)'
    # doneL / doneS never equal bar_index beforehand on history (one run per bar)
    sigLong = (nL > 0) & allowLong
    sigShort = (nS > 0) & allowShort
    # Signal tick mode: fgfLimOkL = fgfLimOkS = true
    blkL = sigLong & ~buyOk
    blkS = sigShort & ~sellOk
    goLong = sigLong & ~blkL
    goShort = sigShort & ~blkS
    oc = bool(p['oppCloses'])
    bc = bool(p['fgfBlkClose'])
    oppL = (nS > 0) & ((oc and not allowShort) | (bc & blkS))
    oppS = (nL > 0) & ((oc and not allowLong) | (bc & blkL))
    # closeL / closeS without the position test (done in the kernel), market mode
    cL = ~goLong & ~goShort & (exitL | oppL)
    cS = ~goShort & ~goLong & (exitS | oppS)

    cap = int((nL * goLong).sum() + (nS * goShort).sum()) + 1
    ocap = int(max(p['maxOpen'], int(nL.max(initial=0)), int(nS.max(initial=0)))) + 2
    mt = float(p['mintick'])
    tol = mt * 1e-6
    (n_tr, t_dir, t_row, t_k, t_epx, t_A, t_off, t_sl, t_xrow, t_xpx, t_xkind, t_xby,
     bar_close, bar_skip, bar_pyr, bar_open, bar_pos) = _run(
        o, h, l, c, goLong, goShort, nL.astype(np.int64), nS.astype(np.int64), cL, cS,
        p['maxOpen'], p['pyramiding'], bool(p['trailOn']), bool(p['slOn']), UNITS[p['trailUnit']],
        float(p['trailAct']), float(p['trailOff']), float(p['slDist']), mt, tol, cap, ocap, inv)

    # ---- comments (strings) and the trade table
    sl_ = slice(0, n_tr)
    d_ = t_dir[sl_].astype(np.int64)
    er = t_row[sl_]
    kk = t_k[sl_]
    xr = t_xrow[sl_]
    xk = t_xkind[sl_]
    # d_ is the REAL side. The label that placed the order sits in the list of its normal-frame
    # side (inverted: a real short comes from longSrc); the id letter and the comment name the
    # real side, the comment with " (inv)" (Pine placeEntry / the id lines, UPDATE 1).
    nd_ = -d_ if inv else d_
    tag = ' (inv)' if inv else ''
    ids, srcs, ecmt = [], [], []
    for j in range(n_tr):
        i = er[j]
        k = kk[j]
        s = longSrc[i][k - 1] if nd_[j] > 0 else shortSrc[i][k - 1]
        if d_[j] > 0:
            ids.append('L%d-%d' % (rows[i], k))
            ecmt.append('ENTER LONG' + tag + ' | ' + s)
        else:
            ids.append('S%d-%d' % (rows[i], k))
            ecmt.append('ENTER SHORT' + tag + ' | ' + s)
        srcs.append(s)
    blkS_txt = 'filter blocked LONG (inv), close | ' if inv else 'filter blocked SHORT, close | '
    blkL_txt = 'filter blocked SHORT (inv), close | ' if inv else 'filter blocked LONG, close | '
    xcmt = []
    for j in range(n_tr):
        kind = xk[j]
        i = xr[j]
        if kind == K_TRAIL:
            xcmt.append('trail TP | ' + srcs[j])
        elif kind == K_SL:
            xcmt.append('SL | ' + srcs[j])
        elif kind == K_REVERSE:
            xcmt.append(ecmt[t_xby[j]])
        elif kind == K_CLOSEALL:
            firstLong = longSrc[i][0] if len(longSrc[i]) > 0 else ''
            firstShort = shortSrc[i][0] if len(shortSrc[i]) > 0 else ''
            if bar_close[i] == 1:     # closeL
                xcmt.append('exit | ' + exitLSrc[i] if exitL[i] else
                            (blkS_txt + firstShort if blkS[i] else
                             'opp ENTER | ' + firstShort))
            else:                     # closeS
                xcmt.append('exit | ' + exitSSrc[i] if exitS[i] else
                            (blkL_txt + firstLong if blkL[i] else
                             'opp ENTER | ' + firstLong))
        else:
            xcmt.append('end')
    ld = d_ > 0
    A_real = np.where(ld, t_A[sl_], -t_A[sl_])
    sl_real = np.where(ld, t_sl[sl_], -t_sl[sl_])
    trades = pd.DataFrame({
        'id': ids,
        'dir': d_,
        'src': srcs,
        'entry_row': rows[er] if n_tr else np.zeros(0, np.int64),
        'entry_time': t_close[er],
        'entry_bar_time': t_open[er],
        'entry_px': t_epx[sl_],
        'exit_row': rows[xr] if n_tr else np.zeros(0, np.int64),
        'exit_time': t_close[xr],
        'exit_bar_time': t_open[xr],
        'exit_px': t_xpx[sl_],
        'exit_kind': [KIND_NAMES[int(x)] for x in xk],
        'exit_comment': xcmt,
        'entry_comment': ecmt,
        'trail_act_px': A_real,
        'trail_off': t_off[sl_],
        'sl_px': sl_real,
    })
    trades['pl'] = trades['dir'] * (trades['exit_px'] - trades['entry_px'])
    trades['bars_held'] = xr - er
    if inv:
        # only with the option on, so that the default frame keeps its pre-Update-1 columns
        trades['sig_dir'] = nd_

    kinds = trades['exit_kind'].value_counts().to_dict() if n_tr else {}
    summary = {
        'bars': int(n),
        'filter': 'on' if filt else 'off',
        'sig_bars_long': int((nLraw > 0).sum()),
        'sig_bars_short': int((nSraw > 0).sum()),
        'sig_bars_cancelled': int(both.sum()),
        'raw_long': int(sigLong.sum()),            # FGD raw long count
        'raw_short': int(sigShort.sum()),          # FGD raw short count
        'blocked_long': int(blkL.sum()),           # FGD blocked long count
        'blocked_short': int(blkS.sum()),          # FGD blocked short count
        'go_long_bars': int(goLong.sum()),
        'go_short_bars': int(goShort.sum()),
        'entries': int(n_tr),
        'long_entries': int(ld.sum()),
        'short_entries': int((~ld).sum()),
        'entries_skipped_room': int(bar_skip.sum()),
        'entries_ignored_pyramiding': int(bar_pyr.sum()),
        'entry_bars': int(np.unique(er).size),
        'close_all_bars': int((bar_close > 0).sum()),
        'exits_trail': int(kinds.get('trail', 0)),
        'exits_sl': int(kinds.get('sl', 0)),
        'exits_close_all': int(kinds.get('close_all', 0)),
        'exits_reverse': int(kinds.get('reverse', 0)),
        'exits_end': int(kinds.get('end', 0)),
        'gross_pl': float(trades['pl'].sum()) if n_tr else 0.0,
        'gross_pl_long': float(trades.loc[ld, 'pl'].sum()) if n_tr else 0.0,
        'gross_pl_short': float(trades.loc[~ld, 'pl'].sum()) if n_tr else 0.0,
        'wins': int((trades['pl'] > 0).sum()) if n_tr else 0,
        'losses': int((trades['pl'] < 0).sum()) if n_tr else 0,
        'buyOk_bars': int(buyOk.sum()),
        'sellOk_bars': int(sellOk.sum()),
        'max_open': int(bar_open.max(initial=0)),
    }
    if inv:
        # only with the option on (the default summary keeps its pre-Update-1 keys)
        summary['xpwInv'] = True
    return trades, summary


def backtest(pair: str, chart_tf: str, sig: pd.DataFrame, perm: pd.DataFrame | None,
             params: dict | None = None):
    """SPEC component 3. Returns (trades, summary)."""
    allb = load_bars(pair, chart_tf)
    rows = np.asarray(sig.index, dtype=np.int64)
    if len(rows) and (rows.min() < 0 or rows.max() >= len(allb)):
        raise ValueError('sig index outside data/%s_%s.parquet' % (pair, chart_tf))
    bars = allb.iloc[rows]
    if 't_close' in sig and not np.array_equal(bars['t_close'].to_numpy(np.int64),
                                               sig['t_close'].to_numpy(np.int64)):
        raise ValueError('sig t_close does not match the data file rows')
    bars = bars.set_axis(sig.index)
    return backtest_bars(bars, sig, perm, params)
