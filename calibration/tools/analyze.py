"""Turn the sweep CSVs into the tables used in the calibration report."""
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sweep

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
D = sweep.DATA
IND_COLS = ["chart_tf", "er_period", "enter", "exit", "atr_period", "atr_mult", "min_dwell", "shock_mult"]
MIN_IS = {"M5": 120, "M15": 90, "M30": 70, "H1": 50}


def md(df, floatfmt=2):
    return df.round(floatfmt).to_markdown(index=False)


def stage1_tables():
    df = pd.read_csv(os.path.join(D, "stage1_indicator_grid.csv"))
    out = []
    out.append(f"Stage 1: {len(df)} indicator combinations (EA inputs at defaults).\n")
    # overall picture per TF
    g = df.groupby("chart_tf").agg(configs=("is_net", "size"),
                                   is_profitable_pct=("is_net", lambda s: (s > 0).mean() * 100),
                                   oos_profitable_pct=("oos_net", lambda s: (s > 0).mean() * 100),
                                   median_is_ret=("is_ret_pct", "median"), median_is_dd=("is_max_dd_pct", "median"),
                                   best_is_sqn=("is_sqn", "max")).reset_index()
    out.append("Share of combinations that made money, per chart timeframe:\n")
    out.append(md(g, 1) + "\n")
    # main effects: mean IS SQN per level of each input
    out.append("Main effects (mean in-sample SQN per input level, all TFs pooled):\n")
    for c in IND_COLS:
        e = df.groupby(c)["is_sqn"].mean().round(2)
        out.append(f"- {c}: " + ", ".join(f"{k}: {v}" for k, v in e.items()))
    out.append("")
    cols = IND_COLS + ["is_trades", "is_ret_pct", "is_pf", "is_max_dd_pct", "is_sqn", "oos_trades", "oos_ret_pct", "oos_pf", "oos_sqn"]
    tops = []
    for tf, g in df.groupby("chart_tf"):
        g = g[g["is_trades"] >= MIN_IS[tf]].sort_values("is_sqn", ascending=False).head(5)
        tops.append(g[cols])
    out.append("Top 5 per chart timeframe by in-sample SQN (min trade count applied):\n")
    out.append(md(pd.concat(tops)) + "\n")
    sel = df[df["is_trades"] >= 50]
    out.append(f"Correlation between in-sample and out-of-sample SQN across combinations: {sel.is_sqn.corr(sel.oos_sqn):.2f} (n={len(sel)})\n")
    return "\n".join(out)


def stage2_tables():
    df = pd.read_csv(os.path.join(D, "stage2_ea_variants.csv"))
    key = IND_COLS
    base = df[df.variant == "baseline"].set_index(key)
    rows = []
    for v, g in df.groupby("variant"):
        if v == "baseline":
            continue
        g = g.set_index(key)
        b = base.loc[g.index]
        d_is = (g["is_sqn"].values - b["is_sqn"].values)
        d_oos = (g["oos_sqn"].values - b["oos_sqn"].values)
        d_ret = (g["is_ret_pct"].values - b["is_ret_pct"].values)
        d_dd = (g["is_max_dd_pct"].values - b["is_max_dd_pct"].values)
        # describe the variant by its non-default EA columns
        ea_cols = [c for c in g.columns if c.startswith("ea_") and g[c].notna().any()]
        desc = ", ".join(f"{c[3:]}={g[c].iloc[0]:g}" for c in ea_cols)
        if "trail_atr_mult" in g.columns and g["trail_atr_mult"].iloc[0] > 0:
            desc += f", trail_atr_mult={g['trail_atr_mult'].iloc[0]:g}"
        rows.append(dict(variant=v, setting=desc, n=len(g), mean_dIS_sqn=d_is.mean(), share_better_IS=(d_is > 0).mean() * 100,
                         mean_dOOS_sqn=d_oos.mean(), share_better_OOS=(d_oos > 0).mean() * 100,
                         mean_dIS_ret=d_ret.mean(), mean_dIS_dd=d_dd.mean()))
    t = pd.DataFrame(rows).sort_values("mean_dIS_sqn", ascending=False)
    return t


def stage3_tables(top=15):
    df = pd.read_csv(os.path.join(D, "stage3_random_joint.csv"))
    out = [f"Stage 3: {len(df)} random joint samples of indicator + EA inputs.\n"]
    g = df.groupby("chart_tf").agg(samples=("is_net", "size"), is_profitable_pct=("is_net", lambda s: (s > 0).mean() * 100),
                                   oos_profitable_pct=("oos_net", lambda s: (s > 0).mean() * 100)).reset_index()
    out.append(md(g, 1) + "\n")
    return "\n".join(out), df


if __name__ == "__main__":
    print(stage1_tables())
