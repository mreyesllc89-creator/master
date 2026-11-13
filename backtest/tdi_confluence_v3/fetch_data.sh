#!/usr/bin/env bash
# Downloads Binance BTCUSDT 1m klines into ./data: Apr-Oct 2026 (monthly) + Nov 1-12 2026 (daily)
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p data; cd data
B=https://data.binance.vision/data/spot
for m in 2026-04 2026-05 2026-06 2026-07 2026-08 2026-09 2026-10; do
  curl -sSf -O "$B/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-$m.zip"; unzip -oq "BTCUSDT-1m-$m.zip"; rm "BTCUSDT-1m-$m.zip"
done
for d in $(seq -w 1 12); do
  curl -sSf -O "$B/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2026-11-$d.zip"; unzip -oq "BTCUSDT-1m-2026-11-$d.zip"; rm "BTCUSDT-1m-2026-11-$d.zip"
done
