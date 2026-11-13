#!/usr/bin/env python3
"""
"Loma" (MACD hump) method, from the trader's video review of the XLZC EA (Nov 2026).

Vocabulary: a HUMP is a run of consecutive closed bars with the MACD main line on one side of
zero. Each hump has a peak (largest |MACD|), a bar count, the price extreme made while it lasted
and the Stochastic extreme reached.

Rules
  1 Trend comes first. A BIG hump below zero (peak >= big_mult x the median peak of the last
    `hist` humps, >= big_min_bars bars and, if stoch_req, Stochastic reached <= 20 during it)
    defines a BEARISH trend; the mirror above zero (Stochastic >= 80) a BULLISH trend. With no
    big hump in force the market is LINEAR: no trades.
  2 Trend break: an opposite hump whose peak reaches break_ratio x the big hump's peak ends
    the trend (it starts the other trend only if it is itself big).
  3 Sell signal (bearish trend): a small pullback hump ABOVE zero (>= pb_min_bars bars, peak
    <= pb_max_ratio x the big hump's peak), then the first bar with MACD below zero. A bare
    touch of zero without a hump is not a signal.
  4 SL above the highest high of the pullback hump (+ buffer + spread). No hump, no SL, no trade.
  5 TP at the low made by the previous hump below zero, anticipated by `anticip` of the
    distance. Skipped when reward < min_rr x risk.
  6 Only the first `max_signals` signals after a big hump are taken (the third is weak); a
    new big hump in the trend direction resets the count. The trend also lapses after
    trend_max_bars bars without a new big hump.
  7 Buys are the exact mirror.

Entries fill at the next bar's open (bid for sells, ask for buys). Chart prices are FTMO mid
quotes: bid = mid - spread/2, ask = mid + spread/2. Exits are tested on the M1 path; when a
stop and a target fall inside the same M1 bar the stop is taken.
"""
import os
import sys

import numba as nb
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xlzc_backtest as B  # noqa: E402

DATA = os.environ.get("HUMP_DATA", "/workspace/gianniskas/mt5-m1-bars-us500-eurusd-xauusd")


@nb.njit(cache=True)
def signals(hi, lo, macd, stk, big_mult, hist, big_min_bars, stoch_req, pb_min_bars, pb_max_ratio,
            break_ratio, max_signals, trend_max_bars, sides, classic, skip_big_pb):
    """Return rows (signal_bar, side, sl_ref, tp_ref, hump_peak_ratio). side +1 buy, -1 sell.
    classic=1: every zero-cross in the allowed direction is a signal (old XLZC trigger) with the
    same SL/TP construction, for comparison."""
    n = len(macd)
    out = np.empty((n // 2 + 8, 5))
    m = 0
    peaks = np.zeros(hist); pk_n = 0; pk_i = 0
    # current hump
    cs = 0; c_n = 0; c_peak = 0.0; c_hi = -1e300; c_lo = 1e300; c_smin = 101.0; c_smax = -1.0
    # previous completed hump (any size) of each sign: price extremes
    last_neg_lo = np.nan; last_pos_hi = np.nan
    # trend
    trend = 0; anchor_peak = 0.0; anchor_bar = -1; used = 0
    for i in range(n):
        v = macd[i]
        if v != v:
            continue
        s = 1 if v >= 0 else -1
        if cs == 0:
            cs = s
        if s != cs:
            # ---- hump cs just completed at bar i-1; bar i is the first bar of the new hump
            med = 0.0
            if pk_n >= 5:
                med = np.median(peaks[:min(pk_n, hist)])
            big = pk_n >= 5 and c_peak >= big_mult * med and c_n >= big_min_bars
            if big and stoch_req == 1:
                big = (c_smin <= 20.0) if cs < 0 else (c_smax >= 80.0)
            # signal check uses the trend in force BEFORE this hump is classified
            took = False
            if classic == 1:
                if cs > 0 and s < 0 and (sides == 0 or sides == -1) and last_neg_lo == last_neg_lo:
                    out[m, 0] = i; out[m, 1] = -1; out[m, 2] = max(c_hi, hi[i]); out[m, 3] = last_neg_lo; out[m, 4] = 0
                    m += 1
                if cs < 0 and s > 0 and (sides == 0 or sides == 1) and last_pos_hi == last_pos_hi:
                    out[m, 0] = i; out[m, 1] = 1; out[m, 2] = min(c_lo, lo[i]); out[m, 3] = last_pos_hi; out[m, 4] = 0
                    m += 1
            else:
                alive = trend != 0 and used < max_signals and (i - anchor_bar) <= trend_max_bars
                if skip_big_pb == 1 and big:
                    alive = False        # the pullback hump is itself a big opposite hump: trend change, no signal
                if alive and trend == -1 and cs > 0 and s < 0 and (sides == 0 or sides == -1):
                    if c_n >= pb_min_bars and c_peak <= pb_max_ratio * anchor_peak and last_neg_lo == last_neg_lo:
                        out[m, 0] = i; out[m, 1] = -1; out[m, 2] = max(c_hi, hi[i]); out[m, 3] = last_neg_lo
                        out[m, 4] = c_peak / anchor_peak
                        m += 1; used += 1; took = True
                if alive and trend == 1 and cs < 0 and s > 0 and (sides == 0 or sides == 1):
                    if c_n >= pb_min_bars and c_peak <= pb_max_ratio * anchor_peak and last_pos_hi == last_pos_hi:
                        out[m, 0] = i; out[m, 1] = 1; out[m, 2] = min(c_lo, lo[i]); out[m, 3] = last_pos_hi
                        out[m, 4] = c_peak / anchor_peak
                        m += 1; used += 1; took = True
            # ---- classify the completed hump
            if big:
                trend = cs; anchor_peak = c_peak; anchor_bar = i - 1; used = 0
            elif trend != 0 and cs == -trend and c_peak >= break_ratio * anchor_peak:
                trend = 0                                  # trend break -> linear
            if cs < 0:
                last_neg_lo = c_lo
            else:
                last_pos_hi = c_hi
            peaks[pk_i] = c_peak; pk_i = (pk_i + 1) % hist; pk_n += 1
            cs = s; c_n = 0; c_peak = 0.0; c_hi = -1e300; c_lo = 1e300; c_smin = 101.0; c_smax = -1.0
        c_n += 1
        a = abs(v)
        if a > c_peak: c_peak = a
        if hi[i] > c_hi: c_hi = hi[i]
        if lo[i] < c_lo: c_lo = lo[i]
        sv = stk[i]
        if sv == sv:
            if sv < c_smin: c_smin = sv
            if sv > c_smax: c_smax = sv
        # a hump still forming that already breaks the trend ends it at once
        if trend != 0 and cs == -trend and c_peak >= break_ratio * anchor_peak:
            trend = 0
    return out[:m]


@nb.njit(cache=True)
def simulate(sig, entry_row, o, h, l, c, hs, tod, s0, s1, buf, anticip, min_rr, tp_mode, tp_rr,
             trail_start, trail_dist, max_spread, min_risk, max_risk, slip, comm, delay, trail_worst, wk):
    """Sequential trades on the M1 path. Returns rows (entry_row, exit_row, side, R, risk)."""
    n = len(o)
    out = np.empty((len(sig), 5))
    m = 0
    busy = -1
    for k in range(len(sig)):
        e = entry_row[k]
        if e >= 0:
            e += delay                                     # stress: enter this many M1 bars late
        if e < 0 or e >= n or e <= busy:
            continue
        if not (s0 <= tod[e] < s1) if s0 < s1 else not (tod[e] >= s0 or tod[e] < s1):
            continue
        sp = 2 * hs[e]
        if sp > max_spread:
            continue
        if wk[e]:                                          # no new trades in the pre-weekend window
            continue
        side = int(sig[k, 1])
        if side < 0:
            entry = o[e] - hs[e] - slip                    # sell at bid (minus slippage)
            sl = sig[k, 2] + buf + hs[e]                   # ask-side stop above the hump high
            risk = sl - entry
            if risk < min_risk or risk > max_risk:
                continue
            if tp_mode == 0:
                ref = sig[k, 3]
                tp = ref + anticip * (entry - ref) + hs[e]  # ask-side target, a little before the low
            else:
                tp = entry - tp_rr * risk
            if entry - tp < min_rr * risk:
                continue
            best = 1e300; stop = sl; px = np.nan; j = e
            while j < n:
                ah = h[j] + hs[j]; al = l[j] + hs[j]; ao = o[j] + hs[j]
                if ao >= stop:
                    px = ao + slip; break
                if ah >= stop:
                    px = stop + slip; break
                if al <= tp:
                    px = min(tp, ao); break
                if trail_start > 0 and entry - al >= trail_start * risk:
                    cand = al + trail_dist * risk
                    if cand < stop:
                        stop = cand
                        if c[j] + hs[j] >= stop or (trail_worst == 1 and ah >= stop):
                            px = stop + slip; break            # same-bar hit (worst: any touch after the low)
                if wk[j]:                                  # close before the weekend at this bar's close
                    px = c[j] + hs[j] + slip; break
                j += 1
            if px != px:
                j = n - 1; px = c[j] + hs[j]
            r = (entry - px - comm) / risk
        else:
            entry = o[e] + hs[e] + slip                    # buy at ask (plus slippage)
            sl = sig[k, 2] - buf - hs[e]                   # bid-side stop below the hump low
            risk = entry - sl
            if risk < min_risk or risk > max_risk:
                continue
            if tp_mode == 0:
                ref = sig[k, 3]
                tp = ref - anticip * (ref - entry) - hs[e]
            else:
                tp = entry + tp_rr * risk
            if tp - entry < min_rr * risk:
                continue
            stop = sl; px = np.nan; j = e
            while j < n:
                bh = h[j] - hs[j]; bl = l[j] - hs[j]; bo = o[j] - hs[j]
                if bo <= stop:
                    px = bo - slip; break
                if bl <= stop:
                    px = stop - slip; break
                if bh >= tp:
                    px = max(tp, bo); break
                if trail_start > 0 and bh - entry >= trail_start * risk:
                    cand = bh - trail_dist * risk
                    if cand > stop:
                        stop = cand
                        if c[j] - hs[j] <= stop or (trail_worst == 1 and bl <= stop):
                            px = stop - slip; break
                if wk[j]:
                    px = c[j] - hs[j] - slip; break
                j += 1
            if px != px:
                j = n - 1; px = c[j] - hs[j]
            r = (px - entry - comm) / risk
        out[m, 0] = e; out[m, 1] = j; out[m, 2] = side; out[m, 3] = r; out[m, 4] = risk
        m += 1
        busy = j
    return out[:m]


SESSIONS = {"all": (0, 1440), "ldn_ny_07-20": (420, 1200), "ny_12-1630": (720, 990), "ny_12-20": (720, 1200),
            "london_07-12": (420, 720)}
DEFAULT = dict(tf="M2", big_mult=1.5, hist=20, big_min_bars=5, stoch_req=1, pb_min_bars=3, pb_max_ratio=0.6,
               break_ratio=1.0, max_signals=2, trend_max_bars=120, sides=0, classic=0, session="all",
               buf=0.30, anticip=0.10, min_rr=0.8, tp_mode=0, tp_rr=1.5, trail_start=0.0, trail_dist=0.5,
               max_spread=0.60, min_risk=0.50, max_risk=1e9, htf="none", slip=0.0, comm=0.0, delay=0, trail_worst=0,
               skip_big_pb=0, weekend_close=0, weekend_min=1380)


class Market:
    def __init__(self, m1=None, half_spread=None):
        """Default: FTMO data with the hourly spread table. Or pass mid-price M1 bars indexed by
        broker server time (New York + 7h) and a per-bar half spread (e.g. Dukascopy bid/ask)."""
        os.environ.setdefault("XLZC_SYMBOL", "XAUUSD")
        hourly = None
        if m1 is None:
            m1, hourly = B.load(DATA)
        self.m1 = m1
        self.t = m1.index.values
        self.o = m1["open"].values.astype(float); self.h = m1["high"].values.astype(float)
        self.l = m1["low"].values.astype(float); self.c = m1["close"].values.astype(float)
        mult = float(os.environ.get("HUMP_SPREAD_MULT", "1"))
        self.hs = (hourly[B.server_to_utc_hour(m1.index)] / 2.0 if half_spread is None else np.asarray(half_spread, float)) * mult
        self.tod = (m1.index.hour * 60 + m1.index.minute).values.astype(np.int64)
        self.dow = m1.index.dayofweek.values                       # server time: Friday = 4
        gap = np.r_[(self.t[1:] - self.t[:-1]) > np.timedelta64(24, "h"), True]
        self.pre_gap = gap                                          # last bar before a closure of a day or more
        self._tf = {}

    def tf(self, name):
        if name not in self._tf:
            t = B.resample(self.m1, name)
            macd = B.macd_main(t["close"]).values.copy()
            macd[:60] = np.nan
            stk, _ = B.stoch(t, 7, 1, 7)
            nxt = t.index.values + np.timedelta64(B.TF_MIN[name], "m")      # next bar's open time
            row = np.searchsorted(self.t, nxt)
            ok = (row < len(self.t))
            gap = np.where(ok, self.t[np.clip(row, 0, len(self.t) - 1)] - nxt, np.timedelta64(10 ** 9, "m"))
            row = np.where(ok & (gap <= np.timedelta64(B.TF_MIN[name], "m")), row, -1)
            bias = {}
            for htf in ("H1", "H4"):                 # last CLOSED higher-timeframe bar: close vs EMA50
                hb = B.resample(self.m1, htf)
                b = np.sign(hb["close"] - B.ema(hb["close"], 50))
                b.index = b.index + pd.Timedelta(minutes=B.TF_MIN[htf])      # known from its close
                bias[htf] = b.reindex(t.index + pd.Timedelta(minutes=B.TF_MIN[name]), method="ffill").values
            self._tf[name] = (t["high"].values.astype(float), t["low"].values.astype(float), macd,
                              stk.values.astype(float), row.astype(np.int64), bias)
        return self._tf[name]

    def run(self, cfg):
        c = dict(DEFAULT); c.update(cfg)
        hi, lo, macd, stk, row, bias = self.tf(c["tf"])
        sg = signals(hi, lo, macd, stk, c["big_mult"], int(c["hist"]), int(c["big_min_bars"]), int(c["stoch_req"]),
                     int(c["pb_min_bars"]), c["pb_max_ratio"], c["break_ratio"], int(c["max_signals"]),
                     int(c["trend_max_bars"]), int(c["sides"]), int(c["classic"]), int(c["skip_big_pb"]))
        if c.get("htf", "none") != "none" and len(sg):      # optional: trade only with the HTF EMA50 side
            sg = sg[bias[c["htf"]][sg[:, 0].astype(np.int64)] == sg[:, 1]]
        er = row[sg[:, 0].astype(np.int64)] if len(sg) else np.zeros(0, np.int64)
        s0, s1 = SESSIONS[c["session"]]
        if c["weekend_close"]:           # Friday from weekend_min (server time) on, and the last bar before any long closure
            wk = ((self.dow == 4) & (self.tod >= int(c["weekend_min"]))) | self.pre_gap
        else:
            wk = np.zeros(len(self.t), np.bool_)
        tr = simulate(sg, er, self.o, self.h, self.l, self.c, self.hs, self.tod, s0, s1, c["buf"], c["anticip"],
                      c["min_rr"], int(c["tp_mode"]), c["tp_rr"], c["trail_start"], c["trail_dist"],
                      c["max_spread"], c["min_risk"], c["max_risk"], c["slip"], c["comm"], int(c["delay"]),
                      int(c["trail_worst"]), wk)
        df = pd.DataFrame(tr, columns=["entry_row", "exit_row", "side", "r", "risk"])
        df["entry_time"] = self.t[df.entry_row.astype(int).values] if len(df) else pd.Series(dtype="datetime64[ns]")
        df.attrs["signals"] = len(sg)
        return df


def stats(r):
    r = np.asarray(r, float)
    if len(r) == 0:
        return dict(n=0, pf=np.nan, net=0.0, win=np.nan, dd=0.0)
    w = r[r > 0].sum(); ls = -r[r < 0].sum()
    eq = np.cumsum(r)
    return dict(n=len(r), pf=(w / ls if ls > 0 else np.inf), net=float(r.sum()), win=float((r > 0).mean()),
                dd=float((np.maximum.accumulate(eq) - eq).max()))


def report(df, label):
    t = df.entry_time.values
    a = stats(df.r)
    y25 = stats(df.r.values[t < np.datetime64("2026-01-01")]); y26 = stats(df.r.values[t >= np.datetime64("2026-01-01")])
    print(f"{label:34s} n={a['n']:5d} PF={a['pf']:.2f} net={a['net']:+7.1f}R win={a['win']:.0%} DD={a['dd']:.1f}R | "
          f"2025 PF={y25['pf']:.2f} ({y25['n']}) | 2026 PF={y26['pf']:.2f} ({y26['n']})")


if __name__ == "__main__":
    mk = Market()
    for tf in ("M1", "M2", "M3", "M5"):
        report(mk.run(dict(tf=tf, classic=1)), f"{tf} every zero-cross, both sides")
        report(mk.run(dict(tf=tf, classic=1, sides=-1)), f"{tf} every zero-cross, sells")
        report(mk.run(dict(tf=tf)), f"{tf} hump method, both sides")
        report(mk.run(dict(tf=tf, sides=-1)), f"{tf} hump method, sells only")
        report(mk.run(dict(tf=tf, sides=1)), f"{tf} hump method, buys only")
