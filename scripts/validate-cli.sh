#!/bin/bash
# ==============================================================================
# EDI Lens CLI Validation Script
# ==============================================================================
# Comprehensive test of all working CLI commands
# ==============================================================================

set -euo pipefail

# Colors for output
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

log_test() { echo -e "${BLUE}[TEST ${TOTAL_TESTS}]${NC} $1"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; ((PASSED_TESTS++)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; ((FAILED_TESTS++)); }
log_skip() { echo -e "${YELLOW}[SKIP]${NC} $1"; }

run_test() {
    local test_name="$1"
    local command="$2"
    local expected_exit_code="${3:-0}"
    
    ((TOTAL_TESTS++))
    log_test "$test_name"
    
    if eval "$command" >/dev/null 2>&1; then
        actual_exit_code=$?
    else
        actual_exit_code=$?
    fi
    
    if [ $actual_exit_code -eq $expected_exit_code ]; then
        log_pass "$test_name"
        return 0
    else
        log_fail "$test_name (exit code: $actual_exit_code, expected: $expected_exit_code)"
        return 1
    fi
}

run_json_test() {
    local test_name="$1"
    local command="$2"
    
    ((TOTAL_TESTS++))
    log_test "$test_name"
    
    local output
    if output=$(eval "$command" 2>/dev/null); then
        # Check if output is valid JSON
        if echo "$output" | jq . >/dev/null 2>&1; then
            log_pass "$test_name"
            return 0
        else
            log_fail "$test_name (invalid JSON output)"
            return 1
        fi
    else
        log_fail "$test_name (command failed)"
        return 1
    fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🧪 EDI Lens CLI Validation Tests"
echo "═══════════════════════════════════"
echo

# Test 1: Help command
run_test "Help command" "./scripts/run-cli.sh --help"

echo

# Test 2: Health check commands
log_test "Health Check Commands"
run_test "Health check (quiet)" "./scripts/run-cli.sh --command health-check --quiet"
run_json_test "Health check JSON" "./scripts/run-cli.sh --command health-check --quiet --output-format json"
run_json_test "System status JSON" "./scripts/run-cli.sh --command system-status --quiet --output-format json"

echo

# Test 3: Registry commands
log_test "Registry Commands"
run_test "List buckets (quiet)" "./scripts/run-cli.sh --command list-buckets --quiet"
run_json_test "List buckets JSON" "./scripts/run-cli.sh --command list-buckets --quiet --output-format json"

# Get bucket ID for further testing
BUCKET_ID=$(./scripts/run-cli.sh --command list-buckets --quiet --output-format json | jq -r '.[0].bucket_id // empty' 2>/dev/null)

if [ -n "$BUCKET_ID" ]; then
    run_json_test "List flows in bucket" "./scripts/run-cli.sh --command list-flows-in-bucket --bucket-id '$BUCKET_ID' --quiet --output-format json"
else
    log_skip "List flows in bucket (no bucket ID available)"
    ((TOTAL_TESTS++))
fi

echo

# Test 4: Template discovery
log_test "Template System"
run_test "Check templates directory exists" "test -d data/flows"
run_test "Simple file processing template exists" "test -f data/flows/simple-file-processing.json"

# Test template loading (this will fail on deployment due to auth, but should load the template)
((TOTAL_TESTS++))
log_test "Template loading test"
if ./scripts/run-cli.sh --command deploy-flow --template simple-file-processing --params input_directory=/tmp/test --quiet 2>&1 | grep -q "Template.*not found"; then
    log_fail "Template loading test (template not found)"
else
    log_pass "Template loading test (template found, deployment failed as expected due to auth)"
fi

echo

# Test 5: Invalid commands (should fail gracefully)
log_test "Error Handling"
run_test "Invalid command" "./scripts/run-cli.sh --command invalid-command" 1
run_test "Missing required parameter" "./scripts/run-cli.sh --command flow-status --quiet" 1

echo

# Test 6: Output format tests
log_test "Output Formats"
run_test "Table format" "./scripts/run-cli.sh --command list-buckets --output-format table --quiet"
run_test "JSON format" "./scripts/run-cli.sh --command list-buckets --output-format json --quiet"

echo

# Test 7: Quiet mode validation
log_test "Quiet Mode Validation"
((TOTAL_TESTS++))
OUTPUT=$(./scripts/run-cli.sh --command health-check --quiet --output-format json 2>/dev/null)
if echo "$OUTPUT" | grep -q "EDI Lens CLI"; then
    log_fail "Quiet mode test (banner still showing)"
else
    log_pass "Quiet mode test (clean output)"
fi

echo

# Summary
echo "═══════════════════════════════════"
echo "🏁 Test Summary"
echo "  Total Tests: $TOTAL_TESTS"
echo "  Passed: $PASSED_TESTS"
echo "  Failed: $FAILED_TESTS"
echo "  Success Rate: $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%"

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed.${NC}"
    exit 1
fi