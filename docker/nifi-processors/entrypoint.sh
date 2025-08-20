#!/bin/bash
set -ex

echo "--- NiFi Entrypoint Script is running! ---"

ls -l /opt/nifi/nifi-current/bin

exec /opt/nifi/nifi-current/bin/nifi.sh run