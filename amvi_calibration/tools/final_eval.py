"""Full evaluation of one setting: the numbers of the report.

Everything is in R (1 R = Stop Loss x the exit ATR at the signal = the amount risked per
trade with the script's Risk % sizing), net of costs unless stated:

  base      commission 0.05 % per side + 1 tick slippage + Binance funding (the lab's rule)
  bitget    0.06 % per side (Bitget's standard taker fee) + 1 tick + funding
  tv_file   what TradingView shows with the calibrated file's Properties (commission 0.05 %,
            1 tick slippage; TradingView does not charge funding)
  tv_0.04   the same with the 0.04 % commission of the original file
  no_cost   no commission, no slippage, no funding
  stress    0.10 % per side + 3 ticks slippage + funding (the lab's stress)

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
SEARCH = ("2023-11-01", "2026-11-26")
PRESAMPLE = ("2021-01-01", "2023-11-01")     # never used by the search or the selection (covers May 2021 and the 2022 bear)
PRE_LOAD = "2020-01-01"


def trades_for(ft, fund, chart_tf, p, start, end, fee, slip, funding=True):
    ep = E.P(**space.engine_params(p))
    tr = E.run(ft, chart_tf, ep, fee=0.0, slip_ticks=slip, start_ms=sweep.ms(start), end_ms=sweep.ms(end))
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


def stats(tr, chart_tf=None):
    r = tr["r"]
    n = int(r.size)
    if n == 0:
        return dict(n=0, total=0.0)
    wins = r[r > 0].sum()
    losses = -r[r <= 0].sum()
    t = pd.to_datetime(tr["entry_t"], unit="ms")
    ym = t.year * 100 + t.month
    months = pd.Series(r).groupby(np.asarray(ym)).sum()
    s = dict(n=n, n_long=int((tr["dir"] > 0).sum()), n_short=int((tr["dir"] < 0).sum()), total=float(r.sum()),
             avg=float(r.mean()), pf=float(wins / losses) if losses > 0 else 99.0, win=float((r > 0).mean()),
             dd=max_drawdown(r), streak=longest_losing_streak(r), months=int(months.size),
             months_pos=int((months > 0).sum()), best_trade=float(r.max()), worst_trade=float(r.min()),
             t_stat=float(r.mean() / r.std(ddof=1) * np.sqrt(n)) if n > 2 and r.std(ddof=1) > 0 else 0.0,
             fee_r=float(tr["fee_r"].sum()), fund_r=float(tr["fund_r"].sum()), gross=float(tr["gross"].sum()),
             avg_risk_pct=float(np.mean(tr["risk"] / tr["entry_px"]) * 100))
    if chart_tf:
        s["avg_bars"] = float(np.mean((tr["exit_t"] - tr["entry_t"]) / (chart_tf * 60000.0)))
    srt = np.sort(r)[::-1]
    s["top10"] = float(srt[:10].sum())
    s["without_top10"] = float(srt[10:].sum())
    s["without_top20"] = float(srt[20:].sum())
    return s


def week_resample(tr, draws=5000, seed=7):
    """Share of resamples (calendar weeks drawn with replacement) with a positive total."""
    r = tr["r"]
    if r.size == 0:
        return 0.0
    wk = (tr["entry_t"] // (7 * 86_400_000)).astype(np.int64)
    u, inv = np.unique(wk, return_inverse=True)
    sums = np.zeros(u.size)
    np.add.at(sums, inv, r)
    rng = np.random.default_rng(seed)
    tot = sums[rng.integers(0, u.size, size=(draws, u.size))].sum(1)
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


def halves(tr, start, end):
    mid = (sweep.ms(start) + sweep.ms(end)) // 2
    a = tr["r"][tr["entry_t"] < mid]
    b = tr["r"][tr["entry_t"] >= mid]
    return float(a.sum()), float(b.sum()), int(a.size), int(b.size)


def evaluate(ctx_search, ctx_pre, chart_tf, p):
    """All numbers for one setting. ctx_* = (features, funding) for the search window and for
    the untouched earlier window."""
    ft, fund = ctx_search
    out = {}
    base = trades_for(ft, fund, chart_tf, p, *SEARCH, fee=BASE_FEE, slip=1)
    out["base"] = stats(base, chart_tf)
    out["base"]["h1"], out["base"]["h2"], out["base"]["n_h1"], out["base"]["n_h2"] = halves(base, *SEARCH)
    out["base"]["weeks_pos"] = week_resample(base)
    out["by_year"] = by_year(base)
    out["by_reason"] = by_reason(base)
    out["bitget"] = stats(trades_for(ft, fund, chart_tf, p, *SEARCH, fee=0.0006, slip=1), chart_tf)
    out["tv_file"] = stats(trades_for(ft, fund, chart_tf, p, *SEARCH, fee=BASE_FEE, slip=1, funding=False), chart_tf)
    out["tv_004"] = stats(trades_for(ft, fund, chart_tf, p, *SEARCH, fee=0.0004, slip=1, funding=False), chart_tf)
    out["no_cost"] = stats(trades_for(ft, fund, chart_tf, p, *SEARCH, fee=0.0, slip=0, funding=False), chart_tf)
    st = trades_for(ft, fund, chart_tf, p, *SEARCH, fee=STRESS_FEE, slip=3)
    out["stress"] = stats(st, chart_tf)
    out["stress"]["h1"], out["stress"]["h2"], _, _ = halves(st, *SEARCH)
    fu = base["fee_u"].sum()
    out["breakeven_fee_pct"] = float((base["gross"].sum() - base["fund_r"].sum()) / fu * 100) if fu > 0 else 0.0
    flip = dict(p)
    flip["inverted"] = not p["inverted"]
    out["other_direction"] = stats(trades_for(ft, fund, chart_tf, flip, *SEARCH, fee=BASE_FEE, slip=1), chart_tf)
    if ctx_pre is not None:
        pf, pfund = ctx_pre
        pre = trades_for(pf, pfund, chart_tf, p, *PRESAMPLE, fee=BASE_FEE, slip=1)
        out["pre"] = stats(pre, chart_tf)
        out["pre"]["weeks_pos"] = week_resample(pre)
        out["pre_by_year"] = by_year(pre)
        out["pre_stress"] = stats(trades_for(pf, pfund, chart_tf, p, *PRESAMPLE, fee=STRESS_FEE, slip=3), chart_tf)
    out["_trades"] = base
    return out


def contexts(need_pre=True):
    cs = sweep.load_context(start=sweep.LOAD_START, end=SEARCH[1])
    cp = sweep.load_context(start=PRE_LOAD, end=PRESAMPLE[1]) if need_pre else None
    return cs, cp


def line(tag, s):
    if not s or s.get("n", 0) == 0:
        return f"{tag}: no trades"
    return (f"{tag}: {s['n']} trades ({s['n_long']}L/{s['n_short']}S), {s['total']:+.1f}R, PF {s['pf']:.2f}, {s['win'] * 100:.0f}% winners, "
            f"max DD {s['dd']:.1f}R, longest losing streak {s['streak']}, {s['months_pos']} of {s['months']} months positive")


if __name__ == "__main__":
    ctf = int(sys.argv[1])
    p = json.load(open(sys.argv[2]))
    cs, cp = contexts()
    e = evaluate(cs, cp, ctf, p)
    print(line("search window, base costs", e["base"]))
    print(f"  halves {e['base']['h1']:+.1f} / {e['base']['h2']:+.1f}R; weeks resampled positive {e['base']['weeks_pos'] * 100:.1f}%; "
          f"top 10 trades {e['base']['top10']:+.1f}R, without them {e['base']['without_top10']:+.1f}R; break-even fee {e['breakeven_fee_pct']:.3f}% per side")
    print(line("  Bitget taker 0.06% + funding", e["bitget"]))
    print(line("  TradingView view (0.05%, no funding)", e["tv_file"]))
    print(line("  TradingView view (0.04%, no funding)", e["tv_004"]))
    print(line("  no costs", e["no_cost"]))
    print(line("  stressed costs", e["stress"]))
    print(line("  other trade direction", e["other_direction"]))
    print(line("untouched 2021-09 to 2023-10, base costs", e.get("pre")))
