"""
Observability Layer for Local Assistant
Provides cost tracking, metrics, traces, and structured logging
"""

from observability.costs import CostTracker, CostWindow, CostLimitExceeded
from observability.metrics import MetricsCollector, get_metrics_collector
from observability.traces import TraceManager, get_trace_manager
from observability.logs import setup_logging, get_logger

__all__ = [
    "CostTracker",
    "CostWindow",
    "CostLimitExceeded",
    "MetricsCollector",
    "get_metrics_collector",
    "TraceManager",
    "get_trace_manager",
    "setup_logging",
    "get_logger",
]
