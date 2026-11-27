"""calib_amvi.py: calibration grid of the AMVI Full MTF Strategy + FGF [Update 1] (key amvi) per pair
and timeframe, with the direction (Normal / Inverted) as a calibrated input (CALIB_SPEC.md, strategy
"amvi"; the grid is section 14 of SPEC_amvi.md), on the canonical replica amvi.py (prepare / simulate /
summary; the direction filter is fgf.fgf_permissions, called by amvi.prepare).

Usage (python3 -I)
  calib_amvi.py PAIR TF [TF ...] [--workers 3] [--out-dir DIR]
      runs the full grid of every (PAIR, TF) cell and writes out/calib_amvi_<PAIR>_<TF>.parquet (one
      row per setting) and out/calib_amvi_dims.json (DIMS). PAIR in BTC, XAU; TF in 1, 5, 15, 30, 60,
      120, 240. Safe to re-run: the files are overwritten (written to a temporary name first). Prints
      the timing of every cell.
  calib_amvi.py --one PAIR TF '<json of p_ values>' [--path tv|mag] [--cost tv|ours|stress]
                [--ltf-last] [--off-grid]
      prints the full summary of ONE setting as one JSON document on stdout (default path mag, cost
      ours = the sweep's scoring). The JSON of p_ values is a row's p_ columns: keys with or without
      the "p_" prefix, null (or NaN) for an unused dimension. One control that is NOT a grid
      dimension (every grid row has ltfRule 'first'):
        --ltf-last   ltfRule 'last' (assumption A2 of SPEC_amvi.md read the other way: a timeframe
                     lower than the chart is read as [1] of the LAST intrabar of the chart bar, as a
                     live bar does, instead of the first). Charts above 1 minute with a lower timeframe
                     enabled only; on chart "1" and with tfSet 'ge' it changes nothing.
      --off-grid also accepts numbers that are not in the grid (highVolThreshold, minConfluence 1..12,
      fgfBandAtr, slMult), another filter timeframe T in minutes (the parent / zones then move with
      it: T / T / 2T / 4T) and tfSet 'ge' on charts 120 / 240.
  calib_amvi.py --estimate PAIR TF [TF ...] [--workers 3] [--per-signal 4]
      times the cell's preparation and a random sample of settings in ONE process and prints the
      estimated time of the full cell; writes nothing.

The grid (SPEC_amvi.md section 14): 24,192 settings per cell on charts 5, 15, 30, 60 and 12,096 on
charts 1, 120, 240 = 504 (252) signal settings x 48 exit settings.
  trigger    highVolThreshold {50, 60, 70, 80} x minConfluence {1, 2, 3} x tfSet {'all' = the seven
             timeframes 1m .. 1D on (en1 .. enD), 'ge' = only those at or above the chart's}; charts 1,
             120, 240: tfSet None = 'all' only (on chart 1 'ge' IS 'all'; on 120 / 240 it would leave
             only 4h and 1D: not in the grid) = 24 trigger settings (12)
  direction  dirSource 'orig' (the filter OFF: the unfused original AMVI_Full_MTF_Strategy.pine, its
             direction dirMode {"Trend (EMA)", "Candle", "Breakout (Donchian)"}; fgf* None) and
             dirSource 'fgf' (the filter ON: the fused file, its direction = the FlashGold Direction
             Filter's zone, fgfTf {"15", "60", "240"} x fgfBandAtr {0.0, 0.25, 0.75} x fgfLvMode
             {"Entry price", "Signal close"}; dirMode None) = 3 + 18 = 21 direction settings.
             fgfTf T moves the parent and the zones with it: fgfParentTf = T, fgfZTf1 / 2 / 3 = T / 2T /
             4T (15 / 30 / 60, 60 / 120 / 240, 240 / 480 / 960). The fused file with fgfOn false trades
             nothing, so "filter off" is dirSource 'orig'; this script has no blocked-signal close.
  exits      inv {False, True} (= amviTradeDir "Follow the filter" / "Inverted", the script's own input;
             with 'orig' a replica-only control: the original file has no such input) x slMult {1.0, 1.5,
             2.5} x exitStyle {'tp3' = (tpMult 3, no trail), 'tp1.5' = (1.5, no trail), 'none' = (0, no
             trail): stop, reversal and collapse only, 'trail' = (0, useTrail with the cell's pair
             below)} x useVolExit {True, False} = 48
  trailing   exitStyle 'trail' = (trailActMul, trailOffMul) = (1.5 d, d) (the script's own 1.5 : 1), ONE
             pair per cell, the table of section 14: d the smallest of {1, 1.75, 2.5, 3.5, 5, 6.5} for
             which d x ATR(14) / close at the 10th percentile of all window bars is at least the 1-minute
             noise floor (BTC 0.1 %, XAU 0.05 %):
                 BTC 1 (9.75, 6.5) | BTC 5 (2.625, 1.75) | BTC 15 .. 240 (1.5, 1)
                 XAU 1 (7.5, 5)    | XAU 5 (2.625, 1.75) | XAU 15 .. 240 (1.5, 1)
             (measured again on the data at every run: in the file metadata, "floor").
  floor_ok   section 14: False for a row whose min_trail_off_pct (the smallest trailing offset of its
             trades, % of the entry price) is below the floor of the pair, True otherwise (rows without
             the trailing stop, and trailing rows without a trade, have min_trail_off_pct NaN: True).
Fixed for EVERY row (decisions of the orchestrator, not dimensions):
  ltfRule 'first'   (A2; --one --ltf-last re-scores a pick under the other reading)
  sizing            the file's own: 10 % of equity per trade (default_qty_type percent_of_equity,
                    default_qty_value 10, capital 10,000); scale-free, no quantity step, no cap
  seconds toggles   en1s .. en45s at the script default (true): no data below 1 minute, so they are
                    na on every bar = off (the Pine run with them off); seconds_ignored = 5 on every row
Everything else stays at the script's defaults (periods 14 / 50 / 20 / 10 / 200, the weights, noRepaint
on, lowVolThreshold 30, maxBars 0, exitAtrLen 14, emaLen 50, dcLen 20, tradeDir "Both", allowReverse
on, the filter's other inputs (fgfOn true)) and the replica's readings (revClose 'void' = A11: a
close_all placed in the same run as a reversal does nothing; counted per row in rev_close_same_run, which
is above 0 only with useVolExit on: 1,081 rows of XAU 240 (0.25 % of their trades), 624 of BTC 240).
default_p(pair, tf, source) gives the two script defaults, both grid rows of every cell: the fused
file (70, 3, 'all', 'fgf', "60", 0.25, "Entry price", normal, 1.5, 'tp3', collapse on) and the original
(70, 3, 'all', 'orig', "Trend (EMA)", normal, 1.5, 'tp3', collapse on); tfSet None on charts 1 / 120 /
240. DEFAULT_P = the fused one with tfSet 'all' (the defaults of DIMS where they are used).

signals(tf) (504 or 252) are the parameters of amvi.prepare (trigger + direction, in DIMS order); EXITS
(48) those of amvi.simulate, the same for every signal setting. A dimension that cannot change the
result is listed once with the value None: dirMode with 'fgf', fgfTf / fgfBandAtr / fgfLvMode with
'orig' (DIMS key unused_when), tfSet on charts 1, 120, 240 (DIMS key unused_on_charts). DIMS = the 12
dimensions (name, values, kind 'ordinal' / 'categorical'; extra keys: side, default, unused_when,
unused_on_charts); row i of a file is grid(pair, tf)[i]. The direction dimension is named inv.

Every setting is scored with path 'mag' (the exit bracket walked along the 1-minute sub-bars; on chart
"1" each bar is its own sub-bar) and cost 'ours'. Per cell: amvi.prepare runs ONCE per signal setting
(in direction-major order, so that the module's direction cache and fgf's filter-series cache serve the
24 (12) trigger settings of a direction), the prepared inputs are slimmed (the arrays that simulate /
summary / trades never read are dropped: trigger, inRange, anyCross, dirUp, dirDn, enCount; arrays equal
between signal settings are kept once; views into the bar files are replaced by window copies), the
1-minute sub-bars, ATR(14) and the volatility-collapse series are built once, the module caches are
dropped, the kernel is compiled, and only then at most 3 workers are forked (copy-on-write); each
simulates the exit settings of one prepared input (amvi.simulate + amvi.summary) and checks that the
module ran exactly the setting it was asked to run. Rows are assembled in grid order, so the file does
not depend on the worker count.

Output columns, in this order:
  p_<name>   one per dimension of DIMS, in DIMS order (p_tfSet, p_dirSource, p_dirMode, p_fgfTf,
             p_fgfLvMode and p_exitStyle are text, the others numbers / booleans; null = None)
  en1, en5, en15, en30, en60, en240, enD, fgfParentTf, fgfZTf1, fgfZTf2, fgfZTf3, tpMult, useTrail,
  trailActMul, trailOffMul
             the Pine inputs that the derived dimensions set (tfSet, fgfTf, exitStyle); fgfParentTf ..
             fgfZTf3 are null with 'orig'; trailActMul / trailOffMul are the cell's pair on 'trail' rows
             and null elsewhere (the trailing stop is off there). They do not start with p_: not
             dimensions.
  floor_ok   see above
  then every field of amvi.summary (all scalars) in its own order: start, end, bars, trades, net_pct,
  pf, win_pct, max_dd_pct, max_dd_init_pct, long, short (REAL sides), raw_long, raw_short (= trig_up /
  trig_dn: triggers in the BUY / SELL zone, or with an up / down bias, normal frame), blocked_long,
  blocked_short (always 0), half1_pct, half2_pct, exposure, final_equity, exit_<kind> counts (sl, tp,
  trail, reverse, vol, time, end), zero_length, h1r_pct, h2r_pct, h1_trades, h2_trades (the fair
  halves), avg_bars_held, costs, triggers, trig_up, trig_dn, trig_none, taken_up, taken_dn,
  ignored_held, orders_unfilled_end, zero_qty, rev_close_same_run, slippage_paid, net_r, h1_r, h2_r (R =
  pnl / (stop distance x quantity)), min_trail_off_pct, seconds_ignored.
Nothing else: no index, no pair / tf column (they are in the file name; the parquet's key-value
metadata "calib" holds strategy, pair, tf, path, cost, ltfRule, the number of settings, the window, the
fixed controls, the tfSet toggles of the cell, the exit styles, the trailing pair and its floor
measurement, and the sha256 of amvi.py and fgf.py that produced the rows: the files as they were when
this process imported them). pf is +inf without a losing trade and NaN without trades; win_pct and
avg_bars_held are NaN without trades; min_trail_off_pct is NaN without the trailing stop or without
trades. --one prints the same non-p_ columns in the same order (Python's json: Infinity / NaN, null)
plus "setting" = {strategy, pair, tf, path, cost, ltfRule, p (the canonical p_ values), in_grid, row
(p is a row of the cell's grid, and its number in the grid file; with --ltf-last, or another path /
cost, the result is NOT that row's), enabled (en1 .. enD as the module resolved them), direction
(dirSource and its inputs as the module resolved them), cell_trail (the cell's pair)}.

Cost (measured 2026-11-27 on the shared machine): one amvi.prepare is 0.01 s (XAU 240) to about 0.1 s
(BTC 1) once the AMVI parts and the filter series are cached (a first one 1.6 s / 5 s); one simulate +
summary 'mag' 1.4 ms (XAU 240) to about 10 ms (BTC 1). See --estimate for every cell.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import multiprocessing as mp
import os
import resource
import sys
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import amvi  # noqa: E402  (imports fgf)
import fgf   # noqa: E402

STRATEGY = 'amvi'
MAX_WORKERS = 3
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
PATH = 'mag'             # the sweep's scoring: 1-minute fills ...
COST = 'ours'            # ... with our costs
LTF_RULE = 'first'       # every grid row (A2); --one --ltf-last: 'last'
CHUNK = 48               # exit settings per worker task (= all of one signal setting)

# ---------------------------------------------------------------------------------------------
# the grid (SPEC_amvi.md section 14)
# ---------------------------------------------------------------------------------------------
TREND, CANDLE, BREAKOUT = "Trend (EMA)", "Candle", "Breakout (Donchian)"
LV_ENTRY, LV_CLOSE = "Entry price", "Signal close"
HIGH_VOLS = (50.0, 60.0, 70.0, 80.0)
CONFLUENCES = (1, 2, 3)
TF_SETS = ('all', 'ge')
TFSET_CHARTS = ('5', '15', '30', '60')            # the charts where tfSet is a dimension
DIR_SOURCES = ('orig', 'fgf')
DIR_MODES = (TREND, CANDLE, BREAKOUT)
FILTER_TFS = ('15', '60', '240')
BANDS = (0.0, 0.25, 0.75)
LV_MODES = (LV_ENTRY, LV_CLOSE)
INVS = (False, True)
SL_MULTS = (1.0, 1.5, 2.5)
USE_VOL_EXITS = (True, False)
# exitStyle: the Pine inputs each member sets ('trail': plus the cell's trailActMul / trailOffMul)
EXIT_STYLES = {
    'tp3': {'tpMult': 3.0, 'useTrail': False},
    'tp1.5': {'tpMult': 1.5, 'useTrail': False},
    'none': {'tpMult': 0.0, 'useTrail': False},
    'trail': {'tpMult': 0.0, 'useTrail': True},
}
STYLES = tuple(EXIT_STYLES)
# the seven requested timeframes that have data (amvi.TFS) with their toggles and their length in minutes
EN_KEYS = tuple(amvi.EN_KEYS)                     # en1, en5, en15, en30, en60, en240, enD
TF_MINUTES = (1, 5, 15, 30, 60, 240, 1440)

# trailing: one (trailActMul, trailOffMul) = (1.5 d, d) per cell, the table of section 14
ATR_LEN = 14
TRAIL_LADDER = (1.0, 1.75, 2.5, 3.5, 5.0, 6.5)
FLOOR_PCT = {'BTC': 0.1, 'XAU': 0.05}             # 1-minute noise floor, % of price
TRAIL_D = {('BTC', '1'): 6.5, ('BTC', '5'): 1.75, ('XAU', '1'): 5.0, ('XAU', '5'): 1.75}   # else 1.0
LOW_VOL = 30.0                                    # lowVolThreshold, the script default (not swept)

# name, values, kind as CALIB_SPEC.md asks; extra keys (as calib_hrd.py): side = 'signal' (a parameter
# of amvi.prepare) or 'exit' (of amvi.simulate), default = the script's default input, unused_when = the
# value of another dimension with which this one is listed once (its value is None), unused_on_charts =
# the charts on which it is listed once (None)
DIMS = [
    {'name': 'highVolThreshold', 'values': list(HIGH_VOLS), 'kind': 'ordinal', 'side': 'signal', 'default': 70.0},
    {'name': 'minConfluence', 'values': list(CONFLUENCES), 'kind': 'ordinal', 'side': 'signal', 'default': 3},
    {'name': 'tfSet', 'values': list(TF_SETS), 'kind': 'categorical', 'side': 'signal', 'default': 'all',
     'unused_on_charts': ['1', '120', '240']},
    {'name': 'dirSource', 'values': list(DIR_SOURCES), 'kind': 'categorical', 'side': 'signal', 'default': 'fgf'},
    {'name': 'dirMode', 'values': list(DIR_MODES), 'kind': 'categorical', 'side': 'signal', 'default': TREND,
     'unused_when': {'dirSource': 'fgf'}},
    {'name': 'fgfTf', 'values': list(FILTER_TFS), 'kind': 'ordinal', 'side': 'signal', 'default': '60',
     'unused_when': {'dirSource': 'orig'}},
    {'name': 'fgfBandAtr', 'values': list(BANDS), 'kind': 'ordinal', 'side': 'signal', 'default': 0.25,
     'unused_when': {'dirSource': 'orig'}},
    {'name': 'fgfLvMode', 'values': list(LV_MODES), 'kind': 'categorical', 'side': 'signal', 'default': LV_ENTRY,
     'unused_when': {'dirSource': 'orig'}},
    {'name': 'inv', 'values': list(INVS), 'kind': 'categorical', 'side': 'exit', 'default': False},
    {'name': 'slMult', 'values': list(SL_MULTS), 'kind': 'ordinal', 'side': 'exit', 'default': 1.5},
    {'name': 'exitStyle', 'values': list(STYLES), 'kind': 'categorical', 'side': 'exit', 'default': 'tp3'},
    {'name': 'useVolExit', 'values': list(USE_VOL_EXITS), 'kind': 'categorical', 'side': 'exit', 'default': True},
]
DIM_NAMES = [d['name'] for d in DIMS]
SIGNAL_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'signal')
EXIT_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'exit')
UNUSED_WHEN = {d['name']: next(iter(d['unused_when'].items())) for d in DIMS if 'unused_when' in d}
DIM_DOC = {
    'highVolThreshold': 'High Vol Threshold: the AMVI level a timeframe must cross (and count above)',
    'minConfluence': 'Min TFs Above High Vol (Confluence) when one of them crosses it',
    'tfSet': "the enabled timeframes en1 .. enD: 'all' = the seven, 'ge' = those at or above the chart's (None on "
             "charts 1, 120, 240: 'all' only)",
    'dirSource': "the direction: 'orig' = the unfused original's bias (the filter off), 'fgf' = the FlashGold "
                 "Direction Filter's zone (the fused file, the filter on)",
    'dirMode': 'Direction Filter of the original: EMA trend / candle colour / Donchian breakout (None with fgf)',
    'fgfTf': 'Filter timeframe; the parent obedience timeframe and the zones 1 / 2 / 3 move with it (T, T / 2T / 4T); '
             'None with orig',
    'fgfBandAtr': 'No-trade band around the level, ATR mult (None with orig)',
    'fgfLvMode': "Level = the signal's entry price or the signal candle's close (None with orig)",
    'inv': 'Trade direction Inverted (amviTradeDir, the script\'s own input; replica-only with orig): a BUY-ZONE '
           'trigger opens a short',
    'slMult': 'Stop Loss, ATR(14) multiples',
    'exitStyle': "tp3 = 3 ATR target; tp1.5 = 1.5 ATR target; none = stop, reversal and collapse only; trail = no "
                 "target, ATR trailing stop with the cell's (trailActMul, trailOffMul) pair",
    'useVolExit': 'Exit on Volatility Collapse (average AMVI crosses below Low Vol 30)',
}
_DIM_TYPE = {'highVolThreshold': float, 'minConfluence': int, 'tfSet': str, 'dirSource': str, 'dirMode': str,
             'fgfTf': str, 'fgfBandAtr': float, 'fgfLvMode': str, 'inv': bool, 'slMult': float, 'exitStyle': str,
             'useVolExit': bool}
_PA_TYPE = {str: pa.string(), int: pa.int64(), float: pa.float64(), bool: pa.bool_()}
# the Pine inputs that the derived dimensions set, written as columns that are not dimensions
INPUT_COLS = tuple((k, bool) for k in EN_KEYS) + (
    ('fgfParentTf', str), ('fgfZTf1', str), ('fgfZTf2', str), ('fgfZTf3', str), ('tpMult', float),
    ('useTrail', bool), ('trailActMul', float), ('trailOffMul', float))
INPUT_NAMES = tuple(k for k, _ in INPUT_COLS)

# The script defaults: the defaults of DIMS where they are used.
DEFAULT_P = {d['name']: d['default'] for d in DIMS}
DEFAULT_P['dirMode'] = None                      # the fused file's default reads the filter, not dirMode
DEFAULT = DEFAULT_P


def has_tfset(tf):
    """tfSet is a dimension on charts 5, 15, 30, 60; elsewhere it is None ('all' only)."""
    return str(tf) in TFSET_CHARTS


def tf_sets(tf):
    return TF_SETS if has_tfset(tf) else (None,)


def default_p(pair=None, tf='60', source='fgf'):
    """The script default of a cell as a grid row: source 'fgf' = the fused file, 'orig' = the original."""
    p = dict(DEFAULT_P)
    if source == 'orig':
        p.update(dirSource='orig', dirMode=TREND, fgfTf=None, fgfBandAtr=None, fgfLvMode=None)
    elif source != 'fgf':
        raise ValueError('source %r is not fgf / orig' % (source,))
    if not has_tfset(tf):
        p['tfSet'] = None
    return p


TRIGGER_SETTINGS = {}
for _tf in TFS:
    TRIGGER_SETTINGS[_tf] = [{'highVolThreshold': h, 'minConfluence': m, 'tfSet': ts}
                             for h in HIGH_VOLS for m in CONFLUENCES for ts in tf_sets(_tf)]
DIRECTION_SETTINGS = ([{'dirSource': 'orig', 'dirMode': dm, 'fgfTf': None, 'fgfBandAtr': None, 'fgfLvMode': None}
                       for dm in DIR_MODES]
                      + [{'dirSource': 'fgf', 'dirMode': None, 'fgfTf': t, 'fgfBandAtr': b, 'fgfLvMode': lv}
                         for t in FILTER_TFS for b in BANDS for lv in LV_MODES])
# SIGNAL settings of a cell: the parameters of amvi.prepare, in DIMS order (trigger outer, direction inner)
_SIGNALS = {tf: [dict(tr, **dr) for tr in TRIGGER_SETTINGS[tf] for dr in DIRECTION_SETTINGS] for tf in TFS}
# EXIT settings: the parameters of amvi.simulate (the same for every signal setting and cell)
EXITS = [{'inv': i, 'slMult': s, 'exitStyle': es, 'useVolExit': ve}
         for i in INVS for s in SL_MULTS for es in STYLES for ve in USE_VOL_EXITS]
N_GRID = {tf: len(_SIGNALS[tf]) * len(EXITS) for tf in TFS}          # 24,192 or 12,096


def signals(pair=None, tf='60'):
    """The SIGNAL settings of a cell (504 on charts 5 .. 60, 252 on 1, 120, 240; the same for both pairs)."""
    return _SIGNALS[str(tf)]


def exits_for(sig=None, pair=None, tf=None):
    """The EXIT settings of one SIGNAL setting (the same 48 for every signal setting and cell)."""
    return EXITS


def merge(sig, x):
    """One grid setting: every dimension of DIMS, in DIMS order."""
    d = dict(sig)
    d.update(x)
    return {k: d[k] for k in DIM_NAMES}


def grid(pair=None, tf='60', sig_idx=None):
    """Every setting of a cell, in file order: for each SIGNAL setting, its EXIT settings."""
    S = signals(pair, tf)
    idx = range(len(S)) if sig_idx is None else sig_idx
    return [merge(S[si], x) for si in idx for x in EXITS]


def n_settings(pair=None, tf='60'):
    return N_GRID[str(tf)]


def key(p):
    return tuple(p[k] for k in DIM_NAMES)


def tf_set(t):
    """fgfTf T -> (fgfParentTf, fgfZTf1, fgfZTf2, fgfZTf3) = (T, T, 2T, 4T)."""
    m = int(str(t))
    return str(m), str(m), str(2 * m), str(4 * m)


def enabled(ts, tf):
    """tfSet -> the seven toggles en1 .. enD on chart tf: 'all' (or None) = all on; 'ge' = the timeframes of
    at least the chart's length on."""
    if ts is None or ts == 'all':
        return {k: True for k in EN_KEYS}
    if ts != 'ge':
        raise ValueError('tfSet %r is not all / ge' % (ts,))
    m = int(str(tf))
    return {k: mm >= m for k, mm in zip(EN_KEYS, TF_MINUTES)}


def trail_pair(pair, tf):
    """(trailActMul, trailOffMul) of the cell = (1.5 d, d)."""
    d = TRAIL_D.get((pair, str(tf)), 1.0)
    return 1.5 * d, d


def signal_params(sig, tf, ltf_rule=LTF_RULE):
    """A SIGNAL setting as amvi.prepare params (everything else at the script's defaults): the two
    thresholds, the seven toggles of tfSet, the direction source and its inputs (dirMode with 'orig';
    the filter timeframe with its parent / zones, the band and the level with 'fgf'), ltfRule."""
    q = {'highVolThreshold': float(sig['highVolThreshold']), 'minConfluence': int(sig['minConfluence'])}
    q.update(enabled(sig['tfSet'], tf))
    q['dirSource'] = str(sig['dirSource'])
    if sig['dirSource'] == 'orig':
        q['dirMode'] = str(sig['dirMode'])
    else:
        par, z1, z2, z3 = tf_set(sig['fgfTf'])
        q.update(fgfTf=str(sig['fgfTf']), fgfParentTf=par, fgfZTf1=z1, fgfZTf2=z2, fgfZTf3=z3,
                 fgfBandAtr=float(sig['fgfBandAtr']), fgfLvMode=str(sig['fgfLvMode']))
    q['ltfRule'] = ltf_rule
    return q


def exit_params(x, pair, tf, path=PATH, cost=COST):
    """An EXIT setting as amvi.simulate params: inv, slMult, the two inputs of its exit style (and, with
    the trailing stop, the cell's pair), useVolExit, path and cost."""
    X = {'inv': bool(x['inv']), 'slMult': float(x['slMult'])}
    X.update(EXIT_STYLES[x['exitStyle']])
    if X['useTrail']:
        X['trailActMul'], X['trailOffMul'] = trail_pair(pair, tf)
    X['useVolExit'] = bool(x['useVolExit'])
    X['path'] = path
    X['cost'] = cost
    return X


def inputs_of(p, pair, tf):
    """The Pine inputs that tfSet, fgfTf and exitStyle set for a setting (the columns INPUT_NAMES)."""
    out = dict(enabled(p['tfSet'], tf))
    if p['dirSource'] == 'fgf':
        par, z1, z2, z3 = tf_set(p['fgfTf'])
    else:
        par = z1 = z2 = z3 = None
    st = EXIT_STYLES[p['exitStyle']]
    act, off = trail_pair(pair, tf) if st['useTrail'] else (None, None)
    out.update(fgfParentTf=par, fgfZTf1=z1, fgfZTf2=z2, fgfZTf3=z3, tpMult=st['tpMult'], useTrail=st['useTrail'],
               trailActMul=act, trailOffMul=off)
    return out


def floor_ok(min_trail_off_pct, pair):
    """Section 14: False when the row's smallest trailing offset (% of the entry price) is below the
    floor of the pair; NaN (no trailing stop, or no trade) is not below it."""
    v = min_trail_off_pct
    return not (v is not None and not (isinstance(v, float) and math.isnan(v)) and float(v) < FLOOR_PCT[pair])


def _typed(name, v, d, off_grid):
    ty = _DIM_TYPE[name]
    if ty is bool:
        if not (isinstance(v, (bool, np.bool_)) or (isinstance(v, (int, float)) and not isinstance(v, bool)
                                                       and v in (0, 1))):
            raise ValueError('%s: %r is not a boolean' % (name, v))
        v = bool(v)
    elif ty is float:
        if isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float, np.integer, np.floating)) \
                or not math.isfinite(v):
            raise ValueError('%s: %r is not a number' % (name, v))
        v = float(v)
    elif ty is int:
        if isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float, np.integer, np.floating)) \
                or not math.isfinite(v) or int(v) != v:
            raise ValueError('%s: %r is not an integer' % (name, v))
        v = int(v)
    elif name == 'fgfTf':
        if isinstance(v, bool) or not isinstance(v, (str, int, np.integer)) or not str(v).strip().isdigit() \
                or int(str(v)) <= 0:
            raise ValueError('fgfTf: %r is not a timeframe in minutes ("15", "60", "240")' % (v,))
        v = str(int(str(v)))
    else:
        if not isinstance(v, str):
            raise ValueError('%s: %r is not a text value' % (name, v))
    if v not in d['values']:
        if not (off_grid and (ty in (float, int) or name == 'fgfTf')):
            raise ValueError('%s: %r is not in the grid %r' % (name, v, d['values']))
        if name == 'minConfluence' and not 1 <= v <= 12:
            raise ValueError('minConfluence: %r is outside 1..12' % (v,))
    return v


def normalize(raw, tf, off_grid=False):
    """A setting of chart tf given as a mapping of p_ values (keys with or without 'p_'; None / NaN /
    missing = unused) -> the canonical dict over DIM_NAMES. dirMode with 'fgf' and fgfTf / fgfBandAtr /
    fgfLvMode with 'orig' are set to None whatever was given (they cannot change the result). tfSet on
    charts 1, 120, 240: None or 'all' -> None; 'ge' is refused on 120 / 240 (not in the grid; --off-grid
    runs it), and on chart 1 it IS 'all' (-> None). Raises ValueError for an unknown key, a missing used
    dimension, a value of the wrong type, or (unless off_grid) a value that is not in the grid. off_grid
    accepts other numbers (thresholds, confluence 1..12, band, stop) and other filter timeframes (in
    minutes); the text dimensions are always one of the grid's."""
    tf = str(tf)
    if tf not in TFS:
        raise ValueError('unknown chart %r' % (tf,))
    vals = {}
    for k, v in raw.items():
        k = k[2:] if isinstance(k, str) and k.startswith('p_') else k
        if k not in DIM_NAMES:
            raise ValueError('unknown dimension %r (one of %s)' % (k, ', '.join(DIM_NAMES)))
        if isinstance(v, float) and math.isnan(v):
            v = None
        vals[k] = v
    out = {}
    for d in DIMS:
        name = d['name']
        if name in UNUSED_WHEN:
            continue
        v = vals.get(name)
        if name == 'tfSet' and not has_tfset(tf):
            if v is None or v == 'all' or (v == 'ge' and tf == '1'):
                out[name] = None
                continue
            if v == 'ge' and off_grid:
                out[name] = 'ge'
                continue
            raise ValueError("tfSet %r on chart %s is not in the grid (only 'all' = null there; --off-grid runs 'ge')"
                             % (v, tf))
        if v is None:
            raise ValueError('dimension %r has no value' % name)
        out[name] = _typed(name, v, d, off_grid)
    for d in DIMS:
        name = d['name']
        if name not in UNUSED_WHEN:
            continue
        other, when = UNUSED_WHEN[name]
        if out[other] == when:
            out[name] = None
            continue
        v = vals.get(name)
        if v is None:
            raise ValueError('dimension %r has no value' % name)
        out[name] = _typed(name, v, d, off_grid)
    return {k: out[k] for k in DIM_NAMES}


_ROWS: dict = {}


def row_of(pair, tf, p):
    """The row number of a setting in a cell's grid file (grid(pair, tf) order; the same for both pairs),
    None when it is not a grid row."""
    tf = str(tf)
    if tf not in _ROWS:
        _ROWS[tf] = {key(q): i for i, q in enumerate(grid(pair, tf))}
    return _ROWS[tf].get(key(p))


def in_grid(pair, tf, p):
    return row_of(pair, tf, p) is not None


# ---------------------------------------------------------------------------------------------
# what a run must echo; the floor of the trailing distance
# ---------------------------------------------------------------------------------------------
def _same_val(a, b):
    """Equal and of the same type (True is not 1, 70 is not 70.0)."""
    return type(a) is type(b) and a == b


def _check_prepared(sp, Pp, pair, tf):
    """amvi.prepare ran the SIGNAL setting it was asked for, and nothing else: its resolved inputs are the
    script's (amvi.DEFAULTS, the filter's = fgf.DEFAULTS) with every value given, its window is the pair's,
    and the number of timeframes with a value on every window bar is the number of toggles that are on
    (the seconds timeframes have no data: na = off)."""
    Q = Pp['params']
    want = dict(amvi.DEFAULTS)
    want.update(sp)
    diff = {k: (Q.get(k), want.get(k)) for k in set(want) | set(Q) if not _same_val(Q.get(k), want.get(k))}
    n_on = sum(bool(sp[k]) for k in EN_KEYS)
    en = Pp.get('enCount')
    ok = (not diff and Pp['pair'] == pair and Pp['tf'] == str(tf) and (Pp['start'], Pp['end']) == tuple(amvi.WINDOWS[pair])
          and not Pp['injected'] and (en is None or bool((en == n_on).all())))
    if not ok:
        raise RuntimeError('amvi.prepare did not run the signal setting %r: %r (enabled %d, enCount %r)'
                           % (sp, diff, n_on, None if en is None else (int(en.min()), int(en.max()))))


def _check_run(X, Pp, R):
    """amvi.simulate ran the EXIT setting it was asked for, and nothing else: its resolved inputs (R['params'])
    are the prepared ones with every value given (amviTradeDir = inv)."""
    want = dict(Pp['params'])
    want.update(X)
    want['amviTradeDir'] = 'Inverted' if want['inv'] else 'Follow the filter'
    Q = R['params']
    if Q != want:
        diff = {k: (Q.get(k), want.get(k)) for k in set(want) | set(Q) if Q.get(k) != want.get(k)}
        raise RuntimeError('amvi.simulate did not run %r: %r' % (X, diff))


def cell_floor(pair, tf, Pp):
    """The trailing distance of the cell against the 1-minute noise floor: the 10th percentile over the
    window of ATR(14) / close (%), times trailOffMul, must be at least FLOOR_PCT[pair]; and d is the
    smallest ladder value that meets it (the table of section 14)."""
    atr = amvi._atr_window(Pp, ATR_LEN)
    p10 = float(np.nanpercentile(atr / Pp['close'] * 100.0, 10))
    act, off = trail_pair(pair, tf)
    d_min = next((d for d in TRAIL_LADDER if d * p10 >= FLOOR_PCT[pair]), None)
    return {'atr_len': ATR_LEN, 'p10_atr_pct': p10, 'trailActMul': act, 'trailOffMul': off,
            'dist_pct_at_p10': off * p10, 'floor_pct': FLOOR_PCT[pair], 'meets_floor': bool(off * p10 >= FLOOR_PCT[pair]),
            'smallest_d': d_min, 'table_ok': d_min == off}


# ---------------------------------------------------------------------------------------------
# one setting
# ---------------------------------------------------------------------------------------------
def one(pair, tf, p, path=PATH, cost=COST, off_grid=False, ltf_rule=LTF_RULE, cache=None):
    """The full summary (amvi.summary) of one setting, computed alone: its own amvi.prepare and one
    amvi.simulate. p: a mapping of p_ values (see normalize). ltf_rule: 'first' (every grid row) or 'last'
    (--ltf-last; not a grid dimension). cache: a dict that keeps the prepared inputs between calls of one
    process (tests)."""
    tf = str(tf)
    if ltf_rule not in ('first', 'last'):
        raise ValueError('ltfRule %r is not first / last' % (ltf_rule,))
    p = normalize(p, tf, off_grid)
    sig = {k: p[k] for k in SIGNAL_DIMS}
    x = {k: p[k] for k in EXIT_DIMS}
    sp = signal_params(sig, tf, ltf_rule)
    ck = (pair, tf, tuple(sorted(sp.items())))
    Pp = cache.get(ck) if cache is not None else None
    if Pp is None:
        Pp = amvi.prepare(pair, tf, sp)
        _check_prepared(sp, Pp, pair, tf)
        if cache is not None:
            cache[ck] = Pp
    X = exit_params(x, pair, tf, path, cost)
    R = amvi.simulate(Pp, X)
    _check_run(X, Pp, R)
    s = amvi.summary(Pp, R)
    out = dict(inputs_of(p, pair, tf))
    out['floor_ok'] = floor_ok(s['min_trail_off_pct'], pair)
    out.update(s)
    row = row_of(pair, tf, p)
    Q = Pp['params']
    if Q['dirSource'] == 'fgf':
        direction = {k: Q[k] for k in ('dirSource', 'fgfOn', 'fgfTf', 'fgfParentTf', 'fgfZTf1', 'fgfZTf2', 'fgfZTf3',
                                        'fgfBandAtr', 'fgfLvMode')}
    else:
        direction = {k: Q[k] for k in ('dirSource', 'dirMode', 'emaLen', 'dcLen', 'tradeDir', 'allowReverse')}
    out['setting'] = {'strategy': STRATEGY, 'pair': pair, 'tf': tf, 'path': path, 'cost': cost, 'ltfRule': Q['ltfRule'],
                      'p': p, 'in_grid': row is not None, 'row': row,
                      'enabled': {k: Q[k] for k in EN_KEYS}, 'direction': direction,
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
# arrays of a prepared input that simulate / summary / trades read; equal ones are kept once per cell
_ARRAYS = ('open', 'high', 'low', 'close', 't_open', 't_close', 'trigUp', 'trigDn', 'hotCount', 'avgAmvi')
_DROPPED = ('trigger', 'inRange', 'anyCross', 'dirUp', 'dirDn', 'enCount')     # never read after prepare


def _slim(Pp, pool):
    """Drop what simulate / summary / trades never read (_DROPPED), replace every array of a prepared input
    that equals one already seen in this cell by that one (the bars, hotCount per threshold and timeframe
    set, avgAmvi per timeframe set), and every view into a larger array (the bar files, the n + 1 count
    arrays) by a copy, so that the module caches can be dropped."""
    for k in _DROPPED:
        Pp[k] = None
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
        hk = (k, a.shape, a.dtype.str, hashlib.blake2b(c.view(np.uint8).data, digest_size=16).digest())
        b = by_hash.get(hk)
        if b is not None and np.array_equal(a, b, equal_nan=a.dtype.kind == 'f'):
            Pp[k] = b                            # a duplicate: not remembered by address (it may be freed now)
            continue
        b = c.copy() if a.base is not None else c
        by_hash[hk] = b
        by_ptr[pk] = (a, b)                      # keeps `a` alive: its address cannot be reused while the pool lives
        Pp[k] = b


def _distinct(P):
    """Number of distinct arrays kept for the prepared inputs of a cell, per name."""
    return {k: len(set(id(Pk[k]) for Pk in P.values())) for k in _ARRAYS}


def peak_rss_mb():
    """The peak resident memory of this process so far (MB; the forked workers are not included)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _release_memory():
    """Hand freed memory back to the system (pyarrow's pool and glibc keep freed buffers)."""
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


def _free_caches():
    """Every module cache: amvi's AMVI parts, v_T, counts, directions and chart ATR; the filter's bars, TDI
    series and filter series (slimmed prepared inputs hold their own arrays)."""
    amvi.clear_caches()
    for name in ('_BARS', '_DIR', '_FILTER'):
        c = getattr(fgf, name, None)
        if isinstance(c, dict):
            c.clear()
    _release_memory()


def _dir_key(sig):
    return tuple(repr(sig[k]) for k in ('dirSource', 'dirMode', 'fgfTf', 'fgfLvMode', 'fgfBandAtr'))


def prepare_cell(pair, tf, sig_idx=None, verbose=False, ltf_rule=LTF_RULE):
    """amvi.prepare once per SIGNAL setting of the cell (all, or those of sig_idx), the 1-minute sub-bars,
    ATR(14) and the collapse series once, the floor measurement, the kernel compiled. Returns the cell: P
    {signal index: prepared input}, the summary columns and timings."""
    tf = str(tf)
    S = signals(pair, tf)
    idx = list(range(len(S))) if sig_idx is None else [int(i) for i in sig_idx]
    t0 = time.time()
    c0 = time.process_time()
    P = {}
    pool = {}
    t_each = []
    # direction-major: the direction of a filter setting is computed once (amvi's direction cache holds 12)
    # and serves its 24 (12) trigger settings; fgf caches its filter series (timeframe x level mode) itself
    order = sorted(idx, key=lambda si: (_dir_key(S[si]), si))
    for si in order:
        sp = signal_params(S[si], tf, ltf_rule)
        t1 = time.time()
        Pp = amvi.prepare(pair, tf, sp)
        t_each.append(time.time() - t1)
        _check_prepared(sp, Pp, pair, tf)
        _slim(Pp, pool)
        P[si] = Pp
    del pool
    P = {si: P[si] for si in idx}
    p0 = P[idx[0]]
    for si, Pk in P.items():
        if (Pk['w0'], Pk['w1'], Pk['mid'], Pk['mid_j'], Pk['n']) != (p0['w0'], p0['w1'], p0['mid'], p0['mid_j'], p0['n']):
            raise ValueError('%s %s signal setting %d: window rows differ' % (pair, tf, si))
    t_sig = time.time() - t0
    t1 = time.time()
    atr = {ATR_LEN: np.array(amvi._atr_window(p0, ATR_LEN), copy=True)}   # a window copy of the chart's ATR(14)
    floor = cell_floor(pair, tf, p0)
    vcs = {}
    for Pk in P.values():
        Pk['atr_cache'] = atr                    # one ATR cache per cell (same bars, same window)
        a = Pk['avgAmvi']
        if id(a) not in vcs:
            vcs[id(a)] = amvi.vol_collapse(Pk, LOW_VOL)
        Pk['vc_cache'] = {LOW_VOL: vcs[id(a)]}  # its own dict: simulate may add other thresholds to it
    n_sub = 0
    if PATH == 'mag':
        sub = amvi.get_sub(p0)                   # built once, checked against the chart bars
        n_sub = len(sub[1])
        for Pk in P.values():
            Pk['sub'] = sub
    _free_caches()
    t_sub = time.time() - t1
    t2 = time.time()
    X0 = exit_params(EXITS[0], pair, tf)
    R0 = amvi.simulate(p0, X0)                   # compile / load the kernel
    _check_run(X0, p0, R0)
    s = amvi.summary(p0, R0)
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
            raise TypeError('amvi.summary field %r is not a scalar: %r' % (k, v))
    _release_memory()
    cell = dict(pair=pair, tf=tf, idx=idx, S=S, P=P, cols=cols, kinds=kinds, bars=int(p0['n']), n_sub=n_sub,
                floor=floor, prepares=len(idx), t_sig=t_sig, t_prep_each=t_each, t_sub=t_sub, t_jit=t_jit,
                t_prep=time.time() - t0, cpu_prep=time.process_time() - c0, ltf_rule=ltf_rule,
                n_vc=len(vcs))
    if verbose:
        print('  %s %s: %d chart bars, %d 1-minute bars; %d signal settings prepared in %.1fs (one amvi.prepare %.3f .. '
              '%.3fs, mean %.3fs), sub-bars + ATR + collapse %.1fs, kernel %.1fs; distinct arrays kept: %s'
              % (pair, tf, cell['bars'], n_sub, len(idx), t_sig, min(t_each), max(t_each), float(np.mean(t_each)),
                 t_sub, t_jit, ', '.join('%s %d' % kv for kv in _distinct(P).items())), flush=True)
        print('  trailing pair (trailActMul, trailOffMul) = (%g, %g): %g x ATR(14)/close at the 10th percentile '
              '(%.4f %%) = %.4f %% of price, floor %.2f %% (smallest d of the ladder meeting it: %s, the table\'s: %s); '
              'floor_ok per row = min_trail_off_pct not below the floor'
              % (floor['trailActMul'], floor['trailOffMul'], floor['trailOffMul'], floor['p10_atr_pct'],
                 floor['dist_pct_at_p10'], floor['floor_pct'], floor['smallest_d'], floor['table_ok']), flush=True)
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
        R = amvi.simulate(Pp, XP[i])
        _check_run(XP[i], Pp, R)
        s = amvi.summary(Pp, R)
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
    """The rows in grid order as an arrow table: p_<name> per dimension (null = None), the Pine inputs of
    the derived dimensions, floor_ok, then every summary field. Column types are fixed here (they do not
    depend on the values)."""
    pair, tf = cell['pair'], cell['tf']
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    G = grid(pair, tf, idx)
    vals = [r for si in idx for r in res[si]]
    if len(G) != len(vals):
        raise RuntimeError('grid and results differ in length')
    names, arrays = [], []
    for name in DIM_NAMES:
        names.append('p_' + name)
        arrays.append(pa.array([p[name] for p in G], type=_PA_TYPE[_DIM_TYPE[name]]))   # None -> null
    ins = [inputs_of(p, pair, tf) for p in G]
    for name, ty in INPUT_COLS:
        names.append(name)
        arrays.append(pa.array([q[name] for q in ins], type=_PA_TYPE[ty]))               # None -> null
    j_tr = cell['cols'].index('min_trail_off_pct')
    names.append('floor_ok')
    arrays.append(pa.array([floor_ok(v[j_tr], pair) for v in vals], type=pa.bool_()))
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


# The code that produces the rows of this process: amvi.py and fgf.py as they were when it imported them.
# A module edited while a long run is under way is not the code that ran, so the sha256 is taken here,
# once, and not when a file is written.
_SRC_SHA = {'amvi': _sha256(amvi.__file__), 'fgf': _sha256(fgf.__file__)}


def file_meta(pair, tf, n, floor=None):
    """What produced a cell's file (stored in the parquet's key-value metadata, key "calib")."""
    act, off = trail_pair(pair, tf)
    return {'strategy': STRATEGY, 'pair': pair, 'tf': str(tf), 'path': PATH, 'cost': COST, 'ltfRule': LTF_RULE,
            'settings': int(n), 'window': [int(v) for v in amvi.WINDOWS[pair]],
            'sizing': '10 % of equity (default_qty_type percent_of_equity, default_qty_value 10), capital 10000',
            'seconds_toggles': 'en1s .. en45s at the script default (true); no data: na = off',
            'tf_sets': {str(ts): enabled(ts, tf) for ts in tf_sets(tf)}, 'exit_styles': EXIT_STYLES,
            'trailActMul': act, 'trailOffMul': off, 'lowVolThreshold': LOW_VOL, 'floor_pct': FLOOR_PCT[pair],
            'floor': floor, 'amvi_sha256': _SRC_SHA['amvi'], 'fgf_sha256': _SRC_SHA['fgf']}


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
    """One (pair, tf) cell: prepare, simulate the grid, write the parquet (and DIMS). sig_idx: only those
    signal settings (tests; never written). Returns (DataFrame, info)."""
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
                floor=cell['floor'], distinct=_distinct(cell['P']), file=None)
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
    info['rows_floor_ok'] = int(df['floor_ok'].sum())
    info['rows_candidates'] = int(((df['h1_trades'] >= 30) & (df['h2_trades'] >= 30) & (df['h1r_pct'] > 0)
                                   & (df['h2r_pct'] > 0) & df['floor_ok']).sum())
    if verbose:
        w = max(info['workers'], 1)
        print('  %s %s done: %d rows%s | prep %.1fs, runs %.1fs with %d workers (%.2f worker-s, %.5fs per '
              'setting per worker, of which CPU %.5fs; workers busy %.0f%%), total %.1fs; load average %.2f; peak RSS '
              'of the parent %.0f MB'
              % (pair, tf, len(df), (' -> ' + info['file']) if info['file'] else ' (not written)', info['t_prep'],
                 info['t_run'], w, info['busy'], info['busy'] / max(info['settings'], 1),
                 info['cpu'] / max(info['settings'], 1), 100.0 * info['busy'] / max(info['t_run'] * w, 1e-9),
                 info['t_total'], os.getloadavg()[0], peak_rss_mb()), flush=True)
        print('  rows with floor_ok: %d of %d (trailing rows below the floor: %d); rows with zero_qty > 0: %d; rows '
              'with at least 30 trades in each half: %d, of which positive in both fair halves (floor_ok): %d'
              % (info['rows_floor_ok'], len(df), len(df) - info['rows_floor_ok'], info['rows_zero_qty'],
                 info['rows_30_trades_each_half'], info['rows_candidates']), flush=True)
    _G.clear()
    return df, info


def estimate_cell(pair, tf, workers=MAX_WORKERS, per_signal=4, seed=20261127, verbose=True):
    """Estimated time of the full cell from ONE process: the real preparation, then per_signal random exit
    settings of every signal setting timed one by one; run time = sum over the signal settings of (mean
    sampled time x 48) / workers. Two estimates: from the wall clock (the machine as loaded as it is now)
    and from this process' CPU time (the 3 workers each having a free CPU). Writes nothing."""
    tf = str(tf)
    cell = prepare_cell(pair, tf, None, verbose)
    rng = np.random.default_rng(seed)
    XP = [exit_params(x, pair, tf) for x in EXITS]
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
        for i in rng.choice(len(XP), size=min(per_signal, len(XP)), replace=False):
            t = time.time()
            c = time.process_time()
            R = amvi.simulate(Pp, XP[int(i)])
            _check_run(XP[int(i)], Pp, R)
            sm = amvi.summary(Pp, R)
            tt.append(time.time() - t)
            cc.append(time.process_time() - c)
            n_thin += sm['h1_trades'] < 30 or sm['h2_trades'] < 30
        t_single += float(np.mean(tt)) * len(XP)
        c_single += float(np.mean(cc)) * len(XP)
        worst = max(worst, max(tt))
        n_s += len(tt)
    n_all = n_settings(pair, tf)
    w = max(workers, 1)
    est = dict(pair=pair, tf=tf, bars=cell['bars'], n_sub=cell['n_sub'], settings=n_all, sampled=n_s,
               t_prep=cell['t_prep'], prepares=cell['prepares'], t_prepare_mean=float(np.mean(cell['t_prep_each'])),
               t_prepare_max=float(np.max(cell['t_prep_each'])), per_setting=t_single / n_all, slowest=worst,
               single_process_run=t_single, workers=workers, est_run=t_single / w,
               est_total=cell['t_prep'] + t_single / w, cpu_prep=cell['cpu_prep'], cpu_per_setting=c_single / n_all,
               est_total_free_cpus=cell['cpu_prep'] + c_single / w,
               sampled_under_30_trades_in_a_half=int(n_thin), t_sample=time.time() - t0, load1=os.getloadavg()[0],
               peak_rss_mb=peak_rss_mb())
    if verbose:
        print('  %s %s estimate: prep %.1fs (%d prepares, %.3fs each on average) + %d settings x %.5fs (slowest '
              'sampled %.4fs; %d sampled) / %d workers = %.1fs runs -> %.1fs total (%.2f min) at the present load '
              '(load average %.2f); by CPU time: prep %.1fs + %d x %.5fs / %d -> %.1fs (%.2f min) with a free CPU '
              'per worker; peak RSS so far %.0f MB'
              % (pair, tf, est['t_prep'], est['prepares'], est['t_prepare_mean'], n_all, est['per_setting'], worst, n_s,
                 workers, est['est_run'], est['est_total'], est['est_total'] / 60.0, est['load1'], est['cpu_prep'],
                 n_all, est['cpu_per_setting'], workers, est['est_total_free_cpus'], est['est_total_free_cpus'] / 60.0,
                 est['peak_rss_mb']), flush=True)
        print('  of the %d sampled settings: %d with fewer than 30 trades in a half' % (n_s, n_thin), flush=True)
    _G.clear()
    return est


# ---------------------------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------------------------
def _main_one(argv):
    ap = argparse.ArgumentParser(prog='calib_amvi.py --one', description='the full summary of one setting, as JSON')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tf', choices=TFS)
    ap.add_argument('p', help='JSON object of the p_ values of the setting')
    ap.add_argument('--path', choices=('tv', 'mag'), default=PATH)
    ap.add_argument('--cost', choices=tuple(amvi.COSTS), default=COST)
    ap.add_argument('--ltf-last', action='store_true',
                    help="ltfRule 'last' (lower timeframes read as on a live bar, A2) instead of the grid's 'first'")
    ap.add_argument('--off-grid', action='store_true', help='accept values that are not in the grid')
    a = ap.parse_args(argv)
    try:
        raw = json.loads(a.p)
        if not isinstance(raw, dict):
            raise ValueError('the p_ values must be a JSON object')
        out = one(a.pair, a.tf, raw, a.path, a.cost, a.off_grid, 'last' if a.ltf_last else 'first')
    except ValueError as e:
        print('calib_amvi.py --one: %s' % e, file=sys.stderr)
        return 2
    print(json.dumps(out, default=_json_default))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--one' in argv:
        argv.remove('--one')
        return _main_one(argv)
    ap = argparse.ArgumentParser(description='AMVI Full MTF Strategy + FGF [Update 1] calibration grid (CALIB_SPEC.md)')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tfs', nargs='+')
    ap.add_argument('--workers', type=int, default=MAX_WORKERS)
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--estimate', action='store_true', help='time a sample in one process; write nothing')
    ap.add_argument('--per-signal', type=int, default=4, help='--estimate: sampled exit settings per signal setting')
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
            print('== calib %s %s %s: %d settings (%d signal settings x %d exit settings), path %s, cost %s, ltfRule '
                  '%s, trailing (%g, %g) =='
                  % (STRATEGY, a.pair, tf, n_settings(a.pair, tf), len(signals(a.pair, tf)), len(EXITS), PATH, COST,
                     LTF_RULE, *trail_pair(a.pair, tf)), flush=True)
            run_cell(a.pair, tf, workers, a.out_dir)
        _free_caches()
    print('all done in %.1fs' % (time.time() - t0), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
