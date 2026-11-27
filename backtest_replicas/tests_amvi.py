"""tests_amvi.py: stage 3 tests of the AMVI Full MTF Strategy + FGF [Update 1] replica (REPLICA_SPEC.md stage 3,
SPEC_amvi.md sections 8 and 13). Prints PASS / FAIL per test; exit code 1 on any failure.

Usage: python3 -I tests_amvi.py [T1 T2 ...] [--quick]
  T1  A == B == canonical, trade by trade and every summary field (reconcile_amvi_cmp.py, one process per cell,
      one at a time): BTC and XAU charts 1, 5, 15, 60, 240, full windows: fixed cases (filter on / off x inv x
      the three cost modes, fgfOn False, revClose 'closes', ltfRule 'last'), 8 settings drawn from the
      calibration grid, the extra inputs and the edge windows (--quick: XAU 60 and BTC 60 only, 3 grid draws)
  T2  path 'mag' on chart "1" == path 'tv' (BTC 1, XAU 1; nine settings each), bit for bit
  T3  path 'mag' with one fake sub-bar per chart bar (the bar itself) == path 'tv', bit for bit
  T4  both paths against a slow pure-Python reference written here from the Pine (L779-835) and SPEC_amvi
      sections 5-7: the strategy.exit re-sent on every bar from strategy.position_avg_price and the var entryAtr,
      as the Pine does it, the bracket walked bar by bar ('tv') or 1-minute sub-bar by sub-bar ('mag'), real
      prices for both sides; 30 random settings on 2-month windows
  T5  each cost mode and the fair halves against a direct recomputation from the trade list (which fills slip,
      the commission on the slipped price, P/L, eq_before, net, halves, R, counters)
  T6  the inv properties of SPEC_amvi section 8 and the statements of the Pine header (P1 exact mirror and its
      cost-'tv' counterexample, P2 single decisions, P3 first trade, P4 fgfOn False, P5 sides and zones incl.
      "Allow buys alone trades shorts only", P6 levels, P7 seconds timeframes, P8 noRepaint, P9 sizing, P10
      original's tradeDir / allowReverse, reversals and closes with Inverted)
  T7  revClose 'void' == 'closes' whenever rev_close_same_run == 0; otherwise the only differences are the
      zero-length trades 'closes' adds
  T8  timing: prepare BTC "1" under 2 minutes; simulate BTC "1" ('tv' and 'mag') and BTC "5" ('mag') under 1 s
  T9  the 1-minute sub-bars rebuild every chart bar (charts 5 to 240, both pairs) and a 'mag' exit lies in its
      chart bar
"""
import math
import os
import resource
import subprocess
import sys
import time

import numpy as np

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import amvi as M  # noqa: E402
import fgf  # noqa: E402

RESULTS = []
TICK = 0.01
WINDOWS = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}
# per fill, per unit: (fixed $, fraction of the fill value, slippage in price): SPEC_amvi section 9, written here
COST = {'tv': {'BTC': (0.0, 0.0004, 0.01), 'XAU': (0.0, 0.0004, 0.01)},
        'ours': {'BTC': (0.10, 0.0002, 0.0), 'XAU': (0.15, 0.0, 0.0)},
        'stress': {'BTC': (0.11, 0.00035, 0.0), 'XAU': (0.26, 0.0, 0.0)}}
TRAIL = {('BTC', '1'): (9.75, 6.5), ('BTC', '5'): (2.625, 1.75), ('XAU', '1'): (7.5, 5.0), ('XAU', '5'): (2.625, 1.75)}
_PC = {}


def report(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print('%s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def prep(pair, tf, pp=None):
    """prepare with a small cache (one cell's settings at a time)."""
    key = (pair, str(tf), repr(sorted((pp or {}).items())))
    if key not in _PC:
        if len(_PC) > 6:
            _PC.clear()
        _PC[key] = M.prepare(pair, tf, dict(pp or {}))
    return _PC[key]


def same_frames(ta, tb, rtol=None):
    """Every column equal (bit for bit, NaN == NaN) or, with rtol, floats to rtol."""
    if list(ta.columns) != list(tb.columns) or len(ta) != len(tb):
        return False, 'shape %s / %s' % (ta.shape, tb.shape)
    for c in ta.columns:
        a = ta[c].to_numpy()
        b = tb[c].to_numpy()
        if a.dtype.kind == 'f':
            if rtol is None:
                bad = ~((a == b) | (np.isnan(a) & np.isnan(b)))
            else:
                with np.errstate(invalid='ignore'):
                    d = np.abs(a - b)
                    bad = (d > rtol * np.maximum(np.abs(a), np.abs(b))) & (d > 1e-12)
                bad |= np.isnan(a) ^ np.isnan(b)
        else:
            bad = a != b
        if bad.any():
            i = int(np.argmax(bad))
            return False, 'row %d col %s: %r / %r' % (i, c, a[i], b[i])
    return True, ''


def same_summary(sa, sb, skip=()):
    for k in sa:
        if k in skip:
            continue
        x, y = sa[k], sb[k]
        if isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y):
            continue
        if x != y:
            return False, '%s %r / %r' % (k, x, y)
    return True, ''


# =================================================================================================================
# T1: A == B == canonical
# =================================================================================================================
def t1(quick=False):
    cells = [('XAU', '60'), ('BTC', '60')] if quick else [
        (p, tf) for p in ('XAU', 'BTC') for tf in ('240', '60', '15', '5', '1')]
    nr = '3' if quick else '8'
    for pair, tf in cells:
        t0 = time.time()
        r = subprocess.run([sys.executable, '-I', os.path.join(W, 'reconcile_amvi_cmp.py'), pair, tf, '--mods',
                            'a,b,c', '--nrand', nr, '--extra', '--edge'], capture_output=True, text=True)
        tot = [ln for ln in r.stdout.splitlines() if ln.startswith('TOTAL')]
        diff = [ln.strip()[:160] for ln in r.stdout.splitlines() if ' DIFF ' in ln]
        report('T1 A == B == canonical %s %s' % (pair, tf), r.returncode == 0 and tot and not diff,
               '%s (%.0f s)%s' % (tot[0] if tot else r.stderr[-300:], time.time() - t0,
                                  ('; first: ' + diff[0]) if diff else ''))


# =================================================================================================================
# T2 / T3: 'mag' == 'tv' on chart "1" and with fake sub-bars
# =================================================================================================================
def _settings(pair, tf):
    ta, to = TRAIL.get((pair, tf), (1.5, 1.0))
    return [({}, {}), ({}, {'inv': True}), ({'dirSource': 'orig'}, {'inv': True, 'cost': 'ours'}),
            ({}, {'useTrail': True, 'tpMult': 0.0, 'trailActMul': ta, 'trailOffMul': to}),
            ({}, {'useTrail': True, 'inv': True, 'cost': 'stress'}),
            ({'highVolThreshold': 60.0, 'minConfluence': 2}, {'maxBars': 3, 'revClose': 'closes', 'inv': True}),
            ({}, {'slMult': 0.0, 'cost': 'ours'}), ({}, {'tpMult': 0.0, 'useVolExit': False}),
            ({'dirSource': 'orig', 'dirMode': 'Candle'}, {'slMult': 0.0, 'tpMult': 0.0, 'useTrail': True,
                                                          'trailActMul': 0.5, 'trailOffMul': 0.25})]


def t2():
    for pair in ('XAU', 'BTC'):
        bad = []
        ntr = 0
        nexit = 0
        for pp, xx in _settings(pair, '1'):
            P = prep(pair, '1', pp)
            Rt = M.simulate(P, dict(xx, path='tv'))
            Rm = M.simulate(P, dict(xx, path='mag'))
            ok1, t1_ = same_frames(M.trades(P, Rt), M.trades(P, Rm))
            ok2, t2_ = same_summary(M.summary(P, Rt), M.summary(P, Rm))
            # on chart "1" every chart bar is its own (only) sub-bar: the exit sub-bar is the exit bar
            T = M.trades(P, Rm)
            br = Rm['xsub'] >= 0
            ok3 = bool(np.all(Rm['xsub'][br] == T['exit_bar'].to_numpy()[br] - P['w0']))
            nexit += int(br.sum())
            ntr += len(T)
            if not (ok1 and ok2 and ok3):
                bad.append('%r %r: %s %s %s' % (pp, xx, t1_, t2_, ok3))
        report('T2 mag == tv on chart 1, %s' % pair, not bad,
               '%d settings, %d trades, %d bracket exits%s' % (len(_settings(pair, '1')), ntr, nexit,
                                                                ('; ' + bad[0]) if bad else ''))
        _PC.clear()


def t3():
    for pair, tf in (('XAU', '15'), ('BTC', '60'), ('XAU', '240'), ('BTC', '5')):
        bad = []
        ntr = 0
        for pp, xx in _settings(pair, tf):
            P = prep(pair, tf, pp)
            Rt = M.simulate(P, dict(xx, path='tv'))
            Rf = M.simulate(P, dict(xx, path='mag'), sub=M.fake_sub_bars(P))
            ok1, t1_ = same_frames(M.trades(P, Rt), M.trades(P, Rf))
            ok2, t2_ = same_summary(M.summary(P, Rt), M.summary(P, Rf))
            ntr += len(M.trades(P, Rt))
            if not (ok1 and ok2):
                bad.append('%r %r: %s %s' % (pp, xx, t1_, t2_))
        report('T3 mag with one fake sub-bar per bar == tv, %s %s' % (pair, tf), not bad,
               '%d settings, %d trades%s' % (len(_settings(pair, tf)), ntr, ('; ' + bad[0]) if bad else ''))
    _PC.clear()


# =================================================================================================================
# T4: a slow pure-Python reference, written from the Pine
# =================================================================================================================
def _stop_in_force(t):
    """The stop of the open trade's strategy.exit: the stop loss and, once armed, the trailing stop; the nearer one
    to the price is in force. Returns (level or None, kind)."""
    side = t['side']
    sl = t['ex']['sl']
    ts = None
    if t['armed']:
        ts = t['best'] - t['off'] if side > 0 else t['best'] + t['off']
    if ts is None:
        return sl, 'sl'
    if sl is None:
        return ts, 'trail'
    if side > 0:
        return (ts, 'trail') if ts >= sl else (sl, 'sl')
    return (ts, 'trail') if ts <= sl else (sl, 'sl')


def _trail_see(t, price):
    """The trailing stop sees a price (activation at entry +/- trail_points ticks, then the best price)."""
    if t['ex']['pts'] is None:
        return
    side = t['side']
    if t['armed']:
        if (side > 0 and price > t['best']) or (side < 0 and price < t['best']):
            t['best'] = price
    else:
        act = t['e'] + t['ex']['pts'] * TICK if side > 0 else t['e'] - t['ex']['pts'] * TICK
        if (side > 0 and price >= act) or (side < 0 and price <= act):
            t['armed'] = True
            t['best'] = price


def _walk_segment(t, o, h, l, c):
    """One bar (or sub-bar) of the open trade's exit: the open, then O-H-L-C or O-L-H-C (high first when the
    high is nearer the open; a tie goes low first). Returns None or (raw price, kind)."""
    side = t['side']
    t['off'] = t['ex']['off'] * TICK if t['ex']['off'] is not None else 0.0
    S, sk = _stop_in_force(t)
    tp = t['ex']['tp']
    if S is not None and ((side > 0 and o <= S) or (side < 0 and o >= S)):
        return o, sk
    if tp is not None and ((side > 0 and o >= tp) or (side < 0 and o <= tp)):
        return o, 'tp'
    _trail_see(t, o)
    pts = (o, h, l, c) if (h - o) < (o - l) else (o, l, h, c)
    prev = o
    for b in pts[1:]:
        fav = (b > prev) if side > 0 else (b < prev)
        adv = (b < prev) if side > 0 else (b > prev)
        if fav:
            if tp is not None and ((side > 0 and b >= tp) or (side < 0 and b <= tp)):
                return (max(tp, prev) if side > 0 else min(tp, prev)), 'tp'
            _trail_see(t, b)
        elif adv:
            S, sk = _stop_in_force(t)
            if S is not None and ((side > 0 and b <= S) or (side < 0 and b >= S)):
                return (min(S, prev) if side > 0 else max(S, prev)), sk
        prev = b
    return None


def ref_simulate(P, X, sub=None):
    """Pure-Python run of the strategy section (L779-835) on prepare()'s signals, history rules of SPEC_amvi
    sections 5-7. X: simulate inputs (inv, slMult, tpMult, useTrail, trailActMul, trailOffMul, useVolExit,
    lowVolThreshold, maxBars, exitAtrLen, revClose, cost, tradeDir, allowReverse). sub: None = path 'tv', else
    (ptr, o, h, l, c) = path 'mag'. Returns (list of trade dicts, dict of totals)."""
    pair = P['pair']
    fix, pct, slip = COST[X['cost']][pair]
    b = fgf._bars(pair, P['tf'])
    atr = fgf._atr(b['high'], b['low'], b['close'], int(X['exitAtrLen']))[P['w0']:P['w1']]
    o, h, l, c = (P[k].tolist() for k in ('open', 'high', 'low', 'close'))
    avg = P['avgAmvi'].tolist()
    lo = float(X['lowVolThreshold'])
    up_a = P['trigUp'].tolist()
    dn_a = P['trigDn'].tolist()
    hot = P['hotCount'].tolist()
    n = P['n']
    slM, tpM = float(X['slMult']), float(X['tpMult'])
    inv = bool(X['inv'])
    has_bracket = slM > 0 or tpM > 0 or bool(X['useTrail'])
    cash = 10000.0
    trade = None
    entry_atr = float('nan')                       # var float entryAtr = na
    exits = {1: None, -1: None}                    # "L-Exit" / "S-Exit" as last sent
    pend = None                                    # the market entry placed by the last run
    pclose = None                                  # the close_all placed by the last run
    out = []
    peak = 10000.0
    mdd = 0.0
    nexpo = 0
    rcs = 0
    eq_mid = 10000.0

    def close_trade(px, kind, j, xsub=-1):
        nonlocal cash, trade
        t = trade
        gross = t['side'] * t['qty'] * (px - t['e'])
        xc = t['qty'] * (fix + pct * px)
        cash += gross - xc
        t.update(exit_bar=j, exit_px=px, kind=kind, pnl=gross - (t['cin'] + xc), xsub=xsub)
        out.append(t)
        trade = None

    for j in range(n):
        oj = o[j]
        # ---- A: the market orders of the last run, in placement order (the entry, then the close_all)
        if pend is not None:
            rev = False
            if trade is not None:
                assert trade['side'] == -pend['side']
                close_trade(oj - trade['side'] * slip, 'reverse', j)
                rev = True
            d = pend['side']
            e = oj + d * slip
            cin = pend['qty'] * (fix + pct * e)
            trade = dict(side=d, sig=pend['sig'], sig_bar=pend['bar'], entry_bar=j, e=e, qty=pend['qty'],
                         eqb=cash, cin=cin, hot=pend['hot'], rev=rev, armed=False, best=e, off=0.0,
                         ex=exits[d], sl0=exits[d]['sl'] if exits[d] else None,
                         tp0=exits[d]['tp'] if exits[d] else None)
            cash -= cin
            if pclose is not None:
                rcs += 1
                if X['revClose'] == 'closes':
                    close_trade(oj - d * slip, pclose, j)
        elif pclose is not None and trade is not None:
            close_trade(oj - trade['side'] * slip, pclose, j)
        pend = None
        pclose = None
        # ---- B: the exit order of the open trade's id, as last sent, along the bar / its sub-bars
        if trade is not None and has_bracket:
            trade['ex'] = exits[trade['side']]
            segs = [(j, oj, h[j], l[j], c[j])] if sub is None else [
                (s, sub[1][s], sub[2][s], sub[3][s], sub[4][s]) for s in range(sub[0][j], sub[0][j + 1])]
            for s, so, sh, sl_, sc in segs:
                hit = _walk_segment(trade, so, sh, sl_, sc)
                if hit is not None:
                    raw, kind = hit
                    close_trade(raw if kind == 'tp' else raw - trade['side'] * slip, kind, j,
                                s if sub is not None else -1)
                    break
        # ---- C: the script at the close (L779-835)
        cj = c[j]
        pos = trade['side'] if trade else 0
        equity = cash + (pos * trade['qty'] * (cj - trade['e']) if trade else 0.0)
        up, dn = up_a[j], dn_a[j]
        long_sig = (dn if inv else up) and X['tradeDir'] != 'Short Only'
        short_sig = (up if inv else dn) and X['tradeDir'] != 'Long Only'
        go_long = long_sig and pos <= 0 and (X['allowReverse'] or pos >= 0)
        go_short = short_sig and pos >= 0 and (X['allowReverse'] or pos <= 0)
        assert not (go_long and go_short)
        if go_long or go_short:
            entry_atr = float(atr[j])                                   # entryAtr := atrX
            pend = dict(side=1 if go_long else -1, qty=0.10 * equity / cj, sig=1 if up else -1, hot=hot[j], bar=j)
        pts = offt = None
        if X['useTrail'] and not math.isnan(entry_atr):
            pts = max(1, math.floor(entry_atr * X['trailActMul'] / TICK + 0.5))
            offt = max(1, math.floor(entry_atr * X['trailOffMul'] / TICK + 0.5))
        if has_bracket and (pos > 0 or go_long):
            ep = trade['e'] if pos > 0 else cj
            exits[1] = dict(sl=ep - entry_atr * slM if slM > 0 else None, tp=ep + entry_atr * tpM if tpM > 0 else None,
                            pts=pts, off=offt)
        if has_bracket and (pos < 0 or go_short):
            ep = trade['e'] if pos < 0 else cj
            exits[-1] = dict(sl=ep + entry_atr * slM if slM > 0 else None, tp=ep - entry_atr * tpM if tpM > 0 else None,
                             pts=pts, off=offt)
        if trade is not None and trade['entry_bar'] == j:
            trade['sl_px'] = exits[trade['side']]['sl'] if has_bracket else None
            trade['tp_px'] = exits[trade['side']]['tp'] if has_bracket else None
        vc = avg[j + 1] < lo and avg[j] >= lo                          # ta.crossunder(avgAmvi, lowVolThreshold)
        if X['useVolExit'] and pos != 0 and vc:
            pclose = 'vol'
        if X['maxBars'] > 0 and pos != 0 and j - trade['entry_bar'] >= X['maxBars'] and pclose is None:
            pclose = 'time'
        # ---- D
        if pos != 0:
            nexpo += 1
        eqc = cash + (pos * trade['qty'] * (cj - trade['e']) if trade else 0.0)
        if j < n - 1:
            peak = max(peak, eqc)
            mdd = max(mdd, (peak - eqc) / peak)
            if j == P['mid_j']:
                eq_mid = eqc
    if trade is not None:
        close_trade(c[n - 1] - trade['side'] * slip, 'end', n - 1)
    peak = max(peak, cash)
    mdd = max(mdd, (peak - cash) / peak)
    if P['mid_j'] == n - 1:
        eq_mid = cash
    return out, dict(final=cash, mdd=mdd * 100.0, expo=nexpo / n, rcs=rcs, eq_mid=eq_mid,
                     unfilled=int(pend is not None) + int(pclose is not None))


def _cmp_ref(P, R, ref, tot):
    T = M.trades(P, R)
    s = M.summary(P, R)
    w0 = P['w0']
    if len(T) != len(ref):
        return False, 'trades %d / %d' % (len(T), len(ref))
    for i, t in enumerate(ref):
        r = T.iloc[i]
        chk = [('dir', r['dir'], t['side']), ('sig', r['sig'], t['sig']), ('sig_bar', r['sig_bar'], t['sig_bar'] + w0),
               ('entry_bar', r['entry_bar'], t['entry_bar'] + w0), ('exit_bar', r['exit_bar'], t['exit_bar'] + w0),
               ('exit_kind', r['exit_kind'], t['kind']), ('hot', r['hot'], t['hot']), ('rev', bool(r['rev']), t['rev'])]
        for nm, a, b in chk:
            if a != b:
                return False, 'trade %d %s %r / %r' % (i, nm, a, b)
        for nm, a, b in (('entry_px', r['entry_px'], t['e']), ('qty', r['qty'], t['qty']),
                         ('exit_px', r['exit_px'], t['exit_px']), ('pnl', r['pnl'], t['pnl']),
                         ('eq_before', r['eq_before'], t['eqb']),
                         ('sl0', r['sl0'], t['sl0']), ('tp0', r['tp0'], t['tp0'])):
            b = float('nan') if b is None else b
            if math.isnan(a) and math.isnan(b):
                continue
            if not (abs(a - b) <= 1e-9 * max(abs(a), abs(b), 1.0)):
                return False, 'trade %d %s %r / %r' % (i, nm, a, b)
        if t['exit_bar'] > t['entry_bar'] and t['kind'] in ('sl', 'tp', 'trail'):
            for nm, a, b in (('sl_px', r['sl_px'], t.get('sl_px')), ('tp_px', r['tp_px'], t.get('tp_px'))):
                b = float('nan') if b is None else b
                if not ((math.isnan(a) and math.isnan(b)) or abs(a - b) <= 1e-9 * max(abs(a), abs(b))):
                    return False, 'trade %d %s %r / %r' % (i, nm, a, b)
        if R.get('sub_t_open') is not None and t['kind'] in ('sl', 'tp', 'trail'):
            if int(R['xsub'][i]) != t['xsub']:
                return False, 'trade %d exit sub-bar %d / %d' % (i, R['xsub'][i], t['xsub'])
    for nm, a, b in (('final_equity', s['final_equity'], tot['final']), ('max_dd_pct', s['max_dd_pct'], tot['mdd']),
                     ('exposure', s['exposure'], tot['expo']),
                     ('half1_pct', s['half1_pct'], (tot['eq_mid'] - 10000.0) / 100.0)):
        if not abs(a - b) <= 1e-9 * max(abs(a), abs(b), 1.0):
            return False, '%s %r / %r' % (nm, a, b)
    if s['rev_close_same_run'] != tot['rcs'] or s['orders_unfilled_end'] != tot['unfilled']:
        return False, 'rcs %d / %d, unfilled %d / %d' % (s['rev_close_same_run'], tot['rcs'],
                                                           s['orders_unfilled_end'], tot['unfilled'])
    return True, ''


def t4(nset=30, seed=4242):
    rng = np.random.default_rng(seed)
    bad = []
    ntr = {'tv': 0, 'mag': 0}
    kinds = {}
    ndiff_paths = 0
    t0 = time.time()
    for k in range(nset):
        pair = str(rng.choice(['BTC', 'XAU']))
        tf = str(rng.choice(['5', '15', '30', '60', '120', '240'] if k else ['1']))
        s0, e0 = WINDOWS[pair]
        st = int(s0 + rng.integers(0, e0 - s0 - 62 * 86400))
        pp = {'start': st, 'end': st + 61 * 86400,
              'highVolThreshold': float(rng.choice([50.0, 55.0, 60.0, 70.0])),
              'minConfluence': int(rng.choice([1, 2, 3]))}
        if rng.random() < 0.4:
            pp['dirSource'] = 'orig'
            pp['dirMode'] = str(rng.choice(['Trend (EMA)', 'Candle', 'Breakout (Donchian)']))
        elif rng.random() < 0.3:
            pp['fgfBandAtr'] = 0.0
        ta, to = TRAIL.get((pair, tf), (1.5, 1.0))
        X = dict(inv=bool(rng.random() < 0.5), slMult=float(rng.choice([0.0, 1.0, 1.5, 2.5])),
                 tpMult=float(rng.choice([0.0, 1.5, 3.0])), useTrail=bool(rng.random() < 0.4),
                 trailActMul=float(rng.choice([ta, 0.5])), trailOffMul=float(rng.choice([to, 0.25])),
                 useVolExit=bool(rng.random() < 0.6), lowVolThreshold=float(rng.choice([30.0, 40.0])),
                 maxBars=int(rng.choice([0, 0, 3, 8])), exitAtrLen=int(rng.choice([14, 7])),
                 revClose=str(rng.choice(['void', 'closes'])), cost=str(rng.choice(['tv', 'ours', 'stress'])),
                 tradeDir='Both', allowReverse=True)
        if pp.get('dirSource') == 'orig' and rng.random() < 0.3:
            X['allowReverse'] = False
        if pp.get('dirSource') == 'orig' and rng.random() < 0.2:
            X['tradeDir'] = str(rng.choice(['Long Only', 'Short Only']))
        P = M.prepare(pair, tf, pp)
        sub = M.get_sub(P)
        res = {}
        for path in ('tv', 'mag'):
            R = M.simulate(P, dict(X, path=path))
            ref, tot = ref_simulate(P, X, None if path == 'tv' else sub[:5])
            ok, txt = _cmp_ref(P, R, ref, tot)
            ntr[path] += len(ref)
            for t in ref:
                kinds[t['kind']] = kinds.get(t['kind'], 0) + 1
            res[path] = M.summary(P, R)
            if not ok:
                bad.append('%d %s %s %s: %s (%r %r)' % (k, pair, tf, path, txt, pp, X))
        if res['tv']['final_equity'] != res['mag']['final_equity']:
            ndiff_paths += 1
    report('T4 tv and mag against the pure-Python reference, %d random 2-month settings' % nset, not bad,
           'trades tv %d / mag %d, kinds %s, settings where mag != tv: %d, %.0f s%s' % (
               ntr['tv'], ntr['mag'], dict(sorted(kinds.items())), ndiff_paths, time.time() - t0,
               ('; ' + bad[0] + (' (+%d more)' % (len(bad) - 1) if len(bad) > 1 else '')) if bad else ''))
    # the default inputs on full windows, both directions, filter on and off, script costs
    bad = []
    ntr = 0
    t0 = time.time()
    for pair, tf in (('BTC', '60'), ('XAU', '15'), ('XAU', '240')):
        for pp in ({}, {'dirSource': 'orig'}):
            P = M.prepare(pair, tf, pp)
            sub = M.get_sub(P)
            for inv in (False, True):
                X = dict(M.DEFAULTS)
                X = {k: X[k] for k in ('slMult', 'tpMult', 'useTrail', 'trailActMul', 'trailOffMul', 'useVolExit',
                                       'lowVolThreshold', 'maxBars', 'exitAtrLen', 'revClose', 'cost', 'tradeDir',
                                       'allowReverse')}
                X['inv'] = inv
                for path in ('tv', 'mag'):
                    R = M.simulate(P, dict(X, path=path))
                    ref, tot = ref_simulate(P, X, None if path == 'tv' else sub[:5])
                    ok, txt = _cmp_ref(P, R, ref, tot)
                    ntr += len(ref)
                    if not ok:
                        bad.append('%s %s %r inv %s %s: %s' % (pair, tf, pp, inv, path, txt))
    report('T4 tv and mag against the pure-Python reference, default inputs, full windows (BTC 60, XAU 15, XAU 240)',
           not bad, '24 runs, %d trades, %.0f s%s' % (ntr, time.time() - t0, ('; ' + bad[0]) if bad else ''))


# =================================================================================================================
# T5: costs and fair halves from the trade list
# =================================================================================================================
def _check_trades_costs(P, R, cost):
    T = M.trades(P, R)
    s = M.summary(P, R)
    pair = P['pair']
    fix, pct, slip = COST[cost][pair]
    w0 = P['w0']
    o, c = P['open'], P['close']
    err = []
    if len(T) == 0:
        return err, 0
    d = T['dir'].to_numpy()
    eb = T['entry_bar'].to_numpy() - w0
    xb = T['exit_bar'].to_numpy() - w0
    kind = T['exit_kind'].to_numpy()
    q = T['qty'].to_numpy()
    epx = T['entry_px'].to_numpy()
    xpx = T['exit_px'].to_numpy()
    # every entry is a market fill at the bar's open, slipped against the order
    if not np.allclose(epx, o[eb] + d * slip, rtol=0, atol=1e-9):
        err.append('entry price')
    # market exits at the open, the 'end' close at the last close: slipped
    mk = np.isin(kind, ['reverse', 'vol', 'time'])
    if not np.allclose(xpx[mk], o[xb[mk]] - d[mk] * slip, rtol=0, atol=1e-9):
        err.append('market exit price')
    en = kind == 'end'
    if not np.allclose(xpx[en], c[-1] - d[en] * slip, rtol=0, atol=1e-9):
        err.append('end price')
    # a stop exit (stop loss / trailing) slips, a target exit does not: the raw price of a 'sl' / 'tp' exit is
    # the level in force (sl0 / tp0 on the fill bar, sl_px / tp_px later) or, through a gap, the open of the bar
    # ('tv') or of the 1-minute sub-bar ('mag') where it filled
    raw = np.where(np.isin(kind, ['sl', 'trail']), xpx + d * slip, xpx)
    mag = R.get('sub_t_open') is not None
    if mag:
        so = M.get_sub(P)[1]
    for i in np.where(np.isin(kind, ['sl', 'tp']))[0]:
        k = kind[i]
        lvl = T[k + '0'].iat[i] if xb[i] == eb[i] else T[k + '_px'].iat[i]
        op = so[R['xsub'][i]] if mag else o[xb[i]]
        if not (abs(raw[i] - lvl) < 1e-9 or abs(raw[i] - op) < 1e-9):
            err.append('%s %d raw %r level %r open %r' % (k, i, raw[i], lvl, op))
            break
    # commission on the slipped fill prices, P/L, equity chain
    costs = q * (fix + pct * epx) + q * (fix + pct * xpx)
    if not np.allclose(T['costs'].to_numpy(), costs, rtol=1e-12, atol=1e-12):
        err.append('costs')
    gross = d * q * (xpx - epx)
    if not np.allclose(T['pnl_gross'].to_numpy(), gross, rtol=1e-12, atol=1e-9):
        err.append('pnl_gross')
    pnl = T['pnl'].to_numpy()
    if not np.allclose(pnl, gross - costs, rtol=1e-9, atol=1e-9):
        err.append('pnl')
    eqb = 10000.0 + np.concatenate([[0.0], np.cumsum(pnl)[:-1]])
    if not np.allclose(T['eq_before'].to_numpy(), eqb, rtol=1e-12, atol=1e-7):
        err.append('eq_before')
    # summary
    if abs(s['net_pct'] - pnl.sum() / 100.0) > 1e-8 or abs(s['final_equity'] - (10000.0 + pnl.sum())) > 1e-6:
        err.append('net')
    if abs(s['costs'] - costs.sum()) > 1e-6:
        err.append('summary costs')
    nslip = len(T) + int((kind != 'tp').sum())
    if abs(s['slippage_paid'] - slip * (q.sum() + q[kind != 'tp'].sum())) > 1e-9 or (slip == 0 and s['slippage_paid']):
        err.append('slippage_paid')
    first = T['entry_time'].to_numpy() <= P['mid']
    h1 = (np.prod(1.0 + pnl[first] / eqb[first]) - 1.0) * 100.0
    h2 = (np.prod(1.0 + pnl[~first] / eqb[~first]) - 1.0) * 100.0
    if abs(s['h1r_pct'] - h1) > 1e-9 or abs(s['h2r_pct'] - h2) > 1e-9 or s['h1_trades'] != int(first.sum()):
        err.append('halves')
    if s['trades'] != len(T) or s['long'] != int((d > 0).sum()) or s['short'] != int((d < 0).sum()):
        err.append('counts')
    if abs(s['win_pct'] - 100.0 * (pnl > 0).mean()) > 1e-9:
        err.append('win')
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    if gl > 0 and abs(s['pf'] - gp / gl) > 1e-9:
        err.append('pf')
    for k in ('sl', 'tp', 'trail', 'reverse', 'vol', 'time', 'end'):
        if s['exit_' + k] != int((kind == k).sum()):
            err.append('exit_' + k)
    if s['zero_length'] != int((eb == xb).sum()) or abs(s['avg_bars_held'] - (xb - eb).mean()) > 1e-12:
        err.append('zero_length / avg_bars_held')
    sld = T['sl_dist'].to_numpy()
    if R['params']['slMult'] > 0:
        r = pnl / (sld * q)
        if abs(s['net_r'] - r.sum()) > 1e-7 or abs(s['h1_r'] - r[first].sum()) > 1e-7:
            err.append('net_r')
    if R['params']['useTrail']:
        if abs(s['min_trail_off_pct'] - np.min(np.maximum(1, np.floor(T['atr'].to_numpy() * R['params']['trailOffMul']
                                                                      / TICK + 0.5)) * TICK / epx) * 100.0) > 1e-9:
            err.append('min_trail_off_pct')
    # sl0 / tp0 / sl_dist from the order's ATR and the signal close
    sb = T['sig_bar'].to_numpy() - w0
    if not np.all(sb == eb - 1):
        err.append('sig_bar')
    return err, nslip


def t5():
    for pair, tf in (('BTC', '60'), ('XAU', '15'), ('BTC', '5'), ('XAU', '1')):
        bad = []
        ntr = 0
        ta, to = TRAIL.get((pair, tf), (1.5, 1.0))
        for pp, xx in (({}, {}), ({'dirSource': 'orig'}, {'inv': True}),
                       ({}, {'useTrail': True, 'tpMult': 0.0, 'trailActMul': ta, 'trailOffMul': to, 'inv': True}),
                       ({'highVolThreshold': 60.0, 'minConfluence': 2}, {'maxBars': 4})):
            P = prep(pair, tf, pp)
            for cost in ('tv', 'ours', 'stress'):
                for path in ('tv', 'mag'):
                    R = M.simulate(P, dict(xx, cost=cost, path=path))
                    err, _ = _check_trades_costs(P, R, cost)
                    ntr += M.summary(P, R)['trades']
                    if err:
                        bad.append('%r %r %s %s: %s' % (pp, xx, cost, path, err))
        report('T5 costs, prices and fair halves from the trade list, %s %s' % (pair, tf), not bad,
               '4 settings x 3 costs x 2 paths, %d trades%s' % (ntr, ('; ' + bad[0]) if bad else ''))
        _PC.clear()


# =================================================================================================================
# T6: inv properties (SPEC_amvi section 8) and the Pine header
# =================================================================================================================
def _mirror_equal(Ta, Tb):
    """P1: Tb (inv) is Ta (normal) with dir negated, sig equal, sl <-> tp swapped, every bar, price and other kind
    equal."""
    if len(Ta) != len(Tb):
        return False, 'trades %d / %d' % (len(Ta), len(Tb))
    sw = {'sl': 'tp', 'tp': 'sl'}
    ka = [sw.get(k, k) for k in Ta['exit_kind']]
    if ka != list(Tb['exit_kind']):
        i = next(i for i, (x, y) in enumerate(zip(ka, Tb['exit_kind'])) if x != y)
        return False, 'kind at %d: %s / %s' % (i, Ta['exit_kind'].iat[i], Tb['exit_kind'].iat[i])
    for c in ('sig_bar', 'entry_bar', 'exit_bar', 'sig', 'entry_px', 'exit_px', 'hot', 'rev'):
        if not (Ta[c].to_numpy() == Tb[c].to_numpy()).all():
            return False, 'column %s' % c
    if not (Ta['dir'].to_numpy() == -Tb['dir'].to_numpy()).all():
        return False, 'dir'
    return True, ''


def t6():
    # ---- P1: exact mirror with slMult == tpMult, no trail, cost 'ours' / 'stress' (no price shift), both paths
    bad = []
    n_ok = 0
    ntr = 0
    for pair, tf in (('BTC', '60'), ('XAU', '15'), ('BTC', '5'), ('XAU', '240')):
        for pp in ({}, {'dirSource': 'orig'}, {'dirSource': 'orig', 'dirMode': 'Candle', 'highVolThreshold': 60.0}):
            P = prep(pair, tf, pp)
            for xx in ({'slMult': 2.0, 'tpMult': 2.0}, {'slMult': 1.0, 'tpMult': 1.0, 'maxBars': 6},
                       {'slMult': 1.5, 'tpMult': 1.5, 'useVolExit': False}):
                for cost in ('ours', 'stress'):
                    for path in ('tv', 'mag'):
                        Ta = M.trades(P, M.simulate(P, dict(xx, cost=cost, path=path)))
                        Tb = M.trades(P, M.simulate(P, dict(xx, cost=cost, path=path, inv=True)))
                        ok, txt = _mirror_equal(Ta, Tb)
                        ntr += len(Ta)
                        if ok:
                            n_ok += 1
                        else:
                            bad.append('%s %s %r %r %s %s: %s' % (pair, tf, pp, xx, cost, path, txt))
        _PC.clear()
    report('T6 P1 exact mirror (slMult == tpMult, no trail, costs ours / stress, tv and mag)', not bad,
           '%d runs, %d trades%s' % (n_ok + len(bad), ntr, ('; ' + bad[0]) if bad else ''))
    # ---- P1 with cost 'tv' does not hold: the stop fill slips, the limit fill does not
    P = prep('BTC', '60')
    Ta = M.trades(P, M.simulate(P, {'slMult': 2.0, 'tpMult': 2.0}))
    Tb = M.trades(P, M.simulate(P, {'slMult': 2.0, 'tpMult': 2.0, 'inv': True}))
    ok, txt = _mirror_equal(Ta, Tb)
    ex = ''
    if not ok:
        i = int(np.argmax((Ta['exit_px'].to_numpy()[:min(len(Ta), len(Tb))] !=
                           Tb['exit_px'].to_numpy()[:min(len(Ta), len(Tb))])))
        ex = 'first trade with another exit price: #%d normal %s %s %.2f -> %.2f, inverted %s %s %.2f -> %.2f' % (
            i, Ta['dir'].iat[i], Ta['exit_kind'].iat[i], Ta['entry_px'].iat[i], Ta['exit_px'].iat[i],
            Tb['dir'].iat[i], Tb['exit_kind'].iat[i], Tb['entry_px'].iat[i], Tb['exit_px'].iat[i])
    report('T6 P1 counterexample with cost tv (slipped entries / stops)', not ok, '%s; %s' % (txt, ex))

    # ---- P2: single decisions, from the same state with the position negated
    bad = []
    nd = 0
    for pair, tf in (('BTC', '60'), ('XAU', '15')):
        P = prep(pair, tf)
        atr = M._atr_window(P, 14)
        idx = np.where(P['trigUp'] | P['trigDn'])[0][:4]
        for j in idx:
            for pos in (-1, 0, 1):
                for sl, tp, tr in ((1.5, 3.0, False), (2.0, 0.0, True)):
                    a = M._decide(-pos, 9876.5, P['close'][j], P['trigUp'][j], P['trigDn'][j], atr[j], False, True,
                                  True, True, sl, tp, tr, 1.5, 1.0, TICK, 0.10)
                    b = M._decide(pos, 9876.5, P['close'][j], P['trigUp'][j], P['trigDn'][j], atr[j], True, True,
                                  True, True, sl, tp, tr, 1.5, 1.0, TICK, 0.10)
                    nd += 1
                    cj = P['close'][j]
                    ok = (a[0] == b[0] and a[1] == -b[1] and a[2] == b[2] and a[3] == b[3] and a[6] == b[6]
                          and a[7] == b[7])
                    if ok and a[0] == 1:
                        for u, v in ((a[4], b[4]), (a[5], b[5])):
                            if math.isnan(u) != math.isnan(v) or (not math.isnan(u) and abs((u - cj) + (v - cj)) > 1e-9):
                                ok = False
                    if not ok:
                        bad.append('%s %s bar %d pos %d: %r / %r' % (pair, tf, j, pos, a, b))
                    # close_all: no side in it (L829-835)
                    for bars_in in (0, 3, 7):
                        if M._close_decision(pos, bars_in, True, True, 5) != M._close_decision(-pos, bars_in, True,
                                                                                              True, 5):
                            bad.append('close decision pos %d' % pos)
    report('T6 P2 single decisions: inv from p == the normal decision from -p, mirrored', not bad,
           '%d decisions (orders, ignored triggers, no signal) + close decisions%s' % (nd, ('; ' + bad[0]) if bad else ''))

    # ---- P3, P5, P6, P9 on default runs, P4, P10, header statements
    bad = {k: [] for k in ('P3', 'P4', 'P5', 'P6', 'P9', 'P10', 'H')}
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('XAU', '15'), ('BTC', '240')):
        for src in ('fgf', 'orig'):
            P = prep(pair, tf, {'dirSource': src})
            for path in ('tv', 'mag'):
                Tn = M.trades(P, M.simulate(P, {'path': path}))
                Ti = M.trades(P, M.simulate(P, {'path': path, 'inv': True}))
                # P3: the first trade
                if len(Tn) and len(Ti):
                    a, b = Tn.iloc[0], Ti.iloc[0]
                    if not (a['sig_bar'] == b['sig_bar'] and a['entry_bar'] == b['entry_bar'] and a['dir'] == -b['dir']
                            and abs((a['entry_px'] - a['dir'] * TICK) - (b['entry_px'] - b['dir'] * TICK)) < 1e-9
                            and a['qty'] == b['qty']):
                        bad['P3'].append('%s %s %s %s' % (pair, tf, src, path))
                # P5: dir == sig / -sig, sig = the normal-frame zone / bias of sig_bar
                for T, sgn in ((Tn, 1), (Ti, -1)):
                    sb = T['sig_bar'].to_numpy() - P['w0']
                    zone = np.where(P['dirUp'][sb], 1, np.where(P['dirDn'][sb], -1, 0))
                    if not ((T['dir'].to_numpy() == sgn * T['sig'].to_numpy()).all() and
                            (T['sig'].to_numpy() == zone).all() and P['trigger'][sb].all()):
                        bad['P5'].append('%s %s %s %s inv %d' % (pair, tf, src, path, sgn < 0))
                    # P6: levels from the signal close on the fill bar, then from the entry price
                    cs = P['close'][sb]
                    d = T['dir'].to_numpy()
                    if not (np.allclose(T['sl0'], cs - d * T['sl_dist'], rtol=0, atol=1e-9) and
                            np.allclose(T['tp0'], cs + d * T['tp_dist'], rtol=0, atol=1e-9)):
                        bad['P6'].append('%s %s %s fill-bar levels' % (pair, tf, src))
                    live = (T['exit_bar'] > T['entry_bar']).to_numpy()
                    if not (np.allclose(T['sl_px'][live], (T['entry_px'] - d * T['sl_dist'])[live], rtol=0, atol=1e-9)
                            and np.allclose(T['tp_px'][live], (T['entry_px'] + d * T['tp_dist'])[live], rtol=0,
                                            atol=1e-9) and T['sl_px'][~live].isna().all()):
                        bad['P6'].append('%s %s %s re-anchored levels' % (pair, tf, src))
                    # P9: qty = 0.10 x equity at the signal close / that close, equity from the trade list
                    pnl = T['pnl'].to_numpy()
                    eb = T['entry_bar'].to_numpy() - P['w0']
                    xb = T['exit_bar'].to_numpy() - P['w0']
                    for i in range(len(T)):
                        s = sb[i]
                        closed = xb[:i] <= s
                        eq = 10000.0 + pnl[:i][closed].sum()
                        op = np.where((~closed) & (eb[:i] <= s))[0]
                        if len(op):             # the trade open at that close: its entry cost paid, open P/L
                            k = op[0]
                            ent_cost = T['qty'].iat[k] * (COST['tv'][pair][0] + COST['tv'][pair][1]
                                                          * T['entry_px'].iat[k])
                            eq += -ent_cost + d[k] * T['qty'].iat[k] * (P['close'][s] - T['entry_px'].iat[k])
                        q = 0.10 * eq / P['close'][s]
                        if abs(q - T['qty'].iat[i]) > 1e-12 * q:
                            bad['P9'].append('%s %s %s %s trade %d %r / %r' % (pair, tf, src, path, i, q,
                                                                               T['qty'].iat[i]))
                            break
                # header: with Inverted a trigger in the other zone still reverses; collapse closes either side
                if src == 'fgf' and len(Ti):
                    rv = Ti.index[Ti['rev'].to_numpy()]
                    for i in rv:
                        if not (Ti['sig'].iat[i] == -Ti['sig'].iat[i - 1] and Ti['exit_kind'].iat[i - 1] == 'reverse'):
                            bad['H'].append('%s %s reversal %d' % (pair, tf, i))
                            break
        # P4: the literal fused file with the filter off trades nothing, both directions, both paths
        P = prep(pair, tf, {'fgfOn': False})
        for inv in (False, True):
            for path in ('tv', 'mag'):
                s = M.summary(P, M.simulate(P, {'inv': inv, 'path': path}))
                if not (s['trades'] == 0 and s['net_pct'] == 0 and s['trig_up'] == 0 and s['trig_dn'] == 0
                        and s['trig_none'] == s['triggers'] > 0):
                    bad['P4'].append('%s %s inv %s %s' % (pair, tf, inv, path))
        # P5 / header: fgfAllowSell off: normal = longs only, inverted = shorts only ("Allow buys alone trades
        # shorts only"); fgfAllowBuy off: the reverse
        for key, real_norm in (('fgfAllowSell', 1), ('fgfAllowBuy', -1)):
            P = prep(pair, tf, {key: False})
            Tn = M.trades(P, M.simulate(P, {}))
            Ti = M.trades(P, M.simulate(P, {'inv': True}))
            if not (len(Tn) and (Tn['dir'] == real_norm).all() and len(Ti) and (Ti['dir'] == -real_norm).all()
                    and (Tn['exit_kind'] != 'reverse').all()):
                bad['P5'].append('%s %s %s off' % (pair, tf, key))
        # P10: the original's allowReverse off / tradeDir
        P = prep(pair, tf, {'dirSource': 'orig'})
        for inv in (False, True):
            T = M.trades(P, M.simulate(P, {'allowReverse': False, 'inv': inv}))
            if (T['exit_kind'] == 'reverse').any():
                bad['P10'].append('%s %s allowReverse inv %s' % (pair, tf, inv))
            T = M.trades(P, M.simulate(P, {'tradeDir': 'Long Only', 'inv': inv}))
            if not (len(T) and (T['dir'] == 1).all() and (T['sig'] == (-1 if inv else 1)).all()):
                bad['P10'].append('%s %s Long Only inv %s' % (pair, tf, inv))
        _PC.clear()
    names = {'P3': 'first trade: same signal bar, fill bar, raw open, qty; opposite side',
             'P4': 'fgfOn False: no trade in either direction (header: "with it off ... nothing trades")',
             'P5': 'dir == sig (normal) / -sig (inverted), sig = the zone of the signal bar; Allow buys alone -> '
                   'shorts only when Inverted',
             'P6': 'levels from the signal close on the fill bar, then from the entry price',
             'P9': 'qty = 10 % of the equity at the signal close (recomputed from the trade list) / that close',
             'P10': "original's allowReverse off: no reversal; Long Only: longs only (sig per inv)",
             'H': 'header: with Inverted a trigger of the other zone reverses the position'}
    for k in ('P3', 'P4', 'P5', 'P6', 'P9', 'P10', 'H'):
        report('T6 %s %s' % (k, names[k]), not bad[k], ('; '.join(bad[k][:2])) if bad[k] else
               'BTC 60, XAU 60, XAU 15, BTC 240; filter on / off; tv and mag')

    # ---- P7 seconds timeframes; P8 noRepaint off = on shifted one bar (contiguous rows)
    bad = []
    for pair, tf in (('XAU', '60'), ('BTC', '15')):
        P0 = prep(pair, tf)
        P1 = prep(pair, tf, {'en1s': False, 'en5s': False, 'en15s': False, 'en30s': False, 'en45s': False})
        s0 = M.summary(P0, M.simulate(P0, {}))
        s1 = M.summary(P1, M.simulate(P1, {}))
        ok = (P0['trigger'] == P1['trigger']).all() and same_summary(s0, s1, skip=('seconds_ignored',))[0] and \
            s0['seconds_ignored'] == 5 and s1['seconds_ignored'] == 0
        P2 = prep(pair, tf, {k: False for k in ('en1', 'en5', 'en15', 'en30', 'en60', 'en240', 'enD')})
        ok = ok and P2['triggers'] == 0 and np.isnan(P2['avgAmvi']).all()
        if not ok:
            bad.append('P7 %s %s' % (pair, tf))
        Poff = prep(pair, tf, {'noRepaint': False})
        cont = P0['t_close'][:-1] == P0['t_open'][1:]          # rows j, j+1 contiguous, j = 0 .. n-2
        x_off = Poff['hotCount'][:-1][cont]
        x_on = P0['hotCount'][1:][cont]
        if not (x_off == x_on).all():
            bad.append('P8 %s %s hotCount' % (pair, tf))
        c2 = cont.copy()                                         # a cross also reads the row before
        c2[1:] &= cont[:-1]
        c2[0] = False
        if not (Poff['anyCross'][:-1][c2] == P0['anyCross'][1:][c2]).all():
            bad.append('P8 %s %s anyCross' % (pair, tf))
        ao = Poff['avgAmvi'][1:-1][cont]
        an = P0['avgAmvi'][2:][cont]
        if not np.allclose(ao, an, rtol=0, atol=0, equal_nan=True):
            bad.append('P8 %s %s avgAmvi' % (pair, tf))
        _PC.clear()
    report('T6 P7 seconds toggles change nothing, seven toggles off: no trigger; P8 noRepaint off = on one bar '
           'earlier (contiguous rows)', not bad, '; '.join(bad[:3]))


# =================================================================================================================
# T7: revClose
# =================================================================================================================
def t7():
    bad = []
    seen = 0
    pos_cases = 0
    for pair, tf in (('BTC', '60'), ('XAU', '15'), ('XAU', '240'), ('BTC', '5')):
        for pp, xx in (({}, {}), ({'dirSource': 'orig'}, {'inv': True}), ({}, {'maxBars': 5}),
                       ({'highVolThreshold': 60.0, 'minConfluence': 2}, {'maxBars': 3, 'inv': True}),
                       ({'highVolThreshold': 55.0, 'minConfluence': 1, 'dirSource': 'orig', 'dirMode': 'Candle'},
                        {'maxBars': 2, 'lowVolThreshold': 45.0})):
            P = prep(pair, tf, pp)
            for path in ('tv', 'mag'):
                Rv = M.simulate(P, dict(xx, path=path, revClose='void'))
                Rc = M.simulate(P, dict(xx, path=path, revClose='closes'))
                sv, sc = M.summary(P, Rv), M.summary(P, Rc)
                Tv, Tc = M.trades(P, Rv), M.trades(P, Rc)
                seen += 1
                if sv['rev_close_same_run'] == 0:
                    if not (same_frames(Tv, Tc)[0] and same_summary(sv, sc)[0]):
                        bad.append('%s %s %r %r %s equal expected' % (pair, tf, pp, xx, path))
                else:
                    pos_cases += 1
                    # 'closes' turns the first such reversal into a zero-length trade closed at its fill open
                    z = Tc[(Tc['entry_bar'] == Tc['exit_bar']) & Tc['rev'] & Tc['exit_kind'].isin(['vol', 'time'])]
                    if len(z) < 1 or len(z) > sc['rev_close_same_run']:
                        bad.append('%s %s %r %r %s closes' % (pair, tf, pp, xx, path))
                    else:
                        i = z.index[0]
                        if not (same_frames(Tv.iloc[:i].reset_index(drop=True), Tc.iloc[:i].reset_index(drop=True))[0]):
                            bad.append('%s %s %r %r %s prefix' % (pair, tf, pp, xx, path))
        _PC.clear()
    report('T7 revClose void == closes when rev_close_same_run == 0; else a zero-length close at the reversal', not bad,
           '%d runs, %d with rev_close_same_run > 0%s' % (seen, pos_cases, ('; ' + bad[0]) if bad else ''))


# =================================================================================================================
# T8: timing; T9: sub-bars
# =================================================================================================================
def t8():
    _PC.clear()
    t0 = time.time()
    P = M.prepare('BTC', '1')
    tp = time.time() - t0
    M.simulate(P, {})
    M.simulate(P, {'path': 'mag'})
    best = {}
    for path in ('tv', 'mag'):
        ts = []
        for _ in range(3):
            t1 = time.time()
            M.simulate(P, {'path': path, 'inv': True})
            ts.append(time.time() - t1)
        best[path] = min(ts)
    t1 = time.time()
    M.prepare('BTC', '1', {'highVolThreshold': 65.0})
    t_trig = time.time() - t1
    P = None
    _PC.clear()
    P5 = M.prepare('BTC', '5')
    M.get_sub(P5)
    t1 = time.time()
    M.simulate(P5, {'path': 'mag'})
    t5 = time.time() - t1
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0
    ok = tp < 120 and best['tv'] < 1.0 and best['mag'] < 1.0 and t5 < 1.0
    report('T8 timing', ok, 'prepare BTC 1 %.1f s (a further trigger setting %.2f s); simulate BTC 1 tv %.3f s, mag '
           '%.3f s; BTC 5 mag %.3f s; peak RSS %.2f GB' % (tp, t_trig, best['tv'], best['mag'], t5, rss))


def t9():
    bad = []
    nsub = 0
    for pair in ('XAU', 'BTC'):
        for tf in ('5', '15', '30', '60', '120', '240'):
            b = fgf._bars(pair, tf)
            s0, e0 = WINDOWS[pair]
            w0 = int(np.searchsorted(b['t_close'], s0, 'left'))
            w1 = int(np.searchsorted(b['t_close'], e0, 'right'))
            try:
                ptr, so, sh, sl, sc, st = M.sub_bars(pair, tf, w0, w1, check=True)
                nsub += len(so)
                if not ((st[ptr[:-1]] >= b['t_open'][w0:w1]).all() and (st[ptr[1:] - 1] < b['t_close'][w0:w1]).all()):
                    bad.append('%s %s times' % (pair, tf))
            except ValueError as ex:
                bad.append('%s %s: %s' % (pair, tf, ex))
    report('T9 the 1-minute sub-bars rebuild every chart bar (charts 5-240, both pairs, full windows)', not bad,
           '%d sub-bars%s' % (nsub, ('; ' + bad[0]) if bad else ''))
    # a 'mag' bracket exit lies inside its chart bar and its sub-bar range
    bad = []
    nx = 0
    for pair, tf in (('BTC', '60'), ('XAU', '240')):
        P = prep(pair, tf)
        for xx in ({}, {'useTrail': True, 'tpMult': 0.0, 'inv': True}):
            R = M.simulate(P, dict(xx, path='mag', cost='ours'))
            T = M.trades(P, R)
            ptr, so, sh, sl, sc, st = M.get_sub(P)
            for i in np.where(R['xsub'] >= 0)[0]:
                nx += 1
                s = R['xsub'][i]
                j = T['exit_bar'].iat[i] - P['w0']
                px = T['exit_px'].iat[i]
                if not (ptr[j] <= s < ptr[j + 1] and sl[s] - 1e-9 <= px <= sh[s] + 1e-9):
                    bad.append('%s %s trade %d' % (pair, tf, i))
                    break
        _PC.clear()
    report("T9 every 'mag' bracket exit fills inside its 1-minute sub-bar, inside its chart bar", not bad,
           '%d exits%s' % (nx, ('; ' + bad[0]) if bad else ''))


def main(argv):
    quick = '--quick' in argv
    want = [a for a in argv if not a.startswith('--')] or ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9']
    t0 = time.time()
    fns = {'T1': lambda: t1(quick), 'T2': t2, 'T3': t3, 'T4': t4, 'T5': t5, 'T6': t6, 'T7': t7, 'T8': t8, 'T9': t9}
    for k in want:
        try:
            fns[k]()
        except Exception as ex:                       # noqa: BLE001
            import traceback
            traceback.print_exc()
            report('%s raised' % k, False, '%s: %s' % (type(ex).__name__, ex))
    npass = sum(ok for _, ok in RESULTS)
    print('TOTAL %d PASS, %d FAIL, %.0f s' % (npass, len(RESULTS) - npass, time.time() - t0), flush=True)
    return 0 if npass == len(RESULTS) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
