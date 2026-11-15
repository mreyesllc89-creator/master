"""Download Dukascopy tick history (hourly .bi5 files) and build monthly tick arrays.

usage:
  python -I fetch_dukascopy.py fetch XAUUSD 2025-11-01 2026-11-14 <data_dir> [workers=1] [pause_s=9]
  python -I fetch_dukascopy.py hours XAUUSD <hours.txt> <data_dir> [pause_s=9]     (lines "YYYY-MM-DD HH", UTC, fetched in that order)
  python -I fetch_dukascopy.py build XAUUSD <data_dir> [out_dir] [first_day] [last_day]

fetch: one request per UTC hour, raw files kept in <data_dir>/raw/<SYM>/<YYYY-MM-DD>/<HH>.bi5
       (zero-length file = hour without ticks). Already present files are skipped, so the
       command can be rerun to resume or extend. The feed gives an address an allowance of roughly
       200 requests that refills at about one request per 10 s and answers 503 when it is spent,
       so the default is one keep-alive connection with a 9 s pause (about 400 hours of ticks per
       hour of downloading). Lower the pause if your address is not throttled.
build: <data_dir>/ticks/<SYM>_<YYYY-MM>.npz with t (UTC milliseconds, int64), bid and ask
       (int32, price * 1000). With out_dir and a day range the files go to <out_dir>/ticks instead
       and only those days are used (a separate store for isolated hours, kept out of the main feed).  Each record of a .bi5 file is 20 bytes big endian:
       ms since the hour start, ask, bid (integers, price * 1000 for XAUUSD), ask volume, bid volume.
"""
import datetime as dt
import http.client
import lzma
import os
import sys
import threading
import time
import urllib.parse

import numpy as np

HOST = "datafeed.dukascopy.com"
REC = np.dtype([("ms", ">u4"), ("ask", ">u4"), ("bid", ">u4"), ("av", ">f4"), ("bv", ">f4")])


def hours(start, end):
    cur = dt.datetime.combine(start, dt.time(0))
    stop = dt.datetime.combine(end, dt.time(23))
    while cur <= stop:
        wd = cur.weekday()                      # Mon=0 .. Sun=6; the market is closed Sat and most of Sun
        if not (wd == 5 or (wd == 6 and cur.hour < 20) or (wd == 4 and cur.hour > 22)):
            yield cur
        cur += dt.timedelta(hours=1)


def connect():
    """One keep-alive connection (through HTTPS_PROXY when set). The feed stalls new TLS handshakes
    when asked too fast but serves quickly over an established connection, so connections are reused."""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        u = urllib.parse.urlparse(proxy)
        c = http.client.HTTPSConnection(u.hostname, u.port, timeout=30)
        c.set_tunnel(HOST, 443)
    else:
        c = http.client.HTTPSConnection(HOST, timeout=30)
    c.connect()
    return c


def hour_path(root, sym, h):
    return os.path.join(root, "raw", sym, h.strftime("%Y-%m-%d"), f"{h.hour:02d}.bi5")


def worker(sym, root, jobs, stats, lock, pace):
    conn = None
    for h in jobs:
        path = hour_path(root, sym, h)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = f"/datafeed/{sym}/{h.year}/{h.month - 1:02d}/{h.day:02d}/{h.hour:02d}h_ticks.bi5"   # month is 0-based
        size = -1
        errors = 0
        while errors < 400:                             # hours of patience: a throttled address recovers by itself
            try:
                if conn is None:
                    conn = connect()
                conn.request("GET", url, headers={"User-Agent": "Mozilla/5.0", "Connection": "keep-alive"})
                r = conn.getresponse()
                body = r.read()
                if r.status == 200:
                    if body:
                        lzma.decompress(body)           # validate before keeping the file
                    tmp = path + ".part"
                    with open(tmp, "wb") as f:
                        f.write(body)
                    os.replace(tmp, path)
                    size = len(body)
                    break
                if r.status == 404:
                    open(path, "wb").close()
                    size = 0
                    break
                errors += 1
                time.sleep(180.0)                       # 503: the request allowance is spent, wait for it to refill
            except Exception:
                try:
                    if conn is not None:
                        conn.close()
                except Exception:
                    pass
                conn = None
                errors += 1
                time.sleep(20.0 if errors <= 2 else 600.0)   # refused connections: the address is blocked, probe rarely
        time.sleep(pace)
        with lock:
            stats["done"] += 1
            stats["fail"] += size < 0
            stats["bytes"] += max(size, 0)
            if size < 0:
                print("FAILED", url, flush=True)
            if stats["done"] % 200 == 0:
                print(f"{stats['done']}/{stats['total']} hours, {stats['bytes'] / 1e6:.0f} MB new, "
                      f"{stats['fail']} failed, {time.time() - stats['t0']:.0f}s", flush=True)


def fetch(sym, start, end, root, workers, pace, listed=None):
    if listed is not None:                                        # explicit hours, in the order given
        jobs = listed
    else:
        jobs = [h for h in hours(start, end)][::-1]               # newest first
    jobs = [h for h in jobs if not os.path.exists(hour_path(root, sym, h))]
    stats = {"done": 0, "fail": 0, "bytes": 0, "total": len(jobs), "t0": time.time()}
    lock = threading.Lock()
    print(f"{len(jobs)} hours to fetch", flush=True)
    threads = [threading.Thread(target=worker, args=(sym, root, jobs[i::workers], stats, lock, pace)) for i in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"done {stats['done']} hours, {stats['bytes'] / 1e6:.0f} MB new, {stats['fail']} failed", flush=True)


def build(sym, root, out_root=None, first=None, last=None):
    raw = os.path.join(root, "raw", sym)
    out = os.path.join(out_root or root, "ticks")
    os.makedirs(out, exist_ok=True)
    months = {}
    for day in sorted(os.listdir(raw)):
        if (first and day < first) or (last and day > last):
            continue
        months.setdefault(day[:7], []).append(day)
    for month, days in months.items():
        ts, bids, asks = [], [], []
        for day in days:
            y, m, d = (int(x) for x in day.split("-"))
            for name in sorted(os.listdir(os.path.join(raw, day))):
                if not name.endswith(".bi5"):
                    continue
                p = os.path.join(raw, day, name)
                if os.path.getsize(p) == 0:
                    continue
                a = np.frombuffer(lzma.decompress(open(p, "rb").read()), dtype=REC)
                base = int(dt.datetime(y, m, d, int(name[:2]), tzinfo=dt.timezone.utc).timestamp() * 1000)
                ts.append(base + a["ms"].astype(np.int64))
                bids.append(a["bid"].astype(np.int32))
                asks.append(a["ask"].astype(np.int32))
        if not ts:
            continue
        t = np.concatenate(ts); b = np.concatenate(bids); a = np.concatenate(asks)
        order = np.argsort(t, kind="stable")
        np.savez_compressed(os.path.join(out, f"{sym}_{month}.npz"), t=t[order], bid=b[order], ask=a[order])
        print(month, len(t), "ticks", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "hours":
        wanted = [dt.datetime.strptime(line.strip(), "%Y-%m-%d %H") for line in open(sys.argv[3]) if line.strip()]
        fetch(sys.argv[2], None, None, sys.argv[4], 1, float(sys.argv[5]) if len(sys.argv) > 5 else 9.0, wanted)
    elif sys.argv[1] == "fetch":
        fetch(sys.argv[2], dt.date.fromisoformat(sys.argv[3]), dt.date.fromisoformat(sys.argv[4]), sys.argv[5],
              int(sys.argv[6]) if len(sys.argv) > 6 else 1, float(sys.argv[7]) if len(sys.argv) > 7 else 9.0)
    else:
        build(sys.argv[2], sys.argv[3], *sys.argv[4:7])
