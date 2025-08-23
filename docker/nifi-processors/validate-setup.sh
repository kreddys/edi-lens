#!/bin/bash
# NiFi Setup Validation Script
# This script validates that NiFi is properly configured and running

set -e

echo "=============================================="
echo "NiFi Setup Validation"
echo "=============================================="
echo "Timestamp: $(date)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

NIFI_HOST=${NIFI_HOST:-"localhost"}
NIFI_PORT=${NIFI_PORT:-"8080"}
NIFI_BASE_URL="http://${NIFI_HOST}:${NIFI_PORT}"

VALIDATION_PASSED=true

# Test 1: Basic connectivity
info "Testing basic connectivity to NiFi..."
if curl -s -f "${NIFI_BASE_URL}/nifi-api/system-diagnostics" > /dev/null; then
    success "✅ NiFi API is accessible"
else
    error "❌ Cannot connect to NiFi API at ${NIFI_BASE_URL}"
    VALIDATION_PASSED=false
fi

# Test 2: System diagnostics
info "Checking system diagnostics..."
SYSTEM_DIAG=$(curl -s "${NIFI_BASE_URL}/nifi-api/system-diagnostics" || echo "")
if [ -n "$SYSTEM_DIAG" ]; then
    success "✅ System diagnostics available"
    # Extract key metrics
    if echo "$SYSTEM_DIAG" | grep -q '"availableProcessors"'; then
        PROCESSORS=$(echo "$SYSTEM_DIAG" | grep -o '"availableProcessors":[0-9]*' | cut -d':' -f2)
        info "   Available processors: $PROCESSORS"
    fi
    if echo "$SYSTEM_DIAG" | grep -q '"totalHeap"'; then
        HEAP=$(echo "$SYSTEM_DIAG" | grep -o '"totalHeap":"[^"]*"' | cut -d'"' -f4)
        info "   Total heap: $HEAP"
    fi
else
    error "❌ Cannot retrieve system diagnostics"
    VALIDATION_PASSED=false
fi

# Test 3: Flow configuration
info "Checking flow configuration..."
FLOW_CONFIG=$(curl -s "${NIFI_BASE_URL}/nifi-api/flow/process-groups/root" || echo "")
if [ -n "$FLOW_CONFIG" ]; then
    success "✅ Flow configuration accessible"
else
    error "❌ Cannot access flow configuration"
    VALIDATION_PASSED=false
fi

# Test 4: Python extensions
info "Checking Python processor availability..."
PROCESSOR_TYPES=$(curl -s "${NIFI_BASE_URL}/nifi-api/flow/processor-types" || echo "")
if [ -n "$PROCESSOR_TYPES" ]; then
    success "✅ Processor types available"
    
    # Check for Python processors
    if echo "$PROCESSOR_TYPES" | grep -q "python"; then
        success "✅ Python processors detected"
        PYTHON_COUNT=$(echo "$PROCESSOR_TYPES" | grep -o "python" | wc -l)
        info "   Found $PYTHON_COUNT Python-related processors"
    else
        warn "⚠️  No Python processors detected - this may be normal if none are installed"
    fi
    
    # Check for EDI processors specifically
    if echo "$PROCESSOR_TYPES" | grep -q -i "edi"; then
        success "✅ EDI processors detected"
        EDI_COUNT=$(echo "$PROCESSOR_TYPES" | grep -o -i "edi" | wc -l)
        info "   Found $EDI_COUNT EDI-related processors"
    else
        warn "⚠️  No EDI processors detected"
    fi
else
    error "❌ Cannot retrieve processor types"
    VALIDATION_PASSED=false
fi

# Test 5: Controller services
info "Checking controller services..."
CONTROLLER_SERVICES=$(curl -s "${NIFI_BASE_URL}/nifi-api/flow/process-groups/root/controller-services" || echo "")
if [ -n "$CONTROLLER_SERVICES" ]; then
    success "✅ Controller services accessible"
else
    error "❌ Cannot access controller services"
    VALIDATION_PASSED=false
fi

# Test 6: User authentication (if applicable)
info "Checking authentication status..."
AUTH_STATUS=$(curl -s "${NIFI_BASE_URL}/nifi-api/access/config" || echo "")
if [ -n "$AUTH_STATUS" ]; then
    success "✅ Authentication configuration accessible"
    if echo "$AUTH_STATUS" | grep -q '"supportsLogin":true'; then
        info "   Authentication is enabled"
    else
        info "   Authentication is disabled (single-user mode)"
    fi
else
    error "❌ Cannot check authentication status"
    VALIDATION_PASSED=false
fi

# Test 7: Version information
info "Checking NiFi version..."
VERSION_INFO=$(curl -s "${NIFI_BASE_URL}/nifi-api/system-diagnostics" | grep -o '"niFiVersion":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
if [ "$VERSION_INFO" != "unknown" ]; then
    success "✅ NiFi version: $VERSION_INFO"
else
    warn "⚠️  Cannot determine NiFi version"
fi

# Test 8: Memory and performance checks
info "Checking performance metrics..."
if [ -n "$SYSTEM_DIAG" ]; then
    # Check memory usage
    if echo "$SYSTEM_DIAG" | grep -q '"usedHeap"'; then
        USED_HEAP=$(echo "$SYSTEM_DIAG" | grep -o '"usedHeap":"[^"]*"' | cut -d'"' -f4)
        info "   Used heap: $USED_HEAP"
    fi
    
    # Check active threads
    if echo "$SYSTEM_DIAG" | grep -q '"activeThreadCount"'; then
        ACTIVE_THREADS=$(echo "$SYSTEM_DIAG" | grep -o '"activeThreadCount":[0-9]*' | cut -d':' -f2)
        info "   Active threads: $ACTIVE_THREADS"
    fi
fi

echo ""
echo "=============================================="
if [ "$VALIDATION_PASSED" = true ]; then
    success "🎉 All validation tests passed!"
    echo ""
    echo "NiFi is properly configured and running."
    echo "Web UI available at: ${NIFI_BASE_URL}/nifi/"
    echo ""
    exit 0
else
    error "❌ Some validation tests failed!"
    echo ""
    echo "Please check the errors above and verify your NiFi configuration."
    echo ""
    exit 1
fi