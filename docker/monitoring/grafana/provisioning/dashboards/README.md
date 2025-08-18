# Grafana Dashboards

This directory contains pre-configured Grafana dashboards for the EDI Lens application.

## Available Dashboards

### 1. EDI Lens - Home (`edi-lens-home.json`)
- **Purpose**: Default home dashboard that loads when you access Grafana
- **Features**:
  - Welcome message with links to other dashboards
  - Recent errors and warnings panel
  - Quick navigation to other dashboards

### 2. EDI Lens Application Logs (`edi-lens-logs.json`)
- **Purpose**: Comprehensive log viewing dashboard
- **Features**:
  - Log volume by service (timeseries chart)
  - All service logs panel
  - Backend service logs panel
  - Auto-refresh every 5 seconds

### 3. EDI Lens Application Metrics (`edi-lens-metrics.json`)
- **Purpose**: Application metrics dashboard
- **Features**:
  - Service status panel
  - HTTP request rate panel
  - Auto-refresh every 5 seconds

## Accessing Dashboards

1. **Home Dashboard**: Automatically loads when you access Grafana at http://localhost:3030
2. **Direct Access**: You can access any dashboard directly using its UID:
   - Home: http://localhost:3030/d/edi-lens-home/edi-lens---home
   - Logs: http://localhost:3030/d/edi-lens-logs/edi-lens-application-logs
   - Metrics: http://localhost:3030/d/edi-lens-metrics/edi-lens-application-metrics

## Customization

You can modify these dashboards directly in Grafana:
1. Open the dashboard you want to modify
2. Click the gear icon in the top right
3. Select "Save as..." to create a copy, or "Save" to overwrite the existing dashboard

## Adding New Dashboards

To add new dashboards:
1. Create a JSON file with your dashboard configuration
2. Place it in this directory (`docker/monitoring/grafana/provisioning/dashboards/`)
3. Restart the Grafana service: `./run.sh dev:monitoring:stop && ./run.sh dev:monitoring:start`

## Documentation

For more information about the monitoring system, see the documentation in [docs/monitoring/](../../../../docs/monitoring/).