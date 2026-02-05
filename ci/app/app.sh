#!/usr/bin/env bash
set -e

CMD="$1"

APP_DIR="$(cd "$(dirname "$0")" && pwd)"

case "$CMD" in
  --self-test)
    echo "[app] running self-test..."

    # 1. Required files
    if [ ! -f "$APP_DIR/version.txt" ]; then
      echo "[app] FAIL: version.txt missing"
      exit 1
    fi

    # 2. Version format check
    VERSION=$(cat "$APP_DIR/version.txt")
    if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      echo "[app] FAIL: invalid version: $VERSION"
      exit 1
    fi

    # 3. Optional: simulate failure
    if [ -f "$APP_DIR/FAIL" ]; then
      echo "[app] FAIL: forced failure file detected at $APP_DIR/FAIL"
      exit 1
    else
      echo "[app] No FAIL file found at $APP_DIR/FAIL. Contents: $(ls $APP_DIR)"
    fi

    echo "[app] self-test OK"
    exit 0
    ;;

  start)
    echo "[app] starting application version $(cat "$APP_DIR/version.txt")"
    while true; do
      sleep 60
    done
    ;;

  *)
    echo "Usage: $0 [--self-test|start]"
    exit 1
    ;;
esac