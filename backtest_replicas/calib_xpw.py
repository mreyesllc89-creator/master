"""calib_xpw.py: calibration grid of XPW v2.8 trailing-TP + FlashGold Direction Filter per pair and
timeframe, with the direction (Normal / Inverted, Update 1) as a calibrated input (CALIB_SPEC.md,
strategy "xpw"), on the verified replica: xpw.py (labels), fgf.py (filter permissions), engine.py
(orders) and sweep_core.py (the fast path: run_cfg, the Bar Magnifier kernel, metrics_fast).

Usage
  python3 -I calib_xpw.py PAIR TF [TF ...] [--workers 3] [--out-dir DIR]
      runs the full grid of every (PAIR, TF) cell and writes out/calib_xpw_<PAIR>_<TF>.parquet
      (one row per setting) and out/calib_xpw_dims.json (DIMS). PAIR in BTC, XAU; TF in 1, 5, 15,
      30, 60, 120, 240. Safe to re-run: the files are overwritten (written to a temp name first).
  python3 -I calib_xpw.py --one PAIR TF '<json of p_ values>' [--path tv|mag] [--cost tv|ours|stress]
      prints the full summary of ONE setting as one JSON document on stdout (default path mag,
      cost ours = the sweep's scoring). The JSON of p_ values is a row's p_ columns: keys with or
      without the "p_" prefix, null (or NaN) for an unused dimension. --off-grid also accepts
      values that are not in the grid (any rsiLen >= 1, distances >= 0, maxOpen 1..100) and the
      extra key "trailUnit" ("percent" | "price" | "ticks"; the grid is all "percent"): the
      script's own default exits are {"trailOn": true, "trailAct": 2, "trailOff": 1,
      "trailUnit": "price", "slOn": false, "maxOpen": 20} (SCRIPT_DEFAULT), which is NOT a grid row.
  python3 -I calib_xpw.py --estimate PAIR TF [TF ...] [--workers 3] [--per-signal 6]
      times the cell's real preparation and a random sample of settings in ONE process and prints
      the estimated time of the full cell; writes nothing.

The grid: 27,216 settings per cell = 18 signal inputs x 3 filter modes x 2 directions x 252 exits
  signals   rsiLen {8, 13, 21} x lblRead {True, False} x labels {all, legs, div}
            rsiLen  = "RSI length" (TDI core); lblRead = "Also trade / label the READ HERE rung";
            labels  = which labels trade, through the script's own per-label action inputs:
                      all  = every act* at its default ("enter");
                      legs = actDL and actDS "off" (the two divergence labels do nothing);
                      div  = actL1, actL2, actS1, actS2 "off" (the four leg labels do nothing).
  filter    fgfOn False (blkClose unused: None) | fgfOn True x blkClose {True, False}
            (fgfBlkClose, "Blocked entry still closes the other side")
  direction inv {False, True} (xpwInv, "Inverted direction"); "Reverse every label" stays off
  exits     trailUnit "percent" (% of the entry price) for every distance:
            [trailOn False (trailAct, trailOff unused: None) | trailOn True x trailAct {0.2, 0.5, 1,
            2, 4} % x trailOff {0.1, 0.3, 1, 3} %] x [slOn False (slDist unused: None) | slOn True x
            slDist {0.5, 1.5, 4} %] x maxOpen {1, 5, 20} ("Max open entries")
Everything else stays at the script's defaults (Trade direction Both, Opposite ENTER closes on,
Signal tick entries, pyramiding 100, 10 % of equity per entry, the filter's own inputs, the other
TDI / ladder inputs, signal rung = chart rung, rung agreement off).

SIGNALS (36) are the parameters of prepare() (the signal inputs + fgfOn), EXITS (1512) those of
simulate() (blkClose, inv, the exits); exits_for(signal) = the EXITS that go with a signal setting
(504 with the filter off, 1008 with it on). A dimension that cannot change the result is listed
once with the value None: blkClose with the filter off (nothing is ever blocked), trailAct /
trailOff with trailOn False, slDist with slOn False.

How one setting is computed (nothing here re-implements the strategy):
  signals     xpw.xpw_signals(pair, tf, window, signal_params) ONCE per signal input (18 per cell)
              -> the per-bar counts nLong / nShort and exitL / exitS (signal_arrays)
  filter      fgf.fgf_permissions(pair, tf, window, {}) once per cell (it does not read the labels)
  gate        gate(): the arrays engine._run needs (goLong / goShort / closeL / closeS ...), built
              expression for expression as engine.backtest_bars / sweep_core.prep do, but for any
              fgfBlkClose and maxOpen (sweep_core.prep fixes fgfBlkClose true and maxOpen 20).
              calib_tests_xpw.py proves trade by trade that the tv path on these arrays equals
              engine.backtest for every non-default value of the grid.
  orders      sweep_core.run_cfg(P, cfg, path, sub, inv): path 'tv' = engine._run itself, 'mag' =
              sweep_core._run_mag on the 1-minute sub-bars (sweep_core.sub_bars; on chart "1" each
              bar is its own sub-bar). check_mag_sync() / check_mag_equiv() run before any result.
  money       sweep_core.metrics_fast = run_tf.metrics: 10,000 initial capital, every entry 10 % of
              the closed equity at its entry, compounding; cost 'tv' = the script's Properties (no
              cost, mode tv0), 'ours' (mode cost: XAU $0.30 per ounce per round trip; BTC 0.02 % per
              side + $0.20 per coin), 'stress' (XAU $0.50 + 1 tick per side; BTC 0.035 % per side +
              $0.20 + 1 tick per side).

Every setting is scored with path 'mag' and cost 'ours'. Per cell the signals are prepared once per
signal input and reused for all its exit settings, the sub-bars are built once, the kernels are
compiled, and only then at most 3 workers are forked (copy-on-write); each simulates chunks of
exit settings of one prepared input. Rows are assembled in grid order, so the file does not depend
on the worker count.

Output columns: p_<name> for every dimension of DIMS, in DIMS order (unused: None for blkClose,
NaN for the distances), then the summary, COLS: the fields of sweep_core.metrics_fast for the
scored cost mode (sweep_core.METRIC_COLS: trades, net_pct, pf, win_pct, max_dd_pct, half1_pct,
half2_pct, avg_trade_ret_pct, max_concurrent, exit_trail, exit_sl, exit_close_all, exit_reverse,
exit_end, max_expo, avg_bars_held, h1r_pct, h2r_pct, h1_trades, h2_trades, h1r_pf, h2r_pf), then
long_trades, short_trades (the REAL sides), entries_skipped_room, entries_ignored_pyramiding,
close_all_bars, max_open (as out/inv_xpw_*.json), then raw_long, raw_short, blocked_long,
blocked_short (candles with a long / short entry signal and how many of them the filter blocked,
on the filter's side). Nothing else: no index, no pair / tf column (they are in the file name; the
parquet's key-value metadata "calib" holds strategy, pair, tf, path, cost, the number of settings,
the window and the sha256 of xpw.py, fgf.py, engine.py and sweep_core.py that produced the rows).
net_pct, pf, win_pct, max_dd_pct, the halves and h?r_pct / h?r_pf are rounded as run_tf.metrics
rounds them (2 decimals; win_pct 1; avg_trade_ret_pct 4). pf is NaN without a losing trade and
without trades; every ratio is NaN without trades, h?r_pct / h?r_pf are NaN for a half without
trades. --one prints the same fields (Python's json: NaN) plus "setting" = {strategy, pair, tf,
path, cost, p, trailUnit, in_grid}.
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
import sweep_core as sc   # noqa: E402  (imports xpw, fgf, engine, run_tf)
import xpw                # noqa: E402
import fgf                # noqa: E402
import engine             # noqa: E402
import run_tf             # noqa: E402

STRATEGY = 'xpw'
MAX_WORKERS = 3
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
PATH = 'mag'             # the sweep's scoring: 1-minute fills ...
COST = 'ours'            # ... with our costs
COST_MODE = {'tv': 'tv0', 'ours': 'cost', 'stress': 'stress'}     # this spec's cost -> sweep_core mode
CHUNK = 42               # exit settings per worker task
UNITS = ('percent', 'price', 'ticks')
TRAIL_UNIT = 'percent'   # the grid's unit of trailAct / trailOff / slDist

# ---------------------------------------------------------------------------------------------
# the grid
# ---------------------------------------------------------------------------------------------
RSI_LENS = (8, 13, 21)
LBL_READS = (True, False)
# labels -> the xpw_signals params that differ from the defaults (every act* defaults to "enter")
LABELS = {'all': {},
          'legs': {'actDL': 'off', 'actDS': 'off'},
          'div': {'actL1': 'off', 'actL2': 'off', 'actS1': 'off', 'actS2': 'off'}}
FILTERS = (False, True)
BLK_CLOSES = (True, False)
INVS = (False, True)
TRAIL_ACTS = (0.2, 0.5, 1.0, 2.0, 4.0)       # % of the entry price
TRAIL_OFFS = (0.1, 0.3, 1.0, 3.0)            # %
SL_DISTS = (0.5, 1.5, 4.0)                   # %
MAX_OPENS = (1, 5, 20)

DIMS = [
    {'name': 'rsiLen', 'values': list(RSI_LENS), 'kind': 'ordinal'},
    {'name': 'lblRead', 'values': list(LBL_READS), 'kind': 'categorical'},
    {'name': 'labels', 'values': list(LABELS), 'kind': 'categorical'},
    {'name': 'fgfOn', 'values': list(FILTERS), 'kind': 'categorical'},
    {'name': 'blkClose', 'values': list(BLK_CLOSES), 'kind': 'categorical'},        # None with fgfOn False
    {'name': 'inv', 'values': list(INVS), 'kind': 'categorical'},
    {'name': 'trailOn', 'values': [False, True], 'kind': 'categorical'},
    {'name': 'trailAct', 'values': list(TRAIL_ACTS), 'kind': 'ordinal'},            # None with trailOn False
    {'name': 'trailOff', 'values': list(TRAIL_OFFS), 'kind': 'ordinal'},            # None with trailOn False
    {'name': 'slOn', 'values': [False, True], 'kind': 'categorical'},
    {'name': 'slDist', 'values': list(SL_DISTS), 'kind': 'ordinal'},                # None with slOn False
    {'name': 'maxOpen', 'values': list(MAX_OPENS), 'kind': 'ordinal'},
]
DIM_NAMES = [d['name'] for d in DIMS]
SIGNAL_DIMS = ('rsiLen', 'lblRead', 'labels', 'fgfOn')
EXIT_DIMS = ('blkClose', 'inv', 'trailOn', 'trailAct', 'trailOff', 'slOn', 'slDist', 'maxOpen')
# a dimension is unused (None) when another one has this value
UNUSED_WHEN = {'blkClose': ('fgfOn', False), 'trailAct': ('trailOn', False), 'trailOff': ('trailOn', False),
               'slDist': ('slOn', False)}
DIM_DOC = {
    'rsiLen': 'RSI length (TDI core)',
    'lblRead': 'Also trade / label the READ HERE rung (<<)',
    'labels': 'labels that trade (act* inputs): all / legs = divergence labels off / div = leg labels off',
    'fgfOn': 'direction filter: Enable filter',
    'blkClose': 'Blocked entry still closes the other side (None: filter off)',
    'inv': 'Inverted direction: opposite side at the same entries (Update 1)',
    'trailOn': 'Use trailing take profit',
    'trailAct': 'Trail activation, % of the entry price (None: trailing off)',
    'trailOff': 'Trail offset, % of the entry price (None: trailing off)',
    'slOn': 'Use stop loss',
    'slDist': 'Stop loss distance, % of the entry price (None: stop loss off)',
    'maxOpen': 'Max open entries',
}
_DIM_TYPE = {'rsiLen': int, 'lblRead': bool, 'labels': str, 'fgfOn': bool, 'blkClose': bool, 'inv': bool,
             'trailOn': bool, 'trailAct': float, 'trailOff': float, 'slOn': bool, 'slDist': float, 'maxOpen': int}

# The script's own default inputs. Its exits (trail 2.0 / 1.0 in PRICE units, no stop, 20 entries)
# are not on this grid (the grid is in percent): there is no default row, hence DEFAULT_P None
# (calib_analyze.py then reports no default). `--one --off-grid` with SCRIPT_DEFAULT reproduces
# out/inv_xpw_<PAIR>_<TF>.json (calib_tests_xpw.py, test 2).
DEFAULT_P = None
SCRIPT_DEFAULT = {'rsiLen': 13, 'lblRead': True, 'labels': 'all', 'fgfOn': True, 'blkClose': True, 'inv': False,
                  'trailOn': True, 'trailAct': 2.0, 'trailOff': 1.0, 'slOn': False, 'slDist': None, 'maxOpen': 20,
                  'trailUnit': 'price'}

# SIGNAL settings: the parameters of prepare(). fgfOn is the innermost loop: the two filter states
# of one signal input share its xpw_signals arrays.
SIGNALS = [{'rsiLen': r, 'lblRead': lr, 'labels': lb, 'fgfOn': f}
           for r in RSI_LENS for lr in LBL_READS for lb in LABELS for f in FILTERS]
# EXIT settings: the parameters of simulate(). blkClose None = the 504 of a filter-off signal
# setting; blkClose True / False = the 1008 of a filter-on one.
_TRAILS = [(False, None, None)] + [(True, a, o) for a in TRAIL_ACTS for o in TRAIL_OFFS]
_STOPS = [(False, None)] + [(True, s) for s in SL_DISTS]
EXITS = [{'blkClose': b, 'inv': i, 'trailOn': ton, 'trailAct': ta, 'trailOff': to, 'slOn': son, 'slDist': sd,
          'maxOpen': mo}
         for b in (None,) + BLK_CLOSES for i in INVS for (ton, ta, to) in _TRAILS for (son, sd) in _STOPS
         for mo in MAX_OPENS]


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
    """A SIGNAL setting as xpw.xpw_signals params (everything else at xpw.DEFAULTS). fgfOn is not
    an xpw input: the filter's permissions are joined in prepare()."""
    p = {'rsiLen': int(sig['rsiLen']), 'lblRead': bool(sig['lblRead'])}
    p.update(LABELS[sig['labels']])
    return p


def exit_cfg(x, unit=TRAIL_UNIT):
    """An EXIT setting as the cfg of sweep_core.run_cfg (= engine params trailOn, trailUnit,
    trailAct, trailOff, slOn, slDist). Unused distances are NaN: sweep_core.cfg_params then passes
    the engine defaults, which the kernel ignores (trailOn / slOn false)."""
    nan = float('nan')
    return {'trailOn': bool(x['trailOn']), 'trailUnit': unit,
            'trailAct': float(x['trailAct']) if x['trailOn'] else nan,
            'trailOff': float(x['trailOff']) if x['trailOn'] else nan,
            'slOn': bool(x['slOn']), 'slDist': float(x['slDist']) if x['slOn'] else nan}


def engine_params(p, unit=TRAIL_UNIT):
    """A whole setting as engine.backtest params (the slow path; used by the tests and the docs:
    engine.backtest(pair, tf, xpw_signals(.., signal_params(p)), perm if p['fgfOn'] else None,
    engine_params(p)) is the same backtest on the tv path)."""
    q = {'fgfOn': bool(p['fgfOn']), 'xpwInv': bool(p['inv']), 'maxOpen': int(p['maxOpen']),
         'trailOn': bool(p['trailOn']), 'trailUnit': unit, 'slOn': bool(p['slOn'])}
    if p['fgfOn']:
        q['fgfBlkClose'] = bool(p['blkClose'])
    if p['trailOn']:
        q['trailAct'] = float(p['trailAct'])
        q['trailOff'] = float(p['trailOff'])
    if p['slOn']:
        q['slDist'] = float(p['slDist'])
    return q


def _num(v):
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, (bool, np.bool_))


def normalize(raw, off_grid=False):
    """A setting given as a mapping of p_ values (keys with or without 'p_'; None / NaN / missing =
    unused) -> (the canonical dict over DIM_NAMES, trailUnit). Unused dimensions are set to None
    whatever was given. Raises ValueError for an unknown key, a missing used dimension, a value of
    the wrong type, or (unless off_grid) a value that is not in the grid / a trailUnit."""
    if not isinstance(raw, dict):
        raise ValueError('the p_ values must be a JSON object')
    vals = {}
    unit = TRAIL_UNIT
    for k, v in raw.items():
        k = k[2:] if k.startswith('p_') else k
        if isinstance(v, float) and math.isnan(v):
            v = None
        if k == 'trailUnit':
            if v is None:
                continue
            if not off_grid and v != TRAIL_UNIT:
                raise ValueError('trailUnit: %r is not in the grid (always %r); use --off-grid' % (v, TRAIL_UNIT))
            if v not in UNITS:
                raise ValueError('trailUnit: %r is not one of %r' % (v, UNITS))
            unit = v
            continue
        if k not in DIM_NAMES:
            raise ValueError('unknown dimension %r (one of %s)' % (k, ', '.join(DIM_NAMES)))
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
            if not off_grid:
                raise ValueError('%s: %r is not in the grid %r' % (name, v, d['values']))
            if name == 'labels':
                raise ValueError('labels: %r is not one of %r' % (v, d['values']))
            if name == 'rsiLen' and v < 1:
                raise ValueError('rsiLen: %r is below 1' % v)
            if name == 'maxOpen' and not 1 <= v <= 100:
                raise ValueError('maxOpen: %r is outside 1..100 (the script\'s input range)' % v)
            if ty is float and v < 0:
                raise ValueError('%s: %r is negative' % (name, v))
        out[name] = v
    return out, unit


_KEYS = None


def in_grid(p, unit=TRAIL_UNIT):
    global _KEYS
    if _KEYS is None:
        _KEYS = set(key(q) for q in grid())
    return unit == TRAIL_UNIT and key(p) in _KEYS


# ---------------------------------------------------------------------------------------------
# prepare: signals + filter permissions -> the arrays of the order kernels
# ---------------------------------------------------------------------------------------------
def signal_arrays(pair, tf, sig):
    """xpw.xpw_signals on the pair's window for one signal input (rsiLen, lblRead, labels), reduced
    to what the orders read, exactly as engine.backtest_bars / sweep_core.prep reduce the frame:
    nL / nS = the number of long / short entry labels of each bar after "long and short labels on
    the same bar cancel out", exitL / exitS. The frame itself (52 display columns) is dropped."""
    start, end = run_tf.WINDOWS[pair]
    df = xpw.xpw_signals(pair, str(tf), start, end, signal_params(sig))
    rows = np.asarray(df.index, dtype=np.int64)
    n = len(rows)
    longSrc = engine._src_lists(df, 'longSrc')
    shortSrc = engine._src_lists(df, 'shortSrc')
    nLraw = np.fromiter((len(v) for v in longSrc), np.int64, n)
    nSraw = np.fromiter((len(v) for v in shortSrc), np.int64, n)
    both = (nLraw > 0) & (nSraw > 0)
    nL = np.where(both, 0, nLraw).astype(np.int64)
    nS = np.where(both, 0, nSraw).astype(np.int64)
    if not (np.array_equal(df['nLong'].to_numpy(np.int64), nL) and np.array_equal(df['nShort'].to_numpy(np.int64), nS)):
        raise ValueError('sig nLong / nShort disagree with the longSrc / shortSrc lists')
    return dict(pair=pair, tf=str(tf), rows=rows, t_close=np.array(df['t_close'].to_numpy(np.int64), copy=True),
                nL=nL, nS=nS, exitL=np.array(df['exitL'].to_numpy(bool), copy=True),
                exitS=np.array(df['exitS'].to_numpy(bool), copy=True),
                maxn=int(max(nL.max(initial=0), nS.max(initial=0))),
                sig_bars_long=int((nLraw > 0).sum()), sig_bars_short=int((nSraw > 0).sum()),
                sig_bars_cancelled=int(both.sum()))


def load_bars(pair, tf, rows, t_close=None):
    """The chart bars of the window as own writable arrays (as sweep_core.prep: numba compiles a
    separate kernel for read-only arrays)."""
    allb = engine.load_bars(pair, str(tf))
    rows = np.asarray(rows, dtype=np.int64)
    if len(rows) and (rows.min() < 0 or rows.max() >= len(allb)):
        raise ValueError('sig index outside data/%s_%s.parquet' % (pair, tf))
    bars = allb.iloc[rows]
    B = {k: np.array(bars[k].to_numpy(np.float64), copy=True) for k in ('open', 'high', 'low', 'close')}
    out = dict(rows=rows, o=B['open'], h=B['high'], l=B['low'], c=B['close'],
               t_open=np.array(bars['t_open'].to_numpy(np.int64), copy=True),
               t_close=np.array(bars['t_close'].to_numpy(np.int64), copy=True))
    if t_close is not None and not np.array_equal(out['t_close'], t_close):
        raise ValueError('sig t_close does not match the data file rows')
    if len(rows) > 1 and not (np.diff(out['t_close']) > 0).all():
        raise ValueError('t_close not strictly increasing')
    return out


def load_perm(pair, tf, rows):
    """The filter's permissions on the window (the filter's own inputs at their defaults), as
    sweep.py / run_tf.py / run_inv_xpw.py obtain them: (buyOk, sellOk) per chart bar."""
    start, end = run_tf.WINDOWS[pair]
    perm = fgf.fgf_permissions(pair, str(tf), start, end, {})
    if not np.array_equal(np.asarray(perm.index, dtype=np.int64), np.asarray(rows, dtype=np.int64)):
        raise ValueError('xpw / fgf rows differ for %s %s' % (pair, tf))
    return (np.array(perm['buyOk'].to_numpy(bool), copy=True), np.array(perm['sellOk'].to_numpy(bool), copy=True))


def gate(S, perm, fgfOn, blkClose):
    """The signal arrays engine._run reads, as engine.backtest_bars computes them (same expressions,
    same order) for fgfOn / fgfBlkClose given and every other input at the engine's default (Trade
    direction Both, Opposite ENTER closes on, Signal tick). Everything is in the normal (decision)
    frame: with Trade direction Both the arrays do not depend on "Inverted direction", which is a
    flag of the kernel. perm = (buyOk, sellOk) or None."""
    p = engine._params({'fgfOn': bool(fgfOn), 'fgfBlkClose': True if blkClose is None else bool(blkClose)})
    if p['tradeDir'] != 'Both' or p['entryFill'] != 'Signal tick':
        raise ValueError('engine defaults changed: gate() serves Trade direction Both, Signal tick only')
    nL, nS, exitL, exitS = S['nL'], S['nS'], S['exitL'], S['exitS']
    n = len(nL)
    filt = bool(p['fgfOn']) and perm is not None
    if bool(p['fgfOn']) and perm is None:
        raise ValueError('filter on without permissions')
    if filt:
        buyOk, sellOk = perm
        if len(buyOk) != n or len(sellOk) != n:
            raise ValueError('perm does not cover every sig row')
    else:
        buyOk = np.ones(n, bool)
        sellOk = np.ones(n, bool)
    allowLong = p['tradeDir'] != 'Short only (sell only)'
    allowShort = p['tradeDir'] != 'Long only (buy only)'
    sigLong = (nL > 0) & allowLong
    sigShort = (nS > 0) & allowShort
    blkL = sigLong & ~buyOk
    blkS = sigShort & ~sellOk
    goLong = sigLong & ~blkL
    goShort = sigShort & ~blkS
    oc = bool(p['oppCloses'])
    bc = bool(p['fgfBlkClose'])
    oppL = (nS > 0) & ((oc and not allowShort) | (bc & blkS))
    oppS = (nL > 0) & ((oc and not allowLong) | (bc & blkL))
    cL = ~goLong & ~goShort & (exitL | oppL)
    cS = ~goShort & ~goLong & (exitS | oppS)
    cap = int((nL * goLong).sum() + (nS * goShort).sum()) + 1
    mt = float(p['mintick'])
    return dict(filter_on=filt, goL=goLong, goS=goShort, cL=cL, cS=cS, cap=cap, pyr=int(p['pyramiding']),
                mt=mt, tol=mt * 1e-6, raw_long=int(sigLong.sum()), raw_short=int(sigShort.sum()),
                blocked_long=int(blkL.sum()), blocked_short=int(blkS.sum()))


def _view(P, blkClose, maxOpen):
    """The dict sweep_core.run_cfg reads, for one (blkClose, maxOpen) of a prepared input: shared
    arrays, the gate of that blkClose, maxOpen and the engine's open-list size for it."""
    blk = None if not P['fgfOn'] else bool(blkClose)
    k = (blk, int(maxOpen))
    v = P['views'].get(k)
    if v is None:
        if blk not in P['gates']:
            P['gates'][blk] = gate(P['S'], P['perm'], P['fgfOn'], blk)
        g = P['gates'][blk]
        B, S = P['B'], P['S']
        mo = int(engine._params({'maxOpen': maxOpen})['maxOpen'])
        v = dict(pair=P['pair'], tf=P['tf'], filter_on=g['filter_on'], rows=B['rows'], t_open=B['t_open'],
                 t_close=B['t_close'], o=B['o'], h=B['h'], l=B['l'], c=B['c'], goL=g['goL'], goS=g['goS'],
                 nL=S['nL'], nS=S['nS'], cL=g['cL'], cS=g['cS'], maxOpen=mo, pyr=g['pyr'], mt=g['mt'],
                 tol=g['tol'], cap=g['cap'], ocap=int(max(mo, S['maxn'])) + 2, blkL=g['blocked_long'],
                 blkS=g['blocked_short'], inv=False)
        P['views'][k] = v
    return v


def prepare(pair, tf, sig, S=None, B=None, perm=None, sub=None):
    """The prepared input of one SIGNAL setting (rsiLen, lblRead, labels, fgfOn), reusable for every
    exit setting: the signal arrays (S, computed here unless given: one xpw_signals call serves
    both filter states), the chart bars (B), the filter's permissions when fgfOn (perm), and the
    gates of every blkClose / the kernel views of every maxOpen of the grid. sub: the 1-minute
    sub-bars (path 'mag'); built on first use when not given."""
    tf = str(tf)
    if S is None:
        S = signal_arrays(pair, tf, sig)
    if B is None:
        B = load_bars(pair, tf, S['rows'], S['t_close'])
    elif not (np.array_equal(B['rows'], S['rows']) and np.array_equal(B['t_close'], S['t_close'])):
        raise ValueError('%s %s: chart rows differ between signal settings' % (pair, tf))
    fgfOn = bool(sig['fgfOn'])
    if fgfOn and perm is None:
        perm = load_perm(pair, tf, S['rows'])
    start, end = run_tf.WINDOWS[pair]
    P = dict(pair=pair, tf=tf, sig=dict(sig), fgfOn=fgfOn, S=S, B=B, perm=perm if fgfOn else None, sub=sub,
             start=int(start), end=int(end), n=len(S['rows']), t_close=B['t_close'], gates={}, views={})
    for blk in (BLK_CLOSES if fgfOn else (None,)):
        for mo in MAX_OPENS:
            _view(P, blk, mo)
    return P


def get_sub(P):
    """The 1-minute sub-bars of the prepared input's chart rows (sweep_core.sub_bars, checked
    against the chart bars), built once."""
    if P['sub'] is None:
        P['sub'] = sc.sub_bars(P['pair'], P['tf'], P['B']['rows'])
    return P['sub']


def simulate(P, x, path=PATH, unit=TRAIL_UNIT):
    """One backtest of a prepared input with one EXIT setting: sweep_core.run_cfg on the view of
    the setting's (blkClose, maxOpen), with inv as the kernel's "Inverted direction" flag.
    path 'tv' = engine._run on the chart bars; 'mag' = sweep_core._run_mag on the sub-bars."""
    v = _view(P, x['blkClose'], x['maxOpen'])
    if path == 'mag':
        return sc.run_cfg(v, exit_cfg(x, unit), 'mag', sub=get_sub(P), inv=bool(x['inv']))
    if path != 'tv':
        raise ValueError('path %r' % (path,))
    return sc.run_cfg(v, exit_cfg(x, unit), 'tv', inv=bool(x['inv']))


RUN_COLS = ('entries_skipped_room', 'entries_ignored_pyramiding', 'close_all_bars', 'max_open')
GATE_COLS = ('raw_long', 'raw_short', 'blocked_long', 'blocked_short')
COLS = tuple(sc.METRIC_COLS) + ('long_trades', 'short_trades') + RUN_COLS + GATE_COLS
INT_COLS = tuple(sc.INT_COLS) + ('long_trades', 'short_trades') + RUN_COLS + GATE_COLS


def summary(P, R, x, cost=COST):
    """The row of one run: sweep_core.metrics_fast for the cost mode, plus the real sides, the
    engine's run counts and the gate's counts (see the module docstring), in COLS order."""
    m = sc.metrics_fast(P['pair'], R, P['t_close'], P['start'], P['end'])[COST_MODE[cost]]
    d = {k: m[k] for k in sc.METRIC_COLS}
    nl = int((R['dir'] > 0).sum())
    d['long_trades'] = nl
    d['short_trades'] = int(R['n']) - nl
    for k in RUN_COLS:
        d[k] = int(R[k])
    g = P['gates'][None if not P['fgfOn'] else bool(x['blkClose'])]
    for k in GATE_COLS:
        d[k] = g[k]
    return d


def guard(P, x=None):
    """Before any 'mag' result: sweep_core._run_mag still is engine._run outside the exit walk
    (source comparison), and with one sub-bar per chart bar it equals engine._run on this input
    (the view of exit setting x; default: the last view = the largest maxOpen)."""
    sc.check_mag_sync()
    v = list(P['views'].values())[-1] if x is None else _view(P, x['blkClose'], x['maxOpen'])
    sc.check_mag_equiv(v)


# ---------------------------------------------------------------------------------------------
# one setting
# ---------------------------------------------------------------------------------------------
def one(pair, tf, p, path=PATH, cost=COST, off_grid=False):
    """The full summary of one setting, computed alone: its own xpw_signals, permissions, gate and
    one run. p: a mapping of p_ values (see normalize)."""
    p, unit = normalize(p, off_grid)
    P = prepare(pair, str(tf), {k: p[k] for k in SIGNAL_DIMS})
    x = {k: p[k] for k in EXIT_DIMS}
    if path == 'mag':
        guard(P, x)
    out = dict(summary(P, simulate(P, x, path, unit), x, cost))
    out['setting'] = {'strategy': STRATEGY, 'pair': pair, 'tf': str(tf), 'path': path, 'cost': cost, 'p': p,
                      'trailUnit': unit, 'in_grid': in_grid(p, unit)}
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
    """Everything the exit settings reuse, built once: xpw_signals once per signal input (18, or
    those of sig_idx), the permissions once, every gate and view, the 1-minute sub-bars once, the
    kernels compiled and guarded. Returns the cell: P {signal index: prepared input} and timings."""
    tf = str(tf)
    idx = list(range(len(SIGNALS))) if sig_idx is None else [int(i) for i in sig_idx]
    t0 = time.time()
    c0 = time.process_time()
    S_by, P = {}, {}
    B = perm = None
    for si in idx:
        sig = SIGNALS[si]
        ki = _sig_inputs(sig)
        if ki not in S_by:
            S_by[ki] = signal_arrays(pair, tf, sig)
            gc.collect()
        S = S_by[ki]
        if B is None:
            B = load_bars(pair, tf, S['rows'], S['t_close'])
        if sig['fgfOn'] and perm is None:
            perm = load_perm(pair, tf, S['rows'])
        P[si] = prepare(pair, tf, sig, S=S, B=B, perm=perm)
    xpw.clear_cache()            # the rung states of every timeframe: not needed any more
    gc.collect()
    t_sig = time.time() - t0
    t1 = time.time()
    sub = None
    n_sub = 0
    if PATH == 'mag':
        sub = sc.sub_bars(pair, tf, B['rows'])
        n_sub = len(sub[1])
        for Pk in P.values():
            Pk['sub'] = sub
    t_sub = time.time() - t1
    t2 = time.time()
    sc.warmup()                  # compile before forking
    p0 = P[idx[0]]
    if PATH == 'mag':
        guard(p0)
    x0 = exits_for(SIGNALS[idx[0]])[4]
    summary(p0, simulate(p0, x0), x0)
    t_jit = time.time() - t2
    cell = dict(pair=pair, tf=tf, idx=idx, P=P, bars=int(len(B['rows'])), n_sub=n_sub, n_signal_inputs=len(S_by),
                t_sig=t_sig, t_sub=t_sub, t_jit=t_jit, t_prep=time.time() - t0, c_prep=time.process_time() - c0)
    if verbose:
        nb = [int(S['sig_bars_long'] + S['sig_bars_short'] - 2 * S['sig_bars_cancelled']) for S in S_by.values()]
        print('  %s %s: %d chart bars, %d 1-minute bars; %d signal inputs (xpw_signals once each, %d .. %d bars with '
              'an entry signal) -> %d prepared inputs in %.1fs, sub-bars %.1fs, kernels + guard %.1fs (preparation: '
              '%.1fs CPU)' % (pair, tf, cell['bars'], n_sub, len(S_by), min(nb), max(nb), len(idx), t_sig, t_sub, t_jit,
                              cell['c_prep']), flush=True)
    return cell


def _work(task):
    si, i0, i1 = task
    t0 = time.time()
    c0 = time.process_time()
    Pp = _G['P'][si]
    X = _G['X'][si]
    out = []
    for i in range(i0, i1):
        s = summary(Pp, simulate(Pp, X[i]), X[i])
        out.append(tuple(s[k] for k in COLS))
    return si, i0, out, time.time() - t0, time.process_time() - c0


def run_prepared(cell, workers=MAX_WORKERS, sig_idx=None, chunk=CHUNK, verbose=False):
    """Simulate every exit setting of the prepared signal settings (all of the cell, or sig_idx).
    Returns (res {signal index: [summary tuple per exit setting]}, info)."""
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    X = {si: exits_for(SIGNALS[si]) for si in idx}
    _G.clear()
    _G.update(P=cell['P'], X=X)
    tasks = [(si, i0, min(i0 + chunk, len(X[si]))) for si in idx for i0 in range(0, len(X[si]), chunk)]
    total = sum(t[2] - t[1] for t in tasks)
    res = {si: [None] * len(X[si]) for si in idx}
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


def frame(cell, res, sig_idx=None):
    """The rows in grid order: p_<name> per dimension, then every summary field (COLS)."""
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    G = grid(idx)
    vals = [r for si in idx for r in res[si]]
    if len(G) != len(vals):
        raise RuntimeError('grid and results differ in length')
    data = {}
    for name in DIM_NAMES:
        col = [p[name] for p in G]
        ty = _DIM_TYPE[name]
        if ty is float:                                   # unused -> NaN
            data['p_' + name] = pd.Series([float('nan') if v is None else v for v in col], dtype=np.float64)
        elif name in UNUSED_WHEN or ty is str:            # unused -> None
            data['p_' + name] = pd.Series(col, dtype=object)
        else:
            data['p_' + name] = pd.Series(col, dtype={bool: bool, int: np.int64}[ty])
    for j, k in enumerate(COLS):
        data[k] = pd.Series([v[j] for v in vals], dtype=np.int64 if k in INT_COLS else np.float64)
    return pd.DataFrame(data)


def _write_atomic(path, writer):
    tmp = path + '.tmp%d' % os.getpid()
    writer(tmp)
    os.replace(tmp, path)


def _sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


SRC_FILES = ('xpw.py', 'fgf.py', 'engine.py', 'sweep_core.py')


def file_meta(pair, tf, n):
    """What produced a cell's file (stored in the parquet's key-value metadata, key "calib")."""
    m = {'strategy': STRATEGY, 'pair': pair, 'tf': str(tf), 'path': PATH, 'cost': COST, 'settings': int(n),
         'window': [int(v) for v in run_tf.WINDOWS[pair]], 'trailUnit': TRAIL_UNIT}
    for f in SRC_FILES:
        m[f[:-3] + '_sha256'] = _sha256(os.path.join(W, f))
    return m


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
                c_prep=cell['c_prep'], t_sig=cell['t_sig'], t_sub=cell['t_sub'], t_jit=cell['t_jit'], file=None)
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
        print('  %s %s done: %d rows%s | prep %.1fs, runs %.1fs with %d workers (%.2f worker-s busy, %.2f s CPU = '
              '%.5fs CPU per setting; workers busy %.0f%% of the run), total %.1fs'
              % (pair, tf, len(df), (' -> ' + info['file']) if info['file'] else ' (not written)', info['t_prep'],
                 info['t_run'], w, info['busy'], info['cpu'], info['cpu'] / max(info['settings'], 1),
                 100.0 * info['busy'] / max(info['t_run'] * w, 1e-9), info['t_total']), flush=True)
    _G.clear()
    return df, info


def estimate_cell(pair, tf, workers=MAX_WORKERS, per_signal=6, seed=20261124, verbose=True):
    """Estimated time of the full cell from ONE process: the real preparation, then per_signal random
    exit settings of every signal setting timed one by one, in CPU seconds (so that other jobs on the
    machine do not count); run time = sum over the signal settings of (mean sampled time x its number
    of exit settings) / workers = the wall time when every worker has a CPU to itself. Writes nothing."""
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
        for i in rng.choice(len(X), size=min(per_signal, len(X)), replace=False):
            t = time.process_time()
            summary(Pp, simulate(Pp, X[int(i)]), X[int(i)])
            tt.append(time.process_time() - t)
        t_single += float(np.mean(tt)) * len(X)
        worst = max(worst, max(tt))
        n_s += len(tt)
    n_all = len(grid())
    est = dict(pair=pair, tf=tf, bars=cell['bars'], n_sub=cell['n_sub'], settings=n_all, sampled=n_s,
               t_prep=cell['t_prep'], c_prep=cell['c_prep'], per_setting=t_single / n_all, slowest=worst,
               single_process_run=t_single, workers=workers, est_run=t_single / max(workers, 1),
               est_total=cell['c_prep'] + t_single / max(workers, 1), t_sample=time.time() - t0, load1=os.getloadavg()[0])
    if verbose:
        print('  %s %s estimate: prep %.1fs CPU (%.1fs wall now) + %d settings x %.5fs CPU (slowest sampled %.4fs; %d '
              'sampled) = %.1fs CPU / %d workers = %.1fs runs -> %.1fs total (%.2f min) with a free CPU per worker; '
              'load average now %.2f'
              % (pair, tf, est['c_prep'], est['t_prep'], n_all, est['per_setting'], worst, n_s, t_single, workers,
                 est['est_run'], est['est_total'], est['est_total'] / 60.0, est['load1']), flush=True)
    return est


def free():
    """Drop every cache of the replica modules (between cells)."""
    _G.clear()
    xpw.clear_cache()
    engine._BARS_CACHE.clear()
    sc._M1_CACHE.clear()
    for nm in ('_BARS', '_DIR', '_FILTER'):
        c = getattr(fgf, nm, None)
        if isinstance(c, dict):
            c.clear()
    gc.collect()


# ---------------------------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------------------------
def _main_one(argv):
    ap = argparse.ArgumentParser(prog='calib_xpw.py --one', description='the full summary of one setting, as JSON')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tf', choices=TFS)
    ap.add_argument('p', help='JSON object of the p_ values of the setting')
    ap.add_argument('--path', choices=('tv', 'mag'), default=PATH)
    ap.add_argument('--cost', choices=tuple(COST_MODE), default=COST)
    ap.add_argument('--off-grid', action='store_true', help='accept values that are not in the grid, and trailUnit')
    a = ap.parse_args(argv)
    try:
        raw = json.loads(a.p)
        out = one(a.pair, a.tf, raw, a.path, a.cost, a.off_grid)
    except ValueError as e:
        print('calib_xpw.py --one: %s' % e, file=sys.stderr)
        return 2
    print(json.dumps(out, default=_json_default))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--one' in argv:
        argv.remove('--one')
        return _main_one(argv)
    ap = argparse.ArgumentParser(description='XPW v2.8 trailing-TP + FGF calibration grid (CALIB_SPEC.md)')
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
        free()
    print('all done in %.1fs' % (time.time() - t0), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
