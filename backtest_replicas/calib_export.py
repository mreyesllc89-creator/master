"""Compressed CSV of a calibration: python3 -I calib_export.py <strategy> <out.csv.gz>"""
import glob, os, sys
import pandas as pd
s, out = sys.argv[1], sys.argv[2]
keep = ['trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades']
fr = []
for f in sorted(glob.glob(f'out/calib_{s}_*_*.parquet')):
    b = os.path.basename(f)[:-8].split('_')
    pair, tf = b[-2], b[-1]
    d = pd.read_parquet(f)
    pc = [c for c in d.columns if c.startswith('p_')]
    extra = [c for c in ('floor_ok',) if c in d.columns]
    x = d[pc + extra + [k for k in keep if k in d.columns]].copy()
    x.columns = [c[2:] if c.startswith('p_') else c for c in x.columns]
    x.insert(0, 'tf', int(tf)); x.insert(0, 'pair', pair)
    for c in ('net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct'):
        if c in x: x[c] = x[c].round(4)
    fr.append(x)
a = pd.concat(fr).sort_values(['pair', 'tf'], kind='mergesort')
a.to_csv(out, index=False, compression={'method': 'gzip', 'compresslevel': 9, 'mtime': 0})
print(s, len(a), round(os.path.getsize(out) / 1e6, 2), 'MB', list(a.columns))
