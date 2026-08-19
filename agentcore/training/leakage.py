"""
LeakageDetector for Phase 6A training pipeline.

Ensures training examples do not overlap with the held-out evaluation set
(eval_cases.jsonl, path configurable via EPOCH_EVAL_PATH env var).

Checks performed:
    1. Exact prompt (instruction) match
    2. Normalized prompt match (lowercase, whitespace-collapsed, punctuation stripped)
    3. Content hash match
    4. Near-duplicate prompt (token-set overlap > 85%)

The evaluation dataset must remain held out.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field


@dataclass
class LeakageCheckResult:
    """Result of a leakage check for a single training candidate."""

    leaked: bool = False
    reason: str = ""
    eval_case_id: str = ""
    match_type: str = ""

    def to_dict(self) -> dict:
        return {
            "leaked": self.leaked,
            "reason": self.reason,
            "eval_case_id": self.eval_case_id,
            "match_type": self.match_type,
        }


@dataclass
class EvalCase:
    """A single evaluation case."""

    case_id: str
    category: str
    prompt: str
    expected_concepts: list[str] = field(default_factory=list)
    forbidden_concepts: list[str] = field(default_factory=list)
    minimum_concepts: int = 0
    normalized_prompt: str = ""
    prompt_hash: str = ""
    tokens: set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, data: dict) -> EvalCase:
        prompt = data.get("prompt", data.get("instruction", ""))
        normalized = _normalize_text(prompt)
        return cls(
            case_id=data.get("id", data.get("case_id", "")),
            category=data.get("category", ""),
            prompt=prompt,
            expected_concepts=data.get("expected_concepts", []),
            forbidden_concepts=data.get("forbidden_concepts", []),
            minimum_concepts=data.get("minimum_concepts", 0),
            normalized_prompt=normalized,
            prompt_hash=_content_hash(prompt),
            tokens=set(_tokenize(prompt)),
        )


def _normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, collapse whitespace, strip punctuation."""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text


def _content_hash(text: str) -> str:
    """Generate a content hash for a text string (normalized before hashing)."""
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()[:32]


def _tokenize(text: str) -> list[str]:
    """Tokenize text into word tokens for near-duplicate detection."""
    tokens = re.findall(r"\b\w+\b", text.lower())
    return tokens


def _jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def _overlap_coefficient(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Compute overlap coefficient (Dice/Sorensen-like) for containment detection.

    Returns |A ∩ B| / min(|A|, |B|). This detects when one text is a
    superset of another — critical for catching training prompts that
    contain an eval case's tokens as a subset.
    """
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    min_len = min(len(tokens_a), len(tokens_b))
    return intersection / min_len if min_len > 0 else 0.0


class LeakageDetector:
    """Detects training examples that overlap with evaluation cases.

    Usage:
        detector = LeakageDetector(eval_path="path/to/eval_cases.jsonl")
        result = detector.check(instruction, output)
        if result.leaked:
            print(f"Rejected: {result.reason}")
    """

    DEFAULT_EVAL_PATH = os.environ.get("EPOCH_EVAL_PATH", "eval_cases.jsonl")
    DEFAULT_NEAR_DUPLICATE_THRESHOLD = 0.85

    def __init__(
        self,
        eval_path: str = DEFAULT_EVAL_PATH,
        near_duplicate_threshold: float = DEFAULT_NEAR_DUPLICATE_THRESHOLD,
    ) -> None:
        self.eval_path = eval_path
        self.near_duplicate_threshold = near_duplicate_threshold
        self._eval_cases: list[EvalCase] = []
        self._eval_prompts: set[str] = set()
        self._eval_normalized: set[str] = set()
        self._eval_hashes: set[str] = set()
        self._loaded = False

    def load(self) -> LeakageDetector:
        """Load evaluation cases from the eval file. Idempotent."""
        if self._loaded:
            return self

        if not os.path.exists(self.eval_path):
            raise FileNotFoundError(f"Evaluation file not found: {self.eval_path}")

        with open(self.eval_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                case = EvalCase.from_dict(data)
                self._eval_cases.append(case)
                self._eval_prompts.add(case.prompt.strip().lower())
                self._eval_normalized.add(case.normalized_prompt)
                self._eval_hashes.add(case.prompt_hash)

        self._loaded = True
        return self

    @property
    def eval_case_count(self) -> int:
        """Number of evaluation cases loaded."""
        if not self._loaded:
            self.load()
        return len(self._eval_cases)

    @property
    def eval_categories(self) -> list[str]:
        """List of evaluation categories."""
        if not self._loaded:
            self.load()
        return sorted({c.category for c in self._eval_cases})

    def check(self, instruction: str, output: str = "") -> LeakageCheckResult:
        """Check if a training example's instruction overlaps with eval cases.

        Checks:
            1. Exact prompt match (case-insensitive)
            2. Normalized prompt match
            3. Content hash match
            4. Near-duplicate token-set overlap
        """
        if not self._loaded:
            self.load()

        normalized_instruction = _normalize_text(instruction)
        instruction_hash = _content_hash(instruction)
        instruction_lower = instruction.strip().lower()
        instruction_tokens = set(_tokenize(instruction))

        # 1. Exact prompt match
        if instruction_lower in self._eval_prompts:
            return LeakageCheckResult(
                leaked=True,
                reason="Exact prompt match with evaluation case",
                eval_case_id=self._find_case_by_prompt(instruction_lower).case_id,
                match_type="exact",
            )

        # 2. Normalized prompt match
        if normalized_instruction in self._eval_normalized:
            return LeakageCheckResult(
                leaked=True,
                reason="Normalized prompt match with evaluation case",
                eval_case_id=self._find_case_by_normalized(normalized_instruction).case_id,
                match_type="normalized",
            )

        # 3. Content hash match
        if instruction_hash in self._eval_hashes:
            return LeakageCheckResult(
                leaked=True,
                reason="Content hash match with evaluation case",
                eval_case_id=self._find_case_by_hash(instruction_hash).case_id,
                match_type="hash",
            )

        # 4. Near-duplicate detection (use overlap coefficient: catches
        #    when training prompt is a superset of an eval prompt)
        best_similarity = 0.0
        best_case: EvalCase | None = None
        for case in self._eval_cases:
            jaccard = _jaccard_similarity(instruction_tokens, case.tokens)
            overlap = _overlap_coefficient(instruction_tokens, case.tokens)
            sim = max(jaccard, overlap)
            if sim > best_similarity:
                best_similarity = sim
                best_case = case

        if best_similarity >= self.near_duplicate_threshold and best_case:
            return LeakageCheckResult(
                leaked=True,
                reason=(
                    f"Near-duplicate prompt (Jaccard similarity "
                    f"{best_similarity:.2%} >= {self.near_duplicate_threshold:.2%})"
                ),
                eval_case_id=best_case.case_id,
                match_type="near_duplicate",
            )

        return LeakageCheckResult(leaked=False)

    def _find_case_by_prompt(self, prompt_lower: str) -> EvalCase:
        for case in self._eval_cases:
            if case.prompt.strip().lower() == prompt_lower:
                return case
        raise ValueError(f"Prompt not found: {prompt_lower}")

    def _find_case_by_normalized(self, normalized: str) -> EvalCase:
        for case in self._eval_cases:
            if case.normalized_prompt == normalized:
                return case
        raise ValueError(f"Normalized prompt not found: {normalized}")

    def _find_case_by_hash(self, content_hash: str) -> EvalCase:
        for case in self._eval_cases:
            if case.prompt_hash == content_hash:
                return case
        raise ValueError(f"Hash not found: {content_hash}")
