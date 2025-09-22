"""NiFi API client with minimal ergonomics and sane defaults."""

from __future__ import annotations

import json
import logging
import ssl
import time
from typing import Any, Dict, List, Optional

import aiohttp

from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class NiFiClientError(RuntimeError):
    """Raised when NiFi API calls fail."""


class NiFiClient(LoggerMixin):
    """Simple NiFi API client."""

    def __init__(
        self,
        nifi_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        *,
        session: Optional[aiohttp.ClientSession] = None,
        verify_ssl: bool = True,
        timeout: Optional[float] = 30,
    ):
        self.nifi_url = nifi_url.rstrip("/")
        self.username = username
        self.password = password
        self._external_session = session
        self.verify_ssl = verify_ssl
        self._timeout = aiohttp.ClientTimeout(total=timeout) if timeout else None
        self.session: Optional[aiohttp.ClientSession] = session
        self.auth_token: Optional[str] = None
        
        self.logger.info("Initializing NiFi client for %s", self.nifi_url)
        self.logger.debug("Authentication: %s", "enabled" if username else "disabled")
        self.logger.debug("SSL verification: %s", "enabled" if verify_ssl else "disabled")
        self.logger.debug("Timeout: %ss", timeout if timeout else "unlimited")
        
        if not verify_ssl:
            self.logger.warning("SSL verification is disabled - not recommended for production")

    async def __aenter__(self) -> "NiFiClient":
        """Async context manager entry."""
        self.logger.debug("Starting NiFi client session")
        
        if self.session is None:
            self.session = await self._create_session()
            self.logger.debug("NiFi client session created")
        else:
            self.logger.debug("Reusing existing NiFi client session")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if exc_type:
            self.logger.error("NiFi client session ended with error: %s", exc_val)
        else:
            self.logger.debug("NiFi client session ended normally")

        if self.session and self._external_session is None:
            await self.session.close()
            self.logger.debug("NiFi client session closed")
            self.session = None

    async def _create_session(self) -> aiohttp.ClientSession:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        connector = None
        if not self.verify_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)

        # Create initial session for authentication
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=self._timeout,
        )

        # Get access token if username/password provided
        if self.username and self.password:
            await self._authenticate_session(session)

        # Close initial session and recreate with auth headers
        await session.close()

        # Add authorization header if we have a token
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        # Create final authenticated session
        session = aiohttp.ClientSession(
            headers=headers,
            connector=aiohttp.TCPConnector(ssl=ssl_context) if not self.verify_ssl else None,
            timeout=self._timeout,
        )

        return session

    async def _get_fresh_token(self, session: aiohttp.ClientSession) -> str:
        """Get a fresh access token for NiFi."""
        auth_url = f"{self.nifi_url}/nifi-api/access/token"

        try:
            async with session.post(
                auth_url,
                data=f"username={self.username}&password={self.password}",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "text/plain"
                }
            ) as response:
                if response.status == 201:
                    token = await response.text()
                    self.logger.debug("Successfully obtained fresh NiFi token")
                    return token
                elif response.status == 400:
                    self.logger.error("Authentication failed: Invalid credentials")
                elif response.status == 409:
                    self.logger.error("Authentication failed: User account is locked")
                else:
                    response_text = await response.text()
                    self.logger.error(f"Authentication failed with status {response.status}: {response_text}")

        except Exception as exc:
            self.logger.error(f"Failed to authenticate with NiFi: {exc}")

        return ""

    async def _authenticate_session(self, session: aiohttp.ClientSession) -> None:
        """Authenticate session and get access token for NiFi 2.x."""
        token = await self._get_fresh_token(session)
        if token:
            self.auth_token = token
            self.logger.info("Successfully authenticated with NiFi")
        else:
            self.logger.warning("Failed to get NiFi token - continuing without authentication")

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        if self.session is None:
            error_msg = "Client session has not been initialised. Use 'async with NiFiClient(...)'."
            self.logger.error("❌ %s", error_msg)
            raise NiFiClientError(error_msg)

        url = f"{self.nifi_url}{path}"
        start_time = time.time()

        # Log request details
        self.logger.debug("NiFi API request: %s %s", method, path)
        if kwargs.get("json"):
            self.logger.debug("Request payload size: %d bytes", len(str(kwargs["json"])))

        try:
            async with self.session.request(method, url, **kwargs) as response:
                execution_time = (time.time() - start_time) * 1000

                # Log response details
                self.logger.debug("NiFi API response: %d (%.2fms) %s",
                                response.status, execution_time, response.content_type)

                # Check for errors before parsing response
                if response.status >= 400:
                    error_text = await response.text()
                    self.logger.error("NiFi API error %d: %s", response.status, error_text)

                response.raise_for_status()

                # Log successful response
                self.logger.debug("NiFi API success: %s %s -> %d", method, path, response.status)

                if response.content_type == "application/json":
                    result = await response.json()
                    if isinstance(result, list):
                        self.logger.debug("Response data: %d items", len(result))
                    elif isinstance(result, dict):
                        self.logger.debug("Response data: dict with %d keys", len(result))
                    else:
                        self.logger.debug("Response data: %s", type(result).__name__)
                    return result
                return await response.text()

        except aiohttp.ClientError as exc:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error("NiFi client request failed after %.2fms: %s %s - %s",
                            execution_time, method, path, exc)
            raise NiFiClientError(f"Request to NiFi failed: {exc}") from exc

    async def get_system_summary(self) -> Dict[str, Any]:
        """Get NiFi system summary - basic connectivity test."""

        result = await self._request("GET", "/nifi-api/system-diagnostics")
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response format for system diagnostics")
        return result

    async def get_root_process_group(self, *, ui_only: bool = True) -> Dict[str, Any]:
        """Get root process group; request UI snapshot by default."""

        path = "/nifi-api/process-groups/root"
        if ui_only:
            path += "?uiOnly=true"

        result = await self._request("GET", path)
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response format for root process group")
        return result

    async def get_process_group_flow(self, pg_id: str = "root") -> Dict[str, Any]:
        """Get process group flow contents."""

        result = await self._request("GET", f"/nifi-api/process-groups/{pg_id}/flow")
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response format for process group flow")
        return result

    async def get_process_group(self, process_group_id: str, *, ui_only: bool = False) -> Dict[str, Any]:
        """Get process group metadata."""

        path = f"/nifi-api/process-groups/{process_group_id}"
        if ui_only:
            path += "?uiOnly=true"

        result = await self._request("GET", path)
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response format for process group")
        return result

    async def dry_run_import_process_group(
        self,
        parent_group_id: str,
        upload_entity: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call NiFi import endpoint with dry-run flag for validation."""

        result = await self._request(
            "POST",
            f"/nifi-api/process-groups/{parent_group_id}/process-groups/import",
            json=upload_entity,
            params={"dryRun": "true"},
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response during dry-run import")
        return result

    async def create_process_group(
        self,
        parent_group_id: str,
        name: str,
        *,
        position: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Create a new process group under the given parent."""

        payload = {
            "revision": {"version": 0},
            "component": {
                "parentGroupId": parent_group_id,
                "name": name,
                "position": position or {"x": 0.0, "y": 0.0},
            },
        }

        result = await self._request(
            "POST",
            f"/nifi-api/process-groups/{parent_group_id}/process-groups",
            json=payload,
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response creating process group")
        return result

    async def update_process_group(
        self,
        process_group_id: str,
        *,
        revision: Optional[int] = None,
        name: Optional[str] = None,
        position: Optional[Dict[str, float]] = None,
        parameter_context_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update process group attributes."""

        if revision is None:
            current = await self.get_process_group(process_group_id)
            revision = current.get("revision", {}).get("version", 0)

        component: Dict[str, Any] = {"id": process_group_id}
        if name is not None:
            component["name"] = name
        if position is not None:
            component["position"] = position
        if parameter_context_id is not None:
            component["parameterContext"] = {"id": parameter_context_id}

        payload = {
            "revision": {"version": revision},
            "component": component,
        }

        result = await self._request(
            "PUT",
            f"/nifi-api/process-groups/{process_group_id}",
            json=payload,
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response updating process group")
        return result

    async def create_parameter_context(
        self,
        name: str,
        *,
        description: str = "",
        parameters: Optional[list[dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create a parameter context."""

        payload = {
            "component": {
                "name": name,
                "description": description,
                "parameters": parameters or [],
            },
            "revision": {"version": 0},
        }

        result = await self._request(
            "POST",
            "/nifi-api/parameter-contexts",
            json=payload,
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response creating parameter context")
        return result

    async def delete_parameter_context(self, context_id: str, *, revision: int) -> Dict[str, Any]:
        """Delete a parameter context by ID."""

        params = {"version": revision}
        result = await self._request(
            "DELETE",
            f"/nifi-api/parameter-contexts/{context_id}",
            params=params,
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response deleting parameter context")
        return result

    async def create_processor(
        self,
        parent_group_id: str,
        processor_type: str,
        name: str,
        *,
        position: Optional[Dict[str, float]] = None,
        properties: Optional[Dict[str, Any]] = None,
        scheduling: Optional[Dict[str, Any]] = None,
        auto_terminated_relationships: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a processor within the specified process group."""

        formatted_properties: Dict[str, Any] = {}
        if properties:
            for key, value in properties.items():
                if isinstance(value, (dict, list)):
                    formatted_properties[key] = json.dumps(value)
                elif value is None:
                    formatted_properties[key] = ""
                else:
                    formatted_properties[key] = str(value)

        scheduling_period = "0 sec"
        scheduling_strategy = "TIMER_DRIVEN"
        concurrent_tasks = 1
        execution_node = None
        bulletin_level = None
        if scheduling:
            scheduling_period = (
                scheduling.get("period")
                or scheduling.get("schedulingPeriod")
                or scheduling_period
            )
            scheduling_strategy = (
                scheduling.get("strategy")
                or scheduling.get("schedulingStrategy")
                or scheduling_strategy
            )
            concurrent_tasks = (
                scheduling.get("concurrent_tasks")
                or scheduling.get("concurrentlySchedulableTaskCount")
                or concurrent_tasks
            )
            execution_node = scheduling.get("executionNode")
            bulletin_level = scheduling.get("bulletinLevel")

        config: Dict[str, Any] = {
            "properties": formatted_properties,
            "schedulingPeriod": scheduling_period,
            "schedulingStrategy": scheduling_strategy,
            "concurrentlySchedulableTaskCount": concurrent_tasks,
        }
        if execution_node is not None:
            config["executionNode"] = execution_node
        if bulletin_level is not None:
            config["bulletinLevel"] = bulletin_level
        if auto_terminated_relationships:
            config["autoTerminatedRelationships"] = list(auto_terminated_relationships)

        payload = {
            "revision": {"version": 0},
            "component": {
                "parentGroupId": parent_group_id,
                "name": name,
                "type": processor_type,
                "position": position or {"x": 0.0, "y": 0.0},
                "config": config,
            },
        }

        result = await self._request(
            "POST",
            f"/nifi-api/process-groups/{parent_group_id}/processors",
            json=payload,
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response creating processor")
        return result

    async def get_processor(self, processor_id: str) -> Dict[str, Any]:
        """Get processor details by ID."""

        result = await self._request("GET", f"/nifi-api/processors/{processor_id}")
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response getting processor")
        return result

    async def delete_processor(self, processor_id: str, *, revision: int) -> Dict[str, Any]:
        """Delete a processor by ID."""

        params = {"version": revision}
        result = await self._request(
            "DELETE",
            f"/nifi-api/processors/{processor_id}",
            params=params,
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response deleting processor")
        return result

    async def create_connection(
        self,
        parent_group_id: str,
        source_id: str,
        source_type: str,
        destination_id: str,
        destination_type: str,
        *,
        name: str = "",
        relationships: Optional[List[str]] = None,
        back_pressure_object_threshold: Optional[int] = None,
        back_pressure_data_size_threshold: Optional[str] = None,
        flow_file_expiration: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a connection between NiFi components."""

        component: Dict[str, Any] = {
            "parentGroupId": parent_group_id,
            "name": name,
            "source": {"id": source_id, "type": source_type},
            "destination": {"id": destination_id, "type": destination_type},
            "selectedRelationships": relationships or ["success"],
        }
        if back_pressure_object_threshold is not None:
            component["backPressureObjectThreshold"] = back_pressure_object_threshold
        if back_pressure_data_size_threshold is not None:
            component["backPressureDataSizeThreshold"] = back_pressure_data_size_threshold
        if flow_file_expiration is not None:
            component["flowFileExpiration"] = flow_file_expiration

        payload = {
            "revision": {"version": 0},
            "component": component,
        }

        result = await self._request(
            "POST",
            f"/nifi-api/process-groups/{parent_group_id}/connections",
            json=payload,
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response creating connection")
        return result

    async def delete_connection(self, connection_id: str, *, revision: int) -> Dict[str, Any]:
        """Delete a connection by ID."""

        params = {"version": revision}
        result = await self._request(
            "DELETE",
            f"/nifi-api/connections/{connection_id}",
            params=params,
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response deleting connection")
        return result

    async def import_from_registry(
        self,
        parent_group_id: str,
        flow_snapshot: Dict[str, Any],
        position: Dict[str, float] = None,
        group_name: str = None,
    ) -> Dict[str, Any]:
        """Import a process group from the NiFi registry using flow snapshot."""

        if position is None:
            position = {"x": 0.0, "y": 0.0}

        # Extract group name from flow snapshot if not provided
        if group_name is None:
            group_name = (flow_snapshot.get("flowContents", {}).get("name") or
                         flow_snapshot.get("flow", {}).get("name") or
                         "Imported Flow")

        payload = {
            "revisionDTO": {"version": 0},
            "flowSnapshot": flow_snapshot,
            "positionDTO": position,
            "groupName": group_name
        }

        result = await self._request(
            "POST",
            f"/nifi-api/process-groups/{parent_group_id}/process-groups/import",
            json=payload,
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response importing process group from registry")
        return result

    async def health_check(self) -> bool:
        """Simple health check."""

        try:
            await self.get_root_process_group()
            return True
        except NiFiClientError as exc:
            log.error("NiFi health check failed: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            log.exception("Unexpected error during NiFi health check: %s", exc)
        return False

    # Additional Process Group Operations
    async def start_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Start all processors in a process group."""
        
        payload = {
            "id": process_group_id,
            "state": "RUNNING"
        }
        
        result = await self._request("PUT", f"/nifi-api/flow/process-groups/{process_group_id}", json=payload)
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response starting process group")
        return result

    async def stop_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Stop all processors in a process group."""
        
        payload = {
            "id": process_group_id,
            "state": "STOPPED"
        }
        
        result = await self._request("PUT", f"/nifi-api/flow/process-groups/{process_group_id}", json=payload)
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response stopping process group")
        return result

    async def delete_process_group(self, process_group_id: str, revision: int) -> Dict[str, Any]:
        """Delete a process group."""
        
        params = {"version": revision}
        result = await self._request("DELETE", f"/nifi-api/process-groups/{process_group_id}", params=params)
        return result

    async def update_parameter_context(self, context_id: str, parameters: dict, revision: int) -> Dict[str, Any]:
        """Update parameter context parameters."""
        
        param_list = []
        for name, value in parameters.items():
            param_list.append({
                "parameter": {
                    "name": name,
                    "value": str(value),
                    "sensitive": False
                }
            })
        
        payload = {
            "revision": {"version": revision},
            "component": {
                "id": context_id,
                "parameters": param_list
            }
        }
        
        result = await self._request("PUT", f"/nifi-api/parameter-contexts/{context_id}", json=payload)
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response updating parameter context")
        return result

    async def get_parameter_context(self, context_id: str) -> Dict[str, Any]:
        """Get parameter context by ID."""
        
        result = await self._request("GET", f"/nifi-api/parameter-contexts/{context_id}")
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response getting parameter context")
        return result

    async def set_parameter_context_for_process_group(self, process_group_id: str, parameter_context_id: str, revision: int) -> Dict[str, Any]:
        """Associate a parameter context with a process group."""

        payload = {
            "revision": {"version": revision},
            "component": {
                "id": process_group_id,
                "parameterContext": {
                    "id": parameter_context_id
                }
            }
        }

        result = await self._request("PUT", f"/nifi-api/process-groups/{process_group_id}", json=payload)
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response setting parameter context")
        return result

    async def create_registry_client(self, name: str, url: str, description: str = "") -> Dict[str, Any]:
        """Create a Registry client in NiFi."""

        payload = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "description": description,
                "properties": {
                    "url": url
                },
                "type": "org.apache.nifi.registry.flow.NifiRegistryFlowRegistryClient"
            }
        }

        result = await self._request("POST", "/nifi-api/controller/registry-clients", json=payload)
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response creating registry client")
        return result

    async def list_registry_clients(self) -> List[Dict[str, Any]]:
        """List all Registry clients in NiFi."""

        result = await self._request("GET", "/nifi-api/controller/registry-clients")
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response listing registry clients")
        return result.get("registries", [])
