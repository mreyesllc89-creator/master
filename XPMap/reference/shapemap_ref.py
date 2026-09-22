#!/usr/bin/env python3
"""
shapemap_ref.py - pure-Python transliteration of "XPW Shape Map v0.4" (Pine v6).

Function by function, same execution order within a bar, same na rules.
This file is the Gate A / Gate B / Gate C reference: it is never generated
from the MQL5 and the MQL5 is never generated from it.

na rules (see XPW_SHAPEMAP_PORT_REPORT.md, section "na rules"):
  NA1  na in a comparison           -> False
  NA2  na in arithmetic             -> na
  NA3  ta.rsi                       -> na until `len` price changes exist (first valid bar = len)
  NA4  ta.sma                       -> na while its window holds na
  NA5  ta.lowest / ta.highest       -> na while its window holds na (window INCLUDES the current bar)
  NA6  ta.atr                       -> RMA of TR, SMA-seeded, TR(bar 0) = high - low, first valid bar = atrLen-1
  NA7  math.max / math.min with na  -> na  (ASSUMED, toggle NA_MAX_PROPAGATES; Gate B settles it)
  NA8  math.abs(na)                 -> na
  NA9  ternary with na condition    -> condition is False -> else branch
  NA10 `not stUp`                   -> stUp is a bool (False when fast/slow na), so `not stUp` is True
  NA11 close[1] on bar 0            -> na  (stp na, mStart na, mPath na, TR uses high-low)
  NA12 var floats initialised na    -> runTop/runBot/prevTop/prevBot/lastBotSep/lastTopSep/lastUpAtr/lastDnAtr/mStart/m1Net/m1Path/m2Net/m2Path
"""

import math

NA = None
NA_MAX_PROPAGATES = True   # NA7 assumption; flip to False if Gate B shows math.max(na, x) == x


# ---------------------------------------------------------------- na helpers
def na(x):
    return x is None


def add(a, b):
    return NA if na(a) or na(b) else a + b


def sub(a, b):
    return NA if na(a) or na(b) else a - b


def mul(a, b):
    return NA if na(a) or na(b) else a * b


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
        if NA_MAX_PROPAGATES:
            return NA
        return b if na(a) else a
    return a if a >= b else b


def pmin(a, b):
    if na(a) or na(b):
        if NA_MAX_PROPAGATES:
            return NA
        return b if na(a) else a
    return a if a <= b else b


def pabs(a):
    return NA if na(a) else abs(a)


# ---------------------------------------------------------------- ta.*
class Sma:
    """ta.sma(src, len): mean of the last len values, na while the window holds na (NA4)."""

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
    """ta.rma(src, len): alpha = 1/len; sum := na(sum[1]) ? ta.sma(src, len) : alpha*src + (1-alpha)*sum[1]."""

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
    """ta.rsi(src, len) per the Pine reference:
       u = max(src - src[1], 0); d = max(src[1] - src, 0)
       rs = rma(u)/rma(d); res = down == 0 ? 100 : up == 0 ? 0 : 100 - 100/(1+rs)"""

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
        rs = au / ad
        return 100.0 - 100.0 / (1.0 + rs)


class Atr:
    """ta.atr(len) = ta.rma(ta.tr(true), len). TR(bar 0) = high - low (NA6, NA11)."""

    def __init__(self, length):
        self.rma = Rma(length)
        self.prev_close = NA

    def update(self, h, l, c):
        if na(self.prev_close):
            tr = h - l
        else:
            tr = max(h - l, abs(h - self.prev_close), abs(l - self.prev_close))
        self.prev_close = c
        return self.rma.update(tr)


class Extreme:
    """ta.lowest / ta.highest over the last n values INCLUDING the current one; na while the window holds na (NA5)."""

    def __init__(self, length):
        self.length = length
        self.win = []

    def update(self, x):
        self.win.append(x)
        if len(self.win) > self.length:
            self.win.pop(0)
        if len(self.win) < self.length or any(na(v) for v in self.win):
            return NA, NA
        return min(self.win), max(self.win)


# ---------------------------------------------------------------- inputs
DEFAULTS = dict(
    rsiLen=14, fastLen=2, slowLen=7, invertFill=True, extLook=20, loFrac=0.33, hiFrac=0.67,
    sqBotOn=True, sqBotMin=1, sqBotMax=3, sqBotCtx=2, sqBotSep=0.0, sqBotArea=True,
    sqTopOn=True, sqTopMin=1, sqTopMax=2, sqTopCtx=3, sqTopSep=0.0, sqTopArea=True,
    tickOn=True, atrLen=14, dnWickFrac=0.55, dnWickAtr=0.8, upWickFrac=0.70, upWickAtr=1.2,
    tickPrice=True, showTbl=True,
)

# minval / maxval exactly as the Pine input() calls declare them
LIMITS = dict(
    rsiLen=(2, None), fastLen=(1, None), slowLen=(1, None), extLook=(5, None),
    loFrac=(0.05, 0.5), hiFrac=(0.5, 0.95),
    sqBotMin=(1, None), sqBotMax=(1, None), sqBotCtx=(1, None), sqBotSep=(0.0, None),
    sqTopMin=(1, None), sqTopMax=(1, None), sqTopCtx=(1, None), sqTopSep=(0.0, None),
    atrLen=(1, None), dnWickFrac=(0.1, 1.0), dnWickAtr=(0.0, None), upWickFrac=(0.1, 1.0), upWickAtr=(0.0, None),
)

OUTPUT_COLUMNS = [
    "rsi", "fast", "slow", "atr", "isRedNow", "runLen", "runTop", "runBot", "runSep",
    "prevTop", "prevBot", "prevSep", "botHit", "topHit", "upTick", "dnTick",
    "mBars", "eff1", "eff2", "vel1", "vel2",
    # extras that the MQL5 R8 buffers carry
    "botSep", "botTop", "botBot", "topSep", "topTop", "topBot", "upTickAtr", "dnTickAtr",
    "botCount", "topCount", "upTickN", "dnTickN",
]


def clamp_params(p):
    """MQL5 OnInit clamps; the reference clamps the same way so both see identical inputs."""
    q = dict(DEFAULTS)
    q.update(p or {})
    for k, (lo, hi) in LIMITS.items():
        if lo is not None and q[k] < lo:
            q[k] = lo
        if hi is not None and q[k] > hi:
            q[k] = hi
    return q


# ---------------------------------------------------------------- the indicator
class ShapeMap:
    def __init__(self, params=None):
        p = clamp_params(params)
        self.p = p
        # series calculators (ta.* calls in the Pine, one instance per call site)
        self.rsi = Rsi(p["rsiLen"])
        self.fast = Sma(p["fastLen"])
        self.slow = Sma(p["slowLen"])
        self.ext = Extreme(p["extLook"])
        self.atr = Atr(p["atrLen"])
        self.bar_index = -1
        self.prev_close = NA
        # ---- var state (R5) ----
        self.runInit = False
        self.runState = False
        self.runLen = 0
        self.runStart = 0
        self.runTop = NA
        self.runBot = NA
        self.runSep = 0.0
        self.prevLen = 0
        self.prevState = False
        self.prevStart = 0
        self.prevEnd = 0
        self.prevTop = NA
        self.prevBot = NA
        self.prevSep = 0.0
        self.prev2Len = 0
        self.botCount = 0
        self.topCount = 0
        self.lastBotBar = NA
        self.lastTopBar = NA
        self.lastBotW = 0
        self.lastTopW = 0
        self.lastBotSep = NA
        self.lastTopSep = NA
        self.upTickN = 0
        self.dnTickN = 0
        self.lastUpTk = NA
        self.lastDnTk = NA
        self.lastUpAtr = NA
        self.lastDnAtr = NA
        self.mDir = 0
        self.mBars = 0
        self.mStart = NA
        self.mPath = 0.0
        self.m1Bars = 0
        self.m1Net = NA
        self.m1Path = NA
        self.m2Bars = 0
        self.m2Net = NA
        self.m2Path = NA
        # drawing records (bar indexes), for Gate A assertions
        self.squares = []   # (left, right, top, bottom, isRed, tag)
        self.labels = []    # (bar_index, y, text, kind)
        self.last = None    # last row, for the table

    # ------------------------------------------------------------ one confirmed bar
    def process(self, o, h, l, c):
        p = self.p
        self.bar_index += 1
        bi = self.bar_index
        out = {}

        # ---------------- TDI plots ----------------
        rsiv = self.rsi.update(c)
        fast = self.fast.update(rsiv)
        slow = self.slow.update(rsiv)
        stUp = gt(fast, slow)                                   # NA1
        isRedNow = stUp if p["invertFill"] else (not stUp)     # NA10
        sep = pabs(sub(fast, slow))                             # NA2/NA8

        # ---------------- Run tracker (if barstate.isconfirmed) ----------------
        curUp = stUp
        if not self.runInit:
            self.runInit = True
            self.runState = curUp
            self.runLen = 1
            self.runStart = bi
            self.runTop = pmax(fast, slow)
            self.runBot = pmin(fast, slow)
            self.runSep = sep
        elif curUp != self.runState:
            self.prev2Len = self.prevLen
            self.prevLen = self.runLen
            self.prevState = self.runState
            self.prevStart = self.runStart
            self.prevEnd = bi - 1
            self.prevTop = self.runTop
            self.prevBot = self.runBot
            self.prevSep = self.runSep
            self.runState = curUp
            self.runLen = 1
            self.runStart = bi
            self.runTop = pmax(fast, slow)
            self.runBot = pmin(fast, slow)
            self.runSep = sep
        else:
            self.runLen = self.runLen + 1
            self.runTop = pmax(self.runTop, pmax(fast, slow))
            self.runBot = pmin(self.runBot, pmin(fast, slow))
            self.runSep = pmax(self.runSep, sep)

        lo, hi = self.ext.update(slow)
        mid = div(add(self.prevTop, self.prevBot), 2.0)
        frac = div(sub(mid, lo), sub(hi, lo)) if gt(hi, lo) else 0.5   # NA9
        isLow = le(frac, p["loFrac"])
        isHigh = ge(frac, p["hiFrac"])
        wasRed = self.prevState if p["invertFill"] else (not self.prevState)

        botHit = (wasRed and self.runLen == p["sqBotCtx"] and self.prevLen >= p["sqBotMin"]
                  and self.prevLen <= p["sqBotMax"] and self.prev2Len >= p["sqBotCtx"]
                  and ((not p["sqBotArea"]) or isLow)
                  and (p["sqBotSep"] == 0.0 or ge(self.prevSep, p["sqBotSep"])))

        topHit = ((not wasRed) and self.runLen == p["sqTopCtx"] and self.prevLen >= p["sqTopMin"]
                  and self.prevLen <= p["sqTopMax"] and self.prev2Len >= p["sqTopCtx"]
                  and ((not p["sqTopArea"]) or isHigh)
                  and (p["sqTopSep"] == 0.0 or ge(self.prevSep, p["sqTopSep"])))

        refRng = sub(hi, lo)
        if botHit:
            self.botCount += 1
            self.lastBotBar = self.prevEnd
            self.lastBotW = self.prevLen
            self.lastBotSep = self.prevSep
            if p["sqBotOn"]:
                self._draw_square(self.prevStart, self.prevEnd, self.prevTop, self.prevBot, True, refRng,
                                  "BOT %d b sep %s" % (self.prevLen, fmt2(self.prevSep)), bi)
        if topHit:
            self.topCount += 1
            self.lastTopBar = self.prevEnd
            self.lastTopW = self.prevLen
            self.lastTopSep = self.prevSep
            if p["sqTopOn"]:
                self._draw_square(self.prevStart, self.prevEnd, self.prevTop, self.prevBot, False, refRng,
                                  "TOP %d b sep %s" % (self.prevLen, fmt2(self.prevSep)), bi)

        # ---------------- Ticks ----------------
        atrv = self.atr.update(h, l, c)
        rng = h - l
        upW = h - max(o, c)
        dnW = min(o, c) - l
        upTick = (p["tickOn"] and rng > 0 and upW >= p["upWickFrac"] * rng and ge(upW, mul(p["upWickAtr"], atrv)))
        dnTick = (p["tickOn"] and rng > 0 and dnW >= p["dnWickFrac"] * rng and ge(dnW, mul(p["dnWickAtr"], atrv)))
        upTickAtr = NA
        dnTickAtr = NA
        if upTick:
            self.upTickN += 1
            self.lastUpTk = bi
            self.lastUpAtr = upW / atrv
            upTickAtr = self.lastUpAtr
            self.labels.append((bi, h if p["tickPrice"] else 95, "^ %s ATR" % fmt2(self.lastUpAtr), "up"))
        if dnTick:
            self.dnTickN += 1
            self.lastDnTk = bi
            self.lastDnAtr = dnW / atrv
            dnTickAtr = self.lastDnAtr
            self.labels.append((bi, l if p["tickPrice"] else 5, "v %s ATR" % fmt2(self.lastDnAtr), "dn"))

        # ---------------- Continuity (if barstate.isconfirmed) ----------------
        stp = sub(c, self.prev_close)                          # NA11 on bar 0
        d = 1 if gt(stp, 0.0) else (-1 if lt(stp, 0.0) else self.mDir)
        if self.mDir == 0:
            self.mDir = d
            self.mBars = 1
            self.mStart = self.prev_close
            self.mPath = pabs(stp)
        elif d == self.mDir:
            self.mBars = self.mBars + 1
            self.mPath = add(self.mPath, pabs(stp))
        else:
            self.m2Bars = self.m1Bars
            self.m2Net = self.m1Net
            self.m2Path = self.m1Path
            self.m1Bars = self.mBars
            self.m1Net = sub(self.prev_close, self.mStart)
            self.m1Path = self.mPath
            self.mDir = d
            self.mBars = 1
            self.mStart = self.prev_close
            self.mPath = pabs(stp)
        self.prev_close = c

        eff1 = NA if (na(self.m1Path) or self.m1Path == 0) else abs(self.m1Net) / self.m1Path
        eff2 = NA if (na(self.m2Path) or self.m2Path == 0) else abs(self.m2Net) / self.m2Path
        vel1 = NA if (na(self.m1Net) or self.m1Bars == 0) else abs(self.m1Net) / self.m1Bars
        vel2 = NA if (na(self.m2Net) or self.m2Bars == 0) else abs(self.m2Net) / self.m2Bars

        out.update(dict(
            bar_index=bi, rsi=rsiv, fast=fast, slow=slow, atr=atrv, isRedNow=1 if isRedNow else 0,
            runLen=self.runLen, runTop=self.runTop, runBot=self.runBot, runSep=self.runSep,
            prevTop=self.prevTop, prevBot=self.prevBot, prevSep=self.prevSep,
            botHit=self.prevLen if botHit else 0, topHit=self.prevLen if topHit else 0,
            upTick=1 if upTick else 0, dnTick=1 if dnTick else 0,
            mBars=self.mBars, eff1=eff1, eff2=eff2, vel1=vel1, vel2=vel2,
            botSep=self.prevSep if botHit else NA, botTop=self.prevTop if botHit else NA, botBot=self.prevBot if botHit else NA,
            topSep=self.prevSep if topHit else NA, topTop=self.prevTop if topHit else NA, topBot=self.prevBot if topHit else NA,
            upTickAtr=upTickAtr, dnTickAtr=dnTickAtr,
            botCount=self.botCount, topCount=self.topCount, upTickN=self.upTickN, dnTickN=self.dnTickN,
            sep=sep, lo=lo, hi=hi, frac=frac, isLow=isLow, isHigh=isHigh, wasRed=wasRed,
            prevLen=self.prevLen, prev2Len=self.prev2Len, stp=stp, d=d, mDir=self.mDir,
        ))
        self.last = out
        return out

    def _draw_square(self, l, r, t, b, isRed, refRng, tag, at_bar):
        h = sub(t, b)
        padMin = pmax(mul(refRng, 0.03), 0.10)
        padv = div(sub(padMin, h), 2.0) if lt(h, padMin) else 0.0
        self.squares.append(dict(left=l, right=r, top=add(t, padv), bottom=sub(b, padv), isRed=isRed, tag=tag, at=at_bar))
        self.labels.append((r, sub(b, padv) if isRed else add(t, padv), tag, "sq"))

    # ------------------------------------------------------------ table (rows as strings)
    def table(self, period_str, mintick_digits, mintick):
        p = self.p
        o = self.last
        if o is None:
            return []
        bi = o["bar_index"]

        def f(x, fmt):
            return "-" if na(x) else fmt(x)

        f2 = lambda x: fmt2(x)
        fm = lambda x: fmt_mintick(x, mintick, mintick_digits)
        isRedNow = o["isRedNow"] == 1
        rows = [
            ("XPW MAP v0.4", period_str),
            ("state", "%s %db sep %s" % ("RED" if isRedNow else "LIME", self.runLen, f(o["sep"], f2))),
            ("BOTTOM squares", "none" if self.botCount == 0 else
             "n=%d  last %db sep %s, %d bars ago" % (self.botCount, self.lastBotW, f(self.lastBotSep, f2), bi - self.lastBotBar)),
            ("TOP squares", "none" if self.topCount == 0 else
             "n=%d  last %db sep %s, %d bars ago" % (self.topCount, self.lastTopW, f(self.lastTopSep, f2), bi - self.lastTopBar)),
            ("BOTTOM ticks", "none" if self.dnTickN == 0 else
             "n=%d  last %s ATR, %d bars ago" % (self.dnTickN, f(self.lastDnAtr, f2), bi - self.lastDnTk)),
            ("TOP ticks", "none" if self.upTickN == 0 else
             "n=%d  last %s ATR, %d bars ago" % (self.upTickN, f(self.lastUpAtr, f2), bi - self.lastUpTk)),
            ("move -1 / -2", "-" if self.m1Bars == 0 else
             "%db eff %s vel %s  |  %db eff %s vel %s" % (self.m1Bars, f(o["eff1"], f2), f(o["vel1"], fm),
                                                         self.m2Bars, f(o["eff2"], f2), f(o["vel2"], fm))),
            ("continuity", "-" if (na(o["eff1"]) or na(o["eff2"])) else
             ("move-1 more continuous" if o["eff1"] > o["eff2"] else
              "move-2 more continuous" if o["eff1"] < o["eff2"] else "equal")),
        ]
        return rows


# ---------------------------------------------------------------- string formats
def fmt2(x):
    """str.tostring(x, "#.##"): two decimals, trailing zeros trimmed (and the dot)."""
    if na(x):
        return "NaN"
    s = "%.2f" % x
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s == "-0":
        s = "0"
    return s


def fmt_mintick(x, mintick, digits):
    """str.tostring(x, format.mintick): rounded to the nearest mintick, printed with the symbol's digits."""
    if na(x):
        return "NaN"
    v = round(x / mintick) * mintick if mintick > 0 else x
    return "%.*f" % (digits, v)


# ---------------------------------------------------------------- driver
def run(bars, params=None):
    """bars: iterable of (open, high, low, close). Returns the list of per-bar output dicts."""
    sm = ShapeMap(params)
    return [sm.process(o, h, l, c) for (o, h, l, c) in bars], sm


if __name__ == "__main__":
    import sys, csv
    if len(sys.argv) < 2:
        print("usage: shapemap_ref.py <ohlc.csv> [key=value ...]   (columns open,high,low,close; time optional)")
        sys.exit(1)
    params = {}
    for kv in sys.argv[2:]:
        k, v = kv.split("=", 1)
        params[k] = (v.lower() == "true") if v.lower() in ("true", "false") else (float(v) if "." in v else int(v))
    rows = []
    with open(sys.argv[1], newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append((float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])))
    outs, sm = run(rows, params)
    w = csv.writer(sys.stdout)
    w.writerow(["bar_index"] + OUTPUT_COLUMNS)
    for o in outs:
        w.writerow([o["bar_index"]] + ["na" if na(o[k]) else o[k] for k in OUTPUT_COLUMNS])
