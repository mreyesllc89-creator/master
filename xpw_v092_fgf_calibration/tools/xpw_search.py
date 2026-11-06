"""Random + evolutionary calibration of XPW v0.9.2 + FGF inputs per symbol/timeframe.

In-sample (IS) selection, out-of-sample (OOS) validation. Only candidates that
are profitable in BOTH windows after modeled costs are accepted.
"""
import json, os, sys, time, random, datetime as dt
import numpy as np
from multiprocessing import Pool
import xpw_run as R

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT, exist_ok=True)

TS = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp())
TF_LABEL = {1: "M1", 5: "M5", 15: "M15", 30: "M30", 60: "H1", 240: "H4"}

# Points grids are defined for gold (tick 0.01 => 100 pts = $1); BTC uses x50.
GOLD_PTS = dict(
    SlPts=[300, 500, 700, 1000, 1500, 2000, 3000, 5000, 7000],
    TpPts=[0, 1000, 2000, 3000, 5000, 10000, 20000, 50000],
    TrActPts=[300, 500, 1000, 2000, 4000],
    TrDisPts=[100, 200, 300, 500, 1000],
    PredBuf=[0, 50, 100, 200, 400],
    ContStopBuf=[20, 50, 100, 200],
    LossRevTinyPts=[300, 500, 1000, 1500, 3000],
)
SPACE = dict(
    SigMode=[0, 1, 2, 3], TurnEntry=[0, 1, 2], ContEntry=[0, 1], OppMode=[0, 1, 2], ArmMode=[0, 1],
    CatchUp=[True, False], FailExit=[False, True],
    ExitUnit=[0, 1, 1], SlAtrM=[1.0, 1.5, 2.0, 3.0, 4.0, 6.0], TpR=[0.0, 1.0, 1.5, 2.0, 3.0, 5.0],
    TrailOn=[True, True, False], TrActAtr=[0.5, 1.0, 2.0, 4.0], TrDisAtr=[0.2, 0.5, 1.0, 2.0],
    TimeStop=[0, 0, 0, 6, 12, 24, 48, 96],
    LossRevOn=[True, False], LossRevWhat=[0, 1], LossRevMax=[1, 2, 3], LossRevTiny=[True, False],
    RsiLen=[7, 9, 14, 21], FastLen=[1, 2, 3], SlowLen=[5, 7, 9, 13, 21], AreaLook=[20, 40], LoFrac=[0.2, 0.3], HiFrac=[0.67, 0.75],
    AllOn=[True, False], AllCtx=[1, 2], BotMaxW=[2, 3, 5], BotCtxIn=[2, 3], BotSepIn=[3, 5, 10],
    TopMaxW=[2, 3, 5], TopCtxIn=[2, 3], TopSepIn=[3, 5, 10], TurnMax=[6, 12, 24], TurnHold=[1, 2, 3],
    BotWickRange=[0.45, 0.55, 0.65], BotWickAtr=[0.5, 0.8, 1.2], TopWickRange=[0.5, 0.6, 0.7], TopWickAtr=[0.6, 0.9, 1.2],
    ContBigAtr=[0.8, 1.0, 1.5, 2.0], ContLook=[20, 30, 50], ContNeedRed=[True, False], ContRedMax=[6, 12, 20],
    ContPinch=[1.0, 2.0, 4.0], ContAfter=[4, 6, 10], ContSep=[3, 5],
    fgfOn=[True, True, False], fgfTfMin=[15, 30, 60, 120, 240], fgfParentMin=[60, 120, 240, 480],
    fgfZoneSet=[(60, 120, 240), (60, 120, 240), (240, 480, 1440), (15, 30, 60), (30, 60, 240)],
    fgfMinAligned=[1, 2, 3], fgfBandAtr=[0.0, 0.1, 0.25, 0.5, 1.0], fgfAgainst=[True, False],
    fgfLast=[0, 0, 1, 2], fgfMinutes=[60, 120, 240, 480], fgfBars=[1, 2, 3, 6],
    fgfBurstAtr=[0.25, 0.5, 0.75, 1.0], fgfUseZones=[True, True, False], fgfFlatParent=[False, True],
    fgfAnyCombo=[False, False, True], fgfUseDrift=[False, False, True], fgfLvMode=[0, 1], fgfEntryDistAtr=[0.1, 0.25, 0.5],
    fgfUseBurst=[True, True, False],
)
PTS_KEYS = list(GOLD_PTS.keys())


def canonicalize(p):
    """Reset inputs that cannot influence the run so identical behaviors share one key."""
    D = R.DEFAULTS
    sig = int(p["SigMode"])
    if sig != 1:
        p["TurnEntry"] = D["TurnEntry"]; p["ArmMode"] = D["ArmMode"]; p["CatchUp"] = D["CatchUp"]; p["PredBuf"] = D["PredBuf"]
        p["FailExit"] = D["FailExit"]; p["MaxChase"] = D["MaxChase"]
    else:
        if int(p["TurnEntry"]) != 0: p["ArmMode"] = D["ArmMode"]; p["CatchUp"] = D["CatchUp"]; p["PredBuf"] = D["PredBuf"]; p["MaxChase"] = D["MaxChase"]
        if int(p["TurnEntry"]) == 2: p["FailExit"] = D["FailExit"]
    if sig != 3:
        p["ContEntry"] = D["ContEntry"]; p["ContStopBuf"] = D["ContStopBuf"]; p["ContStopBars"] = D["ContStopBars"]
        p["ContBigAtr"] = D["ContBigAtr"]; p["ContLook"] = D["ContLook"]; p["ContNeedRed"] = D["ContNeedRed"]; p["ContRedMax"] = D["ContRedMax"]
        p["ContPinch"] = D["ContPinch"]; p["ContAfter"] = D["ContAfter"]; p["ContSep"] = D["ContSep"]
    elif int(p["ContEntry"]) == 0:
        p["ContStopBuf"] = D["ContStopBuf"]; p["ContStopBars"] = D["ContStopBars"]
    if sig != 2:
        p["BotWickRange"] = D["BotWickRange"]; p["BotWickAtr"] = D["BotWickAtr"]; p["TopWickRange"] = D["TopWickRange"]; p["TopWickAtr"] = D["TopWickAtr"]
    if sig in (2, 3):
        p["TurnMax"] = D["TurnMax"]; p["TurnHold"] = D["TurnHold"]
        p["AllOn"] = D["AllOn"]; p["AllCtx"] = D["AllCtx"]; p["BotMaxW"] = D["BotMaxW"]; p["BotCtxIn"] = D["BotCtxIn"]; p["BotSepIn"] = D["BotSepIn"]
        p["TopMaxW"] = D["TopMaxW"]; p["TopCtxIn"] = D["TopCtxIn"]; p["TopSepIn"] = D["TopSepIn"]; p["LoFrac"] = D["LoFrac"]; p["HiFrac"] = D["HiFrac"]
        p["AreaLook"] = D["AreaLook"]
    if sig == 0:
        p["TurnMax"] = D["TurnMax"]; p["TurnHold"] = D["TurnHold"]
    if bool(p["AllOn"]):
        p["BotCtxIn"] = D["BotCtxIn"]; p["BotSepIn"] = D["BotSepIn"]; p["TopCtxIn"] = D["TopCtxIn"]; p["TopSepIn"] = D["TopSepIn"]
        p["LoFrac"] = D["LoFrac"]; p["HiFrac"] = D["HiFrac"]; p["AreaLook"] = D["AreaLook"]
    else:
        p["AllCtx"] = D["AllCtx"]
    if int(p["ExitUnit"]) == 0:
        p["SlAtrM"] = D["SlAtrM"]; p["TpR"] = D["TpR"]; p["TrActAtr"] = D["TrActAtr"]; p["TrDisAtr"] = D["TrDisAtr"]
        if not p["TrailOn"]: p["TrActPts"] = D["TrActPts"]; p["TrDisPts"] = D["TrDisPts"]
    else:
        p["SlPts"] = D["SlPts"]; p["TpPts"] = D["TpPts"]; p["TrActPts"] = D["TrActPts"]; p["TrDisPts"] = D["TrDisPts"]
        if not p["TrailOn"]: p["TrActAtr"] = D["TrActAtr"]; p["TrDisAtr"] = D["TrDisAtr"]
    if not p["LossRevOn"]:
        p["LossRevWhat"] = D["LossRevWhat"]; p["LossRevMax"] = D["LossRevMax"]; p["LossRevTiny"] = D["LossRevTiny"]; p["LossRevTinyPts"] = D["LossRevTinyPts"]
    elif not p["LossRevTiny"]:
        p["LossRevTinyPts"] = D["LossRevTinyPts"]
    if not p["fgfOn"]:
        for k in R.FGF_KEYS:
            if k != "fgfOn": p[k] = D[k]
    else:
        if int(p["fgfLast"]) != 1: p["fgfMinutes"] = D["fgfMinutes"]
        if int(p["fgfLast"]) != 2: p["fgfBars"] = D["fgfBars"]
        if not p["fgfAnyCombo"]: p["fgfUseBurst"] = D["fgfUseBurst"]
        if not p["fgfUseZones"]:
            p["fgfMinAligned"] = D["fgfMinAligned"]; p["fgfFlatParent"] = D["fgfFlatParent"]
            p["fgfParentTf"] = D["fgfParentTf"]; p["fgfZTf1"] = D["fgfZTf1"]; p["fgfZTf2"] = D["fgfZTf2"]; p["fgfZTf3"] = D["fgfZTf3"]
    return p


def sample(rng, symbol, tf):
    p = dict(R.DEFAULTS)
    p["SigTF"] = tf
    for k, v in SPACE.items():
        if k in ("fgfTfMin", "fgfParentMin", "fgfZoneSet"): continue
        p[k] = rng.choice(v)
    mult = 1 if symbol == "XAUUSD" else 50
    for k, v in GOLD_PTS.items():
        p[k] = float(rng.choice(v) * mult)
    if p["SlowLen"] <= p["FastLen"]: p["SlowLen"] = p["FastLen"] + 4
    # FGF timeframes: filter >= chart, parent >= filter
    ftf = rng.choice([m for m in SPACE["fgfTfMin"] if m >= tf] or [tf])
    ptf = rng.choice([m for m in SPACE["fgfParentMin"] if m >= ftf] or [ftf])
    p["fgfTf"] = R.TF_ENUM[ftf]; p["fgfParentTf"] = R.TF_ENUM[ptf]
    z = rng.choice(SPACE["fgfZoneSet"])
    p["fgfZTf1"], p["fgfZTf2"], p["fgfZTf3"] = (R.TF_ENUM[z[0]], R.TF_ENUM[z[1]], R.TF_ENUM[z[2]])
    p["QtyFixed"] = 1.0 if symbol == "XAUUSD" else 0.01
    p["QtyMax"] = p["QtyFixed"]
    return canonicalize(p)


def mutate(rng, p, symbol, tf, k_changes=2):
    q = dict(p)
    keys = list(SPACE.keys()) + PTS_KEYS
    for _ in range(k_changes):
        k = rng.choice(keys)
        if k == "fgfTfMin":
            ftf = rng.choice([m for m in SPACE["fgfTfMin"] if m >= tf] or [tf]); q["fgfTf"] = R.TF_ENUM[ftf]
            if R.ENUM_TF[q["fgfParentTf"]] < ftf: q["fgfParentTf"] = R.TF_ENUM[ftf]
        elif k == "fgfParentMin":
            ftf = R.ENUM_TF[q["fgfTf"]]
            q["fgfParentTf"] = R.TF_ENUM[rng.choice([m for m in SPACE["fgfParentMin"] if m >= ftf] or [ftf])]
        elif k == "fgfZoneSet":
            z = rng.choice(SPACE["fgfZoneSet"]); q["fgfZTf1"], q["fgfZTf2"], q["fgfZTf3"] = (R.TF_ENUM[z[0]], R.TF_ENUM[z[1]], R.TF_ENUM[z[2]])
        elif k in GOLD_PTS:
            mult = 1 if symbol == "XAUUSD" else 50
            q[k] = float(rng.choice(GOLD_PTS[k]) * mult)
        else:
            q[k] = rng.choice(SPACE[k])
    if q["SlowLen"] <= q["FastLen"]: q["SlowLen"] = q["FastLen"] + 4
    return canonicalize(q)


def evaluate(mk, p, is_lo, is_hi, oos_lo, oos_hi):
    r = mk.run(p)
    usd = mk.spec["usd_per_unit"]
    mi = R.metrics(r, is_lo, is_hi); mo = R.metrics(r, oos_lo, oos_hi); ma = R.metrics(r, is_lo, oos_hi)
    for m in (mi, mo, ma):
        for k in ("net", "maxdd", "avg"): m[k] *= usd
    return mi, mo, ma


def score(mi, min_trades):
    if mi["trades"] < min_trades or mi["net"] <= 0: return -1e9
    # consistency-weighted profit: net scaled by how smooth the equity curve is
    return mi["net"] * min(1.0, mi["rf"] / 4.0) * min(1.0, mi["pf"] - 0.95)


def job(args):
    symbol, tf, n_random, n_rounds, n_parents, n_children, seed = args
    rng = random.Random(seed)
    gold = symbol == "XAUUSD"
    if gold and tf <= 15:
        start = TS(2025, 5, 1); is_lo, is_hi, oos_lo, oos_hi = TS(2025, 5, 1), TS(2026, 4, 1), TS(2026, 4, 1), TS(2026, 11, 1)
        window = "2025-05..2026-10 (cent-precision gold proxy only)"
    else:
        start = None; is_lo, is_hi, oos_lo, oos_hi = TS(2023, 1, 1), TS(2025, 7, 1), TS(2025, 7, 1), TS(2026, 11, 1)
        window = "2023-01..2026-10"
    mk = R.Market(symbol, start=start)
    bars = len(mk.bars(tf)[0])
    # minimum trades scale with timeframe
    min_is = {1: 300, 5: 150, 15: 80, 30: 60, 60: 40, 240: 25}[tf]
    min_oos = max(10, min_is // 4)
    t0 = time.time()
    seen = {}
    rows = []

    def key(p):
        return json.dumps({k: p[k] for k in sorted(p)}, sort_keys=True, default=str)

    def consider(p, gen):
        k = key(p)
        if k in seen: return seen[k]
        mi, mo, ma = evaluate(mk, p, is_lo, is_hi, oos_lo, oos_hi)
        s = score(mi, min_is)
        row = dict(gen=gen, score=s, is_=mi, oos=mo, all=ma, params=p)
        seen[k] = row; rows.append(row)
        return row

    # baseline: reference-like defaults
    base = dict(R.DEFAULTS); base["SigTF"] = tf; base["QtyFixed"] = 1.0 if gold else 0.01; base["QtyMax"] = base["QtyFixed"]
    if not gold:
        for k in GOLD_PTS: base[k] = R.DEFAULTS[k] * 50 if k != "TpPts" else 50000.0 * 50
        base["SlPts"] = 20000.0
    consider(base, -1)
    for _ in range(n_random):
        consider(sample(rng, symbol, tf), 0)
    for rnd in range(1, n_rounds + 1):
        ranked = sorted(rows, key=lambda r: r["score"], reverse=True)
        parents = [r["params"] for r in ranked[:n_parents]]
        if not parents or ranked[0]["score"] <= -1e8: break
        for pi, par in enumerate(parents):
            for _ in range(n_children):
                consider(mutate(rng, par, symbol, tf, k_changes=rng.choice([1, 2, 3])), rnd)
    elapsed = time.time() - t0
    # acceptance: profitable IS and OOS, enough trades, PF >= 1.05 both
    candidates = [r for r in rows if r["is_"]["trades"] >= min_is and r["oos"]["trades"] >= min_oos
                  and r["is_"]["net"] > 0 and r["oos"]["net"] > 0 and r["is_"]["pf"] >= 1.15 and r["oos"]["pf"] >= 1.15]
    # balanced rank: the weaker of the annualised IS / OOS profits, weighted by the weaker profit factor
    yr_is = (is_hi - is_lo) / (365.25 * 86400); yr_oos = (oos_hi - oos_lo) / (365.25 * 86400)
    def balanced(r):
        return min(r["is_"]["net"] / yr_is, r["oos"]["net"] / yr_oos) * min(r["is_"]["pf"], r["oos"]["pf"], 3.0) * min(1.0, (r["all"]["rf"] if r["all"]["maxdd"] > 0 else 0) / 3.0)
    for r in rows: r["balanced"] = balanced(r) if r in candidates else 0.0
    candidates.sort(key=balanced, reverse=True)
    uniq = []; sigs = set()
    for r in candidates:
        sg = (r["all"]["trades"], round(r["all"]["net"], 4), r["is_"]["trades"], round(r["is_"]["net"], 4))
        if sg in sigs: continue
        sigs.add(sg); uniq.append(r)
    candidates = uniq
    # cost stress: spread and commission doubled must still leave a profit in both windows
    accepted = []
    usd = mk.spec["usd_per_unit"]
    for r in candidates[:80]:
        rr = mk.run(r["params"], cost_mult=2.0)
        si = R.metrics(rr, is_lo, is_hi); so_ = R.metrics(rr, oos_lo, oos_hi); sa = R.metrics(rr, is_lo, oos_hi)
        for m in (si, so_, sa):
            for k in ("net", "maxdd", "avg"): m[k] *= usd
        r["stress_is"] = si; r["stress_oos"] = so_; r["stress_all"] = sa
        if si["net"] > 0 and so_["net"] > 0:
            accepted.append(r)
    rb = mk.run(rows[0]["params"], cost_mult=2.0)
    rows[0]["stress_all"] = R.metrics(rb, is_lo, oos_hi)
    for k in ("net", "maxdd", "avg"): rows[0]["stress_all"][k] *= usd
    out = dict(symbol=symbol, tf=tf, tf_label=TF_LABEL[tf], bars=bars, window=window,
               is_window=[is_lo, is_hi], oos_window=[oos_lo, oos_hi], evaluated=len(rows), accepted=len(accepted),
               elapsed_s=elapsed, min_is_trades=min_is, min_oos_trades=min_oos,
               baseline=rows[0], top=accepted[:40], candidates_before_stress=len(candidates),
               all_rows=[dict(gen=r["gen"], score=r["score"], is_=r["is_"], oos=r["oos"], all=r["all"]) for r in rows])
    with open(os.path.join(OUT, f"{symbol}_{TF_LABEL[tf]}.json"), "w") as f:
        json.dump(out, f, default=str)
    return symbol, tf, len(rows), len(accepted), elapsed, (accepted[0]["all"] if accepted else None)


if __name__ == "__main__":
    quick = len(sys.argv) > 1 and sys.argv[1] == "quick"
    jobs = []
    seed = 20261106
    for symbol in ("XAUUSD", "BTCUSD"):
        for tf in (240, 60, 30, 15, 5, 1):
            if quick:
                n_random, n_rounds, n_parents, n_children = 40, 1, 4, 5
            elif tf == 1:
                n_random, n_rounds, n_parents, n_children = 400, 3, 12, 15
            elif tf == 5:
                n_random, n_rounds, n_parents, n_children = 800, 4, 15, 20
            else:
                n_random, n_rounds, n_parents, n_children = 1200, 5, 15, 25
            jobs.append((symbol, tf, n_random, n_rounds, n_parents, n_children, seed)); seed += 1
    # slow jobs first
    jobs.sort(key=lambda j: j[1])
    with Pool(4) as pool:
        for res in pool.imap_unordered(job, jobs):
            print(time.strftime("%H:%M:%S"), "done", res, flush=True)
    print("ALL DONE", flush=True)
