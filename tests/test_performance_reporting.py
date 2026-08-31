"""Tests for ARGUS Performance reporting."""

import pytest

from argus.performance.reporting import PerformanceReporter
from argus.performance.telemetry import TelemetryCollector
from argus.performance.models import (
    PerformanceReport,
    PerformanceSnapshot,
)


class TestPerformanceReporter:
    """Tests for PerformanceReporter."""

    def setup_method(self):
        self.telemetry = TelemetryCollector()
        self.reporter = PerformanceReporter(self.telemetry)

    def test_generate_snapshot(self):
        self.telemetry.record_concurrency(3, 2, 10, 5)
        snapshot = self.reporter.generate_snapshot()
        assert isinstance(snapshot, PerformanceSnapshot)

    def test_generate_report(self):
        self.telemetry.record_latency("op1", 1.0, run_id="run-001")
        self.telemetry.record_latency("op2", 2.0, run_id="run-001")
        report = self.reporter.generate_report(run_id="run-001")
        assert isinstance(report, PerformanceReport)
        assert report.run_id == "run-001"
        assert report.total_operations == 2

    def test_format_report(self):
        report = PerformanceReport(
            run_id="run-001",
            total_operations=10,
            successful_operations=8,
            failed_operations=2,
            average_latency=1.5,
            throughput=5.0,
            peak_concurrency=4,
        )
        formatted = self.reporter.format_report(report)
        assert "PERFORMANCE REPORT" in formatted
        assert "run-001" in formatted
        assert "10" in formatted
        assert "8" in formatted

    def test_report_with_no_measurements(self):
        report = self.reporter.generate_report()
        assert report.total_operations == 0
        assert report.average_latency == 0.0
