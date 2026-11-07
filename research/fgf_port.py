#!/usr/bin/env python3
"""
Python port of FlashGold Direction Filter v1.2 (MQL5 DirectionFilterCore.mqh +
the indicator adapter in FlashGold_Direction_Filter_v1_2.mq5), for backtesting
the XLZC EA's FGF build.

Scope: historical (closed-bar) semantics, which is what an EA reading the
indicator's live bar sees for the filter state:
  * The filter is computed on closed filter-TF bars (FgfBuildFilter).
  * At an EA entry time t the indicator's live chart bar picks the last filter
    point whose bar END <= t (FgfChartPick, check-on-tick, live bar), and the
    gate (FgfEvaluateGate) compares the live price with that point's armed level.
  * Parent / child TDI zones are read like the adapter does for closed bars:
    same-or-lower TF -> the bar that closed at the filter bar's end;
    higher TF with "HTF zones use last CLOSED bar" -> the bar before the one
    containing the filter bar's open.

Not modelled: quote-session truncated bar ends (nominal ends are used), the
live-observation commit of request.security values, and the direction score
(it does not affect the buffers the EA reads).

Times: the dataset is in broker server time (FTMO, New York + 7h), the clock MT5
uses for candle alignment, so all bars are resampled on the data index directly.
"""
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

EPS = 1e-10
MISSING = 99
TF_MIN = {"M1": 1, "M2": 2, "M3": 3, "M5": 5, "M15": 15, "M30": 30, "H1": 60,
          "H2": 120, "H4": 240, "H8": 480}


@dataclass(frozen=True)
class FgfConfig:
    filter_tf: str = "H1"
    parent_tf: str = "H1"
    level_mode: int = 0          # 0 entry price, 1 signal close
    window_mode: int = 0         # 0 until next signal, 1 minutes, 2 candles
    check_mode: int = 0          # 0 tick (live price), 1 bar open, 2 previous bar close
    minutes: int = 60
    bars: int = 1
    band_atr: float = 0.25
    against: bool = True         # allow trading against the last signal's direction
    allow_sell: bool = True
    spread_pts: float = 25.0
    entry_dist_pts: float = 50.0
    hold_bars: int = 0
    hold_fav_pts: float = 5.0
    one_per_bar: bool = True
    dist_unit: int = 0           # 0 ATR, 1 points
    burst_atr: float = 0.5
    entry_dist_atr: float = 0.25
    hold_fav_atr: float = 0.1
    burst_pts: float = 172.0
    use_burst: bool = True
    any_combo: bool = False
    drift_bars: int = 60
    use_drift: bool = False
    use_zones: bool = True
    rsi_len: int = 14
    fast_len: int = 2
    min_aligned: int = 2
    flat_parent: bool = False
    ignore_na: bool = True
    htf_closed: bool = True
    zones: tuple = ("H1", "H2", "H4")   # enabled child zone timeframes (max 6)
    tick: float = 0.01                  # FTMO XAUUSD trade tick size


# ----------------------------------------------------------------------------- comparisons
def isnum(x):
    return x is not None and np.isfinite(x)


def GT(a, b): return isnum(a) and isnum(b) and a - b > EPS
def LT(a, b): return isnum(a) and isnum(b) and a - b < -EPS
def GE(a, b): return isnum(a) and isnum(b) and a - b >= -EPS
def LE(a, b): return isnum(a) and isnum(b) and a - b <= EPS
def EQ(a, b): return isnum(a) and isnum(b) and abs(a - b) <= EPS


# ----------------------------------------------------------------------------- bars
def make_bars(m1, tf):
    """OHLC bars for tf. The data index is already broker server time, which is
    the clock MT5 uses to align H2/H4 candles, so bars are resampled directly.
    'open_t' / 'end_t' are server-time epoch seconds (same clock as the EA's entries)."""
    mins = TF_MIN[tf]
    o = m1[["open", "high", "low", "close"]].resample(f"{mins}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    open_s = o.index.values.astype("datetime64[s]").astype(np.int64)
    out = pd.DataFrame({"open_t": open_s, "end_t": open_s + mins * 60,
                        "open": o["open"].values, "high": o["high"].values,
                        "low": o["low"].values, "close": o["close"].values})
    return out.reset_index(drop=True)


def tdi_dirs(close, rsi_len, fast_len):
    """FgfTdiSeries: direction of SMA(fast_len) of Wilder RSI(rsi_len)."""
    n = len(close)
    dirs = np.zeros(n, dtype=np.int64)
    rsi = np.full(n, np.nan)
    gain = loss = 0.0
    fast_prev = None
    fast_sum = 0.0
    for i in range(1, n):
        up = max(close[i] - close[i - 1], 0.0)
        dn = max(close[i - 1] - close[i], 0.0)
        if i <= rsi_len:
            gain += up; loss += dn
            if i < rsi_len:
                continue
            gain /= rsi_len; loss /= rsi_len
        else:
            gain = (gain * (rsi_len - 1) + up) / rsi_len
            loss = (loss * (rsi_len - 1) + dn) / rsi_len
        rsi[i] = 100.0 if EQ(loss, 0.0) else 0.0 if EQ(gain, 0.0) else 100.0 - 100.0 / (1.0 + gain / loss)
        fast_sum += rsi[i]
        if i - rsi_len >= fast_len:
            fast_sum -= rsi[i - fast_len]
        if i - rsi_len + 1 >= fast_len:
            fast = fast_sum / fast_len
            if fast_prev is not None:
                dirs[i] = 1 if GT(fast, fast_prev) else -1 if LT(fast, fast_prev) else 0
            fast_prev = fast
    return dirs


# ----------------------------------------------------------------------------- filter build
@dataclass
class FilterState:
    end_t: np.ndarray        # filter bar end (server-time epoch seconds)
    armed_at: np.ndarray     # -1 if never armed
    armed_bar: np.ndarray
    armed_price: np.ndarray
    armed_dir: np.ndarray
    armed_atr: np.ndarray
    sell: np.ndarray         # bar produced a SELL signal
    buy: np.ndarray


class FgfEngine:
    """Caches bars and TDI directions per timeframe for one M1 data set."""

    def __init__(self, m1):
        self.m1 = m1
        self._bars = {}
        self._dirs = {}

    def bars(self, tf):
        if tf not in self._bars:
            self._bars[tf] = make_bars(self.m1, tf)
        return self._bars[tf]

    def dirs(self, tf, rsi_len, fast_len):
        key = (tf, rsi_len, fast_len)
        if key not in self._dirs:
            self._dirs[key] = tdi_dirs(self.bars(tf)["close"].values, rsi_len, fast_len)
        return self._dirs[key]

    def read_zone(self, cfg, tf, fb, prev_on):
        """Adapter Read() for each filter bar: returns int array of directions.
        prev_on=True -> OpenAt(filter open)-1 (child zones with 'HTF zones use last
        CLOSED bar'); False -> ClosedAt(filter end) (always used for the parent)."""
        b = self.bars(tf)
        d = self.dirs(tf, cfg.rsi_len, cfg.fast_len)
        if prev_on:
            k = np.searchsorted(b["open_t"].values, fb["open_t"].values, side="right") - 1 - 1
        else:
            k = np.searchsorted(b["end_t"].values, fb["end_t"].values, side="right") - 1
        out = np.where(k >= 0, d[np.clip(k, 0, len(d) - 1)], MISSING)
        return out

    def build(self, cfg: FgfConfig) -> FilterState:
        fb = self.bars(cfg.filter_tf)
        n = len(fb)
        o = fb["open"].values; h = fb["high"].values; l = fb["low"].values; c = fb["close"].values
        parents = self.read_zone(cfg, cfg.parent_tf, fb, prev_on=False)
        zones = [self.read_zone(cfg, z, fb, prev_on=cfg.htf_closed and TF_MIN[z] > TF_MIN[cfg.filter_tf])
                 for z in cfg.zones]
        tick = cfg.tick
        half = cfg.spread_pts * tick * 0.5

        armed_at = np.full(n, -1, np.int64); armed_bar = np.full(n, -1, np.int64)
        armed_price = np.full(n, np.nan); armed_dir = np.zeros(n, np.int64); armed_atr = np.full(n, np.nan)
        sell_sig = np.zeros(n, bool); buy_sig = np.zeros(n, bool)

        hold_active = False; hold_is_buy = False; hold_bar = -1; hold_mid = np.nan
        last_entry = -1
        atr = np.nan; tr_seed = 0.0
        a_at = -1; a_bar = -1; a_dir = 0; a_price = np.nan; a_atr = np.nan
        end_t = fb["end_t"].values
        for i in range(n):
            tr = h[i] - l[i] if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
            if i < 14:
                tr_seed += tr
                if i == 13:
                    atr = tr_seed / 14.0
            else:
                atr = (atr * 13.0 + tr) / 14.0
            parent = 0 if parents[i] == MISSING else int(parents[i])
            aligned = 0; active = 0
            for zarr in zones:
                d = int(zarr[i])
                on = (not cfg.ignore_na) or d != MISSING
                if on:
                    active += 1
                if on and parent != 0 and d == parent:
                    aligned += 1
            required = min(cfg.min_aligned, active)
            flat_ok = cfg.flat_parent and parent == 0
            zone_ready = active == 0 or aligned >= required
            zone_buy = (not cfg.use_zones) or ((parent == 1 or flat_ok) and zone_ready)
            zone_sell = (not cfg.use_zones) or ((parent == -1 or flat_ok) and zone_ready)
            bid = c[i] - half; ask = c[i] + half; mid = (bid + ask) * 0.5
            atr_pts = atr / tick if isnum(atr) else np.nan
            if cfg.dist_unit == 0:
                burst_thr = cfg.burst_atr * atr_pts if isnum(atr_pts) else np.nan
                entry_dist = cfg.entry_dist_atr * atr_pts if isnum(atr_pts) else np.nan
                hold_fav = cfg.hold_fav_atr * atr_pts if isnum(atr_pts) else np.nan
            else:
                burst_thr = cfg.burst_pts; entry_dist = cfg.entry_dist_pts; hold_fav = cfg.hold_fav_pts
            burst = (mid - ((c[i - 1] - half) + (c[i - 1] + half)) * 0.5) / tick if i > 0 else np.nan
            drift = (mid - ((c[i - cfg.drift_bars] - half) + (c[i - cfg.drift_bars] + half)) * 0.5) / tick \
                if i >= cfg.drift_bars else np.nan
            burst_buy = GE(burst, burst_thr)
            burst_sell = isnum(burst_thr) and LE(burst, -burst_thr)
            drift_buy = (not cfg.use_drift) or GT(drift, 0.0)
            drift_sell = (not cfg.use_drift) or LT(drift, 0.0)
            if cfg.any_combo:
                raw_buy = zone_buy and ((not cfg.use_burst) or burst_buy or parent == 1)
                raw_sell = zone_sell and ((not cfg.use_burst) or burst_sell or parent == -1)
            else:
                raw_buy = zone_buy and burst_buy
                raw_sell = zone_sell and burst_sell
            buy_c = raw_buy and drift_buy; sell_c = raw_sell and drift_sell
            can_fire = (not cfg.one_per_bar) or last_entry < 0 or last_entry != i
            p_buy = p_sell = False
            buy_entry = sell_entry = np.nan
            if buy_c and can_fire:
                if cfg.hold_bars == 0:
                    buy_entry = ask + entry_dist * tick if isnum(entry_dist) else np.nan
                    p_buy = True; last_entry = i
                elif not hold_active:
                    hold_active = True; hold_is_buy = True; hold_bar = i; hold_mid = mid
                elif hold_is_buy:
                    move = (mid - hold_mid) / tick
                    if i - hold_bar >= cfg.hold_bars and GE(move, hold_fav):
                        buy_entry = ask + entry_dist * tick if isnum(entry_dist) else np.nan
                        p_buy = True; last_entry = i; hold_active = False
            if sell_c and can_fire:
                if cfg.hold_bars == 0:
                    sell_entry = bid - entry_dist * tick if isnum(entry_dist) else np.nan
                    p_sell = True; last_entry = i
                elif not hold_active:
                    hold_active = True; hold_is_buy = False; hold_bar = i; hold_mid = mid
                elif not hold_is_buy:
                    move = (hold_mid - mid) / tick
                    if i - hold_bar >= cfg.hold_bars and GE(move, hold_fav):
                        sell_entry = bid - entry_dist * tick if isnum(entry_dist) else np.nan
                        p_sell = True; last_entry = i; hold_active = False
            if hold_active and ((hold_is_buy and not zone_buy) or ((not hold_is_buy) and not zone_sell)):
                hold_active = False; hold_bar = -1; hold_mid = np.nan
            sig_price = buy_entry if p_buy else sell_entry if p_sell else np.nan
            if p_buy or p_sell:
                a_at = int(end_t[i]); a_bar = i
                a_price = sig_price if (cfg.level_mode == 0 and isnum(sig_price)) else c[i]
                a_dir = 1 if p_buy else -1
                a_atr = atr
            armed_at[i] = a_at; armed_bar[i] = a_bar; armed_price[i] = a_price
            armed_dir[i] = a_dir; armed_atr[i] = a_atr
            buy_sig[i] = p_buy; sell_sig[i] = p_sell
        return FilterState(end_t, armed_at, armed_bar, armed_price, armed_dir, armed_atr, sell_sig, buy_sig)


def sell_allowed(cfg: FgfConfig, st: FilterState, t, value, prev_close=None):
    """FgfChartPick (live chart bar) + FgfEvaluateGate sellOK, evaluated once at the
    first tick of the EA's entry bar.
    t: entry bar open (server-time epoch seconds); value: live bid at that tick;
    prev_close: bid close of the previous trigger bar (check mode 2).
    check_mode 0 on a live/real-tick feed: the first tick arrives after hh:mm:00.000,
    so the chart clock is strictly after the closed filter bar's end and the live
    index is always that bar's index + 1. Modes 1/2 use clock = bar open exactly."""
    t = np.asarray(t, np.int64); value = np.asarray(value, float)
    if cfg.check_mode == 2:
        value = np.asarray(prev_close, float)
    k = np.searchsorted(st.end_t, t, side="right") - 1          # last filter bar with end <= t
    ok = np.zeros(len(t), bool)
    valid = k >= 0
    kk = np.clip(k, 0, len(st.end_t) - 1)
    a_at = st.armed_at[kk]; a_bar = st.armed_bar[kk]; a_price = st.armed_price[kk]
    a_dir = st.armed_dir[kk]; a_atr = st.armed_atr[kk]
    armed = valid & (a_at >= 0) & (t >= a_at)
    at_open = cfg.check_mode in (1, 2)
    # live chart-bar index (FgfChartPick): at_open uses clock = bar.time exactly, so a
    # bar opening on the filter boundary gets index k; tick mode is always k+1.
    index = np.where(at_open & (t == st.end_t[kk]), kk, kk + 1)
    if cfg.window_mode == 1:
        is_open = armed & (t < a_at + cfg.minutes * 60)
    elif cfg.window_mode == 2:
        is_open = armed & (index < a_bar + cfg.bars)
    else:
        is_open = armed
    band = cfg.band_atr * np.where(np.isfinite(a_atr), a_atr, 0.0)
    has_band = band > EPS
    tick = cfg.tick
    lower = np.where(has_band, np.floor((a_price - band) / tick + 1e-9) * tick, a_price)
    on_sig = armed & (index == a_bar)
    at_sell = on_sig & (a_dir < 0) & (value - a_price <= EPS)
    in_dn = np.where(has_band, (value - (lower - tick / 2.0)) < -EPS,
                     ((value - a_price) < -EPS) | at_sell)
    in_dn &= np.isfinite(a_price)
    ok = is_open & cfg.allow_sell & in_dn & (cfg.against | (a_dir < 0))
    return ok
