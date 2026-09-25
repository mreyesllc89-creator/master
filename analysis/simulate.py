"""Bar-level re-simulation of the GVLive strategy on the exported chart bars in data/bars.

Purpose: calibrate (a) earlier entry variants and (b) the time-based exit, using
tick-correct trailing-stop behaviour and realistic costs. The TradingView trade lists
cannot be used for this because their fills are artifacts (see REPORT.md).

Usage: python3 analysis/simulate.py [spread_points] [commission_round_trip] [plotted|strict]

Regime: the local VoVix/DEVMA reproduction blocks about a third of the signals TradingView
plotted, while "regime always on" matches 255 of 258 plotted signals across the six exports,
so the default treats the regime filter as pass-through, which is how TradingView traded it.
"""
import csv, math, pathlib, sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPREAD = float(sys.argv[1]) if len(sys.argv) > 1 else 0.25   # gold points per round trip
COMM = float(sys.argv[2]) if len(sys.argv) > 2 else 1.24     # $ per round trip, 1 oz
COST = SPREAD + COMM
REGIME = sys.argv[3] if len(sys.argv) > 3 else "plotted"   # "plotted": regime always passes (matches 255/258 of the signals TradingView plotted); "strict": local VoVix reproduction

# ---------- Pine-faithful indicator helpers ----------
def ema(x, n):
    a = 2 / (n + 1); out = [None] * len(x); prev = None
    for i, v in enumerate(x):
        prev = v if prev is None else a * v + (1 - a) * prev
        out[i] = prev
    return out

def rma(x, n):
    out = [None] * len(x); prev = None; a = 1 / n
    for i, v in enumerate(x):
        if v is None: continue
        if prev is None:
            window = [w for w in x[max(0, i - n + 1):i + 1] if w is not None]
            if len(window) < n: continue
            prev = sum(window) / n
        else:
            prev = a * v + (1 - a) * prev
        out[i] = prev
    return out

def sma(x, n):
    out = [None] * len(x)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1:i + 1]
        if all(v is not None for v in w): out[i] = sum(w) / n
    return out

def stdev(x, n):
    out = [None] * len(x)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1:i + 1]
        if all(v is not None for v in w):
            m = sum(w) / n; out[i] = math.sqrt(sum((v - m) ** 2 for v in w) / n)
    return out

def true_range(h, l, c):
    return [h[i] - l[i] if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(len(h))]

def rsi(c, n):
    up = [None] + [max(c[i] - c[i - 1], 0) for i in range(1, len(c))]
    dn = [None] + [max(c[i - 1] - c[i], 0) for i in range(1, len(c))]
    ru, rd = rma(up, n), rma(dn, n)
    return [None if ru[i] is None else (100.0 if rd[i] == 0 else 100 - 100 / (1 + ru[i] / rd[i])) for i in range(len(c))]

def gt(a, b): return a is not None and b is not None and a > b
def crossover(a, b, i): return i > 0 and gt(a[i], b[i]) and a[i - 1] is not None and b[i - 1] is not None and a[i - 1] <= b[i - 1]
def crossunder(a, b, i): return i > 0 and gt(b[i], a[i]) and a[i - 1] is not None and b[i - 1] is not None and a[i - 1] >= b[i - 1]

# ---------- data ----------
def load_bars(path):
    rows = list(csv.DictReader(open(path)))
    bars = []
    for r in rows:
        try: o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
        except ValueError: continue
        t = r["time"]; hhmm = int(t[11:13]) * 100 + int(t[14:16]) if "T" in t else 0
        bars.append(dict(t=t, hhmm=hhmm, o=o, h=h, l=l, c=c,
                         pf=(float(r["Fast EMA"]) if r.get("Fast EMA") else None),
                         ps=(float(r["Slow EMA"]) if r.get("Slow EMA") else None),
                         pt=(float(r["Trend EMA"]) if r.get("Trend EMA") else None),
                         plong=r.get("Long Signal") == "1", pshort=r.get("Short Signal") == "1"))
    return bars

def indicators(bars):
    c = [b["c"] for b in bars]; h = [b["h"] for b in bars]; l = [b["l"] for b in bars]
    tr = true_range(h, l, c)
    atr14, atr10, atr30 = rma(tr, 14), rma(tr, 10), rma(tr, 30)
    sd_atr10 = stdev(atr10, 30)
    src = [None if (atr10[i] is None or atr30[i] is None or sd_atr10[i] is None) else (atr10[i] - atr30[i]) / (sd_atr10[i] + 1e-6) for i in range(len(c))]
    dev = stdev(src, 30)
    fastD, slowD = sma(dev, 10), sma(dev, 30)
    regime = [gt(fastD[i], slowD[i]) or (i >= 2 and gt(fastD[i], fastD[i - 1]) and gt(fastD[i], fastD[i - 2])) for i in range(len(c))]
    if REGIME == "plotted": regime = [True] * len(c)
    return dict(c=c, h=h, l=l, atr=atr14, fast=ema(c, 5), slow=ema(c, 13), trend=ema(c, 100),
                fast3=ema(c, 3), slow8=ema(c, 8), rsi=rsi(c, 14), regime=regime)

# ---------- entry variants ----------
# Each returns +1 (long), -1 (short) or 0 for bar i. Filters (trend, regime, RSI) are applied by caller.
def v_base(I, i):
    if crossover(I["fast"], I["slow"], i): return 1
    if crossunder(I["fast"], I["slow"], i): return -1
    return 0

def v_close_x_slow(I, i):
    # price crosses the slow EMA while the fast EMA is still on the wrong side: fires before the EMA cross
    f, s, c = I["fast"], I["slow"], I["c"]
    if crossover(c, s, i) and f[i] <= s[i]: return 1
    if crossunder(c, s, i) and f[i] >= s[i]: return -1
    return 0

def v_projected(I, i):
    # fast EMA still below slow, but extrapolating one bar of each EMA's slope puts fast above slow next bar
    f, s = I["fast"], I["slow"]
    if i < 1 or f[i] is None or s[i] is None or f[i-1] is None: return 0
    pf, ps = 2 * f[i] - f[i - 1], 2 * s[i] - s[i - 1]
    if f[i] <= s[i] and pf > ps and f[i] > f[i - 1]: return 1
    if f[i] >= s[i] and pf < ps and f[i] < f[i - 1]: return -1
    return 0

def v_turn(I, i):
    # fast EMA turns toward the slow EMA with the spread narrowing for two bars and price already across the slow EMA
    f, s, c = I["fast"], I["slow"], I["c"]
    if i < 2 or any(v is None for v in (f[i], f[i-1], f[i-2], s[i], s[i-1], s[i-2])): return 0
    d = [f[i - k] - s[i - k] for k in range(3)]
    if d[0] < 0 and d[0] > d[1] > d[2] and c[i] > s[i]: return 1
    if d[0] > 0 and d[0] < d[1] < d[2] and c[i] < s[i]: return -1
    return 0

def v_ema38(I, i):
    if crossover(I["fast3"], I["slow8"], i): return 1
    if crossunder(I["fast3"], I["slow8"], i): return -1
    return 0

VARIANTS = {"base_ema5x13": v_base, "close_x_slowEMA": v_close_x_slow, "projected_cross": v_projected,
            "fast_turn": v_turn, "ema3x8": v_ema38}

def filtered_signal(I, fn, i):
    d = fn(I, i)
    if d == 0 or I["trend"][i] is None or I["rsi"][i] is None or I["atr"][i] is None: return 0
    if d > 0 and I["c"][i] > I["trend"][i] and I["regime"][i] and I["rsi"][i] < 70: return 1
    if d < 0 and I["c"][i] < I["trend"][i] and I["regime"][i] and I["rsi"][i] > 30: return -1
    return 0

# ---------- exit simulation ----------
def simulate(bars, I, fn, entry_win, flat_win, time_exit_mode, n_bars, sl_mult=2.0, tp_mult=2.0,
             trail=True, act_mult=0.9, off_mult=0.3):
    """time_exit_mode: 'off' | 'hard' (close after n bars) | 'profit' (close at first profitable close once n bars have passed)"""
    trades = []; pos = 0; i = 0; N = len(bars)
    in_win = lambda hhmm, w: w is None or (w[0] <= hhmm < w[1])
    while i < N - 1:
        d = filtered_signal(I, fn, i)
        if d == 0 or not in_win(bars[i]["hhmm"], entry_win):
            i += 1; continue
        e = bars[i]["c"]; atr = I["atr"][i]
        sd, td = atr * sl_mult, atr * tp_mult
        stop, tp = e - d * sd, e + d * td
        act, off = d * td * act_mult, sd * off_mult
        trail_lvl = None; exit_px = None; reason = None; j = i + 1
        while j < N:
            b = bars[j]; o, h, l, c = b["o"], b["h"], b["l"], b["c"]
            fav = h if d > 0 else l; adv = l if d > 0 else h
            # 1. trailing stop already in place from earlier bars
            if trail_lvl is not None and (l <= trail_lvl if d > 0 else h >= trail_lvl):
                exit_px = min(o, trail_lvl) if d > 0 else max(o, trail_lvl); reason = "trail"; break
            # 2. hard stop (checked before target: pessimistic when both are touched in one bar)
            if (l <= stop) if d > 0 else (h >= stop):
                exit_px = min(o, stop) if d > 0 else max(o, stop); reason = "stop"; break
            # 3. take profit
            if (h >= tp) if d > 0 else (l <= tp):
                exit_px = max(o, tp) if d > 0 else min(o, tp); reason = "tp"; break
            # 4. trail activation / ratchet on this bar; a fall back through the new level fills at the close
            if trail:
                if (fav - e) * d >= act * d:
                    cand = fav - d * off
                    trail_lvl = cand if trail_lvl is None else (max(trail_lvl, cand) if d > 0 else min(trail_lvl, cand))
                if trail_lvl is not None and ((c <= trail_lvl) if d > 0 else (c >= trail_lvl)):
                    exit_px = c; reason = "trail"; break
            held = j - i
            # 5. time exit
            if time_exit_mode == "hard" and held >= n_bars:
                exit_px = c; reason = "time"; break
            if time_exit_mode == "profit" and held >= n_bars and (c - e) * d > 0:
                exit_px = c; reason = "time_profit"; break
            # 6. session flat
            if not in_win(b["hhmm"], flat_win):
                exit_px = c; reason = "eod"; break
            j += 1
        if exit_px is None:
            exit_px = bars[N - 1]["c"]; reason = "open"; j = N - 1
        pnl = (exit_px - e) * d - COST
        trades.append(dict(i=i, j=j, d=d, e=e, x=exit_px, pnl=pnl, held=j - i, reason=reason))
        i = j + 1   # flat until the exit bar has closed
    return trades

def stats(tr):
    if not tr: return dict(n=0, net=0, pf=0, win=0, avg=0, dd=0, held=0)
    p = [t["pnl"] for t in tr]; g = sum(x for x in p if x > 0); l = -sum(x for x in p if x < 0)
    cum = peak = dd = 0
    for x in p:
        cum += x; peak = max(peak, cum); dd = min(dd, cum - peak)
    return dict(n=len(p), net=sum(p), pf=(g / l if l else float("inf")), win=100 * sum(1 for x in p if x > 0) / len(p),
                avg=sum(p) / len(p), dd=dd, held=sum(t["held"] for t in tr) / len(tr))

FILES = [("5m", "VANTAGE_XAUUSD_5m.csv"), ("15m", "VANTAGE_XAUUSD_15m.csv"), ("30m", "VANTAGE_XAUUSD_30m.csv"),
         ("60m", "VANTAGE_XAUUSD_60m.csv"), ("240m", "VANTAGE_XAUUSD_240m.csv"), ("1D", "VANTAGE_XAUUSD_1D.csv")]

if __name__ == "__main__":
    print(f"cost per round trip: spread {SPREAD} pts + commission ${COMM} = ${COST:.2f} per 1 oz | regime filter: {REGIME}\n")
    data = {}
    for tf, fn in FILES:
        bars = load_bars(ROOT / "data" / "bars" / fn); I = indicators(bars)
        # validation against the values TradingView plotted
        errs = [abs(I["fast"][i] - b["pf"]) for i, b in enumerate(bars) if b["pf"] is not None and i > 300]
        errt = [abs(I["trend"][i] - b["pt"]) for i, b in enumerate(bars) if b["pt"] is not None and i > 300]
        plotted = {i for i, b in enumerate(bars) if b["plong"] or b["pshort"]}
        mine = {i for i in range(len(bars)) if filtered_signal(I, v_base, i) != 0}
        print(f"{tf:5s}: {len(bars)} bars {bars[0]['t'][:10]} -> {bars[-1]['t'][:10]} | max |EMA err| fast {max(errs):.4f} trend {max(errt):.4f} | "
              f"plotted signals {len(plotted)}, of which reproduced by base rule {len(plotted & mine)} | base rule fires {len(mine)} (before session/position filters)")
        data[tf] = (bars, I)

    # ---- earlier-entry lead analysis: how many bars before the base cross does each variant fire? ----
    print("\n=== Earlier-entry variants: lead vs. the base EMA 5/13 cross (same direction, within 6 bars) ===")
    print(f"{'TF':5s} {'variant':18s} {'fires':>6s} {'lead avg':>9s} {'lead0/1/2/3+':>14s} {'no cross follows':>17s}")
    for tf, (bars, I) in data.items():
        base = {i: filtered_signal(I, v_base, i) for i in range(len(bars))}
        base_idx = [i for i, d in base.items() if d]
        for name, fn in VARIANTS.items():
            if name == "base_ema5x13": continue
            fires = [(i, filtered_signal(I, fn, i)) for i in range(len(bars))]
            fires = [(i, d) for i, d in fires if d]
            leads = []; orphan = 0
            for i, d in fires:
                nxt = [k for k in base_idx if i <= k <= i + 6 and base[k] == d]
                if nxt: leads.append(nxt[0] - i)
                else: orphan += 1
            hist = [sum(1 for x in leads if x == k) for k in (0, 1, 2)] + [sum(1 for x in leads if x >= 3)]
            print(f"{tf:5s} {name:18s} {len(fires):6d} {sum(leads)/max(1,len(leads)):9.2f} {str(hist):>14s} {orphan:17d}")

    # ---- P&L by variant with the current exit stack (tick-correct trail, no time exit) ----
    WIN = {"5m": ((400, 2230), (400, 2330)), "15m": ((400, 2230), (400, 2330)), "30m": ((400, 2230), (400, 2330)),
           "60m": ((400, 2230), (400, 2330)), "240m": (None, None), "1D": (None, None)}
    print("\n=== Entry variants, exits = ATR stop/target + tick-correct trail, no time exit (sessions as tested: 04:00-22:30) ===")
    print(f"{'TF':5s} {'variant':18s} {'n':>4s} {'net$':>8s} {'PF':>6s} {'win%':>6s} {'avg$':>7s} {'maxDD':>8s} {'bars':>5s}")
    for tf, (bars, I) in data.items():
        for name, fn in VARIANTS.items():
            s = stats(simulate(bars, I, fn, *WIN[tf], "off", 0))
            print(f"{tf:5s} {name:18s} {s['n']:4d} {s['net']:8.1f} {s['pf']:6.2f} {s['win']:6.1f} {s['avg']:7.2f} {s['dd']:8.1f} {s['held']:5.1f}")

    # ---- time-exit calibration ----
    for name in ("base_ema5x13", "close_x_slowEMA", "projected_cross"):
        fn = VARIANTS[name]
        print(f"\n=== Time-exit sweep, entry = {name}.  'hard N' closes after N bars; 'profit N' closes at the first profitable close once N bars have passed ===")
        header = f"{'TF':5s} " + " ".join(f"{m:>9s}" for m in ["off"] + [f"hard{n}" for n in (1, 2, 3, 4, 6, 8)] + [f"prof{n}" for n in (0, 1, 2, 3, 4, 6, 8)])
        print(header)
        pooled = defaultdict(list)
        for tf, (bars, I) in data.items():
            row = []
            for mode, n in [("off", 0)] + [("hard", n) for n in (1, 2, 3, 4, 6, 8)] + [("profit", n) for n in (0, 1, 2, 3, 4, 6, 8)]:
                tr = simulate(bars, I, fn, *WIN[tf], mode, n); s = stats(tr)
                pooled[(mode, n)].append(s)
                row.append(f"{s['net']:6.0f}/{s['pf']:.1f}" if s["pf"] < 100 else f"{s['net']:6.0f}/inf")
            print(f"{tf:5s} " + " ".join(f"{x:>9s}" for x in row))
        print("sum  " + " ".join(f"{sum(s['net'] for s in v):9.0f}" for v in pooled.values()) + "   (net $ summed over timeframes)")
        print("avgPF" + " ".join(f"{sum(min(s['pf'],10) for s in v)/len(v):9.2f}" for v in pooled.values()) + "   (PF averaged over timeframes, capped at 10)")
        print("win% " + " ".join(f"{sum(s['win'] for s in v)/len(v):9.1f}" for v in pooled.values()))
