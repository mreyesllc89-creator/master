"""tests_gvl.py [T1 T2 ...]: stage-3 tests of the canonical GVLiveV2 + FGF replica gvl.py (REPLICA_SPEC.md
stage 3; SPEC_gvl.md section 13 "Additions for stage 3"). Prints PASS / FAIL per test, exits non-zero on a
failure. Without arguments every group runs (about 6 minutes on the shared machine).

  T1  A == B == canonical, trade by trade (every column) and every summary field: BTC and XAU, charts 1, 5,
      15, 60, 240, full windows: default inputs; filter off / on; inv off / on; the three cost modes; "Market"
      and "Stop Next Candle"; 12 seeded random settings per cell (6 grid points of SPEC_gvl section 14 + 6 with
      inputs outside the grid). One sub-process per cell (reconcile_gvl_cmp.py).
  T2  the canonical module reproduces the trade lists the two builders saved in stage 2 (4 cells x 8 variants).
  T3  'mag' on chart "1" == 'tv' (both pre-candle modes, filter off / on, inv off / on, random settings).
  T4  'mag' with one fake sub-bar per chart bar == 'tv'.
  T5  'tv' and 'mag' against the slow pure-Python reference gvl_ref.py: 30 random settings over 2-month
      windows of real bars, and the tie fuzz on synthetic bars (where levels meet all the time), where also
      A == B == canonical.
  T6  the fair halves, every summary field and each cost mode against a direct recomputation from the trade
      list and the bar-close equity curve.
  T7  Update 1 (`inv`): P1 exact mirror with a symmetric bracket (both modes, filter off / on, with and
      without a time stop, both paths); P2 single decisions; P3 first trade; P4 fgfOn False == all-True
      permissions; the header's statement on Allow buys / Allow sells; inv False does not depend on Update 1.
  T8  the daily lock against a slow recount from the trade list ("Market" mode); the life of pending orders;
      the 5-minute-window rule on chart "1"; the 'mag' codes.
  T9  timing.
"""
import os
import random
import subprocess
import sys
import time

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import gvl as M  # noqa: E402
import gvl_cases as G  # noqa: E402
import gvl_ref as RF  # noqa: E402
import gvl_synth as SY  # noqa: E402

RESULTS = []
MKT = "Market Next Candle"
STP = "Stop Next Candle"


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, ('  [' + detail + ']') if detail else ''), flush=True)
    return bool(ok)


def same(ta, tb, skip=()):
    ok, msg, _ = G.cmp_trades(ta, tb, skip=skip)
    return ok, msg


def run(P, x=None, **kw):
    R = M.simulate(P, x, **kw)
    return R, M.trades(P, R), M.summary(P, R)


# ---------------------------------------------------------------------------------------------------------
def t1():
    cells = [(p, tf) for p in G.PAIRS for tf in ('60', '240', '15', '5', '1')]
    tot_cases = 0
    tot_trades = 0
    for pair, tf in cells:
        t0 = time.time()
        r = subprocess.run([sys.executable, '-I', os.path.join(W, 'reconcile_gvl_cmp.py'), pair, tf,
                            # stage 4: gvl FIRST. gvl_b puts the work dir at the head of sys.path on its first
                            # prepare(); in a sandbox copy a later `import gvl` then loaded the UNMUTATED work-dir
                            # gvl.py and T1 could not fail for a mutant (gvl_s4/aud_mut.log). Same comparison.
                            '--mods', 'gvl,gvl_a,gvl_b', '--ngrid', '6', '--nwild', '6', '--seed', '7'],
                           capture_output=True, text=True)
        last = [ln for ln in r.stdout.splitlines() if ln.startswith('== ')]
        last = last[-1] if last else (r.stderr.strip().splitlines() or ['no output'])[-1]
        try:
            tot_cases += int(last.split(':')[1].split('cases')[0])
            tot_trades += int(last.split('cases,')[1].split('trades')[0])
        except Exception:
            pass
        check('T1 A == B == canonical, %s %s' % (pair, tf), r.returncode == 0, '%s; %.0f s' % (last[3:], time.time() - t0))
    check('T1 total', tot_cases >= 360, '%d cases, %d trades, 120 random settings' % (tot_cases, tot_trades))


# ---------------------------------------------------------------------------------------------------------
def t2():
    variants = [('off_normal', False, False), ('on_normal', True, False), ('off_inv', False, True),
                ('on_inv', True, True)]
    for pair, tf in (('BTC', '60'), ('BTC', '5'), ('XAU', '60'), ('XAU', '15')):
        Pk = {f: M.prepare(pair, tf, {'fgfOn': f}) for f in (False, True)}
        for who in ('a', 'b'):
            saved = pd.read_parquet(os.path.join(W, 'out', 'gvl_%s_%s_%s.parquet' % (who, pair, tf)))
            bad = []
            n = 0
            for name, fon, inv in variants:
                for suf, mode in (('', MKT), ('_stop', STP)):
                    _, t, _ = run(Pk[fon], {'inv': inv, 'preCandleEntryMode': mode})
                    s = saved[saved['variant'] == name + suf].drop(columns=['variant']).reset_index(drop=True)
                    ok, msg = same(t, s)
                    n += len(t)
                    if not ok:
                        bad.append(name + suf + ': ' + msg)
            check('T2 canonical == saved stage-2 trade lists of build %s, %s %s' % (who.upper(), pair, tf), not bad,
                  '8 variants, %d trades%s' % (n, ('; ' + bad[0]) if bad else ''))


# ---------------------------------------------------------------------------------------------------------
SUMMARY_PATH_FIELDS = ('reentry_extreme', 'reentry_gap_r')      # defined per path (SPEC_gvl 6.3, 12)


def mag_equals_tv(P, x, sub=None):
    xt = dict(x)
    xt['path'] = 'tv'
    xm = dict(x)
    xm['path'] = 'mag'
    Rt, tt, st = run(P, xt, full=True)
    Rm, tm, sm = run(P, xm, full=True, sub=sub)
    ok1, msg = same(tt, tm, skip=('reentry',))
    ok2 = bool(((tt['reentry'] > 0) == (tm['reentry'] > 0)).all()) if ok1 else False
    ok3, msg3 = G.cmp_summary(st, sm, skip=SUMMARY_PATH_FIELDS)
    ok4 = bool(np.array_equal(Rt['eq'], Rm['eq']) and np.array_equal(Rt['pos'], Rm['pos']))
    return ok1 and ok2 and ok3 and ok4, len(tt), (msg or msg3)


def t3():
    for pair in G.PAIRS:
        n_case = 0
        n_tr = 0
        bad = []
        cases = [(lab, p, s) for lab, p, s in G.fixed_cases() if lab.endswith('/tv') or lab.endswith('/ours')]
        cases += G.random_settings(pair, '1', 8, 8, seed=3)
        for prep, sims in G.group_by_prep(cases):
            P = M.prepare(pair, '1', prep)
            for lab, sim in sims:
                ok, n, msg = mag_equals_tv(P, sim)
                n_case += 1
                n_tr += n
                if not ok:
                    bad.append('%s: %s' % (lab, msg))
        check("T3 'mag' on chart 1 == 'tv', %s" % pair, not bad,
              '%d settings, %d trades%s' % (n_case, n_tr, ('; ' + bad[0]) if bad else ''))
        free_memory()


def t4():
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '5'), ('XAU', '15'), ('BTC', '240'), ('XAU', '240')):
        n_case = 0
        n_tr = 0
        bad = []
        cases = [(lab, p, s) for lab, p, s in G.fixed_cases() if lab.endswith('/tv')]
        cases += G.random_settings(pair, tf, 8, 10, seed=4)
        for prep, sims in G.group_by_prep(cases):
            P = M.prepare(pair, tf, prep)
            fake = M.fake_sub_bars(P)
            for lab, sim in sims:
                ok, n, msg = mag_equals_tv(P, sim, sub=fake)
                n_case += 1
                n_tr += n
                if not ok:
                    bad.append('%s: %s' % (lab, msg))
        check("T4 'mag' with one fake sub-bar per chart bar == 'tv', %s %s" % (pair, tf), not bad,
              '%d settings, %d trades%s' % (n_case, n_tr, ('; ' + bad[0]) if bad else ''))
    # the real sub-bars are not the fake ones: the test above can fail
    P = M.prepare('BTC', '60')
    _, tt, _ = run(P, {'path': 'tv'})
    _, tm, _ = run(P, {'path': 'mag'})
    ok, _ = same(tt, tm, skip=('reentry',))
    check("T4 control: real 1-minute sub-bars give other trades than 'tv' on BTC 60", not ok)


# ---------------------------------------------------------------------------------------------------------
COUNTER_KEYS = ('raw_long', 'raw_short', 'blocked_long', 'blocked_short', 'orders_placed', 'pend_placed',
                'pend_filled', 'pend_replaced', 'pend_cancelled', 'pend_open_end', 'locked_bars', 'lock_days',
                'zero_qty', 'margin_over', 'margin_refused')


def against_reference(P, x, path, sub=None):
    """The canonical run on `path` against gvl_ref: trades (every column), bar-close equity, position, counters."""
    xx = dict(x)
    xx['path'] = path
    R, t, s = run(P, xx, full=True, sub=sub if path == 'mag' else None)
    S = None
    if path == 'mag':
        S = sub if sub is not None else M.get_sub(P)
    rr = RF.ref_run(P, R['x'], M.exit_atr(P, R['x']['atrLen']), sub=S)
    tr = RF.ref_frame(P, rr)
    ok, msg = same(t, tr)
    c = rr['counters']
    okc = (bool(G._feq(np.asarray(R['eq']), np.asarray(rr['eq']), 1e-9).all())
           and bool((np.asarray(R['pos'], np.int64) == np.asarray(rr['pos'], np.int64)).all())
           and all(s[k] == c[k] for k in COUNTER_KEYS)
           and bool(G._feq([s['final_equity'], s['max_notional_x']], [c['final_equity'], c['max_notional_x']],
                           1e-9).all())
           and int(round(s['exposure'] * P['n'])) == c['n_pos'])
    if ok and not okc:
        msg = 'counters / equity curve differ'
    return ok and okc, t, msg


def t5():
    # (a) real bars: 30 random settings over 2-month windows, 'tv' and 'mag'
    day = 86400
    cells = [('BTC', '60', 1731801600 + 40 * day), ('XAU', '60', 1483315200 + 30 * day),
             ('BTC', '5', 1731801600 + 400 * day), ('XAU', '15', 1483315200 + 300 * day),
             ('BTC', '15', 1731801600 + 200 * day), ('XAU', '240', 1483315200 + 120 * day)]
    n_case = 0
    kinds = {}
    tot = {'tv': 0, 'mag': 0}
    bad = []
    n_diff = 0
    for pair, tf, start in cells:
        span = 61 * day if tf != '240' else 240 * day          # the 240-minute chart needs more bars for trades
        for lab, prep, sim in G.random_settings(pair, tf, 2, 3, seed=5):
            pp = dict(prep)
            pp.update(start=start, end=start + span)
            P = M.prepare(pair, tf, pp)
            got = {}
            for path in ('tv', 'mag'):
                ok, t, msg = against_reference(P, sim, path)
                got[path] = t
                tot[path] += len(t)
                if not ok:
                    bad.append('%s %s %s %s: %s' % (pair, tf, lab, path, msg))
            for k, v in got['mag']['exit_kind'].value_counts().items():
                kinds[k] = kinds.get(k, 0) + int(v)
            if not same(got['tv'], got['mag'], skip=('reentry',))[0]:
                n_diff += 1
            n_case += 1
    check("T5 'tv' and 'mag' == pure-Python reference, real bars, 2-month windows", not bad and n_case >= 30,
          '%d settings; trades tv %d, mag %d (%s); mag != tv in %d settings%s' % (
              n_case, tot['tv'], tot['mag'], ', '.join('%s %d' % kv for kv in sorted(kinds.items())), n_diff,
              ('; ' + bad[0]) if bad else ''))
    # (b) default inputs on longer windows (the settings the by-timeframe table reports)
    bad = []
    n = 0
    for pair, tf, start, span in (('BTC', '60', 1731801600, 240 * day), ('XAU', '60', 1483315200, 240 * day),
                                  ('BTC', '5', 1731801600 + 100 * day, 30 * day)):
        for fon in (False, True):
            P = M.prepare(pair, tf, {'fgfOn': fon, 'start': start, 'end': start + span})
            for mode in (MKT, STP):
                for inv in (False, True):
                    for cost in ('tv', 'ours'):
                        ok, t, msg = against_reference(P, {'preCandleEntryMode': mode, 'inv': inv, 'cost': cost}, 'mag')
                        n += len(t)
                        if not ok:
                            bad.append('%s %s %s %s %s: %s' % (pair, tf, fon, mode, inv, msg))
    check("T5 'mag' == pure-Python reference, default inputs (filter x mode x inv x cost), longer windows", not bad,
          '48 runs, %d trades%s' % (n, ('; ' + bad[0]) if bad else ''))
    # (c) synthetic bars: the tie fuzz, with A and B
    import gvl_a as A
    import gvl_b as B
    cnt = dict(ab=0, ac=0, tv=0, mag=0, fake=0)
    ntr = 0
    n_case = 0
    after = 0
    # the seven seeds on which the two builds differed as delivered (reconcile_gvl_synth_orig.log) + 33 others,
    # the settings stream of reconcile_gvl_synth.py
    for seed in [33, 61, 72, 79, 111, 129, 149] + list(range(200, 233)):
        S = SY.synth(seed)
        PA, PB, PC = SY.make_P(A, S), SY.make_P(B, S), SY.make_P(M, S)
        rng = random.Random(1000 + seed)
        for _ in range(12):
            x = SY.synth_setting(rng)
            ta = A.trades(PA, A.simulate(PA, x))
            tb = B.trades(PB, B.simulate(PB, x))
            _, tc, _ = run(PC, x)
            ntr += len(tc)
            after += int(tc['after_exit'].sum())
            n_case += 1
            cnt['ab'] += not same(ta, tb)[0]
            cnt['ac'] += not same(ta, tc)[0]
            cnt['tv'] += not against_reference(PC, x, 'tv')[0]
            cnt['mag'] += not against_reference(PC, x, 'mag', sub=S['sub'])[0]
            cnt['fake'] += not mag_equals_tv(PC, x, sub=M.fake_sub_bars(PC))[0]
    check('T5 synthetic tie fuzz: A == B == canonical; canonical == reference on tv and mag; fake sub-bars == tv',
          not any(cnt.values()), '%d cases, %d trades, %d pending fills right after an exit at the same bar; '
          'differing %r' % (n_case, ntr, after, cnt))
    # (d) the one place where the builds differed as delivered (reconcile_gvl.md): a pending order on the
    #     price where a leg ends, right after an exit at that price, fills there
    S = SY.synth(33)
    PC = SY.make_P(M, S)
    x = SY.synth_setting(random.Random(1000 + 33))
    _, tc, _ = run(PC, x)
    r = tc.iloc[5]
    check('T5 a limit on the price where the leg ends fills right after the exit at that price (seed 33)',
          int(r['entry_bar']) == 59 and r['entry_px'] == 988.0 and bool(r['after_exit'])
          and tc.iloc[4]['exit_kind'] == 'tp' and tc.iloc[4]['exit_px'] == 988.0 and int(tc.iloc[4]['exit_bar']) == 59,
          'trade 4 exits tp at 988.00 on bar 59, trade 5 is the buy limit filled at 988.00 on bar 59')


# ---------------------------------------------------------------------------------------------------------
def recompute(P, R, t, cost, pair):
    """The summary from the trade list and the bar-close equity curve alone."""
    init = 100000.0
    fixed, frac = {'tv': (0.0, 0.0),
                   'ours': {'XAU': (0.15, 0.0), 'BTC': (0.10, 0.0002)}[pair],
                   'stress': {'XAU': (0.25 + 0.01, 0.0), 'BTC': (0.10 + 0.01, 0.00035)}[pair]}[cost]
    d = t['dir'].to_numpy(np.float64)
    q = t['qty'].to_numpy()
    e = t['entry_px'].to_numpy()
    xp = t['exit_px'].to_numpy()
    costs = q * (fixed + frac * e) + q * (fixed + frac * xp)
    gross = d * q * (xp - e)
    pnl = gross - costs
    eqb = init + np.concatenate([[0.0], np.cumsum(pnl)[:-1]]) if len(pnl) else np.zeros(0)
    first = t['entry_time'].to_numpy() <= P['mid']
    out = dict(trades=len(t), final_equity=init + pnl.sum(), net_pct=pnl.sum() / init * 100, costs=costs.sum(),
               long=int((d > 0).sum()), short=int((d < 0).sum()),
               h1_trades=int(first.sum()), h2_trades=int((~first).sum()),
               h1r_pct=(np.prod(1 + pnl[first] / eqb[first]) - 1) * 100,
               h2r_pct=(np.prod(1 + pnl[~first] / eqb[~first]) - 1) * 100,
               zero_length=int((t['entry_bar'] == t['exit_bar']).sum()),
               avg_bars_held=float((t['exit_bar'] - t['entry_bar']).mean()) if len(t) else np.nan,
               win_pct=float((pnl > 0).mean() * 100) if len(t) else np.nan)
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    out['pf'] = gp / gl if gl > 0 else (np.inf if gp > 0 else np.nan)
    for k in M.KINDS[1:]:
        out['exit_' + k] = int((t['exit_kind'] == k).sum())
    sld = t['sl_dist'].to_numpy()
    with np.errstate(invalid='ignore', divide='ignore'):
        rm = np.where(sld > 0, pnl / (sld * q), np.nan)
    out.update(net_r=rm.sum(), h1_r=rm[first].sum(), h2_r=rm[~first].sum())
    eq = np.asarray(R['eq'], np.float64)
    pk = np.maximum.accumulate(np.concatenate([[init], eq]))[1:]
    out['max_dd_pct'] = float(((pk - eq) / pk).max() * 100)
    out['max_dd_init_pct'] = float((pk - eq).max() / init * 100)
    eq_mid = eq[P['mid_j']] if P['mid_j'] >= 0 else init
    out['half1_pct'] = (eq_mid - init) / init * 100
    out['half2_pct'] = (eq[-1] - eq_mid) / init * 100
    out['exposure'] = float((np.asarray(R['pos']) != 0).mean())
    return out, pnl, costs, eqb


def t6():
    bad = []
    n = 0
    n_cost = {'tv': 0.0, 'ours': 0.0, 'stress': 0.0}
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '5'), ('XAU', '15'), ('XAU', '240')):
        cases = [(lab, p, s) for lab, p, s in G.fixed_cases()] + G.random_settings(pair, tf, 6, 6, seed=6)
        for prep, sims in G.group_by_prep(cases):
            P = M.prepare(pair, tf, prep)
            for lab, sim in sims:
                for path in ('tv', 'mag'):
                    x = dict(sim)
                    x['path'] = path
                    R, t, s = run(P, x, full=True)
                    ref, pnl, costs, eqb = recompute(P, R, t, R['x']['cost'], pair)
                    msgs = []
                    for k, v in ref.items():
                        if not bool(G._feq([float(v)], [float(s[k])], 1e-9)[0]):
                            msgs.append('%s %r vs %r' % (k, s[k], v))
                    if len(t):
                        if not G._feq(t['pnl'].to_numpy(), pnl, 1e-9).all():
                            msgs.append('pnl')
                        if not G._feq(t['costs'].to_numpy(), costs, 1e-9).all():
                            msgs.append('costs')
                        if not G._feq(t['eq_before'].to_numpy(), eqb, 1e-9).all():
                            msgs.append('eq_before')
                    n_cost[R['x']['cost']] += float(costs.sum())
                    n += 1
                    if msgs:
                        bad.append('%s %s %s %s: %s' % (pair, tf, lab, path, '; '.join(msgs[:3])))
    check('T6 every summary field, pnl, costs and eq_before == a direct recomputation from the trade list', not bad,
          '%d runs (tv and mag; cost tv / ours / stress: %.0f / %.0f / %.0f charged)%s' % (
              n, n_cost['tv'], n_cost['ours'], n_cost['stress'], ('; ' + bad[0]) if bad else ''))
    check("T6 cost 'tv' charges nothing; 'ours' and 'stress' charge", n_cost['tv'] == 0.0 and n_cost['ours'] > 0
          and n_cost['stress'] > 0)
    # the cost of one trade, spelled out (XAU: $0.30 / oz per round trip; stress $0.50 + 1 tick per fill;
    # BTC: 0.02 % per fill + $0.20 per round trip; stress 0.035 % per fill + $0.20 + 1 tick per fill)
    ok = True
    for pair, tf in (('XAU', '60'), ('BTC', '60')):
        P = M.prepare(pair, tf)
        for cost in ('ours', 'stress'):
            _, t, _ = run(P, {'cost': cost})
            r = t.iloc[0]
            if pair == 'XAU':
                want = r['qty'] * (0.30 if cost == 'ours' else 0.50 + 2 * 0.01)
            else:
                pct = 0.0002 if cost == 'ours' else 0.00035
                want = r['qty'] * (pct * (r['entry_px'] + r['exit_px']) + 0.20 + (0.0 if cost == 'ours' else 2 * 0.01))
            ok = ok and abs(r['costs'] - want) <= 1e-9 * max(1.0, want)
    check('T6 the cost of the first trade equals the cost definition (XAU, BTC x ours, stress)', ok)


# ---------------------------------------------------------------------------------------------------------
def t7():
    sym = dict(tpR=1.0, useTrail=False, QtyMode="Fixed", fixedQty=0.01, capMargin=False, useDailyLossLock=False,
               tvMargin=0.0, cost='tv')
    # ---- P1: exact mirror
    bad = []
    n = 0
    ncase = 0
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '5'), ('XAU', '15')):
        for fon in (False, True):
            P = M.prepare(pair, tf, {'fgfOn': fon})
            for mode in (MKT, STP):
                for held in (0, 4):
                    for path in ('tv', 'mag'):
                        x = dict(sym, preCandleEntryMode=mode, maxBarsHeld=held, path=path)
                        _, a, _ = run(P, dict(x, inv=False))
                        _, b, _ = run(P, dict(x, inv=True))
                        m = a.copy()
                        m['dir'] = -m['dir']
                        m['pnl'] = -m['pnl']
                        m['pnl_gross'] = -m['pnl_gross']
                        m['r_mult'] = -m['r_mult']
                        m['exit_kind'] = m['exit_kind'].map(lambda k: {'sl': 'tp', 'tp': 'sl'}.get(k, k))
                        m['order_type'] = m['order_type'].map(lambda k: {'stop': 'limit'}.get(k, k))
                        sl, tp = m['sl_px'].copy(), m['tp_px'].copy()
                        m['sl_px'], m['tp_px'] = tp, sl
                        ok, msg = same(m, b, skip=('eq_before',))
                        ncase += 1
                        n += len(a)
                        if not ok or len(a) == 0:
                            bad.append('%s %s %s %s %d %s: %s' % (pair, tf, fon, mode, held, path, msg))
    check('T7 P1 exact mirror with a symmetric bracket (tpR 1, Fixed 0.01, no lock): inv == normal with dir, pnl '
          'negated, sl <-> tp', not bad, '%d cases, %d trades%s' % (ncase, n, ('; ' + bad[0]) if bad else ''))
    # control: with the default 5 R target the mirror does not hold
    P = M.prepare('BTC', '60')
    _, a, _ = run(P, dict(sym, tpR=5.0, inv=False))
    _, b, _ = run(P, dict(sym, tpR=5.0, inv=True))
    check('T7 P1 control: with tpR 5 the inverted list is not the mirror', len(a) != len(b)
          or not (a['exit_bar'].to_numpy() == b['exit_bar'].to_numpy()).all())

    # ---- P2 / P3: single first decisions from a clean state, default inputs, windows starting anywhere
    bad = []
    n_dec = 0
    n_pend = 0
    n_blocked = 0
    day = 86400
    for pair, tf, s0, e0 in (('BTC', '60', 1731801600, 1794873600), ('XAU', '60', 1483315200, 1529366400),
                             ('BTC', '5', 1731801600, 1794873600), ('XAU', '15', 1483315200, 1529366400)):
        rng = random.Random('p2%s%s' % (pair, tf))
        for i in range(10):
            start = s0 + rng.randrange(0, (e0 - s0) - 40 * day)
            for fon in (False, True):
                P = M.prepare(pair, tf, {'fgfOn': fon, 'start': start, 'end': start + 30 * day})
                for mode in (MKT, STP):
                    Ra, a, sa = run(P, {'preCandleEntryMode': mode, 'inv': False}, full=True)
                    Rb, b, sb = run(P, {'preCandleEntryMode': mode, 'inv': True}, full=True)
                    pa = np.flatnonzero(Ra['placed'])
                    pb = np.flatnonzero(Rb['placed'])
                    if len(pa) == 0 and len(pb) == 0:
                        continue
                    n_dec += 1
                    j = int(pa[0])
                    # the same first decision on the same bar: same signal side and kind, same quantity
                    ok = (len(pb) > 0 and int(pb[0]) == j and Ra['placed'][j] == Rb['placed'][j]
                          and Ra['entry_qty'][j] == Rb['entry_qty'][j])
                    # every decision before it was a blocked one or none, in both
                    ok = ok and bool((Ra['can_enter'][:j + 1] == Rb['can_enter'][:j + 1]).all())
                    blk = (P['armL'][:j] | P['sigL'][:j]) & ~P['buyOk'][:j] | (P['armS'][:j] | P['sigS'][:j]) & ~P['sellOk'][:j]
                    n_blocked += int(blk.sum())
                    if ok and len(a) and len(b) and a['sig_bar'].iloc[0] == b['sig_bar'].iloc[0] == j + P['w0']:
                        ra, rb = a.iloc[0], b.iloc[0]
                        ok = (ra['dir'] == -rb['dir'] and ra['sig'] == rb['sig'] and ra['entry_bar'] == rb['entry_bar']
                              and ra['entry_px'] == rb['entry_px'] and ra['qty'] == rb['qty']
                              and ra['sl_dist'] == rb['sl_dist'] and ra['entry_kind'] == rb['entry_kind']
                              and abs((ra['entry_px'] - ra['sl_px']) + (rb['entry_px'] - rb['sl_px'])) < 1e-9
                              and abs((ra['entry_px'] - ra['tp_px']) + (rb['entry_px'] - rb['tp_px'])) < 1e-9
                              and (ra['order_type'], rb['order_type']) in (('market', 'market'), ('stop', 'limit')))
                        n_pend += ra['order_type'] == 'stop'
                    elif ok:
                        # the first order never filled (cancelled): then in both
                        ok = (len(a) == 0 or a['sig_bar'].iloc[0] != j + P['w0']) and \
                             (len(b) == 0 or b['sig_bar'].iloc[0] != j + P['w0'])
                    if not ok:
                        bad.append('%s %s start %d fon %s %s' % (pair, tf, start, fon, mode))
    check('T7 P2 / P3 first decision and first trade: same bar, kind, quantity, fill bar and price, other side, '
          'bracket mirrored, stop <-> limit', not bad and n_dec >= 100,
          '%d clean starts (%d first trades from a pending order; %d filter-blocked candidates before them, '
          'blocked with the option off and on)%s' % (n_dec, n_pend, n_blocked, ('; ' + bad[0]) if bad else ''))

    # ---- P4: fgfOn False == fgfOn True with all-True permissions
    bad = []
    for pair, tf in (('BTC', '60'), ('XAU', '15')):
        P0 = M.prepare(pair, tf, {'fgfOn': False})
        ones = np.ones(P0['n'], bool)
        P1 = M.prepare(pair, tf, {'fgfOn': True}, _perm=(ones, ones))
        P2 = M.prepare(pair, tf, {'fgfOn': True})
        for mode in (MKT, STP):
            for inv in (False, True):
                x = {'preCandleEntryMode': mode, 'inv': inv}
                _, a, sa = run(P0, x)
                _, b, sb = run(P1, x)
                _, c, sc = run(P2, x)
                if not same(a, b)[0] or not G.cmp_summary(sa, sb)[0]:
                    bad.append('%s %s %s %s' % (pair, tf, mode, inv))
                if same(a, c)[0]:
                    bad.append('%s %s %s %s: the filter changes nothing' % (pair, tf, mode, inv))
        for k in ('armL', 'armS', 'sigL', 'sigS', 'gate'):
            if not np.array_equal(P0[k], P2[k]):
                bad.append('%s differs with the filter' % k)
    check('T7 P4 fgfOn False == fgfOn True with all-True permissions; arms, signals and gates do not depend on '
          'the filter; the real filter changes the trades', not bad, '; '.join(bad[:2]))

    # ---- the header: Allow buys / Allow sells act on the SIGNAL's side
    bad = []
    for pair, tf in (('BTC', '60'), ('XAU', '60')):
        Pb = M.prepare(pair, tf, {'fgfOn': True, 'fgfAllowBuy': False})
        Ps = M.prepare(pair, tf, {'fgfOn': True, 'fgfAllowSell': False})
        for mode in (MKT, STP):
            for inv in (False, True):
                _, a, sa = run(Pb, {'preCandleEntryMode': mode, 'inv': inv})
                _, b, sb = run(Ps, {'preCandleEntryMode': mode, 'inv': inv})
                want_a = 1 if inv else -1          # Allow buys off: only sig -1 entries, which inverted are BUYS
                ok = (len(a) > 0 and (a['sig'] == -1).all() and (a['dir'] == want_a).all()
                      and sa['blocked_long'] == sa['raw_long']
                      and len(b) > 0 and (b['sig'] == 1).all() and (b['dir'] == -want_a).all()
                      and sb['blocked_short'] == sb['raw_short'])
                if not ok:
                    bad.append('%s %s %s %s' % (pair, tf, mode, inv))
    check('T7 header: filter on + Allow buys off = no PRE-L / long-signal entries, which inverted are the SELLS '
          '(only buys remain); Allow sells off the mirror', not bad, '; '.join(bad[:2]))

    # ---- raw / blocked stay in the normal frame; dir = -sig with the option on
    P = M.prepare('XAU', '60', {'fgfOn': True})
    _, a, sa = run(P, {'inv': False})
    _, b, sb = run(P, {'inv': True})
    check('T7 sides: dir == sig with the option off, dir == -sig with it on; order types', bool(
        (a['dir'] == a['sig']).all() and (b['dir'] == -b['sig']).all() and (a['order_type'] == 'market').all()
        and set(run(P, {'inv': True, 'preCandleEntryMode': STP})[1]['order_type']) <= {'limit', 'market'}
        and set(run(P, {'inv': False, 'preCandleEntryMode': STP})[1]['order_type']) <= {'stop', 'market'}))
    # ---- gvInv / inv
    ok = True
    try:
        M.simulate(P, {'inv': True, 'gvInv': False})
        ok = False
    except ValueError:
        pass
    _, c, _ = run(P, {'gvInv': True})
    check('T7 gvInv is the Pine name, inv its alias; both given and disagreeing raises', ok and same(b, c)[0])


# ---------------------------------------------------------------------------------------------------------
def t8():
    # ---- the daily lock against a slow recount of losing trades per New York day ("Market" mode)
    bad = []
    n_lock = 0
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '5'), ('XAU', '15'), ('BTC', '15')):
        P = M.prepare(pair, tf)
        day = P['day']
        w0 = P['w0']
        for path in ('tv', 'mag'):
            for inv in (False, True):
                for cost in ('tv', 'ours'):
                    R, t, s = run(P, {'path': path, 'inv': inv, 'cost': cost}, full=True)
                    xb = t['exit_bar'].to_numpy() - w0
                    sb = t['sig_bar'].to_numpy() - w0
                    lose = (t['pnl'].to_numpy() < 0) & (t['exit_kind'].to_numpy() != 'end')
                    # one trade closes per bar at most in this mode
                    ok = len(np.unique(xb)) == len(xb)
                    # losses[j] = losing trades closed on the day of bar j, up to and including bar j
                    add = np.zeros(P['n'], np.int64)
                    np.add.at(add, xb[lose], 1)
                    cum = np.cumsum(add)
                    first_of_day = np.concatenate([[True], day[1:] != day[:-1]])
                    base = np.maximum.accumulate(np.where(first_of_day, cum - add, 0))
                    losses = cum - base
                    locked = losses >= 3
                    ok = ok and int(locked.sum()) == s['locked_bars'] and np.array_equal(locked, R['locked'])
                    ok = ok and not locked[sb].any()                    # no order is placed in a locked run
                    ok = ok and s['exit_daily_lock'] == 0
                    n_lock += int(locked.sum())
                    if not ok:
                        bad.append('%s %s %s inv %s %s' % (pair, tf, path, inv, cost))
    check('T8 the daily lock == a recount of losing trades per New York day from the trade list (Market mode, '
          'tv and mag, costs tv / ours)', not bad, '%d locked bars recounted%s' % (n_lock, ('; ' + bad[0]) if bad else ''))
    P = M.prepare('BTC', '5')
    _, t0, s0 = run(P, {'useDailyLossLock': True})
    _, t1, s1 = run(P, {'useDailyLossLock': False})
    check('T8 control: without the lock BTC 5 takes many more trades', s1['trades'] > 2 * s0['trades']
          and s1['locked_bars'] == 0, '%d vs %d' % (s1['trades'], s0['trades']))
    # the day key is the New York calendar date of the bar's open
    idx = pd.to_datetime(P['t_open'], unit='s', utc=True).tz_convert('America/New_York')
    key = np.asarray(idx.year) * 10000 + np.asarray(idx.month) * 100 + np.asarray(idx.day)
    ch = np.flatnonzero(P['day'][1:] != P['day'][:-1]) + 1
    hrs = (P['t_open'][ch] % 86400) // 3600
    hours = set(hrs.tolist())
    check('T8 the lock day = New York calendar date of the bar open: it changes at 04:00 (summer) or 05:00 UTC',
          np.array_equal(key, P['day']) and {4, 5} <= hours and float(np.isin(hrs, (4, 5)).mean()) > 0.99,
          'UTC hour of the first bar of a day: 04 on %d days, 05 on %d, other (data holes) on %d' % (
              int((hrs == 4).sum()), int((hrs == 5).sum()), int((~np.isin(hrs, (4, 5))).sum())))

    # ---- the life of pending orders ("Stop" mode)
    bad = []
    n_fill = 0
    n_late = 0
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '5'), ('XAU', '15')):
        for fon in (False, True):
            P = M.prepare(pair, tf, {'fgfOn': fon})
            w0 = P['w0']
            for path in ('tv', 'mag'):
                for inv in (False, True):
                    for cancel in (1, 2, 5):
                        R, t, s = run(P, {'preCandleEntryMode': STP, 'path': path, 'inv': inv,
                                          'preCancelAfterBars': cancel}, full=True)
                        pre = np.flatnonzero(np.abs(R['placed']) == 2)
                        ok = s['pend_placed'] == len(pre) == (s['pend_filled'] + s['pend_replaced']
                                                              + s['pend_cancelled'] + s['pend_open_end'])
                        tk = t[t['entry_kind'] == 2]
                        ok = ok and len(tk) == s['pend_filled']
                        eb = tk['entry_bar'].to_numpy() - w0
                        last = pre[np.searchsorted(pre, eb, side='left') - 1]       # the last placement before the fill
                        in_time = eb <= last + cancel + 1
                        prev_rev = np.zeros(len(t), bool)
                        prev_rev[1:] = ((t['exit_kind'].to_numpy()[:-1] == 'reverse')
                                        & (t['exit_bar'].to_numpy()[:-1] == t['entry_bar'].to_numpy()[1:])
                                        & (t['exit_px'].to_numpy()[:-1] == t['entry_px'].to_numpy()[1:]))
                        late_ok = prev_rev[tk.index.to_numpy()] | tk['after_exit'].to_numpy()
                        ok = ok and bool((eb > last).all()) and bool((in_time | late_ok).all())
                        n_fill += len(tk)
                        n_late += int((~in_time).sum())
                        # a price order fills at its price or at a (sub-)bar open beyond it
                        if not ok:
                            bad.append('%s %s %s %s inv %s cancel %d' % (pair, tf, fon, path, inv, cancel))
    check('T8 pending orders: placed = filled + replaced + cancelled + open at the end; every fill is within '
          'preCancelAfterBars + 1 bars of the last pre-candle placement, or a reversal, or right after an exit '
          'of that bar', not bad, '%d fills, %d of them later than the timer%s' % (n_fill, n_late,
                                                                               ('; ' + bad[0]) if bad else ''))
    # ---- chart "1": the 5-minute-window rule
    P = M.prepare('BTC', '1', {'start': 1731801600 + 300 * 86400, 'end': 1731801600 + 330 * 86400})
    R, t, s = run(P, {'useDailyLossLock': False}, full=True)
    pl = np.flatnonzero(R['placed'])
    secs = (P['t_open'][pl] % 300)
    wins = P['win'][pl]
    R2, t2, s2 = run(P, {'useDailyLossLock': False, 'oneSignalPerPolyWindow': False}, full=True)
    w2 = P['win'][np.flatnonzero(R2['placed'])]
    check('T8 chart 1: orders only in the first two minutes of a 5-minute window, one per window; with the rule '
          'off a window can hold two', len(pl) > 50 and set(secs.tolist()) <= {0, 60} and len(np.unique(wins)) == len(wins)
          and len(np.unique(w2)) < len(w2), '%d orders in 30 days (rule off: %d)' % (len(pl), len(w2)))
    M.clear_cache()
    # ---- 'mag' codes
    P = M.prepare('BTC', '60')
    _, tm, sm = run(P, {'path': 'mag', 'inv': True})
    _, tt, st = run(P, {'path': 'tv', 'inv': True})
    check("T8 'mag': reentry codes are 0 / 1 / 2, reentry_gap_r is 0; 'tv' has a non-zero gap estimate",
          set(tm['reentry'].unique()) <= {0, 1, 2} and sm['reentry_gap_r'] == 0.0 and st['reentry_gap_r'] != 0.0
          and sm['reentry_same_bar'] > 0)
    # entry and exit times are chart-bar times on both paths
    ok = bool((np.isin(tm['entry_time'], P['t_open'])).all()
              and (np.isin(tm['exit_time'][tm['exit_kind'] != 'end'], P['t_open'])).all())
    check("T8 'mag': entry_time / exit_time are chart-bar opens", ok)
    # every bracket exit price of the mag path lies inside its chart bar; sl / tp fill at the level or at a
    # sub-bar open beyond it
    S = M.get_sub(P)
    k = tm['exit_bar'].to_numpy() - P['w0']
    br = tm['exit_kind'].isin(['sl', 'tp']).to_numpy()
    inside = (tm['exit_px'].to_numpy() <= P['high'][k] + 1e-9) & (tm['exit_px'].to_numpy() >= P['low'][k] - 1e-9)
    lvl = np.where(tm['exit_kind'] == 'sl', tm['sl_px'], tm['tp_px'])
    at_level = np.abs(tm['exit_px'].to_numpy() - lvl) < 1e-9
    at_sub_open = np.array([tm['exit_px'].iloc[i] in S[1][S[0][k[i]]:S[0][k[i] + 1]] for i in range(len(tm))])
    check("T8 'mag': a stop / target fills at its level or at a 1-minute open beyond it, inside the chart bar",
          bool(inside[br].all() and (at_level | at_sub_open)[br].all()),
          '%d at the level, %d at a sub-bar open' % (int((at_level & br).sum()), int((~at_level & at_sub_open & br).sum())))


# ---------------------------------------------------------------------------------------------------------
def t9():
    M.clear_cache()
    t0 = time.time()
    P = M.prepare('BTC', '1')
    t_prep = time.time() - t0
    M.simulate(P)
    ts = []
    for x in ({}, {'useDailyLossLock': False}, {'preCandleEntryMode': STP, 'useDailyLossLock': False},
              {'path': 'mag'}, {'path': 'mag', 'useDailyLossLock': False, 'preCandleEntryMode': STP}):
        M.simulate(P, x)
        t0 = time.time()
        for _ in range(3):
            R = M.simulate(P, x)
        ts.append(((time.time() - t0) / 3, len(R['dir'])))
    t0 = time.time()
    M.prepare('BTC', '1', {'preCloseLocation': 0.75, 'preMinVolScore': 0.0})
    t_prep2 = time.time() - t0
    check('T9 timing BTC 1 (1,039,430 bars): first prepare < 120 s, one simulate < 1 s', t_prep < 120 and
          max(a for a, _ in ts) < 1.0,
          'prepare %.1f s (another threshold setting %.2f s); simulate tv default %.3f s (%d trades), lock off '
          '%.3f s (%d), Stop + lock off %.3f s (%d); mag default %.3f s, mag Stop + lock off %.3f s (%d)' % (
              t_prep, t_prep2, ts[0][0], ts[0][1], ts[1][0], ts[1][1], ts[2][0], ts[2][1], ts[3][0], ts[4][0], ts[4][1]))
    M.clear_cache()
    for pair, tf in (('BTC', '60'), ('BTC', '5'), ('XAU', '240')):
        P = M.prepare(pair, tf)
        t0 = time.time()
        M.get_sub(P)
        t_sub = time.time() - t0
        out = []
        for x in ({'path': 'tv'}, {'path': 'mag'}, {'path': 'mag', 'preCandleEntryMode': STP, 'useTrail': True,
                                                     'trailActAtr': 2.0, 'tpR': 0.0, 'useDailyLossLock': False}):
            M.simulate(P, x)
            t0 = time.time()
            for _ in range(5):
                M.simulate(P, x)
            out.append((time.time() - t0) / 5 * 1000)
        check('T9 timing %s %s' % (pair, tf), max(out) < 500,
              'sub-bar table %.2f s; simulate tv %.1f ms, mag %.1f ms, mag Stop + trail + lock off %.1f ms' % (
                  t_sub, out[0], out[1], out[2]))


GROUPS = dict(T1=t1, T2=t2, T3=t3, T4=t4, T5=t5, T6=t6, T7=t7, T8=t8, T9=t9)


def free_memory():
    """Between groups: drop the caches of the replica and of the filter module (data only; nothing is edited),
    so that the whole run stays well under the 3 GB limit."""
    import gc
    import fgf
    M.clear_cache()
    for name in ('_BARS', '_DIR', '_FILTER'):
        d = getattr(fgf, name, None)
        if isinstance(d, dict):
            d.clear()
    gc.collect()


if __name__ == '__main__':
    t_all = time.time()
    names = [a for a in sys.argv[1:] if a in GROUPS] or ['T3', 'T2', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'T1']
    import resource
    for nm in names:
        t0 = time.time()
        GROUPS[nm]()
        free_memory()
        print('-- %s done in %.0f s' % (nm, time.time() - t0), flush=True)
    nf = sum(1 for _, ok in RESULTS if not ok)
    print('== tests_gvl: %d PASS, %d FAIL (%.0f s, peak RSS %.2f GB)' % (
        len(RESULTS) - nf, nf, time.time() - t_all, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0))
    sys.exit(1 if nf else 0)
