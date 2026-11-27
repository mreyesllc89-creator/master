"""calib_tests_xpw.py: tests of calib_xpw.py (CALIB_SPEC.md, strategy "xpw").

Usage: python3 -I calib_tests_xpw.py [name filter ...] [--cells XAU:240,BTC:240] [--files-only]
                                     [--exhaustive]

  test_1_grid             the grid is the full product of the spec (27,216 = 18 x 3 x 2 x 252), keys
                          unique, DIMS / SIGNALS / EXITS consistent, every setting maps to the xpw /
                          engine params the spec means (an independent mapping written here), the
                          script defaults written here are the Pine's, the unused dimensions cannot
                          change a result, the files hold the grid in order
  test_2_default          the script's default inputs are NOT on the grid (its exits are 2.0 / 1.0 in
                          price units): the runner's machinery given the default inputs, through
                          `--one --off-grid` with trailUnit price, reproduces the saved default
                          results out/inv_xpw_<PAIR>_<TF>.json (normal / inverted, filter on mag ours,
                          filter off tv script) on BTC 60 and XAU 240; in process, all 16 saved runs
                          of all 14 cells; and the grid rows that have a saved counterpart in
                          out/sweep_<PAIR>_<TF>.parquet (mag, our costs) equal it
  test_3_one_rows         30 random rows per cell recomputed one at a time through
                          `calib_xpw.py --one` (a new process each) equal the sweep rows; the same
                          rows against the canonical engine on the 1-minute series with this file's
                          own mapping; --path / --cost; bad input; --off-grid
  test_4_workers          XAU 240: 1 worker vs 3 workers identical (frames and file bytes)
  test_5_timing_btc1      BTC 1: the real preparation and one pass (the 1512 settings of one signal
                          input, 3 workers) extrapolated to the full grid: under 45 minutes
  test_6_tv_proof         PROOF for sweep_core.prep's fixed inputs: for every non-default value of the
                          grid (maxOpen 1 / 5, fgfBlkClose false, lblRead false, rsiLen 8 / 21, labels
                          legs / div, percent units, stop loss on) the runner's tv-path run equals
                          engine.backtest trade by trade, filter on and off, normal and inverted, on
                          XAU 240, XAU 15, BTC 240, BTC 60 (and the row = run_tf.metrics on that list)
  test_7_mag_proof        the same for the scored path: the runner's mag run equals the canonical
                          engine (engine.backtest_bars) run on the 1-minute bars with the chart's
                          signals and permissions on the last minute of each chart bar, trade by
                          trade, on the same four cells; and mag_ref.py (pure Python) on XAU 240
  test_8_row_consistency  what every row must satisfy whatever the data (counts add up, a switch
                          that is off leaves no trace; twins: an inverted row differs from its normal
                          twin, a switch that never acted leaves the row of its 'off' twin), and
                          every dimension changes results
  test_9_every_row        (sceptic review) EVERY row of the cells' files, not a sample, recomputed in
                          this process without calib_xpw.py from the row's own p_ columns (this
                          file's mapping, sweep_core.prep + the grid's maxOpen / fgfBlkClose applied
                          here, each view tied to engine.backtest): all 32 summary columns

The cells of tests 3, 8 and 9 (and the files of test 1) are --cells (default XAU 240 and BTC 240): the
file out/calib_xpw_<PAIR>_<TF>.parquet when it exists, else the cell is run here with 3 workers
into calib_tmp_xpw/w3/ (never into out/). Test 2 covers all 14 cells: the file when it exists, else
only the default signal input is run in memory (1512 rows; --files-only skips those cells).
--exhaustive adds to test 6 every one of the 27,216 settings of XAU 240 (tv path vs engine.backtest).
Prints PASS / FAIL per test; exit code 1 on a failure.
"""
import collections
import concurrent.futures
import contextlib
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

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import calib_xpw as C     # noqa: E402
import sweep_core as sc   # noqa: E402
import engine             # noqa: E402
import run_tf             # noqa: E402
import xpw                # noqa: E402
import fgf                # noqa: E402

OUT = os.path.join(W, 'out')
TMP = os.path.join(W, 'calib_tmp_xpw')
DATA = os.path.join(W, 'data')
PINE = '/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine'
TFS = ('1', '5', '15', '30', '60', '120', '240')
CELLS = [('XAU', '240'), ('BTC', '240')]
PROOF_CELLS = [('XAU', '240'), ('XAU', '15'), ('BTC', '240'), ('BTC', '60')]
FILES_ONLY = False
EXHAUSTIVE = False
N_GRID = 27216
SRC = ('calib_xpw.py', 'xpw.py', 'fgf.py', 'engine.py', 'sweep_core.py', 'run_tf.py')


def _p(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# this file's own reading of the spec (independent of calib_xpw's lists and mappings)
# ---------------------------------------------------------------------------------------------
SPEC_DIMS = ['rsiLen', 'lblRead', 'labels', 'fgfOn', 'blkClose', 'inv', 'trailOn', 'trailAct', 'trailOff', 'slOn',
             'slDist', 'maxOpen']
SPEC_KIND = {'rsiLen': 'ordinal', 'lblRead': 'categorical', 'labels': 'categorical', 'fgfOn': 'categorical',
             'blkClose': 'categorical', 'inv': 'categorical', 'trailOn': 'categorical', 'trailAct': 'ordinal',
             'trailOff': 'ordinal', 'slOn': 'categorical', 'slDist': 'ordinal', 'maxOpen': 'ordinal'}
SPEC_UNUSED = {'blkClose': ('fgfOn', False), 'trailAct': ('trailOn', False), 'trailOff': ('trailOn', False),
               'slDist': ('slOn', False)}
T_LABELS = {'all': {}, 'legs': {'actDL': 'off', 'actDS': 'off'},
            'div': {'actL1': 'off', 'actL2': 'off', 'actS1': 'off', 'actS2': 'off'}}
# the Pine's input defaults (xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine), as the replicas name them
XPW_SCRIPT = dict(rsiLen=13, fastLen=2, slowLen=7, bbLen=34, bbMult=1.6185, scaleWin=True, flatWin=20, areaLen=5,
                  areaFrac=0.45, trendLen=20, sigRung='chart rung (*)', lblRead=True, actL1='enter', actL2='enter',
                  actS1='enter', actS2='enter', actDL='enter', actDS='enter', actEnd='enter', actInf='enter',
                  agreeOn=False, reverseAll=False, tradeAgree=True)
ENG_SCRIPT = dict(tradeDir='Both', oppCloses=True, fgfOn=True, fgfBlkClose=True, maxOpen=20, trailOn=True,
                  trailUnit='price', trailAct=2.0, trailOff=1.0, slOn=False, slDist=3.0, entryFill='Signal tick',
                  mintick=0.01, xpwInv=False, pyramiding=100)
# the script's default setting in the runner's dimensions (off the grid: price units)
T_DEFAULT = dict(rsiLen=13, lblRead=True, labels='all', fgfOn=True, blkClose=True, inv=False, trailOn=True,
                 trailAct=2.0, trailOff=1.0, slOn=False, slDist=None, maxOpen=20)
KIND_NAME = {1: 'trail', 2: 'sl', 3: 'close_all', 4: 'reverse', 5: 'end'}
SIG_COLS = ['t_close', 'nLong', 'nShort', 'longSrc', 'shortSrc', 'exitL', 'exitS', 'exitLSrc', 'exitSSrc']
METRIC_FIELDS = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'half1_pct', 'half2_pct', 'avg_trade_ret_pct',
                 'max_concurrent', 'exit_trail', 'exit_sl', 'exit_close_all', 'exit_reverse', 'exit_end', 'max_expo',
                 'avg_bars_held', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades', 'h1r_pf', 'h2r_pf')
SPEC_COLS = METRIC_FIELDS + ('long_trades', 'short_trades', 'entries_skipped_room', 'entries_ignored_pyramiding',
                             'close_all_bars', 'max_open', 'raw_long', 'raw_short', 'blocked_long', 'blocked_short')
INT_FIELDS = ('trades', 'max_concurrent', 'exit_trail', 'exit_sl', 'exit_close_all', 'exit_reverse', 'exit_end',
              'h1_trades', 'h2_trades', 'long_trades', 'short_trades', 'entries_skipped_room',
              'entries_ignored_pyramiding', 'close_all_bars', 'max_open', 'raw_long', 'raw_short', 'blocked_long',
              'blocked_short')
SUM_REQUIRED = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
                'exit_trail', 'exit_sl', 'exit_close_all', 'exit_reverse', 'exit_end', 'max_expo', 'avg_bars_held')


def spec_grid():
    """The task's grid for xpw: signals rsiLen {8, 13, 21} x lblRead {true, false} x labels {all, legs, div};
    filter off | on with fgfBlkClose true | on with it false; direction normal | inverted; exits (percent)
    [trailing off | activation {0.2, 0.5, 1, 2, 4} x offset {0.1, 0.3, 1, 3}] x stop loss {off, 0.5, 1.5, 4}
    x maxOpen {1, 5, 20}."""
    G = []
    trails = [(False, None, None)] + [(True, a, o) for a in (0.2, 0.5, 1.0, 2.0, 4.0) for o in (0.1, 0.3, 1.0, 3.0)]
    stops = [(False, None), (True, 0.5), (True, 1.5), (True, 4.0)]
    for r in (8, 13, 21):
        for lr in (True, False):
            for lb in ('all', 'legs', 'div'):
                for fg, blk in ((False, None), (True, True), (True, False)):
                    for inv in (False, True):
                        for ton, ta, to in trails:
                            for son, sd in stops:
                                for mo in (1, 5, 20):
                                    G.append((r, lr, lb, fg, blk, inv, ton, ta, to, son, sd, mo))
    return G


def xpw_params(p):
    """A setting (dict over SPEC_DIMS) as the complete xpw_signals param set, written from the spec."""
    q = dict(XPW_SCRIPT)
    q.update(rsiLen=p['rsiLen'], lblRead=p['lblRead'])
    q.update(T_LABELS[p['labels']])
    return q


def eng_params(p, unit='percent'):
    """A setting as the complete engine.backtest param set, written from the spec."""
    q = dict(ENG_SCRIPT)
    q.update(fgfOn=p['fgfOn'], xpwInv=p['inv'], maxOpen=p['maxOpen'], trailOn=p['trailOn'], slOn=p['slOn'],
             trailUnit=unit)
    if p['fgfOn']:
        q['fgfBlkClose'] = p['blkClose']
    if p['trailOn']:
        q['trailAct'], q['trailOff'] = p['trailAct'], p['trailOff']
    if p['slOn']:
        q['slDist'] = p['slDist']
    return q


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def _isnan(v):
    return v is None or (isinstance(v, (float, np.floating)) and math.isnan(v))


def _same(a, b):
    """Exact equality; NaN / None equal NaN / None."""
    if _isnan(a) or _isnan(b):
        return _isnan(a) and _isnan(b)
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    return float(a) == float(b)


def _close(a, b, rel=1e-9):
    if _isnan(a) or _isnan(b):
        return _isnan(a) and _isnan(b)
    a, b = float(a), float(b)
    return a == b or abs(a - b) <= rel * max(1.0, abs(a), abs(b))


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


def _sumcols(df):
    return [c for c in df.columns if not c.startswith('p_')]


def _out_file(pair, tf):
    return os.path.join(OUT, 'calib_xpw_%s_%s.parquet' % (pair, tf))


def _sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def _fresh(path):
    """A scratch file is used only when it is newer than the runner and the replica modules."""
    return os.path.exists(path) and os.path.getmtime(path) > max(os.path.getmtime(os.path.join(W, f)) for f in SRC)


def _free():
    C.free()
    gc.collect()


_DF = {}


def _cell_df(pair, tf):
    """(DataFrame, where): out/ when the cell's file exists, else calib_tmp_xpw/w3 (run here if needed)."""
    key = (pair, tf)
    if key not in _DF:
        f = _out_file(pair, tf)
        if os.path.exists(f):
            src = 'out/' + os.path.basename(f)
            if not _fresh(f):
                _p('  note: %s is older than calib_xpw.py or a replica module' % src)
        else:
            d3 = os.path.join(TMP, 'w3')
            f = os.path.join(d3, 'calib_xpw_%s_%s.parquet' % (pair, tf))
            src = 'calib_tmp_xpw/w3/' + os.path.basename(f)
            if not _fresh(f):
                t0 = time.time()
                C.run_cell(pair, tf, workers=3, out_dir=d3, verbose=False)
                _p('  %s %s has no file in out/: run here with 3 workers into %s (%.1fs)' % (pair, tf, src, time.time() - t0))
                _free()
        _DF[key] = (pd.read_parquet(f), src, f)
    return _DF[key][0], _DF[key][1]


def _default_sig_idx():
    return [i for i, s in enumerate(C.SIGNALS) if (s['rsiLen'], s['lblRead'], s['labels']) == (13, True, 'all')]


# ---- the slow, canonical path with this file's own mapping -------------------------------------
def stress_cost_per_unit(pair, entry, exitp):
    """run_tf.cost_per_unit with the stressed costs (SWEEP_SPEC_2 2.)."""
    if pair == 'XAU':
        return 0.50 + 0.02
    return 0.00035 * (entry + exitp) + 0.20 + 0.02


@contextlib.contextmanager
def cost_ref(cost):
    """run_tf.metrics() as the reference for cost 'tv' | 'ours' | 'stress': yields its with_cost flag;
    'stress' swaps run_tf.cost_per_unit (looked up at call time) for the stressed one."""
    saved = run_tf.cost_per_unit
    try:
        if cost == 'stress':
            run_tf.cost_per_unit = stress_cost_per_unit
        yield cost != 'tv'
    finally:
        run_tf.cost_per_unit = saved


def ref_max_expo(pair, tr, with_cost):
    """Largest open notional over closed equity seen right after an entry, with run_tf.metrics()'
    money model and event order (exits before entries at one timestamp)."""
    t = tr.sort_values(['exit_time', 'entry_time']).reset_index(drop=True)
    epx = t['entry_px'].to_numpy(float)
    xpx = t['exit_px'].to_numpy(float)
    d = t['dir'].to_numpy(float)
    et = t['entry_time'].to_numpy()
    xt = t['exit_time'].to_numpy()
    pnl = d * (xpx - epx) - (np.array([run_tf.cost_per_unit(pair, a, b) for a, b in zip(epx, xpx)]) if with_cost
                             else np.zeros(len(t)))
    ev = sorted([(xt[i], 0, i) for i in range(len(t))] + [(et[i], 1, i) for i in range(len(t))])
    eq = run_tf.CAP
    qty = np.zeros(len(t))
    state = np.zeros(len(t), np.int8)        # 0 not entered, 1 open, 2 exited
    open_ = {}
    best = -np.inf
    for _, kind, i in ev:
        if kind == 1:
            qty[i] = run_tf.FRAC * max(eq, 0.0) / epx[i]
            if state[i] == 0:
                state[i] = 1
                open_[i] = qty[i] * epx[i]
                best = max(best, (sum(open_.values()) / eq) if eq > 0 else np.inf)
        else:
            eq += qty[i] * pnl[i]
            state[i] = 2
            open_.pop(i, None)
    return best if best > -np.inf else float('nan')


def ref_summary(pair, tr, start, end, cost, es=None):
    """The row of a trade list by the slow path: run_tf.metrics() on the list and on the trades entered
    in each half (fair halves), the exit kinds, the real sides, the slow max_expo; es: the engine's own
    summary (its run and filter counts)."""
    nan = float('nan')
    mid = start + (end - start) // 2
    out = {}
    with cost_ref(cost) as wc:
        m = run_tf.metrics(pair, tr, start, end, wc)
        n = int(m['trades'])
        halves = []
        for part, s0, s1 in ((tr[tr['entry_time'] <= mid], start, mid), (tr[tr['entry_time'] > mid], mid, end)) if n else ():
            halves.append(run_tf.metrics(pair, part, s0, s1, wc))
        me = ref_max_expo(pair, tr, wc) if n else nan
    out['trades'] = n
    if n == 0:
        for k in METRIC_FIELDS[1:]:
            out[k] = 0 if k in INT_FIELDS else nan
    else:
        for k in ('net_pct', 'win_pct', 'max_dd_pct', 'half1_pct', 'half2_pct', 'avg_trade_ret_pct', 'max_concurrent'):
            out[k] = m[k]
        out['pf'] = nan if m['pf'] is None else m['pf']
        kinds = m['exit_kinds']
        for kn in ('trail', 'sl', 'close_all', 'reverse', 'end'):
            out['exit_' + kn] = int(kinds.get(kn, 0))
        out['max_expo'] = me
        out['avg_bars_held'] = float((tr['exit_row'] - tr['entry_row']).mean())
        for h, hm in zip(('h1', 'h2'), halves):
            nt = int(hm['trades'])
            out[h + '_trades'] = nt
            out[h + 'r_pct'] = hm['net_pct'] if nt else nan
            out[h + 'r_pf'] = hm['pf'] if (nt and hm['pf'] is not None) else nan
    out['long_trades'] = int((tr['dir'] > 0).sum()) if n else 0
    out['short_trades'] = n - out['long_trades']
    if es is not None:
        out['entries_skipped_room'] = int(es['entries_skipped_room'])
        out['entries_ignored_pyramiding'] = int(es['entries_ignored_pyramiding'])
        out['close_all_bars'] = int(es['close_all_bars'])
        out['max_open'] = int(es['max_open'])
        for k in ('raw_long', 'raw_short', 'blocked_long', 'blocked_short'):
            out[k] = int(es[k])
        if n != int(es['entries']):
            out['trades'] = -1                    # never equal: the engine's own count disagrees
    return out


CMP_TOL = ('max_expo', 'avg_bars_held')


def cmp_row(row, ref, tag, bad, skip=(), limit=6):
    """row (the runner's summary) vs ref (ref_summary): every field of ref, exactly (the two float
    fields that are not rounded: within 1e-9). Returns the number of values compared."""
    n = 0
    for k, b in ref.items():
        if k in skip:
            continue
        n += 1
        a = row[k]
        ok = _close(a, b) if k in CMP_TOL else _same(a, b)
        if not ok:
            bad.append('%s.%s runner %r ref %r' % (tag, k, a, b) if len(bad) < limit else '')
    return n


class Ref:
    """One cell by the canonical modules alone, with this file's own mapping: xpw.xpw_signals with the
    full param set, fgf.fgf_permissions, engine.backtest (tv) and, for the Bar Magnifier path,
    engine.backtest_bars on the 1-minute bars of the window with every chart bar's labels and
    permissions on its LAST minute (the script then acts only at chart closes, an entry's exit orders
    start at the next minute, every minute has its own O-H-L-C path and gap test). Nothing of
    calib_xpw.py or sweep_core's kernels / metrics is used."""

    def __init__(self, pair, tf):
        self.pair, self.tf = pair, str(tf)
        self.start, self.end = run_tf.WINDOWS[pair]
        self.perm = fgf.fgf_permissions(pair, self.tf, self.start, self.end, {})
        self._sig = {}
        self._sig1 = (None, None)
        self._m = None

    def sig(self, p):
        k = (p['rsiLen'], p['lblRead'], p['labels'])
        if k not in self._sig:
            df = xpw.xpw_signals(self.pair, self.tf, self.start, self.end, xpw_params(p))
            self._sig[k] = df[SIG_COLS].copy()
        return self._sig[k]

    def rows(self):
        return np.asarray(self.perm.index, dtype=np.int64)

    def tv(self, p, unit='percent'):
        """engine.backtest; rows as window positions. Returns (trades, engine summary)."""
        tr, es = engine.backtest(self.pair, self.tf, self.sig(p), self.perm if p['fgfOn'] else None, eng_params(p, unit))
        r0 = int(self.rows()[0])
        tr = tr.copy()
        tr['entry_row'] = tr['entry_row'] - r0
        tr['exit_row'] = tr['exit_row'] - r0
        return tr, es

    def minutes(self):
        """(1-minute bars of the window's chart bars, owner chart position of each minute, position of
        the last minute of each chart bar, chart t_close), from the data files directly."""
        if self._m is None:
            rows = self.rows()
            ch = pd.read_parquet(os.path.join(DATA, '%s_%s.parquet' % (self.pair, self.tf)),
                                 columns=['open', 'high', 'low', 'close', 't_open', 't_close']).reset_index(drop=True).iloc[rows]
            bo = ch['t_open'].to_numpy(np.int64)
            bc = ch['t_close'].to_numpy(np.int64)
            m = pd.read_parquet(os.path.join(DATA, '%s_1.parquet' % self.pair),
                                columns=['open', 'high', 'low', 'close', 't_open', 't_close']).reset_index(drop=True)
            mt = m['t_open'].to_numpy(np.int64)
            owner = np.searchsorted(bo, mt, side='right') - 1
            keep = (owner >= 0) & (mt < bc[np.clip(owner, 0, len(bc) - 1)])
            m = m[keep].reset_index(drop=True)
            owner = owner[keep]
            first = np.flatnonzero(np.r_[True, owner[1:] != owner[:-1]])
            last = np.flatnonzero(np.r_[owner[1:] != owner[:-1], True])
            if not (np.array_equal(owner[last], np.arange(len(bo))) and (np.diff(owner) >= 0).all()):
                raise AssertionError('%s %s: a chart bar has no 1-minute bar' % (self.pair, self.tf))
            ok = ((m['open'].to_numpy()[first] == ch['open'].to_numpy()) & (m['close'].to_numpy()[last] == ch['close'].to_numpy())
                  & (np.maximum.reduceat(m['high'].to_numpy(), first) == ch['high'].to_numpy())
                  & (np.minimum.reduceat(m['low'].to_numpy(), first) == ch['low'].to_numpy()))
            if not ok.all():
                raise AssertionError('%s %s: chart bars differ from their minutes' % (self.pair, self.tf))
            perm1 = pd.DataFrame({'buyOk': np.ones(len(m), bool), 'sellOk': np.ones(len(m), bool)})
            perm1.loc[last, 'buyOk'] = self.perm['buyOk'].to_numpy(bool)
            perm1.loc[last, 'sellOk'] = self.perm['sellOk'].to_numpy(bool)
            self._m = (m, owner, last, bc, perm1)
        return self._m

    def sig1(self, p):
        k = (p['rsiLen'], p['lblRead'], p['labels'])
        if self._sig1[0] != k:
            sig = self.sig(p)
            m, owner, last, bc, perm1 = self.minutes()
            n1 = len(m)
            empty = []
            L = [empty] * n1
            S = [empty] * n1
            for r, pos in enumerate(last.tolist()):
                a = sig['longSrc'].iloc[r]
                b = sig['shortSrc'].iloc[r]
                if len(a):
                    L[pos] = list(a)
                if len(b):
                    S[pos] = list(b)

            def put(col, dtype, fill):
                a = np.full(n1, fill, dtype)
                a[last] = sig[col].to_numpy()
                return a
            df = pd.DataFrame({'longSrc': pd.Series(L, dtype=object), 'shortSrc': pd.Series(S, dtype=object),
                               'nLong': put('nLong', np.int64, 0), 'nShort': put('nShort', np.int64, 0),
                               'exitL': put('exitL', bool, False), 'exitS': put('exitS', bool, False),
                               'exitLSrc': put('exitLSrc', object, ''), 'exitSSrc': put('exitSSrc', object, '')})
            self._sig1 = (k, df)
        return self._sig1[1]

    def mag(self, p, unit='percent'):
        """The Bar Magnifier run by the canonical engine on the minutes; rows / times mapped back to the
        chart bars (window positions, chart closes). Returns (trades, engine summary)."""
        m, owner, last, bc, perm1 = self.minutes()
        tr, es = engine.backtest_bars(m, self.sig1(p), perm1 if p['fgfOn'] else None, eng_params(p, unit))
        e1 = tr['entry_row'].to_numpy(np.int64)
        x1 = tr['exit_row'].to_numpy(np.int64)
        epos = owner[e1]
        xpos = owner[x1]
        if not np.array_equal(last[epos], e1):
            raise AssertionError('an entry of the minute run is not on the last minute of a chart bar')
        tr = tr.copy()
        tr['entry_row'], tr['exit_row'] = epos, xpos
        tr['entry_time'], tr['exit_time'] = bc[epos], bc[xpos]
        return tr, es


def cmp_trades(R, tr, tclose=None):
    """The runner's run (sweep_core.run_cfg arrays) vs a reference trade list, trade by trade: side,
    entry / exit bar, entry / exit price (exact), exit kind, the entry's number within its bar."""
    if R['n'] != len(tr):
        return ['trade count %d vs %d' % (R['n'], len(tr))]
    if R['n'] == 0:
        return []
    checks = [('dir', R['dir'].astype(np.int64), tr['dir'].to_numpy(np.int64)),
              ('entry bar', R['erow'].astype(np.int64), tr['entry_row'].to_numpy(np.int64)),
              ('exit bar', R['xrow'].astype(np.int64), tr['exit_row'].to_numpy(np.int64)),
              ('entry price', R['epx'], tr['entry_px'].to_numpy(np.float64)),
              ('exit price', R['xpx'], tr['exit_px'].to_numpy(np.float64)),
              ('exit kind', np.array([KIND_NAME[int(v)] for v in R['xkind']], dtype=object), tr['exit_kind'].to_numpy(object)),
              ('entry number', R['k'].astype(np.int64), np.array([int(s.split('-')[1]) for s in tr['id']], np.int64))]
    if tclose is not None:
        checks.append(('entry time', tclose[R['erow']], tr['entry_time'].to_numpy(np.int64)))
        checks.append(('exit time', tclose[R['xrow']], tr['exit_time'].to_numpy(np.int64)))
    bad = []
    for name, a, b in checks:
        if not np.array_equal(a, b):
            k = int(np.nonzero(a != b)[0][0])
            bad.append('%s differs at trade %d: %r vs %r' % (name, k, a[k], b[k]))
    return bad


def _row_of(P, R, x, cost):
    return C.summary(P, R, x, cost)


# ---------------------------------------------------------------------------------------------
# 1. the grid
# ---------------------------------------------------------------------------------------------
def _pine_defaults():
    """The defaults of the swept / fixed inputs, read from the Pine source."""
    if not os.path.exists(PINE):
        return None
    src = open(PINE).read()
    want = [(r'^rsiLen\s*=\s*input\.int\(13,', 'rsiLen 13'), (r'^lblRead\s*=\s*input\.bool\(true,', 'lblRead true'),
            (r'^trailOn\s*=\s*input\.bool\(true,', 'trailOn true'),
            (r'^trailUnit\s*=\s*input\.string\("price",[^\n]*options=\["ticks","price","percent"\]', 'trailUnit price (ticks | price | percent)'),
            (r'^trailAct\s*=\s*input\.float\(2\.0,', 'trailAct 2.0'), (r'^trailOff\s*=\s*input\.float\(1\.0,', 'trailOff 1.0'),
            (r'^slOn\s*=\s*input\.bool\(false,', 'slOn false'), (r'^slDist\s*=\s*input\.float\(3\.0,', 'slDist 3.0'),
            (r'^maxOpen\s*=\s*input\.int\(20,[^\n]*minval=1, maxval=100', 'maxOpen 20 (1..100)'),
            (r'^fgfOn\s*=\s*input\.bool\(true,', 'fgfOn true'), (r'^fgfBlkClose\s*=\s*input\.bool\(true,', 'fgfBlkClose true'),
            (r'^xpwInv\s*=\s*input\.bool\(false,', 'xpwInv false'), (r'^reverseAll\s*=\s*input\.bool\(false,', 'reverseAll false'),
            (r'^tradeDir\s*=\s*input\.string\("Both",', 'tradeDir Both'), (r'^oppCloses\s*=\s*input\.bool\(true,', 'oppCloses true'),
            (r'^agreeOn\s*=\s*input\.bool\(false,', 'agreeOn false'), (r'^sigRung\s*=\s*input\.string\("chart rung \(\*\)",', 'sigRung chart rung'),
            (r'^entryFill\s*=\s*input\.string\("Signal tick",', 'entryFill Signal tick'),
            (r'^strategy\([^\n]*pyramiding=100, initial_capital=10000, default_qty_type=strategy\.percent_of_equity, default_qty_value=10, process_orders_on_close=true',
             'strategy(): pyramiding 100, 10 % of equity, capital 10000')]
    for a in ('actL1', 'actL2', 'actS1', 'actS2', 'actDL', 'actDS', 'actEnd', 'actInf'):
        want.append((r'^%s\s*=\s*input\.string\("enter", "", options=\["off","enter","enter opposite","exit only"\]' % a, a + ' enter (off | ...)'))
    missing = [name for rx, name in want if not re.search(rx, src, re.M)]
    return len(want), missing


def _eq_runs(a, b):
    return a['n'] == b['n'] and all(np.array_equal(a[k], b[k]) for k in ('dir', 'erow', 'k', 'epx', 'xrow', 'xpx', 'xkind'))


def test_1_grid():
    """(1) The grid is the full product described, keys unique; DIMS, SIGNALS, EXITS and the xpw / engine
    params of every setting are what the spec says; unused dimensions cannot change a result; the files
    hold it."""
    ok = True
    S = spec_grid()
    G = C.grid()
    K = [C.key(p) for p in G]
    a = len(S) == N_GRID == 18 * 3 * 2 * 252 and len(set(S)) == N_GRID and 252 == (1 + 5 * 4) * 4 * 3
    b = len(G) == N_GRID and len(set(K)) == N_GRID and K == S
    _p('  spec product %d settings (18 signal x 3 filter x 2 direction x 252 exit), runner grid %d, unique keys %d, '
       'same settings in the same order: %s' % (len(S), len(G), len(set(K)), a and b))
    ok &= a and b
    # the two lists
    sk = [tuple(s[k] for k in C.SIGNAL_DIMS) for s in C.SIGNALS]
    xk = [tuple(x[k] for k in C.EXIT_DIMS) for x in C.EXITS]
    n_off = [len(C.exits_for(s)) for s in C.SIGNALS if not s['fgfOn']]
    n_on = [len(C.exits_for(s)) for s in C.SIGNALS if s['fgfOn']]
    c = (len(sk) == 36 == len(set(sk)) and len(xk) == 1512 == len(set(xk)) and set(n_off) == {504} and set(n_on) == {1008}
         and len(n_off) == 18 == len(n_on) and list(C.SIGNAL_DIMS) + list(C.EXIT_DIMS) == C.DIM_NAMES
         and G == [C.merge(s, x) for s in C.SIGNALS for x in C.exits_for(s)]
         and all(set(s) == set(C.SIGNAL_DIMS) for s in C.SIGNALS) and all(set(x) == set(C.EXIT_DIMS) for x in C.EXITS))
    _p('  SIGNALS %d unique (prepare: rsiLen, lblRead, labels, fgfOn), EXITS %d unique (simulate: blkClose, inv, the '
       'exits); exit settings per signal setting: %d with the filter off, %d with it on; grid = SIGNALS x their EXITS '
       'in order: %s' % (len(set(sk)), len(set(xk)), n_off[0], n_on[0], c))
    ok &= c
    # DIMS
    d_ok = [d['name'] for d in C.DIMS] == SPEC_DIMS == C.DIM_NAMES and all(set(d) == {'name', 'values', 'kind'} for d in C.DIMS)
    for j, d in enumerate(C.DIMS):
        vals = [k[j] for k in S if k[j] is not None]
        seen = sorted(set(vals), key=lambda v: (str(type(v)), v))
        d_ok &= sorted(d['values'], key=lambda v: (str(type(v)), v)) == seen and d['kind'] == SPEC_KIND[d['name']]
        d_ok &= all(type(v) in (bool, int, float, str) for v in d['values'])
        if d['kind'] == 'ordinal':
            d_ok &= list(d['values']) == sorted(d['values'])
    jx = {n: j for j, n in enumerate(SPEC_DIMS)}
    none_ok = C.UNUSED_WHEN == SPEC_UNUSED
    for k in K:
        for j, n in enumerate(SPEC_DIMS):
            if n in SPEC_UNUSED:
                sw, when = SPEC_UNUSED[n]
                none_ok &= (k[j] is None) == (k[jx[sw]] == when)
            else:
                none_ok &= k[j] is not None
    _p('  DIMS: %d dimensions %s; values = the grid\'s values, kinds as specified (ordinal values ascending): %s; '
       'None only for blkClose with the filter off, trailAct / trailOff with trailOn False, slDist with slOn False, '
       'and always there: %s' % (len(C.DIMS), [d['name'] for d in C.DIMS], d_ok, none_ok))
    ok &= d_ok and none_ok
    try:
        json.dumps(C.DIMS)
    except Exception as e:      # noqa: BLE001
        ok = False
        _p('  DIMS is not JSON: %r' % (e,))
    floor_ok = min(C.TRAIL_OFFS) >= 0.1 and C.TRAIL_UNIT == 'percent'
    _p('  smallest trail offset %.2f %% >= the 1-minute noise floors (BTC 0.1 %%, XAU 0.05 %%), unit %s: %s'
       % (min(C.TRAIL_OFFS), C.TRAIL_UNIT, floor_ok))
    ok &= floor_ok
    # the script defaults written here are the Pine's and the replicas'
    pd_ = _pine_defaults()
    m_ok = xpw.DEFAULTS == XPW_SCRIPT and engine.DEFAULTS == ENG_SCRIPT
    if pd_ is None:
        _p('  Pine source not found (%s): defaults not checked against it' % PINE)
    else:
        _p('  the script defaults written here: %d input lines found in the Pine source with these defaults, %d missing%s; '
           'xpw.DEFAULTS and engine.DEFAULTS equal them: %s' % (pd_[0] - len(pd_[1]), len(pd_[1]),
                                                               (' ' + str(pd_[1])) if pd_[1] else '', m_ok))
        ok &= not pd_[1]
    ok &= m_ok
    # the params of every setting
    n_bad = 0
    sp_seen = {}
    for p in G:
        sg = {k: p[k] for k in C.SIGNAL_DIMS}
        x = {k: p[k] for k in C.EXIT_DIMS}
        ks = tuple(sg.values())
        if ks not in sp_seen:
            sp = C.signal_params(sg)
            sp_seen[ks] = xpw._params(sp) == xpw_params(p) and 'fgfOn' not in sp
        want = eng_params(p)
        eff = engine._params(C.engine_params(p))
        t = sc._cfg_tuple(C.exit_cfg(x))
        t_want = (want['trailOn'], want['slOn'], 2, float(want['trailAct']), float(want['trailOff']), float(want['slDist']))
        if not (sp_seen[ks] and eff == want and t == t_want):
            n_bad += 1
            if n_bad <= 3:
                _p('  MAPPING %r: engine %r cfg %r want %r' % (p, {k: (eff.get(k), want.get(k)) for k in want if eff.get(k) != want.get(k)}, t, t_want))
    dflt = dict(C.SCRIPT_DEFAULT)
    unit = dflt.pop('trailUnit')
    def_ok = (dflt == T_DEFAULT and unit == 'price' and C.DEFAULT_P is None and not C.in_grid(dflt, unit)
              and C.in_grid(dflt, 'percent')        # 2 % / 1 % is a row; it is another setting than $2 / $1
              and engine._params(C.engine_params(dflt, unit)) == ENG_SCRIPT
              and xpw._params(C.signal_params(dflt)) == XPW_SCRIPT and C.PATH == 'mag' and C.COST == 'ours'
              and C.COST_MODE == {'tv': 'tv0', 'ours': 'cost', 'stress': 'stress'})
    _p('  params of all %d settings: xpw_signals params (signal_params, resolved by xpw._params, %d keys) and engine '
       'params (engine_params / the kernel cfg of exit_cfg, %d keys) = the mapping written here: %d different'
       % (len(G), len(XPW_SCRIPT), len(ENG_SCRIPT), n_bad))
    _p('  the script\'s default setting (SCRIPT_DEFAULT: trail 2.0 / 1.0 in price units, no stop, maxOpen 20) resolves to '
       'the engine / xpw defaults exactly and is NOT a grid row (DEFAULT_P None; the row with 2 / 1 in percent is '
       'another setting): %s' % def_ok)
    ok &= n_bad == 0 and def_ok
    # normalize: every grid row round-trips, as the file gives it (p_ prefix, NaN or None for unused)
    n_rt = sum(C.normalize({'p_' + k: (float('nan') if v is None else v) for k, v in p.items()}) == (p, 'percent')
               and C.normalize({k: v for k, v in p.items() if v is not None}) == (p, 'percent') for p in G)
    forced = C.normalize(dict(G[0], blkClose=True, trailAct=2.0, trailOff=1.0, slDist=4.0))[0]
    r_ok = n_rt == len(G) and forced == G[0] and not G[0]['fgfOn'] and not G[0]['trailOn'] and not G[0]['slOn']
    _p('  normalize(): %d of %d grid rows round-trip (p_ prefix, NaN / missing for unused); a value given for an '
       'unused dimension is dropped: %s' % (n_rt, len(G), r_ok))
    ok &= r_ok
    # unused dimensions cannot change the result (and the view of a setting is what the engine would get)
    rng = np.random.default_rng(20261124)
    n_u = n_ud = 0
    for pair, tf in CELLS:
        for si in rng.choice(18, size=3, replace=False):
            sg = C.SIGNALS[2 * int(si)]                        # filter off
            sg_on = C.SIGNALS[2 * int(si) + 1]
            assert not sg['fgfOn'] and sg_on['fgfOn']
            P0 = C.prepare(pair, tf, sg)
            P1 = C.prepare(pair, tf, sg_on, S=P0['S'], B=P0['B'])
            X0 = C.exits_for(sg)
            X1 = C.exits_for(sg_on)
            # blkClose with the filter off: the gate itself is the same
            ga = C.gate(P0['S'], None, False, True)
            gb = C.gate(P0['S'], None, False, False)
            same_gate = all(np.array_equal(ga[k], gb[k]) for k in ('goL', 'goS', 'cL', 'cS')) and ga['cap'] == gb['cap']
            n_u += 1
            n_ud += not same_gate
            for i in rng.choice(len(X1), size=8, replace=False):
                x = X1[int(i)]
                base = C.simulate(P1, x, 'mag')
                alts = []
                if not x['trailOn']:
                    for ta, to in ((0.2, 0.1), (4.0, 3.0)):
                        v = C._view(P1, x['blkClose'], x['maxOpen'])
                        alts.append(sc.run_cfg(v, dict(C.exit_cfg(x), trailAct=ta, trailOff=to), 'mag', sub=C.get_sub(P1), inv=x['inv']))
                if not x['slOn']:
                    for sd in (0.5, 4.0):
                        v = C._view(P1, x['blkClose'], x['maxOpen'])
                        alts.append(sc.run_cfg(v, dict(C.exit_cfg(x), slDist=sd), 'mag', sub=C.get_sub(P1), inv=x['inv']))
                for alt in alts:
                    n_u += 1
                    n_ud += not _eq_runs(base, alt)
            for i in rng.choice(len(X0), size=4, replace=False):
                x = X0[int(i)]
                v = C._view(P0, None, x['maxOpen'])
                vb = dict(v, goL=gb['goL'], goS=gb['goS'], cL=gb['cL'], cS=gb['cS'], cap=gb['cap'])
                n_u += 1
                n_ud += not _eq_runs(C.simulate(P0, x, 'mag'), sc.run_cfg(vb, C.exit_cfg(x), 'mag', sub=C.get_sub(P0), inv=x['inv']))
        _free()
    _p('  unused dimensions (%s): fgfBlkClose true vs false with the filter off (gate arrays and runs), other trail '
       'distances with the trail off, other stop distances with the stop off: %d comparisons, %d with a different result'
       % (', '.join('%s %s' % c for c in CELLS), n_u, n_ud))
    ok &= n_ud == 0
    # the files
    fd = os.path.join(OUT, 'calib_xpw_dims.json')
    if os.path.exists(fd):
        same = json.load(open(fd)) == C.DIMS
        _p('  out/calib_xpw_dims.json equals DIMS: %s' % same)
        ok &= same
    else:
        _p('  out/calib_xpw_dims.json: not written yet')
    cols_ok = list(C.COLS) == list(SPEC_COLS) and set(C.INT_COLS) == set(INT_FIELDS) and tuple(sc.METRIC_COLS) == METRIC_FIELDS
    _p('  summary fields = the %d fields of sweep_core.metrics_fast, then long / short trades, the engine\'s run counts '
       'and the gate\'s counts (%d in all), as written here: %s' % (len(METRIC_FIELDS), len(SPEC_COLS), cols_ok))
    ok &= cols_ok
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        f_ok = (len(df) == N_GRID and _keys(df) == S and list(df.columns) == _pcols() + list(SPEC_COLS)
                and all(k in df.columns for k in SUM_REQUIRED))
        t_ok = (all(df[c].dtype == np.int64 for c in INT_FIELDS) and all(df[c].dtype == np.float64 for c in SPEC_COLS if c not in INT_FIELDS)
                and all(df['p_' + n].dtype == np.float64 for n in ('trailAct', 'trailOff', 'slDist'))
                and all(df['p_' + n].dtype == np.int64 for n in ('rsiLen', 'maxOpen'))
                and all(df['p_' + n].dtype == bool for n in ('lblRead', 'fgfOn', 'inv', 'trailOn', 'slOn')))
        nulls = {c: int(df[c].isna().sum()) for c in _sumcols(df) if df[c].isna().any()}
        _p('  %s: %d rows; p_ columns = the grid in order; columns = %d p_ + the %d summary fields, nothing else: %s; '
           'column types: %s (NaN: %s)' % (src, len(df), len(_pcols()), len(SPEC_COLS), f_ok, t_ok, nulls or 'none'))
        ok &= f_ok and t_ok
        meta = C.read_meta(_DF[(pair, tf)][2])
        now = C.file_meta(pair, tf, N_GRID)
        m_ok = meta is not None and all(meta.get(k) == now[k] for k in ('strategy', 'pair', 'tf', 'path', 'cost', 'settings',
                                                                        'window', 'trailUnit'))
        cur = meta is not None and all(meta.get(k) == now[k] for k in now if k.endswith('_sha256'))
        _p('    file metadata: %s, path %s, cost %s, %s settings: %s; written with the xpw.py, fgf.py, engine.py and '
           'sweep_core.py now on disk: %s' % ((meta or {}).get('strategy'), (meta or {}).get('path'), (meta or {}).get('cost'),
                                              (meta or {}).get('settings'), m_ok,
                                              cur if cur else 'NO (rows are still checked against the modules by tests 2 and 3)'))
        ok &= m_ok
    _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 2. the default setting and the saved results
# ---------------------------------------------------------------------------------------------
def _one(pair, tf, p, *extra):
    cmd = [sys.executable, '-I', os.path.join(W, 'calib_xpw.py'), '--one', pair, tf, json.dumps(p)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def _one_many(jobs):
    """[(pair, tf, p, extra)] -> results in order; at most 2 `--one` processes at a time."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        return list(ex.map(lambda j: _one(j[0], j[1], j[2], *j[3]), jobs))


NAMED_RUNS = (('normal', 'on', 'mag', 'ours'), ('inverted', 'on', 'mag', 'ours'), ('normal', 'off', 'tv', 'script'),
              ('inverted', 'off', 'tv', 'script'))
COST_OF = {'script': 'tv', 'ours': 'ours'}


def _default_p(direction, flt):
    p = dict(T_DEFAULT, fgfOn=flt == 'on', inv=direction == 'inverted')
    if flt != 'on':
        p['blkClose'] = None
    return p


def test_2_default():
    """(2) The script's default exits are not on this grid, so instead: the runner's machinery given the
    default inputs (`--one --off-grid`, trailUnit price, 2 / 1) reproduces the saved default results of
    the module, out/inv_xpw_<PAIR>_<TF>.json (same path and cost), on BTC 60 and XAU 240; in process every
    saved run of every cell; and the grid rows with a saved counterpart in the earlier sweep equal it."""
    ok = True
    # (a) through --one --off-grid, a new process each
    jobs, refs = [], []
    for pair, tf in (('BTC', '60'), ('XAU', '240')):
        runs = json.load(open(os.path.join(OUT, 'inv_xpw_%s_%s.json' % (pair, tf))))['runs']
        for direction, flt, path, cost in NAMED_RUNS:
            p = dict(_default_p(direction, flt), trailUnit='price')
            jobs.append((pair, tf, p, ('--off-grid', '--path', path, '--cost', COST_OF[cost])))
            refs.append((pair, tf, direction, flt, path, cost, runs[direction][flt][path][cost]))
    t0 = time.time()
    res = _one_many(jobs)
    for (rc, out, err), (pair, tf, direction, flt, path, cost, ref), job in zip(res, refs, jobs):
        tag = '%s %s %s/%s/%s/%s' % (pair, tf, direction, flt, path, cost)
        if rc != 0:
            _p('  %s: exit code %d %s' % (tag, rc, err.strip()[-300:]))
            ok = False
            continue
        o = json.loads(out)
        st = o.pop('setting')
        bad = [k for k in ref if not _same(o.get(k, 'missing'), ref[k])]
        st_ok = (st['in_grid'] is False and st['trailUnit'] == 'price' and (st['path'], st['cost']) == (path, COST_OF[cost])
                 and st['p'] == _default_p(direction, flt))
        _p('  --one --off-grid %-28s = saved json: %d of %d fields equal%s | %d trades, net %+.2f %%, h1r %+.2f %%, h2r %+.2f %%'
           % (tag, len(ref) - len(bad), len(ref), '' if not bad else ' DIFFERENT: %s' % bad, o['trades'], o['net_pct'],
              o['h1r_pct'], o['h2r_pct']))
        ok &= not bad and st_ok and len(ref) == 28
    rc, out, err = _one('XAU', '240', dict(_default_p('normal', 'on'), trailUnit='price'))
    refused = rc == 2 and out.strip() == ''
    _p('  the same JSON without --off-grid is refused (exit code %d): %s (%.1fs for the 9 processes)' % (rc, refused, time.time() - t0))
    ok &= refused
    # (b) in process, every saved run of every cell; (c) grid rows against the earlier sweep's saved rows
    di = _default_sig_idx()
    tot = dict(cells=0, runs=0, vals=0, rows=0, rvals=0)
    for pair in ('BTC', 'XAU'):
        for tf in TFS:
            have = os.path.exists(_out_file(pair, tf))
            if not have and FILES_ONLY:
                continue
            cell = C.prepare_cell(pair, tf, sig_idx=di)
            bad = []
            sv = json.load(open(os.path.join(OUT, 'inv_xpw_%s_%s.json' % (pair, tf))))
            n_runs = n_vals = 0
            for direction in ('normal', 'inverted'):
                for flt in ('off', 'on'):
                    P = cell['P'][di[1] if flt == 'on' else di[0]]
                    assert P['fgfOn'] == (flt == 'on')
                    p = _default_p(direction, flt)
                    x = {k: p[k] for k in C.EXIT_DIMS}
                    for path in ('tv', 'mag'):
                        R = C.simulate(P, x, path, unit='price')
                        for cost in ('script', 'ours'):
                            ref = sv['runs'][direction][flt][path][cost]
                            row = C.summary(P, R, x, COST_OF[cost])
                            d = [k for k in ref if not _same(row[k], ref[k])]
                            n_runs += 1
                            n_vals += len(ref)
                            if d:
                                bad.append('%s/%s/%s/%s: %s' % (direction, flt, path, cost, d))
            # (c)
            if have:
                df, src = _cell_df(pair, tf)
                src = 'file'
            else:
                res, info = C.run_prepared(cell, workers=3)
                df = C.frame(cell, res)
                src = '1512 rows run here'
            idx = {k: i for i, k in enumerate(_keys(df))}
            sw = pd.read_parquet(os.path.join(OUT, 'sweep_%s_%s.parquet' % (pair, tf)))
            sw = sw[(sw['path'] == 'mag') & (sw['trailUnit'] == 'percent') & (sw['tag'] == 'grid')]
            n_rows = n_rv = 0
            for labels, flt, fg, blk, inv in (('normal', 'off', False, None, False), ('normal', 'on', True, True, False),
                                              ('rev', 'off', False, None, True)):
                g = sw[(sw['labels'] == labels) & (sw['filter'] == flt)]
                for _, r in g.iterrows():
                    ton, son = bool(r['trailOn']), bool(r['slOn'])
                    k = (13, True, 'all', fg, blk, inv, ton, float(r['trailAct']) if ton else None,
                         float(r['trailOff']) if ton else None, son, float(r['slDist']) if son else None, 20)
                    if k not in idx:
                        continue
                    row = df.iloc[idx[k]]
                    d = [m for m in METRIC_FIELDS if not _same(row[m], r['cost_' + m])]
                    n_rows += 1
                    n_rv += len(METRIC_FIELDS)
                    if d:
                        bad.append('saved sweep %s/%s %r: %s' % (labels, flt, k[6:11], d))
            _p('  %s %-3s: the default inputs through the runner = all %d saved runs of inv_xpw json (%d values); grid rows '
               '(%s) = %d saved sweep rows (mag, our costs: the %d exits both grids hold, with the filter off, with it '
               'on, and inverted with the filter off = the saved reversed-label rows), %d values: %s'
               % (pair, tf, n_runs, n_vals, src, n_rows, n_rows // 3, n_rv,
                  'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(bad[:4]))))
            ok &= not bad and n_runs == 16 and n_rows == 153
            tot['cells'] += 1
            tot['runs'] += n_runs
            tot['vals'] += n_vals
            tot['rows'] += n_rows
            tot['rvals'] += n_rv
            del cell
            _free()
    _p('  %d cells: %d saved default runs (%d values) and %d saved sweep rows (%d values) compared'
       % (tot['cells'], tot['runs'], tot['vals'], tot['rows'], tot['rvals']))
    return ok and tot['cells'] > 0


# ---------------------------------------------------------------------------------------------
# 3. random rows through --one
# ---------------------------------------------------------------------------------------------
def test_3_one_rows():
    """(3) 30 random rows per cell recomputed one at a time through `calib_xpw.py --one` (a new process each,
    the row's p_ columns as its JSON) equal the sweep rows on every summary column; the same rows against
    the canonical engine on the 1-minute series with this file's own mapping (trades through
    run_tf.metrics); --path / --cost are honoured; bad input is refused; --off-grid."""
    ok = True
    rng = np.random.default_rng(31)
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        scn = _sumcols(df)
        keys = _keys(df)
        pick = _pick_rows(keys, rng, 30)
        ref = Ref(pair, tf)
        bad = []
        n_vals = n_ref = n_tr = 0
        cover = {n: set() for n in SPEC_DIMS}
        t0 = time.time()
        ps = [dict(zip(SPEC_DIMS, keys[i])) for i in pick]
        res = _one_many([(pair, tf, {'p_' + n: v for n, v in p.items()}, ()) for p in ps])
        t_one = time.time() - t0
        for i, p, (rc, out, err) in zip(pick, ps, res):
            row = df.iloc[i]
            for n, v in p.items():
                cover[n].add(v)
            if rc != 0:
                bad.append('row %d: exit code %d %s' % (i, rc, err.strip()[-200:]))
                continue
            o = json.loads(out)
            st = o.pop('setting')
            if st != {'strategy': 'xpw', 'pair': pair, 'tf': tf, 'path': 'mag', 'cost': 'ours', 'p': p,
                      'trailUnit': 'percent', 'in_grid': True}:
                bad.append('row %d: setting echoed as %r' % (i, st))
            if list(o) != scn:
                bad.append('row %d: fields %r' % (i, list(o)))
                continue
            for k in scn:
                n_vals += 1
                if not _same(row[k], o[k]):
                    bad.append('row %d --one .%s file %r one %r' % (i, k, row[k], o[k]))
            tr, es = ref.mag(p)
            rs = ref_summary(pair, tr, ref.start, ref.end, 'ours', es)
            n_ref += cmp_row(row, rs, 'row %d minute engine' % i, bad, skip=('max_open',))
            n_tr += int(row['trades'])
        cov = all(len(cover[d['name']] - {None}) == len(d['values']) for d in C.DIMS)
        _p('  %s %s (%s): 30 random rows, each in its own `--one` process: %d summary values; and against '
           'engine.backtest_bars on the 1-minute bars + run_tf.metrics with the mapping written here: %d values (%d '
           'trades): %s; every value of every dimension among them: %s (--one %.1fs)'
           % (pair, tf, src, n_vals, n_ref, n_tr,
              'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad[:5] if b)), cov, t_one))
        ok &= not bad and n_vals == 30 * len(scn)
        # --path / --cost
        bad = []
        n = 0
        combos = (('tv', 'tv'), ('tv', 'ours'), ('tv', 'stress'), ('mag', 'tv'), ('mag', 'stress'))
        sel = pick[:4]
        jobs = [(pair, tf, dict(zip(SPEC_DIMS, keys[i])), ('--path', path, '--cost', cost)) for i in sel for path, cost in combos]
        res = _one_many(jobs)
        for (pr, tf_, p, extra), (rc, out, err) in zip(jobs, res):
            path, cost = extra[1], extra[3]
            if rc != 0:
                bad.append('%s %s: exit code %d' % (path, cost, rc))
                continue
            o = json.loads(out)
            if (o['setting']['path'], o['setting']['cost']) != (path, cost):
                bad.append('path / cost echoed %r' % (o['setting'],))
            tr, es = ref.tv(p) if path == 'tv' else ref.mag(p)
            rs = ref_summary(pair, tr, ref.start, ref.end, cost, es)
            n += cmp_row(o, rs, '%s %s' % (path, cost), bad, skip=('max_open',) if path == 'mag' else ())
        _p('  %s %s: --path tv / mag x --cost tv / ours / stress on 4 rows (%d processes) = engine.backtest (tv) or the '
           'minute engine (mag) + run_tf.metrics with that cost: %d values: %s'
           % (pair, tf, len(jobs), n, 'all equal' if not bad else '; '.join(b for b in bad[:5] if b)))
        ok &= not bad
        del ref
        _free()
    # bad input
    pair, tf = CELLS[0]
    p = dict(spec_p(13, True, 'all', True, True, False, True, 1.0, 0.3, True, 1.5, 5))
    cases = (('unknown dimension', dict(p, bbLen=20), ()),
             ('value not in the grid', dict(p, trailAct=3.0), ()),
             ('missing used dimension', {k: v for k, v in p.items() if k != 'inv'}, ()),
             ('trailOn without trailAct', {k: v for k, v in p.items() if k != 'trailAct'}, ()),
             ('trailUnit price on the grid', dict(p, trailUnit='price'), ()),
             ('unknown labels off the grid', dict(p, labels='legs+div'), ('--off-grid',)),
             ('not an object', [1, 2], ()))
    res = _one_many([(pair, tf, q, extra) for _, q, extra in cases])
    chk = [(name, rc, out.strip() == '' and 'calib_xpw.py --one' in err) for (name, _, _), (rc, out, err) in zip(cases, res)]
    q = dict(p, rsiLen=10, trailAct=0.8, trailOff=0.25, slDist=2.5, maxOpen=7)
    rc, out, err = _one(pair, tf, q, '--off-grid')
    og = rc == 0 and json.loads(out)['setting']['in_grid'] is False
    if og:
        o = json.loads(out)
        ref = Ref(pair, tf)
        tr, es = ref.mag(q)
        bad = []
        cmp_row(o, ref_summary(pair, tr, ref.start, ref.end, 'ours', es), 'off-grid', bad, skip=('max_open',))
        og = not bad
    b_ok = all(rc == 2 and e for _, rc, e in chk) and og
    _p('  bad input is refused (exit code 2, nothing on stdout): %s; --off-grid runs a setting outside the grid '
       '(rsiLen 10, trail 0.8 / 0.25 %%, stop 2.5 %%, maxOpen 7) = the minute engine: %s'
       % (', '.join('%s -> %d' % (n, rc) for n, rc, _ in chk), og))
    return ok and b_ok


def spec_p(*vals):
    return dict(zip(SPEC_DIMS, vals))


def _pick_rows(keys, rng, n):
    """n random rows (3 of them among the trailing-off rows, 1 in 21 of the grid), redrawn until every value
    of every dimension occurs among them."""
    off = [i for i, k in enumerate(keys) if not k[6]]
    vals = [set(k[j] for k in keys) - {None} for j in range(len(SPEC_DIMS))]
    for _ in range(1000):
        pick = set(int(i) for i in rng.choice(len(keys), size=n - 3, replace=False))
        pick |= set(int(off[int(i)]) for i in rng.choice(len(off), size=3, replace=False))
        if len(pick) == n and all(set(keys[i][j] for i in pick) - {None} == vals[j] for j in range(len(SPEC_DIMS))):
            return sorted(pick)
    raise RuntimeError('no covering sample found')


# ---------------------------------------------------------------------------------------------
# 4. worker count
# ---------------------------------------------------------------------------------------------
def test_4_workers():
    """(4) XAU 240, the full grid with 1 worker and with 3 workers (files in calib_tmp_xpw/w1 and w3, not
    out/): every row and column identical, and the two files byte for byte; equal to out/ when it exists."""
    d1 = os.path.join(TMP, 'w1')
    d3 = os.path.join(TMP, 'w3')
    a, ia = C.run_cell('XAU', '240', workers=1, out_dir=d1, verbose=False)
    _free()
    b, ib = C.run_cell('XAU', '240', workers=3, out_dir=d3, verbose=False)
    _free()
    f1 = os.path.join(d1, 'calib_xpw_XAU_240.parquet')
    f3 = os.path.join(d3, 'calib_xpw_XAU_240.parquet')
    fa = pd.read_parquet(f1)
    fb = pd.read_parquet(f3)
    same = fa.equals(fb) and a.equals(b) and len(fa) == N_GRID and list(fa.columns) == list(fb.columns) \
        and all(fa[c].dtype == fb[c].dtype for c in fa.columns)
    byt = _sha(f1) == _sha(f3)
    dims = json.load(open(os.path.join(d1, 'calib_xpw_dims.json'))) == C.DIMS == json.load(open(os.path.join(d3, 'calib_xpw_dims.json')))
    _p('  XAU 240: %d rows x %d columns; 1 worker %.1fs (runs %.1fs, %.1fs CPU), 3 workers %.1fs (runs %.1fs, %.1fs CPU, '
       'speed-up x%.2f): frames %s, files %s (sha256 %s), dims.json = DIMS: %s'
       % (len(fa), len(fa.columns), ia['t_total'], ia['t_run'], ia['cpu'], ib['t_total'], ib['t_run'], ib['cpu'],
          ia['t_run'] / ib['t_run'], 'identical' if same else 'DIFFERENT', 'byte for byte equal' if byt else 'DIFFERENT bytes',
          _sha(f3)[:16], dims))
    ok = same and byt and dims
    fo = _out_file('XAU', '240')
    if os.path.exists(fo):
        fo_df = pd.read_parquet(fo)
        again = fo_df.equals(fb)
        _p('  out/calib_xpw_XAU_240.parquet (the production run) equals this re-run: %s (bytes %s)'
           % (again, 'equal' if _sha(fo) == _sha(f3) else 'different'))
        ok &= again
    return ok


# ---------------------------------------------------------------------------------------------
# 5. timing, BTC 1
# ---------------------------------------------------------------------------------------------
def test_5_timing_btc1():
    """(5) BTC 1 (the most chart bars): the real preparation of all 36 signal settings (18 xpw_signals
    calls), then one pass = the 1512 exit settings of one signal input (filter off + on) with 3 workers,
    for the default, the busiest and the quietest signal input; extrapolated to the 18 signal inputs. The
    full grid must stay under 45 min with 3 workers (else the grid is thinned in the order the task
    gives). The verdict is on the CPU seconds the passes used (= the wall time when each of the 3 workers
    has a CPU, with every pass counted as the slowest one); the wall time measured now, next to whatever
    else runs on the 4 CPUs, is printed beside it."""
    load0 = os.getloadavg()[0]
    cell = C.prepare_cell('BTC', '1')
    t_prep = cell['t_prep']
    c_prep = cell['c_prep']
    nsig = {si: int(np.count_nonzero(cell['P'][si]['S']['nL'] + cell['P'][si]['S']['nS'])) for si in cell['idx']}
    di = _default_sig_idx()
    _p('  BTC 1: %d chart bars, %d 1-minute bars; all 36 signal settings (18 xpw_signals calls) prepared in %.1fs '
       'wall = %.1fs CPU (signals + gates %.1fs, sub-bars %.1fs, kernels + guard %.1fs); bars with an entry signal: '
       '%d .. %d (default %d)' % (cell['bars'], cell['n_sub'], t_prep, c_prep, cell['t_sig'], cell['t_sub'], cell['t_jit'],
                                  min(nsig.values()), max(nsig.values()), nsig[di[0]]))
    # chart "1": each bar is its own sub-bar, so the scored mag path must equal the tv path
    rng = np.random.default_rng(5)
    Pd = cell['P'][di[1]]
    Xd = C.exits_for(C.SIGNALS[di[1]])
    n_eq = sum(_eq_runs(C.simulate(Pd, Xd[int(i)], 'mag'), C.simulate(Pd, Xd[int(i)], 'tv'))
               for i in rng.choice(len(Xd), size=12, replace=False))
    _p('  chart "1": mag (real 1-minute sub-bars) == tv on %d of 12 random settings' % n_eq)
    order = sorted(range(0, 36, 2), key=lambda si: nsig[si])
    passes = (('default', di), ('busiest', [order[-1], order[-1] + 1]), ('quietest', [order[0], order[0] + 1]))
    t3, c3 = [], []
    keep = None
    for name, idx in passes:
        res, info = C.run_prepared(cell, workers=3, sig_idx=idx)
        t3.append(info['t_run'])
        c3.append(info['cpu'])
        s = C.SIGNALS[idx[0]]
        _p('  pass %-8s (rsiLen %d, lblRead %s, labels %s): %d settings, 3 workers %.1fs wall, %.1fs CPU (%.4fs CPU per '
           'setting; the workers got %.0f%% of a CPU each)' % (name, s['rsiLen'], s['lblRead'], s['labels'], info['settings'],
                                                               info['t_run'], info['cpu'], info['cpu'] / info['settings'],
                                                               100.0 * info['cpu'] / (3 * info['t_run'])))
        if name == 'default':
            keep = res
    idx = passes[0][1]
    res1, info1 = C.run_prepared(cell, workers=1, sig_idx=idx)
    same = all(len(res1[si]) == len(keep[si]) and all(_same(u, v) for a, b in zip(res1[si], keep[si]) for u, v in zip(a, b))
               for si in idx)
    _p('  pass default with 1 worker: %.1fs wall, %.1fs CPU; speed-up of 3 workers x%.2f; rows identical to the 3-worker '
       'pass: %s' % (info1['t_run'], info1['cpu'], info1['t_run'] / t3[0], same))
    free = c_prep + 18 * float(np.mean(c3)) / 3.0
    free_hi = c_prep + 18 * max(c3) / 3.0
    now = t_prep + 18 * float(np.mean(t3))
    now_hi = t_prep + 18 * max(t3)
    share = sum(c3) / (3.0 * sum(t3))
    _p('  full grid BTC 1 with 3 workers = preparation + 18 passes: %.0f CPU-s in all (preparation %.0f + runs %.0f) -> '
       '%.1f min when each worker has a CPU (mean pass), %.1f min if every pass costs what the slowest did; limit 45 min'
       % (c_prep + 18 * float(np.mean(c3)), c_prep, 18 * float(np.mean(c3)), free / 60.0, free_hi / 60.0))
    _p('  at the speed measured now (load average %.2f -> %.2f on 4 CPUs: other jobs run beside this test, each worker '
       'got %.0f%% of a CPU): %.1f min (mean pass), %.1f min (slowest pass)%s'
       % (load0, os.getloadavg()[0], 100.0 * share, now / 60.0, now_hi / 60.0,
          '' if now_hi < 45 * 60.0 else ' -- OVER 45 min at this load: run the cell when the machine is quieter'))
    _p('  -> the full grid (27,216 settings) fits with 3 workers: nothing thinned' if free_hi < 45 * 60.0
       else '  -> OVER the limit: thin the grid (rsiLen to {13} first)')
    del cell
    _free()
    return same and n_eq == 12 and free_hi < 45 * 60.0


# ---------------------------------------------------------------------------------------------
# 6. PROOF, tv path: the runner's arrays for the non-default inputs give engine.backtest's trades
# ---------------------------------------------------------------------------------------------
N_PER_TV = 7            # exit settings per (signal input, filter mode, direction) and cell
NONDEFAULT = (('maxOpen', 1), ('maxOpen', 5), ('blkClose', False), ('lblRead', False), ('rsiLen', 8), ('rsiLen', 21),
              ('labels', 'legs'), ('labels', 'div'), ('slOn', True), ('slDist', 0.5), ('slDist', 1.5), ('slDist', 4.0),
              ('trailOn', False), ('trailAct', 0.2), ('trailAct', 0.5), ('trailAct', 1.0), ('trailAct', 2.0),
              ('trailAct', 4.0), ('trailOff', 0.1), ('trailOff', 0.3), ('trailOff', 1.0), ('trailOff', 3.0))


def _cover_add(cov, p, n_tr):
    for name, v in NONDEFAULT:
        if p[name] == v and p[name] is not None and isinstance(p[name], type(v)):
            c = cov[(name, v, p['fgfOn'], p['inv'])]
            c[0] += 1
            c[1] += n_tr


def _cover_report(cov, tag):
    """Every non-default value x filter on / off x normal / inverted has settings; prints the table."""
    ok = True
    parts = []
    for name, v in NONDEFAULT:
        cnt = []
        for fg in (False, True):
            for inv in (False, True):
                if name == 'blkClose' and not fg:
                    continue
                cnt.append(cov[(name, v, fg, inv)][0])
        tr = sum(cov[(name, v, fg, inv)][1] for fg in (False, True) for inv in (False, True))
        ok &= min(cnt) >= 1
        parts.append('%s=%s %d (min %d; %d trades)' % (name, v, sum(cnt), min(cnt), tr))
    _p('    %s settings per non-default value (all; the smallest of its filter off / on x normal / inverted groups; '
       'trades compared): %s' % (tag, '; '.join(parts)))
    return ok


def test_6_tv_proof():
    """PROOF (tv path). sweep_core.prep fixes maxOpen 20 and fgfBlkClose true, so calib_xpw builds the
    kernel's arrays itself. For every non-default value used in the grid (maxOpen 1 / 5, fgfBlkClose false,
    lblRead false, rsiLen 8 / 21, labels legs / div, percent units, stop loss on) and their combinations
    the runner's tv-path run equals engine.backtest (fresh xpw_signals / fgf_permissions, this file's own
    param mapping) trade by trade, with the filter on and off, normal and inverted, on XAU 240, XAU 15,
    BTC 240 and BTC 60; and the runner's row equals run_tf.metrics on engine.backtest's trade list."""
    ok = True
    rng = np.random.default_rng(606)
    costs = ('tv', 'ours', 'stress')
    for pair, tf in PROOF_CELLS:
        t0 = time.time()
        ref = Ref(pair, tf)
        cov = collections.defaultdict(lambda: [0, 0])
        bad = []
        n_set = n_tr = n_vals = n_rows = n_zero = 0
        S = B = None
        cur = None
        for sg in C.SIGNALS:
            ki = (sg['rsiLen'], sg['lblRead'], sg['labels'])
            if ki != cur:
                S = C.signal_arrays(pair, tf, sg)
                cur = ki
            P = C.prepare(pair, tf, sg, S=S, B=B)
            B = P['B']
            X = C.exits_for(sg)
            for blk in ((True, False) if sg['fgfOn'] else (None,)):
                for inv in (False, True):
                    cand = [x for x in X if x['blkClose'] == blk and x['inv'] == inv]
                    assert len(cand) == 252
                    for j in rng.choice(len(cand), size=N_PER_TV, replace=False):
                        x = cand[int(j)]
                        p = C.merge(sg, x)
                        R = C.simulate(P, x, 'tv')
                        tr, es = ref.tv(p)
                        d = cmp_trades(R, tr, B['t_close'])
                        if d:
                            bad.append('%r: %s' % (p, d[0]) if len(bad) < 5 else '')
                        n_set += 1
                        n_tr += len(tr)
                        n_zero += len(tr) == 0
                        _cover_add(cov, p, len(tr))
                        if n_set % 3 == 0:                      # the row, one cost mode in turn
                            cost = costs[(n_set // 3) % 3]
                            rs = ref_summary(pair, tr, ref.start, ref.end, cost, es)
                            n_vals += cmp_row(_row_of(P, R, x, cost), rs, '%r %s' % (p, cost), bad)
                            n_rows += 1
        c_ok = _cover_report(cov, '%s %s:' % (pair, tf))
        _p('  %s %-3s: %d settings (%d per signal input x filter off / on+close / on-close x normal / inverted), %d '
           'trades: tv path vs engine.backtest trade by trade (side, bars, prices, exit kind, entry number, times): %s; '
           '%d rows (cost tv / ours / stress in turn) vs run_tf.metrics on that list + the engine\'s counts: %d values; '
           'every non-default value covered with the filter on and off, normal and inverted: %s (%.1fs)'
           % (pair, tf, n_set, N_PER_TV, n_tr, 'all identical' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
              n_rows, n_vals, c_ok, time.time() - t0))
        ok &= not bad and c_ok and n_set == 108 * N_PER_TV and n_tr > 0
        if EXHAUSTIVE and (pair, tf) == ('XAU', '240'):
            t0 = time.time()
            n_all = n_bad = n_t = 0
            S = None
            cur = None
            for sg in C.SIGNALS:
                ki = (sg['rsiLen'], sg['lblRead'], sg['labels'])
                if ki != cur:
                    S = C.signal_arrays(pair, tf, sg)
                    cur = ki
                P = C.prepare(pair, tf, sg, S=S, B=B)
                for x in C.exits_for(sg):
                    p = C.merge(sg, x)
                    tr, es = ref.tv(p)
                    n_bad += bool(cmp_trades(C.simulate(P, x, 'tv'), tr))
                    n_all += 1
                    n_t += len(tr)
            _p('  %s %s EXHAUSTIVE: every one of the %d grid settings, tv path vs engine.backtest trade by trade (%d '
               'trades): %d different (%.1fs)' % (pair, tf, n_all, n_t, n_bad, time.time() - t0))
            ok &= n_bad == 0 and n_all == N_GRID
        del ref
        _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 7. PROOF, mag path
# ---------------------------------------------------------------------------------------------
def test_7_mag_proof():
    """PROOF (the scored path, 1-minute fills). For the same non-default inputs the runner's mag run equals
    the canonical engine itself (engine.backtest_bars) run on the 1-minute bars of the window with every
    chart bar's labels and permissions on its last minute = the Bar Magnifier definition, trade by trade,
    filter on and off, normal and inverted, on XAU 240, XAU 15, BTC 240, BTC 60 (one setting per signal
    input x filter mode, direction alternating); the row = run_tf.metrics on that list. And mag_ref.py,
    the independent pure-Python reference (normal direction), on XAU 240."""
    ok = True
    rng = np.random.default_rng(707)
    costs = ('ours', 'stress', 'tv')
    for pair, tf in PROOF_CELLS:
        t0 = time.time()
        ref = Ref(pair, tf)
        cov = collections.defaultdict(lambda: [0, 0])
        bad = []
        n_set = n_tr = n_vals = n_dif = 0
        S = B = sub = None
        cur = None
        # each filter mode meets each (direction, maxOpen) pair 3 times over its 18 signal inputs
        cnt = {None: 0, True: 1, False: 3}
        for sg in C.SIGNALS:
            ki = (sg['rsiLen'], sg['lblRead'], sg['labels'])
            if ki != cur:
                S = C.signal_arrays(pair, tf, sg)
                cur = ki
            P = C.prepare(pair, tf, sg, S=S, B=B, sub=sub)
            B = P['B']
            sub = C.get_sub(P)
            if n_set == 0:
                C.guard(P)
            X = C.exits_for(sg)
            for blk in ((True, False) if sg['fgfOn'] else (None,)):
                inv = bool(cnt[blk] % 2)
                mo = C.MAX_OPENS[(cnt[blk] // 2) % 3]
                cnt[blk] += 1
                cand = [x for x in X if x['blkClose'] == blk and x['inv'] == inv and x['maxOpen'] == mo]
                x = cand[int(rng.integers(len(cand)))]
                p = C.merge(sg, x)
                R = C.simulate(P, x, 'mag')
                tr, es = ref.mag(p)
                d = cmp_trades(R, tr, B['t_close'])
                if d:
                    bad.append('%r: %s' % (p, d[0]) if len(bad) < 5 else '')
                n_set += 1
                n_tr += len(tr)
                n_dif += not _eq_runs(R, C.simulate(P, x, 'tv'))
                _cover_add(cov, p, len(tr))
                cost = costs[n_set % 3]
                rs = ref_summary(pair, tr, ref.start, ref.end, cost, es)
                n_vals += cmp_row(_row_of(P, R, x, cost), rs, '%r %s' % (p, cost), bad, skip=('max_open',))
        need = [(n, v) for n, v in NONDEFAULT if n in ('maxOpen', 'blkClose', 'lblRead', 'rsiLen', 'labels', 'slOn')]
        c_ok = all(sum(cov[(n, v, fg, inv)][0] for inv in (False, True)) >= 1 for n, v in need for fg in (False, True)
                   if not (n == 'blkClose' and not fg))
        c_ok &= all(sum(cov[(n, v, fg, inv)][0] for fg in (False, True)) >= 1 for n, v in need for inv in (False, True))
        _p('  %s %-3s: %d settings, %d trades: mag path vs engine.backtest_bars on the %d 1-minute bars, trade by trade: '
           '%s; rows vs run_tf.metrics on that list: %d values; mag differs from tv in %d of them; every non-default '
           'input value with the filter off and on, and normal and inverted: %s (%.1fs)'
           % (pair, tf, n_set, n_tr, len(ref.minutes()[0]),
              'all identical' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)),
              n_vals, n_dif, c_ok, time.time() - t0))
        ok &= not bad and c_ok and n_set == 54 and n_tr > 0 and n_dif > 0
        del ref
        _free()
    # mag_ref.py: independent pure-Python reference of the Bar Magnifier path (no kernel of sweep_core / engine)
    import mag_ref
    pair, tf = 'XAU', '240'
    t0 = time.time()
    cases = (spec_p(13, True, 'all', True, False, False, True, 0.5, 0.3, False, None, 1),
             spec_p(8, False, 'legs', False, None, False, True, 2.0, 1.0, True, 1.5, 5),
             spec_p(21, True, 'div', True, False, False, False, None, None, True, 4.0, 20),
             spec_p(13, False, 'all', True, True, False, True, 0.2, 0.1, True, 0.5, 5))
    msub = None
    bad = []
    n_tr = 0
    for p in cases:
        sg = {k: p[k] for k in C.SIGNAL_DIMS}
        x = {k: p[k] for k in C.EXIT_DIMS}
        P = C.prepare(pair, tf, sg)
        if msub is None:
            msub = mag_ref.my_sub_bars(pair, tf, P['B']['rows'])
        R = C.simulate(P, x, 'mag')
        A = mag_ref.ref_arrays(mag_ref.run_ref(C._view(P, x['blkClose'], x['maxOpen']), msub, eng_params(p)))
        d = mag_ref._cmp(R, A)
        n_tr += A['n']
        if d:
            bad.append('%r: %s' % (p, d[0]))
    _p('  %s %s: mag path vs mag_ref.py (pure Python, its own sub-bar table) on %d settings with maxOpen 1 / 5, '
       'fgfBlkClose false, other signal inputs, percent units, stop loss (%d trades): %s (%.1fs)'
       % (pair, tf, len(cases), n_tr, 'all identical' if not bad else '; '.join(bad), time.time() - t0))
    ok &= not bad and n_tr > 0
    _free()
    return ok


# ---------------------------------------------------------------------------------------------
# 8. what every row must satisfy
# ---------------------------------------------------------------------------------------------
def _twin_pairs(keys, drop, left, right):
    """Row pairs (i, j), i in `left` and j in `right`, with the same p_ values outside the dimensions `drop`."""
    jj = [j for j, n in enumerate(SPEC_DIMS) if n not in drop]
    pos = {tuple(keys[j][c] for c in jj): int(j) for j in right}
    out = []
    for i in left:
        j = pos.get(tuple(keys[i][c] for c in jj))
        if j is not None:
            out.append((int(i), j))
    return out


MIRROR = ('trades', 'exit_close_all', 'exit_reverse', 'exit_end', 'h1_trades', 'h2_trades', 'max_concurrent', 'max_open',
          'entries_skipped_room', 'close_all_bars', 'avg_bars_held')


def _twin_checks(df, sig):
    """Relations between rows that differ in ONE input, true whatever the data (sig = a hash of each row's
    summary columns). {name: holds}, and the pair counts."""
    keys = _keys(df)
    ix = {n: j for j, n in enumerate(SPEC_DIMS)}
    n = len(df)
    tr = df['trades'].to_numpy()
    inv = df['p_inv'].to_numpy(bool)
    blk = [k[ix['blkClose']] for k in keys]
    mo = df['p_maxOpen'].to_numpy()
    son = df['p_slOn'].to_numpy(bool)
    ton = df['p_trailOn'].to_numpy(bool)
    cab = df['close_all_bars'].to_numpy()
    skip = df['entries_skipped_room'].to_numpy()
    esl = df['exit_sl'].to_numpy()
    etr = df['exit_trail'].to_numpy()
    lt, st = df['long_trades'].to_numpy(), df['short_trades'].to_numpy()
    nostop = ~ton & ~son
    mir = {c: df[c].to_numpy() for c in MIRROR}
    p_inv = _twin_pairs(keys, ('inv',), np.flatnonzero(~inv), np.flatnonzero(inv))
    p_blk = _twin_pairs(keys, ('blkClose',), [i for i in range(n) if blk[i] is True], [i for i in range(n) if blk[i] is False])
    p_mo = [(i, j) for lo, hi in ((1, 5), (5, 20), (1, 20))
            for i, j in _twin_pairs(keys, ('maxOpen',), np.flatnonzero(mo == lo), np.flatnonzero(mo == hi))]
    p_sl = _twin_pairs(keys, ('slOn', 'slDist'), np.flatnonzero(son), np.flatnonzero(~son))
    p_tr = _twin_pairs(keys, ('trailOn', 'trailAct', 'trailOff'), np.flatnonzero(ton), np.flatnonzero(~ton))
    chk = {
        # the inverted run holds the opposite side: it cannot have the row of its normal twin
        'twins: an inverted row with trades never equals its normal twin':
            len(p_inv) == n // 2 and not any(sig[i] == sig[j] and (tr[i] > 0 or tr[j] > 0) for i, j in p_inv),
        # no trailing, no stop: no order depends on the real side (the script decides in the normal frame, filter
        # on or off), so the inverted run is the mirror image: the same trades with the sides swapped
        'twins: without trailing and stop the inverted twin holds the same trades with the sides swapped':
            all(lt[i] == st[j] and st[i] == lt[j] and all(mir[c][i] == mir[c][j] for c in MIRROR)
                for i, j in p_inv if nostop[i]),
        # a blocked close that never fired cannot change anything
        'twins: fgfBlkClose true without a single close = the row of fgfBlkClose false':
            len(p_blk) == n // 3 and all(sig[i] == sig[j] for i, j in p_blk if cab[i] == 0),
        # the limit only acts by refusing an entry
        'twins: no entry refused for room = the row of every larger maxOpen':
            len(p_mo) == n and all(sig[i] == sig[j] for i, j in p_mo if skip[i] == 0),
        # a stop / a trail that never closed a trade leaves the run of the setting without it
        'twins: stop on without a stop exit = the row with the stop off':
            len(p_sl) == int(son.sum()) and all(sig[i] == sig[j] for i, j in p_sl if esl[i] == 0),
        'twins: trailing on without a trail exit = the row with trailing off':
            len(p_tr) == int(ton.sum()) and all(sig[i] == sig[j] for i, j in p_tr if etr[i] == 0),
    }
    cnt = dict(inv=len(p_inv), mir=sum(1 for i, j in p_inv if nostop[i]), blk=sum(1 for i, j in p_blk if cab[i] == 0), mo=sum(1 for i, j in p_mo if skip[i] == 0),
               sl=sum(1 for i, j in p_sl if esl[i] == 0), tr=sum(1 for i, j in p_tr if etr[i] == 0))
    return chk, cnt


def test_8_row_consistency():
    """Rows hold what they claim, whatever the data: trade counts add up, a switch that is off leaves no
    trace (no trail / stop exits, nothing blocked and no close with the filter off, no close with
    fgfBlkClose false), the open-entries limit holds, twins (rows that differ in one input) relate as
    they must, and every dimension changes results somewhere."""
    ok = True
    live_all = {}
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        ex = ['exit_trail', 'exit_sl', 'exit_close_all', 'exit_reverse', 'exit_end']
        tr = df['trades']
        lim = np.maximum(df['p_maxOpen'], 2)          # a reversing bar may place its (at most 2) labels whatever the room
        noblk = df['p_blkClose'].map(lambda v: v is not None and not bool(v))
        g_raw = df.groupby(['p_rsiLen', 'p_lblRead', 'p_labels'])[['raw_long', 'raw_short']].nunique()
        g_blk = df[df['p_fgfOn']].groupby(['p_rsiLen', 'p_lblRead', 'p_labels'])[['blocked_long', 'blocked_short']].nunique()
        chk = {
            'trades = long_trades + short_trades': (tr == df['long_trades'] + df['short_trades']).all(),
            'trades = h1_trades + h2_trades': (tr == df['h1_trades'] + df['h2_trades']).all(),
            'trades = sum of the exit kinds': (tr == df[ex].sum(axis=1)).all(),
            'trail off: no trail exit': (df.loc[~df['p_trailOn'], 'exit_trail'] == 0).all(),
            'stop off: no stop exit': (df.loc[~df['p_slOn'], 'exit_sl'] == 0).all(),
            'filter off: nothing blocked, no close': (df.loc[~df['p_fgfOn'], ['blocked_long', 'blocked_short', 'exit_close_all', 'close_all_bars']] == 0).all().all(),
            'fgfBlkClose false: no close': (df.loc[noblk, ['exit_close_all', 'close_all_bars']] == 0).all().all(),
            'blocked <= raw': ((df['blocked_long'] <= df['raw_long']) & (df['blocked_short'] <= df['raw_short'])).all(),
            'raw counts depend on the signal input only': (g_raw == 1).all().all(),
            'blocked counts depend on the signal input only (filter on)': (g_blk == 1).all().all(),
            'trades <= entry labels allowed': (tr <= 2 * (df['raw_long'] - df['blocked_long'] + df['raw_short'] - df['blocked_short'])).all(),
            'open entries <= maxOpen (2 on a reversing bar)': ((df['max_open'] <= lim) & (df['max_concurrent'] <= lim) & (df['exit_end'] <= lim)).all(),
            'pyramiding 100 never binds': (df['entries_ignored_pyramiding'] == 0).all(),
            'no trade without a signal; ratios NaN only then': ((df['net_pct'].isna() == (tr == 0)) & (df['win_pct'].isna() == (tr == 0))).all(),
            'fair halves NaN only without trades in the half': ((df['h1r_pct'].isna() == (df['h1_trades'] == 0)) & (df['h2r_pct'].isna() == (df['h2_trades'] == 0))).all(),
            'max_dd in [0, 100], win in [0, 100]': ((df['max_dd_pct'].fillna(0) >= 0) & (df['max_dd_pct'].fillna(0) <= 100) & (df['win_pct'].fillna(0) >= 0) & (df['win_pct'].fillna(0) <= 100)).all(),
            'max_expo >= 10 % with trades (the first entry)': (df.loc[tr > 0, 'max_expo'] >= 0.1 - 1e-12).all(),
            'half1 + half2 = net (rounded)': np.allclose((df['half1_pct'] + df['half2_pct']).fillna(0), df['net_pct'].fillna(0), rtol=0, atol=0.0151),
        }
        # every dimension changes results: groups of rows that differ only in that dimension
        scn = _sumcols(df)
        sig = pd.util.hash_pandas_object(df[scn], index=False).to_numpy()
        tw, tw_n = _twin_checks(df, sig)
        chk.update(tw)
        failed = [k for k, v in chk.items() if not bool(v)]
        # (the keys as plain strings, '-' for an unused dimension: a missing value would drop the row from its group)
        ps = pd.DataFrame({c: ['-' if _isnan(v) else str(v) for v in df[c].tolist()] for c in _pcols()})
        joint = (('rsiLen', ['p_rsiLen']), ('lblRead', ['p_lblRead']), ('labels', ['p_labels']),
                 ('filter (fgfOn, blkClose)', ['p_fgfOn', 'p_blkClose']), ('inv', ['p_inv']),
                 ('trail (trailOn, trailAct, trailOff)', ['p_trailOn', 'p_trailAct', 'p_trailOff']),
                 ('stop (slOn, slDist)', ['p_slOn', 'p_slDist']), ('maxOpen', ['p_maxOpen']))
        parts = []
        for name, cols in joint:
            others = [c for c in _pcols() if c not in cols]
            g = pd.Series(sig).groupby([ps[c].to_numpy() for c in others]).agg(['size', 'nunique'])
            n_all = int((g['nunique'] == g['size']).sum())
            n_any = int((g['nunique'] > 1).sum())
            live_all[name] = live_all.get(name, 0) + n_any
            parts.append('%s %d / %d / %d' % (name, n_all, n_any, len(g)))
            if int(g['size'].sum()) != len(df):
                failed.append('groups of %s do not hold every row' % name)
        n_distinct = len(np.unique(sig))
        cand = int(((df['h1r_pct'] > 0) & (df['h2r_pct'] > 0) & (df['h1_trades'] >= 30) & (df['h2_trades'] >= 30)).sum())
        _p('  %s %s (%s): %d rows, %d checks: %s' % (pair, tf, src, len(df), len(chk),
                                                     'all hold' if not failed else 'FAILED: ' + '; '.join(failed)))
        _p('    twins compared: %d normal / inverted pairs (%d of them without trailing and stop: mirror images); equal rows '
           'required for %d blocked-close pairs without a close, %d maxOpen pairs without a refused entry, %d stop pairs '
           'without a stop exit, %d trailing pairs without a trail exit'
           % (tw_n['inv'], tw_n['mir'], tw_n['blk'], tw_n['mo'], tw_n['sl'], tw_n['tr']))
        _p('    groups differing only in one dimension (all results distinct / some distinct / groups): %s' % '; '.join(parts))
        _p('    trades %d .. %d (median %d); distinct results %d of %d rows; rows positive in both fair halves with '
           '>= 30 trades in each: %d' % (tr.min(), tr.max(), int(tr.median()), n_distinct, len(df), cand))
        ok &= not failed
    dead = [k for k, v in live_all.items() if v == 0]
    _p('  every dimension changes results in at least one group over the cells: %s' % ('yes' if not dead else 'NO: %s' % dead))
    return ok and not dead


# ---------------------------------------------------------------------------------------------
# 9. every row (sceptic review)
# ---------------------------------------------------------------------------------------------
N_VIEWS = 18 * (3 + 2 * 3)          # signal inputs x (filter off | on with the close | on without it) x maxOpen


def _own_cfg(p):
    """A setting as the kernel's exit cfg, written here (unused distances NaN)."""
    nan = float('nan')
    return dict(trailOn=p['trailOn'], trailUnit='percent', trailAct=p['trailAct'] if p['trailOn'] else nan,
                trailOff=p['trailOff'] if p['trailOn'] else nan, slOn=p['slOn'], slDist=p['slDist'] if p['slOn'] else nan)


def _every_row(df, pair, tf):
    """Every row of a cell's frame recomputed in this process WITHOUT calib_xpw.py, from the row's own p_
    columns: xpw.xpw_signals with this file's xpw_params and fgf.fgf_permissions (Ref), sweep_core.prep (the
    module's own arrays: fgfBlkClose true, maxOpen 20) with the grid's two other inputs applied here
    (maxOpen replaced; fgfBlkClose false: closeL / closeS keep only the exit labels), sweep_core.run_cfg
    'mag' with inv, sweep_core.metrics_fast for our costs, the counts of the run and of the gate. Every
    view built here is first tied to the canonical engine: its tv run of the first normal and the first
    inverted setting that use it equals engine.backtest (this file's eng_params) trade by trade, and its
    gate counts are the engine's. Returns (messages, rows, values, views, engine runs)."""
    ref = Ref(pair, tf)
    keys = _keys(df)
    cols = {c: df[c].to_numpy() for c in SPEC_COLS}
    views, tied, bad = {}, set(), []
    sub = None
    cur = None
    n_vals = n_view = 0
    for i, k in enumerate(keys):
        p = dict(zip(SPEC_DIMS, k))
        ks = (p['rsiLen'], p['lblRead'], p['labels'])
        kv = ks + (p['fgfOn'], p['blkClose'], p['maxOpen'])
        if ks != cur:                                   # the file is ordered by signal input: keep one in memory
            cur = ks
            views = {}
            ref._sig = {}
        v = views.get(kv)
        if v is None:
            s = ref.sig(p)
            base = sc.prep(pair, tf, s, ref.perm, p['fgfOn'])
            if base['maxOpen'] != 20 or base['filter_on'] != p['fgfOn'] or base['inv'] is not False:
                raise AssertionError('sweep_core.prep is not what this test assumes')
            v = dict(base)
            if p['blkClose'] is False:
                idle = ~base['goL'] & ~base['goS']
                v['cL'] = idle & s['exitL'].to_numpy(bool)
                v['cS'] = idle & s['exitS'].to_numpy(bool)
            v['maxOpen'] = int(p['maxOpen'])
            v['_gate'] = {'raw_long': int((base['nL'] > 0).sum()), 'raw_short': int((base['nS'] > 0).sum()),
                          'blocked_long': int(base['blkL']), 'blocked_short': int(base['blkS'])}
            if sub is None:
                sub = sc.sub_bars(pair, tf, base['rows'])
                sc.check_mag_sync()
                sc.check_mag_equiv(base)
            views[kv] = v
            n_view += 1
        if (kv, p['inv']) not in tied:
            tied.add((kv, p['inv']))
            tr, es = ref.tv(p)
            d = cmp_trades(sc.run_cfg(v, _own_cfg(p), 'tv', inv=p['inv']), tr, v['t_close'])
            if d or any(v['_gate'][c] != int(es[c]) for c in v['_gate']):
                bad.append('the view of %r is not engine.backtest\'s: %s' % (p, d[0] if d else 'gate counts'))
        R = sc.run_cfg(v, _own_cfg(p), 'mag', sub=sub, inv=p['inv'])
        row = dict(sc.metrics_fast(pair, R, v['t_close'], ref.start, ref.end)['cost'])
        row['long_trades'] = int((R['dir'] > 0).sum())
        row['short_trades'] = int(R['n']) - row['long_trades']
        for c in ('entries_skipped_room', 'entries_ignored_pyramiding', 'close_all_bars', 'max_open'):
            row[c] = int(R[c])
        row.update(v['_gate'])
        for c in SPEC_COLS:
            n_vals += 1
            if not _same(cols[c][i], row[c]):
                bad.append('row %d %s: file %r, recomputed %r (%r)' % (i, c, cols[c][i], row[c], p) if len(bad) < 8 else '')
    return bad, len(keys), n_vals, n_view, len(tied)


def test_9_every_row():
    """(sceptic review) EVERY row of the cells' files, not a sample. The 27,216 settings of each cell are
    recomputed in this process without calib_xpw.py, each from its own p_ columns with this file's mapping
    (sweep_core.prep's arrays, maxOpen and fgfBlkClose false applied here, run_cfg 'mag', metrics_fast for
    our costs; each of the 162 views tied to engine.backtest, normal and inverted): all 32 summary columns
    equal on every row. Why: tests 2 and 3 look at 30 random rows and at the 153 rows the earlier sweep
    also holds, so a wrong result confined to a few hundred rows of the workers' output escapes them (the
    review's mutants narrow_inv: inv ignored for 216 rows, narrow_prev_signal: 84 rows on the previous
    signal input, narrow_swap_rows: two rows exchanged)."""
    ok = True
    for pair, tf in CELLS:
        df, src = _cell_df(pair, tf)
        t0 = time.time()
        bad, n_rows, n_vals, n_view, n_eng = _every_row(df, pair, tf)
        good = (not bad and n_rows == N_GRID == len(df) and n_vals == N_GRID * len(SPEC_COLS) and n_view == N_VIEWS
                and n_eng == 2 * N_VIEWS)
        _p('  %s %s (%s): every one of the %d rows recomputed without calib_xpw.py from its own p_ columns (%d views = '
           'signal input x filter mode x maxOpen, each tied to engine.backtest normal and inverted: %d engine runs): %d '
           'values (%d columns): %s (%.1fs)'
           % (pair, tf, src, n_rows, n_view, n_eng, n_vals, len(SPEC_COLS),
              'all equal' if not bad else '%d DIFFERENCES: %s' % (len(bad), '; '.join(b for b in bad if b)[:1500]), time.time() - t0))
        ok &= good
        _free()
    return ok


# ---------------------------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------------------------
def main(argv):
    global CELLS, FILES_ONLY, EXHAUSTIVE
    args = list(argv)
    if '--cells' in args:
        i = args.index('--cells')
        CELLS = [tuple(c.split(':')) for c in args[i + 1].split(',')]
        del args[i:i + 2]
    if '--files-only' in args:
        args.remove('--files-only')
        FILES_ONLY = True
    if '--exhaustive' in args:
        args.remove('--exhaustive')
        EXHAUSTIVE = True
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
    _p('calib_tests_xpw.py: cells %s; sha256 %s; load average %.2f'
       % (', '.join('%s %s' % c for c in CELLS), ', '.join('%s %s' % (f, _sha(os.path.join(W, f))[:12]) for f in SRC),
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
    return 0 if all(res.values()) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
