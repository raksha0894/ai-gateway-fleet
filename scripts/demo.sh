#!/usr/bin/env bash
set -e
echo "1.90.0" > ../VERSION
echo "Starting system..."
docker compose down -v
docker compose up -d --build

sleep 10

echo "Publishing OTA..."
./build_ota.sh
./publish_ota.sh

sleep 5

echo "Simulating WAN offline..."
docker network disconnect ai-gateway-fleet_wan_net ai-gateway-fleet-gateway-1

sleep 20

echo "Restoring WAN: Online... [NOW]"
docker network connect ai-gateway-fleet_wan_net ai-gateway-fleet-gateway-1

sleep 20

echo "Watching robot logs..."
docker compose logs robot --tail=100

echo "Checking dashboard..."
curl http://localhost:8080/status