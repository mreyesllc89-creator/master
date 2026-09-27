"""mtf_confluence.py - calibrate the multi-timeframe confluence labels (XPW group 11, FlashGold group S4).

For a chart timeframe, runs the strategy (XPW or FlashGold) with its shipped settings, then for each candidate
extra timeframe reproduces the script's per-timeframe event (XPW: breakout of the nearest pivot level above /
below the previous close; FlashGold: parent TDI + burst + hold signal) on that timeframe's own export, maps it
to the chart candle the way the scripts do (higher TF: attributed to the first chart bar after the higher bar
closed; lower TF: any lower bar inside the chart candle), and reports:
  - agreement rate: share of chart entries that had the same-side event within tol x ATR on that timeframe
  - PF / win rate of chart trades WITH and WITHOUT that timeframe's agreement
  - PF / win rate by number of agreeing timeframes (chart counts as one)
Only the overlap of the exports is used (they cover different date ranges).
"""
import sys, os, dataclasses
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xpw_backtest as xb
import flashgold_backtest as fg

TOL = 0.5
TF_MIN = dict(fg.TF_MIN); TF_MIN.update({"xau240": 240, "240": 240, "spx120": 120, "spx180": 180, "spx240": 240, "spx1D": 1440})

def clock(times):
    return pd.to_datetime(pd.Series([s[:19] for s in times])).to_numpy()

def bar_bounds(d, tf):
    t0 = clock(d.time)
    if TF_MIN[tf] >= 1440:
        t1 = t0 + np.timedelta64(16, "h")                       # daily export: date only; cash close 16:00 for the session symbols
        return t0 + np.timedelta64(9, "h") + np.timedelta64(30, "m"), t1
    return t0, t0 + np.timedelta64(TF_MIN[tf], "m")

def latched_pivots(h, l, n):
    N = len(h); sH = np.full(N, np.nan); sL = np.full(N, np.nan); cH = np.nan; cL = np.nan
    for i in range(2 * n, N):
        c = i - n
        okH = all(h[c - k] < h[c] for k in range(1, n + 1)) and all(h[c + k] <= h[c] for k in range(1, n + 1))
        okL = all(l[c - k] > l[c] for k in range(1, n + 1)) and all(l[c + k] >= l[c] for k in range(1, n + 1))
        if okH: cH = h[c]
        if okL: cL = l[c]
        sH[i] = cH; sL[i] = cL
    return sH, sL

def xpw_events(d, barsn=3):
    sH, sL = latched_pivots(d.high, d.low, barsn)
    N = len(d.close); bL = np.zeros(N, bool); bS = np.zeros(N, bool); lu = np.full(N, np.nan); ld = np.full(N, np.nan)
    for j in range(1, N):
        u = sH[j - 1] if not np.isnan(sH[j - 1]) and sH[j - 1] > d.close[j - 1] else np.nan
        v = sL[j - 1] if not np.isnan(sL[j - 1]) and sL[j - 1] < d.close[j - 1] else np.nan
        lu[j] = u; ld[j] = v
        bL[j] = not np.isnan(u) and d.high[j] >= u
        bS[j] = not np.isnan(v) and d.low[j] <= v
    return bL, bS, lu, ld

def fg_events(d, tf, burst_atr, dist_atr, hold):
    """FlashGold self signal on this timeframe (parent TDI + burst + hold, chart-only zone), as fgSelf() in the scripts."""
    data = fg.Data(tf) if False else None
    close = d.close; atr = xb.atr_wilder(d.high, d.low, d.close, 14); dirs = fg.tdi_dir(close)
    N = len(close); bS = np.zeros(N, bool); sS = np.zeros(N, bool); bp = np.full(N, np.nan); sp = np.full(N, np.nan)
    hold_active = False; hold_buy = False; hold_bar = -1; hold_mid = np.nan; last = -1
    for i in range(1, N):
        if np.isnan(atr[i]) or np.isnan(dirs[i]): continue
        ps = 1 if dirs[i] > 0 else -1 if dirs[i] < 0 else 0
        burst = close[i] - close[i - 1]
        bb = burst >= burst_atr * atr[i]; bs = burst <= -burst_atr * atr[i]
        cb = ps == 1 and bb; cs = ps == -1 and bs
        can = last != i
        if cb and can:
            if hold == 0: bS[i] = True; bp[i] = close[i] + dist_atr * atr[i]; last = i
            elif not hold_active: hold_active = True; hold_buy = True; hold_bar = i; hold_mid = close[i]
            elif hold_buy and i - hold_bar >= hold and close[i] - hold_mid >= 0.1 * atr[i]:
                bS[i] = True; bp[i] = close[i] + dist_atr * atr[i]; last = i; hold_active = False
        if cs and can:
            if hold == 0: sS[i] = True; sp[i] = close[i] - dist_atr * atr[i]; last = i
            elif not hold_active: hold_active = True; hold_buy = False; hold_bar = i; hold_mid = close[i]
            elif (not hold_buy) and i - hold_bar >= hold and hold_mid - close[i] >= 0.1 * atr[i]:
                sS[i] = True; sp[i] = close[i] - dist_atr * atr[i]; last = i; hold_active = False
        if hold_active and ((hold_buy and ps != 1) or ((not hold_buy) and ps != -1)): hold_active = False
    return bS, sS, bp, sp

def map_events(chart_d, chart_tf, ex_d, ex_tf, ev, mode="level"):
    """Map extra-TF events (bL, bS, lu, ld) onto chart bars the way the scripts do. Returns per-chart-bar arrays."""
    c0, c1 = bar_bounds(chart_d, chart_tf); e0, e1 = bar_bounds(ex_d, ex_tf)
    N = len(chart_d.close); bL = np.zeros(N, bool); bS = np.zeros(N, bool); lu = np.full(N, np.nan); ld = np.full(N, np.nan)
    higher = TF_MIN[ex_tf] > TF_MIN[chart_tf]
    ebL, ebS, elu, eld = ev
    if higher and mode == "level":
        # XPW: the level that stood at the previous higher-TF close is live on every chart bar of the current
        # higher bar; the chart bar that trades through it IS the higher-timeframe breakout candle.
        # elu[j] = level above the close of higher bar j-1 (that is what the script's [1] read returns).
        idx = np.searchsorted(e0, c0, side="right") - 1          # higher bar containing each chart bar
        for k in range(N):
            j = idx[k]
            if j < 0 or not (e0[j] <= c0[k] < e1[j]): continue
            if not np.isnan(elu[j]) and chart_d.high[k] >= elu[j]: bL[k] = True; lu[k] = elu[j]
            if not np.isnan(eld[j]) and chart_d.low[k] <= eld[j]:  bS[k] = True; ld[k] = eld[j]
    elif higher:
        # FlashGold: the higher-TF signal of bar j (known at its close) stays live through bar j+1
        idx = np.searchsorted(e0, c0, side="right") - 1
        for k in range(N):
            j = idx[k] - 1                                         # previous (closed) higher bar
            if j < 0 or idx[k] >= len(e0) or not (e0[idx[k]] <= c0[k] < e1[idx[k]]): continue
            if ebL[j]: bL[k] = True; lu[k] = elu[j]
            if ebS[j]: bS[k] = True; ld[k] = eld[j]
    else:
        # extra bar j belongs to the chart bar whose [open, close) contains its open time
        idx = np.searchsorted(c0, e0, side="right") - 1
        for j in range(len(e0)):
            k = idx[j]
            if k < 0 or k >= N or not (c0[k] <= e0[j] < c1[k]): continue
            if ebL[j]: bL[k] = True; lu[k] = elu[j]
            if ebS[j]: bS[k] = True; ld[k] = eld[j]
    covered = (c0 >= e0[0]) & (c0 <= e0[-1])
    return bL, bS, lu, ld, covered

def pf(x):
    g = x[x > 0].sum(); l = -x[x < 0].sum(); return g / l if l > 0 else float("inf") if g > 0 else float("nan")

def report(name, chart_tf, extras, trades, chart_d, events_by_tf):
    atr = xb.atr_wilder(chart_d.high, chart_d.low, chart_d.close, 14)
    print(f"\n#### {name} on chart {chart_tf}: {len(trades)} chart trades over the whole export")
    rows = []; agree_mat = {}
    for ex in extras:
        bL, bS, lu, ld, cov = events_by_tf[ex]
        sub = [t for t in trades if cov[t["bar"]]]
        if not sub: print(f"  {ex:>7}: no overlap"); continue
        ag = np.array([(t["side"] > 0 and bL[t["bar"]] and abs(lu[t["bar"]] - t["entry"]) <= TOL * atr[t["bar"]]) or
                       (t["side"] < 0 and bS[t["bar"]] and abs(ld[t["bar"]] - t["entry"]) <= TOL * atr[t["bar"]]) for t in sub])
        p = np.array([t["pnl"] for t in sub])
        agree_mat[ex] = {t["bar"]: a for t, a in zip(sub, ag)}
        w = p[ag]; wo = p[~ag]
        rows.append(dict(extra=ex, overlap_trades=len(sub), agree=int(ag.sum()), agree_pct=round(100 * ag.mean(), 0),
                         pf_with=round(pf(w), 2) if len(w) else None, win_with=round(100 * (w > 0).mean(), 0) if len(w) else None, net_with=round(w.sum(), 1),
                         pf_without=round(pf(wo), 2) if len(wo) else None, win_without=round(100 * (wo > 0).mean(), 0) if len(wo) else None, net_without=round(wo.sum(), 1)))
    print(pd.DataFrame(rows).to_string(index=False))
    # confluence count per trade, over the intersection of coverage
    common = [t for t in trades if all(events_by_tf[ex][4][t["bar"]] for ex in agree_mat)]
    if common and agree_mat:
        cnt = np.array([1 + sum(1 for ex in agree_mat if agree_mat[ex].get(t["bar"], False)) for t in common])
        p = np.array([t["pnl"] for t in common])
        print(f"  by number of agreeing timeframes (chart + extras), {len(common)} trades where every extra has data:")
        for k in sorted(set(cnt)):
            m = cnt == k; print(f"    x{k}: {m.sum():>3} trades, win {100*(p[m]>0).mean():.0f}%, PF {pf(p[m]):.2f}, net {p[m].sum():+.1f}")
        for k in (2, 3):
            m = cnt >= k
            if m.sum(): print(f"    >= x{k}: {m.sum():>3} trades, win {100*(p[m]>0).mean():.0f}%, PF {pf(p[m]):.2f}, net {p[m].sum():+.1f}   | below: {(~m).sum()} trades, win {100*(p[~m]>0).mean():.0f}%, PF {pf(p[~m]):.2f}")

def run_xpw(name, chart_tf, extras, cost, geo):
    d = xb.load_tf(chart_tf, assert_pivots=False)
    cfg = xb.Config(tf=chart_tf, cost_preset=cost, sizing="fixed", fixed_qty=1.0, arm_mode="hold", levels="pivot", **geo).apply_preset()
    tr, _, _ = xb.run_backtest(d, cfg, want_trades=True)
    trades = [dict(bar=t.entry_bar, side=t.side, entry=t.entry_price, pnl=t.net) for t in tr]
    ev = {}
    for ex in extras:
        de = xb.load_tf(ex, assert_pivots=False)
        ev[ex] = map_events(d, chart_tf, de, ex, xpw_events(de, geo["barsn"]))
    report("XPW " + name, chart_tf, extras, trades, d, ev)

def run_fg(name, chart_tf, extras, preset):
    d = fg.get_data(chart_tf)
    cfg = fg.Cfg(tf=chart_tf, **preset)
    tr = fg.run(cfg, d)
    trades = [dict(bar=t["entry_bar"], side=t["side"], entry=t["entry"], pnl=t["pnl"]) for t in tr]
    dd = xb.load_tf(chart_tf, assert_pivots=False)
    ev = {}
    for ex in extras:
        de = xb.load_tf(ex, assert_pivots=False)
        ev[ex] = map_events(dd, chart_tf, de, ex, fg_events(de, ex, preset["burst_atr"], preset["dist_atr"], preset["hold_bars"]), mode="window")
    report("FlashGold " + name, chart_tf, extras, trades, dd, ev)

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "xpw"
    if which == "xpw":
        gold = dict(sl_mode="atr", sl_value=1.5, tp_r=2.5, barsn=3, buf_atr=1.0, trail="tick")
        btc  = dict(sl_mode="atr", sl_value=3.0, tp_r=3.0, barsn=3, buf_atr=0.5, trail="tick")
        spx  = dict(sl_mode="pct", sl_value=0.5, tp_r=2.0, barsn=3, buf_atr=2.0, trail="tick")
        run_xpw("XAUUSD", "xau30", ["xau5", "xau10", "xau15", "xau60", "xau240"], "gold_raw", gold)
        run_xpw("XAUUSD", "xau60", ["xau10", "xau15", "xau30", "xau240"], "gold_raw", gold)
        run_xpw("XAUUSD", "xau15", ["xau5", "xau10", "xau30", "xau60", "xau240"], "gold_raw", gold)
        run_xpw("BTCUSD", "60", ["15", "30", "240"], "vt_btc", btc)
        run_xpw("SPX500", "spx60", ["spx15", "spx30", "spx120", "spx180", "spx240", "spx1D"], "spx_cfd", spx)
        run_xpw("SPX500", "spx120", ["spx15", "spx30", "spx60", "spx180", "spx240", "spx1D"], "spx_cfd", spx)
    else:
        run_fg("XAUUSD", "xau60", ["xau10", "xau15", "xau30", "xau240"], dict(zones="htf2", any_combo=False, burst_atr=0.5, dist_atr=0.25, hold_bars=0, sl_atr=2.0, tp_r=2.0, trail=True, exit_opp=False))
        run_fg("SPX500", "spx15", ["spx1", "spx30", "spx60", "spx120", "spx240"], dict(zones="parent", any_combo=False, burst_atr=0.5, dist_atr=0.25, hold_bars=3, sl_atr=3.0, tp_r=1.5, trail=True, exit_opp=False))
        run_fg("BTCUSD", "60", ["15", "30", "240"], dict(zones="htf3", any_combo=False, burst_atr=0.25, dist_atr=0.25, hold_bars=0, sl_atr=3.0, tp_r=1.0, trail=True, exit_opp=False))
