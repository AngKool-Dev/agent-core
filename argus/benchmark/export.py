"""Benchmark export functionality."""

import csv
import io
import json
from typing import Any, Dict, List, Optional

from argus.benchmark.models import ExperimentResult
from argus.benchmark.reporter import BenchmarkReporter


class BenchmarkExporter:
    """Exports benchmark results in various formats."""

    def __init__(self):
        self._reporter = BenchmarkReporter()

    def to_json(
        self,
        experiment: ExperimentResult,
        score: Optional[Any] = None,
        pretty: bool = True,
    ) -> str:
        """Export experiment results as JSON string."""
        report = self._reporter.generate_json_report(experiment, score)
        if pretty:
            return json.dumps(report, indent=2, default=str)
        return json.dumps(report, default=str)

    def to_csv(self, experiment: ExperimentResult) -> str:
        """Export experiment results as CSV string."""
        rows = self._reporter.generate_csv_data(experiment)
        if not rows:
            return ""

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def to_markdown(
        self,
        experiment: ExperimentResult,
        score: Optional[Any] = None,
    ) -> str:
        """Export experiment results as Markdown."""
        return self._reporter.generate_markdown_report(experiment, score)

    def to_text(
        self,
        experiment: ExperimentResult,
        score: Optional[Any] = None,
    ) -> str:
        """Export experiment results as plain text."""
        return self._reporter.generate_text_report(experiment, score)

    def save_json(
        self,
        experiment: ExperimentResult,
        file_path: str,
        score: Optional[Any] = None,
    ) -> None:
        """Save experiment results to a JSON file."""
        content = self.to_json(experiment, score)
        with open(file_path, "w") as f:
            f.write(content)

    def save_csv(
        self,
        experiment: ExperimentResult,
        file_path: str,
    ) -> None:
        """Save experiment results to a CSV file."""
        content = self.to_csv(experiment)
        with open(file_path, "w") as f:
            f.write(content)

    def save_markdown(
        self,
        experiment: ExperimentResult,
        file_path: str,
        score: Optional[Any] = None,
    ) -> None:
        """Save experiment results to a Markdown file."""
        content = self.to_markdown(experiment, score)
        with open(file_path, "w") as f:
            f.write(content)
