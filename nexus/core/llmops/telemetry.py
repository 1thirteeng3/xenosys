"""
XenoSys LLMOps - Telemetry Module
OpenTelemetry integration for observability.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# Telemetry Types
# ============================================================================

@dataclass
class Span:
    """A trace span."""
    id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str = ""
    parent_id: Optional[str] = None
    name: str = ""
    service: str = "xenosys"
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status: str = "ok"  # ok, error
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: list[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Metric:
    """A metric data point."""
    name: str = ""
    value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = field(default_factory=dict)


# ============================================================================
# Telemetry Exporter (OpenTelemetry compatible)
# ============================================================================

class TelemetryExporter:
    """
    Telemetry exporter with OpenTelemetry compatibility.
    
    Provides:
    - Trace collection
    - Metric collection
    - Export to Jaeger/Grafana
    - Span decoration
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.service_name = self.config.get("service_name", "xenosys")
        
        # Exporters
        self.jaeger_endpoint = self.config.get("jaeger_endpoint", "http://localhost:14268")
        self.prometheus_port = self.config.get("prometheus_port", 9090)
        
        # In-memory storage for demo
        self._spans: list[Span] = []
        self._metrics: list[Metric] = []
        self._lock = asyncio.Lock()
    
    # =========================================================================
    # Tracing
    # =========================================================================
    
    async def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Start a new span."""
        span = Span(
            name=name,
            trace_id=trace_id or str(uuid4()),
            parent_id=parent_id,
            service=self.service_name,
            attributes=attributes or {},
        )
        
        async with self._lock:
            self._spans.append(span)
        
        return span
    
    async def end_span(
        self,
        span: Span,
        status: str = "ok",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """End a span."""
        span.end_time = datetime.utcnow()
        span.status = status
        
        if attributes:
            span.attributes.update(attributes)
        
        # Export to Jaeger
        await self._export_span(span)
    
    async def add_event(
        self,
        span: Span,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an event to a span."""
        span.events.append({
            "name": name,
            "timestamp": datetime.utcnow().isoformat(),
            "attributes": attributes or {},
        })
    
    async def record_exception(
        self,
        span: Span,
        exception: Exception,
    ) -> None:
        """Record an exception in a span."""
        span.status = "error"
        span.attributes["error"] = True
        span.attributes["error.message"] = str(exception)
        span.attributes["error.stack"] = getattr(exception, "__traceback__", None)
    
    # =========================================================================
    # Metrics
    # =========================================================================
    
    async def record_metric(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a metric."""
        metric = Metric(
            name=name,
            value=value,
            labels=labels or {},
        )
        
        async with self._lock:
            self._metrics.append(metric)
    
    async def increment_counter(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment a counter metric."""
        await self.record_metric(name, 1.0, labels)
    
    async def record_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a gauge metric."""
        await self.record_metric(name, value, labels)
    
    # =========================================================================
    # Export
    # =========================================================================
    
    async def _export_span(self, span: Span) -> None:
        """Export span to Jaeger."""
        # In production, would send to Jaeger collector
        # For demo, just log
        logger.debug(f"Exported span: {span.name} ({span.trace_id})")
    
    async def flush(self) -> None:
        """Flush pending exports."""
        # Export all pending spans
        logger.info("Flushed telemetry")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get telemetry statistics."""
        return {
            "spans_count": len(self._spans),
            "metrics_count": len(self._metrics),
            "service_name": self.service_name,
        }


# ============================================================================
# Decorators for Tracing
# ============================================================================

def trace(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """Decorator to trace a function."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            exporter = get_telemetry_exporter()
            
            span = await exporter.start_span(
                name=name,
                attributes=attributes,
            )
            
            try:
                result = await func(*args, **kwargs)
                await exporter.end_span(span)
                return result
            except Exception as e:
                await exporter.record_exception(span, e)
                await exporter.end_span(span, status="error")
                raise
        
        return wrapper
    return decorator


# Global exporter instance
_exporter: Optional[TelemetryExporter] = None


def get_telemetry_exporter(config: Optional[Dict[str, Any]] = None) -> TelemetryExporter:
    """Get or create global telemetry exporter."""
    global _exporter
    if _exporter is None:
        _exporter = TelemetryExporter(config)
    return _exporter