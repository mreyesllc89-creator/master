"""Walk-forward comparison of stop modes on v31_stageB.pkl.
Folds: test month = Jul, Aug, Sep, Oct; train = all earlier months (expanding, from Apr).
For each mode, pick the (signal set x exit) combo with the best TRAIN score, then record the
TEST month's trades. Concatenated test trades = honest out-of-sample estimate of each mode."""
import numpy as np, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
d = pd.read_pickle("v31_stageB.pkl")
N = np.stack(d.n.values); S1 = np.stack(d.s1.values); S2 = np.stack(d.s2.values)
MONTHS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]


def agg(idx_months, rows=slice(None)):
    n = N[rows][:, idx_months].sum(1); s1 = S1[rows][:, idx_months].sum(1); s2 = S2[rows][:, idx_months].sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = s1 / n; var = s2 / n - mean ** 2
        t = mean / np.sqrt(var / np.maximum(n - 1, 1))
    return n, mean, t


def walk_forward(mask, score="t", min_per_month=8):
    rows = np.where(mask)[0]; out = []
    for test in range(3, 7):
        tr = list(range(0, test))
        n, mean, t = agg(tr, rows)
        ok = n >= min_per_month * len(tr)
        if not ok.any(): continue
        sc = np.where(ok, t if score == "t" else mean, -np.inf)
        best = rows[np.nanargmax(sc)]
        out.append(dict(test=MONTHS[test], pick=best, train_n=int(N[best, tr].sum()), train_bp=S1[best, tr].sum() / N[best, tr].sum(),
                        test_n=int(N[best, test]), test_sum=S1[best, test], test_s2=S2[best, test]))
    o = pd.DataFrame(out)
    n = o.test_n.sum(); m = o.test_sum.sum() / n; sd = np.sqrt(o.test_s2.sum() / n - m * m)
    return o, n, m, m / (sd / np.sqrt(n - 1))


def describe(i):
    r = d.iloc[i]
    ex = {"ticks": f"SL {r.x:g} ticks", "atr": f"SL {r.x:g}xATR14({'chart' if r.atr_tf == 0 else str(r.atr_tf) + 'm'})",
          "pct": f"SL {r.x:g}%"}[r["mode"]]
    tr = f" trail {r.tr_act:g}R/{r.tr_off:g}R" if r.trail else ""
    return (f"{r.chart_tf}m chart | piv{r.divL} {r.divMin}-{r.divMax} day{r.dayH:02d} {r['div']} 4th={r.req4} lvl={r.levels} "
            f"tfs={r.tfs}{'(gated)' if r.fix else ''} | {ex} TP {r.rmult:g}R{tr}{'' if r.arm_on_fill else ' [v3.0 late-arm]'}")


if __name__ == "__main__":
    print(len(d), "combos;", d.groupby("mode").size().to_dict())
    allm = list(range(7)); n_all, m_all, t_all = agg(allm)
    d["all_n"] = n_all; d["all_bp"] = m_all; d["all_t"] = t_all
    n_is, m_is, _ = agg([0, 1, 2, 3, 4]); n_os, m_os, _ = agg([5, 6])
    d["is_n"] = n_is; d["is_bp"] = m_is; d["oos_n"] = n_os; d["oos_bp"] = m_os

    print("\n=== Share of combos profitable after fees (all months, >=100 trades) ===")
    q = d[d.all_n >= 100]
    print(q.groupby(["mode", "arm_on_fill"]).apply(lambda x: pd.Series(dict(
        combos=len(x), pct_profitable=100 * (x.all_bp > 0).mean(), median_bp=x.all_bp.median(), p90_bp=x.all_bp.quantile(.9),
        IS_OOS_spearman=x[["is_bp", "oos_bp"]].corr("spearman").iloc[0, 1]))).round(2))

    print("\n=== Walk-forward (expanding train, monthly test Jul..Oct) ===")
    res = []
    for mode in ["ticks", "atr", "pct"]:
        for arm in ([True, False] if mode == "ticks" else [True]):
            for score in ["t", "mean"]:
                mask = (d["mode"] == mode).values & (d.arm_on_fill == arm).values
                o, n, m, t = walk_forward(mask, score)
                res.append(dict(mode=mode, arm_on_fill=arm, select_by=score, oos_trades=n, oos_bp=m, oos_t=t,
                                months_positive=f"{(o.test_sum > 0).sum()}/{len(o)}"))
                if score == "t":
                    for _, r in o.iterrows():
                        print(f"  [{mode}{'' if arm else ' late-arm'}] {r.test}: train {r.train_n} tr {r.train_bp:+.1f}bp -> test {r.test_n} tr {r.test_sum / max(r.test_n, 1):+.1f}bp :: {describe(r.pick)}")
    print(pd.DataFrame(res).round(2).to_string())

    print("\n=== Default signal set: each stop mode's exit grid (all months) ===")
    A = pd.read_pickle("v31_stageA.pkl")
    for tf in (1, 5, 15):
        h = A[(A.chart_tf == tf) & (A.divL == 5) & (A.divMin == 5) & (A.dayH == 0) & (A["div"] == "RB") & (~A.req4) & (A.levels == "off") & (A.tfs == "all") & (~A.fix)].h.iloc[0]
        rep = A[A.h == h].drop(columns=["h", "nsig"]).iloc[0]
        key = ["chart_tf", "divL", "divR", "divMin", "divMax", "dayH", "div", "req4", "levels", "tfs", "fix"]
        sub = d.merge(A[A.h == h][key], on=key)
        if sub.empty: print(tf, "default not in stage B"); continue
        print(f"\n-- {tf}m chart defaults --")
        print(sub.groupby(["mode", "arm_on_fill"]).apply(lambda x: pd.Series(dict(
            trades=x.all_n.median(), median_bp=x.all_bp.median(), best_bp=x.all_bp.max(), best_IS_then_OOS=x.loc[x.is_bp.idxmax(), "oos_bp"]))).round(2))

    print("\n=== Parameter plateaus (median all-month bp across all signal sets, >=100 trades) ===")
    for mode, cols in [("atr", ["atr_tf", "x"]), ("pct", ["x"]), ("ticks", ["x"])]:
        x = q[(q["mode"] == mode) & q.arm_on_fill]
        print(f"\n{mode}:"); print(x.pivot_table(index=cols, columns="rmult", values="all_bp", aggfunc="median").round(2))
        print(" trail:", x.groupby(["tr_act"]).all_bp.median().round(2).to_dict())

    print("\n=== Top 15 by all-month t-stat (>=150 trades) ===")
    top = d[d.all_n >= 150].sort_values("all_t", ascending=False).head(15)
    for i, r in top.iterrows():
        print(f"  t={r.all_t:.2f} n={r.all_n} all {r.all_bp:+.1f}bp IS {r.is_bp:+.1f} OOS {r.oos_bp:+.1f} ({r.oos_n}) win {100 * r.win:.0f}% :: {describe(d.index.get_loc(i))}")
    d.drop(columns=["n", "s1", "s2"]).to_pickle("v31_summary.pkl")
