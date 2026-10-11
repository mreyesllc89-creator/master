#!/usr/bin/env python3
"""XPW Shape Map calibrator.

Replays the XPW_ShapeMap indicator + XPW_ShapeMap_EA rules on exported bars and
grid-searches exits (and CONT thresholds) per symbol. Pure Python, no deps.

  python3 calibrate.py <bars.csv> --symbol XAUUSD|BTCUSD [--modes cont,turn_hold,...] [--out report.md]

Accepted bar files:
  * TradingView export: header "time,open,high,low,close,..." (optional Fast/Slow columns are
    used to verify the TDI port)
  * MetaTrader 5 export (View > Symbols > Bars > Export, or chart Save As): columns
    <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> ... (tab or comma separated)
"""
import csv, sys, math, argparse, itertools

# ───────────────────────── symbol settings ─────────────────────────
SYMBOLS = {
    # point = MT5 _Point, contract = units per lot, spread/commission in price units per unit round-trip
    "XAUUSD": dict(point=0.01, contract=100.0, spread=0.25, comm_pct=0.0,
                   sl_usd=[3, 5, 7, 10, 15], act_usd=[2, 4, 6, 10], dis_usd=[0.5, 1, 2, 3], tp_usd=[0]),
    "BTCUSD": dict(point=0.01, contract=1.0, spread=20.0, comm_pct=0.0,
                   sl_usd=[300, 500, 700, 1000, 1500], act_usd=[100, 200, 400, 800], dis_usd=[10, 30, 60, 120], tp_usd=[0]),
}
START_EQUITY = 10000.0

# ───────────────────────── data ─────────────────────────
def load(path):
    rows = []
    with open(path, newline="") as f:
        head = f.readline()
        f.seek(0)
        if head.lower().startswith("time,"):
            for r in csv.DictReader(f):
                rows.append(dict(t=r["time"], o=float(r["open"]), h=float(r["high"]), l=float(r["low"]), c=float(r["close"]),
                                 fast=float(r["Fast"]) if "Fast" in r and r["Fast"] not in ("", "NaN") else None,
                                 slow=float(r["Slow"]) if "Slow" in r and r["Slow"] not in ("", "NaN") else None))
        else:
            delim = "\t" if "\t" in head else ","
            rd = csv.reader(f, delimiter=delim)
            hdr = [h.strip("<>").upper() for h in next(rd)]
            ix = {k: hdr.index(k) for k in ("OPEN", "HIGH", "LOW", "CLOSE")}
            di, ti = hdr.index("DATE"), (hdr.index("TIME") if "TIME" in hdr else None)
            for r in rd:
                if len(r) <= ix["CLOSE"]: continue
                t = r[di] + (" " + r[ti] if ti is not None else "")
                rows.append(dict(t=t, o=float(r[ix["OPEN"]]), h=float(r[ix["HIGH"]]), l=float(r[ix["LOW"]]), c=float(r[ix["CLOSE"]]), fast=None, slow=None))
    return rows

# ───────────────────────── indicator port ─────────────────────────
P = dict(rsiLen=14, fastLen=2, slowLen=7, invert=True, areaLook=20, loFrac=0.20, hiFrac=0.67,
         allOn=True, allCtx=1, botOn=True, botMinW=1, botMaxW=3, botCtxIn=2, botNeedLow=True, botSepIn=5,
         topOn=True, topMinW=1, topMaxW=2, topCtxIn=3, topNeedHigh=True, topSepIn=5,
         turnOn=True, turnMax=12, turnHold=2, tickOn=True, atrLen=14,
         botWickRange=0.55, botWickAtr=0.8, topWickRange=0.70, topWickAtr=1.20,
         contOn=True, contBigAtr=1.0, contLook=30, contNeedRed=True, contRedMax=12, contPinch=1.0, contAfter=6, contSep=5, contMirror=True)

def indicators(rows, p):
    n = len(rows); c = [r["c"] for r in rows]; h = [r["h"] for r in rows]; l = [r["l"] for r in rows]
    L = p["rsiLen"]
    up = [0.0] * n; dn = [0.0] * n; rsi = [50.0] * n
    for i in range(L, n):
        g = max(c[i] - c[i - 1], 0); d = max(c[i - 1] - c[i], 0)
        if i == L:
            up[i] = sum(max(c[k] - c[k - 1], 0) for k in range(1, L + 1)) / L
            dn[i] = sum(max(c[k - 1] - c[k], 0) for k in range(1, L + 1)) / L
        else:
            up[i] = (up[i - 1] * (L - 1) + g) / L; dn[i] = (dn[i - 1] * (L - 1) + d) / L
        rsi[i] = 100 if dn[i] == 0 else (0 if up[i] == 0 else 100 - 100 / (1 + up[i] / dn[i]))
    fast = [None] * n; slow = [None] * n
    for i in range(L + p["slowLen"], n):
        fast[i] = sum(rsi[i - k] for k in range(p["fastLen"])) / p["fastLen"]
        slow[i] = sum(rsi[i - k] for k in range(p["slowLen"])) / p["slowLen"]
    A = p["atrLen"]; atr = [0.0] * n
    tr = lambda k: max(h[k] - l[k], abs(h[k] - c[k - 1]), abs(l[k] - c[k - 1]))
    for i in range(A, n):
        atr[i] = sum(tr(k) for k in range(i - A + 1, i + 1)) / A if i == A else (atr[i - 1] * (A - 1) + tr(i)) / A
    isRed = [None if fast[i] is None else ((fast[i] > slow[i]) if p["invert"] else (fast[i] < slow[i])) for i in range(n)]
    # predict price
    pred = [None] * n
    for i in range(L + p["slowLen"], n):
        nF = max(p["fastLen"] - 1, 1); nS = max(p["slowLen"] - 1, 1)
        sumF = sum(rsi[i - k] for k in range(nF)) if p["fastLen"] > 1 else 0.0
        sumS = sum(rsi[i - k] for k in range(nS))
        rStar = (sumS / p["slowLen"] - sumF / p["fastLen"]) / (1.0 / p["fastLen"] - 1.0 / p["slowLen"])
        if not (0.01 < rStar < 99.99): continue
        a = L; up1 = up[i] * (a - 1) / a; dn1 = dn[i] * (a - 1) / a; rs = rStar / (100 - rStar)
        r0 = 100 * up1 / (up1 + dn1) if up1 + dn1 > 0 else 50
        pred[i] = c[i] + a * (rs * dn1 - up1) if rStar >= r0 else c[i] - a * (up1 / rs - dn1)
    return dict(rsi=rsi, fast=fast, slow=slow, atr=atr, isRed=isRed, pred=pred)

def signals(rows, ind, p):
    n = len(rows); fast, slow, atr, isRed = ind["fast"], ind["slow"], ind["atr"], ind["isRed"]
    o = [r["o"] for r in rows]; h = [r["h"] for r in rows]; l = [r["l"] for r in rows]; c = [r["c"] for r in rows]
    S = dict(botSq=[False]*n, topSq=[False]*n, turnUp=[False]*n, turnDn=[False]*n, botTick=[False]*n, topTick=[False]*n,
             contUp=[False]*n, contDn=[False]*n, crossUp=[False]*n, crossDn=[False]*n, armL=[False]*n, armS=[False]*n)
    def posW(j):
        if j < p["areaLook"]: return 0.5
        w = slow[j - p["areaLook"] + 1:j + 1]; hi, lo = max(w), min(w)
        return (slow[j] - lo) / (hi - lo) if hi > lo else 0.5
    def detect(i, wantRed, minW, maxW, ctx):
        for w in range(minW, max(minW, maxW) + 1):
            if i - (2 * ctx + w) < 0: return 0
            ok = all((not isRed[i - k]) if wantRed else isRed[i - k] for k in range(ctx))
            ok = ok and all(isRed[i - ctx - k] if wantRed else (not isRed[i - ctx - k]) for k in range(w))
            ok = ok and all((not isRed[i - ctx - w - k]) if wantRed else isRed[i - ctx - w - k] for k in range(ctx))
            if ok: return w
        return 0
    st = dict(lastBot=-10000, lastTop=-10000, botArmed=False, topArmed=False, botArmBar=0, topArmBar=0,
              cSt=[0, 0], cBig=[-10000, -10000], cFlip=[-10000, -10000], cOdd=[0, 0], cLast=[-10000, -10000])
    warm = p["rsiLen"] + p["slowLen"] + max(p["areaLook"], p["atrLen"]) + 12
    botCtx = p["allCtx"] if p["allOn"] else p["botCtxIn"]; topCtx = p["allCtx"] if p["allOn"] else p["topCtxIn"]
    botSep = 0 if p["allOn"] else p["botSepIn"]; topSep = 0 if p["allOn"] else p["topSepIn"]
    def contStep(i, d, bull):
        a = atr[i]; body = abs(c[i] - o[i])
        big = a > 0 and (c[i] > o[i] if bull else c[i] < o[i]) and body >= p["contBigAtr"] * a
        red = isRed[i]; inZone = (not red) if bull else red; odd = red if bull else (not red)
        dirBar = c[i] > o[i] if bull else c[i] < o[i]
        gapNow = abs(fast[i] - slow[i]); gapPrv = abs(fast[i - 1] - slow[i - 1])
        ready = st["cSt"][d] == 3 and inZone and dirBar and i - st["cFlip"][d] <= p["contAfter"] and i - st["cLast"][d] >= p["contSep"]
        if ready: st["cLast"][d] = i; st["cSt"][d] = 0
        elif big: st["cSt"][d] = 1; st["cBig"][d] = i; st["cOdd"][d] = 0
        elif st["cSt"][d] > 0 and i - st["cBig"][d] > p["contLook"]: st["cSt"][d] = 0
        elif st["cSt"][d] == 1:
            if odd: st["cSt"][d] = 2; st["cOdd"][d] = 1
            elif inZone and not p["contNeedRed"]: st["cSt"][d] = 3; st["cFlip"][d] = i
        elif st["cSt"][d] == 2:
            if odd:
                st["cOdd"][d] += 1
                if st["cOdd"][d] > p["contRedMax"]: st["cSt"][d] = 0
            elif inZone:
                if min(gapPrv, gapNow) <= p["contPinch"]: st["cSt"][d] = 3; st["cFlip"][d] = i
                else: st["cSt"][d] = 0
        elif st["cSt"][d] == 3:
            if odd: st["cSt"][d] = 2; st["cOdd"][d] = 1
            elif i - st["cFlip"][d] > p["contAfter"]: st["cSt"][d] = 0
        return p["contOn"] and ready
    for i in range(warm, n):
        if isRed[i] is None: continue
        botArea = p["allOn"] or not p["botNeedLow"] or posW(i - botCtx) <= p["loFrac"]
        topArea = p["allOn"] or not p["topNeedHigh"] or posW(i - topCtx) >= p["hiFrac"]
        bw = detect(i, True, p["botMinW"], p["botMaxW"], botCtx); tw = detect(i, False, p["topMinW"], p["topMaxW"], topCtx)
        botOK = p["botOn"] and bw > 0 and botArea and i - st["lastBot"] >= botSep
        topOK = p["topOn"] and tw > 0 and topArea and i - st["lastTop"] >= topSep
        if botOK: st["lastBot"] = i; S["botSq"][i] = True; st["botArmed"] = True; st["botArmBar"] = i
        if topOK: st["lastTop"] = i; S["topSq"][i] = True; st["topArmed"] = True; st["topArmBar"] = i
        if st["botArmed"] and i - st["botArmBar"] > p["turnMax"]: st["botArmed"] = False
        if st["topArmed"] and i - st["topArmBar"] > p["turnMax"]: st["topArmed"] = False
        H = p["turnHold"]
        holdUp = all(fast[i - k] > slow[i - k] for k in range(H + 1)); holdDn = all(fast[i - k] < slow[i - k] for k in range(H + 1))
        j = i - H
        cUpAt = fast[j] > slow[j] and fast[j - 1] <= slow[j - 1]; cDnAt = fast[j] < slow[j] and fast[j - 1] >= slow[j - 1]
        S["crossUp"][i] = fast[i] > slow[i] and fast[i - 1] <= slow[i - 1]
        S["crossDn"][i] = fast[i] < slow[i] and fast[i - 1] >= slow[i - 1]
        S["armL"][i] = p["turnOn"] and st["botArmed"]; S["armS"][i] = p["turnOn"] and st["topArmed"]
        if p["turnOn"] and st["botArmed"] and cUpAt and holdUp: st["botArmed"] = False; S["turnUp"][i] = True
        if p["turnOn"] and st["topArmed"] and cDnAt and holdDn: st["topArmed"] = False; S["turnDn"][i] = True
        rng = h[i] - l[i]; upW = h[i] - max(o[i], c[i]); dnW = min(o[i], c[i]) - l[i]; a = atr[i]
        S["botTick"][i] = p["tickOn"] and rng > 0 and a > 0 and dnW / rng >= p["botWickRange"] and dnW / a >= p["botWickAtr"]
        S["topTick"][i] = p["tickOn"] and rng > 0 and a > 0 and upW / rng >= p["topWickRange"] and upW / a >= p["topWickAtr"]
        S["contUp"][i] = contStep(i, 0, True)
        dn = contStep(i, 1, False); S["contDn"][i] = p["contMirror"] and dn
    return S

# ───────────────────────── backtest ─────────────────────────
MODES = ["cont", "cont_stop", "turn_hold", "turn_cross", "turn_predict", "square", "tick"]

def backtest(rows, ind, S, sym, mode, sl, tp, act, dis, risk=1.0, opp="reverse", tradeDir="both",
             predBuf=0.0, contStopBuf=0.0, contStopBars=3):
    """Closed-bar replay with the EA's rules. Returns metrics dict."""
    n = len(rows); o = [r["o"] for r in rows]; h = [r["h"] for r in rows]; l = [r["l"] for r in rows]; c = [r["c"] for r in rows]
    fast, slow, pred = ind["fast"], ind["slow"], ind["pred"]
    cost = sym["spread"]                       # round-trip cost per unit (spread) + commission
    eq = START_EQUITY; peak = eq; maxdd = 0.0
    pos = 0; qty = 0.0; entry = 0.0; stop = 0.0; take = 0.0; hh = 0.0; ll = 0.0; ebar = 0
    trades = []; pending = None               # pending = (dir, price, placed_bar, expire_bar)
    def long_sig(i):
        return {"cont": S["contUp"][i], "cont_stop": False, "turn_hold": S["turnUp"][i], "turn_cross": S["armL"][i] and S["crossUp"][i],
                "turn_predict": False, "square": S["botSq"][i], "tick": S["botTick"][i]}[mode]
    def short_sig(i):
        return {"cont": S["contDn"][i], "cont_stop": False, "turn_hold": S["turnDn"][i], "turn_cross": S["armS"][i] and S["crossDn"][i],
                "turn_predict": False, "square": S["topSq"][i], "tick": S["topTick"][i]}[mode]
    def size(sl_):
        return 0.0 if sl_ <= 0 else eq * risk / 100.0 / sl_
    def close_trade(px, i, why):
        nonlocal eq, pos, qty, peak, maxdd
        pnl = (px - entry) * qty * pos - cost * qty - 2 * sym["comm_pct"] / 100 * px * qty
        eq += pnl; trades.append(dict(dir=pos, entry=entry, exit=px, pnl=pnl, bars=i - ebar, why=why, t=rows[i]["t"]))
        peak = max(peak, eq); maxdd = max(maxdd, (peak - eq) / peak * 100)
        pos = 0; qty = 0.0
    def open_trade(d, px, i):
        nonlocal pos, qty, entry, stop, take, hh, ll, ebar
        q = size(sl)
        if q <= 0: return
        pos = d; qty = q; entry = px; ebar = i; hh = px; ll = px
        stop = px - sl * d if sl > 0 else (0 if d > 0 else 1e18)
        take = px + tp * d if tp > 0 else (1e18 if d > 0 else 0)
    canL = tradeDir != "short"; canS = tradeDir != "long"
    for i in range(1, n):
        if fast[i] is None: continue
        # 1. pending stop orders fill inside this bar
        if pending is not None and pos == 0:
            d, px, pb, xb = pending
            if (d > 0 and h[i] >= px) or (d < 0 and l[i] <= px):
                fill = max(px, o[i]) if d > 0 else min(px, o[i]); pending = None; open_trade(d, fill, i)
            elif i >= xb: pending = None
        # 2. manage open position inside this bar
        if pos != 0 and i > ebar:
            if pos > 0:
                if l[i] <= stop: close_trade(stop, i, "SL/trail")
                else:
                    hh = max(hh, h[i])
                    if dis > 0 and hh - entry >= act:
                        ns = hh - dis
                        if ns > stop:
                            stop = ns
                            if c[i] < stop: close_trade(stop, i, "trail")
                    if pos != 0 and h[i] >= take: close_trade(take, i, "TP")
            else:
                if h[i] >= stop: close_trade(stop, i, "SL/trail")
                else:
                    ll = min(ll, l[i])
                    if dis > 0 and entry - ll >= act:
                        ns = ll + dis
                        if ns < stop:
                            stop = ns
                            if c[i] > stop: close_trade(stop, i, "trail")
                    if pos != 0 and l[i] <= take: close_trade(take, i, "TP")
        # 3. signals at this bar's close
        if i >= n - 1: break
        if mode == "turn_predict":
            armL = S["armL"][i]; armS = S["armS"][i]; px = pred[i]
            if px is not None:
                if armL and fast[i] < slow[i] and canL and (pos == 0 or (pos < 0 and opp == "reverse")):
                    pending = (1, px + predBuf, i, i + 1)
                elif armS and fast[i] > slow[i] and canS and (pos == 0 or (pos > 0 and opp == "reverse")):
                    pending = (-1, px - predBuf, i, i + 1)
                else: pending = None
            # catch-up at this close
            if S["crossUp"][i] and armL and canL and (pos == 0 or (pos < 0 and opp == "reverse")) and ebar != i:
                if pos < 0: close_trade(c[i], i, "reverse")
                pending = None; open_trade(1, c[i], i)
            elif S["crossDn"][i] and armS and canS and (pos == 0 or (pos > 0 and opp == "reverse")) and ebar != i:
                if pos > 0: close_trade(c[i], i, "reverse")
                pending = None; open_trade(-1, c[i], i)
            if opp == "close":
                if pos < 0 and armL and S["crossUp"][i]: close_trade(c[i], i, "opp")
                if pos > 0 and armS and S["crossDn"][i]: close_trade(c[i], i, "opp")
            continue
        if mode == "cont_stop":
            if S["contUp"][i] and canL and (pos == 0 or (pos < 0 and opp == "reverse")):
                if pos < 0: close_trade(c[i], i, "reverse")
                pending = (1, h[i] + contStopBuf, i, i + contStopBars)
            elif S["contDn"][i] and canS and (pos == 0 or (pos > 0 and opp == "reverse")):
                if pos > 0: close_trade(c[i], i, "reverse")
                pending = (-1, l[i] - contStopBuf, i, i + contStopBars)
            if opp == "close":
                if pos > 0 and S["contDn"][i]: close_trade(c[i], i, "opp")
                if pos < 0 and S["contUp"][i]: close_trade(c[i], i, "opp")
            continue
        ls, ss = long_sig(i), short_sig(i)
        if ls and ss: ls = ss = False
        if ls:
            if pos < 0:
                if opp == "reverse" and canL: close_trade(c[i], i, "reverse"); open_trade(1, c[i], i)
                elif opp != "ignore": close_trade(c[i], i, "opp")
            elif pos == 0 and canL: open_trade(1, c[i], i)
        if ss:
            if pos > 0:
                if opp == "reverse" and canS: close_trade(c[i], i, "reverse"); open_trade(-1, c[i], i)
                elif opp != "ignore": close_trade(c[i], i, "opp")
            elif pos == 0 and canS: open_trade(-1, c[i], i)
    if pos != 0: close_trade(c[n - 1], n - 1, "end")
    wins = [t for t in trades if t["pnl"] > 0]; losses = [t for t in trades if t["pnl"] <= 0]
    gp = sum(t["pnl"] for t in wins); gl = -sum(t["pnl"] for t in losses)
    return dict(trades=len(trades), win=100.0 * len(wins) / len(trades) if trades else 0, pf=(gp / gl) if gl > 0 else (99.0 if gp > 0 else 0),
                net=(eq - START_EQUITY) / START_EQUITY * 100, maxdd=maxdd, list=trades)

# ───────────────────────── calibration ─────────────────────────
def score(m):   # net return penalised by drawdown; needs some trades to count
    if m["trades"] < 8: return -1e9
    return m["net"] - 1.5 * m["maxdd"]

def fmt(m): return f"trades {m['trades']:3d}  win {m['win']:5.1f}%  PF {m['pf']:5.2f}  net {m['net']:7.2f}%  maxDD {m['maxdd']:5.2f}%"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file"); ap.add_argument("--symbol", required=True, choices=list(SYMBOLS))
    ap.add_argument("--modes", default=",".join(MODES)); ap.add_argument("--out", default=None)
    ap.add_argument("--risk", type=float, default=1.0)
    a = ap.parse_args()
    sym = SYMBOLS[a.symbol]; rows = load(a.file); ind = indicators(rows, P)
    out = []
    def say(s=""):
        print(s); out.append(s)
    say(f"# XPW calibration — {a.symbol}  ({len(rows)} bars, {rows[0]['t']} .. {rows[-1]['t']})")
    # verify the TDI port against exported Fast/Slow when present
    diffs = [abs(ind["fast"][i] - rows[i]["fast"]) + abs(ind["slow"][i] - rows[i]["slow"]) for i in range(60, len(rows)) if rows[i]["fast"] is not None and ind["fast"][i] is not None]
    if diffs: say(f"TDI port check vs exported Fast/Slow: max |diff| = {max(diffs):.4f} RSI pts over {len(diffs)} bars")
    say(f"Account {START_EQUITY:.0f}, risk {a.risk}% per trade, spread {sym['spread']} per unit round trip, point {sym['point']}")
    S = signals(rows, ind, P)
    say(f"Signals: BOT sq {sum(S['botSq'])}, TOP sq {sum(S['topSq'])}, turn▲ {sum(S['turnUp'])}, turn▼ {sum(S['turnDn'])}, BOT tick {sum(S['botTick'])}, TOP tick {sum(S['topTick'])}, CONT▲ {sum(S['contUp'])}, CONT▼ {sum(S['contDn'])}")
    best_all = []
    for mode in a.modes.split(","):
        say(f"\n## mode {mode}")
        results = []
        grids = itertools.product(sym["sl_usd"], sym["tp_usd"], sym["act_usd"], sym["dis_usd"])
        for sl, tp, act, dis in grids:
            if dis >= act: continue
            for tdir in ("both", "long", "short"):
                m = backtest(rows, ind, S, sym, mode, sl, tp, act, dis, risk=a.risk, tradeDir=tdir,
                             predBuf=sym["point"] * 100, contStopBuf=sym["point"] * 50)
                results.append((score(m), sl, tp, act, dis, tdir, m))
        results.sort(key=lambda r: -r[0])
        for r in results[:6]:
            sc, sl, tp, act, dis, tdir, m = r
            say(f"  SL {sl:>6} act {act:>5} dis {dis:>5} {tdir:5s} | {fmt(m)} | pts: SL {sl/sym['point']:.0f} act {act/sym['point']:.0f} dis {dis/sym['point']:.0f}")
        if results and results[0][0] > -1e9: best_all.append((results[0][0], mode, results[0]))
        # CONT thresholds grid on top of the best exits
        if mode.startswith("cont") and results and results[0][0] > -1e9:
            _, sl, tp, act, dis, tdir, _ = results[0]
            say(f"  CONT thresholds (with SL {sl} act {act} dis {dis} {tdir}):")
            rows2 = []
            for big, pinch, after in itertools.product([0.8, 1.0, 1.2, 1.5], [0.75, 1.0, 1.5, 2.0], [4, 6, 8]):
                p2 = dict(P, contBigAtr=big, contPinch=pinch, contAfter=after)
                S2 = signals(rows, ind, p2)
                m = backtest(rows, ind, S2, sym, mode, sl, tp, act, dis, risk=a.risk, tradeDir=tdir, contStopBuf=sym["point"] * 50)
                rows2.append((score(m), big, pinch, after, m))
            rows2.sort(key=lambda r: -r[0])
            for sc, big, pinch, after, m in rows2[:5]:
                say(f"    big {big:3.1f} pinch {pinch:4.2f} after {after} | {fmt(m)}")
    say("\n## best per mode")
    for sc, mode, r in sorted(best_all, key=lambda x: -x[0]):
        _, sl, tp, act, dis, tdir, m = r
        say(f"  {mode:12s} SL {sl} act {act} dis {dis} {tdir:5s} | {fmt(m)}")
    if a.out:
        with open(a.out, "w") as f: f.write("\n".join(out) + "\n")

if __name__ == "__main__":
    main()
