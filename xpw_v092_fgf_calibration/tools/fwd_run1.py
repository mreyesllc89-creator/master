"""Forward test of the run-1 presets on data they never saw (2026-11-01..2026-11-12)."""
import glob, json, csv, datetime as dt
import numpy as np
import xpw_run as R, xpw_report as X
TS = lambda y, m, d: int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp())
F0, F1 = TS(2026, 11, 1), TS(2026, 11, 13)
rows = []; markets = {}
for f in sorted(glob.glob("results_run1/*.json")):
    j = json.load(open(f)); sym = j["symbol"]; tf = int(j["tf"]); lab = X.TF_LABEL[tf]
    is_lo = j["is_window"][0]
    sane = [r for r in j["top"] if r["is_"]["win"] * r["is_"]["trades"] >= X.MIN_WINNERS_IS and r["oos"]["win"] * r["oos"]["trades"] >= X.MIN_WINNERS_OOS][:X.TOP_N]
    if not sane: continue
    start = is_lo   # run 1 had no warm-up prefix: reproduce it exactly
    if (sym, start) not in markets: markets[(sym, start)] = R.Market(sym, start=start)
    mk = markets[(sym, start)]; usd = mk.spec["usd_per_unit"]
    for rank, r in enumerate(sane, 1):
        res = mk.run(r["params"])
        # forward = everything after the run-1 windows, including the end-of-data mark
        m = R.metrics(res, j["oos_window"][1], None); old = R.metrics(res, j["is_window"][0], j["oos_window"][1])
        rows.append(dict(preset=f"{sym}_{lab}_rank{rank}.set", symbol=sym, tf=lab, fwd_trades=m["trades"], fwd_net_usd=round(m["net"] * usd, 2),
                         fwd_pf=round(m["pf"], 2), fwd_win=round(m["win"], 2), check_old_net=round(old["net"] * usd, 2), reported_old_net=round(r["all"]["net"], 2)))
        print(rows[-1], flush=True)
w = csv.DictWriter(open("fwd_run1.csv", "w", newline=""), fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
for sym in ("XAUUSD", "BTCUSD"):
    rs = [r for r in rows if r["symbol"] == sym]
    print(sym, "presets", len(rs), "with trades", sum(r["fwd_trades"] > 0 for r in rs), "profitable", sum(r["fwd_net_usd"] > 0 for r in rs), "losing", sum(r["fwd_net_usd"] < 0 for r in rs),
          "sum net", round(sum(r["fwd_net_usd"] for r in rs), 2))
