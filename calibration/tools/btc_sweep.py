"""Parallel sweeps for the BTCSignalFlow replica (same shape as sweep.py)."""
import os, sys, time, itertools
import numpy as np
import pandas as pd
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rt_model as rt, btc_model as bm

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
YEARS = [2015, 2016, 2017, 2018, 2019]
IS_FROM, IS_TO = "2015-01-01", "2018-07-01"
OOS_FROM, OOS_TO = "2018-07-01", "2020-01-01"
DEFAULT_WINDOWS = {"is": (IS_FROM, IS_TO), "oos": (OOS_FROM, OOS_TO), "all": (IS_FROM, OOS_TO)}
_BT = None


def _epoch(s):
    return int(np.datetime64(s).astype("datetime64[s]").astype(np.int64))


def _years_between(a, b):
    return (_epoch(b) - _epoch(a)) / 86400.0 / 365.25


def _init(years):
    global _BT
    m1 = rt.load_m1(DATA, years, "btcusd")
    _BT = bm.BtcBacktester(rt.Market(m1))


def evaluate(job):
    sig, ea_over, windows = job
    ea_over = dict(ea_over)
    label = ea_over.pop("variant", "")
    ea = bm.ea_params(**ea_over)
    row = dict(sig); row.update({f"ea_{k}": v for k, v in ea_over.items()}); row["variant"] = label
    for name, (a, b) in windows.items():
        try:
            stats, trades, eq = _BT.run(sig, ea, t_from=_epoch(a), t_to=_epoch(b))
            s = bm.summarize(stats, trades, eq, ea[bm.EA_IDX["start_balance"]], _years_between(a, b))
        except Exception as e:  # pragma: no cover
            s = dict(net=np.nan, error=str(e))
        for k, v in s.items():
            row[f"{name}_{k}"] = v
    return row


def run_jobs(jobs, out_csv, years=YEARS, procs=4, chunk=10, tag=""):
    t0 = time.time(); rows = []
    with Pool(procs, initializer=_init, initargs=(years,)) as pool:
        for k, row in enumerate(pool.imap_unordered(evaluate, jobs, chunksize=chunk)):
            rows.append(row)
            if (k + 1) % 1000 == 0:
                print(f"[{tag}] {k+1}/{len(jobs)} {time.time()-t0:.0f}s", flush=True)
                pd.DataFrame(rows).to_csv(out_csv, index=False)
    df = pd.DataFrame(rows); df.to_csv(out_csv, index=False)
    print(f"[{tag}] done {len(jobs)} jobs in {time.time()-t0:.0f}s -> {out_csv}", flush=True)
    return df


def grid(**axes):
    keys = list(axes)
    for vals in itertools.product(*[axes[k] for k in keys]):
        yield dict(zip(keys, vals))


def make_jobs(sig_grid, ea_grid, windows=DEFAULT_WINDOWS):
    jobs = []
    for s in sig_grid:
        sig = dict(bm.SIG_DEFAULTS); sig.update(s)
        for e in ea_grid:
            jobs.append((sig, dict(e), windows))
    return jobs


def signal_grid(tfs=("M15", "M30", "H1", "H4")):
    """Per-method grid over the signal inputs that the method actually uses."""
    out = []
    for tf in tfs:
        for p in grid(pullback_ema=[10, 20, 50]):
            out.append(dict(chart_tf=tf, method=0, **p))
        for p in grid(length=[10, 20, 30, 50], clearance=[0.0, 0.2, 0.5]):
            out.append(dict(chart_tf=tf, method=1, **p))
        for p in grid(length=[10, 20, 30, 50, 100], efficiency=[0.10, 0.20, 0.30, 0.40], clearance=[0.0, 0.2, 0.5]):
            out.append(dict(chart_tf=tf, method=2, **p))
        for p in grid(efficiency=[0.10, 0.20, 0.30, 0.40]):
            out.append(dict(chart_tf=tf, method=3, **p))
        for p in grid(length=[7, 14, 30, 60, 120]):
            out.append(dict(chart_tf=tf, method=4, **p))
        for p in grid(length=[10, 20, 30, 50, 100], exit_bars=[5, 10, 20], clearance=[0.0, 0.2, 0.5]):
            out.append(dict(chart_tf=tf, method=5, **p))
    return out
