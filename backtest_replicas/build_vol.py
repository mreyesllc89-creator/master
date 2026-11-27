"""Add volume to every chart timeframe: data/<PAIR>_<TF>_vol.parquet, one column 'volume', rows
aligned with data/<PAIR>_<TF>.parquet. Volume of a chart bar = sum of the 1-minute volumes whose
t_open lies in [t_open, t_close) of that bar (the 1-minute bars the chart bar was built from).
BTC: Bitstamp base-currency volume. XAU: Dukascopy tick count per minute (tick volume, as
TradingView shows for CFD gold feeds)."""
import glob
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/")
from build_bars import epoch_s
W = '/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/'
TFS = ['1', '5', '15', '30', '60', '120', '240']
for pair in ('BTC', 'XAU'):
    if pair == 'BTC':
        raw = pd.read_parquet(W + 'raw/btc_1m.parquet', columns=['volume'])
        v = raw['volume']
    else:
        parts = [pd.read_parquet(f, columns=['ticks']) for f in sorted(glob.glob(W + 'raw/xau_1m_*.parquet'))]
        raw = pd.concat(parts).sort_index()
        raw = raw[~raw.index.duplicated(keep='last')]
        v = raw['ticks'].astype(float)
    ts = epoch_s(v.index)
    m1 = pd.read_parquet(W + f'data/{pair}_1.parquet', columns=['t_open'])
    vol1 = pd.Series(v.to_numpy(), index=ts).reindex(m1['t_open'].to_numpy())
    assert vol1.notna().all(), (pair, int(vol1.isna().sum()))
    vol1 = vol1.to_numpy()
    cum = np.concatenate([[0.0], np.cumsum(vol1)])
    t1 = m1['t_open'].to_numpy()
    for tf in TFS:
        b = pd.read_parquet(W + f'data/{pair}_{tf}.parquet', columns=['t_open', 't_close'])
        lo = np.searchsorted(t1, b['t_open'].to_numpy(), 'left')
        hi = np.searchsorted(t1, b['t_close'].to_numpy(), 'left')
        assert (hi > lo).all()
        pd.DataFrame({'volume': cum[hi] - cum[lo]}).to_parquet(W + f'data/{pair}_{tf}_vol.parquet')
        print(pair, tf, len(b), 'zero-volume bars', int(((cum[hi] - cum[lo]) == 0).sum()))
