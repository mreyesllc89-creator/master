"""mag_ref.py: an independent, plain pure-Python reference of the XPW v2.8 trailing-TP strategy
with TradingView's Bar Magnifier path ('mag'), used to verify sweep_core.run_cfg(..., 'mag').

Written from SWEEP_SPEC.md ('mag' paragraph), SPEC.md (broker rules 1-10) and the Pine
(xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine lines 1377-1520). It does NOT use
sweep_core's kernels, nor engine._walk / engine._run: only sweep_core.compute_inputs (sig, perm)
and sweep_core.prep (goLong / goShort / nL / nS / cL / cS, chart OHLC) for the inputs. The
1-minute sub-bars are rebuilt here from data/<PAIR>_1.parquet by mapping every minute to the
chart bar that contains it (a different method from sweep_core.sub_bars).

Model (per chart bar i, history, one script run per chart bar):
  1. exits: for each 1-minute sub-bar of bar i in time order, with its own rule-2 path
     (o,h,l,c if (h-o) < (o-l) else o,l,h,c), every open trade's exit order (trailing stop
     and / or stop loss) is evaluated: first the gap test at the sub-bar open (open at or
     beyond the stop -> fill at the open), then the open itself can arm / ratchet the trail,
     then the three segments (rising segments arm / ratchet, falling segments (long) can touch
     the stop: fill at the stop, or at the segment start if the stop is above it). Trailing
     state (armed, best) carries from sub-bar to sub-bar and bar to bar. A trade that exits is
     gone for the following sub-bars. Longs and shorts are written out separately (no
     negation trick).
  2. the script at the close of bar i with the position after step 1: close_all (closeL /
     closeS), then the entries in placement order, all filled at close[i]; an entry opposite
     to the position reverses it (all open trades close, kind 'reverse'); room / maxOpen and
     `room > 0 or position_size opposite` use the values seen by the script (before fills).
  3. trades open at the window end close at the last close (kind 'end').
Levels: activation = entry +/- trail_points * mintick, offset = trail_offset * mintick, SL =
entry -/+ loss * mintick, with trail_points = max(toTicks(trailAct, close), 0), trail_offset =
max(toTicks(trailOff, close), 1), loss = max(toTicks(slDist, close), 1) (Pine placeEntry), not
rounded (as the canonical engine). Touch / arm tests use a tolerance of 1e-6 tick (as the
canonical engine). trail_points 0: armed at the fill with best = the entry price. Trailing
stop and SL equal: the trailing stop is reported (engine convention).

Usage:
  python3 -I mag_ref.py compare [--n 44] [--workers 3]   random settings vs run_cfg 'mag'
  python3 -I mag_ref.py trace                            hand traces of 5 mag exits
"""
from __future__ import annotations

import math
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)

MT = 0.01
TOL = MT * 1e-6
TRAIL, SL, CLOSE_ALL, REVERSE, END = 1, 2, 3, 4, 5
KNAME = {TRAIL: 'trail', SL: 'sl', CLOSE_ALL: 'close_all', REVERSE: 'reverse', END: 'end'}

WINDOWS = [('BTC', '60', 1735689600, 1740787200),      # 2025-01-01 -> 2025-03-01
           ('BTC', '240', 1735689600, 1748736000),     # 2025-01-01 -> 2025-06-01
           ('XAU', '60', 1514851200, 1519862400),      # 2018-01-02 -> 2018-03-01
           ('XAU', '15', 1514851200, 1519862400)]
EXTRA_WINDOWS = [('BTC', '5', 1735689600, 1736899200),     # 2025-01-01 -> 2025-01-15
                 ('BTC', '15', 1735689600, 1738368000),    # 2025-01-01 -> 2025-02-01
                 ('BTC', '30', 1735689600, 1740787200),    # 2025-01-01 -> 2025-03-01
                 ('BTC', '120', 1735689600, 1748736000),   # 2025-01-01 -> 2025-06-01
                 ('XAU', '5', 1514851200, 1516233600),     # 2018-01-02 -> 2018-01-18
                 ('XAU', '30', 1514851200, 1519862400),    # 2018-01-02 -> 2018-03-01
                 ('XAU', '120', 1514851200, 1527811200),   # 2018-01-02 -> 2018-06-01
                 ('XAU', '240', 1514851200, 1527811200)]   # 2018-01-02 -> 2018-06-01
CACHE = os.path.join(W, 'cache_magref')


# ------------------------------------------------------------------ inputs
def _src_mtimes():
    return tuple(os.stat(os.path.join(W, f)).st_mtime_ns for f in ('xpw.py', 'fgf.py'))


def inputs(pair, tf, start, end):
    """(sig, perm) on the window via sweep_core.compute_inputs, pickled under the xpw / fgf mtimes."""
    import sweep_core as sc
    os.makedirs(CACHE, exist_ok=True)
    mt = _src_mtimes()
    path = os.path.join(CACHE, '%s_%s_%d_%d_%d_%d.pkl' % (pair, tf, start, end, mt[0], mt[1]))
    if os.path.exists(path):
        with open(path, 'rb') as fh:
            return pickle.load(fh)
    sig, perm = sc.compute_inputs(pair, tf, start, end)
    if _src_mtimes() == mt:
        with open(path + '.tmp%d' % os.getpid(), 'wb') as fh:
            pickle.dump((sig, perm), fh)
        os.replace(path + '.tmp%d' % os.getpid(), path)
    return sig, perm


def my_sub_bars(pair, tf, rows):
    """List (one per chart row) of lists of (open, high, low, close, t_open) 1-minute sub-bars:
    the minutes with chart t_open <= t_open < chart t_close. Each minute is assigned to the last
    chart bar whose t_open <= the minute's t_open, then kept only if before that bar's t_close.
    Checks the chart OHLC against its sub-bars."""
    ch = pd.read_parquet(os.path.join(W, 'data', '%s_%s.parquet' % (pair, tf)),
                         columns=['open', 'high', 'low', 'close', 't_open', 't_close']).reset_index(drop=True)
    ch = ch.iloc[np.asarray(rows)]
    bo = ch['t_open'].to_numpy(np.int64)
    bc = ch['t_close'].to_numpy(np.int64)
    m = pd.read_parquet(os.path.join(W, 'data', '%s_1.parquet' % pair),
                        columns=['open', 'high', 'low', 'close', 't_open'])
    mt_ = m['t_open'].to_numpy(np.int64)
    sel = (mt_ >= bo[0]) & (mt_ < bc[-1])
    m = m[sel]
    mt_ = mt_[sel]
    owner = np.searchsorted(bo, mt_, side='right') - 1          # last chart bar with t_open <= minute
    keep = (owner >= 0) & (mt_ < bc[np.clip(owner, 0, len(bc) - 1)])
    out = [[] for _ in range(len(bo))]
    mo, mh, ml, mc = (m[k].to_numpy(np.float64) for k in ('open', 'high', 'low', 'close'))
    for j in np.nonzero(keep)[0]:
        out[owner[j]].append((float(mo[j]), float(mh[j]), float(ml[j]), float(mc[j]), int(mt_[j])))
    co, chh, cl, cc = (ch[k].to_numpy(np.float64) for k in ('open', 'high', 'low', 'close'))
    bad = 0
    for r, sb in enumerate(out):
        if not sb:
            raise ValueError('%s %s: chart bar %d has no sub-bars' % (pair, tf, r))
        if not (sb[0][0] == co[r] and sb[-1][3] == cc[r] and max(x[1] for x in sb) == chh[r]
                and min(x[2] for x in sb) == cl[r]):
            bad += 1
        ts = [x[4] for x in sb]
        if ts != sorted(ts):
            raise ValueError('sub-bars not in time order')
    if bad:
        raise ValueError('%s %s: %d chart bars differ from their sub-bars' % (pair, tf, bad))
    return out


# ------------------------------------------------------------------ strategy
def to_ticks(d, ref, unit):
    # Pine: trailUnit == "ticks" ? d : trailUnit == "price" ? d / mintick : ref * d / 100.0 / mintick
    if unit == 'ticks':
        return d
    if unit == 'price':
        return d / MT
    return ref * d / 100.0 / MT


class Trade:
    __slots__ = ('dir', 'k', 'erow', 'epx', 'has_tr', 'A', 'off', 'has_sl', 'sl', 'armed', 'best',
                 'xrow', 'xpx', 'xkind', 'log', 'xsub')

    def __init__(self, d, k, i, px, cfg):
        self.dir = d
        self.k = k
        self.erow = i
        self.epx = px
        self.has_tr = bool(cfg['trailOn'])
        self.has_sl = bool(cfg['slOn'])
        self.A = self.off = self.sl = None
        self.armed = False
        self.best = None
        if self.has_tr:
            trp = max(to_ticks(cfg['trailAct'], px, cfg['trailUnit']), 0.0)
            tro = max(to_ticks(cfg['trailOff'], px, cfg['trailUnit']), 1.0)
            self.off = tro * MT
            if d > 0:
                self.A = px + trp * MT
                self.armed = px >= self.A - TOL
            else:
                self.A = px - trp * MT
                self.armed = px <= self.A + TOL
            self.best = px
        if self.has_sl:
            slp = max(to_ticks(cfg['slDist'], px, cfg['trailUnit']), 1.0)
            self.sl = px - slp * MT if d > 0 else px + slp * MT
        self.xrow = -1
        self.xpx = math.nan
        self.xkind = 0
        self.log = None                   # (chart row, sub-bar) where the trail armed
        self.xsub = -1                    # sub-bar of the exit (trail / sl exits)


def _stops(t):
    """(trail stop or None, sl or None) as they stand now."""
    ts = None
    if t.has_tr and t.armed:
        ts = t.best - t.off if t.dir > 0 else t.best + t.off
    return ts, (t.sl if t.has_sl else None)


def _level_kind(t):
    """The stop nearest to the price and its kind (None if no stop is working)."""
    ts, sl = _stops(t)
    if ts is None and sl is None:
        return None, 0
    if t.dir > 0:
        if sl is None or (ts is not None and ts >= sl):
            return ts, TRAIL
        return sl, SL
    if sl is None or (ts is not None and ts <= sl):
        return ts, TRAIL
    return sl, SL


def _favour(t, p):
    """Price p reached without the trade being stopped: arm / ratchet the trailing stop."""
    if not t.has_tr:
        return
    if t.dir > 0:
        if t.armed:
            if p > t.best:
                t.best = p
        elif p >= t.A - TOL:
            t.armed = True
            t.best = p
    else:
        if t.armed:
            if p < t.best:
                t.best = p
        elif p <= t.A + TOL:
            t.armed = True
            t.best = p


def sub_bar_exit(t, so, sh, sl_, sc_):
    """One 1-minute sub-bar of trade t's exit order. Returns (kind, fill) or None."""
    path = (so, sh, sl_, sc_) if (sh - so) < (so - sl_) else (so, sl_, sh, sc_)
    # gap: the sub-bar opens at or beyond the stop working since the previous price
    lvl, kind = _level_kind(t)
    if lvl is not None:
        if (t.dir > 0 and so <= lvl + TOL) or (t.dir < 0 and so >= lvl - TOL):
            return kind, so
    _favour(t, so)
    for a, b in zip(path[:-1], path[1:]):
        if b == a:
            continue
        toward = (b > a) if t.dir > 0 else (b < a)
        if toward:
            _favour(t, b)
        else:
            lvl, kind = _level_kind(t)
            if lvl is None:
                continue
            if t.dir > 0 and b <= lvl + TOL:
                return kind, (lvl if lvl < a else a)
            if t.dir < 0 and b >= lvl - TOL:
                return kind, (lvl if lvl > a else a)
    return None


def run_ref(P, sub, cfg, trace_rows=None):
    """The whole strategy, 'mag' path. P: sweep_core.prep() dict (inputs only); sub: my_sub_bars.
    Returns the list of Trade in creation (entry) order."""
    c = P['c']
    goL, goS, nL, nS, cL, cS = P['goL'], P['goS'], P['nL'], P['nS'], P['cL'], P['cS']
    maxOpen, pyr = P['maxOpen'], P['pyr']
    n = len(c)
    trades = []
    open_ = []                 # open trades (all the same direction)
    for i in range(n):
        # 1. exit orders along the sub-bars of chart bar i
        if open_:
            for m, (so, sh, sl_, sc_, _t) in enumerate(sub[i]):
                still = []
                for t in open_:
                    was = t.armed
                    r = sub_bar_exit(t, so, sh, sl_, sc_)
                    if t.armed and not was:
                        t.log = (i, m)                        # where the trail armed
                    if r is None:
                        still.append(t)
                    else:
                        t.xkind, t.xpx, t.xrow = r[0], r[1], i
                        t.xsub = m
                open_ = still
                if not open_:
                    break
        # 2. the script at the close of bar i
        pos = 0 if not open_ else open_[0].dir
        opentrades = len(open_)
        if (pos > 0 and cL[i]) or (pos < 0 and cS[i]):        # strategy.close_all
            for t in open_:
                t.xkind, t.xpx, t.xrow = CLOSE_ALL, float(c[i]), i
            open_ = []
        room = maxOpen - opentrades
        for d, go, cnt in ((1, goL[i], nL[i]), (-1, goS[i], nS[i])):
            if not go:
                continue
            for k in range(int(cnt)):
                if room > 0 or pos == -d:
                    cur = 0 if not open_ else open_[0].dir
                    if cur == -d:                             # reversal
                        for t in open_:
                            t.xkind, t.xpx, t.xrow = REVERSE, float(c[i]), i
                        open_ = []
                    if open_ and len(open_) >= pyr:
                        pass                                  # pyramiding: ignored
                    else:
                        t = Trade(d, k + 1, i, float(c[i]), cfg)
                        trades.append(t)
                        open_.append(t)
                    room -= 1
    # 3. window end
    for t in open_:
        t.xkind, t.xpx, t.xrow = END, float(c[n - 1]), n - 1
    return trades


def ref_arrays(trades):
    return dict(n=len(trades),
                dir=np.array([t.dir for t in trades], np.int64),
                erow=np.array([t.erow for t in trades], np.int64),
                epx=np.array([t.epx for t in trades], np.float64),
                xrow=np.array([t.xrow for t in trades], np.int64),
                xpx=np.array([t.xpx for t in trades], np.float64),
                xkind=np.array([t.xkind for t in trades], np.int64))


# ------------------------------------------------------------------ settings
def random_cfg(rng, ref_px):
    unit = str(rng.choice(['percent', 'percent', 'price', 'price', 'ticks']))

    def pct(allow0):
        u = rng.random()
        if allow0 and u < 0.25:
            return 0.0
        if u < 0.6:
            return float(rng.choice([0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]))
        return float(10.0 ** rng.uniform(-3.0, 0.6))

    def conv(p):
        if unit == 'percent':
            return p
        v = p / 100.0 * ref_px
        if unit == 'price':
            return round(v, 2) if rng.random() < 0.5 else v
        v = v / MT
        return float(round(v)) if rng.random() < 0.5 else v

    cfg = dict(tag='rand', trailUnit=unit, trailOn=bool(rng.random() < 0.8), slOn=bool(rng.random() < 0.5))
    cfg['trailAct'] = conv(pct(True))
    cfg['trailOff'] = conv(pct(False))
    cfg['slDist'] = conv(pct(False))
    if rng.random() < 0.06:                       # trail and SL at the same distance (tie)
        cfg['trailAct'] = 0.0
        cfg['slDist'] = cfg['trailOff']
        cfg['trailOn'] = cfg['slOn'] = True
    return cfg


def fixed_cfgs():
    """Hand-picked corners: activation 0, tiny offsets (1-tick clamp), SL only, no exits."""
    return [
        dict(tag='fix', trailOn=True, trailUnit='percent', trailAct=0.0, trailOff=0.01, slOn=False, slDist=1.0),
        dict(tag='fix', trailOn=True, trailUnit='percent', trailAct=0.0, trailOff=0.1, slOn=True, slDist=0.25),
        dict(tag='fix', trailOn=True, trailUnit='percent', trailAct=0.05, trailOff=0.02, slOn=True, slDist=0.1),
        dict(tag='fix', trailOn=False, trailUnit='percent', trailAct=0.0, trailOff=0.1, slOn=True, slDist=0.1),
        dict(tag='fix', trailOn=False, trailUnit='percent', trailAct=0.0, trailOff=0.1, slOn=False, slDist=0.1),
        dict(tag='fix', trailOn=True, trailUnit='price', trailAct=2.0, trailOff=1.0, slOn=False, slDist=3.0),
        dict(tag='fix', trailOn=True, trailUnit='ticks', trailAct=0.0, trailOff=0.3, slOn=True, slDist=0.2),
        dict(tag='fix', trailOn=True, trailUnit='percent', trailAct=0.0, trailOff=0.5, slOn=True, slDist=0.5),
    ]


# ------------------------------------------------------------------ compare
_G = {}


def _setup(w):
    import sweep_core as sc
    pair, tf, start, end = w
    sig, perm = inputs(pair, tf, start, end)
    Ps = {f: sc.prep(pair, tf, sig, perm if f else None, f) for f in (False, True)}
    rows = Ps[False]['rows']
    sub_sc = sc.sub_bars(pair, tf, rows)
    sub_me = my_sub_bars(pair, tf, rows)
    # my sub-bars vs sweep_core's (the table itself)
    ptr, so, sh, sl_, scl = sub_sc
    nsub = sum(len(x) for x in sub_me)
    same = nsub == int(ptr[-1])
    if same:
        flat = np.array([x[:4] for sb in sub_me for x in sb], np.float64)
        lens = np.array([len(x) for x in sub_me], np.int64)
        same = (np.array_equal(np.diff(ptr), lens) and np.array_equal(flat[:, 0], so) and np.array_equal(flat[:, 1], sh)
                and np.array_equal(flat[:, 2], sl_) and np.array_equal(flat[:, 3], scl))
    return dict(Ps=Ps, sub_sc=sub_sc, sub_me=sub_me, sub_same=bool(same), nsub=nsub)


def _cmp(R, A):
    """run_cfg result R vs reference arrays A: list of mismatch strings (first few)."""
    bad = []
    if R['n'] != A['n']:
        bad.append('count %d vs ref %d' % (R['n'], A['n']))
    m = min(R['n'], A['n'])
    for key in ('dir', 'erow', 'epx', 'xrow', 'xpx', 'xkind'):
        a = np.asarray(R[key][:m]).astype(np.float64)
        b = A[key][:m].astype(np.float64)
        neq = ~((a == b) | (np.isnan(a) & np.isnan(b)))
        if neq.any():
            j = int(np.argmax(neq))
            bad.append('%s differs on %d trades, first #%d: run_cfg %r ref %r' % (key, int(neq.sum()), j, a[j], b[j]))
    return bad


def _job(arg):
    import sweep_core as sc
    wi, ci, cfg, filt = arg
    G = _G[wi]
    P = G['Ps'][filt]
    t0 = time.time()
    R = sc.run_cfg(P, cfg, 'mag', sub=G['sub_sc'])
    t1 = time.time()
    A = ref_arrays(run_ref(P, G['sub_me'], cfg))
    t2 = time.time()
    Rtv = sc.run_cfg(P, cfg, 'tv')
    ntv_diff = 0
    if Rtv['n'] == A['n']:
        ntv_diff = int(((Rtv['xrow'] != A['xrow']) | (Rtv['xpx'] != A['xpx']) | (Rtv['xkind'] != A['xkind'])).sum())
    else:
        ntv_diff = -1
    kinds = np.bincount(A['xkind'], minlength=6)[1:].tolist() if A['n'] else [0] * 5
    return wi, ci, filt, cfg, _cmp(R, A), A['n'], kinds, ntv_diff, t1 - t0, t2 - t1


def compare(n_per=44, workers=3, seed=20261118, windows=None):
    import multiprocessing as mp
    global WINDOWS
    if windows is not None:
        WINDOWS = windows
    rng = np.random.default_rng(seed)
    jobs = []
    for wi, w in enumerate(WINDOWS):
        t0 = time.time()
        _G[wi] = _setup(w)
        P = _G[wi]['Ps'][False]
        print('%s %s %d..%d: %d chart bars, %d sub-bars, my sub-bar table == sweep_core.sub_bars: %s (%.1fs)'
              % (w[0], w[1], w[2], w[3], len(P['c']), _G[wi]['nsub'], _G[wi]['sub_same'], time.time() - t0), flush=True)
        ref_px = float(np.median(P['c']))
        cfgs = fixed_cfgs() + [random_cfg(rng, ref_px) for _ in range(n_per)]
        for ci, cfg in enumerate(cfgs):
            for filt in (False, True):
                jobs.append((wi, ci, cfg, filt))
    print('%d runs' % len(jobs), flush=True)
    t0 = time.time()
    ctx = mp.get_context('fork')
    nbad = 0
    tot_tr = 0
    tot_kinds = np.zeros(5, np.int64)
    tv_diff_runs = 0
    rows = []
    with ctx.Pool(workers) as pool:
        for res in pool.imap_unordered(_job, jobs, chunksize=2):
            wi, ci, filt, cfg, bad, ntr, kinds, ntvd, tk, tr_ = res
            tot_tr += ntr
            tot_kinds += np.array(kinds)
            tv_diff_runs += ntvd != 0
            rows.append(res)
            if bad:
                nbad += 1
                w = WINDOWS[wi]
                print('MISMATCH %s %s filter=%s cfg=%r: %s' % (w[0], w[1], filt, cfg, '; '.join(bad[:4])), flush=True)
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    for wi, w in enumerate(WINDOWS):
        rr = [r for r in rows if r[0] == wi]
        print('%s %s: %d runs, %d mismatches, trades %d, kinds trail/sl/close_all/reverse/end %s, '
              'runs where mag != tv: %d, kernel %.3fs/run, ref %.1fs/run'
              % (w[0], w[1], len(rr), sum(1 for r in rr if r[4]), sum(r[5] for r in rr),
                 np.sum([r[6] for r in rr], axis=0).tolist(), sum(1 for r in rr if r[7] != 0),
                 np.mean([r[8] for r in rr]), np.mean([r[9] for r in rr])), flush=True)
    print('TOTAL %d runs, %d with a mismatch, %d trades compared (kinds %s), %d runs where mag differs from tv; %.0fs'
          % (len(rows), nbad, tot_tr, tot_kinds.tolist(), tv_diff_runs, time.time() - t0), flush=True)
    return nbad


# ------------------------------------------------------------------ hand traces
def _hm(ts):
    return pd.Timestamp(int(ts), unit='s').strftime('%m-%d %H:%M')


def show(G, P, cfg, j, R, label):
    """Print trade j of run_cfg result R (the kernel under test) with the raw sub-bars of every
    chart bar from the entry + 1 to the exit (raw data only: no reference state)."""
    sub = G['sub_me']
    d = int(R['dir'][j]); er = int(R['erow'][j]); xr = int(R['xrow'][j])
    epx = float(R['epx'][j]); xpx = float(R['xpx'][j]); xk = int(R['xkind'][j])
    u = cfg['trailUnit']
    print('=' * 100)
    print(label)
    print('cfg', {k: cfg[k] for k in ('trailOn', 'trailUnit', 'trailAct', 'trailOff', 'slOn', 'slDist')})
    trp = max(to_ticks(cfg['trailAct'], epx, u), 0.0) if cfg['trailOn'] else None
    tro = max(to_ticks(cfg['trailOff'], epx, u), 1.0) if cfg['trailOn'] else None
    slp = max(to_ticks(cfg['slDist'], epx, u), 1.0) if cfg['slOn'] else None
    print('trade #%d %s entry row %d (bar closing %s) @ %.6f' % (j, 'LONG' if d > 0 else 'SHORT', er,
          _hm(P['t_close'][er]), epx))
    if trp is not None:
        print('  trail_points %.6f ticks -> activation %.6f ; trail_offset %.6f ticks = %.6f price'
              % (trp, epx + d * trp * MT, tro, tro * MT))
    if slp is not None:
        print('  loss %.6f ticks -> SL %.6f' % (slp, epx - d * slp * MT))
    print('  KERNEL (run_cfg mag): exit row %d @ %.6f kind %s' % (xr, xpx, KNAME[xk]))
    Rtv = G['tv'] if 'tv' in G else None
    for r in range(er + 1, xr + 1):
        print('  chart bar row %d  %s..%s  O %.3f H %.3f L %.3f C %.3f  (%d sub-bars)'
              % (r, _hm(P['t_open'][r]), _hm(P['t_close'][r]), P['o'][r], P['h'][r], P['l'][r], P['c'][r], len(sub[r])))
        prev_c = None
        for m, (so, sh, sl_, sc_, ts) in enumerate(sub[r]):
            order = 'O-H-L-C' if (sh - so) < (so - sl_) else 'O-L-H-C'
            gap = '' if prev_c is None or prev_c == so else ' gap from %.3f' % prev_c
            print('    %3d %s  O %.3f H %.3f L %.3f C %.3f  %s%s' % (m, _hm(ts), so, sh, sl_, sc_, order, gap))
            prev_c = sc_


def trace():
    import sweep_core as sc
    picks = []
    # (window index, cfg, filter, selector, label)
    W60, W240, X60, X15 = 0, 1, 2, 3
    cA = dict(trailOn=True, trailUnit='percent', trailAct=0.1, trailOff=0.05, slOn=True, slDist=0.5)
    cB = dict(trailOn=True, trailUnit='percent', trailAct=0.0, trailOff=0.1, slOn=True, slDist=0.2)
    cC = dict(trailOn=False, trailUnit='percent', trailAct=0.0, trailOff=0.1, slOn=True, slDist=0.05)
    cD = dict(trailOn=True, trailUnit='price', trailAct=2.0, trailOff=1.0, slOn=False, slDist=3.0)
    cE = dict(trailOn=True, trailUnit='ticks', trailAct=30.0, trailOff=20.0, slOn=True, slDist=40.0)
    cache = {}

    def get(wi):
        if wi not in cache:
            cache[wi] = _setup(WINDOWS[wi])
        return cache[wi]

    def run(wi, cfg, filt):
        G = get(wi)
        P = G['Ps'][filt]
        R = sc.run_cfg(P, cfg, 'mag', sub=G['sub_sc'])
        Rtv = sc.run_cfg(P, cfg, 'tv')
        T = run_ref(P, G['sub_me'], cfg)
        return G, P, R, Rtv, T

    def pick(wi, cfg, filt, ok, label):
        G, P, R, Rtv, T = run(wi, cfg, filt)
        for j, t in enumerate(T):
            if ok(t, j, R, Rtv, G):
                show(G, P, cfg, j, R, '%s  [%s %s filter=%s]' % (label, WINDOWS[wi][0], WINDOWS[wi][1], filt))
                print('  tv path (one O-H-L-C path per chart bar) gives: exit row %d @ %.6f %s'
                      % (Rtv['xrow'][j], Rtv['xpx'][j], KNAME[int(Rtv['xkind'][j])]) if Rtv['n'] == R['n'] else '')
                return
        print('no candidate for', label)

    # 1. long trail, activation > 0, armed in an earlier sub-bar of the exit bar, exit at the stop
    pick(W60, cA, False, lambda t, j, R, Rtv, G: t.dir > 0 and t.xkind == TRAIL and t.xrow == t.erow + 1
         and t.log is not None and t.log[0] == t.xrow and 0 < t.log[1] < t.xsub < 20 and Rtv['xrow'][j] != t.xrow,
         'TRACE 1: long trailing exit, armed and stopped inside one chart bar (tv differs)')
    # 2. short trail with activation 0 (armed at the fill), exit at the stop
    pick(X15, cB, False, lambda t, j, R, Rtv, G: t.dir < 0 and t.xkind == TRAIL and t.xrow == t.erow + 1
         and 0 < t.xsub < 15 and t.xpx != G['sub_me'][t.xrow][t.xsub][0],
         'TRACE 2: short trailing exit, activation 0')
    # 3. SL filled at a sub-bar open that gapped through it (not the first sub-bar of the chart bar)
    pick(X60, cC, False, lambda t, j, R, Rtv, G: t.xkind == SL and t.xrow == t.erow + 1 and 0 < t.xsub < 30
         and t.xpx == G['sub_me'][t.xrow][t.xsub][0] and G['sub_me'][t.xrow][t.xsub - 1][3] != t.xpx,
         'TRACE 3: stop loss gapped at a sub-bar open')
    # 4. armed and stopped in the same sub-bar (rise then fall inside one minute)
    pick(W60, cD, True, lambda t, j, R, Rtv, G: t.xkind == TRAIL and t.xrow == t.erow + 1 and t.log is not None
         and t.log == (t.xrow, t.xsub) and t.xsub < 25,
         'TRACE 4: default trail (price 2 / 1): armed and stopped in the same sub-bar')
    # 5. short SL in ticks while a trail is set but not armed
    pick(X15, cE, True, lambda t, j, R, Rtv, G: t.dir < 0 and t.xkind == SL and t.xrow == t.erow + 1 and t.xsub > 0
         and not t.armed,
         'TRACE 5: short stop loss (trail set, never armed)')


if __name__ == '__main__':
    if sys.argv[1:2] == ['trace']:
        trace()
        sys.exit(0)
    args = sys.argv[1:]
    if not args or args[0] == 'compare':
        n = 44
        wk = 3
        if '--n' in args:
            n = int(args[args.index('--n') + 1])
        if '--workers' in args:
            wk = min(3, int(args[args.index('--workers') + 1]))
        seed = int(args[args.index('--seed') + 1]) if '--seed' in args else 20261118
        wins = EXTRA_WINDOWS if '--extra' in args else None
        sys.exit(1 if compare(n, wk, seed, wins) else 0)
