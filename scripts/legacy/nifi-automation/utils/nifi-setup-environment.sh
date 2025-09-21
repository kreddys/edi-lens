#!/bin/bash
# Quick setup script for NiFi EDI Validation Processor testing

set -e

# Color output functions
info() { echo -e "\033[34m[INFO] $1\033[0m"; }
success() { echo -e "\033[32m[SUCCESS] $1\033[0m"; }
warn() { echo -e "\033[33m[WARN] $1\033[0m"; }
error() { echo -e "\033[31m[ERROR] $1\033[0m" >&2; exit 1; }

info "🚀 Setting up NiFi EDI Validation Processor Test Environment"

# Step 1: Deploy processors
info "📦 Deploying EDI processors to NiFi..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOMATION_SCRIPT="$SCRIPT_DIR/../nifi-automation"
if [ -f "$AUTOMATION_SCRIPT" ]; then
    "$AUTOMATION_SCRIPT" deploy-processors volume
else
    error "NiFi automation script not found at: $AUTOMATION_SCRIPT"
fi

# Step 2: Create test directories
info "📁 Creating test directories..."
mkdir -p scripts/nifi-automation/tmp/test-data/success
mkdir -p scripts/nifi-automation/tmp/test-data/failure
mkdir -p /tmp/nifi-test-data/success
mkdir -p /tmp/nifi-test-data/failure

# Step 3: Copy schema files
info "📋 Copying schema files to NiFi..."
docker exec nifi mkdir -p /opt/nifi/schemas
docker cp nifi-edi-processors/schemas/837.5010.X222.A1.json nifi:/opt/nifi/schemas/

# Step 4: Create test EDI files
info "📄 Creating test EDI files..."

# Valid 837P EDI file
cat > scripts/nifi-automation/tmp/test-data/sample_837p_valid.edi << 'EOF'
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234*20240715*1200*CH~
NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~
PER*IC*JOHN DOE*TE*8005551212~
NM1*40*2*PAYER A*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*CA*90210~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GRP123******CI~
NM1*IL*1*DOE*JOHN****MI*SUBID123~
NM1*PR*2*PAYER A*****PI*PAYERID123~
CLM*PATCTRL123*500***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
PWK*OZ*BM***AC*CONTROL123~
HI*BK>87340~
LX*1~
SV1*HC>99213*125*UN*1***1**Y~
DTP*472*D8*20240715~
SE*25*0001~
GE*1*1~
IEA*1*000000001~
EOF

# Invalid 837P EDI file (missing required loop, invalid date length, invalid code)
cat > scripts/nifi-automation/tmp/test-data/sample_837p_invalid.edi << 'EOF'
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234*202407*1200*CH~
PER*IC*JOHN DOE*TE*8005551212~
NM1*40*2*PAYER A*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*CA*90210~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GRP123******CI~
NM1*IL*1*DOE*JOHN****MI*SUBID123~
NM1*PR*2*PAYER A*****PI*PAYERID123~
CLM*PATCTRL123*500***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
PWK*OZ*BM***AC*CONTROL123~
HI*BK>87340~
LX*1~
SV1*HC>99213*125*UN*1***1**X~
DTP*472*D8*20240715~
SE*24*0001~
GE*1*1~
IEA*1*000000001~
EOF

# Copy to global tmp for NiFi processing
cp scripts/nifi-automation/tmp/test-data/sample_837p_valid.edi /tmp/nifi-test-data/
cp scripts/nifi-automation/tmp/test-data/sample_837p_invalid.edi /tmp/nifi-test-data/

# Complex valid EDI file for advanced testing
cat > scripts/nifi-automation/tmp/test-data/sample_837p_complex.edi << 'EOF'
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*BATCH01*20240715*1200*CH~
NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~
PER*IC*JOHN DOE*TE*8005551212~
NM1*40*2*PAYER A*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*CA*90210~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GRP123******CI~
NM1*IL*1*DOE*JOHN****MI*SUBID123~
NM1*PR*2*PAYER A*****PI*PAYERID123~
CLM*JOHNDOE_CLAIM1*500***11>B>1*Y*A*Y*Y~
HI*BK>J100~
LX*1~
SV1*HC>99213*125*UN*1***1**Y~
DTP*472*D8*20240715~
LX*2~
SV1*HC>99214*125*UN*1***2**Y~
DTP*472*D8*20240715~
CLM*JOHNDOE_CLAIM2*25***11>B>1*Y*A*Y*Y~
HI*BK>F410~
LX*1~
SV1*HC>99203*25*UN*1***1**Y~
DTP*472*D8*20240715~
SE*30*0001~
GE*1*1~
IEA*1*000000001~
EOF

# Copy complex file to global tmp
cp scripts/nifi-automation/tmp/test-data/sample_837p_complex.edi /tmp/nifi-test-data/

# Step 5: Restart NiFi to load processors
info "🔄 Restarting NiFi to load EDI processors..."
docker restart nifi

# Wait for NiFi to start
info "⏳ Waiting for NiFi to start (this may take 1-2 minutes)..."
sleep 60

# Check if NiFi is responding
for i in {1..12}; do
    if curl -s http://localhost:8080/nifi > /dev/null 2>&1; then
        success "✅ NiFi is running and accessible!"
        break
    else
        if [ $i -eq 12 ]; then
            warn "⚠️  NiFi may still be starting. Please wait a bit more and check manually."
        else
            info "⏳ Still waiting for NiFi... (attempt $i/12)"
            sleep 10
        fi
    fi
done

# Step 6: Display summary
echo ""
success "🎉 NiFi EDI Validation Test Environment Setup Complete!"
echo ""
echo "📋 What's been set up:"
echo "   ✅ EDI processors deployed to NiFi"
echo "   ✅ Schema files copied to /opt/nifi/schemas/"
echo "   ✅ Test EDI files created in /tmp/nifi-test-data/"
echo "   ✅ Output directories created"
echo "   ✅ NiFi restarted and should be running"
echo ""
echo "📄 Test files created:"
echo "   📝 sample_837p_valid.edi - Valid 837P claim"
echo "   📝 sample_837p_invalid.edi - Invalid 837P (missing loop, bad date, bad code)"
echo "   📝 sample_837p_complex.edi - Complex valid 837P with multiple claims"
echo ""
echo "🌐 Next steps:"
echo "   1. Open NiFi UI: http://localhost:8080"
echo "   2. Login with: admin/admin123"
echo "   3. Use automation scripts in scripts/nifi-automation/ to create workflow"
echo ""
echo "🧪 To test the flow:"
echo "   # Test with valid EDI:"
echo "   cp /tmp/nifi-test-data/sample_837p_valid.edi /tmp/nifi-test-data/test_\$(date +%s).edi"
echo ""
echo "   # Test with invalid EDI:"
echo "   cp /tmp/nifi-test-data/sample_837p_invalid.edi /tmp/nifi-test-data/test_invalid_\$(date +%s).edi"
echo ""
info "💡 Use scripts/nifi-automation/complete_nifi_setup.sh for full automation"