# EDI Lens Real-Time Processing System - Design Document

## Overview

This document describes the design of a robust real-time file processing system for EDI Lens that replaces the unreliable SFTPGo event triggering mechanism with a more scalable and controllable solution.

## Problem Statement

The current implementation relies on SFTPGo to trigger events when files are uploaded via SFTP. However, we've discovered that SFTPGo does not automatically trigger filesystem events for cloud storage providers (S3, etc.). This is a known limitation where filesystem events are only triggered for local filesystem operations, not for cloud storage operations.

This limitation causes:
1. Files uploaded via SFTP to S3 are not automatically processed
2. No real-time processing capability
3. Reliance on polling mechanisms which are inefficient

## Solution Approach

Replace SFTPGo event triggering with a dedicated real-time processing system that:

1. **Independently monitors** S3 buckets for new file uploads
2. **Queues processing jobs** with priority and rate limiting
3. **Processes files** with configurable concurrency
4. **Provides monitoring** and observability

## System Architecture

### Core Components

1. **File Detection Service**
   - Monitors S3/MinIO buckets for new file uploads
   - Can use S3 event notifications or polling
   - Creates processing jobs for new files

2. **Job Queue System**
   - Message queue for job management
   - Priority-based job scheduling
   - Retry mechanism with exponential backoff
   - Dead letter queue for failed jobs

3. **Worker Pool**
   - Configurable number of concurrent workers
   - Multi-tenant aware processing
   - Resource monitoring and management

4. **Rate Limiter**
   - Per-tenant rate limits
   - Per-profile rate limits
   - Global application rate limits

5. **Event Coordinator**
   - Central coordination service
   - Configuration management
   - Monitoring and alerting

### Data Flow

```
1. File Upload → 2. File Detection → 3. Job Creation → 4. Queue → 5. Worker Processing → 6. Results
     ↑              ↑                    ↑               ↑         ↑                      ↑
   S3/MinIO    Detection Service    Event Coord.    Message Queue  Worker Pool        Storage/DB
```

## Detailed Component Design

### 1. File Detection Service

#### Responsibilities
- Monitor S3 buckets for new files
- Extract tenant/partner information from file paths
- Create processing jobs with appropriate priority

#### Implementation Options
- **S3 Event Notifications**: Most efficient, requires configuring MinIO/S3 to send events
- **Polling**: Less efficient but more compatible, periodically scans S3 buckets

#### File Path Convention
```
tenants/{tenant_id}/partners/{partner_id_or_username}/in/{filename}
```

#### Priority Determination
- Critical: Files with "critical" or "urgent" in name
- High: Files with "high" in name
- Normal: Default priority
- Low: Files with "low" or "archive" in name
- Background: Bulk processing files

### 2. Job Queue System

#### Job Structure
```json
{
  "id": "unique_job_id",
  "file_path": "tenants/tenant-a/partners/1/in/file.edi",
  "tenant_id": "tenant-a",
  "partner_id": 1,
  "profile_name": "default",
  "priority": 3,
  "created_at": "2025-01-01T10:00:00Z",
  "retry_count": 0,
  "max_retries": 3
}
```

#### Queue Prioritization
1. **Priority 1**: Critical files (e.g., time-sensitive)
2. **Priority 2**: High-importance files
3. **Priority 3**: Normal processing (default)
4. **Priority 4**: Low-priority batch files
5. **Priority 5**: Background/archival files

#### Retry Mechanism
- Exponential backoff (2^retry_count seconds)
- Maximum retry attempts per job
- Dead letter queue for persistent failures

### 3. Worker Pool

#### Worker Configuration
- Configurable maximum/minimum workers
- Dynamic scaling based on queue depth
- Health monitoring and auto-restart

#### Processing Pipeline
1. Download file from S3
2. Parse and validate EDI content
3. Apply profile rules and SNIP validation
4. Generate acknowledgments (TA1/999)
5. Archive processed file
6. Store results in database

#### Concurrency Control
- Maximum concurrent jobs per worker
- Resource usage monitoring
- Graceful shutdown handling

### 4. Rate Limiter

#### Hierarchical Limits
1. **Global Limit**: Maximum files processed per minute across entire system
2. **Tenant Limit**: Maximum files processed per minute per tenant
3. **Profile Limit**: Maximum files processed per minute per profile

#### Implementation Strategy
- Token bucket algorithm
- Sliding window for accurate rate limiting
- Configurable limit values via environment variables

### 5. Event Coordinator

#### Responsibilities
- System health monitoring
- Configuration management
- Metrics collection and reporting
- Alerting for system issues

#### Monitoring Metrics
- Processing rate (files/minute)
- Queue depth
- Worker utilization
- Error rates
- Processing time distribution

## Configuration Management

### Environment Variables

```bash
# Worker Pool Configuration
MAX_WORKERS=20
MIN_WORKERS=5
WORKER_TIMEOUT_SECONDS=300

# Rate Limiting
GLOBAL_MAX_JOBS_PER_MINUTE=1000
DEFAULT_TENANT_MAX_JOBS_PER_MINUTE=100
DEFAULT_PROFILE_MAX_JOBS_PER_MINUTE=50

# Queue Settings
QUEUE_MAX_RETRIES=3
QUEUE_RETRY_DELAY_BASE_SECONDS=5
DEAD_LETTER_QUEUE_ENABLED=true

# Monitoring
ENABLE_METRICS=true
METRICS_ENDPOINT=/metrics
```

## Deployment Architecture

### Docker Compose Services

```yaml
services:
  redis:          # Message queue and rate limiting
  s3-watcher:     # File detection service
  processor:      # Worker pool service
  coordinator:    # Event coordination service
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: file-processor
spec:
  replicas: 3  # Auto-scaling managed by HPA
  selector:
    matchLabels:
      app: file-processor
  template:
    metadata:
      labels:
        app: file-processor
    spec:
      containers:
      - name: processor
        image: edi-lens/file-processor:latest
        env:
        - name: MAX_WORKERS
          value: "15"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
```

## Scalability Considerations

### Horizontal Scaling
- Multiple worker instances processing jobs in parallel
- Load balancing across tenants
- Auto-scaling based on queue depth

### Vertical Scaling
- Increasing worker capacity per instance
- Optimizing resource usage
- Memory and CPU profiling

### Multi-region Support
- Distributed processing across regions
- Regional queue isolation
- Cross-region failover

## Fault Tolerance

### Error Handling
- Retry mechanism with exponential backoff
- Dead letter queue for persistent failures
- Circuit breaker pattern for external dependencies

### Data Durability
- Persistent job queue (Redis with persistence)
- Transactional processing
- Checkpointing for long-running jobs

### Disaster Recovery
- Backup and restore procedures
- Cross-region replication
- Automated failover

## Security Considerations

### Authentication & Authorization
- Service-to-service authentication
- Tenant isolation
- Role-based access control

### Data Protection
- Encryption at rest and in transit
- Secure credential management
- Audit logging

## Monitoring & Observability

### Metrics Collection
- Processing throughput
- Queue depth and latency
- Error rates and patterns
- Resource utilization

### Logging
- Structured logging with correlation IDs
- Log aggregation and analysis
- Alerting on critical events

### Tracing
- Distributed tracing for job processing
- Performance bottleneck identification
- End-to-end visibility

## Implementation Roadmap

### Phase 1: MVP (2-3 weeks)
- Basic file detection with S3 polling
- Redis-based job queue with single priority
- Simple worker pool with fixed concurrency
- Basic rate limiting

### Phase 2: Enhanced Features (3-4 weeks)
- S3 event notifications integration
- Priority queuing system
- Advanced rate limiting
- Monitoring and metrics

### Phase 3: Production Ready (2-3 weeks)
- Auto-scaling workers
- Comprehensive error handling
- Performance optimization
- Security hardening

### Phase 4: Advanced Features (Ongoing)
- Machine learning integration
- Multi-region support
- Advanced scheduling
- AI-powered error handling

## Integration Points

### Existing Services
- Trading partner management
- Profile configuration
- Validation and acknowledgment services
- Storage and database systems

### External Dependencies
- S3/MinIO for file storage
- Redis for job queue
- Keycloak for authentication
- PostgreSQL for data storage

## Testing Strategy

### Unit Testing
- Individual component testing
- Mock external dependencies
- Edge case coverage

### Integration Testing
- End-to-end workflow testing
- Multi-service interaction
- Performance testing

### Load Testing
- Concurrent processing simulation
- Stress testing rate limits
- Resource usage analysis

## Risk Assessment

### Technical Risks
- Redis performance under high load
- S3 polling efficiency
- Worker resource consumption

### Operational Risks
- Queue backlogs during peak times
- Failed job accumulation
- Monitoring blind spots

### Mitigation Strategies
- Performance monitoring and alerts
- Auto-scaling configuration
- Comprehensive logging and tracing

## Success Metrics

### Performance Metrics
- 99% of files processed within 30 seconds
- Queue depth consistently under 100 jobs
- 99.9% system uptime

### Business Metrics
- Reduced processing latency
- Improved system reliability
- Better resource utilization

## Future Enhancements

### Machine Learning Integration
- Predictive processing time estimation
- Intelligent queue prioritization
- Anomaly detection

### Advanced Scheduling
- Time-based processing rules
- Batch processing windows
- Resource-aware scheduling

### Multi-cloud Support
- AWS S3 integration
- Google Cloud Storage support
- Azure Blob Storage compatibility