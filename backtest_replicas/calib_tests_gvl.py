"""calib_tests_gvl.py: tests of calib_gvl.py (CALIB_SPEC.md, strategy "gvl"; the grid is section 14
of SPEC_gvl.md with the orchestrator's decisions: the scale-free sizing maxQty 1e9 / qtyStep
0.000001 and tvMargin 0 on every row, one trailing pair per cell, column floor_ok, exitStyle one
categorical dimension with its Pine inputs as extra columns, --script-sizing on --one).

Usage: python3 -I calib_tests_gvl.py [name filter ...] [--cells XAU:240,BTC:240] [--files-only]

  test_1_grid             the grid is the full product of section 14 (20,736 = 288 x 72), keys
                          unique, DIMS / SIGNALS / EXITS consistent, the same in all 14 cells; every
                          setting maps to the gvl params the spec means (an independent mapping
                          written here, the Pine's own input defaults read from the .pine file); the
                          trailing pair of every cell = the table, and the table's floor recomputed
                          here from the bar files; floor_ok is measured (a trailing distance below the
                          floor gives False on the "trail" rows only, in the table and in --one); a
                          trailing distance cannot change a row without a trailing stop; the files hold
                          the grid in order, with the input columns
  test_2_default_rows     the default row with --script-sizing, and the same with inv true, equal
                          the saved default results of the module with the same path and cost:
                          out/inv_gvl_<PAIR>_<TF>.json runs normal/off/mag/ours and
                          inverted/off/mag/ours through the command line on BTC 60 and XAU 240 (plus
                          filter on, tv / script costs, "Stop Next Candle" = runs_stop), and every
                          saved run of runs and runs_stop of all 14 cells through calib_gvl.one; the
                          scale-free default rows of the sweep against gvl.run called directly
  test_3_one_rows         30 random rows per cell recomputed one at a time through
                          `calib_gvl.py --one` (a new process each) equal the sweep rows (and echo
                          the row number); the same rows through gvl.run with this file's own
                          mapping; --path / --cost; --script-sizing; --off-grid; bad input
  test_4_workers          XAU 240: 1 worker vs 3 workers identical (frames and file bytes);
                          gvl.prepare runs once per signal setting, the filter once per cell
  test_5_timing_btc1      BTC 1, in a process of its own: the real preparation and passes of the
                          default, a random twelfth and the busiest signal settings with 3 workers,
                          extrapolated to the full grid: under 45 minutes; and the memory the
                          process and its 3 workers hold together (sum of PSS, sampled) and its
                          peak RSS: under 4 GB
  test_6_row_consistency  what every row must satisfy whatever the data (counts add up, a switch
                          that is off leaves no trace, the input columns belong to the setting), and
                          every dimension changes results
  test_7_all_rows         EVERY row of the cells' files (not a sample) recomputed in this process:
                          gvl.prepare once per signal setting, gvl.simulate + gvl.summary per row,
                          with this file's own mapping; all values equal
  test_8_every_cell       every cell that has a file in out/: the file holds the grid in order, and
                          2 random rows of EVERY signal setting (576 rows per cell) recomputed in
                          this process equal the file; equal to the scratch copy when there is one

The cells of tests 3, 6 and 7 (and the files of test 1) are --cells (default XAU 240 and BTC 240):
the file out/calib_gvl_<PAIR>_<TF>.parquet when it exists, else the cell is run here with 3 workers
into calib_tmp_gvl/w3/ (never into out/). Test 2 covers all 14 cells: the file when it exists, else
only the two default signal settings are run in memory (144 rows; --files-only skips those). At
most 2 processes at a time, except the sweep's own 3 workers.
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
import gvl  # noqa: E402
import fgf  # noqa: E402
import calib_gvl as C  # noqa: E402

OUT = os.path.join(W, 'out')
TMP = os.path.join(W, 'calib_tmp_gvl')
PINE = '/home/user/master/GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine'
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
WINDOWS = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}      # CALIB_SPEC.md
INIT = 100000.0
CELLS = [('XAU', '240'), ('BTC', '240')]
FILES_ONLY = False
N_GRID = 20736
MEM_LIMIT_MB = 4000        # test 5: the BTC 1 process + its 3 workers (the session shares 16 GB with other jobs)
SUM_REQUIRED = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
                'exit_sl', 'exit_tp', 'exit_trail', 'exit_reverse', 'exit_time', 'exit_maxbars', 'exit_daily_lock',
                'exit_eod', 'exit_end', 'net_r', 'h1_r', 'h2_r', 'zero_qty', 'reentry_same_bar', 'margin_over',
                'locked_bars')


def _p(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# this file's own reading of the spec (independent of calib_gvl's lists and mappings)
# ---------------------------------------------------------------------------------------------
MARKET = "Market Next Candle"
STOP = "Stop Next Candle"
SPEC_DIMS = ['emaPair', 'trendFilterLen', 'preMinVolScore', 'preMinVolRise', 'preCloseLocation', 'preUseTrend',
             'fgfOn', 'preCandleEntryMode', 'inv', 'slAtrMult', 'exitStyle', 'useDailyLossLock']
# section 14, the table: values in its order, kind, side, default
SPEC_VALUES = {'emaPair': ['5/13', '8/21'], 'trendFilterLen': [50, 100, 200], 'preMinVolScore': [0.0, 35.0],
               'preMinVolRise': [0.0, 1.0], 'preCloseLocation': [0.55, 0.65, 0.75], 'preUseTrend': [True, False],
               'fgfOn': [False, True], 'preCandleEntryMode': [MARKET, STOP], 'inv': [False, True],
               'slAtrMult': [0.5, 1.0, 2.0], 'exitStyle': ['tp5', 'time4', 'trail'], 'useDailyLossLock': [True, False]}
SPEC_KIND = {'emaPair': 'ordinal', 'trendFilterLen': 'ordinal', 'preMinVolScore': 'ordinal', 'preMinVolRise': 'ordinal',
             'preCloseLocation': 'ordinal', 'preUseTrend': 'categorical', 'fgfOn': 'categorical',
             'preCandleEntryMode': 'categorical', 'inv': 'categorical', 'slAtrMult': 'ordinal',
             'exitStyle': 'categorical', 'useDailyLossLock': 'categorical'}
SPEC_SIDE = dict(zip(SPEC_DIMS, ['signal'] * 7 + ['exit'] * 5))
SPEC_DEFAULT = dict(zip(SPEC_DIMS, ('8/21', 100, 35.0, 1.0, 0.65, True, False, MARKET, False, 1.0, 'tp5', True)))
T_EMA = {'5/13': (5, 13), '8/21': (8, 21)}                       # emaPair = (fastEmaLen, slowEmaLen)
T_STYLE = {'tp5': (5.0, 0, False), 'time4': (0.0, 4, False), 'trail': (0.0, 0, True)}   # (tpR, maxBarsHeld, useTrail)
INPUT_NAMES = ['fastEmaLen', 'slowEmaLen', 'tpR', 'maxBarsHeld', 'useTrail', 'trailActAtr', 'trailDstAtr']
# section 14: (trailActAtr, trailDstAtr) per cell; the 10th percentile of ATR(14) / close in %, as printed there
T_TRAIL = {('BTC', '1'): (13.0, 6.5), ('BTC', '5'): (3.5, 1.75), ('XAU', '1'): (10.0, 5.0), ('XAU', '5'): (3.5, 1.75)}
T_P10 = {('BTC', '1'): 0.0157, ('BTC', '5'): 0.0574, ('BTC', '15'): 0.125, ('BTC', '30'): 0.198, ('BTC', '60'): 0.318,
         ('BTC', '120'): 0.512, ('BTC', '240'): 0.826, ('XAU', '1'): 0.0101, ('XAU', '5'): 0.0290,
         ('XAU', '15'): 0.060, ('XAU', '30'): 0.094, ('XAU', '60'): 0.145, ('XAU', '120'): 0.203, ('XAU', '240'): 0.311}
T_LADDER = (1.0, 1.75, 2.5, 3.5, 5.0, 6.5)
T_FLOOR = {'BTC': 0.1, 'XAU': 0.05}
# the Pine's input defaults (GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine; SPEC_gvl.md sections 3.1, 3.2) and
# the replica controls
SCRIPT_DEFAULTS = dict(
    devLen=30, fastVoVixLen=10, slowVoVixLen=30, fastEmaLen=8, slowEmaLen=21, trendFilterLen=100,
    useRsiFilter=True, rsiLen=14, rsiOverbought=70, rsiOversold=30,
    requiredSignalTimeframe='240', allowAnyChartTimeframe=True, maxSignalSecondsAfterWindowStart=90,
    allowWeekendEntries=True,
    usePreCandleArm=True, radarTimeframeMode='Chart', preMinScore=60, preMinVolScore=35.0, preMinVolRise=1.0,
    preCloseLocation=0.65, preUseTrend=True, preUseEmaSlope=False, preUseRvol=False, preRvolLength=20,
    preMinRvol=1.10, preUseBodyAtr=False, preMinBodyAtr=0.20, preUseMicroBreak=False, preBreakoutLookback=2,
    useSessionFilter=False, tradePreset='Balanced', entry_session='0945-1530', morning_entry_session='0945-1115',
    flat_session='0930-1545',
    start=None, end=None, risingRule='any',
    preCandleEntryMode=MARKET, preStopAtrBuffer=0.03, preCancelAfterBars=2, oneSignalPerPolyWindow=True,
    ExitMode='ATR', slPoints=16500.0, tpPoints=82500.0, atrLen=14, slAtrMult=1.0, tpR=5.0, useTrail=False,
    trailActPoints=99000.0, trailPoints=16500.0, trailActAtr=6.0, trailDstAtr=1.0, maxBarsHeld=0,
    QtyMode='Risk %', fixedQty=10.0, riskPct=1.0, maxQty=50.0, qtyStep=0.001, capMargin=True, marginPct=1.0,
    brokerPreset='Manual / custom', manualPointValue=1.0,
    useMaxBarsExit=False, maxBarsInTrade=1, useDailyLossLock=True, maxDailyLossCurrency=0.0, maxDailyLosses=3,
    useMaxStopDistance=False, maxStopDistancePoints=8.0,
    gvInv=False, inv=False, path='tv', cost='tv', tvMargin=0.0,
    # the filter's own inputs (L256-323): OFF by default in this file
    fgfOn=False, fgfTf="60", fgfLvMode="Entry price", fgfLast="Until next signal", fgfMinutes=60, fgfBars=1,
    fgfCheck="Tick", fgfBandAtr=0.25, fgfAgainst=True, fgfAllowBuy=True, fgfAllowSell=True,
    fgfSpreadPts=25.0, fgfEntryDistPts=50.0, fgfHoldBars=0, fgfHoldFavPts=5.0, fgfOnePerBar=True,
    fgfDistUnit="ATR", fgfBurstAtr=0.5, fgfEntryDistAtr=0.25, fgfHoldFavAtr=0.1, fgfBurstPts=172.0,
    fgfUseBurst=True, fgfAnyCombo=False, fgfDriftBars=60, fgfUseDrift=False,
    fgfUseZones=True, fgfParentTf="60", fgfRsiLen=14, fgfFastLen=2, fgfMinAligned=2, fgfFlatParent=False,
    fgfIgnoreNa=True, fgfHtfClosed=True,
    fgfUseZ1=True, fgfZTf1="60", fgfUseZ2=True, fgfZTf2="120", fgfUseZ3=True, fgfZTf3="240",
    fgfUseZ4=False, fgfZTf4="480", fgfUseZ5=False, fgfZTf5="1", fgfUseZ6=False, fgfZTf6="2")
REPLICA_CONTROLS = {'start', 'end', 'risingRule', 'path', 'cost', 'tvMargin', 'inv'}
# the ORDER / EXIT inputs (parameters of gvl.simulate; SPEC_gvl.md section 3.2); everything else is prepare's
ORDER_INPUTS = {'preCandleEntryMode', 'preStopAtrBuffer', 'preCancelAfterBars', 'oneSignalPerPolyWindow', 'ExitMode',
                'slPoints', 'tpPoints', 'atrLen', 'slAtrMult', 'tpR', 'useTrail', 'trailActPoints', 'trailPoints',
                'trailActAtr', 'trailDstAtr', 'maxBarsHeld', 'QtyMode', 'fixedQty', 'riskPct', 'maxQty', 'qtyStep',
                'capMargin', 'marginPct', 'brokerPreset', 'manualPointValue', 'useMaxBarsExit', 'maxBarsInTrade',
                'useDailyLossLock', 'maxDailyLossCurrency', 'maxDailyLosses', 'useMaxStopDistance',
                'maxStopDistancePoints', 'gvInv', 'inv', 'path', 'cost', 'tvMargin'}


def spec_grid():
    """SPEC_gvl.md section 14: 2 x 3 x 2 x 2 x 3 x 2 x 2 prepare settings x 2 x 2 x 3 x 3 x 2 simulate
    settings, the first dimension outermost; the same product in every cell."""
    V = SPEC_VALUES
    G = []
    for ep in V['emaPair']:
        for tl in V['trendFilterLen']:
            for vs in V['preMinVolScore']:
                for vr in V['preMinVolRise']:
                    for cl in V['preCloseLocation']:
                        for ut in V['preUseTrend']:
                            for f in V['fgfOn']:
                                for m in V['preCandleEntryMode']:
                                    for inv in V['inv']:
                                        for sl in V['slAtrMult']:
                                            for es in V['exitStyle']:
                                                for lk in V['useDailyLossLock']:
                                                    G.append((ep, tl, vs, vr, cl, ut, f, m, inv, sl, es, lk))
    return G


def own_inputs(p, pair, tf):
    """The Pine inputs that emaPair and exitStyle set (the extra columns), from the spec's table."""
    f, s = (int(v) for v in p['emaPair'].split('/'))
    tp, mb, tr = T_STYLE[p['exitStyle']]
    act, dst = T_TRAIL.get((pair, tf), (2.0, 1.0)) if tr else (None, None)
    return dict(zip(INPUT_NAMES, (f, s, tp, mb, tr, act, dst)))


def gvl_params(p, pair, tf, path='mag', cost='ours', script_sizing=False):
    """A setting (dict over SPEC_DIMS) as the complete gvl param set, written from the spec and the
    orchestrator's decisions: maxQty 1e9 / qtyStep 0.000001 and tvMargin 0 on every row."""
    q = dict(SCRIPT_DEFAULTS)
    f, s = (int(v) for v in p['emaPair'].split('/'))
    tp, mb, tr = T_STYLE[p['exitStyle']]
    q.update(fastEmaLen=f, slowEmaLen=s, trendFilterLen=p['trendFilterLen'], preMinVolScore=p['preMinVolScore'],
             preMinVolRise=p['preMinVolRise'], preCloseLocation=p['preCloseLocation'], preUseTrend=p['preUseTrend'],
             fgfOn=p['fgfOn'], preCandleEntryMode=p['preCandleEntryMode'], gvInv=p['inv'], inv=p['inv'],
             slAtrMult=p['slAtrMult'], tpR=tp, maxBarsHeld=mb, useTrail=tr, useDailyLossLock=p['useDailyLossLock'],
             path=path, cost=cost, tvMargin=0.0)
    if tr:
        q['trailActAtr'], q['trailDstAtr'] = T_TRAIL.get((pair, tf), (2.0, 1.0))
    if not script_sizing:
        q['maxQty'] = 1e9
        q['qtyStep'] = 0.000001
    return q


def _split(q):
    """gvl params -> (prepare params, simulate params), by this file's list of the ORDER / EXIT inputs."""
    return ({k: v for k, v in q.items() if k not in ORDER_INPUTS}, {k: v for k, v in q.items() if k in ORDER_INPUTS})


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
def _miss(v):
    return v is None or (isinstance(v, (float, np.floating)) and v != v)


def _same(a, b):
    """Exact equality; a missing value (None, NaN) equals a missing value."""
    if _miss(a) or _miss(b):
        return _miss(a) and _miss(b)
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    return float(a) == float(b)


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
    """The p_ columns of a file as a list of key tuples (python values)."""
    cols = [[_py(v) for v in df[c].tolist()] for c in _pcols()]
    return list(zip(*cols))


def _rescols(df):
    """Every column that is not a p_ column: the input columns, floor_ok and the summary fields."""
    return [c for c in df.columns if not c.startswith('p_')]


def _sumcols(df):
    return [c for c in df.columns if not c.startswith('p_') and c != 'floor_ok' and c not in INPUT_NAMES]


def _out_file(pair, tf):
    return os.path.join(OUT, 'calib_gvl_%s_%s.parquet' % (pair, tf))


def _tmp_file(pair, tf, w='w3'):
    return os.path.join(TMP, w, 'calib_gvl_%s_%s.parquet' % (pair, tf))


def _fresh(path):
    """A scratch file is used only when it is newer than the runner and the replica."""
    return os.path.exists(path) and os.path.getmtime(path) > max(os.path.getmtime(os.path.join(W, 'calib_gvl.py')),
                                                                 os.path.getmtime(os.path.join(W, 'gvl.py')))


_DF = {}


def _cell_df(pair, tf):
    """(DataFrame, where): out/ when the cell's file exists, else calib_tmp_gvl/w3 (run here if needed)."""
    key = (pair, tf)
    if key not in _DF:
        f = _out_file(pair, tf)
        if os.path.exists(f):
            src = 'out/' + os.path.basename(f)
            if not _fresh(f):
                _p('  note: %s is older than calib_gvl.py or gvl.py' % src)
        else:
            f = _tmp_file(pair, tf)
            src = 'calib_tmp_gvl/w3/' + os.path.basename(f)
            if not _fresh(f):
                t0 = time.time()
                C.run_cell(pair, tf, workers=3, out_dir=os.path.dirname(f), verbose=False)
                _p('  %s %s has no file in out/: run here with 3 workers into %s (%.1fs)' % (pair, tf, src, time.time() - t0))
                _free()
        _DF[key] = (pd.read_parquet(f), src, f)
    return _DF[key][0], _DF[key][1]


def _cell_path(pair, tf):
    _cell_df(pair, tf)
    return _DF[(pair, tf)][2]


def _free():
    C._free_caches()
    C._G.clear()
    gc.collect()


def _default_sig_idx():
    """The two signal settings with the script's signal inputs: filter off, filter on."""
    return [i for i, s in enumerate(C.SIGNALS)
            if all(s[k] == SPEC_DEFAULT[k] for k in SPEC_DIMS[:6])]


def _run_summary(pair, tf, q):
    """gvl.run (prepare + simulate + summary in one call of the module)."""
    _, s = gvl.run(pair, tf, q)
    return s


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


def _txt(bad):
    return 'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b))


def _own_p10(pair, tf):
    """The 10th percentile over the window of ATR(14) / close in %, computed here from the bar file with
    pandas (Wilder's average as an exponential mean of the true range; the window starts thousands of
    bars into the file, so its seed no longer matters)."""
    t = pq.read_table(os.path.join(W, 'data', '%s_%s.parquet' % (pair, tf)), columns=['high', 'low', 'close', 't_close'])
    h, l, c, tc = (t.column(k).to_numpy() for k in ('high', 'low', 'close', 't_close'))
    pc = np.concatenate(([np.nan], c[:-1]))
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1.0 / 14.0, adjust=False).mean().to_numpy()
    s0, e0 = WINDOWS[pair]
    m = (tc >= s0) & (tc <= e0)
    w0 = int(np.argmax(m))
    return float(np.percentile(atr[m] / c[m] * 100.0, 10)), w0, int(m.sum())


def _sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


# ---------------------------------------------------------------------------------------------
# 1. the grid
# ---------------------------------------------------------------------------------------------
def test_1_grid():
    """(1) The grid is the full product of section 14, keys unique, the same in all 14 cells; DIMS, SIGNALS,
    EXITS and the gvl params of every setting are what the spec says; the trailing table and its floor; a
    trailing distance cannot change a row without a trailing stop; the files hold the grid."""
    ok = True
    # ---- the product
    S = spec_grid()
    all_ok = True
    for pair in PAIRS:
        for tf in TFS:
            G = C.grid(pair, tf)
            K = [C.key(p) for p in G]
            c_ok = (len(G) == N_GRID == len(set(K)) and K == S and C.n_settings(pair, tf) == N_GRID
                    and G == [C.merge(s, x) for s in C.signals(pair, tf) for x in C.exits_for(s, pair, tf)])
            all_ok &= c_ok
            if not c_ok:
                _p('  %s %s: spec %d, runner %d, unique %d, same order %s' % (pair, tf, len(S), len(G), len(set(K)), K == S))
    a = (N_GRID == 288 * 72 == (2 * 3 * 2 * 2 * 3 * 2 * 2) * (2 * 2 * 3 * 3 * 2) == C.N_GRID == len(S) == len(set(S))
         and C.grid() == C.grid('BTC', '1'))
    _p('  spec product 20,736 = 288 prepare settings (2 x 3 x 2 x 2 x 3 x 2 x 2) x 72 simulate settings (2 x 2 x 3 x 3 x '
       '2); the runner\'s grid of each of the 14 cells = the spec\'s, same order, keys unique: %s' % (all_ok and a))
    ok &= all_ok and a
    # ---- the two lists
    G = C.grid('BTC', '240')
    K = [C.key(p) for p in G]
    sk = [tuple(s[k] for k in C.SIGNAL_DIMS) for s in C.SIGNALS]
    xk = [tuple(x[k] for k in C.EXIT_DIMS) for x in C.EXITS]
    c = (len(sk) == 288 == len(set(sk)) and len(xk) == 72 == len(set(xk))
         and list(C.SIGNAL_DIMS) + list(C.EXIT_DIMS) == C.DIM_NAMES == SPEC_DIMS
         and all(list(s) == SPEC_DIMS[:7] for s in C.SIGNALS) and all(list(x) == SPEC_DIMS[7:] for x in C.EXITS)
         and all(len(C.exits_for(s, 'BTC', '240')) == 72 for s in C.SIGNALS)
         and K.count(C.key(SPEC_DEFAULT)) == 1)
    _p('  SIGNALS %d unique (prepare params), EXITS %d unique (simulate params), every signal setting has all 72; the '
       'default setting is one row (row %d): %s' % (len(set(sk)), len(set(xk)), K.index(C.key(SPEC_DEFAULT)), c))
    ok &= c
    # ---- DIMS
    d_ok = [d['name'] for d in C.DIMS] == SPEC_DIMS and len(C.DIMS) == 12 and all(
        {'name', 'values', 'kind'} <= set(d) <= {'name', 'values', 'kind', 'side', 'default'}
        and d['values'] == SPEC_VALUES[d['name']] and [type(v) for v in d['values']] == [type(v) for v in SPEC_VALUES[d['name']]]
        and d['default'] == SPEC_DEFAULT[d['name']] and type(d['default']) is type(SPEC_DEFAULT[d['name']])
        and d['default'] in d['values'] and d['side'] == SPEC_SIDE[d['name']] and d['kind'] == SPEC_KIND[d['name']]
        for d in C.DIMS)
    d_ok &= C.DEFAULT_P == SPEC_DEFAULT and C.DEFAULT is C.DEFAULT_P and list(C.DEFAULT_P) == SPEC_DIMS
    for j, d in enumerate(C.DIMS):
        seen = set(k[j] for k in S)
        d_ok &= set(d['values']) == seen and len(d['values']) == len(seen)
        d_ok &= all(type(v) in (bool, int, float, str) for v in d['values'])
        if d['kind'] == 'ordinal' and d['name'] != 'emaPair':
            d_ok &= list(d['values']) == sorted(d['values'])
    d_ok &= [T_EMA[v] for v in C.DIMS[0]['values']] == sorted(T_EMA.values())          # the pairs in rising order
    none_ok = all(v is not None for k in S for v in k)
    dir_ok = [d['name'] for d in C.DIMS if d['name'] in ('inv', 'gvInv', 'direction')] == ['inv'] \
        and C.DIMS[8]['kind'] == 'categorical' and C.DIMS[8]['values'] == [False, True] and C.DIMS[8]['side'] == 'exit'
    _p('  DIMS: %d dimensions %s; values (in the table\'s order), kinds, sides, defaults as section 14: %s; no dimension '
       'is ever None: %s; the direction dimension is named inv: %s' % (len(C.DIMS), [d['name'] for d in C.DIMS], d_ok,
                                                                       none_ok, dir_ok))
    ok &= d_ok and none_ok and dir_ok
    try:
        ok &= json.loads(json.dumps(C.DIMS)) == C.DIMS
    except Exception as e:      # noqa: BLE001
        ok = False
        _p('  DIMS is not JSON: %r' % (e,))
    # ---- the composite dimensions and the extra columns
    comp = (C.EXIT_STYLES == {k: dict(zip(('tpR', 'maxBarsHeld', 'useTrail'), v)) for k, v in T_STYLE.items()}
            and list(C.EXIT_STYLES) == SPEC_VALUES['exitStyle'] and list(C.INPUT_NAMES) == INPUT_NAMES
            and all(C.ema_pair(k) == v for k, v in T_EMA.items())
            and all(C.inputs_of(dict(zip(SPEC_DIMS, k)), pair, tf) == own_inputs(dict(zip(SPEC_DIMS, k)), pair, tf)
                    for pair in PAIRS for tf in TFS for k in S[::7]))
    _p('  exitStyle: tp5 = tpR 5 / no time stop / no trail, time4 = no target / 4 bars / no trail, trail = no target / '
       'no time stop / trail; emaPair "5/13", "8/21" = (fastEmaLen, slowEmaLen); the input columns %s of a setting = '
       'this file\'s reading: %s' % (INPUT_NAMES, comp))
    ok &= comp
    # ---- the script defaults: this file's copy, the module's, the Pine's own input lines
    m_ok = gvl.DEFAULTS == SCRIPT_DEFAULTS and set(ORDER_INPUTS) == set(gvl.ORDER_KEYS) \
        and set(SCRIPT_DEFAULTS) - ORDER_INPUTS == set(gvl.SIGNAL_KEYS)
    if not m_ok:
        _p('  gvl.DEFAULTS differ from the script defaults written here: %r'
           % {k: (gvl.DEFAULTS.get(k), SCRIPT_DEFAULTS.get(k)) for k in set(gvl.DEFAULTS) | set(SCRIPT_DEFAULTS)
              if gvl.DEFAULTS.get(k) != SCRIPT_DEFAULTS.get(k)})
    pin = pine_inputs()
    found = [k for k in SCRIPT_DEFAULTS if k in pin]
    diff = {k: (SCRIPT_DEFAULTS[k], pin[k][0]) for k in found
            if not (SCRIPT_DEFAULTS[k] == pin[k][0] and isinstance(SCRIPT_DEFAULTS[k], bool) == isinstance(pin[k][0], bool))}
    missing = sorted(set(SCRIPT_DEFAULTS) - set(found) - REPLICA_CONTROLS)
    pine_default = None
    if not missing:
        pine_default = dict(zip(SPEC_DIMS, (
            '%d/%d' % (pin['fastEmaLen'][0], pin['slowEmaLen'][0]), pin['trendFilterLen'][0], pin['preMinVolScore'][0],
            pin['preMinVolRise'][0], pin['preCloseLocation'][0], pin['preUseTrend'][0], pin['fgfOn'][0],
            pin['preCandleEntryMode'][0], pin['gvInv'][0],
            pin['slAtrMult'][0],
            [k for k, v in T_STYLE.items() if v == (pin['tpR'][0], pin['maxBarsHeld'][0], pin['useTrail'][0])][0],
            pin['useDailyLossLock'][0])))
    p_ok = (not diff and not missing and pine_default == SPEC_DEFAULT
            and pin['qtyStep'] == (0.001, 0.000001) and pin['maxQty'][0] == 50.0 and pin['riskPct'][0] == 1.0
            and C.SCALE_FREE == {'maxQty': 1e9, 'qtyStep': 0.000001}
            and C.SCRIPT_SIZING == {'maxQty': 50.0, 'qtyStep': 0.001}
            and C.SCALE_FREE['qtyStep'] >= pin['qtyStep'][1] and C.TV_MARGIN == 0.0)
    _p('  script defaults: gvl.DEFAULTS = the %d written here: %s; the Pine file\'s own input lines give the same '
       'default for %d of them (different: %s; not found: %s); the 12 dimensions\' Pine defaults = DEFAULT_P: %s; the '
       'Pine\'s max quantity 50 and quantity step 0.001 (minval 0.000001 = the grid\'s step); tvMargin 0: %s'
       % (len(SCRIPT_DEFAULTS), m_ok, len(found), diff or 'none', missing or 'none', pine_default == SPEC_DEFAULT, p_ok))
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
    # ---- floor_ok is measured, not assumed (added by the sceptic: every cell's data give True, so a hard-coded
    #      True would pass everything else): with a trailing distance below the floor, the cell's measurement
    #      says False, and so does floor_ok on the "trail" rows (only) of the sweep's table and of --one
    Pp = gvl.prepare('XAU', '240', {})
    p10x = _own_p10('XAU', '240')[0]
    saved = dict(C.TRAIL_D)
    fl = {}
    try:
        for d in (0.1, 0.2):            # 0.1 x 0.311 % = 0.031 % < 0.05 % <= 0.2 x 0.311 % = 0.062 %
            C.TRAIL_D[('XAU', '240')] = d
            fl[d] = C.cell_floor('XAU', '240', Pp)
        C.TRAIL_D[('XAU', '240')] = 0.1
        one_lo = {es: C.one('XAU', '240', dict(SPEC_DEFAULT, exitStyle=es))['floor_ok'] for es in T_STYLE}
        fake = dict(pair='XAU', tf='240', idx=[0], floor=fl[0.1], cols=['trades'], kinds={'trades': int})
        tb = C.table(fake, {0: [(0,)] * 72}, [0]).to_pandas()
    finally:
        C.TRAIL_D.clear()
        C.TRAIL_D.update(saved)
    tb_ok = len(tb) == 72 and [bool(v) for v in tb['floor_ok']] == [es != 'trail' for es in tb['p_exitStyle']]
    fo_ok = (fl[0.1]['floor_ok'] is False and fl[0.2]['floor_ok'] is True
             and abs(fl[0.1]['p10_atr_pct'] - p10x) < 1e-6 and abs(fl[0.1]['dist_pct_at_p10'] - 0.1 * fl[0.1]['p10_atr_pct']) < 1e-12
             and fl[0.1]['floor_pct'] == T_FLOOR['XAU'] and one_lo == {'tp5': True, 'time4': True, 'trail': False} and tb_ok
             and C.floor_ok(dict(SPEC_DEFAULT, exitStyle='trail'), {'floor_ok': False}) is False
             and C.floor_ok(dict(SPEC_DEFAULT, exitStyle='tp5'), {'floor_ok': False}) is True
             and C.trail_pair('XAU', '240') == (2.0, 1.0))
    _p('  floor_ok is measured: XAU 240 with a trailing distance of 0.1 ATR (%.4f %% < 0.05 %%) -> floor_ok %s, with 0.2 ATR '
       '(%.4f %%) -> %s; --one with 0.1 ATR: %s; the table\'s column with that floor is False on the 24 "trail" rows and '
       'True on the others: %s: %s' % (fl[0.1]['dist_pct_at_p10'], fl[0.1]['floor_ok'], fl[0.2]['dist_pct_at_p10'],
                                       fl[0.2]['floor_ok'], one_lo, tb_ok, fo_ok))
    ok &= fo_ok
    _free()
    # ---- the gvl params of every setting, all 14 cells
    n_bad = n_all = 0
    def_ok = True
    for pair in PAIRS:
        for tf in TFS:
            Gc = C.grid(pair, tf)
            for p in Gc:
                sp = C.signal_params({k: p[k] for k in C.SIGNAL_DIMS})
                xp = C.exit_params({k: p[k] for k in C.EXIT_DIMS}, pair, tf)
                eff = gvl._params({**sp, **xp})
                want = gvl_params(p, pair, tf)
                n_all += 1
                if eff != want or (set(sp) & ORDER_INPUTS) or (set(xp) - ORDER_INPUTS) \
                        or any(type(eff[k]) is not type(want[k]) for k in want):
                    n_bad += 1
                    if n_bad <= 3:
                        _p('  MAPPING %s %s %r: %r' % (pair, tf, p, {k: (eff.get(k), want.get(k)) for k in want
                                                                      if eff.get(k) != want.get(k)
                                                                      or type(eff.get(k)) is not type(want.get(k))}))
            eff_d = gvl._params({**C.signal_params({k: SPEC_DEFAULT[k] for k in C.SIGNAL_DIMS}),
                                 **C.exit_params({k: SPEC_DEFAULT[k] for k in C.EXIT_DIMS}, pair, tf)})
            eff_s = gvl._params({**C.signal_params({k: SPEC_DEFAULT[k] for k in C.SIGNAL_DIMS}),
                                 **C.exit_params({k: SPEC_DEFAULT[k] for k in C.EXIT_DIMS}, pair, tf, 'tv', 'tv', True)})
            def_ok &= (eff_d == dict(SCRIPT_DEFAULTS, path='mag', cost='ours', maxQty=1e9, qtyStep=0.000001)
                       and eff_s == SCRIPT_DEFAULTS)
    def_ok &= C.PATH == 'mag' and C.COST == 'ours'
    _p('  gvl params of all %d settings of the 14 cells (signal_params + exit_params, resolved by gvl._params) = the '
       'mapping written here (%d keys each, values and types; maxQty 1e9, qtyStep 0.000001, tvMargin 0, the cell\'s '
       'trailing pair): %d different; signal params only prepare keys, exit params only simulate keys'
       % (n_all, len(SCRIPT_DEFAULTS), n_bad))
    _p('  the default setting\'s params = the script defaults with path mag, cost ours and the scale-free sizing; with '
       'script sizing, path tv and cost tv they ARE the script defaults: %s' % def_ok)
    ok &= n_bad == 0 and def_ok
    # ---- normalize: every grid row round-trips, as the file gives it (p_ prefix) and without the prefix
    n_rt = sum(C.normalize({'p_' + k: v for k, v in p.items()}) == p and C.normalize(dict(p)) == p for p in G)
    coerced = C.normalize(dict(SPEC_DEFAULT, trendFilterLen=100.0, preMinVolScore=35, preUseTrend=1, inv=0, emaPair='8 / 21'.replace(' ', '')))
    r_ok = (n_rt == len(G) and coerced == SPEC_DEFAULT and [type(v) for v in coerced.values()] == [type(v) for v in SPEC_DEFAULT.values()]
            and C.row_of('BTC', '240', SPEC_DEFAULT) == K.index(C.key(SPEC_DEFAULT))
            and [C.row_of('XAU', '5', p) for p in G[::997]] == list(range(0, len(G), 997))
            and C.row_of('BTC', '240', dict(SPEC_DEFAULT, slAtrMult=1.5)) is None)
    _p('  normalize(): %d of %d grid rows round-trip (with and without the p_ prefix); 100.0 / 35 / 1 / 0 are read as '
       'the int / float / booleans they mean; row_of() = the row number: %s' % (n_rt, len(G), r_ok))
    ok &= r_ok
    # ---- on data: a trailing distance cannot change a row whose exit style has no trail
    rng = np.random.default_rng(20261126)
    cnt = dif = live = 0
    for pair, tf in CELLS:
        sub = None
        for si in rng.choice(288, size=4, replace=False):
            Pp = gvl.prepare(pair, tf, C.signal_params(C.SIGNALS[int(si)]))
            sub = sub or gvl.get_sub(Pp)
            Pp['sub'] = sub
            for i in rng.choice(72, size=8, replace=False):
                x = C.EXITS[int(i)]
                xp = C.exit_params(x, pair, tf)
                s0 = gvl.summary(Pp, gvl.simulate(Pp, xp))
                sa = gvl.summary(Pp, gvl.simulate(Pp, dict(xp, trailActAtr=0.5, trailDstAtr=0.05)))
                sb = gvl.summary(Pp, gvl.simulate(Pp, dict(xp, trailActAtr=13.0, trailDstAtr=6.5)))
                changed = not all(_same(s0[k], sa[k]) and _same(s0[k], sb[k]) for k in s0)
                if x['exitStyle'] == 'trail':
                    live += changed
                else:
                    cnt += 1
                    dif += changed
        _free()
    u_ok = dif == 0 and cnt > 10 and live > 0
    _p('  on data (%s): other trailing distances (0.5 / 0.05 and 13 / 6.5 ATR) on rows without a trailing stop: %d of '
       '%d results change (so the columns trailActAtr / trailDstAtr are null there); on "trail" rows they do change '
       'results (%d rows): %s' % (', '.join('%s %s' % c for c in CELLS), dif, cnt, live, u_ok))
    ok &= u_ok
    # ---- the files
    fd = os.path.join(OUT, 'calib_gvl_dims.json')
    if os.path.exists(fd):
        same = json.load(open(fd)) == C.DIMS
        _p('  out/calib_gvl_dims.json equals DIMS: %s' % same)
        ok &= same
    else:
        _p('  out/calib_gvl_dims.json: not written yet')
    cols_want = None
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        if cols_want is None:
            Pp = gvl.prepare(pair, tf, {})
            s = gvl.summary(Pp, gvl.simulate(Pp, {'path': 'mag', 'cost': 'ours'}))
            cols_want = list(s.keys())
            scalar = all(isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool) for v in s.values())
        keys = _keys(df)
        ins = [own_inputs(dict(zip(SPEC_DIMS, k)), pair, tf) for k in keys]
        in_ok = all([_py(v) for v in df[c].tolist()] == [q[c] for q in ins] for c in INPUT_NAMES)
        f_ok = (len(df) == N_GRID and keys == S
                and list(df.columns) == _pcols() + INPUT_NAMES + ['floor_ok'] + cols_want and scalar and in_ok
                and all(k in cols_want for k in SUM_REQUIRED) and df['floor_ok'].dtype == bool and bool(df['floor_ok'].all())
                and not df[_pcols()].isna().any().any()
                and [str(df[c].dtype) for c in INPUT_NAMES] == ['int64', 'int64', 'float64', 'int64', 'bool', 'float64', 'float64'])
        nulls = {c: int(df[c].isna().sum()) for c in _rescols(df) if df[c].isna().any()}
        f_ok &= set(nulls) <= {'pf', 'win_pct', 'avg_bars_held', 'trailActAtr', 'trailDstAtr'} \
            and nulls.get('trailActAtr') == N_GRID * 2 // 3 == nulls.get('trailDstAtr')
        _p('  %s: %d rows; p_ columns = the grid in order, never null; columns = %d p_ + the %d input columns (= this '
           'file\'s reading of every row) + floor_ok (True on every row) + the %d fields of gvl.summary (all scalars), '
           'nothing else: %s (missing values: %s)'
           % (src, len(df), len(_pcols()), len(INPUT_NAMES), len(cols_want), f_ok, nulls or 'none'))
        ok &= f_ok
        meta = C.read_meta(_cell_path(pair, tf))
        now = C.file_meta(pair, tf, N_GRID)
        act, dst = T_TRAIL.get((pair, tf), (2.0, 1.0))
        m_ok = meta is not None and all(meta.get(k) == now[k] for k in (
            'strategy', 'pair', 'tf', 'path', 'cost', 'settings', 'window', 'maxQty', 'qtyStep', 'tvMargin', 'trailActAtr',
            'trailDstAtr', 'exit_styles')) and bool((meta.get('floor') or {}).get('floor_ok')) \
            and (meta['strategy'], meta['pair'], meta['tf'], meta['path'], meta['cost'], meta['settings'], meta['maxQty'],
                 meta['qtyStep'], meta['tvMargin'], meta['trailActAtr'], meta['trailDstAtr'], tuple(meta['window'])) \
            == ('gvl', pair, tf, 'mag', 'ours', N_GRID, 1e9, 0.000001, 0.0, act, dst, WINDOWS[pair])
        cur = meta is not None and meta.get('gvl_sha256') == now['gvl_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
        _p('    file metadata: %s, path %s, cost %s, %s settings, maxQty %s, qtyStep %s, tvMargin %s, trailing (%s, %s): '
           '%s; written with the gvl.py and fgf.py now on disk: %s'
           % ((meta or {}).get('strategy'), (meta or {}).get('path'), (meta or {}).get('cost'),
              (meta or {}).get('settings'), (meta or {}).get('maxQty'), (meta or {}).get('qtyStep'),
              (meta or {}).get('tvMargin'), (meta or {}).get('trailActAtr'), (meta or {}).get('trailDstAtr'), m_ok,
              cur if cur else 'NO (rows are still checked against the module by tests 2, 3 and 7)'))
        ok &= m_ok
    _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 2. the default rows against the saved results
# ---------------------------------------------------------------------------------------------
def _one(pair, tf, p, *extra):
    cmd = [sys.executable, '-I', os.path.join(W, 'calib_gvl.py'), '--one', pair, tf, json.dumps(p)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _json_ref(sv, cols):
    """A saved run of out/inv_gvl_*.json as python values (its writer stores NaN as null, inf as 'inf')."""
    ref = {}
    for k in cols:
        v = sv[k]
        ref[k] = float('nan') if v is None else (float(v) if isinstance(v, str) else v)
    return ref


def _summary_cols():
    Pp = gvl.prepare('XAU', '240', {})
    return list(gvl.summary(Pp, gvl.simulate(Pp, {})).keys())


def test_2_default_rows():
    """(2) The default row with --script-sizing, and the same with inv true, equal the saved default results
    of the module with the same path and cost (out/inv_gvl_<PAIR>_<TF>.json; the filter is OFF by default in
    this script): through the command line on BTC 60 and XAU 240, through calib_gvl.one on every saved run
    of all 14 cells; and the scale-free default rows of the sweep equal gvl.run called directly."""
    ok = True
    sc = _summary_cols()
    dp = dict(SPEC_DEFAULT)
    # ---- (a) the command line, BTC 60 and XAU 240
    for pair, tf in (('BTC', '60'), ('XAU', '240')):
        J = json.load(open(os.path.join(OUT, 'inv_gvl_%s_%s.json' % (pair, tf))))
        ss = ('--script-sizing',)
        tv = ('--script-sizing', '--path', 'tv', '--cost', 'tv')
        cases = (
            ('runs', 'normal/off/mag/ours', dp, ss),
            ('runs', 'inverted/off/mag/ours', dict(dp, inv=True), ss),
            ('runs', 'normal/on/mag/ours', dict(dp, fgfOn=True), ss),
            ('runs', 'inverted/on/mag/ours', dict(dp, fgfOn=True, inv=True), ss),
            ('runs', 'normal/off/tv/script', dp, tv),
            ('runs', 'inverted/off/tv/script', dict(dp, inv=True), tv),
            ('runs', 'normal/off/mag/script', dp, ('--script-sizing', '--cost', 'tv')),
            ('runs', 'inverted/on/tv/ours', dict(dp, fgfOn=True, inv=True), ('--script-sizing', '--path', 'tv')),
            ('runs_stop', 'normal/off/mag/ours', dict(dp, preCandleEntryMode=STOP), ss),
            ('runs_stop', 'inverted/off/mag/ours', dict(dp, preCandleEntryMode=STOP, inv=True), ss),
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
            want = (('sizing', 'script'), ('maxQty', 50.0), ('qtyStep', 0.001), ('tvMargin', 0.0), ('in_grid', True),
                    ('path', 'tv' if '--path' in extra else 'mag'), ('cost', 'tv' if '--cost' in extra else 'ours'),
                    ('p', p), ('row', spec_grid().index(tuple(p.values()))))
            if any(st.get(k) != v for k, v in want) or list(o) != INPUT_NAMES + ['floor_ok'] + sc:
                bad.append('%s %s: setting echoed as %r' % (group, key, st))
            n_vals += _cmp(o, _json_ref(J[group][key], sc), sc, '%s %s' % (group, key), bad)
            first.setdefault((group, key), o)
        # the same default row with the grid's sizing (what the sweep stores): another number, by design
        rc, out, err = _one(pair, tf, dp)
        o = json.loads(out) if rc == 0 else None
        d = first.get(('runs', 'normal/off/mag/ours'))
        di = first.get(('runs', 'inverted/off/mag/ours'))
        _p('  %s %-3s command line: default row --script-sizing = saved run normal/off/mag/ours, with inv true = '
           'inverted/off/mag/ours; also filter on, tv path / script costs, "Stop Next Candle" = runs_stop: %d runs, %d '
           'values: %s' % (pair, tf, len(cases), n_vals, _txt(bad)))
        if o is not None and d is not None and di is not None:
            _p('    default row, script sizing (the published file): %d trades, net %+.3f %%, h1r %+.3f %%, h2r %+.3f %%, '
               'net %+.1f R (inverted: %d trades, net %+.3f %%, %+.1f R); scale-free sizing (the grid row %d): %d trades, '
               'net %+.3f %%, h1r %+.3f %%, h2r %+.3f %%, net %+.1f R'
               % (d['trades'], d['net_pct'], d['h1r_pct'], d['h2r_pct'], d['net_r'], di['trades'], di['net_pct'],
                  di['net_r'], o['setting']['row'], o['trades'], o['net_pct'], o['h1r_pct'], o['h2r_pct'], o['net_r']))
        ok &= not bad and n_vals == len(cases) * len(sc) and o is not None and o['setting']['sizing'] == 'scale-free' \
            and o['setting']['maxQty'] == 1e9 and o['setting']['qtyStep'] == 0.000001
    # ---- (b) every saved run of runs and runs_stop of all 14 cells through calib_gvl.one (script sizing)
    tot = dict(cells=0, runs=0, vals=0)
    for pair in PAIRS:
        for tf in TFS:
            J = json.load(open(os.path.join(OUT, 'inv_gvl_%s_%s.json' % (pair, tf))))
            cache = {}
            bad = []
            n_runs = n_vals = 0
            if not set(sc) <= set(J['runs']['normal/off/mag/ours']):
                bad.append('the saved runs miss fields: %s' % (set(sc) - set(J['runs']['normal/off/mag/ours'])))
            for g, mode in (('runs', MARKET), ('runs_stop', STOP)):
                for key, sv in J[g].items():
                    dname, flt, path, cname = key.split('/')
                    cost = 'tv' if cname == 'script' else 'ours'
                    p = dict(dp, fgfOn=flt == 'on', inv=dname == 'inverted', preCandleEntryMode=mode)
                    want_params = dict(fgfOn=p['fgfOn'], gvInv=p['inv'], path=path, cost=cost)
                    if mode == STOP:
                        want_params['preCandleEntryMode'] = STOP
                    if sv.get('params') != want_params:
                        bad.append('%s %s: saved with params %r' % (g, key, sv.get('params')))
                    o = C.one(pair, tf, p, path, cost, False, True, cache)
                    n_vals += _cmp(o, _json_ref(sv, sc), sc, '%s %s' % (g, key), bad)
                    n_runs += 1
            d = J['runs']['normal/off/mag/ours']
            _p('  %s %-3s: %d saved runs (runs, runs_stop: direction x filter x path x cost) = calib_gvl.one with script '
               'sizing: %d values: %s | saved default mag / ours: %d trades, net %+.3f %%, %+.1f R'
               % (pair, tf, n_runs, n_vals, _txt(bad), d['trades'], d['net_pct'], d['net_r']))
            ok &= not bad and n_runs == 32
            tot['cells'] += 1
            tot['runs'] += n_runs
            tot['vals'] += n_vals
            del cache
            _free()
    _p('  %d cells: %d saved runs, %d values compared (runs_m100 = tvMargin 100 is not a run of this grid: tvMargin is '
       '0 on every row)' % (tot['cells'], tot['runs'], tot['vals']))
    ok &= tot['cells'] == 14
    # ---- (c) the scale-free default rows of the sweep = gvl.run called directly
    di = _default_sig_idx()
    S = spec_grid()
    n_cells = 0
    for pair in PAIRS:
        for tf in TFS:
            if os.path.exists(_out_file(pair, tf)) or (pair, tf) in CELLS:
                df, _ = _cell_df(pair, tf)
                src = 'file'
            elif FILES_ONLY:
                continue
            else:
                df, _ = C.run_cell(pair, tf, workers=3, sig_idx=di, write=False, verbose=False)
                src = '%d rows run here' % len(df)
            idx = {k: i for i, k in enumerate(_keys(df))}
            base = {'path': 'mag', 'cost': 'ours', 'maxQty': 1e9, 'qtyStep': 0.000001}
            bad = []
            n_vals = 0
            rows = {}
            dk = tuple(SPEC_DEFAULT.values())
            for name, key, q in (
                    ('normal, filter off (THE default row)', dk, {}),
                    ('inverted, filter off', dk[:8] + (True,) + dk[9:], {'gvInv': True}),
                    ('normal, filter on', dk[:6] + (True,) + dk[7:], {'fgfOn': True}),
                    ('inverted, filter on', dk[:6] + (True, dk[7], True) + dk[9:], {'fgfOn': True, 'inv': True}),
                    ('Stop Next Candle', dk[:7] + (STOP,) + dk[8:], {'preCandleEntryMode': STOP}),
                    ('no daily lock', dk[:11] + (False,), {'useDailyLossLock': False})):
                row = df.iloc[idx[key]]
                n_vals += _cmp(row, _run_summary(pair, tf, dict(base, **q)), sc, name, bad)
                rows[name] = row
            d = rows['normal, filter off (THE default row)']
            pos_ok = src != 'file' or idx[dk] == S.index(dk)
            _p('  %s %-3s (%s): default rows (normal / inverted x filter off / on, Stop mode, lock off) = gvl.run with '
               'path mag, cost ours, maxQty 1e9, qtyStep 0.000001: %d values: %s | default row: %d trades, net %+.3f %%, '
               'h1r %+.3f %%, h2r %+.3f %%, net %+.1f R, zero_qty %d'
               % (pair, tf, src, n_vals, _txt(bad), d['trades'], d['net_pct'], d['h1r_pct'], d['h2r_pct'], d['net_r'],
                  d['zero_qty']))
            ok &= not bad and pos_ok and list(_keys(df)).count(dk) == 1
            n_cells += 1
            _free()
    _p('  %d cells: the scale-free default rows equal gvl.run called directly' % n_cells)
    return ok and n_cells > 0


# ---------------------------------------------------------------------------------------------
# 3. random rows through --one
# ---------------------------------------------------------------------------------------------
def test_3_one_rows():
    """(3) 30 random rows per cell recomputed one at a time through `calib_gvl.py --one` (a new process each,
    the row's p_ columns as its JSON) equal the sweep rows on every other column; the same rows through
    gvl.run with this file's own mapping; --path / --cost and --script-sizing are honoured; --off-grid;
    bad input is refused."""
    ok = True
    rng = np.random.default_rng(31)
    S = spec_grid()
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        rc_cols = _rescols(df)
        sc = _sumcols(df)
        keys = _keys(df)
        pick = sorted(int(i) for i in rng.choice(len(df), size=30, replace=False))
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
            if st != {'strategy': 'gvl', 'pair': pair, 'tf': tf, 'path': 'mag', 'cost': 'ours', 'p': p, 'in_grid': True,
                      'row': i, 'sizing': 'scale-free', 'maxQty': 1e9, 'qtyStep': 0.000001, 'tvMargin': 0.0,
                      'cell_trail': list(T_TRAIL.get((pair, tf), (2.0, 1.0)))} or S[i] != keys[i]:
                bad.append('row %d: setting echoed as %r' % (i, st))
            if list(o) != rc_cols:
                bad.append('row %d: fields %r' % (i, list(o)))
                continue
            n_vals += _cmp(row, o, rc_cols, 'row %d --one' % i, bad)
            ref = _run_summary(pair, tf, gvl_params(p, pair, tf))
            n_run += _cmp(row, ref, sc, 'row %d gvl.run' % i, bad)
            n_run += _cmp(row, own_inputs(p, pair, tf), INPUT_NAMES, 'row %d inputs' % i, bad)
            n_tr += int(row['trades'])
        dt = time.time() - t0
        cov = all(len(cover[n]) >= 2 for n in SPEC_DIMS)
        _p('  %s %s (%s): 30 random rows, each in its own `--one` process: %d values (input columns, floor_ok, summary), '
           'and through gvl.run with the mapping written here: %d values (%d trades): %s; at least two values of every '
           'dimension among them: %s (%.1fs)' % (pair, tf, src, n_vals, n_run, n_tr, _txt(bad), cov, dt))
        ok &= not bad and n_vals == 30 * len(rc_cols) and n_run == 30 * (len(sc) + len(INPUT_NAMES)) and cov
        # --path / --cost, and the control that is not a dimension
        bad = []
        n = 0
        moved = 0
        sub = [pick[j] for j in (0, 10, 20, 29)]
        for i in sub:
            row = df.iloc[i]
            p = dict(zip(SPEC_DIMS, keys[i]))
            for extra, kw in (
                    (('--path', 'tv', '--cost', 'tv'), dict(path='tv', cost='tv')),
                    (('--path', 'mag', '--cost', 'stress'), dict(path='mag', cost='stress')),
                    (('--path', 'tv', '--cost', 'stress'), dict(path='tv', cost='stress')),
                    (('--script-sizing',), dict(script_sizing=True)),
                    (('--script-sizing', '--path', 'tv', '--cost', 'tv'), dict(script_sizing=True, path='tv', cost='tv'))):
                rc, out, err = _one(pair, tf, p, *extra)
                if rc != 0:
                    bad.append('row %d %s: exit code %d' % (i, ' '.join(extra), rc))
                    continue
                o = json.loads(out)
                st = o['setting']
                if (st['path'], st['cost'], st['sizing'], st['maxQty'], st['qtyStep'], st['tvMargin'], st['row'], st['p']) != (
                        kw.get('path', 'mag'), kw.get('cost', 'ours'), 'script' if kw.get('script_sizing') else 'scale-free',
                        50.0 if kw.get('script_sizing') else 1e9, 0.001 if kw.get('script_sizing') else 0.000001, 0.0, i, p):
                    bad.append('row %d %s: echoed %r' % (i, ' '.join(extra), st))
                ref = _run_summary(pair, tf, gvl_params(p, pair, tf, **kw))
                n += _cmp(o, ref, sc, 'row %d %s' % (i, ' '.join(extra)), bad)
                n += _cmp(o, own_inputs(p, pair, tf), INPUT_NAMES, 'row %d %s inputs' % (i, ' '.join(extra)), bad)
                if extra == ('--script-sizing',):
                    moved += not all(_same(o[k], row[k]) for k in sc)
        _p('  %s %s: 4 rows x (--path tv --cost tv | --path mag --cost stress | --path tv --cost stress | '
           '--script-sizing | --script-sizing --path tv --cost tv) = gvl.run with that path, cost and sizing (maxQty 50, '
           'qtyStep 0.001 with --script-sizing; tvMargin 0 always): %d values: %s; rows whose result moves with '
           '--script-sizing: %d of 4' % (pair, tf, n, _txt(bad), moved))
        ok &= not bad and moved > 0 and n == 4 * 5 * (len(sc) + len(INPUT_NAMES))
        _free()
    # bad input
    pair, tf = CELLS[0]
    p = dict(SPEC_DEFAULT)
    cases = (('unknown dimension', dict(p, riskPct=2.0), ()),
             ('an input column given as a dimension', dict(p, tpR=3.0), ()),
             ('value not in the grid', dict(p, slAtrMult=1.5), ()),
             ('EMA pair not in the grid', dict(p, emaPair='3/8'), ()),
             ('missing dimension', {k: v for k, v in p.items() if k != 'inv'}, ()),
             ('null dimension', dict(p, exitStyle=None), ()),
             ('exit style not one of the three', dict(p, exitStyle='tp3'), ('--off-grid',)),
             ('text for a number', dict(p, trendFilterLen='100'), ()),
             ('below the Pine minimum', dict(p, slAtrMult=0.0), ('--off-grid',)),
             ('close location above the Pine maximum', dict(p, preCloseLocation=0.99), ('--off-grid',)),
             ('malformed EMA pair', dict(p, emaPair='8-21'), ('--off-grid',)),
             ('not an object', [1, 2], ()))
    res = []
    for name, q, extra in cases:
        rc, out, err = _one(pair, tf, q, *extra)
        res.append((name, rc, out.strip() == '' and 'calib_gvl.py --one' in err))
    q = dict(p, slAtrMult=1.5, trendFilterLen=150, emaPair='3/8', preCloseLocation=0.7, preMinVolScore=20.0,
             preCandleEntryMode='Signal Only')
    rc, out, err = _one(pair, tf, q, '--off-grid')
    og = rc == 0 and json.loads(out)['setting']['in_grid'] is False and json.loads(out)['setting']['row'] is None
    if og:
        o = json.loads(out)
        ref = _run_summary(pair, tf, gvl_params(q, pair, tf))
        og = all(_same(o[k], ref[k]) for k in ref) and (o['fastEmaLen'], o['slowEmaLen']) == (3, 8) and o['setting']['p'] == q
    b_ok = all(rc == 2 and e for _, rc, e in res) and og
    _p('  bad input is refused (exit code 2, nothing on stdout): %s; --off-grid runs a setting outside the grid (EMA '
       '3/8, trend EMA 150, stop 1.5 ATR, close location 0.7, vol score 20, "Signal Only") = gvl.run: %s'
       % (', '.join('%s -> %d' % (n, rc) for n, rc, _ in res), og))
    return ok and b_ok


# ---------------------------------------------------------------------------------------------
# 4. worker count
# ---------------------------------------------------------------------------------------------
def test_4_workers():
    """(4) XAU 240, the full grid with 1 worker and with 3 workers (files in calib_tmp_gvl/w1 and w3, not
    out/): every row and column identical, and the two files byte for byte; equal to out/ when it exists.
    With 1 worker everything runs in this process: gvl.prepare is called once per signal setting,
    gvl.simulate and gvl.summary once per row, the filter permissions are computed once."""
    d1 = os.path.join(TMP, 'w1')
    d3 = os.path.join(TMP, 'w3')
    calls = dict(prepare=0, simulate=0, summary=0, fgf=0)
    o_prep, o_sim, o_sum, o_fgf = gvl.prepare, gvl.simulate, gvl.summary, fgf.fgf_permissions
    seen_prep = []
    sim_ids = set()

    def c_prep(*a, **k):
        calls['prepare'] += 1
        seen_prep.append(tuple(sorted(a[2].items())))
        return o_prep(*a, **k)

    def c_sim(*a, **k):
        calls['simulate'] += 1
        sim_ids.add(id(a[0]))
        return o_sim(*a, **k)

    def c_sum(*a, **k):
        calls['summary'] += 1
        return o_sum(*a, **k)

    def c_fgf(*a, **k):
        calls['fgf'] += 1
        return o_fgf(*a, **k)

    _free()
    gvl.prepare, gvl.simulate, gvl.summary, fgf.fgf_permissions = c_prep, c_sim, c_sum, c_fgf
    try:
        a, ia = C.run_cell('XAU', '240', workers=1, out_dir=d1, verbose=False)
    finally:
        gvl.prepare, gvl.simulate, gvl.summary, fgf.fgf_permissions = o_prep, o_sim, o_sum, o_fgf
    _free()
    b, ib = C.run_cell('XAU', '240', workers=3, out_dir=d3, verbose=False)
    _free()
    f1 = _tmp_file('XAU', '240', 'w1')
    f3 = _tmp_file('XAU', '240', 'w3')
    fa = pd.read_parquet(f1)
    fb = pd.read_parquet(f3)
    same = fa.equals(fb) and a.equals(b) and a.equals(fa) and len(fa) == N_GRID and list(fa.columns) == list(fb.columns) \
        and all(fa[c].dtype == fb[c].dtype for c in fa.columns)
    byt = _sha(f1) == _sha(f3)
    dims = json.load(open(os.path.join(d1, 'calib_gvl_dims.json'))) == C.DIMS == json.load(open(os.path.join(d3, 'calib_gvl_dims.json')))
    once = (calls == dict(prepare=288, simulate=N_GRID + 1, summary=N_GRID + 1, fgf=1) and len(set(seen_prep)) == 288
            and len(sim_ids) == 288 and ia['prepares'] == 288 == ib['prepares'])
    _p('  XAU 240: %d rows x %d columns; 1 worker %.1fs (runs %.1fs, CPU %.1fs), 3 workers %.1fs (runs %.1fs, CPU %.1fs, '
       'speed-up x%.2f): frames %s, files %s (sha256 %s), dims.json = DIMS: %s'
       % (len(fa), len(fa.columns), ia['t_total'], ia['t_run'], ia['cpu'], ib['t_total'], ib['t_run'], ib['cpu'],
          ia['t_run'] / ib['t_run'], 'identical' if same else 'DIFFERENT', 'byte for byte equal' if byt else 'DIFFERENT bytes',
          _sha(f3)[:16], dims))
    _p('  the 1-worker run called gvl.prepare %d times (%d different signal settings), fgf.fgf_permissions %d time(s) '
       '(the 144 filter-on prepares share it), gvl.simulate %d and gvl.summary %d times (%d rows + 1 to load the '
       'kernel) on %d prepared inputs: signals prepared once per signal setting and reused for all its exit settings: '
       '%s' % (calls['prepare'], len(set(seen_prep)), calls['fgf'], calls['simulate'], calls['summary'], N_GRID,
               len(sim_ids), once))
    _p('  arrays kept for the 288 prepared inputs (distinct per name): %s'
       % ', '.join('%s %d' % kv for kv in ia['distinct'].items()))
    ok = same and byt and dims and once
    fo = _out_file('XAU', '240')
    if os.path.exists(fo):
        fo_df = pd.read_parquet(fo)
        again = fo_df.equals(fb)
        _p('  out/calib_gvl_XAU_240.parquet (the production run) equals this re-run: %s (bytes %s)'
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
    P = cell['P']
    cand = {si: int(np.count_nonzero((P[si]['armL'] | P[si]['armS'] | P[si]['sigL'] | P[si]['sigS']) & P[si]['gate']
                                     & (P[si]['buyOk'] | P[si]['sellOk']))) for si in cell['idx']}
    order = sorted(cell['idx'], key=lambda si: cand[si])
    rng = np.random.default_rng(5)
    groups = (('default', _default_sig_idx()),
              ('random 24', sorted(int(i) for i in rng.choice(288, size=24, replace=False))),
              ('busiest 8', sorted(order[-8:])),
              ('quietest 8', sorted(order[:8])))
    passes = []
    keep = None
    for name, idx in groups:
        res, info = C.run_prepared(cell, workers=3, sig_idx=idx)
        if name == 'default':
            keep = res
        passes.append(dict(name=name, n_sig=len(idx), cand=[cand[si] for si in idx], settings=info['settings'],
                           t_run=info['t_run'], busy=info['busy'], cpu=info['cpu']))
    idx = groups[0][1]
    res1, info1 = C.run_prepared(cell, workers=1, sig_idx=idx)
    same = all(len(res1[k]) == len(keep[k]) and all(_same(x, y) for a, b in zip(res1[k], keep[k]) for x, y in zip(a, b))
               for k in idx)
    zero = sum(1 for k in idx for r in keep[k] if r[cell['cols'].index('zero_qty')] > 0)
    out = dict(bars=cell['bars'], n_sub=cell['n_sub'], t_prep=cell['t_prep'], cpu_prep=cell['cpu_prep'],
               t_fgf=cell['t_fgf'], t_sig=cell['t_sig'], t_sub=cell['t_sub'], t_jit=cell['t_jit'],
               cand=[min(cand.values()), cand[idx[0]], max(cand.values())], uniq=C._distinct(P), passes=passes,
               one_worker=dict(t_run=info1['t_run'], cpu=info1['cpu'], settings=info1['settings'], same=bool(same)),
               default_rows_zero_qty=zero, floor=cell['floor'],
               rss_after_prep_mb=rss_prep, hwm_after_prep_mb=hwm_prep, rss_end_mb=_status_mb('VmRSS:'),
               hwm_end_mb=_status_mb('VmHWM:'), load0=load0, load1=os.getloadavg()[0])
    print('RESULT ' + json.dumps(out), flush=True)
    return 0


def test_5_timing_btc1():
    """(5) BTC 1 (the largest cell), in a fresh process: the real preparation of all 288 signal settings, then
    passes with 3 workers: the 72 exit settings of the 2 default signal settings, of 24 random signal
    settings (a twelfth of the grid), of the 8 busiest and of the 8 quietest; extrapolated to the 288 signal
    settings. The full grid must stay under 45 min, and the process with its 3 workers under 4 GB."""
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
    ps = {q['name']: q for q in r['passes']}
    _p('  BTC 1: %d chart bars, %d 1-minute bars; all 288 signal settings prepared in %.1fs wall / %.1fs CPU (the filter '
       '%.1fs, all signals %.1fs, sub-bars %.1fs, kernel %.1fs); candles that may place an order per signal setting: '
       '%d .. %d (default %d); distinct arrays kept for the 288 prepared inputs: %s'
       % (r['bars'], r['n_sub'], r['t_prep'], r['cpu_prep'], r['t_fgf'], r['t_sig'], r['t_sub'], r['t_jit'], r['cand'][0],
          r['cand'][2], r['cand'][1], ', '.join('%s %d' % kv for kv in r['uniq'].items())))
    for q in r['passes']:
        _p('  pass %-10s (%d signal settings, %d .. %d order candles): %d settings, 3 workers %.1fs (%.4fs per setting '
           'per worker, %.4fs CPU per setting; workers busy %.0f%%)'
           % (q['name'], q['n_sig'], min(q['cand']), max(q['cand']), q['settings'], q['t_run'], q['busy'] / q['settings'],
              q['cpu'] / q['settings'], 100.0 * q['busy'] / (3 * q['t_run'])))
    o1 = r['one_worker']
    _p('  pass default with 1 worker: %.1fs (%.4fs per setting); speed-up of 3 workers x%.2f; rows identical to the '
       '3-worker pass: %s; default-signal rows with a quantity floored to zero: %d of %d'
       % (o1['t_run'], o1['t_run'] / o1['settings'], o1['t_run'] / ps['default']['t_run'], o1['same'],
          r['default_rows_zero_qty'], o1['settings']))
    est = r['t_prep'] + 12 * ps['random 24']['t_run']
    hi = r['t_prep'] + 36 * ps['busiest 8']['t_run']
    cpu = r['cpu_prep'] + 12 * ps['random 24']['cpu'] / 3.0
    _p('  full grid BTC 1 with 3 workers = preparation + 12 x the random pass: %.1fs = %.1f min at the present load; '
       '%.1f min if every signal setting were as slow as the 8 busiest; by CPU time (a free CPU per worker): %.1f min; '
       'limit 45 min; load average %.2f -> %.2f (other jobs share the 4 CPUs)'
       % (est, est / 60.0, hi / 60.0, cpu / 60.0, r['load0'], r['load1']))
    p10 = _own_p10('BTC', '1')[0]
    fl = (abs(r['floor']['p10_atr_pct'] - p10) <= 1e-6 and r['floor']['floor_ok'] is True
          and (r['floor']['trailActAtr'], r['floor']['trailDstAtr']) == T_TRAIL[('BTC', '1')])
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
    _p('  floor of the cell as the run measured it: 10th percentile of ATR(14) / close %.4f %% x %g = %.4f %% >= 0.1 %%, '
       'equal to this file\'s own measurement: %s' % (r['floor']['p10_atr_pct'], r['floor']['trailDstAtr'],
                                                      r['floor']['dist_pct_at_p10'], fl))
    return bool(o1['same']) and hi < 45 * 60.0 and est < 45 * 60.0 and mem_ok and fl


# ---------------------------------------------------------------------------------------------
# 6. what every row must satisfy
# ---------------------------------------------------------------------------------------------
def test_6_row_consistency():
    """Rows hold what they claim, whatever the data: trade counts add up, net = final equity, the window, a
    switch that is off leaves no trace (exit kinds of the exit style, pending orders only in Stop mode,
    nothing blocked with the filter off, no lock with the lock off, no refused or capped quantity), the arm
    and signal counts belong to the signal setting, the input columns to the setting, and every dimension
    changes results somewhere in the cells."""
    ok = True
    live_all = {}
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        K = _keys(df)
        ex = [c for c in df.columns if c.startswith('exit_')]
        pend = [c for c in df.columns if c.startswith('pend_')]
        tr = df['trades']
        st = df['p_exitStyle'].to_numpy(dtype=object)
        mk = (df['p_preCandleEntryMode'] == MARKET).to_numpy(bool)
        fon = df['p_fgfOn'].to_numpy(bool)
        lock = df['p_useDailyLossLock'].to_numpy(bool)
        sigcols = ['p_' + n for n in SPEC_DIMS[:7]]
        per_sig = df.groupby(sigcols)[['arms_long', 'arms_short', 'sig_long', 'sig_short']].nunique()
        arms = df.groupby(['p_trendFilterLen', 'p_preMinVolScore', 'p_preMinVolRise', 'p_preCloseLocation', 'p_preUseTrend'])[
            ['arms_long', 'arms_short']].nunique()
        notrend = df[~df['p_preUseTrend']].groupby(['p_preMinVolScore', 'p_preMinVolRise', 'p_preCloseLocation'])[
            ['arms_long', 'arms_short']].nunique()
        sigs = df.groupby(['p_emaPair', 'p_trendFilterLen'])[['sig_long', 'sig_short']].nunique()
        ins = [own_inputs(dict(zip(SPEC_DIMS, k)), pair, tf) for k in K]
        chk = {
            'trades = long + short': (tr == df['long'] + df['short']).all(),
            'trades = h1_trades + h2_trades': (tr == df['h1_trades'] + df['h2_trades']).all(),
            'trades = sum of the 9 exit kinds': len(ex) == 9 and (tr == df[ex].sum(axis=1)).all(),
            'net_pct = (final_equity - 100000) / 100000': ((df['final_equity'] - INIT) / INIT * 100 == df['net_pct']).all(),
            'half1_pct + half2_pct = net_pct': np.allclose(df['half1_pct'] + df['half2_pct'], df['net_pct'], rtol=1e-12, atol=1e-8),
            'h1_r + h2_r = net_r': np.allclose(df['h1_r'] + df['h2_r'], df['net_r'], rtol=1e-9, atol=1e-8),
            'window': ((df['start'] == WINDOWS[pair][0]) & (df['end'] == WINDOWS[pair][1])).all() and df['bars'].nunique() == 1,
            'tp5: no trail and no time exit': (df.loc[st == 'tp5', ['exit_trail', 'exit_time']] == 0).all().all(),
            'time4: no target and no trail exit': (df.loc[st == 'time4', ['exit_tp', 'exit_trail']] == 0).all().all(),
            'trail: no target and no time exit': (df.loc[st == 'trail', ['exit_tp', 'exit_time']] == 0).all().all(),
            'the older bar exit and the session filter are off: no maxbars / eod exit': (df[['exit_maxbars', 'exit_eod']] == 0).all().all(),
            'Market mode: no pending order, no reversal': len(pend) == 6 and (df.loc[mk, pend + ['exit_reverse']] == 0).all().all(),
            'Market mode: every order fills but one placed on the last bar': ((df.loc[mk, 'orders_placed'] - tr[mk]).isin([0, 1])).all(),
            'Market mode: no trade is open when the lock starts (no daily_lock exit)': (df.loc[mk, 'exit_daily_lock'] == 0).all(),
            'Stop mode: pending orders filled <= placed <= orders placed': ((df.loc[~mk, 'pend_filled'] <= df.loc[~mk, 'pend_placed'])
                                                                           & (df.loc[~mk, 'pend_placed'] <= df.loc[~mk, 'orders_placed'])).all(),
            'filter off: nothing blocked': (df.loc[~fon, ['blocked_long', 'blocked_short']] == 0).all().all(),
            'blocked <= raw': ((df['blocked_long'] <= df['raw_long']) & (df['blocked_short'] <= df['raw_short'])).all(),
            'lock off: no locked bar, no lock day, no daily_lock exit': (df.loc[~lock, ['locked_bars', 'lock_days', 'exit_daily_lock']] == 0).all().all(),
            'tvMargin 0: no entry refused': (df['margin_refused'] == 0).all(),
            'maxQty 1e9 never binds': (df['qty_capped_max'] == 0).all(),
            'arm and signal counts depend on the signal setting only': (per_sig == 1).all().all() and len(per_sig) == 288,
            'arm counts depend on the five arm dimensions only (not on the EMA pair or the filter)': (arms == 1).all().all() and len(arms) == 72,
            'without preUseTrend the arm counts do not depend on the trend EMA': (notrend == 1).all().all() and len(notrend) == 12,
            'signal counts depend on the EMA pair and the trend EMA only': (sigs == 1).all().all() and len(sigs) == 6,
            'pf / win NaN only without trades': ((df['pf'].isna() == (tr == 0)) & (df['win_pct'].isna() == (tr == 0))).all(),
            'costs > 0 with trades': ((df['costs'] > 0) == (tr > 0)).all(),
            'money finite': np.isfinite(df[['h1r_pct', 'h2r_pct', 'net_pct', 'max_dd_pct', 'net_r', 'h1_r', 'h2_r', 'final_equity']].to_numpy()).all(),
            'max_dd >= 0': (df['max_dd_pct'] >= 0).all(),
            'reentry_extreme <= reentry_same_bar <= trades; reentry_gap_r = 0 on mag': ((df['reentry_extreme'] <= df['reentry_same_bar'])
                                                                                        & (df['reentry_same_bar'] <= tr) & (df['reentry_gap_r'] == 0)).all(),
            'at most one trade closed by the window end': (df['exit_end'] <= 1).all(),
            'floor_ok on every row': bool(df['floor_ok'].all()),
            'the input columns belong to the setting': all([_py(v) for v in df[c].tolist()] == [q[c] for q in ins] for c in INPUT_NAMES),
        }
        failed = [k for k, v in chk.items() if not bool(v)]
        # every dimension changes results: groups of rows that differ only in that dimension
        sc = _sumcols(df)
        sig = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
        parts = []
        n_rows_g = 0
        for j, name in enumerate(SPEC_DIMS):
            gkey = [repr(k[:j] + k[j + 1:]) for k in K]
            g = pd.Series(sig).groupby(gkey).agg(['size', 'nunique'])
            n_all = int((g['nunique'] == g['size']).sum())
            n_any = int((g['nunique'] > 1).sum())
            live_all[name] = live_all.get(name, 0) + n_any
            n_rows_g += int(g['size'].sum())
            sizes_ok = bool((g['size'] == len(SPEC_VALUES[name])).all()) and len(g) == N_GRID // len(SPEC_VALUES[name])
            parts.append('%s %d / %d / %d%s' % (name, n_all, n_any, len(g), '' if sizes_ok else ' GROUPS WRONG'))
            ok &= sizes_ok
        # every row has its direction twin (inv flipped) in the file, and never its result
        pos = {k: i for i, k in enumerate(K)}
        twin = np.array([pos[k[:8] + (not k[8],) + k[9:]] for k in K])
        same_twin = int(((sig == sig[twin]) & (tr.to_numpy() > 0)).sum())
        twin_sig = bool(((df['arms_long'].to_numpy() == df['arms_long'].to_numpy()[twin])
                         & (df['sig_short'].to_numpy() == df['sig_short'].to_numpy()[twin])).all())
        # the orchestrator's analysis reads the file with its own coding of DIMS: every value must be in DIMS
        try:
            import calib_analyze
            codes = calib_analyze.codes_of(df, C.DIMS)
            jdir = next(j for j, d in enumerate(C.DIMS) if d['name'].lower() in calib_analyze.DIR_NAMES)
            an = (C.DIM_NAMES[jdir] == 'inv' and bool((codes >= 0).all()) and len(np.unique(codes, axis=0)) == len(df)
                  and 'floor_ok' in df.columns
                  and [int(c) for c in codes[pos[tuple(SPEC_DEFAULT.values())]]] == [1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0]
                  and len(calib_analyze.neighbours(codes, C.DIMS, jdir, pos[tuple(SPEC_DEFAULT.values())])) == 1 + 2 + 1 + 1 + 2 + 1 + 1 + 1 + 2 + 2 + 1)
            an_txt = ('calib_analyze.codes_of reads every p_ value (direction dimension inv; no value unused; the '
                      'default row has 15 neighbours: one step in each ordinal dimension, any other value in each '
                      'categorical one, the direction never): %s' % an)
        except Exception as e:      # noqa: BLE001
            an = False
            an_txt = 'calib_analyze.codes_of FAILED: %r' % (e,)
        n_distinct = len(np.unique(sig))
        el = ((df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).to_numpy(bool)
        cand = int((el & (df['h1r_pct'] > 0).to_numpy(bool) & (df['h2r_pct'] > 0).to_numpy(bool)).sum())
        zq = int((df['zero_qty'] > 0).sum())
        _p('  %s %s (%s): %d rows, %d checks: %s' % (pair, tf, src, len(df), len(chk),
                                                     'all hold' if not failed else 'FAILED: ' + '; '.join(failed)))
        _p('    groups differing only in one dimension (all results distinct / some distinct / groups): %s' % '; '.join(parts))
        _p('    trades %d .. %d (median %d); distinct results %d of %d rows; rows with trades that equal their direction '
           'twin (inv flipped): %d (the twin has the same arm / signal counts: %s); rows with a quantity floored to '
           'zero: %d, with a quantity set by the script\'s margin cap: %d, with an entry larger than the account: %d '
           '(largest %.1f accounts); rows with >= 30 trades in each half: %d, of which positive in both fair halves: %d'
           % (tr.min(), tr.max(), int(tr.median()), n_distinct, len(df), same_twin, twin_sig, zq,
              int((df['qty_capped_margin'] > 0).sum()), int((df['margin_over'] > 0).sum()), df['max_notional_x'].max(),
              int(el.sum()), cand))
        _p('    every row is in a group of every analysis above (no row dropped): %s; %s' % (n_rows_g == 12 * len(df), an_txt))
        ok &= not failed and same_twin == 0 and twin_sig and n_rows_g == 12 * len(df) and an
    dead = [k for k, v in live_all.items() if v == 0]
    _p('  every dimension changes results in at least one group over the cells: %s' % ('yes' if not dead else 'NO: %s' % dead))
    return ok and not dead


# ---------------------------------------------------------------------------------------------
# 7. every row
# ---------------------------------------------------------------------------------------------
def _groups(keys, pair, tf):
    """The rows of a file grouped by their gvl.prepare params (this file's own mapping):
    {prepare key: (prepare params, [(row, simulate params)])}."""
    groups = {}
    for i, k in enumerate(keys):
        prep, sim = _split(gvl_params(dict(zip(SPEC_DIMS, k)), pair, tf))
        groups.setdefault(tuple(sorted((a, repr(b)) for a, b in prep.items())), (prep, []))[1].append((i, sim))
    return groups


def _recompute(pair, tf, df, per_group=None, rng=None):
    """Recompute rows of a file in this process: gvl.prepare once per signal setting (params from this file's
    own mapping), gvl.simulate + gvl.summary per row (all rows, or per_group random rows of every signal
    setting); also this file's reading of the input columns and of floor_ok. Returns (rows checked, values
    compared, rows that differ, signal settings, fields ok)."""
    sc = _sumcols(df)
    keys = _keys(df)
    vals = [df[c].tolist() for c in sc]
    ivals = [df[c].tolist() for c in INPUT_NAMES]
    fl = df['floor_ok'].tolist()
    groups = _groups(keys, pair, tf)
    p10 = _own_p10(pair, tf)[0]
    dst = T_TRAIL.get((pair, tf), (2.0, 1.0))[1]
    n_rows = n_vals = 0
    bad_rows = []
    fields_ok = True
    sub = None
    for gk in sorted(groups):
        prep, items = groups[gk]
        Pp = gvl.prepare(pair, tf, prep)
        if sub is None:
            sub = (Pp['w0'], Pp['w1'], gvl.get_sub(Pp))
        assert (Pp['w0'], Pp['w1']) == sub[:2]
        Pp['sub'] = sub[2]                      # the 1-minute table depends on the window rows only
        if per_group is not None:
            items = [items[j] for j in sorted(int(x) for x in rng.choice(len(items), size=min(per_group, len(items)), replace=False))]
        for i, sim in items:
            s = gvl.summary(Pp, gvl.simulate(Pp, sim))
            if list(s) != sc:
                fields_ok = False
                break
            p = dict(zip(SPEC_DIMS, keys[i]))
            own = own_inputs(p, pair, tf)
            n_rows += 1
            n_vals += len(sc) + len(INPUT_NAMES) + 1
            if not (all(_same(vals[j][i], s[c]) for j, c in enumerate(sc))
                    and all(_same(ivals[j][i], own[c]) for j, c in enumerate(INPUT_NAMES))
                    and fl[i] is bool((not own['useTrail']) or dst * p10 >= T_FLOOR[pair])):
                bad_rows.append(i)
        del Pp
    return n_rows, n_vals, bad_rows, len(groups), fields_ok


def test_7_all_rows():
    """Every row of the cells' files, not a sample: recomputed in this process with gvl.prepare once per
    signal setting and gvl.simulate + gvl.summary per row, the parameters from this file's own mapping
    (gvl_params, split into the prepare and the simulate keys); every summary value, the input columns and
    floor_ok must be equal. A sample of 30 rows cannot see one stale signal setting or one displaced chunk
    of rows; this does."""
    ok = True
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        t0 = time.time()
        c0 = time.process_time()
        n_rows, n_vals, bad_rows, n_groups, fields_ok = _recompute(pair, tf, df)
        c_ok = (fields_ok and not bad_rows and n_groups == 288 and n_rows == len(df) == N_GRID
                and n_vals == len(df) * (len(_sumcols(df)) + len(INPUT_NAMES) + 1))
        _p('  %s %s (%s): all %d rows recomputed (gvl.prepare for each of the %d signal settings, gvl.simulate + '
           'gvl.summary per row): %d values (summary, input columns, floor_ok), %s (%.1fs, CPU %.1fs)'
           % (pair, tf, src, n_rows, n_groups, n_vals,
              'all equal' if c_ok else '%d ROWS DIFFER (first rows %s)%s'
              % (len(bad_rows), bad_rows[:8], '' if fields_ok else '; the summary fields differ'),
              time.time() - t0, time.process_time() - c0))
        ok &= c_ok
        _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 8. every cell that has a file
# ---------------------------------------------------------------------------------------------
def test_8_every_cell():
    """Every cell with a file in out/: the file holds the grid in order with the result columns and its
    metadata, and 2 random rows of EVERY signal setting (576 rows per cell) recomputed in this process
    (gvl.prepare per signal setting, gvl.simulate + gvl.summary per row, this file's own mapping) equal the
    file; when calib_tmp_gvl/w3 holds a scratch run of the cell made with the same runner and replica, the
    two files are equal byte for byte. The other tests read two cells in full and, of the other twelve, only
    the default rows."""
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
            p10, _, _ = _own_p10(pair, tf)
            act, dst = T_TRAIL.get((pair, tf), (2.0, 1.0))
            g_ok = (len(df) == N_GRID and keys == S and all(k in sc for k in SUM_REQUIRED) and meta is not None
                    and list(df.columns) == _pcols() + INPUT_NAMES + ['floor_ok'] + sc
                    and all(meta.get(k) == now[k] for k in ('strategy', 'pair', 'tf', 'path', 'cost', 'settings', 'window',
                                                            'maxQty', 'qtyStep', 'tvMargin', 'trailActAtr', 'trailDstAtr'))
                    and (meta['trailActAtr'], meta['trailDstAtr'], meta['maxQty'], meta['qtyStep'], meta['tvMargin']) == (act, dst, 1e9, 0.000001, 0.0)
                    and bool(((df['start'] == WINDOWS[pair][0]) & (df['end'] == WINDOWS[pair][1])).all())
                    and bool(df['floor_ok'].all()) and dst * p10 >= T_FLOOR[pair]
                    and abs(meta['floor']['p10_atr_pct'] - p10) < 1e-6)
            cur = meta is not None and meta.get('gvl_sha256') == now['gvl_sha256'] and meta.get('fgf_sha256') == now['fgf_sha256']
            n_rows, n_vals, bad_rows, n_groups, fields_ok = _recompute(pair, tf, df, 2, rng)
            h = pd.util.hash_pandas_object(df[sc], index=False).to_numpy()
            c_ok = g_ok and fields_ok and not bad_rows and n_groups == 288 and n_rows == 576
            ft = _tmp_file(pair, tf)
            scratch = ''
            if _fresh(ft) and cur:
                eq = _sha(ft) == _sha(f)
                scratch = '; equal byte for byte to the scratch run calib_tmp_gvl/w3 (the file the tests ran on before this one existed): %s' % eq
                c_ok &= eq
            tr = df['trades']
            el = (df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)
            _p('  %s %-3s: %d rows, the grid in order, columns, metadata, window, floor_ok: %s; written with the gvl.py / '
               'fgf.py now on disk: %s; %d rows (2 of each of the %d signal settings) recomputed: %d values, %s%s; '
               'distinct results %d; trades %d .. %d; rows with zero_qty > 0: %d; rows with >= 30 trades in each half: '
               '%d (%.1fs)'
               % (pair, tf, len(df), g_ok, cur, n_rows, n_groups, n_vals,
                  'all equal' if not bad_rows and fields_ok else '%d ROWS DIFFER: %s' % (len(bad_rows), bad_rows[:8]), scratch,
                  len(np.unique(h)), tr.min(), tr.max(), int((df['zero_qty'] > 0).sum()), int(el.sum()), time.time() - t0))
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
    _p('calib_tests_gvl.py: cells %s; gvl.py sha256 %s; calib_gvl.py sha256 %s; load average %.2f'
       % (', '.join('%s %s' % c for c in CELLS), _sha(os.path.join(W, 'gvl.py'))[:16],
          _sha(os.path.join(W, 'calib_gvl.py'))[:16], os.getloadavg()[0]))
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
    _p('gvl.py sha256 at the end %s' % _sha(os.path.join(W, 'gvl.py'))[:16])
    return 0 if all(res.values()) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
