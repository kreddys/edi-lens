# Missing Built-in Templates Specification

**Date**: August 16, 2025  
**Author**: Assistant  
**Status**: Complete Built-in Template Requirements  

## Overview

This document specifies the built-in workflow templates that are required by our system design but are currently **0% implemented**. According to `02-template-system.md`, we should have pre-built templates for common EDI processing patterns, but none exist in the current implementation.

## 🏗️ Required Built-in Templates

### 1. SFTP EDI Processor Template

#### Template Specification
```json
{
    "template_id": "global-sftp-edi-processor-v1.0",
    "name": "SFTP EDI File Processor",
    "description": "Monitors SFTP directories for EDI files and processes them with validation and acknowledgment generation",
    "category": "BATCH",
    "scope": "GLOBAL",
    "tenant_id": null,
    "maintainer": "edi-lens-platform",
    "based_on": null,
    "version": "1.0",
    "deployment_method": "registry",
    "tags": ["sftp", "edi", "batch", "validation", "acknowledgments"],
    "features": [
        "sftp-monitoring",
        "edi-validation", 
        "ta1-generation",
        "999-generation",
        "file-archival",
        "error-handling"
    ],
    "is_featured": true,
    "status": "ACTIVE"
}
```

#### Flow Definition Structure
```json
{
    "flow_definition": {
        "processors": [
            {
                "id": "list-sftp-processor",
                "type": "ListSFTP",
                "name": "Monitor SFTP Directory",
                "properties": {
                    "Hostname": "#{SFTP_HOSTNAME}",
                    "Username": "#{SFTP_USERNAME}",
                    "Password": "#{SFTP_PASSWORD}",
                    "Remote Path": "#{INPUT_PATH}",
                    "Search Recursively": "false",
                    "File Filter Regex": "#{FILE_PATTERN_REGEX}",
                    "Listing Strategy": "Tracking Timestamps",
                    "Minimum File Age": "0 sec"
                },
                "auto_terminated_relationships": [],
                "scheduling": {
                    "scheduling_period": "#{POLLING_INTERVAL:5 sec}",
                    "concurrent_tasks": 1
                }
            },
            {
                "id": "fetch-sftp-processor", 
                "type": "FetchSFTP",
                "name": "Fetch EDI Files",
                "properties": {
                    "Hostname": "#{SFTP_HOSTNAME}",
                    "Username": "#{SFTP_USERNAME}",
                    "Password": "#{SFTP_PASSWORD}",
                    "Completion Strategy": "Move File",
                    "Move Destination Directory": "#{PROCESSING_PATH}"
                }
            },
            {
                "id": "validate-edi-processor",
                "type": "InvokeHTTP",
                "name": "Validate EDI Content",
                "properties": {
                    "HTTP Method": "POST",
                    "Remote URL": "#{EDI_LENS_API_URL}/api/v1/edi/validate-batch",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer #{EDI_LENS_SERVICE_TOKEN}",
                    "HTTP Message Body": "{\n  \"edi_content\": \"${file.content:escapeJson()}\",\n  \"tenant_id\": \"#{TENANT_ID}\",\n  \"workflow_id\": \"#{WORKFLOW_ID}\",\n  \"validation_schema\": \"#{VALIDATION_SCHEMA}\",\n  \"snip_level\": #{SNIP_LEVEL:3},\n  \"file_name\": \"${filename}\",\n  \"callback_url\": \"#{NIFI_CALLBACK_URL}\",\n  \"generate_ta1\": #{GENERATE_TA1:true},\n  \"generate_999\": #{GENERATE_999:false}\n}"
                }
            },
            {
                "id": "route-validation-results",
                "type": "RouteOnAttribute",
                "name": "Route Validation Results",
                "properties": {
                    "Routing Strategy": "Route to Property name"
                },
                "dynamic_properties": {
                    "validation_success": "${http.status.code:equals('200')}"
                }
            },
            {
                "id": "extract-ta1-processor",
                "type": "EvaluateJsonPath",
                "name": "Extract TA1 Acknowledgment",
                "properties": {
                    "Destination": "flowfile-attribute",
                    "ta1.content": "$.ta1_content",
                    "job.id": "$.job_id",
                    "validation.valid": "$.valid"
                }
            },
            {
                "id": "write-ta1-processor",
                "type": "PutSFTP",
                "name": "Write TA1 Acknowledgment",
                "properties": {
                    "Hostname": "#{SFTP_HOSTNAME}",
                    "Username": "#{SFTP_USERNAME}",
                    "Password": "#{SFTP_PASSWORD}",
                    "Remote Path": "#{TA1_OUTPUT_PATH}",
                    "Remote Filename": "${filename:substringBeforeLast('.')}_TA1_${now():format('yyyyMMdd_HHmmss')}.edi",
                    "Create Directory": "true"
                }
            },
            {
                "id": "archive-success-processor",
                "type": "PutSFTP", 
                "name": "Archive Successful Files",
                "properties": {
                    "Hostname": "#{SFTP_HOSTNAME}",
                    "Username": "#{SFTP_USERNAME}",
                    "Password": "#{SFTP_PASSWORD}",
                    "Remote Path": "#{SUCCESS_ARCHIVE_PATH}",
                    "Remote Filename": "${filename}",
                    "Create Directory": "true"
                }
            },
            {
                "id": "archive-error-processor",
                "type": "PutSFTP",
                "name": "Archive Error Files", 
                "properties": {
                    "Hostname": "#{SFTP_HOSTNAME}",
                    "Username": "#{SFTP_USERNAME}",
                    "Password": "#{SFTP_PASSWORD}",
                    "Remote Path": "#{ERROR_ARCHIVE_PATH}",
                    "Remote Filename": "${filename}",
                    "Create Directory": "true"
                }
            },
            {
                "id": "log-success-processor",
                "type": "LogAttribute",
                "name": "Log Successful Processing",
                "properties": {
                    "Log Level": "info",
                    "Log Prefix": "EDI Processing Success",
                    "Attributes to Log": "filename,job.id,validation.valid,ta1.content"
                }
            },
            {
                "id": "log-error-processor", 
                "type": "LogAttribute",
                "name": "Log Processing Errors",
                "properties": {
                    "Log Level": "error",
                    "Log Prefix": "EDI Processing Error",
                    "Attributes to Log": "filename,http.status.code,http.response.body"
                }
            }
        ],
        "connections": [
            {
                "source_id": "list-sftp-processor",
                "destination_id": "fetch-sftp-processor",
                "relationships": ["success"]
            },
            {
                "source_id": "fetch-sftp-processor",
                "destination_id": "validate-edi-processor", 
                "relationships": ["success"]
            },
            {
                "source_id": "validate-edi-processor",
                "destination_id": "route-validation-results",
                "relationships": ["response"]
            },
            {
                "source_id": "route-validation-results",
                "destination_id": "extract-ta1-processor",
                "relationships": ["validation_success"]
            },
            {
                "source_id": "extract-ta1-processor",
                "destination_id": "write-ta1-processor",
                "relationships": ["matched"]
            },
            {
                "source_id": "write-ta1-processor",
                "destination_id": "archive-success-processor",
                "relationships": ["success"]
            },
            {
                "source_id": "archive-success-processor", 
                "destination_id": "log-success-processor",
                "relationships": ["success"]
            },
            {
                "source_id": "route-validation-results",
                "destination_id": "archive-error-processor",
                "relationships": ["unmatched"]
            },
            {
                "source_id": "archive-error-processor",
                "destination_id": "log-error-processor",
                "relationships": ["success"]
            }
        ],
        "parameter_contexts": [
            {
                "name": "EDI-Processing-Parameters",
                "description": "Parameters for EDI processing workflow",
                "parameters": [
                    {
                        "name": "TENANT_ID",
                        "description": "Tenant identifier",
                        "sensitive": false
                    },
                    {
                        "name": "WORKFLOW_ID", 
                        "description": "Workflow identifier",
                        "sensitive": false
                    },
                    {
                        "name": "INPUT_PATH",
                        "description": "SFTP input directory path",
                        "sensitive": false
                    },
                    {
                        "name": "SUCCESS_ARCHIVE_PATH",
                        "description": "Path for successful file archive",
                        "sensitive": false
                    },
                    {
                        "name": "ERROR_ARCHIVE_PATH",
                        "description": "Path for error file archive", 
                        "sensitive": false
                    },
                    {
                        "name": "TA1_OUTPUT_PATH",
                        "description": "Path for TA1 acknowledgment output",
                        "sensitive": false
                    },
                    {
                        "name": "VALIDATION_SCHEMA",
                        "description": "EDI validation schema file name",
                        "sensitive": false
                    },
                    {
                        "name": "SNIP_LEVEL",
                        "description": "EDI validation SNIP level",
                        "sensitive": false,
                        "value": "3"
                    },
                    {
                        "name": "GENERATE_TA1",
                        "description": "Whether to generate TA1 acknowledgments",
                        "sensitive": false,
                        "value": "true"
                    },
                    {
                        "name": "GENERATE_999", 
                        "description": "Whether to generate 999 acknowledgments",
                        "sensitive": false,
                        "value": "false"
                    },
                    {
                        "name": "SFTP_HOSTNAME",
                        "description": "SFTP server hostname",
                        "sensitive": false
                    },
                    {
                        "name": "SFTP_USERNAME",
                        "description": "SFTP username",
                        "sensitive": false
                    },
                    {
                        "name": "SFTP_PASSWORD",
                        "description": "SFTP password",
                        "sensitive": true
                    },
                    {
                        "name": "EDI_LENS_API_URL",
                        "description": "EDI Lens API base URL",
                        "sensitive": false,
                        "value": "http://backend:8000"
                    },
                    {
                        "name": "EDI_LENS_SERVICE_TOKEN",
                        "description": "EDI Lens service authentication token",
                        "sensitive": true
                    },
                    {
                        "name": "NIFI_CALLBACK_URL", 
                        "description": "NiFi callback URL for batch processing",
                        "sensitive": false
                    }
                ]
            }
        ]
    }
}
```

#### Configuration Schema
```json
{
    "configuration_schema": {
        "type": "object",
        "required": [
            "input_path",
            "file_patterns", 
            "validation",
            "sftp_connection",
            "output_paths"
        ],
        "properties": {
            "input_path": {
                "type": "string",
                "title": "Input Directory Path",
                "description": "SFTP directory to monitor for incoming EDI files",
                "pattern": "^/sftp/tenants/[^/]+/.+/$",
                "examples": ["/sftp/tenants/tenant-a/claims/in/"]
            },
            "file_patterns": {
                "type": "array",
                "title": "File Patterns",
                "description": "File patterns to match (glob patterns)",
                "items": {
                    "type": "string"
                },
                "minItems": 1,
                "examples": [["*.edi", "*.x12"]]
            },
            "polling_interval": {
                "type": "string",
                "title": "Polling Interval",
                "description": "How often to check for new files",
                "default": "30 sec",
                "pattern": "^\\d+\\s+(sec|min|hour)$"
            },
            "validation": {
                "type": "object",
                "title": "Validation Configuration",
                "required": ["schema"],
                "properties": {
                    "schema": {
                        "type": "string",
                        "title": "EDI Schema",
                        "description": "EDI schema file for validation",
                        "examples": ["837.5010.X222.A1.json"]
                    },
                    "snip_level": {
                        "type": "integer",
                        "title": "SNIP Level",
                        "description": "Validation strictness level",
                        "minimum": 1,
                        "maximum": 5,
                        "default": 3
                    }
                }
            },
            "acknowledgments": {
                "type": "object",
                "title": "Acknowledgment Configuration",
                "properties": {
                    "generate_ta1": {
                        "type": "boolean",
                        "title": "Generate TA1",
                        "description": "Generate TA1 interchange acknowledgments",
                        "default": true
                    },
                    "generate_999": {
                        "type": "boolean", 
                        "title": "Generate 999",
                        "description": "Generate 999 functional acknowledgments",
                        "default": false
                    },
                    "ta1_output_path": {
                        "type": "string",
                        "title": "TA1 Output Path",
                        "description": "Directory for TA1 acknowledgment files",
                        "pattern": "^/sftp/tenants/[^/]+/.+/$"
                    }
                }
            },
            "sftp_connection": {
                "type": "object",
                "title": "SFTP Connection",
                "required": ["hostname", "username"],
                "properties": {
                    "hostname": {
                        "type": "string",
                        "title": "SFTP Hostname",
                        "description": "SFTP server hostname or IP address"
                    },
                    "port": {
                        "type": "integer",
                        "title": "SFTP Port",
                        "description": "SFTP server port",
                        "default": 22,
                        "minimum": 1,
                        "maximum": 65535
                    },
                    "username": {
                        "type": "string",
                        "title": "SFTP Username",
                        "description": "SFTP authentication username"
                    },
                    "password": {
                        "type": "string",
                        "title": "SFTP Password", 
                        "description": "SFTP authentication password",
                        "format": "password"
                    }
                }
            },
            "output_paths": {
                "type": "object",
                "title": "Output Path Configuration",
                "required": ["success_archive", "error_archive"],
                "properties": {
                    "success_archive": {
                        "type": "string",
                        "title": "Success Archive Path",
                        "description": "Directory for successfully processed files",
                        "pattern": "^/sftp/tenants/[^/]+/.+/$"
                    },
                    "error_archive": {
                        "type": "string", 
                        "title": "Error Archive Path",
                        "description": "Directory for files with processing errors",
                        "pattern": "^/sftp/tenants/[^/]+/.+/$"
                    },
                    "processing_temp": {
                        "type": "string",
                        "title": "Processing Temp Path",
                        "description": "Temporary directory during processing",
                        "pattern": "^/sftp/tenants/[^/]+/.+/$"
                    }
                }
            },
            "error_handling": {
                "type": "object",
                "title": "Error Handling Configuration",
                "properties": {
                    "max_retries": {
                        "type": "integer",
                        "title": "Max Retries",
                        "description": "Maximum retry attempts for failed files",
                        "default": 3,
                        "minimum": 0,
                        "maximum": 10
                    },
                    "retry_delay": {
                        "type": "string",
                        "title": "Retry Delay",
                        "description": "Delay between retry attempts",
                        "default": "5 min",
                        "pattern": "^\\d+\\s+(sec|min|hour)$"
                    }
                }
            }
        }
    }
}
```

#### Documentation
```markdown
# SFTP EDI File Processor Template

## Overview
This template monitors SFTP directories for incoming EDI files, validates them against specified schemas, generates acknowledgments (TA1/999), and archives files appropriately.

## Use Cases
- **Healthcare Claims Processing**: Process 837P claim files from trading partners
- **Remittance Processing**: Handle 835 remittance advice files
- **Eligibility Processing**: Process 270/271 eligibility request/response files
- **Any EDI batch processing**: Generic EDI file processing workflow

## Configuration Requirements

### SFTP Connection
- **Hostname**: SFTP server address
- **Port**: SFTP port (default: 22)
- **Username/Password**: Authentication credentials
- **Directories**: Input, archive, and output paths

### File Processing
- **File Patterns**: Glob patterns for file matching (e.g., "*.edi", "*.x12")
- **Polling Interval**: How often to check for new files
- **Validation Schema**: EDI schema for content validation

### Acknowledgments
- **TA1 Generation**: Interchange acknowledgments (recommended: enabled)
- **999 Generation**: Functional acknowledgments (optional)
- **Output Paths**: Where to place acknowledgment files

## Processing Flow
1. **Monitor**: Continuously monitor SFTP input directory
2. **Fetch**: Download detected files to processing area
3. **Validate**: Send to EDI Lens API for validation
4. **Generate**: Create TA1/999 acknowledgments if configured
5. **Archive**: Move files to success/error directories
6. **Log**: Record processing results for monitoring

## Security Considerations
- SFTP credentials are stored as sensitive parameters
- API tokens are encrypted in parameter contexts
- File paths are validated for tenant isolation
- All file operations maintain audit trails

## Monitoring
- Processing logs include file names and results
- Failed files are archived separately for review
- Metrics include throughput and error rates
- Health checks validate SFTP connectivity

## Performance
- Concurrent processing: 1 file at a time (configurable)
- Polling efficiency: Uses timestamp tracking
- Resource usage: Minimal memory footprint
- Scalability: Horizontal scaling via NiFi clustering
```

### 2. HTTP EDI Processor Template

#### Template Specification
```json
{
    "template_id": "global-http-edi-processor-v1.0",
    "name": "HTTP EDI Processor",
    "description": "Processes EDI transactions via HTTP endpoints in real-time with immediate response",
    "category": "REALTIME",
    "scope": "GLOBAL",
    "tenant_id": null,
    "maintainer": "edi-lens-platform",
    "based_on": null,
    "version": "1.0",
    "deployment_method": "registry",
    "tags": ["http", "edi", "realtime", "api", "synchronous"],
    "features": [
        "http-listener",
        "real-time-validation",
        "immediate-response",
        "ta1-generation",
        "api-integration"
    ],
    "is_featured": true,
    "status": "ACTIVE"
}
```

#### Flow Definition Structure
```json
{
    "flow_definition": {
        "processors": [
            {
                "id": "listen-http-processor",
                "type": "ListenHTTP",
                "name": "HTTP EDI Endpoint",
                "properties": {
                    "Listening Port": "#{HTTP_LISTENING_PORT}",
                    "Base Path": "#{HTTP_BASE_PATH}",
                    "HTTP Context Map": "edi-http-context",
                    "HTTP Headers to Receive as Attributes": "Authorization,X-Tenant-ID,Content-Type",
                    "Max Data Size": "#{MAX_PAYLOAD_SIZE:10 MB}",
                    "Max Thread Pool Size": "#{MAX_THREADS:10}"
                }
            },
            {
                "id": "extract-tenant-processor",
                "type": "UpdateAttribute",
                "name": "Extract Tenant Info",
                "properties": {
                    "tenant.id": "${http.headers.X-Tenant-ID}",
                    "authorization": "${http.headers.Authorization}",
                    "request.timestamp": "${now()}"
                }
            },
            {
                "id": "validate-auth-processor",
                "type": "RouteOnAttribute",
                "name": "Validate Authentication",
                "properties": {
                    "Routing Strategy": "Route to Property name"
                },
                "dynamic_properties": {
                    "authenticated": "${authorization:startsWith('Bearer ')}"
                }
            },
            {
                "id": "validate-edi-realtime-processor",
                "type": "InvokeHTTP",
                "name": "Validate EDI Real-time",
                "properties": {
                    "HTTP Method": "POST",
                    "Remote URL": "#{EDI_LENS_API_URL}/api/v1/edi/validate-realtime",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer #{EDI_LENS_SERVICE_TOKEN}",
                    "Request Timeout": "#{REQUEST_TIMEOUT:30 seconds}",
                    "HTTP Message Body": "{\n  \"edi_content\": \"${file.content:escapeJson()}\",\n  \"tenant_id\": \"${tenant.id}\",\n  \"workflow_id\": \"#{WORKFLOW_ID}\",\n  \"validation_schema\": \"#{VALIDATION_SCHEMA}\",\n  \"snip_level\": #{SNIP_LEVEL:2},\n  \"generate_ta1\": #{GENERATE_TA1:true},\n  \"generate_999\": #{GENERATE_999:false}\n}"
                }
            },
            {
                "id": "format-success-response-processor",
                "type": "ReplaceText",
                "name": "Format Success Response",
                "properties": {
                    "Search Value": "(?s)(.*)",
                    "Replacement Value": "${http.response.body}",
                    "Replacement Strategy": "Always Replace"
                }
            },
            {
                "id": "format-error-response-processor",
                "type": "ReplaceText", 
                "name": "Format Error Response",
                "properties": {
                    "Search Value": "(?s)(.*)",
                    "Replacement Value": "{\n  \"error\": {\n    \"code\": \"AUTHENTICATION_FAILED\",\n    \"message\": \"Invalid or missing authentication token\",\n    \"timestamp\": \"${request.timestamp}\"\n  }\n}",
                    "Replacement Strategy": "Always Replace"
                }
            },
            {
                "id": "set-success-headers-processor",
                "type": "UpdateAttribute",
                "name": "Set Success Response Headers",
                "properties": {
                    "http.status.code": "${http.status.code}",
                    "http.status.message": "OK",
                    "Content-Type": "application/json"
                }
            },
            {
                "id": "set-error-headers-processor",
                "type": "UpdateAttribute",
                "name": "Set Error Response Headers", 
                "properties": {
                    "http.status.code": "401",
                    "http.status.message": "Unauthorized",
                    "Content-Type": "application/json"
                }
            },
            {
                "id": "log-request-processor",
                "type": "LogAttribute",
                "name": "Log API Request",
                "properties": {
                    "Log Level": "info",
                    "Log Prefix": "HTTP EDI Request",
                    "Attributes to Log": "tenant.id,http.request.uri,request.timestamp,http.status.code"
                }
            }
        ],
        "connections": [
            {
                "source_id": "listen-http-processor",
                "destination_id": "extract-tenant-processor",
                "relationships": ["success"]
            },
            {
                "source_id": "extract-tenant-processor",
                "destination_id": "validate-auth-processor",
                "relationships": ["success"]
            },
            {
                "source_id": "validate-auth-processor",
                "destination_id": "validate-edi-realtime-processor",
                "relationships": ["authenticated"]
            },
            {
                "source_id": "validate-edi-realtime-processor",
                "destination_id": "format-success-response-processor",
                "relationships": ["response"]
            },
            {
                "source_id": "format-success-response-processor",
                "destination_id": "set-success-headers-processor",
                "relationships": ["success"]
            },
            {
                "source_id": "set-success-headers-processor",
                "destination_id": "log-request-processor",
                "relationships": ["success"]
            },
            {
                "source_id": "validate-auth-processor",
                "destination_id": "format-error-response-processor",
                "relationships": ["unmatched"]
            },
            {
                "source_id": "format-error-response-processor",
                "destination_id": "set-error-headers-processor",
                "relationships": ["success"]
            },
            {
                "source_id": "set-error-headers-processor",
                "destination_id": "log-request-processor",
                "relationships": ["success"]
            }
        ]
    }
}
```

#### Configuration Schema
```json
{
    "configuration_schema": {
        "type": "object",
        "required": [
            "endpoint_config",
            "validation",
            "response_config"
        ],
        "properties": {
            "endpoint_config": {
                "type": "object",
                "title": "HTTP Endpoint Configuration",
                "required": ["listening_port", "base_path"],
                "properties": {
                    "listening_port": {
                        "type": "integer",
                        "title": "Listening Port",
                        "description": "Port for HTTP endpoint",
                        "minimum": 1024,
                        "maximum": 65535,
                        "examples": [8081]
                    },
                    "base_path": {
                        "type": "string",
                        "title": "Base Path",
                        "description": "HTTP base path for the endpoint",
                        "pattern": "^/api/workflows/[^/]+/process$",
                        "examples": ["/api/workflows/realtime-eligibility-001/process"]
                    },
                    "max_payload_size": {
                        "type": "string",
                        "title": "Max Payload Size",
                        "description": "Maximum request payload size",
                        "default": "10 MB",
                        "pattern": "^\\d+\\s+(KB|MB|GB)$"
                    },
                    "request_timeout": {
                        "type": "string",
                        "title": "Request Timeout",
                        "description": "Maximum processing time per request",
                        "default": "30 seconds",
                        "pattern": "^\\d+\\s+(seconds|minutes)$"
                    },
                    "max_concurrent_requests": {
                        "type": "integer",
                        "title": "Max Concurrent Requests",
                        "description": "Maximum concurrent requests to process",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    }
                }
            },
            "validation": {
                "type": "object",
                "title": "Validation Configuration",
                "required": ["schema"],
                "properties": {
                    "schema": {
                        "type": "string",
                        "title": "EDI Schema",
                        "description": "EDI schema file for validation",
                        "examples": ["270.5010.X279.A1.json"]
                    },
                    "snip_level": {
                        "type": "integer",
                        "title": "SNIP Level",
                        "description": "Validation strictness level for real-time processing",
                        "minimum": 1,
                        "maximum": 5,
                        "default": 2
                    }
                }
            },
            "acknowledgments": {
                "type": "object",
                "title": "Acknowledgment Configuration",
                "properties": {
                    "generate_ta1": {
                        "type": "boolean",
                        "title": "Generate TA1",
                        "description": "Include TA1 acknowledgment in response",
                        "default": true
                    },
                    "generate_999": {
                        "type": "boolean",
                        "title": "Generate 999",
                        "description": "Include 999 acknowledgment in response",
                        "default": false
                    }
                }
            },
            "response_config": {
                "type": "object",
                "title": "Response Configuration",
                "properties": {
                    "response_format": {
                        "type": "string",
                        "title": "Response Format",
                        "description": "Format for API responses",
                        "enum": ["JSON", "XML", "EDI"],
                        "default": "JSON"
                    },
                    "include_original_edi": {
                        "type": "boolean",
                        "title": "Include Original EDI",
                        "description": "Include original EDI content in response",
                        "default": false
                    },
                    "include_validation_details": {
                        "type": "boolean",
                        "title": "Include Validation Details",
                        "description": "Include detailed validation results",
                        "default": true
                    }
                }
            },
            "security": {
                "type": "object",
                "title": "Security Configuration",
                "properties": {
                    "require_authentication": {
                        "type": "boolean",
                        "title": "Require Authentication",
                        "description": "Require Bearer token authentication",
                        "default": true
                    },
                    "allowed_content_types": {
                        "type": "array",
                        "title": "Allowed Content Types",
                        "description": "Permitted request content types",
                        "items": {
                            "type": "string"
                        },
                        "default": ["application/json", "text/plain", "application/edi-x12"]
                    }
                }
            }
        }
    }
}
```

### 3. Format Converter Template

#### Template Specification
```json
{
    "template_id": "global-format-converter-v1.0",
    "name": "Format Converter",
    "description": "Converts between different data formats (JSON/CSV/XML ↔ EDI) with configurable mapping rules",
    "category": "TRANSFORMATION",
    "scope": "GLOBAL",
    "tenant_id": null,
    "maintainer": "edi-lens-platform",
    "based_on": null,
    "version": "1.0",
    "deployment_method": "registry",
    "tags": ["transformation", "conversion", "mapping", "json", "xml", "csv", "edi"],
    "features": [
        "format-conversion",
        "mapping-rules",
        "validation",
        "multiple-inputs",
        "multiple-outputs"
    ],
    "is_featured": true,
    "status": "ACTIVE"
}
```

#### Flow Definition Structure
```json
{
    "flow_definition": {
        "processors": [
            {
                "id": "input-listener-processor",
                "type": "#{INPUT_METHOD}",
                "name": "Format Converter Input",
                "properties": {
                    "Input Directory": "#{INPUT_PATH}",
                    "File Filter": "#{INPUT_FILE_PATTERN}",
                    "Listening Port": "#{HTTP_PORT:8082}",
                    "Base Path": "#{HTTP_BASE_PATH:/convert}"
                }
            },
            {
                "id": "detect-format-processor",
                "type": "UpdateAttribute",
                "name": "Detect Input Format",
                "properties": {
                    "detected.format": "${filename:getExtension():toLower()}",
                    "content.type": "${mime.type}"
                }
            },
            {
                "id": "route-input-format-processor",
                "type": "RouteOnAttribute",
                "name": "Route by Input Format",
                "properties": {
                    "Routing Strategy": "Route to Property name"
                },
                "dynamic_properties": {
                    "json_input": "${detected.format:equals('json')}",
                    "xml_input": "${detected.format:equals('xml')}",
                    "csv_input": "${detected.format:equals('csv')}",
                    "edi_input": "${detected.format:in('edi','x12','txt')}"
                }
            },
            {
                "id": "convert-to-edi-processor",
                "type": "InvokeHTTP",
                "name": "Convert to EDI",
                "properties": {
                    "HTTP Method": "POST",
                    "Remote URL": "#{EDI_LENS_API_URL}/api/v1/edi/transform",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer #{EDI_LENS_SERVICE_TOKEN}",
                    "HTTP Message Body": "{\n  \"input_content\": \"${file.content:escapeJson()}\",\n  \"input_format\": \"#{INPUT_FORMAT}\",\n  \"output_format\": \"#{OUTPUT_FORMAT}\",\n  \"mapping_rules\": #{MAPPING_RULES_JSON},\n  \"tenant_id\": \"#{TENANT_ID}\",\n  \"workflow_id\": \"#{WORKFLOW_ID}\"\n}"
                }
            },
            {
                "id": "convert-from-edi-processor",
                "type": "InvokeHTTP",
                "name": "Convert from EDI",
                "properties": {
                    "HTTP Method": "POST",
                    "Remote URL": "#{EDI_LENS_API_URL}/api/v1/edi/transform",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer #{EDI_LENS_SERVICE_TOKEN}",
                    "HTTP Message Body": "{\n  \"input_content\": \"${file.content:escapeJson()}\",\n  \"input_format\": \"EDI\",\n  \"output_format\": \"#{OUTPUT_FORMAT}\",\n  \"mapping_rules\": #{MAPPING_RULES_JSON},\n  \"tenant_id\": \"#{TENANT_ID}\",\n  \"workflow_id\": \"#{WORKFLOW_ID}\"\n}"
                }
            },
            {
                "id": "extract-converted-content-processor",
                "type": "EvaluateJsonPath",
                "name": "Extract Converted Content",
                "properties": {
                    "Destination": "flowfile-content",
                    "output_content": "$.output_content"
                }
            },
            {
                "id": "validate-output-processor",
                "type": "RouteOnAttribute",
                "name": "Validate Output",
                "properties": {
                    "Routing Strategy": "Route to Property name"
                },
                "dynamic_properties": {
                    "conversion_success": "${http.status.code:equals('200')}"
                }
            },
            {
                "id": "deliver-sftp-processor",
                "type": "PutSFTP",
                "name": "Deliver via SFTP",
                "properties": {
                    "Hostname": "#{DELIVERY_SFTP_HOSTNAME}",
                    "Username": "#{DELIVERY_SFTP_USERNAME}",
                    "Password": "#{DELIVERY_SFTP_PASSWORD}",
                    "Remote Path": "#{OUTPUT_PATH}",
                    "Remote Filename": "${filename:substringBeforeLast('.')}.#{OUTPUT_EXTENSION}",
                    "Create Directory": "true"
                }
            },
            {
                "id": "deliver-http-processor",
                "type": "InvokeHTTP",
                "name": "Deliver via HTTP",
                "properties": {
                    "HTTP Method": "POST",
                    "Remote URL": "#{DELIVERY_HTTP_ENDPOINT}",
                    "Content-Type": "#{DELIVERY_CONTENT_TYPE}",
                    "Authorization": "#{DELIVERY_AUTHORIZATION}"
                }
            },
            {
                "id": "log-conversion-processor",
                "type": "LogAttribute",
                "name": "Log Conversion Results",
                "properties": {
                    "Log Level": "info",
                    "Log Prefix": "Format Conversion",
                    "Attributes to Log": "filename,detected.format,conversion.success,output.size"
                }
            }
        ],
        "connections": [
            {
                "source_id": "input-listener-processor",
                "destination_id": "detect-format-processor",
                "relationships": ["success"]
            },
            {
                "source_id": "detect-format-processor",
                "destination_id": "route-input-format-processor",
                "relationships": ["success"]
            },
            {
                "source_id": "route-input-format-processor",
                "destination_id": "convert-to-edi-processor",
                "relationships": ["json_input", "xml_input", "csv_input"]
            },
            {
                "source_id": "route-input-format-processor",
                "destination_id": "convert-from-edi-processor",
                "relationships": ["edi_input"]
            },
            {
                "source_id": "convert-to-edi-processor",
                "destination_id": "extract-converted-content-processor",
                "relationships": ["response"]
            },
            {
                "source_id": "convert-from-edi-processor",
                "destination_id": "extract-converted-content-processor",
                "relationships": ["response"]
            },
            {
                "source_id": "extract-converted-content-processor",
                "destination_id": "validate-output-processor",
                "relationships": ["matched"]
            },
            {
                "source_id": "validate-output-processor",
                "destination_id": "deliver-sftp-processor",
                "relationships": ["conversion_success"]
            },
            {
                "source_id": "deliver-sftp-processor",
                "destination_id": "log-conversion-processor",
                "relationships": ["success"]
            }
        ]
    }
}
```

## 🛠️ Template Seeding Implementation

### Template Seeder Service
```python
# Required: src/services/template_seeder_service.py
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.workflow_template import WorkflowTemplate, TemplateVersion, TemplateUsage
from src.api.schemas import TemplateCreate, TemplateVersionCreate

class TemplateSeederService:
    """Service for seeding built-in workflow templates."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def seed_all_builtin_templates(self) -> Dict[str, Any]:
        """Seed all built-in templates."""
        
        results = {
            "seeded": [],
            "skipped": [],
            "errors": []
        }
        
        templates = [
            self._get_sftp_edi_processor_template(),
            self._get_http_edi_processor_template(),
            self._get_format_converter_template()
        ]
        
        for template_data in templates:
            try:
                result = await self._seed_template(template_data)
                if result["status"] == "seeded":
                    results["seeded"].append(result)
                else:
                    results["skipped"].append(result)
            except Exception as e:
                results["errors"].append({
                    "template_id": template_data["template_id"],
                    "error": str(e)
                })
        
        return results
    
    async def _seed_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Seed a single template."""
        
        # Check if template already exists
        existing_query = select(WorkflowTemplate).where(
            WorkflowTemplate.template_id == template_data["template_id"]
        )
        existing_result = await self.session.execute(existing_query)
        existing_template = existing_result.scalar_one_or_none()
        
        if existing_template:
            return {
                "template_id": template_data["template_id"],
                "status": "skipped",
                "reason": "Template already exists"
            }
        
        # Create template
        template = WorkflowTemplate(
            template_id=template_data["template_id"],
            name=template_data["name"],
            description=template_data["description"],
            category=template_data["category"],
            scope=template_data["scope"],
            tenant_id=template_data.get("tenant_id"),
            maintainer=template_data["maintainer"],
            based_on=template_data.get("based_on"),
            version=template_data["version"],
            flow_definition=template_data["flow_definition"],
            configuration_schema=template_data["configuration_schema"],
            deployment_method=template_data["deployment_method"],
            tags=template_data["tags"],
            features=template_data["features"],
            documentation=template_data.get("documentation"),
            examples=template_data.get("examples"),
            is_featured=template_data["is_featured"],
            status=template_data["status"]
        )
        
        self.session.add(template)
        
        # Create initial version
        initial_version = TemplateVersion(
            template_id=template_data["template_id"],
            version=template_data["version"],
            flow_definition=template_data["flow_definition"],
            configuration_schema=template_data["configuration_schema"],
            changes="Initial built-in template version",
            created_by="edi-lens-platform",
            is_current=True
        )
        
        self.session.add(initial_version)
        
        # Create usage record
        usage_record = TemplateUsage.create_usage_record(
            template_id=template_data["template_id"],
            tenant_id="platform",
            action="CREATE",
            success=True
        )
        
        self.session.add(usage_record)
        
        await self.session.commit()
        
        return {
            "template_id": template_data["template_id"],
            "status": "seeded",
            "name": template_data["name"]
        }
    
    def _get_sftp_edi_processor_template(self) -> Dict[str, Any]:
        """Get SFTP EDI Processor template definition."""
        # Return the complete template definition from above
        return {
            # ... complete template definition ...
        }
    
    def _get_http_edi_processor_template(self) -> Dict[str, Any]:
        """Get HTTP EDI Processor template definition."""
        # Return the complete template definition from above
        return {
            # ... complete template definition ...
        }
    
    def _get_format_converter_template(self) -> Dict[str, Any]:
        """Get Format Converter template definition."""
        # Return the complete template definition from above
        return {
            # ... complete template definition ...
        }
```

### Seeding Management Command
```python
# Required: src/cli/seed_templates.py
import asyncio
import click
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_session
from src.services.template_seeder_service import TemplateSeederService

@click.command()
@click.option('--force', is_flag=True, help='Force re-seeding of existing templates')
async def seed_builtin_templates(force: bool):
    """Seed built-in workflow templates."""
    
    async with get_async_session() as session:
        seeder = TemplateSeederService(session)
        
        if force:
            click.echo("Force seeding enabled - existing templates will be updated")
        
        click.echo("Seeding built-in workflow templates...")
        
        results = await seeder.seed_all_builtin_templates()
        
        # Report results
        click.echo(f"\n✅ Seeded {len(results['seeded'])} templates:")
        for template in results['seeded']:
            click.echo(f"  - {template['template_id']}: {template['name']}")
        
        if results['skipped']:
            click.echo(f"\n⏭️  Skipped {len(results['skipped'])} existing templates:")
            for template in results['skipped']:
                click.echo(f"  - {template['template_id']}: {template['reason']}")
        
        if results['errors']:
            click.echo(f"\n❌ Errors seeding {len(results['errors'])} templates:")
            for error in results['errors']:
                click.echo(f"  - {error['template_id']}: {error['error']}")
        
        click.echo(f"\n🎉 Template seeding completed!")

if __name__ == "__main__":
    asyncio.run(seed_builtin_templates())
```

### Seeding API Endpoint
```python
# Required: Add to src/api/endpoints/workflow_templates.py
@router.post("/seed-builtin", response_model=Dict[str, Any])
async def seed_builtin_templates(
    force: bool = Query(False, description="Force re-seeding of existing templates"),
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("admin"))
) -> Dict[str, Any]:
    """Seed built-in workflow templates (Admin only)."""
    
    seeder = TemplateSeederService(session)
    results = await seeder.seed_all_builtin_templates()
    
    return {
        "message": "Built-in template seeding completed",
        "results": results,
        "seeded_count": len(results["seeded"]),
        "skipped_count": len(results["skipped"]),
        "error_count": len(results["errors"])
    }
```

## 📊 Implementation Status

### Current Status: 0% Complete ❌

**Missing Components:**
- ❌ **Template Definitions**: None of the 3 built-in templates exist
- ❌ **Template Seeder Service**: No automated seeding mechanism
- ❌ **Flow Definitions**: No NiFi processor configurations defined
- ❌ **Configuration Schemas**: No JSON schema validation
- ❌ **Documentation**: No template usage documentation
- ❌ **Management Commands**: No CLI seeding commands
- ❌ **Seeding API**: No administrative seeding endpoint

### Required Implementation

#### Priority 1: Template Definitions (Week 1)
1. **Create Template JSON Files**: Complete template specifications
2. **Define Flow Structures**: NiFi processor and connection definitions
3. **Configuration Schemas**: JSON schemas for validation
4. **Documentation**: Usage guides and examples

#### Priority 2: Seeding Infrastructure (Week 2)
1. **Template Seeder Service**: Automated template creation
2. **Management Commands**: CLI tools for seeding
3. **Seeding API**: Administrative endpoints
4. **Database Integration**: Template storage and versioning

#### Priority 3: Validation & Testing (Week 3)
1. **Schema Validation**: Ensure templates are valid
2. **Template Tests**: Comprehensive template testing
3. **Seeding Tests**: Verify seeding functionality
4. **Documentation**: Complete usage documentation

## 🎯 Next Steps

1. **Create Template JSON Files**: Define complete template specifications
2. **Implement Seeder Service**: Build automated template creation
3. **Add Management Commands**: CLI tools for seeding
4. **Create Seeding Tests**: Verify template creation works
5. **Update Documentation**: Template usage and examples

These built-in templates are critical for user adoption - they provide immediate value and demonstrate best practices for workflow creation.