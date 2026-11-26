"""Equity curves of every timeframe's pick: cumulative net R, the untouched period and the
search window each starting from zero. Small multiples, one panel per chart timeframe.

usage: python charts.py [results_dir]   ->  results/equity_all.png
Colours: slots 1 and 2 of the reference categorical palette (validated for colour-blind
separation); text in text tokens, not in series colours.
"""
import csv
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import make_pine
import space

BLUE, ORANGE = "#257de0", "#f47230"       # search window, untouched period
TEXT, TEXT2, GRID, SURFACE = "#191919", "#666666", "#e6e6e6", "#ffffff"
SPLIT = pd.Timestamp("2023-11-01")


def load(res_dir, name):
    p = os.path.join(res_dir, f"trades_BTCUSDT_{name}.csv")
    if not os.path.exists(p):
        return None
    rows = list(csv.DictReader(open(p)))
    out = {}
    for period in ("untouched", "search"):
        r = [x for x in rows if x["period"] == period]
        t = pd.to_datetime([x["exit_utc"] for x in r])
        out[period] = (t, np.cumsum([float(x["net_R"]) for x in r]))
    return out


def draw(res_dir):
    verdicts = {v["tf"]: v for v in json.load(open(os.path.join(res_dir, "verdicts.json")))}
    tfs = [tf for tf in space.CHART_TFS if tf in verdicts]
    ncol = 3
    nrow = int(np.ceil(len(tfs) / ncol))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.linewidth": 1,
                         "xtick.color": TEXT2, "ytick.color": TEXT2, "axes.labelcolor": TEXT2, "text.color": TEXT})
    fig, axes = plt.subplots(nrow, ncol, figsize=(13.5, 3.5 * nrow + 0.9), dpi=160, facecolor=SURFACE)
    axes = np.atleast_2d(axes)
    for k, tf in enumerate(tfs):
        ax = axes[k // ncol, k % ncol]
        name = make_pine.TF_NAME[tf]
        d = load(res_dir, name)
        ax.set_facecolor(SURFACE)
        ax.grid(True, axis="y", color=GRID, linewidth=1)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(length=0)
        ax.axhline(0, color="#bdbdbd", linewidth=1)
        ax.set_title(f"{name}  ·  {verdicts[tf]['verdict'].lower()}", loc="left", fontsize=11, color=TEXT, pad=8)
        if d is None:
            ax.text(0.5, 0.5, "no setting positive in both halves", transform=ax.transAxes, ha="center", va="center", color=TEXT2)
            ax.set_xticks([])
            continue
        ax.axvline(SPLIT, color="#bdbdbd", linewidth=1)
        for period, col in (("untouched", ORANGE), ("search", BLUE)):
            t, eq = d[period]
            if len(eq) == 0:
                continue
            x0 = pd.Timestamp("2021-01-01") if period == "untouched" else SPLIT
            ax.plot([x0] + list(t), [0.0] + list(eq), color=col, linewidth=2, solid_joinstyle="round", solid_capstyle="round")
            ax.plot([t[-1]], [eq[-1]], marker="o", markersize=7, color=col, markeredgecolor=SURFACE, markeredgewidth=2)
            ax.annotate(f"{eq[-1]:+.0f}R", (t[-1], eq[-1]), xytext=(-6, 9), textcoords="offset points", ha="right", fontsize=10, color=TEXT)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.set_xlim(pd.Timestamp("2021-01-01"), pd.Timestamp("2026-12-15"))
        ax.margins(y=0.18)
    for k in range(len(tfs), nrow * ncol):
        axes[k // ncol, k % ncol].axis("off")
    handles = [plt.Line2D([0], [0], color=ORANGE, linewidth=2, label="untouched period 2021-01 to 2023-10 (never used to choose the setting)"),
               plt.Line2D([0], [0], color=BLUE, linewidth=2, label="search window 2023-11 to 2026-10 (the setting was chosen here)")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.045, 0.955), ncol=2, frameon=False, fontsize=10, labelcolor=TEXT2)
    fig.suptitle("Cumulative result of each timeframe's pick, in R (1R = the amount risked per trade), after fees and funding",
                 x=0.05, y=0.985, ha="left", fontsize=12.5, color=TEXT)
    fig.tight_layout(rect=(0.02, 0.0, 0.99, 0.925))
    out = os.path.join(res_dir, "equity_all.png")
    fig.savefig(out, facecolor=SURFACE)
    print(out)


def draw_direction(res_dir):
    """Two panels: share of the search's settings positive in both halves by trade direction,
    and the commission of one round trip in R, per chart timeframe."""
    summ = json.load(open(os.path.join(res_dir, "summary.json")))
    summ = [r for r in summ if r.get("with_filter_both") is not None]
    if not summ:
        return
    names = [r["name"] for r in summ]
    x = np.arange(len(names))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.linewidth": 1,
                         "xtick.color": TEXT2, "ytick.color": TEXT2, "axes.labelcolor": TEXT2, "text.color": TEXT})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.5, 4.6), dpi=160, facecolor=SURFACE, gridspec_kw={"width_ratios": [1.45, 1]})
    for ax in (a1, a2):
        ax.set_facecolor(SURFACE)
        ax.grid(True, axis="y", color=GRID, linewidth=1)
        ax.set_axisbelow(True)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(length=0)
        ax.set_xticks(x)
        ax.set_xticklabels(names)
    w = 0.36
    wf = np.array([r["with_filter_both"] * 100 for r in summ])
    iv = np.array([r["inverted_both"] * 100 for r in summ])
    a1.bar(x - w / 2 - 0.01, wf, w, color=BLUE, label="with the filter")
    a1.bar(x + w / 2 + 0.01, iv, w, color=ORANGE, label="inverted (the shipped direction)")
    for xi, v in zip(x - w / 2 - 0.01, wf):
        a1.annotate(f"{v:.0f}%" if v >= 9.5 else f"{v:.1f}%", (xi, v), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9, color=TEXT)
    for xi, v in zip(x + w / 2 + 0.01, iv):
        a1.annotate(f"{v:.0f}%" if v >= 9.5 else f"{v:.1f}%", (xi, v), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9, color=TEXT)
    a1.set_ylim(0, max(wf.max(), iv.max()) * 1.22)
    a1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    a1.set_title("Settings positive after costs in both halves of the search window, by trade direction", loc="left", fontsize=11, color=TEXT, pad=26)
    a1.legend(loc="upper left", bbox_to_anchor=(0.0, 1.12), ncol=2, frameon=False, fontsize=10, labelcolor=TEXT2, handlelength=1.2, borderaxespad=0)
    a1.set_xlabel("chart timeframe")
    fee = np.array([r["fee_r"] for r in summ])
    a2.bar(x, fee, 0.5, color=BLUE)
    for xi, v in zip(x, fee):
        a2.annotate(f"{v:.2f}R", (xi, v), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9, color=TEXT)
    a2.set_ylim(0, fee.max() * 1.18)
    a2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1f}R"))
    a2.set_title("Commission of one round trip (0.05% per side) with a 1 x ATR stop", loc="left", fontsize=11, color=TEXT, pad=26)
    a2.set_xlabel("chart timeframe")
    fig.tight_layout(rect=(0.01, 0.0, 0.99, 0.98), w_pad=3)
    out = os.path.join(res_dir, "direction_and_costs.png")
    fig.savefig(out, facecolor=SURFACE)
    print(out)


if __name__ == "__main__":
    rd = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    draw(rd)
    draw_direction(rd)
