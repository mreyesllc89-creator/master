"""Stage 3: evaluate the chosen configs under every spread model, per year, write presets + chart.

usage: python -I final_eval.py            (reads results/refined_*.csv, picks per symbol/timeframe)
writes results/final_table.csv, results/final_configs.json, presets/*.set, results/equity_*.png
"""
import glob
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
from setfile import write_set
from sweep import CACHE, CAPITAL, DATA, IS_YEARS, RESULTS, rstats, equity_stats

PRESETS = os.path.join(os.path.dirname(__file__), "..", "presets")
MODELS = ("modern", "recorded", "mid")


def choose(df, symbol):
    """Best refined candidate per timeframe: highest OOS t-stat among those with IS t > 2."""
    ok = df[(df.is_tstat > 2.0) & (df.oos_n >= 50)]
    if ok.empty:
        ok = df
    return ok.sort_values("oos_tstat", ascending=False).iloc[0]


def evaluate_full(cfg, symbol, tf):
    rows = {}
    curves = {}
    for model in MODELS:
        segs = [(n, with_spread(b, symbol, model)) for n, b in load_bars(DATA, symbol, tf, CACHE)]
        P = resolve(cfg, symbol, tf, CAPITAL)
        name, bars = segs[0]
        tr = backtest(bars, P)
        yrs = bars["year"][tr["o"]]
        lo, hi = IS_YEARS[symbol]
        m_is = (yrs >= lo) & (yrs <= hi)
        r = {}
        for tag, m in (("is", m_is), ("oos", ~m_is), ("all", np.ones(len(yrs), bool))):
            for k, v in rstats(tr["r"][m], tr["pnl"][m]).items():
                r[f"{tag}_{k}"] = v
        r.update({f"all_{k}": v for k, v in equity_stats(tr["pnl"]).items()})
        for y in np.unique(yrs):
            m = yrs == y
            r[f"y{int(y)}_net"] = float(tr["pnl"][m].sum()); r[f"y{int(y)}_n"] = int(m.sum())
        tr2 = backtest(segs[1][1], P)
        for k, v in rstats(tr2["r"], tr2["pnl"]).items():
            r[f"x26_{k}"] = v
        r.update({f"x26_{k}": v for k, v in equity_stats(tr2["pnl"]).items()})
        reasons = np.bincount(tr["reason"], minlength=7)
        r["exit_mix"] = "stop %d / tp %d / dead %d / time %d / blackout %d / reverse %d" % tuple(reasons[:6])
        rows[model] = r
        curves[model] = (bars["utc"][tr["o"]], CAPITAL + np.cumsum(tr["pnl"]))
    return rows, curves


if __name__ == "__main__":
    os.makedirs(PRESETS, exist_ok=True)
    table, configs = [], {}
    for f in sorted(glob.glob(os.path.join(RESULTS, "refined_*_modern.csv"))):
        _, symbol, tf, _ = os.path.basename(f).split("_")
        tf = int(tf)
        df = pd.read_csv(f)
        if df.empty:
            continue
        row = choose(df, symbol)
        cfg = json.loads(row.cfg)
        rows, curves = evaluate_full(cfg, symbol, tf)
        key = f"{symbol}_M{tf}"
        configs[key] = cfg
        for model, r in rows.items():
            r.update(symbol=symbol, tf=tf, model=model, key=key)
            table.append(r)
        write_set(os.path.join(PRESETS, f"DPFX_{key}_calibrated.set"), cfg, symbol,
                  note=f"DannyPhantom V10.21.1 calibrated for {symbol} M{tf}; see danny_phantom_calibration/REPORT.md")
        fig, ax = plt.subplots(figsize=(9, 4))
        for model, (t, eq) in curves.items():
            ax.plot(pd.to_datetime(t, unit="s"), eq, label=model, lw=1)
        lo, hi = IS_YEARS[symbol]
        ax.axvline(pd.Timestamp(f"{hi + 1}-01-01"), color="k", ls="--", lw=0.8)
        ax.set_yscale("log"); ax.set_title(f"{key} calibrated, 1% risk, $10k start (dashed = OOS start)")
        ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
        fig.savefig(os.path.join(RESULTS, f"equity_{key}.png"), dpi=110); plt.close(fig)
        m = rows["modern"]
        print(f"{key:12s} IS t {m['is_tstat']:.2f} n {m['is_n']:5d} | OOS t {m['oos_tstat']:.2f} n {m['oos_n']:5d} "
              f"avgR {m['oos_avg_r']:+.3f} | all ret {m['all_ret']:.0f}% dd {m['all_dd']:.1f}% | "
              f"recorded ret {rows['recorded']['all_ret']:.0f}% | mid ret {rows['mid']['all_ret']:.0f}% | "
              f"2026 n {m['x26_n']} R {m['x26_avg_r']:+.3f}")
    pd.DataFrame(table).to_csv(os.path.join(RESULTS, "final_table.csv"), index=False)
    with open(os.path.join(RESULTS, "final_configs.json"), "w") as fh:
        json.dump(configs, fh, indent=1, sort_keys=True)
