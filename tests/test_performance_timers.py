"""Tests for ARGUS Performance timers and profiler."""

import time

import pytest

from argus.performance.timers import (
    Profiler,
    Timer,
    instrument,
    timed_operation,
)
from argus.performance.models import MeasurementType


class TestTimer:
    """Tests for Timer."""

    def test_start_and_stop(self):
        timer = Timer()
        timer.start()
        time.sleep(0.05)
        elapsed = timer.stop()
        assert elapsed > 0

    def test_elapsed_while_running(self):
        timer = Timer()
        timer.start()
        time.sleep(0.05)
        elapsed = timer.elapsed
        assert elapsed > 0

    def test_reset(self):
        timer = Timer()
        timer.start()
        time.sleep(0.01)
        timer.reset()
        assert timer.elapsed == 0.0

    def test_multiple_starts(self):
        timer = Timer()
        timer.start()
        time.sleep(0.05)
        timer.start()  # Restart - this resets the timer
        time.sleep(0.01)
        elapsed_after_restart = timer.elapsed
        # After restart, elapsed should only measure from restart
        assert elapsed_after_restart < 0.03  # Should be ~0.01, not ~0.06


class TestTimedOperation:
    """Tests for timed_operation context manager."""

    def test_basic_timing(self):
        with timed_operation("test_op") as measurement:
            time.sleep(0.05)
        assert measurement.duration_seconds > 0
        assert measurement.operation_type == "test_op"

    def test_with_run_id(self):
        with timed_operation("test_op", run_id="run-001") as measurement:
            time.sleep(0.01)
        assert measurement.run_id == "run-001"

    def test_with_capability_id(self):
        with timed_operation("test_op", capability_id="cap-001") as measurement:
            time.sleep(0.01)
        assert measurement.capability_id == "cap-001"

    def test_with_provider_id(self):
        with timed_operation("test_op", provider_id="prov-001") as measurement:
            time.sleep(0.01)
        assert measurement.provider_id == "prov-001"


class TestInstrument:
    """Tests for instrument decorator."""

    def test_basic_instrumentation(self):
        @instrument("test_func")
        def slow_func():
            time.sleep(0.01)
            return 42

        result = slow_func()
        assert result == 42

    def test_instrument_with_capability(self):
        @instrument("test_func", capability_id="cap-001")
        def slow_func():
            time.sleep(0.01)
            return 42

        result = slow_func()
        assert result == 42


class TestProfiler:
    """Tests for Profiler."""

    def setup_method(self):
        self.profiler = Profiler()

    def test_record_measurement(self):
        measurement = self.profiler.record_measurement(
            measurement_type=MeasurementType.LATENCY,
            value=1.5,
        )
        assert measurement.value == 1.5
        assert measurement.measurement_type == MeasurementType.LATENCY

    def test_get_measurements(self):
        self.profiler.record_measurement(
            measurement_type=MeasurementType.LATENCY,
            value=1.0,
        )
        self.profiler.record_measurement(
            measurement_type=MeasurementType.THROUGHPUT,
            value=5.0,
        )
        all_measurements = self.profiler.get_measurements()
        assert len(all_measurements) == 2

    def test_get_measurements_filtered(self):
        self.profiler.record_measurement(
            measurement_type=MeasurementType.LATENCY,
            value=1.0,
        )
        self.profiler.record_measurement(
            measurement_type=MeasurementType.THROUGHPUT,
            value=5.0,
        )
        latency_measurements = self.profiler.get_measurements(MeasurementType.LATENCY)
        assert len(latency_measurements) == 1
        assert latency_measurements[0].measurement_type == MeasurementType.LATENCY

    def test_clear(self):
        self.profiler.record_measurement(
            measurement_type=MeasurementType.LATENCY,
            value=1.0,
        )
        self.profiler.clear()
        assert self.profiler.measurement_count == 0

    def test_measurement_count(self):
        assert self.profiler.measurement_count == 0
        self.profiler.record_measurement(
            measurement_type=MeasurementType.LATENCY,
            value=1.0,
        )
        assert self.profiler.measurement_count == 1

    def test_start_and_stop_measurement(self):
        self.profiler.start_measurement("test-measurement")
        time.sleep(0.05)
        measurement = self.profiler.stop_measurement("test-measurement")
        assert measurement is not None
        assert measurement.value > 0

    def test_stop_nonexistent_measurement(self):
        measurement = self.profiler.stop_measurement("nonexistent")
        assert measurement is None

    def test_measurement_with_metadata(self):
        measurement = self.profiler.record_measurement(
            measurement_type=MeasurementType.LATENCY,
            value=1.5,
            metadata={"operation": "test"},
        )
        assert measurement.metadata["operation"] == "test"
