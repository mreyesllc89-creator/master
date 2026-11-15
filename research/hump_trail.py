#!/usr/bin/env python3
"""
Extended trailing stops for the hump (Loma) backtest: every standard family, on the same M1 path
and with the same costs as hump_engine.simulate.

trail_kind (config key "trail_kind"):
  none       no trailing
  R          from the favourable extreme, start / distance in multiples of the initial risk   (engine trail_mode 0)
  points     the same in price units (USD)                                                    (engine trail_mode 1)
  percent    the same in percent of the entry price                                           (engine trail_mode 2)
  atr        the same in multiples of ATR(14) of the trigger timeframe at the signal          (engine trail_mode 3)
  breakeven  once the profit reaches trail_start x risk the stop goes to entry + trail_dist x risk, then stays
  step       ratchet: each time the profit reaches k x trail_start x risk the stop goes to entry + (k-1) x trail_start x risk
  candles    stop beyond the highest high / lowest low of the last trail_p closed trigger bars
  ema        stop beyond the EMA(trail_p) of the trigger closes
  psar       stop at the Parabolic SAR of the trigger timeframe (trail_p: 0 = 0.02/0.2, 1 = 0.01/0.1, 2 = 0.04/0.2)
  hump       stop beyond the extreme of the most recent completed pullback hump (positive hump high for sells,
             negative hump low for buys), with the setup's own MACD
For the four level-based kinds (candles, ema, psar, hump) the level comes from trigger bars that CLOSED at or
before the open of each M1 bar (no look-ahead); the stop is level +/- the setup's SL buffer (+ spread for
sells), only ever tightened, and it starts once the profit has reached trail_start x risk (0 = from the
one-minute bar after the entry bar).
The first four kinds reproduce hump_engine.simulate exactly (see the self-test in __main__).
"""
import os, sys
import numba as nb, numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_engine as H, xlzc_backtest as B

KIND = {"none": 0, "R": 1, "points": 2, "percent": 3, "atr": 4, "breakeven": 5, "step": 6,
        "candles": 7, "ema": 7, "psar": 7, "hump": 7}
PSAR = {0: (0.02, 0.2), 1: (0.01, 0.1), 2: (0.04, 0.2)}


@nb.njit(cache=True)
def simulate_x(sig, entry_row, o, h, l, c, hs, tod, s0, s1, buf, anticip, min_rr, tp_mode, tp_rr,
               trail_start, trail_dist, max_spread, min_risk, max_risk, slip, comm, delay, trail_worst, wk,
               max_hold, eod, trail_kind, tb, lvl_hi, lvl_lo):
    """hump_engine.simulate (hump stop, previous-hump or fixed-RR target) with the extended trailing.
    trail_kind: 0 off, 1 R, 2 points, 3 percent, 4 ATR, 5 breakeven, 6 step, 7 level series.
    tb[j]: index of the last trigger bar closed at or before the open of M1 bar j (-1: none).
    lvl_hi / lvl_lo: per trigger bar, resistance for sells / support for buys (NaN: no level)."""
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
            act = trail_start <= 0.0                      # level trailing: active from the start when no threshold
            while j < n:
                ah = h[j] + hs[j]; al = l[j] + hs[j]; ao = o[j] + hs[j]
                if trail_kind == 7 and act and j > e:     # level known at this bar's open
                    i = tb[j]
                    if i >= 0:
                        lv = lvl_hi[i]
                        if lv == lv:
                            cand = lv + buf + hs[j]
                            if cand < stop:
                                stop = cand
                if ao >= stop:
                    px = ao + slip; break
                if ah >= stop:
                    px = stop + slip; break
                if al <= tp:
                    px = min(tp, ao); break
                fav = entry - al
                if trail_kind >= 1 and trail_kind <= 4:
                    if trail_start > 0 and fav >= trail_start * unit:
                        cand = al + trail_dist * unit
                        if cand < stop:
                            stop = cand
                            if c[j] + hs[j] >= stop or (trail_worst == 1 and ah >= stop):
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
                elif trail_kind == 7:
                    if (not act) and fav >= trail_start * risk:
                        act = True                         # the level is followed from the next bar on
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
            while j < n:
                bh = h[j] - hs[j]; bl = l[j] - hs[j]; bo = o[j] - hs[j]
                if trail_kind == 7 and act and j > e:
                    i = tb[j]
                    if i >= 0:
                        lv = lvl_lo[i]
                        if lv == lv:
                            cand = lv - buf - hs[j]
                            if cand > stop:
                                stop = cand
                if bo <= stop:
                    px = bo - slip; break
                if bl <= stop:
                    px = stop - slip; break
                if bh >= tp:
                    px = max(tp, bo); break
                fav = bh - entry
                if trail_kind >= 1 and trail_kind <= 4:
                    if trail_start > 0 and fav >= trail_start * unit:
                        cand = bh - trail_dist * unit
                        if cand > stop:
                            stop = cand
                            if c[j] - hs[j] <= stop or (trail_worst == 1 and bl <= stop):
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
                elif trail_kind == 7:
                    if (not act) and fav >= trail_start * risk:
                        act = True
                if wk[j]:
                    px = c[j] - hs[j] - slip; break
                if (max_hold > 0 and j - e >= max_hold) or \
                        (eod >= 0 and j > e and tod[j] >= eod and (tod[j - 1] < eod or tod[j - 1] > tod[j])):
                    px = c[j] - hs[j] - slip; break
                j += 1
            if px != px:
                j = n - 1; px = c[j] - hs[j]
            r = (px - entry - comm) / risk
        out[m, 0] = e; out[m, 1] = j; out[m, 2] = side; out[m, 3] = r; out[m, 4] = risk
        m += 1
        busy = j
    return out[:m]


@nb.njit(cache=True)
def psar_levels(high, low, step, mx):
    """Parabolic SAR for the NEXT bar, known at each bar's close. Returns (resistance, support): the SAR
    when it is above price (down mode) / below price (up mode), NaN otherwise."""
    n = len(high)
    hi = np.full(n, np.nan); lo = np.full(n, np.nan)
    if n < 3:
        return hi, lo
    up = high[1] >= high[0]
    ep = high[1] if up else low[1]
    s = min(low[0], low[1]) if up else max(high[0], high[1])
    af = step
    for i in range(2, n):
        if up:
            if low[i] < s:                                 # reversal to down mode
                up = False; s = ep; ep = low[i]; af = step
            elif high[i] > ep:
                ep = high[i]; af = min(af + step, mx)
        else:
            if high[i] > s:                                # reversal to up mode
                up = True; s = ep; ep = high[i]; af = step
            elif low[i] < ep:
                ep = low[i]; af = min(af + step, mx)
        s = s + af * (ep - s)
        if up:
            s = min(s, low[i], low[i - 1]); lo[i] = s
        else:
            s = max(s, high[i], high[i - 1]); hi[i] = s
    return hi, lo


@nb.njit(cache=True)
def hump_levels(high, low, macd):
    """Per bar: high of the most recent COMPLETED positive hump (resistance) and low of the most recent
    completed negative hump (support). A hump is complete on the first bar of the next hump."""
    n = len(macd)
    hi = np.full(n, np.nan); lo = np.full(n, np.nan)
    cs = 0; chi = -1e300; clo = 1e300; lhi = np.nan; llo = np.nan
    for i in range(n):
        v = macd[i]
        if v == v:
            s = 1 if v >= 0 else -1
            if cs == 0:
                cs = s
            if s != cs:
                if cs > 0:
                    lhi = chi
                else:
                    llo = clo
                cs = s; chi = -1e300; clo = 1e300
            if high[i] > chi:
                chi = high[i]
            if low[i] < clo:
                clo = low[i]
        hi[i] = lhi; lo[i] = llo
    return hi, lo


class MarketX(H.Market):
    """hump_engine.Market plus run_x(cfg): the same signals, the extended trailing kinds."""

    def _tb(self, name):
        d = self._tf[name]
        if "tb" not in d:
            closed = d["t"].index.values + np.timedelta64(B.TF_MIN[name], "m")      # close time of each trigger bar
            d["tb"] = (np.searchsorted(closed, self.t, side="right") - 1).astype(np.int64)
            d["lvl"] = {}
        return d["tb"]

    def _levels(self, name, kind, p, fast, slow):
        d = self._tf[name]
        key = (kind, int(p), fast, slow) if kind == "hump" else (kind, int(p))
        if key not in d["lvl"]:
            hi, lo = d["hi"], d["lo"]
            if kind == "candles":
                t = d["t"]
                a = t["high"].rolling(int(p)).max().values.astype(float); b = t["low"].rolling(int(p)).min().values.astype(float)
            elif kind == "ema":
                e = B.ema(d["t"]["close"], int(p)).values.astype(float).copy()
                e[:int(p)] = np.nan
                a, b = e, e
            elif kind == "psar":
                st, mx = PSAR[int(p)]
                a, b = psar_levels(hi, lo, st, mx)
            elif kind == "hump":
                a, b = hump_levels(hi, lo, d["macd"][(fast, slow)])
            else:
                raise ValueError(kind)
            d["lvl"][key] = (a, b)
        return d["lvl"][key]

    def run_x(self, cfg):
        c = dict(H.DEFAULT); c.update(cfg)
        assert int(c["sl_mode"]) == 0 and int(c["tp_mode"]) in (0, 1), "run_x supports the hump stop and tp_mode 0/1"
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
        tk = KIND[kind]
        tb = self._tb(c["tf"])
        if tk == 7:
            lh, ll = self._levels(c["tf"], kind, c.get("trail_p", 0), fast, slow)
        else:
            lh = ll = np.zeros(1)
        ts = 0.0 if tk == 0 else float(c["trail_start"])
        s0, s1 = H.SESSIONS[c["session"]]
        if c["weekend_close"]:
            wk = ((self.dow == 4) & (self.tod >= int(c["weekend_min"]))) | self.pre_gap
        else:
            wk = np.zeros(len(self.t), np.bool_)
        tr = simulate_x(sg, er, self.o, self.h, self.l, self.c, self.hs, self.tod, s0, s1, c["buf"], c["anticip"],
                        c["min_rr"], int(c["tp_mode"]), c["tp_rr"], ts, float(c["trail_dist"]),
                        c["max_spread"], c["min_risk"], c["max_risk"], c["slip"], c["comm"], int(c["delay"]),
                        int(c["trail_worst"]), wk, int(c["max_hold"]), int(c["eod"]), tk, tb, lh, ll)
        df = pd.DataFrame(tr, columns=["entry_row", "exit_row", "side", "r", "risk"])
        df["entry_time"] = self.t[df.entry_row.astype(int).values] if len(df) else pd.Series(dtype="datetime64[ns]")
        return df


# ----------------------------------------------------------------------------- self-test
def _selftest():
    """1) kinds R / points / percent / atr reproduce hump_engine.simulate trade for trade on random setups,
       base and stress. 2) hand-made paths for breakeven, step and level trailing. 3) no look-ahead:
       corrupting prices after a cut leaves every earlier-closed trade unchanged."""
    import random
    os.environ.setdefault("HUMP_SPACE", "2")
    import hump_search as X
    mk = MarketX()
    rng = random.Random(5)
    stress = dict(trail_worst=1, delay=1, slip=0.10, comm=0.07, max_spread=5.0)
    n_ok = 0
    for _ in range(120):
        p = {k: rng.choice(v) for k, v in X.SPACE.items()}
        c = X.engine_cfg(dict(X.BASE, **p))
        for mode, kind in ((0, "R"), (1, "points"), (2, "percent"), (3, "atr")):
            for extra in ({}, stress):
                cc = dict(c, trail_mode=mode, **extra)
                a = mk.run(cc); b = mk.run_x(dict(cc, trail_kind=kind))
                assert len(a) == len(b) and np.array_equal(a[["entry_row", "exit_row", "side"]].values, b[["entry_row", "exit_row", "side"]].values) \
                    and np.allclose(a.r.values, b.r.values, rtol=0, atol=1e-12), (p, mode, extra)
                n_ok += 1
        a = mk.run(dict(c, trail_start=0.0)); b = mk.run_x(dict(c, trail_kind="none"))
        assert len(a) == len(b) and np.allclose(a.r.values, b.r.values, rtol=0, atol=1e-12)
    print("parity with hump_engine.simulate:", n_ok, "runs identical")

    # hand-made M1 path: one buy at bar 0, entry 100, stop 99 (risk 1), target 110
    def path(lows, highs, closes, kind, ts, td, worst=0, lvl=None, tbv=None):
        nb_ = len(lows); o = np.array([100.0] + list(closes[:-1])); h = np.array(highs, float); l = np.array(lows, float)
        cl = np.array(closes, float); hs = np.zeros(nb_); tod = np.arange(nb_) + 600
        sig = np.array([[0, 1, 99.0, 0.0, 0.0, 1.0]]); er = np.array([0])
        wk = np.zeros(nb_, np.bool_)
        tbv = np.arange(nb_) - 1 if tbv is None else np.array(tbv)
        lv = np.full(nb_, np.nan) if lvl is None else np.array(lvl, float)
        tr = simulate_x(sig, er, o, h, l, cl, hs, tod, 0, 1440, 0.0, 0.0, 0.0, 1, 10.0, ts, td, 1e9, 0.0, 1e9, 0.0, 0.0, 0,
                        worst, wk, 0, -1, KIND[kind], tbv.astype(np.int64), lv, lv)
        return round(float(tr[0, 3]), 6), int(tr[0, 1])

    # breakeven at +1R with 0.2R locked: price goes to 101.2, then falls to 99.5 -> exit at 100.2 (+0.2R) on bar 2
    assert path([100, 100.8, 99.5], [100.5, 101.2, 101.0], [100.4, 101.0, 99.6], "breakeven", 1.0, 0.2) == (0.2, 2)
    # without trailing the same path stays open (closed at the last close 99.6 -> -0.4R)
    assert path([100, 100.8, 99.5], [100.5, 101.2, 101.0], [100.4, 101.0, 99.6], "none", 0.0, 0.0) == (-0.4, 2)
    # step 1R: high 102.3 -> stop to entry + 1R = 101; next bar low 100.9 -> exit 101 (+1R)
    assert path([100, 101.5, 100.9], [100.5, 102.3, 102.0], [100.4, 102.0, 101.2], "step", 1.0, 0.0) == (1.0, 2)
    # step: worst case, the same bar that makes 102.3 also dips to 100.9 -> exit +1R on bar 1; base case keeps it
    assert path([100, 100.9, 101.5], [100.5, 102.3, 102.0], [100.4, 102.0, 101.6], "step", 1.0, 0.0, worst=1) == (1.0, 1)
    assert path([100, 100.9, 101.5], [100.5, 102.3, 102.0], [100.4, 102.0, 101.6], "step", 1.0, 0.0, worst=0)[1] == 2
    # level trailing: support 100.6 known from bar 2's open (tb[2] = 1, level index 1) -> bar 2 low 100.5 -> exit 100.6
    assert path([100, 100.9, 100.5], [100.5, 101.4, 101.3], [100.4, 101.2, 100.8], "candles", 0.0, 0.0,
                lvl=[np.nan, 100.6, 100.6]) == (0.6, 2)
    # the level of the bar that is still forming is NOT used: support appears only at index 2 (closed after bar 2 opens)
    assert path([100, 100.9, 100.5], [100.5, 101.4, 101.3], [100.4, 101.2, 100.8], "candles", 0.0, 0.0,
                lvl=[np.nan, np.nan, 100.6])[0] == 0.8
    # level trailing with a 1R activation: not active until +1R was reached on an earlier bar
    assert path([100, 100.9, 100.5], [100.5, 100.95, 100.9], [100.4, 100.9, 100.8], "candles", 1.0, 0.0,
                lvl=[np.nan, 100.6, 100.6])[0] == 0.8
    print("hand-made paths: ok")

    # look-ahead check on real data: scramble everything after a cut, earlier-closed trades must not change
    m1 = mk.m1.copy(); cut = len(m1) * 2 // 3
    rs = np.random.default_rng(3)
    m2 = m1.copy()
    fac = 1.0 + 0.05 * rs.standard_normal(len(m1) - cut)
    for col in ("open", "high", "low", "close"):
        m2.iloc[cut:, m2.columns.get_loc(col)] = m1[col].values[cut:] * fac
    m2["high"] = m2[["open", "high", "low", "close"]].max(axis=1); m2["low"] = m2[["open", "high", "low", "close"]].min(axis=1)
    mk2 = MarketX(m1=m2, half_spread=mk.hs)
    mk1 = MarketX(m1=m1, half_spread=mk.hs)
    kinds = [("candles", 3), ("ema", 21), ("psar", 0), ("hump", 0), ("breakeven", 0), ("step", 0), ("R", 0), ("atr", 0)]
    checked = 0
    for q in range(40):
        p = {k: rng.choice(v) for k, v in X.SPACE.items()}
        kind, tp_ = kinds[q % len(kinds)]
        c = dict(X.engine_cfg(dict(X.BASE, **p)), trail_kind=kind, trail_p=tp_, trail_start=rng.choice([0.0, 0.5, 1.0]) if KIND[kind] == 7 else 1.0,
                 trail_dist=0.5)
        a = mk1.run_x(c); b = mk2.run_x(c)
        ea = a[a.exit_row < cut - 1]; eb = b[b.exit_row < cut - 1]
        cols = ["entry_row", "exit_row", "side"]
        assert len(ea) == len(eb) and np.array_equal(ea[cols].values, eb[cols].values) and np.allclose(ea.r.values, eb.r.values, atol=1e-12), (kind, p)
        checked += len(ea)
    print("no look-ahead: 40 setups,", checked, "earlier trades unchanged after scrambling later prices")


if __name__ == "__main__":
    _selftest()
