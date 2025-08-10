# EDI Lens - SFTP Processing Testing

## Current Status

We have identified and documented a comprehensive solution for the SFTP processing issue. Instead of relying on SFTPGo event triggering (which doesn't work with cloud storage), we're implementing a robust real-time processing system with job queuing and rate limiting.

## Root Cause Analysis

After extensive debugging, we identified that SFTPGo does not automatically trigger filesystem events for cloud storage providers (S3, etc.). This is a known limitation where filesystem events are only triggered for local filesystem operations, not for cloud storage operations.

The logs clearly showed:
- Files are successfully uploaded to S3 through SFTP
- Event rules and actions are properly configured in SFTPGo
- Manual webhook calls to the backend work correctly
- Backend processing works correctly when the webhook is called manually
- But automatic webhook triggering is not happening because SFTPGo doesn't trigger events for S3 operations

## Solution Approach

We are implementing a dedicated real-time processing system that:

1. **Independently monitors** S3 buckets for new file uploads
2. **Queues processing jobs** with priority and rate limiting
3. **Processes files** with configurable concurrency
4. **Provides monitoring** and observability

## System Design

See detailed design in `/docs/realtime-processing-system-design.md`

### Core Components

1. **File Detection Service** - Monitors S3/MinIO buckets for new file uploads
2. **Job Queue System** - Message queue for job management with priority support
3. **Worker Pool** - Processes files with configurable concurrency
4. **Rate Limiter** - Controls processing rate per tenant/profile/application
5. **Event Coordinator** - Central coordination with monitoring

### Data Flow

```
[S3/MinIO] → [File Detection] → [Job Queue] → [Worker Pool] → [Processing Pipeline]
```

## Implementation Status

### Completed
- ✅ Root cause analysis and documentation
- ✅ Comprehensive system design document
- ✅ Architecture planning and component design

### In Progress
- ⏳ Initial implementation of core components
- ⏳ Integration with existing processing pipeline
- ⏳ Testing and validation

### Pending
- ⏳ Full system integration
- ⏳ Performance optimization
- ⏳ Production deployment configuration

## Testing Process (Future)

1. Start the processing system:
   ```
   # Start core services first
   ./run.sh dev:start
   
   # Start processing services (planned)
   ./scripts/start_processing.sh
   ```

2. Upload a test EDI file via SFTP:
   ```
   # Use one of the test files from data/test-files/
   ./scripts/upload_to_sftp.sh data/test-files/test-file-2.edi test123_{timestamp} test123_{timestamp}
   ```

3. Monitor the processing:
   ```
   # Check processor logs (planned)
   docker logs realtime-processor
   
   # Check queue status (planned)
   docker exec redis redis-cli llen queue:normal
   ```

## Expected Behavior (After Implementation)

When a file is uploaded to the SFTP server:
1. File Detection Service identifies the new file in the S3 bucket
2. A processing job is created and added to the job queue
3. Worker Pool processes the job according to priority and rate limits
4. The file is validated according to the partner's profile
5. Appropriate acknowledgments (TA1/999) are generated
6. The original file is archived
7. Responses are stored in the partner's out directory

## Benefits of New Approach

1. **Reliability**: No dependency on SFTPGo event triggering
2. **Scalability**: Configurable worker pools and rate limiting
3. **Observability**: Comprehensive monitoring and metrics
4. **Control**: Fine-grained control over processing resources
5. **Flexibility**: Support for different processing priorities

## Available Test Files

We have several EDI test files available in `data/test-files/` that can be used for testing:
- test-file-2.edi
- test-file-3.edi
- test-file-4.edi
- test-file-5.edi
- test-file-6.edi

## Next Steps

1. Implement core components based on design document
2. Integrate with existing validation and acknowledgment services
3. Set up monitoring and alerting
4. Conduct thorough testing
5. Deploy to staging environment
6. Plan production rollout