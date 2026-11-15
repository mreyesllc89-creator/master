"""Fetch monthly tick files of the public Hugging Face dataset CarlosSilva1/xauusd-ticks (CC-BY-4.0)
and convert them to the same monthly npz layout fetch_dukascopy.py writes.

usage: python -I fetch_hf_ticks.py <data_dir> 2025-11 2026-05

The dataset is the Dukascopy XAU/USD feed (3-digit prices, bid/ask volumes, UTC), May 2021 - May 2026:
  Silva, C. (2026). XAU/USD Tick Data (May 2021 - May 2026) [Data set]. Hugging Face.
  https://huggingface.co/datasets/CarlosSilva1/xauusd-ticks
It is a quick way to get history without the hour-by-hour Dukascopy download. Needs pyarrow.
"""
import json
import os
import sys
import urllib.request

import numpy as np
import pandas as pd

REPO = "CarlosSilva1/xauusd-ticks"


def get(url, path=None):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        body = r.read()
    if path:
        with open(path + ".part", "wb") as f:
            f.write(body)
        os.replace(path + ".part", path)
    return body


def months(a, b):
    y, m = (int(x) for x in a.split("-"))
    ye, me = (int(x) for x in b.split("-"))
    while (y, m) <= (ye, me):
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def main(root, first, last):
    raw = os.path.join(root, "hf")
    out = os.path.join(root, "ticks")
    os.makedirs(raw, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    for y, m in months(first, last):
        tree = json.loads(get(f"https://huggingface.co/api/datasets/{REPO}/tree/main/year={y}/month={m:02d}"))
        parts = []
        for item in sorted(tree, key=lambda x: x["path"]):
            if not item["path"].endswith(".parquet"):
                continue
            local = os.path.join(raw, os.path.basename(item["path"]))
            if not os.path.exists(local) or os.path.getsize(local) != item["size"]:
                get(f"https://huggingface.co/datasets/{REPO}/resolve/main/{item['path']}", local)
            parts.append(pd.read_parquet(local, columns=["timestamp", "bid_price", "ask_price"]))
        d = pd.concat(parts, ignore_index=True)
        t = d["timestamp"].astype("datetime64[ms]").astype("int64").to_numpy()
        order = np.argsort(t, kind="stable")
        bid = np.round(d["bid_price"].to_numpy() * 1000.0).astype(np.int32)
        ask = np.round(d["ask_price"].to_numpy() * 1000.0).astype(np.int32)
        np.savez_compressed(os.path.join(out, f"XAUUSD_{y}-{m:02d}.npz"), t=t[order], bid=bid[order], ask=ask[order])
        print(f"{y}-{m:02d}", len(t), "ticks", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
