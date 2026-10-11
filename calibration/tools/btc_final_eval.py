"""Final evaluation of named BTCSignalFlow configurations.
Usage: python -I btc_final_eval.py configs.json out_dir"""
import sys, os, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import btc_sweep as sw, rt_model as rt, btc_model as bm, btc_setfile

cfg_path, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
configs = json.load(open(cfg_path))
m1 = rt.load_m1(sw.DATA, sw.YEARS, "btcusd"); mkt = rt.Market(m1); bt = bm.BtcBacktester(mkt)
m1b = rt.load_m1(sw.DATA, [2026], "btcusd"); btb = bm.BtcBacktester(rt.Market(m1b))
YEARS = {str(y): (f"{y}-01-01", f"{y+1}-01-01") for y in range(2015, 2020)}
WINDOWS = dict(sw.DEFAULT_WINDOWS); WINDOWS.update(YEARS)


def run(b, sig, ea_over, a=None, c=None):
    ea = bm.ea_params(**ea_over)
    st, tr, eq = b.run(sig, ea, t_from=None if a is None else sw._epoch(a), t_to=None if c is None else sw._epoch(c))
    yrs = sw._years_between(a, c) if a else (b.mkt.m1["t"][-1] - b.mkt.m1["t"][0]) / 86400 / 365.25
    return bm.summarize(st, tr, eq, ea[bm.EA_IDX["start_balance"]], yrs), tr, eq


summary, years = [], []
fig, ax = plt.subplots(figsize=(11, 5.5))
for name, c in configs.items():
    sig = dict(bm.SIG_DEFAULTS); sig.update(c["sig"]); ea_over = dict(c.get("ea", {}))
    for w, (a, b) in WINDOWS.items():
        s, tr, eq = run(bt, sig, ea_over, a, b)
        row = dict(config=name, window=w); row.update(s); (years if w in YEARS else summary).append(row)
        if w == "all":
            cb = mkt.bars(sig["chart_tf"])
            tdf = pd.DataFrame(tr, columns=["entry_bar", "exit_bar", "side", "entry", "exit", "lots", "pnl", "reason", "R", "t_in", "t_out", "balance"])
            tdf["t_in"] = pd.to_datetime(tdf["t_in"], unit="s"); tdf["t_out"] = pd.to_datetime(tdf["t_out"], unit="s")
            tdf["reason"] = tdf["reason"].map({1: "signal", 2: "sl", 3: "tp", 5: "er", 6: "time", 8: "end"})
            tdf.to_csv(os.path.join(out_dir, f"trades_{name}.csv"), index=False)
            tb = m1["t"][cb["first"]]; start = int(np.searchsorted(tb, sw._epoch(a)))
            ax.plot(pd.to_datetime(tb[start:start + len(eq)], unit="s"), eq / 100.0, label=name, linewidth=1.1)
    for label, extra in [("costs_crypto", dict(commission_pct=0.05, swap_pct_day=-0.03)),
                         ("costs_heavy", dict(spread_add_pct=0.03, commission_pct=0.05, swap_pct_day=-0.06))]:
        e2 = dict(ea_over); e2.update(extra)
        s, _, _ = run(bt, sig, e2, *WINDOWS["all"]); row = dict(config=name, window=label); row.update(s); summary.append(row)
    s, _, _ = run(btb, sig, ea_over); row = dict(config=name, window="broker_2026_JulAug"); row.update(s); summary.append(row)
    btc_setfile.write_set(os.path.join(out_dir, f"BTCSignalFlow_EA_{name}.set"), sig, ea_over, comment=name)
    json.dump(dict(sig=sig, ea=ea_over), open(os.path.join(out_dir, f"config_{name}.json"), "w"), indent=1)
ax.axhline(100, color="gray", linewidth=0.6); ax.set_yscale("log")
ax.set_ylabel("equity (% of start, log)"); ax.set_title("BTCSignalFlow on BTCUSD 2015-2019 (Bitfinex 1m + broker spread), compounding")
ax.legend(fontsize=8); ax.grid(alpha=0.3, which="both"); fig.tight_layout(); fig.savefig(os.path.join(out_dir, "equity_curves.png"), dpi=130)
sdf = pd.DataFrame(summary); sdf.to_csv(os.path.join(out_dir, "summary.csv"), index=False)
ydf = pd.DataFrame(years); ydf.to_csv(os.path.join(out_dir, "per_year.csv"), index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
cols = ["config", "window", "trades", "ret_pct", "cagr_pct", "pf", "win_pct", "max_dd_pct", "avg_r", "sqn", "max_loss_streak", "exit_sl_pct"]
print(sdf[cols].round(2).to_string())
print(ydf.pivot(index="window", columns="config", values="ret_pct").round(1).to_string())
print(ydf.pivot(index="window", columns="config", values="trades").to_string())
print(ydf.pivot(index="window", columns="config", values="max_dd_pct").round(1).to_string())
