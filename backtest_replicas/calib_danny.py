"""calib_danny.py: calibration grid of Danny Phantom FX V10.21.1 LiveSafe + FGF [Update 1] per pair
and timeframe, with the direction (Normal / Inverted, Update 1) as a calibrated input
(CALIB_SPEC.md, strategy "danny"; the grid is section 14 of SPEC_danny.md), on the canonical
replica danny.py (prepare / simulate / summary).

Usage (python3 -I)
  calib_danny.py PAIR TF [TF ...] [--workers 3] [--out-dir DIR]
      runs the full grid of every (PAIR, TF) cell and writes out/calib_danny_<PAIR>_<TF>.parquet
      (one row per setting) and out/calib_danny_dims.json (DIMS). PAIR in BTC, XAU; TF in 1, 5,
      15, 30, 60, 120, 240. Safe to re-run: the files are overwritten (written to a temporary
      name first). Prints the timing of every cell.
  calib_danny.py --one PAIR TF '<json of p_ values>' [--path tv|mag] [--cost tv|ours|stress]
                 [--var-rollback true|false] [--script-sizing] [--off-grid]
      prints the full summary of ONE setting as one JSON document on stdout (default path mag,
      cost ours = the sweep's scoring). The JSON of p_ values is a row's p_ columns: keys with or
      without the "p_" prefix, null (or NaN) for an unused dimension. Two controls that are NOT
      grid dimensions (every grid row has varRollback True and the scale-free sizing):
        --var-rollback false  the "as written" reading (danny varRollback False: one run per
                              candle, no rollback of the `var` variables). Nothing else changes:
                              useOnePerZone / useCooldown / cooldownIn stay at the script's
                              defaults (True / True / 10), and now they act.
        --script-sizing       the file's own sizing: qtyStepS3 0.001 and maxQtyS3 50 instead of
                              the grid's 0.000001 and 1e9.
      --off-grid also accepts numbers that are not in the grid, and signalDirection with the
      filter off.
  calib_danny.py --estimate PAIR TF [TF ...] [--workers 3] [--per-signal 6]
      times the cell's preparation and a random sample of settings in ONE process and prints the
      estimated time of the full cell; writes nothing.

The grid: 17,496 settings per cell = 27 signal inputs x 6 (filter x direction) x 108 exits
  signals   manualZoneLength {50, 100, 200} x manualDeltaThreshold {1.0, 1.5, 2.0}
            x [manualUseEmaFilter True x manualEmaLength {100, 200} | manualUseEmaFilter False
               (manualEmaLength unused: None)]
  filter    fgfOn {False, True}. This script has no blocked-signal close.
  direction fgfOn True:  signalDirection {"Inverted (V10 design)", "Original (un-inverted)"} (the
                         OLDER option: flips the zone signals before the filter) x inv {False,
                         True} (dpInv, Update 1 "Inverted direction": flips the order after the
                         gate)
            fgfOn False: signalDirection None x inv {False, True}. None = the script's default
                         value is used. With the filter off, inv True IS the Original signal
                         direction (property P1 of the Pine header: same trades), so the pair
                         would only repeat rows.
  exits     slAtrMultS2 {0.8, 1.2, 2.0} x tpRS2 {4.1667, 0.0 = no target} x timeStopBars {25, 50,
            100} x [useDeadExit True x deadBarsIn {15, 30} | useDeadExit False (deadBarsIn
            unused: None)] x useTrailS2 {False, True}
  trailing  useTrailS2 True = ExitMode ATR with ONE pair per cell, the table of SPEC_danny.md
            section 14: (trailActAtr, trailDstAtr) = (2d, d), d the smallest of {1, 1.75, 2.5,
            3.5, 5, 6.5} for which d x ATR(14) / close at the 10th percentile of the window is at
            least the 1-minute noise floor (BTC 0.1 %, XAU 0.05 %):
                BTC 1 (13, 6.5) | BTC 5 (3.5, 1.75) | BTC 15 .. 240 (2, 1)
                XAU 1 (10, 5)   | XAU 5 (3.5, 1.75) | XAU 15 .. 240 (2, 1)
            The pair is not a dimension (one value per cell); it is in the file's metadata and in
            the "setting" of --one. Column floor_ok: True when the trailing is off, else whether
            the cell's distance meets the floor (measured again on the data at every run; True in
            all 14 cells).
  preset    presetMode "Auto" (the script default) on 13 cells: no preset matches there, "Auto"
            and "Manual" cannot differ, so it is listed once. XAU "5": Auto IS the XAUUSD 5m
            preset (another rule set, which takes no trade on a 0.01-tick gold symbol), so the
            17,496 rows run with presetMode "Manual" and ONE extra row, the last (17,497 rows),
            is the script default there (presetMode "Auto", every other dimension at its
            default).
Fixed for EVERY row (decisions of the orchestrator, not dimensions):
  varRollback True      (assumption E2 of SPEC_danny.md; under it useOnePerZone / useCooldown /
                        cooldownIn are inert unless a quantity floors to zero, so they stay at
                        the script defaults);
  scale-free sizing     qtyStepS3 = 0.000001 and maxQtyS3 = 1e9 (the file's own are 0.001 and
                        50), so that neither a ruined account nor the quantity grain decides a
                        result. Everything else of the sizing is the script's: Risk 1 % of equity,
                        margin cap 1 %, capital 2,000.
                        Limit: 0.000001 is the smallest step the Pine input accepts. An account
                        that has lost about 99.99999 % of its capital (equity x 1 % / stop
                        distance < 0.000001: on the 1-minute charts, where a round trip costs
                        about one stop distance) can still not size a trade and stops trading.
                        Such a row has zero_qty > 0 (a column); the run prints how many there are.
Everything else stays at the script's defaults (ExitMode ATR, ATR 14, loss-cluster pause on,
blackouts on, breakeven off, the filter's own inputs).
DEFAULT_P (= DEFAULT) is the default setting: the script's default inputs WITH the scale-free
sizing above (qtyStepS3 0.000001, maxQtyS3 1e9) and varRollback True. It is NOT literally the
published file's default result: that one is `--one ... --script-sizing` on DEFAULT_P. It is one
row of every cell (on XAU "5": the extra row).

SIGNALS (54; on XAU "5" signals(pair, tf) = the same 54 with "Manual" + the extra one) are the
parameters of danny.prepare (signal inputs + fgfOn); EXITS (648) those of danny.simulate;
exits_for(signal, pair, tf) = the EXITS of a signal setting (216 with the filter off, 432 with it
on). A dimension that cannot change the result is listed once with the value None:
manualEmaLength with manualUseEmaFilter False, deadBarsIn with useDeadExit False; and
signalDirection with fgfOn False (see above). DIMS = the 14 dimensions (name, values, kind
'ordinal' / 'categorical'; extra keys: side, default, unused_when); row i of a file is
grid(pair, tf)[i].

Every setting is scored with path 'mag' (the exit bracket walked along the 1-minute sub-bars; on
chart "1" each bar is its own sub-bar) and cost 'ours'. Per cell: danny.prepare runs ONCE per
signal setting (54 times; the filter permissions are computed once, by the module's cache), the
prepared inputs are slimmed (the diagnostic arrays are dropped, arrays that are equal between
signal settings are kept once), the 1-minute sub-bars and ATR(14) are built once, the kernel is
compiled, and only then at most 3 workers are forked (copy-on-write); each simulates chunks of
exit settings of one prepared input (danny.simulate + danny.summary) and checks that the module
ran the setting it was asked to run. Rows are assembled in grid order, so the file does not
depend on the worker count.

Output columns: p_<name> for every dimension of DIMS, in DIMS order (null = None), floor_ok, then
every field of danny.summary in its own order: start, end, bars, trades, net_pct, pf, win_pct,
max_dd_pct, max_dd_init_pct, long, short (REAL sides), raw_long, raw_short, blocked_long,
blocked_short (the SIGNAL's side), half1_pct, half2_pct, exposure, final_equity, exit_<kind>
counts (sl, tp, trail, be, reverse, dead, time, blackout, end), zero_length, h1r_pct, h2r_pct,
h1_trades, h2_trades (the fair halves), avg_bars_held, costs, slippage_paid, net_r,
reentry_same_bar, reentry_leg1, inherited, zero_qty, qty_capped, margin_breach. Nothing else: no
index, no pair / tf column (they are in the file name; the parquet's key-value metadata "calib"
holds strategy, pair, tf, path, cost, the number of settings, the fixed controls, the trailing
pair and its floor measurement, and the sha256 of danny.py and fgf.py that produced the rows).
pf is +inf without a losing trade and NaN without trades; win_pct and avg_bars_held are NaN
without trades. --one prints floor_ok and the same fields (Python's json: Infinity / NaN) plus
"setting" = {strategy, pair, tf, path, cost, p (the canonical p_ values), in_grid, row (its row
number in the cell's grid file), varRollback, sizing, qtyStepS3, maxQtyS3, useOnePerZone,
useCooldown, cooldownIn (as the module resolved them), trailActAtr, trailDstAtr, preset}.
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
import danny  # noqa: E402

STRATEGY = 'danny'
MAX_WORKERS = 3
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
PATH = 'mag'             # the sweep's scoring: 1-minute fills ...
COST = 'ours'            # ... with our costs
CHUNK = 36               # exit settings per worker task

# ---------------------------------------------------------------------------------------------
# the grid (SPEC_danny.md section 14)
# ---------------------------------------------------------------------------------------------
SIG_INV = "Inverted (V10 design)"            # signalDirection, the script default
SIG_ORIG = "Original (un-inverted)"
ZONE_LENGTHS = (50, 100, 200)
DELTA_THRESHOLDS = (1.0, 1.5, 2.0)
EMAS = ((True, 100), (True, 200), (False, None))          # (manualUseEmaFilter, manualEmaLength)
EMA_LENGTHS = (100, 200)
FILTERS = (False, True)
SIGNAL_DIRECTIONS = (SIG_INV, SIG_ORIG)
INVS = (False, True)
SL_MULTS = (0.8, 1.2, 2.0)
TP_RS = (4.1667, 0.0)                                     # 0 = no target
TIME_STOPS = (25, 50, 100)
DEADS = ((True, 15), (True, 30), (False, None))           # (useDeadExit, deadBarsIn)
DEAD_BARS = (15, 30)
TRAILS = (False, True)

# fixed for every row
VAR_ROLLBACK = True
SCALE_FREE = {'qtyStepS3': 0.000001, 'maxQtyS3': 1e9}     # the grid's sizing
SCRIPT_SIZING = {'qtyStepS3': 0.001, 'maxQtyS3': 50.0}    # the file's own (--one --script-sizing)

# the preset: Auto = the XAUUSD 5m preset on this cell only; its grid runs with Manual
PRESET_CELL = ('XAU', '5')
PRESET_MODES = ('Auto', 'Manual')

# trailing: one (trailActAtr, trailDstAtr) = (2d, d) per cell, the table of section 14
ATR_LEN = 14
TRAIL_LADDER = (1.0, 1.75, 2.5, 3.5, 5.0, 6.5)
FLOOR_PCT = {'BTC': 0.1, 'XAU': 0.05}                     # 1-minute noise floor, % of price
TRAIL_D = {('BTC', '1'): 6.5, ('BTC', '5'): 1.75, ('XAU', '1'): 5.0, ('XAU', '5'): 1.75}   # else 1.0

# name, values, kind as CALIB_SPEC.md asks; extra keys (as calib_hrd.py): side = 'signal' (a parameter
# of danny.prepare) or 'exit' (of danny.simulate), default = the script's default input, unused_when
# = the value of another dimension with which this one is listed once (its value is None)
DIMS = [
    {'name': 'presetMode', 'values': list(PRESET_MODES), 'kind': 'categorical', 'side': 'signal', 'default': 'Auto'},
    {'name': 'manualZoneLength', 'values': list(ZONE_LENGTHS), 'kind': 'ordinal', 'side': 'signal', 'default': 50},
    {'name': 'manualDeltaThreshold', 'values': list(DELTA_THRESHOLDS), 'kind': 'ordinal', 'side': 'signal',
     'default': 1.5},
    {'name': 'manualUseEmaFilter', 'values': [True, False], 'kind': 'categorical', 'side': 'signal', 'default': True},
    {'name': 'manualEmaLength', 'values': list(EMA_LENGTHS), 'kind': 'ordinal', 'side': 'signal', 'default': 100,
     'unused_when': {'manualUseEmaFilter': False}},
    {'name': 'fgfOn', 'values': list(FILTERS), 'kind': 'categorical', 'side': 'signal', 'default': True},
    {'name': 'signalDirection', 'values': list(SIGNAL_DIRECTIONS), 'kind': 'categorical', 'side': 'exit',
     'default': SIG_INV, 'unused_when': {'fgfOn': False}},
    {'name': 'inv', 'values': list(INVS), 'kind': 'categorical', 'side': 'exit', 'default': False},
    {'name': 'slAtrMultS2', 'values': list(SL_MULTS), 'kind': 'ordinal', 'side': 'exit', 'default': 1.2},
    {'name': 'tpRS2', 'values': list(TP_RS), 'kind': 'categorical', 'side': 'exit', 'default': 4.1667},   # 0 = no target
    {'name': 'timeStopBars', 'values': list(TIME_STOPS), 'kind': 'ordinal', 'side': 'exit', 'default': 50},
    {'name': 'useDeadExit', 'values': [True, False], 'kind': 'categorical', 'side': 'exit', 'default': True},
    {'name': 'deadBarsIn', 'values': list(DEAD_BARS), 'kind': 'ordinal', 'side': 'exit', 'default': 15,
     'unused_when': {'useDeadExit': False}},
    {'name': 'useTrailS2', 'values': list(TRAILS), 'kind': 'categorical', 'side': 'exit', 'default': False},
]
DIM_NAMES = [d['name'] for d in DIMS]
SIGNAL_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'signal')
EXIT_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'exit')
# a dimension is listed once (None) when another one has this value
UNUSED_WHEN = {d['name']: next(iter(d['unused_when'].items())) for d in DIMS if 'unused_when' in d}
DIM_DOC = {
    'presetMode': 'Preset Mode (Auto = the XAUUSD 5m preset on XAU "5" only; the grid of that cell runs with Manual)',
    'manualZoneLength': 'Zone length: bars of the average |volume delta|',
    'manualDeltaThreshold': 'Delta threshold: spike = volume delta beyond this multiple of the average',
    'manualUseEmaFilter': 'Use EMA trend filter',
    'manualEmaLength': 'EMA length (None: EMA filter off)',
    'fgfOn': 'direction filter: Enable filter',
    'signalDirection': 'Signal direction, the OLDER option (None: filter off, where inv True is the Original direction)',
    'inv': 'Inverted direction: opposite side at the same entries (Update 1, dpInv)',
    'slAtrMultS2': 'Stop, ATR(14) multiples',
    'tpRS2': 'Target, R multiples of the stop distance (0 = no target)',
    'timeStopBars': 'Time stop, bars in the trade',
    'useDeadExit': 'Dead-trade exit (not in profit after deadBarsIn bars)',
    'deadBarsIn': 'Dead-trade exit, bars (None: dead exit off)',
    'useTrailS2': 'Trailing stop, ATR mode, with the cell\'s (trailActAtr, trailDstAtr) pair',
}
_DIM_TYPE = {'presetMode': str, 'manualZoneLength': int, 'manualDeltaThreshold': float, 'manualUseEmaFilter': bool,
             'manualEmaLength': int, 'fgfOn': bool, 'signalDirection': str, 'inv': bool, 'slAtrMultS2': float,
             'tpRS2': float, 'timeStopBars': int, 'useDeadExit': bool, 'deadBarsIn': int, 'useTrailS2': bool}
_PA_TYPE = {str: pa.string(), int: pa.int64(), float: pa.float64(), bool: pa.bool_()}

# The default setting: the script's default inputs (danny.DEFAULTS; the Pine's input defaults) WITH
# the grid's scale-free sizing (qtyStepS3 0.000001, maxQtyS3 1e9) and varRollback True.
DEFAULT_P = {d['name']: d['default'] for d in DIMS}
DEFAULT = DEFAULT_P

# SIGNAL settings: the parameters of danny.prepare. fgfOn is the innermost loop.
SIGNALS = [{'presetMode': 'Auto', 'manualZoneLength': zl, 'manualDeltaThreshold': dt, 'manualUseEmaFilter': ue,
            'manualEmaLength': el, 'fgfOn': f}
           for zl in ZONE_LENGTHS for dt in DELTA_THRESHOLDS for ue, el in EMAS for f in FILTERS]
# EXIT settings: the parameters of danny.simulate. signalDirection None = the 216 of a filter-off
# signal setting; a value = the 432 of a filter-on one.
EXITS = [{'signalDirection': sd, 'inv': i, 'slAtrMultS2': s, 'tpRS2': t, 'timeStopBars': ts, 'useDeadExit': de,
          'deadBarsIn': db, 'useTrailS2': tr}
         for sd in (None,) + SIGNAL_DIRECTIONS for i in INVS for s in SL_MULTS for t in TP_RS for ts in TIME_STOPS
         for de, db in DEADS for tr in TRAILS]
_EXITS_OFF = [x for x in EXITS if x['signalDirection'] is None]
_EXITS_ON = [x for x in EXITS if x['signalDirection'] is not None]
N_GRID = len(SIGNALS) // 2 * (len(_EXITS_OFF) + len(_EXITS_ON))       # 17,496


def grid_preset(pair, tf):
    """presetMode of the cell's grid rows: "Manual" on XAU "5" (where Auto is the XAUUSD 5m preset)."""
    return 'Manual' if (pair, str(tf)) == PRESET_CELL else 'Auto'


def signals(pair, tf):
    """The SIGNAL settings of a cell: SIGNALS with the cell's presetMode; XAU "5": plus the signal
    setting of the one extra row (the script default, presetMode Auto), last."""
    mode = grid_preset(pair, tf)
    S = [dict(s, presetMode=mode) for s in SIGNALS]
    if (pair, str(tf)) == PRESET_CELL:
        S.append({k: DEFAULT_P[k] for k in SIGNAL_DIMS})
    return S


def exits_for(sig, pair, tf):
    """The EXIT settings of one SIGNAL setting of a cell, in EXITS order. The extra signal setting
    of XAU "5" (presetMode Auto) has one: the script default."""
    if sig['presetMode'] != grid_preset(pair, tf):
        return [{k: DEFAULT_P[k] for k in EXIT_DIMS}]
    return _EXITS_ON if sig['fgfOn'] else _EXITS_OFF


def merge(sig, x):
    """One grid setting: every dimension of DIMS, in DIMS order."""
    d = dict(sig)
    d.update(x)
    return {k: d[k] for k in DIM_NAMES}


def grid(pair, tf, sig_idx=None):
    """Every setting of a cell, in file order: for each SIGNAL setting, its EXIT settings."""
    S = signals(pair, tf)
    idx = range(len(S)) if sig_idx is None else sig_idx
    return [merge(S[si], x) for si in idx for x in exits_for(S[si], pair, tf)]


def n_settings(pair, tf):
    return N_GRID + (1 if (pair, str(tf)) == PRESET_CELL else 0)


def key(p):
    return tuple(p[k] for k in DIM_NAMES)


def trail_pair(pair, tf):
    """(trailActAtr, trailDstAtr) of the cell = (2d, d)."""
    d = TRAIL_D.get((pair, str(tf)), 1.0)
    return 2.0 * d, d


def signal_params(sig):
    """A SIGNAL setting as danny.prepare params (everything else at the script's defaults)."""
    q = {'presetMode': str(sig['presetMode']), 'manualZoneLength': int(sig['manualZoneLength']),
         'manualDeltaThreshold': float(sig['manualDeltaThreshold']),
         'manualUseEmaFilter': bool(sig['manualUseEmaFilter']), 'fgfOn': bool(sig['fgfOn'])}
    if sig['manualUseEmaFilter']:
        q['manualEmaLength'] = int(sig['manualEmaLength'])
    return q


def exit_params(x, pair, tf, path=PATH, cost=COST, var_rollback=VAR_ROLLBACK, script_sizing=False):
    """An EXIT setting as danny.simulate params. Dimensions listed once are left at the script's
    defaults: signalDirection with the filter off, deadBarsIn with the dead exit off (ignored by
    the kernel); trailActAtr / trailDstAtr (the cell's pair) are only given with the trailing on.
    The fixed controls are always given: varRollback and the two sizing inputs."""
    X = {'dpInv': bool(x['inv']), 'slAtrMultS2': float(x['slAtrMultS2']), 'tpRS2': float(x['tpRS2']),
         'timeStopBars': int(x['timeStopBars']), 'useDeadExit': bool(x['useDeadExit']),
         'useTrailS2': bool(x['useTrailS2']), 'varRollback': bool(var_rollback), 'path': path, 'cost': cost}
    X.update(SCRIPT_SIZING if script_sizing else SCALE_FREE)
    if x['signalDirection'] is not None:
        X['signalDirection'] = str(x['signalDirection'])
    if x['useDeadExit']:
        X['deadBarsIn'] = int(x['deadBarsIn'])
    if x['useTrailS2']:
        X['trailActAtr'], X['trailDstAtr'] = trail_pair(pair, tf)
    return X


def normalize(raw, off_grid=False):
    """A setting given as a mapping of p_ values (keys with or without 'p_'; None / NaN / missing =
    unused) -> the canonical dict over DIM_NAMES. manualEmaLength with the EMA filter off and
    deadBarsIn with the dead exit off are set to None whatever was given (they cannot change the
    result). signalDirection with the filter off: None, the default value or missing -> None; the
    other value is refused (it IS another result: the grid lists it as inv flipped) unless off_grid,
    which runs it as given. Raises ValueError for an unknown key, a missing used dimension, or
    (unless off_grid) a value that is not in the grid."""
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
                if name == 'signalDirection' and v is not None and str(v) != SIG_INV:
                    if str(v) != SIG_ORIG:
                        raise ValueError('signalDirection: %r is not one of %r' % (v, d['values']))
                    if not off_grid:
                        raise ValueError('signalDirection %r with fgfOn false is not in the grid: with the filter '
                                         'off it is the same run as null with inv flipped (--off-grid runs it as '
                                         'given)' % (v,))
                    out[name] = SIG_ORIG
                    continue
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
            if not off_grid or ty in (str, bool):
                raise ValueError('%s: %r is not in the grid %r' % (name, v, d['values']))
        out[name] = v
    return out


_ROWS: dict = {}


def row_of(pair, tf, p):
    """The row number of a setting in the cell's grid file (grid(pair, tf) order), None when it is
    not one of the cell's rows."""
    preset_cell = (pair, str(tf)) == PRESET_CELL
    if preset_cell not in _ROWS:
        _ROWS[preset_cell] = {key(q): i for i, q in enumerate(grid(pair, tf))}
    return _ROWS[preset_cell].get(key(p))


def in_grid(pair, tf, p):
    return row_of(pair, tf, p) is not None


# ---------------------------------------------------------------------------------------------
# what a run must echo; the floor of the trailing distance
# ---------------------------------------------------------------------------------------------
def _check_prepared(sig, Pp):
    """danny.prepare ran the SIGNAL setting it was asked for: no preset replaced a swept input
    (only the extra row of XAU "5" runs under the XAUUSD 5m preset)."""
    A = Pp['active']
    Q = Pp['params']
    preset = sig['presetMode'] == 'Auto' and (Pp['pair'], Pp['tf']) == PRESET_CELL
    ok = (bool(A['usingFxPreset']) == preset and Q['presetMode'] == sig['presetMode']
          and bool(Q['fgfOn']) == bool(sig['fgfOn']) and bool(A['useEmaFilter']) == bool(sig['manualUseEmaFilter'])
          and not A['zoneTrendFilter'])
    if not preset:
        ok = ok and (A['zoneLengthInput'] == sig['manualZoneLength']
                     and A['deltaThresholdInput'] == sig['manualDeltaThreshold']
                     and (not sig['manualUseEmaFilter'] or A['emaLength'] == sig['manualEmaLength']))
    if not ok:
        raise RuntimeError('danny.prepare did not run the signal setting %r: active %r' % (sig, A))


def _check_run(x, X, Pp, R):
    """danny.simulate ran the EXIT setting it was asked for: its effective inputs (R['x']) hold every
    value given, and (without a preset) the dead exit is the swept one."""
    q = R['x']
    for k, v in X.items():
        if q[danny._ALIASES.get(k, k)] != v:
            raise RuntimeError('danny.simulate did not run %r: %s is %r' % (X, k, q[danny._ALIASES.get(k, k)]))
    if not Pp['active']['usingFxPreset']:
        E = R['exit']
        if bool(E['deadExitActive']) != bool(x['useDeadExit']) or (x['useDeadExit'] and E['deadBars'] != x['deadBarsIn']):
            raise RuntimeError('danny.simulate did not run the dead exit of %r: %r' % (x, E))


def cell_floor(pair, tf, Pp):
    """The trailing distance of the cell against the 1-minute noise floor: the 10th percentile over
    the window of ATR(14) / close (%), times trailDstAtr, must be at least FLOOR_PCT[pair]."""
    atr = danny.get_atr(Pp, ATR_LEN)
    p10 = float(np.nanpercentile(atr / Pp['c'] * 100.0, 10))
    act, dst = trail_pair(pair, tf)
    return {'atr_len': ATR_LEN, 'p10_atr_pct': p10, 'trailActAtr': act, 'trailDstAtr': dst,
            'dist_pct_at_p10': dst * p10, 'floor_pct': FLOOR_PCT[pair], 'floor_ok': bool(dst * p10 >= FLOOR_PCT[pair])}


# ---------------------------------------------------------------------------------------------
# one setting
# ---------------------------------------------------------------------------------------------
def one(pair, tf, p, path=PATH, cost=COST, off_grid=False, var_rollback=VAR_ROLLBACK, script_sizing=False,
        cache=None):
    """The full summary (danny.summary) of one setting, computed alone: its own danny.prepare and one
    danny.simulate. p: a mapping of p_ values (see normalize). var_rollback / script_sizing: the two
    controls that are not grid dimensions. cache: a dict that keeps the prepared inputs between
    calls of one process (tests)."""
    tf = str(tf)
    p = normalize(p, off_grid)
    sig = {k: p[k] for k in SIGNAL_DIMS}
    x = {k: p[k] for k in EXIT_DIMS}
    sp = signal_params(sig)
    ck = (pair, tf, tuple(sorted(sp.items())))
    Pp = cache.get(ck) if cache is not None else None
    if Pp is None:
        Pp = danny.prepare(pair, tf, sp)
        if cache is not None:
            cache[ck] = Pp
    _check_prepared(sig, Pp)
    X = exit_params(x, pair, tf, path, cost, var_rollback, script_sizing)
    R = danny.simulate(Pp, X)
    _check_run(x, X, Pp, R)
    s = danny.summary(Pp, R)
    out = {'floor_ok': bool((not x['useTrailS2']) or cell_floor(pair, tf, Pp)['floor_ok'])}
    out.update(s)
    row = row_of(pair, tf, p)
    E = R['exit']
    act, dst = trail_pair(pair, tf) if x['useTrailS2'] else (None, None)
    out['setting'] = {'strategy': STRATEGY, 'pair': pair, 'tf': tf, 'path': path, 'cost': cost, 'p': p,
                      'in_grid': row is not None, 'row': row, 'varRollback': bool(var_rollback),
                      'sizing': 'script' if script_sizing else 'scale-free',
                      'qtyStepS3': R['x']['qtyStepS3'], 'maxQtyS3': R['x']['maxQtyS3'],
                      'useOnePerZone': bool(E['onePerZoneActive']), 'useCooldown': bool(E['cooldownActive']),
                      'cooldownIn': int(E['cooldownBars']), 'trailActAtr': act, 'trailDstAtr': dst,
                      'preset': 'XAUUSD 5m' if Pp['active']['usingFxPreset'] else None}
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
# arrays of a prepared input that the kernel reads; equal ones are kept once per cell
_ARRAYS = ('o', 'h', 'l', 'c', 'pc', 't_open', 't_close', 'd_spike', 's_spike', 'trend_l', 'trend_s', 'gate',
           'bclose', 'pre', 'lblock', 'sblock', 'buy_ok', 'sell_ok')


def _slim(Pp, pool):
    """Drop the diagnostic arrays of a prepared input and replace every array that equals one
    already seen in this cell by that one (the bars, the clock gates, the permissions of the same
    filter state, spikes / trend flags shared between signal settings)."""
    Pp['diag'] = None
    for k in _ARRAYS:
        a = Pp[k]
        seen = pool.setdefault(k, [])
        for b in seen:
            if b.dtype == a.dtype and b.shape == a.shape and np.array_equal(a, b, equal_nan=a.dtype.kind == 'f'):
                Pp[k] = b
                break
        else:
            seen.append(a)


def _free_caches(bars=False):
    """The module caches that the prepared inputs no longer need: the filter's series and the
    permission frames (the prepared inputs hold their own arrays); with bars, danny's bar files."""
    danny._PERM.clear()
    fgf = sys.modules.get('fgf')
    for name in ('_BARS', '_DIR', '_FILTER'):
        c = getattr(fgf, name, None) if fgf is not None else None
        if isinstance(c, dict):
            c.clear()
    if bars:
        danny._BARS.clear()
    gc.collect()


def prepare_cell(pair, tf, sig_idx=None, verbose=False):
    """danny.prepare once per SIGNAL setting of the cell (all, or those of sig_idx), the 1-minute
    sub-bars and ATR(14) once, the floor of the trailing distance, the kernel compiled. Returns the
    cell: P {signal index: prepared input}, the summary columns and timings."""
    tf = str(tf)
    S = signals(pair, tf)
    idx = list(range(len(S))) if sig_idx is None else [int(i) for i in sig_idx]
    t0 = time.time()
    c0 = time.process_time()
    P = {}
    pool = {}
    for si in idx:
        Pp = danny.prepare(pair, tf, signal_params(S[si]))
        _check_prepared(S[si], Pp)
        _slim(Pp, pool)
        P[si] = Pp
    p0 = P[idx[0]]
    for si, Pk in P.items():
        if (Pk['w0'], Pk['w1'], Pk['mid'], Pk['mid_j'], Pk['n']) != (p0['w0'], p0['w1'], p0['mid'], p0['mid_j'], p0['n']):
            raise ValueError('%s %s signal setting %d: window rows differ' % (pair, tf, si))
        Pk['atr'] = p0['atr']                      # one ATR cache per cell (same bars, same window)
    t_sig = time.time() - t0
    t1 = time.time()
    n_sub = 0
    if PATH == 'mag':
        sub = danny.get_sub(p0)                    # built once, checked against the chart bars
        n_sub = len(sub[1])
        for Pk in P.values():
            Pk['sub'] = sub
    floor = cell_floor(pair, tf, p0)
    t_sub = time.time() - t1
    t2 = time.time()
    x0 = exits_for(S[idx[0]], pair, tf)[0]
    s = danny.summary(p0, danny.simulate(p0, exit_params(x0, pair, tf)))          # compile / load the kernel
    t_jit = time.time() - t2
    cols = list(s.keys())
    kinds = {}
    for k, v in s.items():
        if isinstance(v, (bool, np.bool_)):
            kinds[k] = bool
        elif isinstance(v, (int, np.integer)):
            kinds[k] = int
        else:
            kinds[k] = float
    _free_caches()
    cell = dict(pair=pair, tf=tf, idx=idx, S=S, P=P, cols=cols, kinds=kinds, bars=int(p0['n']), n_sub=n_sub,
                floor=floor, prepares=len(idx), t_sig=t_sig, t_sub=t_sub, t_jit=t_jit, t_prep=time.time() - t0,
                cpu_prep=time.process_time() - c0)
    if verbose:
        print('  %s %s: %d chart bars, %d 1-minute bars; %d signal settings prepared in %.1fs, sub-bars + ATR %.1fs, '
              'kernel %.1fs' % (pair, tf, cell['bars'], n_sub, len(idx), t_sig, t_sub, t_jit), flush=True)
        print('  trailing pair (trailActAtr, trailDstAtr) = (%g, %g): %g x ATR(14)/close at the 10th percentile '
              '(%.4f %%) = %.4f %% of price, floor %.2f %%: floor_ok %s'
              % (floor['trailActAtr'], floor['trailDstAtr'], floor['trailDstAtr'], floor['p10_atr_pct'],
                 floor['dist_pct_at_p10'], floor['floor_pct'], floor['floor_ok']), flush=True)
    return cell


def _work(task):
    si, i0, i1 = task
    t0 = time.time()
    Pp = _G['P'][si]
    X = _G['X'][si]
    cols = _G['cols']
    pair = _G['pair']
    tf = _G['tf']
    out = []
    for i in range(i0, i1):
        xp = exit_params(X[i], pair, tf)
        R = danny.simulate(Pp, xp)
        _check_run(X[i], xp, Pp, R)
        s = danny.summary(Pp, R)
        out.append(tuple(s[k] for k in cols))
    return si, i0, out, time.time() - t0


def run_prepared(cell, workers=MAX_WORKERS, sig_idx=None, chunk=CHUNK, verbose=False):
    """Simulate every exit setting of the prepared signal settings (all of the cell, or sig_idx).
    Returns (res {signal index: [summary tuple per exit setting]}, info)."""
    pair, tf = cell['pair'], cell['tf']
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    X = {si: exits_for(cell['S'][si], pair, tf) for si in idx}
    _G.clear()
    _G.update(P=cell['P'], X=X, cols=cell['cols'], pair=pair, tf=tf)
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


def table(cell, res, sig_idx=None):
    """The rows in grid order as an arrow table: p_<name> per dimension (null = None), floor_ok, then
    every summary field. Column types are fixed here (they do not depend on the values)."""
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
    names.append('floor_ok')
    arrays.append(pa.array([bool((not p['useTrailS2']) or cell['floor']['floor_ok']) for p in G], type=pa.bool_()))
    for j, k in enumerate(cell['cols']):
        ty = cell['kinds'][k]
        col = [v[j] for v in vals]
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
            'window': [int(v) for v in danny.WINDOWS[pair]], 'varRollback': VAR_ROLLBACK,
            'qtyStepS3': SCALE_FREE['qtyStepS3'], 'maxQtyS3': SCALE_FREE['maxQtyS3'],
            'grid_presetMode': grid_preset(pair, tf), 'trailActAtr': act, 'trailDstAtr': dst, 'floor': floor,
            'danny_sha256': _sha256(os.path.join(W, 'danny.py')), 'fgf_sha256': _sha256(os.path.join(W, 'fgf.py'))}


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
    info['rows_zero_qty'] = int((df['zero_qty'] > 0).sum())
    info['rows_30_trades_each_half'] = int(((df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).sum())
    if verbose:
        w = max(info['workers'], 1)
        print('  %s %s done: %d rows%s | prep %.1fs, runs %.1fs with %d workers (%.2f worker-s, %.5fs per '
              'setting per worker; workers busy %.0f%%), total %.1fs; load average %.2f'
              % (pair, tf, len(df), (' -> ' + info['file']) if info['file'] else ' (not written)', info['t_prep'],
                 info['t_run'], w, info['busy'], info['busy'] / max(info['settings'], 1),
                 100.0 * info['busy'] / max(info['t_run'] * w, 1e-9), info['t_total'], os.getloadavg()[0]), flush=True)
        print('  rows with a quantity floored to zero (zero_qty > 0: an account too small for the 0.000001 step): %d; '
              'rows with at least 30 trades in each half: %d'
              % (info['rows_zero_qty'], info['rows_30_trades_each_half']), flush=True)
    _G.clear()
    return df, info


def estimate_cell(pair, tf, workers=MAX_WORKERS, per_signal=6, seed=20261126, verbose=True):
    """Estimated time of the full cell from ONE process: the real preparation, then per_signal random
    exit settings of every signal setting timed one by one; run time = sum over the signal settings
    of (mean sampled time x its number of exit settings) / workers. Two estimates: from the wall
    clock (the machine as loaded as it is now) and from this process' CPU time (the 3 workers
    each having a free CPU). Writes nothing."""
    tf = str(tf)
    cell = prepare_cell(pair, tf, None, verbose)
    rng = np.random.default_rng(seed)
    t_single = 0.0
    c_single = 0.0
    worst = 0.0
    n_s = 0
    n_zero = 0
    n_thin = 0
    t0 = time.time()
    for si in cell['idx']:
        X = exits_for(cell['S'][si], pair, tf)
        Pp = cell['P'][si]
        tt = []
        cc = []
        for i in rng.choice(len(X), size=min(per_signal, len(X)), replace=False):
            t = time.time()
            c = time.process_time()
            xp = exit_params(X[int(i)], pair, tf)
            R = danny.simulate(Pp, xp)
            _check_run(X[int(i)], xp, Pp, R)
            sm = danny.summary(Pp, R)
            tt.append(time.time() - t)
            cc.append(time.process_time() - c)
            n_zero += sm['zero_qty'] > 0
            n_thin += sm['h1_trades'] < 30 or sm['h2_trades'] < 30
        t_single += float(np.mean(tt)) * len(X)
        c_single += float(np.mean(cc)) * len(X)
        worst = max(worst, max(tt))
        n_s += len(tt)
    n_all = n_settings(pair, tf)
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
    ap = argparse.ArgumentParser(prog='calib_danny.py --one', description='the full summary of one setting, as JSON')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tf', choices=TFS)
    ap.add_argument('p', help='JSON object of the p_ values of the setting')
    ap.add_argument('--path', choices=('tv', 'mag'), default=PATH)
    ap.add_argument('--cost', choices=tuple(danny.COSTS), default=COST)
    ap.add_argument('--var-rollback', choices=('true', 'false'), default='true',
                    help='false = the "as written" reading (danny varRollback False); not a grid dimension')
    ap.add_argument('--script-sizing', action='store_true',
                    help="the file's own qtyStepS3 0.001 and maxQtyS3 50 instead of the grid's scale-free sizing")
    ap.add_argument('--off-grid', action='store_true', help='accept values that are not in the grid')
    a = ap.parse_args(argv)
    try:
        raw = json.loads(a.p)
        if not isinstance(raw, dict):
            raise ValueError('the p_ values must be a JSON object')
        out = one(a.pair, a.tf, raw, a.path, a.cost, a.off_grid, a.var_rollback == 'true', a.script_sizing)
    except ValueError as e:
        print('calib_danny.py --one: %s' % e, file=sys.stderr)
        return 2
    print(json.dumps(out, default=_json_default))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--one' in argv:
        argv.remove('--one')
        return _main_one(argv)
    ap = argparse.ArgumentParser(description='Danny Phantom FX V10.21.1 + FGF calibration grid (CALIB_SPEC.md)')
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
            print('== calib %s %s %s: %d settings (%d signal settings x their exit settings), path %s, cost %s, '
                  'varRollback %s, qtyStepS3 %g, maxQtyS3 %g =='
                  % (STRATEGY, a.pair, tf, n_settings(a.pair, tf), len(signals(a.pair, tf)), PATH, COST, VAR_ROLLBACK,
                     SCALE_FREE['qtyStepS3'], SCALE_FREE['maxQtyS3']), flush=True)
            run_cell(a.pair, tf, workers, a.out_dir)
        _free_caches(bars=True)
    print('all done in %.1fs' % (time.time() - t0), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
