"""calib_tests_danny.py: tests of calib_danny.py (CALIB_SPEC.md, strategy "danny"; the grid is
section 14 of SPEC_danny.md with the orchestrator's decisions: varRollback True and the scale-free
sizing on every row, one trailing pair per cell, column floor_ok).

Usage: python3 -I calib_tests_danny.py [name filter ...] [--cells XAU:240,BTC:240] [--files-only]

  test_1_grid             the grid is the full product of section 14 (17,496 = 27 x 6 x 108; XAU 5:
                          17,497), keys unique, DIMS / SIGNALS / EXITS consistent, on all 14 cells;
                          every setting maps to the danny params the spec means (an independent
                          mapping written here, the Pine's own input defaults read from the .pine
                          file); the trailing pair of every cell = the table, and the table's floor
                          recomputed here from the bar files; the dimensions listed once (None)
                          cannot change a result, P1 (filter off: inv True = the Original signal
                          direction); the files hold the grid in order; the file metadata names the
                          danny.py / fgf.py the process imported (sceptic)
  test_2_default_rows     the default row with --script-sizing equals the saved default result of
                          the module with the same path and cost: out/inv_danny_<PAIR>_<TF>.json
                          runs normal/on/mag/ours and inverted/on/mag/ours through the command line
                          on BTC 60 and XAU 240 (plus filter off, the "as written" runs through
                          --var-rollback false, tv / script costs, the Original signal direction),
                          and every saved run of all 14 cells through calib_danny.one; the
                          scale-free default rows of the sweep against danny.run called directly
  test_3_one_rows         30 random rows per cell recomputed one at a time through
                          `calib_danny.py --one` (a new process each) equal the sweep rows (and echo
                          the row number); the same rows through danny.run with this file's own
                          mapping; --path / --cost; --var-rollback false; --script-sizing; bad input
  test_4_workers          XAU 240: 1 worker vs 3 workers identical (frames and file bytes);
                          danny.prepare runs once per signal setting, the filter once per cell
  test_5_timing_btc1      BTC 1: the real preparation and one pass (648 settings of one signal
                          input, 3 workers) extrapolated to the full grid: under 45 minutes; and the
                          memory the parent and its 3 workers hold together during the passes
                          (sum of PSS, sampled): well under the machine's 15 GB
  test_6_row_consistency  what every row must satisfy whatever the data (counts add up, a switch
                          that is off leaves no trace), and every dimension changes results; the
                          grid's own repeats (sceptic): the 1,944 rows with deadBarsIn 30 behind
                          timeStopBars 25 equal their twin with the dead exit off (also in test 8)
  test_7_all_rows         EVERY row of the cells' files (not a sample) recomputed in this process:
                          danny.prepare once per signal setting, danny.simulate + danny.summary per
                          row, with this file's own mapping; all summary values equal
  test_8_every_cell       every cell that has a file in out/: the file holds the grid in order,
                          and 4 random rows of EVERY signal setting (216 rows per cell) recomputed
                          in this process equal the file

The cells of tests 3, 6 and 7 (and the files of test 1) are --cells (default XAU 240 and BTC 240):
the file out/calib_danny_<PAIR>_<TF>.parquet when it exists, else the cell is run here with 3
workers into calib_tmp_danny/w3/ (never into out/). Test 2 covers all 14 cells: the file when it
exists, else only the two default signal settings are run in memory (648 rows; --files-only skips
those). At most 2 processes at a time, except the sweep's own 3 workers.
Prints PASS / FAIL per test; exit code 1 on a failure.
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
import danny  # noqa: E402
import calib_danny as C  # noqa: E402

OUT = os.path.join(W, 'out')
TMP = os.path.join(W, 'calib_tmp_danny')
PINE = '/home/user/master/DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine'
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
INIT = 2000.0
CELLS = [('XAU', '240'), ('BTC', '240')]
FILES_ONLY = False
N_GRID = 17496
MEM_LIMIT_MB = 6000        # test 5: parent + 3 workers on BTC 1, "well under" the machine's 15 GB
SUM_REQUIRED = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
                'exit_sl', 'exit_tp', 'exit_trail', 'exit_be', 'exit_reverse', 'exit_dead', 'exit_time',
                'exit_blackout', 'exit_end', 'zero_qty', 'reentry_same_bar', 'inherited', 'net_r', 'slippage_paid')


def _p(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# this file's own reading of the spec (independent of calib_danny's lists and mappings)
# ---------------------------------------------------------------------------------------------
V10 = "Inverted (V10 design)"
ORIG = "Original (un-inverted)"
SPEC_DIMS = ['presetMode', 'manualZoneLength', 'manualDeltaThreshold', 'manualUseEmaFilter', 'manualEmaLength',
             'fgfOn', 'signalDirection', 'inv', 'slAtrMultS2', 'tpRS2', 'timeStopBars', 'useDeadExit', 'deadBarsIn',
             'useTrailS2']
SPEC_KIND = {'presetMode': 'categorical', 'manualZoneLength': 'ordinal', 'manualDeltaThreshold': 'ordinal',
             'manualUseEmaFilter': 'categorical', 'manualEmaLength': 'ordinal', 'fgfOn': 'categorical',
             'signalDirection': 'categorical', 'inv': 'categorical', 'slAtrMultS2': 'ordinal', 'tpRS2': 'categorical',
             'timeStopBars': 'ordinal', 'useDeadExit': 'categorical', 'deadBarsIn': 'ordinal',
             'useTrailS2': 'categorical'}
SPEC_SIDE = dict(zip(SPEC_DIMS, ['signal'] * 6 + ['exit'] * 8))
SPEC_DEFAULT = dict(zip(SPEC_DIMS, ('Auto', 50, 1.5, True, 100, True, V10, False, 1.2, 4.1667, 50, True, 15, False)))
SPEC_UNUSED = {'manualEmaLength': {'manualUseEmaFilter': False}, 'signalDirection': {'fgfOn': False},
               'deadBarsIn': {'useDeadExit': False}}
# section 14: (trailActAtr, trailDstAtr) per cell; the 10th percentile of ATR(14) / close in %, as printed there
T_TRAIL = {('BTC', '1'): (13.0, 6.5), ('BTC', '5'): (3.5, 1.75), ('XAU', '1'): (10.0, 5.0), ('XAU', '5'): (3.5, 1.75)}
T_P10 = {('BTC', '1'): 0.0157, ('BTC', '5'): 0.0574, ('BTC', '15'): 0.125, ('BTC', '30'): 0.198, ('BTC', '60'): 0.318,
         ('BTC', '120'): 0.512, ('BTC', '240'): 0.826, ('XAU', '1'): 0.0101, ('XAU', '5'): 0.0290,
         ('XAU', '15'): 0.060, ('XAU', '30'): 0.094, ('XAU', '60'): 0.145, ('XAU', '120'): 0.203, ('XAU', '240'): 0.311}
T_LADDER = (1.0, 1.75, 2.5, 3.5, 5.0, 6.5)
T_FLOOR = {'BTC': 0.1, 'XAU': 0.05}
# the Pine's input defaults (DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine; SPEC_danny.md section 3) and the
# replica controls
SCRIPT_DEFAULTS = dict(
    fgfOn=True, start=None, end=None, path='tv', cost='tv', varRollback=True,
    presetMode="Auto", signalDirection=V10, v2Source="Auto Optimized Profile", lockAutoProfile=True,
    useV106GrowthSlTp=True, useV1021NasAdaptiveDead=True, nasAdaptiveRunupAtr=2.0,
    limitOneDecisionPerBar=True, limitOneFlatExitPerBar=True,
    useDeadExit=True, deadBarsIn=15, useBreakeven=False, beTriggerAtr=1.0,
    useEntryBuffer=True, entryBufferIn=60, useSundayBlock=True, useEntryWindow=False, entryWindowIn="0800-1200",
    useOnePerZone=True, useCooldown=True, cooldownIn=10,
    manualZoneLength=50, manualDeltaThreshold=1.5, manualMinRetestBars=1, manualMaxZoneAge=200, manualInvalidate=True,
    manualUseEmaFilter=True, manualEmaLength=100, manualZoneTrend=False, manualEntryMode="Normal Retest Touch",
    ExitMode="ATR", slPointsIn=5000.0, tpPointsIn=50000.0, atrLenS2=14, slAtrMultS2=1.2, tpRS2=4.1667,
    useTrailS2=False, trailActPts=1000.0, trailPts=100.0, trailActAtr=4.0, trailDstAtr=0.2, timeStopBars=50,
    QtyMode="Risk %", fixedQtyS3=10.0, riskPctS3=1.0, maxQtyS3=50.0, qtyStepS3=0.001, capMarginS3=True,
    marginPctS3=1.0, useSessionFilter=False, nySession="0930-1600",
    useRobustHourFilter=True, useDirectionalMicroFilter=True, useV105DirectionalFilter=True, useV1010PfFilter=True,
    useV1011LossClusterPause=True, manualLossClusterCount=5, manualLossClusterPauseBars=12,
    useV1013VolCostFilter=True, minStopToCostRatio=4.0, modeledSlippageTicksOverride=0,
    useWeekendBlackout=True, useDailyBlackout=True, closeLeadMin=10, dpInv=False)
REPLICA_CONTROLS = {'start', 'end', 'path', 'cost', 'varRollback'}


def spec_grid(pair, tf):
    """SPEC_danny.md section 14: signals 3 x 3 x (EMA on/100, on/200, off); filter off: inv F / T, filter
    on: signalDirection x inv; exits 3 x 2 x 3 x (dead on/15, on/30, off) x trail off / on. XAU "5": the
    grid with presetMode Manual plus one row, the script default (Auto)."""
    mode = 'Manual' if (pair, tf) == ('XAU', '5') else 'Auto'
    G = []
    for zl in (50, 100, 200):
        for dt in (1.0, 1.5, 2.0):
            for ue, el in ((True, 100), (True, 200), (False, None)):
                for fgf in (False, True):
                    for sd in ((V10, ORIG) if fgf else (None,)):
                        for inv in (False, True):
                            for sl in (0.8, 1.2, 2.0):
                                for tp in (4.1667, 0.0):
                                    for ts in (25, 50, 100):
                                        for de, db in ((True, 15), (True, 30), (False, None)):
                                            for tr in (False, True):
                                                G.append((mode, zl, dt, ue, el, fgf, sd, inv, sl, tp, ts, de, db, tr))
    if (pair, tf) == ('XAU', '5'):
        G.append(('Auto', 50, 1.5, True, 100, True, V10, False, 1.2, 4.1667, 50, True, 15, False))
    return G


def danny_params(p, pair, tf, path='mag', cost='ours', var_rollback=True, script_sizing=False):
    """A setting (dict over SPEC_DIMS) as the complete danny param set, written from the spec and the
    orchestrator's decisions: varRollback True and qtyStepS3 0.000001 / maxQtyS3 1e9 on every row."""
    q = dict(SCRIPT_DEFAULTS)
    q.update(presetMode=p['presetMode'], manualZoneLength=p['manualZoneLength'],
             manualDeltaThreshold=p['manualDeltaThreshold'], manualUseEmaFilter=p['manualUseEmaFilter'],
             fgfOn=p['fgfOn'], dpInv=p['inv'], slAtrMultS2=p['slAtrMultS2'], tpRS2=p['tpRS2'],
             timeStopBars=p['timeStopBars'], useDeadExit=p['useDeadExit'], useTrailS2=p['useTrailS2'],
             path=path, cost=cost, varRollback=var_rollback)
    if p['manualUseEmaFilter']:
        q['manualEmaLength'] = p['manualEmaLength']
    if p['signalDirection'] is not None:
        q['signalDirection'] = p['signalDirection']
    if p['useDeadExit']:
        q['deadBarsIn'] = p['deadBarsIn']
    if p['useTrailS2']:
        q['trailActAtr'], q['trailDstAtr'] = T_TRAIL.get((pair, tf), (2.0, 1.0))
    if not script_sizing:
        q['qtyStepS3'] = 0.000001
        q['maxQtyS3'] = 1e9
    return q


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
    """Exact equality; NaN equals NaN; None equals None."""
    if a is None or b is None:
        return a is None and b is None
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
    """Every column that is not a p_ column: floor_ok and the summary fields."""
    return [c for c in df.columns if not c.startswith('p_')]


def _sumcols(df):
    return [c for c in df.columns if not c.startswith('p_') and c != 'floor_ok']


def _out_file(pair, tf):
    return os.path.join(OUT, 'calib_danny_%s_%s.parquet' % (pair, tf))


def _fresh(path):
    """A scratch file is used only when it is newer than the runner and the replica."""
    return os.path.exists(path) and os.path.getmtime(path) > max(os.path.getmtime(os.path.join(W, 'calib_danny.py')),
                                                                 os.path.getmtime(os.path.join(W, 'danny.py')))


_DF = {}


def _cell_df(pair, tf):
    """(DataFrame, where): out/ when the cell's file exists, else calib_tmp_danny/w3 (run here if needed)."""
    key = (pair, tf)
    if key not in _DF:
        f = _out_file(pair, tf)
        if os.path.exists(f):
            src = 'out/' + os.path.basename(f)
            if not _fresh(f):
                _p('  note: %s is older than calib_danny.py or danny.py' % src)
        else:
            d3 = os.path.join(TMP, 'w3')
            f = os.path.join(d3, 'calib_danny_%s_%s.parquet' % (pair, tf))
            src = 'calib_tmp_danny/w3/' + os.path.basename(f)
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
    return [i for i, s in enumerate(C.SIGNALS)
            if (s['manualZoneLength'], s['manualDeltaThreshold'], s['manualUseEmaFilter'], s['manualEmaLength'])
            == (50, 1.5, True, 100)]


def _split(q):
    """danny params -> (prepare params, simulate params)."""
    prep = {k: v for k, v in q.items() if k in danny._PREP_KEYS}
    return prep, {k: v for k, v in q.items() if k not in danny._PREP_KEYS}


def _run_summary(pair, tf, q):
    """danny.run (prepare + simulate + summary in one call of the module) as the row's names."""
    _, s = danny.run(pair, tf, q)
    return {k: v for k, v in s.items() if k not in ('pair', 'tf', 'w0', 'w1')}


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


def _swap_raw(s):
    """The summary with the two signal-side counters exchanged (P1: the same trades from the mirrored signal)."""
    out = dict(s)
    out['raw_long'], out['raw_short'] = s['raw_short'], s['raw_long']
    out['blocked_long'], out['blocked_short'] = s['blocked_short'], s['blocked_long']
    return out


def _late_dead(df, keys):
    """Rows whose dead-trade exit can never act: deadBarsIn is later than timeStopBars, and the time stop
    closes every trade first (danny kernel B7: bars in the trade >= timeStopBars forces the close). Such a
    row must equal, on every result column, its twin with the dead exit off (useDeadExit False, deadBarsIn
    None): it repeats another row of the grid. Returns (rows, rows equal to the twin, rows without a twin)."""
    j_on, j_db, j_ts = SPEC_DIMS.index('useDeadExit'), SPEC_DIMS.index('deadBarsIn'), SPEC_DIMS.index('timeStopBars')
    assert j_db == j_on + 1
    pos = {k: i for i, k in enumerate(keys)}
    rc = _rescols(df)
    v = df[rc].to_numpy(dtype=float)
    n = n_eq = n_miss = 0
    for i, k in enumerate(keys):
        if k[j_on] is True and k[j_db] is not None and k[j_db] > k[j_ts]:
            n += 1
            j = pos.get(k[:j_on] + (False, None) + k[j_db + 1:])
            if j is None:
                n_miss += 1
            elif np.array_equal(v[i], v[j], equal_nan=True):
                n_eq += 1
    return n, n_eq, n_miss


def _own_p10(pair, tf):
    """The 10th percentile over the window of ATR(14) / close in %, computed here from the bar file with
    pandas (Wilder's average as an exponential mean of the true range; the window starts thousands of
    bars into the file, so its seed no longer matters)."""
    t = pq.read_table(os.path.join(W, 'data', '%s_%s.parquet' % (pair, tf)), columns=['high', 'low', 'close', 't_close'])
    h, l, c, tc = (t.column(k).to_numpy() for k in ('high', 'low', 'close', 't_close'))
    pc = np.concatenate(([np.nan], c[:-1]))
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1.0 / 14.0, adjust=False).mean().to_numpy()
    s0, e0 = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}[pair]
    m = (tc >= s0) & (tc <= e0)
    w0 = int(np.argmax(m))
    return float(np.percentile(atr[m] / c[m] * 100.0, 10)), w0, int(m.sum())


# ---------------------------------------------------------------------------------------------
# 1. the grid
# ---------------------------------------------------------------------------------------------
def test_1_grid():
    """(1) The grid is the full product of section 14, keys unique, on all 14 cells; DIMS, SIGNALS, EXITS and
    the danny params of every setting are what the spec says; the trailing table and its floor; the
    dimensions listed once cannot change a result; the files hold the grid."""
    ok = True
    # ---- the product, cell by cell
    sizes = {}
    all_ok = True
    for pair in PAIRS:
        for tf in TFS:
            S = spec_grid(pair, tf)
            G = C.grid(pair, tf)
            K = [C.key(p) for p in G]
            n = N_GRID + (1 if (pair, tf) == ('XAU', '5') else 0)
            c_ok = (len(S) == n == len(set(S)) and len(G) == n == len(set(K)) and K == S and C.n_settings(pair, tf) == n
                    and G == [C.merge(s, x) for s in C.signals(pair, tf) for x in C.exits_for(s, pair, tf)])
            sizes[(pair, tf)] = len(G)
            all_ok &= c_ok
            if not c_ok:
                _p('  %s %s: spec %d, runner %d, unique %d, same order %s' % (pair, tf, len(S), len(G), len(set(K)), K == S))
    a = N_GRID == 27 * 6 * 108 == 27 * (2 * 108 + 4 * 108) == C.N_GRID
    _p('  spec product 17,496 = 27 signal inputs x (filter off: 2 directions + filter on: 2 x 2) x 108 exits; the '
       'runner\'s grid of each of the 14 cells = the spec\'s, same order, keys unique: %s (rows: %s; XAU 5 = the grid '
       'with presetMode Manual + 1 row, the script default)' % (all_ok and a, sorted(set(sizes.values()))))
    ok &= all_ok and a
    # ---- the two lists
    G = C.grid('BTC', '240')
    K = [C.key(p) for p in G]
    sk = [tuple(s[k] for k in C.SIGNAL_DIMS) for s in C.SIGNALS]
    xk = [tuple(x[k] for k in C.EXIT_DIMS) for x in C.EXITS]
    n_off = [len(C.exits_for(s, 'BTC', '240')) for s in C.SIGNALS if not s['fgfOn']]
    n_on = [len(C.exits_for(s, 'BTC', '240')) for s in C.SIGNALS if s['fgfOn']]
    s5 = C.signals('XAU', '5')
    c = (len(sk) == 54 == len(set(sk)) and len(xk) == 648 == len(set(xk)) and set(n_off) == {216} and set(n_on) == {432}
         and len(n_off) == 27 == len(n_on) and list(C.SIGNAL_DIMS) + list(C.EXIT_DIMS) == C.DIM_NAMES
         and C.signals('BTC', '240') == C.SIGNALS and all(s['presetMode'] == 'Auto' for s in C.SIGNALS)
         and len(s5) == 55 and all(s['presetMode'] == 'Manual' for s in s5[:54]) and s5[54]['presetMode'] == 'Auto'
         and [dict(s, presetMode='Auto') for s in s5[:54]] == C.SIGNALS
         and len(C.exits_for(s5[54], 'XAU', '5')) == 1 and C.grid('XAU', '5')[-1] == C.DEFAULT_P)
    _p('  SIGNALS %d unique (prepare params), EXITS %d unique (simulate params); exit settings per signal setting: '
       '%d with the filter off, %d with it on; XAU 5: 54 signal settings with Manual + the default (Auto) with 1 exit '
       'setting, the last row: %s' % (len(set(sk)), len(set(xk)), n_off[0], n_on[0], c))
    ok &= c
    # ---- DIMS
    d_ok = [d['name'] for d in C.DIMS] == SPEC_DIMS and len(C.DIMS) == 14 and all(
        {'name', 'values', 'kind'} <= set(d) <= {'name', 'values', 'kind', 'side', 'default', 'unused_when'}
        and d['default'] == SPEC_DEFAULT[d['name']] and type(d['default']) is type(SPEC_DEFAULT[d['name']])
        and d['side'] == SPEC_SIDE[d['name']] and d.get('unused_when') == SPEC_UNUSED.get(d['name'])
        and d['kind'] == SPEC_KIND[d['name']] for d in C.DIMS)
    d_ok &= C.DEFAULT_P == SPEC_DEFAULT and C.DEFAULT is C.DEFAULT_P
    S_all = [k for pair in PAIRS for tf in TFS for k in spec_grid(pair, tf)]
    for j, d in enumerate(C.DIMS):
        seen = set(k[j] for k in S_all if k[j] is not None)
        d_ok &= set(d['values']) == seen and len(d['values']) == len(seen)
        d_ok &= all(type(v) in (bool, int, float, str) for v in d['values'])
        if d['kind'] == 'ordinal':
            d_ok &= list(d['values']) == sorted(d['values'])
    none_ok = all((k[4] is None) == (k[3] is False) and (k[6] is None) == (k[5] is False)
                  and (k[12] is None) == (k[11] is False)
                  and all(k[j] is not None for j in range(14) if j not in (4, 6, 12)) for k in S_all)
    dir_ok = [d['name'] for d in C.DIMS if d['name'] in ('inv', 'signalDirection')] == ['signalDirection', 'inv'] \
        and C.DIMS[7]['kind'] == 'categorical' and C.DIMS[7]['values'] == [False, True]
    _p('  DIMS: %d dimensions %s; values = the values of the 14 grids, kinds / sides / defaults as specified: %s; None '
       'only for manualEmaLength with the EMA filter off, signalDirection with the filter off, deadBarsIn with the '
       'dead exit off, and always there: %s; the direction dimension is named inv, signalDirection is a categorical '
       'dimension of its own: %s' % (len(C.DIMS), [d['name'] for d in C.DIMS], d_ok, none_ok, dir_ok))
    ok &= d_ok and none_ok and dir_ok
    try:
        json.dumps(C.DIMS)
    except Exception as e:      # noqa: BLE001
        ok = False
        _p('  DIMS is not JSON: %r' % (e,))
    # ---- the script defaults: this file's copy, the module's, the Pine's own input lines
    m_ok = danny.DEFAULTS == SCRIPT_DEFAULTS
    if not m_ok:
        _p('  danny.DEFAULTS differ from the script defaults written here: %r'
           % {k: (danny.DEFAULTS.get(k), SCRIPT_DEFAULTS.get(k)) for k in set(danny.DEFAULTS) | set(SCRIPT_DEFAULTS)
              if danny.DEFAULTS.get(k) != SCRIPT_DEFAULTS.get(k)})
    pin = pine_inputs()
    found = [k for k in SCRIPT_DEFAULTS if k in pin]
    diff = {k: (SCRIPT_DEFAULTS[k], pin[k][0]) for k in found
            if not (SCRIPT_DEFAULTS[k] == pin[k][0] and isinstance(SCRIPT_DEFAULTS[k], bool) == isinstance(pin[k][0], bool))}
    missing = sorted(set(SCRIPT_DEFAULTS) - set(found) - REPLICA_CONTROLS)
    pine_dims = {'inv' if k == 'dpInv' else k: pin[k][0] for k in
                 [('dpInv' if n == 'inv' else n) for n in SPEC_DIMS] if k in pin}
    p_ok = (not diff and not missing and pine_dims == SPEC_DEFAULT
            and pin['qtyStepS3'] == (0.001, 0.000001) and pin['maxQtyS3'][0] == 50.0 and pin['riskPctS3'][0] == 1.0
            and C.SCALE_FREE == {'qtyStepS3': 0.000001, 'maxQtyS3': 1e9}
            and C.SCRIPT_SIZING == {'qtyStepS3': 0.001, 'maxQtyS3': 50.0}
            and C.SCALE_FREE['qtyStepS3'] >= pin['qtyStepS3'][1] and C.VAR_ROLLBACK is True)
    _p('  script defaults: danny.DEFAULTS = the %d written here: %s; the Pine file\'s own input lines give the same '
       'default for %d of them (different: %s; not found: %s); the 14 dimensions\' Pine defaults = DEFAULT_P: %s; the '
       'Pine\'s quantity step 0.001 (minval 0.000001 = the grid\'s step) and max quantity 50: %s'
       % (len(SCRIPT_DEFAULTS), m_ok, len(found), diff or 'none', missing or 'none', pine_dims == SPEC_DEFAULT, p_ok))
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
    # ---- the danny params of every setting, all 14 cells
    n_bad = n_all = 0
    def_ok = True
    for pair in PAIRS:
        for tf in TFS:
            Gc = C.grid(pair, tf)
            for p in Gc:
                sig = {k: p[k] for k in C.SIGNAL_DIMS}
                ex = {k: p[k] for k in C.EXIT_DIMS}
                sp = C.signal_params(sig)
                xp = C.exit_params(ex, pair, tf)
                eff, fgfp = danny._params({**sp, **xp})
                want = danny_params(p, pair, tf)
                n_all += 1
                if eff != want or fgfp != {'fgfOn': p['fgfOn']} or (set(sp) - danny._PREP_KEYS) \
                        or (set(danny._ALIASES.get(k, k) for k in xp) & danny._PREP_KEYS):
                    n_bad += 1
                    if n_bad <= 3:
                        _p('  MAPPING %s %s %r: %r' % (pair, tf, p, {k: (eff.get(k), want.get(k)) for k in want
                                                                      if eff.get(k) != want.get(k)}))
            dp = dict(SPEC_DEFAULT, presetMode=Gc[0]['presetMode'])
            eff_d, _ = danny._params({**C.signal_params({k: dp[k] for k in C.SIGNAL_DIMS}),
                                      **C.exit_params({k: dp[k] for k in C.EXIT_DIMS}, pair, tf)})
            def_ok &= ([C.key(q) for q in Gc].count(C.key(SPEC_DEFAULT)) == 1
                       and eff_d == dict(SCRIPT_DEFAULTS, path='mag', cost='ours', qtyStepS3=0.000001, maxQtyS3=1e9,
                                         presetMode=dp['presetMode']))
    def_ok &= C.PATH == 'mag' and C.COST == 'ours'
    _p('  danny params of all %d settings of the 14 cells (signal_params + exit_params, resolved by danny._params) = '
       'the mapping written here (%d keys each; varRollback True, qtyStepS3 0.000001, maxQtyS3 1e9, the cell\'s '
       'trailing pair): %d different; signal params only prepare keys, exit params only simulate keys'
       % (n_all, len(SCRIPT_DEFAULTS), n_bad))
    _p('  the script\'s default setting is one row of every cell; its params = the script defaults with path mag, cost '
       'ours and the scale-free sizing (XAU 5: also the Manual twin of it): %s' % def_ok)
    ok &= n_bad == 0 and def_ok
    # ---- Auto and Manual cannot differ outside XAU 5
    pm = []
    for pair in PAIRS:
        for tf in TFS:
            qa = danny._params({'presetMode': 'Auto'})[0]
            qm = danny._params({'presetMode': 'Manual'})[0]
            pm.append(((pair, tf), danny.resolve_preset(pair, tf, qa) == danny.resolve_preset(pair, tf, qm)))
    pm_ok = all(same == (cell != ('XAU', '5')) for cell, same in pm)
    _p('  presetMode Auto and Manual resolve to the same active settings on 13 cells and differ on XAU 5 only: %s' % pm_ok)
    ok &= pm_ok
    # ---- normalize: every grid row round-trips, as the file gives it (p_ prefix, NaN or None for unused)
    n_rt = sum(C.normalize({'p_' + k: (float('nan') if v is None else v) for k, v in p.items()}) == p
               and C.normalize({k: v for k, v in p.items() if v is not None}) == p for p in G)
    forced = C.normalize(dict(SPEC_DEFAULT, fgfOn=False, signalDirection=V10, manualUseEmaFilter=False,
                              manualEmaLength=200, useDeadExit=False, deadBarsIn=30))
    refused = False
    try:
        C.normalize(dict(SPEC_DEFAULT, fgfOn=False, signalDirection=ORIG))
    except ValueError:
        refused = True
    kept = C.normalize(dict(SPEC_DEFAULT, fgfOn=False, signalDirection=ORIG), off_grid=True)
    r_ok = (n_rt == len(G) and forced['signalDirection'] is None and forced['manualEmaLength'] is None
            and forced['deadBarsIn'] is None and refused and kept['signalDirection'] == ORIG
            and C.row_of('BTC', '240', kept) is None and C.row_of('BTC', '240', SPEC_DEFAULT) == K.index(C.key(SPEC_DEFAULT))
            and C.row_of('XAU', '5', SPEC_DEFAULT) == N_GRID and C.row_of('BTC', '240', dict(SPEC_DEFAULT, presetMode='Manual')) is None)
    _p('  normalize(): %d of %d grid rows round-trip (p_ prefix, NaN / missing for unused); a value given for an '
       'unused dimension is dropped; signalDirection Original with the filter off is refused (it is another run) '
       'unless --off-grid: %s' % (n_rt, len(G), r_ok))
    ok &= r_ok
    # ---- on data: the dimensions listed once cannot change a result; P1; the inert switches
    rng = np.random.default_rng(20261126)
    cnt = dict(ema=0, dead=0, trail=0, p1=0, p1_on=0, preset=0, inert=0)
    dif = dict(ema=0, dead=0, trail=0, p1=0, p1_on=0, preset=0, inert=0)
    for pair, tf in CELLS:
        sub = None
        for b in rng.choice(9, size=3, replace=False):
            base = 6 * int(b)                                   # the 6 signal settings of one (zone length, delta)
            sig_e = C.SIGNALS[base + 4]                         # EMA filter off, filter off
            sig_f = C.SIGNALS[base + 5]                         # EMA filter off, filter on
            assert not sig_e['manualUseEmaFilter'] and not sig_e['fgfOn'] and sig_f['fgfOn']
            P0 = danny.prepare(pair, tf, C.signal_params(sig_e))
            P1 = danny.prepare(pair, tf, C.signal_params(sig_f))
            Pa = danny.prepare(pair, tf, dict(C.signal_params(sig_e), manualEmaLength=200))
            Pb = danny.prepare(pair, tf, dict(C.signal_params(sig_e), manualEmaLength=37))
            Pm = danny.prepare(pair, tf, dict(C.signal_params(sig_f), presetMode='Manual'))
            sub = sub or danny.get_sub(P0)
            for Pk in (P0, P1, Pa, Pb, Pm):
                Pk['sub'] = sub
            X0 = C.exits_for(sig_e, pair, tf)
            X1 = C.exits_for(sig_f, pair, tf)
            for i in rng.choice(len(X0), size=8, replace=False):
                x = X0[int(i)]
                xp = C.exit_params(x, pair, tf)
                s0 = danny.summary(P0, danny.simulate(P0, xp))
                # manualEmaLength with the EMA filter off
                sa = danny.summary(Pa, danny.simulate(Pa, xp))
                sb = danny.summary(Pb, danny.simulate(Pb, xp))
                cnt['ema'] += 1
                dif['ema'] += not all(_same(s0[k], sa[k]) and _same(s0[k], sb[k]) for k in s0)
                # P1: filter off, Original direction with inv flipped = this row, the signal-side counters exchanged
                so = danny.summary(P0, danny.simulate(P0, dict(xp, signalDirection=ORIG, dpInv=not x['inv'])))
                cnt['p1'] += 1
                dif['p1'] += not all(_same(_swap_raw(s0)[k], so[k]) for k in s0)
                # useOnePerZone / useCooldown / cooldownIn under varRollback True (no quantity floored to zero)
                si = danny.summary(P0, danny.simulate(P0, dict(xp, useOnePerZone=False, useCooldown=False, cooldownIn=3)))
                cnt['inert'] += 1
                dif['inert'] += not (all(_same(s0[k], si[k]) for k in s0) and s0['zero_qty'] == 0)
            for i in rng.choice(len(X1), size=8, replace=False):
                x = X1[int(i)]
                xp = C.exit_params(x, pair, tf)
                s1 = danny.summary(P1, danny.simulate(P1, xp))
                # presetMode Manual on a cell without a preset
                sm = danny.summary(Pm, danny.simulate(Pm, xp))
                cnt['preset'] += 1
                dif['preset'] += not all(_same(s1[k], sm[k]) for k in s1)
                # with the filter ON the Original direction with inv flipped is another run
                so = danny.summary(P1, danny.simulate(P1, dict(xp, signalDirection=ORIG if x['signalDirection'] == V10 else V10,
                                                               dpInv=not x['inv'])))
                cnt['p1_on'] += 1
                dif['p1_on'] += not all(_same(_swap_raw(s1)[k], so[k]) for k in s1)
            offs = [i for i, x in enumerate(X1) if not x['useDeadExit']]
            for i in rng.choice(offs, size=6, replace=False):
                xp = C.exit_params(X1[int(i)], pair, tf)
                s0 = danny.summary(P1, danny.simulate(P1, xp))
                sa = danny.summary(P1, danny.simulate(P1, dict(xp, deadBarsIn=30)))
                sb = danny.summary(P1, danny.simulate(P1, dict(xp, deadBarsIn=7)))
                cnt['dead'] += 1
                dif['dead'] += not all(_same(s0[k], sa[k]) and _same(s0[k], sb[k]) for k in s0)
            offs = [i for i, x in enumerate(X1) if not x['useTrailS2']]
            for i in rng.choice(offs, size=6, replace=False):
                xp = C.exit_params(X1[int(i)], pair, tf)
                s0 = danny.summary(P1, danny.simulate(P1, xp))
                sa = danny.summary(P1, danny.simulate(P1, dict(xp, trailActAtr=2.0, trailDstAtr=1.0)))
                sb = danny.summary(P1, danny.simulate(P1, dict(xp, trailActAtr=0.5, trailDstAtr=0.05)))
                cnt['trail'] += 1
                dif['trail'] += not all(_same(s0[k], sa[k]) and _same(s0[k], sb[k]) for k in s0)
        _free()
    u_ok = (dif['ema'] == dif['dead'] == dif['trail'] == dif['p1'] == dif['preset'] == dif['inert'] == 0
            and dif['p1_on'] > 0)
    _p('  on data (%s): settings with a different result / settings tried: other manualEmaLength with the EMA '
       'filter off %d/%d; other deadBarsIn with the dead exit off %d/%d; other trailing distances with the trailing '
       'off %d/%d; presetMode Manual instead of Auto %d/%d; useOnePerZone, useCooldown off and cooldownIn 3 under '
       'varRollback True %d/%d'
       % (', '.join('%s %s' % c for c in CELLS), dif['ema'], cnt['ema'], dif['dead'], cnt['dead'], dif['trail'],
          cnt['trail'], dif['preset'], cnt['preset'], dif['inert'], cnt['inert']))
    _p('  P1: filter off, signalDirection Original with inv flipped = the grid row (signalDirection None), the '
       'signal-side counters exchanged: %d/%d differ; with the filter ON the same exchange gives another run in '
       '%d/%d settings (there the two direction inputs are two dimensions): %s'
       % (dif['p1'], cnt['p1'], dif['p1_on'], cnt['p1_on'], u_ok))
    ok &= u_ok
    # ---- the files
    fd = os.path.join(OUT, 'calib_danny_dims.json')
    if os.path.exists(fd):
        same = json.load(open(fd)) == C.DIMS
        _p('  out/calib_danny_dims.json equals DIMS: %s' % same)
        ok &= same
    else:
        _p('  out/calib_danny_dims.json: not written yet')
    # ---- the provenance written into a file is the code this process imported (sceptic): file_meta must not
    # read danny.py / fgf.py again when a file is written, a module edited during a long run did not run
    o_sha = C._sha256
    C._sha256 = lambda path: 'read again at write time'
    try:
        m2 = C.file_meta('XAU', '240', N_GRID)
    finally:
        C._sha256 = o_sha
    import fgf
    prov = (m2['danny_sha256'] == C._SRC_SHA['danny'] and m2['fgf_sha256'] == C._SRC_SHA['fgf']
            and len(m2['danny_sha256']) == 64 == len(m2['fgf_sha256'])
            and os.path.samefile(danny.__file__, os.path.join(W, 'danny.py')) and os.path.samefile(fgf.__file__, os.path.join(W, 'fgf.py')))
    _p('  file metadata: the sha256 of danny.py and fgf.py is the one taken when the runner imported them, not read '
       'again when a file is written: %s' % prov)
    ok &= prov
    cols_want = None
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        if cols_want is None:
            Pp = danny.prepare(pair, tf, {})
            s = danny.summary(Pp, danny.simulate(Pp, {'path': 'mag', 'cost': 'ours'}))
            cols_want = list(s.keys())
            scalar = all(isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool) for v in s.values())
        f_ok = (len(df) == C.n_settings(pair, tf) and _keys(df) == spec_grid(pair, tf)
                and list(df.columns) == _pcols() + ['floor_ok'] + cols_want and scalar
                and all(k in cols_want for k in SUM_REQUIRED) and df['floor_ok'].dtype == bool and bool(df['floor_ok'].all()))
        nulls = {c: int(df[c].isna().sum()) for c in _rescols(df) if df[c].isna().any()}
        f_ok &= set(nulls) <= {'pf', 'win_pct', 'avg_bars_held'}
        _p('  %s: %d rows; p_ columns = the grid in order; columns = %d p_ + floor_ok (True on every row) + the %d '
           'fields of danny.summary (all scalars), nothing else: %s (NaN: %s)'
           % (src, len(df), len(_pcols()), len(cols_want), f_ok, nulls or 'none'))
        ok &= f_ok
        meta = C.read_meta(os.path.join(W, src))
        now = C.file_meta(pair, tf, C.n_settings(pair, tf))
        m_ok = meta is not None and all(meta.get(k) == now[k] for k in (
            'strategy', 'pair', 'tf', 'path', 'cost', 'settings', 'window', 'varRollback', 'qtyStepS3', 'maxQtyS3',
            'grid_presetMode', 'trailActAtr', 'trailDstAtr')) and bool((meta.get('floor') or {}).get('floor_ok'))
        cur = meta is not None and meta.get('danny_sha256') == now['danny_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
        _p('    file metadata: %s, path %s, cost %s, %s settings, varRollback %s, qtyStepS3 %s, maxQtyS3 %s, trailing '
           '(%s, %s): %s; written with the danny.py and fgf.py now on disk: %s'
           % ((meta or {}).get('strategy'), (meta or {}).get('path'), (meta or {}).get('cost'),
              (meta or {}).get('settings'), (meta or {}).get('varRollback'), (meta or {}).get('qtyStepS3'),
              (meta or {}).get('maxQtyS3'), (meta or {}).get('trailActAtr'), (meta or {}).get('trailDstAtr'), m_ok,
              cur if cur else 'NO (rows are still checked against the module by tests 2, 3 and 7)'))
        ok &= m_ok
    _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 2. the default rows against the saved results
# ---------------------------------------------------------------------------------------------
def _one(pair, tf, p, *extra):
    cmd = [sys.executable, '-I', os.path.join(W, 'calib_danny.py'), '--one', pair, tf, json.dumps(p)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _json_ref(sv, cols):
    """A saved run of out/inv_danny_*.json as python values (its writer stores NaN as null, inf as 'inf')."""
    ref = {}
    for k in cols:
        v = sv[k]
        ref[k] = float('nan') if v is None else (float(v) if isinstance(v, str) else v)
    return ref


def test_2_default_rows():
    """(2) The default row with --script-sizing equals the saved default results of the module with the same
    path and cost (out/inv_danny_<PAIR>_<TF>.json): through the command line on BTC 60 and XAU 240, through
    calib_danny.one on every saved run of all 14 cells; and the scale-free default rows of the sweep equal
    danny.run called directly."""
    ok = True
    Pp = danny.prepare('XAU', '240', {})
    sc = list(danny.summary(Pp, danny.simulate(Pp, {})).keys())
    dp = dict(SPEC_DEFAULT)
    # ---- (a) the command line, BTC 60 and XAU 240
    for pair, tf in (('BTC', '60'), ('XAU', '240')):
        J = json.load(open(os.path.join(OUT, 'inv_danny_%s_%s.json' % (pair, tf))))
        cases = (
            ('runs', 'normal/on/mag/ours', dp, ('--script-sizing',)),
            ('runs', 'inverted/on/mag/ours', dict(dp, inv=True), ('--script-sizing',)),
            ('runs', 'normal/off/mag/ours', dict(dp, fgfOn=False, signalDirection=None), ('--script-sizing',)),
            ('runs', 'inverted/off/mag/ours', dict(dp, fgfOn=False, signalDirection=None, inv=True), ('--script-sizing',)),
            ('runs_aw', 'normal/on/mag/ours', dp, ('--script-sizing', '--var-rollback', 'false')),
            ('runs_aw', 'inverted/on/mag/ours', dict(dp, inv=True), ('--script-sizing', '--var-rollback', 'false')),
            ('runs', 'normal/on/tv/script', dp, ('--script-sizing', '--path', 'tv', '--cost', 'tv')),
            ('runs', 'inverted/on/tv/script', dict(dp, inv=True), ('--script-sizing', '--path', 'tv', '--cost', 'tv')),
            ('reference', 'original/on/mag/ours', dict(dp, signalDirection=ORIG), ('--script-sizing',)),
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
            want = (('varRollback', '--var-rollback' not in extra), ('sizing', 'script'), ('qtyStepS3', 0.001),
                    ('maxQtyS3', 50.0), ('useOnePerZone', True), ('useCooldown', True), ('cooldownIn', 10),
                    ('in_grid', True), ('path', 'tv' if '--path' in extra else 'mag'),
                    ('cost', 'tv' if '--cost' in extra else 'ours'))
            if any(st.get(k) != v for k, v in want) or list(o) != ['floor_ok'] + sc:
                bad.append('%s %s: setting echoed as %r' % (group, key, st))
            n_vals += _cmp(o, _json_ref(J[group][key], sc), sc, '%s %s' % (group, key), bad)
            first.setdefault(key, o)
        # the same default row with the grid's sizing (what the sweep stores): another number, by design
        rc, out, err = _one(pair, tf, dp)
        o = json.loads(out) if rc == 0 else None
        d = first.get('normal/on/mag/ours')
        _p('  %s %-3s command line: default row --script-sizing = saved runs normal/on/mag/ours and inverted/on/mag/ours, '
           'filter off, --var-rollback false = runs_aw, tv / script costs, Original signal direction = reference: %d '
           'runs, %d values: %s' % (pair, tf, len(cases), n_vals,
                                    'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b))))
        if o is not None and d is not None:
            _p('    default row, script sizing (the published file): %d trades, net %+.3f %%, h1r %+.3f %%, h2r %+.3f %%; '
               'scale-free sizing (the grid row %d): %d trades, net %+.3f %%, h1r %+.3f %%, h2r %+.3f %%'
               % (d['trades'], d['net_pct'], d['h1r_pct'], d['h2r_pct'], o['setting']['row'], o['trades'], o['net_pct'],
                  o['h1r_pct'], o['h2r_pct']))
        ok &= not bad and n_vals == len(cases) * len(sc) and o is not None and o['setting']['sizing'] == 'scale-free' \
            and o['setting']['qtyStepS3'] == 0.000001 and o['setting']['maxQtyS3'] == 1e9
    # ---- (b) every saved run of all 14 cells through calib_danny.one (script sizing)
    tot = dict(cells=0, runs=0, vals=0)
    for pair in PAIRS:
        for tf in TFS:
            J = json.load(open(os.path.join(OUT, 'inv_danny_%s_%s.json' % (pair, tf))))
            cache = {}
            bad = []
            n_runs = n_vals = 0
            groups = [('runs', 'runs_aw', 'reference', 'Auto')]
            if (pair, tf) == ('XAU', '5'):
                groups.append(('runs_manual', 'runs_manual_aw', 'reference_manual', 'Manual'))
            if not set(sc) <= set(J['runs']['normal/on/mag/ours']):
                bad.append('the saved runs miss fields: %s' % (set(sc) - set(J['runs']['normal/on/mag/ours'])))
            for g_runs, g_aw, g_ref, mode in groups:
                for g, rb in ((g_runs, True), (g_aw, False)):
                    for key, sv in J[g].items():
                        dname, flt, path, cname = key.split('/')
                        fgf = flt == 'on'
                        p = dict(dp, presetMode=mode, fgfOn=fgf, signalDirection=V10 if fgf else None, inv=dname == 'inverted')
                        o = C.one(pair, tf, p, path, 'tv' if cname == 'script' else 'ours', False, rb, True, cache)
                        n_vals += _cmp(o, _json_ref(sv, sc), sc, '%s %s' % (g, key), bad)
                        n_runs += 1
                for key, sv in J[g_ref].items():
                    _, flt, path, cname = key.split('/')
                    fgf = flt == 'on'
                    cost = 'tv' if cname == 'script' else 'ours'
                    p = dict(dp, presetMode=mode, fgfOn=fgf, signalDirection=ORIG)
                    o = C.one(pair, tf, p, path, cost, not fgf, True, True, cache)       # filter off: off the grid
                    n_vals += _cmp(o, _json_ref(sv, sc), sc, '%s %s' % (g_ref, key), bad)
                    n_runs += 1
                    if not fgf and not (mode == 'Auto' and (pair, tf) == ('XAU', '5')):
                        # P1: the same run is in the grid as signalDirection None with inv True
                        o2 = C.one(pair, tf, dict(dp, presetMode=mode, fgfOn=False, signalDirection=None, inv=True),
                                   path, cost, False, True, True, cache)
                        n_vals += _cmp(_swap_raw(o2), _json_ref(sv, sc), sc, '%s %s as inv True' % (g_ref, key), bad)
            d = J['runs']['normal/on/mag/ours']
            _p('  %s %-3s: %d saved runs (runs, runs_aw, reference%s) = calib_danny.one with script sizing: %d values: %s '
               '| saved default mag / ours: %d trades, net %+.3f %%'
               % (pair, tf, n_runs, ', and the three Manual groups' if len(groups) == 2 else '', n_vals,
                  'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                  d['trades'], d['net_pct']))
            ok &= not bad and n_runs == 40 * len(groups)
            tot['cells'] += 1
            tot['runs'] += n_runs
            tot['vals'] += n_vals
            del cache
            _free()
    _p('  %d cells: %d saved runs, %d values compared' % (tot['cells'], tot['runs'], tot['vals']))
    ok &= tot['cells'] == 14
    # ---- (c) the scale-free default rows of the sweep = danny.run called directly
    di = _default_sig_idx()
    n_cells = 0
    for pair in PAIRS:
        for tf in TFS:
            if os.path.exists(_out_file(pair, tf)):
                df, _ = _cell_df(pair, tf)
                src = 'file'
            elif FILES_ONLY:
                continue
            else:
                sidx = di + ([54] if (pair, tf) == ('XAU', '5') else [])      # XAU 5: and the extra (Auto) row
                df, _ = C.run_cell(pair, tf, workers=3, sig_idx=sidx, write=False, verbose=False)
                src = '%d rows run here' % len(df)
            idx = {k: i for i, k in enumerate(_keys(df))}
            mode = 'Manual' if (pair, tf) == ('XAU', '5') else 'Auto'
            base = {'path': 'mag', 'cost': 'ours', 'qtyStepS3': 0.000001, 'maxQtyS3': 1e9}
            bad = []
            n_vals = 0
            rows = {}
            for name, key, q in (
                    ('normal, filter on', (mode, 50, 1.5, True, 100, True, V10, False, 1.2, 4.1667, 50, True, 15, False), {}),
                    ('inverted, filter on', (mode, 50, 1.5, True, 100, True, V10, True, 1.2, 4.1667, 50, True, 15, False), {'dpInv': True}),
                    ('normal, filter off', (mode, 50, 1.5, True, 100, False, None, False, 1.2, 4.1667, 50, True, 15, False), {'fgfOn': False}),
                    ('inverted, filter off', (mode, 50, 1.5, True, 100, False, None, True, 1.2, 4.1667, 50, True, 15, False),
                     {'fgfOn': False, 'dpInv': True}),
                    ('Original direction, filter on', (mode, 50, 1.5, True, 100, True, ORIG, False, 1.2, 4.1667, 50, True, 15, False),
                     {'signalDirection': ORIG})):
                row = df.iloc[idx[key]]
                q = dict(base, **q)
                if mode == 'Manual':
                    q['presetMode'] = 'Manual'
                n_vals += _cmp(row, _run_summary(pair, tf, q), sc, name, bad)
                rows[name] = row
            extra = ''
            if (pair, tf) == ('XAU', '5'):
                row = df.iloc[len(df) - 1]
                n_vals += _cmp(row, _run_summary(pair, tf, base), sc, 'the Auto row', bad)
                extra = '; the extra row (Auto = the XAUUSD 5m preset), the last, = danny.run with nothing but the fixed controls: %d trades' % row['trades']
                ok &= _keys(df)[-1] == tuple(SPEC_DEFAULT.values()) and int(row['trades']) == 0 \
                    and list(_keys(df)).count(tuple(SPEC_DEFAULT.values())) == 1
            d = rows['normal, filter on']
            _p('  %s %-3s (%s): default rows (normal / inverted x filter on / off, Original direction) = danny.run with '
               'path mag, cost ours, qtyStepS3 0.000001, maxQtyS3 1e9%s: %d values: %s | default row: %d trades, net '
               '%+.3f %%, h1r %+.3f %%, h2r %+.3f %%, zero_qty %d%s'
               % (pair, tf, src, ', presetMode Manual' if mode == 'Manual' else '', n_vals,
                  'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                  d['trades'], d['net_pct'], d['h1r_pct'], d['h2r_pct'], d['zero_qty'], extra))
            ok &= not bad
            n_cells += 1
            _free()
    _p('  %d cells: the scale-free default rows equal danny.run called directly' % n_cells)
    return ok and n_cells > 0


# ---------------------------------------------------------------------------------------------
# 3. random rows through --one
# ---------------------------------------------------------------------------------------------
def test_3_one_rows():
    """(3) 30 random rows per cell recomputed one at a time through `calib_danny.py --one` (a new process each,
    the row's p_ columns as its JSON) equal the sweep rows on every result column; the same rows through
    danny.run with this file's own mapping; --path / --cost, --var-rollback false and --script-sizing are
    honoured; bad input is refused."""
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
            p = dict(zip(C.DIM_NAMES, keys[i]))
            for n, v in p.items():
                cover[n].add(v)
            rc, out, err = _one(pair, tf, {'p_' + n: v for n, v in p.items()})
            if rc != 0:
                bad.append('row %d: exit code %d %s' % (i, rc, err.strip()[-200:]))
                continue
            o = json.loads(out)
            st = o.pop('setting')
            act, dst = T_TRAIL.get((pair, tf), (2.0, 1.0)) if p['useTrailS2'] else (None, None)
            if st != {'strategy': 'danny', 'pair': pair, 'tf': tf, 'path': 'mag', 'cost': 'ours', 'p': p, 'in_grid': True,
                      'row': i, 'varRollback': True, 'sizing': 'scale-free', 'qtyStepS3': 0.000001, 'maxQtyS3': 1e9,
                      'useOnePerZone': True, 'useCooldown': True, 'cooldownIn': 10, 'trailActAtr': act,
                      'trailDstAtr': dst, 'preset': None}:
                bad.append('row %d: setting echoed as %r' % (i, st))
            if list(o) != rc_cols:
                bad.append('row %d: fields %r' % (i, list(o)))
                continue
            n_vals += _cmp(row, o, rc_cols, 'row %d --one' % i, bad)
            ref = _run_summary(pair, tf, danny_params(p, pair, tf))
            n_run += _cmp(row, ref, sc, 'row %d danny.run' % i, bad)
            n_tr += int(row['trades'])
        dt = time.time() - t0
        cov = all(len(cover[d['name']] - {None}) >= min(len(d['values']), 2 if d['name'] != 'presetMode' else 1)
                  for d in C.DIMS)
        _p('  %s %s (%s): 30 random rows, each in its own `--one` process: %d result values, and through danny.run '
           'with the mapping written here: %d values (%d trades): %s; at least two values of every dimension among '
           'them: %s (%.1fs)' % (pair, tf, src, n_vals, n_run, n_tr,
                               'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                               cov, dt))
        ok &= not bad and n_vals == 30 * len(rc_cols) and n_run == 30 * len(sc)
        # --path / --cost, and the two controls that are not dimensions
        bad = []
        n = 0
        moved = {'--var-rollback false': 0, '--script-sizing': 0}
        sub = [pick[j] for j in (0, 9, 19, 29)]
        for i in sub:
            row = df.iloc[i]
            p = dict(zip(C.DIM_NAMES, keys[i]))
            for extra, kw in (
                    (('--path', 'tv', '--cost', 'tv'), dict(path='tv', cost='tv')),
                    (('--path', 'tv', '--cost', 'stress'), dict(path='tv', cost='stress')),
                    (('--path', 'mag', '--cost', 'stress'), dict(path='mag', cost='stress')),
                    (('--var-rollback', 'false'), dict(var_rollback=False)),
                    (('--var-rollback', 'true'), dict()),
                    (('--script-sizing',), dict(script_sizing=True)),
                    (('--script-sizing', '--var-rollback', 'false', '--path', 'tv', '--cost', 'tv'),
                     dict(script_sizing=True, var_rollback=False, path='tv', cost='tv'))):
                rc, out, err = _one(pair, tf, p, *extra)
                if rc != 0:
                    bad.append('row %d %s: exit code %d' % (i, ' '.join(extra), rc))
                    continue
                o = json.loads(out)
                st = o['setting']
                if (st['path'], st['cost'], st['varRollback'], st['sizing'], st['qtyStepS3'], st['maxQtyS3'], st['row']) != (
                        kw.get('path', 'mag'), kw.get('cost', 'ours'), kw.get('var_rollback', True),
                        'script' if kw.get('script_sizing') else 'scale-free', 0.001 if kw.get('script_sizing') else 0.000001,
                        50.0 if kw.get('script_sizing') else 1e9, i) \
                        or (st['useOnePerZone'], st['useCooldown'], st['cooldownIn']) != (True, True, 10):
                    bad.append('row %d %s: echoed %r' % (i, ' '.join(extra), st))
                ref = _run_summary(pair, tf, danny_params(p, pair, tf, **kw))
                n += _cmp(o, ref, sc, 'row %d %s' % (i, ' '.join(extra)), bad)
                if extra == ('--var-rollback', 'true'):
                    n += _cmp(o, row, rc_cols, 'row %d --var-rollback true' % i, bad)
                for name in moved:
                    if ' '.join(extra) == name:
                        moved[name] += not all(_same(o[k], row[k]) for k in sc)
        m_ok = all(v > 0 for v in moved.values())
        _p('  %s %s: 4 rows x (--path tv --cost tv | --path tv --cost stress | --path mag --cost stress | '
           '--var-rollback false | --var-rollback true | --script-sizing | all of them together) = danny.run with '
           'that path, cost, varRollback and sizing (useOnePerZone / useCooldown / cooldownIn at the script defaults): '
           '%d values: %s; rows whose result moves with --var-rollback false: %d of 4, with --script-sizing: %d of 4'
           % (pair, tf, n, 'all equal' if not bad else '; '.join(b for b in bad if b), moved['--var-rollback false'],
              moved['--script-sizing']))
        ok &= not bad and m_ok
        _free()
    # bad input
    pair, tf = CELLS[0]
    p = dict(SPEC_DEFAULT)
    cases = (('unknown dimension', dict(p, riskPctS3=2.0), ()),
             ('value not in the grid', dict(p, slAtrMultS2=1.0), ()),
             ('missing used dimension', {k: v for k, v in p.items() if k != 'inv'}, ()),
             ('filter on without signalDirection', dict(p, signalDirection=None), ()),
             ('filter off with signalDirection Original', dict(p, fgfOn=False, signalDirection=ORIG), ()),
             ('another preset', dict(p, presetMode='XAUUSD 5m'), ('--off-grid',)),
             ('below the Pine minimum', dict(p, slAtrMultS2=0.0), ('--off-grid',)),
             ('--var-rollback maybe', p, ('--var-rollback', 'maybe')),
             ('not an object', [1, 2], ()))
    res = []
    for name, q, extra in cases:
        rc, out, err = _one(pair, tf, q, *extra)
        res.append((name, rc, out.strip() == '' and 'calib_danny.py --one' in err))
    q = dict(p, slAtrMultS2=1.0, timeStopBars=40, manualZoneLength=75, deadBarsIn=20)
    rc, out, err = _one(pair, tf, q, '--off-grid')
    og = rc == 0 and json.loads(out)['setting']['in_grid'] is False and json.loads(out)['setting']['row'] is None
    if og:
        o = json.loads(out)
        ref = _run_summary(pair, tf, danny_params(q, pair, tf))
        og = all(_same(o[k], ref[k]) for k in ref)
    # filter off with the Original direction, off the grid = the grid row with inv flipped (P1)
    q = dict(p, fgfOn=False, signalDirection=ORIG)
    rc, out, err = _one(pair, tf, q, '--off-grid')
    rc2, out2, _ = _one(pair, tf, dict(p, fgfOn=False, signalDirection=None, inv=True))
    og2 = rc == 0 and rc2 == 0
    if og2:
        o, o2 = json.loads(out), json.loads(out2)
        ref = _run_summary(pair, tf, danny_params(q, pair, tf))
        og2 = (o['setting']['in_grid'] is False and o['setting']['p']['signalDirection'] == ORIG and o2['setting']['in_grid'] is True
               and all(_same(o[k], ref[k]) for k in ref) and all(_same(o[k], _swap_raw(o2)[k]) for k in ref))
    b_ok = all(rc == 2 and e for _, rc, e in res) and og and og2
    _p('  bad input is refused (exit code 2, nothing on stdout): %s; --off-grid runs a setting outside the grid '
       '(stop 1.0 ATR, time stop 40, zone length 75, dead bars 20) = danny.run: %s; --off-grid with the filter off '
       'and signalDirection Original = danny.run, and = the grid row with inv True (counters exchanged): %s'
       % (', '.join('%s -> %d' % (n, rc) for n, rc, _ in res), og, og2))
    return ok and b_ok


# ---------------------------------------------------------------------------------------------
# 4. worker count
# ---------------------------------------------------------------------------------------------
def _sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def test_4_workers():
    """(4) XAU 240, the full grid with 1 worker and with 3 workers (files in calib_tmp_danny/w1 and w3, not
    out/): every row and column identical, and the two files byte for byte; equal to out/ when it exists.
    With 1 worker everything runs in this process: danny.prepare is called once per signal setting,
    danny.simulate once per row, the filter permissions are computed once."""
    d1 = os.path.join(TMP, 'w1')
    d3 = os.path.join(TMP, 'w3')
    import fgf
    calls = dict(prepare=0, simulate=0, fgf=0)
    o_prep, o_sim, o_fgf = danny.prepare, danny.simulate, fgf.fgf_permissions

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
    danny.prepare, danny.simulate, fgf.fgf_permissions = c_prep, c_sim, c_fgf
    try:
        a, ia = C.run_cell('XAU', '240', workers=1, out_dir=d1, verbose=False)
    finally:
        danny.prepare, danny.simulate, fgf.fgf_permissions = o_prep, o_sim, o_fgf
    _free()
    b, ib = C.run_cell('XAU', '240', workers=3, out_dir=d3, verbose=False)
    _free()
    f1 = os.path.join(d1, 'calib_danny_XAU_240.parquet')
    f3 = os.path.join(d3, 'calib_danny_XAU_240.parquet')
    fa = pd.read_parquet(f1)
    fb = pd.read_parquet(f3)
    same = fa.equals(fb) and a.equals(b) and a.equals(fa) and len(fa) == N_GRID and list(fa.columns) == list(fb.columns) \
        and all(fa[c].dtype == fb[c].dtype for c in fa.columns)
    byt = _sha(f1) == _sha(f3)
    dims = json.load(open(os.path.join(d1, 'calib_danny_dims.json'))) == C.DIMS == json.load(open(os.path.join(d3, 'calib_danny_dims.json')))
    once = calls == dict(prepare=54, simulate=N_GRID + 1, fgf=1) and ia['prepares'] == 54 == ib['prepares']
    _p('  XAU 240: %d rows x %d columns; 1 worker %.1fs (runs %.1fs), 3 workers %.1fs (runs %.1fs, speed-up x%.2f): '
       'frames %s, files %s (sha256 %s), dims.json = DIMS: %s'
       % (len(fa), len(fa.columns), ia['t_total'], ia['t_run'], ib['t_total'], ib['t_run'], ia['t_run'] / ib['t_run'],
          'identical' if same else 'DIFFERENT', 'byte for byte equal' if byt else 'DIFFERENT bytes', _sha(f3)[:16], dims))
    _p('  the 1-worker run called danny.prepare %d times (54 signal settings), danny.simulate %d times (%d rows + 1 to '
       'load the kernel), fgf.fgf_permissions %d time(s): signals prepared once per signal setting and reused for all '
       'its exit settings: %s' % (calls['prepare'], calls['simulate'], N_GRID, calls['fgf'], once))
    ok = same and byt and dims and once
    fo = _out_file('XAU', '240')
    if os.path.exists(fo):
        fo_df = pd.read_parquet(fo)
        again = fo_df.equals(fb)
        _p('  out/calib_danny_XAU_240.parquet (the production run) equals this re-run: %s (bytes %s)'
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
    """(5) BTC 1 (the largest cell): the real preparation of all 54 signal settings, then one pass = the 648
    exit settings of one signal input (filter off + on) with 3 workers, for the default, the busiest and
    the quietest signal input; extrapolated to the 27 signal inputs. The full grid must stay under 45 min."""
    _free()
    load0 = os.getloadavg()[0]
    cell = C.prepare_cell('BTC', '1')
    t_prep = cell['t_prep']
    nsp = {si: int(np.count_nonzero(cell['P'][si]['d_spike'] | cell['P'][si]['s_spike'])) for si in cell['idx']}
    uniq = {k: len(set(id(cell['P'][si][k]) for si in cell['idx'])) for k in C._ARRAYS}
    _p('  BTC 1: %d chart bars, %d 1-minute bars; all 54 signal settings prepared in %.1fs (signals %.1fs, sub-bars + '
       'ATR %.1fs, kernel %.1fs); candles that open a zone: %d .. %d (default %d); distinct arrays kept for the 54 '
       'prepared inputs: %s'
       % (cell['bars'], cell['n_sub'], t_prep, cell['t_sig'], cell['t_sub'], cell['t_jit'], min(nsp.values()),
          max(nsp.values()), nsp[_default_sig_idx()[0]], ', '.join('%s %d' % kv for kv in uniq.items())))
    # one signal input (zone length, delta, EMA) = 2 consecutive signal settings: filter off, filter on
    order = sorted(range(0, 54, 2), key=lambda si: nsp[si])
    passes = (('default', _default_sig_idx()), ('busiest', [order[-1], order[-1] + 1]), ('quietest', [order[0], order[0] + 1]))
    t3 = []
    per = []
    keep = None
    mem = []
    for name, idx in passes:
        with _MemWatch() as mw:
            res, info = C.run_prepared(cell, workers=3, sig_idx=idx)
        mem.append(mw)
        t3.append(info['t_run'])
        per.append(info['busy'] / info['settings'])
        s = C.SIGNALS[idx[0]]
        _p('  pass %-8s (zone length %d, delta %g, EMA %s): %d settings, 3 workers %.1fs (%.4fs per setting per '
           'worker, workers busy %.0f%%)' % (name, s['manualZoneLength'], s['manualDeltaThreshold'],
                                             s['manualEmaLength'] if s['manualUseEmaFilter'] else 'off',
                                             info['settings'], info['t_run'], per[-1],
                                             100.0 * info['busy'] / (3 * info['t_run'])))
        if name == 'default':
            keep = res
    idx = passes[0][1]
    res1, info1 = C.run_prepared(cell, workers=1, sig_idx=idx)
    same = all(res1[si] == keep[si] or all(_same(x, y) for a, b in zip(res1[si], keep[si]) for x, y in zip(a, b))
               for si in idx)
    _p('  pass default with 1 worker: %.1fs (%.4fs per setting); speed-up of 3 workers x%.2f; rows identical to the '
       '3-worker pass: %s' % (info1['t_run'], info1['t_run'] / info1['settings'], info1['t_run'] / t3[0], same))
    est = t_prep + 27 * float(np.mean(t3))
    hi = t_prep + 27 * max(t3)
    cpu = 27 * info1['t_run'] / 3.0 + t_prep
    _p('  full grid BTC 1 with 3 workers = preparation %.1fs + 27 passes: %.1fs = %.1f min (mean pass), %.1f min '
       '(every pass as slow as the slowest); from the 1-worker pass / 3: %.1f min; limit 45 min; load average %.2f -> '
       '%.2f (other jobs share the 4 CPUs)'
       % (t_prep, est, est / 60.0, hi / 60.0, cpu / 60.0, load0, os.getloadavg()[0]))
    # memory: the parent holds every prepared input, the workers are forked from it (copy-on-write)
    pk = [m.peak(3) for m in mem]
    mem_ok = all(p is not None for p in pk)
    if mem_ok:
        top = max(pk, key=lambda x: x[1])
        import resource
        rss_self = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        mem_ok = top[1] / 1024.0 < MEM_LIMIT_MB and rss_self < MEM_LIMIT_MB
        _p('  memory during the 3-worker passes (%d samples with the parent and 3 workers alive): parent + workers '
           'hold %.0f MB together (sum of PSS; parent RSS %.0f MB, a worker\'s own private memory at most %.0f MB); '
           'peak RSS of this process over everything it ran, the preparation included: %.0f MB; limit %d MB of the '
           'machine\'s 15 GB: %s' % (sum(len([x for x in m.samples if x[0] >= 3]) for m in mem), top[1] / 1024.0,
                                      top[2] / 1024.0, max(p[3] for p in pk) / 1024.0, rss_self, MEM_LIMIT_MB, mem_ok))
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
    switch that is off leaves no trace (no trail / target / dead / breakeven exits, nothing blocked with
    the filter off, no slippage with our costs), and every dimension changes results somewhere in the cells."""
    ok = True
    live_all = {}
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        ex = [c for c in df.columns if c.startswith('exit_')]
        tr = df['trades']
        dead_off = ~df['p_useDeadExit'].to_numpy(bool)
        chk = {
            'trades = long + short': (tr == df['long'] + df['short']).all(),
            'trades = h1_trades + h2_trades': (tr == df['h1_trades'] + df['h2_trades']).all(),
            'trades = sum of the 9 exit kinds': len(ex) == 9 and (tr == df[ex].sum(axis=1)).all(),
            'net_pct = (final_equity - 2000) / 2000': ((df['final_equity'] - INIT) / INIT * 100 == df['net_pct']).all(),
            'half1_pct + half2_pct = net_pct': np.allclose(df['half1_pct'] + df['half2_pct'], df['net_pct'], rtol=0, atol=1e-9),
            'window': ((df['start'] == danny.WINDOWS[pair][0]) & (df['end'] == danny.WINDOWS[pair][1])).all() and df['bars'].nunique() == 1,
            'trailing off: no trail exit': (df.loc[~df['p_useTrailS2'], 'exit_trail'] == 0).all(),
            'target 0: no tp exit': (df.loc[df['p_tpRS2'] == 0.0, 'exit_tp'] == 0).all(),
            'dead exit off: no dead exit': (df.loc[dead_off, 'exit_dead'] == 0).all(),
            'breakeven is off everywhere: no be exit': (df['exit_be'] == 0).all(),
            'filter off: nothing blocked': (df.loc[~df['p_fgfOn'], ['blocked_long', 'blocked_short']] == 0).all().all(),
            'blocked <= raw': ((df['blocked_long'] <= df['raw_long']) & (df['blocked_short'] <= df['raw_short'])).all(),
            'pf / win NaN only without trades': ((df['pf'].isna() == (tr == 0)) & (df['win_pct'].isna() == (tr == 0))).all(),
            'costs > 0 with trades': ((df['costs'] > 0) == (tr > 0)).all(),
            'cost ours: no slippage in the fills': (df['slippage_paid'] == 0).all(),
            'fair halves finite': np.isfinite(df[['h1r_pct', 'h2r_pct', 'net_pct', 'max_dd_pct', 'net_r']].to_numpy()).all(),
            'max_dd in [0, 100]': ((df['max_dd_pct'] >= 0) & (df['max_dd_pct'] <= 100)).all(),
            'inherited <= reentry_same_bar <= trades, leg1 <= reentry': ((df['inherited'] <= df['reentry_same_bar'])
                                                                         & (df['reentry_leg1'] <= df['reentry_same_bar'])
                                                                         & (df['reentry_same_bar'] <= tr)).all(),
            'at most one trade closed by the window end': (df['exit_end'] <= 1).all(),
            'no entry closed on its own candle, but by the window end (zero_length)': (df['zero_length'] <= df['exit_end']).all(),
            'floor_ok on every row': bool(df['floor_ok'].all()),
        }
        failed = [k for k, v in chk.items() if not bool(v)]
        # the sizing: what the scale-free step and cap leave
        zq = int((df['zero_qty'] > 0).sum())
        cap = int((df['qty_capped'] > 0).sum())
        mb = int((df['margin_breach'] > 0).sum())
        # every dimension changes results: groups of rows that differ only in that dimension
        sc = _sumcols(df)
        sig = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
        K = _keys(df)
        # the p_ values as text, 'None' for an unused dimension (a missing value must not drop its group)
        ps = {c: np.array([repr(k[j]) for k in K]) for j, c in enumerate(_pcols())}
        joint = (('manualZoneLength', ['p_manualZoneLength']), ('manualDeltaThreshold', ['p_manualDeltaThreshold']),
                 ('EMA (manualUseEmaFilter, manualEmaLength)', ['p_manualUseEmaFilter', 'p_manualEmaLength']),
                 ('direction with the filter (fgfOn, signalDirection, inv)', ['p_fgfOn', 'p_signalDirection', 'p_inv']),
                 ('inv', ['p_inv']), ('slAtrMultS2', ['p_slAtrMultS2']), ('tpRS2', ['p_tpRS2']),
                 ('timeStopBars', ['p_timeStopBars']), ('dead (useDeadExit, deadBarsIn)', ['p_useDeadExit', 'p_deadBarsIn']),
                 ('useTrailS2', ['p_useTrailS2']), ('manualEmaLength alone (EMA on)', ['p_manualEmaLength']),
                 ('signalDirection alone (filter on)', ['p_signalDirection']), ('deadBarsIn alone (dead exit on)', ['p_deadBarsIn']))
        parts = []
        n_rows_g = n_sel_g = 0
        for name, cols in joint:
            others = [c for c in _pcols() if c not in cols]
            sel = np.ones(len(df), bool)
            if name.startswith('manualEmaLength alone'):
                sel = df['p_manualUseEmaFilter'].to_numpy(bool)
            elif name.startswith('signalDirection alone'):
                sel = df['p_fgfOn'].to_numpy(bool)
            elif name.startswith('deadBarsIn alone'):
                sel = df['p_useDeadExit'].to_numpy(bool)
            g = pd.Series(sig[sel]).groupby([ps[c][sel] for c in others]).agg(['size', 'nunique'])
            n_all = int((g['nunique'] == g['size']).sum())
            n_any = int((g['nunique'] > 1).sum())
            live_all[name] = live_all.get(name, 0) + n_any
            n_rows_g += int(g['size'].sum())
            n_sel_g += int(sel.sum())
            parts.append('%s %d / %d / %d' % (name, n_all, n_any, len(g)))
        # every row has its direction twin (inv flipped) in the file, and never its result
        pos = {k: i for i, k in enumerate(K)}
        j_inv = C.DIM_NAMES.index('inv')
        twin = np.array([pos.get(k[:j_inv] + (not k[j_inv],) + k[j_inv + 1:], -1) for k in K])
        no_twin = int((twin < 0).sum())                  # XAU 5: the extra (Auto) row has none
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
        # the grid's own repeats: a dead exit at 30 bars behind a time stop at 25 bars never acts
        n_late, n_late_eq, n_late_miss = _late_dead(df, K)
        late_ok = n_late == 27 * 6 * 3 * 2 * 2 == n_late_eq and n_late_miss == 0
        cand = int(((df['h1r_pct'] > 0) & (df['h2r_pct'] > 0) & (df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).sum())
        el = int(((df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).sum())
        _p('  %s %s (%s): %d rows, %d checks: %s' % (pair, tf, src, len(df), len(chk),
                                                     'all hold' if not failed else 'FAILED: ' + '; '.join(failed)))
        _p('    groups differing only in one dimension (all results distinct / some distinct / groups): %s' % '; '.join(parts))
        _p('    trades %d .. %d (median %d); distinct results %d of %d rows; rows with trades that equal their '
           'direction twin (inv flipped): %d; rows with a quantity floored to zero: %d, with a quantity reduced by the '
           'margin cap: %d (max quantity 1e9 never binds), with a margin breach: %d; rows with >= 30 trades in each '
           'half: %d, of which positive in both fair halves: %d'
           % (tr.min(), tr.max(), int(tr.median()), n_distinct, len(df), same_twin, zq, cap, mb, el, cand))
        _p('    every row is in a group of every analysis above (no row dropped): %s; rows without a direction twin in '
           'the file: %d; %s' % (n_rows_g == n_sel_g, no_twin, an_txt))
        _p('    rows whose dead exit (30 bars) comes after the time stop (25 bars) and so can never act: %d (27 x 6 x 12), '
           'equal to their twin with the dead exit off on every result column: %d: %s (the section-14 grid lists these '
           'combinations twice; the analysis counts identical results once)' % (n_late, n_late_eq, late_ok))
        ok &= not failed and same_twin == 0 and n_rows_g == n_sel_g and an and late_ok \
            and no_twin == (1 if (pair, tf) == ('XAU', '5') else 0)
    dead = [k for k, v in live_all.items() if v == 0]
    _p('  every dimension changes results in at least one group over the cells (presetMode has one value outside '
       'XAU 5): %s' % ('yes' if not dead else 'NO: %s' % dead))
    return ok and not dead


# ---------------------------------------------------------------------------------------------
# 7. every row
# ---------------------------------------------------------------------------------------------
def _groups(keys, pair, tf):
    """The rows of a file grouped by their danny.prepare params (this file's own mapping)."""
    groups = {}
    for i, k in enumerate(keys):
        prep, sim = _split(danny_params(dict(zip(SPEC_DIMS, k)), pair, tf))
        groups.setdefault(tuple(sorted((a, repr(b)) for a, b in prep.items())), (prep, []))[1].append((i, sim))
    return groups


def test_7_all_rows():
    """Every row of the cells' files, not a sample: recomputed in this process with danny.prepare once per
    signal setting and danny.simulate + danny.summary per row, the parameters from this file's own mapping
    (danny_params, split into the prepare and the simulate keys); every summary value must be equal. A
    sample of 30 rows cannot see one stale signal setting or one displaced chunk of rows; this does."""
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
        for gk in sorted(groups):
            prep, items = groups[gk]
            Pp = danny.prepare(pair, tf, prep)
            if sub is None:
                sub = (Pp['w0'], Pp['w1'], danny.get_sub(Pp))
            assert (Pp['w0'], Pp['w1']) == sub[:2]
            Pp['sub'] = sub[2]                      # the 1-minute table depends on the window rows only
            n_bad0 = len(bad_rows)
            for i, sim in items:
                s = danny.summary(Pp, danny.simulate(Pp, sim))
                if list(s) != sc:
                    fields_ok = False
                    break
                n_vals += len(sc)
                if not all(_same(vals[j][i], s[c]) for j, c in enumerate(sc)):
                    bad_rows.append(i)
            bad_groups += len(bad_rows) > n_bad0
            del Pp
        n_sig = 54 + (1 if (pair, tf) == ('XAU', '5') else 0)
        c_ok = (fields_ok and not bad_rows and len(groups) == n_sig and n_vals == len(df) * len(sc)
                and len(df) == C.n_settings(pair, tf) and bool(df['floor_ok'].all()))
        _p('  %s %s (%s): all %d rows recomputed (danny.prepare for each of the %d signal settings, danny.simulate + '
           'danny.summary per row): %d summary values, %s (%.1fs)'
           % (pair, tf, src, len(keys), len(groups), n_vals,
              'all equal' if c_ok else '%d ROWS DIFFER in %d signal settings (first rows %s)%s'
              % (len(bad_rows), bad_groups, bad_rows[:8], '' if fields_ok else '; the summary fields differ'),
              time.time() - t0))
        ok &= c_ok
        _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 8. every cell that has a file
# ---------------------------------------------------------------------------------------------
def test_8_every_cell():
    """Every cell with a file in out/: the file holds the grid in order with the result columns, and 4 random
    rows of EVERY signal setting (216 rows per cell) recomputed in this process (danny.prepare per signal
    setting, danny.simulate + danny.summary per row, this file's own mapping) equal the file. The other
    tests read two cells in full and, of the other twelve, only the default rows."""
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
            n = C.n_settings(pair, tf)
            now = C.file_meta(pair, tf, n)
            p10, _, _ = _own_p10(pair, tf)
            act, dst = T_TRAIL.get((pair, tf), (2.0, 1.0))
            g_ok = (len(df) == n and keys == spec_grid(pair, tf) and all(k in sc for k in SUM_REQUIRED) and meta is not None
                    and all(meta.get(k) == now[k] for k in ('strategy', 'pair', 'tf', 'path', 'cost', 'settings', 'window',
                                                            'varRollback', 'qtyStepS3', 'maxQtyS3', 'trailActAtr', 'trailDstAtr'))
                    and (meta['trailActAtr'], meta['trailDstAtr']) == (act, dst)
                    and bool(((df['start'] == danny.WINDOWS[pair][0]) & (df['end'] == danny.WINDOWS[pair][1])).all())
                    and bool(df['floor_ok'].all()) and dst * p10 >= T_FLOOR[pair]
                    and abs(meta['floor']['p10_atr_pct'] - p10) < 1e-6)
            cur = meta is not None and meta.get('danny_sha256') == now['danny_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
            groups = _groups(keys, pair, tf)
            n_rows = n_vals = 0
            bad_rows = []
            sub = None
            for gk in sorted(groups):
                prep, items = groups[gk]
                Pp = danny.prepare(pair, tf, prep)
                if sub is None:
                    sub = (Pp['w0'], Pp['w1'], danny.get_sub(Pp))
                assert (Pp['w0'], Pp['w1']) == sub[:2]
                Pp['sub'] = sub[2]
                for j in sorted(int(x) for x in rng.choice(len(items), size=min(4, len(items)), replace=False)):
                    i, sim = items[j]
                    s = danny.summary(Pp, danny.simulate(Pp, sim))
                    n_rows += 1
                    n_vals += len(sc)
                    if list(s) != sc or not all(_same(df[c].iat[i], s[c]) for c in sc):
                        bad_rows.append(i)
                del Pp
            h = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
            n_sig = 54 + (1 if (pair, tf) == ('XAU', '5') else 0)
            n_late, n_late_eq, n_late_miss = _late_dead(df, keys)
            late_ok = n_late == 1944 == n_late_eq and n_late_miss == 0
            c_ok = g_ok and not bad_rows and len(groups) == n_sig and n_rows == 216 + (1 if n_sig == 55 else 0) and late_ok
            tr = df['trades']
            _p('  %s %-3s: %d rows, the grid in order, metadata, window, floor_ok: %s; written with the danny.py / fgf.py '
               'now on disk: %s; %d rows (4 of each of the %d signal settings) recomputed: %d values, %s; distinct '
               'results %d; trades %d .. %d; rows with zero_qty > 0: %d; dead exit behind the time stop: %d rows, %d equal '
               'to the dead-exit-off twin%s (%.1fs)'
               % (pair, tf, len(df), g_ok, cur, n_rows, len(groups), n_vals,
                  'all equal' if not bad_rows else '%d ROWS DIFFER: %s' % (len(bad_rows), bad_rows[:8]),
                  len(np.unique(h)), tr.min(), tr.max(), int((df['zero_qty'] > 0).sum()), n_late, n_late_eq,
                  '' if late_ok else ' WRONG', time.time() - t0))
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
    _p('calib_tests_danny.py: cells %s; danny.py sha256 %s; calib_danny.py sha256 %s; load average %.2f'
       % (', '.join('%s %s' % c for c in CELLS), _sha(os.path.join(W, 'danny.py'))[:16],
          _sha(os.path.join(W, 'calib_danny.py'))[:16], os.getloadavg()[0]))
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
    _p('danny.py sha256 at the end %s' % _sha(os.path.join(W, 'danny.py'))[:16])
    return 0 if all(res.values()) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
