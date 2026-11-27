"""calib_tests_fgv5.py: tests of calib_fgv5.py (CALIB_SPEC.md, strategy "fgv5"; the grid is section 14 of
SPEC_fgv5.md with the orchestrator's decisions: the file's own sizing (Fixed 10 units) on every row, the R-based
scoring columns (h1r_pct := h1_r, h2r_pct := h2_r, net_pct := net_r; the money figures as *_money), the runner
trail pair (r1, r2) per cell, the derived dimension exitStyle with its Pine inputs as extra columns, floor_ok).

Usage: python3 -I calib_tests_fgv5.py [name filter ...] [--cells XAU:240,BTC:240] [--files-only]

  test_1_grid             the grid is the full product of section 14 (15,984 = 18 x 888 = 3 x 3 x 2 x 2 x 3 x 2
                          x 37 x 2), keys unique, DIMS / SIGNALS / EXITS consistent; every setting maps to the
                          fgv5 inputs the spec means (an independent mapping written here; the script defaults
                          checked against fgv5.DEFAULTS and the Pine file's own input lines); the runner trail
                          pair of every cell = the table, and the table's p10 and ladder recomputed here from the
                          bar files; the inputs listed once (None / not set) cannot change a result; the files hold
                          the grid in order with the columns the spec asks for; the metadata says what produced
                          them and states the R-based scoring
  test_2_default_rows     the default row and the same with inv true equal the saved default results of the
                          module (out/inv_fgv5_<PAIR>_<TF>.json runs normal/on/mag/ours and inverted/on/mag/ours)
                          on BTC 240 and XAU 240, and filter off (normal/off, inverted/off) on BTC 60 and XAU 60:
                          through `--one` (a new process), in the grid rows, and calib_fgv5.one on every saved run
                          of all 14 cells; money fields compared to *_money, R fields to net_r / h1_r / h2_r;
                          and in every cell one 'part30' and one 'run' setting through calib_fgv5.one = fgv5
                          with this file's mapping, the runner trail echoed = the table (cells 1 / 5 too)
  test_3_one_rows         30 random rows per cell recomputed one at a time through `calib_fgv5.py --one` (a new
                          process each) equal the sweep rows (and echo the row number); the same rows through
                          fgv5.prepare / simulate / summary with this file's own mapping and remap; --path /
                          --cost; --risk-sizing; --script-sizing; --off-grid; bad input refused
  test_4_workers          XAU 240: 1 worker vs 3 workers identical (frames and file bytes); fgv5.prepare runs once
                          per signal setting (18), the signal kernel once per signal input (9), the filter once
  test_5_timing_btc1      BTC 1: the real preparation and three passes (1,776 settings = one signal input, filter
                          off + on, 3 workers) extrapolated to the 9 passes of the full grid: under 45 minutes with
                          a free CPU per worker (the workers' CPU time; the wall clock at the present load of the
                          shared machine is printed next to it, with a warning when it is over 45 minutes); the
                          memory of the preparation and of the parent + 3 workers during the passes (sum of PSS,
                          sampled): under 4 GB
  test_6_row_consistency  what every row must satisfy whatever the data (counts add up, the R columns are the R
                          sums, a switch that is off leaves no trace), every dimension changes results, every row
                          has its direction twin, calib_analyze reads every p_ value
  test_7_all_rows         EVERY row of the cells' files (not a sample) recomputed in this process: fgv5.prepare
                          once per signal setting, fgv5.simulate + fgv5.summary per row, with this file's own
                          mapping and its own remap; every non-p_ value equal
  test_8_every_cell       every cell that has a file in out/: the file holds the grid in order, metadata, floor,
                          and 4 random rows of EVERY signal setting (72 rows per cell) recomputed here equal it

The cells of tests 3, 6 and 7 (and the files of test 1) are --cells (default XAU 240 and BTC 240): the file
out/calib_fgv5_<PAIR>_<TF>.parquet when it exists, else the cell is run here with 3 workers into
calib_tmp_fgv5/w3/ (never into out/). Test 2's grid rows of BTC 60 / XAU 60 come from the file when it exists,
else the two default signal settings are run in memory (1,776 rows; --files-only skips those). At most 2
processes at a time, except the sweep's own 3 workers. Prints PASS / FAIL per test; exit code 1 on a failure.
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
import fgv5  # noqa: E402
import fgf  # noqa: E402
import calib_fgv5 as C  # noqa: E402

OUT = os.path.join(W, 'out')
TMP = os.path.join(W, 'calib_tmp_fgv5')
PINE = '/home/user/master/FlashGold_v5_Strategy_BTCUSD_FGF.pine'
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
INIT = 100000.0
CELLS = [('XAU', '240'), ('BTC', '240')]
FILES_ONLY = False
N_GRID = 15984
MEM_LIMIT_MB = 4000        # test 5: "keep a BTC 1 run under 4 GB" (the session shares one 16 GB limit)
SUM_REQUIRED = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
                'net_r', 'h1_r', 'h2_r', 'zero_qty', 'neg_equity_bars', 'be_no_tp', 'tv_rows', 'min_equity',
                'max_notional_x', 'net_pct_money', 'h1r_pct_money', 'h2r_pct_money')


def _p(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# this file's own reading of the spec (independent of calib_fgv5's lists and mappings)
# ---------------------------------------------------------------------------------------------
SPEC_DIMS = ['burstAtrMult', 'minAlignedZones', 'fgfOn', 'inv', 'entryDistAtrMult', 'allowReverse', 'exitStyle',
             'slAtrMult', 'tpR', 'maxBarsHeld']
SPEC_KIND = {'burstAtrMult': 'ordinal', 'minAlignedZones': 'ordinal', 'fgfOn': 'categorical', 'inv': 'categorical',
             'entryDistAtrMult': 'ordinal', 'allowReverse': 'categorical', 'exitStyle': 'categorical',
             'slAtrMult': 'ordinal', 'tpR': 'ordinal', 'maxBarsHeld': 'categorical'}
SPEC_SIDE = dict(zip(SPEC_DIMS, ['signal'] * 3 + ['exit'] * 7))
SPEC_DEFAULT = dict(zip(SPEC_DIMS, (0.5, 2, True, False, 0.25, True, 'pips_default', None, None, 0)))
SPEC_VALUES = {'burstAtrMult': [0.3, 0.5, 1.0], 'minAlignedZones': [1, 2, 3], 'fgfOn': [False, True],
               'inv': [False, True], 'entryDistAtrMult': [0.0, 0.25, 0.5], 'allowReverse': [True, False],
               'exitStyle': ['pips_default', 'fixed', 'part30', 'run'], 'slAtrMult': [0.25, 0.5, 1.0, 2.0],
               'tpR': [1.5, 3.0, 5.0], 'maxBarsHeld': [0, 12]}
SPEC_UNUSED = {'slAtrMult': {'exitStyle': 'pips_default'}, 'tpR': {'exitStyle': 'pips_default'}}
# section 14: (r1, r2) per cell, the 10th percentile of ATR(14) / close in % as printed there, the ladder
T_TRAIL = {('BTC', '1'): (6.5, 8.5), ('BTC', '5'): (2.5, 3.5), ('XAU', '1'): (5.0, 6.5), ('XAU', '5'): (2.5, 3.5)}
T_P10 = {('BTC', '1'): 0.0157, ('BTC', '5'): 0.0574, ('BTC', '15'): 0.125, ('BTC', '30'): 0.198, ('BTC', '60'): 0.318,
         ('BTC', '120'): 0.512, ('BTC', '240'): 0.826, ('XAU', '1'): 0.0101, ('XAU', '5'): 0.0290,
         ('XAU', '15'): 0.0599, ('XAU', '30'): 0.094, ('XAU', '60'): 0.145, ('XAU', '120'): 0.203, ('XAU', '240'): 0.311}
T_LADDER = (1.5, 2.5, 3.5, 5.0, 6.5, 8.5)
T_FLOOR = {'BTC': 0.1, 'XAU': 0.05}
T_WINDOWS = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}
# the Pine's input defaults (SPEC_fgv5.md sections 3.1 and 3.2) and the replica controls
SCRIPT_SIG = dict(
    spreadPoints=25.0, entryHoldBars=0, entryHoldMinFavPoints=5.0, oneEntryPerBar=True,
    DistUnit="ATR", burstAtrMult=0.5, holdFavAtrMult=0.1, burstPointsInput=172.0, useBurstGate=True,
    useAnyCombo=False, priorDriftBars=60, usePriorFilter=False,
    useTdiTradeZone=True, tdiParentTf="60", tdiRsiLen=14, tdiFastLen=2, tdiSlowLen=7, minAlignedZones=2,
    allowNeutralParent=False, ignoreNaZones=True, htfNoRepaint=True,
    useZone1=True, zoneTf1="60", useZone2=True, zoneTf2="120", useZone3=True, zoneTf3="240",
    useZone4=False, zoneTf4="480", useZone5=False, zoneTf5="1", useZone6=False, zoneTf6="2", autoTf=True,
    fgfOn=True, start=None, end=None)
SCRIPT_ORD = dict(
    entryDistAtrMult=0.25, entryDistPoints=50.0, Direction="Both", entryValidBars=3, allowReverse=True,
    exitOnOpposite=False, ExitMode="Pips", pipSize=1.0, slPips=30.0, tpRPips=5.0, runTrailPips=600.0,
    trailActPips=150.0, trailPips=600.0, slPoints=3900.0, tpPoints=19500.0, atrLen=14, slAtrMult=0.1, tpR=2.0,
    useTrail=False, trailActPoints=4500.0, trailPoints=1000.0, trailActAtr=1.0, trailDstAtr=0.25, maxBarsHeld=0,
    TpStyle="Partial + runner", partPct=30.0, runBE=True, runTrailAtr=1.5, runTrailPts=58000.0,
    QtyMode="Fixed", fixedQty=10.0, riskPct=1.0, maxQty=50.0, qtyStep=1.0, fgvInv=False, path='tv', cost='tv')
REPLICA_CONTROLS = {'start', 'end', 'path', 'cost'}
# the exit styles of section 14, as the Pine inputs each one sets (r1 / r2: the cell's runner trail)
T_STYLE = {
    'pips_default': dict(ExitMode='Pips', pipSize=1.0, slPips=30.0, tpRPips=5.0, TpStyle='Partial + runner',
                         partPct=30.0, runBE=True, runTrailPips=600.0),
    'fixed': dict(ExitMode='ATR', TpStyle='Fixed', useTrail=False),
    'part30': dict(ExitMode='ATR', TpStyle='Partial + runner', partPct=30.0, runBE=True, runTrailAtr='r1'),
    'run': dict(ExitMode='ATR', TpStyle='Partial + runner', partPct=0.0, runBE=True, runTrailAtr='r2'),
}
T_INPUT_COLS = ['ExitMode', 'TpStyle', 'pipSize', 'slPips', 'tpRPips', 'runTrailPips', 'partPct', 'runBE',
                'runTrailAtr', 'useTrail']
T_RISK = dict(QtyMode='Risk %', riskPct=1.0, maxQty=1e9, qtyStep=0.000001)
T_REMAP = {'net_pct': 'net_r', 'h1r_pct': 'h1_r', 'h2r_pct': 'h2_r'}
T_MONEY = ['net_pct_money', 'h1r_pct_money', 'h2r_pct_money']


def spec_grid(pair=None, tf=None):
    """SPEC_fgv5.md section 14 as nested loops: signals burst x zones x filter; exits inv x entry distance x
    reverse x (pips_default | 3 ATR styles x 4 stops x 3 targets) x time stop."""
    G = []
    for b in (0.3, 0.5, 1.0):
        for z in (1, 2, 3):
            for f in (False, True):
                for inv in (False, True):
                    for e in (0.0, 0.25, 0.5):
                        for rv in (True, False):
                            br = [('pips_default', None, None)]
                            for st in ('fixed', 'part30', 'run'):
                                for sl in (0.25, 0.5, 1.0, 2.0):
                                    for tp in (1.5, 3.0, 5.0):
                                        br.append((st, sl, tp))
                            for st, sl, tp in br:
                                for mb in (0, 12):
                                    G.append((b, z, f, inv, e, rv, st, sl, tp, mb))
    return G


def t_inputs(p, pair, tf):
    """The non-p_ input columns of one setting: the Pine inputs its exit style sets, None elsewhere."""
    r1, r2 = T_TRAIL.get((pair, tf), (1.5, 2.5))
    q = dict(T_STYLE[p['exitStyle']])
    if 'runTrailAtr' in q:
        q['runTrailAtr'] = r1 if q['runTrailAtr'] == 'r1' else r2
    return {k: q.get(k) for k in T_INPUT_COLS}


def fgv5_params(p, pair, tf, path='mag', cost='ours', sizing='script'):
    """A setting (dict over SPEC_DIMS) as the complete fgv5 inputs (prepare dict, simulate dict), written from the
    spec and the orchestrator's decisions: the file's own sizing (Fixed 10 units) unless sizing 'risk'."""
    sig = dict(SCRIPT_SIG)
    sig.update(burstAtrMult=p['burstAtrMult'], minAlignedZones=p['minAlignedZones'], fgfOn=p['fgfOn'])
    o = dict(SCRIPT_ORD)
    o.update(fgvInv=p['inv'], entryDistAtrMult=p['entryDistAtrMult'], allowReverse=p['allowReverse'],
             maxBarsHeld=p['maxBarsHeld'], path=path, cost=cost)
    o.update({k: v for k, v in t_inputs(p, pair, tf).items() if v is not None})
    if p['exitStyle'] != 'pips_default':
        o.update(slAtrMult=p['slAtrMult'], tpR=p['tpR'])
    if sizing == 'risk':
        o.update(T_RISK)
    return sig, o


def t_scored(s):
    """fgv5.summary -> the columns of a row: the summary's own fields, net_pct / h1r_pct / h2r_pct replaced by
    net_r / h1_r / h2_r, and the money figures as *_money."""
    out = {k: (s[T_REMAP[k]] if k in T_REMAP else v) for k, v in s.items()}
    out['net_pct_money'] = s['net_pct']
    out['h1r_pct_money'] = s['h1r_pct']
    out['h2r_pct_money'] = s['h2r_pct']
    return out


def pine_inputs():
    """name -> default of every `name = input.<type>(default, ...)` line of the Pine."""
    out = {}
    rx = re.compile(r'^\s*([A-Za-z_]\w*)\s*=\s*input\.(int|float|bool|string|timeframe)\(\s*("[^"]*"|[^,)\s]+)')
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
            out[name] = v
    return out


def _own_p10(pair, tf):
    """The 10th percentile over the window of ATR(14) / close in %, and the highest close, computed here from the
    bar file with pandas (Wilder's average as an exponential mean of the true range; the window starts thousands
    of bars into the file, so its seed no longer matters)."""
    t = pq.read_table(os.path.join(W, 'data', '%s_%s.parquet' % (pair, tf)), columns=['high', 'low', 'close', 't_close'])
    h, l, c, tc = (t.column(k).to_numpy() for k in ('high', 'low', 'close', 't_close'))
    pc = np.concatenate(([np.nan], c[:-1]))
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1.0 / 14.0, adjust=False).mean().to_numpy()
    s0, e0 = T_WINDOWS[pair]
    m = (tc >= s0) & (tc <= e0)
    w0 = int(np.argmax(m))
    return float(np.percentile(atr[m] / c[m] * 100.0, 10)), float(c[m].max()), w0, int(m.sum())


def own_floor(pair, tf):
    """floor_ok by exit style, from this file's own p10 and the section-14 rule."""
    p10, cmax, _, _ = _own_p10(pair, tf)
    r1, r2 = T_TRAIL.get((pair, tf), (1.5, 2.5))
    fl = T_FLOOR[pair]
    return {'pips_default': 600.0 / cmax * 100.0 >= fl, 'fixed': True, 'part30': r1 * p10 >= fl,
            'run': r2 * p10 >= fl}, p10


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def _py(v):
    if v is None or v is pd.NA:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if math.isnan(v) else float(v)
    return v


def _same(a, b):
    """Exact equality; NaN equals NaN; None (null) equals None and NaN (a null input column)."""
    a, b = _py(a), _py(b)
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    return float(a) == float(b)


def _pcols():
    return ['p_' + n for n in SPEC_DIMS]


def _keys(df):
    """The p_ columns of a file as a list of key tuples (python values, None for unused)."""
    cols = [[_py(v) for v in df[c].tolist()] for c in _pcols()]
    return list(zip(*cols))


def _rescols(df):
    """Every column that is not a p_ column: the inputs, floor_ok and the result fields."""
    return [c for c in df.columns if not c.startswith('p_')]


def _sumcols(df):
    return [c for c in df.columns if not c.startswith('p_') and c != 'floor_ok' and c not in T_INPUT_COLS]


def _out_file(pair, tf):
    return os.path.join(OUT, 'calib_fgv5_%s_%s.parquet' % (pair, tf))


def _fresh(path):
    """A scratch file is used only when it is newer than the runner and the replica."""
    return os.path.exists(path) and os.path.getmtime(path) > max(os.path.getmtime(os.path.join(W, 'calib_fgv5.py')),
                                                                 os.path.getmtime(os.path.join(W, 'fgv5.py')))


_DF = {}


def _cell_df(pair, tf):
    """(DataFrame, where): out/ when the cell's file exists, else calib_tmp_fgv5/w3 (run here if needed)."""
    key = (pair, tf)
    if key not in _DF:
        f = _out_file(pair, tf)
        if os.path.exists(f):
            src = 'out/' + os.path.basename(f)
            if not _fresh(f):
                _p('  note: %s is older than calib_fgv5.py or fgv5.py' % src)
        else:
            d3 = os.path.join(TMP, 'w3')
            f = os.path.join(d3, 'calib_fgv5_%s_%s.parquet' % (pair, tf))
            src = 'calib_tmp_fgv5/w3/' + os.path.basename(f)
            if not _fresh(f):
                t0 = time.time()
                C.run_cell(pair, tf, workers=3, out_dir=d3, verbose=False)
                _p('  %s %s has no file in out/: run here with 3 workers into %s (%.1fs)' % (pair, tf, src, time.time() - t0))
                _free()
        _DF[key] = (pd.read_parquet(f), src)
    return _DF[key]


def _free():
    C._free_caches(bars=True)
    C._G.clear()
    gc.collect()


def _default_sig_idx():
    return [i for i, s in enumerate(C.SIGNALS) if (s['burstAtrMult'], s['minAlignedZones']) == (0.5, 2)]


def _ref_summary(pair, tf, p, path='mag', cost='ours', sizing='script', cache=None):
    """fgv5.prepare + simulate + summary with this file's own mapping (cache: prepared inputs by signal params)."""
    sig, o = fgv5_params(p, pair, tf, path, cost, sizing)
    k = (pair, tf, tuple(sorted((a, repr(b)) for a, b in sig.items())))
    P = cache.get(k) if cache is not None else None
    if P is None:
        P = fgv5.prepare(pair, tf, sig)
        if cache is not None:
            cache[k] = P
    return fgv5.summary(P, fgv5.simulate(P, o))


def _cmp(row, ref, keys, tag, bad, limit=6):
    n = 0
    for k in keys:
        n += 1
        if not _same(row[k], ref[k]):
            if len(bad) < limit:
                bad.append('%s.%s row %r ref %r' % (tag, k, row[k], ref[k]))
            else:
                bad.append('')
    return n


def _json_ref(sv):
    """A saved run of out/inv_fgv5_*.json as python values (its writer stores NaN as null, inf as 'inf')."""
    ref = {}
    for k, v in sv.items():
        if k in ('direction', 'filter', 'path', 'cost', 'params'):
            ref[k] = v
            continue
        ref[k] = float('nan') if v is None else (float(v) if isinstance(v, str) else v)
    return ref


def _cmp_saved(row, sv, fields, tag, bad):
    """A row (or --one output) against a saved fgv5.summary: the R columns against net_r / h1_r / h2_r, the money
    columns against fgv5's net_pct / h1r_pct / h2r_pct, every other field by its own name."""
    ref = t_scored({k: sv[k] for k in fields})
    return _cmp(row, ref, list(ref), tag, bad)


# ---------------------------------------------------------------------------------------------
# 1. the grid
# ---------------------------------------------------------------------------------------------
def test_1_grid():
    """(1) The grid is the full product of section 14, keys unique; DIMS, SIGNALS, EXITS and the fgv5 inputs of
    every setting are what the spec says; the runner trail table and its floor; the inputs listed once cannot
    change a result; the files hold the grid with the asked-for columns and metadata."""
    ok = True
    S = spec_grid()
    G = C.grid('BTC', '240')
    K = [C.key(p) for p in G]
    same_all = all(C.grid(pair, tf) == G for pair in PAIRS for tf in TFS)
    a = (len(S) == N_GRID == len(set(S)) == 3 * 3 * 2 * 2 * 3 * 2 * 37 * 2 and len(G) == N_GRID == len(set(K))
         and K == S and C.N_GRID == N_GRID and all(C.n_settings(pair, tf) == N_GRID for pair in PAIRS for tf in TFS)
         and same_all and G == [C.merge(s, x) for s in C.signals('BTC', '240') for x in C.exits_for(None, 'BTC', '240')])
    _p('  spec product 15,984 = 3 bursts x 3 zones x 2 filter x 2 inv x 3 entry distances x 2 reverse x (1 + 3 '
       'styles x 4 stops x 3 targets) x 2 time stops; the runner\'s grid = the spec\'s, same order, keys unique, '
       'the same in all 14 cells: %s' % a)
    ok &= a
    sk = [tuple(s[k] for k in C.SIGNAL_DIMS) for s in C.SIGNALS]
    xk = [tuple(x[k] for k in C.EXIT_DIMS) for x in C.EXITS]
    c = (len(sk) == 18 == len(set(sk)) and len(xk) == 888 == len(set(xk)) and list(C.SIGNAL_DIMS) == SPEC_DIMS[:3]
         and list(C.EXIT_DIMS) == SPEC_DIMS[3:] and list(C.SIGNAL_DIMS) + list(C.EXIT_DIMS) == C.DIM_NAMES
         and [s['fgfOn'] for s in C.SIGNALS] == [False, True] * 9)
    _p('  SIGNALS %d unique (prepare params: burstAtrMult, minAlignedZones, fgfOn; filter innermost), EXITS %d unique '
       '(simulate params), the same 888 for every signal setting: %s' % (len(set(sk)), len(set(xk)), c))
    ok &= c
    # ---- DIMS
    d_ok = [d['name'] for d in C.DIMS] == SPEC_DIMS and all(
        {'name', 'values', 'kind'} <= set(d) <= {'name', 'values', 'kind', 'side', 'default', 'unused_when'}
        and d['values'] == SPEC_VALUES[d['name']] and d['kind'] == SPEC_KIND[d['name']]
        and d['side'] == SPEC_SIDE[d['name']] and d['default'] == SPEC_DEFAULT[d['name']]
        and type(d['default']) is type(SPEC_DEFAULT[d['name']]) and d.get('unused_when') == SPEC_UNUSED.get(d['name'])
        and all(type(v) in (bool, int, float, str) for v in d['values'])
        and (d['kind'] != 'ordinal' or list(d['values']) == sorted(d['values'])) for d in C.DIMS)
    d_ok &= C.DEFAULT_P == SPEC_DEFAULT and C.DEFAULT is C.DEFAULT_P
    for j, d in enumerate(C.DIMS):
        d_ok &= set(k[j] for k in S if k[j] is not None) == set(d['values'])
    none_ok = all(((k[7] is None) == (k[6] == 'pips_default')) and ((k[8] is None) == (k[6] == 'pips_default'))
                  and all(k[j] is not None for j in range(10) if j not in (7, 8)) for k in S)
    dir_ok = C.DIMS[3]['name'] == 'inv' and C.DIMS[3]['kind'] == 'categorical' and C.DIMS[3]['values'] == [False, True]
    try:
        json.dumps(C.DIMS)
        js = True
    except Exception:      # noqa: BLE001
        js = False
    _p('  DIMS: %s; values / kinds / sides / defaults / unused_when as section 14: %s; None only for slAtrMult and tpR '
       'with pips_default, and always there: %s; the direction dimension is named inv (fgvInv), categorical: %s; '
       'JSON: %s' % ([d['name'] for d in C.DIMS], d_ok, none_ok, dir_ok, js))
    ok &= d_ok and none_ok and dir_ok and js
    # ---- the script defaults: this file's copy, the module's, the Pine's own input lines
    mod = {k: v for k, v in fgv5.DEFAULTS.items() if k not in fgv5.FGF_KEYS}
    mine = dict(SCRIPT_SIG, **SCRIPT_ORD)
    m_ok = mod == mine and {k: fgv5.DEFAULTS[k] for k in fgv5.FGF_KEYS} == {k: v for k, v in fgf.DEFAULTS.items() if k != 'fgfOn'}
    pin = pine_inputs()
    found = [k for k in mine if k in pin]
    diff = {k: (mine[k], pin[k]) for k in found
            if not (mine[k] == pin[k] and isinstance(mine[k], bool) == isinstance(pin[k], bool))}
    missing = sorted(set(mine) - set(found) - REPLICA_CONTROLS)
    fdiff = {k: (fgf.DEFAULTS[k], pin.get(k)) for k in fgf.DEFAULTS if pin.get(k) != fgf.DEFAULTS[k]}
    p_ok = not diff and not missing and not fdiff and pin['QtyMode'] == 'Fixed' and pin['fixedQty'] == 10.0
    _p('  script defaults: fgv5.DEFAULTS = the %d written here (and its fgf* = fgf.DEFAULTS): %s; the Pine file\'s own '
       'input lines give the same default for %d of them (different: %s; not found: %s); the filter block\'s %d inputs '
       '= fgf.DEFAULTS (different: %s); the file sizes with Fixed 10: %s'
       % (len(mine), m_ok, len(found), diff or 'none', missing or 'none', len(fgf.DEFAULTS), fdiff or 'none', p_ok))
    ok &= m_ok and p_ok
    # ---- the runner trail pair of every cell, and the table recomputed from the bar files
    t_ok = True
    parts = []
    for pair in PAIRS:
        for tf in TFS:
            r1, r2 = T_TRAIL.get((pair, tf), (1.5, 2.5))
            p10, cmax, w0, n = _own_p10(pair, tf)
            need = max(1.5, T_FLOOR[pair] / p10)
            i = next(j for j, v in enumerate(T_LADDER) if v >= need)
            tol = 0.0006 if T_P10[(pair, tf)] >= 0.06 else 0.00006        # the table prints 3 / 4 digits
            fl, _ = own_floor(pair, tf)
            c_ok = (C.runner_trail(pair, tf) == (r1, r2) and (T_LADDER[i], T_LADDER[i + 1]) == (r1, r2)
                    and abs(p10 - T_P10[(pair, tf)]) <= tol and all(fl.values()) and w0 > 1000
                    and C.FLOOR_PCT[pair] == T_FLOOR[pair])
            t_ok &= c_ok
            parts.append('%s %s p10 %.4f%% -> (%g, %g)%s' % (pair, tf, p10, r1, r2, '' if c_ok else ' WRONG'))
    _p('  runner trail (r1, r2) of every cell = the table of section 14; r1 = the smallest of %s >= max(1.5, floor / '
       'p10), r2 the next, with p10 (ATR(14)/close) recomputed here from the bar files and equal to the table\'s; '
       'every style above the floor (BTC 0.1 %%, XAU 0.05 %%): %s' % (list(T_LADDER), t_ok))
    _p('    ' + '; '.join(parts))
    ok &= t_ok and tuple(C.TRAIL_LADDER) == T_LADDER
    # ---- the fgv5 inputs of every setting, all 14 cells
    n_bad = n_all = 0
    for pair in PAIRS:
        for tf in TFS:
            for p in C.grid(pair, tf):
                sp = C.signal_params({k: p[k] for k in C.SIGNAL_DIMS})
                xp = C.exit_params({k: p[k] for k in C.EXIT_DIMS}, pair, tf)
                eff = fgv5._split({**sp, **xp})
                sig, o = fgv5_params(p, pair, tf)
                want = dict(sig, **o)
                got = {k: v for k, v in eff.items() if k not in fgv5.FGF_KEYS}
                fg = {k: eff[k] for k in fgv5.FGF_KEYS}
                n_all += 1
                if got != want or fg != {k: v for k, v in fgf.DEFAULTS.items() if k != 'fgfOn'} \
                        or set(sp) - set(SCRIPT_SIG) or set(fgv5.ALIASES.get(k, k) for k in xp) - set(SCRIPT_ORD) \
                        or C.inputs_of(p, pair, tf) != t_inputs(p, pair, tf):
                    n_bad += 1
                    if n_bad <= 3:
                        _p('  MAPPING %s %s %r: %r' % (pair, tf, p, {k: (got.get(k), want.get(k)) for k in want
                                                                      if got.get(k) != want.get(k)}))
    d_rows = [K.index(C.key(SPEC_DEFAULT))] if C.key(SPEC_DEFAULT) in K else []
    sig, o = fgv5_params(SPEC_DEFAULT, 'BTC', '240')
    def_ok = (K.count(C.key(SPEC_DEFAULT)) == 1 and dict(sig, **o) == dict(SCRIPT_SIG, **dict(SCRIPT_ORD, path='mag', cost='ours'))
              and C.PATH == 'mag' and C.COST == 'ours')
    _p('  fgv5 inputs of all %d settings of the 14 cells (signal_params + exit_params, resolved by fgv5._split) = the '
       'mapping written here; the input columns = the style\'s inputs written here: %d different; signal params only '
       'prepare keys, exit params only simulate keys' % (n_all, n_bad))
    _p('  the script\'s default setting is one row (row %s) of every cell; its inputs = the script defaults with path '
       'mag and cost ours: %s' % (d_rows, def_ok))
    ok &= n_bad == 0 and def_ok
    # ---- normalize: every grid row round-trips, as the file gives it
    n_rt = sum(C.normalize({'p_' + k: (float('nan') if v is None else v) for k, v in p.items()}) == p
               and C.normalize({k: v for k, v in p.items() if v is not None}) == p for p in G)
    forced = C.normalize(dict(SPEC_DEFAULT, slAtrMult=2.0, tpR=1.5))
    r_ok = (n_rt == len(G) and forced['slAtrMult'] is None and forced['tpR'] is None
            and C.row_of('BTC', '240', SPEC_DEFAULT) == K.index(C.key(SPEC_DEFAULT)))
    _p('  normalize(): %d of %d grid rows round-trip (p_ prefix, NaN / missing for unused); slAtrMult / tpR given with '
       'pips_default are dropped: %s' % (n_rt, len(G), r_ok))
    ok &= r_ok
    # ---- on data: inputs that a style does not set (or that it sets but cannot read) do not change a result
    rng = np.random.default_rng(20261127)
    cnt = dict(pips=0, fixed=0, partial=0, entry_pts=0)
    dif = dict(pips=0, fixed=0, partial=0, entry_pts=0)
    for pair, tf in CELLS:
        sub = None
        for si in rng.choice(18, size=4, replace=False):
            sig = C.SIGNALS[int(si)]
            P = fgv5.prepare(pair, tf, C.signal_params(sig))
            sub = sub or fgv5.get_sub(P)
            P['sub'] = sub
            by_style = {s: [j for j, x in enumerate(C.EXITS) if x['exitStyle'] == s] for s in SPEC_VALUES['exitStyle']}
            for i in [j for s in SPEC_VALUES['exitStyle'] for j in rng.choice(by_style[s], size=3, replace=False)]:
                x = C.EXITS[int(i)]
                xp = C.exit_params(x, pair, tf)
                s0 = fgv5.summary(P, fgv5.simulate(P, xp))
                if x['exitStyle'] == 'pips_default':
                    alts = [dict(xp, slAtrMult=2.0, tpR=5.0, runTrailAtr=6.5), dict(xp, useTrail=True, trailActPips=0.0),
                            dict(xp, slAtrMult=0.25, tpR=1.5)]
                    key = 'pips'
                elif x['exitStyle'] == 'fixed':
                    alts = [dict(xp, partPct=0.0, runBE=False, runTrailAtr=0.5), dict(xp, partPct=50.0, runTrailAtr=8.5),
                            dict(xp, runTrailPips=50.0, slPips=5.0, tpRPips=1.0)]
                    key = 'fixed'
                else:
                    alts = [dict(xp, useTrail=True, trailActAtr=0.0, trailDstAtr=0.05),
                            dict(xp, useTrail=True, trailActAtr=2.0, trailDstAtr=1.0),
                            dict(xp, slPips=5.0, runTrailPips=50.0)]
                    key = 'partial'
                for xa in alts:
                    sa = fgv5.summary(P, fgv5.simulate(P, xa))
                    cnt[key] += 1
                    dif[key] += not all(_same(s0[k], sa[k]) for k in s0)
                sa = fgv5.summary(P, fgv5.simulate(P, dict(xp, entryDistPoints=7.0)))     # DistUnit ATR
                cnt['entry_pts'] += 1
                dif['entry_pts'] += not all(_same(s0[k], sa[k]) for k in s0)
            del P
        _free()
    u_ok = all(v == 0 for v in dif.values()) and all(v > 0 for v in cnt.values())
    _p('  on data (%s): settings with a different result / settings tried: pips_default with other ATR stops, targets, '
       'runner ATR or a Fixed-style trail %d/%d; fixed with other partial / breakeven / runner / pips inputs %d/%d; '
       'part30 / run with a Fixed-style trail switched on or other pips inputs %d/%d; another entryDistPoints (DistUnit '
       'ATR) %d/%d: %s' % (', '.join('%s %s' % c for c in CELLS), dif['pips'], cnt['pips'], dif['fixed'], cnt['fixed'],
                           dif['partial'], cnt['partial'], dif['entry_pts'], cnt['entry_pts'], u_ok))
    ok &= u_ok
    # ---- the files
    fd = os.path.join(OUT, 'calib_fgv5_dims.json')
    if os.path.exists(fd):
        same = json.load(open(fd)) == C.DIMS
        _p('  out/calib_fgv5_dims.json equals DIMS: %s' % same)
        ok &= same
    else:
        # a cell file without the dims file is a run that did not finish its job (added by the sceptic: before,
        # a runner that never wrote dims.json passed this test; only test 4's own scratch run saw it)
        cells_out = sorted(f for f in os.listdir(OUT) if f.startswith('calib_fgv5_') and f.endswith('.parquet'))
        _p('  out/calib_fgv5_dims.json: not written%s' % (' although out/ holds %s: FAIL' % cells_out if cells_out else ' yet'))
        ok &= not cells_out
    # provenance: the sha256 written into a file is the code this process imported, not read again at write time
    o_sha = C._sha256
    C._sha256 = lambda path: 'read again at write time'
    try:
        m2 = C.file_meta('XAU', '240', N_GRID)
    finally:
        C._sha256 = o_sha
    prov = (m2['fgv5_sha256'] == C._SRC_SHA['fgv5'] and m2['fgf_sha256'] == C._SRC_SHA['fgf']
            and len(m2['fgv5_sha256']) == 64 == len(m2['fgf_sha256'])
            and os.path.samefile(fgv5.__file__, os.path.join(W, 'fgv5.py')) and os.path.samefile(fgf.__file__, os.path.join(W, 'fgf.py')))
    _p('  file metadata: the sha256 of fgv5.py and fgf.py is the one taken when the runner imported them: %s' % prov)
    ok &= prov
    P = fgv5.prepare('XAU', '240', {})
    s = fgv5.summary(P, fgv5.simulate(P, {'path': 'mag', 'cost': 'ours'}))
    cols_want = list(s.keys()) + T_MONEY
    scalar = all(isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool) for v in s.values())
    del P
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        types = {c: str(df[c].dtype) for c in _pcols()}
        t_ok = (types['p_burstAtrMult'] == types['p_entryDistAtrMult'] == types['p_slAtrMult'] == types['p_tpR'] == 'float64'
                and types['p_minAlignedZones'] == types['p_maxBarsHeld'] == 'int64'
                and types['p_fgfOn'] == types['p_inv'] == types['p_allowReverse'] == 'bool')
        f_ok = (len(df) == N_GRID and _keys(df) == S and list(df.columns) == _pcols() + T_INPUT_COLS + ['floor_ok'] + cols_want
                and scalar and all(k in df.columns for k in SUM_REQUIRED) and df['floor_ok'].dtype == bool
                and bool(df['floor_ok'].all()) and t_ok)
        ins = [{k: _py(v) for k, v in zip(T_INPUT_COLS, r)} for r in df[T_INPUT_COLS].itertuples(index=False)]
        in_ok = all(ins[i] == t_inputs(dict(zip(SPEC_DIMS, k)), pair, tf) for i, k in enumerate(S))
        nulls = {c: int(df[c].isna().sum()) for c in _sumcols(df) if df[c].isna().any()}
        f_ok &= set(nulls) <= {'pf', 'win_pct', 'avg_bars_held', 'max_notional_x', 'h1r_pct_money', 'h2r_pct_money'} and in_ok
        _p('  %s: %d rows; p_ columns = the grid in order (types %s); columns = %d p_ + the %d exit-style inputs (= the '
           'style\'s inputs written here, null where not set: %s) + floor_ok (True on every row) + the %d fields of '
           'fgv5.summary (all scalars) + the 3 money columns, nothing else: %s (NaN: %s)'
           % (src, len(df), 'ok' if t_ok else types, len(_pcols()), len(T_INPUT_COLS), in_ok, len(s), f_ok,
              nulls or 'none'))
        ok &= f_ok
        meta = C.read_meta(os.path.join(W, src))
        now = C.file_meta(pair, tf, N_GRID)
        fl, p10 = own_floor(pair, tf)
        m_ok = (meta is not None and all(meta.get(k) == now[k] for k in (
            'strategy', 'pair', 'tf', 'path', 'cost', 'settings', 'window', 'scoring', 'r_columns', 'money_columns',
            'sizing', 'exit_styles', 'runner_trail')) and meta['path'] == 'mag' and meta['cost'] == 'ours'
            and meta['r_columns'] == T_REMAP and meta['money_columns'] == {m: m[:-6] for m in T_MONEY}
            and 'R-based' in meta['scoring'] and meta['sizing'] == {'QtyMode': 'Fixed', 'fixedQty': 10.0, 'maxQty': 50.0, 'qtyStep': 1.0}
            and meta['runner_trail'] == list(T_TRAIL.get((pair, tf), (1.5, 2.5)))
            and meta['floor']['floor_ok'] == fl and abs(meta['floor']['p10_atr_pct'] - p10) < 1e-6
            and meta['floor']['table_matches_ladder'] is True)
        cur = meta is not None and meta.get('fgv5_sha256') == now['fgv5_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
        _p('    file metadata: %s, path %s, cost %s, %s settings, sizing %s, scoring "%s...", runner trail %s, floor '
           '(p10 %.4f %% = this file\'s): %s; written with the fgv5.py and fgf.py now on disk: %s'
           % ((meta or {}).get('strategy'), (meta or {}).get('path'), (meta or {}).get('cost'), (meta or {}).get('settings'),
              (meta or {}).get('sizing'), str((meta or {}).get('scoring'))[:40], (meta or {}).get('runner_trail'),
              ((meta or {}).get('floor') or {}).get('p10_atr_pct', float('nan')), m_ok,
              cur if cur else 'NO (rows are still checked against the module by tests 2, 3 and 7)'))
        ok &= m_ok
    _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 2. the default rows against the saved results
# ---------------------------------------------------------------------------------------------
def _one(pair, tf, p, *extra):
    cmd = [sys.executable, '-I', os.path.join(W, 'calib_fgv5.py'), '--one', pair, tf, json.dumps(p)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def test_2_default_rows():
    """(2) The default row, and the same with inv true, equal the saved default results of the module
    (out/inv_fgv5_<PAIR>_<TF>.json, same path and cost): runs normal/on/mag/ours and inverted/on/mag/ours on
    BTC 240 and XAU 240, normal/off/mag/ours and inverted/off/mag/ours on BTC 60 and XAU 60 (where the filter-on
    default takes no trade): through the command line, in the grid rows, and every saved run of all 14 cells
    through calib_fgv5.one; in every cell also one 'part30' and one 'run' setting through calib_fgv5.one (the
    cell's own runner trail, which differs on charts 1 and 5)."""
    ok = True
    P = fgv5.prepare('XAU', '240', {})
    sc = list(fgv5.summary(P, fgv5.simulate(P, {})).keys())
    del P
    dp = dict(SPEC_DEFAULT)
    # ---- (a) the command line
    plan = {('BTC', '240'): [('normal/on/mag/ours', dp, ()), ('inverted/on/mag/ours', dict(dp, inv=True), ()),
                             ('normal/on/tv/script', dp, ('--path', 'tv', '--cost', 'tv')),
                             ('inverted/on/tv/script', dict(dp, inv=True), ('--path', 'tv', '--cost', 'tv'))],
            ('XAU', '240'): [('normal/on/mag/ours', dp, ()), ('inverted/on/mag/ours', dict(dp, inv=True), ()),
                             ('normal/on/tv/script', dp, ('--path', 'tv', '--cost', 'tv')),
                             ('inverted/on/tv/script', dict(dp, inv=True), ('--path', 'tv', '--cost', 'tv'))],
            ('BTC', '60'): [('normal/off/mag/ours', dict(dp, fgfOn=False), ()),
                            ('inverted/off/mag/ours', dict(dp, fgfOn=False, inv=True), ()),
                            ('normal/on/mag/ours', dp, ()), ('normal/off/tv/script', dict(dp, fgfOn=False), ('--path', 'tv', '--cost', 'tv'))],
            ('XAU', '60'): [('normal/off/mag/ours', dict(dp, fgfOn=False), ()),
                            ('inverted/off/mag/ours', dict(dp, fgfOn=False, inv=True), ()),
                            ('normal/on/mag/ours', dp, ()), ('normal/off/tv/script', dict(dp, fgfOn=False), ('--path', 'tv', '--cost', 'tv'))]}
    firsts = {}
    for (pair, tf), cases in plan.items():
        J = json.load(open(os.path.join(OUT, 'inv_fgv5_%s_%s.json' % (pair, tf))))['runs']
        bad = []
        n_vals = 0
        for key, p, extra in cases:
            sv = _json_ref(J[key])
            dname, flt, path, cname = key.split('/')
            p_ok = sv['params'] == {'fgfOn': flt == 'on', 'fgvInv': dname == 'inverted', 'path': path,
                                    'cost': 'tv' if cname == 'script' else 'ours'}
            rc, out, err = _one(pair, tf, p, *extra)
            if rc != 0:
                bad.append('%s: exit code %d %s' % (key, rc, err.strip()[-200:]))
                continue
            o = json.loads(out)
            st = o.pop('setting')
            want = (('path', path), ('cost', 'tv' if cname == 'script' else 'ours'), ('sizing', 'script'),
                    ('QtyMode', 'Fixed'), ('fixedQty', 10.0), ('maxQty', 50.0), ('qtyStep', 1.0), ('in_grid', True))
            if any(st.get(k) != v for k, v in want) or not p_ok or list(o) != T_INPUT_COLS + ['floor_ok'] + sc + T_MONEY:
                bad.append('%s: setting echoed as %r / saved params %r' % (key, st, sv['params']))
            n_vals += _cmp_saved(o, sv, sc, key, bad)
            firsts[(pair, tf, key)] = o
        _p('  %s %-3s command line: %s = the saved runs: %d values (R columns vs net_r / h1_r / h2_r, *_money vs the '
           'money fields): %s' % (pair, tf, ', '.join(k for k, _, _ in cases), n_vals,
                                  'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b))))
        ok &= not bad and n_vals == len(cases) * (len(sc) + 3)
    for pair in ('BTC', 'XAU'):
        o = firsts.get((pair, '60', 'normal/on/mag/ours'))
        z = o is not None and o['trades'] == 0
        _p('  %s 60: the filter-on default takes no trade: %s; %s 240 default row: %s trades, R %+.2f (halves %+.2f / %+.2f), '
           'money net %+.3f %%; inverted %s trades, R %+.2f' % (pair, z, pair, firsts[(pair, '240', 'normal/on/mag/ours')]['trades'],
                                                               firsts[(pair, '240', 'normal/on/mag/ours')]['net_pct'],
                                                               firsts[(pair, '240', 'normal/on/mag/ours')]['h1r_pct'],
                                                               firsts[(pair, '240', 'normal/on/mag/ours')]['h2r_pct'],
                                                               firsts[(pair, '240', 'normal/on/mag/ours')]['net_pct_money'],
                                                               firsts[(pair, '240', 'inverted/on/mag/ours')]['trades'],
                                                               firsts[(pair, '240', 'inverted/on/mag/ours')]['net_pct']))
        ok &= z
    # ---- (b) the grid rows: BTC 240 / XAU 240 (filter on) and BTC 60 / XAU 60 (filter off)
    di = _default_sig_idx()
    for pair, tf, flt in (('BTC', '240', 'on'), ('XAU', '240', 'on'), ('BTC', '60', 'off'), ('XAU', '60', 'off')):
        if os.path.exists(_out_file(pair, tf)) or (pair, tf) in CELLS:
            df, src = _cell_df(pair, tf)
        elif FILES_ONLY:
            continue
        else:
            df, _ = C.run_cell(pair, tf, workers=3, sig_idx=di, write=False, verbose=False)
            src = '%d rows run here' % len(df)
        J = json.load(open(os.path.join(OUT, 'inv_fgv5_%s_%s.json' % (pair, tf))))['runs']
        idx = {k: i for i, k in enumerate(_keys(df))}
        bad = []
        n_vals = 0
        rows = {}
        for dname, inv in (('normal', False), ('inverted', True)):
            for fl in ('off', 'on'):
                key = (0.5, 2, fl == 'on', inv, 0.25, True, 'pips_default', None, None, 0)
                row = df.iloc[idx[key]]
                n_vals += _cmp_saved(row, _json_ref(J['%s/%s/mag/ours' % (dname, fl)]), sc, '%s/%s' % (dname, fl), bad)
                rows[(dname, fl)] = row
        d = rows[('normal', flt)]
        v = rows[('inverted', flt)]
        _p('  %s %-3s (%s): the 4 default rows (normal / inverted x filter off / on) = the saved mag / ours runs: %d '
           'values: %s | asked: filter %s default %d trades R %+.2f, inv true %d trades R %+.2f (money halves %s / %s)'
           % (pair, tf, src, n_vals, 'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
              flt, d['trades'], d['net_pct'], v['trades'], v['net_pct'], d['h1r_pct_money'], d['h2r_pct_money']))
        ok &= not bad and n_vals == 4 * (len(sc) + 3)
        _free()
    # ---- (c) every saved run of all 14 cells through calib_fgv5.one
    tot = dict(cells=0, runs=0, vals=0)
    for pair in PAIRS:
        for tf in TFS:
            J = json.load(open(os.path.join(OUT, 'inv_fgv5_%s_%s.json' % (pair, tf))))['runs']
            cache = {}
            bad = []
            n_runs = n_vals = 0
            for key, sv in J.items():
                dname, flt, path, cname = key.split('/')
                p = dict(dp, fgfOn=flt == 'on', inv=dname == 'inverted')
                o = C.one(pair, tf, p, path, 'tv' if cname == 'script' else 'ours', False, 'script', cache)
                n_vals += _cmp_saved(o, _json_ref(sv), sc, key, bad)
                n_runs += 1
            # the ATR runner styles through calib_fgv5.one in EVERY cell (added by the sceptic: the random rows of
            # test 3 are on the --cells, whose runner trail is (1.5, 2.5), and the saved runs are all pips_default,
            # so nothing else runs --one where (r1, r2) differ: BTC / XAU 1 and 5): one 'part30' and one 'run'
            # setting (filter off) = fgv5 with this file's own mapping, and the trail distance echoed = the table
            r1, r2 = T_TRAIL.get((pair, tf), (1.5, 2.5))
            rcache = {}
            n_atr = 0
            for st, rr in (('part30', r1), ('run', r2)):
                q = dict(dp, fgfOn=False, exitStyle=st, slAtrMult=0.5, tpR=1.5)
                o = C.one(pair, tf, q, 'mag', 'ours', False, 'script', cache)
                ref = dict(t_inputs(q, pair, tf))
                ref.update(t_scored(_ref_summary(pair, tf, q, cache=rcache)))
                n_atr += _cmp(o, ref, list(ref), '%s' % st, bad)
                se = o['setting']
                if (se['exit']['runTrailAtr'] != rr or o['runTrailAtr'] != rr or se['runner_trail'] != [r1, r2]
                        or se['exit']['partPct'] != {'part30': 30.0, 'run': 0.0}[st] or se['exit']['ExitMode'] != 'ATR'):
                    bad.append('%s: --one ran runTrailAtr %r / partPct %r (column %r), runner_trail %r; the table says %r'
                               % (st, se['exit']['runTrailAtr'], se['exit']['partPct'], o['runTrailAtr'],
                                  se['runner_trail'], (r1, r2)))
            n_vals += n_atr
            del rcache
            d = J['normal/on/mag/ours']
            _p('  %s %-3s: %d saved runs + part30 / run (runner trail %g / %g) = calib_fgv5.one: %d values: %s | saved '
               'default mag / ours: %d trades, net_r %+.2f, money %+.3f %%, neg_equity_bars %d'
               % (pair, tf, n_runs, r1, r2, n_vals,
                  'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                  d['trades'], d['net_r'], d['net_pct'], d['neg_equity_bars']))
            ok &= not bad and n_runs == 16 and n_atr == 2 * (len(T_INPUT_COLS) + len(sc) + 3)
            tot['cells'] += 1
            tot['runs'] += n_runs
            tot['vals'] += n_vals
            del cache
            _free()
    _p('  %d cells: %d saved runs, %d values compared' % (tot['cells'], tot['runs'], tot['vals']))
    return ok and tot['cells'] == 14


# ---------------------------------------------------------------------------------------------
# 3. random rows through --one
# ---------------------------------------------------------------------------------------------
def test_3_one_rows():
    """(3) 30 random rows per cell recomputed one at a time through `calib_fgv5.py --one` (a new process each, the
    row's p_ columns as its JSON) equal the sweep rows on every non-p_ column; the same rows through fgv5 with this
    file's own mapping and remap; --path / --cost, --risk-sizing, --script-sizing, --off-grid; bad input refused."""
    ok = True
    rng = np.random.default_rng(31)
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        rc_cols = _rescols(df)
        keys = _keys(df)
        pick = sorted(int(i) for i in rng.choice(len(df), size=30, replace=False))
        fl, _ = own_floor(pair, tf)
        bad = []
        n_vals = n_run = n_tr = 0
        cover = {n: set() for n in SPEC_DIMS}
        cache = {}
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
            if (st['strategy'], st['pair'], st['tf'], st['path'], st['cost'], st['p'], st['in_grid'], st['row'], st['sizing'],
                    st['runner_trail']) != ('fgv5', pair, tf, 'mag', 'ours', p, True, i, 'script', list(T_TRAIL.get((pair, tf), (1.5, 2.5)))):
                bad.append('row %d: setting echoed as %r' % (i, st))
            if list(o) != rc_cols:
                bad.append('row %d: fields %r' % (i, list(o)))
                continue
            n_vals += _cmp(row, o, rc_cols, 'row %d --one' % i, bad)
            ref = t_scored(_ref_summary(pair, tf, p, cache=cache))
            ref.update(t_inputs(p, pair, tf))
            ref['floor_ok'] = fl[p['exitStyle']]
            n_run += _cmp(row, ref, rc_cols, 'row %d own mapping' % i, bad)
            n_tr += int(row['trades'])
        dt = time.time() - t0
        cov = all(len(cover[n] - {None}) >= 2 for n in SPEC_DIMS)
        _p('  %s %s (%s): 30 random rows, each in its own `--one` process: %d values, and through fgv5 with the mapping '
           'and the remap written here: %d values (%d trades): %s; at least two values of every dimension among them: '
           '%s (%.1fs)' % (pair, tf, src, n_vals, n_run, n_tr,
                           'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                           cov, dt))
        ok &= not bad and n_vals == 30 * len(rc_cols) == n_run
        # --path / --cost and the sizing controls
        bad = []
        n = 0
        moved = {'--risk-sizing': 0, '--path tv --cost tv': 0}
        sub = [pick[j] for j in (0, 9, 19, 29)]
        for i in sub:
            row = df.iloc[i]
            p = dict(zip(SPEC_DIMS, keys[i]))
            for extra, kw in ((('--path', 'tv', '--cost', 'tv'), dict(path='tv', cost='tv')),
                              (('--path', 'tv', '--cost', 'stress'), dict(path='tv', cost='stress')),
                              (('--path', 'mag', '--cost', 'stress'), dict(path='mag', cost='stress')),
                              (('--risk-sizing',), dict(sizing='risk')),
                              (('--script-sizing',), dict()),
                              (('--risk-sizing', '--path', 'tv', '--cost', 'tv'), dict(sizing='risk', path='tv', cost='tv'))):
                rc, out, err = _one(pair, tf, p, *extra)
                if rc != 0:
                    bad.append('row %d %s: exit code %d' % (i, ' '.join(extra), rc))
                    continue
                o = json.loads(out)
                st = o['setting']
                risk = kw.get('sizing') == 'risk'
                if (st['path'], st['cost'], st['sizing'], st['QtyMode'], st['maxQty'], st['qtyStep'], st['row']) != (
                        kw.get('path', 'mag'), kw.get('cost', 'ours'), 'risk' if risk else 'script',
                        'Risk %' if risk else 'Fixed', 1e9 if risk else 50.0, 0.000001 if risk else 1.0, i):
                    bad.append('row %d %s: echoed %r' % (i, ' '.join(extra), st))
                ref = t_scored(_ref_summary(pair, tf, p, kw.get('path', 'mag'), kw.get('cost', 'ours'), kw.get('sizing', 'script'), cache))
                n += _cmp(o, ref, list(ref), 'row %d %s' % (i, ' '.join(extra)), bad)
                if extra == ('--script-sizing',):
                    n += _cmp(o, row, rc_cols, 'row %d --script-sizing = the row' % i, bad)
                for name in moved:
                    if ' '.join(extra) == name:
                        moved[name] += not all(_same(o[k], row[k]) for k in _sumcols(df))
        m_ok = all(v > 0 for v in moved.values())
        _p('  %s %s: 4 rows x (--path tv --cost tv | --path tv --cost stress | --path mag --cost stress | --risk-sizing | '
           '--script-sizing (= the row) | --risk-sizing --path tv --cost tv) = fgv5 with that path, cost and sizing: %d '
           'values: %s; rows whose result moves with --risk-sizing: %d of 4, with --path tv --cost tv: %d of 4'
           % (pair, tf, n, 'all equal' if not bad else '; '.join(b for b in bad if b), moved['--risk-sizing'],
              moved['--path tv --cost tv']))
        ok &= not bad and m_ok
        del cache
        _free()
    # bad input, off-grid
    pair, tf = CELLS[0]
    p = dict(SPEC_DEFAULT)
    cases = (('unknown dimension', dict(p, riskPct=2.0), ()),
             ('value not in the grid', dict(p, exitStyle='fixed', slAtrMult=0.75, tpR=3.0), ()),
             ('missing used dimension', {k: v for k, v in p.items() if k != 'inv'}, ()),
             ('ATR style without a stop', dict(p, exitStyle='part30'), ()),
             ('unknown exit style', dict(p, exitStyle='trail'), ('--off-grid',)),
             ('below the Pine minimum', dict(p, exitStyle='fixed', slAtrMult=0.001, tpR=3.0), ('--off-grid',)),
             ('both sizings', p, ('--risk-sizing', '--script-sizing')),
             ('not an object', [1, 2], ()))
    res = []
    for name, q, extra in cases:
        rc, out, err = _one(pair, tf, q, *extra)
        res.append((name, rc, out.strip() == '' and 'calib_fgv5.py --one' in err))
    q = dict(p, burstAtrMult=0.4, minAlignedZones=1, exitStyle='run', slAtrMult=0.75, tpR=2.0, maxBarsHeld=6, entryDistAtrMult=0.1)
    rc, out, err = _one(pair, tf, q, '--off-grid')
    og = rc == 0
    if og:
        o = json.loads(out)
        ref = t_scored(_ref_summary(pair, tf, q))
        og = o['setting']['in_grid'] is False and o['setting']['row'] is None and all(_same(o[k], ref[k]) for k in ref)
    b_ok = all(rc == 2 and e for _, rc, e in res) and og
    _p('  bad input is refused (exit code 2, nothing on stdout): %s; --off-grid runs a setting outside the grid (burst '
       '0.4, zones 1, entry 0.1, run style with stop 0.75 / tpR 2, time stop 6) = fgv5 with the mapping written here: %s'
       % (', '.join('%s -> %d' % (n, rc) for n, rc, _ in res), og))
    _free()
    return ok and b_ok


# ---------------------------------------------------------------------------------------------
# 4. worker count
# ---------------------------------------------------------------------------------------------
def _sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def test_4_workers():
    """(4) XAU 240, the full grid with 1 worker and with 3 workers (files in calib_tmp_fgv5/w1 and w3, not out/):
    every row and column identical, the two files byte for byte; equal to out/ when it exists. With 1 worker
    everything runs in this process: fgv5.prepare once per signal setting (18), the signal kernel and the zones
    once per signal input (9), fgv5.simulate once per row, the filter permissions once."""
    d1 = os.path.join(TMP, 'w1')
    d3 = os.path.join(TMP, 'w3')
    calls = dict(prepare=0, simulate=0, fgf=0, signal=0, zones=0)
    o_prep, o_sim, o_fgf, o_sig, o_tz = fgv5.prepare, fgv5.simulate, fgf.fgf_permissions, fgv5._signal_k, fgv5.trade_zone

    def wrap(name, f):
        def g(*a, **k):
            calls[name] += 1
            return f(*a, **k)
        return g

    _free()
    fgv5.prepare, fgv5.simulate, fgf.fgf_permissions = wrap('prepare', o_prep), wrap('simulate', o_sim), wrap('fgf', o_fgf)
    fgv5._signal_k, fgv5.trade_zone = wrap('signal', o_sig), wrap('zones', o_tz)
    try:
        a, ia = C.run_cell('XAU', '240', workers=1, out_dir=d1, verbose=False)
    finally:
        fgv5.prepare, fgv5.simulate, fgf.fgf_permissions, fgv5._signal_k, fgv5.trade_zone = o_prep, o_sim, o_fgf, o_sig, o_tz
    _free()
    b, ib = C.run_cell('XAU', '240', workers=3, out_dir=d3, verbose=False)
    _free()
    f1 = os.path.join(d1, 'calib_fgv5_XAU_240.parquet')
    f3 = os.path.join(d3, 'calib_fgv5_XAU_240.parquet')
    fa = pd.read_parquet(f1)
    fb = pd.read_parquet(f3)
    same = fa.equals(fb) and a.equals(b) and a.equals(fa) and len(fa) == N_GRID and list(fa.columns) == list(fb.columns) \
        and all(fa[c].dtype == fb[c].dtype for c in fa.columns)
    byt = _sha(f1) == _sha(f3)
    dims = json.load(open(os.path.join(d1, 'calib_fgv5_dims.json'))) == C.DIMS == json.load(open(os.path.join(d3, 'calib_fgv5_dims.json')))
    once = calls == dict(prepare=18, simulate=N_GRID + 1, fgf=1, signal=9, zones=9) and ia['prepares'] == 18 == ib['prepares']
    _p('  XAU 240: %d rows x %d columns; 1 worker %.1fs (runs %.1fs), 3 workers %.1fs (runs %.1fs, speed-up x%.2f): '
       'frames %s, files %s (sha256 %s), dims.json = DIMS: %s'
       % (len(fa), len(fa.columns), ia['t_total'], ia['t_run'], ib['t_total'], ib['t_run'], ia['t_run'] / ib['t_run'],
          'identical' if same else 'DIFFERENT', 'byte for byte equal' if byt else 'DIFFERENT bytes', _sha(f3)[:16], dims))
    _p('  the 1-worker run called fgv5.prepare %d times (18 signal settings), the signal kernel %d and the zones %d times '
       '(9 signal inputs: filter off and on share one), fgv5.simulate %d times (%d rows + 1 to load the kernel), '
       'fgf.fgf_permissions %d time(s): signals prepared once per signal setting and reused for all its exit settings: '
       '%s' % (calls['prepare'], calls['signal'], calls['zones'], calls['simulate'], N_GRID, calls['fgf'], once))
    ok = same and byt and dims and once
    fo = _out_file('XAU', '240')
    if os.path.exists(fo):
        fo_df = pd.read_parquet(fo)
        again = fo_df.equals(fb)
        _p('  out/calib_fgv5_XAU_240.parquet (the production run) equals this re-run: %s (bytes %s)'
           % (again, 'equal' if _sha(fo) == _sha(f3) else 'different'))
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
    """Samples twice a second, from a helper process, this process and its child processes (the forked workers,
    and the helper itself, which is small): n children, the sum of their PSS (a page shared copy-on-write by k
    processes counts 1 / k in each, so the sum is the physical memory they hold together), this process' RSS and
    the largest private dirty memory of a child."""

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
    """(5) BTC 1 (the largest cell): the real preparation of all 18 signal settings, then one pass = the 1,776 exit
    settings of one signal input (filter off + on) with 3 workers, for the default, the busiest and the quietest
    signal input; extrapolated to the 9 signal inputs. The full grid must stay under 45 min, the memory under 4 GB."""
    _free()
    load0 = os.getloadavg()[0]
    with _MemWatch() as mp0:
        cell = C.prepare_cell('BTC', '1')
    prep_peak = max((x[2] for x in mp0.samples), default=0) / 1024.0
    prep_end = mp0.samples[-1][2] / 1024.0 if mp0.samples else float('nan')
    t_prep = cell['t_prep']
    nsig = {si: int(cell['P'][si]['sig_buy'] + cell['P'][si]['sig_sell']) for si in cell['idx']}
    uniq = {k: len(set(id(cell['P'][si][k]) for si in cell['idx'])) for k in C._ARRAYS}
    _p('  BTC 1: %d chart bars, %d 1-minute bars; all 18 signal settings prepared in %.1fs (signals %.1fs, sub-bars '
       '%.1fs, kernel %.1fs); signal bars %d .. %d (default %d); distinct arrays kept for the 18 prepared inputs: %s; '
       'this process during the preparation: peak RSS %.0f MB (sampled), %.0f MB at its end (caches released)'
       % (cell['bars'], cell['n_sub'], t_prep, cell['t_sig'], cell['t_sub'], cell['t_jit'], min(nsig.values()),
          max(nsig.values()), nsig[_default_sig_idx()[0]], ', '.join('%s %d' % kv for kv in uniq.items()), prep_peak, prep_end))
    order = sorted(range(0, 18, 2), key=lambda si: nsig[si])
    passes = (('default', _default_sig_idx()), ('busiest', [order[-1], order[-1] + 1]), ('quietest', [order[0], order[0] + 1]))
    t3, per, cpu3, mem = [], [], [], []
    keep = None
    for name, idx in passes:
        l0 = os.getloadavg()[0]
        with _MemWatch() as mw:
            res, info = C.run_prepared(cell, workers=3, sig_idx=idx)
        mem.append(mw)
        t3.append(info['t_run'])
        per.append(info['busy'] / info['settings'])
        cpu3.append(info['cpu'] / 3.0)           # the pass with a free CPU per worker
        s = C.SIGNALS[idx[0]]
        _p('  pass %-8s (burst %g, zones %d; %d signal bars with the filter off): %d settings, 3 workers %.1fs wall (%.4fs '
           'per setting per worker, workers busy %.0f%%); worker CPU %.4fs per setting = %.1fs with a free CPU per worker; '
           'load average %.2f -> %.2f' % (name, s['burstAtrMult'], s['minAlignedZones'], nsig[idx[0]], info['settings'],
                                          info['t_run'], per[-1], 100.0 * info['busy'] / (3 * info['t_run']),
                                          info['cpu'] / info['settings'], cpu3[-1], l0, os.getloadavg()[0]))
        if name == 'default':
            keep = res
    idx = passes[0][1]
    xs = list(range(0, 888, 12))
    res1, info1 = C.run_prepared(cell, workers=1, sig_idx=idx, x_idx=xs)
    same = all(all(_same(x, y) for x, y in zip(res1[si][j], keep[si][xi])) for si in idx for j, xi in enumerate(xs))
    _p('  pass default, every 12th exit setting with 1 worker: %d settings %.1fs (%.4fs per setting); rows identical to '
       'the 3-worker pass: %s' % (info1['settings'], info1['t_run'], info1['t_run'] / info1['settings'], same))
    est = t_prep + 9 * float(np.mean(t3))
    hi = t_prep + 9 * max(t3)
    one_w = t_prep + 9 * 1776 * (info1['t_run'] / info1['settings']) / 3.0
    free = t_prep + 9 * float(np.mean(cpu3))
    free_hi = t_prep + 9 * max(cpu3)
    _p('  full grid BTC 1 with 3 workers, each with a free CPU (worker CPU time) = preparation %.1fs + 9 passes: %.1f min '
       '(mean pass), %.1f min (every pass as slow as the slowest): the criterion, limit 45 min: %s'
       % (t_prep, free / 60.0, free_hi / 60.0, free_hi < 45 * 60.0))
    _p('  the same on the wall clock at the present load (load average %.2f -> %.2f; other jobs share the 4 CPUs): %.1f '
       'min (mean pass), %.1f min (slowest); from the 1-worker sample / 3: %.1f min%s'
       % (load0, os.getloadavg()[0], est / 60.0, hi / 60.0, one_w / 60.0,
          '' if hi < 45 * 60.0 else ' -- WARNING: over 45 min at this load; run BTC 1 when 3 CPUs are free'))
    pk = [m.peak(3) for m in mem]
    mem_ok = all(p is not None for p in pk) and prep_peak > 0
    if mem_ok:
        top = max(pk, key=lambda x: x[1])
        mem_ok = top[1] / 1024.0 < MEM_LIMIT_MB and prep_peak < MEM_LIMIT_MB and top[2] / 1024.0 < MEM_LIMIT_MB
        _p('  memory during the 3-worker passes (%d samples with the parent and 3 workers alive): parent + workers hold '
           '%.0f MB together (sum of PSS; parent RSS %.0f MB, a worker\'s own private memory at most %.0f MB); the '
           'preparation peaked at %.0f MB RSS; limit %d MB: %s'
           % (sum(len([x for x in m.samples if x[0] >= 3]) for m in mem), top[1] / 1024.0, top[2] / 1024.0,
              max(p[3] for p in pk) / 1024.0, prep_peak, MEM_LIMIT_MB, mem_ok))
    else:
        _p('  memory: no sample with the parent and 3 workers alive (/proc/<pid>/smaps_rollup not readable?)')
    del cell
    _free()
    return same and free_hi < 45 * 60.0 and mem_ok


# ---------------------------------------------------------------------------------------------
# 6. what every row must satisfy
# ---------------------------------------------------------------------------------------------
def test_6_row_consistency():
    """Rows hold what they claim, whatever the data: trade counts add up, the R columns are the R sums and the money
    columns fgv5's money fields, the window, a switch that is off leaves no trace, every dimension changes results
    somewhere, every row has its direction twin and differs from it, calib_analyze reads every p_ value."""
    ok = True
    live_all = {}
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        ex = ['exit_' + k for k in ('sl', 'tp', 'tp_part', 'be', 'runner', 'trail', 'reverse', 'opp', 'time', 'end')]
        parts_c = [c for c in df.columns if c.startswith('part_')]
        tr = df['trades']
        st = df['p_exitStyle'].to_numpy(dtype=object)
        fixed = st == 'fixed'
        partial = ~fixed
        run = st == 'run'
        normal = ~df['p_inv'].to_numpy(bool)
        chk = {
            'trades = long + short': (tr == df['long'] + df['short']).all(),
            'trades = h1_trades + h2_trades': (tr == df['h1_trades'] + df['h2_trades']).all(),
            'trades = sum of the 10 exit kinds': (tr == df[ex].sum(axis=1)).all(),
            'net_pct = net_r, h1r_pct = h1_r, h2r_pct = h2_r (exact)': ((df['net_pct'] == df['net_r']) & (df['h1r_pct'] == df['h1_r'])
                                                                       & (df['h2r_pct'] == df['h2_r'])).all(),
            'net_r = h1_r + h2_r': np.allclose(df['h1_r'] + df['h2_r'], df['net_r'], rtol=1e-9, atol=1e-7),
            'R columns finite on every row': np.isfinite(df[['net_pct', 'h1r_pct', 'h2r_pct']].to_numpy()).all(),
            'R columns 0 without trades': (df.loc[tr == 0, ['net_pct', 'h1r_pct', 'h2r_pct']] == 0).all().all(),
            'net_pct_money = (final_equity - 100,000) / 100,000': ((df['final_equity'] - INIT) / INIT * 100 == df['net_pct_money']).all(),
            'half1_pct + half2_pct = net_pct_money': np.allclose(df['half1_pct'] + df['half2_pct'], df['net_pct_money'], rtol=0, atol=1e-9),
            'money halves NaN only with an entry at equity <= 0 (min_equity <= 0 or a reversal)':
                (~(df['h1r_pct_money'].isna() | df['h2r_pct_money'].isna()) | (df['min_equity'] <= 0) | (df['exit_reverse'] > 0)).all(),
            'window': ((df['start'] == T_WINDOWS[pair][0]) & (df['end'] == T_WINDOWS[pair][1])).all() and df['bars'].nunique() == 1,
            'fixed style: no partial, breakeven or runner fills': (df.loc[fixed, ['exit_tp_part', 'exit_be', 'exit_runner', 'be_trades', 'be_no_tp'] + parts_c] == 0).all().all(),
            'partial styles: no full target (XL), no Fixed-style trail': (df.loc[partial, ['exit_tp', 'exit_trail']] == 0).all().all(),
            'run style (partPct 0): no partial target': (df.loc[run, ['exit_tp_part', 'part_tp_part']] == 0).all().all(),
            'useTrail off everywhere: no trail exit': (df['exit_trail'] == 0).all(),
            'time stop off: no time exit': (df.loc[df['p_maxBarsHeld'] == 0, 'exit_time'] == 0).all(),
            'exitOnOpposite off: no opp exit': (df['exit_opp'] == 0).all(),
            'reverse off: no reversal': (df.loc[~df['p_allowReverse'].to_numpy(bool), 'exit_reverse'] == 0).all(),
            'filter off: nothing blocked': (df.loc[~df['p_fgfOn'].to_numpy(bool), ['blocked_long', 'blocked_short']] == 0).all().all(),
            'blocked <= raw': ((df['blocked_long'] <= df['raw_long']) & (df['blocked_short'] <= df['raw_short'])).all(),
            'pf / win NaN only without trades': ((df['pf'].isna() == (tr == 0)) & (df['win_pct'].isna() == (tr == 0))).all(),
            'costs > 0 with trades': ((df['costs'] > 0) == (tr > 0)).all(),
            'cost ours: no slippage in the fills': (df['slippage_paid'] == 0).all(),
            'Fixed 10 units: no quantity floored to zero': (df['zero_qty'] == 0).all(),
            'at most one trade closed by the window end': (df['exit_end'] <= 1).all(),
            'TradingView rows >= trades': (df['tv_rows'] >= tr).all(),
            'normal direction: be_no_tp 0 (SPEC 8)': (df.loc[normal, 'be_no_tp'] == 0).all(),
            'the signal bars are the signal setting\'s': df.groupby(['p_burstAtrMult', 'p_minAlignedZones'])[['sig_buy', 'sig_sell']].nunique().max().max() == 1,
            'floor_ok on every row': bool(df['floor_ok'].all()),
        }
        failed = [k for k, v in chk.items() if not bool(v)]
        sc = _sumcols(df)
        sig = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
        K = _keys(df)
        # the p_ values as text, 'None' for an unused dimension (a missing value must not drop its group: pandas 3's
        # astype(str) keeps missing values missing and groupby drops them)
        ps = {c: np.array([repr(k[j]) for k in K]) for j, c in enumerate(_pcols())}
        nonpips = st != 'pips_default'
        joint = (('burstAtrMult', ['p_burstAtrMult'], None), ('minAlignedZones', ['p_minAlignedZones'], None),
                 ('fgfOn', ['p_fgfOn'], None), ('inv', ['p_inv'], None), ('entryDistAtrMult', ['p_entryDistAtrMult'], None),
                 ('allowReverse', ['p_allowReverse'], None),
                 ('exit rule (exitStyle, slAtrMult, tpR)', ['p_exitStyle', 'p_slAtrMult', 'p_tpR'], None),
                 ('exitStyle alone (ATR styles)', ['p_exitStyle'], nonpips), ('slAtrMult alone', ['p_slAtrMult'], nonpips),
                 ('tpR alone', ['p_tpR'], nonpips), ('maxBarsHeld', ['p_maxBarsHeld'], None))
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
        pos = {k: i for i, k in enumerate(K)}
        j_inv = SPEC_DIMS.index('inv')
        twin = np.array([pos.get(k[:j_inv] + (not k[j_inv],) + k[j_inv + 1:], -1) for k in K])
        no_twin = int((twin < 0).sum())
        twin = np.where(twin < 0, np.arange(len(K)), twin)
        same_twin = int(((sig == sig[twin]) & (tr.to_numpy() > 0)).sum())
        try:
            import calib_analyze
            codes = calib_analyze.codes_of(df, C.DIMS)
            jdir = next(j for j, d in enumerate(C.DIMS) if d['name'].lower() in calib_analyze.DIR_NAMES)
            unused = sorted(set(C.DIM_NAMES[j] for j in np.flatnonzero((codes < 0).any(axis=0))))
            an = (C.DIM_NAMES[jdir] == 'inv' and unused == sorted(SPEC_UNUSED) and len(np.unique(codes, axis=0)) == len(df)
                  and 'floor_ok' in df.columns and np.isfinite(df[['h1r_pct', 'h2r_pct']].to_numpy()).all())
            an_txt = ('calib_analyze.codes_of reads every p_ value (direction dimension inv; unused only in %s), the halves '
                      'it reads are finite: %s' % (unused, an))
        except Exception as e:      # noqa: BLE001
            an = False
            an_txt = 'calib_analyze.codes_of FAILED: %r' % (e,)
        n_distinct = len(np.unique(sig))
        el = (df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)
        cand = int((el & (df['h1r_pct'] > 0) & (df['h2r_pct'] > 0)).sum())
        nan_money = int((df['h1r_pct_money'].isna() | df['h2r_pct_money'].isna()).sum())
        _p('  %s %s (%s): %d rows, %d checks: %s' % (pair, tf, src, len(df), len(chk),
                                                     'all hold' if not failed else 'FAILED: ' + '; '.join(failed)))
        _p('    groups differing only in one dimension (all results distinct / some distinct / groups): %s' % '; '.join(parts))
        _p('    trades %d .. %d (median %d); distinct results %d of %d rows; rows with trades equal to their direction twin '
           '(inv flipped): %d; rows without a twin: %d; rows whose equity went to zero or below: %d, with a money half NaN: '
           '%d; be_no_tp > 0 (inverted rows): %d; rows with >= 30 trades in each half: %d, of which positive in both R '
           'halves: %d' % (tr.min(), tr.max(), int(tr.median()), n_distinct, len(df), same_twin, no_twin,
                           int((df['neg_equity_bars'] > 0).sum()), nan_money, int((df['be_no_tp'] > 0).sum()), int(el.sum()), cand))
        _p('    every row is in a group of every analysis above (no row dropped): %s; %s' % (n_rows_g == n_sel_g, an_txt))
        ok &= not failed and same_twin == 0 and n_rows_g == n_sel_g and an and no_twin == 0
    dead = [k for k, v in live_all.items() if v == 0]
    _p('  every dimension changes results in at least one group over the cells: %s' % ('yes' if not dead else 'NO: %s' % dead))
    return ok and not dead


# ---------------------------------------------------------------------------------------------
# 7. every row
# ---------------------------------------------------------------------------------------------
def _groups(keys, pair, tf):
    """The rows of a file grouped by their fgv5.prepare inputs (this file's own mapping)."""
    groups = {}
    for i, k in enumerate(keys):
        p = dict(zip(SPEC_DIMS, k))
        sig, o = fgv5_params(p, pair, tf)
        groups.setdefault(tuple(sorted((a, repr(b)) for a, b in sig.items())), (sig, []))[1].append((i, p, o))
    return groups


def test_7_all_rows():
    """Every row of the cells' files, not a sample: recomputed in this process with fgv5.prepare once per signal
    setting and fgv5.simulate + fgv5.summary per row, the inputs from this file's own mapping (fgv5_params), the
    row from this file's own remap (t_scored), input columns (t_inputs) and floor (own_floor); every non-p_ value
    must be equal. A sample of 30 rows cannot see one stale signal setting or one displaced chunk of rows; this does."""
    ok = True
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        rc = _rescols(df)
        keys = _keys(df)
        vals = [df[c].tolist() for c in rc]
        groups = _groups(keys, pair, tf)
        fl, _ = own_floor(pair, tf)
        t0 = time.time()
        n_vals = 0
        bad_rows = []
        bad_groups = 0
        sub = None
        for gk in sorted(groups):
            sig, items = groups[gk]
            P = fgv5.prepare(pair, tf, sig)
            if sub is None:
                sub = (P['w0'], P['w1'], fgv5.get_sub(P))
            assert (P['w0'], P['w1']) == sub[:2]
            P['sub'] = sub[2]
            n_bad0 = len(bad_rows)
            for i, p, o in items:
                ref = dict(t_inputs(p, pair, tf))
                ref['floor_ok'] = fl[p['exitStyle']]
                ref.update(t_scored(fgv5.summary(P, fgv5.simulate(P, o))))
                if list(ref) != rc:
                    bad_rows.append(i)
                    continue
                n_vals += len(rc)
                if not all(_same(vals[j][i], ref[c]) for j, c in enumerate(rc)):
                    bad_rows.append(i)
            bad_groups += len(bad_rows) > n_bad0
            del P
        c_ok = not bad_rows and len(groups) == 18 and n_vals == len(df) * len(rc) and len(df) == N_GRID
        _p('  %s %s (%s): all %d rows recomputed (fgv5.prepare for each of the %d signal settings, fgv5.simulate + '
           'fgv5.summary per row, this file\'s remap): %d values, %s (%.1fs)'
           % (pair, tf, src, len(keys), len(groups), n_vals,
              'all equal' if c_ok else '%d ROWS DIFFER in %d signal settings (first rows %s)' % (len(bad_rows), bad_groups, bad_rows[:8]),
              time.time() - t0))
        ok &= c_ok
        _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 8. every cell that has a file
# ---------------------------------------------------------------------------------------------
def test_8_every_cell():
    """Every cell with a file in out/: the file holds the grid in order with the asked-for columns and metadata,
    and 4 random rows of EVERY signal setting (72 rows per cell) recomputed in this process (fgv5.prepare per signal
    setting, fgv5.simulate + fgv5.summary per row, this file's own mapping and remap) equal the file."""
    ok = True
    rng = np.random.default_rng(8)
    n_cells = 0
    S = spec_grid()
    for pair in PAIRS:
        for tf in TFS:
            f = _out_file(pair, tf)
            if not os.path.exists(f):
                continue
            n_cells += 1
            t0 = time.time()
            df = pd.read_parquet(f)
            rc = _rescols(df)
            keys = _keys(df)
            meta = C.read_meta(f)
            now = C.file_meta(pair, tf, N_GRID)
            fl, p10 = own_floor(pair, tf)
            g_ok = (len(df) == N_GRID and keys == S and all(k in rc for k in SUM_REQUIRED) and meta is not None
                    and all(meta.get(k) == now[k] for k in ('strategy', 'pair', 'tf', 'path', 'cost', 'settings', 'window',
                                                            'scoring', 'r_columns', 'money_columns', 'sizing',
                                                            'exit_styles', 'runner_trail'))
                    and meta['runner_trail'] == list(T_TRAIL.get((pair, tf), (1.5, 2.5)))
                    and bool(((df['start'] == T_WINDOWS[pair][0]) & (df['end'] == T_WINDOWS[pair][1])).all())
                    and bool(df['floor_ok'].all()) and all(fl.values()) and meta['floor']['floor_ok'] == fl
                    and abs(meta['floor']['p10_atr_pct'] - p10) < 1e-6)
            cur = meta is not None and meta.get('fgv5_sha256') == now['fgv5_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
            groups = _groups(keys, pair, tf)
            n_rows = n_vals = 0
            bad_rows = []
            sub = None
            for gk in sorted(groups):
                sig, items = groups[gk]
                P = fgv5.prepare(pair, tf, sig)
                if sub is None:
                    sub = (P['w0'], P['w1'], fgv5.get_sub(P))
                assert (P['w0'], P['w1']) == sub[:2]
                P['sub'] = sub[2]
                for j in sorted(int(x) for x in rng.choice(len(items), size=min(4, len(items)), replace=False)):
                    i, p, o = items[j]
                    ref = dict(t_inputs(p, pair, tf))
                    ref['floor_ok'] = fl[p['exitStyle']]
                    ref.update(t_scored(fgv5.summary(P, fgv5.simulate(P, o))))
                    n_rows += 1
                    n_vals += len(rc)
                    if list(ref) != rc or not all(_same(df[c].iat[i], ref[c]) for c in rc):
                        bad_rows.append(i)
                del P
            h = pd.util.hash_pandas_object(df[_sumcols(df)], index=False).to_numpy()
            c_ok = g_ok and not bad_rows and len(groups) == 18 and n_rows == 72
            tr = df['trades']
            _p('  %s %-3s: %d rows, the grid in order, metadata, window, floor_ok: %s; written with the fgv5.py / fgf.py now '
               'on disk: %s; %d rows (4 of each of the %d signal settings) recomputed: %d values, %s; distinct results %d; '
               'trades %d .. %d; rows with equity <= 0 at a bar close: %d (%.1fs)'
               % (pair, tf, len(df), g_ok, cur, n_rows, len(groups), n_vals,
                  'all equal' if not bad_rows else '%d ROWS DIFFER: %s' % (len(bad_rows), bad_rows[:8]),
                  len(np.unique(h)), tr.min(), tr.max(), int((df['neg_equity_bars'] > 0).sum()), time.time() - t0))
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
    _p('calib_tests_fgv5.py: cells %s; fgv5.py sha256 %s; calib_fgv5.py sha256 %s; load average %.2f'
       % (', '.join('%s %s' % c for c in CELLS), _sha(os.path.join(W, 'fgv5.py'))[:16],
          _sha(os.path.join(W, 'calib_fgv5.py'))[:16], os.getloadavg()[0]))
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
    _p('fgv5.py sha256 at the end %s' % _sha(os.path.join(W, 'fgv5.py'))[:16])
    return 0 if all(res.values()) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
