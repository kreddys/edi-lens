#!/bin/bash
# ==============================================================================
# EDI Lens CLI Non-Interactive Testing Script
# ==============================================================================
# This script demonstrates various non-interactive CLI commands
# ==============================================================================

set -euo pipefail

# Colors for output
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[TEST]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🧪 Testing EDI Lens CLI Non-Interactive Commands"
echo "═══════════════════════════════════════════════"
echo

# Test 1: Health Check
log_info "Test 1: Health Check"
./scripts/run-cli.sh --command health-check --quiet
if [ $? -eq 0 ]; then
    log_success "Health check passed"
else
    log_warn "Health check failed (services may not be running)"
fi
echo

# Test 2: Health Check with JSON output
log_info "Test 2: Health Check with JSON output"
./scripts/run-cli.sh --command health-check --output-format json --quiet
echo

# Test 3: System Status
log_info "Test 3: System Status"
./scripts/run-cli.sh --command system-status --quiet
echo

# Test 4: List Registry Buckets
log_info "Test 4: List Registry Buckets"
./scripts/run-cli.sh --command list-buckets
echo

# Test 5: Deploy Flow (with sample parameters)
log_info "Test 5: Deploy Flow (simple-file-processing)"
PROCESS_GROUP_ID=$(./scripts/run-cli.sh --command deploy-flow \
    --template simple-file-processing \
    --params input_directory=/tmp/cli_test_input output_directory=/tmp/cli_test_output \
    --auto-start \
    --quiet \
    --output-format json | jq -r '.process_group_id // empty')

if [ -n "$PROCESS_GROUP_ID" ]; then
    log_success "Flow deployed with Process Group ID: $PROCESS_GROUP_ID"
    
    # Test 6: Check Flow Status
    log_info "Test 6: Check Flow Status"
    ./scripts/run-cli.sh --command flow-status --process-group-id "$PROCESS_GROUP_ID"
    echo
    
    # Test 7: Stop Flow
    log_info "Test 7: Stop Flow"
    ./scripts/run-cli.sh --command stop-flow --process-group-id "$PROCESS_GROUP_ID" --quiet
    log_success "Flow stopped"
    echo
    
    # Test 8: Start Flow
    log_info "Test 8: Start Flow"
    ./scripts/run-cli.sh --command start-flow --process-group-id "$PROCESS_GROUP_ID" --quiet
    log_success "Flow started"
    echo
    
    # Test 9: Delete Flow
    log_info "Test 9: Delete Flow"
    ./scripts/run-cli.sh --command delete-flow --process-group-id "$PROCESS_GROUP_ID" --quiet
    log_success "Flow deleted"
    echo
else
    log_warn "Flow deployment failed, skipping flow-specific tests"
fi

# Test 10: Help/Usage
log_info "Test 10: Show CLI Help"
./scripts/run-cli.sh --help
echo

log_success "🎉 CLI Testing Complete!"
echo
echo "Available Commands:"
echo "  --command health-check                     # Check system health"
echo "  --command system-status                    # Detailed system status"
echo "  --command deploy-flow --template NAME      # Deploy a flow template"
echo "  --command start-flow --process-group-id ID # Start a flow"
echo "  --command stop-flow --process-group-id ID  # Stop a flow"
echo "  --command delete-flow --process-group-id ID # Delete a flow"
echo "  --command flow-status --process-group-id ID # Get flow status"
echo "  --command list-buckets                     # List Registry buckets"
echo
echo "Output Formats:"
echo "  --output-format table                      # Table format (default)"
echo "  --output-format json                       # JSON format"
echo "  --quiet                                    # Minimal output"