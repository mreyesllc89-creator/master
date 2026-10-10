"""Python replica of XPW Shape Map v0.6 Strategy, default mode:
Turn ▲/▼ + Predict (stop at cross price), ALL opportunities, Reverse, fail exit.
Broker emulation follows TradingView: O->H->L->C if high nearer open, else O->L->H->C.
"""
import csv, math, glob, os

UP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data") + os.sep
TK = 0.1

def load(path):
    rows = list(csv.DictReader(open(path)))
    o = [float(r["open"]) for r in rows]; h = [float(r["high"]) for r in rows]
    l = [float(r["low"]) for r in rows]; c = [float(r["close"]) for r in rows]
    fs = [float(r["Fast"]) if r["Fast"] else None for r in rows]
    ss = [float(r["Slow"]) if r["Slow"] else None for r in rows]
    return dict(t=[r["time"] for r in rows], o=o, h=h, l=l, c=c, tvF=fs, tvS=ss)

def indicators(d, rsiLen=14, fastLen=2, slowLen=7):
    c = d["c"]; n = len(c); a = rsiLen
    up = [None]*n; dn = [None]*n; r = [None]*n
    gs = []; ls = []
    for i in range(1, n):
        ch = c[i]-c[i-1]; g = max(ch, 0); lo = max(-ch, 0)
        if up[i-1] is None:
            gs.append(g); ls.append(lo)
            if len(gs) == a:
                up[i] = sum(gs)/a; dn[i] = sum(ls)/a
        else:
            up[i] = (up[i-1]*(a-1)+g)/a; dn[i] = (dn[i-1]*(a-1)+lo)/a
        if up[i] is not None:
            r[i] = 100.0 if dn[i] == 0 else (0.0 if up[i] == 0 else 100-100/(1+up[i]/dn[i]))
    def sma(x, L, i):
        if i-L+1 < 0 or any(x[j] is None for j in range(i-L+1, i+1)): return None
        return sum(x[i-L+1:i+1])/L
    fast = [sma(r, fastLen, i) for i in range(n)]
    slow = [sma(r, slowLen, i) for i in range(n)]
    xpx = [None]*n
    for i in range(n):
        if up[i] is None or slow[i] is None: continue
        sumF = sum(r[i-fastLen+2:i+1]) if fastLen > 1 else 0.0
        sumS = sum(r[i-slowLen+2:i+1])
        rs_ = (sumS/slowLen - sumF/fastLen)/(1.0/fastLen - 1.0/slowLen)
        if 0.01 < rs_ < 99.99:
            up1 = up[i]*(a-1)/a; dn1 = dn[i]*(a-1)/a; rs = rs_/(100-rs_)
            r0 = 100*up1/(up1+dn1) if up1+dn1 > 0 else 50
            xpx[i] = c[i] + a*(rs*dn1-up1) if rs_ >= r0 else c[i] - a*(up1/rs-dn1)
    d.update(r=r, fast=fast, slow=slow, xpx=xpx)
    return d

def signals(d, botMaxW=3, topMaxW=2, turnMax=12, turnHold=2):
    """Per-bar: botArmed/topArmed after the script's turn logic (what predict sees)."""
    f, s = d["fast"], d["slow"]; n = len(f)
    red = [ (f[i] is not None and s[i] is not None and f[i] > s[i]) for i in range(n)]
    ok = [ (f[i] is not None and s[i] is not None) for i in range(n)]
    lime = [ok[i] and not red[i] for i in range(n)]
    def det(i, wantRed, maxW):
        for w in range(1, maxW+1):
            if i-(w+1) < 0: return False
            ctxNow = lime[i] if wantRed else red[i]
            mid = all((red if wantRed else lime)[i-1-k] for k in range(w))
            bef = lime[i-1-w] if wantRed else red[i-1-w]
            if ctxNow and mid and bef: return True
        return False
    bA = [False]*n; tA = [False]*n
    botArmed = topArmed = False; bBar = tBar = 0
    for i in range(n):
        if det(i, True, botMaxW): botArmed, bBar = True, i
        if det(i, False, topMaxW): topArmed, tBar = True, i
        if botArmed and i-bBar > turnMax: botArmed = False
        if topArmed and i-tBar > turnMax: topArmed = False
        if i >= turnHold+1 and all(ok[i-k] for k in range(turnHold+2)):
            holdUp = all(f[i-k] > s[i-k] for k in range(turnHold+1))
            holdDn = all(f[i-k] < s[i-k] for k in range(turnHold+1))
            j = i-turnHold
            cu = f[j] > s[j] and f[j-1] <= s[j-1]
            cd = f[j] < s[j] and f[j-1] >= s[j-1]
            if botArmed and cu and holdUp: botArmed = False
            if topArmed and cd and holdDn: topArmed = False
        bA[i] = botArmed; tA[i] = topArmed
    d.update(botArmed=bA, topArmed=tA)
    return d

def backtest(d, sl, tp, act, dist, trail=True, qty=1.0, fee=0.0, start=150,
             failExit=True, turnHold=2, direction="Both", cons=False, paths=None, end=None):
    """sl/tp/act/dist in points (ticks of 0.1). fee = fraction per side."""
    o, h, l, c = d["o"], d["h"], d["l"], d["c"]
    f, s, xp, bA, tA = d["fast"], d["slow"], d["xpx"], d["botArmed"], d["topArmed"]
    n = len(c)
    pos = 0; ep = 0.0; eb = 0; ext = 0.0; tron = False
    pL = pS = None
    trades = []
    def close_at(px, why):
        nonlocal pos
        pnl = (px-ep)*pos*qty - fee*qty*(px+ep)
        trades.append((pnl, why, eb)); pos = 0
    def open_at(px, side, i):
        nonlocal pos, ep, eb, ext, tron
        pos = side; ep = px; eb = i; ext = px; tron = False
    useT = trail and dist > 0
    for i in range(start, n if end is None else end):
        # ---------- intrabar ----------
        if paths is not None and paths.get(i):
            pts = paths[i]
        else:
            pts = [o[i], h[i], l[i], c[i]] if abs(h[i]-o[i]) < abs(l[i]-o[i]) else [o[i], l[i], h[i], c[i]]
        # conservative: trailing level frozen for the whole bar, updated after it
        fz_on, fz_ext = tron, ext
        # gap fills at open for entry stops
        cur = o[i]
        if pL is not None and pos <= 0 and o[i] >= pL:
            if pos < 0: close_at(o[i], "rev")
            open_at(o[i], 1, i); pL = None
        elif pS is not None and pos >= 0 and o[i] <= pS:
            if pos > 0: close_at(o[i], "rev")
            open_at(o[i], -1, i); pS = None
        for k in range(1, len(pts)):
            a, b = cur, pts[k]
            guard = 0
            while True:
                guard += 1
                if guard > 10: break
                # candidate events on segment a->b: (price, kind)
                ev = []
                upm = b > a
                if pos != 0:
                    slp = ep - pos*sl*TK if sl > 0 else None
                    tpp = ep + pos*tp*TK if tp > 0 else None
                    actp = ep + pos*act*TK
                    if pos > 0:
                        te = (fz_ext if cons else ext); ton = ((fz_on and eb != i) if cons else tron)
                        stops = [x for x in [slp, (te-dist*TK) if (useT and ton) else None] if x is not None]
                        stp = max(stops) if stops else None
                        if not upm and stp is not None and b <= stp <= a: ev.append((stp, "stop"))
                        if upm and tpp is not None and a <= tpp <= b: ev.append((tpp, "TP"))
                        if upm and useT and not tron and not cons and a <= actp <= b: ev.append((actp, "act"))
                    else:
                        te = (fz_ext if cons else ext); ton = ((fz_on and eb != i) if cons else tron)
                        stops = [x for x in [slp, (te+dist*TK) if (useT and ton) else None] if x is not None]
                        stp = min(stops) if stops else None
                        if upm and stp is not None and a <= stp <= b: ev.append((stp, "stop"))
                        if not upm and tpp is not None and b <= tpp <= a: ev.append((tpp, "TP"))
                        if not upm and useT and not tron and not cons and b <= actp <= a: ev.append((actp, "act"))
                if pL is not None and pos <= 0 and upm and a <= pL <= b: ev.append((pL, "eL"))
                if pS is not None and pos >= 0 and not upm and b <= pS <= a: ev.append((pS, "eS"))
                # extend trailing extreme along the move up to the first event
                if not ev:
                    if pos > 0 and tron: ext = max(ext, b)
                    if pos < 0 and tron: ext = min(ext, b)
                    break
                ev.sort(key=lambda e: abs(e[0]-a))
                px, kind = ev[0]
                if pos > 0 and tron: ext = max(ext, px)
                if pos < 0 and tron: ext = min(ext, px)
                if kind == "stop":
                    slp = ep - pos*sl*TK if sl > 0 else None
                    why = "trail" if (((fz_on and eb != i) if cons else tron) and (slp is None or abs(px-slp) > 1e-9)) else "SL"
                    close_at(px, why)
                elif kind == "TP": close_at(px, "TP")
                elif kind == "act": tron = True; ext = px
                elif kind == "eL":
                    if pos < 0: close_at(px, "rev")
                    open_at(px, 1, i); pL = None
                elif kind == "eS":
                    if pos > 0: close_at(px, "rev")
                    open_at(px, -1, i); pS = None
                a = px
                if a == b: break
            cur = b
        if cons and pos != 0:
            # end of bar: activation + extreme from this bar's high / low
            hi_, lo_ = max(pts), min(pts)
            if pos > 0:
                if not tron and useT and hi_ >= ep + act*TK: tron = True; ext = hi_
                elif tron: ext = max(ext, hi_)
            else:
                if not tron and useT and lo_ <= ep - act*TK: tron = True; ext = lo_
                elif tron: ext = min(ext, lo_)
        # ---------- script at close ----------
        if f[i] is None: continue
        p = pos
        wantL = bA[i] and f[i] < s[i] and xp[i] is not None and p <= 0 and direction != "Short only"
        wantS = tA[i] and f[i] > s[i] and xp[i] is not None and p >= 0 and direction != "Long only"
        pL = math.ceil(round(xp[i]/TK, 6))*TK if wantL else None
        pS = math.floor(round(xp[i]/TK, 6))*TK if wantS else None
        if failExit and pos != 0 and i-eb <= turnHold:
            if (pos > 0 and f[i] <= s[i]) or (pos < 0 and f[i] >= s[i]):
                close_at(c[i], "fail")
    return trades

def stats(trades, cap=10000.0):
    if not trades: return dict(n=0, pf=0, net=0, dd=0, wr=0)
    gp = sum(t[0] for t in trades if t[0] > 0); gl = -sum(t[0] for t in trades if t[0] < 0)
    eq = 0; pk = 0; dd = 0
    for t in trades:
        eq += t[0]; pk = max(pk, eq); dd = max(dd, pk-eq)
    return dict(n=len(trades), pf=(gp/gl if gl > 0 else float("inf")), net=eq, dd=dd,
                wr=sum(1 for t in trades if t[0] > 0)/len(trades))

FILES = {
    "1m BYBIT": "BYBIT_BTCUSDT_1_8e16f.csv",
    "5m BYBIT": "BYBIT_BTCUSDT_5_fdfd0.csv",
    "5m OKX": "OKX_BTCUSDT_5_fa223.csv",
    "15m BYBIT": "BYBIT_BTCUSDT_15_16c15.csv",
    "60m OKX": "OKX_BTCUSDT_60_cd1cb.csv",
}

def prepared(name):
    d = load(UP+FILES[name]); indicators(d); signals(d); return d

if __name__ == "__main__":
    for name in FILES:
        d = prepared(name)
        n = len(d["c"])
        errF = max(abs(d["fast"][i]-d["tvF"][i]) for i in range(150, n))
        errS = max(abs(d["slow"][i]-d["tvS"][i]) for i in range(150, n))
        st = stats(backtest(d, 5000, 50000, 1500, 100))
        print(f"{name:10s} bars={n} maxErr fast={errF:.4f} slow={errS:.4f}  default(q=1): {st}")
