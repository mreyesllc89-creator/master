"""XPW Shape Map v0.9.2 replay on real ticks.
Detector = faithful port of ShapeMapV7Core/V8Core (squares, arming, turns, ticks, CONT, Predict cross price).
Execution: Predict stops + catch-up, market modes, CONT stop, SL/TP/trail (Points or ATR), time stop,
opposite-signal Reverse, loss reversal (S4), FlashGold direction gate. Fixed lot, 0.60 RT per lot, real bid/ask fills.
Signal timeframe = chart timeframe (blank input).
"""
import numpy as np, pandas as pd, math
from dataclasses import dataclass, field
import sys; sys.path.insert(0, "../fg5"); from fg5 import Bars, bars_from_ticks, resample, SigParams, fgf_gate

@dataclass
class Det:
    rsiLen: int = 14; fastLen: int = 2; slowLen: int = 7; invertFill: bool = True
    areaLook: int = 20; loFrac: float = 0.20; hiFrac: float = 0.67
    allOn: bool = True; allCtx: int = 1
    botOn: bool = True; botMinW: int = 1; botMaxW: int = 3; botCtxIn: int = 2; botNeedLow: bool = True; botSepIn: int = 5
    topOn: bool = True; topMinW: int = 1; topMaxW: int = 2; topCtxIn: int = 3; topNeedHigh: bool = True; topSepIn: int = 5
    turnOn: bool = True; turnMax: int = 12; turnHold: int = 2
    tickOn: bool = True; atrLen: int = 14; botWickRange: float = 0.55; botWickAtr: float = 0.8; topWickRange: float = 0.70; topWickAtr: float = 1.20
    contOn: bool = True; contBigAtr: float = 1.0; contLook: int = 30; contNeedRed: bool = True; contRedMax: int = 12
    contPinch: float = 1.0; contAfter: int = 6; contSep: int = 5; contMirror: bool = True
    armEvery: bool = False; predBuf: float = 100.0

def detect_all(b: Bars, p: Det, tick):
    n = len(b.c); o, h, l, c = b.o, b.h, b.l, b.c
    rsi = np.full(n, np.nan); up = np.zeros(n); dn = np.zeros(n); validRsi = np.zeros(n, bool)
    fast = np.full(n, np.nan); slow = np.full(n, np.nan); vF = np.zeros(n, bool); vS = np.zeros(n, bool)
    isRed = np.zeros(n, bool); atr = np.full(n, np.nan); vA = np.zeros(n, bool); pos = np.full(n, 0.5)
    out = {k: np.zeros(n, bool) for k in ("botSq", "topSq", "turnUp", "turnDn", "botCross", "topCross", "crossUp", "crossDn", "armL", "armS", "botTick", "topTick", "contUp", "contDn", "validPred")}
    stopL = np.full(n, np.nan); stopS = np.full(n, np.nan); contHi = np.full(n, np.nan); contLo = np.full(n, np.nan)
    rl = p.rsiLen
    lastBot = -10000; lastTop = -10000; botArmed = False; topArmed = False; botArmBar = 0; topArmBar = 0
    cSt = [0, 0]; cBig = [-10000, -10000]; cFlip = [-10000, -10000]; cOdd = [0, 0]; cLast = [-10000, -10000]
    botCtx = p.allCtx if p.allOn else p.botCtxIn; topCtx = p.allCtx if p.allOn else p.topCtxIn
    botSep = 0 if p.allOn else p.botSepIn; topSep = 0 if p.allOn else p.topSepIn
    def redAt(j): return j >= 0 and isRed[j]
    def limeAt(j): return j >= 0 and not isRed[j]
    def linesValid(j): return j >= 0 and vF[j] and vS[j]
    def sma_valid(i, length):
        cnt = 0; s = 0.0; j = i
        while j >= 0 and cnt < length:
            if validRsi[j]: s += rsi[j]; cnt += 1
            j -= 1
        return (s/length, True) if cnt == length else (np.nan, False)
    def detect(i, wantRed, minW, maxW, ctx):
        for w in range(minW, max(minW, maxW) + 1):
            ok = True
            for k in range(ctx):
                if not (limeAt(i-k) if wantRed else redAt(i-k)): ok = False; break
            if ok:
                for k in range(w):
                    if not (redAt(i-ctx-k) if wantRed else limeAt(i-ctx-k)): ok = False; break
            if ok:
                for k in range(ctx):
                    if not (limeAt(i-ctx-w-k) if wantRed else redAt(i-ctx-w-k)): ok = False; break
            if ok: return True, w
        return False, 0
    def tr(i): return h[0]-l[0] if i == 0 else max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    for i in range(n):
        # RSI
        if i >= rl:
            if i == rl:
                u = d = 0.0
                for k in range(1, rl+1): u += max(c[k]-c[k-1], 0.0); d += max(c[k-1]-c[k], 0.0)
                up[i] = u/rl; dn[i] = d/rl
            else:
                up[i] = (up[i-1]*(rl-1) + max(c[i]-c[i-1], 0.0))/rl; dn[i] = (dn[i-1]*(rl-1) + max(c[i-1]-c[i], 0.0))/rl
            rsi[i] = 100.0 if dn[i] == 0 else (0.0 if up[i] == 0 else 100 - 100/(1 + up[i]/dn[i])); validRsi[i] = True
        fast[i], vF[i] = sma_valid(i, p.fastLen); slow[i], vS[i] = sma_valid(i, p.slowLen)
        isRed[i] = vF[i] and vS[i] and ((fast[i] > slow[i]) if p.invertFill else (fast[i] < slow[i]))
        if i >= p.atrLen - 1:
            if i == p.atrLen - 1: atr[i] = sum(tr(k) for k in range(p.atrLen))/p.atrLen
            else: atr[i] = (atr[i-1]*(p.atrLen-1) + tr(i))/p.atrLen
            vA[i] = True
        if vS[i]:
            hi = -np.inf; lo = np.inf
            for k in range(max(0, i-p.areaLook+1), i+1):
                if vS[k]: hi = max(hi, slow[k]); lo = min(lo, slow[k])
            pos[i] = (slow[i]-lo)/(hi-lo) if hi-lo > 0 else 0.5
        # events (confirmed bar)
        botArea = p.allOn or not p.botNeedLow or (i-botCtx >= 0 and pos[i-botCtx] <= p.loFrac)
        topArea = p.allOn or not p.topNeedHigh or (i-topCtx >= 0 and pos[i-topCtx] >= p.hiFrac)
        botRaw, _ = detect(i, True, p.botMinW, p.botMaxW, botCtx); topRaw, _ = detect(i, False, p.topMinW, p.topMaxW, topCtx)
        botSq = p.botOn and botRaw and botArea and i-lastBot >= botSep
        topSq = p.topOn and topRaw and topArea and i-lastTop >= topSep
        if botSq: lastBot = i; botArmed = True; botArmBar = i
        if topSq: lastTop = i; topArmed = True; topArmBar = i
        if botArmed and i-botArmBar > p.turnMax: botArmed = False
        if topArmed and i-topArmBar > p.turnMax: topArmed = False
        cu = linesValid(i) and linesValid(i-1) and fast[i] > slow[i] and fast[i-1] <= slow[i-1]
        cd = linesValid(i) and linesValid(i-1) and fast[i] < slow[i] and fast[i-1] >= slow[i-1]
        out["crossUp"][i] = cu; out["crossDn"][i] = cd
        out["botCross"][i] = p.turnOn and botArmed and cu; out["topCross"][i] = p.turnOn and topArmed and cd
        out["armL"][i] = p.turnOn and (p.armEvery or botArmed); out["armS"][i] = p.turnOn and (p.armEvery or topArmed)
        holdUp = holdDn = True
        for k in range(p.turnHold + 1):
            if not linesValid(i-k): holdUp = holdDn = False; continue
            if not (fast[i-k] > slow[i-k]): holdUp = False
            if not (fast[i-k] < slow[i-k]): holdDn = False
        j = i - p.turnHold
        cuj = linesValid(j) and linesValid(j-1) and fast[j] > slow[j] and fast[j-1] <= slow[j-1]
        cdj = linesValid(j) and linesValid(j-1) and fast[j] < slow[j] and fast[j-1] >= slow[j-1]
        tu = p.turnOn and botArmed and cuj and holdUp; td = p.turnOn and topArmed and cdj and holdDn
        if tu: botArmed = False
        if td: topArmed = False
        out["botSq"][i] = botSq; out["topSq"][i] = topSq; out["turnUp"][i] = tu; out["turnDn"][i] = td
        rng = h[i]-l[i]; upW = h[i]-max(o[i], c[i]); dnW = min(o[i], c[i])-l[i]
        wv = vA[i] and rng > 0 and atr[i] > 0
        out["botTick"][i] = p.tickOn and wv and dnW/rng >= p.botWickRange and dnW/atr[i] >= p.botWickAtr
        out["topTick"][i] = p.tickOn and wv and upW/rng >= p.topWickRange and upW/atr[i] >= p.topWickAtr
        # CONT (V7 ContStep)
        for dd, bull in ((0, True), (1, False)):
            inZone = (not isRed[i]) if bull else isRed[i]; odd = isRed[i] if bull else (not isRed[i])
            dirBar = c[i] > o[i] if bull else c[i] < o[i]; body = abs(c[i]-o[i])
            big = vA[i] and atr[i] > 0 and dirBar and body >= p.contBigAtr*atr[i]
            fired = False
            if cSt[dd] == 3 and inZone and dirBar and i-cFlip[dd] <= p.contAfter and i-cLast[dd] >= p.contSep:
                fired = True; cLast[dd] = i; cSt[dd] = 0
            elif big: cSt[dd] = 1; cBig[dd] = i; cOdd[dd] = 0
            elif cSt[dd] > 0 and i-cBig[dd] > p.contLook: cSt[dd] = 0
            elif cSt[dd] == 1:
                if odd: cSt[dd] = 2; cOdd[dd] = 1
                elif inZone and not p.contNeedRed: cSt[dd] = 3; cFlip[dd] = i
            elif cSt[dd] == 2:
                if odd:
                    cOdd[dd] += 1
                    if cOdd[dd] > p.contRedMax: cSt[dd] = 0
                elif inZone:
                    pinch = linesValid(i) and linesValid(i-1) and min(abs(fast[i]-slow[i]), abs(fast[i-1]-slow[i-1])) <= p.contPinch
                    if pinch: cSt[dd] = 3; cFlip[dd] = i
                    else: cSt[dd] = 0
            elif cSt[dd] == 3:
                if odd: cSt[dd] = 2; cOdd[dd] = 1
                elif i-cFlip[dd] > p.contAfter: cSt[dd] = 0
            if dd == 0 and p.contOn and fired: out["contUp"][i] = True; contHi[i] = h[i]
            if dd == 1 and p.contOn and p.contMirror and fired: out["contDn"][i] = True; contLo[i] = l[i]
        # Predict cross price (XpwV8Prediction)
        if validRsi[i] and p.slowLen > p.fastLen:
            okp = True; sumF = 0.0; sumS = 0.0
            if p.fastLen > 1:
                for k in range(p.fastLen-1):
                    if i-k < 0 or not validRsi[i-k]: okp = False; break
                    sumF += rsi[i-k]
            if okp:
                for k in range(max(p.slowLen-1, 1)):
                    if i-k < 0 or not validRsi[i-k]: okp = False; break
                    sumS += rsi[i-k]
            if okp:
                rStar = (sumS/p.slowLen - sumF/p.fastLen)/(1.0/p.fastLen - 1.0/p.slowLen)
                if 0.01 < rStar < 99.99:
                    a = float(rl); up1 = up[i]*(a-1)/a; dn1 = dn[i]*(a-1)/a; rs = rStar/(100-rStar)
                    r0 = 100*up1/(up1+dn1) if up1+dn1 > 0 else 50.0
                    xPx = c[i] + a*(rs*dn1-up1) if rStar >= r0 else c[i] - a*(up1/rs - dn1)
                    if np.isfinite(xPx):
                        stopL[i] = math.ceil((xPx + p.predBuf*tick)/tick)*tick; stopS[i] = math.floor((xPx - p.predBuf*tick)/tick)*tick
                        out["validPred"][i] = True
    out.update(fast=fast, slow=slow, atr=atr, stopL=stopL, stopS=stopS, contHi=contHi, contLo=contLo, isRed=isRed, validLines=vF & vS)
    return out

@dataclass
class Strat:
    sigMode: str = "Turn"          # Turn | Square | Tick | CONT
    turnEntry: str = "Predict"     # Predict | AtCross | AfterHold
    contEntry: str = "Close"       # Close | Stop
    contStopBuf: float = 50; contStopBars: int = 3
    catchUp: bool = True; maxChase: float = 0.0; oppMode: str = "Reverse"; failExit: bool = False
    exitUnit: str = "Points"; slPts: float = 7000; tpPts: float = 50000; trActPts: float = 1000; trDisPts: float = 100
    exAtrLen: int = 14; slAtrM: float = 2.0; tpR: float = 2.0; trActAtr: float = 4.0; trDisAtr: float = 0.2; trailOn: bool = True; timeStop: int = 0
    lossRevOn: bool = True; lossRevWhat: str = "Any"; lossRevMax: int = 1; lossRevTiny: bool = True; lossRevTinyPts: float = 1500
    fgf: bool = True
    def dists(self, a, tick):
        if self.exitUnit == "Points": return self.slPts*tick, self.tpPts*tick, self.trActPts*tick, self.trDisPts*tick
        return self.slAtrM*a, self.tpR*self.slAtrM*a, self.trActAtr*a, self.trDisAtr*a

def ex_atr(b: Bars, n):
    h, l, c = b.h, b.l, b.c; N = len(c); a = np.full(N, np.nan)
    tr = np.maximum(h-l, np.maximum(np.abs(h-np.roll(c, 1)), np.abs(l-np.roll(c, 1)))); tr[0] = h[0]-l[0]
    if N >= n:
        a[n-1] = tr[:n].mean()
        for i in range(n, N): a[i] = (a[i-1]*(n-1)+tr[i])/n
    return a

def run(b: Bars, t, bid, ask, det, exa, gb, gs, s: Strat, lots=0.1, unit=1.0, comm_side=0.30, tick=0.01):
    n = len(b.c); trades = []
    pos = None; pend = {1: None, -1: None}; pendBar = {1: -1, -1: -1}; pendKind = {1: "", -1: ""}
    market = []          # entries to execute at the next tick: (side, reason)
    chain = 0; placed = 0; blocked = 0; lastEntryTick = -1; lastEntryBar = -1
    q = lots*unit
    def fee(frac=1.0): return comm_side*lots*frac
    def close_pos(px, tt, reason, bar):
        nonlocal pos
        gross = (px-pos["px"])*pos["side"]*q; f = fee()*2
        trades.append(dict(entry_t=pos["entry_t"], exit_t=tt, entry_bar=pos["entry_bar"], exit_bar=bar, side=pos["side"], entry=pos["px"], exit=px, sl_dist=pos["sl"],
                           gross=gross, fee=f, net=gross-f, reason=reason, kind=pos["kind"], move=abs(px-pos["px"])))
        closed = dict(net=gross-f, side=pos["side"], reason=reason, move=abs(px-pos["px"]), kind=pos["kind"]); pos = None; return closed
    def open_pos(side, px, tt, bar, kind):
        nonlocal pos, lastEntryTick, lastEntryBar
        a = exa[bar-1] if bar >= 1 else np.nan          # ATR of the last completed bar at entry; updated when the entry bar closes
        sl, tp, act, dis = s.dists(a, tick)
        pos = dict(side=side, px=px, entry_t=tt, entry_bar=bar, best=px, trailStop=0.0, trailActive=False, sl=sl, tp=tp, act=act, dis=dis, kind=kind, timeExit=False, atr_locked=False)
        lastEntryBar = bar
    def after_close(closed, bar_prev_gate_idx, tt):
        """loss reversal decision (S4) after a close; queue a market entry for the next tick."""
        nonlocal chain
        if closed is None: return
        wasRev = closed["kind"] in ("loss-rev", "tiny-rev")
        tiny = s.lossRevTiny and closed["net"] >= 0 and closed["move"]/tick <= s.lossRevTinyPts
        wasLoss = closed["net"] < 0 or tiny
        if (not wasLoss) or (not wasRev): chain = 0
        exitCounts = s.lossRevWhat == "Any" or closed["reason"] in ("SL", "trail")
        chainOK = s.lossRevMax <= 0 or chain < s.lossRevMax
        if s.lossRevOn and wasLoss and exitCounts and chainOK and pos is None and not market:
            gi = max(bar_prev_gate_idx, 0)
            if closed["side"] > 0 and (not s.fgf or gs[gi]): market.append((-1, "tiny-rev" if tiny else "loss-rev")); chain += 1
            elif closed["side"] < 0 and (not s.fgf or gb[gi]): market.append((1, "tiny-rev" if tiny else "loss-rev")); chain += 1
    for i in range(n):
        s0, s1 = b.bs[i], b.be[i]
        k0 = s0
        while k0 < s1:
            tb = t[k0:s1]; bb = bid[k0:s1]; ba = ask[k0:s1]
            ev = []
            if market:
                ev.append((0, -2, "MKT"))
            if pos is not None:
                side = pos["side"]; ex = bb if side > 0 else ba
                if pos["timeExit"]: ev.append((0, -1, "time stop"))
                cm = np.maximum.accumulate(ex*side); best_sig = np.maximum(cm, pos["best"]*side)
                if pos["sl"] > 0:
                    hit = np.flatnonzero((ex-(pos["px"]-side*pos["sl"]))*side <= 0)
                    if len(hit): ev.append((hit[0], 0, "SL"))
                if pos["tp"] > 0:
                    hit = np.flatnonzero((ex-(pos["px"]+side*pos["tp"]))*side >= 0)
                    if len(hit): ev.append((hit[0], 1, "TP"))
                if s.trailOn and pos["dis"] > 0:
                    active = best_sig-pos["px"]*side >= pos["act"]
                    tstop = np.maximum(best_sig-pos["dis"], pos["trailStop"]*side if pos["trailActive"] else -np.inf)
                    hit = np.flatnonzero(active & (ex*side <= tstop))
                    if len(hit): ev.append((hit[0], 2, "trail"))
            for sd in (1, -1):
                if pend[sd] is None: continue
                hit = np.flatnonzero(ba >= pend[sd]) if sd > 0 else np.flatnonzero(bb <= pend[sd])
                if len(hit): ev.append((hit[0], 3, "PL" if sd > 0 else "PS"))
            if not ev: break
            ev.sort(key=lambda e: (e[0], e[1])); idx, _, kind = ev[0]; kk = k0+idx; tt = t[kk]
            if kind == "MKT":
                side, reason = market.pop(0)
                px = ask[kk] if side > 0 else bid[kk]
                closed = None
                if pos is not None and pos["side"] == -side: closed = close_pos(px, tt, "reverse", i)
                if pos is None:
                    open_pos(side, px, tt, i, reason); pend = {1: None, -1: None}; lastEntryTick = kk
                k0 = kk+1; continue
            if kind in ("SL", "TP", "trail", "time stop"):
                side = pos["side"]; seg = (bid[k0:kk+1] if side > 0 else ask[k0:kk+1])
                pos["best"] = max(pos["best"]*side, np.max(seg*side))*side
                raw = bid[kk] if side > 0 else ask[kk]
                closed = close_pos(raw, tt, kind, i)
                after_close(closed, i-1, tt)
                k0 = kk+1; continue
            sd = 1 if kind == "PL" else -1
            px = ask[kk] if sd > 0 else bid[kk]
            if pos is not None and pos["side"] == -sd:
                seg = (bid[k0:kk+1] if pos["side"] > 0 else ask[k0:kk+1]); pos["best"] = max(pos["best"]*pos["side"], np.max(seg*pos["side"]))*pos["side"]
                close_pos(px, tt, "reverse", i)
            if pos is None:
                open_pos(sd, px, tt, i, pendKind[sd]); lastEntryTick = kk
            pend = {1: None, -1: None}
            k0 = kk+1
        # ---- bar close ----
        if pos is not None:
            side = pos["side"]; seg = bid[s0:s1] if side > 0 else ask[s0:s1]
            if len(seg): pos["best"] = max(pos["best"]*side, np.max(seg*side))*side
            if s.trailOn and pos["dis"] > 0 and (pos["best"]-pos["px"])*side >= pos["act"]:
                nxt = pos["best"]-side*pos["dis"]
                if not pos["trailActive"] or (nxt-pos["trailStop"])*side > 0: pos["trailStop"] = nxt
                pos["trailActive"] = True
            if not pos["atr_locked"] and i == pos["entry_bar"] and s.exitUnit == "ATR" and not np.isnan(exa[i]):
                sl, tp, act, dis = s.dists(exa[i], tick); pos.update(sl=sl, tp=tp, act=act, dis=dis, atr_locked=True)
            if s.timeStop > 0 and i-pos["entry_bar"] >= s.timeStop: pos["timeExit"] = True
        posSide = 0 if pos is None else pos["side"]
        enteredThisBar = lastEntryBar == i
        gBuy = (not s.fgf) or gb[i]; gSell = (not s.fgf) or gs[i]
        # --- signals of this confirmed bar ---
        isTurn = s.sigMode == "Turn"; isCont = s.sigMode == "CONT"
        predict = isTurn and s.turnEntry == "Predict"; atCross = isTurn and s.turnEntry == "AtCross"; contStop = isCont and s.contEntry == "Stop"
        if s.sigMode == "Square": L, S = det["botSq"][i], det["topSq"][i]
        elif isTurn: L, S = (det["botCross"][i], det["topCross"][i]) if atCross else (det["turnUp"][i], det["turnDn"][i])
        elif isCont: L, S = det["contUp"][i], det["contDn"][i]
        else: L, S = det["botTick"][i], det["topTick"][i]
        if predict or contStop: L = S = False
        if L and S: L = S = False
        sigPlaced = False
        if L:
            if posSide < 0:
                if s.oppMode == "Reverse" and gBuy: market.append((1, "L sig")); sigPlaced = True
                elif s.oppMode != "Ignore": market.append((0, "close"))
            elif posSide == 0:
                if gBuy: market.append((1, "L sig")); sigPlaced = True; placed += 1
                else: blocked += 1
        if S:
            if posSide > 0:
                if s.oppMode == "Reverse" and gSell: market.append((-1, "S sig")); sigPlaced = True
                elif s.oppMode != "Ignore": market.append((0, "close"))
            elif posSide == 0:
                if gSell: market.append((-1, "S sig")); sigPlaced = True; placed += 1
                else: blocked += 1
        # "close" marker: handle as close at next tick
        market = [m for m in market if m[0] != 0] + ([(0, "close")] if any(m[0] == 0 for m in market) else [])
        if contStop:
            if posSide != 0: pendKind = {1: "", -1: ""}
            if det["contUp"][i] and (posSide == 0 or (posSide < 0 and s.oppMode == "Reverse")):
                if gBuy: pend[-1] = None; pend[1] = det["contHi"][i] + s.contStopBuf*tick; pendBar[1] = i; pendKind[1] = "L CONT stop"; placed += 1
                else: blocked += 1
            elif det["contDn"][i] and (posSide == 0 or (posSide > 0 and s.oppMode == "Reverse")):
                if gSell: pend[1] = None; pend[-1] = det["contLo"][i] - s.contStopBuf*tick; pendBar[-1] = i; pendKind[-1] = "S CONT stop"; placed += 1
                else: blocked += 1
            else:
                for sd in (1, -1):
                    if pend[sd] is not None and i-pendBar[sd] >= s.contStopBars: pend[sd] = None
        if predict:
            vl = det["validLines"][i]; f, sl_ = det["fast"][i], det["slow"][i]
            wantL = vl and det["armL"][i] and f < sl_ and det["validPred"][i] and posSide <= 0 and (posSide == 0 or s.oppMode == "Reverse")
            wantS = vl and det["armS"][i] and f > sl_ and det["validPred"][i] and posSide >= 0 and (posSide == 0 or s.oppMode == "Reverse")
            if wantL and not gBuy: blocked += 1; wantL = False
            if wantS and not gSell: blocked += 1; wantS = False
            pend[1] = det["stopL"][i] if wantL else None; pendKind[1] = "L predict"
            pend[-1] = det["stopS"][i] if wantS else None; pendKind[-1] = "S predict"
            if wantL or wantS: placed += 1
            if s.catchUp and not enteredThisBar:
                okL = s.maxChase <= 0 or i == 0 or np.isnan(det["stopL"][i-1]) or b.c[i]-det["stopL"][i-1] <= s.maxChase*tick
                okS = s.maxChase <= 0 or i == 0 or np.isnan(det["stopS"][i-1]) or det["stopS"][i-1]-b.c[i] <= s.maxChase*tick
                if det["crossUp"][i] and det["armL"][i] and okL and (posSide == 0 or (posSide < 0 and s.oppMode == "Reverse")):
                    if gBuy: market.append((1, "L cross")); sigPlaced = True
                    else: blocked += 1
                elif det["crossDn"][i] and det["armS"][i] and okS and (posSide == 0 or (posSide > 0 and s.oppMode == "Reverse")):
                    if gSell: market.append((-1, "S cross")); sigPlaced = True
                    else: blocked += 1
        # pending 'close' marker executes at next tick: convert to a close instruction
        if market and market[-1][0] == 0:
            market.pop()
            if pos is not None: pos["timeExit"] = True   # close at next tick (reuse path, reason label below)
    if pos is not None:
        close_pos(bid[-1] if pos["side"] > 0 else ask[-1], t[-1], "end", n-1)
    return pd.DataFrame(trades), dict(placed=placed, blocked=blocked)

def metrics(tr, lots, unit):
    if len(tr) == 0: return dict(trades=0, net=0.0, gross=0.0, fee=0.0, pf=np.nan, win=np.nan, maxdd=0.0, pos_weeks=np.nan, halves="", meanR=np.nan, longs=0, shorts=0, revs=0, reasons="{}")
    g = tr.sort_values("exit_t"); cum = g.net.cumsum(); dd = (cum.cummax()-cum).max()
    w = g.net[g.net > 0].sum(); l = -g.net[g.net < 0].sum(); half = len(g)//2
    wk = g.set_index(pd.to_datetime(g.exit_t, unit="ms")).net.resample("W").sum()
    R = g.net/(g.sl_dist*lots*unit)
    return dict(trades=len(g), net=g.net.sum(), gross=g.gross.sum(), fee=g.fee.sum(), pf=(w/l if l > 0 else np.inf), win=(g.net > 0).mean(), maxdd=dd,
                pos_weeks=(wk > 0).mean(), halves=f"{g.net.iloc[:half].sum():.2f}/{g.net.iloc[half:].sum():.2f}", meanR=R.replace([np.inf, -np.inf], np.nan).mean(),
                longs=int((g.side > 0).sum()), shorts=int((g.side < 0).sum()), revs=int(g.kind.isin(["loss-rev", "tiny-rev"]).sum()), reasons=str(g.reason.value_counts().to_dict()))
