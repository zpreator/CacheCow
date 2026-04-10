#!/usr/bin/env bash
set -euo pipefail

IMAGE="ghcr.io/zpreator/cachecow:latest"
INSTALL_DIR="$HOME/.cachecow"

echo "CacheCow Server Installer"
echo "========================="
echo ""

if ! command -v docker &>/dev/null; then
  echo "Error: Docker is not installed."
  echo "  https://docs.docker.com/get-docker/"
  exit 1
fi

read -rp "Path to store downloaded videos [${HOME}/Videos]: " DOWNLOAD_PATH
DOWNLOAD_PATH="${DOWNLOAD_PATH:-$HOME/Videos}"
mkdir -p "$DOWNLOAD_PATH"

read -rp "Port [8501]: " PORT
PORT="${PORT:-8501}"

read -rp "Timezone (e.g. America/New_York) [UTC]: " TZ
TZ="${TZ:-UTC}"

mkdir -p "$INSTALL_DIR"

cat > "$INSTALL_DIR/docker-compose.yml" << EOF
services:
  web:
    image: ${IMAGE}
    ports:
      - "${PORT}:8501"
    volumes:
      - cachecow-data:/app/data
      - ${DOWNLOAD_PATH}:${DOWNLOAD_PATH}
    environment:
      - PYTHONUNBUFFERED=1
      - TZ=${TZ}
      - DOWNLOAD_PATH=${DOWNLOAD_PATH}
    restart: unless-stopped

volumes:
  cachecow-data:
EOF

echo ""
echo "Pulling CacheCow image..."
docker compose -f "$INSTALL_DIR/docker-compose.yml" pull

echo "Starting CacheCow..."
docker compose -f "$INSTALL_DIR/docker-compose.yml" up -d

echo ""
echo "CacheCow is running at http://$(hostname -I | awk '{print $1}'):${PORT}"
echo "Default login: admin / admin  (change this in Settings)"
echo ""
echo "To stop:   docker compose -f $INSTALL_DIR/docker-compose.yml down"
echo "To update: docker compose -f $INSTALL_DIR/docker-compose.yml pull && docker compose -f $INSTALL_DIR/docker-compose.yml up -d"
