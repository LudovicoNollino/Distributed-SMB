#!/usr/bin/env bash
# Builds the lobby/game-events Docker images and saves them as tar.gz
# bundles for offline distribution (USB stick, no Docker Hub).
#
# Usage: ./build_bundle.sh [output_dir]
set -euo pipefail

OUT_DIR="${1:-bundle}"

mkdir -p "$OUT_DIR"

echo "==> Building distributed-smb-lobby image"
docker build -f Dockerfile.lobby -t distributed-smb-lobby .

echo "==> Building distributed-smb-gameevents image"
docker build -f Dockerfile.gameevents -t distributed-smb-gameevents .

echo "==> Saving distributed-smb-lobby -> $OUT_DIR/smb-lobby.tar.gz"
docker save distributed-smb-lobby | gzip > "$OUT_DIR/smb-lobby.tar.gz"

echo "==> Saving distributed-smb-gameevents -> $OUT_DIR/smb-gameevents.tar.gz"
docker save distributed-smb-gameevents | gzip > "$OUT_DIR/smb-gameevents.tar.gz"

echo "==> Done. Bundle contents:"
ls -lh "$OUT_DIR"
