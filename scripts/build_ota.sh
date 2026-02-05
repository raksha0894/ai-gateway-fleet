#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Accept version from env, else from file
VERSION_FILE_1="$ROOT/VERSION"
VERSION_FILE_2="$ROOT/scripts/VERSION"
VERSION_FILE_3="$ROOT/ci/app/version.txt"

if [[ -n "${VERSION:-}" ]]; then
  VER="$VERSION"
elif [[ -f "$VERSION_FILE_1" ]]; then
  VER="$(cat "$VERSION_FILE_1" | tr -d ' \n\r')"
elif [[ -f "$VERSION_FILE_2" ]]; then
  VER="$(cat "$VERSION_FILE_2" | tr -d ' \n\r')"
elif [[ -f "$VERSION_FILE_3" ]]; then
  VER="$(cat "$VERSION_FILE_3" | tr -d ' \n\r')"
else
  echo "ERROR: No version file found. Create one of:"
  echo "  - ./VERSION (preferred)"
  echo "  - ./scripts/VERSION"
  echo "  - ./ci/app/version.txt"
  exit 1
fi

OUT="$ROOT/ci/out"
SRC="$ROOT/ci/app"
KEY="$ROOT/keys/cosign.key"

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
if [[ ! -f "$KEY" ]]; then
  echo "ERROR: cosign key not found at $KEY"
  echo "Generate once: cosign generate-key-pair --output-key-prefix keys/cosign"
  exit 1
fi

cosign sign-blob \
  --key "$KEY" \
  --bundle "$OUT/$BUNDLE" \
  "$OUT/$ART"

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