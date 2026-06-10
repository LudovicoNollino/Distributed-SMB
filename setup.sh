#!/usr/bin/env bash
# Loads the Distributed SMB Docker images from the bundled tar.gz files.
# Run this once per machine before starting the game.
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Loading distributed-smb-lobby"
docker load < smb-lobby.tar.gz

echo "==> Loading distributed-smb-gameevents"
docker load < smb-gameevents.tar.gz

echo "==> Done. Images available:"
docker images | grep -E "distributed-smb-(lobby|gameevents)"
