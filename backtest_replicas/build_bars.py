"""Build TradingView-style bars for every timeframe the XPW ladder, the FlashGold
Direction Filter and the chart need, from 1-minute bars.

Output: data/<pair>_<tf>.parquet with columns
    open, high, low, close   (float)
    t_open, t_close          (int64, UTC epoch seconds; t_close = the moment the
                              bar is complete: open + tf, or the session end)
    sess                     (int64 session id; gold: the 18:00-17:00 ET trading
                              day, BTC: the UTC date)
indexed 0..n-1 in time order.

TF names: "1","5","15","30","60","120","240","D","W","M".

BTC (Bitstamp, 24/7): UTC grid. Intraday bars aligned to UTC midnight, D = UTC
day, W = Monday 00:00 UTC, M = calendar month.

XAU (Dukascopy bid): TradingView-style session 18:00 -> 17:00 America/New_York.
Ticks between 17:00 and 18:00 ET and over the weekend are dropped. Intraday bars
are anchored at the session start (18:00 ET), so 120 and 240 minute bars start
18:00, 20:00 ... / 18:00, 22:00, 02:00, 06:00, 10:00, 14:00 and the last bar of
each session is truncated at 17:00 (240: 14:00-17:00). D = session (closes
17:00 ET), W = sessions of one Monday-Friday week (Sunday evening belongs to
Monday), M = sessions whose trading date falls in the month.
"""
import sys
import numpy as np
import pandas as pd

D = '/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/'
MIN_TFS = [1, 5, 15, 30, 60, 120, 240]


def epoch_s(idx):
    # DatetimeIndex (tz-aware or naive, any unit) -> int64 epoch seconds
    idx = pd.DatetimeIndex(idx)
    base = pd.Timestamp('1970-01-01', tz=idx.tz) if idx.tz is not None else pd.Timestamp('1970-01-01')
    return np.asarray((idx - base) // pd.Timedelta(seconds=1), dtype=np.int64)


def agg(df, key, t_open, t_close, sess):
    g = df.groupby(key, sort=True)
    out = pd.DataFrame({
        'open': g['open'].first(), 'high': g['high'].max(), 'low': g['low'].min(), 'close': g['close'].last(),
        't_open': g[t_open].first() if isinstance(t_open, str) else t_open(g),
        't_close': g[t_close].first() if isinstance(t_close, str) else t_close(g),
        'sess': g[sess].first(),
    })
    return out.reset_index(drop=True)


def build_btc(m1):
    df = m1[['open', 'high', 'low', 'close']].copy()
    ts = epoch_s(df.index)  # bar open, epoch s
    df['ts'] = ts
    day = ts // 86400
    df['sess'] = day
    res = {}
    for tf in MIN_TFS:
        s = tf * 60
        o = (ts // s) * s
        df['k'] = o
        df['to'] = o
        df['tc'] = o + s
        res[str(tf)] = agg(df, 'k', 'to', 'tc', 'sess')
    # D
    df['k'] = day
    df['to'] = day * 86400
    df['tc'] = day * 86400 + 86400
    res['D'] = agg(df, 'k', 'to', 'tc', 'sess')
    # W: Monday 00:00 UTC. 1970-01-01 was a Thursday -> Monday offset 3 days.
    wk = (day + 3) // 7
    df['k'] = wk
    df['to'] = wk * 7 * 86400 - 3 * 86400
    df['tc'] = df['to'] + 7 * 86400
    res['W'] = agg(df, 'k', 'to', 'tc', 'sess')
    # M: calendar month
    idx = df.index
    mk = (idx.year * 12 + idx.month - 1).values
    df['k'] = mk
    ms = pd.to_datetime({'year': mk // 12, 'month': mk % 12 + 1, 'day': 1}, utc=True)
    me = pd.to_datetime({'year': (mk + 1) // 12, 'month': (mk + 1) % 12 + 1, 'day': 1}, utc=True)
    df['to'] = epoch_s(pd.DatetimeIndex(ms))
    df['tc'] = epoch_s(pd.DatetimeIndex(me))
    res['M'] = agg(df, 'k', 'to', 'tc', 'sess')
    return res


def build_xau(m1):
    df = m1[['open', 'high', 'low', 'close']].copy()
    ts = epoch_s(df.index)
    et = df.index.tz_convert('America/New_York')
    # minutes since local midnight
    lm = (et.hour * 60 + et.minute).values
    wd = et.dayofweek.values           # Mon=0 .. Sun=6
    # session date: 18:00 ET belongs to the next calendar day
    local_date = et.normalize().tz_localize(None)
    sdate = local_date + pd.to_timedelta((lm >= 18 * 60).astype(int), unit='D')
    sdate = pd.DatetimeIndex(sdate)
    keep = ~((lm >= 17 * 60) & (lm < 18 * 60))           # daily break
    swd = sdate.dayofweek.values
    keep &= swd < 5                                      # sessions Mon..Fri only (Sun 18:00 -> Mon session)
    keep &= ~((wd == 4) & (lm >= 17 * 60))               # nothing after Friday 17:00
    keep &= ~(wd == 5)                                   # Saturday
    keep &= ~((wd == 6) & (lm < 18 * 60))                # Sunday before 18:00
    df = df[keep].copy()
    ts = ts[keep]
    sdate = sdate[keep]
    df['ts'] = ts
    # session start = 18:00 ET on the calendar day before the session date, session end = 17:00 ET on the session date
    s_start_local = (sdate - pd.Timedelta(days=1)) + pd.Timedelta(hours=18)
    s_end_local = sdate + pd.Timedelta(hours=17)
    s_start = s_start_local.tz_localize('America/New_York', ambiguous='NaT', nonexistent='shift_forward').tz_convert('UTC')
    s_end = s_end_local.tz_localize('America/New_York', ambiguous='NaT', nonexistent='shift_forward').tz_convert('UTC')
    s_start = epoch_s(s_start)
    s_end = epoch_s(s_end)
    sid = epoch_s(sdate) // 86400   # days since epoch of the session date
    df['sess'] = sid
    res = {}
    for tf in MIN_TFS:
        s = tf * 60
        k = (ts - s_start) // s
        o = s_start + k * s
        c = np.minimum(o + s, s_end)
        df['k'] = o
        df['to'] = o
        df['tc'] = c
        res[str(tf)] = agg(df, 'k', 'to', 'tc', 'sess')
    df['k'] = sid
    df['to'] = s_start
    df['tc'] = s_end
    res['D'] = agg(df, 'k', 'to', 'tc', 'sess')
    # W: Monday-based week of the session date
    wk = (sid + 3) // 7
    df['k'] = wk
    df['to'] = s_start
    df['tc'] = s_end
    w = df.groupby('k', sort=True)
    res['W'] = pd.DataFrame({'open': w['open'].first(), 'high': w['high'].max(), 'low': w['low'].min(),
                             'close': w['close'].last(), 't_open': w['to'].min(), 't_close': w['tc'].max(),
                             'sess': w['sess'].first()}).reset_index(drop=True)
    mk = (sdate.year * 12 + sdate.month - 1).values
    df['k'] = mk
    m = df.groupby('k', sort=True)
    res['M'] = pd.DataFrame({'open': m['open'].first(), 'high': m['high'].max(), 'low': m['low'].min(),
                             'close': m['close'].last(), 't_open': m['to'].min(), 't_close': m['tc'].max(),
                             'sess': m['sess'].first()}).reset_index(drop=True)
    return res


if __name__ == '__main__':
    pair = sys.argv[1]
    if pair == 'BTC':
        m1 = pd.read_parquet(D + 'raw/btc_1m.parquet')
        res = build_btc(m1)
    else:
        import glob
        parts = [pd.read_parquet(f) for f in sorted(glob.glob(D + 'raw/xau_1m_*.parquet'))]
        m1 = pd.concat(parts).sort_index()
        m1 = m1[~m1.index.duplicated(keep='last')]
        res = build_xau(m1)
    for tf, b in res.items():
        b = b.sort_values('t_open').reset_index(drop=True)
        b.to_parquet(D + f'data/{pair}_{tf}.parquet')
        print(pair, tf, len(b), pd.to_datetime(b.t_open.iloc[0], unit='s'), pd.to_datetime(b.t_close.iloc[-1], unit='s'))
