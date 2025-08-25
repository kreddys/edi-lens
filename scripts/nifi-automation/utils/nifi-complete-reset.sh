#!/bin/bash
# ==============================================================================
# NiFi Complete Reset Script
# ==============================================================================
# This script performs a complete reset of NiFi including:
# 1. Stopping NiFi container
# 2. Removing all NiFi persistent data volumes
# 3. Restarting NiFi container
# 4. Redeploying EDI processors
# 5. Creating fresh workflow

set -e

# Color output functions
info() { echo -e "\033[34m[INFO] $1\033[0m"; }
success() { echo -e "\033[32m[SUCCESS] $1\033[0m"; }
warn() { echo -e "\033[33m[WARN] $1\033[0m"; }
error() { echo -e "\033[31m[ERROR] $1\033[0m" >&2; }

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NIFI_CONTAINER="nifi"

# Set environment-specific variables
PROJECT_NAME="edi-lens-dev"
ENV_FILE=".env.dev"
DC_FILES="-f docker/docker-compose.yml"
DC_EXEC="docker compose -p ${PROJECT_NAME} ${DC_FILES} --env-file ${ENV_FILE}"

main() {
    info "🔄 Starting NiFi Complete Reset Process"
    echo ""
    
    # Step 1: Stop NiFi container
    info "Step 1: Stopping NiFi container..."
    if docker ps | grep -q "$NIFI_CONTAINER"; then
        docker stop "$NIFI_CONTAINER" || warn "Failed to stop NiFi container"
    fi
    
    # Step 2: Remove NiFi container
    info "Step 2: Removing NiFi container..."
    if docker ps -a | grep -q "$NIFI_CONTAINER"; then
        docker rm "$NIFI_CONTAINER" || warn "Failed to remove NiFi container"
    fi
    
    # Step 3: Remove all NiFi persistent data volumes
    info "Step 3: Removing all NiFi persistent data volumes..."
    docker volume rm edi-lens-dev_nifi_database_repository edi-lens-dev_nifi_flowfile_repository edi-lens-dev_nifi_content_repository edi-lens-dev_nifi_provenance_repository edi-lens-dev_nifi_conf 2>/dev/null || true
    
    # Skip cleaning test data directory to preserve test files
    info "Step 4: Skipping test data directory cleanup to preserve test files..."
    
    # Step 5: Restart NiFi container
    info "Step 5: Restarting NiFi container..."
    cd "$PROJECT_ROOT"
    ./run.sh dev:start
    
    # Step 6: Wait for NiFi to be ready
    info "Step 6: Waiting for NiFi to be ready (this may take 2-3 minutes)..."
    local attempts=0
    local max_attempts=36  # 3 minutes with 5-second intervals
    
    while [ $attempts -lt $max_attempts ]; do
        if curl -s http://localhost:8080/nifi > /dev/null 2>&1; then
            success "✅ NiFi is ready!"
            break
        fi
        
        attempts=$((attempts + 1))
        if [ $((attempts % 6)) -eq 0 ]; then
            info "⏳ Still waiting... (${attempts}/36 attempts)"
        fi
        sleep 5
    done
    
    if [ $attempts -eq $max_attempts ]; then
        error "❌ NiFi failed to start within timeout"
        exit 1
    fi
    
    # Step 7: Wait additional time for full initialization
    info "Step 7: Waiting for full NiFi initialization..."
    sleep 30
    
    # Step 8: Redeploy EDI processors using the existing deploy processors option
    info "Step 8: Redeploying EDI processors..."
    cd "$SCRIPT_DIR"
    "./nifi-automation" deploy-processors volume
    
    # Step 9: No need to restart NiFi separately as the processors are deployed during start
    info "Step 9: Skipping separate NiFi restart as processors are deployed during start..."
    
    # Step 10: Wait for NiFi to be ready
    info "Step 10: Waiting for NiFi to be ready..."
    # Use docker health check instead of curl for faster response
    local wait_attempts=0
    local max_wait_attempts=24  # 2 minutes with 5-second intervals
    
    while [ $wait_attempts -lt $max_wait_attempts ]; do
        if docker inspect --format='{{.State.Health.Status}}' nifi 2>/dev/null | grep -q "healthy"; then
            success "✅ NiFi is ready!"
            break
        fi
        
        wait_attempts=$((wait_attempts + 1))
        if [ $((wait_attempts % 6)) -eq 0 ]; then
            info "⏳ Still waiting for NiFi to be healthy... (${wait_attempts}/24 attempts)"
        fi
        sleep 5
    done
    
    if [ $wait_attempts -eq $max_wait_attempts ]; then
        error "❌ NiFi failed to become healthy within timeout"
        # Show container logs for debugging
        docker logs nifi | tail -20
        exit 1
    fi
    
    # Step 11: Wait for full initialization
    info "Step 11: Waiting for full NiFi initialization..."
    sleep 15
    
    echo ""
    success "🎉 NiFi Complete Reset Complete!"
    echo ""
    echo "🎯 Next steps:"
    echo "  ./nifi-automation flows                   # List available flows"
    echo "  ./nifi-automation deploy <flow-name>      # Deploy a flow"
    echo "  ./nifi-automation status                  # Check status"
    echo ""
    echo "🌐 Access NiFi UI: https://localhost:8443/nifi"
    echo "🔑 Login: superuser@edilens.com / password123456789"
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "NiFi Complete Reset Script"
        echo ""
        echo "Usage: $0 [options]"
        echo ""
        echo "This script performs a complete reset of NiFi:"
        echo "  1. Stop and remove NiFi container"
        echo "  2. Remove all NiFi persistent data volumes"
        echo "  3. Restart NiFi container"
        echo "  4. Redeploy EDI processors"
        echo "  5. Wait for full initialization"
        echo ""
        echo "Options:"
        echo "  --help, -h    Show this help message"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac