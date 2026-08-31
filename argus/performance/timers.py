"""Timing and profiling infrastructure for performance measurement."""

import functools
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional

from argus.performance.models import (
    LatencyMeasurement,
    MeasurementType,
    PerformanceMeasurement,
)


class Timer:
    """High-resolution timer using monotonic clock."""

    def __init__(self):
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    def start(self) -> None:
        """Start the timer."""
        self._start_time = time.monotonic()
        self._end_time = None

    def stop(self) -> float:
        """Stop the timer and return elapsed seconds."""
        self._end_time = time.monotonic()
        return self.elapsed

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self._start_time is None:
            return 0.0
        end = self._end_time if self._end_time is not None else time.monotonic()
        return end - self._start_time

    def reset(self) -> None:
        """Reset the timer."""
        self._start_time = None
        self._end_time = None


@contextmanager
def timed_operation(
    operation_type: str = "",
    run_id: Optional[str] = None,
    capability_id: Optional[str] = None,
    provider_id: Optional[str] = None,
):
    """Context manager for timing an operation."""
    measurement = LatencyMeasurement(
        operation_type=operation_type,
        run_id=run_id,
        capability_id=capability_id,
        provider_id=provider_id,
    )
    timer = Timer()
    timer.start()
    try:
        yield measurement
    finally:
        measurement.duration_seconds = timer.stop()
        measurement.execution_time_seconds = measurement.duration_seconds


def instrument(
    operation_type: str = "",
    capability_id: Optional[str] = None,
    provider_id: Optional[str] = None,
):
    """Decorator for instrumenting function execution time."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            with timed_operation(
                operation_type=operation_type or func.__name__,
                capability_id=capability_id,
                provider_id=provider_id,
            ) as measurement:
                result = func(*args, **kwargs)
                return result
        return wrapper
    return decorator


class Profiler:
    """Profiler for collecting performance measurements."""

    def __init__(self):
        self._measurements: List[PerformanceMeasurement] = []
        self._active_timers: Dict[str, Timer] = {}

    def start_measurement(
        self,
        measurement_id: str,
        measurement_type: MeasurementType = MeasurementType.LATENCY,
        run_id: Optional[str] = None,
        capability_id: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> Timer:
        """Start a named measurement."""
        timer = Timer()
        timer.start()
        self._active_timers[measurement_id] = timer
        return timer

    def stop_measurement(
        self,
        measurement_id: str,
        unit: str = "seconds",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[PerformanceMeasurement]:
        """Stop a named measurement and record it."""
        timer = self._active_timers.pop(measurement_id, None)
        if timer is None:
            return None

        duration = timer.stop()
        measurement = PerformanceMeasurement(
            measurement_id=measurement_id,
            value=duration,
            unit=unit,
            metadata=metadata or {},
        )
        self._measurements.append(measurement)
        return measurement

    def record_measurement(
        self,
        measurement_type: MeasurementType,
        value: float,
        unit: str = "seconds",
        run_id: Optional[str] = None,
        capability_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PerformanceMeasurement:
        """Record a measurement directly."""
        measurement = PerformanceMeasurement(
            measurement_type=measurement_type,
            value=value,
            unit=unit,
            run_id=run_id,
            capability_id=capability_id,
            provider_id=provider_id,
            metadata=metadata or {},
        )
        self._measurements.append(measurement)
        return measurement

    def get_measurements(
        self,
        measurement_type: Optional[MeasurementType] = None,
    ) -> List[PerformanceMeasurement]:
        """Get all measurements, optionally filtered by type."""
        if measurement_type is None:
            return self._measurements.copy()
        return [m for m in self._measurements if m.measurement_type == measurement_type]

    def clear(self) -> None:
        """Clear all measurements."""
        self._measurements.clear()
        self._active_timers.clear()

    @property
    def measurement_count(self) -> int:
        """Get the number of measurements recorded."""
        return len(self._measurements)
