#!/usr/bin/env python3
"""
Price data at the finest grain available, for the tick-accurate replay of the trailing stops (hump_tick.py).

  duk  <inst> <out_dir> <start YYYY-MM-DD> <end YYYY-MM-DD> [connections=6] [rounds=400]
       Dukascopy hourly tick files (bid and ask of every tick, UTC). Saved per month as <out_dir>/<inst>_<YYYY-MM>.npz with
       t (int64, epoch milliseconds UTC), bid and ask (int32, price x 1000 for XAUUSD). An hour counts as done only when the
       server answered 200 and the content decodes as whole 20-byte ticks, or 404 (no ticks: empty). Saturdays are skipped.
  bin  <out_dir> <first YYYY-MM> <last YYYY-MM> <last day YYYY-MM-DD>
       Binance BTCUSDT one-second klines (monthly files, then daily files for the last month up to the last day). Saved per
       month as <out_dir>/BTCUSDT_<YYYY-MM>.npz with t (int64, epoch seconds UTC) and o, h, l, c (int32, price x 100).
       Each zip is converted and deleted at once to keep the disk free.
"""
import datetime as dt, io, lzma, os, subprocess, sys, time, zipfile
import numpy as np

UA = ["-A", "Mozilla/5.0"]


def duk(inst, out, a, b, conns=6, rounds=400):
    a, b = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    os.makedirs(out, exist_ok=True)
    raw_dir = os.path.join(out, "_raw"); os.makedirs(raw_dir, exist_ok=True)
    div = {"XAUUSD": 1000.0, "EURUSD": 100000.0, "USA500IDXUSD": 1000.0}[inst]
    months = sorted({(d.year, d.month) for d in (a + dt.timedelta(days=i) for i in range((b - a).days + 1))})
    for (y, m) in months:
        dest = os.path.join(out, f"{inst}_{y}-{m:02d}.npz")
        if os.path.exists(dest):
            continue
        days = [d for d in (dt.date(y, m, 1) + dt.timedelta(days=i) for i in range(31)) if d.month == m and a <= d <= b and d.weekday() != 5]
        todo = [(d, h) for d in days for h in range(24) if not os.path.exists(os.path.join(raw_dir, f"{d.isoformat()}_{h:02d}.bi5"))]
        for rnd in range(rounds):
            if not todo:
                break
            batch = todo[:400]
            cfg = os.path.join(raw_dir, f"_curl_{os.getpid()}.cfg")
            with open(cfg, "w") as f:
                for d, h in batch:
                    f.write(f'url = "https://datafeed.dukascopy.com/datafeed/{inst}/{d.year}/{d.month - 1:02d}/{d.day:02d}/{h:02d}h_ticks.bi5"\n'
                            f'output = "{raw_dir}/{d.isoformat()}_{h:02d}.bi5.tmp"\n')
            r = subprocess.run(["curl", "-sS", "--http1.1", *UA, "--parallel", "--parallel-max", str(conns), "--max-time", "120", "-K", cfg,
                                "-w", "%{http_code}\t%{filename_effective}\n"], capture_output=True, text=True)
            codes = dict(reversed(line.split("\t")) for line in r.stdout.splitlines() if line.count("\t") == 1)
            left = []
            for d, h in batch:
                fn = os.path.join(raw_dir, f"{d.isoformat()}_{h:02d}.bi5"); tmp = fn + ".tmp"; code = codes.get(tmp, "000"); good = False
                if code == "200" and os.path.exists(tmp):
                    try:
                        raw = open(tmp, "rb").read()
                        if len(raw) == 0 or len(lzma.decompress(raw)) % 20 == 0:
                            os.replace(tmp, fn); good = True
                    except Exception:
                        pass
                elif code == "404":
                    open(fn, "wb").close(); good = True
                if os.path.exists(tmp):
                    os.remove(tmp)
                if not good:
                    left.append((d, h))
            todo = left + todo[400:]
            print(f"{inst} {y}-{m:02d} round {rnd + 1}: {len(todo)} hours left", flush=True)
            if len(left) == len(batch):
                time.sleep(20)
        if todo:
            raise SystemExit(f"{inst} {y}-{m:02d}: {len(todo)} hours could not be fetched")
        ts, bids, asks = [], [], []
        for d in days:
            for h in range(24):
                fn = os.path.join(raw_dir, f"{d.isoformat()}_{h:02d}.bi5")
                raw = open(fn, "rb").read()
                if not raw:
                    continue
                x = np.frombuffer(lzma.decompress(raw), dtype=">i4").reshape(-1, 5)
                base = int(dt.datetime(d.year, d.month, d.day, h, tzinfo=dt.timezone.utc).timestamp() * 1000)
                ts.append(base + x[:, 0].astype(np.int64)); asks.append(x[:, 1].astype(np.int32)); bids.append(x[:, 2].astype(np.int32))
        t = np.concatenate(ts) if ts else np.zeros(0, np.int64)
        bid = np.concatenate(bids) if bids else np.zeros(0, np.int32); ask = np.concatenate(asks) if asks else np.zeros(0, np.int32)
        o = np.argsort(t, kind="stable"); t, bid, ask = t[o], bid[o], ask[o]
        np.savez_compressed(dest + ".tmp.npz", t=t, bid=bid, ask=ask, divisor=np.float64(div))
        os.replace(dest + ".tmp.npz", dest)
        for d in days:
            for h in range(24):
                fn = os.path.join(raw_dir, f"{d.isoformat()}_{h:02d}.bi5")
                if os.path.exists(fn):
                    os.remove(fn)
        print(f"{inst} {y}-{m:02d}: {len(t):,} ticks saved", flush=True)
    print("DUK_TICKS_DONE", inst, flush=True)


def binance(out, first, last, last_day):
    os.makedirs(out, exist_ok=True)
    y0, m0 = map(int, first.split("-")); y1, m1 = map(int, last.split("-")); ld = dt.date.fromisoformat(last_day)
    months = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        months.append((y, m)); y, m = (y + (m == 12), m % 12 + 1)
    for (y, m) in months:
        dest = os.path.join(out, f"BTCUSDT_{y}-{m:02d}.npz")
        if os.path.exists(dest):
            continue
        monthly = (y, m) != (ld.year, ld.month)
        urls = ([f"https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1s/BTCUSDT-1s-{y}-{m:02d}.zip"] if monthly else
                [f"https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1s/BTCUSDT-1s-{y}-{m:02d}-{d:02d}.zip" for d in range(1, ld.day + 1)])
        parts = []
        for url in urls:
            zp = os.path.join(out, "_part.zip")
            for attempt in range(6):
                r = subprocess.run(["curl", "-sS", "--fail", "--max-time", "900", "-o", zp, url])
                if r.returncode == 0:
                    break
                time.sleep(10 * (attempt + 1))
            else:
                raise SystemExit(f"cannot fetch {url}")
            with zipfile.ZipFile(zp) as z:
                raw = z.read(z.namelist()[0])
            os.remove(zp)
            a = np.loadtxt(io.BytesIO(raw), delimiter=",", usecols=(0, 1, 2, 3, 4), dtype=np.float64, ndmin=2)
            parts.append(a)
        a = np.concatenate(parts)
        t = a[:, 0].astype(np.int64)
        t = np.where(t > 10 ** 14, t // 1000000, t // 1000)            # microseconds from 2025, milliseconds before
        px = np.round(a[:, 1:5] * 100).astype(np.int32)
        o = np.argsort(t, kind="stable"); t, px = t[o], px[o]
        keep = np.r_[True, np.diff(t) > 0]
        t, px = t[keep], px[keep]
        np.savez_compressed(dest + ".tmp.npz", t=t, o=px[:, 0], h=px[:, 1], l=px[:, 2], c=px[:, 3])
        os.replace(dest + ".tmp.npz", dest)
        print(f"BTCUSDT {y}-{m:02d}: {len(t):,} seconds saved", flush=True)
    print("BINANCE_1S_DONE", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "duk":
        duk(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], *(int(x) for x in sys.argv[6:8]))
    elif sys.argv[1] == "bin":
        binance(*sys.argv[2:6])
