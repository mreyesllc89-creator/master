#!/bin/bash
# Fetch Dukascopy XAUUSD tick branches 2011-2018 and aggregate each year to 1m bid/ask OHLC parquet.
set -u
R=/home/user/FX-Data/FX-Data-XAUUSD-DS
OUT=/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/raw
cd $R
for y in 2018 2017 2016 2015 2014 2013 2012 2011; do
  if [ -f $OUT/xau_1m_$y.parquet ]; then echo "skip $y"; continue; fi
  git rev-parse -q --verify x$y >/dev/null || git fetch -q --depth 1 origin XAUUSD-$y:x$y || { echo "fetch fail $y"; continue; }
  rm -rf /tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/tick_$y && mkdir -p /tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/tick_$y
  git archive x$y XAUUSD | tar -x -C /tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/tick_$y
  python3 -I /tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/ticks_to_1m.py /tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/tick_$y $OUT/xau_1m_$y.parquet && rm -rf /tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/tick_$y
  git branch -D x$y >/dev/null 2>&1; git gc -q --prune=now >/dev/null 2>&1
  echo "done $y $(date -u +%H:%M:%S)"
done
echo ALLDONE
