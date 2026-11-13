"""15m optimisation, exits simulated on 1-minute bars (no intrabar path assumption).
Ungated signal sets only (gating showed no benefit in opt15), reduced exit grid."""
import itertools, time, hashlib, pickle, numpy as np, pandas as pd
from multiprocessing import Pool
from engine import *
import opt15
from opt15 import MONTHS, NM, COMM, LEVELS

def exit_grid():
    g = []
    TR = [None, (1.0, 0.5), (0.5, 0.25)]
    for atf, k, m, tr in itertools.product([0, 60, 240], [1, 2, 3, 5, 8, 12], [1, 2, 3, 4], TR):
        if atf == 240 and k > 5: continue
        g.append(("atr", atf, k, m, tr))
    for p, m, tr in itertools.product([0.5, 1.0, 2.0, 3.0], [1, 2, 3, 4], TR):
        g.append(("pct", 0, p, m, tr))
    return g
EXITS = exit_grid()

def sig_configs():
    return [dict(divL=L, divR=L, divMin=mn, divMax=mx, dayH=dh, div="RB", req4=False, levels=lv, tfs="all", fix=False)
            for L, (mn, mx), dh, lv in itertools.product([3, 4, 5, 6, 8], [(5, 60), (10, 120)], list(range(0, 24, 2)) + [13], LEVELS)]

G = {}
def init():
    df = load_1m(); opt15.df = df
    G["df"] = df; G["ohlc"] = tuple(df[k].to_numpy() for k in "ohlc"); G["t1"] = df.index.values.astype("int64")
    G["mi"] = np.searchsorted(MONTHS.asi8, df.index.tz_convert(None).to_period("M").asi8)

def work(cfg):
    df = G["df"]; o1, h1, l1, c1 = G["ohlc"]; n1 = len(o1)
    ch, L, S = opt15.make_signals(cfg)
    pos = np.searchsorted(G["t1"], ch.index.values.astype("int64") + 15 * 60_000_000_000) - 1
    L1 = np.zeros(n1, bool); S1b = np.zeros(n1, bool); L1[pos[L]] = True; S1b[pos[S]] = True
    c = ch.c.to_numpy(); atrs = {a: atr_on_chart(df, ch, 15, a, 14) for a in (0, 60, 240)}
    N = np.zeros((len(EXITS), NM), np.int16); S1 = np.zeros((len(EXITS), NM), np.float32); S2 = np.zeros((len(EXITS), NM), np.float32)
    B = np.full(n1, np.nan); zero = np.zeros(n1)
    for e, (mode, atf, x, m, tr) in enumerate(EXITS):
        B[pos] = atrs[atf] * x if mode == "atr" else c * x / 100.0
        ut = tr is not None
        r, eb, sd = simulate_d(o1, h1, l1, c1, L1, S1b, B, B * m, B * tr[0] if ut else zero, B * tr[1] if ut else zero, ut, True, COMM)
        em = G["mi"][eb]
        N[e] = np.bincount(em, minlength=NM); S1[e] = np.bincount(em, r, minlength=NM); S2[e] = np.bincount(em, r * r, minlength=NM)
    return hashlib.md5(np.packbits(L).tobytes() + np.packbits(S).tobytes()).hexdigest(), int(L.sum() + S.sum()), N, S1, S2

if __name__ == "__main__":
    cfgs = sig_configs(); t = time.time(); print(len(cfgs), "signal configs x", len(EXITS), "exits", flush=True)
    with Pool(4, initializer=init) as P:
        res = P.map(work, cfgs, chunksize=2)
    D = pd.DataFrame(cfgs); D["h"] = [r[0] for r in res]; D["nsig"] = [r[1] for r in res]
    keep = (~D.h.duplicated()) & (D.nsig >= 200)
    idx = np.where(keep)[0]
    np.savez_compressed("opt15m.npz", N=np.stack([res[i][2] for i in idx]), S1=np.stack([res[i][3] for i in idx]), S2=np.stack([res[i][4] for i in idx]))
    D[keep].reset_index(drop=True).to_pickle("opt15m_sig.pkl"); pickle.dump(EXITS, open("opt15m_exits.pkl", "wb"))
    print("done", keep.sum(), "signal sets,", keep.sum() * len(EXITS), "backtests", round(time.time() - t), "s")
