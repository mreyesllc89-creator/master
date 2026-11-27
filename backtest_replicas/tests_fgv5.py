"""tests_fgv5.py: stage-3 tests of the canonical replica fgv5.py (REPLICA_SPEC.md stage 3, SPEC_fgv5.md sections 8, 13).

    python3 -I tests_fgv5.py [section ...]        -> prints PASS / FAIL per test, exit status 1 on any FAIL

Sections (all by default):
  recon    A == B == canonical (path 'tv') on the reconcile cases: the 16 fixed cases of fgv5_cases on BTC 60,
           XAU 60, BTC 240, XAU 15 (full windows) + 8 random settings each (seed 7)
  signals  canonical signals == fgf's copy of the FlashGold signal (fgf._filter_series with the mapped inputs),
           == the filter's own signals on "60"; the counts of SPEC_fgv5 4.6 (BTC 240 with the daily-reset "960")
  kernel   the 29 hand-built scenarios of fgv5_b_check_kernel.py on the canonical module, path 'tv' and path 'mag'
           with one fake sub-bar per bar; 4 hand-built 'mag' scenarios with real sub-bars (M1-M4)
  mag1     path 'mag' on chart "1" == 'tv' (XAU 1 full window, BTC 1 full window)
  fake     path 'mag' with one fake sub-bar per chart bar == 'tv' (6 cells x 6 settings)
  ref      canonical == the slow pure-Python reference fgv5_ref.py on paths 'tv' AND 'mag' (real 1-minute
           sub-bars), 30 random settings over 2-month windows: every trade column the reference produces, the
           order counters, the final equity
  money    fair halves, costs of each cost mode, P/L, net, pf, win % recomputed from the trade list; every fill
           inside its bar (raw prices); 'tv' / 'mag' x cost tv / ours / stress x normal / inverted
  header   SPEC_fgv5 13 (i)-(v): 'tp_part' at the target (or a better open), 'sl' at the stop - slippage (or a
           worse open), qty == calcQty of the placing bar from the trade list (Risk %), 'time' exits at
           entry_bar + maxBarsHeld + 1, 'be' at the entry - slippage (or a worse open), be_no_tp == 0 when normal
  inv      Update 1 properties: P1 exact mirror (both exit units + Pips, exitOnOpposite, time stop, entryValidBars
           0 / 1, filter on / off, paths tv / mag); P2 single decisions (_decide, position negated, Direction
           swapped); P3 first trade; P4 Direction "Long"; P5 chart 60 filter on: no trade; P6 fgfOn False ==
           injected all-True gates; option off == the pre-Update-1 text (git 6c59b9f) and == the unfused original
           apart from the gate
  timing   simulate on BTC "1" (1,039,430 bars) 'tv' well under 1 s after compilation; 'mag' timings
"""
import contextlib
import io
import math
import os
import random
import subprocess
import sys
import time

import numpy as np

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import fgf  # noqa: E402
import fgv5 as C  # noqa: E402
import fgv5_cases as G  # noqa: E402

FAILS = []
NPASS = [0]


def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + info) if info else ''), flush=True)
    if ok:
        NPASS[0] += 1
    else:
        FAILS.append(name)


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(b))


def same_trades(ta, tb, cols=None):
    if cols is not None:
        ta = ta[cols]
        tb = tb[cols]
    ok, msg, first = G.cmp_trades(ta, tb)
    return ok, msg


def run_c(P, x, sub=None):
    R = C.simulate(P, x, full=True, sub=sub)
    return C.trades(P, R), C.summary(P, R), R


# ----------------------------------------------------------------------------------------------
def t_recon():
    import fgv5_a as A
    import fgv5_b as B
    mods = (('fgv5_a', A), ('fgv5_b', B), ('fgv5', C))
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '240'), ('XAU', '15')):
        cases = G.fixed_cases() + G.random_settings(pair, tf, 4, 4, 7)
        nbad = 0
        ntr = 0
        for prep, sims in G.group_by_prep(cases):
            P = {nm: m.prepare(pair, tf, dict(prep)) for nm, m in mods}
            for lab, sim in sims:
                res = {}
                for nm, m in mods:
                    R = m.simulate(P[nm], dict(sim)) if nm == 'fgv5_a' else m.simulate(P[nm], dict(sim), full=True)
                    res[nm] = (m.trades(P[nm], R), m.summary(P[nm], R), R['E'] if nm == 'fgv5_a' else R['eq'])
                ta, sa, ea = res['fgv5_a']
                ntr += len(ta)
                for nm in ('fgv5_b', 'fgv5'):
                    tb, sb, eb = res[nm]
                    ok = G.cmp_trades(ta, tb)[0] and G.cmp_summary(sa, sb)[0] and G.cmp_arrays(ea, eb)[0]
                    if not ok:
                        nbad += 1
                        print('   differs: %s %s %s %s' % (pair, tf, lab, nm))
        check('recon %s %s: A == B == canonical on %d cases (%d trades)' % (pair, tf, len(cases), ntr), nbad == 0)
        fgf._FILTER.clear()
        for m in (A, B, C):
            for c in ('_SIGC', '_PERM', '_SIG'):
                if hasattr(m, c):
                    getattr(m, c).clear()


# ----------------------------------------------------------------------------------------------
def _mapped(chart_tf, Q):
    par, z = C.zone_inputs(Q, chart_tf)
    m = dict(fgfParentTf=par, fgfZTf1=z[0], fgfZTf2=z[1], fgfZTf3=z[2], fgfZTf4=z[3], fgfZTf5=z[4], fgfZTf6=z[5],
             fgfUseZ1=Q['useZone1'], fgfUseZ2=Q['useZone2'], fgfUseZ3=Q['useZone3'], fgfUseZ4=Q['useZone4'],
             fgfUseZ5=Q['useZone5'], fgfUseZ6=Q['useZone6'], fgfRsiLen=Q['tdiRsiLen'], fgfFastLen=Q['tdiFastLen'],
             fgfMinAligned=Q['minAlignedZones'], fgfFlatParent=Q['allowNeutralParent'],
             fgfIgnoreNa=Q['ignoreNaZones'], fgfHtfClosed=Q['htfNoRepaint'], fgfUseZones=Q['useTdiTradeZone'],
             fgfSpreadPts=Q['spreadPoints'], fgfHoldBars=Q['entryHoldBars'], fgfHoldFavPts=Q['entryHoldMinFavPoints'],
             fgfOnePerBar=Q['oneEntryPerBar'], fgfDistUnit=Q['DistUnit'], fgfBurstAtr=Q['burstAtrMult'],
             fgfHoldFavAtr=Q['holdFavAtrMult'], fgfBurstPts=Q['burstPointsInput'], fgfUseBurst=Q['useBurstGate'],
             fgfAnyCombo=Q['useAnyCombo'], fgfDriftBars=Q['priorDriftBars'], fgfUseDrift=Q['usePriorFilter'])
    return m


def t_signals():
    variants = [{}, {'burstAtrMult': 0.3, 'minAlignedZones': 1}, {'entryHoldBars': 2, 'usePriorFilter': True},
                {'useAnyCombo': True, 'useBurstGate': False, 'burstAtrMult': 0.0},
                {'autoTf': False, 'tdiParentTf': '15', 'zoneTf2': '45', 'zoneTf3': 'D', 'htfNoRepaint': False}]
    for pair, tf in (('BTC', '60'), ('XAU', '15'), ('XAU', '240'), ('BTC', '5')):
        for v in variants:
            Q = C._validate(C._split(v))
            S = C.chart_signals(pair, tf, Q)
            fs = fgf._filter_series(pair, tf, fgf._params(_mapped(tf, Q)))
            ok = np.array_equal(S['buy'], fs['buy']) and np.array_equal(S['sell'], fs['sell'])
            check('signals %s %s %s == fgf._filter_series (every row of the chart file)' % (pair, tf, v or 'defaults'),
                  ok, '%d / %d' % (int(S['buy'].sum()), int(S['sell'].sum())))
        fgf._FILTER.clear()
        C._SIG.clear()
    for pair in ('BTC', 'XAU'):
        S = C.chart_signals(pair, '60', C._validate(C._split({})))
        fsig = fgf.filter_signals(pair, '60')
        b = fsig['buy'].to_numpy(bool)
        s = fsig['sell'].to_numpy(bool)
        check('signals %s 60 defaults == the filter\'s own signals (fgf.filter_signals)' % pair,
              np.array_equal(S['buy'], b) and np.array_equal(S['sell'], s))
    table = {('BTC', '60'): (1882, 1918, 0, 0), ('BTC', '240'): (429, 468, 105, 101), ('XAU', '60'): (851, 847, 0, 0),
             ('XAU', '15'): (3472, 3457, 1996, 2065), ('BTC', '120'): (881, 918, 150, 162)}
    for (pair, tf), (nb, ns, ab, as_) in table.items():
        P = C.prepare(pair, tf, {})
        got = (P['sig_buy'], P['sig_sell'], int((P['buySig'] & P['buyOk']).sum()), int((P['sellSig'] & P['sellOk']).sum()))
        check('counts %s %s == SPEC_fgv5 4.6 (signals, of them allowed)' % (pair, tf), got == (nb, ns, ab, as_), str(got))
    fgf._FILTER.clear()
    C.clear_cache()


# ----------------------------------------------------------------------------------------------
class _MagFake:
    """fgv5 with path 'mag' on one fake sub-bar per bar (for the hand-built scenarios of fgv5_b_check_kernel)."""

    def __getattr__(self, k):
        return getattr(C, k)

    def simulate(self, P, x=None, full=False, log_cap=0):
        x = dict(x or {})
        x['path'] = 'mag'
        return C.simulate(P, x, full=full, log_cap=log_cap, sub=C.fake_sub_bars(P))


def _scenarios(label, mod):
    import fgv5_b_check_kernel as K
    K.M = mod
    K.FAILS.clear()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = K.main()
    lines = [ln for ln in buf.getvalue().splitlines()
             if (ln.startswith('PASS ') or ln.startswith('FAIL ')) and not ln.startswith('FAILS')]
    nf = sum(1 for ln in lines if ln.startswith('FAIL'))
    for ln in lines:
        if ln.startswith('FAIL'):
            print('   ' + ln)
    check('kernel %s: the %d hand-built scenarios of fgv5_b_check_kernel.py' % (label, len(lines)),
          rc == 0 and nf == 0 and len(lines) >= 29)


def _mk_sub(rows_per_bar):
    """rows_per_bar: list (one per chart bar) of lists of (o, h, l, c) sub-bars -> (chart bars, sub table)."""
    bars = []
    ptr = [0]
    so, sh, sl, sc, st = [], [], [], [], []
    for k, rows in enumerate(rows_per_bar):
        for i, (a, b, c_, d) in enumerate(rows):
            so.append(a); sh.append(b); sl.append(c_); sc.append(d); st.append(k * 3600 + i * 60)
        ptr.append(len(so))
        bars.append((rows[0][0], max(r[1] for r in rows), min(r[2] for r in rows), rows[-1][3]))
    f = lambda v: np.asarray(v, np.float64)
    return np.asarray(bars, float), (np.asarray(ptr, np.int64), f(so), f(sh), f(sl), f(sc), np.asarray(st, np.int64))


def _mkP(bars, buy=(), sell=(), atr=500.0, params=None):
    n = len(bars)
    bs = np.zeros(n, bool)
    ss = np.zeros(n, bool)
    bs[list(buy)] = True
    ss[list(sell)] = True
    t_open = np.arange(n, dtype=np.int64) * 3600
    return C.prepare_arrays(bars[:, 0], bars[:, 1], bars[:, 2], bars[:, 3], np.full(n, atr), bs, ss,
                            t_open=t_open, t_close=t_open + 3600, params=params)


def t_kernel():
    _scenarios("'tv'", C)
    _scenarios("'mag' (one fake sub-bar per bar)", _MagFake())
    sig = [(89990, 90010, 89980, 90000)]
    # M1: the stop is reached inside the minutes before the target ('tv' books the target first: SPEC 6.3)
    bars, sub = _mk_sub([sig, [(90050, 90130, 90040, 90120), (90120, 90125, 89990, 90000), (90000, 90400, 90000, 90100)],
                         [(90100, 90120, 90080, 90100)], [(90100, 90110, 90090, 90100)]])
    P = _mkP(bars, buy=[0])
    tt, st_, _ = run_c(P, {})
    tm, sm, _ = run_c(P, {'path': 'mag'}, sub=sub)
    r = tm.iloc[0]
    rt = tt.iloc[0]
    check("mag M1: stop inside the minutes: 'sl' joint at 90,095.125, pnl -660.9406 ('tv': tp_part + 'be')",
          len(tm) == 1 and r.exit_kind == 'sl' and r.exit_bar == 1 and close(r.entry_px, 90125.175)
          and close(r.exit_px, 90095.125) and close(r.pnl_gross, -300.5) and close(r.costs, 360.4406)
          and close(r.pnl, -660.9406) and r.tv_rows == 2 and r.part_kind == ''
          and len(tt) == 1 and rt.part_kind == 'tp_part' and rt.exit_kind == 'be' and close(rt.part_px, 90275.175)
          and close(rt.exit_px * 10, 3 * 90275.175 + 7 * 90099.95))
    # M2: the buy stop is crossed by a jump between two minutes: fill at the next minute's open (+ slippage)
    bars, sub = _mk_sub([sig, [(90050, 90100, 90040, 90100), (90200, 90250, 90190, 90240), (90240, 90260, 90230, 90250)],
                         [(90250, 90260, 90240, 90250)]])
    P = _mkP(bars, buy=[0])
    tt, _, _ = run_c(P, {})
    tm, _, _ = run_c(P, {'path': 'mag'}, sub=sub)
    check("mag M2: entry by a jump between minutes at 90,200.05 (gap), 'end' 90,249.95; 'tv' 90,125.175",
          len(tm) == 1 and close(tm.entry_px[0], 90200.05) and bool(tm.gap[0]) and tm.exit_kind[0] == 'end'
          and close(tm.exit_px[0], 90249.95) and close(tm.pnl_gross[0], 499.0)
          and len(tt) == 1 and close(tt.entry_px[0], 90125.175) and not bool(tt.gap[0]) and close(tt.pnl_gross[0], 1247.75))
    # M3: a Fixed-style trailing stop (armed at the fill, $50) follows the minutes and fills inside the bar
    bars, sub = _mk_sub([sig, [(90050, 90130, 90040, 90120), (90120, 90300, 90110, 90290), (90290, 90295, 90240, 90260)],
                         [(90260, 90270, 90200, 90210)], [(90210, 90215, 90205, 90210)]])
    P = _mkP(bars, buy=[0], params=dict(TpStyle='Fixed', useTrail=True, trailActPips=0.0, trailPips=50.0, tpRPips=0.0))
    tt, _, _ = run_c(P, {})
    tm, _, _ = run_c(P, {'path': 'mag'}, sub=sub)
    # 'tv': the chart bar's rise to 90,300 sets best (trail 90,250) and its close 90,260 stays above it; bar 2
    # (high 90,270 < best) falls through 90,250 -> the same price one bar later
    check("mag M3: Fixed trail in the minutes: 'trail' 90,249.95 on bar 1 ('tv': the same level on bar 2)",
          len(tm) == 1 and tm.exit_kind[0] == 'trail' and tm.exit_bar[0] == 1 and close(tm.exit_px[0], 90249.95)
          and close(tm.pnl_gross[0], 1247.75) and close(tm.costs[0], 360.75025)
          and len(tt) == 1 and tt.exit_kind[0] == 'trail' and tt.exit_bar[0] == 2 and close(tt.exit_px[0], 90249.95))
    # M4: inverted buy limit filled after the bar's high (minute 1) passed the target: the breakeven flag reads the
    # CHART bar's high (V18) -> be_no_tp on 'mag' too: XL2 7 at 89,859.95 ('be'), XL1 3 to 'end'
    bars, sub = _mk_sub([[(90010, 90020, 89990, 90000)],
                         [(90700, 90900, 90650, 90700), (90700, 90710, 89800, 89850)],
                         [(89860, 89870, 89850, 89860)], [(89860, 89870, 89850, 89860)]])
    P = _mkP(bars, sell=[0], params=dict(ExitMode='ATR', slAtrMult=1.0, tpR=1.5, runTrailAtr=1.5))
    tm, sm, _ = run_c(P, {'path': 'mag', 'inv': True}, sub=sub)
    tt, stt, _ = run_c(P, {'inv': True})
    r = tm.iloc[0] if len(tm) else None
    check("mag M4: inverted be_no_tp from the chart bar's high: part 'be' 7 at 89,859.95, XL1 3 'end' 89,859.95",
          len(tm) == 1 and r.dir == 1 and r.entry_type == 'limit' and close(r.entry_px, 89874.875)
          and bool(r.be_no_tp) and r.part_kind == 'be' and close(r.part_qty, 7.0) and close(r.part_px, 89859.95)
          and r.exit_kind == 'end' and sm['be_no_tp'] == 1 and G.cmp_trades(tm, tt)[0])


# ----------------------------------------------------------------------------------------------
def _rand_sims(pair, tf, k, seed):
    rng = random.Random('t|%s|%s|%d' % (pair, tf, seed))
    out = [{}, {'inv': True}]
    while len(out) < k:
        out.append(G._wild_sim(rng, pair, tf) if rng.random() < 0.6 else G._grid_sim(rng, pair, tf))
    return out


def t_mag1():
    for pair in ('XAU', 'BTC'):
        flts = (False, True)
        for flt in flts:
            P = C.prepare(pair, '1', {'fgfOn': flt})
            sims = _rand_sims(pair, '1', 4 if pair == 'XAU' else 3, 1)
            nb = 0
            ntr = 0
            for x in sims:
                tt, stt, _ = run_c(P, dict(x, path='tv'))
                tm, smm, _ = run_c(P, dict(x, path='mag'))
                ntr += len(tt)
                if not (G.cmp_trades(tt, tm)[0] and G.cmp_summary(stt, smm)[0]):
                    nb += 1
            check("mag1 %s 1 filter %s: 'mag' == 'tv' on %d settings (%d trades; sub-bars = the chart bars)"
                  % (pair, 'on' if flt else 'off', len(sims), ntr), nb == 0)
            del P
        fgf._FILTER.clear()
        C.clear_cache()


def t_fake():
    for pair, tf in (('BTC', '60'), ('BTC', '5'), ('BTC', '240'), ('XAU', '60'), ('XAU', '15'), ('XAU', '240')):
        P = C.prepare(pair, tf, {'fgfOn': False})
        fk = C.fake_sub_bars(P)
        nb = 0
        ntr = 0
        for x in _rand_sims(pair, tf, 6, 2):
            tt, stt, Rt = run_c(P, dict(x, path='tv'))
            tm, smm, Rm = run_c(P, dict(x, path='mag'), sub=fk)
            ntr += len(tt)
            if not (G.cmp_trades(tt, tm)[0] and G.cmp_summary(stt, smm)[0] and np.array_equal(Rt['eq'], Rm['eq'])):
                nb += 1
        check("fake %s %s: 'mag' with one fake sub-bar per bar == 'tv' (6 settings, %d trades)" % (pair, tf, ntr), nb == 0)
    C.clear_cache()


# ----------------------------------------------------------------------------------------------
def t_ref():
    import fgv5_ref as REF
    rng = random.Random('fgv5-ref-tests')
    cells = [('BTC', '5'), ('BTC', '15'), ('BTC', '60'), ('BTC', '240'), ('XAU', '5'), ('XAU', '15'), ('XAU', '60'),
             ('XAU', '240')]
    nset = 0
    nb = 0
    ntr = {'tv': 0, 'mag': 0}
    ndiff_paths = 0
    kinds = {}
    while nset < 30:
        pair, tf = cells[nset % len(cells)]
        s0, e0 = C.WINDOWS[pair]
        st = rng.randrange(s0, e0 - 62 * 86400)
        prep = G._wild_prep(rng, pair, tf) if rng.random() < 0.5 else G._grid_prep(rng)
        if 'autoTf' in prep or rng.random() < 0.3:
            prep['fgfOn'] = False
        x = G._wild_sim(rng, pair, tf) if rng.random() < 0.6 else G._grid_sim(rng, pair, tf)
        x.pop('path', None)
        P = C.prepare(pair, tf, dict(prep, start=st, end=st + 61 * 86400))
        sub = C.get_sub(P)
        res = {}
        for path in ('tv', 'mag'):
            xx = dict(x, path=path)
            tc, sc, R = run_c(P, xx)
            tr, cnt, E = REF.ref_simulate(P, xx, sub=sub)
            ok1 = G.cmp_trades(tc[list(tr.columns)], tr)[0]
            okc = all(close(float(sc[a]), float(cnt[b])) for a, b in REF.counters_of(sc))
            ok3 = G.cmp_arrays(R['eq'], E)[0]
            ntr[path] += len(tc)
            for k, v in tc['exit_kind'].value_counts().items():
                kinds[k] = kinds.get(k, 0) + int(v)
            if not (ok1 and okc and ok3):
                nb += 1
                print('   ref differs: %s %s %s %s path %s: trades %s counters %s equity %s'
                      % (pair, tf, G.fmt_setting(prep, x), st, path, ok1, okc, ok3))
            res[path] = tc
        if not G.cmp_trades(res['tv'], res['mag'])[0]:
            ndiff_paths += 1
        nset += 1
        fgf._FILTER.clear()
        C._SIG.clear()
        C._PERM.clear()
    check("ref: canonical == fgv5_ref.py on 30 random settings x 2-month windows, paths 'tv' and 'mag' "
          "(%d / %d trades; 'mag' differs from 'tv' in %d of 30)" % (ntr['tv'], ntr['mag'], ndiff_paths), nb == 0,
          'exit kinds %s' % dict(sorted(kinds.items())))


# ----------------------------------------------------------------------------------------------
def _money_ok(P, t, s, cost):
    pair = P['pair']
    cf, cp = C.COSTS[cost][pair]
    ok = True
    msgs = []
    pnl = t.pnl.to_numpy()
    q = t.qty.to_numpy()
    cst = 2 * cf * q + cp * q * (t.entry_px.to_numpy() + t.exit_px.to_numpy())
    if not np.allclose(t.costs.to_numpy(), cst, rtol=1e-9, atol=1e-7):
        ok = False
        msgs.append('costs')
    g = t.dir.to_numpy() * q * (t.exit_px.to_numpy() - t.entry_px.to_numpy())
    if not np.allclose(t.pnl_gross.to_numpy(), g, rtol=1e-7, atol=1e-6):
        ok = False
        msgs.append('pnl_gross')
    if not np.allclose(pnl, t.pnl_gross.to_numpy() - t.costs.to_numpy(), rtol=1e-12, atol=1e-9):
        ok = False
        msgs.append('pnl')
    if abs(s['final_equity'] - (C.INITIAL_CAPITAL + pnl.sum())) > 1e-9 * max(C.INITIAL_CAPITAL, abs(s['final_equity'])):
        ok = False
        msgs.append('final equity')
    if not close(s['net_pct'], (s['final_equity'] - C.INITIAL_CAPITAL) / C.INITIAL_CAPITAL * 100):
        ok = False
        msgs.append('net')
    first = t.entry_time.to_numpy() <= P['mid']
    eqb = t.eq_before.to_numpy()

    def fair(m):
        if not m.any():
            return 0.0
        if (eqb[m] <= 0).any():
            return float('nan')
        return (np.prod(1 + pnl[m] / eqb[m]) - 1) * 100
    for nm, m in (('h1r_pct', first), ('h2r_pct', ~first)):
        v = fair(m)
        if not ((math.isnan(v) and math.isnan(s[nm])) or close(v, s[nm], 1e-9)):
            ok = False
            msgs.append(nm)
    if s['h1_trades'] != int(first.sum()) or s['h2_trades'] != int((~first).sum()):
        ok = False
        msgs.append('h trades')
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    if len(t) and gl > 0 and not close(s['pf'], gp / gl):
        ok = False
        msgs.append('pf')
    if len(t) and not close(s['win_pct'], (pnl > 0).mean() * 100):
        ok = False
        msgs.append('win')
    if not close(s['costs'], float(t.costs.sum())):
        ok = False
        msgs.append('costs sum')
    # eq_before chain: the cash before each entry = initial + every earlier trade's pnl, minus the open trade's
    # P/L at a reversal (its closing leg is booked first): check where the previous trade closed before this entry
    cash = C.INITIAL_CAPITAL
    for i in range(len(t)):
        if i > 0:
            cash += pnl[i - 1]
        if abs(eqb[i] - cash) > 1e-9 * max(C.INITIAL_CAPITAL, abs(cash)):
            ok = False
            msgs.append('eq_before %d' % i)
            break
    return ok, msgs


def _fills_inside(P, t, slip, sub=None):
    """Raw entry and single-fill exit prices lie inside the bar where they happen (the chart bar's range)."""
    w0 = P['w0']
    h, l, c = P['h'], P['l'], P['c']
    eb = t.entry_bar.to_numpy() - w0
    d = t.dir.to_numpy()
    raw_e = t.entry_px.to_numpy() - np.where(t.entry_type.to_numpy() == 'stop', d * slip, 0.0)
    ok = bool(np.all((raw_e >= l[eb] - 1e-9) & (raw_e <= h[eb] + 1e-9)))
    single = (t.part_kind.to_numpy() == '')
    xb = t.exit_bar.to_numpy() - w0
    k = t.exit_kind.to_numpy()
    stopish = np.isin(k, ['sl', 'be', 'runner', 'trail', 'opp', 'time', 'end'])
    raw_x = t.exit_px.to_numpy() + np.where(stopish, d * slip, 0.0)
    rev = k == 'reverse'
    # a reversal's closing leg is booked at the new entry's booked price: the raw price is that of the next trade
    m = single & ~rev
    ok = ok and bool(np.all((raw_x[m] >= l[xb[m]] - 1e-9) & (raw_x[m] <= h[xb[m]] + 1e-9)))
    endm = (k == 'end') & single
    ok = ok and bool(np.all(np.abs(raw_x[endm] - c[xb[endm]]) < 1e-7))
    return ok


def t_money():
    for pair, tf in (('BTC', '60'), ('XAU', '15'), ('BTC', '15'), ('XAU', '240')):
        P = C.prepare(pair, tf, {'fgfOn': tf != '60'})
        nb = 0
        nrun = 0
        for path in ('tv', 'mag'):
            for cost in ('tv', 'ours', 'stress'):
                for inv in (False, True):
                    for extra in ({}, dict(ExitMode='ATR', slAtrMult=0.5, tpR=3.0, QtyMode='Risk %', riskPct=1.0,
                                           maxQty=1e9, qtyStep=0.000001, maxBarsHeld=12)):
                        x = dict(extra, path=path, cost=cost, inv=inv)
                        t, s, R = run_c(P, x)
                        ok, msgs = _money_ok(P, t, s, cost)
                        ok = ok and _fills_inside(P, t, C.SLIPPAGE[cost])
                        nrun += 1
                        if not ok:
                            nb += 1
                            print('   money differs: %s %s %s %s' % (pair, tf, x, msgs))
        check('money %s %s: halves, costs, P/L, net, pf, win, eq_before chain, fills inside the bar (%d runs)'
              % (pair, tf, nrun), nb == 0)
    C.clear_cache()
    fgf._FILTER.clear()


# ----------------------------------------------------------------------------------------------
def _header_ok(P, t, s, x, path, sub):
    Q = C._resolve_x(P, x)
    slip = C.SLIPPAGE[Q['cost']]
    w0 = P['w0']
    o = P['o']
    msgs = []
    if path == 'mag':
        ptr, so = sub[0], sub[1]

    def opens(bar):
        b = bar - w0
        return so[ptr[b]:ptr[b + 1]] if path == 'mag' else o[b:b + 1]
    for i in range(len(t)):
        r = t.iloc[i]
        d = r.dir
        if r.part_kind == 'tp_part' or (r.exit_kind == 'tp_part'):
            if r.part_kind == 'tp_part':
                px, bar = r.part_px, r.part_bar
            elif r.part_kind == '':
                px, bar = r.exit_px, r.exit_bar
            else:            # XL2 left first (inverted be_no_tp): XL1's own fill from the qty-weighted exit price
                px, bar = (r.exit_px * r.qty - r.part_px * r.part_qty) / (r.qty - r.part_qty), r.exit_bar
            if not (close(px, r.tp_px, 1e-7) or any(close(px, v, 1e-7) and d * (v - r.tp_px) >= 0
                                                     for v in opens(bar))):
                msgs.append('tp_part %d' % i)
        if r.exit_kind == 'sl' and r.part_kind == '' and not r.sl_lt_slip:
            raw = r.exit_px + d * slip
            if not (close(raw, r.sl_px) or any(close(raw, v) and d * (v - r.sl_px) <= 0 for v in opens(r.exit_bar))):
                msgs.append('sl %d' % i)
        if r.exit_kind == 'be' and r.part_kind == 'tp_part':
            # the remainder at breakeven (the entry price), raw = exit price of the 'be' part
            q2 = r.qty - r.part_qty
            bepx = (r.exit_px * r.qty - r.part_px * r.part_qty) / q2
            raw = bepx + d * slip
            if not (close(raw, r.entry_px, 1e-7) or any(close(raw, v, 1e-7) and d * (v - r.entry_px) <= 0
                                                       for v in opens(r.exit_bar))):
                msgs.append('be %d' % i)
        if r.exit_kind == 'time' and Q['maxBarsHeld'] > 0:
            if r.exit_bar - r.entry_bar != Q['maxBarsHeld'] + 1:
                msgs.append('time %d' % i)
    if not Q['fgvInv'] and s['be_no_tp'] != 0:
        msgs.append('be_no_tp normal')
    if Q['QtyMode'] == 'Risk %':
        # placements while flat: equity = initial + the P/L of every trade that closed by the placing bar's close
        pnl = t.pnl.to_numpy()
        xb = t.exit_bar.to_numpy()
        eb = t.entry_bar.to_numpy()
        nchk = 0
        for i in range(len(t)):
            sb = t.sig_bar.iloc[i]
            if i > 0 and not (xb[:i] <= sb).all():
                continue                       # a position was open at the placing bar's close
            if i > 0 and (eb[:i] > sb).any():
                continue
            eq = C.INITIAL_CAPITAL + pnl[:i][xb[:i] <= sb].sum()
            sld = t.sl_dist.iloc[i]
            q = eq * Q['riskPct'] / 100.0 / (sld * C.POINTVALUE) if sld > 0 else 0.0
            q = min(q, Q['maxQty'])
            q = math.floor(q / Q['qtyStep'] + 1e-9) * Q['qtyStep']
            nchk += 1
            if not close(q, t.qty.iloc[i], 1e-9):
                msgs.append('qty %d (%r vs %r)' % (i, q, t.qty.iloc[i]))
                break
        if nchk == 0:
            msgs.append('no flat Risk % placement checked')
    return msgs


def t_header():
    cases = [dict(), dict(inv=True), dict(maxBarsHeld=5), dict(maxBarsHeld=5, inv=True),
             dict(ExitMode='ATR', slAtrMult=1.0, tpR=1.5, QtyMode='Risk %', riskPct=1.0, maxQty=1e9, qtyStep=0.000001,
                  allowReverse=False),
             dict(ExitMode='ATR', slAtrMult=0.5, tpR=3.0, QtyMode='Risk %', riskPct=1.0, maxQty=1e9, qtyStep=0.000001,
                  allowReverse=False, inv=True, maxBarsHeld=12),
             dict(ExitMode='Points', slPoints=20000, tpPoints=40000, runBE=True, partPct=50, cost='ours')]
    for pair, tf in (('BTC', '60'), ('BTC', '15'), ('XAU', '15'), ('XAU', '240')):
        P = C.prepare(pair, tf, {'fgfOn': False})
        sub = C.get_sub(P)
        nb = 0
        nt = 0
        for x in cases:
            for path in ('tv', 'mag'):
                xx = dict(x, path=path)
                t, s, R = run_c(P, xx)
                nt += len(t)
                msgs = _header_ok(P, t, s, xx, path, sub)
                if msgs:
                    nb += 1
                    print('   header differs: %s %s %s %s' % (pair, tf, xx, msgs[:5]))
        check("header %s %s: (i) tp_part / sl fills, (ii) Risk %% qty, (iii) time exits, (iv) be fills, (v) be_no_tp, "
              "paths tv / mag (%d runs, %d trades)" % (pair, tf, 2 * len(cases), nt), nb == 0)
    C.clear_cache()


# ----------------------------------------------------------------------------------------------
_SWAP = {'sl': 'tp', 'tp': 'sl'}


def _mirror_ok(tn, ti):
    if len(tn) != len(ti):
        return False, 'counts %d vs %d' % (len(tn), len(ti))
    a = tn.copy()
    a['dir'] = -a['dir']
    a['pnl_gross'] = -a['pnl_gross']
    a['exit_kind'] = [_SWAP.get(k, k) for k in a['exit_kind']]
    a['part_kind'] = [_SWAP.get(k, k) for k in a['part_kind']]
    a['entry_type'] = ['limit' if k == 'stop' else 'stop' for k in a['entry_type']]
    a = a.drop(columns=['pnl', 'eq_before', 'r_mult', 'sl_px', 'tp_px'])
    b = ti.drop(columns=['pnl', 'eq_before', 'r_mult', 'sl_px', 'tp_px'])
    ok, msg, _ = G.cmp_trades(a, b)
    ok = ok and np.allclose(tn.sl_px.fillna(0).to_numpy(), ti.tp_px.fillna(0).to_numpy(), rtol=1e-12) \
        and np.allclose(tn.tp_px.fillna(0).to_numpy(), ti.sl_px.fillna(0).to_numpy(), rtol=1e-12)
    ok = ok and np.allclose(ti.pnl.to_numpy(), -tn.pnl_gross.to_numpy() - tn.costs.to_numpy(), rtol=1e-9, atol=1e-7)
    return ok, msg


def t_inv():
    # P1 exact mirror
    p1 = [dict(ExitMode='ATR', slAtrMult=0.5, tpR=1.0), dict(ExitMode='Points', slPoints=30000, tpPoints=30000),
          dict(ExitMode='Pips', slPips=100, tpRPips=1.0), dict(ExitMode='ATR', slAtrMult=1.0, tpR=1.0, exitOnOpposite=True),
          dict(ExitMode='ATR', slAtrMult=1.0, tpR=1.0, maxBarsHeld=6, entryValidBars=0),
          dict(ExitMode='Pips', slPips=50, tpRPips=1.0, entryValidBars=1, allowReverse=False),
          dict(ExitMode='ATR', slAtrMult=2.0, tpR=1.0, exitOnOpposite=True, allowReverse=False, maxBarsHeld=3)]
    for pair, tf, flt in (('BTC', '60', False), ('BTC', '15', True), ('XAU', '60', False), ('XAU', '15', True)):
        P = C.prepare(pair, tf, {'fgfOn': flt})
        nb = 0
        nt = 0
        for path in ('tv', 'mag'):
            for x in p1:
                base = dict(x, TpStyle='Fixed', useTrail=False, QtyMode='Fixed', Direction='Both', cost='ours', path=path)
                tn, _, _ = run_c(P, dict(base, inv=False))
                ti, _, _ = run_c(P, dict(base, inv=True))
                nt += len(tn)
                ok, msg = _mirror_ok(tn, ti)
                if not ok:
                    nb += 1
                    print('   P1 differs: %s %s %s %s' % (pair, tf, base, msg))
        check('inv P1 %s %s filter %s: exact mirror (Fixed, symmetric bracket, cost ours) on %d runs x paths tv / mag '
              '(%d trades)' % (pair, tf, 'on' if flt else 'off', len(p1), nt), nb == 0)
    # P2 single decisions
    import fgv5_b  # noqa: F401  (only to be sure the API is the same)
    rng = random.Random(5)
    for pair, tf, flt in (('BTC', '60', False), ('XAU', '15', True)):
        P = C.prepare(pair, tf, {'fgfOn': flt})
        idx = np.flatnonzero(P['buySig'] | P['sellSig'])
        nd = 0
        nb = 0
        for _ in range(60):
            k = int(rng.choice(idx))
            for opts in (dict(), dict(allowReverse=False), dict(exitOnOpposite=True), dict(Direction='Long'),
                         dict(Direction='Short', exitOnOpposite=True, allowReverse=False)):
                dmap = {'Both': 'Both', 'Long': 'Short', 'Short': 'Long'}
                for p in (-1, 0, 1):
                    out = []
                    for inv, pp, dirn in ((False, p, opts.get('Direction', 'Both')),
                                          (True, -p, dmap[opts.get('Direction', 'Both')])):
                        x = dict(opts, Direction=dirn, inv=inv, ExitMode='ATR', slAtrMult=0.5)
                        CI, CF, bpx, spx, atrl = _cfg(P, x)
                        buf = np.zeros((2, 11))
                        r = C._decide(pp, 100000.0, bool(P['buySig'][k]), bool(P['sellSig'][k]), bool(P['buyOk'][k]),
                                      bool(P['sellOk'][k]), bpx[k], spx[k], P['atr14'][k], atrl[k], CI, CF, buf)
                        out.append((r, buf[:r[1]].copy()))
                    (rn, bn), (ri, bi) = out
                    nd += 1
                    ok = rn == ri and len(bn) == len(bi)
                    if ok:
                        for a, b in zip(bn, bi):
                            ok = ok and a[0] == b[0] and a[1] == 1 - b[1] and a[2] == 1 - b[2] and a[3] == b[3] \
                                and a[4] == b[4] and a[5] == b[5] and np.array_equal(a[6:], b[6:], equal_nan=True)
                    if not ok:
                        nb += 1
        check('inv P2 %s %s: %d single decisions, option on from -p == option off from p mirrored (slot, STOP <-> '
              'LIMIT; price, qty, sig, locks, close, funnel equal; Direction swapped)' % (pair, tf, nd), nb == 0)
    # P3, P4, P5
    for pair, tf in (('BTC', '60'), ('BTC', '5'), ('XAU', '15'), ('XAU', '240')):
        P = C.prepare(pair, tf, {'fgfOn': tf != '60'})
        for path in ('tv', 'mag'):
            tn, _, _ = run_c(P, dict(path=path))
            ti, _, _ = run_c(P, dict(path=path, inv=True))
            ok = len(tn) > 0 and len(ti) > 0 and tn.entry_bar[0] == ti.entry_bar[0] and tn.dir[0] == -ti.dir[0] \
                and close(tn.entry_px[0] - tn.dir[0] * 0.05 * (tn.entry_type[0] == 'stop'), ti.entry_px[0]) \
                and tn.sig_bar[0] == ti.sig_bar[0]
            check('inv P3 %s %s %s: first trade, same bar and raw price, opposite side' % (pair, tf, path), ok)
            tl, _, _ = run_c(P, dict(path=path, Direction='Long'))
            tli, _, _ = run_c(P, dict(path=path, Direction='Long', inv=True))
            ok = (tl.dir == 1).all() and (tl.sig == 1).all() and (tli.dir == 1).all() and (tli.sig == -1).all() \
                and len(tl) > 0 and len(tli) > 0
            check('inv P4 %s %s %s: Direction "Long": dir +1; sig +1 normal, -1 inverted (%d / %d trades)'
                  % (pair, tf, path, len(tl), len(tli)), ok)
    for pair in ('BTC', 'XAU'):
        P = C.prepare(pair, '60', {})
        n = [run_c(P, dict(path=pa, inv=iv))[1]['trades'] for pa in ('tv', 'mag') for iv in (False, True)]
        check('inv P5 %s 60 filter on (defaults): no trade, both directions, both paths' % pair, n == [0, 0, 0, 0])
    # P6
    for pair, tf in (('BTC', '60'), ('XAU', '15'), ('BTC', '240')):
        Pf = C.prepare(pair, tf, {'fgfOn': False})
        Pi = C.prepare(pair, tf, {'fgfOn': True}, _perm=(np.ones(Pf['n'], bool), np.ones(Pf['n'], bool)))
        ok = True
        for x in ({}, {'inv': True}, {'path': 'mag'}, {'path': 'mag', 'inv': True, 'ExitMode': 'ATR'}):
            ta, sa, _ = run_c(Pf, x)
            tb, sb, _ = run_c(Pi, x)
            ok = ok and G.cmp_trades(ta, tb)[0] and G.cmp_summary(sa, sb)[0]
        check('inv P6 %s %s: fgfOn False == fgfOn True with all-True gates injected (4 runs)' % (pair, tf), ok)
    _pine_text_checks()
    C.clear_cache()
    fgf._FILTER.clear()


def _cfg(P, x):
    """CI / CF / entry prices / ATR(atrLen) exactly as simulate() builds them (for _decide)."""
    Q = C._resolve_x(P, x)
    CI, CF, G_, bpx, spx, atrl, partial, inv, slip = C._config(P, Q)
    return CI, CF, bpx, spx, atrl


def _reduce_off(lines):
    """Pine order code of the HEAD file with fgvInv = false: the reading of L1210-1211 ("Option off: ... each
    if fgvInv ... else runs its else branch, which is the previous code")."""
    import re
    out = []
    i = 0
    tern = re.compile(r'fgvInv \? ("[^"]*"|[^:?]+?) : ("[^"]*"|Direction != "[A-Za-z]+"|[A-Za-z]+)')
    while i < len(lines):
        ln = lines[i]
        st = ln.strip()
        ind = len(ln) - len(ln.lstrip())
        if st.startswith('fgvNL') or st.startswith('fgvNS'):
            i += 1
            continue
        if st == 'if fgvInv':
            j = i + 1
            while j < len(lines) and not (lines[j].strip() == 'else' and len(lines[j]) - len(lines[j].lstrip()) == ind):
                j += 1
            k = j + 1
            while k < len(lines) and (not lines[k].strip() or len(lines[k]) - len(lines[k].lstrip()) > ind):
                if lines[k].strip():
                    out.append(lines[k][4:])
                k += 1
            i = k
            continue
        ln = tern.sub(lambda m: m.group(2), ln)
        ln = ln.replace('fgvNL', 'inLong').replace('fgvNS', 'inShort')
        out.append(ln)
        i += 1
    return out


def _pine_text_checks():
    """Option off == the previous version (L1210-1211: the else branches are the 6c59b9f text), and the 6c59b9f
    strategy code == the unfused original apart from the gate and the funnel (SPEC_fgv5 section 1)."""
    repo = '/home/user/master'
    try:
        cur = open(os.path.join(repo, 'FlashGold_v5_Strategy_BTCUSD_FGF.pine')).read().splitlines()
        old = subprocess.run(['git', '-C', repo, 'show', '6c59b9f:FlashGold_v5_Strategy_BTCUSD_FGF.pine'],
                             capture_output=True, text=True, check=True).stdout.splitlines()
        orig = open(os.path.join(repo, 'FlashGold_v5_Strategy_BTCUSD.pine')).read().splitlines()
    except Exception as e:  # noqa: BLE001
        check('inv text: Pine files readable', False, repr(e))
        return

    def code(lines, a, b):
        i = next(k for k, s in enumerate(lines) if a in s)
        j = next(k for k, s in enumerate(lines) if b in s and k > i)
        return [s.strip() for s in lines[i:j] if s.strip() and not s.strip().startswith('//')]
    A_ = '// ============================== STRATEGY: ORDERS'
    B_ = '// ============================== VISUALS'
    c_old, c_orig = code(old, A_, B_), code(orig, A_, B_)
    i0 = next(k for k, ln in enumerate(cur) if A_ in ln)
    i1 = next(k for k, ln in enumerate(cur) if B_ in ln and k > i0)
    red = _reduce_off(cur[i0:i1])
    c_red = [ln.strip() for ln in red if ln.strip() and not ln.strip().startswith('//')]
    check('inv text: the HEAD order code with fgvInv = false (ternaries -> else value, fgvNL / fgvNS -> inLong / '
          'inShort, "if fgvInv ... else" -> the else branch) == the 6c59b9f text, line for line (%d lines)'
          % len(c_red), c_red == c_old, str([ln for ln in c_red if ln not in c_old][:3] + [ln for ln in c_old if ln not in c_red][:3]))
    # 6c59b9f vs the unfused original: only the gate (and fgfBuyOk / fgfSellOk) and the FGD funnel
    d1 = [s for s in c_old if s not in c_orig]
    d2 = [s for s in c_orig if s not in c_old]
    ok = all(('fgfBuyOk' in s) or ('fgfSellOk' in s) or ('fgd' in s.lower()) or s.startswith('bool fgd')
             or s.startswith('plot(') for s in d1) and all(('if buySignal' in s) or ('if sellSignal' in s) for s in d2)
    check('inv text: 6c59b9f order code == the unfused original + "and fgfBuyOk / fgfSellOk" + the FGD funnel '
          '(%d / %d lines differ)' % (len(d1), len(d2)), ok, str(d2[:2]))


# ----------------------------------------------------------------------------------------------
def t_timing():
    P = C.prepare('BTC', '1', {})
    C.simulate(P, {})
    ts = []
    for x in ({}, {'inv': True}, {'ExitMode': 'ATR', 'slAtrMult': 1.0, 'tpR': 1.5, 'partPct': 0, 'runTrailAtr': 6.5}):
        t0 = time.time()
        C.simulate(P, x)
        ts.append(time.time() - t0)
    check("timing: simulate on BTC 1 (1,039,430 bars) path 'tv' after compilation %s s (< 1 s)"
          % ' / '.join('%.3f' % v for v in ts), max(ts) < 1.0)
    del P
    fgf._FILTER.clear()
    C.clear_cache(bars=True)
    for tf in ('60', '5', '1'):
        P = C.prepare('BTC', tf, {'fgfOn': False})
        t0 = time.time()
        C.get_sub(P)
        tsb = time.time() - t0
        C.simulate(P, {'path': 'mag'})
        t0 = time.time()
        C.simulate(P, {'path': 'mag'})
        C.simulate(P, {'path': 'mag', 'inv': True})
        tm = (time.time() - t0) / 2
        check("timing: BTC %s filter off path 'mag' one simulate %.3f s (sub-bar table built once in %.1f s)"
              % (tf, tm, tsb), tm < 3.0)


SECTIONS = dict(recon=t_recon, signals=t_signals, kernel=t_kernel, mag1=t_mag1, fake=t_fake, ref=t_ref,
                money=t_money, header=t_header, inv=t_inv, timing=t_timing)


def main():
    names = sys.argv[1:] or list(SECTIONS)
    t00 = time.time()
    for nm in names:
        t0 = time.time()
        print('== %s' % nm, flush=True)
        SECTIONS[nm]()
        print('   (%s: %.1f s)' % (nm, time.time() - t0), flush=True)
    print('\n%d PASS, %d FAIL (%.0f s)%s' % (NPASS[0], len(FAILS), time.time() - t00,
                                            ('; FAILS: ' + ', '.join(FAILS)) if FAILS else ''))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
