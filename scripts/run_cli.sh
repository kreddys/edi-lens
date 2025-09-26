#!/bin/bash
# ==============================================================================
# EDI Lens CLI Runner Script
# ==============================================================================
# Simple script to run the EDI Lens CLI with proper environment setup
# ==============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLI_DIR="$SCRIPT_DIR/edi-lens-cli"

# Colors for output
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

check_dependencies() {
    log_info "Checking dependencies..."
    
    # Check if we're in the project root with backend directory
    if [ ! -d "backend" ]; then
        log_error "Must run from project root (backend directory not found)"
        exit 1
    fi
    
    # Check Poetry
    if ! command -v poetry >/dev/null 2>&1; then
        log_error "Poetry is not installed or not in PATH"
        log_info "Install Poetry: https://python-poetry.org/docs/#installation"
        exit 1
    fi
    
    log_info "Found Poetry $(poetry --version | cut -d' ' -f3)"
    
    # Check if backend dependencies are installed
    cd backend
    if ! poetry env info >/dev/null 2>&1; then
        log_warn "Backend dependencies not installed. Installing..."
        poetry install --no-root
    fi
    
    # Verify httpx is available
    if ! poetry run python -c "import httpx" >/dev/null 2>&1; then
        log_error "httpx not available in Poetry environment. Running poetry install..."
        poetry install --no-root
    fi
    
    cd "$PROJECT_ROOT"
    log_info "✅ All dependencies satisfied"
}

setup_environment() {
    log_info "Setting up environment..."
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Check for environment file
    if [ -f ".env.local" ]; then
        log_info "Found .env.local - using local development configuration"
        export EDI_LENS_ENV="local"
    elif [ -f ".env.docker" ]; then
        log_info "Found .env.docker - using Docker configuration"
        export EDI_LENS_ENV="docker"
    else
        log_warn "No environment file found - using defaults"
        export EDI_LENS_ENV="default"
    fi
    
    # Ensure data directories exist
    mkdir -p data/flows data/test-data
    
    # Check if backend is accessible
    log_info "Checking backend connectivity..."
    local backend_url="${EDI_LENS_BACKEND_URL:-http://localhost:8000}"
    
    if curl -s -f "$backend_url/health" >/dev/null 2>&1; then
        log_info "✅ Backend is accessible at $backend_url"
    else
        log_warn "⚠️ Backend may not be accessible at $backend_url"
        log_info "Make sure the EDI Lens backend is running"
    fi
}

show_banner() {
    # Check if quiet mode is requested
    for arg in "$@"; do
        if [[ "$arg" == "--quiet" || "$arg" == "-q" ]]; then
            return # Skip banner in quiet mode
        fi
    done
    
    cat << 'EOF'

🌊 EDI Lens CLI - Interactive NiFi Flow Manager
═══════════════════════════════════════════════

Starting interactive CLI...

EOF
}

main() {
    # Check if we're in quiet mode
    QUIET_MODE=false
    for arg in "$@"; do
        if [[ "$arg" == "--quiet" || "$arg" == "-q" ]]; then
            QUIET_MODE=true
            break
        fi
    done
    
    show_banner "$@"
    
    if [[ "$QUIET_MODE" != "true" ]]; then
        check_dependencies
        setup_environment
        log_info "Starting EDI Lens CLI..."
        echo
    else
        # Quick dependency check without verbose output
        if [ ! -d "backend" ]; then
            echo "❌ Must run from project root" >&2
            exit 1
        fi
        cd backend
        if ! poetry env info >/dev/null 2>&1; then
            echo "❌ Backend dependencies not installed" >&2
            exit 1
        fi
        cd "$PROJECT_ROOT"
    fi
    
    # Run the CLI using Poetry from backend directory
    cd backend
    poetry run python "../scripts/edi-lens-cli/main.py" "$@"
}

# Handle Ctrl+C gracefully
trap 'echo -e "\n👋 CLI interrupted. Goodbye!"; exit 0' INT

# Run main function with all arguments
main "$@"