#!/usr/bin/env bash
# Full-history download for the confirmation test (see PREREGISTRATION.md):
# BTC + 6 other coins, Binance spot 1m klines, 2017-08 .. 2026-10 (monthly files) + 2026-11-01..12 (daily files).
# Zips are kept in data/full/<SYMBOL>/ ; build_npz.py turns them into data/full/<SYMBOL>.npz
set -uo pipefail
cd "$(dirname "$0")"; mkdir -p data/full; cd data/full
B=https://data.binance.vision/data/spot
SYMS="BTCUSDT ETHUSDT BNBUSDT SOLUSDT XRPUSDT DOGEUSDT ADAUSDT"
get() {
  local f; f=$(basename "$1"); local s=${f%%-*}; mkdir -p "$s"
  [ -s "$s/$f" ] && return 0
  if curl -sSf -m 300 --retry 3 --retry-delay 2 -o "$s/$f.part" "$1" 2>/dev/null; then mv "$s/$f.part" "$s/$f"; else rm -f "$s/$f.part"; echo "MISS $f"; fi
}
export -f get
{
  for s in $SYMS; do
    for y in 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
      [ "$y$m" -lt 201708 ] && continue; [ "$y$m" -gt 202610 ] && continue
      echo "$B/monthly/klines/$s/1m/$s-1m-$y-$m.zip"
    done; done
    for d in 01 02 03 04 05 06 07 08 09 10 11 12; do echo "$B/daily/klines/$s/1m/$s-1m-2026-11-$d.zip"; done
  done
} | xargs -P 8 -I{} bash -c 'get "$1"' _ {}
echo "download finished"; du -sh . ; for s in $SYMS; do echo "$s $(ls $s 2>/dev/null | wc -l) files"; done
