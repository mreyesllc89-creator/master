import re, html, os, sys, glob
import numpy as np, pandas as pd
sys.path.insert(0,"/workspace/master/research"); os.environ["HUMP_SPACE"]="2"
import hump_engine as H, hump_search as X
RES="/tmp/claude-0/-workspace-master/53e0ea5b-b347-50b9-8f48-3f5cae086c17/scratchpad/lomares/Loma-preset-results"
def deals(path):
    raw=open(path,"rb").read(); txt=raw.decode("utf-16")
    i=txt.find("Deals"); out=[]
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>",txt[i:],flags=re.S):
        c=[html.unescape(re.sub(r"<[^>]+>","",x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>",r,flags=re.S)]
        if len(c)>=13 and re.match(r"\d{4}\.\d\d\.\d\d \d\d:\d\d:\d\d",c[0]) and c[3] in("buy","sell"): out.append(c)
    d=pd.DataFrame(out,columns=["time","deal","sym","type","dir","vol","price","order","comm","swap","profit","bal","comment"])
    d["time"]=pd.to_datetime(d.time,format="%Y.%m.%d %H:%M:%S")
    for k in("vol","price","comm","swap","profit"): d[k]=d[k].str.replace(" ","").astype(float)
    tr=[]; ins=d[d.dir=="in"].reset_index(drop=True); outs=d[d.dir=="out"].reset_index(drop=True)
    for a,b in zip(ins.itertuples(),outs.itertuples()):
        side=1 if a.type=="buy" else -1
        sl=None
        tr.append(dict(entry=a.time,side=side,entry_px=a.price,exit=b.time,exit_px=b.price,pnl=b.profit+a.comm+b.comm+b.swap,gross=b.profit,why=b.comment.split(" ")[0] if b.comment else "close",vol=a.vol))
    return pd.DataFrame(tr)
pool=pd.read_csv("results/hump_pool_ranked.csv").sort_values("allround",ascending=False).drop_duplicates("fam").head(10).reset_index(drop=True)
mk=H.Market()
pf=lambda x:(x[x>0].sum()/-x[x<0].sum()) if (x<0).any() and (x>0).any() else float('nan')
import make_loma_top10 as T
for path in sorted(glob.glob(RES+"/reports/tester-fix/*.htm")):
    name=os.path.basename(path)[:-4]; rank=int(name[8:10])
    r=pool.iloc[rank-1]; p={k:X.cast(r[k],X.SPACE[k]) for k in X.SPACE}
    p.update(T.OVERRIDE.get((p["tf"],p["sides"],p["session"],p["htf"]),{}))
    c=X.engine_cfg(dict(p,skip_big_pb=1,weekend_close=1))
    py=mk.run(c); py=py[(py.entry_time>="2026-03-01")]
    ea=deals(path)
    ov=ea[ea.entry<"2026-05-16"]; late=ea[ea.entry>="2026-05-16"]
    # match entries within one trigger bar
    tol=pd.Timedelta(minutes=H.B.TF_MIN[p["tf"]])
    pt=py.entry_time.values; matched=0; same_side=0
    for e in ov.itertuples():
        j=np.argmin(np.abs(pt-np.datetime64(e.entry))) if len(pt) else -1
        if j>=0 and abs(pd.Timestamp(pt[j])-e.entry)<=tol:
            matched+=1; same_side+= int(py.side.values[j]==e.side)
    print(f"\n{name}")
    print(f"  EA  Mar1-May15: n={len(ov):3d} PF={pf(ov.pnl.values):.2f} net={ov.pnl.sum():+8.1f} win={(ov.pnl>0).mean():.0%} exits={ov.why.value_counts().to_dict()}")
    print(f"  PY  Mar1-May15: n={len(py):3d} PF={pf(py.r.values):.2f} net={py.r.sum():+5.1f}R win={(py.r>0).mean():.0%}")
    print(f"  EA entries also in PY (within 1 bar): {matched}/{len(ov)} (same side {same_side});  PY entries: {len(py)}")
    print(f"  EA  May16-Nov6 (unseen): n={len(late):3d} PF={pf(late.pnl.values):.2f} net={late.pnl.sum():+8.1f} win={(late.pnl>0).mean():.0%}")
    if rank==1:
        print(ov[["entry","side","entry_px","exit","exit_px","pnl","why"]].head(12).to_string(index=False))
        q=py.copy(); q["exit_time"]=mk.t[q.exit_row.astype(int).values]; q["px"]=mk.o[q.entry_row.astype(int).values]
        print(q[["entry_time","side","px","exit_time","r","risk"]].head(12).round(2).to_string(index=False))
