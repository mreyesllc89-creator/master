"""Stage 3: shipped preset vs the calibrated pick per symbol. Per-year table, monthly-start sweep,
cost stress, July-August 2026, and the .set files.
usage: python final_eval.py <shipped .set template>"""
import datetime as dt, json, sys
import numpy as np, pandas as pd
import common as C, space as S, score as SC, setfile

template = sys.argv[1]
summary, yearly, configs = [], [], {}


def month_starts(sym, y):
    d = C.load(sym, y)
    out = []
    for m in range(1, 13):
        ts = int(dt.datetime(y, m, 1, tzinfo=dt.timezone.utc).timestamp())
        if d["t"][0] - 5 * 86400 <= ts <= d["t"][-1] - 60 * 86400:
            out.append(ts)
    return out


def pick(sym):
    ref = pd.read_csv(f"../results/stage2_refined_{sym}.csv")
    ok = ref[(ref.is_growth > 0) & (ref.is_ruined == 0)]
    if len(ok) == 0:
        ok = ref
    return json.loads(ok.sort_values("oos_score", ascending=False).iloc[0].gene)


for sym in ["XAUUSD", "BTCUSD"]:
    k = C.K_BTC if sym == "BTCUSD" else 1.0
    genes = {"shipped": S.shipped_gene(), "calibrated": pick(sym)}
    for name, g in genes.items():
        p = SC.to_symbol(S.to_params(g, C.SHIPPED), sym)
        configs[f"{sym}_{name}"] = dict(gene=g, inputs=p)
        if name == "calibrated":
            setfile.write(template, f"../presets/TOKIO_VolLab_{sym}_calibrated.set", p,
                          [f"Tokio732_VolLab - calibrated for {sym} (see REPORT.md). Strategy Tester only.",
                           "Price-distance inputs assume a 2026 volatility level; VolATRRef carries the scale."])
        for part, yrs in SC.SPLIT[sym].items():
            for y in yrs:
                for step in SC.STEPS:
                    r = C.backtest(p, sym, y, step=step * k)
                    rs = r["reason"]
                    yearly.append(dict(symbol=sym, config=name, sample=part, year=y, step=step, baskets=r["n"],
                                       final=round(r["final"]), dd_pct=round(r["dd"], 1),
                                       trail=int((rs == 2).sum()), stop=int((rs == 0).sum()), age=int((rs == 1).sum())))
            # every monthly start, three granularities
            fin, dds = [], []
            for y in yrs:
                for ts in ([None] if y == 2026 else month_starts(sym, y)):
                    for step in SC.STEPS:
                        r = C.backtest(p, sym, y, t_from=ts, step=step * k)
                        fin.append(r["final"]); dds.append(r["dd"])
            fin = np.array(fin)
            row = dict(symbol=sym, config=name, sample=part, runs=len(fin), ruined_pct=round(100 * (fin < 300).mean()),
                       losing_pct=round(100 * (fin < 1000).mean()), median_final=round(np.median(fin)),
                       p10_final=round(np.percentile(fin, 10)), p90_final=round(np.percentile(fin, 90)),
                       median_dd=round(np.median(dds), 1), worst_dd=round(max(dds), 1))
            for label, kw in (("spread x2", dict(spread_mult=2.0)), ("slip 0.25", dict(slip=0.25 * k))):
                f2 = [C.backtest(p, sym, y, step=0.5 * k, **kw)["final"] for y in yrs]
                row[f"median_final {label}"] = round(np.median(f2))
            summary.append(row)
            print(row, flush=True)

pd.DataFrame(summary).to_csv("../results/final_summary.csv", index=False)
pd.DataFrame(yearly).to_csv("../results/final_yearly.csv", index=False)
json.dump(configs, open("../results/final_configs.json", "w"), indent=1)
