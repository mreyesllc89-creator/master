# Aggregate Dukascopy tick CSVs (time UTC, ask, bid, askvol, bidvol; prices scaled by 1/100) to 1m OHLC on bid and ask.
import sys, glob, os
import pandas as pd, numpy as np
src, dst = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(os.path.join(src, '**', '*_ticks.csv'), recursive=True))
parts = []
for f in files:
    if os.path.getsize(f) == 0:
        continue
    d = pd.read_csv(f, header=None, names=['t', 'ask', 'bid', 'av', 'bv'], usecols=[0, 1, 2])
    if d.empty:
        continue
    d['t'] = pd.to_datetime(d['t'], format='%Y.%m.%d %H:%M:%S.%f', utc=True)
    d['m'] = d['t'].dt.floor('1min')
    g = d.groupby('m')
    o = pd.DataFrame({'open': g['bid'].first(), 'high': g['bid'].max(), 'low': g['bid'].min(), 'close': g['bid'].last(),
                      'aopen': g['ask'].first(), 'ahigh': g['ask'].max(), 'alow': g['ask'].min(), 'aclose': g['ask'].last(),
                      'ticks': g['bid'].size()})
    parts.append(o)
out = pd.concat(parts).sort_index()
out = out[~out.index.duplicated(keep='last')]
med = out['close'].median()
scale = 100.0 if med < 100 else 1.0          # 2017-18 files carry price/100
for c in ['open', 'high', 'low', 'close', 'aopen', 'ahigh', 'alow', 'aclose']:
    out[c] = (out[c] * scale).round(3)
out.index.name = 'time'
out.to_parquet(dst)
print(dst, len(out), out.index.min(), out.index.max(), 'scale', scale, 'median close', out['close'].median())
