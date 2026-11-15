#!/usr/bin/env python3
"""
Re-calibration of the Loma (hump) method per trigger timeframe, with an honest out-of-sample test.

Question: on which timeframes does the method hold a profit factor of 1.3 or more on data the
calibration never saw?

Protocol (fixed before any out-of-sample result was looked at):
  data     XAUUSD: FTMO M1 (Jan 2025 - May 15 2026) followed by Dukascopy M1 (May 18 - Nov 13 2026), FTMO hourly
           spread table throughout. BTCUSD: Binance BTCUSDT M1 (Jan 2025 - Nov 13 2026), 10 USD spread.
  IS       in-sample: entries before 2026-05-16 03:00 server time, in three blocks
           (2025 H1, 2025 H2, 2026 Jan - May 15).
  OOS      out-of-sample: entries from 2026-05-16 03:00 server time to the end of the data.
  space    hump_search.SPACE with HUMP_SPACE=2 (every calibrated input), one timeframe at a time,
           N random setups per timeframe; the trend-filter timeframe must be a multiple of the trigger timeframe.
  score    in-sample only: the lowest of the six profit factors (three blocks x base costs and harsh
           stress), with at least MIN_N trades in every block.
  pick     per timeframe: the 10 best scores, one per (direction, session, trend filter) family, score >= 1.3.
  test     the picked setups on OOS: pooled profit factor (all their trades together), base and stress.
  pass     pooled OOS PF >= 1.3 on >= 100 trades.

Usage:
  python3 hump_tf_recal.py build  <work_dir> [dukascopy_dir]          # once per symbol: combined M1 series
  python3 hump_tf_recal.py run    <work_dir> <TF> <N> [workers]       # candidates of one timeframe, base + stress
  python3 hump_tf_recal.py select <work_dir> <out_json>               # in-sample pick and out-of-sample test
Environment: HUMP_SYMBOL=XAUUSD|BTCUSD, HUMP_BTC_DATA=<dir with BTCUSD_m1.csv> for BTC.
"""
import json, os, pickle, random, sys, time
from multiprocessing import Pool
import numpy as np, pandas as pd

os.environ["HUMP_SPACE"] = "2"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_engine as H, hump_search as X, xlzc_backtest as B

SYM = H.SYMBOL
TFS = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]
HTFS = ["M15", "M30", "H1", "H4", "D1"]
IS_END = np.datetime64("2026-05-16T03:00")
BLOCKS = [(np.datetime64("2025-01-01"), np.datetime64("2025-07-01")), (np.datetime64("2025-07-01"), np.datetime64("2026-01-01")),
          (np.datetime64("2026-01-01"), IS_END)]
MIN_N = 20
TOPK = 10
PASS_PF, PASS_N = 1.30, 100
STRESS = (dict(trail_worst=1, delay=1, slip=3.0, comm=2.0, max_spread=1e9) if SYM == "BTCUSD"
          else dict(trail_worst=1, delay=1, slip=0.10, comm=0.07, max_spread=5.0))


# ----------------------------------------------------------------------------- data
def build(work, duk_dir=None):
    os.makedirs(work, exist_ok=True)
    if SYM == "BTCUSD":
        m1, hs = H.load_btc()
        hs_real = hs
    else:
        import duk_to_m1 as D
        f, hourly = B.load(H.DATA)
        d, dh = D.load(duk_dir)
        cut = f.index[-1]
        keep = d.index > cut
        d, dh = d[keep], dh[keep]
        m1 = pd.concat([f[["open", "high", "low", "close"]], d[["open", "high", "low", "close"]]])
        assert m1.index.is_monotonic_increasing and not m1.index.duplicated().any()
        hs = hourly[B.server_to_utc_hour(m1.index)] / 2.0                 # FTMO spread table for the whole series
        hs_real = np.r_[hourly[B.server_to_utc_hour(f.index)] / 2.0, dh]  # Dukascopy's own spread after the seam
        print(f"FTMO to {cut}, Dukascopy {d.index[0]} .. {d.index[-1]} ({len(d)} bars)")
    m1 = m1[["open", "high", "low", "close"]].astype(float)
    m1.to_pickle(os.path.join(work, "m1.pkl"))
    np.save(os.path.join(work, "hs.npy"), np.asarray(hs, float)); np.save(os.path.join(work, "hs_real.npy"), np.asarray(hs_real, float))
    print(SYM, m1.index[0], m1.index[-1], len(m1), "bars; IS bars", int((m1.index.values < IS_END).sum()),
          "OOS bars", int((m1.index.values >= IS_END).sum()))


def market(work, real_spread=False):
    m1 = pd.read_pickle(os.path.join(work, "m1.pkl"))
    hs = np.load(os.path.join(work, "hs_real.npy" if real_spread else "hs.npy"))
    return H.Market(m1=m1, half_spread=hs)


# ----------------------------------------------------------------------------- candidates
def valid_htfs(tf):
    m = B.TF_MIN[tf]
    return ["none"] + [h for h in HTFS if B.TF_MIN[h] > m and B.TF_MIN[h] % m == 0]


def candidates(tf, n):
    rng = random.Random(f"{SYM}-{tf}-2026-11")
    keys = [k for k in X.SPACE if k not in ("tf", "htf")]
    seen, out = set(), []
    hl = valid_htfs(tf)
    while len(out) < n:
        p = {k: rng.choice(X.SPACE[k]) for k in keys}
        p["tf"] = tf; p["htf"] = rng.choice(hl)
        key = json.dumps(p, sort_keys=True)
        if key not in seen:
            seen.add(key); out.append(p)
    return out


MK = None


def _init(work):
    global MK
    MK = market(work)


def _trades(p, extra=None):
    c = dict(X.BASE); c.update(p)
    if extra:
        c.update(extra)
    df = MK.run(X.engine_cfg(c))
    return (df.entry_time.values.astype("datetime64[m]").astype(np.int64).astype(np.int32),   # minutes since epoch
            df.r.values.astype(np.float32))


def _one(p):
    return _trades(p), _trades(p, STRESS)


def run(work, tf, n, workers=3):
    cand = candidates(tf, n)
    t0 = time.time()
    with Pool(workers, initializer=_init, initargs=(work,)) as pool:
        res = pool.map(_one, cand, chunksize=16)
    with open(os.path.join(work, f"cand_{tf}.pkl"), "wb") as f:
        pickle.dump(dict(tf=tf, params=cand, base=[r[0] for r in res], stress=[r[1] for r in res]), f, protocol=4)
    print(f"{SYM} {tf}: {n} setups x 2 in {time.time() - t0:.0f}s", flush=True)


# ----------------------------------------------------------------------------- selection and test
def pf(r):
    r = np.asarray(r, float)
    w = r[r > 0].sum(); l = -r[r < 0].sum()
    return float(w / l) if l > 0 else (float("inf") if w > 0 else float("nan"))


def is_score(tb, ts):
    """Lowest of the six in-sample profit factors; 0 when a block has fewer than MIN_N trades."""
    vals = []
    for (t, r) in (tb, ts):
        tt = t.astype("int64").astype("datetime64[m]")
        for a, b in BLOCKS:
            m = (tt >= a) & (tt < b)
            if m.sum() < MIN_N:
                return 0.0
            v = pf(r[m])
            if not np.isfinite(v):
                v = 99.0
            vals.append(v)
    return float(min(vals))


def split(t, r):
    tt = t.astype("int64").astype("datetime64[m]")
    return r[tt < IS_END], tt[tt >= IS_END], r[tt >= IS_END]


def weekly_boot(times, r, reps=2000, seed=7):
    """Profit-factor percentiles from resampling calendar weeks (keeps same-week trades together)."""
    if len(r) == 0:
        return [float("nan")] * 3
    wk = times.astype("datetime64[W]").astype(np.int64)
    groups = [r[wk == w] for w in np.unique(wk)]
    rng = np.random.default_rng(seed); out = []
    for _ in range(reps):
        pick = rng.integers(0, len(groups), len(groups))
        out.append(pf(np.concatenate([groups[i] for i in pick])))
    out = np.asarray(out); out = out[np.isfinite(out)]
    return [float(np.percentile(out, q)) for q in (5, 50, 95)]


def select(work, out_json, real_mk=None):
    rows, picks_all = [], []
    for tf in TFS:
        fn = os.path.join(work, f"cand_{tf}.pkl")
        if not os.path.exists(fn):
            continue
        d = pickle.load(open(fn, "rb"))
        P, Bs, Ss = d["params"], d["base"], d["stress"]
        sc = np.array([is_score(Bs[i], Ss[i]) for i in range(len(P))])
        elig = np.where(sc > 0)[0]
        order = elig[np.argsort(-sc[elig], kind="stable")]
        picked, fams = [], set()
        for i in order:
            if sc[i] < PASS_PF or len(picked) >= TOPK:
                break
            fam = (P[i]["sides"], P[i]["session"], P[i]["htf"])
            if fam in fams:
                continue
            fams.add(fam); picked.append(int(i))
        row = dict(symbol=SYM, tf=tf, setups=len(P), eligible=int(len(elig)), is_ge_1_3=int((sc >= PASS_PF).sum()), picked=len(picked))
        # baseline of the timeframe: every eligible setup, unselected
        if len(elig):
            ob = [split(*Bs[i]) for i in elig]
            allr = np.concatenate([x[2] for x in ob]) if ob else np.zeros(0)
            row["all_eligible_oos_pf"] = pf(allr)
            row["all_eligible_share_oos_ge_1_3"] = float(np.mean([pf(x[2]) >= PASS_PF for x in ob if len(x[2]) >= 15] or [np.nan]))
        if picked:
            isr = [split(*Bs[i])[0] for i in picked]
            ot = np.concatenate([split(*Bs[i])[1] for i in picked]); orr = np.concatenate([split(*Bs[i])[2] for i in picked])
            st = np.concatenate([split(*Ss[i])[1] for i in picked]); sr = np.concatenate([split(*Ss[i])[2] for i in picked])
            ind = [pf(split(*Bs[i])[2]) for i in picked]; ind_n = [len(split(*Bs[i])[2]) for i in picked]
            lo, med, hi = weekly_boot(ot, orr)
            row.update(is_score_median=float(np.median(sc[picked])), is_pf_pooled=pf(np.concatenate(isr)),
                       oos_n=int(len(orr)), oos_pf=pf(orr), oos_net_r=float(orr.sum()),
                       oos_stress_n=int(len(sr)), oos_stress_pf=pf(sr), oos_stress_net_r=float(sr.sum()),
                       oos_pf_p05=lo, oos_pf_p95=hi,
                       oos_individual_ge_1_3=int(sum(1 for v, n in zip(ind, ind_n) if n >= 15 and v >= PASS_PF)),
                       oos_individual_median_pf=float(np.nanmedian(ind)),
                       top1_is_score=float(sc[picked[0]]), top1_oos_n=int(ind_n[0]), top1_oos_pf=ind[0])
            # luck check: how often do 10 random eligible setups of this timeframe do as well out of sample?
            rng = np.random.default_rng(11); better = 0; reps = 1000
            oos_cache = {int(i): split(*Bs[i])[2] for i in elig}
            for _ in range(reps):
                ch = rng.choice(elig, size=min(len(picked), len(elig)), replace=False)
                if pf(np.concatenate([oos_cache[int(i)] for i in ch])) >= row["oos_pf"]:
                    better += 1
            row["random_pick_as_good"] = better / reps
            row["passes"] = bool(row["oos_pf"] >= PASS_PF and row["oos_n"] >= PASS_N)
            for rank, i in enumerate(picked, 1):
                picks_all.append(dict(P[i], symbol=SYM, rank=rank, is_score=float(sc[i]), oos_n=int(ind_n[rank - 1]),
                                      oos_pf=ind[rank - 1], oos_stress_pf=pf(split(*Ss[i])[2])))
        else:
            row["passes"] = False
        rows.append(row)
    out = dict(symbol=SYM, is_end=str(IS_END), min_n=MIN_N, topk=TOPK, pass_pf=PASS_PF, pass_n=PASS_N, stress=STRESS,
               timeframes=rows, picks=picks_all)
    json.dump(out, open(out_json, "w"), indent=1, default=float)
    pd.set_option("display.width", 250)
    cols = ["tf", "setups", "eligible", "is_ge_1_3", "picked", "is_score_median", "oos_n", "oos_pf", "oos_stress_pf",
            "oos_pf_p05", "oos_pf_p95", "oos_individual_ge_1_3", "all_eligible_oos_pf", "random_pick_as_good", "passes"]
    df = pd.DataFrame(rows)
    print(df[[c for c in cols if c in df]].round(2).to_string(index=False))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        build(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]) if len(sys.argv) > 5 else 3)
    elif cmd == "select":
        select(sys.argv[2], sys.argv[3])
