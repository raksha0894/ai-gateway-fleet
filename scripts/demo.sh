#!/usr/bin/env bash
set -e

echo "Starting system..."
docker compose down -v
docker compose up -d --build

sleep 10
OTA_DIR="$(cd "$(dirname "$0")/../dashboard/ota" && pwd)"

# Check write permission
if [[ ! -w "$OTA_DIR" ]]; then
  echo "[demo] ERROR: No write permission on $OTA_DIR"
  echo "Run once:"
  echo "  sudo chown -R \$USER:\$USER ./dashboard"
  echo "Rerun demo.sh post that."
  exit 1
fi

echo "Simulating WAN offline..."
docker network disconnect ai-gateway-fleet_wan_net ai-gateway-fleet-gateway-1
sleep 20
echo "Publishing OTA..."
if [[ "${1:-}" == "--rebuild" ]]; then
  if [[ -z "${COSIGN_PASSWORD:-}" ]]; then
    echo "[demo] COSIGN_PASSWORD not set. Run:"
    echo "  COSIGN_PASSWORD='...' ./demo.sh --rebuild"
    exit 1
  fi

  echo "[demo] Rebuilding + signing OTA artifacts..."
  ./scripts/build_ota.sh
  ./scripts/publish_ota.sh
else
  echo "[demo] Using prebuilt signed artifacts..."
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  VER="$(tr -d '\r\n\t' < "$ROOT/VERSION")"
  echo "The update version is $VER"
  ./scripts/publish_ota.sh
fi
sleep 5

echo "Restoring WAN: Online..."
docker network connect ai-gateway-fleet_wan_net ai-gateway-fleet-gateway-1
echo "[demo] Gateway trying package download..."
set +e
timeout 1m docker compose logs -f gateway
set -e
echo "Gateway disconnects from WAN again..."
docker network disconnect ai-gateway-fleet_wan_net ai-gateway-fleet-gateway-1
sleep 20

# Follow robot logs
echo "[demo] Robot requests update from gateway. Installs after verification. Rollsback if update is bad.."
echo "[demo] Robot sends metrics to gateway..."
set +e
timeout 1m docker compose logs -f robot
set -e


echo "Restoring WAN: Gateway reconnects and forwards metrics..."
docker network connect ai-gateway-fleet_wan_net ai-gateway-fleet-gateway-1

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
echo "[demo] Dashboard with updated metrics..."
sleep 12
curl -fsS http://localhost:8080/status
echo "[demo] OTA verified successfully..."
