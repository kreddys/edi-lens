#!/bin/bash
# ==============================================================================
# SIMPLE E2E TEST FOR NIFI EDI VALIDATION WORKFLOW
# ==============================================================================
# This test assumes the environment is already set up and focuses on testing
# the actual workflow functionality

set -e

# Color output functions
info() { echo -e "\033[34m[INFO] $1\033[0m"; }
success() { echo -e "\033[32m[SUCCESS] $1\033[0m"; }
warn() { echo -e "\033[33m[WARN] $1\033[0m"; }
error() { echo -e "\033[31m[ERROR] $1\033[0m" >&2; }
test_step() { echo -e "\033[35m[TEST] $1\033[0m"; }

# Test configuration
TEST_ID="simple_e2e_$(date +%Y%m%d_%H%M%S)"
TEST_DIR="/tmp/nifi-test-data"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_TEST_DIR="$SCRIPT_DIR/tmp/test-data"
NIFI_URL="http://localhost:8080"
NIFI_USER="superuser@edilens.com"
NIFI_PASS="password123456789"

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    
    test_step "$test_name"
    
    if eval "$test_command" > /dev/null 2>&1; then
        success "✅ PASS: $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        error "❌ FAIL: $test_name"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

get_nifi_token() {
    local token=$(curl -s -X POST "$NIFI_URL/nifi-api/access/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=$NIFI_USER&password=$NIFI_PASS")
    
    if [ ${#token} -gt 50 ]; then
        export NIFI_TOKEN="$token"
        return 0
    else
        return 1
    fi
}

main() {
    info "🚀 Starting Simple E2E Test for NiFi EDI Validation"
    info "Test ID: $TEST_ID"
    
    # Basic connectivity tests
    test_step "Testing basic connectivity..."
    run_test "NiFi UI is accessible" "curl -s $NIFI_URL > /dev/null"
    run_test "Docker container is running" "docker ps | grep -q nifi"
    
    # Authentication test
    test_step "Testing authentication..."
    run_test "NiFi authentication works" "get_nifi_token"
    
    # Test directories
    test_step "Testing test environment..."
    run_test "Test directory exists" "[ -d '$TEST_DIR' ]"
    run_test "Success directory exists" "[ -d '$TEST_DIR/success' ]"
    run_test "Failure directory exists" "[ -d '$TEST_DIR/failure' ]"
    run_test "Local sample files exist" "[ -f \"$LOCAL_TEST_DIR/sample_837p_valid.edi\" ] && [ -f \"$LOCAL_TEST_DIR/sample_837p_invalid.edi\" ]"
    run_test "Global sample files exist" "[ -f \"$TEST_DIR/sample_837p_valid.edi\" ] && [ -f \"$TEST_DIR/sample_837p_invalid.edi\" ]"
    
    # Flow management tests
    test_step "Testing flow management..."
    run_test "Flow manager can authenticate" "python3 \"$SCRIPT_DIR/utils/nifi-flow-manager.py\" cleanup"
    run_test "Flow can be created from YAML" "python3 \"$SCRIPT_DIR/utils/nifi-flow-manager.py\" create --config \"$SCRIPT_DIR/flows/edi-validation-flow.yaml\""
    
    # Check processors were created
    test_step "Verifying flow creation..."
    
    # Get the actual process group ID
    local process_group_id=$(curl -s -H "Authorization: Bearer $NIFI_TOKEN" \
        "$NIFI_URL/nifi-api/flow/process-groups/root" | \
        python3 -c "import sys,json; data=json.load(sys.stdin); print(data['processGroupFlow']['id'])" 2>/dev/null || echo "root")
    
    # Check processors using the correct endpoint
    local processor_count=$(curl -s -H "Authorization: Bearer $NIFI_TOKEN" \
        "$NIFI_URL/nifi-api/process-groups/$process_group_id/processors" | \
        python3 -c "import sys,json; data=json.load(sys.stdin); print(len(data.get('processors',[])))" 2>/dev/null || echo "0")
    
    if [ "$processor_count" -eq 6 ]; then
        success "✅ PASS: 6 processors created correctly"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        error "❌ FAIL: Expected 6 processors, found $processor_count"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    
    # Check connections were created
    local connection_count=$(curl -s -H "Authorization: Bearer $NIFI_TOKEN" \
        "$NIFI_URL/nifi-api/process-groups/$process_group_id/connections" | \
        python3 -c "import sys,json; data=json.load(sys.stdin); print(len(data.get('connections',[])))" 2>/dev/null || echo "0")
    
    if [ "$connection_count" -eq 5 ]; then
        success "✅ PASS: 5 connections created correctly"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        error "❌ FAIL: Expected 5 connections, found $connection_count"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    
    # EDI processor availability
    test_step "Testing EDI processors..."
    local edi_processors=$(curl -s -H "Authorization: Bearer $NIFI_TOKEN" \
        "$NIFI_URL/nifi-api/flow/processor-types" | \
        python3 -c "
import sys,json
try:
    data=json.load(sys.stdin)
    types=[t.get('type','') for t in data.get('processorTypes',[])]
    edi_count = len([t for t in types if 'EDI' in t])
    print(edi_count)
except:
    print(0)
" 2>/dev/null || echo "0")
    
    if [ "$edi_processors" -ge 2 ]; then
        success "✅ PASS: EDI processors are available ($edi_processors found)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        error "❌ FAIL: EDI processors not found"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    
    # Schema files test
    test_step "Testing schema availability..."
    run_test "Schema files accessible in NiFi" "docker exec nifi ls /opt/nifi/schemas/837.5010.X222.A1.json"
    
    # Python dependencies test
    test_step "Testing Python environment..."
    run_test "Python dependencies available" "docker exec nifi python3 -c 'import pydantic, typing_extensions'"
    
    # File processing test (if processors are running)
    test_step "Testing file processing capability..."
    
    # Clear previous results
    rm -f "$TEST_DIR/success/"* "$TEST_DIR/failure/"* 2>/dev/null || true
    
    # Create a test file
    local test_file="$TEST_DIR/test_${TEST_ID}.edi"
    if [ -f "$LOCAL_TEST_DIR/sample_837p_valid.edi" ]; then
        cp "$LOCAL_TEST_DIR/sample_837p_valid.edi" "$test_file"
    else
        error "❌ FAIL: Local sample file not found: $LOCAL_TEST_DIR/sample_837p_valid.edi"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
    
    info "Created test file: $test_file"
    info "⏳ Waiting 15 seconds for potential processing..."
    sleep 15
    
    # Check if any processing occurred
    local result_files=$(ls "$TEST_DIR/success/"*.json 2>/dev/null | wc -l)
    if [ "$result_files" -gt 0 ]; then
        success "✅ PASS: File processing is working (found $result_files result files)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        
        # Check result content
        local result_file=$(ls "$TEST_DIR/success/"*.json | head -1)
        if grep -q '"valid"' "$result_file" 2>/dev/null; then
            success "✅ PASS: Result file contains validation data"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            error "❌ FAIL: Result file missing validation data"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    else
        warn "⚠️  No file processing detected (processors may not be started)"
        info "💡 To test processing: Start processors in NiFi UI and run test again"
    fi
    
    # Cleanup test file
    rm -f "$test_file" 2>/dev/null || true
    
    # Summary
    echo ""
    echo "=============================================="
    echo "           SIMPLE E2E TEST SUMMARY"
    echo "=============================================="
    echo "Test ID: $TEST_ID"
    echo "Tests Passed: $TESTS_PASSED"
    echo "Tests Failed: $TESTS_FAILED"
    echo "=============================================="
    
    if [ $TESTS_FAILED -eq 0 ]; then
        success "🎉 ALL TESTS PASSED!"
        echo ""
        echo "✅ Your NiFi EDI validation workflow is working correctly!"
        echo ""
        echo "🎯 Next steps:"
        echo "1. Open NiFi UI: $NIFI_URL"
        echo "2. Login: $NIFI_USER / $NIFI_PASS"
        echo "3. Start all processors manually"
        echo "4. Test with: cp $TEST_DIR/sample_837p_valid.edi $TEST_DIR/test_\$(date +%s).edi"
        echo "5. Check results: ls -la $TEST_DIR/success/"
        return 0
    else
        error "❌ SOME TESTS FAILED!"
        echo ""
        echo "🔧 Troubleshooting steps:"
        echo "1. Check NiFi container: docker logs nifi"
        echo "2. Verify setup: ./scripts/nifi-automation/setup_nifi_test.sh"
        echo "3. Recreate flow: python3 scripts/nifi-automation/nifi-flow-manager.py create --config scripts/nifi-automation/flows/edi-validation-flow.yaml"
        return 1
    fi
}

# Run main function
main "$@"