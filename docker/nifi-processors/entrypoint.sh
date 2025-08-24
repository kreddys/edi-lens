#!/bin/bash
set -e

echo "============================================="
echo "NiFi Container Startup - Single User Setup"
echo "============================================="
echo "Timestamp: $(date)"
echo "Container hostname: $(hostname)"
echo ""

# === ENVIRONMENT VALIDATION ===
echo "--- ENVIRONMENT VALIDATION ---"

# Validate required basic configuration
if [ -z "${NIFI_SENSITIVE_PROPS_KEY}" ]; then
    echo "ERROR: NIFI_SENSITIVE_PROPS_KEY must be set (32 characters)"
    exit 1
fi

if [ ${#NIFI_SENSITIVE_PROPS_KEY} -ne 32 ]; then
    echo "ERROR: NIFI_SENSITIVE_PROPS_KEY must be exactly 32 characters (current: ${#NIFI_SENSITIVE_PROPS_KEY})"
    exit 1
fi

# Validate authentication configuration
if [ -z "${NIFI_USERNAME}" ]; then
    echo "ERROR: NIFI_USERNAME must be set"
    exit 1
fi

if [ -z "${NIFI_PASSWORD}" ]; then
    echo "ERROR: NIFI_PASSWORD must be set"
    exit 1
fi

echo "✓ All required environment variables are set"
echo ""

# === CONFIGURE AUTHENTICATION ===
echo "--- CONFIGURING SINGLE USER AUTHENTICATION ---"
echo "Setting NiFi single user credentials using official NiFi command..."

# Use NiFi's built-in command to set single user credentials
/opt/nifi/nifi-current/bin/nifi.sh set-single-user-credentials "${NIFI_USERNAME}" "${NIFI_PASSWORD}"

echo "✓ Single user credentials configured successfully"
echo ""

# === CONFIGURATION SUMMARY ===
echo "--- NiFi CONFIGURATION SUMMARY ---"
echo "Authentication: Single User (${NIFI_USERNAME} / ***)"
echo "Web Proxy Host: ${NIFI_WEB_PROXY_HOST}"
echo ""

# === FINAL STARTUP ===
echo "============================================="
echo "Starting NiFi with single-user authentication..."
echo "Web UI will be available at: http://localhost:8080"
echo "============================================="
echo ""

# Start NiFi using the standard startup script
exec /opt/nifi/scripts/start.sh