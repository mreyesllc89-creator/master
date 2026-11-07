"""Stress-test finalist settings: fees, long/short, monthly, random-entry permutation, parameter neighbours."""
import numpy as np, pandas as pd
from engine import *
from sweep3 import TFSETS, DIVSETS, LEVELS
import sweep3

df = load_1m(); sweep3.df = df
BASE = dict(chart_tf=5, divL=5, divR=5, divMin=5, divMax=60, dayH=0, div="RB", req4=False, levels="off", tfs="all", fix=False)
FIN = {
    "A  5m defaults + day13, SL 8xATR(chart) TP2R": (dict(BASE, dayH=13), ("atr", 0, 8, 2, None)),
    "A' 5m defaults + day13, SL 5xATR(60m) TP2R": (dict(BASE, dayH=13), ("atr", 60, 5, 2, None)),
    "B  5m pure defaults, SL 5xATR(60m) TP2R": (dict(BASE), ("atr", 60, 5, 2, None)),
    "C  15m defaults, SL 5xATR(60m) TP2R": (dict(BASE, chart_tf=15), ("atr", 60, 5, 2, None)),
    "D  15m piv3 day13 all4 gated(no1m), SL 0.5xATR TP3R trail .5/.25": (
        dict(BASE, chart_tf=15, divL=3, divR=3, dayH=13, div="all4", tfs="no1m", fix=True), ("atr", 0, 0.5, 3, (0.5, 0.25))),
    "T  5m defaults, v3.0-style ticks 200/400 (protected)": (dict(BASE), ("ticks", 0, 200, 2, (0.75, 0.25))),
}
rng = np.random.default_rng(11)


def dist(ch, cfg, ex):
    mode, atf, x, m, tr = ex
    c = ch.c.to_numpy()
    base = (np.ones(len(c)) * x * TICK if mode == "ticks" else
            atr_on_chart(df, ch, cfg["chart_tf"], atf, 14) * x if mode == "atr" else c * x / 100)
    ut = tr is not None
    return base, base * m, (base * tr[0] if ut else base * 0), (base * tr[1] if ut else base * 0), ut


def run(cfg, ex, L=None, S=None, comm=0.0002):
    ch, L0, S0 = sweep3.make_signals(cfg)
    L = L0 if L is None else L; S = S0 if S is None else S
    o, h, l, c = (ch[k].to_numpy() for k in "ohlc")
    sl, tp, a, f, ut = dist(ch, cfg, ex)
    r, eb, sd = simulate_d(o, h, l, c, L, S, sl, tp, a, f, ut, True, comm)
    return ch, L0, S0, r, eb, sd


def tstat(r):
    return r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 2 else np.nan


def main():
    rows = []
    for name, (cfg, ex) in FIN.items():
        ch, L, S, r, eb, sd = run(cfg, ex)
        mon = ch.index[eb].tz_convert(None).to_period("M").astype(str)
        out = dict(setup=name, trades=len(r), win=100 * (r > 0).mean(), avg_bp=r.mean(), t=tstat(r),
                   pf=r[r > 0].sum() / -r[r < 0].sum(), long_bp=r[sd > 0].mean(), short_bp=r[sd < 0].mean(),
                   n_long=(sd > 0).sum(), n_short=(sd < 0).sum())
        for comm in (0.0, 0.0005):
            out[f"avg_bp@{comm * 100:.2f}%"] = run(cfg, ex, comm=comm)[3].mean()
        eq = np.cumsum(r); out["maxDD_bp"] = (np.maximum.accumulate(eq) - eq).max()
        m = pd.Series(r).groupby(mon).sum(); out["months+"] = f"{(m > 0).sum()}/{len(m)}"
        out["monthly_sum_bp"] = " ".join(f"{v:+.0f}" for v in m.values)
        # random entries: same count of long/short signals, same exits
        o_ = ch.c.to_numpy(); n = len(o_); rnd = []
        for _ in range(300):
            rL = np.zeros(n, bool); rS = np.zeros(n, bool)
            rL[rng.choice(n, L.sum(), replace=False)] = True; rS[rng.choice(n, S.sum(), replace=False)] = True
            rnd.append(run(cfg, ex, rL, rS)[3].mean())
        rnd = np.array(rnd); out["random_avg_bp"] = rnd.mean(); out["p_random>=real"] = (rnd >= r.mean()).mean()
        rows.append(out)
        print(name, "done", flush=True)

    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    R = pd.DataFrame(rows).set_index("setup").round(2)
    print(R.T.to_string())

    print("\n=== Neighbourhood of the ATR(60m) plateau, 5m defaults (dayH 0 / 13), avg bp | trades ===")
    for dh in (0, 13):
        tab = {}
        for k in (3, 4, 5, 6, 8):
            for m in (1.5, 2, 3):
                for tr in (None, (1.0, 0.5)):
                    _, _, _, r, _, _ = run(dict(BASE, dayH=dh), ("atr", 60, k, m, tr))
                    tab[(k, f"TP{m}R" + ("+trail" if tr else ""))] = f"{r.mean():+.1f} | {len(r)}"
        print(f"\nday start {dh:02d}:00 UTC"); print(pd.Series(tab).unstack().to_string())



if __name__ == "__main__":
    main()