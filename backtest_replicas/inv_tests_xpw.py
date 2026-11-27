"""inv_tests_xpw.py: regression and property tests of the Update 1 option "Inverted direction:
opposite side at the same entries" (Pine xpwInv) in the XPW v2.8 trailing-TP replica
(engine.py, sweep_core.py). INV_BT_SPEC.md, task 2.

Usage: python3 -I inv_tests_xpw.py [R1 R2 R3 R4 R5] [--tfs 60,240] [--pairs BTC,XAU]
       (default: every test on every pair / timeframe). Prints PASS / FAIL per test; exits 1 on
       any failure.

R1  option OFF reproduces what the replica gave before Update 1:
    a) out/run_<PAIR>_<TF>.json (tv path): every variant (off, on, on_noblk, rev_off, rev_on)
       recomputed as run_tf.run() does, tv0 / cost metrics and the engine summary equal to the
       saved file, and the trade list equal to out/trades_<PAIR>_<TF>_<variant>.parquet, column
       for column; explicit {'xpwInv': False} / {'inv': False} give the same frame and summary.
    b) out/sweep_<PAIR>_<TF>.parquet: sampled rows (the default row + random grid rows) of every
       (filter, path, labels) group recomputed with sweep_core.prep / run_cfg / metrics_fast:
       every metric of every cost mode identical (tv and mag).
    c) the kernels of pre_inv_backup/ (the pre-change engine._run and sweep_core._run_mag) against
       the new ones with the flag off / omitted: every returned array bit-identical on random
       settings (tv and mag), engine.backtest_bars old == new (frame and summary), and the
       per-setting run time old vs new.
R2  the Pine header's INVERTED vs REVERSE statements, on full windows, tv and mag:
    a) filter off (Signal tick, no "exit only" row): inverted == "Reverse every label", trade by
       trade (dir, entry row, k, entry price, exit row, exit price, exit kind) and every metric;
    b) filter off: both on (reversed labels + inverted) == both off;
    c) through engine.backtest: the two trade lists are equal in every column but the comments,
       the comments differ only by " (inv)", the FGD sides are swapped (raw / blocked / go);
    d) Long only / Short only: inverted == reversed labels in the same one-side mode, and the
       entries taken are those of the OTHER one-side mode without the option, opposite side;
    e) where the header says they differ: filter on (opposite zones) and "exit only" rows. Every
       difference is of the stated kind: inverted, filter on == reversed labels judged in the
       OPPOSITE zones (buyOk / sellOk swapped); inverted with "exit only" rows == reversed labels
       whose "exit only" rows close the other side (exitL / exitS swapped).
R3  mirror property on single decisions: for sampled real bars (their labels, exits and
    permissions) and a prepared position, the decision with the option on from real position p ==
    the mirror of the decision with it off from -p (Long only <-> Short only swapped), and both ==
    a script step transcribed from the Pine at HEAD (ref_step).
R4  mag == tv with the option on: chart "1" with the real 1-minute sub-bars (BTC, XAU, full
    windows), one-sub-bar-per-bar tables on chart 60, and mag with real sub-bars == engine._run
    on the 1-minute series (signals on the last sub-bar); check_mag_sync / check_mag_equiv.
R5  (extra) full runs against an independent pure-Python reference: the script step transcribed
    from the Pine at HEAD (ref_step) + mag_ref.py's exit walker (longs and shorts written out,
    no kernel): engine.backtest (tv; random Trade direction, Opposite ENTER closes, Blocked entry
    closes, Max open entries, pyramiding, reversed labels, "exit only" rows, filter on / off,
    option on / off, random exits) and run_cfg mag (default inputs, independent sub-bars).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import sys
import time
import traceback

import numpy as np
import numba as nb
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import sweep_core as sc   # noqa: E402  (first: its input cache wants xpw / fgf imported by itself)
import engine             # noqa: E402
import run_tf             # noqa: E402
import xpw                # noqa: E402
import fgf                # noqa: E402
import sweep_tests as ST  # noqa: E402  (random_cfg, grid_sample, same_run, same_val, chart1_equiv)
import mag_ref as MR      # noqa: E402  (pure-Python exit walker: Trade, sub_bar_exit, my_sub_bars)

SEED = 20261124
OUT = os.path.join(W, 'out')
BACKUP = os.path.join(W, 'pre_inv_backup')
PAIRS = ['BTC', 'XAU']
TFS = list(sc.TFS)
TD = ('Both', 'Long only (buy only)', 'Short only (sell only)')
SWAP_TD = {TD[0]: TD[0], TD[1]: TD[2], TD[2]: TD[1]}
ARR = ('dir', 'erow', 'k', 'epx', 'xrow', 'xpx', 'xkind')
EXIT_ONLY = {'actDL': 'exit only', 'actDS': 'exit only', 'actEnd': 'exit only'}


class Fail(Exception):
    pass


def cells():
    return [(p, tf) for p in PAIRS for tf in TFS]


def same_metrics(ma, mb):
    return repr(ma) == repr(mb)


def first_diff(Ra, Rb):
    if Ra['n'] != Rb['n']:
        return 'trade count %d vs %d' % (Ra['n'], Rb['n'])
    for k in ARR:
        if not np.array_equal(Ra[k], Rb[k]):
            j = int(np.nonzero(Ra[k] != Rb[k])[0][0])
            return '%s differs at trade %d: %r vs %r' % (k, j, Ra[k][j], Rb[k][j])
    return ''


def swap_perm(perm):
    """The filter's two permissions exchanged (a buy is judged where a sell was, and vice versa)."""
    q = perm.copy()
    q['buyOk'] = perm['sellOk'].to_numpy()
    q['sellOk'] = perm['buyOk'].to_numpy()
    return q


def swap_exits(sig):
    """The "exit only" rows of a signal frame closing the other side."""
    q = sig.copy()
    q['exitL'] = sig['exitS'].to_numpy()
    q['exitS'] = sig['exitL'].to_numpy()
    q['exitLSrc'] = sig['exitSSrc'].to_numpy()
    q['exitSSrc'] = sig['exitLSrc'].to_numpy()
    return q


def frames_equal(a, b, skip=()):
    """Column-for-column equality of two trade frames (NaN == NaN); returns a list of problems."""
    ca = [c for c in a.columns if c not in skip]
    cb = [c for c in b.columns if c not in skip]
    if ca != cb:
        return ['columns %r vs %r' % (ca, cb)]
    if len(a) != len(b):
        return ['rows %d vs %d' % (len(a), len(b))]
    bad = []
    for c in ca:
        x = a[c].to_numpy()
        y = b[c].to_numpy()
        if x.dtype.kind == 'f' or y.dtype.kind == 'f':
            x = x.astype(np.float64)
            y = y.astype(np.float64)
            ok = (x == y) | (np.isnan(x) & np.isnan(y))
        else:
            ok = x == y
        if not np.all(ok):
            j = int(np.nonzero(~np.asarray(ok))[0][0])
            bad.append('%s differs on %d rows, first #%d: %r vs %r' % (c, int((~np.asarray(ok)).sum()), j, x[j], y[j]))
    return bad


def deep_diff(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append('%s/%s only on one side' % (path, k))
            else:
                out += deep_diff(a[k], b[k], '%s/%s' % (path, k))
        return out
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return []
    return [] if a == b else ['%s: %r vs %r' % (path, a, b)]


# =============================================================================== R1
def _json_summary(summ):
    return {k: (v if isinstance(v, (int, float, str, bool)) or v is None else str(v)) for k, v in (summ or {}).items()}


def r1a():
    n_var = n_tr = 0
    for pair, tf in cells():
        t0 = time.time()
        with open(os.path.join(OUT, 'run_%s_%s.json' % (pair, tf))) as fh:
            saved = json.load(fh)
        start, end = run_tf.WINDOWS[pair]
        if (saved['start'], saved['end']) != (start, end):
            raise Fail('%s %s: saved window %r' % (pair, tf, (saved['start'], saved['end'])))
        sig = xpw.xpw_signals(pair, tf, start, end, {})
        perm = fgf.fgf_permissions(pair, tf, start, end, {})
        sig_rev = xpw.xpw_signals(pair, tf, start, end, {'reverseAll': True})
        if int(len(sig)) != saved['bars']:
            raise Fail('%s %s: %d bars, saved %d' % (pair, tf, len(sig), saved['bars']))
        share = {'buyOk': round(float(perm['buyOk'].mean()), 3), 'sellOk': round(float(perm['sellOk'].mean()), 3)}
        if share != saved['perm_share']:
            raise Fail('%s %s: perm_share %r vs saved %r' % (pair, tf, share, saved['perm_share']))
        variants = {
            'off': (sig, None, {'fgfOn': False}),
            'on': (sig, perm, {'fgfOn': True, 'fgfBlkClose': True}),
            'on_noblk': (sig, perm, {'fgfOn': True, 'fgfBlkClose': False}),
            'rev_off': (sig_rev, None, {'fgfOn': False}),
            'rev_on': (sig_rev, perm, {'fgfOn': True, 'fgfBlkClose': True}),
        }
        if set(variants) != set(saved['variants']):
            raise Fail('%s %s: saved variants %r' % (pair, tf, sorted(saved['variants'])))
        nt = 0
        for name, (s, p, prm) in variants.items():
            tr, summ = engine.backtest(pair, tf, s, p, prm)          # no xpwInv key: the default
            got = {'tv0': run_tf.metrics(pair, tr, start, end, False),
                   'cost': run_tf.metrics(pair, tr, start, end, True),
                   'summary': _json_summary(summ)}
            got = json.loads(json.dumps(got, default=str))
            bad = deep_diff(got, saved['variants'][name])
            if bad:
                raise Fail('%s %s %s: json differs: %s' % (pair, tf, name, '; '.join(bad[:5])))
            old = pd.read_parquet(os.path.join(OUT, 'trades_%s_%s_%s.parquet' % (pair, tf, name)))
            bad = frames_equal(tr, old)
            if bad:
                raise Fail('%s %s %s: trades differ from the saved parquet: %s' % (pair, tf, name, '; '.join(bad[:5])))
            if name in ('on', 'rev_off'):
                for extra in ({'xpwInv': False}, {'inv': False}):
                    tr2, summ2 = engine.backtest(pair, tf, s, p, dict(prm, **extra))
                    if frames_equal(tr2, tr) or summ2 != summ:
                        raise Fail('%s %s %s: explicit %r differs from the default' % (pair, tf, name, extra))
            n_var += 1
            nt += len(tr)
        n_tr += nt
        print('  R1a %s %-3s %7d bars: 5 variants == out/run json (tv0, cost, summary) and == saved trade lists '
              '(%d trades) (%.1fs)' % (pair, tf, len(sig), nt, time.time() - t0), flush=True)
    return n_var, n_tr


def r1b(k_rows=6):
    rng = np.random.default_rng(SEED + 1)
    G = sc.grid()
    cfg_cols = ('tag', 'trailOn', 'trailUnit', 'trailAct', 'trailOff', 'slOn', 'slDist')
    n_rows = n_tv = n_mag = 0
    for pair, tf in cells():
        t0 = time.time()
        start, end = run_tf.WINDOWS[pair]
        df = pd.read_parquet(os.path.join(OUT, 'sweep_%s_%s.parquet' % (pair, tf)))
        sig, perm = sc.load_inputs(pair, tf, verbose=False)
        sigs = {'normal': sig, 'rev': sc.load_sig(pair, tf, 'rev', verbose=False)}
        P = {(lab, flt): sc.prep(pair, tf, sigs[lab], perm, flt == 'on') for lab in sc.LABELS for flt in ('off', 'on')}
        del sig, sigs
        if any(Pk['inv'] for Pk in P.values()):
            raise Fail('prep default: P["inv"] is not False')
        sub = sc.sub_bars(pair, tf, P[('normal', 'off')]['rows'])
        groups = {key: g.reset_index(drop=True) for key, g in df.groupby(['filter', 'path', 'labels'], sort=False)}
        if len(groups) != 8:
            raise Fail('%s %s: %d groups in the sweep file' % (pair, tf, len(groups)))
        nr = 0
        for (flt, path, lab), g in groups.items():
            if len(g) != len(G):
                raise Fail('%s %s %s: %d rows' % (pair, tf, (flt, path, lab), len(g)))
            idx = [len(G) - 1] + [int(i) for i in rng.choice(len(G) - 1, k_rows - 1, replace=False)]
            Pk = P[(lab, flt)]
            for i in idx:
                row = g.iloc[i]
                cfg = G[i]
                for c in cfg_cols:
                    if not ST.same_val(row[c], cfg[c]):
                        raise Fail('%s %s %s row %d: setting column %s %r vs grid %r' % (pair, tf, (flt, path, lab), i, c, row[c], cfg[c]))
                R = sc.run_cfg(Pk, cfg, path, sub=sub)               # flag from P (default False)
                m = sc.metrics_fast(pair, R, Pk['t_close'], start, end)
                bad = ['%s_%s %r vs saved %r' % (md, k, m[md][k], row[md + '_' + k])
                       for md in sc.MODES for k in sc.METRIC_COLS if not ST.same_val(row[md + '_' + k], m[md][k])]
                if bad:
                    raise Fail('%s %s %s row %d %r: %s' % (pair, tf, (flt, path, lab), i, cfg, '; '.join(bad[:5])))
                if i == len(G) - 1:
                    R2 = sc.run_cfg(Pk, cfg, path, sub=sub, inv=False)
                    if not ST.same_run(R, R2):
                        raise Fail('%s %s: run_cfg(inv=False) != run_cfg()' % (pair, tf))
                nr += 1
                n_tv += path == 'tv'
                n_mag += path == 'mag'
        n_rows += nr
        print('  R1b %s %-3s: %d sampled rows of out/sweep parquet (8 groups x %d) recomputed: every metric identical '
              '(%.1fs)' % (pair, tf, nr, k_rows, time.time() - t0), flush=True)
    return n_rows, n_tv, n_mag


def load_pre():
    """The pre-change kernels: pre_inv_backup/engine.py as a module, and _run_mag compiled from
    the kernel section of pre_inv_backup/sweep_core.py against that old engine's _walk."""
    pe = os.path.join(BACKUP, 'engine.py')
    ps = os.path.join(BACKUP, 'sweep_core.py')
    for p in (pe, ps):
        if 'xpwInv' in open(p).read():
            raise Fail('%s is not the pre-change module (it mentions xpwInv)' % p)
    spec = importlib.util.spec_from_file_location('engine_pre_inv', pe)
    eng0 = importlib.util.module_from_spec(spec)
    sys.modules['engine_pre_inv'] = eng0
    spec.loader.exec_module(eng0)
    src = open(ps).read()
    a = src.index('@nb.njit\ndef _to_ticks')
    b = src.index('def _norm_tail')
    ns = {'nb': nb, 'np': np, '_walk': eng0._walk, 'K_TRAIL': eng0.K_TRAIL, 'K_SL': eng0.K_SL,
          'K_CLOSEALL': eng0.K_CLOSEALL, 'K_REVERSE': eng0.K_REVERSE, 'K_END': eng0.K_END}
    exec(compile(src[a:b], ps, 'exec'), ns)
    return eng0, ns['_run_mag']


def _same_tuple(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if isinstance(x, np.ndarray):
            if x.dtype != y.dtype or not np.array_equal(x, y, equal_nan=x.dtype.kind == 'f'):
                return False
        elif x != y:
            return False
    return True


def _kargs(P, cfg):
    trailOn, slOn, unit, act, off, sld = sc._cfg_tuple(cfg)
    head = (P['o'], P['h'], P['l'], P['c'])
    tail = (P['goL'], P['goS'], P['nL'], P['nS'], P['cL'], P['cS'], P['maxOpen'], P['pyr'], trailOn, slOn, unit,
            act, off, sld, P['mt'], P['tol'], P['cap'], P['ocap'])
    return head, tail


def r1c():
    eng0, mag0 = load_pre()
    sha = {f: hashlib.sha256(open(os.path.join(BACKUP, f), 'rb').read()).hexdigest()[:16] for f in ('engine.py', 'sweep_core.py')}
    print('  R1c pre-change modules: pre_inv_backup/engine.py sha256 %s.., sweep_core.py %s..' % (sha['engine.py'], sha['sweep_core.py']), flush=True)
    rng = np.random.default_rng(SEED + 3)
    n_tv = n_mag = n_bt = 0
    todo = [c for c in (('BTC', '60'), ('BTC', '5'), ('XAU', '240'), ('XAU', '15'), ('BTC', '240'), ('XAU', '60'))
            if c[0] in PAIRS and c[1] in TFS] or cells()[:2]
    for pair, tf in todo:
        t0 = time.time()
        sig, perm = sc.load_inputs(pair, tf, verbose=False)
        sigs = {'normal': sig, 'rev': sc.load_sig(pair, tf, 'rev', verbose=False)}
        P = {(lab, f): sc.prep(pair, tf, sigs[lab], perm, f) for lab in sc.LABELS for f in (False, True)}
        sub = sc.sub_bars(pair, tf, P[('normal', False)]['rows'])
        ref = float(np.median(P[('normal', False)]['c']))
        cfgs = ST.grid_sample(rng, 6) + [ST.random_cfg(rng, ref) for _ in range(6)]
        for cfg in cfgs:
            for key, Pk in P.items():
                head, tail = _kargs(Pk, cfg)
                old = eng0._run(*head, *tail)
                if not (_same_tuple(old, engine._run(*head, *tail, False)) and _same_tuple(old, engine._run(*head, *tail))):
                    raise Fail('%s %s %s %r: new engine._run (flag off / omitted) != pre-change kernel' % (pair, tf, key, cfg))
                n_tv += 1
                oldm = mag0(*head, *sub, *tail)
                if not (_same_tuple(oldm, sc._run_mag(*head, *sub, *tail, False)) and _same_tuple(oldm, sc._run_mag(*head, *sub, *tail))):
                    raise Fail('%s %s %s %r: new _run_mag (flag off / omitted) != pre-change kernel' % (pair, tf, key, cfg))
                n_mag += 1
        # the drivers: old backtest_bars == new backtest_bars (frame and summary), assorted inputs
        allb = engine.load_bars(pair, tf)
        rows = np.asarray(sigs['normal'].index, dtype=np.int64)
        bars = allb.iloc[rows].set_axis(sigs['normal'].index)
        for lab in sc.LABELS:
            for prm in ({'fgfOn': False}, {'fgfOn': True}, {'fgfOn': True, 'fgfBlkClose': False},
                        {'fgfOn': True, 'tradeDir': TD[1]}, {'fgfOn': False, 'tradeDir': TD[2], 'oppCloses': False},
                        {'fgfOn': True, 'maxOpen': 1, 'slOn': True, 'trailUnit': 'percent', 'trailAct': 0.1, 'trailOff': 0.05, 'slDist': 0.2}):
                a, sa = eng0.backtest_bars(bars, sigs[lab], perm, prm)
                b, sb = engine.backtest_bars(bars, sigs[lab], perm, prm)
                bad = frames_equal(a, b)
                if bad or sa != sb:
                    raise Fail('%s %s %s %r: new backtest_bars != pre-change: %s' % (pair, tf, lab, prm, '; '.join(bad[:3]) or 'summary'))
                n_bt += 1
        print('  R1c %s %-3s: %d settings x 4 (labels, filter): new kernels (flag off and omitted) == pre-change kernels, '
              'tv and mag; backtest_bars old == new on 12 inputs (%.1fs)' % (pair, tf, len(cfgs), time.time() - t0), flush=True)
    # speed: min of repeats, old vs new, the same arrays
    if 'BTC' in PAIRS:
        tf = '1' if '1' in TFS else TFS[0]
        sig, perm = sc.load_inputs('BTC', tf, verbose=False)
        Pk = sc.prep('BTC', tf, sig, perm, False)
        del sig
        G = sc.grid()
        for name, cfg in (('default', G[-1]), ('grid 0.3/0.1 sl 1', dict(tag='grid', trailOn=True, trailUnit='percent', trailAct=0.3, trailOff=0.1, slOn=True, slDist=1.0))):
            head, tail = _kargs(Pk, cfg)
            best = {}
            for rep in range(5):
                for nm, fn in (('old', lambda: eng0._run(*head, *tail)), ('new', lambda: engine._run(*head, *tail, False)),
                               ('inv', lambda: engine._run(*head, *tail, True))):
                    t1 = time.perf_counter()
                    fn()
                    best[nm] = min(best.get(nm, 1e9), time.perf_counter() - t1)
            print('  R1c speed BTC %s tv %-18s %d bars: pre-change %.4fs, new flag off %.4fs (x%.2f), new inverted %.4fs'
                  % (tf, name, len(Pk['c']), best['old'], best['new'], best['new'] / best['old'], best['inv']), flush=True)
            if best['new'] > 1.5 * best['old'] + 0.005:
                raise Fail('engine._run is slower than before: %.4fs vs %.4fs' % (best['new'], best['old']))
        tf = '60' if '60' in TFS else TFS[-1]
        sig, perm = sc.load_inputs('BTC', tf, verbose=False)
        Pk = sc.prep('BTC', tf, sig, perm, False)
        sub = sc.sub_bars('BTC', tf, Pk['rows'])
        head, tail = _kargs(Pk, G[-1])
        best = {}
        for rep in range(5):
            for nm, fn in (('old', lambda: mag0(*head, *sub, *tail)), ('new', lambda: sc._run_mag(*head, *sub, *tail, False)),
                           ('inv', lambda: sc._run_mag(*head, *sub, *tail, True))):
                t1 = time.perf_counter()
                fn()
                best[nm] = min(best.get(nm, 1e9), time.perf_counter() - t1)
        print('  R1c speed BTC %s mag default: %d bars, %d sub-bars: pre-change %.4fs, new flag off %.4fs (x%.2f), new inverted %.4fs'
              % (tf, len(Pk['c']), len(sub[1]), best['old'], best['new'], best['new'] / best['old'], best['inv']), flush=True)
        if best['new'] > 1.5 * best['old'] + 0.005:
            raise Fail('_run_mag is slower than before: %.4fs vs %.4fs' % (best['new'], best['old']))
    return n_tv, n_mag, n_bt


def r1():
    # the parameter itself
    if engine.DEFAULTS.get('xpwInv') is not False:
        raise Fail('engine.DEFAULTS["xpwInv"] is not False')
    if engine._params({})['xpwInv'] is not False or engine._params({'inv': True})['xpwInv'] is not True \
            or engine._params({'xpwInv': 1})['xpwInv'] is not True:
        raise Fail('engine._params: xpwInv / inv not read')
    try:
        engine._params({'inv': True, 'xpwInv': False})
        raise Fail('engine._params accepted inv and xpwInv that disagree')
    except ValueError:
        pass
    n_var, n_tr = r1a()
    n_rows, n_tv, n_mag = r1b()
    k_tv, k_mag, k_bt = r1c()
    return ('option off: %d run-json variants (%d trades) == saved json and saved trade lists; %d sweep rows (%d tv, %d mag) '
            '== saved parquet; new kernels == pre-change kernels on %d tv + %d mag runs, backtest_bars on %d'
            % (n_var, n_tr, n_rows, n_tv, n_mag, k_tv, k_mag, k_bt))


# =============================================================================== R2
def _inv_strip(s):
    return s.replace(' (inv)', '')


def _bt_pair_check(what, a, sa, b, sb, sides_swapped=True):
    """a = an inverted run, b = its reversed-label equivalent (option off): equal in every column
    but the comments (and sig_dir); comments equal once " (inv)" is removed; FGD sides swapped."""
    if 'sig_dir' not in a.columns or not np.array_equal(a['sig_dir'].to_numpy(), -a['dir'].to_numpy()):
        raise Fail('%s: sig_dir missing or not -dir on the inverted run' % what)
    bad = frames_equal(a, b, skip=('entry_comment', 'exit_comment', 'sig_dir'))
    if bad:
        raise Fail('%s: %s' % (what, '; '.join(bad[:4])))
    for col in ('entry_comment', 'exit_comment'):
        x = np.array([_inv_strip(s) for s in a[col]], dtype=object)
        y = b[col].to_numpy(object)
        if not np.array_equal(x, y):
            j = int(np.nonzero(x != y)[0][0])
            raise Fail('%s: %s differs beyond " (inv)" at trade %d: %r vs %r' % (what, col, j, a[col].iloc[j], y[j]))
    if len(a) and not all(' (inv) | ' in s for s in a['entry_comment']):
        raise Fail('%s: an inverted entry comment without " (inv)"' % what)
    pairs = [('raw_long', 'raw_short'), ('blocked_long', 'blocked_short'), ('go_long_bars', 'go_short_bars'),
             ('sig_bars_long', 'sig_bars_short')]
    for x, y in pairs:
        if sides_swapped and not (sa[x] == sb[y] and sa[y] == sb[x]):
            raise Fail('%s: FGD sides %s / %s not swapped: %r %r vs %r %r' % (what, x, y, sa[x], sa[y], sb[x], sb[y]))
    for k in ('entries', 'long_entries', 'short_entries', 'entries_skipped_room', 'entries_ignored_pyramiding', 'entry_bars',
              'close_all_bars', 'exits_trail', 'exits_sl', 'exits_close_all', 'exits_reverse', 'exits_end', 'gross_pl',
              'gross_pl_long', 'gross_pl_short', 'wins', 'losses', 'max_open'):
        if sa[k] != sb[k]:
            raise Fail('%s: summary %s %r vs %r' % (what, k, sa[k], sb[k]))
    if sa.get('xpwInv') is not True or 'xpwInv' in sb:
        raise Fail('%s: summary xpwInv flag' % what)


def r2():
    rng = np.random.default_rng(SEED + 2)
    cnt = dict(a=0, b=0, e=0, tr=0, on_dif=0, norm_dif=0, on_runs=0)
    for pair, tf in cells():
        t0 = time.time()
        start, end = run_tf.WINDOWS[pair]
        sig, perm = sc.load_inputs(pair, tf, verbose=False)
        sr = sc.load_sig(pair, tf, 'rev', verbose=False)
        Pn = {f: sc.prep(pair, tf, sig, perm, f) for f in (False, True)}                # normal labels
        Pni = {f: sc.prep(pair, tf, sig, perm, f, inv=True) for f in (False, True)}     # normal labels, inverted
        Pr = {f: sc.prep(pair, tf, sr, perm, f) for f in (False, True)}                 # reversed labels
        Pri = sc.prep(pair, tf, sr, perm, False, xpwInv=True)                           # both on, filter off
        Prs = sc.prep(pair, tf, sr, swap_perm(perm), True)                              # reversed labels, zones swapped
        del sig, sr
        for f in (False, True):                 # tradeDir Both: the gate does not depend on the option
            if any(not np.array_equal(Pn[f][k], Pni[f][k]) for k in ('goL', 'goS', 'nL', 'nS', 'cL', 'cS')) or not Pni[f]['inv']:
                raise Fail('%s %s: prep(inv=True) changed the signal arrays or did not set P["inv"]' % (pair, tf))
        paths = ('tv', 'mag') if tf != '1' else ('tv',)
        sub = sc.sub_bars(pair, tf, Pn[False]['rows']) if tf != '1' else None
        ref = float(np.median(Pn[False]['c']))
        cfgs = ST.grid_sample(rng, 4) + [ST.random_cfg(rng, ref) for _ in range(4)]
        tc = Pn[False]['t_close']
        nt = 0
        loc = dict(on_dif=0, norm_dif=0)
        for cfg in cfgs:
            for path in paths:
                def run(P):
                    R = sc.run_cfg(P, cfg, path, sub=sub)
                    return R, sc.metrics_fast(pair, R, tc, start, end)
                A, mA = run(Pni[False])
                B, mB = run(Pr[False])
                d = first_diff(A, B)
                if d or not same_metrics(mA, mB):
                    raise Fail('%s %s %s %r filter off: inverted != reversed labels: %s' % (pair, tf, path, cfg, d or 'metrics'))
                cnt['a'] += 1
                C, mC = run(Pri)
                D, mD = run(Pn[False])
                d = first_diff(C, D)
                if d or not same_metrics(mC, mD):
                    raise Fail('%s %s %s %r filter off: both on != both off: %s' % (pair, tf, path, cfg, d or 'metrics'))
                cnt['b'] += 1
                E, mE = run(Pni[True])
                F, mF = run(Prs)
                d = first_diff(E, F)
                if d or not same_metrics(mE, mF):
                    raise Fail('%s %s %s %r filter on: inverted != reversed labels in the opposite zones: %s'
                               % (pair, tf, path, cfg, d or 'metrics'))
                cnt['e'] += 1
                H, _ = run(Pr[True])
                loc['on_dif'] += int(not ST.same_run(E, H))
                loc['norm_dif'] += int(not ST.same_run(A, D))
                cnt['on_runs'] += 1
                nt += A['n'] + C['n'] + E['n']
        cnt['tr'] += nt
        cnt['on_dif'] += loc['on_dif']
        cnt['norm_dif'] += loc['norm_dif']
        print('  R2 %s %-3s %s: %d settings: inv == rev (filter off); both on == both off; filter on: inv == rev with the '
              'zones swapped; %d trades (inv != rev with the filter on in %d of %d runs, inv != normal in %d) (%.1fs)'
              % (pair, tf, '+'.join(paths), len(cfgs), nt, loc['on_dif'], len(cfgs) * len(paths), loc['norm_dif'],
                 time.time() - t0), flush=True)
    if cnt['on_dif'] == 0 or cnt['norm_dif'] == 0:
        raise Fail('inverted never differed from reversed labels with the filter on, or from the normal run: no power')

    # ---- through engine.backtest: comments, FGD sides, one-side modes, "exit only" rows
    n_bt = n_one = n_exit = 0
    exit_dif = 0
    todo = [c for c in (('BTC', '60'), ('XAU', '240'), ('BTC', '15'), ('XAU', '30')) if c[0] in PAIRS and c[1] in TFS] or cells()[:2]
    for pair, tf in todo:
        t0 = time.time()
        start, end = run_tf.WINDOWS[pair]
        sig, perm = sc.load_inputs(pair, tf, verbose=False)
        sr = sc.load_sig(pair, tf, 'rev', verbose=False)
        psw = swap_perm(perm)
        ref = float(np.median(engine.load_bars(pair, tf)['close'].to_numpy()[np.asarray(sig.index)]))
        exits = [{}] + [sc.cfg_params(ST.random_cfg(rng, ref)) for _ in range(2)]
        for ex in exits:
            # c) filter off, Both
            a, sa = engine.backtest(pair, tf, sig, None, dict(ex, fgfOn=False, xpwInv=True))
            b, sb = engine.backtest(pair, tf, sr, None, dict(ex, fgfOn=False))
            _bt_pair_check('%s %s filter off, inv vs rev' % (pair, tf), a, sa, b, sb)
            # both on == both off (the comments keep " (inv)", the FGD sides are those of the reversed labels)
            a2, sa2 = engine.backtest(pair, tf, sr, None, dict(ex, fgfOn=False, inv=True))
            b2, sb2 = engine.backtest(pair, tf, sig, None, dict(ex, fgfOn=False))
            _bt_pair_check('%s %s filter off, both on vs both off' % (pair, tf), a2, sa2, b2, sb2)
            n_bt += 2
            # e) filter on: inverted == reversed labels judged in the opposite zones (blocked close on / off)
            for bc in (True, False):
                a, sa = engine.backtest(pair, tf, sig, perm, dict(ex, fgfOn=True, fgfBlkClose=bc, xpwInv=True))
                b, sb = engine.backtest(pair, tf, sr, psw, dict(ex, fgfOn=True, fgfBlkClose=bc))
                _bt_pair_check('%s %s filter on (blkClose %s), inv vs rev + swapped zones' % (pair, tf, bc), a, sa, b, sb)
                n_bt += 1
            # d) one-side modes
            for td in TD[1:]:
                for oc in (True, False):
                    for flt in (False, True):
                        prm = dict(ex, fgfOn=flt, tradeDir=td, oppCloses=oc)
                        a, sa = engine.backtest(pair, tf, sig, perm if flt else None, dict(prm, xpwInv=True))
                        b, sb = engine.backtest(pair, tf, sr, psw if flt else None, prm)
                        _bt_pair_check('%s %s %s oppCloses %s filter %s, inv vs rev' % (pair, tf, td, oc, flt), a, sa, b, sb)
                        only = 1 if td == TD[1] else -1
                        if len(a) and not (a['dir'] == only).all():
                            raise Fail('%s %s inverted %s: a trade on the other REAL side' % (pair, tf, td))
                        # "the entries taken are those of the other one-side mode without the option, opposite side"
                        o, so = engine.backtest(pair, tf, sig, perm if flt else None, dict(prm, tradeDir=SWAP_TD[td]))
                        if sa['entries_skipped_room'] == 0 and so['entries_skipped_room'] == 0:
                            if not (np.array_equal(a['entry_row'].to_numpy(), o['entry_row'].to_numpy())
                                    and np.array_equal(a['dir'].to_numpy(), -o['dir'].to_numpy())
                                    and np.array_equal(a['src'].to_numpy(object), o['src'].to_numpy(object))
                                    and np.array_equal(a['entry_px'].to_numpy(), o['entry_px'].to_numpy())):
                                raise Fail('%s %s inverted %s: entries != those of %s without the option, mirrored'
                                           % (pair, tf, td, SWAP_TD[td]))
                        n_one += 1
        # e) "exit only" rows: inverted closes the mirrored side
        sx = xpw.xpw_signals(pair, tf, start, end, dict(EXIT_ONLY))
        sxr = xpw.xpw_signals(pair, tf, start, end, dict(EXIT_ONLY, reverseAll=True))
        if not (sx['exitL'].any() and sx['exitS'].any()):
            raise Fail('%s %s: the "exit only" frame has no exits' % (pair, tf))
        if not (np.array_equal(sx['exitL'].to_numpy(), sxr['exitL'].to_numpy()) and np.array_equal(sx['exitS'].to_numpy(), sxr['exitS'].to_numpy())):
            raise Fail('%s %s: reverseAll changed the "exit only" rows' % (pair, tf))
        sxm = swap_exits(sxr)
        for ex in exits:
            for flt in (False, True):
                for td in TD:
                    prm = dict(ex, fgfOn=flt, tradeDir=td)
                    a, sa = engine.backtest(pair, tf, sx, perm if flt else None, dict(prm, xpwInv=True))
                    b, sb = engine.backtest(pair, tf, sxm, psw if flt else None, prm)
                    _bt_pair_check('%s %s exit-only rows, %s, filter %s: inv vs rev with exits mirrored' % (pair, tf, td, flt), a, sa, b, sb)
                    n_exit += 1
                    if td == 'Both' and not flt:
                        c, _ = engine.backtest(pair, tf, sxr, None, prm)     # plain "Reverse every label"
                        exit_dif += int(bool(frames_equal(a, c, skip=('entry_comment', 'exit_comment', 'sig_dir'))))
        print('  R2 %s %-3s engine.backtest, %d exits: comments differ only by " (inv)", FGD sides swapped; one-side modes; '
              '"exit only" rows (%d exitL, %d exitS bars) close the mirrored side (%.1fs)'
              % (pair, tf, len(exits), int(sx['exitL'].sum()), int(sx['exitS'].sum()), time.time() - t0), flush=True)
    if exit_dif == 0:
        raise Fail('with "exit only" rows the inverted run never differed from plain "Reverse every label": no power')
    return ('filter off: inv == rev on %d runs, both on == both off on %d; filter on: inv == rev with the zones swapped on %d '
            '(%d trades in all; plain rev differs with the filter on in %d of %d); engine.backtest: %d pairs of lists (comments, FGD '
            'sides), %d one-side-mode cases, %d "exit only" cases (plain rev differs in %d)'
            % (cnt['a'], cnt['b'], cnt['e'], cnt['tr'], cnt['on_dif'], cnt['on_runs'], n_bt, n_one, n_exit, exit_dif))


# =============================================================== the Pine at HEAD, script step
REF_DEFAULTS = dict(tradeDir='Both', oppCloses=True, fgfOn=True, fgfBlkClose=True, maxOpen=20, pyramiding=100,
                    trailOn=True, trailUnit='price', trailAct=2.0, trailOff=1.0, slOn=False, slDist=3.0, xpwInv=False)


def ref_step(position_size, opentrades, longSrc, shortSrc, exitL, exitS, exitLSrc, exitSSrc, fgfBuyOk, fgfSellOk,
             p, bar_index):
    """One run of the script at a bar close ("Signal tick"), transcribed from the STRATEGY section
    of xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine at HEAD (Update 1), names as in the Pine.
    position_size: sign of strategy.position_size (the REAL position). Returns (orders, info):
    orders in placement order, ('close_all', comment) or ('entry', id, +1 | -1 real side, comment,
    src, k)."""
    xpwInv = bool(p['xpwInv'])
    tradeDir = p['tradeDir']
    oppCloses = bool(p['oppCloses'])
    fgfBlkClose = bool(p['fgfBlkClose'])
    maxOpen = int(p['maxOpen'])
    nLong = len(longSrc)
    nShort = len(shortSrc)
    if nLong > 0 and nShort > 0:
        nLong = 0
        nShort = 0
    allowLong = (tradeDir != "Long only (buy only)") if xpwInv else (tradeDir != "Short only (sell only)")
    allowShort = (tradeDir != "Short only (sell only)") if xpwInv else (tradeDir != "Long only (buy only)")
    sigLong = nLong > 0 and allowLong          # doneL != bar_index: one run per bar on history
    sigShort = nShort > 0 and allowShort
    fgfBlkL = sigLong and not fgfBuyOk         # Signal tick: fgfLimOkL = fgfLimOkS = true
    fgfBlkS = sigShort and not fgfSellOk
    goLong = sigLong and not fgfBlkL
    goShort = sigShort and not fgfBlkS
    oppL = nShort > 0 and ((oppCloses and not allowShort) or (fgfBlkClose and fgfBlkS))
    oppS = nLong > 0 and ((oppCloses and not allowLong) or (fgfBlkClose and fgfBlkL))
    xpwPosN = -position_size if xpwInv else position_size
    closeL = xpwPosN > 0 and not goLong and (not goShort and (exitL or oppL))      # useLimit false
    closeS = xpwPosN < 0 and not goShort and (not goLong and (exitS or oppS))
    firstLong = longSrc[0] if len(longSrc) > 0 else ""
    firstShort = shortSrc[0] if len(shortSrc) > 0 else ""
    orders = []
    if closeL:
        orders.append(('close_all', ("exit | " + exitLSrc) if exitL else
                       ((("filter blocked LONG (inv), close | " if xpwInv else "filter blocked SHORT, close | ") + firstShort)
                        if fgfBlkS else "opp ENTER | " + firstShort)))
    if closeS:
        orders.append(('close_all', ("exit | " + exitSSrc) if exitS else
                       ((("filter blocked SHORT (inv), close | " if xpwInv else "filter blocked LONG, close | ") + firstLong)
                        if fgfBlkL else "opp ENTER | " + firstLong)))

    def place(id_, isLong, src, k):
        realLong = (not isLong) if xpwInv else isLong
        cmt = ("ENTER LONG" if realLong else "ENTER SHORT") + (" (inv)" if xpwInv else "") + " | " + src
        orders.append(('entry', id_, 1 if realLong else -1, cmt, src, k + 1))

    room = maxOpen - opentrades                # pendId is empty in Signal tick mode
    skipped = 0
    if goLong:
        for k in range(nLong):
            if room > 0 or xpwPosN < 0:
                place(("S" if xpwInv else "L") + str(bar_index) + "-" + str(k + 1), True, longSrc[k], k)
                room -= 1
            else:
                skipped += 1
    if goShort:
        for k in range(nShort):
            if room > 0 or xpwPosN > 0:
                place(("L" if xpwInv else "S") + str(bar_index) + "-" + str(k + 1), False, shortSrc[k], k)
                room -= 1
            else:
                skipped += 1
    info = dict(sigLong=sigLong, sigShort=sigShort, fgfBlkL=fgfBlkL, fgfBlkS=fgfBlkS, goLong=goLong, goShort=goShort,
                closeL=closeL, closeS=closeS, skipped=skipped)
    return orders, info


class RT:
    """A reference trade: mag_ref.Trade (levels, trailing state; real side) + ids and comments."""
    __slots__ = ('tr', 'id', 'ecmt', 'src', 'xcmt')

    def __init__(self, tr, id_, ecmt, src):
        self.tr = tr
        self.id = id_
        self.ecmt = ecmt
        self.src = src
        self.xcmt = ''


def _lists(sig, col):
    return [list(x) if x is not None and not (isinstance(x, float) and np.isnan(x)) else [] for x in sig[col]]


def ref_run(bars, sig, perm, params, sub=None):
    """The whole strategy in plain Python: SPEC.md broker rules 1-10 with ref_step as the script
    and mag_ref's exit walker (sub = None: the chart bar itself is the one sub-bar, the 'tv' path;
    else mag_ref.my_sub_bars(...), the 'mag' path). Returns (trades list of RT, counters)."""
    p = dict(REF_DEFAULTS)
    p.update(params or {})
    if 'inv' in p:
        p['xpwInv'] = p.pop('inv')
    cfg = {k: p[k] for k in ('trailOn', 'trailUnit', 'trailAct', 'trailOff', 'slOn', 'slDist')}
    o, h, l, c = (bars[k].to_numpy(np.float64) for k in ('open', 'high', 'low', 'close'))
    rows = [int(x) for x in sig.index]
    n = len(rows)
    longSrc, shortSrc = _lists(sig, 'longSrc'), _lists(sig, 'shortSrc')
    exitL, exitS = sig['exitL'].to_numpy(bool), sig['exitS'].to_numpy(bool)
    exitLSrc, exitSSrc = sig['exitLSrc'].tolist(), sig['exitSSrc'].tolist()
    filt = bool(p['fgfOn']) and perm is not None
    buyOk = perm['buyOk'].to_numpy(bool) if filt else None
    sellOk = perm['sellOk'].to_numpy(bool) if filt else None
    pyr = int(p['pyramiding'])
    out, open_ = [], []
    cnt = dict(skipped=0, pyr=0, blkL=0, blkS=0, rawL=0, rawS=0, close_bars=0)
    for i in range(n):
        # 1. pending exit orders of the open trades
        if open_:
            sbs = sub[i] if sub is not None else [(float(o[i]), float(h[i]), float(l[i]), float(c[i]), 0)]
            for (so, sh, sl_, sc_, _t) in sbs:
                still = []
                for t in open_:
                    r = MR.sub_bar_exit(t.tr, so, sh, sl_, sc_)
                    if r is None:
                        still.append(t)
                    else:
                        t.tr.xkind, t.tr.xpx, t.tr.xrow = r[0], r[1], i
                        t.xcmt = ('trail TP | ' if r[0] == MR.TRAIL else 'SL | ') + t.src
                open_ = still
                if not open_:
                    break
        # 2. the script at the close
        pos = 0 if not open_ else open_[0].tr.dir
        orders, info = ref_step(pos, len(open_), longSrc[i], shortSrc[i], bool(exitL[i]), bool(exitS[i]),
                                exitLSrc[i], exitSSrc[i], bool(buyOk[i]) if filt else True,
                                bool(sellOk[i]) if filt else True, p, rows[i])
        cnt['skipped'] += info['skipped']
        cnt['blkL'] += int(info['fgfBlkL'])
        cnt['blkS'] += int(info['fgfBlkS'])
        cnt['rawL'] += int(info['sigLong'])
        cnt['rawS'] += int(info['sigShort'])
        cnt['close_bars'] += int(info['closeL'] or info['closeS'])
        for od in orders:
            if od[0] == 'close_all':
                for t in open_:
                    t.tr.xkind, t.tr.xpx, t.tr.xrow = MR.CLOSE_ALL, float(c[i]), i
                    t.xcmt = od[1]
                open_ = []
            else:
                _, id_, d, cmt, src, k = od
                cur = 0 if not open_ else open_[0].tr.dir
                if cur == -d:                               # strategy.entry against the position: reversal
                    for t in open_:
                        t.tr.xkind, t.tr.xpx, t.tr.xrow = MR.REVERSE, float(c[i]), i
                        t.xcmt = cmt
                    open_ = []
                if open_ and len(open_) >= pyr:
                    cnt['pyr'] += 1                         # pyramiding limit: the order is ignored
                else:
                    t = RT(MR.Trade(d, k, i, float(c[i]), cfg), id_, cmt, src)
                    out.append(t)
                    open_.append(t)
    # 3. the window end
    for t in open_:
        t.tr.xkind, t.tr.xpx, t.tr.xrow = MR.END, float(c[n - 1]), n - 1
        t.xcmt = 'end'
    return out, cnt


def ref_frame(ref, rows):
    rows = np.asarray(rows, dtype=np.int64)
    er = np.array([t.tr.erow for t in ref], np.int64)
    xr = np.array([t.tr.xrow for t in ref], np.int64)
    nanv = lambda v: np.nan if v is None else v
    return pd.DataFrame({
        'id': [t.id for t in ref],
        'dir': np.array([t.tr.dir for t in ref], np.int64),
        'src': [t.src for t in ref],
        'entry_row': rows[er] if len(ref) else np.zeros(0, np.int64),
        'entry_px': np.array([t.tr.epx for t in ref], np.float64),
        'exit_row': rows[xr] if len(ref) else np.zeros(0, np.int64),
        'exit_px': np.array([t.tr.xpx for t in ref], np.float64),
        'exit_kind': [MR.KNAME[t.tr.xkind] for t in ref],
        'exit_comment': [t.xcmt for t in ref],
        'entry_comment': [t.ecmt for t in ref],
        'trail_act_px': np.array([nanv(t.tr.A) for t in ref], np.float64),
        'trail_off': np.array([nanv(t.tr.off) for t in ref], np.float64),
        'sl_px': np.array([nanv(t.tr.sl) for t in ref], np.float64),
    })


REF_COLS = ['id', 'dir', 'src', 'entry_row', 'entry_px', 'exit_row', 'exit_px', 'exit_kind', 'exit_comment', 'entry_comment',
            'trail_act_px', 'trail_off', 'sl_px']


def cmp_engine_ref(tr, summ, ref, cnt, rows):
    bad = frames_equal(tr[REF_COLS], ref_frame(ref, rows))
    for a, b in (('entries_skipped_room', 'skipped'), ('entries_ignored_pyramiding', 'pyr'), ('blocked_long', 'blkL'),
                 ('blocked_short', 'blkS'), ('raw_long', 'rawL'), ('raw_short', 'rawS'), ('close_all_bars', 'close_bars')):
        if summ[a] != cnt[b]:
            bad.append('summary %s %r vs reference %r' % (a, summ[a], cnt[b]))
    return bad


# =============================================================================== R3
def _mirror_comment(s):
    """An option-off comment as the option-on run of the mirrored decision words it."""
    for a, b in (('ENTER LONG | ', 'ENTER SHORT (inv) | '), ('ENTER SHORT | ', 'ENTER LONG (inv) | '),
                 ('filter blocked SHORT, close | ', 'filter blocked LONG (inv), close | '),
                 ('filter blocked LONG, close | ', 'filter blocked SHORT (inv), close | ')):
        if s.startswith(a):
            return b + s[len(a):]
    return s


def _mini(c0, steps, idx0):
    """3 flat bars at price c0 (no exit order can trigger) carrying the 3 signal rows `steps`."""
    idx = pd.RangeIndex(idx0, idx0 + 3)
    bars = pd.DataFrame({'open': c0, 'high': c0, 'low': c0, 'close': c0, 't_open': [0, 60, 120], 't_close': [60, 120, 180]}, index=idx)
    sig = pd.DataFrame({'longSrc': [list(s['longSrc']) for s in steps], 'shortSrc': [list(s['shortSrc']) for s in steps],
                        'exitL': [bool(s['exitL']) for s in steps], 'exitS': [bool(s['exitS']) for s in steps],
                        'exitLSrc': [s['exitLSrc'] for s in steps], 'exitSSrc': [s['exitSSrc'] for s in steps]}, index=idx)
    perm = pd.DataFrame({'buyOk': [bool(s['buyOk']) for s in steps], 'sellOk': [bool(s['sellOk']) for s in steps]}, index=idx)
    return bars, sig, perm


def _blank():
    return dict(longSrc=[], shortSrc=[], exitL=False, exitS=False, exitLSrc='', exitSSrc='', buyOk=True, sellOk=True)


def _decision(tr, summ, idx0):
    """What the decision bar (row idx0 + 1) did, read off a 3-bar run."""
    setup = tr[tr['entry_row'] == idx0]
    new = tr[tr['entry_row'] == idx0 + 1]
    return dict(
        pos=(0 if len(setup) == 0 else int(setup['dir'].iloc[0])), n_open=len(setup),
        setup_exit=[(int(r), k, cm) for r, k, cm in zip(setup['exit_row'], setup['exit_kind'], setup['exit_comment'])],
        new=[(i, int(d), s, float(px), cm) for i, d, s, px, cm in zip(new['id'], new['dir'], new['src'], new['entry_px'], new['entry_comment'])],
        lev=np.array([new['trail_act_px'] - new['entry_px'], new['trail_off'], new['sl_px'] - new['entry_px']], np.float64),
        counts=tuple(summ[k] for k in ('entries_skipped_room', 'entries_ignored_pyramiding', 'raw_long', 'raw_short',
                                       'blocked_long', 'blocked_short', 'go_long_bars', 'go_short_bars', 'close_all_bars')))


def r3():
    rng = np.random.default_rng(SEED + 4)
    stats = dict(n=0, pos={-1: 0, 0: 0, 1: 0}, close=0, reverse=0, entries=0, skipped=0, blocked=0, exit_rows=0, held_back=0,
                 nothing=0)
    todo = [c for c in (('BTC', '60'), ('XAU', '240'), ('BTC', '15'), ('XAU', '5')) if c[0] in PAIRS and c[1] in TFS] or cells()[:2]
    per_cell = 700
    for pair, tf in todo:
        t0 = time.time()
        sig, perm = sc.load_inputs(pair, tf, verbose=False)
        close = engine.load_bars(pair, tf)['close'].to_numpy(np.float64)
        rows = np.asarray(sig.index, dtype=np.int64)
        L, S = _lists(sig, 'longSrc'), _lists(sig, 'shortSrc')
        has = np.nonzero((sig['nLongRaw'].to_numpy() + sig['nShortRaw'].to_numpy()) > 0)[0]
        buy, sell = perm['buyOk'].to_numpy(bool), perm['sellOk'].to_numpy(bool)
        for it in range(per_cell):
            r = int(rng.choice(has)) if rng.random() < 0.8 else int(rng.integers(0, len(rows)))
            dec = _blank()
            dec.update(longSrc=list(L[r]), shortSrc=list(S[r]), buyOk=bool(buy[r]), sellOk=bool(sell[r]))
            u = rng.random()
            if u < 0.15 and (dec['longSrc'] or dec['shortSrc']):        # several labels on the bar
                k = int(rng.integers(2, 4))
                dec['longSrc'] = (dec['longSrc'] * k)[:max(k, len(dec['longSrc']))]
                dec['shortSrc'] = (dec['shortSrc'] * k)[:max(k, len(dec['shortSrc']))] if dec['shortSrc'] else []
            if rng.random() < 0.25:                                      # an "exit only" row on the bar
                if rng.random() < 0.5:
                    dec.update(exitL=True, exitLSrc='1 Hour * DIV SHORT ZONE END 1st LEG')
                else:
                    dec.update(exitS=True, exitSSrc='1 Hour * DIV LONG ZONE END 1st LEG')
            if rng.random() < 0.3:                                       # other permissions than the bar's
                dec.update(buyOk=bool(rng.random() < 0.5), sellOk=bool(rng.random() < 0.5))
            prm = dict(tradeDir=str(rng.choice(TD, p=[0.5, 0.25, 0.25])), oppCloses=bool(rng.random() < 0.8),
                       fgfBlkClose=bool(rng.random() < 0.7), fgfOn=bool(rng.random() < 0.7),
                       maxOpen=int(rng.choice([1, 2, 3, 20])), pyramiding=int(rng.choice([100, 100, 100, 2])))
            prm.update(sc.cfg_params(ST.grid_sample(rng, 1)[0] if rng.random() < 0.4 else ST.random_cfg(rng, float(close[rows[r]]))))
            # the prepared position: m labels on one normal-frame side on the setup bar (or none)
            setup = _blank()
            side = int(rng.choice([-1, 0, 1], p=[0.4, 0.2, 0.4]))
            m = int(rng.choice([1, 2, 3]))
            if side > 0:
                setup['longSrc'] = ['5 Min << 1st LEG LONGS'] * m
            elif side < 0:
                setup['shortSrc'] = ['5 Min << 1st LEG SHORTS'] * m
            idx0 = int(rows[r])
            c0 = float(close[rows[r]])
            bars, sg, pm = _mini(c0, [setup, dec, _blank()], idx0)
            A, sA = engine.backtest_bars(bars, sg, pm, dict(prm, xpwInv=True))
            B, sB = engine.backtest_bars(bars, sg, pm, dict(prm, tradeDir=SWAP_TD[prm['tradeDir']]))   # option off, mirrored mode
            dA, dB = _decision(A, sA, idx0), _decision(B, sB, idx0)
            what = '%s %s row %d %r setup %d x%d dec %r' % (pair, tf, idx0, prm, side, m, dec)
            # -- the mirror property
            if dA['pos'] != -dB['pos'] or dA['n_open'] != dB['n_open']:
                raise Fail('%s: prepared positions are not mirrors (%r x%d vs %r x%d)' % (what, dA['pos'], dA['n_open'], dB['pos'], dB['n_open']))
            mirB_exit = [(rw, k, _mirror_comment(cm)) for rw, k, cm in dB['setup_exit']]
            if dA['setup_exit'] != mirB_exit:
                raise Fail('%s: what happens to the open position differs: %r vs mirror %r' % (what, dA['setup_exit'], mirB_exit))
            mirB_new = [(('S' if i[0] == 'L' else 'L') + i[1:], -d, s, px, _mirror_comment(cm)) for i, d, s, px, cm in dB['new']]
            if dA['new'] != mirB_new:
                raise Fail('%s: entries differ: %r vs mirror %r' % (what, dA['new'], mirB_new))
            mirB_lev = dB['lev'] * np.array([[-1.0], [1.0], [-1.0]])
            if dA['lev'].shape != mirB_lev.shape or not np.allclose(dA['lev'], mirB_lev, rtol=0, atol=1e-7, equal_nan=True):
                raise Fail('%s: exit distances are not mirrored: %r vs %r' % (what, dA['lev'], dB['lev']))
            if dA['counts'] != dB['counts']:
                raise Fail('%s: counters differ: %r vs %r' % (what, dA['counts'], dB['counts']))
            # -- both against the script step transcribed from the Pine at HEAD
            for nm, tr, sm, pp in (('on', A, sA, dict(prm, xpwInv=True)), ('off', B, sB, dict(prm, tradeDir=SWAP_TD[prm['tradeDir']]))):
                ref, rc = ref_run(bars, sg, pm, pp)
                bad = cmp_engine_ref(tr, sm, ref, rc, sg.index)
                if bad:
                    raise Fail('%s: option %s: engine != Pine script step: %s' % (what, nm, '; '.join(bad[:4])))
            stats['n'] += 1
            stats['pos'][dA['pos']] += 1
            kinds = [k for _, k, _ in dA['setup_exit']]
            stats['close'] += int('close_all' in kinds)
            stats['reverse'] += int('reverse' in kinds)
            stats['entries'] += len(dA['new'])
            stats['skipped'] += int(dA['counts'][0] > 0)
            stats['blocked'] += int(dA['counts'][4] + dA['counts'][5] > 0)
            stats['exit_rows'] += int(dec['exitL'] or dec['exitS'])
            stats['held_back'] += int(side != 0 and dA['n_open'] == 0)
            stats['nothing'] += int(not dA['new'] and all(k == 'end' for k in kinds))
        print('  R3 %s %-3s: %d decisions on sampled bars: option on from p == mirror of option off from -p; both == Pine step (%.1fs)'
              % (pair, tf, per_cell, time.time() - t0), flush=True)
    for k in ('close', 'reverse', 'entries', 'skipped', 'blocked', 'exit_rows'):
        if stats[k] == 0:
            raise Fail('the sample never exercised %s' % k)
    if min(stats['pos'].values()) == 0:
        raise Fail('a real position sign never occurred: %r' % stats['pos'])
    return ('%d single decisions (real position with the option on: short %d, flat %d, long %d): %d closed the position '
            '(close_all), %d reversed it, %d entries placed, %d with entries held back by Max open entries, %d with a blocked '
            'side, %d with an "exit only" row, %d did nothing; setup not allowed by Trade direction in %d'
            % (stats['n'], stats['pos'][-1], stats['pos'][0], stats['pos'][1], stats['close'], stats['reverse'], stats['entries'],
               stats['skipped'], stats['blocked'], stats['exit_rows'], stats['nothing'], stats['held_back']))


# =============================================================================== R4
def r4():
    sc.check_mag_sync()
    rng = np.random.default_rng(SEED + 5)
    n1 = nf = nm = n_tr = n_dif = 0
    # a) chart "1": mag (real 1-minute sub-bars) == tv, option on
    for pair in PAIRS:
        if '1' not in TFS:
            break
        t0 = time.time()
        start, end = run_tf.WINDOWS[pair]
        sig, perm = sc.load_inputs(pair, '1', verbose=False)
        P = {f: sc.prep(pair, '1', sig, perm, f, inv=True) for f in (False, True)}
        del sig
        sub = sc.sub_bars(pair, '1', P[False]['rows'])
        if not np.array_equal(np.diff(sub[0]), np.ones(len(P[False]['c']), np.int64)):
            raise Fail('%s 1: a chart bar without exactly one sub-bar' % pair)
        ref = float(np.median(P[False]['c']))
        cfgs = ST.grid_sample(rng, 16) + [ST.random_cfg(rng, ref) for _ in range(4)]
        nt = nd = 0
        for cfg in cfgs:
            f = bool(rng.random() < 0.5)
            Rt = sc.run_cfg(P[f], cfg, 'tv')
            Rm = sc.run_cfg(P[f], cfg, 'mag', sub=sub)
            d = first_diff(Rt, Rm)
            if d or not same_metrics(sc.metrics_fast(pair, Rt, P[f]['t_close'], start, end), sc.metrics_fast(pair, Rm, P[f]['t_close'], start, end)):
                raise Fail('%s 1 filter=%s %r inverted: mag != tv: %s' % (pair, f, cfg, d or 'metrics'))
            nd += int(not ST.same_run(Rt, sc.run_cfg(P[f], cfg, 'tv', inv=False)))
            nt += Rt['n']
            n1 += 1
        if nd == 0:
            raise Fail('%s 1: the inverted runs never differed from the normal ones' % pair)
        n_tr += nt
        print('  R4 %s 1  %d bars = %d sub-bars: %d settings, option on: mag == tv (%d trades; inverted != normal in %d) (%.1fs)'
              % (pair, len(P[False]['c']), len(sub[1]), len(cfgs), nt, nd, time.time() - t0), flush=True)
    # b) one sub-bar per chart bar, and c) real sub-bars == engine._run on the 1-minute series
    todo = [c for c in (('BTC', '60'), ('BTC', '5'), ('XAU', '240'), ('XAU', '120'), ('XAU', '15')) if c[0] in PAIRS and c[1] in TFS]
    for pair, tf in todo:
        t0 = time.time()
        sig, perm = sc.load_inputs(pair, tf, verbose=False)
        P = {f: sc.prep(pair, tf, sig, perm, f, inv=True) for f in (False, True)}
        del sig
        for f in (False, True):
            sc.check_mag_equiv(P[f])
        sub = sc.sub_bars(pair, tf, P[False]['rows'])
        fake = sc.fake_sub_bars(P[False])
        ptr = sub[0]
        Q = {f: ST.chart1_equiv(P[f], sub) for f in (False, True)}
        ref = float(np.median(P[False]['c']))
        cfgs = ST.grid_sample(rng, 8) + [ST.random_cfg(rng, ref) for _ in range(4)]
        nt = 0
        for cfg in cfgs:
            f = bool(rng.random() < 0.5)
            Rt = sc.run_cfg(P[f], cfg, 'tv')
            Rf = sc.run_cfg(P[f], cfg, 'mag', sub=fake)
            d = first_diff(Rt, Rf)
            if d:
                raise Fail('%s %s filter=%s %r inverted: mag (one sub-bar per bar) != tv: %s' % (pair, tf, f, cfg, d))
            nf += 1
            Rm = sc.run_cfg(P[f], cfg, 'mag', sub=sub)
            R1 = sc.run_cfg(Q[f], cfg, 'tv', inv=True)              # the canonical kernel on the 1-minute series
            e1 = np.searchsorted(ptr, R1['erow'], side='right') - 1
            x1 = np.searchsorted(ptr, R1['xrow'], side='right') - 1
            same = (Rm['n'] == R1['n'] and np.array_equal(Rm['erow'], e1) and np.array_equal(Rm['xrow'], x1)
                    and np.array_equal(ptr[e1 + 1] - 1, R1['erow'])
                    and all(np.array_equal(Rm[k], R1[k]) for k in ('dir', 'k', 'epx', 'xpx', 'xkind')))
            if not same:
                raise Fail('%s %s filter=%s %r inverted: mag != engine._run on the 1-minute series (%d vs %d trades)'
                           % (pair, tf, f, cfg, Rm['n'], R1['n']))
            n_dif += int(not ST.same_run(Rt, Rm))
            nm += 1
            nt += Rm['n']
        n_tr += nt
        print('  R4 %s %-3s %d bars, %d sub-bars: %d settings, option on: mag(one sub-bar per bar) == tv; mag(real sub-bars) == '
              'engine._run on the 1-minute series (%d trades) (%.1fs)' % (pair, tf, len(P[False]['c']), len(sub[1]), len(cfgs), nt, time.time() - t0), flush=True)
    if todo and n_dif == 0:
        raise Fail('mag never differed from tv on real sub-bars: the test does not exercise them')
    return ('option on: chart "1" mag == tv on %d settings; one sub-bar per bar: mag == tv on %d; real sub-bars: mag == '
            'engine._run on the 1-minute series on %d (mag != tv in %d); %d trades; check_mag_sync and check_mag_equiv pass'
            % (n1, nf, nm, n_dif, n_tr))


# =============================================================================== R5
def r5():
    rng = np.random.default_rng(SEED + 6)
    n_tv = n_mag = n_tr = n_neg = 0
    kinds = {}
    cover = dict(inv=0, one_side=0, exit_only=0, rev=0, small_room=0, pyr=0, skipped=0, pyr_hit=0, close_bars=0)
    for pair, tf, a, b in ST.T1_WINDOWS:
        if pair not in PAIRS:
            continue
        t0 = time.time()
        perm = fgf.fgf_permissions(pair, tf, a, b, {})
        sigs = {'normal': xpw.xpw_signals(pair, tf, a, b, {}),
                'rev': xpw.xpw_signals(pair, tf, a, b, {'reverseAll': True}),
                'exit': xpw.xpw_signals(pair, tf, a, b, dict(EXIT_ONLY)),
                'exit_rev': xpw.xpw_signals(pair, tf, a, b, dict(EXIT_ONLY, reverseAll=True))}
        rows = np.asarray(sigs['normal'].index, dtype=np.int64)
        bars = engine.load_bars(pair, tf).iloc[rows].set_axis(sigs['normal'].index)
        ref_px = float(np.median(bars['close'].to_numpy()))
        sub_me = MR.my_sub_bars(pair, tf, rows)                      # independent of sweep_core.sub_bars
        sub_sc = sc.sub_bars(pair, tf, rows)
        # ---- tv: engine.backtest vs the reference, random inputs
        for it in range(36):
            lab = str(rng.choice(['normal', 'normal', 'rev', 'exit', 'exit_rev']))
            prm = dict(xpwInv=bool(rng.random() < 0.67), fgfOn=bool(rng.random() < 0.6),
                       tradeDir=str(rng.choice(TD, p=[0.5, 0.25, 0.25])), oppCloses=bool(rng.random() < 0.8),
                       fgfBlkClose=bool(rng.random() < 0.7), maxOpen=int(rng.choice([1, 2, 3, 20, 20])),
                       pyramiding=int(rng.choice([100, 100, 100, 2])))
            cfg = MR.fixed_cfgs()[it % 8] if it < 8 else (ST.random_cfg(rng, ref_px) if it % 2 else MR.random_cfg(rng, ref_px))
            prm.update(sc.cfg_params(cfg))
            tr, summ = engine.backtest(pair, tf, sigs[lab], perm, prm)
            ref, rc = ref_run(bars, sigs[lab], perm, prm)
            bad = cmp_engine_ref(tr, summ, ref, rc, rows)
            if bad:
                raise Fail('%s %s tv labels=%s %r: engine.backtest != reference: %s' % (pair, tf, lab, prm, '; '.join(bad[:4])))
            if bool(summ.get('xpwInv', False)) != prm['xpwInv']:
                raise Fail('summary xpwInv flag wrong')
            if it < 6:                                               # the comparison has power: the other flag is rejected
                ref2, rc2 = ref_run(bars, sigs[lab], perm, dict(prm, xpwInv=not prm['xpwInv']))
                if not cmp_engine_ref(tr, summ, ref2, rc2, rows):
                    raise Fail('%s %s %r: the reference with the opposite flag also matches' % (pair, tf, prm))
                n_neg += 1
            n_tv += 1
            n_tr += len(tr)
            for k, v in tr['exit_kind'].value_counts().items():
                kinds[k] = kinds.get(k, 0) + int(v)
            cover['inv'] += prm['xpwInv']
            cover['one_side'] += prm['tradeDir'] != 'Both'
            cover['exit_only'] += lab.startswith('exit')
            cover['rev'] += lab.endswith('rev')
            cover['small_room'] += prm['maxOpen'] < 20
            cover['pyr'] += prm['pyramiding'] == 2
            cover['skipped'] += int(summ['entries_skipped_room'] > 0)
            cover['pyr_hit'] += int(summ['entries_ignored_pyramiding'] > 0)
            cover['close_bars'] += int(summ['close_all_bars'] > 0)
        # ---- mag: run_cfg(P inverted / not, 'mag') vs the reference on its own sub-bars (default inputs)
        for it in range(12):
            lab = str(rng.choice(['normal', 'normal', 'rev', 'exit']))
            inv = bool(rng.random() < 0.75)
            f = bool(rng.random() < 0.5)
            cfg = MR.fixed_cfgs()[it] if it < 4 else MR.random_cfg(rng, ref_px)
            P = sc.prep(pair, tf, sc._trim_sig(sigs[lab]), perm, f, inv=inv)
            R = sc.run_cfg(P, cfg, 'mag', sub=sub_sc)
            ref, rc = ref_run(bars, sigs[lab], perm, dict(sc.cfg_params(cfg), fgfOn=f, xpwInv=inv), sub=sub_me)
            A = MR.ref_arrays([t.tr for t in ref])
            bad = MR._cmp(R, A)
            if not np.array_equal(R['k'].astype(np.int64), np.array([t.tr.k for t in ref], np.int64)):
                bad.append('k differs')
            if bad:
                raise Fail('%s %s mag labels=%s filter=%s inv=%s %r: run_cfg != reference: %s' % (pair, tf, lab, f, inv, cfg, '; '.join(bad[:4])))
            Rt = sc.run_cfg(P, cfg, 'tv')                            # and the tv kernel through prep / run_cfg
            ref_t, _ = ref_run(bars, sigs[lab], perm, dict(sc.cfg_params(cfg), fgfOn=f, xpwInv=inv))
            bad = MR._cmp(Rt, MR.ref_arrays([t.tr for t in ref_t]))
            if bad:
                raise Fail('%s %s tv (run_cfg) labels=%s filter=%s inv=%s %r: != reference: %s' % (pair, tf, lab, f, inv, cfg, '; '.join(bad[:4])))
            n_mag += 1
            n_tr += R['n']
        print('  R5 %s %-3s %d bars: 36 engine.backtest runs (tv) and 12 run_cfg runs (mag + tv) == pure-Python reference (%.1fs)'
              % (pair, tf, len(rows), time.time() - t0), flush=True)
    for k in ('trail', 'sl', 'close_all', 'reverse', 'end'):
        if kinds.get(k, 0) == 0:
            raise Fail('exit kind %s never occurred' % k)
    return ('%d tv runs (engine.backtest: ids, real sides, prices, exit kinds, comments, levels, counters) and %d mag runs == the '
            'reference, %d trades; exit kinds %r; of the tv runs: inverted %d, one-side mode %d, "exit only" rows %d, reversed labels '
            '%d, Max open entries < 20 %d (entries held back in %d), pyramiding 2 %d (orders ignored in %d), close_all in %d; '
            'opposite flag rejected in %d / %d' % (n_tv, n_mag, n_tr, kinds, cover['inv'], cover['one_side'], cover['exit_only'],
                                                   cover['rev'], cover['small_room'], cover['skipped'], cover['pyr'],
                                                   cover['pyr_hit'], cover['close_bars'], n_neg, n_neg))


TESTS = {'R1': r1, 'R2': r2, 'R3': r3, 'R4': r4, 'R5': r5}


def main(argv):
    global PAIRS, TFS
    names = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--tfs':
            TFS = [x for x in argv[i + 1].split(',') if x]
            i += 2
        elif a == '--pairs':
            PAIRS = [x for x in argv[i + 1].split(',') if x]
            i += 2
        else:
            names.append(a.upper())
            i += 1
    names = names or list(TESTS)
    for nm in names:
        if nm not in TESTS:
            print('unknown test %s' % nm)
            return 2
    print('inv_tests_xpw: engine.py %d sweep_core.py %d xpw.py %d fgf.py %d (mtime ns); pairs %s, timeframes %s'
          % (tuple(os.stat(os.path.join(W, f)).st_mtime_ns for f in ('engine.py', 'sweep_core.py', 'xpw.py', 'fgf.py'))
             + (','.join(PAIRS), ','.join(TFS))), flush=True)
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
