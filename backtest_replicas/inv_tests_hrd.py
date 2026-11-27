"""inv_tests_hrd.py: regression and property tests of the Update 1 option "Inverted direction:
opposite side at the same entries" in the HRD replica (hrd.py, param hrdInv, alias inv).
INV_BT_SPEC.md, task 2, strategy "hrd".

Ground truth: /home/user/master/HRD_Full_Divergence_Strategy_v1_03_FGF.pine at HEAD (d28ba97);
the Update 1 change is `git -C /home/user/master diff 6c59b9f d28ba97 -- <that file>`.

Usage: python3 -I inv_tests_hrd.py [FILTER ...]
  Runs every function test_<name> whose name contains one of the FILTER substrings (none = all),
  prints PASS / FAIL per test and exits non-zero on any failure.

  R1  option off = the previous replica
      R1a  every variant of out/hrd_<PAIR>_<TF>.json (14 cells) and every saved trade list
      R1b  a sample of out/swah_hrd_<PAIR>_<TF>.parquet rows (tv and mag)
      R1c  bit-for-bit equal to the pre-change module pre_inv_backup/hrd.py
  R2  the Pine header's statements on Inverted vs "Reverse Trading"
      R2a  filter off: Inverted alone = Reverse alone, both on = both off, trade by trade; every
           difference comes from a candle with a LONG and a SHORT signal while flat
      R2b  filter on: Inverted = the normal kernel on swapped signals AND swapped permissions
           (the flip after the gate, checked against the verified normal kernel)
      R2c  the header's statements read directly on the inverted trade lists
  R3  mirror property on single decisions (micro-runs around sampled bars)
  R4  'mag' on chart "1" = 'tv' with the option on
  R5  the kernel with the option on = a pure-Python port of the Pine at HEAD, trade by trade
  R6  speed of the kernel before / after the change
  R7  the option through the public entry points (run / simulate, hrdInv / inv) and the REAL side
      in the public trade list and summary (added by the sceptic review)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import hrd  # noqa: E402

OUT = os.path.join(W, 'out')
TFS = ('1', '5', '15', '30', '60', '120', '240')
CELLS = tuple((p, tf) for p in ('BTC', 'XAU') for tf in TFS)
INIT = 1_000_000.0
PRE = os.path.join(W, 'pre_inv_backup', 'hrd.py')
PRE_SHA256 = 'a3f001eac47a1a2dd8a9c12bb8e308a9939fbb76c3d2f8332c78eb83d7bfc9b3'   # hrd.py before the change
K = {nm: i for i, nm in enumerate(hrd.KINDS)}
ACTS = (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
OFFS = (0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
# 2-month windows (the ones sweep_ah_tests.py uses) for the slow pure-Python comparisons
SHORT_WINDOWS = (('BTC', '60', 1735689600, 1740787200),      # 2025-01-01 -> 2025-03-01
                 ('XAU', '60', 1514851200, 1519862400),      # 2018-01-02 -> 2018-03-01
                 ('BTC', '5', 1735689600, 1740787200))       # 2025-01-01 -> 2025-03-01
SWAP = {'want_l': 'want_s', 'want_s': 'want_l', 'blk_l': 'blk_s', 'blk_s': 'blk_l'}


def _p(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def _aeq(a, b):
    """Exact array equality (shape, dtype, values; NaN == NaN)."""
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape or a.dtype != b.dtype:
        return False
    return bool(np.array_equal(a, b, equal_nan=(a.dtype.kind == 'f')))


def _diff_R(Ra, Rb, swap_frame=False):
    """Names of the kernel outputs that differ between two hrd.simulate results (exact). With
    swap_frame the normal frame of Rb is the mirror of Ra's (its LONG signals are Ra's SHORT
    signals): want_l / want_s / blk_l / blk_s and the raw / blocked counts are compared crosswise."""
    bad = []
    for k in hrd._R_KEYS:
        if k == 'stats':
            sb = Rb['stats'].copy()
            if swap_frame:
                sb[[5, 6, 7, 8]] = sb[[6, 5, 8, 7]]
            if not _aeq(Ra['stats'], sb):
                bad.append(k)
        else:
            kb = SWAP.get(k, k) if swap_frame else k
            if not _aeq(Ra[k], Rb[kb]):
                bad.append(k)
    return bad


def _same_val(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def _close(a, b, rtol=1e-9, atol=0.0):
    if a is None or b is None:
        return a is None and b is None
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    if math.isinf(a) or math.isinf(b):
        return a == b
    return abs(a - b) <= atol + rtol * max(abs(a), abs(b))


def _rand_X(rng, path='tv', trail_share=0.5, direction=True):
    """A random broker / exit setting (every simulate()-level input of the strategy)."""
    X = dict(path=path)
    X['trailOn'] = bool(rng.random() < trail_share)
    X['trailAct'] = float(rng.choice(ACTS)) if rng.random() < 0.7 else float(np.round(rng.uniform(0, 3), 3))
    X['trailOff'] = float(rng.choice(OFFS)) if rng.random() < 0.7 else float(np.round(rng.uniform(0.005, 3), 3))
    X['InpTpPct'] = float(rng.choice([4.0, 4.0, 0.0, float(np.round(rng.uniform(0.2, 6), 2))]))
    X['InpExitCandles'] = int(rng.choice([5, 5, 20, 100, int(rng.integers(1, 60))]))
    X['InpSlPct'] = float(rng.choice([2.0, 2.0, 2.0, 0.0, float(np.round(rng.uniform(0.3, 5), 2))]))
    X['cost'] = str(rng.choice(['tv', 'ours', 'stress']))
    X['blkClose'] = bool(rng.random() < 0.75)
    X['useHybridExit'] = bool(rng.random() < 0.8)
    if direction:
        X['InpTradeDirection'] = str(rng.choice(['Both', 'Both', 'Both', 'Buy Only', 'Sell Only']))
    return X


_PRE = {}


def _load_pre():
    """The replica as it was before the change (pre_inv_backup/hrd.py), as module hrd_pre_inv,
    reading the same data directory."""
    if 'm' not in _PRE:
        sha = hashlib.sha256(open(PRE, 'rb').read()).hexdigest()
        if sha != PRE_SHA256:
            raise RuntimeError('pre_inv_backup/hrd.py is not the pre-change file (sha256 %s)' % sha)
        if 'hrdInv' in open(PRE).read():
            raise RuntimeError('pre_inv_backup/hrd.py already has the option')
        spec = importlib.util.spec_from_file_location('hrd_pre_inv', PRE)
        mod = importlib.util.module_from_spec(spec)
        sys.modules['hrd_pre_inv'] = mod
        spec.loader.exec_module(mod)
        mod.W = W
        mod.DATA = hrd.DATA
        _PRE['m'] = mod
    return _PRE['m']


def _fake_sub(Pp):
    """A sub-bar table with every chart bar as its own single sub-bar."""
    return (np.arange(Pp['n'] + 1, dtype=np.int64), Pp['o'].copy(), Pp['h'].copy(), Pp['l'].copy(), Pp['c'].copy())


# ---------------------------------------------------------------------------------------------
# R1: option off = the previous replica
# ---------------------------------------------------------------------------------------------
def test_R1a_saved_json():
    """R1a: with the option off (absent, hrdInv=False, inv=False) hrd.run reproduces every saved
    result exactly: all 14 cells x every variant of out/hrd_<PAIR>_<TF>.json (every saved summary
    field, including run_hrd.extras) and every saved trade list of out/hrd_trades/ (every column)."""
    import run_hrd
    ok_all = True
    n_runs = n_fields = n_lists = n_rows = 0
    for pair, tf in CELLS:
        saved = json.load(open(os.path.join(OUT, 'hrd_%s_%s.json' % (pair, tf))))
        bad = []
        for name, sv in saved['runs'].items():
            q = dict(sv['params'])
            tr, s = hrd.run(pair, tf, q)
            s2 = dict(s)
            s2.update(run_hrd.extras(tr, s))
            s2['params'] = q
            cl = run_hrd.clean(s2)
            for k, v in sv.items():
                n_fields += 1
                if k == 'exits':
                    same = all(cl['exits'].get(e) == x for e, x in v.items()) and cl['exits'].get('trail') == 0
                else:
                    same = (k in cl and cl[k] == v)
                if not same:
                    bad.append('%s.%s saved %r now %r' % (name, k, v, cl.get(k)))
            for extra in ({'hrdInv': False}, {'inv': False}):          # the option named, off
                q2 = dict(q)
                q2.update(extra)
                tr2, sx = hrd.run(pair, tf, q2)
                if not (tr2.equals(tr) and all(_same_val(sx[k], s[k]) for k in s)):
                    bad.append('%s with %r differs from the default' % (name, extra))
            n_runs += 1
            fn = os.path.join(OUT, 'hrd_trades', 'hrd_%s_%s_%s.parquet' % (pair, tf, name))
            if os.path.exists(fn):
                old = pd.read_parquet(fn)
                n_lists += 1
                n_rows += len(old)
                if len(old) != len(tr):
                    bad.append('%s trades %d vs saved %d' % (name, len(tr), len(old)))
                else:
                    for col in old.columns:
                        if not old[col].reset_index(drop=True).equals(tr[col].reset_index(drop=True)):
                            bad.append('%s trades column %s differs' % (name, col))
        _p('  %s %-3s: %2d runs, %s' % (pair, tf, len(saved['runs']), 'all equal' if not bad else
                                         '%d DIFFERENCES: %s' % (len(bad), '; '.join(bad[:6]))))
        ok_all &= not bad
        hrd._SIG.clear()
        hrd._PERM.clear()
    _p('  %d runs, %d saved fields, %d saved trade lists (%d rows) compared' % (n_runs, n_fields, n_lists, n_rows))
    return ok_all and n_runs == 168


def test_R1b_sweep_rows():
    """R1b: with the option off the kernel reproduces a sample of the saved sweep rows exactly:
    for each of the 14 files out/swah_hrd_<PAIR>_<TF>.parquet and each of its 16 groups (filter
    off / on x path tv / mag x labels normal / rev x cost tv / ours): the default row (setting 0)
    and 5 random settings, every summary column (hrd.summary_fast), half of them with
    hrdInv=False named, half without the param."""
    import sweep_hrd
    rng = np.random.default_rng(20261124)
    G = sweep_hrd.grid()
    ok_all = True
    n_rows = n_vals = 0
    by_path = {'tv': 0, 'mag': 0}
    for pair, tf in CELLS:
        t0 = time.time()
        df = pd.read_parquet(os.path.join(OUT, 'swah_hrd_%s_%s.parquet' % (pair, tf)))
        df = df.set_index(['filter', 'path', 'labels', 'cost', 'setting']).sort_index()
        P = {}
        bad = []
        for flt in ('off', 'on'):
            for lab in ('normal', 'rev'):
                P[(flt, lab)] = hrd.prepare(pair, tf, {'fgfOn': flt == 'on', 'reverse': lab == 'rev'})
        sub = None
        cnt = 0
        for flt in ('off', 'on'):
            for path in ('tv', 'mag'):
                for lab in ('normal', 'rev'):
                    for cost in ('tv', 'ours'):
                        Pp = P[(flt, lab)]
                        if path == 'mag':
                            if sub is None:
                                sub = hrd.get_sub(Pp)
                            Pp['sub'] = sub
                        picks = [0] + sorted(int(x) for x in rng.choice(np.arange(1, len(G)), 5, replace=False))
                        for j, i in enumerate(picks):
                            row = df.loc[(flt, path, lab, cost, i)]
                            cfg = G[i]
                            if not (bool(row['trailOn']) == cfg['trailOn'] and float(row['InpTpPct']) == cfg['InpTpPct']
                                    and int(row['InpExitCandles']) == cfg['InpExitCandles']
                                    and (not cfg['trailOn'] or (float(row['trailAct']) == cfg['trailAct']
                                                                and float(row['trailOff']) == cfg['trailOff']))):
                                bad.append('setting %d: the file row is not grid()[%d]' % (i, i))
                                continue
                            X = sweep_hrd.exit_params(cfg, path, cost)
                            if j % 2:
                                X['hrdInv'] = False
                            s = hrd.summary_fast(Pp, hrd.simulate(Pp, X))
                            for col in sweep_hrd.SUM_COLS:
                                n_vals += 1
                                a, b = s[col], row[col]
                                if col in sweep_hrd.FLOAT_COLS:
                                    same = _same_val(float(a), float(b))
                                else:
                                    same = int(a) == int(b)
                                if not same:
                                    bad.append('%s/%s/%s/%s setting %d %s: file %r now %r' % (flt, path, lab, cost, i, col, b, a))
                            cnt += 1
                            by_path[path] += 1
        n_rows += cnt
        _p('  %s %-3s: %3d rows, %s (%.1fs)' % (pair, tf, cnt, 'all equal' if not bad else
                                                '%d DIFFERENCES: %s' % (len(bad), '; '.join(bad[:4])), time.time() - t0))
        ok_all &= not bad
        hrd._SIG.clear()
        hrd._PERM.clear()
    _p('  %d rows (tv %d, mag %d), %d values compared' % (n_rows, by_path['tv'], by_path['mag'], n_vals))
    return ok_all and n_rows == 14 * 16 * 6


def test_R1c_vs_prechange_module():
    """R1c: with the option off the changed module equals the module as it was before the change
    (pre_inv_backup/hrd.py, sha256 checked), bit for bit: run() (every trade column, every summary
    field) and every kernel output of simulate(full=True) (trade arrays, per-bar equity / position
    / entryBarIndex / hybrid state / want / blocked flags, stats), on 80 random settings (filter,
    Reverse Trading, pivot ties, Trade Direction, SL / TP / candles, hybrid, blkClose, trail, cost
    tv / ours / stress, path tv / mag) over the 2-month windows and the full BTC 60 / 240 and
    XAU 60 / 240 windows."""
    pre = _load_pre()
    rng = np.random.default_rng(1124)
    wins = list(SHORT_WINDOWS) + [('BTC', '60', None, None), ('XAU', '240', None, None),
                                  ('BTC', '240', None, None), ('XAU', '60', None, None)]
    ok_all = True
    n_tr = 0
    n_mag = 0
    kinds = {}
    for i in range(80):
        pair, tf, start, end = wins[i % len(wins)]
        q = _rand_X(rng, 'mag' if rng.random() < 0.35 else 'tv', 0.5)
        q['fgfOn'] = bool(rng.random() < 0.5)
        q['reverse'] = bool(rng.random() < 0.3)
        if rng.random() < 0.15:
            q['pivotTies'] = 'left_strict'
        if start is not None:
            q.update(start=start, end=end)
        n_mag += q['path'] == 'mag'
        ta, sa = pre.run(pair, tf, q)
        tb, sb = hrd.run(pair, tf, q)
        q2 = dict(q)
        q2['hrdInv'] = False
        tc, sc = hrd.run(pair, tf, q2)
        same = ta.equals(tb) and ta.equals(tc) and list(ta.columns) == list(tb.columns)
        same &= set(sa) == set(sb) and all(_same_val(sa[k], sb[k]) and _same_val(sa[k], sc[k]) for k in sa)
        Ra = pre.simulate(pre.prepare(pair, tf, q), None, full=True)
        Rb = hrd.simulate(hrd.prepare(pair, tf, q), {'inv': False}, full=True)
        bad = _diff_R(Ra, Rb)
        n_tr += len(ta)
        for kd, c in ta['exit_kind'].value_counts().items():
            kinds[kd] = kinds.get(kd, 0) + int(c)
        if not same or bad:
            ok_all = False
            _p('  DIFF %s %s %r: run equal %s, kernel outputs differing %s' % (pair, tf, q, same, bad))
    _p('  80 settings (%d mag), %d trades: %s; exit kinds %s'
       % (n_mag, n_tr, 'all equal' if ok_all else 'DIFFERENCES', ', '.join('%s %d' % kv for kv in sorted(kinds.items()))))
    return ok_all


# ---------------------------------------------------------------------------------------------
# R2: Inverted vs Reverse Trading (the Pine header, INVERTED DIRECTION)
# ---------------------------------------------------------------------------------------------
def _nz(x):
    return None if x != x else float(x)


def _pkey(R, i):
    """A trade in price space: everything but its size (quantity, P/L, equity)."""
    return (int(R['dir'][i]), int(R['sk'][i]), int(R['ek'][i]), int(R['xk'][i]), int(R['xsk'][i]),
            int(R['kind'][i]), float(R['epx'][i]), float(R['xpx'][i]), _nz(R['sl'][i]), _nz(R['tp'][i]))


def _same_orders(n, RA, RB, invA, invB, fixed_qty=False, rtol=1e-9):
    """RA / RB: two simulate(full=True) results over the same n bars whose runs must place the
    same real orders, RB's normal frame being the mirror of RA's (swapped signals), except on a
    candle where a run sends BOTH entries (a LONG and a SHORT signal while flat, both allowed):
    there the two entries are sent in the opposite order and the second one stays.
      - no such candle: every kernel output must be equal bit for bit (frames crosswise);
      - else the runs are cut in episodes [d, e): d = such a candle (both runs flat, both send both
        entries), e = the first later candle at whose close both runs are flat again. Then
        (1) the trades whose entry order was placed outside every episode are the same in both
            runs, one to one: side, signal / entry / exit bars, exit order bar, exit kind, entry
            and exit price, SL, TP exactly; quantity and P/L per unit of equity within rtol (the
            two accounts differ after an episode, sizing is a share of equity), or, with
            fixed_qty (Stop Loss % = 0: every order is the fixed quantity), quantity and P/L
            exactly;
        (2) outside the episodes the per-bar state agrees: position side, want / blocked flags
            (crosswise), hybrid peak / counter, entryBarIndex while in a trade;
        (3) every episode starts as the header says: both entries fill at the next open, the
            first is closed at once by the second (zero bars, kind reverse), and the one that
            stays is a BUY in an inverted run, a SELL in a run without Inverted.
    Returns (ok, info, messages)."""
    goA = (RA['want_l'] & ~RA['blk_l']) & (RA['want_s'] & ~RA['blk_s'])
    goB = (RB['want_l'] & ~RB['blk_l']) & (RB['want_s'] & ~RB['blk_s'])
    dbl = np.flatnonzero(goA | goB)
    info = dict(double=int(len(dbl)), episodes=0, in_A=0, in_B=0, matched=0, exact=False)
    if len(dbl) == 0:
        bad = _diff_R(RA, RB, swap_frame=True)
        info['exact'] = not bad
        info['matched'] = int(len(RA['dir']))
        return (not bad), info, (['kernel outputs differ: %s' % bad] if bad else [])
    msgs = []
    posA, posB = RA['pos'], RB['pos']
    flat = (posA == 0) & (posB == 0)
    flat_idx = np.flatnonzero(flat)
    episodes = []
    end_prev = -1
    for d in dbl.tolist():
        if d < end_prev:
            continue                          # inside an episode: the runs already differ
        if not (goA[d] and goB[d] and flat[d]):
            msgs.append('bar %d: both entries sent outside an episode by one run only, or not flat' % d)
            continue
        j = int(np.searchsorted(flat_idx, d, side='right'))
        e = int(flat_idx[j]) if j < len(flat_idx) else n
        episodes.append((d, e))
        end_prev = e
    info['episodes'] = len(episodes)
    ins = np.zeros(n, np.bool_)               # bars where the positions may differ
    tin = np.zeros(n + 1, np.bool_)           # signal bars whose entries belong to an episode
    for d, e in episodes:
        ins[d + 1:e] = True
        tin[d:e] = True
    out = ~ins
    # (1) trades outside the episodes
    iA = np.flatnonzero(~tin[RA['sk']])
    iB = np.flatnonzero(~tin[RB['sk']])
    info['in_A'] = int(len(RA['dir']) - len(iA))
    info['in_B'] = int(len(RB['dir']) - len(iB))
    if len(iA) != len(iB):
        msgs.append('trades outside the episodes: %d vs %d' % (len(iA), len(iB)))
    else:
        info['matched'] = int(len(iA))
        pa = RA['gross'] - RA['cost']
        pb = RB['gross'] - RB['cost']
        for a, b in zip(iA.tolist(), iB.tolist()):
            if _pkey(RA, a) != _pkey(RB, b):
                msgs.append('trade outside the episodes differs: %r vs %r' % (_pkey(RA, a), _pkey(RB, b)))
                break
            ea, eb = float(RA['eqb'][a]), float(RB['eqb'][b])
            if fixed_qty:
                same_size = float(RA['qty'][a]) == float(RB['qty'][b]) and float(pa[a]) == float(pb[b])
            else:
                same_size = (_close(float(RA['qty'][a]) / ea, float(RB['qty'][b]) / eb, rtol)
                             and _close(float(pa[a]) / ea, float(pb[b]) / eb, rtol, 1e-12))
            if not same_size:
                msgs.append('trade outside the episodes: size %s differs at signal bar %d'
                            % ('(fixed quantity)' if fixed_qty else 'per equity', int(RA['sk'][a])))
                break
    # (2) per-bar state outside the episodes
    if not np.array_equal(np.sign(posA[out]), np.sign(posB[out])):
        msgs.append('position side differs outside the episodes')
    for ka in ('want_l', 'want_s', 'blk_l', 'blk_s'):
        if not np.array_equal(RA[ka][out], RB[SWAP[ka]][out]):
            msgs.append('%s differs outside the episodes' % ka)
    for ka in ('peak', 'cnt'):
        if not np.array_equal(RA[ka][out], RB[ka][out]):
            msgs.append('hybrid %s differs outside the episodes' % ka)
    inpos = out & (posA != 0)
    if not np.array_equal(RA['ebi'][inpos], RB['ebi'][inpos]):
        msgs.append('entryBarIndex differs outside the episodes')
    # (3) how each episode starts
    for d, e in episodes:
        if d + 1 >= n:
            continue                          # orders of the last bar do not fill
        for R, inv, nm in ((RA, invA, 'A'), (RB, invB, 'B')):
            ix = np.flatnonzero(R['sk'] == d)
            stay = 1 if inv else -1
            good = (len(ix) == 2 and int(R['dir'][ix[0]]) == -stay and int(R['dir'][ix[1]]) == stay
                    and int(R['kind'][ix[0]]) == K['reverse'] and int(R['ek'][ix[0]]) == d + 1
                    and int(R['xk'][ix[0]]) == d + 1 and int(R['xsk'][ix[0]]) == d and int(R['ek'][ix[1]]) == d + 1
                    and float(R['epx'][ix[0]]) == float(R['xpx'][ix[0]]) == float(R['epx'][ix[1]]))
            if not good:
                msgs.append('episode at bar %d, run %s: not [first entry closed at once, %s stays]'
                            % (d, nm, 'BUY' if stay > 0 else 'SELL'))
    return (not msgs), info, msgs


def _no_double(Pp):
    """prepare()'s arrays with the signals of every candle that has a LONG and a SHORT signal
    removed (a counterfactual input: no candle can send both entries)."""
    Q = dict(Pp)
    m = Pp['long_sig'] & Pp['short_sig']
    Q['long_sig'] = np.ascontiguousarray(Pp['long_sig'] & ~m)
    Q['short_sig'] = np.ascontiguousarray(Pp['short_sig'] & ~m)
    return Q


def test_R2a_filter_off_inv_vs_reverse():
    """R2a (Pine header, INVERTED DIRECTION: 'With the filter off, Reverse alone and Inverted alone
    place the same orders ... and both on = both off, with one exception: a candle that has a LONG
    and a SHORT signal while flat ("Trade Direction" = Both). Both entries are sent and the second
    one stays: a SELL without Inverted (Reverse on or off), a BUY with it'). Filter off, all 14
    cells, full windows, 10 settings each (the defaults with path tv / mag x cost tv / ours, and 6
    random settings: SL / TP / candles / hybrid / trail / cost / Trade Direction), two pairs of runs:
    (a) hrdInv alone vs the verified reversed-labels run (reverse alone), (b) reverse + hrdInv vs
    neither. A pair with no candle that sends both entries must be equal bit for bit on every
    kernel output. Else every difference must lie in an episode opened by such a candle (see
    _same_orders: the trades placed outside the episodes are the same, the episode starts as the
    header says). Counterfactual: with the signals of the double-signal candles removed from the
    inputs, both pairs are equal bit for bit in every cell and setting."""
    rng = np.random.default_rng(2)
    ok_all = True
    tot = dict(pairs=0, exact=0, with_ep=0, episodes=0, matched=0, in_ep=0, cf=0, cf_bad=0, trades=0, fixed=0)
    for pair, tf in CELLS:
        t0 = time.time()
        Pn = hrd.prepare(pair, tf, {'fgfOn': False})
        Pr = hrd.prepare(pair, tf, {'fgfOn': False, 'reverse': True})
        if not (np.array_equal(Pn['long_sig'], Pr['short_sig']) and np.array_equal(Pn['short_sig'], Pr['long_sig'])):
            _p('  %s %s: the reversed signals are not the swapped signals' % (pair, tf))
            ok_all = False
        n = Pn['n']
        n_dbl = int((Pn['long_sig'] & Pn['short_sig']).sum())
        if tf != '1':
            Pr['sub'] = hrd.get_sub(Pn)
        Pn0, Pr0 = _no_double(Pn), _no_double(Pr)
        sets = [dict(path=p, cost=c) for p in ('tv', 'mag') for c in ('tv', 'ours')]
        sets += [_rand_X(rng, 'mag' if (rng.random() < 0.3 and tf != '1') else 'tv', 0.4) for _ in range(6)]
        cell = dict(pairs=0, exact=0, with_ep=0, episodes=0, matched=0, in_ep=0, trades=0, fixed=0)
        for X in sets:
            Xi = dict(X)
            Xi['hrdInv'] = True
            cell['fixed'] += 2 * (float(X.get('InpSlPct', 2.0)) <= 0.0)
            for nmA, PA, XA, PB, XB in (('inv vs reverse', Pn, Xi, Pr, X), ('reverse+inv vs neither', Pr, Xi, Pn, X)):
                RA = hrd.simulate(PA, XA, full=True)
                RB = hrd.simulate(PB, XB, full=True)
                ok, info, msgs = _same_orders(n, RA, RB, True, False,
                                              fixed_qty=float(X.get('InpSlPct', 2.0)) <= 0.0)
                cell['pairs'] += 1
                cell['exact'] += info['exact']
                cell['with_ep'] += info['episodes'] > 0
                cell['episodes'] += info['episodes']
                cell['matched'] += info['matched']
                cell['in_ep'] += info['in_A'] + info['in_B']
                cell['trades'] += len(RA['dir']) + len(RB['dir'])
                if info['double'] and X.get('InpTradeDirection', 'Both') != 'Both':
                    ok = False
                    msgs.append('both entries sent with Trade Direction %s' % X['InpTradeDirection'])
                if not ok:
                    ok_all = False
                    _p('  FAIL %s %s %s %r: %s' % (pair, tf, nmA, X, '; '.join(msgs[:3])))
                # counterfactual: no double-signal candle in the inputs
                PA0 = Pn0 if PA is Pn else Pr0
                PB0 = Pn0 if PB is Pn else Pr0
                bad = _diff_R(hrd.simulate(PA0, XA, full=True), hrd.simulate(PB0, XB, full=True), swap_frame=True)
                tot['cf'] += 1
                tot['cf_bad'] += bool(bad)
                if bad:
                    ok_all = False
                    _p('  FAIL %s %s %s %r, double-signal candles removed: outputs differ %s' % (pair, tf, nmA, X, bad))
        for k_ in cell:
            tot[k_] += cell[k_]
        _p('  %s %-3s: %d candles with a LONG and a SHORT signal; %d run pairs: %d equal bit for bit, %d with '
           'episodes (%d episodes); trades placed outside the episodes %d (all the same), inside %d (%.1fs)'
           % (pair, tf, n_dbl, cell['pairs'], cell['exact'], cell['with_ep'], cell['episodes'], cell['matched'],
              cell['in_ep'], time.time() - t0))
        hrd._SIG.clear()
    _p('  total: %d run pairs (%d trades; %d pairs with the fixed quantity): %d equal bit for bit, %d with episodes '
       '(%d episodes, %d trades inside, %d trades outside); counterfactual without double-signal candles: %d pairs, '
       '%d not equal bit for bit'
       % (tot['pairs'], tot['trades'], tot['fixed'], tot['exact'], tot['with_ep'], tot['episodes'], tot['in_ep'],
          tot['matched'], tot['cf'], tot['cf_bad']))
    return ok_all and tot['exact'] > 0 and tot['with_ep'] > 0 and tot['exact'] + tot['with_ep'] == tot['pairs']


def _swapped(Pp):
    """prepare()'s arrays with the two sides exchanged: LONG signals <-> SHORT signals AND
    buyOk <-> sellOk (the mirror of the whole normal frame)."""
    Q = dict(Pp)
    Q['long_sig'], Q['short_sig'] = Pp['short_sig'], Pp['long_sig']
    Q['buy_ok'], Q['sell_ok'] = Pp['sell_ok'], Pp['buy_ok']
    return Q


def test_R2b_filter_on_swap_identity():
    """R2b: the flip is applied AFTER the gate. With the filter ON, the inverted run must place
    exactly the orders of the verified normal kernel fed with the mirror of the whole normal frame
    (LONG <-> SHORT signals and buyOk <-> sellOk): a LONG signal in the BUY ZONE = a sell, a blocked
    LONG signal against an open long = close that long, Trade Direction = the orders really placed.
    (Reverse Trading swaps only the signals, so with the filter on Inverted is NOT the reversed
    run: also checked.) All 14 cells, full windows, the defaults (tv / mag x cost tv / ours) and 6
    random settings each, labels normal and reversed; every kernel output equal bit for bit unless
    a candle sends both entries (then _same_orders' episode rule; the filter never allows both
    sides at once, so none is expected)."""
    rng = np.random.default_rng(3)
    ok_all = True
    n_pairs = n_exact = n_tr = n_blk = n_differs_from_rev = 0
    both_ok = 0
    for pair, tf in CELLS:
        t0 = time.time()
        cell_pairs = cell_exact = 0
        P = {lab: hrd.prepare(pair, tf, {'reverse': lab == 'rev'}) for lab in ('normal', 'rev')}
        both_ok += int((P['normal']['buy_ok'] & P['normal']['sell_ok']).sum())
        if tf != '1':
            P['rev']['sub'] = hrd.get_sub(P['normal'])
        sets = [dict(path=p, cost=c) for p in ('tv', 'mag') for c in ('tv', 'ours')]
        sets += [_rand_X(rng, 'mag' if (rng.random() < 0.3 and tf != '1') else 'tv', 0.4) for _ in range(6)]
        for X in sets:
            Xi = dict(X)
            Xi['hrdInv'] = True
            for lab in ('normal', 'rev'):
                Pp = P[lab]
                RA = hrd.simulate(Pp, Xi, full=True)
                RB = hrd.simulate(_swapped(Pp), X, full=True)
                ok, info, msgs = _same_orders(Pp['n'], RA, RB, True, False)
                n_pairs += 1
                cell_pairs += 1
                n_exact += info['exact']
                cell_exact += info['exact']
                n_tr += len(RA['dir'])
                n_blk += int((RA['kind'] == K['blocked_close']).sum())
                if not ok:
                    ok_all = False
                    _p('  FAIL %s %s %s %r: %s' % (pair, tf, lab, X, '; '.join(msgs[:3])))
            # with the filter on, Inverted is not Reverse Trading
            Rr = hrd.simulate(P['rev'], X, full=True)
            Ri = hrd.simulate(P['normal'], Xi, full=True)
            n_differs_from_rev += bool(_diff_R(Ri, Rr, swap_frame=True))
        _p('  %s %-3s: %d run pairs, %d equal bit for bit (%.1fs)' % (pair, tf, cell_pairs, cell_exact, time.time() - t0))
        hrd._SIG.clear()
        hrd._PERM.clear()
    _p('  total: %d run pairs, %d equal bit for bit, %d inverted trades (%d blocked closes); bars with buyOk and '
       'sellOk both true: %d; inverted != reversed labels (filter on) in %d of %d settings'
       % (n_pairs, n_exact, n_tr, n_blk, both_ok, n_differs_from_rev, n_pairs // 2))
    return ok_all and n_blk > 0 and n_differs_from_rev > 0


def test_R2c_header_statements():
    """R2c: the header's statements read directly on the inverted runs (hrdInv on, defaults, path
    tv, cost tv; filter on and off; all 14 cells), from the kernel's trade list and the inputs:
    (a) every real SELL comes from a LONG signal the gate allows (buyOk), every real BUY from a
        SHORT signal it allows (sellOk); the order is placed on the signal candle and fills at the
        next open;
    (b) SL / TP mirrored about the signal close, same distances: a sell has its stop at close x
        (1 + SL %) and its target at close x (1 - TP %), a buy the other way round;
    (c) quantity = the risk rule on the account's equity at the signal close and the same stop
        distance (equity x 1 % / (close x 2 %), floor 0.01);
    (d) a blocked_close of a real long was ordered on a candle with a LONG signal the filter
        blocked (not buyOk), of a real short on a blocked SHORT signal; a 'reverse' exit of a real
        long was ordered by an allowed LONG signal (a sell), of a real short by an allowed SHORT;
    (e) Trade Direction = the orders really placed: Buy Only -> only real buys, all from SHORT
        signals; Sell Only -> only real sells, all from LONG signals;
    (f) the inverted trade list against the normal one: the first trade is the mirror (same signal
        candle, fill candle, price and quantity, other side); the lists stay mirrored (in price
        space) until an exit that the header names as different on the two sides (SL / TP, hybrid),
        never before. Prints the length of the mirrored prefix and the exit kinds at its end."""
    ok_all = True
    tot = dict(trades=0, sells=0, buys=0, blk=0, rev=0, qty=0)
    for pair, tf in CELLS:
        msgs = []
        line = []
        for flt in ('off', 'on'):
            Pp = hrd.prepare(pair, tf, {'fgfOn': flt == 'on'})
            c, o = Pp['c'], Pp['o']
            L, S, bok, sok = Pp['long_sig'], Pp['short_sig'], Pp['buy_ok'], Pp['sell_ok']
            R = hrd.simulate(Pp, {'hrdInv': True}, full=True)
            N = hrd.simulate(Pp, None, full=True)
            d, sk, ek = R['dir'], R['sk'], R['ek']
            sell = d < 0
            buy = d > 0
            tot['trades'] += len(d)
            tot['sells'] += int(sell.sum())
            tot['buys'] += int(buy.sum())
            # (a)
            if not ((L[sk[sell]] & bok[sk[sell]]).all() and (S[sk[buy]] & sok[sk[buy]]).all()):
                msgs.append('%s (a) side vs signal / gate' % flt)
            if not (np.array_equal(ek, sk + 1) and np.array_equal(R['epx'], o[ek])):
                msgs.append('%s (a) fill candle / price' % flt)
            # (b)
            sl_exp = np.where(sell, c[sk] * (1.0 + 2.0 / 100.0), c[sk] * (1.0 - 2.0 / 100.0))
            tp_exp = np.where(sell, c[sk] * (1.0 - 4.0 / 100.0), c[sk] * (1.0 + 4.0 / 100.0))
            if not (np.array_equal(R['sl'], sl_exp) and np.array_equal(R['tp'], tp_exp)
                    and (R['sl'][sell] > c[sk[sell]]).all() and (R['tp'][sell] < c[sk[sell]]).all()
                    and (R['sl'][buy] < c[sk[buy]]).all() and (R['tp'][buy] > c[sk[buy]]).all()):
                msgs.append('%s (b) SL / TP' % flt)
            # (c)
            q_exp = np.maximum(R['eq'][sk] * (1.0 / 100.0) / (c[sk] * (2.0 / 100.0) * 1.0), 0.01)
            if not np.allclose(R['qty'], q_exp, rtol=1e-12, atol=0.0):
                msgs.append('%s (c) quantity' % flt)
            tot['qty'] += len(d)
            # (d)
            xsk = R['xsk']
            bc = R['kind'] == K['blocked_close']
            rv = R['kind'] == K['reverse']
            tot['blk'] += int(bc.sum())
            tot['rev'] += int(rv.sum())
            x = xsk[bc & buy]
            y = xsk[bc & sell]
            if not ((L[x] & ~bok[x]).all() and (S[y] & ~sok[y]).all()):
                msgs.append('%s (d) blocked close' % flt)
            x = xsk[rv & buy]
            y = xsk[rv & sell]
            if not ((L[x] & bok[x]).all() and (S[y] & sok[y]).all()):
                msgs.append('%s (d) reversal' % flt)
            # (e)
            Rb = hrd.simulate(Pp, {'hrdInv': True, 'InpTradeDirection': 'Buy Only'})
            Rs = hrd.simulate(Pp, {'hrdInv': True, 'InpTradeDirection': 'Sell Only'})
            if not (len(Rb['dir']) and (Rb['dir'] > 0).all() and (S[Rb['sk']] & sok[Rb['sk']]).all()
                    and len(Rs['dir']) and (Rs['dir'] < 0).all() and (L[Rs['sk']] & bok[Rs['sk']]).all()):
                msgs.append('%s (e) Trade Direction' % flt)
            # (f) mirrored prefix against the normal run
            m = min(len(d), len(N['dir']))
            i = 0
            while i < m:
                a, b = _pkey(R, i), _pkey(N, i)
                mirror = (a[0] == -b[0] and a[1:8] == b[1:8]
                          and _close(a[8] - c[a[1]], c[a[1]] - b[8], 1e-9, 1e-9)
                          and _close(a[9] - c[a[1]], c[a[1]] - b[9], 1e-9, 1e-9))
                if not mirror:
                    break
                i += 1
            if m == 0:
                msgs.append('%s (f) no trades' % flt)
            else:                             # the first entry: same candle, price and quantity, other side
                a, b = _pkey(R, 0), _pkey(N, 0)
                if not (a[0] == -b[0] and a[1] == b[1] and a[2] == b[2] and a[6] == b[6]
                        and float(R['qty'][0]) == float(N['qty'][0])
                        and _close(a[8] - c[a[1]], c[a[1]] - b[8], 1e-9, 1e-9)
                        and _close(a[9] - c[a[1]], c[a[1]] - b[9], 1e-9, 1e-9)):
                    msgs.append('%s (f) the first entry is not the mirror' % flt)
            if i < m:
                a, b = _pkey(R, i), _pkey(N, i)
                entry_mirror = (a[0] == -b[0] and a[1] == b[1] and a[2] == b[2] and a[6] == b[6])
                asym = {K['sl'], K['tp'], K['trail'], K['hybrid']}
                if not (entry_mirror and (a[5] in asym or b[5] in asym)):
                    msgs.append('%s (f) the lists part at trade %d without an SL / TP / hybrid exit: %r vs %r' % (flt, i, a, b))
                line.append('%s: %d trades, mirrored prefix %d, then inverted exit %s / normal exit %s'
                            % (flt, len(d), i, hrd.KINDS[a[5]], hrd.KINDS[b[5]]))
            else:
                line.append('%s: %d trades, mirrored to the end' % (flt, len(d)))
        _p('  %s %-3s: %s%s' % (pair, tf, '; '.join(line), '' if not msgs else ' | FAIL: ' + '; '.join(msgs)))
        ok_all &= not msgs
        hrd._SIG.clear()
        hrd._PERM.clear()
    _p('  total: %d inverted trades (%d real sells from allowed LONG signals, %d real buys from allowed SHORT '
       'signals), %d blocked closes, %d reversals, %d quantities checked'
       % (tot['trades'], tot['sells'], tot['buys'], tot['blk'], tot['rev'], tot['qty']))
    return ok_all and tot['blk'] > 0 and tot['rev'] > 0


# ---------------------------------------------------------------------------------------------
# R3: mirror property on single decisions
# ---------------------------------------------------------------------------------------------
def _micro(Pp, k, m, s0, sig, perm):
    """m + 2 real bars k-m .. k+1 of Pp. Bar 0: a forced normal-frame entry signal of side s0
    (+1 LONG, -1 SHORT, 0 none), both sides allowed by the gate; bars 1 .. m-1: no signal; bar m
    (= k, the decision under test): signals sig = (LONG, SHORT), permissions perm = (buyOk, sellOk).
    Bar m+1 only receives the fills of the orders placed on bar m."""
    a, b = k - m, k + 2
    n = m + 2
    L = np.zeros(n, np.bool_)
    S = np.zeros(n, np.bool_)
    bo = np.ones(n, np.bool_)
    so = np.ones(n, np.bool_)
    if s0 > 0:
        L[0] = True
    elif s0 < 0:
        S[0] = True
    L[m], S[m] = sig
    bo[m], so[m] = perm
    Q = dict(Pp)
    Q.update(o=Pp['o'][a:b], h=Pp['h'][a:b], l=Pp['l'][a:b], c=Pp['c'][a:b], long_sig=L, short_sig=S,
             buy_ok=bo, sell_ok=so, n=n, cap=2 * n + 4, mid_j=0, sub=None,
             t_open=Pp['t_open'][a:b], t_close=Pp['t_close'][a:b])
    return Q


_MIRROR_DIR = {'Both': 'Both', 'Buy Only': 'Sell Only', 'Sell Only': 'Buy Only'}


def _decision(R, m):
    """What the script decided on bar m of a micro-run, read from the kernel outputs: the normal
    frame flags, the time exit (entryBarIndex reset), and the fills of bar m's orders at the open
    of bar m+1 in order: trades closed by an order of bar m (side, kind) and trades opened by an
    entry of bar m (side, quantity, SL, TP, fill price, and its exit kind if an order of bar m
    closed it at that same open)."""
    fl = (bool(R['want_l'][m]), bool(R['want_s'][m]), bool(R['blk_l'][m]), bool(R['blk_s'][m]))
    ev = []
    for i in range(len(R['dir'])):
        placed_exit = int(R['xsk'][i]) == m
        opened = int(R['sk'][i]) == m
        if not (placed_exit or opened):
            continue
        ev.append(dict(dir=int(R['dir'][i]), opened=opened, closed=placed_exit,
                       kind=int(R['kind'][i]) if placed_exit else -1,
                       qty=float(R['qty'][i]), sl=float(R['sl'][i]), tp=float(R['tp'][i]),
                       epx=float(R['epx'][i]), xpx=float(R['xpx'][i]) if placed_exit else 0.0))
    return fl, int(R['ebi'][m]), ev


def test_R3_mirror_single_decisions():
    """R3: single decisions. Around sampled real bars k (BTC 60, XAU 240, BTC 5, XAU 15; filter
    arrays replaced by enumerated cases) the kernel is run on the micro-window k-m .. k+1 (m in
    1..4): a forced entry on its first bar puts the account in a real position p on bar k (or
    none), then bar k gets every case of (LONG signal, SHORT signal) x (buyOk, sellOk) x
    blkClose x Trade Direction x forced side (long / short / flat) = 288 cases per bar, with
    random SL / TP / exit-candles per bar. The orders placed on bar k are read from their fills at
    the next open.
    (i) MIRROR (hybrid exit off): the decision with the option ON from real position p equals the
        mirror of the decision with it OFF from -p. Both runs get the same normal-frame inputs
        (Trade Direction mirrored: it names the orders really placed); cases where the two
        positions on bar k are not mirror images (one bracket was hit on the way) are skipped and
        counted. Compared: want / blocked flags equal; time exit (entryBarIndex) equal; the same
        closes in the same order on the mirrored trade (blocked close, time, reverse); the same
        entries on the other side, SL / TP mirrored about bar k's close at the same distances
        (and exactly close x (1 -/+ SL %), close x (1 +/- TP %) for the real side), quantity by
        the same rule on each account's own equity (equal when the equities are equal).
    (ii) SAME REAL TRADE (hybrid exit on, random minDecayUpdates / exit candles): the time exit
        and the hybrid exit measure the trade really open, they are not mirrored. The run with the
        option ON must equal, on every kernel output, the run with it OFF fed with the mirrored
        normal frame (signals and permissions swapped, so the same real trade is open); when bar k
        sends both entries (flat, both signals, both allowed) only their order differs: the second
        one stays, a BUY with the option, a SELL without."""
    rng = np.random.default_rng(33)
    cases = [(s0, sig, perm, blk, td)
             for s0 in (1, -1, 0)
             for sig in ((False, False), (True, False), (False, True), (True, True))
             for perm in ((True, True), (True, False), (False, True), (False, False))
             for blk in (True, False)
             for td in ('Both', 'Buy Only', 'Sell Only')]
    ok_all = True
    st = dict(bars=0, mirror=0, skipped=0, closes=0, entries=0, time=0, blk=0, rev=0, pos_cases=0, flat_cases=0,
              same=0, hyb=0, dbl=0, time2=0)
    fails = []
    for pair, tf, nb in (('BTC', '60', 150), ('XAU', '240', 150), ('BTC', '5', 100), ('XAU', '15', 100)):
        t0 = time.time()
        Pp = hrd.prepare(pair, tf, {'fgfOn': False})
        ks = rng.choice(np.arange(8, Pp['n'] - 3), nb, replace=False)
        for k in ks.tolist():
            st['bars'] += 1
            m = int(rng.integers(1, 5))
            slp, tpp = [(2.0, 4.0), (2.0, 4.0), (0.5, 1.0), (1.0, 1.0), (0.0, 0.0), (3.0, 0.0), (0.2, 0.3)][int(rng.integers(0, 7))]
            base = dict(InpSlPct=slp, InpTpPct=tpp, InpExitCandles=int(rng.choice([1, 2, 3, 5])),
                        cost=str(rng.choice(['tv', 'ours'])))
            hyb = dict(base, useHybridExit=True, minDecayUpdates=int(rng.integers(1, 4)),
                       InpExitCandles=int(rng.choice([2, 3, 50])), minActivationPts=int(rng.choice([1, 40])))
            ck = float(Pp['c'][k])
            for s0, sig, perm, blk, td in cases:
                Q = _micro(Pp, k, m, s0, sig, perm)
                # ---- (i) mirror
                Xon = dict(base, useHybridExit=False, blkClose=blk, InpTradeDirection=td, hrdInv=True)
                Xoff = dict(base, useHybridExit=False, blkClose=blk, InpTradeDirection=_MIRROR_DIR[td], hrdInv=False)
                A = hrd.simulate(Q, Xon, full=True)
                B = hrd.simulate(Q, Xoff, full=True)
                if not np.array_equal(A['pos'][:m + 1], -B['pos'][:m + 1]):
                    st['skipped'] += 1
                else:
                    st['mirror'] += 1
                    if A['pos'][m] != 0:
                        st['pos_cases'] += 1
                    else:
                        st['flat_cases'] += 1
                    fa, ea, va = _decision(A, m)
                    fb, eb, vb = _decision(B, m)
                    good = fa == fb and ea == eb and len(va) == len(vb) and np.array_equal(A['ebi'][:m + 1], B['ebi'][:m + 1])
                    if good:
                        for x, y in zip(va, vb):
                            good &= (x['dir'] == -y['dir'] and x['opened'] == y['opened'] and x['closed'] == y['closed']
                                     and x['kind'] == y['kind'] and x['epx'] == y['epx'] and x['xpx'] == y['xpx'])
                            if x['closed']:
                                st['closes'] += 1
                                st['time'] += x['kind'] == K['time']
                                st['blk'] += x['kind'] == K['blocked_close']
                                st['rev'] += x['kind'] == K['reverse']
                            if x['opened']:
                                st['entries'] += 1
                                for r, eq in ((x, float(A['eq'][m])), (y, float(B['eq'][m]))):
                                    d = r['dir']
                                    if slp > 0.0:
                                        good &= r['sl'] == (ck * (1.0 - slp / 100.0) if d > 0 else ck * (1.0 + slp / 100.0))
                                        q_exp = max(eq * (1.0 / 100.0) / (ck * (slp / 100.0) * 1.0), 0.01)
                                        good &= _close(r['qty'], q_exp, 1e-12)
                                    else:
                                        good &= math.isnan(r['sl']) and r['qty'] == 0.01
                                    if tpp > 0.0:
                                        good &= r['tp'] == (ck * (1.0 + tpp / 100.0) if d > 0 else ck * (1.0 - tpp / 100.0))
                                    else:
                                        good &= math.isnan(r['tp'])
                                if slp > 0.0:
                                    good &= _close(x['sl'] - ck, ck - y['sl'], 1e-9, 1e-9)
                                if tpp > 0.0:
                                    good &= _close(x['tp'] - ck, ck - y['tp'], 1e-9, 1e-9)
                                if float(A['eq'][m]) == float(B['eq'][m]):
                                    good &= x['qty'] == y['qty']
                    if not good:
                        ok_all = False
                        if len(fails) < 5:
                            fails.append('(i) %s %s bar %d m %d case %r base %r: on %r | off %r'
                                         % (pair, tf, k, m, (s0, sig, perm, blk, td), base, _decision(A, m), _decision(B, m)))
                # ---- (ii) the same real trade: time exit and hybrid exit
                Xon = dict(hyb, blkClose=blk, InpTradeDirection=td, hrdInv=True)
                Xoff = dict(hyb, blkClose=blk, InpTradeDirection=td, hrdInv=False)
                A = hrd.simulate(Q, Xon, full=True)
                B = hrd.simulate(_swapped(Q), Xoff, full=True)
                both = (A['want_l'][m] and not A['blk_l'][m]) and (A['want_s'][m] and not A['blk_s'][m])
                st['same'] += 1
                st['hyb'] += int((A['kind'] == K['hybrid']).sum())
                st['time2'] += int((A['kind'] == K['time']).sum())
                if not both:
                    good = not _diff_R(A, B, swap_frame=True)
                else:
                    st['dbl'] += 1
                    ok2, info, msgs = _same_orders(m + 2, A, B, True, False, fixed_qty=slp <= 0.0)
                    good = ok2 and info['episodes'] == 1
                if not good:
                    ok_all = False
                    if len(fails) < 5:
                        fails.append('(ii) %s %s bar %d m %d case %r hyb %r' % (pair, tf, k, m, (s0, sig, perm, blk, td), hyb))
        _p('  %s %-3s: %d bars x %d cases (%.1fs)' % (pair, tf, nb, len(cases), time.time() - t0))
    for f in fails:
        _p('  FAIL ' + f)
    _p('  (i) mirror: %d decisions compared (%d from a real position, %d flat), %d skipped (positions on bar k not '
       'mirror images); closes compared %d (time %d, blocked close %d, reverse %d), entries compared %d'
       % (st['mirror'], st['pos_cases'], st['flat_cases'], st['skipped'], st['closes'], st['time'], st['blk'], st['rev'],
          st['entries']))
    _p('  (ii) same real trade: %d decisions compared, every kernel output equal; hybrid exits %d, time exits %d; '
       'bars sending both entries %d (the second stays: BUY inverted, SELL not)'
       % (st['same'], st['hyb'], st['time2'], st['dbl']))
    return (ok_all and st['pos_cases'] > 1000 and st['time'] > 0 and st['blk'] > 0 and st['rev'] > 0
            and st['hyb'] > 0 and st['dbl'] > 0)


# ---------------------------------------------------------------------------------------------
# R4: mag on chart "1" == tv with the option on
# ---------------------------------------------------------------------------------------------
def test_R4_mag_chart1():
    """R4: with the option ON, path 'mag' on chart "1" (the real 1-minute sub-bars are the chart
    bars) equals path 'tv' on every kernel output: BTC 1 and XAU 1, full windows, filter off and
    on, the defaults (cost tv and ours) and 6 random settings each (trail, TP, SL, candles,
    hybrid, blkClose, Trade Direction, cost). Also: mag with a fake sub-bar table (every chart
    bar its own single sub-bar) == tv on BTC 60 and XAU 240, option on, 12 settings each."""
    rng = np.random.default_rng(4)
    ok_all = True
    for pair, tf, fake in (('BTC', '1', False), ('XAU', '1', False), ('BTC', '60', True), ('XAU', '240', True)):
        for flt in ('off', 'on'):
            t0 = time.time()
            Pp = hrd.prepare(pair, tf, {'fgfOn': flt == 'on'})
            if fake:
                Pp['sub'] = _fake_sub(Pp)
            else:
                ptr = hrd.get_sub(Pp)[0]
                if not np.array_equal(ptr, np.arange(Pp['n'] + 1)):
                    _p('  %s 1: the sub-bar table is not one per chart bar' % pair)
                    ok_all = False
            sets = [dict(cost='tv'), dict(cost='ours')] + [_rand_X(rng, 'tv', 0.6) for _ in range(10 if fake else 6)]
            n_eq = n_tr = 0
            for X in sets:
                X = dict(X)
                X['hrdInv'] = True
                X['path'] = 'tv'
                a = hrd.simulate(Pp, X, full=True)
                X['path'] = 'mag'
                b = hrd.simulate(Pp, X, full=True)
                n_tr += len(a['dir'])
                bad = _diff_R(a, b)
                if bad:
                    ok_all = False
                    _p('  DIFF %s %s %s %r: %s' % (pair, tf, flt, X, bad))
                else:
                    n_eq += 1
            _p('  %s %-3s filter %-3s %s: %d/%d settings equal (%d inverted trades) (%.1fs)'
               % (pair, tf, flt, 'fake sub-bars' if fake else 'real 1m sub-bars', n_eq, len(sets), n_tr, time.time() - t0))
        hrd._SIG.clear()
        hrd._PERM.clear()
    return ok_all


# ---------------------------------------------------------------------------------------------
# R5: the kernel with the option on == a pure-Python port of the Pine at HEAD
# ---------------------------------------------------------------------------------------------
def pine_ref_run(Pp, X, subs=None):
    """Pure-Python port of the Pine at HEAD, section RISK ENGINE EXECUTION LOGIC to HYBRID
    DECAY-SLIP EXIT ENGINE (lines 972-1106), with hrdInv, on a plain broker (market orders fill at
    the next open in placement order; strategy.entry opposite to the position reverses it in the
    same fill, same direction is ignored; strategy.close(id) closes the trade its id opened;
    strategy.exit(from_entry) = the SL / TP / trail order of that entry, walked along the bar's
    path or the 1-minute sub-bars by sweep_ah_tests._hrd_ref_exit, the independent intrabar
    reference that Update 1 does not touch). It keeps the Pine's names and its order ids and
    comments, and does not use hrd's kernels. Inputs from hrd.prepare: window OHLC, longSignal /
    shortSignal (after Reverse Trading), fgfBuyOk / fgfSellOk. Returns the list of trades."""
    import sweep_ah_tests as T0
    p = dict(hrd.DEFAULTS)
    p.update(Pp['params'])
    for kx, vx in X.items():
        p[hrd._ALIASES.get(kx, kx)] = vx
    pair = Pp['pair']
    mintick = 0.01
    pointvalue = 1.0
    o, h, l, c = (Pp[k].tolist() for k in ('o', 'h', 'l', 'c'))
    longSig, shortSig = Pp['long_sig'].tolist(), Pp['short_sig'].tolist()
    buyOk, sellOk = Pp['buy_ok'].tolist(), Pp['sell_ok'].tolist()
    n = len(o)
    hrdInv = bool(p['hrdInv'])
    InpTradeDirection = p['InpTradeDirection']
    InpSlPct, InpTpPct = float(p['InpSlPct']), float(p['InpTpPct'])
    InpRiskPct, InpFixedQty = float(p['InpRiskPct']), float(p['InpFixedQty'])
    InpExitCandles = int(p['InpExitCandles'])
    hrdBlkClose = bool(p['blkClose'])
    hrdTrailOn, hrdTrailAct, hrdTrailOff = bool(p['trailOn']), float(p['trailAct']), float(p['trailOff'])
    useHybridExit = bool(p['useHybridExit'])
    hybridSensitivity, trailStepMult = float(p['hybridSensitivity']), float(p['trailStepMult'])
    minDecayUpdates, minActivationPts = int(p['minDecayUpdates']), int(p['minActivationPts'])
    trades = []
    st = {'cash': 1_000_000.0, 'pos': None}
    LONG, SHORT = 1, -1

    def close_pos(k, px, kind, comment=''):
        q = st['pos']
        xc = T0._hrd_ref_fill_cost(pair, p['cost'], px, q['qty'])
        gross = q['dir'] * q['qty'] * (px - q['px']) * pointvalue
        st['cash'] += gross - xc
        trades.append(dict(dir=q['dir'], ek=q['ek'], sk=q['sk'], epx=q['px'], qty=q['qty'], xk=k, xpx=px, kind=kind,
                           pnl=gross - (q['cost'] + xc), eqb=q['eqb'], sl=q['sl'], tp=q['tp'], id=q['id'],
                           entry_comment=q['comment'], exit_comment=comment))
        st['pos'] = None

    def calculatePositionSize(slDistancePrice, equity):
        if InpSlPct <= 0.0 or slDistancePrice <= 0.0:
            return InpFixedQty
        riskAmount = equity * (InpRiskPct / 100.0)
        if pointvalue > 0.0:
            positionSize = riskAmount / (slDistancePrice * pointvalue)
        else:
            positionSize = InpFixedQty
        if positionSize < InpFixedQty:
            positionSize = InpFixedQty
        return positionSize

    pending = []
    size_prev = 0.0
    entryBarIndex = None
    g_PeakProfit, g_UpdateCounter = 0.0, 0
    for k in range(n):
        # ---- broker: the orders of the previous bar at this open, in placement order
        for od in pending:
            if od[0] == 'close_all':
                if st['pos'] is not None:
                    close_pos(k, o[k], od[1], od[2])
            elif od[0] == 'close':
                if st['pos'] is not None and st['pos']['id'] == od[1]:
                    close_pos(k, o[k], 'blocked_close', od[2])
            else:
                _, oid, direction, qty, comment, ex, sk = od
                if st['pos'] is not None and st['pos']['dir'] == direction:
                    continue                                  # pyramiding 0
                if st['pos'] is not None:
                    close_pos(k, o[k], 'reverse', comment)
                ec = T0._hrd_ref_fill_cost(pair, p['cost'], o[k], qty)
                eqb = st['cash']
                st['cash'] -= ec
                trail = None
                if ex['trail_points'] is not None:
                    trail = dict(A=o[k] + direction * ex['trail_points'] * mintick, ofs=ex['trail_offset'] * mintick,
                                 armed=ex['trail_points'] == 0.0, best=o[k])
                st['pos'] = dict(id=oid, dir=direction, qty=qty, px=o[k], ek=k, sk=sk, cost=ec, eqb=eqb,
                                 sl=ex['stop'], tp=ex['limit'], comment=comment, exit_comment=ex['comment'],
                                 ex=dict(stop=ex['stop'], limit=ex['limit'], trail=trail))
        pending = []
        q = st['pos']
        if q is not None and (q['sl'] is not None or q['tp'] is not None or q['ex']['trail'] is not None):
            for bar in (subs[k] if subs is not None else [(o[k], h[k], l[k], c[k])]):
                hit = T0._hrd_ref_exit(q['dir'], bar[0], bar[1], bar[2], bar[3], q['ex'])
                if hit is not None:
                    close_pos(k, hit[1], hit[0], q['exit_comment'])
                    break
        # ---- the script at the close of bar k
        q = st['pos']
        close = c[k]
        position_size = q['dir'] * q['qty'] if q is not None else 0.0
        position_avg_price = q['px'] if q is not None else None
        equity = st['cash'] + (q['dir'] * q['qty'] * (close - q['px']) * pointvalue if q is not None else 0.0)
        longSignal, shortSignal = longSig[k], shortSig[k]
        fgfBuyOk, fgfSellOk = buyOk[k], sellOk[k]
        # 2. Apply Trade Direction Filter
        longDirectionAllowed = (InpTradeDirection == 'Both') or (InpTradeDirection == 'Buy Only')
        shortDirectionAllowed = (InpTradeDirection == 'Both') or (InpTradeDirection == 'Sell Only')
        # 3. Time-based exit
        if position_size != 0 and size_prev == 0:
            entryBarIndex = k
        if position_size != 0 and entryBarIndex is not None and (k - entryBarIndex >= InpExitCandles):
            pending.append(('close_all', 'time', 'Time-based Exit'))
            entryBarIndex = None
        # UPDATE 1
        hrdPos = -position_size if hrdInv else position_size
        hrdDirOkL = shortDirectionAllowed if hrdInv else longDirectionAllowed
        hrdDirOkS = longDirectionAllowed if hrdInv else shortDirectionAllowed
        hrdIdL = 'Short' if hrdInv else 'Long'
        hrdIdS = 'Long' if hrdInv else 'Short'
        hrdWantLong = longSignal and hrdDirOkL and hrdPos <= 0
        hrdWantShort = shortSignal and hrdDirOkS and hrdPos >= 0
        hrdBlkLong = hrdWantLong and not fgfBuyOk
        hrdBlkShort = hrdWantShort and not fgfSellOk
        if hrdBlkClose and hrdBlkLong and hrdPos < 0:
            pending.append(('close', hrdIdS, 'filter blocked LONG signal, close long (inv)' if hrdInv else 'filter blocked LONG, close'))
        if hrdBlkClose and hrdBlkShort and hrdPos > 0:
            pending.append(('close', hrdIdL, 'filter blocked SHORT signal, close short (inv)' if hrdInv else 'filter blocked SHORT, close'))
        # 4. LONG EXECUTION
        if hrdWantLong and fgfBuyOk:
            estimatedEntryPrice = close
            stopLossDistanceLong = estimatedEntryPrice * (InpSlPct / 100.0) if InpSlPct > 0.0 else 0.0
            stopLossPriceLong = (estimatedEntryPrice * ((1.0 + InpSlPct / 100.0) if hrdInv else (1.0 - InpSlPct / 100.0))
                                 if InpSlPct > 0.0 else None)
            takeProfitPriceLong = (estimatedEntryPrice * ((1.0 - InpTpPct / 100.0) if hrdInv else (1.0 + InpTpPct / 100.0))
                                   if InpTpPct > 0.0 else None)
            longQuantity = calculatePositionSize(stopLossDistanceLong, equity)
            hrdTrPts = max(estimatedEntryPrice * hrdTrailAct / 100.0 / mintick, 0.0) if hrdTrailOn else None
            hrdTrOfs = max(estimatedEntryPrice * hrdTrailOff / 100.0 / mintick, 1.0) if hrdTrailOn else None
            pending.append(('entry', hrdIdL, SHORT if hrdInv else LONG, longQuantity,
                            'Entry Short (inv)' if hrdInv else 'Entry Long',
                            dict(id='Short Exit' if hrdInv else 'Long Exit', from_entry=hrdIdL, stop=stopLossPriceLong,
                                 limit=takeProfitPriceLong, trail_points=hrdTrPts, trail_offset=hrdTrOfs,
                                 comment='SL/TP Short (inv)' if hrdInv else 'SL/TP Long'), k))
        # 5. SHORT EXECUTION
        if hrdWantShort and fgfSellOk:
            estimatedEntryPrice = close
            stopLossDistanceShort = estimatedEntryPrice * (InpSlPct / 100.0) if InpSlPct > 0.0 else 0.0
            stopLossPriceShort = (estimatedEntryPrice * ((1.0 - InpSlPct / 100.0) if hrdInv else (1.0 + InpSlPct / 100.0))
                                  if InpSlPct > 0.0 else None)
            takeProfitPriceShort = (estimatedEntryPrice * ((1.0 + InpTpPct / 100.0) if hrdInv else (1.0 - InpTpPct / 100.0))
                                    if InpTpPct > 0.0 else None)
            shortQuantity = calculatePositionSize(stopLossDistanceShort, equity)
            hrdTrPts = max(estimatedEntryPrice * hrdTrailAct / 100.0 / mintick, 0.0) if hrdTrailOn else None
            hrdTrOfs = max(estimatedEntryPrice * hrdTrailOff / 100.0 / mintick, 1.0) if hrdTrailOn else None
            pending.append(('entry', hrdIdS, LONG if hrdInv else SHORT, shortQuantity,
                            'Entry Long (inv)' if hrdInv else 'Entry Short',
                            dict(id='Long Exit' if hrdInv else 'Short Exit', from_entry=hrdIdS, stop=stopLossPriceShort,
                                 limit=takeProfitPriceShort, trail_points=hrdTrPts, trail_offset=hrdTrOfs,
                                 comment='SL/TP Long (inv)' if hrdInv else 'SL/TP Short'), k))
        # HYBRID DECAY-SLIP EXIT ENGINE (unchanged: the trade really open)
        inTrade = position_size != 0
        isLong = position_size > 0
        currentProfit = 0.0
        if inTrade:
            if isLong:
                currentProfit = close - position_avg_price
            else:
                currentProfit = position_avg_price - close
        if not inTrade:
            g_PeakProfit = 0.0
            g_UpdateCounter = 0
        if useHybridExit and inTrade:
            activationLevel = minActivationPts * mintick
            if (currentProfit >= activationLevel) or (g_PeakProfit >= activationLevel):
                g_UpdateCounter += 1
                if currentProfit > g_PeakProfit:
                    g_PeakProfit = currentProfit
                speedDrop = g_PeakProfit - currentProfit
                decayTriggered = speedDrop > (trailStepMult * 8 * mintick * hybridSensitivity)
                slipTriggered = currentProfit < (g_PeakProfit * 0.85)
                if decayTriggered and slipTriggered and g_UpdateCounter >= minDecayUpdates and g_PeakProfit > 0:
                    pending.append(('close_all', 'hybrid', 'Hybrid Exit'))
                    g_PeakProfit = 0.0
                    g_UpdateCounter = 0
        size_prev = position_size
    if st['pos'] is not None:
        close_pos(n - 1, c[n - 1], 'end')
    return trades


def _cmp_ref(R, ref, rtol=1e-9):
    nt = len(R['dir'])
    if nt != len(ref):
        return False, 'trade count %d vs ref %d' % (nt, len(ref))
    for i, t in enumerate(ref):
        ints = (int(R['dir'][i]) == t['dir'] and int(R['ek'][i]) == t['ek'] and int(R['sk'][i]) == t['sk']
                and int(R['xk'][i]) == t['xk'] and hrd.KINDS[int(R['kind'][i])] == t['kind'])
        pnl = float(R['gross'][i] - R['cost'][i])
        fl = (_close(float(R['epx'][i]), t['epx'], rtol) and _close(float(R['xpx'][i]), t['xpx'], rtol)
              and _close(float(R['qty'][i]), t['qty'], rtol) and _close(pnl, t['pnl'], rtol, 1e-6)
              and _close(float(R['eqb'][i]), t['eqb'], rtol)
              and (_close(float(R['sl'][i]), t['sl'], rtol) if t['sl'] is not None else math.isnan(R['sl'][i]))
              and (_close(float(R['tp'][i]), t['tp'], rtol) if t['tp'] is not None else math.isnan(R['tp'][i])))
        if not (ints and fl):
            return False, ('trade %d differs: kernel dir %d signal %d entry %d exit %d kind %s px %.6f -> %.6f qty %.8f '
                           'pnl %.6f | ref %r' % (i, R['dir'][i], R['sk'][i], R['ek'][i], R['xk'][i],
                                                  hrd.KINDS[int(R['kind'][i])], R['epx'][i], R['xpx'][i], R['qty'][i], pnl, t))
    return True, ''


def _ref_comments_ok(ref, inv):
    """The Pine's ids and comments name the side really traded: id "Long" is always a buy, "Short"
    always a sell; inverted comments end in "(inv)"."""
    for t in ref:
        side = 'Long' if t['dir'] > 0 else 'Short'
        if t['id'] != side:
            return False
        if t['entry_comment'] != ('Entry %s (inv)' % side if inv else 'Entry %s' % side):
            return False
        if t['kind'] in ('sl', 'tp', 'trail') and t['exit_comment'] != ('SL/TP %s (inv)' % side if inv else 'SL/TP %s' % side):
            return False
        if t['kind'] == 'blocked_close':
            if inv:
                exp = ('filter blocked LONG signal, close long (inv)' if t['dir'] > 0
                       else 'filter blocked SHORT signal, close short (inv)')
            else:
                exp = 'filter blocked SHORT, close' if t['dir'] > 0 else 'filter blocked LONG, close'
            if t['exit_comment'] != exp:
                return False
    return True


def test_R5_pine_reference():
    """R5: hrd.simulate with the option ON equals pine_ref_run (a pure-Python port of the Pine at
    HEAD, lines 972-1106, with hrdInv) trade by trade: side, signal / entry / exit bars and exit
    kind exact; prices, quantity, P/L, eq_before, SL / TP within 1e-9. (a) the report cells BTC 60
    and XAU 240, full windows, defaults, direction normal / inverted x filter off / on x path tv /
    mag x cost tv / ours (the 16 runs of run_inv_hrd.py); (b) 40 random settings each over the
    2-month windows BTC 60, XAU 60, BTC 5 (path tv) and 15 each over BTC 60, XAU 60 (path mag, 1-
    minute sub-bars rebuilt independently): filter on / off, labels normal / reversed, hrdInv on in
    3 of 4, Trade Direction, SL / TP / candles, hybrid, blkClose, trail, cost tv / ours / stress.
    Also: in the port every id / comment names the side really traded (the Pine's hrdIdL / hrdIdS
    and comments)."""
    import sweep_ah_tests as T0
    ok_all = True
    kinds = {}
    n_inv_tr = 0

    def one(Pp, X, subs, tag):
        nonlocal ok_all, n_inv_tr
        R = hrd.simulate(Pp, X)
        ref = pine_ref_run(Pp, X, subs)
        ok, msg = _cmp_ref(R, ref)
        inv = bool(X.get('hrdInv', False))
        if ok and not _ref_comments_ok(ref, inv):
            ok, msg = False, 'an id / comment does not name the side really traded'
        for t in ref:
            kinds[t['kind']] = kinds.get(t['kind'], 0) + 1
        if inv:
            n_inv_tr += len(ref)
        if not ok:
            ok_all = False
            _p('  FAIL %s %r: %s' % (tag, X, msg))
        return len(ref)

    # (a) the report cells
    for pair, tf in (('BTC', '60'), ('XAU', '240')):
        t0 = time.time()
        n_tr = 0
        subs = None
        for flt in ('off', 'on'):
            Pp = hrd.prepare(pair, tf, {'fgfOn': flt == 'on'})
            if subs is None:
                subs = T0._hrd_ref_subbars(Pp)
            for inv in (False, True):
                for path in ('tv', 'mag'):
                    for cost in ('tv', 'ours'):
                        n_tr += one(Pp, dict(hrdInv=inv, path=path, cost=cost), subs if path == 'mag' else None,
                                    '%s %s filter %s' % (pair, tf, flt))
        _p('  (a) %s %-3s full window: 16 runs, %d trades compared (%.1fs)' % (pair, tf, n_tr, time.time() - t0))
    # (b) random settings
    rng = np.random.default_rng(5)
    for path, n_per, wins in (('tv', 40, SHORT_WINDOWS), ('mag', 15, SHORT_WINDOWS[:2])):
        for pair, tf, start, end in wins:
            t0 = time.time()
            cache = {}
            subs = None
            n_tr = 0
            for i in range(n_per):
                flt = 'on' if rng.random() < 0.6 else 'off'
                lab = 'rev' if rng.random() < 0.3 else 'normal'
                if (flt, lab) not in cache:
                    cache[(flt, lab)] = hrd.prepare(pair, tf, {'fgfOn': flt == 'on', 'reverse': lab == 'rev',
                                                               'start': start, 'end': end})
                Pp = cache[(flt, lab)]
                X = _rand_X(rng, path, 0.5)
                X['hrdInv'] = bool(rng.random() < 0.75)
                if path == 'mag' and subs is None:
                    subs = T0._hrd_ref_subbars(Pp)
                n_tr += one(Pp, X, subs if path == 'mag' else None, '%s %s %s/%s' % (pair, tf, flt, lab))
            _p('  (b) %s %-3s %s: %d settings, %d trades compared (%.1fs)' % (pair, tf, path, n_per, n_tr, time.time() - t0))
    _p('  exit kinds compared: %s; trades of inverted runs: %d'
       % (', '.join('%s %d' % kv for kv in sorted(kinds.items())), n_inv_tr))
    return ok_all and n_inv_tr > 0 and all(kinds.get(k_, 0) > 0 for k_ in ('sl', 'tp', 'reverse', 'blocked_close', 'time',
                                                                            'hybrid', 'trail'))


# ---------------------------------------------------------------------------------------------
# R6: speed
# ---------------------------------------------------------------------------------------------
def test_R6_speed():
    """R6: the kernel stays fast. BTC 1 (about 1.04 M bars), filter off, path tv: the same 12
    settings (the defaults and 11 trail settings) timed on the pre-change kernel, the changed
    kernel with the option off, and with it on (5 interleaved passes, the best of each); BTC 60
    mag, one setting, option off / on. Passes when the changed kernel (option off or on) takes at
    most 1.5 x the pre-change time per setting (+ 2 ms)."""
    pre = _load_pre()
    Pn = hrd.prepare('BTC', '1', {'fgfOn': False})
    Po = pre.prepare('BTC', '1', {'fgfOn': False})
    rng = np.random.default_rng(6)
    sets = [dict()] + [dict(trailOn=True, trailAct=float(rng.choice(ACTS)), trailOff=float(rng.choice(OFFS)),
                            InpExitCandles=int(rng.choice([5, 20, 100])), InpTpPct=float(rng.choice([4.0, 0.0])))
                       for _ in range(11)]
    for X in sets[:2]:                         # compile / load
        pre.simulate(Po, X)
        hrd.simulate(Pn, X)
        hrd.simulate(Pn, dict(X, hrdInv=True))

    fns = [lambda X: pre.simulate(Po, X), lambda X: hrd.simulate(Pn, X),
           lambda X: hrd.simulate(Pn, dict(X, hrdInv=True))]
    best = [1e9, 1e9, 1e9]
    for _ in range(5):                         # interleaved, so that a busy moment hits all three
        for j, fn in enumerate(fns):
            t0 = time.time()
            for X in sets:
                fn(X)
            best[j] = min(best[j], (time.time() - t0) / len(sets))
    t_pre, t_off, t_on = best
    _p('  BTC 1 tv (%d bars), per setting: pre-change %.4fs, changed option off %.4fs (x%.2f), option on %.4fs (x%.2f)'
       % (Pn['n'], t_pre, t_off, t_off / t_pre, t_on, t_on / t_pre))
    P60 = hrd.prepare('BTC', '60', {'fgfOn': False})
    hrd.simulate(P60, dict(path='mag'))
    t0 = time.time()
    for _ in range(20):
        hrd.simulate(P60, dict(path='mag'))
    t_m0 = (time.time() - t0) / 20
    t0 = time.time()
    for _ in range(20):
        hrd.simulate(P60, dict(path='mag', hrdInv=True))
    t_m1 = (time.time() - t0) / 20
    _p('  BTC 60 mag (%d chart bars, %d sub-bars), per setting: option off %.4fs, on %.4fs'
       % (P60['n'], len(P60['sub'][1]), t_m0, t_m1))
    return t_off <= 1.5 * t_pre + 0.002 and t_on <= 1.5 * t_pre + 0.002


# ---------------------------------------------------------------------------------------------
# R7: the option through the public entry points; the public trade list reports the REAL side
# (added by the sceptic review: the tests above switch the option on only as simulate(P,
# {'hrdInv': True}) and read the kernel arrays)
# ---------------------------------------------------------------------------------------------
def test_R7_public_entry_points_real_side():
    """R7: the option switched ON through every public entry point, and the REAL side in the
    public results. BTC 60, XAU 240, BTC 240, XAU 60 (full windows) x filter off / on x 5 parameter
    sets (defaults; cost ours + path mag; Reverse Trading; Trade Direction Buy Only; Sell Only with
    blkClose off).
    (a) hrd.run(.., {'inv': True}) = hrd.run(.., {'hrdInv': True}) = prepare() WITHOUT the option +
        simulate(P, {'inv': True}) = simulate(P, {'hrdInv': True}): the same trade list, summary
        and kernel outputs, and not those of the run without the option; hrd.summary_fast (the
        sweep's summary) gives run()'s numbers; another spelling of the option is refused.
    (b) in the DataFrame of hrd.run: every dir -1 row (a real sell) was ordered on a candle with a
        LONG signal the gate allows, every dir +1 row on an allowed SHORT signal; pnl_gross = dir x
        qty x (exit_px - entry_px); a sell has sl_px above and tp_px below the signal close, a buy
        the other way round. Summary: short = the LONG-signal entries (raw_long - blocked_long,
        less an order of the last candle), long = the SHORT-signal entries; raw_long / raw_short
        = the candles with a LONG / SHORT signal while the REAL position is >= 0 / <= 0 and the
        real side (sell / buy) is allowed by Trade Direction; blocked_* = those the gate refuses
        (buyOk for a LONG signal, sellOk for a SHORT signal)."""
    ok_all = True
    n_runs = n_tr = n_sell = n_buy = 0
    sets = ({}, {'cost': 'ours', 'path': 'mag'}, {'reverse': True}, {'InpTradeDirection': 'Buy Only'},
            {'InpTradeDirection': 'Sell Only', 'blkClose': False})
    for pair, tf in (('BTC', '60'), ('XAU', '240'), ('BTC', '240'), ('XAU', '60')):
        cell_bad = 0
        for flt in ('off', 'on'):
            for extra in sets:
                base = dict(extra, fgfOn=(flt == 'on'))
                msgs = []
                tr_a, s_a = hrd.run(pair, tf, dict(base, inv=True))
                tr_h, s_h = hrd.run(pair, tf, dict(base, hrdInv=True))
                tr_n, _ = hrd.run(pair, tf, base)
                Pp = hrd.prepare(pair, tf, base)                 # prepared WITHOUT the option
                R = hrd.simulate(Pp, {'inv': True}, full=True)
                R2 = hrd.simulate(Pp, {'hrdInv': True}, full=True)
                # ---- (a)
                if not (tr_a.equals(tr_h) and tr_a.equals(hrd.trades_frame(Pp, R)) and not _diff_R(R, R2)
                        and set(s_a) == set(s_h) and all(_same_val(s_a[k], s_h[k]) for k in s_a)):
                    msgs.append('(a) inv / hrdInv / run / simulate do not agree')
                if len(tr_a) == 0 or tr_a.equals(tr_n):
                    msgs.append('(a) the option changes nothing (or no trades)')
                for k, v in hrd.summary_fast(Pp, R).items():
                    ref = s_a['exits'][k[5:]] if k.startswith('exit_') else s_a.get(k, v)
                    if not _same_val(ref, v):
                        msgs.append('(a) summary_fast %s %r, run %r' % (k, v, ref))
                try:
                    hrd.simulate(Pp, {'inverted': True})
                    msgs.append('(a) an unknown spelling of the option is accepted')
                except ValueError:
                    pass
                # ---- (b)
                c = Pp['c']
                L, S, bok, sok = Pp['long_sig'], Pp['short_sig'], Pp['buy_ok'], Pp['sell_ok']
                d = tr_a['dir'].to_numpy()
                sk = tr_a['signal_bar'].to_numpy() - Pp['w0']
                sell = d < 0
                buy = d > 0
                if not ((sell | buy).all() and (L[sk[sell]] & bok[sk[sell]]).all() and (S[sk[buy]] & sok[sk[buy]]).all()):
                    msgs.append('(b) side of a trade vs its signal / gate')
                g = d * tr_a['qty'].to_numpy() * (tr_a['exit_px'].to_numpy() - tr_a['entry_px'].to_numpy())
                if not np.allclose(tr_a['pnl_gross'].to_numpy(), g, rtol=1e-12, atol=1e-9):
                    msgs.append('(b) pnl_gross is not that of the side reported')
                slp, tpp = tr_a['sl_px'].to_numpy(), tr_a['tp_px'].to_numpy()
                if not ((slp[sell] > c[sk[sell]]).all() and (tpp[sell] < c[sk[sell]]).all()
                        and (slp[buy] < c[sk[buy]]).all() and (tpp[buy] > c[sk[buy]]).all()):
                    msgs.append('(b) SL / TP side')
                go_l = int((R['want_l'] & ~R['blk_l'])[:-1].sum())
                go_s = int((R['want_s'] & ~R['blk_s'])[:-1].sum())
                if not (s_a['short'] == int(sell.sum()) == go_l and s_a['long'] == int(buy.sum()) == go_s):
                    msgs.append('(b) long / short counts: summary %d / %d, entries from SHORT / LONG signals %d / %d'
                                % (s_a['long'], s_a['short'], go_s, go_l))
                td = base.get('InpTradeDirection', 'Both')
                sells_ok = td in ('Both', 'Sell Only')
                buys_ok = td in ('Both', 'Buy Only')
                pos = R['pos']
                wl = L & (pos >= 0) & sells_ok
                ws = S & (pos <= 0) & buys_ok
                if not (np.array_equal(R['want_l'], wl) and np.array_equal(R['want_s'], ws)
                        and s_a['raw_long'] == int(wl.sum()) and s_a['raw_short'] == int(ws.sum())
                        and s_a['blocked_long'] == int((wl & ~bok).sum()) and s_a['blocked_short'] == int((ws & ~sok).sum())):
                    msgs.append('(b) raw / blocked counts are not the signal side read on the real position')
                if td == 'Buy Only' and sell.any() or td == 'Sell Only' and buy.any():
                    msgs.append('(b) Trade Direction %s' % td)
                n_runs += 1
                n_tr += len(d)
                n_sell += int(sell.sum())
                n_buy += int(buy.sum())
                if msgs:
                    ok_all = False
                    cell_bad += 1
                    _p('  FAIL %s %s filter %s %r: %s' % (pair, tf, flt, extra, '; '.join(msgs[:4])))
        _p('  %s %-3s: %d settings, %s' % (pair, tf, 2 * len(sets), 'all hold' if not cell_bad else '%d FAIL' % cell_bad))
        hrd._SIG.clear()
        hrd._PERM.clear()
    _p('  total: %d inverted runs through run() and simulate(), %d trades (%d real sells, %d real buys)'
       % (n_runs, n_tr, n_sell, n_buy))
    return ok_all and n_sell > 0 and n_buy > 0


# ---------------------------------------------------------------------------------------------
def main(argv):
    flt = [a for a in argv if not a.startswith('-')]
    names = sorted(k for k, v in globals().items() if k.startswith('test_') and callable(v))
    if flt:
        names = [k for k in names if any(f in k for f in flt)]
    if not names:
        _p('no tests match %s' % flt)
        return 2
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
