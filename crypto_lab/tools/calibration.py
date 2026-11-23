"""Calibration: does what a rule promised in-sample match what it delivered out-of-sample, and is the
out-of-sample result distinguishable from luck once every combination tried is counted?

usage: python -I calibration.py <data_dir> <out_dir> [tf ...]      (default tfs: 1h 4h)

Uses the same walk-forward as the Judge (6 m train / 3 m test, costs included). Three checks:
1. Win-rate calibration. Each window's forecast is the train win rate of the grid point it picked; the outcome
   is each out-of-sample trade (win = net pnl > 0). Reliability table, Brier score and Brier skill against a
   constant forecast.
2. Shrinkage. Train average R against test average R per window: how much of the in-sample edge survives.
3. Significance per combination. Mean out-of-sample R per trade with a 95 % interval and a one-sided p-value
   from a bootstrap over calendar months (trades inside a month move together), then a Holm correction over
   every combination in the run. `alive` = Holm-adjusted p < 0.05.
Writes calibration_windows.csv, calibration_combos.csv and calibration_<date>.md to <out_dir>.
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
import perpbt as bt
import strategies as st

SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
N_BOOT = 20000
BUCKETS = [0, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 1.0001]


def month_bootstrap(trades, rng, n_boot=N_BOOT):
    """Mean R per trade, resampling whole calendar months. Returns (lo, hi, one-sided p for mean <= 0)."""
    g = trades.groupby(trades.exit_time.dt.tz_convert(None).dt.to_period("M")).r
    s, n = g.sum().values, g.count().values
    if len(s) < 3:
        return np.nan, np.nan, np.nan
    pick = rng.integers(0, len(s), size=(n_boot, len(s)))
    means = s[pick].sum(axis=1) / n[pick].sum(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi), float((1 + (means <= 0).sum()) / (n_boot + 1))


def holm(p):
    """Holm step-down adjusted p-values (NaN stays NaN and does not count as a test)."""
    p = np.asarray(p, float); out = np.full(len(p), np.nan)
    ok = np.where(~np.isnan(p))[0]
    order = ok[np.argsort(p[ok])]
    m = len(order); run = 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (m - k) * p[i])); out[i] = run
    return out


def jobs_for(sym, funding, btc, metrics):
    jobs = [(n, f, g, None) for n, (f, g) in st.LIBRARY.items()]
    jobs += [(n, f, g, funding) for n, (f, g) in st.LIBRARY_WITH_FUNDING.items()]
    if sym != "BTCUSDT":
        jobs += [(n, f, g, btc) for n, (f, g) in st.LIBRARY_WITH_BTC.items()]
    if metrics is not None:
        jobs += [(n, f, g, metrics) for n, (f, g) in st.LIBRARY_WITH_METRICS.items()]
    return jobs


def collect(data, tfs):
    """Run the walk-forward for every combination. Returns (window rows, OOS trades with a `forecast` column)."""
    wins, trades = [], []
    for tf in tfs:
        btc = bt.load(data, "BTCUSDT", tf)
        for sym in SYMS:
            df = bt.load(data, sym, tf); funding = bt.load_funding(data, sym)
            mp = f"{data}/{sym}_metrics.parquet"
            metrics = pd.read_parquet(mp) if os.path.exists(mp) else None
            for name, fn, grid, extra in jobs_for(sym, funding, btc, metrics):
                strat = (lambda d, fn=fn, extra=extra, **p: fn(d, extra, **p)) if extra is not None else fn
                try:
                    oos, picks = bt.walk_forward(df, funding, sym, strat, grid)
                except Exception as e:  # report, never guess
                    print(f"FAILED {name} {sym} {tf}: {type(e).__name__}: {e}", flush=True)
                    wins.append(dict(strategy=name, symbol=sym, tf=tf, error=f"{type(e).__name__}: {e}"))
                    continue
                key = dict(strategy=name, symbol=sym, tf=tf)
                for p in picks:
                    t = oos[(oos.entry_time >= p["test_start"]) & (oos.entry_time < p["test_end"])] if len(oos) else oos
                    wins.append(dict(**key, test_start=str(p["test_start"].date()), grid_size=p["grid_size"],
                                     train_n=p["train_n"], train_win=p["train_win"], train_avg_r=p["train_avg_r"],
                                     test_n=len(t), test_win=float((t.pnl > 0).mean()) if len(t) else np.nan,
                                     test_avg_r=float(np.nanmean(t.r)) if len(t) else np.nan))
                    if len(t):
                        trades.append(t.assign(**key, forecast=p["train_win"]))
                print(f"{name} {sym} {tf}: {len(picks)} windows, {len(oos)} OOS trades", flush=True)
    return pd.DataFrame(wins), (pd.concat(trades, ignore_index=True) if trades else pd.DataFrame())


def reliability(tr):
    tr = tr.assign(won=(tr.pnl > 0).astype(float), bucket=pd.cut(tr.forecast, BUCKETS, right=False))
    g = tr.groupby("bucket", observed=True)
    tab = pd.DataFrame(dict(trades=g.size(), predicted=g.forecast.mean(), realised=g.won.mean()))
    tab["gap"] = tab.realised - tab.predicted
    brier = float(((tr.forecast - tr.won) ** 2).mean())
    base = float(tr.won.mean())
    ref = float(((base - tr.won) ** 2).mean())
    return tab, dict(trades=len(tr), predicted=float(tr.forecast.mean()), realised=base, brier=brier, brier_ref=ref,
                     skill=1 - brier / ref if ref else np.nan)


def shrinkage(w):
    w = w[w.test_n >= 10]
    if len(w) < 3:
        return dict(windows=len(w))
    slope = float(np.polyfit(w.train_avg_r, w.test_avg_r, 1)[0])
    return dict(windows=len(w), train_avg_r=float(w.train_avg_r.mean()), test_avg_r=float(w.test_avg_r.mean()),
                slope=slope, corr=float(np.corrcoef(w.train_avg_r, w.test_avg_r)[0, 1]),
                test_positive=float((w.test_avg_r > 0).mean()))


def combos(tr, rng):
    rows = []
    for (s, y, tf), t in tr.groupby(["strategy", "symbol", "tf"]):
        lo, hi, p = month_bootstrap(t, rng) if len(t) >= 50 else (np.nan, np.nan, np.nan)
        rows.append(dict(strategy=s, symbol=y, tf=tf, trades=len(t), predicted_win=float(t.forecast.mean()),
                         realised_win=float((t.pnl > 0).mean()), avg_r=float(np.nanmean(t.r)), ci_lo=lo, ci_hi=hi, p=p))
    c = pd.DataFrame(rows)
    c["p_holm"] = holm(c.p.values)
    c["alive"] = c.p_holm < 0.05
    return c.sort_values(["p", "avg_r"], ascending=[True, False], na_position="last")


def pct(x):
    return "n/a" if pd.isna(x) else f"{100 * x:.1f} %"


def report(w, tr, c, tfs, date):
    L = [f"# Calibration — {date}", "",
         f"Walk-forward as in the Judge (6 m train / 3 m test, fees + funding + slippage). Timeframes: {', '.join(tfs)}. "
         f"{c.shape[0]} combinations, {len(w.dropna(subset=['train_n']))} windows, {len(tr)} out-of-sample trades. "
         "Every number below is computed by `tools/calibration.py`; none is an estimate.", ""]
    if "error" in w and w.error.notna().any():
        L += ["**Combinations that could not be run:**", ""] + [f"- {r.strategy} {r.symbol} {r.tf}: {r.error}" for r in w[w.error.notna()].itertuples()] + [""]
    L += ["## 1. Win rate: promised in-sample vs delivered out-of-sample", "",
          "| Timeframe | OOS trades | Predicted win | Realised win | Brier | Brier of a constant forecast | Skill |", "|---|---|---|---|---|---|---|"]
    for tf in tfs + ["all"]:
        t = tr if tf == "all" else tr[tr.tf == tf]
        if len(t):
            _, s = reliability(t)
            L.append(f"| {tf} | {s['trades']} | {pct(s['predicted'])} | {pct(s['realised'])} | {s['brier']:.4f} | {s['brier_ref']:.4f} | {s['skill']:+.3f} |")
    tab, _ = reliability(tr)
    L += ["", "Skill below zero means the train win rate predicts a trade's outcome worse than one constant number would.", "",
          "| Predicted win rate | OOS trades | Mean predicted | Realised | Gap |", "|---|---|---|---|---|"]
    L += [f"| {b.left:.2f}–{min(b.right, 1):.2f} | {int(r.trades)} | {pct(r.predicted)} | {pct(r.realised)} | {100 * r.gap:+.1f} pts |" for b, r in tab.iterrows()]
    L += ["", "## 2. Shrinkage of the edge (average R per trade, windows with >= 10 test trades)", "",
          "| Timeframe | Windows | Train avg R | Test avg R | Slope test~train | Correlation | Windows positive in test |", "|---|---|---|---|---|---|---|"]
    for tf in tfs + ["all"]:
        s = shrinkage(w if tf == "all" else w[w.tf == tf])
        if "slope" in s:
            L.append(f"| {tf} | {s['windows']} | {s['train_avg_r']:+.3f} | {s['test_avg_r']:+.3f} | {s['slope']:+.2f} | {s['corr']:+.2f} | {pct(s['test_positive'])} |")
    L += ["", "A slope of 1 would mean the in-sample edge carries over in full; 0 means it carries no information.", "",
          "## 3. Is any out-of-sample result distinguishable from luck?", "",
          f"Mean R per trade, 95 % interval and one-sided p from a bootstrap over calendar months ({N_BOOT} resamples); "
          f"Holm correction over the {int(c.p.notna().sum())} combinations with >= 50 OOS trades.", "",
          "| Strategy | Symbol | TF | OOS trades | Predicted win | Realised win | Avg R | 95 % interval | p | p (Holm) | Alive |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in c.itertuples():
        ci = "n/a (< 50 trades)" if pd.isna(r.p) else f"{r.ci_lo:+.3f} to {r.ci_hi:+.3f}"
        L.append(f"| {r.strategy} | {r.symbol} | {r.tf} | {r.trades} | {pct(r.predicted_win)} | {pct(r.realised_win)} | {r.avg_r:+.3f} | {ci} | "
                 f"{'n/a' if pd.isna(r.p) else f'{r.p:.4f}'} | {'n/a' if pd.isna(r.p_holm) else f'{r.p_holm:.4f}'} | {'YES' if r.alive else 'no'} |")
    n_alive = int(c.alive.sum())
    L += ["", f"**Result: {n_alive} of {len(c)} combinations survive the correction.**", ""]
    return "\n".join(L)


def main():
    data, out = sys.argv[1], sys.argv[2]; tfs = sys.argv[3:] or ["1h", "4h"]
    os.makedirs(out, exist_ok=True)
    w, tr = collect(data, tfs)
    c = combos(tr, np.random.default_rng(20261123))
    w.to_csv(os.path.join(out, "calibration_windows.csv"), index=False)
    c.to_csv(os.path.join(out, "calibration_combos.csv"), index=False)
    date = datetime.date.today().isoformat()
    md = report(w, tr, c, tfs, date)
    with open(os.path.join(out, f"calibration_{date}.md"), "w") as fh:
        fh.write(md)
    print(md)


if __name__ == "__main__":
    main()
