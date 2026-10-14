"""XPW Orientation TDI v2.8 strategy replay on real ticks.
13-rung ladder (rungs computed on their own bars, read with closed-by-chart-close semantics = lookahead_off on history),
assembly / inheritance / READ HERE, label events -> entries (every label trades), pyramiding with per-entry SL/TP/trail,
opposite labels reverse, FlashGold direction gate (60m). Signal tick fill = market at the next tick after the label candle closes.
Rungs without enough history are UNAVAILABLE (declared), seconds rungs disabled.
"""
import numpy as np, pandas as pd, math, sys
sys.path.insert(0, "../fg5"); from fg5 import Bars, bars_from_ticks, resample, SigParams, fgf_gate, rsi as rsi_pine
RUNGS = ["1 Month", "1 Week", "1 Day", "4 Hour", "1 Hour", "30 Min", "15 Min", "5 Min", "1 Min", "30 Sec", "15 Sec", "5 Sec", "1 Sec"]
RSEC = [2592000, 604800, 86400, 14400, 3600, 1800, 900, 300, 60, 30, 15, 5, 1]
HWIN = [20, 17, 28, 24, 16, 12, 12, 12, 20, 12, 12, 12, 20]
UNAV, UNRD, STAIR, ENDF, FIRST, MIDF, SECOND, MIDS = "UNAVAILABLE", "UNREADABLE", "STAIRCASE", "END FIRST LEG", "FIRST LEG", "MID FIRST LEG", "SECOND LEG", "MID SECOND LEG"

def rung_state(b: Bars, h, rsiLen=13, fastLen=2, bbLen=34, areaLen=5, areaFrac=0.45, trendLen=20):
    c = pd.Series(b.c); lo = pd.Series(b.l); hi = pd.Series(b.h)
    r = pd.Series(rsi_pine(b.c, rsiLen)); fast = r.rolling(fastLen).mean(); basis = r.rolling(bbLen).mean()
    recentLow = lo.rolling(h).min(); priorLow = recentLow.shift(h); recentHigh = hi.rolling(h).max(); priorHigh = recentHigh.shift(h)
    fLR = fast.rolling(h).min(); fLP = fLR.shift(h); fHR = fast.rolling(h).max(); fHP = fHR.shift(h)
    avail = recentLow.notna() & priorLow.notna() & fLR.notna() & fLP.notna() & recentHigh.notna() & priorHigh.notna() & fHR.notna() & fHP.notna()
    brokeLow = recentLow < priorLow; brokeHigh = recentHigh > priorHigh; tLow = fLR < fLP; tHigh = fHR > fHP
    refuseLow = brokeLow & ~tLow; refuseHigh = brokeHigh & ~tHigh
    rngS = fast.rolling(areaLen).max() - fast.rolling(areaLen).min(); rngL = fast.rolling(h).max() - fast.rolling(h).min()
    compressed = (rngL > 0) & ((rngS/rngL) <= areaFrac)
    stairUp = brokeHigh & tHigh & ~refuseHigh; stairDn = brokeLow & tLow & ~refuseLow
    smaC = c.rolling(trendLen).mean(); basisP = basis.shift(trendLen)
    dirOk = basisP.notna() & smaC.notna()
    d = np.where((basis > basisP) & (c > smaC), 1.0, np.where((basis < basisP) & (c < smaC), -1.0, 0.0))
    return dict(tclose=(b.tclose_arr if hasattr(b, "tclose_arr") else b.t + b.tf_ms), dir=d, rl=refuseLow.fillna(False).values, rh=refuseHigh.fillna(False).values, c=compressed.fillna(False).values,
                su=stairUp.fillna(False).values, sd=stairDn.fillna(False).values, ok=dirOk.values, avail=avail.values)

def map_to_chart(chart: Bars, st):
    """latest rung bar closed by the chart bar's close (lookahead_off on history)."""
    k = np.searchsorted(st["tclose"], chart.t + chart.tf_ms, side="right") - 1
    ok = k >= 0; kk = np.maximum(k, 0)
    out = {name: np.where(ok, st[name][kk], False if st[name].dtype == bool else 0.0) for name in ("dir", "rl", "rh", "c", "su", "sd", "ok")}
    out["avail"] = ok & np.where(ok, st["avail"][kk], False)
    return out

def ladder_events(chart: Bars, t, bid, chart_sec, ext=None):
    """Returns per-bar events list and readAt. ext: optional dict rung_name -> Bars for rungs not buildable from ticks (cross-feed)."""
    n = len(chart.c); chartIdx = max(i for i, s in enumerate(RSEC) if s >= chart_sec) if any(s >= chart_sec for s in RSEC) else 0
    # chart anchor: smallest rung >= chart tf = last index with RSEC >= chart_sec
    chartIdx = [i for i, s in enumerate(RSEC) if s >= chart_sec][-1]
    rungs = []
    for i, (name, sec, h) in enumerate(zip(RUNGS, RSEC, HWIN)):
        if sec < 60: rungs.append(None); continue                      # seconds rungs disabled
        if ext is not None and name in ext: rb = ext[name]
        elif sec*1000 == chart.tf_ms: rb = chart
        elif sec <= 86400: rb = bars_from_ticks(t, bid, sec*1000)
        else: rungs.append(None); continue
        if len(rb.c) < 2*h + 40: rungs.append(None); continue
        rungs.append(map_to_chart(chart, rung_state(rb, h)))
    posA = [UNAV]*13; prevPos = [""]*13; prevRead = -1
    events = []; readAtA = np.full(n, -1)
    for b in range(n):
        vals = []
        for i in range(13):
            r = rungs[i]
            if r is None or not r["avail"][b]: vals.append(None)
            else: vals.append(dict(dir=r["dir"][b], rl=bool(r["rl"][b]), rh=bool(r["rh"][b]), c=bool(r["c"][b]), su=bool(r["su"][b]), sd=bool(r["sd"][b]), ok=bool(r["ok"][b])))
        baseDir = None
        for i in range(13):
            if vals[i] is not None and vals[i]["ok"] and baseDir is None: baseDir = 1.0 if vals[i]["dir"] >= 0 else -1.0
        if baseDir is None: baseDir = 1.0
        flip = False; newPos = [UNAV]*13; inhA = [False]*13; orient = [1.0]*13
        for i in range(13):
            v = vals[i]; o = baseDir*(-1.0 if flip else 1.0); orient[i] = o
            pp = "" if i == 0 else newPos[i-1]; inh = False; pos = UNAV
            if v is not None:
                refStart = v["rl"] if o > 0 else v["rh"]; refEnd = v["rh"] if o > 0 else v["rl"]; stair = v["sd"] if o > 0 else v["su"]; area = v["c"]
                if stair: pos = STAIR
                elif refEnd: pos = ENDF
                elif refStart and area: pos = SECOND if pp in (ENDF, FIRST, MIDF) else FIRST
                elif area: pos = MIDS if pp in (SECOND, MIDS) else (STAIR if pp == STAIR else MIDF)
                else:
                    inh = True; pos = UNRD if (i == 0 or pp in (UNAV, UNRD)) else pp
            newPos[i] = pos; inhA[i] = inh
            if pos == ENDF and not inh: flip = not flip
            if pos == FIRST and not inh: flip = False
        readAt = -1
        for i in range(chartIdx, 13):
            if newPos[i] in (FIRST, SECOND) and not inhA[i]: readAt = i; break
        readAtA[b] = readAt
        ev = []   # (rung, code, up, isChart, isReadRung)
        for i in range(13):
            p = newPos[i]; prev = prevPos[i]
            if i == readAt and readAt != prevRead: prevR = ""
            else: prevR = prev
            up = orient[i] > 0
            for usePrev, tag in ((prev, "std"), (prevR, "read")):
                if tag == "read" and (i != readAt or prevR == prev): continue
                wasSecond = usePrev in (SECOND, MIDS)
                code = 0
                if p != usePrev and not inhA[i]:
                    if p == ENDF: code = 3
                    elif p == FIRST: code = 1
                    elif p == SECOND: code = 2
                    elif wasSecond and p in (STAIR, MIDF): code = 4
                    elif p == MIDF: code = 5
                    elif p == STAIR: code = 6
                if code: ev.append((i, code, up, i == chartIdx, i == readAt, tag))
            prevPos[i] = p
        prevRead = readAt
        events.append(ev)
    return events, readAtA, chartIdx

def entries_for(ev, b, readAt, chartIdx, mode, infoOn, reverseAll, lblRead=True):
    """mode: 'chart' | 'every'. Returns (nLong, nShort, srcs)."""
    L = []; S = []
    for (i, code, up, isChart, isRead, tag) in ev:
        active = (mode == "every") or (i == chartIdx)
        isReadRung = lblRead and i == readAt and not active
        if not (active or isReadRung): continue
        # for the READ rung, use the 'read' tagged event when it exists (prev reset), else 'std'
        if isReadRung:
            has_read = any(e[0] == i and e[5] == "read" for e in ev)
            if has_read and tag != "read": continue
        elif tag == "read": continue
        if code in (5, 6) and not infoOn: continue
        if code in (1, 2, 5): d = 1 if up else -1
        else: d = -1 if up else 1
        if reverseAll: d = -d
        (L if d > 0 else S).append(f"{RUNGS[i]}{' *' if isChart else (' <<' if isReadRung else '')} ev{code}")
    return L, S

class Exits:
    def __init__(self, unit="ATR", sl=3.0, tpR=1.0, trail=True, act=1.0, dist=0.75, slPts=10000, tpPts=30000, actPts=15000, distPts=10000):
        self.unit, self.sl, self.tpR, self.trail, self.act, self.dist, self.slPts, self.tpPts, self.actPts, self.distPts = unit, sl, tpR, trail, act, dist, slPts, tpPts, actPts, distPts
    def dists(self, a, tick):
        if self.unit == "Points": return self.slPts*tick, self.tpPts*tick, self.actPts*tick, max(self.distPts*tick, tick)
        return self.sl*a, self.tpR*self.sl*a, self.act*a, max(self.dist*a, tick)

def run(chart, t, bid, ask, bar_entries, atr, gb, gs, ex: Exits, maxOpen=20, fgf=True, lots=0.1, unit=1.0, comm_side=0.30, tick=0.01):
    n = len(chart.c); trades = []; open_ = []; queue = []   # queue: list of (side, src) to fill at next tick
    q = lots*unit
    def close_entry(e, px, tt, reason, bar):
        gross = (px-e["px"])*e["side"]*q; f = 2*comm_side*lots
        trades.append(dict(entry_t=e["t"], exit_t=tt, entry_bar=e["bar"], exit_bar=bar, side=e["side"], entry=e["px"], exit=px, sl_dist=e["sl"], gross=gross, fee=f, net=gross-f, reason=reason, kind=e["src"]))
    for i in range(n):
        s0, s1 = chart.bs[i], chart.be[i]; k0 = s0
        while k0 < s1:
            bb = bid[k0:s1]; ba = ask[k0:s1]; ev = []
            if queue: ev.append((0, -1, "Q", None))
            for j, e in enumerate(open_):
                side = e["side"]; x = bb if side > 0 else ba
                cm = np.maximum(np.maximum.accumulate(x*side), e["best"]*side)
                if e["sl"] > 0:
                    h = np.flatnonzero((x-(e["px"]-side*e["sl"]))*side <= 0)
                    if len(h): ev.append((h[0], 0, "SL", j))
                if e["tp"] > 0:
                    h = np.flatnonzero((x-(e["px"]+side*e["tp"]))*side >= 0)
                    if len(h): ev.append((h[0], 1, "TP", j))
                if ex.trail:
                    active = cm - e["px"]*side >= e["act"]; tstop = cm - e["dist"]
                    h = np.flatnonzero(active & (x*side <= tstop))
                    if len(h): ev.append((h[0], 2, "trail", j))
            if not ev: break
            ev.sort(key=lambda z: (z[0], z[1])); idx, _, kind, j = ev[0]; kk = k0+idx; tt = t[kk]
            if kind == "Q":
                side, src = queue.pop(0)
                px = ask[kk] if side > 0 else bid[kk]
                # reversal: close every open entry on the other side at this tick
                for e in [e for e in open_ if e["side"] == -side]:
                    e["best"] = max(e["best"]*e["side"], np.max((bid[k0:kk+1] if e["side"] > 0 else ask[k0:kk+1])*e["side"]))*e["side"]
                    close_entry(e, px, tt, "reverse", i)
                open_ = [e for e in open_ if e["side"] == side]
                sl, tp, act, dist = ex.dists(src[1], tick)
                open_.append(dict(side=side, px=px, t=tt, bar=i, sl=sl, tp=tp, act=act, dist=dist, best=px, src=src[0]))
                k0 = kk + 1 if not queue else kk      # remaining queued entries fill on the same tick
                if queue: k0 = kk
                if not queue: k0 = kk+1
                continue
            e = open_[j]; side = e["side"]; seg = bid[k0:kk+1] if side > 0 else ask[k0:kk+1]
            e["best"] = max(e["best"]*side, np.max(seg*side))*side
            close_entry(e, bid[kk] if side > 0 else ask[kk], tt, kind, i); open_.pop(j); k0 = kk+1
        for e in open_:
            seg = bid[s0:s1] if e["side"] > 0 else ask[s0:s1]
            if len(seg): e["best"] = max(e["best"]*e["side"], np.max(seg*e["side"]))*e["side"]
        # bar close: label entries
        L, S = bar_entries[i]
        if L and S: L, S = [], []
        posSize = sum(e["side"] for e in open_)
        a = atr[i]
        if L and ((not fgf) or gb[i]) and not np.isnan(a):
            room = maxOpen - len(open_)
            for src in L:
                if room > 0 or posSize < 0: queue.append((1, (src, a))); room -= 1
        if S and ((not fgf) or gs[i]) and not np.isnan(a):
            room = maxOpen - len(open_)
            for src in S:
                if room > 0 or posSize > 0: queue.append((-1, (src, a))); room -= 1
    for e in open_: close_entry(e, bid[-1] if e["side"] > 0 else ask[-1], t[-1], "end", n-1)
    return pd.DataFrame(trades)
