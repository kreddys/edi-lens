"""
NiFi Registry Client for EDI Lens.

This client provides integration with Apache NiFi Registry for managing
workflow templates as versioned flows.
"""

import aiohttp
import json
import logging
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urljoin

log = logging.getLogger(__name__)


class NiFiRegistryClient:
    """Client for NiFi Registry API integration."""

    def __init__(self, registry_url: str, auth_token: Optional[str] = None, timeout: int = 30):
        self.registry_url = registry_url.rstrip('/')
        self.auth_token = auth_token
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        headers = {'Content-Type': 'application/json'}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    # --- Bucket Management ---

    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List all available buckets."""
        async with self.session.get(f"{self.registry_url}/nifi-registry-api/buckets") as response:
            response.raise_for_status()
            return await response.json()

    async def create_bucket(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new bucket for storing flows."""
        bucket_data = {
            "name": name,
            "description": description,
            "allowBundleRedeploy": False,
            "allowPublicRead": False
        }
        
        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets",
            json=bucket_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def get_bucket(self, bucket_id: str) -> Dict[str, Any]:
        """Get bucket details by ID."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def delete_bucket(self, bucket_id: str) -> bool:
        """Delete a bucket by ID."""
        async with self.session.delete(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}"
        ) as response:
            response.raise_for_status()
            return response.status == 200

    # --- Flow Management ---

    async def create_flow(
        self,
        bucket_id: str,
        flow_name: str,
        flow_description: str = "",
        flow_type: str = "Flow"
    ) -> Dict[str, Any]:
        """Create a new flow in the registry."""
        flow_data = {
            "name": flow_name,
            "description": flow_description,
            "type": flow_type,
            "bucketIdentifier": bucket_id
        }
        
        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows",
            json=flow_data
        ) as response:
            if response.status >= 400:
                response_text = await response.text()
                log.error(f"NiFi Registry create_flow Error: {response.status} - {response_text}")
                log.error(f"Request URL: {response.url}")
                log.error(f"Request payload: {json.dumps(flow_data, indent=2)}")
                
                error_msg = f"{response.status}, message='{response.reason}', url='{response.url}'"
                if response_text:
                    try:
                        error_json = json.loads(response_text)
                        if 'message' in error_json:
                            error_msg += f", details='{error_json['message']}'"
                    except json.JSONDecodeError:
                        error_msg += f", response='{response_text}'"
                
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=error_msg,
                    headers=response.headers
                )
            
            return await response.json()

    async def create_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        version_data: Dict[str, Any],
        comments: str = ""
    ) -> Dict[str, Any]:
        """Create a new version of an existing flow."""
        # According to NiFi Registry API, we need to send a VersionedFlowSnapshot object
        # which includes bucket info, snapshot metadata, and flow contents
        
        # Handle both direct flow definition and nested flowContents structure
        if "flowContents" in version_data:
            flow_contents = version_data["flowContents"]
        elif "flow_definition" in version_data:
            # Our template structure has flow_definition at root level
            flow_contents = version_data["flow_definition"]
        else:
            # Assume the version_data IS the flow contents
            flow_contents = version_data
        
        # Ensure the flow contents have the required version field
        if "version" not in flow_contents:
            flow_contents["version"] = 1
            
        # Ensure required fields are present
        if "identifier" not in flow_contents:
            flow_contents["identifier"] = flow_id
            
        # Get existing versions to determine next version number
        existing_versions = await self.list_flow_versions(bucket_id, flow_id)
        if existing_versions:
            max_version = max(v["version"] for v in existing_versions)
            next_version = max_version + 1
        else:
            next_version = 1
        
        version_payload = {
            "bucket": {
                "identifier": bucket_id
            },
            "snapshotMetadata": {
                "flowIdentifier": flow_id,
                "comments": comments,
                "version": next_version
            },
            "flowContents": flow_contents,
            "parameterContexts": version_data.get("parameterContexts", {}),
            "externalControllerServices": version_data.get("externalControllerServices", {})
        }
        
        # Debug logging
        log.debug(f"Creating flow version {next_version} for flow {flow_id}")
        
        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions",
            json=version_payload
        ) as response:
            # Log the request and response for debugging
            response_text = await response.text()
            
            if response.status >= 400:
                # Enhanced error logging for Registry template upload
                log.error(f"=== NIFI REGISTRY TEMPLATE UPLOAD FAILURE ===")
                log.error(f"HTTP Status: {response.status} - {response.reason}")
                log.error(f"Request URL: {response.url}")
                log.error(f"Response Headers: {dict(response.headers)}")
                log.error(f"Response Body: {response_text}")
                
                # Analyze template structure for common issues
                flow_contents = version_payload.get("flowContents", {})
                processors = flow_contents.get("processors", [])
                connections = flow_contents.get("connections", [])
                
                log.error(f"Template Analysis:")
                log.error(f"  - Total Processors: {len(processors)}")
                log.error(f"  - Total Connections: {len(connections)}")
                log.error(f"  - Template Size: {len(json.dumps(version_payload))} bytes")
                
                # Check each processor for potential Registry issues
                for i, processor in enumerate(processors):
                    proc_name = processor.get('name', 'Unknown')
                    proc_type = processor.get('type', 'Unknown')
                    bundle = processor.get('bundle', {})
                    
                    log.error(f"  Processor {i+1}: {proc_name}")
                    log.error(f"    - Type: {proc_type}")
                    log.error(f"    - Bundle: {bundle.get('group', 'N/A')}/{bundle.get('artifact', 'N/A')}/{bundle.get('version', 'N/A')}")
                    log.error(f"    - Required fields: id={bool(processor.get('identifier'))}, name={bool(proc_name)}, type={bool(proc_type)}")
                
                # Look for specific Registry error patterns
                if response_text:
                    if "validation" in response_text.lower():
                        log.error("REGISTRY VALIDATION ERROR detected")
                    if "bundle" in response_text.lower():
                        log.error("REGISTRY BUNDLE ERROR detected")
                    if "property" in response_text.lower():
                        log.error("REGISTRY PROPERTY ERROR detected")
                
                log.error(f"=== END REGISTRY UPLOAD DEBUG ===")
                
                # Create a detailed error message
                error_msg = f"{response.status}, message='{response.reason}', url='{response.url}'"
                if response_text:
                    try:
                        error_json = json.loads(response_text)
                        if 'message' in error_json:
                            error_msg += f", details='{error_json['message']}'"
                    except json.JSONDecodeError:
                        error_msg += f", response='{response_text}'"
                
                # Raise a more informative exception
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=error_msg,
                    headers=response.headers
                )
            
            # Parse the response
            try:
                result = json.loads(response_text)
                
                # Check if there are any validation warnings or issues
                if "flowContents" in result:
                    sent_processors = len(version_payload.get("flowContents", {}).get("processors", []))
                    received_processors = len(result["flowContents"].get("processors", []))
                    if sent_processors != received_processors:
                        log.warning(f"Processor count mismatch: sent {sent_processors}, received {received_processors}")
                        log.warning(f"Sent processors: {[p.get('name', p.get('id', 'unknown')) for p in version_payload.get('flowContents', {}).get('processors', [])]}")
                        log.warning(f"Received processors: {[p.get('name', p.get('identifier', 'unknown')) for p in result['flowContents'].get('processors', [])]}")
                
                return result
            except json.JSONDecodeError as e:
                log.error(f"Failed to parse Registry response as JSON: {e}")
                log.error(f"Raw response: {response_text}")
                raise

    async def get_flow(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Get flow details by ID."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def list_flows(self, bucket_id: str) -> List[Dict[str, Any]]:
        """List all flows in a bucket."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows"
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def delete_flow(self, bucket_id: str, flow_id: str) -> bool:
        """Delete a flow by ID."""
        async with self.session.delete(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}"
        ) as response:
            response.raise_for_status()
            return response.status == 200

    # --- Flow Version Management ---

    async def get_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        version: Optional[Union[int, str]] = None
    ) -> Dict[str, Any]:
        """Get a specific version of a flow."""
        log.debug(f"Getting flow version: bucket_id={bucket_id}, flow_id={flow_id}, version={version}")
        url = f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}"
        if version:
            url += f"/versions/{version}"
        
        log.debug(f"Getting flow version {version or 'latest'} for flow {flow_id} from URL: {url}")
        async with self.session.get(url) as response:
            response.raise_for_status()
            result = await response.json()
            return result

    async def list_flow_versions(self, bucket_id: str, flow_id: str) -> List[Dict[str, Any]]:
        """List all versions of a flow."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions"
        ) as response:
            response.raise_for_status()
            return await response.json()

    # --- Extension Bundles (for custom processors) ---

    async def upload_extension_bundle(
        self,
        bucket_id: str,
        file_path: str,
        bundle_name: str,
        bundle_description: str = ""
    ) -> Dict[str, Any]:
        """Upload a custom processor bundle (NAR file)."""
        # This would typically involve multipart form upload
        # Implementation details would depend on the specific API
        raise NotImplementedError("Extension bundle upload not yet implemented")

    # --- Health and Diagnostics ---

    async def get_registry_info(self) -> Dict[str, Any]:
        """Get registry information and version."""
        async with self.session.get(f"{self.registry_url}/nifi-registry-api/config") as response:
            response.raise_for_status()
            return await response.json()

    async def health_check(self) -> Dict[str, Any]:
        """Check if the registry is healthy."""
        async with self.session.get(f"{self.registry_url}/nifi-registry-api/health") as response:
            response.raise_for_status()
            return await response.json()