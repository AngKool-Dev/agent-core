"""
ExperienceAnalyzer and LearningCandidate for Phase 6A training pipeline.

Pipeline:
    Experience
        ↓
    ExperienceAnalyzer          (analyzes + generates candidates)
        ↓
    LearningCandidate
        ↓
    QualityScorer               (scores candidates)
        ↓
    Human Review (quality gate)
        ↓
    TrainingExample
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .domains import classify_domains
from .experience import Experience


@dataclass
class LearningCandidate:
    """A candidate training example produced by ExperienceAnalyzer.

    Not yet a TrainingExample — must pass QualityScorer first.
    """

    instruction: str
    output: str
    source: str
    domains: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    candidate_id: str = ""
    is_correction: bool = False
    is_wrong: bool = False
    rationale: str = ""
    quality_score: float = 0.0
    quality_reasons: list[str] = field(default_factory=list)
    has_verified_outcome: bool = False
    candidate_type: str = "standard"
    instruction_length: int = 0
    output_length: int = 0
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id:
            key = f"{self.instruction}:{self.output[:200]}"
            self.candidate_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        if not self.content_hash:
            self.content_hash = hashlib.sha256(
                f"{self.instruction.lower().strip()}|{self.output.lower().strip()}".encode()
            ).hexdigest()[:16]
        if self.instruction_length == 0:
            self.instruction_length = len(self.instruction.split())
        if self.output_length == 0:
            self.output_length = len(self.output.split())

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "instruction": self.instruction,
            "output": self.output,
            "source": self.source,
            "domains": list(self.domains),
            "metadata": dict(self.metadata),
            "is_correction": self.is_correction,
            "is_wrong": self.is_wrong,
            "rationale": self.rationale,
            "quality_score": self.quality_score,
            "quality_reasons": list(self.quality_reasons),
            "has_verified_outcome": self.has_verified_outcome,
            "candidate_type": self.candidate_type,
            "instruction_length": self.instruction_length,
            "output_length": self.output_length,
            "content_hash": self.content_hash,
        }


@dataclass
class TrainingExample:
    """A finalized training example that has passed the quality gate."""

    instruction: str
    output: str
    source: str
    domains: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    quality_metadata: dict[str, Any] = field(default_factory=dict)
    is_correction: bool = False
    content_hash: str = ""
    example_id: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = hashlib.sha256(
                f"{self.instruction.lower().strip()}|{self.output.lower().strip()}".encode()
            ).hexdigest()[:16]
        if not self.example_id:
            key = f"{self.instruction}:{self.output[:200]}"
            self.example_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "instruction": self.instruction,
            "output": self.output,
            "source": self.source,
            "domains": list(self.domains),
            "metadata": dict(self.metadata),
            "quality_score": self.quality_score,
            "quality_metadata": dict(self.quality_metadata),
            "is_correction": self.is_correction,
            "content_hash": self.content_hash,
            "example_id": self.example_id,
        }


class ExperienceAnalyzer:
    """Analyzes experiences and produces LearningCandidates.

    For each Experience, the analyzer:
    1. Validates basic quality (non-empty instruction/output, not too short)
    2. Classifies domains
    3. Tags correction/wrong pairs
    4. Computes basic metadata (lengths, hashes, etc.)

    The analyzer NEVER directly produces TrainingExamples — those come
    from the QualityScorer pipeline.
    """

    MIN_INSTRUCTION_WORDS = 3
    MIN_OUTPUT_WORDS = 10
    MAX_INSTRUCTION_LEN = 500
    MAX_OUTPUT_LEN = 4000

    def analyze(self, experience: Experience) -> list[LearningCandidate]:
        """Analyze a single Experience and return candidates.

        Returns a list with one candidate (or empty if rejected).
        CorrectionPair experiences can produce two candidates (wrong + correct).
        """
        candidates: list[LearningCandidate] = []

        if not self._is_valid(experience):
            return candidates

        domains = (
            experience.domains
            if experience.domains
            else classify_domains(experience.instruction + " " + experience.output)
        )

        meta = dict(experience.metadata)
        meta.setdefault("created_at", datetime.now(UTC).isoformat())

        candidate = LearningCandidate(
            instruction=experience.instruction.strip(),
            output=experience.output.strip(),
            source=experience.source,
            domains=domains or ["uncategorized"],
            metadata=meta,
            candidate_type=meta.get("candidate_type", "standard"),
            is_correction=meta.get("is_correction", False),
            is_wrong=meta.get("is_wrong", False),
            rationale=meta.get("rationale", ""),
            has_verified_outcome=meta.get("has_verified_outcome", False),
        )
        candidates.append(candidate)

        return candidates

    def analyze_correction_pair(
        self,
        pair_instruction: str,
        wrong: str,
        correct: str,
        rationale: str,
        domains: list[str] | None = None,
    ) -> list[LearningCandidate]:
        """Analyze a correction pair, producing a CORRECT learning candidate.

        The wrong answer is captured as metadata but the candidate itself
        is the correct answer, with is_correction=True.
        """
        candidates: list[LearningCandidate] = []

        if not pair_instruction.strip() or not correct.strip():
            return candidates

        combined = pair_instruction + " " + correct
        classified_domains = domains if domains else classify_domains(combined)

        candidate = LearningCandidate(
            instruction=pair_instruction.strip(),
            output=correct.strip(),
            source="correction",
            domains=classified_domains,
            metadata={
                "wrong_answer": wrong.strip(),
                "rationale": rationale,
                "is_correction": True,
                "has_verified_outcome": True,
                "created_at": datetime.now(UTC).isoformat(),
            },
            is_correction=True,
            is_wrong=False,
            rationale=rationale,
            has_verified_outcome=True,
            candidate_type="correction",
        )
        candidates.append(candidate)

        return candidates

    def _is_valid(self, experience: Experience) -> bool:
        """Basic validation — rejects empty, too-short, or too-long experiences."""
        if not experience.instruction or not experience.output:
            return False
        if len(experience.instruction.strip().split()) < self.MIN_INSTRUCTION_WORDS:
            return False
        if len(experience.output.strip().split()) < self.MIN_OUTPUT_WORDS:
            return False
        if len(experience.instruction) > self.MAX_INSTRUCTION_LEN:
            return False
        return len(experience.output) <= self.MAX_OUTPUT_LEN
