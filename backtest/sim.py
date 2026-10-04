import numpy as np, pandas as pd, numba as nb, itertools, sys

def ema(x, n):
    a = 2/(n+1); out = np.empty_like(x); out[0] = x[0]
    for i in range(1, len(x)): out[i] = a*x[i] + (1-a)*out[i-1]
    return out
def rma(x, n):
    out = np.empty_like(x); out[:n] = np.nan; out[n-1] = np.mean(x[:n])
    for i in range(n, len(x)): out[i] = (out[i-1]*(n-1) + x[i])/n
    return out
def atr(h, l, c, n=14):
    tr = np.maximum(h-l, np.maximum(abs(h-np.r_[c[0], c[:-1]]), abs(l-np.r_[c[0], c[:-1]])))
    return rma(tr, n)

def signals(d, mode, read, fast, slow, brk):
    o,h,l,c = (d[k].values for k in ['open','high','low','close'])
    n = len(c); L = np.zeros(n, bool); S = np.zeros(n, bool)
    if mode == 'ema':
        ef, es = ema(c, fast), ema(c, slow)
        if read == 'open':   # decision at bar t for next open (proxy open = close[t])
            aF, aS = 2/(fast+1), 2/(slow+1)
            efN = aF*c + (1-aF)*ef; esN = aS*c + (1-aS)*es
            L = (efN > esN) & (ef <= es); S = (efN < esN) & (ef >= es)
        else:
            L[1:] = (ef[1:] > es[1:]) & (ef[:-1] <= es[:-1]); S[1:] = (ef[1:] < es[1:]) & (ef[:-1] >= es[:-1])
    elif mode == 'engulf':
        L[1:] = (c[1:]>o[1:])&(c[:-1]<o[:-1])&(c[1:]>=o[:-1])&(o[1:]<=c[:-1])
        S[1:] = (c[1:]<o[1:])&(c[:-1]>o[:-1])&(c[1:]<=o[:-1])&(o[1:]>=c[:-1])
    else:
        hh = pd.Series(h).rolling(brk).max().shift(1).values; ll = pd.Series(l).rolling(brk).min().shift(1).values
        L[1:] = (c[1:]>hh[1:])&(c[:-1]<=hh[:-1]); S[1:] = (c[1:]<ll[1:])&(c[:-1]>=ll[:-1])
    return L, S

@nb.njit(cache=True)
def run(o,h,l,c,L,S,trend,atrv,dirmode,slm,tpR,trA,trO,maxbars,comm,start,end):
    # dirmode 0 both 1 long 2 short ; slm<=0 no SL ; tpR<=0 no TP ; trA<=0 no trail ; maxbars<=0 off
    eq = 1.0; peak = 1.0; mdd = 0.0
    pos = 0; ent = 0.0; qty = 0.0; sl = 0.0; tp = 0.0; trOn = False; best = 0.0; trAct=0.0; trOff=0.0; ebar = 0
    pend = 0   # 1 go long, -1 go short, 2 flat
    pa = 0.0   # atr at signal
    ntr = 0; wins = 0; gp = 0.0; gl = 0.0
    for i in range(start, end):
        # 1) fill pending at open
        if pend != 0:
            if pos != 0:
                px = o[i]; pnl = qty*(px-ent)*pos - comm*qty*px
                eq += pnl; ntr += 1
                tot = pnl - (-comm*qty*ent)  # entry comm already paid
                if pnl > 0: wins += 1; gp += pnl
                else: gl -= pnl
                pos = 0
            if pend == 1 or pend == -1:
                pos = pend; ent = o[i]; qty = eq/ent; eq -= comm*qty*ent; ebar = i
                d = pa*slm
                sl = ent - pos*d if slm > 0 else np.nan
                tp = ent + pos*d*tpR if (tpR > 0 and slm > 0) else np.nan
                trAct = pa*trA; trOff = pa*trO; trOn = False; best = ent
            pend = 0
        # 2) intrabar exits, TV path: O->H->L->C if H nearer O else O->L->H->C
        if pos != 0:
            hfirst = (h[i]-o[i]) < (o[i]-l[i])
            pts = (o[i], h[i], l[i], c[i]) if hfirst else (o[i], l[i], h[i], c[i])
            xp = np.nan
            prev = o[i]
            for k in range(1, 4):
                p = pts[k]
                # move from prev to p; check stops along segment in order
                if pos == 1:
                    if p < prev:   # moving down: trailing/SL
                        st = sl
                        if trOn:
                            ts = best - trOff
                            st = ts if (np.isnan(st) or ts > st) else st
                        if not np.isnan(st) and p <= st:
                            xp = min(st, prev); break
                    else:          # moving up: TP, trail activation
                        if not np.isnan(tp) and p >= tp:
                            xp = max(tp, prev); break
                        if p > best: best = p
                        if trA > 0 and best - ent >= trAct: trOn = True
                else:
                    if p > prev:
                        st = sl
                        if trOn:
                            ts = best + trOff
                            st = ts if (np.isnan(st) or ts < st) else st
                        if not np.isnan(st) and p >= st:
                            xp = max(st, prev); break
                    else:
                        if not np.isnan(tp) and p <= tp:
                            xp = min(tp, prev); break
                        if p < best: best = p
                        if trA > 0 and ent - best >= trAct: trOn = True
                prev = p
            if not np.isnan(xp):
                pnl = qty*(xp-ent)*pos - comm*qty*xp
                eq += pnl; ntr += 1
                if qty*(xp-ent)*pos - comm*qty*(xp+ent) > 0: wins += 1; gp += pnl
                else: gl -= pnl
                pos = 0
        # mark to market
        m = eq + (qty*(c[i]-ent)*pos if pos != 0 else 0.0)
        if m > peak: peak = m
        dd = 1 - m/peak
        if dd > mdd: mdd = dd
        # 3) decisions at close
        if i == end-1: break
        tl = np.isnan(trend[i]) or trend[i] <= 0 or c[i] > trend[i]
        ts_ = np.isnan(trend[i]) or trend[i] <= 0 or c[i] < trend[i]
        pa = atrv[i]
        if L[i] and tl and dirmode != 2 and pos != 1: pend = 1
        elif S[i] and ts_ and dirmode != 1 and pos != -1: pend = -1
        elif pos == 1 and S[i]: pend = 2
        elif pos == -1 and L[i]: pend = 2
        elif pos != 0 and maxbars > 0 and i - ebar + 1 >= maxbars: pend = 2
    m = eq + (qty*(c[end-1]-ent)*pos if pos != 0 else 0.0)
    pf = gp/gl if gl > 0 else 99.0
    return m-1, mdd, ntr, (wins/ntr if ntr else 0.0), pf
