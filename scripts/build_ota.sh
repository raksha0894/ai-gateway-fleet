#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Accept version from VERSION file in the root folder
VER="$(tr -d '\r\n\t' < "$ROOT/VERSION")"

OUT="$ROOT/ci/out"
SRC="$ROOT/ci/app"
KEY="$ROOT/keys/cosign.key"
#Whether to sign artifacts or not (default is true) 
DO_SIGN="${DO_SIGN:-true}"

mkdir -p "$OUT"

ART="app-v${VER}.tar.gz"
BUNDLE="app-v${VER}.tar.gz.bundle"
SHA="app-v${VER}.sha256"
MANIFEST="manifest.json"

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: Source dir not found: $SRC"
  exit 1
fi

echo "[build_ota] VERSION=$VER"
echo "[build_ota] SRC=$SRC"
echo "[build_ota] OUT=$OUT"

# Sync packaged version
echo "$VER" > "$SRC/version.txt"

# Build tarball
tar -C "$SRC" -czf "$OUT/$ART" .

# sha256 file (content is only the hex digest, easy for python)
sha256sum "$OUT/$ART" | awk '{print $1}' > "$OUT/$SHA"

# Cosign sign-blob bundle (offline verification friendly)
if [ "$DO_SIGN" = "true" ]; then
  if [[ ! -f "$KEY" ]]; then
    echo "Set DO_SIGN=false to skip signing."
    exit 1
  fi

  cosign sign-blob \
    --key "$KEY" \
    --bundle "$OUT/$BUNDLE" \
    "$OUT/$ART"
else
  echo "[build_ota] DO_SIGN=false; skipping signing step."
fi

# Manifest (what robot + gateway expect)
cat > "$OUT/$MANIFEST" <<EOF
{
  "version": "$VER",
  "artifact": "$ART",
  "bundle": "$BUNDLE",
  "sha256": "$(cat "$OUT/$SHA")"
}
EOF

echo "[build_ota] Built:"
ls -lh "$OUT/$ART" "$OUT/$SHA" "$OUT/$BUNDLE" "$OUT/$MANIFEST"