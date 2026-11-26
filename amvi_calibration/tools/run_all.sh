#!/bin/sh
# Rebuild the whole AMVI calibration for BTCUSDT from public data. Run from this folder:
#   sh run_all.sh
# About an hour on 4 cores. Needs: python3 with numpy, pandas, pyarrow, numba, requests.
set -e
cd "$(dirname "$0")"
DATA=../data
RES=../results

# 1. data: Binance USDT-M perpetual BTCUSDT, 1-minute bars and funding (public archive)
python3 fetch_1m.py "$DATA" 2020-01 2026-11 BTCUSDT
python3 -c "
import sys; sys.path.insert(0, '../../crypto_lab/tools')
import fetch_binance as fb
fb.funding('BTCUSDT', '2020-01', '2026-11', '$DATA')"

# 2. checks: order scenarios, then the engine against the independent reference versions
python3 test_orders.py
python3 difftest.py both 6 7

# 3. random search per chart timeframe (settings, seed)
for job in "240 16000" "60 16000" "30 16000" "15 16000" "10 12000" "5 12000" "3 8000" "2 8000" "1 6000"; do
    set -- $job
    python3 sweep.py "$1" "$2" 1 "$RES/sweeps"
done

# 4. hold-out tests, plateau test, final evaluation and files
for tf in 1 2 3 5 10 15 30 60 240; do
    python3 holdout.py "$tf" "$RES/sweeps" > "$RES/holdout_${tf}m.txt"
    python3 plateau.py "$tf" "$RES" > "$RES/plateau_${tf}m.txt"
done
python3 report.py "$RES"
