"""Self-contained HTML report for an EVK analysis (no external files; Google Fonts optional)."""
import html
import json

import numpy as np
import pandas as pd


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    return o


def _curve(trades, v):
    eq = np.cumsum(np.nan_to_num(trades[v].to_numpy(float)))
    return [[str(t)[:10], round(float(e), 3)] for t, e in zip(trades.close_time, eq)]


def build(run, value, ho, wf, st, cmp=None, title=None):
    v = run.value_col(value)
    unit = "R" if v == "r" else "money"
    chosen = ho["chosen"]
    ch_tr = run.trades[run.trades["pass"] == chosen] if chosen is not None else run.trades.iloc[0:0]
    tab = ho["table"]
    top = ho["ranked"].head(20)
    top_rows = []
    for p, r in top.iterrows():
        top_rows.append(dict(label=run.label(p), score=r.rank_score, is_trades=r.is_trades, is_pf=r.is_pf,
                             oos_trades=r.oos_trades, oos_pf=r.oos_pf, all_net=r.all_net))
    data = dict(
        meta=run.meta, unit=unit, passes=len(run.passes), optimized=[c[2:] for c in run.varying],
        trades=len(run.trades), split=ho["split"], criterion=ho["criterion"], smooth=ho["smooth"],
        min_trades=ho["min_trades"], topk=ho["topk"], base_rate=ho["base_rate"], base_median=ho["base_median"],
        chosen=dict(label=run.label(chosen) if chosen is not None else None,
                    row=tab.loc[chosen].to_dict() if chosen is not None else {},
                    curve=_curve(ch_tr, v)),
        top=top_rows, wf=dict(windows=wf["windows"], oos=wf["oos"], curve=_curve(wf["oos_trades"], v)
                              if len(wf["oos_trades"]) else [], train=wf.get("train_months"),
                              test=wf.get("test_months"), anchored=wf.get("anchored"),
                              distinct=wf.get("distinct_picks")),
        stress=st,
        cmp=None if cmp is None else {k: val for k, val in cmp.items() if k != "pairs"},
    )
    payload = json.dumps(_clean(data))
    name = html.escape(title or (run.meta.split("|")[1].strip() if "|" in run.meta else "EA") + " validation")
    return TEMPLATE.replace("__TITLE__", name).replace("__DATA__", payload)


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
:root{--bg:#f7f7f4;--surface:#fff;--fg:#1b1d22;--fg2:#555a63;--muted:#8a8f98;--rule:#e2e2dc;--gold:#9a6b00;--good:#1e7d3a;--bad:#b4322f;--warnbg:#fff5dc;--s1:#2a78d6;--s2:#eb6834;
--sans:"Libre Franklin",system-ui,-apple-system,"Segoe UI",sans-serif;--mono:"JetBrains Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#141518;--surface:#1c1d21;--fg:#eceae4;--fg2:#b9bac0;--muted:#868a93;--rule:#2e3036;--gold:#e0b44a;--good:#4cc072;--bad:#ec6b67;--warnbg:#2c2614;--s1:#3987e5;--s2:#d95926;color-scheme:dark}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 var(--sans)}
main{max-width:980px;margin:0 auto;padding:32px max(16px,env(safe-area-inset-right,0px)) 64px max(16px,env(safe-area-inset-left,0px));display:grid;grid-template-columns:minmax(0,1fr);gap:36px}
.eyebrow,h1,p{overflow-wrap:anywhere}
h1{font-size:28px;line-height:1.15;margin:0}h2{font-size:19px;margin:0}p{margin:0;max-width:72ch;color:var(--fg2)}
.eyebrow{font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--gold)}
section,header{display:grid;gap:12px;min-width:0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.v{background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:14px 16px;display:grid;gap:4px;align-content:start}
.v b{font:600 22px/1.15 var(--mono)}.v span{font-size:13px;color:var(--fg2)}
.tw{overflow-x:auto;border:1px solid var(--rule);border-radius:6px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:13.5px}
th,td{padding:7px 11px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--rule)}
th{font:600 11px var(--mono);text-transform:uppercase;letter-spacing:.05em;color:var(--muted);background:var(--bg)}
td:first-child,th:first-child{text-align:left}td.wrap{white-space:normal;min-width:240px;text-align:left}tr:last-child td{border-bottom:0}
.pos{color:var(--good);font-weight:600}.neg{color:var(--bad);font-weight:600}
.chart{background:var(--surface);border:1px solid var(--rule);border-radius:6px;padding:12px}
.chart svg{display:block;width:100%;height:auto}.axis text{fill:var(--muted);font:11px var(--mono)}.grid line{stroke:var(--rule)}
.note{background:var(--warnbg);border-left:3px solid var(--gold);padding:10px 14px;border-radius:0 6px 6px 0}.note p{color:var(--fg)}
ul{margin:0;padding-left:20px;color:var(--fg2);display:grid;gap:5px;max-width:74ch}code{font-family:var(--mono);font-size:.9em}
</style></head><body><main>
<header><div class="eyebrow" id="meta"></div><h1>__TITLE__</h1><p id="intro"></p></header>
<section><div class="tiles" id="tiles"></div><div class="note"><p id="verdict"></p></div></section>
<section><h2>Hold-out test</h2><p id="hoText"></p><div class="tw"><table id="ho"></table></div></section>
<section><h2>The pass chosen before the hold-out</h2><p id="chText"></p><div class="chart" id="chChart"></div><div class="tw"><table id="ch"></table></div></section>
<section><h2>Walk-forward</h2><p id="wfText"></p><div class="chart" id="wfChart"></div><div class="tw"><table id="wf"></table></div></section>
<section><h2>Stress tests on the chosen pass</h2><p>Extra cost per trade, removing the best trades, reshuffled trade order (drawdown risk) and a bootstrap of the profit factor. The bootstrap is conditional on this pass and ignores how it was chosen, so it overstates confidence.</p><div class="tw"><table id="cost"></table></div><div class="tw"><table id="mc"></table></div></section>
<section id="cmpSec" hidden><h2>A/B comparison</h2><p id="cmpText"></p><div class="tw"><table id="cmp"></table></div></section>
<section><h2>Top passes by the selection score</h2><p>Ranked using data before the split only. Out-of-sample columns were not used for the ranking.</p><div class="tw"><table id="top"></table></div></section>
<section><h2>How to read this</h2><ul>
<li><b>In-sample (IS)</b>: data used to choose. <b>Out-of-sample (OOS)</b>: data after the split, never used to choose. Only OOS numbers estimate future results.</li>
<li><b>Profit factor (PF)</b>: gross profit / gross loss. Above 1 makes money. A pass with no losing trade is capped at 100.</li>
<li><b>Base rate</b>: share of all passes profitable out of sample. A selection method is useful only if its picks beat the base rate.</li>
<li><b>Neighbourhood</b>: the pass plus the passes one optimization step away on each numeric input. Choosing by the neighbourhood median avoids isolated lucky peaks.</li>
<li><b>Walk-forward</b>: choose on a training window, trade the next test window, roll forward, and join all test windows. It is the closest backtest to running the EA with periodic re-optimization.</li>
<li>Results come from the MT5 Strategy Tester runs in the input file. Check the tester model ("Every tick based on real ticks" is best) before trusting them.</li></ul></section>
</main><script>
const D=__DATA__;const U=D.unit==="R"?"R":"";
const f2=x=>x==null||!isFinite(x)?"–":Number(x).toFixed(2);const pct=x=>x==null?"–":Math.round(x*100)+"%";
const cls=(x,r=1)=>x==null?"":(x>=r?"pos":"neg");const tb=(id,h,rows)=>{document.getElementById(id).innerHTML="<tr>"+h.map(x=>`<th>${x}</th>`).join("")+"</tr>"+rows.join("")};
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
document.getElementById("meta").textContent=D.meta||"EVK";
document.getElementById("intro").textContent=`${D.passes} passes, ${D.trades} trades, results in ${D.unit}. Optimized inputs: ${D.optimized.join(", ")||"none"}. Split for the hold-out: ${D.split}. Selection criterion: ${D.criterion}${D.smooth?" (neighbourhood median)":""}, at least ${D.min_trades} trades before the split.`;
const ch=D.chosen.row||{};const t1=D.topk.find(r=>r.k===10)||D.topk[D.topk.length-1]||{};
document.getElementById("tiles").innerHTML=[
 [f2(ch.oos_pf),`out-of-sample PF of the pass chosen on in-sample data (${ch.oos_trades??0} trades)`],
 [pct(D.base_rate),"base rate: passes profitable out of sample"],
 [f2(t1.oos_pf_median),`median out-of-sample PF of the top ${t1.k??"–"} picks`],
 [f2(D.wf.oos.pf),`walk-forward PF, all test windows joined (${D.wf.oos.trades} trades, ${D.wf.distinct??0} different picks)`]
].map(([b,s])=>`<div class="v"><b>${b}</b><span>${s}</span></div>`).join("");
const good=(t1.oos_pf_median??0)>1&&(t1.oos_profitable??0)>(D.base_rate??1)&&(D.wf.oos.pf??0)>1;
document.getElementById("verdict").innerHTML=good?"<b>The selection held up out of sample.</b> Picks made on in-sample data stayed profitable after the split, beat the base rate, and the walk-forward was profitable. Confirm with a forward test on a demo account.":"<b>The selection did not clearly hold up out of sample.</b> At least one of these failed: the top picks' median out-of-sample PF above 1, their profitable share above the base rate, a profitable walk-forward. Treat the in-sample best as curve-fitted.";
document.getElementById("hoText").textContent=`Passes ranked on data before ${D.split}, then measured after it. Base rate: ${pct(D.base_rate)} of passes profitable out of sample (median PF ${f2(D.base_median)}).`;
tb("ho",["Top k","Median IS score","Median OOS PF","OOS profitable","Median OOS trades"],D.topk.map(r=>`<tr><td>${r.k}</td><td>${f2(r.is_score_median)}</td><td class="${cls(r.oos_pf_median)}">${f2(r.oos_pf_median)}</td><td class="${cls(r.oos_profitable,D.base_rate)}">${pct(r.oos_profitable)}</td><td>${r.oos_trades_median}</td></tr>`));
document.getElementById("chText").innerHTML=`Inputs: <code>${D.chosen.label||"–"}</code>. Neighbourhood: ${pct(ch.nb_share_gt1)} of its neighbours score above 1. The dashed line is the split.`;
tb("ch",["Part","Trades","PF","Win","Net "+U,"Max DD "+U],["is","oos","all"].map(k=>`<tr><td>${{is:"In-sample",oos:"Out-of-sample",all:"Whole run"}[k]}</td><td>${ch[k+"_trades"]??0}</td><td class="${cls(ch[k+"_pf"])}">${f2(ch[k+"_pf"])}</td><td>${pct(ch[k+"_win"])}</td><td>${f2(ch[k+"_net"])}</td><td>${f2(ch[k+"_maxdd"])}</td></tr>`));
function eq(id,pts,mark){const box=document.getElementById(id);if(!pts.length){box.innerHTML="<p>No trades.</p>";return}
 const W=900,H=280,m={l:52,r:12,t:10,b:28},NS="http://www.w3.org/2000/svg",mk=(t,a,p)=>{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);p&&p.appendChild(e);return e};
 const svg=mk("svg",{viewBox:`0 0 ${W} ${H}`,role:"img"},box);const t0=Date.parse(pts[0][0]),t1=Date.parse(pts[pts.length-1][0])+864e5;
 const ys=pts.map(p=>p[1]).concat([0]);const lo=Math.min(...ys),hi=Math.max(...ys);const pad=(hi-lo)*.08||1;
 const x=d=>m.l+(Date.parse(d)-t0)/(t1-t0)*(W-m.l-m.r),y=v=>m.t+(H-m.t-m.b)-(v-lo+pad)/(hi-lo+2*pad)*(H-m.t-m.b);
 const g=mk("g",{class:"grid"},svg),a=mk("g",{class:"axis"},svg);for(let i=0;i<=4;i++){const v=lo-pad+(hi-lo+2*pad)*i/4;mk("line",{x1:m.l,x2:W-m.r,y1:y(v),y2:y(v)},g);mk("text",{x:m.l-6,y:y(v)+4,"text-anchor":"end"},a).textContent=Math.abs(v)>=1000?Math.round(v):v.toFixed(1)}
 for(let i=0;i<=4;i++){const t=new Date(t0+(t1-t0)*i/4).toISOString().slice(0,7);mk("text",{x:m.l+(W-m.l-m.r)*i/4,y:H-8,"text-anchor":i==0?"start":i==4?"end":"middle"},a).textContent=t}
 if(mark&&Date.parse(mark)>t0&&Date.parse(mark)<t1){mk("line",{x1:x(mark),x2:x(mark),y1:m.t,y2:H-m.b,stroke:css("--fg2"),"stroke-dasharray":"4 4"},svg)}
 let d=`M${x(pts[0][0])},${y(0)}`;pts.forEach(p=>d+=` H${x(p[0])} V${y(p[1])}`);mk("path",{d,fill:"none",stroke:css("--s1"),"stroke-width":2},svg)}
eq("chChart",D.chosen.curve,D.split);eq("wfChart",D.wf.curve,null);
document.getElementById("wfText").textContent=`${D.wf.anchored?"Anchored":"Rolling"} windows: train ${D.wf.train} months, test ${D.wf.test} months. Each test window trades the pass chosen on its training window. Joined out-of-sample result: ${D.wf.oos.trades} trades, PF ${f2(D.wf.oos.pf)}, net ${f2(D.wf.oos.net)} ${U}.`;
tb("wf",["Train","Test","Chosen inputs","IS trades","IS PF","OOS trades","OOS PF","OOS net "+U],D.wf.windows.map(r=>`<tr><td>${r.train}</td><td>${r.test}</td><td class="wrap">${r.chosen||"no pass qualified"}</td><td>${r.is_trades??"–"}</td><td>${f2(r.is_pf)}</td><td>${r.oos_trades??"–"}</td><td class="${cls(r.oos_pf)}">${f2(r.oos_pf)}</td><td>${f2(r.oos_net)}</td></tr>`));
const S=D.stress||{};tb("cost",["Test","PF","Net "+U],[...(S.cost||[]).map(r=>`<tr><td>Extra cost ${r.cost}</td><td class="${cls(r.pf)}">${f2(r.pf)}</td><td>${f2(r.net)}</td></tr>`),...(S.drop_best||[]).map(r=>`<tr><td>Remove best ${r.removed} trade(s)</td><td class="${cls(r.pf)}">${f2(r.pf)}</td><td>${f2(r.net)}</td></tr>`)]);
const mc=S.mc_drawdown||{},bp=S.bootstrap_pf||{};tb("mc",["Measure","Value"],[`<tr><td>Max drawdown, actual order</td><td>${f2(mc.actual)} ${U}</td></tr>`,`<tr><td>Max drawdown, reshuffled: median / 95% / 99%</td><td>${f2(mc.p50)} / ${f2(mc.p95)} / ${f2(mc.p99)} ${U}</td></tr>`,`<tr><td>Bootstrap PF: 5% / median / 95%</td><td>${f2(bp.p5)} / ${f2(bp.p50)} / ${f2(bp.p95)}</td></tr>`,`<tr><td>Bootstrap chance PF &lt; 1</td><td>${pct(bp.p_below_1)}</td></tr>`]);
if(D.cmp){const c=D.cmp;document.getElementById("cmpSec").hidden=false;document.getElementById("cmpText").textContent=`${c.matched} pass pairs with identical inputs (${c.inputs.join(", ")||"single pass"}), ${c.used} with enough trades in both.`;
 tb("cmp",["Measure",c.label_a,c.label_b],[`<tr><td>Median PF</td><td>${f2(c.pf_a)}</td><td class="${cls(c.pf_b,c.pf_a)}">${f2(c.pf_b)}</td></tr>`,`<tr><td>Median net (${c.unit})</td><td>${f2(c.net_a)}</td><td>${f2(c.net_b)}</td></tr>`,`<tr><td>Share of pairs where ${c.label_b} has the higher PF</td><td colspan="2">${pct(c.share_pf_up)}</td></tr>`,`<tr><td>Share where ${c.label_b} has the higher net</td><td colspan="2">${pct(c.share_net_up)}</td></tr>`,`<tr><td>Trades kept by ${c.label_b}</td><td colspan="2">${pct(c.trades_kept)}</td></tr>`])}
tb("top",["Inputs","Score","IS trades","IS PF","OOS trades","OOS PF","Net "+U],D.top.map(r=>`<tr><td class="wrap"><code>${r.label}</code></td><td>${f2(r.score)}</td><td>${r.is_trades}</td><td>${f2(r.is_pf)}</td><td>${r.oos_trades}</td><td class="${cls(r.oos_pf)}">${f2(r.oos_pf)}</td><td>${f2(r.all_net)}</td></tr>`));
</script></body></html>"""
