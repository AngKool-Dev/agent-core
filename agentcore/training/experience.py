"""
Experience data model for Phase 6A training pipeline.

An Experience represents a unit of knowledge — a single instruction/output
pair that may become a training example.  Examples include:

    - Source code facts extracted from the AgentCore codebase
    - Correction examples (wrong answer → correct answer)
    - Evaluation case patterns (for analysis only, not direct training)
    - Architectural decisions and design principles
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Experience:
    """A single experience that may yield training candidates.

    Attributes:
        instruction: The question/prompt that would be asked of the model.
        output: The correct, verified output/answer.
        input_context: Optional additional context (rarely used).
        source: Where this experience originated (e.g. "agentcore source",
                "correction", "architecture doc").
        domains: Pre-computed list of domains this experience covers.
        metadata: Arbitrary additional metadata (category, quality hints, etc.).
        experience_id: Deterministic ID for deduplication.
    """

    instruction: str
    output: str
    input_context: str = ""
    source: str = ""
    domains: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    experience_id: str = ""

    def __post_init__(self) -> None:
        if not self.experience_id:
            key = f"{self.instruction}:{self.output[:200]}"
            self.experience_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "instruction": self.instruction,
            "output": self.output,
            "input_context": self.input_context,
            "source": self.source,
            "domains": list(self.domains),
            "metadata": dict(self.metadata),
            "experience_id": self.experience_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Experience:
        return cls(
            instruction=data["instruction"],
            output=data["output"],
            input_context=data.get("input_context", ""),
            source=data.get("source", ""),
            domains=list(data.get("domains", [])),
            metadata=dict(data.get("metadata", {})),
            experience_id=data.get("experience_id", ""),
        )


@dataclass
class CorrectionPair:
    """A wrong answer paired with a correct answer, for contrastive learning.

    The idea: show the model what NOT to say, then what TO say.
    """

    instruction: str
    wrong_output: str
    correct_output: str
    rationale: str = ""
    source: str = "correction"
    domains: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    experience_id: str = ""

    def __post_init__(self) -> None:
        if not self.experience_id:
            key = f"{self.instruction}:{self.wrong_output[:100]}:{self.correct_output[:100]}"
            self.experience_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def to_experience_correct(self) -> Experience:
        return Experience(
            instruction=self.instruction,
            output=self.correct_output,
            source=self.source,
            domains=list(self.domains),
            metadata={
                "rationale": self.rationale,
                "is_correction": True,
                "has_verified_outcome": True,
                "instruction_context": "CORRECTION: " + self.rationale
                if self.rationale
                else "CORRECTION",
            },
            experience_id=self.experience_id + "_correct",
        )

    def to_experience_wrong(self) -> Experience:
        return Experience(
            instruction=self.instruction,
            output=self.wrong_output,
            source=self.source,
            domains=list(self.domains),
            metadata={
                "is_correction": True,
                "is_wrong": True,
                "rationale": self.rationale,
            },
            experience_id=self.experience_id + "_wrong",
        )
