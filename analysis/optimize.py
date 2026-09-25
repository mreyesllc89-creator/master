"""Grid optimisation of the v2.4 inputs on the exported bars (stop-at-cross entry).

Parameters swept (all distances in ATR units): stop, target, trail activation, trail offset,
cross buffer, trade direction, time exit. Ranked by a robustness score, not by any single
timeframe, and the finalists are checked on a first-half / second-half split.

Usage: python3 analysis/optimize.py [spread_points] [commission_round_trip]
"""
import itertools, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import simulate as S
from simulate import load_bars, indicators, stats, FILES, ROOT, COST
from simulate_intrabar import cross_price, filters_ok

def arm_series(bars, I, maxd):
    """For each bar i, the (direction, cross price, atr) armed at the close of bar i-1, or None."""
    f, s = I["fast"], I["slow"]; out = [None] * len(bars)
    for i in range(1, len(bars)):
        k = i - 1
        if f[k] is None or s[k] is None or I["atr"][k] is None: continue
        d = 1 if f[k] <= s[k] else -1
        if not filters_ok(I, k, d): continue
        cp = cross_price(f[k], s[k]); dist = (cp - bars[k]["c"]) * d
        if dist < 0 or dist > maxd * I["atr"][k]: continue
        out[i] = (d, cp, I["atr"][k])
    return out

def run(bars, arms, p, lo=0, hi=None):
    """p: dict(sl, tp, act, off, buf, dirn, texit, n). act/off None = no trail. Returns trade pnl list."""
    hi = len(bars) if hi is None else hi
    tr = []; i = max(lo, 1)
    while i < hi - 1:
        a = arms[i]
        if a is None: i += 1; continue
        d, cp, atr = a
        if (p["dirn"] == "long" and d < 0) or (p["dirn"] == "short" and d > 0): i += 1; continue
        lvl = cp + d * p["buf"] * atr; b = bars[i]
        if not ((b["h"] >= lvl) if d > 0 else (b["l"] <= lvl)): i += 1; continue
        e = max(b["o"], lvl) if d > 0 else min(b["o"], lvl)
        sd, td = atr * p["sl"], atr * p["tp"]
        stop, tp = e - d * sd, e + d * td
        act = None if p["act"] is None else d * atr * p["act"]; off = None if p["off"] is None else atr * p["off"]
        trail_lvl = None; x = None
        if (b["c"] <= stop) if d > 0 else (b["c"] >= stop):
            x, j = b["c"], i
        else:
            j = i + 1
            while j < hi:
                bb = bars[j]; o, h, l, c = bb["o"], bb["h"], bb["l"], bb["c"]; fav = h if d > 0 else l
                if trail_lvl is not None and (l <= trail_lvl if d > 0 else h >= trail_lvl):
                    x = min(o, trail_lvl) if d > 0 else max(o, trail_lvl); break
                if (l <= stop) if d > 0 else (h >= stop):
                    x = min(o, stop) if d > 0 else max(o, stop); break
                if (h >= tp) if d > 0 else (l <= tp):
                    x = max(o, tp) if d > 0 else min(o, tp); break
                if act is not None:
                    if (fav - e) * d >= act * d:
                        cand = fav - d * off
                        trail_lvl = cand if trail_lvl is None else (max(trail_lvl, cand) if d > 0 else min(trail_lvl, cand))
                    if trail_lvl is not None and ((c <= trail_lvl) if d > 0 else (c >= trail_lvl)):
                        x = c; break
                held = j - i
                if p["texit"] == "hard" and held >= p["n"]: x = c; break
                if p["texit"] == "profit" and held >= p["n"] and (c - e) * d > 0: x = c; break
                j += 1
            if x is None: x, j = bars[hi - 1]["c"], hi - 1
        tr.append((x - e) * d - COST)
        i = j + 1
    return tr

def summary(pnls):
    if not pnls: return dict(n=0, net=0.0, pf=0.0, win=0.0, dd=0.0)
    g = sum(x for x in pnls if x > 0); l = -sum(x for x in pnls if x < 0)
    cum = peak = dd = 0.0
    for x in pnls:
        cum += x; peak = max(peak, cum); dd = min(dd, cum - peak)
    return dict(n=len(pnls), net=sum(pnls), pf=(g / l if l else 9.99), win=100 * sum(1 for x in pnls if x > 0) / len(pnls), dd=dd)

GRID = dict(
    sl=[1.0, 1.5, 2.0, 3.0],
    tp=[1.0, 1.5, 2.0, 3.0, 4.0],
    trail=[(None, None), (0.5, 0.3), (1.0, 0.3), (1.0, 0.6), (1.5, 0.5), (1.8, 0.6)],   # (activation, offset) in ATR; (1.8, 0.6) = v2 defaults with 2 ATR TP/SL
    buf=[0.1, 0.2, 0.3],
    dirn=["both", "long", "short"],
    texit=[("off", 0), ("profit", 4)],
)

if __name__ == "__main__":
    t0 = time.time()
    data = []
    for tf, fn in FILES:
        bars = load_bars(ROOT / "data" / "bars" / fn); I = indicators(bars)
        data.append((tf, bars, arm_series(bars, I, 2.0)))
    combos = list(itertools.product(GRID["sl"], GRID["tp"], GRID["trail"], GRID["buf"], GRID["dirn"], GRID["texit"]))
    print(f"cost ${COST:.2f}/round trip | {len(combos)} parameter sets x {len(data)} timeframes")
    results = []
    for sl, tp, (act, off), buf, dirn, (texit, n) in combos:
        p = dict(sl=sl, tp=tp, act=act, off=off, buf=buf, dirn=dirn, texit=texit, n=n)
        per = {tf: summary(run(bars, arms, p)) for tf, bars, arms in data}
        pooled_n = sum(s["n"] for s in per.values())
        pooled_net = sum(s["net"] for s in per.values())
        pos_tfs = sum(1 for s in per.values() if s["net"] > 0)
        avg_pf = sum(min(s["pf"], 5) for s in per.values()) / len(per)
        # robustness score: average capped PF, penalised unless most timeframes are positive
        score = avg_pf * (0.5 + pos_tfs / len(per))
        results.append((score, pooled_net, pooled_n, pos_tfs, avg_pf, p, per))
    results.sort(key=lambda r: -r[0])
    print(f"done in {time.time()-t0:.0f}s\n")

    def fmt(p):
        trail = "off" if p["act"] is None else "%.1f/%.1f" % (p["act"], p["off"])
        te = p["texit"] + (str(p["n"]) if p["texit"] != "off" else "")
        return "SL %.1f TP %.1f trail %-8s buf %.1f dir %-5s texit %s" % (p["sl"], p["tp"], trail, p["buf"], p["dirn"], te)
    tfs = [tf for tf, _, _ in data]
    print("=== Top 25 by robustness score (avg capped PF x share of positive timeframes) ===")
    print(f"{'score':>5s} {'net$':>6s} {'n':>4s} {'+TF':>3s} {'avgPF':>5s}  params" + " " * 44 + " | " + " ".join(f"{tf:>9s}" for tf in tfs))
    for score, net, n, pos, apf, p, per in results[:25]:
        print(f"{score:5.2f} {net:6.0f} {n:4d} {pos:3d} {apf:5.2f}  {fmt(p):60s} | " + " ".join(f"{per[tf]['net']:5.0f}/{min(per[tf]['pf'],9.9):.1f}" for tf in tfs))

    print("\n=== Best 'both directions' sets (no long/short bias) ===")
    both = [r for r in results if r[5]["dirn"] == "both"][:10]
    for score, net, n, pos, apf, p, per in both:
        print(f"{score:5.2f} {net:6.0f} {n:4d} {pos:3d} {apf:5.2f}  {fmt(p):60s} | " + " ".join(f"{per[tf]['net']:5.0f}/{min(per[tf]['pf'],9.9):.1f}" for tf in tfs))

    print("\n=== Best for the 15m chart alone (min 25 trades), for comparison ===")
    r15 = sorted([r for r in results if r[6]["15m"]["n"] >= 25], key=lambda r: -r[6]["15m"]["pf"])[:8]
    for score, net, n, pos, apf, p, per in r15:
        s = per["15m"]; print(f"15m n {s['n']:3d} net {s['net']:6.0f} PF {s['pf']:4.2f} win {s['win']:4.0f}% DD {s['dd']:6.0f}  {fmt(p)}")

    print("\n=== Split test on the finalists: first half vs second half of each export (net$/PF) ===")
    finalists = results[:5] + both[:3]
    seen = set()
    for score, net, n, pos, apf, p, per in finalists:
        key = fmt(p)
        if key in seen: continue
        seen.add(key)
        print(key)
        for tf, bars, arms in data:
            mid = len(bars) // 2
            a, b = summary(run(bars, arms, p, 0, mid)), summary(run(bars, arms, p, mid, None))
            print(f"    {tf:5s} 1st half {a['net']:6.0f}/{min(a['pf'],9.9):.1f} (n {a['n']:3d})   2nd half {b['net']:6.0f}/{min(b['pf'],9.9):.1f} (n {b['n']:3d})")
