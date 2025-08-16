"""
Built-in Templates Service for EDI Lens.

This service manages the built-in workflow templates that provide
out-of-box functionality for common EDI processing patterns.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.workflow_template import WorkflowTemplate
from src.nifi.clients.registry_client import NiFiRegistryClient

logger = logging.getLogger(__name__)


class BuiltInTemplatesService:
    """Service for managing built-in workflow templates."""

    def __init__(self, registry_url: str, registry_auth_token: Optional[str] = None):
        self.registry_url = registry_url
        self.registry_auth_token = registry_auth_token

    # --- Built-in Template Definitions ---

    def _get_sftp_edi_processor_template(self) -> Dict[str, Any]:
        """Get SFTP EDI Processor template definition."""
        return {
            "template_id": "global-sftp-edi-processor-v1.0",
            "name": "SFTP EDI File Processor",
            "description": "Monitors SFTP directories for EDI files and processes them with validation and acknowledgment generation",
            "category": "BATCH",
            "scope": "GLOBAL",
            "tenant_id": None,
            "maintainer": "edi-lens-platform",
            "based_on": None,
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
            "is_featured": True,
            "status": "ACTIVE",
            "flow_definition": {
                "processors": [
                    {
                        "id": "list-sftp-processor",
                        "type": "ListSFTP",
                        "name": "Monitor SFTP Directory",
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
                        "type": "RouteOnAttribute",
                        "name": "Route by Tenant",
                        "position": {"x": 350, "y": 100},
                        "properties": {
                            "Routing Strategy": "Route to Property name"
                        },
                        "dynamic_properties": {
                            "${TENANT_ID}": "${path:contains('/${TENANT_ID}/'}"
                        },
                        "auto_terminated_relationships": ["unmatched"]
                    },
                    {
                        "id": "fetch-sftp-processor",
                        "type": "FetchSFTP",
                        "name": "Fetch EDI File",
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
                        "type": "InvokeHTTP",
                        "name": "Validate EDI Content",
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
                        "id": "handle-validation-response",
                        "type": "RouteOnAttribute",
                        "name": "Handle Validation Response",
                        "position": {"x": 1100, "y": 100},
                        "properties": {
                            "Routing Strategy": "Route to Property name",
                            "success": "${invokehttp.status.code:equals(200)}"
                        },
                        "auto_terminated_relationships": ["unmatched"]
                    },
                    {
                        "id": "move-to-archive",
                        "type": "PutSFTP",
                        "name": "Archive Processed File",
                        "position": {"x": 1350, "y": 50},
                        "properties": {
                            "Hostname": "sftpgo",
                            "Port": "2022",
                            "Username": "${SFTP_USERNAME}",
                            "Password": "${SFTP_PASSWORD}",
                            "Remote Path": "${path}/.archive/${now():format('yyyy/MM/dd')}",
                            "Create Directory": "true"
                        }
                    },
                    {
                        "id": "move-to-errors",
                        "type": "PutSFTP",
                        "name": "Move Failed File to Errors",
                        "position": {"x": 1350, "y": 150},
                        "properties": {
                            "Hostname": "sftpgo",
                            "Port": "2022",
                            "Username": "${SFTP_USERNAME}",
                            "Password": "${SFTP_PASSWORD}",
                            "Remote Path": "${path}/.errors/${now():format('yyyy/MM/dd')}",
                            "Create Directory": "true"
                        }
                    }
                ],
                "connections": [
                    {
                        "source": "list-sftp-processor",
                        "destination": "route-tenant-processor",
                        "relationship": "success"
                    },
                    {
                        "source": "route-tenant-processor",
                        "destination": "fetch-sftp-processor",
                        "relationship": "${TENANT_ID}"
                    },
                    {
                        "source": "fetch-sftp-processor",
                        "destination": "validate-edi-processor",
                        "relationship": "success"
                    },
                    {
                        "source": "validate-edi-processor",
                        "destination": "handle-validation-response",
                        "relationship": "Response"
                    },
                    {
                        "source": "handle-validation-response",
                        "destination": "move-to-archive",
                        "relationship": "success"
                    },
                    {
                        "source": "handle-validation-response",
                        "destination": "move-to-errors",
                        "relationship": "unmatched"
                    }
                ],
                "controller_services": [],
                "parameter_contexts": [
                    {
                        "name": "sftp-edi-processor-parameters",
                        "description": "Parameters for SFTP EDI processing workflow",
                        "parameters": [
                            {
                                "name": "SFTP_USERNAME",
                                "description": "SFTP username for file access",
                                "sensitive": True
                            },
                            {
                                "name": "SFTP_PASSWORD",
                                "description": "SFTP password for file access",
                                "sensitive": True
                            },
                            {
                                "name": "INPUT_PATH",
                                "description": "SFTP directory to monitor for incoming EDI files",
                                "sensitive": False
                            },
                            {
                                "name": "FILE_PATTERN_REGEX",
                                "description": "Regex pattern for matching EDI files",
                                "sensitive": False,
                                "value": ".*\\.edi$"
                            },
                            {
                                "name": "VALIDATION_SCHEMA",
                                "description": "EDI schema for validation",
                                "sensitive": False
                            },
                            {
                                "name": "SNIP_LEVEL",
                                "description": "Validation strictness level (1-5)",
                                "sensitive": False,
                                "value": "3"
                            },
                            {
                                "name": "GENERATE_TA1",
                                "description": "Generate TA1 acknowledgments",
                                "sensitive": False,
                                "value": "true"
                            },
                            {
                                "name": "GENERATE_999",
                                "description": "Generate 999 acknowledgments",
                                "sensitive": False,
                                "value": "false"
                            },
                            {
                                "name": "EDI_BACKEND_SERVICE_TOKEN",
                                "description": "Service token for backend API access",
                                "sensitive": True
                            }
                        ]
                    }
                ]
            },
            "configuration_schema": {
                "type": "object",
                "required": [
                    "input_path",
                    "file_patterns",
                    "validation"
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
                                "default": True
                            },
                            "generate_999": {
                                "type": "boolean", 
                                "title": "Generate 999",
                                "description": "Generate 999 functional acknowledgments",
                                "default": False
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

    def _get_http_edi_processor_template(self) -> Dict[str, Any]:
        """Get HTTP EDI Processor template definition."""
        return {
            "template_id": "global-http-edi-processor-v1.0",
            "name": "HTTP EDI Processor",
            "description": "Processes EDI transactions via HTTP endpoints in real-time with immediate response",
            "category": "REALTIME",
            "scope": "GLOBAL",
            "tenant_id": None,
            "maintainer": "edi-lens-platform",
            "based_on": None,
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
            "is_featured": True,
            "status": "ACTIVE",
            "flow_definition": {
                "processors": [
                    {
                        "id": "listen-http-processor",
                        "type": "ListenHTTP",
                        "name": "HTTP EDI Endpoint",
                        "position": {"x": 100, "y": 100},
                        "properties": {
                            "Listening Port": "${HTTP_LISTENING_PORT}",
                            "Base Path": "${HTTP_BASE_PATH}",
                            "HTTP Context Map": "edi-http-context",
                            "HTTP Headers to Receive as Attributes": "Authorization,X-Tenant-ID,Content-Type",
                            "Max Data Size": "${MAX_PAYLOAD_SIZE:10 MB}",
                            "Max Thread Pool Size": "${MAX_THREADS:10}"
                        }
                    },
                    {
                        "id": "extract-tenant-processor",
                        "type": "UpdateAttribute",
                        "name": "Extract Tenant Info",
                        "position": {"x": 350, "y": 100},
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
                        "position": {"x": 600, "y": 100},
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
                        "position": {"x": 850, "y": 100},
                        "properties": {
                            "HTTP Method": "POST",
                            "Remote URL": "http://backend:8000/api/v1/edi/validate-realtime",
                            "Content-Type": "application/json",
                            "Authorization": "Bearer ${EDI_BACKEND_SERVICE_TOKEN}",
                            "Request Timeout": "${REQUEST_TIMEOUT:30 seconds}",
                            "HTTP Message Body": "{\"edi_content\": \"${file.content:escapeJson()}\", \"tenant_id\": \"${tenant.id}\", \"workflow_id\": \"${WORKFLOW_ID}\", \"validation_schema\": \"${VALIDATION_SCHEMA}\", \"snip_level\": ${SNIP_LEVEL:2}, \"generate_ta1\": ${GENERATE_TA1:true}, \"generate_999\": ${GENERATE_999:false}}"
                        }
                    },
                    {
                        "id": "format-success-response-processor",
                        "type": "ReplaceText",
                        "name": "Format Success Response",
                        "position": {"x": 1100, "y": 50},
                        "properties": {
                            "Search Value": "(.*)",
                            "Replacement Value": "${http.response.body}",
                            "Replacement Strategy": "Always Replace"
                        }
                    },
                    {
                        "id": "format-error-response-processor", 
                        "type": "ReplaceText",
                        "name": "Format Error Response",
                        "position": {"x": 1100, "y": 150},
                        "properties": {
                            "Search Value": "(.*)",
                            "Replacement Value": "{\\n  \\\"error\\\": {\\n    \\\"code\\\": \\\"AUTHENTICATION_FAILED\\\",\\n    \\\"message\\\": \\\"Invalid or missing authentication token\\\",\\n    \\\"timestamp\\\": \\\"${request.timestamp}\\\"\\n  }\\n}",
                            "Replacement Strategy": "Always Replace"
                        }
                    },
                    {
                        "id": "set-success-headers-processor",
                        "type": "UpdateAttribute",
                        "name": "Set Success Response Headers",
                        "position": {"x": 1350, "y": 50},
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
                        "position": {"x": 1350, "y": 150},
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
                        "position": {"x": 1600, "y": 100},
                        "properties": {
                            "Log Level": "info",
                            "Log Prefix": "HTTP EDI Request",
                            "Attributes to Log": "tenant.id,http.request.uri,request.timestamp,http.status.code"
                        }
                    }
                ],
                "connections": [
                    {
                        "source": "listen-http-processor",
                        "destination": "extract-tenant-processor",
                        "relationship": "success"
                    },
                    {
                        "source": "extract-tenant-processor",
                        "destination": "validate-auth-processor",
                        "relationship": "success"
                    },
                    {
                        "source": "validate-auth-processor",
                        "destination": "validate-edi-realtime-processor",
                        "relationship": "authenticated"
                    },
                    {
                        "source": "validate-edi-realtime-processor",
                        "destination": "format-success-response-processor",
                        "relationship": "response"
                    },
                    {
                        "source": "format-success-response-processor",
                        "destination": "set-success-headers-processor",
                        "relationship": "success"
                    },
                    {
                        "source": "set-success-headers-processor",
                        "destination": "log-request-processor",
                        "relationship": "success"
                    },
                    {
                        "source": "validate-auth-processor",
                        "destination": "format-error-response-processor",
                        "relationship": "unmatched"
                    },
                    {
                        "source": "format-error-response-processor",
                        "destination": "set-error-headers-processor",
                        "relationship": "success"
                    },
                    {
                        "source": "set-error-headers-processor",
                        "destination": "log-request-processor",
                        "relationship": "success"
                    }
                ],
                "controller_services": [],
                "parameter_contexts": [
                    {
                        "name": "http-edi-processor-parameters",
                        "description": "Parameters for HTTP EDI processing workflow",
                        "parameters": [
                            {
                                "name": "HTTP_LISTENING_PORT",
                                "description": "Port for HTTP endpoint",
                                "sensitive": False,
                                "value": "8081"
                            },
                            {
                                "name": "HTTP_BASE_PATH",
                                "description": "HTTP base path for the endpoint",
                                "sensitive": False,
                                "value": "/api/workflows/realtime-edi-process"
                            },
                            {
                                "name": "MAX_PAYLOAD_SIZE",
                                "description": "Maximum request payload size",
                                "sensitive": False,
                                "value": "10 MB"
                            },
                            {
                                "name": "MAX_THREADS",
                                "description": "Maximum concurrent requests to process",
                                "sensitive": False,
                                "value": "10"
                            },
                            {
                                "name": "REQUEST_TIMEOUT",
                                "description": "Maximum processing time per request",
                                "sensitive": False,
                                "value": "30 seconds"
                            },
                            {
                                "name": "VALIDATION_SCHEMA",
                                "description": "EDI schema for validation",
                                "sensitive": False
                            },
                            {
                                "name": "SNIP_LEVEL",
                                "description": "Validation strictness level for real-time processing",
                                "sensitive": False,
                                "value": "2"
                            },
                            {
                                "name": "GENERATE_TA1",
                                "description": "Include TA1 acknowledgment in response",
                                "sensitive": False,
                                "value": "true"
                            },
                            {
                                "name": "GENERATE_999",
                                "description": "Include 999 acknowledgment in response",
                                "sensitive": False,
                                "value": "false"
                            },
                            {
                                "name": "EDI_BACKEND_SERVICE_TOKEN",
                                "description": "Service token for backend API access",
                                "sensitive": True
                            }
                        ]
                    }
                ]
            },
            "configuration_schema": {
                "type": "object",
                "required": [
                    "endpoint_config",
                    "validation"
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
                                "examples": ["/api/workflows/realtime-claims-001/process"]
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
                                "default": True
                            },
                            "generate_999": {
                                "type": "boolean",
                                "title": "Generate 999",
                                "description": "Include 999 acknowledgment in response",
                                "default": False
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
                                "default": False
                            },
                            "include_validation_details": {
                                "type": "boolean",
                                "title": "Include Validation Details",
                                "description": "Include detailed validation results",
                                "default": True
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
                                "default": True
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

    def _get_format_converter_template(self) -> Dict[str, Any]:
        """Get Format Converter template definition."""
        return {
            "template_id": "global-format-converter-v1.0",
            "name": "Format Converter",
            "description": "Converts between different data formats (JSON/CSV/XML ↔ EDI) with configurable mapping rules",
            "category": "TRANSFORMATION",
            "scope": "GLOBAL",
            "tenant_id": None,
            "maintainer": "edi-lens-platform",
            "based_on": None,
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
            "is_featured": True,
            "status": "ACTIVE",
            "flow_definition": {
                "processors": [
                    {
                        "id": "input-listener-processor",
                        "type": "${INPUT_METHOD}",  # Dynamically configured
                        "name": "Format Converter Input",
                        "position": {"x": 100, "y": 100},
                        "properties": {
                            "Input Directory": "${INPUT_PATH}",
                            "File Filter": "${INPUT_FILE_PATTERN}",
                            "Listening Port": "${HTTP_PORT:8082}",
                            "Base Path": "${HTTP_BASE_PATH:/convert}"
                        }
                    },
                    {
                        "id": "detect-format-processor",
                        "type": "UpdateAttribute",
                        "name": "Detect Input Format",
                        "position": {"x": 350, "y": 100},
                        "properties": {
                            "detected.format": "${filename:getExtension():toLower()}",
                            "content.type": "${mime.type}"
                        }
                    },
                    {
                        "id": "route-input-format-processor",
                        "type": "RouteOnAttribute",
                        "name": "Route by Input Format",
                        "position": {"x": 600, "y": 100},
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
                        "position": {"x": 850, "y": 100},
                        "properties": {
                            "HTTP Method": "POST",
                            "Remote URL": "http://backend:8000/api/v1/edi/transform",
                            "Content-Type": "application/json",
                            "Authorization": "Bearer ${EDI_BACKEND_SERVICE_TOKEN}",
                            "HTTP Message Body": "{\\n  \\\"input_content\\\": \\\"${file.content:escapeJson()}\\\",\\n  \\\"input_format\\\": \\\"#{INPUT_FORMAT}\\\",\\n  \\\"output_format\\\": \\\"#{OUTPUT_FORMAT}\\\",\\n  \\\"mapping_rules\\\": #{MAPPING_RULES_JSON},\\n  \\\"tenant_id\\\": \\\"#{TENANT_ID}\\\",\\n  \\\"workflow_id\\\": \\\"#{WORKFLOW_ID}\\\"\\n}"
                        }
                    },
                    {
                        "id": "convert-from-edi-processor",
                        "type": "InvokeHTTP",
                        "name": "Convert from EDI",
                        "position": {"x": 850, "y": 200},
                        "properties": {
                            "HTTP Method": "POST",
                            "Remote URL": "http://backend:8000/api/v1/edi/transform",
                            "Content-Type": "application/json",
                            "Authorization": "Bearer ${EDI_BACKEND_SERVICE_TOKEN}",
                            "HTTP Message Body": "{\\n  \\\"input_content\\\": \\\"${file.content:escapeJson()}\\\",\\n  \\\"input_format\\\": \\\"EDI\\\",\\n  \\\"output_format\\\": \\\"#{OUTPUT_FORMAT}\\\",\\n  \\\"mapping_rules\\\": #{MAPPING_RULES_JSON},\\n  \\\"tenant_id\\\": \\\"#{TENANT_ID}\\\",\\n  \\\"workflow_id\\\": \\\"#{WORKFLOW_ID}\\\"\\n}"
                        }
                    },
                    {
                        "id": "extract-converted-content-processor",
                        "type": "EvaluateJsonPath",
                        "name": "Extract Converted Content",
                        "position": {"x": 1100, "y": 150},
                        "properties": {
                            "Destination": "flowfile-content",
                            "output_content": "$.output_content"
                        }
                    },
                    {
                        "id": "validate-output-processor",
                        "type": "RouteOnAttribute",
                        "name": "Validate Output",
                        "position": {"x": 1350, "y": 150},
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
                        "position": {"x": 1600, "y": 100},
                        "properties": {
                            "Hostname": "#{SFTP_HOSTNAME}",
                            "Username": "#{SFTP_USERNAME}",
                            "Password": "#{SFTP_PASSWORD}",
                            "Remote Path": "#{OUTPUT_PATH}",
                            "Remote Filename": "${filename:substringBeforeLast('.')}.#{OUTPUT_EXTENSION}",
                            "Create Directory": "true"
                        }
                    },
                    {
                        "id": "deliver-http-processor",
                        "type": "InvokeHTTP",
                        "name": "Deliver via HTTP",
                        "position": {"x": 1600, "y": 200},
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
                        "position": {"x": 1850, "y": 150},
                        "properties": {
                            "Log Level": "info",
                            "Log Prefix": "Format Conversion",
                            "Attributes to Log": "filename,detected.format,conversion.success,output.size"
                        }
                    }
                ],
                "connections": [
                    {
                        "source": "input-listener-processor",
                        "destination": "detect-format-processor",
                        "relationship": "success"
                    },
                    {
                        "source": "detect-format-processor",
                        "destination": "route-input-format-processor",
                        "relationship": "success"
                    },
                    {
                        "source": "route-input-format-processor",
                        "destination": "convert-to-edi-processor",
                        "relationships": ["json_input", "xml_input", "csv_input"]
                    },
                    {
                        "source": "route-input-format-processor",
                        "destination": "convert-from-edi-processor",
                        "relationships": ["edi_input"]
                    },
                    {
                        "source": "convert-to-edi-processor",
                        "destination": "extract-converted-content-processor",
                        "relationship": "response"
                    },
                    {
                        "source": "convert-from-edi-processor",
                        "destination": "extract-converted-content-processor",
                        "relationship": "response"
                    },
                    {
                        "source": "extract-converted-content-processor",
                        "destination": "validate-output-processor",
                        "relationship": "matched"
                    },
                    {
                        "source": "validate-output-processor",
                        "destination": "deliver-sftp-processor",
                        "relationship": "conversion_success"
                    },
                    {
                        "source": "validate-output-processor",
                        "destination": "deliver-http-processor",
                        "relationship": "conversion_success"
                    },
                    {
                        "source": "deliver-sftp-processor",
                        "destination": "log-conversion-processor",
                        "relationship": "success"
                    },
                    {
                        "source": "deliver-http-processor",
                        "destination": "log-conversion-processor",
                        "relationship": "success"
                    }
                ],
                "controller_services": [],
                "parameter_contexts": [
                    {
                        "name": "format-converter-parameters",
                        "description": "Parameters for format converter workflow",
                        "parameters": [
                            {
                                "name": "INPUT_METHOD",
                                "description": "Input method (SFTP, HTTP, etc.)",
                                "sensitive": False,
                                "value": "GetFile"
                            },
                            {
                                "name": "INPUT_PATH",
                                "description": "Input directory for file-based conversion",
                                "sensitive": False
                            },
                            {
                                "name": "INPUT_FILE_PATTERN",
                                "description": "Pattern for matching input files",
                                "sensitive": False,
                                "value": "*.*"
                            },
                            {
                                "name": "HTTP_PORT",
                                "description": "HTTP listening port",
                                "sensitive": False,
                                "value": "8082"
                            },
                            {
                                "name": "HTTP_BASE_PATH",
                                "description": "HTTP base path",
                                "sensitive": False,
                                "value": "/convert"
                            },
                            {
                                "name": "TENANT_ID",
                                "description": "Tenant identifier",
                                "sensitive": False
                            },
                            {
                                "name": "WORKFLOW_ID", 
                                "description": "Workflow identifier",
                                "sensitive": False
                            },
                            {
                                "name": "INPUT_FORMAT",
                                "description": "Input format (JSON, XML, CSV, EDI)",
                                "sensitive": False
                            },
                            {
                                "name": "OUTPUT_FORMAT",
                                "description": "Output format (JSON, XML, CSV, EDI)",
                                "sensitive": False
                            },
                            {
                                "name": "MAPPING_RULES_JSON",
                                "description": "JSON mapping rules",
                                "sensitive": False,
                                "value": "{}"
                            },
                            {
                                "name": "OUTPUT_PATH",
                                "description": "Output path for converted files",
                                "sensitive": False
                            },
                            {
                                "name": "OUTPUT_EXTENSION",
                                "description": "File extension for output",
                                "sensitive": False,
                                "value": "json"
                            },
                            {
                                "name": "SFTP_HOSTNAME",
                                "description": "SFTP server hostname",
                                "sensitive": False
                            },
                            {
                                "name": "SFTP_USERNAME",
                                "description": "SFTP username",
                                "sensitive": False
                            },
                            {
                                "name": "SFTP_PASSWORD",
                                "description": "SFTP password",
                                "sensitive": True
                            },
                            {
                                "name": "DELIVERY_HTTP_ENDPOINT",
                                "description": "HTTP delivery endpoint",
                                "sensitive": False
                            },
                            {
                                "name": "DELIVERY_CONTENT_TYPE",
                                "description": "HTTP delivery content type",
                                "sensitive": False,
                                "value": "application/json"
                            },
                            {
                                "name": "DELIVERY_AUTHORIZATION",
                                "description": "HTTP delivery authorization",
                                "sensitive": True
                            },
                            {
                                "name": "EDI_BACKEND_SERVICE_TOKEN",
                                "description": "Service token for backend API access",
                                "sensitive": True
                            }
                        ]
                    }
                ]
            },
            "configuration_schema": {
                "type": "object",
                "required": [
                    "input_config",
                    "output_config",
                    "conversion_config"
                ],
                "properties": {
                    "input_config": {
                        "type": "object",
                        "title": "Input Configuration",
                        "required": ["method"],
                        "properties": {
                            "method": {
                                "type": "string",
                                "title": "Input Method",
                                "description": "How data enters the converter",
                                "enum": ["SFTP", "HTTP", "LOCAL_FILE_SYSTEM"]
                            },
                            "path": {
                                "type": "string",
                                "title": "Input Path",
                                "description": "Directory or endpoint for input data",
                                "pattern": "^(/sftp/tenants/[^/]+/.+/$|^/local/.+/$|^http://.+)"
                            },
                            "file_patterns": {
                                "type": "array",
                                "title": "File Patterns",
                                "description": "Patterns for matching input files",
                                "items": {
                                    "type": "string"
                                },
                                "examples": [["*.edi", "*.json", "*.xml"]]
                            },
                            "http_config": {
                                "type": "object",
                                "title": "HTTP Configuration",
                                "properties": {
                                    "listening_port": {
                                        "type": "integer",
                                        "title": "Listening Port",
                                        "description": "Port for HTTP listener",
                                        "default": 8082,
                                        "minimum": 1024,
                                        "maximum": 65535
                                    },
                                    "base_path": {
                                        "type": "string",
                                        "title": "Base Path",
                                        "description": "HTTP base path",
                                        "default": "/convert"
                                    }
                                }
                            }
                        }
                    },
                    "output_config": {
                        "type": "object",
                        "title": "Output Configuration",
                        "required": ["method", "path"],
                        "properties": {
                            "method": {
                                "type": "string",
                                "title": "Output Method",
                                "description": "How data exits the converter",
                                "enum": ["SFTP", "HTTP", "LOCAL_FILE_SYSTEM"]
                            },
                            "path": {
                                "type": "string",
                                "title": "Output Path",
                                "description": "Directory or endpoint for output data",
                                "pattern": "^(/sftp/tenants/[^/]+/.+/$|^/local/.+/$|^http://.+)"
                            },
                            "file_extension": {
                                "type": "string",
                                "title": "Output File Extension",
                                "description": "File extension for output files",
                                "examples": [".json", ".xml", ".csv", ".edi"]
                            }
                        }
                    },
                    "conversion_config": {
                        "type": "object",
                        "title": "Conversion Configuration",
                        "required": ["input_format", "output_format"],
                        "properties": {
                            "input_format": {
                                "type": "string",
                                "title": "Input Format",
                                "description": "Format of input data",
                                "enum": ["JSON", "XML", "CSV", "EDI"]
                            },
                            "output_format": {
                                "type": "string",
                                "title": "Output Format",
                                "description": "Desired output format",
                                "enum": ["JSON", "XML", "CSV", "EDI"]
                            },
                            "mapping_rules": {
                                "type": "object",
                                "title": "Mapping Rules",
                                "description": "Custom mapping rules for format conversion"
                            },
                            "validation": {
                                "type": "object",
                                "title": "Validation Configuration",
                                "properties": {
                                    "validate_input": {
                                        "type": "boolean",
                                        "title": "Validate Input",
                                        "description": "Validate input format before conversion",
                                        "default": True
                                    },
                                    "validate_output": {
                                        "type": "boolean",
                                        "title": "Validate Output",
                                        "description": "Validate output format after conversion",
                                        "default": True
                                    }
                                }
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
                                "description": "Maximum retry attempts for failed conversions",
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
                            },
                            "failure_output_path": {
                                "type": "string",
                                "title": "Failure Output Path",
                                "description": "Directory for failed conversion files",
                                "pattern": "^(/sftp/tenants/[^/]+/.+/errors/$|^/local/.+/errors/$)"
                            }
                        }
                    }
                }
            }
        }

    def get_all_built_in_templates(self) -> List[Dict[str, Any]]:
        """Get all built-in template definitions."""
        return [
            self._get_sftp_edi_processor_template(),
            self._get_http_edi_processor_template(),
            self._get_format_converter_template()
        ]

    # --- Template Seeding Methods ---

    async def seed_built_in_templates(self, session: AsyncSession) -> Dict[str, Any]:
        """Seed all built-in templates into the database."""
        results = {
            "seeded": [],
            "skipped": [],
            "errors": []
        }
        
        templates = self.get_all_built_in_templates()
        
        for template_data in templates:
            try:
                result = await self._seed_template(template_data, session)
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

    async def _seed_template(self, template_data: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
        """Seed a single template into the database."""
        # Check if template already exists
        existing_query = select(WorkflowTemplate).where(
            WorkflowTemplate.template_id == template_data["template_id"]
        )
        existing_result = await session.execute(existing_query)
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
            tenant_id=template_data["tenant_id"],
            maintainer=template_data["maintainer"],
            based_on=template_data["based_on"],
            version=template_data["version"],
            flow_definition=template_data["flow_definition"],
            configuration_schema=template_data["configuration_schema"],
            deployment_method=template_data["deployment_method"],
            tags=template_data["tags"],
            features=template_data["features"],
            documentation="",  # TODO: Add detailed documentation
            examples={},  # TODO: Add examples
            is_featured=template_data["is_featured"],
            status=template_data["status"]
        )
        
        session.add(template)
        
        # Create initial version
        initial_version = WorkflowTemplate.TemplateVersion(
            template_id=template_data["template_id"],
            version=template_data["version"],
            flow_definition=template_data["flow_definition"],
            configuration_schema=template_data["configuration_schema"],
            changes="Initial built-in template version",
            created_by=template_data["maintainer"],
            is_current=True
        )
        
        session.add(initial_version)
        
        await session.commit()
        await session.refresh(template)
        
        return {
            "template_id": template_data["template_id"],
            "status": "seeded",
            "name": template_data["name"]
        }

    async def register_template_in_registry(
        self,
        template: WorkflowTemplate
    ) -> bool:
        """Register a template in NiFi Registry."""
        try:
            async with NiFiRegistryClient(self.registry_url, self.registry_auth_token) as registry_client:
                # 1. Check if bucket exists for EDI Lens templates
                buckets = await registry_client.list_buckets()
                edi_lens_bucket = None
                
                for bucket in buckets:
                    if bucket["name"] == "edi-lens-templates":
                        edi_lens_bucket = bucket
                        break
                
                # Create bucket if it doesn't exist
                if not edi_lens_bucket:
                    logger.info("Creating EDI Lens templates bucket in NiFi Registry")
                    edi_lens_bucket = await registry_client.create_bucket(
                        name="edi-lens-templates",
                        description="Built-in EDI Lens workflow templates"
                    )
                
                # 2. Check if flow exists for this template
                flows = await registry_client.list_flows(edi_lens_bucket["identifier"])
                template_flow = None
                
                for flow in flows:
                    if flow["name"] == template.name:
                        template_flow = flow
                        break
                
                # 3. Create flow if it doesn't exist
                if not template_flow:
                    logger.info(f"Creating flow for template {template.template_id}")
                    template_flow = await registry_client.create_flow(
                        bucket_id=edi_lens_bucket["identifier"],
                        flow_name=template.name,
                        flow_description=template.description
                    )
                
                # 4. Create flow version with template definition
                logger.info(f"Creating flow version for template {template.template_id}")
                flow_version = await registry_client.create_flow_version(
                    bucket_id=edi_lens_bucket["identifier"],
                    flow_id=template_flow["identifier"],
                    version_data=template.flow_definition,
                    comments=f"Template version {template.version} - {template.description}"
                )
                
                logger.info(f"Successfully registered template {template.template_id} in NiFi Registry as flow version {flow_version['version']}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to register template {template.template_id} in NiFi Registry: {str(e)}")
            return False