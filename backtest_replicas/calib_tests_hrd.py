"""calib_tests_hrd.py: tests of calib_hrd.py (CALIB_SPEC.md, strategy "hrd").

Usage: python3 -I calib_tests_hrd.py [name filter ...] [--cells XAU:240,BTC:240] [--files-only]

  test_1_grid             the grid is the full product of the spec (23,328 = 27 x 3 x 2 x 144), keys
                          unique, DIMS / SIGNALS / EXITS consistent, every setting maps to the hrd
                          params the spec means (an independent mapping written here), the unused
                          dimensions cannot change a result, the files hold the grid in order
  test_2_default_rows     the row of the script's default setting equals the saved default result
                          of the module with the same path and cost (out/swah_hrd_<PAIR>_<TF>.parquet,
                          mag / ours, filter on and off), plus every other grid row that has a saved
                          counterpart (48 per cell), the saved Update 1 runs (out/inv_hrd_*.json)
                          and the module run live (hrd.run): all 14 cells
  test_3_one_rows         30 random rows per cell recomputed one at a time through
                          `calib_hrd.py --one` (a new process each) equal the sweep rows (and echo
                          the row number); the same
                          rows through hrd.run with this file's own mapping; --path / --cost; bad input
  test_4_workers          XAU 240: 1 worker vs 3 workers identical (frames and file bytes)
  test_5_timing_btc1      BTC 1: the real preparation and one pass (864 settings of one signal
                          input, 3 workers) extrapolated to the full grid: under 45 minutes; and the
                          memory the parent and its 3 workers hold together during the passes
                          (sum of PSS, sampled): well under the machine's 15 GB
  test_6_row_consistency  what every row must satisfy whatever the data (counts add up, a switch
                          that is off leaves no trace), and every dimension changes results
  test_7_all_rows         EVERY row of the cells' files (not a sample) recomputed in this process:
                          hrd.prepare once per signal setting, hrd.simulate + hrd.summary_fast per
                          row, with this file's own mapping; all summary values equal (added by the
                          sceptic: 30 random rows cannot see one stale signal setting or one
                          displaced chunk of rows)
  test_8_every_cell       every cell that has a file in out/ (all 14 after the production runs): the
                          file holds the grid in order, and 4 random rows of EVERY signal setting
                          (216 rows per cell) recomputed in this process equal the file (added by the
                          sceptic: the other tests read two cells, and of the other twelve only the
                          rows of the default signal setting; on the 240-minute cells maxDivLookback
                          60 and 120 give the same rows, so only other cells can tell them apart)

The cells of tests 3, 6 and 7 (and the files of test 1) are --cells (default XAU 240 and BTC 240): the
file out/calib_hrd_<PAIR>_<TF>.parquet when it exists, else the cell is run here with 3 workers
into calib_tmp_hrd/w3/ (never into out/). Test 2 covers all 14 cells: the file when it exists,
else only the two default signal settings are run in memory (864 rows; --files-only skips those).
Prints PASS / FAIL per test; exit code 1 on a failure.
"""
import gc
import hashlib
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import hrd  # noqa: E402
import calib_hrd as C  # noqa: E402

OUT = os.path.join(W, 'out')
TMP = os.path.join(W, 'calib_tmp_hrd')
TFS = ('1', '5', '15', '30', '60', '120', '240')
INIT = 1_000_000.0
CELLS = [('XAU', '240'), ('BTC', '240')]
FILES_ONLY = False
N_GRID = 23328
MEM_LIMIT_MB = 6000        # test 5: parent + 3 workers on BTC 1, "well under" the machine's 15 GB
SUM_REQUIRED = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
                'exit_sl', 'exit_tp', 'exit_reverse', 'exit_blocked_close', 'exit_time', 'exit_hybrid', 'exit_end',
                'exit_trail')


def _p(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# this file's own reading of the spec (independent of calib_hrd's lists and mappings)
# ---------------------------------------------------------------------------------------------
SPEC_DIMS = ['pivotStrength', 'maxDivLookback', 'divs', 'fgfOn', 'blkClose', 'inv', 'InpSlPct', 'InpTpPct',
             'InpExitCandles', 'useHybridExit', 'trailOn', 'trail']
SPEC_KIND = {'pivotStrength': 'ordinal', 'maxDivLookback': 'ordinal', 'divs': 'categorical', 'fgfOn': 'categorical',
             'blkClose': 'categorical', 'inv': 'categorical', 'InpSlPct': 'ordinal', 'InpTpPct': 'categorical',
             'InpExitCandles': 'ordinal', 'useHybridExit': 'categorical', 'trailOn': 'categorical', 'trail': 'ordinal'}
T_DIVS = {'all': dict(showBullReg=True, showBearReg=True, showBullHid=True, showBearHid=True),
          'regular': dict(showBullReg=True, showBearReg=True, showBullHid=False, showBearHid=False),
          'hidden': dict(showBullReg=False, showBearReg=False, showBullHid=True, showBearHid=True)}
T_TRAIL = {'0.5/0.15': (0.5, 0.15), '1/0.5': (1.0, 0.5), '2/1': (2.0, 1.0)}
# the Pine's input defaults (HRD_Full_Divergence_Strategy_v1_03_FGF.pine) and the replica controls
SCRIPT_DEFAULTS = dict(
    fgfOn=True, blkClose=True, cost='tv', reverse=False, pivotTies='strict', smaNa='skip', start=None, end=None,
    path='tv', pivotStrength=5, maxDivLookback=60, showBullReg=True, showBearReg=True, showBullHid=True,
    showBearHid=True, InpTradeDirection='Both', InpRiskPct=1.0, InpFixedQty=0.01, InpSlPct=2.0, InpTpPct=4.0,
    InpExitCandles=5, useHybridExit=True, hybridSensitivity=1.0, minDecayUpdates=10, trailStepMult=1.0,
    minActivationPts=40, trailOn=False, trailAct=1.0, trailOff=0.5, hrdInv=False)


def spec_grid():
    """CALIB_SPEC.md, HRD: signals 3 x 3 x 3; filter off | on with the blocked close | on without it;
    direction normal | inverted; exits 3 x 2 x 3 x 2 x [trail off | 3 (activation, offset) pairs]."""
    G = []
    for ps in (3, 5, 8):
        for lb in (30, 60, 120):
            for dv in ('all', 'regular', 'hidden'):
                for fgf, blk in ((False, None), (True, True), (True, False)):
                    for inv in (False, True):
                        for sl in (1.0, 2.0, 4.0):
                            for tp in (0.0, 4.0):
                                for ec in (5, 20, 100):
                                    for hyb in (True, False):
                                        for ton, tr in ((False, None), (True, '0.5/0.15'), (True, '1/0.5'),
                                                        (True, '2/1')):
                                            G.append((ps, lb, dv, fgf, blk, inv, sl, tp, ec, hyb, ton, tr))
    return G


def hrd_params(p, path='mag', cost='ours'):
    """A setting (dict over SPEC_DIMS) as the complete hrd param set, written from the spec."""
    q = dict(SCRIPT_DEFAULTS)
    q.update(pivotStrength=p['pivotStrength'], maxDivLookback=p['maxDivLookback'], fgfOn=p['fgfOn'],
             hrdInv=p['inv'], InpSlPct=p['InpSlPct'], InpTpPct=p['InpTpPct'], InpExitCandles=p['InpExitCandles'],
             useHybridExit=p['useHybridExit'], trailOn=p['trailOn'], path=path, cost=cost)
    q.update(T_DIVS[p['divs']])
    if p['fgfOn']:
        q['blkClose'] = p['blkClose']
    if p['trailOn']:
        q['trailAct'], q['trailOff'] = T_TRAIL[p['trail']]
    return q


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


def _sumcols(df):
    return [c for c in df.columns if not c.startswith('p_')]


def _out_file(pair, tf):
    return os.path.join(OUT, 'calib_hrd_%s_%s.parquet' % (pair, tf))


def _fresh(path):
    """A scratch file is used only when it is newer than the runner and the replica."""
    return os.path.exists(path) and os.path.getmtime(path) > max(os.path.getmtime(os.path.join(W, 'calib_hrd.py')),
                                                                 os.path.getmtime(os.path.join(W, 'hrd.py')))


_DF = {}


def _cell_df(pair, tf):
    """(DataFrame, where): out/ when the cell's file exists, else calib_tmp_hrd/w3 (run here if needed)."""
    key = (pair, tf)
    if key not in _DF:
        f = _out_file(pair, tf)
        if os.path.exists(f):
            src = 'out/' + os.path.basename(f)
            if not _fresh(f):
                _p('  note: %s is older than calib_hrd.py or hrd.py' % src)
        else:
            d3 = os.path.join(TMP, 'w3')
            f = os.path.join(d3, 'calib_hrd_%s_%s.parquet' % (pair, tf))
            src = 'calib_tmp_hrd/w3/' + os.path.basename(f)
            if not _fresh(f):
                t0 = time.time()
                C.run_cell(pair, tf, workers=3, out_dir=d3, verbose=False)
                _p('  %s %s has no file in out/: run here with 3 workers into %s (%.1fs)' % (pair, tf, src, time.time() - t0))
                _free()
        _DF[key] = (pd.read_parquet(f), src)
    return _DF[key]


def _free():
    hrd._SIG.clear()
    hrd._PERM.clear()
    hrd._CACHE.clear()
    C._G.clear()
    gc.collect()


def _default_sig_idx():
    return [i for i, s in enumerate(C.SIGNALS)
            if (s['pivotStrength'], s['maxDivLookback'], s['divs']) == (5, 60, 'all')]


def _split(q):
    """hrd params -> (prepare params, simulate params)."""
    prep = {k: v for k, v in q.items() if k in hrd._PREP_KEYS}
    return prep, {k: v for k, v in q.items() if k not in hrd._PREP_KEYS}


def _run_summary(pair, tf, q):
    """hrd.run (prepare + the full kernel + summarize on the trade list) flattened to the row's names."""
    tr, s = hrd.run(pair, tf, q)
    out = {k: v for k, v in s.items() if k != 'exits'}
    for k, v in s['exits'].items():
        out['exit_' + k] = v
    out['costs'] = float(np.sum(tr['costs'].to_numpy())) if len(tr) else 0.0
    out['start'], out['end'] = hrd.WINDOWS[pair]
    return out


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


# ---------------------------------------------------------------------------------------------
# 1. the grid
# ---------------------------------------------------------------------------------------------
def test_1_grid():
    """(1) The grid is the full product described, keys unique; DIMS, SIGNALS, EXITS and the hrd params of
    every setting are what the spec says; unused dimensions cannot change a result; the files hold it."""
    ok = True
    S = spec_grid()
    G = C.grid()
    K = [C.key(p) for p in G]
    a = len(S) == N_GRID == 27 * 3 * 2 * 144 and len(set(S)) == N_GRID
    b = len(G) == N_GRID and len(set(K)) == N_GRID and set(K) == set(S)
    _p('  spec product %d settings (27 signal x 3 filter x 2 direction x 144 exit), runner grid %d, unique keys %d, '
       'same set: %s' % (len(S), len(G), len(set(K)), a and b))
    ok &= a and b
    # the two lists
    sk = [tuple(s[k] for k in C.SIGNAL_DIMS) for s in C.SIGNALS]
    xk = [tuple(x[k] for k in C.EXIT_DIMS) for x in C.EXITS]
    n_off = [len(C.exits_for(s)) for s in C.SIGNALS if not s['fgfOn']]
    n_on = [len(C.exits_for(s)) for s in C.SIGNALS if s['fgfOn']]
    c = (len(sk) == 54 == len(set(sk)) and len(xk) == 864 == len(set(xk)) and set(n_off) == {288} and set(n_on) == {576}
         and len(n_off) == 27 == len(n_on) and list(C.SIGNAL_DIMS) + list(C.EXIT_DIMS) == C.DIM_NAMES
         and G == [C.merge(s, x) for s in C.SIGNALS for x in C.exits_for(s)])
    _p('  SIGNALS %d unique (prepare params), EXITS %d unique (simulate params); exit settings per signal setting: '
       '%d with the filter off, %d with it on; grid = SIGNALS x their EXITS in order: %s'
       % (len(set(sk)), len(set(xk)), n_off[0], n_on[0], c))
    ok &= c
    # DIMS
    dflt = dict(zip(SPEC_DIMS, (5, 60, 'all', True, True, False, 2.0, 4.0, 5, True, False, None)))
    side = dict(zip(SPEC_DIMS, ['signal'] * 4 + ['exit'] * 8))
    unused = {'blkClose': {'fgfOn': False}, 'trail': {'trailOn': False}}
    d_ok = [d['name'] for d in C.DIMS] == SPEC_DIMS and all(
        {'name', 'values', 'kind'} <= set(d) <= {'name', 'values', 'kind', 'side', 'default', 'unused_when'}
        and d['default'] == dflt[d['name']] and type(d['default']) is type(dflt[d['name']])
        and d['side'] == side[d['name']] and d.get('unused_when') == unused.get(d['name']) for d in C.DIMS)
    d_ok &= C.DEFAULT_P == dflt and C.DEFAULT is C.DEFAULT_P
    for j, d in enumerate(C.DIMS):
        vals = [k[j] for k in S if k[j] is not None]
        seen = sorted(set(vals), key=lambda v: (str(type(v)), v))
        d_ok &= sorted(d['values'], key=lambda v: (str(type(v)), v)) == seen and d['kind'] == SPEC_KIND[d['name']]
        d_ok &= all(type(v) in (bool, int, float, str) for v in d['values'])
        if d['kind'] == 'ordinal' and d['name'] != 'trail':
            d_ok &= list(d['values']) == sorted(d['values'])
    d_ok &= C.DIMS[11]['values'] == ['0.5/0.15', '1/0.5', '2/1'] and C.TRAILS == T_TRAIL
    none_ok = all((k[4] is None) == (k[3] is False) and (k[11] is None) == (k[10] is False)
                  and all(k[j] is not None for j in range(12) if j not in (4, 11)) for k in K)
    _p('  DIMS: %d dimensions %s; values = the grid\'s values, kinds as specified: %s; None only for blkClose with '
       'the filter off and trail with trailOn False, and always there: %s'
       % (len(C.DIMS), [d['name'] for d in C.DIMS], d_ok, none_ok))
    ok &= d_ok and none_ok
    try:
        json.dumps(C.DIMS)
    except Exception as e:      # noqa: BLE001
        ok = False
        _p('  DIMS is not JSON: %r' % (e,))
    floor_ok = min(o for _, o in T_TRAIL.values()) >= 0.1
    _p('  smallest trail offset %.2f %% >= the 1-minute noise floors (BTC 0.1 %%, XAU 0.05 %%): %s'
       % (min(o for _, o in T_TRAIL.values()), floor_ok))
    ok &= floor_ok
    # the hrd params of every setting
    m_ok = hrd.DEFAULTS == SCRIPT_DEFAULTS
    if not m_ok:
        _p('  hrd.DEFAULTS differ from the script defaults written here: %r'
           % {k: (hrd.DEFAULTS.get(k), SCRIPT_DEFAULTS.get(k)) for k in set(hrd.DEFAULTS) | set(SCRIPT_DEFAULTS)
              if hrd.DEFAULTS.get(k) != SCRIPT_DEFAULTS.get(k)})
    n_bad = 0
    for p in G:
        sig = {k: p[k] for k in C.SIGNAL_DIMS}
        ex = {k: p[k] for k in C.EXIT_DIMS}
        sp = C.signal_params(sig)
        xp = C.exit_params(ex)
        eff, fgfp = hrd._params({**sp, **xp})
        want = hrd_params(p)
        if eff != want or fgfp != {'fgfOn': p['fgfOn']} or (set(sp) - hrd._PREP_KEYS) \
                or (set(hrd._ALIASES.get(k, k) for k in xp) & hrd._PREP_KEYS):
            n_bad += 1
            if n_bad <= 3:
                _p('  MAPPING %r: %r' % (p, {k: (eff.get(k), want.get(k)) for k in want if eff.get(k) != want.get(k)}))
    dp = dict(zip(SPEC_DIMS, (5, 60, 'all', True, True, False, 2.0, 4.0, 5, True, False, None)))
    eff_d, _ = hrd._params({**C.signal_params({k: dp[k] for k in C.SIGNAL_DIMS}),
                            **C.exit_params({k: dp[k] for k in C.EXIT_DIMS})})
    def_ok = (C.DEFAULT_P == dp and K.count(C.key(dp)) == 1
              and eff_d == dict(SCRIPT_DEFAULTS, path='mag', cost='ours') and C.PATH == 'mag' and C.COST == 'ours')
    _p('  hrd params of all %d settings (signal_params + exit_params, resolved by hrd._params) = the mapping written '
       'here (%d keys each): %d different; signal params only prepare keys, exit params only simulate keys'
       % (len(G), len(SCRIPT_DEFAULTS), n_bad))
    _p('  the script\'s default setting %r is one row; its params = hrd.DEFAULTS with path mag, cost ours: %s'
       % (tuple(dp.values()), def_ok))
    ok &= m_ok and n_bad == 0 and def_ok
    # normalize: every grid row round-trips, as the file gives it (p_ prefix, NaN or None for unused)
    n_rt = sum(C.normalize({'p_' + k: (float('nan') if v is None else v) for k, v in p.items()}) == p
               and C.normalize({k: v for k, v in p.items() if v is not None}) == p for p in G)
    forced = C.normalize(dict(dp, fgfOn=False, blkClose=True, trail='2/1'))
    r_ok = n_rt == len(G) and forced['blkClose'] is None and forced['trail'] is None
    _p('  normalize(): %d of %d grid rows round-trip (p_ prefix, NaN / missing for unused); a value given for an '
       'unused dimension is dropped: %s' % (n_rt, len(G), r_ok))
    ok &= r_ok
    # unused dimensions cannot change the result
    rng = np.random.default_rng(20261124)
    n_u = n_ud = 0
    for pair, tf in CELLS:
        for si in rng.choice(27, size=4, replace=False):
            sig = C.SIGNALS[2 * int(si)]                       # filter off
            sig_on = C.SIGNALS[2 * int(si) + 1]
            assert not sig['fgfOn'] and sig_on['fgfOn']
            P0 = hrd.prepare(pair, tf, C.signal_params(sig))
            P1 = hrd.prepare(pair, tf, C.signal_params(sig_on))
            X0 = C.exits_for(sig)
            X1 = C.exits_for(sig_on)
            for i in rng.choice(len(X0), size=6, replace=False):
                x = C.exit_params(X0[int(i)])
                s0 = hrd.summary_fast(P0, hrd.simulate(P0, dict(x, blkClose=True)))
                s1 = hrd.summary_fast(P0, hrd.simulate(P0, dict(x, blkClose=False)))
                n_u += 1
                n_ud += not all(_same(s0[k], s1[k]) for k in s0)
            offs = [i for i, x in enumerate(X1) if not x['trailOn']]
            for i in rng.choice(offs, size=6, replace=False):
                x = C.exit_params(X1[int(i)])
                s0 = hrd.summary_fast(P1, hrd.simulate(P1, x))
                s1 = hrd.summary_fast(P1, hrd.simulate(P1, dict(x, trailAct=0.3, trailOff=0.07)))
                s2 = hrd.summary_fast(P1, hrd.simulate(P1, dict(x, trailAct=2.0, trailOff=1.0)))
                n_u += 1
                n_ud += not all(_same(s0[k], s1[k]) and _same(s0[k], s2[k]) for k in s0)
        _free()
    _p('  unused dimensions (%s): blkClose True vs False with the filter off, other trail distances with the trail '
       'off: %d settings, %d with a different result' % (', '.join('%s %s' % c for c in CELLS), n_u, n_ud))
    ok &= n_ud == 0
    # the files
    fd = os.path.join(OUT, 'calib_hrd_dims.json')
    if os.path.exists(fd):
        same = json.load(open(fd)) == C.DIMS
        _p('  out/calib_hrd_dims.json equals DIMS: %s' % same)
        ok &= same
    else:
        _p('  out/calib_hrd_dims.json: not written yet')
    cols_want = None
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        if cols_want is None:
            Pp = hrd.prepare(pair, tf, {})
            cols_want = list(hrd.summary_fast(Pp, hrd.simulate(Pp, {'path': 'mag', 'cost': 'ours'})).keys())
        f_ok = (len(df) == N_GRID and _keys(df) == K and list(df.columns) == _pcols() + cols_want
                and all(k in cols_want for k in SUM_REQUIRED))
        nulls = {c: int(df[c].isna().sum()) for c in _sumcols(df) if df[c].isna().any()}
        f_ok &= set(nulls) <= {'pf', 'win_pct', 'avg_bars_held'}
        _p('  %s: %d rows; p_ columns = the grid in order; columns = %d p_ + the %d fields of hrd.summary_fast, '
           'nothing else: %s (NaN: %s)' % (src, len(df), len(_pcols()), len(cols_want), f_ok, nulls or 'none'))
        ok &= f_ok
        meta = C.read_meta(os.path.join(W, src))
        now = C.file_meta(pair, tf, N_GRID)
        m_ok = meta is not None and all(meta.get(k) == now[k] for k in ('strategy', 'pair', 'tf', 'path', 'cost',
                                                                        'settings', 'window'))
        cur = meta is not None and meta.get('hrd_sha256') == now['hrd_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
        _p('    file metadata: %s, path %s, cost %s, %s settings: %s; written with the hrd.py and fgf.py now on disk: %s'
           % ((meta or {}).get('strategy'), (meta or {}).get('path'), (meta or {}).get('cost'),
              (meta or {}).get('settings'), m_ok, cur if cur else 'NO (rows are still checked against the module by tests 2 and 3)'))
        ok &= m_ok
    _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 2. the default rows against the saved results
# ---------------------------------------------------------------------------------------------
def test_2_default_rows():
    """(2) The row of the script's default setting equals the saved default result of the module with the
    same path and cost (swah_hrd mag / ours, tag default), filter on (the script's default) and off; every
    other grid row with a saved counterpart; the saved Update 1 runs; the module run live. All 14 cells."""
    ok = True
    di = _default_sig_idx()
    tot = dict(cells=0, rows=0, vals=0, inv=0, live=0)
    for pair in ('BTC', 'XAU'):
        for tf in TFS:
            if os.path.exists(_out_file(pair, tf)):
                df, src = _cell_df(pair, tf)
                src = 'file'
            elif FILES_ONLY:
                continue
            else:
                df, _ = C.run_cell(pair, tf, workers=3, sig_idx=di, write=False, verbose=False)
                src = '864 rows run here'
            idx = {k: i for i, k in enumerate(_keys(df))}
            sw = pd.read_parquet(os.path.join(OUT, 'swah_hrd_%s_%s.parquet' % (pair, tf)))
            sw = sw[(sw['path'] == 'mag') & (sw['labels'] == 'normal') & (sw['cost'] == 'ours')]
            sw_sum = [c for c in sw.columns if c not in ('pair', 'tf', 'filter', 'path', 'labels', 'cost', 'setting', 'tag',
                                                         'trailOn', 'trailAct', 'trailOff', 'InpTpPct', 'InpExitCandles')]
            bad = []
            if not set(sw_sum) <= set(df.columns):
                bad.append('columns missing: %s' % (set(sw_sum) - set(df.columns)))
            n_rows = n_vals = 0
            dflt = {}
            for fgf, blk, flt in ((True, True, 'on'), (False, None, 'off')):
                for tp in (4.0, 0.0):
                    for ec in (5, 20, 100):
                        for tr in (None, '0.5/0.15', '1/0.5', '2/1'):
                            k = (5, 60, 'all', fgf, blk, False, 2.0, tp, ec, True, tr is not None, tr)
                            row = df.iloc[idx[k]]
                            m = (sw['filter'] == flt) & (sw['InpTpPct'] == tp) & (sw['InpExitCandles'] == ec)
                            if tr is None:
                                m &= ~sw['trailOn']
                            else:
                                m &= sw['trailOn'] & (sw['trailAct'] == T_TRAIL[tr][0]) & (sw['trailOff'] == T_TRAIL[tr][1])
                            if int(m.sum()) != 1:
                                bad.append('%s: %d saved rows' % (k, int(m.sum())))
                                continue
                            ref = sw[m].iloc[0]
                            if tr is None and tp == 4.0 and ec == 5:
                                if ref['tag'] != 'default':
                                    bad.append('saved row of %s is not tagged default' % flt)
                                dflt[flt] = row
                            n_vals += _cmp(row, ref, sw_sum, 'filter %s tp %g ec %d trail %s' % (flt, tp, ec, tr), bad)
                            n_rows += 1
            # the saved Update 1 runs (run_inv_hrd.py), where the cell has them
            n_inv = 0
            fj = os.path.join(OUT, 'inv_hrd_%s_%s.json' % (pair, tf))
            if os.path.exists(fj):
                runs = json.load(open(fj))['runs']
                for direction, inv in (('normal', False), ('inverted', True)):
                    for fgf, blk, flt in ((True, True, 'on'), (False, None, 'off')):
                        sv = runs['%s_%s_mag_ours' % (direction, flt)]
                        row = df.iloc[idx[(5, 60, 'all', fgf, blk, inv, 2.0, 4.0, 5, True, False, None)]]
                        ref = {}
                        for k, v in sv.items():
                            if k == 'exits':
                                ref.update({'exit_' + e: x for e, x in v.items()})
                            elif k in df.columns:
                                ref[k] = float('nan') if v is None else (float(v) if isinstance(v, str) else v)
                        n_vals += _cmp(row, ref, list(ref), '%s %s (inv json)' % (direction, flt), bad)
                        n_inv += 1
            # the module, live: hrd.run with nothing but path and cost, and with the filter off
            n_live = 0
            for flt, q in (('on', {'path': 'mag', 'cost': 'ours'}), ('off', {'path': 'mag', 'cost': 'ours', 'fgfOn': False})):
                if flt in dflt:
                    ref = _run_summary(pair, tf, q)
                    keys = [k for k in ref if k in df.columns]
                    n_vals += _cmp(dflt[flt], ref, keys, 'default %s (hrd.run live)' % flt, bad)
                    n_live += 1
            d = dflt.get('on')
            _p('  %s %-3s (%s): %2d rows = saved swah mag/ours rows, %d = saved inverted-run json, %d = hrd.run live; '
               '%d values: %s | default row: %d trades, net %+.3f %%, h1r %+.3f %%, h2r %+.3f %%'
               % (pair, tf, src, n_rows, n_inv, n_live, n_vals,
                  'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                  d['trades'], d['net_pct'], d['h1r_pct'], d['h2r_pct']))
            ok &= not bad and n_rows == 48 and n_live == 2
            tot['cells'] += 1
            tot['rows'] += n_rows
            tot['vals'] += n_vals
            tot['inv'] += n_inv
            tot['live'] += n_live
            _free()
    _p('  %d cells: %d rows against the saved sweep, %d against the saved inverted runs, %d against hrd.run live, '
       '%d values compared' % (tot['cells'], tot['rows'], tot['inv'], tot['live'], tot['vals']))
    return ok and tot['cells'] > 0


# ---------------------------------------------------------------------------------------------
# 3. random rows through --one
# ---------------------------------------------------------------------------------------------
def _one(pair, tf, p, *extra):
    cmd = [sys.executable, '-I', os.path.join(W, 'calib_hrd.py'), '--one', pair, tf, json.dumps(p)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def test_3_one_rows():
    """(3) 30 random rows per cell recomputed one at a time through `calib_hrd.py --one` (a new process each,
    the row's p_ columns as its JSON) equal the sweep rows on every summary column; the same rows through
    hrd.run with this file's own mapping; --path / --cost are honoured; bad input is refused."""
    ok = True
    rng = np.random.default_rng(31)
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
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
            if st != {'strategy': 'hrd', 'pair': pair, 'tf': tf, 'path': 'mag', 'cost': 'ours', 'p': p, 'in_grid': True,
                      'row': i}:
                bad.append('row %d: setting echoed as %r' % (i, st))
            if list(o) != sc:
                bad.append('row %d: fields %r' % (i, list(o)))
                continue
            n_vals += _cmp(row, o, sc, 'row %d --one' % i, bad)
            ref = _run_summary(pair, tf, hrd_params(p))
            n_run += _cmp(row, ref, [k for k in ref if k in sc], 'row %d hrd.run' % i, bad)
            n_tr += int(row['trades'])
        dt = time.time() - t0
        cov = all(len(cover[d['name']] - {None}) == len(d['values']) for d in C.DIMS)
        _p('  %s %s (%s): 30 random rows, each in its own `--one` process: %d summary values, and through hrd.run '
           'with the mapping written here: %d values (%d trades): %s; every value of every dimension among them: %s '
           '(%.1fs)' % (pair, tf, src, n_vals, n_run, n_tr,
                       'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
                       cov, dt))
        ok &= not bad and n_vals == 30 * len(sc)
        # --path / --cost
        bad = []
        n = 0
        for i in pick[:4]:
            p = dict(zip(C.DIM_NAMES, keys[i]))
            for path, cost in (('tv', 'tv'), ('tv', 'stress'), ('mag', 'stress')):
                rc, out, err = _one(pair, tf, p, '--path', path, '--cost', cost)
                if rc != 0:
                    bad.append('row %d %s %s: exit code %d' % (i, path, cost, rc))
                    continue
                o = json.loads(out)
                if (o['setting']['path'], o['setting']['cost']) != (path, cost):
                    bad.append('row %d: path / cost echoed %r' % (i, o['setting']))
                ref = _run_summary(pair, tf, hrd_params(p, path, cost))
                n += _cmp(o, ref, [k for k in ref if k in sc], 'row %d %s %s' % (i, path, cost), bad)
        _p('  %s %s: --path tv --cost tv, --path tv --cost stress, --path mag --cost stress on 4 rows = hrd.run with '
           'that path and cost: %d values: %s' % (pair, tf, n, 'all equal' if not bad else '; '.join(b for b in bad if b)))
        ok &= not bad
        _free()
    # bad input
    pair, tf = CELLS[0]
    p = dict(C.DEFAULT_P)
    cases = (('unknown dimension', dict(p, InpRiskPct=2.0), ()),
             ('value not in the grid', dict(p, InpSlPct=3.0), ()),
             ('missing used dimension', {k: v for k, v in p.items() if k != 'inv'}, ()),
             ('trailOn without trail', dict(p, trailOn=True), ()),
             ('not an object', [1, 2], ()))
    res = []
    for name, q, extra in cases:
        rc, out, err = _one(pair, tf, q, *extra)
        res.append((name, rc, out.strip() == '' and 'calib_hrd.py --one' in err))
    rc, out, err = _one(pair, tf, dict(p, InpSlPct=3.0, trailOn=True, trail='0.8/0.3'), '--off-grid')
    og = rc == 0 and json.loads(out)['setting']['in_grid'] is False and json.loads(out)['setting']['row'] is None
    if og:
        o = json.loads(out)
        ref = _run_summary(pair, tf, dict(hrd_params(p), InpSlPct=3.0, trailOn=True, trailAct=0.8, trailOff=0.3))
        og = all(_same(o[k], ref[k]) for k in ref if k in o)
    b_ok = all(rc == 2 and e for _, rc, e in res) and og
    _p('  bad input is refused (exit code 2, nothing on stdout): %s; --off-grid runs a setting outside the grid '
       '(SL 3 %%, trail 0.8 / 0.3) = hrd.run: %s' % (', '.join('%s -> %d' % (n, rc) for n, rc, _ in res), og))
    return ok and b_ok


# ---------------------------------------------------------------------------------------------
# 4. worker count
# ---------------------------------------------------------------------------------------------
def _sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def test_4_workers():
    """(4) XAU 240, the full grid with 1 worker and with 3 workers (files in calib_tmp_hrd/w1 and w3, not
    out/): every row and column identical, and the two files byte for byte; equal to out/ when it exists."""
    d1 = os.path.join(TMP, 'w1')
    d3 = os.path.join(TMP, 'w3')
    a, ia = C.run_cell('XAU', '240', workers=1, out_dir=d1, verbose=False)
    _free()
    b, ib = C.run_cell('XAU', '240', workers=3, out_dir=d3, verbose=False)
    _free()
    f1 = os.path.join(d1, 'calib_hrd_XAU_240.parquet')
    f3 = os.path.join(d3, 'calib_hrd_XAU_240.parquet')
    fa = pd.read_parquet(f1)
    fb = pd.read_parquet(f3)
    same = fa.equals(fb) and a.equals(b) and len(fa) == N_GRID and list(fa.columns) == list(fb.columns) \
        and all(fa[c].dtype == fb[c].dtype for c in fa.columns)
    byt = _sha(f1) == _sha(f3)
    dims = json.load(open(os.path.join(d1, 'calib_hrd_dims.json'))) == C.DIMS == json.load(open(os.path.join(d3, 'calib_hrd_dims.json')))
    _p('  XAU 240: %d rows x %d columns; 1 worker %.1fs (runs %.1fs), 3 workers %.1fs (runs %.1fs, speed-up x%.2f): '
       'frames %s, files %s (sha256 %s), dims.json = DIMS: %s'
       % (len(fa), len(fa.columns), ia['t_total'], ia['t_run'], ib['t_total'], ib['t_run'], ia['t_run'] / ib['t_run'],
          'identical' if same else 'DIFFERENT', 'byte for byte equal' if byt else 'DIFFERENT bytes', _sha(f3)[:16], dims))
    ok = same and byt and dims
    fo = _out_file('XAU', '240')
    if os.path.exists(fo):
        fo_df = pd.read_parquet(fo)
        again = fo_df.equals(fb)
        _p('  out/calib_hrd_XAU_240.parquet (the production run) equals this re-run: %s (bytes %s)'
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
    """(5) BTC 1 (the largest cell): the real preparation of all 54 signal settings, then one pass = the 864
    exit settings of one signal input (filter off + on) with 3 workers, for the default, the busiest and
    the quietest signal input; extrapolated to the 27 signal inputs. The full grid must stay under 45 min."""
    load0 = os.getloadavg()[0]
    cell = C.prepare_cell('BTC', '1')
    t_prep = cell['t_prep']
    nsig = {si: int(np.count_nonzero(cell['P'][si]['long_sig'] | cell['P'][si]['short_sig'])) for si in cell['idx']}
    _p('  BTC 1: %d chart bars, %d 1-minute bars; all 54 signal settings prepared in %.1fs (signals %.1fs, sub-bars '
       '%.1fs, kernel %.1fs); bars with a signal: %d .. %d (default %d)'
       % (cell['bars'], cell['n_sub'], t_prep, cell['t_sig'], cell['t_sub'], cell['t_jit'], min(nsig.values()),
          max(nsig.values()), nsig[_default_sig_idx()[0]]))
    order = sorted(range(0, 54, 2), key=lambda si: nsig[si])
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
        _p('  pass %-8s (pivotStrength %d, maxDivLookback %d, divs %s): %d settings, 3 workers %.1fs (%.4fs per '
           'setting per worker, workers busy %.0f%%)' % (name, s['pivotStrength'], s['maxDivLookback'], s['divs'],
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
    _p('  full grid BTC 1 with 3 workers = preparation %.1fs + 27 passes: %.1fs = %.1f min (mean pass), %.1f min '
       '(every pass as slow as the slowest); limit 45 min; load average %.2f -> %.2f (other jobs share the 4 CPUs)'
       % (t_prep, est, est / 60.0, hi / 60.0, load0, os.getloadavg()[0]))
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
    switch that is off leaves no trace (no trail / target / hybrid / blocked-close exits, nothing blocked
    with the filter off), and every dimension changes results somewhere in the cells."""
    ok = True
    live_all = {}
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        ex = [c for c in df.columns if c.startswith('exit_')]
        tr = df['trades']
        chk = {
            'trades = long + short': (tr == df['long'] + df['short']).all(),
            'trades = h1_trades + h2_trades': (tr == df['h1_trades'] + df['h2_trades']).all(),
            'trades = sum of the exit kinds': (tr == df[ex].sum(axis=1)).all(),
            'net_pct = (final_equity - initial) / initial': ((df['final_equity'] - INIT) / INIT * 100 == df['net_pct']).all(),
            'half1_pct + half2_pct = net_pct': np.allclose(df['half1_pct'] + df['half2_pct'], df['net_pct'], rtol=0, atol=1e-9),
            'window': ((df['start'] == hrd.WINDOWS[pair][0]) & (df['end'] == hrd.WINDOWS[pair][1])).all() and df['bars'].nunique() == 1,
            'trail off: no trail exit': (df.loc[~df['p_trailOn'], 'exit_trail'] == 0).all(),
            'target 0: no tp exit': (df.loc[df['p_InpTpPct'] == 0.0, 'exit_tp'] == 0).all(),
            'hybrid off: no hybrid exit': (df.loc[~df['p_useHybridExit'], 'exit_hybrid'] == 0).all(),
            'filter off: nothing blocked, no blocked close': (df.loc[~df['p_fgfOn'], ['blocked_long', 'blocked_short', 'exit_blocked_close']] == 0).all().all(),
            'blkClose False: no blocked close': (df.loc[df['p_blkClose'].map(lambda v: v is not None and not bool(v)), 'exit_blocked_close'] == 0).all(),
            'blocked <= raw': ((df['blocked_long'] <= df['raw_long']) & (df['blocked_short'] <= df['raw_short'])).all(),
            'pf / win NaN only without trades': ((df['pf'].isna() == (tr == 0)) & (df['win_pct'].isna() == (tr == 0))).all(),
            'costs > 0 with trades': ((df['costs'] > 0) == (tr > 0)).all(),
            'fair halves finite': np.isfinite(df[['h1r_pct', 'h2r_pct', 'net_pct', 'max_dd_pct']].to_numpy()).all(),
            'max_dd in [0, 100)': ((df['max_dd_pct'] >= 0) & (df['max_dd_pct'] < 100)).all(),
        }
        failed = [k for k, v in chk.items() if not bool(v)]
        # every dimension changes results: groups of rows that differ only in that dimension
        sc = _sumcols(df)
        sig = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
        ps = df[_pcols()].astype(str)
        joint = (('pivotStrength', ['p_pivotStrength']), ('maxDivLookback', ['p_maxDivLookback']), ('divs', ['p_divs']),
                 ('filter (fgfOn, blkClose)', ['p_fgfOn', 'p_blkClose']), ('inv', ['p_inv']), ('InpSlPct', ['p_InpSlPct']),
                 ('InpTpPct', ['p_InpTpPct']), ('InpExitCandles', ['p_InpExitCandles']),
                 ('useHybridExit', ['p_useHybridExit']), ('trail (trailOn, trail)', ['p_trailOn', 'p_trail']),
                 ('blkClose alone (filter on)', ['p_blkClose']), ('trail alone (trailing on)', ['p_trail']))
        parts = []
        for name, cols in joint:
            others = [c for c in _pcols() if c not in cols]
            sel = np.ones(len(df), bool)
            if name.startswith('blkClose alone'):
                sel = df['p_fgfOn'].to_numpy(bool)
            elif name.startswith('trail alone'):
                sel = df['p_trailOn'].to_numpy(bool)
            g = pd.Series(sig[sel]).groupby([ps[c].to_numpy()[sel] for c in others]).agg(['size', 'nunique'])
            n_all = int((g['nunique'] == g['size']).sum())
            n_any = int((g['nunique'] > 1).sum())
            live_all[name] = live_all.get(name, 0) + n_any
            parts.append('%s %d / %d / %d' % (name, n_all, n_any, len(g)))
        n_distinct = len(np.unique(sig))
        cand = int(((df['h1r_pct'] > 0) & (df['h2r_pct'] > 0) & (df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).sum())
        _p('  %s %s (%s): %d rows, %d checks: %s' % (pair, tf, src, len(df), len(chk),
                                                     'all hold' if not failed else 'FAILED: ' + '; '.join(failed)))
        _p('    groups differing only in one dimension (all results distinct / some distinct / groups): %s' % '; '.join(parts))
        _p('    trades %d .. %d (median %d); distinct results %d of %d rows; rows positive in both fair halves with '
           '>= 30 trades in each: %d' % (tr.min(), tr.max(), int(tr.median()), n_distinct, len(df), cand))
        ok &= not failed
    dead = [k for k, v in live_all.items() if v == 0]
    _p('  every dimension changes results in at least one group over the cells: %s' % ('yes' if not dead else 'NO: %s' % dead))
    return ok and not dead


# ---------------------------------------------------------------------------------------------
# 7. every row
# ---------------------------------------------------------------------------------------------
def test_7_all_rows():
    """Every row of the cells' files, not a sample: recomputed in this process with hrd.prepare once per
    signal setting and hrd.simulate + hrd.summary_fast per row, the parameters from this file's own mapping
    (hrd_params, split into the prepare and the simulate keys); every summary value must be equal. A sample
    of 30 rows cannot see one stale signal setting or one displaced chunk of rows; this does."""
    ok = True
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        sc = _sumcols(df)
        keys = _keys(df)
        vals = [df[c].tolist() for c in sc]
        groups = {}
        for i, k in enumerate(keys):
            prep, sim = _split(hrd_params(dict(zip(SPEC_DIMS, k))))
            groups.setdefault(tuple(sorted((a, repr(b)) for a, b in prep.items())), (prep, []))[1].append((i, sim))
        t0 = time.time()
        n_vals = 0
        bad_rows = []
        bad_groups = 0
        fields_ok = True
        for gk in sorted(groups):
            prep, items = groups[gk]
            Pp = hrd.prepare(pair, tf, prep)
            n_bad0 = len(bad_rows)
            for i, sim in items:
                s = hrd.summary_fast(Pp, hrd.simulate(Pp, sim))
                if list(s) != sc:
                    fields_ok = False
                    break
                n_vals += len(sc)
                if not all(_same(vals[j][i], s[c]) for j, c in enumerate(sc)):
                    bad_rows.append(i)
            bad_groups += len(bad_rows) > n_bad0
            del Pp
            hrd._SIG.clear()
        c_ok = fields_ok and not bad_rows and len(groups) == 54 and n_vals == N_GRID * len(sc) == len(df) * len(sc)
        _p('  %s %s (%s): all %d rows recomputed (hrd.prepare for each of the %d signal settings, hrd.simulate + '
           'summary_fast per row): %d summary values, %s (%.1fs)'
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
    """Every cell with a file in out/: the file holds the grid in order with the summary columns, and 4
    random rows of EVERY signal setting (216 rows per cell) recomputed in this process (hrd.prepare per signal
    setting, hrd.simulate + hrd.summary_fast per row, this file's own mapping) equal the file. The other tests
    read two cells in full and, of the other twelve, only the rows of the default signal setting."""
    ok = True
    K = [C.key(p) for p in C.grid()]
    rng = np.random.default_rng(8)
    n_cells = 0
    lb_same = []
    for pair in ('BTC', 'XAU'):
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
            g_ok = (len(df) == N_GRID and keys == K and all(k in sc for k in SUM_REQUIRED) and meta is not None
                    and all(meta.get(k) == now[k] for k in ('strategy', 'pair', 'tf', 'path', 'cost', 'settings', 'window'))
                    and bool(((df['start'] == hrd.WINDOWS[pair][0]) & (df['end'] == hrd.WINDOWS[pair][1])).all()))
            cur = meta is not None and meta.get('hrd_sha256') == now['hrd_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
            groups = {}
            for i, k in enumerate(keys):
                prep, sim = _split(hrd_params(dict(zip(SPEC_DIMS, k))))
                groups.setdefault(tuple(sorted((a, repr(b)) for a, b in prep.items())), (prep, []))[1].append((i, sim))
            n_rows = n_vals = 0
            bad_rows = []
            for gk in sorted(groups):
                prep, items = groups[gk]
                Pp = hrd.prepare(pair, tf, prep)
                for j in sorted(int(x) for x in rng.choice(len(items), size=4, replace=False)):
                    i, sim = items[j]
                    s = hrd.summary_fast(Pp, hrd.simulate(Pp, sim))
                    n_rows += 1
                    n_vals += len(sc)
                    if list(s) != sc or not all(_same(df[c].iat[i], s[c]) for c in sc):
                        bad_rows.append(i)
                del Pp
                hrd._SIG.clear()
            # how much of the grid is live in this cell: maxDivLookback 60 against 120
            h = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
            lb = df['p_maxDivLookback'].to_numpy()
            same_lb = bool((h[lb == 60] == h[lb == 120]).all())
            if same_lb:
                lb_same.append('%s %s' % (pair, tf))
            c_ok = g_ok and not bad_rows and len(groups) == 54 and n_rows == 216
            _p('  %s %-3s: %d rows, the grid in order, metadata and window: %s; written with the hrd.py / fgf.py now on '
               'disk: %s; %d rows (4 of each of the %d signal settings) recomputed: %d values, %s; distinct results %d '
               '(%.1fs)' % (pair, tf, len(df), g_ok, cur, n_rows, len(groups), n_vals,
                           'all equal' if not bad_rows else '%d ROWS DIFFER: %s' % (len(bad_rows), bad_rows[:8]),
                           len(np.unique(h)), time.time() - t0))
            ok &= c_ok
            _free()
    if n_cells == 0:
        _p('  no cell has a file in out/ yet: nothing to check')
    else:
        _p('  %d cells checked; cells where maxDivLookback 60 and 120 give the same rows everywhere (consecutive pivots '
           'are never further apart than 60 bars there): %s' % (n_cells, ', '.join(lb_same) or 'none'))
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
        if pair not in ('BTC', 'XAU') or tf not in TFS:
            _p('unknown cell %s:%s' % (pair, tf))
            return 2
    names = sorted(k for k, v in globals().items() if k.startswith('test_') and callable(v))
    if args:
        names = [k for k in names if any(f in k for f in args)]
    if not names:
        _p('no tests match %s' % args)
        return 2
    _p('calib_tests_hrd.py: cells %s; hrd.py sha256 %s; calib_hrd.py sha256 %s; load average %.2f'
       % (', '.join('%s %s' % c for c in CELLS), _sha(os.path.join(W, 'hrd.py'))[:16],
          _sha(os.path.join(W, 'calib_hrd.py'))[:16], os.getloadavg()[0]))
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
    return 0 if all(res.values()) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
