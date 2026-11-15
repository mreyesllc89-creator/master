"""Report figures (static PNG, light surface). usage: python -I charts.py <results_dir>

Palette and mark rules: one hue per series in a fixed order (blue, orange, aqua), thin bars with a
rounded data end, 2 px lines, hairline solid grid, text in ink colours, a legend only when there are
two or more series, never two y scales.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.labelcolor": INK2, "ytick.labelcolor": INK2, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "axes.grid": False, "legend.frameon": False,
})


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


def hbar(ax, y, x0, x1, h, color):
    """Horizontal bar from x0 to x1, square at the baseline (x0) and rounded at the data end."""
    w = x1 - x0
    if abs(w) < 1e-12:
        return
    r = min(h / 2.2, abs(w) * 0.5)
    ax.add_patch(FancyBboxPatch((min(x0, x1), y - h / 2), abs(w), h, boxstyle=f"round,pad=0,rounding_size={r}",
                                linewidth=0, facecolor=color, mutation_aspect=1.0, zorder=3))
    # square off the baseline end
    ax.barh(y, w * 0.5, left=x0, height=h, color=color, linewidth=0, zorder=3)


def vbar(ax, x, y, w, color):
    r = min(w / 2.2, abs(y) * 0.5)
    ax.add_patch(FancyBboxPatch((x - w / 2, min(0, y)), w, abs(y), boxstyle=f"round,pad=0,rounding_size={r}",
                                linewidth=0, facecolor=color, zorder=3))
    ax.bar(x, y * 0.5, width=w, color=color, linewidth=0, zorder=3)


def fig_monthly(res, out):
    m = pd.read_csv(os.path.join(res, "baseline_by_month.csv"))
    m = m[(m.preset == "FlashGold_NativeReference") & (m.month != "ALL")]
    fig, ax = plt.subplots(figsize=(8.2, 3.9), dpi=160)
    x = np.arange(len(m))
    ax.set_xlim(-0.6, len(m) - 0.4)
    ax.set_ylim(0, 1.15)
    frame(ax)
    for i, v in zip(x, m.pf):
        ax.bar(i, v, width=0.34, color=BLUE, linewidth=0, zorder=3)
        ax.text(i, v + 0.025, f"{v:.2f}", ha="center", va="bottom", fontsize=9, color=INK2)
    ax.axhline(1.0, color=INK2, linewidth=1.0, zorder=2)
    ax.text(len(m) - 0.45, 1.02, "break-even (1.00)", ha="right", va="bottom", fontsize=9, color=INK2)
    ax.set_xticks(x)
    ax.set_xticklabels(m.month, fontsize=9)
    ax.set_ylabel("profit factor")
    title(ax, "The shipped reference preset loses in every month replayed",
          "Profit factor per month, tick replay with fills calibrated to the real account (9,908 trades in total)")
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
    ax.plot(d.h_s, d.mid_drift_FLXQ, color=BLUE, linewidth=2, marker="o", markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=4,
            label="price move in the trade's favour after the fill (momentum stop entries)")
    ax.plot(d.h_s, np.full(len(d), cost), color=ORANGE, linewidth=2, zorder=3, label="what a round trip costs (spread + slippage)")
    ax.axhline(0, color=AXIS, linewidth=0.8, zorder=2)
    ax.text(d.h_s.iloc[-1], cost + 1.2, f"cost about {cost:.0f} points", ha="right", va="bottom", fontsize=9, color=INK2)
    k = int(d.mid_drift_FLXQ.idxmax())
    ax.text(d.h_s.loc[k], d.mid_drift_FLXQ.loc[k] + 1.6, f"best case +{d.mid_drift_FLXQ.loc[k]:.0f} points", ha="center", va="bottom", fontsize=9, color=INK2)
    ax.set_xticks([1, 2, 5, 10, 20, 30, 60, 120, 300])
    ax.set_xticklabels(["1 s", "2 s", "5 s", "10 s", "20 s", "30 s", "1 min", "2 min", "5 min"])
    ax.minorticks_off()
    ax.set_ylim(min(-6, d.mid_drift_FLXQ.min() - 3), cost + 8)
    ax.set_xlabel("time after the fill")
    ax.set_ylabel("points (1 point = $0.01)")
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.93), fontsize=9, handlelength=1.6)
    title(ax, "After a fill the market keeps moving the trade's way by only a few points",
          "Average mid-price move after entry versus the average cost of the trade, 6,960 replayed momentum entries")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_inputs(res, out):
    o = pd.read_csv(os.path.join(res, "oat_native_all.csv"))
    o = o[o.n >= 2000]
    base = o[o.is_base].pf.iloc[0]
    g = o.groupby("input").pf.agg(["min", "max"])
    g["span"] = g["max"] - g["min"]
    g = g[~g.index.str.startswith("X_")].sort_values("span", ascending=False).head(16).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.2, 5.6), dpi=160)
    frame(ax, grid="x")
    y = np.arange(len(g))
    for i, (name, r) in zip(y, g.iterrows()):
        ax.plot([r["min"], r["max"]], [i, i], color=BLUE, linewidth=6, solid_capstyle="round", zorder=3)
    ax.scatter(np.full(len(g), base), y, s=46, color=ORANGE, edgecolor=SURFACE, linewidth=1.5, zorder=5)
    ax.axvline(1.0, color=INK2, linewidth=1.0, zorder=2)
    ax.text(1.0, len(g) - 0.25, "break-even", ha="center", va="bottom", fontsize=9, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(g.index, fontsize=9)
    ax.set_xlim(0.6, 1.05)
    ax.set_ylim(-0.7, len(g) + 0.3)
    ax.set_xlabel("profit factor over all eight months")
    ax.plot([], [], color=BLUE, linewidth=6, solid_capstyle="round", label="range over the values tested")
    ax.scatter([], [], s=46, color=ORANGE, edgecolor=SURFACE, linewidth=1.5, label="shipped preset")
    ax.legend(loc="lower left", fontsize=9, bbox_to_anchor=(0.0, 0.0))
    title(ax, "No single input moves the profit factor to break-even",
          "The 16 inputs with the widest effect; each varied alone around the shipped reference preset (settings with under 2,000 trades left out)")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


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
    fig.text(0.012, 0.905, "Reference preset entries, speed profit exit off; darker = higher. Every cell loses 13 to 25 points per trade.", fontsize=9.5, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(out)
    plt.close(fig)


def fig_spread(res, out):
    s = pd.read_csv(os.path.join(res, "study_spread.csv"))
    names = list(dict.fromkeys(s.name))
    fig, ax = plt.subplots(figsize=(8.2, 4.0), dpi=160)
    frame(ax)
    for name, color in zip(names, (BLUE, ORANGE, AQUA)):
        d = s[s.name == name].sort_values("spread_median")
        ax.plot(d.spread_median, d.pf, color=color, linewidth=2, marker="o", markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5, label=name, zorder=4)
        ax.text(d.spread_median.iloc[0] - 0.25, d.pf.iloc[0], f"{d.pf.iloc[0]:.2f}", ha="right", va="center", fontsize=9, color=INK2)
    ax.axhline(1.0, color=INK2, linewidth=1.0, zorder=2)
    ax.text(s.spread_median.max(), 1.01, "break-even", ha="right", va="bottom", fontsize=9, color=INK2)
    ax.set_xlabel("median spread of the rebuilt feed, points")
    ax.set_ylabel("profit factor")
    ax.set_ylim(0.4, 1.15)
    ax.legend(loc="lower left", fontsize=9)
    title(ax, "A tighter spread helps, but not enough to reach break-even",
          "Profit factor over eight months with the feed rebuilt at different spreads")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_fidelity(res, out):
    f = pd.read_csv(os.path.join(res, "fidelity_exit_mix.csv"))
    kinds = list(f.kind)
    fig, ax = plt.subplots(figsize=(8.2, 3.6), dpi=160)
    frame(ax, grid="x")
    y = np.arange(len(kinds))[::-1]
    h = 0.26
    for i, (_, r) in zip(y, f.iterrows()):
        ax.barh(i + h / 2 + 0.03, r.real, height=h, color=BLUE, linewidth=0, zorder=3)
        ax.barh(i - h / 2 - 0.03, r.replay, height=h, color=ORANGE, linewidth=0, zorder=3)
        ax.text(r.real + 0.8, i + h / 2 + 0.03, f"{r.real:.0f}%", va="center", fontsize=9, color=INK2)
        ax.text(r.replay + 0.8, i - h / 2 - 0.03, f"{r.replay:.0f}%", va="center", fontsize=9, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(kinds)
    ax.set_xlim(0, 70)
    ax.set_xlabel("share of trades closed this way, %")
    ax.barh([], [], color=BLUE, label="real trades (saved chart)")
    ax.barh([], [], color=ORANGE, label="tick replay")
    ax.legend(loc="lower right", fontsize=9)
    title(ax, "The replay closes trades the same way the real account did",
          str(f.note.iloc[0]))
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def _mix(c0, c1, q):
    a = np.array([int(c0[i:i + 2], 16) for i in (1, 3, 5)], float)
    b = np.array([int(c1[i:i + 2], 16) for i in (1, 3, 5)], float)
    v = a + (b - a) * q
    return "#%02x%02x%02x" % tuple(int(round(x)) for x in v)


def fig_grid(res, out):
    """Profit factor by spread cap x alert multiplier: diverging around break-even (blue above, red below)."""
    g = pd.read_csv(os.path.join(res, "grid_stops.csv"))
    tab = g.pivot_table(index="MaxSpreadPoints", columns="MaxTrailingMultiplier", values="pf").sort_index(ascending=False)
    cnt = g.pivot_table(index="MaxSpreadPoints", columns="MaxTrailingMultiplier", values="n").sort_index(ascending=False)
    v = tab.to_numpy()
    span = max(abs(np.nanmax(v) - 1.0), abs(1.0 - np.nanmin(v)))
    fig, ax = plt.subplots(figsize=(8.4, 4.6), dpi=160)
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
            ax.text(j + 0.5, y + 0.58, f"{v[i, j]:.2f}", ha="center", va="center", fontsize=10, color=ink)
            ax.text(j + 0.5, y + 0.27, f"{int(cnt.to_numpy()[i, j]):,} trades", ha="center", va="center", fontsize=7.5, color=ink)
    ax.set_xticks(np.arange(v.shape[1]) + 0.5)
    ax.set_xticklabels([f"{c:g}" for c in tab.columns])
    ax.set_yticks(np.arange(v.shape[0]) + 0.5)
    ax.set_yticklabels([f"{int(c)}" for c in tab.index[::-1]])
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xlabel("MaxTrailingMultiplier (alert needs a move of this many spreads)   -   shipped: 7.5")
    ax.set_ylabel("MaxSpreadPoints (shipped: 31)")
    title(ax, "Only large bursts at a tight spread get above break-even",
          "Profit factor over eight months, stop orders only, realistic fills. Blue = above 1.00, red = below.")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def fig_latency(res, out):
    d = pd.read_csv(os.path.join(res, "latency.csv"))
    fig, ax = plt.subplots(figsize=(8.2, 4.0), dpi=160)
    frame(ax)
    names = list(dict.fromkeys(d.name))
    for name, color in zip(names, (BLUE, ORANGE, AQUA)):
        k = d[d.name == name].sort_values("latency_ms")
        ax.plot(k.latency_ms, k.pf, color=color, linewidth=2, marker="o", markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5, label=name, zorder=4)
        ax.text(k.latency_ms.iloc[-1] + 6, k.pf.iloc[-1], f"{k.pf.iloc[-1]:.2f}", va="center", fontsize=9, color=INK2)
    ax.axhline(1.0, color=INK2, linewidth=1.0, zorder=2)
    ax.text(d.latency_ms.max(), 1.008, "break-even", ha="right", va="bottom", fontsize=9, color=INK2)
    ax.set_xlim(-10, d.latency_ms.max() + 45)
    ax.set_xlabel("delay between the EA sending an order and the fill, milliseconds")
    ax.set_ylabel("profit factor")
    ax.legend(loc="lower left", fontsize=9)
    title(ax, "Market entries only look profitable when orders fill with no delay",
          "Profit factor over eight months against order delay. The real account's fills fit a delay of about 150 ms.")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


if __name__ == "__main__":
    res = sys.argv[1]
    os.makedirs(os.path.join(res, "charts"), exist_ok=True)
    for name, fn in (("monthly_pf", fig_monthly), ("edge_vs_cost", fig_edge), ("input_ranges", fig_inputs),
                     ("exit_grid", fig_exit_grid), ("spread", fig_spread), ("fidelity", fig_fidelity),
                     ("spread_multiplier_grid", fig_grid), ("latency", fig_latency)):
        try:
            fn(res, os.path.join(res, "charts", name + ".png"))
            print("wrote", name)
        except (FileNotFoundError, KeyError) as e:
            print("skipped", name, "-", e)
