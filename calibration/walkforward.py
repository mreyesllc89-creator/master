"""Walk-forward check for the gold sweep: pick on the first half of each export, score on the second half.

Three candidates per timeframe, all latch arming, pivot levels, gold_raw costs, fixed 1 oz:
  shipped   the XAUUSD build defaults (ATR 1.5 / 2.5R / BarsN 3 / buffer 1.0 / tick trail)
  plateau   recommend()'s plateau pick on the FIRST half only
  best      the single cell with the highest first-half net (what naive optimisation would ship)
Each is then run on the SECOND half, which it never saw.
"""
import itertools, os, sys, dataclasses
import numpy as np, pandas as pd
import xpw_backtest as xb

TFS = ["xau10", "xau15", "xau30", "xau60", "xau240"]
SHIPPED = dict(sl_mode="atr", sl_value=1.5, tp_r=2.5, barsn=3, buf_atr=1.0, trail="tick")


def half(d: xb.TFData, which: str) -> xb.TFData:
    n = len(d.close); m = n // 2
    sl = slice(0, m) if which == "first" else slice(m, n)
    h = dataclasses.replace(d, time=d.time[sl], hour=d.hour[sl], open=d.open[sl], high=d.high[sl], low=d.low[sl], close=d.close[sl],
                            csv_swingH=d.csv_swingH[sl], csv_swingL=d.csv_swingL[sl], csv_trail=d.csv_trail[sl], atr=d.atr[sl], piv={})
    return h


def run(d, **kw):
    cfg = xb.Config(tf="x", cost_preset="gold_raw", sizing="fixed", fixed_qty=1.0, arm_mode="latch", levels="pivot", **kw).apply_preset()
    trades, _, _ = xb.run_backtest(d, cfg, want_trades=False)
    return xb.metrics(trades)


def grid(d):
    rows = []
    for (slm, slv), tpr, bn, buf, tr in itertools.product(xb.GRID["sl"], xb.GRID["tp_r"], xb.GRID["barsn"], xb.GRID["buf_atr"], xb.GRID["trail"]):
        m = run(d, sl_mode=slm, sl_value=slv, tp_r=tpr, barsn=bn, buf_atr=buf, trail=tr)
        rows.append(dict(tf="x", sl_mode=slm, sl_value=slv, tp_r=tpr, barsN=bn, buf_atr=buf, trail=tr, cost_preset="gold_raw",
                         arm_mode="latch", levels="pivot", **m))
    return pd.DataFrame(rows)


def fmt(m):
    return f"{m['n_trades']:>3} trades, net {m['net_pnl']:+7.1f}, PF {m['profit_factor_net']:.2f}, expR {m['expectancy_R']:+.2f}, DD {m['max_drawdown_net']:.0f}"


def main():
    out = ["# Gold walk-forward (first half picks, second half scores)", "",
           "Latch arming, pivot levels, gold_raw costs, fixed 1 oz. Net per ounce; multiply by 100 for one lot.", ""]
    summary = []
    for tf in TFS:
        d = xb.load_tf(tf, assert_pivots=False)
        a, b = half(d, "first"), half(d, "second")
        df = grid(a)
        rec = xb.recommend({"x": df}, presets=("gold_raw",))["x"]["gold_raw"]
        pick = rec.get("pick")
        best = df.sort_values("net_pnl", ascending=False).iloc[0]
        cands = {"shipped": SHIPPED}
        if pick:
            cands["plateau"] = dict(sl_mode=pick["sl_mode"], sl_value=pick["sl_value"], tp_r=pick["tp_r"], barsn=int(pick["barsN"]), buf_atr=pick["buf_atr"], trail=pick["trail"])
        cands["best"] = dict(sl_mode=best.sl_mode, sl_value=best.sl_value, tp_r=best.tp_r, barsn=int(best.barsN), buf_atr=best.buf_atr, trail=best.trail)
        out.append(f"## {tf}: {len(a.close)} bars in-sample ({a.time[0][:10]} to {a.time[-1][:10]}), {len(b.close)} bars out-of-sample ({b.time[0][:10]} to {b.time[-1][:10]})")
        out.append(""); out.append("| candidate | settings | in-sample | out-of-sample |"); out.append("|---|---|---|---|")
        for name, kw in cands.items():
            mi, mo = run(a, **kw), run(b, **kw)
            sett = f"{kw['sl_mode']} {kw['sl_value']} / {kw['tp_r']}R / BarsN {kw['barsn']} / buf {kw['buf_atr']} / {kw['trail']}"
            out.append(f"| {name} | {sett} | {fmt(mi)} | {fmt(mo)} |")
            summary.append(dict(tf=tf, candidate=name, in_net=mi["net_pnl"], out_net=mo["net_pnl"], out_trades=mo["n_trades"], out_pf=mo["profit_factor_net"]))
        # how much of the out-of-sample grid is positive at all
        dfo = grid(b)
        meas = dfo[(dfo.same_bar_exit_share <= 0.5) & (dfo.n_trades >= 8)]
        out.append(""); out.append(f"Out-of-sample grid: {(meas.net_pnl > 0).mean()*100:.0f}% of {len(meas)} measurable cells positive, median net {meas.net_pnl.median():+.0f}.")
        out.append("")
    s = pd.DataFrame(summary)
    out.append("## Summary (out-of-sample net per oz)"); out.append("")
    out.append(s.pivot(index="tf", columns="candidate", values="out_net").round(0).reindex(TFS).to_markdown())
    out.append(""); out.append("Positive out of sample: " + ", ".join(f"{c} {int((s[s.candidate==c].out_net>0).sum())}/{len(TFS)}" for c in ["shipped", "plateau", "best"]))
    txt = "\n".join(out)
    os.makedirs(os.path.join(xb.RESULTS_DIR, "xau"), exist_ok=True)
    open(os.path.join(xb.RESULTS_DIR, "xau", "walkforward.md"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
