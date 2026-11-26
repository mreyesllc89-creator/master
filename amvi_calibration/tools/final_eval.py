"""Full evaluation of one setting: the numbers of the report.

Everything is in R (1 R = Stop Loss x the exit ATR at the signal = the amount risked per
trade with the script's Risk % sizing), net of costs unless stated:

  base      commission 0.05 % per side + 1 tick slippage + Binance funding (the lab's rule)
  bitget    0.06 % per side (Bitget's standard taker fee) + 1 tick + funding
  no_cost   no commission, no slippage, no funding
  stress    0.10 % per side + 3 ticks slippage + funding (the lab's stress)
  tv_view   roughly what TradingView's Strategy Tester shows for the calibrated file: stops
            and trailing stops walked on the chart's own candles (no Bar Magnifier), the
            file's 0.06 % commission, 1 tick slippage, no funding
  walk_1m, walk_chart   base costs, with the orders walked on 1-minute bars / on the chart's
            candles instead of second by second: how much the result owes to the path
  trail_restart   base costs, if the trailing stop started again at every candle close

Orders are filled on the second-by-second price path unless stated.

used as a library by report.py; `python final_eval.py <chart_tf> <json setting file>` prints one.
"""
import json
import sys

import numpy as np
import pandas as pd

import amvi_engine as E
import bars
import space
import sweep

BASE_FEE = sweep.BASE_FEE
STRESS_FEE = 0.0010
RISK_PCT = 0.5      # the calibrated files' sizing: 0.5 % of equity at risk per trade ...
LEV_CAP = 5.0       # ... but never a position larger than 5x equity (Margin 20 %)
SEARCH = (sweep.WINDOW_START, sweep.WINDOW_END)
PRESAMPLE = ("2021-01-01", "2023-11-01")     # never used by the search or the selection (covers May 2021 and the 2022 bear)
PRE_LOAD = "2020-01-01"


def trades_for(ft, fund, chart_tf, p, start, end, fee, slip, funding=True, walk="fine", trail_reset=False):
    ep = E.P(**space.engine_params(p))
    tr = E.run(ft, chart_tf, ep, fee=0.0, slip_ticks=slip, start_ms=sweep.ms(start), end_ms=sweep.ms(end),
               walk=walk, trail_reset=trail_reset)
    keep = tr["entry_t"] >= sweep.ms(start)
    tr = {k: v[keep] for k, v in tr.items()}
    fu = (tr["entry_px"] + tr["exit_px"]) / tr["risk"]
    fd = fund.paid(tr["entry_t"], tr["exit_t"], tr["dir"].astype(np.float64), tr["entry_px"], tr["risk"]) if (funding and fund is not None) else np.zeros(fu.size)
    tr["gross"] = tr["r"]
    tr["fee_r"] = fee * fu
    tr["fund_r"] = fd
    tr["r"] = tr["gross"] - tr["fee_r"] - fd
    tr["fee_u"] = fu
    return tr


def longest_losing_streak(r):
    best = cur = 0
    for x in r:
        cur = cur + 1 if x <= 0 else 0
        best = max(best, cur)
    return best


def max_drawdown(r):
    if r.size == 0:
        return 0.0
    eq = np.cumsum(r)
    return float((np.maximum.accumulate(np.maximum(eq, 0.0)) - eq).max())


def stats(tr, chart_tf=None, period=None):
    """period = (start, end): 'months' is then every calendar month of the period (a month
    without a trade is a month that was not positive); without it, the months with a trade."""
    r = tr["r"]
    n = int(r.size)
    if n == 0:
        return dict(n=0, total=0.0)
    wins = r[r > 0].sum()
    losses = -r[r <= 0].sum()
    t = pd.to_datetime(tr["entry_t"], unit="ms")
    ym = t.year * 100 + t.month
    months = pd.Series(r).groupby(np.asarray(ym)).sum()
    n_months = sweep.n_months(sweep.ms(period[0]), sweep.ms(period[1])) if period else int(months.size)
    s = dict(n=n, n_long=int((tr["dir"] > 0).sum()), n_short=int((tr["dir"] < 0).sum()), total=float(r.sum()),
             avg=float(r.mean()), pf=float(wins / losses) if losses > 0 else 99.0, win=float((r > 0).mean()),
             dd=max_drawdown(r), streak=longest_losing_streak(r), months=int(n_months),
             months_pos=int((months > 0).sum()), best_trade=float(r.max()), worst_trade=float(r.min()),
             t_stat=float(r.mean() / r.std(ddof=1) * np.sqrt(n)) if n > 2 and r.std(ddof=1) > 0 else 0.0,
             fee_r=float(tr["fee_r"].sum()), fund_r=float(tr["fund_r"].sum()), gross=float(tr["gross"].sum()),
             avg_risk_pct=float(np.mean(tr["risk"] / tr["entry_px"]) * 100))
    if chart_tf:
        s["avg_bars"] = float(np.mean((tr["exit_t"] - tr["entry_t"]) / (chart_tf * 60000.0)))
    # in % of equity with the files' sizing: a tight stop would need more than 5x leverage, the
    # position is then capped and less than 0.5 % is at risk on that trade
    stop_pct = tr["risk"] / tr["entry_px"] * 100
    at_risk = np.minimum(RISK_PCT, LEV_CAP * stop_pct)
    s["pct_total"] = float((r * at_risk).sum())
    s["pct_dd"] = max_drawdown(r * at_risk)
    s["cap_share"] = float((LEV_CAP * stop_pct < RISK_PCT).mean())
    srt = np.sort(r)[::-1]
    s["top10"] = float(srt[:10].sum())
    s["without_top10"] = float(srt[10:].sum())
    s["without_top20"] = float(srt[20:].sum())
    return s


def week_resample(tr, period, draws=5000, seed=7):
    """Share of resamples (the period's calendar weeks drawn with replacement, weeks without a
    trade included as zero) with a positive total."""
    r = tr["r"]
    if r.size == 0:
        return 0.0
    W = 7 * 86_400_000
    w0 = sweep.ms(period[0]) // W
    w1 = (sweep.ms(period[1]) - 1) // W
    sums = np.zeros(int(w1 - w0 + 1))
    wk = np.clip((tr["entry_t"] // W).astype(np.int64) - w0, 0, sums.size - 1)
    np.add.at(sums, wk, r)
    rng = np.random.default_rng(seed)
    tot = sums[rng.integers(0, sums.size, size=(draws, sums.size))].sum(1)
    return float((tot > 0).mean())


def by_year(tr):
    t = pd.to_datetime(tr["entry_t"], unit="ms")
    out = []
    for y in sorted(set(t.year)):
        m = np.asarray(t.year == y)
        r = tr["r"][m]
        out.append(dict(year=int(y), n=int(r.size), total=float(r.sum()), win=float((r > 0).mean()), dd=max_drawdown(r)))
    return out


def by_reason(tr):
    names = {E.X_STOP: "stop loss", E.X_TP: "take profit", E.X_TRAIL: "trailing stop", E.X_REV: "reversal",
             E.X_VOL: "volatility exit", E.X_TIME: "time stop", E.X_END: "open at the end"}
    out = []
    for k, name in names.items():
        m = tr["why"] == k
        if m.any():
            out.append(dict(reason=name, n=int(m.sum()), total=float(tr["r"][m].sum()), avg=float(tr["r"][m].mean())))
    return out


def half_split(start, end):
    """The boundary between the two halves used by the selection: whole calendar months, the
    first half = the first (months // 2) months."""
    nm = sweep.n_months(sweep.ms(start), sweep.ms(end))
    return sweep.ms(pd.Timestamp(start) + pd.DateOffset(months=nm // 2))


def halves(tr, start, end):
    mid = half_split(start, end)
    a = tr["r"][tr["entry_t"] < mid]
    b = tr["r"][tr["entry_t"] >= mid]
    return float(a.sum()), float(b.sum()), int(a.size), int(b.size)


def warm_date(ft, chart_tf, p):
    """First time at which every enabled AMVI timeframe has a value on the chart (ms)."""
    ep = E.P(**space.engine_params(p))
    ch = ft.mk.tf(chart_tf)
    worst = 0
    for tf in ep["tfs"]:
        v = E.gather(ft.amvi(tf, ep), ft.idx("amvi", chart_tf, tf))
        ok = np.nonzero(~np.isnan(v))[0]
        worst = max(worst, int(ok[0]) if ok.size else len(ch) - 1)
    return int(ch.t[worst])


def evaluate(ctx_search, ctx_pre, chart_tf, p, light=False):
    """All numbers for one setting. ctx_* = (features, funding) for the search window and for
    the untouched earlier window. light: only the base and stressed numbers of both windows."""
    ft, fund = ctx_search
    out = {}
    base = trades_for(ft, fund, chart_tf, p, *SEARCH, fee=BASE_FEE, slip=1)
    out["base"] = stats(base, chart_tf, SEARCH)
    out["base"]["h1"], out["base"]["h2"], out["base"]["n_h1"], out["base"]["n_h2"] = halves(base, *SEARCH)
    out["base"]["weeks_pos"] = week_resample(base, SEARCH)
    st = trades_for(ft, fund, chart_tf, p, *SEARCH, fee=STRESS_FEE, slip=3)
    out["stress"] = stats(st, chart_tf, SEARCH)
    out["stress"]["h1"], out["stress"]["h2"], _, _ = halves(st, *SEARCH)
    if not light:
        out["by_year"] = by_year(base)
        out["by_reason"] = by_reason(base)
        out["bitget"] = stats(trades_for(ft, fund, chart_tf, p, *SEARCH, fee=0.0006, slip=1), chart_tf)
        out["no_cost"] = stats(trades_for(ft, fund, chart_tf, p, *SEARCH, fee=0.0, slip=0, funding=False), chart_tf)
        out["tv_view"] = stats(trades_for(ft, fund, chart_tf, p, *SEARCH, fee=0.0006, slip=1, funding=False, walk="chart"), chart_tf)
        out["walk_1m"] = stats(trades_for(ft, fund, chart_tf, p, *SEARCH, fee=BASE_FEE, slip=1, walk="1m"), chart_tf)
        out["walk_chart"] = stats(trades_for(ft, fund, chart_tf, p, *SEARCH, fee=BASE_FEE, slip=1, walk="chart"), chart_tf)
        if p.get("trail"):
            out["trail_restart"] = stats(trades_for(ft, fund, chart_tf, p, *SEARCH, fee=BASE_FEE, slip=1, trail_reset=True), chart_tf)
        fu = base["fee_u"].sum()
        out["breakeven_fee_pct"] = float((base["gross"].sum() - base["fund_r"].sum()) / fu * 100) if fu > 0 else 0.0
        flip = dict(p)
        flip["inverted"] = not p["inverted"]
        out["other_direction"] = stats(trades_for(ft, fund, chart_tf, flip, *SEARCH, fee=BASE_FEE, slip=1), chart_tf)
    if ctx_pre is not None:
        pf, pfund = ctx_pre
        # the untouched period is scored from the first day on which every AMVI timeframe of
        # the setting has a value (a daily AMVI with long periods needs up to 600 days)
        warm = warm_date(pf, chart_tf, p)
        pre_from = PRESAMPLE[0]
        if warm > sweep.ms(PRESAMPLE[0]):
            pre_from = (pd.Timestamp(warm, unit="ms").normalize() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        out["pre_from"] = pre_from
        pre = trades_for(pf, pfund, chart_tf, p, pre_from, PRESAMPLE[1], fee=BASE_FEE, slip=1)
        out["_pre_trades"] = pre
        out["pre"] = stats(pre, chart_tf, (pre_from, PRESAMPLE[1]))
        out["pre"]["weeks_pos"] = week_resample(pre, (pre_from, PRESAMPLE[1]))
        out["pre_by_year"] = by_year(pre)
        out["pre_stress"] = stats(trades_for(pf, pfund, chart_tf, p, pre_from, PRESAMPLE[1], fee=STRESS_FEE, slip=3), chart_tf, (pre_from, PRESAMPLE[1]))
        if not light:
            out["pre_tv_view"] = stats(trades_for(pf, pfund, chart_tf, p, pre_from, PRESAMPLE[1], fee=0.0006, slip=1, funding=False, walk="chart"), chart_tf)
            if p.get("trail"):
                out["pre_trail_restart"] = stats(trades_for(pf, pfund, chart_tf, p, pre_from, PRESAMPLE[1], fee=BASE_FEE, slip=1, trail_reset=True), chart_tf)
    out["_trades"] = base
    return out


def contexts(need_pre=True):
    cs = sweep.load_context(start=sweep.LOAD_START, end=SEARCH[1], sec_start=SEARCH[0])
    cp = sweep.load_context(start=PRE_LOAD, end=PRESAMPLE[1], sec_start=PRESAMPLE[0]) if need_pre else None
    return cs, cp


def line(tag, s):
    if not s or s.get("n", 0) == 0:
        return f"{tag}: no trades"
    return (f"{tag}: {s['n']} trades ({s['n_long']}L/{s['n_short']}S), {s['total']:+.1f}R, PF {s['pf']:.2f}, {s['win'] * 100:.0f}% winners, "
            f"max DD {s['dd']:.1f}R, longest losing streak {s['streak']}, {s['months_pos']} of {s['months']} months positive")


if __name__ == "__main__":
    ctf = int(sys.argv[1])
    p = space.normalize(json.load(open(sys.argv[2])))
    cs, cp = contexts()
    e = evaluate(cs, cp, ctf, p)
    print(line("search window, base costs", e["base"]))
    print(f"  halves {e['base']['h1']:+.1f} / {e['base']['h2']:+.1f}R; weeks resampled positive {e['base']['weeks_pos'] * 100:.1f}%; "
          f"top 10 trades {e['base']['top10']:+.1f}R, without them {e['base']['without_top10']:+.1f}R; break-even fee {e['breakeven_fee_pct']:.3f}% per side")
    print(line("  Bitget taker 0.06% + funding", e["bitget"]))
    print(line("  no costs", e["no_cost"]))
    print(line("  stressed costs", e["stress"]))
    print(line("  orders walked on 1-minute bars", e["walk_1m"]))
    print(line("  orders walked on chart candles", e["walk_chart"]))
    print(line("  TradingView's view (chart candles, 0.06%, no funding)", e["tv_view"]))
    if "trail_restart" in e:
        print(line("  trailing stop restarted at every candle close", e["trail_restart"]))
    print(line("  other trade direction", e["other_direction"]))
    print(line(f"untouched {e['pre_from']} to 2023-10, base costs", e.get("pre")))
    print(line("  stressed costs", e.get("pre_stress")))
