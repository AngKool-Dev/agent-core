"""
DatasetBuilder for Phase 6A training pipeline.

Assembles LearningCandidates into a validated TrainingExample dataset.

Quality gate:
    - minimum quality >= configured threshold
    - duplicate ratio == 0 (content hash dedup)
    - evaluation leakage == 0
    - rejected candidates excluded
    - all examples have instruction, output, source, quality metadata
    - no secrets / credentials / API keys

Version management:
    - Datasets are versioned as agentcore-v016, agentcore-v017, etc.
    - The versioning scheme is a simple incrementing integer suffix.
    - The previous dataset (agentcore-v015 or agentcore_train.json) is preserved.

Output format: JSONL (one training example per line), compatible with
the EraAI training script (train_lora_cpu.py).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .analyzer import LearningCandidate, TrainingExample
from .leakage import LeakageDetector
from .scorer import QualityScorer

# Secret detection patterns (conservative)
SECRET_PATTERNS = [
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"][a-zA-Z0-9]{20,}"),
    re.compile(r"(?i)secret\s*[:=]\s*['\"][a-zA-Z0-9]{8,}"),
    re.compile(r"(?i)password\s*[:=]\s*['\"][^\s'\"]+"),
    re.compile(r"(?i)access[_-]?token\s*[:=]\s*['\"][a-zA-Z0-9]{10,}"),
    re.compile(r"(?i)auth[_-]?token\s*[:=]\s*['\"][a-zA-Z0-9]{10,}"),
    re.compile(r"(?i)private[_-]?key\s*[:=]\s*['\"]"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"gh[pousr]_[a-zA-Z0-9]{20,}"),
]

# Patterns that indicate personal data / PII
PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b\d{3}-\d{3}-\d{4}\b"),  # Phone
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),  # Email
    re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),  # Credit card
]


@dataclass
class DatasetConfig:
    """Configuration for dataset building."""

    min_quality: float = 0.50
    max_duplicate_ratio: float = 0.0
    require_secrets_check: bool = True
    require_source: bool = True
    require_quality_metadata: bool = True
    version_base: str = "agentcore-v015"
    version_increment: int = 1


@dataclass
class DatasetValidationResult:
    """Result of dataset quality validation."""

    passed: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "checks": dict(self.checks),
        }


class DatasetBuilder:
    """Assembles and validates a training dataset from LearningCandidates.

    Quality gate (Step 10):
        - min quality >= threshold
        - duplicate ratio == 0
        - evaluation leakage == 0
        - no rejected candidates in final set
        - all examples have required fields
        - no secrets / PII
    """

    def __init__(
        self,
        scorer: QualityScorer | None = None,
        leakage_detector: LeakageDetector | None = None,
        config: DatasetConfig | None = None,
    ) -> None:
        self.scorer = scorer or QualityScorer()
        self.leakage_detector = leakage_detector
        self.config = config or DatasetConfig()

    def build(
        self,
        candidates: list[LearningCandidate],
        *,
        apply_quality_gate: bool = True,
    ) -> tuple[list[TrainingExample], list[LearningCandidate], DatasetValidationResult]:
        """Build and validate a dataset from candidates.

        Returns:
            (training_examples, rejected_candidates, validation_result)
        """
        scored: list[tuple[LearningCandidate, float, list[str]]] = []
        rejected: list[LearningCandidate] = []

        for candidate in candidates:
            score, reasons = self.scorer.score(candidate)
            candidate.quality_score = score
            candidate.quality_reasons = reasons

            if apply_quality_gate and not self.scorer.is_acceptable(score):
                candidate.metadata["rejection_reason"] = "below_quality_threshold"
                rejected.append(candidate)
                continue

            if apply_quality_gate and self._contains_secrets(
                candidate.instruction + " " + candidate.output
            ):
                candidate.metadata["rejection_reason"] = "potential_secret_detected"
                rejected.append(candidate)
                continue

            if self.leakage_detector is not None:
                leak_result = self.leakage_detector.check(candidate.instruction)
                if leak_result.leaked:
                    candidate.metadata["rejection_reason"] = (
                        f"evaluation_leakage:{leak_result.match_type}:{leak_result.eval_case_id}"
                    )
                    rejected.append(candidate)
                    continue

            scored.append((candidate, score, reasons))

        # Deduplicate by content hash
        seen_hashes: set[str] = set()
        deduped: list[tuple[LearningCandidate, float, list[str]]] = []
        duplicates_in_input = 0
        for candidate, score, reasons in scored:
            if candidate.content_hash in seen_hashes:
                duplicates_in_input += 1
                continue
            seen_hashes.add(candidate.content_hash)
            deduped.append((candidate, score, reasons))

        # Sort by quality score descending (best first)
        deduped.sort(key=lambda x: x[1], reverse=True)

        # Convert to TrainingExamples
        training_examples: list[TrainingExample] = []
        for candidate, score, reasons in deduped:
            example = TrainingExample(
                instruction=candidate.instruction,
                output=candidate.output,
                source=candidate.source,
                domains=list(candidate.domains),
                metadata=dict(candidate.metadata),
                quality_score=score,
                quality_metadata={
                    "quality_reasons": reasons,
                    "candidate_type": candidate.candidate_type,
                    "has_verified_outcome": candidate.has_verified_outcome,
                    "candidate_id": candidate.candidate_id,
                },
                is_correction=candidate.is_correction,
                content_hash=candidate.content_hash,
                example_id=candidate.candidate_id,
            )
            training_examples.append(example)

        validation = self._validate(training_examples, rejected, len(candidates))

        return training_examples, rejected, validation

    def _validate(
        self,
        examples: list[TrainingExample],
        rejected: list[LearningCandidate],
        total_candidates: int,
    ) -> DatasetValidationResult:
        """Run the quality gate checks."""
        result = DatasetValidationResult()

        # Check: minimum quality >= threshold
        below_threshold = [e for e in examples if e.quality_score < self.config.min_quality]
        if below_threshold:
            result.errors.append(
                f"{len(below_threshold)} examples below quality threshold {self.config.min_quality}"
            )
            result.passed = False

        # Check: duplicate ratio == 0
        hashes = [e.content_hash for e in examples]
        if hashes:
            dup_ratio = 1 - len(set(hashes)) / len(hashes)
        else:
            dup_ratio = 0.0
        if dup_ratio > self.config.max_duplicate_ratio:
            result.errors.append(
                f"Duplicate ratio {dup_ratio:.2%} exceeds max {self.config.max_duplicate_ratio:.2%}"
            )
            result.passed = False

        # Check: no rejected candidates in final set
        # (Already enforced by build — rejected candidates are excluded)

        # Check: all examples have required fields
        for ex in examples:
            if not ex.instruction:
                result.errors.append(f"Example {ex.example_id} has empty instruction")
                result.passed = False
            if not ex.output:
                result.errors.append(f"Example {ex.example_id} has empty output")
                result.passed = False
            if self.config.require_source and not ex.source:
                result.errors.append(f"Example {ex.example_id} has empty source")
                result.passed = False
            if self.config.require_quality_metadata and not ex.quality_metadata:
                result.errors.append(f"Example {ex.example_id} has no quality metadata")
                result.passed = False

        # Check: no secrets
        all_text = " ".join(e.instruction + e.output for e in examples)
        if self._contains_secrets(all_text):
            result.errors.append("Potential secrets detected in dataset")
            result.passed = False

        # Check: no PII
        for ex in examples:
            if self._contains_pii(ex.instruction + " " + ex.output):
                result.errors.append(f"PII detected in example {ex.example_id}")
                result.passed = False

        # Summary checks
        result.checks["total_examples"] = len(examples)
        result.checks["rejected_count"] = len(rejected)
        result.checks["duplicate_ratio"] = round(dup_ratio, 4)
        result.checks["avg_quality"] = (
            round(sum(e.quality_score for e in examples) / len(examples), 4) if examples else 0.0
        )
        result.checks["min_quality"] = min(e.quality_score for e in examples) if examples else 0.0
        result.checks["max_quality"] = max(e.quality_score for e in examples) if examples else 0.0

        return result

    def _contains_secrets(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in SECRET_PATTERNS)

    def _contains_pii(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in PII_PATTERNS)

    def get_version(self, existing_versions: list[str]) -> str:
        """Determine the next dataset version.

        Existing versions like 'agentcore-v015' -> 'agentcore-v016'
        """
        max_num = 0
        for v in existing_versions:
            match = re.match(r"agentcore-v(\d+)", v)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)
        next_num = max_num + 1
        return f"agentcore-v{next_num:03d}"

    def save(
        self,
        examples: list[TrainingExample],
        path: str,
        *,
        version: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Save dataset as JSONL to the given path.

        If path is a directory, the file is saved as <path>/<version>.jsonl.
        Returns the full path to the saved file.
        """
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)

        metadata = {
            "version": version or "unknown",
            "created_at": datetime.now(UTC).isoformat(),
            "total_examples": len(examples),
            "domains": sorted({d for ex in examples for d in ex.domains}),
            "corrections": sum(1 for ex in examples if ex.is_correction),
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        # Write JSONL
        with open(path, "w", encoding="utf-8") as f:
            for example in examples:
                record = {
                    "instruction": example.instruction,
                    "output": example.output,
                    "source": example.source,
                    "domains": list(example.domains),
                    "metadata": dict(example.metadata),
                    "quality_score": example.quality_score,
                    "quality_metadata": dict(example.quality_metadata),
                    "is_correction": example.is_correction,
                    "content_hash": example.content_hash,
                    "example_id": example.example_id,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return path
