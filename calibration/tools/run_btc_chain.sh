#!/bin/bash
S=/tmp/claude-0/-home-user-master/132b1502-5b33-502e-bebd-2c02a6cae884/scratchpad
while ! grep -q "\[btc1\] done" $S/data/btc_stage1.log; do sleep 15; done
cd $S && python3 -I tools/btc_stage2.py > data/btc_stage2.log 2>&1
python3 -I tools/btc_stage3.py 5000 > data/btc_stage3.log 2>&1
