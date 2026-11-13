"""Individual report for one calibrated preset: stats, yearly/monthly tables, trade list, equity chart.

usage: python -I trade_report.py XAUUSD_M60 [spread_model]
writes results/report_<KEY>.md, results/trades_<KEY>.csv, results/report_<KEY>.png
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from data import load_bars, with_spread
from engine import backtest
from params import resolve
from sweep import CACHE, CAPITAL, DATA, IS_YEARS, RESULTS

REASON = {0: "stop", 1: "target", 2: "dead exit", 3: "time stop", 4: "blackout close", 5: "reversal", 6: "end of data"}


def trades_frame(tr, bars, tf):
    df = pd.DataFrame({
        "entry_time": pd.to_datetime(bars["utc"][tr["i"]], unit="s"),
        "exit_time": pd.to_datetime(bars["utc"][tr["o"]], unit="s"),
        "side": np.where(tr["side"] > 0, "long", "short"),
        "bars_held": tr["o"] - tr["i"],
        "pnl_usd": tr["pnl"].round(2), "r_multiple": tr["r"].round(3),
        "exit": [REASON[int(x)] for x in tr["reason"]],
    })
    df["equity"] = (CAPITAL + df.pnl_usd.cumsum()).round(2)
    return df


def stats(df):
    pnl = df.pnl_usd.values
    eq = CAPITAL + np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[CAPITAL], eq]))[1:]
    dd = (peak - eq) / peak
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    wins = pnl > 0
    streak = max_l = cur = 0
    for w in wins:
        cur = cur + 1 if not w else 0
        max_l = max(max_l, cur)
    yrs = max((df.exit_time.iloc[-1] - df.entry_time.iloc[0]).days / 365.25, 1e-9)
    return {
        "Trades": len(df), "Trades per year": round(len(df) / yrs, 1),
        "Net profit": f"${pnl.sum():,.0f} ({100 * pnl.sum() / CAPITAL:,.0f} %)",
        "CAGR": f"{100 * ((eq[-1] / CAPITAL) ** (1 / yrs) - 1):.1f} %" if eq[-1] > 0 else "ruin",
        "Profit factor": round(gp / gl, 2) if gl else "inf",
        "Win rate": f"{100 * wins.mean():.1f} %",
        "Average trade": f"${pnl.mean():,.2f} ({df.r_multiple.mean():+.3f} R)",
        "Average win / loss": f"${pnl[wins].mean():,.2f} / ${pnl[~wins].mean():,.2f}",
        "Largest win / loss": f"${pnl.max():,.2f} / ${pnl.min():,.2f}",
        "Max drawdown": f"{100 * dd.max():.1f} % (${(peak - eq).max():,.0f})",
        "Longest losing streak": max_l,
        "Average bars held": round(df.bars_held.mean(), 1),
        "Long / short trades": f"{(df.side == 'long').sum()} / {(df.side == 'short').sum()}",
        "Long / short net": f"${pnl[df.side == 'long'].sum():,.0f} / ${pnl[df.side == 'short'].sum():,.0f}",
        "Sharpe (per-trade, annualised)": round(pnl.mean() / pnl.std() * np.sqrt(len(df) / yrs), 2) if pnl.std() else 0,
    }


def main():
    key = sys.argv[1]; model = sys.argv[2] if len(sys.argv) > 2 else "modern"
    symbol, tf = key.split("_M"); tf = int(tf)
    cfg = json.load(open(os.path.join(RESULTS, "final_configs.json")))[key]
    P = resolve(cfg, symbol, tf, CAPITAL)
    segs = load_bars(DATA, symbol, tf, CACHE)
    out = [f"# {key} — individual backtest report", "",
           f"Preset `presets/DPFX_{key}_calibrated.set`, chart {symbol} M{tf}, spread model **{model}**, "
           f"${CAPITAL:,.0f} start, 1 % risk per trade, Python replica of the EA (see REPORT.md for the method).", ""]
    frames = []
    for name, raw in segs:
        bars = with_spread(raw, symbol, model)
        tr = backtest(bars, P)
        df = trades_frame(tr, bars, tf); df["segment"] = name; frames.append(df)
        out += [f"## Segment {name} ({pd.to_datetime(bars['utc'][0], unit='s'):%Y-%m-%d} → {pd.to_datetime(bars['utc'][-1], unit='s'):%Y-%m-%d})", ""]
        if len(df) < 2:
            out += [f"{len(df)} trade(s) only.", ""]; continue
        out.append("| Metric | Value |"); out.append("|---|---|")
        for k, v in stats(df).items():
            out.append(f"| {k} | {v} |")
        out.append("")
        lo, hi = IS_YEARS[symbol]
        y = df.groupby(df.exit_time.dt.year).agg(trades=("pnl_usd", "size"), net=("pnl_usd", "sum"),
                                                 win=("pnl_usd", lambda s: 100 * (s > 0).mean()),
                                                 avg_r=("r_multiple", "mean"))
        if len(y) > 1:
            out += ["### By year", "", "| Year | Trades | Net | Win % | Avg R | Sample |", "|---|---|---|---|---|---|"]
            for yr, r in y.iterrows():
                tag = "in-sample" if lo <= yr <= hi else "out-of-sample"
                out.append(f"| {yr} | {int(r.trades)} | ${r.net:,.0f} | {r.win:.0f} | {r.avg_r:+.2f} | {tag} |")
            out.append("")
        m = df.groupby(df.exit_time.dt.to_period("M")).agg(trades=("pnl_usd", "size"), net=("pnl_usd", "sum"))
        out += ["### By month", "", f"{(m.net > 0).sum()} of {len(m)} months profitable; worst month ${m.net.min():,.0f}, best ${m.net.max():,.0f}.", ""]
        if len(m) <= 40:
            out += ["| Month | Trades | Net |", "|---|---|---|"] + [f"| {p} | {int(r.trades)} | ${r.net:,.0f} |" for p, r in m.iterrows()] + [""]
        ex = df.groupby("exit").agg(n=("pnl_usd", "size"), net=("pnl_usd", "sum"), avg_r=("r_multiple", "mean"))
        out += ["### By exit reason", "", "| Exit | Trades | Net | Avg R |", "|---|---|---|---|"]
        out += [f"| {e} | {int(r.n)} | ${r.net:,.0f} | {r.avg_r:+.2f} |" for e, r in ex.iterrows()] + [""]
        out += ["### Last 15 trades", "", df.tail(15).to_markdown(index=False), ""]
    allt = pd.concat(frames)
    allt.to_csv(os.path.join(RESULTS, f"trades_{key}.csv"), index=False)
    fig, axes = plt.subplots(len(frames), 1, figsize=(10, 4 * len(frames)))
    for ax, df, (name, _) in zip(np.atleast_1d(axes), frames, segs):
        ax.plot(df.exit_time, df.equity, lw=1)
        ax.set_title(f"{key} equity, segment {name}, {model} spread, 1 % risk"); ax.grid(alpha=0.3)
        if len(df) > 50:
            ax.set_yscale("log")
    fig.tight_layout(); fig.savefig(os.path.join(RESULTS, f"report_{key}.png"), dpi=110)
    out += ["## Files", "", f"Full trade list: `results/trades_{key}.csv`; equity chart: `results/report_{key}.png`."]
    with open(os.path.join(RESULTS, f"report_{key}.md"), "w") as fh:
        fh.write("\n".join(out))
    print("\n".join(out[:40]))


if __name__ == "__main__":
    main()
