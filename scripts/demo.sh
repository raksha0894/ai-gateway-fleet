#!/usr/bin/env bash
set -e

echo "Starting system..."
docker compose down -v
docker compose up -d --build

sleep 10
OTA_DIR="$(cd "$(dirname "$0")/../dashboard/ota" && pwd)"

if [ ! -w "$OTA_DIR" ]; then
  echo "Fixing permissions on $OTA_DIR"
  sudo chown -R "$USER":"$USER" "$OTA_DIR"
fi
echo "Publishing OTA..."
if [[ "${1:-}" == "--rebuild" ]]; then
  if [[ -z "${COSIGN_PASSWORD:-}" ]]; then
    echo "[demo] COSIGN_PASSWORD not set. Run:"
    echo "  COSIGN_PASSWORD='...' ./demo.sh --rebuild"
    exit 1
  fi

  echo "[demo] Rebuilding + signing OTA artifacts..."
  ./build_ota.sh
  ./publish_ota.sh
else
  echo "[demo] Using prebuilt signed artifacts (no secrets needed)..."
  cp -f ../ci/out/* ../dashboard/ota/
fi
sleep 5

echo "Simulating WAN offline..."
docker network disconnect ai-gateway-fleet_wan_net ai-gateway-fleet-gateway-1
sleep 20

echo "Restoring WAN: Online... [NOW]"
docker network connect ai-gateway-fleet_wan_net ai-gateway-fleet-gateway-1
sleep 20

# Follow robot logs
echo "[demo] Follow Robot logs..."
set +e
timeout 1m docker compose logs -f robot
set -e

# Get current version
NEW_VERSION=$(docker compose exec -T robot cat /app/state/current/version.txt)

# Wait for dashboard
COUNT=0

while [ "$COUNT" -lt 5 ]; do
  if curl -fsS http://localhost:8080/status | grep -q "$NEW_VERSION"; then
    COUNT=$((COUNT + 1))
  fi
  sleep 2
done
echo "[demo] Updated metrics from the dashboard..."
sleep 5
curl -fsS http://localhost:8080/status
echo "[demo] OTA verified successfully..."