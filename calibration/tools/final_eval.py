"""Final evaluation of named configurations: full-period, IS, OOS, per-year
walk-forward table, cost sensitivity, equity-curve chart, trade lists and
MT5 .set files.  Usage: python -I final_eval.py configs.json out_dir"""
import sys, os, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sweep, rt_model as rt, setfile

cfg_path, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
configs = json.load(open(cfg_path))
m1 = rt.load_m1(sweep.DATA, sweep.YEARS)
mkt = rt.Market(m1)
bt = rt.Backtester(mkt)
m1_2026 = rt.load_m1(sweep.DATA, [2026]) if os.path.exists(os.path.join(sweep.DATA, "xauusd_m1_2026.npz")) else None
bt_2026 = rt.Backtester(rt.Market(m1_2026)) if m1_2026 is not None else None

YEAR_WINDOWS = {str(y): (f"{y}-01-01", f"{y+1}-01-01") for y in range(2011, 2019)}
WINDOWS = dict(sweep.DEFAULT_WINDOWS)
WINDOWS.update(YEAR_WINDOWS)


def run(ind, ea_over, a, b):
    ea = rt.ea_params(**ea_over)
    st, tr, eq = bt.run(ind, ea, t_from=sweep._epoch(a), t_to=sweep._epoch(b))
    s = rt.summarize(st, tr, eq, ea[rt.EA_IDX["start_balance"]], sweep._years_between(a, b))
    return s, tr, eq


summary_rows = []
year_rows = []
fig, ax = plt.subplots(figsize=(11, 5.5))
for name, c in configs.items():
    ind = dict(rt.IND_DEFAULTS); ind.update(c["ind"])
    ea_over = dict(c.get("ea", {}))
    for w, (a, b) in WINDOWS.items():
        s, tr, eq = run(ind, ea_over, a, b)
        row = dict(config=name, window=w); row.update(s)
        (year_rows if w in YEAR_WINDOWS else summary_rows).append(row)
        if w == "all":
            cb = mkt.bars(ind["chart_tf"])
            tdf = pd.DataFrame(tr, columns=["entry_bar", "exit_bar", "side", "entry", "exit", "lots", "pnl", "reason", "R", "t_in", "t_out", "balance"])
            tdf["t_in"] = pd.to_datetime(tdf["t_in"], unit="s"); tdf["t_out"] = pd.to_datetime(tdf["t_out"], unit="s")
            tdf["reason"] = tdf["reason"].map({1: "signal", 2: "sl", 3: "tp", 4: "st_flip", 5: "er", 6: "time", 7: "friday", 8: "end"})
            tdf.to_csv(os.path.join(out_dir, f"trades_{name}.csv"), index=False)
            # equity curve on chart-bar closes (UTC)
            tb = m1["t"][cb["first"]]
            start = int(np.searchsorted(tb, sweep._epoch(a)))
            times = pd.to_datetime(tb[start:start + len(eq)], unit="s")
            ax.plot(times, eq / 10000.0 * 100.0, label=name, linewidth=1.1)
    # cost sensitivity on the full window
    for label, extra in [("costs_xm_spread+10pts_swap-8", dict(spread_add_pts=10, swap_usd_lot_night=-8.0)),
                         ("costs_heavy_spread+20pts_swap-15", dict(spread_add_pts=20, swap_usd_lot_night=-15.0))]:
        e2 = dict(ea_over); e2.update(extra)
        s, _, _ = run(ind, e2, *WINDOWS["all"])
        row = dict(config=name, window=label); row.update(s); summary_rows.append(row)
    # broker tick data July-August 2026 (XAUUSD-ECNc), a separate recent sanity window
    if m1_2026 is not None:
        ea = rt.ea_params(**ea_over)
        st, tr, eq = bt_2026.run(ind, ea)
        s = rt.summarize(st, tr, eq, ea[rt.EA_IDX["start_balance"]], (m1_2026["t"][-1] - m1_2026["t"][0]) / 86400 / 365.25)
        row = dict(config=name, window="broker_2026_JulAug"); row.update(s); summary_rows.append(row)
    setfile.write_set(os.path.join(out_dir, f"RegimeTrend_EA_{name}.set"), ind, ea_over, comment=name)
    json.dump(dict(ind=ind, ea=ea_over), open(os.path.join(out_dir, f"config_{name}.json"), "w"), indent=1)

ax.axhline(100, color="gray", linewidth=0.6)
ax.set_ylabel("equity (% of start)"); ax.set_title("RegimeTrend_EA on XAUUSD 2011-2018, 1% risk per trade, compounding")
ax.legend(fontsize=8); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(out_dir, "equity_curves.png"), dpi=130)

sdf = pd.DataFrame(summary_rows); sdf.to_csv(os.path.join(out_dir, "summary.csv"), index=False)
ydf = pd.DataFrame(year_rows); ydf.to_csv(os.path.join(out_dir, "per_year.csv"), index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
cols = ["config", "window", "trades", "ret_pct", "cagr_pct", "pf", "win_pct", "max_dd_pct", "avg_r", "sqn", "max_loss_streak", "exit_sl_pct"]
print(sdf[cols].round(2).to_string())
print()
piv = ydf.pivot(index="window", columns="config", values="ret_pct").round(1)
print("per-year return % (compounding restarts each year):")
print(piv.to_string())
piv2 = ydf.pivot(index="window", columns="config", values="trades")
print("per-year trades:"); print(piv2.to_string())
