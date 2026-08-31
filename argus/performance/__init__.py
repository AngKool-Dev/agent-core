"""ARGUS Performance Package - Concurrency, resource control, and regression protection."""

from argus.performance.models import (
    BackpressureAction,
    ConcurrencyMeasurement,
    ConcurrencyMode,
    ConcurrencyPolicy,
    ContentionMeasurement,
    LatencyMeasurement,
    MeasurementType,
    PerformanceBudget,
    PerformanceMeasurement,
    PerformanceReport,
    PerformanceSnapshot,
    ResourceBudget,
    ResourceMeasurement,
    ResourceType,
    ThroughputMeasurement,
    QueueMeasurement,
)
from argus.performance.timers import Profiler, Timer, instrument, timed_operation
from argus.performance.resources import ResourceController, ResourceError
from argus.performance.scheduler import BoundedScheduler, SchedulerError, TaskHandle
from argus.performance.backpressure import BackpressureController, BackpressureError
from argus.performance.isolation import ExecutionContext, IsolationError, IsolationManager
from argus.performance.contention import (
    ContentionDetector,
    ContentionError,
    DeadlockError,
    LockWrapper,
)
from argus.performance.telemetry import TelemetryCollector
from argus.performance.regression import PerformanceRegressionDetector
from argus.performance.reporting import PerformanceReporter

__all__ = [
    # Models
    "BackpressureAction",
    "ConcurrencyMeasurement",
    "ConcurrencyMode",
    "ConcurrencyPolicy",
    "ContentionMeasurement",
    "LatencyMeasurement",
    "MeasurementType",
    "PerformanceBudget",
    "PerformanceMeasurement",
    "PerformanceReport",
    "PerformanceSnapshot",
    "ResourceBudget",
    "ResourceMeasurement",
    "ResourceType",
    "ThroughputMeasurement",
    "QueueMeasurement",
    # Timers
    "Profiler",
    "Timer",
    "instrument",
    "timed_operation",
    # Resources
    "ResourceController",
    "ResourceError",
    # Scheduler
    "BoundedScheduler",
    "SchedulerError",
    "TaskHandle",
    # Backpressure
    "BackpressureController",
    "BackpressureError",
    # Isolation
    "ExecutionContext",
    "IsolationError",
    "IsolationManager",
    # Contention
    "ContentionDetector",
    "ContentionError",
    "DeadlockError",
    "LockWrapper",
    # Telemetry
    "TelemetryCollector",
    # Regression
    "PerformanceRegressionDetector",
    # Reporting
    "PerformanceReporter",
]
