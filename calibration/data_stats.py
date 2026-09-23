import pandas as pd, numpy as np, glob, os
files = {
 '1': 'calibration/data/BTCUSD_1.csv',
 '15': 'calibration/data/BTCUSD_15.csv',
 '30': 'calibration/data/BTCUSD_30.csv',
 '60': 'calibration/data/BTCUSD_60.csv',
 '240': 'calibration/data/BTCUSD_240.csv',
}
def atr(df, n=14):
    h,l,c = df.high, df.low, df.close
    pc = c.shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    # Wilder RMA
    a = tr.ewm(alpha=1/n, adjust=False).mean()
    return a
def pivots(df, n=5):
    H = df.high.values; L = df.low.values; N=len(df)
    ph = np.full(N, np.nan); pl = np.full(N, np.nan)
    for i in range(n, N-n):
        w = H[i-n:i+n+1]
        if H[i] == w.max() and (w[:n] < H[i]).all() and (w[n+1:] <= H[i]).all():
            ph[i+n] = H[i]   # confirmed n bars later (Pine ta.pivothigh returns at bar i+n)
        w2 = L[i-n:i+n+1]
        if L[i] == w2.min() and (w2[:n] > L[i]).all() and (w2[n+1:] >= L[i]).all():
            pl[i+n] = L[i]
    return ph, pl
for tf, f in files.items():
    df = pd.read_csv(f)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    n = len(df)
    span = df.time.iloc[-1] - df.time.iloc[0]
    a = atr(df)
    atr_pct = (a / df.close * 100)
    rng_pct = ((df.high - df.low)/df.close*100)
    ret = df.close.pct_change()*100
    gaps = (df.open - df.close.shift(1)).abs()/df.close*100
    ph, pl = pivots(df)
    # replicate swingH/swingL forward fill
    sH = pd.Series(ph).ffill(); sL = pd.Series(pl).ffill()
    matchH = np.isclose(sH.values, df['Swing High'].values, equal_nan=True)
    matchL = np.isclose(sL.values, df['Swing Low'].values, equal_nan=True)
    # count comparable rows (both non-nan)
    bothH = ~np.isnan(sH.values) & ~np.isnan(df['Swing High'].values)
    bothL = ~np.isnan(sL.values) & ~np.isnan(df['Swing Low'].values)
    print(f"=== TF {tf}m: {n} bars, {df.time.iloc[0]} -> {df.time.iloc[-1]} span={span}")
    print(f"  close: min {df.close.min():.0f} max {df.close.max():.0f} last {df.close.iloc[-1]:.0f}")
    print(f"  ATR14 abs: median {a.median():.1f}  mean {a.mean():.1f}  p10 {a.quantile(.1):.1f} p90 {a.quantile(.9):.1f}")
    print(f"  ATR14 %:   median {atr_pct.median():.4f}  mean {atr_pct.mean():.4f}  p10 {atr_pct.quantile(.1):.4f} p90 {atr_pct.quantile(.9):.4f}")
    print(f"  bar range %: median {rng_pct.median():.4f} mean {rng_pct.mean():.4f} p90 {rng_pct.quantile(.9):.4f} max {rng_pct.max():.4f}")
    print(f"  |ret| %: median {ret.abs().median():.4f} std {ret.std():.4f}")
    print(f"  gap % (open vs prev close): median {gaps.median():.5f} p95 {gaps.quantile(.95):.5f} max {gaps.max():.5f}")
    print(f"  swingH match: {matchH[bothH].mean()*100:.1f}% of {bothH.sum()} rows; swingL match: {matchL[bothL].mean()*100:.1f}% of {bothL.sum()} rows")
    print(f"  trail non-null rows: {df['Trail'].notna().sum()}")
    # channel width relative to ATR
    chw = (df['Swing High'] - df['Swing Low'])
    print(f"  channel width/ATR: median {(chw/a).median():.2f}, channel width %: median {(chw/df.close*100).median():.3f}")
    # how many pivots
    print(f"  pivot highs: {(~np.isnan(ph)).sum()}, pivot lows: {(~np.isnan(pl)).sum()}")
    # mismatch detail
    mm = np.where(bothH & ~matchH)[0]
    if len(mm): print("  first H mismatches idx:", mm[:5], sH.values[mm[:5]], df['Swing High'].values[mm[:5]])
    mm = np.where(bothL & ~matchL)[0]
    if len(mm): print("  first L mismatches idx:", mm[:5], sL.values[mm[:5]], df['Swing Low'].values[mm[:5]])
