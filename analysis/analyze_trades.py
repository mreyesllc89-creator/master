"""Per-file statistics for the TradingView "List of trades" exports in data/backtests.

Usage: python3 analysis/analyze_trades.py [round_trip_cost_usd]
The optional argument is the cost subtracted from every trade (default 1.24 = 0.62 commission x 2 sides).
"""
import csv, sys, glob, os
from collections import defaultdict, Counter
from datetime import datetime

import pathlib
U = str(pathlib.Path(__file__).resolve().parent.parent / "data" / "backtests")

def load(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    trades = {}
    for r in rows:
        n = int(r["Trade number"]); t = trades.setdefault(n, {})
        typ = r["Type"]
        if r["Date and time"] in ("", "Open") or r["Signal"]=="Open": continue
        raw=r["Date and time"]; dt = datetime.strptime(raw, "%Y-%m-%d %H:%M") if ":" in raw else datetime.strptime(raw, "%Y-%m-%d")
        if typ.startswith("Entry"):
            t["side"] = "long" if "long" in typ else "short"
            t["entry_time"] = dt; t["entry_price"] = float(r["Price USD"]); t["entry_sig"] = r["Signal"]
        else:
            t["exit_time"] = dt; t["exit_price"] = float(r["Price USD"]); t["exit_sig"] = r["Signal"]
        t["pnl"] = float(r["Net PnL USD"]); t["comm"] = float(r["Commission USD"] or 0)
        t["bars"] = int(r["Duration (bars)"] or 0); t["qty"] = float(r["Size (qty)"])
        t["mfe"] = float(r["Favorable excursion USD"] or 0); t["mae"] = float(r["Adverse excursion USD"] or 0)
    out = [t for n, t in sorted(trades.items()) if "entry_time" in t and "exit_time" in t]
    return out

def infer_tf(trades):
    diffs = [ (t["exit_time"]-t["entry_time"]).total_seconds()/60/t["bars"] for t in trades if t["bars"]>0 and t["exit_time"]>t["entry_time"] and (t["exit_time"]-t["entry_time"]).total_seconds()/60/t["bars"]<=1440]
    c = Counter(round(d) for d in diffs)
    return c.most_common(1)[0][0] if c else None

def maxdd(pnls):
    peak=cum=0; dd=0
    for p in pnls:
        cum+=p; peak=max(peak,cum); dd=min(dd,cum-peak)
    return dd

def pf(pnls):
    g=sum(p for p in pnls if p>0); l=-sum(p for p in pnls if p<0)
    return g/l if l else float("inf")

def summarize(name, tr, rt_cost):
    pnls=[t["pnl"] for t in tr]
    n=len(pnls); wins=[p for p in pnls if p>0]; losses=[p for p in pnls if p<0]
    net=sum(pnls)
    print(f"\n{'='*100}\n{name}")
    print(f"  timeframe ~{infer_tf(tr)}m | trades {n} | {tr[0]['entry_time']:%Y-%m-%d} -> {tr[-1]['exit_time']:%Y-%m-%d}")
    print(f"  net ${net:,.2f} | win% {100*len(wins)/n:.1f} | PF {pf(pnls):.2f} | avg/trade ${net/n:.3f} | avg win ${sum(wins)/max(1,len(wins)):.2f} | avg loss ${sum(losses)/max(1,len(losses)):.2f} | maxDD ${maxdd(pnls):,.2f} | commission col total ${sum(t['comm'] for t in tr):.2f}")
    adj=[p-rt_cost for p in pnls]
    print(f"  after ${rt_cost:.2f}/round-trip cost: net ${sum(adj):,.2f} | PF {pf(adj):.2f} | win% {100*sum(1 for p in adj if p>0)/n:.1f} | maxDD ${maxdd(adj):,.2f}")
    # sides
    for s in ("long","short"):
        ps=[t["pnl"] for t in tr if t["side"]==s]
        if ps: print(f"  {s:5s}: n={len(ps):5d} net ${sum(ps):9.2f} PF {pf(ps):.2f} win% {100*sum(1 for p in ps if p>0)/len(ps):.1f}")
    # exit reason
    print("  exit reasons:")
    by=defaultdict(list)
    for t in tr: by[t["exit_sig"]].append(t["pnl"])
    for k,v in sorted(by.items(), key=lambda kv:-len(kv[1])):
        print(f"    {k:15s} n={len(v):5d} net ${sum(v):9.2f} avg ${sum(v)/len(v):7.3f} win% {100*sum(1 for p in v if p>0)/len(v):.1f}")
    # duration
    print("  duration (bars):")
    by=defaultdict(list)
    for t in tr: by[min(t["bars"],5)].append(t["pnl"])
    for k in sorted(by):
        v=by[k]; print(f"    {str(k)+('+' if k==5 else ''):4s} n={len(v):5d} net ${sum(v):9.2f} avg ${sum(v)/len(v):7.3f} win% {100*sum(1 for p in v if p>0)/len(v):.1f}")
    # hour of day
    print("  entry hour (export clock):")
    by=defaultdict(list)
    for t in tr: by[t["entry_time"].hour].append(t["pnl"])
    for k in sorted(by):
        v=by[k]; print(f"    {k:02d}: n={len(v):5d} net ${sum(v):9.2f} avg ${sum(v)/len(v):7.3f}")
    hhmm=[t["entry_time"].hour*100+t["entry_time"].minute for t in tr]
    print(f"  entry time range: {min(hhmm):04d} - {max(hhmm):04d}; exits range: {min(t['exit_time'].hour*100+t['exit_time'].minute for t in tr):04d} - {max(t['exit_time'].hour*100+t['exit_time'].minute for t in tr):04d}")
    dow=Counter(t["entry_time"].strftime('%a') for t in tr); print(f"  weekdays: {dict(dow)}")
    # monthly
    print("  monthly net:")
    by=defaultdict(list)
    for t in tr: by[t["exit_time"].strftime('%Y-%m')].append(t["pnl"])
    print("    "+"  ".join(f"{k}:{sum(v):+.0f}" for k,v in sorted(by.items())))
    # top contributions
    srt=sorted(pnls)
    print(f"  worst 5: {[round(p,2) for p in srt[:5]]} best 5: {[round(p,2) for p in srt[-5:]]}")
    print(f"  top 5% of trades contribute ${sum(srt[-max(1,n//20):]):,.2f} of ${net:,.2f}")
    # MFE/MAE
    print(f"  avg MFE ${sum(t['mfe'] for t in tr)/n:.3f} avg MAE ${sum(t['mae'] for t in tr)/n:.3f}")
    w=[t for t in tr if t["pnl"]>0]
    close_to_mfe=sum(1 for t in w if t["mfe"]-t["pnl"] <= max(0.05, 0.1*t["mfe"]))
    print(f"  winners whose PnL is within 10% (or $0.05) of their MFE: {close_to_mfe}/{len(w)} = {100*close_to_mfe/max(1,len(w)):.1f}%  | avg win/avg MFE(winners) = {sum(t['pnl'] for t in w)/max(1e-9,sum(t['mfe'] for t in w)):.2f}")
    pts=[abs(t["exit_price"]-t["entry_price"]) for t in w]
    print(f"  median winner size in gold points: {sorted(pts)[len(pts)//2]:.3f}")
    # price move per trade in points (for cost sanity)
    return dict(name=name, tf=infer_tf(tr), n=n, net=net, pf=pf(pnls), win=100*len(wins)/n, dd=maxdd(pnls), adjnet=sum(adj), adjpf=pf(adj), avg=net/n)

if __name__ == "__main__":
    rt=float(sys.argv[1]) if len(sys.argv)>1 else 1.24
    res=[]
    import hashlib
    seen=set()
    for p in sorted(glob.glob(U+"/GVLiveV2_*.csv")):
        h=hashlib.md5(open(p,"rb").read()).hexdigest()
        if h in seen: continue
        seen.add(h)
        tr=load(p)
        res.append(summarize(os.path.basename(p), tr, rt))
    print("\n\nSUMMARY (round-trip cost $%.2f)"%rt)
    print(f"{'file':60s} {'tf':>4s} {'n':>6s} {'net':>9s} {'PF':>5s} {'win%':>5s} {'maxDD':>9s} {'avg':>7s} {'net-cost':>9s} {'PF-cost':>7s}")
    for r in sorted(res,key=lambda r:r['tf'] or 0):
        print(f"{r['name'][:60]:60s} {r['tf']:>4} {r['n']:6d} {r['net']:9.0f} {r['pf']:5.2f} {r['win']:5.1f} {r['dd']:9.0f} {r['avg']:7.3f} {r['adjnet']:9.0f} {r['adjpf']:7.2f}")
