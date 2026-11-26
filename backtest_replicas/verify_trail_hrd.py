"""Independent verifier of hrd.py's trailing take profit and 'mag' (Bar Magnifier) path.

A plain pure-Python broker for HRD v1.03 + FGF, written from the Pine
(/home/user/master/HRD_Full_Divergence_Strategy_v1_03_FGF.pine), SPEC_AH.md and SWEEP_AH_SPEC.md
WITHOUT reading hrd.py's new kernel (_walk / _simulate / sub_bars). From hrd.py it reuses only
prepare()'s per-bar inputs: the window, chart OHLC / times, longSignal / shortSignal (after
Reverse Trading) and the filter permissions buyOk / sellOk. Everything else (script logic at the
close: entryBarIndex time exit, gate, blocked close, entries with SL / TP / trail, hybrid exit,
sizing on strategy.equity; broker: placement-order fills at the next open, reversals, intrabar
exit order with the trailing stop along the tv path or the 1-minute sub-bars, costs) is here.

The 1-minute sub-bars are rebuilt here from data/<PAIR>_1.parquet (t_open in [t_open, t_close)
of the chart bar).

Usage:
  python3 -I verify_trail_hrd.py check DATASET [N] [SEED] [extra]   DATASET in BTC60, XAU60, BTC15, XAU240
                                    (extra: also random blkClose / direction / SL % / hybrid on-off)
  python3 -I verify_trail_hrd.py mutate [DATASET ...]       sensitivity: each mutation must be caught
  python3 -I verify_trail_hrd.py trace                       hand-trace 5 trail exits
"""
import os
import sys
import time
import random

import numpy as np
import pyarrow.parquet as pq

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import hrd  # noqa: E402  (inputs only: prepare(); the engine under test: simulate / trades_frame)

TICK = 0.01
INIT = 1_000_000.0
# per fill, per unit: (fixed $, fraction of fill value), written from SPEC_AH.md / SWEEP_AH_SPEC.md
REF_COSTS = {
    'tv': {'XAU': (0.0, 0.0), 'BTC': (0.0, 0.0)},
    'ours': {'XAU': (0.15, 0.0), 'BTC': (0.10, 0.0002)},
    'stress': {'XAU': (0.25 + 0.01, 0.0), 'BTC': (0.10 + 0.01, 0.00035)},
}
ACTS = [0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5]
OFFS = [0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5]

# mutation switches (mutate mode only): plausible alternative readings that the comparison
# must detect; empty in the real check
MUT = set()

DATASETS = {
    'BTC60': ('BTC', '60', None, None),
    'XAU60': ('XAU', '60', None, None),
    'BTC15': ('BTC', '15', 1767225600, 1775001600),     # 2026-01-01 .. 2026-04-01 (3 months)
    'XAU240': ('XAU', '240', None, None),
}


# ---------------------------------------------------------------------------------------------
# 1-minute sub-bars, rebuilt independently
# ---------------------------------------------------------------------------------------------
_M1 = {}
_SUB_BASE = {}


def minute_bars(pair):
    if pair not in _M1:
        t = pq.read_table(os.path.join(W, 'data', f'{pair}_1.parquet'),
                          columns=['open', 'high', 'low', 'close', 't_open']).to_pandas()
        _M1[pair] = t
    return _M1[pair]


def build_sub(pair, to, tc):
    """For chart bars with t_open `to`, t_close `tc`: (lo, hi, O, H, L, C) with the sub-bars of
    chart bar j = rows lo[j]..hi[j]-1 of the returned lists (sliced to the window)."""
    m = minute_bars(pair)
    mto = m['t_open'].to_numpy()
    lo = np.searchsorted(mto, to, side='left')
    hi = np.searchsorted(mto, tc, side='left')
    a, b = int(lo[0]), int(hi[-1])
    _SUB_BASE[pair] = (a, mto)
    O = m['open'].to_numpy()[a:b].tolist()
    H = m['high'].to_numpy()[a:b].tolist()
    L = m['low'].to_numpy()[a:b].tolist()
    C = m['close'].to_numpy()[a:b].tolist()
    return (lo - a).tolist(), (hi - a).tolist(), O, H, L, C


def check_sub(Pp, sub):
    lo, hi, O, H, L, C = sub
    o, h, l, c = Pp['o'], Pp['h'], Pp['l'], Pp['c']
    bad = 0
    empty = 0
    for j in range(Pp['n']):
        if hi[j] <= lo[j]:
            empty += 1
            continue
        if (O[lo[j]] != o[j] or C[hi[j] - 1] != c[j] or max(H[lo[j]:hi[j]]) != h[j]
                or min(L[lo[j]:hi[j]]) != l[j]):
            bad += 1
    return empty, bad


# ---------------------------------------------------------------------------------------------
# exit order along one path (open, x1, x2, close), written in price space per side
# ---------------------------------------------------------------------------------------------
class Trade:
    __slots__ = ('d', 'qty', 'epx', 'ek', 'sk', 'sl', 'tp', 'trail', 'A', 'off', 'armed', 'best',
                 'ecost', 'eqb', 'gross', 'xk', 'xpx', 'kind', 'xcost', 'how', 'armed_at')


def _path(o, h, l, c):
    # rule 4: high first when (high - open) < (open - low), else low first
    if (h - o) < (o - l):
        return (o, h, l, c)
    return (o, l, h, c)


def _stop_kind_long(t):
    ts = (t.best - t.off) if (t.trail and t.armed) else None
    if ts is None:
        return t.sl, 'sl'
    if t.sl is None or ts >= t.sl:
        return ts, 'trail'
    return t.sl, 'sl'


def _stop_kind_short(t):
    ts = (t.best + t.off) if (t.trail and t.armed) else None
    if ts is None:
        return t.sl, 'sl'
    if t.sl is None or ts <= t.sl:
        return ts, 'trail'
    return t.sl, 'sl'


def walk(t, pts, log=None, sub_open=False):
    """One path for trade t. Returns (kind, price) or None. Updates the trailing state.
    sub_open: this path starts at a later sub-bar's open (mutation 'no_sub_gap' only)."""
    v0 = pts[0]
    if 'no_sub_gap' in MUT and sub_open:
        # mutation: no gap rule at later sub-bar opens (a jump fills at the stop level)
        stop, sk = (_stop_kind_long(t) if t.d > 0 else _stop_kind_short(t))
        if stop is not None and ((t.d > 0 and v0 <= stop) or (t.d < 0 and v0 >= stop)):
            return sk, stop
    arm_strict = 'arm_strict' in MUT
    if t.d > 0:
        stop, sk = _stop_kind_long(t)
        if stop is not None and v0 <= stop:
            return sk, v0
        if t.tp is not None and v0 >= t.tp:
            return 'tp', v0
        if t.trail:
            if t.armed:
                if v0 > t.best:
                    t.best = v0
            elif v0 >= t.A and not (arm_strict and v0 == t.A):
                t.armed = True
                t.best = v0
                if log is not None:
                    log.append(f'      armed at open {v0}')
        a = v0
        for b in pts[1:]:
            if b > a:
                if t.tp is not None and b >= t.tp:
                    return 'tp', (t.tp if t.tp > a else a)
                if t.trail:
                    if t.armed:
                        if b > t.best:
                            t.best = b
                    elif b >= t.A and not (arm_strict and b == t.A):
                        t.armed = True
                        t.best = b
                        if log is not None:
                            log.append(f'      armed on rise to {b}')
            elif b < a:
                stop, sk = _stop_kind_long(t)
                if stop is not None and b <= stop:
                    return sk, (stop if stop < a else a)
            a = b
        return None
    else:
        stop, sk = _stop_kind_short(t)
        if stop is not None and v0 >= stop:
            return sk, v0
        if t.tp is not None and v0 <= t.tp:
            return 'tp', v0
        if t.trail:
            if t.armed:
                if v0 < t.best:
                    t.best = v0
            elif v0 <= t.A and not (arm_strict and v0 == t.A):
                t.armed = True
                t.best = v0
                if log is not None:
                    log.append(f'      armed at open {v0}')
        a = v0
        for b in pts[1:]:
            if b < a:
                if t.tp is not None and b <= t.tp:
                    return 'tp', (t.tp if t.tp < a else a)
                if t.trail:
                    if t.armed:
                        if b < t.best:
                            t.best = b
                    elif b <= t.A and not (arm_strict and b == t.A):
                        t.armed = True
                        t.best = b
                        if log is not None:
                            log.append(f'      armed on fall to {b}')
            elif b > a:
                stop, sk = _stop_kind_short(t)
                if stop is not None and b >= stop:
                    return sk, (stop if stop > a else a)
            a = b
        return None


# ---------------------------------------------------------------------------------------------
# the strategy + broker
# ---------------------------------------------------------------------------------------------
def ref_broker(Pp, X, sub=None, trace_sel=None, trace_log=None):
    """X: exit / broker params (as hrd.simulate's X). sub: build_sub() output for path 'mag'.
    Returns (list of Trade, final cash, counts dict)."""
    Q = dict(hrd.DEFAULTS)
    Q.update({k: v for k, v in Pp['params'].items() if k in Q})
    for k, v in (X or {}).items():
        Q[hrd._ALIASES.get(k, k)] = v
    o = Pp['o'].tolist()
    h = Pp['h'].tolist()
    l = Pp['l'].tolist()
    c = Pp['c'].tolist()
    LS = Pp['long_sig'].tolist()
    SS = Pp['short_sig'].tolist()
    BOK = Pp['buy_ok'].tolist()
    SOK = Pp['sell_ok'].tolist()
    n = Pp['n']
    c_fix, c_pct = REF_COSTS[Q['cost']][Pp['pair']]
    mag = Q['path'] == 'mag'
    if mag:
        lo, hi, MO, MH, ML, MC = sub
    td = Q['InpTradeDirection']
    long_ok = td in ('Both', 'Buy Only')
    short_ok = td in ('Both', 'Sell Only')
    slp_pct = float(Q['InpSlPct'])
    tp_pct = float(Q['InpTpPct'])
    risk = float(Q['InpRiskPct'])
    fixq = float(Q['InpFixedQty'])
    nexit = int(Q['InpExitCandles'])
    hyb = bool(Q['useHybridExit'])
    sens = float(Q['hybridSensitivity'])
    min_dec = int(Q['minDecayUpdates'])
    step = float(Q['trailStepMult'])
    min_act = int(Q['minActivationPts'])
    tr_on = bool(Q['trailOn'])
    tr_act = float(Q['trailAct'])
    tr_off = float(Q['trailOff'])
    blk = bool(Q['blkClose'])

    def cost(px, q):
        return q * (c_fix + c_pct * px)

    cash = INIT
    tr = None              # open trade
    trades = []
    pending = []           # orders placed at the previous close, in placement order
    ebi = None             # entryBarIndex
    pos_prev = 0           # strategy.position_size[1] (sign)
    peak = 0.0
    cnt = 0
    raw_l = raw_s = blk_l = blk_s = 0

    def close_trade(t, j, px, kind):
        nonlocal cash
        t.xk = j
        t.xpx = px
        t.kind = kind
        t.gross = t.d * (px - t.epx) * t.qty
        t.xcost = cost(px, t.qty)
        cash += t.gross - t.xcost
        trades.append(t)

    for i in range(n):
        # 1. market orders from the previous close fill at this open, in placement order
        if pending:
            for od in pending:
                typ = od[0]
                if typ == 'close_all':
                    if tr is not None:
                        close_trade(tr, i, o[i], od[1])
                        tr = None
                elif typ == 'close':
                    if tr is not None and tr.d == od[1]:
                        close_trade(tr, i, o[i], 'blocked_close')
                        tr = None
                else:  # entry
                    _, d, q, slv, tpv, pts, ofs, sk = od
                    if tr is not None and tr.d == d:
                        continue                      # pyramiding 0
                    if tr is not None:
                        close_trade(tr, i, o[i], 'reverse')
                        tr = None
                    t = Trade()
                    t.d, t.qty, t.epx, t.ek, t.sk, t.sl, t.tp = d, q, o[i], i, sk, slv, tpv
                    t.eqb = cash
                    t.how = None
                    t.ecost = cost(o[i], q)
                    cash -= t.ecost
                    t.trail = pts is not None
                    if t.trail:
                        t.A = t.epx + d * pts * TICK
                        t.off = ofs * TICK
                        if 'A_from_signal' in MUT:
                            t.A = c[sk] + d * pts * TICK
                        if 'off_from_fill' in MUT:
                            t.off = max(t.epx * tr_off / 100.0 / TICK, 1.0) * TICK
                        t.armed = pts == 0.0
                        t.best = t.epx
                    else:
                        t.A = t.off = t.best = None
                        t.armed = False
                    tr = t
            pending = []
        # 2. the open trade's exit order along this bar (from the open; on the fill bar the fill
        #    is at the open, so the same path is 'the rest of the bar')
        if tr is not None:
            log = None
            if trace_sel is not None and tr.ek == trace_sel[0] and tr.d == trace_sel[1]:
                log = trace_log
                log.append(f'  bar {i + Pp["w0"]} (t_open {int(Pp["t_open"][i])}): O {o[i]} H {h[i]} L {l[i]} '
                           f'C {c[i]} | before: armed {tr.armed} best {tr.best}'
                           + (' [fill bar]' if i == tr.ek else ''))
            res = None
            saved_trail = tr.trail
            if 'trail_next_bar' in MUT and i == tr.ek:
                tr.trail = False            # mutation: the trail starts on the bar after the fill
            if 'mag_tv' in MUT:
                mag_now = False
            else:
                mag_now = mag
            if mag_now:
                for k in range(lo[i], hi[i]):
                    if 'mag_chart_dir' in MUT:
                        hf = (h[i] - o[i]) < (o[i] - l[i])
                        pts = (MO[k], MH[k], ML[k], MC[k]) if hf else (MO[k], ML[k], MH[k], MC[k])
                    else:
                        pts = _path(MO[k], MH[k], ML[k], MC[k])
                    if log is not None:
                        base, mto = _SUB_BASE[Pp['pair']]
                        log.append(f'    1m row {base + k} (t_open {int(mto[base + k])}): O {MO[k]} H {MH[k]} '
                                   f'L {ML[k]} C {MC[k]} path {pts}')
                    res = walk(tr, pts, log, sub_open=k > lo[i])
                    if log is not None:
                        log.append(f'      -> armed {tr.armed} best {tr.best} res {res}')
                    if res is not None:
                        break
            else:
                pts = _path(o[i], h[i], l[i], c[i])
                res = walk(tr, pts, log)
                if log is not None:
                    log.append(f'    path {pts} -> armed {tr.armed} best {tr.best} res {res}')
            tr.trail = saved_trail
            if res is not None:
                # coverage tags: 'open' = gap at the chart bar open, 'subopen' = gap at a later
                # sub-bar's open, 'path' = touched along a path
                if res[1] == o[i] and (not mag_now or k == lo[i]):
                    tr.how = 'open'
                elif mag_now and res[1] == MO[k]:
                    tr.how = 'subopen'
                else:
                    tr.how = 'path'
                close_trade(tr, i, res[1], res[0])
                tr = None
        # 3. the script at the close
        pos = 0 if tr is None else tr.d
        orders = []
        if pos != 0 and pos_prev == 0:
            ebi = i
        if pos != 0 and ebi is not None and (i - ebi >= nexit):
            orders.append(('close_all', 'time'))
            ebi = None
        want_l = bool(LS[i]) and long_ok and pos <= 0
        want_s = bool(SS[i]) and short_ok and pos >= 0
        bl = want_l and not BOK[i]
        bs = want_s and not SOK[i]
        raw_l += want_l
        raw_s += want_s
        blk_l += bl
        blk_s += bs
        if blk and bl and pos < 0:
            orders.append(('close', -1))
        if blk and bs and pos > 0:
            orders.append(('close', 1))
        open_pl = 0.0
        if pos != 0:
            open_pl = tr.d * (c[i] - tr.epx) * tr.qty
        equity = cash + open_pl
        for d, go in ((1, want_l and BOK[i]), (-1, want_s and SOK[i])):
            if not go:
                continue
            ep = c[i]
            if slp_pct > 0.0:
                sld = ep * (slp_pct / 100.0)
                slv = ep * (1.0 - slp_pct / 100.0) if d > 0 else ep * (1.0 + slp_pct / 100.0)
            else:
                sld = 0.0
                slv = None
            if tp_pct > 0.0:
                tpv = ep * (1.0 + tp_pct / 100.0) if d > 0 else ep * (1.0 - tp_pct / 100.0)
            else:
                tpv = None
            if slp_pct <= 0.0 or sld <= 0.0:
                q = fixq
            else:
                q = equity * (risk / 100.0) / (sld * 1.0)
                if q < fixq:
                    q = fixq
            if tr_on:
                pts = max(ep * tr_act / 100.0 / TICK, 0.0)
                ofs = max(ep * tr_off / 100.0 / TICK, 1.0)
                if 'round_ticks' in MUT:
                    pts = float(round(pts))
                    ofs = float(round(ofs))
            else:
                pts = ofs = None
            orders.append(('entry', d, q, slv, tpv, pts, ofs, i))
        # hybrid decay-slip exit (globals reset only when flat at a close)
        if pos == 0:
            peak = 0.0
            cnt = 0
        elif hyb:
            cur = (c[i] - tr.epx) if pos > 0 else (tr.epx - c[i])
            act_lv = min_act * TICK
            if cur >= act_lv or peak >= act_lv:
                cnt += 1
                if cur > peak:
                    peak = cur
                drop = peak - cur
                decay = drop > (step * 8 * TICK * sens)
                slip = cur < (peak * 0.85)
                if decay and slip and cnt >= min_dec and peak > 0:
                    orders.append(('close_all', 'hybrid'))
                    peak = 0.0
                    cnt = 0
        pos_prev = pos
        pending = orders if i < n - 1 else []       # orders placed on the last bar never fill
    if tr is not None:                               # rule 5: close at the last close, kind 'end'
        close_trade(tr, n - 1, c[n - 1], 'end')
        tr = None
    return trades, cash, dict(raw_long=raw_l, raw_short=raw_s, blocked_long=blk_l, blocked_short=blk_s)


# ---------------------------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------------------------
def close(a, b, rtol=1e-9, atol=1e-9):
    if a is None or b is None or (isinstance(b, float) and np.isnan(b)):
        return (a is None or (isinstance(a, float) and np.isnan(a))) and \
               (b is None or (isinstance(b, float) and np.isnan(b)))
    return abs(a - b) <= atol + rtol * max(abs(a), abs(b))


def compare(Pp, X, sub):
    R = hrd.simulate(Pp, X)
    tf = hrd.trades_frame(Pp, R)
    s = hrd.summary_fast(Pp, R)
    mine, cash, cnts = ref_broker(Pp, X, sub)
    w0 = Pp['w0']
    msgs = []
    if len(tf) != len(mine):
        msgs.append(f'trade count engine {len(tf)} ref {len(mine)}')
    m = min(len(tf), len(mine))
    cols = {k: tf[k].to_numpy() for k in ('dir', 'entry_bar', 'exit_bar', 'signal_bar', 'entry_px', 'exit_px',
                                          'qty', 'pnl', 'costs', 'eq_before', 'sl_px', 'tp_px')}
    kinds = tf['exit_kind'].tolist()
    first_bad = None
    for j in range(m):
        t = mine[j]
        ok = (int(cols['dir'][j]) == t.d and int(cols['entry_bar'][j]) - w0 == t.ek
              and int(cols['exit_bar'][j]) - w0 == t.xk and int(cols['signal_bar'][j]) - w0 == t.sk
              and kinds[j] == t.kind
              and close(float(cols['entry_px'][j]), t.epx) and close(float(cols['exit_px'][j]), t.xpx)
              and close(float(cols['qty'][j]), t.qty) and close(float(cols['pnl'][j]), t.gross - t.ecost - t.xcost)
              and close(float(cols['costs'][j]), t.ecost + t.xcost)
              and close(float(cols['eq_before'][j]), t.eqb)
              and close(float(cols['sl_px'][j]), t.sl) and close(float(cols['tp_px'][j]), t.tp))
        if not ok:
            first_bad = j
            break
    if first_bad is not None:
        j = first_bad
        t = mine[j]
        msgs.append(f'first mismatch at trade {j}: engine {tf.iloc[j].to_dict()} | ref dir {t.d} ek {t.ek + w0} '
                    f'xk {t.xk + w0} sk {t.sk + w0} kind {t.kind} epx {t.epx} xpx {t.xpx} qty {t.qty} '
                    f'pnl {t.gross - t.ecost - t.xcost} sl {t.sl} tp {t.tp} eqb {t.eqb}')
    if not close(s['final_equity'], cash, rtol=1e-9, atol=1e-6):
        msgs.append(f'final equity engine {s["final_equity"]} ref {cash}')
    for k, v in cnts.items():
        if s[k] != v:
            msgs.append(f'{k} engine {s[k]} ref {v}')
    ntrail = sum(1 for t in mine if t.kind == 'trail')
    return msgs, len(mine), ntrail, mine


def rand_setting(rng, extra=False):
    X = {}
    if extra:
        # off-grid broker inputs too (not in the sweep grid): wider coverage of the exit code
        X['blkClose'] = rng.random() < 0.7
        X['InpTradeDirection'] = rng.choice(['Both', 'Both', 'Buy Only', 'Sell Only'])
        X['InpSlPct'] = rng.choice([2.0, 2.0, 0.5, 0.0])
        X['useHybridExit'] = rng.random() < 0.5
    if rng.random() < 0.85:
        X.update(trailOn=True, trailAct=rng.choice(ACTS), trailOff=rng.choice(OFFS))
    else:
        X.update(trailOn=False)
    X['InpTpPct'] = rng.choice([4.0, 0.0])
    X['InpExitCandles'] = rng.choice([5, 20, 100])
    X['cost'] = rng.choice(['tv', 'ours', 'stress'])
    return X


def run_check(ds, nset=40, seed=1, extra=False):
    pair, tf, st, en = DATASETS[ds]
    rng = random.Random(seed)
    settings = [(rand_setting(rng, extra), rng.random() < 0.3) for _ in range(nset)]   # (X, labels rev)
    t0 = time.time()
    preps = {}
    subs = {}
    for fon in (False, True):
        for rev in (False, True):
            prm = dict(fgfOn=fon, reverse=rev)
            if st is not None:
                prm.update(start=st, end=en)
            Pp = hrd.prepare(pair, tf, prm)
            preps[(fon, rev)] = Pp
            if rev is False:
                sub = build_sub(pair, Pp['t_open'], Pp['t_close'])
                emp, bad = check_sub(Pp, sub)
                print(f'{ds} filter {"on" if fon else "off"}: bars {Pp["n"]}, sub-bars {len(sub[2])}, '
                      f'chart bars without sub-bars {emp}, sub-bar aggregate mismatches {bad}', flush=True)
                subs[fon] = sub
    print(f'{ds}: prepared in {time.time() - t0:.1f}s', flush=True)
    tot = dict(runs=0, fail=0, trades=0, trail=0, kinds={}, cov={})
    for si, (X0, rev) in enumerate(settings):
        for fon in (False, True):
            for path in ('tv', 'mag'):
                X = dict(X0, path=path)
                Pp = preps[(fon, rev)]
                t1 = time.time()
                msgs, nt, ntr, mine = compare(Pp, X, subs[fon] if path == 'mag' else None)
                tot['runs'] += 1
                tot['trades'] += nt
                tot['trail'] += ntr
                for t in mine:
                    tot['kinds'][t.kind] = tot['kinds'].get(t.kind, 0) + 1
                    if t.kind in ('trail', 'sl', 'tp'):
                        key = f'{path}:{t.kind}:{t.how}' + (':fillbar' if t.xk == t.ek else '')
                        tot['cov'][key] = tot['cov'].get(key, 0) + 1
                    if t.kind == 'trail' and X0.get('trailAct') == 0:
                        tot['cov']['trail_act0'] = tot['cov'].get('trail_act0', 0) + 1
                    if t.kind == 'trail' and X0.get('InpTpPct') == 0.0:
                        tot['cov']['trail_tp_off'] = tot['cov'].get('trail_tp_off', 0) + 1
                tag = (f'{ds} s{si:02d} filt {"on " if fon else "off"} lab {"rev" if rev else "nor"} {path:3s} '
                       f'{X0}')
                if msgs:
                    tot['fail'] += 1
                    print('FAIL', tag, flush=True)
                    for mm in msgs:
                        print('    ', mm, flush=True)
                else:
                    print(f'ok   {tag}: {nt} trades, {ntr} trail ({time.time() - t1:.2f}s)', flush=True)
    print(f'{ds} TOTAL: runs {tot["runs"]}, failed {tot["fail"]}, trades {tot["trades"]}, trail exits '
          f'{tot["trail"]}, kinds {dict(sorted(tot["kinds"].items()))}, {time.time() - t0:.1f}s', flush=True)
    print(f'{ds} coverage (path:kind:how[:fillbar]): {dict(sorted(tot["cov"].items()))}', flush=True)
    return tot


# ---------------------------------------------------------------------------------------------
# hand traces
# ---------------------------------------------------------------------------------------------
TRACE_CASES = [
    ('BTC', '60', None, None, dict(trailOn=True, trailAct=0.5, trailOff=0.2, path='tv'), 0),
    ('BTC', '60', None, None, dict(trailOn=True, trailAct=0.3, trailOff=0.1, path='mag'), 1),
    ('XAU', '60', None, None, dict(trailOn=True, trailAct=0.0, trailOff=0.15, path='mag', InpTpPct=0.0), 2),
    ('XAU', '240', None, None, dict(trailOn=True, trailAct=0.2, trailOff=0.1, path='tv', cost='stress'), 3),
    ('BTC', '15', 1767225600, 1775001600, dict(trailOn=True, trailAct=0.1, trailOff=0.05, path='mag'), 4),
    # 6th: a trail exit filled at a later sub-bar's OPEN (the price jumped past the stop between sub-bars)
    ('XAU', '60', None, None, dict(trailOn=True, trailAct=0.1, trailOff=0.05, path='mag'), 'subopen'),
]


def trace():
    import datetime as _dt

    def ts(x):
        return _dt.datetime.fromtimestamp(int(x), _dt.timezone.utc).strftime('%Y-%m-%d %H:%M')

    for pair, tf, st, en, X, pick in TRACE_CASES:
        prm = dict(fgfOn=False)
        if st is not None:
            prm.update(start=st, end=en)
        Pp = hrd.prepare(pair, tf, prm)
        sub = build_sub(pair, Pp['t_open'], Pp['t_close']) if X['path'] == 'mag' else None
        mine, _, _ = ref_broker(Pp, X, sub)
        # prefer a trail exit that armed on a later bar than the fill and exits after the fill bar
        trails = [t for t in mine if t.kind == 'trail' and t.xk > t.ek]
        if pick == 'subopen':
            t = [u for u in trails if u.how == 'subopen' and u.xk - u.ek <= 2][0]
        else:
            t = trails[min(len(trails) - 1, 3 + 7 * pick)]
        log = []
        mine2, _, _ = ref_broker(Pp, X, sub, trace_sel=(t.ek, t.d), trace_log=log)
        R = hrd.simulate(Pp, X)
        tf_ = hrd.trades_frame(Pp, R)
        row = tf_[(tf_['entry_bar'] == t.ek + Pp['w0']) & (tf_['dir'] == t.d)]
        w0 = Pp['w0']
        print('=' * 110)
        print(f'{pair} {tf} filter off {X}')
        print(f'  {"LONG" if t.d > 0 else "SHORT"}: signal bar {t.sk + w0} close {Pp["c"][t.sk]} -> fill at the open '
              f'of bar {t.ek + w0} ({ts(Pp["t_open"][t.ek])} UTC) at {t.epx}, qty {t.qty:.6f}')
        ep = Pp['c'][t.sk]
        pts = max(ep * X['trailAct'] / 100.0 / TICK, 0.0)
        ofs = max(ep * X['trailOff'] / 100.0 / TICK, 1.0)
        print(f'  SL {t.sl}  TP {t.tp}  trail_points {pts:.4f} ticks -> activation A = fill '
              f'{"+" if t.d > 0 else "-"} {pts * TICK:.6f} = {t.A:.6f};  trail_offset {ofs:.4f} ticks = {t.off:.6f}')
        for line in log:
            print(line)
        stop = t.best - t.d * t.off
        print(f'  REF exit: bar {t.xk + w0} ({ts(Pp["t_open"][t.xk])} UTC) kind {t.kind} at {t.xpx} '
              f'(best {t.best}, trailing stop = best {"-" if t.d > 0 else "+"} offset = {stop:.6f}); '
              f'pnl {t.gross - t.ecost - t.xcost:.4f}')
        print('  ENGINE :', row[['dir', 'entry_bar', 'entry_px', 'exit_bar', 'exit_px', 'exit_kind', 'qty',
                                 'pnl']].to_dict('records'))


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'check':
        ds = sys.argv[2]
        nset = int(sys.argv[3]) if len(sys.argv) > 3 else 40
        seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        tot = run_check(ds, nset, seed, extra=len(sys.argv) > 5 and sys.argv[5] == 'extra')
        sys.exit(1 if tot['fail'] else 0)
    elif len(sys.argv) >= 2 and sys.argv[1] == 'mutate':
        # each mutation must make the comparison fail somewhere (sensitivity of the check)
        import io
        import contextlib
        for mut in ('A_from_signal', 'off_from_fill', 'trail_next_bar', 'no_sub_gap', 'round_ticks',
                    'arm_strict', 'mag_tv', 'mag_chart_dir'):
            MUT.clear()
            MUT.add(mut)
            res = []
            for ds in sys.argv[2:] or ['XAU240', 'BTC15']:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    tot = run_check(ds, 12, 7)
                res.append(f'{ds}: {tot["fail"]}/{tot["runs"]} runs differ')
            print(f'mutation {mut:16s}: ' + ', '.join(res), flush=True)
        MUT.clear()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'trace':
        trace()
    else:
        print(__doc__)
