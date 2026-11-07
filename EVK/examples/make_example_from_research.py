#!/usr/bin/env python3
"""Build example EVK files from the XLZC Python research engine, in exactly the format
EVK.mqh writes, so the Python tool can be tested without MetaTrader.

  python3 EVK/examples/make_example_from_research.py <data_dir> <out_dir>

Writes  xlzc_m2h1_off.csv  (81 passes, no filter)  and  xlzc_m2h1_fgf.csv  (same passes,
FlashGold defaults). Each trade risks 100 account-currency units, so profit = 100 * R.
"""
import itertools
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "research"))
import fgf_backtest as FB  # noqa: E402
import xlzc_calibrate as C  # noqa: E402

RISK = 100.0


class NoCache(dict):
    def get(self, *a, **k):
        return None


def write(path, rows, names):
    with open(path, "w") as f:
        f.write("# EVK 1.0 | XAUUSD_M1_LiquidityZeroCross_Bearish (research replica) | XAUUSD | USD | "
                "times are broker server time\n")
        f.write("pass,criterion," + ",".join("p." + n for n in names) +
                ",open_time,close_time,side,volume,entry,exit,sl,profit,risk,r,magic\n")
        for pid, params, trades in rows:
            pre = f"{pid},0," + ",".join(str(params[n]) for n in names)
            if not trades:
                f.write(pre + ",,,,,,,,,,,\n")
            for ot, ct, r in trades:
                f.write(f"{pre},{ot},{ct},sell,1.00,0,0,0,{r * RISK:.2f},{RISK:.2f},{r:.4f},20261112\n")


def main():
    data_dir, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    p = FB.prepare(data_dir, ["M2/H1"])
    FB.init_worker(p)
    path = p["path"]
    exits = []
    orig = path.simulate

    def sim(*a, **k):
        res = orig(*a, **k)
        exits.append(res[0])
        return res
    path.simulate = sim
    C.G["cache"] = NoCache()
    fgf_mask = FB.fgf_mask(FB.cfg_from_label(FB.DEFAULT_LABEL), "M2/H1", {})
    names = ["LiquidityLookbackBars", "SwingStrength", "SL_Buffer_Points", "MinRewardRisk"]
    grid = list(itertools.product([15, 25, 40], [2, 3, 4], [40, 80, 120], [1.0, 1.5, 2.0]))
    for tag, mask in (("off", None), ("fgf", fgf_mask)):
        rows = []
        for pid, (N, S, buf, rr) in enumerate(grid, start=1):
            cfg = dict(tf="M2/H1", N=N, S=S, buffer=buf, NT=120, min_rr=rr, fb=1.5, stoch="soft",
                       session="ny_12-1630", trail=True)
            exits.clear()
            tr = FB.run_with_mask(cfg, mask)
            assert len(exits) == len(tr)
            to_s = lambda t: int(np.datetime64(t, "s").astype(np.int64))
            trades = [(to_s(et), to_s(path.t[xi]), r) for (et, r), xi in zip(tr, exits)]
            rows.append((pid, dict(zip(names, (N, S, round(buf * 2 ** 0.5), rr))), trades))
        write(os.path.join(out, f"xlzc_m2h1_{tag}.csv"), rows, names)
        print(tag, len(rows), "passes", sum(len(r[2]) for r in rows), "trades")


if __name__ == "__main__":
    main()
