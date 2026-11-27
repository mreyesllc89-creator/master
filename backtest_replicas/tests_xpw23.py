"""tests_xpw23.py: tests of the canonical replica xpw23.py (REPLICA_SPEC.md stage 3, key xpw23).

Usage: python3 -I tests_xpw23.py [section ...]        (no section = all; exit code 1 on any FAIL)

  abc     A == B == canonical (path 'tv'), trade by trade (every column), every summary field and the
          bar-close equity curve, BTC and XAU, charts 240, 60, 15, 5 and 1, full windows: default
          inputs, filter off, inv on (filter on and off), each cost mode, random settings from the
          calibration grid of SPEC_xpw23.md section 9 and random settings outside it (limit mode,
          one-side modes, Points, Risk, ...). Run in child processes, one pair and one group of
          charts at a time (memory on the 1-minute charts).
  mag1    path 'mag' on chart "1" == 'tv', bit for bit (in the chart-1 children)
  timing  prepare / simulate on BTC "1" (in the chart-1 child), mag on other charts
  sub     the 1-minute sub-bars of all 14 cells: every chart bar equals its sub-bars; equal to the
          verified hrd.sub_bars on two cells
  unit    hand-made bars: the worked checks of SPEC_xpw23.md section 5 on both paths, hand-made
          sub-bars where 'mag' must differ from 'tv' in a known way, and the path tie (T16) in each
          of the three places where a (sub-)bar's path is chosen
  fake    'mag' with one fake sub-bar per chart bar (the chart bar itself) == 'tv', bit for bit
  ref     'tv' and 'mag' against the slow pure-Python reference xpw23_magref.py, 32 random settings
          over 2-month windows on 8 cells
  engine  both paths against the verified replica of the trailing-TP file (engine.py; its Bar Magnifier
          kernel sweep_core._run_mag) on the settings where the two Pine files place the same orders
  money   fair halves, each cost mode, the equity curve, drawdown, exposure, exit counts, fifo_exits
          and the R sums against a direct recomputation from the trade list; Risk quantities
          against a direct evaluation of entryQty()
  inv     the properties the Pine header states for "Inverted direction" (Update 1)
  audit   stage 4: the script logic of Pine lines 1645-1799 on hand-made bars, one decision per case, each
          answer worked out by hand from the Pine (the pre-filter gate, the closes, the pending list and
          its ghosts, the reversal bar, one-side mode, the time stop, the trail floors, Risk sizing, ATR)
"""
from __future__ import annotations

import gc
import math
import os
import resource
import subprocess
import sys
import time

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, W)
import reconcile_xpw23_cmp as CMP    # noqa: E402  (installs the memo of xpw_signals / fgf_permissions)
import xpw                            # noqa: E402
import xpw23 as M                     # noqa: E402

feq = CMP.feq
NPASS = 0
NFAIL = 0
LIMIT = "Limit at label price"
EVERY = "every rung (1 Sec to 1 Month)"


def report(ok, name, detail=''):
    global NPASS, NFAIL
    if ok:
        NPASS += 1
    else:
        NFAIL += 1
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, (': ' + detail) if detail else ''), flush=True)
    return ok


def rss_gb():
    """Peak resident memory of THIS process, GB. VmHWM belongs to the process image, so a child started
    by sec_abc reports its own peak (ru_maxrss would carry over the parent's high-water mark)."""
    try:
        with open('/proc/self/status') as fh:
            for ln in fh:
                if ln.startswith('VmHWM:'):
                    return int(ln.split()[1]) / 1048576.0
    except Exception:
        pass
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0


def exact_frames(a, b, skip=()):
    """Two trade frames are equal bit for bit (NaN == NaN)."""
    if len(a) != len(b) or list(a.columns) != list(b.columns):
        return 'shape'
    for c in a.columns:
        if c in skip:
            continue
        x, y = a[c].to_numpy(), b[c].to_numpy()
        if x.dtype.kind == 'f':
            ok = (x == y) | (np.isnan(x) & np.isnan(y))
        else:
            ok = x == y
        if not np.all(ok):
            return c
    return ''


def exact_summ(a, b, skip=('path',)):
    for k, v in a.items():
        if k in skip:
            continue
        w = b[k]
        if isinstance(v, float) and isinstance(w, float) and math.isnan(v) and math.isnan(w):
            continue
        if v != w:
            return k
    return ''


def both_paths_equal(P, x):
    """simulate(tv) and simulate(mag) on P (whatever P['sub'] is) are equal bit for bit."""
    xa = dict(x)
    xa['path'] = 'tv'
    xb = dict(x)
    xb['path'] = 'mag'
    Ra, Rb = M.simulate(P, xa), M.simulate(P, xb)
    ta, tb = M.trades(P, Ra), M.trades(P, Rb)
    bad = exact_frames(ta, tb) or exact_summ(M.summary(P, Ra), M.summary(P, Rb))
    if not bad and not np.array_equal(Ra['eq'], Rb['eq']):
        bad = 'equity curve'
    return bad, len(ta)


# =========================================================================================== abc
def three_way(pair, tf, cases, MA, MB):
    """A == canonical and B == canonical on every case. Returns (settings, trades, list of diffs)."""
    diffs = []
    nset = ntr = 0
    for kind, pp, sims in cases:
        gc.collect()
        if str(tf) == '1':
            # a 1-minute chart: one xpw_signals call peaks near 2.4 GB, so nothing else may be held
            # while it runs (the caches are pure memo: results do not change)
            if not any(k[0] == 'sig' and CMP._key(pair, str(tf), M.WINDOWS[pair][0], M.WINDOWS[pair][1],
                                                   {q: v for q, v in pp.items() if q in xpw.DEFAULTS}, {}) == k[1:]
                       for k in CMP._memo):
                CMP._memo.clear()
                MA._SIG_CACHE.clear()
                M.free_caches()
        PC = M.prepare(pair, tf, pp)
        PA = MA.prepare(pair, tf, pp)
        PB = MB.prepare(pair, tf, pp)
        for nm, PX in (('A', PA), ('B', PB)):
            pbad = [k for k in CMP.P_ARRAYS if not np.array_equal(np.asarray(PX[k]), np.asarray(PC[k]))]
            pbad += [k for k in CMP.P_SCALARS if PX[k] != PC[k]]
            if pbad:
                diffs.append('%s prepare %r: P differs in %s' % (nm, pp, pbad))
        for x in sims:
            RC = M.simulate(PC, x, full=True)
            tc, sc = M.trades(PC, RC), M.summary(PC, RC)
            nset += 1
            ntr += len(tc)
            for nm, MX, PX in (('A', MA, PA), ('B', MB, PB)):
                RX = MX.simulate(PX, x, full=True)
                tx, sx = MX.trades(PX, RX), MX.summary(PX, RX)
                nbad, desc, cols = CMP.cmp_frames(tx, tc)
                sbad, keys = CMP.cmp_summ(sx, sc)
                eok = feq(CMP.curve(MX, RX), RC['eq'])
                if nbad or sbad or not eok.all():
                    diffs.append('%s != canonical [%s] prep=%r x=%r: %d trades differ (%s); summary %s; equity bars %d'
                                 % (nm, kind, pp, x, nbad, desc, sbad, int((~eok).sum())))
        del PA, PB, PC
    return nset, ntr, diffs


def child(pair, tfs):
    import importlib
    MA = importlib.import_module('xpw23_a')
    MB = importlib.import_module('xpw23_b')
    for tf in tfs:
        rng = np.random.default_rng([2311, sum(map(ord, pair)), sum(map(ord, str(tf)))])
        one = str(tf) == '1'
        npr = 2 if one else 3
        t_prep = None
        if one:
            # timing of the first prepare of the cell (signals + filter), before anything is cached
            t0 = time.time()
            P1 = M.prepare(pair, '1')
            t_prep = time.time() - t0
            del P1
            print('     (peak RSS after the first prepare of %s 1: %.2f GB)' % (pair, rss_gb()), flush=True)
        cases = [('base', {}, CMP.BASE_SIMS), ('base', {'fgfOn': False}, CMP.BASE_SIMS)]
        for _ in range(npr):
            cases.append(('grid', CMP.grid_prep(rng), [CMP.grid_sim(rng) for _ in range(5)]))
        for _ in range(npr):
            cases.append(('extra', CMP.extra_prep(rng), [CMP.extra_sim(rng, pair) for _ in range(5)]))
        t0 = time.time()
        nset, ntr, diffs = three_way(pair, tf, cases, MA, MB)
        report(not diffs, 'abc %s %s: A == B == canonical on %d settings (12 base, %d grid, %d extra), %d trades '
               '[%.0fs]' % (pair, tf, nset, 5 * npr, 5 * npr, ntr, time.time() - t0), ' | '.join(diffs[:3]))
        if one:
            mag1_and_timing(pair, t_prep)
        CMP._memo.clear()
        xpw.clear_cache()
        gc.collect()
    report(rss_gb() < 3.0, 'memory %s %s: peak RSS of this process %.2f GB (limit 3 GB)' % (pair, ' '.join(tfs), rss_gb()))


def mag1_and_timing(pair, t_prep):
    """Chart "1": path 'mag' (sub-bars read from the 1-minute file through the sub-bar mapping) must be
    'tv' bit for bit; and the speed limits of REPLICA_SPEC.md on the 1-minute chart."""
    for pp in ({}, {'fgfOn': False}):
        P = M.prepare(pair, '1', pp)
        sub = M.get_sub(P)
        ok_map = (len(sub[1]) == P['n'] and np.array_equal(sub[0], np.arange(P['n'] + 1)))
        report(ok_map, 'mag1 %s 1 %r: one sub-bar per chart bar (%d)' % (pair, pp, len(sub[1])))
        bad = []
        ntr = 0
        sims = [{}, {'xpwInv': True, 'cost': 'ours'}, {'entryFill': LIMIT}, {'entryFill': LIMIT, 'xpwInv': True},
                {'timeStop': 24, 'maxOpen': 3, 'cost': 'stress'}, {'trailOn': False, 'tpRMult': 4.0, 'slAtrMult': 6.0},
                {'qtyMode': 'Risk', 'riskPct': 0.5, 'entryFill': LIMIT, 'limitBars': 12}]
        for x in sims:
            b, nt = both_paths_equal(P, x)
            ntr += nt
            if b:
                bad.append('%r: %s' % (x, b))
        report(not bad, 'mag1 %s 1 %r: mag == tv bit for bit on %d settings, %d trades' % (pair, pp, len(sims), ntr),
               ' | '.join(bad))
        if not pp:
            def best(x, k=3):
                ts = []
                for _ in range(k):
                    t0 = time.time()
                    R = M.simulate(P, x)
                    ts.append(time.time() - t0)
                return min(ts), R
            heavy = {'trailOn': False, 'tpRMult': 0.0, 'slAtrMult': 6.0}
            out = []
            worst = 0.0
            for nm, x in (('default', {}), ('inverted', {'xpwInv': True}), ('limit', {'entryFill': LIMIT}),
                          ('no trail, no target, stop 6 ATR', heavy)):
                for path in ('tv', 'mag'):
                    xx = dict(x)
                    xx['path'] = path
                    t, R = best(xx)
                    worst = max(worst, t)
                    out.append('%s %s %.3fs' % (nm, path, t))
            t0 = time.time()
            s = M.summary(P, R)
            ts = time.time() - t0
            report(worst < 1.0, 'timing %s 1 (%d bars): one simulate under 1 s on both paths (worst %.3fs)' % (
                pair, P['n'], worst), '; '.join(out) + '; summary %.3fs' % ts)
            report(t_prep < 120.0, 'timing %s 1: first prepare %.1fs (limit 120 s)' % (pair, t_prep))
        del P
        gc.collect()
    M.free_caches()


def sec_abc():
    """Children, one at a time: each prints its own PASS / FAIL lines."""
    global NPASS, NFAIL
    for pair in ('XAU', 'BTC'):
        for tfs in (('240', '60', '15', '5'), ('1',)):
            r = subprocess.run([sys.executable, '-I', os.path.abspath(__file__), '--child', pair] + list(tfs),
                               capture_output=True, text=True)
            for ln in r.stdout.splitlines():
                print(ln, flush=True)
                if ln.startswith('PASS '):
                    NPASS += 1
                elif ln.startswith('FAIL '):
                    NFAIL += 1
            if r.returncode not in (0, 1) or 'CHILD DONE' not in r.stdout:
                report(False, 'abc child %s %s ended abnormally (code %d)' % (pair, tfs, r.returncode),
                       r.stderr[-800:])


# =========================================================================================== sub
def sec_sub():
    for pair in ('BTC', 'XAU'):
        for tf in ('1', '5', '15', '30', '60', '120', '240'):
            b = M.read_bars(pair, tf)
            st, en = M.WINDOWS[pair]
            w0 = int(np.searchsorted(b['t_close'], st, side='left'))
            w1 = int(np.searchsorted(b['t_close'], en, side='right'))
            sl = slice(w0, w1)
            try:
                sub = M.sub_bars(pair, b['t_open'][sl], b['t_close'][sl], b['open'][sl], b['high'][sl], b['low'][sl],
                                 b['close'][sl], check=True)
                ln = np.diff(sub[0])
                ok = bool(ln.min() >= 1)
                inside = bool(((b['low'][sl] <= b['open'][sl]) & (b['low'][sl] <= b['close'][sl])
                               & (b['high'][sl] >= b['open'][sl]) & (b['high'][sl] >= b['close'][sl])).all())
                det = '%d chart bars, %d sub-bars (%d to %d per bar)' % (w1 - w0, len(sub[1]), ln.min(), ln.max())
                if tf == '1':
                    ok = ok and int(ln.max()) == 1
            except ValueError as e:
                ok, inside, det = False, False, str(e)
            report(ok and inside, 'sub %s %s: every chart bar equals its 1-minute sub-bars (first open, highest high, '
                   'lowest low, last close); open / close inside [low, high]' % (pair, tf), det)
            del b
    import hrd
    for pair, tf in (('XAU', '240'), ('BTC', '60')):
        P = M.prepare(pair, tf, {'fgfOn': False})
        sub = M.get_sub(P)
        ref = hrd.sub_bars(pair, tf, P['w0'], P['w1'])
        ok = all(np.array_equal(sub[i], ref[i]) for i in range(5))
        report(ok, 'sub %s %s: equal to the verified hrd.sub_bars (ptr and the four price arrays)' % (pair, tf))
    hrd._BARS.clear() if hasattr(hrd, '_BARS') else None


# =========================================================================================== unit
PTS = dict(exitUnit='Points', slPtsIn=300.0, tpPtsIn=300.0, trActPts=100.0, trDistPts=75.0)


def _sub_of(groups):
    """groups: per chart bar a list of (o, h, l, c) sub-bars -> P['sub'] tuple."""
    ptr = [0]
    so, sh, sl, sc, qlo, qhi = [], [], [], [], [], []
    for g in groups:
        for (o_, h_, l_, c_) in g:
            so.append(o_)
            sh.append(h_)
            sl.append(l_)
            sc.append(c_)
        ptr.append(len(so))
        qlo.append(min(z[2] for z in g))
        qhi.append(max(z[1] for z in g))
    f = lambda a: np.ascontiguousarray(np.array(a, np.float64))      # noqa: E731
    return (np.array(ptr, np.int64), f(so), f(sh), f(sl), f(sc), f(qlo), f(qhi))


def _bars_of(groups):
    return [(g[0][0], max(z[1] for z in g), min(z[2] for z in g), g[-1][3]) for g in groups]


def _hand(groups, x, nLong=None, nShort=None, **kw):
    bars = _bars_of(groups)
    o, h, l, c = (np.array([b[i] for b in bars]) for i in range(4))
    P = M.make_P(o, h, l, c, nLong=nLong, nShort=nShort, **kw)
    P['sub'] = _sub_of(groups)
    out = {}
    for path in ('tv', 'mag'):
        xx = dict(PTS)
        xx.update(x)
        xx['path'] = path
        R = M.simulate(P, xx)
        out[path] = M.trades(P, R)
    return out


def _is(t, i, kind, px, bar=None):
    r = t.iloc[i]
    return r['exit_kind'] == kind and abs(r['exit_px'] - px) < 1e-9 and (bar is None or r['exit_bar'] == bar)


def sec_unit():
    E = (99.0, 100.5, 98.9, 100.0)                  # bar 0: closes at 100.00 with one long label -> fill 100.00
    # --- the four worked checks of SPEC_xpw23.md section 5 (one sub-bar per chart bar: both paths)
    t = _hand([[E], [(100.20, 101.60, 99.90, 100.50)]], {}, nLong=[1, 0])
    report(all(_is(t[p], 0, 'trail', 100.85, 1) for p in t), 'unit worked check 1: O 100.20 H 101.60 L 99.90 C 100.50 '
           '-> trail at 100.85 (both paths)')
    t = _hand([[E], [(100.20, 103.40, 100.10, 103.20)]], {}, nLong=[1, 0])
    report(all(_is(t[p], 0, 'tp', 103.00, 1) for p in t), 'unit worked check 2: O 100.20 H 103.40 L 100.10 C 103.20 '
           '-> tp at 103.00 (both paths)')
    t = _hand([[E], [(96.50, 96.80, 96.00, 96.20)]], {}, nLong=[1, 0])
    report(all(_is(t[p], 0, 'sl', 96.50, 1) for p in t), 'unit worked check 3: open 96.50 below the stop -> sl at the '
           'open 96.50 (both paths)')
    t = _hand([[E], [(100.20, 100.90, 99.00, 99.50)], [(99.40, 99.60, 98.00, 98.20)], [(98.2, 98.3, 98.1, 98.2)]],
              {'timeStop': 2}, nLong=[1, 0, 0, 0])
    report(all(_is(t[p], 0, 'time', 98.20, 2) for p in t), 'unit worked check 4: time stop 2 -> closed at 98.20 on the '
           'second bar after the fill (both paths)')
    # --- hand-made sub-bars where the 1-minute path must differ from the chart-bar path
    # chart bar O 100.20 H 103.40 L 100.10 C 103.20: tv = low first, then the rise to the target 103.00.
    # minutes: (100.20, 101.80, 100.10, 101.00) arms the trail at 101.80 and falls back through 101.05.
    g = [[E], [(100.20, 101.80, 100.10, 101.00), (101.00, 103.40, 100.90, 103.20)]]
    t = _hand(g, {}, nLong=[1, 0])
    report(_is(t['tv'], 0, 'tp', 103.00, 1) and _is(t['mag'], 0, 'trail', 101.05, 1),
           'unit mag 1: tv = tp 103.00; minutes arm the trail at 101.80 and stop it at 101.05 (trail)')
    # a stop jumped over between two minutes fills at the next minute's open, not at the stop
    g = [[E], [(100.20, 100.30, 100.00, 100.10), (96.50, 96.60, 96.00, 96.20)]]
    t = _hand(g, {}, nLong=[1, 0])
    report(_is(t['tv'], 0, 'sl', 97.00, 1) and _is(t['mag'], 0, 'sl', 96.50, 1),
           'unit mag 2: tv = sl at 97.00; the minute opens at 96.50 below the stop: sl at 96.50')
    # a target jumped over between two minutes fills at the next minute's open
    g = [[E], [(100.20, 100.40, 100.10, 100.30), (103.60, 103.80, 103.50, 103.70)]]
    t = _hand(g, {'trailOn': False}, nLong=[1, 0])
    report(_is(t['tv'], 0, 'tp', 103.00, 1) and _is(t['mag'], 0, 'tp', 103.60, 1),
           'unit mag 3: tv = tp at 103.00; the minute opens at 103.60 above the target: tp at 103.60')
    # the order of the extremes: chart bar says high first (stop survives until the low: sl), minutes
    # say the low came first (sl at once, no difference in price) -- and the opposite case:
    # chart bar O 100 H 100.9 L 99.1 C 100.8: tie-free: (h-o)=0.9 < (o-l)=0.9? no (equal) -> low first.
    g = [[E], [(100.00, 100.95, 99.95, 100.90), (100.90, 101.00, 97.50, 100.80)]]
    t = _hand(g, {'trActPts': 90.0, 'trDistPts': 50.0}, nLong=[1, 0])
    # tv: O 100 H 101 L 97.5 C 100.8 -> (1.0 < 2.5) high first: arms at 101.00 (act 100.90), stop 100.50, falls: trail 100.50
    # mag: minute 1 low first then 100.95 arms (best 100.95), close 100.90 > 100.45; minute 2: 100.90 -> 101.00 (best
    #      101.00) -> 97.50 meets 100.50: trail 100.50 as well; same price here
    report(_is(t['tv'], 0, 'trail', 100.50, 1) and _is(t['mag'], 0, 'trail', 100.50, 1),
           'unit mag 4: trail ratchets across two minutes (best 100.95 then 101.00): trail at 100.50 on both paths')
    # limit mode: pending buy limit at the label candle's low 98.90; next chart bar O 99.5 H 99.6 L 98.0 C 98.5
    L0 = (99.0, 100.5, 98.9, 100.0)
    g = [[L0], [(99.50, 99.60, 99.20, 99.30), (98.60, 98.70, 98.00, 98.50)]]
    t = _hand(g, {'entryFill': LIMIT, 'slPtsIn': 300.0, 'tpPtsIn': 0.0, 'trailOn': False}, nLong=[1, 0])
    a, b = t['tv'].iloc[0], t['mag'].iloc[0]
    report(abs(a['entry_px'] - 98.90) < 1e-9 and a['entry_bar'] == 1 and abs(b['entry_px'] - 98.60) < 1e-9
           and b['entry_bar'] == 1 and a['exit_kind'] == 'end' and b['exit_kind'] == 'end',
           'unit mag 5: buy limit 98.90: tv fills at 98.90 on the way down; the minute opens at 98.60 through it: '
           'fill at 98.60')
    # the same inverted: a sell stop at 98.90, same fills; its stop is above (98.60 + 3.00), target off
    t = _hand(g, {'entryFill': LIMIT, 'slPtsIn': 300.0, 'tpPtsIn': 0.0, 'trailOn': False, 'xpwInv': True}, nLong=[1, 0])
    a, b = t['tv'].iloc[0], t['mag'].iloc[0]
    report(a['dir'] == -1 and b['dir'] == -1 and abs(a['entry_px'] - 98.90) < 1e-9 and abs(b['entry_px'] - 98.60) < 1e-9
           and abs(b['sl_px'] - 101.60) < 1e-9 and a['id'] == 'S0-1',
           'unit mag 6: inverted, the sell stop at 98.90 fills where the limit would (98.90 tv, 98.60 mag), id S0-1, '
           'stop above at 101.60')
    # a pending entry filled in one minute and stopped in a later minute of the same chart bar
    g = [[L0], [(99.50, 99.60, 98.80, 99.00), (99.00, 99.10, 95.50, 95.80)]]
    t = _hand(g, {'entryFill': LIMIT, 'slPtsIn': 300.0, 'tpPtsIn': 0.0, 'trailOn': False}, nLong=[1, 0])
    report(all(abs(t[p].iloc[0]['entry_px'] - 98.90) < 1e-9 and _is(t[p], 0, 'sl', 95.90, 1) for p in t)
           and int(t['mag'].iloc[0]['entry_bar']) == 1,
           'unit mag 7: limit filled at 98.90 in minute 1, stopped at 95.90 in minute 2 of the same chart bar')
    # T6 stays on the chart bar: the label candle closes at its low -> the pending entry fills at that close
    g = [[(99.0, 100.5, 98.9, 98.9)], [(98.9, 99.0, 98.8, 98.95)]]
    t = _hand(g, {'entryFill': LIMIT, 'slPtsIn': 0.0, 'tpPtsIn': 0.0, 'trailOn': False}, nLong=[1, 0])
    report(all(int(t[p].iloc[0]['entry_bar']) == 0 and abs(t[p].iloc[0]['entry_px'] - 98.9) < 1e-9
               and bool(t[p].iloc[0]['fill_at_close']) for p in t),
           'unit T6: the label candle closes at its low: the limit fills at that close (both paths)')
    # --- entryQty() (Pine 1698-1705): the order of operations. Rounded DOWN to the step first, capped after.
    t = _hand([[E], [(100.0, 100.1, 99.9, 100.0)]], {'qtyFixed': 0.3, 'qtyStep': 0.25, 'qtyMax': 0.2}, nLong=[1, 0])
    report(all(len(t[p]) == 1 and abs(t[p].iloc[0]['qty'] - 0.2) < 1e-12 for p in t),
           'unit qty 1: Fixed 0.3, step 0.25, max 0.2 -> floor to 0.25, then the cap: 0.2 (cap first would round to 0)')
    Pq = M.make_P(np.array([99.0, 100.0]), np.array([100.5, 100.1]), np.array([98.9, 99.9]), np.array([100.0, 100.0]),
                  nLong=[1, 0])
    Rq = M.simulate(Pq, dict(PTS, qtyFixed=0.1, qtyStep=0.25))
    sq = M.summary(Pq, Rq)
    report(sq['trades'] == 0 and sq['skipped_qty'] == 1 and sq['placed'] == 0,
           'unit qty 2: Fixed 0.1 with step 0.25 rounds to 0: nothing is placed (skipped_qty 1)')
    t = _hand([[E], [(100.0, 100.1, 99.9, 100.0)]], {'qtyMode': 'Risk', 'riskPct': 1.0, 'qtyMax': 50.0}, nLong=[1, 0])
    #     equity 10,000 x 1 % / (300 ticks x 0.01) = 33.333..., step 0.01 -> 33.33
    report(all(abs(t[p].iloc[0]['qty'] - 33.33) < 1e-9 for p in t),
           'unit qty 3: Risk 1 % of 10,000 over a 300-tick stop = 33.333 -> 33.33 (step 0.01)')
    t = _hand([[E], [(100.0, 100.1, 99.9, 100.0)]], {'qtyMode': 'Risk', 'riskPct': 1.0}, nLong=[1, 0])
    report(all(abs(t[p].iloc[0]['qty'] - 2.0) < 1e-12 for p in t), 'unit qty 4: the same with the default max 2.0 -> 2.0')
    t = _hand([[E], [(100.0, 100.1, 99.9, 100.0)]], {'qtyMode': 'Risk', 'riskPct': 1.0, 'slPtsIn': 0.0, 'qtyFixed': 0.07},
              nLong=[1, 0])
    report(all(abs(t[p].iloc[0]['qty'] - 0.07) < 1e-12 for p in t),
           'unit qty 5: Risk without a stop loss falls back to the fixed quantity (0.07)')
    # --- T4, a level that is touched exactly is filled (limit: backtest_fill_limits_assumption 0; stop alike)
    t = _hand([[E], [(100.25, 103.00, 100.125, 102.50)]], {'trailOn': False}, nLong=[1, 0])
    report(all(_is(t[p], 0, 'tp', 103.00, 1) for p in t), 'unit touch 1: the high equals the target 103.00 -> tp at '
           '103.00 (both paths)')
    t = _hand([[E], [(100.25, 100.375, 97.00, 97.50)]], {'trailOn': False}, nLong=[1, 0])
    report(all(_is(t[p], 0, 'sl', 97.00, 1) for p in t), 'unit touch 2: the low equals the stop 97.00 -> sl at 97.00 '
           '(both paths)')
    g = [[(99.0, 100.5, 98.75, 100.0)], [(99.50, 99.625, 98.75, 99.25)]]
    t = _hand(g, {'entryFill': LIMIT, 'slPtsIn': 0.0, 'tpPtsIn': 0.0, 'trailOn': False}, nLong=[1, 0])
    report(all(len(t[p]) == 1 and abs(t[p].iloc[0]['entry_px'] - 98.75) < 1e-12 and int(t[p].iloc[0]['entry_bar']) == 1
               for p in t),
           'unit touch 3: the next low equals the pending buy limit 98.75 -> filled at 98.75 (both paths)')
    # --- T16, the path tie (high - open == open - low): open -> LOW -> high -> close, in each of the three
    #     places where a (sub-)bar's path is chosen. Prices are binary fractions, so the tie is exact.
    # (a) a trade open before the bar: O 100.00 H 103.50 L 96.50: low first = the stop 97.00; high first would
    #     be the target 103.00. As a chart bar (both paths) and as the second minute of a chart bar (mag).
    t = _hand([[E], [(100.00, 103.50, 96.50, 100.00)]], {'trailOn': False}, nLong=[1, 0])
    report(all(_is(t[p], 0, 'sl', 97.00, 1) for p in t),
           'unit T16 a: tie bar O 100.00 H 103.50 L 96.50 -> low first: sl at 97.00, not tp at 103.00 (both paths)')
    g = [[E], [(100.25, 100.50, 100.00, 100.00), (100.00, 103.50, 96.50, 100.00)]]
    t = _hand(g, {'trailOn': False}, nLong=[1, 0])
    #    tv: the chart bar O 100.25 H 103.50 L 96.50 is no tie: (3.25 < 3.75) high first -> tp 103.00
    report(_is(t['tv'], 0, 'tp', 103.00, 1) and _is(t['mag'], 0, 'sl', 97.00, 1),
           'unit T16 a2: the tie is in the second minute: mag = sl at 97.00 (low first inside the minute); the chart '
           'bar itself is no tie and goes high first: tv = tp at 103.00')
    # (b) a pending entry: buy limit 98.90, tie bar O 99.50 H 100.25 L 98.75 C 99.375: low first = filled on the
    #     first leg and its target 99.90 (100 pts) is reached on the way up; high first = filled on the second
    #     leg, the close 99.375 stays below the target
    g = [[L0], [(99.50, 100.25, 98.75, 99.375)], [(99.375, 99.50, 99.25, 99.375)]]
    t = _hand(g, {'entryFill': LIMIT, 'slPtsIn': 300.0, 'tpPtsIn': 100.0, 'trailOn': False}, nLong=[1, 0, 0])
    report(all(abs(t[p].iloc[0]['entry_px'] - 98.90) < 1e-9 and _is(t[p], 0, 'tp', 99.90, 1) for p in t),
           'unit T16 b: pending buy limit 98.90 on a tie bar: filled on the way down first, target 99.90 on the way '
           'up in the same bar (both paths)')
    # (c) the minutes after an intrabar fill: filled at 98.90 in minute 1; minute 2 is the tie O 99.00 H 102.50
    #     L 95.50: low first = its stop 95.90; high first would be its target 101.90
    g = [[L0], [(99.50, 99.625, 98.75, 99.00), (99.00, 102.50, 95.50, 99.25)]]
    t = _hand(g, {'entryFill': LIMIT, 'slPtsIn': 300.0, 'tpPtsIn': 300.0, 'trailOn': False}, nLong=[1, 0])
    #    tv: chart bar O 99.50 H 102.50 L 95.50 (3.0 < 4.0: high first): filled on the fall, stopped at 95.90 too
    report(all(abs(t[p].iloc[0]['entry_px'] - 98.90) < 1e-9 and _is(t[p], 0, 'sl', 95.90, 1) for p in t),
           'unit T16 c: filled in minute 1, minute 2 is a tie: low first -> sl at 95.90, not tp at 101.90 (mag; tv '
           'gives the same exit)')


# =========================================================================================== fake
def sec_fake():
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '240'), ('XAU', '240'), ('BTC', '15'), ('XAU', '15'),
                     ('BTC', '5')):
        rng = np.random.default_rng([77, sum(map(ord, pair)), sum(map(ord, tf))])
        bad = []
        ntr = nset = 0
        for pp in ({}, {'fgfOn': False}, CMP.extra_prep(rng)):
            P = M.prepare(pair, tf, pp)
            P['sub'] = M.fake_sub(P)
            sims = [{}, {'xpwInv': True}, {'entryFill': LIMIT}, {'entryFill': LIMIT, 'xpwInv': True, 'cost': 'ours'}]
            sims += [CMP.grid_sim(rng) for _ in range(2)] + [CMP.extra_sim(rng, pair) for _ in range(3)]
            for x in sims:
                b, nt = both_paths_equal(P, x)
                nset += 1
                ntr += nt
                if b:
                    bad.append('%r %r: %s' % (pp, x, b))
        report(not bad, 'fake %s %s: mag with one fake sub-bar per chart bar == tv bit for bit, %d settings, %d trades'
               % (pair, tf, nset, ntr), ' | '.join(bad[:3]))


# =========================================================================================== ref
REF_COLS = None


def cmp_ref(P, x, mag, mb):
    import xpw23_magref as RF
    xx = dict(x)
    xx['path'] = 'mag' if mag else 'tv'
    R = M.simulate(P, xx)
    t = M.trades(P, R)
    s = M.summary(P, R)
    rr = RF.ref_run(P, x, mag, mb)
    rt = pd.DataFrame(rr['trades'])
    bad = []
    if len(rt) != len(t):
        bad.append('trade count %d vs reference %d' % (len(t), len(rt)))
    elif len(t):
        for c in rt.columns:
            a, b = t[c].to_numpy(), rt[c].to_numpy()
            ok = feq(a, b) if a.dtype.kind == 'f' else (a == b)
            ok = np.asarray(ok, bool)
            if not ok.all():
                i = int(np.nonzero(~ok)[0][0])
                bad.append('%s: %d rows, first %d: %r vs %r' % (c, int((~ok).sum()), i, a[i], b[i]))
    eok = feq(R['eq'], np.array(rr['eq']))
    if not eok.all():
        bad.append('equity curve: %d bars' % int((~eok).sum()))
    cn = rr['counters']
    for k in ('placed', 'skipped_room', 'skipped_qty', 'pend_placed', 'pend_filled', 'pend_filled_at_close',
              'pend_cancelled', 'pend_open_end', 'close_all_bars', 'max_open', 'raw_long', 'raw_short',
              'blocked_long', 'blocked_short'):
        if s[k] != cn[k]:
            bad.append('%s: %r vs reference %r' % (k, s[k], cn[k]))
    if abs(s['exposure'] - cn['exposure_bars'] / P['n']) > 1e-12:
        bad.append('exposure')
    return len(t), bad, t


def sec_ref():
    import xpw23_magref as RF
    cells = (('BTC', '60'), ('XAU', '60'), ('BTC', '240'), ('XAU', '240'), ('BTC', '15'), ('XAU', '15'), ('BTC', '5'),
             ('XAU', '5'))
    tot = [0, 0, 0]
    kinds = {}
    for ci, (pair, tf) in enumerate(cells):
        rng = np.random.default_rng([424, ci])
        w0, w1 = M.WINDOWS[pair]
        bad_all = []
        nset = ntr = ndiff = 0
        t0 = time.time()
        for v in range(2):
            st = int(w0 + rng.integers(0, (w1 - w0) // 86400 - 62) * 86400)
            pp = (CMP.grid_prep(rng), CMP.extra_prep(rng))[v]
            pp = dict(pp)
            pp.update(start=st, end=st + 61 * 86400)
            P = M.prepare(pair, tf, pp)
            mb = RF.minute_bars_of(P)
            sims = [CMP.grid_sim(rng), CMP.extra_sim(rng, pair)]
            if ci == 0 and v == 0:
                sims.append({})
            for x in sims:
                nset += 1
                res = {}
                for mag in (False, True):
                    nt, bad, t = cmp_ref(P, x, mag, mb)
                    ntr += nt
                    res[mag] = t
                    for k, c in t['exit_kind'].value_counts().items():
                        kinds[k] = kinds.get(k, 0) + int(c)
                    if bad:
                        bad_all.append('%s prep=%r x=%r: %s' % ('mag' if mag else 'tv', pp, x, '; '.join(bad[:4])))
                # how much the two paths differ on this setting (so that the mag comparison is not empty)
                a, b = res[False], res[True]
                if len(a) != len(b) or not (np.array_equal(a['exit_px'].to_numpy(), b['exit_px'].to_numpy())
                                            and np.array_equal(a['entry_px'].to_numpy(), b['entry_px'].to_numpy())):
                    ndiff += 1
        tot[0] += nset
        tot[1] += ntr
        tot[2] += ndiff
        report(not bad_all, 'ref %s %s: tv and mag == the pure-Python reference on %d random settings over two 2-month '
               'windows, %d trades (tv and mag differ from each other on %d of them) [%.0fs]' % (
                   pair, tf, nset, ntr, ndiff, time.time() - t0), ' | '.join(bad_all[:2]))
    report(tot[0] >= 30 and tot[2] >= 15, 'ref total: %d settings, %d trades compared; the two paths differ on %d '
           'settings; exit kinds seen %r' % (tot[0], tot[1], tot[2], dict(sorted(kinds.items()))))


# =========================================================================================== money
def recompute(P, R):
    """Every money field of the summary from the trade list and the bars alone."""
    t = M.trades(P, R, comments=False)
    s = M.summary(P, R)
    X = R['x']
    fix, pct = M.COSTS[X['cost']][P['pair']]
    init = 10000.0
    bad = []

    def chk(name, a, b, rel=1e-9):
        if not bool(np.all(feq(a, b, rel))):
            bad.append('%s: %r vs %r' % (name, a if np.ndim(a) == 0 else 'array', b if np.ndim(b) == 0 else 'array'))
    d = t['dir'].to_numpy(np.float64)
    q = t['qty'].to_numpy()
    ep, xp = t['entry_px'].to_numpy(), t['exit_px'].to_numpy()
    ec = q * (fix + pct * ep)
    xc = q * (fix + pct * xp)
    gross = d * (xp - ep) * q
    pnl = gross - (ec + xc)
    chk('costs column', t['costs'].to_numpy(), ec + xc)
    chk('pnl_gross column', t['pnl_gross'].to_numpy(), gross)
    chk('pnl column', t['pnl'].to_numpy(), pnl)
    chk('costs', s['costs'], float((ec + xc).sum()))
    chk('final_equity', s['final_equity'], init + pnl.sum())
    chk('net_pct', s['net_pct'], pnl.sum() / init * 100.0, 1e-8)
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    chk('pf', s['pf'], gp / gl if gl > 0 else (np.inf if gp > 0 else np.nan))
    chk('win_pct', s['win_pct'], (pnl > 0).mean() * 100.0 if len(t) else np.nan)
    first = t['entry_time'].to_numpy() <= P['mid']
    if s['h1_trades'] != int(first.sum()) or s['h2_trades'] != int((~first).sum()):
        bad.append('h1_trades / h2_trades')
    risk = X['qtyMode'] == 'Risk' and (X['slAtrMult'] if X['exitUnit'] == 'ATR' else X['slPtsIn']) > 0
    if s['halves_rule'] != ('compound' if risk else 'additive'):
        bad.append('halves_rule')
    eqb = t['eq_before'].to_numpy()
    for nm, m in (('h1r_pct', first), ('h2r_pct', ~first)):
        if not m.any():
            v = 0.0
        elif not risk:
            v = 100.0 * pnl[m].sum() / init
        elif (eqb[m] <= 0).any():
            v = np.nan
        else:
            v = 100.0 * (np.prod(1.0 + pnl[m] / eqb[m]) - 1.0)
        chk(nm, s[nm], v, 1e-8)
    # the bar-close equity curve from the trade list: realized P/L of the trades closed so far, plus
    # the open trades at this close (their entry cost is already paid)
    n = P['n']
    r0 = int(P['rows'][0])
    eb = (t['entry_bar'].to_numpy() - r0).astype(np.int64)
    xb = (t['exit_bar'].to_numpy() - r0).astype(np.int64)
    c = P['close']
    real = np.cumsum(np.bincount(xb, weights=pnl, minlength=n))
    dq = np.cumsum(np.bincount(eb, weights=d * q, minlength=n) - np.bincount(xb, weights=d * q, minlength=n))
    base = d * q * ep + ec
    db = np.cumsum(np.bincount(eb, weights=base, minlength=n) - np.bincount(xb, weights=base, minlength=n))
    eq = init + real + c * dq - db
    chk('equity curve', R['eq'], eq, 1e-7)
    mid_j = int(np.searchsorted(P['t_close'], P['mid'], side='right')) - 1
    e_mid = eq[mid_j] if mid_j >= 0 else init
    chk('half1_pct', s['half1_pct'], (e_mid - init) / init * 100.0, 1e-6)
    chk('half2_pct', s['half2_pct'], (eq[-1] - e_mid) / init * 100.0, 1e-6)
    peak = np.maximum.accumulate(np.maximum(R['eq'], init))
    chk('max_dd_pct', s['max_dd_pct'], ((peak - R['eq']) / peak).max() * 100.0)
    chk('max_dd_init_pct', s['max_dd_init_pct'], (peak - R['eq']).max() / init * 100.0)
    # open trades after step 3 of each bar; on the last bar the trades closed as 'end' are still open
    is_end = (t['exit_kind'] == 'end').to_numpy()
    nopen = np.cumsum(np.bincount(eb, minlength=n) - np.bincount(xb, minlength=n))
    nopen[-1] += int(is_end.sum())
    chk('exposure', s['exposure'], float((nopen > 0).mean()))
    if s['max_open'] != int(nopen.max()):
        bad.append('max_open %r vs %r' % (s['max_open'], int(nopen.max())))
    sq = np.cumsum(np.bincount(eb, weights=q, minlength=n) - np.bincount(xb, weights=q, minlength=n))
    sq[-1] += q[is_end].sum()
    eq_pos = eq.copy()
    eq_pos[-1] += xc[is_end].sum()                    # the state before the 'end' closes (exit costs not paid yet)
    held = nopen > 0
    notional = sq * c
    mb_ = int((notional[held] > eq_pos[held] * (1 + 1e-12)).sum())
    mb2 = int((notional[held] > eq_pos[held] * (1 - 1e-12)).sum())
    if not (min(mb_, mb2) <= s['margin_bars'] <= max(mb_, mb2)):
        bad.append('margin_bars %r vs %r' % (s['margin_bars'], mb_))
    if held.any():
        me = np.inf if (eq_pos[held] <= 0).any() else float((notional[held] / eq_pos[held]).max())
        chk('max_expo', s['max_expo'], me, 1e-7)
    for k in M.KINDS[1:]:
        if s['exit_' + k] != int((t['exit_kind'] == k).sum()):
            bad.append('exit_' + k)
    if s['long'] != int((t['dir'] > 0).sum()) or s['short'] != int((t['dir'] < 0).sum()) or s['trades'] != len(t):
        bad.append('long / short / trades')
    if s['zero_length'] != int((eb == xb).sum()):
        bad.append('zero_length')
    chk('avg_bars_held', s['avg_bars_held'], float((xb - eb).mean()) if len(t) else np.nan)
    slt = t['sl_ticks'].to_numpy()
    hs = ~np.isnan(slt)
    with np.errstate(invalid='ignore', divide='ignore'):
        Rm = pnl / (q * slt * 0.01)
    chk('R column', t['R'].to_numpy(), Rm)
    chk('net_R', s['net_R'], Rm[hs].sum(), 1e-8)
    chk('h1_R', s['h1_R'], Rm[hs & first].sum(), 1e-8)
    chk('h2_R', s['h2_R'], Rm[hs & ~first].sum(), 1e-8)
    if len(t) <= 6000:                                 # fifo_exits by brute force
        kind = t['exit_kind'].to_numpy()
        closefill = np.isin(kind, ('time', 'close_all', 'reverse', 'end'))
        own = np.isin(kind, ('sl', 'tp', 'trail', 'time'))
        cntf = 0
        for i in np.nonzero(own)[0]:
            e = xb[:i]
            if ((e > xb[i]) | ((e == xb[i]) & closefill[:i] & (not closefill[i]))).any():
                cntf += 1
        if s['fifo_exits'] != cntf:
            bad.append('fifo_exits %r vs %r' % (s['fifo_exits'], cntf))
    return bad, len(t)


def risk_qty(P, R):
    """Every quantity of a Risk-mode run against entryQty() evaluated on the equity the script saw on
    the placement bar, rebuilt from the trade list: 10,000 + P/L of the trades closed before that
    run - entry costs of the trades open at it + their open P/L at that close."""
    t = M.trades(P, R, comments=False)
    X = R['x']
    fix, pct = M.COSTS[X['cost']][P['pair']]
    r0 = int(P['rows'][0])
    atr = M.atr_window(P, X['atrLen'])
    eb = t['entry_bar'].to_numpy() - r0
    xb = t['exit_bar'].to_numpy() - r0
    sb = t['sig_bar'].to_numpy() - r0
    kind = t['exit_kind'].to_numpy()
    intr_x = np.isin(kind, ('sl', 'tp', 'trail'))
    at_close = t['fill_at_close'].to_numpy()
    d, q, ep = t['dir'].to_numpy(np.float64), t['qty'].to_numpy(), t['entry_px'].to_numpy()
    pnl = t['pnl'].to_numpy()
    ec = q * (fix + pct * ep)
    worst = 0.0
    nchk = 0
    for j in np.unique(sb):
        closed = (xb < j) | ((xb == j) & intr_x)                       # closed before the run of bar j
        opened = ((eb < j) | ((eb == j) & ~at_close)) & ~closed        # open at the run of bar j
        cj = P['close'][j]
        eqj = 10000.0 + pnl[closed].sum() + (d[opened] * (cj - ep[opened]) * q[opened] - ec[opened]).sum()
        slT = X['slAtrMult'] * atr[j] / 0.01 if X['exitUnit'] == 'ATR' else X['slPtsIn']
        qq = X['qtyFixed']
        if X['qtyMode'] == 'Risk' and slT > 0:
            rpc = slT * 0.01 * 1.0
            qq = eqj * X['riskPct'] / 100.0 / rpc if rpc > 0 else 0.0
        raw = qq
        if X['qtyStep'] > 0:
            qq = math.floor(qq / X['qtyStep'] + 1e-9) * X['qtyStep']
        qq = min(qq, X['qtyMax'])
        for v in q[sb == j]:
            nchk += 1
            dv = abs(v - qq)
            # the rebuilt equity differs from the kernel's by rounding (1e-12 relative): at most one step
            # when raw / step sits on an integer
            if dv > 1e-9 and X['qtyStep'] > 0 and abs(raw / X['qtyStep'] - round(raw / X['qtyStep'])) < 1e-6:
                dv = 0.0
            worst = max(worst, dv)
    return worst, nchk


def sec_money():
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '240'), ('XAU', '15'), ('BTC', '5')):
        for pp in ({}, {'fgfOn': False}):
            P = M.prepare(pair, tf, pp)
            bad = []
            ntr = nset = 0
            sims = [dict(cost=c, path=p, xpwInv=i) for c in ('tv', 'ours', 'stress') for p in ('tv', 'mag')
                    for i in (False, True)]
            sims += [dict(qtyMode='Risk', riskPct=1.0, cost='ours', path='mag', qtyMax=50.0, qtyStep=0.001),
                     dict(qtyMode='Risk', riskPct=0.5, cost='stress', path='tv', entryFill=LIMIT, xpwInv=True,
                          qtyMax=50.0, qtyStep=0.001),
                     dict(entryFill=LIMIT, path='mag', cost='ours', timeStop=12, maxOpen=3),
                     dict(exitUnit='Points', path='mag', cost='stress', slPtsIn=0.0,
                          tpPtsIn=20000.0 * (1 if pair == 'BTC' else 0.02), trDistPts=0.0)]
            for x in sims:
                R = M.simulate(P, x)
                b, nt = recompute(P, R)
                nset += 1
                ntr += nt
                if b:
                    bad.append('%r: %s' % (x, '; '.join(b[:4])))
            report(not bad, 'money %s %s %r: costs (tv / ours / stress), fair halves, equity curve, drawdown, exposure, '
                   'exit counts, R sums recomputed from the trade list: %d settings, %d trades' % (
                       pair, tf, pp, nset, ntr), ' | '.join(bad[:3]))
            if not pp:
                worst = 0.0
                nq = 0
                for x in (dict(qtyMode='Risk', riskPct=1.0, qtyMax=1000.0, qtyStep=0.001, cost='ours', path='mag'),
                          dict(qtyMode='Risk', riskPct=2.0, qtyMax=1000.0, qtyStep=0.01, cost='tv', path='tv',
                               entryFill=LIMIT, xpwInv=True),
                          dict(qtyMode='Risk', riskPct=0.3, qtyMax=1000.0, qtyStep=0.0, cost='stress', path='mag',
                               timeStop=10)):
                    R = M.simulate(P, x)
                    w, k = risk_qty(P, R)
                    worst = max(worst, w)
                    nq += k
                report(worst <= 1e-9, 'money %s %s: Risk quantities == entryQty() on the equity rebuilt from the trade '
                       'list, %d entries, largest difference %.2e' % (pair, tf, nq, worst))


# =========================================================================================== inv
def same_real_trades(ta, tb, flip=False):
    """The same real trades (ids, sides, bars, prices, quantities, exit kinds, P/L). flip: tb is the
    mirror (other side, other id letter, gross P/L negated)."""
    if len(ta) != len(tb):
        return 'count %d vs %d' % (len(ta), len(tb))
    ida = ta['id'].to_numpy()
    idb = tb['id'].to_numpy()
    if flip:
        idb = np.array([('L' if s[0] == 'S' else 'S') + s[1:] for s in idb], dtype=object)
    if not (ida == idb).all():
        return 'id'
    sg = -1 if flip else 1
    if not (ta['dir'].to_numpy() == sg * tb['dir'].to_numpy()).all():
        return 'dir'
    for c in ('sig_bar', 'k', 'entry_bar', 'exit_bar', 'exit_kind', 'src'):
        if not (ta[c].to_numpy() == tb[c].to_numpy()).all():
            return c
    for c in ('entry_px', 'qty', 'exit_px'):
        if not feq(ta[c].to_numpy(), tb[c].to_numpy()).all():
            return c
    if not feq(ta['pnl_gross'].to_numpy(), sg * tb['pnl_gross'].to_numpy()).all():
        return 'pnl_gross'
    if not flip and not (feq(ta['pnl'].to_numpy(), tb['pnl'].to_numpy()).all()
                         and feq(ta['eq_before'].to_numpy(), tb['eq_before'].to_numpy()).all()):
        return 'pnl / eq_before'
    return ''


def sec_inv():
    SWAP = {"Both": "Both", "Long only (buy only)": "Short only (sell only)",
            "Short only (sell only)": "Long only (buy only)"}
    NOEXIT = dict(slAtrMult=0.0, trailOn=False)          # ATR mode: no stop -> no target; trail off
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '240'), ('XAU', '240'), ('BTC', '15'), ('XAU', '15')):
        Pn = M.prepare(pair, tf, {'fgfOn': False})
        Pr = M.prepare(pair, tf, {'fgfOn': False, 'reverseAll': True})
        Pn['sub'] = M.get_sub(Pn)
        Pr['sub'] = Pn['sub']
        # (1) header VS REVERSE: filter off, Signal tick, no row on "exit only": either option alone places the
        #     same orders; both on trade as both off
        bad = []
        ntr = 0
        sims = [{}, {'trailOn': False, 'tpRMult': 3.0}, {'maxOpen': 3, 'timeStop': 24, 'cost': 'ours'},
                {'qtyMode': 'Risk', 'riskPct': 1.0, 'cost': 'stress'}, {'tradeDir': "Long only (buy only)"}]
        for x in sims:
            for path in ('tv', 'mag'):
                xx = dict(x)
                xx['path'] = path
                xi = dict(xx)
                xi['xpwInv'] = True
                # with the option, "Long only" keeps the real buys: reverseAll + Long only keeps them too
                a = M.trades(Pn, M.simulate(Pn, xi))            # inv alone
                b = M.trades(Pr, M.simulate(Pr, xx))            # reverseAll alone
                c = M.trades(Pr, M.simulate(Pr, xi))            # both on
                e = M.trades(Pn, M.simulate(Pn, xx))            # both off
                ntr += len(a) + len(c)
                r1 = same_real_trades(a, b)
                r2 = same_real_trades(c, e)
                if r1 or r2:
                    bad.append('%r: inv vs reverse %r, both on vs both off %r' % (xx, r1, r2))
        report(not bad, 'inv %s %s: filter off, Signal tick, default rows: inv alone == reverseAll alone, both on == '
               'both off (tv and mag), %d settings, %d trades' % (pair, tf, 2 * len(sims), ntr), ' | '.join(bad[:3]))
        # the comments and the FGD sides are what differs (header): raw long (inv) = the label's own side
        Ra = M.simulate(Pn, {'xpwInv': True})
        Rb = M.simulate(Pr, {})
        sa, sb = M.summary(Pn, Ra), M.summary(Pr, Rb)
        s0 = M.summary(Pn, M.simulate(Pn, {}))
        report(sa['raw_long'] == s0['raw_long'] and sa['raw_short'] == s0['raw_short']
               and sb['raw_long'] == s0['raw_short'] and sb['raw_short'] == s0['raw_long'],
               'inv %s %s: FGD counts keep the label side with inv (raw L / S %d / %d as with the option off) and are '
               'swapped by reverseAll (%d / %d)' % (pair, tf, sa['raw_long'], sa['raw_short'], sb['raw_long'],
                                                    sb['raw_short']))
        ta = M.trades(Pn, Ra)
        report(bool(ta['entry_comment'].str.contains(r' \(inv\) \| ').all())
               and bool((ta['sig_dir'] == -ta['dir']).all())
               and bool(((ta['dir'] > 0) == ta['id'].str.startswith('L')).all()),
               'inv %s %s: inverted orders carry "(inv)", ids start with the real side letter, sig_dir = -dir' % (pair, tf))
        # (2) with the filter on the two options differ (a LONG label needs the BUY zone with inv, the SELL zone
        #     reversed); in limit mode they differ even with the filter off (stop at the low vs limit at the high)
        Pfn = M.prepare(pair, tf, {})
        Pfr = M.prepare(pair, tf, {'reverseAll': True})
        a = M.trades(Pfn, M.simulate(Pfn, {'xpwInv': True}))
        b = M.trades(Pfr, M.simulate(Pfr, {}))
        la = M.trades(Pn, M.simulate(Pn, {'xpwInv': True, 'entryFill': LIMIT}))
        lb = M.trades(Pr, M.simulate(Pr, {'entryFill': LIMIT}))
        report(bool(same_real_trades(a, b)) and bool(same_real_trades(la, lb)),
               'inv %s %s: filter on, inv != reverseAll (%d vs %d trades); limit mode, filter off, inv != reverseAll '
               '(%d vs %d trades)' % (pair, tf, len(a), len(b), len(la), len(lb)))
        # the filter gate is the label's: an inverted run takes exactly the entries of the normal run when room
        # never binds (blocked stays blocked), on the other side
        Rn, Ri = M.simulate(Pfn, {'maxOpen': 100}), M.simulate(Pfn, {'xpwInv': True, 'maxOpen': 100})
        sn, si = M.summary(Pfn, Rn), M.summary(Pfn, Ri)
        tn, ti = M.trades(Pfn, Rn), M.trades(Pfn, Ri)
        same_entries = (len(tn) == len(ti) and (tn['sig_bar'].to_numpy() == ti['sig_bar'].to_numpy()).all()
                        and (tn['k'].to_numpy() == ti['k'].to_numpy()).all()
                        and (tn['dir'].to_numpy() == -ti['dir'].to_numpy()).all()
                        and (tn['entry_px'].to_numpy() == ti['entry_px'].to_numpy()).all())
        report(sn['skipped_room'] == 0 and si['skipped_room'] == 0 and bool(same_entries)
               and sn['blocked_long'] == si['blocked_long'] and sn['blocked_short'] == si['blocked_short'],
               'inv %s %s: filter on, Max open entries 100 (room never binds): the inverted run fills the same %d '
               'entries (bar, label, price) on the opposite side; blocked L / S unchanged (%d / %d)' % (pair, tf, len(tn), sn['blocked_long'],
                                                                     sn['blocked_short']))
        # (3) header FRAME / ONE SIDE: with every S2 exit off nothing but the script closes a trade, so the
        #     inverted run must be the exact mirror of the run with the option off and the other one-side
        #     mode: the same trades on the opposite side (both fill modes, time stop, exit-only rows)
        Px = M.prepare(pair, tf, {'actDL': 'exit only', 'actDS': 'exit only', 'actInf': 'off'})
        Px['sub'] = Pn['sub']
        Pfn['sub'] = Pn['sub']
        bad = []
        ntr = 0
        ncase = 0
        for PP in (Pfn, Px, Pn):
            for td in SWAP:
                for fill in ("Signal tick", LIMIT):
                    for ts in (0, 24):
                        for path in ('tv', 'mag'):
                            x = dict(NOEXIT, tradeDir=td, entryFill=fill, timeStop=ts, path=path, maxOpen=5)
                            xm = dict(x, tradeDir=SWAP[td], xpwInv=True)
                            a = M.trades(PP, M.simulate(PP, x))
                            b = M.trades(PP, M.simulate(PP, xm))
                            ncase += 1
                            ntr += len(a)
                            r = same_real_trades(a, b, flip=True)
                            if r:
                                bad.append('%r: %s' % (x, r))
        report(not bad, 'inv %s %s: every S2 exit off: inv on == the mirror of inv off with the other one-side mode '
               '(same trades, opposite side), %d cases, %d trades' % (pair, tf, ncase, ntr), ' | '.join(bad[:3]))
        # (4) ONE SIDE with the default exits: "Long only" + inv takes the SHORT entries as buys: every trade is
        #     a real buy from a short label, and (room never binding) they are the entries of "Short only"
        x1 = dict(tradeDir="Long only (buy only)", xpwInv=True, maxOpen=100)
        x2 = dict(tradeDir="Short only (sell only)", maxOpen=100)
        R1, R2 = M.simulate(Pfn, x1), M.simulate(Pfn, x2)
        t1, t2 = M.trades(Pfn, R1), M.trades(Pfn, R2)
        s1, s2 = M.summary(Pfn, R1), M.summary(Pfn, R2)
        k1 = set(zip(t1['sig_bar'].tolist(), t1['k'].tolist()))
        k2 = set(zip(t2['sig_bar'].tolist(), t2['k'].tolist()))
        report(bool((t1['dir'] == 1).all() and (t1['sig_dir'] == -1).all() and (t2['dir'] == -1).all())
               and k1 == k2 and s1['skipped_room'] + s2['skipped_room'] == 0 and s1['raw_long'] == 0,
               'inv %s %s: Long only + inv = only real buys, all from SHORT labels; the entries of Short only without '
               'the option (%d and %d trades, skipped for room %d / %d)' % (pair, tf, len(t1), len(t2),
                                                                           s1['skipped_room'], s2['skipped_room']))
        # (5) header VS REVERSE, "Otherwise, both on": an entry is on the side it has with both off, but is taken
        #     only where the filter allows the OPPOSITE side (a LONG label buys in the SELL ZONE). Expected
        #     entries straight from the un-reversed labels and the filter permissions (room never binding).
        Rb = M.simulate(Pfr, {'xpwInv': True, 'maxOpen': 100})
        tb, sb = M.trades(Pfr, Rb, comments=False), M.summary(Pfr, Rb)
        exp = []
        rows = Pfn['rows']
        for j in np.nonzero((Pfn['nLong'] > 0) | (Pfn['nShort'] > 0))[0].tolist():
            if Pfn['nLong'][j] > 0 and Pfn['sellOk'][j]:
                exp += [(int(rows[j]), k + 1, 1) for k in range(int(Pfn['nLong'][j]))]
            elif Pfn['nShort'][j] > 0 and Pfn['buyOk'][j]:
                exp += [(int(rows[j]), k + 1, -1) for k in range(int(Pfn['nShort'][j]))]
        got = list(zip(tb['sig_bar'].tolist(), tb['k'].tolist(), tb['dir'].tolist()))
        report(sb['skipped_room'] == 0 and got == exp and bool((tb['entry_bar'] == tb['sig_bar']).all()),
               'inv %s %s: filter on, both options on: every LONG label is a real BUY taken where the SELL zone '
               'allows it (and the mirror), %d entries == the labels gated by the opposite permission' % (
                   pair, tf, len(exp)))
        #     ... in limit mode by a stop at the other end of the candle (a buy stop at the HIGH)
        Rl = M.simulate(Pfr, {'xpwInv': True, 'entryFill': LIMIT, 'maxOpen': 100})
        tl = M.trades(Pfr, Rl)
        r0 = int(rows[0])
        sgb = (tl['sig_bar'].to_numpy() - r0).astype(np.int64)
        enb = (tl['entry_bar'].to_numpy() - r0).astype(np.int64)
        buy = tl['dir'].to_numpy() > 0
        px = tl['entry_px'].to_numpy()
        lvl = np.where(buy, Pfr['high'][sgb], Pfr['low'][sgb])          # the label candle's other end
        at_lvl = np.abs(px - lvl) <= 1e-9
        at_open = (np.abs(px - Pfr['open'][enb]) <= 1e-9) & (enb > sgb) & np.where(buy, px >= lvl, px <= lvl)
        report(len(tl) > 0 and bool((at_lvl | at_open).all()) and bool(buy.any()) and bool((~buy).any())
               and bool(tl.loc[buy, 'entry_comment'].str.startswith('ENTER LONG (inv) stop @ label | ').all())
               and bool((tl['sig_dir'] == -tl['dir']).all()),
               'inv %s %s: the same in limit mode: the real buys are buy STOPS at the label candle\'s HIGH (filled at '
               'it, or at the open of a bar that gaps over it), the sells sell stops at its low, %d trades' % (
                   pair, tf, len(tl)))
        # (6) header CLOSES: an "exit only" row closes the side its label is against (option off) / the mirrored
        #     side = the side its label points to (option on). Filter off, exit-only divergence rows.
        Pe = M.prepare(pair, tf, {'fgfOn': False, 'actDL': 'exit only', 'actDS': 'exit only', 'actInf': 'off'})
        ok = True
        ncl = 0
        for inv_ in (False, True):
            te = M.trades(Pe, M.simulate(Pe, dict(NOEXIT, xpwInv=inv_)), comments=False)
            ca = te[te['exit_kind'] == 'close_all']
            jb = (ca['exit_bar'].to_numpy() - int(Pe['rows'][0])).astype(np.int64)
            d_ = ca['dir'].to_numpy()
            xl, xs = Pe['exitL'][jb], Pe['exitS'][jb]          # exitL: a SHORT-pointing exit-only label (closes longs)
            want = ((d_ < 0) & xl) | ((d_ > 0) & xs) if inv_ else ((d_ > 0) & xl) | ((d_ < 0) & xs)
            ok = ok and len(ca) > 0 and bool(want.all())
            ncl += len(ca)
        report(ok, 'inv %s %s: "exit only" rows: option off they close the side the label is against, option on the '
               'side it points to (every close_all trade of both runs, %d)' % (pair, tf, ncl))
        del Pn, Pr, Pfn, Pfr, Px, Pe
        gc.collect()


# =========================================================================================== engine
def sec_engine():
    """The canonical module against the verified replica of the trailing-TP file (engine.py, and its
    Bar Magnifier kernel sweep_core._run_mag, built, reconciled and audited by other agents) on the
    settings where the two Pine files place the same orders: filter off, Signal tick, exits in ticks =
    trail_points / trail_offset (+ loss), no target, no time stop, Trade direction Both, Max open
    entries 20. Both paths, with and without "Inverted direction". Sizes differ (10 % of equity
    there, 0.1 unit here), so sides, rows, label index, prices and exit kinds are compared."""
    import sweep_core as SC
    tot = [0, 0]
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '15'), ('XAU', '240'), ('BTC', '240'), ('XAU', '15')):
        st, en = M.WINDOWS[pair]
        sc = 100.0 if pair == 'BTC' else 1.0             # ticks: 100 = $1
        bad = []
        ntr = ncase = ndiff = 0
        t0 = time.time()
        for sp in ({}, {'actDL': 'exit only', 'actDS': 'exit only', 'actInf': 'off'}):
            sig = xpw.xpw_signals(pair, tf, st, en, sp)
            P = M.prepare(pair, tf, dict(sp, fgfOn=False))
            M.get_sub(P)
            rows = P['rows']
            for inv in (False, True):
                PS = SC.prep(pair, tf, sig, None, False, inv=inv)
                sub = SC.sub_bars(pair, tf, PS['rows'])
                for A, B, C in ((200 * sc, 100 * sc, 0.0), (0.0, 150 * sc, 300 * sc), (500 * sc, 50 * sc, 400 * sc),
                                (100 * sc, 300 * sc, 1000 * sc), (50 * sc, 20 * sc, 0.0)):
                    cfg = dict(trailOn=True, trailUnit='ticks', trailAct=A, trailOff=B, slOn=C > 0,
                               slDist=C if C > 0 else np.nan)
                    x = dict(exitUnit='Points', slPtsIn=C, tpPtsIn=0.0, trActPts=A, trDistPts=B, xpwInv=inv)
                    res = {}
                    for path in ('tv', 'mag'):
                        r = SC.run_cfg(PS, cfg, path, sub=sub, inv=inv)
                        t = M.trades(P, M.simulate(P, dict(x, path=path)), comments=False)
                        ncase += 1
                        ntr += len(t)
                        res[path] = t
                        why = ''
                        if len(t) != r['n']:
                            why = 'trades %d vs %d' % (len(t), r['n'])
                        else:
                            kinds = np.array([SC.KIND_NAMES[int(k)] for k in r['xkind']], dtype=object)
                            for nm, a, b in (('dir', t['dir'].to_numpy(), r['dir']),
                                             ('entry_bar', t['entry_bar'].to_numpy(), rows[r['erow']]),
                                             ('k', t['k'].to_numpy(), r['k']),
                                             ('exit_bar', t['exit_bar'].to_numpy(), rows[r['xrow']]),
                                             ('exit_kind', t['exit_kind'].to_numpy(), kinds)):
                                if not (np.asarray(a) == np.asarray(b)).all():
                                    why = nm
                                    break
                            if not why:
                                for nm, a, b in (('entry_px', t['entry_px'].to_numpy(), r['epx']),
                                                 ('exit_px', t['exit_px'].to_numpy(), r['xpx'])):
                                    if not feq(a, b).all():
                                        why = nm
                                        break
                        if why:
                            bad.append('%r inv %s %s act/off/sl %g/%g/%g: %s' % (sp, inv, path, A, B, C, why))
                    a, b = res['tv'], res['mag']
                    if len(a) != len(b) or not np.array_equal(a['exit_px'].to_numpy(), b['exit_px'].to_numpy()):
                        ndiff += 1
        tot[0] += ncase
        tot[1] += ntr
        report(not bad, 'engine %s %s: filter off, Signal tick, tick exits: == engine.py (tv) and sweep_core._run_mag '
               '(mag), normal and inverted, %d runs, %d trades (tv and mag differ from each other in %d of %d '
               'settings) [%.0fs]' % (pair, tf, ncase, ntr, ndiff, ncase // 2, time.time() - t0), ' | '.join(bad[:3]))
    report(tot[0] >= 200, 'engine total: %d runs, %d trades compared with the trailing-TP replica' % (tot[0], tot[1]))


# =========================================================================================== timing
def sec_timing():
    for pair, tf in (('BTC', '5'), ('BTC', '60'), ('BTC', '240'), ('XAU', '15')):
        P = M.prepare(pair, tf)
        t0 = time.time()
        sub = M.get_sub(P)
        tsub = time.time() - t0
        out = []
        worst = 0.0
        for nm, x in (('default', {}), ('no trail, no target, stop 6 ATR', {'trailOn': False, 'tpRMult': 0.0,
                                                                              'slAtrMult': 6.0}),
                      ('limit', {'entryFill': LIMIT})):
            for path in ('tv', 'mag'):
                xx = dict(x, path=path)
                ts = []
                for _ in range(3):
                    t0 = time.time()
                    R = M.simulate(P, xx)
                    ts.append(time.time() - t0)
                worst = max(worst, min(ts))
                out.append('%s %s %.4fs' % (nm, path, min(ts)))
        report(worst < 0.5, 'timing %s %s (%d bars, %d sub-bars, built in %.1fs): one simulate, worst %.4fs' % (
            pair, tf, P['n'], len(sub[1]), tsub, worst), '; '.join(out))


# ===================================================================================== audit (stage 4)
NOEX = dict(slPtsIn=0.0, tpPtsIn=0.0, trailOn=False)          # every S2 exit off (Points mode)


def _hand2(bars, x, **kw):
    """bars: one (o, h, l, c) per chart bar (its only sub-bar). Returns {path: (trades, summary)}."""
    o, h, l, c = (np.array([b[i] for b in bars], np.float64) for i in range(4))
    P = M.make_P(o, h, l, c, **kw)
    P['sub'] = _sub_of([[b] for b in bars])
    out = {}
    for path in ('tv', 'mag'):
        xx = dict(PTS)
        xx.update(x)
        xx['path'] = path
        R = M.simulate(P, xx)
        out[path] = (M.trades(P, R), M.summary(P, R))
    return out


def _row(t, i, **want):
    """Trade i of the frame has these values (floats to 1e-9)."""
    if i >= len(t):
        return False
    r = t.iloc[i]
    for k, v in want.items():
        if isinstance(v, float):
            if not abs(float(r[k]) - v) < 1e-9:
                return False
        elif r[k] != v:
            return False
    return True


def _both(res, n, rows=(), **summ):
    """Both paths: n trades, the given rows (index, dict), the given summary fields."""
    for p in res:
        t, s = res[p]
        if len(t) != n:
            return False
        if not all(_row(t, i, **w) for i, w in rows):
            return False
        if not all(s[k] == v for k, v in summ.items()):
            return False
    return True


def sec_audit():
    """Stage 4 (audit): the SCRIPT logic of Pine lines 1645-1799 on hand-made bars, one decision per case,
    each answer worked out by hand from the Pine. Added because one-line mutants of these statements
    survived the sections unit / fake / ref / money / inv (they are only met by a few random settings of
    ref and abc). One sub-bar per chart bar, so both paths must give the same answer."""
    E = (99.0, 100.5, 98.9, 100.0)                  # closes at 100.00: a market entry of bar 0 fills there
    F1 = (100.0, 100.3, 99.9, 100.2)
    F2 = (100.2, 100.4, 100.1, 100.3)
    LB = (100.0, 101.0, 99.0, 100.5)                # limit mode: buy limit 99.00 / sell limit 101.00
    lim = dict(NOEX, entryFill=LIMIT)
    # 1. market mode, 1669 / 1770: an opposite entry the filter blocks does nothing at all, even with an
    #    "exit only" label on the same bar (goShort is the PRE-filter flag and holds the close back)
    r = _hand2([E, F1, F2], NOEX, nLong=[1, 0, 0], nShort=[0, 1, 0], sellOk=[True, False, True],
               exitL=[False, True, False])
    report(_both(r, 1, [(0, dict(id='L0-1', exit_kind='end', exit_bar=2, exit_px=100.3))], raw_short=1,
                 blocked_short=1, close_all_bars=0),
           'audit 1: market mode, a blocked SHORT entry (+ an exit-only label) on a bar: the long is not closed')
    # 2. the same with the sides swapped: short open, blocked LONG entry + exit-only label against shorts
    r = _hand2([E, F1, F2], NOEX, nShort=[1, 0, 0], nLong=[0, 1, 0], buyOk=[True, False, True],
               exitS=[False, True, False])
    report(_both(r, 1, [(0, dict(id='S0-1', dir=-1, exit_kind='end', exit_bar=2))], raw_long=1, blocked_long=1,
                 close_all_bars=0),
           'audit 2: market mode, a blocked LONG entry (+ an exit-only label) on a bar: the short is not closed')
    # 3. market mode, 1670: an exit-only label does not close on a bar with an entry of the side held
    r = _hand2([E, F1, F2], NOEX, nShort=[1, 1, 0], exitS=[False, True, False])
    report(_both(r, 2, [(0, dict(id='S0-1', exit_kind='end')), (1, dict(id='S1-1', entry_px=100.2, exit_kind='end'))],
                 close_all_bars=0),
           'audit 3: market mode, exit-only label + a SHORT entry on the same bar: no close, the entry stacks')
    # 4. limit mode, 1669 / 1717: a blocked opposite entry signal closes the long AND cancels the pending longs
    r = _hand2([LB, (100.5, 100.6, 98.5, 99.5), (99.5, 100.0, 99.2, 99.8), (99.8, 99.9, 98.0, 98.2)], lim,
               nLong=[1, 1, 0, 0], nShort=[0, 0, 1, 0], sellOk=[True, True, False, True])
    report(_both(r, 1, [(0, dict(id='L0-1', entry_bar=1, entry_px=99.0, exit_kind='close_all', exit_bar=2,
                                 exit_px=99.8))],
                 pend_placed=2, pend_filled=1, pend_cancelled=1, pend_cancel_against=1, blocked_short=1),
           'audit 4: limit mode, a blocked SHORT entry signal: close_all at 99.80 and the pending buy limit 98.50 is '
           'cancelled (it would have filled on the next bar)')
    # 5. limit mode, 1717: an exit-only label cancels the pending entries of ITS side only
    quiet = (100.5, 100.8, 100.0, 100.4)
    down, up = (100.4, 100.5, 98.0, 98.5), (100.4, 102.0, 100.3, 101.5)
    r = _hand2([LB, quiet, down], lim, nLong=[1, 0, 0], exitL=[False, True, False])
    ok = _both(r, 0, pend_placed=1, pend_cancelled=1, pend_cancel_against=1)
    r = _hand2([LB, quiet, down], lim, nLong=[1, 0, 0], exitS=[False, True, False])
    ok = ok and _both(r, 1, [(0, dict(id='L0-1', entry_bar=2, entry_px=99.0))], pend_cancelled=0)
    report(ok, 'audit 5: limit mode, exitL cancels the pending buy limit (no fill at 99.00 on the next bar); exitS '
           'does not (filled at 99.00)')
    r = _hand2([LB, quiet, up], lim, nShort=[1, 0, 0], exitS=[False, True, False])
    ok = _both(r, 0, pend_placed=1, pend_cancelled=1, pend_cancel_against=1)
    r = _hand2([LB, quiet, up], lim, nShort=[1, 0, 0], exitL=[False, True, False])
    ok = ok and _both(r, 1, [(0, dict(id='S0-1', dir=-1, entry_bar=2, entry_px=101.0))], pend_cancelled=0)
    report(ok, 'audit 6: limit mode, exitS cancels the pending sell limit (no fill at 101.00); exitL does not')
    # 7. limit mode, 1758 / 1783-1791: an entry that filled and closed before a run saw it open stays in the
    #    list as a ghost and holds one unit of room. Max open entries 2, stop 300 pts.
    #    bar 1: A fills at 99.00 and is stopped at 96.00 in the same bar; room 2 - 0 - 1 (ghost) = 1: B at 95.00
    #    bar 2: B fills; room 2 - 1 - 2 = -1: skipped; B leaves the list, the ghost stays
    #    bar 3: room 2 - 1 - 1 (ghost) = 0: skipped (without the ghost a third order would go in and fill on bar 4)
    r = _hand2([LB, (100.5, 100.6, 95.0, 95.5), (95.5, 96.0, 94.9, 95.8), (95.8, 96.2, 95.6, 96.0),
                (96.0, 96.1, 95.0, 95.2)], dict(entryFill=LIMIT, maxOpen=2, slPtsIn=300.0, tpPtsIn=0.0, trailOn=False),
               nLong=[1, 1, 1, 1, 0])
    report(_both(r, 2, [(0, dict(id='L0-1', entry_bar=1, entry_px=99.0, exit_kind='sl', exit_px=96.0, exit_bar=1)),
                        (1, dict(id='L1-1', entry_bar=2, entry_px=95.0, exit_kind='end', exit_px=95.2, exit_bar=4))],
                 pend_placed=2, skipped_room=2, zero_length=1),
           'audit 7: limit mode, Max open entries 2: the ghost of an entry filled and stopped inside one bar holds '
           'room on the next bars (2 labels skipped, no third order)')
    # 8. market mode, 1762: on a reversal bar every label is placed, whatever Max open entries says
    r = _hand2([E, F1, F2], dict(NOEX, maxOpen=1), nShort=[1, 0, 0], nLong=[0, 2, 0])
    ok = _both(r, 3, [(0, dict(id='S0-1', exit_kind='reverse', exit_px=100.2, exit_bar=1)),
                      (1, dict(id='L1-1', entry_px=100.2, exit_kind='end')), (2, dict(id='L1-2', entry_px=100.2))],
               max_open=2, reverse_over_room=1, skipped_room=0)
    r = _hand2([E, F1, F2], dict(NOEX, maxOpen=1), nLong=[1, 2, 0])
    ok = ok and _both(r, 1, [(0, dict(id='L0-1', exit_kind='end'))], skipped_room=2, max_open=1)
    report(ok, 'audit 8: Max open entries 1: two LONG labels against a short are both placed (reverse + stack); '
           'two labels on the side held are both skipped')
    # 9. the same under Inverted direction: the exemption reads xpwPos (a real long is the normal-frame short)
    r = _hand2([E, F1, F2], dict(NOEX, maxOpen=1, xpwInv=True), nShort=[1, 0, 0], nLong=[0, 2, 0])
    report(_both(r, 3, [(0, dict(id='L0-1', dir=1, sig_dir=-1, exit_kind='reverse', exit_px=100.2)),
                        (1, dict(id='S1-1', dir=-1, sig_dir=1, exit_kind='end')), (2, dict(id='S1-2', dir=-1))],
                 reverse_over_room=1, raw_long=1, raw_short=1),
           'audit 9: inverted, Max open entries 1: the SHORT label is a real buy (L0-1); two LONG labels reverse it '
           'as real sells S1-1, S1-2')
    # 10. one-side mode, 1665-1670: the entry signal held back closes the position only with oppCloses
    lo = "Long only (buy only)"
    r = _hand2([E, F1, F2], dict(NOEX, tradeDir=lo), nLong=[1, 0, 0], nShort=[0, 1, 0])
    ok = _both(r, 1, [(0, dict(id='L0-1', exit_kind='close_all', exit_px=100.2, exit_bar=1))], raw_short=0)
    r = _hand2([E, F1, F2], dict(NOEX, tradeDir=lo, oppCloses=False), nLong=[1, 0, 0], nShort=[0, 1, 0])
    ok = ok and _both(r, 1, [(0, dict(id='L0-1', exit_kind='end', exit_bar=2))], close_all_bars=0)
    r = _hand2([E, F1, F2], dict(NOEX, tradeDir=lo), nShort=[1, 0, 0])
    ok = ok and _both(r, 0, raw_short=0, placed=0)
    report(ok, 'audit 10: Long only: a SHORT label closes the long (Opposite ENTER closes on), does nothing with it '
           'off, and never opens a short')
    r = _hand2([E, F1, F2], dict(NOEX, tradeDir=lo, xpwInv=True), nShort=[1, 0, 0], nLong=[0, 1, 0])
    report(_both(r, 1, [(0, dict(id='L0-1', dir=1, sig_dir=-1, exit_kind='close_all', exit_px=100.2))],
                 raw_short=1, raw_long=0),
           'audit 11: Long only + inverted: the SHORT label is the real buy, the LONG label is the opposite ENTER '
           'that closes it')
    # 12. the filter gate reads the permission of the label side, 1759 / 1770, and the FGD funnel 1796-1799
    r = _hand2([E, F1, F2], NOEX, nShort=[1, 0, 0], buyOk=[False, True, True])
    ok = _both(r, 1, [(0, dict(id='S0-1', dir=-1))], blocked_short=0, blocked_long=0)
    r = _hand2([E, F1, F2], NOEX, nShort=[1, 0, 0], sellOk=[False, True, True])
    ok = ok and _both(r, 0, raw_short=1, blocked_short=1, raw_long=0, blocked_long=0)
    r = _hand2([E, F1, F2], NOEX, nLong=[1, 0, 0], buyOk=[False, True, True])
    ok = ok and _both(r, 0, raw_long=1, blocked_long=1, raw_short=0, blocked_short=0)
    r = _hand2([E, F1, F2], dict(NOEX, xpwInv=True), nLong=[1, 0, 0], sellOk=[False, True, True])
    ok = ok and _both(r, 1, [(0, dict(id='S0-1', dir=-1, sig_dir=1))], blocked_long=0)
    report(ok, 'audit 12: a SHORT entry needs the sell permission only, a LONG entry the buy permission only (also '
           'when it is placed as a sell under Inverted direction); FGD blocked counts on the label side')
    # 13. limit mode, 1715-1722: close_all does not cancel pending entries; the close through oppL (one-side
    #     mode) leaves the pending long live: it fills on the next bar
    r = _hand2([LB, (100.5, 100.6, 98.5, 99.5), (99.5, 100.0, 99.2, 99.8), (99.8, 99.9, 98.0, 98.2)],
               dict(lim, tradeDir=lo), nLong=[1, 1, 0, 0], nShort=[0, 0, 1, 0])
    report(_both(r, 2, [(0, dict(id='L0-1', entry_px=99.0, exit_kind='close_all', exit_px=99.8, exit_bar=2)),
                        (1, dict(id='L1-1', entry_bar=3, entry_px=98.5, exit_kind='end'))], pend_cancelled=0),
           'audit 13: limit mode, Long only: the opposite ENTER closes the long at 99.80; the pending buy limit '
           '98.50 stays and fills on the next bar')
    # 14. limit mode, 1669: an exit-only label does not close on a bar with a new entry of the side held
    #     (bar 0 closes at its low: the limit fills at that close, T6)
    r = _hand2([(100.0, 101.0, 99.0, 99.0), (99.0, 99.5, 98.9, 99.2), (99.2, 99.3, 99.0, 99.1)], lim,
               nLong=[1, 1, 0], exitL=[False, True, False])
    report(_both(r, 1, [(0, dict(id='L0-1', entry_bar=0, entry_px=99.0, exit_kind='end', exit_px=99.1))],
                 close_all_bars=0, pend_placed=2, pend_open_end=1),
           'audit 14: limit mode, exit-only label + a LONG entry on the same bar: the long is not closed')
    # 15. time stop, 1751: the bars are counted from the FILL bar of a pending entry, not from its label
    r = _hand2([LB, (100.5, 100.8, 100.0, 100.4), (100.4, 100.5, 98.8, 99.2), (99.2, 99.5, 99.0, 99.3),
                (99.3, 99.6, 99.1, 99.4), (99.4, 99.5, 99.3, 99.4)], dict(lim, timeStop=2), nLong=[1, 0, 0, 0, 0, 0])
    report(_both(r, 1, [(0, dict(id='L0-1', entry_bar=2, entry_px=99.0, exit_kind='time', exit_bar=4, exit_px=99.4))]),
           'audit 15: limit mode, time stop 2: label on bar 0, filled on bar 2, closed at the close of bar 4')
    # 16. T9: on a bar with close_all and a due time stop the trade is close_all (placed first)
    r = _hand2([E, F1, F2], dict(NOEX, timeStop=1), nLong=[1, 0, 0], exitL=[False, True, False])
    report(_both(r, 1, [(0, dict(exit_kind='close_all', exit_bar=1, exit_px=100.2))], exit_time=0),
           'audit 16: close_all and a due time stop on one bar: the trade is close_all')
    # 17. inverted limit mode, 1740-1743 (T6 / T7): the sell stop at the candle low is tested like the buy
    #     limit it replaces: no fill at a close above the low; a fill at a close equal to the low
    r = _hand2([LB, (100.5, 100.8, 100.0, 100.4)], dict(lim, xpwInv=True), nLong=[1, 0])
    ok = _both(r, 0, pend_placed=1, pend_filled_at_close=0, pend_open_end=1)
    r = _hand2([(100.0, 101.0, 99.0, 99.0), (99.0, 99.2, 98.8, 99.1)], dict(lim, xpwInv=True), nLong=[1, 0])
    ok = ok and _both(r, 1, [(0, dict(id='S0-1', dir=-1, entry_bar=0, entry_px=99.0, exit_kind='end'))],
                      pend_filled_at_close=1)
    report(ok, 'audit 17: inverted limit mode: the sell stop at the low 99.00 is not filled at a close of 100.50, '
           'and is filled at a close equal to the low')
    # 18. 1745: trail_offset = max(trDist, 1 tick). Points 0.5 -> 1 tick = 0.01: armed at 101.50, the fall to
    #     101.495 does not reach 101.49; the next bar does
    r = _hand2([E, (100.25, 101.5, 100.125, 101.495), (101.495, 101.5, 101.25, 101.375)], dict(trDistPts=0.5),
               nLong=[1, 0, 0])
    report(_both(r, 1, [(0, dict(exit_kind='trail', exit_px=101.49, exit_bar=2, tr_off=0.01))]),
           'audit 18: trail distance 0.5 pts is floored to 1 tick: trail at 101.49 on the second bar, not 101.495 '
           'on the first')
    # 19. 1745: trail_points 0 = armed at the fill: stop 100.00 - 0.75 at once, also when price never rises
    r = _hand2([E, (99.875, 99.875, 99.0, 99.125)], dict(trActPts=0.0), nLong=[1, 0])
    report(_both(r, 1, [(0, dict(exit_kind='trail', exit_px=99.25, exit_bar=1))]),
           'audit 19: trail activation 0: armed at the fill, trail at 99.25 on a bar that only falls')
    # 20. the trailing stop does not exist before the activation price is reached: low first (1.25 >= 1.00), the
    #     fall to 99.00 passes "fill - offset" 99.25 with the trail not armed yet; the rise to 101.25 arms it
    #     (stop 100.50), the close 101.00 stays above
    r = _hand2([E, (100.0, 101.25, 99.0, 101.0)], {}, nLong=[1, 0])
    report(_both(r, 1, [(0, dict(exit_kind='end', exit_px=101.0))]),
           'audit 20: the bar falls to 99.00 before it reaches the activation 101.00: no trailing stop at 99.25, '
           'nothing exits')
    # 21. T4: a target already passed at the open fills at the open (path tv too)
    r = _hand2([E, (103.5, 103.75, 103.25, 103.625)], dict(trailOn=False), nLong=[1, 0])
    report(_both(r, 1, [(0, dict(exit_kind='tp', exit_px=103.5, exit_bar=1))]),
           'audit 21: the bar opens at 103.50 above the target 103.00: tp at the open 103.50')
    # 22. ATR mode, 1687-1688: the target is a multiple of the STOP distance (ATR 1.00: stop 3.00, R 0.5 -> 1.50)
    one = {14: np.ones(3)}
    ab = [E, (100.25, 102.0, 100.125, 101.75), (101.75, 101.8, 101.0, 101.1)]
    r = _hand2(ab, dict(exitUnit='ATR', trailOn=False), nLong=[1, 0, 0], atr=one)
    ok = _both(r, 1, [(0, dict(exit_kind='end', sl_px=97.0, tp_px=103.0))])
    r = _hand2(ab, dict(exitUnit='ATR', trailOn=False, tpRMult=0.5), nLong=[1, 0, 0], atr=one)
    ok = ok and _both(r, 1, [(0, dict(exit_kind='tp', exit_px=101.5, exit_bar=1))])
    r = _hand2(ab, dict(exitUnit='ATR', slAtrMult=0.0), nLong=[1, 0, 0], atr=one)
    ok = ok and _both(r, 1, [(0, dict(exit_kind='trail', exit_px=101.25, exit_bar=2, tr_act_px=101.0))]) and all(
        np.isnan(r[p][0].iloc[0]['sl_px']) and np.isnan(r[p][0].iloc[0]['tp_px']) for p in r)
    report(ok, 'audit 22: ATR mode with ATR 1.00: stop 97.00 and target 103.00 (1 R); R 0.5 -> tp at 101.50; a stop '
           'of 0 switches the target off too (the trail 1.0 / 0.75 ATR still works: 101.25)')
    # 23. S3, 1702: Risk sizing reads strategy.equity WITH the open profit of the bar's close
    #     entry 1: 10,000 x 1 % / 3.00 = 33.33; entry 2 at 101.50: (10,000 + 33.33 x 1.50) x 1 % / 3.00 = 33.4999 -> 33.49
    r = _hand2([E, (100.25, 101.75, 100.125, 101.5), (101.5, 101.6, 101.4, 101.5)],
               dict(trailOn=False, qtyMode='Risk', riskPct=1.0, qtyMax=50.0), nLong=[1, 1, 0])
    report(_both(r, 2, [(0, dict(qty=33.33)), (1, dict(qty=33.49, entry_px=101.5))]),
           'audit 23: Risk 1 %: 33.33 at 10,000, then 33.49 on an equity of 10,049.995 (open profit included)')
    # 24. ta.atr = rma of the TRUE range (all three legs)
    a = M._atr(np.array([101.0, 99.0, 105.0]), np.array([99.0, 97.0, 104.0]), np.array([100.0, 98.0, 104.5]), 2)
    report(bool(np.isnan(a[0]) and abs(a[1] - 2.5) < 1e-12 and abs(a[2] - 4.75) < 1e-12),
           'audit 24: ATR(2) of three bars with a gap down and a gap up: na, 2.50, 4.75')
    # 26. limit mode, 1716: "Limit valid (bars)" 2: the order of bar 0 is live on bars 1 and 2 (the cancel is
    #     placed in the run of bar 2, after that bar's path) and gone on bar 3
    q2 = (100.4, 100.6, 100.1, 100.3)
    r = _hand2([LB, quiet, q2, (100.3, 100.4, 98.0, 98.5)], dict(lim, limitBars=2), nLong=[1, 0, 0, 0])
    ok = _both(r, 0, pend_placed=1, pend_cancelled=1, pend_cancel_stale=1, pend_cancel_against=0)
    r = _hand2([LB, quiet, down, (98.5, 98.6, 98.4, 98.5)], dict(lim, limitBars=2), nLong=[1, 0, 0, 0])
    ok = ok and _both(r, 1, [(0, dict(id='L0-1', entry_bar=2, entry_px=99.0, exit_kind='end'))], pend_cancelled=0)
    report(ok, 'audit 26: limit valid 2 bars: no fill at 99.00 on bar 3 (cancelled at the close of bar 2); a touch '
           'on bar 2 itself still fills')
    # 25. fair halves: a trade entered on the bar that closes exactly at mid belongs to the first half
    flat = (100.0, 100.1, 99.9, 100.0)
    r = _hand2([flat] * 5, NOEX, nLong=[0, 0, 1, 0, 0])
    report(_both(r, 1, [(0, dict(entry_bar=2, entry_time=180))], h1_trades=1, h2_trades=0),
           'audit 25: window 60..300, mid 180: the trade entered at t_close 180 is a first-half trade')


SECTIONS = dict(sub=sec_sub, unit=sec_unit, audit=sec_audit, fake=sec_fake, ref=sec_ref, engine=sec_engine,
                money=sec_money, inv=sec_inv, timing=sec_timing, abc=sec_abc)
ORDER = ('unit', 'audit', 'sub', 'fake', 'ref', 'engine', 'money', 'inv', 'timing', 'abc')


def main():
    args = sys.argv[1:]
    if args and args[0] == '--child':
        child(args[1], args[2:])
        print('CHILD DONE', flush=True)
        return 1 if NFAIL else 0
    todo = args or list(ORDER)
    t0 = time.time()
    for s in todo:
        if s in ('mag1',):
            s = 'abc'
        if s not in SECTIONS:
            print('unknown section %r (known: %s)' % (s, ', '.join(ORDER)))
            return 2
        t1 = time.time()
        SECTIONS[s]()
        print('-- section %s: %.0fs, peak RSS %.2f GB' % (s, time.time() - t1, rss_gb()), flush=True)
        CMP._memo.clear()
        gc.collect()
    print('TOTAL: %d PASS, %d FAIL, %.0fs' % (NPASS, NFAIL, time.time() - t0))
    return 1 if NFAIL else 0


if __name__ == '__main__':
    sys.exit(main())
