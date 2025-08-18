# Monitoring Stack for EDI Lens

This directory contains the configuration files for the monitoring stack used in the EDI Lens application. The stack consists of:

1. **Loki** - For log aggregation
2. **Prometheus** - For metrics collection
3. **Grafana** - For visualization
4. **Promtail** - For log forwarding to Loki

## Services Overview

- **Grafana**: http://localhost:3030 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Loki**: http://localhost:3100

## Usage

The monitoring services can be started in two ways:

1. **Separately**: Using the dedicated commands:
   ```bash
   ./run.sh dev:monitoring:start
   ./run.sh dev:monitoring:stop
   ./run.sh dev:monitoring:logs
   ```

2. **Together with the main application**: Using the `--with-monitoring` flag:
   ```bash
   ./run.sh dev:start --with-monitoring
   ```

## Configuration Files

- `prometheus/prometheus.yml` - Prometheus configuration
- `promtail/promtail-config.yml` - Promtail configuration for log forwarding

## Accessing the Services

After starting the monitoring services:

1. **Grafana**:
   - URL: http://localhost:3030
   - Default credentials: admin/admin
   - Pre-configured datasources for Prometheus and Loki

2. **Prometheus**:
   - URL: http://localhost:9090
   - Use the web interface to explore metrics

3. **Loki**:
   - URL: http://localhost:3100
   - Accessed primarily through Grafana

## Setting up Dashboards

Grafana dashboards can be created manually or imported. Some recommended dashboards for the services in this stack include:

- Docker monitoring dashboards
- System metrics dashboards
- Application-specific dashboards

For more information about the monitoring system, see the main documentation in [docs/monitoring/](../../docs/monitoring/).