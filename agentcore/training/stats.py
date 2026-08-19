"""
Dataset statistics and reporting for Phase 6A.

Provides DatasetStats and a CLI command:

    python -m agentcore.training.stats --dataset <path>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

from .dataset import DatasetConfig
from .domains import classify_domains


@dataclass
class DatasetStats:
    """Statistics for a training dataset."""

    version: str = ""
    total_examples: int = 0
    domain_counts: dict[str, int] = field(default_factory=dict)
    correction_count: int = 0
    success_count: int = 0
    duplicate_count: int = 0
    leakage_count: int = 0
    avg_quality: float = 0.0
    min_quality: float = 0.0
    max_quality: float = 0.0
    ready: bool = False
    sources: dict[str, int] = field(default_factory=dict)
    category_distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "total_examples": self.total_examples,
            "domain_counts": dict(self.domain_counts),
            "correction_count": self.correction_count,
            "success_count": self.success_count,
            "duplicate_count": self.duplicate_count,
            "leakage_count": self.leakage_count,
            "avg_quality": round(self.avg_quality, 4),
            "min_quality": round(self.min_quality, 4),
            "max_quality": round(self.max_quality, 4),
            "ready": self.ready,
            "sources": dict(self.sources),
            "category_distribution": dict(self.category_distribution),
        }

    def format_report(self) -> str:
        """Format stats as a human-readable report."""
        lines = []
        lines.append("=" * 60)
        lines.append("EraAI Dataset Statistics")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Dataset: {self.version}")
        lines.append(f"Total examples: {self.total_examples}")
        lines.append("")
        lines.append("Categories:")
        all_domains = [
            "architecture",
            "orchestration",
            "runtime",
            "runtime_adapter",
            "cancellation",
            "task_lifecycle",
            "failure_handling",
            "memory",
            "routing",
            "execution",
            "extensibility",
            "safety",
            "events",
            "persistence",
            "shutdown",
        ]
        for domain in all_domains:
            count = self.domain_counts.get(domain, 0)
            lines.append(f"  {domain:<20} {count:>3}")
        lines.append("")
        lines.append(f"Corrections: {self.correction_count}")
        lines.append(f"Successes: {self.success_count}")
        lines.append(f"Duplicates: {self.duplicate_count}")
        lines.append(f"Evaluation leakage: {self.leakage_count}")
        lines.append("")
        lines.append(f"Average quality: {self.avg_quality:.4f}")
        lines.append(f"Min quality: {self.min_quality:.4f}")
        lines.append(f"Max quality: {self.max_quality:.4f}")
        lines.append("")
        lines.append(f"Ready: {'YES' if self.ready else 'NO'}")
        lines.append("=" * 60)
        return "\n".join(lines)


def compute_stats(dataset_path: str, *, eval_path: str | None = None) -> DatasetStats:
    """Compute statistics for a JSONL dataset file."""
    examples: list[dict] = []
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))

    stats = DatasetStats()
    stats.total_examples = len(examples)

    domain_counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    scores: list[float] = []
    content_hashes: list[str] = []
    correction_count = 0
    success_count = 0

    for ex in examples:
        # Domain counts (each example can have multiple domains)
        domains_list = ex.get("domains", [])
        if not domains_list:
            domains_list = classify_domains(ex.get("instruction", "") + " " + ex.get("output", ""))
        for d in domains_list:
            domain_counts[d] = domain_counts.get(d, 0) + 1

        # Sources
        source = ex.get("source", "unknown")
        sources[source] = sources.get(source, 0) + 1

        # Quality scores
        score = ex.get("quality_score", 0.0)
        scores.append(score)

        # Content hashes (for duplicate detection)
        content_hashes.append(ex.get("content_hash", ""))

        # Correction / success
        if ex.get("is_correction", False):
            correction_count += 1
        else:
            success_count += 1

    stats.domain_counts = domain_counts
    stats.sources = sources
    stats.correction_count = correction_count
    stats.success_count = success_count
    stats.avg_quality = sum(scores) / len(scores) if scores else 0.0
    stats.min_quality = min(scores) if scores else 0.0
    stats.max_quality = max(scores) if scores else 0.0

    # Duplicate count
    unique_hashes = set(content_hashes)
    stats.duplicate_count = len(content_hashes) - len(unique_hashes)

    # Category distribution (primary domain per example)
    category_dist: dict[str, int] = {}
    for ex in examples:
        domains_list = ex.get("domains", [])
        primary = domains_list[0] if domains_list else "uncategorized"
        category_dist[primary] = category_dist.get(primary, 0) + 1
    stats.category_distribution = category_dist

    # Evaluation leakage check
    stats.leakage_count = 0
    if eval_path and os.path.exists(eval_path):
        from .leakage import LeakageDetector

        detector = LeakageDetector(eval_path=eval_path)
        detector.load()
        for ex in examples:
            result = detector.check(ex.get("instruction", ""))
            if result.leaked:
                stats.leakage_count += 1

    # Determine version from filename if not in metadata
    stats.version = "unknown"
    basename = os.path.basename(dataset_path)
    if basename.startswith("agentcore-v"):
        stats.version = basename.replace(".jsonl", "").replace(".json", "")

    # Ready check
    config = DatasetConfig()
    stats.ready = (
        stats.total_examples >= 100
        and stats.avg_quality >= config.min_quality
        and stats.duplicate_count == 0
        and stats.leakage_count == 0
    )

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="EraAI dataset statistics")
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to JSONL dataset file",
    )
    parser.add_argument(
        "--eval",
        default=None,
        help="Path to eval_cases.jsonl for leakage check",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    if not os.path.exists(args.dataset):
        print(f"Error: dataset not found: {args.dataset}", file=sys.stderr)
        return 1

    stats = compute_stats(args.dataset, eval_path=args.eval)

    if args.json:
        print(json.dumps(stats.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(stats.format_report())

    return 0 if stats.ready else 1


if __name__ == "__main__":
    sys.exit(main())
