"""Judge: run every library strategy through the gauntlet on every symbol / timeframe, write cards.

usage: python -I judge.py <data_dir> <out_dir> [tf]
Gauntlet per (strategy, symbol, tf): in-sample grid summary, walk-forward OOS (6 m train / 3 m test),
regime table by quarter, cost stress (double fees + 3 ticks slippage), score 1-5 x 5 criteria.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
import perpbt as bt
import strategies as st

SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def score(s, wf, regimes):
    if s.get("trades", 0) < 50:
        return dict(total=0, note="fewer than 50 OOS trades")
    sc = {}
    sc["profit"] = 5 if s["ret_pct"] > 30 else 4 if s["ret_pct"] > 15 else 3 if s["ret_pct"] > 5 else 2 if s["ret_pct"] > 0 else 1
    sc["drawdown"] = 5 if s["maxdd_pct"] < 5 else 4 if s["maxdd_pct"] < 10 else 3 if s["maxdd_pct"] < 15 else 2 if s["maxdd_pct"] < 25 else 1
    sc["trades"] = 5 if s["trades"] > 400 else 4 if s["trades"] > 200 else 3 if s["trades"] > 100 else 2
    sc["streak"] = 5 if s["losing_streak"] <= 5 else 4 if s["losing_streak"] <= 8 else 3 if s["losing_streak"] <= 12 else 2 if s["losing_streak"] <= 18 else 1
    pos_q = (regimes.net_r > 0).mean() if len(regimes) else 0
    sc["regimes"] = 5 if pos_q >= 0.8 else 4 if pos_q >= 0.65 else 3 if pos_q >= 0.5 else 2 if pos_q >= 0.35 else 1
    sc["total"] = sum(sc.values())
    return sc


def gauntlet(name, fn, grid, df, funding, sym, extra, out_dir, tf):
    strat = (lambda d, **p: fn(d, extra, **p)) if extra is not None else fn
    oos, picks = bt.walk_forward(df, funding, sym, strat, grid)
    if len(oos) == 0:
        return None
    eq = (10000 + oos.pnl.cumsum()); eq.index = oos.exit_time
    s = bt.summarize(oos, eq)
    reg = bt.regime_table(oos)
    # cost stress: re-run the OOS picks with double fees and 3 ticks
    stressed = []
    for p in picks:
        d = df[p["train_start"]:p["test_end"]]
        t, _ = bt.run(d, strat(d, **p["params"]), funding, sym, fee_pct=0.10, slip_ticks=3)
        stressed.append(t[t.entry_time >= p["test_start"]])
    st_tr = pd.concat(stressed) if stressed else pd.DataFrame()
    st_s = bt.summarize(st_tr, 10000 + st_tr.pnl.cumsum().set_axis(st_tr.exit_time)) if len(st_tr) else dict(trades=0)
    sc = score(s, picks, reg)
    worst_month = oos.groupby(oos.exit_time.dt.tz_convert(None).dt.to_period("M")).pnl.sum()
    card = {
        "strategy": name, "symbol": sym, "tf": tf, "mechanism": fn.__doc__.strip().split("\n")[0],
        "oos": s, "stressed": st_s, "score": sc, "windows": [dict(test_start=str(p["test_start"].date()), params=p["params"], n=p["n"]) for p in picks],
        "worst_month": dict(month=str(worst_month.idxmin()), pnl=round(float(worst_month.min()), 2)) if len(worst_month) else None,
        "regimes": reg.reset_index().astype(str).to_dict("records"),
    }
    with open(os.path.join(out_dir, f"card_{name}_{sym}_{tf}.json"), "w") as fh:
        json.dump(card, fh, indent=1, default=str)
    return card


def main():
    data, out = sys.argv[1], sys.argv[2]; tf = sys.argv[3] if len(sys.argv) > 3 else "1h"
    os.makedirs(out, exist_ok=True)
    rows = []
    btc = bt.load(data, "BTCUSDT", tf)
    for sym in SYMS:
        df = bt.load(data, sym, tf); funding = bt.load_funding(data, sym)
        metrics = pd.read_parquet(f"{data}/{sym}_metrics.parquet") if os.path.exists(f"{data}/{sym}_metrics.parquet") else None
        jobs = [(n, f, g, None) for n, (f, g) in st.LIBRARY.items()]
        jobs += [(n, f, g, funding) for n, (f, g) in st.LIBRARY_WITH_FUNDING.items()]
        if sym != "BTCUSDT":
            jobs += [(n, f, g, btc) for n, (f, g) in st.LIBRARY_WITH_BTC.items()]
        if metrics is not None:
            jobs += [(n, f, g, metrics) for n, (f, g) in st.LIBRARY_WITH_METRICS.items()]
        for name, fn, grid, extra in jobs:
            c = gauntlet(name, fn, grid, df, funding, sym, extra, out, tf)
            if c:
                rows.append(dict(strategy=name, symbol=sym, tf=tf, **{k: c["oos"].get(k) for k in ("trades", "ret_pct", "pf", "maxdd_pct", "losing_streak", "avg_r")},
                                 stressed_ret=c["stressed"].get("ret_pct"), total=c["score"].get("total")))
                print(rows[-1], flush=True)
    lb = pd.DataFrame(rows).sort_values("total", ascending=False)
    lb.to_csv(os.path.join(out, f"leaderboard_{tf}.csv"), index=False)
    print(lb.to_string())


if __name__ == "__main__":
    main()
