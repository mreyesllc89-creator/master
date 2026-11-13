#!/usr/bin/env python3
"""Download Dukascopy XAUUSD one-minute BID and ASK candles (bi5) with retries.
Usage: python3 duk_download.py <out_dir> <start YYYY-MM-DD> <end YYYY-MM-DD>
Dukascopy months are 0-based in the URL. Empty days (weekends, holidays) are recorded as 0-byte files."""
import datetime as dt, os, subprocess, sys, time
out, a, b = sys.argv[1], dt.date.fromisoformat(sys.argv[2]), dt.date.fromisoformat(sys.argv[3])
os.makedirs(out, exist_ok=True)
d = a; todo = []
while d <= b:
    if d.weekday() != 5:                       # no Saturday data
        for side in ("BID", "ASK"):
            todo.append((d, side))
    d += dt.timedelta(days=1)
fails = 0
for d, side in todo:
    fn = f"{out}/{d.isoformat()}_{side}.bi5"
    if os.path.exists(fn):
        continue
    url = f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{d.year}/{d.month - 1:02d}/{d.day:02d}/{side}_candles_min_1.bi5"
    ok = False
    for attempt in range(12):
        r = subprocess.run(["curl", "-sS", "--http1.1", "-A", "Mozilla/5.0", "-o", fn + ".tmp", "-w", "%{http_code}",
                            "--max-time", "40", url], capture_output=True, text=True)
        code = r.stdout.strip()[-3:]
        if code == "200":
            os.replace(fn + ".tmp", fn); ok = True; break
        if code == "404":
            open(fn, "wb").close(); ok = True; break
        time.sleep(min(1 + attempt, 6))
    if not ok:
        fails += 1
        print("FAILED", d, side, flush=True)
print("done; failed:", fails, flush=True)
