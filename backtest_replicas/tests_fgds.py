"""tests_fgds.py: stage-3 tests of the canonical replica fgds.py (REPLICA_SPEC.md stage 3, SPEC_fgds.md 8 and 13).

Usage: python3 -I tests_fgds.py [T1 T2 ...]      (no argument = all; prints PASS / FAIL, exit 1 on a failure)

T1  A == B == canonical (path 'tv'): fixed cases (default inputs, filter off, inv on with the filter on and off,
    each cost mode, the other two triggers) and random settings (grid + outside the grid) on BTC 60, XAU 60,
    BTC 240, XAU 15, full windows; and 60 x 8 synthetic-grid cases (fgds_synth.py: exact ties on the levels)
T2  path 'mag' on chart "1" == 'tv' (BTC 1, XAU 1, full windows, 9 settings each)
T3  path 'mag' with one fake sub-bar per chart bar (each sub-bar = the chart bar) == 'tv'
T4  path 'mag' (and 'tv') against the slow pure-Python reference fgds_ref.py: 30 random settings over random
    2-month windows of real data with the real 1-minute sub-bars; 40 x 6 synthetic cases (1..6 sub-bars per bar)
T5  fair halves, every cost mode and every summary field against a direct recomputation from the trade list
    and the chart closes (bar-close equity, drawdown, halves, exposure, costs, P/L, eq_before, R)
T6  the inv properties of SPEC_fgds 8 (P1-P9) and the header properties (i)-(iv) of SPEC_fgds 13
T7  hand-built bars for 'mag': the sub-bars decide which level is met first; a gap between two sub-bars through
    the stop; the trailing stop across sub-bars; a trade filled at the open stopped in a later sub-bar
T8  the 1-minute sub-bars rebuild every chart bar of the 12 cells above "1" (open / high / low / close)
T9  timing: one simulate on BTC "1" (tv and mag) well under 1 s after compilation; prepare under 2 minutes
"""
import math
import os
import random
import resource
import sys
import time

import numpy as np

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import fgf  # noqa: E402
import fgds as M  # noqa: E402
import fgds_a as A  # noqa: E402
import fgds_b as B  # noqa: E402
import fgds_cases as G  # noqa: E402
import fgds_ref as REF  # noqa: E402
import fgds_synth as S  # noqa: E402

NPASS = 0
NFAIL = 0
FAILS = []
TIMING = {}


def check(name, ok, info=''):
    global NPASS, NFAIL
    if ok:
        NPASS += 1
        print('PASS %s %s' % (name, info), flush=True)
    else:
        NFAIL += 1
        FAILS.append(name)
        print('FAIL %s %s' % (name, info), flush=True)


_PC = {}


def get_P(pair, tf, **fp):
    key = (pair, tf, tuple(sorted(fp.items())))
    if key not in _PC:
        t0 = time.time()
        _PC[key] = M.prepare(pair, tf, fp)
        TIMING['prepare %s %s %s' % (pair, tf, fp or '')] = time.time() - t0
    return _PC[key]


def free():
    _PC.clear()
    M.clear_cache()
    fgf._FILTER.clear()


def run(P, x, sub=None, full=False):
    R = M.simulate(P, dict(x), full=full, sub=sub)
    return M.trades(P, R), M.summary(P, R), R


def same(ta, tb, sa=None, sb=None):
    ok, msg, _ = G.cmp_trades(ta, tb)
    if sa is not None:
        ok2, msg2 = G.cmp_summary(sa, sb)
        ok = ok and ok2
        msg = msg + ' ' + msg2
    return ok, msg


# ================================================================================================
def t1():
    print('\n=== T1: A == B == canonical (path tv) ===')
    mods = (('fgds_a', A), ('fgds_b', B), ('fgds', M))
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '240'), ('XAU', '15')):
        cases = G.fixed_cases() + G.random_settings(pair, tf, 8, 8, 7)
        nbad = 0
        ntr = 0
        for prep, sims in G.group_by_prep(cases):
            Ps = {nm: mod.prepare(pair, tf, prep) for nm, mod in mods}
            for lab, sim in sims:
                out = {}
                for nm, mod in mods:
                    R = mod.simulate(Ps[nm], dict(sim), full=True)
                    out[nm] = (mod.trades(Ps[nm], R), mod.summary(Ps[nm], R), R)
                ta, sa, Ra = out['fgds']
                ntr += len(ta)
                for nm in ('fgds_a', 'fgds_b'):
                    tb, sb, Rb = out[nm]
                    ok1, m1, _ = G.cmp_trades(ta, tb)
                    ok2, m2 = G.cmp_summary(sa, sb)
                    ok3, m3 = G.cmp_arrays(Ra, Rb)
                    if not (ok1 and ok2 and ok3):
                        nbad += 1
                        print('   differs: %s %s %s vs fgds: %s %s %s' % (lab, G.fmt_setting(prep, sim), nm, m1, m2,
                                                                       m3))
            fgf._FILTER.clear()
        check('T1 A == B == canonical %s %s' % (pair, tf), nbad == 0,
              '(%d cases, %d trades each)' % (len(cases), ntr))
    # synthetic grid
    nbad = 0
    ntr = 0
    for seed in range(60):
        D = S.make(1000 + seed)
        rng = random.Random('t1|%d' % seed)
        for k in range(8):
            x = S.random_sim(rng)
            pair = rng.choice(['XAU', 'BTC'])
            out = {}
            for nm, mod in mods:
                P = S.P_for(nm, D, pair)
                R = mod.simulate(P, dict(x), full=True)
                out[nm] = (mod.trades(P, R), mod.summary(P, R), R)
            ta, sa, Ra = out['fgds']
            ntr += len(ta)
            for nm in ('fgds_a', 'fgds_b'):
                tb, sb, Rb = out[nm]
                if not (G.cmp_trades(ta, tb)[0] and G.cmp_summary(sa, sb)[0] and G.cmp_arrays(Ra, Rb)[0]):
                    nbad += 1
    check('T1 A == B == canonical, synthetic grid bars', nbad == 0, '(480 cases, %d trades)' % ntr)


# ================================================================================================
SETTINGS_1M = [
    {}, {'inv': True}, {'cost': 'ours'}, {'cost': 'stress', 'inv': True},
    {'dsTpR': 0.0, 'dsUseTrail': True, 'dsTrActAtr': 13.0, 'dsTrDstAtr': 6.5},
    {'dsExitMode': 'Points', 'dsSlPoints': 3000.0, 'dsTpPoints': 0.0, 'dsUseTrail': True, 'dsTrActPts': 1000.0,
     'dsTrPts': 500.0, 'inv': True},
    {'dsTrigger': 'Signal confirmed'}, {'dsTrigger': 'New signal', 'inv': True, 'dsTimeStop': 3},
    {'dsZoneExit': False, 'dsReverse': False, 'dsSlAtr': 0.5, 'dsTpR': 1.5},
]


def t2():
    print('\n=== T2: mag on chart "1" == tv ===')
    for pair in ('BTC', 'XAU'):
        P = get_P(pair, '1')
        sub = M.get_sub(P)
        check('T2 %s 1: one sub-bar per chart bar, equal to it' % pair,
              len(sub[1]) == P['n'] and np.array_equal(sub[0], np.arange(P['n'] + 1))
              and np.array_equal(sub[1], P['o']) and np.array_equal(sub[4], P['c']))
        for x in SETTINGS_1M:
            ta, sa, _ = run(P, dict(x, path='tv'))
            tb, sb, _ = run(P, dict(x, path='mag'))
            ok, msg = same(ta, tb, sa, sb)
            check('T2 %s 1 mag == tv %s' % (pair, x), ok, '(%d trades) %s' % (len(ta), msg if not ok else ''))
        free()


# ================================================================================================
def t3():
    print('\n=== T3: mag with one fake sub-bar per chart bar == tv ===')
    for pair, tf in (('BTC', '60'), ('XAU', '15'), ('BTC', '5'), ('XAU', '240')):
        P = get_P(pair, tf)
        fake = M.fake_sub_bars(P)
        xs = [dict(inv=inv, cost=cost) for inv in (False, True) for cost in ('tv', 'ours', 'stress')]
        xs += [dict(dsTrigger=t, inv=inv) for t in ('Signal confirmed', 'New signal') for inv in (False, True)]
        xs += [s for _, p, s in G.random_settings(pair, tf, 6, 6, 3)]
        nbad = 0
        for x in xs:
            ta, sa, _ = run(P, dict(x, path='tv'))
            tb, sb, _ = run(P, dict(x, path='mag'), sub=fake)
            if not same(ta, tb, sa, sb)[0]:
                nbad += 1
        check('T3 %s %s fake sub-bars mag == tv' % (pair, tf), nbad == 0, '(%d settings)' % len(xs))
        tv = run(P, {'path': 'tv'})[0]
        mg = run(P, {'path': 'mag'})[0]
        print('   (real 1-minute sub-bars, default inputs: tv %d trades, mag %d trades, %d trades differ in exit '
              'price or kind)' % (len(tv), len(mg), int(((tv.exit_px.to_numpy() != mg.exit_px.to_numpy())
                                                         | (tv.exit_kind.to_numpy() != mg.exit_kind.to_numpy())).sum())
                                  if len(tv) == len(mg) else -1))
    free()


# ================================================================================================
def t4():
    print('\n=== T4: mag / tv against the pure-Python reference fgds_ref.py ===')
    rng = random.Random(20261126)
    cells = [(p, t) for p in ('BTC', 'XAU') for t in ('5', '15', '30', '60', '120', '240')]
    two_months = 61 * 86400
    nmag_diff = 0
    i = 0
    tries = 0
    while i < 30:
        tries += 1
        pair, tf = rng.choice(cells)
        s0, e0 = M.WINDOWS[pair]
        st = rng.randint(s0, e0 - two_months)
        lab, prep, sim = rng.choice(G.random_settings(pair, tf, 4, 4, 100 + tries))
        prep = dict(prep, start=st, end=st + two_months)
        P = M.prepare(pair, tf, prep)
        if len(run(P, dict(sim, path='tv'))[0]) < 5:
            fgf._FILTER.clear()
            continue                       # a setting without trades in that window proves nothing: draw again
        res = {}
        for path in ('mag', 'tv'):
            x = dict(sim, path=path)
            tc, sc, R = run(P, x, full=True)
            tr, sr, er = REF.run_ref(P, x)
            ok1, m1, _ = G.cmp_trades(tc, tr)
            ok2 = G._feq(np.asarray(R['eq'])[:-1], er[:-1]).all() and bool(
                G._feq(sc['final_equity'], sr['final_equity']))
            res[path] = tc
            check('T4 #%02d %s %s %s vs reference' % (i, pair, tf, path), ok1 and ok2,
                  '(%d trades, %s)%s' % (len(tc), ', '.join('%s %d' % kv for kv in sorted(
                      tc.exit_kind.value_counts().items())), '' if ok1 and ok2 else ' ' + m1 + ' | ' +
                      G.fmt_setting(prep, sim)))
        if not G.cmp_trades(res['mag'], res['tv'])[0]:
            nmag_diff += 1
        fgf._FILTER.clear()
        i += 1
    print('   %d draws for 30 windows with at least 5 trades' % tries)
    print('   mag differs from tv in %d of the 30 windows' % nmag_diff)
    check('T4 the comparison is not vacuous (mag != tv somewhere)', nmag_diff > 0, '(%d of 30)' % nmag_diff)
    nbad = 0
    ntr = 0
    ndiff = 0
    for seed in range(40):
        D = S.make(5000 + seed)
        r2 = random.Random('t4|%d' % seed)
        for k in range(6):
            x = S.random_sim(r2)
            pair = r2.choice(['XAU', 'BTC'])
            P = S.P_for('fgds', D, pair)
            out = {}
            for path in ('mag', 'tv'):
                xx = dict(x, path=path)
                tc, sc, R = run(P, xx, full=True)
                tr, sr, er = REF.run_ref(P, xx)
                ntr += len(tc)
                out[path] = tc
                if not (G.cmp_trades(tc, tr)[0] and G._feq(np.asarray(R['eq'])[:-1], er[:-1]).all()):
                    nbad += 1
            ndiff += not G.cmp_trades(out['mag'], out['tv'])[0]
    check('T4 synthetic sub-bars: mag and tv == reference', nbad == 0,
          '(240 cases x 2 paths, %d trades; mag != tv in %d cases)' % (ntr, ndiff))
    free()


# ================================================================================================
FEE = {('tv', 'XAU'): (0.0, 0.0), ('tv', 'BTC'): (0.0, 0.0),
       ('ours', 'XAU'): (0.30 / 2, 0.0), ('ours', 'BTC'): (0.20 / 2, 0.0002),
       ('stress', 'XAU'): (0.50 / 2 + 0.01, 0.0), ('stress', 'BTC'): (0.20 / 2 + 0.01, 0.00035)}


def recompute(P, T, x):
    """Every summary field from the trade list and the chart closes alone."""
    n, w0, c = P['n'], P['w0'], P['c']
    cost = x.get('cost', 'tv')
    fix, pct = FEE[(cost, P['pair'])]
    d = T['dir'].to_numpy()
    q = T['qty'].to_numpy()
    e = T['entry_px'].to_numpy()
    xp = T['exit_px'].to_numpy()
    ek = T['entry_bar'].to_numpy() - w0
    xk = T['exit_bar'].to_numpy() - w0
    kind = T['exit_kind'].to_numpy()
    ec = q * (fix + pct * e)
    xc = q * (fix + pct * xp)
    gross = d * q * (xp - e)
    pnl = gross - ec - xc
    out = {}
    out['costs_ok'] = bool(G._feq(T['costs'].to_numpy(), ec + xc).all())
    out['pnl_ok'] = bool(G._feq(T['pnl'].to_numpy(), pnl).all() and G._feq(T['pnl_gross'].to_numpy(), gross).all())
    eqb = 10000.0 + np.concatenate([[0.0], np.cumsum(pnl)[:-1]]) if len(T) else np.zeros(0)
    out['eqb_ok'] = bool(G._feq(T['eq_before'].to_numpy(), eqb).all())
    delta = np.zeros(n)
    np.add.at(delta, ek, -ec)
    np.add.at(delta, xk, gross - xc)
    cash = 10000.0 + np.cumsum(delta)
    opl = np.zeros(n)
    inpos = np.zeros(n, bool)
    for i in range(len(T)):
        hi = xk[i] + 1 if kind[i] == 'end' else xk[i]
        if hi > ek[i]:
            sl_ = slice(ek[i], hi)
            opl[sl_] += d[i] * q[i] * (c[sl_] - e[i])
            inpos[sl_] = True
    E = cash + opl
    final = 10000.0 + pnl.sum()
    E[n - 1] = final           # the last point of the curve is the final equity (after the 'end' close)
    curve = np.concatenate([[10000.0], E[:n - 1], [final]])
    pk = np.maximum.accumulate(curve)
    out['E'] = E
    out['final_equity'] = final
    out['net_pct'] = (final - 10000.0) / 100.0
    out['max_dd_pct'] = float(((pk - curve) / pk).max() * 100)
    out['max_dd_init_pct'] = float((pk - curve).max() / 100.0)
    mid = P['mid']
    mj = P['mid_j']
    em = 10000.0 if mj < 0 else (final if mj == n - 1 else E[mj])
    out['half1_pct'] = (em - 10000.0) / 100.0
    out['half2_pct'] = (final - em) / 100.0
    out['exposure'] = inpos.sum() / n
    first = T['entry_time'].to_numpy() <= mid
    g = 1.0 + pnl / eqb if len(T) else np.zeros(0)
    out['h1r_pct'] = (np.prod(g[first]) - 1.0) * 100.0
    out['h2r_pct'] = (np.prod(g[~first]) - 1.0) * 100.0
    out['h1_trades'] = int(first.sum())
    out['h2_trades'] = int((~first).sum())
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    out['pf'] = gp / gl if gl > 0 else (np.inf if gp > 0 else np.nan)
    out['win_pct'] = (pnl > 0).mean() * 100 if len(T) else np.nan
    out['trades'] = len(T)
    out['long'] = int((d > 0).sum())
    out['short'] = int((d < 0).sum())
    for k in M.KINDS[1:]:
        out['exit_' + k] = int((kind == k).sum())
    out['avg_bars_held'] = float((xk - ek).mean()) if len(T) else np.nan
    out['zero_length'] = int((xk == ek).sum())
    out['costs'] = float((ec + xc).sum())
    sld = T['sl_dist'].to_numpy()
    with np.errstate(divide='ignore', invalid='ignore'):
        rm = np.where(sld > 0, pnl / (sld * q), np.nan)
    out['net_r'] = float(np.nansum(rm))
    out['h1_r'] = float(np.nansum(rm[first]))
    out['h2_r'] = float(np.nansum(rm[~first]))
    out['margin_over'] = int((q * e * 0.01 > eqb).sum())
    return out


def t5():
    print('\n=== T5: summaries against a direct recomputation from the trade list ===')
    keys = ('final_equity', 'net_pct', 'max_dd_pct', 'max_dd_init_pct', 'half1_pct', 'half2_pct', 'exposure',
            'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades', 'pf', 'win_pct', 'trades', 'long', 'short',
            'avg_bars_held', 'zero_length', 'costs', 'net_r', 'h1_r', 'h2_r', 'margin_over') + tuple(
        'exit_' + k for k in M.KINDS[1:])
    for pair, tf in (('BTC', '60'), ('XAU', '15'), ('XAU', '60'), ('BTC', '240')):
        P = get_P(pair, tf)
        xs = []
        for cost in ('tv', 'ours', 'stress'):
            for inv in (False, True):
                for path in ('tv', 'mag'):
                    xs.append(dict(cost=cost, inv=inv, path=path))
        xs += [dict(s, path='mag') for _, p, s in G.random_settings(pair, tf, 0, 8, 11) if not p]
        xs += [dict(dsTrigger='New signal', dsTimeStop=4, cost='stress', inv=True, path='mag'),
               dict(dsTrigger='Signal confirmed', dsUseTrail=True, dsTpR=0.0, cost='ours', path='mag')]
        for x in xs:
            T, s, R = run(P, x, full=True)
            r = recompute(P, T, x)
            bad = [k for k in keys if not G._feq(np.float64(s[k]), np.float64(r[k]))]
            okE = bool(G._feq(np.asarray(R['eq'])[:-1], r['E'][:-1]).all())
            ok = r['costs_ok'] and r['pnl_ok'] and r['eqb_ok'] and okE and not bad
            check('T5 %s %s %s' % (pair, tf, x), ok,
                  '(%d trades; h1r %.2f h2r %.2f)%s' % (len(T), s['h1r_pct'], s['h2r_pct'],
                                                        '' if ok else ' bad: %s costs %s pnl %s eqb %s E %s' % (
                                                            bad, r['costs_ok'], r['pnl_ok'], r['eqb_ok'], okE)))
    free()


# ================================================================================================
def mirror_ok(tn, ti):
    if len(tn) != len(ti):
        return False, '%d vs %d trades' % (len(tn), len(ti))
    for col in ('sig', 'sig_bar', 'entry_bar', 'exit_bar', 'entry_time', 'exit_time', 'entry_px', 'exit_px', 'qty',
                'rev', 'capf', 'sl_dist'):
        if not np.array_equal(tn[col].to_numpy(), ti[col].to_numpy()):
            return False, 'column %s' % col
    if not np.array_equal(tn['dir'].to_numpy(), -ti['dir'].to_numpy()):
        return False, 'dir'
    sw = {'sl': 'tp', 'tp': 'sl'}
    if [sw.get(k, k) for k in tn['exit_kind']] != list(ti['exit_kind']):
        return False, 'exit_kind'
    for col in ('pnl', 'pnl_gross', 'r_mult'):
        if not G._feq(tn[col].to_numpy(), -ti[col].to_numpy()).all():
            return False, col
    if not (G._feq(tn['sl_px'].to_numpy(), ti['tp_px'].to_numpy()).all()
            and G._feq(tn['tp_px'].to_numpy(), ti['sl_px'].to_numpy()).all()):
        return False, 'sl_px <-> tp_px'
    if not G._feq(tn['eq_before'].to_numpy() - 1e4, -(ti['eq_before'].to_numpy() - 1e4)).all():
        return False, 'eq_before'
    return True, '%d trades' % len(tn)


def dsqty(x, equity, close, stop_dist):
    q = x.get('dsFixedQty', 1.0)
    if x.get('dsQtyMode', 'Risk %') == 'Risk %':
        q = equity * x.get('dsRiskPct', 0.5) / 100.0 / stop_dist if stop_dist > 0 else 0.0
    q = min(q, x.get('dsMaxQty', 50.0))
    if x.get('dsCapMargin', True) and x.get('dsMarginPct', 1.0) > 0:
        q = min(q, equity / (close * x.get('dsMarginPct', 1.0) / 100.0))
    st = x.get('dsQtyStep', 0.001)
    return math.floor(q / st + 1e-9) * st


def header_props(P, x, T, R):
    """(i) zone exits, (ii) levels, (iii) qty, (iv) time exits. Returns a list of failures."""
    bad = []
    trig = x.get('dsTrigger', 'Zone start')
    rb, rs, kb, ks = M.trigger_arrays(P, trig)
    w0 = P['w0']
    L_ = x.get('dsAtrLen', 14)
    atr = M.atr_window(P, L_)
    r = recompute(P, T, x)
    E = r['E']
    points = x.get('dsExitMode', 'ATR') == 'Points'
    for row in T.itertuples():
        k, xk, s = row.entry_bar - w0, row.exit_bar - w0, row.sig_bar - w0
        keep = kb if row.sig > 0 else ks
        if s != k - 1:
            bad.append('sig_bar')
        if not (rb[s] if row.sig > 0 else rs[s]):
            bad.append('trigger at sig_bar')
        if row.exit_kind == 'zone':                                    # (i)
            if keep[xk - 1] or not keep[k:xk - 1].all():
                bad.append('(i) zone exit at %d' % row.exit_bar)
        if points:                                                     # (ii)
            slT, tpT = x.get('dsSlPoints', 1000.0), x.get('dsTpPoints', 3000.0)
        else:
            slT = 0.0 if np.isnan(atr[s]) else x.get('dsSlAtr', 1.0) * atr[s] / 0.01
            tpT = slT * x.get('dsTpR', 3.0)
        slp = row.entry_px - row.dir * (slT * 0.01) if slT > 0 else np.nan
        tpp = row.entry_px + row.dir * (tpT * 0.01) if tpT > 0 else np.nan
        if not (G._feq(slp, row.sl_px) and G._feq(tpp, row.tp_px)):
            bad.append('(ii) levels at %d' % row.entry_bar)
        # (iii): the equity rebuilt here may differ from the kernel's in the last bit (summation order), which can
        # move the floor only when q / step sits on an integer: accept the quantity of either bound
        qs = {dsqty(x, E[s] * (1 + f), P['c'][s], slT * 0.01) for f in (-1e-12, 0.0, 1e-12)}
        if not any(G._feq(q, row.qty, 1e-12) for q in qs):
            bad.append('(iii) qty at %d: %r vs %r' % (row.entry_bar, sorted(qs), row.qty))
        if row.exit_kind == 'time' and xk - k != x.get('dsTimeStop', 0) + 1:   # (iv)
            bad.append('(iv) time exit at %d' % row.exit_bar)
    return bad


def t6():
    print('\n=== T6: inv properties P1-P9 and header properties (i)-(iv) ===')
    # P1, exact mirror
    sym = []
    for trig in ('Zone start', 'Signal confirmed', 'New signal'):
        for ze in (True, False):
            for rv in (True, False):
                for ts in (0, 3):
                    base = dict(dsTrigger=trig, dsZoneExit=ze, dsReverse=rv, dsTimeStop=ts, dsQtyMode='Fixed',
                                dsCapMargin=False, dsSides='Both', cost='tv', dsUseTrail=False)
                    sym.append(dict(base, dsTpR=1.0, dsFixedQty=0.01))
                    sym.append(dict(base, dsExitMode='Points', dsSlPoints=1500.0, dsTpPoints=1500.0, dsFixedQty=0.02))
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('XAU', '15'), ('BTC', '240')):
        P = get_P(pair, tf)
        for path in ('tv', 'mag'):
            nbad = 0
            ntr = 0
            first_bad = ''
            for x in sym:
                tn = run(P, dict(x, inv=False, path=path))[0]
                ti = run(P, dict(x, inv=True, path=path))[0]
                ok, msg = mirror_ok(tn, ti)
                ntr += len(tn)
                if not ok:
                    nbad += 1
                    first_bad = first_bad or '%s: %s' % (x, msg)
            check('T6 P1 exact mirror %s %s %s' % (pair, tf, path), nbad == 0,
                  '(%d settings, %d trades)%s' % (len(sym), ntr, ' ' + first_bad if nbad else ''))
    # P2, 5 single decisions through _decide: the same state with the position negated
    P = get_P('BTC', '60')
    for trig in ('Zone start', 'Signal confirmed'):
        rb, rs, kb, ks = M.trigger_arrays(P, trig)
        atr = M.atr_window(P, 14)
        rng = random.Random(5)
        picks = rng.sample([int(j) for j in np.flatnonzero(rb | rs)], 5)
        good = True
        for j in picks:
            for pos, prev, eb in ((0, 0, -1), (1, 1, j - 2), (-1, -1, j - 3), (1, 0, j), (-1, 1, j)):
                outs = []
                for inv, p, pp in ((False, pos, prev), (True, -pos, -prev)):
                    a = M.kernel_args(M.resolve(P, {'inv': inv, 'dsTrigger': trig, 'dsTimeStop': 2}))
                    outs.append(M._decide(j, p, pp, eb, 10432.5, P['c'][j], atr[j], rb[j], rs[j], kb[j], ks[j],
                                          *a[:10], *a[11:], 0.01, 1.0))
                n_, i_ = outs
                good &= (n_[0] == -i_[0] and n_[1] == i_[1] and n_[2:8] == i_[2:8] and n_[8] == i_[8]
                         and n_[9] == i_[9])
                if pos == 0 or (pos == 1 and prev == 1):
                    print('   %s bar %d: rb %d rs %d keepB %d keepS %d | normal pos %+d: order %+d sig %+d q %.3f slT '
                          '%.1f close %s | inverted pos %+d: order %+d sig %+d q %.3f slT %.1f close %s' % (
                              trig, j + P['w0'], rb[j], rs[j], kb[j], ks[j], pos, n_[0], n_[1], n_[2], n_[3],
                              M.KINDS[n_[8]] or '-', -pos, i_[0], i_[1], i_[2], i_[3], M.KINDS[i_[8]] or '-'))
        check('T6 P2 single decisions, %s (5 bars x 5 states)' % trig, good)
    # P3, P8, P9 and the header properties on the default and on a few others, both paths
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '5'), ('XAU', '15')):
        P = get_P(pair, tf)
        for path in ('tv', 'mag'):
            tn, sn, _ = run(P, {'path': path})
            ti, si, _ = run(P, {'path': path, 'inv': True})
            check('T6 P3 first trade %s %s %s' % (pair, tf, path),
                  tn.entry_bar[0] == ti.entry_bar[0] and tn.entry_px[0] == ti.entry_px[0] and tn.qty[0] == ti.qty[0]
                  and tn.dir[0] == -ti.dir[0])
            okp8 = all(s['zero_qty'] == 0 and s['trades'] == s['raw_long'] + s['raw_short'] - s['orders_unfilled_end']
                       for s in (sn, si))
            check('T6 P8 Zone start: every trigger trades %s %s %s' % (pair, tf, path), okp8,
                  '(%d / %d trades, %d + %d triggers)' % (sn['trades'], si['trades'], sn['raw_long'], sn['raw_short']))
            nrev = 0
            nopp = 0
            for trig in ('Zone start', 'Signal confirmed', 'New signal'):
                for inv in (False, True):
                    s = run(P, {'path': path, 'inv': inv, 'dsTrigger': trig, 'dsReverse': False})[1]
                    nrev += s['exit_reverse']
                    nopp += s['exit_opp']
            check('T6 P9 dsReverse off: no reverse exit %s %s %s' % (pair, tf, path), nrev == 0,
                  '(3 triggers x 2 directions: %d reverse, %d opp)' % (nrev, nopp))
    hx = [{}, {'inv': True}, {'dsTimeStop': 3, 'inv': True, 'cost': 'ours'},
          {'dsTrigger': 'Signal confirmed', 'dsTimeStop': 2, 'cost': 'stress'},
          {'dsTrigger': 'New signal', 'dsTimeStop': 5, 'inv': True},
          {'dsExitMode': 'Points', 'dsSlPoints': 800.0, 'dsTpPoints': 2400.0, 'dsTimeStop': 4, 'dsSides': 'Long only'},
          {'dsSlAtr': 2.0, 'dsTpR': 0.0, 'dsUseTrail': True, 'dsTrActAtr': 2.0, 'dsTrDstAtr': 1.0, 'inv': True,
           'dsZoneExit': False},
          {'dsRiskPct': 3.0, 'dsMaxQty': 1e9, 'cost': 'ours', 'dsTimeStop': 6}]
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '5'), ('XAU', '15')):
        P = get_P(pair, tf)
        for path in ('tv', 'mag'):
            bad = []
            n = 0
            kinds = {}
            for x in hx:
                T, s, R = run(P, dict(x, path=path), full=True)
                n += len(T)
                for k, v in T.exit_kind.value_counts().items():
                    kinds[k] = kinds.get(k, 0) + int(v)
                bad += header_props(P, x, T, R)
            check('T6 header (i)-(iv) %s %s %s' % (pair, tf, path), not bad,
                  '(%d settings, %d trades: %s)%s' % (len(hx), n, ', '.join('%s %d' % kv for kv in sorted(kinds.items())),
                                                      ' ' + '; '.join(bad[:5]) if bad else ''))
    # P4 filter off; P5 Sides; P6 Signal confirmed; P7 New signal
    for pair in ('BTC', 'XAU'):
        P0 = get_P(pair, '60', fgfOn=False)
        ok = not any(P0[k].any() for k in ('buyEdge', 'sellEdge', 'confEdgeB', 'confEdgeS', 'newBuy', 'newSell'))
        for trig in ('Zone start', 'Signal confirmed', 'New signal'):
            for inv in (False, True):
                for path in ('tv', 'mag'):
                    s = run(P0, {'dsTrigger': trig, 'inv': inv, 'path': path})[1]
                    ok &= s['trades'] == 0 and s['net_pct'] == 0.0
        check('T6 P4 filter off: no trigger, no trade %s 60' % pair, bool(ok))
        P = get_P(pair, '60')
        for sides, d in (('Long only', 1), ('Short only', -1)):
            for inv in (False, True):
                T, s, _ = run(P, {'dsSides': sides, 'inv': inv})
                sg = -d if inv else d
                check('T6 P5 %s %s inv %s' % (pair, sides, inv),
                      len(T) > 0 and (T['dir'] == d).all() and (T['sig'] == sg).all() and s['exit_reverse'] == 0
                      and s['exit_opp'] > 0, '(%d trades, %d opp)' % (len(T), s['exit_opp']))
        Pa = get_P(pair, '60', fgfAgainst=False)
        for inv in (False, True):
            T, s, _ = run(P, {'dsTrigger': 'Signal confirmed', 'inv': inv})
            sd = P['sigDir'][T['sig_bar'].to_numpy() - P['w0']]
            ok = (T['sig'].to_numpy() == sd).all() and (T['dir'].to_numpy() == (-1 if inv else 1) * T['sig'].to_numpy()).all()
            Ta = run(Pa, {'dsTrigger': 'Signal confirmed', 'inv': inv})[0]
            check('T6 P6 Signal confirmed %s inv %s: sig == sigDir, dir rule, independent of fgfAgainst' % (pair, inv),
                  bool(ok) and G.cmp_trades(T, Ta)[0], '(%d trades)' % len(T))
        base = {inv: run(P, {'dsTrigger': 'New signal', 'inv': inv})[0] for inv in (False, True)}
        ok = True
        for fp in ({'fgfBandAtr': 0.75}, {'fgfLvMode': 'Signal close'}, {'fgfAgainst': False}, {'fgfAllowBuy': False},
                   {'fgfAllowSell': False}, {'fgfLast': 'Candles', 'fgfBars': 1}):
            P7 = get_P(pair, '60', **fp)
            for inv in (False, True):
                ok &= G.cmp_trades(base[inv], run(P7, {'dsTrigger': 'New signal', 'inv': inv})[0])[0]
        for inv in (False, True):
            ok &= G.cmp_trades(base[inv], run(P, {'dsTrigger': 'New signal', 'inv': inv, 'dsZoneExit': False})[0])[0]
        check('T6 P7 New signal independent of band / level / against / allow / last / zone exit %s 60' % pair,
              bool(ok), '(%d / %d trades)' % (len(base[False]), len(base[True])))
        free()


# ================================================================================================
def _hand(chart, subs, rb=(), rs=(), **x):
    """Chart bars from sub-bars [(o, h, l, c), ...] per chart bar; triggers at the given bars; Points mode."""
    n = len(subs)
    ptr = np.zeros(n + 1, np.int64)
    ptr[1:] = np.cumsum([len(s) for s in subs])
    flat = [b for s in subs for b in s]
    so, sh, sl, sc = (np.array([b[i] for b in flat], np.float64) for i in range(4))
    o = np.array([s[0][0] for s in subs])
    c = np.array([s[-1][3] for s in subs])
    h = np.array([max(b[1] for b in s) for s in subs])
    l_ = np.array([min(b[2] for b in s) for s in subs])
    assert chart is None or np.allclose(np.c_[o, h, l_, c], np.array(chart))
    R0 = np.zeros(n, np.bool_)
    rbA, rsA = R0.copy(), R0.copy()
    rbA[list(rb)] = True
    rsA[list(rs)] = True
    kb = np.ones(n, np.bool_)
    ks = np.ones(n, np.bool_)
    P = dict(o=o, h=h, l=l_, c=c, sim=dict(M.SIM_DEFAULTS), prep=dict(M.PREP_DEFAULTS))
    out = {}
    for path in ('tv', 'mag'):
        Q = M.resolve(P, dict(x, path=path, dsExitMode='Points', dsQtyMode='Fixed', dsFixedQty=1.0,
                              dsCapMargin=False))
        R = M.run_arrays(o, h, l_, c, rbA, rsA, kb, ks, np.full(n, 1.0), Q, 'XAU', -1, False,
                         (ptr, so, sh, sl, sc) if path == 'mag' else None)
        out[path] = [(int(R['dir'][i]), int(R['ek'][i]), int(R['xk'][i]), round(float(R['epx'][i]), 9),
                      round(float(R['xpx'][i]), 9), M.KINDS[int(R['kind'][i])]) for i in range(len(R['dir']))]
    return out


def t7():
    print('\n=== T7: hand-built sub-bars (path mag) ===')
    flat = [(100.0, 100.0, 100.0, 100.0)]
    # (a) chart bar 2 = O 100 H 103 L 97 C 100 (tie: tv walks O-L-H-C, the stop first); the sub-bars rise to
    # 103 first: the target at 102 fills before the stop at 98
    r = _hand(None, [flat, flat, [(100.0, 103.0, 100.0, 103.0), (103.0, 103.0, 97.0, 97.0), (97.0, 100.0, 97.0, 100.0)],
                     flat], rb=[0], dsSlPoints=200.0, dsTpPoints=200.0)
    check('T7a sub-bars decide which level comes first (long: tv sl at 98, mag tp at 102)',
          r['tv'] == [(1, 1, 2, 100.0, 98.0, 'sl')] and r['mag'] == [(1, 1, 2, 100.0, 102.0, 'tp')], repr(r))
    # (b) a gap between two sub-bars through the stop: the stop fills at the later sub-bar's open (97.0), not at
    # the stop (98.0); on tv the chart bar O 100 H 100.5 L 96.5 C 97 falls through 98 on its path: 98.0
    r = _hand(None, [flat, flat, [(100.0, 100.5, 99.5, 100.0), (97.0, 97.5, 96.5, 97.0)], flat], rb=[1],
              dsSlPoints=200.0, dsTpPoints=0.0)
    check('T7b gap between sub-bars through the stop fills at the sub-bar open',
          r['mag'] == [(1, 2, 2, 100.0, 97.0, 'sl')] and r['tv'] == [(1, 2, 2, 100.0, 98.0, 'sl')], repr(r))
    # (c) a short: the trailing stop arms in one sub-bar and is hit in a later one; trail act 200 ticks (2.00),
    # offset 100 (1.00), no stop / target. Fill 100 (bar 1 open). Bar 1 sub-bars: 100 -> 97.5 (armed at 98,
    # best 97.5), then 97.5 .. 99 (stop 98.5 hit at 98.5). tv on the chart bar O 100 H 99.? path decides
    sb = [(100.0, 100.0, 97.5, 97.5), (97.5, 99.0, 97.5, 99.0), (99.0, 99.0, 99.0, 99.0)]
    r = _hand(None, [flat, sb, flat], rs=[0], dsSlPoints=0.0, dsTpPoints=0.0, dsUseTrail=True, dsTrActPts=200.0,
              dsTrPts=100.0)
    check('T7c short: trailing stop armed in one sub-bar, hit in a later one at best + offset',
          r['mag'] == [(-1, 1, 1, 100.0, 98.5, 'trail')], repr(r))
    # (d) trail state carries over chart bars and sub-bars: long from 100 (bar 1 open), act 100 ticks, offset 50
    # ticks. Bar 1 sub-bars reach 101.5 (best), bar 2 opens 101.2 and its second sub-bar falls to 100.8:
    # stop 101.0 hit there -> 101.0 'trail' on bar 2
    r = _hand(None, [flat, [(100.0, 101.0, 100.0, 101.0), (101.0, 101.5, 101.0, 101.2)],
                     [(101.2, 101.3, 101.2, 101.3), (101.3, 101.3, 100.8, 100.9)], flat], rb=[0], dsSlPoints=300.0,
              dsTpPoints=0.0, dsUseTrail=True, dsTrActPts=100.0, dsTrPts=50.0)
    check('T7d trailing state carries across chart bars and sub-bars', r['mag'] == [(1, 1, 2, 100.0, 101.0, 'trail')],
          repr(r))
    # (e) inverted: the same trigger as (a) opens a short; the sub-bars rise first: its stop at 102 fills (sl)
    r = _hand(None, [flat, flat, [(100.0, 103.0, 100.0, 103.0), (103.0, 103.0, 97.0, 97.0), (97.0, 100.0, 97.0, 100.0)],
                     flat], rb=[0], dsSlPoints=200.0, dsTpPoints=200.0, inv=True)
    check('T7e inverted (a): the short is stopped at 102 on mag, takes its target at 98 on tv',
          r['mag'] == [(-1, 1, 2, 100.0, 102.0, 'sl')] and r['tv'] == [(-1, 1, 2, 100.0, 98.0, 'tp')], repr(r))
    # (f) an entry filled at the open is not gap-tested against its own fill; a close request ('opp') fills at the
    # chart open even when a sub-bar later would have hit the stop
    r = _hand(None, [flat, flat, [(100.0, 100.0, 99.0, 99.0), (99.0, 99.0, 97.0, 97.0)], flat], rb=[0], rs=[1],
              dsSlPoints=200.0, dsTpPoints=0.0, dsReverse=False)
    check('T7f opposite trigger with reverse off: strategy.close at the chart open, before the sub-bars',
          r['mag'] == [(1, 1, 2, 100.0, 100.0, 'opp')] and r['tv'] == r['mag'], repr(r))


# ================================================================================================
def t8():
    print('\n=== T8: the 1-minute sub-bars rebuild every chart bar ===')
    for pair in ('BTC', 'XAU'):
        for tf in ('5', '15', '30', '60', '120', '240'):
            P = get_P(pair, tf, fgfOn=False)
            try:
                sub = M.sub_bars(pair, tf, P['w0'], P['w1'], check=True)
                ok = len(sub[0]) == P['n'] + 1
                info = '(%d chart bars, %d sub-bars)' % (P['n'], len(sub[1]))
            except ValueError as ex:
                ok, info = False, str(ex)
            check('T8 %s %s sub-bars == chart bars' % (pair, tf), ok, info)
        free()


# ================================================================================================
def t9():
    print('\n=== T9: timing ===')
    t0 = time.time()
    P = get_P('BTC', '1')
    tp = time.time() - t0
    M.get_sub(P)
    run(P, {'path': 'tv'})
    run(P, {'path': 'mag'})
    best = {}
    for path in ('tv', 'mag'):
        ts = []
        for inv in (False, True, False):
            t1 = time.time()
            M.simulate(P, {'path': path, 'inv': inv})
            ts.append(time.time() - t1)
        best[path] = min(ts)
    check('T9 BTC 1 simulate tv %.3f s, mag %.3f s (< 1 s)' % (best['tv'], best['mag']),
          best['tv'] < 1.0 and best['mag'] < 1.0)
    check('T9 BTC 1 prepare %.1f s (< 120 s; %s)' % (tp, 'cached by T2' if tp < 0.1 else 'filter included'),
          tp < 120.0)
    P = get_P('BTC', '5')
    run(P, {'path': 'mag'})
    t1 = time.time()
    M.simulate(P, {'path': 'mag'})
    t5 = time.time() - t1
    check('T9 BTC 5 simulate mag %.3f s (1,038,000 sub-bars)' % t5, t5 < 1.0)
    free()


TESTS = dict(T1=t1, T2=t2, T3=t3, T4=t4, T5=t5, T6=t6, T7=t7, T8=t8, T9=t9)


def main():
    names = sys.argv[1:] or list(TESTS)
    t0 = time.time()
    for nm in names:
        TESTS[nm]()
    print('\n== tests_fgds: %d PASS, %d FAIL, %.0f s, peak RSS %.2f GB' % (
        NPASS, NFAIL, time.time() - t0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0))
    for k, v in TIMING.items():
        if v > 1.0:
            print('   %s: %.1f s' % (k, v))
    if FAILS:
        print('FAILED: ' + ', '.join(FAILS))
    return 1 if NFAIL else 0


if __name__ == '__main__':
    sys.exit(main())
