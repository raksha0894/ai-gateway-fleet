#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/ci/out"
DEST="$ROOT/dashboard/ota"

if [[ ! -f "$OUT/manifest.json" ]]; then
  echo "ERROR: manifest.json not found in $OUT"
  echo "Run: ./scripts/build_ota.sh"
  exit 1
fi

mkdir -p "$DEST"

cp -v "$OUT/"* "$DEST/"

echo "[publish_ota] Published OTA artifacts to $DEST"
ls -lh "$DEST"