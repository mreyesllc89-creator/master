"""Report figures (static PNG, light surface). usage: python -I charts.py <results_dir>

Colour follows the entity in every figure: blue = the shipped reference preset, orange = the calibrated
preset, aqua = the real account, yellow = the market-entry set found without an order delay, magenta = the
shipped preset with the market route opened. Reference
levels (break-even, cost) are drawn in ink, not in a series colour. Thin marks, 2 px lines, hairline
grid, text in ink colours, a legend only when there are two or more series, never two y scales.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.labelcolor": INK2, "ytick.labelcolor": INK2, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "axes.grid": False, "legend.frameon": False,
})


def _mix(c0, c1, q):
    a = np.array([int(c0[i:i + 2], 16) for i in (1, 3, 5)], float)
    b = np.array([int(c1[i:i + 2], 16) for i in (1, 3, 5)], float)
    v = a + (b - a) * q
    return "#%02x%02x%02x" % tuple(int(round(x)) for x in v)


BLUE_TINT, ORANGE_TINT = "#b7d3f6", _mix(SURFACE, ORANGE, 0.4)


def frame(ax, grid="y"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_visible(grid != "y")
    ax.spines["bottom"].set_visible(grid != "x")
    ax.grid(axis=grid, color=GRID, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def title(ax, text, sub=None):
    ax.set_title(text, loc="left", fontsize=12.5, fontweight="bold", color=INK, pad=24 if sub else 10)
    if sub:
        ax.text(0, 1.035, sub, transform=ax.transAxes, fontsize=9.5, color=INK2, va="bottom")


def line(ax, x, y, color, label=None):
    ax.plot(x, y, color=color, linewidth=2, marker="o", markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5, label=label, zorder=4)


def fig_monthly(res, out):
    m = pd.read_csv(os.path.join(res, "baseline_by_month.csv"))
    m = m[(m.preset == "FlashGold_NativeReference") & (m.case == "real fills") & (m.month != "ALL")]
    fig, ax = plt.subplots(figsize=(8.2, 3.9), dpi=160)
    x = np.arange(len(m))
    ax.set_xlim(-0.6, len(m) - 0.4)
    ax.set_ylim(0, max(1.15, float(m.pf.max()) + 0.12))
    frame(ax)
    for i, v in zip(x, m.pf):
        ax.bar(i, v, width=0.34, color=BLUE, linewidth=0, zorder=3)
        ax.text(i, v + 0.025, f"{v:.2f}", ha="center", va="bottom", fontsize=9, color=INK2)
    ax.axhline(1.0, color=INK2, linewidth=1.0, zorder=2)
    ax.text(len(m) - 0.45, 1.02, "break-even (1.00)", ha="right", va="bottom", fontsize=9, color=INK2)
    ax.set_xticks(x)
    ax.set_xticklabels(m.month, fontsize=9)
    ax.set_ylabel("profit factor")
    head = ("The shipped reference preset loses in every month replayed" if m.pf.max() < 1
            else f"The shipped reference preset loses in {int((m.pf < 1).sum())} of {len(m)} months replayed")
    title(ax, head, f"Profit factor per month, tick replay with fills calibrated to the real account ({int(m.n.sum()):,} trades in total)")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_edge(res, out):
    d = pd.read_csv(os.path.join(res, "forward_drift.csv"))
    d = d[d.h_s <= 300]
    fig, ax = plt.subplots(figsize=(8.2, 4.0), dpi=160)
    frame(ax)
    ax.set_xscale("log")
    cost = float(d.cost.iloc[0])
    line(ax, d.h_s, d.mid_drift_FLXQ, BLUE)
    ax.axhline(cost, color=INK2, linewidth=1.0, zorder=3)
    ax.axhline(0, color=AXIS, linewidth=0.8, zorder=2)
    ax.text(d.h_s.iloc[-1], cost + 1.2, f"what a round trip costs in spread and slippage: about {cost:.0f} points", ha="right", va="bottom", fontsize=9, color=INK2)
    k = int(d.mid_drift_FLXQ.idxmax())
    ax.text(d.h_s.loc[k], d.mid_drift_FLXQ.loc[k] + 1.6, f"best case +{d.mid_drift_FLXQ.loc[k]:.0f} points", ha="center", va="bottom", fontsize=9, color=INK2)
    ax.text(d.h_s.iloc[0], d.mid_drift_FLXQ.iloc[0] + 5.0, "price move in the trade's favour", ha="left", va="bottom", fontsize=9, color=INK2)
    ax.set_xticks([1, 2, 5, 10, 20, 30, 60, 120, 300])
    ax.set_xticklabels(["1 s", "2 s", "5 s", "10 s", "20 s", "30 s", "1 min", "2 min", "5 min"])
    ax.minorticks_off()
    ax.set_ylim(min(-8, d.mid_drift_FLXQ.min() - 4), cost + 8)
    ax.set_xlabel("time after the fill")
    ax.set_ylabel("points (1 point = $0.01)")
    title(ax, "After a fill the market keeps moving the trade's way by only a few points",
          f"Average mid-price move after entry against the average cost of a trade, {int(d.n_FLXQ.iloc[0]):,} replayed momentum entries")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def _ranges(res, name, min_trades, color, tint, dot_label, head, sub, out):
    o = pd.read_csv(os.path.join(res, name))
    base = o[o.is_base].pf.iloc[0]
    o = o[(o.n >= min_trades) & ~o.input.str.startswith("X_")]
    g = o.groupby("input").pf.agg(["min", "max"])
    g["span"] = g["max"] - g["min"]
    g = g.sort_values("span", ascending=False).head(16).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.2, 5.6), dpi=160)
    frame(ax, grid="x")
    y = np.arange(len(g))
    for i, (_, r) in zip(y, g.iterrows()):
        ax.plot([r["min"], r["max"]], [i, i], color=tint, linewidth=6, solid_capstyle="round", zorder=3)
    ax.scatter(np.full(len(g), base), y, s=46, color=color, edgecolor=SURFACE, linewidth=1.5, zorder=5)
    lo, hi = min(float(g["min"].min()), 1.0), max(float(g["max"].max()), 1.0)
    pad = 0.06 * (hi - lo)
    ax.axvline(1.0, color=INK2, linewidth=1.0, zorder=2)
    ax.text(1.0 - 0.012 * (hi - lo), len(g) - 0.3, "break-even", ha="right", va="bottom", fontsize=9, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(g.index, fontsize=9)
    ax.set_xlim(lo - pad, hi + pad)
    ax.set_ylim(-0.7, len(g) + 0.5)
    ax.set_xlabel(f"profit factor over all replayed months (settings with under {min_trades:,} trades left out)")
    handles = [plt.Line2D([], [], color=tint, linewidth=6, solid_capstyle="round", label="range over the values tested"),
               plt.Line2D([], [], color=color, marker="o", markersize=7, markeredgecolor=SURFACE, linewidth=0, label=dot_label)]
    fig.legend(handles=handles, loc="lower right", bbox_to_anchor=(0.985, 0.005), fontsize=9, ncol=2, columnspacing=1.6)
    fig.suptitle(head, x=0.012, y=0.985, ha="left", fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.012, 0.93, sub, fontsize=9.5, color=INK2)
    fig.tight_layout(rect=(0, 0.035, 1, 0.925))
    fig.savefig(out)
    plt.close(fig)


def fig_inputs(res, out):
    _ranges(res, "oat_native_all.csv", 2000, BLUE, BLUE_TINT, "shipped reference preset",
            "No single input moves the shipped preset to break-even",
            "The 16 inputs with the widest effect, each varied alone around the shipped reference preset", out)


def fig_inputs_cal(res, out):
    _ranges(res, "oat_calibrated.csv", 400, ORANGE, ORANGE_TINT, "calibrated preset",
            "Around the calibrated preset most inputs can only lower the profit factor",
            "The 16 inputs with the widest effect, each varied alone around the calibrated preset", out)


def fig_exit_grid(res, out):
    r = pd.read_csv(os.path.join(res, "study_exits.csv"))
    g = r[(r.tag == "geometry") & (r.UseSpeedProfitExit == 0)]
    pf = g.pivot_table(index="StopSLPoints", columns="StopTPPoints", values="pf")
    av = g.pivot_table(index="StopSLPoints", columns="StopTPPoints", values="avg")
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.1), dpi=160)
    for ax, tab, name, fmt in ((axes[0], pf, "Profit factor", "{:.2f}"), (axes[1], av, "Average points per trade", "{:.0f}")):
        v = tab.to_numpy()
        lo, hi = np.nanmin(v), np.nanmax(v)
        ax.set_xlim(0, v.shape[1])
        ax.set_ylim(0, v.shape[0])
        for i in range(v.shape[0]):
            for j in range(v.shape[1]):
                q = (v[i, j] - lo) / (hi - lo + 1e-12)
                c = SEQ[int(round(q * (len(SEQ) - 1)))]
                ax.add_patch(plt.Rectangle((j + 0.03, i + 0.03), 0.94, 0.94, facecolor=c, linewidth=0))
                ax.text(j + 0.5, i + 0.5, fmt.format(v[i, j]), ha="center", va="center", fontsize=9,
                        color="#ffffff" if q > 0.55 else INK)
        ax.set_xticks(np.arange(v.shape[1]) + 0.5)
        ax.set_xticklabels([f"{int(c)}" for c in tab.columns])
        ax.set_yticks(np.arange(v.shape[0]) + 0.5)
        ax.set_yticklabels([f"{int(c)}" for c in tab.index])
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xlabel("take profit, points")
        ax.set_ylabel("stop loss, points")
        ax.set_title(name, loc="left", fontsize=11, fontweight="bold", color=INK)
    fig.suptitle("Stops and targets rescale the result but do not change its sign", x=0.012, ha="left", fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.012, 0.905, f"Shipped preset entries, speed profit exit off; darker = higher. Every cell loses {-np.nanmax(av.to_numpy()):.0f} to "
             f"{-np.nanmin(av.to_numpy()):.0f} points per trade.", fontsize=9.5, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(out)
    plt.close(fig)


def fig_spread(res, out):
    s = pd.read_csv(os.path.join(res, "study_spread.csv"))
    names = list(dict.fromkeys(s.name))
    fig, ax = plt.subplots(figsize=(8.2, 4.0), dpi=160)
    frame(ax)
    for name in names:
        color = ORANGE if name.startswith("calibrated") else BLUE
        d = s[s.name == name].sort_values("spread_median")
        line(ax, d.spread_median, d.pf, color, name)
        ax.text(d.spread_median.iloc[0] - 0.35, d.pf.iloc[0], f"{d.pf.iloc[0]:.2f}", ha="right", va="center", fontsize=9, color=INK2)
        ax.text(d.spread_median.iloc[-1] + 0.35, d.pf.iloc[-1], f"{d.pf.iloc[-1]:.2f}", ha="left", va="center", fontsize=9, color=INK2)
    ax.axhline(1.0, color=INK2, linewidth=1.0, zorder=2)
    ax.text(s.spread_median.max() + 2.0, 1.01, "break-even", ha="right", va="bottom", fontsize=9, color=INK2)
    ax.set_xlim(s.spread_median.min() - 2.2, s.spread_median.max() + 2.2)
    ax.set_xlabel("median spread of the rebuilt feed, points")
    ax.set_ylabel("profit factor")
    ax.set_ylim(min(0.4, float(s.pf.min()) - 0.05), max(1.15, float(s.pf.max()) + 0.08))
    ax.legend(loc="lower left", fontsize=9)
    ship = s[s.name == names[0]]
    head = ("The shipped preset stays below break-even at every spread tested" if ship.pf.max() < 1
            else "The shipped preset reaches break-even only at the tightest spread tested")
    title(ax, head, "Profit factor over the replayed months with the feed rebuilt at five spread levels")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_fidelity(res, out):
    f = pd.read_csv(os.path.join(res, "fidelity_exit_mix.csv"))
    kinds = list(f.kind)
    fig, ax = plt.subplots(figsize=(8.2, 3.7), dpi=160)
    frame(ax, grid="x")
    y = np.arange(len(kinds))[::-1]
    h = 0.26
    for i, (_, r) in zip(y, f.iterrows()):
        ax.barh(i + h / 2 + 0.03, r.real, height=h, color=AQUA, linewidth=0, zorder=3)
        ax.barh(i - h / 2 - 0.03, r.replay, height=h, color=BLUE, linewidth=0, zorder=3)
        ax.text(r.real + 0.8, i + h / 2 + 0.03, f"{r.real:.0f}%", va="center", fontsize=9, color=INK2)
        ax.text(r.replay + 0.8, i - h / 2 - 0.03, f"{r.replay:.0f}%", va="center", fontsize=9, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(kinds)
    ax.set_xlim(0, 70)
    ax.set_xlabel("share of trades closed this way, %")
    ax.legend(handles=[Patch(facecolor=AQUA, label="real account (saved chart)"), Patch(facecolor=BLUE, label="tick replay of the shipped preset")],
              loc="lower right", fontsize=9)
    m = pd.Series(str(f.note.iloc[0])).str.extract(r"(\d[\d,]*) real trades.*against ([\d,]+) replayed")
    title(ax, "The replay closes trades the same way the real account did",
          f"Stop and limit routes: {m.iloc[0, 0]} real trades (7 Sep to 8 Oct 2026) against {m.iloc[0, 1]} replayed trades")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_grid(res, out):
    """Profit factor by spread cap x alert multiplier: diverging around break-even (blue above, red below)."""
    g = pd.read_csv(os.path.join(res, "grid_calibrated.csv"))
    tab = g.pivot_table(index="MaxSpreadPoints", columns="MaxTrailingMultiplier", values="pf").sort_index(ascending=False)
    cnt = g.pivot_table(index="MaxSpreadPoints", columns="MaxTrailingMultiplier", values="n").sort_index(ascending=False)
    v = tab.to_numpy()
    span = max(abs(np.nanmax(v) - 1.0), abs(1.0 - np.nanmin(v)))
    fig, ax = plt.subplots(figsize=(8.8, 4.4), dpi=160)
    ax.set_xlim(0, v.shape[1])
    ax.set_ylim(0, v.shape[0])
    for i in range(v.shape[0]):
        for j in range(v.shape[1]):
            q = (v[i, j] - 1.0) / span
            step = round(abs(q) * 4) / 4.0                       # four steps per arm, neutral midpoint
            c = _mix("#f0efec", "#1c5cab" if q > 0 else "#d03b3b", step)
            y = v.shape[0] - 1 - i
            ax.add_patch(plt.Rectangle((j + 0.03, y + 0.03), 0.94, 0.94, facecolor=c, linewidth=0))
            ink = "#ffffff" if step >= 0.75 else INK
            ax.text(j + 0.5, y + 0.6, f"{v[i, j]:.2f}", ha="center", va="center", fontsize=10, color=ink)
            ax.text(j + 0.5, y + 0.27, f"{int(cnt.to_numpy()[i, j]):,} trades", ha="center", va="center", fontsize=7.2, color=ink)
    ax.set_xticks(np.arange(v.shape[1]) + 0.5)
    ax.set_xticklabels([f"{c:g}" for c in tab.columns])
    ax.set_yticks(np.arange(v.shape[0]) + 0.5)
    ax.set_yticklabels([f"{int(c)}" for c in tab.index[::-1]])
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xlabel("MaxTrailingMultiplier: the alert needs a move of this many spreads (shipped 7.5, calibrated 30)")
    ax.set_ylabel("MaxSpreadPoints (shipped 31, calibrated 14)")
    above = sorted(float(c) for c in tab.columns[(np.nanmax(v, axis=0) >= 1.05)])
    head = (f"The profit factor clears break-even only for multipliers of {above[0]:g} to {above[-1]:g}" if above
            else "No cell of the grid clears break-even")
    title(ax, head, "Calibrated preset with the spread cap and the alert multiplier varied, all replayed months. Blue = above 1.00, red = below.")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_latency(res, out):
    d = pd.read_csv(os.path.join(res, "latency.csv"))
    fig, ax = plt.subplots(figsize=(8.2, 4.3), dpi=160)
    frame(ax)
    colors = {"shipped reference preset": BLUE, "calibrated preset": ORANGE, "shipped preset with the market route opened": MAGENTA,
              "best set found with no order delay": YELLOW}
    for name in dict.fromkeys(d.name):
        short = name.split(" (")[0]
        k = d[d.name == name].sort_values("latency_ms")
        line(ax, k.latency_ms, k.pf, colors[short], short)
        ax.text(k.latency_ms.iloc[-1] + 6, k.pf.iloc[-1], f"{k.pf.iloc[-1]:.2f}", va="center", fontsize=9, color=INK2)
    ax.axhline(1.0, color=INK2, linewidth=1.0, zorder=2)
    ax.text(d.latency_ms.max(), 1.008, "break-even", ha="right", va="bottom", fontsize=9, color=INK2)
    ax.set_xlim(-10, d.latency_ms.max() + 45)
    ax.set_ylim(float(d.pf.min()) - 0.17, float(d.pf.max()) + 0.05)
    ax.set_xlabel("delay between the EA sending an order and the fill, milliseconds")
    ax.set_ylabel("profit factor")
    ax.legend(loc="lower left", fontsize=8.5, ncol=2, columnspacing=1.4, handlelength=1.6)
    title(ax, "Market entries only look profitable when orders fill with no delay",
          "Profit factor over the replayed months against order delay. The real account's fills fit a delay of about 150 ms.")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_equity(res, out):
    """Cumulative points of the calibrated preset, trade by trade (the data has a gap from June to September 2026)."""
    t = pd.read_csv(os.path.join(res, "center_final_center_trades.csv"), parse_dates=["entry_time"]).sort_values("entry_time").reset_index(drop=True)
    eq = t.pts.cumsum()
    fig, ax = plt.subplots(figsize=(8.2, 4.0), dpi=160)
    frame(ax)
    x = np.arange(1, len(t) + 1)
    ax.plot(x, eq, color=ORANGE, linewidth=2, zorder=4)
    ax.axhline(0, color=AXIS, linewidth=0.8, zorder=2)
    month = t.entry_time.dt.to_period("M").astype(str)
    first = month.drop_duplicates().index.to_numpy()
    labels, last = [], -1e9
    for f in first:                                              # skip a label that would collide with the previous one
        if f - last >= 0.055 * len(t):
            labels.append(month.iloc[f][2:])
            last = f
        else:
            labels.append("")
    ax.set_xticks(first + 1)
    ax.set_xticklabels(labels, fontsize=8.5)
    for f in first[1:]:
        ax.axvline(f + 1, color=GRID, linewidth=0.8, zorder=1)
    ax.text(x[-1], float(eq.iloc[-1]), f"  {eq.iloc[-1]:+,.0f}", va="center", ha="left", fontsize=9, color=INK2)
    peak = eq.cummax()
    j = int((peak - eq).idxmax())
    ax.annotate(f"largest drawdown {float((peak - eq).max()):,.0f} points", xy=(j + 1, float(eq.iloc[j])),
                xytext=(j + 1, float(eq.iloc[j]) - 0.16 * float(eq.max() - eq.min())),
                ha="center", va="top", fontsize=9, color=INK2, arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
    ax.set_xlim(0, len(t) * 1.09)
    ax.set_xlabel("trades in time order; ticks mark the first trade of a month (year-month), no quotes for June to September 2026")
    ax.set_ylabel("cumulative points per 0.01 lot")
    pos = int((t.groupby(month).pts.sum() > 0).sum())
    title(ax, f"The calibrated preset's profit comes from {pos} of {month.nunique()} months",
          f"Cumulative result of the calibrated preset in the replay, {len(t):,} trades, fills calibrated to the real account")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_trailing_cal(res, out):
    """Trail-layer distance on the calibrated entries: profit factor and largest drawdown, side by side (one scale each)."""
    t = pd.read_csv(os.path.join(res, "study_trailing_calibrated.csv"))
    none = t[t.tag == "none"].iloc[0]
    lay = t[t.tag == "layer"].sort_values("distance")
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.0), dpi=160)
    for ax, col, name, fmt in ((axes[0], "pf", "Profit factor", "{:.2f}"), (axes[1], "dd", "Largest drawdown, points", "{:,.0f}")):
        frame(ax)
        xs = np.arange(len(lay))
        line(ax, xs, lay[col], ORANGE)
        ax.axhline(float(none[col]), color=INK2, linewidth=1.0, zorder=2)
        lo, hi = min(float(lay[col].min()), float(none[col])), max(float(lay[col].max()), float(none[col]))
        ax.text(-0.42, float(none[col]) + 0.015 * (hi - lo), "no trailing: " + fmt.format(float(none[col])), ha="left", va="bottom", fontsize=9, color=INK2)
        if col == "pf":
            k = int(np.argmax(lay[col].to_numpy()))
            ax.text(xs[k], float(lay[col].iloc[k]) + 0.04 * (hi - lo), fmt.format(float(lay[col].iloc[k])), ha="center", va="bottom", fontsize=9, color=INK2)
        else:
            k = int(np.argmin(lay[col].to_numpy()))
            ax.text(xs[k], float(lay[col].iloc[k]) - 0.05 * (hi - lo), fmt.format(float(lay[col].iloc[k])), ha="center", va="top", fontsize=9, color=INK2)
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{int(v)}" for v in lay.distance], fontsize=9)
        ax.set_xlim(-0.5, len(lay) - 0.5)
        ax.set_ylim(lo - 0.16 * (hi - lo), hi + 0.2 * (hi - lo))
        ax.set_xlabel("trail layer distance behind the best price, points")
        ax.set_title(name, loc="left", fontsize=11, fontweight="bold", color=INK)
    fig.suptitle("A trail of 125 to 200 points keeps the profit factor; a closer one costs it", x=0.012, y=0.985, ha="left", fontsize=12.5,
                 fontweight="bold", color=INK)
    fig.text(0.012, 0.9, "Calibrated entries, only the trail layer distance changes (shipped 100, calibrated 150). The line is the preset with no trailing.",
             fontsize=9.5, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(out)
    plt.close(fig)


def fig_joint(res, out):
    """Average profit factor by alert multiplier across the joint grid, with the range of the sets behind each average."""
    d = pd.read_csv(os.path.join(res, "grid_joint.csv"))
    g = d.groupby("MaxTrailingMultiplier").pf.agg(["mean", "min", "max", "size"]).reset_index()
    fig, ax = plt.subplots(figsize=(8.2, 4.1), dpi=160)
    frame(ax)
    xs = np.arange(len(g))
    for i, r in zip(xs, g.itertuples()):
        ax.plot([i, i], [r.min, r.max], color=ORANGE_TINT, linewidth=7, solid_capstyle="round", zorder=3)
    ax.plot(xs, g["mean"], color=ORANGE, linewidth=2, marker="o", markersize=7, markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=5)
    means = g["mean"].to_numpy()
    for i in xs:                                                 # label on the side of the point that the line leaves free
        rising = i + 1 < len(means) and means[i + 1] > means[i]
        ax.text(i + 0.13, means[i] + (-0.006 if rising else 0.006), f"{means[i]:.2f}", ha="left", va="top" if rising else "bottom", fontsize=9, color=INK2)
    ax.axhline(1.0, color=INK2, linewidth=1.0, zorder=2)
    ax.text(len(g) - 0.28, 0.996, "break-even", ha="right", va="top", fontsize=9, color=INK2)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{v:g}" for v in g.MaxTrailingMultiplier])
    ax.set_xlim(-0.5, len(g) - 0.25)
    ax.set_ylim(float(g["min"].min()) - 0.02, float(g["max"].max()) + 0.075)
    ax.set_xlabel("MaxTrailingMultiplier")
    ax.set_ylabel("profit factor, all replayed months")
    handles = [plt.Line2D([], [], color=ORANGE, linewidth=2, marker="o", markersize=7, markeredgecolor=SURFACE, label=f"average of {int(g['size'].iloc[0])} input sets"),
               plt.Line2D([], [], color=ORANGE_TINT, linewidth=7, solid_capstyle="round", label="lowest to highest of those sets")]
    ax.legend(handles=handles, loc="upper left", fontsize=9, ncol=2, columnspacing=1.6)
    title(ax, f"Averaged over {len(d)} neighbouring input sets the edge is small: about {d.pf.mean():.2f}",
          "Each point averages all sets of the joint grid that share that multiplier")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


if __name__ == "__main__":
    res = sys.argv[1]
    os.makedirs(os.path.join(res, "charts"), exist_ok=True)
    for name, fn in (("monthly_pf", fig_monthly), ("edge_vs_cost", fig_edge), ("input_ranges", fig_inputs),
                     ("exit_grid", fig_exit_grid), ("spread", fig_spread), ("fidelity", fig_fidelity),
                     ("spread_multiplier_grid", fig_grid), ("latency", fig_latency), ("equity_calibrated", fig_equity),
                     ("trailing_calibrated", fig_trailing_cal), ("joint_grid", fig_joint), ("input_ranges_calibrated", fig_inputs_cal)):
        try:
            fn(res, os.path.join(res, "charts", name + ".png"))
            print("wrote", name)
        except (FileNotFoundError, KeyError, IndexError) as e:
            print("skipped", name, "-", repr(e))
