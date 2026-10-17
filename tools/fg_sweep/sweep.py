"""FlashGold v5: which exits work on which chart timeframe, after costs?

Automated walk-forward sweep on one TradingView export. For every chart
timeframe it:
  1. builds the chart from the export (5m export -> 5m, 15m, 30m, 1H, 2H),
     with the export's own candles as the intrabar path (better fills than a
     4-point guess on the higher timeframes);
  2. runs every exit setting in the grid on the IN-SAMPLE part only
     (default first 60%), worst-case fills, with costs;
  3. picks a setting from a stable area, not the single best cell: the cell
     whose neighbours (next stop / next target) are also good, among cells
     with enough trades and both in-sample halves positive;
  4. runs that one setting on the OUT-OF-SAMPLE part it has never seen, and
     reports it under all four conditions of docs/rules/validation.md.

Usage:
    python -I tools/fg_sweep/sweep.py <export_5m.csv> [--out sweep_report.md]

The filter is off (the off/on test showed no edge); the signal is the
strategy's default. Engine: tools/fgf_ab/fg5.py.
"""
import argparse, itertools, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "fgf_ab"))
import fg5 as F
from fgf_ab import load_csv, tv_path

SL = [0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0]          # stop, ATR(14) of the chart
TPR = [1.0, 2.0, 3.0, 5.0]                          # target, R multiple of the stop
STYLES = ["Fixed", "Partial + runner"]
BURST = [0.5, 1.0]                                  # burst threshold, ATR mult

G = {}   # per-process data (set by init)


def build_tf(ms, o, h, l, c, base_ms, mult):
    """Chart of mult x the base candles, aligned to 00:00 UTC; each chart bar's
    path is its base candles, 4 points each (TradingView's open-nearer-extreme
    rule)."""
    path = tv_path(o, h, l, c)
    path_t = np.repeat(ms, 4) + np.tile(np.arange(4), len(ms))
    tf = base_ms * mult
    key = ms // tf
    st = np.flatnonzero(np.r_[True, key[1:] != key[:-1]]); en = np.r_[st[1:], len(ms)]
    chart = F.Bars(key[st] * tf, o[st], np.maximum.reduceat(h, st), np.minimum.reduceat(l, st), c[en - 1], tf, st * 4, en * 4)
    return chart, path_t, path


def init(data):
    G.update(data)


def run_cell(args):
    tfm, burst, sl, tpr, style, worst, with_cost, b0, b1 = args
    D = G[tfm]
    sig = D["sig"][burst]
    cost = G["cost"] if with_cost else G["nocost"]
    xp = F.ExitParams(mode="ATR", sl_atr=sl, tpr_atr=tpr, style=style, use_trail=False)
    # trades are taken from b0; bars after b1 are cut off by slicing the chart
    ch = D["chart"]
    if b1 < len(ch.t):
        ch = F.Bars(ch.t[:b1], ch.o[:b1], ch.h[:b1], ch.l[:b1], ch.c[:b1], ch.tf_ms, ch.bs[:b1], ch.be[:b1])
        pe = ch.be[-1]
        pt, pp = G["path_t"][:pe], G["path"][:pe]
    else:
        pt, pp = G["path_t"], G["path"]
    gate = np.ones(len(ch.t), bool)
    tr, _ = F.run(ch, pt, pp, pp, sig, gate, gate, xp, cost, synthetic=True, worst_case=worst, start_bar=b0)
    return args, tr


def summarize(tr, cost, mid_ms):
    m = F.metrics(tr, cost)
    if len(tr):
        h1 = F.metrics(tr[tr.entry_t < mid_ms], cost)["net"]; h2 = F.metrics(tr[tr.entry_t >= mid_ms], cost)["net"]
    else:
        h1 = h2 = 0.0
    return dict(trades=m["trades"], net=float(m["net"]), pf=float(m["pf"]) if m["trades"] else np.nan,
                maxdd=float(m["maxdd"]), per_trade=(float(m["net"]) / m["trades"] if m["trades"] else np.nan), h1=h1, h2=h2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default="sweep_report.md")
    ap.add_argument("--tfs", default="1,3,6,12,24", help="chart timeframes as multiples of the export's (5m: 5m,15m,30m,1H,2H)")
    ap.add_argument("--is-frac", type=float, default=0.6, help="in-sample share of the scored period")
    ap.add_argument("--qty", type=float, default=10)
    ap.add_argument("--tick", type=float, default=0.01)
    ap.add_argument("--comm-pct", type=float, default=0.02)
    ap.add_argument("--slip-ticks", type=int, default=5)
    ap.add_argument("--warmup-days", type=float, default=5.0)
    ap.add_argument("--min-trades", type=int, default=30, help="in-sample trades a cell needs to be chosen")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    a = ap.parse_args()

    ms, o, h, l, c = load_csv(a.csv)
    base_ms = int(np.median(np.diff(ms)))
    cost = F.Costs(qty=a.qty, unit=1.0, comm_side_per_qty=0.0, comm_pct=a.comm_pct, slip_ticks=a.slip_ticks, tick=a.tick)
    nocost = F.Costs(qty=a.qty, unit=1.0, comm_side_per_qty=0.0, comm_pct=0.0, slip_ticks=0, tick=a.tick)
    t0 = ms[0] + int(a.warmup_days * 86400000)
    t_split = t0 + int((ms[-1] - t0) * a.is_frac)
    is_mid = t0 + (t_split - t0) // 2
    oos_mid = t_split + (ms[-1] - t_split) // 2

    data = dict(cost=cost, nocost=nocost)
    tfs = [int(x) for x in a.tfs.split(",")]
    for m in tfs:
        chart, path_t, path = build_tf(ms, o, h, l, c, base_ms, m)
        data["path_t"], data["path"] = path_t, path
        z2 = F.resample(chart, 2); z3 = F.resample(chart, 4)
        sig = {b: F.signal(chart, z2, z3, F.SigParams(burst_atr=b), a.tick) for b in BURST}
        data[m] = dict(chart=chart, sig=sig, b_start=int(np.searchsorted(chart.t, t0)),
                       b_split=int(np.searchsorted(chart.t, t_split)))

    # 1. in-sample grid, worst case with costs
    jobs = [(m, b, sl, tp, st, True, True, data[m]["b_start"], data[m]["b_split"])
            for m in tfs for b, sl, tp, st in itertools.product(BURST, SL, TPR, STYLES)]
    print(f"in-sample grid: {len(jobs)} runs on {a.jobs} cores", file=sys.stderr)
    rows = []
    with ProcessPoolExecutor(a.jobs, initializer=init, initargs=(data,)) as ex:
        for args, tr in ex.map(run_cell, jobs, chunksize=4):
            m, b, sl, tp, st = args[:5]
            rows.append(dict(tf=m * base_ms // 60000, mult=m, burst=b, sl=sl, tpr=tp, style=st, **summarize(tr, cost, is_mid)))
    IS = pd.DataFrame(rows)

    # 2. choose per timeframe: eligible cells, scored by the median net of the
    # cell and its stop / target neighbours (a plateau, not a peak)
    picks = []
    for m in tfs:
        T = IS[IS.mult == m].copy()
        def plateau(r):
            nb = T[(T.burst == r.burst) & (T["style"] == r["style"]) &
                   (T.sl.isin(SL[max(0, SL.index(r.sl) - 1): SL.index(r.sl) + 2])) &
                   (T.tpr.isin(TPR[max(0, TPR.index(r.tpr) - 1): TPR.index(r.tpr) + 2]))]
            return nb.net.median()
        T["plateau"] = T.apply(plateau, axis=1)
        E = T[(T.trades >= a.min_trades) & (T.h1 > 0) & (T.h2 > 0)]
        picks.append((m, None if E.empty else E.sort_values("plateau", ascending=False).iloc[0], len(E), len(T)))

    # 3. out-of-sample: the pick only, all four conditions
    oos_jobs = []
    for m, p, _, _ in picks:
        if p is None: continue
        for worst, wc in itertools.product((False, True), (False, True)):
            oos_jobs.append((m, p.burst, p.sl, p.tpr, p["style"], worst, wc, data[m]["b_split"], len(data[m]["chart"].t)))
    OOS = {}
    with ProcessPoolExecutor(a.jobs, initializer=init, initargs=(data,)) as ex:
        for args, tr in ex.map(run_cell, oos_jobs):
            OOS[(args[0], args[5], args[6])] = summarize(tr, cost if args[6] else nocost, oos_mid)

    IS.to_csv(os.path.splitext(a.out)[0] + "_insample_grid.csv", index=False)
    d = lambda x: pd.to_datetime(x, unit="ms", utc=True).strftime("%Y-%m-%d")
    L = ["# FlashGold v5: exits per timeframe (walk-forward)", "",
         f"Data: {os.path.basename(a.csv)}, {base_ms // 60000}m candles. In-sample {d(t0)} to {d(t_split)}, "
         f"out-of-sample {d(t_split)} to {d(ms[-1])} (never used to choose).",
         f"{a.qty:g} contracts, costs {a.comm_pct:g}% per side + {a.slip_ticks} ticks. Filter off, default signal.",
         f"Grid per timeframe: stop {SL} ATR x target {TPR} R x {STYLES} x burst {BURST} = "
         f"{len(SL) * len(TPR) * len(STYLES) * len(BURST)} settings, scored worst case with costs.",
         "Chosen = best plateau (median of the cell and its stop/target neighbours) among cells with "
         f">= {a.min_trades} in-sample trades and both in-sample halves positive.", "",
         "| Chart | Eligible / tried | Chosen | IS trades, net, PF | OOS worst+costs: trades, net, PF, max DD | OOS halves | OOS no costs (TV fills) | Verdict |",
         "|---|---|---|---|---|---|---|---|"]
    for m, p, ne, nt in picks:
        tf = f"{m * base_ms // 60000}m"
        if p is None:
            L.append(f"| {tf} | 0 / {nt} | - | - | - | - | - | **none passes in-sample** |"); continue
        w = OOS[(m, True, True)]; n0 = OOS[(m, False, False)]
        ok = w["net"] > 0 and w["h1"] > 0 and w["h2"] > 0 and w["trades"] >= 20
        L.append(f"| {tf} | {ne} / {nt} | SL {p.sl:g} ATR, TP {p.tpr:g}R, {p['style']}, burst {p.burst:g} | "
                 f"{p.trades}, {p.net:.0f}, {p.pf:.2f} | {w['trades']}, {w['net']:.0f}, {w['pf']:.2f}, {w['maxdd']:.0f} | "
                 f"{w['h1']:.0f} / {w['h2']:.0f} | {n0['net']:.0f} | **{'holds' if ok else 'fails'}** |")
    L += ["", "**Verdict:** *holds* = out of sample, worst case with costs, net positive in both halves with >= 20 trades. "
          "*fails* = it does not. *none passes in-sample* = no setting was positive in both in-sample halves after costs.", "",
          f"How much data this is: about {(ms[-1] - t0) / 86400000:.0f} days scored, so the out-of-sample part is only "
          f"about {(ms[-1] - t_split) / 86400000:.0f} days of one market. A *holds* here means: keep testing it (new exports, "
          "other symbols, demo), not: trade it.", "",
          "The full in-sample grid is in the `_insample_grid.csv` next to this report."]
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
