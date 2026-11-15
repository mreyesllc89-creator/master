#!/usr/bin/env python3
"""Download Dukascopy one-minute BID and ASK candles (bi5) for a long date range, several connections at a
time. Instrument: XAUUSD, or the Dukascopy name in DUK_INSTRUMENT (EURUSD, USA500IDXUSD). Dukascopy resets many connections, so the list is worked through in rounds until every file is there.

A file counts as done only when the server answered 200 and the content decodes (LZMA), or when it answered 404
(no data that day: recorded as a 0-byte file). Anything else is retried in the next round.

Usage: python3 duk_download2.py <out_dir> <start YYYY-MM-DD> <end YYYY-MM-DD> [connections=8] [max_rounds=60]
"""
import datetime as dt, lzma, os, subprocess, sys, time

INST = os.environ.get("DUK_INSTRUMENT", "XAUUSD")

out, a, b = sys.argv[1], dt.date.fromisoformat(sys.argv[2]), dt.date.fromisoformat(sys.argv[3])
conns = int(sys.argv[4]) if len(sys.argv) > 4 else 8
max_rounds = int(sys.argv[5]) if len(sys.argv) > 5 else 60
os.makedirs(out, exist_ok=True)
todo = []
d = a
while d <= b:
    if d.weekday() != 5:                       # no Saturday data
        for side in ("BID", "ASK"):
            if not os.path.exists(f"{out}/{d.isoformat()}_{side}.bi5"):
                todo.append((d, side))
    d += dt.timedelta(days=1)
print(f"{len(todo)} files to fetch", flush=True)
for rnd in range(1, max_rounds + 1):
    if not todo:
        break
    batch = todo[:400]
    cfg = os.path.join(out, f"_curl_{os.getpid()}.cfg")          # one list per process: several may share the folder
    with open(cfg, "w") as f:
        for d, side in batch:
            f.write(f'url = "https://datafeed.dukascopy.com/datafeed/{INST}/{d.year}/{d.month - 1:02d}/{d.day:02d}/{side}_candles_min_1.bi5"\n'
                    f'output = "{out}/{d.isoformat()}_{side}.bi5.tmp"\n')
    r = subprocess.run(["curl", "-sS", "--http1.1", "-A", "Mozilla/5.0", "--parallel", "--parallel-max", str(conns), "--max-time", "90",
                        "-K", cfg, "-w", "%{http_code}\t%{filename_effective}\n"], capture_output=True, text=True)
    codes = {}
    for line in r.stdout.splitlines():
        p = line.split("\t")
        if len(p) == 2:
            codes[p[1]] = p[0]
    ok = 0; left = []
    for d, side in batch:
        fn = f"{out}/{d.isoformat()}_{side}.bi5"; tmp = fn + ".tmp"; code = codes.get(tmp, "000")
        good = False
        if code == "200" and os.path.exists(tmp):
            try:
                raw = open(tmp, "rb").read()
                if len(raw) == 0 or len(lzma.decompress(raw)) % 24 == 0:
                    os.replace(tmp, fn); good = True
            except Exception:
                pass
        elif code == "404":
            open(fn, "wb").close(); good = True
        if os.path.exists(tmp):
            os.remove(tmp)
        if good:
            ok += 1
        else:
            left.append((d, side))
    todo = left + todo[400:]
    print(f"round {rnd}: {ok} of {len(batch)} fetched, {len(todo)} left", flush=True)
    if ok == 0:
        time.sleep(20)
print("DONE; missing:", len(todo), flush=True)
