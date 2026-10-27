"""Stage 2: pick robust stage-1 candidates and hill-climb them one input at a time.

usage: python -I refine.py SYMBOL TF [spread_model] [top_k]
Selection: in-sample t-stat ranked, but a candidate must also have a positive out-of-sample
mean R and at least 30 trades per in-sample year; this rejects pure in-sample fits.
Refinement maximises the in-sample t-stat only; OOS / 2026 are reported, never optimised.
writes results/refined_<SYMBOL>_<TF>_<model>.csv
"""
import json
import multiprocessing as mp
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pandas as pd
from space import neighbours
from sweep import CACHE, DATA, IS_YEARS, RESULTS, _init, _work, G

MIN_PER_YEAR = 30


def pick(df, symbol, k):
    lo, hi = IS_YEARS[symbol]
    years = hi - lo + 1
    ok = df[(df.is_n >= MIN_PER_YEAR * years) & (df.oos_avg_r > 0) & (df.oos_n >= 50)]
    ok = ok.sort_values("is_tstat", ascending=False)
    # de-duplicate near-identical configs by keeping distinct (preset, direction, sl, tp) tuples
    seen, picked = set(), []
    for _, row in ok.iterrows():
        c = json.loads(row.cfg)
        key = (c["presetMode"], c["tradeOriginalDirection"], c["slAtrMultS2"], c["tpRS2"], c["atrLenS2"])
        if key in seen:
            continue
        seen.add(key); picked.append(row)
        if len(picked) >= k:
            break
    return picked


def climb(cfg, pool, rounds=3):
    best = pool.apply(_work, ((0, cfg),)); best_cfg = cfg
    for _ in range(rounds):
        cands = neighbours(best_cfg)
        res = pool.map(_work, [(i, c) for i, (_, c) in enumerate(cands)], chunksize=4)
        improved = False
        for (k, c), r in zip(cands, res):
            if r["is_tstat"] > best["is_tstat"] + 0.05 and r["is_n"] >= best["is_n"] * 0.5:
                best, best_cfg, improved = r, c, True
        if not improved:
            break
    return best_cfg, best


if __name__ == "__main__":
    symbol, tf = sys.argv[1], int(sys.argv[2])
    model = sys.argv[3] if len(sys.argv) > 3 else "modern"
    top_k = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    df = pd.read_csv(os.path.join(RESULTS, f"sweep_{symbol}_{tf}_{model}.csv"))
    picked = pick(df, symbol, top_k)
    rows = []
    with mp.Pool(os.cpu_count(), initializer=_init, initargs=(symbol, tf, model)) as pool:
        for row in picked:
            cfg0 = json.loads(row.cfg)
            cfg, r = climb(cfg0, pool)
            r["cfg"] = json.dumps(cfg, sort_keys=True); r["seed_id"] = int(row.id)
            r["seed_is_tstat"] = float(row.is_tstat)
            rows.append(r)
            print(f"{symbol} M{tf} seed {row.id}: IS t {row.is_tstat:.2f}->{r['is_tstat']:.2f} "
                  f"OOS t {row.oos_tstat:.2f}->{r['oos_tstat']:.2f} 2026 R {r.get('x26_avg_r', 0):+.3f}", flush=True)
    out = pd.DataFrame(rows).sort_values("is_tstat", ascending=False)
    out.to_csv(os.path.join(RESULTS, f"refined_{symbol}_{tf}_{model}.csv"), index=False)
