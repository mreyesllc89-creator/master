"""The two trade directions by filter timeframe, from the sweep records.

usage: python direction_by_filter.py [results_dir] [n_worlds=1000]

Does "trade with the filter" hold whatever the filter's timeframe? For every chart and every
filter timeframe of the search, the settings with at least 30 trades in each half of the search
window are split by trade direction:

  before costs   share positive in both halves before costs (the trades themselves)
  after costs    share with a net result above zero over the whole window (0.05 % per side,
                 1 tick, funding)
  luck           share of luck-only worlds (months drawn at random, every setting's month
                 flipped by one coin toss: luck.py) whose before-cost gap between the two
                 directions is at least as large, in either direction

Also printed, because the report quotes them: the 5m and 10m settings that trade with the
filter, with a 4h filter and without a trailing stop.

Writes results/direction_by_filter.md (the table of REPORT.md, section 6) and prints the log.
"""
import os
import sys

import numpy as np

import holdout as H
import make_pine
import space

NS = 36


def both_gross(g, cnt):
    """(eligible, positive in both halves before costs) for monthly gross R and trade counts."""
    h = NS // 2
    ok = (cnt[:, :h].sum(1) >= 30) & (cnt[:, h:].sum(1) >= 30)
    pos = (g[:, :h].sum(1) > 0) & (g[:, h:].sum(1) > 0)
    return ok, pos


def share(pos, m):
    return float(pos[m].mean()) if m.any() else float("nan")


def run(res_dir, n_worlds=1000, seed=2026):
    rows, log = [], []
    for tf in space.CHART_TFS:
        d, settings = H.load(os.path.join(res_dir, "sweeps"), tf)
        g = d["gross"].astype(np.float64)
        net = g - H.BASE_FEE * d["feeu"].astype(np.float64) - d["fund"].astype(np.float64)
        cnt = d["cnt"]
        inv = np.array([bool(s["inverted"]) for s in settings])
        ftf = np.array([int(s["f_tf"]) for s in settings])
        trail = np.array([bool(s["trail"]) for s in settings])
        ok, pos = both_gross(g, cnt)
        netpos = net.sum(1) > 0
        total = net.sum(1)
        fts = sorted(set(ftf.tolist()))
        # luck-only worlds: the gap between the directions inside each filter timeframe
        rng = np.random.default_rng(seed + tf)
        gaps = {f: [] for f in fts}
        for _ in range(n_worlds):
            idx = rng.integers(0, g.shape[1], NS)
            sg = rng.choice(np.array([-1.0, 1.0]), NS)
            okw, posw = both_gross(g[:, idx] * sg, cnt[:, idx])
            for f in fts:
                gaps[f].append(share(posw, okw & (ftf == f) & ~inv) - share(posw, okw & (ftf == f) & inv))
        name = make_pine.TF_NAME[tf]
        log.append(f"chart {name}: {int(ok.sum()):,} of {len(settings):,} settings with at least 30 trades in each half")
        cells = {}
        for f in fts:
            w, i = ok & (ftf == f) & ~inv, ok & (ftf == f) & inv
            gap = share(pos, w) - share(pos, i)
            gv = np.array(gaps[f])
            gv = gv[~np.isnan(gv)]
            luck = float((np.abs(gv) >= abs(gap)).mean()) if gv.size else float("nan")
            cells[f] = (share(pos, w), share(pos, i), luck)
            log.append(f"  filter {make_pine.TF_NAME.get(f, str(f)):>3}: with the filter {int(w.sum()):4d} settings, before costs {share(pos, w) * 100:5.1f}%, "
                       f"after costs {share(netpos, w) * 100:4.1f}% | inverted {int(i.sum()):4d} settings, before costs {share(pos, i) * 100:5.1f}%, "
                       f"after costs {share(netpos, i) * 100:4.1f}% | gap {gap * 100:+5.1f} points, luck-only worlds with a gap this large: {luck * 100:.1f}%")
        rows.append((tf, name, cells))
        if tf in (5, 10):
            for label, sel in (("a 4h filter", ftf == 240), ("a 4h or 1D filter", ftf >= 240)):
                m = ok & ~inv & ~trail & sel
                log.append(f"  with the filter, {label}, trailing off: {int(m.sum())} settings, {int(netpos[m].sum())} positive after costs = "
                           f"{netpos[m].mean() * 100:.1f}%, median {np.median(total[m]):+.1f}R")
    # the table: one row per chart, one column per filter timeframe; the chart's own timeframe first
    cols = [5, 15, 30, 60, 240, 1440]
    L = ["| Chart | Filter on the chart's own timeframe | " + " | ".join(make_pine.TF_NAME[c] + " filter" for c in cols) + " |",
         "|---|---|" + "---|" * len(cols)]

    def cell(c):
        if c is None:
            return "-"
        t = f"{c[0] * 100:.0f}% / {c[1] * 100:.0f}%"
        return t + " *" if c[1] > c[0] else t
    for tf, name, cells in rows:
        own = cells.get(tf)
        L.append(f"| {name} | {cell(own)} | " + " | ".join("see first column" if c == tf and own else cell(cells.get(c)) for c in cols) + " |")
    L += ["", "\\* inverted ahead."]
    open(os.path.join(res_dir, "direction_by_filter.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(log))
    print()
    print("\n".join(L))


if __name__ == "__main__":
    rd = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    run(rd, int(sys.argv[2]) if len(sys.argv) > 2 else 1000)
