"""V1 API router configuration."""

from fastapi import APIRouter

from .flows.flows import router as flows_router
from .flows.deployments import router as deployments_router
from .flows.executions import router as executions_router
from .flows.simple_executions import router as simple_executions_router
from .flows.versions import router as versions_router
from .templates.templates import router as templates_router
from .registry.buckets import router as buckets_router
from .registry.flows import router as registry_flows_router, general_router as registry_flows_general_router

# Create the main v1 router
v1_router = APIRouter(prefix="/api/v1")

# Include all sub-routers
v1_router.include_router(flows_router)
v1_router.include_router(deployments_router)
v1_router.include_router(executions_router)
v1_router.include_router(simple_executions_router)
v1_router.include_router(versions_router)
v1_router.include_router(templates_router)
v1_router.include_router(buckets_router)
v1_router.include_router(registry_flows_router)
v1_router.include_router(registry_flows_general_router)