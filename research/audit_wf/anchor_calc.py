"""The price anchor as build() computes it (mean close of the last 180 days of the series), the same mean over the
180 days before 2026-01-01 (no 2026 data), and the price level of every year (how far the scale moves costs).
Usage: python3 anchor_calc.py <work> <out_json>"""
import json, os, sys
import pandas as pd
work, out_json = sys.argv[1:3]
m1 = pd.read_pickle(os.path.join(work, "m1.pkl"))
meta = json.load(open(os.path.join(work, "meta.json")))
c = m1["close"]
last = m1.index[-1]
a_file = float(c[m1.index >= last - pd.Timedelta(days=180)].mean())
cut = pd.Timestamp("2026-01-01")
a_pre = float(c[(m1.index >= cut - pd.Timedelta(days=180)) & (m1.index < cut)].mean())
yearly = {int(y): float(v) for y, v in c.groupby(m1.index.year).mean().items()}
res = dict(meta_anchor=meta["anchor_price"], recomputed=a_file, window_start=str(last - pd.Timedelta(days=180)), last=str(last),
           anchor_pre2026=a_pre, ratio_pre2026_to_file=a_pre / a_file, yearly_mean_close=yearly,
           scale_by_year={y: v / a_file for y, v in yearly.items()})
json.dump(res, open(out_json, "w"), indent=1)
print(json.dumps(res, indent=1))
