"""Port of the embedded FlashGold Direction Filter v1.2 (FlashGold/DirectionFilterCore.mqh,
DirectionFilterClock.mqh, QuoteBucketSeries.mqh, PermissionExpiry.mqh and the adapter in
SpeedAlertFlashGoldPermission.mqh).

What is reproduced
  * FgfTdiSeries      RSI (Wilder) -> SMA(fastLen) -> direction of the fast line, per timeframe
  * FgfBuildFilter    ATR(14), parent/zone alignment, burst and drift tests, hold logic, armed level
  * FgfEvaluateGate   BUY/SELL area test against the armed level and its ATR band
  * CFgfQuoteBuckets  the "micro" filter bars: occupied quote buckets of FG_IntervalMs, first bucket of
                      every capture epoch excluded, a new epoch after a quote gap > FG_MicroMaxGapMs
  * timed permission  FG_InpLast = Seconds / Milliseconds (end-exclusive deadline after the signal bar)

Simplifications (documented in REPORT.md)
  * Bars end at their nominal time; the broker's quote-session calendar is not applied.
  * In native mode the "observed live" commits of parent/zone directions are not replayed: a finished
    filter bar always uses closed-bar parent/zone values.
  * The tick check mode (FG_InpCheck = Tick) is the only one implemented; it is what every preset uses.
    In that mode the gate always reads the state of the last *completed* filter bar.
"""
import numpy as np
from numba import njit

EPS = 1e-10
MISSING = 99
TICK = 0.01


@njit(cache=True)
def _gt(a, b):
    return (not np.isnan(a)) and (not np.isnan(b)) and a - b > EPS


@njit(cache=True)
def _lt(a, b):
    return (not np.isnan(a)) and (not np.isnan(b)) and a - b < -EPS


@njit(cache=True)
def _ge(a, b):
    return (not np.isnan(a)) and (not np.isnan(b)) and a - b >= -EPS


@njit(cache=True)
def _le(a, b):
    return (not np.isnan(a)) and (not np.isnan(b)) and a - b <= EPS


@njit(cache=True)
def _eq(a, b):
    return (not np.isnan(a)) and (not np.isnan(b)) and abs(a - b) <= EPS


def make_bars(t, bid, period_ms):
    """Occupied bars of a native timeframe from bid ticks (MT5 chart bars are bid based)."""
    key = t // period_ms
    start = np.concatenate(([0], np.flatnonzero(np.diff(key)) + 1))
    stop = np.concatenate((start[1:], [len(t)]))
    time = key[start] * period_ms
    return dict(time=time.astype(np.int64), end=(time + period_ms).astype(np.int64), open=bid[start].copy(),
                high=np.maximum.reduceat(bid, start), low=np.minimum.reduceat(bid, start), close=bid[stop - 1].copy())


@njit(cache=True)
def tdi_dirs(close, rsi_len, fast_len):
    """FgfTdiSeries: +1 / -1 / 0 per bar."""
    n = len(close)
    dirs = np.zeros(n, dtype=np.int8)
    rsi = np.full(n, np.nan)
    gain = 0.0
    loss = 0.0
    fast_prev = np.nan
    fast_sum = 0.0
    for i in range(1, n):
        up = max(close[i] - close[i - 1], 0.0)
        dn = max(close[i - 1] - close[i], 0.0)
        if i <= rsi_len:
            gain += up
            loss += dn
            if i < rsi_len:
                continue
            gain /= rsi_len
            loss /= rsi_len
        else:
            gain = (gain * (rsi_len - 1) + up) / rsi_len
            loss = (loss * (rsi_len - 1) + dn) / rsi_len
        if _eq(loss, 0.0):
            rsi[i] = 100.0
        elif _eq(gain, 0.0):
            rsi[i] = 0.0
        else:
            rsi[i] = 100.0 - 100.0 / (1.0 + gain / loss)
        fast_sum += rsi[i]
        if i - rsi_len >= fast_len:
            fast_sum -= rsi[i - fast_len]
        if i - rsi_len + 1 >= fast_len:
            fast = fast_sum / fast_len
            if not np.isnan(fast_prev):
                dirs[i] = 1 if _gt(fast, fast_prev) else (-1 if _lt(fast, fast_prev) else 0)
            fast_prev = fast
    return dirs


@njit(cache=True)
def micro_buckets(t, bid, interval, max_bars, max_gap, restart):
    """CFgfQuoteBuckets over a whole tick array.

    Returns bar arrays plus li (index inside the capture epoch). `restart` = False is the literal
    v1.501 behaviour: when an epoch reaches max_bars the stream blocks for good ("restart required").
    `restart` = True starts a fresh epoch at that quote instead, i.e. what an operator restart does."""
    n = len(t)
    cap = n
    bt = np.empty(cap, np.int64)
    bo = np.empty(cap, np.float64)
    bh = np.empty(cap, np.float64)
    bl = np.empty(cap, np.float64)
    bc = np.empty(cap, np.float64)
    li = np.empty(cap, np.int32)
    nb = 0
    have = False
    initial = -1
    last_ms = -1
    epoch_len = 0
    blocked = False
    for k in range(n):
        if blocked:
            break
        ms = t[k]
        price = bid[k]
        if have and ms - last_ms > max_gap:
            have = False
            epoch_len = 0
        bucket = (ms // interval) * interval
        if not have:
            initial = bucket
            have = True
            last_ms = ms
            continue
        last_ms = ms
        if bucket == initial:
            continue
        if epoch_len > 0 and bt[nb - 1] == bucket:
            if price > bh[nb - 1]:
                bh[nb - 1] = price
            if price < bl[nb - 1]:
                bl[nb - 1] = price
            bc[nb - 1] = price
        else:
            if epoch_len >= max_bars:
                if restart:
                    initial = bucket
                    epoch_len = 0
                    continue
                blocked = True
                break
            bt[nb] = bucket
            bo[nb] = price
            bh[nb] = price
            bl[nb] = price
            bc[nb] = price
            li[nb] = epoch_len
            epoch_len += 1
            nb += 1
    return bt[:nb].copy(), bo[:nb].copy(), bh[:nb].copy(), bl[:nb].copy(), bc[:nb].copy(), li[:nb].copy()


@njit(cache=True)
def build_filter(li, high, low, close, end, parents, zones, child_on,
                 level_mode, spread_pts, entry_dist_pts, hold_bars, hold_fav_pts, one_per_bar, dist_unit,
                 burst_atr, entry_dist_atr, hold_fav_atr, burst_pts, use_burst, any_combo, drift_bars,
                 use_drift, use_zones, min_aligned, flat_parent, ignore_na):
    """FgfBuildFilter for a concatenation of series; li[i] == 0 starts a new series (epoch).

    Output per bar = the armed state *after* that bar: armedAt, armedBar (index in its series),
    armedPrice, armedDir, armedAtr, plus the bar's own signal (+1 buy, -1 sell, 0) and ATR."""
    n = len(close)
    armed_at = np.full(n, -1, np.int64)
    armed_bar = np.full(n, -1, np.int32)
    armed_price = np.full(n, np.nan)
    armed_dir = np.zeros(n, np.int8)
    armed_atr = np.full(n, np.nan)
    signal = np.zeros(n, np.int8)
    atr_out = np.full(n, np.nan)
    half = spread_pts * TICK * 0.5
    hold_active = False
    hold_is_buy = False
    hold_sig_bar = -1
    last_entry_bar = -1
    hold_sig_mid = np.nan
    atr = np.nan
    tr_seed = 0.0
    a_at = -1
    a_bar = -1
    a_dir = 0
    a_price = np.nan
    a_atr = np.nan
    for k in range(n):
        i = li[k]
        if i == 0:
            hold_active = False
            hold_is_buy = False
            hold_sig_bar = -1
            last_entry_bar = -1
            hold_sig_mid = np.nan
            atr = np.nan
            tr_seed = 0.0
            a_at = -1
            a_bar = -1
            a_dir = 0
            a_price = np.nan
            a_atr = np.nan
        if i == 0:
            tr = high[k] - low[k]
        else:
            tr = max(high[k] - low[k], max(abs(high[k] - close[k - 1]), abs(low[k] - close[k - 1])))
        if i < 14:
            tr_seed += tr
            if i == 13:
                atr = tr_seed / 14.0
        else:
            atr = (atr * 13.0 + tr) / 14.0
        atr_out[k] = atr
        parent = 0 if parents[k] == MISSING else parents[k]
        aligned = 0
        active = 0
        for z in range(6):
            d = zones[k, z]
            on = child_on[z] and ((not ignore_na) or d != MISSING)
            if on:
                active += 1
            if on and parent != 0 and d == parent:
                aligned += 1
        required = min(min_aligned, active)
        parent_flat_allowed = flat_parent and parent == 0
        zone_ready = active == 0 or aligned >= required
        zone_buy = (not use_zones) or ((parent == 1 or parent_flat_allowed) and zone_ready)
        zone_sell = (not use_zones) or ((parent == -1 or parent_flat_allowed) and zone_ready)
        bid = close[k] - half
        ask = close[k] + half
        mid = (bid + ask) * 0.5
        atr_pts = atr / TICK if not np.isnan(atr) else np.nan
        if dist_unit == 0:
            burst_thr = burst_atr * atr_pts if not np.isnan(atr_pts) else np.nan
            entry_dist = entry_dist_atr * atr_pts if not np.isnan(atr_pts) else np.nan
            hold_fav = hold_fav_atr * atr_pts if not np.isnan(atr_pts) else np.nan
        else:
            burst_thr = burst_pts
            entry_dist = entry_dist_pts
            hold_fav = hold_fav_pts
        burst = np.nan
        if i > 0:
            burst = (mid - ((close[k - 1] - half) + (close[k - 1] + half)) * 0.5) / TICK
        drift = np.nan
        if i >= drift_bars:
            drift = (mid - ((close[k - drift_bars] - half) + (close[k - drift_bars] + half)) * 0.5) / TICK
        burst_buy = _ge(burst, burst_thr)
        burst_sell = (not np.isnan(burst_thr)) and _le(burst, -burst_thr)
        drift_buy = (not use_drift) or _gt(drift, 0.0)
        drift_sell = (not use_drift) or _lt(drift, 0.0)
        if any_combo:
            raw_buy = zone_buy and ((not use_burst) or burst_buy or parent == 1)
            raw_sell = zone_sell and ((not use_burst) or burst_sell or parent == -1)
        else:
            raw_buy = zone_buy and burst_buy
            raw_sell = zone_sell and burst_sell
        buy_cand = raw_buy and drift_buy
        sell_cand = raw_sell and drift_sell
        can_fire = (not one_per_bar) or last_entry_bar < 0 or last_entry_bar != i
        buy_entry = np.nan
        sell_entry = np.nan
        p_buy = False
        p_sell = False
        if buy_cand and can_fire:
            if hold_bars == 0:
                buy_entry = ask + entry_dist * TICK if not np.isnan(entry_dist) else np.nan
                p_buy = True
                last_entry_bar = i
            elif not hold_active:
                hold_active = True
                hold_is_buy = True
                hold_sig_bar = i
                hold_sig_mid = mid
            elif hold_is_buy:
                move = (mid - hold_sig_mid) / TICK
                if i - hold_sig_bar >= hold_bars and _ge(move, hold_fav):
                    buy_entry = ask + entry_dist * TICK if not np.isnan(entry_dist) else np.nan
                    p_buy = True
                    last_entry_bar = i
                    hold_active = False
        if sell_cand and can_fire:
            if hold_bars == 0:
                sell_entry = bid - entry_dist * TICK if not np.isnan(entry_dist) else np.nan
                p_sell = True
                last_entry_bar = i
            elif not hold_active:
                hold_active = True
                hold_is_buy = False
                hold_sig_bar = i
                hold_sig_mid = mid
            elif not hold_is_buy:
                move = (hold_sig_mid - mid) / TICK
                if i - hold_sig_bar >= hold_bars and _ge(move, hold_fav):
                    sell_entry = bid - entry_dist * TICK if not np.isnan(entry_dist) else np.nan
                    p_sell = True
                    last_entry_bar = i
                    hold_active = False
        if hold_active and ((hold_is_buy and not zone_buy) or ((not hold_is_buy) and not zone_sell)):
            hold_active = False
            hold_sig_bar = -1
            hold_sig_mid = np.nan
        sig_price = buy_entry if p_buy else (sell_entry if p_sell else np.nan)
        if p_buy or p_sell:
            a_at = end[k]
            a_bar = i
            a_price = sig_price if (level_mode == 0 and not np.isnan(sig_price)) else close[k]
            a_dir = 1 if p_buy else -1
            a_atr = atr
            signal[k] = a_dir
        armed_at[k] = a_at
        armed_bar[k] = a_bar
        armed_price[k] = a_price
        armed_dir[k] = a_dir
        armed_atr[k] = a_atr
    return armed_at, armed_bar, armed_price, armed_dir, armed_atr, signal, atr_out


@njit(cache=True)
def gate(a_at, a_bar, a_price, a_dir, a_atr, clock, index, value,
         window_mode, minutes, bars, band_atr, against, allow_buy, allow_sell):
    """FgfEvaluateGate + the adapter's final test. Returns 1 (BUY area), -1 (SELL area) or 0."""
    armed = a_at >= 0 and clock >= a_at
    end_ms = -1
    if window_mode == 1 and armed:
        end_ms = a_at + minutes * 60000
    if window_mode == 1:
        is_open = armed and clock < end_ms
    elif window_mode == 2:
        is_open = armed and index < a_bar + bars
    else:
        is_open = armed
    on_sig = armed and index == a_bar
    band = band_atr * (a_atr if not np.isnan(a_atr) else 0.0)
    in_up = False
    in_dn = False
    if not np.isnan(a_price):
        has_band = _gt(band, 0.0)
        if has_band:
            upper = np.ceil((a_price + band) / TICK - 1e-9) * TICK
            lower = np.floor((a_price - band) / TICK + 1e-9) * TICK
            in_up = _gt(value, upper + TICK / 2.0)
            in_dn = _lt(value, lower - TICK / 2.0)
        else:
            at_buy = on_sig and a_dir > 0 and _ge(value, a_price)
            at_sell = on_sig and a_dir < 0 and _le(value, a_price)
            in_up = _gt(value, a_price) or at_buy
            in_dn = _lt(value, a_price) or at_sell
    buy_ok = is_open and allow_buy and in_up and (against or a_dir > 0)
    sell_ok = is_open and allow_sell and in_dn and (against or a_dir < 0)
    if buy_ok:
        return 1
    if sell_ok:
        return -1
    return 0


PERIOD_MS = {1: 60000, 2: 120000, 3: 180000, 4: 240000, 5: 300000, 6: 360000, 10: 600000, 12: 720000,
             15: 900000, 20: 1200000, 30: 1800000, 16385: 3600000, 16386: 7200000, 16387: 10800000,
             16388: 14400000, 16390: 21600000, 16392: 28800000, 16396: 43200000, 16408: 86400000}


def fg_key(p):
    """The inputs that change the precomputed filter series (the gate inputs are applied per tick)."""
    names = ["UseFlashGoldDirectionFilter", "FG_Resolution", "FG_IntervalMs", "FG_MicroMaxBars", "FG_MicroMaxGapMs",
             "FG_InpTf", "FG_InpLvMode", "FG_InpSpreadPts", "FG_InpEntryDistPts", "FG_InpHoldBars", "FG_InpHoldFavPts",
             "FG_InpOnePerBar", "FG_InpDistUnit", "FG_InpBurstAtr", "FG_InpEntryDistAtr", "FG_InpHoldFavAtr",
             "FG_InpBurstPts", "FG_InpUseBurst", "FG_InpAnyCombo", "FG_InpDriftBars", "FG_InpUseDrift", "FG_InpUseZones",
             "FG_InpParentTf", "FG_InpRsiLen", "FG_InpFastLen", "FG_InpMinAligned", "FG_InpFlatParent", "FG_InpIgnoreNa",
             "FG_InpHtfClosed", "FG_InpUseZ1", "FG_InpZTf1", "FG_InpUseZ2", "FG_InpZTf2", "FG_InpUseZ3", "FG_InpZTf3",
             "FG_InpUseZ4", "FG_InpZTf4", "FG_InpUseZ5", "FG_InpZTf5", "FG_InpUseZ6", "FG_InpZTf6", "X_MicroRestart"]
    return tuple(float(p[k]) for k in names)


class FilterSeries:
    """Precomputed filter bars and armed states for one FlashGold configuration over a whole feed."""

    def __init__(self, feed, p, bar_cache=None, keep_detail=False):
        self.enabled = bool(p["UseFlashGoldDirectionFilter"])
        self.micro = int(p["FG_Resolution"]) == 1
        empty_i = np.zeros(0, np.int64)
        empty_f = np.zeros(0, np.float64)
        self.time = empty_i; self.end = empty_i; self.li = np.zeros(0, np.int32)
        self.a_at = empty_i; self.a_bar = np.zeros(0, np.int32); self.a_price = empty_f
        self.a_dir = np.zeros(0, np.int8); self.a_atr = empty_f
        self.signal = np.zeros(0, np.int8); self.atr = empty_f; self.signals = 0
        self.interval = int(p["FG_IntervalMs"]) if self.micro else PERIOD_MS[int(p["FG_InpTf"])]
        if not self.enabled:
            return
        cache = bar_cache if bar_cache is not None else {}

        def tf(code):
            code = int(code)
            if code == 0:
                code = 1                                   # PERIOD_CURRENT = the M1 chart
            key = ("bars", code)
            if key not in cache:
                cache[key] = make_bars(feed.t, feed.bid, PERIOD_MS[code])
            dkey = ("dirs", code, int(p["FG_InpRsiLen"]), int(p["FG_InpFastLen"]))
            if dkey not in cache:
                cache[dkey] = tdi_dirs(cache[key]["close"], int(p["FG_InpRsiLen"]), int(p["FG_InpFastLen"]))
            return cache[key], cache[dkey]

        parent_bars, parent_dirs = tf(p["FG_InpParentTf"])
        child_on = np.array([bool(p[f"FG_InpUseZ{z}"]) for z in range(1, 7)])
        children = [tf(p[f"FG_InpZTf{z}"]) if child_on[z - 1] else None for z in range(1, 7)]

        def closed_at(bars, times):                       # last bar with end <= time
            return np.searchsorted(bars["end"], times, side="right") - 1

        def open_at(bars, times):                         # last bar with open time <= time
            return np.searchsorted(bars["time"], times, side="right") - 1

        def read(dirs, k):
            out = np.full(len(k), MISSING, np.int8)
            ok = k >= 0
            out[ok] = dirs[k[ok]]
            return out

        if self.micro:
            bt, bo, bh, bl, bc, li = micro_buckets(feed.t, feed.bid, self.interval, int(p["FG_MicroMaxBars"]),
                                                    int(p["FG_MicroMaxGapMs"]), bool(p["X_MicroRestart"]))
            self.time = bt; self.end = bt + self.interval; self.li = li
            high, low, close = bh, bl, bc
            parents = read(parent_dirs, closed_at(parent_bars, bt))
            zones = np.full((len(bt), 6), MISSING, np.int8)
            for z in range(6):
                if children[z] is not None:
                    zones[:, z] = read(children[z][1], closed_at(children[z][0], bt))
        else:
            fbars, _ = tf(p["FG_InpTf"])
            self.time = fbars["time"]; self.end = fbars["end"]
            self.li = np.arange(len(self.time), dtype=np.int32)
            high, low, close = fbars["high"], fbars["low"], fbars["close"]
            parents = read(parent_dirs, closed_at(parent_bars, self.end))
            zones = np.full((len(self.time), 6), MISSING, np.int8)
            for z in range(6):
                if children[z] is None:
                    continue
                cb, cd = children[z]
                code = int(p[f"FG_InpZTf{z + 1}"]) or 1
                previous_on = bool(p["FG_InpHtfClosed"]) and PERIOD_MS[code] > self.interval
                k = open_at(cb, self.time) - 1 if previous_on else closed_at(cb, self.end)
                zones[:, z] = read(cd, k)
        (self.a_at, self.a_bar, self.a_price, self.a_dir, self.a_atr, self.signal, self.atr) = build_filter(
            self.li, high, low, close, self.end, parents, zones, child_on,
            int(p["FG_InpLvMode"]), float(p["FG_InpSpreadPts"]), float(p["FG_InpEntryDistPts"]), int(p["FG_InpHoldBars"]),
            float(p["FG_InpHoldFavPts"]), bool(p["FG_InpOnePerBar"]), int(p["FG_InpDistUnit"]), float(p["FG_InpBurstAtr"]),
            float(p["FG_InpEntryDistAtr"]), float(p["FG_InpHoldFavAtr"]), float(p["FG_InpBurstPts"]), bool(p["FG_InpUseBurst"]),
            bool(p["FG_InpAnyCombo"]), int(p["FG_InpDriftBars"]), bool(p["FG_InpUseDrift"]), bool(p["FG_InpUseZones"]),
            int(p["FG_InpMinAligned"]), bool(p["FG_InpFlatParent"]), bool(p["FG_InpIgnoreNa"]))
        self.signals = int(np.count_nonzero(self.signal))
        if not keep_detail:
            self.signal = np.zeros(0, np.int8)
            self.atr = np.zeros(0, np.float64)
