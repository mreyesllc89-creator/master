#!/usr/bin/env python3
"""Collect every number shown in the Loma out-of-sample report into results/loma_report_data.json.
Usage: python3 make_loma_report_data.py <dukascopy_dir> <codex_results_dir>"""
import glob, html, json, os, re, sys
import numpy as np, pandas as pd

os.environ["HUMP_SPACE"] = "2"
import hump_engine as H, hump_search as X, duk_to_m1 as D, make_loma_top10 as T

DUK, RES = sys.argv[1], sys.argv[2]
RANKS = [1, 2, 3, 4, 5, 7]
# The Strategy Tester run charged 6 USD per lot round trip (1 lot = 1 ounce on XAUUSD-ECNc). VT Markets' real
# commission, as the account owner reported it, is 0.60 USD per lot round trip: one tenth.
TESTER_COMM_PER_LOT, REAL_COMM_PER_LOT = 6.0, 0.60
REAL_COMM_SCALE = REAL_COMM_PER_LOT / TESTER_COMM_PER_LOT


def pf(x):
    x = np.asarray(x, float); w = x[x > 0].sum(); l = -x[x < 0].sum()
    return float(w / l) if l > 0 else None


def deals(path):
    txt = open(path, "rb").read().decode("utf-16"); i = txt.find("Deals"); out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", txt[i:], flags=re.S):
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.S)]
        if len(c) >= 13 and re.match(r"\d{4}\.\d\d\.\d\d \d\d:\d\d:\d\d", c[0]) and c[3] in ("buy", "sell"):
            out.append(c)
    d = pd.DataFrame(out, columns=["time", "deal", "sym", "type", "dir", "vol", "price", "order", "comm", "swap", "profit", "bal", "comment"])
    d["time"] = pd.to_datetime(d.time, format="%Y.%m.%d %H:%M:%S")
    for k in ("vol", "price", "comm", "swap", "profit"):
        d[k] = d[k].str.replace(" ", "").astype(float)
    ins = d[d.dir == "in"].reset_index(drop=True); outs = d[d.dir == "out"].reset_index(drop=True)
    return pd.DataFrame([dict(entry=a.time, gross=b.profit + b.swap, comm=a.comm + b.comm)
                         for a, b in zip(ins.itertuples(), outs.itertuples())])


out = {}
summ = pd.read_csv("../presets/top10/TOP10_SUMMARY.csv")
pool = pd.read_csv("results/hump_pool_ranked.csv").sort_values("allround", ascending=False).drop_duplicates("fam").head(10).reset_index(drop=True)
m, h = D.load(DUK); mk = H.Market(m1=m, half_spread=h)
out["dukascopy_span"] = [str(m.index[0]), str(m.index[-1])]

presets, vt_all, duk_rows = [], [], []
for rank in RANKS:
    s = summ[summ["rank"] == rank].iloc[0]
    vt = deals(glob.glob(f"{RES}/reports/tester-fix/Loma_Top{rank:02d}_*.htm")[0])
    vt["preset"] = f"Top{rank:02d}"; vt_all.append(vt)
    presets.append(dict(preset=f"Top{rank:02d}", file=s.file, tf=s.timeframe, direction=s.direction, session=s.session,
                        filter=s.trend_filter, target=s.target, trailing=s.trailing,
                        bt_trades=int(s.trades), bt_pf=float(s.pf), bt_pf_2026=float(s.pf_2026), bt_stress_pf=float(s.stress_pf),
                        vt_trades=len(vt), vt_gross=round(vt.gross.sum(), 2), vt_comm=round(vt.comm.sum(), 2),
                        vt_net=round(vt.gross.sum() + vt.comm.sum(), 2), vt_gross_pf=pf(vt.gross), vt_net_pf=pf(vt.gross + vt.comm)))
    r = pool.iloc[rank - 1]; p = {k: X.cast(r[k], X.SPACE[k]) for k in X.SPACE}
    p.update(T.OVERRIDE.get((p["tf"], p["sides"], p["session"], p["htf"]), {}))
    c = X.engine_cfg(dict(p, skip_big_pb=1, weekend_close=1, max_spread=5))
    df = mk.run(c); tol = pd.Timedelta(minutes=H.B.TF_MIN[p["tf"]])
    for name, a, b in [("Jun-Aug", "2026-06-01", "2026-08-31"), ("Sep-Nov 6", "2026-08-31", "2026-11-07")]:
        d = df[(df.entry_time >= a) & (df.entry_time < b)]; v = vt[(vt.entry >= a) & (vt.entry < b)]; pt = d.entry_time.values
        match = sum(1 for e in v.itertuples() if len(pt) and abs(pd.Timestamp(pt[np.argmin(np.abs(pt - np.datetime64(e.entry)))]) - e.entry) <= tol)
        duk_rows.append(dict(preset=f"Top{rank:02d}", tf=p["tf"], period=name, duk_n=len(d), duk_pf=pf(d.r), duk_netR=round(float(d.r.sum()), 1),
                             vt_n=len(v), vt_gross_pf=pf(v.gross), matched=match, _r=d.r.tolist(), _g=v.gross.tolist()))
    # whole untouched period per preset (Jun 1 - Nov 6 2026), for the preset headers and summary CSV
    d = df[(df.entry_time >= "2026-06-01") & (df.entry_time < "2026-11-07")]; v = vt[(vt.entry >= "2026-06-01") & (vt.entry < "2026-11-07")]
    presets[-1].update(oos_vt_n=len(v), oos_vt_gross=round(float(v.gross.sum()), 2), oos_vt_gross_pf=pf(v.gross),
                       oos_vt_net=round(float((v.gross + v.comm).sum()), 2), oos_vt_net_pf=pf(v.gross + v.comm),
                       oos_vt_pf_real_comm=pf(v.gross + REAL_COMM_SCALE * v.comm),
                       oos_duk_n=len(d), oos_duk_pf=pf(d.r), oos_duk_netR=round(float(d.r.sum()), 2))
out["presets"] = presets
tot = []
for per in ["Jun-Aug", "Sep-Nov 6"]:
    rr = [x for x in duk_rows if x["period"] == per]
    r_ = np.concatenate([x["_r"] for x in rr]); g_ = np.concatenate([x["_g"] for x in rr])
    tot.append(dict(preset="All six", tf="", period=per, duk_n=len(r_), duk_pf=pf(r_), duk_netR=round(float(r_.sum()), 1),
                    vt_n=len(g_), vt_gross_pf=pf(g_), matched=sum(x["matched"] for x in rr)))
out["dukascopy"] = [{k: v for k, v in x.items() if not k.startswith("_")} for x in duk_rows] + tot

va = pd.concat(vt_all); va["month"] = va.entry.dt.strftime("%Y-%m")
out["vt_monthly"] = [dict(month=mo, trades=len(g), gross=round(g.gross.sum(), 2), comm=round(g.comm.sum(), 2), gross_pf=pf(g.gross))
                     for mo, g in va.groupby("month")]
out["vt_periods"] = [dict(period=n, trades=len(g), gross=round(g.gross.sum(), 2), gross_pf=pf(g.gross), net_pf=pf(g.gross + g.comm),
                          real_comm=round(float(REAL_COMM_SCALE * g.comm.sum()), 2),
                          real_net=round(float((g.gross + REAL_COMM_SCALE * g.comm).sum()), 2),
                          real_net_pf=pf(g.gross + REAL_COMM_SCALE * g.comm))
                     for n, g in [("Mar-May", va[va.entry < "2026-06-01"]), ("Jun-Nov 6", va[va.entry >= "2026-06-01"]),
                                  ("whole run", va)]]
out["vt_commission"] = dict(tester_per_lot_round_trip=TESTER_COMM_PER_LOT, real_per_lot_round_trip=REAL_COMM_PER_LOT)
out["vt_total"] = dict(trades=len(va), gross=round(va.gross.sum(), 2), comm=round(va.comm.sum(), 2),
                       net=round(va.gross.sum() + va.comm.sum(), 2), gross_pf=pf(va.gross))

wf = []
for f in sorted(glob.glob("results/walkforward/wf_*_windows.csv")):
    tr, te = re.findall(r"wf_(\d+)_(\d+)_", f)[0]; w = pd.read_csv(f)
    for (var, st), g in w.groupby(["variant", "stress"]):
        gl = np.where(g.pf != 1, g.net / (g.pf - 1), 0.0); gw = g.pf * gl      # per-window gross loss / win in R
        gl, gw = np.nan_to_num(gl), np.nan_to_num(gw)
        wf.append(dict(train=int(tr), test=int(te), variant=var, stress=bool(st), windows=len(g),
                       profitable=int((g.net > 0).sum()), empty=int((g.n == 0).sum()), trades=int(g.n.sum()),
                       netR=round(float(g.net.sum()), 1), pooled_pf=float(gw.sum() / gl.sum()) if gl.sum() > 0 else None))
out["walkforward"] = wf
w = pd.read_csv("results/walkforward/wf_6_1_windows.csv")
out["wf_6_1_top5"] = [dict(window=r.window, n=int(r.n), netR=round(r.net, 2)) for r in w[(w.variant == "top5") & (~w.stress)].itertuples()]
json.dump(out, open("results/loma_report_data.json", "w"), indent=1, default=float)
print(json.dumps({k: out[k] for k in ("vt_total", "vt_monthly")}, indent=0)); print(pd.DataFrame(out["dukascopy"]).to_string()); print(pd.DataFrame(wf).to_string())
print(pd.DataFrame(presets).drop(columns=["file"]).to_string())
