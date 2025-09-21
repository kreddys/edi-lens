#!/bin/bash
# Restart all EDI-Lens services

echo "Stopping all services..."
pkill -f "minio" || true
pkill -f "keycloak" || true
pkill -f "sftpgo" || true
pkill -f "nifi" || true
pkill -f "uvicorn" || true
pkill -f "npm.*dev" || true

sleep 5

echo "Restarting services..."
cd "$(dirname "${BASH_SOURCE[0]}")/.."
./scripts/setup_codex.sh
