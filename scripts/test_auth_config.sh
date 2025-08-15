#!/bin/bash
# =============================================================================
# EDI Lens Authentication Configuration Test Script
# =============================================================================
# This script demonstrates the standardized, environment-driven authentication
# configuration after cleanup.

set -e

echo "🧪 Testing EDI Lens Authentication Configuration"
echo "================================================"

# Load environment variables (in real usage, these would come from .env files)
export KEYCLOAK_BROWSER_URL=http://localhost:8081
export KEYCLOAK_REALM=edi-lens
export KEYCLOAK_NIFI_CLIENT_ID=nifi-service
export KEYCLOAK_NIFI_CLIENT_SECRET=nifi-service-secret
export KEYCLOAK_BACKEND_CLIENT_ID=edi-lens-backend
export KEYCLOAK_BACKEND_CLIENT_SECRET=this-is-a-very-secret-key-change-it
export KEYCLOAK_UI_CLIENT_ID=edi-lens-ui

echo ""
echo "🔧 Environment Configuration:"
echo "  KEYCLOAK_BROWSER_URL: $KEYCLOAK_BROWSER_URL"
echo "  KEYCLOAK_REALM: $KEYCLOAK_REALM"
echo "  KEYCLOAK_NIFI_CLIENT_ID: $KEYCLOAK_NIFI_CLIENT_ID"
echo "  KEYCLOAK_BACKEND_CLIENT_ID: $KEYCLOAK_BACKEND_CLIENT_ID"
echo "  KEYCLOAK_UI_CLIENT_ID: $KEYCLOAK_UI_CLIENT_ID"

echo ""
echo "🎫 Testing Token Generation:"

# Test NiFi service token
echo "  → Generating NiFi service token..."
NIFI_TOKEN=$(python scripts/get_auth_token.py --service nifi-service)
if [ $? -eq 0 ]; then
    echo "    ✅ NiFi token generated successfully"
else
    echo "    ❌ NiFi token generation failed"
    exit 1
fi

# Test backend service token  
echo "  → Generating backend service token..."
BACKEND_TOKEN=$(python scripts/get_auth_token.py --service backend)
if [ $? -eq 0 ]; then
    echo "    ✅ Backend token generated successfully"
else
    echo "    ❌ Backend token generation failed"
    exit 1
fi

echo ""
echo "🚀 Testing API Endpoints:"

# Test EDI endpoint with NiFi token
echo "  → Testing EDI endpoint with NiFi token..."
RESPONSE=$(curl -s -H "Authorization: Bearer $NIFI_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"edi_content":"ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *241215*1200*U*00401*000000001*0*P*>~GS*HC*SENDER*RECEIVER*20241215*1200*1*X*004010X098A1~ST*837*0001~BHT*0019*00*1*20241215*1200~SE*4*0001~GE*1*1~IEA*1*000000001~","tenant_id":"tenant-a","acknowledgment_code":"A","workflow_id":"test"}' \
    http://localhost:3001/api/v1/edi/generate-ta1)

if echo "$RESPONSE" | grep -q "ta1_content"; then
    echo "    ✅ EDI endpoint working correctly"
else
    echo "    ❌ EDI endpoint failed: $RESPONSE"
    exit 1
fi

echo ""
echo "🎉 All tests passed! Authentication configuration is working correctly."
echo ""
echo "📝 Summary of improvements:"
echo "  ✅ Removed fake/mock token generation"
echo "  ✅ All client IDs now configurable via environment variables"
echo "  ✅ Keycloak setup script uses env vars instead of hardcoded values"
echo "  ✅ Token generation script simplified and standardized"
echo "  ✅ .env.dev.example updated with clear documentation"
echo ""
echo "🔧 Usage examples:"
echo "  # Generate NiFi service token:"
echo "  python scripts/get_auth_token.py --service nifi-service"
echo ""
echo "  # Generate backend service token:"
echo "  python scripts/get_auth_token.py --service backend"
echo ""
echo "  # Generate user token (when user auth is fixed):"
echo "  python scripts/get_auth_token.py --user admin.a@edilens.com --password password --tenant tenant-a"