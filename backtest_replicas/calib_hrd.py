"""calib_hrd.py: calibration grid of HRD Full Divergence v1.03 + FGF per pair and timeframe, with
the direction (Normal / Inverted, Update 1) as a calibrated input (CALIB_SPEC.md, strategy "hrd"),
on the canonical replica hrd.py (prepare / simulate / summary_fast).

Usage
  python3 -I calib_hrd.py PAIR TF [TF ...] [--workers 3] [--out-dir DIR]
      runs the full grid of every (PAIR, TF) cell and writes out/calib_hrd_<PAIR>_<TF>.parquet
      (one row per setting) and out/calib_hrd_dims.json (DIMS). PAIR in BTC, XAU; TF in 1, 5, 15,
      30, 60, 120, 240. Safe to re-run: the files are overwritten (written to a temp name first).
  python3 -I calib_hrd.py --one PAIR TF '<json of p_ values>' [--path tv|mag] [--cost tv|ours|stress]
      prints the full summary of ONE setting as one JSON document on stdout (default path mag,
      cost ours = the sweep's scoring). The JSON of p_ values is a row's p_ columns: keys with or
      without the "p_" prefix, null (or NaN) for an unused dimension. --off-grid also accepts
      values that are not in the grid (numbers, and "act/off" for trail).
  python3 -I calib_hrd.py --estimate PAIR TF [TF ...] [--workers 3] [--per-signal 6]
      times the cell's preparation and a random sample of settings in ONE process and prints the
      estimated time of the full cell; writes nothing.

The grid: 23,328 settings per cell = 27 signal inputs x 3 filter modes x 2 directions x 144 exits
  signals   pivotStrength {3, 5, 8} x maxDivLookback {30, 60, 120} x divs {all, regular, hidden}
            divs = which divergences give signals, through the script's own show* inputs:
            all = the four of them (default); regular = showBullReg + showBearReg only; hidden =
            showBullHid + showBearHid only. Breakouts always trade.
  filter    fgfOn False (blkClose unused: None) | fgfOn True x blkClose {True, False}
            (hrdBlkClose, "Blocked opposite signal still closes the trade")
  direction inv {False, True} (hrdInv, "Inverted direction"); "Reverse Trading" stays off
  exits     InpSlPct {1, 2, 4} x InpTpPct {0 = no target, 4} x InpExitCandles {5, 20, 100}
            x useHybridExit {True, False} x [trailOn False (trail unused: None) | trailOn True x
            trail {"0.5/0.15", "1/0.5", "2/1"}]; trail = "activation % / offset %" (hrdTrailAct /
            hrdTrailOff), the two move together, so they are ONE ordinal dimension.
Everything else stays at the script's defaults (Trade Direction Both, risk 1 %, hybrid inputs,
the filter's own inputs). The script's default setting is one of the rows (DEFAULT_P).

SIGNALS (54) are the parameters of hrd.prepare (signal inputs + fgfOn), EXITS (864) those of
hrd.simulate (blkClose, inv, the exits); exits_for(signal) = the EXITS that go with a signal
setting (288 with the filter off, 576 with it on). A dimension that cannot change the result is
listed once with the value None: blkClose with the filter off (nothing is ever blocked), trail
with trailOn False. DIMS = the 12 dimensions (name, values, kind 'ordinal' / 'categorical'; extra
keys: side, default, unused_when); row i of a file is grid()[i].

Every setting is scored with path 'mag' (exits walked along the 1-minute sub-bars; on chart "1"
each bar is its own sub-bar) and cost 'ours'. Per cell: hrd.prepare runs ONCE per signal setting
(the per-bar signal arrays are dropped afterwards, only the window's signal / permission arrays
are kept), the 1-minute sub-bars are built once, the kernel is compiled, and only then at most 3
workers are forked (copy-on-write); each simulates chunks of exit settings of one prepared input
(hrd.simulate + hrd.summary_fast). Rows are assembled in grid order, so the file does not depend
on the worker count.

Output columns: p_<name> for every dimension of DIMS, in DIMS order, then every field of
hrd.summary_fast in its own order (start, end, bars, trades, net_pct, pf, win_pct, max_dd_pct,
max_dd_init_pct, long, short, raw_long, raw_short, blocked_long, blocked_short, half1_pct,
half2_pct, exposure, final_equity, exit_<kind> counts, zero_length, h1r_pct, h2r_pct, h1_trades,
h2_trades, avg_bars_held, costs). Nothing else: no index, no pair / tf column (they are in the
file name; the parquet's key-value metadata "calib" holds strategy, pair, tf, path, cost, the
number of settings and the sha256 of hrd.py and fgf.py that produced the rows). pf is +inf without a losing trade and NaN without trades; win_pct and avg_bars_held
are NaN without trades. --one prints the same fields (Python's json: Infinity / NaN) plus
"setting" = {strategy, pair, tf, path, cost, p (the canonical p_ values), in_grid, row (its row
number in the grid file)}.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import hrd  # noqa: E402

STRATEGY = 'hrd'
MAX_WORKERS = 3
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
PATH = 'mag'             # the sweep's scoring: 1-minute fills ...
COST = 'ours'            # ... with our costs
CHUNK = 48               # exit settings per worker task

# ---------------------------------------------------------------------------------------------
# the grid
# ---------------------------------------------------------------------------------------------
PIVOT_STRENGTHS = (3, 5, 8)
MAX_DIV_LOOKBACKS = (30, 60, 120)
# divs -> (showBullReg, showBearReg, showBullHid, showBearHid)
DIVS = {'all': (True, True, True, True), 'regular': (True, True, False, False), 'hidden': (False, False, True, True)}
FILTERS = (False, True)
BLK_CLOSES = (True, False)
INVS = (False, True)
SL_PCTS = (1.0, 2.0, 4.0)
TP_PCTS = (0.0, 4.0)
EXIT_CANDLES = (5, 20, 100)
HYBRIDS = (True, False)
# trail -> (trailAct %, trailOff %)
TRAILS = {'0.5/0.15': (0.5, 0.15), '1/0.5': (1.0, 0.5), '2/1': (2.0, 1.0)}

# name, values, kind as CALIB_SPEC.md asks; extra keys (as calib_apex.py): side = 'signal' (a parameter
# of hrd.prepare) or 'exit' (of hrd.simulate), default = the script's default input, unused_when =
# the value of another dimension with which this one cannot change the result (its value is None)
DIMS = [
    {'name': 'pivotStrength', 'values': list(PIVOT_STRENGTHS), 'kind': 'ordinal', 'side': 'signal', 'default': 5},
    {'name': 'maxDivLookback', 'values': list(MAX_DIV_LOOKBACKS), 'kind': 'ordinal', 'side': 'signal', 'default': 60},
    {'name': 'divs', 'values': list(DIVS), 'kind': 'categorical', 'side': 'signal', 'default': 'all'},
    {'name': 'fgfOn', 'values': list(FILTERS), 'kind': 'categorical', 'side': 'signal', 'default': True},
    {'name': 'blkClose', 'values': list(BLK_CLOSES), 'kind': 'categorical', 'side': 'exit', 'default': True,
     'unused_when': {'fgfOn': False}},
    {'name': 'inv', 'values': list(INVS), 'kind': 'categorical', 'side': 'exit', 'default': False},
    {'name': 'InpSlPct', 'values': list(SL_PCTS), 'kind': 'ordinal', 'side': 'exit', 'default': 2.0},
    {'name': 'InpTpPct', 'values': list(TP_PCTS), 'kind': 'categorical', 'side': 'exit', 'default': 4.0},   # 0 = no target
    {'name': 'InpExitCandles', 'values': list(EXIT_CANDLES), 'kind': 'ordinal', 'side': 'exit', 'default': 5},
    {'name': 'useHybridExit', 'values': list(HYBRIDS), 'kind': 'categorical', 'side': 'exit', 'default': True},
    {'name': 'trailOn', 'values': [False, True], 'kind': 'categorical', 'side': 'exit', 'default': False},
    {'name': 'trail', 'values': list(TRAILS), 'kind': 'ordinal', 'side': 'exit', 'default': None,
     'unused_when': {'trailOn': False}},
]
DIM_NAMES = [d['name'] for d in DIMS]
SIGNAL_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'signal')
EXIT_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'exit')
# a dimension is unused (None) when another one has this value
UNUSED_WHEN = {d['name']: next(iter(d['unused_when'].items())) for d in DIMS if 'unused_when' in d}
DIM_DOC = {
    'pivotStrength': 'Pivot Strength (L/R), bars',
    'maxDivLookback': 'Max Divergence Lookback, bars',
    'divs': 'divergences that give signals (show* inputs): all four / regular only / hidden only',
    'fgfOn': 'direction filter: Enable filter',
    'blkClose': 'Blocked opposite signal still closes the trade (None: filter off)',
    'inv': 'Inverted direction: opposite side at the same entries (Update 1)',
    'InpSlPct': 'Stop Loss, % of the signal close',
    'InpTpPct': 'Take Profit, % of the signal close (0 = disabled)',
    'InpExitCandles': 'Close after X Candles',
    'useHybridExit': 'Use Hybrid Exit',
    'trailOn': 'Use trailing take profit',
    'trail': 'Trail activation % / Trail offset % (None: trailing off)',
}
_DIM_TYPE = {'pivotStrength': int, 'maxDivLookback': int, 'divs': str, 'fgfOn': bool, 'blkClose': bool,
             'inv': bool, 'InpSlPct': float, 'InpTpPct': float, 'InpExitCandles': int, 'useHybridExit': bool,
             'trailOn': bool, 'trail': str}

# the script's default setting (hrd.DEFAULTS; the Pine's input defaults): filter on with the blocked
# close, normal direction, SL 2 %, TP 4 %, 5 candles, hybrid exit on, trailing off
DEFAULT_P = {d['name']: d['default'] for d in DIMS}
DEFAULT = DEFAULT_P

# SIGNAL settings: the parameters of hrd.prepare. fgfOn is the innermost loop: the two filter
# states of one signal input share hrd's signal arrays.
SIGNALS = [{'pivotStrength': ps, 'maxDivLookback': lb, 'divs': dv, 'fgfOn': f}
           for ps in PIVOT_STRENGTHS for lb in MAX_DIV_LOOKBACKS for dv in DIVS for f in FILTERS]
# EXIT settings: the parameters of hrd.simulate. blkClose None = the 288 of a filter-off signal
# setting; blkClose True / False = the 576 of a filter-on one.
EXITS = [{'blkClose': b, 'inv': i, 'InpSlPct': s, 'InpTpPct': t, 'InpExitCandles': c, 'useHybridExit': h,
          'trailOn': tr is not None, 'trail': tr}
         for b in (None,) + BLK_CLOSES for i in INVS for s in SL_PCTS for t in TP_PCTS for c in EXIT_CANDLES
         for h in HYBRIDS for tr in (None,) + tuple(TRAILS)]


def exits_for(sig):
    """The EXIT settings of one SIGNAL setting, in EXITS order."""
    return [x for x in EXITS if (x['blkClose'] is None) == (not sig['fgfOn'])]


def merge(sig, x):
    """One grid setting: every dimension of DIMS, in DIMS order."""
    d = dict(sig)
    d.update(x)
    return {k: d[k] for k in DIM_NAMES}


def grid(sig_idx=None):
    """Every setting, in file order: for each SIGNAL setting, its EXIT settings."""
    idx = range(len(SIGNALS)) if sig_idx is None else sig_idx
    return [merge(SIGNALS[si], x) for si in idx for x in exits_for(SIGNALS[si])]


def key(p):
    return tuple(p[k] for k in DIM_NAMES)


def signal_params(sig):
    """A SIGNAL setting as hrd.prepare params (everything else at the script's defaults)."""
    br, er, bh, eh = DIVS[sig['divs']]
    return {'pivotStrength': int(sig['pivotStrength']), 'maxDivLookback': int(sig['maxDivLookback']),
            'showBullReg': br, 'showBearReg': er, 'showBullHid': bh, 'showBearHid': eh,
            'fgfOn': bool(sig['fgfOn'])}


def trail_pair(label):
    """'act/off' -> (trailAct %, trailOff %)."""
    if label in TRAILS:
        return TRAILS[label]
    a, o = str(label).split('/')
    return float(a), float(o)


def exit_params(x, path=PATH, cost=COST):
    """An EXIT setting as hrd.simulate params. Unused dimensions are left at the defaults: blkClose
    with the filter off (no signal is ever blocked), trailAct / trailOff with the trail off (the
    kernel ignores them)."""
    X = {'hrdInv': bool(x['inv']), 'InpSlPct': float(x['InpSlPct']), 'InpTpPct': float(x['InpTpPct']),
         'InpExitCandles': int(x['InpExitCandles']), 'useHybridExit': bool(x['useHybridExit']),
         'trailOn': bool(x['trailOn']), 'path': path, 'cost': cost}
    if x['blkClose'] is not None:
        X['blkClose'] = bool(x['blkClose'])
    if x['trailOn']:
        X['trailAct'], X['trailOff'] = trail_pair(x['trail'])
    return X


def normalize(raw, off_grid=False):
    """A setting given as a mapping of p_ values (keys with or without 'p_'; None / NaN / missing =
    unused) -> the canonical dict over DIM_NAMES. Unused dimensions are set to None whatever was
    given. Raises ValueError for an unknown key, a missing used dimension, or (unless off_grid) a
    value that is not in the grid."""
    vals = {}
    for k, v in raw.items():
        k = k[2:] if k.startswith('p_') else k
        if k not in DIM_NAMES:
            raise ValueError('unknown dimension %r (one of %s)' % (k, ', '.join(DIM_NAMES)))
        if isinstance(v, float) and math.isnan(v):
            v = None
        vals[k] = v
    out = {}
    for d in DIMS:
        name = d['name']
        v = vals.get(name)
        if name in UNUSED_WHEN:
            other, when = UNUSED_WHEN[name]
            if out[other] == when:
                out[name] = None
                continue
        if v is None:
            raise ValueError('dimension %r has no value' % name)
        ty = _DIM_TYPE[name]
        if ty is bool:
            if not (isinstance(v, (bool, np.bool_)) or (isinstance(v, (int, float)) and v in (0, 1))):
                raise ValueError('%s: %r is not a boolean' % (name, v))
            v = bool(v)
        elif ty is int:
            if isinstance(v, bool) or not isinstance(v, (int, float, np.integer, np.floating)) or int(v) != v:
                raise ValueError('%s: %r is not an integer' % (name, v))
            v = int(v)
        elif ty is float:
            if isinstance(v, bool) or not isinstance(v, (int, float, np.integer, np.floating)):
                raise ValueError('%s: %r is not a number' % (name, v))
            v = float(v)
        else:
            v = str(v)
        if v not in d['values']:
            if not off_grid:
                raise ValueError('%s: %r is not in the grid %r' % (name, v, d['values']))
            if name == 'divs':
                raise ValueError('divs: %r is not one of %r' % (v, d['values']))
            if name == 'trail':
                trail_pair(v)
        out[name] = v
    return out


_ROWS = None


def row_of(p):
    """The row number of a setting in the grid file (grid() order), None when it is not in the grid."""
    global _ROWS
    if _ROWS is None:
        _ROWS = {key(q): i for i, q in enumerate(grid())}
    return _ROWS.get(key(p))


def in_grid(p):
    return row_of(p) is not None


# ---------------------------------------------------------------------------------------------
# one setting
# ---------------------------------------------------------------------------------------------
def one(pair, tf, p, path=PATH, cost=COST, off_grid=False):
    """The full summary (hrd.summary_fast) of one setting, computed alone: its own hrd.prepare and
    one hrd.simulate. p: a mapping of p_ values (see normalize)."""
    p = normalize(p, off_grid)
    Pp = hrd.prepare(pair, str(tf), signal_params({k: p[k] for k in SIGNAL_DIMS}))
    s = hrd.summary_fast(Pp, hrd.simulate(Pp, exit_params({k: p[k] for k in EXIT_DIMS}, path, cost)))
    out = dict(s)
    row = row_of(p)
    out['setting'] = {'strategy': STRATEGY, 'pair': pair, 'tf': str(tf), 'path': path, 'cost': cost, 'p': p,
                      'in_grid': row is not None, 'row': row}
    return out


def _json_default(v):
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    raise TypeError('not JSON serializable: %r' % (v,))


# ---------------------------------------------------------------------------------------------
# one cell
# ---------------------------------------------------------------------------------------------
_G: dict = {}            # shared with forked workers (copy-on-write)


def _sig_inputs(sig):
    return tuple(sig[k] for k in SIGNAL_DIMS if k != 'fgfOn')


def prepare_cell(pair, tf, sig_idx=None, verbose=False):
    """hrd.prepare once per SIGNAL setting (all 54, or those of sig_idx), the 1-minute sub-bars once,
    the kernel compiled. Returns the cell: P {signal index: prepared input}, the summary columns
    and timings. The per-bar signal arrays of hrd (P['S'], hrd._SIG) are dropped: the kernel needs
    only the window's long / short signal and permission arrays."""
    tf = str(tf)
    idx = list(range(len(SIGNALS))) if sig_idx is None else [int(i) for i in sig_idx]
    t0 = time.time()
    P = {}
    for n, si in enumerate(idx):
        Pp = hrd.prepare(pair, tf, signal_params(SIGNALS[si]))
        Pp['S'] = None
        P[si] = Pp
        if n + 1 == len(idx) or _sig_inputs(SIGNALS[idx[n + 1]]) != _sig_inputs(SIGNALS[si]):
            hrd._SIG.clear()
            gc.collect()
    p0 = P[idx[0]]
    for si, Pk in P.items():
        if Pk['w0'] != p0['w0'] or Pk['w1'] != p0['w1'] or Pk['mid'] != p0['mid']:
            raise ValueError('%s %s signal setting %d: window rows differ' % (pair, tf, si))
    t_sig = time.time() - t0
    t1 = time.time()
    n_sub = 0
    if PATH == 'mag':
        sub = hrd.get_sub(p0)
        n_sub = len(sub[1])
        for Pk in P.values():
            Pk['sub'] = sub
    t_sub = time.time() - t1
    t2 = time.time()
    s = hrd.summary_fast(p0, hrd.simulate(p0, exit_params(exits_for(SIGNALS[idx[0]])[1])))   # compile / load
    t_jit = time.time() - t2
    cols = list(s.keys())
    kinds = {}
    for k, v in s.items():
        if isinstance(v, (bool, np.bool_)):
            kinds[k] = bool
        elif isinstance(v, (int, np.integer)):
            kinds[k] = np.int64
        else:
            kinds[k] = np.float64
    cell = dict(pair=pair, tf=tf, idx=idx, P=P, cols=cols, kinds=kinds, bars=int(p0['n']), n_sub=n_sub,
                t_sig=t_sig, t_sub=t_sub, t_jit=t_jit, t_prep=time.time() - t0)
    if verbose:
        print('  %s %s: %d chart bars, %d 1-minute bars; %d signal settings prepared in %.1fs, sub-bars %.1fs, '
              'kernel %.1fs' % (pair, tf, cell['bars'], n_sub, len(idx), t_sig, t_sub, t_jit), flush=True)
    return cell


def _work(task):
    si, i0, i1 = task
    t0 = time.time()
    Pp = _G['P'][si]
    X = _G['X'][si]
    cols = _G['cols']
    out = []
    for i in range(i0, i1):
        s = hrd.summary_fast(Pp, hrd.simulate(Pp, exit_params(X[i])))
        out.append(tuple(s[k] for k in cols))
    return si, i0, out, time.time() - t0


def run_prepared(cell, workers=MAX_WORKERS, sig_idx=None, chunk=CHUNK, verbose=False):
    """Simulate every exit setting of the prepared signal settings (all of the cell, or sig_idx).
    Returns (res {signal index: [summary tuple per exit setting]}, info)."""
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    X = {si: exits_for(SIGNALS[si]) for si in idx}
    _G.clear()
    _G.update(P=cell['P'], X=X, cols=cell['cols'])
    tasks = [(si, i0, min(i0 + chunk, len(X[si]))) for si in idx for i0 in range(0, len(X[si]), chunk)]
    total = sum(t[2] - t[1] for t in tasks)
    res = {si: [None] * len(X[si]) for si in idx}
    t1 = time.time()
    state = dict(done=0, busy=0.0, next=0.1)

    def collect(result):
        si, i0, out, dt = result
        res[si][i0:i0 + len(out)] = out
        state['busy'] += dt
        state['done'] += len(out)
        done = state['done']
        if verbose and (done / total >= state['next'] or done == total):
            el = time.time() - t1
            print('    %5.1f%%  %d/%d settings  %.1fs elapsed  eta %.1fs'
                  % (100.0 * done / total, done, total, el, el / done * (total - done)), flush=True)
            while state['next'] <= done / total:
                state['next'] += 0.1

    if workers <= 1:
        for t in tasks:
            collect(_work(t))
    else:
        ctx = mp.get_context('fork')
        with ctx.Pool(processes=workers) as pool:
            for result in pool.imap_unordered(_work, tasks):
                collect(result)
    for si in idx:
        if any(r is None for r in res[si]):
            raise RuntimeError('signal setting %d: missing results' % si)
    t_run = time.time() - t1
    return res, dict(settings=total, t_run=t_run, busy=state['busy'], workers=workers, tasks=len(tasks))


def frame(cell, res, sig_idx=None):
    """The rows in grid order: p_<name> per dimension, then every summary field."""
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    G = grid(idx)
    vals = [r for si in idx for r in res[si]]
    if len(G) != len(vals):
        raise RuntimeError('grid and results differ in length')
    data = {}
    for name in DIM_NAMES:
        col = [p[name] for p in G]
        ty = _DIM_TYPE[name]
        if name in UNUSED_WHEN or ty is str:
            data['p_' + name] = pd.Series(col, dtype=object)
        else:
            data['p_' + name] = pd.Series(col, dtype={bool: bool, int: np.int64, float: np.float64}[ty])
    for j, k in enumerate(cell['cols']):
        data[k] = pd.Series([v[j] for v in vals], dtype=cell['kinds'][k])
    return pd.DataFrame(data)


def _write_atomic(path, writer):
    tmp = path + '.tmp%d' % os.getpid()
    writer(tmp)
    os.replace(tmp, path)


def _sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def file_meta(pair, tf, n):
    """What produced a cell's file (stored in the parquet's key-value metadata, key "calib")."""
    return {'strategy': STRATEGY, 'pair': pair, 'tf': str(tf), 'path': PATH, 'cost': COST, 'settings': int(n),
            'window': [int(v) for v in hrd.WINDOWS[pair]],
            'hrd_sha256': _sha256(os.path.join(W, 'hrd.py')), 'fgf_sha256': _sha256(os.path.join(W, 'fgf.py'))}


def write_parquet(df, path, meta):
    """df.to_parquet(path, index=False) plus the key-value metadata "calib" (pandas ignores it)."""
    t = pa.Table.from_pandas(df, preserve_index=False)
    md = dict(t.schema.metadata or {})
    md[b'calib'] = json.dumps(meta, sort_keys=True).encode()
    pq.write_table(t.replace_schema_metadata(md), path)


def read_meta(path):
    md = pq.read_schema(path).metadata or {}
    return json.loads(md[b'calib'].decode()) if b'calib' in md else None


def write_dims(out_dir):
    path = os.path.join(out_dir, 'calib_%s_dims.json' % STRATEGY)

    def wr(tmp):
        with open(tmp, 'w') as f:
            json.dump(DIMS, f, indent=1)
            f.write('\n')
    _write_atomic(path, wr)
    return path


def run_cell(pair, tf, workers=MAX_WORKERS, out_dir=None, sig_idx=None, write=True, chunk=CHUNK, verbose=True):
    """One (pair, tf) cell: prepare, simulate the grid, write the parquet (and DIMS). sig_idx: only
    those signal settings (tests; never written). Returns (DataFrame, info)."""
    tf = str(tf)
    if write and sig_idx is not None:
        raise ValueError('a partial grid is never written')
    t0 = time.time()
    cell = prepare_cell(pair, tf, sig_idx, verbose)
    res, info = run_prepared(cell, workers, None, chunk, verbose)
    df = frame(cell, res)
    info.update(pair=pair, tf=tf, rows=len(df), bars=cell['bars'], n_sub=cell['n_sub'], t_prep=cell['t_prep'],
                t_sig=cell['t_sig'], t_sub=cell['t_sub'], t_jit=cell['t_jit'], file=None)
    if write:
        out_dir = out_dir or os.path.join(W, 'out')
        os.makedirs(out_dir, exist_ok=True)
        path_out = os.path.join(out_dir, 'calib_%s_%s_%s.parquet' % (STRATEGY, pair, tf))
        meta = file_meta(pair, tf, len(df))
        _write_atomic(path_out, lambda tmp: write_parquet(df, tmp, meta))
        write_dims(out_dir)
        info['file'] = path_out
    info['t_total'] = time.time() - t0
    if verbose:
        w = max(info['workers'], 1)
        print('  %s %s done: %d rows%s | prep %.1fs, runs %.1fs with %d workers (%.2f worker-s, %.5fs per '
              'setting per worker; workers busy %.0f%%), total %.1fs'
              % (pair, tf, len(df), (' -> ' + info['file']) if info['file'] else ' (not written)', info['t_prep'],
                 info['t_run'], w, info['busy'], info['busy'] / max(info['settings'], 1),
                 100.0 * info['busy'] / max(info['t_run'] * w, 1e-9), info['t_total']), flush=True)
    _G.clear()
    return df, info


def estimate_cell(pair, tf, workers=MAX_WORKERS, per_signal=6, seed=20261124, verbose=True):
    """Estimated time of the full cell from ONE process: the real preparation, then per_signal random
    exit settings of every signal setting timed one by one; run time = sum over the signal settings
    of (mean sampled time x its number of exit settings) / workers. Writes nothing."""
    tf = str(tf)
    cell = prepare_cell(pair, tf, None, verbose)
    rng = np.random.default_rng(seed)
    t_single = 0.0
    worst = 0.0
    n_s = 0
    t0 = time.time()
    for si in cell['idx']:
        X = exits_for(SIGNALS[si])
        Pp = cell['P'][si]
        tt = []
        for i in rng.choice(len(X), size=per_signal, replace=False):
            t = time.time()
            hrd.summary_fast(Pp, hrd.simulate(Pp, exit_params(X[int(i)])))
            tt.append(time.time() - t)
        t_single += float(np.mean(tt)) * len(X)
        worst = max(worst, max(tt))
        n_s += len(tt)
    n_all = len(grid())
    est = dict(pair=pair, tf=tf, bars=cell['bars'], n_sub=cell['n_sub'], settings=n_all, sampled=n_s,
               t_prep=cell['t_prep'], per_setting=t_single / n_all, slowest=worst, single_process_run=t_single,
               workers=workers, est_run=t_single / max(workers, 1), est_total=cell['t_prep'] + t_single / max(workers, 1),
               t_sample=time.time() - t0, load1=os.getloadavg()[0])
    if verbose:
        print('  %s %s estimate: prep %.1fs + %d settings x %.5fs (slowest sampled %.4fs; %d sampled) / %d workers '
              '= %.1fs runs -> %.1fs total (%.2f min); load average %.2f'
              % (pair, tf, est['t_prep'], n_all, est['per_setting'], worst, n_s, workers, est['est_run'],
                 est['est_total'], est['est_total'] / 60.0, est['load1']), flush=True)
    return est


# ---------------------------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------------------------
def _main_one(argv):
    ap = argparse.ArgumentParser(prog='calib_hrd.py --one', description='the full summary of one setting, as JSON')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tf', choices=TFS)
    ap.add_argument('p', help='JSON object of the p_ values of the setting')
    ap.add_argument('--path', choices=('tv', 'mag'), default=PATH)
    ap.add_argument('--cost', choices=tuple(hrd.COSTS), default=COST)
    ap.add_argument('--off-grid', action='store_true', help='accept values that are not in the grid')
    a = ap.parse_args(argv)
    try:
        raw = json.loads(a.p)
        if not isinstance(raw, dict):
            raise ValueError('the p_ values must be a JSON object')
        out = one(a.pair, a.tf, raw, a.path, a.cost, a.off_grid)
    except ValueError as e:
        print('calib_hrd.py --one: %s' % e, file=sys.stderr)
        return 2
    print(json.dumps(out, default=_json_default))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--one' in argv:
        argv.remove('--one')
        return _main_one(argv)
    ap = argparse.ArgumentParser(description='HRD v1.03 + FGF calibration grid (CALIB_SPEC.md)')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tfs', nargs='+')
    ap.add_argument('--workers', type=int, default=MAX_WORKERS)
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--estimate', action='store_true', help='time a sample in one process; write nothing')
    ap.add_argument('--per-signal', type=int, default=6, help='--estimate: sampled exit settings per signal setting')
    a = ap.parse_args(argv)
    for tf in a.tfs:
        if tf not in TFS:
            ap.error('unknown TF %r (one of %s)' % (tf, ', '.join(TFS)))
    workers = max(1, min(int(a.workers), MAX_WORKERS))
    if workers != a.workers:
        print('workers capped at %d' % workers, flush=True)
    t0 = time.time()
    for tf in a.tfs:
        if a.estimate:
            print('== calib %s %s %s: estimate ==' % (STRATEGY, a.pair, tf), flush=True)
            est = estimate_cell(a.pair, tf, workers, a.per_signal)
            print('ESTIMATE ' + json.dumps(est), flush=True)
        else:
            print('== calib %s %s %s: %d settings (%d signal x exit settings), path %s, cost %s =='
                  % (STRATEGY, a.pair, tf, len(grid()), len(SIGNALS), PATH, COST), flush=True)
            run_cell(a.pair, tf, workers, a.out_dir)
        hrd._CACHE.clear()
        hrd._PERM.clear()
        gc.collect()
    print('all done in %.1fs' % (time.time() - t0), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
