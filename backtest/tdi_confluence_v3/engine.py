"""Python port of 'TDI Confluence Strategy v3.0 [Full]' + a TradingView-style broker emulator."""
import glob, os
import numpy as np, pandas as pd
from numba import njit

HERE = os.path.dirname(os.path.abspath(__file__))
TICK = 0.01  # BTCUSDT mintick


def load_1m():
    fs = sorted(glob.glob(os.path.join(HERE, "data", "BTCUSDT-1m-*.csv")))
    df = pd.concat([pd.read_csv(f, header=None, usecols=range(6)) for f in fs])
    df.columns = ["t", "o", "h", "l", "c", "v"]
    t = df["t"].astype("int64")
    t = np.where(t > 1e14, t // 1000, t)  # us -> ms
    df.index = pd.to_datetime(t, unit="ms", utc=True).as_unit("ns")  # MTF mapping below works in ns
    return df.drop(columns="t").sort_index()


def resample(df, tf):
    if tf == 1:
        return df.copy()
    r = df.resample(f"{tf}min", label="left", closed="left")
    return pd.DataFrame({"o": r.o.first(), "h": r.h.max(), "l": r.l.min(), "c": r.c.last()}).dropna()


# ---------------- Pine primitives ----------------
@njit(cache=True)
def rsi(c, n):
    out = np.full(c.size, np.nan)
    g = 0.0; l = 0.0
    for i in range(1, c.size):
        d = c[i] - c[i - 1]
        up = d if d > 0 else 0.0; dn = -d if d < 0 else 0.0
        if i < n:
            g += up; l += dn
        elif i == n:
            g = (g + up) / n; l = (l + dn) / n
        else:
            a = 1.0 / n
            g = a * up + (1.0 - a) * g; l = a * dn + (1.0 - a) * l
        if i >= n:
            out[i] = 100.0 if l == 0 else (0.0 if g == 0 else 100 - 100 / (1 + g / l))
    return out


def sma(x, n):
    return pd.Series(x).rolling(n).mean().to_numpy()


def stdev(x, n):
    return pd.Series(x).rolling(n).std(ddof=0).to_numpy()


def cross_over(a, b):
    a1 = np.roll(a, 1); b1 = np.roll(b, 1)
    r = (a > b) & (a1 <= b1); r[0] = False
    return r


def calc_tdi(c):
    r = rsi(c, 14)
    ma = sma(r, 34); off = 1.6185 * stdev(r, 34)
    mid = ((ma + off) + (ma - off)) / 2
    mbb = sma(r, 7); mab = sma(r, 2)
    with np.errstate(invalid="ignore"):
        long1 = cross_over(mab, mbb) & (mbb > mid) & (mbb > 50)
        short1 = cross_over(mbb, mab) & (mbb < mid) & (mbb < 50)
    return long1, short1


@njit(cache=True)
def _pivots(osc, L, R, low):
    n = osc.size
    pl = np.full(n, np.nan); ph = np.full(n, np.nan)
    for i in range(L + R, n):
        c = i - R; v = osc[c]
        if np.isnan(v):
            continue
        isl = True; ish = True
        for k in range(c - L, c + R + 1):
            if k == c:
                continue
            w = osc[k]
            if np.isnan(w):
                isl = False; ish = False; break
            if k < c:
                if not v < w: isl = False
                if not v > w: ish = False
            else:
                if not v <= w: isl = False
                if not v >= w: ish = False
        if isl: pl[i] = v
        if ish: ph[i] = v
    return pl, ph


@njit(cache=True)
def _div(osc, lo, hi, L, R, mn, mx):
    n = osc.size
    pl, ph = _pivots(osc, L, R, lo)
    rb = np.zeros(n, np.bool_); rr = np.zeros(n, np.bool_)
    hb = np.zeros(n, np.bool_); hr = np.zeros(n, np.bool_)
    # state: last & prev pivot (osc, price), bars since
    lastPlO = np.nan; lastPlP = np.nan; lastPhO = np.nan; lastPhP = np.nan
    bsPl = -1; bsPh = -1  # -1 == na
    for i in range(n):
        prevBsPl = bsPl; prevBsPh = bsPh
        if not np.isnan(pl[i]):
            prevO = lastPlO; prevP = lastPlP; cp = lo[i - R]; v = pl[i]
            okb = prevBsPl >= 0 and mn <= prevBsPl and prevBsPl <= mx
            if not np.isnan(prevO) and okb:
                if cp < prevP and v > prevO: rb[i] = True
                if cp > prevP and v < prevO: hb[i] = True
            lastPlO = v; lastPlP = cp; bsPl = 0
        elif bsPl >= 0:
            bsPl += 1
        if not np.isnan(ph[i]):
            prevO = lastPhO; prevP = lastPhP; cp = hi[i - R]; v = ph[i]
            okb = prevBsPh >= 0 and mn <= prevBsPh and prevBsPh <= mx
            if not np.isnan(prevO) and okb:
                if cp > prevP and v < prevO: rr[i] = True
                if cp < prevP and v > prevO: hr[i] = True
            lastPhO = v; lastPhP = cp; bsPh = 0
        elif bsPh >= 0:
            bsPh += 1
    return rb, rr, hb, hr


def calc_div(o, h, l, c, L, R, mn, mx):
    return _div(rsi(c, 14), l, h, L, R, mn, mx)


# ---------------- MTF mapping (request.security, lookahead_off, history) ----------------
def map_security(sec_close_t, vals, chart_close_t):
    """value of last security bar whose close time <= chart bar close time."""
    idx = np.searchsorted(sec_close_t, chart_close_t, side="right") - 1
    out = []
    for v in vals:
        m = np.zeros(chart_close_t.size, bool)
        ok = idx >= 0
        m[ok] = v[idx[ok]]
        out.append(m)
    return out


TFS = [1, 5, 15, 30, 60]
_cache = {}


def security_block(df1, chart_tf, L, R, mn, mx):
    """returns dict tf -> (tdiL, tdiS, rb, rr, hb, hr) mapped to chart bars + chart df."""
    key = (chart_tf, L, R, mn, mx)
    if key in _cache:
        return _cache[key]
    ch = resample(df1, chart_tf)
    cct = ch.index.values.astype("int64") + chart_tf * 60_000_000_000
    out = {}
    for tf in TFS:
        s = resample(df1, tf)
        o, h, l, c = (s[k].to_numpy() for k in "ohlc")
        tl, ts = calc_tdi(c)
        rb, rr, hb, hr = calc_div(o, h, l, c, L, R, mn, mx)
        sct = s.index.values.astype("int64") + tf * 60_000_000_000
        out[tf] = map_security(sct, [tl, ts, rb, rr, hb, hr], cct)
    _cache[key] = (ch, out)
    return ch, out


def edge(x):
    p = np.roll(x, 1); p[0] = False
    return x & ~p


@njit(cache=True)
def _day_and_counters(h, l, newDay, bull, bear):
    n = h.size
    dH = np.empty(n); dL = np.empty(n)
    nb = bull.shape[1]
    cb = np.zeros(nb, np.int64); cs = np.zeros(nb, np.int64)
    f4b = np.zeros(n, np.bool_); f4s = np.zeros(n, np.bool_)
    for i in range(n):
        if newDay[i] or i == 0:
            dH[i] = h[i]; dL[i] = l[i]
        else:
            dH[i] = max(dH[i - 1], h[i]); dL[i] = min(dL[i - 1], l[i])
        if newDay[i]:
            cb[:] = 0; cs[:] = 0
        for k in range(nb):
            if bull[i, k]:
                cb[k] += 1; cs[k] = 0
            if bear[i, k]:
                cs[k] += 1; cb[k] = 0
            if cb[k] == 4 and bull[i, k]: f4b[i] = True
            if cs[k] == 4 and bear[i, k]: f4s[i] = True
    return dH, dL, f4b, f4s


def signals(df1, chart_tf=5, divL=5, divR=5, divMin=5, divMax=60, dayH=0, dayM=0,
            tfs_on=(1, 1, 1, 1, 1), regBull=True, regBear=False, hidBull=False, hidBear=False,
            req4=False, levels=False, buyLevel=38, sellLevel=62, fix_toggles=False):
    regBull, regBear, hidBull, hidBear = bool(regBull), bool(regBear), bool(hidBull), bool(hidBear)
    ch, sec = security_block(df1, chart_tf, divL, divR, divMin, divMax)
    h = ch.h.to_numpy(); l = ch.l.to_numpy(); c = ch.c.to_numpy()
    hr = ch.index.hour.to_numpy(); mi = ch.index.minute.to_numpy()
    at = (hr == dayH) & (mi == dayM)
    newDay = at & ~np.r_[False, at[:-1]]
    bull = np.zeros((h.size, 5), bool); bear = np.zeros((h.size, 5), bool)
    rawL = np.zeros(h.size, bool); rawS = np.zeros(h.size, bool)
    for k, tf in enumerate(TFS):
        tl, ts, rb, rr, hb, hrr = sec[tf]
        on = bool(tfs_on[k])
        bull[:, k] = (on & edge(tl)) | (regBull & edge(rb)) | (hidBull & edge(hb))
        bear[:, k] = (on & edge(ts)) | (regBear & edge(rr)) | (hidBear & edge(hrr))
        if fix_toggles:  # variant: entry filter honours the toggles
            rawL |= (on & tl) | (regBull & rb) | (hidBull & hb)
            rawS |= (on & ts) | (regBear & rr) | (hidBear & hrr)
        else:            # as written: raw values of every TF regardless of toggles
            rawL |= tl | rb | hb
            rawS |= ts | rr | hrr
    dH, dL, f4b, f4s = _day_and_counters(h, l, newDay, bull, bear)
    dH1 = np.r_[np.nan, dH[:-1]]; dL1 = np.r_[np.nan, dL[:-1]]
    l1 = np.r_[np.nan, l[:-1]]; h1 = np.r_[np.nan, h[:-1]]
    with np.errstate(invalid="ignore"):
        breakHigh = (h > np.nan_to_num(dH1)) & (l1 <= np.nan_to_num(dH1))
        breakLow = (l < np.nan_to_num(dL1)) & (h1 >= np.nan_to_num(dL1))
    fL = breakLow & rawL; fS = breakHigh & rawS
    if req4:
        fL &= f4b; fS &= f4s
    cL = edge(fL); cS = edge(fS)
    if levels:
        fast = sma(rsi(c, 14), 2)
        with np.errstate(invalid="ignore"):
            cL &= fast <= buyLevel; cS &= fast >= sellLevel
    return ch, cL, cS


# ---------------- broker emulator ----------------
@njit(cache=True)
def _walk(pts, E, sl, tp, act, off, use_trail, peak, tact):
    """long-side path walk on (possibly negated) prices. returns (exit_px or nan, peak, tact)."""
    stop = E - sl
    ts = -1e18
    if use_trail and tact:
        ts = peak - off
    p0 = pts[0]
    if p0 > peak:
        peak = p0
    if use_trail and peak >= E + act:
        tact = True
    if use_trail and tact:
        ts = peak - off
    st = max(stop, ts)
    if p0 <= st: return p0, peak, tact
    if p0 >= E + tp: return p0, peak, tact
    for s in range(3):
        a = pts[s]; b = pts[s + 1]
        if b > a:
            if b >= E + tp:
                # trail could have activated on the way; can't stop going up
                return E + tp, peak, tact
            if b > peak: peak = b
            if use_trail and peak >= E + act:
                tact = True
                ts = peak - off
        elif b < a:
            st = stop
            if use_trail and tact and ts > st: st = ts
            if b <= st:
                return st, peak, tact
    return np.nan, peak, tact


@njit(cache=True)
def simulate(o, h, l, c, sigL, sigS, sl_t, tp_t, use_trail, act_t, off_t, tick, comm, eq0, pct):
    n = o.size
    sl = sl_t * tick; tp = tp_t * tick; act = act_t * tick; off = off_t * tick
    pos = 0; E = 0.0; qty = 0.0; armed = False; peak = 0.0; tact = False
    eq = eq0; peakEq = eq0; mdd = 0.0
    maxT = n
    tr_pnl = np.zeros(maxT); tr_bar = np.zeros(maxT, np.int64); nt = 0
    pend = 0; pendQty = 0.0
    pts = np.empty(4)
    for i in range(n):
        # 1) market orders from previous close fill at open
        if pend != 0 and pend != pos:
            if pos != 0:
                pnl = pos * qty * (o[i] - E) - comm * qty * (o[i] + E)
                eq += pnl; tr_pnl[nt] = pnl; tr_bar[nt] = i; nt += 1
            pos = pend; E = o[i]; qty = pendQty; armed = False; tact = False
            peak = E if pos > 0 else -E
        pend = 0
        # 2) exits (only once strategy.exit was registered on a previous close)
        if pos != 0 and armed:
            if abs(o[i] - h[i]) < abs(o[i] - l[i]):
                pts[0] = o[i]; pts[1] = h[i]; pts[2] = l[i]; pts[3] = c[i]
            else:
                pts[0] = o[i]; pts[1] = l[i]; pts[2] = h[i]; pts[3] = c[i]
            if pos < 0:
                for k in range(4): pts[k] = -pts[k]
            Eadj = E if pos > 0 else -E
            px, peak, tact = _walk(pts, Eadj, sl, tp, act, off, use_trail, peak, tact)
            if not np.isnan(px):
                xp = px if pos > 0 else -px
                pnl = pos * qty * (xp - E) - comm * qty * (xp + E)
                eq += pnl; tr_pnl[nt] = pnl; tr_bar[nt] = i; nt += 1
                pos = 0
        if eq > peakEq: peakEq = eq
        dd = (peakEq - eq) / peakEq
        if dd > mdd: mdd = dd
        # 3) script at close
        if pos != 0:
            armed = True
        eqo = eq + (pos * qty * (c[i] - E) if pos != 0 else 0.0)  # strategy.equity incl. open profit
        if sigL[i] and not sigS[i] and pos != 1:
            pend = 1; pendQty = eqo * pct / c[i]
        elif sigS[i] and not sigL[i] and pos != -1:
            pend = -1; pendQty = eqo * pct / c[i]
    return tr_pnl[:nt], tr_bar[:nt], mdd


def stats(pnl, mdd, eq0=10000.0):
    n = pnl.size
    if n == 0:
        return dict(trades=0, net_pct=0.0, win=np.nan, pf=np.nan, mdd_pct=0.0, avg_bp=np.nan)
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    return dict(trades=n, net_pct=100 * pnl.sum() / eq0, win=100 * (pnl > 0).mean(),
                pf=gp / gl if gl > 0 else np.inf, mdd_pct=100 * mdd,
                # avg trade in basis points of the traded notional (1% equity)
                avg_bp=1e4 * pnl.mean() / (eq0 * 0.01))


# ================= v3.1: distance-based exits (ticks / ATR / percent) =================
@njit(cache=True)
def atr(h, l, c, n):
    m = h.size
    out = np.full(m, np.nan)
    s = 0.0
    for i in range(m):
        tr = h[i] - l[i] if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        if i < n - 1:
            s += tr
        elif i == n - 1:
            s = (s + tr) / n; out[i] = s
        else:
            s = (1.0 / n) * tr + (1.0 - 1.0 / n) * s; out[i] = s
    return out


def map_float(sec_close_t, v, chart_close_t):
    idx = np.searchsorted(sec_close_t, chart_close_t, side="right") - 1
    out = np.full(chart_close_t.size, np.nan)
    ok = idx >= 0
    out[ok] = v[idx[ok]]
    return out


def atr_on_chart(df1, ch, chart_tf, atr_tf, n):
    """ATR in price units on chart bars. atr_tf == 0 -> chart TF (ta.atr); otherwise
    last *closed* atr_tf bar (request.security(..., ta.atr(n)[1], lookahead_on))."""
    if atr_tf == 0:
        return atr(ch.h.to_numpy(), ch.l.to_numpy(), ch.c.to_numpy(), n)
    # Pine: request.security(tf, ta.atr(n)[1], lookahead_on) -> every chart bar inside HTF bar k
    # (including the one closing it) sees atr[k-1]. Index by chart-bar OPEN time, shift back one.
    s = resample(df1, atr_tf)
    a = atr(s.h.to_numpy(), s.l.to_numpy(), s.c.to_numpy(), n)
    k = np.searchsorted(s.index.values.astype("int64"), ch.index.values.astype("int64"), side="right") - 1
    out = np.full(len(ch), np.nan)
    ok = k >= 1
    out[ok] = a[k[ok] - 1]
    return out


@njit(cache=True)
def simulate_d(o, h, l, c, sigL, sigS, slA, tpA, actA, offA, use_trail, arm_on_fill, comm):
    """Exit distances (price units) are taken from the arrays at the SIGNAL bar and frozen
    for the trade. arm_on_fill=True: exits protect the position from the fill bar (v3.1 Pine
    places strategy.exit on the entry bar); False reproduces v3.0 (armed one bar later).
    Returns per-trade return in bp of notional (after commission), entry bar, side."""
    n = o.size
    ret = np.zeros(n); ebar = np.zeros(n, np.int64); side = np.zeros(n, np.int64); nt = 0
    pos = 0; E = 0.0; armed = False; peak = 0.0; tact = False; eb = 0
    sl = 0.0; tp = 0.0; act = 0.0; off = 0.0
    pend = 0; psl = 0.0; ptp = 0.0; pact = 0.0; poff = 0.0
    pts = np.empty(4)
    for i in range(n):
        if pend != 0 and pend != pos:
            if pos != 0:
                ret[nt] = 1e4 * (pos * (o[i] - E) / E - comm * (o[i] + E) / E)
                ebar[nt] = eb; side[nt] = pos; nt += 1
            pos = pend; E = o[i]; eb = i; tact = False
            sl = psl; tp = ptp; act = pact; off = poff
            peak = E if pos > 0 else -E
            armed = arm_on_fill
        pend = 0
        if pos != 0 and armed:
            if abs(o[i] - h[i]) < abs(o[i] - l[i]):
                pts[0] = o[i]; pts[1] = h[i]; pts[2] = l[i]; pts[3] = c[i]
            else:
                pts[0] = o[i]; pts[1] = l[i]; pts[2] = h[i]; pts[3] = c[i]
            if pos < 0:
                for k in range(4): pts[k] = -pts[k]
            Eadj = E if pos > 0 else -E
            px, peak, tact = _walk(pts, Eadj, sl, tp, act, off, use_trail, peak, tact)
            if not np.isnan(px):
                xp = px if pos > 0 else -px
                ret[nt] = 1e4 * (pos * (xp - E) / E - comm * (xp + E) / E)
                ebar[nt] = eb; side[nt] = pos; nt += 1
                pos = 0
        if pos != 0:
            armed = True
        ok = not np.isnan(slA[i])
        if ok and sigL[i] and not sigS[i] and pos != 1:
            pend = 1; psl = slA[i]; ptp = tpA[i]; pact = actA[i]; poff = offA[i]
        elif ok and sigS[i] and not sigL[i] and pos != -1:
            pend = -1; psl = slA[i]; ptp = tpA[i]; pact = actA[i]; poff = offA[i]
    return ret[:nt], ebar[:nt], side[:nt]
