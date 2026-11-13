#!/usr/bin/env bash
# Writes data_manifest.sha256 (SHA-256 of every source zip and every .npz in data/full) and checks every zip
# against the .CHECKSUM file Binance publishes next to it. Reads file bytes only.
set -uo pipefail
cd "$(dirname "$0")"
B=https://data.binance.vision/data/spot
tmp=$(mktemp -d)
( cd data/full && find . -name '*.zip' -o -name '*.npz' | sed 's#^\./##' | sort | xargs -P 4 -n 50 sha256sum ) | sort -k2 | sed 's#  #  data/full/#' > data_manifest.sha256
bad=0; n=0
while read -r h p; do
  case "$p" in *.zip) ;; *) continue;; esac
  f=$(basename "$p"); s=${f%%-*}
  if [[ "$f" =~ -1m-[0-9]{4}-[0-9]{2}-[0-9]{2}\.zip$ ]]; then kind=daily; else kind=monthly; fi
  echo "$B/$kind/klines/$s/1m/$f.CHECKSUM $h $f"
done < data_manifest.sha256 > "$tmp/urls"
check() { local url=$1 want=$2 f=$3; got=$(curl -sSf -m 60 --retry 3 "$url" 2>/dev/null | awk '{print $1}');
  if [ "$got" = "$want" ]; then echo "OK $f"; else echo "MISMATCH $f published=$got local=$want"; fi; }
export -f check
xargs -P 8 -L 1 bash -c 'check "$0" "$1" "$2"' < "$tmp/urls" > "$tmp/res"
echo "zips checked against Binance .CHECKSUM: $(grep -c '^OK' "$tmp/res") OK, $(grep -vc '^OK' "$tmp/res") not OK"
grep -v '^OK' "$tmp/res" | head
echo "manifest: $(wc -l < data_manifest.sha256) files ($(grep -c '\.zip$' data_manifest.sha256) zips, $(grep -c '\.npz$' data_manifest.sha256) npz)"
rm -rf "$tmp"
