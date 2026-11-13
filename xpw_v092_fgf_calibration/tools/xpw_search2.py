"""Run 2: stratified calibration. Every entry style x trade direction is searched
on its own for each symbol/timeframe, over a wider input grid, with stricter
validation: in-sample selection, out-of-sample check, 2x cost stress, calendar
block consistency, neighbour stability, and an untouched forward window."""
import json, os, sys, time, random, datetime as dt
import numpy as np
from multiprocessing import Pool
import xpw_run as R
import xpw_search as S1

QUICK = len(sys.argv) > 1 and sys.argv[1] == "quick"
OUT = os.environ.get("XPW_OUT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "results2_quick" if QUICK else "results2")
TS = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp())
TF_LABEL = {1: "M1", 5: "M5", 15: "M15", 30: "M30", 60: "H1", 240: "H4"}
YEAR = 365.25 * 86400
MIN_IS = {1: 300, 5: 150, 15: 80, 30: 60, 60: 40, 240: 25}
MIN_WIN_IS, MIN_WIN_OOS = 15, 8

# (SigMode, TurnEntry, ContEntry, label)
STYLES = [(0, None, None, "BOT/TOP square"), (1, 0, None, "Turn, predict stop"), (1, 1, None, "Turn, at cross"),
          (1, 2, None, "Turn, after hold"), (2, None, None, "BOT/TOP tick"), (3, None, 0, "CONT, at close"),
          (3, None, 1, "CONT, stop entry")]
DIRS = [(0, "Both"), (1, "Long only"), (2, "Short only")]
STRATUM_KEYS = ("SigMode", "TurnEntry", "ContEntry", "TradeDir", "SigTF")

GOLD_PTS = dict(
    SlPts=[200, 300, 500, 700, 1000, 1500, 2000, 3000, 5000, 7000, 10000],
    TpPts=[0, 500, 1000, 2000, 3000, 5000, 10000, 20000, 50000],
    TrActPts=[200, 300, 500, 1000, 2000, 4000],
    TrDisPts=[100, 200, 300, 500, 1000, 2000],
    PredBuf=[0, 50, 100, 200, 400],
    ContStopBuf=[20, 50, 100, 200],
    LossRevTinyPts=[300, 500, 1000, 1500, 3000],
    MaxChase=[0, 0, 200, 500, 1000],
)
SPACE = dict(
    OppMode=[0, 1, 2], ArmMode=[0, 1], CatchUp=[True, False], FailExit=[False, True], ContStopBars=[2, 3, 5],
    ExitUnit=[0, 1, 1], SlAtrM=[0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0], TpR=[0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0],
    TrailOn=[True, True, False], TrActAtr=[0.25, 0.5, 1.0, 2.0, 4.0, 6.0], TrDisAtr=[0.2, 0.5, 1.0, 2.0, 3.0],
    TimeStop=[0, 0, 0, 3, 6, 12, 24, 48, 96, 192], ExAtrLen=[7, 14, 21], AtrLen=[7, 14, 21],
    LossRevOn=[True, False], LossRevWhat=[0, 1], LossRevMax=[0, 1, 2, 3, 5], LossRevTiny=[True, False],
    RsiLen=[5, 7, 9, 14, 21, 28], FastLen=[1, 2, 3, 5], SlowLen=[3, 5, 7, 9, 13, 21, 34], InvertFill=[True, True, False],
    AreaLook=[20, 40, 60], LoFrac=[0.15, 0.2, 0.3], HiFrac=[0.67, 0.75, 0.85],
    AllOn=[True, False], AllCtx=[1, 2, 3], BotMinW=[1, 2], BotMaxW=[2, 3, 5, 8], BotCtxIn=[1, 2, 3], BotSepIn=[0, 3, 5, 10],
    TopMinW=[1, 2], TopMaxW=[2, 3, 5, 8], TopCtxIn=[1, 2, 3], TopSepIn=[0, 3, 5, 10], BotNeedLow=[True, True, False], TopNeedHigh=[True, True, False],
    TurnMax=[3, 6, 12, 24, 48], TurnHold=[1, 2, 3, 4],
    BotWickRange=[0.35, 0.45, 0.55, 0.65, 0.75], BotWickAtr=[0.3, 0.5, 0.8, 1.2, 1.6],
    TopWickRange=[0.35, 0.45, 0.55, 0.65, 0.75], TopWickAtr=[0.3, 0.5, 0.8, 1.2, 1.6],
    ContBigAtr=[0.6, 0.8, 1.0, 1.5, 2.0, 3.0], ContLook=[10, 20, 30, 50], ContNeedRed=[True, False], ContRedMax=[3, 6, 12, 20],
    ContPinch=[0.5, 1.0, 2.0, 4.0, 8.0], ContAfter=[2, 4, 6, 10], ContSep=[0, 3, 5, 10], ContMirror=[True],
    fgfTfMin=[5, 15, 30, 60, 120, 240, 480, 1440], fgfParentMin=[60, 120, 240, 480, 1440],
    fgfZoneSet=[(60, 120, 240), (60, 120, 240), (240, 480, 1440), (15, 30, 60), (30, 60, 240), (60, 240, 1440), (120, 240, 480)],
    fgfMinAligned=[1, 2, 3], fgfBandAtr=[0.0, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5], fgfAgainst=[True, False],
    fgfLast=[0, 0, 1, 2], fgfMinutes=[60, 120, 240, 480, 1440], fgfBars=[1, 2, 3, 6, 12],
    fgfBurstAtr=[0.25, 0.5, 0.75, 1.0, 1.5, 2.0], fgfUseZones=[True, True, False], fgfFlatParent=[False, True],
    fgfAnyCombo=[False, False, True], fgfUseDrift=[False, False, True], fgfDriftBars=[20, 60, 120], fgfLvMode=[0, 1],
    fgfEntryDistAtr=[0.0, 0.1, 0.25, 0.5], fgfUseBurst=[True, True, False], fgfHoldBars=[0, 0, 1, 2], fgfHoldFavAtr=[0.1, 0.25],
    fgfRsiLen=[9, 14, 21], fgfFastLen=[2, 3],
)
SPECIAL = ("fgfTfMin", "fgfParentMin", "fgfZoneSet")


def canonicalize(p):
    """Reset every input that cannot influence this run, so equal behaviours share one key.
    Soundness (reset inputs really are inert) is checked by canon_test.py."""
    D = R.DEFAULTS
    mult = 1.0 if float(p["QtyFixed"]) >= 1.0 else 50.0     # point inputs: BTC grid is 50x the gold grid
    keep_parent = p["fgfParentTf"]
    S1.canonicalize(p)
    sig = int(p["SigMode"])
    predict = sig == 1 and int(p["TurnEntry"]) == 0
    cont_stop = sig == 3 and int(p["ContEntry"]) == 1
    one_sided = int(p["TradeDir"]) != 0
    if sig == 2:
        for k in ("RsiLen", "FastLen", "SlowLen", "InvertFill"): p[k] = D[k]
    if sig in (2, 3):
        for k in ("BotMinW", "TopMinW", "BotNeedLow", "TopNeedHigh"): p[k] = D[k]
    if sig in (0, 1): p["AtrLen"] = D["AtrLen"]
    if int(p["ExitUnit"]) == 0: p["ExAtrLen"] = D["ExAtrLen"]
    if one_sided:
        # a reversal needs the other direction, which is not allowed
        p["LossRevOn"] = False
        for k in ("LossRevWhat", "LossRevMax", "LossRevTiny"): p[k] = D[k]
        if predict or cont_stop:
            if int(p["OppMode"]) == 2: p["OppMode"] = 0     # no opposite position can exist: Reverse == Ignore
        elif int(p["OppMode"]) == 1: p["OppMode"] = 0       # opposite entry is not allowed: Reverse == Close only
    squares_live = sig in (0, 1)
    if predict and int(p["ArmMode"]) == 1:
        # every cross arms the stop: squares, areas and turn timing are never read
        squares_live = False
        for k in ("AllOn", "AllCtx", "BotMinW", "BotMaxW", "BotCtxIn", "BotSepIn", "BotNeedLow", "TopMinW", "TopMaxW", "TopCtxIn", "TopSepIn",
                  "TopNeedHigh", "LoFrac", "HiFrac", "AreaLook", "TurnMax", "InvertFill"): p[k] = D[k]
        if not p["FailExit"]: p["TurnHold"] = D["TurnHold"]
    if predict and one_sided and int(p["ArmMode"]) == 0 and int(p["OppMode"]) != 1:
        side = ("TopMinW", "TopMaxW", "TopCtxIn", "TopSepIn", "TopNeedHigh", "HiFrac") if int(p["TradeDir"]) == 1 else \
               ("BotMinW", "BotMaxW", "BotCtxIn", "BotSepIn", "BotNeedLow", "LoFrac")
        for k in side: p[k] = D[k]
    if squares_live:
        if p["AllOn"]:
            p["BotNeedLow"] = D["BotNeedLow"]; p["TopNeedHigh"] = D["TopNeedHigh"]
        else:
            if not p["BotNeedLow"]: p["LoFrac"] = D["LoFrac"]
            if not p["TopNeedHigh"]: p["HiFrac"] = D["HiFrac"]
            if not p["BotNeedLow"] and not p["TopNeedHigh"]: p["AreaLook"] = D["AreaLook"]
    if p["fgfOn"]:
        if int(p["fgfHoldBars"]) == 0: p["fgfHoldFavAtr"] = D["fgfHoldFavAtr"]
        if not p["fgfUseDrift"]: p["fgfDriftBars"] = D["fgfDriftBars"]
        parent_live = p["fgfUseZones"] or (p["fgfAnyCombo"] and p["fgfUseBurst"])
        if parent_live and not p["fgfUseZones"]: p["fgfParentTf"] = keep_parent      # run-1 canonicalize reset it although it is read
        if not parent_live:
            p["fgfRsiLen"] = D["fgfRsiLen"]; p["fgfFastLen"] = D["fgfFastLen"]
        if int(p["fgfLvMode"]) == 1: p["fgfEntryDistAtr"] = D["fgfEntryDistAtr"]
        if p["fgfAnyCombo"] and not p["fgfUseBurst"]: p["fgfBurstAtr"] = D["fgfBurstAtr"]
    # inert point inputs take the symbol-scaled default, so a later mutation re-activates them on the symbol's own grid
    inert = []
    if int(p["ExitUnit"]) != 0: inert += ["SlPts", "TpPts", "TrActPts", "TrDisPts"]
    elif not p["TrailOn"]: inert += ["TrActPts", "TrDisPts"]
    if not predict: inert.append("PredBuf")
    if not (predict and p["CatchUp"]): inert.append("MaxChase")
    if not cont_stop: inert.append("ContStopBuf")
    if not (p["LossRevOn"] and p["LossRevTiny"]): inert.append("LossRevTinyPts")
    for k in inert: p[k] = D[k] * mult
    if int(p["SlowLen"]) <= int(p["FastLen"]): p["SlowLen"] = int(p["FastLen"]) + 4
    return p


def _set_special(rng, q, k, tf):
    if k == "fgfTfMin":
        ftf = rng.choice([m for m in SPACE["fgfTfMin"] if m >= tf] or [tf]); q["fgfTf"] = R.TF_ENUM[ftf]
        if R.ENUM_TF[q["fgfParentTf"]] < ftf:
            q["fgfParentTf"] = R.TF_ENUM[min([m for m in SPACE["fgfParentMin"] if m >= ftf] or [ftf])]
    elif k == "fgfParentMin":
        ftf = R.ENUM_TF[q["fgfTf"]]
        q["fgfParentTf"] = R.TF_ENUM[rng.choice([m for m in SPACE["fgfParentMin"] if m >= ftf] or [ftf])]
    else:
        z = rng.choice(SPACE["fgfZoneSet"]); q["fgfZTf1"], q["fgfZTf2"], q["fgfZTf3"] = (R.TF_ENUM[z[0]], R.TF_ENUM[z[1]], R.TF_ENUM[z[2]])


def sample(rng, symbol, tf, style, direction, fgf_on):
    return canonicalize(sample_raw(rng, symbol, tf, style, direction, fgf_on))


def sample_raw(rng, symbol, tf, style, direction, fgf_on):
    p = dict(R.DEFAULTS)
    p["SigTF"] = tf
    for k, v in SPACE.items():
        if k not in SPECIAL: p[k] = rng.choice(v)
    mult = 1 if symbol == "XAUUSD" else 50
    for k, v in GOLD_PTS.items(): p[k] = float(rng.choice(v) * mult)
    p["SigMode"] = style[0]
    p["TurnEntry"] = style[1] if style[1] is not None else R.DEFAULTS["TurnEntry"]
    p["ContEntry"] = style[2] if style[2] is not None else R.DEFAULTS["ContEntry"]
    p["TradeDir"] = direction
    p["fgfOn"] = fgf_on
    p["fgfTf"] = R.TF_ENUM[60]; p["fgfParentTf"] = R.TF_ENUM[60]
    _set_special(rng, p, "fgfTfMin", tf); _set_special(rng, p, "fgfParentMin", tf); _set_special(rng, p, "fgfZoneSet", tf)
    p["QtyFixed"] = 1.0 if symbol == "XAUUSD" else 0.01
    p["QtyMax"] = p["QtyFixed"]
    return p


MUT_KEYS = [k for k in list(SPACE.keys()) + list(GOLD_PTS.keys()) + ["fgfOn"]]


def mutate(rng, p, symbol, tf, k_changes):
    """Change k inputs; retried until the canonical parameter set really differs from the parent."""
    base = key_of(p); mult = 1 if symbol == "XAUUSD" else 50
    q = dict(p)
    for _ in range(40):
        q = dict(p)
        for _ in range(k_changes):
            k = rng.choice(MUT_KEYS)
            if k in SPECIAL: _set_special(rng, q, k, tf)
            elif k == "fgfOn": q[k] = not q[k]
            else:
                vals = sorted({float(v * mult) for v in GOLD_PTS[k]} if k in GOLD_PTS else set(SPACE[k]))
                vals = [v for v in vals if v != q[k]]
                if vals: q[k] = rng.choice(vals)
        q = canonicalize(q)
        if key_of(q) != base: return q
    return q


WARMUP = 120 * 86400


def windows(symbol, tf):
    """Data starts WARMUP before the in-sample window (indicator and filter warm-up only: no entry before is_[0])."""
    if symbol == "XAUUSD" and tf <= 15:
        # PAX Gold is quoted in cents only from 2025-05-16; the window starts on the first full day after that
        w = dict(is_=(TS(2025, 5, 17), TS(2026, 4, 1)), oos=(TS(2026, 4, 1), TS(2026, 11, 1)),
                 blocks=[TS(2025, 5, 17), TS(2025, 11, 1), TS(2026, 5, 1), TS(2026, 11, 1)], label="2025-05-17 to 2026-10")
    else:
        w = dict(is_=(TS(2023, 1, 1), TS(2025, 7, 1)), oos=(TS(2025, 7, 1), TS(2026, 11, 1)),
                 blocks=[TS(2023, 1, 1), TS(2024, 1, 1), TS(2025, 1, 1), TS(2026, 1, 1), TS(2026, 11, 1)], label="2023-01 to 2026-10")
    w["start"] = w["is_"][0] - WARMUP
    w["fwd"] = (w["oos"][1], None)      # everything after the out-of-sample window, incl. the end-of-data mark
    return w


_MK = {}


def market(symbol, start):
    key = (symbol, start)
    if key not in _MK:
        _MK.clear()
        _MK[key] = R.Market(symbol, start=start)
    return _MK[key]


def key_of(p):
    return json.dumps({k: p[k] for k in sorted(p)}, sort_keys=True, default=str)


def run(mk, p, w, cost_mult=1.0):
    return mk.run(p, cost_mult=cost_mult, trade_from=w["is_"][0])


def usd_metrics(mk, res, lo, hi):
    m = R.metrics(res, lo, hi)
    for k in ("net", "maxdd", "avg"): m[k] *= mk.spec["usd_per_unit"]
    return m


def is_score(mi, min_trades):
    if mi["trades"] < min_trades or mi["net"] <= 0: return -1e9
    return mi["net"] * min(1.0, mi["rf"] / 4.0) * min(1.0, mi["pf"] - 0.95)


def balanced(r, w):
    yi = (w["is_"][1] - w["is_"][0]) / YEAR; yo = (w["oos"][1] - w["oos"][0]) / YEAR
    return min(r["is_"]["net"] / yi, r["oos"]["net"] / yo) * min(r["is_"]["pf"], r["oos"]["pf"], 3.0) * min(1.0, r["all"]["rf"] / 3.0)


def passes_basic(r, min_is, min_oos):
    return (r["is_"]["trades"] >= min_is and r["oos"]["trades"] >= min_oos and r["is_"]["net"] > 0 and r["oos"]["net"] > 0
            and r["is_"]["pf"] >= 1.15 and r["oos"]["pf"] >= 1.15)


def trade_sig(res, lo=None, hi=None):
    """Trade list as a hashable signature, optionally only trades closing in [lo, hi)."""
    m = np.ones(int(res["n"]), bool)
    if res["n"] and (lo is not None or hi is not None):
        xt = res["time"][res["exit_i"]]
        if lo is not None: m &= xt >= lo
        if hi is not None: m &= xt < hi
    return (int(m.sum()), res["entry_i"][m].tobytes(), res["exit_i"][m].tobytes(), res["side"][m].tobytes(), np.round(res["pnl"][m], 8).tobytes())


def stratum_file(symbol, tf, si, direction):
    return os.path.join(OUT, "strata", f"{symbol}_{TF_LABEL[tf]}_{si}_{direction}.json")


def stratum_task(args):
    symbol, tf, si, direction, budget, seed = args
    n_random, n_rounds, n_parents, n_children, keep = budget
    style = STYLES[si]
    w = windows(symbol, tf)
    mk = market(symbol, w["start"])
    for c in (mk._ind, mk._evt, mk._fgf): c.clear()
    rng = random.Random(seed)
    min_is = MIN_IS[tf]; min_oos = max(10, min_is // 4)
    t0 = time.time(); seen = {}; rows = []

    def consider(p, gen):
        k = key_of(p)
        if k in seen: return
        res = run(mk, p, w)
        row = dict(gen=gen, params=p, is_=usd_metrics(mk, res, *w["is_"]), oos=usd_metrics(mk, res, *w["oos"]),
                   all=usd_metrics(mk, res, w["is_"][0], w["oos"][1]))
        row["score"] = is_score(row["is_"], min_is)
        seen[k] = row; rows.append(row)

    for i in range(n_random):
        consider(sample(rng, symbol, tf, style, direction, i % 2 == 0), 0)
    for rnd in range(1, n_rounds + 1):
        ranked = sorted(rows, key=lambda r: r["score"], reverse=True)
        if ranked[0]["score"] <= -1e8: break
        # parents: best distinct behaviours, so clones do not crowd the parent set
        parents = []; psig = set()
        for r in ranked:
            sg = (r["all"]["trades"], round(r["all"]["net"], 4))
            if sg in psig or r["score"] <= -1e8: continue
            psig.add(sg); parents.append(r["params"])
            if len(parents) == n_parents: break
        for par in parents:
            for _ in range(n_children):
                consider(mutate(rng, par, symbol, tf, rng.choice([1, 2, 3])), rnd)
    n_is_pos = sum(1 for r in rows if r["score"] > -1e8)
    cands = [r for r in rows if passes_basic(r, min_is, min_oos)]
    cands.sort(key=lambda r: balanced(r, w), reverse=True)
    uniq = []; sigs = set()
    for r in cands:
        sg = (r["all"]["trades"], round(r["all"]["net"], 4), r["is_"]["trades"], round(r["is_"]["net"], 4))
        if sg in sigs: continue
        sigs.add(sg); uniq.append(r)
    out = []
    for r in uniq[:keep]:
        full_score(mk, w, r); r["style"] = style[3]; r["style_i"] = si; r["direction"] = direction
        out.append(r)
    best = max(rows, key=lambda r: r["score"])
    result = dict(symbol=symbol, tf=tf, style_i=si, style=style[3], direction=direction, evaluated=len(rows), is_profitable=n_is_pos,
                  pass_is_oos=len(cands), pass_is_oos_distinct=len(uniq), best_is_net=best["is_"]["net"] if best["score"] > -1e8 else None,
                  best_is_oos_net=best["oos"]["net"] if best["score"] > -1e8 else None, elapsed=time.time() - t0, candidates=out,
                  stamp=stamp_for(symbol, tf, budget, seed))
    tmp = stratum_file(symbol, tf, si, direction) + ".tmp"
    json.dump(result, open(tmp, "w"), default=str); os.replace(tmp, stratum_file(symbol, tf, si, direction))
    return {k: v for k, v in result.items() if k != "candidates"}


def full_score(mk, w, r):
    """All window figures of one candidate: in-sample, out-of-sample, both, calendar blocks, unseen days, 2x costs."""
    res = run(mk, r["params"], w)
    r["is_"] = usd_metrics(mk, res, *w["is_"]); r["oos"] = usd_metrics(mk, res, *w["oos"]); r["all"] = usd_metrics(mk, res, w["is_"][0], w["oos"][1])
    r["blocks"] = [usd_metrics(mk, res, w["blocks"][i], w["blocks"][i + 1])["net"] for i in range(len(w["blocks"]) - 1)]
    r["fwd"] = usd_metrics(mk, res, *w["fwd"])
    rs = run(mk, r["params"], w, cost_mult=2.0)
    r["stress_is"] = usd_metrics(mk, rs, *w["is_"]); r["stress_oos"] = usd_metrics(mk, rs, *w["oos"])
    r["stress_all"] = usd_metrics(mk, rs, w["is_"][0], w["oos"][1])
    r["balanced"] = balanced(r, w)
    return r


def stamp_for(symbol, tf, budget, seed):
    w = windows(symbol, tf)
    return dict(budget=list(budget), seed=seed, is_=list(w["is_"]), oos=list(w["oos"]), blocks=list(w["blocks"]), start=w["start"], min_is=MIN_IS[tf])


def stratum_done(symbol, tf, si, d, budget, seed):
    """A saved stratum is reused only if it was produced with the same budget, seed and windows."""
    f = stratum_file(symbol, tf, si, d)
    if not os.path.exists(f): return False
    try: return json.load(open(f)).get("stamp") == stamp_for(symbol, tf, budget, seed)
    except Exception: return False


def rescore_task(args):
    """Re-score the saved candidates of one stratum with the current accounting and re-apply the IS/OOS gate."""
    symbol, tf, si, d = args
    s = json.load(open(stratum_file(symbol, tf, si, d)))
    w = windows(symbol, tf); mk = market(symbol, w["start"])
    for c in (mk._ind, mk._evt, mk._fgf): c.clear()
    min_is = MIN_IS[tf]; min_oos = max(10, min_is // 4)
    kept = []
    for r in s["candidates"]:
        full_score(mk, w, r)
        if passes_basic(r, min_is, min_oos): kept.append(r)
    s["saved"] = len(s["candidates"]); s["candidates"] = kept
    return s


def accept(r):
    """Stress, winners and block-consistency rules applied on top of the basic IS/OOS filter."""
    if not (r["stress_is"]["net"] > 0 and r["stress_oos"]["net"] > 0): return False
    if r["is_"]["wins"] < MIN_WIN_IS or r["oos"]["wins"] < MIN_WIN_OOS: return False
    return sum(1 for b in r["blocks"] if b <= 0) <= 1


N_NEIGHBOURS, MIN_NEIGHBOURS, MIN_STABLE = 24, 12, 0.5


def stability_task(args):
    """Share of neighbours that stay profitable overall and out of sample. A neighbour changes one input to
    another value of its search grid (any value, not only the adjacent one) and only counts if its trades in the
    scored windows differ from the base and from every earlier neighbour."""
    symbol, tf, plist, seed = args
    w = windows(symbol, tf); mk = market(symbol, w["start"])
    for c in (mk._ind, mk._evt, mk._fgf): c.clear()
    rng = random.Random(seed); out = []
    for p in plist:
        lo, hi = w["is_"][0], w["oos"][1]       # neighbours must differ inside the scored windows
        keys = {key_of(p)}; sigs = {trade_sig(run(mk, p, w), lo, hi)}; ok = 0; n = 0; tries = 0
        while n < N_NEIGHBOURS and tries < 240:
            tries += 1
            q = mutate(rng, p, symbol, tf, 1)
            k = key_of(q)
            if k in keys: continue
            keys.add(k)
            res = run(mk, q, w); sg = trade_sig(res, lo, hi)
            if sg in sigs: continue          # same trades as the base or an earlier neighbour: not a real neighbour
            sigs.add(sg); n += 1
            if R.metrics(res, w["is_"][0], w["oos"][1])["net"] > 0 and R.metrics(res, *w["oos"])["net"] > 0: ok += 1
        out.append(dict(neighbours=n, stable_share=ok / n if n else 0.0))
    return symbol, tf, out


def baseline_task(args):
    symbol, tf = args
    w = windows(symbol, tf); mk = market(symbol, w["start"])
    base = dict(R.DEFAULTS); base["SigTF"] = tf; base["QtyFixed"] = 1.0 if symbol == "XAUUSD" else 0.01; base["QtyMax"] = base["QtyFixed"]
    if symbol != "XAUUSD":
        for k in S1.GOLD_PTS: base[k] = R.DEFAULTS[k] * 50 if k != "TpPts" else 50000.0 * 50
        base["SlPts"] = 20000.0
    res = run(mk, base, w)
    k0 = int(np.searchsorted(mk.bars(tf)[0], w["is_"][0]))
    return symbol, tf, usd_metrics(mk, res, w["is_"][0], w["oos"][1]), len(mk.bars(tf)[0]) - k0


def is_stable(r):
    return r["stability"]["neighbours"] >= MIN_NEIGHBOURS and r["stability"]["stable_share"] >= MIN_STABLE


def merge(pool, pairs):
    """Merge the saved strata per symbol/timeframe, apply acceptance, check neighbour stability for the overall
    leaders AND the leaders of every way of playing, and write one JSON per symbol/timeframe."""
    merged = {}; todo = []; by_pair = {}
    for symbol, tf in pairs:
        have = [(symbol, tf, si, d) for si in range(len(STYLES)) for d, _ in DIRS if os.path.exists(stratum_file(symbol, tf, si, d))]
        if len(have) != len(STYLES) * len(DIRS):
            print("incomplete", symbol, TF_LABEL[tf], len(have), flush=True); continue
        todo += have
    for s in pool.imap_unordered(rescore_task, todo):
        by_pair.setdefault((s["symbol"], s["tf"]), []).append(s)
    for symbol, tf in pairs:
        if (symbol, tf) not in by_pair: continue
        ss = by_pair[(symbol, tf)]
        cands = sorted([c for s in ss for c in s["candidates"]], key=lambda r: r["balanced"], reverse=True)
        acc = [r for r in cands if accept(r)]
        chk = list(acc[:30]); ids = {id(r) for r in chk}; per = {}
        for r in acc:
            k = (r["style_i"], r["direction"]); per[k] = per.get(k, 0) + 1
            if per[k] <= 5 and id(r) not in ids: chk.append(r); ids.add(id(r))
        chk.sort(key=lambda r: r["balanced"], reverse=True)
        merged[(symbol, tf)] = (ss, cands, acc, chk)
    stab_tasks = [(symbol, tf, [r["params"] for r in chk], 7700 + tf + (0 if symbol == "BTCUSD" else 5000))      # seed fixed per pair
                  for (symbol, tf), (ss, cands, acc, chk) in merged.items() if chk]
    for symbol, tf, out in pool.imap_unordered(stability_task, stab_tasks):
        chk = merged[(symbol, tf)][3]
        assert len(out) == len(chk)
        for r, s in zip(chk, out): r["stability"] = s
        print(time.strftime("%H:%M:%S"), "stability", symbol, TF_LABEL[tf], len(chk), flush=True)
    bases = {(s, tf): (m, bars) for s, tf, m, bars in pool.imap_unordered(baseline_task, list(merged.keys()))}
    for (symbol, tf), (ss, cands, acc, chk) in merged.items():
        w = windows(symbol, tf)
        final = [r for r in chk if is_stable(r)]
        out = dict(symbol=symbol, tf=tf, tf_label=TF_LABEL[tf], window=w["label"], is_window=list(w["is_"]), oos_window=list(w["oos"]),
                   blocks=w["blocks"], bars=bases[(symbol, tf)][1], baseline=bases[(symbol, tf)][0],
                   evaluated=sum(s["evaluated"] for s in ss), pass_is_oos=sum(s["pass_is_oos_distinct"] for s in ss),
                   rules_tested=len(cands), pass_rules=len(acc), checked_for_stability=len(chk), final=len(final),
                   strata=[dict({k: v for k, v in s.items() if k not in ("candidates", "stamp")}, rules_tested=len(s["candidates"]),
                                pass_rules=sum(1 for c in s["candidates"] if accept(c)))
                           for s in sorted(ss, key=lambda s: (s["style_i"], s["direction"]))],
                   top=final, unstable=[r for r in chk if not is_stable(r)])
        json.dump(out, open(os.path.join(OUT, f"{symbol}_{TF_LABEL[tf]}.json"), "w"), default=str)
        print("job", symbol, TF_LABEL[tf], "evaluated", out["evaluated"], "pass IS+OOS", out["pass_is_oos"], "pass rules", len(acc),
              "checked", len(chk), "final", len(final), flush=True)


def budget_for(tf, quick):
    if quick: return (24, 1, 3, 4, 10)
    if tf == 1: return (80, 2, 6, 8, 25)
    if tf == 5: return (200, 2, 8, 10, 40)
    return (500, 4, 12, 15, 60)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    quick = mode == "quick"
    os.makedirs(os.path.join(OUT, "strata"), exist_ok=True)
    tasks = []; seed = 20261113
    pairs = [(s, tf) for s in ("BTCUSD", "XAUUSD") for tf in (1, 5, 15, 30, 60, 240)]
    if quick: pairs = [("XAUUSD", 60), ("BTCUSD", 240)]
    for symbol, tf in pairs:
        for si in range(len(STYLES)):
            for d, _ in DIRS:
                seed += 1
                if not stratum_done(symbol, tf, si, d, budget_for(tf, quick), seed):      # resumable: matching finished strata are kept
                    tasks.append((symbol, tf, si, d, budget_for(tf, quick), seed))
    t0 = time.time()
    with Pool(4, maxtasksperchild=8) as pool:
        if mode != "merge":
            for n, res in enumerate(pool.imap_unordered(stratum_task, tasks), 1):
                print(time.strftime("%H:%M:%S"), f"stratum {n}/{len(tasks)}", res["symbol"], TF_LABEL[res["tf"]], res["style"], DIRS[res["direction"]][1],
                      "evaluated", res["evaluated"], "pass", res["pass_is_oos_distinct"], "%.0fs" % res["elapsed"], flush=True)
        merge(pool, pairs)
    print("ALL DONE %.1f min" % ((time.time() - t0) / 60), flush=True)
