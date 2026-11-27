"""calib_xpw23.py: calibration grid of XPW Orientation TDI v2.8 (S2 / S3 exits) + FGF [Update 1] per
pair and timeframe, with the direction (Normal / Inverted, Update 1) as a calibrated input
(CALIB_SPEC.md, strategy "xpw23"; the grid is section 9 of SPEC_xpw23.md), on the canonical replica
xpw23.py (prepare / simulate / summary; its signals are xpw.xpw_signals, its filter
fgf.fgf_permissions).

Usage (python3 -I)
  calib_xpw23.py PAIR TF [TF ...] [--workers 3] [--out-dir DIR]
      runs the full grid of every (PAIR, TF) cell and writes out/calib_xpw23_<PAIR>_<TF>.parquet
      (one row per setting) and out/calib_xpw23_dims.json (DIMS). PAIR in BTC, XAU; TF in 1, 5,
      15, 30, 60, 120, 240. Safe to re-run: the files are overwritten (written to a temporary
      name first). Prints the timing of every cell.
  calib_xpw23.py --one PAIR TF '<json of p_ values>' [--path tv|mag] [--cost tv|ours|stress]
                 [--off-grid]
      prints the full summary of ONE setting as one JSON document on stdout (default path mag,
      cost ours = the sweep's scoring). The JSON of p_ values is a row's p_ columns: keys with or
      without the "p_" prefix, null (or NaN) for an unused dimension. --off-grid also accepts
      values that are not in the grid (numbers the Pine inputs accept, "enter opposite" for the
      two label dimensions, and a trail that can never arm: see below).
  calib_xpw23.py --estimate PAIR TF [TF ...] [--workers 3] [--per-signal 6]
      times the cell's preparation and a random sample of settings in ONE process and prints the
      estimated time of the full cell; writes nothing.

The grid: 16,200 settings per cell = 18 signal settings x 900 exit settings, the same in every cell
  signals   actDL_actDS {"enter", "off", "exit only"}: the two divergence rows of the script's
            "Labels" group together (actDL = actDS = the value)
            x actInf {"enter", "off", "exit only"}: the Info row (look for / staircase)
            x fgfOn {False, True}: the direction filter. This script has no blocked-signal close.
  direction inv {False, True} = xpwInv, "Inverted direction: opposite side at the same entries"
  exits     slAtrMult {1.5, 3.0, 6.0} x tpRMult {1.0, 2.0, 4.0, 0.0}; 0 = no target, listed last
            (the far end of the ordinal dimension)
            x [trailOn False (trActAtr, trDistAtr unused: None)
               | trailOn True x trActAtr {1.0, 3.0} x trDistAtr {0.75, 1.5, 3.0}]
            x timeStop {0, 24} (0 = off) x maxOpen {1, 3, 20}
  listed once: a trail that can never arm before the target fills, tpRMult > 0 and trActAtr >=
            tpRMult x slAtrMult, i.e. (slAtrMult, tpRMult) = (1.5, 1), (1.5, 2), (3, 1) with
            trActAtr 3.0: the target is nearer than (or exactly at) the activation price and is
            tested first, so the run is the run with the trail off. Those 3 x 3 = 9 combinations
            are not rows; their result is the trailOn False row (never_arms(); `--one --off-grid`
            runs one as given). 12 x 7 - 9 = 75 stop / target / trail settings, x 2 x 3 x 2 = 900.
  still a row, although it cannot differ either (section 9 does not list it; calib_tests_xpw23.py
            shows it on data): slAtrMult 1.5, tpRMult 1.0 with the trail 1.0 / 3.0. The trail arms,
            but its stop (best price - 3.0 ATR) stays below the stop loss (entry - 1.5 ATR) until
            the target (entry + 1.5 ATR) fills, so these 216 rows of every cell repeat their
            trail-off rows. They are kept: the grid is the spec's 16,200, and the rule counts
            settings with identical results once.
Everything else stays at the script's defaults: Signal tick entries, Quantity "Fixed" 0.1 unit per
entry, exit unit "ATR" with ATR length 14, Trade direction Both, signal rung = chart rung with the
READ HERE rung, the four leg rows and End-of-leg "enter", "Reverse every label" off, the filter's
own inputs. The script's default setting is a grid point: DEFAULT_P (enter, enter, filter on,
normal, stop 3.0 ATR, target 1.0 R, trail on 1.0 / 0.75 ATR, no time stop, 20 entries).

SIGNALS (18) are the parameters of xpw23.prepare (the label actions + fgfOn), EXITS (900) those of
xpw23.simulate (inv and the exits); every signal setting has all 900. DIMS = the 11 dimensions
(name, values, kind 'ordinal' / 'categorical'; extra keys: side, default, unused_when); row i of a
file is grid()[i] (for each signal setting, its exit settings).

Column floor_ok (the 1-minute noise floor of the trailing distance; SPEC_xpw23.md section 9): True
when the trail is off; with the trail on, True when trDistAtr x the median over the window of
ATR(14) / close is at least 0.1 % of price on BTC, 0.05 % on gold. The median is measured on the
data at every run (it is in the file's metadata). Rows below the floor are computed like the others
(the product, DIMS and the default row are the same in every cell); the rule's pool takes floor_ok
rows only: trDistAtr 3.0 on the 1-minute charts (7,128 rows), 1.5 and 3.0 on the 5-minute charts
(11,664), every row from 15 minutes up.

Every setting is scored with path 'mag' (exit orders walked along the 1-minute sub-bars; on chart
"1" each bar is its own sub-bar) and cost 'ours'. Money model = xpw23.summary: 10,000 account, a
fixed 0.1 unit per entry, no compounding, so the fair halves h1r_pct / h2r_pct are additive sums of
the profit of the trades entered in each half, in % of 10,000 (halves_rule 'additive' on every
row: checked); net_R, h1_R, h2_R give the same in R (profit / the stop distance of the entry).
Per cell: xpw23.prepare runs ONCE per signal setting (18 times; the two filter states of one label
setting share one xpw.xpw_signals call, 9 per cell), the prepared inputs are slimmed (the label
texts are dropped, arrays that are equal between signal settings are kept once), the 1-minute
sub-bars and ATR(14) are built once, the kernel is compiled, and only then at most 3 workers are
forked (copy-on-write); each simulates chunks of exit settings of one prepared input
(xpw23.simulate + xpw23.summary) and checks that the module ran the setting it was asked to run.
Rows are assembled in grid order, so the file does not depend on the worker count.

Output columns: p_<name> for every dimension of DIMS, in DIMS order (null = None), floor_ok, then
every numeric field of xpw23.summary in its own order: start, end, bars, trades, net_pct, pf,
win_pct, max_dd_pct, max_dd_init_pct, long, short (REAL sides), raw_long, raw_short, blocked_long,
blocked_short (the label's side), exit_<kind> counts (sl, tp, trail, time, close_all, reverse,
end), avg_bars_held, exposure, half1_pct, half2_pct, h1_trades, h2_trades, h1r_pct, h2r_pct (the
fair halves), final_equity, costs, net_R, h1_R, h2_R, n_R, placed, skipped_room, skipped_qty, the
pend_* counts (0: Signal tick), close_all_bars, max_open, zero_length, max_expo, margin_bars,
fifo_exits, pend_ghosts, pend_cancel_stale, pend_cancel_against, reverse_bars, reverse_over_room,
labels_long, labels_short, both_cancel_bars. The five text fields of the summary (pair, tf,
halves_rule, path, cost) are the same on every row of a file and are in the parquet's key-value
metadata "calib" (with the strategy, the number of settings, the window, the fixed inputs, the
floor measurement and the sha256 of xpw23.py, xpw.py and fgf.py that produced the rows). Nothing
else: no index. pf is +inf without a losing trade and NaN without trades; win_pct and
avg_bars_held are NaN without trades. net_pct and max_dd_pct are in % of 10,000 and may pass
100 in either direction (no margin model: xpw23_notes.md, T11). --one prints floor_ok and the same
fields (Python's json: Infinity / NaN) plus "setting" = {strategy, pair, tf, path, cost, p (the
canonical p_ values), in_grid, row (its row number in the grid file), halves_rule, fixed (the
fixed inputs as the module resolved them), median_atr_pct, floor_pct}.
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
import pyarrow as pa
import pyarrow.parquet as pq

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import xpw23  # noqa: E402  (imports xpw, fgf)
import xpw    # noqa: E402
import fgf    # noqa: E402

STRATEGY = 'xpw23'
MAX_WORKERS = 3
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
PATH = 'mag'             # the sweep's scoring: 1-minute fills ...
COST = 'ours'            # ... with our costs
CHUNK = 30               # exit settings per worker task

# ---------------------------------------------------------------------------------------------
# the grid (SPEC_xpw23.md section 9)
# ---------------------------------------------------------------------------------------------
ACTIONS = ('enter', 'off', 'exit only')      # actDL = actDS (together), and actInf
FILTERS = (False, True)
INVS = (False, True)
SL_MULTS = (1.5, 3.0, 6.0)
TP_MULTS = (1.0, 2.0, 4.0, 0.0)              # 0 = no target, the far end
TRAILS = (False, True)
TR_ACTS = (1.0, 3.0)
TR_DISTS = (0.75, 1.5, 3.0)
TIME_STOPS = (0, 24)                         # 0 = off
MAX_OPENS = (1, 3, 20)

# fixed for every row: the script's defaults, given to xpw23.simulate explicitly
FIXED_X = {'tradeDir': 'Both', 'oppCloses': True, 'entryFill': 'Signal tick', 'exitUnit': 'ATR', 'atrLen': 14,
           'qtyMode': 'Fixed', 'qtyFixed': 0.1}
HALVES_RULE = 'additive'                     # Fixed quantity: the fair halves are sums (xpw23.summary)
ATR_LEN = 14                                 # the floor's ATR = the exits' ATR
FLOOR_PCT = {'BTC': 0.1, 'XAU': 0.05}        # 1-minute noise floor of a trailing distance, % of price

# name, values, kind as CALIB_SPEC.md asks; extra keys (as calib_hrd.py / calib_danny.py): side =
# 'signal' (a parameter of xpw23.prepare) or 'exit' (of xpw23.simulate), default = the script's
# default input, unused_when = the value of another dimension with which this one is listed once
# (its value is None)
DIMS = [
    {'name': 'actDL_actDS', 'values': list(ACTIONS), 'kind': 'categorical', 'side': 'signal', 'default': 'enter'},
    {'name': 'actInf', 'values': list(ACTIONS), 'kind': 'categorical', 'side': 'signal', 'default': 'enter'},
    {'name': 'fgfOn', 'values': list(FILTERS), 'kind': 'categorical', 'side': 'signal', 'default': True},
    {'name': 'inv', 'values': list(INVS), 'kind': 'categorical', 'side': 'exit', 'default': False},
    {'name': 'slAtrMult', 'values': list(SL_MULTS), 'kind': 'ordinal', 'side': 'exit', 'default': 3.0},
    {'name': 'tpRMult', 'values': list(TP_MULTS), 'kind': 'ordinal', 'side': 'exit', 'default': 1.0},   # 0 = no target, last
    {'name': 'trailOn', 'values': list(TRAILS), 'kind': 'categorical', 'side': 'exit', 'default': True},
    {'name': 'trActAtr', 'values': list(TR_ACTS), 'kind': 'ordinal', 'side': 'exit', 'default': 1.0,
     'unused_when': {'trailOn': False}},
    {'name': 'trDistAtr', 'values': list(TR_DISTS), 'kind': 'ordinal', 'side': 'exit', 'default': 0.75,
     'unused_when': {'trailOn': False}},
    {'name': 'timeStop', 'values': list(TIME_STOPS), 'kind': 'ordinal', 'side': 'exit', 'default': 0},
    {'name': 'maxOpen', 'values': list(MAX_OPENS), 'kind': 'ordinal', 'side': 'exit', 'default': 20},
]
DIM_NAMES = [d['name'] for d in DIMS]
SIGNAL_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'signal')
EXIT_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'exit')
# a dimension is listed once (None) when another one has this value
UNUSED_WHEN = {d['name']: next(iter(d['unused_when'].items())) for d in DIMS if 'unused_when' in d}
DIM_DOC = {
    'actDL_actDS': 'Labels: Divergence LONG zone and Divergence SHORT zone, what the strategy does on them (both rows together)',
    'actInf': 'Labels: Info (look for / stair), what the strategy does on it',
    'fgfOn': 'direction filter: Enable filter',
    'inv': 'Inverted direction: opposite side at the same entries (Update 1, xpwInv)',
    'slAtrMult': 'Stop loss, ATR(14) multiples',
    'tpRMult': 'Take profit, R multiple of the stop distance (0 = no target)',
    'trailOn': 'Trailing stop',
    'trActAtr': 'Trail activation, ATR(14) multiples of profit (None: trailing off)',
    'trDistAtr': 'Trail distance, ATR(14) multiples (None: trailing off)',
    'timeStop': 'Time stop, bars (0 = off)',
    'maxOpen': 'Max open entries',
}
_DIM_TYPE = {'actDL_actDS': str, 'actInf': str, 'fgfOn': bool, 'inv': bool, 'slAtrMult': float, 'tpRMult': float,
             'trailOn': bool, 'trActAtr': float, 'trDistAtr': float, 'timeStop': int, 'maxOpen': int}
_PA_TYPE = {str: pa.string(), int: pa.int64(), float: pa.float64(), bool: pa.bool_()}

# The default setting = the script's default inputs (the Pine's input defaults): a grid point.
DEFAULT_P = {d['name']: d['default'] for d in DIMS}
DEFAULT = DEFAULT_P


def never_arms(sl, tp, act):
    """A trail that can never arm before the target fills: the target (tp x sl ATR from the entry) is
    not farther than the activation price (act ATR), and the target is tested first. Such a run is
    the run with the trail off, so the grid lists it once (as trailOn False)."""
    return tp > 0.0 and act >= tp * sl


def trails_for(sl, tp):
    """The (trailOn, trActAtr, trDistAtr) settings of one (slAtrMult, tpRMult): trail off, then every
    activation x distance whose trail can arm."""
    return [(False, None, None)] + [(True, a, d) for a in TR_ACTS for d in TR_DISTS if not never_arms(sl, tp, a)]


# SIGNAL settings: the parameters of xpw23.prepare. fgfOn is the innermost loop: the two filter
# states of one label setting share its xpw.xpw_signals call.
SIGNALS = [{'actDL_actDS': a, 'actInf': b, 'fgfOn': f} for a in ACTIONS for b in ACTIONS for f in FILTERS]
# EXIT settings: the parameters of xpw23.simulate, in DIMS order.
EXITS = [{'inv': i, 'slAtrMult': s, 'tpRMult': t, 'trailOn': ton, 'trActAtr': ta, 'trDistAtr': td, 'timeStop': ts,
          'maxOpen': mo}
         for i in INVS for s in SL_MULTS for t in TP_MULTS for (ton, ta, td) in trails_for(s, t)
         for ts in TIME_STOPS for mo in MAX_OPENS]
N_GRID = len(SIGNALS) * len(EXITS)           # 16,200


def exits_for(sig=None):
    """The EXIT settings of a SIGNAL setting: all of them, for every signal setting."""
    return EXITS


def merge(sig, x):
    """One grid setting: every dimension of DIMS, in DIMS order."""
    d = dict(sig)
    d.update(x)
    return {k: d[k] for k in DIM_NAMES}


def grid(sig_idx=None):
    """Every setting, in file order: for each SIGNAL setting, its EXIT settings."""
    idx = range(len(SIGNALS)) if sig_idx is None else sig_idx
    return [merge(SIGNALS[si], x) for si in idx for x in EXITS]


def key(p):
    return tuple(p[k] for k in DIM_NAMES)


def signal_params(sig):
    """A SIGNAL setting as xpw23.prepare params (everything else at the script's defaults)."""
    return {'actDL': str(sig['actDL_actDS']), 'actDS': str(sig['actDL_actDS']), 'actInf': str(sig['actInf']),
            'fgfOn': bool(sig['fgfOn'])}


def exit_params(x, path=PATH, cost=COST):
    """An EXIT setting as xpw23.simulate params: the fixed inputs (FIXED_X), the swept ones, path and
    cost. trActAtr / trDistAtr are only given with the trail on (off: the script's defaults, which
    the kernel does not read)."""
    X = dict(FIXED_X)
    X.update(xpwInv=bool(x['inv']), slAtrMult=float(x['slAtrMult']), tpRMult=float(x['tpRMult']),
             trailOn=bool(x['trailOn']), timeStop=int(x['timeStop']), maxOpen=int(x['maxOpen']), path=path, cost=cost)
    if x['trailOn']:
        X['trActAtr'] = float(x['trActAtr'])
        X['trDistAtr'] = float(x['trDistAtr'])
    return X


def _num(v):
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, (bool, np.bool_))


def normalize(raw, off_grid=False):
    """A setting given as a mapping of p_ values (keys with or without 'p_'; None / NaN / missing =
    unused) -> the canonical dict over DIM_NAMES. trActAtr / trDistAtr with the trail off are set to
    None whatever was given (they cannot change the result). Raises ValueError for an unknown key, a
    missing used dimension, a value of the wrong type, or (unless off_grid) a value that is not in
    the grid or a trail that can never arm (the grid lists that run once, as trailOn false)."""
    if not isinstance(raw, dict):
        raise ValueError('the p_ values must be a JSON object')
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
            if not (isinstance(v, (bool, np.bool_)) or (_num(v) and v in (0, 1))):
                raise ValueError('%s: %r is not a boolean' % (name, v))
            v = bool(v)
        elif ty is int:
            if not _num(v) or int(v) != v:
                raise ValueError('%s: %r is not an integer' % (name, v))
            v = int(v)
        elif ty is float:
            if not _num(v) or not math.isfinite(v):
                raise ValueError('%s: %r is not a number' % (name, v))
            v = float(v)
        else:
            v = str(v)
        if v not in d['values']:
            if not off_grid or ty is bool:
                raise ValueError('%s: %r is not in the grid %r' % (name, v, d['values']))
            if ty is str and v not in xpw.ACTS:
                raise ValueError('%s: %r is not one of %r' % (name, v, list(xpw.ACTS)))
        out[name] = v
    if out['trailOn'] and never_arms(out['slAtrMult'], out['tpRMult'], out['trActAtr']) and not off_grid:
        raise ValueError('trailOn true with trActAtr %g, slAtrMult %g, tpRMult %g is not in the grid: the trail can '
                         'never arm before the target fills, so the run is the trailOn false row (listed once); '
                         '--off-grid runs it as given' % (out['trActAtr'], out['slAtrMult'], out['tpRMult']))
    return out


_ROWS: dict = {}


def row_of(p):
    """The row number of a setting in a cell's grid file (grid() order), None when it is not a row."""
    if not _ROWS:
        _ROWS.update((key(q), i) for i, q in enumerate(grid()))
    return _ROWS.get(key(p))


def in_grid(p):
    return row_of(p) is not None


# ---------------------------------------------------------------------------------------------
# what a run must echo; the floor of the trailing distance
# ---------------------------------------------------------------------------------------------
def _check_prepared(sig, Pp):
    """xpw23.prepare ran the SIGNAL setting it was asked for, on the pair's window, with every other
    signal / filter input at the module's default."""
    Q = Pp['params']
    want = dict(xpw.DEFAULTS)
    want.update(fgf.DEFAULTS)
    want.update(signal_params(sig))
    want.update(start=xpw23.WINDOWS[Pp['pair']][0], end=xpw23.WINDOWS[Pp['pair']][1])
    if Q != want:
        raise RuntimeError('xpw23.prepare did not run the signal setting %r: %r'
                           % (sig, {k: (Q.get(k), want.get(k)) for k in set(Q) | set(want) if Q.get(k) != want.get(k)}))


def _check_run(X, R):
    """xpw23.simulate ran the EXIT setting it was asked for: its resolved inputs (R['x']) hold every
    value given (the fixed inputs included)."""
    q = R['x']
    for k, v in X.items():
        if q[k] != v:
            raise RuntimeError('xpw23.simulate did not run %r: %s is %r' % (X, k, q[k]))


def cell_floor(pair, Pp):
    """The 1-minute noise floor of the cell: the median over the window of ATR(14) / close in %; a
    trailing distance of d ATR meets the floor when d x that median >= FLOOR_PCT[pair]."""
    atr = xpw23.atr_window(Pp, ATR_LEN)
    r = atr / Pp['close'] * 100.0
    if not np.isfinite(r).all():
        raise ValueError('%s %s: ATR(%d) / close is not finite on every window bar' % (pair, Pp['tf'], ATR_LEN))
    med = float(np.median(r))
    return {'atr_len': ATR_LEN, 'median_atr_pct': med, 'floor_pct': FLOOR_PCT[pair],
            'dist_ok': {'%g' % d: bool(d * med >= FLOOR_PCT[pair]) for d in TR_DISTS}}


def floor_ok(x, floor):
    """floor_ok of one setting: True with the trail off, else trDistAtr x the median >= the floor."""
    if not x['trailOn']:
        return True
    return bool(float(x['trDistAtr']) * floor['median_atr_pct'] >= floor['floor_pct'])


# the text fields of xpw23.summary: the same on every row of a cell, kept in the file's metadata
TEXT_FIELDS = ('pair', 'tf', 'halves_rule', 'path', 'cost')


def _row(Pp, R, path=PATH, cost=COST):
    """xpw23.summary of a run, its text fields checked against what the row claims."""
    s = xpw23.summary(Pp, R)
    if (s['pair'], s['tf'], s['halves_rule'], s['path'], s['cost']) != (Pp['pair'], Pp['tf'], HALVES_RULE, path, cost):
        raise RuntimeError('xpw23.summary: %r' % ({k: s[k] for k in TEXT_FIELDS},))
    return s


# ---------------------------------------------------------------------------------------------
# one setting
# ---------------------------------------------------------------------------------------------
def one(pair, tf, p, path=PATH, cost=COST, off_grid=False, cache=None):
    """The full summary (xpw23.summary) of one setting, computed alone: its own xpw23.prepare and one
    xpw23.simulate. p: a mapping of p_ values (see normalize). cache: a dict that keeps the prepared
    inputs between calls of one process (tests)."""
    tf = str(tf)
    p = normalize(p, off_grid)
    sig = {k: p[k] for k in SIGNAL_DIMS}
    x = {k: p[k] for k in EXIT_DIMS}
    sp = signal_params(sig)
    ck = (pair, tf, tuple(sorted(sp.items())))
    Pp = cache.get(ck) if cache is not None else None
    if Pp is None:
        Pp = xpw23.prepare(pair, tf, sp)
        if cache is not None:
            cache[ck] = Pp
    _check_prepared(sig, Pp)
    X = exit_params(x, path, cost)
    R = xpw23.simulate(Pp, X)
    _check_run(X, R)
    s = _row(Pp, R, path, cost)
    fl = cell_floor(pair, Pp)
    out = {'floor_ok': floor_ok(x, fl)}
    out.update((k, v) for k, v in s.items() if k not in TEXT_FIELDS)
    out['setting'] = {'strategy': STRATEGY, 'pair': pair, 'tf': tf, 'path': path, 'cost': cost, 'p': p,
                      'in_grid': in_grid(p), 'row': row_of(p), 'halves_rule': s['halves_rule'],
                      'fixed': {k: R['x'][k] for k in FIXED_X}, 'median_atr_pct': fl['median_atr_pct'],
                      'floor_pct': fl['floor_pct']}
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
# arrays of a prepared input that the kernel and the summary read; equal ones are kept once per cell
_ARRAYS = ('open', 'high', 'low', 'close', 't_open', 't_close', 'rows', 'nLong', 'nShort', 'nLongRaw', 'nShortRaw',
           'exitL', 'exitS', 'buyOk', 'sellOk')
# what only xpw23.trades reads (the label texts of every entry): not needed for a summary
_DROP = ('long_ptr', 'long_code', 'short_ptr', 'short_code', 'exitL_code', 'exitS_code', 'src_table')


def _slim(Pp, pool):
    """Drop the label-text tables of a prepared input and replace every array that equals one already
    seen in this cell by that one (the bars, the permissions of the same filter state, label counts
    shared between signal settings). An array that is a view (xpw23 hands out the label counts as
    views of the signal frame's column block: about 170 MB kept alive per label setting on a
    1-minute chart) is first copied to its own memory, so that only its values are kept."""
    for k in _DROP:
        Pp[k] = None
    for k in _ARRAYS:
        a = Pp[k]
        seen = pool.setdefault(k, [])
        for b in seen:
            if b is a or (b.dtype == a.dtype and b.shape == a.shape and np.array_equal(a, b)):
                Pp[k] = b
                break
        else:
            if not a.flags.owndata:
                a = np.ascontiguousarray(a).copy()
                Pp[k] = a
            seen.append(a)


def _sig_input(sig):
    return tuple(sig[k] for k in SIGNAL_DIMS if k != 'fgfOn')


def free(deep=True):
    """Drop the caches of the replica modules (between cells; results never change)."""
    _G.clear()
    xpw23.free_caches(deep=deep)


def prepare_cell(pair, tf, sig_idx=None, verbose=False):
    """xpw23.prepare once per SIGNAL setting of the cell (all, or those of sig_idx), the 1-minute
    sub-bars and ATR(14) once, the floor of the trailing distances, the kernel compiled. Returns the
    cell: P {signal index: prepared input}, the summary columns and timings."""
    tf = str(tf)
    idx = list(range(len(SIGNALS))) if sig_idx is None else [int(i) for i in sig_idx]
    t0 = time.time()
    c0 = time.process_time()
    P = {}
    pool = {}
    for n, si in enumerate(idx):
        sig = SIGNALS[si]
        Pp = xpw23.prepare(pair, tf, signal_params(sig))
        _check_prepared(sig, Pp)
        _slim(Pp, pool)
        P[si] = Pp
        if n + 1 == len(idx) or _sig_input(SIGNALS[idx[n + 1]]) != _sig_input(sig):
            # the label setting is done (both filter states): drop its xpw_signals tables from the
            # module's cache and hand the memory back (one call on a 1-minute chart peaks near 2.4 GB)
            xpw23.free_caches(deep=False)
    p0 = P[idx[0]]
    for si, Pk in P.items():
        if (Pk['w0'], Pk['w1'], Pk['mid'], Pk['mid_j'], Pk['n']) != (p0['w0'], p0['w1'], p0['mid'], p0['mid_j'], p0['n']):
            raise ValueError('%s %s signal setting %d: window rows differ' % (pair, tf, si))
        Pk['_atr'] = p0['_atr']                    # one ATR cache per cell (same bars, same window)
    t_sig = time.time() - t0
    t1 = time.time()
    n_sub = 0
    if PATH == 'mag':
        sub = xpw23.get_sub(p0)                    # built once, checked against the chart bars
        n_sub = len(sub[1])
        for Pk in P.values():
            Pk['sub'] = sub
    floor = cell_floor(pair, p0)
    t_sub = time.time() - t1
    t2 = time.time()
    X0 = exit_params(EXITS[0])
    R0 = xpw23.simulate(p0, X0)                    # compile / load the kernel before forking
    _check_run(X0, R0)
    s = _row(p0, R0)
    t_jit = time.time() - t2
    cols = [k for k in s if k not in TEXT_FIELDS]
    kinds = {}
    for k in cols:
        v = s[k]
        if isinstance(v, (bool, np.bool_, str)):
            raise RuntimeError('xpw23.summary field %r is not a number: %r' % (k, v))
        kinds[k] = int if isinstance(v, (int, np.integer)) else float
    free(deep=True)                                # the rung states and the filter series: not needed any more
    cell = dict(pair=pair, tf=tf, idx=idx, P=P, cols=cols, kinds=kinds, bars=int(p0['n']), n_sub=n_sub, floor=floor,
                prepares=len(idx), signal_inputs=len(set(_sig_input(SIGNALS[si]) for si in idx)), t_sig=t_sig,
                t_sub=t_sub, t_jit=t_jit, t_prep=time.time() - t0, cpu_prep=time.process_time() - c0)
    if verbose:
        lab = sorted(int(Pk['nLong'].sum() + Pk['nShort'].sum()) for Pk in P.values())
        print('  %s %s: %d chart bars, %d 1-minute bars; %d signal settings prepared in %.1fs (%d label settings = '
              'xpw_signals calls; %d .. %d entry labels), sub-bars + ATR %.1fs, kernel %.1fs'
              % (pair, tf, cell['bars'], n_sub, len(idx), t_sig, cell['signal_inputs'], lab[0], lab[-1], t_sub, t_jit),
              flush=True)
        print('  floor: median ATR(%d) / close over the window %.4f %%; trailing distance x that >= %.2f %% of price: %s'
              % (ATR_LEN, floor['median_atr_pct'], floor['floor_pct'],
                 ', '.join('trDistAtr %s: %.4f %% %s' % (d, float(d) * floor['median_atr_pct'], 'ok' if ok else 'BELOW')
                           for d, ok in floor['dist_ok'].items())), flush=True)
    return cell


def _work(task):
    si, i0, i1 = task
    t0 = time.time()
    c0 = time.process_time()
    Pp = _G['P'][si]
    cols = _G['cols']
    out = []
    for i in range(i0, i1):
        X = exit_params(EXITS[i])
        R = xpw23.simulate(Pp, X)
        _check_run(X, R)
        s = _row(Pp, R)
        out.append(tuple(s[k] for k in cols))
    return si, i0, out, time.time() - t0, time.process_time() - c0


def run_prepared(cell, workers=MAX_WORKERS, sig_idx=None, chunk=CHUNK, verbose=False):
    """Simulate every exit setting of the prepared signal settings (all of the cell, or sig_idx).
    Returns (res {signal index: [summary tuple per exit setting]}, info)."""
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    _G.clear()
    _G.update(P=cell['P'], cols=cell['cols'])
    nx = len(EXITS)
    tasks = [(si, i0, min(i0 + chunk, nx)) for si in idx for i0 in range(0, nx, chunk)]
    total = sum(t[2] - t[1] for t in tasks)
    res = {si: [None] * nx for si in idx}
    t1 = time.time()
    state = dict(done=0, busy=0.0, cpu=0.0, next=0.1)

    def collect(result):
        si, i0, out, dt, cpu = result
        res[si][i0:i0 + len(out)] = out
        state['busy'] += dt
        state['cpu'] += cpu
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
    return res, dict(settings=total, t_run=t_run, busy=state['busy'], cpu=state['cpu'], workers=workers,
                     tasks=len(tasks))


def table(cell, res, sig_idx=None):
    """The rows in grid order as an arrow table: p_<name> per dimension (null = None), floor_ok, then
    every numeric summary field. Column types are fixed here (they do not depend on the values)."""
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    G = grid(idx)
    vals = [r for si in idx for r in res[si]]
    if len(G) != len(vals):
        raise RuntimeError('grid and results differ in length')
    names, arrays = [], []
    for name in DIM_NAMES:
        names.append('p_' + name)
        arrays.append(pa.array([p[name] for p in G], type=_PA_TYPE[_DIM_TYPE[name]]))
    names.append('floor_ok')
    arrays.append(pa.array([floor_ok(p, cell['floor']) for p in G], type=pa.bool_()))
    for j, k in enumerate(cell['cols']):
        col = [v[j] for v in vals]
        names.append(k)
        if cell['kinds'][k] is float:
            arrays.append(pa.array(np.asarray(col, dtype=np.float64), type=pa.float64()))     # NaN stays NaN, not null
        else:
            arrays.append(pa.array(col, type=pa.int64()))
    return pa.Table.from_arrays(arrays, names=names)


def frame(cell, res, sig_idx=None):
    """table() as the DataFrame that pd.read_parquet gives for the file."""
    return table(cell, res, sig_idx).to_pandas()


def _write_atomic(path, writer):
    tmp = path + '.tmp%d' % os.getpid()
    writer(tmp)
    os.replace(tmp, path)


def _sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


SRC_FILES = ('xpw23.py', 'xpw.py', 'fgf.py')


def file_meta(pair, tf, n, floor=None):
    """What produced a cell's file (stored in the parquet's key-value metadata, key "calib")."""
    m = {'strategy': STRATEGY, 'pair': pair, 'tf': str(tf), 'path': PATH, 'cost': COST, 'settings': int(n),
         'window': [int(v) for v in xpw23.WINDOWS[pair]], 'halves_rule': HALVES_RULE, 'fixed': dict(FIXED_X),
         'floor': floor}
    for f in SRC_FILES:
        m[f[:-3] + '_sha256'] = _sha256(os.path.join(W, f))
    return m


def write_parquet(t, path, meta):
    """The arrow table to a parquet file, plus the key-value metadata "calib"."""
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
    t = table(cell, res)
    df = t.to_pandas()
    info.update(pair=pair, tf=tf, rows=len(df), bars=cell['bars'], n_sub=cell['n_sub'], t_prep=cell['t_prep'],
                cpu_prep=cell['cpu_prep'], t_sig=cell['t_sig'], t_sub=cell['t_sub'], t_jit=cell['t_jit'],
                prepares=cell['prepares'], signal_inputs=cell['signal_inputs'], floor=cell['floor'], file=None)
    if write:
        if len(df) != N_GRID:
            raise RuntimeError('%s %s: %d rows, the grid has %d' % (pair, tf, len(df), N_GRID))
        out_dir = out_dir or os.path.join(W, 'out')
        os.makedirs(out_dir, exist_ok=True)
        path_out = os.path.join(out_dir, 'calib_%s_%s_%s.parquet' % (STRATEGY, pair, tf))
        meta = file_meta(pair, tf, len(df), cell['floor'])
        _write_atomic(path_out, lambda tmp: write_parquet(t, tmp, meta))
        write_dims(out_dir)
        info['file'] = path_out
    info['t_total'] = time.time() - t0
    fl = df['floor_ok'].to_numpy(bool)
    thick = ((df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).to_numpy(bool)
    info['rows_floor_ok'] = int(fl.sum())
    info['rows_30_trades_each_half'] = int(thick.sum())
    info['rows_floor_ok_30_trades'] = int((fl & thick).sum())
    if verbose:
        w = max(info['workers'], 1)
        print('  %s %s done: %d rows%s | prep %.1fs, runs %.1fs with %d workers (%.2f worker-s busy, %.2f s CPU = '
              '%.5fs CPU per setting; workers busy %.0f%% of the run), total %.1fs; load average %.2f'
              % (pair, tf, len(df), (' -> ' + info['file']) if info['file'] else ' (not written)', info['t_prep'],
                 info['t_run'], w, info['busy'], info['cpu'], info['cpu'] / max(info['settings'], 1),
                 100.0 * info['busy'] / max(info['t_run'] * w, 1e-9), info['t_total'], os.getloadavg()[0]), flush=True)
        print('  rows in the rule\'s pool (floor_ok): %d of %d; rows with at least 30 trades entered in each half: %d '
              '(%d of them in the pool)'
              % (info['rows_floor_ok'], len(df), info['rows_30_trades_each_half'], info['rows_floor_ok_30_trades']),
              flush=True)
    _G.clear()
    return df, info


def estimate_cell(pair, tf, workers=MAX_WORKERS, per_signal=6, seed=20261126, verbose=True):
    """Estimated time of the full cell from ONE process: the real preparation, then per_signal random
    exit settings of every signal setting timed one by one; run time = sum over the signal settings
    of (mean sampled time x its number of exit settings) / workers. Two estimates: from the wall
    clock (the machine as loaded as it is now) and from this process' CPU time (the 3 workers each
    having a free CPU). Writes nothing."""
    tf = str(tf)
    cell = prepare_cell(pair, tf, None, verbose)
    rng = np.random.default_rng(seed)
    t_single = 0.0
    c_single = 0.0
    worst = 0.0
    n_s = 0
    n_thin = 0
    t0 = time.time()
    for si in cell['idx']:
        Pp = cell['P'][si]
        tt = []
        cc = []
        for i in rng.choice(len(EXITS), size=min(per_signal, len(EXITS)), replace=False):
            t = time.time()
            c = time.process_time()
            X = exit_params(EXITS[int(i)])
            R = xpw23.simulate(Pp, X)
            _check_run(X, R)
            sm = _row(Pp, R)
            tt.append(time.time() - t)
            cc.append(time.process_time() - c)
            n_thin += sm['h1_trades'] < 30 or sm['h2_trades'] < 30
        t_single += float(np.mean(tt)) * len(EXITS)
        c_single += float(np.mean(cc)) * len(EXITS)
        worst = max(worst, max(tt))
        n_s += len(tt)
    w = max(workers, 1)
    est = dict(pair=pair, tf=tf, bars=cell['bars'], n_sub=cell['n_sub'], settings=N_GRID, sampled=n_s,
               t_prep=cell['t_prep'], per_setting=t_single / N_GRID, slowest=worst, single_process_run=t_single,
               workers=workers, est_run=t_single / w, est_total=cell['t_prep'] + t_single / w,
               cpu_prep=cell['cpu_prep'], cpu_per_setting=c_single / N_GRID,
               est_total_free_cpus=cell['cpu_prep'] + c_single / w,
               sampled_under_30_trades_in_a_half=int(n_thin), median_atr_pct=cell['floor']['median_atr_pct'],
               t_sample=time.time() - t0, load1=os.getloadavg()[0])
    if verbose:
        print('  %s %s estimate: prep %.1fs + %d settings x %.5fs (slowest sampled %.4fs; %d sampled) / %d workers '
              '= %.1fs runs -> %.1fs total (%.2f min) at the present load (load average %.2f); by CPU time: prep '
              '%.1fs + %d x %.5fs / %d -> %.1fs (%.2f min) with a free CPU per worker'
              % (pair, tf, est['t_prep'], N_GRID, est['per_setting'], worst, n_s, workers, est['est_run'],
                 est['est_total'], est['est_total'] / 60.0, est['load1'], est['cpu_prep'], N_GRID,
                 est['cpu_per_setting'], workers, est['est_total_free_cpus'], est['est_total_free_cpus'] / 60.0),
              flush=True)
        print('  of the %d sampled settings: %d with fewer than 30 trades in a half' % (n_s, n_thin), flush=True)
    return est


# ---------------------------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------------------------
def _main_one(argv):
    ap = argparse.ArgumentParser(prog='calib_xpw23.py --one', description='the full summary of one setting, as JSON')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tf', choices=TFS)
    ap.add_argument('p', help='JSON object of the p_ values of the setting')
    ap.add_argument('--path', choices=('tv', 'mag'), default=PATH)
    ap.add_argument('--cost', choices=tuple(xpw23.COSTS), default=COST)
    ap.add_argument('--off-grid', action='store_true', help='accept values that are not in the grid')
    a = ap.parse_args(argv)
    try:
        raw = json.loads(a.p)
        out = one(a.pair, a.tf, raw, a.path, a.cost, a.off_grid)
    except ValueError as e:
        print('calib_xpw23.py --one: %s' % e, file=sys.stderr)
        return 2
    print(json.dumps(out, default=_json_default))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--one' in argv:
        argv.remove('--one')
        return _main_one(argv)
    ap = argparse.ArgumentParser(description='XPW v2.8 (S2 / S3 exits) + FGF calibration grid (CALIB_SPEC.md)')
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
            print('== calib %s %s %s: %d settings (%d signal settings x %d exit settings), path %s, cost %s =='
                  % (STRATEGY, a.pair, tf, N_GRID, len(SIGNALS), len(EXITS), PATH, COST), flush=True)
            run_cell(a.pair, tf, workers, a.out_dir)
        free()
        gc.collect()
    print('all done in %.1fs' % (time.time() - t0), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
