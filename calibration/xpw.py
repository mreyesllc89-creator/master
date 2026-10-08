"""Python replica of XPW Shape Map v0.6 Strategy, Turn Predict entries, with costs."""
import csv, math, sys
import numpy as np

def load(path):
    rows = list(csv.reader(open(path)))
    h = rows[0]; d = rows[1:]
    col = lambda name, k=0: [i for i, x in enumerate(h) if x == name][k]
    f = lambda i: np.array([float(r[i]) if r[i] != '' else np.nan for r in d])
    out = dict(t=[r[0] for r in d], o=f(1), h=f(2), l=f(3), c=f(4),
               fastx=f(col('Fast')), slowx=f(col('Slow')), xpx=f(col('Predicted cross price')))
    return out

def rma(x, n):
    out = np.full(len(x), np.nan); s = None; buf = []
    for i, v in enumerate(x):
        if np.isnan(v): continue
        if s is None:
            buf.append(v)
            if len(buf) == n: s = sum(buf) / n; out[i] = s
        else:
            s = (s * (n - 1) + v) / n; out[i] = s
    return out

def sma(x, n):
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1:i + 1]
        if not np.isnan(w).any(): out[i] = w.mean()
    return out

def indicators(D, rsiLen=14, fastLen=2, slowLen=7):
    c = D['c']; pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(pc), D['h'] - D['l'], np.maximum(D['h'] - D['l'], np.maximum(abs(D['h'] - pc), abs(D['l'] - pc))))
    D['atr'] = rma(tr, 14); chg = np.r_[np.nan, np.diff(c)]
    up = rma(np.where(np.isnan(chg), np.nan, np.maximum(chg, 0)), rsiLen)
    dn = rma(np.where(np.isnan(chg), np.nan, np.maximum(-chg, 0)), rsiLen)
    r = np.where(dn == 0, 100.0, np.where(up == 0, 0.0, 100 - 100 / (1 + up / np.where(dn == 0, 1, dn))))
    r[np.isnan(up)] = np.nan
    fast = sma(r, fastLen); slow = sma(r, slowLen)
    sumF = r.copy() if fastLen == 2 else sma(r, fastLen - 1) * (fastLen - 1)
    sumS = sma(r, slowLen - 1) * (slowLen - 1)
    xpx = np.full(len(c), np.nan); a = float(rsiLen)
    for i in range(len(c)):
        if np.isnan(up[i]) or np.isnan(dn[i]) or np.isnan(sumS[i]) or np.isnan(sumF[i]): continue
        rs_ = (sumS[i] / slowLen - sumF[i] / fastLen) / (1.0 / fastLen - 1.0 / slowLen)
        if 0.01 < rs_ < 99.99:
            up1 = up[i] * (a - 1) / a; dn1 = dn[i] * (a - 1) / a
            rs = rs_ / (100 - rs_)
            r0 = 100 * up1 / (up1 + dn1) if up1 + dn1 > 0 else 50
            xpx[i] = c[i] + a * (rs * dn1 - up1) if rs_ >= r0 else c[i] - a * (up1 / rs - dn1)
    D.update(r=r, fast=fast, slow=slow, xpxc=xpx)
    return D

def signals(D, botMaxW=3, topMaxW=2, turnMax=12, turnHold=2):
    """Per bar (confirmed): wantL / wantS flags as computed at the bar close (before pos filter)."""
    f, s = D['fast'], D['slow']; n = len(f)
    isRed = np.where(np.isnan(f) | np.isnan(s), False, f > s); isLime = ~isRed
    gt = lambda i: (not np.isnan(f[i]) and not np.isnan(s[i]) and f[i] > s[i])
    lt = lambda i: (not np.isnan(f[i]) and not np.isnan(s[i]) and f[i] < s[i])
    def detect(i, red, maxW):
        for w in range(1, maxW + 1):
            if i - (1 + w) < 0: return False
            ok = (isLime[i] if red else isRed[i])
            ok = ok and all((isRed[i-1-k] if red else isLime[i-1-k]) for k in range(w))
            ok = ok and (isLime[i-1-w] if red else isRed[i-1-w])
            if ok: return True
        return False
    def cross(i, up):
        if i < 1: return False
        if any(np.isnan(v) for v in (f[i], s[i], f[i-1], s[i-1])): return False
        return (f[i] > s[i] and f[i-1] <= s[i-1]) if up else (f[i] < s[i] and f[i-1] >= s[i-1])
    bA = tA = False; bBar = tBar = 0
    wantL = np.zeros(n, bool); wantS = np.zeros(n, bool); crossFail = None
    for i in range(n):
        if detect(i, True, botMaxW): bA, bBar = True, i
        if detect(i, False, topMaxW): tA, tBar = True, i
        if bA and i - bBar > turnMax: bA = False
        if tA and i - tBar > turnMax: tA = False
        if i >= turnHold:
            holdUp = all(gt(i-k) for k in range(turnHold+1)); holdDn = all(lt(i-k) for k in range(turnHold+1))
            if bA and cross(i-turnHold, True) and holdUp: bA = False
            if tA and cross(i-turnHold, False) and holdDn: tA = False
        ok = not np.isnan(D['xpxc'][i])
        wantL[i] = bA and lt(i) and ok
        wantS[i] = tA and gt(i) and ok
    D.update(wantL=wantL, wantS=wantS)
    return D

def path(o, h, l, c, tvpath=True):
    if abs(h - o) < abs(l - o): return [o, h, l, c]
    return [o, l, h, c]

def backtest(D, sl, tp, act, dist, comm=0.05, slip=5.0, spread=1.0, tick=0.01, mode='tv', turnHold=2, lo=0, hi=None, failExit=True, atr=None):
    """sl/tp/act/dist in % of entry price (0 / None = off). comm % per side. slip, spread in $.
    mode 'tv' = TradingView OHLC path; 'pess' = trail uses only previous bars' extremes, SL before TP."""
    O, H, L, C = D['o'], D['h'], D['l'], D['c']; f, s = D['fast'], D['slow']
    wl, ws, xp = D['wantL'], D['wantS'], D['xpxc']
    n = len(C); hi = n if hi is None else hi
    pos = 0; ep = 0.0; eb = 0; best = 0.0; trades = []
    pend = None  # (dir, stop price)
    sl0, tp0, act0, dist0 = sl, tp, act, dist
    P = dict(sl=sl, tp=tp, act=act, dist=dist)
    adv = slip + spread / 2
    def close_trade(px, kind, stopish=True):
        nonlocal pos
        fill = px - pos * (adv if stopish else spread / 2)
        g = (fill - ep) * pos
        cost = comm / 100 * (ep + fill)
        trades.append(((g - cost) / ep * 100, kind))
        pos = 0
    def open_trade(d, px, i):
        nonlocal pos, ep, eb, best
        pos = d; ep = px + d * adv; eb = i; best = px
        if atr is not None:
            k = atr[i-1] / ep * 100
            P['sl'], P['tp'], P['act'], P['dist'] = sl0 * k, (tp0 * sl0 * k if tp0 else 0), act0 * k, dist0 * k
        # commission on entry added at close via (ep+fill)
    for i in range(lo, hi):
        o, h, l, c = O[i], H[i], L[i], C[i]
        pts = path(o, h, l, c)
        # walk the path segment by segment
        cur = pts[0]
        # gap at open handled as a segment from previous close to open with fills at open
        segs = [(cur, cur)] + [(pts[k], pts[k+1]) for k in range(3)]
        trail_ok_bar = True
        prev_best = best
        for (a, b) in segs:
            x = a
            for _ in range(6):
                up = b >= x
                ev = []  # (price, kind)
                if pend is not None and pend[0] != pos:
                    d, sp = pend
                    if d == 1 and (b >= sp if up else False) or (d == 1 and a == b and x >= sp): ev.append((max(sp, x), 'entry'))
                    if d == -1 and ((not up and b <= sp) or (a == b and x <= sp)): ev.append((min(sp, x), 'entry'))
                if pos != 0:
                    sl, tp, act, dist = P['sl'], P['tp'], P['act'], P['dist']
                    slp = ep * (1 - pos * sl / 100) if sl else None
                    tpp = ep * (1 + pos * tp / 100) if tp else None
                    actp = ep * (1 + pos * act / 100)
                    bref = best if mode == 'tv' else prev_best
                    trail_on = dist and ((bref - actp) * pos >= 0)
                    trp = bref - pos * ep * dist / 100 if trail_on else None
                    if pos == 1:
                        if slp and x <= slp if a == b else (slp and not up and b <= slp): ev.append((min(slp, x), 'SL'))
                        if trp and (x <= trp if a == b else (not up and b <= trp)): ev.append((min(trp, x), 'trail'))
                        if tpp and (x >= tpp if a == b else (up and b >= tpp)): ev.append((max(tpp, x), 'TP'))
                    else:
                        if slp and (x >= slp if a == b else (up and b >= slp)): ev.append((max(slp, x), 'SL'))
                        if trp and (x >= trp if a == b else (up and b >= trp)): ev.append((max(trp, x), 'trail'))
                        if tpp and (x <= tpp if a == b else (not up and b <= tpp)): ev.append((min(tpp, x), 'TP'))
                if not ev:
                    if pos != 0 and mode == 'tv': best = max(best, b) if pos == 1 else min(best, b)
                    break
                if mode == 'pess':  # adverse first when ambiguous
                    pri = {'SL': 0, 'trail': 1, 'entry': 2, 'TP': 3}
                    ev.sort(key=lambda e: (abs(e[0] - x), pri[e[1]]))
                else:
                    ev.sort(key=lambda e: abs(e[0] - x))
                px, kind = ev[0]
                if pos != 0 and mode == 'tv': best = max(best, px) if pos == 1 else min(best, px)
                if kind == 'entry':
                    d = pend[0]
                    if pos != 0: close_trade(px, 'rev')
                    open_trade(d, px, i); pend = None; prev_best = px if mode == 'pess' else best
                    if mode == 'pess': prev_best = px  # no trail activation on entry bar
                else:
                    close_trade(px, kind, stopish=(kind != 'TP'))
                x = px
        if pos != 0 and mode == 'pess':
            best = max(best, h) if pos == 1 else min(best, l)
        # bar close: script logic
        posAtClose = pos
        if not np.isnan(xp[i]):
            if wl[i] and posAtClose <= 0: pend = (1, math.ceil(xp[i] / tick) * tick)
            elif ws[i] and posAtClose >= 0: pend = (-1, math.floor(xp[i] / tick) * tick)
            else: pend = None
        else: pend = None
        if pend is not None and ((pend[0] == 1 and c >= pend[1]) or (pend[0] == -1 and c <= pend[1])):
            pass  # would fill at close in TV; rare, let it fill next bar open
        if failExit and pos != 0 and i - eb <= turnHold:
            if (pos == 1 and f[i] <= s[i]) or (pos == -1 and f[i] >= s[i]):
                close_trade(c, 'fail')
    if pos != 0: close_trade(C[hi-1], 'open', stopish=False)
    return trades

def stats(tr):
    r = np.array([t[0] for t in tr]) if tr else np.zeros(0)
    gp = r[r > 0].sum(); gl = -r[r < 0].sum()
    return dict(n=len(r), net=r.sum(), pf=gp / gl if gl > 0 else (np.inf if gp > 0 else 0), win=(r > 0).mean() * 100 if len(r) else 0,
                avg=r.mean() if len(r) else 0)
