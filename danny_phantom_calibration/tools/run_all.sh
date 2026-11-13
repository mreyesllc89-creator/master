#!/usr/bin/env bash
# Full rerun after new data is imported: baseline, stage-1 sweeps, refinement, final tables, presets, docs.
set -e
cd "$(dirname "$0")"
export DP_DATA="${DP_DATA:-$PWD/../data}" DP_CACHE="${DP_CACHE:-/tmp/dp_cache}"
rm -rf "$DP_CACHE"
python -I baseline.py > ../baseline.txt
for s in XAUUSD BTCUSD; do for tf in 5 15 30 60 240 10 3 2 1; do
  n=16000; [ "$tf" -le 3 ] && n=6000
  python -I sweep.py "$s" "$tf" "$n" modern
  python -I refine.py "$s" "$tf" modern 6
done; done
python -I final_eval.py
python -I preset_docs.py
for k in XAUUSD_M60 XAUUSD_M30 XAUUSD_M15 BTCUSD_M240; do python -I trade_report.py "$k"; done
