"""verify_trail_apex.py: INDEPENDENT verifier of apex.py's trailing take profit and its
Bar Magnifier path 'mag' (SWEEP_AH_SPEC.md sections 1-2).

Written from the Pine (/home/user/master/ApexForge_Flow_Resonance_Strategy_FGF.pine,
"STRATEGY EXECUTION" and the apxTrail* inputs) and the spec, WITHOUT using apex.py's
broker / sub-bar code. From apex.py only prepare() is used, as INPUT: the per-bar signal
arrays (sig_l / sig_s), the filter permissions (buy_ok / sell_ok) and the Pine zone stop /
target per bar (stp_l, lim_l, stp_s, lim_s), plus the chart OHLC of the window.
The 1-minute sub-bars are rebuilt here from data/<PAIR>_1.parquet. apex.simulate() /
trades_frame() are only called as the system under test.

    python3 -I verify_trail_apex.py regress [CELL ...]     trail off vs saved out/apex_trades
    python3 -I verify_trail_apex.py compare CELL [N] [SEED] random grid settings x path x filter
    python3 -I verify_trail_apex.py trace                    hand traces of 5 trail exits
CELL = BTC_60 | XAU_60 | BTC_15 (3-month window 2025-01-01..2025-04-01) | XAU_240 | ...

Reference broker (TradingView, history, process_orders_on_close false):
  - The script runs at each chart bar close with the position after that bar's fills /
    exits; market orders (strategy.entry, strategy.close) fill at the next bar's open, in
    the order placed; pyramiding 0 (a same-side entry is ignored); an opposite entry
    reverses (kind 'reverse'); orders placed on the last window bar never fill; a trade
    still open after the last bar is closed at its close (kind 'end').
  - Pine logic per bar (window position i):
        blkClose and blkShort and pos>0 -> strategy.close long  (and mirrored)
        goLong: entry long; if pos<=0: ptsL = max(c*act/100/tick, 0), ofsL = max(c*off/100/tick, 1)
        goLong or (sigLong and pos>0): Exit Long = (stp_l[i], lim_l[i] or na when trailOn and
                                       not useTarget, ptsL, ofsL)   effective from bar i+1
    (shorts mirrored; trailOff -> pts / ofs na: no trailing).
  - Sizing qty = 1% x equity / close at the signal bar, equity = initial 1e6 + closed P/L
    (after costs) + open P/L at that close - the open trade's entry cost.
  - Costs per fill: rate x fill value + fee x qty (tv 0.04%; ours XAU $0.15/oz, BTC 0.02% +
    $0.10; stress XAU $0.25 + 0.01, BTC 0.035% + $0.10 + 0.01).
  - Exits of the open trade on each bar, from the entry fill (that bar's open) on, along the
    path open -> high -> low -> close if (high-open) < (open-low) else open -> low -> high
    -> close (tv: the chart bar; mag: every 1-minute sub-bar in time order, each with its own
    path, the state carrying over). At every (sub-)bar open: a level already beyond fills at
    that open. Trailing (long; short mirrored): activation = fill + pts x tick; once price
    reaches it, armed with best = the price there; stop = best - ofs x tick, best only rises;
    on a falling segment the first level touched is the higher of trail stop / zone stop;
    on a rising segment the limit. pts 0 = armed at the fill. A re-sent exit changes stop /
    limit only; the trailing state and distances stay (Pine stores pts / ofs per trade).
  - Tie conventions (not decidable from the Pine): trail-stop touch / arming with a 1e-9
    price tolerance (real-number ties count as touches); equal trail and zone stops ->
    'trail'; at an open beyond both a stop and the limit -> the stop.
"""
import math
import os
import random
import sys
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import apex  # noqa: E402  (prepare() as input; simulate() as the system under test)

TICK = 0.01
INIT = 1_000_000.0
TOL = 1e-9
NAN = float('nan')
# mutation switches (all off = the reference); used by `mutate` to show the comparison has teeth
MUT = dict(tie_trail=True, path_le=False, no_sub_gap=False, reset_on_resend=False, dist_from_fill=False,
           act_from_close=False, eq_closed_only=False)
COUNT = {}


def _cnt(k, v=1):
    COUNT[k] = COUNT.get(k, 0) + v
WIN = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}
CELLS = {
    'BTC_60': ('BTC', '60', None, None),
    'XAU_60': ('XAU', '60', None, None),
    'BTC_15': ('BTC', '15', 1735689600, 1743465600),     # 2025-01-01 .. 2025-04-01
    'XAU_240': ('XAU', '240', None, None),
    'BTC_240': ('BTC', '240', None, None),
    'XAU_15': ('XAU', '15', None, None),
    'BTC_5': ('BTC', '5', None, None),
    'XAU_5': ('XAU', '5', None, None),
    'BTC_120': ('BTC', '120', None, None),
    'XAU_120': ('XAU', '120', None, None),
    'BTC_30': ('BTC', '30', None, None),
    'XAU_30': ('XAU', '30', None, None),
}
ACTS = (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
OFFS = (0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)


def ref_rates(pair, cost):
    """(rate of fill value, $ per unit) per fill, from SPEC_AH.md / SWEEP_AH_SPEC.md."""
    if cost == 'tv':
        return 0.0004, 0.0
    if cost == 'ours':
        return (0.0, 0.15) if pair == 'XAU' else (0.0002, 0.10)
    if cost == 'stress':
        return (0.0, 0.25 + 0.01) if pair == 'XAU' else (0.00035, 0.10 + 0.01)
    raise ValueError(cost)


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------
_M1 = {}


def minute_bars(pair):
    if pair not in _M1:
        t = pq.read_table(os.path.join(W, 'data', f'{pair}_1.parquet'),
                          columns=['open', 'high', 'low', 'close', 't_open'])
        _M1[pair] = {k: t.column(k).to_numpy() for k in ('open', 'high', 'low', 'close', 't_open')}
    return _M1[pair]


def build_sub(pair, S):
    """Independent sub-bar table: for chart bar r, the 1-minute rows with t_open in
    [t_open[r], t_close[r]). Returns (lo list, hi list, o, h, l, c lists of the needed span)."""
    m = minute_bars(pair)
    lo = np.searchsorted(m['t_open'], S['t_open'], 'left')
    hi = np.searchsorted(m['t_open'], S['t_close'], 'left')
    if (hi <= lo).any():
        raise RuntimeError('chart bar without sub-bars')
    a, b = int(lo[0]), int(hi[-1])
    sl = slice(a, b)
    return dict(lo=(lo - a).tolist(), hi=(hi - a).tolist(), o=m['open'][sl].tolist(),
                h=m['high'][sl].tolist(), l=m['low'][sl].tolist(), c=m['close'][sl].tolist(),
                t=m['t_open'][sl].tolist(), base=a)


def lists(S):
    if '_vl' not in S:
        S['_vl'] = {k: S[k].tolist() for k in ('o', 'h', 'l', 'c', 'sig_l', 'sig_s', 'buy_ok', 'sell_ok',
                                              'stp_l', 'lim_l', 'stp_s', 'lim_s', 't_open', 't_close')}
    return S['_vl']


# ---------------------------------------------------------------------------
# the reference broker
# ---------------------------------------------------------------------------
def _path(o, h, l, c):
    if MUT['path_le']:
        return (o, h, l, c) if (h - o) <= (o - l) else (o, l, h, c)
    return (o, h, l, c) if (h - o) < (o - l) else (o, l, h, c)


def _point(tr, ex, p, log):
    """A (sub-)bar open, or the end of a segment already handled: update the trailing state
    at price p and fill any level that p is beyond. Returns (px, kind) or None."""
    d = tr['dir']
    sv, lv, has_t = ex['stop'], ex['limit'], tr['has_trail']
    if d > 0:
        if has_t:
            if not tr['armed']:
                if p >= tr['act_px'] - TOL:
                    tr['armed'] = True
                    tr['best'] = p
                    if log is not None:
                        log.append(f'      armed at {p} (activation {tr["act_px"]:.6f})')
            elif p > tr['best']:
                tr['best'] = p
        ts = tr['best'] - tr['ofs'] if (has_t and tr['armed']) else NAN
        hit_t = p <= ts + TOL
        hit_s = p <= sv
        if hit_t or hit_s:
            if hit_t and (not hit_s or ts > sv or (MUT['tie_trail'] and ts == sv)):
                return p, 'trail'
            return p, 'sl'
        if p >= lv:
            return p, 'tp'
    else:
        if has_t:
            if not tr['armed']:
                if p <= tr['act_px'] + TOL:
                    tr['armed'] = True
                    tr['best'] = p
                    if log is not None:
                        log.append(f'      armed at {p} (activation {tr["act_px"]:.6f})')
            elif p < tr['best']:
                tr['best'] = p
        ts = tr['best'] + tr['ofs'] if (has_t and tr['armed']) else NAN
        hit_t = p >= ts - TOL
        hit_s = p >= sv
        if hit_t or hit_s:
            if hit_t and (not hit_s or ts < sv or (MUT['tie_trail'] and ts == sv)):
                return p, 'trail'
            return p, 'sl'
        if p <= lv:
            return p, 'tp'
    return None


def _segment(tr, ex, p0, p1):
    """Price moves monotonically from p0 to p1 (p0 already checked). Returns (px, kind) or None."""
    d = tr['dir']
    sv, lv, has_t = ex['stop'], ex['limit'], tr['has_trail']
    if p1 == p0:
        return None
    if d > 0:
        if p1 > p0:                       # rising: only the limit can fill; then trail state
            if p1 >= lv:
                return lv, 'tp'
            if has_t:
                if not tr['armed']:
                    if p1 >= tr['act_px'] - TOL:
                        tr['armed'] = True
                        tr['best'] = p1
                elif p1 > tr['best']:
                    tr['best'] = p1
            return None
        ts = tr['best'] - tr['ofs'] if (has_t and tr['armed']) else NAN
        hit_t = p1 <= ts + TOL
        hit_s = p1 <= sv
        if hit_t and hit_s:
            _cnt('seg_both_stops')
            if ts == sv:
                _cnt('seg_equal_stops')
            return (ts, 'trail') if (ts > sv or (MUT['tie_trail'] and ts == sv)) else (sv, 'sl')
        if hit_t:
            return ts, 'trail'
        if hit_s:
            return sv, 'sl'
        return None
    if p1 < p0:                           # falling (short): only the limit; then trail state
        if p1 <= lv:
            return lv, 'tp'
        if has_t:
            if not tr['armed']:
                if p1 <= tr['act_px'] + TOL:
                    tr['armed'] = True
                    tr['best'] = p1
            elif p1 < tr['best']:
                tr['best'] = p1
        return None
    ts = tr['best'] + tr['ofs'] if (has_t and tr['armed']) else NAN
    hit_t = p1 >= ts - TOL
    hit_s = p1 >= sv
    if hit_t and hit_s:
        _cnt('seg_both_stops')
        if ts == sv:
            _cnt('seg_equal_stops')
        return (ts, 'trail') if (ts < sv or (MUT['tie_trail'] and ts == sv)) else (sv, 'sl')
    if hit_t:
        return ts, 'trail'
    if hit_s:
        return sv, 'sl'
    return None


def walk(tr, ex, paths, log=None):
    """paths: list of 4-point (sub-)bar paths in time order."""
    prev = None
    for k, pts in enumerate(paths):
        if MUT['no_sub_gap'] and k > 0:
            r = _segment(tr, ex, prev, pts[0])      # mutation: the jump is a continuous move
        else:
            r = _point(tr, ex, pts[0], log)
        if r is not None:
            _cnt('exit_at_open_' + ('first' if k == 0 else 'later_sub') + '_' + r[1])
        if log is not None:
            log.append(f'    sub {k:3d} path {pts}  armed={tr["armed"]} best={tr["best"]} '
                       f'trail_stop={_tstop(tr)} zone_stop={ex["stop"]} limit={ex["limit"]}')
        if r is not None:
            return r + (k,)
        for j in range(3):
            r = _segment(tr, ex, pts[j], pts[j + 1])
            if r is not None:
                return r + (k,)
        prev = pts[3]
        if log is not None and tr['armed']:
            log.append(f'          after: best={tr["best"]} trail_stop={_tstop(tr)}')
    return None


def _tstop(tr):
    if not (tr['has_trail'] and tr['armed']):
        return None
    return tr['best'] - tr['dir'] * tr['ofs']


def ref_run(S, X, sub=None, trace_trades=None):
    """Reference broker. X: trailOn, trailAct, trailOff, useTarget, blkClose, cost, path.
    Returns a list of trade dicts (bars as window positions)."""
    V = lists(S)
    o, h, l, c = V['o'], V['h'], V['l'], V['c']
    sigL, sigS, bok, sok = V['sig_l'], V['sig_s'], V['buy_ok'], V['sell_ok']
    stpL, limL, stpS, limS = V['stp_l'], V['lim_l'], V['stp_s'], V['lim_s']
    n = len(c)
    rate, fee = ref_rates(S['pair'], X['cost'])
    trail_on = bool(X['trailOn'])
    act = float(X.get('trailAct', 1.0))
    off = float(X.get('trailOff', 0.5))
    drop_target = trail_on and not X['useTarget']
    blk = bool(X['blkClose'])
    mag = X['path'] == 'mag'
    if mag and sub is None:
        raise ValueError('mag needs sub')

    trades = []
    closed = 0.0
    tr = None                       # open trade
    exits = {1: None, -1: None}     # Exit Long / Exit Short as last sent
    pts_v = {1: NAN, -1: NAN}       # Pine vars apxTrPts / apxTrOfs
    ofs_v = {1: NAN, -1: NAN}
    pend = None
    log = None

    def close(i, px, kind):
        nonlocal tr, closed
        xc = rate * px * tr['qty'] + fee * tr['qty']
        pnl = tr['dir'] * (px - tr['epx']) * tr['qty'] - tr['ecost'] - xc
        tr.update(exit_bar=i, exit_px=px, exit_kind=kind, exit_cost=xc, pnl=pnl)
        trades.append(tr)
        closed += pnl
        tr = None

    for i in range(n):
        # 1) market order placed at the previous close fills at this open
        if pend is not None:
            kind, side, q, sb = pend
            pend = None
            if kind == 'close':
                if tr is not None and tr['dir'] == side:
                    close(i, o[i], 'blocked_close')
            else:
                if tr is not None and tr['dir'] == -side:
                    close(i, o[i], 'reverse')
                if tr is None:
                    ex = exits[side]
                    pts, ofs = ex['pts'], ex['ofs']
                    has_t = not math.isnan(pts)
                    if has_t and MUT['dist_from_fill']:
                        pts = max(o[i] * act / 100.0 / TICK, 0.0)
                        ofs = max(o[i] * off / 100.0 / TICK, 1.0)
                    ref_px = c[sb] if MUT['act_from_close'] else o[i]
                    tr = dict(dir=side, entry_bar=i, signal_bar=sb, epx=o[i], qty=q,
                              ecost=rate * o[i] * q + fee * q, eq_before=INIT + closed,
                              has_trail=has_t, armed=False, best=NAN,
                              act_px=(ref_px + side * pts * TICK) if has_t else NAN,
                              ofs=(ofs * TICK) if has_t else NAN, pts=pts, ofs_ticks=ofs)
                # else: same side -> ignored (pyramiding 0)
        # 2) the open trade's exit along this bar's path
        if tr is not None:
            ex = exits[tr['dir']]
            if trace_trades is not None and (tr['entry_bar'], tr['dir']) in trace_trades:
                log = trace_trades[(tr['entry_bar'], tr['dir'])]
                log.append(f'  bar {i} t_open {V["t_open"][i]} O {o[i]} H {h[i]} L {l[i]} C {c[i]} '
                           f'| stop {ex["stop"]} limit {ex["limit"]} armed={tr["armed"]} best={tr["best"]}')
            else:
                log = None
            if mag:
                a, b = sub['lo'][i], sub['hi'][i]
                so, sh, sl_, sc = sub['o'], sub['h'], sub['l'], sub['c']
                paths = [_path(so[k], sh[k], sl_[k], sc[k]) for k in range(a, b)]
            else:
                paths = [_path(o[i], h[i], l[i], c[i])]
            r = walk(tr, ex, paths, log)
            if r is not None:
                px, kind, k = r
                tr['exit_sub'] = k
                if kind == 'trail' and i == tr['entry_bar']:
                    _cnt('trail_exit_on_fill_bar')
                if mag and k > 0:
                    _cnt('mag_exit_after_first_sub')
                if log is not None:
                    log.append(f'    -> EXIT {kind} at {px} on sub-bar {k}')
                close(i, px, kind)
        if i == n - 1:
            break                    # orders placed on the last bar never fill
        # 3) the script at the close of bar i
        pos = 0 if tr is None else tr['dir']
        eq = INIT + closed
        if tr is not None and not MUT['eq_closed_only']:
            eq += tr['dir'] * (c[i] - tr['epx']) * tr['qty'] - tr['ecost']
        goL = sigL[i] and bok[i]
        goS = sigS[i] and sok[i]
        blkL = sigL[i] and not bok[i]
        blkS = sigS[i] and not sok[i]
        if blk and blkS and pos > 0:
            pend = ('close', 1, None, i)
        if blk and blkL and pos < 0:
            pend = ('close', -1, None, i)
        for side, go, sig, stp, lim in ((1, goL, sigL[i], stpL[i], limL[i]),
                                        (-1, goS, sigS[i], stpS[i], limS[i])):
            if go:
                pend = ('entry', side, 0.01 * eq / c[i], i)
                if pos * side <= 0:          # flat or opposite: a new trade
                    if trail_on:
                        pts_v[side] = max(c[i] * act / 100.0 / TICK, 0.0)
                        ofs_v[side] = max(c[i] * off / 100.0 / TICK, 1.0)
                    else:
                        pts_v[side] = NAN
                        ofs_v[side] = NAN
            if go or (sig and pos * side > 0):
                if pos * side > 0 and tr['has_trail']:
                    _cnt('resend_while_trailing')
                    if tr['armed']:
                        _cnt('resend_while_armed')
                    if MUT['reset_on_resend']:
                        tr['armed'] = False
                        tr['best'] = NAN
                exits[side] = dict(stop=stp, limit=NAN if drop_target else lim,
                                   pts=pts_v[side], ofs=ofs_v[side], bar=i)
    if tr is not None:
        close(n - 1, c[n - 1], 'end')
    return trades


# ---------------------------------------------------------------------------
# comparison with the engine
# ---------------------------------------------------------------------------
ICOLS = ('dir', 'entry_bar', 'exit_bar', 'signal_bar', 'entry_time', 'exit_time')
PCOLS = ('entry_px', 'exit_px')
FCOLS = ('qty', 'pnl', 'entry_cost', 'exit_cost', 'eq_before')


def ref_frame(S, trades):
    w0 = S['w0']
    V = lists(S)
    return pd.DataFrame({
        'entry_time': [V['t_open'][t['entry_bar']] for t in trades],
        'exit_time': [V['t_close' if t['exit_kind'] == 'end' else 't_open'][t['exit_bar']] for t in trades],
        'dir': [t['dir'] for t in trades],
        'entry_bar': [t['entry_bar'] + w0 for t in trades],
        'exit_bar': [t['exit_bar'] + w0 for t in trades],
        'signal_bar': [t['signal_bar'] + w0 for t in trades],
        'entry_px': [t['epx'] for t in trades],
        'exit_px': [t['exit_px'] for t in trades],
        'exit_kind': [t['exit_kind'] for t in trades],
        'qty': [t['qty'] for t in trades],
        'pnl': [t['pnl'] for t in trades],
        'entry_cost': [t['ecost'] for t in trades],
        'exit_cost': [t['exit_cost'] for t in trades],
        'eq_before': [t['eq_before'] for t in trades],
    }, columns=list(ICOLS + PCOLS + ('exit_kind',) + FCOLS))


def compare_frames(R, E, cols_f=FCOLS, rtol=1e-9):
    """Returns (ok, message, worst). Prices must be exactly equal."""
    if len(R) != len(E):
        k = min(len(R), len(E))
        first = None
        for j in range(k):
            if not (R['entry_bar'].iat[j] == E['entry_bar'].iat[j] and R['exit_bar'].iat[j] == E['exit_bar'].iat[j]
                    and R['exit_kind'].iat[j] == E['exit_kind'].iat[j]):
                first = j
                break
        return False, f'trade count ref {len(R)} eng {len(E)} (first diff at {first})', None
    if len(R) == 0:
        return True, 'no trades', {}
    worst = {}
    bad = []
    for col in ICOLS:
        m = R[col].to_numpy() != E[col].to_numpy()
        if m.any():
            bad.append((col, int(np.argmax(m))))
    m = R['exit_kind'].to_numpy() != E['exit_kind'].astype(str).to_numpy()
    if m.any():
        bad.append(('exit_kind', int(np.argmax(m))))
    for col in PCOLS:
        a, b = R[col].to_numpy(), E[col].to_numpy()
        dd = np.abs(a - b)
        worst[col] = float(dd.max())
        if (a != b).any():
            bad.append((col, int(np.argmax(a != b))))
    for col in cols_f:
        a, b = R[col].to_numpy(), E[col].to_numpy()
        dd = np.abs(a - b) / np.maximum(1.0, np.abs(b))
        worst[col] = float(dd.max())
        if (dd > rtol).any():
            bad.append((col, int(np.argmax(dd > rtol))))
    if bad:
        return False, 'mismatch ' + ', '.join(f'{c}@{j}' for c, j in bad), worst
    return True, 'equal', worst


def ref_summary(S, trades):
    """The summary fields a trade list determines (independent recomputation)."""
    V = lists(S)
    final = INIT + sum(t['pnl'] for t in trades)
    mid = S['mid']
    first = [t for t in trades if V['t_open'][t['entry_bar']] <= mid]
    second = [t for t in trades if V['t_open'][t['entry_bar']] > mid]
    p1 = 1.0
    for t in first:
        p1 *= 1.0 + t['pnl'] / t['eq_before']
    p2 = 1.0
    for t in second:
        p2 *= 1.0 + t['pnl'] / t['eq_before']
    kinds = {}
    for t in trades:
        kinds[t['exit_kind']] = kinds.get(t['exit_kind'], 0) + 1
    return dict(trades=len(trades), net_pct=100.0 * (final - INIT) / INIT, final_equity=final,
                h1r_pct=100.0 * (p1 - 1.0), h2r_pct=100.0 * (p2 - 1.0), h1_trades=len(first),
                h2_trades=len(second), kinds=kinds,
                avg_bars_held=(sum(t['exit_bar'] - t['entry_bar'] for t in trades) / len(trades)) if trades else NAN)


def compare_summary(rs, es):
    bad = []
    for k in ('trades', 'h1_trades', 'h2_trades'):
        if rs[k] != es[k]:
            bad.append(k)
    for k in ('net_pct', 'final_equity', 'h1r_pct', 'h2r_pct', 'avg_bars_held'):
        a, b = rs[k], es[k]
        if not (a == b or (math.isnan(a) and math.isnan(b)) or abs(a - b) <= 1e-9 * max(1.0, abs(b))):
            bad.append(k)
    ek = {k: v for k, v in es['exit_kinds'].items() if v}
    if ek != rs['kinds']:
        bad.append('exit_kinds')
    for k, v in rs['kinds'].items():
        if es['exit_' + k] != v:
            bad.append('exit_' + k)
    return bad


# ---------------------------------------------------------------------------
# modes
# ---------------------------------------------------------------------------
_S = {}


def prep(cell, fgf_on, rev, full=False):
    pair, tf, s, e = CELLS[cell]
    key = (cell, fgf_on, rev, full)
    if key not in _S:
        p = {'fgfOn': fgf_on, 'reverse': rev}
        if s is not None and not full:
            p['start'], p['end'] = s, e
        _S[key] = apex.prepare(pair, tf, p)
    return _S[key]


def regress(cells):
    """Trail off, cost tv, every saved variant: the reference equals out/apex_trades."""
    variants = {'off': (False, False, True), 'on': (True, False, True), 'on_noblk': (True, False, False),
                'rev_off': (False, True, True), 'rev_on': (True, True, True)}
    tot = bad = rows = 0
    for cell in cells:
        for v, (fon, rev, blk) in variants.items():
            S = prep(cell, fon, rev, full=True)
            f = os.path.join(W, 'out', 'apex_trades', f'{cell}_{v}.parquet')
            if not os.path.exists(f):
                continue
            saved = pd.read_parquet(f)
            X = dict(trailOn=False, trailAct=1.0, trailOff=0.5, useTarget=True, blkClose=blk, cost='tv', path='tv')
            R = ref_frame(S, ref_run(S, X))
            ok, msg, worst = compare_frames(R, saved, cols_f=('qty', 'pnl', 'entry_cost', 'exit_cost'))
            tot += 1
            rows += len(saved)
            bad += not ok
            print(f'regress {cell:8s} {v:9s} trades {len(saved):6d}: {"OK" if ok else "FAIL"} {msg}', flush=True)
    print(f'REGRESS {"PASS" if bad == 0 else "FAIL"}: {tot - bad}/{tot} runs, {rows} saved rows')
    return bad == 0


def grid():
    G = []
    for ut in (True, False):
        G.append(dict(trailOn=False, trailAct=1.0, trailOff=0.5, useTarget=ut))
        for a in ACTS:
            for o in OFFS:
                G.append(dict(trailOn=True, trailAct=a, trailOff=o, useTarget=ut))
    return G


def compare(cell, nset=40, seed=1, offgrid=False):
    pair = CELLS[cell][0]
    rng = random.Random(seed * 1000 + sum(map(ord, cell)))
    G = grid()
    trail_idx = [k for k, g in enumerate(G) if g['trailOn']]
    pick = rng.sample(trail_idx, nset - 2) + [0, 197]          # + both trail-off rows
    if offgrid:      # uniform / boundary values, incl. offset 0 (1-tick floor) and activation 0
        G = []
        for _ in range(nset):
            a = rng.choice((0.0, 0.0, rng.uniform(0, 0.3), rng.uniform(0, 5)))
            o = rng.choice((0.0, 0.0, 1e-4, rng.uniform(0, 0.05), rng.uniform(0, 5)))
            G.append(dict(trailOn=True, trailAct=a, trailOff=o, useTarget=rng.random() < 0.5))
        pick = list(range(nset))
    t0 = time.time()
    sub = build_sub(pair, prep(cell, False, False))
    print(f'{cell}: sub-bars built in {time.time() - t0:.1f}s ({len(sub["o"])} 1m rows)', flush=True)
    stats = dict(runs=0, fail=0, trades=0, kinds={}, sum_fail=0)
    t_ref = t_eng = 0.0
    for k in pick:
        g = G[k]
        cost = rng.choice(('tv', 'ours', 'stress'))
        rev = rng.random() < 0.3
        blk = rng.random() < 0.8
        for path in ('tv', 'mag'):
            for fon in (False, True):
                S = prep(cell, fon, rev)
                X = dict(g, blkClose=blk, cost=cost, path=path)
                t1 = time.time()
                rt = ref_run(S, X, sub if path == 'mag' else None)
                t2 = time.time()
                ex = {kk: X[kk] for kk in ('trailOn', 'trailAct', 'trailOff', 'useTarget', 'blkClose', 'cost', 'path')}
                out, es = apex.simulate(S, ex)
                E = apex.trades_frame(S, out)
                t3 = time.time()
                t_ref += t2 - t1
                t_eng += t3 - t2
                R = ref_frame(S, rt)
                ok, msg, worst = compare_frames(R, E)
                sb = compare_summary(ref_summary(S, rt), es)
                stats['runs'] += 1
                stats['trades'] += len(R)
                for kk, vv in R['exit_kind'].value_counts().items():
                    stats['kinds'][kk] = stats['kinds'].get(kk, 0) + int(vv)
                if not ok or sb:
                    stats['fail'] += 1
                    print(f'  FAIL {cell} set#{k} {g} cost={cost} rev={rev} blk={blk} path={path} fgf={fon}: '
                          f'{msg} summary_bad={sb}', flush=True)
                    if not ok and len(R) == len(E):
                        show_diff(R, E)
    print(f'{cell}: {stats["runs"]} runs, {stats["runs"] - stats["fail"]} equal, {stats["trades"]} trades, '
          f'kinds {dict(sorted(stats["kinds"].items()))}; ref {t_ref:.1f}s engine {t_eng:.1f}s', flush=True)
    print(f'COMPARE {cell} {"PASS" if stats["fail"] == 0 else "FAIL"}')
    return stats


MUTATIONS = {
    'tol0 (exact trail compares)': ('TOL', 0.0),
    'equal stops -> sl': ('tie_trail', False),
    'path rule <= instead of <': ('path_le', True),
    'no gap rule between sub-bars': ('no_sub_gap', True),
    'reset trail state on re-send': ('reset_on_resend', True),
    'distances from the fill open': ('dist_from_fill', True),
    'activation from the signal close': ('act_from_close', True),
    'sizing on closed equity': ('eq_closed_only', True),
}


def mutate(cells, nset=12, seed=7):
    """Coverage of the reference (event counts) and its power: for each mutation of the
    reference, the number of runs in which it no longer equals the engine."""
    global TOL
    G = grid()
    trail_idx = [k for k, g in enumerate(G) if g['trailOn']]
    hits = {m: 0 for m in MUTATIONS}
    runs = mag_diff = 0
    COUNT.clear()
    for cell in cells:
        pair = CELLS[cell][0]
        rng = random.Random(seed * 1000 + sum(map(ord, cell)))
        sub = build_sub(pair, prep(cell, False, False))
        for k in rng.sample(trail_idx, nset):
            g = G[k]
            cost = rng.choice(('tv', 'ours', 'stress'))
            rev = rng.random() < 0.3
            for fon in (False, True):
                S = prep(cell, fon, rev)
                frames = {}
                for path in ('tv', 'mag'):
                    X = dict(g, blkClose=True, cost=cost, path=path)
                    out, _ = apex.simulate(S, {kk: X[kk] for kk in ('trailOn', 'trailAct', 'trailOff', 'useTarget',
                                                                     'blkClose', 'cost', 'path')})
                    E = apex.trades_frame(S, out)
                    frames[path] = E
                    sb = sub if path == 'mag' else None
                    R = ref_run(S, X, sb)
                    ok, msg, _ = compare_frames(ref_frame(S, R), E)
                    if not ok:
                        print('  base reference differs!', cell, g, path, fon, msg)
                    runs += 1
                    saved = dict(COUNT)
                    for name, (flag, val) in MUTATIONS.items():
                        if flag == 'TOL':
                            old, TOL = TOL, val
                        else:
                            old, MUT[flag] = MUT[flag], val
                        try:
                            Rm = ref_frame(S, ref_run(S, X, sb))
                        finally:
                            if flag == 'TOL':
                                TOL = old
                            else:
                                MUT[flag] = old
                        hits[name] += not compare_frames(Rm, E)[0]
                    COUNT.clear()
                    COUNT.update(saved)
                a, b = frames['tv'], frames['mag']
                mag_diff += not (len(a) == len(b) and a.drop(columns=['exit_kind']).equals(b.drop(columns=['exit_kind']))
                                 and (a['exit_kind'] == b['exit_kind']).all())
    print(f'MUTATE cells {cells}: {runs} runs ({runs // 2} tv + {runs // 2} mag); '
          f'engine mag != tv in {mag_diff} of {runs // 2} (setting, filter) pairs')
    for name, v in hits.items():
        print(f'  mutation {name:36s}: differs from the engine in {v:4d} / {runs} runs')
    print('  reference event counts (unmutated):', dict(sorted(COUNT.items())))


def show_diff(R, E, maxn=3):
    cols = list(ICOLS + PCOLS + ('exit_kind',) + FCOLS)
    shown = 0
    for j in range(len(R)):
        r, e = R.iloc[j], E.iloc[j]
        diff = [c for c in cols if (r[c] != e[c] if c in ICOLS + PCOLS + ('exit_kind',)
                                     else abs(r[c] - e[c]) > 1e-9 * max(1, abs(e[c])))]
        if diff:
            print(f'    trade {j}: ' + '; '.join(f'{c} ref={r[c]} eng={e[c]}' for c in diff))
            shown += 1
            if shown >= maxn:
                break


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'regress':
        cells = sys.argv[2:] or ['BTC_60', 'XAU_60', 'BTC_15', 'XAU_240']
        sys.exit(0 if regress(cells) else 1)
    elif mode == 'compare':
        cell = sys.argv[2]
        nset = int(sys.argv[3]) if len(sys.argv) > 3 else 40
        seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        st = compare(cell, nset, seed, offgrid=len(sys.argv) > 5 and sys.argv[5] == 'offgrid')
        sys.exit(0 if st['fail'] == 0 else 1)
    elif mode == 'mutate':
        mutate(sys.argv[2:] or ['BTC_60', 'XAU_60', 'BTC_15', 'XAU_240'])
    elif mode == 'trace':
        import verify_trail_apex_trace  # noqa
    else:
        raise SystemExit(__doc__)
