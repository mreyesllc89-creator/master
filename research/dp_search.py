#!/usr/bin/env python3
"""
Full-input calibration of the Danny Phantom EA (replica dp_engine.py).

Every input that changes trading is searched, plus code-level settings the EA hard-codes:
  timeframe (EA: M5 only), trade direction, zone settings, trend filter, entry mode,
  ExitMode ATR and Points, SL / TP, trailing (start / distance), breakeven, time stop,
  dead-trade exit, one-per-zone, cooldown, loss-cluster pause, cost filter (also for BTC),
  one-decision / one-flat-exit per bar, entry buffer, Sunday block, weekend / daily blackout,
  close lead, NY session, the four gold hour filters, and recalibrated blocked hours.

Selection uses 2025 only (worst half-year PF, >= MIN_TRADES per half, median over one-step
neighbours); 2026 is out of sample. Phases:
  R  random sample of the whole space
  L  coordinate refinement of the best random points, then neighbour smoothing
  H  recalibrated blocked NY hours (from 2025 trades) on the finalists
Usage: python3 dp_search.py <SYMBOL> <R|L|H> <out_dir> [n_random]
"""
import json
import os
import random
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

import dp_engine as D

MIN_TRADES = 40
HALVES = [("h1", "2025-01-01", "2025-07-01"), ("h2", "2025-07-01", "2026-01-01")]
OOS = ("oos", "2026-01-01", "2027-01-01")
SESSIONS = {"none": None, "ny_cash": (570, 960), "ny_am": (480, 720), "london_ny": (180, 720),
            "ny_day": (480, 1020), "asia": (1080, 180)}


def space(sym):
    gold = sym == "XAUUSD"
    s = dict(
        tf=[1, 2, 3, 5, 10, 15, 30], fade=[1, 0],
        zlen=[10, 20, 30, 50, 80, 120], delta=[1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0],
        min_retest=[1, 2, 3, 5, 8], max_age=[20, 50, 100, 200, 400], inval=[1, 0],
        use_ema=[1, 0], ema_len=[20, 50, 100, 200], ztrend=[0, 1], mode=[0, 1], atr_len=[7, 14, 21, 30],
        points=[0, 1],
        sl=[0.5, 0.8, 1.0, 1.2, 1.6, 2.0, 2.5, 3.0, 4.0],
        tpr=[0.0, 0.75, 1.0, 1.5, 2.0, 3.0, 4.1667, 6.0],
        sl_usd=([1, 2, 3, 5, 8, 12, 20] if gold else [25, 50, 100, 150, 250, 400, 600]),
        tp_mult=[0.0, 1.0, 1.5, 2.0, 3.0, 5.0],
        trail=[0, 1], tact=[0.5, 1.0, 2.0, 3.0, 4.0], tdst=[0.2, 0.5, 1.0, 1.5, 2.0],
        tstop=[0, 10, 20, 50, 100, 200],
        dead=[0, 1], dead_bars=[5, 10, 15, 25, 40],
        be=[0, 1], be_trig=[0.5, 1.0, 1.5, 2.0],
        opz=[1, 0], cd=[1, 0], cd_bars=[3, 10, 20],
        lc=[1, 0], lc_n=[2, 3, 5, 8], lc_pause=[6, 12, 24, 48],
        cost=[1, 0], cost_ratio=[2.0, 4.0, 6.0, 8.0],
        lim_dec=[1, 0], lim_flat=[1, 0],
        entry_buffer=[0, 30, 60, 120], sunday_block=[1, 0], weekend_blackout=[1, 0], daily_blackout=[1, 0],
        close_lead=[5, 10, 30], session=list(SESSIONS),
    )
    if gold:
        s.update(robust_hour=[1, 0], micro=[1, 0], v105=[1, 0], v1010=[1, 0])
    return s


def to_cfg(sym, p):
    """Search point -> engine config (Points mode distances in EA points of the reference tick)."""
    prof = D.GOLD_PROFILE if sym == "XAUUSD" else D.BTC_PROFILE
    c = dict(prof)
    for k, v in p.items():
        if k not in ("tf", "sl_usd", "tp_mult", "session", "block_hours"):
            c[k] = v
    for k in ("sunday_block", "weekend_blackout", "daily_blackout", "robust_hour", "micro", "v105", "v1010"):
        if k in p:
            c[k] = bool(p[k])
    c["session"] = SESSIONS[p["session"]]
    c["intrabar"] = int(os.environ.get("DP_INTRABAR", c["intrabar"]))   # 0 = live bar-close EA
    c["block_hours"] = tuple(p.get("block_hours", ()))
    mt = c["mintick"]
    c["sl_pts"] = p["sl_usd"] / mt
    c["tp_pts"] = p["sl_usd"] * p["tp_mult"] / mt
    c["tact_pts"] = p["sl_usd"] * p["tact"] / mt          # Points-mode trailing in multiples of the stop
    c["tdst_pts"] = p["sl_usd"] * p["tdst"] / mt
    return c


MK = None
SYM = None


def init(sym):
    global MK, SYM
    SYM = sym
    MK = D.Market(sym)


def pf_of(x):
    w = x[x > 0].sum(); l = -x[x < 0].sum()
    return w / l if l > 0 else (np.inf if w > 0 else np.nan)


def measure(df):
    t = df.entry_time.values
    row = {}
    for name, a, b in HALVES + [OOS, ("all", "2000-01-01", "2100-01-01")]:
        m = (t >= np.datetime64(a)) & (t < np.datetime64(b))
        x = df.pnl.values[m]; r = df.r.values[m]
        row[f"{name}_n"] = int(m.sum()); row[f"{name}_pf"] = pf_of(x); row[f"{name}_net"] = float(x.sum())
        row[f"{name}_pfr"] = pf_of(r[np.isfinite(r)])          # risk-% sizing (each trade risks 1R)
    ok = row["h1_n"] >= MIN_TRADES and row["h2_n"] >= MIN_TRADES
    row["raw"] = float(min(row["h1_pf"], row["h2_pf"])) if ok else 0.0
    return row


def run_point(p, extra=None):
    cfg = to_cfg(SYM, p)
    if extra:
        cfg.update(extra)
    return measure(MK.run(int(p["tf"]), cfg))


def eval_point(p):
    try:
        return {**p, **run_point(p)}
    except Exception as e:  # keep the search alive; log the point
        return {**p, "raw": 0.0, "error": repr(e)}


def phase_r(sym, out, n):
    sp = space(sym)
    rng = random.Random(20251)
    pts = [{k: rng.choice(v) for k, v in sp.items()} for _ in range(n)]
    rows = []
    with Pool(4, initializer=init, initargs=(sym,)) as pool:
        for i, r in enumerate(pool.imap_unordered(eval_point, pts, chunksize=4)):
            rows.append(r)
            if i % 1000 == 0:
                print(i, n, flush=True)
    df = pd.DataFrame(rows).sort_values("raw", ascending=False)
    df.to_csv(os.path.join(out, "phaseR.csv"), index=False)
    print(df.head(20).to_string())


def neighbours(sp, p):
    for k, lv in sp.items():
        i = lv.index(p[k])
        for d in (-1, 1):
            if 0 <= i + d < len(lv):
                q = dict(p); q[k] = lv[i + d]
                yield k, q


def refine(p):
    """Coordinate ascent on the 2025 score from one start, then the neighbour median."""
    sp = space(SYM)
    seen = {}

    def score(q):
        key = json.dumps(q, sort_keys=True)
        if key not in seen:
            seen[key] = run_point(q)
        return seen[key]["raw"]

    best = dict(p); bs = score(best)
    for rnd in range(2):
        improved = False
        keys = list(sp)
        random.Random(rnd + int(bs * 1000)).shuffle(keys)
        for k in keys:
            for v in sp[k]:
                if v == best[k]:
                    continue
                q = dict(best); q[k] = v
                s = score(q)
                if s > bs + 0.005:
                    best, bs, improved = q, s, True
        if not improved:
            break
    nb = [score(q) for _, q in neighbours(sp, best)]
    res = {**best, **seen[json.dumps(best, sort_keys=True)]}
    res["nb_median"] = float(np.median(nb + [bs])); res["nb_min"] = float(min(nb)); res["n_evals"] = len(seen)
    return res


def phase_l(sym, out, top=20):
    df = pd.read_csv(os.path.join(out, "phaseR.csv"))
    sp = space(sym)
    starts = []
    for _, r in df.head(top).iterrows():
        starts.append({k: _cast(r[k], sp[k]) for k in sp})
    with Pool(4, initializer=init, initargs=(sym,)) as pool:
        rows = pool.map(refine, starts, chunksize=1)
    res = pd.DataFrame(rows).sort_values("nb_median", ascending=False)
    res.to_csv(os.path.join(out, "phaseL.csv"), index=False)
    cols = list(sp) + ["h1_n", "h1_pf", "h2_n", "h2_pf", "raw", "nb_median", "nb_min", "oos_n", "oos_pf", "oos_pfr",
                       "all_n", "all_pf"]
    print(res[cols].to_string())


def _cast(v, levels):
    for lv in levels:
        if str(lv) == str(v) or (isinstance(lv, (int, float)) and not isinstance(lv, bool)
                                 and isinstance(v, (int, float)) and float(lv) == float(v)):
            return lv
    raise ValueError((v, levels))


def hours_for(p):
    """Block NY hours whose 2025 trades lose (>= 15 trades, PF < 0.7); re-measure."""
    cfg = to_cfg(SYM, p)
    df = MK.run(int(p["tf"]), cfg)
    t = pd.DatetimeIndex(df.entry_time)
    if SYM == "XAUUSD":
        nyh = (t - pd.Timedelta(hours=7)).hour
    else:
        nyh = t.tz_localize("UTC").tz_convert("America/New_York").hour
    in25 = (t < "2026-01-01")
    blocks = []
    for h in range(24):
        x = df.pnl.values[in25 & (nyh == h)]
        if len(x) >= 15 and pf_of(x) < 0.7:
            blocks.append(h)
    q = dict(p); q["block_hours"] = blocks
    return {**{k: v for k, v in p.items()}, "blocks": blocks, **{f"blk_{k}": v for k, v in run_point(q).items()}}


def phase_h(sym, out, top=8):
    res = pd.read_csv(os.path.join(out, "phaseL.csv"))
    sp = space(sym)
    pts = [{k: _cast(r[k], sp[k]) for k in sp} for _, r in res.head(top).iterrows()]
    with Pool(4, initializer=init, initargs=(sym,)) as pool:
        rows = pool.map(hours_for, pts, chunksize=1)
    h = pd.DataFrame(rows)
    h.to_csv(os.path.join(out, "phaseH.csv"), index=False)
    print(h[["tf", "fade", "blocks", "blk_h1_pf", "blk_h2_pf", "blk_raw", "blk_oos_n", "blk_oos_pf"]].to_string())


if __name__ == "__main__":
    sym, ph, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    if ph == "R":
        phase_r(sym, out, int(sys.argv[4]) if len(sys.argv) > 4 else 15000)
    elif ph == "L":
        phase_l(sym, out)
    elif ph == "H":
        phase_h(sym, out)
