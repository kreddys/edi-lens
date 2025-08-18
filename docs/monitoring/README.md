# Monitoring Documentation

This directory contains documentation for the monitoring system implemented in the EDI Lens application.

## Overview

The EDI Lens application includes a comprehensive monitoring stack with Grafana, Loki, and Prometheus for centralized logging and metrics visualization.

## Documentation Files

1. **[MONITORING.md](MONITORING.md)** - Complete guide to the monitoring system
2. **[MONITORING_ENHANCED_SUMMARY.md](MONITORING_ENHANCED_SUMMARY.md)** - Summary of enhancements with default dashboards
3. **[MONITORING_FINAL_SUMMARY.md](MONITORING_FINAL_SUMMARY.md)** - Final implementation summary
4. **[MONITORING_KEY_FILES.md](MONITORING_KEY_FILES.md)** - Key files and configurations
5. **[MONITORING_STATUS_SUMMARY.md](MONITORING_STATUS_SUMMARY.md)** - Status summary during implementation
6. **[DOCKER_MONITORING.md](DOCKER_MONITORING.md)** - Documentation for the Docker monitoring stack

## Accessing Monitoring Services

- **Grafana**: http://localhost:3030 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Loki**: http://localhost:3100

## Default Dashboards

Grafana comes with three pre-configured dashboards:
1. **Home Dashboard** (`edi-lens-home`): Default landing page with quick navigation
2. **Logs Dashboard** (`edi-lens-logs`): Comprehensive log viewing with log volume charts
3. **Metrics Dashboard** (`edi-lens-metrics`): Application metrics visualization

## Usage

### Starting the System
The monitoring system can be started in two ways:

1. **Integrated with main application**:
   ```bash
   ./run.sh dev:start --with-monitoring
   ```

2. **Separately**:
   ```bash
   ./run.sh dev:monitoring:start
   ```