"""FlashGold v5 (BTCUSD FGF build) with the FlashGold Direction Filter OFF vs ON.

Runs the strategy twice on the same TradingView chart export, once with the
filter gate off and once on, and scores both the way docs/rules/validation.md
asks: TradingView-style fills and worst-case fills, each without and with
costs, on the whole period and on each half.

Usage:
    python -I tools/fgf_ab/fgf_ab.py <export.csv> [--out report.md] [options]

<export.csv> is TradingView's "Export chart data" of the chart you trade
(1m to 1H; 5m or lower recommended so the 60m filter has many candles):
columns time, open, high, low, close (time as Unix seconds or ISO). The
filter's 60m / 120m / 240m candles and the chart x2 / x4 zones are built
from it, aligned to 00:00 UTC like TradingView's crypto candles.

Engine: fg5.py, the Python replay of the FlashGold v5 strategy and the FGF
gate from tools/vt_top10_stress/engines (branch claude/hopeful-meitner-4ky6wl),
unchanged. Defaults below are the strategy's input defaults on main.
"""
import argparse, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fg5 as F


def load_csv(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    for c in ("time", "open", "high", "low", "close"):
        if c not in df.columns:
            sys.exit(f"{path}: missing column '{c}' (need time, open, high, low, close)")
    t = df["time"]
    if np.issubdtype(t.dtype, np.number):
        ms = (t.astype("int64") * (1000 if t.max() < 1e12 else 1)).to_numpy()
    else:
        ms = (pd.to_datetime(t, utc=True).astype("int64") // 1_000_000).to_numpy()
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    order = np.argsort(ms, kind="stable")
    ms, o, h, l, c = ms[order], o[order], h[order], l[order], c[order]
    keep = np.r_[True, ms[1:] != ms[:-1]]
    return ms[keep], o[keep], h[keep], l[keep], c[keep]


def tv_path(o, h, l, c):
    """4-point path per bar, TradingView's broker-emulator rule: open nearer
    the high -> open, high, low, close; else open, low, high, close."""
    up_first = (h - o) <= (o - l)
    p = np.empty((len(o), 4))
    p[:, 0] = o; p[:, 3] = c
    p[:, 1] = np.where(up_first, h, l); p[:, 2] = np.where(up_first, l, h)
    return p.ravel()


def build(ms, o, h, l, c, tf_ms):
    n = len(ms)
    chart = F.Bars(ms, o, h, l, c, tf_ms, np.arange(n) * 4, np.arange(n) * 4 + 4)
    path = tv_path(o, h, l, c)
    path_t = np.repeat(ms, 4) + np.tile(np.arange(4), n)
    return chart, path_t, path


def resample_to(chart, target_ms):
    if target_ms % chart.tf_ms:
        sys.exit(f"chart timeframe {chart.tf_ms // 60000}m does not divide {target_ms // 60000}m")
    return F.resample(chart, target_ms // chart.tf_ms) if target_ms != chart.tf_ms else chart


def score(tr, cost, mid_ms):
    """Whole period and the two halves (split by entry time)."""
    out = {}
    for name, sub in (("all", tr), ("H1", tr[tr.entry_t < mid_ms] if len(tr) else tr),
                      ("H2", tr[tr.entry_t >= mid_ms] if len(tr) else tr)):
        out[name] = F.metrics(sub, cost)
    return out


def fmt_pf(x):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else ("inf" if np.isinf(x) else f"{x:.2f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("csv")
    ap.add_argument("--out", default="fgf_ab_report.md")
    ap.add_argument("--tick", type=float, default=0.01, help="symbol mintick (BTCUSD 0.01)")
    ap.add_argument("--qty", type=float, default=10, help="contracts (strategy default 10)")
    ap.add_argument("--unit", type=float, default=1.0, help="P&L per 1 price unit per contract")
    ap.add_argument("--comm-pct", type=float, default=0.02, help="commission %% of notional per side")
    ap.add_argument("--slip-ticks", type=int, default=5, help="slippage ticks per side")
    ap.add_argument("--spread-pts", type=float, default=25.0)
    ap.add_argument("--filter-tf", type=int, default=60, help="filter timeframe, minutes")
    ap.add_argument("--band-atr", type=float, default=0.25)
    ap.add_argument("--no-against", action="store_true", help="filter: do not allow trading against the signal")
    ap.add_argument("--exit-mode", default="Pips", choices=["Pips", "ATR", "Points"])
    ap.add_argument("--warmup-days", type=float, default=3.0, help="no trades before this (indicator warm-up)")
    ap.add_argument("--placebos", type=int, default=20, help="random filters that block the same share of signals")
    a = ap.parse_args()

    ms, o, h, l, c = load_csv(a.csv)
    tf_ms = int(np.median(np.diff(ms)))
    chart, path_t, path = build(ms, o, h, l, c, tf_ms)
    z2 = F.resample(chart, 2); z3 = F.resample(chart, 4)
    fb = resample_to(chart, a.filter_tf * 60000)
    fz2 = F.resample(fb, 2); fz3 = F.resample(fb, 4)
    sp = F.SigParams(spread_pts=a.spread_pts)
    sig = F.signal(chart, z2, z3, sp, a.tick)
    start_ms = ms[0] + int(a.warmup_days * 86400000)
    start_bar = int(np.searchsorted(ms, start_ms))
    mid_ms = start_ms + (ms[-1] - start_ms) // 2
    xp = F.ExitParams(mode=a.exit_mode)

    gates = {"off": F.fgf_gate(chart, fb, fz2, fz3, sp, a.tick, enabled=False)[:2],
             "on": F.fgf_gate(chart, fb, fz2, fz3, sp, a.tick, band_atr=a.band_atr, against=not a.no_against, enabled=True)[:2]}
    costs = {"no costs": F.Costs(qty=a.qty, unit=a.unit, comm_side_per_qty=0.0, comm_pct=0.0, slip_ticks=0, tick=a.tick),
             "with costs": F.Costs(qty=a.qty, unit=a.unit, comm_side_per_qty=0.0, comm_pct=a.comm_pct, slip_ticks=a.slip_ticks, tick=a.tick)}
    # Placebo: a random gate that keeps the same share of signal bars as the
    # real filter. Blocking signals saves costs whatever the filter knows, so
    # the real filter must beat these, not just "filter off".
    is_sig = (sig["buy"] | sig["sell"]) & (np.arange(len(ms)) >= start_bar)
    kept = np.where(sig["buy"], gates["on"][0], gates["on"][1])[is_sig]
    keep_p = float(kept.mean()) if len(kept) else 1.0
    rng = np.random.default_rng(7)
    placebo = [(rng.random(len(ms)) < keep_p, rng.random(len(ms)) < keep_p) for _ in range(a.placebos)]
    rows = []; prow = []
    for fill in ("TradingView", "worst case"):
        for cname, cost in costs.items():
            for g in ("off", "on"):
                tr, info = F.run(chart, path_t, path, path, sig, gates[g][0], gates[g][1], xp, cost,
                                 synthetic=True, worst_case=(fill == "worst case"), start_bar=start_bar)
                s = score(tr, cost, mid_ms)
                rows.append(dict(fill=fill, costs=cname, filter=g, placed=info["placed"], blocked=info["blocked"],
                                 trades=s["all"]["trades"], net=s["all"]["net"], pf=s["all"]["pf"], win=s["all"]["win"],
                                 maxdd=s["all"]["maxdd"], h1=s["H1"]["net"], h2=s["H2"]["net"]))
            for gb, gs in placebo:
                tr, info = F.run(chart, path_t, path, path, sig, gb, gs, xp, cost,
                                 synthetic=True, worst_case=(fill == "worst case"), start_bar=start_bar)
                s = score(tr, cost, mid_ms)
                prow.append(dict(fill=fill, costs=cname, net=s["all"]["net"], h1=s["H1"]["net"], h2=s["H2"]["net"]))
    R = pd.DataFrame(rows); P = pd.DataFrame(prow)
    R.to_csv(os.path.splitext(a.out)[0] + ".csv", index=False)

    d0 = pd.to_datetime(start_ms, unit="ms", utc=True); d1 = pd.to_datetime(ms[-1], unit="ms", utc=True)
    dm = pd.to_datetime(mid_ms, unit="ms", utc=True)
    L = [f"# FlashGold Direction Filter: off vs on", "",
         f"Data: `{os.path.basename(a.csv)}`, {tf_ms // 60000}m chart, {len(ms)} bars; scored {d0:%Y-%m-%d %H:%M} to {d1:%Y-%m-%d %H:%M} UTC "
         f"(after {a.warmup_days:g} warm-up days), halves split at {dm:%Y-%m-%d %H:%M}.",
         f"Strategy: FlashGold v5 (BTCUSD FGF build) input defaults, exits {a.exit_mode}, {a.qty:g} contracts. "
         f"Filter: {a.filter_tf}m, band {a.band_atr:g} ATR, against {'off' if a.no_against else 'on'}. "
         f"Costs: {a.comm_pct:g}% per side + {a.slip_ticks} ticks slippage per side.", "",
         "| Fills | Costs | Filter | Trades | Net | Net/trade | PF | Win | Max DD | H1 net | H2 net | Signals blocked |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['fill']} | {r['costs']} | {r['filter']} | {r['trades']} | {r['net']:.0f} | "
                 f"{(r['net'] / r['trades'] if r['trades'] else float('nan')):.1f} | {fmt_pf(r['pf'])} | "
                 f"{(r['win'] * 100 if r['trades'] else float('nan')):.0f}% | {r['maxdd']:.0f} | {r['h1']:.0f} | {r['h2']:.0f} | "
                 f"{r['blocked'] if r['filter'] == 'on' else '-'} |")
    L += ["", "## Filter on minus filter off (net)", "", "| Fills | Costs | All | H1 | H2 |", "|---|---|---|---|---|"]
    for fill in ("TradingView", "worst case"):
        for cname in costs:
            off = R[(R.fill == fill) & (R.costs == cname) & (R["filter"] == "off")].iloc[0]
            on = R[(R.fill == fill) & (R.costs == cname) & (R["filter"] == "on")].iloc[0]
            L.append(f"| {fill} | {cname} | {on.net - off.net:+.0f} | {on.h1 - off.h1:+.0f} | {on.h2 - off.h2:+.0f} |")
    L += ["", f"## Filter on vs {a.placebos} random filters keeping the same share of signals ({keep_p:.0%})", "",
          "Beats = the share of random filters whose net the real filter beats.", "",
          "| Fills | Costs | Filter on: all / H1 / H2 | Random median: all / H1 / H2 | Beats: all / H1 / H2 |",
          "|---|---|---|---|---|"]
    verdict = None
    for fill in ("TradingView", "worst case"):
        for cname in costs:
            on = R[(R.fill == fill) & (R.costs == cname) & (R["filter"] == "on")].iloc[0]
            pp = P[(P.fill == fill) & (P.costs == cname)]
            bt = [float((on[k] > pp[k]).mean()) if len(pp) else float("nan") for k in ("net", "h1", "h2")]
            md = [pp[k].median() if len(pp) else float("nan") for k in ("net", "h1", "h2")]
            L.append(f"| {fill} | {cname} | {on.net:.0f} / {on.h1:.0f} / {on.h2:.0f} | {md[0]:.0f} / {md[1]:.0f} / {md[2]:.0f} | "
                     f"{bt[0]:.0%} / {bt[1]:.0%} / {bt[2]:.0%} |")
            if fill == "worst case" and cname == "with costs":
                verdict = min(bt)
    L += ["", "**Read it this way:** the filter earns its place only if, in the worst-case, with-costs row, it beats "
          "at least 90% of the random filters on the whole period AND in each half. Beating \"filter off\" is not "
          "enough: any filter that trades less pays less in costs.",
          "", f"**Verdict:** {'PASS' if verdict is not None and verdict >= 0.9 else 'NOT SHOWN'} "
          f"(worst case, with costs: beats {verdict:.0%} of random filters in its weakest of all / H1 / H2).",
          "", "Fills: \"TradingView\" walks each bar open -> nearer extreme -> other extreme -> close and fills stops at their "
          "price (plus slippage); \"worst case\" moves price against an open position first inside every bar. "
          "This is a replica on OHLC bars, not TradingView itself: expect the trade counts to differ a little from the "
          "Strategy Tester."]
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
