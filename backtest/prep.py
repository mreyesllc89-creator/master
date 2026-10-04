# Download Bitstamp BTC/USD 1-minute data and resample it to 15m / 1h / 4h / 1D.
#   pip install pandas numpy numba pyarrow
#   python prep.py && python grid.py 4h
import os, subprocess, pandas as pd
BASE = 'https://raw.githubusercontent.com/ff137/bitstamp-btcusd-minute-data/main/data/'
for f, p in [('hist.csv.gz', 'historical/btcusd_bitstamp_1min_2012-2025.csv.gz'),
             ('latest.csv', 'updates/btcusd_bitstamp_1min_latest.csv')]:
    if not os.path.exists(f):
        subprocess.run(['curl', '-sSL', '-o', f, BASE + p], check=True)
h = pd.read_csv('hist.csv.gz'); l = pd.read_csv('latest.csv')
d = pd.concat([h, l]).drop_duplicates('timestamp').sort_values('timestamp')
d = d[d.timestamp >= pd.Timestamp('2017-06-01').timestamp()]
d.index = pd.to_datetime(d.timestamp, unit='s'); d = d.drop(columns='timestamp')
for tf in ['15min', '1h', '4h', '1D']:
    r = d.resample(tf).agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
    r.to_parquet(f'btc_{tf}.parquet'); print(tf, len(r), r.index[0], r.index[-1])
