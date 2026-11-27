"""sweep_apex.py: trailing take-profit sweep of ApexForge Flow Resonance + FGF
(SWEEP_AH_SPEC.md section 3), with the canonical module apex.py.

Usage: python3 -I sweep_apex.py PAIR TF [TF ...] [--workers 3] [--paths tv,mag]
                                [--labels normal,rev] [--costs tv,ours]

Grid (percent of the signal close, Pine apxTrailAct / apxTrailOff):
  activation 0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5
  offset     0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5
  + trail off, all x useTarget {True, False}  ->  394 settings
  (with the trail off the Pine keeps the target whatever useTarget says, so the two
  trail-off rows give the same result; both are kept so the grid is a full product).
Per (PAIR, TF): filter {off, on} x path {tv, mag} x labels {normal, rev} x cost {tv, ours}
(--costs tv,ours,stress adds the stressed costs). labels 'rev' = apex param reverse=True
(swap long / short signals before the gate, literal brackets: the replica's control).
For each TF: prepares signals / gate once per (labels, filter) and the 1-minute sub-bars once,
compiles, then forks at most 3 workers (copy-on-write) that simulate the settings, and writes
out/swah_apex_<PAIR>_<TF>.parquet: one row per (filter, path, labels, cost, setting) with
pair, tf, filter, path, labels, cost, setting, trailOn, trailAct, trailOff (NaN when off),
useTarget and every scalar summary field of apex.simulate (no prefix; the cost column says
which). Chart "1": mag == tv by definition (each chart bar is its own sub-bar), so only tv
runs and its rows are copied with path "mag". Rows are sorted by the key, so the file does
not depend on the worker count. Prints progress and timing per TF.
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import apex  # noqa: E402

MAX_WORKERS = 3
PAIRS = ('BTC', 'XAU')
TFS = ('1', '5', '15', '30', '60', '120', '240')
ACTS = (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
OFFS = (0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
FILTERS = ('off', 'on')
LABELS = ('normal', 'rev')
PATHS = ('tv', 'mag')
COSTS_DEFAULT = ('tv', 'ours')
KEY_COLS = ('pair', 'tf', 'filter', 'path', 'labels', 'cost', 'setting')
SET_COLS = ('trailOn', 'trailAct', 'trailOff', 'useTarget')
SUM_COLS = ('start', 'end', 'bars', 'trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'long', 'short',
            'raw_long', 'raw_short', 'blocked_long', 'blocked_short', 'half1_pct', 'half2_pct', 'exposure',
            'costs', 'final_equity', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades') \
    + tuple('exit_' + k for k in apex._KINDS) + ('avg_bars_held', 'stopped_at_fill_open')
FLOAT_COLS = {'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'half1_pct', 'half2_pct', 'exposure', 'costs',
              'final_equity', 'h1r_pct', 'h2r_pct', 'avg_bars_held'}

_G: dict = {}            # shared with forked workers (copy-on-write)


def grid():
    """The 394 exit settings, in a fixed order: for useTarget True then False, the trail-off row,
    then activation x offset."""
    G = []
    for ut in (True, False):
        G.append(dict(trailOn=False, trailAct=float('nan'), trailOff=float('nan'), useTarget=ut))
        for a in ACTS:
            for o in OFFS:
                G.append(dict(trailOn=True, trailAct=float(a), trailOff=float(o), useTarget=ut))
    return G


def exit_params(cfg, path, cost):
    X = {'trailOn': cfg['trailOn'], 'useTarget': cfg['useTarget'], 'path': path, 'cost': cost}
    if cfg['trailOn']:
        X['trailAct'] = cfg['trailAct']
        X['trailOff'] = cfg['trailOff']
    return X


def _work(task):
    lab, flt, path, cost, i0, i1 = task
    t0 = time.time()
    S = _G['S'][(lab, flt)]
    G = _G['G']
    out = []
    for i in range(i0, i1):
        _, s = apex.simulate(S, exit_params(G[i], path, cost))
        out.append(((flt, path, lab, cost, i), tuple(s[k] for k in SUM_COLS)))
    return out, (path, lab, flt, cost), time.time() - t0


def run_tf_sweep(pair, tf, workers=MAX_WORKERS, paths=PATHS, labels=LABELS, costs=COSTS_DEFAULT,
                 out_dir=None, chunk=None, verbose=True):
    tf = str(tf)
    t0 = time.time()
    S = {(lab, flt): apex.prepare(pair, tf, {'fgfOn': flt == 'on', 'reverse': lab == 'rev'})
         for lab in labels for flt in FILTERS}
    s0 = S[(labels[0], 'off')]
    for key, Sk in S.items():
        if Sk['w0'] != s0['w0'] or Sk['w1'] != s0['w1']:
            raise ValueError('%s %s %s: window rows differ' % (pair, tf, key))
    run_paths = []
    if 'tv' in paths or ('mag' in paths and tf == '1'):      # chart "1": mag is a copy of tv
        run_paths.append('tv')
    if 'mag' in paths and tf != '1':
        run_paths.append('mag')
        tsb = time.time()
        sub = apex.sub_bars(s0)
        for Sk in S.values():
            Sk['sub'] = sub
        if verbose:
            print('  sub-bars %s %s: %d chart bars, %d 1-minute bars (%.1fs)'
                  % (pair, tf, len(sub[0]) - 1, len(sub[1]), time.time() - tsb), flush=True)
    G = grid()
    for path in run_paths:                                   # compile / load the kernels before forking
        apex.simulate(s0, exit_params(G[2], path, costs[0]))
    _G.clear()
    _G.update(S=S, G=G)
    t_prep = time.time() - t0
    if chunk is None:
        chunk = max(8, -(-len(G) // (6 * max(workers, 1))))
    tasks = [(lab, flt, path, cost, i, min(i + chunk, len(G)))
             for path in run_paths for lab in labels for flt in FILTERS for cost in costs
             for i in range(0, len(G), chunk)]
    total = sum(t[5] - t[4] for t in tasks)
    if verbose:
        print('  %s %s: %d bars, %d runs (%s x labels %s x filter off/on x cost %s x %d settings), '
              '%d workers, prep %.1fs' % (pair, tf, s0['w1'] - s0['w0'], total, '/'.join(run_paths),
                                          '/'.join(labels), '/'.join(costs), len(G), workers, t_prep), flush=True)
    res = {}
    busy = {}
    t1 = time.time()
    done = 0
    next_report = 0.1

    def collect(result):
        nonlocal done, next_report
        chunk_out, grp, dt = result
        busy[grp] = busy.get(grp, 0.0) + dt
        for key, vals in chunk_out:
            res[key] = vals
        done += len(chunk_out)
        if verbose and (done / total >= next_report or done == total):
            el = time.time() - t1
            print('    %5.1f%%  %d/%d runs  %.1fs elapsed  eta %.1fs'
                  % (100.0 * done / total, done, total, el, el / done * (total - done)), flush=True)
            while next_report <= done / total:
                next_report += 0.1

    if workers <= 1:
        for t in tasks:
            collect(_work(t))
    else:
        ctx = mp.get_context('fork')
        with ctx.Pool(processes=workers) as pool:
            for result in pool.imap_unordered(_work, tasks):
                collect(result)
    t_run = time.time() - t1

    rows = []
    for flt in FILTERS:
        for path in PATHS:
            if path not in paths:
                continue
            src = 'tv' if (path == 'mag' and tf == '1') else path
            for lab in labels:
                for cost in costs:
                    for i, cfg in enumerate(G):
                        r = [pair, tf, flt, path, lab, cost, i]
                        r += [cfg[k] for k in SET_COLS]
                        r += list(res[(flt, src, lab, cost, i)])
                        rows.append(r)
    df = pd.DataFrame(rows, columns=list(KEY_COLS) + list(SET_COLS) + list(SUM_COLS))
    for k in SUM_COLS:
        df[k] = df[k].astype(np.float64 if k in FLOAT_COLS else np.int64)
    df['setting'] = df['setting'].astype(np.int64)
    df['trailOn'] = df['trailOn'].astype(bool)
    df['useTarget'] = df['useTarget'].astype(bool)
    out_dir = out_dir or os.path.join(W, 'out')
    os.makedirs(out_dir, exist_ok=True)
    path_out = os.path.join(out_dir, 'swah_apex_%s_%s.parquet' % (pair, tf))
    tmp = path_out + '.tmp%d' % os.getpid()
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path_out)
    el = time.time() - t0
    if verbose:
        for grp in sorted(busy):
            print('    pass %-3s labels=%-6s filter=%-3s cost=%-6s: %.2f worker-s (%.5fs per setting)'
                  % (grp[0], grp[1], grp[2], grp[3], busy[grp], busy[grp] / len(G)), flush=True)
        print('  %s %s done: %d rows -> %s | prep %.1fs, runs %.1fs (%.5fs per run per worker), total %.1fs'
              % (pair, tf, len(df), path_out, t_prep, t_run, t_run * max(workers, 1) / max(total, 1), el),
              flush=True)
    return df, el


def main(argv=None):
    ap = argparse.ArgumentParser(description='ApexForge + FGF trailing take-profit sweep')
    ap.add_argument('pair', choices=PAIRS)
    ap.add_argument('tfs', nargs='+')
    ap.add_argument('--workers', type=int, default=MAX_WORKERS)
    ap.add_argument('--paths', default=','.join(PATHS))
    ap.add_argument('--labels', default=','.join(LABELS))
    ap.add_argument('--costs', default=','.join(COSTS_DEFAULT))
    a = ap.parse_args(argv)

    def lst(s, allowed, what):
        v = [x.strip() for x in s.split(',') if x.strip()]
        if not v:
            ap.error('--%s is empty' % what)
        for x in v:
            if x not in allowed:
                ap.error('unknown %s %r (one of %s)' % (what, x, ', '.join(allowed)))
        return tuple(x for x in allowed if x in v)

    paths = lst(a.paths, PATHS, 'paths')
    labels = lst(a.labels, LABELS, 'labels')
    costs = lst(a.costs, apex.COSTS, 'costs')
    for tf in a.tfs:
        if tf not in TFS:
            ap.error('unknown TF %r (one of %s)' % (tf, ', '.join(TFS)))
    workers = max(1, min(int(a.workers), MAX_WORKERS))
    if workers != a.workers:
        print('workers capped at %d' % workers, flush=True)
    t0 = time.time()
    for tf in a.tfs:
        print('== apex %s %s ==' % (a.pair, tf), flush=True)
        run_tf_sweep(a.pair, tf, workers, paths, labels, costs)
    print('all done in %.1fs' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
