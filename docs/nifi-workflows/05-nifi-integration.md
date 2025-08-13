# NiFi Integration Guide

## Overview

This guide covers the integration between NiFi and the EDI Lens backend using a hybrid JSON/Registry approach for template management. Templates are stored as JSON in our database and deployed using either NiFi Registry (preferred) or XML conversion (fallback).

## Template Storage Strategy

### JSON Template Format

Templates are stored as JSON objects that define the complete NiFi flow structure. We have two main processing patterns:

#### 1. Batch Processing Pattern (SFTP Files)
- **File Detection**: NiFi monitors SFTP directories
- **Processing**: Each file creates separate batch job
- **API Call**: `/api/v1/edi/validate-batch` with webhook callback
- **Response**: Asynchronous via webhook when job completes

#### 2. Real-time Processing Pattern (HTTP Requests)  
- **Request Detection**: NiFi listens for HTTP requests
- **Processing**: Immediate processing of EDI content
- **API Call**: `/api/v1/edi/validate-realtime` for synchronous response
- **Response**: Immediate return to caller

### SFTP Batch Processing Template

```json
{
    "template_id": "sftp-edi-processor-v1.0",
    "name": "SFTP EDI Processor v1.0",
    "description": "Monitors SFTP directories for EDI files and processes them",
    "category": "BATCH",
    "deployment_method": "registry",
    "flow_definition": {
        "processors": [
            {
                "id": "list-sftp-processor",
                "name": "Monitor SFTP Directory",
                "type": "org.apache.nifi.processors.standard.ListSFTP",
                "position": {"x": 100, "y": 100},
                "properties": {
                    "Hostname": "sftpgo",
                    "Port": "2022",
                    "Username": "${SFTP_USERNAME}",
                    "Password": "${SFTP_PASSWORD}",
                    "Remote Path": "${INPUT_PATH}",
                    "Search Recursively": "false",
                    "File Filter Regex": "${FILE_PATTERN_REGEX}",
                    "Polling Interval": "10 sec"
                },
                "auto_terminated_relationships": [],
                "scheduling": {
                    "strategy": "TIMER_DRIVEN",
                    "period": "10 sec"
                }
            },
            {
                "id": "route-tenant-processor",
                "name": "Route by Tenant",
                "type": "org.apache.nifi.processors.standard.RouteOnAttribute",
                "position": {"x": 350, "y": 100},
                "properties": {
                    "Routing Strategy": "Route to Property name"
                },
                "dynamic_properties": {
                    "${TENANT_ID}": "${path:contains('/${TENANT_ID}/')}"
                },
                "auto_terminated_relationships": ["unmatched"]
            },
            {
                "id": "fetch-sftp-processor",
                "name": "Fetch EDI File",
                "type": "org.apache.nifi.processors.standard.FetchSFTP",
                "position": {"x": 600, "y": 100},
                "properties": {
                    "Hostname": "sftpgo",
                    "Port": "2022",
                    "Username": "${SFTP_USERNAME}",
                    "Password": "${SFTP_PASSWORD}",
                    "Remote File": "${path}/${filename}",
                    "Move Destination Directory": "${path}/.processing",
                    "Create Directory": "true"
                }
            },
            {
                "id": "validate-edi-processor",
                "name": "Validate EDI Content",
                "type": "org.apache.nifi.processors.standard.InvokeHTTP",
                "position": {"x": 850, "y": 100},
                "properties": {
                    "HTTP Method": "POST",
                    "Remote URL": "http://backend:8000/api/v1/edi/validate-batch",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer ${EDI_BACKEND_SERVICE_TOKEN}",
                    "Request Body": "{\"edi_content\": \"${flowfile:content}\", \"tenant_id\": \"${TENANT_ID}\", \"workflow_id\": \"${WORKFLOW_ID}\", \"validation_schema\": \"${VALIDATION_SCHEMA}\", \"snip_level\": ${SNIP_LEVEL}, \"file_name\": \"${filename}\", \"callback_url\": \"http://nifi:8080/webhook/batch-complete\", \"generate_ta1\": ${GENERATE_TA1}, \"generate_999\": ${GENERATE_999}}",
                    "Request Character Encoding": "UTF-8"
                },
                "auto_terminated_relationships": ["retry"]
            },
            {
                "id": "route-validation-processor",
                "name": "Route Validation Results",
                "type": "org.apache.nifi.processors.standard.RouteOnAttribute",
                "position": {"x": 1100, "y": 100},
                "properties": {
                    "Routing Strategy": "Route to Property name"
                },
                "dynamic_properties": {
                    "valid": "${valid:equals('true')}",
                    "invalid": "${valid:equals('false')}"
                },
                "auto_terminated_relationships": ["unmatched"]
            },
            {
                "id": "generate-ack-processor",
                "name": "Generate Acknowledgments",
                "type": "org.apache.nifi.processors.standard.InvokeHTTP",
                "position": {"x": 1350, "y": 50},
                "properties": {
                    "HTTP Method": "POST",
                    "Remote URL": "http://backend:8000/api/v1/edi/generate-acknowledgments",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer ${EDI_BACKEND_SERVICE_TOKEN}",
                    "Request Body": "{\"edi_content\": \"${original_edi_content}\", \"tenant_id\": \"${TENANT_ID}\", \"workflow_id\": \"${WORKFLOW_ID}\", \"generate_ta1\": ${GENERATE_TA1}, \"generate_999\": ${GENERATE_999}, \"validation_errors\": ${validation_results}, \"file_name\": \"${filename}\"}"
                }
            },
            {
                "id": "store-ack-processor",
                "name": "Store Acknowledgments",
                "type": "org.apache.nifi.processors.standard.PutSFTP",
                "position": {"x": 1600, "y": 50},
                "properties": {
                    "Hostname": "sftpgo",
                    "Port": "2022",
                    "Username": "${SFTP_USERNAME}",
                    "Password": "${SFTP_PASSWORD}",
                    "Remote Path": "${SUCCESS_OUTPUT_PATH}",
                    "Remote Filename": "${filename:substringBeforeLast('.')}_${acknowledgment_type}_${now():format('yyyyMMdd_HHmmss')}.edi",
                    "Create Directory": "true"
                }
            },
            {
                "id": "archive-processor",
                "name": "Archive Processed File",
                "type": "org.apache.nifi.processors.standard.PutSFTP",
                "position": {"x": 1850, "y": 50},
                "properties": {
                    "Hostname": "sftpgo",
                    "Port": "2022",
                    "Username": "${SFTP_USERNAME}",
                    "Password": "${SFTP_PASSWORD}",
                    "Remote Path": "${ARCHIVE_PATH}",
                    "Remote Filename": "${now():format('yyyyMMdd_HHmmss')}_${filename}",
                    "Create Directory": "true"
                }
            },
            {
                "id": "error-handler-processor",
                "name": "Handle Processing Errors",
                "type": "org.apache.nifi.processors.standard.PutSFTP",
                "position": {"x": 1350, "y": 200},
                "properties": {
                    "Hostname": "sftpgo",
                    "Port": "2022",
                    "Username": "${SFTP_USERNAME}",
                    "Password": "${SFTP_PASSWORD}",
                    "Remote Path": "${ERROR_PATH}",
                    "Remote Filename": "${now():format('yyyyMMdd_HHmmss')}_ERROR_${filename}",
                    "Create Directory": "true"
                }
            }
        ],
        "connections": [
            {
                "id": "list-to-route",
                "source_id": "list-sftp-processor",
                "destination_id": "route-tenant-processor",
                "source_relationships": ["success"]
            },
            {
                "id": "route-to-fetch",
                "source_id": "route-tenant-processor",
                "destination_id": "fetch-sftp-processor",
                "source_relationships": ["${TENANT_ID}"]
            },
            {
                "id": "fetch-to-validate",
                "source_id": "fetch-sftp-processor",
                "destination_id": "validate-edi-processor",
                "source_relationships": ["success"]
            },
            {
                "id": "validate-to-route",
                "source_id": "validate-edi-processor",
                "destination_id": "route-validation-processor",
                "source_relationships": ["success"]
            },
            {
                "id": "valid-to-ack",
                "source_id": "route-validation-processor",
                "destination_id": "generate-ack-processor",
                "source_relationships": ["valid"]
            },
            {
                "id": "ack-to-store",
                "source_id": "generate-ack-processor",
                "destination_id": "store-ack-processor",
                "source_relationships": ["success"]
            },
            {
                "id": "store-to-archive",
                "source_id": "store-ack-processor",
                "destination_id": "archive-processor",
                "source_relationships": ["success"]
            },
            {
                "id": "invalid-to-error",
                "source_id": "route-validation-processor",
                "destination_id": "error-handler-processor",
                "source_relationships": ["invalid"]
            },
            {
                "id": "fetch-error-to-handler",
                "source_id": "fetch-sftp-processor",
                "destination_id": "error-handler-processor",
                "source_relationships": ["failure"]
            },
            {
                "id": "validate-error-to-handler",
                "source_id": "validate-edi-processor",
                "destination_id": "error-handler-processor",
                "source_relationships": ["failure"]
            }
        ],
        "parameter_contexts": [
            {
                "name": "workflow-parameters",
                "description": "Parameters for workflow configuration",
                "parameters": {
                    "WORKFLOW_ID": {
                        "description": "Unique workflow identifier",
                        "sensitive": false
                    },
                    "TENANT_ID": {
                        "description": "Tenant identifier",
                        "sensitive": false
                    },
                    "INPUT_PATH": {
                        "description": "SFTP input directory path",
                        "sensitive": false
                    },
                    "FILE_PATTERN_REGEX": {
                        "description": "Regex pattern for file matching",
                        "sensitive": false
                    },
                    "VALIDATION_SCHEMA": {
                        "description": "EDI validation schema name",
                        "sensitive": false
                    },
                    "SNIP_LEVEL": {
                        "description": "SNIP validation level",
                        "sensitive": false
                    },
                    "GENERATE_TA1": {
                        "description": "Whether to generate TA1 acknowledgments",
                        "sensitive": false
                    },
                    "GENERATE_999": {
                        "description": "Whether to generate 999 acknowledgments", 
                        "sensitive": false
                    },
                    "SUCCESS_OUTPUT_PATH": {
                        "description": "SFTP output path for successful processing",
                        "sensitive": false
                    },
                    "ERROR_PATH": {
                        "description": "SFTP path for error files",
                        "sensitive": false
                    },
                    "ARCHIVE_PATH": {
                        "description": "SFTP path for archived files",
                        "sensitive": false
                    },
                    "SFTP_USERNAME": {
                        "description": "SFTP username for tenant",
                        "sensitive": false
                    },
                    "SFTP_PASSWORD": {
                        "description": "SFTP password for tenant",
                        "sensitive": true
                    },
                    "EDI_BACKEND_SERVICE_TOKEN": {
                        "description": "JWT token for backend API calls",
                        "sensitive": true
                    }
                }
            }
        ]
    },
    "configuration_schema": {
        "type": "object",
        "required": ["input_path", "file_patterns", "validation", "output"],
        "properties": {
            "input_path": {
                "type": "string",
                "description": "SFTP directory to monitor"
            },
            "file_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "File patterns to match"
            },
            "validation": {
                "type": "object",
                "properties": {
                    "schema": {"type": "string"},
                    "snip_level": {"type": "integer", "minimum": 1, "maximum": 5}
                }
            },
            "acknowledgments": {
                "type": "object",
                "properties": {
                    "generate_ta1": {"type": "boolean"},
                    "generate_999": {"type": "boolean"}
                }
            },
            "output": {
                "type": "object",
                "properties": {
                    "success_path": {"type": "string"},
                    "error_path": {"type": "string"},
                    "archive_path": {"type": "string"}
                }
            }
        }
    }
}
```

### HTTP Real-time Processing Template

```json
{
    "template_id": "http-edi-processor-v1.0",
    "name": "HTTP EDI Real-time Processor v1.0",
    "description": "Processes EDI transactions via HTTP endpoints in real-time",
    "category": "REALTIME",
    "deployment_method": "registry",
    "flow_definition": {
        "processors": [
            {
                "id": "listen-http-processor",
                "name": "Listen for HTTP Requests",
                "type": "org.apache.nifi.processors.standard.ListenHTTP",
                "position": {"x": 100, "y": 100},
                "properties": {
                    "Listening Port": "${HTTP_LISTENING_PORT}",
                    "Base Path": "${HTTP_BASE_PATH}",
                    "HTTP Context Map": "http-context-map",
                    "Allowed Paths": ".*",
                    "Additional HTTP Methods": "POST"
                }
            },
            {
                "id": "extract-edi-processor",
                "name": "Extract EDI Content",
                "type": "org.apache.nifi.processors.standard.ExtractText",
                "position": {"x": 350, "y": 100},
                "properties": {
                    "edi_content": "(?s)(.+)",
                    "Include Capture Group 0": "false"
                }
            },
            {
                "id": "validate-realtime-processor",
                "name": "Validate EDI Real-time",
                "type": "org.apache.nifi.processors.standard.InvokeHTTP",
                "position": {"x": 600, "y": 100},
                "properties": {
                    "HTTP Method": "POST",
                    "Remote URL": "http://backend:8000/api/v1/edi/validate-realtime",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer ${EDI_BACKEND_SERVICE_TOKEN}",
                    "Request Body": "{\"edi_content\": \"${edi_content}\", \"tenant_id\": \"${TENANT_ID}\", \"workflow_id\": \"${WORKFLOW_ID}\", \"validation_schema\": \"${VALIDATION_SCHEMA}\", \"snip_level\": ${SNIP_LEVEL}, \"generate_ta1\": ${GENERATE_TA1}, \"generate_999\": ${GENERATE_999}}",
                    "Request Character Encoding": "UTF-8"
                }
            },
            {
                "id": "format-response-processor",
                "name": "Format HTTP Response",
                "type": "org.apache.nifi.processors.standard.ReplaceText",
                "position": {"x": 850, "y": 100},
                "properties": {
                    "Search Value": "(?s)(.*)",
                    "Replacement Value": "${flowfile:content}",
                    "Replacement Strategy": "Regex Replace"
                }
            },
            {
                "id": "respond-http-processor",
                "name": "Send HTTP Response",
                "type": "org.apache.nifi.processors.standard.RespondHTTP",
                "position": {"x": 1100, "y": 100},
                "properties": {
                    "HTTP Context Map": "http-context-map",
                    "HTTP Status Code": "200",
                    "Content-Type": "application/json"
                }
            },
            {
                "id": "error-response-processor",
                "name": "Handle Error Response",
                "type": "org.apache.nifi.processors.standard.RespondHTTP",
                "position": {"x": 850, "y": 200},
                "properties": {
                    "HTTP Context Map": "http-context-map",
                    "HTTP Status Code": "500",
                    "Content-Type": "application/json",
                    "HTTP Response Body": "{\"error\": \"Processing failed\", \"timestamp\": \"${now():format('yyyy-MM-dd HH:mm:ss')}\"}"
                }
            }
        ],
        "connections": [
            {
                "id": "listen-to-extract",
                "source_id": "listen-http-processor",
                "destination_id": "extract-edi-processor",
                "source_relationships": ["success"]
            },
            {
                "id": "extract-to-validate",
                "source_id": "extract-edi-processor",
                "destination_id": "validate-realtime-processor",
                "source_relationships": ["matched"]
            },
            {
                "id": "validate-to-format",
                "source_id": "validate-realtime-processor",
                "destination_id": "format-response-processor",
                "source_relationships": ["success"]
            },
            {
                "id": "format-to-respond",
                "source_id": "format-response-processor",
                "destination_id": "respond-http-processor",
                "source_relationships": ["success"]
            },
            {
                "id": "validate-error-to-error-response",
                "source_id": "validate-realtime-processor",
                "destination_id": "error-response-processor",
                "source_relationships": ["failure"]
            },
            {
                "id": "extract-error-to-error-response",
                "source_id": "extract-edi-processor",
                "destination_id": "error-response-processor",
                "source_relationships": ["unmatched"]
            }
        ],
        "parameter_contexts": [
            {
                "name": "realtime-workflow-parameters",
                "description": "Parameters for real-time workflow configuration",
                "parameters": {
                    "WORKFLOW_ID": {
                        "description": "Unique workflow identifier",
                        "sensitive": false
                    },
                    "TENANT_ID": {
                        "description": "Tenant identifier",
                        "sensitive": false
                    },
                    "HTTP_LISTENING_PORT": {
                        "description": "Port for HTTP listener",
                        "sensitive": false
                    },
                    "HTTP_BASE_PATH": {
                        "description": "Base path for HTTP endpoint",
                        "sensitive": false
                    },
                    "VALIDATION_SCHEMA": {
                        "description": "EDI validation schema name",
                        "sensitive": false
                    },
                    "SNIP_LEVEL": {
                        "description": "SNIP validation level",
                        "sensitive": false
                    },
                    "GENERATE_TA1": {
                        "description": "Whether to generate TA1 acknowledgments",
                        "sensitive": false
                    },
                    "GENERATE_999": {
                        "description": "Whether to generate 999 acknowledgments",
                        "sensitive": false
                    },
                    "EDI_BACKEND_SERVICE_TOKEN": {
                        "description": "JWT token for backend API calls",
                        "sensitive": true
                    }
                }
            }
        ]
    },
    "configuration_schema": {
        "type": "object",
        "required": ["endpoint", "validation"],
        "properties": {
            "endpoint": {
                "type": "string",
                "description": "HTTP endpoint path for processing requests"
            },
            "listening_port": {
                "type": "integer",
                "description": "Port number for HTTP listener",
                "default": 8081
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Request timeout in seconds",
                "default": 30
            },
            "max_payload_size_mb": {
                "type": "integer",
                "description": "Maximum payload size in MB",
                "default": 10
            },
            "validation": {
                "type": "object",
                "properties": {
                    "schema": {"type": "string"},
                    "snip_level": {"type": "integer", "minimum": 1, "maximum": 5}
                }
            },
            "acknowledgments": {
                "type": "object",
                "properties": {
                    "generate_ta1": {"type": "boolean"},
                    "generate_999": {"type": "boolean"}
                }
            }
        }
    }
}
```

## Database Schema

```sql
CREATE TABLE workflow_templates (
    template_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    category VARCHAR NOT NULL,
    version VARCHAR DEFAULT '1.0',
    
    -- Template stored as JSON
    flow_definition JSONB NOT NULL,
    configuration_schema JSONB NOT NULL,
    
    -- NiFi deployment information
    deployment_method VARCHAR DEFAULT 'registry', -- 'registry' or 'xml'
    nifi_registry_flow_id VARCHAR,
    nifi_registry_bucket_id VARCHAR,
    nifi_xml_template_cache TEXT, -- Cached XML for fallback
    
    -- Metadata
    metadata JSONB,
    status VARCHAR DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_templates_category ON workflow_templates(category);
CREATE INDEX idx_templates_status ON workflow_templates(status);
CREATE INDEX idx_templates_deployment_method ON workflow_templates(deployment_method);
```

## Docker Compose Configuration

```yaml
services:
  nifi:
    image: apache/nifi:1.23.2
    container_name: nifi
    hostname: nifi
    environment:
      # Basic Configuration
      - NIFI_WEB_HTTP_HOST=0.0.0.0
      - NIFI_WEB_HTTP_PORT=8080
      - NIFI_CLUSTER_IS_NODE=false
      - NIFI_SENSITIVE_PROPS_KEY=${NIFI_SENSITIVE_PROPS_KEY}
      
      # Security Configuration
      - SINGLE_USER_CREDENTIALS_USERNAME=admin
      - SINGLE_USER_CREDENTIALS_PASSWORD=${NIFI_ADMIN_PASSWORD}
      
      # OIDC Configuration (Keycloak Integration)
      - NIFI_SECURITY_USER_OIDC_DISCOVERY_URL=${KEYCLOAK_URL}/realms/edi-lens/.well-known/openid_configuration
      - NIFI_SECURITY_USER_OIDC_CLIENT_ID=nifi
      - NIFI_SECURITY_USER_OIDC_CLIENT_SECRET=${NIFI_CLIENT_SECRET}
      - NIFI_SECURITY_USER_OIDC_PREFERRED_JWSALGORITHM=RS256
      
      # JVM Configuration
      - NIFI_JVM_HEAP_INIT=1g
      - NIFI_JVM_HEAP_MAX=2g
      
      # Backend Integration
      - EDI_BACKEND_URL=http://backend:8000
      
    ports:
      - "8080:8080"
    volumes:
      # Data persistence
      - nifi_database_repository:/opt/nifi/nifi-current/database_repository
      - nifi_flowfile_repository:/opt/nifi/nifi-current/flowfile_repository
      - nifi_content_repository:/opt/nifi/nifi-current/content_repository
      - nifi_provenance_repository:/opt/nifi/nifi-current/provenance_repository
      - nifi_conf:/opt/nifi/nifi-current/conf
      
      # SFTP access
      - sftp_tenant_data:/sftp/tenants:ro
      
    networks:
      - edi_lens_network
    depends_on:
      - keycloak
      - backend
      - nifi-registry
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/nifi-api/system-diagnostics"]
      interval: 30s
      timeout: 10s
      retries: 3

  nifi-registry:
    image: apache/nifi-registry:1.23.2
    container_name: nifi-registry
    environment:
      - NIFI_REGISTRY_WEB_HTTP_HOST=0.0.0.0
      - NIFI_REGISTRY_WEB_HTTP_PORT=18080
      - NIFI_REGISTRY_DB_URL=jdbc:postgresql://db-app:5432/${POSTGRES_DB}
      - NIFI_REGISTRY_DB_USER=${POSTGRES_USER}
      - NIFI_REGISTRY_DB_PASS=${POSTGRES_PASSWORD}
      - NIFI_REGISTRY_DB_CLASS=org.postgresql.Driver
    ports:
      - "18080:18080"
    volumes:
      - nifi_registry_data:/opt/nifi-registry/nifi-registry-current/database
      - nifi_registry_flow_storage:/opt/nifi-registry/nifi-registry-current/flow_storage
    networks:
      - edi_lens_network
    depends_on:
      - db-app

volumes:
  nifi_database_repository:
  nifi_flowfile_repository:
  nifi_content_repository:
  nifi_provenance_repository:
  nifi_conf:
  nifi_registry_data:
  nifi_registry_flow_storage:
```

## Template Management Implementation

### Hybrid Template Manager

```python
import aiohttp
import json
import uuid
from typing import Dict, List, Optional
from datetime import datetime

class HybridTemplateManager:
    def __init__(self, nifi_client, registry_client, db_session):
        self.nifi_client = nifi_client
        self.registry_client = registry_client
        self.db = db_session
        self.xml_converter = NiFiXMLConverter()
    
    async def deploy_workflow(self, workflow: Workflow, template: WorkflowTemplate) -> str:
        """Deploy a workflow using the preferred method for the template."""
        
        if template.deployment_method == "registry":
            try:
                return await self._deploy_via_registry(workflow, template)
            except Exception as e:
                logger.warning(f"Registry deployment failed, falling back to XML: {e}")
                return await self._deploy_via_xml(workflow, template)
        else:
            return await self._deploy_via_xml(workflow, template)
    
    async def _deploy_via_registry(self, workflow: Workflow, template: WorkflowTemplate) -> str:
        """Deploy workflow using NiFi Registry."""
        
        # Get or create bucket
        bucket_id = await self._ensure_bucket_exists(template.category)
        
        # Get or create versioned flow
        flow_id = template.nifi_registry_flow_id
        if not flow_id:
            flow_id = await self._create_versioned_flow(template, bucket_id)
            # Update template with flow ID
            await self._update_template_registry_info(template.template_id, flow_id, bucket_id)
        
        # Create process group from versioned flow
        process_group_id = await self._create_process_group_from_flow(
            workflow, 
            flow_id, 
            bucket_id
        )
        
        # Configure parameters
        await self._configure_workflow_parameters(workflow, process_group_id)
        
        # Start the workflow
        await self.nifi_client.start_process_group(process_group_id)
        
        return process_group_id
    
    async def _deploy_via_xml(self, workflow: Workflow, template: WorkflowTemplate) -> str:
        """Deploy workflow using XML template conversion."""
        
        # Convert JSON template to XML
        xml_template = self.xml_converter.json_to_xml(
            template.flow_definition,
            workflow.configuration,
            workflow
        )
        
        # Upload and instantiate template
        template_id = await self.nifi_client.upload_template(xml_template)
        process_group_id = await self.nifi_client.instantiate_template(
            template_id,
            f"workflow-{workflow.workflow_id}"
        )
        
        # Configure processors
        await self._configure_xml_processors(workflow, process_group_id)
        
        # Start the workflow
        await self.nifi_client.start_process_group(process_group_id)
        
        return process_group_id
    
    async def _ensure_bucket_exists(self, category: str) -> str:
        """Ensure a bucket exists for the template category."""
        
        bucket_name = f"edi-lens-{category.lower()}-templates"
        
        # Try to get existing bucket
        buckets = await self.registry_client.get_buckets()
        for bucket in buckets:
            if bucket["name"] == bucket_name:
                return bucket["identifier"]
        
        # Create new bucket
        bucket = await self.registry_client.create_bucket({
            "name": bucket_name,
            "description": f"EDI Lens {category} workflow templates"
        })
        
        return bucket["identifier"]
    
    async def _create_versioned_flow(self, template: WorkflowTemplate, bucket_id: str) -> str:
        """Create a versioned flow in NiFi Registry."""
        
        # Create flow metadata
        flow = await self.registry_client.create_flow({
            "name": template.name,
            "description": template.description,
            "bucketIdentifier": bucket_id
        })
        
        # Create initial version
        flow_version = await self.registry_client.create_flow_version(
            bucket_id,
            flow["identifier"],
            self._build_registry_flow_definition(template.flow_definition)
        )
        
        return flow["identifier"]
    
    def _build_registry_flow_definition(self, flow_definition: dict) -> dict:
        """Convert our JSON flow definition to NiFi Registry format."""
        
        return {
            "flowContents": {
                "identifier": str(uuid.uuid4()),
                "name": "Flow Contents",
                "processors": [
                    self._convert_processor_for_registry(proc)
                    for proc in flow_definition["processors"]
                ],
                "connections": [
                    self._convert_connection_for_registry(conn)
                    for conn in flow_definition["connections"]
                ],
                "parameterContexts": [
                    self._convert_parameter_context_for_registry(ctx)
                    for ctx in flow_definition.get("parameter_contexts", [])
                ]
            }
        }
    
    def _convert_processor_for_registry(self, processor: dict) -> dict:
        """Convert processor definition to NiFi Registry format."""
        
        return {
            "identifier": processor["id"],
            "name": processor["name"],
            "type": processor["type"],
            "position": {
                "x": processor["position"]["x"],
                "y": processor["position"]["y"]
            },
            "properties": processor["properties"],
            "propertyDescriptors": {},
            "autoTerminatedRelationships": processor.get("auto_terminated_relationships", []),
            "schedulingStrategy": processor.get("scheduling", {}).get("strategy", "TIMER_DRIVEN"),
            "schedulingPeriod": processor.get("scheduling", {}).get("period", "0 sec"),
            "executionNode": "ALL",
            "penaltyDuration": "30 sec",
            "yieldDuration": "1 sec",
            "runDurationMillis": 0,
            "concurrentlySchedulableTaskCount": 1
        }
    
    def _convert_connection_for_registry(self, connection: dict) -> dict:
        """Convert connection definition to NiFi Registry format."""
        
        return {
            "identifier": connection["id"],
            "name": "",
            "source": {
                "id": connection["source_id"],
                "type": "PROCESSOR"
            },
            "destination": {
                "id": connection["destination_id"],
                "type": "PROCESSOR"
            },
            "selectedRelationships": connection["source_relationships"],
            "backPressureObjectThreshold": 10000,
            "backPressureDataSizeThreshold": "1 GB",
            "flowFileExpiration": "0 sec",
            "prioritizers": []
        }
    
    async def _configure_workflow_parameters(self, workflow: Workflow, process_group_id: str):
        """Configure parameter context for the workflow."""
        
        # Build parameter values from workflow configuration
        parameters = self._build_workflow_parameters(workflow)
        
        # Get parameter context
        parameter_contexts = await self.nifi_client.get_parameter_contexts(process_group_id)
        
        if parameter_contexts:
            # Update existing parameter context
            context_id = parameter_contexts[0]["id"]
            await self.nifi_client.update_parameter_context(context_id, parameters)
        else:
            # Create new parameter context
            context = await self.nifi_client.create_parameter_context({
                "name": f"workflow-{workflow.workflow_id}-parameters",
                "description": f"Parameters for workflow {workflow.name}",
                "parameters": parameters
            })
            
            # Link to process group
            await self.nifi_client.set_process_group_parameter_context(
                process_group_id,
                context["id"]
            )
    
    def _build_workflow_parameters(self, workflow: Workflow) -> Dict[str, Dict]:
        """Build parameter values from workflow configuration."""
        
        config = workflow.configuration
        
        parameters = {
            "WORKFLOW_ID": {
                "value": workflow.workflow_id,
                "sensitive": False
            },
            "TENANT_ID": {
                "value": workflow.tenant_id,
                "sensitive": False
            },
            "INPUT_PATH": {
                "value": config.get("input_path", ""),
                "sensitive": False
            },
            "FILE_PATTERN_REGEX": {
                "value": self._build_file_pattern_regex(config.get("file_patterns", [])),
                "sensitive": False
            },
            "VALIDATION_SCHEMA": {
                "value": config.get("validation", {}).get("schema", ""),
                "sensitive": False
            },
            "SNIP_LEVEL": {
                "value": str(config.get("validation", {}).get("snip_level", 3)),
                "sensitive": False
            },
            "GENERATE_TA1": {
                "value": str(config.get("acknowledgments", {}).get("generate_ta1", False)).lower(),
                "sensitive": False
            },
            "GENERATE_999": {
                "value": str(config.get("acknowledgments", {}).get("generate_999", False)).lower(),
                "sensitive": False
            },
            "SUCCESS_OUTPUT_PATH": {
                "value": config.get("output", {}).get("success_path", ""),
                "sensitive": False
            },
            "ERROR_PATH": {
                "value": config.get("output", {}).get("error_path", ""),
                "sensitive": False
            },
            "ARCHIVE_PATH": {
                "value": config.get("output", {}).get("archive_path", ""),
                "sensitive": False
            }
        }
        
        # Add sensitive parameters
        parameters.update(await self._get_sensitive_parameters(workflow.tenant_id))
        
        return parameters
    
    async def _get_sensitive_parameters(self, tenant_id: str) -> Dict[str, Dict]:
        """Get sensitive parameters for the tenant."""
        
        # Get SFTP credentials
        sftp_creds = await self.get_tenant_sftp_credentials(tenant_id)
        
        # Get service token
        service_token = await self.get_service_token()
        
        return {
            "SFTP_USERNAME": {
                "value": sftp_creds["username"],
                "sensitive": False
            },
            "SFTP_PASSWORD": {
                "value": sftp_creds["password"],
                "sensitive": True
            },
            "EDI_BACKEND_SERVICE_TOKEN": {
                "value": service_token,
                "sensitive": True
            }
        }
```

### NiFi Registry Client

```python
class NiFiRegistryClient:
    def __init__(self, base_url: str, service_token: str):
        self.base_url = base_url
        self.service_token = service_token
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                'Authorization': f'Bearer {self.service_token}',
                'Content-Type': 'application/json'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_buckets(self) -> List[Dict]:
        """Get all buckets from NiFi Registry."""
        
        async with self.session.get(f'{self.base_url}/nifi-registry-api/buckets') as response:
            if response.status != 200:
                raise Exception(f"Failed to get buckets: {response.status}")
            return await response.json()
    
    async def create_bucket(self, bucket_data: Dict) -> Dict:
        """Create a new bucket in NiFi Registry."""
        
        async with self.session.post(
            f'{self.base_url}/nifi-registry-api/buckets',
            json=bucket_data
        ) as response:
            if response.status != 200:
                raise Exception(f"Failed to create bucket: {response.status}")
            return await response.json()
    
    async def create_flow(self, flow_data: Dict) -> Dict:
        """Create a new versioned flow."""
        
        async with self.session.post(
            f'{self.base_url}/nifi-registry-api/buckets/{flow_data["bucketIdentifier"]}/flows',
            json=flow_data
        ) as response:
            if response.status != 200:
                raise Exception(f"Failed to create flow: {response.status}")
            return await response.json()
    
    async def create_flow_version(self, bucket_id: str, flow_id: str, flow_definition: Dict) -> Dict:
        """Create a new version of a flow."""
        
        version_data = {
            "flow": {
                "bucketIdentifier": bucket_id,
                "identifier": flow_id
            },
            "flowSnapshot": flow_definition
        }
        
        async with self.session.post(
            f'{self.base_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions',
            json=version_data
        ) as response:
            if response.status != 200:
                raise Exception(f"Failed to create flow version: {response.status}")
            return await response.json()
```

### XML Converter (Fallback)

```python
class NiFiXMLConverter:
    def json_to_xml(self, flow_definition: dict, configuration: dict, workflow) -> str:
        """Convert JSON flow definition to NiFi XML template."""
        
        # Replace parameters in flow definition
        configured_flow = self._apply_configuration(flow_definition, configuration, workflow)
        
        # Generate XML
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<template encoding-version="1.4">',
            f'  <description>{workflow.description}</description>',
            f'  <groupId>edi-lens-workflows</groupId>',
            f'  <name>{workflow.name}</name>',
            '  <snippet>',
            '    <processGroups>',
            f'      <id>{uuid.uuid4()}</id>',
            '      <processors>'
        ]
        
        # Convert processors
        for processor in configured_flow["processors"]:
            xml_parts.extend(self._processor_to_xml(processor))
        
        xml_parts.extend([
            '      </processors>',
            '      <connections>'
        ])
        
        # Convert connections
        for connection in configured_flow["connections"]:
            xml_parts.extend(self._connection_to_xml(connection))
        
        xml_parts.extend([
            '      </connections>',
            '    </processGroups>',
            '  </snippet>',
            '</template>'
        ])
        
        return '\n'.join(xml_parts)
    
    def _processor_to_xml(self, processor: dict) -> List[str]:
        """Convert processor definition to XML."""
        
        xml_parts = [
            '        <processor>',
            f'          <id>{processor["id"]}</id>',
            f'          <name>{processor["name"]}</name>',
            f'          <type>{processor["type"]}</type>',
            '          <properties>'
        ]
        
        # Add properties
        for key, value in processor["properties"].items():
            xml_parts.extend([
                '            <property>',
                f'              <name>{key}</name>',
                f'              <value>{value}</value>',
                '            </property>'
            ])
        
        xml_parts.extend([
            '          </properties>',
            '        </processor>'
        ])
        
        return xml_parts
    
    def _connection_to_xml(self, connection: dict) -> List[str]:
        """Convert connection definition to XML."""
        
        xml_parts = [
            '        <connection>',
            f'          <id>{connection["id"]}</id>',
            f'          <sourceId>{connection["source_id"]}</sourceId>',
            f'          <destinationId>{connection["destination_id"]}</destinationId>',
            '          <selectedRelationships>'
        ]
        
        for relationship in connection["source_relationships"]:
            xml_parts.append(f'            <selectedRelationship>{relationship}</selectedRelationship>')
        
        xml_parts.extend([
            '          </selectedRelationships>',
            '        </connection>'
        ])
        
        return xml_parts
```

This hybrid approach provides the best of both worlds: modern NiFi Registry integration with JSON templates while maintaining XML fallback compatibility.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "1", "content": "Create new docs folder for NiFi workflow architecture", "status": "completed"}, {"id": "2", "content": "Document template-driven workflow system", "status": "completed"}, {"id": "3", "content": "Create implementation roadmap documentation", "status": "completed"}, {"id": "4", "content": "Document API specifications for workflows", "status": "completed"}, {"id": "5", "content": "Create NiFi integration guide with JSON templates", "status": "completed"}, {"id": "6", "content": "Update existing docs to reference new architecture", "status": "in_progress"}]