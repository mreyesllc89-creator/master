"""calib_tests_amvi.py: tests of calib_amvi.py (CALIB_SPEC.md, strategy "amvi"; the grid is section 14
of SPEC_amvi.md with the orchestrator's decisions: ltfRule 'first' on every row and --one --ltf-last as a
control, the file's own 10 % sizing, one trailing pair per cell, column floor_ok from min_trail_off_pct).

Usage: python3 -I calib_tests_amvi.py [name filter ...] [--cells XAU:240,BTC:240] [--files-only]

  test_1_grid             the grid is the full product of section 14 (24,192 = 24 x 21 x 48 on charts 5 ..
                          60, 12,096 = 12 x 21 x 48 on 1, 120, 240), keys unique, DIMS / signals / EXITS
                          consistent; every setting of all 14 cells maps to the amvi params the spec means
                          (an independent mapping written here; the Pine's own input defaults read from
                          the two .pine files); both script defaults are grid rows; the trailing pair of
                          every cell = the table, and the table's 10th percentiles recomputed here from the
                          bar files; the dimensions listed once (None) cannot change a result (dirMode with
                          'fgf', the filter inputs with 'orig', trailing distances with the trailing stop
                          off); ltfRule cannot change chart "1" nor a 'ge' setting; normalize(); the files
                          hold the grid in order with the columns of the docstring; the file metadata names
                          the amvi.py / fgf.py the process imported
  test_2_default_rows     the default rows (fused file: dirSource 'fgf'; original: 'orig'), normal and
                          inverted, equal the saved default results of the module (out/inv_amvi_<PAIR>_<TF>.json
                          runs normal/on/mag/ours, inverted/on/mag/ours, normal/off/mag/ours,
                          inverted/off/mag/ours) through the command line on BTC 60 and XAU 240, plus tv /
                          script costs, and --ltf-last against runs_ltf_last; every saved run (runs and
                          runs_ltf_last) of all 14 cells through calib_amvi.one; the default rows of the sweep
                          against the saved runs and amvi.run called directly
  test_3_one_rows         30 random rows per cell recomputed one at a time through `calib_amvi.py --one` (a
                          new process each) equal the sweep rows (and echo the row number); the same rows
                          through amvi.run with this file's own mapping; --path / --cost; --ltf-last (=
                          amvi.run with ltfRule 'last'); --off-grid; bad input
  test_4_workers          XAU 240: 1 worker vs 3 workers identical (frames and file bytes); amvi.prepare runs
                          once per signal setting (252), fgf.fgf_permissions once per filter setting (18),
                          amvi.simulate once per row
  test_5_timing_btc1      BTC 1: the real preparation of the 252 signal settings and 3 passes of 8 whole signal
                          settings with 3 workers extrapolated to the full grid: under 45 minutes; and the
                          memory the parent and its 3 workers hold together (sum of PSS, sampled): under 4 GB
  test_6_row_consistency  what every row must satisfy whatever the data (counts add up, a switch that is
                          off leaves no trace, the trigger counts belong to the signal setting, floor_ok =
                          min_trail_off_pct not below the floor), every dimension changes results (tfSet on
                          an in-memory part of XAU 60), direction twins
  test_7_all_rows         EVERY row of the cells' files (not a sample) recomputed in this process:
                          amvi.prepare once per signal setting, amvi.simulate + amvi.summary per row, with this
                          file's own mapping; all values equal, and the input columns and floor_ok
  test_8_every_cell       every cell that has a file in out/: the file holds the grid in order, metadata, and
                          4 random rows of EVERY signal setting recomputed in this process
  test_9_other_cells      (added by the sceptic) the sweep path in memory on XAU 5, BTC 15 and XAU 1, the cells
                          whose rows the 240-minute files cannot check (other trailing pairs, tfSet all / ge in
                          one run, rows below the trailing floor): 16 (8) signal settings each, every row
                          recomputed with this file's own mapping, 1 worker = 3 workers, rows through --one

The cells of tests 1 (files), 3, 6 and 7 are --cells (default XAU 240 and BTC 240): the file
out/calib_amvi_<PAIR>_<TF>.parquet when it exists, else the cell is run here with 3 workers into
calib_tmp_amvi/w3/ (never into out/). Test 2 covers all 14 cells: the file when it exists, else only the two
default signal settings are run in memory (96 rows; --files-only skips those). At most 2 processes at a time,
except the sweep's own 3 workers. Prints PASS / FAIL per test; exit code 1 on a failure.
Note (pandas 3): string columns read from parquet have the 'str' dtype, whose missing values are NaN;
astype(str) keeps them missing and groupby drops missing keys, so every grouping here is on repr() of the
python values (None -> 'None').
"""
import gc
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import amvi  # noqa: E402
import fgf   # noqa: E402
import calib_amvi as C  # noqa: E402

OUT = os.path.join(W, 'out')
TMP = os.path.join(W, 'calib_tmp_amvi')
PINE = '/home/user/master/AMVI_Full_MTF_Strategy_FGF.pine'
PINE_ORIG = '/home/user/master/AMVI_Full_MTF_Strategy.pine'
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
INIT = 10000.0
WIN = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}
CELLS = [('XAU', '240'), ('BTC', '240')]
FILES_ONLY = False
MEM_LIMIT_MB = 4000        # test 5: parent + 3 workers on BTC 1 (the prompt: keep a BTC 1 run under 4 GB)
SUM_REQUIRED = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
                'exit_sl', 'exit_tp', 'exit_trail', 'exit_reverse', 'exit_vol', 'exit_time', 'exit_end', 'net_r',
                'h1_r', 'h2_r', 'min_trail_off_pct', 'triggers', 'trig_up', 'trig_dn', 'trig_none', 'zero_qty')


def _p(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# this file's own reading of the spec (independent of calib_amvi's lists and mappings)
# ---------------------------------------------------------------------------------------------
TR, CA, BO = "Trend (EMA)", "Candle", "Breakout (Donchian)"
EP, SCL = "Entry price", "Signal close"
SPEC_DIMS = ['highVolThreshold', 'minConfluence', 'tfSet', 'dirSource', 'dirMode', 'fgfTf', 'fgfBandAtr', 'fgfLvMode',
             'inv', 'slMult', 'exitStyle', 'useVolExit']
SPEC_KIND = dict(zip(SPEC_DIMS, ['ordinal', 'ordinal', 'categorical', 'categorical', 'categorical', 'ordinal', 'ordinal',
                                 'categorical', 'categorical', 'ordinal', 'categorical', 'categorical']))
SPEC_SIDE = dict(zip(SPEC_DIMS, ['signal'] * 8 + ['exit'] * 4))
SPEC_DEFAULT = dict(zip(SPEC_DIMS, (70.0, 3, 'all', 'fgf', TR, '60', 0.25, EP, False, 1.5, 'tp3', True)))
SPEC_VALUES = {'highVolThreshold': [50.0, 60.0, 70.0, 80.0], 'minConfluence': [1, 2, 3], 'tfSet': ['all', 'ge'],
               'dirSource': ['orig', 'fgf'], 'dirMode': [TR, CA, BO], 'fgfTf': ['15', '60', '240'],
               'fgfBandAtr': [0.0, 0.25, 0.75], 'fgfLvMode': [EP, SCL], 'inv': [False, True], 'slMult': [1.0, 1.5, 2.5],
               'exitStyle': ['tp3', 'tp1.5', 'none', 'trail'], 'useVolExit': [True, False]}
SPEC_UNUSED = {'dirMode': {'dirSource': 'fgf'}, 'fgfTf': {'dirSource': 'orig'}, 'fgfBandAtr': {'dirSource': 'orig'},
               'fgfLvMode': {'dirSource': 'orig'}}
NO_TFSET = ('1', '120', '240')                      # tfSet None ('all' only) on these charts
# section 14, dimension 11: exitStyle = (tpMult, useTrail)
STYLE = {'tp3': (3.0, False), 'tp1.5': (1.5, False), 'none': (0.0, False), 'trail': (0.0, True)}
# section 14, dimension 6: fgfTf T moves fgfParentTf = T and fgfZTf1 / 2 / 3 = T / 2T / 4T
TFSET = {'15': ('15', '15', '30', '60'), '60': ('60', '60', '120', '240'), '240': ('240', '240', '480', '960')}
# section 14, dimension 3: the toggles en1 en5 en15 en30 en60 en240 enD; 'ge' = at or above the chart's timeframe
EN = ('en1', 'en5', 'en15', 'en30', 'en60', 'en240', 'enD')
GE = {'5': (False, True, True, True, True, True, True), '15': (False, False, True, True, True, True, True),
      '30': (False, False, False, True, True, True, True), '60': (False, False, False, False, True, True, True)}
# section 14: (trailActMul, trailOffMul) per cell; the 10th percentile of ATR(14) / close in %, as printed there
T_TRAIL = {('BTC', '1'): (9.75, 6.5), ('BTC', '5'): (2.625, 1.75), ('XAU', '1'): (7.5, 5.0), ('XAU', '5'): (2.625, 1.75)}
T_P10 = {('BTC', '1'): 0.0157, ('BTC', '5'): 0.0574, ('BTC', '15'): 0.125, ('BTC', '30'): 0.198, ('BTC', '60'): 0.318,
         ('BTC', '120'): 0.512, ('BTC', '240'): 0.826, ('XAU', '1'): 0.0101, ('XAU', '5'): 0.0290,
         ('XAU', '15'): 0.0599, ('XAU', '30'): 0.094, ('XAU', '60'): 0.145, ('XAU', '120'): 0.203, ('XAU', '240'): 0.311}
T_LADDER = (1.0, 1.75, 2.5, 3.5, 5.0, 6.5)
T_FLOOR = {'BTC': 0.1, 'XAU': 0.05}
# the Pine's input defaults (AMVI_Full_MTF_Strategy_FGF.pine L70-119 and the filter block; the original's
# O53-58; SPEC_amvi section 3) and the replica controls
SCRIPT_DEFAULTS = dict(
    fastATRPeriod=14, slowATRPeriod=50, stdDevPeriod=20, candleRangePeriod=10, normalizationPeriod=200, noRepaint=True,
    aatrWeight=0.35, vrWeight=0.25, nsdWeight=0.25, acrWeight=0.15, highVolThreshold=70.0, minConfluence=3,
    en1s=True, en5s=True, en15s=True, en30s=True, en45s=True,
    en1=True, en5=True, en15=True, en30=True, en60=True, en240=True, enD=True,
    useDateRange=False, startTime=1577836800, endTime=4102358400,
    dirSource='fgf', dirMode=TR, emaLen=50, dcLen=20, ltfRule='first', start=None, end=None,
    amviTradeDir="Follow the filter", inv=False, exitAtrLen=14, slMult=1.5, tpMult=3.0, useTrail=False,
    trailActMul=1.5, trailOffMul=1.0, useVolExit=True, lowVolThreshold=30.0, maxBars=0,
    tradeDir="Both", allowReverse=True, revClose='void', path='tv', cost='tv',
    fgfOn=True, fgfTf="60", fgfLvMode=EP, fgfLast="Until next signal", fgfMinutes=60, fgfBars=1, fgfCheck="Tick",
    fgfBandAtr=0.25, fgfAgainst=True, fgfAllowBuy=True, fgfAllowSell=True,
    fgfSpreadPts=25.0, fgfEntryDistPts=50.0, fgfHoldBars=0, fgfHoldFavPts=5.0, fgfOnePerBar=True,
    fgfDistUnit="ATR", fgfBurstAtr=0.5, fgfEntryDistAtr=0.25, fgfHoldFavAtr=0.1, fgfBurstPts=172.0,
    fgfUseBurst=True, fgfAnyCombo=False, fgfDriftBars=60, fgfUseDrift=False,
    fgfUseZones=True, fgfParentTf="60", fgfRsiLen=14, fgfFastLen=2, fgfMinAligned=2, fgfFlatParent=False,
    fgfIgnoreNa=True, fgfHtfClosed=True,
    fgfUseZ1=True, fgfZTf1="60", fgfUseZ2=True, fgfZTf2="120", fgfUseZ3=True, fgfZTf3="240",
    fgfUseZ4=False, fgfZTf4="480", fgfUseZ5=False, fgfZTf5="1", fgfUseZ6=False, fgfZTf6="2")
REPLICA_CONTROLS = {'dirSource', 'ltfRule', 'start', 'end', 'inv', 'revClose', 'path', 'cost'}
ORIG_ONLY = {'dirMode', 'emaLen', 'dcLen', 'tradeDir', 'allowReverse'}
TIME_INPUTS = {'startTime': '2020-01-01T00:00:00', 'endTime': '2099-12-31T00:00:00'}


def spec_grid(tf):
    """SPEC_amvi.md section 14 on chart tf: trigger (threshold x confluence x timeframe set; the set is None
    on charts 1, 120, 240) x direction (orig x 3 modes, fgf x 3 timeframes x 3 bands x 2 levels) x inv x stop x
    exit style x collapse exit."""
    G = []
    sets = (None,) if tf in NO_TFSET else ('all', 'ge')
    dirs = [('orig', m, None, None, None) for m in (TR, CA, BO)] + \
        [('fgf', None, t, b, lv) for t in ('15', '60', '240') for b in (0.0, 0.25, 0.75) for lv in (EP, SCL)]
    for h in (50.0, 60.0, 70.0, 80.0):
        for mc in (1, 2, 3):
            for ts in sets:
                for d in dirs:
                    for inv in (False, True):
                        for sl in (1.0, 1.5, 2.5):
                            for es in ('tp3', 'tp1.5', 'none', 'trail'):
                                for ve in (True, False):
                                    G.append((h, mc, ts) + d + (inv, sl, es, ve))
    return G


def spec_default(tf, source='fgf'):
    p = dict(SPEC_DEFAULT)
    if source == 'fgf':
        p['dirMode'] = None
    else:
        p.update(dirSource='orig', fgfTf=None, fgfBandAtr=None, fgfLvMode=None)
    if tf in NO_TFSET:
        p['tfSet'] = None
    return p


def amvi_params(p, pair, tf, path='mag', cost='ours', ltf='first'):
    """A setting (dict over SPEC_DIMS) as the complete amvi param set, written from the spec and the
    orchestrator's decisions (ltfRule 'first' on every row; the script's own sizing). Unused (None): the
    script's default value."""
    q = dict(SCRIPT_DEFAULTS)
    q.update(highVolThreshold=p['highVolThreshold'], minConfluence=p['minConfluence'])
    if p['tfSet'] == 'ge':
        q.update(dict(zip(EN, GE[tf] if tf in GE else tuple(m >= int(tf) for m in (1, 5, 15, 30, 60, 240, 1440)))))
    q['dirSource'] = p['dirSource']
    if p['dirSource'] == 'orig':
        q['dirMode'] = p['dirMode']
    else:
        t = p['fgfTf']
        par, z1, z2, z3 = TFSET.get(t) or (t, t, str(2 * int(t)), str(4 * int(t)))
        q.update(fgfTf=t, fgfParentTf=par, fgfZTf1=z1, fgfZTf2=z2, fgfZTf3=z3, fgfBandAtr=p['fgfBandAtr'],
                 fgfLvMode=p['fgfLvMode'])
    q.update(inv=p['inv'], amviTradeDir='Inverted' if p['inv'] else 'Follow the filter', slMult=p['slMult'],
             useVolExit=p['useVolExit'], path=path, cost=cost, ltfRule=ltf)
    q['tpMult'], q['useTrail'] = STYLE[p['exitStyle']]
    if q['useTrail']:
        q['trailActMul'], q['trailOffMul'] = T_TRAIL.get((pair, tf), (1.5, 1.0))
    return q


def _split(q):
    """amvi params -> (prepare params, simulate params)."""
    return ({k: v for k, v in q.items() if k in amvi.PREP_KEYS}, {k: v for k, v in q.items() if k in amvi.SIM_KEYS})


def pine_inputs(path):
    """name -> (default, minval or None) of every `name = input.<type>(default, ...)` line of a Pine file."""
    out = {}
    rx = re.compile(r'^\s*(?:(?:var|varip)\s+)?(?:(?:int|float|bool|string)\s+)?([A-Za-z_]\w*)\s*=\s*'
                    r'input\.(int|float|bool|string|session|timeframe|time)\(\s*("[^"]*"|timestamp\("[^"]*"\)|[^,)\s]+)')
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = rx.match(line)
            if not m:
                continue
            name, ty, dv = m.groups()
            if ty == 'bool':
                v = {'true': True, 'false': False}[dv]
            elif ty == 'int':
                v = int(dv)
            elif ty == 'float':
                v = float(dv)
            elif ty == 'time':
                v = dv[len('timestamp("'):-2]
            else:
                v = dv.strip('"')
            mv = re.search(r'minval\s*=\s*([-0-9.eE]+)', line)
            out[name] = (v, float(mv.group(1)) if mv else None)
    return out


def inputs_here(p, pair, tf):
    """The Pine inputs that tfSet, fgfTf and exitStyle set (this file's reading of section 14)."""
    out = dict(zip(EN, GE[tf] if p['tfSet'] == 'ge' else (True,) * 7))
    if p['dirSource'] == 'fgf':
        par, z1, z2, z3 = TFSET[p['fgfTf']]
    else:
        par = z1 = z2 = z3 = None
    tp, tr = STYLE[p['exitStyle']]
    act, off = T_TRAIL.get((pair, tf), (1.5, 1.0)) if tr else (None, None)
    out.update(fgfParentTf=par, fgfZTf1=z1, fgfZTf2=z2, fgfZTf3=z3, tpMult=tp, useTrail=tr, trailActMul=act,
               trailOffMul=off)
    return out


def floor_here(v, pair):
    """Section 14: floor_ok False when min_trail_off_pct is below the pair's floor (NaN: not below)."""
    return not (v is not None and v == v and v < T_FLOOR[pair])


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def _same(a, b):
    """Exact equality; NaN equals NaN; None equals None (and NaN: a null float column reads as NaN)."""
    na = a is None or (isinstance(a, float) and a != a)
    nb = b is None or (isinstance(b, float) and b != b)
    if na or nb:
        return na and nb
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    if isinstance(a, (bool, np.bool_)) or isinstance(b, (bool, np.bool_)):
        return isinstance(a, (bool, np.bool_)) and isinstance(b, (bool, np.bool_)) and bool(a) == bool(b)
    fa, fb = float(a), float(b)
    return fa == fb


def _py(v):
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if math.isnan(v) else float(v)
    return v


def _pcols():
    return ['p_' + n for n in C.DIM_NAMES]


def _keys(df):
    """The p_ columns of a file as a list of key tuples (python values, None for unused)."""
    cols = [[_py(v) for v in df[c].tolist()] for c in _pcols()]
    return list(zip(*cols))


def _rescols(df):
    """Every column that is not a p_ column: the input columns, floor_ok and the summary fields."""
    return [c for c in df.columns if not c.startswith('p_')]


def _sumcols(df):
    return [c for c in df.columns if not c.startswith('p_') and c != 'floor_ok' and c not in C.INPUT_NAMES]


def _out_file(pair, tf):
    return os.path.join(OUT, 'calib_amvi_%s_%s.parquet' % (pair, tf))


def _fresh(path):
    """A scratch file is used only when it is newer than the runner and the replica."""
    return os.path.exists(path) and os.path.getmtime(path) > max(os.path.getmtime(os.path.join(W, 'calib_amvi.py')),
                                                                 os.path.getmtime(os.path.join(W, 'amvi.py')))


_DF = {}


def _cell_df(pair, tf):
    """(DataFrame, where): out/ when the cell's file exists, else calib_tmp_amvi/w3 (run here if needed)."""
    k = (pair, tf)
    if k not in _DF:
        f = _out_file(pair, tf)
        if os.path.exists(f):
            src = 'out/' + os.path.basename(f)
            if not _fresh(f):
                _p('  note: %s is older than calib_amvi.py or amvi.py' % src)
        else:
            d3 = os.path.join(TMP, 'w3')
            f = os.path.join(d3, 'calib_amvi_%s_%s.parquet' % (pair, tf))
            src = 'calib_tmp_amvi/w3/' + os.path.basename(f)
            if not _fresh(f):
                t0 = time.time()
                C.run_cell(pair, tf, workers=3, out_dir=d3, verbose=False)
                _p('  %s %s has no file in out/: run here with 3 workers into %s (%.1fs)' % (pair, tf, src, time.time() - t0))
                _free()
        _DF[k] = (pd.read_parquet(f), f, src)
    return _DF[k]


def _free():
    C._free_caches()
    C._G.clear()
    gc.collect()


def _default_sig_idx(tf):
    """Signal indices of the two script defaults (fused, original) in signals(tf)."""
    out = []
    for src in ('fgf', 'orig'):
        d = spec_default(tf, src)
        out.append(next(i for i, s in enumerate(C.signals(None, tf)) if all(s[k] == d[k] for k in C.SIGNAL_DIMS)))
    return out


def _run_summary(pair, tf, q):
    """amvi.run (prepare + simulate + summary in one call of the module)."""
    _, s = amvi.run(pair, tf, q)
    return s


def _cmp(row, ref, keys, tag, bad, limit=6):
    n = 0
    for k in keys:
        n += 1
        if not _same(_py(row[k]), _py(ref[k])):
            if len(bad) < limit:
                bad.append('%s.%s row %r ref %r' % (tag, k, row[k], ref[k]))
            else:
                bad.append('')
    return n


def _fmt_bad(bad):
    return 'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b))


def _own_p10(pair, tf):
    """The 10th percentile over the window of ATR(14) / close in %, computed here from the bar file with
    pandas (Wilder's average as an exponential mean of the true range; the window starts thousands of bars
    into the file, so its seed no longer matters)."""
    t = pq.read_table(os.path.join(W, 'data', '%s_%s.parquet' % (pair, tf)), columns=['high', 'low', 'close', 't_close'])
    h, l, c, tc = (t.column(k).to_numpy() for k in ('high', 'low', 'close', 't_close'))
    pc = np.concatenate(([np.nan], c[:-1]))
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1.0 / 14.0, adjust=False).mean().to_numpy()
    s0, e0 = WIN[pair]
    m = (tc >= s0) & (tc <= e0)
    w0 = int(np.argmax(m))
    return float(np.percentile(atr[m] / c[m] * 100.0, 10)), w0, int(m.sum())


def _sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


# ---------------------------------------------------------------------------------------------
# 1. the grid
# ---------------------------------------------------------------------------------------------
def test_1_grid():
    """(1) The grid is the full product of section 14, keys unique; DIMS, the signal and exit lists and the
    amvi params of every setting of the 14 cells are what the spec says; the trailing table and its floor;
    the dimensions listed once cannot change a result; normalize(); the files hold the grid."""
    ok = True
    # ---- the product, per chart
    parts = []
    for tf in TFS:
        S = spec_grid(tf)
        G = C.grid('BTC', tf)
        K = [C.key(p) for p in G]
        n = 24192 if tf not in NO_TFSET else 12096
        a = (len(S) == n == len(set(S)) and len(G) == n == len(set(K)) and K == S and C.n_settings('XAU', tf) == n
             and C.grid('XAU', tf) == G and G == [C.merge(s, x) for s in C.signals('BTC', tf) for x in C.exits_for()]
             and len(C.signals('BTC', tf)) == n // 48 and n == (24 if tf not in NO_TFSET else 12) * 21 * 48)
        ok &= a
        parts.append('%s %d %s' % (tf, len(G), 'ok' if a else 'WRONG'))
    _p('  spec product per chart (24 or 12 trigger settings x 21 direction settings x 48 exit settings) = the '
       'runner\'s grid, same order, keys unique, the same for BTC and XAU: %s' % ', '.join(parts))
    # ---- the two lists
    S5 = C.signals('BTC', '5')
    S1 = C.signals('BTC', '1')
    sk = [tuple(s[k] for k in C.SIGNAL_DIMS) for s in S5]
    xk = [tuple(x[k] for k in C.EXIT_DIMS) for x in C.EXITS]
    c = (len(sk) == 504 == len(set(sk)) and len(xk) == 48 == len(set(xk)) and len(S1) == 252
         and list(C.SIGNAL_DIMS) + list(C.EXIT_DIMS) == C.DIM_NAMES and list(C.SIGNAL_DIMS) == SPEC_DIMS[:8]
         and all(C.exits_for(s) is C.EXITS for s in S5) and all(s['tfSet'] is None for s in S1)
         and all(C.signals(None, t) == S1 for t in NO_TFSET) and all(C.signals(None, t) == S5 for t in GE)
         and len(C.DIRECTION_SETTINGS) == 21)
    _p('  signal settings %d unique on charts 5 .. 60 and %d on 1 / 120 / 240 (amvi.prepare params), exit settings '
       '%d unique (amvi.simulate params), the same 48 for every signal setting: %s' % (len(set(sk)), len(S1), len(set(xk)), c))
    ok &= c
    # ---- DIMS
    d_ok = [d['name'] for d in C.DIMS] == SPEC_DIMS and len(C.DIMS) == 12 and all(
        {'name', 'values', 'kind'} <= set(d) <= {'name', 'values', 'kind', 'side', 'default', 'unused_when', 'unused_on_charts'}
        and d['default'] == SPEC_DEFAULT[d['name']] and type(d['default']) is type(SPEC_DEFAULT[d['name']])
        and d['side'] == SPEC_SIDE[d['name']] and d.get('unused_when') == SPEC_UNUSED.get(d['name'])
        and d['kind'] == SPEC_KIND[d['name']] and d['values'] == SPEC_VALUES[d['name']]
        and [type(v) for v in d['values']] == [type(v) for v in SPEC_VALUES[d['name']]] for d in C.DIMS)
    d_ok &= C.DIMS[2].get('unused_on_charts') == list(NO_TFSET) and all('unused_on_charts' not in d for d in C.DIMS if d['name'] != 'tfSet')
    d_ok &= all(C.default_p(None, tf, src) == spec_default(tf, src) for tf in TFS for src in ('fgf', 'orig'))
    for tf in ('5', '240'):
        S = spec_grid(tf)
        for j, d in enumerate(C.DIMS):
            seen = set(k[j] for k in S if k[j] is not None)
            want = set(d['values']) if not (d['name'] == 'tfSet' and tf in NO_TFSET) else set()
            d_ok &= seen == want
    none_ok = True
    for tf in TFS:
        for k in spec_grid(tf)[::7]:
            none_ok &= ((k[4] is None) == (k[3] == 'fgf') and all((k[j] is None) == (k[3] == 'orig') for j in (5, 6, 7))
                        and (k[2] is None) == (tf in NO_TFSET) and all(k[j] is not None for j in (0, 1, 3, 8, 9, 10, 11)))
    dir_ok = (C.DIMS[8]['name'] == 'inv' and C.DIMS[8]['kind'] == 'categorical' and C.DIMS[8]['values'] == [False, True]
              and C.DIMS[3]['name'] == 'dirSource' and C.DIMS[3]['values'] == ['orig', 'fgf']
              and not any(d['name'] in ('fgfOn', 'filter', 'ltfRule') for d in C.DIMS))
    _p('  DIMS: %d dimensions %s; values, kinds, sides, defaults as specified: %s; None only for dirMode with fgf, '
       'fgfTf / fgfBandAtr / fgfLvMode with orig, tfSet on charts 1 / 120 / 240, and always there: %s; the direction '
       'dimension is named inv, the filter off / on dimension is dirSource, ltfRule is not a dimension: %s'
       % (len(C.DIMS), [d['name'] for d in C.DIMS], d_ok, none_ok, dir_ok))
    ok &= d_ok and none_ok and dir_ok
    try:
        json.dumps(C.DIMS)
    except Exception as e:      # noqa: BLE001
        ok = False
        _p('  DIMS is not JSON: %r' % (e,))
    # ---- the script defaults: this file's copy, the module's, the Pine's own input lines
    m_ok = amvi.DEFAULTS == SCRIPT_DEFAULTS
    if not m_ok:
        _p('  amvi.DEFAULTS differ from the script defaults written here: %r'
           % {k: (amvi.DEFAULTS.get(k), SCRIPT_DEFAULTS.get(k)) for k in set(amvi.DEFAULTS) | set(SCRIPT_DEFAULTS)
              if amvi.DEFAULTS.get(k) != SCRIPT_DEFAULTS.get(k)})
    pin = pine_inputs(PINE)
    pino = pine_inputs(PINE_ORIG)
    diff = {}
    missing = []
    for k, v in SCRIPT_DEFAULTS.items():
        if k in REPLICA_CONTROLS or k == 'inv':
            continue
        src = pino if k in ORIG_ONLY else pin
        if k not in src:
            missing.append(k)
            continue
        pv = src[k][0]
        if k in TIME_INPUTS:
            good = pv == TIME_INPUTS[k] and v == int(pd.Timestamp(pv, tz='UTC').timestamp())
        else:
            good = pv == v and isinstance(pv, bool) == isinstance(v, bool)
        if not good:
            diff[k] = (v, pv)
    for k in ORIG_ONLY:
        if k in pin:
            diff[k] = 'also in the fused file'
    pd_dims = {k: pin[k][0] for k in ('highVolThreshold', 'minConfluence', 'fgfTf', 'fgfBandAtr', 'fgfLvMode', 'slMult')}
    pd_dims.update(dirMode=pino['dirMode'][0], inv=pin['amviTradeDir'][0] == 'Inverted',
                   useVolExit=pin['useVolExit'][0], dirSource='fgf' if pin['fgfOn'][0] else None,
                   tfSet='all' if all(pin[e][0] for e in EN) else None,
                   exitStyle='tp3' if (pin['tpMult'][0], pin['useTrail'][0]) == STYLE['tp3'] else None)
    p_ok = (not diff and not missing and pd_dims == SPEC_DEFAULT
            and (pin['fgfParentTf'][0], pin['fgfZTf1'][0], pin['fgfZTf2'][0], pin['fgfZTf3'][0]) == TFSET[pin['fgfTf'][0]]
            and (pin['trailActMul'][0], pin['trailOffMul'][0]) == (1.5, 1.0) and pin['lowVolThreshold'][0] == 30.0
            and pin['maxBars'][0] == 0 and pino['minConfluence'][0] == pin['minConfluence'][0]
            and pino['highVolThreshold'][0] == pin['highVolThreshold'][0] and 'amviTradeDir' not in pino)
    q = open(PINE, encoding='utf-8').read()
    st_ok = bool(re.search(r'initial_capital\s*=\s*10000', q) and re.search(r'default_qty_type\s*=\s*strategy\.percent_of_equity', q)
                 and re.search(r'default_qty_value\s*=\s*10\b', q)) and amvi.QTY_FRAC == 0.10 and amvi.INITIAL_CAPITAL == INIT
    _p('  script defaults: amvi.DEFAULTS = the %d written here: %s; the Pine files\' own input lines (the fused file; '
       'dirMode / emaLen / dcLen / tradeDir / allowReverse from the original) give the same default for all of them '
       '(different: %s; not found: %s); the 12 dimensions\' Pine defaults = the fused default row (the default parent '
       '/ zones = the "60" set, the original\'s dirMode "Trend (EMA)"): %s; sizing 10 %% of equity, capital 10,000 '
       '(strategy() call = the module): %s'
       % (len(SCRIPT_DEFAULTS), m_ok, diff or 'none', missing or 'none', p_ok, st_ok))
    ok &= m_ok and p_ok and st_ok
    # ---- the trailing pair of every cell, and the table's 10th percentiles recomputed from the bar files
    t_ok = True
    parts = []
    for pair in PAIRS:
        for tf in TFS:
            act, off = T_TRAIL.get((pair, tf), (1.5, 1.0))
            p10, w0, n = _own_p10(pair, tf)
            d_small = next((x for x in T_LADDER if x * p10 >= T_FLOOR[pair]), None)
            tol = 0.0006 if T_P10[(pair, tf)] >= 0.06 else 0.00006        # the table prints 3 / 4 decimals
            c_ok = (C.trail_pair(pair, tf) == (act, off) and act == 1.5 * off and d_small == off
                    and abs(p10 - T_P10[(pair, tf)]) <= tol and off * p10 >= T_FLOOR[pair] and w0 > 1000
                    and C.FLOOR_PCT[pair] == T_FLOOR[pair])
            t_ok &= c_ok
            parts.append('%s %s %.4f%% x %g = %.4f%%%s' % (pair, tf, p10, off, off * p10, '' if c_ok else ' WRONG'))
    _p('  trailing pair (1.5 d, d) of every cell = the table of section 14, d = the smallest of %s with d x the 10th '
       'percentile of ATR(14)/close >= the floor (BTC 0.1 %%, XAU 0.05 %%), percentile recomputed here from the bar '
       'files and equal to the table\'s: %s' % (list(T_LADDER), t_ok))
    _p('    ' + '; '.join(parts))
    ok &= t_ok and tuple(C.TRAIL_LADDER) == T_LADDER
    # ---- floor_ok() itself, at and around both floors (no row of a 240-minute file is below the floor, so the
    # files of tests 3, 6 and 7 cannot show a wrong floor_ok; test 9 checks it on data where rows are below it)
    fv = ((0.0999, 'BTC', False), (0.1, 'BTC', True), (0.07, 'BTC', False), (0.07, 'XAU', True), (0.0499, 'XAU', False),
          (0.05, 'XAU', True), (float('nan'), 'BTC', True), (None, 'XAU', True), (np.float64(0.01), 'XAU', False),
          (np.float64('nan'), 'XAU', True), (2.0, 'BTC', True))
    fo_ok = all(isinstance(C.floor_ok(v, pr), bool) and C.floor_ok(v, pr) == w == floor_here(v, pr) for v, pr, w in fv)
    _p('  floor_ok(min_trail_off_pct, pair) at and around the floors (BTC 0.1 %%, XAU 0.05 %%; NaN / None = no trailing '
       'trade = True), %d cases: %s' % (len(fv), fo_ok))
    ok &= fo_ok
    # ---- the amvi params of every setting, all 14 cells
    n_bad = n_all = 0
    def_ok = True
    for pair in PAIRS:
        for tf in TFS:
            G = C.grid(pair, tf)
            K = [C.key(p) for p in G]
            for p in G:
                sp = C.signal_params({k: p[k] for k in C.SIGNAL_DIMS}, tf)
                xp = C.exit_params({k: p[k] for k in C.EXIT_DIMS}, pair, tf)
                eff = amvi._check(amvi._merge(amvi.DEFAULTS, dict(sp, **xp)))
                want = amvi_params(p, pair, tf)
                n_all += 1
                if eff != want or (set(sp) - amvi.PREP_KEYS) or (set(xp) - amvi.SIM_KEYS):
                    n_bad += 1
                    if n_bad <= 3:
                        _p('  MAPPING %s %s %r: %r' % (pair, tf, p, {k: (eff.get(k), want.get(k)) for k in set(want) | set(eff)
                                                                      if eff.get(k) != want.get(k)}))
            for src in ('fgf', 'orig'):
                d = spec_default(tf, src)
                sp = C.signal_params({k: d[k] for k in C.SIGNAL_DIMS}, tf)
                eff = amvi._check(amvi._merge(amvi.DEFAULTS, dict(sp, **C.exit_params({k: d[k] for k in C.EXIT_DIMS}, pair, tf))))
                want = dict(SCRIPT_DEFAULTS, path='mag', cost='ours')
                if src == 'orig':
                    want['dirSource'] = 'orig'
                def_ok &= K.count(C.key(d)) == 1 and eff == want
    def_ok &= C.PATH == 'mag' and C.COST == 'ours' and C.LTF_RULE == 'first'
    _p('  amvi params of all %d settings of the 14 cells (signal_params + exit_params, resolved by amvi._check) = the '
       'mapping written here (%d keys each; ltfRule first, the cell\'s trailing pair, tfSet\'s toggles, fgfTf with its '
       'parent / zones): %d different; signal params only prepare keys, exit params only simulate keys'
       % (n_all, len(SCRIPT_DEFAULTS), n_bad))
    _p('  both script defaults (fused file, original) are one row each of every cell; their params = the script '
       'defaults with path mag, cost ours (and dirSource orig): %s' % def_ok)
    ok &= n_bad == 0 and def_ok
    # ---- normalize: every grid row round-trips, as the file gives it (p_ prefix, NaN or None for unused)
    r_ok = True
    n_rt = n_g = 0
    for tf in ('60', '240'):
        G = C.grid(None, tf)
        n_g += len(G)
        n_rt += sum(C.normalize({'p_' + k: (float('nan') if v is None else v) for k, v in p.items()}, tf) == p
                    and C.normalize({k: v for k, v in p.items() if v is not None}, tf) == p for p in G)
    d60, d240 = spec_default('60'), spec_default('240')
    o60 = spec_default('60', 'orig')
    forced = C.normalize(dict(d60, dirMode=BO), '60')
    forced2 = C.normalize(dict(o60, fgfTf='240', fgfBandAtr=0.75, fgfLvMode=SCL), '60')
    forced3 = C.normalize(dict(d240, tfSet='all'), '240')
    forced4 = C.normalize(dict(d60, tfSet='ge'), '1')
    r_ok &= (n_rt == n_g and forced == d60 and forced2 == o60 and forced3 == d240 and forced4 == spec_default('1')
             and C.row_of('BTC', '240', d240) is not None and C.normalize(dict(d60, fgfTf=60, minConfluence=3.0), '60') == d60)
    refused = []
    for name, q, tf, og in (('fgf without a band', dict(d60, fgfBandAtr=None), '60', False),
                            ('orig without a mode', dict(o60, dirMode=None), '60', False),
                            ('tfSet missing on chart 60', dict(d60, tfSet=None), '60', False),
                            ('tfSet ge on chart 240', dict(d240, tfSet='ge'), '240', False),
                            ('threshold not in the grid', dict(d60, highVolThreshold=65.0), '60', False),
                            ('filter timeframe not in the grid', dict(d60, fgfTf='30'), '60', False),
                            ('confluence 13', dict(d60, minConfluence=13), '60', True),
                            ('unknown exit style', dict(d60, exitStyle='tp5'), '60', True),
                            ('unknown dirSource', dict(d60, dirSource='none'), '60', True),
                            ('fgfOn is not a dimension', dict(d60, fgfOn=False), '60', True),
                            ('ltfRule is not a dimension', dict(d60, ltfRule='last'), '60', True),
                            ('inv not a boolean', dict(d60, inv='yes'), '60', False),
                            ('confluence not an integer', dict(d60, minConfluence=2.5), '60', True)):
        try:
            C.normalize(q, tf, off_grid=og)
            refused.append((name, False))
        except ValueError:
            refused.append((name, True))
    kept = C.normalize(dict(d60, fgfTf='30', fgfBandAtr=0.5, highVolThreshold=65.0, minConfluence=4), '60', off_grid=True)
    kept2 = C.normalize(dict(d240, tfSet='ge'), '240', off_grid=True)
    r_ok &= (all(v for _, v in refused) and kept['fgfTf'] == '30' and C.row_of('BTC', '60', kept) is None
             and kept2['tfSet'] == 'ge' and C.row_of('BTC', '240', kept2) is None)
    _p('  normalize(): %d of %d grid rows (charts 60, 240) round-trip (p_ prefix, NaN / missing for unused); dirMode with '
       'fgf, the filter inputs with orig, tfSet all on 240 and ge on 1 become the grid\'s None; refused: %s; --off-grid '
       'keeps fgfTf "30", band 0.5, threshold 65, confluence 4, and tfSet ge on 240 (not grid rows): %s'
       % (n_rt, n_g, ', '.join('%s %s' % (n, 'yes' if v else 'NO') for n, v in refused), r_ok))
    ok &= r_ok
    # ---- on data: the dimensions listed once cannot change a result; ltfRule on chart 1 and with 'ge'
    rng = np.random.default_rng(20261127)
    cnt = dict(mode=0, filt=0, trail=0, ltf1=0, ltfge=0, ltfall=0)
    dif = dict(mode=0, filt=0, trail=0, ltf1=0, ltfge=0, ltfall=0)
    for pair, tf in CELLS + [('XAU', '15')]:
        sub = None
        sp_list = [amvi_params(dict(spec_default(tf, src), highVolThreshold=h, minConfluence=m), pair, tf)
                   for src in ('fgf', 'orig') for h, m in ((60.0, 2), (50.0, 1))]
        for q in sp_list:
            prep, sim = _split(q)
            P0 = amvi.prepare(pair, tf, prep)
            sub = sub or amvi.get_sub(P0)
            P0['sub'] = sub
            if prep['dirSource'] == 'fgf':
                alt = dict(prep, dirMode=rng.choice([CA, BO]).item())
                kk = 'mode'
            else:
                alt = dict(prep, fgfTf='240', fgfParentTf='240', fgfZTf1='240', fgfZTf2='480', fgfZTf3='960',
                           fgfBandAtr=0.75, fgfLvMode=SCL)
                kk = 'filt'
            P1 = amvi.prepare(pair, tf, alt)
            P1['sub'] = sub
            cnt[kk] += 1
            dif[kk] += not (np.array_equal(P0['trigUp'], P1['trigUp']) and np.array_equal(P0['trigDn'], P1['trigDn']))
            for es in ('tp3', 'none'):
                x = dict(sim, tpMult=STYLE[es][0])
                s0 = amvi.summary(P0, amvi.simulate(P0, x))
                s1 = amvi.summary(P1, amvi.simulate(P1, x))
                sa = amvi.summary(P0, amvi.simulate(P0, dict(x, trailActMul=9.75, trailOffMul=6.5)))
                sb = amvi.summary(P0, amvi.simulate(P0, dict(x, trailActMul=0.3, trailOffMul=0.1)))
                cnt[kk] += 1
                dif[kk] += not all(_same(s0[k], s1[k]) for k in s0)
                cnt['trail'] += 1
                dif['trail'] += not all(_same(s0[k], sa[k]) and _same(s0[k], sb[k]) for k in s0)
            if tf == '15':
                # ltfRule: with 'ge' no timeframe is lower than the chart: 'last' = 'first'; with 'all' it moves
                ge = dict(prep, **dict(zip(EN, GE['15'])))
                for base, kk2 in ((ge, 'ltfge'), (prep, 'ltfall')):
                    Pa = amvi.prepare(pair, tf, base)
                    Pb = amvi.prepare(pair, tf, dict(base, ltfRule='last'))
                    cnt[kk2] += 1
                    dif[kk2] += not (np.array_equal(Pa['trigUp'], Pb['trigUp']) and np.array_equal(Pa['trigDn'], Pb['trigDn']))
            del P0, P1
        _free()
    for pair in ('XAU',):
        for src in ('fgf', 'orig'):
            prep, _ = _split(amvi_params(dict(spec_default('1', src), highVolThreshold=60.0, minConfluence=2), pair, '1'))
            Pa = amvi.prepare(pair, '1', prep)
            Pb = amvi.prepare(pair, '1', dict(prep, ltfRule='last'))
            cnt['ltf1'] += 1
            dif['ltf1'] += not (np.array_equal(Pa['trigUp'], Pb['trigUp']) and np.array_equal(Pa['trigDn'], Pb['trigDn'])
                                and np.array_equal(Pa['hotCount'], Pb['hotCount']) and np.array_equal(Pa['avgAmvi'], Pb['avgAmvi'], equal_nan=True))
            del Pa, Pb
        _free()
    u_ok = (all(dif[k] == 0 for k in ('mode', 'filt', 'trail', 'ltf1', 'ltfge')) and dif['ltfall'] > 0
            and all(v > 0 for v in cnt.values()))
    _p('  on data (%s, XAU 15, XAU 1): settings with a different result / settings tried: another dirMode with fgf %d/%d, '
       'other filter inputs with orig %d/%d (trigger arrays and summaries), trailing distances with the trailing stop '
       'off %d/%d; ltfRule last vs first: chart 1 %d/%d, tfSet ge on chart 15 %d/%d (no timeframe below the chart), '
       'tfSet all on chart 15 %d/%d (expected to move): %s'
       % (', '.join('%s %s' % c for c in CELLS), dif['mode'], cnt['mode'], dif['filt'], cnt['filt'], dif['trail'],
          cnt['trail'], dif['ltf1'], cnt['ltf1'], dif['ltfge'], cnt['ltfge'], dif['ltfall'], cnt['ltfall'], u_ok))
    ok &= u_ok
    # ---- the files
    fd = os.path.join(OUT, 'calib_amvi_dims.json')
    if os.path.exists(fd):
        same = json.load(open(fd)) == C.DIMS
        _p('  out/calib_amvi_dims.json equals DIMS: %s' % same)
        ok &= same
    else:
        _p('  out/calib_amvi_dims.json: not written yet')
    # ---- the provenance written into a file is the code this process imported
    o_sha = C._sha256
    C._sha256 = lambda path: 'read again at write time'
    try:
        m2 = C.file_meta('XAU', '240', 12096)
    finally:
        C._sha256 = o_sha
    prov = (m2['amvi_sha256'] == C._SRC_SHA['amvi'] and m2['fgf_sha256'] == C._SRC_SHA['fgf']
            and len(m2['amvi_sha256']) == 64 == len(m2['fgf_sha256'])
            and os.path.samefile(amvi.__file__, os.path.join(W, 'amvi.py')) and os.path.samefile(fgf.__file__, os.path.join(W, 'fgf.py')))
    _p('  file metadata: the sha256 of amvi.py and fgf.py is the one taken when the runner imported them, not read '
       'again when a file is written: %s' % prov)
    ok &= prov
    cols_want = None
    for pair, tf in CELLS:
        df, path, src = _cell_df(pair, tf)
        if cols_want is None:
            P0 = amvi.prepare(pair, tf, {})
            s = amvi.summary(P0, amvi.simulate(P0, {'path': 'mag', 'cost': 'ours'}))
            cols_want = list(s.keys())
            scalar = all(isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool) for v in s.values())
            del P0
        keys = _keys(df)
        n = 24192 if tf not in NO_TFSET else 12096
        ins_ok = all(_same(_py(df[c].iat[i]), want[c]) for i in range(0, len(df), 7)
                     for want in [inputs_here(dict(zip(SPEC_DIMS, keys[i])), pair, tf)] for c in C.INPUT_NAMES)
        f_ok = (len(df) == n and keys == spec_grid(tf) and ins_ok
                and list(df.columns) == _pcols() + list(C.INPUT_NAMES) + ['floor_ok'] + cols_want and scalar
                and all(k in cols_want for k in SUM_REQUIRED) and df['floor_ok'].dtype == bool)
        nulls = {c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().any()}
        fg = (df['p_dirSource'] == 'fgf').to_numpy()
        trl = (df['p_exitStyle'] == 'trail').to_numpy()
        no_tr = (df['trades'] == 0).to_numpy()
        f_ok &= (set(nulls) <= {'p_tfSet', 'p_dirMode', 'p_fgfTf', 'p_fgfBandAtr', 'p_fgfLvMode', 'fgfParentTf', 'fgfZTf1',
                                'fgfZTf2', 'fgfZTf3', 'trailActMul', 'trailOffMul', 'pf', 'win_pct', 'avg_bars_held',
                                'min_trail_off_pct'}
                 and np.array_equal(df['p_tfSet'].isna().to_numpy(), np.full(len(df), tf in NO_TFSET))
                 and np.array_equal(df['p_dirMode'].isna().to_numpy(), fg)
                 and all(np.array_equal(df[c].isna().to_numpy(), ~fg) for c in ('p_fgfTf', 'p_fgfBandAtr', 'p_fgfLvMode',
                                                                               'fgfParentTf', 'fgfZTf1', 'fgfZTf2', 'fgfZTf3'))
                 and all(np.array_equal(df[c].isna().to_numpy(), ~trl) for c in ('trailActMul', 'trailOffMul'))
                 and all(np.array_equal(df[c].isna().to_numpy(), no_tr) for c in ('pf', 'win_pct', 'avg_bars_held'))
                 and np.array_equal(df['min_trail_off_pct'].isna().to_numpy(), ~trl | no_tr))
        _p('  %s: %d rows; p_ columns = the grid in order; columns = %d p_ + the %d Pine inputs of tfSet / fgfTf / '
           'exitStyle + floor_ok + the %d fields of amvi.summary (all scalars), nothing else: %s (null / NaN: %s)'
           % (src, len(df), len(_pcols()), len(C.INPUT_NAMES), len(cols_want), f_ok, nulls or 'none'))
        ok &= f_ok
        meta = C.read_meta(path)
        now = C.file_meta(pair, tf, n)
        m_ok = meta is not None and all(meta.get(k) == now[k] for k in (
            'strategy', 'pair', 'tf', 'path', 'cost', 'ltfRule', 'settings', 'window', 'tf_sets', 'exit_styles',
            'trailActMul', 'trailOffMul', 'lowVolThreshold', 'floor_pct')) and bool((meta.get('floor') or {}).get('table_ok'))
        cur = meta is not None and meta.get('amvi_sha256') == now['amvi_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
        _p('    file metadata: %s, path %s, cost %s, ltfRule %s, %s settings, trailing (%s, %s), floor table ok %s: %s; '
           'written with the amvi.py and fgf.py now on disk: %s'
           % ((meta or {}).get('strategy'), (meta or {}).get('path'), (meta or {}).get('cost'), (meta or {}).get('ltfRule'),
              (meta or {}).get('settings'), (meta or {}).get('trailActMul'), (meta or {}).get('trailOffMul'),
              ((meta or {}).get('floor') or {}).get('table_ok'), m_ok,
              cur if cur else 'NO (rows are still checked against the module by tests 2, 3 and 7)'))
        ok &= m_ok
    _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 2. the default rows against the saved results
# ---------------------------------------------------------------------------------------------
def _one(pair, tf, p, *extra):
    cmd = [sys.executable, '-I', os.path.join(W, 'calib_amvi.py'), '--one', pair, tf, json.dumps(p)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _json_ref(sv, cols):
    """A saved run of out/inv_amvi_*.json as python values (its writer stores NaN as null, inf as 'inf')."""
    ref = {}
    for k in cols:
        v = sv[k]
        ref[k] = float('nan') if v is None else (float(v) if isinstance(v, str) else v)
    return ref


def _p_key(key, tf):
    """The grid row of a saved run key '<direction>/<filter>/<path>/<cost>'."""
    dname, flt = key.split('/')[:2]
    return dict(spec_default(tf, 'fgf' if flt == 'on' else 'orig'), inv=dname == 'inverted')


def _extra_key(key):
    path, cname = key.split('/')[2:]
    return (('--path', 'tv') if path == 'tv' else ()) + (('--cost', 'tv') if cname == 'script' else ())


def test_2_default_rows():
    """(2) The default rows (fused file and original, normal and inverted) equal the saved default results of
    the module with the same path and cost (out/inv_amvi_<PAIR>_<TF>.json runs normal/on/mag/ours,
    inverted/on/mag/ours, normal/off/mag/ours, inverted/off/mag/ours) through the command line on BTC 60 and XAU
    240, also with the TradingView path / script costs, and with --ltf-last against runs_ltf_last; every saved
    run (runs, runs_ltf_last) of all 14 cells through calib_amvi.one; the default rows of the sweep equal the
    saved runs and amvi.run called directly."""
    ok = True
    P0 = amvi.prepare('XAU', '240', {})
    sc = list(amvi.summary(P0, amvi.simulate(P0, {})).keys())
    del P0
    # ---- (a) the command line, BTC 60 and XAU 240
    for pair, tf in (('BTC', '60'), ('XAU', '240')):
        J = json.load(open(os.path.join(OUT, 'inv_amvi_%s_%s.json' % (pair, tf))))
        cases = [('runs', k, ()) for k in ('normal/on/mag/ours', 'inverted/on/mag/ours', 'normal/off/mag/ours',
                                           'inverted/off/mag/ours', 'normal/on/tv/script', 'inverted/on/tv/script',
                                           'normal/off/tv/script', 'inverted/off/tv/script', 'inverted/on/mag/script',
                                           'normal/off/tv/ours')]
        cases += [('runs_ltf_last', k, ('--ltf-last',)) for k in ('normal/on/mag/ours', 'inverted/on/mag/ours',
                                                                   'normal/on/tv/script', 'inverted/on/tv/script')]
        bad = []
        n_vals = 0
        got = {}
        for group, k, extra in cases:
            p = _p_key(k, tf)
            ex = extra + _extra_key(k)
            rc, out, err = _one(pair, tf, p, *ex)
            if rc != 0:
                bad.append('%s %s: exit code %d %s' % (group, k, rc, err.strip()[-200:]))
                continue
            o = json.loads(out)
            st = o.pop('setting')
            want = (('ltfRule', 'last' if '--ltf-last' in ex else 'first'), ('in_grid', True), ('row', C.row_of(pair, tf, p)),
                    ('path', 'tv' if '--path' in ex else 'mag'), ('cost', 'tv' if '--cost' in ex else 'ours'), ('p', p))
            if any(st.get(a) != v for a, v in want) or list(o) != list(C.INPUT_NAMES) + ['floor_ok'] + sc:
                bad.append('%s %s: setting echoed as %r' % (group, k, st))
            n_vals += _cmp(o, _json_ref(J[group][k], sc), sc, '%s %s' % (group, k), bad)
            got[(group, k)] = o
        moved = [k for g, k, _ in cases if g == 'runs_ltf_last' and ('runs', k) in got and (g, k) in got
                 and not all(_same(got[('runs', k)][c], got[(g, k)][c]) for c in sc)]
        _p('  %s %-3s command line: the default rows (fused / original x normal / inverted) = the saved runs */on/mag/ours '
           'and */off/mag/ours, also tv / script costs; the fused rows with --ltf-last = runs_ltf_last: %d runs, %d values: '
           '%s; --ltf-last moves the result of %d of the %d fused runs compared'
           % (pair, tf, len(cases), n_vals, _fmt_bad(bad), len(moved), sum(1 for g, _, _ in cases if g == 'runs_ltf_last')))
        for k in ('normal/on/mag/ours', 'inverted/on/mag/ours', 'normal/off/mag/ours', 'inverted/off/mag/ours'):
            o = got.get(('runs', k))
            if o is not None:
                _p('    %-22s row %5d: %d trades, net %+.3f %%, h1r %+.3f %%, h2r %+.3f %% (%d / %d trades)'
                   % (k, C.row_of(pair, tf, _p_key(k, tf)), o['trades'], o['net_pct'], o['h1r_pct'], o['h2r_pct'],
                      o['h1_trades'], o['h2_trades']))
        ok &= not bad and n_vals == len(cases) * len(sc) and len(moved) > 0
    # ---- (b) every saved run of all 14 cells through calib_amvi.one (in this process)
    tot = dict(cells=0, runs=0, vals=0)
    for pair in PAIRS:
        for tf in TFS:
            J = json.load(open(os.path.join(OUT, 'inv_amvi_%s_%s.json' % (pair, tf))))
            cache = {}
            bad = []
            n_runs = n_vals = 0
            if not set(sc) <= set(J['runs']['normal/on/mag/ours']):
                bad.append('the saved runs miss fields: %s' % (set(sc) - set(J['runs']['normal/on/mag/ours'])))
            for g, ltf in (('runs', 'first'), ('runs_ltf_last', 'last')):
                for k, sv in J[g].items():
                    path, cname = k.split('/')[2:]
                    o = C.one(pair, tf, _p_key(k, tf), path, 'tv' if cname == 'script' else 'ours', False, ltf, cache)
                    n_vals += _cmp(o, _json_ref(sv, sc), sc, '%s %s' % (g, k), bad)
                    n_runs += 1
            d = J['runs']['normal/on/mag/ours']
            _p('  %s %-3s: %d saved runs (runs 16, runs_ltf_last 8) = calib_amvi.one: %d values: %s | saved fused default '
               'mag / ours: %d trades, net %+.3f %%' % (pair, tf, n_runs, n_vals, _fmt_bad(bad), d['trades'], d['net_pct']))
            ok &= not bad and n_runs == 24
            tot['cells'] += 1
            tot['runs'] += n_runs
            tot['vals'] += n_vals
            del cache
            _free()
    _p('  %d cells: %d saved runs, %d values compared' % (tot['cells'], tot['runs'], tot['vals']))
    ok &= tot['cells'] == 14
    # ---- (c) the default rows of the sweep = the saved runs and amvi.run called directly
    n_cells = 0
    for pair in PAIRS:
        for tf in TFS:
            if os.path.exists(_out_file(pair, tf)) or (pair, tf) in _DF:
                df, _, src = _cell_df(pair, tf)
            elif FILES_ONLY:
                continue
            else:
                df, _ = C.run_cell(pair, tf, workers=3, sig_idx=_default_sig_idx(tf), write=False, verbose=False)
                src = '%d rows run here' % len(df)
            J = json.load(open(os.path.join(OUT, 'inv_amvi_%s_%s.json' % (pair, tf))))
            idx = {k: i for i, k in enumerate(_keys(df))}
            bad = []
            n_vals = 0
            for k in ('normal/on/mag/ours', 'inverted/on/mag/ours', 'normal/off/mag/ours', 'inverted/off/mag/ours'):
                p = _p_key(k, tf)
                row = df.iloc[idx[tuple(p[c] for c in SPEC_DIMS)]]
                n_vals += _cmp(row, _json_ref(J['runs'][k], sc), sc, k + ' json', bad)
                n_vals += _cmp(row, _run_summary(pair, tf, amvi_params(p, pair, tf)), sc, k + ' amvi.run', bad)
                if not bool(row['floor_ok']):
                    bad.append('%s: floor_ok False' % k)
            _p('  %s %-3s (%s): the four default rows of the sweep = the saved runs */on|off/mag/ours and amvi.run with the '
               'mapping written here: %d values: %s' % (pair, tf, src, n_vals, _fmt_bad(bad)))
            ok &= not bad and n_vals == 8 * len(sc)
            n_cells += 1
            _free()
    _p('  %d cells: the default rows of the sweep equal the saved runs and amvi.run' % n_cells)
    return ok and n_cells > 0


# ---------------------------------------------------------------------------------------------
# 3. random rows through --one
# ---------------------------------------------------------------------------------------------
def test_3_one_rows():
    """(3) 30 random rows per cell recomputed one at a time through `calib_amvi.py --one` (a new process each,
    the row's p_ columns as its JSON) equal the sweep rows on every non-p_ column; the same rows through amvi.run
    with this file's own mapping; --path / --cost and --ltf-last are honoured (= amvi.run with that path, cost,
    ltfRule); --off-grid; bad input is refused."""
    ok = True
    rng = np.random.default_rng(31)
    for pair, tf in CELLS:
        df, _, src = _cell_df(pair, tf)
        rc_cols = _rescols(df)
        sc = _sumcols(df)
        keys = _keys(df)
        pick = sorted(int(i) for i in rng.choice(len(df), size=30, replace=False))
        bad = []
        n_vals = n_run = n_tr = 0
        cover = {n: set() for n in C.DIM_NAMES}
        t0 = time.time()
        for i in pick:
            row = df.iloc[i]
            p = dict(zip(SPEC_DIMS, keys[i]))
            for n, v in p.items():
                cover[n].add(v)
            rc, out, err = _one(pair, tf, {'p_' + n: v for n, v in p.items()})
            if rc != 0:
                bad.append('row %d: exit code %d %s' % (i, rc, err.strip()[-200:]))
                continue
            o = json.loads(out)
            st = o.pop('setting')
            q = amvi_params(p, pair, tf)
            if p['dirSource'] == 'fgf':
                direction = {k: q[k] for k in ('dirSource', 'fgfOn', 'fgfTf', 'fgfParentTf', 'fgfZTf1', 'fgfZTf2', 'fgfZTf3',
                                                'fgfBandAtr', 'fgfLvMode')}
            else:
                direction = {k: q[k] for k in ('dirSource', 'dirMode', 'emaLen', 'dcLen', 'tradeDir', 'allowReverse')}
            if st != {'strategy': 'amvi', 'pair': pair, 'tf': tf, 'path': 'mag', 'cost': 'ours', 'ltfRule': 'first', 'p': p,
                      'in_grid': True, 'row': i, 'enabled': {k: q[k] for k in EN}, 'direction': direction,
                      'cell_trail': list(T_TRAIL.get((pair, tf), (1.5, 1.0)))}:
                bad.append('row %d: setting echoed as %r' % (i, st))
            if list(o) != rc_cols:
                bad.append('row %d: fields %r' % (i, list(o)))
                continue
            n_vals += _cmp(row, o, rc_cols, 'row %d --one' % i, bad)
            ref = _run_summary(pair, tf, q)
            n_run += _cmp(row, ref, sc, 'row %d amvi.run' % i, bad)
            if not (_same(_py(row['floor_ok']), floor_here(ref['min_trail_off_pct'], pair))
                    and all(_same(_py(row[c]), v) for c, v in inputs_here(p, pair, tf).items())):
                bad.append('row %d: inputs / floor_ok' % i)
            n_tr += int(row['trades'])
        dt = time.time() - t0
        cov = all(len(cover[d['name']] - {None}) >= 2 for d in C.DIMS if not (d['name'] == 'tfSet' and tf in NO_TFSET))
        _p('  %s %s (%s): 30 random rows, each in its own `--one` process: %d values (inputs, floor_ok, summary), and '
           'through amvi.run with the mapping written here: %d values (%d trades): %s; at least two values of every '
           'dimension among them: %s (%.1fs)' % (pair, tf, src, n_vals, n_run, n_tr, _fmt_bad(bad), cov, dt))
        ok &= not bad and n_vals == 30 * len(rc_cols) and n_run == 30 * len(sc) and cov
        # --path / --cost and --ltf-last (the control that is not a dimension)
        bad = []
        n = 0
        moved = 0
        fused = [i for i in pick if keys[i][3] == 'fgf']
        orig = [i for i in pick if keys[i][3] == 'orig']
        sub = sorted(set(fused[:2] + orig[:2] + [pick[0], pick[29]]))
        for i in sub:
            row = df.iloc[i]
            p = dict(zip(SPEC_DIMS, keys[i]))
            for extra, kw in (
                    (('--path', 'tv', '--cost', 'tv'), dict(path='tv', cost='tv')),
                    (('--path', 'tv', '--cost', 'stress'), dict(path='tv', cost='stress')),
                    (('--path', 'mag', '--cost', 'stress'), dict(path='mag', cost='stress')),
                    (('--ltf-last',), dict(ltf='last')),
                    (('--ltf-last', '--path', 'tv', '--cost', 'tv'), dict(ltf='last', path='tv', cost='tv'))):
                rc, out, err = _one(pair, tf, p, *extra)
                if rc != 0:
                    bad.append('row %d %s: exit code %d' % (i, ' '.join(extra), rc))
                    continue
                o = json.loads(out)
                st = o['setting']
                if (st['path'], st['cost'], st['ltfRule'], st['row']) != (kw.get('path', 'mag'), kw.get('cost', 'ours'),
                                                                          kw.get('ltf', 'first'), i):
                    bad.append('row %d %s: echoed %r' % (i, ' '.join(extra), st))
                ref = _run_summary(pair, tf, amvi_params(p, pair, tf, **kw))
                n += _cmp(o, ref, sc, 'row %d %s' % (i, ' '.join(extra)), bad)
                if extra == ('--ltf-last',):
                    moved += not all(_same(o[k], _py(row[k])) for k in sc)
        _p('  %s %s: %d rows x (--path tv --cost tv | --path tv --cost stress | --path mag --cost stress | --ltf-last | '
           '--ltf-last --path tv --cost tv) = amvi.run with that path, cost and ltfRule: %d values: %s; rows whose result '
           'moves with --ltf-last: %d of %d' % (pair, tf, len(sub), n, _fmt_bad(bad), moved, len(sub)))
        ok &= not bad and moved > 0
        _free()
    # bad input
    pair, tf = CELLS[0]
    p = spec_default(tf)
    cases = (('unknown dimension', dict(p, emaLen=20), ()),
             ('fgfOn is not a dimension', dict(p, fgfOn=False), ()),
             ('ltfRule is not a dimension', dict(p, ltfRule='last'), ()),
             ('value not in the grid', dict(p, slMult=2.0), ()),
             ('filter timeframe not in the grid', dict(p, fgfTf='30'), ()),
             ('missing used dimension', {k: v for k, v in p.items() if k != 'inv'}, ()),
             ('fgf without a band', dict(p, fgfBandAtr=None), ()),
             ('unknown exit style', dict(p, exitStyle='tp5'), ('--off-grid',)),
             ('below the Pine minimum', dict(p, slMult=-1.0), ('--off-grid',)),
             ('confluence 13', dict(p, minConfluence=13), ('--off-grid',)),
             ('not an object', [1, 2], ()))
    res = []
    for name, q, extra in cases:
        rc, out, err = _one(pair, tf, q, *extra)
        res.append((name, rc, out.strip() == '' and 'calib_amvi.py --one' in err))
    q = dict(p, fgfTf='30', fgfBandAtr=0.5, highVolThreshold=65.0, minConfluence=2, slMult=2.0)
    rc, out, err = _one(pair, tf, q, '--off-grid')
    og = rc == 0 and json.loads(out)['setting']['in_grid'] is False and json.loads(out)['setting']['row'] is None
    if og:
        o = json.loads(out)
        ref = _run_summary(pair, tf, amvi_params(q, pair, tf))
        og = all(_same(o[k], ref[k]) for k in ref) and (o['fgfParentTf'], o['fgfZTf1'], o['fgfZTf2'], o['fgfZTf3']) == \
            ('30', '30', '60', '120') and o['setting']['direction']['fgfZTf3'] == '120'
    # the original with filter inputs given: the grid row (they are dropped)
    q = dict(spec_default(tf, 'orig'), fgfTf='240', fgfBandAtr=0.75, fgfLvMode=SCL)
    rc, out, _ = _one(pair, tf, q)
    rc2, out2, _ = _one(pair, tf, spec_default(tf, 'orig'))
    og2 = rc == 0 and rc2 == 0
    if og2:
        o, o2 = json.loads(out), json.loads(out2)
        og2 = o['setting']['in_grid'] is True and o['setting']['p'] == spec_default(tf, 'orig') and o == o2
    b_ok = all(rc == 2 and e for _, rc, e in res) and og and og2
    _p('  bad input is refused (exit code 2, nothing on stdout): %s; --off-grid runs a setting outside the grid (filter '
       'timeframe 30 with its zones 30 / 60 / 120, band 0.5, threshold 65, confluence 2, stop 2 ATR) = amvi.run: %s; the '
       'original given filter inputs = the grid row with None there: %s'
       % (', '.join('%s -> %d' % (n, rc) for n, rc, _ in res), og, og2))
    return ok and b_ok


# ---------------------------------------------------------------------------------------------
# 4. worker count
# ---------------------------------------------------------------------------------------------
def test_4_workers():
    """(4) XAU 240, the full grid with 1 worker and with 3 workers (files in calib_tmp_amvi/w1 and w3, not out/):
    every row and column identical, and the two files byte for byte; equal to out/ when it exists. With 1 worker
    everything runs in this process: amvi.prepare is called once per signal setting (252), fgf.fgf_permissions
    once per filter setting (18), amvi.simulate once per row."""
    d1 = os.path.join(TMP, 'w1')
    d3 = os.path.join(TMP, 'w3')
    n = 12096
    calls = dict(prepare=0, simulate=0, fgf=0)
    o_prep, o_sim, o_fgf = amvi.prepare, amvi.simulate, fgf.fgf_permissions

    def c_prep(*a, **k):
        calls['prepare'] += 1
        return o_prep(*a, **k)

    def c_sim(*a, **k):
        calls['simulate'] += 1
        return o_sim(*a, **k)

    def c_fgf(*a, **k):
        calls['fgf'] += 1
        return o_fgf(*a, **k)

    _free()
    amvi.prepare, amvi.simulate, fgf.fgf_permissions = c_prep, c_sim, c_fgf
    try:
        a, ia = C.run_cell('XAU', '240', workers=1, out_dir=d1, verbose=False)
    finally:
        amvi.prepare, amvi.simulate, fgf.fgf_permissions = o_prep, o_sim, o_fgf
    _free()
    b, ib = C.run_cell('XAU', '240', workers=3, out_dir=d3, verbose=False)
    _free()
    _DF.pop(('XAU', '240'), None)
    f1 = os.path.join(d1, 'calib_amvi_XAU_240.parquet')
    f3 = os.path.join(d3, 'calib_amvi_XAU_240.parquet')
    fa = pd.read_parquet(f1)
    fb = pd.read_parquet(f3)
    same = fa.equals(fb) and a.equals(b) and a.equals(fa) and len(fa) == n and list(fa.columns) == list(fb.columns) \
        and all(fa[c].dtype == fb[c].dtype for c in fa.columns)
    byt = _sha(f1) == _sha(f3)
    dims = json.load(open(os.path.join(d1, 'calib_amvi_dims.json'))) == C.DIMS == json.load(open(os.path.join(d3, 'calib_amvi_dims.json')))
    once = calls == dict(prepare=252, simulate=n + 1, fgf=18) and ia['prepares'] == 252 == ib['prepares']
    _p('  XAU 240: %d rows x %d columns; 1 worker %.1fs (runs %.1fs), 3 workers %.1fs (runs %.1fs, speed-up x%.2f): '
       'frames %s, files %s (sha256 %s), dims.json = DIMS: %s'
       % (len(fa), len(fa.columns), ia['t_total'], ia['t_run'], ib['t_total'], ib['t_run'], ia['t_run'] / ib['t_run'],
          'identical' if same else 'DIFFERENT', 'byte for byte equal' if byt else 'DIFFERENT bytes', _sha(f3)[:16], dims))
    _p('  the 1-worker run called amvi.prepare %d times (252 signal settings), fgf.fgf_permissions %d times (18 filter '
       'settings), amvi.simulate %d times (%d rows + 1 to load the kernel): signals prepared once per signal setting and '
       'reused for all its exit settings: %s; distinct arrays kept: %s'
       % (calls['prepare'], calls['fgf'], calls['simulate'], n, once, ia['distinct']))
    ok = same and byt and dims and once
    fo = _out_file('XAU', '240')
    if os.path.exists(fo):
        fo_df = pd.read_parquet(fo)
        again = fo_df.equals(fb)
        _p('  out/calib_amvi_XAU_240.parquet (the production run) equals this re-run: %s (bytes %s)'
           % (again, 'equal' if _sha(fo) == _sha(f3) else 'different: the metadata differs only if amvi.py / fgf.py changed'))
        ok &= again
    return ok


# ---------------------------------------------------------------------------------------------
# 5. timing and memory, BTC 1
# ---------------------------------------------------------------------------------------------
_MEM_CODE = r"""
import os, sys, time
root = int(sys.argv[1])
def kb(pid, name, key):
    try:
        with open('/proc/%d/%s' % (pid, name)) as f:
            for line in f:
                if line.startswith(key):
                    return int(line.split()[1])
    except OSError:
        pass
    return 0
def children(pid):
    out = []
    for p in os.listdir('/proc'):
        if p.isdigit() and int(p) != os.getpid():
            try:
                with open('/proc/%s/stat' % p) as f:
                    s = f.read()
                if int(s[s.rindex(')') + 2:].split()[1]) == pid:
                    out.append(int(p))
            except (OSError, ValueError):
                pass
    return out
while os.path.exists('/proc/%d' % root):
    ch = children(root)
    pss = [kb(p, 'smaps_rollup', 'Pss:') for p in [root] + ch]
    prv = [kb(p, 'smaps_rollup', 'Private_Dirty:') for p in ch]
    print(len(ch), sum(pss), kb(root, 'status', 'VmRSS:'), max(prv or [0]), flush=True)
    time.sleep(0.5)
"""


class _MemWatch:
    """Samples twice a second, from a helper process, this process and its child processes (the forked
    workers): n children, the sum of their PSS (proportional set size: a page shared copy-on-write by k
    processes counts 1 / k in each, so the sum is the physical memory they hold together), this process' RSS
    and the largest private dirty memory of a child (the helper does not count itself). peak() = the sample
    with the largest PSS sum."""

    def __enter__(self):
        self.p = subprocess.Popen([sys.executable, '-I', '-c', _MEM_CODE, str(os.getpid())], stdout=subprocess.PIPE,
                                  text=True)
        return self

    def __exit__(self, *exc):
        time.sleep(0.6)
        self.p.terminate()
        out = self.p.communicate()[0]
        self.samples = [tuple(int(v) for v in line.split()) for line in out.splitlines() if len(line.split()) == 4]
        return False

    def peak(self, min_children=0):
        s = [x for x in self.samples if x[0] >= min_children]
        return max(s, key=lambda x: x[1]) if s else None


def test_5_timing_btc1():
    """(5) BTC 1 (the largest cell): the real preparation of all 252 signal settings (timed), then passes = all
    48 exit settings of 8 signal settings with 3 workers (the two defaults and 6 more of the default trigger, the 8
    busiest and the 8 quietest signal settings), extrapolated to the 12,096 rows. The full grid must stay under 45 min; parent + 3 workers
    under 4 GB."""
    _free()
    n_all = 12096
    load0 = os.getloadavg()[0]
    with _MemWatch() as mw0:
        cell = C.prepare_cell('BTC', '1')
    t_prep = cell['t_prep']
    te = np.asarray(cell['t_prep_each'])
    pk0 = mw0.peak(0)
    ntr = {si: cell['P'][si]['trig_up'] + cell['P'][si]['trig_dn'] for si in cell['idx']}
    dist = C._distinct(cell['P'])
    _p('  BTC 1: %d chart bars, %d 1-minute bars; all 252 signal settings prepared in %.1fs: one amvi.prepare %.3fs min / '
       '%.3fs median / %.3fs mean / %.3fs max; sub-bars + ATR %.1fs, kernel %.1fs; memory during the preparation (one '
       'process, PSS): %.0f MB; distinct arrays kept for the 252 prepared inputs: %s'
       % (cell['bars'], cell['n_sub'], t_prep, te.min(), np.median(te), te.mean(), te.max(), cell['t_sub'], cell['t_jit'],
          (pk0[1] / 1024.0) if pk0 else float('nan'), ', '.join('%s %d' % kv for kv in dist.items())))
    host = _default_sig_idx('1')
    order = sorted(cell['idx'], key=lambda si: (ntr[si], si))
    # passes of 8 signal settings each (384 settings; the pool start is a small part of a pass): the 8 settings
    # of the default trigger with the most directed trigger bars, the 8 busiest and the 8 quietest of the cell
    dflt = sorted((si for si in cell['idx'] if C.signals(None, '1')[si]['highVolThreshold'] == 70.0
                   and C.signals(None, '1')[si]['minConfluence'] == 3 and si not in host), key=lambda si: -ntr[si])[:6]
    passes = (('default', host + dflt), ('busiest', order[-8:]), ('quietest', order[:8]))
    per = []
    keep = None
    mem = []
    for name, idx in passes:
        with _MemWatch() as mw:
            res, info = C.run_prepared(cell, workers=3, sig_idx=idx)
        mem.append(mw)
        per.append(info['t_run'] / info['settings'])
        _p('  pass %-8s (%d signal settings, %d .. %d directed trigger bars each): %d settings, 3 workers %.1fs (%.4fs per '
           'setting, workers busy %.0f%%)'
           % (name, len(idx), min(ntr[si] for si in idx), max(ntr[si] for si in idx), info['settings'], info['t_run'],
              per[-1], 100.0 * info['busy'] / (3 * info['t_run'])))
        if name == 'default':
            keep = res
    res1, info1 = C.run_prepared(cell, workers=1, sig_idx=passes[0][1])
    same = all(len(res1[si]) == len(keep[si]) and all(_same(x, y) for a, b in zip(res1[si], keep[si]) for x, y in zip(a, b))
               for si in passes[0][1])
    _p('  pass default with 1 worker: %.1fs (%.4fs per setting); speed-up of 3 workers x%.2f; rows identical to the '
       '3-worker pass: %s' % (info1['t_run'], info1['t_run'] / info1['settings'], info1['t_run'] / (per[0] * info1['settings']), same))
    est = t_prep + n_all * float(np.mean(per))
    hi = t_prep + n_all * max(per)
    cpu = t_prep + n_all * info1['t_run'] / info1['settings'] / 3.0
    _p('  full grid BTC 1 with 3 workers = preparation %.1fs + 12,096 settings: %.1fs = %.1f min (mean of the passes), '
       '%.1f min (every setting as slow as in the slowest pass); from the 1-worker pass / 3: %.1f min; limit 45 min; '
       'load average %.2f -> %.2f (other jobs share the 4 CPUs)'
       % (t_prep, est, est / 60.0, hi / 60.0, cpu / 60.0, load0, os.getloadavg()[0]))
    pk = [m.peak(3) for m in mem]
    mem_ok = all(p is not None for p in pk)
    if mem_ok:
        top = max(pk, key=lambda x: x[1])
        import resource
        rss_self = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        mem_ok = top[1] / 1024.0 < MEM_LIMIT_MB and (pk0 is None or pk0[1] / 1024.0 < MEM_LIMIT_MB)
        _p('  memory during the 3-worker passes (%d samples with the parent and 3 workers alive): parent + workers hold '
           '%.0f MB together (sum of PSS; parent RSS %.0f MB, a worker\'s own private memory at most %.0f MB); peak RSS of '
           'this test process over everything it ran (tests before included): %.0f MB; limit %d MB: %s'
           % (sum(len([x for x in m.samples if x[0] >= 3]) for m in mem), top[1] / 1024.0, top[2] / 1024.0,
              max(p[3] for p in pk) / 1024.0, rss_self, MEM_LIMIT_MB, mem_ok))
    else:
        _p('  memory: no sample with the parent and 3 workers alive (/proc/<pid>/smaps_rollup not readable?)')
    del cell
    _free()
    return same and hi < 45 * 60.0 and mem_ok


# ---------------------------------------------------------------------------------------------
# 6. what every row must satisfy
# ---------------------------------------------------------------------------------------------
def _liveness(df, K, sig, joint, live_all, tag):
    """For each (name, columns, selection): groups of rows that differ only in those columns; returns the
    parts of the report and whether every row of the selection is in a group."""
    ps = {c: np.array([repr(k[j]) for k in K]) for j, c in enumerate(_pcols())}
    parts = []
    full = True
    for name, cols, sel in joint:
        others = [c for c in _pcols() if c not in cols]
        sel = np.ones(len(df), bool) if sel is None else sel
        if not sel.any():
            continue
        g = pd.Series(sig[sel]).groupby([ps[c][sel] for c in others]).agg(['size', 'nunique'])
        n_all = int((g['nunique'] == g['size']).sum())
        n_any = int((g['nunique'] > 1).sum())
        live_all[name] = live_all.get(name, 0) + n_any
        full &= int(g['size'].sum()) == int(sel.sum())
        parts.append('%s %d / %d / %d' % (name, n_all, n_any, len(g)))
    return parts, full


def test_6_row_consistency():
    """Rows hold what they claim, whatever the data: trade counts add up, net = final equity, the window, a switch
    that is off leaves no trace (no trail / target / collapse / time exits), raw_* = the trigger counts, the
    trigger counts belong to the signal setting (triggers to the trigger setting), floor_ok = min_trail_off_pct
    not below the floor, and every dimension changes results somewhere (tfSet on an in-memory part of XAU 60)."""
    ok = True
    live_all = {}
    for pair, tf in CELLS:
        df, _, src = _cell_df(pair, tf)
        ex = [c for c in df.columns if c.startswith('exit_')]
        tr = df['trades']
        es = df['p_exitStyle'].to_numpy(dtype=object)
        ve = df['p_useVolExit'].to_numpy(bool)
        inv = df['p_inv'].to_numpy(bool)
        fg = (df['p_dirSource'] == 'fgf').to_numpy()
        taken = df['taken_up'] + df['taken_dn']
        mt = df['min_trail_off_pct'].to_numpy()
        flr = np.array([floor_here(_py(v), pair) for v in mt])
        lu = np.where(inv, df['taken_up'] - df['short'], df['taken_up'] - df['long'])
        ld = np.where(inv, df['taken_dn'] - df['long'], df['taken_dn'] - df['short'])
        chk = {
            'trades = long + short': (tr == df['long'] + df['short']).all(),
            'trades = h1_trades + h2_trades': (tr == df['h1_trades'] + df['h2_trades']).all(),
            'trades = sum of the 7 exit kinds': len(ex) == 7 and (tr == df[ex].sum(axis=1)).all(),
            'orders taken - trades in {0, 1} (an order of the last bar), <= orders_unfilled_end':
                (((taken - tr) >= 0) & ((taken - tr) <= 1) & ((taken - tr) <= df['orders_unfilled_end'])).all(),
            'taken by zone = trades by real side (inv swaps), up to the last order': ((lu >= 0) & (ld >= 0) & (lu + ld == taken - tr)).all(),
            'taken <= directed triggers': (taken <= df['trig_up'] + df['trig_dn']).all(),
            'net_pct = (final_equity - 10000) / 10000': ((df['final_equity'] - INIT) / INIT * 100 == df['net_pct']).all(),
            'half1_pct + half2_pct = net_pct': np.allclose(df['half1_pct'] + df['half2_pct'], df['net_pct'], rtol=0, atol=1e-9),
            'h1_r + h2_r = net_r': np.allclose(df['h1_r'] + df['h2_r'], df['net_r'], rtol=1e-9, atol=1e-6),
            'window': ((df['start'] == WIN[pair][0]) & (df['end'] == WIN[pair][1])).all() and df['bars'].nunique() == 1,
            'no trailing stop: no trail exit': (df.loc[es != 'trail', 'exit_trail'] == 0).all(),
            'no target (none, trail): no tp exit': (df.loc[(es == 'none') | (es == 'trail'), 'exit_tp'] == 0).all(),
            'collapse exit off: no vol exit': (df.loc[~ve, 'exit_vol'] == 0).all(),
            'time stop 0 everywhere: no time exit': (df['exit_time'] == 0).all(),
            'nothing blocked': ((df['blocked_long'] == 0) & (df['blocked_short'] == 0)).all(),
            'raw_long / raw_short = trig_up / trig_dn': ((df['raw_long'] == df['trig_up']) & (df['raw_short'] == df['trig_dn'])).all(),
            'triggers = trig_up + trig_dn + trig_none': (df['triggers'] == df['trig_up'] + df['trig_dn'] + df['trig_none']).all(),
            'pf / win / avg_bars_held NaN only without trades': ((df['pf'].isna() == (tr == 0)) & (df['win_pct'].isna() == (tr == 0))
                                                                 & (df['avg_bars_held'].isna() == (tr == 0))).all(),
            'min_trail_off_pct NaN without trailing or trades, else > 0': (np.array_equal(np.isnan(mt), (es != 'trail') | (tr == 0).to_numpy())
                                                                          and bool((mt[~np.isnan(mt)] > 0).all())),
            'floor_ok = min_trail_off_pct not below the floor': np.array_equal(df['floor_ok'].to_numpy(bool), flr),
            'costs > 0 with trades': ((df['costs'] > 0) == (tr > 0)).all(),
            'cost ours: no slippage': (df['slippage_paid'] == 0).all(),
            'fair halves finite': np.isfinite(df[['h1r_pct', 'h2r_pct', 'net_pct', 'max_dd_pct', 'net_r']].to_numpy()).all(),
            'max_dd_pct >= 0': (df['max_dd_pct'] >= 0).all(),
            'at most one trade closed by the window end': (df['exit_end'] <= 1).all(),
            'zero_length <= trades': (df['zero_length'] <= tr).all(),
            'no quantity <= 0 (10 % of equity)': (df['zero_qty'] == 0).all(),
            'the seconds toggles: 5 ignored on every row': (df['seconds_ignored'] == 5).all(),
            'the trailing pair only on trail rows': (np.array_equal(df['useTrail'].to_numpy(bool), es == 'trail')
                                                     and np.array_equal(df['tpMult'].to_numpy(), np.array([STYLE[e][0] for e in es]))),
        }
        K = _keys(df)
        # the trigger counts belong to the signal setting; the number of triggers to the trigger setting
        fs, ft = {}, {}
        for i, k in enumerate(K):
            fs.setdefault(k[:8], set()).add((int(df['trig_up'].iat[i]), int(df['trig_dn'].iat[i]), int(df['trig_none'].iat[i])))
            ft.setdefault(k[:3], set()).add(int(df['triggers'].iat[i]))
        n_sig = 252 if tf in NO_TFSET else 504
        chk['trigger counts constant per signal setting'] = len(fs) == n_sig and all(len(v) == 1 for v in fs.values())
        chk['triggers constant per trigger setting (all 21 directions)'] = len(ft) == n_sig // 21 and all(len(v) == 1 for v in ft.values())
        n_b0 = sum(1 for k, v in fs.items() if k[3] == 'fgf' and k[6] == 0.0 and next(iter(v))[2] > 0)
        failed = [k for k, v in chk.items() if not bool(v)]
        sc = _sumcols(df)
        sig = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
        joint = (('highVolThreshold', ['p_highVolThreshold'], None), ('minConfluence', ['p_minConfluence'], None),
                 ('tfSet', ['p_tfSet'], None if tf not in NO_TFSET else np.zeros(len(df), bool)),
                 ('dirSource with the dimensions it switches', ['p_dirSource', 'p_dirMode', 'p_fgfTf', 'p_fgfBandAtr', 'p_fgfLvMode'], None),
                 ('dirMode (orig)', ['p_dirMode'], ~fg), ('fgfTf (fgf)', ['p_fgfTf'], fg), ('fgfBandAtr (fgf)', ['p_fgfBandAtr'], fg),
                 ('fgfLvMode (fgf)', ['p_fgfLvMode'], fg), ('inv', ['p_inv'], None), ('slMult', ['p_slMult'], None),
                 ('exitStyle', ['p_exitStyle'], None), ('useVolExit', ['p_useVolExit'], None))
        parts, full = _liveness(df, K, sig, joint, live_all, '%s %s' % (pair, tf))
        # every row has its direction twin (inv flipped) in the file, and never its result (when it trades)
        pos = {k: i for i, k in enumerate(K)}
        j_inv = C.DIM_NAMES.index('inv')
        twin = np.array([pos.get(k[:j_inv] + (not k[j_inv],) + k[j_inv + 1:], -1) for k in K])
        no_twin = int((twin < 0).sum())
        twin = np.where(twin < 0, np.arange(len(K)), twin)
        same_twin = int(((sig == sig[twin]) & (tr.to_numpy() > 0)).sum())
        try:
            import calib_analyze
            codes = calib_analyze.codes_of(df, C.DIMS)
            jdir = next(j for j, d in enumerate(C.DIMS) if d['name'].lower() in calib_analyze.DIR_NAMES)
            unused = sorted(set(C.DIM_NAMES[j] for j in np.flatnonzero((codes < 0).any(axis=0))))
            want_unused = sorted(list(SPEC_UNUSED) + (['tfSet'] if tf in NO_TFSET else []))
            an = (C.DIM_NAMES[jdir] == 'inv' and unused == want_unused and len(np.unique(codes, axis=0)) == len(df)
                  and 'floor_ok' in df.columns and '--ltf-last' in str(calib_analyze.CONTROLS.get('amvi')))
            an_txt = ('calib_analyze.codes_of reads every p_ value (direction dimension inv; unused only in %s; its amvi '
                      'control is --ltf-last): %s' % (unused, an))
        except Exception as e:      # noqa: BLE001
            an = False
            an_txt = 'calib_analyze.codes_of FAILED: %r' % (e,)
        n_distinct = len(np.unique(sig))
        cand = int(((df['h1r_pct'] > 0) & (df['h2r_pct'] > 0) & (df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)
                    & df['floor_ok']).sum())
        el = int(((df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).sum())
        _p('  %s %s (%s): %d rows, %d checks: %s' % (pair, tf, src, len(df), len(chk),
                                                     'all hold' if not failed else 'FAILED: ' + '; '.join(failed)))
        _p('    groups differing only in one dimension (all results distinct / some distinct / groups): %s' % '; '.join(parts))
        _p('    trades %d .. %d (median %d; %d rows without a trade); distinct results %d of %d rows; rows with trades '
           'that equal their direction twin (inv flipped): %d; rows below the trailing floor: %d; rows with a close_all '
           'dropped after a reversal (rev_close_same_run > 0, A11): %d; rows with >= 30 trades in each half: %d, of which '
           'positive in both fair halves: %d; filter settings with band 0 and a trigger without a zone: %d'
           % (tr.min(), tr.max(), int(tr.median()), int((tr == 0).sum()), n_distinct, len(df), same_twin,
              int((~df['floor_ok']).sum()), int((df['rev_close_same_run'] > 0).sum()), el, cand, n_b0))
        _p('    every row is in a group of every analysis above (no row dropped): %s; rows without a direction twin in '
           'the file: %d; %s' % (full, no_twin, an_txt))
        ok &= not failed and same_twin == 0 and full and an and no_twin == 0
    # tfSet is None on charts 1 / 120 / 240: its effect on a chart where it is a dimension (XAU 60, in memory)
    S = C.signals(None, '60')
    idx = [i for i, s in enumerate(S) if (s['highVolThreshold'], s['minConfluence']) == (60.0, 2)
           and (s['dirSource'], s['dirMode'], s['fgfTf'], s['fgfBandAtr']) in (('orig', TR, None, None), ('fgf', None, '60', 0.25))
           and s['fgfLvMode'] in (None, EP)]
    df, _ = C.run_cell('XAU', '60', workers=3, sig_idx=idx, write=False, verbose=False)
    K = _keys(df)
    sig = pd.util.hash_pandas_object(df[_sumcols(df)], index=False).to_numpy()
    ge = (df['p_tfSet'] == 'ge').to_numpy()
    en_ok = all(tuple(bool(df[e].iat[i]) for e in EN) == (GE['60'] if ge[i] else (True,) * 7) for i in range(len(df)))
    parts, full = _liveness(df, K, sig, (('tfSet', ['p_tfSet'], None),), live_all, 'XAU 60')
    trg = {s: sorted(set(df.loc[df['p_tfSet'] == s, 'triggers'])) for s in ('all', 'ge')}
    _p('  XAU 60 in memory (%d signal settings: thresholds 60 / 2, the default directions, tfSet all / ge; %d rows): '
       'tfSet groups %s; triggers all %s / ge %s; the toggles en1 .. enD of the rows = the set: %s'
       % (len(idx), len(df), '; '.join(parts), trg['all'], trg['ge'], en_ok))
    ok &= len(idx) == 4 and full and en_ok and trg['all'] != trg['ge']
    _free()
    dead = [k for k, v in live_all.items() if v == 0]
    _p('  every dimension changes results in at least one group over the cells: %s' % ('yes' if not dead else 'NO: %s' % dead))
    return ok and not dead and len(live_all) == 12


# ---------------------------------------------------------------------------------------------
# 7. every row
# ---------------------------------------------------------------------------------------------
def _groups(keys, pair, tf):
    """The rows of a file grouped by their amvi.prepare params (this file's own mapping)."""
    groups = {}
    for i, k in enumerate(keys):
        prep, sim = _split(amvi_params(dict(zip(SPEC_DIMS, k)), pair, tf))
        groups.setdefault(tuple(sorted((a, repr(b)) for a, b in prep.items())), (prep, []))[1].append((i, sim, k))
    return groups


def test_7_all_rows():
    """Every row of the cells' files, not a sample: recomputed in this process with amvi.prepare once per signal
    setting and amvi.simulate + amvi.summary per row, the parameters from this file's own mapping (amvi_params,
    split into the prepare and the simulate keys); every summary value, the input columns and floor_ok must be
    equal."""
    ok = True
    for pair, tf in CELLS:
        df, _, src = _cell_df(pair, tf)
        sc = _sumcols(df)
        keys = _keys(df)
        vals = [df[c].tolist() for c in sc]
        ins = {c: df[c].tolist() for c in C.INPUT_NAMES}
        fl = df['floor_ok'].tolist()
        groups = _groups(keys, pair, tf)
        t0 = time.time()
        n_vals = 0
        bad_rows = []
        bad_groups = 0
        fields_ok = True
        sub = None
        for gk in sorted(groups):
            prep, items = groups[gk]
            Pp = amvi.prepare(pair, tf, prep)
            if sub is None:
                sub = (Pp['w0'], Pp['w1'], amvi.get_sub(Pp))
            assert (Pp['w0'], Pp['w1']) == sub[:2]
            Pp['sub'] = sub[2]                      # the 1-minute table depends on the window rows only
            n_bad0 = len(bad_rows)
            for i, sim, k in items:
                s = amvi.summary(Pp, amvi.simulate(Pp, sim))
                if list(s) != sc:
                    fields_ok = False
                    break
                n_vals += len(sc)
                want_in = inputs_here(dict(zip(SPEC_DIMS, k)), pair, tf)
                if not (all(_same(_py(vals[j][i]), s[c]) for j, c in enumerate(sc))
                        and all(_same(_py(ins[c][i]), want_in[c]) for c in C.INPUT_NAMES)
                        and bool(fl[i]) == floor_here(s['min_trail_off_pct'], pair)):
                    bad_rows.append(i)
            bad_groups += len(bad_rows) > n_bad0
            del Pp
        n_sig = 252 if tf in NO_TFSET else 504
        c_ok = fields_ok and not bad_rows and len(groups) == n_sig and n_vals == len(df) * len(sc) and len(df) == n_sig * 48
        _p('  %s %s (%s): all %d rows recomputed (amvi.prepare for each of the %d signal settings, amvi.simulate + '
           'amvi.summary per row): %d summary values, plus the %d input columns and floor_ok: %s (%.1fs)'
           % (pair, tf, src, len(keys), len(groups), n_vals, len(C.INPUT_NAMES),
              'all equal' if not bad_rows and fields_ok else '%d ROWS DIFFER in %d signal settings (first rows %s)%s'
              % (len(bad_rows), bad_groups, bad_rows[:8], '' if fields_ok else '; the summary fields differ'),
              time.time() - t0))
        ok &= c_ok
        _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 8. every cell that has a file
# ---------------------------------------------------------------------------------------------
def test_8_every_cell():
    """Every cell with a file in out/: the file holds the grid in order with the result columns and its metadata,
    and 4 random rows of EVERY signal setting (1,008 or 2,016 rows per cell) recomputed in this process
    (amvi.prepare per signal setting, amvi.simulate + amvi.summary per row, this file's own mapping) equal the
    file."""
    ok = True
    rng = np.random.default_rng(8)
    n_cells = 0
    for pair in PAIRS:
        for tf in TFS:
            f = _out_file(pair, tf)
            if not os.path.exists(f):
                continue
            n_cells += 1
            t0 = time.time()
            df = pd.read_parquet(f)
            sc = _sumcols(df)
            keys = _keys(df)
            n_sig = 252 if tf in NO_TFSET else 504
            meta = C.read_meta(f)
            now = C.file_meta(pair, tf, n_sig * 48)
            p10, _, _ = _own_p10(pair, tf)
            act, off = T_TRAIL.get((pair, tf), (1.5, 1.0))
            g_ok = (len(df) == n_sig * 48 and keys == spec_grid(tf) and all(k in sc for k in SUM_REQUIRED) and meta is not None
                    and all(meta.get(k) == now[k] for k in ('strategy', 'pair', 'tf', 'path', 'cost', 'ltfRule', 'settings',
                                                            'window', 'trailActMul', 'trailOffMul', 'tf_sets'))
                    and (meta['trailActMul'], meta['trailOffMul']) == (act, off)
                    and bool(((df['start'] == WIN[pair][0]) & (df['end'] == WIN[pair][1])).all())
                    and np.array_equal(df['floor_ok'].to_numpy(bool),
                                       np.array([floor_here(_py(v), pair) for v in df['min_trail_off_pct'].tolist()]))
                    and off * p10 >= T_FLOOR[pair] and abs(meta['floor']['p10_atr_pct'] - p10) < 1e-6)
            cur = meta is not None and meta.get('amvi_sha256') == now['amvi_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
            groups = _groups(keys, pair, tf)
            n_rows = n_vals = 0
            bad_rows = []
            sub = None
            for gk in sorted(groups):
                prep, items = groups[gk]
                Pp = amvi.prepare(pair, tf, prep)
                if sub is None:
                    sub = (Pp['w0'], Pp['w1'], amvi.get_sub(Pp))
                assert (Pp['w0'], Pp['w1']) == sub[:2]
                Pp['sub'] = sub[2]
                take = [items[int(j)] for j in rng.choice(len(items), size=min(4, len(items)), replace=False)]
                for i, sim, _ in sorted(take):
                    s = amvi.summary(Pp, amvi.simulate(Pp, sim))
                    n_rows += 1
                    n_vals += len(sc)
                    if list(s) != sc or not all(_same(_py(df[c].iat[i]), s[c]) for c in sc):
                        bad_rows.append(i)
                del Pp
            h = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
            c_ok = g_ok and not bad_rows and len(groups) == n_sig and n_rows == n_sig * 4
            tr = df['trades']
            _p('  %s %-3s: %d rows, the grid in order, metadata, window, floor_ok: %s; written with the amvi.py / fgf.py now '
               'on disk: %s; %d rows (4 of each of the %d signal settings) recomputed: %d values, %s; distinct results %d; '
               'trades %d .. %d; rows below the trailing floor: %d (%.1fs)'
               % (pair, tf, len(df), g_ok, cur, n_rows, len(groups), n_vals,
                  'all equal' if not bad_rows else '%d ROWS DIFFER: %s' % (len(bad_rows), bad_rows[:8]),
                  len(np.unique(h)), tr.min(), tr.max(), int((~df['floor_ok']).sum()), time.time() - t0))
            ok &= c_ok
            _free()
    if n_cells == 0:
        _p('  no cell has a file in out/ yet: nothing to check')
    else:
        _p('  %d cells checked' % n_cells)
    return ok


# ---------------------------------------------------------------------------------------------
# 9. the sweep path on cells the 240-minute files cannot show
# ---------------------------------------------------------------------------------------------
T9_CELLS = (('XAU', '5'), ('BTC', '15'), ('XAU', '1'))
T9_BELOW = (('XAU', '5'), ('BTC', '15'))            # cells where the loose trigger has trailing rows below the floor


def _t9_signals(tf):
    """Signal settings of chart tf that exercise what the 240-minute cells cannot: tfSet 'ge' next to 'all' in one run
    (charts 5 .. 60: two sets of toggles, two volatility-collapse series), the loose trigger (rows below the trailing
    floor on charts 5 and 15) and the default one, the original's Candle / Breakout modes, the filter timeframes 15
    and 240 with both level modes and the bands 0 / 0.75. Returns (signal indices, the keys' first 8 values)."""
    want = set()
    for h, m in ((50.0, 1), (70.0, 3)):
        for ts in ((None,) if tf in NO_TFSET else ('all', 'ge')):
            for d in (('orig', CA, None, None, None), ('orig', BO, None, None, None), ('fgf', None, '15', 0.0, SCL),
                      ('fgf', None, '240', 0.75, EP)):
                want.add((h, m, ts) + d)
    idx = [i for i, s in enumerate(C.signals(None, tf)) if tuple(s[k] for k in C.SIGNAL_DIMS) in want]
    return idx, want


def test_9_other_cells():
    """The sweep path (prepare_cell + run_prepared with 3 workers, as in a production run) on cells whose rows the
    240-minute files cannot check: XAU 5 (trailing pair (2.625, 1.75), tfSet all / ge), BTC 15 (tfSet; rows below the
    trailing floor), XAU 1 (pair (7.5, 5), chart 1); 16 (8 on chart 1) signal settings each, in memory. Every row
    recomputed here with this file's own mapping (summary, input columns, floor_ok), with rows below the trailing
    floor present and the cell's trailing pair shown to matter; 1 worker = 3 workers; a few rows through `--one`
    (trailing rows below and above the floor, 'ge' rows, the original inverted) equal the sweep rows."""
    ok = True
    for pair, tf in T9_CELLS:
        idx, want = _t9_signals(tf)
        t0 = time.time()
        df, info = C.run_cell(pair, tf, workers=3, sig_idx=idx, write=False, verbose=False)
        t_sweep = time.time() - t0
        df1, _ = C.run_cell(pair, tf, workers=1, sig_idx=idx, write=False, verbose=False)
        same1 = df1.equals(df)
        del df1
        _free()
        keys = _keys(df)
        full = spec_grid(tf)
        rowno = {k: i for i, k in enumerate(full)}
        G = [k for k in full if k[:8] in want]
        sc = _sumcols(df)
        rc_cols = _rescols(df)
        g_ok = (keys == G and len(idx) == len(want) and len(df) == len(want) * 48
                and list(df.columns) == _pcols() + list(C.INPUT_NAMES) + ['floor_ok'] + sc)
        # every row, this file's own mapping
        groups = _groups(keys, pair, tf)
        bad = []
        n_vals = 0
        sub = None
        alt_n = alt_moved = 0
        t1 = time.time()
        for gk in sorted(groups):
            prep, items = groups[gk]
            Pp = amvi.prepare(pair, tf, prep)
            if sub is None:
                sub = amvi.get_sub(Pp)
            Pp['sub'] = sub
            for i, sim, k in items:
                s = amvi.summary(Pp, amvi.simulate(Pp, sim))
                want_in = inputs_here(dict(zip(SPEC_DIMS, k)), pair, tf)
                n_vals += len(sc) + len(want_in) + 1
                if (list(s) != sc or not all(_same(_py(df[c].iat[i]), s[c]) for c in sc)
                        or not all(_same(_py(df[c].iat[i]), v) for c, v in want_in.items())
                        or bool(df['floor_ok'].iat[i]) != floor_here(s['min_trail_off_pct'], pair)):
                    bad.append(i)
                if (pair, tf) in T_TRAIL and k[10] == 'trail' and s['trades'] > 0 and alt_n < 8:
                    # the cell's own trailing pair matters: the pair of charts 15 .. 240 gives another result
                    s2 = amvi.summary(Pp, amvi.simulate(Pp, dict(sim, trailActMul=1.5, trailOffMul=1.0)))
                    alt_n += 1
                    alt_moved += not all(_same(s[c], s2[c]) for c in sc)
            del Pp
        del sub
        _free()
        t_rec = time.time() - t1
        n_below = int((~df['floor_ok']).sum())
        sens = []
        if tf not in NO_TFSET:
            trg = {ts: sorted(set(df.loc[df['p_tfSet'] == ts, 'triggers'])) for ts in ('all', 'ge')}
            sens.append(('tfSet ge triggers differ from all', trg['all'] != trg['ge']))
            sens.append(('two avgAmvi series kept (all, ge)', info['distinct']['avgAmvi'] == 2))
        if (pair, tf) in T_TRAIL:
            sens.append(('the cell\'s trailing pair moves %d of %d trailing rows tried' % (alt_moved, alt_n), alt_moved > 0))
        if (pair, tf) in T9_BELOW:
            sens.append(('rows below the trailing floor: %d' % n_below, n_below > 0))
        # a few rows through --one, each in its own process
        es = df['p_exitStyle'].to_numpy(dtype=object)
        fl = df['floor_ok'].to_numpy(bool)
        trd = df['trades'].to_numpy()
        cand = [np.flatnonzero((es == 'trail') & ~fl), np.flatnonzero((es == 'trail') & fl & (trd > 0)),
                np.flatnonzero((df['p_tfSet'] == 'ge').to_numpy() & df['p_inv'].to_numpy(bool)),
                np.flatnonzero((df['p_dirMode'] == BO).to_numpy() & df['p_inv'].to_numpy(bool) & (es == 'none'))]
        rng = np.random.default_rng(9)
        pick = sorted(set(int(rng.choice(c)) for c in cand if len(c)))
        one_bad = []
        for i in pick:
            p = dict(zip(SPEC_DIMS, keys[i]))
            rc, out, err = _one(pair, tf, {'p_' + n: v for n, v in p.items()})
            if rc != 0:
                one_bad.append('row %d: exit code %d %s' % (i, rc, err.strip()[-200:]))
                continue
            o = json.loads(out)
            st = o.pop('setting')
            if (list(o) != rc_cols or st['row'] != rowno[keys[i]] or st['p'] != p or st['in_grid'] is not True
                    or st['cell_trail'] != list(T_TRAIL.get((pair, tf), (1.5, 1.0)))
                    or st['enabled'] != {e: inputs_here(p, pair, tf)[e] for e in EN}):
                one_bad.append('row %d: fields / setting %r' % (i, st))
                continue
            b1 = []
            _cmp(df.iloc[i], o, rc_cols, 'row %d --one' % i, b1)
            one_bad += b1
        cell_ok = g_ok and not bad and n_vals > 0 and same1 and all(v for _, v in sens) and not one_bad and len(pick) >= (2 if tf in NO_TFSET else 3)
        _p('  %s %-2s in memory: %d signal settings x 48 = %d rows, 3 workers %.1fs; the grid rows in order: %s; 1 worker = '
           '3 workers: %s; every row recomputed with this file\'s mapping (%d values: summary, input columns, floor_ok): %s '
           '(%.1fs); %s; %d rows through --one (trailing below / above the floor, ge inverted, Breakout inverted): %s'
           % (pair, tf, len(idx), len(df), t_sweep, g_ok, same1, n_vals,
              'all equal' if not bad else '%d ROWS DIFFER (first %s)' % (len(bad), bad[:8]), t_rec,
              '; '.join('%s: %s' % sv for sv in sens) or 'no sensitivity requirement', len(pick), _fmt_bad(one_bad)))
        ok &= cell_ok
        del df
        _free()
    return ok


# ---------------------------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------------------------
def main(argv):
    global CELLS, FILES_ONLY
    args = list(argv)
    if '--cells' in args:
        i = args.index('--cells')
        CELLS = [tuple(c.split(':')) for c in args[i + 1].split(',')]
        del args[i:i + 2]
    if '--files-only' in args:
        args.remove('--files-only')
        FILES_ONLY = True
    for pair, tf in CELLS:
        if pair not in PAIRS or tf not in TFS:
            _p('unknown cell %s:%s' % (pair, tf))
            return 2
    names = sorted(k for k, v in globals().items() if k.startswith('test_') and callable(v))
    if args:
        names = [k for k in names if any(f in k for f in args)]
    if not names:
        _p('no tests match %s' % args)
        return 2
    _p('calib_tests_amvi.py: cells %s; amvi.py sha256 %s; fgf.py sha256 %s; calib_amvi.py sha256 %s; load average %.2f'
       % (', '.join('%s %s' % c for c in CELLS), _sha(os.path.join(W, 'amvi.py'))[:16], _sha(os.path.join(W, 'fgf.py'))[:16],
          _sha(os.path.join(W, 'calib_amvi.py'))[:16], os.getloadavg()[0]))
    res = {}
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
    _p('\nsummary: %d PASS, %d FAIL' % (sum(res.values()), len(res) - sum(res.values())))
    for k, r in res.items():
        _p('  %s %s' % ('PASS' if r else 'FAIL', k))
    _p('amvi.py sha256 at the end %s' % _sha(os.path.join(W, 'amvi.py'))[:16])
    return 0 if all(res.values()) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
