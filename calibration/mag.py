from sim import *
from datetime import datetime
def mpaths(d, m1, tfmin):
    idx = {}
    for j, t in enumerate(m1["t"]):
        idx[datetime.fromisoformat(t)] = j
    paths = {}; first = None
    for i, t in enumerate(d["t"]):
        T = datetime.fromisoformat(t); pts = []
        from datetime import timedelta
        js = [idx.get(T + timedelta(minutes=k)) for k in range(tfmin)]
        if any(j is None for j in js): continue
        for j in js:
            o,h,l,c = m1["o"][j],m1["h"][j],m1["l"][j],m1["c"][j]
            sub = [o,h,l,c] if abs(h-o) < abs(l-o) else [o,l,h,c]
            pts += sub if not pts else sub
        # anchor to HTF open/close
        pts[0] = d["o"][i]; pts[-1] = d["c"][i]
        paths[i] = pts
        if first is None: first = i
    return paths, first
m1 = load(UP+FILES["1m BYBIT"])
if __name__ == "__main__":
  for name, tf in [("5m BYBIT",5),("15m BYBIT",15),("60m OKX",60)]:
    d = prepared(name); P, st = mpaths(d, m1, tf)
    print(f"== {name}: 1m-covered bars {len(P)} from {d['t'][st]}")
    for (sl,act,dis) in [(500,150,10),(500,0,10),(500,100,50),(500,200,100),(500,300,150),(750,400,200),(1000,600,300)]:
        r = [stats(backtest(d,sl*10,50000,act*10,dis*10,start=st,**kw)) for kw in (dict(), dict(cons=True), dict(paths=P))]
        print(f"  SL{sl} act{act} dist{dis}: " + " | ".join(f"{lab} n={x['n']} PF={x['pf']:.2f} net={x['net']:.0f}" for lab,x in zip(("OHLC","CONS","1m-MAG"),r)))
