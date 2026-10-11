"""Direction accuracy of each part of the entry logic used as a held direction (no burst needed):
zone permission (parent TDI side + child zones aligned), parent TDI direction, FDF structure direction, the
signal-held direction, the level side (the existing filter) and the signal-held direction reversed."""
import sys
import numpy as np
import pandas as pd
import fgengine as E
import fgrun as R
from calib import zones_for, IS_END
from dir_stage2 import hold_dir, metrics

OUT = "results_dir"


def run(tf, S):
    split = int(IS_END.timestamp())
    rows = []
    ch = S.bars(tf)

    def add(name, d, **kw):
        r = dict(source=name, **kw)
        r.update(metrics(ch["c"], d.astype(np.int8), ch["t_open"], split, warm=300))
        rows.append(r)

    for pm in (1, 2, 4, 8):
        for ma in (0, 1, 2, 3):
            p = R.params(parent_tf=tf * pm, zones=zones_for(tf, 0), min_aligned=ma, burst_atr=0.5, fd_tf=tf)
            ctx = R.context(S, tf, p)
            zb, zs = ctx["zbuy"], ctx["zsell"]
            add("zone permission", np.where(zb & ~zs, 1, np.where(zs & ~zb, -1, 0)), pm=pm, ma=ma)
            if ma == 0:
                add("parent TDI direction", ctx["pside"], pm=pm, ma=-1)
            if ma == 2:
                d0, lv, sd, age = hold_dir(ch["c"], ctx["atr14"], ctx["buy"], ctx["sell"], ctx["bpx"], ctx["spx"], 0, 0.0)
                add("signal held", d0, pm=pm, ma=ma)
                add("signal held, reversed", -d0, pm=pm, ma=ma)
                d2, *_ = hold_dir(ch["c"], ctx["atr14"], ctx["buy"], ctx["sell"], ctx["bpx"], ctx["spx"], 2, 0.0)
                add("level side (filter now)", d2, pm=pm, ma=ma)
    for fm in (1, 2, 4, 8):
        p = R.params(fd_tf=tf * fm)
        ctx = R.context(S, tf, p)
        add("FDF structure direction", ctx["fdir"], pm=-1, ma=-1, fm=fm)
    D = pd.DataFrame(rows)
    D["tf"] = tf
    D.to_parquet(f"{OUT}/DS_{tf}.parquet")
    return D


if __name__ == "__main__":
    tf = int(sys.argv[1])
    S = R.Source(pd.read_parquet("btc_1m.parquet"), 1)
    run(tf, S)
    print("DS done", tf)
