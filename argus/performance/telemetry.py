"""Performance telemetry collection."""

import threading
import time
from typing import Any, Dict, List, Optional

from argus.performance.models import (
    ConcurrencyMeasurement,
    ContentionMeasurement,
    PerformanceMeasurement,
    QueueMeasurement,
    ResourceMeasurement,
    ThroughputMeasurement,
    MeasurementType,
)
from argus.performance.timers import Profiler


class TelemetryCollector:
    """Collects performance telemetry."""

    def __init__(self):
        self._profiler = Profiler()
        self._lock = threading.Lock()
        self._snapshots: List[Dict[str, Any]] = []
        self._active = False

    def start(self) -> None:
        """Start telemetry collection."""
        with self._lock:
            self._active = True

    def stop(self) -> None:
        """Stop telemetry collection."""
        with self._lock:
            self._active = False

    @property
    def is_active(self) -> bool:
        """Check if telemetry is active."""
        return self._active

    def record_latency(
        self,
        operation_type: str,
        duration_seconds: float,
        run_id: Optional[str] = None,
    ) -> PerformanceMeasurement:
        """Record a latency measurement."""
        return self._profiler.record_measurement(
            measurement_type=MeasurementType.LATENCY,
            value=duration_seconds,
            unit="seconds",
            run_id=run_id,
            metadata={"operation_type": operation_type},
        )

    def record_throughput(
        self,
        operations_per_second: float,
        total_operations: int,
    ) -> PerformanceMeasurement:
        """Record a throughput measurement."""
        return self._profiler.record_measurement(
            measurement_type=MeasurementType.THROUGHPUT,
            value=operations_per_second,
            unit="ops/sec",
            metadata={"total_operations": total_operations},
        )

    def record_resource(
        self,
        resource_type: str,
        current: int,
        maximum: int,
    ) -> ResourceMeasurement:
        """Record a resource measurement."""
        measurement = ResourceMeasurement(
            current_usage=current,
            max_usage=maximum,
            metadata={"resource_type": resource_type},
        )
        with self._lock:
            self._snapshots.append({
                "type": "resource",
                "data": measurement,
                "timestamp": time.monotonic(),
            })
        return measurement

    def record_concurrency(
        self,
        active: int,
        queued: int,
        completed: int,
        max_concurrency: int,
    ) -> ConcurrencyMeasurement:
        """Record a concurrency measurement."""
        measurement = ConcurrencyMeasurement(
            active_operations=active,
            queued_operations=queued,
            completed_operations=completed,
            max_concurrency=max_concurrency,
        )
        with self._lock:
            self._snapshots.append({
                "type": "concurrency",
                "data": measurement,
                "timestamp": time.monotonic(),
            })
        return measurement

    def record_queue(
        self,
        queue_size: int,
        max_size: int,
        wait_time: float,
    ) -> QueueMeasurement:
        """Record a queue measurement."""
        measurement = QueueMeasurement(
            queue_size=queue_size,
            max_size=max_size,
            wait_time_seconds=wait_time,
        )
        with self._lock:
            self._snapshots.append({
                "type": "queue",
                "data": measurement,
                "timestamp": time.monotonic(),
            })
        return measurement

    def record_contention(
        self,
        lock_name: str,
        wait_count: int,
        wait_time: float,
    ) -> ContentionMeasurement:
        """Record a contention measurement."""
        measurement = ContentionMeasurement(
            lock_name=lock_name,
            wait_count=wait_count,
            wait_time_seconds=wait_time,
        )
        with self._lock:
            self._snapshots.append({
                "type": "contention",
                "data": measurement,
                "timestamp": time.monotonic(),
            })
        return measurement

    def get_all_measurements(self) -> List[PerformanceMeasurement]:
        """Get all measurements."""
        return self._profiler.get_measurements()

    def get_snapshots(self) -> List[Dict[str, Any]]:
        """Get all snapshots."""
        with self._lock:
            return list(self._snapshots)

    def clear(self) -> None:
        """Clear all telemetry data."""
        with self._lock:
            self._profiler.clear()
            self._snapshots.clear()
