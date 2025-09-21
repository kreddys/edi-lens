# FILE: backend/src/core/metrics.py

"""
Prometheus metrics collection for EDI Lens backend service.
"""

import logging
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from fastapi.routing import APIRoute
from typing import Callable
import time

logger = logging.getLogger(__name__)

# Create a custom registry to avoid conflicts
registry = CollectorRegistry()

# HTTP metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status_code'],
    registry=registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    registry=registry
)

http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests currently being processed',
    registry=registry
)

# EDI-specific metrics
edi_documents_processed_total = Counter(
    'edi_documents_processed_total',
    'Total number of EDI documents processed',
    ['tenant', 'document_type', 'status'],
    registry=registry
)

edi_validation_duration_seconds = Histogram(
    'edi_validation_duration_seconds',
    'EDI validation duration in seconds',
    ['document_type'],
    registry=registry
)

active_workflows = Gauge(
    'active_workflows',
    'Number of currently active workflows',
    registry=registry
)

database_connections = Gauge(
    'database_connections_active',
    'Number of active database connections',
    registry=registry
)

# Application info
app_info = Gauge(
    'app_info',
    'Application information',
    ['version', 'environment'],
    registry=registry
)


class PrometheusMiddleware:
    """FastAPI middleware for collecting HTTP metrics"""
    
    def __init__(self, app_name: str = "edi-lens-backend"):
        self.app_name = app_name
    
    async def __call__(self, request: Request, call_next: Callable):
        start_time = time.time()
        
        # Get route pattern (more stable than full path for grouping)
        route_pattern = request.url.path
        if hasattr(request, 'route') and hasattr(request.route, 'path'):
            route_pattern = request.route.path
        
        # Increment in-progress gauge
        http_requests_in_progress.inc()
        
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception as e:
            status_code = "500"
            logger.error(f"Request failed: {e}")
            raise
        finally:
            # Decrement in-progress gauge
            http_requests_in_progress.dec()
            
            # Record metrics
            duration = time.time() - start_time
            method = request.method
            
            http_requests_total.labels(
                method=method,
                endpoint=route_pattern,
                status_code=status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method,
                endpoint=route_pattern
            ).observe(duration)
        
        return response


def get_metrics_response() -> Response:
    """Generate Prometheus metrics response"""
    try:
        metrics_data = generate_latest(registry)
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return Response(
            content=f"Error generating metrics: {e}",
            status_code=500,
            media_type="text/plain"
        )


def init_app_metrics(version: str = "unknown", environment: str = "development"):
    """Initialize application-level metrics"""
    app_info.labels(version=version, environment=environment).set(1)
    logger.info(f"Initialized Prometheus metrics for {environment} environment, version {version}")


def record_edi_document_processed(tenant: str, document_type: str, status: str):
    """Record EDI document processing event"""
    edi_documents_processed_total.labels(
        tenant=tenant,
        document_type=document_type,
        status=status
    ).inc()


def record_validation_duration(document_type: str, duration_seconds: float):
    """Record EDI validation duration"""
    edi_validation_duration_seconds.labels(
        document_type=document_type
    ).observe(duration_seconds)


def set_active_workflows(count: int):
    """Update active workflows count"""
    active_workflows.set(count)


def set_database_connections(count: int):
    """Update database connections count"""
    database_connections.set(count)