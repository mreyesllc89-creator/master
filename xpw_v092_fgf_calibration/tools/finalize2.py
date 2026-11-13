"""Recompute the forward-window figures of run-2 presets as 'everything after the out-of-sample window',
so the last hours of data and the end-of-data mark-to-market are included (bar times are on the server clock)."""
import glob, json, os, sys
import xpw_run as R, xpw_search2 as S
RES = os.environ.get("XPW_OUT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "results2")
for f in sorted(glob.glob(os.path.join(RES, "*.json"))):
    j = json.load(open(f)); sym = j["symbol"]; tf = int(j["tf"])
    w = S.windows(sym, tf); mk = S.market(sym, w["start"]); n = 0
    for r in j["top"] + j["unstable"]:
        res = mk.run(r["params"])
        old = r["fwd"]["net"]; r["fwd"] = S.usd_metrics(mk, res, w["oos"][1], None); n += 1
        chk = S.usd_metrics(mk, res, *w["oos"])
        assert abs(chk["net"] - r["oos"]["net"]) < 1e-6, (f, chk["net"], r["oos"]["net"])
    json.dump(j, open(f, "w"), default=str)
    print(os.path.basename(f), "recomputed", n, flush=True)
