#!/usr/bin/env python3
"""
Wide calibration search for the XLZC bearish EA (v1.1 inputs).

Extends xlzc_backtest.py with:
  * more trigger/HTF pairs (M1, M2, M3, M5 triggers; M5..H1 bias)
  * TP_LookbackBars: the TP liquidity pool may be searched further back than the SL structure
  * TP_FallbackRR: if no pool pays MinRewardRisk, use a fixed RR target instead of skipping
  * finer session windows (broker server time, see xlzc_backtest.py)

Robustness-first selection: the sample is cut into three periods
(2025-H1, 2025-H2, 2026 Jan-May). A configuration is only "robust" if it is
profitable in all three, and it is ranked by its WORST period PF, not by the
total. Neighbour stability is checked afterwards.

Usage: python3 xlzc_calibrate.py <data_dir> <out_dir>
"""
import itertools
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

import xlzc_backtest as B

PERIODS = [("2025H1", "2025-01-01", "2025-07-01"),
           ("2025H2", "2025-07-01", "2026-01-01"),
           ("2026", "2026-01-01", "2027-01-01")]
SESSIONS = {"asia_00-06": (0, 360), "london_07-11": (420, 660), "ny_12-1630": (720, 990),
            "ldn_ny_07-20": (420, 1200), "all_day": (0, 1440)}
PAIRS = ["M1/M5", "M1/M15", "M1/M30", "M1/H1",
         "M2/M15", "M2/M30", "M2/H1",
         "M3/M15", "M3/M30", "M3/H1",
         "M5/M15", "M5/M30", "M5/H1"]
# every-timeframe extension: triggers up to H1, trend filters up to D1 (filter >= 3x trigger)
ALL_TRIGGERS = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]
ALL_FILTERS = ["M15", "M30", "H1", "H2", "H4", "D1"]
ALL_PAIRS = [f"{t}/{h}" for t in ALL_TRIGGERS for h in ALL_FILTERS
             if B.TF_MIN[h] >= 3 * B.TF_MIN[t]]
if os.environ.get("XLZC_PAIRS") == "new":
    PAIRS = [p for p in ALL_PAIRS if p not in PAIRS]
elif os.environ.get("XLZC_PAIRS"):
    PAIRS = os.environ["XLZC_PAIRS"].split(",")
NS = [15, 25, 40]
SS = [2, 3, 4]
NT_MAX = 120


def sl_structure(t, sig, N, S, sh):
    hi = t["high"].values; cl = t["close"].values; op = t["open"].values
    out = []
    for e in sig["entry_bar"].values:
        if e - N - S < 0:
            out.append(None); continue
        mo = op[e]
        sweep = -1
        for j in range(1, N + 1):
            aj = e - j
            for i in range(j + S + 1, N + 1):
                ai = e - i
                if sh[ai] and hi[aj] > hi[ai] and cl[aj] < hi[ai]:
                    sweep = j; break
            if sweep > 0:
                break
        sb = -1
        if sweep > 0 and hi[e - sweep] > mo:
            sb = sweep
        else:
            for i in range(1 + S, N + 1):
                if sh[e - i] and hi[e - i] > mo:
                    sb = i; break
        if sb < 0:
            out.append(None); continue
        out.append((max(hi[e - sb:e].max(), mo), sb == sweep))
    return out


def low_pools(t, sig, S, sl_flags):
    """Swing lows below the entry open within NT_MAX bars: list of (shift, low)."""
    lo = t["low"].values; op = t["open"].values
    out = []
    for e in sig["entry_bar"].values:
        mo = op[e]
        lst = [(i, lo[e - i]) for i in range(1 + S, NT_MAX + 1)
               if e - i - S >= 0 and sl_flags[e - i] and lo[e - i] < mo]
        out.append(lst)
    return out


G = {}


def init_worker(payload):
    G.update(payload)


def run_cfg(cfg):
    pair = cfg["tf"]; trig = pair.split("/")[0]
    sig = G["sig"][pair]
    sls = G["sls"][(pair, cfg["N"], cfg["S"])]
    pools = G["pools"][(pair, cfg["S"])]
    path = G["path"]
    s0, s1 = SESSIONS[cfg["session"]]
    pt = 0.01
    # point distances scale with the trigger timeframe (sqrt) and the instrument (B.INST)
    k = B.TF_MIN[trig] ** 0.5 * B.INST["scale"]
    nt = cfg["N"] if cfg["NT"] == 0 else cfg["NT"]
    trades = []
    busy = np.datetime64("1970-01-01")
    cache = G.setdefault("cache", {})
    for n in range(len(sig["mi"])):
        if not sig["bias"][n]:
            continue
        if cfg["stoch"] == "hard" and not sig["stoch_ok"][n]:
            continue
        et = sig["et"][n]
        if et <= busy:
            continue
        tod = sig["tod"][n]
        if not (s0 <= tod < s1):
            continue
        st = sls[n]
        if st is None:
            continue
        mi = sig["mi"][n]
        if mi < 0:
            continue
        hs = path.hs[mi]
        if 2 * hs / pt > B.INST["spread_cap"]:
            continue
        entry = path.o[mi] - hs
        sl = st[0] + hs + cfg["buffer"] * k * pt
        risk = sl - entry
        rp = risk / pt
        if rp < 50 * k or rp > 1000 * k:
            continue
        tp = None
        tp_buf = cfg.get("tp_buf", 0) * k * pt       # EA TP_Buffer_Points: TP this far above the pool
        if cfg.get("zone_tol"):
            # EA v1.20 TP_ZONE: swing lows within zone_tol form one zone; TP above the zone top
            lows_nt = sorted((low for shift, low in pools[n] if shift <= nt), reverse=True)
            zones = []
            for low in lows_nt:
                if zones and zones[-1][1] - low <= cfg["zone_tol"] * k * pt:
                    zones[-1][1] = low; zones[-1][2] += 1
                else:
                    zones.append([low, low, 1])
            for top, _bot, cnt in zones:
                if cnt < cfg.get("zone_min", 1):
                    continue
                c = top - hs + tp_buf
                if entry - c > 0 and entry - c >= cfg["min_rr"] * risk:
                    tp = c
                    break
        else:
            for shift, low in pools[n]:
                if shift > nt:
                    continue
                c = low - hs + tp_buf
                if entry - c > 0 and entry - c >= cfg["min_rr"] * risk:
                    if tp is None or c > tp:
                        tp = c  # nearest qualifying pool (highest low)
        if tp is None:
            if cfg["fb"] <= 0:
                continue
            tp = entry - cfg["fb"] * risk
        # trailing start / distance in gold points (scaled by k); defaults 150 / 100
        t_start, t_dist = cfg.get("trail_start", 150), cfg.get("trail_dist", 100)
        trail = (round(t_start * k) * pt, round(t_dist * k) * pt) if cfg["trail"] else None
        key = (mi, round(sl, 3), round(tp, 3), trail, trig, B.M1Path.TRAIL_MODE)
        res = cache.get(key)
        if res is None:
            res = path.simulate(mi, entry, sl, tp, trail, None)
            cache[key] = res
        xi, r = res
        busy = path.t[xi]
        trades.append((et, r))
    return cfg, trades


def seg_stats(trades):
    out = {}
    rs_all = [r for _, r in trades]
    out.update({f"all_{k}": v for k, v in B.stats(rs_all).items()})
    for name, a, b in PERIODS:
        a = np.datetime64(a); b = np.datetime64(b)
        rs = [r for t, r in trades if a <= t < b]
        s = B.stats(rs)
        out[f"{name}_trades"] = s["trades"]; out[f"{name}_pf"] = s["pf"]; out[f"{name}_net"] = s["net_r"]
    return out


def main():
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    m1, hs = B.load(data_dir)
    path = B.M1Path(m1, hs)
    sigs, sls, pools = {}, {}, {}
    for pair in PAIRS:
        trig, htf = pair.split("/")
        t, sig = B.build_signals(m1, trig, htf)
        mi = np.searchsorted(path.t, sig["entry_time"].values)
        ok = (mi < len(path.t))
        mi = np.where(ok, mi, -1)
        tol = np.timedelta64(B.TF_MIN[trig], "m")
        mi = np.where((mi >= 0) & (path.t[np.clip(mi, 0, len(path.t) - 1)] - sig["entry_time"].values <= tol), mi, -1)
        et = sig["entry_time"]
        sigs[pair] = dict(bias=sig["bias"].values, stoch_ok=sig["stoch_ok"].values,
                          et=et.values, tod=(et.dt.hour * 60 + et.dt.minute).values, mi=mi)
        for S in SS:
            shf, slf = B.swing_flags(t["high"].values, t["low"].values, S)
            pools[(pair, S)] = low_pools(t, sig, S, slf)
            for N in NS:
                sls[(pair, N, S)] = sl_structure(t, sig, N, S, shf)
        print(f"{pair}: {len(sig)} signals, {int(sig.bias.sum())} biased", flush=True)

    grid = [dict(tf=p, N=N, S=S, buffer=buf, NT=nt, min_rr=rr, fb=fb, stoch=st, session=se, trail=tr)
            for p, N, S, buf, nt, rr, fb, st, se, tr in itertools.product(
                PAIRS, NS, SS, [40, 80, 120], [0, 60, 120], [1.0, 1.5, 2.0], [0.0, 1.5],
                ["soft", "hard"], list(SESSIONS), [False, True])]
    # group by pair so the per-worker simulation cache is effective
    print(f"{len(grid)} configurations", flush=True)
    payload = dict(sig=sigs, sls=sls, pools=pools, path=path)
    rows = []
    with Pool(4, initializer=init_worker, initargs=(payload,)) as pool:
        for i, (cfg, trades) in enumerate(pool.imap(run_cfg, grid, chunksize=64)):
            row = dict(cfg); row.update(seg_stats(trades)); rows.append(row)
            if i % 10000 == 0:
                print(i, flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, "calibration_grid.csv"), index=False)
    print("done", len(df))


if __name__ == "__main__":
    main()
