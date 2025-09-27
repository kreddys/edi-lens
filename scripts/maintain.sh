#!/usr/bin/env bash
# ==============================================================================
# EDI LENS - UNIFIED MAINTENANCE SCRIPT
# ==============================================================================
# Automatic environment detection and delegation to the appropriate maintenance 
# script. This script provides a single interface for all development operations
# regardless of whether you're in a local Docker environment or Codex environment.
# ==============================================================================

set -euo pipefail

# --- Output helpers -----------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { printf "${BLUE}[INFO]${NC} %s\n" "$1"; }
success() { printf "${GREEN}[SUCCESS]${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; exit 1; }

# --- Environment Detection ----------------------------------------------------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env.local"

detect_environment() {
    local env_type="local"
    
    # Check for Codex environment markers
    if [ -d "/opt/codex-services" ] || [ -d "$PROJECT_ROOT/.codex-services" ]; then
        env_type="codex"
    elif [ -f "$ENV_FILE" ] && grep -q "CODEX_ENVIRONMENT=true" "$ENV_FILE" 2>/dev/null; then
        env_type="codex"
    elif command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet postgresql 2>/dev/null; then
        # PostgreSQL running as system service suggests Codex environment
        env_type="codex"
    elif [ "$EUID" -eq 0 ] && [ -f "/var/lib/postgresql/16/main/PG_VERSION" ]; then
        # Running as root with PostgreSQL data directory suggests Codex
        env_type="codex"
    fi
    
    echo "$env_type"
}

# --- Main Delegation Logic ---------------------------------------------------
main() {
    local env_type
    env_type=$(detect_environment)
    
    local script_name=""
    local sudo_prefix=""
    
    case "$env_type" in
        "codex")
            script_name="maintain_codex.sh"
            sudo_prefix="sudo"
            info "🔧 Detected Codex environment - using $script_name"
            ;;
        "local")
            script_name="maintain_local.sh"
            sudo_prefix=""
            info "🐳 Detected local development environment - using $script_name"
            ;;
        *)
            error "Unable to detect environment type"
            ;;
    esac
    
    local script_path="$PROJECT_ROOT/scripts/$script_name"
    
    if [ ! -f "$script_path" ]; then
        error "Maintenance script not found: $script_path"
    fi
    
    # Execute the appropriate script with all passed arguments
    if [ -n "$sudo_prefix" ]; then
        exec $sudo_prefix bash "$script_path" "$@"
    else
        exec bash "$script_path" "$@"
    fi
}

# Show help if requested without delegation (to avoid confusion)
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "help" ]; then
    cat <<EOF
EDI Lens Unified Development Maintenance

This script automatically detects your environment and delegates to the 
appropriate maintenance script:

ENVIRONMENTS:
  Local Development    -> maintain_local.sh (Docker-based)
  Codex Environment    -> maintain_codex.sh (Native services, requires sudo)

USAGE:
    $0 <command> [options]

ESSENTIAL COMMANDS:
    start                Start all services (infrastructure + backend + frontend)
    stop                 Stop all services
    restart              Restart all services
    status               Show detailed status of all services
    logs [service]       Show logs (backend, frontend, nifi, registry, db)
    clean                DESTRUCTIVE: Remove all containers, volumes, and data

DEVELOPMENT COMMANDS:
    test [type]          Run combined tests - both backend and frontend (unit, integration, e2e, all, watch)
    dev                  Start in development mode (infrastructure + backend + frontend)

TEST TYPES:
    unit                 Run unit tests (backend + frontend)
    integration          Run integration tests (backend + frontend) 
    e2e                  Run end-to-end tests (backend + frontend)
    all                  Run all test types (default)
    watch                Run backend tests in watch mode (backend only)

EXAMPLES:
    $0 start             # Start everything
    $0 status            # Show status
    $0 logs backend      # Show backend logs
    $0 test unit         # Run unit tests (backend + frontend)
    $0 test integration  # Run integration tests (backend + frontend)
    $0 test e2e          # Run E2E tests (backend + frontend)
    $0 clean             # Nuclear option - removes all data

SERVICES:
    - Frontend (port 3000)     - React/Vite dev server
    - Backend API (port 8000)  - FastAPI with auto docs
    - PostgreSQL (port 5432)   - Database storage
    - Apache NiFi (port 8443)  - Data flow engine  
    - NiFi Registry (port 18080) - Flow version control

For environment-specific help, run the detected script directly with --help

EOF
    exit 0
fi

main "$@"