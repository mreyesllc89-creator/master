"""One-second bars of a Binance USDT-M perpetual, built from the public aggTrades archive.

usage: python fetch_1s.py <out_dir> <start YYYY-MM> <end YYYY-MM> [symbol] [procs]

Writes one file per month, <out_dir>/sec/<SYM>_1s_<YYYY-MM>.npz:
    sec      int32  epoch seconds (only seconds in which at least one trade happened)
    o h l c  int32  first / highest / lowest / last trade price of that second, times 100

A month is taken from the monthly archive file; a month that has no monthly file yet (the
open month) from its daily files. Every download is checked against the archive's SHA-256.
The trade files are large (0.4 to 1.3 GB per month) and are deleted after conversion.
"""
import hashlib
import os
import subprocess
import sys
import time
import zipfile
from multiprocessing import Pool

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pc

BASE = "https://data.binance.vision/data/futures/um"
NAMES = ["agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id", "transact_time", "is_buyer_maker"]
PRICE_MULT = 100


def months(start, end):
    return [str(p) for p in pd.period_range(start, end, freq="M")]


def download(url, path, tries=6):
    """curl with resume. Returns False when the file does not exist (404)."""
    for k in range(tries):
        r = subprocess.run(["curl", "-sS", "-L", "--fail", "-C", "-", "--max-time", "3600", "-o", path, url],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return True
        if "404" in r.stderr or r.returncode == 22:
            if os.path.exists(path):
                os.remove(path)
            return False
        time.sleep(3 * (k + 1))
    raise RuntimeError(f"download failed: {url}: {r.stderr.strip()}")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def fetch_zip(url, tmp_dir):
    """Download url (a .zip) into tmp_dir and verify its checksum. None when it does not exist."""
    path = os.path.join(tmp_dir, os.path.basename(url))
    if os.path.exists(path):
        os.remove(path)
    if not download(url, path):
        return None
    cpath = path + ".CHECKSUM"
    if download(url + ".CHECKSUM", cpath):
        want = open(cpath).read().split()[0].strip().lower()
        os.remove(cpath)
        got = sha256(path)
        if got != want:
            os.remove(path)
            raise RuntimeError(f"checksum mismatch for {url}")
    return path


def zip_to_seconds(path):
    """(sec, o, h, l, c) of every second that has a trade in an aggTrades zip."""
    z = zipfile.ZipFile(path)
    name = z.namelist()[0]
    with z.open(name) as f:
        head = f.readline()
    has_header = not head[:1].isdigit()
    S, O, H, L, C = [], [], [], [], []
    with z.open(name) as f:
        rd = pc.open_csv(
            f,
            read_options=pc.ReadOptions(column_names=NAMES, skip_rows=1 if has_header else 0, block_size=64 << 20),
            convert_options=pc.ConvertOptions(include_columns=["price", "transact_time"],
                                              column_types={"price": pa.float64(), "transact_time": pa.int64()}))
        for b in rd:
            t = b.column("transact_time").to_numpy()
            if t.size == 0:
                continue
            if t[-1] > 10 ** 14:          # microseconds
                t = t // 1000
            px = np.rint(b.column("price").to_numpy() * PRICE_MULT).astype(np.int32)
            sec = (t // 1000).astype(np.int64)
            if (sec[1:] < sec[:-1]).any():
                order = np.argsort(sec, kind="stable")
                sec, px = sec[order], px[order]
            chg = np.flatnonzero(sec[1:] != sec[:-1]) + 1
            starts = np.concatenate((np.zeros(1, np.int64), chg))
            ends = np.concatenate((chg, np.array([sec.size]))) - 1
            s, o, h, l, c = sec[starts], px[starts], np.maximum.reduceat(px, starts), np.minimum.reduceat(px, starts), px[ends]
            if S and S[-1][-1] == s[0]:   # a second split over two blocks
                H[-1][-1] = max(H[-1][-1], h[0])
                L[-1][-1] = min(L[-1][-1], l[0])
                C[-1][-1] = c[0]
                s, o, h, l, c = s[1:], o[1:], h[1:], l[1:], c[1:]
            if s.size:
                S.append(s), O.append(o), H.append(h.copy()), L.append(l.copy()), C.append(c.copy())
    if not S:
        e = np.empty(0, np.int32)
        return e, e, e, e, e
    return merge([(np.concatenate(S), np.concatenate(O), np.concatenate(H), np.concatenate(L), np.concatenate(C))])


def merge(parts):
    """Concatenate (sec, o, h, l, c) parts; seconds that occur twice or out of order are combined."""
    sec = np.concatenate([p[0] for p in parts]).astype(np.int64)
    o, h, l, c = (np.concatenate([p[k] for p in parts]).astype(np.int32) for k in (1, 2, 3, 4))
    if sec.size and (sec[1:] <= sec[:-1]).any():
        order = np.argsort(sec, kind="stable")
        sec, o, h, l, c = sec[order], o[order], h[order], l[order], c[order]
        chg = np.flatnonzero(sec[1:] != sec[:-1]) + 1
        starts = np.concatenate((np.zeros(1, np.int64), chg))
        ends = np.concatenate((chg, np.array([sec.size]))) - 1
        sec, o, h, l, c = sec[starts], o[starts], np.maximum.reduceat(h, starts), np.minimum.reduceat(l, starts), c[ends]
    return sec.astype(np.int32), o, h, l, c


def do_month(args):
    sym, ym, out = args
    t0 = time.time()
    sec_dir = os.path.join(out, "sec")
    tmp_dir = os.path.join(out, "tmp_1s")
    os.makedirs(sec_dir, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)
    dest = os.path.join(sec_dir, f"{sym}_1s_{ym}.npz")
    if os.path.exists(dest):
        return f"{ym}: already there"
    parts, src = [], "monthly"
    path = fetch_zip(f"{BASE}/monthly/aggTrades/{sym}/{sym}-aggTrades-{ym}.zip", tmp_dir)
    if path is not None:
        parts.append(zip_to_seconds(path))
        os.remove(path)
    else:
        src = "daily"
        for d in pd.date_range(f"{ym}-01", pd.Period(ym, freq="M").end_time.normalize(), freq="D"):
            path = fetch_zip(f"{BASE}/daily/aggTrades/{sym}/{sym}-aggTrades-{d:%Y-%m-%d}.zip", tmp_dir)
            if path is None:
                continue
            parts.append(zip_to_seconds(path))
            os.remove(path)
        src = f"daily x{len(parts)}"
    if not parts:
        return f"{ym}: no files"
    sec, o, h, l, c = merge(parts)
    np.savez(dest + ".tmp.npz", sec=sec, o=o, h=h, l=l, c=c)
    os.replace(dest + ".tmp.npz", dest)
    return f"{ym}: {sec.size:,} seconds with trades ({src}) in {time.time() - t0:.0f}s"


if __name__ == "__main__":
    out, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
    sym = sys.argv[4] if len(sys.argv) > 4 else "BTCUSDT"
    procs = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    jobs = [(sym, ym, out) for ym in months(start, end)][::-1]    # newest first
    with Pool(procs) as pool:
        for msg in pool.imap_unordered(do_month, jobs):
            print(msg, flush=True)
    print("done", flush=True)
