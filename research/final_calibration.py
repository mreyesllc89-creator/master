#!/usr/bin/env python3
"""
Final calibration over inputs AND timeframes, in two stages, chosen on 2025 ONLY.

  python3 final_calibration.py stageA <data_dir> <out_dir>
  python3 final_calibration.py stageB <data_dir> <out_dir>
  python3 final_calibration.py verify <data_dir> <out_dir>
(BTC: prefix with XLZC_SYMBOL=BTCUSD XLZC_SPREAD_PTS=500 XLZC_SPREAD_CAP=1000)

Stage A - every trigger/filter pair (39) x structure (N, S, buffer, TP lookback, min RR,
          fallback RR = 324) x trailing (off, 150/100, 150/50, 300/50, 400/50 gold pts) x session
          (NY 12:00-16:30, London+NY 07:00-20:00) x stochastic (soft, hard). ~250k runs.
Stage B - for the best 10 pairs, the 50 best Stage A setups each, every v1.20 option: trend
          condition (and/or/macd/ema) x stochastic rule (and/or, soft/hard) x TP mode
          (swing, zones tol 50 / 100 anchored on the zone top) x TP buffer (0, 20). 64 each.
verify  - the final pick per pair under the four same-bar fill models.

Selection score (2025 only): worst half-year PF, smoothed as the median over the setup and its
structure neighbours (one step in N, S, buffer, TP lookback, min RR), >= 30 trades per half.
Distances are gold points x sqrt(trigger minutes) x instrument scale, as in the EA presets
(zone tolerance and TP buffer too: write them to the EA multiplied by that factor).
"""
import itertools
import json
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

import fgf_backtest as FB
import xlzc_backtest as B
import xlzc_calibrate as C

PAIRS = C.ALL_PAIRS + ["M1/M5"]
STRUCT = dict(N=[15, 25, 40], S=[2, 3, 4], buffer=[40, 80, 120], NT=[60, 120], min_rr=[1.0, 1.5, 2.0], fb=[0.0, 1.5])
TRAILS = {"off": None, "150/100": (150, 100), "150/50": (150, 50), "300/50": (300, 50), "400/50": (400, 50)}
SESSIONS = ["ny_12-1630", "ldn_ny_07-20"]
MODES = ["next", "close", "worst", "random"]


def cfg_of(pair, N, S, buffer, NT, min_rr, fb, trail, session, stoch, **extra):
    c = dict(tf=pair, N=N, S=S, buffer=buffer, NT=NT, min_rr=min_rr, fb=fb, stoch=stoch, session=session,
             trail=TRAILS[trail] is not None)
    if TRAILS[trail]:
        c["trail_start"], c["trail_dist"] = TRAILS[trail]
    c.update(extra)
    return c


def stats(tr):
    s = C.seg_stats(tr)
    out = {k: (None if not np.isfinite(v) else float(v)) for k, v in s.items()}
    r = np.array([x[1] for x in tr])
    out["win"] = float((r > 0).mean()) if len(r) else None
    h1, h2 = out["2025H1_pf"], out["2025H2_pf"]
    out["min25"] = min(h1, h2) if h1 is not None and h2 is not None else None
    out["t25"] = min(out["2025H1_trades"], out["2025H2_trades"])
    return out


# ------------------------------------------------------------------------- data with option variants
def htf_comp(m1, tf):
    h = B.resample(m1, tf)
    m = B.macd_main(h["close"]); e = B.ema(h["close"], 50)
    return pd.DataFrame({"close_time": h.index + pd.Timedelta(minutes=B.TF_MIN[tf]),
                         "mn": (m < 0).values, "be": (h["close"] < e).values}).iloc[60:]


def prepare(data_dir, pairs):
    p = FB.prepare(data_dir, pairs)
    m1, _ = B.load(data_dir)
    comps = {}
    for pair in pairs:
        trig, htf = pair.split("/")
        if htf not in comps:
            comps[htf] = htf_comp(m1, htf)
        sig = p["sig"][pair]
        s = pd.DataFrame({"t": pd.to_datetime(sig["et"])}).reset_index()
        j = pd.merge_asof(s.sort_values("t"), comps[htf].sort_values("close_time"), left_on="t",
                          right_on="close_time", direction="backward").sort_values("index")
        mn, be = j["mn"].fillna(False).to_numpy(bool), j["be"].fillna(False).to_numpy(bool)
        # stochastic "or" rule (spec: from overbought OR turning down), recomputed on the trigger TF
        t = B.resample(m1, trig)
        k, d = B.stoch(t)
        k = k.values; d = d.values
        bars = np.searchsorted(t.index.values, sig["et"]) - 1          # signal bar = bar before entry
        bars = np.clip(bars, 4, len(k) - 1)
        was_ob = np.array([np.nanmax(k[b - 4:b + 1]) >= 80 for b in bars])
        turned = (k[bars] < d[bars]) | (k[bars] < 80)
        for cond, bias in (("and", mn & be), ("or", mn | be), ("macd", mn), ("ema", be)):
            for srule, sok in (("and", was_ob & turned), ("or", was_ob | turned)):
                alias = f"{pair}|{cond}|{srule}"
                p["sig"][alias] = dict(sig, bias=bias, stoch_ok=sok)
                for S in C.SS:
                    p["pools"][(alias, S)] = p["pools"][(pair, S)]
                    for N in C.NS:
                        p["sls"][(alias, N, S)] = p["sls"][(pair, N, S)]
    return p


def job(cfg):
    tr = C.run_cfg(cfg)[1]
    s = stats(tr)
    s.update({k: v for k, v in cfg.items() if k != "tf"})
    s["tf"] = cfg["tf"]
    return s


def smooth(df, keys_fixed):
    """Neighbourhood median of min25 over the structure grid, per fixed group."""
    out = np.full(len(df), np.nan)
    dims = list(STRUCT)
    idx = {tuple(r): i for i, r in enumerate(df[keys_fixed + dims].itertuples(index=False, name=None))}
    vals = df["min25"].to_numpy(float)
    ok = (df["t25"].to_numpy(float) >= 30) & np.isfinite(vals)
    for i, r in enumerate(df[keys_fixed + dims].itertuples(index=False, name=None)):
        if not ok[i]:
            continue
        v = [vals[i]]
        base = list(r)
        for di, dname in enumerate(dims):
            grid = STRUCT[dname]
            pos = grid.index(base[len(keys_fixed) + di])
            for q in (pos - 1, pos + 1):
                if 0 <= q < len(grid):
                    nb = base.copy(); nb[len(keys_fixed) + di] = grid[q]
                    j = idx.get(tuple(nb))
                    if j is not None and np.isfinite(vals[j]):
                        v.append(vals[j])
        out[i] = np.median(v)
    return out


def main():
    stage, data_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)
    if stage == "stageA":
        payload = FB.prepare(data_dir, PAIRS)
        grid = [cfg_of(p, *v[:6], trail=v[6], session=v[7], stoch=v[8])
                for p in PAIRS for v in itertools.product(*STRUCT.values(), TRAILS, SESSIONS, ["soft", "hard"])]
        print(f"stage A: {len(grid)} runs", flush=True)
        rows = []
        with Pool(4, initializer=FB.init_worker, initargs=(payload,)) as pool:
            for i, r in enumerate(pool.imap(job, grid, chunksize=200)):
                rows.append(r)
                if i % 25000 == 0:
                    print(i, flush=True)
        df = pd.DataFrame(rows)
        df["trail_set"] = df.apply(lambda r: "off" if not r["trail"] else f"{int(r['trail_start'])}/{int(r['trail_dist'])}", axis=1)
        df.to_csv(os.path.join(out_dir, "stageA.csv.gz"), index=False)
        print("done", len(df))
    elif stage == "stageB":
        a = pd.read_csv(os.path.join(out_dir, "stageA.csv.gz"))
        fixed = ["tf", "trail_set", "session", "stoch"]
        a["smooth25"] = np.nan
        for _, g in a.groupby(fixed):
            a.loc[g.index, "smooth25"] = smooth(g, fixed)
        a.to_csv(os.path.join(out_dir, "stageA_scored.csv.gz"), index=False)
        best_pair = a.groupby("tf").smooth25.max().sort_values(ascending=False)
        pairs = best_pair.dropna().head(10).index.tolist()
        print("top 10 pairs by 2025 smoothed score:", pairs, flush=True)
        payload = prepare(data_dir, pairs)
        grid = []
        for pair in pairs:
            top = a[a.tf == pair].sort_values("smooth25", ascending=False).head(50)
            for _, r in top.iterrows():
                for cond, srule, stoch, tpm, buf in itertools.product(["and", "or", "macd", "ema"], ["and", "or"],
                                                                       ["soft", "hard"], ["swing", 50, 100], [0, 20]):
                    if stoch == "soft" and srule == "or":
                        continue                       # the rule only matters when the stochastic blocks
                    extra = {"tp_buf": buf}
                    if tpm != "swing":
                        extra.update(zone_tol=tpm, zone_min=1)
                    c = cfg_of(f"{pair}|{cond}|{srule}", r.N, r.S, r.buffer, r.NT, r.min_rr, r.fb,
                               trail=r.trail_set, session=r.session, stoch=stoch, **extra)
                    c["base_rank_score"] = r.smooth25
                    grid.append(c)
        print(f"stage B: {len(grid)} runs", flush=True)

        def strip(c):
            c = dict(c); c.pop("base_rank_score", None); return c
        rows = []
        with Pool(4, initializer=FB.init_worker, initargs=(payload,)) as pool:
            for c, r in zip(grid, pool.imap(job, [strip(c) for c in grid], chunksize=100)):
                r["stageA_smooth25"] = c["base_rank_score"]; rows.append(r)
        b = pd.DataFrame(rows)
        b["pair"] = b.tf.str.split("|").str[0]
        b["cond"] = b.tf.str.split("|").str[1]
        b["stoch_rule"] = b.tf.str.split("|").str[2]
        b.to_csv(os.path.join(out_dir, "stageB.csv.gz"), index=False)
        print("done", len(b))
    else:   # verify: final pick per pair = best 2025 worst-half PF among stage B rows that also
        #       keep the stage A neighbourhood score (>= 30 trades/half); 2026 out of sample
        b = pd.read_csv(os.path.join(out_dir, "stageB.csv.gz"))
        b = b[(b.t25 >= 30) & b.min25.notna()]
        b["score"] = np.minimum(b.min25, b.stageA_smooth25 + 0.25)   # option gain capped: avoid one-off peaks
        picks = b.sort_values("score", ascending=False).groupby("pair").head(1)
        payload = prepare(data_dir, sorted(picks.pair.unique()))
        FB.init_worker(payload)
        res = []
        for _, r in picks.iterrows():
            cfg = {k: r[k] for k in ["tf", "N", "S", "buffer", "NT", "min_rr", "fb", "stoch", "session", "trail"]}
            for k in ("trail_start", "trail_dist", "zone_tol", "zone_min", "tp_buf"):
                if k in r and pd.notna(r[k]):
                    cfg[k] = r[k]
            cfg = {k: (v.item() if hasattr(v, "item") else v) for k, v in cfg.items()}
            fills = {}
            for m in MODES:
                B.M1Path.TRAIL_MODE = m; C.G["cache"] = {}
                fills[m] = stats(C.run_cfg(cfg)[1])
            B.M1Path.TRAIL_MODE = "close"; C.G["cache"] = {}
            res.append(dict(pair=r.pair, cfg=cfg, score=float(r.score), fills=fills))
            f = fills
            print(f"{r.pair:7s} {cfg['tf'].split('|',1)[1]:9s} N{cfg['N']} S{cfg['S']} buf{cfg['buffer']} NT{cfg['NT']} "
                  f"RR{cfg['min_rr']} fb{cfg['fb']} {cfg['session']} {cfg['stoch']} trail "
                  f"{(str(cfg.get('trail_start'))+'/'+str(cfg.get('trail_dist'))) if cfg['trail'] else 'off'} "
                  f"zone {cfg.get('zone_tol','-')} buf {cfg.get('tp_buf',0)} | 2025 {f['close']['2025H1_pf']:.2f}/{f['close']['2025H2_pf']:.2f}"
                  f" | trades {f['close']['all_trades']:.0f} PF {min(x['all_pf'] for x in f.values()):.2f}-{max(x['all_pf'] for x in f.values()):.2f}"
                  f" | 2026 {min((x['2026_pf'] or 0) for x in f.values()):.2f}-{max((x['2026_pf'] or 0) for x in f.values()):.2f}"
                  f" ({f['close']['2026_trades']:.0f} tr)", flush=True)
        json.dump(res, open(os.path.join(out_dir, "final_picks.json"), "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
