"""calib_fgds.py: calibration grid of the FlashGold Direction Strategy [Update 1] (key fgds) per
pair and timeframe, with the direction (Normal / Inverted) as a calibrated input (CALIB_SPEC.md,
strategy "fgds"; the grid is section 14 of SPEC_fgds.md), on the canonical replica fgds.py
(prepare / simulate / summary; its signals ARE the direction filter: fgf.fgf_permissions).

Usage (python3 -I)
  calib_fgds.py PAIR TF [TF ...] [--workers 3] [--out-dir DIR]
      runs the full grid of every (PAIR, TF) cell and writes out/calib_fgds_<PAIR>_<TF>.parquet
      (one row per setting) and out/calib_fgds_dims.json (DIMS). PAIR in BTC, XAU; TF in 1, 5,
      15, 30, 60, 120, 240. Safe to re-run: the files are overwritten (written to a temporary
      name first). Prints the timing of every cell.
  calib_fgds.py --one PAIR TF '<json of p_ values>' [--path tv|mag] [--cost tv|ours|stress]
                [--script-sizing] [--off-grid]
      prints the full summary of ONE setting as one JSON document on stdout (default path mag,
      cost ours = the sweep's scoring). The JSON of p_ values is a row's p_ columns: keys with or
      without the "p_" prefix, null (or NaN) for an unused dimension. One control that is NOT a
      grid dimension (every grid row has the scale-free sizing):
        --script-sizing   the file's own sizing: dsMaxQty 50 and dsQtyStep 0.001 instead of the
                          grid's 1e9 and 0.000001.
      --off-grid also accepts numbers that are not in the grid (burst, band, stop) and another
      filter timeframe T (the parent / zones then move with it: T / T / 2T / 4T).
  calib_fgds.py --estimate PAIR TF [TF ...] [--workers 3] [--per-signal 4]
      times the cell's preparation and a random sample of settings in ONE process and prints the
      estimated time of the full cell; writes nothing.

The grid: 21,600 settings per cell, the same in every cell (SPEC_fgds.md section 14)
  signal   fgfTf {"15", "60", "240"} (moves the parent and the zones with it: fgfParentTf = T,
           fgfZTf1 / 2 / 3 = T / 2T / 4T, i.e. 15 / 30 / 60, 60 / 120 / 240, 240 / 480 / 960)
           x fgfBurstAtr {0.25, 0.5, 1.0} x fgfBandAtr {0.0, 0.25, 0.75} x fgfLvMode {"Entry
           price", "Signal close"} x fgfUseZones {True, False} = 108 filter settings
  exits    dsTrigger {"Zone start", "Signal confirmed", "New signal"} x inv {False, True}
           (= dsDirection "Follow the filter" / "Inverted", the script's own input) x dsZoneExit
           {True, False} x dsReverse {True, False} x dsSlAtr {0.5, 1.0, 2.0} x exitStyle {'tp3' =
           (dsTpR 3, no trail), 'tp1.5' = (1.5, no trail), 'none' = (0, no trail), 'trail' = (0,
           trailing stop with the cell's pair below)}
           = 192 per filter setting for "Zone start" and "Signal confirmed", and 48 for "New
           signal" (dsZoneExit has no effect there: None)
  "New signal" reads neither the band nor the level mode (fgfBandAtr / fgfLvMode only move the
           level and the zones; the signals and their direction do not depend on them), so its
           rows are listed once per (fgfTf, fgfBurstAtr, fgfUseZones) with fgfBandAtr, fgfLvMode
           and dsZoneExit None: 18 x 48 = 864 rows. They are run on the prepared input of the
           filter setting with the script's band 0.25 and level "Entry price" (their host, where
           they sit in the file), so their trig_zone_* / trig_conf_* fields are the counts of
           that prepared input (counts of P, not of the run).
  Total 108 x 192 + 18 x 48 = 20,736 + 864 = 21,600.
  filter   ON in every row: there is no filter-off dimension (fgfOn False = no trigger, no trade,
           in every cell); the script has no blocked-signal close.
  trailing exitStyle 'trail' = (dsTrActAtr, dsTrDstAtr) = (2d, d), ONE pair per cell, the table of
           SPEC_fgds.md section 14: d the smallest of {1, 1.75, 2.5, 3.5, 5, 6.5} for which
           d x ATR(14) / close at the 10th percentile of the window is at least the 1-minute noise
           floor (BTC 0.1 %, XAU 0.05 %):
                BTC 1 (13, 6.5) | BTC 5 (3.5, 1.75) | BTC 15 .. 240 (2, 1)
                XAU 1 (10, 5)   | XAU 5 (3.5, 1.75) | XAU 15 .. 240 (2, 1)
           Column floor_ok: True without the trailing stop, else whether the cell's distance meets
           the floor, measured again on the data at every run (True in all 14 cells).
Fixed for EVERY row (decisions of the orchestrator, not dimensions):
  scale-free sizing  dsMaxQty = 1e9 and dsQtyStep = 0.000001 (the file's own are 50 and 0.001),
                     so that neither the 50-unit cap nor the quantity grain decides a result.
                     Everything else of the sizing is the script's: Risk 0.5 % of equity over the
                     stop, margin cap on with 1 %, capital 10,000.
                     Limit: 0.000001 is the smallest step the Pine input accepts. An account with
                     equity x 0.5 % / stop distance < 0.000001 can still not size a trade: from
                     there on it trades less or not at all and its result is NOT scale-free (the
                     ruined accounts of the 1-minute charts). Such a row has zero_qty > 0 (a
                     column); the run prints how many there are.
Everything else stays at the script's defaults (fgfOn true, fgfLast "Until next signal", fgfCheck
"Tick", fgfAgainst on, both sides allowed, the signal's other inputs, dsSides "Both", dsExitMode
"ATR", dsAtrLen 14, dsTimeStop 0, Risk 0.5 %, margin cap on).
DEFAULT_P (= DEFAULT) is the default setting: the script's default inputs ("60", 0.5, 0.25, "Entry
price", zones on, "Zone start", normal, zone exit on, reverse on, 1.0, 'tp3') WITH the scale-free
sizing above (dsMaxQty 1e9, dsQtyStep 0.000001). It is NOT literally the published file's default
result: that one is `--one ... --script-sizing` on DEFAULT_P. It is one row of every cell.

SIGNALS (108) are the parameters of fgds.prepare (the filter inputs: one fgf.fgf_permissions call
each, 108 per cell; "New signal" needs 18 of them and reuses them). EXITS (240 = 192 + 48) those
of fgds.simulate; exits_for(signal) = the EXIT settings of a signal setting (192, or 240 on the 18
"New signal" hosts: band 0.25 and level "Entry price"). A dimension that cannot change the result
is listed once with the value None: fgfBandAtr, fgfLvMode and dsZoneExit with "New signal".
DIMS = the 11 dimensions (name, values, kind 'ordinal' / 'categorical'; extra keys: side,
default, unused_when); row i of a file is grid()[i] (the same in every cell). The direction
dimension is named inv.

Every setting is scored with path 'mag' (the exit bracket walked along the 1-minute sub-bars; on
chart "1" each bar is its own sub-bar) and cost 'ours'. Per cell: fgds.prepare runs ONCE per
signal setting (108 times, one filter call each; in the order of the filter's own series cache,
which is dropped between settings that do not share it), the prepared inputs are slimmed (the
diagnostic arrays and sigDir / newSig, which simulate does not read, are dropped; arrays equal
between signal settings are kept once; views into the bar files are replaced by window copies),
the 1-minute sub-bars and ATR(14) are built once, the module caches are dropped, the kernel is
compiled, and only then at most 3 workers are forked (copy-on-write); each simulates chunks of
exit settings of one prepared input (fgds.simulate + fgds.summary) and checks that the module ran
exactly the setting it was asked to run. Rows are assembled in grid order, so the file does not
depend on the worker count.

Output columns, in this order:
  p_<name>   one per dimension of DIMS, in DIMS order (p_fgfTf, p_fgfLvMode, p_dsTrigger and
             p_exitStyle are text, the others numbers / booleans; null = None)
  fgfParentTf, fgfZTf1, fgfZTf2, fgfZTf3, dsTpR, dsUseTrail, dsTrActAtr, dsTrDstAtr
             the Pine inputs that the two composite dimensions set (fgfTf, exitStyle);
             dsTrActAtr / dsTrDstAtr are the cell's pair on 'trail' rows and null elsewhere (the
             trailing stop is off there). They do not start with p_: not dimensions.
  floor_ok   see above
  then every field of fgds.summary (all scalars) in its own order: start, end, bars, trades,
  net_pct, pf, win_pct, max_dd_pct, max_dd_init_pct, long, short (REAL sides), raw_long,
  raw_short (trigger bars of the chosen trigger, normal frame), blocked_long, blocked_short
  (always 0), half1_pct, half2_pct, exposure, final_equity, exit_<kind> counts (sl, tp, trail,
  reverse, opp, zone, time, end), zero_length, h1r_pct, h2r_pct, h1_trades, h2_trades (the fair
  halves), avg_bars_held, costs, net_r, h1_r, h2_r (R = pnl / (stop distance x quantity)),
  trig_zone_buy, trig_zone_sell, trig_conf_buy, trig_conf_sell, trig_new_buy, trig_new_sell (the
  prepared input's trigger counts), taken_long, taken_short, orders_placed, orders_unfilled_end,
  zero_qty, qty_capped_max, qty_capped_margin, margin_over, max_notional_x.
Nothing else: no index, no pair / tf column (they are in the file name; the parquet's key-value
metadata "calib" holds strategy, pair, tf, path, cost, the number of settings, the window, the
fixed controls, the trailing pair and its floor measurement, and the sha256 of fgds.py and fgf.py
that produced the rows: the files as they were when this process imported them). pf is +inf
without a losing trade and NaN without trades; win_pct and avg_bars_held are NaN without trades.
--one prints the same non-p_ columns in the same order (Python's json: Infinity / NaN, null) plus
"setting" = {strategy, pair, tf, path, cost, p (the canonical p_ values), in_grid, row (its row
number in the grid file), sizing, dsMaxQty, dsQtyStep (as the module resolved them), filter (the
swept filter inputs as the module resolved them), cell_trail (the cell's pair)}.

Cost (measured 2026-11-26/27 on the shared 4-CPU machine, load average 4 - 8 from other jobs):
  preparation  one fgds.prepare = one fgf.fgf_permissions call: on BTC 1 0.32 s min, 0.39 s median,
               0.45 - 0.48 s mean, 2.2 s max (a call that builds a new filter series; the three bands
               of one series reuse it), so the 108 of BTC 1 take 47 - 54 s; XAU 1 23 s; BTC 5 13 s;
               every other cell 2 - 7 s. Peak memory of the preparation on BTC 1: 3.0 GB (one
               process); during the runs parent + 3 workers hold 1.4 GB together (sum of PSS).
  runs         one fgds.simulate + fgds.summary, path 'mag', one process: BTC 1 0.03 - 0.04 s, XAU 1
               0.02 s, every other cell 0.004 - 0.014 s.
  a full cell  with 3 workers (--estimate, 3 workers each with a free CPU / at load 8): BTC 1 4.6 /
               5.8 min (calib_tests_fgds.py test 5, from passes at load 4.5: 7.1 min), BTC 5 1.6 /
               1.9, BTC 15 .. 240 1.2 - 1.4, XAU 1 2.6 / 3.1, XAU 5 0.9 / 1.3, XAU 15 .. 240 0.5 - 0.8
               min. At load 8 the 3 workers get less than a CPU each: the production runs of BTC 240
               and XAU 240 took 3.0 and 1.2 min (2.3 and 2.0 times the estimate; XAU 240 again 0.6
               min at load 4.5).
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
import fgds  # noqa: E402  (imports fgf)
import fgf   # noqa: E402

STRATEGY = 'fgds'
MAX_WORKERS = 3
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
PATH = 'mag'             # the sweep's scoring: 1-minute fills ...
COST = 'ours'            # ... with our costs
CHUNK = 48               # exit settings per worker task

# ---------------------------------------------------------------------------------------------
# the grid (SPEC_fgds.md section 14)
# ---------------------------------------------------------------------------------------------
ZONE_START = "Zone start"                    # dsTrigger, the script default
SIG_CONF = "Signal confirmed"
NEW_SIG = "New signal"
LV_ENTRY = "Entry price"                     # fgfLvMode, the script default
LV_CLOSE = "Signal close"
FILTER_TFS = ('15', '60', '240')
BURSTS = (0.25, 0.5, 1.0)
BANDS = (0.0, 0.25, 0.75)
LV_MODES = (LV_ENTRY, LV_CLOSE)
USE_ZONES = (True, False)
TRIGGERS = (ZONE_START, SIG_CONF, NEW_SIG)
INVS = (False, True)
ZONE_EXITS = (True, False)
REVERSES = (True, False)
SL_ATRS = (0.5, 1.0, 2.0)
# exitStyle: the Pine inputs each member sets ('trail': plus the cell's dsTrActAtr / dsTrDstAtr)
EXIT_STYLES = {
    'tp3': {'dsTpR': 3.0, 'dsUseTrail': False},
    'tp1.5': {'dsTpR': 1.5, 'dsUseTrail': False},
    'none': {'dsTpR': 0.0, 'dsUseTrail': False},
    'trail': {'dsTpR': 0.0, 'dsUseTrail': True},
}
STYLES = tuple(EXIT_STYLES)
# the band and the level mode that "New signal" rows run with (the script defaults; they cannot
# change a "New signal" result): the 18 signal settings with these values host the "New signal" rows
NEW_HOST = {'fgfBandAtr': 0.25, 'fgfLvMode': LV_ENTRY}

# fixed for every row
SCALE_FREE = {'dsMaxQty': 1e9, 'dsQtyStep': 0.000001}     # the grid's sizing
SCRIPT_SIZING = {'dsMaxQty': 50.0, 'dsQtyStep': 0.001}    # the file's own (--one --script-sizing)

# trailing: one (dsTrActAtr, dsTrDstAtr) = (2d, d) per cell, the table of section 14
ATR_LEN = 14
TRAIL_LADDER = (1.0, 1.75, 2.5, 3.5, 5.0, 6.5)
FLOOR_PCT = {'BTC': 0.1, 'XAU': 0.05}                     # 1-minute noise floor, % of price
TRAIL_D = {('BTC', '1'): 6.5, ('BTC', '5'): 1.75, ('XAU', '1'): 5.0, ('XAU', '5'): 1.75}   # else 1.0

# name, values, kind as CALIB_SPEC.md asks; extra keys (as calib_hrd.py): side = 'signal' (a parameter
# of fgds.prepare) or 'exit' (of fgds.simulate), default = the script's default input, unused_when = the
# value of another dimension with which this one is listed once (its value is None)
_NEW_UNUSED = {'dsTrigger': NEW_SIG}
DIMS = [
    {'name': 'fgfTf', 'values': list(FILTER_TFS), 'kind': 'ordinal', 'side': 'signal', 'default': '60'},
    {'name': 'fgfBurstAtr', 'values': list(BURSTS), 'kind': 'ordinal', 'side': 'signal', 'default': 0.5},
    {'name': 'fgfBandAtr', 'values': list(BANDS), 'kind': 'ordinal', 'side': 'signal', 'default': 0.25,
     'unused_when': dict(_NEW_UNUSED)},
    {'name': 'fgfLvMode', 'values': list(LV_MODES), 'kind': 'categorical', 'side': 'signal', 'default': LV_ENTRY,
     'unused_when': dict(_NEW_UNUSED)},
    {'name': 'fgfUseZones', 'values': list(USE_ZONES), 'kind': 'categorical', 'side': 'signal', 'default': True},
    {'name': 'dsTrigger', 'values': list(TRIGGERS), 'kind': 'categorical', 'side': 'exit', 'default': ZONE_START},
    {'name': 'inv', 'values': list(INVS), 'kind': 'categorical', 'side': 'exit', 'default': False},
    {'name': 'dsZoneExit', 'values': list(ZONE_EXITS), 'kind': 'categorical', 'side': 'exit', 'default': True,
     'unused_when': dict(_NEW_UNUSED)},
    {'name': 'dsReverse', 'values': list(REVERSES), 'kind': 'categorical', 'side': 'exit', 'default': True},
    {'name': 'dsSlAtr', 'values': list(SL_ATRS), 'kind': 'ordinal', 'side': 'exit', 'default': 1.0},
    {'name': 'exitStyle', 'values': list(STYLES), 'kind': 'categorical', 'side': 'exit', 'default': 'tp3'},
]
DIM_NAMES = [d['name'] for d in DIMS]
SIGNAL_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'signal')
EXIT_DIMS = tuple(d['name'] for d in DIMS if d['side'] == 'exit')
UNUSED_WHEN = {d['name']: next(iter(d['unused_when'].items())) for d in DIMS if 'unused_when' in d}
DIM_DOC = {
    'fgfTf': 'Filter timeframe; the parent obedience timeframe and the zones 1 / 2 / 3 move with it (T, T / 2T / 4T)',
    'fgfBurstAtr': 'Burst threshold, ATR mult: how many FlashGold signals exist',
    'fgfBandAtr': 'No-trade band around the level, ATR mult (None: "New signal", which does not read it)',
    'fgfLvMode': 'Level = the signal\'s entry price or the signal candle\'s close (None: "New signal")',
    'fgfUseZones': 'Use the TDI trade-zone filter of the signals',
    'dsTrigger': 'Entry trigger: first bar of a zone / a signal\'s own zone reached / every new signal',
    'inv': 'Trade direction Inverted (dsDirection, the script\'s own input): a buy trigger opens a short',
    'dsZoneExit': 'Close when the entry zone ends (None: "New signal", where it has no effect)',
    'dsReverse': 'An opposite entry reverses the trade (else it only closes it)',
    'dsSlAtr': 'Stop loss, ATR(14) multiples',
    'exitStyle': "tp3 = 3 R target; tp1.5 = 1.5 R target; none = stop and the strategy's own exits only; trail = no "
                 "target, trailing stop with the cell's (dsTrActAtr, dsTrDstAtr) pair",
}
_DIM_TYPE = {'fgfTf': str, 'fgfBurstAtr': float, 'fgfBandAtr': float, 'fgfLvMode': str, 'fgfUseZones': bool,
             'dsTrigger': str, 'inv': bool, 'dsZoneExit': bool, 'dsReverse': bool, 'dsSlAtr': float,
             'exitStyle': str}
_PA_TYPE = {str: pa.string(), int: pa.int64(), float: pa.float64(), bool: pa.bool_()}
# the Pine inputs that the two composite dimensions set, written as columns that are not dimensions
INPUT_COLS = (('fgfParentTf', str), ('fgfZTf1', str), ('fgfZTf2', str), ('fgfZTf3', str), ('dsTpR', float),
              ('dsUseTrail', bool), ('dsTrActAtr', float), ('dsTrDstAtr', float))
INPUT_NAMES = tuple(k for k, _ in INPUT_COLS)

# The default setting: the script's default inputs (fgds.DEFAULTS; the Pine's input defaults) WITH the
# grid's scale-free sizing (dsMaxQty 1e9, dsQtyStep 0.000001).
DEFAULT_P = {d['name']: d['default'] for d in DIMS}
DEFAULT = DEFAULT_P

# SIGNAL settings: the parameters of fgds.prepare (the filter inputs), in DIMS order.
SIGNALS = [{'fgfTf': t, 'fgfBurstAtr': b, 'fgfBandAtr': bd, 'fgfLvMode': lv, 'fgfUseZones': z}
           for t in FILTER_TFS for b in BURSTS for bd in BANDS for lv in LV_MODES for z in USE_ZONES]
# EXIT settings: the parameters of fgds.simulate. "Zone start" / "Signal confirmed" (192, every signal
# setting), then "New signal" (48, the 18 hosts only; dsZoneExit None).
EXITS_MAIN = [{'dsTrigger': t, 'inv': i, 'dsZoneExit': ze, 'dsReverse': rv, 'dsSlAtr': s, 'exitStyle': es}
              for t in (ZONE_START, SIG_CONF) for i in INVS for ze in ZONE_EXITS for rv in REVERSES
              for s in SL_ATRS for es in STYLES]
EXITS_NEW = [{'dsTrigger': NEW_SIG, 'inv': i, 'dsZoneExit': None, 'dsReverse': rv, 'dsSlAtr': s, 'exitStyle': es}
             for i in INVS for rv in REVERSES for s in SL_ATRS for es in STYLES]
EXITS = EXITS_MAIN + EXITS_NEW
N_GRID = len(SIGNALS) * len(EXITS_MAIN) + sum(1 for s in SIGNALS if all(s[k] == v for k, v in NEW_HOST.items())) \
    * len(EXITS_NEW)                                       # 21,600


def is_new_host(sig):
    """True for the 18 signal settings that also carry the "New signal" rows."""
    return all(sig[k] == v for k, v in NEW_HOST.items())


def signals(pair=None, tf=None):
    """The SIGNAL settings of a cell (the same in every cell)."""
    return SIGNALS


def exits_for(sig, pair=None, tf=None):
    """The EXIT settings of one SIGNAL setting (the same in every cell): 192, plus the 48 "New
    signal" ones on a host."""
    return EXITS if is_new_host(sig) else EXITS_MAIN


def merge(sig, x):
    """One grid setting: every dimension of DIMS, in DIMS order. "New signal": the band and the level
    mode are None (the row is run on the host's prepared input)."""
    d = dict(sig)
    d.update(x)
    if d['dsTrigger'] == NEW_SIG:
        d['fgfBandAtr'] = None
        d['fgfLvMode'] = None
        d['dsZoneExit'] = None
    return {k: d[k] for k in DIM_NAMES}


def grid(pair=None, tf=None, sig_idx=None):
    """Every setting of a cell, in file order: for each SIGNAL setting, its EXIT settings."""
    idx = range(len(SIGNALS)) if sig_idx is None else sig_idx
    return [merge(SIGNALS[si], x) for si in idx for x in exits_for(SIGNALS[si])]


def n_settings(pair=None, tf=None):
    return N_GRID


def key(p):
    return tuple(p[k] for k in DIM_NAMES)


def tf_set(t):
    """fgfTf T -> (fgfParentTf, fgfZTf1, fgfZTf2, fgfZTf3) = (T, T, 2T, 4T)."""
    m = int(str(t))
    return str(m), str(m), str(2 * m), str(4 * m)


def trail_pair(pair, tf):
    """(dsTrActAtr, dsTrDstAtr) of the cell = (2d, d)."""
    d = TRAIL_D.get((pair, str(tf)), 1.0)
    return 2.0 * d, d


def signal_params(sig):
    """A SIGNAL setting as fgds.prepare params (everything else at the script's defaults). None (a
    "New signal" row) = the script's default value (the host's)."""
    par, z1, z2, z3 = tf_set(sig['fgfTf'])
    band = sig['fgfBandAtr'] if sig['fgfBandAtr'] is not None else NEW_HOST['fgfBandAtr']
    lv = sig['fgfLvMode'] if sig['fgfLvMode'] is not None else NEW_HOST['fgfLvMode']
    return {'fgfTf': str(sig['fgfTf']), 'fgfParentTf': par, 'fgfZTf1': z1, 'fgfZTf2': z2, 'fgfZTf3': z3,
            'fgfBurstAtr': float(sig['fgfBurstAtr']), 'fgfBandAtr': float(band), 'fgfLvMode': str(lv),
            'fgfUseZones': bool(sig['fgfUseZones'])}


def exit_params(x, pair, tf, path=PATH, cost=COST, script_sizing=False):
    """An EXIT setting as fgds.simulate params: the swept inputs, the two inputs of its exit style
    (and, with the trailing stop, the cell's pair), and the fixed controls, always given: the two
    sizing inputs. dsZoneExit None ("New signal") is left at the script's default (the module
    ignores it there)."""
    X = {'dsTrigger': str(x['dsTrigger']), 'inv': bool(x['inv']), 'dsReverse': bool(x['dsReverse']),
         'dsSlAtr': float(x['dsSlAtr']), 'path': path, 'cost': cost}
    if x['dsZoneExit'] is not None:
        X['dsZoneExit'] = bool(x['dsZoneExit'])
    X.update(EXIT_STYLES[x['exitStyle']])
    if X['dsUseTrail']:
        X['dsTrActAtr'], X['dsTrDstAtr'] = trail_pair(pair, tf)
    X.update(SCRIPT_SIZING if script_sizing else SCALE_FREE)
    return X


def inputs_of(p, pair, tf):
    """The Pine inputs that fgfTf and exitStyle set for a setting (the columns INPUT_NAMES);
    dsTrActAtr / dsTrDstAtr: the cell's pair with the trailing stop, None without it."""
    par, z1, z2, z3 = tf_set(p['fgfTf'])
    st = EXIT_STYLES[p['exitStyle']]
    act, dst = trail_pair(pair, tf) if st['dsUseTrail'] else (None, None)
    return {'fgfParentTf': par, 'fgfZTf1': z1, 'fgfZTf2': z2, 'fgfZTf3': z3, 'dsTpR': st['dsTpR'],
            'dsUseTrail': st['dsUseTrail'], 'dsTrActAtr': act, 'dsTrDstAtr': dst}


def _typed(name, v, d, off_grid):
    ty = _DIM_TYPE[name]
    if ty is bool:
        if not (isinstance(v, (bool, np.bool_)) or (isinstance(v, (int, float)) and v in (0, 1))):
            raise ValueError('%s: %r is not a boolean' % (name, v))
        v = bool(v)
    elif ty is float:
        if isinstance(v, bool) or not isinstance(v, (int, float, np.integer, np.floating)) or not math.isfinite(v):
            raise ValueError('%s: %r is not a number' % (name, v))
        v = float(v)
    elif name == 'fgfTf':
        if isinstance(v, bool) or not isinstance(v, (str, int, np.integer)) or not str(v).strip().isdigit() \
                or int(str(v)) <= 0:
            raise ValueError('fgfTf: %r is not a timeframe in minutes ("15", "60", "240")' % (v,))
        v = str(int(str(v)))
    else:
        if not isinstance(v, str):
            raise ValueError('%s: %r is not a text value' % (name, v))
    if v not in d['values']:
        if not (off_grid and (ty is float or name == 'fgfTf')):
            raise ValueError('%s: %r is not in the grid %r' % (name, v, d['values']))
    return v


def normalize(raw, off_grid=False):
    """A setting given as a mapping of p_ values (keys with or without 'p_'; None / NaN / missing =
    unused) -> the canonical dict over DIM_NAMES. fgfBandAtr, fgfLvMode and dsZoneExit with "New
    signal" are set to None whatever was given (they cannot change the result). Raises ValueError
    for an unknown key, a missing used dimension, a value of the wrong type, or (unless off_grid) a
    value that is not in the grid. off_grid accepts other numbers (burst, band, stop) and other
    filter timeframes (in minutes); the text dimensions and exitStyle are always one of the grid's."""
    vals = {}
    for k, v in raw.items():
        k = k[2:] if isinstance(k, str) and k.startswith('p_') else k
        if k not in DIM_NAMES:
            raise ValueError('unknown dimension %r (one of %s)' % (k, ', '.join(DIM_NAMES)))
        if isinstance(v, float) and math.isnan(v):
            v = None
        vals[k] = v
    out = {}
    # the switches first (dsTrigger comes after the dimensions it switches off)
    for d in DIMS:
        name = d['name']
        if name in UNUSED_WHEN:
            continue
        v = vals.get(name)
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
    """fgds.prepare ran the SIGNAL setting it was asked for, and nothing else: its resolved filter
    inputs are the filter's defaults with the given values (fgfOn true), its ds* defaults are the
    script's, its window the pair's."""
    want = fgf._params(dict(fgf.DEFAULTS, **sp))
    if Pp['fgfp'] != want or not Pp['fgfp']['fgfOn'] or Pp['sim'] != fgds.SIM_DEFAULTS or Pp['pair'] != pair \
            or Pp['tf'] != str(tf) or (Pp['start'], Pp['end']) != tuple(fgds.WINDOWS[pair]):
        diff = {k: (Pp['fgfp'].get(k), want.get(k)) for k in set(want) | set(Pp['fgfp'])
                if Pp['fgfp'].get(k) != want.get(k)}
        raise RuntimeError('fgds.prepare did not run the signal setting %r: %r' % (sp, diff))


def _check_run(X, Pp, R):
    """fgds.simulate ran the EXIT setting it was asked for, and nothing else: its resolved inputs
    (R['Q']) are the script's (the prepared ones) with every value given (dsDirection = inv)."""
    want = dict(Pp['sim'])
    want.update(X)
    want['dsDirection'] = 'Inverted' if want['inv'] else 'Follow the filter'
    if R['Q'] != want:
        diff = {k: (R['Q'].get(k), want.get(k)) for k in set(want) | set(R['Q']) if R['Q'].get(k) != want.get(k)}
        raise RuntimeError('fgds.simulate did not run %r: %r' % (X, diff))


def cell_floor(pair, tf, Pp):
    """The trailing distance of the cell against the 1-minute noise floor: the 10th percentile over
    the window of ATR(14) / close (%), times dsTrDstAtr, must be at least FLOOR_PCT[pair]."""
    atr = fgds.atr_window(Pp, ATR_LEN)
    p10 = float(np.nanpercentile(atr / Pp['c'] * 100.0, 10))
    act, dst = trail_pair(pair, tf)
    return {'atr_len': ATR_LEN, 'p10_atr_pct': p10, 'trActAtr': act, 'trDstAtr': dst,
            'dist_pct_at_p10': dst * p10, 'floor_pct': FLOOR_PCT[pair], 'floor_ok': bool(dst * p10 >= FLOOR_PCT[pair])}


def floor_ok(p, floor):
    """floor_ok of one setting: True without a trailing stop, else the cell's measurement."""
    return bool((not EXIT_STYLES[p['exitStyle']]['dsUseTrail']) or floor['floor_ok'])


# ---------------------------------------------------------------------------------------------
# one setting
# ---------------------------------------------------------------------------------------------
def one(pair, tf, p, path=PATH, cost=COST, off_grid=False, script_sizing=False, cache=None):
    """The full summary (fgds.summary) of one setting, computed alone: its own fgds.prepare and one
    fgds.simulate. p: a mapping of p_ values (see normalize). script_sizing: the file's own dsMaxQty
    50 and dsQtyStep 0.001 (not a grid dimension). cache: a dict that keeps the prepared inputs
    between calls of one process (tests)."""
    tf = str(tf)
    p = normalize(p, off_grid)
    sig = {k: p[k] for k in SIGNAL_DIMS}
    x = {k: p[k] for k in EXIT_DIMS}
    sp = signal_params(sig)
    ck = (pair, tf, tuple(sorted(sp.items())))
    Pp = cache.get(ck) if cache is not None else None
    if Pp is None:
        Pp = fgds.prepare(pair, tf, sp)
        if cache is not None:
            cache[ck] = Pp
    _check_prepared(sp, Pp, pair, tf)
    X = exit_params(x, pair, tf, path, cost, script_sizing)
    R = fgds.simulate(Pp, X)
    _check_run(X, Pp, R)
    s = fgds.summary(Pp, R)
    out = dict(inputs_of(p, pair, tf))
    out['floor_ok'] = floor_ok(p, cell_floor(pair, tf, Pp))
    out.update(s)
    row = row_of(pair, tf, p)
    fp = Pp['fgfp']
    out['setting'] = {'strategy': STRATEGY, 'pair': pair, 'tf': tf, 'path': path, 'cost': cost, 'p': p,
                      'in_grid': row is not None, 'row': row, 'sizing': 'script' if script_sizing else 'scale-free',
                      'dsMaxQty': R['Q']['dsMaxQty'], 'dsQtyStep': R['Q']['dsQtyStep'],
                      'filter': {k: fp[k] for k in ('fgfOn', 'fgfTf', 'fgfParentTf', 'fgfZTf1', 'fgfZTf2', 'fgfZTf3',
                                                    'fgfBurstAtr', 'fgfBandAtr', 'fgfLvMode', 'fgfUseZones')},
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
_ARRAYS = ('o', 'h', 'l', 'c', 't_open', 't_close', 'buyOk', 'sellOk', 'confBuy', 'confSell', 'buyEdge', 'sellEdge',
           'confEdgeB', 'confEdgeS', 'newBuy', 'newSell')
_DROPPED = ('diag', 'sigDir', 'newSig')        # never read by simulate / summary / trades


def _slim(Pp, pool):
    """Drop what simulate does not read (the diagnostics, sigDir, newSig), replace every array of a
    prepared input that equals one already seen in this cell by that one (the bars, the permissions
    and signals shared between filter settings), and every view into a larger array (the bar files,
    the filter frame) by a copy of the window, so that the module caches can be dropped."""
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
        hk = (k, a.shape, a.dtype.str, bool(a.flags.writeable),
              hashlib.blake2b(c.view(np.uint8).data, digest_size=16).digest())
        b = by_hash.get(hk)
        if b is not None and np.array_equal(a, b):
            Pp[k] = b                            # a duplicate: not remembered by address (it is freed now)
            continue
        b = c
        if a.base is not None:
            b = c.copy()
            b.setflags(write=bool(a.flags.writeable))        # same array type for the kernel as the module's own
        by_hash[hk] = b
        by_ptr[pk] = (a, b)                      # keeps `a` alive: its address cannot be reused while the pool lives
        Pp[k] = b


def _distinct(P):
    """Number of distinct arrays kept for the prepared inputs of a cell, per name."""
    return {k: len(set(id(Pk[k]) for Pk in P.values())) for k in _ARRAYS}


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
    """Every module cache: fgds' sub-bar tables and full ATR, the filter's bars, TDI series and
    filter series (slimmed prepared inputs hold their own arrays)."""
    fgds.clear_cache()
    for name in ('_BARS', '_DIR', '_FILTER'):
        c = getattr(fgf, name, None)
        if isinstance(c, dict):
            c.clear()
    _release_memory()


def _filter_key(sp):
    """The part of a signal setting that fgf's own filter-series cache (fgf._FILTER) depends on: all
    but the band (a chart-level input)."""
    return (sp['fgfTf'], sp['fgfBurstAtr'], sp['fgfLvMode'], sp['fgfUseZones'])


def prepare_cell(pair, tf, sig_idx=None, verbose=False):
    """fgds.prepare once per SIGNAL setting of the cell (all 108, or those of sig_idx; one
    fgf.fgf_permissions call each), the 1-minute sub-bars and ATR(14) once, the floor of the
    trailing distance, the kernel compiled. Returns the cell: P {signal index: prepared input},
    the summary columns and timings."""
    tf = str(tf)
    S = SIGNALS
    idx = list(range(len(S))) if sig_idx is None else [int(i) for i in sig_idx]
    t0 = time.time()
    c0 = time.process_time()
    P = {}
    pool = {}
    atr = None
    t_each = []
    # in the order of fgf's filter-series cache: the three bands of one filter series together, then
    # the series is dropped (on BTC "15" it is about 55 MB)
    order = sorted(idx, key=lambda si: (_filter_key(signal_params(S[si])), si))
    last = None
    for si in order:
        sp = signal_params(S[si])
        fk = _filter_key(sp)
        if last is not None and fk != last:
            fgf._FILTER.clear()
        last = fk
        t1 = time.time()
        Pp = fgds.prepare(pair, tf, sp)
        t_each.append(time.time() - t1)
        _check_prepared(sp, Pp, pair, tf)
        _slim(Pp, pool)
        if atr is None:
            a = Pp['atr'][ATR_LEN]
            atr = {ATR_LEN: np.ascontiguousarray(a).copy() if a.base is not None else a}
        Pp['atr'] = atr                            # one ATR cache per cell (same bars, same window)
        P[si] = Pp
    del pool
    P = {si: P[si] for si in idx}
    p0 = P[idx[0]]
    for si, Pk in P.items():
        if (Pk['w0'], Pk['w1'], Pk['mid'], Pk['mid_j'], Pk['n']) != (p0['w0'], p0['w1'], p0['mid'], p0['mid_j'], p0['n']):
            raise ValueError('%s %s signal setting %d: window rows differ' % (pair, tf, si))
    t_sig = time.time() - t0
    t1 = time.time()
    n_sub = 0
    if PATH == 'mag':
        sub = fgds.get_sub(p0)                     # built once, checked against the chart bars
        n_sub = len(sub[1])
        for Pk in P.values():
            Pk['sub'] = sub
    floor = cell_floor(pair, tf, p0)
    _free_caches()
    t_sub = time.time() - t1
    t2 = time.time()
    X0 = exit_params(EXITS[0], pair, tf)
    R0 = fgds.simulate(p0, X0)                     # compile / load the kernel
    _check_run(X0, p0, R0)
    s = fgds.summary(p0, R0)
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
            raise TypeError('fgds.summary field %r is not a scalar: %r' % (k, v))
    _release_memory()
    cell = dict(pair=pair, tf=tf, idx=idx, S=S, P=P, cols=cols, kinds=kinds, bars=int(p0['n']), n_sub=n_sub,
                floor=floor, prepares=len(idx), t_sig=t_sig, t_prep_each=t_each, t_sub=t_sub, t_jit=t_jit,
                t_prep=time.time() - t0, cpu_prep=time.process_time() - c0)
    if verbose:
        print('  %s %s: %d chart bars, %d 1-minute bars; %d signal settings prepared in %.1fs (one fgds.prepare = one '
              'filter call: %.2f .. %.2fs, mean %.2fs), sub-bars + ATR %.1fs, kernel %.1fs'
              % (pair, tf, cell['bars'], n_sub, len(idx), t_sig, min(t_each), max(t_each), float(np.mean(t_each)),
                 t_sub, t_jit), flush=True)
        print('  trailing pair (dsTrActAtr, dsTrDstAtr) = (%g, %g): %g x ATR(14)/close at the 10th percentile '
              '(%.4f %%) = %.4f %% of price, floor %.2f %%: floor_ok %s'
              % (floor['trActAtr'], floor['trDstAtr'], floor['trDstAtr'], floor['p10_atr_pct'],
                 floor['dist_pct_at_p10'], floor['floor_pct'], floor['floor_ok']), flush=True)
    return cell


def _work(task):
    si, i0, i1 = task
    t0 = time.time()
    c0 = time.process_time()
    Pp = _G['P'][si]
    XP = _G['XP'][si]
    cols = _G['cols']
    out = []
    for i in range(i0, i1):
        R = fgds.simulate(Pp, XP[i])
        _check_run(XP[i], Pp, R)
        s = fgds.summary(Pp, R)
        out.append(tuple(s[k] for k in cols))
    return si, i0, out, time.time() - t0, time.process_time() - c0


def run_prepared(cell, workers=MAX_WORKERS, sig_idx=None, chunk=CHUNK, verbose=False):
    """Simulate every exit setting of the prepared signal settings (all of the cell, or sig_idx).
    Returns (res {signal index: [summary tuple per exit setting]}, info)."""
    pair, tf = cell['pair'], cell['tf']
    idx = list(cell['idx']) if sig_idx is None else [int(i) for i in sig_idx]
    xp_main = [exit_params(x, pair, tf) for x in EXITS_MAIN]
    xp_all = xp_main + [exit_params(x, pair, tf) for x in EXITS_NEW]
    XP = {si: (xp_all if is_new_host(cell['S'][si]) else xp_main) for si in idx}
    _G.clear()
    _G.update(P=cell['P'], XP=XP, cols=cell['cols'])
    tasks = [(si, i0, min(i0 + chunk, len(XP[si]))) for si in idx for i0 in range(0, len(XP[si]), chunk)]
    total = sum(t[2] - t[1] for t in tasks)
    res = {si: [None] * len(XP[si]) for si in idx}
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
    """The rows in grid order as an arrow table: p_<name> per dimension (null = None), the Pine inputs
    of the composite dimensions, floor_ok, then every summary field. Column types are fixed here
    (they do not depend on the values)."""
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


# The code that produces the rows of this process: fgds.py and fgf.py as they were when it imported
# them. A module edited while a long run is under way is not the code that ran, so the sha256 is taken
# here, once, and not when a file is written.
_SRC_SHA = {'fgds': _sha256(fgds.__file__), 'fgf': _sha256(fgf.__file__)}


def file_meta(pair, tf, n, floor=None):
    """What produced a cell's file (stored in the parquet's key-value metadata, key "calib")."""
    act, dst = trail_pair(pair, tf)
    return {'strategy': STRATEGY, 'pair': pair, 'tf': str(tf), 'path': PATH, 'cost': COST, 'settings': int(n),
            'window': [int(v) for v in fgds.WINDOWS[pair]], 'dsMaxQty': SCALE_FREE['dsMaxQty'],
            'dsQtyStep': SCALE_FREE['dsQtyStep'], 'fgfOn': True, 'dsTrActAtr': act, 'dsTrDstAtr': dst,
            'exit_styles': EXIT_STYLES, 'new_signal_host': NEW_HOST, 'floor': floor,
            'fgds_sha256': _SRC_SHA['fgds'], 'fgf_sha256': _SRC_SHA['fgf']}


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
                floor=cell['floor'], distinct=_distinct(cell['P']), file=None)
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
    info['rows_margin_capped_over_1pct'] = int((df['qty_capped_margin'] > 0.01 * df['trades']).sum())
    if verbose:
        w = max(info['workers'], 1)
        print('  %s %s done: %d rows%s | prep %.1fs, runs %.1fs with %d workers (%.2f worker-s, %.5fs per '
              'setting per worker, of which CPU %.5fs; workers busy %.0f%%), total %.1fs; load average %.2f'
              % (pair, tf, len(df), (' -> ' + info['file']) if info['file'] else ' (not written)', info['t_prep'],
                 info['t_run'], w, info['busy'], info['busy'] / max(info['settings'], 1),
                 info['cpu'] / max(info['settings'], 1), 100.0 * info['busy'] / max(info['t_run'] * w, 1e-9),
                 info['t_total'], os.getloadavg()[0]), flush=True)
        print('  rows with floor_ok: %d of %d; rows with a quantity floored to zero (zero_qty > 0: an account too '
              'small for the 0.000001 step): %d; rows with qty_capped_margin above 1 %% of their trades (flagged by '
              'SPEC_fgds section 9): %d; rows with at least 30 trades in each half: %d'
              % (info['rows_floor_ok'], len(df), info['rows_zero_qty'], info['rows_margin_capped_over_1pct'],
                 info['rows_30_trades_each_half']), flush=True)
    _G.clear()
    return df, info


def estimate_cell(pair, tf, workers=MAX_WORKERS, per_signal=4, seed=20261126, verbose=True):
    """Estimated time of the full cell from ONE process: the real preparation, then per_signal random
    exit settings of every signal setting timed one by one; run time = sum over the signal settings
    of (mean sampled time x its number of exit settings) / workers. Two estimates: from the wall
    clock (the machine as loaded as it is now) and from this process' CPU time (the 3 workers
    each having a free CPU). Writes nothing."""
    tf = str(tf)
    cell = prepare_cell(pair, tf, None, verbose)
    rng = np.random.default_rng(seed)
    xp_main = [exit_params(x, pair, tf) for x in EXITS_MAIN]
    xp_all = xp_main + [exit_params(x, pair, tf) for x in EXITS_NEW]
    t_single = 0.0
    c_single = 0.0
    worst = 0.0
    n_s = 0
    n_zero = 0
    n_thin = 0
    t0 = time.time()
    for si in cell['idx']:
        XP = xp_all if is_new_host(cell['S'][si]) else xp_main
        Pp = cell['P'][si]
        tt = []
        cc = []
        for i in rng.choice(len(XP), size=min(per_signal, len(XP)), replace=False):
            t = time.time()
            c = time.process_time()
            R = fgds.simulate(Pp, XP[int(i)])
            _check_run(XP[int(i)], Pp, R)
            sm = fgds.summary(Pp, R)
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
               t_prep=cell['t_prep'], prepares=cell['prepares'], t_prepare_mean=float(np.mean(cell['t_prep_each'])),
               t_prepare_max=float(np.max(cell['t_prep_each'])), per_setting=t_single / n_all, slowest=worst,
               single_process_run=t_single, workers=workers, est_run=t_single / w,
               est_total=cell['t_prep'] + t_single / w, cpu_prep=cell['cpu_prep'], cpu_per_setting=c_single / n_all,
               est_total_free_cpus=cell['cpu_prep'] + c_single / w,
               sampled_zero_qty=int(n_zero), sampled_under_30_trades_in_a_half=int(n_thin),
               t_sample=time.time() - t0, load1=os.getloadavg()[0])
    if verbose:
        print('  %s %s estimate: prep %.1fs (%d prepares, %.2fs each on average) + %d settings x %.5fs (slowest '
              'sampled %.4fs; %d sampled) / %d workers = %.1fs runs -> %.1fs total (%.2f min) at the present load '
              '(load average %.2f); by CPU time: prep %.1fs + %d x %.5fs / %d -> %.1fs (%.2f min) with a free CPU '
              'per worker'
              % (pair, tf, est['t_prep'], est['prepares'], est['t_prepare_mean'], n_all, est['per_setting'], worst, n_s,
                 workers, est['est_run'], est['est_total'], est['est_total'] / 60.0, est['load1'], est['cpu_prep'],
                 n_all, est['cpu_per_setting'], workers, est['est_total_free_cpus'], est['est_total_free_cpus'] / 60.0),
              flush=True)
        print('  of the %d sampled settings: %d with a quantity floored to zero (zero_qty > 0), %d with fewer than '
              '30 trades in a half' % (n_s, n_zero, n_thin), flush=True)
    return est


# ---------------------------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------------------------
def _main_one(argv):
    ap = argparse.ArgumentParser(prog='calib_fgds.py --one', description='the full summary of one setting, as JSON')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tf', choices=TFS)
    ap.add_argument('p', help='JSON object of the p_ values of the setting')
    ap.add_argument('--path', choices=('tv', 'mag'), default=PATH)
    ap.add_argument('--cost', choices=tuple(fgds.COSTS), default=COST)
    ap.add_argument('--script-sizing', action='store_true',
                    help="the file's own dsMaxQty 50 and dsQtyStep 0.001 instead of the grid's scale-free sizing")
    ap.add_argument('--off-grid', action='store_true', help='accept values that are not in the grid')
    a = ap.parse_args(argv)
    try:
        raw = json.loads(a.p)
        if not isinstance(raw, dict):
            raise ValueError('the p_ values must be a JSON object')
        out = one(a.pair, a.tf, raw, a.path, a.cost, a.off_grid, a.script_sizing)
    except ValueError as e:
        print('calib_fgds.py --one: %s' % e, file=sys.stderr)
        return 2
    print(json.dumps(out, default=_json_default))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--one' in argv:
        argv.remove('--one')
        return _main_one(argv)
    ap = argparse.ArgumentParser(description='FlashGold Direction Strategy [Update 1] calibration grid (CALIB_SPEC.md)')
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
            print('== calib %s %s %s: %d settings (%d signal settings x their exit settings), path %s, cost %s, '
                  'dsMaxQty %g, dsQtyStep %g, trailing (%g, %g) =='
                  % (STRATEGY, a.pair, tf, N_GRID, len(SIGNALS), PATH, COST, SCALE_FREE['dsMaxQty'],
                     SCALE_FREE['dsQtyStep'], *trail_pair(a.pair, tf)), flush=True)
            run_cell(a.pair, tf, workers, a.out_dir)
        _free_caches()
    print('all done in %.1fs' % (time.time() - t0), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
