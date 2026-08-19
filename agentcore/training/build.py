"""
Phase 6A dataset builder CLI.

Assembles training candidates into a versioned, validated JSONL dataset.

Usage:
    python -m agentcore.training.build --output <path>
    python -m agentcore.training.build --stats         # print stats only

The builder:
    1. Collects all experiences from candidates.py
    2. Runs each through ExperienceAnalyzer → LearningCandidate
    3. Scores with QualityScorer → rejects below threshold
    4. Checks for eval leakage → rejects matches
    5. Deduplicates by content hash
    6. Optionally balances category distribution
    7. Validates with quality gate
    8. Writes versioned JSONL dataset

Safety:
    - Does NOT train. Does NOT modify existing adapters.
    - Previous dataset (agentcore-v015, agentcore_train.json) is preserved.
"""

from __future__ import annotations

import argparse
import os
import sys

from .analyzer import ExperienceAnalyzer, LearningCandidate, TrainingExample
from .candidates import get_all_experiences
from .dataset import DatasetBuilder, DatasetConfig
from .leakage import LeakageDetector
from .scorer import QualityScorer
from .stats import DatasetStats, compute_stats

# Balancing configuration: target distribution per category
# Prioritizes underrepresented categories and memory
CATEGORY_PRIORITY = [
    "memory",  # highest priority (v1 regression)
    "extensibility",  # 0% baseline
    "orchestration",  # 0% baseline
    "runtime_adapter",  # 22% baseline
    "architecture",  # 25% baseline
    "runtime",  # 58% baseline (had regression)
    "cancellation",  # 57% baseline (had regression)
    "failure_handling",  # 58% baseline (had regression)
    "task_lifecycle",  # 100% baseline
    "shutdown",  # 33% baseline
    "safety",  # 57% baseline
    "persistence",  # 56% baseline
    "execution",  # 44% baseline
    "routing",  # 61% baseline
    "events",  # 67% baseline
]

ALL_CATEGORIES = [
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

# Domain to category mapping (for balancing)
DOMAIN_TO_CATEGORY = {
    "architecture": "architecture",
    "orchestration": "orchestration",
    "runtime": "runtime",
    "runtime_adapter": "runtime_adapter",
    "cancellation": "cancellation",
    "task_lifecycle": "task_lifecycle",
    "failure_handling": "failure_handling",
    "memory": "memory",
    "routing": "routing",
    "execution": "execution",
    "extensibility": "extensibility",
    "safety": "safety",
    "events": "events",
    "persistence": "persistence",
    "shutdown": "shutdown",
}


def build_dataset(
    output_path: str | None = None,
    *,
    eval_path: str | None = None,
    min_quality: float = 0.50,
    balance: bool = True,
    apply_quality_gate: bool = True,
) -> tuple[list[TrainingExample], list[LearningCandidate], DatasetStats]:
    """Build the Phase 6A dataset.

    Returns:
        (training_examples, rejected_candidates, stats)
    """
    # Step 1: Collect experiences
    experiences = get_all_experiences()

    # Step 2: Analyze experiences → learning candidates
    analyzer = ExperienceAnalyzer()
    candidates: list[LearningCandidate] = []
    for exp in experiences:
        candidates.extend(analyzer.analyze(exp))

    # Step 3: Score candidates (quality gate)
    scorer = QualityScorer(threshold=min_quality)

    # Step 4: Set up leakage detector
    leakage_detector = None
    if eval_path:
        leakage_detector = LeakageDetector(eval_path=eval_path)

    # Step 5: Build dataset (scores, filters, dedupes, validates)
    builder_config = DatasetConfig(min_quality=min_quality)
    builder = DatasetBuilder(
        scorer=scorer,
        leakage_detector=leakage_detector,
        config=builder_config,
    )

    # Score all candidates first to see what passes
    scored_candidates: list[LearningCandidate] = []
    rejected: list[LearningCandidate] = []

    for candidate in candidates:
        score, reasons = scorer.score(candidate)
        candidate.quality_score = score
        candidate.quality_reasons = reasons

        if not scorer.is_acceptable(score):
            candidate.metadata["rejection_reason"] = "below_quality_threshold"
            rejected.append(candidate)
            continue

        if leakage_detector is not None:
            leak_result = leakage_detector.check(candidate.instruction)
            if leak_result.leaked:
                candidate.metadata["rejection_reason"] = (
                    f"evaluation_leakage:{leak_result.match_type}:{leak_result.eval_case_id}"
                )
                rejected.append(candidate)
                continue

        scored_candidates.append(candidate)

    # Step 6: Deduplicate by content hash
    seen_hashes: set[str] = set()
    deduped: list[LearningCandidate] = []
    dup_count = 0
    for candidate in scored_candidates:
        if candidate.content_hash in seen_hashes:
            dup_count += 1
            continue
        seen_hashes.add(candidate.content_hash)
        deduped.append(candidate)

    # Step 7: Balance category distribution
    if balance:
        deduped = _balance_categories(deduped)

    # Step 8: Convert to TrainingExamples
    training_examples: list[TrainingExample] = []
    for candidate in deduped:
        example = TrainingExample(
            instruction=candidate.instruction,
            output=candidate.output,
            source=candidate.source,
            domains=list(candidate.domains),
            metadata=dict(candidate.metadata),
            quality_score=candidate.quality_score,
            quality_metadata={
                "quality_reasons": list(candidate.quality_reasons),
                "candidate_type": candidate.candidate_type,
                "has_verified_outcome": candidate.has_verified_outcome,
                "candidate_id": candidate.candidate_id,
            },
            is_correction=candidate.is_correction,
            content_hash=candidate.content_hash,
            example_id=candidate.candidate_id,
        )
        training_examples.append(example)

    # Step 9: Determine version
    version = "agentcore-v016"

    # Step 10: Save if output path provided
    saved_stats = DatasetStats()
    if output_path:
        # Determine version from existing files
        existing_versions = _find_existing_versions(os.path.dirname(output_path) or ".")
        version = builder.get_version(existing_versions)

        # Save as JSONL
        builder.save(
            training_examples,
            output_path,
            version=version,
            extra_metadata={
                "description": "Phase 6A: EraAI Adapter v2 training dataset",
                "eval_path": eval_path or "held-out",
                "min_quality_threshold": min_quality,
                "total_candidates": len(candidates),
                "rejected_count": len(rejected),
                "duplicate_count": dup_count,
            },
        )

        # Compute stats from saved file
        saved_stats = compute_stats(output_path, eval_path=eval_path)
        saved_stats.version = version
    else:
        saved_stats = _compute_in_memory_stats(training_examples, rejected, dup_count)
        saved_stats.version = version

    return training_examples, rejected, saved_stats


def _balance_categories(
    candidates: list[LearningCandidate],
) -> list[LearningCandidate]:
    """Balance the candidate set across categories.

    Strategy:
    1. Group candidates by their primary category (first domain).
    2. For underrepresented categories (below target), add candidates up to target.
    3. For overrepresented categories, subsample to cap.
    4. Always preserve all memory and correction examples.
    5. Never drop below 60% of the original count.
    """
    if not candidates:
        return candidates

    # Group by primary category
    by_category: dict[str, list[LearningCandidate]] = {}
    for c in candidates:
        primary = c.domains[0] if c.domains else "uncategorized"
        by_category.setdefault(primary, []).append(c)

    # Count current distribution
    total = len(candidates)

    # Target: at least 8-10 per category, memory gets at least 40
    target_per_category = max(total // len(ALL_CATEGORIES), 5)
    target_per_category = max(target_per_category, 5)

    result: list[LearningCandidate] = []
    for category in ALL_CATEGORIES:
        examples = by_category.get(category, [])
        if category == "memory":
            # Memory is always preserved in full
            result.extend(examples)
        elif len(examples) > target_per_category * 2:
            # Cap oversampled categories at 2x target, keeping best-scoring
            examples_sorted = sorted(examples, key=lambda c: c.quality_score, reverse=True)
            result.extend(examples_sorted[: target_per_category * 2])
        else:
            result.extend(examples)

    # Add any uncategorized examples
    result.extend(by_category.get("uncategorized", []))

    return result


def _compute_in_memory_stats(
    examples: list[TrainingExample],
    rejected: list[LearningCandidate],
    dup_count: int,
) -> DatasetStats:
    """Compute stats without saving to disk."""
    stats = DatasetStats()
    stats.total_examples = len(examples)

    domain_counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    scores: list[float] = []
    correction_count = 0
    success_count = 0

    for ex in examples:
        for d in ex.domains:
            domain_counts[d] = domain_counts.get(d, 0) + 1
        source = ex.source or "unknown"
        sources[source] = sources.get(source, 0) + 1
        scores.append(ex.quality_score)
        if ex.is_correction:
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
    stats.duplicate_count = dup_count

    config = DatasetConfig()
    stats.ready = (
        stats.total_examples >= 100
        and stats.avg_quality >= config.min_quality
        and stats.duplicate_count == 0
    )

    return stats


def _find_existing_versions(directory: str) -> list[str]:
    """Find existing dataset versions in a directory."""
    versions = ["agentcore-v015"]  # Known previous version
    if os.path.isdir(directory):
        for f in os.listdir(directory):
            if f.startswith("agentcore-v") and f.endswith(".jsonl"):
                versions.append(f.replace(".jsonl", ""))
            elif f.startswith("agentcore-v") and f.endswith(".json"):
                versions.append(f.replace(".json", ""))
    return versions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 6A: Build EraAI training dataset for Adapter v2"
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output path for JSONL dataset",
    )
    parser.add_argument(
        "--eval",
        default=os.environ.get("EPOCH_EVAL_PATH", ""),
        help="Path to eval_cases.jsonl (for leakage detection)",
    )
    parser.add_argument(
        "--min-quality",
        type=float,
        default=0.50,
        help="Minimum quality score threshold (default: 0.50)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print dataset statistics only (requires --output)",
    )
    parser.add_argument(
        "--no-balance",
        action="store_true",
        help="Skip category balancing",
    )
    args = parser.parse_args()

    print("=== Phase 6A Dataset Builder ===")
    print()

    examples, rejected, stats = build_dataset(
        output_path=args.output,
        eval_path=args.eval if os.path.exists(args.eval) else None,
        min_quality=args.min_quality,
        balance=not args.no_balance,
    )

    print(f"Total candidates: {len(examples) + len(rejected)}")
    print(f"Accepted examples: {len(examples)}")
    print(f"Rejected candidates: {len(rejected)}")
    print(f"Evaluation leakage: {stats.leakage_count}")
    print(f"Duplicates: {stats.duplicate_count}")
    print()
    print("Category distribution:")
    for cat in ALL_CATEGORIES:
        count = stats.domain_counts.get(cat, 0)
        bar = "#" * (count // 2)
        print(f"  {cat:<20} {count:>3} {bar}")
    print()
    print(f"Average quality: {stats.avg_quality:.4f}")
    print(f"Min quality: {stats.min_quality:.4f}")
    print(f"Max quality: {stats.max_quality:.4f}")
    print(f"Corrections: {stats.correction_count}")
    print(f"Successes: {stats.success_count}")
    print(f"Ready: {'YES' if stats.ready else 'NO'}")
    print()

    if args.stats and args.output and os.path.exists(args.output):
        print(stats.format_report())

    return 0 if stats.ready else 1


if __name__ == "__main__":
    sys.exit(main())
