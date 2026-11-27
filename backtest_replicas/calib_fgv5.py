"""calib_fgv5.py: calibration grid of FlashGold v5 Strategy (BTCUSD) + FGF [Update 1] (key fgv5) per pair and
timeframe, with the direction (Normal / Inverted, Update 1 "Inverted direction" = fgvInv) as a calibrated input
(CALIB_SPEC.md, strategy "fgv5"; the grid is section 14 of SPEC_fgv5.md), on the canonical replica fgv5.py
(prepare / simulate / summary; the direction filter is fgf.fgf_permissions, called by fgv5.prepare).

Usage (python3 -I)
  calib_fgv5.py PAIR TF [TF ...] [--workers 3] [--out-dir DIR]
      runs the full grid of every (PAIR, TF) cell and writes out/calib_fgv5_<PAIR>_<TF>.parquet (one row per
      setting) and out/calib_fgv5_dims.json (DIMS). PAIR in BTC, XAU; TF in 1, 5, 15, 30, 60, 120, 240. Safe to
      re-run: the files are overwritten (written to a temporary name first). Prints the timing of every cell.
  calib_fgv5.py --one PAIR TF '<json of p_ values>' [--path tv|mag] [--cost tv|ours|stress]
                [--risk-sizing | --script-sizing] [--off-grid]
      prints the full summary of ONE setting as one JSON document on stdout (default path mag, cost ours = the
      sweep's scoring), with the same columns as a row of the file (R-based net_pct / h1r_pct / h2r_pct, see
      SCORING) plus "setting". The JSON of p_ values is a row's p_ columns: keys with or without the "p_" prefix,
      null (or NaN) for an unused dimension. Sizing (not a grid dimension):
        (default) / --script-sizing  the file's own sizing, the grid's: QtyMode "Fixed", fixedQty 10, maxQty 50,
                                     qtyStep 1 (--script-sizing is accepted for symmetry with the other runners:
                                     it changes nothing here, the grid already runs the file's sizing)
        --risk-sizing                the scale-free "Risk %" branch that SPEC_fgv5.md section 14 proposed for the
                                     grid: QtyMode "Risk %", riskPct 1.0, maxQty 1e9, qtyStep 0.000001
      --off-grid also accepts numbers that are not in the grid (burstAtrMult, minAlignedZones, entryDistAtrMult,
      slAtrMult, tpR, maxBarsHeld).
  calib_fgv5.py --estimate PAIR TF [TF ...] [--workers 3] [--per-signal 8]
      times the cell's preparation and a random sample of settings in ONE process and prints the estimated
      time of the full cell; writes nothing.

The grid (SPEC_fgv5.md section 14): 15,984 settings per cell, the same in every cell = 18 signal settings
(prepare) x 888 exit settings (simulate).
  signals    burstAtrMult {0.3, 0.5, 1.0} x minAlignedZones {1, 2, 3} x fgfOn {False, True} (the filter; the
             script has no blocked-signal close, so the filter is off / on only)
  exits      inv {False, True} (= fgvInv, Update 1) x entryDistAtrMult {0.0, 0.25, 0.5} x allowReverse {True,
             False} x [exitStyle 'pips_default' (slAtrMult, tpR None) | exitStyle in {'fixed', 'part30', 'run'} x
             slAtrMult {0.25, 0.5, 1.0, 2.0} x tpR {1.5, 3.0, 5.0}] x maxBarsHeld {0, 12} = 2 x 3 x 2 x 37 x 2
  exitStyle  a derived dimension: each value is a whole exit rule whose Pine inputs are written to columns
             that do not start with p_ (null where the style does not set the input):
               'pips_default'  ExitMode "Pips", pipSize 1, slPips 30, tpRPips 5, TpStyle "Partial + runner",
                               partPct 30, runBE on, runTrailPips 600 (the script's default exit)
               'fixed'         ExitMode "ATR", TpStyle "Fixed", useTrail off: stop slAtrMult x ATR(14), target
                               tpR R
               'part30'        ExitMode "ATR", TpStyle "Partial + runner", partPct 30, runBE on, runTrailAtr r1
               'run'           ExitMode "ATR", TpStyle "Partial + runner", partPct 0 (all runner: breakeven and
                               trail from the tpR level), runBE on, runTrailAtr r2
  runner trail (r1, r2) per cell, the table of section 14: the ladder 1.5, 2.5, 3.5, 5, 6.5, 8.5; r1 = the
             smallest ladder value >= max(1.5, floor / p10), r2 = the next one, p10 = the 10th percentile over the
             window of ATR(14) / close (%), floor = the 1-minute noise floor (BTC 0.1 %, XAU 0.05 %):
                 BTC 1 (6.5, 8.5) | BTC 5 (2.5, 3.5) | BTC 15 .. 240 (1.5, 2.5)
                 XAU 1 (5, 6.5)   | XAU 5 (2.5, 3.5) | XAU 15 .. 240 (1.5, 2.5)
             The pair is not a dimension (one value per cell); it is in the file metadata ("floor", measured
             again on the data at every run, with the ladder choice recomputed) and in the "setting" of --one.
  floor_ok   per row, measured on the data of the cell: 'part30' r1 x p10 >= floor, 'run' r2 x p10 >= floor,
             'pips_default' the $600 runner as % of the highest close of the window >= floor, 'fixed' True (no
             trailing). Section 14 says True on every row; the run prints the count.
A combination that cannot differ is listed once: 'pips_default' with slAtrMult / tpR None (Pips mode reads
neither), 'fixed' carries no runner (partPct / runBE / runTrailAtr not set: the Fixed style reads none of them).
DIMS = the 10 dimensions (name, values, kind 'ordinal' / 'categorical'; extra keys: side 'signal' (a parameter of
fgv5.prepare) / 'exit' (of fgv5.simulate), default = the script's default, unused_when); row i of a file is
grid(pair, tf)[i]. The direction dimension is named inv. DEFAULT_P (= DEFAULT) is the script default, one row of
every cell: 0.5, 2, filter on, normal, 0.25, reverse on, 'pips_default', None, None, 0.
Everything else at the script defaults (autoTf on: parent / zones = chart / 2x / 4x, zones 1-3, DistUnit "ATR",
entryValidBars 3, exitOnOpposite off, Direction "Both", atrLen 14, the filter's own inputs, spreadPoints 25).

SCORING (the orchestrator's decision for this runner). The grid runs the file's own sizing: a fixed 10 units on
100,000, no margin (v5): on BTC equity goes below zero and fgv5.summary's money halves h1r_pct / h2r_pct are NaN
there (a half holding an entry with eq_before <= 0). The rule (calib_analyze.py) reads h1r_pct / h2r_pct, so in
THIS runner's rows (and in --one):
      h1r_pct := h1_r    h2r_pct := h2_r    net_pct := net_r
the sums of R multiples of the trades entered in the first half / the second half / the whole window (R = the
trade's stop distance x quantity; r_mult = pnl / (sl_dist x qty), NaN skipped, 0 without trades; the halves split
by entry time <= / > the window's middle, as h1_trades / h2_trades), and fgv5.summary's money figures are kept
under other names:
      net_pct_money (= fgv5 net_pct)    h1r_pct_money (= fgv5 h1r_pct)    h2r_pct_money (= fgv5 h2r_pct)
Every other scalar field of fgv5.summary is stored under its own name. The same statement is in the parquet
metadata ("calib" -> "scoring"). So every row has finite h1r_pct / h2r_pct / net_pct, in R, not in %.
(SPEC_fgv5.md section 14 proposed the "Risk %" sizing for the grid instead; it is --one --risk-sizing.)

Every setting is scored with path 'mag' (pending entries and the exit orders walk the 1-minute sub-bars; on chart
"1" each bar is its own sub-bar) and cost 'ours'. Per cell: fgv5.prepare runs ONCE per signal setting (18 times;
the TDI series, the 9 signal computations and the filter permissions are computed once by the module's caches),
the prepared inputs are slimmed (the window arrays are copied out of the module's bar caches and equal arrays are
kept once), the 1-minute sub-bars are built once, the module caches are dropped, the kernel is compiled, and
only then at most 3 workers are forked (copy-on-write); each simulates chunks of exit settings of one prepared
input (fgv5.simulate + fgv5.summary) and checks that the module ran the setting it was asked to run. Rows are
assembled in grid order, so the file does not depend on the worker count.

Output columns, in this order:
  p_<name>   one per dimension of DIMS, in DIMS order (p_exitStyle is text; null = None)
  ExitMode, TpStyle, pipSize, slPips, tpRPips, runTrailPips, partPct, runBE, runTrailAtr, useTrail
             the Pine inputs that exitStyle sets (null where the style does not set it); not dimensions
  floor_ok   see above
  then every field of fgv5.summary in its own order (all scalars), net_pct / h1r_pct / h2r_pct R-based (SCORING):
  start, end, bars, trades, net_pct, pf, win_pct, max_dd_pct, max_dd_init_pct, long, short (REAL sides),
  raw_long, raw_short, blocked_long, blocked_short (the FGD funnel, normal frame), half1_pct, half2_pct, exposure,
  final_equity, exit_<kind> (sl, tp, tp_part, be, runner, trail, reverse, opp, time, end), zero_length, h1r_pct,
  h2r_pct, h1_trades, h2_trades, avg_bars_held, costs, part_<kind>, tv_rows, be_trades, be_no_tp, net_r, h1_r,
  h2_r, orders_placed, orders_replaced, orders_filled, orders_cancelled, oca_cancelled, orders_unfilled_end,
  both_pending_bars, gap_entries, zero_qty, sl_lt_slip, slippage_paid, neg_equity_bars, min_equity,
  max_notional_x, sig_buy, sig_sell
  net_pct_money, h1r_pct_money, h2r_pct_money (last): fgv5.summary's net_pct, h1r_pct, h2r_pct (NaN stays NaN)
Nothing else: no index, no pair / tf column (they are in the file name; the parquet's key-value metadata "calib"
holds strategy, pair, tf, path, cost, the scoring statement, the sizing, the number of settings, the window, the
exit styles, the runner trail pair and its floor measurement, and the sha256 of fgv5.py and fgf.py that produced
the rows: the files as they were when this process imported them, not as they are when the file is written).
pf is +inf without a losing trade and NaN without trades; win_pct and avg_bars_held are NaN without trades;
max_notional_x is NaN when no entry had a positive eq_before; h1r_pct_money / h2r_pct_money NaN as fgv5 says.
--one prints the same non-p_ columns in the same order (Python's json: Infinity / NaN, null) plus "setting" =
{strategy, pair, tf, path, cost, p (the canonical p_ values), in_grid, row (its row number in the cell's grid
file), sizing, QtyMode, fixedQty, riskPct, maxQty, qtyStep (as the module resolved them), runner_trail (the cell's
r1, r2), exit (the exit inputs as the module resolved them)}.
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
import fgv5  # noqa: E402
import fgf  # noqa: E402  (imported by fgv5; named here for the provenance and the cache release)

STRATEGY = 'fgv5'
MAX_WORKERS = 3
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
PATH = 'mag'             # the sweep's scoring: 1-minute fills ...
COST = 'ours'            # ... with our costs
CHUNK = 37               # exit settings per worker task (888 = 24 x 37)

# ---------------------------------------------------------------------------------------------
# the grid (SPEC_fgv5.md section 14)
# ---------------------------------------------------------------------------------------------
BURSTS = (0.3, 0.5, 1.0)
ZONES = (1, 2, 3)
FILTERS = (False, True)
INVS = (False, True)
ENTRY_DISTS = (0.0, 0.25, 0.5)
REVERSES = (True, False)
STYLES = ('pips_default', 'fixed', 'part30', 'run')
SL_MULTS = (0.25, 0.5, 1.0, 2.0)
TP_RS = (1.5, 3.0, 5.0)
MAX_BARS = (0, 12)

# the exit rules of exitStyle (None = the runner's trail distance of the cell, r1 / r2)
PIPS_RUNNER = 600.0                       # runTrailPips of 'pips_default', in $ (pipSize 1)
STYLE_INPUTS = {
    'pips_default': {'ExitMode': 'Pips', 'TpStyle': 'Partial + runner', 'pipSize': 1.0, 'slPips': 30.0,
                     'tpRPips': 5.0, 'runTrailPips': PIPS_RUNNER, 'partPct': 30.0, 'runBE': True},
    'fixed': {'ExitMode': 'ATR', 'TpStyle': 'Fixed', 'useTrail': False},
    'part30': {'ExitMode': 'ATR', 'TpStyle': 'Partial + runner', 'partPct': 30.0, 'runBE': True, 'runTrailAtr': 'r1'},
    'run': {'ExitMode': 'ATR', 'TpStyle': 'Partial + runner', 'partPct': 0.0, 'runBE': True, 'runTrailAtr': 'r2'},
}
# the Pine inputs that exitStyle sets, written as columns that are not dimensions (null where not set)
INPUT_COLS = (('ExitMode', str), ('TpStyle', str), ('pipSize', float), ('slPips', float), ('tpRPips', float),
              ('runTrailPips', float), ('partPct', float), ('runBE', bool), ('runTrailAtr', float),
              ('useTrail', bool))
INPUT_NAMES = tuple(k for k, _ in INPUT_COLS)

# runner trail distances (r1, r2) per cell, the table of section 14
TRAIL_LADDER = (1.5, 2.5, 3.5, 5.0, 6.5, 8.5)
TRAIL_MIN = 1.5
FLOOR_PCT = {'BTC': 0.1, 'XAU': 0.05}                     # 1-minute noise floor, % of price
TRAIL_R = {('BTC', '1'): (6.5, 8.5), ('BTC', '5'): (2.5, 3.5), ('XAU', '1'): (5.0, 6.5), ('XAU', '5'): (2.5, 3.5)}
TRAIL_R_DEFAULT = (1.5, 2.5)                              # charts 15 .. 240
ATR_LEN = 14

# sizing (not a dimension): the grid runs the file's own; section 14's proposal is --one --risk-sizing
SIZINGS = {'script': {'QtyMode': 'Fixed', 'fixedQty': 10.0, 'maxQty': 50.0, 'qtyStep': 1.0},
           'risk': {'QtyMode': 'Risk %', 'riskPct': 1.0, 'maxQty': 1e9, 'qtyStep': 0.000001}}
GRID_SIZING = 'script'

# the R-based scoring of this runner: column -> fgv5.summary field it holds; the money figures move to *_money
R_COLS = {'net_pct': 'net_r', 'h1r_pct': 'h1_r', 'h2r_pct': 'h2_r'}
MONEY_COLS = (('net_pct_money', 'net_pct'), ('h1r_pct_money', 'h1r_pct'), ('h2r_pct_money', 'h2r_pct'))
SCORING = ('R-based: h1r_pct := h1_r, h2r_pct := h2_r, net_pct := net_r (sums of the R multiples of the trades '
           'entered in the first half / second half / whole window; R = the trade\'s stop distance x quantity, '
           'r_mult = pnl / (sl_dist x qty), NaN skipped); fgv5.summary\'s money figures are net_pct_money, '
           'h1r_pct_money, h2r_pct_money (fgv5 net_pct, h1r_pct, h2r_pct). Reason: the file trades a fixed 10 units '
           'on 100,000 with no margin, equity goes below zero on BTC and the money halves are NaN there.')

# name, values, kind as CALIB_SPEC.md asks; extra keys: side = 'signal' (a parameter of fgv5.prepare) or 'exit'
# (of fgv5.simulate), default = the script's default input, unused_when = the value of another dimension with
# which this one is listed once (its value is None)
DIMS = [
    {'name': 'burstAtrMult', 'values': list(BURSTS), 'kind': 'ordinal', 'side': 'signal', 'default': 0.5},
    {'name': 'minAlignedZones', 'values': list(ZONES), 'kind': 'ordinal', 'side': 'signal', 'default': 2},
    {'name': 'fgfOn', 'values': list(FILTERS), 'kind': 'categorical', 'side': 'signal', 'default': True},
    {'name': 'inv', 'values': list(INVS), 'kind': 'categorical', 'side': 'exit', 'default': False},
    {'name': 'entryDistAtrMult', 'values': list(ENTRY_DISTS), 'kind': 'ordinal', 'side': 'exit', 'default': 0.25},
    {'name': 'allowReverse', 'values': list(REVERSES), 'kind': 'categorical', 'side': 'exit', 'default': True},
    {'name': 'exitStyle', 'values': list(STYLES), 'kind': 'categorical', 'side': 'exit', 'default': 'pips_default'},
    {'name': 'slAtrMult', 'values': list(SL_MULTS), 'kind': 'ordinal', 'side': 'exit', 'default': None,
     'unused_when': {'exitStyle': 'pips_default'}},
    {'name': 'tpR', 'values': list(TP_RS), 'kind': 'ordinal', 'side': 'exit', 'default': None,
     'unused_when': {'exitStyle': 'pips_default'}},
    {'name': 'maxBarsHeld', 'values': list(MAX_BARS), 'kind': 'categorical', 'side': 'exit', 'default': 0},
]
DIM_NAMES = [d['name'] for d in DIMS]
SIGNAL_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'signal')
EXIT_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'exit')
UNUSED_WHEN = {d['name']: next(iter(d['unused_when'].items())) for d in DIMS if 'unused_when' in d}
DIM_DOC = {
    'burstAtrMult': 'Burst threshold, ATR(14) multiples (DistUnit ATR)',
    'minAlignedZones': 'Minimum TDI zones aligned with the parent (1 = parent only, 3 = parent + 2x + 4x)',
    'fgfOn': 'direction filter: Enable filter',
    'inv': 'Inverted direction: opposite side at the same entries (Update 1, fgvInv)',
    'entryDistAtrMult': 'Entry distance beyond the spread, ATR(14) multiples',
    'allowReverse': 'Opposite signal may reverse an open position',
    'exitStyle': 'Exit rule (derived: its Pine inputs are the non-p_ columns ExitMode .. useTrail)',
    'slAtrMult': 'Stop, ATR(14) multiples (ExitMode ATR; None with pips_default)',
    'tpR': 'Target R (fixed) / partial target, breakeven trigger and trail activation (part30, run); None with '
           'pips_default',
    'maxBarsHeld': 'Time stop, bars (0 = off)',
}
_DIM_TYPE = {'burstAtrMult': float, 'minAlignedZones': int, 'fgfOn': bool, 'inv': bool, 'entryDistAtrMult': float,
             'allowReverse': bool, 'exitStyle': str, 'slAtrMult': float, 'tpR': float, 'maxBarsHeld': int}
_PA_TYPE = {str: pa.string(), int: pa.int64(), float: pa.float64(), bool: pa.bool_()}

DEFAULT_P = {d['name']: d['default'] for d in DIMS}
DEFAULT = DEFAULT_P

# SIGNAL settings: the parameters of fgv5.prepare. fgfOn is the innermost loop.
SIGNALS = [{'burstAtrMult': b, 'minAlignedZones': z, 'fgfOn': f} for b in BURSTS for z in ZONES for f in FILTERS]
_BRACKETS = [('pips_default', None, None)] + [(st, s, t) for st in STYLES[1:] for s in SL_MULTS for t in TP_RS]
# EXIT settings: the parameters of fgv5.simulate, the same 888 for every signal setting
EXITS = [{'inv': i, 'entryDistAtrMult': e, 'allowReverse': r, 'exitStyle': st, 'slAtrMult': s, 'tpR': t,
          'maxBarsHeld': m}
         for i in INVS for e in ENTRY_DISTS for r in REVERSES for st, s, t in _BRACKETS for m in MAX_BARS]
N_GRID = len(SIGNALS) * len(EXITS)                       # 15,984


def signals(pair=None, tf=None):
    """The SIGNAL settings of a cell (the same 18 in every cell)."""
    return [dict(s) for s in SIGNALS]


def exits_for(sig=None, pair=None, tf=None):
    """The EXIT settings of one SIGNAL setting (the same 888 for every signal setting and cell)."""
    return EXITS


def merge(sig, x):
    """One grid setting: every dimension of DIMS, in DIMS order."""
    d = dict(sig)
    d.update(x)
    return {k: d[k] for k in DIM_NAMES}


def grid(pair=None, tf=None, sig_idx=None):
    """Every setting of a cell, in file order: for each SIGNAL setting, its EXIT settings."""
    S = signals(pair, tf)
    idx = range(len(S)) if sig_idx is None else sig_idx
    return [merge(S[si], x) for si in idx for x in exits_for(S[si], pair, tf)]


def n_settings(pair=None, tf=None):
    return N_GRID


def key(p):
    return tuple(p[k] for k in DIM_NAMES)


def runner_trail(pair, tf):
    """(r1, r2) of the cell, the table of section 14."""
    return TRAIL_R.get((pair, str(tf)), TRAIL_R_DEFAULT)


def style_inputs(style, pair, tf):
    """The Pine inputs that one exitStyle sets, on one cell (runTrailAtr = the cell's r1 / r2)."""
    q = dict(STYLE_INPUTS[style])
    if 'runTrailAtr' in q:
        r1, r2 = runner_trail(pair, tf)
        q['runTrailAtr'] = r1 if q['runTrailAtr'] == 'r1' else r2
    return q


def inputs_of(p, pair, tf):
    """The values of the INPUT_COLS columns of one setting (None where its style does not set the input)."""
    q = style_inputs(p['exitStyle'], pair, tf)
    return {k: q.get(k) for k in INPUT_NAMES}


def signal_params(sig):
    """A SIGNAL setting as fgv5.prepare params (everything else at the script's defaults)."""
    return {'burstAtrMult': float(sig['burstAtrMult']), 'minAlignedZones': int(sig['minAlignedZones']),
            'fgfOn': bool(sig['fgfOn'])}


def exit_params(x, pair, tf, path=PATH, cost=COST, sizing=GRID_SIZING):
    """An EXIT setting as fgv5.simulate params: the direction, entry distance, reverse switch and time stop, the
    Pine inputs of the exit style (slAtrMult / tpR only for the ATR styles), the sizing, path and cost."""
    X = {'fgvInv': bool(x['inv']), 'entryDistAtrMult': float(x['entryDistAtrMult']),
         'allowReverse': bool(x['allowReverse']), 'maxBarsHeld': int(x['maxBarsHeld'])}
    X.update(style_inputs(x['exitStyle'], pair, tf))
    if x['exitStyle'] != 'pips_default':
        X['slAtrMult'] = float(x['slAtrMult'])
        X['tpR'] = float(x['tpR'])
    X.update(SIZINGS[sizing])
    X['path'] = path
    X['cost'] = cost
    return X


def normalize(raw, off_grid=False):
    """A setting given as a mapping of p_ values (keys with or without 'p_'; None / NaN / missing = unused) ->
    the canonical dict over DIM_NAMES. slAtrMult / tpR with exitStyle 'pips_default' are set to None whatever was
    given (Pips mode reads neither). Raises ValueError for an unknown key, a missing used dimension, or (unless
    off_grid, for the numeric dimensions) a value that is not in the grid."""
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
            if not isinstance(v, str):
                raise ValueError('%s: %r is not a string' % (name, v))
        if v not in d['values']:
            if not off_grid or ty in (str, bool):
                raise ValueError('%s: %r is not in the grid %r' % (name, v, d['values']))
        out[name] = v
    return out


_ROWS: dict = {}


def row_of(pair, tf, p):
    """The row number of a setting in the cell's grid file, None when it is not one of the cell's rows."""
    if 'rows' not in _ROWS:
        _ROWS['rows'] = {key(q): i for i, q in enumerate(grid(pair, tf))}
    return _ROWS['rows'].get(key(p))


def in_grid(pair, tf, p):
    return row_of(pair, tf, p) is not None


# ---------------------------------------------------------------------------------------------
# what a run must echo; the floor of the runner trail distances
# ---------------------------------------------------------------------------------------------
def _check_prepared(sig, P, pair, tf):
    """fgv5.prepare ran the SIGNAL setting it was asked for: the three swept inputs as given, every other signal
    input (and the filter's) at the script default, the zones on chart / 2x / 4x, no injected gate."""
    want = {k: fgv5.DEFAULTS[k] for k in P['sigQ']}
    want.update(burstAtrMult=float(sig['burstAtrMult']), minAlignedZones=int(sig['minAlignedZones']),
                fgfOn=bool(sig['fgfOn']))
    csec = fgv5.tf_seconds(tf)
    zones = [fgv5.tf_name(tf), fgv5.tf_from_seconds(2 * csec), fgv5.tf_from_seconds(4 * csec)]
    ok = (P['sigQ'] == want and P['ordQ'] == fgv5.ORD_DEFAULTS and not P['injected'] and P['pair'] == pair
          and P['tf'] == str(tf) and P['parent_tf'] == fgv5.tf_name(tf) and list(P['zone_tfs'][:3]) == zones
          and (P['start'], P['end']) == tuple(fgv5.WINDOWS[pair]))
    if not ok:
        raise RuntimeError('fgv5.prepare did not run the signal setting %r on %s %s' % (sig, pair, tf))


def _check_run(X, R):
    """fgv5.simulate ran the EXIT setting it was asked for: its resolved inputs (R['Q']) hold every value given."""
    q = R['Q']
    for k, v in X.items():
        if q[fgv5.ALIASES.get(k, k)] != v:
            raise RuntimeError('fgv5.simulate did not run %r: %s is %r' % (X, k, q[fgv5.ALIASES.get(k, k)]))
    if R['inv'] != X['fgvInv'] or R['path'] != X['path'] or R['partial'] != (X['TpStyle'] == 'Partial + runner'):
        raise RuntimeError('fgv5.simulate did not run %r: inv %r path %r partial %r'
                           % (X, R['inv'], R['path'], R['partial']))


def ladder_pick(p10, floor):
    """(r1, r2) by the rule of section 14: r1 = the smallest ladder value >= max(1.5, floor / p10), r2 = the
    next ladder value (None past the end of the ladder)."""
    need = max(TRAIL_MIN, floor / p10)
    i = next((j for j, v in enumerate(TRAIL_LADDER) if v >= need), None)
    if i is None:
        return None, None
    return TRAIL_LADDER[i], (TRAIL_LADDER[i + 1] if i + 1 < len(TRAIL_LADDER) else None)


def cell_floor(pair, tf, P):
    """The runner trail distances of the cell against the 1-minute noise floor, measured on the window: the 10th
    percentile of ATR(14) / close (%) times r1 / r2; the $600 'pips_default' runner as % of the highest close."""
    tf = str(tf)
    c = P['c']
    atr = P['atr14']
    p10 = float(np.nanpercentile(atr / c * 100.0, 10))
    floor = FLOOR_PCT[pair]
    r1, r2 = runner_trail(pair, tf)
    m1, m2 = ladder_pick(p10, floor)
    pips_pct = float(PIPS_RUNNER / np.nanmax(c) * 100.0)
    ok = {'pips_default': bool(pips_pct >= floor), 'fixed': True, 'part30': bool(r1 * p10 >= floor),
          'run': bool(r2 * p10 >= floor)}
    return {'atr_len': ATR_LEN, 'p10_atr_pct': p10, 'floor_pct': floor, 'floor_over_p10': floor / p10,
            'r1': r1, 'r2': r2, 'ladder_r1': m1, 'ladder_r2': m2, 'table_matches_ladder': (m1, m2) == (r1, r2),
            'r1_pct_at_p10': r1 * p10, 'r2_pct_at_p10': r2 * p10, 'pips_runner_pct_at_max_close': pips_pct,
            'floor_ok': ok}


# ---------------------------------------------------------------------------------------------
# the stored row: the R-based scoring
# ---------------------------------------------------------------------------------------------
def score_fields(cols):
    """The result columns of a row from the fgv5.summary field names: the summary's own order with net_pct /
    h1r_pct / h2r_pct R-based, then the three money columns."""
    return list(cols) + [m for m, _ in MONEY_COLS]


def scored(s):
    """fgv5.summary -> the row's result values (dict, in score_fields order)."""
    out = {}
    for k, v in s.items():
        out[k] = s[R_COLS[k]] if k in R_COLS else v
    for m, k in MONEY_COLS:
        out[m] = s[k]
    return out


# ---------------------------------------------------------------------------------------------
# one setting
# ---------------------------------------------------------------------------------------------
def one(pair, tf, p, path=PATH, cost=COST, off_grid=False, sizing=GRID_SIZING, cache=None):
    """The full row (floor_ok, the exit style's inputs, the scored summary) of one setting, computed alone: its
    own fgv5.prepare and one fgv5.simulate. p: a mapping of p_ values (see normalize). sizing 'script' (the
    grid's, the file's own) or 'risk' (section 14's proposal). cache: a dict that keeps the prepared inputs
    between calls of one process (tests)."""
    tf = str(tf)
    p = normalize(p, off_grid)
    sig = {k: p[k] for k in SIGNAL_DIMS}
    x = {k: p[k] for k in EXIT_DIMS}
    sp = signal_params(sig)
    ck = (pair, tf, tuple(sorted(sp.items())))
    P = cache.get(ck) if cache is not None else None
    if P is None:
        P = fgv5.prepare(pair, tf, sp)
        if cache is not None:
            cache[ck] = P
    _check_prepared(sig, P, pair, tf)
    X = exit_params(x, pair, tf, path, cost, sizing)
    R = fgv5.simulate(P, X)
    _check_run(X, R)
    s = fgv5.summary(P, R)
    fl = cell_floor(pair, tf, P)
    out = {}
    out.update(inputs_of(p, pair, tf))
    out['floor_ok'] = fl['floor_ok'][p['exitStyle']]
    out.update(scored(s))
    row = row_of(pair, tf, p)
    Q = R['Q']
    out['setting'] = {'strategy': STRATEGY, 'pair': pair, 'tf': tf, 'path': path, 'cost': cost, 'p': p,
                      'in_grid': row is not None, 'row': row, 'sizing': sizing,
                      'QtyMode': Q['QtyMode'], 'fixedQty': Q['fixedQty'], 'riskPct': Q['riskPct'],
                      'maxQty': Q['maxQty'], 'qtyStep': Q['qtyStep'], 'runner_trail': list(runner_trail(pair, tf)),
                      'exit': {k: Q[k] for k in ('ExitMode', 'TpStyle', 'pipSize', 'slPips', 'tpRPips',
                                                 'runTrailPips', 'partPct', 'runBE', 'runTrailAtr', 'useTrail',
                                                 'slAtrMult', 'tpR', 'atrLen', 'fgvInv', 'entryDistAtrMult',
                                                 'allowReverse', 'maxBarsHeld', 'entryValidBars', 'Direction',
                                                 'exitOnOpposite')},
                      'scoring': 'net_pct / h1r_pct / h2r_pct = net_r / h1_r / h2_r (R); money in *_money'}
    # the column order of a row: the inputs, floor_ok, the scored summary (then the setting)
    order = list(INPUT_NAMES) + ['floor_ok'] + score_fields(s.keys()) + ['setting']
    return {k: out[k] for k in order}


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
# arrays of a prepared input that simulate / summary read; window copies, equal ones kept once per cell
_ARRAYS = ('o', 'h', 'l', 'c', 't_open', 't_close', 'atr14', 'buySig', 'sellSig', 'buyOk', 'sellOk')


def _slim(P, pool):
    """Replace every array of a prepared input by a window copy (they are views into the module's bar / signal
    caches, which hold the whole files), and by the one already seen in this cell when equal (the bars and ATR
    of the window, the filter permissions, the signals shared by filter off / on)."""
    for k in _ARRAYS:
        a = P[k]
        seen = pool.setdefault(k, [])
        for b in seen:
            if b.dtype == a.dtype and b.shape == a.shape and np.array_equal(a, b, equal_nan=a.dtype.kind == 'f'):
                P[k] = b
                break
        else:
            b = np.ascontiguousarray(a).copy()
            seen.append(b)
            P[k] = b


def _free_caches(bars=False):
    """The module caches that the prepared inputs no longer need (signals, permissions, ATR, sub-bars, the TDI
    series and fgf's filter series); with bars, also the bar files of fgv5 and fgf."""
    fgv5._SIG.clear()
    fgv5._PERM.clear()
    fgv5._SUB.clear()
    fgv5._ATR.clear()
    fgv5._DIRS.clear()
    for name in ('_DIR', '_FILTER'):
        c = getattr(fgf, name, None)
        if isinstance(c, dict):
            c.clear()
    if bars:
        fgv5._CHART.clear()
        fgv5._TFBARS.clear()
        c = getattr(fgf, '_BARS', None)
        if isinstance(c, dict):
            c.clear()
    gc.collect()
    # hand the freed memory back to the system before workers are forked (BTC 1: 1.5 GB -> 0.4 GB): arrow's
    # pool keeps the bar files' buffers, glibc the freed heap
    try:
        pa.default_memory_pool().release_unused()
    except Exception:   # noqa: BLE001
        pass
    try:
        import ctypes
        ctypes.CDLL('libc.so.6').malloc_trim(0)
    except Exception:   # noqa: BLE001
        pass


def prepare_cell(pair, tf, sig_idx=None, verbose=False):
    """fgv5.prepare once per SIGNAL setting of the cell (all, or those of sig_idx), the 1-minute sub-bars once,
    the floor of the runner trail distances, the module caches dropped, the kernel compiled. Returns the cell:
    P {signal index: prepared input}, the summary columns and timings."""
    tf = str(tf)
    S = signals(pair, tf)
    idx = list(range(len(S))) if sig_idx is None else [int(i) for i in sig_idx]
    t0 = time.time()
    c0 = time.process_time()
    P = {}
    pool = {}
    sig_key = lambda s: (s['burstAtrMult'], s['minAlignedZones'])
    for j, si in enumerate(idx):
        Pk = fgv5.prepare(pair, tf, signal_params(S[si]))
        _check_prepared(S[si], Pk, pair, tf)
        _slim(Pk, pool)
        P[si] = Pk
        if j + 1 == len(idx) or sig_key(S[idx[j + 1]]) != sig_key(S[si]):
            # the next signal setting computes another signal: drop fgv5's signal cache (whole-file zone arrays,
            # about 170 MB per signal on BTC 1); filter off and on of one signal (consecutive) share one entry
            fgv5._SIG.clear()
            gc.collect()
    p0 = P[idx[0]]
    for si, Pk in P.items():
        if (Pk['w0'], Pk['w1'], Pk['mid'], Pk['mid_j'], Pk['n']) != (p0['w0'], p0['w1'], p0['mid'], p0['mid_j'], p0['n']):
            raise ValueError('%s %s signal setting %d: window rows differ' % (pair, tf, si))
    t_sig = time.time() - t0
    t1 = time.time()
    n_sub = 0
    if PATH == 'mag':
        sub = tuple(np.ascontiguousarray(a) for a in fgv5.get_sub(p0))    # built once, checked against the bars
        n_sub = len(sub[1])
        for Pk in P.values():
            Pk['sub'] = sub
    floor = cell_floor(pair, tf, p0)
    t_sub = time.time() - t1
    _free_caches(bars=True)
    t2 = time.time()
    x0 = exits_for(S[idx[0]], pair, tf)[0]
    X0 = exit_params(x0, pair, tf)
    R0 = fgv5.simulate(p0, X0)                                         # compile / load the kernel
    _check_run(X0, R0)
    s = fgv5.summary(p0, R0)
    t_jit = time.time() - t2
    cols = score_fields(s.keys())
    sc = scored(s)
    kinds = {}
    for k in cols:
        v = sc[k]
        if isinstance(v, (bool, np.bool_)):
            kinds[k] = bool
        elif isinstance(v, (int, np.integer)):
            kinds[k] = int
        else:
            kinds[k] = float
    cell = dict(pair=pair, tf=tf, idx=idx, S=S, P=P, cols=cols, kinds=kinds, bars=int(p0['n']), n_sub=n_sub,
                floor=floor, prepares=len(idx), t_sig=t_sig, t_sub=t_sub, t_jit=t_jit, t_prep=time.time() - t0,
                cpu_prep=time.process_time() - c0)
    if verbose:
        print('  %s %s: %d chart bars, %d 1-minute bars; %d signal settings prepared in %.1fs, sub-bars %.1fs, '
              'kernel %.1fs' % (pair, tf, cell['bars'], n_sub, len(idx), t_sig, t_sub, t_jit), flush=True)
        print('  runner trail (r1, r2) = (%g, %g): 10th percentile of ATR(14)/close %.4f %%, floor %.2f %% (floor / '
              'p10 = %.2f, ladder pick (%s, %s), table %s): r1 %.4f %%, r2 %.4f %% of price; the $600 pips runner '
              '%.3f %% of the highest close; floor_ok by style %s'
              % (floor['r1'], floor['r2'], floor['p10_atr_pct'], floor['floor_pct'], floor['floor_over_p10'],
                 floor['ladder_r1'], floor['ladder_r2'], 'matches' if floor['table_matches_ladder'] else 'DIFFERS',
                 floor['r1_pct_at_p10'], floor['r2_pct_at_p10'], floor['pips_runner_pct_at_max_close'],
                 floor['floor_ok']), flush=True)
    return cell


def _work(task):
    si, i0, i1 = task
    t0 = time.time()
    c0 = time.process_time()
    P = _G['P'][si]
    X = _G['X'][si]
    cols = _G['cols']
    pair = _G['pair']
    tf = _G['tf']
    out = []
    for i in range(i0, i1):
        xp = exit_params(X[i], pair, tf)
        R = fgv5.simulate(P, xp)
        _check_run(xp, R)
        s = scored(fgv5.summary(P, R))
        out.append(tuple(s[k] for k in cols))
    return si, i0, out, time.time() - t0, time.process_time() - c0


def run_prepared(cell, workers=MAX_WORKERS, sig_idx=None, chunk=CHUNK, verbose=False, x_idx=None):
    """Simulate every exit setting of the prepared signal settings (all of the cell, or sig_idx; x_idx: only
    those exit settings, tests). Returns (res {signal index: [summary tuple per exit setting]}, info)."""
    pair, tf = cell['pair'], cell['tf']
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    X = {si: (exits_for(cell['S'][si], pair, tf) if x_idx is None
              else [exits_for(cell['S'][si], pair, tf)[j] for j in x_idx]) for si in idx}
    _G.clear()
    _G.update(P=cell['P'], X=X, cols=cell['cols'], pair=pair, tf=tf)
    tasks = [(si, i0, min(i0 + chunk, len(X[si]))) for si in idx for i0 in range(0, len(X[si]), chunk)]
    total = sum(t[2] - t[1] for t in tasks)
    res = {si: [None] * len(X[si]) for si in idx}
    t1 = time.time()
    state = dict(done=0, busy=0.0, cpu=0.0, next=0.1)

    def collect(result):
        si, i0, out, dt, dc = result
        res[si][i0:i0 + len(out)] = out
        state['busy'] += dt
        state['cpu'] += dc
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
    """The rows in grid order as an arrow table: p_<name> per dimension (null = None), the Pine inputs of the
    exit style, floor_ok, then the scored summary fields. Column types are fixed here (they do not depend on the
    values)."""
    pair, tf = cell['pair'], cell['tf']
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    G = grid(pair, tf, idx)
    vals = [r for si in idx for r in res[si]]
    if len(G) != len(vals):
        raise RuntimeError('grid and results differ in length')
    names, arrays = [], []
    for name in DIM_NAMES:
        names.append('p_' + name)
        arrays.append(pa.array([p[name] for p in G], type=_PA_TYPE[_DIM_TYPE[name]]))      # None -> null
    ins = [inputs_of(p, pair, tf) for p in G]
    for name, ty in INPUT_COLS:
        names.append(name)
        arrays.append(pa.array([q[name] for q in ins], type=_PA_TYPE[ty]))                  # None -> null
    names.append('floor_ok')
    arrays.append(pa.array([cell['floor']['floor_ok'][p['exitStyle']] for p in G], type=pa.bool_()))
    for j, k in enumerate(cell['cols']):
        ty = cell['kinds'][k]
        col = [v[j] for v in vals]
        if k in names:
            raise RuntimeError('summary field %r collides with a column' % k)
        names.append(k)
        if ty is float:
            arrays.append(pa.array(np.asarray(col, dtype=np.float64), type=pa.float64()))     # NaN stays NaN
        else:
            arrays.append(pa.array(col, type=_PA_TYPE[ty]))
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


# The code that produces the rows of this process: fgv5.py and fgf.py as they were when it imported them. A
# module edited while a long run is under way is not the code that ran, so the sha256 is taken here, once.
_SRC_SHA = {'fgv5': _sha256(fgv5.__file__), 'fgf': _sha256(fgf.__file__)}


def file_meta(pair, tf, n, floor=None):
    """What produced a cell's file (stored in the parquet's key-value metadata, key "calib")."""
    r1, r2 = runner_trail(pair, tf)
    return {'strategy': STRATEGY, 'pair': pair, 'tf': str(tf), 'path': PATH, 'cost': COST, 'settings': int(n),
            'window': [int(v) for v in fgv5.WINDOWS[pair]], 'scoring': SCORING,
            'r_columns': dict(R_COLS), 'money_columns': {m: k for m, k in MONEY_COLS},
            'sizing': dict(SIZINGS[GRID_SIZING]), 'initial_capital': fgv5.INITIAL_CAPITAL,
            'exit_styles': {k: style_inputs(k, pair, tf) for k in STYLES}, 'runner_trail': [r1, r2],
            'floor': floor, 'fgv5_sha256': _SRC_SHA['fgv5'], 'fgf_sha256': _SRC_SHA['fgf']}


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
    """One (pair, tf) cell: prepare, simulate the grid, write the parquet (and DIMS). sig_idx: only those signal
    settings (tests; never written). Returns (DataFrame, info)."""
    tf = str(tf)
    if write and sig_idx is not None:
        raise ValueError('a partial grid is never written')
    t0 = time.time()
    cell = prepare_cell(pair, tf, sig_idx, verbose)
    res, info = run_prepared(cell, workers, None, chunk, verbose)
    t = table(cell, res)
    df = t.to_pandas()
    info.update(pair=pair, tf=tf, rows=len(df), bars=cell['bars'], n_sub=cell['n_sub'], t_prep=cell['t_prep'],
                t_sig=cell['t_sig'], t_sub=cell['t_sub'], t_jit=cell['t_jit'], prepares=cell['prepares'],
                floor=cell['floor'], file=None)
    if write:
        if len(df) != n_settings(pair, tf):
            raise RuntimeError('%s %s: %d rows, the grid has %d' % (pair, tf, len(df), n_settings(pair, tf)))
        out_dir = out_dir or os.path.join(W, 'out')
        os.makedirs(out_dir, exist_ok=True)
        path_out = os.path.join(out_dir, 'calib_%s_%s_%s.parquet' % (STRATEGY, pair, tf))
        meta = file_meta(pair, tf, len(df), cell['floor'])
        _write_atomic(path_out, lambda tmp: write_parquet(t, tmp, meta))
        write_dims(out_dir)
        info['file'] = path_out
    info['t_total'] = time.time() - t0
    info['rows_floor_ok'] = int(df['floor_ok'].sum())
    info['rows_neg_equity'] = int((df['neg_equity_bars'] > 0).sum())
    info['rows_money_half_nan'] = int((df['h1r_pct_money'].isna() | df['h2r_pct_money'].isna()).sum())
    info['rows_30_trades_each_half'] = int(((df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).sum())
    info['rows_both_halves_pos_30'] = int(((df['h1_trades'] >= 30) & (df['h2_trades'] >= 30) & (df['h1r_pct'] > 0)
                                           & (df['h2r_pct'] > 0) & df['floor_ok']).sum())
    if verbose:
        w = max(info['workers'], 1)
        print('  %s %s done: %d rows%s | prep %.1fs, runs %.1fs with %d workers (%.2f worker-s, %.5fs per '
              'setting per worker; workers busy %.0f%%; worker CPU %.5fs per setting = %.1fs runs with a free CPU '
              'per worker), total %.1fs; load average %.2f'
              % (pair, tf, len(df), (' -> ' + info['file']) if info['file'] else ' (not written)', info['t_prep'],
                 info['t_run'], w, info['busy'], info['busy'] / max(info['settings'], 1),
                 100.0 * info['busy'] / max(info['t_run'] * w, 1e-9), info['cpu'] / max(info['settings'], 1),
                 info['cpu'] / w, info['t_total'], os.getloadavg()[0]), flush=True)
        print('  rows with floor_ok: %d of %d; rows whose equity went to zero or below at a bar close: %d; rows with a '
              'money half NaN (h1r_pct_money / h2r_pct_money): %d; rows with >= 30 trades in each half: %d, of which '
              'positive in both R halves: %d'
              % (info['rows_floor_ok'], len(df), info['rows_neg_equity'], info['rows_money_half_nan'],
                 info['rows_30_trades_each_half'], info['rows_both_halves_pos_30']), flush=True)
    _G.clear()
    return df, info


def estimate_cell(pair, tf, workers=MAX_WORKERS, per_signal=8, seed=20261127, verbose=True):
    """Estimated time of the full cell from ONE process: the real preparation, then per_signal random exit
    settings of every signal setting timed one by one; run time = sum over the signal settings of (mean sampled
    time x its number of exit settings) / workers. Two estimates: from the wall clock (the machine as loaded as
    it is now) and from this process' CPU time (the 3 workers each having a free CPU). Writes nothing."""
    tf = str(tf)
    cell = prepare_cell(pair, tf, None, verbose)
    rng = np.random.default_rng(seed)
    t_single = 0.0
    c_single = 0.0
    worst = 0.0
    n_s = 0
    t0 = time.time()
    for si in cell['idx']:
        X = exits_for(cell['S'][si], pair, tf)
        P = cell['P'][si]
        tt = []
        cc = []
        for i in rng.choice(len(X), size=min(per_signal, len(X)), replace=False):
            t = time.time()
            c = time.process_time()
            xp = exit_params(X[int(i)], pair, tf)
            R = fgv5.simulate(P, xp)
            _check_run(xp, R)
            scored(fgv5.summary(P, R))
            tt.append(time.time() - t)
            cc.append(time.process_time() - c)
        t_single += float(np.mean(tt)) * len(X)
        c_single += float(np.mean(cc)) * len(X)
        worst = max(worst, max(tt))
        n_s += len(tt)
    n_all = n_settings(pair, tf)
    w = max(workers, 1)
    import resource
    est = dict(pair=pair, tf=tf, bars=cell['bars'], n_sub=cell['n_sub'], settings=n_all, sampled=n_s,
               t_prep=cell['t_prep'], per_setting=t_single / n_all, slowest=worst, single_process_run=t_single,
               workers=workers, est_run=t_single / w, est_total=cell['t_prep'] + t_single / w,
               cpu_prep=cell['cpu_prep'], cpu_per_setting=c_single / n_all,
               est_total_free_cpus=cell['cpu_prep'] + c_single / w, t_sample=time.time() - t0,
               load1=os.getloadavg()[0], peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0)
    if verbose:
        print('  %s %s estimate: prep %.1fs + %d settings x %.5fs (slowest sampled %.4fs; %d sampled) / %d workers '
              '= %.1fs runs -> %.1fs total (%.2f min) at the present load (load average %.2f); by CPU time: prep '
              '%.1fs + %d x %.5fs / %d -> %.1fs (%.2f min) with a free CPU per worker; peak RSS %.0f MB'
              % (pair, tf, est['t_prep'], n_all, est['per_setting'], worst, n_s, workers, est['est_run'],
                 est['est_total'], est['est_total'] / 60.0, est['load1'], est['cpu_prep'], n_all,
                 est['cpu_per_setting'], workers, est['est_total_free_cpus'], est['est_total_free_cpus'] / 60.0,
                 est['peak_rss_mb']), flush=True)
    _G.clear()
    return est


# ---------------------------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------------------------
def _main_one(argv):
    ap = argparse.ArgumentParser(prog='calib_fgv5.py --one', description='the full row of one setting, as JSON')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tf', choices=TFS)
    ap.add_argument('p', help='JSON object of the p_ values of the setting')
    ap.add_argument('--path', choices=('tv', 'mag'), default=PATH)
    ap.add_argument('--cost', choices=tuple(fgv5.COSTS), default=COST)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--risk-sizing', action='store_true',
                   help='section 14\'s "Risk %%" sizing (riskPct 1, maxQty 1e9, qtyStep 0.000001) instead of the '
                        'file\'s Fixed 10 units')
    g.add_argument('--script-sizing', action='store_true',
                   help='the file\'s own sizing (Fixed 10 units): the grid\'s already, so this changes nothing')
    ap.add_argument('--off-grid', action='store_true', help='accept numbers that are not in the grid')
    a = ap.parse_args(argv)
    try:
        raw = json.loads(a.p)
        if not isinstance(raw, dict):
            raise ValueError('the p_ values must be a JSON object')
        out = one(a.pair, a.tf, raw, a.path, a.cost, a.off_grid, 'risk' if a.risk_sizing else 'script')
    except ValueError as e:
        print('calib_fgv5.py --one: %s' % e, file=sys.stderr)
        return 2
    print(json.dumps(out, default=_json_default))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--one' in argv:
        argv.remove('--one')
        return _main_one(argv)
    ap = argparse.ArgumentParser(description='FlashGold v5 Strategy + FGF calibration grid (CALIB_SPEC.md)')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tfs', nargs='+')
    ap.add_argument('--workers', type=int, default=MAX_WORKERS)
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--estimate', action='store_true', help='time a sample in one process; write nothing')
    ap.add_argument('--per-signal', type=int, default=8, help='--estimate: sampled exit settings per signal setting')
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
            print('== calib %s %s %s: %d settings (%d signal settings x %d exit settings), path %s, cost %s, sizing '
                  '%s, scoring: net_pct / h1r_pct / h2r_pct in R (net_r / h1_r / h2_r), money in *_money =='
                  % (STRATEGY, a.pair, tf, n_settings(a.pair, tf), len(SIGNALS), len(EXITS), PATH, COST,
                     SIZINGS[GRID_SIZING]), flush=True)
            run_cell(a.pair, tf, workers, a.out_dir)
        _free_caches(bars=True)
    print('all done in %.1fs' % (time.time() - t0), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
