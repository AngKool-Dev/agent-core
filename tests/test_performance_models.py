"""Tests for ARGUS Performance models."""

import pytest

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


class TestMeasurementType:
    """Tests for MeasurementType enum."""

    def test_all_types_exist(self):
        types = [t.value for t in MeasurementType]
        assert "latency" in types
        assert "throughput" in types
        assert "resource" in types
        assert "concurrency" in types
        assert "queue" in types
        assert "contention" in types


class TestResourceType:
    """Tests for ResourceType enum."""

    def test_all_types_exist(self):
        types = [t.value for t in ResourceType]
        assert "concurrent_runs" in types
        assert "concurrent_capabilities" in types
        assert "tool_calls" in types
        assert "tokens" in types
        assert "recovery_attempts" in types


class TestBackpressureAction:
    """Tests for BackpressureAction enum."""

    def test_all_actions_exist(self):
        actions = [a.value for a in BackpressureAction]
        assert "accept" in actions
        assert "queue" in actions
        assert "throttle" in actions
        assert "reject" in actions
        assert "cancel" in actions


class TestPerformanceMeasurement:
    """Tests for PerformanceMeasurement model."""

    def test_create_measurement(self):
        measurement = PerformanceMeasurement(
            measurement_type=MeasurementType.LATENCY,
            value=1.5,
            unit="seconds",
        )
        assert measurement.value == 1.5
        assert measurement.unit == "seconds"

    def test_measurement_with_correlation(self):
        measurement = PerformanceMeasurement(
            measurement_type=MeasurementType.LATENCY,
            value=2.0,
            run_id="run-001",
            session_id="session-001",
            operation_id="op-001",
            capability_id="cap-001",
            provider_id="prov-001",
        )
        assert measurement.run_id == "run-001"
        assert measurement.capability_id == "cap-001"


class TestLatencyMeasurement:
    """Tests for LatencyMeasurement model."""

    def test_create_measurement(self):
        measurement = LatencyMeasurement(
            operation_type="model_call",
            duration_seconds=1.5,
            wait_time_seconds=0.1,
            execution_time_seconds=1.4,
        )
        assert measurement.operation_type == "model_call"
        assert measurement.duration_seconds == 1.5
        assert measurement.wait_time_seconds == 0.1
        assert measurement.execution_time_seconds == 1.4


class TestResourceMeasurement:
    """Tests for ResourceMeasurement model."""

    def test_create_measurement(self):
        measurement = ResourceMeasurement(
            resource_type=ResourceType.CONCURRENT_RUNS,
            current_usage=3,
            max_usage=5,
        )
        assert measurement.current_usage == 3
        assert measurement.max_usage == 5


class TestConcurrencyMeasurement:
    """Tests for ConcurrencyMeasurement model."""

    def test_create_measurement(self):
        measurement = ConcurrencyMeasurement(
            active_operations=3,
            queued_operations=2,
            completed_operations=10,
            max_concurrency=5,
        )
        assert measurement.active_operations == 3
        assert measurement.queued_operations == 2
        assert measurement.completed_operations == 10
        assert measurement.max_concurrency == 5


class TestThroughputMeasurement:
    """Tests for ThroughputMeasurement model."""

    def test_create_measurement(self):
        measurement = ThroughputMeasurement(
            operations_per_second=5.0,
            window_seconds=1.0,
            total_operations=5,
        )
        assert measurement.operations_per_second == 5.0
        assert measurement.total_operations == 5


class TestQueueMeasurement:
    """Tests for QueueMeasurement model."""

    def test_create_measurement(self):
        measurement = QueueMeasurement(
            queue_size=3,
            max_size=10,
            wait_time_seconds=0.5,
        )
        assert measurement.queue_size == 3
        assert measurement.max_size == 10
        assert measurement.wait_time_seconds == 0.5


class TestContentionMeasurement:
    """Tests for ContentionMeasurement model."""

    def test_create_measurement(self):
        measurement = ContentionMeasurement(
            lock_name="test_lock",
            wait_count=5,
            wait_time_seconds=1.0,
            contention_level=0.5,
        )
        assert measurement.lock_name == "test_lock"
        assert measurement.wait_count == 5


class TestPerformanceBudget:
    """Tests for PerformanceBudget model."""

    def test_default_budget(self):
        budget = PerformanceBudget()
        assert budget.max_concurrent_runs == 1
        assert budget.max_concurrent_capabilities == 4
        assert budget.max_tool_calls == 50
        assert budget.max_tokens == 100000

    def test_custom_budget(self):
        budget = PerformanceBudget(
            max_concurrent_runs=5,
            max_tool_calls=100,
        )
        assert budget.max_concurrent_runs == 5
        assert budget.max_tool_calls == 100


class TestResourceBudget:
    """Tests for ResourceBudget model."""

    def test_is_exhausted(self):
        budget = PerformanceBudget(max_concurrent_runs=2)
        usage = ResourceBudget(
            limits=budget,
            current_concurrent_runs=2,
        )
        assert usage.is_exhausted(ResourceType.CONCURRENT_RUNS) is True

    def test_is_not_exhausted(self):
        budget = PerformanceBudget(max_concurrent_runs=5)
        usage = ResourceBudget(
            limits=budget,
            current_concurrent_runs=2,
        )
        assert usage.is_exhausted(ResourceType.CONCURRENT_RUNS) is False


class TestConcurrencyPolicy:
    """Tests for ConcurrencyPolicy model."""

    def test_default_policy(self):
        policy = ConcurrencyPolicy()
        assert policy.mode == ConcurrencyMode.BOUNDED
        assert policy.max_concurrency == 4
        assert policy.max_queue_size == 10

    def test_serial_policy(self):
        policy = ConcurrencyPolicy(
            mode=ConcurrencyMode.SERIAL,
            max_concurrency=1,
        )
        assert policy.mode == ConcurrencyMode.SERIAL
        assert policy.max_concurrency == 1


class TestPerformanceSnapshot:
    """Tests for PerformanceSnapshot model."""

    def test_create_snapshot(self):
        snapshot = PerformanceSnapshot(
            active_operations=3,
            queued_operations=2,
            completed_operations=10,
            average_latency=1.5,
            p95_latency=3.0,
            throughput=5.0,
        )
        assert snapshot.active_operations == 3
        assert snapshot.average_latency == 1.5
        assert snapshot.throughput == 5.0


class TestPerformanceReport:
    """Tests for PerformanceReport model."""

    def test_create_report(self):
        report = PerformanceReport(
            run_id="run-001",
            total_operations=10,
            successful_operations=8,
            failed_operations=2,
            average_latency=1.5,
        )
        assert report.run_id == "run-001"
        assert report.total_operations == 10
        assert report.successful_operations == 8
