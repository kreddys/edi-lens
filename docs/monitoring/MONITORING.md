# Monitoring System for EDI Lens

## Overview

We've implemented a comprehensive monitoring system for the EDI Lens application using:
- **Grafana** for visualization
- **Prometheus** for metrics collection
- **Loki** for log aggregation
- **Promtail** for log forwarding

All services are routed through Caddy for consistent access.

## Services and Ports

| Service    | Internal Port | External Port | URL                   |
|------------|---------------|---------------|-----------------------|
| Grafana    | 3000          | 3030          | http://localhost:3030 |
| Prometheus | 9090          | 9090          | http://localhost:9090 |
| Loki       | 3100          | 3100          | http://localhost:3100 |

## Usage

### Starting the Main Application with Monitoring

To start the main application along with monitoring services:

```bash
./run.sh dev:start --with-monitoring
```

### Starting Monitoring Services Separately

To start only the monitoring services:

```bash
./run.sh dev:monitoring:start
```

To stop the monitoring services:

```bash
./run.sh dev:monitoring:stop
```

To view logs from monitoring services:

```bash
./run.sh dev:monitoring:logs
```

## Configuration

The monitoring system is configured with:

1. **Prometheus** (`docker/monitoring/prometheus/prometheus.yml`):
   - Scrapes metrics from all EDI Lens services
   - Configured with appropriate scrape intervals for each service

2. **Loki** (using default configuration):
   - Collects logs from all Docker containers
   - No additional configuration needed for basic operation

3. **Promtail** (`docker/monitoring/promtail/promtail-config.yml`):
   - Forwards logs from Docker containers to Loki
   - Automatically discovers and labels logs from containers

4. **Grafana**:
   - Pre-configured with Prometheus and Loki as data sources
   - Includes default dashboards for immediate use
   - Default credentials: admin/admin

## Accessing the Services

After starting the services:

1. **Grafana**: http://localhost:3030
   - Default credentials: admin/admin
   - Pre-configured with Prometheus and Loki data sources
   - Includes default dashboards:
     - Home Dashboard (`edi-lens-home`): Default landing page
     - Logs Dashboard (`edi-lens-logs`): Log volume and detailed views
     - Metrics Dashboard (`edi-lens-metrics`): Application metrics

2. **Prometheus**: http://localhost:9090
   - Use the web interface to explore metrics

3. **Loki**: http://localhost:3100
   - Accessed primarily through Grafana

## Default Dashboards

Grafana comes with three pre-configured dashboards to help you get started immediately:

### 1. Home Dashboard (`edi-lens-home`)
- Default landing page that loads when you access Grafana
- Welcome message with quick navigation links
- Panel showing recent errors and warnings from all services

### 2. Logs Dashboard (`edi-lens-logs`)
- Comprehensive log viewing dashboard
- Log volume by service (timeseries chart)
- All service logs panel
- Backend service logs panel
- Auto-refresh every 5 seconds

### 3. Metrics Dashboard (`edi-lens-metrics`)
- Application metrics dashboard
- Service status panel
- HTTP request rate panel
- Auto-refresh every 5 seconds

## Using the Dashboards

1. **Access Grafana**: Open http://localhost:3030 in your browser
2. **Log in**: Use the default credentials (admin/admin)
3. **Navigate Dashboards**: 
   - The Home Dashboard will load by default
   - Use the links in the Home Dashboard to navigate to other dashboards
   - Or use the dashboard selector in the left sidebar

4. **View Logs**:
   - In the Logs Dashboard, you can see log volume charts and detailed logs
   - Filter by time range using the selector in the top right
   - Click on any log line to see its details

5. **View Metrics**:
   - In the Metrics Dashboard, you can see service status and request rates
   - Panels automatically refresh every 5 seconds

## Customizing Dashboards

You can customize the dashboards directly in Grafana:
1. Open any dashboard
2. Click the gear icon in the top right
3. Select "Add panel" to add new visualizations
4. Use the "Save" button to save your changes

## Next Steps

1. Create custom dashboards in Grafana for your specific metrics
2. Set up alerting rules in Prometheus
3. Configure more detailed logging in your application services
4. Add additional exporters for more detailed metrics (e.g., PostgreSQL exporter)