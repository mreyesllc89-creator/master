"""Random search of the AMVI strategy's inputs on one chart timeframe.

usage: python sweep.py <chart_tf_minutes> <n_settings> <seed> [out_dir]

Every setting is backtested once over the search window (entries from 2023-11-01) and
reduced to monthly sums, so any split of the window (halves, thirds, single months) and any
fee level can be scored afterwards without running it again:

  net R of a month = gross R - fee_per_side x fee_units - funding R

  gross   R with slippage (1 tick on market and stop fills) and no commission
  fee_u   sum over trades of (entry price + exit price) / risk distance
  fund    funding paid (+) or received (-) by the position at Binance's 8-hourly rates, in R

The window before 2023-11-01 is NOT scored here: it is kept untouched for the final test.
"""
import hashlib
import json
import os
import sys
import time
from multiprocessing import get_context

import numpy as np
import pandas as pd

import amvi_engine as E
import bars
import space

WINDOW_START = "2023-11-01"
WINDOW_END = "2026-11-26"      # exclusive
LOAD_START = "2022-01-01"      # bars before the window are only there to warm the indicators up
BASE_FEE = 0.0005              # taker fee per side (crypto_lab hard rule 2: 0.05 % per side + funding + 1 tick)
G = {}                         # process globals shared with the forked workers


def ms(day):
    return int(pd.Timestamp(day, tz="UTC").value // 10 ** 6)


def month_index(t_ms, start_ms):
    """Calendar-month number of each time, 0 = the month of start_ms."""
    d = pd.to_datetime(np.asarray(t_ms), unit="ms")
    s = pd.Timestamp(start_ms, unit="ms")
    return np.asarray((d.year - s.year) * 12 + (d.month - s.month), dtype=np.int64)


def n_months(start_ms, end_ms):
    s, e = pd.Timestamp(start_ms, unit="ms"), pd.Timestamp(end_ms - 1, unit="ms")
    return (e.year - s.year) * 12 + (e.month - s.month) + 1


class Funding:
    """Binance BTCUSDT funding: cumulative rate at any time (position open at the funding
    timestamp pays direction x rate x notional)."""

    def __init__(self, path):
        f = pd.read_parquet(path)
        # a third of the prints are stamped a few ms after the hour: floor them to the hour
        t = f["calc_time"].to_numpy(np.int64) // 3_600_000 * 3_600_000
        r = f["last_funding_rate"].to_numpy(np.float64)
        o = np.argsort(t)
        self.t = t[o]
        self.cum = np.concatenate(([0.0], np.cumsum(r[o])))

    def paid(self, entry_t, exit_t, direction, entry_px, risk):
        """Funding cost in R per trade (positive = paid): every funding stamp T with
        entry < T <= exit, i.e. the position is open when the stamp passes."""
        a = np.searchsorted(self.t, entry_t, side="right")
        b = np.searchsorted(self.t, exit_t, side="right")
        return direction * (self.cum[b] - self.cum[a]) * entry_px / risk


def load_context(symbol="BTCUSDT", start=LOAD_START, end=WINDOW_END):
    m1 = bars.load_1m(symbol, start=start, end=end)
    mk = bars.Market(m1)
    ft = E.Features(mk)
    fpath = os.path.join(bars.DATA_DIR, f"{symbol}_funding.parquet")
    fund = Funding(fpath) if os.path.exists(fpath) else None
    return ft, fund


def precompute(ft, chart_tf):
    """Build every array the workers read, in the parent, so fork shares the memory."""
    g = space.GRID
    for tf in space.AMVI_TFS:
        for fast in g["fast"]:
            for norm in g["norm"]:
                ft.natr(tf, fast, norm)
            for slow in g["slow"]:
                ft.nvr(tf, fast, slow)
        for norm in g["norm"]:
            for sd in g["sd"]:
                ft.nsd(tf, sd, norm)
            for cr in g["cr"]:
                ft.ncr(tf, cr, norm)
        ft.idx("amvi", chart_tf, tf)
    f_all = sorted(set(space.FILTER_TFS) | {chart_tf})
    z_all = set()
    for f in f_all:
        ft.atr(f, 14)
        ft.idx("arm", chart_tf, f)
        for par in space.parent_options(f):
            z_all.add((f, par))
        for zs in space.zone_options(f):
            for z in zs:
                z_all.add((f, z))
    for f, z in sorted(z_all):
        for rsi_len, fast_len in g["tdi"]:
            ft.tdi(z, rsi_len, fast_len)
        ft.idx("zone", f, z)
    for f in f_all:
        ft.idx("arm_open", chart_tf, f)
    for n in g["exit_atr"]:
        ft.atr(chart_tf, n)
    # compile the simulator before forking
    E.run(ft, chart_tf, E.P(), start_ms=ms(WINDOW_START), end_ms=ms(WINDOW_START) + 86_400_000)


_ARMS = {}


def arms_cached(ft, p):
    k = space.filter_key(p)
    a = _ARMS.get(k)
    if a is None:
        if len(_ARMS) >= 3:
            _ARMS.pop(next(iter(_ARMS)))
        a = E.filter_arms(ft, p)
        _ARMS[k] = a
    return a


def entry_hash(tr):
    """Order-free fingerprint of a setting's entries (signal bar and side): equal for settings
    that take the same trades, used to count distinct entry sets."""
    x = (tr["sig_bar"].astype(np.uint64) * np.uint64(2) + (tr["dir"] > 0).astype(np.uint64))
    x = (x ^ (x >> np.uint64(33))) * np.uint64(0xFF51AFD7ED558CCD)
    x = (x ^ (x >> np.uint64(33))) * np.uint64(0xC4CEB9FE1A85EC53)
    return int(np.bitwise_xor.reduce(x)) if x.size else 0


def evaluate(p, ft=None, fund=None, chart_tf=None, start_ms=None, end_ms=None, full=False):
    """Backtest one setting; monthly gross R, fee units, funding R and trade counts."""
    ft = ft or G["ft"]
    fund = fund if fund is not None else G.get("fund")
    chart_tf = chart_tf or G["chart_tf"]
    start_ms = start_ms or G["start_ms"]
    end_ms = end_ms or G["end_ms"]
    ep = E.P(**space.engine_params(p))
    trig, volc, _ = E.trigger_arrays(ft, chart_tf, ep)
    zone = E.zone_array(ft, chart_tf, ep, arms_cached(ft, ep))
    tr = E.run(ft, chart_tf, ep, fee=0.0, slip_ticks=1, start_ms=start_ms, end_ms=end_ms, signals=(trig, volc, zone))
    nm = n_months(start_ms, end_ms)
    gross = np.zeros(nm, np.float32)
    feeu = np.zeros(nm, np.float32)
    fundr = np.zeros(nm, np.float32)
    cnt = np.zeros(nm, np.int32)
    n = tr["r"].size
    if n:
        keep = tr["entry_t"] >= start_ms
        for k in tr:
            tr[k] = tr[k][keep]
        n = tr["r"].size
    fu = (tr["entry_px"] + tr["exit_px"]) / tr["risk"] if n else np.zeros(0)
    fd = fund.paid(tr["entry_t"], tr["exit_t"], tr["dir"].astype(np.float64), tr["entry_px"], tr["risk"]) if (n and fund is not None) else np.zeros(n)
    if n:
        m = np.clip(month_index(tr["entry_t"], start_ms), 0, nm - 1)
        np.add.at(gross, m, tr["r"])
        np.add.at(feeu, m, fu)
        np.add.at(fundr, m, fd)
        np.add.at(cnt, m, 1)
    net = tr["r"] - BASE_FEE * fu - fd if n else np.zeros(0)
    eq = np.cumsum(net)
    dd = float((np.maximum.accumulate(np.maximum(eq, 0.0)) - eq).max()) if n else 0.0
    res = dict(gross=gross, feeu=feeu, fund=fundr, cnt=cnt, n=int(n), n_long=int((tr["dir"] > 0).sum()) if n else 0,
               wins=int((net > 0).sum()), dd=dd, h=entry_hash(tr) if n else 0,
               bars_held=float(np.mean((tr["exit_t"] - tr["entry_t"]) / (chart_tf * 60000.0))) if n else 0.0)
    if full:
        tr["fee_u"] = fu
        tr["fund_r"] = fd
        res["trades"] = tr
    return res


def _work(chunk):
    return [(i, evaluate(p)) for i, p in chunk]


def run_sweep(chart_tf, n_settings, seed, out_dir, procs=4):
    t0 = time.time()
    ft, fund = load_context()
    precompute(ft, chart_tf)
    G.update(ft=ft, fund=fund, chart_tf=chart_tf, start_ms=ms(WINDOW_START), end_ms=ms(WINDOW_END))
    rng = np.random.default_rng(seed)
    settings = [space.draw(rng, chart_tf) for _ in range(n_settings)]
    order = sorted(range(n_settings), key=lambda i: (space.filter_key(settings[i]), settings[i]["tfs"]))
    chunks = [[(i, settings[i]) for i in order[k:k + 40]] for k in range(0, n_settings, 40)]
    print(f"[{chart_tf}m] context ready in {time.time() - t0:.0f}s; {n_settings} settings, {len(chunks)} chunks", flush=True)
    nm = n_months(G["start_ms"], G["end_ms"])
    gross = np.zeros((n_settings, nm), np.float32)
    feeu = np.zeros((n_settings, nm), np.float32)
    fundr = np.zeros((n_settings, nm), np.float32)
    cnt = np.zeros((n_settings, nm), np.int32)
    meta = [None] * n_settings
    done = 0
    t1 = time.time()
    with get_context("fork").Pool(procs) as pool:
        for part in pool.imap_unordered(_work, chunks):
            for i, r in part:
                gross[i], feeu[i], fundr[i], cnt[i] = r["gross"], r["feeu"], r["fund"], r["cnt"]
                meta[i] = dict(n=r["n"], n_long=r["n_long"], wins=r["wins"], dd=r["dd"], h=r["h"], bars_held=r["bars_held"])
            done += len(part)
            if done % 2000 < 40:
                el = time.time() - t1
                print(f"[{chart_tf}m] {done}/{n_settings}  {el:.0f}s  ({el / done * 1000:.0f} ms per setting)", flush=True)
    os.makedirs(out_dir, exist_ok=True)
    tag = f"sweep_{chart_tf}m_seed{seed}"
    np.savez_compressed(os.path.join(out_dir, tag + ".npz"), gross=gross, feeu=feeu, fund=fundr, cnt=cnt,
                        h=np.array([m["h"] for m in meta], dtype=np.uint64),
                        n=np.array([m["n"] for m in meta]), n_long=np.array([m["n_long"] for m in meta]),
                        wins=np.array([m["wins"] for m in meta]), dd=np.array([m["dd"] for m in meta]),
                        bars_held=np.array([m["bars_held"] for m in meta]))
    with open(os.path.join(out_dir, tag + ".json"), "w") as f:
        json.dump(dict(chart_tf=chart_tf, seed=seed, n=n_settings, window=[WINDOW_START, WINDOW_END], base_fee=BASE_FEE,
                       settings=settings), f)
    print(f"[{chart_tf}m] done in {time.time() - t0:.0f}s -> {tag}", flush=True)


if __name__ == "__main__":
    ctf, n, seed = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    out = sys.argv[4] if len(sys.argv) > 4 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "sweeps")
    run_sweep(ctf, n, seed, out)
