#!/usr/bin/env bash
# Downloads Binance BTCUSDT 1m klines (Apr-Oct 2026) into ./data
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p data; cd data
for m in 2026-04 2026-05 2026-06 2026-07 2026-08 2026-09 2026-10; do
  curl -sSf -O "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-$m.zip"
  unzip -oq "BTCUSDT-1m-$m.zip" && rm "BTCUSDT-1m-$m.zip"
done
