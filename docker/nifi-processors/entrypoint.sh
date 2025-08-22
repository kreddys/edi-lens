#!/bin/bash

echo "--- Starting NiFi with Python Extensions ---"

# Configure NiFi for HTTPS with container access
export NIFI_WEB_HTTPS_HOST=0.0.0.0
export NIFI_WEB_HTTPS_PORT=8443

# Ensure Python is available  
export NIFI_PYTHON_COMMAND=/usr/bin/python3

# Manually update the Python extensions directory property in nifi.properties
sed -i 's|nifi.python.extensions.source.directory.default=.*|nifi.python.extensions.source.directory.default=/opt/nifi/nifi-current/python/extensions|g' /opt/nifi/nifi-current/conf/nifi.properties

echo "Configuration: HTTPS on ${NIFI_WEB_HTTPS_HOST}:${NIFI_WEB_HTTPS_PORT}, Python: $NIFI_PYTHON_COMMAND"
echo "Python Extensions: /opt/nifi/nifi-current/python/extensions"
echo "Updated nifi.properties with correct Python extensions path"

# Use the original NiFi startup script
exec /opt/nifi/scripts/start.sh