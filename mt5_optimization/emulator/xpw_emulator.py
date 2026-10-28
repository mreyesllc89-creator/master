#!/usr/bin/env python3
"""
XPW ShapeMap v0.9.2 + FlashGold -- Python emulation of the MT5 EA's PF preset.

Reads an MT5 chart export (File > Save As on the chart, tab-separated:
<DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>) or any
CSV with Date,Time,Open,High,Low,Close columns, and replays:

  * Shape-map core (ShapeMapV7Core.mqh): Wilder RSI(14), SMA fast 2 / slow 7
    on RSI, BOT/TOP squares with AllOn=true (ctx 1, no spacing), arming for
    TurnMax bars, Turn signal = cross held TurnHold bars.
  * Entry = Turn after hold (TurnEntry=2), candle-close evaluation
    (EnterTick=false), fill at next bar open with half-spread.
  * OppMode = Close only, LossRev off, trail off, TimeStop off.
  * ATR exits: SL = SlAtrM x ATR(14) at entry, TP = TpR x SL. Stop-first
    (worst case) when a bar touches both.
  * FlashGold direction filter (DirectionFilterCore.mqh, simplified): H1 TDI
    parent + H1/H2/H4 zones (>= 2 aligned), burst >= 0.5 ATR(H1), armed
    level = ask + 0.25 ATR (buy) / bid - 0.25 ATR (sell), 0.25 ATR no-trade
    band, trade only WITH the armed direction (fgfAgainst=false), permission
    lasts until the next signal.
  * Risk-% sizing (1 % of equity / SL distance), QtyMax, margin cap, lot step.

Differences from the MT5 tester, deliberately not modelled: tick-level fills,
variable spread, swap, the SigTF=10 relay on an M15 chart (the signal runs on
the chart bars here), BOT/TOP tick and CONT signal modes, Predict stop entries.

Usage:
  python3 xpw_emulator.py --csv XAUUSD_M5.csv --symbol XAUUSD
  python3 xpw_emulator.py --csv BTCUSD_M15.csv --symbol BTCUSD
  python3 xpw_emulator.py --synthetic XAUUSD      # format demo, random data
"""
import argparse, csv, math, os, sys
from datetime import datetime, timedelta

# --------------------------------------------------------------------------
# Symbol profiles (VT Markets assumptions; override with CLI flags)
# --------------------------------------------------------------------------
PROFILES = {
    "XAUUSD": dict(tick=0.01, contract=100.0, vol_step=0.01, vol_min=0.01, qty_max=50.0,
                   spread_pts=20.0, mgn_pct=1.0, sl_atr=2.0, tp_r=3.0, tf_minutes=5),
    "BTCUSD": dict(tick=0.01, contract=1.0, vol_step=0.01, vol_min=0.01, qty_max=1.0,
                   spread_pts=3000.0, mgn_pct=0.5, sl_atr=1.5, tp_r=4.0, tf_minutes=15),
}
RSI_LEN, FAST, SLOW, ATR_LEN = 14, 2, 7, 14
TURN_MAX, TURN_HOLD, ALL_CTX = 12, 2, 1
BOT_MINW, BOT_MAXW, TOP_MINW, TOP_MAXW = 1, 3, 1, 2
RISK_PCT, DEPOSIT = 1.0, 10000.0
FGF_BURST_ATR, FGF_ENTRY_ATR, FGF_BAND_ATR, FGF_MIN_ALIGNED = 0.5, 0.25, 0.25, 2

# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def load_csv(path):
    bars = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096); f.seek(0)
        delim = "\t" if sample.count("\t") > sample.count(",") else ","
        rd = csv.reader(f, delimiter=delim)
        header = next(rd)
        cols = [h.strip("<>").strip().upper() for h in header]
        ix = {c: i for i, c in enumerate(cols)}
        for row in rd:
            if not row or len(row) < 5: continue
            try:
                if "TIME" in ix and "DATE" in ix:
                    t = datetime.strptime(row[ix["DATE"]] + " " + row[ix["TIME"]], "%Y.%m.%d %H:%M:%S")
                else:
                    t = datetime.fromisoformat(row[ix.get("DATETIME", 0)])
                o, h, l, c = (float(row[ix[k]]) for k in ("OPEN", "HIGH", "LOW", "CLOSE"))
            except (ValueError, KeyError):
                continue
            bars.append((t, o, h, l, c))
    bars.sort()
    return bars

def synthetic(symbol, months=12, seed=7):
    """Random walk with volatility clustering. FORMAT DEMO ONLY."""
    import random
    rnd = random.Random(seed)
    p = PROFILES[symbol]
    price = 4000.0 if symbol == "XAUUSD" else 100000.0
    base_vol = (0.00055 if symbol == "XAUUSD" else 0.0016)   # per-bar sigma
    tf = p["tf_minutes"]
    t = datetime(2025, 10, 27, 0, 0)
    end = t + timedelta(days=30 * months)
    bars, vol, drift = [], base_vol, 0.0
    while t < end:
        if t.weekday() >= 5 and symbol == "XAUUSD":
            t += timedelta(minutes=tf); continue
        vol = max(base_vol * 0.4, min(base_vol * 3, vol * 0.985 + base_vol * 0.015 + abs(rnd.gauss(0, base_vol * 0.08))))
        drift = drift * 0.90 + rnd.gauss(0, vol * 0.01)
        o = price
        path = [o]
        for _ in range(4):
            path.append(path[-1] * (1 + drift + rnd.gauss(0, vol / 2)))
        c = path[-1]; h = max(path) * (1 + abs(rnd.gauss(0, vol / 4))); l = min(path) * (1 - abs(rnd.gauss(0, vol / 4)))
        bars.append((t, round(o, 2), round(h, 2), round(l, 2), round(c, 2)))
        price = c
        t += timedelta(minutes=tf)
    return bars

def resample(bars, minutes):
    out, cur = [], None
    for (t, o, h, l, c) in bars:
        key = t.replace(minute=(t.minute // minutes) * minutes if minutes < 60 else 0,
                        second=0, microsecond=0)
        if minutes >= 60:
            key = key.replace(hour=(t.hour // (minutes // 60)) * (minutes // 60))
        if cur is None or cur["key"] != key:
            if cur: out.append(cur)
            cur = dict(key=key, t=key, end=key + timedelta(minutes=minutes), o=o, h=h, l=l, c=c)
        else:
            cur["h"] = max(cur["h"], h); cur["l"] = min(cur["l"], l); cur["c"] = c
    if cur: out.append(cur)
    return out

# --------------------------------------------------------------------------
# Indicators
# --------------------------------------------------------------------------
def rsi_wilder(close, n):
    out = [None] * len(close); up = dn = 0.0
    for i in range(1, len(close)):
        u = max(close[i] - close[i - 1], 0.0); d = max(close[i - 1] - close[i], 0.0)
        if i <= n:
            up += u; dn += d
            if i < n: continue
            up /= n; dn /= n
        else:
            up = (up * (n - 1) + u) / n; dn = (dn * (n - 1) + d) / n
        out[i] = 100.0 if dn == 0 else (0.0 if up == 0 else 100 - 100 / (1 + up / dn))
    return out

def sma(series, n):
    out = [None] * len(series); window = []
    for i, v in enumerate(series):
        if v is None: window = []; continue
        window.append(v)
        if len(window) > n: window.pop(0)
        if len(window) == n: out[i] = sum(window) / n
    return out

def atr_pine(high, low, close, n):
    out = [None] * len(close); prev = None
    for i in range(len(close)):
        tr = high[i] - low[i] if i == 0 else max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        if i < n - 1: continue
        if i == n - 1:
            s = 0.0
            for k in range(n):
                s += high[k] - low[k] if k == 0 else max(high[k] - low[k], abs(high[k] - close[k - 1]), abs(low[k] - close[k - 1]))
            prev = s / n
        else:
            prev = (prev * (n - 1) + tr) / n
        out[i] = prev
    return out

# --------------------------------------------------------------------------
# Shape-map Turn signals (SigMode=1, TurnEntry=2, AllOn=true)
# --------------------------------------------------------------------------
def turn_signals(close):
    n = len(close)
    rsi = rsi_wilder(close, RSI_LEN); fast = sma(rsi, FAST); slow = sma(rsi, SLOW)
    valid = [fast[i] is not None and slow[i] is not None for i in range(n)]
    red = [valid[i] and fast[i] > slow[i] for i in range(n)]      # InvertFill: fast>slow = RED
    lime = [valid[i] and not red[i] for i in range(n)]
    def detect(i, want_red, minw, maxw, ctx):
        for w in range(minw, max(minw, maxw) + 1):
            ok = True
            def at(j, want): return 0 <= j < n and (red[j] if want else lime[j])
            for k in range(ctx):
                if not at(i - k, not want_red): ok = False; break
            for k in range(w):
                if not ok or not at(i - ctx - k, want_red): ok = False; break
            for k in range(ctx):
                if not ok or not at(i - ctx - w - k, not want_red): ok = False; break
            if ok: return True
        return False
    turn_up = [False] * n; turn_dn = [False] * n
    bot_armed = top_armed = False; bot_bar = top_bar = -1
    for i in range(n):
        if detect(i, True, BOT_MINW, BOT_MAXW, ALL_CTX): bot_armed, bot_bar = True, i
        if detect(i, False, TOP_MINW, TOP_MAXW, ALL_CTX): top_armed, top_bar = True, i
        if bot_armed and i - bot_bar > TURN_MAX: bot_armed = False
        if top_armed and i - top_bar > TURN_MAX: top_armed = False
        hold_up = hold_dn = True
        for k in range(TURN_HOLD + 1):
            j = i - k
            if j < 0 or not valid[j]: hold_up = hold_dn = False; continue
            if not fast[j] > slow[j]: hold_up = False
            if not fast[j] < slow[j]: hold_dn = False
        j = i - TURN_HOLD
        cv = j >= 1 and valid[j] and valid[j - 1]
        xu = cv and fast[j] > slow[j] and fast[j - 1] <= slow[j - 1]
        xd = cv and fast[j] < slow[j] and fast[j - 1] >= slow[j - 1]
        if bot_armed and xu and hold_up: turn_up[i] = True; bot_armed = False
        if top_armed and xd and hold_dn: turn_dn[i] = True; top_armed = False
    return turn_up, turn_dn

# --------------------------------------------------------------------------
# FlashGold direction filter (simplified port)
# --------------------------------------------------------------------------
def tdi_dirs(closes):
    rsi = rsi_wilder(closes, RSI_LEN); fast = sma(rsi, FAST)
    d = [0] * len(closes)
    for i in range(1, len(closes)):
        if fast[i] is not None and fast[i - 1] is not None:
            d[i] = 1 if fast[i] > fast[i - 1] else (-1 if fast[i] < fast[i - 1] else 0)
    return d

def last_closed_dir(tf_bars, dirs, when):
    """Direction of the last bar of tf_bars whose end <= when (fgfHtfClosed)."""
    lo, hi = 0, len(tf_bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if tf_bars[mid]["end"] <= when: lo = mid + 1
        else: hi = mid
    return dirs[lo - 1] if lo - 1 >= 0 else 99

def build_filter(chart, tick, spread_pts):
    h1 = resample(chart, 60); h2 = resample(chart, 120); h4 = resample(chart, 240)
    d1 = tdi_dirs([b["c"] for b in h1]); d2 = tdi_dirs([b["c"] for b in h2]); d4 = tdi_dirs([b["c"] for b in h4])
    atr = atr_pine([b["h"] for b in h1], [b["l"] for b in h1], [b["c"] for b in h1], 14)
    half = spread_pts * tick * 0.5
    points = []  # (armed_at, level, dir, atr)
    armed = None
    for i, b in enumerate(h1):
        parent = d1[i]
        zones = [d1[i], last_closed_dir(h2, d2, b["end"]), last_closed_dir(h4, d4, b["end"])]
        active = [z for z in zones if z != 99]
        aligned = sum(1 for z in active if parent != 0 and z == parent)
        ready = len(active) == 0 or aligned >= min(FGF_MIN_ALIGNED, len(active))
        zone_buy = parent == 1 and ready; zone_sell = parent == -1 and ready
        a = atr[i]
        if a is None or i == 0: points.append(armed); continue
        burst = b["c"] - h1[i - 1]["c"]
        thr = FGF_BURST_ATR * a
        buy = zone_buy and burst >= thr; sell = zone_sell and burst <= -thr
        if buy: armed = (b["end"], b["c"] + half + FGF_ENTRY_ATR * a, 1, a)
        elif sell: armed = (b["end"], b["c"] - half - FGF_ENTRY_ATR * a, -1, a)
        points.append(armed)
    def permission(when, value):
        lo, hi = 0, len(h1)
        while lo < hi:
            mid = (lo + hi) // 2
            if h1[mid]["end"] <= when: lo = mid + 1
            else: hi = mid
        p = points[lo - 1] if lo - 1 >= 0 else None
        if p is None: return False, False
        armed_at, level, d, a = p
        if when < armed_at: return False, False
        band = FGF_BAND_ATR * a
        in_up = value > level + band + tick / 2; in_dn = value < level - band - tick / 2
        return (in_up and d > 0), (in_dn and d < 0)      # fgfAgainst=false
    return permission

# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------
def run(bars, symbol, prof, use_filter=True):
    t = [b[0] for b in bars]; o = [b[1] for b in bars]; h = [b[2] for b in bars]; l = [b[3] for b in bars]; c = [b[4] for b in bars]
    n = len(bars)
    turn_up, turn_dn = turn_signals(c)
    atr = atr_pine(h, l, c, ATR_LEN)
    permission = build_filter(bars, prof["tick"], prof["spread_pts"]) if use_filter else (lambda when, v: (True, True))
    half = prof["spread_pts"] * prof["tick"] * 0.5
    equity = DEPOSIT; peak = equity; max_dd = 0.0; max_dd_pct = 0.0
    pos = None; trades = []; pending = None; eq_curve = [(t[0], equity)]
    blocked = 0; signals = 0; too_small = 0
    for i in range(1, n):
        # 1) fill pending entry at this bar's open
        if pending is not None and pos is None:
            side, sl_dist, idx = pending
            px = o[i] + half if side > 0 else o[i] - half
            risk = equity * RISK_PCT / 100.0
            q = risk / sl_dist if sl_dist > 0 else 0.0
            q = min(q, prof["qty_max"])
            q = min(q, 0.95 * equity / (c[idx] * prof["mgn_pct"] / 100.0))
            lots = math.floor(q / prof["contract"] / prof["vol_step"] + 1e-9) * prof["vol_step"]
            if lots >= prof["vol_min"]:
                units = lots * prof["contract"]
                pos = dict(side=side, entry=px, units=units, lots=lots, sl=px - side * sl_dist, tp=px + side * prof["tp_r"] * sl_dist,
                           open_t=t[i], open_i=i)
            else:
                too_small += 1
            pending = None
        # 2) manage open position on this bar (worst case: SL first)
        if pos is not None and i > pos["open_i"]:
            side = pos["side"]
            bid_h, bid_l = h[i] - half, l[i] - half
            ask_h, ask_l = h[i] + half, l[i] + half
            exit_px = reason = None
            if side > 0:
                if bid_l <= pos["sl"]: exit_px, reason = pos["sl"], "SL"
                elif bid_h >= pos["tp"]: exit_px, reason = pos["tp"], "TP"
            else:
                if ask_h >= pos["sl"]: exit_px, reason = pos["sl"], "SL"
                elif ask_l <= pos["tp"]: exit_px, reason = pos["tp"], "TP"
            if exit_px is not None:
                pnl = side * (exit_px - pos["entry"]) * pos["units"]
                equity += pnl
                trades.append(dict(open=pos["open_t"], close=t[i], side="buy" if side > 0 else "sell", lots=pos["lots"],
                                   entry=pos["entry"], exit=exit_px, pnl=pnl, reason=reason))
                pos = None
        # 3) evaluate confirmed signal at bar close
        if turn_up[i] or turn_dn[i]:
            signals += 1
            if pos is not None:
                # OppMode = Close only
                if (pos["side"] > 0 and turn_dn[i]) or (pos["side"] < 0 and turn_up[i]):
                    side = pos["side"]
                    exit_px = c[i] - half if side > 0 else c[i] + half
                    pnl = side * (exit_px - pos["entry"]) * pos["units"]
                    equity += pnl
                    trades.append(dict(open=pos["open_t"], close=t[i], side="buy" if side > 0 else "sell", lots=pos["lots"],
                                       entry=pos["entry"], exit=exit_px, pnl=pnl, reason="opp signal"))
                    pos = None
            if pos is None and atr[i] is not None and not (turn_up[i] and turn_dn[i]):
                buy_ok, sell_ok = permission(t[i] + timedelta(minutes=prof["tf_minutes"]), c[i])
                side = 1 if turn_up[i] else -1
                if (side > 0 and buy_ok) or (side < 0 and sell_ok):
                    pending = (side, prof["sl_atr"] * atr[i], i)
                else:
                    blocked += 1
        peak = max(peak, equity)
        dd = peak - equity
        if dd > max_dd: max_dd = dd; max_dd_pct = dd / peak * 100 if peak > 0 else 0
        if i % 50 == 0: eq_curve.append((t[i], equity))
    return dict(trades=trades, equity=equity, max_dd=max_dd, max_dd_pct=max_dd_pct, eq_curve=eq_curve,
                signals=signals, blocked=blocked, too_small=too_small, bars=n, start=t[0], end=t[-1])

# --------------------------------------------------------------------------
# Report (MT5 Strategy Tester style)
# --------------------------------------------------------------------------
def report(res, symbol, prof, title, data_note):
    tr = res["trades"]; wins = [x for x in tr if x["pnl"] > 0]; losses = [x for x in tr if x["pnl"] <= 0]
    gp = sum(x["pnl"] for x in wins); gl = -sum(x["pnl"] for x in losses); net = gp - gl
    pf = gp / gl if gl > 0 else float("inf") if gp > 0 else 0.0
    longs = [x for x in tr if x["side"] == "buy"]; shorts = [x for x in tr if x["side"] == "sell"]
    def pct(a, b): return 100.0 * a / b if b else 0.0
    # consecutive runs
    def run_max(sign):
        best = cur = 0
        for x in tr:
            if (x["pnl"] > 0) == sign: cur += 1; best = max(best, cur)
            else: cur = 0
        return best
    L = []
    L.append("=" * 78)
    L.append(f" {title}")
    L.append(f" {data_note}")
    L.append("=" * 78)
    L.append(f" Symbol: {symbol}   Period: {prof['tf_minutes']}-minute chart   Bars: {res['bars']:,}")
    L.append(f" Range: {res['start']:%Y.%m.%d %H:%M} -> {res['end']:%Y.%m.%d %H:%M}   Deposit: {DEPOSIT:,.0f} USD")
    L.append(f" Preset: Turn after-hold, candle close, close-only opposite, ATR exits SL {prof['sl_atr']} x ATR14, TP {prof['tp_r']}R,")
    L.append(f"         no trail, no loss-rev, FlashGold H1 filter with-direction, Risk 1 %, spread {prof['spread_pts']:.0f} pts")
    L.append("-" * 78)
    L.append(f" Turn signals: {res['signals']:>6}    blocked by filter: {res['blocked']:>6}    below min lot: {res['too_small']:>4}    trades: {len(tr)}")
    L.append("-" * 78)
    L.append(f" Total Net Profit:      {net:>12,.2f}    Gross Profit:   {gp:>12,.2f}    Gross Loss:  {-gl:>12,.2f}")
    L.append(f" Profit Factor:         {pf:>12.2f}    Expected Payoff: {net / len(tr) if tr else 0:>11,.2f}    Final equity: {res['equity']:>10,.2f}")
    L.append(f" Max Equity Drawdown:   {res['max_dd']:>12,.2f} ({res['max_dd_pct']:.2f} %)    Recovery Factor: {net / res['max_dd'] if res['max_dd'] > 0 else 0:.2f}")
    L.append(f" Total Trades:          {len(tr):>12}    Short: {len(shorts)} ({pct(len([x for x in shorts if x['pnl'] > 0]), len(shorts)):.1f} % won)"
             f"    Long: {len(longs)} ({pct(len([x for x in longs if x['pnl'] > 0]), len(longs)):.1f} % won)")
    L.append(f" Profit Trades:         {len(wins):>6} ({pct(len(wins), len(tr)):.1f} %)    Loss Trades: {len(losses)} ({pct(len(losses), len(tr)):.1f} %)")
    L.append(f" Largest profit trade:  {max((x['pnl'] for x in tr), default=0):>12,.2f}    Largest loss trade: {min((x['pnl'] for x in tr), default=0):>12,.2f}")
    L.append(f" Average profit trade:  {gp / len(wins) if wins else 0:>12,.2f}    Average loss trade: {-gl / len(losses) if losses else 0:>12,.2f}")
    L.append(f" Max consecutive wins:  {run_max(True):>12}    Max consecutive losses: {run_max(False)}")
    exits = {}
    for x in tr: exits[x["reason"]] = exits.get(x["reason"], 0) + 1
    L.append(f" Exit reasons:          " + ", ".join(f"{k} {v}" for k, v in sorted(exits.items())))
    # monthly table
    L.append("-" * 78)
    L.append(" Month      Trades   Net P/L      PF    Win%")
    months = {}
    for x in tr:
        k = x["close"].strftime("%Y-%m"); m = months.setdefault(k, [0, 0.0, 0.0, 0.0, 0])
        m[0] += 1; m[1] += x["pnl"]
        if x["pnl"] > 0: m[2] += x["pnl"]; m[4] += 1
        else: m[3] -= x["pnl"]
    for k in sorted(months):
        m = months[k]; mpf = m[2] / m[3] if m[3] > 0 else float("inf")
        L.append(f" {k}   {m[0]:>6}   {m[1]:>9,.2f}   {mpf:>5.2f}   {pct(m[4], m[0]):>5.1f}")
    # ASCII equity curve
    L.append("-" * 78)
    L.append(" Equity curve (balance after closed trades, 60 columns)")
    eq = [DEPOSIT]
    for x in tr: eq.append(eq[-1] + x["pnl"])
    if len(eq) > 1:
        cols = 60; rows = 12
        step = max(1, len(eq) // cols)
        samp = [eq[min(len(eq) - 1, i * step)] for i in range(cols)]
        lo, hi = min(samp), max(samp)
        grid = [[" "] * cols for _ in range(rows)]
        for x, v in enumerate(samp):
            y = rows - 1 - int((v - lo) / (hi - lo) * (rows - 1)) if hi > lo else rows // 2
            grid[y][x] = "#"
        for r, line in enumerate(grid):
            label = f"{hi - (hi - lo) * r / (rows - 1):>9,.0f} |" if r in (0, rows // 2, rows - 1) else " " * 10 + "|"
            L.append(" " + label + "".join(line))
        L.append(" " * 11 + "+" + "-" * cols)
    L.append("=" * 78)
    return "\n".join(L)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv"); ap.add_argument("--symbol", default="XAUUSD", choices=list(PROFILES))
    ap.add_argument("--synthetic", choices=list(PROFILES))
    ap.add_argument("--months", type=int, default=12); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-filter", action="store_true"); ap.add_argument("--spread", type=float)
    ap.add_argument("--sl-atr", type=float); ap.add_argument("--tp-r", type=float); ap.add_argument("--tf", type=int)
    ap.add_argument("--trades-csv")
    a = ap.parse_args()
    symbol = a.synthetic or a.symbol
    prof = dict(PROFILES[symbol])
    if a.spread is not None: prof["spread_pts"] = a.spread
    if a.sl_atr is not None: prof["sl_atr"] = a.sl_atr
    if a.tp_r is not None: prof["tp_r"] = a.tp_r
    if a.tf is not None: prof["tf_minutes"] = a.tf
    if a.synthetic:
        bars = synthetic(symbol, a.months, a.seed)
        note = "*** SYNTHETIC RANDOM-WALK DATA: layout demo only, the numbers carry no information ***"
    else:
        if not a.csv: ap.error("--csv or --synthetic required")
        bars = load_csv(a.csv); note = f"Data: {os.path.basename(a.csv)} ({len(bars):,} bars)"
        if len(bars) > 1:
            prof["tf_minutes"] = int((bars[1][0] - bars[0][0]).total_seconds() // 60) or prof["tf_minutes"]
    res = run(bars, symbol, prof, use_filter=not a.no_filter)
    print(report(res, symbol, prof, f"XPW ShapeMap v0.9.2 + FlashGold PF preset -- Python emulation ({symbol})", note))
    if a.trades_csv:
        with open(a.trades_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["open", "close", "side", "lots", "entry", "exit", "pnl", "reason"])
            w.writeheader(); w.writerows(res["trades"])
        print(f"trades written to {a.trades_csv}")

if __name__ == "__main__":
    main()
