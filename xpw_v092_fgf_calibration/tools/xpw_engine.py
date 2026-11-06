"""Python/numba port of the XPW ShapeMap v0.9.2 + FlashGold EA decision logic.

Ported from the MQL5 sources in the handoff package:
  ShapeMapV7Core (RSI/SMA/ATR, square detection), ShapeMapV8Core (crosses,
  turns, wick ticks, prediction), ShapeMapV92Core (CONT state machine),
  ShapeMapV92Execution (ordered command planner), ShapeMapV8Execution
  (exit distances, position management), FlashGold DirectionFilterCore
  (TDI zones, burst signal, permission gate) and the Filter indicator mapping.

Bar-level approximations (no tick data):
  * signals are evaluated on confirmed bars (EnterTick=false semantics);
  * market orders fill at the next bar open +/- half spread;
  * virtual stop entries fill inside the bar at max(stop, open) +/- half spread;
  * SL/TP/trail are checked against bar high/low; when both are reachable in
    one bar the stop loss is assumed to be hit first; the trailing stop is
    advanced after the bar's exits are resolved;
  * a trade opened by a stop inside a bar is closed at its SL in that same bar
    only if the bar closes beyond the SL.
"""
import numpy as np
from numba import njit

EMPTY = 1e308
MISSING_DIR = 99


# --------------------------------------------------------------------------
# Indicators (XpwV7Calculate numerical path)
# --------------------------------------------------------------------------
@njit(cache=True)
def indicators(o, h, l, c, rsiLen, fastLen, slowLen, invertFill, areaLook, atrLen, exAtrLen):
    n = len(c)
    rsi = np.full(n, EMPTY); up = np.zeros(n); dn = np.zeros(n); validRsi = np.zeros(n, np.uint8)
    fast = np.full(n, EMPTY); slow = np.full(n, EMPTY)
    validFast = np.zeros(n, np.uint8); validSlow = np.zeros(n, np.uint8); isRed = np.zeros(n, np.uint8)
    atr = np.full(n, EMPTY); validAtr = np.zeros(n, np.uint8); pos = np.full(n, 0.5)
    exAtr = np.full(n, EMPTY); validExAtr = np.zeros(n, np.uint8)
    sumF = 0.0; sumS = 0.0
    for i in range(n):
        if rsiLen >= 2 and i >= rsiLen:
            if i == rsiLen:
                u = 0.0; d = 0.0
                for k in range(1, rsiLen + 1):
                    ch = c[k] - c[k - 1]
                    if ch > 0: u += ch
                    else: d -= ch
                up[i] = u / rsiLen; dn[i] = d / rsiLen
            else:
                ch = c[i] - c[i - 1]
                up[i] = (up[i - 1] * (rsiLen - 1) + (ch if ch > 0 else 0.0)) / rsiLen
                dn[i] = (dn[i - 1] * (rsiLen - 1) + (-ch if ch < 0 else 0.0)) / rsiLen
            if dn[i] == 0.0: rsi[i] = 100.0
            elif up[i] == 0.0: rsi[i] = 0.0
            else: rsi[i] = 100.0 - 100.0 / (1.0 + up[i] / dn[i])
            validRsi[i] = 1
            # NA-skipping SMA == plain SMA over the contiguous valid RSI run
            cnt = i - rsiLen + 1
            sumF += rsi[i]
            if cnt > fastLen: sumF -= rsi[i - fastLen]
            if cnt >= fastLen: fast[i] = sumF / fastLen; validFast[i] = 1
            sumS += rsi[i]
            if cnt > slowLen: sumS -= rsi[i - slowLen]
            if cnt >= slowLen: slow[i] = sumS / slowLen; validSlow[i] = 1
        if validFast[i] and validSlow[i]:
            isRed[i] = 1 if ((fast[i] > slow[i]) if invertFill else (fast[i] < slow[i])) else 0
        # ATR (ta.atr): TR at bar0 = high-low, SMA seed at length-1 then Wilder
        if atrLen >= 2 and i >= atrLen - 1:
            if i == atrLen - 1:
                s = 0.0
                for k in range(atrLen):
                    if k == 0: tr = h[0] - l[0]
                    else: tr = max(h[k] - l[k], max(abs(h[k] - c[k - 1]), abs(l[k] - c[k - 1])))
                    s += tr
                atr[i] = s / atrLen
            else:
                tr = max(h[i] - l[i], max(abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
                atr[i] = (atr[i - 1] * (atrLen - 1) + tr) / atrLen
            validAtr[i] = 1
        if exAtrLen >= 1 and i >= exAtrLen - 1:
            if i == exAtrLen - 1:
                s = 0.0
                for k in range(exAtrLen):
                    if k == 0: tr = h[0] - l[0]
                    else: tr = max(h[k] - l[k], max(abs(h[k] - c[k - 1]), abs(l[k] - c[k - 1])))
                    s += tr
                exAtr[i] = s / exAtrLen
            else:
                tr = max(h[i] - l[i], max(abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
                exAtr[i] = (exAtr[i - 1] * (exAtrLen - 1) + tr) / exAtrLen
            validExAtr[i] = 1
        if validSlow[i] and areaLook > 0:
            hi = -EMPTY; lo = EMPTY
            k0 = i - areaLook + 1
            if k0 < 0: k0 = 0
            for k in range(k0, i + 1):
                if validSlow[k]:
                    if slow[k] > hi: hi = slow[k]
                    if slow[k] < lo: lo = slow[k]
            rng = hi - lo
            pos[i] = (slow[i] - lo) / rng if rng > 0.0 else 0.5
    return rsi, up, dn, validRsi, fast, slow, validFast, validSlow, isRed, atr, validAtr, pos, exAtr, validExAtr


@njit(cache=True)
def _red_at(j, isRed, n):
    return j >= 0 and j < n and isRed[j] == 1


@njit(cache=True)
def _lime_at(j, isRed, n):
    return j >= 0 and j < n and isRed[j] == 0


@njit(cache=True)
def _lines_valid(j, validFast, validSlow, n):
    return j >= 0 and j < n and validFast[j] == 1 and validSlow[j] == 1


@njit(cache=True)
def _detect(i, wantRedWedge, minW, maxW, ctx, isRed, n):
    wHi = max(minW, maxW)
    for w in range(minW, wHi + 1):
        ok = True
        for k in range(ctx):
            if not ok: break
            if wantRedWedge:
                if not _lime_at(i - k, isRed, n): ok = False
            else:
                if not _red_at(i - k, isRed, n): ok = False
        for k in range(w):
            if not ok: break
            if wantRedWedge:
                if not _red_at(i - ctx - k, isRed, n): ok = False
            else:
                if not _lime_at(i - ctx - k, isRed, n): ok = False
        for k in range(ctx):
            if not ok: break
            if wantRedWedge:
                if not _lime_at(i - ctx - w - k, isRed, n): ok = False
            else:
                if not _red_at(i - ctx - w - k, isRed, n): ok = False
        if ok:
            return True, w
    return False, 0


@njit(cache=True)
def _cross_up(j, fast, slow, validFast, validSlow, n):
    return _lines_valid(j, validFast, validSlow, n) and _lines_valid(j - 1, validFast, validSlow, n) \
        and fast[j] > slow[j] and fast[j - 1] <= slow[j - 1]


@njit(cache=True)
def _cross_dn(j, fast, slow, validFast, validSlow, n):
    return _lines_valid(j, validFast, validSlow, n) and _lines_valid(j - 1, validFast, validSlow, n) \
        and fast[j] < slow[j] and fast[j - 1] >= slow[j - 1]


@njit(cache=True)
def events(o, h, l, c, rsi, up, dn, validRsi, fast, slow, validFast, validSlow, isRed, atr, validAtr, pos,
           rsiLen, fastLen, slowLen, loFrac, hiFrac, allOn, allCtx,
           botOn, botMinW, botMaxW, botCtxIn, botNeedLow, botSepIn,
           topOn, topMinW, topMaxW, topCtxIn, topNeedHigh, topSepIn,
           turnOn, turnMax, turnHold, armEvery,
           tickOn, botWickRange, botWickAtr, topWickRange, topWickAtr,
           contOn, contBigAtr, contLook, contNeedRed, contRedMax, contPinch, contAfter, contSep, contMirror):
    """XpwV92SignalEvaluate on confirmed bars (okBar=true). Returns per-bar
    event flags and the inverse-Wilder prediction price."""
    n = len(c)
    botSq = np.zeros(n, np.uint8); topSq = np.zeros(n, np.uint8)
    turnUp = np.zeros(n, np.uint8); turnDn = np.zeros(n, np.uint8)
    botCross = np.zeros(n, np.uint8); topCross = np.zeros(n, np.uint8)
    crossUp = np.zeros(n, np.uint8); crossDn = np.zeros(n, np.uint8)
    armL = np.zeros(n, np.uint8); armS = np.zeros(n, np.uint8)
    botTick = np.zeros(n, np.uint8); topTick = np.zeros(n, np.uint8)
    contUp = np.zeros(n, np.uint8); contDn = np.zeros(n, np.uint8)
    xPx = np.full(n, EMPTY); validPred = np.zeros(n, np.uint8)
    lastBotBar = -10000; lastTopBar = -10000
    botArmed = False; topArmed = False; botArmBar = 0; topArmBar = 0
    cSt = np.zeros(2, np.int64); cBigAt = np.full(2, -10000); cFlipAt = np.full(2, -10000)
    cOddCnt = np.zeros(2, np.int64); cLastSig = np.full(2, -10000)
    bc = allCtx if allOn else botCtxIn
    tc = allCtx if allOn else topCtxIn
    bs = 0 if allOn else botSepIn
    ts = 0 if allOn else topSepIn
    for i in range(n):
        ba = allOn or (not botNeedLow) or (i - bc >= 0 and pos[i - bc] <= loFrac)
        ta = allOn or (not topNeedHigh) or (i - tc >= 0 and pos[i - tc] >= hiFrac)
        br, bw = _detect(i, True, botMinW, botMaxW, bc, isRed, n)
        tr, tw = _detect(i, False, topMinW, topMaxW, tc, isRed, n)
        bot = botOn and br and ba and (i - lastBotBar >= bs)
        top = topOn and tr and ta and (i - lastTopBar >= ts)
        if bot:
            lastBotBar = i; botArmed = True; botArmBar = i; botSq[i] = 1
        if top:
            lastTopBar = i; topArmed = True; topArmBar = i; topSq[i] = 1
        if botArmed and i - botArmBar > turnMax: botArmed = False
        if topArmed and i - topArmBar > turnMax: topArmed = False
        cu = _cross_up(i, fast, slow, validFast, validSlow, n)
        cd = _cross_dn(i, fast, slow, validFast, validSlow, n)
        if turnOn and botArmed and cu: botCross[i] = 1
        if turnOn and topArmed and cd: topCross[i] = 1
        armL[i] = 1 if (turnOn and (armEvery or botArmed)) else 0
        armS[i] = 1 if (turnOn and (armEvery or topArmed)) else 0
        hu = True; hd = True
        for k in range(turnHold + 1):
            if not _lines_valid(i - k, validFast, validSlow, n):
                hu = False; hd = False; continue
            if not (fast[i - k] > slow[i - k]): hu = False
            if not (fast[i - k] < slow[i - k]): hd = False
        j = i - turnHold
        if turnOn and botArmed and _cross_up(j, fast, slow, validFast, validSlow, n) and hu:
            botArmed = False; turnUp[i] = 1
        if turnOn and topArmed and _cross_dn(j, fast, slow, validFast, validSlow, n) and hd:
            topArmed = False; turnDn[i] = 1
        if cu: crossUp[i] = 1
        if cd: crossDn[i] = 1
        rng = h[i] - l[i]
        uw = h[i] - max(o[i], c[i]); dw = min(o[i], c[i]) - l[i]
        wick = rng > 0 and validAtr[i] == 1 and atr[i] > 0
        if tickOn and wick and dw / rng >= botWickRange and dw / atr[i] >= botWickAtr: botTick[i] = 1
        if tickOn and wick and uw / rng >= topWickRange and uw / atr[i] >= topWickAtr: topTick[i] = 1
        # CONT state machines (XpwV92ContStep, confirmed=true, okBar=true)
        for d in range(2):
            bull = d == 0
            inZone = (isRed[i] == 0) if bull else (isRed[i] == 1)
            oddClr = (isRed[i] == 1) if bull else (isRed[i] == 0)
            dirBar = (c[i] > o[i]) if bull else (c[i] < o[i])
            big = validAtr[i] == 1 and atr[i] > 0 and dirBar and abs(c[i] - o[i]) >= contBigAtr * atr[i]
            ready = cSt[d] == 3 and inZone and dirBar and i - cFlipAt[d] <= contAfter and i - cLastSig[d] >= contSep
            fired = ready
            if ready:
                cLastSig[d] = i; cSt[d] = 0
            elif big:
                cSt[d] = 1; cBigAt[d] = i; cOddCnt[d] = 0
            elif cSt[d] > 0 and i - cBigAt[d] > contLook:
                cSt[d] = 0
            elif cSt[d] == 1:
                if oddClr: cSt[d] = 2; cOddCnt[d] = 1
                elif inZone and not contNeedRed: cSt[d] = 3; cFlipAt[d] = i
            elif cSt[d] == 2:
                if oddClr:
                    cOddCnt[d] += 1
                    if cOddCnt[d] > contRedMax: cSt[d] = 0
                elif inZone:
                    pinch = _lines_valid(i, validFast, validSlow, n) and _lines_valid(i - 1, validFast, validSlow, n) \
                        and min(abs(fast[i] - slow[i]), abs(fast[i - 1] - slow[i - 1])) <= contPinch
                    if pinch: cSt[d] = 3; cFlipAt[d] = i
                    else: cSt[d] = 0
            elif cSt[d] == 3:
                if oddClr: cSt[d] = 2; cOddCnt[d] = 1
                elif i - cFlipAt[d] > contAfter: cSt[d] = 0
            if fired:
                if bull:
                    if contOn: contUp[i] = 1
                else:
                    if contOn and contMirror: contDn[i] = 1
        # Prediction (XpwV8Prediction with tickSize=1)
        if slowLen > fastLen and validRsi[i] == 1:
            okp = True; sF = 0.0; sS = 0.0
            if fastLen > 1:
                L = fastLen - 1
                if i - L + 1 < 0: okp = False
                else:
                    for k in range(L):
                        if validRsi[i - k] == 0: okp = False; break
                        sF += rsi[i - k]
            if okp:
                L = max(slowLen - 1, 1)
                if i - L + 1 < 0: okp = False
                else:
                    for k in range(L):
                        if validRsi[i - k] == 0: okp = False; break
                        sS += rsi[i - k]
            if okp:
                rStar = (sS / slowLen - sF / fastLen) / (1.0 / fastLen - 1.0 / slowLen)
                if rStar > 0.01 and rStar < 99.99:
                    a = float(rsiLen)
                    up1 = up[i] * (a - 1.0) / a; dn1 = dn[i] * (a - 1.0) / a
                    rs = rStar / (100.0 - rStar)
                    r0 = 100.0 * up1 / (up1 + dn1) if up1 + dn1 > 0.0 else 50.0
                    if rStar >= r0: x = c[i] + a * (rs * dn1 - up1)
                    else: x = c[i] - a * (up1 / rs - dn1)
                    if np.isfinite(x):
                        xPx[i] = x; validPred[i] = 1
    return botSq, topSq, turnUp, turnDn, botCross, topCross, crossUp, crossDn, armL, armS, botTick, topTick, contUp, contDn, xPx, validPred


# --------------------------------------------------------------------------
# FlashGold Direction Filter
# --------------------------------------------------------------------------
@njit(cache=True)
def tdi_dirs(c, rsiLen, fastLen):
    """FgfTdiSeries: direction of the fast SMA of RSI (+1/-1/0)."""
    n = len(c)
    dirs = np.zeros(n, np.int8)
    rsi = np.full(n, EMPTY)
    gain = 0.0; loss = 0.0; fastPrev = EMPTY; fastSum = 0.0
    eps = 1e-10
    for i in range(1, n):
        upv = max(c[i] - c[i - 1], 0.0); dnv = max(c[i - 1] - c[i], 0.0)
        if i <= rsiLen:
            gain += upv; loss += dnv
            if i < rsiLen: continue
            gain /= rsiLen; loss /= rsiLen
        else:
            gain = (gain * (rsiLen - 1) + upv) / rsiLen
            loss = (loss * (rsiLen - 1) + dnv) / rsiLen
        if abs(loss) <= eps: r = 100.0
        elif abs(gain) <= eps: r = 0.0
        else: r = 100.0 - 100.0 / (1.0 + gain / loss)
        rsi[i] = r
        fastSum += r
        if i - rsiLen >= fastLen: fastSum -= rsi[i - fastLen]
        if i - rsiLen + 1 >= fastLen:
            f = fastSum / fastLen
            if fastPrev != EMPTY:
                if f - fastPrev > eps: dirs[i] = 1
                elif f - fastPrev < -eps: dirs[i] = -1
                else: dirs[i] = 0
            fastPrev = f
    return dirs


@njit(cache=True)
def _closed_at(times, period, t):
    """index of last bar with end (time+period) <= t, else -1"""
    lo = 0; hi = len(times) - 1; ans = -1
    while lo <= hi:
        m = (lo + hi) // 2
        if times[m] + period <= t: ans = m; lo = m + 1
        else: hi = m - 1
    return ans


@njit(cache=True)
def _open_at(times, t):
    lo = 0; hi = len(times) - 1; ans = -1
    while lo <= hi:
        m = (lo + hi) // 2
        if times[m] <= t: ans = m; lo = m + 1
        else: hi = m - 1
    return ans


@njit(cache=True)
def fgf_filter(ft, fo, fh, fl, fc, fperiod, parentT, parentDirs, parentPeriod,
               childT0, childD0, childP0, childOn0, childT1, childD1, childP1, childOn1,
               childT2, childD2, childP2, childOn2, htfClosed,
               tick, spreadPts, entryDistPts, holdBars, holdFavPts, onePerBar, distUnit,
               burstAtr, entryDistAtr, holdFavAtr, burstPts, useBurst, anyCombo, driftBars, useDrift,
               useZones, minAligned, flatParent, ignoreNa, levelMode):
    """FgfBuildFilter over filter-timeframe bars with parent/child zone mapping
    as the Filter indicator does for historical bars. Returns armed state per
    filter bar."""
    n = len(fc)
    armedAtA = np.full(n, -1, np.int64); armedBarA = np.full(n, -1, np.int64)
    armedPriceA = np.full(n, EMPTY); armedDirA = np.zeros(n, np.int64); armedIdA = np.zeros(n, np.int64)
    armedAtrA = np.full(n, EMPTY)
    holdActive = False; holdIsBuy = False; holdSignalBar = -1; lastEntryBar = -1
    holdSignalMid = EMPTY; atr = EMPTY; trSeed = 0.0
    armedAt = -1; armedBar = -1; armedDir = 0; armedId = 0; armedPrice = EMPTY; armedAtr = EMPTY
    eps = 1e-10
    for i in range(n):
        bEnd = ft[i] + fperiod
        if i == 0: tr = fh[i] - fl[i]
        else: tr = max(fh[i] - fl[i], max(abs(fh[i] - fc[i - 1]), abs(fl[i] - fc[i - 1])))
        if i < 14:
            trSeed += tr
            if i == 13: atr = trSeed / 14.0
        else:
            atr = (atr * 13.0 + tr) / 14.0
        # parent: last parent bar closed at or before this filter bar's end
        k = _closed_at(parentT, parentPeriod, bEnd)
        parent = 0 if k < 0 else int(parentDirs[k])
        aligned = 0; active = 0
        for z in range(3):
            if z == 0: on = childOn0; cT = childT0; cD = childD0; cP = childP0
            elif z == 1: on = childOn1; cT = childT1; cD = childD1; cP = childP1
            else: on = childOn2; cT = childT2; cD = childD2; cP = childP2
            if not on: continue
            previousOn = htfClosed and cP > fperiod
            if previousOn: kk = _open_at(cT, ft[i]) - 1
            else: kk = _closed_at(cT, cP, bEnd)
            d = MISSING_DIR if kk < 0 else int(cD[kk])
            zon = (not ignoreNa) or d != MISSING_DIR
            if zon: active += 1
            if zon and parent != 0 and d == parent: aligned += 1
        required = min(minAligned, active)
        parentFlatAllowed = flatParent and parent == 0
        zoneReady = active == 0 or aligned >= required
        zoneBuy = (not useZones) or ((parent == 1 or parentFlatAllowed) and zoneReady)
        zoneSell = (not useZones) or ((parent == -1 or parentFlatAllowed) and zoneReady)
        halfSpread = spreadPts * tick * 0.5
        bid = fc[i] - halfSpread; ask = fc[i] + halfSpread; mid = (bid + ask) * 0.5
        atrPts = atr / tick if atr != EMPTY else EMPTY
        if distUnit == 0:
            burstThreshold = burstAtr * atrPts if atrPts != EMPTY else EMPTY
            entryDistance = entryDistAtr * atrPts if atrPts != EMPTY else EMPTY
            holdFavorable = holdFavAtr * atrPts if atrPts != EMPTY else EMPTY
        else:
            burstThreshold = burstPts; entryDistance = entryDistPts; holdFavorable = holdFavPts
        burst = (mid - fc[i - 1]) / tick if i > 0 else EMPTY
        drift = (mid - fc[i - driftBars]) / tick if i >= driftBars else EMPTY
        burstBuy = burst != EMPTY and burstThreshold != EMPTY and burst - burstThreshold >= -eps
        burstSell = burst != EMPTY and burstThreshold != EMPTY and burst + burstThreshold <= eps
        driftBuy = (not useDrift) or (drift != EMPTY and drift > eps)
        driftSell = (not useDrift) or (drift != EMPTY and drift < -eps)
        if anyCombo:
            rawBuy = zoneBuy and ((not useBurst) or burstBuy or parent == 1)
            rawSell = zoneSell and ((not useBurst) or burstSell or parent == -1)
        else:
            rawBuy = zoneBuy and burstBuy; rawSell = zoneSell and burstSell
        buyCandidate = rawBuy and driftBuy; sellCandidate = rawSell and driftSell
        canFire = (not onePerBar) or lastEntryBar < 0 or lastEntryBar != i
        buy = False; sell = False; buyEntry = EMPTY; sellEntry = EMPTY
        if buyCandidate and canFire:
            if holdBars == 0:
                buyEntry = ask + entryDistance * tick if entryDistance != EMPTY else EMPTY
                buy = True; lastEntryBar = i
            elif not holdActive:
                holdActive = True; holdIsBuy = True; holdSignalBar = i; holdSignalMid = mid
            elif holdIsBuy:
                move = (mid - holdSignalMid) / tick
                if i - holdSignalBar >= holdBars and holdFavorable != EMPTY and move - holdFavorable >= -eps:
                    buyEntry = ask + entryDistance * tick if entryDistance != EMPTY else EMPTY
                    buy = True; lastEntryBar = i; holdActive = False
        if sellCandidate and canFire:
            if holdBars == 0:
                sellEntry = bid - entryDistance * tick if entryDistance != EMPTY else EMPTY
                sell = True; lastEntryBar = i
            elif not holdActive:
                holdActive = True; holdIsBuy = False; holdSignalBar = i; holdSignalMid = mid
            elif not holdIsBuy:
                move = (holdSignalMid - mid) / tick
                if i - holdSignalBar >= holdBars and holdFavorable != EMPTY and move - holdFavorable >= -eps:
                    sellEntry = bid - entryDistance * tick if entryDistance != EMPTY else EMPTY
                    sell = True; lastEntryBar = i; holdActive = False
        if holdActive and ((holdIsBuy and not zoneBuy) or ((not holdIsBuy) and not zoneSell)):
            holdActive = False; holdSignalBar = -1; holdSignalMid = EMPTY
        signalPrice = buyEntry if buy else (sellEntry if sell else EMPTY)
        if buy or sell:
            armedAt = bEnd; armedBar = i
            armedPrice = signalPrice if (levelMode == 0 and signalPrice != EMPTY) else fc[i]
            armedDir = 1 if buy else -1; armedId += 1; armedAtr = atr
        armedAtA[i] = armedAt; armedBarA[i] = armedBar; armedPriceA[i] = armedPrice
        armedDirA[i] = armedDir; armedIdA[i] = armedId; armedAtrA[i] = armedAtr
    return armedAtA, armedBarA, armedPriceA, armedDirA, armedIdA, armedAtrA


@njit(cache=True)
def fgf_permissions(ct, cc, cperiod, ft, fperiod, armedAtA, armedBarA, armedPriceA, armedDirA, armedAtrA,
                    enabled, windowMode, minutes, bars, bandAtr, against, allowBuy, allowSell, tick):
    """Per chart bar permission mask (1=buy, 2=sell) as the Filter indicator
    computes for historical bars with checkMode=Tick: the filter bar is the
    last one closed at the chart bar end; value is the chart close."""
    n = len(cc)
    buyOK = np.zeros(n, np.uint8); sellOK = np.zeros(n, np.uint8)
    eps = 1e-10
    for i in range(n):
        if not enabled:
            buyOK[i] = 1; sellOK[i] = 1; continue
        cEnd = ct[i] + cperiod
        fi = _closed_at(ft, fperiod, cEnd)
        if fi < 0: continue
        armedAt = armedAtA[fi]; armedBar = armedBarA[fi]; armedPrice = armedPriceA[fi]
        armedDir = armedDirA[fi]; armedAtr = armedAtrA[fi]
        clock = cEnd
        fEnd = ft[fi] + fperiod
        index = fi if clock == fEnd else fi + 1
        armed = armedAt >= 0 and clock >= armedAt
        if windowMode == 1: opn = armed and clock < armedAt + minutes * 60
        elif windowMode == 2: opn = armed and index < armedBar + bars
        else: opn = armed
        onSigBar = armed and index == armedBar
        band = bandAtr * (armedAtr if armedAtr != EMPTY else 0.0)
        inUp = False; inDn = False
        if armedPrice != EMPTY:
            hasBand = band > eps
            if hasBand:
                upper = np.ceil((armedPrice + band) / tick - 1e-9) * tick
                lower = np.floor((armedPrice - band) / tick + 1e-9) * tick
            else:
                upper = armedPrice; lower = armedPrice
            value = cc[i]
            atBuy = onSigBar and armedDir > 0 and value - armedPrice >= -eps
            atSell = onSigBar and armedDir < 0 and value - armedPrice <= eps
            if hasBand:
                inUp = value - (upper + tick / 2.0) > eps
                inDn = value - (lower - tick / 2.0) < -eps
            else:
                inUp = (value - armedPrice > eps) or atBuy
                inDn = (value - armedPrice < -eps) or atSell
        if opn and allowBuy and inUp and (against or armedDir > 0): buyOK[i] = 1
        if opn and allowSell and inDn and (against or armedDir < 0): sellOK[i] = 1
    return buyOK, sellOK


# --------------------------------------------------------------------------
# Execution simulator (XpwV92BuildPlan + XpwV8ManagePosition)
# Signals on chart bars; fills, stops and trailing resolved on 1-minute sub-bars.
# --------------------------------------------------------------------------
@njit(cache=True)
def _half_spread(price, spreadPts, spreadPct, tick):
    s = spreadPts * tick
    if spreadPct * price > s: s = spreadPct * price
    return s * 0.5


@njit(cache=True)
def simulate(o, h, l, c, sub_start, sub_end, so, sh, sl_, sc,
             exAtr, validExAtr, fast, slow, validFast, validSlow,
             botSq, topSq, turnUp, turnDn, botCross, topCross, crossUp, crossDn, armL, armS,
             botTick, topTick, contUp, contDn, xPx, validPred, fgfBuy, fgfSell,
             sigMode, tradeDir, turnEntry, failExit, oppMode, armEvery, predBuf, catchUp, maxChase,
             contEntry, contStopBuf, contStopBars, exitUnit, slPts, tpPts, slAtrM, tpR, trailOn,
             trActPts, trDisPts, trActAtr, trDisAtr, timeStop, turnHold,
             lossRevOn, lossRevWhat, lossRevMax, lossRevTiny, lossRevTinyPts,
             tick, spreadPts, spreadPct, commPts, commPct, maxTrades):
    n = len(c)
    tEntryI = np.zeros(maxTrades, np.int64); tExitI = np.zeros(maxTrades, np.int64)
    tSide = np.zeros(maxTrades, np.int64); tEntryPx = np.zeros(maxTrades); tExitPx = np.zeros(maxTrades)
    tPnl = np.zeros(maxTrades); tReason = np.zeros(maxTrades, np.int64); tKind = np.zeros(maxTrades, np.int64)
    nt = 0
    equity = np.zeros(n)
    predict = sigMode == 1 and turnEntry == 0
    atCross = sigMode == 1 and turnEntry == 1
    contStop = sigMode == 3 and contEntry == 1
    canL = tradeDir != 2; canS = tradeDir != 1
    pos = 0; entryPx = 0.0; entryI = -1; best = 0.0; trailStop = 0.0; trailActive = False
    posKind = 0
    slTk = 0.0; tpTk = 0.0; taTk = 0.0; tdTk = 0.0; hasSL = False; hasTP = False; hasTrail = False
    qClose = False; qCloseReason = 0
    qEntrySide = 0; qEntryKind = 0
    pendL = False; pendLpx = 0.0; pendS = False; pendSpx = 0.0; pendKind = 0
    contStopBar = -10000; contStopDir = 0
    lossRevSeen = 0; lossRevChain = 0; closedCount = 0
    lastPnl = 0.0; lastSide = 0; lastEntryPx = 0.0; lastExitPx = 0.0; lastKind = 0; lastReason = 0
    realized = 0.0
    prevStopL = EMPTY; prevStopS = EMPTY; prevValid = False

    for i in range(1, n):
        enteredThisBar = False
        k0 = sub_start[i]; k1 = sub_end[i]
        px_o = o[i]
        half = _half_spread(px_o, spreadPts, spreadPct, tick)
        comm = commPts * tick + commPct * px_o
        # ---- pending market orders from the previous close fill at the chart open
        if qClose and pos != 0:
            ex = px_o - half if pos > 0 else px_o + half
            pnl = (ex - entryPx) * pos - comm
            if nt < maxTrades:
                tEntryI[nt] = entryI; tExitI[nt] = i; tSide[nt] = pos; tEntryPx[nt] = entryPx; tExitPx[nt] = ex
                tPnl[nt] = pnl; tReason[nt] = qCloseReason; tKind[nt] = posKind; nt += 1
            realized += pnl; closedCount += 1
            lastPnl = pnl; lastSide = pos; lastEntryPx = entryPx; lastExitPx = ex; lastKind = posKind; lastReason = qCloseReason
            pos = 0
        qClose = False
        if qEntrySide != 0:
            if pos != 0 and pos != qEntrySide:
                ex = px_o - half if pos > 0 else px_o + half
                pnl = (ex - entryPx) * pos - comm
                if nt < maxTrades:
                    tEntryI[nt] = entryI; tExitI[nt] = i; tSide[nt] = pos; tEntryPx[nt] = entryPx; tExitPx[nt] = ex
                    tPnl[nt] = pnl; tReason[nt] = 5; tKind[nt] = posKind; nt += 1
                realized += pnl; closedCount += 1
                lastPnl = pnl; lastSide = pos; lastEntryPx = entryPx; lastExitPx = ex; lastKind = posKind; lastReason = 5
                pos = 0
            if pos == 0:
                pos = qEntrySide; entryPx = px_o + half * pos; entryI = i; best = entryPx; trailStop = 0.0; trailActive = False
                posKind = qEntryKind
                if exitUnit == 0:
                    slTk = slPts; tpTk = tpPts; taTk = trActPts; tdTk = trDisPts
                    hasSL = slTk > 0; hasTP = tpTk > 0; hasTrail = trailOn and tdTk > 0
                else:
                    if validExAtr[i] == 1:
                        a = exAtr[i]; slTk = slAtrM * a / tick; tpTk = tpR * slTk; taTk = trActAtr * a / tick; tdTk = trDisAtr * a / tick
                        hasSL = slTk > 0; hasTP = tpTk > 0; hasTrail = trailOn and tdTk > 0
                    else:
                        hasSL = False; hasTP = False; hasTrail = False
                pendL = False; pendS = False
            qEntrySide = 0
        # ---- sub-bar loop: stop fills and exit management
        for k in range(k0, k1):
            hk = _half_spread(so[k], spreadPts, spreadPct, tick)
            ck = commPts * tick + commPct * so[k]
            filledNow = False
            if pendL or pendS:
                fillL = pendL and (pos == 0 or (pos < 0 and oppMode == 0)) and sh[k] >= pendLpx - hk
                fillS = pendS and (pos == 0 or (pos > 0 and oppMode == 0)) and sl_[k] <= pendSpx + hk
                side = 0
                if fillL and fillS:
                    side = 1 if abs(pendLpx - so[k]) <= abs(pendSpx - so[k]) else -1
                elif fillL: side = 1
                elif fillS: side = -1
                if side != 0:
                    fillPx = max(pendLpx, so[k] + hk) if side > 0 else min(pendSpx, so[k] - hk)
                    if pos != 0 and pos != side:
                        ex = fillPx - 2 * hk if pos > 0 else fillPx + 2 * hk
                        pnl = (ex - entryPx) * pos - ck
                        if nt < maxTrades:
                            tEntryI[nt] = entryI; tExitI[nt] = i; tSide[nt] = pos; tEntryPx[nt] = entryPx; tExitPx[nt] = ex
                            tPnl[nt] = pnl; tReason[nt] = 5; tKind[nt] = posKind; nt += 1
                        realized += pnl; closedCount += 1
                        lastPnl = pnl; lastSide = pos; lastEntryPx = entryPx; lastExitPx = ex; lastKind = posKind; lastReason = 5
                        pos = 0
                    pos = side; entryPx = fillPx; entryI = i; best = entryPx; trailStop = 0.0; trailActive = False
                    posKind = pendKind; enteredThisBar = True; filledNow = True
                    if exitUnit == 0:
                        slTk = slPts; tpTk = tpPts; taTk = trActPts; tdTk = trDisPts
                        hasSL = slTk > 0; hasTP = tpTk > 0; hasTrail = trailOn and tdTk > 0
                    else:
                        if validExAtr[i] == 1:
                            a = exAtr[i]; slTk = slAtrM * a / tick; tpTk = tpR * slTk; taTk = trActAtr * a / tick; tdTk = trDisAtr * a / tick
                            hasSL = slTk > 0; hasTP = tpTk > 0; hasTrail = trailOn and tdTk > 0
                        else:
                            hasSL = False; hasTP = False; hasTrail = False
                    pendL = False; pendS = False
                    if pendKind == 2: contStopDir = 0
            if pos != 0:
                slv = entryPx - pos * slTk * tick if hasSL else 0.0
                tpv = entryPx + pos * tpTk * tick if hasTP else 0.0
                if hasTrail and trailActive and (slv == 0.0 or (trailStop - slv) * pos > 0): slv = trailStop
                exitPx = 0.0; reason = 0
                execClose = sc[k] - hk if pos > 0 else sc[k] + hk
                if filledNow:
                    # the stop filled somewhere inside this minute: only a close beyond the SL is counted
                    if slv != 0.0 and (execClose - slv) * pos <= 0: exitPx = slv; reason = 1
                else:
                    execOpen = so[k] - hk if pos > 0 else so[k] + hk
                    execAdv = (sl_[k] - hk) if pos > 0 else (sh[k] + hk)
                    execFav = (sh[k] - hk) if pos > 0 else (sl_[k] + hk)
                    trailWins = trailActive and slv == trailStop
                    if slv != 0.0 and (execOpen - slv) * pos <= 0:
                        exitPx = execOpen; reason = 3 if trailWins else 1
                    elif tpv != 0.0 and (execOpen - tpv) * pos >= 0:
                        exitPx = execOpen; reason = 2
                    elif slv != 0.0 and (execAdv - slv) * pos <= 0:
                        exitPx = slv; reason = 3 if trailWins else 1
                    elif tpv != 0.0 and (execFav - tpv) * pos >= 0:
                        exitPx = tpv; reason = 2
                    else:
                        # pessimistic intrabar order: favorable extreme first, then adverse
                        if (execFav - best) * pos > 0: best = execFav
                        if hasTrail and (best - entryPx) * pos >= taTk * tick:
                            trailActive = True
                            nxt = best - pos * tdTk * tick
                            if trailStop == 0.0 or (nxt - trailStop) * pos > 0: trailStop = nxt
                            if (execAdv - trailStop) * pos <= 0:
                                exitPx = trailStop
                                reason = 3
                if reason != 0:
                    pnl = (exitPx - entryPx) * pos - ck
                    if nt < maxTrades:
                        tEntryI[nt] = entryI; tExitI[nt] = i; tSide[nt] = pos; tEntryPx[nt] = entryPx; tExitPx[nt] = exitPx
                        tPnl[nt] = pnl; tReason[nt] = reason; tKind[nt] = posKind; nt += 1
                    realized += pnl; closedCount += 1
                    lastPnl = pnl; lastSide = pos; lastEntryPx = entryPx; lastExitPx = exitPx; lastKind = posKind; lastReason = reason
                    pos = 0
        # ---- equity mark at chart close
        if pos != 0:
            mk = c[i] - half if pos > 0 else c[i] + half
            equity[i] = realized + (mk - entryPx) * pos
        else:
            equity[i] = realized
        # ---- plan at bar close (confirmed)
        fb = fgfBuy[i] == 1; fs = fgfSell[i] == 1
        if sigMode == 0: ls = botSq[i] == 1; ss = topSq[i] == 1
        elif sigMode == 1:
            if atCross: ls = botCross[i] == 1; ss = topCross[i] == 1
            else: ls = turnUp[i] == 1; ss = turnDn[i] == 1
        elif sigMode == 3: ls = contUp[i] == 1; ss = contDn[i] == 1
        else: ls = botTick[i] == 1; ss = topTick[i] == 1
        if predict or contStop or (ls and ss): ls = False; ss = False
        hasMarketSig = ls or ss
        if ls:
            if pos < 0:
                if oppMode == 0 and canL and fb: qEntrySide = 1; qEntryKind = 0
                elif oppMode != 2: qClose = True; qCloseReason = 4
            elif pos == 0 and canL and fb: qEntrySide = 1; qEntryKind = 0
        if ss:
            if pos > 0:
                if oppMode == 0 and canS and fs: qEntrySide = -1; qEntryKind = 0
                elif oppMode != 2: qClose = True; qCloseReason = 4
            elif pos == 0 and canS and fs: qEntrySide = -1; qEntryKind = 0
        if contStop:
            if pos != 0: contStopDir = 0
            cu = contUp[i] == 1; cd = contDn[i] == 1
            if cu and canL and (pos == 0 or (pos < 0 and oppMode == 0)) and fb:
                pendS = False; pendL = True; pendLpx = h[i] + contStopBuf * tick; pendKind = 2
                contStopBar = i; contStopDir = 1
            elif cd and canS and (pos == 0 or (pos > 0 and oppMode == 0)) and fs:
                pendL = False; pendS = True; pendSpx = l[i] - contStopBuf * tick; pendKind = 2
                contStopBar = i; contStopDir = -1
            elif contStopDir != 0 and i - contStopBar >= contStopBars:
                pendL = False; pendS = False; contStopDir = 0
            if oppMode == 1:
                if pos > 0 and cd: qClose = True; qCloseReason = 4
                if pos < 0 and cu: qClose = True; qCloseReason = 4
        if predict:
            vl = validFast[i] == 1 and validSlow[i] == 1
            vp = validPred[i] == 1
            stopL = EMPTY; stopS = EMPTY
            if vp:
                stopL = np.ceil((xPx[i] + predBuf * tick) / tick) * tick
                stopS = np.floor((xPx[i] - predBuf * tick) / tick) * tick
            aL = armL[i] == 1; aS = armS[i] == 1
            wantL = vl and aL and fast[i] < slow[i] and canL and vp and pos <= 0 and (pos == 0 or oppMode == 0) and fb
            wantS = vl and aS and fast[i] > slow[i] and canS and vp and pos >= 0 and (pos == 0 or oppMode == 0) and fs
            if wantL: pendL = True; pendLpx = stopL; pendKind = 1
            else: pendL = False
            if wantS: pendS = True; pendSpx = stopS; pendKind = 1
            else: pendS = False
            if catchUp and not enteredThisBar:
                chaseL = maxChase <= 0 or (not prevValid) or c[i] - prevStopL <= maxChase * tick
                chaseS = maxChase <= 0 or (not prevValid) or prevStopS - c[i] <= maxChase * tick
                if crossUp[i] == 1 and aL and canL and chaseL and (pos == 0 or (pos < 0 and oppMode == 0)) and fb:
                    qEntrySide = 1; qEntryKind = 1
                elif crossDn[i] == 1 and aS and canS and chaseS and (pos == 0 or (pos > 0 and oppMode == 0)) and fs:
                    qEntrySide = -1; qEntryKind = 1
            if oppMode == 1:
                if pos < 0 and aL and crossUp[i] == 1: qClose = True; qCloseReason = 4
                if pos > 0 and aS and crossDn[i] == 1: qClose = True; qCloseReason = 4
            prevValid = vp; prevStopL = stopL; prevStopS = stopS
        if pos != 0:
            held = i - entryI
            if failExit and (predict or atCross) and validFast[i] == 1 and validSlow[i] == 1 and held <= turnHold:
                if pos > 0 and fast[i] <= slow[i]: qClose = True; qCloseReason = 6
                if pos < 0 and fast[i] >= slow[i]: qClose = True; qCloseReason = 6
            if timeStop > 0 and held >= timeStop: qClose = True; qCloseReason = 7
        if closedCount > lossRevSeen:
            lossRevSeen = closedCount
            wasRev = lastKind == 3 or lastKind == 4
            movePts = abs(lastExitPx - lastEntryPx) / tick
            tiny = lossRevTiny and lastPnl >= 0 and movePts <= lossRevTinyPts
            loss = lastPnl < 0 or tiny
            if (not loss) or (not wasRev): lossRevChain = 0
            counts = lossRevWhat == 0 or lastReason == 1 or lastReason == 3
            chain = lossRevMax <= 0 or lossRevChain < lossRevMax
            flat = pos == 0 and not hasMarketSig
            if lossRevOn and loss and counts and chain and flat and qEntrySide == 0:
                side = 0
                if lastSide > 0 and canS and fs: side = -1
                elif lastSide < 0 and canL and fb: side = 1
                if side != 0:
                    qEntrySide = side; qEntryKind = 4 if tiny else 3
                    lossRevChain += 1
    if pos != 0:
        half = _half_spread(c[n - 1], spreadPts, spreadPct, tick)
        ex = c[n - 1] - half if pos > 0 else c[n - 1] + half
        pnl = (ex - entryPx) * pos - (commPts * tick + commPct * c[n - 1])
        if nt < maxTrades:
            tEntryI[nt] = entryI; tExitI[nt] = n - 1; tSide[nt] = pos; tEntryPx[nt] = entryPx; tExitPx[nt] = ex
            tPnl[nt] = pnl; tReason[nt] = 8; tKind[nt] = posKind; nt += 1
        realized += pnl
        equity[n - 1] = realized
    return nt, tEntryI[:nt], tExitI[:nt], tSide[:nt], tEntryPx[:nt], tExitPx[:nt], tPnl[:nt], tReason[:nt], tKind[:nt], equity
