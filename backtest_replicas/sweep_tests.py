"""sweep_tests.py: tests T1-T4 of SWEEP_SPEC.md and T5-T7 of SWEEP_SPEC_2.md for sweep_core.py.

Usage: python3 -I sweep_tests.py [T1 T2 T3 TM TX T5 TC T6 T7 TS T4]      (default: all)
Prints PASS / FAIL per test; exits 1 on any failure.

T1  tv == canonical: random settings (units ticks / price / percent, activation, offset,
    trailOn, slOn, slDist, filter on / off) on BTC 60, BTC 5, XAU 60, XAU 15 short windows:
    run_cfg(.., 'tv') trade arrays == engine.backtest() trades exactly, and metrics_fast ==
    run_tf.metrics() for both cost modes (rel 1e-9 on floats, exact on counts); the extra
    fields (exit counts, avg_bars_held, max_expo) against slow Python references.
T2  mag on chart "1" (real 1-minute sub-bars) == tv on chart "1" (BTC, XAU; full windows).
T3  mag with a fake sub-bar table (each chart bar its own sub-bar) == tv (BTC 60, XAU 60;
    full windows), and _run_mag's non-step-1 code == engine._run's current source.
TM  mag with real multi-minute sub-bars (BTC 60 / 5, XAU 240 / 120 / 15; full windows) ==
    canonical engine._run on the 1-minute sub-bar series with the chart's signals on the last
    sub-bar of each chart bar (an independent reference for the Bar Magnifier walk).
TX  metrics_fast == run_tf.metrics (and max_expo == its reference) on synthetic trade sets
    dense in timestamp ties, exits on the entry bar, exits at the half split, entries at the
    half split, no losses, equity driven below zero; every cost mode (tv0, cost, stress), the
    fair halves (as T6), and the unrounded values within 1e-9.
T5  rev labels: run_cfg(.., 'tv') on the sig with XPW "Reverse every label" on == engine.backtest
    with that sig (trade arrays exactly; metrics == run_tf.metrics), 20 settings per T1 window
    (random filter); the reversed frame swaps the entries and keeps the exits; the sweep's cached
    rev frame (load_sig) == a fresh xpw_signals(.., {'reverseAll': True}) on full windows and
    trades == engine.backtest on it; the cached normal frame read after it == a fresh normal one.
TC  input cache keeps labels apart: empty cache dir, both orders (normal / rev first), 3 passes:
    every load == a fresh frame of its own labels, one file per labels with distinct keys, files
    never rewritten on a read.
T6  fair halves: h1r_pct / h2r_pct / h1_trades / h2_trades / h1r_pf / h2r_pf == run_tf.metrics()
    on the trades entered in each half (entry_time <= mid / > mid, start / end set to that half),
    the rounded values and the unrounded ones within 1e-9, on the T5 settings x labels normal /
    rev x the three cost modes (stress: run_tf.cost_per_unit swapped for the stressed variant).
T7  stress: metrics_fast()['stress'] == run_tf.metrics() with the stressed cost function (every
    field, exit counts, avg_bars_held, max_expo; unrounded within 1e-9) on the same settings.
TS  sweep.py end to end: XAU 240 full grid, both paths and labels, 3 workers: parquet structure
    (row count, unique (filter, path, labels, setting) keys, one default row per group), sampled
    rows of every group == independent computation from fresh xpw / fgf frames (tv: engine.backtest
    + run_tf.metrics, every cost mode and the fair halves; mag: _run_mag), rev != normal; 1 worker
    on a grid subset == the 3-worker rows; XAU "1" on a grid subset: mag rows == tv rows per labels.
T4  timing: full grid on BTC "1", tv, single process, once per (labels, filter); one mag setting
    on BTC "60" full window.
"""
from __future__ import annotations

import contextlib
import math
import os
import pickle
import shutil
import sys
import tempfile
import time
import traceback

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import sweep_core as sc   # noqa: E402
import engine             # noqa: E402
import run_tf             # noqa: E402
import xpw                # noqa: E402
import fgf                # noqa: E402

SEED = 20261118
T1_WINDOWS = [('BTC', '60', 1735689600, 1740787200),     # 2025-01-01 -> 2025-03-01
              ('BTC', '5', 1735689600, 1736899200),      # 2025-01-01 -> 2025-01-15
              ('XAU', '60', 1514851200, 1519862400),     # 2018-01-02 -> 2018-03-01
              ('XAU', '15', 1514851200, 1519862400)]
T1_PER_WINDOW = 60
REL = 1e-9


class Fail(Exception):
    pass


# ------------------------------------------------------------------ helpers
def _pct_draw(rng, allow_zero):
    """A distance in percent of price: 0, a grid value, or log-uniform 0.001% .. 6%."""
    u = rng.random()
    if allow_zero and u < 0.15:
        return 0.0
    if u < 0.5:
        return float(rng.choice(sc.OFFS + sc.ACTS[1:]))
    return float(10.0 ** rng.uniform(-3.0, 0.8))


def _in_unit(rng, pct, unit, ref):
    if unit == 'percent':
        return pct
    price = pct / 100.0 * ref
    if unit == 'price':
        return round(price, 2) if rng.random() < 0.5 else price
    t = price / sc.MINTICK
    return float(round(t)) if rng.random() < 0.5 else t


def random_cfg(rng, ref):
    """A random setting in a random unit (ref: a typical price of the window)."""
    unit = str(rng.choice(['ticks', 'price', 'percent']))
    cfg = dict(tag='rand', trailUnit=unit, trailOn=bool(rng.random() < 0.85), slOn=bool(rng.random() < 0.5))
    cfg['trailAct'] = _in_unit(rng, _pct_draw(rng, True), unit, ref)
    off = _pct_draw(rng, False)
    if rng.random() < 0.05:                       # below one tick: clamped to 1 tick
        off = 0.3 * sc.MINTICK / ref * 100.0
    cfg['trailOff'] = _in_unit(rng, off, unit, ref)
    cfg['slDist'] = _in_unit(rng, _pct_draw(rng, False), unit, ref)
    return cfg


def grid_sample(rng, k):
    G = sc.grid()
    idx = rng.choice(len(G), size=k - 1, replace=False)
    return [G[-1]] + [G[int(i)] for i in idx]      # always include the default row


def feq(a, b):
    a_none = a is None or (isinstance(a, float) and math.isnan(a))
    b_none = b is None or (isinstance(b, float) and math.isnan(b))
    if a_none or b_none:
        return a_none and b_none
    a = float(a)
    b = float(b)
    if a == b:
        return True
    return abs(a - b) <= REL * max(abs(a), abs(b))


KIND_FROM_NAME = {'trail': 'exit_trail', 'sl': 'exit_sl', 'close_all': 'exit_close_all',
                  'reverse': 'exit_reverse', 'end': 'exit_end'}
REF_KEYS = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'half1_pct', 'half2_pct',
            'avg_trade_ret_pct', 'max_concurrent')


def ref_max_expo(pair, trades, with_cost):
    """Slow reference for max_expo: run_tf.metrics()'s event loop, and after each entry the sum
    over open trades (entered, not yet exited) of qty x entry price over closed equity."""
    t = trades.sort_values(['exit_time', 'entry_time']).reset_index(drop=True)
    gross = t['dir'].astype(float) * (t['exit_px'] - t['entry_px'])
    cst = (np.array([run_tf.cost_per_unit(pair, a, b) for a, b in zip(t['entry_px'], t['exit_px'])])
           if with_cost else np.zeros(len(t)))
    pnl_u = gross.values - cst
    ev = ([(t['exit_time'].values[i], 0, i) for i in range(len(t))]
          + [(t['entry_time'].values[i], 1, i) for i in range(len(t))])
    ev.sort()
    eq = run_tf.CAP
    qty = np.zeros(len(t))
    state = np.zeros(len(t), np.int8)       # 0 not entered, 1 open, 2 exited
    best = -np.inf
    for ts, kind, i in ev:
        if kind == 1:
            qty[i] = run_tf.FRAC * max(eq, 0.0) / t['entry_px'].values[i]
            if state[i] == 0:
                state[i] = 1
                op = state == 1
                expo = (qty[op] * t['entry_px'].values[op]).sum() / eq if eq > 0 else np.inf
                best = max(best, expo)
        else:
            eq += qty[i] * pnl_u[i]
            state[i] = 2
    return best if best > -np.inf else np.nan


def compare_trades(R, P, tr):
    """run_cfg arrays vs engine.backtest trades; returns a list of mismatch strings."""
    bad = []
    if R['n'] != len(tr):
        return ['trade count %d vs %d' % (R['n'], len(tr))]
    if R['n'] == 0:
        return bad
    rows = P['rows']
    checks = [('dir', R['dir'].astype(np.int64), tr['dir'].to_numpy(np.int64)),
              ('entry_row', rows[R['erow']], tr['entry_row'].to_numpy(np.int64)),
              ('exit_row', rows[R['xrow']], tr['exit_row'].to_numpy(np.int64)),
              ('entry_px', R['epx'], tr['entry_px'].to_numpy(np.float64)),
              ('exit_px', R['xpx'], tr['exit_px'].to_numpy(np.float64)),
              ('exit_kind', np.array([sc.KIND_NAMES[int(x)] for x in R['xkind']], dtype=object),
               tr['exit_kind'].to_numpy(object)),
              ('entry_time', P['t_close'][R['erow']], tr['entry_time'].to_numpy(np.int64)),
              ('exit_time', P['t_close'][R['xrow']], tr['exit_time'].to_numpy(np.int64))]
    for name, a, b in checks:
        if not np.array_equal(a, b):
            k = int(np.nonzero(a != b)[0][0])
            bad.append('%s differs at trade %d: %r vs %r' % (name, k, a[k], b[k]))
    return bad


def compare_metrics(m, ref, tr, pair, cost):
    bad = []
    for k in REF_KEYS:
        if k not in ref:
            continue
        a, b = m[k], ref[k]
        if k in sc.INT_COLS:
            if int(a) != int(b):
                bad.append('%s %r vs %r' % (k, a, b))
        elif not feq(a, b):
            bad.append('%s %r vs %r' % (k, a, b))
    if ref.get('trades', 0) == 0:
        return bad
    kinds = ref['exit_kinds']
    for name, col in KIND_FROM_NAME.items():
        if int(m[col]) != int(kinds.get(name, 0)):
            bad.append('%s %r vs %r' % (col, m[col], kinds.get(name, 0)))
    if not feq(m['avg_bars_held'], float((tr['exit_row'] - tr['entry_row']).mean())):
        bad.append('avg_bars_held %r' % m['avg_bars_held'])
    me = ref_max_expo(pair, tr, cost)
    if not (m['max_expo'] == me or (np.isnan(m['max_expo']) and np.isnan(me))
            or abs(m['max_expo'] - me) <= 1e-9 * max(1.0, abs(me))):
        bad.append('max_expo %r vs %r' % (m['max_expo'], me))
    return bad


def same_run(Ra, Rb):
    if Ra['n'] != Rb['n']:
        return False
    for k in ('dir', 'erow', 'k', 'epx', 'xrow', 'xpx', 'xkind'):
        if not np.array_equal(Ra[k], Rb[k]):
            return False
    return True


# ------------------------------------------------- references for SWEEP_SPEC_2
def stress_cost_per_unit(pair, entry, exitp):
    """run_tf.cost_per_unit with the stressed costs (SWEEP_SPEC_2 2.)."""
    if pair == 'XAU':
        return 0.50 + 0.02
    return 0.00035 * (entry + exitp) + 0.20 + 0.02


def _no_round(x, nd=None):
    return x


@contextlib.contextmanager
def ref_mode(mode, unrounded=False):
    """run_tf.metrics() as the reference for cost mode `mode` ('tv0' | 'cost' | 'stress'): yields
    its with_cost flag; 'stress' swaps run_tf.cost_per_unit for stress_cost_per_unit (metrics()
    and ref_max_expo look it up at call time); unrounded shadows the builtin round() in run_tf's
    globals so metrics() returns its values before rounding. Restored on exit."""
    saved = run_tf.cost_per_unit
    try:
        if mode == 'stress':
            run_tf.cost_per_unit = stress_cost_per_unit
        if unrounded:
            run_tf.round = _no_round
        yield mode != 'tv0'
    finally:
        run_tf.cost_per_unit = saved
        run_tf.__dict__.pop('round', None)


def ref_metrics(pair, tr, start, end, mode, unrounded=False):
    with ref_mode(mode, unrounded) as cost:
        return run_tf.metrics(pair, tr, start, end, cost)


RAW_SLOTS = (('net_pct', sc.M_NET), ('pf', sc.M_PF), ('win_pct', sc.M_WIN), ('max_dd_pct', sc.M_DD),
             ('half1_pct', sc.M_H1), ('half2_pct', sc.M_H2), ('avg_trade_ret_pct', sc.M_AVG))


def raw_eq(a, b):
    """unrounded kernel value vs unrounded reference: None / NaN alike, else rel 1e-9."""
    return feq(float(a), b)


def compare_raw(raw_row, refu):
    """metrics_raw row vs run_tf.metrics() unrounded; returns (bad list, n compared, n bit-equal)."""
    bad = []
    n_cmp = n_exact = 0
    if refu.get('trades', 0) == 0:
        return bad, 0, 0
    for k, slot in RAW_SLOTS:
        a, b = raw_row[slot], refu[k]
        n_cmp += 1
        if b is not None and float(a) == float(b):
            n_exact += 1
        elif b is None and np.isnan(a):
            n_exact += 1
        if not raw_eq(a, b):
            bad.append('unrounded %s %r vs %r' % (k, a, b))
    return bad, n_cmp, n_exact


def split_halves(tr, start, end):
    """The direct computation of SWEEP_SPEC_2 3.: trades entered in each half, with start / end
    set to that half."""
    mid = start + (end - start) // 2
    return ((tr[tr['entry_time'] <= mid], start, mid), (tr[tr['entry_time'] > mid], mid, end))


def compare_halves(pair, m, raw_row, tr, start, end, mode):
    """m = metrics_fast()[mode], raw_row = metrics_raw()[mode index] vs run_tf.metrics() on the
    trades entered in each half. Returns (bad list, n compared unrounded, n bit-equal)."""
    bad = []
    n_cmp = n_exact = 0
    for h, (part, s0, s1) in enumerate(split_halves(tr, start, end)):
        nm = 'h%d' % (h + 1)
        ref = ref_metrics(pair, part, s0, s1, mode)
        refu = ref_metrics(pair, part, s0, s1, mode, unrounded=True)
        nt = ref['trades']
        if int(m[nm + '_trades']) != nt or int(raw_row[sc.M_H1N + h]) != nt:
            bad.append('%s_trades %r vs %r' % (nm, m[nm + '_trades'], nt))
            continue
        if nt == 0:
            if not (np.isnan(m[nm + 'r_pct']) and np.isnan(m[nm + 'r_pf'])):
                bad.append('%s empty half: %r %r, expected NaN' % (nm, m[nm + 'r_pct'], m[nm + 'r_pf']))
            continue
        if not feq(m[nm + 'r_pct'], ref['net_pct']):
            bad.append('%sr_pct %r vs %r' % (nm, m[nm + 'r_pct'], ref['net_pct']))
        if not feq(m[nm + 'r_pf'], ref['pf']):
            bad.append('%sr_pf %r vs %r' % (nm, m[nm + 'r_pf'], ref['pf']))
        for slot, k in ((sc.M_H1R + h, 'net_pct'), (sc.M_H1PF + h, 'pf')):
            a, b = raw_row[slot], refu[k]
            n_cmp += 1
            n_exact += int((b is None and np.isnan(a)) or (b is not None and float(a) == float(b)))
            if not raw_eq(a, b):
                bad.append('unrounded %sr %s %r vs %r' % (nm, k, a, b))
    return bad, n_cmp, n_exact


# -------------------------------------------------------------------- tests
def t1():
    rng = np.random.default_rng(SEED)
    n_cfg = 0
    n_tr = 0
    for pair, tf, a, b in T1_WINDOWS:
        t0 = time.time()
        sig_full = xpw.xpw_signals(pair, tf, a, b, {})
        perm = fgf.fgf_permissions(pair, tf, a, b, {})
        sig_trim = sc._trim_sig(sig_full)            # what the sweep caches
        P = {f: sc.prep(pair, tf, sig_trim, perm, f) for f in (False, True)}
        ref = float(np.median(P[False]['c']))
        cfgs = [(sc.grid()[-1], False), (sc.grid()[-1], True)]
        cfgs += [(random_cfg(rng, ref), bool(rng.random() < 0.5)) for _ in range(T1_PER_WINDOW - 2)]
        stats = {'trail': 0, 'sl': 0, 'close_all': 0, 'reverse': 0, 'end': 0}
        for cfg, f in cfgs:
            R = sc.run_cfg(P[f], cfg, 'tv')
            params = dict(sc.cfg_params(cfg), fgfOn=f)
            tr, _ = engine.backtest(pair, tf, sig_full, perm if f else None, params)
            bad = compare_trades(R, P[f], tr)
            m = sc.metrics_fast(pair, R, P[f]['t_close'], a, b)
            for cost, key in ((False, 'tv0'), (True, 'cost')):
                refm = run_tf.metrics(pair, tr, a, b, cost)
                bad += ['%s: %s' % (key, x) for x in compare_metrics(m[key], refm, tr, pair, cost)]
            if bad:
                raise Fail('%s %s filter=%s cfg=%r: %s' % (pair, tf, f, cfg, '; '.join(bad[:5])))
            n_cfg += 1
            n_tr += R['n']
            for kname, v in tr['exit_kind'].value_counts().items():
                stats[kname] += int(v)
        print('  T1 %s %-3s %d bars: %d settings OK, exit kinds seen %s (%.1fs)'
              % (pair, tf, len(sig_full), len(cfgs), stats, time.time() - t0), flush=True)
    return '%d settings, %d trades: trade arrays identical, metrics identical (tv0 and cost)' % (n_cfg, n_tr)


def _mag_vs_tv(pair, tf, k, fake, rng):
    sig, perm = sc.load_inputs(pair, tf)
    start, end = run_tf.WINDOWS[pair]
    P = {f: sc.prep(pair, tf, sig, perm, f) for f in (False, True)}
    t0 = time.time()
    sub = sc.fake_sub_bars(P[False]) if fake else sc.sub_bars(pair, tf, P[False]['rows'])
    tsub = time.time() - t0
    ref = float(np.median(P[False]['c']))
    cfgs = grid_sample(rng, k - 4) + [random_cfg(rng, ref) for _ in range(4)]
    n_tr = 0
    for cfg in cfgs:
        f = bool(rng.random() < 0.5)
        Rt = sc.run_cfg(P[f], cfg, 'tv')
        Rm = sc.run_cfg(P[f], cfg, 'mag', sub=sub)
        if not same_run(Rt, Rm):
            raise Fail('%s %s filter=%s cfg=%r: mag != tv (%d vs %d trades)' % (pair, tf, f, cfg, Rm['n'], Rt['n']))
        mt = sc.metrics_fast(pair, Rt, P[f]['t_close'], start, end)
        mm = sc.metrics_fast(pair, Rm, P[f]['t_close'], start, end)
        if repr(mt) != repr(mm):
            raise Fail('%s %s cfg=%r: metrics differ' % (pair, tf, cfg))
        n_tr += Rt['n']
    print('  %s %-3s %d bars, %d sub-bars (%.1fs): %d settings identical (%d trades)'
          % (pair, tf, len(P[False]['c']), len(sub[1]), tsub, len(cfgs), n_tr), flush=True)
    return len(cfgs)


def t2():
    rng = np.random.default_rng(SEED + 2)
    n = sum(_mag_vs_tv(pair, '1', 20, False, rng) for pair in ('BTC', 'XAU'))
    return '%d settings: mag (real 1-minute sub-bars) == tv on chart "1"' % n


def t3():
    sc.check_mag_sync()
    rng = np.random.default_rng(SEED + 3)
    n = sum(_mag_vs_tv(pair, '60', 20, True, rng) for pair in ('BTC', 'XAU'))
    return '%d settings: mag (one sub-bar per chart bar) == tv; _run_mag steps 2-3 == engine._run source' % n


def chart1_equiv(P, sub):
    """The engine arrays of a chart made of the sub-bars themselves, with chart bar r's signals
    (goL / goS / nL / nS / cL / cS) on its LAST sub-bar and nothing on the others. The script then
    acts only at chart-bar closes (= last sub-bar closes), entries fill at the chart close, an
    entry's exits start at the next chart bar's first sub-bar, and every sub-bar gets its own
    rule-2 path, gap test and carried trailing state: exactly the Bar Magnifier definition."""
    ptr, so, sh, sl, sc_ = sub
    n1 = int(ptr[-1])
    last = ptr[1:] - 1
    Q = dict(o=so, h=sh, l=sl, c=sc_, maxOpen=P['maxOpen'], pyr=P['pyr'], mt=P['mt'], tol=P['tol'],
             cap=P['cap'], ocap=P['ocap'])
    for k, dt in (('goL', np.bool_), ('goS', np.bool_), ('cL', np.bool_), ('cS', np.bool_),
                  ('nL', np.int64), ('nS', np.int64)):
        a = np.zeros(n1, dt)
        a[last] = P[k]
        Q[k] = a
    return Q


def tm():
    """mag with REAL multi-minute sub-bars == canonical engine._run ('tv') on the 1-minute
    sub-bar series with the chart's signals on the last sub-bar of each chart bar (rows mapped
    back to chart bars). T2 / T3 only have one sub-bar per chart bar; this exercises the trailing
    state carried across sub-bars, the gap test at every sub-bar open and the stop at the first
    exit, against the canonical kernel."""
    rng = np.random.default_rng(SEED + 5)
    n_cfg = n_tr = n_dif = 0
    for pair, tf in (('BTC', '60'), ('BTC', '5'), ('XAU', '240'), ('XAU', '120'), ('XAU', '15')):
        sig, perm = sc.load_inputs(pair, tf)
        P = {f: sc.prep(pair, tf, sig, perm, f) for f in (False, True)}
        sub = sc.sub_bars(pair, tf, P[False]['rows'])
        ptr = sub[0]
        Q = {f: chart1_equiv(P[f], sub) for f in (False, True)}
        ref = float(np.median(P[False]['c']))
        cfgs = grid_sample(rng, 8) + [random_cfg(rng, ref) for _ in range(4)]
        t0 = time.time()
        for cfg in cfgs:
            f = bool(rng.random() < 0.5)
            Rm = sc.run_cfg(P[f], cfg, 'mag', sub=sub)
            R1 = sc.run_cfg(Q[f], cfg, 'tv')
            e1 = np.searchsorted(ptr, R1['erow'], side='right') - 1
            x1 = np.searchsorted(ptr, R1['xrow'], side='right') - 1
            same = (Rm['n'] == R1['n'] and np.array_equal(Rm['erow'], e1) and np.array_equal(Rm['xrow'], x1)
                    and np.array_equal(ptr[e1 + 1] - 1, R1['erow'])
                    and all(np.array_equal(Rm[k], R1[k]) for k in ('dir', 'k', 'epx', 'xpx', 'xkind')))
            if not same:
                raise Fail('%s %s filter=%s cfg=%r: mag != chart-1 reference (%d vs %d trades)'
                           % (pair, tf, f, cfg, Rm['n'], R1['n']))
            Rt = sc.run_cfg(P[f], cfg, 'tv')
            n_dif += int(not same_run(Rt, Rm))
            n_cfg += 1
            n_tr += Rm['n']
        print('  TM %s %-3s %d bars, %d sub-bars: %d settings identical (%.1fs)'
              % (pair, tf, len(P[False]['c']), len(sub[1]), len(cfgs), time.time() - t0), flush=True)
    if n_dif == 0:
        raise Fail('mag never differed from tv: the test does not exercise the sub-bars')
    return ('%d settings, %d trades: mag == engine._run on the sub-bar series (mag != tv in %d of them)'
            % (n_cfg, n_tr, n_dif))


def tx():
    """metrics_fast vs run_tf.metrics on synthetic trade sets dense in ties: many trades per
    entry bar, exits on the same bar as other entries, exits on the entry bar itself (as a trade
    entered on the last bar and closed 'end'), exits exactly at the half split, no losses (pf
    None), huge losses (equity <= 0, qty clamped to 0)."""
    rng = np.random.default_rng(SEED + 7)
    rng2 = np.random.default_rng(SEED + 8)                  # entries at the split (SWEEP_SPEC_2)
    names = {1: 'trail', 2: 'sl', 3: 'close_all', 4: 'reverse', 5: 'end'}
    n_sets = 0
    n_cmp = n_exact = 0
    n_at_mid = n_empty_half = 0
    for it in range(400):
        nb_ = int(rng.integers(2, 40))
        t_close = np.cumsum(rng.integers(1, 4, nb_)).astype(np.int64) * 60 + 1_000_000
        start = int(t_close[0] - 60)
        end = int(t_close[-1])
        n = int(rng.integers(1, 60))
        erow = np.sort(rng.integers(0, nb_, n)).astype(np.int64)
        kmid = np.nonzero(t_close == start + (end - start) // 2)[0]
        if len(kmid) and rng2.random() < 0.5:               # some entries exactly at the split
            erow = np.sort(np.where(rng2.random(n) < 0.3, kmid[0], erow)).astype(np.int64)
        xrow = np.minimum(erow + rng.integers(0, 6, n) * (rng.random(n) < 0.9), nb_ - 1).astype(np.int64)
        if rng.random() < 0.3:                               # some exits exactly at the split
            mid = start + (end - start) // 2
            k = np.nonzero(t_close == mid)[0]
            if len(k):
                sel = (erow <= k[0]) & (rng.random(n) < 0.5)
                xrow[sel] = k[0]
        dirs = np.where(rng.random(n) < 0.5, 1, -1).astype(np.int8)
        epx = np.round(1000.0 + rng.normal(0, 30, n), 2)
        mode = rng.random()
        move = rng.normal(0, 5, n) if mode < 0.6 else (np.abs(rng.normal(0, 5, n)) if mode < 0.8 else rng.normal(-3000, 500, n))
        xpx = np.round(epx + dirs * move, 2)
        xkind = rng.integers(1, 6, n).astype(np.int8)
        R = dict(n=n, dir=dirs, erow=erow, epx=epx, xrow=xrow, xpx=xpx, xkind=xkind)
        tr = pd.DataFrame({'dir': dirs.astype(np.int64), 'entry_row': erow, 'exit_row': xrow,
                           'entry_time': t_close[erow], 'exit_time': t_close[xrow],
                           'entry_px': epx, 'exit_px': xpx, 'exit_kind': [names[int(x)] for x in xkind]})
        mid = start + (end - start) // 2
        n_at_mid += int((t_close[erow] == mid).sum())
        n_empty_half += int((t_close[erow] <= mid).all() or (t_close[erow] > mid).all())
        for pair in ('BTC', 'XAU'):
            m = sc.metrics_fast(pair, R, t_close, start, end)
            raw = sc.metrics_raw(pair, R, t_close, start, end)
            for mi, key in enumerate(sc.MODES):
                with ref_mode(key) as cost:
                    refm = run_tf.metrics(pair, tr, start, end, cost)
                    bad = compare_metrics(m[key], refm, tr, pair, cost)
                b2, c2, e2 = compare_raw(raw[mi], ref_metrics(pair, tr, start, end, key, unrounded=True))
                b3, c3, e3 = compare_halves(pair, m[key], raw[mi], tr, start, end, key)
                bad += b2 + b3
                n_cmp += c2 + c3
                n_exact += e2 + e3
                if bad:
                    raise Fail('synthetic set %d %s %s: %s' % (it, pair, key, '; '.join(bad[:5])))
            n_sets += 1
    print('  TX: %d entries exactly at the split, %d sets with an empty half; unrounded: %d / %d values bit-equal'
          % (n_at_mid, n_empty_half, n_exact, n_cmp), flush=True)
    return ('%d synthetic trade sets (BTC and XAU costs) x tv0 / cost / stress: metrics_fast == run_tf.metrics, '
            'max_expo == reference, fair halves == metrics() per half' % n_sets)


# ------------------------------------------------------------ T5 - T7 (SWEEP_SPEC_2)
T5_PER_WINDOW = 20
_CASES: dict = {}


def cases():
    """Shared by T5-T7. Per T1 window: the full xpw frames for labels normal and rev, perm, P per
    (labels, filter on / off), and T5_PER_WINDOW settings (the default row + 9 grid rows + 10
    random settings in random units), each with a random filter."""
    if _CASES:
        return _CASES
    rng = np.random.default_rng(SEED + 11)
    for pair, tf, a, b in T1_WINDOWS:
        sig = {lab: xpw.xpw_signals(pair, tf, a, b, dict(sc.LABEL_PARAMS[lab])) for lab in sc.LABELS}
        perm = fgf.fgf_permissions(pair, tf, a, b, {})
        P = {(lab, f): sc.prep(pair, tf, sc._trim_sig(sig[lab]), perm, f) for lab in sc.LABELS for f in (False, True)}
        ref = float(np.median(P[('normal', False)]['c']))
        k_grid = T5_PER_WINDOW // 2
        cfgs = grid_sample(rng, k_grid) + [random_cfg(rng, ref) for _ in range(T5_PER_WINDOW - k_grid)]
        cfgs = [(cfg, bool(rng.random() < 0.5)) for cfg in cfgs]
        _CASES[(pair, tf, a, b)] = dict(sig=sig, perm=perm, P=P, cfgs=cfgs, runs={})
    return _CASES


def case_run(case, pair, tf, lab, ci):
    """(R = run_cfg tv, engine.backtest trades) of setting ci with labels lab, memoized."""
    key = (lab, ci)
    if key not in case['runs']:
        cfg, f = case['cfgs'][ci]
        R = sc.run_cfg(case['P'][(lab, f)], cfg, 'tv')
        tr, _ = engine.backtest(pair, tf, case['sig'][lab], case['perm'] if f else None,
                                dict(sc.cfg_params(cfg), fgfOn=f))
        case['runs'][key] = (R, tr)
    return case['runs'][key]


def t5():
    n_cfg = n_tr = n_dif = 0
    for (pair, tf, a, b), case in cases().items():
        t0 = time.time()
        sn, sr = case['sig']['normal'], case['sig']['rev']
        swap = (np.array_equal(sr['nLongRaw'].to_numpy(), sn['nShortRaw'].to_numpy())
                and np.array_equal(sr['nShortRaw'].to_numpy(), sn['nLongRaw'].to_numpy())
                and np.array_equal(sr['exitL'].to_numpy(), sn['exitL'].to_numpy())
                and np.array_equal(sr['exitS'].to_numpy(), sn['exitS'].to_numpy()))
        if not swap:
            raise Fail('%s %s: the rev frame does not swap the entries / keep the exits' % (pair, tf))
        if np.array_equal(sr['nLong'].to_numpy(), sn['nLong'].to_numpy()):
            raise Fail('%s %s: reverseAll changed no entry' % (pair, tf))
        nd = 0
        for ci, (cfg, f) in enumerate(case['cfgs']):
            R, tr = case_run(case, pair, tf, 'rev', ci)
            Pr = case['P'][('rev', f)]
            bad = compare_trades(R, Pr, tr)
            m = sc.metrics_fast(pair, R, Pr['t_close'], a, b)
            for cost, key in ((False, 'tv0'), (True, 'cost')):
                bad += ['%s: %s' % (key, x) for x in compare_metrics(m[key], run_tf.metrics(pair, tr, a, b, cost), tr, pair, cost)]
            if bad:
                raise Fail('%s %s rev filter=%s cfg=%r: %s' % (pair, tf, f, cfg, '; '.join(bad[:5])))
            Rn, _ = case_run(case, pair, tf, 'normal', ci)
            nd += int(not same_run(Rn, R))
            n_cfg += 1
            n_tr += R['n']
        n_dif += nd
        print('  T5 %s %-3s %d bars: %d rev settings == engine.backtest (rev trades != normal in %d) (%.1fs)'
              % (pair, tf, len(sr), len(case['cfgs']), nd, time.time() - t0), flush=True)
    if n_dif == 0:
        raise Fail('rev never differed from normal')
    # the sweep's own rev inputs: load_sig (cached) on full windows
    rng = np.random.default_rng(SEED + 12)
    n_full = 0
    for pair, tf in (('XAU', '60'), ('BTC', '240')):
        t0 = time.time()
        start, end = run_tf.WINDOWS[pair]
        fresh = xpw.xpw_signals(pair, tf, start, end, {'reverseAll': True})
        sr = sc.load_sig(pair, tf, 'rev')
        sr2 = sc.load_sig(pair, tf, 'rev')                  # the second read comes from the cache
        sr3, perm3 = sc.load_inputs(pair, tf, labels='rev')
        sn, perm = sc.load_inputs(pair, tf)
        for nm, x in (('load_sig', sr), ('load_sig again', sr2), ('load_inputs rev', sr3)):
            try:
                pd.testing.assert_frame_equal(x, sc._trim_sig(fresh))
            except AssertionError as e:
                raise Fail('%s %s: %s != fresh xpw_signals reverseAll: %s' % (pair, tf, nm, str(e)[:300]))
        # ... and the normal frame read after the rev one is still the normal one (no label mix-up)
        try:
            pd.testing.assert_frame_equal(sn, sc._trim_sig(xpw.xpw_signals(pair, tf, start, end, {})))
            pd.testing.assert_frame_equal(perm, fgf.fgf_permissions(pair, tf, start, end, {}))
        except AssertionError as e:
            raise Fail('%s %s: load_inputs normal != fresh xpw_signals / fgf_permissions: %s' % (pair, tf, str(e)[:300]))
        if not perm3.equals(perm):
            raise Fail('%s %s: load_inputs rev perm != normal perm' % (pair, tf))
        if not sr.index.equals(sn.index):
            raise Fail('%s %s: rev rows != normal rows' % (pair, tf))
        Pf = {f: sc.prep(pair, tf, sr, perm, f) for f in (False, True)}
        ref = float(np.median(Pf[False]['c']))
        for cfg in grid_sample(rng, 3) + [random_cfg(rng, ref)]:
            f = bool(rng.random() < 0.5)
            R = sc.run_cfg(Pf[f], cfg, 'tv')
            tr, _ = engine.backtest(pair, tf, fresh, perm if f else None, dict(sc.cfg_params(cfg), fgfOn=f))
            bad = compare_trades(R, Pf[f], tr)
            if bad:
                raise Fail('%s %s full window rev filter=%s cfg=%r: %s' % (pair, tf, f, cfg, '; '.join(bad[:5])))
            n_full += 1
            n_tr += R['n']
        print('  T5 %s %-3s full window %d bars: cached rev frame == fresh, 4 settings == engine.backtest (%.1fs)'
              % (pair, tf, len(sr), time.time() - t0), flush=True)
    return ('%d rev settings on the T1 windows + %d on full windows, %d trades: trade arrays identical to '
            'engine.backtest with the reversed sig, metrics identical' % (n_cfg, n_full, n_tr))


def t6():
    n_run = n_cmp = n_exact = 0
    n_mid = n_cross = n_tr = 0
    for (pair, tf, a, b), case in cases().items():
        t0 = time.time()
        mid = a + (b - a) // 2
        for ci, (cfg, f) in enumerate(case['cfgs']):
            for lab in sc.LABELS:
                R, tr = case_run(case, pair, tf, lab, ci)
                tc = case['P'][(lab, f)]['t_close']
                m = sc.metrics_fast(pair, R, tc, a, b)
                raw = sc.metrics_raw(pair, R, tc, a, b)
                for mi, md in enumerate(sc.MODES):
                    bad, c, e = compare_halves(pair, m[md], raw[mi], tr, a, b, md)
                    if bad:
                        raise Fail('%s %s %s filter=%s %s cfg=%r: %s' % (pair, tf, lab, f, md, cfg, '; '.join(bad[:5])))
                    n_cmp += c
                    n_exact += e
                n_run += 1
                n_tr += len(tr)
                if len(tr):
                    n_mid += int((tr['entry_time'] == mid).sum())
                    n_cross += int(((tr['entry_time'] <= mid) & (tr['exit_time'] > mid)).sum())
        print('  T6 %s %-3s: %d settings x 2 labels x 3 cost modes OK (%.1fs)'
              % (pair, tf, len(case['cfgs']), time.time() - t0), flush=True)
    print('  T6: %d trades entered exactly at mid (-> half 1), %d entered in half 1 and exited in half 2'
          % (n_mid, n_cross), flush=True)
    return ('%d runs (%d trades) x tv0 / cost / stress: h1r / h2r pct, pf, trades == run_tf.metrics() per '
            'half; unrounded %d / %d values bit-equal (rest within 1e-9)' % (n_run, n_tr, n_exact, n_cmp))


def t7():
    n_run = n_cmp = n_exact = n_tr = 0
    for (pair, tf, a, b), case in cases().items():
        t0 = time.time()
        for ci, (cfg, f) in enumerate(case['cfgs']):
            for lab in sc.LABELS:
                R, tr = case_run(case, pair, tf, lab, ci)
                tc = case['P'][(lab, f)]['t_close']
                m = sc.metrics_fast(pair, R, tc, a, b)['stress']
                raw = sc.metrics_raw(pair, R, tc, a, b)[sc.MODES.index('stress')]
                with ref_mode('stress') as cost:
                    ref = run_tf.metrics(pair, tr, a, b, cost)
                    bad = compare_metrics(m, ref, tr, pair, cost)
                b2, c, e = compare_raw(raw, ref_metrics(pair, tr, a, b, 'stress', unrounded=True))
                bad += b2
                if bad:
                    raise Fail('%s %s %s filter=%s cfg=%r: %s' % (pair, tf, lab, f, cfg, '; '.join(bad[:5])))
                n_cmp += c
                n_exact += e
                n_run += 1
                n_tr += len(tr)
        print('  T7 %s %-3s: %d settings x 2 labels OK (%.1fs)' % (pair, tf, len(case['cfgs']), time.time() - t0),
              flush=True)
    return ('%d runs (%d trades): stress metrics == run_tf.metrics() with the stressed cost function '
            '(every field, exit counts, avg_bars_held, max_expo); unrounded %d / %d values bit-equal'
            % (n_run, n_tr, n_exact, n_cmp))


def tc():
    """The input cache keeps the labels apart. In an empty cache dir, in both orders (normal then
    rev, rev then normal): load_inputs / load_sig compute and write two files with different keys,
    later calls read them back without rewriting them, and every frame equals a fresh
    xpw_signals / fgf_permissions of its own labels."""
    pair, tf = 'XAU', '240'
    start, end = run_tf.WINDOWS[pair]
    if sc._IMPORTED_MTIMES is None:
        raise Fail('sweep_core caching is disabled in this process (xpw / fgf imported before it?)')
    fresh = {lab: sc._trim_sig(xpw.xpw_signals(pair, tf, start, end, dict(sc.LABEL_PARAMS[lab]))) for lab in sc.LABELS}
    perm0 = fgf.fgf_permissions(pair, tf, start, end, {})
    if fresh['normal'].equals(fresh['rev']):
        raise Fail('normal and rev frames are equal: the test cannot tell them apart')

    def same(x, y, what):
        try:
            pd.testing.assert_frame_equal(x, y)
        except AssertionError as e:
            raise Fail('%s: %s' % (what, str(e)[:300]))

    saved = sc.CACHE
    n_load = 0
    for order in (('normal', 'rev'), ('rev', 'normal')):
        tmp = tempfile.mkdtemp(prefix='_cache_test_', dir=W)
        try:
            sc.CACHE = tmp
            stamps = None
            for rep in range(3):                 # 0: computed and written; 1, 2: read back
                for lab in order:
                    what = 'order %s pass %d %s' % ('/'.join(order), rep, lab)
                    if lab == 'normal':
                        s, p = sc.load_inputs(pair, tf, verbose=False)
                        same(p, perm0, what + ' perm')
                    else:
                        s = sc.load_sig(pair, tf, lab, verbose=False)
                        s2, p = sc.load_inputs(pair, tf, verbose=False, labels=lab)
                        same(s2, fresh[lab], what + ' load_inputs(labels=%s) sig' % lab)
                        same(p, perm0, what + ' load_inputs(labels=%s) perm' % lab)
                        n_load += 1
                    same(s, fresh[lab], what + ' sig')
                    n_load += 1
                files = sorted(f for f in os.listdir(tmp) if f.endswith('.pkl'))
                if len(files) != 2:
                    raise Fail('order %s pass %d: cache files %r, expected one per labels' % ('/'.join(order), rep, files))
                st = {f: os.stat(os.path.join(tmp, f)).st_mtime_ns for f in files}
                if rep == 0:
                    stamps = st
                elif st != stamps:
                    raise Fail('order %s pass %d: a cache file was rewritten on a read (labels share a slot?)'
                               % ('/'.join(order), rep))
            keys = []
            for f in files:
                with open(os.path.join(tmp, f), 'rb') as fh:
                    keys.append(pickle.load(fh)['key'])
            if keys[0] == keys[1]:
                raise Fail('normal and rev cache entries have the same key')
        finally:
            sc.CACHE = saved
            shutil.rmtree(tmp, ignore_errors=True)
    return ('%s %s, empty cache, both orders, 3 passes: %d loads == fresh frames of their own labels; '
            'one file per labels, distinct keys, never rewritten on a read' % (pair, tf, n_load))


# ------------------------------------------------------------ sweep.py end to end
SWEEP_KEY = ['filter', 'path', 'labels', 'tag', 'trailOn', 'trailUnit', 'trailAct', 'trailOff', 'slOn', 'slDist']
METRIC_FIELDS = [md + '_' + k for md in sc.MODES for k in sc.METRIC_COLS]


def row_metrics(row, md):
    return {k: row[md + '_' + k] for k in sc.METRIC_COLS}


def same_val(a, b):
    """Exact equality, NaN == NaN."""
    an = isinstance(a, (float, np.floating)) and np.isnan(a)
    bn = isinstance(b, (float, np.floating)) and np.isnan(b)
    return (an and bn) or (not an and not bn and a == b)


def n_rows_differ(ga, gb):
    a = ga[METRIC_FIELDS].to_numpy(np.float64)
    b = gb[METRIC_FIELDS].to_numpy(np.float64)
    return int((~((a == b) | (np.isnan(a) & np.isnan(b)))).any(axis=1).sum())


def compare_halves_rounded(pair, m, tr, start, end, mode):
    """The fair-half fields of a metrics dict vs run_tf.metrics() on the trades entered in each half."""
    bad = []
    for h, (part, s0, s1) in enumerate(split_halves(tr, start, end)):
        nm = 'h%d' % (h + 1)
        ref = ref_metrics(pair, part, s0, s1, mode)
        if int(m[nm + '_trades']) != ref['trades']:
            bad.append('%s_trades %r vs %r' % (nm, m[nm + '_trades'], ref['trades']))
        elif ref['trades'] == 0:
            if not (np.isnan(m[nm + 'r_pct']) and np.isnan(m[nm + 'r_pf'])):
                bad.append('%s empty half: %r %r' % (nm, m[nm + 'r_pct'], m[nm + 'r_pf']))
        else:
            if not feq(m[nm + 'r_pct'], ref['net_pct']):
                bad.append('%sr_pct %r vs %r' % (nm, m[nm + 'r_pct'], ref['net_pct']))
            if not feq(m[nm + 'r_pf'], ref['pf']):
                bad.append('%sr_pf %r vs %r' % (nm, m[nm + 'r_pf'], ref['pf']))
    return bad


def check_sweep_frame(sweep, df, pair, tf, G, paths=('tv', 'mag'), labels=sc.LABELS):
    """Structure of a sweep output frame: columns and dtypes, row count, unique (filter, path,
    labels, setting) keys, every (filter, path, labels) group = the settings of G in G's order with
    exactly one default row (the script's own defaults). Returns the groups, indexed like G."""
    cols = ['pair', 'tf', 'filter', 'path', 'labels'] + list(sweep.CFG_COLS) + METRIC_FIELDS
    if list(df.columns) != cols:
        raise Fail('%s %s: columns %r' % (pair, tf, list(df.columns)))
    n_exp = len(sweep.FILTERS) * len(paths) * len(labels) * len(G)
    if len(df) != n_exp:
        raise Fail('%s %s: %d rows, expected %d' % (pair, tf, len(df), n_exp))
    if not ((df['pair'] == pair).all() and (df['tf'] == tf).all()):
        raise Fail('%s %s: pair / tf columns wrong' % (pair, tf))
    dup = df.duplicated(SWEEP_KEY, keep=False)
    if dup.any():
        raise Fail('%s %s: %d rows share a key %s' % (pair, tf, int(dup.sum()), SWEEP_KEY))
    for md in sc.MODES:
        for k in sc.METRIC_COLS:
            want = np.int64 if k in sc.INT_COLS else np.float64
            if df[md + '_' + k].dtype != want:
                raise Fail('%s %s: %s_%s dtype %s' % (pair, tf, md, k, df[md + '_' + k].dtype))
    cfg_ref = pd.DataFrame(G)[list(sweep.CFG_COLS)]
    groups = {}
    for key, g in df.groupby(['filter', 'path', 'labels'], sort=False):
        g = g.reset_index(drop=True)
        try:
            pd.testing.assert_frame_equal(g[list(sweep.CFG_COLS)], cfg_ref, check_dtype=False)
        except AssertionError as e:
            raise Fail('%s %s %s: settings differ from grid(): %s' % (pair, tf, key, str(e)[:300]))
        d = g[g['tag'] == 'default']
        if len(d) != 1:
            raise Fail('%s %s %s: %d default rows' % (pair, tf, key, len(d)))
        d = d.iloc[0]
        if not (d['trailOn'] and d['trailUnit'] == 'price' and d['trailAct'] == 2.0 and d['trailOff'] == 1.0
                and not d['slOn']):
            raise Fail('%s %s %s: default row %r' % (pair, tf, key, dict(d[list(sweep.CFG_COLS)])))
        groups[key] = g
    want = {(f, p, lab) for f in sweep.FILTERS for p in paths for lab in labels}
    if set(groups) != want:
        raise Fail('%s %s: groups %r, expected %r' % (pair, tf, sorted(groups), sorted(want)))
    return groups


@contextlib.contextmanager
def patched_grid(G):
    """sc.grid() returns the settings G (sweep.run_tf_sweep calls sc.grid())."""
    saved = sc.grid
    sc.grid = lambda: [dict(g) for g in G]
    try:
        yield
    finally:
        sc.grid = saved


def run_sweep_tmp(sweep, pair, tf, workers, G=None):
    """sweep.run_tf_sweep into a temporary out dir; returns (frame returned, frame read back from
    the parquet file)."""
    tmp = tempfile.mkdtemp(prefix='_sweep_test_', dir=os.path.join(W, 'out'))
    try:
        with (patched_grid(G) if G is not None else contextlib.nullcontext()):
            df, _ = sweep.run_tf_sweep(pair, tf, ['tv', 'mag'], workers, out_dir=tmp)
        files = os.listdir(tmp)
        if files != ['sweep_%s_%s.parquet' % (pair, tf)]:
            raise Fail('%s %s: sweep wrote %r' % (pair, tf, files))
        dfp = pd.read_parquet(os.path.join(tmp, files[0]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        pd.testing.assert_frame_equal(df, dfp)
    except AssertionError as e:
        raise Fail('%s %s: parquet round trip: %s' % (pair, tf, str(e)[:300]))
    return dfp


def ts():
    """sweep.py end to end (the routing of labels / filter / path to rows, which T1-T7 do not
    see): XAU 240 full grid, both paths, both labels, 3 workers -> the parquet's structure (rows,
    unique keys, one default row per (filter, path, labels)); sampled rows of every (filter, path,
    labels) == an independent computation from FRESH xpw_signals / fgf_permissions (tv: engine.backtest
    + run_tf.metrics for tv0 / cost / stress and the fair halves; mag: _run_mag on the fresh arrays);
    rev rows != normal rows. Then a 1-worker run on a subset of the grid == the same rows of the
    3-worker run, and chart "1" (XAU, subset of the grid): mag rows == tv rows per labels, rev
    rows from the reversed sig."""
    import sweep
    G = sc.grid()
    rng = np.random.default_rng(SEED + 13)
    pair, tf = 'XAU', '240'
    start, end = run_tf.WINDOWS[pair]
    t0 = time.time()
    df = run_sweep_tmp(sweep, pair, tf, sweep.MAX_WORKERS)
    t_sweep = time.time() - t0
    groups = check_sweep_frame(sweep, df, pair, tf, G)
    perm = fgf.fgf_permissions(pair, tf, start, end, {})
    idx = [len(G) - 1, len(G) - 2] + [int(i) for i in rng.choice(len(G) - 8, 6, replace=False)]
    n_chk = 0
    for lab in sc.LABELS:
        fresh = xpw.xpw_signals(pair, tf, start, end, dict(sc.LABEL_PARAMS[lab]))
        for flt in sweep.FILTERS:
            f = flt == 'on'
            P = sc.prep(pair, tf, sc._trim_sig(fresh), perm, f)
            sub = sc.sub_bars(pair, tf, P['rows'])
            for i in idx:
                cfg = G[i]
                bad = []
                tr, _ = engine.backtest(pair, tf, fresh, perm if f else None, dict(sc.cfg_params(cfg), fgfOn=f))
                row = groups[(flt, 'tv', lab)].iloc[i]
                for md in sc.MODES:
                    m = row_metrics(row, md)
                    with ref_mode(md) as cost:
                        bad += ['tv %s: %s' % (md, x) for x in
                                compare_metrics(m, run_tf.metrics(pair, tr, start, end, cost), tr, pair, cost)]
                    bad += ['tv %s: %s' % (md, x) for x in compare_halves_rounded(pair, m, tr, start, end, md)]
                mm = sc.metrics_fast(pair, sc.run_cfg(P, cfg, 'mag', sub=sub), P['t_close'], start, end)
                row = groups[(flt, 'mag', lab)].iloc[i]
                bad += ['mag %s_%s %r vs %r' % (md, k, row[md + '_' + k], mm[md][k])
                        for md in sc.MODES for k in sc.METRIC_COLS if not same_val(row[md + '_' + k], mm[md][k])]
                if bad:
                    raise Fail('%s %s %s filter=%s setting %d %r: %s' % (pair, tf, lab, flt, i, cfg, '; '.join(bad[:5])))
                n_chk += 2
    dif = {}
    for flt in sweep.FILTERS:
        for path in ('tv', 'mag'):
            dif[(flt, path)] = n_rows_differ(groups[(flt, path, 'normal')], groups[(flt, path, 'rev')])
            if dif[(flt, path)] == 0:
                raise Fail('%s %s filter=%s path=%s: rev rows == normal rows' % (pair, tf, flt, path))
        if n_rows_differ(groups[(flt, 'tv', 'normal')], groups[(flt, 'mag', 'normal')]) == 0:
            raise Fail('%s %s filter=%s: mag rows == tv rows' % (pair, tf, flt))
    if n_rows_differ(groups[('off', 'tv', 'normal')], groups[('on', 'tv', 'normal')]) == 0:
        raise Fail('%s %s: filter on rows == filter off rows' % (pair, tf))
    print('  TS %s %s: %d rows (%.1fs, 3 workers), structure OK, %d sampled rows == fresh recomputation, '
          'rev != normal in %s rows' % (pair, tf, len(df), t_sweep, n_chk, dif), flush=True)

    # 1 worker on a subset of the grid == the same rows of the 3-worker run
    sel = sorted(set([int(i) for i in rng.choice(len(G) - 1, 40, replace=False)] + [len(G) - 1]))
    G1 = [G[i] for i in sel]
    df1 = run_sweep_tmp(sweep, pair, tf, 1, G1)
    g1 = check_sweep_frame(sweep, df1, pair, tf, G1)
    for key, g in g1.items():
        try:
            pd.testing.assert_frame_equal(g, groups[key].iloc[sel].reset_index(drop=True), check_exact=True)
        except AssertionError as e:
            raise Fail('%s %s %s: 1-worker rows != 3-worker rows: %s' % (pair, tf, key, str(e)[:300]))
    print('  TS %s %s: 1 worker, %d settings: rows identical to the 3-worker run' % (pair, tf, len(G1)), flush=True)

    # chart "1": mag rows are copies of tv rows, per labels; rev rows from the reversed sig
    pair, tf = 'XAU', '1'
    start, end = run_tf.WINDOWS[pair]
    sel = [len(G) - 1, len(G) - 2, 0, int(rng.integers(1, len(G) - 8)), int(rng.integers(1, len(G) - 8))]
    G2 = [G[i] for i in sel]
    t0 = time.time()
    df2 = run_sweep_tmp(sweep, pair, tf, sweep.MAX_WORKERS, G2)
    g2 = check_sweep_frame(sweep, df2, pair, tf, G2)
    for flt in sweep.FILTERS:
        for lab in sc.LABELS:
            a, b = g2[(flt, 'tv', lab)], g2[(flt, 'mag', lab)]
            if not (b['path'] == 'mag').all() or not a.drop(columns='path').equals(b.drop(columns='path')):
                raise Fail('%s %s filter=%s labels=%s: mag rows are not a copy of the tv rows' % (pair, tf, flt, lab))
        if n_rows_differ(g2[(flt, 'tv', 'normal')], g2[(flt, 'tv', 'rev')]) == 0:
            raise Fail('%s %s filter=%s: rev rows == normal rows' % (pair, tf, flt))
    perm = fgf.fgf_permissions(pair, tf, start, end, {})
    for lab in sc.LABELS:
        fresh = sc._trim_sig(xpw.xpw_signals(pair, tf, start, end, dict(sc.LABEL_PARAMS[lab])))
        for flt in sweep.FILTERS:
            P = sc.prep(pair, tf, fresh, perm, flt == 'on')
            for i in (0, 3):
                mm = sc.metrics_fast(pair, sc.run_cfg(P, G2[i], 'tv'), P['t_close'], start, end)
                row = g2[(flt, 'tv', lab)].iloc[i]
                bad = ['%s_%s %r vs %r' % (md, k, row[md + '_' + k], mm[md][k])
                       for md in sc.MODES for k in sc.METRIC_COLS if not same_val(row[md + '_' + k], mm[md][k])]
                if bad:
                    raise Fail('%s %s %s filter=%s %r: %s' % (pair, tf, lab, flt, G2[i], '; '.join(bad[:5])))
                n_chk += 1
    print('  TS %s %s: %d settings x 2 labels (%.1fs): mag rows == tv rows, rows == fresh recomputation'
          % (pair, tf, len(G2), time.time() - t0), flush=True)
    return ('sweep.py output: XAU 240 full grid (structure, unique keys, default row per filter / path / '
            'labels, %d rows checked against fresh inputs, 1 worker == 3 workers); XAU 1 mag == tv copy per '
            'labels' % n_chk)


def t4():
    pair, tf = 'BTC', '1'
    start, end = run_tf.WINDOWS[pair]
    t0 = time.time()
    sig, perm = sc.load_inputs(pair, tf)
    sigs = {'normal': sig, 'rev': sc.load_sig(pair, tf, 'rev')}
    P = {(lab, flt): sc.prep(pair, tf, sigs[lab], perm, flt == 'on') for lab in sc.LABELS for flt in ('off', 'on')}
    del sig, sigs, perm
    sc.warmup()
    t_in = time.time() - t0
    G = sc.grid()
    passes = []
    for lab in sc.LABELS:
        for flt in ('off', 'on'):
            Pk = P[(lab, flt)]
            t1 = time.time()
            tr_tot = 0
            t_run = 0.0
            t_met = 0.0
            for cfg in G:
                a = time.time()
                R = sc.run_cfg(Pk, cfg, 'tv')
                b = time.time()
                sc.metrics_fast(pair, R, Pk['t_close'], start, end)
                c = time.time()
                t_run += b - a
                t_met += c - b
                tr_tot += R['n']
            el = time.time() - t1
            passes.append((lab, flt, el))
            print('  BTC 1 tv labels=%-6s filter=%-3s: %d bars, %d settings in %.1fs = %.3fs per setting '
                  '(engine._run %.3fs + metrics_fast %.4fs), %.0f trades per setting avg'
                  % (lab, flt, len(Pk['c']), len(G), el, el / len(G), t_run / len(G), t_met / len(G),
                     tr_tot / len(G)), flush=True)
    print('  BTC 1 inputs (normal + rev) + prep x4 + warmup: %.1fs' % t_in, flush=True)
    # one mag setting, BTC 60, full window
    sig, perm = sc.load_inputs('BTC', '60')
    P60 = sc.prep('BTC', '60', sig, perm, False)
    t2_ = time.time()
    sub = sc.sub_bars('BTC', '60', P60['rows'])
    t_sub = time.time() - t2_
    cfg = dict(tag='grid', trailOn=True, trailUnit='percent', trailAct=0.3, trailOff=0.1, slOn=True, slDist=1.0)
    sc.run_cfg(P60, cfg, 'mag', sub=sub)              # (compiled already; warm the caches)
    t3_ = time.time()
    R = sc.run_cfg(P60, cfg, 'mag', sub=sub)
    m = sc.metrics_fast('BTC', R, P60['t_close'], start, end)
    t_mag = time.time() - t3_
    t4_ = time.time()
    Rt = sc.run_cfg(P60, cfg, 'tv')
    sc.metrics_fast('BTC', Rt, P60['t_close'], start, end)
    t_tv = time.time() - t4_
    print('  BTC 60 mag, %r: %d bars, %d sub-bars (sub_bars %.2fs): %.3fs per setting (tv %.4fs); '
          '%d trades, tv0 net %s%%' % ({k: cfg[k] for k in ('trailAct', 'trailOff', 'slDist')}, len(P60['c']),
                                       len(sub[1]), t_sub, t_mag, t_tv, R['n'], m['tv0']['net_pct']), flush=True)
    return ('BTC 1 full grid tv, single process, per pass: %s (%d settings each); BTC 60 mag: %.3f s/setting'
            % (', '.join('%s/%s %.1fs = %.3f s/setting' % (lab, flt, el, el / len(G)) for lab, flt, el in passes),
               len(G), t_mag))


TESTS = {'T1': t1, 'T2': t2, 'T3': t3, 'TM': tm, 'TX': tx, 'T5': t5, 'TC': tc, 'T6': t6, 'T7': t7, 'TS': ts,
         'T4': t4}


def main(argv):
    names = [a.upper() for a in argv] or list(TESTS)
    for nm in names:
        if nm not in TESTS:
            print('unknown test %s' % nm)
            return 2
    print('sweep_tests: xpw.py %d fgf.py %d engine.py %d (mtime ns)' % tuple(
        os.stat(os.path.join(W, f)).st_mtime_ns for f in ('xpw.py', 'fgf.py', 'engine.py')), flush=True)
    sc.warmup()
    failed = []
    for nm in names:
        t0 = time.time()
        print('%s ...' % nm, flush=True)
        try:
            msg = TESTS[nm]()
            print('%s PASS (%.1fs): %s' % (nm, time.time() - t0, msg), flush=True)
        except Exception as e:
            failed.append(nm)
            if not isinstance(e, Fail):
                traceback.print_exc()
            print('%s FAIL (%.1fs): %s' % (nm, time.time() - t0, e), flush=True)
    print('%s: %d / %d tests passed' % ('OK' if not failed else 'FAILED', len(names) - len(failed), len(names)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
