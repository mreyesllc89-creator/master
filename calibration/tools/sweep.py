"""Parallel parameter sweeps for the RegimeTrend replica.

A job = (indicator params dict, EA overrides dict). Every job is evaluated on
the in-sample window and the out-of-sample window separately (compounding
restarts in each window), so OOS numbers are honest.
"""
import os, sys, time, itertools, json
import numpy as np
import pandas as pd
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rt_model as rt

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
YEARS = list(range(2011, 2019))
IS_FROM, IS_TO = "2011-01-01", "2017-01-01"
OOS_FROM, OOS_TO = "2017-01-01", "2019-01-01"

_BT = None


def _epoch(s):
    return int(np.datetime64(s).astype("datetime64[s]").astype(np.int64))


def _init(years, offset_h, dst):
    global _BT
    m1 = rt.load_m1(DATA, years)
    _BT = rt.Backtester(rt.Market(m1, offset_h, dst))


def _years_between(a, b):
    return (_epoch(b) - _epoch(a)) / 86400.0 / 365.25


def evaluate(job):
    ind, ea_over, windows = job
    ea = rt.ea_params(**ea_over)
    row = dict(ind)
    row.update({f"ea_{k}": v for k, v in ea_over.items()})
    for name, (a, b) in windows.items():
        try:
            stats, trades, eq = _BT.run(ind, ea, t_from=_epoch(a), t_to=_epoch(b))
            s = rt.summarize(stats, trades, eq, ea[rt.EA_IDX["start_balance"]], _years_between(a, b))
        except Exception as e:  # pragma: no cover
            s = dict(net=np.nan, error=str(e))
        for k, v in s.items():
            row[f"{name}_{k}"] = v
    return row


def run_jobs(jobs, out_csv, years=YEARS, offset_h=2, dst="US", procs=4, chunk=20, tag=""):
    t0 = time.time()
    rows = []
    with Pool(procs, initializer=_init, initargs=(years, offset_h, dst)) as pool:
        for k, row in enumerate(pool.imap_unordered(evaluate, jobs, chunksize=chunk)):
            rows.append(row)
            if (k + 1) % 500 == 0:
                print(f"[{tag}] {k+1}/{len(jobs)} {time.time()-t0:.0f}s", flush=True)
                pd.DataFrame(rows).to_csv(out_csv, index=False)
    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    print(f"[{tag}] done {len(jobs)} jobs in {time.time()-t0:.0f}s -> {out_csv}", flush=True)
    return df


def run_jobs_custom(jobs, out_csv, fn, years=YEARS, offset_h=2, dst="US", procs=4, chunk=20, tag=""):
    """Like run_jobs but with a custom per-job function (must be picklable: module-level)."""
    t0 = time.time()
    rows = []
    with Pool(procs, initializer=_init, initargs=(years, offset_h, dst)) as pool:
        for k, row in enumerate(pool.imap_unordered(fn, jobs, chunksize=chunk)):
            rows.append(row)
            if (k + 1) % 500 == 0:
                print(f"[{tag}] {k+1}/{len(jobs)} {time.time()-t0:.0f}s", flush=True)
                pd.DataFrame(rows).to_csv(out_csv, index=False)
    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    print(f"[{tag}] done {len(jobs)} jobs in {time.time()-t0:.0f}s -> {out_csv}", flush=True)
    return df


def evaluate_labeled(job):
    """job = (ind, ea_over_with_optional_'variant', windows); keeps the label in the row."""
    ind, ea, w = job
    ea = dict(ea)
    label = ea.pop("variant", "")
    row = evaluate((ind, ea, w))
    row["variant"] = label
    return row


def grid(**axes):
    keys = list(axes)
    for vals in itertools.product(*[axes[k] for k in keys]):
        yield dict(zip(keys, vals))


def make_jobs(ind_grid, ea_grid, windows):
    jobs = []
    for ind_over in ind_grid:
        ind = dict(rt.IND_DEFAULTS); ind.update(ind_over)
        for ea_over in ea_grid:
            jobs.append((ind, dict(ea_over), windows))
    return jobs


DEFAULT_WINDOWS = {"is": (IS_FROM, IS_TO), "oos": (OOS_FROM, OOS_TO), "all": (IS_FROM, OOS_TO)}
