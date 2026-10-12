"""Bug fix 1 size: candles (evaluation months 2020-01 .. 2026-10, complete candles) whose zone differs between the frozen
comparison (close vs level +- band) and the indicator's tick rule (edges rounded outward to 0.01, half-tick guard),
for the baselines and the frozen final picks of the pre-fix primary run. Usage: python tickfix_count.py <out_csv>"""
import sys, os, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wf_common as W

HERE = os.path.dirname(os.path.abspath(__file__))
S = W.load("utc")
rows = []
for tf in W.FILTER_TFS:
    ch = S.bars(tf)
    last_ts = int(S.base.index[-1].timestamp()) + 60
    N = int(np.searchsorted(ch["t_close"], last_ts, side="right"))
    mon = W.month_id(ch["t_open"][:N])
    ev = mon >= 2020 * 12
    sets = list(W.baselines(tf))
    fj = json.load(open(f"{HERE}/out_v0_pre_tickfix/wf_final_{tf}_utc_mt5_real.json"))
    for k in ("R1_greedy", "R2_conservative"):
        d = fj[k]
        sets.append(dict(parent=int(d["parent"]), zones=tuple(int(x) for x in str(d["zones"]).split("/")),
                         ma=int(d["min_aligned"]), use_zones=bool(d["use_zones"]), kind=f"v0_final_{k}"))
    for r in sets:
        z1, g, ctx = W.zone_of(S, tf, r, "mt5")
        c = ch["c"]
        L, A, D = W.held(c, ctx["atr14"], ctx["buy"], ctx["sell"], ctx["bpx"], ctx["spx"])
        z0 = W.zone_edges(c, L, W.BAND * np.nan_to_num(A), exact_tick=None)
        z0, z1 = z0[:N][ev], z1[:N][ev]
        rows.append(dict(filter_tf=W.NAMES[tf], kind=r["kind"], setting=W.label(r), candles=int(ev.sum()),
                         zone_changed=int((z0 != z1).sum()), share=float((z0 != z1).mean()),
                         buy_to_none=int(((z0 == 1) & (z1 == 0)).sum()), sell_to_none=int(((z0 == -1) & (z1 == 0)).sum()),
                         other=int(((z0 != z1) & ~(((z0 == 1) | (z0 == -1)) & (z1 == 0))).sum())))
    print(tf, flush=True)
pd.DataFrame(rows).to_csv(sys.argv[1], index=False, float_format="%.7f")
print(pd.DataFrame(rows).to_string())
