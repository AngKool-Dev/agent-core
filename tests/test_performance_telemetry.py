"""Tests for ARGUS Performance telemetry and regression detection."""

import pytest

from argus.performance.telemetry import TelemetryCollector
from argus.performance.regression import PerformanceRegressionDetector
from argus.performance.models import (
    MeasurementType,
    PerformanceMeasurement,
    ResourceType,
)


class TestTelemetryCollector:
    """Tests for TelemetryCollector."""

    def setup_method(self):
        self.telemetry = TelemetryCollector()

    def test_start_and_stop(self):
        self.telemetry.start()
        assert self.telemetry.is_active is True
        self.telemetry.stop()
        assert self.telemetry.is_active is False

    def test_record_latency(self):
        measurement = self.telemetry.record_latency("model_call", 1.5, run_id="run-001")
        assert measurement.value == 1.5
        assert measurement.run_id == "run-001"

    def test_record_throughput(self):
        measurement = self.telemetry.record_throughput(5.0, 10)
        assert measurement.value == 5.0

    def test_record_resource(self):
        measurement = self.telemetry.record_resource("concurrent_runs", 3, 5)
        assert measurement.current_usage == 3
        assert measurement.max_usage == 5

    def test_record_concurrency(self):
        measurement = self.telemetry.record_concurrency(3, 2, 10, 5)
        assert measurement.active_operations == 3
        assert measurement.queued_operations == 2
        assert measurement.completed_operations == 10

    def test_record_queue(self):
        measurement = self.telemetry.record_queue(3, 10, 0.5)
        assert measurement.queue_size == 3
        assert measurement.max_size == 10
        assert measurement.wait_time_seconds == 0.5

    def test_record_contention(self):
        measurement = self.telemetry.record_contention("lock-1", 5, 1.0)
        assert measurement.lock_name == "lock-1"
        assert measurement.wait_count == 5
        assert measurement.wait_time_seconds == 1.0

    def test_get_all_measurements(self):
        self.telemetry.record_latency("op1", 1.0)
        self.telemetry.record_latency("op2", 2.0)
        measurements = self.telemetry.get_all_measurements()
        assert len(measurements) == 2

    def test_get_snapshots(self):
        self.telemetry.record_concurrency(1, 0, 5, 4)
        snapshots = self.telemetry.get_snapshots()
        assert len(snapshots) == 1
        assert snapshots[0]["type"] == "concurrency"

    def test_clear(self):
        self.telemetry.record_latency("op1", 1.0)
        self.telemetry.record_concurrency(1, 0, 5, 4)
        self.telemetry.clear()
        assert len(self.telemetry.get_all_measurements()) == 0
        assert len(self.telemetry.get_snapshots()) == 0


class TestPerformanceRegressionDetector:
    """Tests for PerformanceRegressionDetector."""

    def setup_method(self):
        self.detector = PerformanceRegressionDetector(
            latency_threshold=1.5,
            throughput_threshold=0.7,
            error_rate_threshold=0.1,
        )

    def test_latency_regression_detected(self):
        baseline = [1.0, 1.1, 0.9, 1.0]
        current = [2.0, 2.1, 1.9, 2.0]
        result = self.detector.check_latency_regression(baseline, current)
        assert result["is_regression"] is True

    def test_latency_no_regression(self):
        baseline = [1.0, 1.1, 0.9, 1.0]
        current = [1.1, 1.2, 1.0, 1.1]
        result = self.detector.check_latency_regression(baseline, current)
        assert result["is_regression"] is False

    def test_latency_insufficient_data(self):
        result = self.detector.check_latency_regression([], [1.0])
        assert result["is_regression"] is False
        assert result["reason"] == "insufficient_data"

    def test_throughput_regression_detected(self):
        baseline = [10.0, 11.0, 9.0, 10.0]
        current = [5.0, 4.0, 6.0, 5.0]
        result = self.detector.check_throughput_regression(baseline, current)
        assert result["is_regression"] is True

    def test_throughput_no_regression(self):
        baseline = [10.0, 11.0, 9.0, 10.0]
        current = [9.0, 10.0, 8.0, 9.0]
        result = self.detector.check_throughput_regression(baseline, current)
        assert result["is_regression"] is False

    def test_error_rate_regression_detected(self):
        result = self.detector.check_error_rate_regression(1, 100, 15, 100)
        assert result["is_regression"] is True

    def test_error_rate_no_regression(self):
        result = self.detector.check_error_rate_regression(5, 100, 6, 100)
        assert result["is_regression"] is False

    def test_analyze_measurements(self):
        baseline = [
            PerformanceMeasurement(measurement_type=MeasurementType.LATENCY, value=1.0),
            PerformanceMeasurement(measurement_type=MeasurementType.LATENCY, value=1.1),
        ]
        current = [
            PerformanceMeasurement(measurement_type=MeasurementType.LATENCY, value=2.0),
            PerformanceMeasurement(measurement_type=MeasurementType.LATENCY, value=2.1),
        ]
        result = self.detector.analyze_measurements(baseline, current)
        assert "latency" in result
        assert "sample_size" in result
