#!/bin/bash
set -e

echo "==============================================="
echo "NiFi Container Startup - Debug Information"
echo "==============================================="
echo "Timestamp: $(date)"
echo "Container hostname: $(hostname)"
echo "Container IP: $(hostname -i)"
echo "User: $(whoami) ($(id))"
echo ""

# === ENVIRONMENT VARIABLE DEBUGGING ===
echo "--- ENVIRONMENT VARIABLES ---"
echo "Key NiFi Configuration Variables:"
echo "  NIFI_WEB_HTTP_HOST: ${NIFI_WEB_HTTP_HOST:-NOT_SET}"
echo "  NIFI_WEB_HTTP_PORT: ${NIFI_WEB_HTTP_PORT:-NOT_SET}"
echo "  NIFI_WEB_HTTPS_HOST: ${NIFI_WEB_HTTPS_HOST:-NOT_SET}"
echo "  NIFI_WEB_HTTPS_PORT: ${NIFI_WEB_HTTPS_PORT:-NOT_SET}"
echo "  NIFI_REMOTE_INPUT_SECURE: ${NIFI_REMOTE_INPUT_SECURE:-NOT_SET}"
echo "  NIFI_CLUSTER_IS_NODE: ${NIFI_CLUSTER_IS_NODE:-NOT_SET}"
echo "  NIFI_SENSITIVE_PROPS_KEY: ${NIFI_SENSITIVE_PROPS_KEY:0:10}... (truncated)"
echo "  SINGLE_USER_CREDENTIALS_USERNAME: ${SINGLE_USER_CREDENTIALS_USERNAME:-NOT_SET}"
echo "  NIFI_LOG_LEVEL: ${NIFI_LOG_LEVEL:-NOT_SET}"
echo ""

# === SECURITY CONFIGURATION DEBUG ===
echo "--- SECURITY CONFIGURATION ---"
echo "Security-related variables:"
echo "  NIFI_SECURITY_KEYSTORE: '${NIFI_SECURITY_KEYSTORE:-NOT_SET}'"
echo "  NIFI_SECURITY_TRUSTSTORE: '${NIFI_SECURITY_TRUSTSTORE:-NOT_SET}'"
echo "  NIFI_SECURITY_USER_AUTHORIZER: '${NIFI_SECURITY_USER_AUTHORIZER:-NOT_SET}'"
echo "  NIFI_SECURITY_USER_LOGIN_IDENTITY_PROVIDER: '${NIFI_SECURITY_USER_LOGIN_IDENTITY_PROVIDER:-NOT_SET}'"
echo ""

# === FILESYSTEM CHECKS ===
echo "--- FILESYSTEM CHECKS ---"
echo "NiFi installation directory:"
ls -la /opt/nifi/ || echo "ERROR: /opt/nifi/ not found"
echo ""

echo "NiFi current directory:"
ls -la /opt/nifi/nifi-current/ || echo "ERROR: /opt/nifi/nifi-current/ not found"
echo ""

echo "NiFi conf directory:"
ls -la /opt/nifi/nifi-current/conf/ || echo "ERROR: /opt/nifi/nifi-current/conf/ not found"
echo ""

echo "NiFi scripts directory:"
ls -la /opt/nifi/nifi-current/bin/ || echo "ERROR: /opt/nifi/nifi-current/bin/ not found"
echo ""

# === PYTHON CONFIGURATION CHECKS ===
echo "--- PYTHON CONFIGURATION ---"
echo "Python command: $(which python3 2>/dev/null || echo 'NOT_FOUND')"
echo "Python version: $(python3 --version 2>/dev/null || echo 'NOT_AVAILABLE')"
echo "Python path: $PYTHONPATH"
echo ""

echo "Python extensions directory:"
if [ -d "/opt/nifi/nifi-current/python" ]; then
    echo "  Python directory exists"
    ls -la /opt/nifi/nifi-current/python/
    echo ""
    if [ -d "/opt/nifi/nifi-current/python/extensions" ]; then
        echo "  Extensions directory exists"
        ls -la /opt/nifi/nifi-current/python/extensions/
    else
        echo "  Extensions directory NOT FOUND - creating..."
        mkdir -p /opt/nifi/nifi-current/python/extensions
        echo "  Extensions directory created"
    fi
else
    echo "  Python directory NOT FOUND - creating..."
    mkdir -p /opt/nifi/nifi-current/python/extensions
    echo "  Python directory structure created"
fi
echo ""

# === JAVA CONFIGURATION ===
echo "--- JAVA CONFIGURATION ---"
echo "Java version: $(java -version 2>&1 | head -1 || echo 'NOT_AVAILABLE')"
echo "JAVA_HOME: ${JAVA_HOME:-NOT_SET}"
echo "Java options: ${JAVA_OPTS:-NOT_SET}"
echo ""

# === NIFI BOOTSTRAP CONFIGURATION ===
echo "--- BOOTSTRAP CONFIGURATION ---"
if [ -f "/opt/nifi/nifi-current/conf/bootstrap.conf" ]; then
    echo "Bootstrap configuration file exists"
    echo "Key bootstrap properties:"
    grep -E "^java.arg" /opt/nifi/nifi-current/conf/bootstrap.conf | head -5 || echo "No java.arg properties found"
else
    echo "Bootstrap configuration file NOT FOUND"
fi
echo ""

# === NETWORK CONNECTIVITY CHECKS ===
echo "--- NETWORK CONNECTIVITY ---"
echo "Hostname resolution:"
nslookup localhost 2>/dev/null | head -5 || echo "nslookup not available"
echo ""

echo "Port availability check:"
netstat -tulpn 2>/dev/null | grep ":8080" || echo "Port 8080 not in use (expected)"
echo ""

# === FINAL STARTUP MESSAGE ===
echo "==============================================="
echo "Starting NiFi with detailed logging enabled..."
echo "==============================================="
echo ""

# === EXPLICIT NIFI PROPERTIES CONFIGURATION ===
echo "--- EXPLICIT PROPERTY CONFIGURATION ---"
echo "Setting explicit nifi.properties overrides..."

# First, remove any conflicting configuration
echo "Removing conflicting configuration from nifi.properties..."
sed -i '/^nifi.web.http.port=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.web.http.host=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.remote.input.secure=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.remote.input.http.enabled=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.remote.input.http.port=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.web.https.port=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.web.https.host=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.cluster.protocol.is.secure=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.security.user.authorizer=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.security.user.login.identity.provider=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.security.user.oidc.discovery.url=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.security.user.oidc.client.id=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.security.user.oidc.client.secret=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.security.user.oidc.claim.identifying.user=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.security.user.oidc.preferred.jwsalgorithm=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.security.user.oidc.additional.scopes=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.security.user.oidc.fallback.claims.identifying.user=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.web.proxy.host=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.web.proxy.context.path=/d' /opt/nifi/nifi-current/conf/nifi.properties
sed -i '/^nifi.remote.input.host=/d' /opt/nifi/nifi-current/conf/nifi.properties

# Create a temporary properties override
cat >> /opt/nifi/nifi-current/conf/nifi.properties << 'EOF'

# === FORCE REMOTE INPUT HTTP (NOT HTTPS) ===
nifi.remote.input.secure=false
nifi.remote.input.http.enabled=true
nifi.remote.input.http.port=8081

# === ENSURE WEB HTTPS PORT IS SET (SECURE MODE ONLY) ===
nifi.web.https.port=8443
nifi.web.https.host=0.0.0.0

# === PROXY CONFIGURATION ===
nifi.web.proxy.host=localhost:8080
nifi.web.proxy.context.path=

# === REMOTE INPUT CONFIGURATION ===
nifi.remote.input.host=localhost

# === CLUSTER PROTOCOL SECURITY ===
nifi.cluster.protocol.is.secure=false

EOF

# === AUTHENTICATION CONFIGURATION ===
# Check if OIDC is configured
if [ -n "${NIFI_SECURITY_USER_OIDC_CLIENT_ID}" ] && [ -n "${NIFI_SECURITY_USER_OIDC_DISCOVERY_URL}" ]; then
    echo "OIDC authentication configured - using managed authorizer"
    cat >> /opt/nifi/nifi-current/conf/nifi.properties << 'OIDC_EOF'
    
# OIDC Authentication Configuration
nifi.security.user.authorizer=managed-authorizer
nifi.security.user.login.identity.provider=

OIDC_EOF
    
    # Add OIDC properties with variable substitution
    cat >> /opt/nifi/nifi-current/conf/nifi.properties << OIDC_VARS
nifi.security.user.oidc.discovery.url=${KEYCLOAK_URL}/realms/edi-lens/.well-known/openid-configuration
nifi.security.user.oidc.client.id=${NIFI_SECURITY_USER_OIDC_CLIENT_ID}
nifi.security.user.oidc.client.secret=${NIFI_SECURITY_USER_OIDC_CLIENT_SECRET}
nifi.security.user.oidc.claim.identifying.user=preferred_username

OIDC_VARS
else
    echo "Single user authentication configured"
    cat >> /opt/nifi/nifi-current/conf/nifi.properties << 'SINGLE_EOF'
    
# Single User Authentication Configuration  
nifi.security.user.authorizer=single-user-authorizer
nifi.security.user.login.identity.provider=single-user-provider
SINGLE_EOF
fi

echo "Properties file updated with explicit remote input configuration"
echo ""

# Enable verbose logging for the startup script
export NIFI_BOOTSTRAP_VERBOSE_LOGGING=true

# Start NiFi using the standard startup script
exec /opt/nifi/scripts/start.sh