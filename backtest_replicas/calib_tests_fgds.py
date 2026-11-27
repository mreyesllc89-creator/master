"""calib_tests_fgds.py: tests of calib_fgds.py (CALIB_SPEC.md, strategy "fgds"; the grid is section
14 of SPEC_fgds.md with the orchestrator's decisions: the scale-free sizing dsMaxQty 1e9 / dsQtyStep
0.000001 on every row, the filter on in every row, one trailing pair per cell, column floor_ok).

Usage: python3 -I calib_tests_fgds.py [name filter ...] [--cells XAU:240,BTC:240] [--files-only]

  test_1_grid             the grid is the full product of section 14 (21,600 = 108 x 192 + 18 x 48),
                          keys unique, DIMS / SIGNALS / EXITS consistent; every setting of all 14
                          cells maps to the fgds params the spec means (an independent mapping
                          written here, the Pine's own input defaults read from the .pine file);
                          the trailing pair of every cell = the table, and the table's floor
                          recomputed here from the bar files; the dimensions listed once (None)
                          cannot change a result (band / level / zone exit with "New signal",
                          trailing distances with the trailing stop off); normalize(); the files
                          hold the grid in order with the columns of the docstring; the file
                          metadata names the fgds.py / fgf.py the process imported
  test_2_default_rows     the default row with --script-sizing, and the same with inv true, equal
                          the saved default results of the module (out/inv_fgds_<PAIR>_<TF>.json
                          runs normal/on/mag/ours and inverted/on/mag/ours) through the command
                          line on BTC 60 and XAU 240 (plus tv / script costs and the other two
                          triggers); every saved filter-on run of all 14 cells through
                          calib_fgds.one with script sizing (the filter-off runs: no trade); the
                          scale-free default rows of the sweep against fgds.run called directly,
                          and every row of the default signal setting (240, of which 60 with the
                          cell's own trailing pair) of all 14 cells through the sweep's path
                          against fgds.prepare + fgds.simulate with this file's own mapping (the
                          only check of the sweep path on BTC / XAU 1 and 5, whose trailing pair
                          is not the 240-minute one, before their files exist)
  test_3_one_rows         30 random rows per cell recomputed one at a time through
                          `calib_fgds.py --one` (a new process each) equal the sweep rows (and echo
                          the row number); the same rows through fgds.run with this file's own
                          mapping; --path / --cost; --script-sizing; --off-grid; bad input
  test_4_workers          XAU 240: 1 worker vs 3 workers identical (frames and file bytes);
                          fgds.prepare and fgf.fgf_permissions run once per signal setting (108),
                          fgds.simulate once per row
  test_5_timing_btc1      BTC 1: the real preparation of the 108 signal settings (the cost of one
                          fgf.fgf_permissions call measured) and passes of whole signal settings
                          with 3 workers extrapolated to the full grid: under 45 minutes; and the
                          memory the parent and its 3 workers hold together during the passes (sum
                          of PSS, sampled): under 4 GB
  test_6_row_consistency  what every row must satisfy whatever the data (counts add up, a switch
                          that is off leaves no trace, the trigger counts are those of the chosen
                          trigger), and every dimension changes results; direction twins
  test_7_all_rows         EVERY row of the cells' files (not a sample) recomputed in this process:
                          fgds.prepare once per signal setting, fgds.simulate + fgds.summary per
                          row, with this file's own mapping; all values equal; the "New signal"
                          arrays do not depend on the band or the level mode
  test_8_every_cell       every cell that has a file in out/: the file holds the grid in order,
                          metadata, and 4 random rows of EVERY signal setting plus 2 "New signal"
                          rows of every host (468 rows per cell) recomputed in this process

The cells of tests 1 (files), 3, 6 and 7 are --cells (default XAU 240 and BTC 240): the file
out/calib_fgds_<PAIR>_<TF>.parquet when it exists, else the cell is run here with 3 workers into
calib_tmp_fgds/w3/ (never into out/). Test 2 covers all 14 cells: the file when it exists, else only
the default signal setting is run in memory (240 rows; --files-only skips those). At most 2
processes at a time, except the sweep's own 3 workers. Prints PASS / FAIL per test; exit code 1 on
a failure.
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
import fgds  # noqa: E402
import fgf   # noqa: E402
import calib_fgds as C  # noqa: E402

OUT = os.path.join(W, 'out')
TMP = os.path.join(W, 'calib_tmp_fgds')
PINE = '/home/user/master/FlashGold_Direction_Strategy.pine'
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
INIT = 10000.0
WIN = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}
CELLS = [('XAU', '240'), ('BTC', '240')]
FILES_ONLY = False
N_GRID = 21600
MEM_LIMIT_MB = 4000        # test 5: parent + 3 workers on BTC 1 (the prompt: keep a BTC 1 run under 4 GB)
SUM_REQUIRED = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
                'exit_sl', 'exit_tp', 'exit_trail', 'exit_reverse', 'exit_opp', 'exit_zone', 'exit_time', 'exit_end',
                'net_r', 'h1_r', 'h2_r', 'zero_qty', 'qty_capped_max', 'qty_capped_margin', 'margin_over',
                'max_notional_x')


def _p(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# this file's own reading of the spec (independent of calib_fgds' lists and mappings)
# ---------------------------------------------------------------------------------------------
ZS, SC, NS = "Zone start", "Signal confirmed", "New signal"
EP, SCL = "Entry price", "Signal close"
SPEC_DIMS = ['fgfTf', 'fgfBurstAtr', 'fgfBandAtr', 'fgfLvMode', 'fgfUseZones', 'dsTrigger', 'inv', 'dsZoneExit',
             'dsReverse', 'dsSlAtr', 'exitStyle']
SPEC_KIND = {'fgfTf': 'ordinal', 'fgfBurstAtr': 'ordinal', 'fgfBandAtr': 'ordinal', 'fgfLvMode': 'categorical',
             'fgfUseZones': 'categorical', 'dsTrigger': 'categorical', 'inv': 'categorical',
             'dsZoneExit': 'categorical', 'dsReverse': 'categorical', 'dsSlAtr': 'ordinal', 'exitStyle': 'categorical'}
SPEC_SIDE = dict(zip(SPEC_DIMS, ['signal'] * 5 + ['exit'] * 6))
SPEC_DEFAULT = dict(zip(SPEC_DIMS, ('60', 0.5, 0.25, EP, True, ZS, False, True, True, 1.0, 'tp3')))
SPEC_VALUES = {'fgfTf': ['15', '60', '240'], 'fgfBurstAtr': [0.25, 0.5, 1.0], 'fgfBandAtr': [0.0, 0.25, 0.75],
               'fgfLvMode': [EP, SCL], 'fgfUseZones': [True, False], 'dsTrigger': [ZS, SC, NS], 'inv': [False, True],
               'dsZoneExit': [True, False], 'dsReverse': [True, False], 'dsSlAtr': [0.5, 1.0, 2.0],
               'exitStyle': ['tp3', 'tp1.5', 'none', 'trail']}
SPEC_UNUSED = {'fgfBandAtr': {'dsTrigger': NS}, 'fgfLvMode': {'dsTrigger': NS}, 'dsZoneExit': {'dsTrigger': NS}}
# section 14, dimension 11: exitStyle = (dsTpR, dsUseTrail)
STYLE = {'tp3': (3.0, False), 'tp1.5': (1.5, False), 'none': (0.0, False), 'trail': (0.0, True)}
# section 14, dimension 1: fgfTf T moves fgfParentTf = T and fgfZTf1 / 2 / 3 = T / 2T / 4T
TFSET = {'15': ('15', '15', '30', '60'), '60': ('60', '60', '120', '240'), '240': ('240', '240', '480', '960')}
# section 14: (dsTrActAtr, dsTrDstAtr) per cell; the 10th percentile of ATR(14) / close in %, as printed there
T_TRAIL = {('BTC', '1'): (13.0, 6.5), ('BTC', '5'): (3.5, 1.75), ('XAU', '1'): (10.0, 5.0), ('XAU', '5'): (3.5, 1.75)}
T_P10 = {('BTC', '1'): 0.0157, ('BTC', '5'): 0.0574, ('BTC', '15'): 0.125, ('BTC', '30'): 0.198, ('BTC', '60'): 0.318,
         ('BTC', '120'): 0.512, ('BTC', '240'): 0.826, ('XAU', '1'): 0.0101, ('XAU', '5'): 0.0290,
         ('XAU', '15'): 0.0599, ('XAU', '30'): 0.094, ('XAU', '60'): 0.145, ('XAU', '120'): 0.203, ('XAU', '240'): 0.311}
T_LADDER = (1.0, 1.75, 2.5, 3.5, 5.0, 6.5)
T_FLOOR = {'BTC': 0.1, 'XAU': 0.05}
# the Pine's input defaults (FlashGold_Direction_Strategy.pine L106-168, L697-725; SPEC_fgds section 3) and
# the replica controls
SCRIPT_DEFAULTS = dict(
    fgfOn=True, fgfTf="60", fgfLvMode=EP, fgfLast="Until next signal", fgfMinutes=60, fgfBars=1, fgfCheck="Tick",
    fgfBandAtr=0.25, fgfAgainst=True, fgfAllowBuy=True, fgfAllowSell=True,
    fgfSpreadPts=25.0, fgfEntryDistPts=50.0, fgfHoldBars=0, fgfHoldFavPts=5.0, fgfOnePerBar=True,
    fgfDistUnit="ATR", fgfBurstAtr=0.5, fgfEntryDistAtr=0.25, fgfHoldFavAtr=0.1, fgfBurstPts=172.0,
    fgfUseBurst=True, fgfAnyCombo=False, fgfDriftBars=60, fgfUseDrift=False,
    fgfUseZones=True, fgfParentTf="60", fgfRsiLen=14, fgfFastLen=2, fgfMinAligned=2, fgfFlatParent=False,
    fgfIgnoreNa=True, fgfHtfClosed=True,
    fgfUseZ1=True, fgfZTf1="60", fgfUseZ2=True, fgfZTf2="120", fgfUseZ3=True, fgfZTf3="240",
    fgfUseZ4=False, fgfZTf4="480", fgfUseZ5=False, fgfZTf5="1", fgfUseZ6=False, fgfZTf6="2",
    start=None, end=None,
    dsTrigger=ZS, dsDirection="Follow the filter", dsSides="Both", dsZoneExit=True, dsReverse=True,
    dsExitMode="ATR", dsSlPoints=1000.0, dsTpPoints=3000.0, dsAtrLen=14, dsSlAtr=1.0, dsTpR=3.0,
    dsUseTrail=False, dsTrActPts=2000.0, dsTrPts=500.0, dsTrActAtr=2.0, dsTrDstAtr=0.5, dsTimeStop=0,
    dsQtyMode="Risk %", dsFixedQty=1.0, dsRiskPct=0.5, dsMaxQty=50.0, dsQtyStep=0.001, dsCapMargin=True,
    dsMarginPct=1.0,
    path='tv', cost='tv', inv=False)
REPLICA_CONTROLS = {'start', 'end', 'path', 'cost', 'inv'}


def spec_grid(pair=None, tf=None):
    """SPEC_fgds.md section 14: 108 filter settings (filter timeframe x burst x band x level x zones), each
    with "Zone start" and "Signal confirmed" x direction x zone exit x reverse x stop x exit style; on the
    18 with band 0.25 and level "Entry price" also "New signal" x direction x reverse x stop x exit style
    (band, level and zone exit None). The same in every cell."""
    G = []
    for t in ('15', '60', '240'):
        for b in (0.25, 0.5, 1.0):
            for bd in (0.0, 0.25, 0.75):
                for lv in (EP, SCL):
                    for z in (True, False):
                        for trig in (ZS, SC):
                            for inv in (False, True):
                                for ze in (True, False):
                                    for rv in (True, False):
                                        for sl in (0.5, 1.0, 2.0):
                                            for es in ('tp3', 'tp1.5', 'none', 'trail'):
                                                G.append((t, b, bd, lv, z, trig, inv, ze, rv, sl, es))
                        if bd == 0.25 and lv == EP:
                            for inv in (False, True):
                                for rv in (True, False):
                                    for sl in (0.5, 1.0, 2.0):
                                        for es in ('tp3', 'tp1.5', 'none', 'trail'):
                                            G.append((t, b, None, None, z, NS, inv, None, rv, sl, es))
    return G


def fgds_params(p, pair, tf, path='mag', cost='ours', script_sizing=False):
    """A setting (dict over SPEC_DIMS) as the complete fgds param set, written from the spec and the
    orchestrator's decisions: dsMaxQty 1e9 / dsQtyStep 0.000001 on every row (the file's own 50 / 0.001
    with script_sizing). Unused (None): the script's default value."""
    q = dict(SCRIPT_DEFAULTS)
    par, z1, z2, z3 = TFSET.get(p['fgfTf']) or (p['fgfTf'], p['fgfTf'], str(2 * int(p['fgfTf'])), str(4 * int(p['fgfTf'])))
    q.update(fgfTf=p['fgfTf'], fgfParentTf=par, fgfZTf1=z1, fgfZTf2=z2, fgfZTf3=z3, fgfBurstAtr=p['fgfBurstAtr'],
             fgfUseZones=p['fgfUseZones'], dsTrigger=p['dsTrigger'], inv=p['inv'],
             dsDirection='Inverted' if p['inv'] else 'Follow the filter', dsReverse=p['dsReverse'],
             dsSlAtr=p['dsSlAtr'], path=path, cost=cost)
    if p['fgfBandAtr'] is not None:
        q['fgfBandAtr'] = p['fgfBandAtr']
    if p['fgfLvMode'] is not None:
        q['fgfLvMode'] = p['fgfLvMode']
    if p['dsZoneExit'] is not None:
        q['dsZoneExit'] = p['dsZoneExit']
    q['dsTpR'], q['dsUseTrail'] = STYLE[p['exitStyle']]
    if q['dsUseTrail']:
        q['dsTrActAtr'], q['dsTrDstAtr'] = T_TRAIL.get((pair, tf), (2.0, 1.0))
    if not script_sizing:
        q['dsMaxQty'] = 1e9
        q['dsQtyStep'] = 0.000001
    return q


def _split(q):
    """fgds params -> (prepare params, simulate params)."""
    prep = {k: v for k, v in q.items() if k in fgds.PREP_DEFAULTS}
    return prep, {k: v for k, v in q.items() if k not in fgds.PREP_DEFAULTS}


def pine_inputs():
    """name -> (default, minval or None) of every `name = input.<type>(default, ...)` line of the Pine."""
    out = {}
    rx = re.compile(r'^\s*(?:(?:var|varip)\s+)?(?:(?:int|float|bool|string)\s+)?([A-Za-z_]\w*)\s*=\s*'
                    r'input\.(int|float|bool|string|session|timeframe)\(\s*("[^"]*"|[^,)\s]+)')
    with open(PINE, encoding='utf-8') as f:
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
            else:
                v = dv.strip('"')
            mv = re.search(r'minval\s*=\s*([-0-9.eE]+)', line)
            out[name] = (v, float(mv.group(1)) if mv else None)
    return out


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
    fa, fb = float(a), float(b)
    return fa == fb or (fa != fa and fb != fb)


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
    return os.path.join(OUT, 'calib_fgds_%s_%s.parquet' % (pair, tf))


def _fresh(path):
    """A scratch file is used only when it is newer than the runner and the replica."""
    return os.path.exists(path) and os.path.getmtime(path) > max(os.path.getmtime(os.path.join(W, 'calib_fgds.py')),
                                                                 os.path.getmtime(os.path.join(W, 'fgds.py')))


_DF = {}


def _cell_df(pair, tf):
    """(DataFrame, where): out/ when the cell's file exists, else calib_tmp_fgds/w3 (run here if needed)."""
    key = (pair, tf)
    if key not in _DF:
        f = _out_file(pair, tf)
        if os.path.exists(f):
            src = 'out/' + os.path.basename(f)
            if not _fresh(f):
                _p('  note: %s is older than calib_fgds.py or fgds.py' % src)
        else:
            d3 = os.path.join(TMP, 'w3')
            f = os.path.join(d3, 'calib_fgds_%s_%s.parquet' % (pair, tf))
            src = 'calib_tmp_fgds/w3/' + os.path.basename(f)
            if not _fresh(f):
                t0 = time.time()
                C.run_cell(pair, tf, workers=3, out_dir=d3, verbose=False)
                _p('  %s %s has no file in out/: run here with 3 workers into %s (%.1fs)' % (pair, tf, src, time.time() - t0))
                _free()
        _DF[key] = (pd.read_parquet(f), src)
    return _DF[key]


def _free():
    C._free_caches()
    C._G.clear()
    gc.collect()


def _default_sig_idx():
    return [i for i, s in enumerate(C.SIGNALS)
            if (s['fgfTf'], s['fgfBurstAtr'], s['fgfBandAtr'], s['fgfLvMode'], s['fgfUseZones']) == ('60', 0.5, 0.25, EP, True)]


def _run_summary(pair, tf, q):
    """fgds.run (prepare + simulate + summary in one call of the module)."""
    _, s = fgds.run(pair, tf, q)
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


def _own_p10(pair, tf):
    """The 10th percentile over the window of ATR(14) / close in %, computed here from the bar file with
    pandas (Wilder's average as an exponential mean of the true range; the window starts thousands of
    bars into the file, so its seed no longer matters)."""
    t = pq.read_table(os.path.join(W, 'data', '%s_%s.parquet' % (pair, tf)), columns=['high', 'low', 'close', 't_close'])
    h, l, c, tc = (t.column(k).to_numpy() for k in ('high', 'low', 'close', 't_close'))
    pc = np.concatenate(([np.nan], c[:-1]))
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1.0 / 14.0, adjust=False).mean().to_numpy()
    s0, e0 = WIN[pair]
    m = (tc >= s0) & (tc <= e0)
    w0 = int(np.argmax(m))
    return float(np.percentile(atr[m] / c[m] * 100.0, 10)), w0, int(m.sum())


_COUNTS = ('trig_zone_buy', 'trig_zone_sell', 'trig_conf_buy', 'trig_conf_sell', 'trig_new_buy', 'trig_new_sell')


# ---------------------------------------------------------------------------------------------
# 1. the grid
# ---------------------------------------------------------------------------------------------
def test_1_grid():
    """(1) The grid is the full product of section 14, keys unique; DIMS, SIGNALS, EXITS and the fgds params
    of every setting of the 14 cells are what the spec says; the trailing table and its floor; the dimensions
    listed once cannot change a result; normalize(); the files hold the grid."""
    ok = True
    # ---- the product
    S = spec_grid()
    G = C.grid()
    K = [C.key(p) for p in G]
    a = (len(S) == N_GRID == len(set(S)) and len(G) == N_GRID == len(set(K)) and K == S and C.N_GRID == N_GRID
         and N_GRID == 108 * 192 + 18 * 48 and all(C.grid(pair, tf) == G for pair in PAIRS for tf in TFS)
         and all(C.n_settings(pair, tf) == N_GRID for pair in PAIRS for tf in TFS)
         and G == [C.merge(s, x) for s in C.SIGNALS for x in C.exits_for(s)])
    n_tr = {t: sum(1 for k in S if k[5] == t) for t in (ZS, SC, NS)}
    _p('  spec product 21,600 = 108 filter settings x 192 ("Zone start", "Signal confirmed") + 18 x 48 ("New '
       'signal"); the runner\'s grid = the spec\'s, same order, keys unique, the same in all 14 cells: %s (rows per '
       'trigger %s)' % (a, n_tr))
    ok &= a and n_tr == {ZS: 10368, SC: 10368, NS: 864}
    # ---- the two lists
    sk = [tuple(s[k] for k in C.SIGNAL_DIMS) for s in C.SIGNALS]
    xk = [tuple(x[k] for k in C.EXIT_DIMS) for x in C.EXITS]
    n_ex = sorted(set(len(C.exits_for(s)) for s in C.SIGNALS))
    hosts = [s for s in C.SIGNALS if len(C.exits_for(s)) == 240]
    c = (len(sk) == 108 == len(set(sk)) and len(xk) == 240 == len(set(xk)) and n_ex == [192, 240] and len(hosts) == 18
         and all(s['fgfBandAtr'] == 0.25 and s['fgfLvMode'] == EP for s in hosts)
         and list(C.SIGNAL_DIMS) + list(C.EXIT_DIMS) == C.DIM_NAMES and C.signals('BTC', '1') == C.SIGNALS
         and all(None not in s.values() for s in C.SIGNALS)
         and [x for x in C.EXITS if x['dsTrigger'] == NS] == C.EXITS_NEW and all(x['dsZoneExit'] is None for x in C.EXITS_NEW))
    _p('  SIGNALS %d unique (fgds.prepare params = filter settings), EXITS %d unique (fgds.simulate params); exit '
       'settings per signal setting %s; the 18 "New signal" hosts are the settings with band 0.25 and level Entry '
       'price: %s' % (len(set(sk)), len(set(xk)), n_ex, c))
    ok &= c
    # ---- DIMS
    d_ok = [d['name'] for d in C.DIMS] == SPEC_DIMS and len(C.DIMS) == 11 and all(
        {'name', 'values', 'kind'} <= set(d) <= {'name', 'values', 'kind', 'side', 'default', 'unused_when'}
        and d['default'] == SPEC_DEFAULT[d['name']] and type(d['default']) is type(SPEC_DEFAULT[d['name']])
        and d['side'] == SPEC_SIDE[d['name']] and d.get('unused_when') == SPEC_UNUSED.get(d['name'])
        and d['kind'] == SPEC_KIND[d['name']] and d['values'] == SPEC_VALUES[d['name']]
        and [type(v) for v in d['values']] == [type(v) for v in SPEC_VALUES[d['name']]] for d in C.DIMS)
    d_ok &= C.DEFAULT_P == SPEC_DEFAULT and C.DEFAULT is C.DEFAULT_P
    for j, d in enumerate(C.DIMS):
        seen = set(k[j] for k in S if k[j] is not None)
        d_ok &= set(d['values']) == seen and len(d['values']) == len(seen)
    none_ok = all(((k[2] is None) == (k[5] == NS)) and ((k[3] is None) == (k[5] == NS)) and ((k[7] is None) == (k[5] == NS))
                  and all(k[j] is not None for j in range(11) if j not in (2, 3, 7)) for k in S)
    dir_ok = C.DIMS[6]['name'] == 'inv' and C.DIMS[6]['kind'] == 'categorical' and C.DIMS[6]['values'] == [False, True] \
        and not any(d['name'] in ('fgfOn', 'filter') for d in C.DIMS)
    _p('  DIMS: %d dimensions %s; values, kinds, sides, defaults as specified: %s; None only for fgfBandAtr, fgfLvMode '
       'and dsZoneExit with "New signal", and always there: %s; the direction dimension is named inv, and there is no '
       'filter dimension: %s' % (len(C.DIMS), [d['name'] for d in C.DIMS], d_ok, none_ok, dir_ok))
    ok &= d_ok and none_ok and dir_ok
    try:
        json.dumps(C.DIMS)
    except Exception as e:      # noqa: BLE001
        ok = False
        _p('  DIMS is not JSON: %r' % (e,))
    # ---- the script defaults: this file's copy, the module's, the Pine's own input lines
    m_ok = fgds.DEFAULTS == SCRIPT_DEFAULTS
    if not m_ok:
        _p('  fgds.DEFAULTS differ from the script defaults written here: %r'
           % {k: (fgds.DEFAULTS.get(k), SCRIPT_DEFAULTS.get(k)) for k in set(fgds.DEFAULTS) | set(SCRIPT_DEFAULTS)
              if fgds.DEFAULTS.get(k) != SCRIPT_DEFAULTS.get(k)})
    pin = pine_inputs()
    found = [k for k in SCRIPT_DEFAULTS if k in pin]
    diff = {k: (SCRIPT_DEFAULTS[k], pin[k][0]) for k in found
            if not (SCRIPT_DEFAULTS[k] == pin[k][0] and isinstance(SCRIPT_DEFAULTS[k], bool) == isinstance(pin[k][0], bool))}
    missing = sorted(set(SCRIPT_DEFAULTS) - set(found) - REPLICA_CONTROLS)
    pd_dims = {k: pin[k][0] for k in SPEC_DIMS if k in pin}
    pd_dims['inv'] = pin['dsDirection'][0] == 'Inverted'
    pd_dims['exitStyle'] = 'tp3' if (pin['dsTpR'][0], pin['dsUseTrail'][0]) == STYLE['tp3'] else None
    p_ok = (not diff and not missing and pd_dims == SPEC_DEFAULT
            and pin['dsQtyStep'] == (0.001, 0.000001) and pin['dsMaxQty'][0] == 50.0 and pin['dsRiskPct'][0] == 0.5
            and pin['fgfOn'][0] is True and pin['dsCapMargin'][0] is True and pin['dsMarginPct'][0] == 1.0
            and (pin['fgfParentTf'][0], pin['fgfZTf1'][0], pin['fgfZTf2'][0], pin['fgfZTf3'][0]) == TFSET[pin['fgfTf'][0]]
            and C.SCALE_FREE == {'dsMaxQty': 1e9, 'dsQtyStep': 0.000001}
            and C.SCRIPT_SIZING == {'dsMaxQty': 50.0, 'dsQtyStep': 0.001}
            and C.SCALE_FREE['dsQtyStep'] >= pin['dsQtyStep'][1])
    _p('  script defaults: fgds.DEFAULTS = the %d written here: %s; the Pine file\'s own input lines give the same '
       'default for %d of them (different: %s; not found: %s); the 11 dimensions\' Pine defaults = DEFAULT_P (the '
       'default parent / zones = the "60" set): %s; the Pine\'s quantity step 0.001 (minval 0.000001 = the grid\'s '
       'step), max quantity 50, risk 0.5 %%, margin cap 1 %%: %s'
       % (len(SCRIPT_DEFAULTS), m_ok, len(found), diff or 'none', missing or 'none', pd_dims == SPEC_DEFAULT, p_ok))
    ok &= m_ok and p_ok
    # ---- the trailing pair of every cell, and the floor of the table recomputed from the bar files
    t_ok = True
    parts = []
    for pair in PAIRS:
        for tf in TFS:
            act, dst = T_TRAIL.get((pair, tf), (2.0, 1.0))
            p10, w0, n = _own_p10(pair, tf)
            d_small = next((x for x in T_LADDER if x * p10 >= T_FLOOR[pair]), None)
            tol = 0.0006 if T_P10[(pair, tf)] >= 0.06 else 0.00006        # the table prints 3 / 4 decimals
            c_ok = (C.trail_pair(pair, tf) == (act, dst) and act == 2 * dst and d_small == dst
                    and abs(p10 - T_P10[(pair, tf)]) <= tol and dst * p10 >= T_FLOOR[pair] and w0 > 1000
                    and C.FLOOR_PCT[pair] == T_FLOOR[pair])
            t_ok &= c_ok
            parts.append('%s %s %.4f%% x %g = %.4f%%%s' % (pair, tf, p10, dst, dst * p10, '' if c_ok else ' WRONG'))
    _p('  trailing pair (2d, d) of every cell = the table of section 14, d = the smallest of %s with d x the 10th '
       'percentile of ATR(14)/close >= the floor (BTC 0.1 %%, XAU 0.05 %%), percentile recomputed here from the bar '
       'files and equal to the table\'s: %s' % (list(T_LADDER), t_ok))
    _p('    ' + '; '.join(parts))
    ok &= t_ok and tuple(C.TRAIL_LADDER) == T_LADDER
    # ---- the fgds params of every setting, all 14 cells
    n_bad = n_all = 0
    def_ok = True
    for pair in PAIRS:
        for tf in TFS:
            for p in G:
                sp = C.signal_params({k: p[k] for k in C.SIGNAL_DIMS})
                xp = C.exit_params({k: p[k] for k in C.EXIT_DIMS}, pair, tf)
                fake = {'sim': dict(fgds.SIM_DEFAULTS), 'prep': dict(fgds.PREP_DEFAULTS, **sp)}
                Q = fgds.resolve(fake, xp)
                fp = fgf._params(dict(fgf.DEFAULTS, **sp))
                eff = dict(fp, start=None, end=None)
                eff.update(Q)
                want = fgds_params(p, pair, tf)
                n_all += 1
                if eff != want or (set(sp) - set(fgds.PREP_DEFAULTS)) or (set(xp) & set(fgds.PREP_DEFAULTS)):
                    n_bad += 1
                    if n_bad <= 3:
                        _p('  MAPPING %s %s %r: %r' % (pair, tf, p, {k: (eff.get(k), want.get(k)) for k in set(want) | set(eff)
                                                                      if eff.get(k) != want.get(k)}))
            sp = C.signal_params({k: SPEC_DEFAULT[k] for k in C.SIGNAL_DIMS})
            Q = fgds.resolve({'sim': dict(fgds.SIM_DEFAULTS), 'prep': dict(fgds.PREP_DEFAULTS, **sp)},
                             C.exit_params({k: SPEC_DEFAULT[k] for k in C.EXIT_DIMS}, pair, tf))
            eff_d = dict(fgf._params(dict(fgf.DEFAULTS, **sp)), start=None, end=None)
            eff_d.update(Q)
            def_ok &= (K.count(C.key(SPEC_DEFAULT)) == 1
                       and eff_d == dict(SCRIPT_DEFAULTS, path='mag', cost='ours', dsMaxQty=1e9, dsQtyStep=0.000001))
    def_ok &= C.PATH == 'mag' and C.COST == 'ours'
    _p('  fgds params of all %d settings of the 14 cells (signal_params + exit_params, resolved by fgf._params and '
       'fgds.resolve) = the mapping written here (%d keys each; dsMaxQty 1e9, dsQtyStep 0.000001, the cell\'s trailing '
       'pair, fgfTf with its parent / zones): %d different; signal params only prepare keys, exit params only simulate '
       'keys' % (n_all, len(SCRIPT_DEFAULTS), n_bad))
    _p('  the script\'s default setting is one row of the grid; its params = the script defaults with path mag, cost '
       'ours and the scale-free sizing: %s' % def_ok)
    ok &= n_bad == 0 and def_ok
    # ---- normalize: every grid row round-trips, as the file gives it (p_ prefix, NaN or None for unused)
    n_rt = sum(C.normalize({'p_' + k: (float('nan') if v is None else v) for k, v in p.items()}) == p
               and C.normalize({k: v for k, v in p.items() if v is not None}) == p for p in G)
    forced = C.normalize(dict(SPEC_DEFAULT, dsTrigger=NS, fgfBandAtr=0.75, fgfLvMode=SCL, dsZoneExit=False))
    r_ok = (n_rt == len(G) and forced['fgfBandAtr'] is None and forced['fgfLvMode'] is None and forced['dsZoneExit'] is None
            and C.row_of('BTC', '240', forced) is not None and C.row_of('BTC', '240', SPEC_DEFAULT) == K.index(C.key(SPEC_DEFAULT))
            and C.normalize(dict(SPEC_DEFAULT, fgfTf=60)) == SPEC_DEFAULT)
    refused = []
    for name, q, og in (('Zone start without a band', dict(SPEC_DEFAULT, fgfBandAtr=None), False),
                        ('band not in the grid', dict(SPEC_DEFAULT, fgfBandAtr=0.5), False),
                        ('filter timeframe not in the grid', dict(SPEC_DEFAULT, fgfTf='30'), False),
                        ('unknown exit style', dict(SPEC_DEFAULT, exitStyle='tp5'), True),
                        ('unknown trigger', dict(SPEC_DEFAULT, dsTrigger='Zone end'), True),
                        ('fgfOn is not a dimension', dict(SPEC_DEFAULT, fgfOn=False), True),
                        ('inv not a boolean', dict(SPEC_DEFAULT, inv='yes'), False)):
        try:
            C.normalize(q, off_grid=og)
            refused.append((name, False))
        except ValueError:
            refused.append((name, True))
    kept = C.normalize(dict(SPEC_DEFAULT, fgfTf='30', fgfBandAtr=0.5), off_grid=True)
    r_ok &= all(v for _, v in refused) and kept['fgfTf'] == '30' and C.row_of('BTC', '240', kept) is None
    _p('  normalize(): %d of %d grid rows round-trip (p_ prefix, NaN / missing for unused); band / level / zone exit '
       'given with "New signal" are dropped (the row is the grid\'s); refused: %s; --off-grid keeps fgfTf "30" and band '
       '0.5 (not a grid row): %s' % (n_rt, len(G), ', '.join('%s %s' % (n, 'yes' if v else 'NO') for n, v in refused), r_ok))
    ok &= r_ok
    # ---- on data: the dimensions listed once cannot change a result
    rng = np.random.default_rng(20261126)
    cnt = dict(new_band=0, new_ze=0, trail=0, new_arr=0)
    dif = dict(new_band=0, new_ze=0, trail=0, new_arr=0)
    for pair, tf in CELLS:
        sub = None
        for hi in rng.choice(18, size=3, replace=False):
            host = [s for s in C.SIGNALS if C.is_new_host(s)][int(hi)]
            sibs = [s for s in C.SIGNALS if all(s[k] == host[k] for k in ('fgfTf', 'fgfBurstAtr', 'fgfUseZones'))]
            assert len(sibs) == 6
            Ph = fgds.prepare(pair, tf, C.signal_params(host))
            sub = sub or fgds.get_sub(Ph)
            Ph['sub'] = sub
            for sib in sibs:
                if sib is host:
                    continue
                Ps = fgds.prepare(pair, tf, C.signal_params(sib))
                Ps['sub'] = sub
                cnt['new_arr'] += 1
                dif['new_arr'] += not (np.array_equal(Ps['newBuy'], Ph['newBuy']) and np.array_equal(Ps['newSell'], Ph['newSell']))
                for i in rng.choice(len(C.EXITS_NEW), size=3, replace=False):
                    xp = C.exit_params(C.EXITS_NEW[int(i)], pair, tf)
                    s0 = fgds.summary(Ph, fgds.simulate(Ph, xp))
                    s1 = fgds.summary(Ps, fgds.simulate(Ps, xp))
                    cnt['new_band'] += 1
                    dif['new_band'] += not all(_same(s0[k], s1[k]) for k in s0 if k not in _COUNTS[:4])
                del Ps
            for i in rng.choice(len(C.EXITS_NEW), size=6, replace=False):
                xp = C.exit_params(C.EXITS_NEW[int(i)], pair, tf)
                s0 = fgds.summary(Ph, fgds.simulate(Ph, xp))
                s1 = fgds.summary(Ph, fgds.simulate(Ph, dict(xp, dsZoneExit=False)))
                cnt['new_ze'] += 1
                dif['new_ze'] += not all(_same(s0[k], s1[k]) for k in s0)
            offs = [x for x in C.EXITS if x['exitStyle'] != 'trail']
            for i in rng.choice(len(offs), size=8, replace=False):
                xp = C.exit_params(offs[int(i)], pair, tf)
                s0 = fgds.summary(Ph, fgds.simulate(Ph, xp))
                sa = fgds.summary(Ph, fgds.simulate(Ph, dict(xp, dsTrActAtr=0.5, dsTrDstAtr=0.05)))
                sb = fgds.summary(Ph, fgds.simulate(Ph, dict(xp, dsTrActAtr=13.0, dsTrDstAtr=6.5)))
                cnt['trail'] += 1
                dif['trail'] += not all(_same(s0[k], sa[k]) and _same(s0[k], sb[k]) for k in s0)
            del Ph
        _free()
    u_ok = all(v == 0 for v in dif.values()) and all(v > 0 for v in cnt.values())
    _p('  on data (%s): settings with a different result / settings tried: "New signal" on the prepared input of '
       'another band / level (the trigger counts of P aside) %d/%d, and its newBuy / newSell arrays differ in %d/%d '
       'prepared inputs; "New signal" with dsZoneExit False %d/%d; other trailing distances with the trailing stop off '
       '%d/%d: %s' % (', '.join('%s %s' % c for c in CELLS), dif['new_band'], cnt['new_band'], dif['new_arr'],
                      cnt['new_arr'], dif['new_ze'], cnt['new_ze'], dif['trail'], cnt['trail'], u_ok))
    ok &= u_ok
    # ---- the files
    fd = os.path.join(OUT, 'calib_fgds_dims.json')
    if os.path.exists(fd):
        same = json.load(open(fd)) == C.DIMS
        _p('  out/calib_fgds_dims.json equals DIMS: %s' % same)
        ok &= same
    else:
        _p('  out/calib_fgds_dims.json: not written yet')
    # ---- the provenance written into a file is the code this process imported: file_meta must not read
    # fgds.py / fgf.py again when a file is written
    o_sha = C._sha256
    C._sha256 = lambda path: 'read again at write time'
    try:
        m2 = C.file_meta('XAU', '240', N_GRID)
    finally:
        C._sha256 = o_sha
    prov = (m2['fgds_sha256'] == C._SRC_SHA['fgds'] and m2['fgf_sha256'] == C._SRC_SHA['fgf']
            and len(m2['fgds_sha256']) == 64 == len(m2['fgf_sha256'])
            and os.path.samefile(fgds.__file__, os.path.join(W, 'fgds.py')) and os.path.samefile(fgf.__file__, os.path.join(W, 'fgf.py')))
    _p('  file metadata: the sha256 of fgds.py and fgf.py is the one taken when the runner imported them, not read '
       'again when a file is written: %s' % prov)
    ok &= prov
    cols_want = None
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        if cols_want is None:
            Pp = fgds.prepare(pair, tf, {})
            s = fgds.summary(Pp, fgds.simulate(Pp, {'path': 'mag', 'cost': 'ours'}))
            cols_want = list(s.keys())
            scalar = all(isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool) for v in s.values())
            del Pp
        keys = _keys(df)
        ins_ok = all(_same(_py(df[c].iat[i]), C_in[c]) for i in range(0, len(df), 97)
                     for C_in in [_inputs_here(dict(zip(SPEC_DIMS, keys[i])), pair, tf)] for c in C.INPUT_NAMES)
        f_ok = (len(df) == N_GRID and keys == spec_grid() and ins_ok
                and list(df.columns) == _pcols() + list(C.INPUT_NAMES) + ['floor_ok'] + cols_want and scalar
                and all(k in cols_want for k in SUM_REQUIRED) and df['floor_ok'].dtype == bool and bool(df['floor_ok'].all()))
        nulls = {c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().any()}
        ns = (df['p_dsTrigger'] == NS).to_numpy()
        tr_rows = (df['p_exitStyle'] == 'trail').to_numpy()
        no_tr = (df['trades'] == 0).to_numpy()
        f_ok &= (set(nulls) <= {'p_fgfBandAtr', 'p_fgfLvMode', 'p_dsZoneExit', 'dsTrActAtr', 'dsTrDstAtr', 'pf', 'win_pct',
                                'avg_bars_held'}
                 and all(np.array_equal(df[c].isna().to_numpy(), ns) for c in ('p_fgfBandAtr', 'p_fgfLvMode', 'p_dsZoneExit'))
                 and all(np.array_equal(df[c].isna().to_numpy(), ~tr_rows) for c in ('dsTrActAtr', 'dsTrDstAtr'))
                 and all(np.array_equal(df[c].isna().to_numpy(), no_tr) for c in ('pf', 'win_pct', 'avg_bars_held')))
        _p('  %s: %d rows; p_ columns = the grid in order; columns = %d p_ + the %d Pine inputs of fgfTf / exitStyle + '
           'floor_ok (True on every row) + the %d fields of fgds.summary (all scalars), nothing else: %s (null / NaN: %s)'
           % (src, len(df), len(_pcols()), len(C.INPUT_NAMES), len(cols_want), f_ok, nulls or 'none'))
        ok &= f_ok
        meta = C.read_meta(os.path.join(W, src))
        now = C.file_meta(pair, tf, N_GRID)
        m_ok = meta is not None and all(meta.get(k) == now[k] for k in (
            'strategy', 'pair', 'tf', 'path', 'cost', 'settings', 'window', 'dsMaxQty', 'dsQtyStep', 'fgfOn',
            'dsTrActAtr', 'dsTrDstAtr', 'exit_styles', 'new_signal_host')) and bool((meta.get('floor') or {}).get('floor_ok'))
        cur = meta is not None and meta.get('fgds_sha256') == now['fgds_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
        _p('    file metadata: %s, path %s, cost %s, %s settings, dsMaxQty %s, dsQtyStep %s, trailing (%s, %s): %s; '
           'written with the fgds.py and fgf.py now on disk: %s'
           % ((meta or {}).get('strategy'), (meta or {}).get('path'), (meta or {}).get('cost'),
              (meta or {}).get('settings'), (meta or {}).get('dsMaxQty'), (meta or {}).get('dsQtyStep'),
              (meta or {}).get('dsTrActAtr'), (meta or {}).get('dsTrDstAtr'), m_ok,
              cur if cur else 'NO (rows are still checked against the module by tests 2, 3 and 7)'))
        ok &= m_ok
    _free()
    return ok


def _inputs_here(p, pair, tf):
    """The Pine inputs that fgfTf and exitStyle set (this file's reading of section 14)."""
    par, z1, z2, z3 = TFSET[p['fgfTf']]
    tp, tr = STYLE[p['exitStyle']]
    act, dst = T_TRAIL.get((pair, tf), (2.0, 1.0)) if tr else (None, None)
    return {'fgfParentTf': par, 'fgfZTf1': z1, 'fgfZTf2': z2, 'fgfZTf3': z3, 'dsTpR': tp, 'dsUseTrail': tr,
            'dsTrActAtr': act, 'dsTrDstAtr': dst}


# ---------------------------------------------------------------------------------------------
# 2. the default rows against the saved results
# ---------------------------------------------------------------------------------------------
def _one(pair, tf, p, *extra):
    cmd = [sys.executable, '-I', os.path.join(W, 'calib_fgds.py'), '--one', pair, tf, json.dumps(p)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _json_ref(sv, cols):
    """A saved run of out/inv_fgds_*.json as python values (its writer stores NaN as null, inf as 'inf')."""
    ref = {}
    for k in cols:
        v = sv[k]
        ref[k] = float('nan') if v is None else (float(v) if isinstance(v, str) else v)
    return ref


def _p_trig(trig, inv):
    """The default setting with another trigger / direction (as the grid lists it)."""
    p = dict(SPEC_DEFAULT, dsTrigger=trig, inv=inv)
    if trig == NS:
        p.update(fgfBandAtr=None, fgfLvMode=None, dsZoneExit=None)
    return p


_GROUP_TRIG = {'runs': ZS, 'runs_conf': SC, 'runs_new': NS}


def test_2_default_rows():
    """(2) The default row with --script-sizing, and the same with inv true, equal the saved default results of
    the module with the same path and cost (out/inv_fgds_<PAIR>_<TF>.json runs normal/on/mag/ours and
    inverted/on/mag/ours): through the command line on BTC 60 and XAU 240, through calib_fgds.one on every saved
    filter-on run of all 14 cells; and the scale-free default rows of the sweep equal fgds.run called directly, and so
    does every row of the default signal setting (the cell's own trailing pair) in all 14 cells."""
    ok = True
    Pp = fgds.prepare('XAU', '240', {})
    sc = list(fgds.summary(Pp, fgds.simulate(Pp, {})).keys())
    del Pp
    dp = dict(SPEC_DEFAULT)
    # ---- (a) the command line, BTC 60 and XAU 240
    for pair, tf in (('BTC', '60'), ('XAU', '240')):
        J = json.load(open(os.path.join(OUT, 'inv_fgds_%s_%s.json' % (pair, tf))))
        cases = (
            ('runs', 'normal/on/mag/ours', dp, ('--script-sizing',)),
            ('runs', 'inverted/on/mag/ours', dict(dp, inv=True), ('--script-sizing',)),
            ('runs', 'normal/on/tv/script', dp, ('--script-sizing', '--path', 'tv', '--cost', 'tv')),
            ('runs', 'inverted/on/tv/script', dict(dp, inv=True), ('--script-sizing', '--path', 'tv', '--cost', 'tv')),
            ('runs', 'inverted/on/mag/script', dict(dp, inv=True), ('--script-sizing', '--cost', 'tv')),
            ('runs_conf', 'normal/on/mag/ours', _p_trig(SC, False), ('--script-sizing',)),
            ('runs_conf', 'inverted/on/mag/ours', _p_trig(SC, True), ('--script-sizing',)),
            ('runs_new', 'normal/on/mag/ours', _p_trig(NS, False), ('--script-sizing',)),
            ('runs_new', 'inverted/on/mag/ours', _p_trig(NS, True), ('--script-sizing',)),
        )
        bad = []
        n_vals = 0
        first = {}
        for group, key, p, extra in cases:
            rc, out, err = _one(pair, tf, p, *extra)
            if rc != 0:
                bad.append('%s %s: exit code %d %s' % (group, key, rc, err.strip()[-200:]))
                continue
            o = json.loads(out)
            st = o.pop('setting')
            want = (('sizing', 'script'), ('dsMaxQty', 50.0), ('dsQtyStep', 0.001), ('in_grid', True),
                    ('path', 'tv' if '--path' in extra else 'mag'), ('cost', 'tv' if '--cost' in extra else 'ours'))
            if any(st.get(k) != v for k, v in want) or list(o) != list(C.INPUT_NAMES) + ['floor_ok'] + sc:
                bad.append('%s %s: setting echoed as %r' % (group, key, st))
            n_vals += _cmp(o, _json_ref(J[group][key], sc), sc, '%s %s' % (group, key), bad)
            first.setdefault((group, key), o)
        # the same default row with the grid's sizing (what the sweep stores): another number, by design
        rc, out, err = _one(pair, tf, dp)
        o = json.loads(out) if rc == 0 else None
        rc2, out2, _ = _one(pair, tf, dict(dp, inv=True))
        o2 = json.loads(out2) if rc2 == 0 else None
        d = first.get(('runs', 'normal/on/mag/ours'))
        d2 = first.get(('runs', 'inverted/on/mag/ours'))
        _p('  %s %-3s command line: default row --script-sizing = saved runs normal/on/mag/ours, and with inv true = '
           'inverted/on/mag/ours; also tv / script costs, mag / script costs, "Signal confirmed" and "New signal" (runs_conf, '
           'runs_new): %d runs, %d values: %s' % (pair, tf, len(cases), n_vals,
                                                  'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b))))
        if o is not None and d is not None and o2 is not None and d2 is not None:
            for nm, a_, b_ in (('normal', d, o), ('inverted', d2, o2)):
                _p('    default row %-8s script sizing (the published file): %d trades, net %+.3f %%, h1r %+.3f %%, h2r '
                   '%+.3f %%, zero_qty %d, capped at 50: %d | scale-free sizing (grid row %d): %d trades, net %+.3f %%, '
                   'h1r %+.3f %%, h2r %+.3f %%, zero_qty %d'
                   % (nm, a_['trades'], a_['net_pct'], a_['h1r_pct'], a_['h2r_pct'], a_['zero_qty'], a_['qty_capped_max'],
                      b_['setting']['row'], b_['trades'], b_['net_pct'], b_['h1r_pct'], b_['h2r_pct'], b_['zero_qty']))
        ok &= not bad and n_vals == len(cases) * len(sc) and o is not None and o['setting']['sizing'] == 'scale-free' \
            and o['setting']['dsQtyStep'] == 0.000001 and o['setting']['dsMaxQty'] == 1e9 \
            and o['setting']['row'] == C.row_of(pair, tf, dp) and o2 is not None
    # ---- (b) every saved run of all 14 cells through calib_fgds.one (script sizing)
    tot = dict(cells=0, runs=0, vals=0, off=0)
    for pair in PAIRS:
        for tf in TFS:
            J = json.load(open(os.path.join(OUT, 'inv_fgds_%s_%s.json' % (pair, tf))))
            cache = {}
            bad = []
            n_runs = n_vals = n_off = 0
            if not set(sc) <= set(J['runs']['normal/on/mag/ours']):
                bad.append('the saved runs miss fields: %s' % (set(sc) - set(J['runs']['normal/on/mag/ours'])))
            for g, trig in _GROUP_TRIG.items():
                for key, sv in J[g].items():
                    dname, flt, path, cname = key.split('/')
                    if flt == 'off':
                        # no filter-off dimension: the filter off trades nothing, in every cell
                        n_off += 1
                        if sv['trades'] != 0 or sv['orders_placed'] != 0 or sv['net_pct'] != 0:
                            bad.append('%s %s: a filter-off run with trades' % (g, key))
                        continue
                    p = _p_trig(trig, dname == 'inverted')
                    o = C.one(pair, tf, p, path, 'tv' if cname == 'script' else 'ours', False, True, cache)
                    n_vals += _cmp(o, _json_ref(sv, sc), sc, '%s %s' % (g, key), bad)
                    n_runs += 1
            d = J['runs']['normal/on/mag/ours']
            _p('  %s %-3s: %d saved filter-on runs (runs, runs_conf, runs_new) = calib_fgds.one with script sizing: %d '
               'values: %s; %d saved filter-off runs: no trade | saved default mag / ours: %d trades, net %+.3f %%, '
               'zero_qty %d, capped at 50: %d'
               % (pair, tf, n_runs, n_vals, 'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                  n_off, d['trades'], d['net_pct'], d['zero_qty'], d['qty_capped_max']))
            ok &= not bad and n_runs == 24 and n_off == 24
            tot['cells'] += 1
            tot['runs'] += n_runs
            tot['vals'] += n_vals
            tot['off'] += n_off
            del cache
            _free()
    _p('  %d cells: %d saved filter-on runs, %d values compared; %d filter-off runs without a trade'
       % (tot['cells'], tot['runs'], tot['vals'], tot['off']))
    ok &= tot['cells'] == 14
    # ---- (c) the scale-free default rows of the sweep = fgds.run called directly
    di = _default_sig_idx()
    n_cells = 0
    for pair in PAIRS:
        for tf in TFS:
            if os.path.exists(_out_file(pair, tf)) or (pair, tf) in _DF:
                df, src = _cell_df(pair, tf)
            elif FILES_ONLY:
                continue
            else:
                df, _ = C.run_cell(pair, tf, workers=3, sig_idx=di, write=False, verbose=False)
                src = '%d rows run here' % len(df)
            idx = {k: i for i, k in enumerate(_keys(df))}
            base = {'path': 'mag', 'cost': 'ours', 'dsMaxQty': 1e9, 'dsQtyStep': 0.000001}
            bad = []
            n_vals = 0
            rows = {}
            for trig in (ZS, SC, NS):
                for inv in (False, True):
                    name = '%s %s' % (trig, 'inverted' if inv else 'normal')
                    row = df.iloc[idx[tuple(_p_trig(trig, inv)[k] for k in SPEC_DIMS)]]
                    q = dict(base, dsTrigger=trig, dsDirection='Inverted' if inv else 'Follow the filter')
                    n_vals += _cmp(row, _run_summary(pair, tf, q), sc, name, bad)
                    rows[name] = row
            d = rows['Zone start normal']
            _p('  %s %-3s (%s): default rows ("Zone start" / "Signal confirmed" / "New signal" x normal / inverted) = '
               'fgds.run with path mag, cost ours, dsMaxQty 1e9, dsQtyStep 0.000001: %d values: %s | default row: %d '
               'trades, net %+.3f %%, h1r %+.3f %%, h2r %+.3f %%, zero_qty %d'
               % (pair, tf, src, n_vals, 'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                  d['trades'], d['net_pct'], d['h1r_pct'], d['h2r_pct'], d['zero_qty']))
            ok &= not bad and n_vals == 6 * len(sc)
            # every row of the default signal setting (192 + 48 "New signal" = 240, a quarter of them with the
            # trailing stop and the CELL'S trailing pair) through the sweep's path, against the module run here
            # with this file's own mapping: the only check of the sweep path on the cells whose trailing pair is
            # not the 240-minute one (BTC / XAU 1 and 5) before their files exist
            keys = _keys(df)
            mine = [i for i, k in enumerate(keys) if (k[0], k[1], k[4]) == ('60', 0.5, True)
                    and (k[5] == NS or (k[2], k[3]) == (0.25, EP))]
            prep, _ = _split(fgds_params(dict(zip(SPEC_DIMS, keys[mine[0]])), pair, tf))
            Pd = fgds.prepare(pair, tf, prep)
            bad2 = []
            n2 = n_tr = 0
            for i in mine:
                p = dict(zip(SPEC_DIMS, keys[i]))
                pr, sim = _split(fgds_params(p, pair, tf))
                assert pr == prep
                s = fgds.summary(Pd, fgds.simulate(Pd, sim))
                n2 += _cmp(df.iloc[i], s, sc, 'row %d' % i, bad2)
                n_tr += p['exitStyle'] == 'trail'
                if p['exitStyle'] == 'trail' and (df['dsTrActAtr'].iat[i], df['dsTrDstAtr'].iat[i]) != (sim['dsTrActAtr'], sim['dsTrDstAtr']):
                    bad2.append('row %d: trailing columns %r' % (i, (df['dsTrActAtr'].iat[i], df['dsTrDstAtr'].iat[i])))
            del Pd
            _p('    every row of the default signal setting (%d rows, %d with the trailing stop (%g, %g)) = fgds.prepare + '
               'fgds.simulate with the mapping written here: %d values: %s'
               % (len(mine), n_tr, *T_TRAIL.get((pair, tf), (2.0, 1.0)), n2,
                  'all equal' if not bad2 else '%d DIFFERENCES: %s' % (len(bad2), '; '.join(b for b in bad2 if b))))
            ok &= not bad2 and len(mine) == 240 and n_tr == 60 and n2 == 240 * len(sc)
            n_cells += 1
            _free()
    _p('  %d cells: the scale-free default rows equal fgds.run called directly' % n_cells)
    return ok and n_cells > 0


# ---------------------------------------------------------------------------------------------
# 3. random rows through --one
# ---------------------------------------------------------------------------------------------
def test_3_one_rows():
    """(3) 30 random rows per cell recomputed one at a time through `calib_fgds.py --one` (a new process each,
    the row's p_ columns as its JSON) equal the sweep rows on every non-p_ column; the same rows through fgds.run
    with this file's own mapping; --path / --cost and --script-sizing are honoured; --off-grid; bad input is
    refused."""
    ok = True
    rng = np.random.default_rng(31)
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
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
            par, z1, z2, z3 = TFSET[p['fgfTf']]
            filt = {'fgfOn': True, 'fgfTf': p['fgfTf'], 'fgfParentTf': par, 'fgfZTf1': z1, 'fgfZTf2': z2, 'fgfZTf3': z3,
                    'fgfBurstAtr': p['fgfBurstAtr'], 'fgfBandAtr': 0.25 if p['fgfBandAtr'] is None else p['fgfBandAtr'],
                    'fgfLvMode': EP if p['fgfLvMode'] is None else p['fgfLvMode'], 'fgfUseZones': p['fgfUseZones']}
            if st != {'strategy': 'fgds', 'pair': pair, 'tf': tf, 'path': 'mag', 'cost': 'ours', 'p': p, 'in_grid': True,
                      'row': i, 'sizing': 'scale-free', 'dsMaxQty': 1e9, 'dsQtyStep': 0.000001, 'filter': filt,
                      'cell_trail': list(T_TRAIL.get((pair, tf), (2.0, 1.0)))}:
                bad.append('row %d: setting echoed as %r' % (i, st))
            if list(o) != rc_cols:
                bad.append('row %d: fields %r' % (i, list(o)))
                continue
            n_vals += _cmp(row, o, rc_cols, 'row %d --one' % i, bad)
            ref = _run_summary(pair, tf, fgds_params(p, pair, tf))
            n_run += _cmp(row, ref, sc, 'row %d fgds.run' % i, bad)
            n_tr += int(row['trades'])
        dt = time.time() - t0
        cov = all(len(cover[d['name']] - {None}) >= 2 for d in C.DIMS)
        _p('  %s %s (%s): 30 random rows, each in its own `--one` process: %d values (inputs, floor_ok, summary), and '
           'through fgds.run with the mapping written here: %d values (%d trades): %s; at least two values of every '
           'dimension among them: %s (%.1fs)'
           % (pair, tf, src, n_vals, n_run, n_tr,
              'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)), cov, dt))
        ok &= not bad and n_vals == 30 * len(rc_cols) and n_run == 30 * len(sc)
        # --path / --cost, and the control that is not a dimension
        bad = []
        n = 0
        moved = 0
        sub = [pick[j] for j in (0, 9, 19, 29)]
        for i in sub:
            row = df.iloc[i]
            p = dict(zip(SPEC_DIMS, keys[i]))
            for extra, kw in (
                    (('--path', 'tv', '--cost', 'tv'), dict(path='tv', cost='tv')),
                    (('--path', 'tv', '--cost', 'stress'), dict(path='tv', cost='stress')),
                    (('--path', 'mag', '--cost', 'stress'), dict(path='mag', cost='stress')),
                    (('--script-sizing',), dict(script_sizing=True)),
                    (('--script-sizing', '--path', 'tv', '--cost', 'tv'), dict(script_sizing=True, path='tv', cost='tv'))):
                rc, out, err = _one(pair, tf, p, *extra)
                if rc != 0:
                    bad.append('row %d %s: exit code %d' % (i, ' '.join(extra), rc))
                    continue
                o = json.loads(out)
                st = o['setting']
                if (st['path'], st['cost'], st['sizing'], st['dsQtyStep'], st['dsMaxQty'], st['row']) != (
                        kw.get('path', 'mag'), kw.get('cost', 'ours'), 'script' if kw.get('script_sizing') else 'scale-free',
                        0.001 if kw.get('script_sizing') else 0.000001, 50.0 if kw.get('script_sizing') else 1e9, i):
                    bad.append('row %d %s: echoed %r' % (i, ' '.join(extra), st))
                ref = _run_summary(pair, tf, fgds_params(p, pair, tf, **kw))
                n += _cmp(o, ref, sc, 'row %d %s' % (i, ' '.join(extra)), bad)
                if extra == ('--script-sizing',):
                    moved += not all(_same(o[k], _py(row[k])) for k in sc)
        _p('  %s %s: 4 rows x (--path tv --cost tv | --path tv --cost stress | --path mag --cost stress | '
           '--script-sizing | --script-sizing --path tv --cost tv) = fgds.run with that path, cost and sizing: %d '
           'values: %s; rows whose result moves with --script-sizing (dsMaxQty 50, dsQtyStep 0.001): %d of 4'
           % (pair, tf, n, 'all equal' if not bad else '; '.join(b for b in bad if b), moved))
        ok &= not bad and moved > 0
        _free()
    # bad input
    pair, tf = CELLS[0]
    p = dict(SPEC_DEFAULT)
    cases = (('unknown dimension', dict(p, dsRiskPct=2.0), ()),
             ('fgfOn is not a dimension', dict(p, fgfOn=False), ()),
             ('value not in the grid', dict(p, dsSlAtr=1.5), ()),
             ('filter timeframe not in the grid', dict(p, fgfTf='30'), ()),
             ('missing used dimension', {k: v for k, v in p.items() if k != 'inv'}, ()),
             ('Zone start without a band', dict(p, fgfBandAtr=None), ()),
             ('unknown exit style', dict(p, exitStyle='tp5'), ('--off-grid',)),
             ('below the Pine minimum', dict(p, dsSlAtr=0.001), ('--off-grid',)),
             ('not an object', [1, 2], ()))
    res = []
    for name, q, extra in cases:
        rc, out, err = _one(pair, tf, q, *extra)
        res.append((name, rc, out.strip() == '' and 'calib_fgds.py --one' in err))
    q = dict(p, fgfTf='30', fgfBurstAtr=0.75, fgfBandAtr=0.5, dsSlAtr=1.5)
    rc, out, err = _one(pair, tf, q, '--off-grid')
    og = rc == 0 and json.loads(out)['setting']['in_grid'] is False and json.loads(out)['setting']['row'] is None
    if og:
        o = json.loads(out)
        ref = _run_summary(pair, tf, fgds_params(q, pair, tf))
        og = all(_same(o[k], ref[k]) for k in ref) and (o['fgfParentTf'], o['fgfZTf1'], o['fgfZTf2'], o['fgfZTf3']) == \
            ('30', '30', '60', '120') and o['setting']['filter']['fgfZTf3'] == '120'
    # "New signal" with a band, a level and a zone exit given: the grid row (they are dropped)
    q = dict(p, dsTrigger=NS, fgfBandAtr=0.75, fgfLvMode=SCL, dsZoneExit=False)
    rc, out, _ = _one(pair, tf, q)
    rc2, out2, _ = _one(pair, tf, _p_trig(NS, False))
    og2 = rc == 0 and rc2 == 0
    if og2:
        o, o2 = json.loads(out), json.loads(out2)
        og2 = (o['setting']['in_grid'] is True and o['setting']['p'] == _p_trig(NS, False) and o == o2)
    b_ok = all(rc == 2 and e for _, rc, e in res) and og and og2
    _p('  bad input is refused (exit code 2, nothing on stdout): %s; --off-grid runs a setting outside the grid '
       '(filter timeframe 30 with its zones 30 / 60 / 120, burst 0.75, band 0.5, stop 1.5 ATR) = fgds.run: %s; "New '
       'signal" given a band, a level and a zone exit = the grid row with None there: %s'
       % (', '.join('%s -> %d' % (n, rc) for n, rc, _ in res), og, og2))
    return ok and b_ok


# ---------------------------------------------------------------------------------------------
# 4. worker count
# ---------------------------------------------------------------------------------------------
def _sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def test_4_workers():
    """(4) XAU 240, the full grid with 1 worker and with 3 workers (files in calib_tmp_fgds/w1 and w3, not
    out/): every row and column identical, and the two files byte for byte; equal to out/ when it exists.
    With 1 worker everything runs in this process: fgds.prepare and fgf.fgf_permissions are called once per
    signal setting (108), fgds.simulate once per row."""
    d1 = os.path.join(TMP, 'w1')
    d3 = os.path.join(TMP, 'w3')
    calls = dict(prepare=0, simulate=0, fgf=0)
    o_prep, o_sim, o_fgf = fgds.prepare, fgds.simulate, fgf.fgf_permissions

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
    fgds.prepare, fgds.simulate, fgf.fgf_permissions = c_prep, c_sim, c_fgf
    try:
        a, ia = C.run_cell('XAU', '240', workers=1, out_dir=d1, verbose=False)
    finally:
        fgds.prepare, fgds.simulate, fgf.fgf_permissions = o_prep, o_sim, o_fgf
    _free()
    b, ib = C.run_cell('XAU', '240', workers=3, out_dir=d3, verbose=False)
    _free()
    _DF.pop(('XAU', '240'), None)
    f1 = os.path.join(d1, 'calib_fgds_XAU_240.parquet')
    f3 = os.path.join(d3, 'calib_fgds_XAU_240.parquet')
    fa = pd.read_parquet(f1)
    fb = pd.read_parquet(f3)
    same = fa.equals(fb) and a.equals(b) and a.equals(fa) and len(fa) == N_GRID and list(fa.columns) == list(fb.columns) \
        and all(fa[c].dtype == fb[c].dtype for c in fa.columns)
    byt = _sha(f1) == _sha(f3)
    dims = json.load(open(os.path.join(d1, 'calib_fgds_dims.json'))) == C.DIMS == json.load(open(os.path.join(d3, 'calib_fgds_dims.json')))
    once = calls == dict(prepare=108, simulate=N_GRID + 1, fgf=108) and ia['prepares'] == 108 == ib['prepares']
    _p('  XAU 240: %d rows x %d columns; 1 worker %.1fs (runs %.1fs), 3 workers %.1fs (runs %.1fs, speed-up x%.2f): '
       'frames %s, files %s (sha256 %s), dims.json = DIMS: %s'
       % (len(fa), len(fa.columns), ia['t_total'], ia['t_run'], ib['t_total'], ib['t_run'], ia['t_run'] / ib['t_run'],
          'identical' if same else 'DIFFERENT', 'byte for byte equal' if byt else 'DIFFERENT bytes', _sha(f3)[:16], dims))
    _p('  the 1-worker run called fgds.prepare %d times (108 signal settings), fgf.fgf_permissions %d times, '
       'fgds.simulate %d times (%d rows + 1 to load the kernel): signals prepared once per signal setting (one filter '
       'call each, "New signal" on its host\'s) and reused for all its exit settings: %s; distinct arrays kept: %s'
       % (calls['prepare'], calls['fgf'], calls['simulate'], N_GRID, once, ia['distinct']))
    ok = same and byt and dims and once
    fo = _out_file('XAU', '240')
    if os.path.exists(fo):
        fo_df = pd.read_parquet(fo)
        again = fo_df.equals(fb)
        _p('  out/calib_fgds_XAU_240.parquet (the production run) equals this re-run: %s (bytes %s)'
           % (again, 'equal' if _sha(fo) == _sha(f3) else 'different: the metadata differs only if fgds.py / fgf.py changed'))
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
    processes counts 1 / k in each, so the sum is the physical memory they hold together), this process'
    RSS and the largest private dirty memory of a child. peak() = the sample with the largest PSS sum."""

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
    """(5) BTC 1 (the largest cell): the real preparation of all 108 signal settings (one fgds.prepare = one
    fgf.fgf_permissions call each, timed), then passes = all the exit settings of one signal setting with 3
    workers (the default host, the busiest and the quietest filter setting), extrapolated to the 21,600 rows.
    The full grid must stay under 45 min; parent + 3 workers under 4 GB."""
    _free()
    load0 = os.getloadavg()[0]
    with _MemWatch() as mw0:
        cell = C.prepare_cell('BTC', '1')
    t_prep = cell['t_prep']
    te = np.asarray(cell['t_prep_each'])
    pk0 = mw0.peak(0)
    ntr = {si: sum(cell['P'][si]['counts'].values()) for si in cell['idx']}
    dist = C._distinct(cell['P'])
    _p('  BTC 1: %d chart bars, %d 1-minute bars; all 108 signal settings prepared in %.1fs: one fgds.prepare (one '
       'fgf.fgf_permissions call) %.2fs min / %.2fs median / %.2fs mean / %.2fs max; sub-bars + ATR %.1fs, kernel '
       '%.1fs; memory during the preparation (one process): %.0f MB; distinct arrays kept for the 108 prepared inputs: %s'
       % (cell['bars'], cell['n_sub'], t_prep, te.min(), np.median(te), te.mean(), te.max(), cell['t_sub'], cell['t_jit'],
          (pk0[1] / 1024.0) if pk0 else float('nan'), ', '.join('%s %d' % kv for kv in dist.items())))
    host = _default_sig_idx()[0]
    order = sorted((si for si in cell['idx'] if not C.is_new_host(C.SIGNALS[si])), key=lambda si: ntr[si])
    passes = (('default', [host]), ('busiest', [order[-1]]), ('quietest', [order[0]]))
    per = []
    keep = None
    mem = []
    for name, idx in passes:
        with _MemWatch() as mw:
            res, info = C.run_prepared(cell, workers=3, sig_idx=idx)
        mem.append(mw)
        per.append(info['t_run'] / info['settings'])
        s = C.SIGNALS[idx[0]]
        _p('  pass %-8s (fgfTf %s, burst %g, band %g, %s, zones %s; %d trigger bars over the three triggers): %d '
           'settings, 3 workers %.1fs (%.4fs per setting, workers busy %.0f%%)'
           % (name, s['fgfTf'], s['fgfBurstAtr'], s['fgfBandAtr'], s['fgfLvMode'], s['fgfUseZones'], ntr[idx[0]],
              info['settings'], info['t_run'], per[-1], 100.0 * info['busy'] / (3 * info['t_run'])))
        if name == 'default':
            keep = res
    res1, info1 = C.run_prepared(cell, workers=1, sig_idx=[host])
    same = all(len(res1[si]) == len(keep[si]) and all(_same(x, y) for a, b in zip(res1[si], keep[si]) for x, y in zip(a, b))
               for si in [host])
    _p('  pass default with 1 worker: %.1fs (%.4fs per setting); speed-up of 3 workers x%.2f; rows identical to the '
       '3-worker pass: %s' % (info1['t_run'], info1['t_run'] / info1['settings'], info1['t_run'] / (per[0] * info1['settings']), same))
    est = t_prep + N_GRID * float(np.mean(per))
    hi = t_prep + N_GRID * max(per)
    cpu = t_prep + N_GRID * info1['t_run'] / info1['settings'] / 3.0
    _p('  full grid BTC 1 with 3 workers = preparation %.1fs + 21,600 settings: %.1fs = %.1f min (mean of the passes), '
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
        _p('  memory during the 3-worker passes (%d samples with the parent and 3 workers alive): parent + workers '
           'hold %.0f MB together (sum of PSS; parent RSS %.0f MB, a worker\'s own private memory at most %.0f MB); '
           'peak RSS of this test process over everything it ran (tests before included): %.0f MB; limit %d MB: %s'
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
def test_6_row_consistency():
    """Rows hold what they claim, whatever the data: trade counts add up, net = final equity, the window, a
    switch that is off leaves no trace (no trail / target / zone / reverse / time exits), raw_* = the trigger
    counts of the chosen trigger, the trigger counts are those of the prepared input, and every dimension changes
    results somewhere in the cells."""
    ok = True
    live_all = {}
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        ex = [c for c in df.columns if c.startswith('exit_')]
        tr = df['trades']
        trig = df['p_dsTrigger'].to_numpy(dtype=object)
        es = df['p_exitStyle'].to_numpy(dtype=object)
        ze = np.array([_py(v) for v in df['p_dsZoneExit'].tolist()], dtype=object)
        rv = df['p_dsReverse'].to_numpy(bool)
        is_ns = trig == NS
        raw_l = np.where(trig == ZS, df['trig_zone_buy'], np.where(trig == SC, df['trig_conf_buy'], df['trig_new_buy']))
        raw_s = np.where(trig == ZS, df['trig_zone_sell'], np.where(trig == SC, df['trig_conf_sell'], df['trig_new_sell']))
        chk = {
            'trades = long + short': (tr == df['long'] + df['short']).all(),
            'trades = h1_trades + h2_trades': (tr == df['h1_trades'] + df['h2_trades']).all(),
            'trades = sum of the 8 exit kinds': len(ex) == 8 and (tr == df[ex].sum(axis=1)).all(),
            'trades = orders_placed - orders_unfilled_end': (tr == df['orders_placed'] - df['orders_unfilled_end']).all(),
            'orders_placed = taken_long + taken_short': (df['orders_placed'] == df['taken_long'] + df['taken_short']).all(),
            'net_pct = (final_equity - 10000) / 10000': ((df['final_equity'] - INIT) / INIT * 100 == df['net_pct']).all(),
            'half1_pct + half2_pct = net_pct': np.allclose(df['half1_pct'] + df['half2_pct'], df['net_pct'], rtol=0, atol=1e-9),
            'h1_r + h2_r = net_r': np.allclose(df['h1_r'] + df['h2_r'], df['net_r'], rtol=1e-9, atol=1e-6),
            'window': ((df['start'] == WIN[pair][0]) & (df['end'] == WIN[pair][1])).all() and df['bars'].nunique() == 1,
            'no trailing stop: no trail exit': (df.loc[es != 'trail', 'exit_trail'] == 0).all(),
            'no target (none, trail): no tp exit': (df.loc[(es == 'none') | (es == 'trail'), 'exit_tp'] == 0).all(),
            'zone exit off or "New signal": no zone exit': (df.loc[is_ns | (ze == False), 'exit_zone'] == 0).all(),  # noqa: E712
            'reverse off: no reverse exit': (df.loc[~rv, 'exit_reverse'] == 0).all(),
            'reverse on, nothing unsized: no opp exit': (df.loc[rv & (df['zero_qty'] == 0).to_numpy(), 'exit_opp'] == 0).all(),
            'time stop 0 everywhere: no time exit': (df['exit_time'] == 0).all(),
            'nothing blocked': ((df['blocked_long'] == 0) & (df['blocked_short'] == 0)).all(),
            'raw_long / raw_short = the counts of the chosen trigger': (np.array_equal(df['raw_long'].to_numpy(), raw_l)
                                                                       and np.array_equal(df['raw_short'].to_numpy(), raw_s)),
            'pf / win / avg_bars_held NaN only without trades': ((df['pf'].isna() == (tr == 0)) & (df['win_pct'].isna() == (tr == 0))
                                                                 & (df['avg_bars_held'].isna() == (tr == 0))).all(),
            'costs > 0 with trades': ((df['costs'] > 0) == (tr > 0)).all(),
            'fair halves finite': np.isfinite(df[['h1r_pct', 'h2r_pct', 'net_pct', 'max_dd_pct', 'net_r']].to_numpy()).all(),
            'max_dd_pct >= 0': (df['max_dd_pct'] >= 0).all(),
            'at most one trade closed by the window end': (df['exit_end'] <= 1).all(),
            'zero_length <= trades': (df['zero_length'] <= tr).all(),
            'dsMaxQty 1e9 never binds': (df['qty_capped_max'] == 0).all(),
            'floor_ok on every row': bool(df['floor_ok'].all()),
        }
        # the trigger counts belong to the prepared input: constant within a signal setting; the "New signal" rows
        # carry the counts of their host (band 0.25, level Entry price)
        K = _keys(df)
        fs = {}
        for i, k in enumerate(K):
            sk = (k[0], k[1], 0.25 if k[2] is None else k[2], EP if k[3] is None else k[3], k[4])
            fs.setdefault(sk, set()).add(tuple(int(df[c].iat[i]) for c in _COUNTS))
        chk['trigger counts constant per prepared input (NS rows = their host)'] = len(fs) == 108 and all(len(v) == 1 for v in fs.values())
        failed = [k for k, v in chk.items() if not bool(v)]
        zq = int((df['zero_qty'] > 0).sum())
        capm = int((df['qty_capped_margin'] > 0).sum())
        capm1 = int((df['qty_capped_margin'] > 0.01 * tr).sum())
        mo = int((df['margin_over'] > 0).sum())
        dd100 = int((df['max_dd_pct'] > 100).sum())
        # every dimension changes results: groups of rows that differ only in that dimension
        sc = _sumcols(df)
        sig = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
        # the p_ values as text, 'None' for an unused dimension (a missing value must not drop its group: with
        # pandas 3, astype(str) keeps missing values and groupby drops them)
        ps = {c: np.array([repr(k[j]) for k in K]) for j, c in enumerate(_pcols())}
        joint = (('fgfTf', ['p_fgfTf'], None), ('fgfBurstAtr', ['p_fgfBurstAtr'], None),
                 ('fgfBandAtr (Zone start, Signal confirmed)', ['p_fgfBandAtr'], ~is_ns),
                 ('fgfLvMode (Zone start, Signal confirmed)', ['p_fgfLvMode'], ~is_ns),
                 ('fgfUseZones', ['p_fgfUseZones'], None),
                 ('dsTrigger Zone start / Signal confirmed', ['p_dsTrigger'], ~is_ns),
                 ('dsTrigger with the dimensions it switches off', ['p_dsTrigger', 'p_fgfBandAtr', 'p_fgfLvMode', 'p_dsZoneExit'], None),
                 ('inv', ['p_inv'], None), ('dsZoneExit (Zone start, Signal confirmed)', ['p_dsZoneExit'], ~is_ns),
                 ('dsReverse', ['p_dsReverse'], None), ('dsSlAtr', ['p_dsSlAtr'], None), ('exitStyle', ['p_exitStyle'], None))
        parts = []
        n_rows_g = n_sel_g = 0
        for name, cols, sel in joint:
            others = [c for c in _pcols() if c not in cols]
            sel = np.ones(len(df), bool) if sel is None else sel
            g = pd.Series(sig[sel]).groupby([ps[c][sel] for c in others]).agg(['size', 'nunique'])
            n_all = int((g['nunique'] == g['size']).sum())
            n_any = int((g['nunique'] > 1).sum())
            live_all[name] = live_all.get(name, 0) + n_any
            n_rows_g += int(g['size'].sum())
            n_sel_g += int(sel.sum())
            parts.append('%s %d / %d / %d' % (name, n_all, n_any, len(g)))
        # every row has its direction twin (inv flipped) in the file, and never its result (when it trades)
        pos = {k: i for i, k in enumerate(K)}
        j_inv = C.DIM_NAMES.index('inv')
        twin = np.array([pos.get(k[:j_inv] + (not k[j_inv],) + k[j_inv + 1:], -1) for k in K])
        no_twin = int((twin < 0).sum())
        twin = np.where(twin < 0, np.arange(len(K)), twin)
        same_twin = int(((sig == sig[twin]) & (tr.to_numpy() > 0)).sum())
        # the orchestrator's analysis reads the file with its own coding of DIMS: every value must be in DIMS
        try:
            import calib_analyze
            codes = calib_analyze.codes_of(df, C.DIMS)
            jdir = next(j for j, d in enumerate(C.DIMS) if d['name'].lower() in calib_analyze.DIR_NAMES)
            unused = sorted(set(C.DIM_NAMES[j] for j in np.flatnonzero((codes < 0).any(axis=0))))
            an = (C.DIM_NAMES[jdir] == 'inv' and unused == sorted(SPEC_UNUSED) and len(np.unique(codes, axis=0)) == len(df)
                  and 'floor_ok' in df.columns)
            an_txt = 'calib_analyze.codes_of reads every p_ value (direction dimension inv; unused only in %s): %s' % (unused, an)
        except Exception as e:      # noqa: BLE001
            an = False
            an_txt = 'calib_analyze.codes_of FAILED: %r' % (e,)
        n_distinct = len(np.unique(sig))
        cand = int(((df['h1r_pct'] > 0) & (df['h2r_pct'] > 0) & (df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).sum())
        el = int(((df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).sum())
        _p('  %s %s (%s): %d rows, %d checks: %s' % (pair, tf, src, len(df), len(chk),
                                                     'all hold' if not failed else 'FAILED: ' + '; '.join(failed)))
        _p('    groups differing only in one dimension (all results distinct / some distinct / groups): %s' % '; '.join(parts))
        _p('    trades %d .. %d (median %d; %d rows without a trade); distinct results %d of %d rows; rows with trades '
           'that equal their direction twin (inv flipped): %d; rows with a quantity floored to zero: %d; rows with a '
           'quantity set by the margin cap: %d (above 1 %% of the trades: %d); rows with margin_over: %d; rows with a '
           'drawdown above 100 %%: %d; rows with >= 30 trades in each half: %d, of which positive in both fair halves: %d'
           % (tr.min(), tr.max(), int(tr.median()), int((tr == 0).sum()), n_distinct, len(df), same_twin, zq, capm, capm1,
              mo, dd100, el, cand))
        _p('    every row is in a group of every analysis above (no row dropped): %s; rows without a direction twin in '
           'the file: %d; %s' % (n_rows_g == n_sel_g, no_twin, an_txt))
        ok &= not failed and same_twin == 0 and n_rows_g == n_sel_g and an and no_twin == 0
    dead = [k for k, v in live_all.items() if v == 0]
    _p('  every dimension changes results in at least one group over the cells: %s' % ('yes' if not dead else 'NO: %s' % dead))
    return ok and not dead


# ---------------------------------------------------------------------------------------------
# 7. every row
# ---------------------------------------------------------------------------------------------
def _groups(keys, pair, tf):
    """The rows of a file grouped by their fgds.prepare params (this file's own mapping)."""
    groups = {}
    for i, k in enumerate(keys):
        prep, sim = _split(fgds_params(dict(zip(SPEC_DIMS, k)), pair, tf))
        groups.setdefault(tuple(sorted((a, repr(b)) for a, b in prep.items())), (prep, []))[1].append((i, sim, k))
    return groups


def test_7_all_rows():
    """Every row of the cells' files, not a sample: recomputed in this process with fgds.prepare once per
    signal setting and fgds.simulate + fgds.summary per row, the parameters from this file's own mapping
    (fgds_params, split into the prepare and the simulate keys); every summary value must be equal. And the
    "New signal" trigger arrays of every prepared input equal those of the 5 others with the same filter
    timeframe, burst and zones (band and level cannot change them)."""
    ok = True
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        sc = _sumcols(df)
        keys = _keys(df)
        vals = [df[c].tolist() for c in sc]
        groups = _groups(keys, pair, tf)
        t0 = time.time()
        n_vals = 0
        bad_rows = []
        bad_groups = 0
        fields_ok = True
        sub = None
        newarr = {}
        for gk in sorted(groups):
            prep, items = groups[gk]
            Pp = fgds.prepare(pair, tf, prep)
            if sub is None:
                sub = (Pp['w0'], Pp['w1'], fgds.get_sub(Pp))
            assert (Pp['w0'], Pp['w1']) == sub[:2]
            Pp['sub'] = sub[2]                      # the 1-minute table depends on the window rows only
            nk = (prep['fgfTf'], prep['fgfBurstAtr'], prep['fgfUseZones'])
            newarr.setdefault(nk, []).append(hashlib.sha256(Pp['newBuy'].tobytes() + Pp['newSell'].tobytes()).hexdigest())
            n_bad0 = len(bad_rows)
            for i, sim, _ in items:
                s = fgds.summary(Pp, fgds.simulate(Pp, sim))
                if list(s) != sc:
                    fields_ok = False
                    break
                n_vals += len(sc)
                if not all(_same(_py(vals[j][i]), s[c]) for j, c in enumerate(sc)):
                    bad_rows.append(i)
            bad_groups += len(bad_rows) > n_bad0
            del Pp
        n_ns = sum(1 for _, items in groups.values() for _, _, k in items if k[5] == NS)
        new_ok = len(newarr) == 18 and all(len(v) == 6 and len(set(v)) == 1 for v in newarr.values())
        c_ok = (fields_ok and not bad_rows and len(groups) == 108 and n_vals == len(df) * len(sc) and len(df) == N_GRID
                and bool(df['floor_ok'].all()) and n_ns == 864 and new_ok)
        _p('  %s %s (%s): all %d rows recomputed (fgds.prepare for each of the %d signal settings, the %d "New signal" '
           'rows on the prepared input of band 0.25 / Entry price, fgds.simulate + fgds.summary per row): %d summary '
           'values, %s; newBuy / newSell identical over the 6 band / level settings of each of the %d (fgfTf, burst, '
           'zones): %s (%.1fs)'
           % (pair, tf, src, len(keys), len(groups), n_ns, n_vals,
              'all equal' if not bad_rows and fields_ok else '%d ROWS DIFFER in %d signal settings (first rows %s)%s'
              % (len(bad_rows), bad_groups, bad_rows[:8], '' if fields_ok else '; the summary fields differ'),
              len(newarr), new_ok, time.time() - t0))
        ok &= c_ok
        _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 8. every cell that has a file
# ---------------------------------------------------------------------------------------------
def test_8_every_cell():
    """Every cell with a file in out/: the file holds the grid in order with the result columns and its
    metadata, and 4 random rows of EVERY signal setting plus 2 "New signal" rows of every host (468 rows per
    cell) recomputed in this process (fgds.prepare per signal setting, fgds.simulate + fgds.summary per row,
    this file's own mapping) equal the file."""
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
            meta = C.read_meta(f)
            now = C.file_meta(pair, tf, N_GRID)
            p10, _, _ = _own_p10(pair, tf)
            act, dst = T_TRAIL.get((pair, tf), (2.0, 1.0))
            g_ok = (len(df) == N_GRID and keys == spec_grid() and all(k in sc for k in SUM_REQUIRED) and meta is not None
                    and all(meta.get(k) == now[k] for k in ('strategy', 'pair', 'tf', 'path', 'cost', 'settings', 'window',
                                                            'dsMaxQty', 'dsQtyStep', 'fgfOn', 'dsTrActAtr', 'dsTrDstAtr'))
                    and (meta['dsTrActAtr'], meta['dsTrDstAtr']) == (act, dst)
                    and bool(((df['start'] == WIN[pair][0]) & (df['end'] == WIN[pair][1])).all())
                    and bool(df['floor_ok'].all()) and dst * p10 >= T_FLOOR[pair]
                    and abs(meta['floor']['p10_atr_pct'] - p10) < 1e-6)
            cur = meta is not None and meta.get('fgds_sha256') == now['fgds_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
            groups = _groups(keys, pair, tf)
            n_rows = n_vals = 0
            bad_rows = []
            sub = None
            for gk in sorted(groups):
                prep, items = groups[gk]
                Pp = fgds.prepare(pair, tf, prep)
                if sub is None:
                    sub = (Pp['w0'], Pp['w1'], fgds.get_sub(Pp))
                assert (Pp['w0'], Pp['w1']) == sub[:2]
                Pp['sub'] = sub[2]
                main = [it for it in items if it[2][5] != NS]
                new = [it for it in items if it[2][5] == NS]
                take = [main[int(j)] for j in rng.choice(len(main), size=min(4, len(main)), replace=False)]
                if new:
                    take += [new[int(j)] for j in rng.choice(len(new), size=2, replace=False)]
                for i, sim, _ in sorted(take):
                    s = fgds.summary(Pp, fgds.simulate(Pp, sim))
                    n_rows += 1
                    n_vals += len(sc)
                    if list(s) != sc or not all(_same(_py(df[c].iat[i]), s[c]) for c in sc):
                        bad_rows.append(i)
                del Pp
            h = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
            c_ok = g_ok and not bad_rows and len(groups) == 108 and n_rows == 108 * 4 + 18 * 2
            tr = df['trades']
            _p('  %s %-3s: %d rows, the grid in order, metadata, window, floor_ok: %s; written with the fgds.py / fgf.py '
               'now on disk: %s; %d rows (4 of each of the %d signal settings + 2 "New signal" rows of each host) '
               'recomputed: %d values, %s; distinct results %d; trades %d .. %d; rows with zero_qty > 0: %d (%.1fs)'
               % (pair, tf, len(df), g_ok, cur, n_rows, len(groups), n_vals,
                  'all equal' if not bad_rows else '%d ROWS DIFFER: %s' % (len(bad_rows), bad_rows[:8]),
                  len(np.unique(h)), tr.min(), tr.max(), int((df['zero_qty'] > 0).sum()), time.time() - t0))
            ok &= c_ok
            _free()
    if n_cells == 0:
        _p('  no cell has a file in out/ yet: nothing to check')
    else:
        _p('  %d cells checked' % n_cells)
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
    _p('calib_tests_fgds.py: cells %s; fgds.py sha256 %s; fgf.py sha256 %s; calib_fgds.py sha256 %s; load average %.2f'
       % (', '.join('%s %s' % c for c in CELLS), _sha(os.path.join(W, 'fgds.py'))[:16], _sha(os.path.join(W, 'fgf.py'))[:16],
          _sha(os.path.join(W, 'calib_fgds.py'))[:16], os.getloadavg()[0]))
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
    _p('fgds.py sha256 at the end %s' % _sha(os.path.join(W, 'fgds.py'))[:16])
    return 0 if all(res.values()) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
