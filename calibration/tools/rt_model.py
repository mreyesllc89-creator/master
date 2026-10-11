"""Python replica of the RegimeTrend indicator (v1.03) + RegimeTrend_EA (v1.49)
for calibration on XAUUSD M1 bid/ask bars.

Fidelity notes
- Chart / H1 / H4 bars are built from M1 bars in *broker server time*
  (UTC+2, UTC+3 during US DST: the "NY close" convention the EA's tester
  session clock assumes), so H1/H4 boundaries match the MT5 chart.
- MT5 iATR is a simple moving average of True Range (ATR.mq5), replicated.
- Indicator buffers are computed exactly as the MQL5 code: ER on the last
  CLOSED H1 bar, SuperTrend on the chart TF, state machine with hysteresis /
  dwell / shock, H4 EMA-slope macro trend with HTF-bar debounce.
- EA decisions happen once per chart bar, at the bar's first tick (= open of
  its first M1 bar), using shift-1 (last closed bar) values. Stops / TP are
  checked on every M1 bar (bid for buys, ask for sells), SL before TP, gap
  fills at the M1 open when it already trades through the level.
- Lot sizing: % of equity / loss-per-lot to the SL, floor to 0.01, cap.
"""
import os
import numpy as np
import numba as nb

# ----------------------------------------------------------------- constants
POINT = 0.01
TICK = 0.01
CONTRACT = 100.0
VOL_STEP = 0.01
VOL_MIN = 0.01

REG_UNSET, REG_CHOPPY, REG_NEUTRAL, REG_TRENDING = -1, 0, 1, 2
ST_RANGE, ST_UP, ST_DOWN, ST_NEUTRAL, ST_UNSET = 0, 1, -1, 2, -999
MACRO_UNSET, MACRO_DOWN, MACRO_FLAT, MACRO_UP = -2, -1, 0, 1

TF_SEC = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H2": 7200,
          "H4": 14400, "D1": 86400}

# ----------------------------------------------------------------- data


def load_m1(data_dir, years):
    cols = ["t", "bo", "bh", "bl", "bc", "ao", "ah", "al", "ac"]
    parts = {c: [] for c in cols}
    for y in years:
        f = os.path.join(data_dir, f"xauusd_m1_{y}.npz")
        if not os.path.exists(f):
            continue
        z = np.load(f)
        for c in cols:
            parts[c].append(z[c])
    out = {c: np.concatenate(parts[c]) for c in cols}
    order = np.argsort(out["t"], kind="stable")
    for c in cols:
        out[c] = out[c][order]
    keep = np.ones(len(out["t"]), bool)
    keep[1:] = out["t"][1:] != out["t"][:-1]
    for c in cols:
        out[c] = out[c][keep]
    return out


def _nth_sunday_utc(year, month, n):
    """epoch seconds of 00:00 UTC of the n-th Sunday (n>=1) of a month."""
    d = np.datetime64(f"{year:04d}-{month:02d}-01")
    dow = (d.astype("datetime64[D]").astype(np.int64) + 4) % 7  # 0 = Sunday
    first_sun = d + np.timedelta64(int((7 - dow) % 7), "D")
    s = first_sun + np.timedelta64(7 * (n - 1), "D")
    return s.astype("datetime64[s]").astype(np.int64)


def server_offset_seconds(t_utc, base_hours=2, dst="US"):
    """Broker server offset (seconds) for each UTC timestamp."""
    off = np.full(len(t_utc), base_hours * 3600, np.int64)
    if dst == "NONE":
        return off
    years = np.unique(t_utc.astype("datetime64[s]").astype("datetime64[Y]").astype(int) + 1970)
    for y in years:
        if dst == "US":
            start = _nth_sunday_utc(y, 3, 2) + 7 * 3600     # 2nd Sunday March, 02:00 EST
            end = _nth_sunday_utc(y, 11, 1) + 6 * 3600      # 1st Sunday Nov, 02:00 EDT
        else:  # EU
            start = _nth_sunday_utc(y, 3, 5)  # placeholder, EU not used for XM
            end = _nth_sunday_utc(y, 10, 5)
        m = (t_utc >= start) & (t_utc < end)
        off[m] += 3600
    return off


def build_bars(t_server, m1, tf_sec, need_ask=True):
    """Aggregate M1 bars (bid OHLC, ask OHLC) into TF bars keyed on server time."""
    key = (t_server // tf_sec) * tf_sec
    _, first = np.unique(key, return_index=True)
    last = np.empty_like(first)
    last[:-1] = first[1:] - 1
    last[-1] = len(key) - 1
    bars = {
        "t": key[first],
        "first": first, "last": last,
        "o": m1["bo"][first],
        "h": np.maximum.reduceat(m1["bh"], first),
        "l": np.minimum.reduceat(m1["bl"], first),
        "c": m1["bc"][last],
    }
    if need_ask:
        bars["ao"] = m1["ao"][first]
        bars["ac"] = m1["ac"][last]
    return bars

# ----------------------------------------------------------------- indicator pieces


@nb.njit(cache=True)
def atr_sma(h, l, c, period):
    n = len(h)
    tr = np.zeros(n)
    atr = np.zeros(n)
    for i in range(1, n):
        hi = h[i] if h[i] > c[i - 1] else c[i - 1]
        lo = l[i] if l[i] < c[i - 1] else c[i - 1]
        tr[i] = hi - lo
    if n <= period:
        return atr
    s = 0.0
    for i in range(1, period + 1):
        s += tr[i]
    atr[period] = s / period
    for i in range(period + 1, n):
        atr[i] = atr[i - 1] + (tr[i] - tr[i - period]) / period
    return atr


@nb.njit(cache=True)
def supertrend(h, l, c, atr, mult, seed):
    n = len(h)
    st = np.full(n, np.nan)
    fu = np.zeros(n)
    fl = np.zeros(n)
    d = np.zeros(n)
    for i in range(seed, n):
        a = atr[i]
        hl2 = (h[i] + l[i]) * 0.5
        upper = hl2 + mult * a
        lower = hl2 - mult * a
        if i == seed:
            fu[i] = upper
            fl[i] = lower
            d[i] = 1.0 if c[i] > hl2 else -1.0
            st[i] = fl[i] if d[i] > 0 else fu[i]
            continue
        pfu, pfl, pd = fu[i - 1], fl[i - 1], d[i - 1]
        fu[i] = upper if (upper < pfu or c[i - 1] > pfu) else pfu
        fl[i] = lower if (lower > pfl or c[i - 1] < pfl) else pfl
        if pd > 0:
            d[i] = -1.0 if c[i] < fl[i] else 1.0
        else:
            d[i] = 1.0 if c[i] > fu[i] else -1.0
        st[i] = fl[i] if d[i] > 0 else fu[i]
    return st, d


@nb.njit(cache=True)
def efficiency_ratio(c, period):
    n = len(c)
    er = np.full(n, -1.0)
    for j in range(period, n):
        vol = 0.0
        for k in range(j - period + 1, j + 1):
            vol += abs(c[k] - c[k - 1])
        direction = abs(c[j] - c[j - period])
        er[j] = direction / vol if vol > 0 else 0.0
    return er


def map_closed_htf(t_chart, t_htf):
    """Index of the last CLOSED HTF bar as of each chart bar's open time (-1 if none)."""
    j_cur = np.searchsorted(t_htf, t_chart, side="right") - 1
    return j_cur - 1


@nb.njit(cache=True)
def state_machine(er, st_dir, atr, h, l, enter, exit_, min_dwell, shock, seed):
    n = len(er)
    state = np.full(n, ST_UNSET, np.int64)
    dwell = np.zeros(n, np.int64)
    for i in range(seed, n):
        if er[i] < 0.0 or atr[i] <= 0.0:
            state[i] = ST_UNSET
            dwell[i] = 0
            continue
        ps = state[i - 1] if i > 0 else ST_UNSET
        pdw = dwell[i - 1] if i > 0 else 0
        if ps == ST_UNSET:
            state[i] = ST_RANGE
            dwell[i] = 1
            continue
        # shock
        if atr[i] > 0 and (h[i] - l[i]) > shock * atr[i]:
            state[i] = ST_RANGE
            dwell[i] = 1
            continue
        trend_state = ST_UP if st_dir[i] > 0 else ST_DOWN
        in_trend = (ps == ST_UP or ps == ST_DOWN)
        if in_trend:
            target = ST_RANGE if er[i] < exit_ else trend_state
        else:
            if er[i] > enter:
                target = trend_state
            elif er[i] < exit_:
                target = ST_RANGE
            else:
                target = ST_NEUTRAL
        if target == ps or pdw < min_dwell:
            state[i] = ps
            dwell[i] = pdw + 1
        else:
            state[i] = target
            dwell[i] = 1
    return state, dwell


@nb.njit(cache=True)
def macro_raw(c_htf, ema_period, slope_bars, deadband_pct):
    n = len(c_htf)
    ema = np.full(n, np.nan)
    k = 2.0 / (ema_period + 1.0)
    running = 0.0
    for j in range(n):
        if j < ema_period - 1:
            running += c_htf[j]
            continue
        if j == ema_period - 1:
            running += c_htf[j]
            ema[j] = running / ema_period
            continue
        ema[j] = c_htf[j] * k + ema[j - 1] * (1.0 - k)
    raw = np.full(n, MACRO_UNSET, np.int64)
    for j in range(slope_bars, n):
        now, prev = ema[j], ema[j - slope_bars]
        if np.isnan(now) or np.isnan(prev) or prev == 0.0:
            raw[j] = MACRO_UNSET
            continue
        rel = (now - prev) / prev * 100.0
        if rel > deadband_pct:
            raw[j] = MACRO_UP
        elif rel < -deadband_pct:
            raw[j] = MACRO_DOWN
        else:
            raw[j] = MACRO_FLAT
    return raw


@nb.njit(cache=True)
def macro_debounce(raw_mapped, closed_idx, min_dwell):
    n = len(raw_mapped)
    trend = np.full(n, MACRO_UNSET, np.int64)
    dwell = np.zeros(n, np.int64)
    for i in range(n):
        pt = trend[i - 1] if i > 0 else MACRO_UNSET
        pdw = dwell[i - 1] if i > 0 else 0
        boundary = True if i == 0 else (closed_idx[i] != closed_idx[i - 1])
        if not boundary:
            trend[i] = pt
            dwell[i] = pdw
            continue
        raw = raw_mapped[i]
        if raw == MACRO_UNSET:
            trend[i] = MACRO_UNSET
            dwell[i] = 0
        elif pt == MACRO_UNSET:
            trend[i] = raw
            dwell[i] = 1
        elif raw == pt or pdw < min_dwell:
            trend[i] = pt
            dwell[i] = pdw + 1
        else:
            trend[i] = raw
            dwell[i] = 1
    return trend, dwell


def regime_split(state):
    regime = np.full(len(state), REG_UNSET, np.int64)
    regime[(state == ST_UP) | (state == ST_DOWN)] = REG_TRENDING
    regime[state == ST_NEUTRAL] = REG_NEUTRAL
    regime[state == ST_RANGE] = REG_CHOPPY
    direction = np.zeros(len(state), np.int64)
    direction[state == ST_UP] = 1
    direction[state == ST_DOWN] = -1
    return regime, direction


# ----------------------------------------------------------------- indicator parameter set
IND_DEFAULTS = dict(
    chart_tf="M15", regime_tf="H1", er_period=20, enter=0.42, exit=0.18,
    atr_period=10, atr_mult=4.0, min_dwell=6, shock_mult=3.0,
    macro_tf="H4", macro_ema=50, macro_slope=3, macro_deadband=0.05, macro_min_dwell=2,
    trail_atr_mult=0.0,   # >0: second, tighter SuperTrend used only for trailing (new)
)


class Market:
    """Holds M1 data in server time plus cached TF bars."""

    def __init__(self, m1, base_offset_h=2, dst="US"):
        self.m1 = m1
        self.t_utc = m1["t"]
        self.t_srv = self.t_utc + server_offset_seconds(self.t_utc, base_offset_h, dst)
        self._bars = {}

    def bars(self, tf):
        if tf not in self._bars:
            self._bars[tf] = build_bars(self.t_srv, self.m1, TF_SEC[tf])
        return self._bars[tf]


def compute_indicators(mkt, p):
    """Returns dict of per-chart-bar arrays matching the indicator buffers."""
    cb = mkt.bars(p["chart_tf"])
    h1 = mkt.bars(p["regime_tf"])
    h4 = mkt.bars(p["macro_tf"])
    n = len(cb["t"])
    seed = p["atr_period"] + 1
    atr = atr_sma(cb["h"], cb["l"], cb["c"], p["atr_period"])
    st, st_dir = supertrend(cb["h"], cb["l"], cb["c"], atr, p["atr_mult"], seed)
    # ER on HTF mapped to chart bars (last closed HTF bar)
    er_h = efficiency_ratio(h1["c"], p["er_period"])
    closed = map_closed_htf(cb["t"], h1["t"])
    er = np.where(closed >= p["er_period"], er_h[np.clip(closed, 0, len(er_h) - 1)], -1.0)
    state, dwell = state_machine(er, st_dir, atr, cb["h"], cb["l"], p["enter"], p["exit"],
                                 p["min_dwell"], p["shock_mult"], seed)
    regime, direction = regime_split(state)
    # macro
    raw_h = macro_raw(h4["c"], p["macro_ema"], p["macro_slope"], p["macro_deadband"])
    closed4 = map_closed_htf(cb["t"], h4["t"])
    raw_m = np.where(closed4 >= 0, raw_h[np.clip(closed4, 0, len(raw_h) - 1)], MACRO_UNSET)
    macro, _ = macro_debounce(raw_m, closed4, p["macro_min_dwell"])
    out = dict(atr=atr, st=st, st_dir=st_dir, er=er, state=state, dwell=dwell,
               regime=regime, direction=direction, macro=macro)
    if p.get("trail_atr_mult", 0.0) > 0:
        st2, _ = supertrend(cb["h"], cb["l"], cb["c"], atr, p["trail_atr_mult"], seed)
        out["st_trail"] = st2
    else:
        out["st_trail"] = st
    # bars since the regime became trending in the current direction (leg age)
    leg_age = np.full(n, -1, np.int64)
    age = -1
    for i in range(n):
        if regime[i] == REG_TRENDING and (i == 0 or regime[i - 1] != REG_TRENDING or direction[i] != direction[i - 1]):
            age = 0
        elif regime[i] == REG_TRENDING and age >= 0:
            age += 1
        else:
            age = -1
        leg_age[i] = age
    out["leg_age"] = leg_age
    return out


# ----------------------------------------------------------------- EA parameters
EA_KEYS = [
    # existing EA inputs
    "risk_pct", "fixed_lots", "max_lots", "min_stop_atr", "min_stop_pts",
    "use_st_sl", "trail_mode", "trail_step_pts", "use_be", "be_r", "be_buffer_pts",
    "tp_r", "exit_mode", "trade_direction", "use_macro_filter", "strict_shorts",
    "strict_longs", "use_session", "start_hour", "end_hour",
    # new, switchable improvements (defaults = current EA behaviour)
    "exit_on_st_flip", "max_bars_in_trade", "er_exit", "trail_atr_k", "trail_activate_r",
    "lock_trigger_r", "lock_r", "partial_r", "partial_pct", "max_spread_pts", "min_er_entry",
    "entry_prev_state", "late_entry_bars", "reentry_after_stop", "close_friday_hour",
    "max_stop_atr", "sl_atr_mult",
    # cost model
    "spread_add_pts", "commission_per_lot", "swap_usd_lot_night", "start_balance",
]
EA_IDX = {k: i for i, k in enumerate(EA_KEYS)}
EA_DEFAULTS = dict(
    risk_pct=1.0, fixed_lots=0.0, max_lots=5.0, min_stop_atr=1.0, min_stop_pts=0,
    use_st_sl=1, trail_mode=1, trail_step_pts=50, use_be=0, be_r=1.0, be_buffer_pts=10,
    tp_r=0.0, exit_mode=1, trade_direction=0, use_macro_filter=1, strict_shorts=1,
    strict_longs=1, use_session=0, start_hour=7, end_hour=18,
    exit_on_st_flip=0, max_bars_in_trade=0, er_exit=0.0, trail_atr_k=3.0, trail_activate_r=0.0,
    lock_trigger_r=0.0, lock_r=0.0, partial_r=0.0, partial_pct=50.0, max_spread_pts=0,
    min_er_entry=0.0, entry_prev_state=0, late_entry_bars=0, reentry_after_stop=0,
    close_friday_hour=0, max_stop_atr=0.0, sl_atr_mult=0.0,
    spread_add_pts=0.0, commission_per_lot=0.0, swap_usd_lot_night=0.0, start_balance=10000.0,
)
# trail_mode: 0 off, 1 SuperTrend (EA default), 2 tighter SuperTrend (ind trail_atr_mult),
#             3 chandelier (extreme -/+ k*ATR), 4 ATR from last close


def ea_params(**over):
    p = dict(EA_DEFAULTS)
    p.update(over)
    arr = np.zeros(len(EA_KEYS))
    for k, i in EA_IDX.items():
        arr[i] = float(p[k])
    return arr


# exit reason codes
X_SIGNAL, X_SL, X_TP, X_STFLIP, X_ER, X_TIME, X_FRIDAY, X_END = 1, 2, 3, 4, 5, 6, 7, 8
MAX_TRADES = 60000


@nb.njit(cache=True)
def _round_stop(price, buy):
    if buy:
        return np.floor(price / TICK + 1e-9) * TICK
    return np.ceil(price / TICK - 1e-9) * TICK


@nb.njit(cache=True)
def _cand(buy, price, old_sl, min_step, bid, ask, best):
    """Returns the better of `best` and the rounded/validated candidate `price`."""
    if np.isnan(price) or price <= 0.0:
        return best
    sl = _round_stop(price, buy)
    if old_sl > 0:
        if buy:
            if not (sl > old_sl + 1e-9 and sl - old_sl + 1e-9 >= min_step):
                return best
        else:
            if not (sl < old_sl - 1e-9 and old_sl - sl + 1e-9 >= min_step):
                return best
    dist = (bid - sl) if buy else (sl - ask)
    if dist < TICK - 1e-9:
        return best
    if best == 0.0:
        return sl
    if buy:
        return sl if sl > best else best
    return sl if sl < best else best


@nb.njit(cache=True)
def backtest(P,
             cb_t, cb_first, cb_last, cb_h, cb_l, cb_c,
             m1_t_utc, bo, bh, bl, bc, ao, ah, al, ac,
             regime, direction, st, st_dir, st_trail, atr, er, macro, leg_age,
             start_bar):
    """Event loop. Returns (stats, trades[n,12], equity[n_bars])."""
    n = len(cb_t)
    trades = np.zeros((MAX_TRADES, 12))
    ntr = 0
    equity = np.zeros(n)

    risk_pct = P[0]; fixed_lots = P[1]; max_lots = P[2]; min_stop_atr = P[3]; min_stop_pts = P[4]
    use_st_sl = P[5] > 0; trail_mode = int(P[6]); trail_step = P[7] * POINT; use_be = P[8] > 0
    be_r = P[9]; be_buf = P[10] * POINT; tp_r = P[11]; exit_mode = int(P[12]); trade_dir = int(P[13])
    use_macro = P[14] > 0; strict_shorts = P[15] > 0; strict_longs = P[16] > 0
    use_session = P[17] > 0; start_hour = int(P[18]); end_hour = int(P[19])
    exit_on_st_flip = P[20] > 0; max_bars = int(P[21]); er_exit = P[22]; trail_k = P[23]
    trail_act_r = P[24]; lock_trig = P[25]; lock_r = P[26]; partial_r = P[27]; partial_pct = P[28]
    max_spread = P[29] * POINT; min_er_entry = P[30]; entry_prev_state = int(P[31])
    late_entry_bars = int(P[32]); reentry_after_stop = P[33] > 0; close_friday_hour = int(P[34])
    max_stop_atr = P[35]; sl_atr_mult = P[36]
    spread_add = P[37] * POINT; commission = P[38]; swap_night = P[39]; balance = P[40]
    need_macro = use_macro or strict_shorts or strict_longs

    in_pos = False
    side = 0
    entry = 0.0; sl = 0.0; tp = 0.0; lots = 0.0; orig_lots = 0.0; risk = 0.0
    entry_bar = 0; entry_m1 = 0; fav = 0.0; partial_done = False
    traded_leg_id = -1; stopped_leg_id = -1
    leg_id = 0
    peak = balance
    max_dd = 0.0
    max_dd_pct = 0.0
    gross_p = 0.0; gross_l = 0.0; wins = 0; sum_r = 0.0
    realized_partial = 0.0
    entry_day = 0
    half_spread_add = spread_add * 0.5

    for i in range(start_bar, n):
        # leg bookkeeping (based on closed bar i-1)
        if regime[i - 1] == REG_TRENDING and (regime[i - 2] != REG_TRENDING or direction[i - 1] != direction[i - 2]):
            leg_id += 1
        f = cb_first[i]
        la = cb_last[i]
        bid = bo[f] - half_spread_add
        ask = ao[f] + half_spread_add
        reg_now = regime[i - 1]; reg_prev = regime[i - 2]; dir_now = direction[i - 1]
        macro_now = macro[i - 1]; st1 = st[i - 1]; atr1 = atr[i - 1]; er1 = er[i - 1]
        t0 = m1_t_utc[f]
        hour_gmt = (t0 // 3600) % 24
        dow = ((t0 // 86400) + 4) % 7
        exited_at_open = False

        if in_pos:
            buy = side == 1
            # ---------------- manage (BE / lock / trailing), once per bar at its open
            dist = (bid - entry) if buy else (entry - ask)
            best = 0.0
            if use_be and risk > 0 and dist / risk >= be_r:
                best = _cand(buy, entry + (be_buf if buy else -be_buf), sl, 0.0, bid, ask, best)
            if lock_trig > 0 and risk > 0 and dist / risk >= lock_trig:
                best = _cand(buy, entry + (lock_r * risk if buy else -lock_r * risk), sl, trail_step, bid, ask, best)
            if trail_mode > 0 and (trail_act_r <= 0 or (risk > 0 and dist / risk >= trail_act_r)):
                cand = np.nan
                if trail_mode == 1:
                    cand = st1
                elif trail_mode == 2:
                    cand = st_trail[i - 1]
                elif trail_mode == 3:
                    cand = (fav - trail_k * atr1) if buy else (fav + trail_k * atr1)
                elif trail_mode == 4:
                    cand = (cb_c[i - 1] - trail_k * atr1) if buy else (cb_c[i - 1] + trail_k * atr1)
                best = _cand(buy, cand, sl, trail_step, bid, ask, best)
            if best > 0:
                sl = best
            # ---------------- partial close
            if partial_r > 0 and not partial_done and risk > 0 and dist / risk >= partial_r:
                amt = np.floor(orig_lots * partial_pct / 100.0 / VOL_STEP + 1e-9) * VOL_STEP
                if amt >= VOL_MIN and lots - amt >= VOL_MIN - 1e-9:
                    px = bid if buy else ask
                    pnl = ((px - entry) if buy else (entry - px)) * CONTRACT * amt - commission * amt
                    balance += pnl
                    realized_partial += pnl
                    lots -= amt
                partial_done = True
            # ---------------- indicator exit at bar open
            ex = 0
            if exit_mode == 0:
                if reg_now != REG_TRENDING:
                    ex = X_SIGNAL
                elif dir_now != 0 and dir_now != side:
                    ex = X_SIGNAL
            else:
                if reg_now == REG_CHOPPY:
                    ex = X_SIGNAL
                elif dir_now != 0 and dir_now != side:
                    ex = X_SIGNAL
            if ex == 0 and exit_on_st_flip and st_dir[i - 1] != side:
                ex = X_STFLIP
            if ex == 0 and er_exit > 0 and er1 >= 0 and er1 < er_exit:
                ex = X_ER
            if ex == 0 and max_bars > 0 and (i - entry_bar) >= max_bars:
                ex = X_TIME
            if ex == 0 and close_friday_hour > 0 and dow == 5 and hour_gmt >= close_friday_hour:
                ex = X_FRIDAY
            if ex != 0:
                px = bid if buy else ask
                pnl = ((px - entry) if buy else (entry - px)) * CONTRACT * lots - commission * lots
                nights = (m1_t_utc[f] + 7200) // 86400 - entry_day
                pnl += swap_night * nights * orig_lots
                balance += pnl
                tot = pnl + realized_partial
                if ntr < MAX_TRADES:
                    trades[ntr, 0] = entry_bar; trades[ntr, 1] = i; trades[ntr, 2] = side
                    trades[ntr, 3] = entry; trades[ntr, 4] = px; trades[ntr, 5] = orig_lots
                    trades[ntr, 6] = tot; trades[ntr, 7] = ex; trades[ntr, 8] = (tot / (risk * CONTRACT * orig_lots)) if risk > 0 else 0.0
                    trades[ntr, 9] = m1_t_utc[entry_m1]; trades[ntr, 10] = t0; trades[ntr, 11] = balance
                    ntr += 1
                if tot > 0:
                    gross_p += tot; wins += 1
                else:
                    gross_l -= tot
                if risk > 0:
                    sum_r += tot / (risk * CONTRACT * orig_lots)
                in_pos = False
                realized_partial = 0.0
                exited_at_open = True
        if (not in_pos) and (not exited_at_open):
            # ---------------- entry evaluation
            transition = (reg_now == REG_TRENDING and reg_prev != REG_TRENDING and dir_now != 0)
            late = False
            if (not transition) and late_entry_bars > 0 and reg_now == REG_TRENDING and dir_now != 0:
                age = leg_age[i - 1]
                if age >= 1 and age <= late_entry_bars:
                    if traded_leg_id != leg_id or (reentry_after_stop and stopped_leg_id == leg_id and traded_leg_id == leg_id):
                        late = True
            ok = transition or late
            if ok and transition and entry_prev_state == 1 and reg_prev != REG_NEUTRAL:
                ok = False
            if ok and transition and entry_prev_state == 2 and reg_prev != REG_CHOPPY:
                ok = False
            if ok and late and reentry_after_stop and traded_leg_id == leg_id and stopped_leg_id != leg_id:
                ok = False
            if ok and late and (not reentry_after_stop) and traded_leg_id == leg_id:
                ok = False
            if ok:
                if (trade_dir == 1 and dir_now != 1) or (trade_dir == 2 and dir_now != -1):
                    ok = False
            if ok and use_session:
                if start_hour < end_hour:
                    ok = hour_gmt >= start_hour and hour_gmt < end_hour
                else:
                    ok = hour_gmt >= start_hour or hour_gmt < end_hour
            if ok and need_macro and macro_now == MACRO_UNSET:
                ok = False
            if ok and use_macro:
                if dir_now == 1 and macro_now < 0:
                    ok = False
                if dir_now == -1 and macro_now > 0:
                    ok = False
            if ok and strict_shorts and dir_now == -1 and macro_now != MACRO_DOWN:
                ok = False
            if ok and strict_longs and dir_now == 1 and macro_now != MACRO_UP:
                ok = False
            if ok and max_spread > 0 and (ask - bid) > max_spread + 1e-9:
                ok = False
            if ok and min_er_entry > 0 and er1 < min_er_entry:
                ok = False
            if ok and atr1 <= 0:
                ok = False
            if ok:
                buy = dir_now == 1
                floor_d = min_stop_pts * POINT
                if min_stop_atr > 0 and min_stop_atr * atr1 > floor_d:
                    floor_d = min_stop_atr * atr1
                sl_new = 0.0
                valid = True
                if sl_atr_mult > 0:
                    stop_price = (bid - sl_atr_mult * atr1) if buy else (ask + sl_atr_mult * atr1)
                    if buy:
                        if bid - floor_d < stop_price:
                            stop_price = bid - floor_d
                    else:
                        if ask + floor_d > stop_price:
                            stop_price = ask + floor_d
                    sl_new = _round_stop(stop_price, buy)
                elif use_st_sl and not np.isnan(st1) and st1 > 0:
                    if buy:
                        if st1 < bid:
                            stop_price = st1 if st1 < bid - floor_d else bid - floor_d
                            if max_stop_atr > 0 and stop_price < bid - max_stop_atr * atr1:
                                stop_price = bid - max_stop_atr * atr1
                            sl_new = _round_stop(stop_price, True)
                        else:
                            valid = False
                    else:
                        if st1 > ask:
                            stop_price = st1 if st1 > ask + floor_d else ask + floor_d
                            if max_stop_atr > 0 and stop_price > ask + max_stop_atr * atr1:
                                stop_price = ask + max_stop_atr * atr1
                            sl_new = _round_stop(stop_price, False)
                        else:
                            valid = False
                else:
                    valid = False  # % risk needs a stop
                if valid:
                    px_entry = ask if buy else bid
                    r_dist = (px_entry - sl_new) if buy else (sl_new - px_entry)
                    if r_dist <= 0:
                        valid = False
                if valid:
                    tp_new = 0.0
                    if tp_r > 0:
                        tp_new = (ask + tp_r * (ask - sl_new)) if buy else (bid - tp_r * (sl_new - bid))
                        tp_new = np.round(tp_new, 2)
                    loss_per_lot = r_dist * CONTRACT
                    if fixed_lots > 0:
                        vol = fixed_lots
                    else:
                        vol = balance * risk_pct / 100.0 / loss_per_lot
                    cap = max_lots if max_lots > 0 else 50.0
                    if vol > cap:
                        vol = cap
                    vol = np.floor(vol / VOL_STEP + 1e-9) * VOL_STEP
                    if vol >= VOL_MIN:
                        in_pos = True
                        side = 1 if buy else -1
                        entry = px_entry; sl = sl_new; tp = tp_new; lots = vol; orig_lots = vol
                        risk = r_dist; entry_bar = i; entry_m1 = f; fav = entry; partial_done = False
                        traded_leg_id = leg_id
                        entry_day = (t0 + 7200) // 86400
                        realized_partial = 0.0
        # ---------------- intrabar stop / tp on M1 bars
        if in_pos:
            buy = side == 1
            for k in range(f, la + 1):
                ex = 0
                px = 0.0
                if buy:
                    lo = bl[k] - half_spread_add
                    hi = bh[k] - half_spread_add
                    op = bo[k] - half_spread_add
                    if lo <= sl:
                        ex = X_SL; px = op if op < sl else sl
                    elif tp > 0 and hi >= tp:
                        ex = X_TP; px = op if op > tp else tp
                    if hi > fav:
                        fav = hi
                else:
                    hi = ah[k] + half_spread_add
                    lo = al[k] + half_spread_add
                    op = ao[k] + half_spread_add
                    if hi >= sl:
                        ex = X_SL; px = op if op > sl else sl
                    elif tp > 0 and lo <= tp:
                        ex = X_TP; px = op if op < tp else tp
                    if lo < fav:
                        fav = lo
                if ex != 0:
                    pnl = ((px - entry) if buy else (entry - px)) * CONTRACT * lots - commission * lots
                    nights = (m1_t_utc[k] + 7200) // 86400 - entry_day
                    pnl += swap_night * nights * orig_lots
                    balance += pnl
                    tot = pnl + realized_partial
                    if ntr < MAX_TRADES:
                        trades[ntr, 0] = entry_bar; trades[ntr, 1] = i; trades[ntr, 2] = side
                        trades[ntr, 3] = entry; trades[ntr, 4] = px; trades[ntr, 5] = orig_lots
                        trades[ntr, 6] = tot; trades[ntr, 7] = ex; trades[ntr, 8] = (tot / (risk * CONTRACT * orig_lots)) if risk > 0 else 0.0
                        trades[ntr, 9] = m1_t_utc[entry_m1]; trades[ntr, 10] = m1_t_utc[k]; trades[ntr, 11] = balance
                        ntr += 1
                    if tot > 0:
                        gross_p += tot; wins += 1
                    else:
                        gross_l -= tot
                    if risk > 0:
                        sum_r += tot / (risk * CONTRACT * orig_lots)
                    if ex == X_SL or ex == X_TP:
                        stopped_leg_id = leg_id
                    in_pos = False
                    realized_partial = 0.0
                    break
        # ---------------- equity at bar close
        eq = balance
        if in_pos:
            if side == 1:
                eq += (bc[la] - half_spread_add - entry) * CONTRACT * lots
            else:
                eq += (entry - ac[la] - half_spread_add) * CONTRACT * lots
        equity[i] = eq
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
        ddp = dd / peak if peak > 0 else 0.0
        if ddp > max_dd_pct:
            max_dd_pct = ddp
        if balance <= 0:
            break

    # close any open position at the end (mark to market)
    if in_pos:
        la = cb_last[n - 1]
        buy = side == 1
        px = (bc[la] - half_spread_add) if buy else (ac[la] + half_spread_add)
        pnl = ((px - entry) if buy else (entry - px)) * CONTRACT * lots - commission * lots
        balance += pnl
        tot = pnl + realized_partial
        if ntr < MAX_TRADES:
            trades[ntr, 0] = entry_bar; trades[ntr, 1] = n - 1; trades[ntr, 2] = side
            trades[ntr, 3] = entry; trades[ntr, 4] = px; trades[ntr, 5] = orig_lots
            trades[ntr, 6] = tot; trades[ntr, 7] = X_END; trades[ntr, 8] = (tot / (risk * CONTRACT * orig_lots)) if risk > 0 else 0.0
            trades[ntr, 9] = m1_t_utc[entry_m1]; trades[ntr, 10] = m1_t_utc[la]; trades[ntr, 11] = balance
            ntr += 1
        if tot > 0:
            gross_p += tot; wins += 1
        else:
            gross_l -= tot
        if risk > 0:
            sum_r += tot / (risk * CONTRACT * orig_lots)

    stats = np.zeros(10)
    stats[0] = balance - P[40]           # net profit
    stats[1] = ntr                       # trades
    stats[2] = wins
    stats[3] = gross_p
    stats[4] = gross_l
    stats[5] = max_dd_pct * 100.0        # max drawdown % of peak equity
    stats[6] = sum_r
    stats[7] = max_dd
    stats[8] = balance
    return stats, trades[:ntr], equity


class Backtester:
    """Caches indicator series per indicator-parameter tuple and runs EA sweeps."""

    def __init__(self, mkt):
        self.mkt = mkt
        self._cache = {}

    MAX_CACHE = 6   # bounded: sweeps create a new indicator series per job

    def indicators(self, ind):
        key = tuple(sorted(ind.items()))
        if key not in self._cache:
            if len(self._cache) >= self.MAX_CACHE:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = compute_indicators(self.mkt, ind)
        return self._cache[key]

    def run(self, ind, ea, start_bar=None, t_from=None, t_to=None):
        I = self.indicators(ind)
        cb = self.mkt.bars(ind["chart_tf"])
        m1 = self.mkt.m1
        if start_bar is None:
            start_bar = ind["atr_period"] + 4
        # time window (UTC epoch) -> bar range by masking regime outside window
        regime = I["regime"]
        if t_from is not None or t_to is not None:
            tb = m1["t"][cb["first"]]
            if t_from is not None:
                start_bar = max(start_bar, int(np.searchsorted(tb, t_from)))
            n_end = len(cb["t"]) if t_to is None else int(np.searchsorted(tb, t_to))
        else:
            n_end = len(cb["t"])
        sl_ = slice(0, n_end)
        stats, trades, equity = backtest(
            ea, cb["t"][sl_], cb["first"][sl_], cb["last"][sl_], cb["h"][sl_], cb["l"][sl_], cb["c"][sl_],
            m1["t"], m1["bo"], m1["bh"], m1["bl"], m1["bc"], m1["ao"], m1["ah"], m1["al"], m1["ac"],
            regime[sl_], I["direction"][sl_], I["st"][sl_], I["st_dir"][sl_], I["st_trail"][sl_],
            I["atr"][sl_], I["er"][sl_], I["macro"][sl_], I["leg_age"][sl_], start_bar)
        return stats, trades, equity[start_bar:n_end]


def summarize(stats, trades, equity, start_balance, years):
    net, ntr, wins, gp, gl, mddp, sum_r, mdd, final = stats[:9]
    ntr = int(ntr); wins = int(wins)
    pf = gp / gl if gl > 0 else (np.inf if gp > 0 else 0.0)
    ret = net / start_balance * 100.0
    cagr = ((final / start_balance) ** (1.0 / years) - 1.0) * 100.0 if final > 0 and years > 0 else -100.0
    out = dict(net=net, ret_pct=ret, cagr_pct=cagr, trades=ntr, win_pct=(wins / ntr * 100 if ntr else 0.0),
               pf=pf, max_dd_pct=mddp, avg_r=(sum_r / ntr if ntr else 0.0),
               calmar=(cagr / mddp if mddp > 0 else 0.0), final=final)
    if ntr:
        r = trades[:, 8]
        out["r_std"] = float(np.std(r))
        out["sqn"] = float(np.sqrt(ntr) * np.mean(r) / (np.std(r) + 1e-12))
        # longest losing streak
        losses = trades[:, 6] <= 0
        streak = best = 0
        for x in losses:
            streak = streak + 1 if x else 0
            best = max(best, streak)
        out["max_loss_streak"] = best
        out["avg_bars"] = float(np.mean(trades[:, 1] - trades[:, 0]))
        out["exit_sl_pct"] = float(np.mean(trades[:, 7] == X_SL) * 100)
        out["exit_sig_pct"] = float(np.mean(trades[:, 7] == X_SIGNAL) * 100)
    else:
        out.update(r_std=0.0, sqn=0.0, max_loss_streak=0, avg_bars=0.0, exit_sl_pct=0.0, exit_sig_pct=0.0)
    return out
