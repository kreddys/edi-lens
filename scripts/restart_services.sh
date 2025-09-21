#!/bin/bash
# Restart all EDI-Lens services

echo "🔄 Restarting all EDI-Lens services..."
echo ""

# Use the new flag-driven functionality from setup_codex.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

./scripts/setup_codex.sh --restart-services
