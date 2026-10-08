import sys, glob, pandas as pd
sys.path.insert(0, sys.argv[1])
from ticks import load_ticks
for sym in ['XAUUSD-ECNc', 'BTCUSD.c']:
    fs = sorted(glob.glob(sys.argv[2] + '/' + sym + '_*.csv'))
    df = pd.concat([load_ticks(f) for f in fs]).drop_duplicates('ts').sort_values('ts').reset_index(drop=True)
    gaps = df['ts'].diff()
    big = df.loc[gaps > pd.Timedelta('2h'), 'ts']
    print(sym, len(df), df['ts'].iloc[0], '->', df['ts'].iloc[-1])
    for i in big.index: print('   gap', df['ts'][i-1], '->', df['ts'][i])
    df.to_pickle(sys.argv[2] + '/' + sym + '.pkl')
