#!/bin/sh
# $1 clock, $2 read
cd "$(dirname "$0")/.."
for tf in 5 15 30 60 120 240 480 1440; do echo $tf; done | xargs -P 2 -I{} sh -c "../calib_venv/bin/python wf/wf_grid.py {} $1 $2 real all > wf/out/log_grid_{}_$1_$2.txt 2>&1 && ../calib_venv/bin/python wf/wf_select.py {} $1 $2 real > wf/out/log_sel_{}_$1_$2.txt 2>&1; echo grid+select {} $1 $2 \$?"
