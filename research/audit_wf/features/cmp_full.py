"""Full-series comparison: hump_wf.Feat (built on the module's own Mk of the run folder) against my independent
features (mine.py), and every condition lambda against my own reading of its description, on every trigger bar
with an entry, both sides. Usage: [HUMP_SYMBOL=BTCUSD] python3 cmp_full.py <run folder> <TF,TF,...> <out.json>"""
import json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, "/workspace/master/research")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_wf as W
import mine as M

work, tfs, out_json = sys.argv[1], sys.argv[2].split(","), sys.argv[3]
t0 = time.time()
MK = W.Mk(work)
W.MK = MK
tm = M.minutes(MK.m1.index)
o, h, l, c = MK.o, MK.h, MK.l, MK.c
v = MK.vol.values.astype(float)
print(f"{W.SYM}: market ready {time.time() - t0:.0f}s, {len(tm)} rows", flush=True)

NAMES = ["tr_h4", "tr_d1", "sl_h4", "sl_d1", "adx_h1", "adx_h4", "atrp", "pdr", "tdr", "pdpos", "dopen", "asia_pos", "nyor_pos",
         "rn", "bos_up", "bos_dn", "hm1", "hm2", "volr", "body_dir", "body_frac", "rng_atr", "xs_dn", "xs_up", "sw_dn", "sw_up"]


def cmp(a, b, times):
    a = np.asarray(a); b = np.asarray(b)
    if a.dtype.kind == "f" or b.dtype.kind == "f":
        a = a.astype(float); b = b.astype(float)
        both_nan = np.isnan(a) & np.isnan(b)
        with np.errstate(invalid="ignore"):
            close = both_nan | (np.abs(a - b) <= 1e-9 * np.maximum(1.0, np.abs(a)))
        bad = ~close
        md = float(np.nanmax(np.abs(a - b))) if (~np.isnan(a) & ~np.isnan(b)).any() else 0.0
    else:
        bad = a != b; md = None
    idx = np.flatnonzero(bad)
    return dict(n=int(len(a)), bad=int(bad.sum()), nan_module=int(np.isnan(a.astype(float)).sum()) if a.dtype.kind == "f" else None,
                first_bad=[str(times[i]) for i in idx[:3]], last_bad=str(times[idx[-1]]) if len(idx) else None, max_abs_diff=md)


def my_conditions(G, i, s, te, de, rnd):
    """My own reading of each description (G: dict of feature arrays)."""
    sell = s < 0; buy = s > 0
    g = {k: np.asarray(G[k])[i] for k in G}
    with np.errstate(invalid="ignore"):
        C = {}
        C["base"] = np.ones(len(i), bool)
        C["trend_h4"] = (sell & (g["tr_h4"] == -1)) | (buy & (g["tr_h4"] == 1))
        C["trend_d1"] = (sell & (g["tr_d1"] == -1)) | (buy & (g["tr_d1"] == 1))
        C["slope_h4"] = (sell & (g["sl_h4"] == -1)) | (buy & (g["sl_h4"] == 1))
        C["slope_d1"] = (sell & (g["sl_d1"] == -1)) | (buy & (g["sl_d1"] == 1))
        C["adx_h1_20"] = g["adx_h1"] >= 20; C["adx_h1_30"] = g["adx_h1"] >= 30
        C["adx_h4_20"] = g["adx_h4"] >= 20; C["adx_h4_30"] = g["adx_h4"] >= 30
        C["adx_h1_lt20"] = g["adx_h1"] < 20
        C["atrp_ge50"] = g["atrp"] >= 0.5; C["atrp_ge70"] = g["atrp"] >= 0.7; C["atrp_le50"] = g["atrp"] <= 0.5
        C["atrp_30_70"] = (g["atrp"] >= 0.3) & (g["atrp"] <= 0.7)
        C["pdr_ge80"] = g["pdr"] >= 0.8; C["pdr_ge120"] = g["pdr"] >= 1.2
        C["tdr_ge40"] = g["tdr"] >= 0.4; C["tdr_ge70"] = g["tdr"] >= 0.7
        p = g["pdpos"]
        C["pd_premium"] = (sell & (p >= 0.5)) | (buy & (p <= 0.5))
        C["pd_momentum"] = (sell & (p <= 0.5)) | (buy & (p >= 0.5))
        C["pd_break"] = (sell & (p < 0)) | (buy & (p > 1))
        C["pd_inside"] = (p >= 0) & (p <= 1)
        a = g["asia_pos"]
        C["asia_break"] = (sell & (a < 0)) | (buy & (a > 1)); C["asia_inside"] = (a >= 0) & (a <= 1)
        n = g["nyor_pos"]
        C["nyor_break"] = (sell & (n < 0)) | (buy & (n > 1)); C["nyor_inside"] = (n >= 0) & (n <= 1)
        C["day_with"] = (sell & (g["dopen"] == -1)) | (buy & (g["dopen"] == 1))
        C["day_against"] = (sell & (g["dopen"] == 1)) | (buy & (g["dopen"] == -1))
        C["round_near"] = g["rn"] <= 0.3; C["round_far"] = g["rn"] >= 0.5
        C["bos"] = (sell & g["bos_dn"]) | (buy & g["bos_up"]); C["no_bos"] = ~C["bos"]
        C["htf_macd_1"] = (sell & (g["hm1"] == -1)) | (buy & (g["hm1"] == 1))
        C["htf_macd_2"] = (sell & (g["hm2"] == -1)) | (buy & (g["hm2"] == 1))
        C["htf_macd_both"] = C["htf_macd_1"] & C["htf_macd_2"]
        C["vol_ge150"] = g["volr"] >= 1.5; C["vol_ge200"] = g["volr"] >= 2.0; C["vol_le100"] = g["volr"] <= 1.0
        C["candle_with"] = (sell & (g["body_dir"] == -1)) | (buy & (g["body_dir"] == 1))
        C["candle_against"] = (sell & (g["body_dir"] == 1)) | (buy & (g["body_dir"] == -1))
        C["candle_body50"] = g["body_frac"] >= 0.5
        C["candle_big"] = g["rng_atr"] >= 1.0; C["candle_small"] = g["rng_atr"] < 1.0
        for a_, b_ in ((7, 10), (10, 13), (13, 16), (16, 19), (19, 22)):
            C[f"hours_{a_}_{b_}"] = (te >= a_ * 60) & (te < b_ * 60)
        C["not_us_open"] = ~((te >= 15 * 60) & (te < 17 * 60 + 30))
        C["no_monday"] = de != 0; C["no_friday"] = de != 4; C["tue_thu"] = (de >= 1) & (de <= 3)
        C["no_news_times"] = ~(((te >= 15 * 60) & (te <= 16 * 60)) | ((te >= 16 * 60 + 30) & (te <= 17 * 60 + 30)))
        C["xlzc_stoch"] = (sell & g["xs_dn"]) | (buy & g["xs_up"])
        C["xlzc_sweep"] = (sell & g["sw_dn"]) | (buy & g["sw_up"])
        C["xlzc_both"] = (sell & g["xs_dn"] & g["sw_dn"]) | (buy & g["xs_up"] & g["sw_up"])
        for k, nm in enumerate("abc"):
            C[f"random_{nm}"] = rnd[k][i] < 0.5
    return C


res = {}
for tf in tfs:
    t1 = time.time()
    F = MK.feat(tf)
    d = MK._tf[tf]
    times = d["t"].index
    mine = M.features(tm, o, h, l, c, v, tf, W.HTF_UP[tf])
    G = dict(mine["F"])
    assert len(mine["T"]) == len(times) and (mine["T"] == M.minutes(times)).all(), "trigger bars differ"
    # sweep flags: the module's numba function is the XLZC reference copied; checked separately (xlzc_check.py)
    G["sw_dn"] = F.sw_dn; G["sw_up"] = F.sw_up
    r = {}
    for nm in NAMES:
        if nm in ("sw_dn", "sw_up"):
            continue
        r[nm] = cmp(getattr(F, nm), G[nm], times)
    # textbook Wilder seeds (SMA) for ATR / ADX: how long the seed matters
    tb = M.features(tm, o, h, l, c, v, tf, W.HTF_UP[tf], seed="sma")["F"]
    seed = {}
    for nm in ("adx_h1", "adx_h4", "atrp", "rng_atr"):
        a = np.asarray(getattr(F, nm), float); b = np.asarray(tb[nm], float)
        ok = ~np.isnan(a) & ~np.isnan(b)
        dif = np.where(ok, np.abs(a - b), 0)
        big = np.flatnonzero(dif > 1e-6)
        thr = {"adx_h1": (20, 30), "adx_h4": (20, 30), "atrp": (0.3, 0.5, 0.7), "rng_atr": (1.0,)}[nm]
        flips = np.zeros(len(a), bool)
        for x in thr:
            flips |= ok & ((a >= x) != (b >= x))
        fl = np.flatnonzero(flips)
        seed[nm] = dict(bars_differ_1e6=int(len(big)), last_differ=str(times[big[-1]]) if len(big) else None,
                        threshold_flips=int(flips.sum()), last_flip=str(times[fl[-1]]) if len(fl) else None)
    r["textbook_seed"] = seed
    # conditions on every trigger bar with an entry row, both sides
    row = d["row"]
    ii = np.flatnonzero(row >= 0)
    i2 = np.r_[ii, ii]; s2 = np.r_[np.full(len(ii), 1, np.int8), np.full(len(ii), -1, np.int8)]
    er = row[i2]
    te = MK.tod[er]; de = MK.dow[er]
    mineC = my_conditions({nm: getattr(F, nm) for nm in NAMES}, i2, s2, te, de, F.rnd)
    mineC2 = my_conditions(G, i2, s2, te, de, F.rnd)
    cr = {}
    for key, grp, text, fn in W.CONDS:
        mod = np.asarray(fn(F, i2, s2, te, de), bool)
        cr[key] = dict(module_true=int(mod.sum()), lambda_vs_mine=int((mod != mineC[key]).sum()),
                       end_to_end_vs_mine=int((mod != mineC2[key]).sum()), n=int(len(mod)))
    r["conditions"] = cr
    res[tf] = r
    bad = {k: v["bad"] for k, v in r.items() if isinstance(v, dict) and "bad" in v and v["bad"]}
    badc = {k: (v["lambda_vs_mine"], v["end_to_end_vs_mine"]) for k, v in cr.items() if v["lambda_vs_mine"] or v["end_to_end_vs_mine"]}
    print(f"{W.SYM} {tf}: {len(times)} bars, {len(ii)} with entry; feature mismatches {bad}; condition mismatches {badc}; {time.time() - t1:.0f}s", flush=True)
    print("   seed:", seed, flush=True)
    MK._feat.pop(tf, None)
json.dump(res, open(out_json, "w"), indent=1)
print("CMP_FULL_DONE", W.SYM)
