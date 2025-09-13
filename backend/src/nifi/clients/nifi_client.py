"""
NiFi API Client for EDI Lens.

This client provides integration with Apache NiFi for managing
running instances of workflows as process groups.
"""

import aiohttp
import json
import logging
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urljoin

from src.exceptions.workflow_exceptions import NiFiConnectionError, NiFiAPIError

log = logging.getLogger(__name__)


class NiFiAPIClient:
    """Client for NiFi REST API integration."""

    def __init__(self, nifi_url: str, auth_token: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize NiFi API Client.
        
        Args:
            nifi_url: Base NiFi URL (e.g., 'http://nifi:8080')
            auth_token: Optional Bearer token for authentication
            username: Optional username for token-based auth
            password: Optional password for token-based auth
        """
        self.base_url = nifi_url.rstrip('/')
        self.nifi_url = f"{self.base_url}/nifi-api"
        self.auth_token = auth_token
        self.username = username
        self.password = password
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        # Create SSL context that skips certificate verification for development
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Create session without basic auth (we'll use token auth instead)
        # Use different connector based on URL scheme
        if self.nifi_url.startswith('https'):
            session_connector = aiohttp.TCPConnector(ssl=ssl_context)
        else:
            session_connector = aiohttp.TCPConnector()  # No SSL for HTTP
            
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=session_connector
        )
        
        # Get auth token if username/password provided
        if not self.auth_token and self.username and self.password:
            try:
                self.auth_token = await self._get_auth_token()
                log.info(f"Successfully authenticated with NiFi at {self.nifi_url}")
            except Exception as e:
                log.error(f"Failed to authenticate with NiFi at {self.nifi_url}: {e}")
                raise NiFiConnectionError(
                    f"Authentication failed with username {self.username}",
                    url=self.nifi_url
                ) from e
        
        # Update session headers with auth token
        headers = {'Content-Type': 'application/json'}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        # Close and recreate session with auth headers
        await self.session.close()
        
        # Use appropriate connector for the session
        if self.nifi_url.startswith('https'):
            session_connector = aiohttp.TCPConnector(ssl=ssl_context)
        else:
            session_connector = aiohttp.TCPConnector()
            
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
            connector=session_connector
        )
        return self
    
    async def _get_auth_token(self) -> str:
        """Get authentication token from NiFi."""
        auth_data = f"username={self.username}&password={self.password}"
        token_url = f"{self.nifi_url}/access/token"
        
        log.debug(f"Requesting auth token from {token_url}")
        
        try:
            async with self.session.post(
                token_url,
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                if response.status == 201:
                    token = await response.text()
                    log.debug("Successfully obtained auth token")
                    return token
                else:
                    error_text = await response.text()
                    log.error(f"Auth token request failed: {response.status} - {error_text}")
                    raise NiFiConnectionError(
                        f"Authentication rejected by NiFi server: {response.status}",
                        url=token_url,
                        status_code=response.status
                    )
        except aiohttp.ClientError as e:
            log.error(f"Network error during authentication: {e}")
            raise NiFiConnectionError(
                f"Network error connecting to NiFi: {str(e)}",
                url=token_url
            ) from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _make_api_call(
        self, 
        method: str, 
        endpoint: str, 
        json_data: dict = None, 
        params: dict = None,
        expected_status: int = 200
    ) -> dict:
        """Make an API call with proper error handling and logging."""
        url = f"{self.nifi_url}/{endpoint.lstrip('/')}"
        
        log.debug(f"{method.upper()} {url}")
        if json_data:
            log.debug(f"Request payload: {json_data}")
        
        try:
            async with self.session.request(
                method, url, json=json_data, params=params
            ) as response:
                response_text = await response.text()
                
                log.debug(f"Response status: {response.status}")
                log.debug(f"Response body: {response_text[:500]}...")
                
                if response.status != expected_status:
                    log.error(f"API call failed: {method} {endpoint} returned {response.status}")
                    raise NiFiAPIError(
                        f"{method.upper()} {endpoint} failed",
                        endpoint=endpoint,
                        status_code=response.status,
                        response_body=response_text
                    )
                
                # Parse JSON response if possible
                try:
                    return json.loads(response_text) if response_text else {}
                except json.JSONDecodeError:
                    return {"raw_response": response_text}
                    
        except aiohttp.ClientError as e:
            log.error(f"Network error during API call {method} {endpoint}: {e}")
            raise NiFiConnectionError(
                f"Network error: {str(e)}",
                url=url
            ) from e

    # --- Process Groups ---

    async def create_process_group(
        self,
        parent_group_id: str,
        name: str,
        position: Dict[str, int],
        template_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new process group."""
        process_group_data = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "position": position,
                "parentGroupId": parent_group_id
            }
        }
        
        if template_id:
            process_group_data["component"]["templateId"] = template_id
        
        async with self.session.post(
            f"{self.nifi_url}/process-groups/{parent_group_id}/process-groups",
            json=process_group_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def get_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Get process group details by ID."""
        url = f"{self.nifi_url}/process-groups/{process_group_id}"
        log.debug(f"Getting process group from URL: {url}")
        try:
            log.debug(f"About to make HTTP request to NiFi")
            async with self.session.get(url) as response:
                log.debug(f"Response status: {response.status}")
                log.debug(f"Response headers: {dict(response.headers)}")
                
                try:
                    response.raise_for_status()  # This is NOT async!
                    log.debug("Response status check passed")
                except Exception as e:
                    log.error(f"Response status check failed: {e}")
                    raise
                
                try:
                    text = await response.text()
                    log.debug(f"Response text length: {len(text) if text else 0}")
                    log.debug(f"Response text: {text[:500]}...")  # First 500 chars
                except Exception as e:
                    log.error(f"Failed to get response text: {e}")
                    return {}
                
                if not text:
                    log.warning("Response text is empty")
                    return {}
                    
                try:
                    import json
                    result = json.loads(text)
                    log.debug(f"Response parsed successfully, keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
                    return result
                except Exception as e:
                    log.error(f"Failed to parse response as JSON: {e}")
                    log.error(f"Response text was: {text}")
                    return {}
        except Exception as e:
            log.error(f"Unexpected error in get_process_group: {e}")
            log.error(f"Exception type: {type(e)}")
            raise

    async def update_process_group(
        self,
        process_group_id: str,
        name: Optional[str] = None,
        position: Optional[Dict[str, int]] = None,
        parameter_context_id: Optional[str] = None,
        version: int = 0
    ) -> Dict[str, Any]:
        """Update process group properties."""
        # First get current state
        current = await self.get_process_group(process_group_id)
        
        # Use current revision if version not specified
        if version == 0:
            version = current.get("revision", {}).get("version", 0)
        
        update_data = {
            "revision": {"version": version},
            "component": {
                "id": process_group_id
            }
        }
        
        if name:
            update_data["component"]["name"] = name
        if position:
            update_data["component"]["position"] = position
        if parameter_context_id:
            update_data["component"]["parameterContext"] = {
                "id": parameter_context_id
            }
            
        async with self.session.put(
            f"{self.nifi_url}/process-groups/{process_group_id}",
            json=update_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def delete_process_group(
        self,
        process_group_id: str,
        version: int = 0
    ) -> bool:
        """Delete a process group."""
        async with self.session.delete(
            f"{self.nifi_url}/process-groups/{process_group_id}",
            params={"version": version}
        ) as response:
            response.raise_for_status()
            return response.status == 200

    async def start_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Start a process group."""
        # Use the correct NiFi API endpoint and format for starting process groups
        # The request body needs to include the process group ID and state
        request_body = {
            "id": process_group_id,
            "state": "RUNNING"
        }
        
        async with self.session.put(
            f"{self.nifi_url}/flow/process-groups/{process_group_id}",
            json=request_body,
            headers={"Content-Type": "application/json"}
        ) as response:
            # Log the response for debugging
            if response.status >= 400:
                try:
                    error_text = await response.text()
                    log.error(f"NiFi API Error (start): {response.status} - {error_text}")
                except:
                    pass
            response.raise_for_status()
            return await response.json()

    async def stop_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Stop a process group."""
        # Use the correct NiFi API endpoint and format for stopping process groups
        # The request body needs to include the process group ID and state
        request_body = {
            "id": process_group_id,
            "state": "STOPPED"
        }
        
        async with self.session.put(
            f"{self.nifi_url}/flow/process-groups/{process_group_id}",
            json=request_body,
            headers={"Content-Type": "application/json"}
        ) as response:
            # Log the response for debugging
            if response.status >= 400:
                try:
                    error_text = await response.text()
                    log.error(f"NiFi API Error (stop): {response.status} - {error_text}")
                except:
                    pass
            response.raise_for_status()
            return await response.json()

    # --- Parameter Contexts ---

    async def create_parameter_context(
        self,
        name: str,
        description: str = "",
        parameters: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Create a new parameter context."""
        log.debug("Creating parameter context with NiFi API")
        log.debug(f"Parameter context name: {name}")
        log.debug(f"Parameter context description: {description}")
        log.debug(f"Parameters count: {len(parameters) if parameters else 0}")
        
        # Transform parameters to NiFi format - each parameter must be wrapped in a "parameter" object
        formatted_parameters = []
        if parameters:
            log.debug(f"Formatting {len(parameters)} parameters for NiFi API")
            for param in parameters:
                formatted_param = {
                    "parameter": param
                }
                formatted_parameters.append(formatted_param)
                log.debug(f"Formatted parameter: {param['name']} = '{param['value']}'")
        else:
            log.debug("No parameters to format")
        
        param_context_data = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "description": description,
                "parameters": formatted_parameters
            }
        }
        
        # Debug logging
        log.debug(f"Sending parameter context data to NiFi: {param_context_data}")
        log.debug(f"Number of parameters in payload: {len(formatted_parameters)}")
        
        async with self.session.post(
            f"{self.nifi_url}/parameter-contexts",
            json=param_context_data
        ) as response:
            # Log the response for debugging
            if response.status >= 400:
                try:
                    error_text = await response.text()
                    log.error(f"NiFi API Error: {response.status} - {error_text}")
                    # Raise the error with more details
                    response.raise_for_status()
                except Exception as e:
                    log.error(f"Exception while handling NiFi API error: {str(e)}")
                    raise
            else:
                result = await response.json()
                log.info("Parameter context created successfully in NiFi")
                log.debug(f"Parameter context ID: {result.get('id')}")
                log.debug(f"Parameter context name: {result.get('component', {}).get('name')}")
                log.debug(f"Parameter context parameters: {len(result.get('component', {}).get('parameters', []))}")
                return result

    async def get_parameter_context(self, context_id: str) -> Dict[str, Any]:
        """Get parameter context by ID."""
        async with self.session.get(
            f"{self.nifi_url}/parameter-contexts/{context_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def update_parameter_context(
        self,
        context_id: str,
        parameters: List[Dict[str, Any]],
        version: int = 0
    ) -> Dict[str, Any]:
        """Update parameter context with new parameters."""
        update_data = {
            "revision": {"version": version},
            "component": {
                "id": context_id,
                "parameters": parameters
            }
        }
        
        async with self.session.put(
            f"{self.nifi_url}/parameter-contexts/{context_id}",
            json=update_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    # --- Templates ---

    async def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates."""
        async with self.session.get(f"{self.nifi_url}/templates") as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("templates", [])

    async def instantiate_template(
        self,
        parent_group_id: str,
        template_id: str,
        position: Dict[str, int]
    ) -> Dict[str, Any]:
        """Instantiate a template in a process group."""
        template_data = {
            "originX": position["x"],
            "originY": position["y"],
            "templateId": template_id
        }
        
        async with self.session.post(
            f"{self.nifi_url}/process-groups/{parent_group_id}/template-instance",
            json=template_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    # --- Controller Services ---

    async def create_controller_service(
        self,
        parent_group_id: str,
        service_type: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a controller service."""
        service_data = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "type": service_type,
                "parentGroupId": parent_group_id
            }
        }
        
        if properties:
            service_data["component"]["properties"] = properties
        
        async with self.session.post(
            f"{self.nifi_url}/process-groups/{parent_group_id}/controller-services",
            json=service_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    # --- Processors ---

    async def create_processor(
        self,
        parent_group_id: str,
        processor_type: str,
        name: str,
        position: Dict[str, int],
        properties: Optional[Dict[str, Any]] = None,
        scheduling: Optional[Dict[str, Any]] = None,
        auto_terminated_relationships: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a processor in the specified process group."""
        processor_data = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "type": processor_type,
                "parentGroupId": parent_group_id,
                "position": position
            }
        }
        
        # Add properties to the component if provided
        if properties:
            # Ensure property values are properly formatted as strings
            formatted_properties = {}
            for key, value in properties.items():
                if isinstance(value, (dict, list)):
                    formatted_properties[key] = json.dumps(value)
                else:
                    formatted_properties[key] = str(value) if value is not None else ""
            processor_data["component"]["properties"] = formatted_properties
            
        # Add scheduling configuration if provided
        if scheduling:
            config = {}
            config["schedulingPeriod"] = scheduling.get("period", "0 sec")
            config["schedulingStrategy"] = scheduling.get("strategy", "TIMER_DRIVEN")
            config["concurrentlySchedulableTaskCount"] = scheduling.get("concurrent_tasks", 1)
            processor_data["component"]["config"] = config
            
        async with self.session.post(
            f"{self.nifi_url}/process-groups/{parent_group_id}/processors",
            json=processor_data
        ) as response:
            # Log detailed request and response information for debugging
            log.debug(f"NiFi API Request - URL: {response.url}")
            log.debug(f"NiFi API Request - Method: POST")
            log.debug(f"NiFi API Request - Headers: {getattr(self.session, 'headers', {})}")
            log.debug(f"NiFi API Request - Body: {processor_data}")
            
            try:
                response.raise_for_status()
                result = await response.json()
                log.debug(f"NiFi API Response - Status: {response.status}")
                log.debug(f"NiFi API Response - Body: {result}")
                return result
            except aiohttp.ClientResponseError as e:
                # Try to get error details
                try:
                    error_text = await response.text()
                    log.error(f"NiFi API Error (create processor): {response.status} - {error_text}")
                    log.error(f"Request URL: {response.url}")
                    log.error(f"Request data: {processor_data}")
                except Exception as ex:
                    log.error(f"Failed to read error response: {ex}")
                
                # Re-raise with more context
                raise Exception(f"Failed to create processor '{name}' of type '{processor_type}': {response.status} - {e.message}") from e
            except Exception as e:
                log.error(f"Unexpected error creating processor '{name}' of type '{processor_type}': {str(e)}")
                log.error(f"Request URL: {response.url}")
                log.error(f"Request data: {processor_data}")
                raise Exception(f"Unexpected error creating processor '{name}' of type '{processor_type}': {str(e)}") from e

    async def get_processor(self, processor_id: str) -> Dict[str, Any]:
        """Get processor details by ID."""
        async with self.session.get(
            f"{self.nifi_url}/processors/{processor_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def update_processor(
        self,
        processor_id: str,
        properties: Optional[Dict[str, Any]] = None,
        scheduling: Optional[Dict[str, Any]] = None,
        version: int = 0
    ) -> Dict[str, Any]:
        """Update processor configuration."""
        # First get current state to get the revision
        current = await self.get_processor(processor_id)
        current_version = current.get("revision", {}).get("version", 0)
        
        update_data = {
            "revision": {"version": current_version},
            "component": {
                "id": processor_id
            }
        }
        
        if properties or scheduling:
            config = {}
            if properties:
                config["properties"] = properties
            if scheduling:
                config.update({
                    "schedulingPeriod": scheduling.get("period", "0 sec"),
                    "schedulingStrategy": scheduling.get("strategy", "TIMER_DRIVEN"),
                    "concurrentlySchedulableTaskCount": scheduling.get("concurrent_tasks", 1)
                })
            update_data["component"]["config"] = config
            
        async with self.session.put(
            f"{self.nifi_url}/processors/{processor_id}",
            json=update_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    # --- Connections ---

    async def create_connection(
        self,
        source_id: str,
        source_type: str,
        destination_id: str,
        destination_type: str,
        relationships: List[str],
        parent_group_id: str,
        name: Optional[str] = None,
        back_pressure_object_threshold: int = 1000,
        back_pressure_data_size_threshold: str = "1 GB",
        flow_file_expiration: str = "0 sec"
    ) -> Dict[str, Any]:
        """Create a connection between processors."""
        connection_data = {
            "revision": {"version": 0},
            "component": {
                "name": name or f"{source_id} -> {destination_id}",
                "source": {
                    "id": source_id,
                    "type": source_type,
                    "groupId": parent_group_id
                },
                "destination": {
                    "id": destination_id,
                    "type": destination_type,
                    "groupId": parent_group_id
                },
                "selectedRelationships": relationships,
                "backPressureObjectThreshold": back_pressure_object_threshold,
                "backPressureDataSizeThreshold": back_pressure_data_size_threshold,
                "flowFileExpiration": flow_file_expiration
            }
        }
        
        async with self.session.post(
            f"{self.nifi_url}/process-groups/{parent_group_id}/connections",
            json=connection_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def get_connection(self, connection_id: str) -> Dict[str, Any]:
        """Get connection details by ID."""
        async with self.session.get(
            f"{self.nifi_url}/connections/{connection_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()

    # --- Health and Diagnostics ---

    async def get_system_diagnostics(self) -> Dict[str, Any]:
        """Get system diagnostics."""
        async with self.session.get(f"{self.nifi_url}/system-diagnostics") as response:
            response.raise_for_status()
            return await response.json()

    async def get_flow_status(self) -> Dict[str, Any]:
        """Get overall flow status."""
        async with self.session.get(f"{self.nifi_url}/flow/status") as response:
            response.raise_for_status()
            return await response.json()

    async def delete_parameter_context(self, context_id: str, version: int = 0) -> bool:
        """Delete a parameter context."""
        async with self.session.delete(
            f"{self.nifi_url}/parameter-contexts/{context_id}",
            params={"version": version}
        ) as response:
            if response.status >= 400:
                try:
                    error_text = await response.text()
                    log.error(f"NiFi API Error (delete parameter context): {response.status} - {error_text}")
                except:
                    pass
            response.raise_for_status()
            return response.status == 200

    async def get_processors_in_group(self, process_group_id: str) -> List[Dict[str, Any]]:
        """Get all processors in a process group."""
        async with self.session.get(
            f"{self.nifi_url}/process-groups/{process_group_id}/processors"
        ) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("processors", [])

    async def restart_processor(self, processor_id: str, version: int = 0) -> Dict[str, Any]:
        """Restart a processor to force parameter re-evaluation."""
        try:
            # First get current state
            log.debug(f"Getting current state for processor {processor_id}")
            async with self.session.get(
                f"{self.nifi_url}/processors/{processor_id}"
            ) as response:
                response.raise_for_status()
                current_state = await response.json()
                
            # Use current revision if version not specified
            if version == 0:
                version = current_state.get("revision", {}).get("version", 0)
            
            current_status = current_state.get("component", {}).get("state", "STOPPED")
            validation_status = current_state.get("component", {}).get("validationStatus", "VALID")
            
            log.debug(f"Processor {processor_id}: state={current_status}, validationStatus={validation_status}, version={version}")
            
            # If processor is INVALID, we can't restart it until it becomes valid
            if validation_status == "INVALID":
                log.warning(f"Processor {processor_id} is INVALID, cannot restart until validation issues are resolved")
                return {"status": "skipped", "reason": "Processor is invalid"}
            
            # Stop processor if it's running
            if current_status == "RUNNING":
                log.debug(f"Stopping processor {processor_id} (currently RUNNING)")
                stop_data = {
                    "revision": {"version": version},
                    "state": "STOPPED"
                }
                
                async with self.session.put(
                    f"{self.nifi_url}/processors/{processor_id}/run-status",
                    json=stop_data
                ) as response:
                    response.raise_for_status()
                    stopped_state = await response.json()
                    version = stopped_state.get("revision", {}).get("version", version + 1)
                    log.debug(f"Processor {processor_id} stopped, new version: {version}")
            
            # Start processor to trigger parameter re-evaluation
            log.debug(f"Starting processor {processor_id}")
            start_data = {
                "revision": {"version": version},
                "state": "RUNNING"
            }
            
            async with self.session.put(
                f"{self.nifi_url}/processors/{processor_id}/run-status",
                json=start_data
            ) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    log.error(f"Failed to start processor {processor_id}: {response.status} - {error_text}")
                response.raise_for_status()
                result = await response.json()
                log.debug(f"Processor {processor_id} restarted successfully")
                return result
                
        except Exception as e:
            log.error(f"Failed to restart processor {processor_id}: {e}")
            raise

    async def get_processor_types(self) -> List[Dict[str, Any]]:
        """Get all available processor types from NiFi."""
        return await self._make_api_call("GET", "flow/processor-types")

    async def get_processor_type_details(self, type_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific processor type including property descriptors."""
        try:
            # Get basic processor type info
            processor_types = await self.get_processor_types()
            processor_type = None
            for pt in processor_types.get("processorTypes", []):
                if pt.get("type") == type_name:
                    processor_type = pt
                    break
            
            if not processor_type:
                return None
            
            # Get property descriptors by creating a temporary processor
            root_pg = await self.get_process_group("root")
            root_id = root_pg["component"]["id"]
            
            # Create temporary processor
            temp_processor = await self.create_processor(
                parent_group_id=root_id,
                processor_type=type_name,
                name="TEMP_VALIDATION_PROCESSOR",
                position={"x": 0, "y": 0}
            )
            
            temp_id = temp_processor["id"]
            
            try:
                # Get processor details with property descriptors
                processor_details = await self.get_processor(temp_id)
                config = processor_details.get("component", {}).get("config", {})
                descriptors = config.get("descriptors", {})
                
                # Convert descriptors to the format our validator expects
                supported_property_descriptors = []
                for prop_name, descriptor in descriptors.items():
                    supported_property_descriptors.append({
                        "name": prop_name,
                        "displayName": descriptor.get("displayName", prop_name),
                        "required": descriptor.get("required", False),
                        "defaultValue": descriptor.get("defaultValue"),
                        "allowableValues": descriptor.get("allowableValues", [])
                    })
                
                # Add property descriptors to processor type info
                processor_type["supportedPropertyDescriptors"] = supported_property_descriptors
                
            finally:
                # Clean up - delete temporary processor
                try:
                    current_processor = await self.get_processor(temp_id)
                    current_version = current_processor.get("revision", {}).get("version", 0)
                    await self.session.delete(f"{self.nifi_url}/processors/{temp_id}?version={current_version}")
                except Exception as e:
                    log.warning(f"Failed to clean up temporary processor {temp_id}: {e}")
            
            return processor_type
            
        except Exception as e:
            log.error(f"Failed to get processor type details for {type_name}: {e}")
            return None

    async def health_check(self) -> bool:
        """Check if NiFi is healthy."""
        try:
            async with self.session.get(f"{self.nifi_url}/system-diagnostics") as response:
                return response.status == 200
        except Exception:
            return False