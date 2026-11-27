"""sweep.py: trailing-exit sweep of XPW v2.8 (trailing-TP) +/- the FlashGold Direction Filter.

Usage: python3 -I sweep.py PAIR TF [TF ...] [--paths tv,mag] [--labels normal,rev] [--workers 3]

For each TF: loads (or builds and caches) sig / perm on run_tf.WINDOWS[PAIR] and, for labels
"rev", the sig with XPW's "Reverse every label" on (cached too; perm is the same), prepares the
engine arrays for every (labels, filter off / on) and the 1-minute sub-bars (path mag), compiles
the kernels, then forks at most 3 workers that run the 1380 settings of sweep_core.grid() for
every (filter, path, labels) and writes out/sweep_<PAIR>_<TF>.parquet: one row per (filter, path,
labels, setting) with pair, tf, filter, path, labels, tag, trailOn, trailUnit, trailAct, trailOff,
slOn, slDist and tv0_* / cost_* / stress_* metrics (sweep_core.METRIC_COLS, cost modes
sweep_core.MODES). Chart "1": mag == tv by definition, so only tv runs and its rows are copied
with path "mag". Prints progress, timing per TF, and the worker-seconds of each (path, labels,
filter) pass.
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
import sweep_core as sc   # noqa: E402
import run_tf             # noqa: E402

MAX_WORKERS = 3
CFG_COLS = ('tag', 'trailOn', 'trailUnit', 'trailAct', 'trailOff', 'slOn', 'slDist')
FILTERS = ('off', 'on')

_G: dict = {}            # shared with forked workers (copy-on-write)


def _work(task):
    lab, flt, path, i0, i1 = task
    t0 = time.time()
    P = _G['P'][(lab, flt)]
    G = _G['G']
    pair, start, end = _G['pair'], _G['start'], _G['end']
    out = []
    for i in range(i0, i1):
        R = sc.run_cfg(P, G[i], path)
        m = sc.metrics_fast(pair, R, P['t_close'], start, end)
        out.append((lab, flt, path, i, m))
    return out, (path, lab, flt), time.time() - t0


def _row(pair, tf, flt, path, lab, cfg, m):
    r = {'pair': pair, 'tf': tf, 'filter': flt, 'path': path, 'labels': lab}
    for k in CFG_COLS:
        r[k] = cfg[k]
    for md in sc.MODES:
        mm = m[md]
        for k in sc.METRIC_COLS:
            r[md + '_' + k] = mm[k]
    return r


def run_tf_sweep(pair, tf, paths, workers, out_dir=None, chunk=None, labels=sc.LABELS):
    tf = str(tf)
    labels = tuple(lab for lab in sc.LABELS if lab in labels)
    if not labels:
        raise ValueError('no labels')
    t0 = time.time()
    start, end = run_tf.WINDOWS[pair]
    sc.check_mag_sync()
    sig, perm = sc.load_inputs(pair, tf)
    sigs = {'normal': sig}
    if 'rev' in labels:
        sigs['rev'] = sc.load_sig(pair, tf, 'rev')
    P = {(lab, flt): sc.prep(pair, tf, sigs[lab], perm, flt == 'on') for lab in labels for flt in FILTERS}
    del sig, sigs, perm
    rows0 = P[(labels[0], 'off')]['rows']
    for key, Pk in P.items():
        if not np.array_equal(Pk['rows'], rows0) or not np.array_equal(Pk['t_close'], P[(labels[0], 'off')]['t_close']):
            raise ValueError('%s %s %s: chart rows differ between labels / filters' % (pair, tf, key))
    run_paths = []
    if 'tv' in paths or ('mag' in paths and tf == '1'):     # chart "1": mag is a copy of tv
        run_paths.append('tv')
    if 'mag' in paths and tf != '1':
        run_paths.append('mag')
        tsb = time.time()
        sub = sc.sub_bars(pair, tf, rows0)
        for Pk in P.values():
            Pk['sub'] = sub
        print('  sub-bars %s %s: %d chart bars, %d 1-minute bars (%.1fs)'
              % (pair, tf, len(sub[0]) - 1, len(sub[1]), time.time() - tsb), flush=True)
    G = sc.grid()
    sc.warmup()                                   # compile before forking
    if 'mag' in run_paths:
        for Pk in P.values():
            sc.check_mag_equiv(Pk)                # _run_mag still follows engine._run's step 1
    _G.clear()
    _G.update(P=P, G=G, pair=pair, start=start, end=end)
    t_prep = time.time() - t0
    nb = len(rows0)
    if chunk is None:
        # ~ 15 chunks per worker per (labels, filter, path), at least 4 settings each
        chunk = max(4, -(-len(G) // (15 * max(workers, 1))))
    tasks = [(lab, flt, path, i, min(i + chunk, len(G)))
             for path in run_paths for lab in labels for flt in FILTERS for i in range(0, len(G), chunk)]
    total = sum(t[4] - t[3] for t in tasks)
    print('  %s %s: %d bars, %d runs (%s x labels %s x filter off/on x %d settings), %d workers, prep %.1fs'
          % (pair, tf, nb, total, '/'.join(run_paths), '/'.join(labels), len(G), workers, t_prep), flush=True)
    res = {}
    busy = {}
    t1 = time.time()
    done = 0
    next_report = 0.1

    def collect(result):
        nonlocal done, next_report
        chunk_out, grp, dt = result
        busy[grp] = busy.get(grp, 0.0) + dt
        for lab, flt, path, i, m in chunk_out:
            res[(lab, flt, path, i)] = m
        done += len(chunk_out)
        if done / total >= next_report or done == total:
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
        for path in ('tv', 'mag'):
            if path not in paths:
                continue
            src = 'tv' if (path == 'mag' and tf == '1') else path
            for lab in labels:
                for i, cfg in enumerate(G):
                    rows.append(_row(pair, tf, flt, path, lab, cfg, res[(lab, flt, src, i)]))
    df = pd.DataFrame(rows)
    for md in sc.MODES:
        for k in sc.METRIC_COLS:
            c = md + '_' + k
            df[c] = df[c].astype(np.int64 if k in sc.INT_COLS else np.float64)
    out_dir = out_dir or os.path.join(W, 'out')
    os.makedirs(out_dir, exist_ok=True)
    path_out = os.path.join(out_dir, 'sweep_%s_%s.parquet' % (pair, tf))
    tmp = path_out + '.tmp%d' % os.getpid()
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path_out)
    el = time.time() - t0
    for grp in sorted(busy):
        print('    pass %s labels=%-6s filter=%-3s: %.1f worker-s (%.4fs per setting)'
              % (grp[0], grp[1], grp[2], busy[grp], busy[grp] / len(G)), flush=True)
    print('  %s %s done: %d rows -> %s | prep %.1fs, runs %.1fs (%.4fs per run per worker), total %.1fs'
          % (pair, tf, len(df), path_out, t_prep, t_run, t_run * max(workers, 1) / max(total, 1), el),
          flush=True)
    return df, el


def main(argv=None):
    ap = argparse.ArgumentParser(description='trailing-exit sweep')
    ap.add_argument('pair', choices=sc.PAIRS)
    ap.add_argument('tfs', nargs='+')
    ap.add_argument('--paths', default='tv,mag')
    ap.add_argument('--labels', default=','.join(sc.LABELS))
    ap.add_argument('--workers', type=int, default=MAX_WORKERS)
    a = ap.parse_args(argv)
    paths = [p.strip() for p in a.paths.split(',') if p.strip()]
    for p in paths:
        if p not in ('tv', 'mag'):
            ap.error('unknown path %r' % p)
    labels = [x.strip() for x in a.labels.split(',') if x.strip()]
    if not labels:
        ap.error('--labels is empty')
    for x in labels:
        if x not in sc.LABELS:
            ap.error('unknown labels %r (one of %s)' % (x, ', '.join(sc.LABELS)))
    for tf in a.tfs:
        if tf not in sc.TFS:
            ap.error('unknown TF %r (one of %s)' % (tf, ', '.join(sc.TFS)))
    workers = max(1, min(int(a.workers), MAX_WORKERS))
    if workers != a.workers:
        print('workers capped at %d' % workers, flush=True)
    t0 = time.time()
    for tf in a.tfs:
        print('== %s %s ==' % (a.pair, tf), flush=True)
        run_tf_sweep(a.pair, tf, paths, workers, labels=labels)
    print('all done in %.1fs' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
