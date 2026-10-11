"""Python replica of BTCSignalFlow_Test_EA v1.10 (+ BTCMethodSignals.mqh) for
calibration on BTCUSD M1 bid/ask bars. Shares the data layer and execution
conventions with rt_model.py (RegimeTrend replica).

EA rules replicated
- Signal timeframe = chart timeframe (InpSignalPeriod = CURRENT). One decision
  per new bar at its first tick, signals evaluated on the last closed bar.
- CBTCMethodSignals: ATR14 (MT5 SMA-of-TR), EMA50/200 (MT5 seed = first
  price), pullback EMA, Bollinger(20, 2) with population std, RSI14 (Wilder),
  20-bar efficiency ratio, H4 EMA50/200/ATR14 macro on the last H4 bar closed
  by the decision time, ATR% volatility gate 0.10 %..4 % (6 % on D1).
- Six methods (trend pullback, breakout retest, efficiency breakout, range
  reversion, time momentum, Donchian trend) exactly as in the include.
- Entry at market, SL = entry -/+ StopATR x ATR, TP = TakeProfitR x risk,
  trailing stop = close -/+ TrailATR x ATR through the money manager (never
  loosens, min step 50 points), exit on opposite trend / macro / mean,
  optional time stop, spread filter <= MaxSpreadATR x ATR.
- Lots = RiskPercent of equity / (stop distance x contract), floor to 0.01,
  margin budget MaxMarginPct of equity at `leverage`.
"""
import os, sys
import numpy as np
import numba as nb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rt_model as rt
from rt_model import Market, atr_sma, TF_SEC

POINT = 0.01
TICK = 0.01
CONTRACT = 1.0
VOL_STEP = 0.01
VOL_MIN = 0.01

M_TREND_PULLBACK, M_BREAKOUT_RETEST, M_EFFICIENCY_BREAKOUT, M_RANGE_REVERSION, M_TIME_MOMENTUM, M_DONCHIAN_TREND = 0, 1, 2, 3, 4, 5


# ------------------------------------------------------------------ MT5 standard indicators
@nb.njit(cache=True)
def ema_mt5(price, period):
    n = len(price)
    out = np.full(n, np.nan)
    if n == 0:
        return out
    k = 2.0 / (period + 1.0)
    out[0] = price[0]
    for i in range(1, n):
        out[i] = price[i] * k + out[i - 1] * (1.0 - k)
    return out


@nb.njit(cache=True)
def bands_mt5(price, period, dev):
    n = len(price)
    mid = np.full(n, np.nan); up = np.full(n, np.nan); lo = np.full(n, np.nan)
    for i in range(period - 1, n):
        s = 0.0
        for k in range(i - period + 1, i + 1):
            s += price[k]
        m = s / period
        v = 0.0
        for k in range(i - period + 1, i + 1):
            v += (price[k] - m) ** 2
        sd = np.sqrt(v / period)
        mid[i] = m; up[i] = m + dev * sd; lo[i] = m - dev * sd
    return mid, up, lo


@nb.njit(cache=True)
def rsi_mt5(price, period):
    n = len(price)
    out = np.full(n, np.nan)
    if n <= period:
        return out
    pos = 0.0; neg = 0.0
    for i in range(1, period + 1):
        d = price[i] - price[i - 1]
        if d > 0:
            pos += d
        else:
            neg -= d
    pos /= period; neg /= period
    out[period] = 100.0 if neg == 0 else 100.0 - 100.0 / (1.0 + pos / neg)
    for i in range(period + 1, n):
        d = price[i] - price[i - 1]
        p = d if d > 0 else 0.0
        q = -d if d < 0 else 0.0
        pos = (pos * (period - 1) + p) / period
        neg = (neg * (period - 1) + q) / period
        out[i] = 100.0 if neg == 0 else 100.0 - 100.0 / (1.0 + pos / neg)
    return out


# ------------------------------------------------------------------ signal engine
@nb.njit(cache=True)
def _channel(h, l, i, start, count):
    """max high / min low over bars r[start .. start+count-1] where r[j] = bar i-j."""
    hi = -1e300; lo = 1e300
    for j in range(start, start + count):
        k = i - j
        if h[k] > hi:
            hi = h[k]
        if l[k] < lo:
            lo = l[k]
    return hi, lo


@nb.njit(cache=True)
def evaluate_signals(method, length, exit_bars, efficiency, clearance, max_atr_pct,
                     o, h, l, c, atr, fast, slow, pull, bb_mid, bb_up, bb_lo, rsi,
                     h4_idx, h4_ok, hf_arr, hl_arr, ho_arr, ha_arr):
    """For each bar i (as the LAST CLOSED bar, i.e. shift 1 of the next bar) compute
    side, trend, macro, mean, valid. Arrays indexed by the signal bar itself."""
    n = len(c)
    side = np.zeros(n, np.int64); trend = np.zeros(n, np.int64); macro = np.zeros(n, np.int64)
    mean = np.full(n, np.nan); valid = np.zeros(n, np.bool_); er_out = np.zeros(n)
    count = max(max(length + 12, exit_bars + 2), 35)
    for i in range(n):
        if i < count or i < 205 or i - 5 < 0:
            continue
        if not (atr[i] > 0) or np.isnan(fast[i]) or np.isnan(slow[i]) or np.isnan(slow[i - 4]) or np.isnan(pull[i]):
            continue
        close = c[i]
        if close <= 0:
            continue
        atr_pct = 100.0 * atr[i] / close
        allow_entry = atr_pct >= 0.10 and atr_pct <= max_atr_pct
        tr = 1 if (fast[i] > slow[i] and slow[i] > slow[i - 4]) else (-1 if (fast[i] < slow[i] and slow[i] < slow[i - 4]) else 0)
        change = 0.0
        for j in range(20):
            change += abs(c[i - j] - c[i - j - 1])
        er = abs(c[i] - c[i - 20]) / change if change > 0 else 0.0
        er_out[i] = er
        mn = pull[i]
        # macro
        if not h4_ok[i]:
            continue
        hf = hf_arr[i]; hl = hl_arr[i]; ho = ho_arr[i]; ha = ha_arr[i]
        if np.isnan(hf) or np.isnan(hl) or np.isnan(ho) or not (ha > 0):
            continue
        mc = 0
        if abs(hf - hl) >= 0.25 * ha:
            mc = 1 if (hf > hl and hl > ho) else (-1 if (hf < hl and hl < ho) else 0)
        sd = 0
        if method == 0:
            touch_buy = False; touch_sell = False
            for j in range(3):
                p = pull[i - j]
                if l[i - j] <= p:
                    touch_buy = True
                if h[i - j] >= p:
                    touch_sell = True
            if mc == 1 and touch_buy and close > mn and close > h[i - 1] and close > o[i] and close - mn <= 1.5 * atr[i]:
                sd = 1
            if mc == -1 and touch_sell and close < mn and close < l[i - 1] and close < o[i] and mn - close <= 1.5 * atr[i]:
                sd = -1
        elif method == 1:
            for j in range(1, 9):
                hi, lo = _channel(h, l, i, j + 1, length)
                ba = atr[i - j]
                direction = 1 if c[i - j] > hi + clearance * ba else (-1 if c[i - j] < lo - clearance * ba else 0)
                if direction == 0:
                    continue
                level = hi if direction == 1 else lo
                invalid = False; already = False
                for k in range(j - 1, 0, -1):
                    ck = c[i - k]; lk = l[i - k]; hk = h[i - k]; ok_ = o[i - k]
                    if direction == 1 and ck < level - 0.75 * ba:
                        invalid = True
                    if direction == -1 and ck > level + 0.75 * ba:
                        invalid = True
                    if direction == 1 and lk <= level + 0.25 * ba and ck > level + 0.10 * ba and ck > ok_:
                        already = True
                    if direction == -1 and hk >= level - 0.25 * ba and ck < level - 0.10 * ba and ck < ok_:
                        already = True
                if (not invalid) and (not already) and direction == mc:
                    if direction == 1 and l[i] <= level + 0.25 * ba and close > level + 0.10 * ba and close > o[i]:
                        sd = 1
                    if direction == -1 and h[i] >= level - 0.25 * ba and close < level - 0.10 * ba and close < o[i]:
                        sd = -1
                break
        elif method == 2:
            hi, lo = _channel(h, l, i, 1, length)
            if er >= efficiency:
                if tr == 1 and close > hi + clearance * atr[i]:
                    sd = 1
                if tr == -1 and close < lo - clearance * atr[i]:
                    sd = -1
        elif method == 3:
            if np.isnan(bb_mid[i]) or np.isnan(bb_up[i - 1]) or np.isnan(rsi[i - 1]):
                continue
            mn = bb_mid[i]
            if er <= efficiency:
                if c[i - 1] < bb_lo[i - 1] and close > bb_lo[i] and close < bb_up[i] and rsi[i - 1] <= 35:
                    sd = 1
                if c[i - 1] > bb_up[i - 1] and close < bb_up[i] and close > bb_lo[i] and rsi[i - 1] >= 65:
                    sd = -1
        elif method == 4:
            tr = 1 if (close > c[i - length] and close > slow[i]) else (-1 if (close < c[i - length] and close < slow[i]) else 0)
            sd = tr
        else:
            hi, lo = _channel(h, l, i, 1, length)
            ehi, elo = _channel(h, l, i, 1, exit_bars)
            tr = 1 if close > ehi else (-1 if close < elo else 0)
            if close > hi + clearance * atr[i]:
                sd = 1
            if close < lo - clearance * atr[i]:
                sd = -1
        if not allow_entry:
            sd = 0
        side[i] = sd; trend[i] = tr; macro[i] = mc; mean[i] = mn; valid[i] = True
    return side, trend, macro, mean, valid, er_out


SIG_DEFAULTS = dict(chart_tf="H1", method=2, length=30, exit_bars=10, efficiency=0.20, pullback_ema=20, clearance=0.20)


def compute_signals(mkt, p):
    tf = p["chart_tf"]
    cb = mkt.bars(tf)
    h4 = mkt.bars("H4")
    c = cb["c"]
    atr = atr_sma(cb["h"], cb["l"], c, 14)
    fast = ema_mt5(c, 50); slow = ema_mt5(c, 200); pull = ema_mt5(c, int(p["pullback_ema"]))
    bb_mid, bb_up, bb_lo = bands_mt5(c, 20, 2.0)
    rsi = rsi_mt5(c, 14)
    # H4 macro: last H4 bar whose close time (open + 4h) <= decision_time = bar open + period
    period = TF_SEC[tf]
    decision = cb["t"] + period
    h4_open = h4["t"]
    hs = np.searchsorted(h4_open + 14400, decision, side="right") - 1   # last bar with close <= decision
    h4_ok = hs >= 3
    hs_c = np.clip(hs, 0, len(h4_open) - 1)
    hf4 = ema_mt5(h4["c"], 50); hl4 = ema_mt5(h4["c"], 200); ha4 = atr_sma(h4["h"], h4["l"], h4["c"], 14)
    hf = hf4[hs_c]; hl = hl4[hs_c]; ho = hl4[np.clip(hs_c - 3, 0, len(h4_open) - 1)]; ha = ha4[hs_c]
    h4_ok &= (hs_c >= 204)
    max_atr_pct = 6.0 if tf == "D1" else 4.0
    side, trend, macro, mean, valid, er = evaluate_signals(
        int(p["method"]), int(p["length"]), int(p["exit_bars"]), float(p["efficiency"]), float(p["clearance"]), max_atr_pct,
        cb["o"], cb["h"], cb["l"], c, atr, fast, slow, pull, bb_mid, bb_up, bb_lo, rsi,
        hs_c, h4_ok, hf, hl, ho, ha)
    return dict(side=side, trend=trend, macro=macro, mean=mean, valid=valid, atr=atr, er=er, close=c)


# ------------------------------------------------------------------ EA parameters
EA_KEYS = ["risk_pct", "stop_atr", "trail_atr", "tp_r", "max_hold_bars", "max_spread_atr", "max_margin_pct",
           "leverage", "trail_step_pts", "exit_rule",
           # improvements (0 = original)
           "use_be", "be_r", "trail_activate_r", "lock_trigger_r", "lock_r", "trail_mode", "partial_r", "partial_pct",
           "er_exit", "long_only", "short_only",
           "spread_add_pct", "commission_pct", "swap_pct_day", "start_balance"]
EA_IDX = {k: i for i, k in enumerate(EA_KEYS)}
EA_DEFAULTS = dict(risk_pct=0.5, stop_atr=2.5, trail_atr=3.5, tp_r=4.0, max_hold_bars=0, max_spread_atr=0.30,
                   max_margin_pct=10.0, leverage=10.0, trail_step_pts=50, exit_rule=0,
                   use_be=0, be_r=1.0, trail_activate_r=0.0, lock_trigger_r=0.0, lock_r=0.0, trail_mode=1, partial_r=0.0,
                   partial_pct=50.0, er_exit=0.0, long_only=0, short_only=0,
                   spread_add_pct=0.0, commission_pct=0.0, swap_pct_day=0.0, start_balance=10000.0)
# exit_rule: 0 = method default (trend / macro / mean), 1 = no signal exit (stops only)
# trail_mode: 0 off, 1 ATR from close (original), 2 chandelier (extreme -/+ trail_atr x ATR)


def ea_params(**over):
    p = dict(EA_DEFAULTS); p.update(over)
    arr = np.zeros(len(EA_KEYS))
    for k, i in EA_IDX.items():
        arr[i] = float(p[k])
    return arr


X_SIGNAL, X_SL, X_TP, X_TIME, X_ER, X_END = 1, 2, 3, 6, 5, 8
MAX_TRADES = 60000


@nb.njit(cache=True)
def _round_stop(price, buy):
    return (np.floor(price / TICK + 1e-9) if buy else np.ceil(price / TICK - 1e-9)) * TICK


@nb.njit(cache=True)
def _cand(buy, price, old_sl, min_step, bid, ask, best):
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
def backtest(P, method, cb_t, cb_first, cb_last, cb_c, m1_t, bo, bh, bl, bc, ao, ah, al, ac,
             side_a, trend_a, macro_a, mean_a, valid_a, atr_a, er_a, start_bar):
    n = len(cb_t)
    trades = np.zeros((MAX_TRADES, 12)); ntr = 0
    equity = np.zeros(n)
    risk_pct = P[0]; stop_atr = P[1]; trail_atr = P[2]; tp_r = P[3]; max_hold = int(P[4]); max_spread_atr = P[5]
    max_margin_pct = P[6]; leverage = P[7]; trail_step = P[8] * POINT; exit_rule = int(P[9])
    use_be = P[10] > 0; be_r = P[11]; trail_act = P[12]; lock_trig = P[13]; lock_r = P[14]; trail_mode = int(P[15])
    partial_r = P[16]; partial_pct = P[17]; er_exit = P[18]; long_only = P[19] > 0; short_only = P[20] > 0
    spread_add_pct = P[21] / 100.0; commission_pct = P[22] / 100.0; swap_pct_day = P[23] / 100.0; balance = P[24]

    in_pos = False; side = 0; entry = 0.0; sl = 0.0; tp = 0.0; lots = 0.0; orig_lots = 0.0; risk = 0.0
    entry_bar = 0; entry_m1 = 0; fav = 0.0; partial_done = False; realized_partial = 0.0
    peak = balance; max_dd_pct = 0.0; max_dd = 0.0; gross_p = 0.0; gross_l = 0.0; wins = 0; sum_r = 0.0
    entry_t = 0

    for i in range(start_bar, n):
        j = i - 1   # last closed bar = signal bar
        if not valid_a[j]:
            # EA: Evaluate() failed -> nothing happens this bar (no management either)
            # still check stops intrabar below
            pass
        f = cb_first[i]; la = cb_last[i]
        hs = bo[f] * spread_add_pct * 0.5
        bid = bo[f] - hs; ask = ao[f] + hs
        atr1 = atr_a[j]; sd = side_a[j]; tr = trend_a[j]; mc = macro_a[j]; mn = mean_a[j]; cl = cb_c[j]
        exited_at_open = False
        if valid_a[j] and atr1 > 0:
            if in_pos:
                buy = side == 1
                dist = (bid - entry) if buy else (entry - ask)
                # signal exit
                close_now = False
                if exit_rule == 0:
                    if method == 3:
                        close_now = (cl >= mn) if buy else (cl <= mn)
                    elif method == 0 or method == 1:
                        close_now = (mc < 0) if buy else (mc > 0)
                    else:
                        close_now = (tr < 0) if buy else (tr > 0)
                ex = X_SIGNAL if close_now else 0
                if ex == 0 and max_hold > 0 and (i - entry_bar) >= max_hold:
                    ex = X_TIME
                if ex == 0 and er_exit > 0 and er_a[j] < er_exit:
                    ex = X_ER
                if ex != 0:
                    px = bid if buy else ask
                    pnl = ((px - entry) if buy else (entry - px)) * CONTRACT * lots
                    pnl -= commission_pct * (entry + px) * CONTRACT * lots
                    pnl -= swap_pct_day * entry * CONTRACT * orig_lots * ((m1_t[f] - entry_t) / 86400.0)
                    balance += pnl; tot = pnl + realized_partial
                    if ntr < MAX_TRADES:
                        trades[ntr, 0] = entry_bar; trades[ntr, 1] = i; trades[ntr, 2] = side; trades[ntr, 3] = entry
                        trades[ntr, 4] = px; trades[ntr, 5] = orig_lots; trades[ntr, 6] = tot; trades[ntr, 7] = ex
                        trades[ntr, 8] = tot / (risk * CONTRACT * orig_lots) if risk > 0 else 0.0
                        trades[ntr, 9] = m1_t[entry_m1]; trades[ntr, 10] = m1_t[f]; trades[ntr, 11] = balance; ntr += 1
                    if tot > 0:
                        gross_p += tot; wins += 1
                    else:
                        gross_l -= tot
                    if risk > 0:
                        sum_r += tot / (risk * CONTRACT * orig_lots)
                    in_pos = False; realized_partial = 0.0; exited_at_open = True
                else:
                    # manage: BE / lock / trailing (money manager, once per bar)
                    best = 0.0
                    if use_be and risk > 0 and dist / risk >= be_r:
                        best = _cand(buy, entry, sl, 0.0, bid, ask, best)
                    if lock_trig > 0 and risk > 0 and dist / risk >= lock_trig:
                        best = _cand(buy, entry + (lock_r * risk if buy else -lock_r * risk), sl, trail_step, bid, ask, best)
                    if trail_atr > 0 and trail_mode > 0 and (trail_act <= 0 or (risk > 0 and dist / risk >= trail_act)):
                        if trail_mode == 1:
                            cand = cl - trail_atr * atr1 if buy else cl + trail_atr * atr1
                        else:
                            cand = fav - trail_atr * atr1 if buy else fav + trail_atr * atr1
                        best = _cand(buy, cand, sl, trail_step, bid, ask, best)
                    if best > 0:
                        sl = best
                    if partial_r > 0 and not partial_done and risk > 0 and dist / risk >= partial_r:
                        amt = np.floor(orig_lots * partial_pct / 100.0 / VOL_STEP + 1e-9) * VOL_STEP
                        if amt >= VOL_MIN and lots - amt >= VOL_MIN - 1e-9:
                            px = bid if buy else ask
                            pnl = ((px - entry) if buy else (entry - px)) * CONTRACT * amt - commission_pct * (entry + px) * CONTRACT * amt
                            balance += pnl; realized_partial += pnl; lots -= amt
                        partial_done = True
            elif sd != 0:
                ok = True
                if long_only and sd != 1:
                    ok = False
                if short_only and sd != -1:
                    ok = False
                if ok and max_spread_atr > 0 and (ask - bid) > max_spread_atr * atr1:
                    ok = False
                if ok:
                    buy = sd == 1
                    px_entry = ask if buy else bid
                    if buy:
                        s0 = px_entry - stop_atr * atr1
                        if bid - TICK < s0:
                            s0 = bid - TICK
                        sl_new = _round_stop(s0, True)
                    else:
                        s0 = px_entry + stop_atr * atr1
                        if ask + TICK > s0:
                            s0 = ask + TICK
                        sl_new = _round_stop(s0, False)
                    r_dist = (px_entry - sl_new) if buy else (sl_new - px_entry)
                    if r_dist > 0 and sl_new > 0:
                        tp_new = 0.0
                        if tp_r > 0:
                            t0_ = px_entry + (tp_r * r_dist if buy else -tp_r * r_dist)
                            tp_new = (np.ceil(t0_ / TICK - 1e-9) if buy else np.floor(t0_ / TICK + 1e-9)) * TICK
                        vol = balance * risk_pct / 100.0 / (r_dist * CONTRACT)
                        # margin budget
                        if max_margin_pct > 0 and leverage > 0:
                            cap = balance * max_margin_pct / 100.0 * leverage / (px_entry * CONTRACT)
                            if vol > cap:
                                vol = cap
                        vol = np.floor(vol / VOL_STEP + 1e-9) * VOL_STEP
                        if vol >= VOL_MIN:
                            in_pos = True; side = sd; entry = px_entry; sl = sl_new; tp = tp_new; lots = vol; orig_lots = vol
                            risk = r_dist; entry_bar = i; entry_m1 = f; fav = entry; partial_done = False
                            realized_partial = 0.0; entry_t = m1_t[f]
                            balance -= commission_pct * entry * CONTRACT * vol * 0.0  # commission applied at exit on both legs
        # intrabar stops on M1
        if in_pos:
            buy = side == 1
            for k in range(f, la + 1):
                hsk = bo[k] * spread_add_pct * 0.5
                ex = 0; px = 0.0
                if buy:
                    lo = bl[k] - hsk; hi = bh[k] - hsk; op = bo[k] - hsk
                    if lo <= sl:
                        ex = X_SL; px = op if op < sl else sl
                    elif tp > 0 and hi >= tp:
                        ex = X_TP; px = op if op > tp else tp
                    if hi > fav:
                        fav = hi
                else:
                    hi = ah[k] + hsk; lo = al[k] + hsk; op = ao[k] + hsk
                    if hi >= sl:
                        ex = X_SL; px = op if op > sl else sl
                    elif tp > 0 and lo <= tp:
                        ex = X_TP; px = op if op < tp else tp
                    if lo < fav:
                        fav = lo
                if ex != 0:
                    pnl = ((px - entry) if buy else (entry - px)) * CONTRACT * lots
                    pnl -= commission_pct * (entry + px) * CONTRACT * lots
                    pnl -= swap_pct_day * entry * CONTRACT * orig_lots * ((m1_t[k] - entry_t) / 86400.0)
                    balance += pnl; tot = pnl + realized_partial
                    if ntr < MAX_TRADES:
                        trades[ntr, 0] = entry_bar; trades[ntr, 1] = i; trades[ntr, 2] = side; trades[ntr, 3] = entry
                        trades[ntr, 4] = px; trades[ntr, 5] = orig_lots; trades[ntr, 6] = tot; trades[ntr, 7] = ex
                        trades[ntr, 8] = tot / (risk * CONTRACT * orig_lots) if risk > 0 else 0.0
                        trades[ntr, 9] = m1_t[entry_m1]; trades[ntr, 10] = m1_t[k]; trades[ntr, 11] = balance; ntr += 1
                    if tot > 0:
                        gross_p += tot; wins += 1
                    else:
                        gross_l -= tot
                    if risk > 0:
                        sum_r += tot / (risk * CONTRACT * orig_lots)
                    in_pos = False; realized_partial = 0.0
                    break
        eq = balance
        if in_pos:
            hsl = bo[la] * spread_add_pct * 0.5
            eq += ((bc[la] - hsl - entry) if side == 1 else (entry - ac[la] - hsl)) * CONTRACT * lots
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
    if in_pos:
        la = cb_last[n - 1]; buy = side == 1
        px = bc[la] if buy else ac[la]
        pnl = ((px - entry) if buy else (entry - px)) * CONTRACT * lots - commission_pct * (entry + px) * CONTRACT * lots
        balance += pnl; tot = pnl + realized_partial
        if ntr < MAX_TRADES:
            trades[ntr, 0] = entry_bar; trades[ntr, 1] = n - 1; trades[ntr, 2] = side; trades[ntr, 3] = entry
            trades[ntr, 4] = px; trades[ntr, 5] = orig_lots; trades[ntr, 6] = tot; trades[ntr, 7] = X_END
            trades[ntr, 8] = tot / (risk * CONTRACT * orig_lots) if risk > 0 else 0.0
            trades[ntr, 9] = m1_t[entry_m1]; trades[ntr, 10] = m1_t[la]; trades[ntr, 11] = balance; ntr += 1
        if tot > 0:
            gross_p += tot; wins += 1
        else:
            gross_l -= tot
        if risk > 0:
            sum_r += tot / (risk * CONTRACT * orig_lots)
    stats = np.zeros(10)
    stats[0] = balance - P[24]; stats[1] = ntr; stats[2] = wins; stats[3] = gross_p; stats[4] = gross_l
    stats[5] = max_dd_pct * 100.0; stats[6] = sum_r; stats[7] = max_dd; stats[8] = balance
    return stats, trades[:ntr], equity


class BtcBacktester:
    MAX_CACHE = 6

    def __init__(self, mkt):
        self.mkt = mkt
        self._cache = {}

    def signals(self, sig):
        key = tuple(sorted(sig.items()))
        if key not in self._cache:
            if len(self._cache) >= self.MAX_CACHE:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = compute_signals(self.mkt, sig)
        return self._cache[key]

    def run(self, sig, ea, t_from=None, t_to=None):
        S = self.signals(sig)
        cb = self.mkt.bars(sig["chart_tf"])
        m1 = self.mkt.m1
        tb = m1["t"][cb["first"]]
        start_bar = 210
        n_end = len(cb["t"])
        if t_from is not None:
            start_bar = max(start_bar, int(np.searchsorted(tb, t_from)))
        if t_to is not None:
            n_end = int(np.searchsorted(tb, t_to))
        sl_ = slice(0, n_end)
        stats, trades, equity = backtest(
            ea, int(sig["method"]), cb["t"][sl_], cb["first"][sl_], cb["last"][sl_], cb["c"][sl_],
            m1["t"], m1["bo"], m1["bh"], m1["bl"], m1["bc"], m1["ao"], m1["ah"], m1["al"], m1["ac"],
            S["side"][sl_], S["trend"][sl_], S["macro"][sl_], S["mean"][sl_], S["valid"][sl_], S["atr"][sl_], S["er"][sl_], start_bar)
        return stats, trades, equity[start_bar:n_end]


summarize = rt.summarize
