"""calib_gvl.py: calibration grid of GVLiveV2 | Crypto Polymarket Any-Chart Pre-Candle + FGF
[Update 1] per pair and timeframe, with the direction (Normal / Inverted, Update 1) as a calibrated
input (CALIB_SPEC.md, strategy "gvl"; the grid is section 14 of SPEC_gvl.md), on the canonical
replica gvl.py (prepare / simulate / summary; its filter is fgf.fgf_permissions).

Usage (python3 -I)
  calib_gvl.py PAIR TF [TF ...] [--workers 3] [--out-dir DIR]
      runs the full grid of every (PAIR, TF) cell and writes out/calib_gvl_<PAIR>_<TF>.parquet
      (one row per setting) and out/calib_gvl_dims.json (DIMS). PAIR in BTC, XAU; TF in 1, 5, 15,
      30, 60, 120, 240. Safe to re-run: the files are overwritten (written to a temporary name
      first). Prints the timing of every cell.
  calib_gvl.py --one PAIR TF '<json of p_ values>' [--path tv|mag] [--cost tv|ours|stress]
               [--script-sizing] [--off-grid]
      prints the full summary of ONE setting as one JSON document on stdout (default path mag,
      cost ours = the sweep's scoring). The JSON of p_ values is a row's p_ columns: keys with or
      without the "p_" prefix; every dimension must have a value (none is ever unused).
        --script-sizing  the file's own sizing: maxQty 50 and qtyStep 0.001 instead of the grid's
                         1e9 and 0.000001. NOT a grid dimension: every grid row has the scale-free
                         sizing. It is how a pick is re-checked with the published file's sizing.
        --off-grid       also accepts numbers that are not in the grid (the Pine's own limits
                         still apply), any "fast/slow" EMA pair and the entry mode "Signal Only".
  calib_gvl.py --estimate PAIR TF [TF ...] [--workers 3] [--per-signal 2]
      times the cell's preparation and a random sample of settings in ONE process and prints the
      estimated time of the full cell; writes nothing.

The grid: 20,736 settings per cell = 288 signal settings x 72 exit settings, the same product in
every cell (dimension names as in SPEC_gvl.md section 14)
  signals   emaPair {"5/13", "8/21"} = (fastEmaLen, slowEmaLen) of the EMA-cross signals
            x trendFilterLen {50, 100, 200} x preMinVolScore {0, 35} x preMinVolRise {0, 1}
            x preCloseLocation {0.55, 0.65, 0.75} x preUseTrend {True, False}
            x fgfOn {False, True}: the direction filter. This script has no blocked-signal close.
  exits     preCandleEntryMode {"Market Next Candle", "Stop Next Candle"}
            x inv {False, True} = gvInv, "Inverted direction: opposite side at the same entries"
              (Update 1): the direction dimension, the control of rule C
            x slAtrMult {0.5, 1.0, 2.0}
            x exitStyle {"tp5", "time4", "trail"}: ONE categorical dimension, three whole exit
              rules. The Pine inputs it sets:
                  tp5    tpR 5.0, maxBarsHeld 0, useTrail False      (a 5 R target)
                  time4  tpR 0.0, maxBarsHeld 4, useTrail False      (no target, 4-bar time stop)
                  trail  tpR 0.0, maxBarsHeld 0, useTrail True with the cell's pair below
            x useDailyLossLock {True, False} (True = 3 losing trades per New York day)
  trailing  exitStyle "trail" = ONE (trailActAtr, trailDstAtr) = (2d, d) per cell, the table of
            SPEC_gvl.md section 14: d the smallest of {1, 1.75, 2.5, 3.5, 5, 6.5} for which
            d x ATR(14) / close at the 10th percentile of the window is at least the 1-minute
            noise floor (BTC 0.1 %, XAU 0.05 %):
                BTC 1 (13, 6.5) | BTC 5 (3.5, 1.75) | BTC 15 .. 240 (2, 1)
                XAU 1 (10, 5)   | XAU 5 (3.5, 1.75) | XAU 15 .. 240 (2, 1)
            The pair is not a dimension (one value per cell). Column floor_ok: True when the exit
            style has no trail, else whether the cell's distance meets the floor (measured again
            on the data at every run; True in all 14 cells).
No combination is a structural duplicate of another (with preUseTrend False the trend EMA still
gates the EMA-cross signals), so no dimension is ever None.

Fixed for EVERY row (decisions of the orchestrator, not dimensions):
  scale-free sizing     maxQty = 1e9 and qtyStep = 0.000001 (the file's own are 50 and 0.001), so
                        that neither the 50-unit cap (on gold it caps every default trade at 50 oz,
                        0.01 to 0.24 % of the account at risk instead of 1 %) nor the quantity
                        grain of a shrunken account decides a result. Everything else of the sizing
                        is the script's: Risk 1 % of equity over the stop distance, the script's
                        own margin cap (marginPct 1), capital 100,000.
                        Limit: 0.000001 is the smallest step the Pine input accepts. An account
                        that has lost practically all of its capital (equity x 1 % / stop distance
                        < 0.000001 units: on the 1-minute charts, where a round trip costs about
                        one stop distance, i.e. about 1 % of the account per trade, after one to
                        two thousand trades) can still not size a trade and stops trading. Such a
                        row has zero_qty > 0 (a column); the run prints how many there are.
  tvMargin 0            TradingView's margin rule is not modelled (SPEC_gvl.md G14).
Everything else stays at the script's defaults (RSI filter on, radar "Chart", ExitMode ATR, atrLen
14, preStopAtrBuffer 0.03, preCancelAfterBars 2, maxDailyLosses 3, no $ lock, the filter's own
inputs).
DEFAULT_P (= DEFAULT) is the default setting: the script's default inputs (8/21, 100, 35, 1,
0.65, trend on, filter OFF, Market Next Candle, normal, 1.0, tp5, lock on) WITH the two values of
the scale-free sizing above (maxQty 1e9, qtyStep 0.000001). It is one row of every cell. It is NOT
literally the published file's default result: that one is `--one ... --script-sizing` on
DEFAULT_P.

SIGNALS (288) are the parameters of gvl.prepare (signal inputs + fgfOn), EXITS (72) those of
gvl.simulate; every signal setting has all 72. DIMS = the 12 dimensions (name, values, kind
'ordinal' / 'categorical'; extra keys: side 'signal' / 'exit', default); row i of a file is
grid()[i] (for each signal setting, its exit settings).

Every setting is scored with path 'mag' (the bracket and the pending pre-candle price orders walk
the 1-minute sub-bars; on chart "1" each bar is its own sub-bar) and cost 'ours'. Per cell: the
filter permissions are computed first and once, gvl.prepare runs ONCE per signal setting (288
times; after the first one a call is a few vector comparisons on cached series), the prepared
inputs are slimmed (arrays that are equal between signal settings are kept once, views into the
bar files are replaced by window copies, the module caches are dropped and the freed memory is
handed back to the system), the 1-minute sub-bars are built once, the kernel is compiled, and only
then at most 3 workers are forked (copy-on-write);
each simulates chunks of exit settings of one prepared input (gvl.simulate + gvl.summary) and
checks that the module ran exactly the setting it was asked to run (every effective input = the
script default, the swept value or the fixed control). Rows are assembled in grid order, so the
file does not depend on the worker count.

Output columns, in this order:
  p_<name>      one per dimension of DIMS, in DIMS order (p_emaPair, p_preCandleEntryMode and
                p_exitStyle are text, the others numbers / booleans; never null)
  fastEmaLen, slowEmaLen, tpR, maxBarsHeld, useTrail, trailActAtr, trailDstAtr
                the Pine inputs that the two composite dimensions set (emaPair, exitStyle);
                trailActAtr / trailDstAtr are the cell's pair on "trail" rows and null elsewhere
                (the trailing stop is off there). They do not start with p_: not dimensions.
  floor_ok      see above
  then every field of gvl.summary (all scalars) in its own order: start, end, bars, trades,
  net_pct, pf, win_pct, max_dd_pct, max_dd_init_pct, long, short (REAL sides), raw_long,
  raw_short, blocked_long, blocked_short (the SIGNAL's side), half1_pct, half2_pct, exposure,
  final_equity, exit_<kind> counts (sl, tp, trail, reverse, time, maxbars, daily_lock, eod, end),
  zero_length, h1r_pct, h2r_pct, h1_trades, h2_trades (the fair halves), avg_bars_held, costs,
  net_r, h1_r, h2_r (R = profit / (stop distance x quantity)), arms_long, arms_short, sig_long,
  sig_short, orders_placed, the pend_* counts, reentry_same_bar, reentry_extreme, reentry_gap_r
  (0 on path 'mag'), pend_fill_after_exit, inherit_ebi, locked_bars, lock_days, zero_qty,
  qty_capped_max, qty_capped_margin, margin_over, margin_refused, max_notional_x.
Nothing else: no index, no pair / tf column (they are in the file name; the parquet's key-value
metadata "calib" holds strategy, pair, tf, path, cost, the number of settings, the window, the
fixed controls, the trailing pair and its floor measurement, and the sha256 of gvl.py and fgf.py
that produced the rows). pf is +inf without a losing trade and NaN without trades; win_pct and
avg_bars_held are NaN without trades. --one prints the same non-p_ columns in the same order
(Python's json: Infinity / NaN, null) plus "setting" = {strategy, pair, tf, path, cost, p (the
canonical p_ values), in_grid, row (its row number in the grid file), sizing, maxQty, qtyStep,
tvMargin, cell_trail (the cell's pair)}.
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
import gvl  # noqa: E402  (imports fgf)

STRATEGY = 'gvl'
MAX_WORKERS = 3
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
PATH = 'mag'             # the sweep's scoring: 1-minute fills ...
COST = 'ours'            # ... with our costs
CHUNK = 24               # exit settings per worker task

# ---------------------------------------------------------------------------------------------
# the grid (SPEC_gvl.md section 14)
# ---------------------------------------------------------------------------------------------
MODE_MARKET = "Market Next Candle"           # preCandleEntryMode, the script default
MODE_STOP = "Stop Next Candle"
EMA_PAIRS = ('5/13', '8/21')                 # emaPair = "fastEmaLen/slowEmaLen"
TREND_LENS = (50, 100, 200)
VOL_SCORES = (0.0, 35.0)
VOL_RISES = (0.0, 1.0)
CLOSE_LOCS = (0.55, 0.65, 0.75)
USE_TRENDS = (True, False)
FILTERS = (False, True)
ENTRY_MODES = (MODE_MARKET, MODE_STOP)
INVS = (False, True)
SL_MULTS = (0.5, 1.0, 2.0)
# exitStyle: the Pine inputs each member sets ("trail": plus the cell's trailActAtr / trailDstAtr)
EXIT_STYLES = {
    'tp5': {'tpR': 5.0, 'maxBarsHeld': 0, 'useTrail': False},
    'time4': {'tpR': 0.0, 'maxBarsHeld': 4, 'useTrail': False},
    'trail': {'tpR': 0.0, 'maxBarsHeld': 0, 'useTrail': True},
}
STYLES = tuple(EXIT_STYLES)
LOCKS = (True, False)

# fixed for every row
SCALE_FREE = {'maxQty': 1e9, 'qtyStep': 0.000001}         # the grid's sizing
SCRIPT_SIZING = {'maxQty': 50.0, 'qtyStep': 0.001}        # the file's own (--one --script-sizing)
TV_MARGIN = 0.0

# trailing: one (trailActAtr, trailDstAtr) = (2d, d) per cell, the table of section 14
ATR_LEN = 14
TRAIL_LADDER = (1.0, 1.75, 2.5, 3.5, 5.0, 6.5)
FLOOR_PCT = {'BTC': 0.1, 'XAU': 0.05}                     # 1-minute noise floor, % of price
TRAIL_D = {('BTC', '1'): 6.5, ('BTC', '5'): 1.75, ('XAU', '1'): 5.0, ('XAU', '5'): 1.75}   # else 1.0

# name, values, kind as CALIB_SPEC.md asks; extra keys (as calib_hrd.py): side = 'signal' (a parameter
# of gvl.prepare) or 'exit' (of gvl.simulate), default = the script's default input
DIMS = [
    {'name': 'emaPair', 'values': list(EMA_PAIRS), 'kind': 'ordinal', 'side': 'signal', 'default': '8/21'},
    {'name': 'trendFilterLen', 'values': list(TREND_LENS), 'kind': 'ordinal', 'side': 'signal', 'default': 100},
    {'name': 'preMinVolScore', 'values': list(VOL_SCORES), 'kind': 'ordinal', 'side': 'signal', 'default': 35.0},
    {'name': 'preMinVolRise', 'values': list(VOL_RISES), 'kind': 'ordinal', 'side': 'signal', 'default': 1.0},
    {'name': 'preCloseLocation', 'values': list(CLOSE_LOCS), 'kind': 'ordinal', 'side': 'signal', 'default': 0.65},
    {'name': 'preUseTrend', 'values': list(USE_TRENDS), 'kind': 'categorical', 'side': 'signal', 'default': True},
    {'name': 'fgfOn', 'values': list(FILTERS), 'kind': 'categorical', 'side': 'signal', 'default': False},
    {'name': 'preCandleEntryMode', 'values': list(ENTRY_MODES), 'kind': 'categorical', 'side': 'exit',
     'default': MODE_MARKET},
    {'name': 'inv', 'values': list(INVS), 'kind': 'categorical', 'side': 'exit', 'default': False},
    {'name': 'slAtrMult', 'values': list(SL_MULTS), 'kind': 'ordinal', 'side': 'exit', 'default': 1.0},
    {'name': 'exitStyle', 'values': list(STYLES), 'kind': 'categorical', 'side': 'exit', 'default': 'tp5'},
    {'name': 'useDailyLossLock', 'values': list(LOCKS), 'kind': 'categorical', 'side': 'exit', 'default': True},
]
DIM_NAMES = [d['name'] for d in DIMS]
SIGNAL_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'signal')
EXIT_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'exit')
DIM_DOC = {
    'emaPair': 'Fast EMA / Slow EMA of the EMA-cross signals (the fast one also the radar EMA slope, off here)',
    'trendFilterLen': 'Trend Filter EMA (the EMA-cross signals; the arms when preUseTrend)',
    'preMinVolScore': 'Minimum Radar Vol Score of an arm (ATR(10) / ATR(30) rescaled to 0..100)',
    'preMinVolRise': 'Minimum Radar Vol Rise of an arm (vol score against the previous candle)',
    'preCloseLocation': 'Close Location Pressure: where in its range the arm candle must close',
    'preUseTrend': 'Use Trend Direction: an arm needs the close on the right side of the trend EMA',
    'fgfOn': 'direction filter: Enable filter',
    'preCandleEntryMode': 'Pre-Candle Entry Mode: market order at the next open / stop order beyond the candle',
    'inv': 'Inverted direction: opposite side at the same entries (Update 1, gvInv)',
    'slAtrMult': 'Stop loss, ATR(14) multiples',
    'exitStyle': 'tp5 = 5 R target; time4 = no target, 4-bar time stop; trail = no target, trailing stop with the '
                 "cell's (trailActAtr, trailDstAtr) pair",
    'useDailyLossLock': 'Use Daily Loss Lock (3 losing trades per New York day)',
}
_DIM_TYPE = {'emaPair': str, 'trendFilterLen': int, 'preMinVolScore': float, 'preMinVolRise': float,
             'preCloseLocation': float, 'preUseTrend': bool, 'fgfOn': bool, 'preCandleEntryMode': str, 'inv': bool,
             'slAtrMult': float, 'exitStyle': str, 'useDailyLossLock': bool}
_PA_TYPE = {str: pa.string(), int: pa.int64(), float: pa.float64(), bool: pa.bool_()}
# the Pine inputs that the two composite dimensions set, written as columns that are not dimensions
INPUT_COLS = (('fastEmaLen', int), ('slowEmaLen', int), ('tpR', float), ('maxBarsHeld', int), ('useTrail', bool),
              ('trailActAtr', float), ('trailDstAtr', float))
INPUT_NAMES = tuple(k for k, _ in INPUT_COLS)

# The default setting: the script's default inputs (gvl.DEFAULTS; the Pine's input defaults) WITH the
# grid's scale-free sizing (maxQty 1e9, qtyStep 0.000001).
DEFAULT_P = {d['name']: d['default'] for d in DIMS}
DEFAULT = DEFAULT_P

# SIGNAL settings: the parameters of gvl.prepare. fgfOn is the innermost loop.
SIGNALS = [{'emaPair': ep, 'trendFilterLen': tl, 'preMinVolScore': vs, 'preMinVolRise': vr, 'preCloseLocation': cl,
            'preUseTrend': ut, 'fgfOn': f}
           for ep in EMA_PAIRS for tl in TREND_LENS for vs in VOL_SCORES for vr in VOL_RISES for cl in CLOSE_LOCS
           for ut in USE_TRENDS for f in FILTERS]
# EXIT settings: the parameters of gvl.simulate.
EXITS = [{'preCandleEntryMode': m, 'inv': i, 'slAtrMult': s, 'exitStyle': es, 'useDailyLossLock': lk}
         for m in ENTRY_MODES for i in INVS for s in SL_MULTS for es in STYLES for lk in LOCKS]
N_GRID = len(SIGNALS) * len(EXITS)                        # 20,736


def signals(pair=None, tf=None):
    """The SIGNAL settings of a cell (the same in every cell)."""
    return SIGNALS


def exits_for(sig=None, pair=None, tf=None):
    """The EXIT settings of one SIGNAL setting of a cell (the same 72 for every one)."""
    return EXITS


def merge(sig, x):
    """One grid setting: every dimension of DIMS, in DIMS order."""
    d = dict(sig)
    d.update(x)
    return {k: d[k] for k in DIM_NAMES}


def grid(pair=None, tf=None, sig_idx=None):
    """Every setting of a cell, in file order: for each SIGNAL setting, its EXIT settings."""
    idx = range(len(SIGNALS)) if sig_idx is None else sig_idx
    return [merge(SIGNALS[si], x) for si in idx for x in EXITS]


def n_settings(pair=None, tf=None):
    return N_GRID


def key(p):
    return tuple(p[k] for k in DIM_NAMES)


def ema_pair(v):
    """'fast/slow' -> (fastEmaLen, slowEmaLen)."""
    parts = str(v).split('/')
    if len(parts) != 2 or not all(q.strip().isdigit() for q in parts):
        raise ValueError('emaPair: %r is not "fastEmaLen/slowEmaLen"' % (v,))
    return int(parts[0]), int(parts[1])


def trail_pair(pair, tf):
    """(trailActAtr, trailDstAtr) of the cell = (2d, d)."""
    d = TRAIL_D.get((pair, str(tf)), 1.0)
    return 2.0 * d, d


def signal_params(sig):
    """A SIGNAL setting as gvl.prepare params (everything else at the script's defaults)."""
    f, s = ema_pair(sig['emaPair'])
    return {'fastEmaLen': f, 'slowEmaLen': s, 'trendFilterLen': int(sig['trendFilterLen']),
            'preMinVolScore': float(sig['preMinVolScore']), 'preMinVolRise': float(sig['preMinVolRise']),
            'preCloseLocation': float(sig['preCloseLocation']), 'preUseTrend': bool(sig['preUseTrend']),
            'fgfOn': bool(sig['fgfOn'])}


def exit_params(x, pair, tf, path=PATH, cost=COST, script_sizing=False):
    """An EXIT setting as gvl.simulate params: the swept inputs, the three inputs of its exit style
    (and, with the trailing stop, the cell's pair), and the fixed controls, always given: the two
    sizing inputs and tvMargin."""
    X = {'preCandleEntryMode': str(x['preCandleEntryMode']), 'gvInv': bool(x['inv']),
         'slAtrMult': float(x['slAtrMult']), 'useDailyLossLock': bool(x['useDailyLossLock']),
         'tvMargin': TV_MARGIN, 'path': path, 'cost': cost}
    X.update(EXIT_STYLES[x['exitStyle']])
    if X['useTrail']:
        X['trailActAtr'], X['trailDstAtr'] = trail_pair(pair, tf)
    X.update(SCRIPT_SIZING if script_sizing else SCALE_FREE)
    return X


def inputs_of(p, pair, tf):
    """The Pine inputs that emaPair and exitStyle set for a setting (the columns INPUT_NAMES);
    trailActAtr / trailDstAtr: the cell's pair with the trailing stop, None without it."""
    f, s = ema_pair(p['emaPair'])
    st = EXIT_STYLES[p['exitStyle']]
    act, dst = trail_pair(pair, tf) if st['useTrail'] else (None, None)
    return {'fastEmaLen': f, 'slowEmaLen': s, 'tpR': st['tpR'], 'maxBarsHeld': st['maxBarsHeld'],
            'useTrail': st['useTrail'], 'trailActAtr': act, 'trailDstAtr': dst}


def normalize(raw, off_grid=False):
    """A setting given as a mapping of p_ values (keys with or without 'p_') -> the canonical dict
    over DIM_NAMES. Raises ValueError for an unknown key, a dimension without a value (None / NaN /
    missing: no dimension of this grid is ever unused), a value of the wrong type, or (unless
    off_grid) a value that is not in the grid. off_grid accepts other numbers, any "fast/slow" EMA
    pair and the third entry mode of the Pine ("Signal Only"); exitStyle is always one of the three."""
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
                raise ValueError('%s: %r is not a text value' % (name, v))
            if name == 'emaPair':
                v = '%d/%d' % ema_pair(v)
        if v not in d['values']:
            free = off_grid and (ty in (int, float) or name == 'emaPair'
                                 or (name == 'preCandleEntryMode' and v in gvl._OPTIONS['preCandleEntryMode']))
            if not free:
                raise ValueError('%s: %r is not in the grid %r' % (name, v, d['values']))
        out[name] = v
    return out


_ROWS: dict = {}


def row_of(pair, tf, p):
    """The row number of a setting in a cell's grid file (grid() order; the same in every cell),
    None when it is not a grid row."""
    if not _ROWS:
        _ROWS.update({key(q): i for i, q in enumerate(grid())})
    return _ROWS.get(key(p))


def in_grid(pair, tf, p):
    return row_of(pair, tf, p) is not None


# ---------------------------------------------------------------------------------------------
# what a run must echo; the floor of the trailing distance
# ---------------------------------------------------------------------------------------------
def _check_prepared(sp, Pp, pair, tf):
    """gvl.prepare ran the SIGNAL setting it was asked for, and nothing else: its resolved
    parameters are the script's defaults with the given values; the radar is the chart."""
    want = dict(gvl.DEFAULTS)
    want.update(sp)
    if Pp['params'] != want or Pp['pair'] != pair or Pp['tf'] != str(tf) or Pp['use_radar'] \
            or (Pp['start'], Pp['end']) != tuple(gvl.WINDOWS[pair]):
        diff = {k: (Pp['params'].get(k), want.get(k)) for k in set(want) | set(Pp['params'])
                if Pp['params'].get(k) != want.get(k)}
        raise RuntimeError('gvl.prepare did not run the signal setting %r: %r' % (sp, diff))


def _check_run(X, Pp, R):
    """gvl.simulate ran the EXIT setting it was asked for, and nothing else: its effective inputs
    (R['x']) are the prepared ones with every value given (inv = gvInv)."""
    want = dict(Pp['params'])
    want.update(X)
    want['inv'] = want['gvInv']
    if R['x'] != want or R['inv'] is not X['gvInv'] or R['path'] != X['path']:
        diff = {k: (R['x'].get(k), want.get(k)) for k in set(want) | set(R['x']) if R['x'].get(k) != want.get(k)}
        raise RuntimeError('gvl.simulate did not run %r: %r' % (X, diff))


def cell_floor(pair, tf, Pp):
    """The trailing distance of the cell against the 1-minute noise floor: the 10th percentile over
    the window of ATR(14) / close (%), times trailDstAtr, must be at least FLOOR_PCT[pair]."""
    atr = gvl.exit_atr(Pp, ATR_LEN)
    p10 = float(np.nanpercentile(atr / Pp['close'] * 100.0, 10))
    act, dst = trail_pair(pair, tf)
    return {'atr_len': ATR_LEN, 'p10_atr_pct': p10, 'trailActAtr': act, 'trailDstAtr': dst,
            'dist_pct_at_p10': dst * p10, 'floor_pct': FLOOR_PCT[pair], 'floor_ok': bool(dst * p10 >= FLOOR_PCT[pair])}


def floor_ok(p, floor):
    """floor_ok of one setting: True without a trailing stop, else the cell's measurement."""
    return bool((not EXIT_STYLES[p['exitStyle']]['useTrail']) or floor['floor_ok'])


# ---------------------------------------------------------------------------------------------
# one setting
# ---------------------------------------------------------------------------------------------
def one(pair, tf, p, path=PATH, cost=COST, off_grid=False, script_sizing=False, cache=None):
    """The full summary (gvl.summary) of one setting, computed alone: its own gvl.prepare and one
    gvl.simulate. p: a mapping of p_ values (see normalize). script_sizing: the file's own maxQty
    and qtyStep (not a grid dimension). cache: a dict that keeps the prepared inputs between calls
    of one process (tests)."""
    tf = str(tf)
    p = normalize(p, off_grid)
    sig = {k: p[k] for k in SIGNAL_DIMS}
    x = {k: p[k] for k in EXIT_DIMS}
    sp = signal_params(sig)
    ck = (pair, tf, tuple(sorted(sp.items())))
    Pp = cache.get(ck) if cache is not None else None
    if Pp is None:
        Pp = gvl.prepare(pair, tf, sp)
        if cache is not None:
            cache[ck] = Pp
    _check_prepared(sp, Pp, pair, tf)
    X = exit_params(x, pair, tf, path, cost, script_sizing)
    R = gvl.simulate(Pp, X)
    _check_run(X, Pp, R)
    s = gvl.summary(Pp, R)
    out = dict(inputs_of(p, pair, tf))
    out['floor_ok'] = floor_ok(p, cell_floor(pair, tf, Pp))
    out.update(s)
    row = row_of(pair, tf, p)
    out['setting'] = {'strategy': STRATEGY, 'pair': pair, 'tf': tf, 'path': path, 'cost': cost, 'p': p,
                      'in_grid': row is not None, 'row': row,
                      'sizing': 'script' if script_sizing else 'scale-free',
                      'maxQty': R['x']['maxQty'], 'qtyStep': R['x']['qtyStep'], 'tvMargin': R['x']['tvMargin'],
                      'cell_trail': list(trail_pair(pair, tf))}
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
# arrays of a prepared input; equal ones are kept once per cell
_ARRAYS = ('rows', 'open', 'high', 'low', 'close', 't_open', 't_close', 'armL', 'armS', 'sigL', 'sigS', 'buyOk',
           'sellOk', 'gate', 'flatOk', 'win', 'day', 'atr14')


def _slim(Pp, pool):
    """Replace every array of a prepared input that equals one already seen in this cell by that
    one (the bars, the clocks, the permissions of the same filter state, arms / signals shared
    between signal settings), and every view into a larger array (the bar files, the full-length
    ATR) by a copy of the window, so that the module caches can be dropped."""
    by_ptr = pool.setdefault('ptr', {})
    by_hash = pool.setdefault('hash', {})
    for k in _ARRAYS:
        a = Pp[k]
        if a.ndim != 1:
            raise TypeError('prepared array %r is not one-dimensional' % k)
        pk = (k, a.__array_interface__['data'][0], a.shape, a.strides, a.dtype.str)
        hit = by_ptr.get(pk)
        if hit is not None:                      # the memory of an array seen before, which is still alive
            Pp[k] = hit[1]
            continue
        c = np.ascontiguousarray(a)
        hk = (k, a.shape, a.dtype.str, bool(a.flags.writeable),
              hashlib.blake2b(c.view(np.uint8).data, digest_size=16).digest())
        b = by_hash.get(hk)
        if b is not None and np.array_equal(a, b, equal_nan=a.dtype.kind == 'f'):
            Pp[k] = b                            # a duplicate: not remembered by address (it is freed now)
            continue
        b = c
        if a.base is not None:
            b = c.copy()
            b.setflags(write=bool(a.flags.writeable))        # same array type for the kernel as the module's own
        by_hash[hk] = b
        by_ptr[pk] = (a, b)                      # keeps `a` alive: its address cannot be reused while the pool lives
        Pp[k] = b
    Pp['atr_cache'] = {ATR_LEN: Pp['atr14']}


def _distinct(P):
    """Number of distinct arrays kept for the prepared inputs of a cell, per name."""
    return {k: len(set(id(Pk[k]) for Pk in P.values())) for k in _ARRAYS}


def _release_memory():
    """Hand freed memory back to the system: pyarrow's pool keeps the buffers of the bar files it
    read and glibc keeps freed heap pages (on a 1-minute chart about 1.1 GB together)."""
    gc.collect()
    try:
        pa.default_memory_pool().release_unused()
    except Exception:       # noqa: BLE001  (a hint only)
        pass
    try:
        import ctypes
        ctypes.CDLL('libc.so.6').malloc_trim(0)
    except Exception:       # noqa: BLE001  (not glibc)
        pass


def _free_filter():
    """The filter's own series (the prepared inputs / gvl's permission cache hold the results)."""
    fgf = sys.modules.get('fgf')
    for name in ('_BARS', '_DIR', '_FILTER'):
        c = getattr(fgf, name, None) if fgf is not None else None
        if isinstance(c, dict):
            c.clear()
    _release_memory()


def _free_caches():
    """Every module cache: the bar files, the series, the window slices, the permissions, the
    sub-bar tables (slimmed prepared inputs hold their own arrays), and the filter's."""
    gvl.clear_cache()
    _free_filter()


def _prime_filter(pair, tf, sp):
    """The filter permissions of the cell, computed before anything else is in memory (on a
    1-minute chart the filter needs about 1.3 GB while it runs), then its series are dropped.
    gvl.prepare finds the result in the module's cache: the filter runs once per cell."""
    Q = gvl._params(sp)
    s0, e0 = gvl.WINDOWS[pair]
    gvl.permissions(pair, str(tf), s0, e0, {k: Q[k] for k in gvl.FGF_DEFAULTS})
    _free_filter()


def prepare_cell(pair, tf, sig_idx=None, verbose=False):
    """gvl.prepare once per SIGNAL setting of the cell (all, or those of sig_idx), the 1-minute
    sub-bars once, the floor of the trailing distance, the kernel compiled. Returns the cell:
    P {signal index: prepared input}, the summary columns and timings."""
    tf = str(tf)
    S = SIGNALS
    idx = list(range(len(S))) if sig_idx is None else [int(i) for i in sig_idx]
    t0 = time.time()
    c0 = time.process_time()
    on = [si for si in idx if S[si]['fgfOn']]
    if on:
        _prime_filter(pair, tf, signal_params(S[on[0]]))
    t_fgf = time.time() - t0
    P = {}
    pool = {}
    for si in idx:
        sp = signal_params(S[si])
        Pp = gvl.prepare(pair, tf, sp)
        _check_prepared(sp, Pp, pair, tf)
        _slim(Pp, pool)
        P[si] = Pp
    del pool
    p0 = P[idx[0]]
    for si, Pk in P.items():
        if (Pk['w0'], Pk['w1'], Pk['mid'], Pk['mid_j'], Pk['n']) != (p0['w0'], p0['w1'], p0['mid'], p0['mid_j'], p0['n']):
            raise ValueError('%s %s signal setting %d: window rows differ' % (pair, tf, si))
    t_sig = time.time() - t0
    t1 = time.time()
    n_sub = 0
    if PATH == 'mag':
        sub = gvl.get_sub(p0)                      # built once, checked against the chart bars
        n_sub = len(sub[1])
        for Pk in P.values():
            Pk['sub'] = sub
    floor = cell_floor(pair, tf, p0)
    _free_caches()
    t_sub = time.time() - t1
    t2 = time.time()
    X0 = exit_params(EXITS[0], pair, tf)
    R0 = gvl.simulate(p0, X0)                      # compile / load the kernel
    _check_run(X0, p0, R0)
    s = gvl.summary(p0, R0)
    t_jit = time.time() - t2
    cols = list(s.keys())
    kinds = {}
    for k, v in s.items():
        if isinstance(v, (bool, np.bool_)):
            kinds[k] = bool
        elif isinstance(v, (int, np.integer)):
            kinds[k] = int
        elif isinstance(v, (float, np.floating)):
            kinds[k] = float
        else:
            raise TypeError('gvl.summary field %r is not a scalar: %r' % (k, v))
    _release_memory()
    cell = dict(pair=pair, tf=tf, idx=idx, S=S, P=P, cols=cols, kinds=kinds, bars=int(p0['n']), n_sub=n_sub,
                floor=floor, prepares=len(idx), t_fgf=t_fgf, t_sig=t_sig, t_sub=t_sub, t_jit=t_jit,
                t_prep=time.time() - t0, cpu_prep=time.process_time() - c0)
    if verbose:
        print('  %s %s: %d chart bars, %d 1-minute bars; %d signal settings prepared in %.1fs (of which the filter '
              '%.1fs), sub-bars %.1fs, kernel %.1fs'
              % (pair, tf, cell['bars'], n_sub, len(idx), t_sig, t_fgf, t_sub, t_jit), flush=True)
        print('  trailing pair (trailActAtr, trailDstAtr) = (%g, %g): %g x ATR(14)/close at the 10th percentile '
              '(%.4f %%) = %.4f %% of price, floor %.2f %%: floor_ok %s'
              % (floor['trailActAtr'], floor['trailDstAtr'], floor['trailDstAtr'], floor['p10_atr_pct'],
                 floor['dist_pct_at_p10'], floor['floor_pct'], floor['floor_ok']), flush=True)
    return cell


def _work(task):
    si, i0, i1 = task
    t0 = time.time()
    c0 = time.process_time()
    Pp = _G['P'][si]
    XP = _G['XP']
    cols = _G['cols']
    out = []
    for i in range(i0, i1):
        R = gvl.simulate(Pp, XP[i])
        _check_run(XP[i], Pp, R)
        s = gvl.summary(Pp, R)
        out.append(tuple(s[k] for k in cols))
    return si, i0, out, time.time() - t0, time.process_time() - c0


def run_prepared(cell, workers=MAX_WORKERS, sig_idx=None, chunk=CHUNK, verbose=False):
    """Simulate every exit setting of the prepared signal settings (all of the cell, or sig_idx).
    Returns (res {signal index: [summary tuple per exit setting]}, info)."""
    pair, tf = cell['pair'], cell['tf']
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    XP = [exit_params(x, pair, tf) for x in EXITS]
    _G.clear()
    _G.update(P=cell['P'], XP=XP, cols=cell['cols'])
    tasks = [(si, i0, min(i0 + chunk, len(XP))) for si in idx for i0 in range(0, len(XP), chunk)]
    total = sum(t[2] - t[1] for t in tasks)
    res = {si: [None] * len(XP) for si in idx}
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
    """The rows in grid order as an arrow table: p_<name> per dimension, the Pine inputs of the
    composite dimensions, floor_ok, then every summary field. Column types are fixed here (they do
    not depend on the values)."""
    pair, tf = cell['pair'], cell['tf']
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    G = grid(pair, tf, idx)
    vals = [r for si in idx for r in res[si]]
    if len(G) != len(vals):
        raise RuntimeError('grid and results differ in length')
    names, arrays = [], []
    for name in DIM_NAMES:
        names.append('p_' + name)
        arrays.append(pa.array([p[name] for p in G], type=_PA_TYPE[_DIM_TYPE[name]]))
    ins = [inputs_of(p, pair, tf) for p in G]
    for name, ty in INPUT_COLS:
        names.append(name)
        arrays.append(pa.array([q[name] for q in ins], type=_PA_TYPE[ty]))       # None -> null
    names.append('floor_ok')
    arrays.append(pa.array([floor_ok(p, cell['floor']) for p in G], type=pa.bool_()))
    for j, k in enumerate(cell['cols']):
        ty = cell['kinds'][k]
        col = [v[j] for v in vals]
        if k in names:
            raise RuntimeError('summary field %r collides with a column' % k)
        names.append(k)
        if ty is float:
            arrays.append(pa.array(np.asarray(col, dtype=np.float64), type=pa.float64()))     # NaN stays NaN, not null
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


def file_meta(pair, tf, n, floor=None):
    """What produced a cell's file (stored in the parquet's key-value metadata, key "calib")."""
    act, dst = trail_pair(pair, tf)
    return {'strategy': STRATEGY, 'pair': pair, 'tf': str(tf), 'path': PATH, 'cost': COST, 'settings': int(n),
            'window': [int(v) for v in gvl.WINDOWS[pair]], 'maxQty': SCALE_FREE['maxQty'],
            'qtyStep': SCALE_FREE['qtyStep'], 'tvMargin': TV_MARGIN, 'trailActAtr': act, 'trailDstAtr': dst,
            'exit_styles': EXIT_STYLES, 'floor': floor,
            'gvl_sha256': _sha256(os.path.join(W, 'gvl.py')), 'fgf_sha256': _sha256(os.path.join(W, 'fgf.py'))}


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
                t_fgf=cell['t_fgf'], t_sig=cell['t_sig'], t_sub=cell['t_sub'], t_jit=cell['t_jit'],
                prepares=cell['prepares'], floor=cell['floor'], distinct=_distinct(cell['P']), file=None)
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
    info['rows_zero_qty'] = int((df['zero_qty'] > 0).sum())
    info['rows_30_trades_each_half'] = int(((df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).sum())
    info['rows_floor_ok'] = int(df['floor_ok'].sum())
    if verbose:
        w = max(info['workers'], 1)
        print('  %s %s done: %d rows%s | prep %.1fs, runs %.1fs with %d workers (%.2f worker-s, %.5fs per '
              'setting per worker, of which CPU %.5fs; workers busy %.0f%%), total %.1fs; load average %.2f'
              % (pair, tf, len(df), (' -> ' + info['file']) if info['file'] else ' (not written)', info['t_prep'],
                 info['t_run'], w, info['busy'], info['busy'] / max(info['settings'], 1),
                 info['cpu'] / max(info['settings'], 1), 100.0 * info['busy'] / max(info['t_run'] * w, 1e-9),
                 info['t_total'], os.getloadavg()[0]), flush=True)
        print('  rows with floor_ok: %d of %d; rows with a quantity floored to zero (zero_qty > 0: an account too '
              'small for the 0.000001 step): %d; rows with at least 30 trades in each half: %d'
              % (info['rows_floor_ok'], len(df), info['rows_zero_qty'], info['rows_30_trades_each_half']), flush=True)
    _G.clear()
    return df, info


def estimate_cell(pair, tf, workers=MAX_WORKERS, per_signal=2, seed=20261126, verbose=True):
    """Estimated time of the full cell from ONE process: the real preparation, then per_signal random
    exit settings of every signal setting timed one by one; run time = sum over the signal settings
    of (mean sampled time x its number of exit settings) / workers. Two estimates: from the wall
    clock (the machine as loaded as it is now) and from this process' CPU time (the 3 workers
    each having a free CPU). Writes nothing."""
    tf = str(tf)
    cell = prepare_cell(pair, tf, None, verbose)
    rng = np.random.default_rng(seed)
    XP = [exit_params(x, pair, tf) for x in EXITS]
    t_single = 0.0
    c_single = 0.0
    worst = 0.0
    n_s = 0
    n_zero = 0
    n_thin = 0
    t0 = time.time()
    for si in cell['idx']:
        Pp = cell['P'][si]
        tt = []
        cc = []
        for i in rng.choice(len(XP), size=min(per_signal, len(XP)), replace=False):
            t = time.time()
            c = time.process_time()
            R = gvl.simulate(Pp, XP[int(i)])
            _check_run(XP[int(i)], Pp, R)
            sm = gvl.summary(Pp, R)
            tt.append(time.time() - t)
            cc.append(time.process_time() - c)
            n_zero += sm['zero_qty'] > 0
            n_thin += sm['h1_trades'] < 30 or sm['h2_trades'] < 30
        t_single += float(np.mean(tt)) * len(XP)
        c_single += float(np.mean(cc)) * len(XP)
        worst = max(worst, max(tt))
        n_s += len(tt)
    n_all = N_GRID
    w = max(workers, 1)
    est = dict(pair=pair, tf=tf, bars=cell['bars'], n_sub=cell['n_sub'], settings=n_all, sampled=n_s,
               t_prep=cell['t_prep'], per_setting=t_single / n_all, slowest=worst, single_process_run=t_single,
               workers=workers, est_run=t_single / w, est_total=cell['t_prep'] + t_single / w,
               cpu_prep=cell['cpu_prep'], cpu_per_setting=c_single / n_all,
               est_total_free_cpus=cell['cpu_prep'] + c_single / w,
               sampled_zero_qty=int(n_zero), sampled_under_30_trades_in_a_half=int(n_thin),
               t_sample=time.time() - t0, load1=os.getloadavg()[0])
    if verbose:
        print('  %s %s estimate: prep %.1fs + %d settings x %.5fs (slowest sampled %.4fs; %d sampled) / %d workers '
              '= %.1fs runs -> %.1fs total (%.2f min) at the present load (load average %.2f); by CPU time: prep '
              '%.1fs + %d x %.5fs / %d -> %.1fs (%.2f min) with a free CPU per worker'
              % (pair, tf, est['t_prep'], n_all, est['per_setting'], worst, n_s, workers, est['est_run'],
                 est['est_total'], est['est_total'] / 60.0, est['load1'], est['cpu_prep'], n_all,
                 est['cpu_per_setting'], workers, est['est_total_free_cpus'], est['est_total_free_cpus'] / 60.0),
              flush=True)
        print('  of the %d sampled settings: %d with a quantity floored to zero (zero_qty > 0), %d with fewer than '
              '30 trades in a half' % (n_s, n_zero, n_thin), flush=True)
    return est


# ---------------------------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------------------------
def _main_one(argv):
    ap = argparse.ArgumentParser(prog='calib_gvl.py --one', description='the full summary of one setting, as JSON')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tf', choices=TFS)
    ap.add_argument('p', help='JSON object of the p_ values of the setting')
    ap.add_argument('--path', choices=('tv', 'mag'), default=PATH)
    ap.add_argument('--cost', choices=tuple(gvl.COSTS), default=COST)
    ap.add_argument('--script-sizing', action='store_true',
                    help="the file's own maxQty 50 and qtyStep 0.001 instead of the grid's scale-free sizing")
    ap.add_argument('--off-grid', action='store_true', help='accept values that are not in the grid')
    a = ap.parse_args(argv)
    try:
        raw = json.loads(a.p)
        if not isinstance(raw, dict):
            raise ValueError('the p_ values must be a JSON object')
        out = one(a.pair, a.tf, raw, a.path, a.cost, a.off_grid, a.script_sizing)
    except ValueError as e:
        print('calib_gvl.py --one: %s' % e, file=sys.stderr)
        return 2
    print(json.dumps(out, default=_json_default))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--one' in argv:
        argv.remove('--one')
        return _main_one(argv)
    ap = argparse.ArgumentParser(description='GVLiveV2 Polymarket Pre-Candle + FGF calibration grid (CALIB_SPEC.md)')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tfs', nargs='+')
    ap.add_argument('--workers', type=int, default=MAX_WORKERS)
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--estimate', action='store_true', help='time a sample in one process; write nothing')
    ap.add_argument('--per-signal', type=int, default=2, help='--estimate: sampled exit settings per signal setting')
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
            print('== calib %s %s %s: %d settings (%d signal settings x %d exit settings), path %s, cost %s, '
                  'maxQty %g, qtyStep %g, tvMargin %g =='
                  % (STRATEGY, a.pair, tf, N_GRID, len(SIGNALS), len(EXITS), PATH, COST, SCALE_FREE['maxQty'],
                     SCALE_FREE['qtyStep'], TV_MARGIN), flush=True)
            run_cell(a.pair, tf, workers, a.out_dir)
        _free_caches()
    print('all done in %.1fs' % (time.time() - t0), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
