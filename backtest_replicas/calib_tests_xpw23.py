"""calib_tests_xpw23.py: tests of calib_xpw23.py (CALIB_SPEC.md, strategy "xpw23"; the grid is section
9 of SPEC_xpw23.md: 16,200 settings per cell, the direction dimension named inv, column floor_ok).

Usage: python3 -I calib_tests_xpw23.py [name filter ...] [--cells XAU:240,BTC:240] [--files-only]

  test_1_grid             the grid is the full product of section 9 (16,200 = 18 x 900), keys unique,
                          DIMS = the table of the spec file (read from it), SIGNALS / EXITS
                          consistent; the nine "trail can never arm" combinations are the ones left
                          out, and on data such a run equals its trail-off row; every setting maps to
                          the xpw23 params the spec means (an independent mapping written here; the
                          script defaults read from the .pine file); the floor table of section 9
                          recomputed here from the bar files (median ATR(14) / close, pools 7,128 /
                          11,664 / 16,200); the dimensions listed once (None) cannot change a result;
                          the files hold the grid in order and the rule's reader (calib_analyze)
                          sees the neighbours and the direction twins the spec describes
  test_2_default_rows     the default row, and the same row with inv true, equal the saved default
                          results of the module with the same path and cost:
                          out/inv_xpw23_<PAIR>_<TF>.json runs normal/on/mag/ours and
                          inverted/on/mag/ours, through the command line on BTC 60 and XAU 240 (plus
                          filter off and tv / script costs); every saved run of all 14 cells through
                          calib_xpw23.one (and the saved "Reverse every label" runs = the filter-off
                          inv rows); the default rows of the sweep (file, or the default label
                          setting run here with 3 workers) against the saved runs and xpw23.run
  test_3_one_rows         30 random rows per cell recomputed one at a time through
                          `calib_xpw23.py --one` (a new process each) equal the sweep rows (and echo
                          the row number); the same rows through xpw23.run with this file's own
                          mapping; --path / --cost; bad input; --off-grid
  test_4_workers          XAU 240: 1 worker vs 3 workers identical (frames and file bytes);
                          xpw23.prepare runs once per signal setting (18), xpw.xpw_signals once per
                          label setting (9), xpw23.simulate once per row
  test_5_timing_btc1      BTC 1 in a fresh process: the real preparation of all 18 signal settings
                          and one pass (the 1,800 settings of one label setting, 3 workers) for the
                          busiest, a middle and the quietest label setting, extrapolated to the full
                          grid: under 45 minutes; and the memory of that process and its 3 workers
                          (sum of PSS, sampled over the whole run; the peak RSS of the process):
                          under 4 GB
  test_6_row_consistency  what every row must satisfy whatever the data (counts add up, a switch
                          that is off leaves no trace, floor_ok is the rule), and every dimension
                          changes results
  test_7_all_rows         EVERY row of the cells' files (not a sample) recomputed in this process:
                          xpw23.prepare once per signal setting, xpw23.simulate + xpw23.summary per
                          row, with this file's own mapping; all summary values equal
  test_8_every_cell       every cell that has a file in out/: the file holds the grid in order,
                          floor_ok by this file's own median, and 4 random rows of EVERY signal
                          setting (72 rows per cell) recomputed in this process equal the file
  test_9_one_floor        `--one` on XAU 5 and BTC 5, where the floor binds: floor_ok false for the
                          default trail (0.75 ATR), true for 1.5 ATR and trail off, the pair's floor;
                          = the file's rows when the files exist (added by the sceptic: every row of
                          XAU 240 / BTC 240 is above the floor, so tests 2 and 3 cannot see it)

The cells of tests 3, 6 and 7 (and the files of test 1) are --cells (default XAU 240 and BTC 240):
the file out/calib_xpw23_<PAIR>_<TF>.parquet when it exists, else the cell is run here with 3
workers into calib_tmp_xpw23/w3/ (never into out/). Test 2 covers all 14 cells: the file when it
exists, else only the default label setting is run in memory (1,800 rows; --files-only skips
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
import xpw23  # noqa: E402
import xpw    # noqa: E402
import fgf    # noqa: E402
import calib_xpw23 as C  # noqa: E402

OUT = os.path.join(W, 'out')
TMP = os.path.join(W, 'calib_tmp_xpw23')
PINE = '/home/user/master/xpw_orientation_tdi_v2.8_strategy_FGF.pine'
SPEC = os.path.join(W, 'SPEC_xpw23.md')
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
WINDOWS = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}
INIT = 10000.0
CELLS = [('XAU', '240'), ('BTC', '240')]
FILES_ONLY = False
N_GRID = 16200
MEM_LIMIT_MB = 4000        # test 5: a BTC 1 run (the process and its 3 workers) stays under 4 GB
SUM_REQUIRED = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
                'net_R', 'h1_R', 'h2_R', 'exit_sl', 'exit_tp', 'exit_trail', 'exit_time', 'exit_close_all',
                'exit_reverse', 'exit_end', 'long', 'short', 'avg_bars_held', 'exposure')
TEXT = ('pair', 'tf', 'halves_rule', 'path', 'cost')


def _p(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# this file's own reading of the spec (independent of calib_xpw23's lists and mappings)
# ---------------------------------------------------------------------------------------------
SPEC_DIMS = ['actDL_actDS', 'actInf', 'fgfOn', 'inv', 'slAtrMult', 'tpRMult', 'trailOn', 'trActAtr', 'trDistAtr',
             'timeStop', 'maxOpen']
SPEC_VALUES = {'actDL_actDS': ['enter', 'off', 'exit only'], 'actInf': ['enter', 'off', 'exit only'],
               'fgfOn': [False, True], 'inv': [False, True], 'slAtrMult': [1.5, 3.0, 6.0],
               'tpRMult': [1.0, 2.0, 4.0, 0.0], 'trailOn': [False, True], 'trActAtr': [1.0, 3.0],
               'trDistAtr': [0.75, 1.5, 3.0], 'timeStop': [0, 24], 'maxOpen': [1, 3, 20]}
SPEC_KIND = {'actDL_actDS': 'categorical', 'actInf': 'categorical', 'fgfOn': 'categorical', 'inv': 'categorical',
             'slAtrMult': 'ordinal', 'tpRMult': 'ordinal', 'trailOn': 'categorical', 'trActAtr': 'ordinal',
             'trDistAtr': 'ordinal', 'timeStop': 'ordinal', 'maxOpen': 'ordinal'}
SPEC_SIDE = dict(zip(SPEC_DIMS, ['signal'] * 3 + ['exit'] * 8))
SPEC_DEFAULT = dict(zip(SPEC_DIMS, ('enter', 'enter', True, False, 3.0, 1.0, True, 1.0, 0.75, 0, 20)))
SPEC_UNUSED = {'trActAtr': {'trailOn': False}, 'trDistAtr': {'trailOn': False}}
# section 9: median over the window of ATR(14) / close in %, as printed there; the floors
T_MED = {('BTC', '1'): 0.0433, ('BTC', '5'): 0.1281, ('BTC', '15'): 0.2547, ('BTC', '30'): 0.3810,
         ('BTC', '60'): 0.5621, ('BTC', '120'): 0.8126, ('BTC', '240'): 1.1730, ('XAU', '1'): 0.0185,
         ('XAU', '5'): 0.0461, ('XAU', '15'): 0.0859, ('XAU', '30'): 0.1278, ('XAU', '60'): 0.1863,
         ('XAU', '120'): 0.2539, ('XAU', '240'): 0.3712}
T_FLOOR = {'BTC': 0.1, 'XAU': 0.05}
T_POOL_DISTS = {'1': (3.0,), '5': (1.5, 3.0)}                     # else: all three
T_POOL = {'1': 7128, '5': 11664}                                  # else 16,200
# the Pine's input defaults (xpw_orientation_tdi_v2.8_strategy_FGF.pine, lines 447-540 and 1130)
SCRIPT_SIG = dict(rsiLen=13, fastLen=2, slowLen=7, bbLen=34, bbMult=1.6185, scaleWin=True, flatWin=20, areaLen=5,
                  areaFrac=0.45, trendLen=20, sigRung="chart rung (*)", lblRead=True, actL1="enter", actL2="enter",
                  actS1="enter", actS2="enter", actDL="enter", actDS="enter", actEnd="enter", actInf="enter",
                  agreeOn=False, reverseAll=False, tradeAgree=True)
SCRIPT_X = dict(tradeDir="Both", oppCloses=True, entryFill="Signal tick", limitBars=5, maxOpen=20, exitUnit="ATR",
                slPtsIn=10000.0, tpPtsIn=30000.0, atrLen=14, slAtrMult=3.0, tpRMult=1.0, trailOn=True,
                trActPts=15000.0, trDistPts=10000.0, trActAtr=1.0, trDistAtr=0.75, timeStop=0, qtyMode="Fixed",
                qtyFixed=0.1, riskPct=1.0, qtyMax=2.0, qtyStep=0.01, xpwInv=False)
FIXED = {'tradeDir': 'Both', 'oppCloses': True, 'entryFill': 'Signal tick', 'exitUnit': 'ATR', 'atrLen': 14,
         'qtyMode': 'Fixed', 'qtyFixed': 0.1}


def spec_never_arms(sl, tp, act):
    """Section 9: "a trail that can never arm before the target fills (tpRMult > 0 and trActAtr >=
    tpRMult * slAtrMult)"."""
    return tp > 0 and act >= tp * sl


def spec_grid():
    """SPEC_xpw23.md section 9, in the order of its table: 3 x 3 x filter x direction x stop x target x
    [trail off | activation x distance, without the trails that can never arm] x time stop x max open."""
    G = []
    for a in ('enter', 'off', 'exit only'):
        for b in ('enter', 'off', 'exit only'):
            for f in (False, True):
                for inv in (False, True):
                    for sl in (1.5, 3.0, 6.0):
                        for tp in (1.0, 2.0, 4.0, 0.0):
                            trails = [(False, None, None)]
                            for act in (1.0, 3.0):
                                for dist in (0.75, 1.5, 3.0):
                                    if not spec_never_arms(sl, tp, act):
                                        trails.append((True, act, dist))
                            for ton, act, dist in trails:
                                for ts in (0, 24):
                                    for mo in (1, 3, 20):
                                        G.append((a, b, f, inv, sl, tp, ton, act, dist, ts, mo))
    return G


def own_params(p, path='mag', cost='ours'):
    """A setting (dict over SPEC_DIMS) as the complete xpw23 param sets (prepare, simulate), written
    from the spec: the script defaults with the swept inputs replaced; both divergence rows get the
    one value; a trail that is off keeps the script's own distances."""
    prep = dict(SCRIPT_SIG)
    prep.update(actDL=p['actDL_actDS'], actDS=p['actDL_actDS'], actInf=p['actInf'], fgfOn=p['fgfOn'])
    sim = dict(SCRIPT_X)
    sim.update(xpwInv=p['inv'], slAtrMult=p['slAtrMult'], tpRMult=p['tpRMult'], trailOn=p['trailOn'],
               timeStop=p['timeStop'], maxOpen=p['maxOpen'], path=path, cost=cost)
    if p['trailOn']:
        sim.update(trActAtr=p['trActAtr'], trDistAtr=p['trDistAtr'])
    return prep, sim


def pine_inputs():
    """name -> default of every `name = input.<type>(default, ...)` line of the Pine."""
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
            out[name] = v
    return out


def spec_table():
    """The dimension table of section 9 of SPEC_xpw23.md, read from the file: [(name, values, kind,
    stage)], and its floor table: {(pair, tf): (median %, distances in the pool or None = all, pool)}."""
    txt = open(SPEC, encoding='utf-8').read()
    sec = txt[txt.index('## 9. Calibration grid proposal'):]
    dims = []
    for line in sec.splitlines():
        m = re.match(r'^\| `(\w+)`[^|]*\| ([^|]+) \| (ordinal|categorical) \| (prepare|simulate) \|$', line)
        if not m:
            continue
        name, vals, kind, stage = m.groups()
        vals = vals.split(' (')[0]
        out = []
        for v in (vals.split('", "') if vals.startswith('"') else vals.split(', ')):
            v = v.strip().strip('"')
            if v in ('false', 'true'):
                out.append(v == 'true')
            elif re.fullmatch(r'-?\d+', v):
                out.append(int(v))
            elif re.fullmatch(r'-?\d+\.\d+', v):
                out.append(float(v))
            else:
                out.append(v)
        dims.append((name, out, kind, stage))
    floor = {}
    for line in sec.splitlines():
        m = re.match(r'^\| (BTC|XAU) ([\d, ]+) \| ([\d., ]+)% \| ([^|]+) \| ([\d,]+) \|$', line)
        if not m:
            continue
        pair, tfs, meds, dists, pool = m.groups()
        tfs = [t.strip() for t in tfs.split(',')]
        meds = [float(x) for x in meds.split(',')]
        ds = None if dists.strip() == 'all' else tuple(float(x) for x in dists.split(','))
        for tf, md in zip(tfs, meds):
            floor[(pair, tf)] = (md, ds, int(pool.replace(',', '')))
    return dims, floor


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
    return ['p_' + n for n in SPEC_DIMS]


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
    return os.path.join(OUT, 'calib_xpw23_%s_%s.parquet' % (pair, tf))


def _fresh(path):
    """A scratch file is used only when it is newer than the runner and the replica."""
    return os.path.exists(path) and os.path.getmtime(path) > max(
        os.path.getmtime(os.path.join(W, f)) for f in ('calib_xpw23.py', 'xpw23.py', 'xpw.py', 'fgf.py'))


_DF = {}


def _cell_df(pair, tf):
    """(DataFrame, where): out/ when the cell's file exists, else calib_tmp_xpw23/w3 (run here if needed)."""
    key = (pair, tf)
    if key not in _DF:
        f = _out_file(pair, tf)
        if os.path.exists(f):
            src = 'out/' + os.path.basename(f)
            if not _fresh(f):
                _p('  note: %s is older than calib_xpw23.py or the replica modules' % src)
        else:
            d3 = os.path.join(TMP, 'w3')
            f = os.path.join(d3, 'calib_xpw23_%s_%s.parquet' % (pair, tf))
            src = 'calib_tmp_xpw23/w3/' + os.path.basename(f)
            if not _fresh(f):
                t0 = time.time()
                C.run_cell(pair, tf, workers=3, out_dir=d3, verbose=False)
                _p('  %s %s has no file in out/: run here with 3 workers into %s (%.1fs)' % (pair, tf, src, time.time() - t0))
                _free()
        _DF[key] = (pd.read_parquet(f), src)
    return _DF[key]


def _free():
    C.free()
    gc.collect()


def _num_summary(s):
    """xpw23.summary without its five text fields (the row's fields)."""
    return {k: v for k, v in s.items() if k not in TEXT}


class _Ref:
    """xpw23 called directly with this file's own mapping: prepare once per (pair, tf, prepare params),
    simulate + summary per setting. The 1-minute table and ATR(14) of a window are shared."""

    def __init__(self, pair, tf):
        self.pair, self.tf = pair, str(tf)
        self.P = {}
        self.sub = None
        self.atr = {}

    def prepared(self, prep):
        k = tuple(sorted((a, repr(b)) for a, b in prep.items()))
        Pp = self.P.get(k)
        if Pp is None:
            Pp = xpw23.prepare(self.pair, self.tf, prep)
            if self.sub is None:
                self.sub = (Pp['w0'], Pp['w1'], xpw23.get_sub(Pp))
            assert (Pp['w0'], Pp['w1']) == self.sub[:2]
            Pp['sub'] = self.sub[2]
            Pp['_atr'] = self.atr
            self.P[k] = Pp
        return Pp

    def run(self, prep, sim):
        Pp = self.prepared(prep)
        s = xpw23.summary(Pp, xpw23.simulate(Pp, sim))
        ok = (s['pair'], s['tf'], s['path'], s['cost']) == (self.pair, self.tf, sim['path'], sim['cost'])
        return _num_summary(s), ok and s['halves_rule'] == 'additive'

    def row(self, p, path='mag', cost='ours'):
        prep, sim = own_params(p, path, cost)
        return self.run(prep, sim)

    def drop(self):
        self.P.clear()


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


def _swap_labels(s):
    """A summary with the label-side counters exchanged (the same trades from the mirrored labels)."""
    out = dict(s)
    out['raw_long'], out['raw_short'] = s['raw_short'], s['raw_long']
    out['blocked_long'], out['blocked_short'] = s['blocked_short'], s['blocked_long']
    out['labels_long'], out['labels_short'] = s['labels_short'], s['labels_long']
    return out


def _own_median(pair, tf):
    """The median over the window of ATR(14) / close in %, computed here from the bar file with pandas
    (Wilder's average as an exponential mean of the true range; the window starts thousands of bars
    into the file, so its seed no longer matters). Returns (median, first window row, window rows)."""
    t = pq.read_table(os.path.join(W, 'data', '%s_%s.parquet' % (pair, tf)), columns=['high', 'low', 'close', 't_close'])
    h, l, c, tc = (t.column(k).to_numpy() for k in ('high', 'low', 'close', 't_close'))
    pc = np.concatenate(([np.nan], c[:-1]))
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1.0 / 14.0, adjust=False).mean().to_numpy()
    s0, e0 = WINDOWS[pair]
    m = (tc >= s0) & (tc <= e0)
    return float(np.median(atr[m] / c[m] * 100.0)), int(np.argmax(m)), int(m.sum())


_MED = {}


def _median(pair, tf):
    if (pair, tf) not in _MED:
        _MED[(pair, tf)] = _own_median(pair, tf)
    return _MED[(pair, tf)]


def _own_floor_ok(pair, tf, k):
    """floor_ok of a key tuple by this file's own median: trail off, or trDistAtr x median >= the floor."""
    return (not k[6]) or (k[8] * _median(pair, tf)[0] >= T_FLOOR[pair])


def _sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def _nb_brute(K, kinds, values, i, jdir):
    """The neighbours of row i as CALIB_SPEC.md words them: rows that differ in exactly one dimension
    (a dimension unused on either side follows its switch and is not counted), one step for an ordinal
    dimension, any other value for a categorical one; never the direction."""
    a = K[i]
    out = []
    for r, b in enumerate(K):
        diff = [j for j in range(len(a)) if a[j] is not None and b[j] is not None and a[j] != b[j]]
        if len(diff) != 1 or diff[0] == jdir:
            continue
        j = diff[0]
        if kinds[j] == 'ordinal' and abs(values[j].index(a[j]) - values[j].index(b[j])) != 1:
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------------------------------------
# 1. the grid
# ---------------------------------------------------------------------------------------------
def test_1_grid():
    """(1) The grid is the full product of section 9, keys unique; DIMS is the table of the spec file;
    SIGNALS, EXITS and the xpw23 params of every setting are what the spec says; the trails that can
    never arm are the nine left out and equal their trail-off rows on data; the floor table recomputed
    from the bar files; the dimensions listed once cannot change a result; the files hold the grid."""
    ok = True
    # ---- the product
    S = spec_grid()
    G = C.grid()
    K = [C.key(p) for p in G]
    full = [(sl, tp, ton, act, dist) for sl in (1.5, 3.0, 6.0) for tp in (1.0, 2.0, 4.0, 0.0)
            for ton, act, dist in [(False, None, None)] + [(True, a, d) for a in (1.0, 3.0) for d in (0.75, 1.5, 3.0)]]
    kept = sorted(set(k[4:9] for k in S), key=full.index)
    left = [c for c in full if c not in kept]
    left_want = [(sl, tp, True, 3.0, d) for sl, tp in ((1.5, 1.0), (1.5, 2.0), (3.0, 1.0)) for d in (0.75, 1.5, 3.0)]
    a = (len(S) == N_GRID == len(set(S)) and len(G) == N_GRID == len(set(K)) and K == S and C.N_GRID == N_GRID
         and N_GRID == 18 * 900 == 3 * 3 * 2 * (2 * (12 * 7 - 9) * 2 * 3)
         and G == [C.merge(s, x) for s in C.SIGNALS for x in C.exits_for(s)])
    b = (len(full) == 84 and len(kept) == 75 and left == left_want
         and all(spec_never_arms(sl, tp, act) for sl, tp, _, act, _ in left)
         and not any(ton and spec_never_arms(sl, tp, act) for sl, tp, ton, act, _ in kept)
         and all(C.never_arms(sl, tp, act) == spec_never_arms(sl, tp, act)
                 for sl in (1.5, 3.0, 6.0) for tp in (1.0, 2.0, 4.0, 0.0) for act in (1.0, 3.0)))
    _p('  spec product 16,200 = 18 signal settings (3 x 3 x filter off / on) x 900 exit settings (2 directions x 75 '
       'stop / target / trail x 2 time stops x 3 max open); the runner\'s grid = the spec\'s, same order, keys '
       'unique: %s' % a)
    _p('  stop x target x trail = 12 x 7 = 84, minus the 9 trail-on combinations that can never arm (tpRMult > 0 and '
       'trActAtr >= tpRMult x slAtrMult: (1.5, 1), (1.5, 2), (3, 1) with activation 3.0, each x 3 distances) = 75; '
       'exactly those 9 are not rows, their trail-off row is: %s' % b)
    ok &= a and b
    # ---- the two lists
    sk = [tuple(s[k] for k in C.SIGNAL_DIMS) for s in C.SIGNALS]
    xk = [tuple(x[k] for k in C.EXIT_DIMS) for x in C.EXITS]
    c = (len(sk) == 18 == len(set(sk)) and len(xk) == 900 == len(set(xk)) and all(C.exits_for(s) is C.EXITS for s in C.SIGNALS)
         and list(C.SIGNAL_DIMS) + list(C.EXIT_DIMS) == C.DIM_NAMES == SPEC_DIMS
         and all(sk[i][:2] == sk[i + 1][:2] and sk[i][2] is False and sk[i + 1][2] is True for i in range(0, 18, 2)))
    _p('  SIGNALS %d unique (prepare params), EXITS %d unique (simulate params), every signal setting has all of them; '
       'the two filter states of a label setting are consecutive signal settings: %s' % (len(set(sk)), len(set(xk)), c))
    ok &= c
    # ---- DIMS: the table of the spec file itself, and what is written here
    tdims, tfloor = spec_table()
    t_ok = ([('inv' if n == 'xpwInv' else n) for n, _, _, _ in tdims] == SPEC_DIMS
            and all(v == SPEC_VALUES[('inv' if n == 'xpwInv' else n)] and [type(x) for x in v] == [type(x) for x in SPEC_VALUES[('inv' if n == 'xpwInv' else n)]]
                    for n, v, _, _ in tdims)
            and all(k == SPEC_KIND[('inv' if n == 'xpwInv' else n)] for n, _, k, _ in tdims)
            and all({'prepare': 'signal', 'simulate': 'exit'}[st] == SPEC_SIDE[('inv' if n == 'xpwInv' else n)] for n, _, _, st in tdims))
    d_ok = [d['name'] for d in C.DIMS] == SPEC_DIMS and len(C.DIMS) == 11 and all(
        {'name', 'values', 'kind'} <= set(d) <= {'name', 'values', 'kind', 'side', 'default', 'unused_when'}
        and d['values'] == SPEC_VALUES[d['name']] and [type(v) for v in d['values']] == [type(v) for v in SPEC_VALUES[d['name']]]
        and d['default'] == SPEC_DEFAULT[d['name']] and type(d['default']) is type(SPEC_DEFAULT[d['name']])
        and d['side'] == SPEC_SIDE[d['name']] and d.get('unused_when') == SPEC_UNUSED.get(d['name'])
        and d['kind'] == SPEC_KIND[d['name']] for d in C.DIMS)
    d_ok &= C.DEFAULT_P == SPEC_DEFAULT and C.DEFAULT is C.DEFAULT_P
    for j, d in enumerate(C.DIMS):
        seen = set(k[j] for k in S if k[j] is not None)
        d_ok &= set(d['values']) == seen and len(d['values']) == len(seen)
        if d['kind'] == 'ordinal' and d['name'] != 'tpRMult':
            d_ok &= list(d['values']) == sorted(d['values'])
    d_ok &= C.DIMS[5]['values'] == [1.0, 2.0, 4.0, 0.0]            # 0 = no target, ordered last
    none_ok = all((k[7] is None) == (k[6] is False) == (k[8] is None)
                  and all(k[j] is not None for j in range(11) if j not in (7, 8)) for k in S)
    dir_ok = [d['name'] for d in C.DIMS if d['name'] in ('inv', 'xpwInv')] == ['inv'] \
        and C.DIMS[3]['kind'] == 'categorical' and C.DIMS[3]['values'] == [False, True]
    _p('  DIMS: %d dimensions %s; names (xpwInv named inv), values, kinds and stages = the table of section 9 read '
       'from SPEC_xpw23.md: %s, = the copy written here with the defaults: %s; None only for trActAtr / trDistAtr '
       'with the trail off, and always there: %s; the direction dimension is inv [False, True]: %s'
       % (len(C.DIMS), [d['name'] for d in C.DIMS], t_ok, d_ok, none_ok, dir_ok))
    ok &= t_ok and d_ok and none_ok and dir_ok
    try:
        ok &= json.loads(json.dumps(C.DIMS)) == C.DIMS
    except Exception as e:      # noqa: BLE001
        ok = False
        _p('  DIMS is not JSON: %r' % (e,))
    # ---- the script defaults: this file's copy, the modules', the Pine's own input lines
    xd = dict(xpw23.X_DEFAULTS)
    m_ok = (xpw.DEFAULTS == SCRIPT_SIG and {k: v for k, v in xd.items() if k not in ('path', 'cost')} == SCRIPT_X
            and (xd['path'], xd['cost']) == ('tv', 'tv') and fgf.DEFAULTS['fgfOn'] is True)
    pin = pine_inputs()
    both = dict(SCRIPT_SIG, **SCRIPT_X)
    found = [k for k in both if k in pin]
    diff = {k: (both[k], pin[k]) for k in found
            if not (both[k] == pin[k] and isinstance(both[k], bool) == isinstance(pin[k], bool))}
    missing = sorted(set(both) - set(found))
    fgf_diff = {k: (fgf.DEFAULTS[k], pin[k]) for k in fgf.DEFAULTS if k in pin
                and not (fgf.DEFAULTS[k] == pin[k] and isinstance(fgf.DEFAULTS[k], bool) == isinstance(pin[k], bool))}
    pine_dims = dict(actDL_actDS=pin.get('actDL'), actInf=pin.get('actInf'), fgfOn=pin.get('fgfOn'), inv=pin.get('xpwInv'),
                     slAtrMult=pin.get('slAtrMult'), tpRMult=pin.get('tpRMult'), trailOn=pin.get('trailOn'),
                     trActAtr=pin.get('trActAtr'), trDistAtr=pin.get('trDistAtr'), timeStop=pin.get('timeStop'),
                     maxOpen=pin.get('maxOpen'))
    p_ok = (not diff and not missing and not fgf_diff and pine_dims == SPEC_DEFAULT and pin.get('actDS') == 'enter'
            and all(pin.get(k) == v for k, v in FIXED.items()) and C.FIXED_X == FIXED
            and all(type(C.FIXED_X[k]) is type(v) for k, v in FIXED.items()) and C.ATR_LEN == 14 == pin.get('atrLen'))
    _p('  script defaults: xpw.DEFAULTS and xpw23.X_DEFAULTS = the %d written here: %s; the Pine file\'s own input '
       'lines give the same default for %d of them (different: %s; not found: %s) and for the %d filter inputs of '
       'fgf.DEFAULTS found there (different: %s); the 11 dimensions\' Pine defaults = DEFAULT_P; the fixed inputs '
       '(Signal tick, Fixed 0.1, ATR 14, Both) are the Pine\'s: %s'
       % (len(both), m_ok, len(found), diff or 'none', missing or 'none', sum(k in pin for k in fgf.DEFAULTS),
          fgf_diff or 'none', p_ok))
    ok &= m_ok and p_ok
    # ---- the xpw23 params of every setting
    n_bad = 0
    for p in G:
        sig = {k: p[k] for k in C.SIGNAL_DIMS}
        ex = {k: p[k] for k in C.EXIT_DIMS}
        sp = C.signal_params(sig)
        xp = C.exit_params(ex)
        prep, sim = own_params(p)
        eff_p = dict(xpw.DEFAULTS, **{k: v for k, v in sp.items() if k in xpw.DEFAULTS})
        eff_f = dict(fgf.DEFAULTS, **{k: v for k, v in sp.items() if k in fgf.DEFAULTS})
        eff_x = xpw23.resolve_x(xp)
        want_x = xpw23.resolve_x(sim)
        if (eff_p != {k: v for k, v in prep.items() if k != 'fgfOn'} or eff_f != dict(fgf.DEFAULTS, fgfOn=p['fgfOn'])
                or eff_x != want_x or want_x != sim or any(type(eff_x[k]) is not type(sim[k]) for k in sim)
                or (set(sp) - xpw23._PREP_KEYS) or (set(xp) - xpw23._SIM_KEYS) or (set(sp) & xpw23._SIM_KEYS)
                or sp['actDL'] != sp['actDS']):
            n_bad += 1
            if n_bad <= 3:
                _p('  MAPPING %r: %r' % (p, {k: (eff_x.get(k), sim.get(k)) for k in sim if eff_x.get(k) != sim.get(k)}))
    dp = dict(SPEC_DEFAULT)
    eff_d = xpw23.resolve_x(C.exit_params({k: dp[k] for k in C.EXIT_DIMS}))
    def_ok = (K.count(C.key(SPEC_DEFAULT)) == 1 and eff_d == dict(SCRIPT_X, path='mag', cost='ours')
              and C.signal_params({k: dp[k] for k in C.SIGNAL_DIMS}) == dict(actDL='enter', actDS='enter', actInf='enter', fgfOn=True)
              and C.PATH == 'mag' and C.COST == 'ours' and C.row_of(SPEC_DEFAULT) == K.index(C.key(SPEC_DEFAULT)) == S.index(tuple(SPEC_DEFAULT.values())))
    _p('  xpw23 params of all %d settings (signal_params + exit_params, resolved as the module resolves them) = the '
       'mapping written here (%d signal + %d order / exit inputs + path mag, cost ours): %d different; signal params '
       'only prepare keys, exit params only simulate keys' % (len(G), len(SCRIPT_SIG) + 1, len(SCRIPT_X), n_bad))
    _p('  the script\'s default setting is one row (row %d); its params = the script defaults with path mag, cost '
       'ours: %s' % (C.row_of(SPEC_DEFAULT), def_ok))
    ok &= n_bad == 0 and def_ok
    # ---- normalize: every grid row round-trips, as the file gives it (p_ prefix, NaN or None for unused)
    n_rt = sum(C.normalize({'p_' + k: (float('nan') if v is None else v) for k, v in p.items()}) == p
               and C.normalize({k: v for k, v in p.items() if v is not None}) == p for p in G)
    forced = C.normalize(dict(SPEC_DEFAULT, trailOn=False, trActAtr=3.0, trDistAtr=1.5))
    refused = 0
    for sl, tp, _, act, dist in left:
        q = dict(SPEC_DEFAULT, slAtrMult=sl, tpRMult=tp, trActAtr=act, trDistAtr=dist)
        try:
            C.normalize(q)
        except ValueError:
            refused += 1
        kept_q = C.normalize(q, off_grid=True)
        refused += 100 * (kept_q != q or C.row_of(kept_q) is not None or C.in_grid(kept_q))
    r_ok = (n_rt == len(G) and forced['trActAtr'] is None and forced['trDistAtr'] is None and refused == 9
            and C.row_of(forced) == K.index(C.key(forced)))
    _p('  normalize(): %d of %d grid rows round-trip (p_ prefix, NaN / missing for unused); a value given for an '
       'unused dimension is dropped; the 9 never-arming combinations are refused (their run is the trail-off row) '
       'unless --off-grid: %s' % (n_rt, len(G), r_ok))
    ok &= r_ok
    # ---- the floor: the table of section 9, recomputed from the bar files
    f_ok = set(tfloor) == set(T_MED)
    parts = []
    for pair in PAIRS:
        for tf in TFS:
            med, w0, n = _median(pair, tf)
            dists = [d for d in (0.75, 1.5, 3.0) if d * med >= T_FLOOR[pair]]
            pool = sum(1 for k in S if _own_floor_ok(pair, tf, k))
            want_d = list(T_POOL_DISTS.get(tf, (0.75, 1.5, 3.0)))
            want_pool = T_POOL.get(tf, N_GRID)
            tm, td, tp_ = tfloor.get((pair, tf), (None, None, None))
            c_ok = (abs(med - T_MED[(pair, tf)]) <= 0.00006 and dists == want_d and pool == want_pool and w0 > 1000
                    and tm == T_MED[(pair, tf)] and tp_ == want_pool and list(td or (0.75, 1.5, 3.0)) == want_d
                    and C.FLOOR_PCT[pair] == T_FLOOR[pair]
                    and all(C.floor_ok(dict(zip(SPEC_DIMS, k)), {'median_atr_pct': med, 'floor_pct': T_FLOOR[pair]})
                            == _own_floor_ok(pair, tf, k) for k in S[:900]))
            f_ok &= c_ok
            parts.append('%s %s %.4f%% -> %s, pool %d%s' % (pair, tf, med, '/'.join('%g' % d for d in dists), pool,
                                                           '' if c_ok else ' WRONG'))
    _p('  floor: median over the window of ATR(14) / close recomputed here from the 14 bar files = the table of '
       'section 9 (4 decimals); trDistAtr values with distance x median >= the floor (BTC 0.1 %%, XAU 0.05 %%) and '
       'the pool they leave (7,128 on the 1-minute charts, 11,664 on the 5-minute charts, else 16,200) = the '
       'table: %s' % f_ok)
    _p('    ' + '; '.join(parts))
    ok &= f_ok
    # ---- on data: a trail that cannot arm = the trail-off row; trail distances with the trail off
    rng = np.random.default_rng(20261126)
    cnt = dict(never=0, eq=0, off=0, ctl=0)
    dif = dict(never=0, eq=0, off=0, ctl=0)
    tp_hits = 0
    for pair, tf in CELLS:
        ref = _Ref(pair, tf)
        for si in sorted(int(i) for i in rng.choice(18, size=6, replace=False)):
            a_, b_, f_ = sk[si]
            for inv in (False, True):
                for path in ('mag', 'tv'):
                    for sl, tp, _, act, dist in left:
                        ts = int(rng.choice([0, 24]))
                        mo = int(rng.choice([1, 3, 20]))
                        base = dict(zip(SPEC_DIMS, (a_, b_, f_, inv, sl, tp, False, None, None, ts, mo)))
                        prep, sim = own_params(base, path)
                        s_off, _ = ref.run(prep, sim)
                        s_on, _ = ref.run(prep, dict(sim, trailOn=True, trActAtr=act, trDistAtr=dist))
                        kind = 'eq' if act == tp * sl else 'never'
                        cnt[kind] += 1
                        dif[kind] += not all(_same(s_off[k], s_on[k]) for k in s_off)
                        tp_hits += s_off['exit_tp'] > 0
                        if dist == 0.75:
                            # control: the same trail with an activation that CAN arm is another run
                            s_c, _ = ref.run(prep, dict(sim, trailOn=True, trActAtr=1.0, trDistAtr=dist))
                            cnt['ctl'] += 1
                            dif['ctl'] += not all(_same(s_off[k], s_c[k]) for k in s_off)
                    for _ in range(4):
                        k = S[int(rng.integers(len(S)))]
                        base = dict(zip(SPEC_DIMS, (a_, b_, f_, inv) + k[4:6] + (False, None, None) + k[9:]))
                        prep, sim = own_params(base, path)
                        s0, _ = ref.run(prep, sim)
                        s1, _ = ref.run(prep, dict(sim, trActAtr=3.0, trDistAtr=3.0))
                        s2, _ = ref.run(prep, dict(sim, trActAtr=0.2, trDistAtr=0.05))
                        cnt['off'] += 1
                        dif['off'] += not (all(_same(s0[k], s1[k]) for k in s0) and all(_same(s0[k], s2[k]) for k in s0))
        ref.drop()
        _free()
    u_ok = dif['never'] == dif['eq'] == dif['off'] == 0 and dif['ctl'] > 0.9 * cnt['ctl'] and tp_hits > 0.9 * (cnt['never'] + cnt['eq'])
    _p('  on data (%s; 6 signal settings x normal / inverted x paths mag / tv): runs with a different summary / runs '
       'tried: trail on that can never arm vs its trail-off run: activation beyond the target %d/%d, activation '
       'exactly at the target (3.0 ATR = 2 x 1.5 = 1 x 3.0) %d/%d (%d of these runs fill targets); control, the '
       'same trail with activation 1.0: %d/%d differ; other trail distances with the trail off: %d/%d: %s'
       % (', '.join('%s %s' % c for c in CELLS), dif['never'], cnt['never'], dif['eq'], cnt['eq'], tp_hits, dif['ctl'],
          cnt['ctl'], dif['off'], cnt['off'], u_ok))
    ok &= u_ok
    # ---- the files
    fd = os.path.join(OUT, 'calib_xpw23_dims.json')
    if os.path.exists(fd):
        same = json.load(open(fd)) == C.DIMS
        _p('  out/calib_xpw23_dims.json equals DIMS: %s' % same)
        ok &= same
    else:
        _p('  out/calib_xpw23_dims.json: not written yet')
    import calib_analyze as CA
    kinds = [SPEC_KIND[n] for n in SPEC_DIMS]
    values = [SPEC_VALUES[n] for n in SPEC_DIMS]
    cols_want = None
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        if cols_want is None:
            Pp = xpw23.prepare(pair, tf, {})
            s = xpw23.summary(Pp, xpw23.simulate(Pp, {'path': 'mag', 'cost': 'ours'}))
            text_ok = [k for k, v in s.items() if isinstance(v, str)] == list(TEXT)
            cols_want = [k for k in s if k not in TEXT]
            scalar = all(isinstance(s[k], (int, float, np.integer, np.floating)) and not isinstance(s[k], bool) for k in cols_want)
            int_cols = [k for k in cols_want if isinstance(s[k], (int, np.integer))]
        kf = _keys(df)
        fl_own = [_own_floor_ok(pair, tf, k) for k in kf]
        f_ok = (len(df) == N_GRID and kf == S and list(df.columns) == _pcols() + ['floor_ok'] + cols_want and scalar and text_ok
                and all(k in cols_want for k in SUM_REQUIRED) and df['floor_ok'].dtype == bool
                and df['floor_ok'].tolist() == fl_own
                and all(str(df[c].dtype) == 'int64' for c in int_cols)
                and all(str(df[c].dtype) == 'float64' for c in cols_want if c not in int_cols)
                and all(str(df['p_' + n].dtype) == 'bool' for n in ('fgfOn', 'inv', 'trailOn'))
                and all(str(df['p_' + n].dtype) == 'int64' for n in ('timeStop', 'maxOpen'))
                and all(str(df['p_' + n].dtype) == 'float64' for n in ('slAtrMult', 'tpRMult', 'trActAtr', 'trDistAtr')))
        nulls = {c: int(df[c].isna().sum()) for c in _rescols(df) if df[c].isna().any()}
        f_ok &= set(nulls) <= {'pf', 'win_pct', 'avg_bars_held'}
        _p('  %s: %d rows; p_ columns = the grid in order; columns = %d p_ + floor_ok (= the rule, by this file\'s own '
           'median: %d True) + the %d numeric fields of xpw23.summary in its order (its %d text fields pair, tf, '
           'halves_rule, path, cost are in the metadata), nothing else: %s (NaN: %s)'
           % (src, len(df), len(_pcols()), sum(fl_own), len(cols_want), len(TEXT), f_ok, nulls or 'none'))
        ok &= f_ok
        meta = C.read_meta(os.path.join(W, src))
        now = C.file_meta(pair, tf, N_GRID)
        med = _median(pair, tf)[0]
        m_ok = (meta is not None and all(meta.get(k) == now[k] for k in ('strategy', 'pair', 'tf', 'path', 'cost', 'settings', 'window', 'halves_rule', 'fixed'))
                and meta['strategy'] == 'xpw23' and meta['path'] == 'mag' and meta['cost'] == 'ours' and meta['settings'] == N_GRID
                and meta['window'] == list(WINDOWS[pair]) and meta['halves_rule'] == 'additive' and meta['fixed'] == FIXED
                and abs(meta['floor']['median_atr_pct'] - med) <= 1e-9 * med and meta['floor']['floor_pct'] == T_FLOOR[pair]
                and meta['floor']['atr_len'] == 14)
        cur = meta is not None and all(meta.get(k) == now[k] for k in ('xpw23_sha256', 'xpw_sha256', 'fgf_sha256'))
        _p('    file metadata: %s, path %s, cost %s, %s settings, halves_rule %s, fixed inputs, floor median %.6f %% (= '
           'this file\'s own %.6f): %s; written with the xpw23.py, xpw.py and fgf.py now on disk: %s'
           % ((meta or {}).get('strategy'), (meta or {}).get('path'), (meta or {}).get('cost'), (meta or {}).get('settings'),
              (meta or {}).get('halves_rule'), ((meta or {}).get('floor') or {}).get('median_atr_pct', float('nan')), med, m_ok,
              cur if cur else 'NO (rows are still checked against the module by tests 2, 3 and 7)'))
        ok &= m_ok
        # the rule's reader: codes, direction twins, neighbours
        Cd = CA.codes_of(df, C.DIMS)
        jdir = [j for j, d in enumerate(C.DIMS) if d['name'].lower() in CA.DIR_NAMES]
        code_ok = jdir == [3] and all((Cd[i, j] == -1) == (kf[i][j] is None) and (kf[i][j] is None or values[j][Cd[i, j]] == kf[i][j])
                                      for i in range(0, N_GRID, 7) for j in range(11))
        pos = {k: i for i, k in enumerate(kf)}
        twin_ok = all((k[:3] + (not k[3],) + k[4:]) in pos for k in kf)
        tw = Cd.copy()
        tw[:, 3] = 1 - tw[:, 3]
        twin_ok &= all(int(np.flatnonzero((Cd == tw[i]).all(axis=1))[0]) == pos[kf[i][:3] + (not kf[i][3],) + kf[i][4:]]
                       for i in range(0, N_GRID, 257))
        rows = [pos[tuple(SPEC_DEFAULT.values())]] + sorted(int(i) for i in rng.choice(N_GRID, size=24, replace=False))
        nb_ok = True
        nbn = []
        for i in rows:
            a_ = sorted(int(x) for x in CA.neighbours(Cd, C.DIMS, 3, i))
            b_ = _nb_brute(kf, kinds, values, i, 3)
            nb_ok &= a_ == b_
            nbn.append(len(a_))
        _p('    the rule\'s reader (calib_analyze): codes = the DIMS values, -1 exactly where a dimension is None, the '
           'direction is dimension inv: %s; every row has its direction twin in the file: %s; neighbours of the default '
           'row and of 24 random rows = the neighbours as CALIB_SPEC.md words them (default row: %d; others %d .. %d): %s'
           % (code_ok, twin_ok, nbn[0], min(nbn[1:]), max(nbn[1:]), nb_ok))
        ok &= code_ok and twin_ok and nb_ok and nbn[0] == 12
    _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 2. the default rows against the saved results
# ---------------------------------------------------------------------------------------------
def _one(pair, tf, p, *extra):
    cmd = [sys.executable, '-I', os.path.join(W, 'calib_xpw23.py'), '--one', pair, tf, json.dumps(p)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _json_ref(sv, cols):
    """A saved run of out/inv_xpw23_*.json as python values (its writer stores NaN as null, inf as 'inf')."""
    ref = {}
    for k in cols:
        v = sv[k]
        ref[k] = float('nan') if v is None else (float(v) if isinstance(v, str) else v)
    return ref


def _summary_cols():
    Pp = xpw23.prepare('XAU', '240', {})
    return [k for k in xpw23.summary(Pp, xpw23.simulate(Pp, {})) if k not in TEXT]


def test_2_default_rows():
    """(2) The default row, and the same row with inv true, equal the saved default results of the module
    with the same path and cost (out/inv_xpw23_<PAIR>_<TF>.json, runs normal/on/mag/ours and
    inverted/on/mag/ours): through the command line on BTC 60 and XAU 240; through calib_xpw23.one on every
    saved run of all 14 cells; and the default rows of the sweep itself equal the saved runs and xpw23.run."""
    ok = True
    sc = _summary_cols()
    dp = dict(SPEC_DEFAULT)
    # ---- (a) the command line, BTC 60 and XAU 240
    for pair, tf in (('BTC', '60'), ('XAU', '240')):
        J = json.load(open(os.path.join(OUT, 'inv_xpw23_%s_%s.json' % (pair, tf))))
        cases = (
            ('normal/on/mag/ours', dp, ()),
            ('inverted/on/mag/ours', dict(dp, inv=True), ()),
            ('normal/off/mag/ours', dict(dp, fgfOn=False), ()),
            ('inverted/off/mag/ours', dict(dp, fgfOn=False, inv=True), ()),
            ('normal/on/tv/script', dp, ('--path', 'tv', '--cost', 'tv')),
            ('inverted/on/tv/script', dict(dp, inv=True), ('--path', 'tv', '--cost', 'tv')),
            ('normal/on/mag/script', dp, ('--cost', 'tv')),
            ('inverted/on/tv/ours', dict(dp, inv=True), ('--path', 'tv')),
        )
        bad = []
        n_vals = 0
        first = {}
        for key, p, extra in cases:
            rc, out, err = _one(pair, tf, {'p_' + k: v for k, v in p.items()}, *extra)
            if rc != 0:
                bad.append('%s: exit code %d %s' % (key, rc, err.strip()[-200:]))
                continue
            o = json.loads(out)
            st = o.pop('setting')
            want = (('strategy', 'xpw23'), ('pair', pair), ('tf', tf), ('p', p), ('in_grid', True),
                    ('row', spec_grid().index(tuple(p.values()))), ('halves_rule', 'additive'), ('fixed', FIXED),
                    ('path', 'tv' if '--path' in extra else 'mag'), ('cost', 'tv' if '--cost' in extra else 'ours'))
            if any(st.get(k) != v for k, v in want) or list(o) != ['floor_ok'] + sc:
                bad.append('%s: setting echoed as %r' % (key, st))
            n_vals += _cmp(o, _json_ref(J['runs'][key], sc), sc, key, bad)
            first[key] = o
        d, e = first.get('normal/on/mag/ours'), first.get('inverted/on/mag/ours')
        _p('  %s %-3s command line: the default row = saved run normal/on/mag/ours, with inv true = inverted/on/mag/ours; '
           'also filter off (both directions), --path tv --cost tv = .../tv/script, --cost tv, --path tv: %d runs, %d '
           'values: %s' % (pair, tf, len(cases), n_vals,
                           'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b))))
        if d is not None and e is not None:
            _p('    default row: %d trades, net %+.3f %%, h1r %+.3f %%, h2r %+.3f %%, net_R %+.2f; inv true: %d trades, net '
               '%+.3f %%, h1r %+.3f %%, h2r %+.3f %%, net_R %+.2f'
               % (d['trades'], d['net_pct'], d['h1r_pct'], d['h2r_pct'], d['net_R'], e['trades'], e['net_pct'], e['h1r_pct'],
                  e['h2r_pct'], e['net_R']))
        ok &= not bad and n_vals == len(cases) * len(sc)
    # ---- (b) every saved run of all 14 cells through calib_xpw23.one
    tot = dict(cells=0, runs=0, vals=0)
    for pair in PAIRS:
        for tf in TFS:
            J = json.load(open(os.path.join(OUT, 'inv_xpw23_%s_%s.json' % (pair, tf))))
            cache = {}
            bad = []
            n_runs = n_vals = 0
            if not set(sc) <= set(J['runs']['normal/on/mag/ours']):
                bad.append('the saved runs miss fields: %s' % (set(sc) - set(J['runs']['normal/on/mag/ours'])))
            for key, sv in J['runs'].items():
                dname, flt, path, cname = key.split('/')
                p = dict(dp, fgfOn=flt == 'on', inv=dname == 'inverted')
                o = C.one(pair, tf, p, path, 'tv' if cname == 'script' else 'ours', False, cache)
                n_vals += _cmp(o, _json_ref(sv, sc), sc, key, bad)
                n_runs += 1
            for key, sv in J['reference'].items():
                # "Reverse every label" (reverseAll, not a dimension): with the filter off it places the
                # orders of inv true (the Pine header); the label-side counters are mirrored
                _, flt, path, cname = key.split('/')
                if flt != 'off':
                    continue
                o = C.one(pair, tf, dict(dp, fgfOn=False, inv=True), path, 'tv' if cname == 'script' else 'ours', False, cache)
                n_vals += _cmp(_swap_labels(o), _json_ref(sv, sc), sc, key + ' as inv true', bad)
                n_runs += 1
            d = J['runs']['normal/on/mag/ours']
            _p('  %s %-3s: %d saved runs (16 runs; 4 filter-off "Reverse every label" runs = the inv true rows) = '
               'calib_xpw23.one: %d values: %s | saved default mag / ours: %d trades, net %+.3f %%'
               % (pair, tf, n_runs, n_vals, 'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                  d['trades'], d['net_pct']))
            ok &= not bad and n_runs == 20
            tot['cells'] += 1
            tot['runs'] += n_runs
            tot['vals'] += n_vals
            del cache
            _free()
    _p('  %d cells: %d saved runs, %d values compared' % (tot['cells'], tot['runs'], tot['vals']))
    ok &= tot['cells'] == 14
    # ---- (c) the default rows of the sweep = the saved runs = xpw23.run called directly
    S = spec_grid()
    n_cells = 0
    for pair in PAIRS:
        for tf in TFS:
            if os.path.exists(_out_file(pair, tf)):
                df, _ = _cell_df(pair, tf)
                src = 'file'
            elif FILES_ONLY:
                continue
            else:
                df, _ = C.run_cell(pair, tf, workers=3, sig_idx=[0, 1], write=False, verbose=False)
                _free()
                src = '%d rows run here' % len(df)
            kf = _keys(df)
            idx = {k: i for i, k in enumerate(kf)}
            J = json.load(open(os.path.join(OUT, 'inv_xpw23_%s_%s.json' % (pair, tf))))
            bad = []
            n_vals = 0
            rows = {}
            for name, p in (('normal/on/mag/ours', dp), ('inverted/on/mag/ours', dict(dp, inv=True)),
                            ('normal/off/mag/ours', dict(dp, fgfOn=False)), ('inverted/off/mag/ours', dict(dp, fgfOn=False, inv=True))):
                row = df.iloc[idx[tuple(p.values())]]
                n_vals += _cmp(row, _json_ref(J['runs'][name], sc), sc, name + ' saved', bad)
                prep, sim = own_params(p)
                _, s = xpw23.run(pair, tf, dict(prep, **sim))
                n_vals += _cmp(row, s, sc, name + ' xpw23.run', bad)
                if row['floor_ok'] != _own_floor_ok(pair, tf, tuple(p.values())):
                    bad.append('%s floor_ok %r' % (name, row['floor_ok']))
                rows[name] = row
            d, e = rows['normal/on/mag/ours'], rows['inverted/on/mag/ours']
            _p('  %s %-3s (%s): default rows (normal / inverted x filter on / off) = the saved runs .../mag/ours and = '
               'xpw23.run with path mag, cost ours: %d values: %s | default row %d (floor_ok %s): %d trades, net %+.3f %%, '
               'h1r %+.3f %%, h2r %+.3f %%; inv true: net %+.3f %%, h1r %+.3f %%, h2r %+.3f %%'
               % (pair, tf, src, n_vals, 'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                  S.index(tuple(dp.values())), bool(d['floor_ok']), d['trades'], d['net_pct'], d['h1r_pct'], d['h2r_pct'],
                  e['net_pct'], e['h1r_pct'], e['h2r_pct']))
            ok &= not bad and n_vals == 8 * len(sc) and kf.count(tuple(dp.values())) == 1
            n_cells += 1
            _free()
    _p('  %d cells: the default rows of the sweep equal the saved default results and xpw23.run called directly' % n_cells)
    return ok and n_cells > 0


# ---------------------------------------------------------------------------------------------
# 3. random rows through --one
# ---------------------------------------------------------------------------------------------
def test_3_one_rows():
    """(3) 30 random rows per cell recomputed one at a time through `calib_xpw23.py --one` (a new process
    each, the row's p_ columns as its JSON) equal the sweep rows on every result column; the same rows
    through xpw23 called directly with this file's own mapping; --path / --cost are honoured; bad input is
    refused; --off-grid."""
    ok = True
    rng = np.random.default_rng(31)
    S = spec_grid()
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        rc_cols = _rescols(df)
        sc = _sumcols(df)
        keys = _keys(df)
        pick = sorted(int(i) for i in rng.choice(len(df), size=30, replace=False))
        ref = _Ref(pair, tf)
        med = _median(pair, tf)[0]
        bad = []
        n_vals = n_run = n_tr = 0
        cover = {n: set() for n in SPEC_DIMS}
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
            m = st.pop('median_atr_pct', None)
            if st != {'strategy': 'xpw23', 'pair': pair, 'tf': tf, 'path': 'mag', 'cost': 'ours', 'p': p, 'in_grid': True,
                      'row': i, 'halves_rule': 'additive', 'fixed': FIXED, 'floor_pct': T_FLOOR[pair]} \
                    or m is None or abs(m - med) > 1e-9 * med or S[i] != keys[i]:
                bad.append('row %d: setting echoed as %r' % (i, st))
            if list(o) != rc_cols:
                bad.append('row %d: fields %r' % (i, list(o)))
                continue
            n_vals += _cmp(row, o, rc_cols, 'row %d --one' % i, bad)
            s, t_ok = ref.row(p)
            if not t_ok:
                bad.append('row %d: text fields of xpw23.summary' % i)
            n_run += _cmp(row, s, sc, 'row %d xpw23' % i, bad)
            n_tr += int(row['trades'])
        dt = time.time() - t0
        cov = all(len(cover[n] - {None}) >= 2 for n in SPEC_DIMS)
        _p('  %s %s (%s): 30 random rows, each in its own `--one` process: %d result values, and through xpw23 called '
           'directly with the mapping written here: %d values (%d trades): %s; at least two values of every dimension '
           'among them: %s (%.1fs)' % (pair, tf, src, n_vals, n_run, n_tr,
                                     'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                                     cov, dt))
        ok &= not bad and n_vals == 30 * len(rc_cols) and n_run == 30 * len(sc) and cov
        # --path / --cost
        bad = []
        n = 0
        moved = {'path': 0, 'cost': 0}
        sub = [pick[j] for j in (0, 14, 29)]
        for i in sub:
            row = df.iloc[i]
            p = dict(zip(SPEC_DIMS, keys[i]))
            for extra, path, cost in ((('--path', 'tv', '--cost', 'tv'), 'tv', 'tv'), (('--path', 'tv'), 'tv', 'ours'),
                                      (('--cost', 'stress'), 'mag', 'stress'), (('--path', 'mag', '--cost', 'ours'), 'mag', 'ours')):
                rc, out, err = _one(pair, tf, p, *extra)
                if rc != 0:
                    bad.append('row %d %s: exit code %d' % (i, ' '.join(extra), rc))
                    continue
                o = json.loads(out)
                st = o['setting']
                if (st['path'], st['cost'], st['row'], st['in_grid']) != (path, cost, i, True):
                    bad.append('row %d %s: echoed %r' % (i, ' '.join(extra), st))
                s, t_ok = ref.row(p, path, cost)
                n += _cmp(o, s, sc, 'row %d %s' % (i, ' '.join(extra)), bad)
                if (path, cost) == ('mag', 'ours'):
                    n += _cmp(o, row, rc_cols, 'row %d explicit mag / ours' % i, bad)
                elif (path, cost) == ('tv', 'ours'):
                    moved['path'] += not all(_same(o[k], row[k]) for k in sc)
                elif (path, cost) == ('mag', 'stress'):
                    moved['cost'] += not all(_same(o[k], row[k]) for k in sc)
                    if not (o['costs'] > row['costs'] and o['trades'] == row['trades'] and o['net_pct'] < row['net_pct']):
                        bad.append('row %d: stressed costs are not higher' % i)
        _p('  %s %s: 3 rows x (--path tv --cost tv | --path tv | --cost stress | --path mag --cost ours) = xpw23 with '
           'that path and cost: %d values: %s; rows whose result moves with --path tv: %d of 3, with --cost stress '
           '(same trades, higher costs): %d of 3'
           % (pair, tf, n, 'all equal' if not bad else '; '.join(b for b in bad if b), moved['path'], moved['cost']))
        ok &= not bad and moved['cost'] == 3
        ref.drop()
        _free()
    # bad input
    pair, tf = CELLS[0]
    p = dict(SPEC_DEFAULT)
    cases = (('unknown dimension', dict(p, riskPct=2.0), ()),
             ('value not in the grid', dict(p, slAtrMult=2.0), ()),
             ('label action not in the grid', dict(p, actInf='enter opposite'), ()),
             ('missing used dimension', {k: v for k, v in p.items() if k != 'inv'}, ()),
             ('trail on without trActAtr', dict(p, trActAtr=None), ()),
             ('a trail that can never arm', dict(p, trActAtr=3.0), ()),
             ('wrong type', dict(p, fgfOn='yes'), ()),
             ('unknown label action', dict(p, actInf='close'), ('--off-grid',)),
             ('below the Pine minimum', dict(p, slAtrMult=-1.0), ('--off-grid',)),
             ('maxOpen above the Pine maximum', dict(p, maxOpen=101), ('--off-grid',)),
             ('--cost free', p, ('--cost', 'free')),
             ('not an object', [1, 2], ()))
    res = []
    for name, q, extra in cases:
        rc, out, err = _one(pair, tf, q, *extra)
        res.append((name, rc, out.strip() == '' and 'calib_xpw23.py --one' in err))
    ref = _Ref(pair, tf)
    q = dict(p, slAtrMult=2.0, tpRMult=3.0, trActAtr=2.0, trDistAtr=1.0, timeStop=12, maxOpen=5, actInf='enter opposite')
    rc, out, err = _one(pair, tf, q, '--off-grid')
    og = rc == 0 and json.loads(out)['setting']['in_grid'] is False and json.loads(out)['setting']['row'] is None
    if og:
        o = json.loads(out)
        s, _ = ref.row(q)
        og = all(_same(o[k], s[k]) for k in s) and o['floor_ok'] == (1.0 * _median(pair, tf)[0] >= T_FLOOR[pair])
    # a trail that can never arm, off the grid = its trail-off row
    q = dict(p, trActAtr=3.0)
    rc, out, err = _one(pair, tf, q, '--off-grid')
    rc2, out2, _ = _one(pair, tf, dict(p, trailOn=False, trActAtr=None, trDistAtr=None))
    og2 = rc == 0 and rc2 == 0
    if og2:
        o, o2 = json.loads(out), json.loads(out2)
        s, _ = ref.row(q)
        og2 = (o['setting']['in_grid'] is False and o['setting']['p'] == q and o2['setting']['in_grid'] is True
               and all(_same(o[k], s[k]) for k in s) and all(_same(o[k], o2[k]) for k in s) and o2['exit_trail'] == 0)
    ref.drop()
    _free()
    b_ok = all(rc == 2 and e for _, rc, e in res) and og and og2
    _p('  bad input is refused (exit code 2, nothing on stdout): %s; --off-grid runs a setting outside the grid (stop '
       '2.0, target 3.0 R, trail 2.0 / 1.0, time stop 12, 5 entries, Info "enter opposite") = xpw23: %s; --off-grid '
       'with the default trail and activation 3.0 (it can never arm) = xpw23, and = the grid\'s trail-off row: %s'
       % (', '.join('%s -> %d' % (n, rc) for n, rc, _ in res), og, og2))
    return ok and b_ok


# ---------------------------------------------------------------------------------------------
# 4. worker count
# ---------------------------------------------------------------------------------------------
def test_4_workers():
    """(4) XAU 240, the full grid with 1 worker and with 3 workers (files in calib_tmp_xpw23/w1 and w3, not
    out/): every row and column identical, and the two files byte for byte; equal to out/ when it exists.
    With 1 worker everything runs in this process: xpw23.prepare is called once per signal setting,
    xpw.xpw_signals once per label setting, xpw23.simulate once per row."""
    d1 = os.path.join(TMP, 'w1')
    d3 = os.path.join(TMP, 'w3')
    calls = dict(prepare=0, simulate=0, summary=0, signals=0, fgf=0)
    o_prep, o_sim, o_sum, o_sig, o_fgf = xpw23.prepare, xpw23.simulate, xpw23.summary, xpw.xpw_signals, fgf.fgf_permissions
    seen_prep = []

    def c_prep(*a, **k):
        calls['prepare'] += 1
        seen_prep.append(tuple(sorted(a[2].items())))
        return o_prep(*a, **k)

    def c_sim(*a, **k):
        calls['simulate'] += 1
        return o_sim(*a, **k)

    def c_sum(*a, **k):
        calls['summary'] += 1
        return o_sum(*a, **k)

    def c_sig(*a, **k):
        calls['signals'] += 1
        return o_sig(*a, **k)

    def c_fgf(*a, **k):
        calls['fgf'] += 1
        return o_fgf(*a, **k)

    _free()
    xpw23.prepare, xpw23.simulate, xpw23.summary, xpw.xpw_signals, fgf.fgf_permissions = c_prep, c_sim, c_sum, c_sig, c_fgf
    try:
        a, ia = C.run_cell('XAU', '240', workers=1, out_dir=d1, verbose=False)
    finally:
        xpw23.prepare, xpw23.simulate, xpw23.summary, xpw.xpw_signals, fgf.fgf_permissions = o_prep, o_sim, o_sum, o_sig, o_fgf
    _free()
    b, ib = C.run_cell('XAU', '240', workers=3, out_dir=d3, verbose=False)
    _free()
    f1 = os.path.join(d1, 'calib_xpw23_XAU_240.parquet')
    f3 = os.path.join(d3, 'calib_xpw23_XAU_240.parquet')
    fa = pd.read_parquet(f1)
    fb = pd.read_parquet(f3)
    same = fa.equals(fb) and a.equals(b) and a.equals(fa) and len(fa) == N_GRID and list(fa.columns) == list(fb.columns) \
        and all(fa[c].dtype == fb[c].dtype for c in fa.columns)
    byt = _sha(f1) == _sha(f3)
    dims = json.load(open(os.path.join(d1, 'calib_xpw23_dims.json'))) == C.DIMS == json.load(open(os.path.join(d3, 'calib_xpw23_dims.json')))
    once = (calls == dict(prepare=18, simulate=N_GRID + 1, summary=N_GRID + 1, signals=9, fgf=9) and len(set(seen_prep)) == 18
            and ia['prepares'] == 18 == ib['prepares'] and ia['signal_inputs'] == 9 == ib['signal_inputs'])
    _p('  XAU 240: %d rows x %d columns; 1 worker %.1fs (runs %.1fs), 3 workers %.1fs (runs %.1fs, speed-up x%.2f): '
       'frames %s, files %s (sha256 %s), dims.json = DIMS: %s'
       % (len(fa), len(fa.columns), ia['t_total'], ia['t_run'], ib['t_total'], ib['t_run'], ia['t_run'] / ib['t_run'],
          'identical' if same else 'DIFFERENT', 'byte for byte equal' if byt else 'DIFFERENT bytes', _sha(f3)[:16], dims))
    _p('  the 1-worker run called xpw23.prepare %d times (18 different signal settings), xpw.xpw_signals %d times (9 '
       'label settings), fgf.fgf_permissions %d times (the 9 filter-on prepares), xpw23.simulate %d and xpw23.summary '
       '%d times (%d rows + 1 to load the kernel): signals prepared once per signal setting and reused for all its '
       'exit settings: %s' % (calls['prepare'], calls['signals'], calls['fgf'], calls['simulate'], calls['summary'], N_GRID, once))
    ok = same and byt and dims and once
    fo = _out_file('XAU', '240')
    if os.path.exists(fo):
        fo_df = pd.read_parquet(fo)
        again = fo_df.equals(fb)
        _p('  out/calib_xpw23_XAU_240.parquet (the production run) equals this re-run: %s (bytes %s)'
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


def _status_mb(key):
    with open('/proc/self/status') as f:
        for line in f:
            if line.startswith(key):
                return int(line.split()[1]) / 1024.0
    return float('nan')


def _btc1_child():
    """The measured part of test 5, in a process of its own (so that its memory is that of a BTC 1 run and
    nothing else): prints one line RESULT <json>."""
    load0 = os.getloadavg()[0]
    cell = C.prepare_cell('BTC', '1')
    rss_prep, hwm_prep = _status_mb('VmRSS:'), _status_mb('VmHWM:')
    lab = {si: int(cell['P'][si]['nLong'].sum() + cell['P'][si]['nShort'].sum()) for si in cell['idx']}
    trd = {si: int(cell['P'][si]['nLong'][cell['P'][si]['buyOk']].sum() + cell['P'][si]['nShort'][cell['P'][si]['sellOk']].sum())
           for si in cell['idx']}
    uniq = {k: len(set(id(cell['P'][si][k]) for si in cell['idx'])) for k in C._ARRAYS}
    order = sorted(range(0, 18, 2), key=lambda si: lab[si])          # label settings, by entry labels
    names = {order[-1]: 'busiest', order[4]: 'middle', order[0]: 'quietest'}
    passes = []
    keep = {}
    for si in (order[-1], order[4], order[0]):
        res, info = C.run_prepared(cell, workers=3, sig_idx=[si, si + 1])
        keep[si] = res
        passes.append(dict(name=names[si], sig=si, labels=lab[si], gated=[trd[si], trd[si + 1]], default=si == 0,
                           setting=[C.SIGNALS[si]['actDL_actDS'], C.SIGNALS[si]['actInf']], settings=info['settings'],
                           t_run=info['t_run'], busy=info['busy'], cpu=info['cpu']))
    si = order[0]
    res1, info1 = C.run_prepared(cell, workers=1, sig_idx=[si, si + 1])
    same = all(len(res1[k]) == len(keep[si][k]) and all(_same(x, y) for a, b in zip(res1[k], keep[si][k]) for x, y in zip(a, b))
               for k in (si, si + 1))
    out = dict(bars=cell['bars'], n_sub=cell['n_sub'], t_prep=cell['t_prep'], cpu_prep=cell['cpu_prep'], t_sig=cell['t_sig'],
               t_sub=cell['t_sub'], t_jit=cell['t_jit'], labels=[lab[si] for si in range(0, 18, 2)], uniq=uniq, passes=passes,
               one_worker=dict(sig=si, t_run=info1['t_run'], cpu=info1['cpu'], settings=info1['settings'], same=bool(same)),
               rss_after_prep_mb=rss_prep, hwm_after_prep_mb=hwm_prep, rss_end_mb=_status_mb('VmRSS:'),
               hwm_end_mb=_status_mb('VmHWM:'), median_atr_pct=cell['floor']['median_atr_pct'],
               dist_ok=cell['floor']['dist_ok'], load0=load0, load1=os.getloadavg()[0])
    print('RESULT ' + json.dumps(out), flush=True)
    return 0


def test_5_timing_btc1():
    """(5) BTC 1 (the largest cell), in a fresh process: the real preparation of all 18 signal settings, then
    one pass = the 1,800 settings of one label setting (filter off + on) with 3 workers, for the busiest
    (the default), a middle and the quietest label setting; extrapolated to the 9 label settings. The full
    grid must stay under 45 min, and the process with its 3 workers under 4 GB."""
    child = subprocess.Popen([sys.executable, '-I', os.path.abspath(__file__), '--child-btc1'], stdout=subprocess.PIPE, text=True)
    watch = subprocess.Popen([sys.executable, '-I', '-c', _MEM_CODE, str(child.pid)], stdout=subprocess.PIPE, text=True)
    out = child.communicate()[0]
    time.sleep(0.6)
    watch.terminate()
    samples = [tuple(int(v) for v in line.split()) for line in watch.communicate()[0].splitlines() if len(line.split()) == 4]
    line = [x for x in out.splitlines() if x.startswith('RESULT ')]
    if child.returncode != 0 or not line:
        _p('  the BTC 1 process failed (exit code %s): %s' % (child.returncode, out[-600:]))
        return False
    r = json.loads(line[0][7:])
    ps = r['passes']
    _p('  BTC 1: %d chart bars, %d 1-minute bars; all 18 signal settings prepared in %.1fs wall / %.1fs CPU (signals '
       '%.1fs, sub-bars + ATR %.1fs, kernel %.1fs); entry labels of the 9 label settings: %s; distinct arrays kept for '
       'the 18 prepared inputs: %s'
       % (r['bars'], r['n_sub'], r['t_prep'], r['cpu_prep'], r['t_sig'], r['t_sub'], r['t_jit'], r['labels'],
          ', '.join('%s %d' % kv for kv in r['uniq'].items())))
    for q in ps:
        _p('  pass %-8s (actDL_actDS %s, actInf %s%s; %d entry labels, %d / %d after the filter off / on): %d settings, 3 '
           'workers %.1fs (%.4fs per setting per worker, %.4fs CPU per setting; workers busy %.0f%%)'
           % (q['name'], q['setting'][0], q['setting'][1], ' = the default' if q['default'] else '', q['labels'],
              q['gated'][0], q['gated'][1], q['settings'], q['t_run'], q['busy'] / q['settings'], q['cpu'] / q['settings'],
              100.0 * q['busy'] / (3 * q['t_run'])))
    o1 = r['one_worker']
    q0 = [q for q in ps if q['sig'] == o1['sig']][0]
    _p('  pass quietest with 1 worker: %.1fs (%.4fs per setting); speed-up of 3 workers x%.2f; rows identical to the '
       '3-worker pass: %s' % (o1['t_run'], o1['t_run'] / o1['settings'], o1['t_run'] / q0['t_run'], o1['same']))
    # the 9 label settings: pass time interpolated on the number of entry labels between the three measured
    xs = [q['labels'] for q in sorted(ps, key=lambda q: q['labels'])]
    tw = [q['t_run'] for q in sorted(ps, key=lambda q: q['labels'])]
    tc = [q['cpu'] / 3.0 for q in sorted(ps, key=lambda q: q['labels'])]
    est = r['t_prep'] + float(sum(np.interp(n, xs, tw) for n in r['labels']))
    cpu = r['cpu_prep'] + float(sum(np.interp(n, xs, tc) for n in r['labels']))
    hi = r['t_prep'] + 9 * max(tw)
    _p('  full grid BTC 1 with 3 workers = preparation + 9 passes (pass time interpolated on the entry labels): %.1fs = '
       '%.1f min at the present load; %.1f min if every pass were as slow as the slowest; by CPU time (a free CPU per '
       'worker): %.1f min; limit 45 min; load average %.2f -> %.2f (other jobs share the 4 CPUs)'
       % (est, est / 60.0, hi / 60.0, cpu / 60.0, r['load0'], r['load1']))
    fl = (abs(r['median_atr_pct'] - _median('BTC', '1')[0]) <= 1e-9 * r['median_atr_pct']
          and r['dist_ok'] == {'0.75': False, '1.5': False, '3': True})
    # memory: the process holds every prepared input, the workers are forked from it (copy-on-write)
    s3 = [x for x in samples if x[0] >= 3]
    mem_ok = bool(samples) and bool(s3)
    if mem_ok:
        top = max(samples, key=lambda x: x[1])
        top3 = max(s3, key=lambda x: x[1])
        mem_ok = top[1] / 1024.0 < MEM_LIMIT_MB and r['hwm_end_mb'] < MEM_LIMIT_MB
        _p('  memory of the BTC 1 process and its workers, sampled twice a second over the whole run (%d samples, %d with '
           '3 workers alive): the most they hold together (sum of PSS) %.0f MB (with %d workers alive); during the '
           '3-worker passes %.0f MB (the process %.0f MB RSS, a worker\'s own private memory at most %.0f MB); peak RSS '
           'of the process %.0f MB (reached in the preparation: %.0f MB by its end, %.0f MB held after it); limit %d MB: %s'
           % (len(samples), len(s3), top[1] / 1024.0, top[0], top3[1] / 1024.0, top3[2] / 1024.0,
              max(x[3] for x in s3) / 1024.0, r['hwm_end_mb'], r['hwm_after_prep_mb'], r['rss_after_prep_mb'], MEM_LIMIT_MB, mem_ok))
    else:
        _p('  memory: no sample of the process with 3 workers alive (/proc/<pid>/smaps_rollup not readable?)')
    _p('  floor of the cell as the run measured it: median ATR(14) / close %.4f %%, trDistAtr 3.0 only in the pool: %s'
       % (r['median_atr_pct'], fl))
    return bool(o1['same']) and hi < 45 * 60.0 and est < 45 * 60.0 and mem_ok and fl


# ---------------------------------------------------------------------------------------------
# 6. what every row must satisfy
# ---------------------------------------------------------------------------------------------
def test_6_row_consistency():
    """Rows hold what they claim, whatever the data: trade counts add up, net = final equity = the sum of the
    fair halves (fixed quantity), a switch that is off leaves no trace (no trail / target / time-stop exits,
    nothing blocked with the filter off, no close_all without an "exit only" row, no pending orders), the
    label counts belong to the label setting, floor_ok is the rule, and every dimension changes results."""
    ok = True
    live_all = {}
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        K = _keys(df)
        ex = [c for c in df.columns if c.startswith('exit_')]
        tr = df['trades']
        xo = ((df['p_actDL_actDS'] == 'exit only') | (df['p_actInf'] == 'exit only')).to_numpy(bool)
        fon = df['p_fgfOn'].to_numpy(bool)
        ton = df['p_trailOn'].to_numpy(bool)
        lab = df.groupby(['p_actDL_actDS', 'p_actInf'])[['labels_long', 'labels_short', 'both_cancel_bars', 'raw_long', 'raw_short']].nunique()
        blk = df.groupby(['p_actDL_actDS', 'p_actInf', 'p_fgfOn'])[['blocked_long', 'blocked_short']].nunique()
        pend = [c for c in df.columns if c.startswith('pend_')]
        chk = {
            'trades = long + short': (tr == df['long'] + df['short']).all(),
            'trades = h1_trades + h2_trades': (tr == df['h1_trades'] + df['h2_trades']).all(),
            'trades = sum of the 7 exit kinds': len(ex) == 7 and (tr == df[ex].sum(axis=1)).all(),
            'trades = placed = n_R (Signal tick: every order fills; every trade has a stop)': ((tr == df['placed']) & (tr == df['n_R'])).all(),
            'net_pct = (final_equity - 10000) / 10000': ((df['final_equity'] - INIT) / INIT * 100 == df['net_pct']).all(),
            'half1_pct + half2_pct = net_pct': np.allclose(df['half1_pct'] + df['half2_pct'], df['net_pct'], rtol=0, atol=1e-9),
            'h1r_pct + h2r_pct = net_pct (fixed quantity: the fair halves are sums)': np.allclose(df['h1r_pct'] + df['h2r_pct'], df['net_pct'], rtol=0, atol=1e-8),
            'h1_R + h2_R = net_R': np.allclose(df['h1_R'] + df['h2_R'], df['net_R'], rtol=1e-9, atol=1e-8),
            'window': ((df['start'] == WINDOWS[pair][0]) & (df['end'] == WINDOWS[pair][1])).all() and df['bars'].nunique() == 1,
            'trail off: no trail exit': (df.loc[~ton, 'exit_trail'] == 0).all(),
            'target 0: no tp exit': (df.loc[df['p_tpRMult'] == 0.0, 'exit_tp'] == 0).all(),
            'time stop 0: no time exit': (df.loc[df['p_timeStop'] == 0, 'exit_time'] == 0).all(),
            'no "exit only" row: no close_all': ((df.loc[~xo, 'exit_close_all'] == 0) & (df.loc[~xo, 'close_all_bars'] == 0)).all(),
            'filter off: nothing blocked': (df.loc[~fon, ['blocked_long', 'blocked_short']] == 0).all().all(),
            'blocked <= raw': ((df['blocked_long'] <= df['raw_long']) & (df['blocked_short'] <= df['raw_short'])).all(),
            'raw <= labels (candles with a signal <= entry labels)': ((df['raw_long'] <= df['labels_long']) & (df['raw_short'] <= df['labels_short'])).all(),
            'label counts and raw signals depend on the label setting only': (lab == 1).all().all() and len(lab) == 9,
            'blocked signals depend on the label setting and the filter only': (blk == 1).all().all() and len(blk) == 18,
            'Signal tick: no pending orders': len(pend) >= 7 and (df[pend] == 0).all().all(),
            'no quantity floors to zero': (df['skipped_qty'] == 0).all(),
            'placed + skipped_room <= labels of the gated candles': (df['placed'] + df['skipped_room'] <= df['labels_long'] + df['labels_short']).all(),
            'max_open <= maxOpen unless a reversal candle placed more (reverse_over_room)': ((df['max_open'] <= df['p_maxOpen']) | (df['reverse_over_room'] > 0)).all(),
            'pf / win NaN only without trades': ((df['pf'].isna() == (tr == 0)) & (df['win_pct'].isna() == (tr == 0))).all(),
            'costs > 0 with trades': ((df['costs'] > 0) == (tr > 0)).all(),
            'money finite': np.isfinite(df[['h1r_pct', 'h2r_pct', 'net_pct', 'max_dd_pct', 'net_R', 'h1_R', 'h2_R', 'final_equity']].to_numpy()).all(),
            'max_dd >= 0': (df['max_dd_pct'] >= 0).all(),
            'zero_length <= exit_end (a market entry is closed on its own candle only by the window end)': (df['zero_length'] <= df['exit_end']).all(),
            'floor_ok = trail off or trDistAtr x median >= the floor': df['floor_ok'].tolist() == [_own_floor_ok(pair, tf, k) for k in K],
        }
        failed = [k for k, v in chk.items() if not bool(v)]
        # every dimension changes results: groups of rows that differ only in that dimension
        sc = _sumcols(df)
        sig = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
        joint = (('actDL_actDS', ['actDL_actDS']), ('actInf', ['actInf']), ('fgfOn', ['fgfOn']), ('inv', ['inv']),
                 ('slAtrMult', ['slAtrMult']), ('tpRMult', ['tpRMult']),
                 ('trail (trailOn, trActAtr, trDistAtr)', ['trailOn', 'trActAtr', 'trDistAtr']),
                 ('trActAtr alone (trail on)', ['trActAtr']), ('trDistAtr alone (trail on)', ['trDistAtr']),
                 ('timeStop', ['timeStop']), ('maxOpen', ['maxOpen']))
        parts = []
        for name, cols in joint:
            others = [j for j, n in enumerate(SPEC_DIMS) if n not in cols]
            sel = ton if 'alone' in name else np.ones(len(df), bool)
            gkey = [repr(tuple(k[j] for j in others)) for k, m in zip(K, sel) if m]      # None is a value here
            g = pd.Series(sig[sel]).groupby(gkey).agg(['size', 'nunique'])
            g = g[g['size'] > 1]
            n_all = int((g['nunique'] == g['size']).sum())
            n_any = int((g['nunique'] > 1).sum())
            live_all[name] = live_all.get(name, 0) + n_any
            parts.append('%s %d / %d / %d' % (name, n_all, n_any, len(g)))
        # a setting never has the result of its direction twin
        pos = {k: i for i, k in enumerate(K)}
        twin = np.array([pos[k[:3] + (not k[3],) + k[4:]] for k in K])
        same_twin = int(((sig == sig[twin]) & (tr.to_numpy() > 0)).sum())
        mirror = bool(((df['raw_long'].to_numpy() == df['raw_long'].to_numpy()[twin]) & (df['blocked_long'].to_numpy() == df['blocked_long'].to_numpy()[twin])
                       & (df['labels_short'].to_numpy() == df['labels_short'].to_numpy()[twin])).all())
        n_distinct = len(np.unique(sig))
        # trail-on rows that repeat their trail-off row (same other dimensions), by (stop, target, activation, distance)
        off_row = np.array([pos[k[:6] + (False, None, None) + k[9:]] for k in K])
        rep = {}
        for i in np.flatnonzero(ton):
            g = K[i][4:6] + K[i][7:9]
            a_, b_ = rep.get(g, (0, 0))
            rep[g] = (a_ + int(sig[i] == sig[off_row[i]]), b_ + 1)
        full_rep = sorted(g for g, (a_, b_) in rep.items() if a_ == b_)
        some_rep = sum(a_ for g, (a_, b_) in rep.items() if g not in full_rep)
        dup_ok = (1.5, 1.0, 1.0, 3.0) in full_rep and rep[(1.5, 1.0, 1.0, 3.0)][1] == 216
        fl = df['floor_ok'].to_numpy(bool)
        el = ((df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).to_numpy(bool)
        cand = ((df['h1r_pct'] > 0) & (df['h2r_pct'] > 0)).to_numpy(bool) & el
        _p('  %s %s (%s): %d rows, %d checks: %s' % (pair, tf, src, len(df), len(chk),
                                                     'all hold' if not failed else 'FAILED: ' + '; '.join(failed)))
        _p('    groups differing only in one dimension (all results distinct / some distinct / groups): %s' % '; '.join(parts))
        _p('    trades %d .. %d (median %d); distinct results %d of %d rows; rows with trades that equal their direction '
           'twin (inv flipped): %d; the twin has the same label-side counters (raw, blocked, labels: decided before the '
           'inversion): %s; rows in the pool (floor_ok) %d; rows with >= 30 trades in each half: %d (%d in the pool), of '
           'which positive in both fair halves: %d (%d in the pool)'
           % (tr.min(), tr.max(), int(tr.median()), n_distinct, len(df), same_twin, mirror, int(fl.sum()), int(el.sum()),
              int((el & fl).sum()), int(cand.sum()), int((cand & fl).sum())))
        _p('    a trail that is on but cannot act: stop 1.5 ATR, target 1.0 R, trail 1.0 / 3.0 (its stop, best - 3.0 ATR, '
           'stays below the stop loss until the target at +1.5 ATR fills; not listed in section 9): all %d such rows '
           'repeat their trail-off row: %s; (stop, target, activation, distance) groups whose rows all repeat their '
           'trail-off row: %s; other trail-on rows that happen to equal their trail-off row: %d of %d'
           % (rep[(1.5, 1.0, 1.0, 3.0)][1], dup_ok, full_rep, some_rep, int(ton.sum()) - sum(rep[g][1] for g in full_rep)))
        ok &= not failed and same_twin == 0 and mirror and dup_ok
    dead = [k for k, v in live_all.items() if v == 0]
    _p('  every dimension changes results in at least one group over the cells: %s' % ('yes' if not dead else 'NO: %s' % dead))
    return ok and not dead


# ---------------------------------------------------------------------------------------------
# 7. every row
# ---------------------------------------------------------------------------------------------
def _groups(keys):
    """The rows of a file grouped by their xpw23.prepare params (this file's own mapping), the two filter
    states of a label setting next to each other: [(prep, [(row, simulate params)])]."""
    groups = {}
    for i, k in enumerate(keys):
        prep, sim = own_params(dict(zip(SPEC_DIMS, k)))
        gk = (prep['actDL'], prep['actDS'], prep['actInf'], prep['fgfOn'])
        groups.setdefault(gk, (prep, []))[1].append((i, sim))
    return [groups[gk] for gk in sorted(groups)]


def _recompute(pair, tf, df, pick=None, rng=None):
    """Rows of a cell's file recomputed with xpw23 called directly: every row, or `pick` random rows of
    every signal setting. Returns (signal settings, rows, values, rows that differ, fields ok)."""
    sc = _sumcols(df)
    keys = _keys(df)
    vals = [df[c].tolist() for c in sc]
    groups = _groups(keys)
    ref = _Ref(pair, tf)
    n_rows = n_vals = 0
    bad_rows = []
    fields_ok = True
    for g, (prep, items) in enumerate(groups):
        Pp = ref.prepared(prep)
        if pick is not None:
            items = [items[j] for j in sorted(int(x) for x in rng.choice(len(items), size=min(pick, len(items)), replace=False))]
        for i, sim in items:
            s = xpw23.summary(Pp, xpw23.simulate(Pp, sim))
            if [k for k in s if k not in TEXT] != sc or (s['pair'], s['tf'], s['halves_rule'], s['path'], s['cost']) != (pair, tf, 'additive', 'mag', 'ours'):
                fields_ok = False
                break
            n_rows += 1
            n_vals += len(sc)
            if not all(_same(vals[j][i], s[c]) for j, c in enumerate(sc)):
                bad_rows.append(i)
        ref.drop()
        del Pp
        if g + 1 == len(groups) or groups[g + 1][0]['fgfOn'] is False:
            xpw23.free_caches(deep=False)           # the label setting is done: its signal tables can go
    return len(groups), n_rows, n_vals, bad_rows, fields_ok


def test_7_all_rows():
    """Every row of the cells' files, not a sample: recomputed in this process with xpw23.prepare once per
    signal setting and xpw23.simulate + xpw23.summary per row, the parameters from this file's own mapping
    (own_params: the complete script defaults with the swept inputs replaced); every summary value must be
    equal. A sample of 30 rows cannot see one stale signal setting or one displaced chunk of rows; this does."""
    ok = True
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        t0 = time.time()
        n_sig, n_rows, n_vals, bad_rows, fields_ok = _recompute(pair, tf, df)
        sc = _sumcols(df)
        c_ok = (fields_ok and not bad_rows and n_sig == 18 and n_rows == len(df) == N_GRID and n_vals == N_GRID * len(sc))
        _p('  %s %s (%s): all %d rows recomputed (xpw23.prepare for each of the %d signal settings, xpw23.simulate + '
           'xpw23.summary per row): %d summary values, %s (%.1fs)'
           % (pair, tf, src, n_rows, n_sig, n_vals,
              'all equal' if c_ok else '%d ROWS DIFFER (first rows %s)%s'
              % (len(bad_rows), bad_rows[:8], '' if fields_ok else '; the summary fields differ'), time.time() - t0))
        ok &= c_ok
        _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 8. every cell that has a file
# ---------------------------------------------------------------------------------------------
def test_8_every_cell():
    """Every cell with a file in out/: the file holds the grid in order with the result columns, floor_ok is
    the rule by this file's own median, and 4 random rows of EVERY signal setting (72 rows per cell)
    recomputed in this process (xpw23.prepare per signal setting, xpw23.simulate + xpw23.summary per row,
    this file's own mapping) equal the file. The other tests read two cells in full and, of the other
    twelve, only the default rows."""
    ok = True
    rng = np.random.default_rng(8)
    S = spec_grid()
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
            med = _median(pair, tf)[0]
            fl_own = [_own_floor_ok(pair, tf, k) for k in keys]
            g_ok = (len(df) == N_GRID and keys == S and all(k in sc for k in SUM_REQUIRED) and meta is not None
                    and all(meta.get(k) == now[k] for k in ('strategy', 'pair', 'tf', 'path', 'cost', 'settings', 'window', 'halves_rule', 'fixed'))
                    and bool(((df['start'] == WINDOWS[pair][0]) & (df['end'] == WINDOWS[pair][1])).all())
                    and df['floor_ok'].tolist() == fl_own and sum(fl_own) == T_POOL.get(tf, N_GRID)
                    and abs(meta['floor']['median_atr_pct'] - med) <= 1e-9 * med)
            cur = meta is not None and all(meta.get(k) == now[k] for k in ('xpw23_sha256', 'xpw_sha256', 'fgf_sha256'))
            n_sig, n_rows, n_vals, bad_rows, fields_ok = _recompute(pair, tf, df, pick=4, rng=rng)
            h = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
            c_ok = g_ok and fields_ok and not bad_rows and n_sig == 18 and n_rows == 72
            tr = df['trades']
            el = (df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)
            _p('  %s %-3s: %d rows, the grid in order, metadata, window: %s; floor_ok = the rule (median %.4f %%, pool %d); '
               'written with the xpw23.py / xpw.py / fgf.py now on disk: %s; %d rows (4 of each of the %d signal settings) '
               'recomputed: %d values, %s; distinct results %d; trades %d .. %d; rows with >= 30 trades in each half: %d (%.1fs)'
               % (pair, tf, len(df), g_ok, med, sum(fl_own), cur, n_rows, n_sig, n_vals,
                  'all equal' if not bad_rows and fields_ok else '%d ROWS DIFFER: %s' % (len(bad_rows), bad_rows[:8]),
                  len(np.unique(h)), tr.min(), tr.max(), int(el.sum()), time.time() - t0))
            ok &= c_ok
            _free()
    if n_cells == 0:
        _p('  no cell has a file in out/ yet: nothing to check')
    else:
        _p('  %d cells checked' % n_cells)
    return ok


# ---------------------------------------------------------------------------------------------
# 9. floor_ok through --one where the floor binds (added by the sceptic)
# ---------------------------------------------------------------------------------------------
def test_9_one_floor():
    """floor_ok printed by `calib_xpw23.py --one` on the two cells where the noise floor binds for one
    distance and not for the next (XAU 5: floor 0.05 %, BTC 5: floor 0.1 %, median about 0.05 / 0.13 %):
    the default trail (0.75 ATR) is below the floor, 1.5 ATR is not, trail off is always in the pool;
    the floor and the median it echoes are the pair's; and when the cell's file exists in out/, the
    whole --one output equals the file's row. On XAU 240 / BTC 240 (tests 2 and 3) every row is above
    the floor, so a --one that always printed floor_ok true, or used the other pair's floor, passed them."""
    ok = True
    S = spec_grid()
    for pair, tf in (('XAU', '5'), ('BTC', '5')):
        med = _median(pair, tf)[0]
        f = _out_file(pair, tf)
        df = pd.read_parquet(f) if os.path.exists(f) else None
        keys = _keys(df) if df is not None else None
        bad = []
        got = []
        n_vals = 0
        for trail, dist, want in ((True, 0.75, False), (True, 1.5, True), (False, None, True)):
            p = dict(SPEC_DEFAULT, trailOn=trail, trActAtr=1.0 if trail else None, trDistAtr=dist)
            rule = (not trail) or (dist * med >= T_FLOOR[pair])
            if rule is not want or (trail and (dist in T_POOL_DISTS[tf]) is not want):
                bad.append('the expectation for %s %s trDistAtr %s is not the rule / the table' % (pair, tf, dist))
            rc, out, err = _one(pair, tf, {'p_' + k: v for k, v in p.items()})
            if rc != 0:
                bad.append('trDistAtr %s: exit code %d %s' % (dist, rc, err.strip()[-200:]))
                continue
            o = json.loads(out)
            st = o.pop('setting')
            got.append('%s -> %s' % ('trail off' if not trail else 'trDistAtr %g' % dist, o['floor_ok']))
            if (o['floor_ok'] is not want or st['floor_pct'] != T_FLOOR[pair] or st['median_atr_pct'] is None
                    or abs(st['median_atr_pct'] - med) > 1e-9 * med or st['row'] != S.index(tuple(p.values()))):
                bad.append('trDistAtr %s: floor_ok %r (want %r), floor %r, median %r'
                           % (dist, o['floor_ok'], want, st['floor_pct'], st['median_atr_pct']))
            if df is not None:
                i = S.index(tuple(p.values()))
                if keys[i] != S[i]:
                    bad.append('the file does not hold the grid in order')
                    continue
                n_vals += _cmp(df.iloc[i], o, _rescols(df), 'row %d --one' % i, bad)
        _p('  %s %s (median %.4f %%, floor %.2f %%): --one prints floor_ok %s%s: %s'
           % (pair, tf, med, T_FLOOR[pair], ', '.join(got),
              '; = the file\'s rows (%d values)' % n_vals if df is not None else ' (no file in out/ yet)',
              'as the rule says' if not bad else 'WRONG: ' + '; '.join(b for b in bad if b)))
        ok &= not bad
    return ok


# ---------------------------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------------------------
def main(argv):
    global CELLS, FILES_ONLY
    args = list(argv)
    if '--child-btc1' in args:
        return _btc1_child()
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
    src = ('xpw23.py', 'xpw.py', 'fgf.py', 'calib_xpw23.py')
    _p('calib_tests_xpw23.py: cells %s; sha256 %s; load average %.2f'
       % (', '.join('%s %s' % c for c in CELLS), ', '.join('%s %s' % (f, _sha(os.path.join(W, f))[:16]) for f in src),
          os.getloadavg()[0]))
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
    _p('sha256 at the end: %s' % ', '.join('%s %s' % (f, _sha(os.path.join(W, f))[:16]) for f in src))
    return 0 if all(res.values()) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
