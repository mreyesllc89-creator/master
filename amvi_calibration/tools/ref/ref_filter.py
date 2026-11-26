"""Third reference: a literal copy of the FlashGold direction filter (written by an independent
reviewer during the code review, kept unchanged apart from this note). Used by
replicate_picks.py to check the filter zone of every pick, including the two filter modes the
other reference versions do not implement (Candles permission, Level at candle open).

Slow, literal, loop-based re-computation of the FlashGold direction filter of
AMVI_FGF_Inverted_XAUUSD_15m.pine (lines 252-845) and of amviDirUp / amviDirDn (932-933).

One execution per bar, None = na, every Pine statement translated one to one (the Pine line
numbers are in the comments). Nothing is imported from the calibration tools.

request.security on historical bars (the semantics given to the reviewers):
  requested ABOVE the context, lookahead_on  -> the requested bar that contains the context bar's open
                                                (the expression's own [1] then gives the last closed one)
  requested ABOVE the context, lookahead_off -> the last requested bar whose close <= the context bar's close
  requested EQUAL                            -> the context's own bar
  requested BELOW, lookahead_off             -> the last requested bar inside the context bar
"""
import math

MS = 60000
MINTICK = 0.1


# ----------------------------------------------------------------------------------------
# na-aware comparisons (Pine v6: a comparison with na is false)
# ----------------------------------------------------------------------------------------
def gt(a, b):
    return a is not None and b is not None and a > b


def lt(a, b):
    return a is not None and b is not None and a < b


def ge(a, b):
    return a is not None and b is not None and a >= b


def le(a, b):
    return a is not None and b is not None and a <= b


def eq(a, b):
    return a is not None and b is not None and a == b


def nz(a, b=0):
    return b if a is None else a


def add(a, b):
    return None if a is None or b is None else a + b


def sub(a, b):
    return None if a is None or b is None else a - b


def mul(a, b):
    return None if a is None or b is None else a * b


def div(a, b):
    return None if a is None or b is None else a / b


# ----------------------------------------------------------------------------------------
# bars
# ----------------------------------------------------------------------------------------
class Bars:
    def __init__(self, tf):
        self.tf = tf
        self.t, self.o, self.h, self.l, self.c = [], [], [], [], []

    def __len__(self):
        return len(self.t)


def build(m1, tf):
    """Bars of tf minutes from 1m bars: a bar opens at every multiple of tf minutes."""
    out = Bars(tf)
    key = None
    for i in range(len(m1.t)):
        k = m1.t[i] // (tf * MS)
        if k != key:
            key = k
            out.t.append(k * tf * MS)
            out.o.append(m1.o[i])
            out.h.append(m1.h[i])
            out.l.append(m1.l[i])
            out.c.append(m1.c[i])
        else:
            if m1.h[i] > out.h[-1]:
                out.h[-1] = m1.h[i]
            if m1.l[i] < out.l[-1]:
                out.l[-1] = m1.l[i]
            out.c[-1] = m1.c[i]
    return out


# ----------------------------------------------------------------------------------------
# Pine built-ins, reference listings
# ----------------------------------------------------------------------------------------
def p_sma(x, n):
    # pine_sma: sum = 0.0; for i = 0 to n - 1: sum := sum + x[i] / n
    out = [None] * len(x)
    for i in range(len(x)):
        if i - (n - 1) < 0:
            continue
        s = 0.0
        for k in range(n):
            v = x[i - k]
            if v is None:
                s = None
                break
            s = s + v / n
        out[i] = s
    return out


def p_rma(src, n):
    # pine_rma: sum := na(sum[1]) ? ta.sma(src, n) : alpha * src + (1 - alpha) * nz(sum[1])
    alpha = 1 / n
    sma = p_sma(src, n)
    out = [None] * len(src)
    prev = None
    for i in range(len(src)):
        if prev is None:
            cur = sma[i]
        else:
            cur = None if src[i] is None else alpha * src[i] + (1 - alpha) * prev
        out[i] = cur
        prev = cur
    return out


def p_rsi(x, n):
    # pine_rsi: u = max(x - x[1], 0); d = max(x[1] - x, 0); rs = rma(u) / rma(d); 100 - 100 / (1 + rs)
    u = [None] * len(x)
    d = [None] * len(x)
    for i in range(1, len(x)):
        u[i] = max(x[i] - x[i - 1], 0.0)
        d[i] = max(x[i - 1] - x[i], 0.0)
    ru = p_rma(u, n)
    rd = p_rma(d, n)
    out = [None] * len(x)
    for i in range(len(x)):
        a, b = ru[i], rd[i]
        if a is None or b is None:
            continue
        if b == 0.0:
            out[i] = 100.0 if a > 0.0 else None      # x / 0 = inf -> 100; 0 / 0 = na
        else:
            out[i] = 100.0 - 100.0 / (1.0 + a / b)
    return out


def p_atr(b, n):
    tr = [None] * len(b)
    for i in range(len(b)):
        if i == 0:
            tr[i] = b.h[i] - b.l[i]
        else:
            tr[i] = max(b.h[i] - b.l[i], abs(b.h[i] - b.c[i - 1]), abs(b.l[i] - b.c[i - 1]))
    return p_rma(tr, n)


def tdi_dir(close, rsi_len, fast_len):
    """fgfTdiDir (337-340), plus the fast line itself (to recognise exact ties)."""
    r = p_rsi(close, rsi_len)
    f = p_sma(r, fast_len)
    d = [0] * len(f)
    for i in range(len(f)):
        f1 = f[i - 1] if i > 0 else None
        d[i] = 1 if gt(f[i], f1) else -1 if lt(f[i], f1) else 0
    return d, f


# ----------------------------------------------------------------------------------------
# request.security merges (pointer loops)
# ----------------------------------------------------------------------------------------
def map_contains_open(req_t, ctx_t):
    """ABOVE, lookahead_on: the requested bar that contains the context bar's open."""
    out, j = [], -1
    for t in ctx_t:
        while j + 1 < len(req_t) and req_t[j + 1] <= t:
            j += 1
        out.append(j if j >= 0 else None)
    return out


def map_closed_by_close(req_t, R, ctx_t, C):
    """ABOVE, lookahead_off: the last requested bar whose close <= the context bar's close."""
    out, j = [], -1
    for t in ctx_t:
        while j + 1 < len(req_t) and req_t[j + 1] + R * MS <= t + C * MS:
            j += 1
        out.append(j if j >= 0 else None)
    return out


def map_last_inside(req_t, ctx_t, C):
    """BELOW, lookahead_off: the last requested bar inside the context bar."""
    out, j = [], -1
    for t in ctx_t:
        while j + 1 < len(req_t) and req_t[j + 1] < t + C * MS:
            j += 1
        assert j >= 0 and req_t[j] >= t, "a context bar without an intrabar"
        out.append(j)
    return out


def map_equal(req_t, ctx_t):
    assert req_t == ctx_t
    return list(range(len(ctx_t)))


# ----------------------------------------------------------------------------------------
# the filter
# ----------------------------------------------------------------------------------------
INPUT_DEFAULTS = dict(
    fgfOn=True, fgfLast="Until next signal", fgfMinutes=60, fgfBars=1, fgfCheckIn="Tick",
    fgfSpreadPts=25.0, fgfEntryDistPts=50.0, fgfHoldBars=0, fgfHoldFavPts=5.0, fgfOnePerBar=True,
    fgfDistUnit="ATR", fgfHoldFavAtr=0.1, fgfBurstPts=172.0,
    fgfFlatParent=False, fgfIgnoreNa=True, fgfHtfClosed=True,
)


class Cache:
    """Bars / TDI / ATR per timeframe, shared between parameter sets."""

    def __init__(self, m1):
        self.m1 = m1
        self._bars, self._tdi, self._atr, self.tdi_override = {}, {}, {}, None

    def bars(self, tf):
        if tf not in self._bars:
            self._bars[tf] = build(self.m1, tf)
        return self._bars[tf]

    def tdi(self, tf, rsi_len, fast_len):
        k = (tf, rsi_len, fast_len)
        if k not in self._tdi:
            if self.tdi_override is not None:
                self._tdi[k] = ([int(v) for v in self.tdi_override(tf, rsi_len, fast_len)], None)
            else:
                self._tdi[k] = tdi_dir(self.bars(tf).c, rsi_len, fast_len)
        return self._tdi[k]

    def atr14(self, tf):
        if tf not in self._atr:
            self._atr[tf] = p_atr(self.bars(tf), 14)
        return self._atr[tf]


def filter_context(cache, I):
    """fgfRead() (546-551) on every candle of the filter timeframe. I = Pine inputs (dict)."""
    F = I["fgfTf"]
    fb = cache.bars(F)
    n = len(fb)
    ctxSec = F * 60                                   # fgfTfSec (324), passed as ctxSec (547)

    def fgfZoneDir(tf):                               # 348-351
        zb = cache.bars(tf)
        d, _ = cache.tdi(tf, I["fgfRsiLen"], I["fgfFastLen"])
        dprev = [None] + d[:-1]                       # fgfTdiDirPrev (342-344): d[1]
        use_prev = I["fgfHtfClosed"] and tf * 60 > ctxSec
        if tf > F:
            m = map_contains_open(zb.t, fb.t) if use_prev else map_closed_by_close(zb.t, tf, fb.t, F)
        elif tf == F:
            assert not use_prev
            m = map_equal(zb.t, fb.t)
        else:
            assert not use_prev
            m = map_last_inside(zb.t, fb.t, F)
        src = dprev if use_prev else d
        return [None if j is None else src[j] for j in m]

    parentDirS = fgfZoneDir(I["fgfParentTf"])         # 372
    zoneDirS = [fgfZoneDir(tf) if use else None for use, tf in I["zones6"]]      # 373-378 (an unused zone is requested too but never read)
    atr = cache.atr14(F)                              # ta.atr(14) (399, 548)

    pt = MINTICK                                      # 363
    halfSpread = I["fgfSpreadPts"] * pt * 0.5         # 364
    mid_hist = []
    # var state of fgfSignal (420-424) and fgfArm (484-489)
    holdActive, holdIsBuy, holdSignalBar, holdSignalMid, lastEntryBar = False, False, None, None, None
    aAt, aBar, aPx, aDir, aId, aAtr = None, None, None, 0, 0, None
    rec = []
    for k in range(n):
        bar_index, time_, close = k, fb.t[k], fb.c[k]
        time_close = time_ + F * MS
        bidPx = close - halfSpread                    # 365
        askPx = close + halfSpread                    # 366
        midPrice = (bidPx + askPx) * 0.5              # 367
        mid_hist.append(midPrice)

        parentDir = parentDirS[k]
        zdir = [None if s is None else s[k] for s in zoneDirS]
        on = [use and (not I["fgfIgnoreNa"] or zdir[q] is not None) for q, (use, _tf) in enumerate(I["zones6"])]   # 353-354, 380-385
        activeZones = sum(1 if o else 0 for o in on)                                                              # 387
        parentSide = 1 if gt(parentDir, 0) else -1 if lt(parentDir, 0) else 0                                     # 388
        alignedZones = sum(1 if (on[q] and parentSide != 0 and eq(zdir[q], parentSide)) else 0 for q in range(6))  # 356-357, 389
        requiredAligned = min(I["fgfMinAligned"], activeZones)                                                    # 391
        parentFlatAllowed = I["fgfFlatParent"] and parentSide == 0                                                # 392
        zoneReady = activeZones == 0 or alignedZones >= requiredAligned                                           # 393
        tradeZoneBuyAllowed = (not I["fgfUseZones"]) or ((parentSide == 1 or parentFlatAllowed) and zoneReady)    # 395
        tradeZoneSellAllowed = (not I["fgfUseZones"]) or ((parentSide == -1 or parentFlatAllowed) and zoneReady)  # 396

        atrPts = div(atr[k], pt)                                                                    # 399
        burstThrPts = mul(I["fgfBurstAtr"], atrPts) if I["fgfDistUnit"] == "ATR" else I["fgfBurstPts"]          # 400
        entryDistPts = mul(I["fgfEntryDistAtr"], atrPts) if I["fgfDistUnit"] == "ATR" else I["fgfEntryDistPts"]  # 401
        mid1 = mid_hist[k - 1] if k >= 1 else None
        midD = mid_hist[k - I["fgfDriftBars"]] if k >= I["fgfDriftBars"] else None
        burstPts = div(sub(midPrice, mid1), pt)                                                     # 404
        priorDriftPts = div(sub(midPrice, midD), pt)                                                # 405
        burstBuy = ge(burstPts, burstThrPts)                                                        # 407
        burstSell = le(burstPts, None if burstThrPts is None else -burstThrPts)                     # 408
        priorBuyOk = (not I["fgfUseDrift"]) or gt(priorDriftPts, 0)                                 # 410
        priorSellOk = (not I["fgfUseDrift"]) or lt(priorDriftPts, 0)                                # 411
        if I["fgfAnyCombo"]:                                                                        # 413-414
            rawBuyCandidate = tradeZoneBuyAllowed and ((not I["fgfUseBurst"]) or burstBuy or parentSide == 1)
            rawSellCandidate = tradeZoneSellAllowed and ((not I["fgfUseBurst"]) or burstSell or parentSide == -1)
        else:
            rawBuyCandidate = tradeZoneBuyAllowed and burstBuy
            rawSellCandidate = tradeZoneSellAllowed and burstSell
        buyCandidate = rawBuyCandidate and priorBuyOk                                               # 416
        sellCandidate = rawSellCandidate and priorSellOk                                            # 417

        buyEntryPrice = sellEntryPrice = None                                                       # 426-429
        buySignal = sellSignal = False
        canFire = (not I["fgfOnePerBar"]) or lastEntryBar is None or lastEntryBar != bar_index      # 431
        assert I["fgfHoldBars"] == 0
        if buyCandidate and canFire:                                                                # 433-437
            buyEntryPrice = add(askPx, mul(entryDistPts, pt))
            buySignal = True
            lastEntryBar = bar_index
        if sellCandidate and canFire:                                                               # 452-456
            sellEntryPrice = sub(bidPx, mul(entryDistPts, pt))
            sellSignal = True
            lastEntryBar = bar_index
        signalPx = buyEntryPrice if buySignal else sellEntryPrice if sellSignal else None           # 476

        fAtr = atr[k]                                                                               # 548
        prev = (aAt, aBar, aPx, aDir, aId, aAtr)                                                    # the [1] values of 551
        if k == 0:
            prev = (None, None, None, None, None, None)
        if buySignal or sellSignal:                                                                 # 490-496
            aAt = nz(time_close, time_)
            aBar = bar_index
            aPx = nz(signalPx, close) if I["fgfLvMode"] == "Entry price" else close
            aDir = 1 if buySignal else -1
            aId += 1
            aAtr = fAtr
        rec.append(dict(aAt=aAt, aBar=aBar, aPx=aPx, aDir=aDir, aId=aId, aAtr=aAtr, idx=bar_index, open=time_,
                        close=nz(time_close, time_), qAt=prev[0], qBar=prev[1], qPx=prev[2], qDir=prev[3], qId=prev[4],
                        qAtr=prev[5], qClose=(fb.t[k - 1] + F * MS) if k >= 1 else None,
                        buy=buySignal, sell=sellSignal, par=parentSide, al=alignedZones, ac=activeZones))
    return fb, rec


NA_REC = dict(aAt=None, aBar=None, aPx=None, aDir=None, aId=None, aAtr=None, idx=None, open=None, close=None,
              qAt=None, qBar=None, qPx=None, qDir=None, qId=None, qAtr=None, qClose=None)


def chart_zone(cache, chart_tf, I, detail=False):
    """Lines 323-330 and 553-672, then 932-933, on every chart bar. Returns the zone list
    (+1 amviDirUp, -1 amviDirDn, 0 neither) and, with detail, the per-bar intermediate values."""
    C = chart_tf
    F = I["fgfTf"]
    cb = cache.bars(C)
    fb, rec = filter_context(cache, I)
    # 553: request.security(syminfo.tickerid, fgfTfEff, fgfRead(), gaps_off, lookahead_off)
    if F > C:
        m = map_closed_by_close(fb.t, F, cb.t, C)
    elif F == C:
        m = map_equal(fb.t, cb.t)
    else:
        m = map_last_inside(fb.t, cb.t, C)

    fgfTfSec = F * 60
    fgfCheck = "Level at candle open" if (I["fgfCheckIn"] != "Candle open" and fgfTfSec <= C * 60) else I["fgfCheckIn"]   # 330
    mt = MINTICK                                                                                                        # 659
    zone = []
    rows = []
    # the previous chart bar's values of the series read with [1]
    pCAt = pCBar = pCPx = pCDir = pCId = pCAtr = pCK = pCKClose = None
    pClose = None
    for i in range(len(cb)):
        time_, close, open_ = cb.t[i], cb.c[i], cb.o[i]
        time_close = time_ + C * MS
        r = NA_REC if m[i] is None else rec[m[i]]
        fpAt, fpBar, fpPx, fpDir, fpId, fpIdx, fpClose, fpAtr = r["aAt"], r["aBar"], r["aPx"], r["aDir"], r["aId"], r["idx"], r["close"], r["aAtr"]
        fqAt, fqBar, fqPx, fqDir, fqId, fqClose, fqAtr = r["qAt"], r["qBar"], r["qPx"], r["qDir"], r["qId"], r["qClose"], r["qAtr"]

        fgfLiveBar = False                                                                           # 570: one execution per bar, at its close
        fgfAtOpen = fgfCheck == "Candle open" or fgfCheck == "Level at candle open" or (fgfCheck == "Candle close" and fgfLiveBar)   # 572
        fgfClockC = nz(time_close, time_)                                                            # 577 (confirmed bar)
        fgfClock = time_ if fgfAtOpen else fgfClockC                                                 # 578
        fgfSelC = 1 if ge(fgfClockC, fpClose) else 2                                                 # 588
        fgfSel = (1 if le(fpClose, time_) else 2 if le(fqClose, time_) else 0) if fgfAtOpen else fgfSelC   # 589
        fgfCAt = fpAt if fgfSelC == 1 else fqAt                                                      # 591
        fgfCBar = fpBar if fgfSelC == 1 else fqBar                                                   # 592
        fgfCPx = fpPx if fgfSelC == 1 else fqPx                                                      # 593
        fgfCDir = fpDir if fgfSelC == 1 else fqDir                                                   # 594
        fgfCId = fpId if fgfSelC == 1 else fqId                                                      # 595
        if fgfSelC == 1:                                                                             # 601
            fgfCIdx = fpIdx if eq(fgfClockC, fpClose) else add(fpIdx, 1)
        else:
            fgfCIdx = sub(fpIdx, 1) if eq(fgfClockC, fqClose) else fpIdx
        fgfCK = fpIdx if fgfSelC == 1 else sub(fpIdx, 1)                                             # 603
        fgfCKClose = fpClose if fgfSelC == 1 else fqClose                                            # 604

        fgfSigAt = fpAt if fgfSel == 1 else fqAt if fgfSel == 2 else pCAt                            # 606
        fgfSigBar = fpBar if fgfSel == 1 else fqBar if fgfSel == 2 else pCBar                        # 607
        fgfLevel = fpPx if fgfSel == 1 else fqPx if fgfSel == 2 else pCPx                            # 608
        fgfSigDir = nz(fpDir if fgfSel == 1 else fqDir if fgfSel == 2 else pCDir)                    # 609
        fgfCAtr = fpAtr if fgfSelC == 1 else fqAtr                                                   # 611
        fgfSigAtr = fpAtr if fgfSel == 1 else fqAtr if fgfSel == 2 else pCAtr                        # 612
        if not fgfAtOpen:                                                                            # 637
            fgfIdx = fgfCIdx
        elif fgfSel == 1:
            fgfIdx = fpIdx if eq(time_, fpClose) else add(fpIdx, 1)
        elif fgfSel == 2:
            fgfIdx = sub(fpIdx, 1) if eq(time_, fqClose) else fpIdx
        else:
            fgfIdx = pCK if eq(time_, pCKClose) else add(pCK, 1)

        if fgfCheck == "Candle open":                                                                # 640
            fgfValue = open_
        elif fgfCheck == "Candle close" and fgfLiveBar:
            fgfValue = pClose
        else:
            fgfValue = close

        fgfArmed = fgfSigAt is not None and fgfClock >= fgfSigAt                                     # 644
        fgfEnd = (fgfSigAt + I["fgfMinutes"] * 60000) if (I["fgfLast"] == "Minutes" and fgfArmed) else None      # 645
        fgfEndBar = add(fgfSigBar, I["fgfBars"]) if (I["fgfLast"] == "Candles" and fgfArmed) else None           # 646
        if I["fgfLast"] == "Minutes":                                                                # 647
            fgfOpen = fgfArmed and lt(fgfClock, fgfEnd)
        elif I["fgfLast"] == "Candles":
            fgfOpen = fgfArmed and lt(fgfIdx, fgfEndBar)
        else:
            fgfOpen = fgfArmed

        fgfOnSigBar = fgfArmed and eq(fgfIdx, fgfSigBar)                                             # 651
        fgfAtBuyLv = fgfOnSigBar and fgfSigDir > 0 and ge(fgfValue, fgfLevel)                        # 652
        fgfAtSellLv = fgfOnSigBar and fgfSigDir < 0 and le(fgfValue, fgfLevel)                       # 653

        fgfBand = I["fgfBandAtr"] * nz(fgfSigAtr)                                                    # 658
        if fgfBand > 0:                                                                              # 660-663
            fgfUpLv = None if fgfLevel is None else math.ceil((fgfLevel + fgfBand) / mt - 1e-9) * mt
            fgfDnLv = None if fgfLevel is None else math.floor((fgfLevel - fgfBand) / mt + 1e-9) * mt
            fgfInUp = gt(fgfValue, add(fgfUpLv, mt / 2))
            fgfInDn = lt(fgfValue, sub(fgfDnLv, mt / 2))
        else:
            fgfUpLv = fgfDnLv = fgfLevel
            fgfInUp = gt(fgfValue, fgfLevel) or fgfAtBuyLv
            fgfInDn = lt(fgfValue, fgfLevel) or fgfAtSellLv
        fgfUpNow = fgfInUp and (I["fgfAgainst"] or fgfSigDir > 0)                                    # 667
        fgfDnNow = fgfInDn and (I["fgfAgainst"] or fgfSigDir < 0)                                    # 668
        fgfBuyOk = (not I["fgfOn"]) or (fgfOpen and I["fgfAllowBuy"] and fgfUpNow)                   # 671
        fgfSellOk = (not I["fgfOn"]) or (fgfOpen and I["fgfAllowSell"] and fgfDnNow)                 # 672

        amviDirUp = I["fgfOn"] and fgfBuyOk and not fgfSellOk                                        # 932
        amviDirDn = I["fgfOn"] and fgfSellOk and not fgfBuyOk                                        # 933
        zone.append(1 if amviDirUp else -1 if amviDirDn else 0)
        if detail:
            rows.append(dict(i=i, time=time_, close=close, k=m[i], sel=fgfSel, selC=fgfSelC, sigAt=fgfSigAt, sigBar=fgfSigBar,
                             level=fgfLevel, sigDir=fgfSigDir, sigAtr=fgfSigAtr, idx=fgfIdx, armed=fgfArmed, open=fgfOpen,
                             onSig=fgfOnSigBar, band=fgfBand, up=fgfUpLv, dn=fgfDnLv, inUp=fgfInUp, inDn=fgfInDn,
                             buyOk=fgfBuyOk, sellOk=fgfSellOk))
        # the series read with [1] on the next bar
        pCAt, pCBar, pCPx, pCDir, pCId, pCAtr, pCK, pCKClose = fgfCAt, fgfCBar, fgfCPx, fgfCDir, fgfCId, fgfCAtr, fgfCK, fgfCKClose
        pClose = close
    return (zone, rows, rec) if detail else zone


def inputs_from_engine(p):
    """Engine parameter dict -> the Pine inputs it stands for (as make_pine.pine_inputs maps them)."""
    I = dict(INPUT_DEFAULTS)
    zones = list(p["zones"])[:6]
    template = [60, 120, 240, 480, 1, 2]
    z6 = []
    for k in range(6):
        on = k < len(zones)
        z6.append((on, zones[k] if on else template[k]))
    I.update(
        fgfTf=int(p["f_tf"]), fgfLvMode="Signal close" if p["lv_mode"] == "close" else "Entry price",
        fgfLast="Candles" if p["perm_candles"] > 0 else "Until next signal",
        fgfBars=int(p["perm_candles"]) if p["perm_candles"] > 0 else 1,
        fgfCheckIn="Level at candle open" if p["check_open"] else "Tick",
        fgfBandAtr=float(p["band"]), fgfAgainst=bool(p["against"]), fgfAllowBuy=bool(p["allow_buy"]), fgfAllowSell=bool(p["allow_sell"]),
        fgfBurstAtr=float(p["burst_atr"]), fgfEntryDistAtr=float(p["entry_dist_atr"]),
        fgfUseBurst=bool(p["use_burst"]), fgfAnyCombo=bool(p["any_combo"]),
        fgfDriftBars=int(p["drift_bars"]), fgfUseDrift=bool(p["use_drift"]),
        fgfUseZones=bool(p["use_zones"]), fgfParentTf=int(p["parent_tf"]),
        fgfRsiLen=int(p["rsi_len"]), fgfFastLen=int(p["fast_len"]), fgfMinAligned=int(p["min_aligned"]),
        fgfSpreadPts=float(p["spread_pts"]), zones6=z6,
    )
    return I
