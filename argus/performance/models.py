"""Performance, concurrency, and resource control data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MeasurementType(Enum):
    """Types of performance measurements."""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    RESOURCE = "resource"
    CONCURRENCY = "concurrency"
    QUEUE = "queue"
    CONTENTION = "contention"


class ResourceType(Enum):
    """Types of resources that can be budgeted."""
    CONCURRENT_RUNS = "concurrent_runs"
    CONCURRENT_CAPABILITIES = "concurrent_capabilities"
    CONCURRENT_PROVIDER_CALLS = "concurrent_provider_calls"
    TOOL_CALLS = "tool_calls"
    QUEUED_OPERATIONS = "queued_operations"
    WALL_CLOCK_TIME = "wall_clock_time"
    TOKENS = "tokens"
    RECOVERY_ATTEMPTS = "recovery_attempts"
    MCP_CALLS = "mcp_calls"


class BackpressureAction(Enum):
    """Actions to take when capacity is exhausted."""
    ACCEPT = "accept"
    QUEUE = "queue"
    THROTTLE = "throttle"
    REJECT = "reject"
    CANCEL = "cancel"


class ConcurrencyMode(Enum):
    """Concurrency execution modes."""
    SERIAL = "serial"
    BOUNDED = "bounded_concurrent"
    UNBOUNDED = "unbounded"


@dataclass
class PerformanceMeasurement:
    """A single performance measurement."""
    measurement_id: str = ""
    measurement_type: MeasurementType = MeasurementType.LATENCY
    value: float = 0.0
    unit: str = "seconds"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: Optional[str] = None
    session_id: Optional[str] = None
    operation_id: Optional[str] = None
    capability_id: Optional[str] = None
    provider_id: Optional[str] = None
    event_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LatencyMeasurement:
    """Latency measurement for an operation."""
    operation_type: str = ""
    duration_seconds: float = 0.0
    wait_time_seconds: float = 0.0
    execution_time_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: Optional[str] = None
    capability_id: Optional[str] = None
    provider_id: Optional[str] = None


@dataclass
class ResourceMeasurement:
    """Resource usage measurement."""
    resource_type: ResourceType = ResourceType.CONCURRENT_RUNS
    current_usage: int = 0
    max_usage: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConcurrencyMeasurement:
    """Concurrency level measurement."""
    active_operations: int = 0
    queued_operations: int = 0
    completed_operations: int = 0
    max_concurrency: int = 1
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ThroughputMeasurement:
    """Throughput measurement."""
    operations_per_second: float = 0.0
    window_seconds: float = 1.0
    total_operations: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class QueueMeasurement:
    """Queue state measurement."""
    queue_size: int = 0
    max_size: int = 0
    wait_time_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ContentionMeasurement:
    """Lock contention measurement."""
    lock_name: str = ""
    wait_count: int = 0
    wait_time_seconds: float = 0.0
    contention_level: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PerformanceBudget:
    """Budget for performance-related resources."""
    max_concurrent_runs: int = 1
    max_concurrent_capabilities: int = 4
    max_concurrent_provider_calls: int = 2
    max_tool_calls: int = 50
    max_queued_operations: int = 10
    max_wall_clock_seconds: int = 3600
    max_tokens: int = 100000
    max_recovery_attempts: int = 3
    max_mcp_calls: int = 5


@dataclass
class ResourceBudget:
    """Current resource budget usage."""
    current_concurrent_runs: int = 0
    current_concurrent_capabilities: int = 0
    current_concurrent_provider_calls: int = 0
    current_tool_calls: int = 0
    current_queued_operations: int = 0
    current_tokens: int = 0
    current_recovery_attempts: int = 0
    current_mcp_calls: int = 0
    limits: PerformanceBudget = field(default_factory=PerformanceBudget)

    def is_exhausted(self, resource_type: ResourceType) -> bool:
        """Check if a specific resource is exhausted."""
        check_map = {
            ResourceType.CONCURRENT_RUNS: (
                self.current_concurrent_runs >= self.limits.max_concurrent_runs
            ),
            ResourceType.CONCURRENT_CAPABILITIES: (
                self.current_concurrent_capabilities >= self.limits.max_concurrent_capabilities
            ),
            ResourceType.CONCURRENT_PROVIDER_CALLS: (
                self.current_concurrent_provider_calls >= self.limits.max_concurrent_provider_calls
            ),
            ResourceType.TOOL_CALLS: (
                self.current_tool_calls >= self.limits.max_tool_calls
            ),
            ResourceType.QUEUED_OPERATIONS: (
                self.current_queued_operations >= self.limits.max_queued_operations
            ),
            ResourceType.TOKENS: (
                self.current_tokens >= self.limits.max_tokens
            ),
            ResourceType.RECOVERY_ATTEMPTS: (
                self.current_recovery_attempts >= self.limits.max_recovery_attempts
            ),
            ResourceType.MCP_CALLS: (
                self.current_mcp_calls >= self.limits.max_mcp_calls
            ),
        }
        return check_map.get(resource_type, False)


@dataclass
class ConcurrencyPolicy:
    """Policy for concurrent execution."""
    mode: ConcurrencyMode = ConcurrencyMode.BOUNDED
    max_concurrency: int = 4
    max_queue_size: int = 10
    default_timeout_seconds: float = 300.0
    enable_priority: bool = False
    fairness: str = "fifo"
    isolation_level: str = "full"


@dataclass
class PerformanceSnapshot:
    """A point-in-time snapshot of performance metrics."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    active_operations: int = 0
    queued_operations: int = 0
    completed_operations: int = 0
    failed_operations: int = 0
    average_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    throughput: float = 0.0
    resource_usage: Dict[str, int] = field(default_factory=dict)
    contention_events: int = 0


@dataclass
class PerformanceReport:
    """Aggregated performance report."""
    report_id: str = ""
    run_id: Optional[str] = None
    start_time: str = ""
    end_time: str = ""
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    cancelled_operations: int = 0
    timeout_operations: int = 0
    average_latency: float = 0.0
    median_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    throughput: float = 0.0
    peak_concurrency: int = 0
    resource_exhaustion_events: int = 0
    contention_events: int = 0
    measurements: List[PerformanceMeasurement] = field(default_factory=list)
