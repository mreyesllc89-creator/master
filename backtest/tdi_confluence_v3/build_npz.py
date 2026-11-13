"""Turn the downloaded Binance kline zips (data/full/<SYMBOL>/*.zip) into one data/full/<SYMBOL>.npz per symbol
and print a data-quality report (range, missing minutes, largest gaps, missing months).

    python3 build_npz.py                 # all symbols found in data/full
    python3 build_npz.py BTCUSDT ...     # selected symbols
    python3 build_npz.py --insample      # data/full/BTCUSDT_insample.npz from the CSVs used so far (2024-11 .. 2026-11-12)
"""
import glob, os, re, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FULL = os.path.join(HERE, "data", "full")


def read_klines(path):
    """open time (ms), o, h, l, c from one Binance kline file (zip or csv; with or without header)."""
    d = pd.read_csv(path, header=None, usecols=[0, 1, 2, 3, 4], dtype=str)
    d = d.apply(pd.to_numeric, errors="coerce").dropna()
    t = d[0].to_numpy().astype("int64")
    t = np.where(t > 10 ** 14, t // 1000, t)          # Binance spot switched to microseconds in 2025
    return t, d[1].to_numpy(float), d[2].to_numpy(float), d[3].to_numpy(float), d[4].to_numpy(float)


def assemble(files):
    parts = [read_klines(f) for f in files]
    t, o, h, l, c = (np.concatenate([p[i] for p in parts]) for i in range(5))
    order = np.argsort(t, kind="stable")
    t, o, h, l, c = t[order], o[order], h[order], l[order], c[order]
    keep = np.r_[True, np.diff(t) > 0]                 # drop duplicate timestamps
    return t[keep], o[keep], h[keep], l[keep], c[keep]


def report(sym, t, o, h, l, c, files):
    idx = pd.to_datetime(t, unit="ms", utc=True)
    m = t // 60000                                     # minute index: off-grid stamps count in the minute they start in
    gaps = np.maximum(np.diff(m) - 1, 0)
    big = np.argsort(gaps)[::-1][:5]
    print(f"\n{sym}: {len(t):,} bars  {idx[0]} -> {idx[-1]}  files {len(files)}")
    print(f"  off-grid timestamps: {(t % 60000 != 0).sum()}  bad OHLC rows: {((h < l) | (h < o) | (h < c) | (l > o) | (l > c) | (l <= 0)).sum()}")
    print(f"  missing minutes: {int(gaps.sum()):,} ({100 * gaps.sum() / (len(t) + gaps.sum()):.3f}%) in {(gaps > 0).sum()} gaps; largest:")
    for i in big:
        if gaps[i] > 0:
            print(f"    {idx[i]} -> {idx[i + 1]}  ({int(gaps[i])} min)")
    months = sorted({m for f in files for m in re.findall(r"-1m-(\d{4}-\d{2})\.zip$", f)})
    if months:
        exp = [str(p) for p in pd.period_range(months[0], months[-1], freq="M")]
        miss = sorted(set(exp) - set(months))
        print(f"  monthly files {months[0]} .. {months[-1]}; missing inside range: {miss if miss else 'none'}")


def main():
    args = sys.argv[1:]
    if args[:1] == ["--insample"]:
        files = sorted(glob.glob(os.path.join(HERE, "data", "BTCUSDT-1m-*.csv")))
        t, o, h, l, c = assemble(files)
        os.makedirs(FULL, exist_ok=True)
        np.savez_compressed(os.path.join(FULL, "BTCUSDT_insample.npz"), t=t, o=o, h=h, l=l, c=c)
        report("BTCUSDT_insample", t, o, h, l, c, files)
        return
    syms = args or sorted(d for d in os.listdir(FULL) if os.path.isdir(os.path.join(FULL, d)))
    for sym in syms:
        files = sorted(glob.glob(os.path.join(FULL, sym, f"{sym}-1m-*.zip")), key=lambda f: (len(os.path.basename(f)), f))
        monthly = [f for f in files if re.search(r"-1m-\d{4}-\d{2}\.zip$", f)]
        daily = [f for f in files if re.search(r"-1m-\d{4}-\d{2}-\d{2}\.zip$", f)]
        t, o, h, l, c = assemble(sorted(monthly) + sorted(daily))
        np.savez_compressed(os.path.join(FULL, f"{sym}.npz"), t=t, o=o, h=h, l=l, c=c)
        report(sym, t, o, h, l, c, monthly + daily)


if __name__ == "__main__":
    main()
