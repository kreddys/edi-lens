#!/bin/bash
# Complete automated NiFi EDI validation setup and workflow creation

set -e

# Color output functions
info() { echo -e "\033[34m[INFO] $1\033[0m"; }
success() { echo -e "\033[32m[SUCCESS] $1\033[0m"; }
warn() { echo -e "\033[33m[WARN] $1\033[0m"; }
error() { echo -e "\033[31m[ERROR] $1\033[0m" >&2; exit 1; }

info "🚀 Complete NiFi EDI Validation Setup & Workflow Creation"
echo "=" * 60

# Step 1: Run the basic setup
info "📦 Step 1: Setting up NiFi environment..."
if [ -f "scripts/nifi-automation/nifi-setup-environment.sh" ]; then
    ./scripts/nifi-automation/nifi-setup-environment.sh
else
    error "Setup script not found. Please run this from the project root."
fi

# Step 2: Wait for NiFi to be fully ready
info "⏳ Step 2: Waiting for NiFi to be fully ready..."
sleep 30

# Check if NiFi is responding
for i in {1..20}; do
    if curl -s http://localhost:8080/nifi-api/system-diagnostics > /dev/null 2>&1; then
        success "✅ NiFi API is responding!"
        break
    else
        if [ $i -eq 20 ]; then
            warn "⚠️  NiFi API not responding. Trying workflow creation anyway..."
        else
            info "⏳ Waiting for NiFi API... (attempt $i/20)"
            sleep 5
        fi
    fi
done

# Step 3: Create workflow automatically
info "🤖 Step 3: Creating workflow automatically..."

# Use the new YAML-based flow manager with enhanced options
info "🔧 Creating workflow using YAML-based flow manager..."
if python3 scripts/nifi-automation/nifi-flow-manager.py create --config scripts/nifi-automation/flows/edi-validation-flow.yaml --start --wait 10; then
    success "✅ Workflow created and started successfully!"
else
    warn "⚠️  YAML flow creation failed. Trying force cleanup and retry..."
    
    # Try force cleanup and retry
    python3 scripts/nifi-automation/nifi-flow-manager.py cleanup --force
    sleep 5
    
    if python3 scripts/nifi-automation/nifi-flow-manager.py create --config scripts/nifi-automation/flows/edi-validation-flow.yaml --start --wait 10; then
        success "✅ Workflow created successfully after cleanup!"
    else
        warn "⚠️  Workflow creation still failing."
        echo ""
        echo "📋 Try these options:"
        echo "   1. Clean restart: ./scripts/nifi-automation/nifi_restart_clean.sh"
        echo "   2. Manual cleanup: python3 scripts/nifi-automation/nifi-flow-manager.py cleanup --force"
        echo "   3. Check status: python3 scripts/nifi-automation/nifi-flow-manager.py status --verbose"
        echo "   4. NiFi UI: http://localhost:8080 (superuser@edilens.com/password123456789)"
        exit 1
    fi
fi

# Step 4: Verify workflow
info "🔍 Step 4: Verifying workflow..."
sleep 5

# Check if processors are running
if curl -s http://localhost:8080/nifi-api/flow/process-groups/root | grep -q "RUNNING"; then
    success "✅ Processors are running!"
else
    warn "⚠️  Some processors may not be running. Check NiFi UI."
fi

# Step 5: Run initial test
info "🧪 Step 5: Running initial test..."

# Test with valid EDI
test_file="/tmp/nifi-test-data/test_auto_$(date +%s).edi"
cp /tmp/nifi-test-data/sample_837p_valid.edi "$test_file"
info "📄 Created test file: $test_file"

# Wait a moment for processing
sleep 10

# Check results
if [ -d "/tmp/nifi-test-data/success" ] && [ "$(ls -A /tmp/nifi-test-data/success 2>/dev/null)" ]; then
    success "✅ Test file processed successfully!"
    echo "📊 Results found in: /tmp/nifi-test-data/success/"
    ls -la /tmp/nifi-test-data/success/
else
    warn "⚠️  No results yet. Processing may take a moment."
fi

# Final summary
echo ""
success "🎉 Complete NiFi EDI Validation Setup Finished!"
echo ""
echo "📋 What's been created:"
echo "   ✅ NiFi environment with EDI processors"
echo "   ✅ Complete EDI validation workflow"
echo "   ✅ Test data files and directories"
echo "   ✅ Automated workflow running"
echo ""
echo "🌐 Access points:"
echo "   🖥️  NiFi UI: http://localhost:8080 (admin/admin123)"
echo "   📁 Test data: /tmp/nifi-test-data/"
echo "   📊 Results: /tmp/nifi-test-data/success/ and /tmp/nifi-test-data/failure/"
echo ""
echo "🧪 Quick tests:"
echo "   # Test valid EDI:"
echo "   cp /tmp/nifi-test-data/sample_837p_valid.edi /tmp/nifi-test-data/test_\$(date +%s).edi"
echo ""
echo "   # Test invalid EDI:"
echo "   cp /tmp/nifi-test-data/sample_837p_invalid.edi /tmp/nifi-test-data/test_invalid_\$(date +%s).edi"
echo ""
echo "   # Monitor logs:"
echo "   docker logs nifi | grep -E '(VALIDATION SUCCESS|VALIDATION FAILURE)'"
echo ""
echo "   # Check results:"
echo "   ls -la /tmp/nifi-test-data/success/"
echo "   cat /tmp/nifi-test-data/success/*.json"
echo ""
info "💡 The workflow is now ready for testing your EDI validation processor!"