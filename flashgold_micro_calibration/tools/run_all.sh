#!/bin/bash
# Every study of the report, one process at a time: each one loads the whole tick feed (about 7 GB),
# so two at once do not fit in 16 GB. A finished step leaves results/.done_<name>; running the script
# again skips finished steps, so it can be restarted after an interruption.
#
# usage: bash run_all.sh            (from tools/; ticks must be in ../data, see REPORT.md section 13)
cd "$(dirname "$0")" || exit 1
R=../results
step() {   # step <name> <log file> <command...>
  local name=$1 log=$2; shift 2
  [ -f "$R/.done_$name" ] && return 0
  echo "$(date -u +%H:%M:%S) start $name"
  if "$@" > "$log" 2>&1; then touch "$R/.done_$name"; echo "$(date -u +%H:%M:%S) done  $name"; else echo "$(date -u +%H:%M:%S) FAILED $name (see $log)"; fi
}
P="python3 -I"
REF=FlashGold_NativeReference
step selftest          $R/selftest.log          $P selftest.py ../data
step center_final      $R/center_final.log      $P local.py $R/center_final.json $R/center_final.csv
step center_no_trail   $R/center_no_trailing_variant.log $P local.py $R/center_no_trailing_variant.json $R/center_no_trailing_variant.csv
step baseline          $R/baseline.log          $P baseline.py $R
step real_replay       $R/real/real_replay.log  $P real_replay.py $R/real/real_trades_sar.csv $R/real/variants_real.json $R/real/real_replay 3 12
step grid_calibrated   $R/grid_calibrated.log   $P grid2.py $R/center_final.json $R/grid_calibrated.json $R/grid_calibrated.csv
step trailing_cal      $R/study_trailing_calibrated.log $P study.py trailing_cal $REF $R/study_trailing_calibrated.csv 12 $R/center_final.json
step latency           $R/latency.log           $P latency_study.py $R/variants_latency.json $R/latency.csv 0 50 100 150 250 400
step spread            $R/study_spread.log      $P spread_study.py $R/variants_spread.json $R/study_spread.csv 4 8 12 16 24
step oat_calibrated    $R/oat_calibrated.log    $P oat.py $REF $R/oat_calibrated.csv 12 main $R/center_final.json
step oat_native        $R/oat_native_all.log    $P oat.py $REF $R/oat_native_all.csv
step study_trailing    $R/study_trailing.log    $P study.py trailing $REF $R/study_trailing.csv
step study_exits       $R/study_exits.log       $P study.py exits $REF $R/study_exits.csv
step grid_stops        $R/grid_stops.log        $P grid2.py $R/center_stops.json $R/grid_stops.json $R/grid_stops.csv
step oat_micro         $R/oat_micro1s_fg.log    $P oat.py FlashGold_Micro1s $R/oat_micro1s_fg.csv 12 micro
echo "$(date -u +%H:%M:%S) queue finished"
