"""verify_inv_apex.py: INDEPENDENT verifier of the "Inverted direction" option (Update 1,
input apxInv) of the apex replica (apex.py, exit param `inv`).

Written from the Pine at HEAD (/home/user/master/ApexForge_Flow_Resonance_Strategy_FGF.pine,
sections "DIRECTION FILTER GATE", "INVERTED DIRECTION (Update 1)" and "STRATEGY EXECUTION")
WITHOUT reading apex.py's new broker code. From apex.py only prepare() is used, as INPUT:
the per-bar signal arrays (sig_l = bullResonance, sig_s = bearResonance), the filter
permissions (buy_ok = fgfBuyOk, sell_ok = fgfSellOk), the box edges (diag dBot / sTop) and
the window OHLC. The Pine's stopPrice / targetPrice are recomputed here from the box edges
and checked against prepare()'s arrays. The 1-minute sub-bars are rebuilt here from
data/<PAIR>_1.parquet. The path walker (_point / _segment / walk) is the one of the older
independent broker verify_trail_apex.py; the ORDER BOOK and the SCRIPT STEP are new and
literal: orders carry the Pine ids ("Apex Long" / "Apex Short", "Exit Long" / "Exit Short")
and the script step is a line-by-line transcription of the Pine (apxPosN, apxIdBuy, ...).

    python3 -I verify_inv_apex.py regress [CELL ...]          option off, trail off vs saved out/apex_trades
    python3 -I verify_inv_apex.py compare CELL [N] [SEED]     default + N random exit settings x filter x
                                                             path x cost x option {on, off}
    python3 -I verify_inv_apex.py mutate [CELL ...]           teeth: mutated references vs the replica
    python3 -I verify_inv_apex.py trace                       hand traces of 5+ inverted trades
    python3 -I verify_inv_apex.py checkjson PAIR TF [TF ...]  every entry of out/inv_apex_<PAIR>_<TF>.json
    python3 -I verify_inv_apex.py bits [CELL ...]             2.0*close - x vs close - (x - close), last bits
    python3 -I verify_inv_apex.py api                         parameter plumbing; chart "1": mag == tv
CELL = BTC_60 | XAU_60 | BTC_15 (3-month window 2025-01-01..2025-04-01) | XAU_240 | ...

Reference broker (TradingView, history, process_orders_on_close false, pyramiding 0):
  - The script runs at each chart bar close and sees strategy.position_size after that bar's
    fills / exits. strategy.entry / strategy.close are market orders: they fill at the next
    bar's open in the order placed. An entry on the side of the open position is ignored; on
    the other side it reverses (kind 'reverse'). strategy.close(id) closes the open trade only
    if it was opened by that id (kind 'blocked_close'). Orders placed on the last window bar
    never fill; a trade still open after the last bar is closed at its close (kind 'end').
  - strategy.exit(exit id, from_entry id, stop, limit, trail_points, trail_offset): one order
    per exit id, replaced when sent again, removed when the trade of its from_entry closes;
    it acts on the open trade whose entry id is its from_entry, from that trade's fill on.
  - The script step (Pine at HEAD), with pos = sign of the REAL position:
        apxPosN  = apxInv ? -pos : pos
        apxIdBuy = apxInv ? "Apex Short" : "Apex Long";  apxIdSell the other
        apxExBuy = apxInv ? "Exit Short" : "Exit Long";  apxExSell the other
        if apxBlkClose and apxBlkShort and apxPosN > 0: strategy.close(apxIdBuy)
        if apxBlkClose and apxBlkLong  and apxPosN < 0: strategy.close(apxIdSell)
        if apxGoLong:
            strategy.entry(apxIdBuy, apxInv ? short : long)
            if apxPosN <= 0: apxTrPtsL / apxTrOfsL := trailOn ? max(close*act/100/mintick, 0) /
                                                                max(close*off/100/mintick, 1) : na
        if apxGoLong or (bullResonance and apxPosN > 0):
            stopPrice = demand bottom * 0.995; targetPrice = close + (close - stopPrice) * rr
            strategy.exit(apxExBuy, apxIdBuy, stop = apxInv ? 2.0*close - stopPrice : stopPrice,
                          limit = trailOn and not useTarget ? na : (apxInv ? 2.0*close - targetPrice
                          : targetPrice), trail_points = apxTrPtsL, trail_offset = apxTrOfsL)
        (the SELL block mirrored: apxIdSell / apxExSell, supply top * 1.005, apxPosN >= 0 / < 0)
  - Sizing qty = 1% x equity / close at the signal bar, equity = initial 1e6 + closed P/L
    (after costs) + open P/L at that close - the open trade's entry cost.
  - Costs per fill: rate x fill value + fee x qty (tv 0.04%; ours XAU $0.15/oz, BTC 0.02% +
    $0.10; stress XAU $0.25 + 0.01, BTC 0.035% + $0.10 + 0.01).
  - Exits of the open trade on each bar, from the entry fill (that bar's open) on, along the
    path open -> high -> low -> close if (high-open) < (open-low) else open -> low -> high
    -> close (tv: the chart bar; mag: every 1-minute sub-bar in time order). At every
    (sub-)bar open a level already beyond fills at that open. Trailing on the REAL side of the
    trade: activation = fill + dir x pts x tick; once reached, stop = best -/+ ofs x tick.
  - Tie conventions as verify_trail_apex.py (1e-9 tolerance on trail touches / arming; equal
    trail and zone stops -> 'trail'; at an open beyond both a stop and the limit -> the stop).

Results of 2026-11-24 (logs in this directory): via_BTC_60.log, via_XAU_60.log, via_BTC_15.log,
via_XAU_240.log (compare, seed 1, 14 random settings), via2_<CELL>.log (seed 2, 12 cells),
via_mutate.log, via_trace.log, via_checkjson_BTC.log / _XAU.log, via_bits.log, via_bits_all.log
(verify_inv_apex_bits.py), via_api.log.
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
import apex  # noqa: E402  (prepare() as input; simulate() / trades_frame() as the system under test)

TICK = 0.01
INIT = 1_000_000.0
TOL = 1e-9
NAN = float('nan')
PINE = '/home/user/master/ApexForge_Flow_Resonance_Strategy_FGF.pine'
# mutation switches (all off = the reference); `mutate` shows the comparison has teeth
MUT = dict(no_mirror=False, mirror_alt=False, blk_real_pos=False, resend_real_pos=False, pts_real_pos=False,
           gate_order_side=False, trail_swapped_kind=False, same_side=False, mirror_fill=False)
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
    'BTC_5': ('BTC', '5', 1735689600, 1738368000),       # 2025-01-01 .. 2025-02-01
    'XAU_5': ('XAU', '5', 1483315200, 1491004800),       # 2017-01-02 .. 2017-04-01
    'BTC_120': ('BTC', '120', None, None),
    'XAU_120': ('XAU', '120', None, None),
    'BTC_30': ('BTC', '30', None, None),
    'XAU_30': ('XAU', '30', None, None),
    'BTC_1': ('BTC', '1', 1735689600, 1736899200),       # 2025-01-01 .. 2025-01-15
    'XAU_1': ('XAU', '1', 1488326400, 1489536000),       # 2017-03-01 .. 2017-03-15
}
ACTS = (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
OFFS = (0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
COSTS = ('tv', 'ours', 'stress')


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
    [t_open[r], t_close[r])."""
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


def _same(a, b):
    return bool(np.array_equal(a, b, equal_nan=True))


def lists(S):
    """Plain-Python inputs of the reference. The Pine's stopPrice / targetPrice per bar are
    recomputed from the box edges (demand bottom, supply top) and compared with prepare()."""
    if '_vl' in S:
        return S['_vl']
    V = {k: S[k].tolist() for k in ('o', 'h', 'l', 'c', 'sig_l', 'sig_s', 'buy_ok', 'sell_ok', 't_open', 't_close')}
    P = S['P']
    c = S['c']
    rr = float(P['rrRatio'])
    if not P['reverse']:
        d = S['diag']
        stop_l = d['dBot'] * 0.995                    # stopPrice = box.get_bottom(demandBox) * 0.995
        tgt_l = c + (c - stop_l) * rr                 # targetPrice = close + (close - stopPrice) * rrRatio
        stop_s = d['sTop'] * 1.005                    # stopPrice = box.get_top(supplyBox) * 1.005
        tgt_s = c - (stop_s - c) * rr                 # targetPrice = close - (stopPrice - close) * rrRatio
        if not (_same(stop_l, S['stp_l']) and _same(tgt_l, S['lim_l']) and _same(stop_s, S['stp_s'])
                and _same(tgt_s, S['lim_s'])):
            raise RuntimeError('prepare() stop / target arrays differ from the Pine formulas')
        if not (_same(S['sig_l'], d['bull']) and _same(S['sig_s'], d['bear'])):
            raise RuntimeError('prepare() signals are not bull / bear resonance')
        if bool((S['sig_l'] & S['sig_s']).any()):
            raise RuntimeError('a bar with both resonances')
        # the brackets of a normal trade are on the right sides of the signal close
        bl, br = S['sig_l'], S['sig_s']
        if not ((stop_l[bl] < c[bl]).all() and (tgt_l[bl] > c[bl]).all() and (stop_s[br] > c[br]).all()
                and (tgt_s[br] < c[br]).all()):
            raise RuntimeError('a normal bracket on the wrong side of its signal close')
    else:                                             # replica-only control: take its arrays as they are
        stop_l, tgt_l, stop_s, tgt_s = S['stp_l'], S['lim_l'], S['stp_s'], S['lim_s']
    V['stop_l'], V['tgt_l'], V['stop_s'], V['tgt_s'] = (x.tolist() for x in (stop_l, tgt_l, stop_s, tgt_s))
    S['_vl'] = V
    return V


# ---------------------------------------------------------------------------
# path walker (from the older independent broker verify_trail_apex.py; REAL trade side)
# ---------------------------------------------------------------------------
def _path(o, h, l, c):
    return (o, h, l, c) if (h - o) < (o - l) else (o, l, h, c)


def _point(tr, ex, p, log):
    """A (sub-)bar open: update the trailing state at price p and fill any level that p is
    beyond. Returns (px, kind) or None."""
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
            if hit_t and (not hit_s or ts >= sv):
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
            if hit_t and (not hit_s or ts <= sv):
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
            return (ts, 'trail') if ts >= sv else (sv, 'sl')
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
        return (ts, 'trail') if ts <= sv else (sv, 'sl')
    if hit_t:
        return ts, 'trail'
    if hit_s:
        return sv, 'sl'
    return None


def _tstop(tr):
    if not (tr['has_trail'] and tr['armed']):
        return None
    return tr['best'] - tr['dir'] * tr['ofs']


def walk(tr, ex, paths, log=None):
    """paths: list of 4-point (sub-)bar paths in time order."""
    for k, pts in enumerate(paths):
        r = _point(tr, ex, pts[0], log)
        if r is not None:
            _cnt('exit_at_open_' + ('first' if k == 0 else 'later_sub') + '_' + r[1])
        if log is not None:
            log.append(f'    sub {k:3d} path {pts}  armed={tr["armed"]} best={tr["best"]} '
                       f'trail_stop={_tstop(tr)} stop={ex["stop"]} limit={ex["limit"]}')
        if r is not None:
            return r + (k,)
        for j in range(3):
            r = _segment(tr, ex, pts[j], pts[j + 1])
            if r is not None:
                return r + (k,)
        if log is not None and tr['armed']:
            log.append(f'          after: best={tr["best"]} trail_stop={_tstop(tr)}')
    return None


# ---------------------------------------------------------------------------
# the reference: literal order book + the Pine's script step
# ---------------------------------------------------------------------------
LONG, SHORT = 1, -1                     # strategy.long / strategy.short


def ref_run(S, X, sub=None, trace_trades=None, events=None):
    """Reference broker. X: inv, trailOn, trailAct, trailOff, useTarget, blkClose, cost, path.
    Returns (trades, curve): trades = list of dicts (bars as window positions, `dir` = the REAL
    side), curve = dict(eq=[bar-close equity], pos=[real position sign at the close])."""
    V = lists(S)
    o, h, l, c = V['o'], V['h'], V['l'], V['c']
    bullRes, bearRes, fgfBuyOk, fgfSellOk = V['sig_l'], V['sig_s'], V['buy_ok'], V['sell_ok']
    stopL, tgtL, stopS, tgtS = V['stop_l'], V['tgt_l'], V['stop_s'], V['tgt_s']
    n = len(c)
    rate, fee = ref_rates(S['pair'], X['cost'])
    apxInv = bool(X.get('inv', False))
    apxTrailOn = bool(X['trailOn'])
    apxTrailAct = float(X.get('trailAct', 1.0))
    apxTrailOff = float(X.get('trailOff', 0.5))
    apxUseTarget = bool(X['useTarget'])
    apxBlkClose = bool(X['blkClose'])
    mag = X['path'] == 'mag'
    if mag and sub is None:
        raise ValueError('mag needs sub')

    trades = []
    closed = 0.0
    tr = None                       # the open trade (dict) or None
    market = []                     # market orders placed at the last close, in placement order
    exit_orders = {}                # strategy.exit orders by exit id
    apxTrPtsL = apxTrOfsL = apxTrPtsS = apxTrOfsS = NAN       # var float ... = na
    eq_curve = [0.0] * n
    pos_curve = [0] * n

    def close_trade(i, px, kind):
        nonlocal tr, closed
        xc = rate * px * tr['qty'] + fee * tr['qty']
        pnl = tr['dir'] * (px - tr['epx']) * tr['qty'] - tr['ecost'] - xc
        tr.update(exit_bar=i, exit_px=px, exit_kind=kind, exit_cost=xc, pnl=pnl)
        trades.append(tr)
        closed += pnl
        for xid in [k for k, v in exit_orders.items() if v['from_entry'] == tr['id']]:
            del exit_orders[xid]     # an exit whose entry trade has closed is cancelled
        tr = None

    def exit_of(trd):
        for xid, v in exit_orders.items():
            if v['from_entry'] == trd['id']:
                return v
        return None

    for i in range(n):
        # 1) market orders placed at the previous close fill at this open, in placement order
        for od in market:
            if od['type'] == 'close':
                if tr is not None and tr['id'] == od['id']:
                    close_trade(i, o[i], 'blocked_close')
            else:
                if tr is not None and tr['dir'] == od['direction']:
                    _cnt('entry_ignored_same_side')
                    continue                                   # pyramiding 0
                if tr is not None:
                    close_trade(i, o[i], 'reverse')
                tr = dict(id=od['id'], dir=od['direction'], entry_bar=i, signal_bar=od['bar'], epx=o[i],
                          qty=od['qty'], ecost=rate * o[i] * od['qty'] + fee * od['qty'], eq_before=INIT + closed,
                          signal_kind=od['signal_kind'], armed=False, best=NAN, has_trail=False,
                          act_px=NAN, ofs=NAN, pts_ticks=NAN, ofs_ticks=NAN)
                ex = exit_of(tr)
                if ex is None:
                    raise RuntimeError('a trade without its strategy.exit order')
                if not math.isnan(ex['trail_points']):
                    # activation = entry fill price +/- trail_points x mintick, on the trade's own side
                    tr.update(has_trail=True, act_px=o[i] + tr['dir'] * ex['trail_points'] * TICK,
                              ofs=ex['trail_offset'] * TICK, pts_ticks=ex['trail_points'],
                              ofs_ticks=ex['trail_offset'])
        market = []
        # 2) the open trade's exit order along this bar's path
        if tr is not None:
            ex = exit_of(tr)
            if tr['has_trail'] and (ex['trail_points'] != tr['pts_ticks'] or ex['trail_offset'] != tr['ofs_ticks']):
                raise RuntimeError('trail distances changed inside a trade')
            key = (tr['entry_bar'], tr['dir'])
            log = trace_trades.get(key) if trace_trades is not None else None
            if log is not None:
                log.append(f'  bar {i} t_open {V["t_open"][i]} O {o[i]} H {h[i]} L {l[i]} C {c[i]} '
                           f'| stop {ex["stop"]} limit {ex["limit"]} armed={tr["armed"]} best={tr["best"]}')
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
                tr['exit_order'] = dict(ex)
                if log is not None:
                    log.append(f'    -> EXIT {kind} at {px} on sub-bar {k}')
                close_trade(i, px, kind)
        # bar-close equity / position (for max drawdown, exposure, the half split)
        eq = INIT + closed
        if tr is not None:
            eq += tr['dir'] * (c[i] - tr['epx']) * tr['qty'] - tr['ecost']
        eq_curve[i] = eq
        pos_curve[i] = 0 if tr is None else tr['dir']
        if i == n - 1:
            break                    # orders placed on the last bar never fill
        # 3) the script at the close of bar i  (Pine at HEAD, line by line)
        position_size = 0 if tr is None else tr['dir']          # sign of strategy.position_size
        close = c[i]
        bullResonance, bearResonance = bullRes[i], bearRes[i]
        if MUT['gate_order_side'] and apxInv:      # MUTATION: gate by the ORDER's side
            apxGoLong = bullResonance and fgfSellOk[i]
            apxGoShort = bearResonance and fgfBuyOk[i]
            apxBlkLong = bullResonance and not fgfSellOk[i]
            apxBlkShort = bearResonance and not fgfBuyOk[i]
        else:
            apxGoLong = bullResonance and fgfBuyOk[i]
            apxGoShort = bearResonance and fgfSellOk[i]
            apxBlkLong = bullResonance and not fgfBuyOk[i]
            apxBlkShort = bearResonance and not fgfSellOk[i]
        apxPosN = -position_size if apxInv else position_size
        apxIdBuy = "Apex Short" if apxInv else "Apex Long"
        apxIdSell = "Apex Long" if apxInv else "Apex Short"
        apxExBuy = "Exit Short" if apxInv else "Exit Long"
        apxExSell = "Exit Long" if apxInv else "Exit Short"
        dirBuy = SHORT if apxInv else LONG                      # apxInv ? strategy.short : strategy.long
        dirSell = LONG if apxInv else SHORT
        if MUT['same_side'] and apxInv:            # MUTATION: orders not flipped at all
            apxIdBuy, apxIdSell, apxExBuy, apxExSell = "Apex Long", "Apex Short", "Exit Long", "Exit Short"
            dirBuy, dirSell = LONG, SHORT
            apxPosN = position_size
        posBlk = position_size if (MUT['blk_real_pos'] and apxInv) else apxPosN
        posRs = position_size if (MUT['resend_real_pos'] and apxInv) else apxPosN
        posPt = position_size if (MUT['pts_real_pos'] and apxInv) else apxPosN

        if apxBlkClose and apxBlkShort and posBlk > 0:
            market.append(dict(type='close', id=apxIdBuy, bar=i))
            if events is not None:
                events.append((i, 'close', apxIdBuy))
        if apxBlkClose and apxBlkLong and posBlk < 0:
            market.append(dict(type='close', id=apxIdSell, bar=i))
            if events is not None:
                events.append((i, 'close', apxIdSell))

        if apxGoLong:
            market.append(dict(type='entry', id=apxIdBuy, direction=dirBuy, qty=0.01 * eq / close, bar=i,
                               signal_kind='BUY'))
            if posPt <= 0:
                apxTrPtsL = max(close * apxTrailAct / 100.0 / TICK, 0.0) if apxTrailOn else NAN
                apxTrOfsL = max(close * apxTrailOff / 100.0 / TICK, 1.0) if apxTrailOn else NAN
        if apxGoLong or (bullResonance and posRs > 0):
            stopPrice = stopL[i]
            targetPrice = tgtL[i]
            apxStopBuy = 2.0 * close - stopPrice if apxInv else stopPrice
            apxTgtBuy = 2.0 * close - targetPrice if apxInv else targetPrice
            if apxInv and MUT['no_mirror']:
                apxStopBuy, apxTgtBuy = stopPrice, targetPrice
            if apxInv and MUT['mirror_alt']:       # algebraically equal, another float expression
                apxStopBuy, apxTgtBuy = close - (stopPrice - close), close - (targetPrice - close)
            if apxInv and MUT['mirror_fill']:      # mirrored about the NEXT open instead of the close
                apxStopBuy, apxTgtBuy = 2.0 * o[i + 1] - stopPrice, 2.0 * o[i + 1] - targetPrice
            if position_size != 0 and tr['id'] == apxIdBuy:
                _cnt('resend_buy_kind')
            pts, ofs = (apxTrPtsS, apxTrOfsS) if (MUT['trail_swapped_kind'] and apxInv) else (apxTrPtsL, apxTrOfsL)
            exit_orders[apxExBuy] = dict(from_entry=apxIdBuy, stop=apxStopBuy,
                                         limit=NAN if (apxTrailOn and not apxUseTarget) else apxTgtBuy,
                                         trail_points=pts, trail_offset=ofs, bar=i)
            if events is not None:
                events.append((i, 'exit', apxExBuy, apxIdBuy, apxStopBuy, exit_orders[apxExBuy]['limit']))

        if apxGoShort:
            market.append(dict(type='entry', id=apxIdSell, direction=dirSell, qty=0.01 * eq / close, bar=i,
                               signal_kind='SELL'))
            if posPt >= 0:
                apxTrPtsS = max(close * apxTrailAct / 100.0 / TICK, 0.0) if apxTrailOn else NAN
                apxTrOfsS = max(close * apxTrailOff / 100.0 / TICK, 1.0) if apxTrailOn else NAN
        if apxGoShort or (bearResonance and posRs < 0):
            stopPrice = stopS[i]
            targetPrice = tgtS[i]
            apxStopSell = 2.0 * close - stopPrice if apxInv else stopPrice
            apxTgtSell = 2.0 * close - targetPrice if apxInv else targetPrice
            if apxInv and MUT['no_mirror']:
                apxStopSell, apxTgtSell = stopPrice, targetPrice
            if apxInv and MUT['mirror_alt']:
                apxStopSell, apxTgtSell = close - (stopPrice - close), close - (targetPrice - close)
            if apxInv and MUT['mirror_fill']:
                apxStopSell, apxTgtSell = 2.0 * o[i + 1] - stopPrice, 2.0 * o[i + 1] - targetPrice
            if position_size != 0 and tr['id'] == apxIdSell:
                _cnt('resend_sell_kind')
            pts, ofs = (apxTrPtsL, apxTrOfsL) if (MUT['trail_swapped_kind'] and apxInv) else (apxTrPtsS, apxTrOfsS)
            exit_orders[apxExSell] = dict(from_entry=apxIdSell, stop=apxStopSell,
                                          limit=NAN if (apxTrailOn and not apxUseTarget) else apxTgtSell,
                                          trail_points=pts, trail_offset=ofs, bar=i)
            if events is not None:
                events.append((i, 'exit', apxExSell, apxIdSell, apxStopSell, exit_orders[apxExSell]['limit']))
    if tr is not None:
        close_trade(n - 1, c[n - 1], 'end')
    return trades, dict(eq=eq_curve, pos=pos_curve, final=INIT + closed)


# ---------------------------------------------------------------------------
# comparison with the replica
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
    """Returns (ok, message, worst). Sides, bars, times, kinds and prices must be exactly equal;
    quantities / P&L / costs / equity to 1e-9 relative."""
    if len(R) != len(E):
        k = min(len(R), len(E))
        first = None
        for j in range(k):
            if not (R['entry_bar'].iat[j] == E['entry_bar'].iat[j] and R['exit_bar'].iat[j] == E['exit_bar'].iat[j]
                    and R['exit_kind'].iat[j] == E['exit_kind'].iat[j] and R['dir'].iat[j] == E['dir'].iat[j]):
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
        worst[col] = float(np.abs(a - b).max())
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


def ref_summary(S, trades, curve):
    """Every summary field a trade list and the bar-close equity curve determine, recomputed
    here (SPEC_AH.md definitions)."""
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
    wins = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    losses = -sum(t['pnl'] for t in trades if t['pnl'] < 0)
    peak = INIT
    mxdd = 0.0
    for e in curve['eq'][:-1] + [final]:       # the last point is the equity after the 'end' close
        if e > peak:
            peak = e
        dd = (peak - e) / peak
        if dd > mxdd:
            mxdd = dd
    # half split: bar-close equity of the last bar with t_close <= mid
    im = -1
    for k, tcl in enumerate(V['t_close']):
        if tcl <= mid:
            im = k
        else:
            break
    eq_mid = curve['eq'][im] if im >= 0 else INIT
    if im == len(V['t_close']) - 1:
        eq_mid = final
    return dict(trades=len(trades), net_pct=100.0 * (final - INIT) / INIT, final_equity=final,
                h1r_pct=100.0 * (p1 - 1.0), h2r_pct=100.0 * (p2 - 1.0), h1_trades=len(first),
                h2_trades=len(second), kinds=kinds,
                long=sum(1 for t in trades if t['dir'] > 0), short=sum(1 for t in trades if t['dir'] < 0),
                pf=(wins / losses) if losses > 0 else (float('inf') if wins > 0 else NAN),
                win_pct=(100.0 * sum(1 for t in trades if t['pnl'] > 0) / len(trades)) if trades else NAN,
                max_dd_pct=100.0 * mxdd,
                exposure=sum(1 for p in curve['pos'] if p != 0) / len(curve['pos']),
                half1_pct=100.0 * (eq_mid - INIT) / INIT, half2_pct=100.0 * (final - eq_mid) / INIT,
                costs=sum(t['ecost'] + t['exit_cost'] for t in trades),
                raw_long=sum(1 for x in V['sig_l'] if x), raw_short=sum(1 for x in V['sig_s'] if x),
                blocked_long=sum(1 for a, b in zip(V['sig_l'], V['buy_ok']) if a and not b),
                blocked_short=sum(1 for a, b in zip(V['sig_s'], V['sell_ok']) if a and not b),
                avg_bars_held=(sum(t['exit_bar'] - t['entry_bar'] for t in trades) / len(trades)) if trades else NAN)


SUM_INT = ('trades', 'h1_trades', 'h2_trades', 'long', 'short', 'raw_long', 'raw_short', 'blocked_long',
           'blocked_short')
SUM_FLT = ('net_pct', 'final_equity', 'h1r_pct', 'h2r_pct', 'avg_bars_held', 'pf', 'win_pct', 'max_dd_pct',
           'exposure', 'half1_pct', 'half2_pct', 'costs')


def compare_summary(rs, es, skip=()):
    bad = []
    for k in SUM_INT:
        if rs[k] != es[k]:
            bad.append(k)
    for k in SUM_FLT:
        if k in skip:
            continue
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


def prep(cell, fgf_on, rev=False, full=False, rev_stops='literal'):
    pair, tf, s, e = CELLS[cell]
    key = (cell, fgf_on, rev, full, rev_stops)
    if key not in _S:
        p = {'fgfOn': fgf_on, 'reverse': rev, 'reverseStops': rev_stops}
        if s is not None and not full:
            p['start'], p['end'] = s, e
        _S[key] = apex.prepare(pair, tf, p)
    return _S[key]


def eng_run(S, X, inv_key='inv'):
    ex = {kk: X[kk] for kk in ('trailOn', 'trailAct', 'trailOff', 'useTarget', 'blkClose', 'cost', 'path')}
    if inv_key is not None:
        ex[inv_key] = bool(X.get('inv', False))
    out, es = apex.simulate(S, ex)
    return apex.trades_frame(S, out), es


def regress(cells):
    """Option off, trail off, cost tv, every saved variant: the reference equals out/apex_trades."""
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
            X = dict(inv=False, trailOn=False, trailAct=1.0, trailOff=0.5, useTarget=True, blkClose=blk, cost='tv',
                     path='tv')
            R = ref_frame(S, ref_run(S, X)[0])
            ok, msg, worst = compare_frames(R, saved, cols_f=('qty', 'pnl', 'entry_cost', 'exit_cost'))
            tot += 1
            rows += len(saved)
            bad += not ok
            print(f'regress {cell:8s} {v:9s} trades {len(saved):6d}: {"OK" if ok else "FAIL"} {msg}', flush=True)
    print(f'REGRESS {"PASS" if bad == 0 else "FAIL"}: {tot - bad}/{tot} runs, {rows} saved rows')
    return bad == 0


DEFAULT_EXIT = dict(trailOn=False, trailAct=1.0, trailOff=0.5, useTarget=True, blkClose=True)


def settings(cell, nset, seed):
    """The default exits (x every cost) + nset random other exit settings."""
    rng = random.Random(seed * 1000 + sum(map(ord, cell)))
    out = [dict(DEFAULT_EXIT, cost=cst, rev=False, tag='default') for cst in COSTS]
    out.append(dict(DEFAULT_EXIT, blkClose=False, cost='tv', rev=False, tag='default, blkClose off'))
    out.append(dict(DEFAULT_EXIT, useTarget=False, cost='ours', rev=False, tag='trail off, useTarget off (no effect)'))
    for j in range(nset):
        r = rng.random()
        if r < 0.55:      # on the sweep grid
            g = dict(trailOn=True, trailAct=rng.choice(ACTS), trailOff=rng.choice(OFFS), useTarget=rng.random() < 0.5)
        elif r < 0.9:     # off the grid / boundaries (offset 0 = the 1-tick floor, activation 0)
            g = dict(trailOn=True, trailAct=rng.choice((0.0, rng.uniform(0, 0.3), rng.uniform(0, 5))),
                     trailOff=rng.choice((0.0, 1e-4, rng.uniform(0, 0.05), rng.uniform(0, 5))),
                     useTarget=rng.random() < 0.5)
        else:
            g = dict(trailOn=False, trailAct=rng.uniform(0, 5), trailOff=rng.uniform(0, 5), useTarget=rng.random() < 0.5)
        g.update(blkClose=rng.random() < 0.75, cost=rng.choice(COSTS), rev=rng.random() < 0.15, tag=f'random {j}')
        out.append(g)
    return out


def compare(cell, nset=14, seed=1):
    pair = CELLS[cell][0]
    t0 = time.time()
    sub = build_sub(pair, prep(cell, False))
    print(f'{cell}: sub-bars built in {time.time() - t0:.1f}s ({len(sub["o"])} 1m rows)', flush=True)
    st = {False: dict(runs=0, fail=0, trades=0, kinds={}), True: dict(runs=0, fail=0, trades=0, kinds={})}
    t_ref = t_eng = 0.0
    COUNT.clear()
    diff_on_off = 0
    inv_keys = ('inv', 'apxInv')
    nk = 0
    for g in settings(cell, nset, seed):
        for fon in (False, True):
            S = prep(cell, fon, g['rev'])
            for path in ('tv', 'mag'):
                frames = {}
                for inv in (True, False):
                    X = dict(g, path=path, inv=inv)
                    t1 = time.time()
                    rt, curve = ref_run(S, X, sub if path == 'mag' else None)
                    t2 = time.time()
                    if inv:
                        key = inv_keys[nk % 2]        # both spellings of the parameter
                        nk += 1
                    else:
                        key = (None, 'inv', 'apxInv')[nk % 3]   # absent / explicit False
                    E, es = eng_run(S, X, key)
                    t3 = time.time()
                    t_ref += t2 - t1
                    t_eng += t3 - t2
                    R = ref_frame(S, rt)
                    frames[inv] = R
                    ok, msg, worst = compare_frames(R, E)
                    sb = compare_summary(ref_summary(S, rt, curve), es)
                    s = st[inv]
                    s['runs'] += 1
                    s['trades'] += len(R)
                    for kk, vv in R['exit_kind'].value_counts().items():
                        s['kinds'][kk] = s['kinds'].get(kk, 0) + int(vv)
                    if not ok or sb:
                        s['fail'] += 1
                        print(f'  FAIL {cell} inv={inv} [{g["tag"]}] {g} path={path} fgf={fon}: {msg} '
                              f'summary_bad={sb}', flush=True)
                        if not ok and len(R) == len(E):
                            show_diff(R, E)
                a, b = frames[True], frames[False]
                diff_on_off += not (len(a) == len(b) and (a['dir'].to_numpy() == b['dir'].to_numpy()).all())
    for inv in (True, False):
        s = st[inv]
        print(f'{cell} option {"ON " if inv else "OFF"}: {s["runs"]} runs, {s["runs"] - s["fail"]} equal, '
              f'{s["trades"]} trades, kinds {dict(sorted(s["kinds"].items()))}', flush=True)
    print(f'{cell}: option on differs from option off in {diff_on_off} of {st[True]["runs"]} runs; '
          f'ref {t_ref:.1f}s engine {t_eng:.1f}s; reference events {dict(sorted(COUNT.items()))}')
    fail = st[True]['fail'] + st[False]['fail']
    print(f'COMPARE {cell} {"PASS" if fail == 0 else "FAIL"}')
    return fail


MUTATIONS = {
    'orders not flipped (same side)': 'same_side',
    'bracket not mirrored': 'no_mirror',
    'bracket mirrored about the fill open': 'mirror_fill',
    'mirror as close - (x - close) [same value, info]': 'mirror_alt',
    'blocked close decided on the real position': 'blk_real_pos',
    're-send decided on the real position': 'resend_real_pos',
    'trail ticks fixed on the real position test': 'pts_real_pos',
    'trail ticks of the other signal kind': 'trail_swapped_kind',
    'gate by the order side': 'gate_order_side',
}


def mutate(cells, nset=10, seed=7):
    """For each mutation of the reference's INVERTED script step: the number of option-on runs in
    which it no longer equals the replica (0 would mean the comparison cannot see that rule)."""
    hits = {m: 0 for m in MUTATIONS}
    runs = base_bad = 0
    for cell in cells:
        pair = CELLS[cell][0]
        sub = build_sub(pair, prep(cell, False))
        for g in settings(cell, nset, seed):
            if g['rev']:
                continue
            for fon in (False, True):
                S = prep(cell, fon, False)
                for path in ('tv', 'mag'):
                    X = dict(g, path=path, inv=True)
                    E, _ = eng_run(S, X)
                    sb = sub if path == 'mag' else None
                    ok, msg, _ = compare_frames(ref_frame(S, ref_run(S, X, sb)[0]), E)
                    base_bad += not ok
                    runs += 1
                    for name, flag in MUTATIONS.items():
                        MUT[flag] = True
                        try:
                            Rm = ref_frame(S, ref_run(S, X, sb)[0])
                            okm = compare_frames(Rm, E)[0]
                        except RuntimeError:      # the mutant breaks an invariant of the reference
                            okm = False
                        finally:
                            MUT[flag] = False
                        hits[name] += not okm
    print(f'MUTATE cells {cells}: {runs} option-on runs, unmutated reference differs in {base_bad}')
    for name in MUTATIONS:
        print(f'  mutation {name:44s}: differs from the replica in {hits[name]:4d} / {runs} runs')
    # the algebraically equal mirror expression is informational (see mode `bits`): not a rule
    good = base_bad == 0 and all(v > 0 for k, v in hits.items() if MUTATIONS[k] != 'mirror_alt')
    print('MUTATE ' + ('PASS: every wrong rule is seen' if good else 'FAIL'))
    return good


def checkjson(pair, tfs):
    """Recompute every entry of out/inv_apex_<PAIR>_<TF>.json (run_inv_apex.py: 16 runs + 16
    reversed-label reference runs, full window, default inputs) with the reference broker."""
    import json
    all_ok = True
    for tf in tfs:
        f = os.path.join(W, 'out', f'inv_apex_{pair}_{tf}.json')
        J = json.load(open(f))
        cellname = f'_json_{pair}_{tf}'
        CELLS[cellname] = (pair, tf, None, None)
        sub = None
        bad = n = 0
        t0 = time.time()
        for sect in ('runs', 'reference'):
            for key, js in J[sect].items():
                dname, fname, path, cname = key.split('/')
                fon = {'off': False, 'on': True}[fname]
                cost = {'script': 'tv', 'ours': 'ours'}[cname]
                rev, rstops, inv = False, 'literal', False
                if dname == 'inverted':
                    inv = True
                elif dname == 'rev_literal':
                    rev = True
                elif dname == 'rev_mirror':
                    rev, rstops = True, 'mirror'
                elif dname != 'normal':
                    raise ValueError(dname)
                S = prep(cellname, fon, rev, True, rstops)
                if path == 'mag' and sub is None:
                    sub = build_sub(pair, S)
                X = dict(DEFAULT_EXIT, cost=cost, path=path, inv=inv)
                rt, curve = ref_run(S, X, sub if path == 'mag' else None)
                rs = ref_summary(S, rt, curve)
                es = dict(js)
                for k in SUM_FLT:                       # the JSON writes nan as null, inf as 'inf'
                    if es[k] is None:
                        es[k] = NAN
                    elif es[k] == 'inf':
                        es[k] = float('inf')
                sb = compare_summary(rs, es)
                lab = []
                if (js['direction'], js['filter'], js['path'], js['cost']) != (dname, fname, path, cname):
                    lab.append('labels')
                if js['params']['fgfOn'] != fon or js['params']['cost'] != cost or js['exit_params']['path'] != path \
                        or bool(js['inv']) != inv or js['params']['reverse'] != rev \
                        or (rev and js['params']['reverseStops'] != rstops) or js['exit_params']['trailOn'] \
                        or not js['params']['blkClose'] or js['start'] != WIN[pair][0] or js['end'] != WIN[pair][1]:
                    lab.append('params')
                n += 1
                if sb or lab:
                    bad += 1
                    print(f'  FAIL {pair} {tf} {sect} {key}: {sb + lab}')
        print(f'checkjson {pair} {tf}: {n - bad}/{n} entries of {os.path.basename(f)} equal the reference '
              f'({time.time() - t0:.0f}s)', flush=True)
        all_ok = all_ok and bad == 0
    print('CHECKJSON ' + ('PASS' if all_ok else 'FAIL'))
    return all_ok


def bits(cells):
    """The two algebraically equal mirror expressions: where 2.0*close - x (the Pine) and
    close - (x - close) give different doubles for a level that a trade exits at, the replica
    must have the Pine's."""
    tot = diff = bad = runs = 0
    for cell in cells:
        for fon in (False, True):
            S = prep(cell, fon)
            for g in (dict(DEFAULT_EXIT), dict(DEFAULT_EXIT, blkClose=False),
                      dict(trailOn=True, trailAct=2.0, trailOff=1.0, useTarget=True, blkClose=True)):
                X = dict(g, cost='tv', path='tv', inv=True)
                R = ref_frame(S, ref_run(S, X)[0])
                MUT['mirror_alt'] = True
                try:
                    A = ref_frame(S, ref_run(S, X)[0])
                finally:
                    MUT['mirror_alt'] = False
                E, _ = eng_run(S, X)
                runs += 1
                tot += len(R)
                ok, msg, _ = compare_frames(R, E)
                if not ok:
                    bad += 1
                    print(f'  FAIL {cell} fgf={fon} {g}: {msg}')
                if len(A) == len(R):
                    m = A['exit_px'].to_numpy() != R['exit_px'].to_numpy()
                    for j in np.nonzero(m)[0]:
                        diff += 1
                        print(f'  {cell} fgf={fon} trail={g["trailOn"]} trade {j} {R["exit_kind"].iat[j]}: Pine expression '
                              f'{R["exit_px"].iat[j]!r}, other expression {A["exit_px"].iat[j]!r}, replica '
                              f'{E["exit_px"].iat[j]!r} -> {"Pine" if E["exit_px"].iat[j] == R["exit_px"].iat[j] else "NOT the Pine"}')
                else:
                    print(f'  {cell} fgf={fon}: the other expression changes the trade count ({len(A)} vs {len(R)})')
                    diff += 1
    print(f'BITS: {runs} option-on runs, {tot} trades; {diff} exits where the two expressions differ in the last bits; '
          f'replica != reference in {bad} runs')
    print('BITS ' + ('PASS' if bad == 0 else 'FAIL'))
    return bad == 0


def api():
    """Parameter plumbing of the replica: `inv` / `apxInv`, as a prepare() default and as a
    simulate() override, and apex.run(); chart "1": 'mag' == 'tv' with the option on."""
    ok_all = True

    def same(a, b):
        return len(a) == len(b) and all(np.array_equal(a[c].to_numpy(), b[c].to_numpy()) for c in a.columns)

    for pair, tf in (('BTC', '240'), ('XAU', '120')):
        base = {'fgfOn': True}
        S0 = apex.prepare(pair, tf, base)
        Eon = apex.trades_frame(S0, apex.simulate(S0, {'inv': True})[0])
        Eoff = apex.trades_frame(S0, apex.simulate(S0, None)[0])
        checks = []
        checks.append(('simulate apxInv=True == inv=True', same(Eon, apex.trades_frame(S0, apex.simulate(S0, {'apxInv': True})[0]))))
        checks.append(('simulate inv=False == default', same(Eoff, apex.trades_frame(S0, apex.simulate(S0, {'inv': False})[0]))))
        for nm in ('apxInv', 'inv'):
            S1 = apex.prepare(pair, tf, dict(base, **{nm: True}))
            checks.append((f'prepare {nm}=True -> simulate default inverted',
                           same(Eon, apex.trades_frame(S1, apex.simulate(S1, None)[0]))))
            checks.append((f'prepare {nm}=True, simulate inv=False -> normal',
                           same(Eoff, apex.trades_frame(S1, apex.simulate(S1, {'inv': False})[0]))))
            tr, sm = apex.run(pair, tf, dict(base, **{nm: True}))
            checks.append((f'run {nm}=True == simulate inv=True', same(Eon, tr) and sm['inv'] is True))
        tr, sm = apex.run(pair, tf, base)
        checks.append(('run default == normal, summary inv False', same(Eoff, tr) and sm['inv'] is False))
        checks.append(('inverted differs from normal', not same(Eon, Eoff)))
        for name, ok in checks:
            print(f'  api {pair} {tf}: {"ok  " if ok else "FAIL"} {name}')
            ok_all = ok_all and ok
    # chart "1": the reference on both paths, the replica on both paths, option on
    for cell in ('BTC_1', 'XAU_1'):
        pair = CELLS[cell][0]
        for fon in (False, True):
            S = prep(cell, fon)
            sub = build_sub(pair, S)
            for g in (dict(DEFAULT_EXIT), dict(trailOn=True, trailAct=0.1, trailOff=0.05, useTarget=False, blkClose=True)):
                fr = {}
                for path in ('tv', 'mag'):
                    X = dict(g, cost='ours', path=path, inv=True)
                    R = ref_frame(S, ref_run(S, X, sub if path == 'mag' else None)[0])
                    E, _ = eng_run(S, X)
                    ok, msg, _ = compare_frames(R, E)
                    fr[path] = E
                    if not ok:
                        print(f'  FAIL {cell} fgf={fon} {path}: {msg}')
                        ok_all = False
                eq = same(fr['tv'], fr['mag'])
                print(f'  chart 1 {cell} fgf={fon} trail={g["trailOn"]}: {len(fr["tv"])} trades, replica == reference on tv and mag, '
                      f'mag {"==" if eq else "!="} tv')
                ok_all = ok_all and eq
    # header: "Allow buys off blocks the BUY signals, i.e. the SELL orders placed when inverted
    # (only BUY entries are left); Allow sells off the reverse."
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '30')):
        for pname, want in (('fgfAllowBuy', 1), ('fgfAllowSell', -1)):
            S = apex.prepare(pair, tf, {'fgfOn': True, pname: False})
            for g in (dict(DEFAULT_EXIT), dict(trailOn=True, trailAct=0.3, trailOff=0.2, useTarget=True, blkClose=False)):
                X = dict(g, cost='tv', path='tv', inv=True)
                rt, curve = ref_run(S, X)
                E, es = eng_run(S, X)
                ok, msg, _ = compare_frames(ref_frame(S, rt), E)
                sides = set(t['dir'] for t in rt)
                good = ok and sides == {want} and not compare_summary(ref_summary(S, rt, curve), es) \
                    and not any(t['exit_kind'] == 'reverse' for t in rt)
                print(f'  {pair} {tf} {pname} off, inverted, trail={g["trailOn"]} blkClose={g["blkClose"]}: {len(rt)} trades, '
                      f'real sides {sorted(sides)} (only {"BUY" if want > 0 else "SELL"} orders left), replica == reference: {ok}')
                ok_all = ok_all and good
    print('API ' + ('PASS' if ok_all else 'FAIL'))
    return ok_all


def show_diff(R, E, maxn=3):
    cols = list(ICOLS + PCOLS + ('exit_kind',) + FCOLS)
    shown = 0
    for j in range(len(R)):
        r, e = R.iloc[j], E.iloc[j]
        diff = [c for c in cols if (r[c] != e[c] if c in ICOLS + PCOLS + ('exit_kind',)
                                     else abs(r[c] - e[c]) > 1e-9 * max(1, abs(e[c])))]
        if diff:
            print(f'    trade {j}: ' + '; '.join(f'{c} ref={r[c]!r} eng={e[c]!r}' for c in diff))
            shown += 1
            if shown >= maxn:
                break


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'regress':
        cells = sys.argv[2:] or ['BTC_60', 'XAU_60', 'BTC_15', 'XAU_240']
        sys.exit(0 if regress(cells) else 1)
    elif mode == 'compare':
        cell = sys.argv[2]
        nset = int(sys.argv[3]) if len(sys.argv) > 3 else 14
        seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        sys.exit(0 if compare(cell, nset, seed) == 0 else 1)
    elif mode == 'mutate':
        sys.exit(0 if mutate(sys.argv[2:] or ['BTC_60', 'XAU_60', 'BTC_15', 'XAU_240']) else 1)
    elif mode == 'checkjson':
        sys.exit(0 if checkjson(sys.argv[2], sys.argv[3:]) else 1)
    elif mode == 'bits':
        sys.exit(0 if bits(sys.argv[2:] or [c for c in CELLS if not c.endswith('_1')]) else 1)
    elif mode == 'api':
        sys.exit(0 if api() else 1)
    elif mode == 'trace':
        import verify_inv_apex_trace  # noqa
        sys.exit(0 if verify_inv_apex_trace.main() else 1)
    else:
        raise SystemExit(__doc__)
