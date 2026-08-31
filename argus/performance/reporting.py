"""Performance reporting."""

from typing import Any, Dict, List, Optional

from argus.performance.models import (
    PerformanceReport,
    PerformanceSnapshot,
)
from argus.performance.telemetry import TelemetryCollector


class PerformanceReporter:
    """Generates performance reports."""

    def __init__(self, telemetry: Optional[TelemetryCollector] = None):
        self._telemetry = telemetry or TelemetryCollector()

    def generate_snapshot(self) -> PerformanceSnapshot:
        """Generate a current performance snapshot."""
        measurements = self._telemetry.get_all_measurements()
        snapshots = self._telemetry.get_snapshots()

        latencies = [m.value for m in measurements if m.measurement_type.value == "latency"]
        throughputs = [m.value for m in measurements if m.measurement_type.value == "throughput"]

        return PerformanceSnapshot(
            active_operations=sum(
                1 for s in snapshots
                if s["type"] == "concurrency"
            ),
            completed_operations=len([
                s for s in snapshots
                if s["type"] == "concurrency"
            ]),
            average_latency=sum(latencies) / len(latencies) if latencies else 0.0,
            throughput=sum(throughputs) / len(throughputs) if throughputs else 0.0,
        )

    def generate_report(
        self,
        run_id: Optional[str] = None,
    ) -> PerformanceReport:
        """Generate a performance report."""
        measurements = self._telemetry.get_all_measurements()
        snapshots = self._telemetry.get_snapshots()

        latencies = [m.value for m in measurements if m.measurement_type.value == "latency"]

        return PerformanceReport(
            run_id=run_id,
            total_operations=len(measurements),
            successful_operations=len([m for m in measurements if m.value > 0]),
            average_latency=sum(latencies) / len(latencies) if latencies else 0.0,
            measurements=measurements,
        )

    def format_report(self, report: PerformanceReport) -> str:
        """Format a report as text."""
        lines = [
            "PERFORMANCE REPORT",
            "=" * 40,
            f"Run ID: {report.run_id or 'N/A'}",
            f"Total Operations: {report.total_operations}",
            f"Successful: {report.successful_operations}",
            f"Failed: {report.failed_operations}",
            f"Average Latency: {report.average_latency:.4f}s",
            f"Throughput: {report.throughput:.2f} ops/sec",
            f"Peak Concurrency: {report.peak_concurrency}",
        ]
        return "\n".join(lines)
