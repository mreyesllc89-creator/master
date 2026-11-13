"""Stage 1: joint random search per symbol / timeframe, in-sample scored, out-of-sample recorded.

usage: python -I sweep.py SYMBOL TF N [spread_model]
writes results/sweep_<SYMBOL>_<TF>.csv
"""
import json
import multiprocessing as mp
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
from data import load_bars, with_spread
from engine import backtest
from params import resolve
from space import sample

DATA = os.environ.get("DP_DATA", "/tmp/claude-0/-home-user-master/5fd8d858-05df-5949-bac4-7341515d4eed/scratchpad/data/m1")
CACHE = os.environ.get("DP_CACHE", "/tmp/claude-0/-home-user-master/5fd8d858-05df-5949-bac4-7341515d4eed/scratchpad/cache")
RESULTS = os.path.join(os.path.dirname(__file__), "..", "results")
IS_YEARS = {"XAUUSD": (2011, 2015), "BTCUSD": (2015, 2017)}
CAPITAL = 10000.0

G = {}


def rstats(r, pnl):
    n = len(r)
    if n < 2:
        return dict(n=n, avg_r=0.0, tstat=0.0, pf=0.0, win=0.0, net=float(pnl.sum()) if n else 0.0)
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    sd = r.std()
    return dict(n=n, avg_r=float(r.mean()), tstat=float(r.mean() / sd * np.sqrt(n)) if sd > 0 else 0.0,
                pf=float(gp / gl) if gl > 0 else 99.0, win=float((pnl > 0).mean() * 100), net=float(pnl.sum()))


def equity_stats(pnl):
    if len(pnl) == 0:
        return dict(ret=0.0, dd=0.0)
    eq = CAPITAL + np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[CAPITAL], eq]))[1:]
    return dict(ret=float(100 * (eq[-1] / CAPITAL - 1)), dd=float(100 * ((peak - eq) / peak).max()))


def evaluate(cfg, symbol, tf, segs):
    """segs: [(name, bars)] with the long history first and the 2026 export second."""
    P = resolve(cfg, symbol, tf, CAPITAL)
    name, bars = segs[0]
    tr = backtest(bars, P)
    yrs = bars["year"][tr["o"]]
    lo, hi = IS_YEARS[symbol]
    m_is = (yrs >= lo) & (yrs <= hi)
    out = {}
    for tag, m in (("is", m_is), ("oos", ~m_is), ("all", np.ones(len(yrs), bool))):
        for k, v in rstats(tr["r"][m], tr["pnl"][m]).items():
            out[f"{tag}_{k}"] = v
    for k, v in equity_stats(tr["pnl"]).items():
        out[f"all_{k}"] = v
    for y in np.unique(yrs):
        out[f"y{int(y)}"] = float(tr["r"][yrs == y].mean()) if (yrs == y).any() else 0.0
    out["years_pos"] = int(sum(1 for y in np.unique(yrs) if tr["r"][yrs == y].sum() > 0))
    out["years_n"] = int(len(np.unique(yrs)))
    if len(segs) > 1:
        tr2 = backtest(segs[1][1], P)
        for k, v in rstats(tr2["r"], tr2["pnl"]).items():
            out[f"x26_{k}"] = v
        for k, v in equity_stats(tr2["pnl"]).items():
            out[f"x26_{k}"] = v
    return out


def _init(symbol, tf, model):
    G["segs"] = [(n, with_spread(b, symbol, model)) for n, b in load_bars(DATA, symbol, tf, CACHE)]
    G["symbol"] = symbol; G["tf"] = tf


def _work(args):
    i, cfg = args
    r = evaluate(cfg, G["symbol"], G["tf"], G["segs"])
    r["id"] = i; r["cfg"] = json.dumps(cfg, sort_keys=True)
    return r


if __name__ == "__main__":
    symbol, tf, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    model = sys.argv[4] if len(sys.argv) > 4 else "modern"
    os.makedirs(RESULTS, exist_ok=True)
    rng = random.Random(f"{symbol}-{tf}-{model}")
    jobs = [(i, sample(rng)) for i in range(n)]
    # always include the shipped preset and its un-inverted twin
    jobs.append((n, {"presetMode": "XAUUSD 5m"}))
    jobs.append((n + 1, {"presetMode": "XAUUSD 5m", "tradeOriginalDirection": True}))
    t0 = time.time()
    with mp.Pool(os.cpu_count(), initializer=_init, initargs=(symbol, tf, model)) as pool:
        rows = []
        for k, r in enumerate(pool.imap_unordered(_work, jobs, chunksize=8)):
            rows.append(r)
            if k % 500 == 0:
                print(f"{symbol} M{tf} {k}/{len(jobs)} {time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(rows).sort_values("is_tstat", ascending=False)
    df.to_csv(os.path.join(RESULTS, f"sweep_{symbol}_{tf}_{model}.csv"), index=False)
    print(f"done {symbol} M{tf} {len(df)} rows in {time.time()-t0:.0f}s")
