#!/usr/bin/env python3
"""
shapemap_ref.py - pure-Python transliteration of "XPW Shape Map v0.5" (Pine v6), function by function,
same execution order within a bar, same na rules. Reference for Gates A/B/C. Never generated from the MQL5.

na rules (see XPW_SHAPEMAP_V0.5_PORT_REPORT.md):
  NA1  na in a comparison -> False            NA2  na in arithmetic -> na
  NA3  ta.rsi na for bars 0..len-1             NA4  ta.sma na while its window holds na
  NA5  ta.highest/lowest na while the window (INCLUDING the current bar) holds na (ASSUMED, Gate B)
  NA6  ta.atr = RMA(TR), SMA-seeded, TR(bar 0) = high-low
  NA7  math.max/min with na -> na (ASSUMED; toggle NA_MAX_PROPAGATES; unreachable with the default gates)
  NA8  history reference before bar 0 (x[k], k > bar_index) -> na -> comparisons False
  NA9  ternary with na condition -> else branch (posW = 0.5 while rngW is na)
  NA10 bools never na: isRed False while fast/slow na, so isLime is True during warm-up
  NA11 ta.crossover(a,b) = a > b and a[1] <= b[1]; ta.crossunder = a < b and a[1] >= b[1]; na -> False
"""

NA = None
NA_MAX_PROPAGATES = True


def na(x):
    return x is None


def sub(a, b):
    return NA if na(a) or na(b) else a - b


def div(a, b):
    return NA if na(a) or na(b) else a / b


def gt(a, b):
    return False if na(a) or na(b) else a > b


def ge(a, b):
    return False if na(a) or na(b) else a >= b


def lt(a, b):
    return False if na(a) or na(b) else a < b


def le(a, b):
    return False if na(a) or na(b) else a <= b


def pmax(a, b):
    if na(a) or na(b):
        return NA if NA_MAX_PROPAGATES else (b if na(a) else a)
    return a if a >= b else b


def pmin(a, b):
    if na(a) or na(b):
        return NA if NA_MAX_PROPAGATES else (b if na(a) else a)
    return a if a <= b else b


class Sma:
    def __init__(self, length):
        self.length = length
        self.win = []

    def update(self, x):
        self.win.append(x)
        if len(self.win) > self.length:
            self.win.pop(0)
        if len(self.win) < self.length or any(na(v) for v in self.win):
            return NA
        return sum(self.win) / self.length


class Rma:
    def __init__(self, length):
        self.length = length
        self.sma = Sma(length)
        self.value = NA

    def update(self, x):
        if na(self.value):
            self.value = self.sma.update(x)
        else:
            self.value = (x + (self.length - 1) * self.value) / self.length if not na(x) else NA
        return self.value


class Rsi:
    def __init__(self, length):
        self.up = Rma(length)
        self.dn = Rma(length)
        self.prev = NA

    def update(self, src):
        chg = sub(src, self.prev)
        self.prev = src
        u = NA if na(chg) else max(chg, 0.0)
        d = NA if na(chg) else max(-chg, 0.0)
        au = self.up.update(u)
        ad = self.dn.update(d)
        if na(au) or na(ad):
            return NA
        if ad == 0.0:
            return 100.0
        if au == 0.0:
            return 0.0
        return 100.0 - 100.0 / (1.0 + au / ad)


class Atr:
    def __init__(self, length):
        self.rma = Rma(length)
        self.prev_close = NA

    def update(self, h, l, c):
        tr = (h - l) if na(self.prev_close) else max(h - l, abs(h - self.prev_close), abs(l - self.prev_close))
        self.prev_close = c
        return self.rma.update(tr)


class Extreme:
    def __init__(self, length):
        self.length = length
        self.win = []

    def update(self, x):
        self.win.append(x)
        if len(self.win) > self.length:
            self.win.pop(0)
        if len(self.win) < self.length or any(na(v) for v in self.win):
            return NA, NA
        return max(self.win), min(self.win)


DEFAULTS = dict(
    rsiLen=14, fastLen=2, slowLen=7, invertFill=True,
    areaLook=20, loFrac=0.20, hiFrac=0.67,
    botOn=True, botMinW=1, botMaxW=3, botCtx=2, botNeedLow=True, botSep=5,
    topOn=True, topMinW=1, topMaxW=2, topCtx=3, topNeedHigh=True, topSep=5,
    turnOn=True, turnMax=12, turnHold=2,
    tickOn=True, atrLen=14, botWickRange=0.55, botWickAtr=0.8, topWickRange=0.70, topWickAtr=1.20,
    showTable=True,
)
LIMITS = dict(
    rsiLen=(2, None), fastLen=(1, None), slowLen=(1, None), areaLook=(5, None), loFrac=(0.0, 1.0), hiFrac=(0.0, 1.0),
    botMinW=(1, None), botMaxW=(1, None), botCtx=(1, None), botSep=(0, None),
    topMinW=(1, None), topMaxW=(1, None), topCtx=(1, None), topSep=(0, None),
    turnMax=(1, None), turnHold=(1, None), atrLen=(2, None),
)
OUTPUT_COLUMNS = [
    "rsi", "fast", "slow", "atr", "isRed", "posW", "inLow", "inHigh",
    "botRaw", "botWid", "topRaw", "topWid", "botSq", "botSqTop", "botSqBot", "topSq", "topSqTop", "topSqBot",
    "botArmed", "topArmed", "botTurn", "botGap", "topTurn", "topGap", "botTick", "topTick",
    "legDir", "legDist", "legBars", "legEff", "nBotSq", "nTopSq", "nBotTurn", "nTopTurn", "nBotTk", "nTopTk",
]


def clamp_params(p):
    q = dict(DEFAULTS)
    q.update(p or {})
    for k, (lo, hi) in LIMITS.items():
        if lo is not None and q[k] < lo:
            q[k] = lo
        if hi is not None and q[k] > hi:
            q[k] = hi
    return q


def fmt2(x):      # "#.##"
    if na(x):
        return "NaN"
    s = "%.2f" % x
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return "0" if s == "-0" else s


def fmt00(x):     # "#.00"
    return "NaN" if na(x) else "%.2f" % x


class ShapeMap:
    def __init__(self, params=None):
        p = clamp_params(params)
        self.p = p
        self.rsi = Rsi(p["rsiLen"])
        self.fastS = Sma(p["fastLen"])
        self.slowS = Sma(p["slowLen"])
        self.ext = Extreme(p["areaLook"])
        self.atr = Atr(p["atrLen"])
        self.bar_index = -1
        self.prev_close = NA
        # per-bar history (index = bar_index) of the series the Pine references with [k]
        self.h_isRed, self.h_fast, self.h_slow, self.h_inLow, self.h_inHigh = [], [], [], [], []
        # ---- var state ----
        self.lastBotBar = -10000
        self.lastTopBar = -10000
        self.lastBotWedge = -10000
        self.lastTopWedge = -10000
        self.nBotSq = 0
        self.nTopSq = 0
        self.botArmed = False
        self.botArmBar = 0
        self.topArmed = False
        self.topArmBar = 0
        self.nBotTurn = 0
        self.nTopTurn = 0
        self.lastBotGap = 0
        self.lastTopGap = 0
        self.nBotTk = 0
        self.nTopTk = 0
        self.legOpen = False
        self.legDir = 0
        self.legP0 = NA
        self.legB0 = 0
        self.legPath = 0.0
        self.leg1 = "—"
        self.leg2 = "—"
        self.boxes = []
        self.labels = []
        self.last = None

    # x[k] with NA8
    def hist(self, arr, k):
        i = self.bar_index - k
        return arr[i] if i >= 0 else NA

    def isRedAt(self, k):
        v = self.hist(self.h_isRed, k)
        return False if na(v) else v

    def isLimeAt(self, k):
        v = self.hist(self.h_isRed, k)
        return False if na(v) else (not v)

    def detect(self, wantRedWedge, minW, maxW, ctx):
        wHi = max(minW, maxW)
        fired = False
        wOut = 0
        for w in range(minW, wHi + 1):
            if not fired:
                ok = True
                for i in range(0, ctx):
                    v = self.isLimeAt(i) if wantRedWedge else self.isRedAt(i)
                    if not v:
                        ok = False
                if ok:
                    for i in range(0, w):
                        v = self.isRedAt(ctx + i) if wantRedWedge else self.isLimeAt(ctx + i)
                        if not v:
                            ok = False
                if ok:
                    for i in range(0, ctx):
                        v = self.isLimeAt(ctx + w + i) if wantRedWedge else self.isRedAt(ctx + w + i)
                        if not v:
                            ok = False
                if ok:
                    fired = True
                    wOut = w
        return fired, wOut

    def process(self, o, h, l, c):
        p = self.p
        self.bar_index += 1
        bi = self.bar_index
        # ---- TDI ----
        r = self.rsi.update(c)
        fast = self.fastS.update(r)
        slow = self.slowS.update(r)
        isRed = gt(fast, slow) if p["invertFill"] else lt(fast, slow)
        # ---- AREAS ----
        hiW, loW = self.ext.update(slow)
        rngW = sub(hiW, loW)
        posW = div(sub(slow, loW), rngW) if gt(rngW, 0.0) else 0.5
        inLow = le(posW, p["loFrac"])
        inHigh = ge(posW, p["hiFrac"])
        self.h_isRed.append(isRed)
        self.h_fast.append(fast)
        self.h_slow.append(slow)
        self.h_inLow.append(inLow)
        self.h_inHigh.append(inHigh)
        # ---- WEDGES ----
        botRaw, botWid = self.detect(True, p["botMinW"], p["botMaxW"], p["botCtx"])
        topRaw, topWid = self.detect(False, p["topMinW"], p["topMaxW"], p["topCtx"])
        inLowAt = self.hist(self.h_inLow, p["botCtx"])
        inHighAt = self.hist(self.h_inHigh, p["topCtx"])
        botOK = (p["botOn"] and botRaw and ((not p["botNeedLow"]) or (inLowAt is True)) and (bi - self.lastBotBar >= p["botSep"]))
        topOK = (p["topOn"] and topRaw and ((not p["topNeedHigh"]) or (inHighAt is True)) and (bi - self.lastTopBar >= p["topSep"]))
        botSqTop = botSqBot = topSqTop = topSqBot = NA
        if botOK:
            self.lastBotBar = bi
            self.lastBotWedge = bi - p["botCtx"]
            self.nBotSq += 1
            lft = bi - p["botCtx"] - botWid + 1
            rgt = bi - p["botCtx"]
            hh, ll = -1e10, 1e10
            for i in range(0, botWid):
                hh = pmax(hh, pmax(self.hist(self.h_fast, p["botCtx"] + i), self.hist(self.h_slow, p["botCtx"] + i)))
                ll = pmin(ll, pmin(self.hist(self.h_fast, p["botCtx"] + i), self.hist(self.h_slow, p["botCtx"] + i)))
            botSqTop, botSqBot = hh, ll
            self.boxes.append(dict(left=lft, right=rgt, top=sub(hh, -1.5), bottom=sub(ll, 1.5), isRed=True, at=bi))
            self.labels.append((rgt, sub(ll, 2.0), "BOT " + str(botWid), "sq"))
        if topOK:
            self.lastTopBar = bi
            self.lastTopWedge = bi - p["topCtx"]
            self.nTopSq += 1
            lft = bi - p["topCtx"] - topWid + 1
            rgt = bi - p["topCtx"]
            hh, ll = -1e10, 1e10
            for i in range(0, topWid):
                hh = pmax(hh, pmax(self.hist(self.h_fast, p["topCtx"] + i), self.hist(self.h_slow, p["topCtx"] + i)))
                ll = pmin(ll, pmin(self.hist(self.h_fast, p["topCtx"] + i), self.hist(self.h_slow, p["topCtx"] + i)))
            topSqTop, topSqBot = hh, ll
            self.boxes.append(dict(left=lft, right=rgt, top=sub(hh, -1.5), bottom=sub(ll, 1.5), isRed=False, at=bi))
            self.labels.append((rgt, sub(hh, -2.0), "TOP " + str(topWid), "sq"))
        # ---- TURN MARK ----
        if botOK:
            self.botArmed = True
            self.botArmBar = bi
        if topOK:
            self.topArmed = True
            self.topArmBar = bi
        if self.botArmed and bi - self.botArmBar > p["turnMax"]:
            self.botArmed = False
        if self.topArmed and bi - self.topArmBar > p["turnMax"]:
            self.topArmed = False
        holdUp = True
        holdDn = True
        for i in range(0, p["turnHold"] + 1):
            if not gt(self.hist(self.h_fast, i), self.hist(self.h_slow, i)):
                holdUp = False
            if not lt(self.hist(self.h_fast, i), self.hist(self.h_slow, i)):
                holdDn = False
        th = p["turnHold"]
        crossedUpAt = gt(self.hist(self.h_fast, th), self.hist(self.h_slow, th)) and le(self.hist(self.h_fast, th + 1), self.hist(self.h_slow, th + 1))
        crossedDnAt = lt(self.hist(self.h_fast, th), self.hist(self.h_slow, th)) and ge(self.hist(self.h_fast, th + 1), self.hist(self.h_slow, th + 1))
        botTurn = p["turnOn"] and self.botArmed and crossedUpAt and holdUp
        topTurn = p["turnOn"] and self.topArmed and crossedDnAt and holdDn
        botGap = topGap = NA
        if botTurn:
            self.botArmed = False
            self.nBotTurn += 1
            tb = bi - th
            self.lastBotGap = tb - self.lastBotWedge
            botGap = self.lastBotGap
            self.labels.append((tb, sub(pmin(self.hist(self.h_fast, th), self.hist(self.h_slow, th)), 3.0), "▲", "turn"))
        if topTurn:
            self.topArmed = False
            self.nTopTurn += 1
            tb = bi - th
            self.lastTopGap = tb - self.lastTopWedge
            topGap = self.lastTopGap
            self.labels.append((tb, sub(pmax(self.hist(self.h_fast, th), self.hist(self.h_slow, th)), -3.0), "▼", "turn"))
        # ---- TICKS ----
        atrV = self.atr.update(h, l, c)
        rngBar = h - l
        upWick = h - max(o, c)
        dnWick = min(o, c) - l
        botTick = p["tickOn"] and rngBar > 0 and gt(atrV, 0.0) and dnWick / rngBar >= p["botWickRange"] and ge(div(dnWick, atrV), p["botWickAtr"])
        topTick = p["tickOn"] and rngBar > 0 and gt(atrV, 0.0) and upWick / rngBar >= p["topWickRange"] and ge(div(upWick, atrV), p["topWickAtr"])
        botTickV = topTickV = NA
        if botTick:
            self.nBotTk += 1
            botTickV = dnWick / atrV
            self.labels.append((bi, l, "BOT", "tick"))
        if topTick:
            self.nTopTk += 1
            topTickV = upWick / atrV
            self.labels.append((bi, h, "TOP", "tick"))
        # ---- LEGS ----
        if self.legOpen:
            self.legPath += abs(c - self.prev_close)
        legDir = 0
        legDist = legBars = legEff = NA
        if botTurn or topTurn:
            if self.legOpen:
                dist = abs(c - self.legP0)
                bars = bi - self.legB0
                eff = dist / self.legPath if self.legPath > 0 else 0.0
                self.leg2 = self.leg1
                self.leg1 = ("UP " if self.legDir > 0 else "DN ") + fmt2(dist) + " / " + str(bars) + "b / eff " + fmt00(eff)
                legDir, legDist, legBars, legEff = self.legDir, dist, bars, eff
            self.legOpen = True
            self.legDir = 1 if botTurn else -1
            self.legP0 = c
            self.legB0 = bi
            self.legPath = 0.0
        self.prev_close = c
        out = dict(
            bar_index=bi, rsi=r, fast=fast, slow=slow, atr=atrV, isRed=1 if isRed else 0, posW=posW,
            inLow=1 if inLow else 0, inHigh=1 if inHigh else 0,
            botRaw=1 if botRaw else 0, botWid=botWid, topRaw=1 if topRaw else 0, topWid=topWid,
            botSq=botWid if botOK else 0, botSqTop=botSqTop, botSqBot=botSqBot,
            topSq=topWid if topOK else 0, topSqTop=topSqTop, topSqBot=topSqBot,
            botArmed=1 if self.botArmed else 0, topArmed=1 if self.topArmed else 0,
            botTurn=1 if botTurn else 0, botGap=botGap, topTurn=1 if topTurn else 0, topGap=topGap,
            botTick=botTickV, topTick=topTickV,
            legDir=legDir, legDist=legDist, legBars=legBars, legEff=legEff,
            nBotSq=self.nBotSq, nTopSq=self.nTopSq, nBotTurn=self.nBotTurn, nTopTurn=self.nTopTurn, nBotTk=self.nBotTk, nTopTk=self.nTopTk,
            botOK=botOK, topOK=topOK, inLowAt=inLowAt, inHighAt=inHighAt, holdUp=holdUp, holdDn=holdDn,
            crossedUpAt=crossedUpAt, crossedDnAt=crossedDnAt, leg1=self.leg1, leg2=self.leg2,
        )
        self.last = out
        return out

    def table(self):
        o = self.last
        if o is None:
            return []
        area = " LOW" if o["inLow"] else (" HIGH" if o["inHigh"] else " MID")
        return [
            ("XPW Shape Map v0.5", "RED" if o["isRed"] else "LIME"),
            ("Area pos", fmt00(o["posW"]) + area),
            ("BOT squares", str(self.nBotSq)),
            ("TOP squares", str(self.nTopSq)),
            ("BOT turns", str(self.nBotTurn) + "  gap " + str(self.lastBotGap) + "b"),
            ("TOP turns", str(self.nTopTurn) + "  gap " + str(self.lastTopGap) + "b"),
            ("BOT ticks", str(self.nBotTk)),
            ("TOP ticks", str(self.nTopTk)),
            ("Leg -1", self.leg1),
            ("Leg -2", self.leg2),
        ]


def run(bars, params=None):
    sm = ShapeMap(params)
    return [sm.process(o, h, l, c) for (o, h, l, c) in bars], sm


if __name__ == "__main__":
    import sys, csv
    if len(sys.argv) < 2:
        print("usage: shapemap_ref.py <ohlc.csv> [key=value ...]")
        sys.exit(1)
    params = {}
    for kv in sys.argv[2:]:
        k, v = kv.split("=", 1)
        params[k] = (v.lower() == "true") if v.lower() in ("true", "false") else (float(v) if "." in v else int(v))
    rows = []
    with open(sys.argv[1], newline="") as fh:
        for rr in csv.DictReader(fh):
            rows.append((float(rr["open"]), float(rr["high"]), float(rr["low"]), float(rr["close"])))
    outs, sm = run(rows, params)
    w = csv.writer(sys.stdout)
    w.writerow(["bar_index"] + OUTPUT_COLUMNS)
    for o in outs:
        w.writerow([o["bar_index"]] + ["na" if na(o[k]) else o[k] for k in OUTPUT_COLUMNS])
    for row in sm.table():
        print(row, file=sys.stderr)
