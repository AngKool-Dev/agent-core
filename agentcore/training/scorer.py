"""
QualityScorer for Phase 6A training pipeline.

Scoring rubric (deterministic, no LLM):

Score = w1 * coverage + w2 * specificity + w3 * evidence + w4 * correction + w5 * length

  coverage    — how many key concepts/domains are addressed (0-1)
  specificity — does the output avoid vague/generic language? (0-1)
  evidence    — does the output reference concrete AgentCore artifacts? (0-1)
  correction  — is this a correction example with verified outcome? (0-1)
  length      — output length relative to minimum (0-1, saturates)

Weights are configurable. Default weights favor specificity and correction.

Threshold: examples below 0.50 are rejected.
"""

from __future__ import annotations

from typing import ClassVar

from .analyzer import LearningCandidate

# Concrete AgentCore terms that count as "evidence"
AGENTCORE_EVIDENCE_TERMS = [
    "agentcore",
    "hermesruntime",
    "runtimeadapter",
    "runtimeadapter",
    "orchestration layer",
    "orchestrator",
    "taskregistry",
    "memorymanager",
    "memorybackend",
    "memoryrecord",
    "memorytype",
    "memoryconfidence",
    "observationstore",
    "observation",
    "eventbus",
    "hermeseventbridge",
    "runtimeregistry",
    "toolmanager",
    "taskpersistence",
    "runtime response",
    "finishreason",
    "toolcall",
    "toolresult",
    "memory harvesting",
    "memory harvester",
    "memorycandidate",
    "taskrecord",
    "taskstate",
    "skillrouter",
    "routingresult",
    "lifecycle",
    "lifecyclestates",
    "capabilit",
    "process isolation",
    "process_isolation",
    "external tool execution",
    "text_generation",
    "streaming",
    "cancellation",
    "tool_calls",
    "dbobsidian",
    "db-obsidian",
    "inmemorybackend",
    "hermesapi",
    "completion marker",
    "complete marker",
    "verification",
    "verification_scope",
    "contract",
    "adapter interface",
    "separation",
    "decouple",
    "isolation",
    "persistence",
    "confidenc",
    "provenance",
    "harvest",
]

# Vague terms that hurt specificity score
VAGUE_TERMS = [
    "something",
    "anything",
    "everything",
    "basically",
    "simply",
    "just",
    "really",
    "very",
    "like",
    "kind of",
    "sort of",
    "in a way",
    "on the other hand",
    "it depends",
    "may be",
    "might be",
    "could be",
    "probably",
    "possibly",
    "generally",
    "typically",
]

# Concept coverage — for each domain, the key terms that should appear
DOMAIN_CONCEPTS: dict[str, list[str]] = {
    "architecture": ["orchestration layer", "runtime", "agent", "task", "separation"],
    "orchestration": [
        "orchestration layer",
        "scheduling",
        "task",
        "resource management",
    ],
    "runtime": ["runtime adapter", "runtime", "execution", "capabilities"],
    "runtime_adapter": [
        "adapter interface",
        "runtime adapter",
        "contract",
        "lifecycle",
    ],
    "cancellation": [
        "cancellation",
        "propagate",
        "terminate",
        "interrupt",
        "cancelled",
    ],
    "task_lifecycle": ["lifecycle", "task states", "pending", "running", "terminal"],
    "failure_handling": ["error", "failure", "retry", "backoff", "isolation"],
    "memory": [
        "memory",
        "state management",
        "persistence",
        "retrieval",
        "confidence",
        "provenance",
    ],
    "routing": ["routing", "dispatcher", "capabilit", "requirements"],
    "execution": ["execution delegation", "delegate", "runtime adapter", "actual work"],
    "extensibility": [
        "extensible",
        "plugin",
        "adapter interface",
        "separation",
        "modify core",
    ],
    "safety": ["isolation", "resource limit", "process", "sandbox", "crash prevention"],
    "events": ["event", "event-driven", "push", "notification", "subscribe"],
    "persistence": ["persist", "durable", "storage", "flushed", "recovery"],
    "shutdown": ["graceful", "shutdown", "draining", "cancelled state"],
}


class QualityScorer:
    """Deterministic quality scorer for training candidates."""

    DEFAULT_THRESHOLD: ClassVar[float] = 0.50
    DEFAULT_WEIGHTS: ClassVar[dict[str, float]] = {
        "coverage": 0.25,
        "specificity": 0.20,
        "evidence": 0.30,
        "correction": 0.15,
        "length": 0.10,
    }
    MIN_OUTPUT_WORDS: ClassVar[int] = 10

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.threshold = threshold
        self.weights = weights or self.DEFAULT_WEIGHTS

    def score(self, candidate: LearningCandidate) -> tuple[float, list[str]]:
        """Score a candidate. Returns (score, reasons)."""
        reasons: list[str] = []

        coverage = self._coverage_score(candidate, reasons)
        specificity = self._specificity_score(candidate, reasons)
        evidence = self._evidence_score(candidate, reasons)
        correction = self._correction_score(candidate, reasons)
        length_score = self._length_score(candidate, reasons)

        total = (
            coverage * self.weights["coverage"]
            + specificity * self.weights["specificity"]
            + evidence * self.weights["evidence"]
            + correction * self.weights["correction"]
            + length_score * self.weights["length"]
        )
        total = round(total, 4)

        reasons.append(f"coverage={coverage:.2f}")
        reasons.append(f"specificity={specificity:.2f}")
        reasons.append(f"evidence={evidence:.2f}")
        reasons.append(f"correction={correction:.2f}")
        reasons.append(f"length={length_score:.2f}")
        reasons.append(f"final={total:.4f}")

        return total, reasons

    def is_acceptable(self, score: float) -> bool:
        return score >= self.threshold

    def _coverage_score(self, candidate: LearningCandidate, reasons: list[str]) -> float:
        """How many key domain concepts are addressed in the output."""
        output_lower = candidate.output.lower()
        domains = candidate.domains

        if not domains or domains == ["uncategorized"]:
            reasons.append("coverage: no domains classified")
            return 0.3

        matched = 0
        total = 0
        for domain in domains:
            concepts = DOMAIN_CONCEPTS.get(domain, [])
            if not concepts:
                continue
            total += len(concepts)
            for concept in concepts:
                if concept in output_lower:
                    matched += 1

        if total == 0:
            return 0.4

        score = matched / total
        if score >= 0.5:
            reasons.append(f"coverage: {matched}/{total} concepts matched")
        else:
            reasons.append(f"coverage: only {matched}/{total} concepts matched")
        return round(score, 4)

    def _specificity_score(self, candidate: LearningCandidate, reasons: list[str]) -> float:
        """Penalize vague language."""
        text_lower = (candidate.instruction + " " + candidate.output).lower()
        vague_count = sum(1 for term in VAGUE_TERMS if term in text_lower)

        if vague_count == 0:
            score = 1.0
            reasons.append("specificity: no vague terms")
        else:
            # Each vague term costs 0.15, capped at 0.4
            penalty = min(vague_count * 0.15, 0.6)
            score = max(1.0 - penalty, 0.4)
            reasons.append(f"specificity: {vague_count} vague terms, penalty={penalty:.2f}")

        return round(score, 4)

    def _evidence_score(self, candidate: LearningCandidate, reasons: list[str]) -> float:
        """How much concrete AgentCore knowledge is referenced."""
        text_lower = (candidate.instruction + " " + candidate.output).lower()
        evidence_count = sum(1 for term in AGENTCORE_EVIDENCE_TERMS if term in text_lower)

        if evidence_count >= 3:
            score = 1.0
            reasons.append(f"evidence: {evidence_count} concrete terms")
        elif evidence_count >= 1:
            score = 0.6
            reasons.append(f"evidence: {evidence_count} concrete terms")
        else:
            score = 0.2
            reasons.append("evidence: no concrete AgentCore terms found")

        return round(score, 4)

    def _correction_score(self, candidate: LearningCandidate, reasons: list[str]) -> float:
        """Bonus for correction examples with verified outcomes."""
        if candidate.is_correction and candidate.has_verified_outcome:
            reasons.append("correction: correction with verified outcome")
            return 1.0
        elif candidate.is_correction:
            reasons.append("correction: correction without verified outcome")
            return 0.5
        else:
            reasons.append("correction: not a correction example")
            return 0.3

    def _length_score(self, candidate: LearningCandidate, reasons: list[str]) -> float:
        """Reward adequate output length."""
        output_words = len(candidate.output.split())
        if output_words >= self.MIN_OUTPUT_WORDS:
            score = min(output_words / (self.MIN_OUTPUT_WORDS * 3), 1.0)
            reasons.append(f"length: output has {output_words} words")
        else:
            score = 0.0
            reasons.append(f"length: output too short ({output_words} words)")
        return round(score, 4)
