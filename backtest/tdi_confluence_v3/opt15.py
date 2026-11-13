"""15m-chart input optimisation on 2 years (Nov 2024 - Nov 12 2026).
Stage A: enumerate signal inputs, dedupe identical signal sets.
Stage B: each distinct signal set x exit grid; store per-month (n, sum bp, sum bp^2)."""
import itertools, time, hashlib, numpy as np, pandas as pd
from multiprocessing import Pool
from engine import *

CHART = 15
TFSETS = {"all": (1, 1, 1, 1, 1), "no1m": (0, 1, 1, 1, 1), "15-60": (0, 0, 1, 1, 1), "60only": (0, 0, 0, 0, 1), "1-5": (1, 1, 0, 0, 0)}
DIVSETS = {"RB": (1, 0, 0, 0), "RB+RR": (1, 1, 0, 0), "all4": (1, 1, 1, 1), "none": (0, 0, 0, 0)}
LEVELS = {"off": None, "30/70": (30, 70), "35/65": (35, 65), "38/62": (38, 62), "42/58": (42, 58), "45/55": (45, 55)}
COMM = 0.0002
MONTHS = pd.period_range("2024-11", "2026-11", freq="M")
NM = len(MONTHS)
df = None
def init():
    global df; df = load_1m()

def sig_configs():
    out = []
    for L, (mn, mx), dh, dv, req4, lv, ts, fix in itertools.product(
            [3, 4, 5, 6, 8], [(5, 60), (10, 120)], range(0, 24, 2), DIVSETS, [False, True], LEVELS, TFSETS, [False, True]):
        if not req4 and not fix and (ts != "all" or dv != "RB"): continue   # toggles irrelevant as written
        if fix and ts == "all" and dv == "RB": continue
        out.append(dict(divL=L, divR=L, divMin=mn, divMax=mx, dayH=dh, div=dv, req4=req4, levels=lv, tfs=ts, fix=fix))
    # 13:00 (current default) as an extra hour
    out += [dict(c, dayH=13) for c in out if c["dayH"] == 12]
    return out

def make_signals(cfg):
    d = DIVSETS[cfg["div"]]; lv = LEVELS[cfg["levels"]]
    return signals(df, chart_tf=CHART, divL=cfg["divL"], divR=cfg["divR"], divMin=cfg["divMin"], divMax=cfg["divMax"],
                   dayH=cfg["dayH"], tfs_on=TFSETS[cfg["tfs"]], regBull=d[0], regBear=d[1], hidBull=d[2], hidBear=d[3],
                   req4=cfg["req4"], levels=lv is not None, buyLevel=lv[0] if lv else 38, sellLevel=lv[1] if lv else 62,
                   fix_toggles=cfg["fix"])

def stage_a(cfg):
    ch, L, S = make_signals(cfg)
    return hashlib.md5(np.packbits(L).tobytes() + np.packbits(S).tobytes()).hexdigest(), int(L.sum() + S.sum())

TRAILS = [None, (1.0, 0.5), (0.5, 0.25)]
RMULT = [1, 1.5, 2, 3, 4]
def exit_grid():
    g = []
    for atf, k, m, tr in itertools.product([0, 60, 240], [1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12], RMULT, TRAILS):
        if atf == 240 and k > 6: continue
        g.append(("atr", atf, k, m, tr))
    for p, m, tr in itertools.product([0.5, 0.75, 1.0, 1.5, 2.0, 3.0], RMULT, TRAILS):
        g.append(("pct", 0, p, m, tr))
    return g
EXITS = exit_grid()

def stage_b(cfg):
    ch, L, S = make_signals(cfg)
    o, h, l, c = (ch[k].to_numpy() for k in "ohlc")
    mi = np.searchsorted(MONTHS.asi8, ch.index.tz_convert(None).to_period("M").asi8)
    atrs = {atf: atr_on_chart(df, ch, CHART, atf, 14) for atf in (0, 60, 240)}
    N = np.zeros((len(EXITS), NM), np.int16); S1 = np.zeros((len(EXITS), NM), np.float32); S2 = np.zeros((len(EXITS), NM), np.float32)
    for e, (mode, atf, x, m, tr) in enumerate(EXITS):
        base = atrs[atf] * x if mode == "atr" else c * x / 100.0
        ut = tr is not None
        a, f = (base * tr[0], base * tr[1]) if ut else (base * 0, base * 0)
        r, eb, sd = simulate_d(o, h, l, c, L, S, base, base * m, a, f, ut, True, COMM)
        em = mi[eb]
        N[e] = np.bincount(em, minlength=NM); S1[e] = np.bincount(em, r, minlength=NM); S2[e] = np.bincount(em, r * r, minlength=NM)
    return N, S1, S2

if __name__ == "__main__":
    cfgs = sig_configs(); t = time.time()
    with Pool(4, initializer=init) as P:
        a = P.map(stage_a, cfgs, chunksize=16)
    A = pd.DataFrame(cfgs); A["h"] = [x[0] for x in a]; A["nsig"] = [x[1] for x in a]
    D = A.drop_duplicates("h"); D = D[D.nsig >= 200].reset_index(drop=True)
    print(len(cfgs), "configs ->", A.h.nunique(), "distinct;", len(D), "with >=200 signals;", round(time.time() - t), "s", flush=True)
    with Pool(4, initializer=init) as P:
        res = P.map(stage_b, D.drop(columns=["h", "nsig"]).to_dict("records"), chunksize=4)
    np.savez_compressed("opt15.npz", N=np.stack([r[0] for r in res]), S1=np.stack([r[1] for r in res]), S2=np.stack([r[2] for r in res]))
    D.to_pickle("opt15_sig.pkl"); print("done", len(D) * len(EXITS), "backtests", round(time.time() - t), "s")
