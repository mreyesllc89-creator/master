import itertools, json, sys, statistics
from sim import *
ACT = [0, 25, 50, 100, 150, 200, 300, 400, 600, 800, 1200, 1600]
DIS = [25, 50, 75, 100, 150, 200, 300, 400, 600]
SL  = [150, 250, 350, 500, 750, 1000, 1500, 2500]
FEE = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
def atr(d, L=14):
    tr = [d["h"][0]-d["l"][0]] + [max(d["h"][i]-d["l"][i], abs(d["h"][i]-d["c"][i-1]), abs(d["l"][i]-d["c"][i-1])) for i in range(1, len(d["c"]))]
    return statistics.median(tr[150:])
def st2(d, sl, act, dis, lo=150, hi=None):
    out = []
    for cons in (False, True):
        tr = backtest(d, sl*10, 50000, act*10, dis*10, fee=FEE, start=lo, cons=cons)
        if hi is not None: tr = [t for t in tr if t[2] < hi]
        out.append(stats(tr))
    return out
def sc(pair, minN):
    v = []
    for s in pair:
        if s["n"] < minN or s["net"] <= 0: v.append(-1 if s["n"] >= minN else -2); continue
        v.append(min(s["pf"], 5) * s["net"]/max(s["dd"], 50))
    return min(v)
def pick(res, minN):
    def rob(k):
        return statistics.median(sc(res[kk], minN) for kk in [(k[0]+x, k[1]+y, k[2]+z) for x, y, z in itertools.product((-1,0,1), repeat=3)] if kk in res)
    return max(res, key=rob)
F = lambda s: f"n={s['n']:3d} PF={s['pf']:5.2f} net=${s['net']:7.0f} DD=${s['dd']:5.0f} WR={s['wr']:.0%}"
summary = {}
for name in FILES:
    d = prepared(name); n = len(d["c"]); cut = 150 + int((n-150)*0.6)
    res = {k: st2(d, SL[k[2]], ACT[k[0]], DIS[k[1]]) for k in itertools.product(range(len(ACT)), range(len(DIS)), range(len(SL)))}
    b = pick(res, 15); a, di, s = b
    resI = {k: st2(d, SL[k[2]], ACT[k[0]], DIS[k[1]], hi=cut) for k in res}
    bi = pick(resI, 8)
    oos = st2(d, SL[bi[2]], ACT[bi[0]], DIS[bi[1]], lo=cut)
    dflt = st2(d, 500, 150, 10)
    A = atr(d)
    print(f"\n== {name}  fee {FEE*100:.3f}%/side  qty 1 BTC  median bar range ${A:.0f}   [OHLC model | conservative model]")
    print(f"  default SL500 act150 dist10     : {F(dflt[0])} | {F(dflt[1])}")
    print(f"  CALIBRATED SL{SL[s]} act{ACT[a]} dist{DIS[di]} : {F(res[b][0])} | {F(res[b][1])}")
    print(f"     = SL {SL[s]/A:.1f}x  act {ACT[a]/A:.1f}x  dist {DIS[di]/A:.1f}x bar range")
    print(f"  walk-forward: picked on first 60% -> SL{SL[bi[2]]} act{ACT[bi[0]]} dist{DIS[bi[1]]}; last 40%: {F(oos[0])} | {F(oos[1])}")
    summary[name] = dict(sl=SL[s], act=ACT[a], dist=DIS[di], rng=A, std=res[b][0], cons=res[b][1], dflt=dflt, wf=dict(sl=SL[bi[2]], act=ACT[bi[0]], dist=DIS[bi[1]], oos=oos))
json.dump(summary, open(f"calibration_fee{FEE}.json", "w"), indent=1)
