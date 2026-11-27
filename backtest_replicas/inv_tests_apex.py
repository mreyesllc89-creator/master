"""inv_tests_apex.py: tests of the Update 1 option "Inverted direction" (Pine input apxInv,
replica param `apxInv`, alias `inv`) added to apex.py (INV_BT_SPEC.md, task 2).

Usage: python3 -I inv_tests_apex.py [FILTER ...]
  Runs every function named test_<Rn>_<name> whose name contains one of the FILTER substrings
  (none = all). Prints PASS / FAIL per test and exits non-zero on any failure.

  R1  option off = before:  R1a every variant x cost of out/apex_<PAIR>_<TF>.json (14 cells,
      every saved field, and the saved trade lists); R1b a sample of out/swah_apex_*.parquet
      rows (tv and mag); R1c the module against its pre-change copy
      (pre_inv_backup/apex.py) on random settings, every output array bit for bit.
  R2  filter OFF (header: "With the filter off and 'Inverted direction' on every signal
      trades the opposite side"; apex has no Pine reverse option, the replica's control is
      `reverse` + reverseStops 'mirror'):  R2a inv == the reversed-labels run trade by trade
      (and == the saved rev_off_mir summaries);  R2b inv == the UNCHANGED normal kernel on
      relabelled inputs (signals swapped, gates swapped with them, brackets 2*close - x),
      bit for bit, filter off AND on;  R2c the header's statements checked on the trade
      lists (side against the signal, gate of the SIGNAL's side, blocked-opposite close on
      the mirrored position, exit levels = the mirrored bracket of the last same-kind signal).
  R3  mirror property on single decisions (kernel probes on real bars): the decision taken
      with the option on from real position p == the mirror of the decision with it off
      from -p; and both == a literal transcription of the Pine script step.
  R4  'mag' on chart "1" == 'tv' with the option on (and mag with one fake sub-bar per chart
      bar == tv on other charts).
  R5  (extra) engine == an independent pure-Python reference written from the Pine at HEAD
      in the REAL frame (string ids "Apex Long" / "Exit Short" ...), trade by trade, option
      on and off, tv and mag, random exits / costs / filter.
  R6  (extra) speed of the kernel against the pre-change kernel.
  R7  (extra) the files written by run_inv_apex.py against the saved results and a recomputation.
  R8  (extra) mutants of the new script step and of the parameter plumbing are each caught.
  R9  (sceptic) the two names of the option (Pine apxInv, alias inv) through run / prepare /
      simulate, and which one wins.
  R10 (sceptic) single decisions with an opening gap after the signal candle: the bracket is
      mirrored about the signal CLOSE, not about the fill (R3's probes are flat).
  R11 (sceptic) the filter's "Allow buys" / "Allow sells" keep meaning the SIGNAL's side
      (header: Allow buys off + inverted leaves only BUY orders, i.e. real longs).
"""
from __future__ import annotations

import importlib.util
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
import apex  # noqa: E402              (the module under test)
import run_apex  # noqa: E402          (VARIANTS / EXTRAS of the saved results)
import sweep_apex  # noqa: E402        (grid / columns of the saved sweep)
import verify_trail_apex as VT  # noqa: E402   (independent exit walk along a bar path, sub-bars)

TFS = ('1', '5', '15', '30', '60', '120', '240')
PAIRS = ('BTC', 'XAU')
INIT = 1_000_000.0
TICK = 0.01
NAN = float('nan')
ACTS = (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
OFFS = (0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)


def _p(*a):
    print(*a, flush=True)


_PRE = None


def pre_module():
    """The pre-change apex.py (pre_inv_backup/apex.py), loaded under another name, reading
    the same data directory."""
    global _PRE
    if _PRE is None:
        f = os.path.join(W, 'pre_inv_backup', 'apex.py')
        spec = importlib.util.spec_from_file_location('apex_pre_inv', f)
        m = importlib.util.module_from_spec(spec)
        sys.modules['apex_pre_inv'] = m
        spec.loader.exec_module(m)
        bdir = os.path.dirname(f)
        while bdir in sys.path:              # the copy puts its own folder first on sys.path
            sys.path.remove(bdir)
        m.DATA = apex.DATA
        _PRE = m
    return _PRE


def _same_arrays(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x.shape != y.shape or x.dtype != y.dtype:
            return False
        if x.dtype.kind == 'f':
            if not np.array_equal(x, y, equal_nan=True):
                return False
        elif not np.array_equal(x, y):
            return False
    return True


def _feq(a, b):
    a = float(a)
    b = float(b)
    return a == b or (math.isnan(a) and math.isnan(b))


def _clean(x):
    if isinstance(x, float):
        if math.isnan(x):
            return None
        if math.isinf(x):
            return 'inf' if x > 0 else '-inf'
        return x
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if hasattr(x, 'item'):
        return _clean(x.item())
    return x


def _random_exit(rng, trail_share=0.8, path=None, costs=('tv', 'ours', 'stress')):
    def pick(grid, lo):
        return float(rng.choice(grid)) if rng.random() < 0.7 else float(np.round(rng.uniform(lo, 5.0), 4))
    return dict(trailOn=bool(rng.random() < trail_share), trailAct=pick(ACTS, 0.0), trailOff=pick(OFFS, 0.0),
                useTarget=bool(rng.random() < 0.5), blkClose=bool(rng.random() < 0.8),
                cost=str(rng.choice(list(costs))), path=path or str(rng.choice(['tv', 'mag'])))


# =============================================================================================
# R1: option off reproduces every saved result
# =============================================================================================
def test_R1a_saved_json():
    """Option off (absent / apxInv False / inv False, in turn): every saved result of
    run_apex.py, 14 cells x every variant x cost, every saved summary field exact (seconds
    excluded), and the saved trade lists (out/apex_trades, cost tv) exact on every column."""
    ok = True
    n_sum = n_tr = n_rows = 0
    forms = ({}, {'apxInv': False}, {'inv': False})
    used = [0, 0, 0]
    t0 = time.time()
    for pair in PAIRS:
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
                    q.update(forms[n_sum % 3])
                    used[n_sum % 3] += 1
                    tr, s = apex.run(pair, tf, q)
                    s = dict(s)
                    s['variant'] = var
                    s['stopped_at_fill_open'] = int(((tr.entry_bar == tr.exit_bar) & (tr.exit_kind == 'sl')
                                                     & (tr.exit_px == tr.entry_px)).sum())
                    if s.get('inv') is not False:
                        ok = False
                        _p('  FAIL %s %s %s %s: summary inv is %r' % (pair, tf, var, cost, s.get('inv')))
                    s = _clean(s)
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
    _p('  R1a: %d summaries (every saved field; option absent %d / apxInv False %d / inv False %d), '
       '%d trade lists / %d trade rows (every saved column) compared exactly, %.0fs'
       % (n_sum, used[0], used[1], used[2], n_tr, n_rows, time.time() - t0))
    return ok and n_sum == 182 and n_tr == 70


def test_R1b_saved_sweep_rows():
    """Option off: 40 random rows of every out/swah_apex_<PAIR>_<TF>.parquet (20 tv + 20 mag,
    4 trail-off + 16 trail-on each; chart 1 mag rows with the real mag kernel), recomputed
    with apex.simulate from the row's own columns: every summary column identical."""
    ok = True
    rng = np.random.default_rng(20261124)
    t0 = time.time()
    tot = 0
    for pair in PAIRS:
        for tf in TFS:
            t1 = time.time()
            d = pd.read_parquet(os.path.join(OUT, 'swah_apex_%s_%s.parquet' % (pair, tf)))
            pth = d['path'].to_numpy()
            ton = d['trailOn'].to_numpy()
            idx = []
            for path in ('tv', 'mag'):
                for on, k in ((False, 4), (True, 16)):
                    idx += [int(i) for i in rng.choice(np.flatnonzero((pth == path) & (ton == on)), k, replace=False)]
            S = {}
            bad = []
            for i in idx:
                row = d.iloc[i]
                key = (row['filter'], row['labels'])
                if key not in S:
                    S[key] = apex.prepare(pair, tf, {'fgfOn': key[0] == 'on', 'reverse': key[1] == 'rev'})
                X = {'trailOn': bool(row['trailOn']), 'useTarget': bool(row['useTarget']), 'path': row['path'],
                     'cost': row['cost'], 'blkClose': True}
                if X['trailOn']:
                    X['trailAct'] = float(row['trailAct'])
                    X['trailOff'] = float(row['trailOff'])
                if i % 2:
                    X['inv'] = False
                _, s = apex.simulate(S[key], X)
                for k in sweep_apex.SUM_COLS:
                    if not (s[k] == row[k] or (isinstance(s[k], float) and math.isnan(s[k]) and math.isnan(row[k]))):
                        bad.append('row %d %s: saved %r now %r' % (i, k, row[k], s[k]))
            tot += len(idx)
            if bad:
                ok = False
            _p('  %s %-4s: %d rows (%d tv, %d mag) x %d columns: %s (%.1fs)'
               % (pair, tf, len(idx), sum(pth[i] == 'tv' for i in idx), sum(pth[i] == 'mag' for i in idx),
                  len(sweep_apex.SUM_COLS), 'ok' if not bad else 'FAIL ' + '; '.join(bad[:3]), time.time() - t1))
    _p('  R1b: %d sweep rows recomputed, %.0fs' % (tot, time.time() - t0))
    return ok


R1C_CELLS = (('BTC', '60', 10), ('XAU', '60', 10), ('BTC', '15', 8), ('XAU', '240', 8), ('BTC', '240', 8),
             ('XAU', '5', 6), ('BTC', '1', 4))


def test_R1c_against_pre_change_module():
    """Option off: the edited apex.py against its pre-change copy (pre_inv_backup/apex.py),
    random settings (filter, reverse / reverseStops, pivotTies, trailing, target, blkClose,
    all three costs, tv and mag): the prepared arrays and all 15 broker outputs (trade
    arrays, equity / position curves, stats) are bit-identical, and so is every summary
    field the old module had."""
    pre = pre_module()
    rng = np.random.default_rng(424242)
    ok = True
    t0 = time.time()
    n = ntr = 0
    for pair, tf, k in R1C_CELLS:
        fails = 0
        tr_here = 0
        for i in range(k):
            p = {'fgfOn': bool(rng.random() < 0.6), 'reverse': bool(rng.random() < 0.3),
                 'reverseStops': str(rng.choice(['literal', 'mirror'])),
                 'pivotTies': 'left_strict' if rng.random() < 0.15 else 'strict'}
            X = _random_exit(rng)
            Xn = dict(X)
            if i % 2:
                Xn['inv'] = False
            Sn = apex.prepare(pair, tf, p)
            Sp = pre.prepare(pair, tf, p)
            keys = ('o', 'h', 'l', 'c', 't_open', 't_close', 'sig_l', 'sig_s', 'buy_ok', 'sell_ok',
                    'stp_l', 'lim_l', 'stp_s', 'lim_s')
            same = _same_arrays([Sn[x] for x in keys], [Sp[x] for x in keys])
            on, sn = apex.simulate(Sn, Xn, want_curves=True)
            op, sp = pre.simulate(Sp, X, want_curves=True)
            same = same and _same_arrays(on, op)
            diff = [x for x in sp if x != 'seconds' and _clean(sp[x]) != _clean(sn.get(x))]
            n += 1
            tr_here += len(on[0])
            if not same or diff or sn['inv'] is not False:
                ok = False
                fails += 1
                _p('  FAIL %s %s %s %s: arrays same %s, summary diff %s' % (pair, tf, p, X, same, diff[:4]))
        ntr += tr_here
        _p('  %s %-4s: %d settings, %d trades, %d failures' % (pair, tf, k, tr_here, fails))
    _p('  R1c: %d runs, %d trades, new == pre-change bit for bit (%.0fs)' % (n, ntr, time.time() - t0))
    return ok


# =============================================================================================
# R2: filter off, the header's statements
# =============================================================================================
def _frame(S, out):
    return apex.trades_frame(S, out)


def _cmp_frames_tol(a, b, rtol_px=1e-12, rtol_money=1e-9):
    """Two trade frames: integer columns and the entry price exact, exit price / money within a
    relative tolerance. Returns (error or None, number of rows whose exit_px differs in bits,
    max |exit_px diff|)."""
    if len(a) != len(b):
        return 'trade count %d vs %d' % (len(a), len(b)), 0, 0.0
    if len(a) == 0:
        return None, 0, 0.0
    for col in ('dir', 'entry_time', 'exit_time', 'entry_bar', 'exit_bar', 'signal_bar'):
        m = a[col].to_numpy() != b[col].to_numpy()
        if m.any():
            return '%s differs at trade %d' % (col, int(np.argmax(m))), 0, 0.0
    m = a['exit_kind'].astype(str).to_numpy() != b['exit_kind'].astype(str).to_numpy()
    if m.any():
        return 'exit_kind differs at trade %d' % int(np.argmax(m)), 0, 0.0
    if (a['entry_px'].to_numpy() != b['entry_px'].to_numpy()).any():
        return 'entry_px differs', 0, 0.0
    xa, xb = a['exit_px'].to_numpy(), b['exit_px'].to_numpy()
    dx = np.abs(xa - xb)
    if (dx > rtol_px * np.abs(xb)).any():
        return 'exit_px differs by %g at trade %d' % (dx.max(), int(np.argmax(dx))), int((xa != xb).sum()), float(dx.max())
    for col in ('qty', 'pnl', 'entry_cost', 'exit_cost', 'eq_before'):
        va, vb = a[col].to_numpy(), b[col].to_numpy()
        dd = np.abs(va - vb) / np.maximum(1.0, np.abs(vb))
        if (dd > rtol_money).any():
            return '%s differs (rel %g) at trade %d' % (col, dd.max(), int(np.argmax(dd))), int((xa != xb).sum()), float(dx.max())
    return None, int((xa != xb).sum()), float(dx.max())


def test_R2a_filter_off_equals_reversed_labels():
    """Filter off: the inv run == the existing reversed-labels run with mirrored brackets
    (reverse True, reverseStops 'mirror', verified in reconcile_apex.md / run_apex.py), trade by
    trade: side, bars, times, exit kind, entry price exact; exit price within 1e-12 relative
    (the Pine mirrors the already rounded normal target, `2*close - (close + (close - S)*rr)`,
    where the replica's control computes `close - (close - S)*rr` directly: algebraically equal,
    not always bit-equal; the mirrored stops `2*close - S` and `close + (close - S)` ARE
    bit-equal, the inner difference being exact: counted); money within
    1e-9. All 14 cells: defaults on the tv path with both costs, the mag path, and 3 random
    exit settings each. And the default tv / cost-tv run against the SAVED rev_off_mir summary of
    out/apex_<PAIR>_<TF>.json (counts exact, money 1e-9 relative)."""
    ok = True
    rng = np.random.default_rng(31)
    t0 = time.time()
    tot = {'runs': 0, 'trades': 0, 'bits': 0}
    mx = 0.0
    for pair in PAIRS:
        for tf in TFS:
            Sn = apex.prepare(pair, tf, {'fgfOn': False})
            Sr = apex.prepare(pair, tf, {'fgfOn': False, 'reverse': True, 'reverseStops': 'mirror'})
            sets = [dict(cost='tv', path='tv'), dict(cost='ours', path='tv'), dict(cost='tv', path='mag')]
            sets += [_random_exit(rng) for _ in range(3)]
            msgs = []
            ntr = nb = 0
            for X in sets:
                oi, si = apex.simulate(Sn, dict(X, inv=True))
                orv, sr = apex.simulate(Sr, dict(X, inv=False))
                err, bits, dmax = _cmp_frames_tol(_frame(Sn, oi), _frame(Sr, orv))
                tot['runs'] += 1
                ntr += len(oi[0])
                nb += bits
                mx = max(mx, dmax)
                if err:
                    msgs.append('%s: %s' % (X, err))
                # the signal-side counts swap (reverse relabels the signals; inv keeps the FGD side)
                if (si['raw_long'], si['raw_short']) != (sr['raw_short'], sr['raw_long']):
                    msgs.append('raw counts')
                if (si['long'], si['short'], si['exit_kinds']) != (sr['long'], sr['short'], sr['exit_kinds']):
                    msgs.append('%s: long / short / exit kinds' % X)
            # the saved reversed-labels (mirror) summary
            sv = json.load(open(os.path.join(OUT, 'apex_%s_%s.json' % (pair, tf))))['rev_off_mir']['tv']
            _, si = apex.simulate(Sn, {'inv': True})
            si = _clean(si)
            for k in ('trades', 'long', 'short', 'exit_kinds', 'bars'):
                if si[k] != sv[k]:
                    msgs.append('saved rev_off_mir %s: %r vs %r' % (k, si[k], sv[k]))
            for k in ('net_pct', 'pf', 'win_pct', 'max_dd_pct', 'half1_pct', 'half2_pct', 'exposure', 'costs',
                      'final_equity'):
                a, b = si[k], sv[k]
                num = isinstance(a, (int, float)) and isinstance(b, (int, float))
                if not (a == b or (num and abs(a - b) <= 1e-9 * max(1.0, abs(b)))):
                    msgs.append('saved rev_off_mir %s: %r vs %r' % (k, a, b))
            tot['trades'] += ntr
            tot['bits'] += nb
            if msgs:
                ok = False
            _p('  %s %-4s: %d settings, %d trades (%d exit prices not bit-equal), saved rev_off_mir %d trades '
               'net %+.6f%% vs inv %+.6f%%: %s' % (pair, tf, len(sets), ntr, nb, sv['trades'], sv['net_pct'],
                                                 si['net_pct'], 'ok' if not msgs else 'FAIL ' + '; '.join(msgs[:3])))
    _p('  R2a: %d runs, %d trades compared; %d exit prices differ in the last bits (max |diff| %.3g); %.0fs'
       % (tot['runs'], tot['trades'], tot['bits'], mx, time.time() - t0))
    return ok


def relabel(S):
    """The inverted script as inputs of the NORMAL script: the signals swapped, each gate
    moved with its signal, each bracket mirrored about the close with the Pine's own
    expression (2.0 * close - x) and moved with its signal."""
    c = S['c']
    R = dict(S)
    R['sig_l'], R['sig_s'] = S['sig_s'], S['sig_l']
    R['buy_ok'], R['sell_ok'] = S['sell_ok'], S['buy_ok']
    R['stp_l'] = 2.0 * c - S['stp_s']
    R['lim_l'] = 2.0 * c - S['lim_s']
    R['stp_s'] = 2.0 * c - S['stp_l']
    R['lim_s'] = 2.0 * c - S['lim_l']
    R['raw_long'], R['raw_short'] = S['raw_short'], S['raw_long']
    R['blocked_long'], R['blocked_short'] = S['blocked_short'], S['blocked_long']
    return R


def test_R2b_inv_equals_normal_kernel_on_relabelled_inputs(cells=None):
    """inv on == the normal (option off) kernel run on relabelled inputs: signals swapped,
    each gate and each bracket moved with its signal, the bracket mirrored with the Pine's
    expression 2.0 * close - x. Every broker output (trade arrays with the real side, equity /
    position curves, stats) bit-identical, and every summary field equal (the raw / blocked
    signal counts keep the SIGNAL's side when inverted, so they are compared swapped). Filter
    off AND on, 14 cells x 2 filters x 4 exit settings (the default + 3 random; tv and mag).
    Also: bull and bear resonance never share a bar (so the order of the two blocks cannot
    matter)."""
    ok = True
    rng = np.random.default_rng(77)
    t0 = time.time()
    n = ntr = 0
    for pair, tf in (cells or [(a, b) for a in PAIRS for b in TFS]):
        if True:
            fails = 0
            tr_here = 0
            both = 0
            for flt in (False, True):
                S = apex.prepare(pair, tf, {'fgfOn': flt})
                both += int((S['sig_l'] & S['sig_s']).sum())
                R = relabel(S)
                for X in [dict(path='tv', cost='tv')] + [_random_exit(rng) for _ in range(3)]:
                    oi, si = apex.simulate(S, dict(X, inv=True), want_curves=True)
                    on, sn = apex.simulate(R, dict(X, inv=False), want_curves=True)
                    n += 1
                    tr_here += len(oi[0])
                    # the raw / blocked counts keep the SIGNAL's side when inverted (the FGD rows):
                    # on the relabelled inputs they are the swapped ones
                    swap = {'raw_long': 'raw_short', 'raw_short': 'raw_long',
                            'blocked_long': 'blocked_short', 'blocked_short': 'blocked_long'}
                    skip = ('seconds', 'inv', 'params')
                    diff = [k for k in si if k not in skip and _clean(si[k]) != _clean(sn[swap.get(k, k)])]
                    if not _same_arrays(oi, on) or diff or si['inv'] is not True:
                        ok = False
                        fails += 1
                        _p('  FAIL %s %s fgf=%s %s: %s' % (pair, tf, flt, X, diff[:4]))
            if both:
                ok = False
            ntr += tr_here
            _p('  %s %-4s: 8 runs, %d trades, %d failures; bars with both signals: %d' % (pair, tf, tr_here, fails, both))
    _p('  R2b: %d runs, %d trades, inv == normal kernel on relabelled inputs bit for bit (%.0fs)'
       % (n, ntr, time.time() - t0))
    return ok


def _check_header_statements(S, X, out, flt):
    """The header's statements on one run (tv or mag), from the trade arrays, the position
    curve and the prepared signal / gate / bracket arrays. Returns (list of errors, counters)."""
    inv = bool(X.get('inv', False))
    t_dir, t_eb, t_epx, t_qty, t_xb, t_xpx, t_kind, t_pnl, t_ecom, t_xcom, t_sigb = out[:11]
    posc = out[12]
    n = len(S['c'])
    bull, bear, bok, sok = S['sig_l'], S['sig_s'], S['buy_ok'], S['sell_ok']
    err = []
    cnt = {'trades': len(t_dir), 'level_exits': 0, 'open_exits': 0, 'blocked_close': 0, 'resend_brackets': 0}
    sd = -1 if inv else 1                       # real side of the trade a BUY signal opens
    # (1) the side against the signal; the gate of the SIGNAL's side
    for j in range(len(t_dir)):
        k = int(t_sigb[j])
        d = int(t_dir[j])
        is_buy_sig = d == sd                    # this trade was opened by a BUY (bull) signal
        if is_buy_sig:
            if not (bull[k] and bok[k]):
                err.append('trade %d (dir %d): no allowed BUY signal on its signal bar' % (j, d))
        elif not (bear[k] and sok[k]):
            err.append('trade %d (dir %d): no allowed SELL signal on its signal bar' % (j, d))
        if int(t_eb[j]) != k + 1 or t_epx[j] != S['o'][k + 1]:
            err.append('trade %d: not filled at the next open' % j)
    # (2) every allowed signal trades (unless that signal's trade is already open): entries
    posn = posc * sd                            # apxPosN at each bar close
    want = set()
    for k in np.flatnonzero((bull & bok) | (bear & sok)):
        if k == n - 1:
            continue
        side = 1 if bull[k] else -1             # signal frame
        if posn[k] != side:
            want.add(int(k))
    got = set(int(k) for k in t_sigb)
    if want != got:
        err.append('signal bars that should open a trade: %d, trades: %d, missing %s, extra %s'
                   % (len(want), len(got), sorted(want - got)[:3], sorted(got - want)[:3]))
    # (3) blocked-opposite close on the mirrored position
    blk = bool(X.get('blkClose', True))
    wantc = set()
    if blk:
        for k in np.flatnonzero((bear & ~sok) | (bull & ~bok)):
            if k == n - 1:
                continue
            if bear[k] and not sok[k] and posn[k] > 0:
                wantc.add(int(k) + 1)
            if bull[k] and not bok[k] and posn[k] < 0:
                wantc.add(int(k) + 1)
    gotc = set(int(t_xb[j]) for j in range(len(t_dir)) if t_kind[j] == apex.K_BLK)
    cnt['blocked_close'] = len(gotc)
    if wantc != gotc:
        err.append('blocked closes: expected %d, got %d' % (len(wantc), len(gotc)))
    if not flt and (gotc or (S['blocked_long'] + S['blocked_short'])):
        err.append('filter off but blocked signals / closes')
    # (4) stop / target = the bracket of the last same-kind signal bar, mirrored when inverted
    #     (only decidable without the trailing; a level, or an open beyond it)
    if not X.get('trailOn', False):
        c = S['c']
        mag = X.get('path', 'tv') == 'mag'
        for j in range(len(t_dir)):
            kd = int(t_kind[j])
            if kd not in (apex.K_SL, apex.K_TP):
                continue
            d = int(t_dir[j])
            is_buy_sig = d == sd
            sig = bull if is_buy_sig else bear
            k0, k1 = int(t_sigb[j]), int(t_xb[j])
            ks = k0 + int(np.flatnonzero(sig[k0:k1])[-1])            # last (re-)send before the exit bar
            if ks != k0:
                cnt['resend_brackets'] += 1
            stp = (S['stp_l'] if is_buy_sig else S['stp_s'])[ks]
            lim = (S['lim_l'] if is_buy_sig else S['lim_s'])[ks]
            if inv:
                stp = 2.0 * c[ks] - stp
                lim = 2.0 * c[ks] - lim
            lvl = stp if kd == apex.K_SL else lim
            x = t_xpx[j]
            if x == lvl:
                cnt['level_exits'] += 1
            else:
                beyond = (d * (x - lvl) < 0) if kd == apex.K_SL else (d * (x - lvl) > 0)
                at_open = mag or x == S['o'][k1]
                if beyond and at_open:
                    cnt['open_exits'] += 1
                else:
                    err.append('trade %d: %s at %r, level %r (signal bar %d, last send %d)'
                               % (j, apex._KINDS[kd], x, lvl, k0, ks))
            # the mirrored bracket is on the right side of the signal close
            if not ((d * (c[ks] - stp) > 0) and (d * (lim - c[ks]) > 0)):
                err.append('trade %d: bracket not around the close' % j)
    return err, cnt


def test_R2c_header_statements():
    """The header's statements, checked on the trade lists of the inverted runs (and of the
    normal runs as a control of the check): filter OFF 'every signal trades the opposite
    side'; filter ON 'a BUY the filter allows is placed as a SELL ... a blocked signal stays
    blocked', 'a blocked SELL signal closes the open short, a blocked BUY signal the open
    long'; 'stop = 2 x close - normal stop, target = 2 x close - normal target' and 'a later
    signal of the same kind still re-sets that trade's stop and target'. 14 cells x filter
    off / on x option on / off, tv path (plus mag on 60 / 240), default exits."""
    ok = True
    t0 = time.time()
    tot = {}
    nrun = 0
    for pair in PAIRS:
        for tf in TFS:
            msgs = []
            line = []
            for flt in (False, True):
                S = apex.prepare(pair, tf, {'fgfOn': flt})
                for inv in (True, False):
                    for path in (('tv', 'mag') if tf in ('60', '240') else ('tv',)):
                        X = {'inv': inv, 'path': path, 'blkClose': True, 'trailOn': False}
                        out, s = apex.simulate(S, X, want_curves=True)
                        err, cnt = _check_header_statements(S, X, out, flt)
                        nrun += 1
                        # the opposite side: with the filter off every trade is against its signal
                        if inv:
                            sig_side = np.where(S['sig_l'][out[10]], 1, -1)
                            if len(out[0]) and not np.array_equal(out[0], -sig_side):
                                err.append('a trade is not on the opposite side of its signal')
                            for k, v in cnt.items():
                                tot[k] = tot.get(k, 0) + v
                            if path == 'tv':
                                line.append('%s %d tr (%dL %dS)' % ('on' if flt else 'off', s['trades'], s['long'], s['short']))
                        if err:
                            msgs.append('fgf=%s inv=%s %s: %s' % (flt, inv, path, err[0]))
            if msgs:
                ok = False
            _p('  %s %-4s inverted: %s: %s' % (pair, tf, ', '.join(line), 'ok' if not msgs else 'FAIL ' + ' | '.join(msgs[:3])))
    _p('  R2c: %d runs; inverted runs: %s (%.0fs)' % (nrun, tot, time.time() - t0))
    return ok and tot.get('level_exits', 0) > 1000 and tot.get('blocked_close', 0) > 100 and tot.get('resend_brackets', 0) > 10


# =============================================================================================
# The literal Pine reference (Pine at HEAD, lines 800-865), REAL frame, string ids
# =============================================================================================
def ref_rates(pair, cost):
    """(rate of the fill value, $ per unit) per fill: INV_BT_SPEC 'script' (0.04% per side) /
    'ours' (XAU $0.30 per ounce round trip; BTC 0.02% per side + $0.20 round trip) and the
    stress costs of SWEEP_AH_SPEC."""
    if cost == 'tv':
        return 0.04 / 100.0, 0.0
    if cost == 'ours':
        return (0.0, 0.30 / 2.0) if pair == 'XAU' else (0.02 / 100.0, 0.20 / 2.0)
    if cost == 'stress':
        return (0.0, 0.50 / 2.0 + 0.01) if pair == 'XAU' else (0.035 / 100.0, 0.10 + 0.01)
    raise ValueError(cost)


def V_from_S(S):
    """Per-bar inputs of the script as lists. bull / bear = the resonance signals as prepared
    (sig_l / sig_s), stopB / tgtB = stopPrice / targetPrice of the BUY block, stopS / tgtS of
    the SELL block."""
    return dict(o=S['o'].tolist(), h=S['h'].tolist(), l=S['l'].tolist(), c=S['c'].tolist(),
                bull=S['sig_l'].tolist(), bear=S['sig_s'].tolist(),
                buyOk=S['buy_ok'].tolist(), sellOk=S['sell_ok'].tolist(),
                stopB=S['stp_l'].tolist(), tgtB=S['lim_l'].tolist(),
                stopS=S['stp_s'].tolist(), tgtS=S['lim_s'].tolist())


def pine_ref(V, X, rate, fee, sub=None, want_state=False):
    """Independent pure-Python reference of the Pine at HEAD (Update 1), written in the REAL
    frame the way TradingView sees the script: entries and exit orders are kept by their
    string ids ("Apex Long" is always a real long), the script reads strategy.position_size
    and derives apxPosN / apxIdBuy / apxIdSell / apxExBuy / apxExSell exactly as lines 814-818.
    Broker rules of SPEC_AH.md; the exit order of the open trade is walked along the bar path
    (or the 1-minute sub-bars) with verify_trail_apex.walk (independent of apex._walk).
    Returns the trade dicts (and, with want_state, the final state before the end close)."""
    o, h, l, c = V['o'], V['h'], V['l'], V['c']
    n = len(c)
    apxInv = bool(X.get('inv', False))
    apxBlkClose = bool(X['blkClose'])
    apxTrailOn = bool(X['trailOn'])
    apxTrailAct = float(X.get('trailAct', 1.0))
    apxTrailOff = float(X.get('trailOff', 0.5))
    apxUseTarget = bool(X['useTarget'])
    mag = X['path'] == 'mag'
    LONG, SHORT = 1, -1                       # strategy.long / strategy.short
    trades = []
    closed = 0.0
    tr = None                                 # the open trade (id, dir, ...)
    exits = {}                                # exit id -> order (from_entry, stop, limit, pts, ofs)
    pending = []                              # market orders placed at the last close, in order
    apxTrPtsL = apxTrOfsL = apxTrPtsS = apxTrOfsS = NAN       # var float ... = na

    def close(i, px, kind):
        nonlocal tr, closed
        xc = rate * px * tr['qty'] + fee * tr['qty']
        pnl = tr['dir'] * (px - tr['epx']) * tr['qty'] - tr['ecost'] - xc
        tr.update(exit_bar=i, exit_px=px, exit_kind=kind, pnl=pnl)
        trades.append(tr)
        closed += pnl
        for xid in [x for x, e in exits.items() if e['from_entry'] == tr['id']]:
            del exits[xid]                    # an exit whose entry trade has closed is cancelled
        tr = None

    for i in range(n):
        # market orders of the previous bar fill at this open, in the order placed
        for od in pending:
            if od[0] == 'close':              # strategy.close(id)
                if tr is not None and tr['id'] == od[1]:
                    close(i, o[i], 'blocked_close')
            else:                             # strategy.entry(id, direction)
                _, eid, d, q, sb = od
                if tr is not None and tr['dir'] == d:
                    continue                  # pyramiding = 0
                if tr is not None:
                    close(i, o[i], 'reverse')
                tr = dict(id=eid, dir=d, entry_bar=i, signal_bar=sb, epx=o[i], qty=q,
                          ecost=rate * o[i] * q + fee * q, eq_before=INIT + closed,
                          has_trail=False, armed=False, best=NAN, act_px=NAN, ofs=NAN)
        pending = []
        # the open trade's strategy.exit order along this bar
        if tr is not None:
            ex = None
            for e in exits.values():
                if e['from_entry'] == tr['id']:
                    ex = e
            if ex is not None:
                tr['has_trail'] = not math.isnan(ex['pts'])
                if tr['has_trail']:
                    tr['act_px'] = tr['epx'] + tr['dir'] * ex['pts'] * TICK
                    tr['ofs'] = ex['ofs'] * TICK
                if mag:
                    paths = [VT._path(sub['o'][k], sub['h'][k], sub['l'][k], sub['c'][k])
                             for k in range(sub['lo'][i], sub['hi'][i])]
                else:
                    paths = [VT._path(o[i], h[i], l[i], c[i])]
                r = VT.walk(tr, ex, paths)
                if r is not None:
                    close(i, r[0], r[1])
        if i == n - 1:
            break                             # orders placed on the last bar never fill
        # ------------------------------------------------------------------ the script, bar close
        position_size = 0 if tr is None else tr['dir']            # sign of strategy.position_size
        equity = INIT + closed
        if tr is not None:
            equity += tr['dir'] * (c[i] - tr['epx']) * tr['qty'] - tr['ecost']
        close_ = c[i]
        bullResonance, bearResonance = V['bull'][i], V['bear'][i]
        fgfBuyOk, fgfSellOk = V['buyOk'][i], V['sellOk'][i]
        apxGoLong = bullResonance and fgfBuyOk                                        # 800
        apxGoShort = bearResonance and fgfSellOk                                      # 801
        apxBlkLong = bullResonance and not fgfBuyOk                                   # 802
        apxBlkShort = bearResonance and not fgfSellOk                                 # 803
        apxPosN = -position_size if apxInv else position_size                         # 814
        apxIdBuy = 'Apex Short' if apxInv else 'Apex Long'                            # 815
        apxIdSell = 'Apex Long' if apxInv else 'Apex Short'                           # 816
        apxExBuy = 'Exit Short' if apxInv else 'Exit Long'                            # 817
        apxExSell = 'Exit Long' if apxInv else 'Exit Short'                           # 818
        if apxBlkClose and apxBlkShort and apxPosN > 0:                               # 822
            pending.append(('close', apxIdBuy))
        if apxBlkClose and apxBlkLong and apxPosN < 0:                                # 824
            pending.append(('close', apxIdSell))
        if apxGoLong:                                                                 # 838
            pending.append(('entry', apxIdBuy, SHORT if apxInv else LONG, 0.01 * equity / close_, i))
            if apxPosN <= 0:
                apxTrPtsL = max(close_ * apxTrailAct / 100.0 / TICK, 0.0) if apxTrailOn else NAN
                apxTrOfsL = max(close_ * apxTrailOff / 100.0 / TICK, 1.0) if apxTrailOn else NAN
        if apxGoLong or (bullResonance and apxPosN > 0):                              # 844
            stopPrice = V['stopB'][i]
            targetPrice = V['tgtB'][i]
            apxStopBuy = 2.0 * close_ - stopPrice if apxInv else stopPrice            # 849
            apxTgtBuy = 2.0 * close_ - targetPrice if apxInv else targetPrice         # 850
            exits[apxExBuy] = dict(from_entry=apxIdBuy, stop=apxStopBuy,
                                   limit=NAN if (apxTrailOn and not apxUseTarget) else apxTgtBuy,
                                   pts=apxTrPtsL, ofs=apxTrOfsL)
        if apxGoShort:                                                                # 853
            pending.append(('entry', apxIdSell, LONG if apxInv else SHORT, 0.01 * equity / close_, i))
            if apxPosN >= 0:
                apxTrPtsS = max(close_ * apxTrailAct / 100.0 / TICK, 0.0) if apxTrailOn else NAN
                apxTrOfsS = max(close_ * apxTrailOff / 100.0 / TICK, 1.0) if apxTrailOn else NAN
        if apxGoShort or (bearResonance and apxPosN < 0):                             # 858
            stopPrice = V['stopS'][i]
            targetPrice = V['tgtS'][i]
            apxStopSell = 2.0 * close_ - stopPrice if apxInv else stopPrice           # 863
            apxTgtSell = 2.0 * close_ - targetPrice if apxInv else targetPrice        # 864
            exits[apxExSell] = dict(from_entry=apxIdSell, stop=apxStopSell,
                                    limit=NAN if (apxTrailOn and not apxUseTarget) else apxTgtSell,
                                    pts=apxTrPtsS, ofs=apxTrOfsS)
    state = None
    if want_state:
        state = dict(pos=0 if tr is None else tr['dir'], exits={k: dict(v) for k, v in exits.items()},
                     pts_buy=apxTrPtsL, ofs_buy=apxTrOfsL, pts_sell=apxTrPtsS, ofs_sell=apxTrOfsS)
    if tr is not None:
        close(n - 1, c[n - 1], 'end')
    return (trades, state) if want_state else trades


def cmp_engine_ref(out, ref):
    """Engine broker arrays vs reference trade dicts: sides / bars / kinds / prices exact, money 1e-9."""
    t_dir, t_eb, t_epx, t_qty, t_xb, t_xpx, t_kind, t_pnl, t_ecom, t_xcom, t_sigb = out[:11]
    t_eqb = out[13]
    if len(t_dir) != len(ref):
        return 'trade count %d vs ref %d' % (len(t_dir), len(ref))
    for j, r in enumerate(ref):
        eng = (int(t_dir[j]), int(t_eb[j]), int(t_xb[j]), int(t_sigb[j]), apex._KINDS[t_kind[j]],
               float(t_epx[j]), float(t_xpx[j]))
        rr = (r['dir'], r['entry_bar'], r['exit_bar'], r['signal_bar'], r['exit_kind'], r['epx'], r['exit_px'])
        if eng != rr:
            return 'trade %d: engine %s vs ref %s' % (j, eng, rr)
        if (r['id'] == 'Apex Long') != (r['dir'] > 0):
            return 'trade %d: id %s with dir %d' % (j, r['id'], r['dir'])
        for nm, a, b in (('qty', t_qty[j], r['qty']), ('pnl', t_pnl[j], r['pnl']), ('eq_before', t_eqb[j], r['eq_before'])):
            if not math.isclose(float(a), b, rel_tol=1e-9, abs_tol=1e-9):
                return 'trade %d: %s engine %r vs ref %r' % (j, nm, float(a), b)
    return None


# =============================================================================================
# R3: single decisions
# =============================================================================================
R3_CELLS = (('BTC', '60'), ('XAU', '240'), ('BTC', '15'), ('XAU', '60'))
R3_TRAILS = ((False, 1.0, 0.5, True), (True, 0.3, 0.2, True), (True, 0.0, 0.05, False))


def _probe(inv, setup, dec, c0, ck, lv, blk, trail, rate, fee):
    """One decision through the real kernel: 3 flat bars. Bar 0 (price c0): an optional setup
    signal (+1 BUY kind, -1 SELL kind, gates open, no stop / target) whose order fills at bar
    1's open. Bar 1 (price ck = the sampled bar's close): the decision under test, with the
    given signals dec = (bull, bear, buyOk, sellOk) and the sampled bar's stop / target
    lv = (stopB, tgtB, stopS, tgtS). Bar 2 (price ck): the orders fill; last bar.
    Returns the broker output with the final state (apex.STATE_KEYS in stats[4:])."""
    o = np.array([c0, ck, ck])
    sig_l = np.array([setup == 1, dec[0], False])
    sig_s = np.array([setup == -1, dec[1], False])
    buy_ok = np.array([True, dec[2], True])
    sell_ok = np.array([True, dec[3], True])
    keep = not (trail[0] and not trail[3])
    stp_l = np.array([NAN, lv[0], NAN])
    lim_l = np.array([NAN, lv[1] if keep else NAN, NAN])
    stp_s = np.array([NAN, lv[2], NAN])
    lim_s = np.array([NAN, lv[3] if keep else NAN, NAN])
    return apex._broker(o, o, o, o, sig_l, sig_s, buy_ok, sell_ok, stp_l, lim_l, stp_s, lim_s,
                        blk, rate, fee, apex.INIT_CAPITAL, 1.0, trail[0], trail[1], trail[2],
                        apex.MINTICK, apex.TRAIL_TOL, False, *apex._NO_SUB, 8, 0, True, inv, True)


def _probe_ref(inv, setup, dec, c0, ck, lv, blk, trail, rate, fee):
    V = dict(o=[c0, ck, ck], h=[c0, ck, ck], l=[c0, ck, ck], c=[c0, ck, ck],
             bull=[setup == 1, dec[0], False], bear=[setup == -1, dec[1], False],
             buyOk=[True, dec[2], True], sellOk=[True, dec[3], True],
             stopB=[NAN, lv[0], NAN], tgtB=[NAN, lv[1], NAN], stopS=[NAN, lv[2], NAN], tgtS=[NAN, lv[3], NAN])
    X = dict(inv=inv, blkClose=blk, trailOn=trail[0], trailAct=trail[1], trailOff=trail[2], useTarget=trail[3],
             path='tv')
    return pine_ref(V, X, rate, fee, want_state=True)


def _mirror_error(I, N, ck, p):
    """I = the probe with the option on (real position p at the decision), N = the same
    inputs with it off (position -p). None if I is the mirror of N."""
    if int(I[12][1]) != p or int(N[12][1]) != -p:
        return 'precondition: position at the decision %d (on) / %d (off), wanted %d / %d' % (I[12][1], N[12][1], p, -p)
    if len(I[0]) != len(N[0]):
        return 'orders: %d trades vs %d' % (len(I[0]), len(N[0]))
    if not np.array_equal(I[0], -N[0]):
        return 'trade sides not opposite'
    for j in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13):       # every other trade array, equity curve, eq_before
        if not np.array_equal(I[j], N[j], equal_nan=True):
            return 'output %d differs' % j
    if not np.array_equal(I[12], -N[12]):
        return 'position curve not mirrored'
    si, sn = I[14], N[14]
    if not np.array_equal(si[:4], sn[:4]):
        return 'equity stats differ'
    a = dict(zip(apex.STATE_KEYS, si[4:].tolist()))
    b = dict(zip(apex.STATE_KEYS, sn[4:].tolist()))
    if a['pos'] != -b['pos']:
        return 'final position not mirrored'
    for mine, other in (('xl', 'xs'), ('xs', 'xl')):         # Exit Long (on) <-> Exit Short (off)
        if a[mine + '_on'] != b[other + '_on']:
            return '%s_on' % mine
        if not _feq(a[mine + '_stop'], 2.0 * ck - b[other + '_stop']):
            return '%s_stop %r is not 2*close - %r' % (mine, a[mine + '_stop'], b[other + '_stop'])
        if not _feq(a[mine + '_limit'], 2.0 * ck - b[other + '_limit']):
            return '%s_limit %r is not 2*close - %r' % (mine, a[mine + '_limit'], b[other + '_limit'])
        if not (_feq(a[mine + '_pts'], b[other + '_pts']) and _feq(a[mine + '_ofs'], b[other + '_ofs'])):
            return '%s trail ticks' % mine
    for k in ('pts_buy', 'ofs_buy', 'pts_sell', 'ofs_sell'):  # per SIGNAL kind on both sides
        if not _feq(a[k], b[k]):
            return k
    return None


def _ref_error(K, ref):
    """A kernel probe against the literal Pine reference: trades and final state."""
    trades, st = ref
    err = cmp_engine_ref(K, trades)
    if err:
        return err
    a = dict(zip(apex.STATE_KEYS, K[14][4:].tolist()))
    if int(a['pos']) != st['pos']:
        return 'final position %d vs ref %d' % (a['pos'], st['pos'])
    for xid, pre, eid in (('Exit Long', 'xl', 'Apex Long'), ('Exit Short', 'xs', 'Apex Short')):
        e = st['exits'].get(xid)
        if (a[pre + '_on'] != 0.0) != (e is not None):
            return '%s: engine on=%s, ref %s' % (xid, a[pre + '_on'], e)
        if e is not None:
            if e['from_entry'] != eid:
                return '%s from_entry %s' % (xid, e['from_entry'])
            for k1, k2 in (('_stop', 'stop'), ('_limit', 'limit'), ('_pts', 'pts'), ('_ofs', 'ofs')):
                if not _feq(a[pre + k1], e[k2]):
                    return '%s %s: engine %r ref %r' % (xid, k2, a[pre + k1], e[k2])
    for k in ('pts_buy', 'ofs_buy', 'pts_sell', 'ofs_sell'):
        if not _feq(a[k], st[k]):
            return '%s: engine %r ref %r' % (k, a[k], st[k])
    return None


def _outcome(K):
    """A short label of what the decision did (coverage tally)."""
    kinds = [apex._KINDS[k] for k in K[6]]
    a = dict(zip(apex.STATE_KEYS, K[14][4:].tolist()))
    lab = []
    if 'blocked_close' in kinds:
        lab.append('close')
    if 'reverse' in kinds:
        lab.append('reverse')
    if len(K[0]) and int(K[1][-1]) == 2:
        lab.append('entry')
    if not math.isnan(a['xl_stop']) or not math.isnan(a['xs_stop']):
        lab.append('bracket')
    if 'sl' in kinds or 'tp' in kinds:
        lab.append('exit@open')
    return '+'.join(lab) or 'nothing'


def test_R3_single_decision_mirror(cells=None, nsig=120, noth=60):
    """Single decisions through the real kernel on sampled bars (every signal bar up to 120
    per cell + 60 other bars; their close and their stop / target, also where the forced signal
    gives a bracket on the wrong side of the price): for each real position p in {-1, 0, +1} x
    the 16 combinations of (bull, bear, buyOk, sellOk) (also the ones the data never shows) x
    blkClose on / off x 3 exit settings (no trail; trail 0.3 / 0.2 with target; trail 0 / 0.05
    without target): the decision with the option ON from real position p is the mirror of the
    decision with it OFF from -p: orders on the other side (same bars, prices, sizes, P/L), the
    exit order on the other id with stop = 2*close - stop and limit = 2*close - limit, the same
    trailing ticks per signal kind. And each of the two decisions equals the literal Pine
    transcription (pine_ref: string ids, strategy.position_size)."""
    ok = True
    t0 = time.time()
    tally = {}
    nprobe = nmis = nref = 0
    ident = 0
    for pair, tf in (cells or R3_CELLS):
        S = apex.prepare(pair, tf, {'fgfOn': False})
        rate, fee = apex.cost_rates(pair, 'tv' if pair == 'BTC' else 'ours')
        rng = np.random.default_rng(5)
        sigbars = np.flatnonzero(S['sig_l'] | S['sig_s'])
        if len(sigbars) > nsig:
            sigbars = np.sort(rng.choice(sigbars, nsig, replace=False))
        valid = np.flatnonzero(~np.isnan(S['stp_l']) & ~np.isnan(S['stp_s']) & ~(S['sig_l'] | S['sig_s']))
        others = np.sort(rng.choice(valid, noth, replace=False))
        bars = np.concatenate([sigbars, others])
        fails = 0
        first = None
        for k in bars.tolist():
            ck = float(S['c'][k])
            c0 = ck * 1.0005
            lv = (float(S['stp_l'][k]), float(S['lim_l'][k]), float(S['stp_s'][k]), float(S['lim_s'][k]))
            for p in (-1, 0, 1):
                setup = -p                      # option on: a SELL-kind signal opens the real long
                for code in range(16):
                    dec = (bool(code & 1), bool(code & 2), bool(code & 4), bool(code & 8))
                    for blk in (True, False):
                        for trail in R3_TRAILS:
                            I = _probe(True, setup, dec, c0, ck, lv, blk, trail, rate, fee)
                            N = _probe(False, setup, dec, c0, ck, lv, blk, trail, rate, fee)
                            nprobe += 1
                            err = _mirror_error(I, N, ck, p)
                            if err is None:
                                e1 = _ref_error(I, _probe_ref(True, setup, dec, c0, ck, lv, blk, trail, rate, fee))
                                e2 = _ref_error(N, _probe_ref(False, setup, dec, c0, ck, lv, blk, trail, rate, fee))
                                nref += 2
                                if e1 or e2:
                                    err = 'vs Pine transcription: %s' % (e1 or e2)
                            lab = _outcome(I)
                            tally[lab] = tally.get(lab, 0) + 1
                            if _same_arrays(I, N):
                                ident += 1
                            if err:
                                nmis += 1
                                fails += 1
                                if first is None:
                                    first = 'bar %d p=%d dec=%s blk=%s trail=%s: %s' % (k, p, dec, blk, trail, err)
        if fails:
            ok = False
        _p('  %s %-4s: %d bars (%d signal bars) x 288 decisions: %d failures%s'
           % (pair, tf, len(bars), len(sigbars), fails, '' if first is None else ' | first: ' + first))
    _p('  R3: %d decisions (each: option on from p vs option off from -p), %d mirror / transcription failures; '
       '%d kernel-vs-Pine-transcription comparisons' % (nprobe, nmis, nref))
    _p('  outcomes of the inverted decisions: %s' % dict(sorted(tally.items(), key=lambda kv: -kv[1])))
    _p('  decisions where on and off give the SAME output without mirroring: %d of %d (the test is not vacuous '
       'on the other %d) (%.0fs)' % (ident, nprobe, nprobe - ident, time.time() - t0))
    need = ('close', 'reverse', 'entry', 'bracket')
    covered = all(any(n in lab.split('+') for lab in tally) for n in need)
    return ok and covered and nprobe - ident > 1000 and nref == 2 * nprobe


# =============================================================================================
# R4: mag on chart 1 == tv with the option on
# =============================================================================================
def test_R4_mag_chart1_equals_tv_inverted():
    """Option ON: 'mag' on chart "1" (real 1-minute sub-bars = the chart bars) == 'tv', BTC 1
    and XAU 1 full windows, filter off and on, 6 exit settings each (the default + 5 random with
    trailing, all costs); and mag with one fake sub-bar per chart bar == tv on BTC 60 / XAU 60 /
    BTC 240 / XAU 240 (10 settings each). Every trade array and the equity stats identical."""
    ok = True
    rng = np.random.default_rng(404)
    t0 = time.time()
    for pair, tf, fake, k in (('BTC', '1', False, 6), ('XAU', '1', False, 6), ('BTC', '60', True, 10),
                              ('XAU', '60', True, 10), ('BTC', '240', True, 10), ('XAU', '240', True, 10)):
        fails = ntr = ntrail = nshort = 0
        for flt in (False, True):
            S = apex.prepare(pair, tf, {'fgfOn': flt})
            for i in range(k // 2):
                X = dict(blkClose=True, cost='tv') if i == 0 else _random_exit(rng, trail_share=0.9)
                X['inv'] = True
                ot, st = apex.simulate(S, dict(X, path='tv'))
                om, sm = apex.simulate(S, dict(X, path='mag'), sub=apex.fake_sub_bars(S) if fake else None)
                ntr += len(ot[0])
                ntrail += int((ot[6] == apex.K_TRAIL).sum())
                nshort += int((ot[0] < 0).sum())
                same = (_same_arrays(ot[:11] + ot[13:], om[:11] + om[13:]) and st['inv'] and sm['inv']
                        and sm['exit_params']['path'] == 'mag')
                if not same:
                    ok = False
                    fails += 1
                    _p('  FAIL %s %s fgf=%s %s: mag != tv' % (pair, tf, flt, X))
        _p('  %s %-3s %s: %d settings, %d trades (%d short, %d trail exits), %d failures'
           % (pair, tf, 'fake sub-bars' if fake else 'real sub-bars (chart 1)', k, ntr, nshort, ntrail, fails))
    _p('  R4: %.0fs' % (time.time() - t0))
    return ok


# =============================================================================================
# R5 (extra): engine == literal Pine reference, full runs
# =============================================================================================
R5_CELLS = (('BTC', '60', None, None, 12, 4), ('XAU', '60', None, None, 12, 4), ('XAU', '240', None, None, 10, 4),
            ('BTC', '240', None, None, 10, 4), ('BTC', '15', 1735689600, 1743465600, 10, 3),
            ('XAU', '15', None, None, 6, 0), ('BTC', '5', 1735689600, 1751328000, 6, 0))


def test_R5_reference_pine_head(cells=None, need_kinds=True):
    """Engine == pine_ref (the Pine at HEAD transcribed in the real frame with its string ids;
    the open trade's exit walked by verify_trail_apex.walk), trade by trade: side, entry /
    exit / signal bars, exit kind and both prices exact, qty / P&L / equity-before within 1e-9.
    7 cells; random filter, blkClose, trailing / target, cost (tv / ours / stress); option ON in
    3 runs of 4 (OFF in the rest, which validates the reference on the verified path); tv and
    mag (real 1-minute sub-bars, rebuilt by verify_trail_apex.build_sub); 1 run in 5 with the
    replica's `reverse` control on top."""
    ok = True
    rng = np.random.default_rng(20261123)
    t0 = time.time()
    tot = {'runs': 0, 'trades': 0, 'inv_runs': 0, 'inv_trades': 0, 'mag_runs': 0}
    kinds = {}
    sides = {1: 0, -1: 0}
    for pair, tf, start, end, n_tv, n_mag in (cells or R5_CELLS):
        fails = 0
        ntr = 0
        subs = None
        for i in range(n_tv + n_mag):
            path = 'tv' if i < n_tv else 'mag'
            X = _random_exit(rng, trail_share=0.7, path=path)
            X['inv'] = bool(i % 4 != 3)
            p = {'fgfOn': bool(rng.random() < 0.6), 'reverse': bool(rng.random() < 0.2),
                 'reverseStops': str(rng.choice(['literal', 'mirror']))}
            if start is not None:
                p.update(start=start, end=end)
            S = apex.prepare(pair, tf, p)
            if path == 'mag' and subs is None:
                subs = VT.build_sub(pair, S)
            out, s = apex.simulate(S, X)
            rate, fee = ref_rates(pair, X['cost'])
            ref = pine_ref(V_from_S(S), X, rate, fee, subs if path == 'mag' else None)
            err = cmp_engine_ref(out, ref)
            tot['runs'] += 1
            tot['trades'] += len(ref)
            tot['mag_runs'] += path == 'mag'
            if X['inv']:
                tot['inv_runs'] += 1
                tot['inv_trades'] += len(ref)
                for r in ref:
                    kinds[r['exit_kind']] = kinds.get(r['exit_kind'], 0) + 1
                    sides[r['dir']] += 1
            ntr += len(ref)
            if err or s['inv'] != X['inv']:
                ok = False
                fails += 1
                _p('  FAIL %s %s %s %s: %s' % (pair, tf, p, X, err))
        _p('  %s %-4s: %d tv + %d mag settings, %d trades, %d failures' % (pair, tf, n_tv, n_mag, ntr, fails))
    _p('  R5: %d runs (%d mag), %d trades; option on: %d runs, %d trades (%d long, %d short), exit kinds %s (%.0fs)'
       % (tot['runs'], tot['mag_runs'], tot['trades'], tot['inv_runs'], tot['inv_trades'], sides[1], sides[-1],
          dict(sorted(kinds.items())), time.time() - t0))
    if not need_kinds:
        return ok
    return ok and kinds.get('trail', 0) > 100 and kinds.get('blocked_close', 0) > 50 and kinds.get('sl', 0) > 100


# =============================================================================================
# R6 (extra): speed
# =============================================================================================
def _best(fn, reps):
    best = float('inf')
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t)
    return best


def test_R6_speed():
    """Kernel speed, best of 9: one exit setting on BTC 1 (1.04M bars, tv; trail off and a
    trailing setting) and on BTC 60 mag (1.04M sub-bars), new kernel with the option off and on
    against the pre-change kernel. Pass: every new timing <= 1.5 x the pre-change one + 5 ms and
    BTC 1 < 0.5 s per setting (SWEEP_AH_SPEC)."""
    pre = pre_module()
    ok = True
    for pair, tf, path in (('BTC', '1', 'tv'), ('BTC', '60', 'mag')):
        Sn = apex.prepare(pair, tf, {'fgfOn': True})
        Sp = pre.prepare(pair, tf, {'fgfOn': True})
        for X in (dict(path=path), dict(path=path, trailOn=True, trailAct=0.3, trailOff=0.2)):
            pre.simulate(Sp, X)
            apex.simulate(Sn, dict(X, inv=False))
            apex.simulate(Sn, dict(X, inv=True))
            tp = _best(lambda: pre.simulate(Sp, X), 9)
            t0 = _best(lambda: apex.simulate(Sn, dict(X, inv=False)), 9)
            t1 = _best(lambda: apex.simulate(Sn, dict(X, inv=True)), 9)
            good = t0 <= 1.5 * tp + 0.005 and t1 <= 1.5 * tp + 0.005 and (tf != '1' or max(t0, t1) < 0.5)
            ok = ok and good
            _p('  %s %-3s %s trail=%s: pre-change %.4fs | new, option off %.4fs (x%.2f) | new, option on %.4fs (x%.2f): %s'
               % (pair, tf, path, X.get('trailOn', False), tp, t0, t0 / tp, t1, t1 / tp, 'ok' if good else 'SLOW'))
    return ok


# =============================================================================================
# R7 (extra): the files written by run_inv_apex.py
# =============================================================================================
def _jsame(a, b, rtol=0.0):
    if a == b:
        return True
    if rtol and isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= rtol * max(1.0, abs(b))
    return False


def test_R7_runner_files():
    """Every out/inv_apex_<PAIR>_<TF>.json written by run_inv_apex.py: (a) the 16 runs
    (direction x filter x path x cost) and the 16 reference runs are present, with their key
    fields; (b) normal tv runs == the saved out/apex_<PAIR>_<TF>.json (off / on, cost tv / ours:
    every saved field) and rev_literal / rev_mirror == the saved rev_off / rev_on / rev_off_mir /
    rev_on_mir; (c) normal and rev_literal runs, tv AND mag == the trail-off rows of the saved
    sweep out/swah_apex_<PAIR>_<TF>.parquet (every summary column); (d) inverted, filter off ==
    rev_mirror, filter off (counts exact, money 1e-9); (e) every run recomputed with
    apex.simulate is identical; (f) inside each run: inv flag, long + short = trades = the exit
    counts = h1_trades + h2_trades, and the raw / blocked signal counts of the inverted runs are
    those of the normal runs (the signal's side); (g) chart 1: mag == tv."""
    import glob
    files = sorted(glob.glob(os.path.join(OUT, 'inv_apex_*_*.json')))
    if not files:
        _p('  no out/inv_apex_*.json yet (run run_inv_apex.py first)')
        return False
    ok = True
    cm = {'script': 'tv', 'ours': 'ours'}
    combos = [(fl, p, c) for fl in ('off', 'on') for p in ('tv', 'mag') for c in ('script', 'ours')]
    skip = ('seconds', 'variant')
    for f in files:
        res = json.load(open(f))
        m = res['_meta']
        pair, tf = m['pair'], m['tf']
        msgs = []
        runs, ref = res['runs'], res['reference']
        if set(runs) != {'%s/%s/%s/%s' % ((d,) + x) for d in ('normal', 'inverted') for x in combos}:
            msgs.append('run keys')
        if set(ref) != {'%s/%s/%s/%s' % ((d,) + x) for d in ('rev_literal', 'rev_mirror') for x in combos}:
            msgs.append('reference keys')
        if m['window'] != list(apex.WINDOWS[pair]) or os.path.basename(f) != 'inv_apex_%s_%s.json' % (pair, tf):
            msgs.append('window / name')
        saved = json.load(open(os.path.join(OUT, 'apex_%s_%s.json' % (pair, tf))))
        sw = pd.read_parquet(os.path.join(OUT, 'swah_apex_%s_%s.parquet' % (pair, tf)))
        sw = sw[(~sw['trailOn']) & sw['useTarget']]
        nb = ns = 0
        S = {}
        for d, src, inv, lab, pp in (('normal', runs, False, 'normal', {}), ('inverted', runs, True, None, {}),
                                     ('rev_literal', ref, False, 'rev', {'reverse': True}),
                                     ('rev_mirror', ref, False, None, {'reverse': True, 'reverseStops': 'mirror'})):
            for fl, path, c in combos:
                key = '%s/%s/%s/%s' % (d, fl, path, c)
                s = src.get(key)
                if s is None:
                    continue
                if (s['direction'], s['filter'], s['path'], s['cost']) != (d, fl, path, c) or s['inv'] is not inv \
                        or s['exit_params']['path'] != path or s['params']['cost'] != cm[c] \
                        or s['params']['fgfOn'] is not (fl == 'on') or s['pair'] != pair or s['tf'] != tf:
                    msgs.append('%s: key fields' % key)
                # (f) inside the run
                if not (s['long'] + s['short'] == s['trades'] == s['h1_trades'] + s['h2_trades']
                        == sum(s['exit_' + k] for k in apex._KINDS) == sum(s['exit_kinds'].values())):
                    msgs.append('%s: counts' % key)
                # (b) the saved by-timeframe results (tv path)
                var = {('normal', 'off'): 'off', ('normal', 'on'): 'on', ('rev_literal', 'off'): 'rev_off',
                       ('rev_literal', 'on'): 'rev_on', ('rev_mirror', 'off'): 'rev_off_mir',
                       ('rev_mirror', 'on'): 'rev_on_mir'}.get((d, fl))
                if var is not None and path == 'tv' and cm[c] in saved[var]:
                    sv = saved[var][cm[c]]
                    bad = [k for k in sv if k not in skip and sv[k] != s.get(k)]
                    nb += 1
                    if bad:
                        msgs.append('%s vs saved %s/%s: %s' % (key, var, cm[c], bad[:4]))
                # (c) the saved sweep (tv and mag)
                if lab is not None:
                    row = sw[(sw['filter'] == fl) & (sw['path'] == path) & (sw['labels'] == lab) & (sw['cost'] == cm[c])]
                    if len(row) != 1:
                        msgs.append('%s: %d sweep rows' % (key, len(row)))
                    else:
                        row = row.iloc[0]
                        ns += 1
                        for k in sweep_apex.SUM_COLS:
                            a, b = s[k], row[k]
                            a = float('inf') if a == 'inf' else (float('nan') if a is None else a)
                            if not (a == b or (isinstance(a, float) and math.isnan(a) and math.isnan(b))):
                                msgs.append('%s vs sweep %s: %r vs %r' % (key, k, s[k], b))
                # (e) recomputed
                kS = (fl, tuple(sorted(pp.items())))
                if kS not in S:
                    S[kS] = apex.prepare(pair, tf, dict(pp, fgfOn=fl == 'on'))
                _, s2 = apex.simulate(S[kS], {'inv': inv, 'path': path, 'cost': cm[c]})
                s2 = _clean(dict(s2))
                bad = [k for k in s2 if k != 'seconds' and s2[k] != s.get(k)]
                if bad:
                    msgs.append('%s recomputed: %s' % (key, bad[:4]))
        for fl, path, c in combos:
            a = runs.get('inverted/%s/%s/%s' % (fl, path, c))
            n = runs.get('normal/%s/%s/%s' % (fl, path, c))
            if a is None or n is None:
                continue
            # (f) the signal counts keep the signal's side
            if any(a[k] != n[k] for k in ('raw_long', 'raw_short', 'blocked_long', 'blocked_short', 'bars')):
                msgs.append('inverted/%s/%s/%s: raw / blocked counts differ from normal' % (fl, path, c))
            if fl == 'off':                  # (d) == the reversed labels with mirrored brackets
                b = ref.get('rev_mirror/off/%s/%s' % (path, c))
                for k in ('trades', 'long', 'short', 'exit_kinds', 'h1_trades', 'h2_trades'):
                    if a[k] != b[k]:
                        msgs.append('inverted/off/%s/%s vs rev_mirror %s: %r vs %r' % (path, c, k, a[k], b[k]))
                for k in ('net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'exposure', 'avg_bars_held',
                          'costs', 'final_equity'):
                    if not _jsame(a[k], b[k], 1e-9):
                        msgs.append('inverted/off/%s/%s vs rev_mirror %s: %r vs %r' % (path, c, k, a[k], b[k]))
        if tf == '1':                        # (g)
            for d, src in (('normal', runs), ('inverted', runs), ('rev_literal', ref), ('rev_mirror', ref)):
                for fl in ('off', 'on'):
                    for c in ('script', 'ours'):
                        a, b = src['%s/%s/tv/%s' % (d, fl, c)], src['%s/%s/mag/%s' % (d, fl, c)]
                        if any(a[k] != b[k] for k in a if k not in ('seconds', 'path', 'exit_params')):
                            msgs.append('%s/%s/%s: chart 1 mag != tv' % (d, fl, c))
        if msgs:
            ok = False
        i_off, i_on = runs['inverted/off/tv/script'], runs['inverted/on/tv/script']
        n_off, n_on = runs['normal/off/tv/script'], runs['normal/on/tv/script']
        _p('  %s: 32 runs; %d == saved by-timeframe results, %d == saved sweep rows; tv / script net: off normal '
           '%+.4f%% inverted %+.4f%% | on normal %+.4f%% inverted %+.4f%%: %s'
           % (os.path.basename(f), nb, ns, n_off['net_pct'], i_off['net_pct'], n_on['net_pct'], i_on['net_pct'],
              'ok' if not msgs else 'FAIL ' + '; '.join(msgs[:4])))
    return ok


# =============================================================================================
# R9 (sceptic): the names of the option
# =============================================================================================
R9_CELLS = (('BTC', '60'), ('XAU', '240'), ('XAU', '60'))


def _run_key(tr, s):
    """A run as comparable data: the trade frame and the summary without its timing."""
    return tr, {k: v for k, v in _clean(dict(s)).items() if k != 'seconds'}


def _same_run(a, b):
    ta, sa = a
    tb, sb = b
    return len(ta) == len(tb) and all(ta[col].equals(tb[col]) for col in ta.columns) and sa == sb


def test_R9_option_names(cells=None):
    """The option can be given by its Pine name `apxInv` or by the replica alias `inv`, in the
    params of run() / prepare() and in the exit params of simulate(): every way of switching it
    on gives the same inverted run (trade list and summary), every way of leaving it off the
    normal run, the two differ, an explicit `inv` wins over `apxInv` (like blkClose over
    apxBlkClose), simulate()'s value wins over prepare()'s, the summary's `inv` says which run
    it is, and a misspelt name is refused. 3 cells x filter on / off."""
    ok = True
    n = 0
    for pair, tf in (cells or R9_CELLS):
        msgs = []
        for flt in (True, False):
            base = {'fgfOn': flt}
            S0 = apex.prepare(pair, tf, base)

            def sim(S, X):
                out, s = apex.simulate(S, X)
                return _run_key(apex.trades_frame(S, out), s)

            def run(p):
                return _run_key(*apex.run(pair, tf, dict(base, **p)))

            want_inv = sim(S0, {'inv': True})
            want_nrm = sim(S0, None)
            if _same_run(want_inv, want_nrm) or len(want_inv[0]) == 0:
                msgs.append('fgf=%s: inverted == normal (nothing to tell apart)' % flt)
            on = (('run apxInv=True', lambda: run({'apxInv': True})),
                  ('run inv=True', lambda: run({'inv': True})),
                  ('run apxInv=False inv=True', lambda: run({'apxInv': False, 'inv': True})),
                  ('prepare apxInv=True, simulate()', lambda: sim(apex.prepare(pair, tf, dict(base, apxInv=True)), None)),
                  ('prepare inv=True, simulate()', lambda: sim(apex.prepare(pair, tf, dict(base, inv=True)), None)),
                  ('simulate apxInv=True', lambda: sim(S0, {'apxInv': True})),
                  ('simulate inv=1', lambda: sim(S0, {'inv': 1})),
                  ('prepare apxInv=False, simulate apxInv=True',
                   lambda: sim(apex.prepare(pair, tf, dict(base, apxInv=False)), {'apxInv': True})))
            off = (('run default', lambda: run({})),
                   ('run apxInv=False', lambda: run({'apxInv': False})),
                   ('run inv=False', lambda: run({'inv': False})),
                   ('run apxInv=True inv=False', lambda: run({'apxInv': True, 'inv': False})),
                   ('simulate apxInv=False', lambda: sim(S0, {'apxInv': False})),
                   ('prepare apxInv=True, simulate inv=False',
                    lambda: sim(apex.prepare(pair, tf, dict(base, apxInv=True)), {'inv': False})),
                   ('prepare inv=True, simulate apxInv=False',
                    lambda: sim(apex.prepare(pair, tf, dict(base, inv=True)), {'apxInv': False})))
            for forms, want, flag in ((on, want_inv, True), (off, want_nrm, False)):
                for name, fn in forms:
                    n += 1
                    try:
                        got = fn()
                    except Exception as e:
                        msgs.append('fgf=%s %s: %r' % (flt, name, e))
                        continue
                    if got[1].get('inv') is not flag:
                        msgs.append('fgf=%s %s: summary inv is %r' % (flt, name, got[1].get('inv')))
                    elif not _same_run(got, want):
                        msgs.append('fgf=%s %s: not the %s run (%d trades vs %d)'
                                    % (flt, name, 'inverted' if flag else 'normal', len(got[0]), len(want[0])))
            for name, fn in (('simulate apxInverted', lambda: apex.simulate(S0, {'apxInverted': True})),
                             ('prepare invert', lambda: apex.prepare(pair, tf, dict(base, invert=True)))):
                n += 1
                try:
                    fn()
                    msgs.append('fgf=%s %s: accepted' % (flt, name))
                except KeyError:
                    pass
        if msgs:
            ok = False
        _p('  %s %-4s: filter on / off x (8 ways on, 7 ways off, 2 misspelt): %s'
           % (pair, tf, 'ok' if not msgs else 'FAIL ' + ' | '.join(msgs[:4])))
    _p('  R9: %d forms' % n)
    return ok


# =============================================================================================
# R10 (sceptic): the mirror is about the signal close, not about the fill
# =============================================================================================
R10_CELLS = (('BTC', '60'), ('XAU', '240'), ('XAU', '60'))
R10_GAP = 0.003                              # 0.3 % of the signal close (the zone stop is > 0.5 % away)


def _gap_probe(inv, setup, kind, c0, ck, o2, x3, lv, rate, fee):
    """One decision with an opening gap, through the real kernel and through pine_ref. 4 bars.
    Bar 0: flat at c0, an optional setup signal (+1 BUY kind / -1 SELL kind, no bracket), filled
    at bar 1's open. Bar 1: flat at ck = the sampled signal candle's close, with the allowed
    signal `kind` and that candle's stop / target lv = (stopB, tgtB, stopS, tgtS). Bar 2: flat
    at o2 (the gapped open, where the order fills). Bar 3: opens at o2, runs to x3 and closes
    back at o2 (last bar). Returns (kernel output with the final state, pine_ref result)."""
    o = np.array([c0, ck, o2, o2])
    h = np.array([c0, ck, o2, max(o2, x3)])
    l = np.array([c0, ck, o2, min(o2, x3)])
    sig_l = np.array([setup == 1, kind == 1, False, False])
    sig_s = np.array([setup == -1, kind == -1, False, False])
    yes = np.ones(4, np.bool_)
    stp_l = np.array([NAN, lv[0], NAN, NAN])
    lim_l = np.array([NAN, lv[1], NAN, NAN])
    stp_s = np.array([NAN, lv[2], NAN, NAN])
    lim_s = np.array([NAN, lv[3], NAN, NAN])
    K = apex._broker(o, h, l, o.copy(), sig_l, sig_s, yes, yes, stp_l, lim_l, stp_s, lim_s,
                     True, rate, fee, apex.INIT_CAPITAL, 1.0, False, 1.0, 0.5,
                     apex.MINTICK, apex.TRAIL_TOL, False, *apex._NO_SUB, 8, 0, True, inv, True)
    V = dict(o=o.tolist(), h=h.tolist(), l=l.tolist(), c=o.tolist(), bull=sig_l.tolist(), bear=sig_s.tolist(),
             buyOk=[True] * 4, sellOk=[True] * 4, stopB=stp_l.tolist(), tgtB=lim_l.tolist(),
             stopS=stp_s.tolist(), tgtS=lim_s.tolist())
    X = dict(inv=inv, blkClose=True, trailOn=False, useTarget=True, path='tv')
    return K, pine_ref(V, X, rate, fee, want_state=True)


def test_R10_bracket_about_signal_close_with_gap(cells=None, nmax=200):
    """The mirrored bracket is taken about the SIGNAL candle's close, whatever the next open is
    (Pine 849-850 / 863-864: 2.0 * close - stopPrice on the signal bar). R3's probes are flat, so
    there the fill equals the close; here the bar after the signal opens 0.3 % away. For every
    sampled signal candle (its close, its own stop / target, its own kind), from flat, from the
    other kind's trade (reversal) and from its own kind's trade (re-send), option ON:
    (a) the entry fills at the gapped open on the side opposite to the signal;
    (b) the exit order holds stop == 2.0 * close - stopPrice and limit == 2.0 * close -
        targetPrice bit for bit (close = the signal candle's), not the mirror about the fill;
    (c) gap towards the stop: a move that reaches the stop mirrored about the close but not yet
        the one mirrored about the fill ends the trade there (`sl` at that exact price); gap
        away from the stop: a move that passes the level mirrored about the fill but stays
        short of the one about the close does NOT end it;
    (d) the kernel equals the Pine transcription (trades and final state).
    Option OFF as a control: the exit order holds the candle's stopPrice / targetPrice."""
    ok = True
    t0 = time.time()
    nprobe = nsl = nhold = 0
    for pair, tf in (cells or R10_CELLS):
        S = apex.prepare(pair, tf, {'fgfOn': False})
        rate, fee = apex.cost_rates(pair, 'tv' if pair == 'BTC' else 'ours')
        rng = np.random.default_rng(10)
        bars = np.flatnonzero(S['sig_l'] | S['sig_s'])
        if len(bars) > nmax:
            bars = np.sort(rng.choice(bars, nmax, replace=False))
        fails = 0
        first = None
        for k in bars.tolist():
            ck = float(S['c'][k])
            c0 = ck * 1.0005
            kind = 1 if S['sig_l'][k] else -1
            lv = (float(S['stp_l'][k]), float(S['lim_l'][k]), float(S['stp_s'][k]), float(S['lim_s'][k]))
            stop0, tgt0 = (lv[0], lv[1]) if kind == 1 else (lv[2], lv[3])
            sm = 2.0 * ck - stop0                 # the Pine's apxStopBuy / apxStopSell
            tm = 2.0 * ck - tgt0
            d = -kind                             # real side of the inverted trade
            g = R10_GAP * ck
            if not (abs(ck - stop0) > 1.5 * g):
                continue                          # (never on the sampled data: the zone stop is > 0.5 % away)
            for setup in (0, -kind, kind):
                for toward in (True, False):
                    # the stop of a real side d is on the side -d of the price
                    o2 = ck - d * g if toward else ck + d * g
                    x3 = sm - 0.5 * d * g if toward else sm + d * g
                    err = None
                    K, ref = _gap_probe(True, setup, kind, c0, ck, o2, x3, lv, rate, fee)
                    nprobe += 1
                    a = dict(zip(apex.STATE_KEYS, K[14][4:].tolist()))
                    pre = 'xl' if d > 0 else 'xs'
                    if len(K[0]) == 0 or int(K[0][-1]) != d:
                        err = 'the last trade is not on the opposite side of the signal'
                    elif setup != kind and (int(K[1][-1]) != 2 or float(K[2][-1]) != o2):
                        err = 'entry not at the gapped open'
                    elif not (a[pre + '_stop'] == sm and a[pre + '_limit'] == tm):
                        err = 'exit order %r / %r, wanted 2*close - x = %r / %r' % (a[pre + '_stop'], a[pre + '_limit'], sm, tm)
                    elif a[pre + '_stop'] == 2.0 * o2 - stop0:
                        err = 'the probe cannot tell the close from the fill'
                    elif toward and not (apex._KINDS[K[6][-1]] == 'sl' and float(K[5][-1]) == sm and int(K[4][-1]) == 3):
                        err = 'gap towards the stop: exit %s at %r on bar %d, wanted sl at %r on bar 3' \
                              % (apex._KINDS[K[6][-1]], float(K[5][-1]), int(K[4][-1]), sm)
                    elif not toward and apex._KINDS[K[6][-1]] != 'end':
                        err = 'gap away from the stop: exit %s at %r, wanted none' % (apex._KINDS[K[6][-1]], float(K[5][-1]))
                    else:
                        err = _ref_error(K, ref)
                        if err:
                            err = 'vs Pine transcription: ' + err
                    if err is None:
                        nsl += toward
                        nhold += not toward
                        # control: the option off keeps the candle's own bracket
                        N, refn = _gap_probe(False, setup, kind, c0, ck, o2, x3, lv, rate, fee)
                        b = dict(zip(apex.STATE_KEYS, N[14][4:].tolist()))
                        pn = 'xl' if kind > 0 else 'xs'
                        if not (b[pn + '_stop'] == stop0 and b[pn + '_limit'] == tgt0 and int(N[0][-1]) == kind):
                            err = 'option off: exit order %r / %r, wanted %r / %r' % (b[pn + '_stop'], b[pn + '_limit'], stop0, tgt0)
                        else:
                            err = _ref_error(N, refn)
                            if err:
                                err = 'option off vs Pine transcription: ' + err
                    if err:
                        fails += 1
                        if first is None:
                            first = 'bar %d kind %d setup %d toward=%s: %s' % (k, kind, setup, toward, err)
        if fails:
            ok = False
        _p('  %s %-4s: %d signal candles x 3 starting positions x 2 gaps: %d failures%s'
           % (pair, tf, len(bars), fails, '' if first is None else ' | first: ' + first))
    _p('  R10: %d gap decisions with the option on (%d stopped at the level mirrored about the close, %d correctly not '
       'stopped), each also with the option off (%.0fs)' % (nprobe, nsl, nhold, time.time() - t0))
    return ok and nsl > 100 and nhold > 100 and nsl + nhold == nprobe


# =============================================================================================
# R11 (sceptic): the side restriction of the filter acts on the SIGNAL's side
# =============================================================================================
R11_CELLS = (('BTC', '60'), ('XAU', '60'), ('BTC', '15'), ('XAU', '240'), ('BTC', '240'), ('XAU', '15'))


def test_R11_allow_one_side(cells=None):
    """Header of Update 1: "The filter's Allow buys / Allow sells keep meaning the SIGNAL's side:
    Allow buys off blocks the BUY signals, i.e. the SELL orders placed when inverted (only BUY
    entries are left); Allow sells off the reverse." With fgfAllowBuy off: every BUY signal is
    blocked; the normal run holds only real SHORTS and the inverted run only real LONGS, each
    opened by an allowed SELL signal; a blocked BUY signal closes the trade of the SELL kind
    (`blocked_close`, apxBlkClose on: exactly at the open after each blocked BUY signal met
    while that trade is open) and no trade is reversed. fgfAllowSell off: mirrored. 6 cells,
    tv path."""
    ok = True
    tot = {'runs': 0, 'trades': 0, 'blocked_close': 0}
    for pair, tf in (cells or R11_CELLS):
        msgs = []
        line = []
        for off_side, pname in ((1, 'fgfAllowBuy'), (-1, 'fgfAllowSell')):
            S = apex.prepare(pair, tf, {'fgfOn': True, pname: False})
            sig_off = S['sig_l'] if off_side == 1 else S['sig_s']          # the signals of the side switched off
            ok_off = S['buy_ok'] if off_side == 1 else S['sell_ok']
            sig_on = S['sig_s'] if off_side == 1 else S['sig_l']
            ok_on = S['sell_ok'] if off_side == 1 else S['buy_ok']
            if ok_off.any():
                msgs.append('%s off: the gate still allows that side on %d bars' % (pname, int(ok_off.sum())))
            blocked = S['blocked_long'] if off_side == 1 else S['blocked_short']
            raw = S['raw_long'] if off_side == 1 else S['raw_short']
            if blocked != raw:
                msgs.append('%s off: %d of %d signals of that side blocked' % (pname, blocked, raw))
            for inv in (False, True):
                out, s = apex.simulate(S, {'inv': inv}, want_curves=True)
                t_dir, t_eb, t_xb, t_kind, t_sigb = out[0], out[1], out[4], out[6], out[10]
                tot['runs'] += 1
                tot['trades'] += len(t_dir)
                want_dir = -off_side if not inv else off_side     # normal: the other side only; inverted: flipped
                if len(t_dir) == 0:
                    msgs.append('%s off inv=%s: no trades' % (pname, inv))
                    continue
                if not (t_dir == want_dir).all():
                    msgs.append('%s off inv=%s: %d trades on the wrong real side' % (pname, inv, int((t_dir != want_dir).sum())))
                if not (sig_on[t_sigb] & ok_on[t_sigb]).all():
                    msgs.append('%s off inv=%s: a trade without an allowed signal of the other kind' % (pname, inv))
                if (s['long'], s['short']) != ((len(t_dir), 0) if want_dir > 0 else (0, len(t_dir))):
                    msgs.append('%s off inv=%s: summary long / short %d / %d' % (pname, inv, s['long'], s['short']))
                if s['exit_reverse'] != 0:
                    msgs.append('%s off inv=%s: %d reversals with one side off' % (pname, inv, s['exit_reverse']))
                # blocked closes: exactly the blocked signals of the off side met while the trade is open
                posc = out[12]
                n = len(posc)
                kb = np.flatnonzero(sig_off & (posc == want_dir))
                want_close = set(int(k) + 1 for k in kb if k < n - 1)
                got_close = set(int(x) for x, kd in zip(t_xb, t_kind) if kd == apex.K_BLK)
                tot['blocked_close'] += len(got_close)
                if want_close != got_close:
                    msgs.append('%s off inv=%s: blocked closes %d, expected %d' % (pname, inv, len(got_close), len(want_close)))
                line.append('%s off %s: %d %s' % ('buys' if off_side == 1 else 'sells', 'inverted' if inv else 'normal',
                                                  len(t_dir), 'long' if want_dir > 0 else 'short'))
        if msgs:
            ok = False
        _p('  %s %-4s: %s: %s' % (pair, tf, ', '.join(line), 'ok' if not msgs else 'FAIL ' + ' | '.join(msgs[:3])))
    _p('  R11: %s' % tot)
    if cells is not None:                    # a reduced run (R8): no coverage thresholds
        return ok and tot['trades'] > 0
    return ok and tot['trades'] > 500 and tot['blocked_close'] > 50


# =============================================================================================
# R8 (extra): the tests have teeth (mutants of the new script step and of the plumbing)
# =============================================================================================
_GATE_SWAP = (('go_l = sl_k and buy_ok[k]', 'go_l = sl_k and (sell_ok[k] if inv else buy_ok[k])'),
              ('go_s = ss_k and sell_ok[k]', 'go_s = ss_k and (buy_ok[k] if inv else sell_ok[k])'),
              ('bk_l = sl_k and not buy_ok[k]', 'bk_l = sl_k and not (sell_ok[k] if inv else buy_ok[k])'),
              ('bk_s = ss_k and not sell_ok[k]', 'bk_s = ss_k and not (buy_ok[k] if inv else sell_ok[k])'))
_FOUR = (('xs_s = 2.0 * c[k] - stp_l[k]', 'xs_s = %s'), ('xs_l = 2.0 * c[k] - lim_l[k]', 'xs_l = %s'),
         ('xl_s = 2.0 * c[k] - stp_s[k]', 'xl_s = %s'), ('xl_l = 2.0 * c[k] - lim_s[k]', 'xl_l = %s'))


def _four(*exprs):
    return tuple((old, new % e) for (old, new), e in zip(_FOUR, exprs))


# (name, ((old, new), ...) each `old` occurring exactly once in apex.py, the checks that MUST catch it)
MUTANTS = (
    ('m1 blocked close reads the REAL position',
     (('if blk_close and bk_s and posn > 0:', 'if blk_close and bk_s and pos > 0:'),), ('R3',)),
    ('m2 BUY-signal stop not mirrored',
     (('xs_s = 2.0 * c[k] - stp_l[k]', 'xs_s = stp_l[k]'),), ('R3',)),
    ('m3 SELL-signal target not mirrored',
     (('xl_l = 2.0 * c[k] - lim_s[k]', 'xl_l = lim_s[k]'),), ('R3',)),
    ('m4 same-kind re-send reads the REAL position',
     (('if go_l or (sl_k and posn > 0):', 'if go_l or (sl_k and pos > 0):'),), ('R3',)),
    ('m5 trailing ticks fixed on the REAL position',
     (('if posn <= 0:', 'if pos <= 0:'),), ('R3',)),
    ('m6 blocked close names the other id',
     (('pend[npend] = 2 * side_b;', 'pend[npend] = -2 * side_b;'),), ('R3',)),
    ('m7 BUY-signal entry not flipped',
     (('pend[npend] = side_b;', 'pend[npend] = 1;'),), ('R3',)),
    ('m8 inverted exit takes the other signal kind\'s trailing ticks',
     (('xs_tp = trp_l', 'xs_tp = trp_s'),), ('R3',)),
    # added by the sceptic review
    ('m9 gate of the OTHER side when inverted (= the flip before the gate)', _GATE_SWAP, ('R2b', 'R3', 'R5', 'R11')),
    ('m10 position read not mirrored at all (apxPosN = position_size)',
     (('            posn = -pos\n', '            posn = pos\n'),), ('R2b', 'R3', 'R5')),
    ('m11 bracket mirrored about the FILL (next open), not the signal close',
     _four('2.0 * o[k + 1] - stp_l[k]', '2.0 * o[k + 1] - lim_l[k]', '2.0 * o[k + 1] - stp_s[k]', '2.0 * o[k + 1] - lim_s[k]'),
     ('R2b', 'R5', 'R10')),
    ('m12 bracket distances measured from the fill (open + close - x)',
     _four('o[k + 1] + c[k] - stp_l[k]', 'o[k + 1] + c[k] - lim_l[k]', 'o[k + 1] + c[k] - stp_s[k]', 'o[k + 1] + c[k] - lim_s[k]'),
     ('R2b', 'R5', 'R10')),
    ('m13 stop and target swap roles instead of being mirrored',
     _four('lim_l[k]', 'stp_l[k]', 'lim_s[k]', 'stp_s[k]'), ('R2b', 'R3', 'R5', 'R10')),
    ('m14 both blocked closes keep the normal ids',
     (('pend[npend] = 2 * side_b;', 'pend[npend] = 2;'), ('pend[npend] = -2 * side_b;', 'pend[npend] = -2;')),
     ('R2b', 'R3', 'R5')),
    ('m15 SELL-signal entry not flipped',
     (('pend[npend] = -side_b;', 'pend[npend] = -1;'),), ('R2b', 'R3', 'R5')),
    ('m16 the trade list reports the NORMAL side',
     (('return (t_dir[:nt], t_eb[:nt]', 'return (t_dir[:nt] * (-1 if inv else 1), t_eb[:nt]'),), ('R2b', 'R5')),
    ('m17 trail points and trail offset swapped on the inverted exits',
     (('                xs_tp = trp_l\n                xs_to = tro_l\n', '                xs_tp = tro_l\n                xs_to = trp_l\n'),
      ('                xl_tp = trp_s\n                xl_to = tro_s\n', '                xl_tp = tro_s\n                xl_to = trp_s\n')),
     ('R3', 'R5')),
    ('m18 the Pine name apxInv is ignored by run() / prepare()',
     (("('useTarget', 'apxUseTarget'), ('inv', 'apxInv')):", "('useTarget', 'apxUseTarget')):"),), ('R9',)),
    ('m19 simulate() refuses the Pine name apxInv',
     (("'apxUseTarget': 'useTarget', 'apxBlkClose': 'blkClose', 'apxInv': 'inv'}",
       "'apxUseTarget': 'useTarget', 'apxBlkClose': 'blkClose'}"),), ('R9',)),
    ('m20 apxInv wins over an explicit inv',
     (("        if P[rep] is None:\n            P[rep] = P[pine]\n",
       "        if P[rep] is None or (rep == 'inv' and P[pine]):\n            P[rep] = P[pine]\n"),), ('R9',)),
)


def _load_mutant(i, reps):
    src = open(os.path.join(W, 'apex.py')).read()
    txt = src
    for old, new in reps:
        if txt.count(old) != 1:
            raise RuntimeError('mutation target %r occurs %d times in apex.py' % (old, txt.count(old)))
        txt = txt.replace(old, new)
    d = os.path.join(W, 'inv_apex_mut')
    os.makedirs(d, exist_ok=True)
    f = os.path.join(d, 'apex_m%d.py' % i)
    txt = ('# MUTANT %d of apex.py, written by inv_tests_apex.py (test R8): DELIBERATELY WRONG, never use it.\n'
           '# Changed: %s\n' % (i, ' | '.join('%r -> %r' % r for r in reps))) + txt
    if not (os.path.exists(f) and open(f).read() == txt):     # keep the file (and its numba cache) if unchanged
        with open(f, 'w') as fh:
            fh.write(txt)
    spec = importlib.util.spec_from_file_location('apex_inv_mut%d' % i, f)
    m = importlib.util.module_from_spec(spec)
    sys.modules['apex_inv_mut%d' % i] = m
    spec.loader.exec_module(m)
    while d in sys.path:
        sys.path.remove(d)
    m.DATA = apex.DATA
    m._CACHE = apex._CACHE            # same data / signals / gates: only the broker differs
    return m


def _quick_checks():
    """Reduced R2b / R3 / R5 / R9 / R10 / R11 (BTC 60 and XAU 60), output suppressed. Returns {name: passed}
    (a check that crashes on the mutant counts as failed)."""
    import contextlib
    import io
    checks = (
        ('R2b', lambda: test_R2b_inv_equals_normal_kernel_on_relabelled_inputs(cells=[('BTC', '60'), ('XAU', '60')])),
        ('R3', lambda: test_R3_single_decision_mirror(cells=[('BTC', '60')], nsig=25, noth=10)),
        ('R5', lambda: test_R5_reference_pine_head(cells=[('BTC', '60', None, None, 12, 0), ('XAU', '60', None, None, 12, 0)],
                                                   need_kinds=False)),
        ('R9', lambda: test_R9_option_names(cells=[('BTC', '60')])),
        ('R10', lambda: test_R10_bracket_about_signal_close_with_gap(cells=[('BTC', '60')])),
        ('R11', lambda: test_R11_allow_one_side(cells=[('BTC', '60'), ('XAU', '60')])),
    )
    res = {}
    with contextlib.redirect_stdout(io.StringIO()):
        for name, fn in checks:
            try:
                res[name] = bool(fn())
            except Exception:
                res[name] = False
    return res


def test_R8_mutants_are_caught():
    """The tests have teeth: 20 mutants of apex.py (each a plausible mistake of the inverted
    mapping or of its parameter plumbing; written to inv_apex_mut/, never to apex.py) are run
    through reduced versions of R2b (relabelled inputs), R3 (single decisions), R5 (Pine
    reference), R9 (option names), R10 (gap probes) and R11 (one side off) on BTC 60 / XAU 60.
    Control: the real module passes all six. Pass: every mutant fails every check listed for it
    (m1-m8: R3, which enumerates every decision; the bracket-about-the-fill mutants: R10, since
    R3's probes are flat; the plumbing mutants: R9)."""
    global apex
    real = apex
    ok = True
    t0 = time.time()
    base = _quick_checks()
    _p('  control (apex.py as it is): %s' % ', '.join('%s %s' % (k, 'pass' if v else 'FAIL') for k, v in base.items()))
    ok = ok and all(base.values())
    for i, (name, reps, must) in enumerate(MUTANTS, 1):
        try:
            apex = _load_mutant(i, reps)
            res = _quick_checks()
        finally:
            apex = real
        caught = [k for k, v in res.items() if not v]
        good = bool(caught) and all(k in caught for k in must)
        ok = ok and good
        _p('  %-72s caught by: %-22s %s' % (name, ', '.join(caught) or 'NOTHING',
                                           'ok' if good else 'NOT CAUGHT by ' + ', '.join(k for k in must if k not in caught)))
    _p('  R8: %d mutants (%.0fs)' % (len(MUTANTS), time.time() - t0))
    return ok


# =============================================================================================
def main(argv):
    flt = [a for a in argv if not a.startswith('-')]
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith('test_') and callable(f)]
    if flt:
        tests = [(n, f) for n, f in tests if any(x in n for x in flt)]
    res = []
    t00 = time.time()
    for name, fn in tests:
        _p('== %s: %s' % (name, ' '.join((fn.__doc__ or '').split())))
        t0 = time.time()
        try:
            good = bool(fn())
        except Exception as e:               # a crash is a failure, with its traceback
            import traceback
            traceback.print_exc()
            _p('  EXCEPTION %r' % (e,))
            good = False
        res.append((name, good))
        _p('%s %s (%.1fs)' % ('PASS' if good else 'FAIL', name, time.time() - t0))
    _p('')
    _p('summary: %d PASS, %d FAIL (%.0fs)' % (sum(g for _, g in res), sum(not g for _, g in res), time.time() - t00))
    for name, good in res:
        _p('  %s %s' % ('PASS' if good else 'FAIL', name))
    return 0 if res and all(g for _, g in res) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
