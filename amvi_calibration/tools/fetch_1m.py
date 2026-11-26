"""Fetch Binance USDT-M perpetual 1-minute klines (public bulk archive) for the AMVI calibration.

usage: python fetch_1m.py <out_dir> <start YYYY-MM> <end YYYY-MM> [symbol]
Reuses crypto_lab/tools/fetch_binance.py (monthly files, daily files for the open month,
one parquet per month under <out_dir>/raw/<SYM>_1m, merged to <out_dir>/<SYM>_1m.parquet).
The data directory is git-ignored: re-run this to rebuild it.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "crypto_lab", "tools"))
import fetch_binance as fb  # noqa: E402

if __name__ == "__main__":
    out, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
    sym = sys.argv[4] if len(sys.argv) > 4 else "BTCUSDT"
    os.makedirs(out, exist_ok=True)
    fb.klines(sym, "1m", start, end, out)
