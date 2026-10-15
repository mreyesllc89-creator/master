"""Report-only: each preset filled on TradingView's bar-magnifier intrabar timeframe instead of 1-minute paths
(TradingView help centre, 'What is bar magnifier backtesting mode': 15m -> 2m, 30m -> 5m, 1H -> 10m, 4H -> 30m,
1D -> 60m, each row covering the timeframes up to the next; 1m -> 10S and 5m -> 30S cannot be built from 1-minute
data). The 200,000-intrabar cap is not modelled (here the whole history is magnified)."""
import json, sys
import numpy as np
import pandas as pd
import fgrun as R
import pipe2 as P
from stage_c import apply_filters

TV_MAG = {15: 2, 30: 5, 60: 10, 120: 10, 240: 30, 480: 30, 1440: 60}

if __name__ == "__main__":
    base = pd.read_parquet("btc_1m.parquet")
    S = R.Source(base, 1)
    out = {}
    for tf, m in TV_MAG.items():
        r = json.load(open(f"{P.OUT}/preset_{tf}.json"))
        e, f, x = r["entry"], r["filter"], r["exits"]
        p = P.base_params(tf, e, f)
        p.update(sl_atr=x["sl"], tp_r=x["tpr"], trail_act_atr=x["act"], trail_dst_atr=x["dst"], use_trail=x["act"] > 0,
                 re_mode=x["rm"], re_max=x["rmax"], re_dist_atr=0.25, exit_opp=x["xopp"], fd_exit_break=x["xbrk"], fd_on=True,
                 use_mag=True)
        ctx = apply_filters(R.context(S, tf, p), S, tf, p, f)
        tr = R.run(S, tf, p, ctx, mag=S.bars(m))
        eb = tr.ebar.to_numpy()
        mt = P.trade_metrics(tr, ctx["atr14"][eb], ctx["ch"]["t_open"][eb])
        one = r["results"]["preset"]
        out[tf] = dict(intrabar=m, is_pf_1m=one["is_pf"], is_pf_tv=mt["is_pf"], oos_pf_1m=one["oos_pf"], oos_pf_tv=mt["oos_pf"],
                       is_n_1m=one["is_n"], is_n_tv=mt["is_n"])
        print(tf, out[tf], flush=True)
    json.dump(out, open(f"{P.OUT}/tv_check.json", "w"), indent=1)
