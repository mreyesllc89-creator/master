#!/usr/bin/env python3
"""
xpw_backtest.py - Python replica of the XPW Breakout v2.01 Pine v6 strategy,
used to calibrate geometry + cost parameters for BTCUSD.

Replicates the TradingView broker emulator WITHOUT bar magnifier:
  * strategy logic runs once per bar at bar close; orders placed on bar i are
    active from bar i+1
  * intrabar path: close >= open -> open, low, high, close
                   close <  open -> open, high, low, close
  * stop entries fill at the stop level (or the open when gapped through),
    adverse slippage + half spread added
  * OCA: one straddle leg filling cancels the other on the same bar
  * bracket exit (stop + limit) is live from the entry fill, including the
    remainder of the fill bar. Stop and limit inside the same path segment:
    STOP wins (conservative)
  * trail 'bar' mode  = v2.01 (ratchet recomputed at bar close from close,
    applies from the next bar)
  * trail 'tick' mode = ratchet updated at every path node (open, lo/hi,
    hi/lo, close) and the updated stop is live for the rest of the bar

Usage:
  python3 xpw_backtest.py run    --tf 60 --sl-mode pct --sl 0.1 --tp-r 2.5 --barsn 5 --buf 1.0 --trail bar --cost cfd_std
  python3 xpw_backtest.py parity
  python3 xpw_backtest.py sweep  [--tfs 15,30,60,240,1] [--jobs 4]
  python3 xpw_backtest.py geometry
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
RESULTS_DIR = os.path.join(HERE, "results")
TF_FILES = {tf: os.path.join(DATA_DIR, f"BTCUSD_{tf}.csv") for tf in ("1", "15", "30", "60", "240")}

INITIAL_CAPITAL = 100000.0

# --------------------------------------------------------------------------
# Cost presets: (commission_pct per side, commission_cash per contract per
# side, spread_usd (full), slippage_usd per side)
# --------------------------------------------------------------------------
COST_PRESETS = {
    "none":     dict(commission_pct=0.0,    commission_cash=0.0,   spread_usd=0.0,  slippage_usd=0.0),
    "exchange": dict(commission_pct=0.0005, commission_cash=0.0,   spread_usd=0.0,  slippage_usd=2.0),
    "cfd_std":  dict(commission_pct=0.0,    commission_cash=0.0,   spread_usd=17.0, slippage_usd=5.0),
    "cfd_raw":  dict(commission_pct=0.0,    commission_cash=3.0,   spread_usd=6.0,  slippage_usd=5.0),
    # v2.01 Pine header (gold): 0.003 cash per contract per side, 30 ticks slippage (BTC tick 0.01 -> $0.30)
    "v201":     dict(commission_pct=0.0,    commission_cash=0.003, spread_usd=0.0,  slippage_usd=0.30),
}


# --------------------------------------------------------------------------
# Indicators (no lookahead)
# --------------------------------------------------------------------------
def atr_wilder(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    """ta.atr(n): RMA of true range. RMA seeded with SMA of first n TRs (ta.rma), na before."""
    N = len(high)
    tr = np.empty(N)
    tr[0] = high[0] - low[0]
    pc = close[:-1]
    tr[1:] = np.maximum.reduce([high[1:] - low[1:], np.abs(high[1:] - pc), np.abs(low[1:] - pc)])
    out = np.full(N, np.nan)
    if N < n:
        return out
    a = tr[:n].mean()
    out[n - 1] = a
    alpha = 1.0 / n
    for i in range(n, N):
        a = alpha * tr[i] + (1 - alpha) * a
        out[i] = a
    return out


def pivots(high: np.ndarray, low: np.ndarray, n: int):
    """ta.pivothigh(high,n,n) / ta.pivotlow(low,n,n): value is returned on bar i+n
    (confirmation bar) for a pivot at bar i. Ported from data_stats.py (validated
    100% against the TradingView 'Swing High'/'Swing Low' export for n=5)."""
    N = len(high)
    ph = np.full(N, np.nan)
    pl = np.full(N, np.nan)
    for i in range(n, N - n):
        w = high[i - n:i + n + 1]
        if high[i] == w.max() and (w[:n] < high[i]).all() and (w[n + 1:] <= high[i]).all():
            ph[i + n] = high[i]
        w2 = low[i - n:i + n + 1]
        if low[i] == w2.min() and (w2[:n] > low[i]).all() and (w2[n + 1:] >= low[i]).all():
            pl[i + n] = low[i]
    return ph, pl


def ffill(a: np.ndarray, seed: float = np.nan) -> np.ndarray:
    out = np.empty_like(a)
    cur = seed
    for i in range(len(a)):
        if not np.isnan(a[i]):
            cur = a[i]
        out[i] = cur
    return out


def percentrank(x: np.ndarray, length: int) -> np.ndarray:
    """ta.percentrank(x, length): % of the previous `length` values <= current value."""
    N = len(x)
    out = np.full(N, np.nan)
    for i in range(length, N):
        win = x[i - length:i]
        if np.isnan(x[i]) or np.isnan(win).any():
            continue
        out[i] = 100.0 * np.sum(win <= x[i]) / length
    return out


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
@dataclass
class TFData:
    tf: str
    time: list
    hour: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    csv_swingH: np.ndarray
    csv_swingL: np.ndarray
    csv_trail: np.ndarray
    atr: np.ndarray
    piv: dict = field(default_factory=dict)  # barsN -> (swingH ffilled, swingL ffilled)

    def swings(self, barsn: int, seed_from_csv: bool = False):
        key = (barsn, seed_from_csv)
        if key not in self.piv:
            ph, pl = pivots(self.high, self.low, barsn)
            sH = ffill(ph, self.csv_swingH[0] if seed_from_csv else np.nan)
            sL = ffill(pl, self.csv_swingL[0] if seed_from_csv else np.nan)
            self.piv[key] = (sH, sL)
        return self.piv[key]


def load_tf(tf: str, atr_len: int = 14, assert_pivots: bool = True) -> TFData:
    df = pd.read_csv(TF_FILES[tf])
    t = df["time"].astype(str).tolist()
    hour = np.array([int(s[11:13]) for s in t])  # exchange/chart-local hour as exported
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    d = TFData(tf=tf, time=t, hour=hour, open=o, high=h, low=l, close=c,
               csv_swingH=df["Swing High"].to_numpy(dtype=float),
               csv_swingL=df["Swing Low"].to_numpy(dtype=float),
               csv_trail=df["Trail"].to_numpy(dtype=float),
               atr=atr_wilder(h, l, c, atr_len))
    if assert_pivots:
        sH, sL = d.swings(5, seed_from_csv=False)
        both = ~np.isnan(sH) & ~np.isnan(d.csv_swingH)
        assert np.allclose(sH[both], d.csv_swingH[both]), f"TF{tf}: swingH mismatch vs CSV"
        both = ~np.isnan(sL) & ~np.isnan(d.csv_swingL)
        assert np.allclose(sL[both], d.csv_swingL[both]), f"TF{tf}: swingL mismatch vs CSV"
    return d


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
@dataclass
class Config:
    tf: str = "60"
    sl_mode: str = "pct"         # 'pct' | 'atr'
    sl_value: float = 0.1        # percent of entry level, or ATR multiple
    tp_r: float = 2.5            # TP distance as multiple of SL distance
    barsn: int = 5
    buf_atr: float = 1.0         # entry buffer = ATR * buf_atr
    trail: str = "bar"           # 'off' | 'bar' | 'tick'
    trg_atr: float = 1.0
    dst_atr: float = 1.5
    atr_len: int = 14
    cost_preset: str = "cfd_std"
    commission_pct: float = 0.0
    commission_cash: float = 0.0
    spread_usd: float = 0.0
    slippage_usd: float = 0.0
    sizing: str = "fixed"        # 'fixed' | 'risk'
    fixed_qty: float = 1.0
    risk_pct: float = 4.0
    max_qty: float = 50.0
    qty_step: float = 0.001
    sh: int = 0                  # session start hour (0 = off)
    eh: int = 0
    use_gate: bool = False
    comp_len: int = 200
    comp_pct: float = 30.0
    seed_swings: bool = False    # seed swingH/L from first CSV row (parity only)
    close_at_end: bool = True

    def apply_preset(self):
        p = COST_PRESETS[self.cost_preset]
        self.commission_pct = p["commission_pct"]
        self.commission_cash = p["commission_cash"]
        self.spread_usd = p["spread_usd"]
        self.slippage_usd = p["slippage_usd"]
        return self


@dataclass
class Trade:
    side: int               # +1 long, -1 short
    entry_bar: int
    exit_bar: int
    order_level: float
    entry_price: float
    exit_price: float
    qty: float
    sl_dist: float
    exit_kind: str          # tp | sl | trail | end
    gross: float
    cost: float
    net: float
    bars_held: int
    r_mult: float


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------
def run_backtest(d: TFData, cfg: Config, want_trades: bool = True):
    o, h, l, c, atr = d.open, d.high, d.low, d.close, d.atr
    N = len(o)
    sH, sL = d.swings(cfg.barsn, cfg.seed_swings)
    hs = 0.5 * cfg.spread_usd
    slip = cfg.slippage_usd + hs      # adverse move on every stop/market fill
    cpct, ccash = cfg.commission_pct, cfg.commission_cash
    trail_on = cfg.trail != "off"
    tick_mode = cfg.trail == "tick"

    # session
    if cfg.sh != 0 and cfg.eh != 0 and cfg.sh > cfg.eh:
        in_session = (d.hour >= cfg.sh) | (d.hour < cfg.eh)
    else:
        in_session = np.ones(N, dtype=bool)
        if cfg.sh != 0:
            in_session &= d.hour >= cfg.sh
        if cfg.eh != 0:
            in_session &= d.hour < cfg.eh
    # compression gate
    if cfg.use_gate:
        with np.errstate(invalid="ignore", divide="ignore"):
            comp = np.where(atr > 0, (sH - sL) / atr, np.nan)
        pr = percentrank(comp, cfg.comp_len)
        gate_ok = ~np.isnan(pr) & (pr <= cfg.comp_pct)
    else:
        gate_ok = np.ones(N, dtype=bool)

    def commission(price, qty):
        return cpct * price * qty + ccash * qty

    equity = INITIAL_CAPITAL
    trades: list[Trade] = []
    in_pos = np.zeros(N, dtype=bool)
    trail_series = np.full(N, np.nan)

    # pending orders: dict(level, sl_dist, tp, qty) or None
    pend_long = None
    pend_short = None
    # position: dict(side, entry_bar, order_level, entry, qty, sl_dist, stop, tp, sl0, trail)
    pos = None

    def open_position(side, bar, order, fill):
        # `fill` = ideal fill (stop level, or the open when gapped through); actual = ideal + adverse slippage + half spread.
        # SL/TP/trail are anchored on the ACTUAL avg price (strategy.position_avg_price includes slippage), as in TradingView.
        nonlocal pos
        entry = fill + side * slip
        pos = dict(side=side, entry_bar=bar, order_level=order["level"], entry=entry, entry_ideal=fill,
                   qty=order["qty"], sl_dist=order["sl_dist"],
                   stop=order["level"] - side * order["sl_dist"],   # fill-bar bracket on order level
                   tp=order["level"] + side * order["sl_dist"] * cfg.tp_r,
                   sl0=None, trail=None, entry_cost=commission(entry, order["qty"]))

    def close_position(bar, fill, kind, market):
        # gross = P&L at ideal fills (no spread/slippage); cost = commission + spread + slippage actually paid; net = gross - cost
        nonlocal pos, equity
        side, qty = pos["side"], pos["qty"]
        exitp = fill - side * slip if market else fill
        gross = side * (fill - pos["entry_ideal"]) * qty
        friction = side * (pos["entry"] - pos["entry_ideal"]) * qty + side * (fill - exitp) * qty
        cost = pos["entry_cost"] + commission(exitp, qty) + friction
        net = gross - cost
        equity += net
        risk = pos["sl_dist"] * qty
        trades.append(Trade(side, pos["entry_bar"], bar, pos["order_level"], pos["entry"], exitp, qty,
                            pos["sl_dist"], kind, gross, cost, net, bar - pos["entry_bar"],
                            net / risk if risk > 0 else 0.0))
        pos = None

    def stop_kind():
        # 'trail' if the stop has been ratcheted beyond the initial SL, else 'sl'
        if pos["sl0"] is None:
            return "sl"
        s = pos["side"]
        return "trail" if s * (pos["stop"] - pos["sl0"]) > 1e-9 else "sl"

    def tick_ratchet(price, a):
        # tick-mode ratchet update at a path node, using ATR `a`
        if pos is None or not trail_on or pos["sl0"] is None or np.isnan(a):
            return
        s = pos["side"]
        if s * (price - pos["entry"]) > a * cfg.trg_atr:
            cand = price - s * a * cfg.dst_atr
            if s * (cand - pos["stop"]) > 0:
                pos["stop"] = cand

    def check_exit_segment(bar, a, b):
        """Position open; price moves a -> b. Returns True if closed."""
        s = pos["side"]
        stop, tp = pos["stop"], pos["tp"]
        lo, hi = (a, b) if a <= b else (b, a)
        stop_hit = lo <= stop <= hi
        tp_hit = lo <= tp <= hi
        if stop_hit:                       # stop first when both are in the segment
            close_position(bar, stop, stop_kind(), market=True)
            return True
        if tp_hit:
            close_position(bar, tp, "tp", market=False)
            return True
        return False

    for i in range(N):
        oi, hi_, li, ci = o[i], h[i], l[i], c[i]
        nodes = (oi, li, hi_, ci) if ci >= oi else (oi, hi_, li, ci)
        a_prev = atr[i - 1] if i > 0 else np.nan

        # ---------------- intrabar processing of bar i ----------------
        # Open node
        if pos is not None:
            s = pos["side"]
            if s * (oi - pos["stop"]) <= 0:
                close_position(i, oi, stop_kind(), market=True)          # gapped through stop
            elif s * (oi - pos["tp"]) >= 0:
                close_position(i, oi, "tp", market=False)                # gapped through TP: better fill
            else:
                if tick_mode:
                    tick_ratchet(oi, a_prev)
        elif pend_long is not None or pend_short is not None:
            if pend_long is not None and oi >= pend_long["level"]:
                open_position(+1, i, pend_long, oi)
                pend_long = pend_short = None
            elif pend_short is not None and oi <= pend_short["level"]:
                open_position(-1, i, pend_short, oi)
                pend_long = pend_short = None

        # Segments
        for k in range(3):
            a, b = nodes[k], nodes[k + 1]
            if pos is not None:
                if check_exit_segment(i, a, b):
                    continue  # flat now; no re-entry possible within the bar (orders cancelled by OCA / none placed)
                if tick_mode and k < 2:
                    tick_ratchet(b, a_prev)
            elif pend_long is not None or pend_short is not None:
                filled = None
                if b > a:
                    if pend_long is not None and a < pend_long["level"] <= b:
                        filled = (+1, pend_long, pend_long["level"])
                else:
                    if pend_short is not None and b <= pend_short["level"] < a:
                        filled = (-1, pend_short, pend_short["level"])
                if filled is not None:
                    side, order, fp = filled
                    open_position(side, i, order, fp)
                    pend_long = pend_short = None
                    # bracket live for the remainder of this segment fp -> b, then later segments
                    if check_exit_segment(i, fp, b):
                        continue
                    if tick_mode and k < 2:
                        tick_ratchet(b, a_prev)

        # ---------------- bar close logic (Pine script runs here) ----------------
        ai = atr[i]
        if pos is not None:
            s = pos["side"]
            entry = pos["entry"]
            if pos["sl0"] is None:
                # first close after the fill: bracket switches to avg-price based levels
                sl_dist = entry * cfg.sl_value / 100.0 if cfg.sl_mode == "pct" else pos["sl_dist"]
                pos["sl0"] = entry - s * sl_dist
                pos["tp"] = entry + s * sl_dist * cfg.tp_r
                pos["stop"] = pos["sl0"]          # Pine: trailL := na(trailL) ? sl0L : trailL
                pos["trail"] = pos["stop"]
            if trail_on and not np.isnan(ai):
                if s * (ci - entry) > ai * cfg.trg_atr:
                    cand = ci - s * ai * cfg.dst_atr
                    if s * (cand - pos["stop"]) > 0:
                        pos["stop"] = cand
            in_pos[i] = True
            trail_series[i] = pos["stop"]
            pend_long = pend_short = None   # Pine: cancel while not flat
        else:
            flat = True
            can_arm = flat and in_session[i] and gate_ok[i]
            swH, swL = sH[i], sL[i]
            buffer = ai * cfg.buf_atr if not np.isnan(ai) else np.nan
            pend_long = pend_short = None
            if can_arm and not np.isnan(buffer):
                if not np.isnan(swH) and swH > ci and ci < swH - buffer:
                    sl_dist = swH * cfg.sl_value / 100.0 if cfg.sl_mode == "pct" else ai * cfg.sl_value
                    qty = calc_qty(cfg, equity, sl_dist)
                    if qty > 0 and sl_dist > 0:
                        pend_long = dict(level=swH, sl_dist=sl_dist, qty=qty)
                if not np.isnan(swL) and swL < ci and ci > swL + buffer:
                    sl_dist = swL * cfg.sl_value / 100.0 if cfg.sl_mode == "pct" else ai * cfg.sl_value
                    qty = calc_qty(cfg, equity, sl_dist)
                    if qty > 0 and sl_dist > 0:
                        pend_short = dict(level=swL, sl_dist=sl_dist, qty=qty)

    if pos is not None and cfg.close_at_end:
        close_position(N - 1, c[-1], "end", market=True)

    return trades, in_pos, trail_series


def calc_qty(cfg: Config, equity: float, sl_dist: float) -> float:
    if cfg.sizing == "risk" and sl_dist > 0:
        raw = equity * cfg.risk_pct / 100.0 / sl_dist
    else:
        raw = cfg.fixed_qty
    if raw <= 0 or math.isnan(raw):
        raw = cfg.fixed_qty
    q = min(raw, cfg.max_qty)
    q = math.floor(q / cfg.qty_step + 1e-9) * cfg.qty_step
    return q


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def metrics(trades: list[Trade]) -> dict:
    n = len(trades)
    m = dict(n_trades=n, n_long=0, n_short=0, win_rate=np.nan, gross_pnl=0.0, total_cost=0.0, net_pnl=0.0,
             cost_to_gross_ratio=np.nan, profit_factor_net=np.nan, expectancy_R=np.nan,
             max_drawdown_net=0.0, avg_bars_held=np.nan, exit_tp=0.0, exit_sl=0.0, exit_trail=0.0, exit_end=0.0,
             same_bar_exit_share=np.nan, avg_net_per_trade=np.nan)
    if n == 0:
        return m
    net = np.array([t.net for t in trades])
    gross = np.array([t.gross for t in trades])
    cost = np.array([t.cost for t in trades])
    m["n_long"] = sum(1 for t in trades if t.side > 0)
    m["n_short"] = n - m["n_long"]
    m["win_rate"] = float((net > 0).mean())
    m["gross_pnl"] = float(gross.sum())
    m["total_cost"] = float(cost.sum())
    m["net_pnl"] = float(net.sum())
    absg = np.abs(gross).sum()
    m["cost_to_gross_ratio"] = float(cost.sum() / absg) if absg > 0 else np.nan
    wins, losses = net[net > 0].sum(), -net[net < 0].sum()
    m["profit_factor_net"] = float(wins / losses) if losses > 0 else (np.inf if wins > 0 else np.nan)
    m["expectancy_R"] = float(np.mean([t.r_mult for t in trades]))
    eq = INITIAL_CAPITAL + np.cumsum(net)
    peak = np.maximum.accumulate(np.concatenate([[INITIAL_CAPITAL], eq]))
    m["max_drawdown_net"] = float((peak[1:] - eq).max())
    m["avg_bars_held"] = float(np.mean([t.bars_held for t in trades]))
    for k in ("tp", "sl", "trail", "end"):
        m["exit_" + k] = sum(1 for t in trades if t.exit_kind == k) / n
    m["same_bar_exit_share"] = sum(1 for t in trades if t.bars_held == 0) / n   # entry and exit inside the same bar: outcome set by the OHLC path assumption
    m["avg_net_per_trade"] = float(net.mean())
    return m


def print_trades(trades: list[Trade], d: TFData):
    print(f"{'#':>3} {'side':>5} {'entry_bar':>9} {'entry_time':>25} {'exit_bar':>8} {'level':>10} {'entry':>10} "
          f"{'exit':>10} {'qty':>6} {'sl_dist':>8} {'kind':>5} {'gross':>10} {'cost':>8} {'net':>10} {'R':>6} {'bars':>4}")
    for j, t in enumerate(trades, 1):
        print(f"{j:>3} {'LONG' if t.side > 0 else 'SHORT':>5} {t.entry_bar:>9} {d.time[t.entry_bar]:>25} {t.exit_bar:>8} "
              f"{t.order_level:>10.2f} {t.entry_price:>10.2f} {t.exit_price:>10.2f} {t.qty:>6.3f} {t.sl_dist:>8.2f} "
              f"{t.exit_kind:>5} {t.gross:>10.2f} {t.cost:>8.2f} {t.net:>10.2f} {t.r_mult:>6.2f} {t.bars_held:>4}")


# --------------------------------------------------------------------------
# Parity vs TradingView 'Trail' column
# --------------------------------------------------------------------------
def v201_config(tf: str, cost_preset: str = "v201", **kw) -> Config:
    cfg = Config(tf=tf, sl_mode="pct", sl_value=0.1, tp_r=2.5, barsn=5, buf_atr=1.0, trail="bar",
                 trg_atr=1.0, dst_atr=1.5, cost_preset=cost_preset, sizing="fixed", fixed_qty=1.0)
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg.apply_preset()


PARITY_VARIANTS = {
    # v2.01 Pine header defaults
    "v201_defaults": dict(tp_r=2.5, dst_atr=1.5),
    # settings inferred from the TV 'Trail' column: initial trail = avg*0.999 (SL 0.1%), entry = level +/- 0.30
    # (slippage 30 ticks), every ratchet step has (close - trail)/ATR = 1.900, and positions were held through
    # bars exceeding a 0.25% TP but never a 0.5% one -> TP 0.5% (= 5R at SL 0.1%), trail distance 1.9 ATR
    "tv_inferred": dict(tp_r=5.0, dst_atr=1.9),
}


def _episodes(mask):
    eps, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        if not v and start is not None:
            eps.append((start, i - 1)); start = None
    if start is not None:
        eps.append((start, len(mask) - 1))
    return eps


def parity(tfs=("15", "30", "60", "240", "1"), verbose=True) -> dict:
    out = {}
    for tf in tfs:
        d = load_tf(tf)
        tv = ~np.isnan(d.csv_trail)
        tv_eps = _episodes(tv)
        res_tf = dict(bars=int(len(d.open)), tv_bars_in_pos=int(tv.sum()), tv_episodes=len(tv_eps), tv_episode_ranges=tv_eps)
        # implied TV entry price from first trail value of each episode (trail0 = avg*(1 -/+ 0.001))
        implied = []
        sH, sL = d.swings(5, True)
        for a, b in tv_eps:
            t0 = d.csv_trail[a]
            side = 1 if t0 < d.close[a] else -1
            avg = t0 / 0.999 if side > 0 else t0 / 1.001
            lvl = sH[a] if side > 0 else sL[a]
            implied.append(dict(bar=a, side=side, implied_avg=float(avg), level=float(lvl), avg_minus_level=float(avg - lvl)))
        res_tf["tv_implied_fills"] = implied
        res_tf["tv_fills_at_level_plus_slip"] = int(sum(1 for x in implied if abs(abs(x["avg_minus_level"]) - 0.30) < 0.01))
        for vname, vkw in PARITY_VARIANTS.items():
            cfg = v201_config(tf, seed_swings=True, **vkw)
            trades, in_pos, trail = run_backtest(d, cfg)
            both = in_pos & tv
            union = in_pos | tv
            diff = np.abs(trail[both] - d.csv_trail[both]) if both.any() else np.array([])
            eng_eps = _episodes(in_pos)
            ep_match = sum(1 for e in eng_eps if e in tv_eps)
            r = dict(variant=vname, params=vkw, engine_bars_in_pos=int(in_pos.sum()), overlap_bars=int(both.sum()),
                     jaccard=float(both.sum() / union.sum()) if union.sum() else np.nan,
                     recall_of_tv=float(both.sum() / tv.sum()) if tv.sum() else np.nan,
                     precision_of_engine=float(both.sum() / in_pos.sum()) if in_pos.sum() else np.nan,
                     engine_trades=len(trades), engine_episodes=len(eng_eps), episodes_identical=ep_match,
                     engine_episode_ranges=eng_eps,
                     trail_abs_diff_median=float(np.median(diff)) if len(diff) else np.nan,
                     trail_abs_diff_max=float(diff.max()) if len(diff) else np.nan,
                     net_pnl=metrics(trades)["net_pnl"], n_trades=len(trades))
            res_tf[vname] = r
            if verbose:
                print(f"\n=== PARITY TF {tf}m  variant={vname} {vkw}  (seed_swings=True, cost=v201) ===")
                for k, v in r.items():
                    print(f"  {k}: {v}")
                if vname == "v201_defaults":
                    print(f"  tv_bars_in_pos: {res_tf['tv_bars_in_pos']}  tv_episodes: {res_tf['tv_episodes']}  tv_episode_ranges: {tv_eps}")
                    print(f"  tv fills at level+/-0.30: {res_tf['tv_fills_at_level_plus_slip']} of {len(implied)}")
                    print_trades(trades, d)
        out[tf] = res_tf
    return out


# --------------------------------------------------------------------------
# Sweep
# --------------------------------------------------------------------------
GRID = dict(
    sl=[("pct", 0.1), ("pct", 0.25), ("pct", 0.5), ("pct", 1.0), ("atr", 1.0), ("atr", 1.5), ("atr", 2.0), ("atr", 3.0)],
    tp_r=[1.0, 1.5, 2.0, 2.5, 3.0],
    barsn=[3, 5, 8],
    buf_atr=[0.5, 1.0, 2.0],
    trail=["off", "bar", "tick"],
    cost=["none", "exchange", "cfd_std", "cfd_raw"],
)

_TFDATA: dict[str, TFData] = {}


def _get_tf(tf: str) -> TFData:
    if tf not in _TFDATA:
        _TFDATA[tf] = load_tf(tf, assert_pivots=False)
    return _TFDATA[tf]


def _run_one(args):
    tf, (slm, slv), tpr, bn, buf, tr, cost = args
    d = _get_tf(tf)
    cfg = Config(tf=tf, sl_mode=slm, sl_value=slv, tp_r=tpr, barsn=bn, buf_atr=buf, trail=tr,
                 cost_preset=cost, sizing="fixed", fixed_qty=1.0).apply_preset()
    trades, _, _ = run_backtest(d, cfg, want_trades=False)
    m = metrics(trades)
    row = dict(tf=tf, sl_mode=slm, sl_value=slv, tp_r=tpr, barsN=bn, buf_atr=buf, trail=tr, cost_preset=cost)
    row.update(m)
    return row


def sweep(tfs, jobs: int) -> dict[str, pd.DataFrame]:
    import multiprocessing as mp
    os.makedirs(RESULTS_DIR, exist_ok=True)
    frames = {}
    for tf in tfs:
        combos = list(itertools.product([tf], GRID["sl"], GRID["tp_r"], GRID["barsn"], GRID["buf_atr"], GRID["trail"], GRID["cost"]))
        t0 = time.time()
        if jobs > 1:
            with mp.Pool(jobs) as pool:
                rows = pool.map(_run_one, combos, chunksize=64)
        else:
            rows = [_run_one(cmb) for cmb in combos]
        df = pd.DataFrame(rows)
        df.to_csv(os.path.join(RESULTS_DIR, f"sweep_{tf}.csv"), index=False)
        frames[tf] = df
        print(f"TF {tf}: {len(df)} configs in {time.time() - t0:.1f}s -> results/sweep_{tf}.csv", flush=True)
    return frames


# --------------------------------------------------------------------------
# Cost geometry
# --------------------------------------------------------------------------
def cost_geometry(tfs) -> dict:
    out = {}
    for tf in tfs:
        d = _get_tf(tf)
        price = float(np.nanmedian(d.close))
        atr_med = float(np.nanmedian(d.atr))
        atr_pct = float(np.nanmedian(d.atr / d.close * 100))
        sl_pct01 = price * 0.001
        sl_atr15 = 1.5 * atr_med
        row = dict(median_close=price, median_atr_usd=atr_med, median_atr_pct=atr_pct,
                   sl_dist_pct0_1_usd=sl_pct01, sl_dist_1_5atr_usd=sl_atr15, presets={})
        for name, p in COST_PRESETS.items():
            rt = 2 * p["commission_pct"] * price + 2 * p["commission_cash"] + p["spread_usd"] + 2 * p["slippage_usd"]
            min_tp = rt / 0.20
            row["presets"][name] = dict(
                round_trip_usd_per_btc=rt, cost_pct_of_price=rt / price * 100, cost_over_atr=rt / atr_med,
                cost_over_sl_pct0_1=rt / sl_pct01, cost_over_sl_1_5atr=rt / sl_atr15,
                min_tp_usd_for_cost_lt_20pct=min_tp, min_tp_pct_for_cost_lt_20pct=min_tp / price * 100,
                min_tp_in_atr=min_tp / atr_med)
        out[tf] = row
    return out


def geometry_markdown(geo: dict) -> str:
    lines = []
    lines.append("| TF | median close | median ATR (USD) | median ATR % | preset | RT cost USD/BTC | cost % price | cost/ATR | cost/SL(0.1%) | cost/SL(1.5 ATR) | min TP USD (cost<20%) | min TP % | min TP in ATR |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for tf, r in geo.items():
        for name, p in r["presets"].items():
            lines.append(f"| {tf}m | {r['median_close']:.0f} | {r['median_atr_usd']:.1f} | {r['median_atr_pct']:.3f} | {name} | "
                         f"{p['round_trip_usd_per_btc']:.2f} | {p['cost_pct_of_price']:.4f} | {p['cost_over_atr']:.3f} | "
                         f"{p['cost_over_sl_pct0_1']:.3f} | {p['cost_over_sl_1_5atr']:.3f} | {p['min_tp_usd_for_cost_lt_20pct']:.1f} | "
                         f"{p['min_tp_pct_for_cost_lt_20pct']:.3f} | {p['min_tp_in_atr']:.2f} |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Recommendations (plateau-aware)
# --------------------------------------------------------------------------
def _neighbors(row, df):
    """1-step grid neighbours varying one parameter (same tf, cost preset, sl_mode)."""
    sl_vals = [v for m, v in GRID["sl"] if m == row.sl_mode]
    def step(lst, val):
        i = lst.index(val)
        return [lst[j] for j in (i - 1, i + 1) if 0 <= j < len(lst)]
    base = (df.cost_preset == row.cost_preset) & (df.sl_mode == row.sl_mode)
    masks = []
    for v in step(sl_vals, row.sl_value):
        masks.append(base & (df.sl_value == v) & (df.tp_r == row.tp_r) & (df.barsN == row.barsN) & (df.buf_atr == row.buf_atr) & (df.trail == row.trail))
    for v in step(GRID["tp_r"], row.tp_r):
        masks.append(base & (df.sl_value == row.sl_value) & (df.tp_r == v) & (df.barsN == row.barsN) & (df.buf_atr == row.buf_atr) & (df.trail == row.trail))
    for v in step(GRID["barsn"], row.barsN):
        masks.append(base & (df.sl_value == row.sl_value) & (df.tp_r == row.tp_r) & (df.barsN == v) & (df.buf_atr == row.buf_atr) & (df.trail == row.trail))
    for v in step(GRID["buf_atr"], row.buf_atr):
        masks.append(base & (df.sl_value == row.sl_value) & (df.tp_r == row.tp_r) & (df.barsN == row.barsN) & (df.buf_atr == v) & (df.trail == row.trail))
    for v in [t for t in GRID["trail"] if t != row.trail]:
        masks.append(base & (df.sl_value == row.sl_value) & (df.tp_r == row.tp_r) & (df.barsN == row.barsN) & (df.buf_atr == row.buf_atr) & (df.trail == v))
    idx = []
    for mk in masks:
        idx.extend(df.index[mk].tolist())
    return df.loc[idx]


MAX_SAME_BAR_SHARE = 0.5   # configs whose trades mostly resolve inside the fill bar are emulator-path artefacts, not evidence


def recommend(frames: dict[str, pd.DataFrame], presets=("cfd_std", "exchange"), min_trades=15) -> dict:
    rec = {}
    for tf, df in frames.items():
        rec[tf] = {}
        for preset in presets:
            sub = df[(df.cost_preset == preset)]
            measurable = sub.same_bar_exit_share <= MAX_SAME_BAR_SHARE
            cand = sub[(sub.n_trades >= min_trades) & (sub.net_pnl > 0) & measurable].copy()
            entry = dict(preset=preset, min_trades=min_trades, max_same_bar_share=MAX_SAME_BAR_SHARE, n_configs=int(len(sub)),
                         n_configs_meeting_min_trades=int((sub.n_trades >= min_trades).sum()),
                         n_configs_positive=int((sub.net_pnl > 0).sum()),
                         n_configs_excluded_same_bar=int((~measurable).sum()),
                         n_configs_positive_and_min_trades=int(len(cand)),
                         max_trades_any_config=int(sub.n_trades.max()))
            if len(cand) == 0:
                entry["verdict"] = ("too few trades" if (sub.n_trades >= min_trades).sum() == 0
                                    else "no config with n_trades>=%d is net positive" % min_trades)
                entry["pick"] = None
                # still report the best available for context
                best = sub.sort_values("net_pnl", ascending=False).iloc[0]
                entry["best_raw_net_config"] = _row_to_dict(best)
                rec[tf][preset] = entry
                continue
            scores = []
            for ix, row in cand.iterrows():
                nb = _neighbors(row, df)
                nb_net = nb.net_pnl.to_numpy()
                nb_pos = float((nb_net > 0).mean()) if len(nb) else np.nan
                hood = np.concatenate([[row.net_pnl], nb_net])
                scores.append(dict(ix=ix, nb_n=len(nb), nb_pos_frac=nb_pos, hood_mean=float(hood.mean()),
                                   hood_median=float(np.median(hood)), hood_min=float(hood.min())))
            sc = pd.DataFrame(scores).set_index("ix")
            cand = cand.join(sc)
            # robust: neighbourhood median positive and >= 60% of neighbours positive; rank by neighbourhood mean
            robust = cand[(cand.nb_pos_frac >= 0.6) & (cand.hood_median > 0)]
            pool = robust if len(robust) else cand
            pool = pool.sort_values(["hood_mean", "expectancy_R"], ascending=False)
            best = pool.iloc[0]
            entry["verdict"] = "plateau pick" if len(robust) else "no plateau; best isolated positive config (fragile)"
            entry["pick"] = _row_to_dict(best)
            entry["pick"].update(dict(neighbours=int(best.nb_n), neighbours_positive_frac=float(best.nb_pos_frac),
                                      neighbourhood_mean_net=float(best.hood_mean), neighbourhood_median_net=float(best.hood_median),
                                      neighbourhood_min_net=float(best.hood_min)))
            entry["top5"] = [_row_to_dict(r) | dict(neighbours_positive_frac=float(r.nb_pos_frac), neighbourhood_mean_net=float(r.hood_mean))
                             for _, r in pool.head(5).iterrows()]
            rec[tf][preset] = entry
    return rec


def _row_to_dict(r) -> dict:
    keys = ["tf", "sl_mode", "sl_value", "tp_r", "barsN", "buf_atr", "trail", "cost_preset", "n_trades", "n_long", "n_short",
            "win_rate", "gross_pnl", "total_cost", "net_pnl", "cost_to_gross_ratio", "profit_factor_net", "expectancy_R",
            "max_drawdown_net", "avg_bars_held", "exit_tp", "exit_sl", "exit_trail", "exit_end", "same_bar_exit_share"]
    return {k: _json_safe(r[k]) for k in keys}


def v201_baseline(frames: dict[str, pd.DataFrame]) -> dict:
    out = {}
    for tf, df in frames.items():
        m = df[(df.sl_mode == "pct") & (df.sl_value == 0.1) & (df.tp_r == 2.5) & (df.barsN == 5) & (df.buf_atr == 1.0) & (df.trail == "bar")]
        out[tf] = {r.cost_preset: _row_to_dict(r) for _, r in m.iterrows()}
    return out


def _fmt(v, nd=2):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "n/a" if v is None or math.isnan(v) else "inf"
    return f"{v:.{nd}f}"


def config_table(rows: list[dict], title: str) -> str:
    lines = [f"**{title}**", "",
             "| tf | cost | SL mode | SL | TP R | BarsN | buf ATR | trail | n | win% | gross | cost | net | cost/|gross| | PF | exp R | maxDD | bars held | same-bar % | tp/sl/trail/end | nb+ | hood mean |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r is None:
            continue
        lines.append(f"| {r['tf']} | {r['cost_preset']} | {r['sl_mode']} | {r['sl_value']} | {r['tp_r']} | {r['barsN']} | {r['buf_atr']} | {r['trail']} | "
                     f"{r['n_trades']} | {_fmt(r['win_rate'] * 100 if r['win_rate'] is not None else None, 0)} | {_fmt(r['gross_pnl'], 0)} | {_fmt(r['total_cost'], 0)} | "
                     f"{_fmt(r['net_pnl'], 0)} | {_fmt(r['cost_to_gross_ratio'])} | {_fmt(r['profit_factor_net'])} | {_fmt(r['expectancy_R'])} | "
                     f"{_fmt(r['max_drawdown_net'], 0)} | {_fmt(r['avg_bars_held'], 1)} | {_fmt(r['same_bar_exit_share'] * 100, 0)} | "
                     f"{_fmt(r['exit_tp'] * 100, 0)}/{_fmt(r['exit_sl'] * 100, 0)}/{_fmt(r['exit_trail'] * 100, 0)}/{_fmt(r['exit_end'] * 100, 0)} | "
                     f"{_fmt(r.get('neighbours_positive_frac'), 2) if r.get('neighbours_positive_frac') is not None else '-'} | "
                     f"{_fmt(r.get('neighbourhood_mean_net'), 0) if r.get('neighbourhood_mean_net') is not None else '-'} |")
    return "\n".join(lines)


def write_notes(frames, geo, rec, base, par, timing: dict):
    L = []
    L.append("# XPW Breakout BTCUSD calibration sweep\n")
    L.append("Engine: `calibration/xpw_backtest.py` (TradingView broker-emulator replica, no bar magnifier). "
             "Sizing fixed 1.0 BTC, initial capital 100000. Grid per TF: SL {pct 0.1/0.25/0.5/1.0, atr 1.0/1.5/2.0/3.0} x TP R {1,1.5,2,2.5,3} "
             "x BarsN {3,5,8} x buffer ATR {0.5,1,2} x trail {off, bar, tick} x cost {none, exchange, cfd_std, cfd_raw} = 4320 configs per TF.\n")
    L.append("## READ THIS FIRST: sample-size caveat\n")
    L.append("Each timeframe has ~600 bars (15m: 7.6 days, 30m: 12 days, 60m: 25 days, 240m: 99 days; **1m: only ~10 hours**). "
             "Most configs produce 5-40 trades. This sweep calibrates **cost and geometry sanity** (is the TP big enough to pay the spread, "
             "does the SL sit inside or outside typical noise, does the trail help or hurt at a given bar size). It does **not** prove an edge, "
             "and any single 'best' config is mostly noise. Prefer the plateau readings (neighbour-positive fraction, neighbourhood mean) over the raw best.\n")
    L.append("## Data / timing\n")
    for tf, t in timing.items():
        L.append(f"- TF {tf}m: {t['bars']} bars, {t['configs']} configs, {t['secs']:.1f}s")
    L.append("")
    L.append("## Cost geometry (median ATR, round-trip cost per 1 BTC)\n")
    L.append("Round-trip cost = 2 x commission (pct x price, or cash) + full spread + 2 x slippage. 'min TP' = TP distance at which the round trip is 20% of TP.\n")
    L.append(geometry_markdown(geo))
    L.append("")
    L.append("## Parity vs TradingView ('Trail' column non-null = TV in position)\n")
    L.append("The TV export was evidently NOT run at the v2.01 header defaults. From the Trail column: initial trail = avg x 0.999 "
             "(SL 0.1% confirmed), implied entry = stop level +/- 0.30 in most episodes (30-tick slippage confirmed), every trail ratchet step "
             "has (close - trail)/ATR = 1.900 on every TF (ATR replica confirmed to 3 decimals; trail distance was 1.9 ATR, not 1.5), and positions were "
             "held through bars exceeding a 0.25% TP but never a 0.5% one (TP was 0.5%, not 0.25%). Both variants are compared below.\n")
    L.append("| TF | variant | bars | TV bars in pos | engine bars in pos | overlap | Jaccard | recall of TV | TV episodes | engine episodes | identical episodes | TV fills at level+/-slip | median |trail diff| | max |trail diff| |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for tf, r2 in par.items():
        for vname in PARITY_VARIANTS:
            r = r2[vname]
            L.append(f"| {tf}m | {vname} | {r2['bars']} | {r2['tv_bars_in_pos']} | {r['engine_bars_in_pos']} | {r['overlap_bars']} | {_fmt(r['jaccard'])} | "
                     f"{_fmt(r['recall_of_tv'])} | {r2['tv_episodes']} | {r['engine_episodes']} | {r['episodes_identical']} | "
                     f"{r2['tv_fills_at_level_plus_slip']}/{r2['tv_episodes']} | {_fmt(r['trail_abs_diff_median'], 2)} | {_fmt(r['trail_abs_diff_max'], 1)} |")
    L.append("")
    L.append("Remaining differences: (a) a few TV fills sit at the bar close + slippage rather than at the stop level (15m bars 129 and 275), and a few "
             "TV episodes are absent where the engine holds through the fill bar (15m 542, 687; 240m 248) - both are consistent with TradingView "
             "having used bar magnifier (intrabar path different from the OHLC assumption); (b) TV's ATR/pivot history starts before the CSV window "
             "(swingH/swingL are seeded from the first CSV row in parity mode, ATR is seeded inside the window); (c) the 1m file is ~10 hours. "
             "Perfect parity is not expected and is not claimed; the held-bar trail values match to <1e-6 where both hold, which is the part that matters "
             "for calibrating geometry. Episode ranges are printed by `python3 xpw_backtest.py parity`.\n")
    L.append("## Sub-bar geometry is an emulator artefact, not evidence\n")
    L.append("Without bar magnifier the emulator assumes the intrabar path open-low-high-close (or open-high-low-close). After a buy-stop fills on the "
             "way up, the assumed path always continues to the bar high BEFORE it can revisit the stop, so any TP that sits inside the bar's remaining range "
             "is 'hit' first. A 0.1% SL / 0.25% TP on bars whose ATR is 0.24% (15m) to 1.0% (240m) therefore resolves inside the fill bar almost every time "
             "(v2.01 baseline: 0.1-0.9 bars held, 100% same-bar exits on 240m) and the win rate is a property of the path assumption. TradingView shows the "
             "same artefact without bar magnifier; the TV export (evidently WITH bar magnifier) already disagreed with the OHLC path on 3 of 34 fill bars. "
             "Configs with more than 50% same-bar exits are therefore reported (column 'same-bar %') but excluded from the recommendation picks. "
             "The 'exchange' preset also shows the true cost picture for that geometry: ~$85 round trip against an $80 SL and $200 TP.\n")
    L.append("## v2.01 gold defaults on BTCUSD (SL 0.1%, TP 0.25% = 2.5R, BarsN 5, buffer 1.0 ATR, trail bar)\n")
    rows = []
    for tf, d in base.items():
        for preset in ("none", "exchange", "cfd_std", "cfd_raw"):
            rows.append(d.get(preset))
    L.append(config_table(rows, "v2.01 baseline by cost preset"))
    L.append("")
    L.append("## Recommendations\n")
    for tf, d in rec.items():
        for preset, e in d.items():
            L.append(f"### TF {tf}m, preset {preset}\n")
            L.append(f"- configs: {e['n_configs']}, with >= {e['min_trades']} trades: {e['n_configs_meeting_min_trades']}, net positive: {e['n_configs_positive']}, "
                     f"excluded as same-bar artefacts (> {int(e['max_same_bar_share']*100)}% of trades exit in the fill bar): {e['n_configs_excluded_same_bar']}, "
                     f"eligible (positive, enough trades, measurable): {e['n_configs_positive_and_min_trades']}, max trades any config: {e['max_trades_any_config']}")
            L.append(f"- verdict: **{e['verdict']}**" + ("  (1m file is ~10 hours; ignore for calibration)" if tf == "1" else ""))
            if e.get("pick"):
                rows = [e["pick"], base[tf].get(preset)]
                L.append("")
                L.append(config_table(rows, "pick (first row) vs v2.01 default (second row)"))
                L.append("")
                L.append(config_table(e["top5"], "top 5 by neighbourhood mean"))
            else:
                L.append("")
                L.append(config_table([e.get("best_raw_net_config"), base[tf].get(preset)], "best raw net (for context only) vs v2.01 default"))
            L.append("")
    L.append("## Marginal views (mean net over all other grid dims, all TFs except 1m)\n")
    allf = pd.concat([f for tf, f in frames.items() if tf != "1"]) if any(tf != "1" for tf in frames) else pd.concat(frames.values())
    for dim in ("trail", "sl_mode", "sl_value", "tp_r", "barsN", "buf_atr"):
        g = allf.groupby(["cost_preset", dim]).agg(mean_net=("net_pnl", "mean"), pos_frac=("net_pnl", lambda s: float((s > 0).mean())),
                                                    mean_trades=("n_trades", "mean"), mean_expR=("expectancy_R", "mean")).reset_index()
        L.append(f"**by {dim}**\n")
        L.append("| cost | " + dim + " | mean net | positive frac | mean trades | mean exp R |")
        L.append("|---|---|---|---|---|---|")
        for _, r in g.iterrows():
            L.append(f"| {r.cost_preset} | {r[dim]} | {r.mean_net:.0f} | {r.pos_frac:.2f} | {r.mean_trades:.1f} | {r.mean_expR:.3f} |")
        L.append("")
    L.append("## Caveats\n")
    L.append("- ~600 bars per TF; the 1m file covers ~10 hours. Nothing here is statistically significant; treat as cost/geometry sanity only.")
    L.append("- Emulator replica without bar magnifier: intrabar ordering is an assumption (open-low-high-close / open-high-low-close). Same-bar entry+exit is guesswork on both sides.")
    L.append("- Tick-mode trail is an approximation (ratchet at 4 path nodes per bar with the previous bar's ATR), not a true tick replay.")
    L.append("- ATR is seeded inside the CSV window (SMA of first 14 TRs); TradingView's ATR has longer history. Pivots start unseeded in the sweep (first ~2*BarsN bars untradable).")
    L.append("- Costs: spread is applied as half-spread on every stop/market fill, none on TP limit fills; slippage per side on stop/market fills. Commission on both sides. 'gross' = P&L at ideal fills (stop level / open / TP price); 'cost' = commission + spread + slippage actually paid; net = gross - cost.")
    L.append("- Open position at end of data is closed at the last close (market, with slippage) and tagged 'end'.")
    L.append("- Fixed 1.0 BTC sizing; equity effects of risk sizing are not in the sweep (engine supports --sizing risk).")
    with open(os.path.join(RESULTS_DIR, "SWEEP_NOTES.md"), "w") as f:
        f.write("\n".join(L) + "\n")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _json_safe(o):
    if isinstance(o, dict):
        return {str(k): _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (np.isnan(o) or np.isinf(o)) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run one config, print trades + metrics")
    r.add_argument("--tf", default="60")
    r.add_argument("--sl-mode", default="pct", choices=["pct", "atr"])
    r.add_argument("--sl", type=float, default=0.1)
    r.add_argument("--tp-r", type=float, default=2.5)
    r.add_argument("--barsn", type=int, default=5)
    r.add_argument("--buf", type=float, default=1.0)
    r.add_argument("--trail", default="bar", choices=["off", "bar", "tick"])
    r.add_argument("--trg", type=float, default=1.0)
    r.add_argument("--dst", type=float, default=1.5)
    r.add_argument("--cost", default="cfd_std", choices=list(COST_PRESETS))
    r.add_argument("--sizing", default="fixed", choices=["fixed", "risk"])
    r.add_argument("--qty", type=float, default=1.0)
    r.add_argument("--risk", type=float, default=4.0)
    r.add_argument("--max-qty", type=float, default=50.0)
    r.add_argument("--qty-step", type=float, default=0.001)
    r.add_argument("--sh", type=int, default=0)
    r.add_argument("--eh", type=int, default=0)
    r.add_argument("--gate", action="store_true")
    r.add_argument("--seed-swings", action="store_true")

    p = sub.add_parser("parity", help="v2.01 defaults vs TradingView Trail column")
    p.add_argument("--tfs", default="15,30,60,240,1")

    s = sub.add_parser("sweep", help="full grid sweep + summary.json + SWEEP_NOTES.md")
    s.add_argument("--tfs", default="15,30,60,240,1")
    s.add_argument("--jobs", type=int, default=max(1, os.cpu_count() or 1))

    g = sub.add_parser("geometry", help="print cost geometry table")
    g.add_argument("--tfs", default="1,15,30,60,240")

    a = ap.parse_args(argv)

    if a.cmd == "run":
        d = load_tf(a.tf)
        cfg = Config(tf=a.tf, sl_mode=a.sl_mode, sl_value=a.sl, tp_r=a.tp_r, barsn=a.barsn, buf_atr=a.buf, trail=a.trail,
                     trg_atr=a.trg, dst_atr=a.dst, cost_preset=a.cost, sizing=a.sizing, fixed_qty=a.qty, risk_pct=a.risk,
                     max_qty=a.max_qty, qty_step=a.qty_step, sh=a.sh, eh=a.eh, use_gate=a.gate, seed_swings=a.seed_swings).apply_preset()
        trades, in_pos, _ = run_backtest(d, cfg)
        print(json.dumps(_json_safe(asdict(cfg))))
        print_trades(trades, d)
        m = metrics(trades)
        print(json.dumps(_json_safe(m), indent=1))
    elif a.cmd == "parity":
        res = parity(tuple(a.tfs.split(",")))
        os.makedirs(RESULTS_DIR, exist_ok=True)
        with open(os.path.join(RESULTS_DIR, "parity.json"), "w") as f:
            json.dump(_json_safe(res), f, indent=1)
    elif a.cmd == "geometry":
        print(geometry_markdown(cost_geometry(a.tfs.split(","))))
    elif a.cmd == "sweep":
        tfs = a.tfs.split(",")
        t_all = time.time()
        timing = {}
        frames = {}
        for tf in tfs:
            t0 = time.time()
            frames.update(sweep([tf], a.jobs))
            timing[tf] = dict(bars=len(_get_tf(tf).open), configs=len(frames[tf]), secs=time.time() - t0)
        geo = cost_geometry(tfs)
        rec = recommend(frames)
        base = v201_baseline(frames)
        par = parity(tuple(tfs), verbose=False)
        summary = dict(generated=time.strftime("%Y-%m-%d %H:%M:%S"), initial_capital=INITIAL_CAPITAL, sizing="fixed 1.0 BTC",
                       grid=GRID, cost_presets=COST_PRESETS, timing=timing, cost_geometry=geo, recommendations=rec,
                       v201_baseline=base, parity=par,
                       caveats=["~600 bars per TF (1m: ~10 hours) - cost/geometry sanity only, no edge proof",
                                "broker-emulator replica without bar magnifier; intrabar order is assumed",
                                "tick trail approximated by 4-node path ratchet",
                                "ATR seeded inside window; pivots unseeded in sweep"])
        with open(os.path.join(RESULTS_DIR, "summary.json"), "w") as f:
            json.dump(_json_safe(summary), f, indent=1)
        write_notes(frames, geo, rec, base, par, timing)
        print(f"done in {time.time() - t_all:.1f}s -> results/summary.json, results/SWEEP_NOTES.md")


if __name__ == "__main__":
    main()
