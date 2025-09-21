#!/bin/bash
# Check status of all EDI-Lens services

echo "=== EDI-Lens Service Status ==="
echo ""

check_service() {
    local name="$1"
    local url="$2"
    local process="$3"
    local extra="$4"

    printf "%-15s " "$name:"

    if [ -n "$process" ] && pgrep -f "$process" >/dev/null; then
        if [ -n "$url" ]; then
            local curl_opts=""
            if [ "$extra" = "-k" ]; then
                curl_opts="-k"
            fi
            if curl -fs $curl_opts "$url" >/dev/null 2>&1; then
                echo "✅ HEALTHY"
            else
                echo "🟡 STARTING"
            fi
        else
            echo "✅ RUNNING"
        fi
    else
        echo "❌ STOPPED"
    fi
}

check_service "PostgreSQL" "" "postgres"
check_service "MinIO" "http://localhost:9000/minio/health/live" "minio"
check_service "Keycloak" "http://localhost:8180" "keycloak"
check_service "SFTPGo" "http://localhost:8280/healthz" "sftpgo"
check_service "NiFi Registry" "http://localhost:18080/nifi-registry/" "nifi-registry"
check_service "NiFi" "https://localhost:8443/nifi-api/system-diagnostics" "nifi" "-k"
check_service "Backend" "http://localhost:8000/api/v1/health" "uvicorn"
check_service "Frontend" "http://localhost:3000" "npm"

echo ""
echo "Service URLs:"
echo "  Frontend:        http://localhost:3000"
echo "  Backend API:     http://localhost:8000"
echo "  API Docs:        http://localhost:8000/docs"
echo "  Keycloak:        http://localhost:8180"
echo "  SFTPGo:          http://localhost:8280"
echo "  MinIO Console:   http://localhost:9001"
echo "  NiFi:            https://localhost:8443"
echo "  NiFi Registry:   http://localhost:18080"
echo ""
echo "Logs available in: codex-services/logs/"
