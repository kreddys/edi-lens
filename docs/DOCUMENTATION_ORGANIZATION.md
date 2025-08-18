# Documentation Organization Summary

This file summarizes how the documentation has been organized in the EDI Lens project.

## Documentation Structure

### Root Directory
- `README.md` - Main project README with references to documentation

### docs/ Directory
- `README.md` - Main documentation README
- `architecture.md` - System architecture and design decisions
- `user_guide.md` - Instructions for using the application
- `keycloak_setup_guide.md` - Configuration guide for Keycloak

### docs/adr/ Directory
- Architectural Decision Records (ADRs) documenting important technical choices

### docs/monitoring/ Directory
All monitoring-related documentation has been moved here:

1. **Main Monitoring Documentation**:
   - `MONITORING.md` - Complete guide to the monitoring system
   - `MONITORING_ENHANCED_SUMMARY.md` - Summary of enhancements with default dashboards
   - `MONITORING_FINAL_SUMMARY.md` - Final implementation summary
   - `MONITORING_KEY_FILES.md` - Key files and configurations
   - `MONITORING_STATUS_SUMMARY.md` - Status summary during implementation

2. **Docker Monitoring Documentation**:
   - `DOCKER_MONITORING.md` - Documentation for the Docker monitoring stack

3. **Grafana Dashboards Documentation**:
   - `docker/monitoring/grafana/provisioning/dashboards/README.md` - Dashboard documentation

## Access Points

### Main Project README
- References to monitoring documentation in `docs/monitoring/`

### Monitoring Documentation
- Comprehensive guides and summaries in `docs/monitoring/`
- Docker-specific documentation in `docs/monitoring/DOCKER_MONITORING.md`

### Grafana Dashboards
- Documentation in `docker/monitoring/grafana/provisioning/dashboards/README.md`

## Benefits of This Organization

1. **Centralized Documentation**: All monitoring documentation is now in one place
2. **Easy Navigation**: Clear structure makes it easy to find relevant information
3. **Reduced Clutter**: Root directory is cleaner without multiple documentation files
4. **Better Organization**: Related documentation is grouped together
5. **Maintainable**: Easier to update and maintain documentation in logical groups

## Files Moved

The following files were moved from the root directory to `docs/monitoring/`:
- `MONITORING.md`
- `MONITORING_FINAL_SUMMARY.md`
- `MONITORING_STATUS_SUMMARY.md`
- `MONITORING_KEY_FILES.md`
- `MONITORING_ENHANCED_SUMMARY.md`

The following file was moved from `docker/monitoring/` to `docs/monitoring/`:
- `README.md` (renamed to `DOCKER_MONITORING.md`)