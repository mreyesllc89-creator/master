"""calib_apex.py: calibration grid of ApexForge Flow Resonance + FGF per pair and timeframe,
with the direction (Normal / Inverted, Update 1) as a calibrated input (CALIB_SPEC.md), on the
canonical replica apex.py.

Usage (python3 -I):
    calib_apex.py PAIR TF [TF ...] [--workers 3] [--mem-mb 1000] [--out-dir DIR]
        runs the whole grid on each cell and writes out/calib_apex_<PAIR>_<TF>.parquet (one row
        per setting) and out/calib_apex_dims.json (DIMS). Safe to re-run (overwrites; each file
        is written under a temporary name first).
    calib_apex.py --one PAIR TF '<json of p_ values>' [--path tv|mag] [--cost tv|ours|stress]
                  [--off-grid]
        prints the full summary of ONE setting as JSON (one object on stdout, nothing else):
        every field of apex.simulate's summary, plus "setting" = {strategy, pair, tf, path, cost,
        p (the canonical p_ values), in_grid, row (its row number in the grid file)}. Python's
        json: NaN / Infinity for a pf or win_pct without trades / without a losing trade. The
        JSON of p_ values is a row's p_ columns: keys with or without the "p_" prefix, null (or
        NaN) for an unused dimension. --off-grid also accepts values that are not in the grid.
    calib_apex.py --estimate [PAIR [TF ...]] [--samples 12]
        single process, no file written: times every signal setting and a sample of its exit
        settings, and prints the estimated time of the full grid of each cell.

Grid: 12,312 settings per cell, defined as two lists.
  SIGNALS (54; what apex.prepare needs for the signals and the filter permissions):
      zoneLookback {10, 20, 30} x minBodyStr {0.5, 0.65, 0.8} x volMultiplier {1.2, 1.7, 2.2}
      x fgfOn {False, True}                                    (htfTimeframe stays "15")
  EXITS (304 with the filter on; orders and exits):
      rrRatio {1.5, 2, 3, 5} x blkClose {True, False} x inv {False, True}
      x [trailing off | trailing on with trailAct {0.3, 1, 3} % x trailOff {0.2, 0.5, 1.5} %
         x useTarget {True (target kept), False (dropped)}]    (19 trailing settings)
  A combination that cannot differ from another is listed once, the unused dimensions = None:
      fgfOn False  -> blkClose None (nothing is ever blocked): 152 exits instead of 304;
      trailOn False -> trailAct, trailOff, useTarget None (the Pine keeps the target whatever
                       "Keep the target" says when the trailing is off).
  27 x (152 + 304) = 12,312. grid() lists them in a fixed order (signal setting, then its
  exits): row i of the file is grid()[i].
  NOT folded (the spec counts the full product rrRatio x trailing settings): with the trailing on
  and the target dropped there is no limit order, so rrRatio cannot change the result either: the
  4 rrRatio rows of such a setting are identical (4,374 of the 12,312 rows repeat another row this
  way, in every cell). Rule C counts identical results once; calib_tests_apex.py checks the rows
  are identical.
DIMS describes the 11 swept dimensions (name, values, kind ordinal / categorical; extra keys:
side, default = the script's default, unused_when = when the value is None).

Scoring: every setting with path 'mag' (1-minute Bar Magnifier fills; chart "1": each chart bar
is its own sub-bar, = 'tv') and cost 'ours'.

How it runs. rrRatio is an exit of the strategy, but apex.py builds the target arrays in
prepare(): the runner calls apex.prepare once per (signal setting, rrRatio), and the module
serves these calls from its own caches, so the signal kernel runs ONCE per (zoneLookback,
minBodyStr, volMultiplier) (27 times per cell) and the filter permissions ONCE per cell
(counted by the runner and printed: info['signal_runs'], info['gate_runs']); every exit setting
of a signal setting reuses them. The main process prepares the inputs of a batch of signal settings
(as many as fit the memory budget, --mem-mb), then forks at most 3 workers (copy-on-write) that
simulate the batch's settings; the batch is then freed (including apex's signal cache). Rows
are written in grid order, so the file does not depend on the worker count or the batch size.

Output columns: one p_<name> per dimension, in DIMS order (null = None), then every result
field of the summary of apex.simulate, in its order: start, end, bars, trades, net_pct, pf,
win_pct, max_dd_pct, long, short (REAL sides), raw_long, raw_short, blocked_long, blocked_short
(the SIGNAL's side), half1_pct, half2_pct, exposure, costs, final_equity, h1r_pct, h2r_pct,
h1_trades, h2_trades (the fair halves), exit_<kind> counts, avg_bars_held, stopped_at_fill_open.
Nothing else, so that "every column that is not a p_ column" is a result (identical results can
be found by comparing them): no row number, no pair / tf (they are in the file name), and the
summary fields that only repeat the setting or the clock are not stored: inv (= p_inv), params /
exit_params (= the p_ columns + path mag + cost ours; each worker checks that the summary echoes
the setting it was asked to run, and stops the run if not), exit_kinds (= the exit_<kind>
columns), seconds (a timing). pf is +inf without a losing trade and NaN without trades; win_pct
and avg_bars_held are NaN without trades.
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import apex  # noqa: E402

STRATEGY = 'apex'
MAX_WORKERS = 3
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
PATH = 'mag'                 # the calibration scores 1-minute fills ...
COST = 'ours'                # ... with our costs
MEM_MB = 1000                # memory budget of the prepared inputs of one batch of signal settings

ZONE_LOOKBACK = (10, 20, 30)
MIN_BODY_STR = (0.5, 0.65, 0.8)
VOL_MULTIPLIER = (1.2, 1.7, 2.2)
RR_RATIO = (1.5, 2.0, 3.0, 5.0)
TRAIL_ACT = (0.3, 1.0, 3.0)
TRAIL_OFF = (0.2, 0.5, 1.5)

DIMS = [
    {'name': 'zoneLookback', 'values': list(ZONE_LOOKBACK), 'kind': 'ordinal', 'side': 'signal', 'default': 20},
    {'name': 'minBodyStr', 'values': list(MIN_BODY_STR), 'kind': 'ordinal', 'side': 'signal', 'default': 0.65},
    {'name': 'volMultiplier', 'values': list(VOL_MULTIPLIER), 'kind': 'ordinal', 'side': 'signal', 'default': 1.7},
    {'name': 'fgfOn', 'values': [False, True], 'kind': 'categorical', 'side': 'signal', 'default': True},
    {'name': 'blkClose', 'values': [True, False], 'kind': 'categorical', 'side': 'exit', 'default': True,
     'unused_when': {'fgfOn': False}},
    {'name': 'inv', 'values': [False, True], 'kind': 'categorical', 'side': 'exit', 'default': False},
    {'name': 'rrRatio', 'values': list(RR_RATIO), 'kind': 'ordinal', 'side': 'exit', 'default': 3.0},
    {'name': 'trailOn', 'values': [False, True], 'kind': 'categorical', 'side': 'exit', 'default': False},
    {'name': 'trailAct', 'values': list(TRAIL_ACT), 'kind': 'ordinal', 'side': 'exit', 'default': None,
     'unused_when': {'trailOn': False}},
    {'name': 'trailOff', 'values': list(TRAIL_OFF), 'kind': 'ordinal', 'side': 'exit', 'default': None,
     'unused_when': {'trailOn': False}},
    {'name': 'useTarget', 'values': [True, False], 'kind': 'categorical', 'side': 'exit', 'default': None,
     'unused_when': {'trailOn': False}},
]
NAMES = tuple(d['name'] for d in DIMS)
SIGNAL_NAMES = tuple(d['name'] for d in DIMS if d['side'] == 'signal')
EXIT_NAMES = tuple(d['name'] for d in DIMS if d['side'] == 'exit')
DEFAULT = {d['name']: d['default'] for d in DIMS}           # the script's default setting
P_TYPES = {'zoneLookback': pa.int64(), 'minBodyStr': pa.float64(), 'volMultiplier': pa.float64(),
           'fgfOn': pa.bool_(), 'blkClose': pa.bool_(), 'inv': pa.bool_(), 'rrRatio': pa.float64(),
           'trailOn': pa.bool_(), 'trailAct': pa.float64(), 'trailOff': pa.float64(), 'useTarget': pa.bool_()}

P_COLS = tuple('p_' + k for k in NAMES)
SUM_COLS = ('start', 'end', 'bars', 'trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'long', 'short',
            'raw_long', 'raw_short', 'blocked_long', 'blocked_short', 'half1_pct', 'half2_pct', 'exposure',
            'costs', 'final_equity', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades') \
    + tuple('exit_' + k for k in apex._KINDS) + ('avg_bars_held', 'stopped_at_fill_open')
FLOAT_COLS = {'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'half1_pct', 'half2_pct', 'exposure', 'costs',
              'final_equity', 'h1r_pct', 'h2r_pct', 'avg_bars_held'}
# summary fields that repeat the setting, the cell or the clock: not columns (see the docstring)
SUM_NOT_STORED = ('pair', 'tf', 'inv', 'seconds', 'exit_kinds', 'params', 'exit_params')


# ----------------------------------------------------------------------------------------------
# The grid
# ----------------------------------------------------------------------------------------------
def _trails():
    """The 19 trailing settings: off, then activation x offset x target kept / dropped."""
    T = [dict(trailOn=False, trailAct=None, trailOff=None, useTarget=None)]
    for a in TRAIL_ACT:
        for o in TRAIL_OFF:
            for ut in (True, False):
                T.append(dict(trailOn=True, trailAct=float(a), trailOff=float(o), useTarget=ut))
    return T


def signal_settings():
    """The 54 SIGNAL settings (27 signal input sets x filter off / on)."""
    return [dict(zoneLookback=int(zl), minBodyStr=float(mb), volMultiplier=float(vm), fgfOn=f)
            for zl in ZONE_LOOKBACK for mb in MIN_BODY_STR for vm in VOL_MULTIPLIER for f in (False, True)]


def exit_settings(fgf_on=True):
    """The EXIT settings that can differ under a filter state: 304 with the filter on, 152 with it
    off (blkClose None). rrRatio is the outer loop: the settings of one (signal setting, rrRatio)
    are consecutive (they share one prepared input)."""
    E = []
    for rr in RR_RATIO:
        for blk in ((True, False) if fgf_on else (None,)):
            for inv in (False, True):
                for t in _trails():
                    E.append(dict(blkClose=blk, inv=inv, rrRatio=float(rr), **t))
    return E


SIGNALS = signal_settings()
EXITS = exit_settings(True)
_EXITS_OFF = exit_settings(False)


def exits_for(sig):
    """The exit settings of a signal setting (new dicts)."""
    return [dict(e) for e in (EXITS if sig['fgfOn'] else _EXITS_OFF)]


def grid():
    """Every setting, in a fixed order (SIGNALS order, then the exits of each): a list of dicts
    {dimension name: value or None}. The position in the list is the column `setting`."""
    G = []
    for s in SIGNALS:
        for e in exits_for(s):
            cfg = dict(s)
            cfg.update(e)
            G.append({k: cfg[k] for k in NAMES})
    return G


def layout():
    """[(signal index, rrRatio index, first setting, end setting)]: the consecutive settings of
    the grid that share one prepared input (same signal setting and rrRatio)."""
    L = []
    i = 0
    for si, s in enumerate(SIGNALS):
        per = len(EXITS if s['fgfOn'] else _EXITS_OFF) // len(RR_RATIO)
        for ri in range(len(RR_RATIO)):
            L.append((si, ri, i, i + per))
            i += per
    return L


def key_of(cfg):
    return tuple(cfg[k] for k in NAMES)


def prepare_params(cfg):
    """The params of apex.prepare for a setting (signals, filter, and the target ratio the module
    turns into the per-bar target arrays)."""
    return {'zoneLookback': cfg['zoneLookback'], 'minBodyStr': cfg['minBodyStr'],
            'volMultiplier': cfg['volMultiplier'], 'fgfOn': cfg['fgfOn'], 'rrRatio': cfg['rrRatio']}


def exit_params(cfg, path=PATH, cost=COST):
    """The exit params of apex.simulate for a setting. None = the dimension is unused: the
    module default is left in place (it has no effect there)."""
    X = {'inv': cfg['inv'], 'trailOn': cfg['trailOn'], 'path': path, 'cost': cost}
    if cfg['blkClose'] is not None:
        X['blkClose'] = cfg['blkClose']
    if cfg['trailOn']:
        X['trailAct'] = cfg['trailAct']
        X['trailOff'] = cfg['trailOff']
        X['useTarget'] = cfg['useTarget']
    return X


def _as_bool(name, v):
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, float, np.integer, np.floating)) and v in (0, 1):
        return bool(v)
    raise ValueError('p_%s must be true or false, got %r' % (name, v))


def _as_int(name, v):
    if isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float, np.integer, np.floating)) \
            or float(v) != int(v):
        raise ValueError('p_%s must be an integer, got %r' % (name, v))
    return int(v)


def _as_float(name, v):
    if isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float, np.integer, np.floating)):
        raise ValueError('p_%s must be a number, got %r' % (name, v))
    return float(v)


def setting_from(p):
    """The canonical setting of a mapping of p_ values (keys with or without the 'p_' prefix;
    null / NaN = None). A used dimension must be given; an unused one (blkClose with the filter
    off; trailAct / trailOff / useTarget with the trailing off) is forced to None, as in the grid.
    Values outside the grid are accepted here (apex validates them; one() refuses them unless
    asked)."""
    q = {}
    for k, v in p.items():
        name = k[2:] if k.startswith('p_') else k
        if name not in NAMES:
            raise KeyError('unknown dimension %r (one of %s)' % (k, ', '.join(NAMES)))
        if name in q:
            raise KeyError('dimension %r given twice' % name)
        if isinstance(v, (float, np.floating)) and math.isnan(v):
            v = None
        q[name] = v

    def need(name):
        if q.get(name) is None:
            raise ValueError('p_%s is required' % name)
        return q[name]

    cfg = dict.fromkeys(NAMES)
    cfg['zoneLookback'] = _as_int('zoneLookback', need('zoneLookback'))
    cfg['minBodyStr'] = _as_float('minBodyStr', need('minBodyStr'))
    cfg['volMultiplier'] = _as_float('volMultiplier', need('volMultiplier'))
    cfg['fgfOn'] = _as_bool('fgfOn', need('fgfOn'))
    if cfg['fgfOn']:
        cfg['blkClose'] = _as_bool('blkClose', need('blkClose'))
    cfg['inv'] = _as_bool('inv', need('inv'))
    cfg['rrRatio'] = _as_float('rrRatio', need('rrRatio'))
    cfg['trailOn'] = _as_bool('trailOn', need('trailOn'))
    if cfg['trailOn']:
        cfg['trailAct'] = _as_float('trailAct', need('trailAct'))
        cfg['trailOff'] = _as_float('trailOff', need('trailOff'))
        cfg['useTarget'] = _as_bool('useTarget', need('useTarget'))
    return cfg


def _check_echo(cfg, s, path, cost):
    """The summary must describe the setting that was asked for."""
    sp, xp = s['params'], s['exit_params']
    ok = (sp['zoneLookback'] == cfg['zoneLookback'] and sp['minBodyStr'] == cfg['minBodyStr']
          and sp['volMultiplier'] == cfg['volMultiplier'] and sp['rrRatio'] == cfg['rrRatio']
          and sp['fgfOn'] == cfg['fgfOn'] and sp['htfTimeframe'] == '15' and sp['reverse'] is False
          and sp['cost'] == cost and xp['path'] == path
          and s['inv'] == cfg['inv'] and xp['trailOn'] == cfg['trailOn']
          and (cfg['blkClose'] is None or sp['blkClose'] == cfg['blkClose'])
          and (not cfg['trailOn'] or (xp['trailAct'] == cfg['trailAct'] and xp['trailOff'] == cfg['trailOff']
                                      and xp['useTarget'] == cfg['useTarget'])))
    if not ok:
        raise RuntimeError('apex summary does not echo the setting %r: params %r exit_params %r inv %r'
                           % (cfg, sp, xp, s['inv']))


# ----------------------------------------------------------------------------------------------
# One setting (--one)
# ----------------------------------------------------------------------------------------------
def _json_default(v):
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    raise TypeError('not JSON serializable: %r' % (v,))


_GRID_INDEX = None


def grid_index():
    """{setting key: row number}."""
    global _GRID_INDEX
    if _GRID_INDEX is None:
        _GRID_INDEX = {key_of(c): i for i, c in enumerate(grid())}
    return _GRID_INDEX


def one(pair, tf, p, path=PATH, cost=COST, off_grid=False):
    """The full summary of apex.simulate for one setting, computed alone (its own apex.prepare
    and one apex.simulate). p: a mapping of p_ values (see setting_from). Adds "setting" =
    {strategy, pair, tf, path, cost, p (canonical), in_grid, row (row number in the grid file,
    None off the grid)}. A setting that is not in the grid is refused unless off_grid."""
    cfg = setting_from(p)
    row = grid_index().get(key_of(cfg))
    if row is None and not off_grid:
        raise ValueError('not a setting of the grid: %r (--off-grid runs it anyway)' % (cfg,))
    S = apex.prepare(pair, str(tf), prepare_params(cfg))
    _, s = apex.simulate(S, exit_params(cfg, path, cost))
    _check_echo(cfg, s, path, cost)
    s = dict(s)
    s['setting'] = {'strategy': STRATEGY, 'pair': pair, 'tf': str(tf), 'path': path, 'cost': cost, 'p': cfg,
                    'in_grid': row is not None, 'row': row}
    return s


# ----------------------------------------------------------------------------------------------
# The sweep of one cell
# ----------------------------------------------------------------------------------------------
_G: dict = {}            # shared with the forked workers (copy-on-write)


def _work(task):
    si, ri, i0, i1 = task
    t0, c0 = time.time(), time.process_time()
    S = _G['S'][(si, ri)]
    G, path, cost = _G['G'], _G['path'], _G['cost']
    out = []
    for i in range(i0, i1):
        cfg = G[i]
        _, s = apex.simulate(S, exit_params(cfg, path, cost))
        _check_echo(cfg, s, path, cost)
        out.append((i, tuple(s[k] for k in SUM_COLS)))
    return out, time.time() - t0, time.process_time() - c0


def _cache_keys(kind):
    return {k for k in apex._CACHE if isinstance(k, tuple) and k and k[0] == kind}


def _drop_signal_cache():
    for k in _cache_keys('sig'):
        del apex._CACHE[k]


def _triple_bytes(n, w1):
    """Rough size of the prepared inputs of one signal input set (its signal arrays in apex's
    cache + 8 prepared dicts: filter off / on x 4 rrRatio)."""
    return 372 * n + 16 * w1


def _batches(n, w1, mem_mb):
    """Signal input sets (0..26) grouped so that one batch's prepared inputs fit the budget."""
    nt = len(SIGNALS) // 2
    per = max(1, min(nt, int(mem_mb * 1e6 // max(_triple_bytes(n, w1), 1))))
    return [list(range(a, min(a + per, nt))) for a in range(0, nt, per)]


def _shared(pair, tf, G, L, path, cost):
    """What every setting of the cell shares, before any fork: bars, the filter permissions
    (computed once), the 1-minute sub-bars, the compiled kernels. Returns a prepared input."""
    on = next(g for g in L if SIGNALS[g[0]]['fgfOn'])
    S0 = apex.prepare(pair, tf, prepare_params(G[on[2]]))
    if path == 'mag':
        apex.sub_bars(S0)
    warm = next(i for i in range(on[2], on[3]) if G[i]['trailOn'])
    apex.simulate(S0, exit_params(G[warm], path, cost))      # compile / load the kernel before forking
    return S0


def _prepare_batch(pair, tf, G, L, triples, path):
    """The prepared inputs {(signal index, rrRatio index): S} of a batch of signal input sets."""
    S = {}
    tri = set(triples)
    for si, ri, i0, _ in L:
        if si // 2 in tri:
            Sk = apex.prepare(pair, tf, prepare_params(G[i0]))
            if path == 'mag':
                apex.sub_bars(Sk)                # the cell's table (cached by the module)
            S[(si, ri)] = Sk
    return S


def _table(G, rows):
    cols = []
    names = []
    for k in NAMES:
        cols.append(pa.array([c[k] for c in G], P_TYPES[k]))
        names.append('p_' + k)
    for j, k in enumerate(SUM_COLS):
        v = [r[j] for r in rows]
        if k in FLOAT_COLS:
            cols.append(pa.array(np.array(v, dtype=np.float64)))        # NaN stays NaN (no trades)
        else:
            cols.append(pa.array(np.array(v, dtype=np.int64)))
        names.append(k)
    return pa.Table.from_arrays(cols, names=names)


def _write_atomic(path_out, writer):
    tmp = path_out + '.tmp%d' % os.getpid()
    writer(tmp)
    os.replace(tmp, path_out)


def write_dims(out_dir):
    f = os.path.join(out_dir, 'calib_%s_dims.json' % STRATEGY)

    def w(tmp):
        with open(tmp, 'w') as fh:
            json.dump(DIMS, fh, indent=1)
            fh.write('\n')
    _write_atomic(f, w)
    return f


def run_cell(pair, tf, workers=MAX_WORKERS, out_dir=None, path=PATH, cost=COST, mem_mb=MEM_MB,
             verbose=True, write=True):
    """The whole grid on one cell. Returns (frame, info); writes the parquet and the dims JSON
    unless write is False."""
    tf = str(tf)
    t0 = time.time()
    G = grid()
    L = layout()
    sig0, gate0 = _cache_keys('sig'), _cache_keys('perm')
    S0 = _shared(pair, tf, G, L, path, cost)
    signal_runs = len(_cache_keys('sig') - sig0)             # 1: the first signal input set
    n, w1 = len(S0['c']), S0['w1']
    nsub = len(apex.sub_bars(S0)[1]) if path == 'mag' else 0
    window = (S0['w0'], S0['w1'], S0['start'], S0['end'])
    del S0
    t_shared = time.time() - t0
    batches = _batches(n, w1, mem_mb)
    if verbose:
        print('  %s %s: %d bars, %d 1-minute sub-bars; filter permissions, kernels (%.1fs)'
              % (pair, tf, n, nsub, t_shared), flush=True)
        print('  grid: %d settings = %d signal settings x exits (filter off %d, on %d); path %s, cost %s; '
              '%d worker%s; %d batch%s of <= %d signal input sets'
              % (len(G), len(SIGNALS), len(_EXITS_OFF), len(EXITS), path, cost, workers,
                 '' if workers == 1 else 's', len(batches), '' if len(batches) == 1 else 'es', len(batches[0])),
              flush=True)
    rows = [None] * len(G)
    t_prep = t_run = busy = cpu = 0.0
    n_prepared = done = 0
    for b, triples in enumerate(batches):
        tb = time.time()
        seen = _cache_keys('sig')
        S = _prepare_batch(pair, tf, G, L, triples, path)
        signal_runs += len(_cache_keys('sig') - seen)        # signal kernel runs = new cache entries
        for Sk in S.values():
            if (Sk['w0'], Sk['w1'], Sk['start'], Sk['end']) != window:
                raise ValueError('%s %s: window rows differ between prepared inputs' % (pair, tf))
        n_prepared += len(S)
        tasks = sorted((g for g in L if (g[0], g[1]) in S), key=lambda g: (g[2] - g[3], g[2]))
        _G.clear()
        _G.update(S=S, G=G, path=path, cost=cost)
        dp = time.time() - tb
        t_prep += dp
        tr = time.time()
        if workers <= 1:
            for chunk, dt, dc in map(_work, tasks):
                busy += dt
                cpu += dc
                for i, vals in chunk:
                    rows[i] = vals
                done += len(chunk)
        else:
            ctx = mp.get_context('fork')
            with ctx.Pool(processes=workers) as pool:
                for chunk, dt, dc in pool.imap_unordered(_work, tasks):
                    busy += dt
                    cpu += dc
                    for i, vals in chunk:
                        rows[i] = vals
                    done += len(chunk)
        dr = time.time() - tr
        t_run += dr
        _G.clear()
        S.clear()
        _drop_signal_cache()
        if verbose:
            el = time.time() - t0
            print('    batch %d/%d: %d signal input sets, %d prepared inputs in %.1fs; %d settings in %.1fs; '
                  '%5.1f%% done, %.1fs elapsed, eta %.1fs'
                  % (b + 1, len(batches), len(triples), len(tasks), dp, sum(g[3] - g[2] for g in tasks), dr,
                     100.0 * done / len(G), el, (el - t_shared) / done * (len(G) - done)), flush=True)
    gate_runs = len(_cache_keys('perm') - gate0)
    if any(r is None for r in rows):
        raise RuntimeError('%s %s: %d settings were not simulated' % (pair, tf, sum(r is None for r in rows)))
    tw = time.time()
    table = _table(G, rows)
    path_out = None
    if write:
        out_dir = out_dir or os.path.join(W, 'out')
        os.makedirs(out_dir, exist_ok=True)
        path_out = os.path.join(out_dir, 'calib_%s_%s_%s.parquet' % (STRATEGY, pair, tf))
        _write_atomic(path_out, lambda tmp: pq.write_table(table, tmp))
        write_dims(out_dir)
    df = table.to_pandas()
    t_write = time.time() - tw
    el = time.time() - t0
    info = dict(pair=pair, tf=tf, rows=len(df), bars=n, sub_bars=nsub, workers=workers, batches=len(batches),
                prepared=n_prepared, signal_runs=signal_runs, gate_runs=gate_runs, file=path_out,
                t_shared=t_shared, t_prep=t_prep, t_run=t_run, worker_seconds=busy, worker_cpu=cpu,
                t_write=t_write, total=el)
    if verbose:
        print('  %s %s done: %d rows -> %s' % (pair, tf, len(df), path_out), flush=True)
        print('    timing: shared %.1fs, signal prep %.1fs (%d signal kernel runs, %d prepared inputs, filter '
              'permissions computed %d time%s), runs %.1fs (workers: %.1fs CPU = %.5fs per setting; %.1fs busy '
              'wall: CPU share %.0f%%), write %.1fs, total %.1fs'
              % (t_shared, t_prep, signal_runs, n_prepared, gate_runs, '' if gate_runs == 1 else 's', t_run, cpu,
                 cpu / len(G), busy, 100.0 * cpu / max(busy, 1e-9), t_write, el), flush=True)
    return df, info


# ----------------------------------------------------------------------------------------------
# Time estimate of a cell (single process, nothing written)
# ----------------------------------------------------------------------------------------------
def estimate_cell(pair, tf, n_per=12, seed=0, path=PATH, cost=COST, workers=MAX_WORKERS, verbose=True):
    """Measures the shared preparation and, for each of the 27 signal input sets, its preparation
    and n_per random settings of its 456; extrapolates the simulation time to the whole grid.
    The simulations are measured in CPU seconds (time.process_time: what a worker needs when it has
    a core to itself), the serial part (shared + signal prep, main process) in CPU seconds too:
    est_wall = shared + signal prep + simulation CPU / workers = the wall time on an otherwise idle
    machine. The wall time actually spent measuring is reported next to it (measured_in, load)."""
    tf = str(tf)
    t0, c00 = time.time(), time.process_time()
    G = grid()
    L = layout()
    rng = np.random.default_rng(seed)
    S0 = _shared(pair, tf, G, L, path, cost)
    n, w1 = len(S0['c']), S0['w1']
    del S0
    t_shared = time.process_time() - c00
    t_prep = sim = 0.0
    n_sim = 0
    lo_t, hi_t = float('inf'), 0.0
    for tri in range(len(SIGNALS) // 2):
        tp = time.process_time()
        S = _prepare_batch(pair, tf, G, L, [tri], path)
        t_prep += time.process_time() - tp
        groups = [g for g in L if (g[0], g[1]) in S]
        idx = np.concatenate([np.arange(g[2], g[3]) for g in groups])
        owner = {i: (g[0], g[1]) for g in groups for i in range(g[2], g[3])}
        pick = rng.choice(idx, size=min(n_per, len(idx)), replace=False)
        ts = time.process_time()
        for i in pick.tolist():
            apex.simulate(S[owner[i]], exit_params(G[i], path, cost))
        dt = (time.process_time() - ts) / len(pick)
        sim += dt * len(idx)
        n_sim += len(pick)
        lo_t, hi_t = min(lo_t, dt), max(hi_t, dt)
        S.clear()
        _drop_signal_cache()
    est = dict(pair=pair, tf=tf, bars=n, settings=len(G), sampled=n_sim, t_shared=t_shared, t_prep=t_prep,
               sim_cpu=sim, per_setting=sim / len(G), per_setting_min=lo_t, per_setting_max=hi_t,
               est_wall_1=t_shared + t_prep + sim, est_wall=t_shared + t_prep + sim / max(workers, 1),
               workers=workers, batches=len(_batches(n, w1, MEM_MB)), measured_in=time.time() - t0,
               measured_cpu=time.process_time() - c00)
    if verbose:
        print('  %-3s %-3s %8d bars | shared %5.1fs + signal prep %5.1fs + simulations %7.1fs CPU '
              '(%.5fs per setting; per signal input set %.5f..%.5f) | estimate: %6.1fs with %d workers '
              '(%.1f min), %7.1fs with 1 | measured in %.1fs wall, %.1fs CPU'
              % (pair, tf, n, t_shared, t_prep, sim, sim / len(G), lo_t, hi_t, est['est_wall'], workers,
                 est['est_wall'] / 60.0, est['est_wall_1'], est['measured_in'], est['measured_cpu']), flush=True)
    return est


# ----------------------------------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description='ApexForge + FGF calibration grid (CALIB_SPEC.md)')
    ap.add_argument('pair', nargs='?', choices=PAIRS)
    ap.add_argument('rest', nargs='*', metavar='TF',
                    help="timeframes; with --one: TF and the JSON object of p_ values")
    ap.add_argument('--workers', type=int, default=MAX_WORKERS)
    ap.add_argument('--one', action='store_true', help='print the full summary of one setting as JSON')
    ap.add_argument('--path', choices=apex.PATHS, default=PATH, help='--one only')
    ap.add_argument('--cost', choices=apex.COSTS, default=COST, help='--one only')
    ap.add_argument('--off-grid', action='store_true', help='--one: accept values that are not in the grid')
    ap.add_argument('--estimate', action='store_true', help='time estimate of the full grid, no file written')
    ap.add_argument('--samples', type=int, default=12, help='--estimate: settings timed per signal input set')
    ap.add_argument('--mem-mb', type=int, default=MEM_MB, help='memory budget of one batch of prepared inputs')
    ap.add_argument('--out-dir', default=None, help='output directory (default: out/ next to this file)')
    a = ap.parse_args(argv)

    if a.one:
        if a.estimate or a.pair is None or len(a.rest) != 2 or a.rest[0] not in TFS:
            ap.error("--one needs PAIR TF '<json of p_ values>'")
        try:
            p = json.loads(a.rest[1])
        except ValueError as e:
            ap.error('--one: the p_ values are not valid JSON (%s)' % e)
        if not isinstance(p, dict):
            ap.error('--one: the p_ values must be a JSON object')
        try:
            s = one(a.pair, a.rest[0], p, a.path, a.cost, a.off_grid)
        except (KeyError, ValueError) as e:
            ap.error('--one: %s' % (e.args[0] if e.args else e))
        print(json.dumps(s, default=_json_default), flush=True)
        return 0
    if (a.path, a.cost) != (PATH, COST):
        ap.error('--path / --cost only apply to --one (the grid is scored with path %s, cost %s)' % (PATH, COST))
    for tf in a.rest:
        if tf not in TFS:
            ap.error('unknown TF %r (one of %s)' % (tf, ', '.join(TFS)))
    workers = max(1, min(int(a.workers), MAX_WORKERS))
    if workers != a.workers:
        print('workers capped at %d' % workers, flush=True)
    if a.estimate:
        cells = [(p, tf) for p in ((a.pair,) if a.pair else PAIRS) for tf in (a.rest or TFS)]
        print('estimated time of the full grid (%d settings) per cell, %d workers each with a core to itself '
              '(CPU seconds measured single-process: every signal input set prepared, %d of its 456 settings '
              'timed)' % (len(grid()), workers, a.samples), flush=True)
        t0 = time.time()
        est = [estimate_cell(p, tf, a.samples, workers=workers) for p, tf in cells]
        print('all cells: %.1fs = %.1f min with %d workers (one cell after the other); measured in %.1fs wall'
              % (sum(e['est_wall'] for e in est), sum(e['est_wall'] for e in est) / 60.0, workers,
                 time.time() - t0), flush=True)
        return 0
    if a.pair is None or not a.rest:
        ap.error('PAIR and at least one TF are required')
    t0 = time.time()
    for tf in a.rest:
        print('== calib %s %s %s ==' % (STRATEGY, a.pair, tf), flush=True)
        run_cell(a.pair, tf, workers, out_dir=a.out_dir, mem_mb=a.mem_mb)
    print('all done in %.1fs' % (time.time() - t0), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
