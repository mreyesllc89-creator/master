#!/usr/bin/env python3
"""
More trailing systems for the hump (Loma) backtest, on top of hump_trail.py (which is left untouched).

New kinds (config key "trail_kind"):
  chandelier  stop = best price since entry -/+ trail_dist x ATR(14) of the trigger timeframe, with the ATR of
              the last closed trigger bar (a live ATR, unlike kind "atr" which fixes it at the signal)
  profitlock  once the profit reaches trail_start x risk, the stop locks trail_dist (0..1) of the best open profit
  timestop    the stop moves linearly from the initial stop to breakeven over trail_dist market minutes
  partial     half the position is closed at +trail_start x risk, the stop of the rest goes to breakeven and,
              if trail_dist > 0, trails the best price at trail_dist x risk (when the target is reached on the same
              bar as the half-close level, half is booked at that level and half at the target)
  supertrend  level trailing at the SuperTrend line (trail_p: 0 = 10/3.0, 1 = 10/2.0, 2 = 7/1.5)
  keltner     level trailing at the Keltner band EMA(20) -/+ m x ATR(10) (trail_p: 0 = 1.0, 1 = 1.5, 2 = 2.0)
  bollinger   level trailing at the Bollinger band SMA(20) -/+ k x sd (trail_p: 0 = 1.0, 1 = 2.0)
  kijun       level trailing at the Ichimoku base line (highest high + lowest low) / 2 over trail_p bars
  pivots      level trailing at the last confirmed swing low / high with trail_p bars on each side
              (2 = Bill Williams fractals; larger = ZigZag-like swings)
  sma         level trailing at the SMA(trail_p) of the trigger closes
  donchian    level trailing at the lowest low / highest high of trail_p trigger bars (20, 55)
  htfcandle   level trailing at the low / high of the last closed higher-timeframe candle (trail_p = its minutes)
Level kinds use only trigger (or higher-timeframe) bars closed at or before the open of each M1 bar; the stop
is level -/+ the setup's SL buffer (+ spread for sells), is only ever tightened, and starts once the profit has
reached trail_start x risk (0 = from the one-minute bar after the entry bar).

One-minute resolution. hump_trail.simulate_x places a dollar, percent or ATR-at-entry trailing stop from the
running bar's own extreme. When the distance is under about two one-minute ranges the pullbacks inside the bar
are never tested, and the result is too good (measured against ticks: up to +0.05R per trade). run_y therefore
uses a rule that one-minute data resolves exactly, for the kinds points, percent, atr, profitlock and the trailing
part of partial: the stop is moved from the extreme of each COMPLETED one-minute bar and holds from the next
bar's open (config key "trail_closed", default 1; 0 gives the old rule). Kind R, the EA's own trailing, keeps
the engine's rule; chandelier and the level kinds always worked from completed bars. simulate_y with
trail_closed 0 reproduces hump_trail.simulate_x for every earlier kind (self-test in __main__).
"""
import os, sys
import numba as nb, numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_engine as H, xlzc_backtest as B
import hump_trail as T

KIND2 = {"chandelier": 8, "profitlock": 9, "timestop": 10, "partial": 11,
         "supertrend": 7, "keltner": 7, "bollinger": 7, "kijun": 7, "pivots": 7, "sma": 7, "donchian": 7, "htfcandle": 7}
ALLKIND = dict(T.KIND, **KIND2)
SUPERTREND = {0: (10, 3.0), 1: (10, 2.0), 2: (7, 1.5)}
KELTNER = {0: 1.0, 1: 1.5, 2: 2.0}
BOLLINGER = {0: 1.0, 1: 2.0}


@nb.njit(cache=True)
def simulate_y(sig, entry_row, o, h, l, c, hs, tod, s0, s1, buf, anticip, min_rr, tp_mode, tp_rr,
               trail_start, trail_dist, max_spread, min_risk, max_risk, slip, comm, delay, trail_worst, wk,
               max_hold, eod, trail_kind, tb, lvl_hi, lvl_lo, aux, closed):
    """hump_trail.simulate_x plus trail_kind 8 chandelier (aux = ATR per trigger bar), 9 profit lock,
    10 time stop, 11 partial close. Returns rows (entry_row, exit_row, side, R, risk).
    closed = 1: kinds 2, 3, 4 (dollars, percent, ATR at entry), 9 (profit lock) and the trailing part of 11 move the
    stop from the extreme of each COMPLETED one-minute bar; the new stop holds from the next bar's open (filled at
    that open when the price is already through it) and never closes the trade inside the bar that set it.
    closed = 0: those kinds use the rule of hump_trail.simulate_x (stop from the running bar's own extreme)."""
    n = len(o)
    out = np.empty((len(sig), 5))
    m = 0
    busy = -1
    for k in range(len(sig)):
        e = entry_row[k]
        if e >= 0:
            e += delay
        if e < 0 or e >= n or e <= busy:
            continue
        if not (s0 <= tod[e] < s1) if s0 < s1 else not (tod[e] >= s0 or tod[e] < s1):
            continue
        sp = 2 * hs[e]
        if sp > max_spread:
            continue
        if wk[e]:
            continue
        side = int(sig[k, 1])
        atr = sig[k, 5]
        part = False
        if side < 0:
            entry = o[e] - hs[e] - slip
            sl = sig[k, 2] + buf + hs[e]
            risk = sl - entry
            if not (risk == risk):
                continue
            if risk < min_risk or risk > max_risk:
                continue
            if tp_mode == 0:
                ref = sig[k, 3]
                tp = ref + anticip * (entry - ref) + hs[e]
            else:
                tp = entry - tp_rr * risk
            unit = risk if trail_kind == 1 else (1.0 if trail_kind == 2 else (0.01 * entry if trail_kind == 3 else atr))
            if entry - tp < min_rr * risk:
                continue
            stop = sl; px = np.nan; j = e
            act = trail_start <= 0.0
            best = entry                                   # lowest ask-side low seen on earlier bars
            while j < n:
                ah = h[j] + hs[j]; al = l[j] + hs[j]; ao = o[j] + hs[j]
                if j > e:                                  # stop moves known at this bar's open
                    if trail_kind == 7:
                        if act:
                            i = tb[j]
                            if i >= 0:
                                lv = lvl_hi[i]
                                if lv == lv:
                                    cand = lv + buf + hs[j]
                                    if cand < stop:
                                        stop = cand
                    elif trail_kind == 8:
                        if act:
                            i = tb[j]
                            if i >= 0:
                                a = aux[i]
                                if a == a:
                                    cand = best + trail_dist * a
                                    if cand < stop:
                                        stop = cand
                    elif trail_kind == 10:
                        frac = (j - e) / trail_dist
                        if frac > 1.0:
                            frac = 1.0
                        cand = sl - frac * (sl - entry)
                        if cand < stop:
                            stop = cand
                if ao >= stop:
                    px = ao + slip; break
                if ah >= stop:
                    px = stop + slip; break
                if al <= tp:
                    px = min(tp, ao)
                    if trail_kind == 11 and (not part) and trail_start * risk <= entry - tp + 1e-9 * risk:
                        part = True                        # the half-close level lies at or before the target (rounding-tolerant): half is booked there
                    break
                fav = entry - al
                if trail_kind >= 1 and trail_kind <= 4:
                    if trail_start > 0 and fav >= trail_start * unit:
                        cand = al + trail_dist * unit
                        if cand < stop:
                            stop = cand
                            if (closed == 0 or trail_kind == 1) and (c[j] + hs[j] >= stop or (trail_worst == 1 and ah >= stop)):
                                px = stop + slip; break
                elif trail_kind == 5:
                    if trail_start > 0 and fav >= trail_start * risk:
                        cand = entry - trail_dist * risk
                        if cand < stop:
                            stop = cand
                            if c[j] + hs[j] >= stop or (trail_worst == 1 and ah >= stop):
                                px = stop + slip; break
                elif trail_kind == 6:
                    if trail_start > 0 and fav >= trail_start * risk:
                        kk = np.floor(fav / (trail_start * risk))
                        cand = entry - (kk - 1.0) * trail_start * risk
                        if cand < stop:
                            stop = cand
                            if c[j] + hs[j] >= stop or (trail_worst == 1 and ah >= stop):
                                px = stop + slip; break
                elif trail_kind == 7 or trail_kind == 8:
                    if (not act) and fav >= trail_start * risk:
                        act = True
                elif trail_kind == 9:
                    if trail_start > 0 and fav >= trail_start * risk:
                        cand = entry - trail_dist * fav
                        if cand < stop:
                            stop = cand
                            if closed == 0 and (c[j] + hs[j] >= stop or (trail_worst == 1 and ah >= stop)):
                                px = stop + slip; break
                elif trail_kind == 11:
                    hit = False
                    if (not part) and fav >= trail_start * risk:
                        part = True                        # half closed at entry - trail_start x risk
                        if entry < stop:
                            stop = entry; hit = True
                    if closed == 1:
                        if hit and (c[j] + hs[j] >= stop or (trail_worst == 1 and ah >= stop)):
                            px = stop + slip; break            # the rest goes out at breakeven in the half-close bar
                        if part and trail_dist > 0:
                            cand = al + trail_dist * risk
                            if cand < stop:
                                stop = cand                    # holds from the next bar's open
                    else:
                        if part and trail_dist > 0:
                            cand = al + trail_dist * risk
                            if cand < stop:
                                stop = cand; hit = True
                        if hit and (c[j] + hs[j] >= stop or (trail_worst == 1 and ah >= stop)):
                            px = stop + slip; break
                if al < best:
                    best = al
                if wk[j]:
                    px = c[j] + hs[j] + slip; break
                if (max_hold > 0 and j - e >= max_hold) or \
                        (eod >= 0 and j > e and tod[j] >= eod and (tod[j - 1] < eod or tod[j - 1] > tod[j])):
                    px = c[j] + hs[j] + slip; break
                j += 1
            if px != px:
                j = n - 1; px = c[j] + hs[j]
            r = (entry - px - comm) / risk
        else:
            entry = o[e] + hs[e] + slip
            sl = sig[k, 2] - buf - hs[e]
            risk = entry - sl
            if not (risk == risk):
                continue
            if risk < min_risk or risk > max_risk:
                continue
            if tp_mode == 0:
                ref = sig[k, 3]
                tp = ref - anticip * (ref - entry) - hs[e]
            else:
                tp = entry + tp_rr * risk
            unit = risk if trail_kind == 1 else (1.0 if trail_kind == 2 else (0.01 * entry if trail_kind == 3 else atr))
            if tp - entry < min_rr * risk:
                continue
            stop = sl; px = np.nan; j = e
            act = trail_start <= 0.0
            best = entry                                   # highest bid-side high seen on earlier bars
            while j < n:
                bh = h[j] - hs[j]; bl = l[j] - hs[j]; bo = o[j] - hs[j]
                if j > e:
                    if trail_kind == 7:
                        if act:
                            i = tb[j]
                            if i >= 0:
                                lv = lvl_lo[i]
                                if lv == lv:
                                    cand = lv - buf - hs[j]
                                    if cand > stop:
                                        stop = cand
                    elif trail_kind == 8:
                        if act:
                            i = tb[j]
                            if i >= 0:
                                a = aux[i]
                                if a == a:
                                    cand = best - trail_dist * a
                                    if cand > stop:
                                        stop = cand
                    elif trail_kind == 10:
                        frac = (j - e) / trail_dist
                        if frac > 1.0:
                            frac = 1.0
                        cand = sl + frac * (entry - sl)
                        if cand > stop:
                            stop = cand
                if bo <= stop:
                    px = bo - slip; break
                if bl <= stop:
                    px = stop - slip; break
                if bh >= tp:
                    px = max(tp, bo)
                    if trail_kind == 11 and (not part) and trail_start * risk <= tp - entry + 1e-9 * risk:
                        part = True
                    break
                fav = bh - entry
                if trail_kind >= 1 and trail_kind <= 4:
                    if trail_start > 0 and fav >= trail_start * unit:
                        cand = bh - trail_dist * unit
                        if cand > stop:
                            stop = cand
                            if (closed == 0 or trail_kind == 1) and (c[j] - hs[j] <= stop or (trail_worst == 1 and bl <= stop)):
                                px = stop - slip; break
                elif trail_kind == 5:
                    if trail_start > 0 and fav >= trail_start * risk:
                        cand = entry + trail_dist * risk
                        if cand > stop:
                            stop = cand
                            if c[j] - hs[j] <= stop or (trail_worst == 1 and bl <= stop):
                                px = stop - slip; break
                elif trail_kind == 6:
                    if trail_start > 0 and fav >= trail_start * risk:
                        kk = np.floor(fav / (trail_start * risk))
                        cand = entry + (kk - 1.0) * trail_start * risk
                        if cand > stop:
                            stop = cand
                            if c[j] - hs[j] <= stop or (trail_worst == 1 and bl <= stop):
                                px = stop - slip; break
                elif trail_kind == 7 or trail_kind == 8:
                    if (not act) and fav >= trail_start * risk:
                        act = True
                elif trail_kind == 9:
                    if trail_start > 0 and fav >= trail_start * risk:
                        cand = entry + trail_dist * fav
                        if cand > stop:
                            stop = cand
                            if closed == 0 and (c[j] - hs[j] <= stop or (trail_worst == 1 and bl <= stop)):
                                px = stop - slip; break
                elif trail_kind == 11:
                    hit = False
                    if (not part) and fav >= trail_start * risk:
                        part = True
                        if entry > stop:
                            stop = entry; hit = True
                    if closed == 1:
                        if hit and (c[j] - hs[j] <= stop or (trail_worst == 1 and bl <= stop)):
                            px = stop - slip; break
                        if part and trail_dist > 0:
                            cand = bh - trail_dist * risk
                            if cand > stop:
                                stop = cand
                    else:
                        if part and trail_dist > 0:
                            cand = bh - trail_dist * risk
                            if cand > stop:
                                stop = cand; hit = True
                        if hit and (c[j] - hs[j] <= stop or (trail_worst == 1 and bl <= stop)):
                            px = stop - slip; break
                if bh > best:
                    best = bh
                if wk[j]:
                    px = c[j] - hs[j] - slip; break
                if (max_hold > 0 and j - e >= max_hold) or \
                        (eod >= 0 and j > e and tod[j] >= eod and (tod[j - 1] < eod or tod[j - 1] > tod[j])):
                    px = c[j] - hs[j] - slip; break
                j += 1
            if px != px:
                j = n - 1; px = c[j] - hs[j]
            r = (px - entry - comm) / risk
        if part:                                           # half closed at +trail_start R, half at the final exit
            r = 0.5 * (trail_start - comm / risk) + 0.5 * r
        out[m, 0] = e; out[m, 1] = j; out[m, 2] = side; out[m, 3] = r; out[m, 4] = risk
        m += 1
        busy = j
    return out[:m]


@nb.njit(cache=True)
def supertrend_levels(high, low, close, atr, mult):
    """SuperTrend line known at each bar's close: (resistance when the trend is down, support when it is up)."""
    n = len(close)
    hi = np.full(n, np.nan); lo = np.full(n, np.nan)
    fu = np.nan; fl = np.nan; up = True; started = False
    for i in range(n):
        a = atr[i]
        if not (a == a):
            continue
        mid = 0.5 * (high[i] + low[i])
        ub = mid + mult * a; lb = mid - mult * a
        if not started:
            fu = ub; fl = lb; up = close[i] >= mid; started = True
        else:
            pfu = fu; pfl = fl
            fu = ub if (ub < pfu or close[i - 1] > pfu) else pfu
            fl = lb if (lb > pfl or close[i - 1] < pfl) else pfl
            if up:                                  # the flip is tied to the current state (classic SuperTrend):
                if close[i] < pfl:                   # an up-trend ends on a close below its support line, even when a
                    up = False                       # stale upper band lies below that close after a gap up
            elif close[i] > pfu:
                up = True
        if up:
            lo[i] = fl
        else:
            hi[i] = fu
    return hi, lo


@nb.njit(cache=True)
def pivot_levels(high, low, w):
    """Last confirmed swing high / low with w bars on each side; a pivot at bar j is known at bar j + w."""
    n = len(high)
    hi = np.full(n, np.nan); lo = np.full(n, np.nan)
    lhi = np.nan; llo = np.nan
    for i in range(n):
        j = i - w
        if j >= w:
            is_hi = True; is_lo = True
            for q in range(j - w, j + w + 1):
                if q != j:
                    if high[q] >= high[j]:
                        is_hi = False
                    if low[q] <= low[j]:
                        is_lo = False
            if is_hi:
                lhi = high[j]
            if is_lo:
                llo = low[j]
        hi[i] = lhi; lo[i] = llo
    return hi, lo


def wilder_atr(t, period):
    pc = t["close"].shift(1)
    tr = pd.concat([t["high"] - t["low"], (t["high"] - pc).abs(), (t["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean().values.astype(float)


class MarketY(T.MarketX):
    """MarketX plus run_y(cfg): every trailing kind of hump_trail.py and of this module."""

    def _levels(self, name, kind, p, fast, slow):
        if kind in T.KIND:
            return super()._levels(name, kind, p, fast, slow)
        d = self._tf[name]
        key = (kind, int(p))
        if key not in d["lvl"]:
            t = d["t"]; hi, lo = d["hi"], d["lo"]; cl = t["close"].values.astype(float)
            if kind == "supertrend":
                per, mult = SUPERTREND[int(p)]
                a, b = supertrend_levels(hi, lo, cl, wilder_atr(t, per), mult)
            elif kind == "keltner":
                e = B.ema(t["close"], 20).values.astype(float).copy(); e[:20] = np.nan
                w = KELTNER[int(p)] * wilder_atr(t, 10)
                a, b = e + w, e - w
            elif kind == "bollinger":
                mid = t["close"].rolling(20).mean().values.astype(float); sd = t["close"].rolling(20).std(ddof=0).values.astype(float)
                a, b = mid + BOLLINGER[int(p)] * sd, mid - BOLLINGER[int(p)] * sd
            elif kind == "kijun":
                v = 0.5 * (t["high"].rolling(int(p)).max() + t["low"].rolling(int(p)).min())
                a = b = v.values.astype(float)
            elif kind == "pivots":
                a, b = pivot_levels(hi, lo, int(p))
            elif kind == "sma":
                a = b = t["close"].rolling(int(p)).mean().values.astype(float)
            elif kind == "donchian":
                a = t["high"].rolling(int(p)).max().values.astype(float); b = t["low"].rolling(int(p)).min().values.astype(float)
            elif kind == "htfcandle":
                htf = {v: k for k, v in B.TF_MIN.items()}[int(p)]
                assert B.TF_MIN[htf] > B.TF_MIN[name]
                hb = B.resample(self.m1, htf)
                hclose = hb.index.values + np.timedelta64(B.TF_MIN[htf], "m")       # close time of each HTF candle
                tclose = t.index.values + np.timedelta64(B.TF_MIN[name], "m")       # close time of each trigger bar
                q = np.searchsorted(hclose, tclose, side="right") - 1               # last HTF candle closed by then
                a = np.where(q >= 0, hb["high"].values.astype(float)[np.clip(q, 0, None)], np.nan)
                b = np.where(q >= 0, hb["low"].values.astype(float)[np.clip(q, 0, None)], np.nan)
            else:
                raise ValueError(kind)
            d["lvl"][key] = (a, b)
        return d["lvl"][key]

    def run_y(self, cfg):
        c = dict(H.DEFAULT); c.update(cfg)
        assert int(c["sl_mode"]) == 0 and int(c["tp_mode"]) in (0, 1)
        fast, slow = int(c["macd_fast"]), int(c["macd_slow"])
        hi, lo, macd, stk, row, bias, atr = self.tf(c["tf"], fast, slow, int(c["stoch_k"]))
        sg = H.signals(hi, lo, macd, stk, c["big_mult"], int(c["hist"]), int(c["big_min_bars"]), int(c["stoch_req"]),
                       int(c["pb_min_bars"]), c["pb_max_ratio"], c["break_ratio"], int(c["max_signals"]),
                       int(c["trend_max_bars"]), int(c["sides"]), int(c["classic"]), int(c["skip_big_pb"]),
                       c["stoch_lo"], c["stoch_hi"])
        if c.get("htf", "none") != "none" and len(sg):
            sg = sg[bias[(c["htf"], int(c["htf_ema"]))][sg[:, 0].astype(np.int64)] == sg[:, 1]]
        ix = sg[:, 0].astype(np.int64) if len(sg) else np.zeros(0, np.int64)
        sg = np.column_stack([sg, atr[ix]]) if len(sg) else np.zeros((0, 6))
        er = row[ix]
        kind = c.get("trail_kind", "R")
        tk = ALLKIND[kind]
        tb = self._tb(c["tf"])
        if tk == 7:
            lh, ll = self._levels(c["tf"], kind, c.get("trail_p", 0), fast, slow)
        else:
            lh = ll = np.zeros(1)
        aux = atr if tk == 8 else np.zeros(1)
        ts = 0.0 if tk == 0 else float(c["trail_start"])
        s0, s1 = H.SESSIONS[c["session"]]
        if c["weekend_close"]:
            wk = ((self.dow == 4) & (self.tod >= int(c["weekend_min"]))) | self.pre_gap
        else:
            wk = np.zeros(len(self.t), np.bool_)
        tr = simulate_y(sg, er, self.o, self.h, self.l, self.c, self.hs, self.tod, s0, s1, c["buf"], c["anticip"],
                        c["min_rr"], int(c["tp_mode"]), c["tp_rr"], ts, float(c["trail_dist"]),
                        c["max_spread"], c["min_risk"], c["max_risk"], c["slip"], c["comm"], int(c["delay"]),
                        int(c["trail_worst"]), wk, int(c["max_hold"]), int(c["eod"]), tk, tb, lh, ll, aux,
                        int(c.get("trail_closed", 1)))
        df = pd.DataFrame(tr, columns=["entry_row", "exit_row", "side", "r", "risk"])
        df["entry_time"] = self.t[df.entry_row.astype(int).values] if len(df) else pd.Series(dtype="datetime64[ns]")
        return df


# ----------------------------------------------------------------------------- self-test
def _selftest():
    import random
    os.environ.setdefault("HUMP_SPACE", "2")
    import hump_search as X
    mk = MarketY()
    rng = random.Random(9)
    stress = dict(trail_worst=1, delay=1, slip=0.10, comm=0.07, max_spread=5.0)
    old = [("none", 0), ("R", 0), ("points", 0), ("percent", 0), ("atr", 0), ("breakeven", 0), ("step", 0),
           ("candles", 3), ("ema", 21), ("psar", 0), ("hump", 0)]
    n_ok = 0
    for q in range(110):
        p = {k: rng.choice(v) for k, v in X.SPACE.items()}
        kind, tp_ = old[q % len(old)]
        c = dict(X.engine_cfg(dict(X.BASE, **p)), trail_kind=kind, trail_p=tp_)
        if kind in ("candles", "ema", "psar", "hump"):
            c["trail_start"] = rng.choice([0.0, 0.5, 1.0])
        elif c["trail_start"] <= 0:
            c["trail_start"] = 1.0
        for extra in ({}, stress):
            a = mk.run_x(dict(c, **extra)); b = mk.run_y(dict(c, **extra, trail_closed=0))
            cols = ["entry_row", "exit_row", "side"]
            assert len(a) == len(b) and np.array_equal(a[cols].values, b[cols].values) and np.allclose(a.r.values, b.r.values, rtol=0, atol=1e-12), (kind, p)
            n_ok += 1
    print("parity with hump_trail.simulate_x (trail_closed 0):", n_ok, "runs identical")

    # hand-made M1 path: one buy at bar 0, entry 100, stop 99 (risk 1), target 110; trigger bars = M1 bars
    def path(lows, highs, closes, kind, ts, td, worst=0, lvl=None, aux=None, comm=0.0, rr=10.0, closed=1):
        nb_ = len(lows); o = np.array([100.0] + list(closes[:-1])); h = np.array(highs, float); l = np.array(lows, float)
        cl = np.array(closes, float); hs = np.zeros(nb_); tod = np.arange(nb_) + 600
        sig = np.array([[0, 1, 99.0, 0.0, 0.0, 1.0]]); er = np.array([0]); wk = np.zeros(nb_, np.bool_)
        tbv = (np.arange(nb_) - 1).astype(np.int64)
        lv = np.full(nb_, np.nan) if lvl is None else np.array(lvl, float)
        ax = np.full(nb_, np.nan) if aux is None else np.array(aux, float)
        tr = simulate_y(sig, er, o, h, l, cl, hs, tod, 0, 1440, 0.0, 0.0, 0.0, 1, rr, ts, td, 1e9, 0.0, 1e9, 0.0, comm, 0,
                        worst, wk, 0, -1, ALLKIND[kind], tbv, lv, lv, ax, closed)
        return round(float(tr[0, 3]), 6), int(tr[0, 1])

    # chandelier 2 x ATR(=0.4): high 102 on bar 1 -> from bar 2 the stop is 102 - 0.8 = 101.2; bar 2 low 101.0 -> +1.2R
    assert path([100, 101.0, 101.0, 101.5], [100.5, 102.0, 101.9, 101.8], [100.4, 101.8, 101.5, 101.6], "chandelier", 0.0, 2.0,
                aux=[0.4, 0.4, 0.4, 0.4]) == (1.2, 2)
    # the best price of the bar itself is not used at that bar's open: with the high of 102 only on bar 2 the stop on bar 2 is 100.5 - 0.8
    assert path([100, 100.2, 101.0, 101.5], [100.5, 100.5, 102.0, 101.8], [100.4, 100.4, 101.8, 101.6], "chandelier", 0.0, 2.0,
                aux=[0.4, 0.4, 0.4, 0.4])[1] == 3
    # profit lock 50% from +1R: high 102 -> stop 101; next bar low 100.9 -> +1R
    assert path([100, 101.2, 100.9], [100.5, 102.0, 101.5], [100.4, 101.6, 101.0], "profitlock", 1.0, 0.5) == (1.0, 2)
    # time stop over 4 minutes: bar 2 stop = 99 + 2/4 = 99.5; low 99.4 -> exit 99.5 (-0.5R); without it the trade stays open
    assert path([100, 99.8, 99.4, 99.6], [100.5, 100.2, 100.0, 99.9], [100.1, 99.9, 99.7, 99.8], "timestop", 0.0, 4.0) == (-0.5, 2)
    assert path([100, 99.8, 99.4, 99.6], [100.5, 100.2, 100.0, 99.9], [100.1, 99.9, 99.7, 99.8], "none", 0.0, 0.0)[1] == 3
    # partial at +1R, rest to breakeven: high 101.2 (half out at 101), later low 99.9 -> rest at 100: 0.5*1 + 0.5*0 = 0.5R
    assert path([100, 100.6, 99.9], [100.5, 101.2, 100.8], [100.4, 100.9, 100.1], "partial", 1.0, 0.0) == (0.5, 2)
    # partial with a 0.5R trail on the rest: high 102 -> rest trails to 101.5; next bar low 101.4 -> 0.5*1 + 0.5*1.5 = 1.25R
    assert path([100, 100.8, 101.4], [100.5, 102.0, 101.9], [100.4, 101.8, 101.6], "partial", 1.0, 0.5) == (1.25, 2)
    # partial never reached: plain stop-out at -1R
    assert path([100, 99.5, 98.9], [100.5, 100.4, 99.6], [100.2, 99.6, 99.0], "partial", 1.0, 0.0) == (-1.0, 2)
    # commission is charged once on the whole size: 0.2 per unit -> 0.5*(1-0.2) + 0.5*(0-0.2) = 0.3R
    assert path([100, 100.6, 99.9], [100.5, 101.2, 100.8], [100.4, 100.9, 100.1], "partial", 1.0, 0.0, comm=0.2) == (0.3, 2)
    # the half-close level (+1R) and the target (+2R) are reached on the same bar: half at +1R, half at +2R = 1.5R
    assert path([100, 100.4, 101.5], [100.5, 102.5, 102.2], [100.4, 102.2, 101.9], "partial", 1.0, 0.0, rr=2.0) == (1.5, 1)
    # a target that lies before the half-close level: the whole position goes out at the target
    assert path([100, 100.4, 101.5], [100.5, 102.5, 102.2], [100.4, 102.2, 101.9], "partial", 3.0, 0.0, rr=2.0) == (2.0, 1)
    # closed-bar rule, dollar trailing from +1 with a distance of 0.5: bar 1 runs to 102 and closes at 101.4. The old
    # rule closes inside that bar at 102 - 0.5 = 101.5; the closed-bar rule sets 101.5 for bar 2, which opens at 101.4
    # (already through the stop) and is filled there
    bars = ([100, 100.3, 101.2], [100.5, 102.0, 101.6], [100.4, 101.4, 101.3])
    assert path(*bars, "points", 1.0, 0.5, closed=0) == (1.5, 1) and path(*bars, "points", 1.0, 0.5, closed=0, worst=1) == (1.5, 1)
    assert path(*bars, "points", 1.0, 0.5) == (1.4, 2) and path(*bars, "points", 1.0, 0.5, worst=1) == (1.4, 2)
    # the same with a bar 2 that opens above the stop and then falls through it: filled at the stop, 101.5
    bars = ([100, 100.3, 101.2], [100.5, 102.0, 101.9], [100.4, 101.7, 101.3])
    assert path(*bars, "points", 1.0, 0.5) == (1.5, 2) and path(*bars, "percent", 1.0, 0.5) == (1.5, 2)
    assert path(*bars, "atr", 1.0, 0.5) == (1.5, 2)                     # ATR at the signal = 1 in these paths
    # profit lock 50% from +1R, closed-bar: bar 1 high 102 locks 101 for bar 2 even though bar 1 itself closes at 100.8
    bars = ([100, 100.7, 100.6], [100.5, 102.0, 100.9], [100.4, 100.8, 100.7])
    assert path(*bars, "profitlock", 1.0, 0.5, closed=0) == (1.0, 1) and path(*bars, "profitlock", 1.0, 0.5) == (0.8, 2)
    # partial, closed-bar: the breakeven move still acts inside the half-close bar (close 99.9 under the entry -> rest
    # out at breakeven), while the 0.5R trail on the rest only holds from the next bar
    assert path([100, 99.8, 99.7], [100.5, 101.2, 100.1], [100.4, 99.9, 99.8], "partial", 1.0, 0.5) == (0.5, 1)
    assert path([100, 100.8, 101.3], [100.5, 102.0, 101.9], [100.4, 101.2, 101.6], "partial", 1.0, 0.5, closed=0) == (1.25, 1)
    assert path([100, 100.8, 101.1], [100.5, 102.0, 101.9], [100.4, 101.2, 101.6], "partial", 1.0, 0.5) == (1.1, 2)
    print("hand-made paths: ok")

    # one-minute resolution: each minute is cut into 6 pieces; a reference that walks the pieces (stop and target
    # tested piece by piece, stop moved only when a minute has closed) must give the same exit as simulate_y on the
    # one-minute bars under the closed-bar rule. The old rule fails this on a large share of the paths.
    def fine(side, entry, sl, kind, ts, td, unit, so, sh, slo, sc, per):
        risk = abs(entry - sl); stop = sl; nmin = len(so) // per
        for mnt in range(nmin):
            for q in range(mnt * per, (mnt + 1) * per):
                if side > 0:
                    if so[q] <= stop: return (so[q] - entry) / risk, mnt
                    if slo[q] <= stop: return (stop - entry) / risk, mnt
                else:
                    if so[q] >= stop: return (entry - so[q]) / risk, mnt
                    if sh[q] >= stop: return (entry - stop) / risk, mnt
            ext = sh[mnt * per:(mnt + 1) * per].max() if side > 0 else slo[mnt * per:(mnt + 1) * per].min()
            fav = (ext - entry) * side
            if kind == "profitlock":
                if fav >= ts * risk:
                    cand = entry + side * td * fav
                    stop = max(stop, cand) if side > 0 else min(stop, cand)
            elif fav >= ts * unit:
                cand = ext - side * td * unit
                stop = max(stop, cand) if side > 0 else min(stop, cand)
        return (sc[-1] - entry) * side / risk, nmin - 1

    rs2 = np.random.default_rng(11); per, nmin = 6, 45; same = {0: 0, 1: 0}; total = 0
    for q in range(1600):
        step = rs2.normal(0.02, 0.25, per * nmin)                       # a drifting walk in pieces of a minute
        side = 1 if q % 2 == 0 else -1
        sc = 100.0 + side * np.cumsum(step); so = np.concatenate([[100.0], sc[:-1]])
        wig = np.abs(rs2.normal(0, 0.12, (2, per * nmin)))
        sh = np.maximum(so, sc) + wig[0]; slo = np.minimum(so, sc) - wig[1]
        o1 = so[::per]; c1 = sc[per - 1::per]; h1 = sh.reshape(nmin, per).max(axis=1); l1 = slo.reshape(nmin, per).min(axis=1)
        kind = ("points", "percent", "atr", "profitlock")[q % 4]
        ts = float(rs2.choice([0.5, 1.0, 2.0])); td = float(rs2.choice([0.25, 0.5, 1.0])) if kind != "profitlock" else float(rs2.choice([0.3, 0.5, 0.7]))
        atr = 0.8; unit = {"points": 1.0, "percent": 1.0, "atr": atr, "profitlock": 1.0}[kind]      # 1% of 100 = 1.0
        sig = np.array([[0, side, 100.0 - side * 1.5, 0.0, 0.0, atr]]); zero = np.zeros(nmin)
        ref = fine(side, 100.0, 100.0 - side * 1.5, kind, ts, td, unit, so, sh, slo, sc, per)
        total += 1
        for closed in (0, 1):
            tr = simulate_y(sig, np.array([0]), o1, h1, l1, c1, zero, np.arange(nmin) + 600, 0, 1440, 0.0, 0.0, 0.0, 1, 1e6,
                            ts, td, 1e9, 0.0, 1e9, 0.0, 0.0, 0, 0, np.zeros(nmin, np.bool_), 0, -1, ALLKIND[kind],
                            (np.arange(nmin) - 1).astype(np.int64), np.full(nmin, np.nan), np.full(nmin, np.nan), np.full(nmin, np.nan), closed)
            ok = abs(tr[0, 3] - ref[0]) < 1e-9 and int(tr[0, 1]) == ref[1]
            same[closed] += ok
            assert ok or closed == 0, (q, kind, side, ts, td, tr[0, 3], tr[0, 1], ref)
    assert same[1] == total and same[0] < 0.9 * total, same
    print(f"one-minute resolution: closed-bar rule equals the walk in pieces of a minute on {same[1]} of {total} paths; "
          f"the old rule on {same[0]}")

    # level builders against straightforward references on real bars
    d = mk._tf[list(mk._tf)[0]]; name = list(mk._tf)[0]; t = d["t"]; mk._tb(name)
    hi, lo = d["hi"], d["lo"]
    a, b = pivot_levels(hi[:400], lo[:400], 2)
    for i in range(10, 400):
        j = max([q for q in range(2, i - 1) if hi[q] > max(hi[q - 2], hi[q - 1], hi[q + 1], hi[q + 2])], default=None)
        assert (j is None and np.isnan(a[i])) or a[i] == hi[j], i
    # SuperTrend after a gap up: bar 2 closes at 105, under the support line at 108 -> the up-trend ends, resistance 109
    h3, l3 = supertrend_levels(np.array([100.5, 111.0, 110.0]), np.array([99.5, 109.0, 104.0]), np.array([100.0, 110.5, 105.0]),
                               np.ones(3), 2.0)
    assert np.isnan(l3[2]) and h3[2] == 109.0 and l3[1] == 108.0, (h3, l3)
    sa, sb = mk._levels(name, "supertrend", 0, 12, 26)
    cl = t["close"].values
    below = np.nanmean((sb <= cl)[~np.isnan(sb)]); above = np.nanmean((sa >= cl)[~np.isnan(sa)])
    assert np.all(np.isnan(sa) | np.isnan(sb)) and below > 0.99 and above > 0.99, (below, above)
    print(f"level builders: pivots match a direct search; SuperTrend support below the close on {below:.1%} of up bars, "
          f"resistance above it on {above:.1%} of down bars")

    # level timing: the level used on a one-minute row must come out the same when the series ends at that row.
    # (The scramble test below has no power against a level read one trigger bar early; this one does.)
    lv_kinds = [("supertrend", 1), ("keltner", 1), ("bollinger", 1), ("kijun", 26), ("pivots", 3), ("sma", 20), ("donchian", 20),
                ("htfcandle", 60), ("candles", 3), ("ema", 21), ("psar", 0), ("hump", 0)]
    rs3 = np.random.default_rng(21); n_cmp = 0; n_shift = 0
    for tfn in ("M3", "M10"):
        mk.tf(tfn, 12, 26, 7); full_tb = mk._tb(tfn)
        full = {kd: mk._levels(tfn, kd[0], kd[1], 12, 26) for kd in lv_kinds}
        for j in sorted(rs3.integers(60000, len(mk.m1) - 1, 6)):
            part = MarketY(m1=mk.m1.iloc[:j + 1], half_spread=mk.hs[:j + 1])
            part.tf(tfn, 12, 26, 7); ptb = part._tb(tfn)
            i_full, i_part = full_tb[j], ptb[j]
            assert i_full == i_part and i_full >= 1, (tfn, j)
            for kd in lv_kinds:
                a_, b_ = part._levels(tfn, kd[0], kd[1], 12, 26)
                for cut_arr, full_arr in ((a_, full[kd][0]), (b_, full[kd][1])):
                    x, y = cut_arr[i_part], full_arr[i_full]
                    assert (x == y) or (x != x and y != y), (tfn, j, kd, x, y)
                    n_cmp += 1
                    z = full_arr[i_full + 1] if i_full + 1 < len(full_arr) else np.nan    # the level one bar early
                    n_shift += not ((x == z) or (x != x and z != z))
    assert n_shift > 0.25 * n_cmp, (n_shift, n_cmp)
    print(f"level timing: {n_cmp} levels identical when the series is cut at the row that uses them; "
          f"a level read one bar early would differ in {n_shift}")

    # look-ahead check: scramble everything after a cut, earlier-closed trades must not change
    m1 = mk.m1.copy(); cut = len(m1) * 2 // 3
    rs = np.random.default_rng(4)
    m2 = m1.copy(); fac = 1.0 + 0.05 * rs.standard_normal(len(m1) - cut)
    for col in ("open", "high", "low", "close"):
        m2.iloc[cut:, m2.columns.get_loc(col)] = m1[col].values[cut:] * fac
    m2["high"] = m2[["open", "high", "low", "close"]].max(axis=1); m2["low"] = m2[["open", "high", "low", "close"]].min(axis=1)
    mk1 = MarketY(m1=m1, half_spread=mk.hs); mk2 = MarketY(m1=m2, half_spread=mk.hs)
    kinds = [("chandelier", 0), ("profitlock", 0), ("timestop", 0), ("partial", 0), ("supertrend", 1), ("keltner", 1), ("bollinger", 0),
             ("kijun", 26), ("pivots", 3), ("sma", 20), ("donchian", 20), ("htfcandle", 60)]
    checked = 0
    for q in range(60):
        p = {k: rng.choice(v) for k, v in X.SPACE.items()}
        if p["tf"] in ("M15",) and kinds[q % len(kinds)][0] == "htfcandle":
            p["tf"] = "M5"
        kind, tp_ = kinds[q % len(kinds)]
        c = dict(X.engine_cfg(dict(X.BASE, **p)), trail_kind=kind, trail_p=tp_)
        c["trail_start"] = {"timestop": 0.0, "partial": 1.0, "profitlock": 1.0}.get(kind, rng.choice([0.0, 0.5, 1.0]))
        c["trail_dist"] = {"chandelier": 2.0, "profitlock": 0.5, "timestop": 120.0, "partial": 0.5}.get(kind, 0.5)
        a = mk1.run_y(c); b = mk2.run_y(c)
        ea = a[a.exit_row < cut - 1]; eb = b[b.exit_row < cut - 1]
        cols = ["entry_row", "exit_row", "side"]
        assert len(ea) == len(eb) and np.array_equal(ea[cols].values, eb[cols].values) and np.allclose(ea.r.values, eb.r.values, atol=1e-12), (kind, p)
        checked += len(ea)
    print("no look-ahead: 60 setups,", checked, "earlier trades unchanged after scrambling later prices")


if __name__ == "__main__":
    _selftest()
