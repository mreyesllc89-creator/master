"""v3.1 sweep: compare stop modes (ticks / ATR / percent), exits protected from the fill bar.
Stage A: enumerate all signal configs, dedupe identical trade-signal sets.
Stage B: every distinct signal set x every exit setting in each mode.
Stores per-combo monthly aggregates (n, sum bp, sum bp^2) for walk-forward analysis."""
import itertools, sys, time, hashlib, numpy as np, pandas as pd
from multiprocessing import Pool
from engine import *

TFSETS = {"all": (1, 1, 1, 1, 1), "no1m": (0, 1, 1, 1, 1), "15-60": (0, 0, 1, 1, 1), "60only": (0, 0, 0, 0, 1), "1-5": (1, 1, 0, 0, 0)}
DIVSETS = {"RB": (1, 0, 0, 0), "RB+RR": (1, 1, 0, 0), "all4": (1, 1, 1, 1), "none": (0, 0, 0, 0)}
LEVELS = {"off": None, "38/62": (38, 62), "30/70": (30, 70), "45/55": (45, 55)}
COMM = 0.0002
MONTHS = pd.period_range("2026-04", "2026-10", freq="M")

df = None
def init():
    global df; df = load_1m()


def sig_configs():
    out = []
    for tf, (L, R), (mn, mx), dh, dv, req4, lv, ts, fix in itertools.product(
            [1, 5, 15], [(3, 3), (5, 5), (8, 8)], [(5, 60), (10, 120)], [0, 13], DIVSETS, [False, True], LEVELS, TFSETS, [False, True]):
        if not req4 and not fix and ts != "all": continue
        if fix and ts == "all": continue
        out.append(dict(chart_tf=tf, divL=L, divR=R, divMin=mn, divMax=mx, dayH=dh, div=dv, req4=req4, levels=lv, tfs=ts, fix=fix))
    return out


def make_signals(cfg):
    d = DIVSETS[cfg["div"]]; lv = LEVELS[cfg["levels"]]
    return signals(df, chart_tf=cfg["chart_tf"], divL=cfg["divL"], divR=cfg["divR"], divMin=cfg["divMin"], divMax=cfg["divMax"],
                   dayH=cfg["dayH"], tfs_on=TFSETS[cfg["tfs"]], regBull=d[0], regBear=d[1], hidBull=d[2], hidBear=d[3],
                   req4=cfg["req4"], levels=lv is not None, buyLevel=lv[0] if lv else 38, sellLevel=lv[1] if lv else 62,
                   fix_toggles=cfg["fix"])


def stage_a(cfg):
    ch, L, S = make_signals(cfg)
    h = hashlib.md5(np.packbits(L).tobytes() + np.packbits(S).tobytes() + bytes([cfg["chart_tf"]])).hexdigest()
    return cfg, h, int(L.sum() + S.sum())


TRAILS = [None, (1.0, 0.5), (0.5, 0.25)]   # (activation, offset) as multiples of the SL distance
RMULT = [1, 1.5, 2, 3]

def exit_grid():
    g = []
    for sl, m, tr in itertools.product([200, 1000, 5000, 10000, 20000, 40000, 80000], [1, 2, 3], [None, (0.75, 0.25)]):
        g.append(("ticks", 0, sl, m, tr))                     # sl in ticks
    for atf, k, m, tr in itertools.product([0, 15, 60], [0.5, 1, 1.5, 2, 3, 5, 8, 12], RMULT, TRAILS):
        g.append(("atr", atf, k, m, tr))                       # sl = k * ATR(14) on atf (0 = chart)
    for p, m, tr in itertools.product([0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0], RMULT, TRAILS):
        g.append(("pct", 0, p, m, tr))                         # sl = p % of close
    return g


def stage_b(cfg):
    ch, L, S = make_signals(cfg)
    o, h, l, c = (ch[k].to_numpy() for k in "ohlc")
    month = ch.index.tz_convert(None).to_period("M")
    mi = np.searchsorted(MONTHS.asi8, month.asi8)
    atrs = {atf: atr_on_chart(df, ch, cfg["chart_tf"], atf, 14) for atf in (0, 15, 60)}
    one = np.ones(len(o))
    rows = []
    for mode, atf, x, m, tr in exit_grid():
        if mode == "ticks": base = one * x * TICK
        elif mode == "atr": base = atrs[atf] * x
        else: base = c * x / 100.0
        ut = tr is not None
        a, f = (base * tr[0], base * tr[1]) if ut else (base * 0, base * 0)
        for arm in ((True, False) if mode == "ticks" else (True,)):
            r, eb, sd = simulate_d(o, h, l, c, L, S, base, base * m, a, f, ut, arm, COMM)
            em = mi[eb]
            n = np.bincount(em, minlength=7); s1 = np.bincount(em, r, minlength=7); s2 = np.bincount(em, r * r, minlength=7)
            row = dict(cfg); row.update(mode=mode, atr_tf=atf, x=x, rmult=m, trail=ut,
                                        tr_act=tr[0] if ut else 0, tr_off=tr[1] if ut else 0, arm_on_fill=arm,
                                        n=n, s1=s1, s2=s2, win=(r > 0).mean() if r.size else np.nan)
            rows.append(row)
    return rows


if __name__ == "__main__":
    cfgs = sig_configs(); t = time.time()
    with Pool(4, initializer=init) as P:
        a = P.map(stage_a, cfgs, chunksize=8)
    A = pd.DataFrame([dict(c, h=h, nsig=n) for c, h, n in a])
    A.to_pickle("v31_stageA.pkl")
    D = A.drop_duplicates("h"); D = D[D.nsig >= 60]
    print(len(cfgs), "configs ->", A.h.nunique(), "distinct signal sets;", len(D), "with >=60 signals;", round(time.time() - t), "s", flush=True)
    with Pool(4, initializer=init) as P:
        res = [r for rows in P.imap_unordered(stage_b, D.drop(columns=["h", "nsig"]).to_dict("records"), chunksize=2) for r in rows]
    pd.DataFrame(res).to_pickle("v31_stageB.pkl"); print("done", len(res), round(time.time() - t), "s")
