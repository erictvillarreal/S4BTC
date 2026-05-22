#!/usr/bin/env bash
set -e

BASE_URL="https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1h"
OUT_DIR="data/raw_backfill"

mkdir -p $OUT_DIR

echo "======================================="
echo "DOWNLOADING BTCUSDT 1H MONTHLY DATA"
echo "======================================="

for YEAR in 2022 2023 2024 2025 2026
do
  for MONTH in 01 02 03 04 05 06 07 08 09 10 11 12
  do
    FILE="BTCUSDT-1h-${YEAR}-${MONTH}.zip"
    URL="${BASE_URL}/${FILE}"

    echo ""
    echo "[DOWNLOAD] $FILE"

    wget -nc -P $OUT_DIR $URL || true
  done
done

echo ""
echo "======================================="
echo "DOWNLOAD COMPLETE"
echo "======================================="

find $OUT_DIR -iname "*.zip" | wc -l
