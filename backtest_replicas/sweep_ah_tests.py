"""sweep_ah_tests.py: tests of SWEEP_AH_SPEC.md section 4 (trailing sweep of ApexForge + FGF
and HRD v1.03 + FGF).

Usage: python3 -I sweep_ah_tests.py [FILTER ...]
  Runs every function named test_<strategy>_<Rn>_<name> whose name contains one of the
  FILTER substrings (none = all), e.g. `apex`, `hrd`, `apex_R2`. Prints PASS / FAIL per test
  and exits non-zero on any failure. Each strategy's tests are separate functions (the apex
  ones live in the APEX section below).
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
OUT = os.path.join(W, 'out')
TFS = ('1', '5', '15', '30', '60', '120', '240')
INIT = 1_000_000.0


def _p(*a):
    print(*a, flush=True)


# =============================================================================================
# APEX: ApexForge Flow Resonance + FGF (apex.py, sweep_apex.py)
# =============================================================================================
APEX_GRID_ACTS = (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
APEX_GRID_OFFS = (0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
APEX_TOL = 0.01 * 1e-6          # trailing touch / arm tolerance (1e-6 tick), as documented in apex.py


def _apex_ref_costs(pair, cost):
    """(rate of value, $ per unit) per fill, written from the specs (not apex.cost_rates)."""
    if cost == 'tv':
        return 0.04 / 100.0, 0.0
    if pair == 'XAU':
        return 0.0, (0.30 / 2.0 if cost == 'ours' else 0.50 / 2.0 + 0.01)
    if cost == 'ours':
        return 0.02 / 100.0, 0.20 / 2.0
    return 0.035 / 100.0, 0.20 / 2.0 + 0.01


def _apex_ref_subbars(S):
    """Bar Magnifier sub-bars rebuilt independently: every 1-minute bar is mapped to the window
    chart bar that contains it (t_open[r] <= t < t_close[r]). Returns a list (per chart bar) of
    lists of (o, h, l, c) tuples."""
    m = pd.read_parquet(os.path.join(W, 'data', '%s_1.parquet' % S['pair']),
                        columns=['open', 'high', 'low', 'close', 't_open'])
    t = m['t_open'].to_numpy()
    to, tc = S['t_open'], S['t_close']
    sel = (t >= to[0]) & (t < tc[-1])
    m = m[sel]
    t = t[sel]
    r = np.searchsorted(to, t, side='right') - 1
    ok = (r >= 0) & (t < tc[np.maximum(r, 0)])
    subs = [[] for _ in range(len(to))]
    for ri, oo, hh, ll, cc in zip(r[ok].tolist(), m['open'].to_numpy()[ok].tolist(), m['high'].to_numpy()[ok].tolist(),
                                  m['low'].to_numpy()[ok].tolist(), m['close'].to_numpy()[ok].tolist()):
        subs[ri].append((oo, hh, ll, cc))
    return subs


def _apex_ref_bar_long(bo, bh, bl, bc, st):
    """Pure-Python long exit on one (sub-)bar, real prices. st: stop, limit (None = absent),
    trail (None or dict act_px, ofs, armed, best; mutated). Returns (kind, price) or None."""
    path = [bo, bh, bl, bc] if (bh - bo) < (bo - bl) else [bo, bl, bh, bc]
    tr = st['trail']

    def stops_hit(p):
        hits = []
        if st['stop'] is not None and p <= st['stop']:
            hits.append((st['stop'], 1, 'sl'))
        if tr is not None and tr['armed'] and p <= tr['best'] - tr['ofs'] + APEX_TOL:
            hits.append((tr['best'] - tr['ofs'], 2, 'trail'))
        return max(hits) if hits else None          # the higher stop is touched first (trail on a tie)

    def favour(p):
        if tr is None:
            return
        if tr['armed']:
            tr['best'] = max(tr['best'], p)
        elif p >= tr['act_px'] - APEX_TOL:
            tr['armed'] = True
            tr['best'] = p

    hit = stops_hit(bo)
    if hit:
        return hit[2], bo
    if st['limit'] is not None and bo >= st['limit']:
        return 'tp', bo
    favour(bo)
    for a, b in zip(path[:-1], path[1:]):
        if b > a:
            if st['limit'] is not None and b >= st['limit']:
                return 'tp', max(st['limit'], a)
            favour(b)
        elif b < a:
            hit = stops_hit(b)
            if hit:
                return hit[2], min(hit[0], a)
    return None


def _apex_ref_bar_short(bo, bh, bl, bc, st):
    """Short mirror of _apex_ref_bar_long, written out with real prices."""
    path = [bo, bh, bl, bc] if (bh - bo) < (bo - bl) else [bo, bl, bh, bc]
    tr = st['trail']

    def stops_hit(p):
        hits = []
        if st['stop'] is not None and p >= st['stop']:
            hits.append((-st['stop'], 1, 'sl'))
        if tr is not None and tr['armed'] and p >= tr['best'] + tr['ofs'] - APEX_TOL:
            hits.append((-(tr['best'] + tr['ofs']), 2, 'trail'))
        return max(hits) if hits else None          # the lower stop is touched first (trail on a tie)

    def favour(p):
        if tr is None:
            return
        if tr['armed']:
            tr['best'] = min(tr['best'], p)
        elif p <= tr['act_px'] + APEX_TOL:
            tr['armed'] = True
            tr['best'] = p

    hit = stops_hit(bo)
    if hit:
        return hit[2], bo
    if st['limit'] is not None and bo <= st['limit']:
        return 'tp', bo
    favour(bo)
    for a, b in zip(path[:-1], path[1:]):
        if b < a:
            if st['limit'] is not None and b <= st['limit']:
                return 'tp', min(st['limit'], a)
            favour(b)
        elif b > a:
            hit = stops_hit(b)
            if hit:
                return hit[2], max(-hit[0], a)
    return None


def apex_ref_run(S, X, subs=None):
    """Independent pure-Python ApexForge broker with the trailing take profit, written from the
    Pine (STRATEGY EXECUTION) and SPEC_AH / SWEEP_AH_SPEC rules; uses only the prepared signal /
    gate / zone-level arrays of apex.prepare. X: trailOn, trailAct, trailOff, useTarget,
    blkClose, cost, path ('mag' needs subs from _apex_ref_subbars). Returns a list of trade dicts."""
    o, h, l, c = (S[k].tolist() for k in ('o', 'h', 'l', 'c'))
    sigL, sigS = S['sig_l'].tolist(), S['sig_s'].tolist()
    bok, sok = S['buy_ok'].tolist(), S['sell_ok'].tolist()
    nan2none = lambda v: None if math.isnan(v) else v
    stopL, stopS = [nan2none(v) for v in S['stp_l'].tolist()], [nan2none(v) for v in S['stp_s'].tolist()]
    keep_target = not (X['trailOn'] and not X['useTarget'])
    limL = [nan2none(v) if keep_target else None for v in S['lim_l'].tolist()]
    limS = [nan2none(v) if keep_target else None for v in S['lim_s'].tolist()]
    rate, fee = _apex_ref_costs(S['pair'], X['cost'])
    n = len(c)
    trades = []
    closed = 0.0
    pos = None             # the open trade
    orders = {1: None, -1: None}       # strategy.exit "Exit Long" / "Exit Short"
    ticks = {1: (None, None), -1: (None, None)}   # apxTrPts / apxTrOfs (var floats)
    pending = []

    def fill_cost(px, q):
        return rate * px * q + fee * q

    def close_trade(px, kind, k):
        nonlocal pos, closed
        xc = fill_cost(px, pos['qty'])
        pnl = pos['dir'] * (px - pos['epx']) * pos['qty'] - pos['ecost'] - xc
        trades.append(dict(dir=pos['dir'], entry_bar=pos['ebar'], entry_px=pos['epx'], qty=pos['qty'],
                           exit_bar=k, exit_px=px, exit_kind=kind, pnl=pnl, eq_before=pos['eqb'],
                           signal_bar=pos['sbar']))
        closed += pnl
        orders[pos['dir']] = None          # its exit order is cancelled with the trade
        pos = None

    for k in range(n):
        for kind, d, q, sb in pending:
            if kind == 'entry':
                if pos is not None and pos['dir'] == d:
                    continue                                   # pyramiding 0
                if pos is not None:
                    close_trade(o[k], 'reverse', k)
                pts, ofs = ticks[d]
                eqb = INIT + closed
                pos = dict(dir=d, qty=q, epx=o[k], ecost=fill_cost(o[k], q), ebar=k, sbar=sb, eqb=eqb,
                           trail=None if pts is None else dict(act_px=o[k] + d * pts * 0.01, ofs=ofs * 0.01,
                                                               armed=False, best=o[k]))
            elif pos is not None and pos['dir'] == d:
                close_trade(o[k], 'blocked_close', k)
        pending = []
        if pos is not None and orders[pos['dir']] is not None:
            od = orders[pos['dir']]
            st = dict(stop=od['stop'], limit=od['limit'], trail=pos['trail'])
            bars = subs[k] if X['path'] == 'mag' else [(o[k], h[k], l[k], c[k])]
            fn = _apex_ref_bar_long if pos['dir'] > 0 else _apex_ref_bar_short
            for bo, bh, bl, bc in bars:
                res = fn(bo, bh, bl, bc, st)
                if res is not None:
                    close_trade(res[1], res[0], k)
                    break
        eq = INIT + closed
        if pos is not None:
            eq += pos['dir'] * (c[k] - pos['epx']) * pos['qty'] - pos['ecost']
        if k == n - 1:
            break
        p = 0 if pos is None else pos['dir']
        goL, goS = sigL[k] and bok[k], sigS[k] and sok[k]
        if X['blkClose'] and sigS[k] and not sok[k] and p > 0:
            pending.append(('close', 1, 0.0, k))
        if X['blkClose'] and sigL[k] and not bok[k] and p < 0:
            pending.append(('close', -1, 0.0, k))
        for d, go, sig, stops, lims in ((1, goL, sigL[k], stopL, limL), (-1, goS, sigS[k], stopS, limS)):
            if go:
                pending.append(('entry', d, 0.01 * eq / c[k], k))
                if p * d <= 0:                                 # position_size <= 0 (long) / >= 0 (short)
                    if X['trailOn']:
                        ticks[d] = (max(c[k] * X['trailAct'] / 100.0 / 0.01, 0.0),
                                    max(c[k] * X['trailOff'] / 100.0 / 0.01, 1.0))
                    else:
                        ticks[d] = (None, None)
            if go or (sig and p == d):
                orders[d] = dict(stop=stops[k], limit=lims[k])   # re-sent: the trade keeps its trail
    if pos is not None:
        close_trade(c[n - 1], 'end', n - 1)
    return trades


def _apex_cmp_trades(out, ref, w0=0):
    """Engine broker arrays vs reference trade dicts: ints / kinds / prices exact, money 1e-9."""
    import apex
    t_dir, t_eb, t_epx, t_qty, t_xb, t_xpx, t_kind, t_pnl, t_ecom, t_xcom, t_sigb = out[:11]
    t_eqb = out[13]
    if len(t_dir) != len(ref):
        return 'trade count %d vs ref %d' % (len(t_dir), len(ref))
    for j, r in enumerate(ref):
        eng = (int(t_dir[j]), int(t_eb[j]), int(t_xb[j]), int(t_sigb[j]), apex._KINDS[t_kind[j]],
               float(t_epx[j]), float(t_xpx[j]))
        rr = (r['dir'], r['entry_bar'], r['exit_bar'], r['signal_bar'], r['exit_kind'], r['entry_px'], r['exit_px'])
        if eng != rr:
            return 'trade %d: engine %s vs ref %s' % (j, eng, rr)
        for nm, a, b in (('qty', t_qty[j], r['qty']), ('pnl', t_pnl[j], r['pnl']), ('eq_before', t_eqb[j], r['eq_before'])):
            if not math.isclose(float(a), b, rel_tol=1e-9, abs_tol=1e-9):
                return 'trade %d: %s engine %r vs ref %r' % (j, nm, float(a), b)
    return None


def _apex_random_setting(rng, trail_share=0.9, path='tv'):
    def pick(grid, lo):
        return float(rng.choice(grid)) if rng.random() < 0.7 else float(np.round(rng.uniform(lo, 5.0), 4))
    return dict(trailOn=bool(rng.random() < trail_share), trailAct=pick(APEX_GRID_ACTS, 0.0),
                trailOff=pick(APEX_GRID_OFFS, 0.0), useTarget=bool(rng.random() < 0.5),
                blkClose=bool(rng.random() < 0.8), cost=str(rng.choice(['tv', 'ours', 'stress'])), path=path)


def _apex_clean(x):
    if isinstance(x, float):
        if math.isnan(x):
            return None
        if math.isinf(x):
            return 'inf' if x > 0 else '-inf'
        return x
    if isinstance(x, dict):
        return {k: _apex_clean(v) for k, v in x.items()}
    if hasattr(x, 'item'):
        return _apex_clean(x.item())
    return x


def test_apex_R1_regression():
    """Defaults (trail off, useTarget True, path 'tv'): every saved result of run_apex.py, all
    14 cells x every variant x cost, every saved summary field exact (seconds excluded), and
    the saved trade lists (out/apex_trades, cost tv) exact on every saved column."""
    import apex
    import run_apex
    ok = True
    n_sum = n_tr = n_rows = 0
    t0 = time.time()
    for pair in ('BTC', 'XAU'):
        for tf in TFS:
            t1 = time.time()
            saved = json.load(open(os.path.join(OUT, 'apex_%s_%s.json' % (pair, tf))))
            for var, by_cost in saved.items():
                if var.startswith('_'):
                    continue
                p = dict(run_apex.VARIANTS.get(var, run_apex.EXTRAS.get(var)))
                for cost, sv in by_cost.items():
                    q = dict(p)
                    q['cost'] = cost
                    tr, s = apex.run(pair, tf, q)
                    s = dict(s)
                    s['variant'] = var
                    s['stopped_at_fill_open'] = int(((tr.entry_bar == tr.exit_bar) & (tr.exit_kind == 'sl')
                                                     & (tr.exit_px == tr.entry_px)).sum())
                    s = _apex_clean(s)
                    bad = [k for k in sv if k != 'seconds' and sv[k] != s.get(k)]
                    n_sum += 1
                    if bad:
                        ok = False
                        _p('  FAIL summary %s %s %s %s: %s' % (pair, tf, var, cost,
                                                               [(k, sv[k], s.get(k)) for k in bad][:4]))
                    f = os.path.join(OUT, 'apex_trades', '%s_%s_%s.parquet' % (pair, tf, var))
                    if cost == 'tv' and os.path.exists(f):
                        old = pd.read_parquet(f)
                        n_tr += 1
                        n_rows += len(old)
                        same = len(old) == len(tr) and all(old[col].equals(tr[col]) for col in old.columns)
                        if not same:
                            ok = False
                            _p('  FAIL trades %s %s %s: %d saved vs %d now' % (pair, tf, var, len(old), len(tr)))
            _p('  %s %-4s: checked (%.1fs)' % (pair, tf, time.time() - t1))
    _p('  R1: %d summaries (every saved field), %d trade lists / %d trade rows (every saved column) '
       'compared exactly, %.0fs' % (n_sum, n_tr, n_rows, time.time() - t0))
    return ok


APEX_R2_WINDOWS = (('BTC', '60', None, None),                       # full windows
                   ('XAU', '60', None, None),
                   ('BTC', '5', 1735689600, 1751328000))            # 2025-01-01 -> 2025-07-01


def _apex_prep_window(pair, tf, start, end, flt, lab):
    import apex
    p = {'fgfOn': flt, 'reverse': lab}
    if start is not None:
        p.update(start=start, end=end)
    return apex.prepare(pair, tf, p)


def test_apex_R2_reference_tv():
    """Trail on (mostly), tv path: 30 random settings per window (BTC 60 / XAU 60 full, BTC 5
    six months; random activation / offset from the grid or uniform 0..5 %, useTarget, filter,
    labels, blkClose, cost incl. stress): the engine equals the independent pure-Python
    reference trade by trade."""
    import apex
    rng = np.random.default_rng(20261118)
    ok = True
    tot = {'runs': 0, 'trades': 0}
    kinds = {}
    t0 = time.time()
    for pair, tf, start, end in APEX_R2_WINDOWS:
        fails = 0
        for i in range(30):
            X = _apex_random_setting(rng)
            flt = bool(rng.random() < 0.6)
            lab = bool(rng.random() < 0.3)
            S = _apex_prep_window(pair, tf, start, end, flt, lab)
            out, s = apex.simulate(S, X)
            ref = apex_ref_run(S, X)
            err = _apex_cmp_trades(out, ref)
            tot['runs'] += 1
            tot['trades'] += len(ref)
            for r in ref:
                kinds[r['exit_kind']] = kinds.get(r['exit_kind'], 0) + 1
            if err:
                ok = False
                fails += 1
                _p('  FAIL %s %s %s fgf=%s rev=%s: %s' % (pair, tf, X, flt, lab, err))
        _p('  %s %s: 30 settings, %d failures' % (pair, tf, fails))
    _p('  R2 tv: %d runs, %d trades compared; exit kinds %s (%.0fs)' % (tot['runs'], tot['trades'], kinds,
                                                                       time.time() - t0))
    return ok and kinds.get('trail', 0) > 100


def test_apex_R2m_reference_mag():
    """Path 'mag' with the real 1-minute sub-bars (rebuilt independently in the reference):
    8 random trail settings each on BTC 60 and XAU 60 (full windows) and BTC 240 (full):
    engine == reference trade by trade."""
    import apex
    rng = np.random.default_rng(7)
    ok = True
    t0 = time.time()
    ntr = 0
    kinds = {}
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '240')):
        subs = None
        fails = 0
        for i in range(8):
            X = _apex_random_setting(rng, trail_share=1.0 if i else 0.0, path='mag')
            flt = bool(rng.random() < 0.6)
            lab = bool(rng.random() < 0.3)
            S = _apex_prep_window(pair, tf, None, None, flt, lab)
            if subs is None:
                subs = _apex_ref_subbars(S)
            out, s = apex.simulate(S, X)
            ref = apex_ref_run(S, X, subs)
            ntr += len(ref)
            for r in ref:
                kinds[r['exit_kind']] = kinds.get(r['exit_kind'], 0) + 1
            err = _apex_cmp_trades(out, ref)
            if err:
                ok = False
                fails += 1
                _p('  FAIL %s %s %s fgf=%s rev=%s: %s' % (pair, tf, X, flt, lab, err))
        _p('  %s %s: 8 settings, %d failures' % (pair, tf, fails))
    _p('  R2m mag: %d trades compared; exit kinds %s (%.0fs)' % (ntr, kinds, time.time() - t0))
    return ok


def _apex_same_out(a, b):
    for x, y in zip(a[:11] + a[13:], b[:11] + b[13:]):
        if not np.array_equal(x, y, equal_nan=True) if x.dtype.kind == 'f' else not np.array_equal(x, y):
            return False
    return True


def test_apex_R3_mag_equivalence():
    """mag on chart '1' == tv (BTC and XAU 1, full windows, 20 settings each), and mag with a
    fake sub-bar table (every chart bar its own single sub-bar) == tv (BTC 60 / XAU 60 / BTC 240,
    20 settings each): every trade array and the equity stats exactly equal."""
    import apex
    rng = np.random.default_rng(3)
    ok = True
    t0 = time.time()
    for pair, tf, fake in (('BTC', '1', False), ('XAU', '1', False), ('BTC', '60', True), ('XAU', '60', True),
                           ('BTC', '240', True)):
        fails = 0
        ntr = 0
        ntrail = 0
        for i in range(20):
            X = _apex_random_setting(rng, trail_share=0.9)
            flt = bool(rng.random() < 0.6)
            lab = bool(rng.random() < 0.3)
            S = apex.prepare(pair, tf, {'fgfOn': flt, 'reverse': lab})
            Xt = dict(X, path='tv')
            Xm = dict(X, path='mag')
            ot, st = apex.simulate(S, Xt)
            om, sm = apex.simulate(S, Xm, sub=apex.fake_sub_bars(S) if fake else None)
            ntr += len(ot[0])
            ntrail += int((ot[6] == apex.K_TRAIL).sum())
            same = _apex_same_out(ot, om) and np.array_equal(ot[14], om[14])
            if not same:
                ok = False
                fails += 1
                _p('  FAIL %s %s %s: mag != tv' % (pair, tf, X))
        _p('  %s %-3s %s: 20 settings, %d trades (%d trail), %d failures'
           % (pair, tf, 'fake sub-bars' if fake else 'real sub-bars (chart 1)', ntr, ntrail, fails))
    _p('  R3: %.0fs' % (time.time() - t0))
    return ok


def test_apex_R4_halves_and_stress():
    """Fair halves, eq_before and the stressed costs against direct recomputations from the
    trade list (20 random settings: windows of R2 + BTC 1 / XAU 1 full, tv and mag, all costs),
    and the kernel's equity statistics against the bar-close curve formulas."""
    import apex
    rng = np.random.default_rng(11)
    ok = True
    t0 = time.time()
    cases = [('BTC', '60'), ('XAU', '60'), ('BTC', '5'), ('XAU', '1'), ('BTC', '1'), ('XAU', '240')]
    stress = {'XAU': (0.0, 0.50 / 2 + 0.01), 'BTC': (0.00035, 0.20 / 2 + 0.01)}
    worst = {'eqb': 0.0, 'half': 0.0, 'cost': 0.0, 'qty': 0.0}
    n_stress = 0
    for i in range(20):
        pair, tf = cases[i % len(cases)]
        X = _apex_random_setting(rng, trail_share=0.8, path=str(rng.choice(['tv', 'mag'])))
        if i % 2 == 0:
            X['cost'] = 'stress'
        flt = bool(rng.random() < 0.6)
        lab = bool(rng.random() < 0.3)
        S = apex.prepare(pair, tf, {'fgfOn': flt, 'reverse': lab})
        out, s = apex.simulate(S, X, want_curves=True)
        tr = apex.trades_frame(S, out)
        msg = []
        # eq_before = initial capital + P/L of every earlier trade (one position at a time)
        eqb = INIT + np.concatenate([[0.0], np.cumsum(tr['pnl'].to_numpy())[:-1]])
        d = np.max(np.abs(eqb - tr['eq_before'].to_numpy()) / eqb) if len(tr) else 0.0
        worst['eqb'] = max(worst['eqb'], d)
        if d > 1e-12:
            msg.append('eq_before off by %g' % d)
        mid = S['start'] + (S['end'] - S['start']) // 2
        for half, sel in (('h1', tr['entry_time'] <= mid), ('h2', tr['entry_time'] > mid)):
            part = tr[sel]
            g = 1.0
            for pnl, e in zip(part['pnl'], part['eq_before']):
                g *= 1.0 + pnl / e
            want = 100.0 * (g - 1.0)
            dd = abs(want - s[half + 'r_pct'])
            worst['half'] = max(worst['half'], dd)
            if dd > 1e-9 or len(part) != s[half + '_trades']:
                msg.append('%s %r vs %r (%d vs %d trades)' % (half, s[half + 'r_pct'], want, s[half + '_trades'], len(part)))
        # costs per fill and pnl; final equity
        rate, fee = stress[pair] if X['cost'] == 'stress' else _apex_ref_costs(pair, X['cost'])
        q = tr['qty'].to_numpy()
        ec = rate * q * tr['entry_px'].to_numpy() + fee * q
        xc = rate * q * tr['exit_px'].to_numpy() + fee * q
        pnl = tr['dir'].to_numpy() * (tr['exit_px'].to_numpy() - tr['entry_px'].to_numpy()) * q - ec - xc
        for nm, a, b in (('entry_cost', tr['entry_cost'].to_numpy(), ec), ('exit_cost', tr['exit_cost'].to_numpy(), xc),
                         ('pnl', tr['pnl'].to_numpy(), pnl)):
            dd = float(np.max(np.abs(a - b))) if len(a) else 0.0
            worst['cost'] = max(worst['cost'], dd)
            if dd > 1e-6:
                msg.append('%s off by %g' % (nm, dd))
        if not math.isclose(s['final_equity'], INIT + float(tr['pnl'].sum()), rel_tol=1e-12):
            msg.append('final equity')
        # sizing: 1% of the equity at the signal close (closed P/L + open P/L - its entry cost)
        cw = S['c']
        w0 = S['w0']
        eb, xb, sb = tr['entry_bar'].to_numpy() - w0, tr['exit_bar'].to_numpy() - w0, tr['signal_bar'].to_numpy() - w0
        kd = tr['exit_kind'].to_numpy()
        pn = tr['pnl'].to_numpy()
        # one position at a time: trades are ordered by entry and by exit, and never overlap
        if len(tr) and not ((np.diff(eb) >= 0).all() and (np.diff(xb) >= 0).all() and (eb[1:] >= xb[:-1]).all()):
            msg.append('trades overlap')
        closed_x = np.where(kd != 'end', xb, np.iinfo(np.int64).max)      # an 'end' trade is never closed in time
        order = np.argsort(closed_x, kind='stable')
        cum = np.concatenate([[0.0], np.cumsum(pn[order])])
        for j in range(len(tr)):
            k = sb[j]
            eq = INIT + float(cum[np.searchsorted(closed_x[order], k, side='right')])   # trades closed by bar k's close
            m = int(np.searchsorted(eb, k, side='right')) - 1                       # the trade open at bar k's close
            if m >= 0 and (xb[m] > k or kd[m] == 'end'):
                eq += tr['dir'].iat[m] * (cw[k] - tr['entry_px'].iat[m]) * q[m] - tr['entry_cost'].iat[m]
            r = abs(0.01 * eq / cw[k] - q[j]) / q[j]
            worst['qty'] = max(worst['qty'], r)
            if r > 1e-9:
                msg.append('qty of trade %d off by %g' % (j, r))
                break
        # in-kernel equity statistics == the reconciled curve formulas
        eqc, posc = out[11], out[12]
        peak = np.maximum.accumulate(np.concatenate([[INIT], eqc]))
        ddc = (peak[1:] - eqc) / peak[1:]
        im = int(np.searchsorted(S['t_close'], mid, side='right')) - 1
        eq_mid = eqc[im] if im >= 0 else INIT
        if not (s['max_dd_pct'] == float(100.0 * ddc.max()) and s['exposure'] == float((posc != 0).mean())
                and s['half1_pct'] == float(100.0 * (eq_mid - INIT) / INIT) and s['final_equity'] == float(eqc[-1])):
            msg.append('kernel stats != curve formulas')
        n_stress += X['cost'] == 'stress'
        if msg:
            ok = False
            _p('  FAIL %s %s %s: %s' % (pair, tf, X, '; '.join(msg[:4])))
        else:
            _p('  ok %s %-3s %-6s %-3s trail=%d act=%-6s off=%-6s tgt=%d: %4d trades h1r %+.4f%% (%d) h2r %+.4f%% (%d)'
               % (pair, tf, X['cost'], X['path'], X['trailOn'], X['trailAct'], X['trailOff'], X['useTarget'],
                  len(tr), s['h1r_pct'], s['h1_trades'], s['h2r_pct'], s['h2_trades']))
    _p('  R4: 20 settings (%d with stress costs); worst rel eq_before %.2e, abs halves %.2e, abs cost/pnl %.2e, '
       'rel qty %.2e (%.0fs)' % (n_stress, worst['eqb'], worst['half'], worst['cost'], worst['qty'], time.time() - t0))
    return ok


def test_apex_R5_timing():
    """Timing: one full-grid pass on BTC 1 (tv, filter off, labels normal, cost tv: 394 settings,
    single process) and one mag setting on BTC 60 (full window)."""
    import apex
    import sweep_apex
    t0 = time.time()
    S = apex.prepare('BTC', '1', {'fgfOn': False})
    tp = time.time() - t0
    G = sweep_apex.grid()
    apex.simulate(S, sweep_apex.exit_params(G[2], 'tv', 'tv'))      # compiled / cached already
    t1 = time.time()
    for cfg in G:
        apex.simulate(S, sweep_apex.exit_params(cfg, 'tv', 'tv'))
    tg = time.time() - t1
    _p('  BTC 1 (%d bars): prepare %.1fs; full grid tv pass %d settings in %.1fs = %.4fs per setting'
       % (S['w1'] - S['w0'], tp, len(G), tg, tg / len(G)))
    S60 = apex.prepare('BTC', '60', {})
    t2 = time.time()
    sub = apex.sub_bars(S60)
    tsub = time.time() - t2
    X = dict(trailOn=True, trailAct=0.5, trailOff=0.2, useTarget=False, path='mag')
    apex.simulate(S60, X)
    t3 = time.time()
    reps = 20
    for _ in range(reps):
        out, s = apex.simulate(S60, X)
    tm = (time.time() - t3) / reps
    _p('  BTC 60 mag (%d chart bars, %d sub-bars, built in %.1fs): one setting %.4fs (%d trades, exposure %.3f)'
       % (S60['w1'] - S60['w0'], len(sub[1]), tsub, tm, s['trades'], s['exposure']))
    return tg / len(G) < 0.5


def _apex_spec_grid():
    """The 394 Apex exit settings of SWEEP_AH_SPEC.md section 3, from this file's own grid constants
    (not sweep_apex.grid()): {(trailOn, trailAct, trailOff, useTarget)}, None = no distance."""
    trail = [(False, None, None)] + [(True, float(a), float(o)) for a in APEX_GRID_ACTS for o in APEX_GRID_OFFS]
    return {t + (ut,) for t in trail for ut in (True, False)}


def _apex_row_setting(row):
    on = bool(row['trailOn'])
    return (on, float(row['trailAct']) if on else None, float(row['trailOff']) if on else None, bool(row['useTarget']))


def _apex_row_exit(row):
    """The exit params of a sweep row built from its own columns (not with sweep_apex.exit_params)."""
    X = {'trailOn': bool(row['trailOn']), 'useTarget': bool(row['useTarget']), 'path': row['path'],
         'cost': row['cost'], 'blkClose': True}
    if X['trailOn']:
        X['trailAct'] = float(row['trailAct'])
        X['trailOff'] = float(row['trailOff'])
    return X


def test_apex_R6_sweep_files():
    """Every out/swah_apex_<PAIR>_<TF>.parquet present: the 16 groups (filter x path x labels x
    cost) each hold exactly the 394 settings of the spec grid (checked against this file's own
    grid constants, not sweep_apex.grid()), one row per key, the same setting index -> setting
    columns in every group; rev rows carry the normal rows' raw long / short counts swapped; the
    trail-off tv rows equal the saved run_apex results (on / off / rev_on / rev_off); trail-off
    rows with useTarget False == True (the Pine keeps the target with the trailing off); chart 1:
    mag rows == tv rows; 12 random rows, one random trail-on row per group and every row of one
    random group, recomputed with apex.simulate from exit params built from the row's own columns
    (chart 1 mag rows with the real mag kernel), are identical."""
    import glob
    import apex
    import sweep_apex
    files = sorted(glob.glob(os.path.join(OUT, 'swah_apex_*_*.parquet')))
    if not files:
        _p('  no sweep files yet')
        return False
    ok = True
    rng = np.random.default_rng(1)
    G = sweep_apex.grid()
    spec = _apex_spec_grid()
    var = {('on', 'normal'): 'on', ('off', 'normal'): 'off', ('on', 'rev'): 'rev_on', ('off', 'rev'): 'rev_off'}
    for f in files:
        d = pd.read_parquet(f)
        pair, tf = d['pair'].iat[0], d['tf'].iat[0]
        msg = []
        keys = ['filter', 'path', 'labels', 'cost', 'setting']
        grp = d.groupby(keys[:4])
        n_groups = grp.ngroups
        costs = sorted(set(d['cost']))
        want = {(fl, p, lb, c) for fl in ('off', 'on') for p in ('tv', 'mag') for lb in ('normal', 'rev') for c in costs}
        if (d.duplicated(keys).any() or len(d) != n_groups * len(spec) or (grp.size() != len(spec)).any()
                or set(grp.groups) != want or not {'tv', 'ours'} <= set(costs)):
            msg.append('rows / keys / groups')
        smap = None
        for g, x in grp:
            st = [_apex_row_setting(r) for r in x[['trailOn', 'trailAct', 'trailOff', 'useTarget']].to_dict('records')]
            if len(set(st)) != len(st) or set(st) != spec:
                msg.append('group %s: settings != spec grid (%d missing, %d extra, %d duplicated)'
                           % (g, len(spec - set(st)), len(set(st) - spec), len(st) - len(set(st))))
            m = dict(zip(x['setting'].tolist(), st))
            if smap is None:
                smap = m
            elif m != smap:
                msg.append('group %s: setting index -> setting columns differ' % (g,))
        for fl in ('off', 'on'):           # rev = the labels swapped: raw long / short counts swap
            a = d[(d['filter'] == fl) & (d['labels'] == 'normal')][['raw_long', 'raw_short']].drop_duplicates()
            b = d[(d['filter'] == fl) & (d['labels'] == 'rev')][['raw_long', 'raw_short']].drop_duplicates()
            if not (len(a) == 1 and len(b) == 1 and a['raw_long'].iat[0] == b['raw_short'].iat[0]
                    and a['raw_short'].iat[0] == b['raw_long'].iat[0]):
                msg.append('rev raw counts not swapped (filter %s)' % fl)
        saved = json.load(open(os.path.join(OUT, 'apex_%s_%s.json' % (pair, tf))))
        off = d[~d['trailOn']]
        for (flt, lab), v in var.items():
            for cost in costs:
                if cost not in saved[v]:
                    continue
                r = off[(off['filter'] == flt) & (off['labels'] == lab) & (off['cost'] == cost) & (off['path'] == 'tv')]
                sv = saved[v][cost]
                for _, row in r.iterrows():
                    for k in ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'half1_pct', 'half2_pct', 'exposure',
                              'final_equity', 'costs', 'long', 'short', 'blocked_long', 'blocked_short'):
                        a = sv[k]
                        b = row[k]
                        a = float('inf') if a == 'inf' else a
                        if not ((a is None and np.isnan(b)) or a == b):
                            msg.append('trail-off %s %s %s %s: %r vs saved %r' % (flt, lab, cost, k, b, a))
        a = off[off['useTarget']].drop(columns=['setting', 'useTarget']).reset_index(drop=True)
        b = off[~off['useTarget']].drop(columns=['setting', 'useTarget']).reset_index(drop=True)
        if not a.equals(b):
            msg.append('trail-off useTarget True != False')
        if tf == '1':
            tvr = d[d['path'] == 'tv'].drop(columns='path').reset_index(drop=True)
            mgr = d[d['path'] == 'mag'].drop(columns='path').reset_index(drop=True)
            if not tvr.equals(mgr):
                msg.append('chart 1: mag rows != tv rows')
        picks = [int(i) for i in rng.choice(len(d), 12, replace=False)]
        trail_on = d['trailOn'].to_numpy()
        gsorted = sorted(grp.indices)
        for g in gsorted:
            ix = grp.indices[g]
            picks.append(int(rng.choice(ix[trail_on[ix]])))
        full = gsorted[int(rng.integers(len(gsorted)))]          # one whole group: every setting
        picks += [int(i) for i in grp.indices[full]]
        S = {}
        for i in picks:
            row = d.iloc[i]
            key = (row['filter'], row['labels'])
            if key not in S:
                S[key] = apex.prepare(pair, tf, {'fgfOn': key[0] == 'on', 'reverse': key[1] == 'rev'})
            cfg = G[int(row['setting'])]
            if not all((cfg[k] == row[k]) or (isinstance(cfg[k], float) and math.isnan(cfg[k]) and math.isnan(row[k]))
                       for k in sweep_apex.SET_COLS):
                msg.append('setting columns of row %d' % i)
            _, s = apex.simulate(S[key], _apex_row_exit(row))
            for k in sweep_apex.SUM_COLS:
                if not (s[k] == row[k] or (isinstance(s[k], float) and math.isnan(s[k]) and math.isnan(row[k]))):
                    msg.append('row %d %s: %r vs %r' % (i, k, row[k], s[k]))
        _p('  %s: %d rows (%d groups x %d settings), %d rows recomputed (all of group %s), %s'
           % (os.path.basename(f), len(d), n_groups, len(spec), len(picks), '/'.join(full),
              'ok' if not msg else 'FAIL ' + '; '.join(msg[:5])))
        ok = ok and not msg
    return ok


def test_apex_R7_edges_and_determinism():
    """What the random tests rarely reach, and determinism. (a) apex._walk unit cases (long space):
    a trailing stop equal to the zone stop is reported as 'trail' (falling segment and gapping
    open); a higher zone stop wins; the ratchet; no arming below the activation price; arming on a
    rising segment then the stop on the falling one in the same bar; the 1e-6-tick touch tolerance
    at the open. (b) engine == reference with trailOff 0 and tiny offsets (the Pine floors the
    offset at one tick), BTC 60 / XAU 60, tv and mag. (c) sweep_apex.grid() is the spec grid.
    (d) the XAU 240 sweep with 1 and 3 workers writes identical frames (== out/ file if present).
    (e) rev labels (BTC / XAU 60): sig_l / sig_s swapped, gate and brackets unchanged, every rev
    trade against the original label of its signal bar."""
    import shutil
    import tempfile
    import apex
    import sweep_apex
    ok = True
    t0 = time.time()
    # (a) apex._walk(v0, v1, v2, v3, sv, has_s, lv, has_l, has_t, A, off, armed, best, tol)
    tol = apex.TRAIL_TOL
    T, SL, TP, NONE = apex.K_TRAIL, apex.K_SL, apex.K_TP, -1
    cases = [
        ('tie on a falling segment -> trail', (105., 95., 106., 100., 100., True, 0., False, True, 0., 10., True, 110.), (T, 100.)),
        ('tie at a gapping open -> trail at the open', (99., 101., 98., 100., 100., True, 0., False, True, 0., 10., True, 110.), (T, 99.)),
        ('zone stop above the trail wins', (105., 95., 106., 100., 102., True, 0., False, True, 0., 10., True, 110.), (SL, 102.)),
        ('ratchet on the rising segment', (111., 120., 114., 118., 0., False, 0., False, True, 0., 5., True, 110.), (T, 115.)),
        ('no arming below the activation', (100., 104., 96., 97., 0., False, 0., False, True, 105., 5., False, 100.), (NONE, None)),
        ('arm on the rise, stop on the fall', (100., 99., 110., 100., 0., False, 0., False, True, 105., 5., False, 100.), (T, 105.)),
        ('target first on the rise', (112., 116., 104., 110., 0., False, 115., True, True, 0., 5., True, 110.), (TP, 115.)),
        ('touch within the tolerance at the open', (100. + 0.4 * tol, 101., 100.5, 101., 0., False, 0., False, True, 0., 10., True, 110.),
         (T, 100. + 0.4 * tol)),
        ('beyond the tolerance: no exit', (100. + 3 * tol, 101., 100.5, 101., 0., False, 0., False, True, 0., 10., True, 110.), (NONE, None)),
    ]
    for name, args, (wk, wpx) in cases:
        k, px, _, _ = apex._walk(*args, tol)
        good = int(k) == wk and (wpx is None or float(px) == wpx)
        if not good:
            ok = False
        _p('  walk %-42s %s (kind %d px %r, want %d %r)' % (name, 'ok' if good else 'FAIL', int(k), float(px), wk, wpx))
    # (b) offset floor of one tick and tiny offsets vs the reference
    rng = np.random.default_rng(77)
    n = fails = ntr = 0
    for pair in ('BTC', 'XAU'):
        subs = None
        for flt in (False, True):
            S = _apex_prep_window(pair, '60', None, None, flt, False)
            for path in ('tv', 'mag'):
                if path == 'mag' and subs is None:
                    subs = _apex_ref_subbars(S)
                for tro in (0.0, 1e-5, 1e-4):
                    X = dict(trailOn=True, trailAct=float(rng.choice([0.0, 0.05, 0.3])), trailOff=tro,
                             useTarget=bool(rng.random() < 0.5), blkClose=True, cost=str(rng.choice(['tv', 'ours', 'stress'])), path=path)
                    out, _ = apex.simulate(S, X)
                    ref = apex_ref_run(S, X, subs if path == 'mag' else None)
                    err = _apex_cmp_trades(out, ref)
                    n += 1
                    ntr += len(ref)
                    if err:
                        fails += 1
                        ok = False
                        _p('  FAIL %s 60 fgf=%s %s: %s' % (pair, flt, X, err))
    _p('  offset floor / tiny offsets: %d runs, %d trades, %d failures' % (n, ntr, fails))
    # (e) rev labels: the signals swap, the gate and the literal brackets stay, and every rev trade
    # goes against the original label of its signal bar
    for pair in ('BTC', 'XAU'):
        for flt in (False, True):
            Sn = _apex_prep_window(pair, '60', None, None, flt, False)
            Sr = _apex_prep_window(pair, '60', None, None, flt, True)
            out, _ = apex.simulate(Sr, {'trailOn': True, 'trailAct': 0.3, 'trailOff': 0.2})
            good = (np.array_equal(Sr['sig_l'], Sn['sig_s']) and np.array_equal(Sr['sig_s'], Sn['sig_l'])
                    and Sn['sig_l'].any() and Sn['sig_s'].any()
                    and np.array_equal(Sr['buy_ok'], Sn['buy_ok']) and np.array_equal(Sr['sell_ok'], Sn['sell_ok'])
                    and np.array_equal(Sr['stp_l'], Sn['stp_l'], equal_nan=True)
                    and np.array_equal(Sr['stp_s'], Sn['stp_s'], equal_nan=True)
                    and len(out[0]) > 0 and bool(np.all(np.where(out[0] > 0, Sn['sig_s'][out[10]], Sn['sig_l'][out[10]]))))
            ok = ok and good
            _p('  rev labels %s 60 fgf=%s: signals swapped, gate / brackets kept, %d trades against their original label: %s'
               % (pair, flt, len(out[0]), 'ok' if good else 'FAIL'))
    # (c) the sweep grid
    G = sweep_apex.grid()
    gs = [(g['trailOn'], g['trailAct'] if g['trailOn'] else None, g['trailOff'] if g['trailOn'] else None, g['useTarget']) for g in G]
    good = len(G) == 394 and len(set(gs)) == 394 and set(gs) == _apex_spec_grid()
    # every setting reaches apex.simulate intact (on XAU 240 useTarget never changes a result, so the
    # files alone cannot show a dropped useTarget / swapped distance)
    base = apex._params({})
    nbad = 0
    for cfg in G:
        for path in ('tv', 'mag'):
            for cost in apex.COSTS:
                X = apex._exit_params(base, sweep_apex.exit_params(cfg, path, cost))
                want = dict(trailOn=cfg['trailOn'], useTarget=cfg['useTarget'], path=path, cost=cost, blkClose=True)
                if cfg['trailOn']:
                    want.update(trailAct=cfg['trailAct'], trailOff=cfg['trailOff'])
                nbad += any(X[k] != v for k, v in want.items())
    good = good and nbad == 0
    ok = ok and good
    _p('  sweep_apex.grid(): %d settings, %d unique, == spec grid; sweep_apex.exit_params -> apex exit params '
       'wrong for %d of %d (setting, path, cost): %s' % (len(G), len(set(gs)), nbad, len(G) * 2 * len(apex.COSTS),
                                                        'ok' if good else 'FAIL'))
    # (d) determinism across worker counts
    tmp = tempfile.mkdtemp(prefix='.r7_det_', dir=W)
    try:
        d1, _ = sweep_apex.run_tf_sweep('XAU', '240', workers=1, out_dir=os.path.join(tmp, 'w1'), verbose=False)
        d3, _ = sweep_apex.run_tf_sweep('XAU', '240', workers=3, out_dir=os.path.join(tmp, 'w3'), verbose=False)
        f1 = pd.read_parquet(os.path.join(tmp, 'w1', 'swah_apex_XAU_240.parquet'))
        f3 = pd.read_parquet(os.path.join(tmp, 'w3', 'swah_apex_XAU_240.parquet'))
        same = f1.equals(f3) and d1.equals(d3) and len(f1) == 16 * 394
        fo = os.path.join(OUT, 'swah_apex_XAU_240.parquet')
        same_out = pd.read_parquet(fo).equals(f1) if os.path.exists(fo) else None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = ok and same and same_out is not False
    _p('  XAU 240 sweep, 1 vs 3 workers: %d rows, identical: %s; == out/ file: %s (%.0fs)'
       % (len(f1), same, same_out, time.time() - t0))
    return ok


# =============================================================================================
# HRD: HRD Full Divergence v1.03 + FGF (hrd.py, sweep_hrd.py)
# =============================================================================================
HRD_WINDOWS = (('BTC', '60', 1735689600, 1740787200),      # 2025-01-01 -> 2025-03-01
               ('XAU', '60', 1514851200, 1519862400),      # 2018-01-02 -> 2018-03-01
               ('BTC', '5', 1735689600, 1740787200))       # 2025-01-01 -> 2025-03-01
HRD_ACTS = (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
HRD_OFFS = (0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
HRD_KINDS = ['', 'sl', 'tp', 'reverse', 'blocked_close', 'time', 'hybrid', 'end', 'trail']
HRD_SUMMARY_KEYS = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'max_dd_init_pct', 'long', 'short',
                    'raw_long', 'raw_short', 'blocked_long', 'blocked_short', 'half1_pct', 'half2_pct',
                    'exposure', 'final_equity', 'zero_length', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
                    'avg_bars_held')


def _hrd_same(a, b):
    """Exact equality, NaN == NaN."""
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def _hrd_close(a, b, rtol=1e-9, atol=1e-9):
    if a is None or b is None:
        return a is None and b is None
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    if math.isinf(a) or math.isinf(b):
        return a == b
    return abs(a - b) <= atol + rtol * max(abs(a), abs(b))


def _hrd_ref_fill_cost(pair, cost, px, qty):
    """Cost of one fill, written from the specs (SPEC_AH.md 'Sizing and costs', SWEEP_AH_SPEC.md 2)."""
    if cost == 'tv':
        return 0.0                                   # HRD's strategy() sets no commission
    if pair == 'XAU':
        per_unit = 0.30 / 2.0 if cost == 'ours' else 0.50 / 2.0 + 0.01
        return qty * per_unit
    if cost == 'ours':
        return qty * (0.20 / 2.0) + qty * px * (0.02 / 100.0)
    return qty * (0.20 / 2.0 + 0.01) + qty * px * (0.035 / 100.0)


def _hrd_ref_subbars(Pp):
    """Bar Magnifier sub-bars rebuilt independently of hrd.sub_bars: every 1-minute bar goes to the
    first window chart bar whose t_close is after its t_open (kept when t_open >= that bar's
    t_open). Returns a list (per chart bar) of lists of (o, h, l, c)."""
    m = pd.read_parquet(os.path.join(W, 'data', '%s_1.parquet' % Pp['pair']),
                        columns=['open', 'high', 'low', 'close', 't_open'])
    to, tc = Pp['t_open'], Pp['t_close']
    t = m['t_open'].to_numpy()
    sel = (t >= to[0]) & (t < tc[-1])
    t = t[sel]
    r = np.searchsorted(tc, t, side='right')
    ok = (r < len(tc)) & (t >= to[np.minimum(r, len(tc) - 1)])
    subs = [[] for _ in range(len(to))]
    cols = [m[c].to_numpy()[sel][ok].tolist() for c in ('open', 'high', 'low', 'close')]
    for ri, oo, hh, ll, cc in zip(r[ok].tolist(), *cols):
        subs[ri].append((oo, hh, ll, cc))
    return subs


def _hrd_ref_exit(d, bo, bh, bl, bc, st):
    """The open trade's exit order (stop loss, limit, trailing stop) on one (sub-)bar, in real
    prices, written from SWEEP_AH_SPEC.md section 1 / SPEC_AH.md rule 4: path O-H-L-C if
    (H - O) < (O - L) else O-L-H-C; a stop / limit already beyond at the open fills at the open;
    the trail arms when price reaches the activation price and then follows the best price at the
    offset, moving only in the trade's favour; along the path the first level touched wins.
    st: dict(stop, limit, trail) (None = absent; trail = dict(A, ofs, armed, best), mutated).
    Returns (kind, price) or None."""
    path = [bo, bh, bl, bc] if (bh - bo) < (bo - bl) else [bo, bl, bh, bc]
    tr = st['trail']
    lim = st['limit']

    def stop_now():
        c = []
        if st['stop'] is not None:
            c.append(('sl', st['stop']))
        if tr is not None and tr['armed']:
            c.append(('trail', tr['best'] - tr['ofs'] if d > 0 else tr['best'] + tr['ofs']))
        if not c:
            return None
        if d > 0:                                   # the highest stop of a long; equal -> trail
            return max(c, key=lambda kv: (kv[1], kv[0] == 'trail'))
        return min(c, key=lambda kv: (kv[1], kv[0] != 'trail'))

    def follow(p):
        if tr is None:
            return
        if tr['armed']:
            if (d > 0 and p > tr['best']) or (d < 0 and p < tr['best']):
                tr['best'] = p
        elif (d > 0 and p >= tr['A']) or (d < 0 and p <= tr['A']):
            tr['armed'] = True
            tr['best'] = p

    p0 = path[0]
    s = stop_now()
    if s is not None and ((d > 0 and p0 <= s[1]) or (d < 0 and p0 >= s[1])):
        return s[0], p0
    if lim is not None and ((d > 0 and p0 >= lim) or (d < 0 and p0 <= lim)):
        return 'tp', p0
    follow(p0)
    for a, b in zip(path[:-1], path[1:]):
        if (d > 0 and b > a) or (d < 0 and b < a):          # towards the target
            if lim is not None and ((d > 0 and b >= lim) or (d < 0 and b <= lim)):
                return 'tp', lim
            follow(b)
        elif (d > 0 and b < a) or (d < 0 and b > a):        # against the trade
            s = stop_now()
            if s is not None and ((d > 0 and b <= s[1]) or (d < 0 and b >= s[1])):
                return s[0], s[1]
    return None


def hrd_ref_run(Pp, X, subs=None):
    """Plain pure-Python HRD v1.03 + FGF strategy and broker with the optional trailing take
    profit, written from the Pine (lines 880-980) and the specs. Inputs from hrd.prepare (the
    verified signals after Reverse Trading and the filter permissions, window OHLC); it does not
    use hrd's kernels. subs: per-bar 1-minute sub-bars (path 'mag') or None (path 'tv').
    Returns the list of trades (dicts)."""
    import hrd
    p = dict(hrd.DEFAULTS)
    p.update(Pp['params'])
    p.update(X)
    pair = Pp['pair']
    mt = 0.01
    o, h, l, c = (Pp[k].tolist() for k in ('o', 'h', 'l', 'c'))
    ls, ss = Pp['long_sig'].tolist(), Pp['short_sig'].tolist()
    bok, sok = Pp['buy_ok'].tolist(), Pp['sell_ok'].tolist()
    n = len(o)
    td = p['InpTradeDirection']
    long_allowed = td in ('Both', 'Buy Only')
    short_allowed = td in ('Both', 'Sell Only')
    sl_pct, tp_pct = float(p['InpSlPct']), float(p['InpTpPct'])
    trades = []
    st = {'cash': 1_000_000.0, 'pos': None}

    def close(k, px, kind):
        q = st['pos']
        xc = _hrd_ref_fill_cost(pair, p['cost'], px, q['qty'])
        gross = q['dir'] * q['qty'] * (px - q['px'])
        st['cash'] += gross - xc
        trades.append(dict(dir=q['dir'], ek=q['ek'], sk=q['sk'], epx=q['px'], qty=q['qty'], xk=k, xpx=px, kind=kind,
                           pnl=gross - (q['cost'] + xc), eqb=q['eqb'], sl=q['sl'], tp=q['tp']))
        st['pos'] = None

    pending = []
    prev_size = 0.0
    ebi = None
    g_peak, g_cnt = 0.0, 0
    for k in range(n):
        for od in pending:
            if od[0] == 'close_all':
                if st['pos'] is not None:
                    close(k, o[k], od[1])
            elif od[0] == 'close':
                if st['pos'] is not None and st['pos']['dir'] == od[1]:
                    close(k, o[k], od[2])
            else:
                _, d, qty, slp, tpp, pts, ofs, sk = od
                if st['pos'] is not None and st['pos']['dir'] == d:
                    continue                                  # pyramiding 0
                if st['pos'] is not None:
                    close(k, o[k], 'reverse')
                ec = _hrd_ref_fill_cost(pair, p['cost'], o[k], qty)
                eqb = st['cash']
                st['cash'] -= ec
                trail = None
                if pts is not None:
                    trail = dict(A=o[k] + d * pts * mt, ofs=ofs * mt, armed=pts == 0.0, best=o[k])
                st['pos'] = dict(dir=d, qty=qty, px=o[k], ek=k, sk=sk, cost=ec, eqb=eqb, sl=slp, tp=tpp,
                                 ex=dict(stop=slp, limit=tpp, trail=trail))
        pending = []
        q = st['pos']
        if q is not None and (q['sl'] is not None or q['tp'] is not None or q['ex']['trail'] is not None):
            for bar in (subs[k] if subs is not None else [(o[k], h[k], l[k], c[k])]):
                hit = _hrd_ref_exit(q['dir'], bar[0], bar[1], bar[2], bar[3], q['ex'])
                if hit is not None:
                    close(k, hit[1], hit[0])
                    break
        # the script at the close
        q = st['pos']
        size = q['dir'] * q['qty'] if q is not None else 0.0
        equity = st['cash'] + (q['dir'] * q['qty'] * (c[k] - q['px']) if q is not None else 0.0)
        if size != 0 and prev_size == 0:
            ebi = k
        if size != 0 and ebi is not None and (k - ebi >= int(p['InpExitCandles'])):
            pending.append(('close_all', 'time'))
            ebi = None
        want_l = ls[k] and long_allowed and size <= 0
        want_s = ss[k] and short_allowed and size >= 0
        blk_l = want_l and not bok[k]
        blk_s = want_s and not sok[k]
        if p['blkClose'] and blk_l and size < 0:
            pending.append(('close', -1, 'blocked_close'))
        if p['blkClose'] and blk_s and size > 0:
            pending.append(('close', 1, 'blocked_close'))
        for d, go in ((1, want_l and bok[k]), (-1, want_s and sok[k])):
            if not go:
                continue
            est = c[k]
            dist = est * (sl_pct / 100.0) if sl_pct > 0.0 else 0.0
            slp = (est * (1.0 - d * sl_pct / 100.0)) if sl_pct > 0.0 else None
            tpp = (est * (1.0 + d * tp_pct / 100.0)) if tp_pct > 0.0 else None
            if sl_pct <= 0.0 or dist <= 0.0:
                qty = float(p['InpFixedQty'])
            else:
                qty = equity * (float(p['InpRiskPct']) / 100.0) / (dist * 1.0)
                qty = max(qty, float(p['InpFixedQty']))
            pts = ofs = None
            if p['trailOn']:
                pts = max(est * float(p['trailAct']) / 100.0 / mt, 0.0)
                ofs = max(est * float(p['trailOff']) / 100.0 / mt, 1.0)
            pending.append(('entry', d, qty, slp, tpp, pts, ofs, k))
        # hybrid decay-slip exit
        in_trade = size != 0
        cur = 0.0
        if in_trade:
            cur = (c[k] - q['px']) if size > 0 else (q['px'] - c[k])
        if not in_trade:
            g_peak, g_cnt = 0.0, 0
        if p['useHybridExit'] and in_trade:
            if cur >= int(p['minActivationPts']) * mt or g_peak >= int(p['minActivationPts']) * mt:
                g_cnt += 1
                if cur > g_peak:
                    g_peak = cur
                decay = (g_peak - cur) > (float(p['trailStepMult']) * 8 * mt * float(p['hybridSensitivity']))
                slip = cur < g_peak * 0.85
                if decay and slip and g_cnt >= int(p['minDecayUpdates']) and g_peak > 0:
                    pending.append(('close_all', 'hybrid'))
                    g_peak, g_cnt = 0.0, 0
        prev_size = size
    if st['pos'] is not None:
        close(n - 1, c[n - 1], 'end')
    return trades


def _hrd_cmp_ref(R, ref, rtol=1e-9):
    """hrd.simulate output R vs hrd_ref_run trades: ints / kinds exact, floats within rtol.
    Returns (ok, message)."""
    nt = len(R['dir'])
    if nt != len(ref):
        return False, 'trade count %d vs ref %d' % (nt, len(ref))
    for i, t in enumerate(ref):
        ints = (int(R['dir'][i]) == t['dir'] and int(R['ek'][i]) == t['ek'] and int(R['sk'][i]) == t['sk']
                and int(R['xk'][i]) == t['xk'] and HRD_KINDS[int(R['kind'][i])] == t['kind'])
        pnl = float(R['gross'][i] - R['cost'][i])
        fl = (_hrd_close(float(R['epx'][i]), t['epx'], rtol, 0) and _hrd_close(float(R['xpx'][i]), t['xpx'], rtol, 0)
              and _hrd_close(float(R['qty'][i]), t['qty'], rtol, 0) and _hrd_close(pnl, t['pnl'], rtol, 1e-6)
              and _hrd_close(float(R['eqb'][i]), t['eqb'], rtol, 0)
              and (_hrd_close(float(R['sl'][i]), t['sl'], rtol, 0) if t['sl'] is not None else math.isnan(R['sl'][i]))
              and (_hrd_close(float(R['tp'][i]), t['tp'], rtol, 0) if t['tp'] is not None else math.isnan(R['tp'][i])))
        if not (ints and fl):
            return False, ('trade %d differs: engine dir %d entry %d exit %d kind %s px %.6f -> %.6f qty %.8f pnl %.6f | '
                           'ref %r' % (i, R['dir'][i], R['ek'][i], R['xk'][i], HRD_KINDS[int(R['kind'][i])], R['epx'][i],
                                       R['xpx'][i], R['qty'][i], pnl, t))
    return True, ''


def _hrd_random_X(rng, path='tv', trail_share=0.9):
    X = dict(path=path)
    X['trailOn'] = bool(rng.random() < trail_share)
    X['trailAct'] = float(rng.choice(HRD_ACTS)) if rng.random() < 0.7 else float(np.round(rng.uniform(0, 3), 3))
    X['trailOff'] = float(rng.choice(HRD_OFFS)) if rng.random() < 0.7 else float(np.round(rng.uniform(0.005, 3), 3))
    X['InpTpPct'] = float(rng.choice([4.0, 0.0, 0.0, float(np.round(rng.uniform(0.2, 6), 2))]))
    X['InpExitCandles'] = int(rng.choice([5, 20, 100, int(rng.integers(1, 60))]))
    X['InpSlPct'] = float(rng.choice([2.0, 2.0, 2.0, 0.0, float(np.round(rng.uniform(0.3, 5), 2))]))
    X['cost'] = str(rng.choice(['tv', 'ours', 'stress']))
    X['blkClose'] = bool(rng.random() < 0.8)
    X['useHybridExit'] = bool(rng.random() < 0.85)
    return X


def _hrd_prep_cache():
    import hrd
    cache = {}

    def get(pair, tf, start, end, flt, lab):
        key = (pair, tf, start, end, flt, lab)
        if key not in cache:
            prm = {'fgfOn': flt == 'on', 'reverse': lab == 'rev'}
            if start is not None:
                prm.update(start=start, end=end)
            cache[key] = hrd.prepare(pair, tf, prm)
        return cache[key]
    return get


def test_hrd_R1_regression():
    """R1: hrd.py with the defaults (trail off, path tv) reproduces every saved result exactly: all
    14 cells x every variant of out/hrd_<PAIR>_<TF>.json (every saved summary field, including
    run_hrd.extras) and every saved trade list in out/hrd_trades/ (every saved column)."""
    import hrd
    import run_hrd
    ok_all = True
    n_runs = n_fields = n_lists = n_rows = 0
    for pair in ('BTC', 'XAU'):
        for tf in TFS:
            saved = json.load(open(os.path.join(OUT, 'hrd_%s_%s.json' % (pair, tf))))
            bad = []
            for name, sv in saved['runs'].items():
                q = dict(sv['params'])
                tr, s = hrd.run(pair, tf, q)
                s2 = dict(s)
                s2.update(run_hrd.extras(tr, s))
                s2['params'] = q
                cl = run_hrd.clean(s2)
                for k, v in sv.items():
                    n_fields += 1
                    if k == 'exits':
                        same = all(cl['exits'].get(e) == x for e, x in v.items()) and cl['exits'].get('trail') == 0
                    else:
                        same = (k in cl and cl[k] == v)
                    if not same:
                        bad.append('%s.%s saved %r now %r' % (name, k, v, cl.get(k)))
                # hrd's own avg_bars_held equals the saved run_hrd one
                own = run_hrd.clean(s['avg_bars_held'])
                if own != sv.get('avg_bars_held'):
                    bad.append('%s.avg_bars_held (hrd) %r vs saved %r' % (name, own, sv.get('avg_bars_held')))
                n_runs += 1
                fn = os.path.join(OUT, 'hrd_trades', 'hrd_%s_%s_%s.parquet' % (pair, tf, name))
                if os.path.exists(fn):
                    old = pd.read_parquet(fn)
                    n_lists += 1
                    n_rows += len(old)
                    if len(old) != len(tr):
                        bad.append('%s trades %d vs saved %d' % (name, len(tr), len(old)))
                    else:
                        for col in old.columns:
                            if not old[col].reset_index(drop=True).equals(tr[col].reset_index(drop=True)):
                                bad.append('%s trades column %s differs' % (name, col))
                    if not np.allclose(tr['eq_before'].to_numpy(),
                                       INIT + np.concatenate([[0.0], np.cumsum(tr['pnl'].to_numpy())[:-1]]),
                                       rtol=1e-12, atol=1e-6):
                        bad.append('%s eq_before != initial + previous P/L' % name)
            _p('  %s %-3s: %2d runs, %s' % (pair, tf, len(saved['runs']), 'all equal' if not bad else
                                             '%d DIFFERENCES: %s' % (len(bad), '; '.join(bad[:6]))))
            ok_all &= not bad
            hrd._SIG.clear()
            hrd._PERM.clear()
    _p('  %d runs, %d saved fields, %d saved trade lists (%d rows) compared' % (n_runs, n_fields, n_lists, n_rows))
    return ok_all


def test_hrd_R1b_trail_off_vs_original():
    """R1b: with the trail off, the extended kernel equals the original one (hrd_a.py, the
    pre-trail implementation) trade by trade on 30 random trail-off settings (InpTpPct incl. 0,
    InpExitCandles incl. 20 / 100, SL, hybrid, blkClose, direction, cost tv / ours, filter, Reverse
    Trading) on the R2 windows and the full BTC 240 / XAU 240 windows."""
    import hrd
    import hrd_a
    rng = np.random.default_rng(20261118)
    wins = list(HRD_WINDOWS) + [('BTC', '240', None, None), ('XAU', '240', None, None)]
    ok_all = True
    n_tr = 0
    cols = None
    for i in range(30):
        pair, tf, start, end = wins[i % len(wins)]
        X = _hrd_random_X(rng)
        q = {k: X[k] for k in ('InpTpPct', 'InpExitCandles', 'InpSlPct', 'blkClose', 'useHybridExit')}
        q['cost'] = 'ours' if X['cost'] != 'tv' else 'tv'
        q['fgfOn'] = bool(rng.random() < 0.5)
        q['reverse'] = bool(rng.random() < 0.3)
        q['InpTradeDirection'] = str(rng.choice(['Both', 'Both', 'Buy Only', 'Sell Only']))
        if start is not None:
            q.update(start=start, end=end)
        ta, sa = hrd_a.run(pair, tf, q)
        tb, sb = hrd.run(pair, tf, q)
        cols = list(ta.columns)
        same = len(ta) == len(tb) and all(ta[c].equals(tb[c]) for c in cols)
        same &= all(_hrd_same(sa[k], sb[k]) for k in sa if k != 'exits') and all(sb['exits'][k] == v for k, v in sa['exits'].items())
        n_tr += len(ta)
        if not same:
            ok_all = False
            _p('  DIFF %s %s %r' % (pair, tf, q))
    _p('  30 settings, %d trades: %s (columns %s)' % (n_tr, 'all equal' if ok_all else 'DIFFERENCES', ', '.join(cols)))
    return ok_all


def _hrd_R2(path, n_per, wins, seed, trail_share=0.9):
    import hrd
    get = _hrd_prep_cache()
    rng = np.random.default_rng(seed)
    ok_all = True
    tot = {}
    nset = 0
    for pair, tf, start, end in wins:
        subs_cache = {}
        n_tr = 0
        t0 = time.time()
        for i in range(n_per):
            flt = 'on' if rng.random() < 0.5 else 'off'
            lab = 'rev' if rng.random() < 0.3 else 'normal'
            Pp = get(pair, tf, start, end, flt, lab)
            X = _hrd_random_X(rng, path, trail_share)
            subs = None
            if path == 'mag':
                if 'subs' not in subs_cache:
                    subs_cache['subs'] = _hrd_ref_subbars(Pp)
                subs = subs_cache['subs']
            R = hrd.simulate(Pp, X)
            ref = hrd_ref_run(Pp, X, subs)
            ok, msg = _hrd_cmp_ref(R, ref)
            nset += 1
            n_tr += len(ref)
            for t in ref:
                tot[t['kind']] = tot.get(t['kind'], 0) + 1
            if not ok:
                ok_all = False
                _p('  FAIL %s %s %s/%s %r: %s' % (pair, tf, flt, lab, X, msg))
        _p('  %s %-3s %s: %d settings, %d trades compared (%.1fs)' % (pair, tf, path, n_per, n_tr, time.time() - t0))
    _p('  exit kinds compared: %s' % ', '.join('%s %d' % kv for kv in sorted(tot.items())))
    return ok_all and tot.get('trail', 0) > 0


def test_hrd_R2_reference_tv():
    """R2: trail on (90% of settings), path tv: hrd.simulate equals the pure-Python reference
    hrd_ref_run trade by trade (dir, entry / signal / exit bars, kind exact; prices, qty, P/L,
    eq_before, SL / TP within 1e-9) on 30 random settings each over BTC 60, XAU 60 and BTC 5
    (2-month windows): random activation / offset, TP (incl. 0), time exit, SL, hybrid, blkClose,
    cost (tv / ours / stress), filter on / off, labels normal / rev."""
    return _hrd_R2('tv', 30, HRD_WINDOWS, 1)


def test_hrd_R2m_reference_mag():
    """R2m: path mag (Bar Magnifier): hrd.simulate equals hrd_ref_run with independently rebuilt
    1-minute sub-bars, trade by trade, on 15 random settings each over BTC 60 and XAU 60."""
    return _hrd_R2('mag', 15, HRD_WINDOWS[:2], 2)


def test_hrd_R3_mag_equivalence():
    """R3: mag on chart 1 (real 1-minute sub-bars = the chart bars) == tv, BTC and XAU full windows,
    8 settings each; mag with a fake sub-bar table (every chart bar its own single sub-bar) == tv,
    BTC 60 and XAU 60 full windows, 20 settings each. Every kernel output equal exactly."""
    import hrd
    rng = np.random.default_rng(3)
    ok_all = True

    def same(a, b):
        return all(np.array_equal(a[k], b[k], equal_nan=(a[k].dtype.kind == 'f')) for k in a)

    for pair, tf, nset, fake in (('BTC', '1', 8, False), ('XAU', '1', 8, False),
                                 ('BTC', '60', 20, True), ('XAU', '60', 20, True)):
        t0 = time.time()
        Pp = hrd.prepare(pair, tf, {'fgfOn': bool(rng.random() < 0.5)})
        if fake:
            Pp['sub'] = (np.arange(Pp['n'] + 1, dtype=np.int64), Pp['o'].copy(), Pp['h'].copy(), Pp['l'].copy(),
                         Pp['c'].copy())
        else:
            ptr = hrd.get_sub(Pp)[0]
            if not np.array_equal(ptr, np.arange(Pp['n'] + 1)):
                _p('  %s 1: sub-bar table is not one per chart bar' % pair)
                ok_all = False
        n_eq = 0
        n_tr = 0
        for i in range(nset):
            X = _hrd_random_X(rng, 'tv', 0.85)
            a = hrd.simulate(Pp, X)
            X['path'] = 'mag'
            b = hrd.simulate(Pp, X)
            n_tr += len(a['dir'])
            if same(a, b):
                n_eq += 1
            else:
                ok_all = False
                _p('  DIFF %s %s %r' % (pair, tf, X))
        _p('  %s %-3s %s: %d/%d settings equal (%d trades) (%.1fs)'
           % (pair, tf, 'fake sub-bars' if fake else 'real 1m sub-bars', n_eq, nset, n_tr, time.time() - t0))
        hrd._SIG.clear()
    return ok_all


def test_hrd_R4_halves_and_stress():
    """R4: (a) eq_before = initial capital + the P/L of every earlier trade; (b) h1r_pct / h2r_pct /
    h1_trades / h2_trades equal a direct recomputation from the trade list (split by entry_time
    <= mid, compounded 1 + pnl / eq_before); (c) stress costs (and ours / tv) equal a direct
    recomputation per fill from the spec; (d) summary_fast (the sweep) equals run()'s summary on
    every field exactly. 24 random settings (half stress) over the R2 windows and the full 240
    windows, tv and mag."""
    import hrd
    rng = np.random.default_rng(4)
    wins = list(HRD_WINDOWS) + [('BTC', '240', None, None), ('XAU', '240', None, None)]
    ok_all = True
    n_tr = n_stress = 0
    for i in range(24):
        pair, tf, start, end = wins[i % len(wins)]
        X = _hrd_random_X(rng, 'mag' if i % 4 == 3 else 'tv', 0.8)
        if i % 2 == 0:
            X['cost'] = 'stress'
        prm = {'fgfOn': bool(rng.random() < 0.5), 'reverse': bool(rng.random() < 0.3)}
        if start is not None:
            prm.update(start=start, end=end)
        tr, s = hrd.run(pair, tf, dict(prm, **X))
        Pp = hrd.prepare(pair, tf, prm)
        sf = hrd.summary_fast(Pp, hrd.simulate(Pp, X))
        bad = []
        n_tr += len(tr)
        # (a)
        pn = tr['pnl'].tolist()
        for j in range(len(tr)):
            if not _hrd_close(float(tr['eq_before'].iloc[j]), INIT + math.fsum(pn[:j]), 1e-12, 1e-6):
                bad.append('eq_before trade %d' % j)
                break
        # (b)
        s0, e0 = (start, end) if start is not None else hrd.WINDOWS[pair]
        mid = s0 + (e0 - s0) // 2
        g = {1: 1.0, 2: 1.0}
        cnt = {1: 0, 2: 0}
        for et, pnl, eqb in zip(tr['entry_time'].tolist(), pn, tr['eq_before'].tolist()):
            hh = 1 if et <= mid else 2
            g[hh] *= 1.0 + pnl / eqb
            cnt[hh] += 1
        for hh in (1, 2):
            if not _hrd_close(s['h%dr_pct' % hh], (g[hh] - 1.0) * 100.0, 1e-9, 1e-9):
                bad.append('h%dr_pct %r vs %r' % (hh, s['h%dr_pct' % hh], (g[hh] - 1.0) * 100.0))
            if s['h%d_trades' % hh] != cnt[hh]:
                bad.append('h%d_trades' % hh)
        # (c)
        for t in tr.itertuples():
            cst = (_hrd_ref_fill_cost(pair, X['cost'], t.entry_px, t.qty)
                   + _hrd_ref_fill_cost(pair, X['cost'], t.exit_px, t.qty))
            gross = t.dir * t.qty * (t.exit_px - t.entry_px)
            if not (_hrd_close(t.costs, cst, 1e-12, 1e-9) and _hrd_close(t.pnl_gross, gross, 1e-12, 1e-9)
                    and _hrd_close(t.pnl, gross - cst, 1e-12, 1e-6)):
                bad.append('costs trade %r' % (t,))
                break
        n_stress += len(tr) if X['cost'] == 'stress' else 0
        # (d)
        for k in HRD_SUMMARY_KEYS:
            if not _hrd_same(s[k], sf[k]):
                bad.append('summary_fast %s %r vs run %r' % (k, sf[k], s[k]))
        for kk, v in s['exits'].items():
            if sf['exit_' + kk] != v:
                bad.append('summary_fast exit_%s' % kk)
        if not _hrd_close(sf['costs'], float(tr['costs'].sum()), 1e-12, 1e-9):
            bad.append('costs sum')
        if bad:
            ok_all = False
            _p('  FAIL %s %s %r %r: %s' % (pair, tf, prm, X, '; '.join(bad[:5])))
    _p('  24 settings, %d trades (%d with stress costs) checked' % (n_tr, n_stress))
    return ok_all


def test_hrd_R5_timing():
    """R5: timing: one full-grid pass (1182 settings) on BTC 1, filter off, path tv, cost tv, single
    process (simulate + summary_fast); one mag setting on BTC 60 over the full window."""
    import hrd
    import sweep_hrd
    t0 = time.time()
    Pp = hrd.prepare('BTC', '1', {'fgfOn': False})
    tp = time.time() - t0
    G = sweep_hrd.grid()
    hrd.summary_fast(Pp, hrd.simulate(Pp, sweep_hrd.exit_params(G[2], 'tv', 'tv')))
    t1 = time.time()
    worst = 0.0
    for cfg in G:
        t2 = time.time()
        hrd.summary_fast(Pp, hrd.simulate(Pp, sweep_hrd.exit_params(cfg, 'tv', 'tv')))
        worst = max(worst, time.time() - t2)
    tg = time.time() - t1
    _p('  BTC 1 (%d bars): prepare %.1fs; full grid tv pass %d settings in %.1fs = %.4fs per setting (slowest %.4fs)'
       % (Pp['n'], tp, len(G), tg, tg / len(G), worst))
    hrd._SIG.clear()
    P60 = hrd.prepare('BTC', '60', {})
    t3 = time.time()
    sub = hrd.get_sub(P60)
    tsub = time.time() - t3
    X = dict(trailOn=True, trailAct=0.5, trailOff=0.2, InpTpPct=0.0, InpExitCandles=100, path='mag')
    hrd.simulate(P60, X)
    t4 = time.time()
    reps = 20
    for _ in range(reps):
        s = hrd.summary_fast(P60, hrd.simulate(P60, X))
    tm = (time.time() - t4) / reps
    _p('  BTC 60 mag (%d chart bars, %d sub-bars, built in %.1fs): one setting %.4fs (%d trades, exposure %.3f)'
       % (P60['n'], len(sub[1]), tsub, tm, s['trades'], s['exposure']))
    return tg / len(G) < 0.5


def test_hrd_R6_determinism():
    """R6: sweep_hrd output does not depend on the worker count: XAU 240, workers 1 vs 3, every row
    and column equal (files written to sweep_ah_backup/, not out/)."""
    import sweep_hrd
    d1 = os.path.join(W, 'sweep_ah_backup', 'det_w1')
    d3 = os.path.join(W, 'sweep_ah_backup', 'det_w3')
    a, ta = sweep_hrd.run_tf_sweep('XAU', '240', workers=1, out_dir=d1, verbose=False)
    b, tb = sweep_hrd.run_tf_sweep('XAU', '240', workers=3, out_dir=d3, verbose=False)
    fa = pd.read_parquet(os.path.join(d1, 'swah_hrd_XAU_240.parquet'))
    fb = pd.read_parquet(os.path.join(d3, 'swah_hrd_XAU_240.parquet'))
    ok = fa.equals(fb) and len(fa) == 2 * 2 * 2 * 2 * len(sweep_hrd.grid())
    _p('  XAU 240: %d rows, workers 1 %.1fs vs workers 3 %.1fs: %s' % (len(fa), ta, tb, 'identical' if ok else 'DIFFERENT'))
    return ok


def _hrd_ref_row(Pp, ref):
    """The sweep's trade-derived summary fields recomputed from hrd_ref_run's trade list."""
    pn = [t['pnl'] for t in ref]
    g = {1: 1.0, 2: 1.0}
    n1 = 0
    costs = 0.0
    for t in ref:
        if Pp['t_open'][t['ek']] <= Pp['mid']:
            g[1] *= 1.0 + t['pnl'] / t['eqb']
            n1 += 1
        else:
            g[2] *= 1.0 + t['pnl'] / t['eqb']
        costs += t['dir'] * t['qty'] * (t['xpx'] - t['epx']) - t['pnl']
    e = dict(trades=len(ref), net_pct=math.fsum(pn) / INIT * 100.0, final_equity=INIT + math.fsum(pn),
             long=sum(t['dir'] > 0 for t in ref), short=sum(t['dir'] < 0 for t in ref),
             h1r_pct=(g[1] - 1.0) * 100.0, h2r_pct=(g[2] - 1.0) * 100.0, h1_trades=n1, h2_trades=len(ref) - n1,
             avg_bars_held=float(np.mean([t['xk'] - t['ek'] for t in ref])) if ref else float('nan'),
             zero_length=sum(t['xk'] == t['ek'] for t in ref), costs=costs)
    for k in HRD_KINDS[1:]:
        e['exit_' + k] = sum(t['kind'] == k for t in ref)
    return e


def test_hrd_R7_sweep_rows():
    """R7: sweep_hrd's rows hold the settings they claim. XAU 240 sweep as run in production (workers 3,
    costs tv / ours; file in sweep_ah_backup/r7, read back): (a) grid completeness: the 16 groups
    filter x path x labels x cost, each exactly 1182 rows with unique keys and setting 0..1181, whose
    setting columns are the spec grid built here (activation x offset of SWEEP_AH_SPEC.md + trail off,
    x InpTpPct {4, 0} x InpExitCandles {5, 20, 100}) with one 'default' row (trail off, TP 4, 5 candles);
    (b) the 8 default tv rows equal the saved out/hrd_XAU_240.json runs on every saved scalar field
    exactly; (c) labels: prepare(reverse) swaps longSignal / shortSignal (filter off and on) and every
    rev group differs from its normal group; (d) 48 random rows (3 per group) equal the pure-Python
    reference hrd_ref_run run with the row's own filter / labels / path / cost / setting: trades,
    long / short, every exit count, net_pct, final equity, costs, h1r / h2r, h1 / h2 trades,
    avg_bars_held, zero_length; (e) on XAU 240 the 4 % target never fills, so a BTC 240 tv sweep (labels
    normal, cost tv) checks the InpTpPct column: no tp exit with TP 0, some with TP 4, and 6 rows with tp
    exits plus their TP-0 twins equal hrd_ref_run."""
    import itertools
    import hrd
    import sweep_hrd
    pair, tf = 'XAU', '240'
    d = os.path.join(W, 'sweep_ah_backup', 'r7')
    sweep_hrd.run_tf_sweep(pair, tf, workers=3, out_dir=d, verbose=False)
    df = pd.read_parquet(os.path.join(d, 'swah_hrd_%s_%s.parquet' % (pair, tf)))
    bad = []
    # (a)
    exp = set()
    for tp in (4.0, 0.0):
        for ec in (5, 20, 100):
            exp.add((False, None, None, tp, ec))
            for a, o in itertools.product(HRD_ACTS, HRD_OFFS):
                exp.add((True, float(a), float(o), tp, ec))
    if len(exp) != 1182:
        bad.append('spec grid has %d settings' % len(exp))
    groups = set(itertools.product(('off', 'on'), ('tv', 'mag'), ('normal', 'rev'), ('tv', 'ours')))
    seen = set()
    if set(df['pair']) != {pair} or set(df['tf']) != {tf}:
        bad.append('pair / tf columns')
    if df.duplicated(['filter', 'path', 'labels', 'cost', 'setting']).any():
        bad.append('duplicate keys')
    for key, g in df.groupby(['filter', 'path', 'labels', 'cost']):
        seen.add(key)
        rows = set()
        for r in g.itertuples():
            rows.add((bool(r.trailOn), None if not r.trailOn else float(r.trailAct),
                      None if not r.trailOn else float(r.trailOff), float(r.InpTpPct), int(r.InpExitCandles)))
            if not r.trailOn and not (math.isnan(r.trailAct) and math.isnan(r.trailOff)):
                bad.append('%s trail-off row %d with trailAct / trailOff' % (key, r.setting))
        dft = g[g['tag'] == 'default']
        if not (len(g) == 1182 and rows == exp and sorted(g['setting']) == list(range(1182)) and len(dft) == 1
                and not dft['trailOn'].iloc[0] and dft['InpTpPct'].iloc[0] == 4.0 and dft['InpExitCandles'].iloc[0] == 5):
            bad.append('group %s: %d rows, %d distinct settings, grid %s, %d default rows'
                       % (key, len(g), len(rows), rows == exp, len(dft)))
        if (g.loc[~g['trailOn'], 'exit_trail'] != 0).any() or (g.loc[g['InpTpPct'] == 0, 'exit_tp'] != 0).any():
            bad.append('group %s: trail exits with the trail off or TP exits with TP 0' % (key,))
    if seen != groups:
        bad.append('groups %s' % sorted(seen ^ groups))
    _p('  (a) %d rows, %d groups x %d settings, keys unique: %s' % (len(df), len(seen), len(exp), 'ok' if not bad else 'BAD'))
    # (b)
    saved = json.load(open(os.path.join(OUT, 'hrd_%s_%s.json' % (pair, tf))))['runs']
    nb = 0
    for flt, lab, cost in itertools.product(('off', 'on'), ('normal', 'rev'), ('tv', 'ours')):
        sv = saved[('rev_' if lab == 'rev' else '') + '%s_%s' % (flt, cost)]
        r = df[(df['tag'] == 'default') & (df['path'] == 'tv') & (df['filter'] == flt) & (df['labels'] == lab)
               & (df['cost'] == cost)].iloc[0]
        for k, v in sv.items():
            if k in ('exits', 'params', 'pair', 'tf', 'w0', 'w1') or k not in df.columns:
                if k == 'exits':
                    for e, x in v.items():
                        nb += 1
                        if r['exit_' + e] != x:
                            bad.append('default %s/%s/%s exit_%s %r vs saved %r' % (flt, lab, cost, e, r['exit_' + e], x))
                continue
            nb += 1
            x = r[k]
            x = None if (isinstance(x, float) and math.isnan(x)) else ('inf' if x == np.inf else x)
            if x != v:
                bad.append('default %s/%s/%s %s %r vs saved %r' % (flt, lab, cost, k, x, v))
    _p('  (b) 8 default tv rows: %d saved fields compared' % nb)
    # (c)
    for flt in ('off', 'on'):
        pn = hrd.prepare(pair, tf, {'fgfOn': flt == 'on'})
        pr = hrd.prepare(pair, tf, {'fgfOn': flt == 'on', 'reverse': True})
        if not (np.array_equal(pn['long_sig'], pr['short_sig']) and np.array_equal(pn['short_sig'], pr['long_sig'])
                and pn['long_sig'].any() and pn['short_sig'].any()
                and not np.array_equal(pn['long_sig'], pn['short_sig'])):
            bad.append('reverse does not swap the signals (filter %s)' % flt)
    num = [c for c in sweep_hrd.SUM_COLS if c not in ('start', 'end', 'bars')]
    for flt, path, cost in itertools.product(('off', 'on'), ('tv', 'mag'), ('tv', 'ours')):
        a = df[(df['filter'] == flt) & (df['path'] == path) & (df['cost'] == cost) & (df['labels'] == 'normal')]
        b = df[(df['filter'] == flt) & (df['path'] == path) & (df['cost'] == cost) & (df['labels'] == 'rev')]
        if a[num].reset_index(drop=True).equals(b[num].reset_index(drop=True)):
            bad.append('rev rows equal normal rows (%s %s %s)' % (flt, path, cost))
    _p('  (c) reverse swaps the signals; rev groups differ from normal groups')
    # (d)
    rng = np.random.default_rng(77)
    get = _hrd_prep_cache()
    subs = None
    nd = 0
    ntr = 0
    for key, g in df.groupby(['filter', 'path', 'labels', 'cost']):
        for i in rng.choice(len(g), 3, replace=False):
            r = g.iloc[int(i)]
            Pp = get(pair, tf, None, None, r['filter'], r['labels'])
            X = dict(path=r['path'], cost=r['cost'], trailOn=bool(r['trailOn']), InpTpPct=float(r['InpTpPct']),
                     InpExitCandles=int(r['InpExitCandles']))
            if r['trailOn']:
                X.update(trailAct=float(r['trailAct']), trailOff=float(r['trailOff']))
            if r['path'] == 'mag' and subs is None:
                subs = _hrd_ref_subbars(Pp)
            ref = hrd_ref_run(Pp, X, subs if r['path'] == 'mag' else None)
            ntr += len(ref)
            for k, v in _hrd_ref_row(Pp, ref).items():
                if not _hrd_close(float(r[k]), float(v), 1e-9, 1e-7):
                    bad.append('row %s setting %d %s: sweep %r reference %r' % (key, r['setting'], k, r[k], v))
            nd += 1
    _p('  (d) %d random rows (%d reference trades) vs hrd_ref_run' % (nd, ntr))
    # (e) on XAU 240 the 4 % target never fills (TP 4 and TP 0 rows are equal), so the InpTpPct column
    # is checked on BTC 240 (tv path, labels normal, cost tv, file in sweep_ah_backup/r7b): no tp exit
    # with TP 0, some with TP 4, and 6 rows with tp exits + their TP-0 twins vs hrd_ref_run
    d2 = os.path.join(W, 'sweep_ah_backup', 'r7b')
    sweep_hrd.run_tf_sweep('BTC', '240', workers=3, paths=('tv',), labels=('normal',), costs=('tv',), out_dir=d2,
                           verbose=False)
    db = pd.read_parquet(os.path.join(d2, 'swah_hrd_BTC_240.parquet'))
    if (db.loc[db['InpTpPct'] == 0, 'exit_tp'] != 0).any() or not (db.loc[db['InpTpPct'] == 4, 'exit_tp'] > 0).any():
        bad.append('BTC 240: tp exits with TP 0 or none with TP 4')
    tp_rows = db[db['exit_tp'] > 0]
    ne = 0
    for i in rng.choice(len(tp_rows), min(6, len(tp_rows)), replace=False):
        r4 = tp_rows.iloc[int(i)]
        tw = db[(db['filter'] == r4['filter']) & (db['trailOn'] == r4['trailOn'])
                & (db['InpExitCandles'] == r4['InpExitCandles']) & (db['InpTpPct'] == 0.0)]
        if r4['trailOn']:
            tw = tw[(tw['trailAct'] == r4['trailAct']) & (tw['trailOff'] == r4['trailOff'])]
        for r in (r4, tw.iloc[0]):
            Pp = get('BTC', '240', None, None, r['filter'], 'normal')
            X = dict(path='tv', cost='tv', trailOn=bool(r['trailOn']), InpTpPct=float(r['InpTpPct']),
                     InpExitCandles=int(r['InpExitCandles']))
            if r['trailOn']:
                X.update(trailAct=float(r['trailAct']), trailOff=float(r['trailOff']))
            for k, v in _hrd_ref_row(Pp, hrd_ref_run(Pp, X)).items():
                if not _hrd_close(float(r[k]), float(v), 1e-9, 1e-7):
                    bad.append('BTC 240 row %s setting %d %s: sweep %r reference %r' % (r['filter'], r['setting'], k, r[k], v))
            ne += 1
    _p('  (e) BTC 240 tv: %d rows with tp exits under TP 4, none under TP 0; %d rows vs hrd_ref_run'
       % (int((db['exit_tp'] > 0).sum()), ne))
    for b in bad[:12]:
        _p('  ' + b)
    return not bad


def test_hrd_R8_sweep_chart1():
    """R8: chart 1 in the sweep: sweep_hrd XAU 1 (labels normal, costs tv / stress, both filters, workers 3;
    file in sweep_ah_backup/r8): the 'mag' rows equal the 'tv' rows on every column, and for 10 random
    settings x both filters x both costs hrd.simulate with path 'mag' on the real 1-minute sub-bars (a
    one-sub-bar-per-bar table, checked) equals those rows on every summary field exactly."""
    import hrd
    import sweep_hrd
    d = os.path.join(W, 'sweep_ah_backup', 'r8')
    sweep_hrd.run_tf_sweep('XAU', '1', workers=3, labels=('normal',), costs=('tv', 'stress'), out_dir=d, verbose=False)
    df = pd.read_parquet(os.path.join(d, 'swah_hrd_XAU_1.parquet'))
    k = ['filter', 'labels', 'cost', 'setting']
    tv = df[df['path'] == 'tv'].set_index(k).sort_index()
    mg = df[df['path'] == 'mag'].set_index(k).sort_index()
    cols = [c for c in df.columns if c not in k + ['path']]
    ok = len(tv) == 2 * 2 * 1182 and len(mg) == len(tv) and tv[cols].equals(mg[cols])
    _p('  XAU 1: %d tv rows, %d mag rows, mag == tv on every column: %s' % (len(tv), len(mg), ok))
    G = sweep_hrd.grid()
    P = {f: hrd.prepare('XAU', '1', {'fgfOn': f == 'on'}) for f in ('off', 'on')}
    sub = hrd.get_sub(P['off'])
    if not np.array_equal(sub[0], np.arange(P['off']['n'] + 1)):
        ok = False
        _p('  sub-bar table is not one per chart bar')
    P['on']['sub'] = sub
    rng = np.random.default_rng(8)
    nd = 0
    for i in rng.choice(len(G), 10, replace=False):
        for f in ('off', 'on'):
            for cost in ('tv', 'stress'):
                s = hrd.summary_fast(P[f], hrd.simulate(P[f], sweep_hrd.exit_params(G[int(i)], 'mag', cost)))
                r = mg.loc[(f, 'normal', cost, int(i))]
                for c in sweep_hrd.SUM_COLS:
                    if not (_hrd_same(float(s[c]), float(r[c]))):
                        ok = False
                        nd += 1
                        if nd < 8:
                            _p('  setting %d %s %s %s: real mag %r vs row %r' % (i, f, cost, c, s[c], r[c]))
    _p('  10 settings x 2 filters x 2 costs: real-sub-bar mag runs equal the rows: %s' % (nd == 0))
    hrd._SIG.clear()
    return ok


def test_hrd_R9_tick_clamps():
    """R9: sub-tick distances: the R2 XAU 60 window with every price (chart bars and 1-minute sub-bars)
    divided by 100 (about 13, so a trail offset below about 0.077 % clamps to 1 tick and activations
    are fractions of a tick): hrd.simulate equals hrd_ref_run trade by trade on 20 random settings each,
    tv and mag, cost tv and stress (the grid's small offsets in more than half the settings)."""
    import hrd
    pair, tf, start, end = HRD_WINDOWS[1]
    rng = np.random.default_rng(9)
    ok_all = True
    tot = {}
    for flt in ('off', 'on'):
        Pp = dict(hrd.prepare(pair, tf, {'fgfOn': flt == 'on', 'start': start, 'end': end}))
        for kk in ('o', 'h', 'l', 'c'):
            Pp[kk] = Pp[kk] / 100.0
        ptr, so, sh, sl_, sc = hrd.sub_bars(pair, tf, Pp['w0'], Pp['w1'])
        Pp['sub'] = (ptr, so / 100.0, sh / 100.0, sl_ / 100.0, sc / 100.0)
        subs = [[(so[s] / 100.0, sh[s] / 100.0, sl_[s] / 100.0, sc[s] / 100.0) for s in range(ptr[k], ptr[k + 1])]
                for k in range(Pp['n'])]
        for i in range(20):
            path = 'mag' if i % 2 else 'tv'
            X = _hrd_random_X(rng, path, 1.0)
            if rng.random() < 0.6:
                X['trailOff'] = float(rng.choice((0.01, 0.02, 0.05)))
            X['cost'] = 'stress' if rng.random() < 0.5 else 'tv'
            R = hrd.simulate(Pp, X)
            ref = hrd_ref_run(Pp, X, subs if path == 'mag' else None)
            ok, msg = _hrd_cmp_ref(R, ref)
            for t in ref:
                tot[t['kind']] = tot.get(t['kind'], 0) + 1
            if not ok:
                ok_all = False
                _p('  FAIL %s %r: %s' % (flt, X, msg))
    _p('  40 settings, exit kinds: %s' % ', '.join('%s %d' % kv for kv in sorted(tot.items())))
    return ok_all and tot.get('trail', 0) > 0


def test_hrd_R4b_half_boundary():
    """R4b: the fair-half split at its boundary: on the R2 BTC 60 and XAU 60 windows, the window end is
    moved so that mid = start + (end - start) // 2 is exactly the entry time (fill bar t_open) of a trade
    (start unchanged, so the trades before the new end are the same); that trade must count in the
    first half (entry_time <= mid): h1_trades / h2_trades and h1r_pct / h2r_pct (summary_fast and run())
    equal a recomputation from run()'s trade list, and the trade is there. 4 settings per pair, tv and mag."""
    import hrd
    ok_all = True
    n_b = 0
    for pair, tf, start, end in HRD_WINDOWS[:2]:
        for X in (dict(trailOn=True, trailAct=0.2, trailOff=0.2, path='tv'),
                  dict(trailOn=True, trailAct=0.0, trailOff=0.1, InpTpPct=0.0, InpExitCandles=20, path='mag', cost='stress'),
                  dict(trailOn=False, path='tv', cost='ours'),
                  dict(trailOn=True, trailAct=1.0, trailOff=0.5, InpExitCandles=100, path='mag')):
            Pp = hrd.prepare(pair, tf, {'fgfOn': False, 'start': start, 'end': end})
            R = hrd.simulate(Pp, X)
            ets = Pp['t_open'][R['ek']]
            T = int(ets[len(ets) // 2])
            end2 = start + 2 * (T - start)
            prm = {'fgfOn': False, 'start': start, 'end': end2}
            tr, s = hrd.run(pair, tf, dict(prm, **X))
            P2 = hrd.prepare(pair, tf, prm)
            sf = hrd.summary_fast(P2, hrd.simulate(P2, X))
            mid = start + (end2 - start) // 2
            first = tr['entry_time'] <= mid
            g1 = float(np.prod(1.0 + tr['pnl'][first] / tr['eq_before'][first]))
            g2 = float(np.prod(1.0 + tr['pnl'][~first] / tr['eq_before'][~first]))
            hit = int((tr['entry_time'] == mid).sum())
            n_b += hit
            for ss, nm in ((s, 'run'), (sf, 'summary_fast')):
                good = (mid == T and hit == 1 and ss['h1_trades'] == int(first.sum())
                        and ss['h2_trades'] == int((~first).sum())
                        and _hrd_close(ss['h1r_pct'], (g1 - 1.0) * 100.0) and _hrd_close(ss['h2r_pct'], (g2 - 1.0) * 100.0))
                if not good:
                    ok_all = False
                    _p('  FAIL %s %s %s %r: mid %d T %d, %d trades at mid, h1 %d vs %d, h1r %r vs %r'
                       % (pair, tf, nm, X, mid, T, hit, ss['h1_trades'], int(first.sum()), ss['h1r_pct'], (g1 - 1.0) * 100.0))
    _p('  8 windows with a trade entering exactly at mid (%d such trades): %s' % (n_b, 'all in half 1' if ok_all else 'WRONG'))
    return ok_all


# =============================================================================================
# runner
# =============================================================================================
def main(argv):
    flt = [a for a in argv if not a.startswith('-')]
    names = sorted(k for k, v in globals().items() if k.startswith('test_') and callable(v))
    if flt:
        names = [k for k in names if any(f in k for f in flt)]
    if not names:
        _p('no tests match %s' % flt)
        return 2
    res = {}
    for k in names:
        _p('== %s: %s' % (k, ' '.join((globals()[k].__doc__ or '').split())))
        t0 = time.time()
        try:
            r = bool(globals()[k]())
        except Exception as e:      # noqa: BLE001
            import traceback
            traceback.print_exc()
            _p('  exception: %r' % (e,))
            r = False
        res[k] = r
        _p('%s %s (%.1fs)' % ('PASS' if r else 'FAIL', k, time.time() - t0))
    _p('\nsummary: %d PASS, %d FAIL' % (sum(res.values()), len(res) - sum(res.values())))
    for k, r in res.items():
        _p('  %s %s' % ('PASS' if r else 'FAIL', k))
    return 0 if all(res.values()) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
