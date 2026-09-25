"""Same-candle early entry: a stop order at the price where the EMA 5/13 cross will occur.

At the close of bar t-1 the EMAs F (fast) and S (slow) are known. On bar t each EMA updates as
a*close + (1-a)*prev, so the close that makes them equal is

    cross = ((1 - a_s) * S - (1 - a_f) * F) / (a_f - a_s)

A stop order at that price fills the moment bar t trades through it, which is inside the same
candle in which the close-based cross would later be confirmed, and usually at a better price.
The risk is a fill on a bar that later closes back on the wrong side (an unconfirmed cross).

Usage: python3 analysis/simulate_intrabar.py [spread_points] [commission_round_trip]
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import simulate as S
from simulate import load_bars, indicators, filtered_signal, v_base, stats, FILES, ROOT, COST

A_F, A_S = 2 / 6, 2 / 14

def cross_price(F, Sl):
    return ((1 - A_S) * Sl - (1 - A_F) * F) / (A_F - A_S)

def filters_ok(I, i, d):
    if I["trend"][i] is None or I["rsi"][i] is None or I["atr"][i] is None: return False
    if d > 0: return I["c"][i] > I["trend"][i] and I["regime"][i] and I["rsi"][i] < 70
    return I["c"][i] < I["trend"][i] and I["regime"][i] and I["rsi"][i] > 30

def run_exits(bars, I, i_entry, e, d, atr, time_mode, n_bars, entry_bar_stop_check=True):
    """Exit evaluation starting on the entry bar (stop vs close only) then normal bars after."""
    sd, td = atr * 2.0, atr * 2.0
    stop, tp = e - d * sd, e + d * td
    act, off = d * td * 0.9, sd * 0.3
    N = len(bars); trail_lvl = None
    b = bars[i_entry]
    if entry_bar_stop_check and ((b["c"] <= stop) if d > 0 else (b["c"] >= stop)):
        return i_entry, b["c"], "stop_entrybar"
    j = i_entry + 1
    while j < N:
        b = bars[j]; o, h, l, c = b["o"], b["h"], b["l"], b["c"]
        fav = h if d > 0 else l
        if trail_lvl is not None and (l <= trail_lvl if d > 0 else h >= trail_lvl):
            return j, (min(o, trail_lvl) if d > 0 else max(o, trail_lvl)), "trail"
        if (l <= stop) if d > 0 else (h >= stop):
            return j, (min(o, stop) if d > 0 else max(o, stop)), "stop"
        if (h >= tp) if d > 0 else (l <= tp):
            return j, (max(o, tp) if d > 0 else min(o, tp)), "tp"
        if (fav - e) * d >= act * d:
            cand = fav - d * off
            trail_lvl = cand if trail_lvl is None else (max(trail_lvl, cand) if d > 0 else min(trail_lvl, cand))
        if trail_lvl is not None and ((c <= trail_lvl) if d > 0 else (c >= trail_lvl)):
            return j, c, "trail"
        held = j - i_entry
        if time_mode == "hard" and held >= n_bars: return j, c, "time"
        if time_mode == "profit" and held >= n_bars and (c - e) * d > 0: return j, c, "time_profit"
        j += 1
    return N - 1, bars[N - 1]["c"], "open"

def sim_close_entry(bars, I, time_mode, n):
    tr = []; i = 0
    while i < len(bars) - 1:
        d = filtered_signal(I, v_base, i)
        if d == 0: i += 1; continue
        e = bars[i]["c"]
        j, x, r = run_exits(bars, I, i, e, d, I["atr"][i], time_mode, n, entry_bar_stop_check=False)
        tr.append(dict(i=i, j=j, d=d, e=e, x=x, pnl=(x - e) * d - COST, held=j - i, reason=r, ref_close=e))
        i = j + 1
    return tr

def sim_stop_entry(bars, I, time_mode, n, max_dist_atr=1.0):
    """At close of bar i-1: if fast is on the wrong side and filters pass, arm a stop at the cross price for bar i."""
    tr = []; i = 1; f, s = I["fast"], I["slow"]
    while i < len(bars) - 1:
        k = i - 1
        if f[k] is None or s[k] is None or I["atr"][k] is None: i += 1; continue
        d = 1 if f[k] <= s[k] else -1
        if not filters_ok(I, k, d): i += 1; continue
        cp = cross_price(f[k], s[k])
        # only arm if the cross price is ahead of the current close and within max_dist_atr of it
        dist = (cp - bars[k]["c"]) * d
        if dist < 0 or dist > max_dist_atr * I["atr"][k]: i += 1; continue
        b = bars[i]
        hit = (b["h"] >= cp) if d > 0 else (b["l"] <= cp)
        if not hit: i += 1; continue
        e = max(b["o"], cp) if d > 0 else min(b["o"], cp)   # gap through the level fills at the open
        confirmed = (b["c"] > cp) if d > 0 else (b["c"] < cp)
        j, x, r = run_exits(bars, I, i, e, d, I["atr"][k], time_mode, n)
        tr.append(dict(i=i, j=j, d=d, e=e, x=x, pnl=(x - e) * d - COST, held=j - i, reason=r,
                       confirmed=confirmed, ref_close=b["c"], improve=(b["c"] - e) * d))
        i = j + 1
    return tr

if __name__ == "__main__":
    print(f"cost per round trip ${COST:.2f} | regime filter: {S.REGIME}\n")
    print("=== Same-candle stop entry at the EMA cross price vs. entry at the signal bar close (no time exit) ===")
    print(f"{'TF':5s} {'entry':22s} {'n':>4s} {'net$':>8s} {'PF':>6s} {'win%':>6s} {'avg$':>7s} {'maxDD':>8s} | {'confirmed%':>10s} {'fill vs close':>13s} {'in ATR':>7s}")
    pooled = {}
    for tf, fn in FILES:
        bars = load_bars(ROOT / "data" / "bars" / fn); I = indicators(bars)
        for label, tr in (("close of signal bar", sim_close_entry(bars, I, "off", 0)),
                          ("stop at cross price", sim_stop_entry(bars, I, "off", 0))):
            st = stats(tr)
            extra = ""
            if "confirmed" in (tr[0] if tr else {}):
                conf = 100 * sum(1 for t in tr if t["confirmed"]) / len(tr)
                imp = sum(t["improve"] for t in tr) / len(tr)
                atr_avg = sum(I["atr"][t["i"]] for t in tr) / len(tr)
                extra = f"| {conf:10.1f} {imp:13.3f} {imp/atr_avg:7.2f}"
            print(f"{tf:5s} {label:22s} {st['n']:4d} {st['net']:8.1f} {st['pf']:6.2f} {st['win']:6.1f} {st['avg']:7.2f} {st['dd']:8.1f} {extra}")
            pooled.setdefault(label, []).append(st)
    for label, v in pooled.items():
        print(f"sum   {label:22s} net {sum(s['net'] for s in v):8.0f}  avgPF {sum(min(s['pf'],10) for s in v)/len(v):.2f}  win% {sum(s['win'] for s in v)/len(v):.1f}")

    print("\n=== Stop-at-cross entry with the profit-aware time exit (net$/PF) ===")
    cols = [("off", 0)] + [("profit", n) for n in (1, 2, 3, 4, 6)] + [("hard", n) for n in (2, 4)]
    print(f"{'TF':5s} " + " ".join(f"{m+str(n) if m!='off' else 'off':>10s}" for m, n in cols))
    tot = {c: 0.0 for c in cols}
    for tf, fn in FILES:
        bars = load_bars(ROOT / "data" / "bars" / fn); I = indicators(bars)
        row = []
        for c in cols:
            st = stats(sim_stop_entry(bars, I, *c)); tot[c] += st["net"]
            row.append(f"{st['net']:5.0f}/{min(st['pf'],9.9):.1f}")
        print(f"{tf:5s} " + " ".join(f"{x:>10s}" for x in row))
    print("sum   " + " ".join(f"{tot[c]:10.0f}" for c in cols))

    print("\n=== Confirmed vs unconfirmed fills (stop entry, no time exit): does the cross confirm at the close? ===")
    for tf, fn in FILES:
        bars = load_bars(ROOT / "data" / "bars" / fn); I = indicators(bars)
        tr = sim_stop_entry(bars, I, "off", 0)
        c = [t for t in tr if t["confirmed"]]; u = [t for t in tr if not t["confirmed"]]
        sc, su = stats(c), stats(u)
        print(f"{tf:5s} confirmed n={sc['n']:3d} net {sc['net']:7.1f} PF {sc['pf']:4.2f} win {sc['win']:5.1f} | unconfirmed n={su['n']:3d} net {su['net']:7.1f} PF {su['pf']:4.2f} win {su['win']:5.1f}")
