"""EVK command line.

  python -m evk analyze RUN.csv [--split 2026-01-01] [--value auto|r|profit]
                        [--criterion min_period_pf|pf|net|expectancy|net_over_dd]
                        [--min-trades 30] [--no-smooth] [--train 6] [--test 2] [--anchored]
                        [--compare OTHER.csv --labels "Without,With"] [--out report.html]
"""
import argparse
import os
import sys

import pandas as pd

from . import analyze as A
from .io import load
from .report import build


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m evk", description="EA Validation Kit analysis")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="hold-out, walk-forward, robustness and stress tests of one run")
    a.add_argument("csv")
    a.add_argument("--split", help="hold-out start date YYYY-MM-DD (default: last 25%% of the period)")
    a.add_argument("--value", default="auto", choices=["auto", "r", "profit"],
                   help="trade result unit: R (needs a stop loss) or money; auto picks R when available")
    a.add_argument("--criterion", default="min_period_pf",
                   choices=["min_period_pf", "pf", "net", "expectancy", "net_over_dd"])
    a.add_argument("--min-trades", type=int, default=30, help="minimum in-sample trades to rank a pass")
    a.add_argument("--no-smooth", action="store_true", help="rank by the pass alone, not its neighbourhood median")
    a.add_argument("--train", type=int, default=6, help="walk-forward training window, months")
    a.add_argument("--test", type=int, default=2, help="walk-forward test window, months")
    a.add_argument("--anchored", action="store_true", help="walk-forward training always starts at the beginning")
    a.add_argument("--compare", help="second run with the same optimized inputs (e.g. filter on)")
    a.add_argument("--labels", default="A,B", help="names for the run and the --compare run")
    a.add_argument("--out", help="HTML report path (default: next to the CSV)")
    args = ap.parse_args(argv)

    run = load(args.csv)
    if run.trades.empty:
        sys.exit("No trades in the file.")
    t0, t1 = run.trades.close_time.min(), run.trades.close_time.max()
    split = pd.Timestamp(args.split) if args.split else (t0 + (t1 - t0) * 0.75).normalize()
    v = run.value_col(args.value)
    print(f"{run.meta}\n{len(run.passes)} passes, {len(run.trades)} trades, {t0.date()} .. {t1.date()}, unit {v}")
    print(f"optimized inputs: {', '.join(c[2:] for c in run.varying) or 'none'}")

    ho = A.holdout(run, args.value, split, args.criterion, args.min_trades, smooth=not args.no_smooth)
    print(f"\nHOLD-OUT (choose before {split.date()}, test after): base rate {ho['base_rate']:.0%} of passes profitable")
    for r in ho["topk"]:
        print(f"  top {r['k']:>2}: median OOS PF {r['oos_pf_median']:.2f}, profitable {r['oos_profitable']:.0%}")
    if ho["chosen"] is not None:
        row = ho["table"].loc[ho["chosen"]]
        print(f"  chosen: {run.label(ho['chosen'])}\n          IS PF {row.is_pf:.2f} ({row.is_trades:.0f} tr) -> OOS PF {row.oos_pf:.2f} ({row.oos_trades:.0f} tr)")

    wf = A.walkforward(run, args.value, args.train, args.test, args.criterion,
                       max(5, args.min_trades * args.train // 12), smooth=not args.no_smooth, anchored=args.anchored)
    o = wf["oos"]
    print(f"\nWALK-FORWARD ({args.train}m train / {args.test}m test): {o['trades']} OOS trades, PF {o['pf']:.2f}, net {o['net']:.2f}")

    st = A.stress(run.trades[run.trades["pass"] == ho["chosen"]][v]) if ho["chosen"] is not None else {}
    cmp = None
    if args.compare:
        la, lb = (args.labels.split(",") + ["B"])[:2]
        cmp = A.compare(run, load(args.compare), args.value, la.strip(), lb.strip())
        if "pf_a" in cmp:
            print(f"\nCOMPARE {la} vs {lb}: {cmp['used']} pairs, median PF {cmp['pf_a']:.2f} -> {cmp['pf_b']:.2f}, "
                  f"{lb} better PF in {cmp['share_pf_up']:.0%}, better net in {cmp['share_net_up']:.0%}")

    out = args.out or os.path.splitext(args.csv)[0] + "_report.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(build(run, args.value, ho, wf, st, cmp))
    print(f"\nreport: {out}")


if __name__ == "__main__":
    main()
