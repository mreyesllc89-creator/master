"""sweep_core.py: building blocks of the trailing-exit sweep (SWEEP_SPEC.md + SWEEP_SPEC_2.md).

    load_inputs(pair, tf[, labels])            -> (sig, perm) on run_tf.WINDOWS[pair], pickled
    load_sig(pair, tf, labels)                 -> sig only ('normal' | 'rev' = XPW "Reverse every
                                                  label" on), pickled; perm is the same for both
    prep(pair, tf, sig, perm, filter_on[, inv]) -> P: the arrays engine._run needs
    sub_bars(pair, tf, rows)                   -> (ptr, o, h, l, c) 1-minute sub-bars per chart row
    run_cfg(P, cfg, path[, sub, inv])          -> trade arrays + summary counts ('tv' | 'mag')
    metrics_fast(pair, R, t_close, start, end) -> {'tv0': {...}, 'cost': {...}, 'stress': {...}}
                                                  (tv0 / cost = run_tf.metrics; stress = the same
                                                  with the stressed costs of SWEEP_SPEC_2 2.)
    grid()                                     -> the 1380 settings of one (pair, TF, filter, path)

Cost modes (MODES), per unit (ounce / coin) round trip: tv0 none; cost = run_tf.cost_per_unit
(XAU 0.30; BTC 0.0002 * (entry + exit) + 0.20); stress (XAU 0.50 + 0.02; BTC 0.00035 * (entry +
exit) + 0.20 + 0.02: $0.50 / 0.035% per side + $0.20, plus 1 tick = 0.01 per side).

Fair halves (h1r_pct, h2r_pct, h1_trades, h2_trades, h1r_pf, h2r_pf, every cost mode): the
trades ENTERED in each half (entry_time <= mid, > mid; mid = start + (end - start) // 2), each
set run through run_tf.metrics()' money model on its own from a fresh 10,000 (= run_tf.metrics()
on that subset: h?r_pct = its net_pct, h?r_pf = its pf). A half without trades: h?_trades 0,
h?r_pct and h?r_pf NaN (as net_pct / pf of a run without trades); h?r_pf NaN also when the half
has no losing trade (metrics() pf None). half1_pct / half2_pct are unchanged.

UPDATE 1 ("Inverted direction: opposite side at the same entries", Pine xpwInv): prep(...,
inv=False) stores P['inv'] (aliases: prep(..., xpwInv=...) and run_cfg(..., inv=...), which
overrides P['inv']); both kernels take the flag as their last argument (engine._run's docstring
and comments say what it does; _run_mag's step 2 is the same text). False = the sweep as it was;
True: R['dir'] is the REAL side of every trade, so metrics_fast needs no change.

Path 'tv' calls engine._run itself. Path 'mag' calls _run_mag below, a copy of engine._run in
which step 1 (the pending exit orders) walks the chart bar's 1-minute sub-bars in time order,
calling engine._walk once per sub-bar with that sub-bar's own rule-2 path; the trailing state
(armed, best) carries from sub-bar to sub-bar, the gap test runs at every sub-bar open. Steps
2 and 3 (the script at the chart bar close, the window end) are a verbatim copy:
check_mag_sync() compares them with engine._run's current source and raises if they differ.

metrics_fast reproduces run_tf.metrics() bit for bit: same trade order (exit, then entry),
same event order (exits before entries at one timestamp), the same float operations in the
same order, numpy's pairwise summation for every .sum() / .mean(), and the same rounding
(numpy rounding where metrics() rounds an np.float64, Python rounding where it rounds a float).
"""
from __future__ import annotations

import inspect
import os
import pickle
import sys
import time

import numpy as np
import numba as nb
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)


def _mtimes_of(names):
    return tuple(os.stat(os.path.join(W, nm)).st_mtime_ns for nm in names)


def _proc_start_ns():
    """This process's start time (epoch ns) from /proc, or None when unknown."""
    try:
        with open('/proc/self/stat') as fh:
            st = fh.read()
        ticks = int(st[st.rindex(')') + 2:].split()[19])      # field 22: starttime (clock ticks since boot)
        with open('/proc/stat') as fh:
            btime = next(int(ln.split()[1]) for ln in fh if ln.startswith('btime '))
        return int((btime + ticks / os.sysconf('SC_CLK_TCK')) * 1e9)
    except Exception:
        return None


# modules whose output the input cache depends on: record their mtimes around the import so
# that the cache key names the version this process actually runs
_SRC_FILES = ('xpw.py', 'fgf.py')
_PRE_IMPORTED = [nm for nm in ('xpw', 'fgf') if nm in sys.modules]
_m0 = _mtimes_of(_SRC_FILES)
import xpw      # noqa: E402
import fgf      # noqa: E402
import engine   # noqa: E402
import run_tf   # noqa: E402
_m1 = _mtimes_of(_SRC_FILES)
_IMPORTED_MTIMES = _m1 if _m0 == _m1 else None      # None: changed while importing -> no cache
# The cache key must name the code this process runs: the modules must be W's files, and if a
# caller imported them before us they may be an older version than the file on disk now, unless
# the files have not changed since this process started.
if _IMPORTED_MTIMES is not None:
    try:
        _same = all(os.path.samefile(m.__file__, os.path.join(W, f)) for m, f in ((xpw, 'xpw.py'), (fgf, 'fgf.py')))
    except Exception:
        _same = False
    if not _same:
        _IMPORTED_MTIMES = None
    elif _PRE_IMPORTED:
        _ps = _proc_start_ns()
        if _ps is None or max(_m1) >= _ps - 2_000_000_000:
            _IMPORTED_MTIMES = None

from engine import _walk, K_TRAIL, K_SL, K_CLOSEALL, K_REVERSE, K_END   # noqa: E402,F401

CACHE = os.path.join(W, 'cache_sweep')
DATA = os.path.join(W, 'data')
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
UNIT_CODE = {'ticks': 0, 'price': 1, 'percent': 2}
KIND_NAMES = {K_TRAIL: 'trail', K_SL: 'sl', K_CLOSEALL: 'close_all', K_REVERSE: 'reverse', K_END: 'end'}
MINTICK = 0.01

# columns of the xpw_signals frame that engine.backtest reads (the 52 display columns pos_*,
# orient_*, inh_*, shape_* and 'events' are dropped from the cache: they do not trade)
SIG_KEEP = ('t_close', 'chartIdx', 'readAt', 'baseDir', 'nLongRaw', 'nShortRaw', 'nLong', 'nShort',
            'longSrc', 'shortSrc', 'exitL', 'exitS', 'exitLSrc', 'exitSSrc')

# ------------------------------------------------------------------- grid
ACTS = (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
OFFS = (0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
SLS = (None, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0)          # None = slOn false


def grid():
    """The 1380 settings, in a fixed order. Each: dict(tag, trailOn, trailUnit, trailAct,
    trailOff, slOn, slDist); trailAct / trailOff are NaN when trailOn is false, slDist NaN
    when slOn is false (the engine then ignores them)."""
    out = []
    for a in ACTS:
        for f in OFFS:
            for s in SLS:
                out.append(dict(tag='grid', trailOn=True, trailUnit='percent', trailAct=a, trailOff=f,
                                slOn=s is not None, slDist=np.nan if s is None else s))
    for s in SLS:
        out.append(dict(tag='grid', trailOn=False, trailUnit='percent', trailAct=np.nan, trailOff=np.nan,
                        slOn=s is not None, slDist=np.nan if s is None else s))
    d = engine.DEFAULTS
    out.append(dict(tag='default', trailOn=bool(d['trailOn']), trailUnit=d['trailUnit'],
                    trailAct=float(d['trailAct']), trailOff=float(d['trailOff']),
                    slOn=bool(d['slOn']), slDist=np.nan))
    return out


def cfg_params(cfg):
    """A grid setting as engine.backtest params (NaN placeholders -> the engine defaults)."""
    d = engine.DEFAULTS
    p = {'trailOn': bool(cfg['trailOn']), 'trailUnit': cfg['trailUnit'], 'slOn': bool(cfg['slOn'])}
    for k in ('trailAct', 'trailOff', 'slDist'):
        v = cfg.get(k, np.nan)
        p[k] = float(d[k]) if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)
    return p


# ------------------------------------------------------------------ inputs
def _data_mtimes(pair):
    fs = sorted(f for f in os.listdir(DATA) if f.startswith(pair + '_') and f.endswith('.parquet'))
    return tuple((f, os.stat(os.path.join(DATA, f)).st_mtime_ns) for f in fs)


def _trim_sig(sig):
    return sig[[c for c in SIG_KEEP if c in sig.columns]].copy()


def compute_inputs(pair, tf, start, end):
    sig = xpw.xpw_signals(pair, tf, start, end, {})
    perm = fgf.fgf_permissions(pair, tf, start, end, {})
    if not perm.index.equals(sig.index):
        raise ValueError('xpw / fgf rows differ for %s %s' % (pair, tf))
    return _trim_sig(sig), perm


LABELS = ('normal', 'rev')
LABEL_PARAMS = {'normal': {}, 'rev': {'reverseAll': True}}     # xpw_signals params per labels


def compute_sig(pair, tf, start, end, labels):
    return _trim_sig(xpw.xpw_signals(pair, tf, start, end, dict(LABEL_PARAMS[labels])))


def _cache_slot(pair, tf, start, end, labels):
    """(key, path) of the cache file for (pair, tf, window, labels), or (None, None) when no cache
    may be used: the key holds the mtimes of xpw.py and fgf.py as imported by this process (they
    must still be the files on disk) and of the pair's data files. The 'normal' key / file name are
    those of SWEEP_SPEC.md's cache (sig + perm); 'rev' adds labels and the xpw params (sig only)."""
    if _IMPORTED_MTIMES is None or _mtimes_of(_SRC_FILES) != _IMPORTED_MTIMES:
        return None, None
    key = dict(pair=pair, tf=tf, start=start, end=end, src=_IMPORTED_MTIMES, data=_data_mtimes(pair))
    tag = '%s_%s_%d_%d_x%d_f%d' % (pair, tf, start, end, key['src'][0], key['src'][1])
    if labels != 'normal':
        key['labels'] = labels
        key['params'] = dict(LABEL_PARAMS[labels])
        tag += '_' + labels
    return key, os.path.join(CACHE, tag + '.pkl')


def _cache_read(key, path, what, verbose):
    if key is None or not os.path.exists(path):
        return None
    try:
        with open(path, 'rb') as fh:
            obj = pickle.load(fh)
        if obj.get('key') == key:
            if verbose:
                print('  %s: cache %s' % (what, os.path.basename(path)), flush=True)
            return obj
    except Exception as e:  # corrupt / partial file: recompute
        print('  cache read failed (%s): recomputing' % e, flush=True)
    return None


def _cache_write(key, path, pair, payload, verbose):
    """Write only when the source files on disk are still the versions this process imported and
    the data files did not change while computing (so a stale cache is never written, nor read)."""
    if key is not None and _mtimes_of(_SRC_FILES) == _IMPORTED_MTIMES and _data_mtimes(pair) == key['data']:
        os.makedirs(CACHE, exist_ok=True)
        tmp = path + '.tmp%d' % os.getpid()
        with open(tmp, 'wb') as fh:
            pickle.dump(dict(payload, key=key), fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
    elif verbose:
        print('  (xpw.py / fgf.py / data changed since import, or xpw / fgf imported before sweep_core'
              ' and changed since this process started: inputs not cached)', flush=True)


def load_inputs(pair, tf, verbose=True, labels='normal'):
    """sig, perm on run_tf.WINDOWS[pair], cached in cache_sweep/ under a key made of pair, tf,
    window, the mtimes of xpw.py and fgf.py as imported by this process, and the mtimes of the
    pair's data files. A cache is written only when the source files on disk are still the
    versions this process imported (so a stale cache is never written, nor read).
    labels 'rev': sig = load_sig(pair, tf, 'rev') (XPW "Reverse every label" on), perm as for
    'normal' (the filter does not read the labels)."""
    tf = str(tf)
    if labels != 'normal':
        sig = load_sig(pair, tf, labels, verbose)
        return sig, load_inputs(pair, tf, verbose)[1]
    start, end = run_tf.WINDOWS[pair]
    key, path = _cache_slot(pair, tf, start, end, 'normal')
    obj = _cache_read(key, path, 'inputs %s %s' % (pair, tf), verbose)
    if obj is not None:
        return obj['sig'], obj['perm']
    t0 = time.time()
    sig, perm = compute_inputs(pair, tf, start, end)
    if verbose:
        print('  inputs %s %s: computed in %.1fs (%d rows)' % (pair, tf, time.time() - t0, len(sig)), flush=True)
    _cache_write(key, path, pair, {'sig': sig, 'perm': perm}, verbose)
    return sig, perm


def load_sig(pair, tf, labels='normal', verbose=True):
    """The trimmed xpw_signals frame on run_tf.WINDOWS[pair] for labels 'normal' (params {}) or
    'rev' (params {'reverseAll': True}), cached like load_inputs (rev in its own file)."""
    tf = str(tf)
    if labels not in LABEL_PARAMS:
        raise ValueError('labels %r not one of %r' % (labels, LABELS))
    if labels == 'normal':
        return load_inputs(pair, tf, verbose)[0]
    start, end = run_tf.WINDOWS[pair]
    key, path = _cache_slot(pair, tf, start, end, labels)
    what = 'sig %s %s %s' % (pair, tf, labels)
    obj = _cache_read(key, path, what, verbose)
    if obj is not None:
        return obj['sig']
    t0 = time.time()
    sig = compute_sig(pair, tf, start, end, labels)
    if verbose:
        print('  %s: computed in %.1fs (%d rows)' % (what, time.time() - t0, len(sig)), flush=True)
    _cache_write(key, path, pair, {'sig': sig}, verbose)
    return sig


# -------------------------------------------------------------------- prep
def prep(pair, tf, sig, perm, filter_on, inv=False, xpwInv=None):
    """The arrays engine._run needs, computed exactly as engine.backtest_bars does with the
    Pine defaults (tradeDir Both, oppCloses true, fgfBlkClose true, maxOpen 20, pyramiding
    100, Signal tick, mintick 0.01). filter_on False = perm None / fgfOn false.
    inv (alias xpwInv) = UPDATE 1's "Inverted direction": stored as P['inv'] for run_cfg. With
    tradeDir Both the signal arrays do not depend on it (the gate works in the normal frame)."""
    if xpwInv is not None:
        if inv and not xpwInv:
            raise ValueError("prep: 'inv' and 'xpwInv' disagree")
        inv = xpwInv
    p = engine._params({'fgfOn': bool(filter_on), 'fgfBlkClose': True, 'xpwInv': bool(inv)})
    allb = engine.load_bars(pair, tf)
    rows = np.asarray(sig.index, dtype=np.int64)
    n = len(rows)
    if n and (rows.min() < 0 or rows.max() >= len(allb)):
        raise ValueError('sig index outside data/%s_%s.parquet' % (pair, tf))
    bars = allb.iloc[rows]
    # own writable copies: pandas hands out read-only views, and numba compiles a separate
    # version of each kernel for read-only arrays (warmup() compiles the writable one)
    t_close = np.array(bars['t_close'].to_numpy(np.int64), copy=True)
    if 't_close' in sig and not np.array_equal(t_close, sig['t_close'].to_numpy(np.int64)):
        raise ValueError('sig t_close does not match the data file rows')
    if n > 1 and not (np.diff(t_close) > 0).all():
        raise ValueError('t_close not strictly increasing')
    o = np.array(bars['open'].to_numpy(np.float64), copy=True)
    h = np.array(bars['high'].to_numpy(np.float64), copy=True)
    l = np.array(bars['low'].to_numpy(np.float64), copy=True)
    c = np.array(bars['close'].to_numpy(np.float64), copy=True)
    t_open = np.array(bars['t_open'].to_numpy(np.int64), copy=True)

    longSrc = engine._src_lists(sig, 'longSrc')
    shortSrc = engine._src_lists(sig, 'shortSrc')
    nLraw = np.fromiter((len(x) for x in longSrc), np.int64, n)
    nSraw = np.fromiter((len(x) for x in shortSrc), np.int64, n)
    both = (nLraw > 0) & (nSraw > 0)
    nL = np.where(both, 0, nLraw)
    nS = np.where(both, 0, nSraw)
    if 'nLong' in sig and 'nShort' in sig:
        if not (np.array_equal(sig['nLong'].to_numpy(np.int64), nL)
                and np.array_equal(sig['nShort'].to_numpy(np.int64), nS)):
            raise ValueError('sig nLong / nShort disagree with the longSrc / shortSrc lists')
    exitL = sig['exitL'].to_numpy(bool) if 'exitL' in sig else np.zeros(n, bool)
    exitS = sig['exitS'].to_numpy(bool) if 'exitS' in sig else np.zeros(n, bool)

    filt = bool(p['fgfOn']) and perm is not None
    if filt:
        if not perm.index.equals(sig.index):
            perm = perm.reindex(sig.index)
            if perm[['buyOk', 'sellOk']].isna().any().any():
                raise ValueError('perm does not cover every sig row')
        buyOk = perm['buyOk'].to_numpy(bool)
        sellOk = perm['sellOk'].to_numpy(bool)
    else:
        buyOk = np.ones(n, bool)
        sellOk = np.ones(n, bool)
    inv = bool(p['xpwInv'])
    if inv:                               # as engine.backtest_bars (Pine allowLong / allowShort)
        allowLong = p['tradeDir'] != 'Long only (buy only)'
        allowShort = p['tradeDir'] != 'Short only (sell only)'
    else:
        allowLong = p['tradeDir'] != 'Short only (sell only)'
        allowShort = p['tradeDir'] != 'Long only (buy only)'
    sigLong = (nL > 0) & allowLong
    sigShort = (nS > 0) & allowShort
    blkL = sigLong & ~buyOk
    blkS = sigShort & ~sellOk
    goLong = sigLong & ~blkL
    goShort = sigShort & ~blkS
    oc = bool(p['oppCloses'])
    bc = bool(p['fgfBlkClose'])
    oppL = (nS > 0) & ((oc and not allowShort) | (bc & blkS))
    oppS = (nL > 0) & ((oc and not allowLong) | (bc & blkL))
    cL = ~goLong & ~goShort & (exitL | oppL)
    cS = ~goShort & ~goLong & (exitS | oppS)
    cap = int((nL * goLong).sum() + (nS * goShort).sum()) + 1
    ocap = int(max(p['maxOpen'], int(nL.max(initial=0)), int(nS.max(initial=0)))) + 2
    mt = float(p['mintick'])
    return dict(pair=pair, tf=str(tf), filter_on=filt, rows=rows, t_open=t_open, t_close=t_close,
                o=o, h=h, l=l, c=c, goL=goLong, goS=goShort,
                nL=nL.astype(np.int64), nS=nS.astype(np.int64), cL=cL, cS=cS,
                maxOpen=int(p['maxOpen']), pyr=int(p['pyramiding']), mt=mt, tol=mt * 1e-6,
                cap=cap, ocap=ocap, blkL=int(blkL.sum()), blkS=int(blkS.sum()), inv=inv)


# ---------------------------------------------------------------- sub-bars
_M1_CACHE: dict = {}


def _m1(pair):
    d = _M1_CACHE.get(pair)
    if d is None:
        df = pd.read_parquet(os.path.join(DATA, '%s_1.parquet' % pair),
                             columns=['open', 'high', 'low', 'close', 't_open'])
        d = {k: np.ascontiguousarray(df[k].to_numpy(np.float64 if k != 't_open' else np.int64))
             for k in df.columns}
        if len(d['t_open']) > 1 and not (np.diff(d['t_open']) > 0).all():
            raise ValueError('%s_1 t_open not strictly increasing' % pair)
        _M1_CACHE[pair] = d
    return d


def sub_bars(pair, tf, rows, check=True):
    """1-minute sub-bars of the chart rows `rows` of data/<pair>_<tf>.parquet: the rows of
    data/<pair>_1.parquet with t_open in [bar t_open, bar t_close). Returns (ptr, o, h, l, c):
    ptr int64 (n+1), sub-bars of chart row k = [ptr[k], ptr[k+1]) of the contiguous arrays.
    With check, every chart bar must have >= 1 sub-bar and its OHLC must equal the sub-bars'
    first open / max high / min low / last close (build_bars.py built it from them)."""
    rows = np.asarray(rows, dtype=np.int64)
    bars = engine.load_bars(pair, str(tf))
    bo = bars['t_open'].to_numpy(np.int64)[rows]
    bc = bars['t_close'].to_numpy(np.int64)[rows]
    m = _m1(pair)
    s = np.searchsorted(m['t_open'], bo, side='left')
    e = np.searchsorted(m['t_open'], bc, side='left')
    ln = (e - s).astype(np.int64)
    ptr = np.zeros(len(rows) + 1, np.int64)
    np.cumsum(ln, out=ptr[1:])
    tot = int(ptr[-1])
    idx = np.repeat(s - ptr[:-1], ln) + np.arange(tot, dtype=np.int64)
    so = np.ascontiguousarray(m['open'][idx])
    sh = np.ascontiguousarray(m['high'][idx])
    sl = np.ascontiguousarray(m['low'][idx])
    sc = np.ascontiguousarray(m['close'][idx])
    if check and len(rows):
        if (ln <= 0).any():
            raise ValueError('%s %s: %d chart bars without 1-minute sub-bars' % (pair, tf, int((ln <= 0).sum())))
        st = ptr[:-1]
        ok = ((so[st] == bars['open'].to_numpy()[rows]) & (sc[ptr[1:] - 1] == bars['close'].to_numpy()[rows])
              & (np.maximum.reduceat(sh, st) == bars['high'].to_numpy()[rows])
              & (np.minimum.reduceat(sl, st) == bars['low'].to_numpy()[rows]))
        if not ok.all():
            raise ValueError('%s %s: %d chart bars differ from their sub-bars' % (pair, tf, int((~ok).sum())))
    return ptr, so, sh, sl, sc


def fake_sub_bars(P):
    """Every chart bar is its own single sub-bar (test T3)."""
    n = len(P['c'])
    return (np.arange(n + 1, dtype=np.int64), P['o'].copy(), P['h'].copy(), P['l'].copy(), P['c'].copy())


# ------------------------------------------------------------------ kernels
@nb.njit
def _to_ticks(d, ref, unit, mt):
    # = engine._to_ticks (Pine toTicks)
    if unit == 0:
        return d
    elif unit == 1:
        return d / mt
    return ref * d / 100.0 / mt


# NOTE: not cache=True: it calls engine._walk, and numba's on-disk cache of this file would not
# notice a change in engine.py. Compiled once per process (the sweep compiles before forking).
@nb.njit
def _run_mag(o, h, l, c, ptr, so, sh, sl_, sc, goL, goS, nl, ns, cL, cS,
             maxOpen, pyr, trailOn, slOn, unit, trailAct, trailOff, slDist, mt, tol, cap, ocap, inv=False):
    # inv = Pine xpwInv (UPDATE 1), as in engine._run: the signal arrays are in the normal frame,
    # t_dir / pos_dir / the exit levels are the REAL side (step 1 walks the real position).
    n = c.shape[0]
    t_dir = np.zeros(cap, np.int8)
    t_row = np.zeros(cap, np.int64)
    t_k = np.zeros(cap, np.int32)
    t_epx = np.zeros(cap, np.float64)
    t_A = np.full(cap, np.nan)          # activation price (long space)
    t_off = np.full(cap, np.nan)        # trail offset, price
    t_sl = np.full(cap, np.nan)         # stop-loss price (long space)
    t_act = np.zeros(cap, np.bool_)
    t_best = np.zeros(cap, np.float64)
    t_xrow = np.full(cap, -1, np.int64)
    t_xpx = np.full(cap, np.nan)
    t_xkind = np.zeros(cap, np.int8)
    t_xby = np.full(cap, -1, np.int64)  # reverse: id of the reversing trade
    bar_close = np.zeros(n, np.int8)    # 1 = closeL fired, 2 = closeS (normal frame: xpwPosN > 0 / < 0)
    bar_skip = np.zeros(n, np.int32)    # entries not placed (room)
    bar_pyr = np.zeros(n, np.int32)     # entries placed but ignored (pyramiding)
    bar_open = np.zeros(n, np.int32)    # strategy.opentrades seen by the script
    bar_pos = np.zeros(n, np.int8)      # sign of strategy.position_size seen by the script
    open_ids = np.empty(ocap, np.int64)
    n_open = 0
    pos_dir = 0
    n_tr = 0
    for i in range(n):
        # 1. (Bar Magnifier) pending exit orders of open trades, along the chart bar's
        #    1-minute sub-bars in time order, each sub-bar with its own rule-2 path; the
        #    trailing state carries from sub-bar to sub-bar; the gap test runs at every
        #    sub-bar open. Trades are independent here, so each trade walks its sub-bars
        #    until it exits (same result as sub-bar-major order).
        if n_open > 0:
            sgn = float(pos_dir)
            s0 = ptr[i]
            s1 = ptr[i + 1]
            w = 0
            for q in range(n_open):
                j = open_ids[q]
                has_tr = not np.isnan(t_A[j])
                has_sl = not np.isnan(t_sl[j])
                kind = 0
                px = 0.0
                if has_tr or has_sl:
                    a2 = t_act[j]
                    b2 = t_best[j]
                    for s in range(s0, s1):
                        if (sh[s] - so[s]) < (so[s] - sl_[s]):
                            p1 = sh[s]
                            p2 = sl_[s]
                        else:
                            p1 = sl_[s]
                            p2 = sh[s]
                        kind, px, a2, b2 = _walk(sgn * so[s], sgn * p1, sgn * p2, sgn * sc[s], a2, b2,
                                                 t_A[j], t_off[j], t_sl[j], has_tr, has_sl, tol)
                        if kind != 0:
                            break
                    t_act[j] = a2
                    t_best[j] = b2
                if kind != 0:
                    t_xrow[j] = i
                    t_xpx[j] = sgn * px
                    t_xkind[j] = kind
                else:
                    open_ids[w] = j
                    w += 1
            n_open = w
            if n_open == 0:
                pos_dir = 0
        # 2. the script at the close, with the updated position
        pos = pos_dir                    # sign of strategy.position_size (the real position)
        posn = -pos if inv else pos      # Pine xpwPosN: the position in the normal frame
        opent = n_open
        bar_open[i] = opent
        bar_pos[i] = pos
        if (posn > 0 and cL[i]) or (posn < 0 and cS[i]):
            for q in range(n_open):
                j = open_ids[q]
                t_xrow[j] = i
                t_xpx[j] = c[i]
                t_xkind[j] = K_CLOSEALL
            bar_close[i] = 1 if posn > 0 else 2
            n_open = 0
            pos_dir = 0
        room = maxOpen - opent
        for side in range(2):
            if side == 0:
                if not goL[i]:
                    continue
                d = 1
                cnt = nl[i]
            else:
                if not goS[i]:
                    continue
                d = -1
                cnt = ns[i]
            dr = -d if inv else d        # the side really traded (Pine realLong)
            for k in range(cnt):
                if room > 0 or posn == -d:
                    # market order, filled at this close in placement order
                    if pos_dir == -dr:
                        for q in range(n_open):
                            j = open_ids[q]
                            t_xrow[j] = i
                            t_xpx[j] = c[i]
                            t_xkind[j] = K_REVERSE
                            t_xby[j] = n_tr
                        n_open = 0
                        pos_dir = 0
                    if pos_dir == dr and n_open >= pyr:
                        bar_pyr[i] += 1
                    else:
                        j = n_tr
                        n_tr += 1
                        t_dir[j] = dr
                        t_row[j] = i
                        t_k[j] = k + 1
                        t_epx[j] = c[i]
                        e = dr * c[i]
                        ref = c[i]
                        if trailOn:
                            trp = _to_ticks(trailAct, ref, unit, mt)
                            if trp < 0.0:
                                trp = 0.0
                            tro = _to_ticks(trailOff, ref, unit, mt)
                            if tro < 1.0:
                                tro = 1.0
                            t_A[j] = e + trp * mt
                            t_off[j] = tro * mt
                            t_act[j] = e >= t_A[j] - tol      # trail_points 0: armed at the fill
                            t_best[j] = e
                        if slOn:
                            slp = _to_ticks(slDist, ref, unit, mt)
                            if slp < 1.0:
                                slp = 1.0
                            t_sl[j] = e - slp * mt
                        open_ids[n_open] = j
                        n_open += 1
                        pos_dir = dr
                    room -= 1
                else:
                    bar_skip[i] += 1
    # 3. trades still open at the window end
    if n > 0:
        for q in range(n_open):
            j = open_ids[q]
            t_xrow[j] = n - 1
            t_xpx[j] = c[n - 1]
            t_xkind[j] = K_END
    return (n_tr, t_dir, t_row, t_k, t_epx, t_A, t_off, t_sl, t_xrow, t_xpx, t_xkind, t_xby,
            bar_close, bar_skip, bar_pyr, bar_open, bar_pos)


def _norm_tail(src, start_marker):
    i = src.index(start_marker)
    return [ln.rstrip() for ln in src[i:].splitlines() if ln.strip()]


def check_mag_sync():
    """Raise if _run_mag's non-step-1 code (allocations, step 2, step 3) differs from the
    current engine._run source, or engine._to_ticks from ours."""
    eng = inspect.getsource(engine._run.py_func)
    mag = inspect.getsource(_run_mag.py_func)
    a, b = '    n = c.shape[0]', '        # 1. '
    pre_e = eng[eng.index(a):eng.index(b)]
    pre_m = mag[mag.index(a):mag.index(b)]
    if pre_e != pre_m:
        raise AssertionError('_run_mag allocations differ from engine._run')
    if _norm_tail(eng, '        # 2. the script at the close') != _norm_tail(mag, '        # 2. the script at the close'):
        raise AssertionError('_run_mag steps 2-3 differ from engine._run')
    te = inspect.getsource(engine._to_ticks.py_func)
    tm = inspect.getsource(_to_ticks.py_func)
    body = lambda s: [ln.strip() for ln in s.splitlines() if ln.strip() and not ln.strip().startswith(('#', '@', 'def '))]
    if body(te) != body(tm):
        raise AssertionError('_to_ticks differs from engine._to_ticks')
    return True


def check_mag_equiv(P):
    """Runtime guard for step 1, which check_mag_sync() does not compare: with every chart bar
    its own single sub-bar, _run_mag must equal engine._run (as it is now) on a few settings.
    Raises AssertionError if engine.py's step 1 has changed in a way _run_mag does not follow."""
    sub = fake_sub_bars(P)
    G = grid()
    for cfg in (G[-1], G[0], G[len(G) // 2], G[-4]):
        for inv in (False, True):         # UPDATE 1: with and without "Inverted direction"
            a = run_cfg(P, cfg, 'tv', inv=inv)
            b = run_cfg(P, cfg, 'mag', sub=sub, inv=inv)
            if a['n'] != b['n'] or not all(np.array_equal(a[x], b[x]) for x in ('dir', 'erow', 'k', 'epx', 'xrow', 'xpx', 'xkind')):
                raise AssertionError('_run_mag with one sub-bar per chart bar != engine._run for %r (inv %s): '
                                     'engine.py step 1 changed? re-check _run_mag' % (cfg, inv))
    return True


# ------------------------------------------------------------------ run_cfg
def _cfg_tuple(cfg):
    p = cfg_params(cfg)
    return (bool(p['trailOn']), bool(p['slOn']), UNIT_CODE[p['trailUnit']],
            float(p['trailAct']), float(p['trailOff']), float(p['slDist']))


def run_cfg(P, cfg, path='tv', sub=None, inv=None):
    """One backtest. cfg: dict with trailOn, trailUnit, trailAct, trailOff, slOn, slDist (NaN
    placeholders take the engine defaults). path 'tv' = engine._run; 'mag' = _run_mag on the
    sub-bars `sub` (default P['sub']). Returns dict: n, dir, erow, epx, xrow, xpx, xkind
    (rows = positions in the window; P['rows'][erow] = data file rows) and summary counts.
    inv: UPDATE 1's "Inverted direction" (Pine xpwInv); None = P['inv'] (False when P has none).
    dir is the REAL side of each trade."""
    trailOn, slOn, unit, act, off, sld = _cfg_tuple(cfg)
    inv = bool(P.get('inv', False)) if inv is None else bool(inv)
    if path == 'tv':
        r = engine._run(P['o'], P['h'], P['l'], P['c'], P['goL'], P['goS'], P['nL'], P['nS'], P['cL'], P['cS'],
                        P['maxOpen'], P['pyr'], trailOn, slOn, unit, act, off, sld, P['mt'], P['tol'],
                        P['cap'], P['ocap'], inv)
    elif path == 'mag':
        ptr, so, sh, sl, sc = sub if sub is not None else P['sub']
        r = _run_mag(P['o'], P['h'], P['l'], P['c'], ptr, so, sh, sl, sc,
                     P['goL'], P['goS'], P['nL'], P['nS'], P['cL'], P['cS'],
                     P['maxOpen'], P['pyr'], trailOn, slOn, unit, act, off, sld, P['mt'], P['tol'],
                     P['cap'], P['ocap'], inv)
    else:
        raise ValueError('path %r' % (path,))
    (n_tr, t_dir, t_row, t_k, t_epx, t_A, t_off, t_sl, t_xrow, t_xpx, t_xkind, t_xby,
     bar_close, bar_skip, bar_pyr, bar_open, bar_pos) = r
    xk = t_xkind[:n_tr]
    cnt = np.bincount(xk, minlength=6) if n_tr else np.zeros(6, np.int64)
    return dict(n=int(n_tr), dir=t_dir[:n_tr], erow=t_row[:n_tr], k=t_k[:n_tr], epx=t_epx[:n_tr],
                xrow=t_xrow[:n_tr], xpx=t_xpx[:n_tr], xkind=xk,
                entries=int(n_tr), exits_trail=int(cnt[K_TRAIL]), exits_sl=int(cnt[K_SL]),
                exits_close_all=int(cnt[K_CLOSEALL]), exits_reverse=int(cnt[K_REVERSE]),
                exits_end=int(cnt[K_END]), entries_skipped_room=int(bar_skip.sum()),
                entries_ignored_pyramiding=int(bar_pyr.sum()), close_all_bars=int((bar_close > 0).sum()),
                max_open=int(bar_open.max(initial=0)))


# ------------------------------------------------------------------ metrics
@nb.njit(cache=True)
def _pw_block(a, s, n):
    """numpy's pairwise_sum for n <= 128 (the leaves of its recursion)."""
    if n < 8:
        res = 0.0
        for i in range(n):
            res += a[s + i]
        return res
    elif n <= 128:
        r0 = a[s]
        r1 = a[s + 1]
        r2 = a[s + 2]
        r3 = a[s + 3]
        r4 = a[s + 4]
        r5 = a[s + 5]
        r6 = a[s + 6]
        r7 = a[s + 7]
        i = 8
        m = n - (n % 8)
        while i < m:
            r0 += a[s + i]
            r1 += a[s + i + 1]
            r2 += a[s + i + 2]
            r3 += a[s + i + 3]
            r4 += a[s + i + 4]
            r5 += a[s + i + 5]
            r6 += a[s + i + 6]
            r7 += a[s + i + 7]
            i += 8
        res = ((r0 + r1) + (r2 + r3)) + ((r4 + r5) + (r6 + r7))
        while i < n:
            res += a[s + i]
            i += 1
        return res


@nb.njit(cache=True)
def _pairwise(a, s, n):
    """numpy's pairwise_sum (loops_utils.h), bit for bit: ndarray.sum() of a contiguous float64
    array = 0.0 + _pairwise(a, 0, len(a)). numpy recurses pw(s, n) = pw(s, n2) + pw(s + n2,
    n - n2) with n2 = n // 2 - (n // 2) % 8 while n > 128; this walks the same tree with an
    explicit stack (numba's on-disk cache does not support recursive functions)."""
    if n <= 128:
        return _pw_block(a, s, n)
    ss = np.empty(64, np.int64)       # frame start
    nn = np.empty(64, np.int64)       # frame length
    stage = np.empty(64, np.int64)    # 0: expand, 1: waiting for left, 2: waiting for right
    left = np.empty(64)
    ss[0] = s
    nn[0] = n
    stage[0] = 0
    sp = 1
    val = 0.0
    have = False                      # val is a finished child sum for frame sp - 1
    while True:
        top = sp - 1
        if not have:
            # expand: first the left half
            n2 = nn[top] // 2
            n2 -= n2 % 8
            stage[top] = 1
            if n2 <= 128:
                val = _pw_block(a, ss[top], n2)
                have = True
            else:
                ss[sp] = ss[top]
                nn[sp] = n2
                stage[sp] = 0
                sp += 1
        elif stage[top] == 1:
            left[top] = val
            stage[top] = 2
            have = False
            n2 = nn[top] // 2
            n2 -= n2 % 8
            cs = ss[top] + n2
            cn = nn[top] - n2
            if cn <= 128:
                val = _pw_block(a, cs, cn)
                have = True
            else:
                ss[sp] = cs
                nn[sp] = cn
                stage[sp] = 0
                sp += 1
        else:
            val = left[top] + val
            sp -= 1
            if sp == 0:
                return val


@nb.njit(cache=True)
def _npsum(a, n):
    return 0.0 + _pairwise(a, 0, n)


# raw (unrounded) metric slots
M_TRADES, M_NET, M_PF, M_WIN, M_DD, M_H1, M_H2, M_AVG, M_MAXC, M_TRAIL, M_SL, M_CLOSEALL, \
    M_REVERSE, M_END, M_EXPO, M_BARS, M_H1R, M_H2R, M_H1N, M_H2N, M_H1PF, M_H2PF = range(22)
NM = 22
MODES = ('tv0', 'cost', 'stress')        # rows of the raw metrics array


@nb.njit(cache=True)
def _sim_subset(ks, js, ns, order, tpos, erow, xrow, epx, pnl, cap0, frac, qty, realized, tmp):
    """run_tf.metrics()' money model on a subset of the trades on its own, from a fresh cap0:
    ks[:ns] = the subset's positions in t (trades sorted by exit, entry) in t order, js[:ns] = its
    trade ids (entry order). Same operations in the same order as metrics() on the subset frame
    (it sorts the subset by exit / entry time = the restriction of t's order; events in time
    order, exits before entries at one timestamp). Returns (net %, pf; NaN pf without a loss).
    Overwrites qty / realized at the subset's positions."""
    for q in range(ns):
        qty[ks[q]] = 0.0
        realized[ks[q]] = 0.0
    eq = cap0
    ie = 0
    ii = 0
    while ie < ns or ii < ns:
        if ie < ns and (ii >= ns or xrow[order[ks[ie]]] <= erow[js[ii]]):
            k = ks[ie]
            realized[k] = qty[k] * pnl[k]
            eq += realized[k]
            ie += 1
        else:
            j = js[ii]
            k = tpos[j]
            mm = 0.0 if 0.0 > eq else eq
            qty[k] = frac * mm / epx[j]
            ii += 1
    s = 0.0
    for q in range(ns):
        s += realized[ks[q]]
    curve_last = cap0 + s
    c = 0
    for q in range(ns):
        r = realized[ks[q]]
        if r > 0:
            tmp[c] = r
            c += 1
    wins = _npsum(tmp, c)
    c = 0
    for q in range(ns):
        r = realized[ks[q]]
        if r < 0:
            tmp[c] = r
            c += 1
    losses = -_npsum(tmp, c)
    net = 100 * (curve_last - cap0) / cap0
    pf = wins / losses if losses > 0 else np.nan
    return net, pf


@nb.njit(cache=True)
def _metrics_kernel(is_btc, n, dirs, erow, epx, xrow, xpx, xkind, t_close, mid, cap0, frac, out):
    """out[m, :] for m = 0 (tv0), 1 (cost) and 2 (stress): the values run_tf.metrics() rounds,
    before rounding (NaN pf when there is no loss), plus the extra fields and the fair halves."""
    out[:, :] = np.nan
    nmode = out.shape[0]
    for m in range(nmode):
        out[m, M_TRADES] = n
    if n == 0:
        for m in range(nmode):
            for f in (M_MAXC, M_TRAIL, M_SL, M_CLOSEALL, M_REVERSE, M_END, M_H1N, M_H2N):
                out[m, f] = 0.0
        return
    nb_ = t_close.shape[0] + 1
    key = np.empty(n, np.int64)
    for j in range(n):
        key[j] = xrow[j] * nb_ + erow[j]
    order = np.argsort(key, kind='mergesort')       # t = trades sorted by (exit_time, entry_time)
    tpos = np.empty(n, np.int64)
    for k in range(n):
        tpos[order[k]] = k
    kc = np.zeros(6, np.int64)
    bars_sum = 0.0
    for j in range(n):
        kc[xkind[j]] += 1
        bars_sum += float(xrow[j] - erow[j])
    pnl = np.empty(n)
    ret = np.empty(n)
    qty = np.empty(n)
    realized = np.empty(n)
    exited = np.empty(n, np.bool_)
    tmp = np.empty(n)
    # fair halves: trades entered at t_close <= mid (half 0) / > mid (half 1), as positions in t
    # (t order) and as trade ids (entry order)
    hk = np.empty((2, n), np.int64)
    hj = np.empty((2, n), np.int64)
    hn = np.zeros(2, np.int64)
    for k in range(n):
        h = 0 if t_close[erow[order[k]]] <= mid else 1
        hk[h, hn[h]] = k
        hn[h] += 1
    hn[:] = 0
    for j in range(n):
        h = 0 if t_close[erow[j]] <= mid else 1
        hj[h, hn[h]] = j
        hn[h] += 1
    for m in range(nmode):
        for k in range(n):
            j = order[k]
            e = epx[j]
            x = xpx[j]
            g = float(dirs[j]) * (x - e)
            if m == 1:
                if is_btc:
                    cst = 0.0002 * (e + x) + 0.20
                else:
                    cst = 0.30
            elif m == 2:
                # stress: 0.035% / $0.50 per side + $0.20 per coin, plus 1 tick per side
                if is_btc:
                    cst = 0.00035 * (e + x) + 0.20 + 0.02
                else:
                    cst = 0.50 + 0.02
            else:
                cst = 0.0
            pnl[k] = g - cst
            ret[k] = pnl[k] / e
            qty[k] = 0.0
            realized[k] = 0.0
            exited[k] = False
        # events in time order, exits before entries at one timestamp; exits in t order,
        # entries in entry order (t_close strictly increasing: rows order = time order)
        eq = cap0
        ie = 0
        ii = 0
        cc = 0
        mc = 0
        open_not = 0.0
        n_open = 0
        max_expo = -np.inf
        while ie < n or ii < n:
            if ie < n and (ii >= n or xrow[order[ie]] <= erow[ii]):
                k = ie
                realized[k] = qty[k] * pnl[k]
                eq += realized[k]
                exited[k] = True
                cc -= 1
                ie += 1
                # open notional bookkeeping (max_expo)
                j = order[k]
                if j < ii:                       # its entry was processed: it was open
                    open_not -= qty[k] * epx[j]
                    n_open -= 1
                    if n_open == 0:
                        open_not = 0.0
            else:
                j = ii
                k = tpos[j]
                mm = 0.0 if 0.0 > eq else eq
                qty[k] = frac * mm / epx[j]
                cc += 1
                if cc > mc:
                    mc = cc
                ii += 1
                if not exited[k]:
                    open_not += qty[k] * epx[j]
                    n_open += 1
                    ex = open_not / eq if eq > 0.0 else np.inf
                    if ex > max_expo:
                        max_expo = ex
        # equity curve by exit order
        s = 0.0
        peak = cap0
        dd = -np.inf
        for k in range(n):
            s += realized[k]
            cv = cap0 + s
            if cv > peak:
                peak = cv
            v = (peak - cv) / peak
            if v > dd:
                dd = v
        curve_last = cap0 + s
        # wins / losses / halves: pairwise sums of the masked arrays (in t order)
        q = 0
        for k in range(n):
            if realized[k] > 0:
                tmp[q] = realized[k]
                q += 1
        n_win = q
        wins = _npsum(tmp, q)
        q = 0
        for k in range(n):
            if realized[k] < 0:
                tmp[q] = realized[k]
                q += 1
        losses = -_npsum(tmp, q)
        q = 0
        for k in range(n):
            if t_close[xrow[order[k]]] <= mid:
                tmp[q] = realized[k]
                q += 1
        h1 = _npsum(tmp, q)
        q = 0
        for k in range(n):
            if t_close[xrow[order[k]]] > mid:
                tmp[q] = realized[k]
                q += 1
        h2 = _npsum(tmp, q)
        out[m, M_NET] = 100 * (curve_last - cap0) / cap0
        out[m, M_PF] = wins / losses if losses > 0 else np.nan
        out[m, M_WIN] = 100 * (n_win / n)
        out[m, M_DD] = 100 * dd
        out[m, M_H1] = 100 * h1 / cap0
        out[m, M_H2] = 100 * h2 / cap0
        out[m, M_AVG] = 100 * (_npsum(ret, n) / n)
        out[m, M_MAXC] = mc
        out[m, M_TRAIL] = kc[1]
        out[m, M_SL] = kc[2]
        out[m, M_CLOSEALL] = kc[3]
        out[m, M_REVERSE] = kc[4]
        out[m, M_END] = kc[5]
        out[m, M_EXPO] = max_expo if max_expo > -np.inf else np.nan
        out[m, M_BARS] = bars_sum / n
        # fair halves (last: they overwrite qty / realized of this mode)
        for h in range(2):
            out[m, M_H1N + h] = hn[h]
            if hn[h] > 0:
                net_h, pf_h = _sim_subset(hk[h], hj[h], hn[h], order, tpos, erow, xrow, epx, pnl,
                                          cap0, frac, qty, realized, tmp)
                out[m, M_H1R + h] = net_h
                out[m, M_H1PF + h] = pf_h


METRIC_COLS = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'half1_pct', 'half2_pct',
               'avg_trade_ret_pct', 'max_concurrent', 'exit_trail', 'exit_sl', 'exit_close_all',
               'exit_reverse', 'exit_end', 'max_expo', 'avg_bars_held',
               'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades', 'h1r_pf', 'h2r_pf')
INT_COLS = ('trades', 'max_concurrent', 'exit_trail', 'exit_sl', 'exit_close_all', 'exit_reverse', 'exit_end',
            'h1_trades', 'h2_trades')


def metrics_raw(pair, R, t_close, start, end):
    """Unrounded metrics, shape (3, NM): rows MODES, columns the M_* slots."""
    out = np.empty((len(MODES), NM))
    mid = start + (end - start) // 2
    _metrics_kernel(pair == 'BTC', R['n'], R['dir'], R['erow'], R['epx'], R['xrow'], R['xpx'], R['xkind'],
                    t_close, int(mid), float(run_tf.CAP), float(run_tf.FRAC), out)
    return out


def _round_row(v):
    """Rounding exactly as run_tf.metrics(): np.float64 rounding (numpy) for net / pf / dd /
    halves, Python float rounding for win_pct and avg_trade_ret_pct."""
    n = int(v[M_TRADES])
    d = {'trades': n}
    if n == 0:
        for k in METRIC_COLS[1:]:
            d[k] = 0 if k in INT_COLS else np.nan
        return d
    f64 = np.float64
    d['net_pct'] = float(round(f64(v[M_NET]), 2))
    d['pf'] = float(round(f64(v[M_PF]), 2)) if not np.isnan(v[M_PF]) else np.nan
    d['win_pct'] = round(float(v[M_WIN]), 1)
    d['max_dd_pct'] = float(round(f64(v[M_DD]), 2))
    d['half1_pct'] = float(round(f64(v[M_H1]), 2))
    d['half2_pct'] = float(round(f64(v[M_H2]), 2))
    d['avg_trade_ret_pct'] = round(float(v[M_AVG]), 4)
    d['max_concurrent'] = int(v[M_MAXC])
    d['exit_trail'] = int(v[M_TRAIL])
    d['exit_sl'] = int(v[M_SL])
    d['exit_close_all'] = int(v[M_CLOSEALL])
    d['exit_reverse'] = int(v[M_REVERSE])
    d['exit_end'] = int(v[M_END])
    d['max_expo'] = float(v[M_EXPO])
    d['avg_bars_held'] = float(v[M_BARS])
    # fair halves: run_tf.metrics() on the trades entered in each half -> its net_pct / pf
    for h, nm in ((0, 'h1'), (1, 'h2')):
        nt = int(v[M_H1N + h])
        d[nm + 'r_pct'] = float(round(f64(v[M_H1R + h]), 2)) if nt > 0 else np.nan
        d[nm + '_trades'] = nt
        pf = v[M_H1PF + h]
        d[nm + 'r_pf'] = float(round(f64(pf), 2)) if nt > 0 and not np.isnan(pf) else np.nan
    return d


def metrics_fast(pair, R, t_close, start, end):
    """run_tf.metrics(pair, trades, start, end, cost) for cost False ('tv0') and True ('cost'),
    and with the stressed cost function ('stress'), plus exit_* counts, max_expo, avg_bars_held
    and the fair halves. R = run_cfg output, t_close = P['t_close']."""
    out = metrics_raw(pair, R, t_close, start, end)
    return {md: _round_row(out[i]) for i, md in enumerate(MODES)}


def warmup(P=None):
    """Compile every kernel (before forking workers). numba compiles a separate version for
    read-only arrays: prep() and sub_bars() return writable arrays, as these."""
    n = 3
    z = np.zeros(n)
    b = np.zeros(n, np.bool_)
    i = np.zeros(n, np.int64)
    PP = dict(o=z + 1, h=z + 1, l=z + 1, c=z + 1, goL=b, goS=b, nL=i, nS=i, cL=b, cS=b, maxOpen=20, pyr=100,
              mt=0.01, tol=1e-8, cap=1, ocap=22, t_close=np.arange(n, dtype=np.int64))
    sub = (np.arange(n + 1, dtype=np.int64), z + 1, z + 1, z + 1, z + 1)
    for path in ('tv', 'mag'):
        R = run_cfg(PP, grid()[0], path, sub=sub)
        metrics_fast('BTC', R, PP['t_close'], 0, 10)
