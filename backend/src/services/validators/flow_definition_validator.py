"""NiFi-backed validator for VersionedFlow definitions before Registry storage."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple

from ...clients.nifi_client import NiFiClient
from ...core.logging import get_logger
from ..flow_deployment_executor import FlowDeploymentExecutor

log = get_logger(__name__)


def _hash_definition(flow_definition: Dict[str, Any], parameters: Optional[Dict[str, Any]]) -> str:
    """Stable hash for caching validations."""

    payload = {
        "flow_definition": flow_definition,
        "parameters": parameters or {},
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


class FlowDefinitionValidator:
    """Runs component-level deployment in cleanup mode to validate flow definitions."""

    def __init__(self, nifi_client: NiFiClient):
        self._executor = FlowDeploymentExecutor(nifi_client)
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._cache_ttl_seconds = 120.0

    async def validate(
        self,
        flow_definition: Dict[str, Any],
        *,
        parameters: Optional[Dict[str, Any]] = None,
        skip_cache: bool = False,
    ) -> Dict[str, Any]:
        """Return validation report. Raises FlowServiceError when NiFi call fails."""

        cache_key = _hash_definition(flow_definition, parameters)
        now = time.time()

        if not skip_cache:
            cached = self._cache.get(cache_key)
            if cached and now - cached[0] < self._cache_ttl_seconds:
                log.debug("Reusing cached validation result for flow definition")
                return cached[1]

        result = await self._executor.execute(
            flow_definition,
            parameters=parameters or {},
            parent_group_id="root",
            cleanup_on_success=True,
            create_connections=False,
        )
        report = {
            "issues": result.get("failures", []),
            "summary": result.get("summary", {}),
            "has_errors": not result.get("success", False),
        }
        self._cache[cache_key] = (now, report)
        return report
