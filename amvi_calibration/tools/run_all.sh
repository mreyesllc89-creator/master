#!/bin/sh
# Rebuild the whole AMVI calibration for BTCUSDT from public data. Run from this folder:
#   sh run_all.sh
# About two hours on 4 cores (half of it the trade-by-trade download, 47 GB streamed and
# reduced to 4 GB). Needs: python3 with numpy, pandas, pyarrow, numba, matplotlib; curl.
set -e
cd "$(dirname "$0")"
DATA=../data
RES=../results
mkdir -p "$RES/sweeps" "$RES/checks"

# 1. data: Binance USDT-M perpetual BTCUSDT (public archive): 1-minute bars, funding, and
#    one-second bars built from the aggregated trades
python3 fetch_1m.py "$DATA" 2020-01 2026-11 BTCUSDT
python3 -c "
import sys; sys.path.insert(0, '../../crypto_lab/tools')
import fetch_binance as fb
fb.funding('BTCUSDT', '2020-01', '2026-11', '$DATA')"
python3 fetch_1s.py "$DATA" 2021-01 2026-10 BTCUSDT 3
python3 fetch_1s.py "$DATA" fill BTCUSDT      # eight days of 2022 are missing from the monthly files

# 2. checks: hand-computed order scenarios; the engine against the two independent reference
#    versions; the second-by-second shortcut against walking every second
python3 test_orders.py > "$RES/checks/test_orders.txt"
python3 difftest.py both 6 7 > "$RES/checks/difftest_default.txt"
python3 difftest.py both 6 11 2023-10-01 2024-01-01 > "$RES/checks/difftest_gap_period.txt"
python3 test_fine.py 12 3 2026-07-01 2026-10-01 > "$RES/checks/test_fine.txt"
python3 test_fine.py 12 4 2021-05-01 2021-07-01 > "$RES/checks/test_fine_2021.txt"

# 3. random search per chart timeframe (settings, seed)
for job in "240 16000" "60 16000" "30 16000" "15 16000" "10 12000" "5 12000" "3 8000" "2 8000" "1 6000"; do
    set -- $job
    python3 sweep.py "$1" "$2" 1 "$RES/sweeps"
done

# 4. hold-out tests and plateau test inside the search window; the pick of a timeframe is
#    fixed here
for tf in 240 60 30 15 10 5 3 2 1; do
    python3 holdout.py "$tf" "$RES/sweeps" > "$RES/holdout_${tf}m.txt"
    python3 plateau.py "$tf" "$RES" > "$RES/plateau_${tf}m.txt"
done

# 5. studies that choose nothing: the inputs one by one, the selection method on the untouched
#    period, what luck alone would produce, the trailing stop
python3 inputs_summary.py "$RES" > /dev/null
python3 untouched_check.py "$RES" > "$RES/untouched_check.txt"
for tf in 240 60 30 15 10 5 3 2 1; do
    python3 luck.py "$tf" "$RES" 1000 > "$RES/luck_${tf}m.txt"
done
for tf in 240 60 30 15 10; do
    python3 trailing_study.py "$tf" "$RES" 300 5 > "$RES/trailing_${tf}m.txt"
done
for tf in 5 3 2 1; do
    python3 trailing_study.py "$tf" "$RES" 200 5 > "$RES/trailing_${tf}m.txt"
done

# 6. final evaluation, verdicts, calibrated files, trade lists, tables, charts, report
python3 report.py "$RES" > "$RES/report_run.log"
python3 check_outputs.py .. > "$RES/checks/check_outputs.txt"     # trade lists and files against the records
python3 charts.py "$RES"
python3 convergence.py "$RES" > "$RES/convergence.txt"
python3 assemble_report.py ..
