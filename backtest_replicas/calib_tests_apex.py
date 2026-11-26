"""calib_tests_apex.py: tests of calib_apex.py (CALIB_SPEC.md, section "The runner", Tests).

Usage: python3 -I calib_tests_apex.py [FILTER ...]
  Runs every test_<name> whose name contains one of the FILTER substrings (none = all), prints
  PASS / FAIL per test, exits non-zero on any failure.

  T1 grid      the grid is the full product of the spec (rebuilt here from the spec's own value
               lists), keys unique, the two lists, the None convention, DIMS; and on data: the
               unused dimensions really cannot change a result.
  T2 default   the row of the script's default setting == the saved default result of the module
               with the same path and cost (out/swah_apex_*.parquet, out/inv_apex_*.json) and a
               fresh apex.run with the module defaults; plus every other saved result the grid
               overlaps (38 trailing-sweep rows, the inverted runs).
  T3 one       30 random rows recomputed one at a time through `calib_apex.py --one` (one
               subprocess each) == the sweep rows; the same rows through apex.run with params
               written here from the row's own columns (Pine names; not the runner's mapping).
  T4 workers   XAU 240: 1 worker (command line) vs 3 workers vs 3 workers in 27 batches:
               identical frames and files; the signal kernel runs once per signal input set, the
               filter permissions once. Columns = p_ columns + result fields only.
  T5 timing    one BTC 1 pass (a signal input set with all its exits) extrapolated to the full
               grid; must stay under 45 minutes with 3 workers; and the memory of that run,
               estimated from the same pass (well under 15 GB).
  T6 files     every out/calib_apex_<PAIR>_<TF>.parquet present: schema, rows == grid, internal
               consistency, the saved results, 30 random rows recomputed, dims JSON; the two
               240-minute files: every row recomputed.
  T7 every row (sceptic review) EVERY row of the XAU 240 sweep and of a second, busier cell (the
               test's own BTC 120 sweep) recomputed with apex.prepare / apex.simulate from the
               row's own p_ columns (parameters written here), not a sample; the second cell also
               against the saved results (default row included) and the internal consistency.
The internal consistency (T4, T6) includes the twin relations that hold whatever the data: a
setting with trades never has the results of its inverted twin; filter-on settings with / without
the blocked close are identical unless a blocked close happened; rrRatio cannot change a setting
whose target is dropped (these rows repeat each other: the grid keeps the spec's full product).

T2 / T3 / T4 / T7 use the test's own sweeps (XAU 240; T7 also BTC 120), written under calib_apex_tmp/, never out/.
At most 2 processes at a time, except the sweep's own 3 workers.
"""
from __future__ import annotations

import glob
import itertools
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import apex  # noqa: E402
import calib_apex as ca  # noqa: E402

OUT = os.path.join(W, 'out')
TMP = os.path.join(W, 'calib_apex_tmp')
CELL = ('XAU', '240')
CELL2 = ('BTC', '120')            # a busier cell for T7 (every setting trades; XAU 240 leaves a third of the grid empty)
LIMIT_S = 45 * 60.0
MEM_LIMIT_MB = 6000              # T5: estimated memory of a BTC 1 run with 3 workers (the machine has 15 GB)

# The grid of CALIB_SPEC.md, written from the spec (not taken from calib_apex)
SPEC_ZL = (10, 20, 30)
SPEC_MB = (0.5, 0.65, 0.8)
SPEC_VM = (1.2, 1.7, 2.2)
SPEC_RR = (1.5, 2.0, 3.0, 5.0)
SPEC_ACT = (0.3, 1.0, 3.0)
SPEC_OFF = (0.2, 0.5, 1.5)
SPEC_NAMES = ('zoneLookback', 'minBodyStr', 'volMultiplier', 'fgfOn', 'blkClose', 'inv', 'rrRatio', 'trailOn',
              'trailAct', 'trailOff', 'useTarget')
SPEC_N = 12312


def _p(*a):
    print(*a, flush=True)


def _spec_keys():
    """{(zoneLookback, minBodyStr, volMultiplier, fgfOn, blkClose, inv, rrRatio, trailOn, trailAct,
    trailOff, useTarget)}: signals x filter {off; on with the blocked close; on without} x direction
    x rrRatio x [trailing off | activation x offset x target kept / dropped]."""
    filters = ((False, None), (True, True), (True, False))
    trails = [(False, None, None, None)] + [(True, a, o, ut) for a in SPEC_ACT for o in SPEC_OFF
                                           for ut in (True, False)]
    K = set()
    for zl, mb, vm, (f, blk), inv, rr, tr in itertools.product(SPEC_ZL, SPEC_MB, SPEC_VM, filters, (False, True),
                                                               SPEC_RR, trails):
        K.add((zl, mb, vm, f, blk, inv, rr) + tr)
    return K


# ----------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------
_COUNT = {'signals': 0}
_GATE = {}                                      # (pair, tf) -> calls of fgf.fgf_permissions
_orig_signals = apex._signals
_orig_perm = apex.fgf.fgf_permissions


def _count_signals(*a, **k):
    _COUNT['signals'] += 1
    return _orig_signals(*a, **k)


def _count_perm(pair, chart_tf, *a, **k):
    _GATE[(pair, str(chart_tf))] = _GATE.get((pair, str(chart_tf)), 0) + 1
    return _orig_perm(pair, chart_tf, *a, **k)


apex._signals = _count_signals                  # counters only: the kernels themselves are untouched
apex.fgf.fgf_permissions = _count_perm

_RUNS = {}


def _sweep(tag, workers, mem_mb=ca.MEM_MB, cell=CELL):
    """The test's own sweep of a cell (XAU 240 unless said; once per tag), in calib_apex_tmp/tests_<tag>/."""
    if tag not in _RUNS:
        d = os.path.join(TMP, 'tests_' + tag)
        ca._drop_signal_cache()                 # signals other tests left in apex's cache
        c0, g0 = _COUNT['signals'], _GATE.get(cell, 0)
        _p('  -- sweep %s %s, %d worker(s), mem budget %d MB -> %s' % (cell[0], cell[1], workers, mem_mb, d))
        df, info = ca.run_cell(cell[0], cell[1], workers=workers, out_dir=d, mem_mb=mem_mb, verbose=False)
        info['count_signals'] = _COUNT['signals'] - c0
        info['count_gate'] = _GATE.get(cell, 0) - g0
        _p('     %d rows in %.1fs (shared %.1fs, signal prep %.1fs, runs %.1fs; workers %.1fs CPU, %.1fs busy wall), '
           '%d batch(es), signal kernel runs %d, filter permission runs %d'
           % (info['rows'], info['total'], info['t_shared'], info['t_prep'], info['t_run'], info['worker_cpu'],
              info['worker_seconds'], info['batches'], info['count_signals'], info['count_gate']))
        _RUNS[tag] = (df, info)
    return _RUNS[tag]


def _rss_mb():
    """Resident memory of this process, MB."""
    with open('/proc/self/status') as fh:
        for line in fh:
            if line.startswith('VmRSS:'):
                return int(line.split()[1]) / 1024.0
    return float('nan')


def _num(v):
    """A saved / JSON value as a number: null -> NaN, 'inf' -> inf."""
    if v is None:
        return float('nan')
    if v == 'inf':
        return float('inf')
    if v == '-inf':
        return float('-inf')
    return v


def _same(a, b):
    a, b = _num(a), _num(b)
    if isinstance(a, (float, np.floating)) and math.isnan(a):
        return isinstance(b, (float, np.floating)) and math.isnan(b)
    return bool(a == b)


def _diff(row, s, cols):
    """Columns of a sweep row that differ from a summary (dict or row)."""
    return ['%s: %r vs %r' % (k, row[k], s[k]) for k in cols if not _same(row[k], s[k])]


def _row_p(row):
    """The p_ values of a frame row as a JSON-able dict (null for unused)."""
    p = {}
    for c in ca.P_COLS:
        v = row[c]
        if v is None or (isinstance(v, (float, np.floating)) and math.isnan(v)):
            p[c] = None
        elif isinstance(v, (bool, np.bool_)):
            p[c] = bool(v)
        elif isinstance(v, (int, np.integer)):
            p[c] = int(v)
        else:
            p[c] = float(v)
    return p


def _direct(pair, tf, row, path, cost):
    """The summary of a row through apex.run, the params written here from the row's own columns
    with the Pine input names (independent of calib_apex.prepare_params / exit_params)."""
    p = _row_p(row)
    prm = {'htfTimeframe': '15', 'zoneLookback': p['p_zoneLookback'], 'minBodyStr': p['p_minBodyStr'],
           'volMultiplier': p['p_volMultiplier'], 'rrRatio': p['p_rrRatio'], 'fgfOn': p['p_fgfOn'],
           'apxInv': p['p_inv'], 'apxTrailOn': p['p_trailOn'], 'path': path, 'cost': cost}
    if p['p_blkClose'] is not None:
        prm['apxBlkClose'] = p['p_blkClose']
    if p['p_trailOn']:
        prm['apxTrailAct'] = p['p_trailAct']
        prm['apxTrailOff'] = p['p_trailOff']
        prm['apxUseTarget'] = p['p_useTarget']
    _, s = apex.run(pair, tf, prm)
    ca._drop_signal_cache()          # a 1-minute cell keeps ~160 MB per signal input set in apex's cache
    return s


def _one_cli(pair, tf, p, extra=(), fail_ok=False):
    cmd = [sys.executable, '-I', os.path.join(W, 'calib_apex.py'), '--one', pair, tf, json.dumps(p)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        if fail_ok:
            return None
        raise RuntimeError('--one failed (%d): %s' % (r.returncode, r.stderr[-1500:]))
    return json.loads(r.stdout)


def _echo_ok(s, pair, tf, row_no, p, path='mag', cost='ours'):
    """The "setting" block of a --one output describes the row that was asked for."""
    e = s['setting']
    return (e == {'strategy': 'apex', 'pair': pair, 'tf': tf, 'path': path, 'cost': cost,
                  'p': {k[2:] if k.startswith('p_') else k: v for k, v in p.items()}, 'in_grid': True, 'row': row_no}
            and s['pair'] == pair and s['tf'] == tf and s['inv'] == e['p']['inv']
            and s['params']['cost'] == cost and s['exit_params']['path'] == path)


def _default_mask(df, **over):
    """Rows whose p_ values are the script's defaults, except the given overrides (None = null)."""
    want = dict(ca.DEFAULT)
    want.update(over)
    m = np.ones(len(df), bool)
    for k, v in want.items():
        c = df['p_' + k]
        m &= c.isna().to_numpy() if v is None else (c == v).fillna(False).to_numpy(bool)
    return m


def _saved_checks(df, pair, tf):
    """Every saved result of the module that the grid overlaps (path mag, cost ours).
    Returns (messages, counts)."""
    msg = []
    n = {'default': 0, 'swah': 0, 'inv': 0, 'chart1': 0}
    d0 = df[_default_mask(df)]
    if len(d0) != 1:
        return ['%d rows with the default setting' % len(d0)], n
    row0 = d0.iloc[0]
    # (a) the trailing sweep of the module: filter x trailing settings at the default signals, rrRatio 3
    f = os.path.join(OUT, 'swah_apex_%s_%s.parquet' % (pair, tf))
    if os.path.exists(f):
        sw = pd.read_parquet(f)
        sw = sw[(sw['path'] == 'mag') & (sw['labels'] == 'normal') & (sw['cost'] == 'ours')]
        cols = [k for k in ca.SUM_COLS if k in sw.columns]
        if len(cols) != len(ca.SUM_COLS):
            msg.append('swah columns: missing %s' % sorted(set(ca.SUM_COLS) - set(cols)))
        s0 = sw[(sw['filter'] == 'on') & (~sw['trailOn']) & (sw['useTarget'])]
        if len(s0) != 1:
            msg.append('swah default rows: %d' % len(s0))
        else:
            bad = _diff(row0, s0.iloc[0], cols)
            n['default'] += 1
            if bad:
                msg.append('DEFAULT row vs swah: ' + '; '.join(bad[:4]))
        sub = df[(df['p_zoneLookback'] == 20) & (df['p_minBodyStr'] == 0.65) & (df['p_volMultiplier'] == 1.7)
                 & (df['p_rrRatio'] == 3.0) & (~df['p_inv']) & (df['p_blkClose'] != False)]   # noqa: E712
        for _, row in sub.iterrows():
            m = (sw['filter'] == ('on' if row['p_fgfOn'] else 'off')) & (sw['trailOn'] == row['p_trailOn'])
            if row['p_trailOn']:
                m &= (sw['trailAct'] == row['p_trailAct']) & (sw['trailOff'] == row['p_trailOff']) \
                    & (sw['useTarget'] == row['p_useTarget'])
            else:
                m &= sw['useTarget']
            s = sw[m]
            if len(s) != 1:
                msg.append('swah: %d rows for row %d' % (len(s), row.name))
                continue
            bad = _diff(row, s.iloc[0], cols)
            n['swah'] += 1
            if bad:
                msg.append('row %d vs swah: %s' % (row.name, '; '.join(bad[:4])))
        if len(sub) != 38:
            msg.append('%d rows overlap the trailing sweep, expected 38' % len(sub))
    else:
        msg.append('no %s' % os.path.basename(f))
    # (b) the inverted-direction runs of the module (default inputs): normal / inverted x filter
    f = os.path.join(OUT, 'inv_apex_%s_%s.json' % (pair, tf))
    if os.path.exists(f):
        runs = json.load(open(f))['runs']
        for dname, inv in (('normal', False), ('inverted', True)):
            for fname, fon in (('off', False), ('on', True)):
                s = runs['%s/%s/mag/ours' % (dname, fname)]
                r = df[_default_mask(df, inv=inv, fgfOn=fon, blkClose=True if fon else None)]
                if len(r) != 1:
                    msg.append('inv json %s/%s: %d rows' % (dname, fname, len(r)))
                    continue
                bad = _diff(r.iloc[0], s, ca.SUM_COLS)
                if s['inv'] != inv or s['params']['fgfOn'] != fon or s['exit_params']['path'] != 'mag':
                    bad.append('the saved run is not %s/%s/mag' % (dname, fname))
                n['inv'] += 1
                if dname == 'normal' and fname == 'on':
                    n['default'] += 1
                if bad:
                    msg.append('%s/%s vs inv json: %s' % (dname, fname, '; '.join(bad[:4])))
    # (c) chart "1": mag == tv, so the saved by-timeframe results (tv path, cost ours) apply too
    f = os.path.join(OUT, 'apex_%s_%s.json' % (pair, tf))
    if tf == '1' and os.path.exists(f):
        sv = json.load(open(f))
        for var, over in (('on', {}), ('off', {'fgfOn': False, 'blkClose': None}), ('on_noblk', {'blkClose': False})):
            s = sv[var]['ours']
            r = df[_default_mask(df, **over)]
            cols = [k for k in ca.SUM_COLS if k in s]
            bad = _diff(r.iloc[0], s, cols) if len(r) == 1 else ['%d rows' % len(r)]
            n['chart1'] += 1
            if bad or len(cols) < 10:
                msg.append('%s vs apex json (%d fields): %s' % (var, len(cols), '; '.join(bad[:4])))
    return msg, n


def _consistency(df, pair, tf):
    """Internal consistency of a frame: schema, keys, grid order, and relations between the p_
    columns and the results that only hold if every row sits next to its own setting."""
    msg = []
    G = ca.grid()
    want_cols = list(ca.P_COLS) + list(ca.SUM_COLS)
    if list(df.columns) != want_cols:
        msg.append('columns %s' % [c for c in set(df.columns) ^ set(want_cols)])
        return msg
    if len(df) != SPEC_N or len(G) != SPEC_N:
        msg.append('%d rows' % len(df))
        return msg
    if not (df.index == np.arange(len(df))).all():
        msg.append('index')
    for k in ca.NAMES:                       # the p_ columns are the grid, in order
        col = df['p_' + k].tolist()
        exp = [c[k] for c in G]
        if not all((e is None and (v is None or (isinstance(v, float) and math.isnan(v)))) or (e is not None and v == e)
                   for v, e in zip(col, exp)):
            msg.append('p_%s != grid()' % k)
    if df[list(ca.P_COLS)].duplicated().any():
        msg.append('duplicated p_ keys')
    for k in ca.SUM_COLS:
        if str(df[k].dtype) != ('float64' if k in ca.FLOAT_COLS else 'int64'):
            msg.append('dtype %s %s' % (k, df[k].dtype))
    for k in ca.NAMES:
        want = {'int64': ('int64',), 'double': ('float64',), 'bool': ('bool', 'object')}[str(ca.P_TYPES[k])]
        if str(df['p_' + k].dtype) not in want:
            msg.append('dtype p_%s %s' % (k, df['p_' + k].dtype))
    w = apex.WINDOWS[pair]
    if not ((df['start'] == w[0]).all() and (df['end'] == w[1]).all() and df['bars'].nunique() == 1):
        msg.append('window columns')
    kinds = ['exit_' + k for k in apex._KINDS]
    if not ((df['trades'] == df['long'] + df['short']).all() and (df['trades'] == df[kinds].sum(axis=1)).all()
            and (df['trades'] == df['h1_trades'] + df['h2_trades']).all()):
        msg.append('trade counts')
    trail = df['p_trailOn'].to_numpy(bool)
    fon = df['p_fgfOn'].to_numpy(bool)
    blk = (df['p_blkClose'] == True).to_numpy(bool)          # noqa: E712
    keep = (df['p_useTarget'] == True).to_numpy(bool)        # noqa: E712
    if (df['exit_trail'][~trail] != 0).any():
        msg.append('trail exits with the trailing off')
    if (df['exit_tp'][trail & ~keep] != 0).any():
        msg.append('target exits with the target dropped')
    if (df['exit_blocked_close'][~(fon & blk)] != 0).any():
        msg.append('blocked closes without filter / switch')
    if (df['exit_time'] != 0).any() or (df['exit_hybrid'] != 0).any() or (df['exit_end'] > 1).any():
        msg.append('exit kinds')
    if (df[['blocked_long', 'blocked_short']][~fon] != 0).any().any():
        msg.append('blocked signals with the filter off')
    sig = ['p_zoneLookback', 'p_minBodyStr', 'p_volMultiplier']
    g = df.groupby(sig)[['raw_long', 'raw_short']].nunique()
    if (g != 1).any().any() or len(g) != 27:
        msg.append('raw signal counts vary inside a signal input set')
    g = df.groupby(sig + ['p_fgfOn'])[['blocked_long', 'blocked_short']].nunique()
    if (g != 1).any().any() or len(g) != 54:
        msg.append('blocked signal counts vary inside a signal setting')
    if ((df['blocked_long'] > df['raw_long']) | (df['blocked_short'] > df['raw_short'])).any():
        msg.append('blocked > raw')
    zero = (df['raw_long'] + df['raw_short'] == 0)
    if (df['trades'][zero] != 0).any() or (df['net_pct'][zero] != 0).any():
        msg.append('trades without signals')
    if ((df['trades'] == 0) & ((df['h1r_pct'] != 0) | (df['h2r_pct'] != 0) | (df['final_equity'] != 1e6))).any():
        msg.append('results without trades')
    msg += _twins(df, G)
    return msg


def _same_rows(R, tw):
    """Rows i whose result columns all equal those of row tw[i] (NaN == NaN)."""
    A, B = R, R[tw]
    return ((A == B) | (np.isnan(A) & np.isnan(B))).all(axis=1)


def _twins(df, G):
    """Relations between a row and its twin (the same setting with one switch flipped) that hold
    whatever the data. G = grid(): the caller has checked that the p_ columns are G, in order.
      (a) normal / inverted: the counts on the SIGNAL's side are the same; with trades the results
          never are (the first trade is entered at the same price on the other side);
      (b) filter on, with / without the blocked close: identical unless a blocked close happened
          (the switch only acts through such a close, and every such close is a trade);
      (c) trailing on with the target dropped: there is no limit order, so rrRatio cannot change
          the result (the 4 rrRatio rows repeat each other; the grid keeps the spec's product)."""
    msg = []
    idx = {tuple(c[k] for k in SPEC_NAMES): i for i, c in enumerate(G)}

    def twin(c, i, **flip):
        return idx[tuple(dict(c, **flip)[k] for k in SPEC_NAMES)]

    R = df[list(ca.SUM_COLS)].to_numpy(dtype=np.float64)
    tr = df['trades'].to_numpy()
    tw = np.array([twin(c, i, inv=not c['inv']) for i, c in enumerate(G)])
    sigc = df[['raw_long', 'raw_short', 'blocked_long', 'blocked_short', 'bars']].to_numpy()
    if (sigc != sigc[tw]).any():
        msg.append('signal counts differ between a setting and its inverted twin')
    n = int((_same_rows(R, tw) & ((tr > 0) | (tr[tw] > 0))).sum())
    if n:
        msg.append('%d settings with trades have the results of their inverted twin' % n)
    tw = np.array([twin(c, i, blkClose=not c['blkClose']) if c['fgfOn'] else i for i, c in enumerate(G)])
    nb = df['exit_blocked_close'].to_numpy()
    n = int(((nb == 0) & (nb[tw] == 0) & ~_same_rows(R, tw)).sum())
    if n:
        msg.append('%d settings differ from their blocked-close twin without any blocked close' % n)
    tw = np.array([twin(c, i, rrRatio=SPEC_RR[0]) if c['useTarget'] is False else i for i, c in enumerate(G)])
    n = int((~_same_rows(R, tw)).sum())
    if n:
        msg.append('%d settings without target change with rrRatio' % n)
    return msg


def _every_row(df, pair, tf):
    """Every row of a frame recomputed in this process with apex.prepare / apex.simulate, the
    parameters written here from the row's own p_ columns with the Pine input names (not
    calib_apex.prepare_params / exit_params / layout). An unused dimension (None) gets the Pine
    default on even rows and another value on odd rows. Returns (messages, rows compared)."""
    msg = []
    P = df[list(ca.P_COLS)].to_dict('records')
    R = df[list(ca.SUM_COLS)].to_dict('records')
    cur = S = None
    nbad = 0
    for i, row in enumerate(P):
        p = _row_p(row)
        key = (p['p_zoneLookback'], p['p_minBodyStr'], p['p_volMultiplier'], p['p_fgfOn'], p['p_rrRatio'])
        if key != cur:
            if cur is not None and key[:3] != cur[:3]:
                ca._drop_signal_cache()
            S = apex.prepare(pair, tf, {'htfTimeframe': '15', 'zoneLookback': key[0], 'minBodyStr': key[1],
                                        'volMultiplier': key[2], 'fgfOn': key[3], 'rrRatio': key[4]})
            cur = key
        odd, ton = i % 2 == 1, p['p_trailOn']
        X = {'apxInv': p['p_inv'], 'apxTrailOn': ton, 'path': 'mag', 'cost': 'ours',
             'apxBlkClose': p['p_blkClose'] if p['p_blkClose'] is not None else not odd,
             'apxTrailAct': p['p_trailAct'] if ton else (3.0 if odd else 1.0),
             'apxTrailOff': p['p_trailOff'] if ton else (1.5 if odd else 0.5),
             'apxUseTarget': p['p_useTarget'] if ton else not odd}
        _, s = apex.simulate(S, X)
        bad = _diff(R[i], s, ca.SUM_COLS)
        if s['inv'] != p['p_inv'] or s['exit_params']['path'] != 'mag' or s['params']['cost'] != 'ours':
            bad.append('the run is not the row\'s setting')
        if bad:
            nbad += 1
            if nbad <= 3:
                msg.append('row %d %r: %s' % (i, p, '; '.join(bad[:3])))
    ca._drop_signal_cache()
    if nbad > 3:
        msg.append('%d rows differ' % nbad)
    return msg, len(P)


# ----------------------------------------------------------------------------------------------
# tests
# ----------------------------------------------------------------------------------------------
def test_T1_grid():
    """(1) The grid is the full product described in the spec, keys unique: grid() == the product
    rebuilt here from the spec's value lists (12,312 = 27 signals x 3 filter states x 2 directions
    x 4 rrRatio x 19 trailing settings); the two lists SIGNALS (54) / EXITS (304, 152 with the
    filter off) and grid() = their ordered product; None exactly where a dimension is unused;
    DIMS (names, values, kinds, defaults = the Pine defaults of apex.py); layout() groups;
    setting_from() round trip. On data (XAU 240 and BTC 240, a sample of signal settings): the
    dimensions set to None really cannot change the result, and the listed ones can."""
    ok = True
    G = ca.grid()
    keys = [ca.key_of(c) for c in G]
    spec = _spec_keys()
    good = (len(G) == SPEC_N == len(spec) == 27 * 3 * 2 * 4 * 19 and len(set(keys)) == len(keys)
            and set(keys) == spec and tuple(ca.NAMES) == SPEC_NAMES and all(tuple(c) == SPEC_NAMES for c in G))
    _p('  grid(): %d settings, %d unique keys, spec product %d: %s (missing %d, extra %d)'
       % (len(G), len(set(keys)), len(spec), 'ok' if good else 'FAIL', len(spec - set(keys)), len(set(keys) - spec)))
    ok &= good
    # the two lists
    sig_keys = [tuple(s[k] for k in ('zoneLookback', 'minBodyStr', 'volMultiplier', 'fgfOn')) for s in ca.SIGNALS]
    ex_names = ('blkClose', 'inv', 'rrRatio', 'trailOn', 'trailAct', 'trailOff', 'useTarget')
    ex_on = [tuple(e[k] for k in ex_names) for e in ca.EXITS]
    ex_off = [tuple(e[k] for k in ex_names) for e in ca.exits_for({'fgfOn': False})]
    good = (len(ca.SIGNALS) == 54 == len(set(sig_keys))
            and set(sig_keys) == set(itertools.product(SPEC_ZL, SPEC_MB, SPEC_VM, (False, True)))
            and len(ex_on) == 304 == len(set(ex_on)) and len(ex_off) == 152 == len(set(ex_off))
            and all(e[0] in (True, False) for e in ex_on) and all(e[0] is None for e in ex_off)
            and {e[1:] for e in ex_on} == {e[1:] for e in ex_off}
            and all(set(s) == set(ca.SIGNAL_NAMES) for s in ca.SIGNALS)
            and all(set(e) == set(ca.EXIT_NAMES) for e in ca.EXITS)
            and set(ca.SIGNAL_NAMES) | set(ca.EXIT_NAMES) == set(SPEC_NAMES))
    prod = [dict(s, **e) for s in ca.SIGNALS for e in ca.exits_for(s)]
    good &= [ca.key_of(c) for c in prod] == keys and 27 * (152 + 304) == SPEC_N
    _p('  two lists: %d SIGNAL settings x EXIT settings (%d with the filter on, %d with it off) = %d, '
       'grid() is their ordered product: %s' % (len(ca.SIGNALS), len(ex_on), len(ex_off), len(prod),
                                               'ok' if good else 'FAIL'))
    ok &= good
    # None exactly where unused
    good = all((c['blkClose'] is None) == (not c['fgfOn']) for c in G) \
        and all((c[k] is None) == (not c['trailOn']) for c in G for k in ('trailAct', 'trailOff', 'useTarget')) \
        and all(c[k] is not None for c in G for k in ('zoneLookback', 'minBodyStr', 'volMultiplier', 'fgfOn', 'inv',
                                                       'rrRatio', 'trailOn'))
    n_off = sum(not c['fgfOn'] for c in G)
    n_notrail = sum(not c['trailOn'] for c in G)
    _p('  None: blkClose None on the %d filter-off settings, trailAct / trailOff / useTarget None on the %d '
       'trailing-off settings, nowhere else: %s' % (n_off, n_notrail, 'ok' if good else 'FAIL'))
    ok &= good and n_off == 27 * 152 and n_notrail == 27 * 3 * 2 * 4
    # DIMS
    spec_vals = {'zoneLookback': SPEC_ZL, 'minBodyStr': SPEC_MB, 'volMultiplier': SPEC_VM, 'fgfOn': (False, True),
                 'blkClose': (True, False), 'inv': (False, True), 'rrRatio': SPEC_RR, 'trailOn': (False, True),
                 'trailAct': SPEC_ACT, 'trailOff': SPEC_OFF, 'useTarget': (True, False)}
    spec_kind = {k: ('ordinal' if k in ('zoneLookback', 'minBodyStr', 'volMultiplier', 'rrRatio', 'trailAct',
                                        'trailOff') else 'categorical') for k in SPEC_NAMES}
    good = [d['name'] for d in ca.DIMS] == list(SPEC_NAMES)
    for d in ca.DIMS:
        k = d['name']
        col = [c[k] for c in G]
        real = {v for v in col if v is not None}
        good &= (d['kind'] == spec_kind[k] and len(d['values']) == len(set(d['values']))
                 and set(d['values']) == real == set(spec_vals[k]) and None not in d['values']
                 and (d['kind'] != 'ordinal' or list(d['values']) == sorted(d['values']))
                 and ((None in col) == ('unused_when' in d)))
        if 'unused_when' in d:               # None exactly when the stated switch is in the stated state
            (sw, val), = d['unused_when'].items()
            good &= all((c[k] is None) == (c[sw] == val) for c in G)
    D = apex.DEFAULTS
    pine_default = {'zoneLookback': D['zoneLookback'], 'minBodyStr': D['minBodyStr'], 'volMultiplier': D['volMultiplier'],
                    'fgfOn': D['fgfOn'], 'blkClose': D['apxBlkClose'], 'inv': D['apxInv'], 'rrRatio': D['rrRatio'],
                    'trailOn': D['apxTrailOn'], 'trailAct': None, 'trailOff': None, 'useTarget': None}
    good &= ca.DEFAULT == pine_default and keys.count(ca.key_of(ca.DEFAULT)) == 1 and D['htfTimeframe'] == '15'
    good &= json.loads(json.dumps(ca.DIMS)) == ca.DIMS
    _p('  DIMS: %d dimensions (%s), values == the grid\'s, default setting = the Pine defaults, row %d: %s'
       % (len(ca.DIMS), ', '.join('%s %s[%d]' % (d['name'], d['kind'][:3], len(d['values'])) for d in ca.DIMS),
          keys.index(ca.key_of(ca.DEFAULT)), 'ok' if good else 'FAIL'))
    ok &= good
    # layout: consecutive groups sharing one prepared input
    L = ca.layout()
    good = len(L) == 216 and L[0][2] == 0 and L[-1][3] == len(G) and all(a[3] == b[2] for a, b in zip(L, L[1:]))
    for si, ri, i0, i1 in L:
        pp = ca.prepare_params(G[i0])
        good &= all(ca.prepare_params(G[i]) == pp for i in range(i0, i1)) \
            and pp == dict(ca.SIGNALS[si], rrRatio=ca.RR_RATIO[ri]) and (i1 - i0) == (76 if pp['fgfOn'] else 38)
    good &= len({json.dumps(ca.prepare_params(G[g[2]]), sort_keys=True) for g in L}) == 216
    good &= all(set(ca.prepare_params(c)) <= set(apex.DEFAULTS) for c in G[::97]) \
        and all(set(ca.exit_params(c)) <= set(apex.EXIT_KEYS) for c in G[::97])
    _p('  layout(): %d groups of 38 / 76 consecutive settings, one prepare_params each: %s'
       % (len(L), 'ok' if good else 'FAIL'))
    ok &= good
    # setting_from round trip
    idx = ca.grid_index()
    good = all(ca.setting_from({'p_' + k: v for k, v in c.items()}) == c and idx[ca.key_of(c)] == i
               for i, c in enumerate(G))
    c = dict(G[5])                                   # filter off, trailing on
    good &= ca.setting_from(dict(c, blkClose=float('nan'))) == c and ca.setting_from(dict(c, blkClose=False)) == c
    c2 = dict(G[0])                                  # trailing off: distances ignored
    good &= ca.setting_from(dict(c2, trailAct=9.0, trailOff=9.0, useTarget=False)) == c2
    for bad in ({'p_nope': 1}, {k: v for k, v in G[-1].items() if k != 'blkClose'},
                {k: v for k, v in G[-1].items() if k != 'trailOff'}, dict(G[-1], inv='yes')):
        try:
            ca.setting_from(bad)
            good = False
        except (KeyError, ValueError):
            pass
    _p('  setting_from(): round trip of the %d settings, NaN = None, unused forced to None, bad input refused: %s'
       % (len(G), 'ok' if good else 'FAIL'))
    ok &= good
    # on data: unused dimensions cannot change the result; the listed ones can
    rng = np.random.default_rng(11)
    for pair, tf in (('XAU', '240'), ('BTC', '240')):
        same = diff_blk = diff_ut = n_runs = 0
        bad = []
        for si in sorted(rng.choice(27, 6, replace=False).tolist()):
            sg = ca.SIGNALS[2 * si]
            for fon in (False, True):
                S = apex.prepare(pair, tf, dict(sg, fgfOn=fon, rrRatio=float(rng.choice(SPEC_RR))))
                for inv in (False, True):
                    for tr in ((False, None, None), (True, 0.3, 0.5), (True, 1.0, 0.2)):
                        X = {'inv': inv, 'trailOn': tr[0], 'path': 'mag', 'cost': 'ours'}
                        if tr[0]:
                            X.update(trailAct=tr[1], trailOff=tr[2])

                        def run(**kw):
                            out, s = apex.simulate(S, dict(X, **kw))
                            return out, {k: s[k] for k in ca.SUM_COLS}

                        o1, s1 = run(blkClose=True, useTarget=True)
                        o2, s2 = run(blkClose=False, useTarget=True)
                        n_runs += 2
                        eq_blk = _diff(s1, s2, ca.SUM_COLS) == [] and all(np.array_equal(a, b, equal_nan=True)
                                                                         for a, b in zip(o1[:11], o2[:11]))
                        if not fon:
                            same += 1
                            if not eq_blk:
                                bad.append('filter off: blkClose changes %r' % (X,))
                        else:
                            diff_blk += not eq_blk
                        if not tr[0]:                # trailing off: target switch and distances are dead
                            o3, s3 = run(blkClose=True, useTarget=False, trailAct=float(rng.choice(SPEC_ACT)),
                                         trailOff=float(rng.choice(SPEC_OFF)))
                            n_runs += 1
                            same += 1
                            if _diff(s1, s3, ca.SUM_COLS) or not all(np.array_equal(a, b, equal_nan=True)
                                                                     for a, b in zip(o1[:11], o3[:11])):
                                bad.append('trailing off: useTarget / distances change %r' % (X,))
                        else:
                            o3, s3 = run(blkClose=True, useTarget=False)
                            n_runs += 1
                            diff_ut += bool(_diff(s1, s3, ca.SUM_COLS))
            ca._drop_signal_cache()
        good = not bad and diff_blk > 0 and diff_ut > 0
        _p('  %s %s, 6 signal input sets, %d runs: %d comparisons where a dimension is None: all identical '
           '(summary and trades): %s; where it is listed it does change results (blkClose %d, useTarget %d cases)%s'
           % (pair, tf, n_runs, same, 'ok' if not bad else 'FAIL', diff_blk, diff_ut,
              '' if good else ' FAIL ' + '; '.join(bad[:3])))
        ok &= good
    return ok


def test_T2_default_row():
    """(2) The row of the script's default setting (zoneLookback 20, minBodyStr 0.65, volMultiplier
    1.7, filter on with the blocked close, normal direction, rrRatio 3, trailing off) equals the
    saved default result of the module with the same path (mag) and cost (ours): the row of
    out/swah_apex_XAU_240.parquet (filter on / mag / normal / ours / trailing off), the run
    normal/on/mag/ours of out/inv_apex_XAU_240.json, and a fresh apex.run with the module
    defaults. Also every other saved result the grid overlaps: the 38 rows of the trailing sweep
    (filter off / on x trailing settings) and the 4 runs of the inverted-direction file."""
    pair, tf = CELL
    df, _ = _sweep('w3', 3)
    msg, n = _saved_checks(df, pair, tf)
    row0 = df[_default_mask(df)].iloc[0]
    _, s = apex.run(pair, tf, {'path': 'mag', 'cost': 'ours'})         # the module's own defaults
    bad = _diff(row0, s, ca.SUM_COLS)
    scal = {k for k, v in s.items() if not isinstance(v, dict)}
    missing = scal - set(ca.SUM_COLS) - {'pair', 'tf', 'inv', 'seconds'}
    dicts = {k for k, v in s.items() if isinstance(v, dict)}
    stored_ok = (not missing and set(ca.SUM_COLS) <= scal and dicts == {'exit_kinds', 'params', 'exit_params'}
                 and set(ca.SUM_NOT_STORED) == (set(s) - set(ca.SUM_COLS))
                 and [k for k in s if k in ca.SUM_COLS] == list(ca.SUM_COLS))
    _p('  default row = row %d: trades %d net %.6f%% h1r %.6f%% (%d) h2r %.6f%% (%d) pf %s'
       % (row0.name, row0['trades'], row0['net_pct'], row0['h1r_pct'], row0['h1_trades'], row0['h2r_pct'],
          row0['h2_trades'], row0['pf']))
    _p('  vs saved default (swah parquet + inv json): %d comparisons; vs apex.run defaults (%d fields): %s'
       % (n['default'], len(ca.SUM_COLS), 'ok' if not bad and n['default'] == 2 else 'FAIL ' + '; '.join(bad[:4])))
    _p('  other saved results the grid overlaps: %d trailing-sweep rows, %d inverted-file runs: %s'
       % (n['swah'], n['inv'], 'ok' if not msg else 'FAIL ' + '; '.join(msg[:5])))
    _p('  summary fields: the %d result fields are the columns, in the summary\'s order; not stored, and only '
       'those: %s: %s' % (len(ca.SUM_COLS), ', '.join(ca.SUM_NOT_STORED), 'ok' if stored_ok else 'FAIL %s' % sorted(missing)))
    return not bad and not msg and n['default'] == 2 and n['swah'] == 38 and n['inv'] == 4 and stored_ok


def test_T3_one():
    """(3) 30 random rows of the XAU 240 sweep recomputed one at a time through
    `python3 -I calib_apex.py --one XAU 240 '<json of the row's p_ values>'` (one subprocess per
    row): every summary column equal, the echoed setting and row number equal. The same 30 rows
    through apex.run with params written in this file from the row's columns (Pine input names).
    10 more rows drawn among those with >= 5 trades (the random draw holds many settings without
    signals). --one with --path tv --cost stress / tv == the module called directly; --one
    accepts keys without the p_ prefix."""
    pair, tf = CELL
    df, _ = _sweep('w3', 3)
    rng = np.random.default_rng(20261124)
    picks = sorted(rng.choice(len(df), 30, replace=False).tolist())
    busy = np.flatnonzero(df['trades'].to_numpy() >= 5)
    extra = sorted(rng.choice(busy, 10, replace=False).tolist())
    ok = True
    n_tr = n_inv = n_trail = n_fon = 0
    t0 = time.time()
    for j, i in enumerate(picks + extra):
        row = df.iloc[i]
        p = _row_p(row)
        s = _one_cli(pair, tf, p)
        bad = _diff(row, s, ca.SUM_COLS)
        if not _echo_ok(s, pair, tf, i, p):
            bad.append('echo %r' % (s['setting'],))
        d = _direct(pair, tf, row, 'mag', 'ours')
        bad += ['direct ' + b for b in _diff(row, d, ca.SUM_COLS)]
        if d['inv'] != p['p_inv'] or set(d) - set(s):
            bad.append('direct run: inv / missing fields')
        if bad:
            ok = False
            _p('  FAIL row %d %r: %s' % (i, p, '; '.join(bad[:4])))
        if j < 30:
            n_tr += row['trades'] > 0
            n_inv += bool(row['p_inv'])
            n_trail += bool(row['p_trailOn'])
            n_fon += bool(row['p_fgfOn'])
    _p('  30 random rows (%d with trades, %d inverted, %d trailing on, %d filter on) + 10 rows with >= 5 trades: '
       '--one (subprocess) and apex.run (own params) == the sweep row on %d columns: %s (%.1fs, %.2fs per --one)'
       % (n_tr, n_inv, n_trail, n_fon, len(ca.SUM_COLS), 'ok' if ok else 'FAIL', time.time() - t0,
          (time.time() - t0) / 40))
    # the other views of a pick
    good = True
    for i in extra[:3]:
        row = df.iloc[i]
        for path, cost in (('tv', 'stress'), ('mag', 'stress'), ('tv', 'tv')):
            p = {k[2:]: v for k, v in _row_p(row).items()}             # keys without the prefix
            s = _one_cli(pair, tf, p, ['--path', path, '--cost', cost])
            d = _direct(pair, tf, row, path, cost)
            bad = _diff(s, d, ca.SUM_COLS)
            if bad or not _echo_ok(s, pair, tf, i, p, path, cost) or set(d) - set(s):
                good = False
                _p('  FAIL row %d --path %s --cost %s: %s' % (i, path, cost, '; '.join(bad[:4])))
    _p('  --one --path tv|mag --cost stress|tv on 3 rows (9 runs, keys without the p_ prefix) == apex.run: %s'
       % ('ok' if good else 'FAIL'))
    # off the grid: refused, unless asked
    p = _row_p(df.iloc[extra[0]])
    p['p_rrRatio'] = 2.5
    refused = _one_cli(pair, tf, p, fail_ok=True) is None
    s = _one_cli(pair, tf, p, ['--off-grid'])
    off = (refused and s['setting']['in_grid'] is False and s['setting']['row'] is None
           and s['params']['rrRatio'] == 2.5 and _one_cli(pair, tf, {'p_zoneLookback': 20}, fail_ok=True) is None)
    _p('  a setting off the grid (rrRatio 2.5) is refused, and run with --off-grid; an incomplete one is refused: %s'
       % ('ok' if off else 'FAIL'))
    return ok and good and off


def test_T4_workers():
    """(4) 1 worker vs 3 workers identical on XAU 240: the 1-worker sweep through the command
    line (`calib_apex.py XAU 240 --workers 1 --out-dir ...`), the 3-worker sweep in one batch and
    the 3-worker sweep with a 1 MB budget (27 batches, one signal input set each): identical
    frames and identical parquet / dims files. Signals prepared once per signal input set: 27
    runs of apex._signals for 216 prepared inputs (12,312 settings), the filter permissions once
    (counted by wrappers around apex._signals and fgf.fgf_permissions). Internal consistency of
    the frame. == out/calib_apex_XAU_240.parquet if it exists."""
    pair, tf = CELL
    df3, i3 = _sweep('w3', 3)
    dfb, ib = _sweep('w3_batches', 3, mem_mb=1)
    d1 = os.path.join(TMP, 'tests_w1_cli')
    t0 = time.time()
    r = subprocess.run([sys.executable, '-I', os.path.join(W, 'calib_apex.py'), pair, tf, '--workers', '1',
                        '--out-dir', d1], capture_output=True, text=True)
    t1 = time.time() - t0
    if r.returncode != 0:
        _p('  FAIL 1-worker command line: %s' % r.stderr[-1500:])
        return False
    for line in r.stdout.strip().splitlines():
        _p('  [1 worker, command line] ' + line)
    name = 'calib_apex_%s_%s.parquet' % (pair, tf)
    f1, f3, fb = (os.path.join(d, name) for d in (d1, os.path.join(TMP, 'tests_w3'), os.path.join(TMP, 'tests_w3_batches')))
    df1 = pd.read_parquet(f1)
    eq13 = df1.equals(df3) and pd.read_parquet(f3).equals(df3) and (df1.dtypes == df3.dtypes).all()
    eq3b = df3.equals(dfb)
    by13 = open(f1, 'rb').read() == open(f3, 'rb').read()
    by3b = open(f3, 'rb').read() == open(fb, 'rb').read()
    dims = [json.load(open(os.path.join(os.path.dirname(f), 'calib_apex_dims.json'))) for f in (f1, f3, fb)]
    dims_ok = all(d == ca.DIMS for d in dims)
    _p('  1 worker (%.1fs incl. start) vs 3 workers (%.1fs): frames %s, files byte-identical %s (%d bytes)'
       % (t1, i3['total'], 'identical' if eq13 else 'DIFFER', by13, os.path.getsize(f3)))
    _p('  3 workers, 1 batch vs %d batches (%.1fs): frames %s, files byte-identical %s; dims JSON == DIMS: %s'
       % (ib['batches'], ib['total'], 'identical' if eq3b else 'DIFFER', by3b, dims_ok))
    once = all(i['count_signals'] == 27 == i['signal_runs'] and i['prepared'] == 216 and i['rows'] == SPEC_N
               for i in (i3, ib))
    cli = '27 signal kernel runs, 216 prepared inputs, filter permissions computed 1 time)' in r.stdout
    gate = (_GATE.get(CELL, 0) == 1 and i3['count_gate'] + ib['count_gate'] <= 1
            and i3['gate_runs'] + ib['gate_runs'] <= 1 and cli)
    _p('  signals prepared once per signal input set: %d / %d runs of apex._signals for %d prepared inputs and %d '
       'settings in the two 3-worker sweeps: %s; fgf.fgf_permissions called %d time for %s %s in this whole test '
       'process; the command-line sweep reports 27 signal runs and 1 permission run: %s'
       % (i3['count_signals'], ib['count_signals'], i3['prepared'], i3['rows'], 'ok' if once else 'FAIL',
          _GATE.get(CELL, 0), pair, tf, 'ok' if gate else 'FAIL'))
    cons = _consistency(df3, pair, tf)
    _p('  internal consistency of the frame: %s' % ('ok' if not cons else 'FAIL ' + '; '.join(cons[:5])))
    saved = os.path.join(OUT, name)
    same_out = True
    if os.path.exists(saved):
        same_out = pd.read_parquet(saved).equals(df3)
        _p('  == out/%s: %s' % (name, same_out))
    else:
        _p('  out/%s not written yet' % name)
    return eq13 and eq3b and by13 and by3b and dims_ok and once and gate and not cons and same_out \
        and ib['batches'] == 27 and i3['batches'] == 1


def test_T5_timing_btc1():
    """(5) Timing of one BTC 1 pass extrapolated to the full grid. One pass = one signal input
    set (the default one) with all its settings: its 8 prepared inputs (filter off / on x 4
    rrRatio) and its 456 settings, single process, path mag (chart 1: every bar is its own
    sub-bar), cost ours. Full grid = 27 passes; with 3 workers = shared + 27 x prep (main
    process) + 27 x simulations / 3. Second estimate: calib_apex.estimate_cell (every one of the
    27 signal input sets prepared, 8 random settings of each timed). Both must stay under 45
    minutes: otherwise the grid has to be thinned. Memory (sceptic review): the resident memory of
    this process before / after preparing that signal input set and after its simulations gives the
    estimate of a run with 3 workers (main process + one batch of prepared inputs; the forked
    workers share its pages): must stay well under the machine's 15 GB (measured on the real run by
    the review: 2.75 GB for main + 3 workers, shared pages counted once)."""
    pair, tf = 'BTC', '1'
    G = ca.grid()
    L = ca.layout()
    t0, c0 = time.time(), time.process_time()
    S0 = ca._shared(pair, tf, G, L, 'mag', 'ours')
    n, w1 = len(S0['c']), S0['w1']
    del S0
    ca._drop_signal_cache()
    w_shared, t_shared = time.time() - t0, time.process_time() - c0
    rss0 = _rss_mb()
    tri = ca.SIGNALS.index(dict(zoneLookback=20, minBodyStr=0.65, volMultiplier=1.7, fgfOn=False)) // 2
    t0, c0 = time.time(), time.process_time()
    S = ca._prepare_batch(pair, tf, G, L, [tri], 'mag')
    w_prep, t_prep = time.time() - t0, time.process_time() - c0
    rss1 = _rss_mb()
    groups = [g for g in L if (g[0], g[1]) in S]
    t0, c0 = time.time(), time.process_time()
    n_set = trades = 0
    for si, ri, i0, i1 in groups:
        for i in range(i0, i1):
            _, s = apex.simulate(S[(si, ri)], ca.exit_params(G[i]))
            n_set += 1
            trades += s['trades']
    w_sim, t_sim = time.time() - t0, time.process_time() - c0
    rss2 = _rss_mb()
    S.clear()
    ca._drop_signal_cache()
    # memory of the run with 3 workers, from this one signal input set: the main process holds the
    # shared data and one batch of prepared inputs; the forked workers read its pages (copy-on-write)
    # and only add what the simulations allocate
    batch = len(ca._batches(n, w1, ca.MEM_MB)[0])
    per_set, per_set_runner = rss1 - rss0, ca._triple_bytes(n, w1) / 1e6
    sim_add = max(rss2 - rss1, 0.0)
    mem_est = rss0 + batch * per_set + 3 * sim_add
    mem_ok = mem_est < MEM_LIMIT_MB and per_set < 2.0 * per_set_runner and batch * per_set_runner <= ca.MEM_MB
    est1 = t_shared + 27 * t_prep + 27 * t_sim
    est3 = t_shared + 27 * t_prep + 27 * t_sim / 3.0
    wall3 = w_shared + 27 * w_prep + 27 * w_sim / 3.0            # at the pace of this (shared, busy) machine
    _p('  BTC 1 (%d bars): shared %.1fs CPU (%.1fs wall); one pass = default signal input set: prep %.1fs CPU '
       '(%.1fs wall) + %d settings in %.1fs CPU (%.1fs wall) = %.4fs CPU per setting, %.0f trades per setting'
       % (n, t_shared, w_shared, t_prep, w_prep, n_set, t_sim, w_sim, t_sim / n_set, trades / n_set))
    _p('  extrapolated to the full grid (27 passes, %d settings): %.0fs = %.1f min with 1 process; with 3 workers '
       '%.0fs = %.1f min if each has a core (CPU seconds), %.0fs = %.1f min at the wall-clock pace just measured'
       % (27 * n_set, est1, est1 / 60, est3, est3 / 60, wall3, wall3 / 60))
    _p('  memory (sceptic review): this process holds %.0f MB after the shared preparation; one signal input set '
       'adds %.0f MB (the runner budgets %.0f MB, so %d per batch of <= %d MB); its 456 simulations add %.0f MB. '
       'Run with 3 workers: main %.0f + %d x %.0f MB, workers share its pages and add <= 3 x %.0f MB: about %.0f MB; '
       'must stay well under 15 GB (limit here %d MB): %s'
       % (rss0, per_set, per_set_runner, batch, ca.MEM_MB, sim_add, rss0, batch, per_set, sim_add, mem_est,
          MEM_LIMIT_MB, 'ok' if mem_ok else 'FAIL'))
    e = ca.estimate_cell(pair, tf, n_per=8, verbose=False)
    _p('  sampled over all 27 signal input sets (%d settings timed): shared %.1fs + signal prep %.1fs + '
       'simulations %.0fs CPU (%.4fs per setting, %.4f..%.4f by signal input set) -> %.0fs = %.1f min with 3 workers'
       % (e['sampled'], e['t_shared'], e['t_prep'], e['sim_cpu'], e['per_setting'], e['per_setting_min'],
          e['per_setting_max'], e['est_wall'], e['est_wall'] / 60))
    slow = e['measured_in'] / max(e['measured_cpu'], 1e-9)       # wall / CPU while measuring (machine load)
    worst = max(est3, wall3, (t_shared + e['t_prep'] + e['sim_cpu'] / 3.0) * slow,
                (t_shared + e['t_prep'] + 27 * 456 * e['per_setting_max'] / 3.0) * slow)
    ok = n_set == 456 and worst < LIMIT_S and mem_ok
    _p('  worst case: every setting at the slowest signal input set\'s pace, times the wall / CPU ratio of this '
       'measurement (%.2f): %.1f min; limit 45 min: %s (the grid is not thinned)'
       % (slow, worst / 60, 'ok' if ok else 'FAIL: thin the grid'))
    return ok


def test_T6_files():
    """Every out/calib_apex_<PAIR>_<TF>.parquet present (none before the first run): schema and
    dtypes, rows == grid() in order, unique keys, internal consistency (trade counts, exit kinds
    against the switches, signal counts per signal setting), the saved results of the module the
    grid overlaps (default row included), 30 random rows + 10 rows with trades recomputed with
    apex.run from the row's own columns, 2 rows through `--one`; out/calib_apex_dims.json == DIMS.
    The two 240-minute files (small cells): EVERY row recomputed (as T7)."""
    files = sorted(glob.glob(os.path.join(OUT, 'calib_apex_*_*.parquet')))
    if not files:
        _p('  no out/calib_apex_<PAIR>_<TF>.parquet yet: nothing to check')
        return True
    ok = True
    fd = os.path.join(OUT, 'calib_apex_dims.json')
    good = os.path.exists(fd) and json.load(open(fd)) == ca.DIMS
    _p('  out/calib_apex_dims.json == DIMS: %s' % ('ok' if good else 'FAIL'))
    ok &= good
    rng = np.random.default_rng(5)
    for f in files:
        df = pd.read_parquet(f)
        pair, tf = os.path.basename(f)[:-len('.parquet')].split('_')[2:4]
        msg = _consistency(df, pair, tf)
        n = {'default': 0, 'swah': 0, 'inv': 0, 'chart1': 0}
        n_re = n_all = 0
        if not msg:
            m2, n = _saved_checks(df, pair, tf)
            msg += m2
            if tf == '240':                      # small cells: every row, not a sample
                m3, n_all = _every_row(df, pair, tf)
                msg += ['every row: ' + m for m in m3]
            picks = rng.choice(len(df), 30, replace=False).tolist()
            busy = np.flatnonzero(df['trades'].to_numpy() >= 5)
            picks += rng.choice(busy, min(10, len(busy)), replace=False).tolist()
            for i in sorted(picks):
                row = df.iloc[i]
                bad = _diff(row, _direct(pair, tf, row, 'mag', 'ours'), ca.SUM_COLS)
                n_re += 1
                if bad:
                    msg.append('row %d: %s' % (i, '; '.join(bad[:3])))
            ca._drop_signal_cache()
            for i in picks[-2:]:
                row = df.iloc[i]
                s = _one_cli(pair, tf, _row_p(row))
                bad = _diff(row, s, ca.SUM_COLS)
                if bad or not _echo_ok(s, pair, tf, i, _row_p(row)):
                    msg.append('--one row %d: %s' % (i, '; '.join(bad[:3])))
        cand = int(((df['h1r_pct'] > 0) & (df['h2r_pct'] > 0) & (df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).sum())
        _p('  %s: %d rows, %d with trades, %d distinct results; saved results: default %d, trailing sweep %d, '
           'inverted file %d, chart-1 file %d; %d rows recomputed%s; [rows positive in both halves with >= 30 trades '
           'each: %d]: %s'
           % (os.path.basename(f), len(df), int((df['trades'] > 0).sum()),
              len(df[[c for c in df.columns if not c.startswith('p_')]].drop_duplicates()), n['default'], n['swah'],
              n['inv'],
              n['chart1'], n_re, ' + every row (%d)' % n_all if n_all else '', cand,
              'ok' if not msg else 'FAIL ' + '; '.join(msg[:5])))
        ok &= not msg
    return ok


def test_T7_every_row():
    """(sceptic review) EVERY row, not a sample, on two cells: the XAU 240 sweep and the test's own
    sweep of a second, busier cell (BTC 120, 3 workers: every setting trades there, while XAU 240
    leaves a third of the grid without a trade and whole regions where a switch changes nothing,
    e.g. the target at rrRatio 5). The 12,312 settings of each are recomputed in this process with
    apex.prepare / apex.simulate, the parameters written in this file from the row's own p_
    columns (Pine input names; an unused dimension gets the Pine default on even rows and another
    value on odd rows): all 33 result columns equal on every row. The second cell also passes
    the internal consistency and the saved results of the module (its default row has 26 trades;
    XAU 240's has 2). Why: T3 / T6 draw 40 rows per cell, so a mapping error confined to a few
    hundred settings can escape them (the review's mutants narrow_usetarget, narrow_rr_work,
    narrow_inv did)."""
    ok = True
    for tag, cell in (('w3', CELL), ('w3_cell2', CELL2)):
        pair, tf = cell
        df, info = _sweep(tag, 3, cell=cell)
        t0 = time.time()
        msg, n = _every_row(df, pair, tf)
        good = not msg and n == SPEC_N
        _p('  %s %s: %d rows (%d with trades, %d distinct results, %d inverted, %d filter on without the blocked '
           'close) recomputed with apex.prepare / apex.simulate from their own p_ columns in %.1fs: %s'
           % (pair, tf, n, int((df['trades'] > 0).sum()), len(df[list(ca.SUM_COLS)].drop_duplicates()),
              int(df['p_inv'].sum()), int((df['p_blkClose'] == False).sum()),                   # noqa: E712
              time.time() - t0, 'all %d result columns equal on every row' % len(ca.SUM_COLS) if good
              else 'FAIL ' + '; '.join(msg[:4])))
        ok &= good
        if cell != CELL:
            cons = _consistency(df, pair, tf)
            m2, k = _saved_checks(df, pair, tf)
            row0 = df[_default_mask(df)].iloc[0]
            good = (not cons and not m2 and k['default'] == 2 and k['swah'] == 38 and k['inv'] == 4
                    and info['count_signals'] == 27 == info['signal_runs'] and info['prepared'] == 216
                    and info['count_gate'] <= 1 and info['gate_runs'] <= 1)
            _p('  %s %s: internal consistency %s; default row (%d trades, net %.6f%%) == the saved default result '
               '(%d comparisons), %d trailing-sweep rows, %d inverted-file runs: %s; %d signal kernel runs for %d '
               'prepared inputs: %s' % (pair, tf, 'ok' if not cons else 'FAIL ' + '; '.join(cons[:4]),
                                        row0['trades'], row0['net_pct'], k['default'], k['swah'], k['inv'],
                                        'ok' if not m2 else 'FAIL ' + '; '.join(m2[:4]), info['count_signals'],
                                        info['prepared'], 'ok' if good else 'FAIL'))
            ok &= good
    return ok


def main(argv):
    flt = [a for a in argv if not a.startswith('-')]
    names = sorted(k for k, v in globals().items() if k.startswith('test_') and callable(v))
    if flt:
        names = [k for k in names if any(f in k for f in flt)]
    if not names:
        _p('no tests match %s' % flt)
        return 2
    res = {}
    t00 = time.time()
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
    _p('\nsummary: %d PASS, %d FAIL (%.0fs)' % (sum(res.values()), len(res) - sum(res.values()), time.time() - t00))
    for k, r in res.items():
        _p('  %s %s' % ('PASS' if r else 'FAIL', k))
    return 0 if all(res.values()) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
