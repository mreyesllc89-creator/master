#!/bin/bash
S=/tmp/claude-0/-home-user-master/132b1502-5b33-502e-bebd-2c02a6cae884/scratchpad
rm -rf /home/user/fx-data/fx-data-xauusd-ds
for y in 2017 2016 2015 2014 2013 2012 2011; do
  echo "=== $y $(date)"
  d=/home/user/fx-data/xau-$y
  rm -rf "$d"
  for attempt in 1 2 3; do
    GIT_LFS_SKIP_SMUDGE=1 git clone -q --depth 1 --branch XAUUSD-$y https://github.com/FX-Data/fx-data-xauusd-ds "$d" && break
    echo "clone failed attempt $attempt"; sleep 10
  done
  python3 -I $S/tools/convert_ticks.py "$d/XAUUSD" "$S/data/xauusd_m1_$y.npz" 2>&1 | tail -1
  rm -rf "$d"
done
echo "=== DONE $(date)"
