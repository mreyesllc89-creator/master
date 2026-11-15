#!/usr/bin/env python3
"""check_hf_sizes.py -- do the quote sizes of the Hugging Face parquet copy (data/hf, Nov 2025 - May 2026) behave like the
sizes in the raw Dukascopy hourly files (data/raw, Sep - Nov 2026)?  Companion of probe_flow_proxy.py (which reads only data/raw).

usage:  python3 -I check_hf_sizes.py <repo_path> [parquet_file_name=XAUUSD-2026-03-part0002.parquet] [max_ticks=2000000]
reads   <repo_path>/data/hf/<parquet_file_name>  (one file, first max_ticks rows)  and 40 random non-empty hours of <repo_path>/data/raw
writes  probe_flow_proxy_sizes_check.csv next to this script
"""
import glob
import lzma
import os
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
REC = np.dtype([("ms", ">u4"), ("ask", ">u4"), ("bid", ">u4"), ("av", ">f4"), ("bv", ">f4")])


def summarise(name, av, bv):
    si = (bv - av) / (bv + av)
    mode_a = pd.Series(np.round(av, 6)).mode()[0]
    mode_b = pd.Series(np.round(bv, 6)).mode()[0]
    return dict(source=name, ticks=len(av), ask_size_unique=len(np.unique(np.round(av, 6))), bid_size_unique=len(np.unique(np.round(bv, 6))),
                ask_size_modal_value=float(mode_a), ask_size_modal_share=float((np.round(av, 6) == mode_a).mean()),
                bid_size_modal_value=float(mode_b), bid_size_modal_share=float((np.round(bv, 6) == mode_b).mean()),
                ask_size_p50=float(np.percentile(av, 50)), ask_size_p99=float(np.percentile(av, 99)),
                bid_size_p50=float(np.percentile(bv, 50)), bid_size_p99=float(np.percentile(bv, 99)),
                imbalance_mean=float(si.mean()), imbalance_sd=float(si.std()), imbalance_exactly_zero_share=float((np.abs(si) < 1e-9).mean()),
                imbalance_p5=float(np.percentile(si, 5)), imbalance_p95=float(np.percentile(si, 95)), corr_ask_bid_size=float(np.corrcoef(av, bv)[0, 1]))


def main():
    repo = sys.argv[1]
    fname = sys.argv[2] if len(sys.argv) > 2 else "XAUUSD-2026-03-part0002.parquet"
    max_ticks = int(sys.argv[3]) if len(sys.argv) > 3 else 2_000_000
    files = [f for f in sorted(glob.glob(os.path.join(repo, "data", "raw", "XAUUSD", "*", "*.bi5"))) if os.path.getsize(f) > 0]
    pick = np.random.default_rng(1).choice(len(files), min(40, len(files)), replace=False)
    av, bv = [], []
    for k in pick:
        a = np.frombuffer(lzma.decompress(open(files[k], "rb").read()), dtype=REC)
        av.append(a["av"].astype(float))
        bv.append(a["bv"].astype(float))
    rows = [summarise("raw Dukascopy hourly files, 40 random hours, Sep-Nov 2026", np.concatenate(av), np.concatenate(bv))]
    t = pq.read_table(os.path.join(repo, "data", "hf", fname)).slice(0, max_ticks).to_pandas()
    rows.append(summarise(f"hf parquet {fname}, first {len(t)} ticks", t.ask_volume.values.astype(float), t.bid_volume.values.astype(float)))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(HERE, "probe_flow_proxy_sizes_check.csv"), index=False, float_format="%.6g")
    pd.set_option("display.width", 250)
    print(out.T.to_string())


if __name__ == "__main__":
    main()
