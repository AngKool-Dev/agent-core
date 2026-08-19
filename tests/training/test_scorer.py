"""Tests for Phase 6A QualityScorer."""

import pytest

from agentcore.training.analyzer import LearningCandidate
from agentcore.training.scorer import (
    AGENTCORE_EVIDENCE_TERMS,
    VAGUE_TERMS,
    QualityScorer,
)


@pytest.fixture
def scorer():
    return QualityScorer(threshold=0.50)


@pytest.fixture
def good_candidate():
    return LearningCandidate(
        instruction="What is the MemoryManager in AgentCore?",
        output=(
            "The MemoryManager in agentcore/memory.py is responsible for "
            "orchestrating memory operations. It normalizes backend results, "
            "limits context size, handles failures gracefully, and emits events. "
            "The manager delegates to MemoryBackend and never raises on backend "
            "failure. It uses confidence levels and provenance tracking."
        ),
        source="agentcore source",
        domains=["memory"],
        candidate_type="standard",
        is_correction=False,
        has_verified_outcome=False,
    )


@pytest.fixture
def correction_candidate():
    return LearningCandidate(
        instruction="What should happen when a task is cancelled?",
        output=(
            "Cancellation must propagate into the active runtime. The "
            "OrchestrationEngine calls RuntimeAdapter.cancel() which "
            "terminates the subprocess. This is the correct behavior."
        ),
        source="correction",
        domains=["cancellation", "runtime"],
        candidate_type="correction",
        is_correction=True,
        has_verified_outcome=True,
        rationale="Cancellation must propagate to the runtime process.",
    )


class TestQualityScorer:
    def test_score_returns_float_in_range(self, scorer, good_candidate):
        score, reasons = scorer.score(good_candidate)
        assert 0.0 <= score <= 1.0
        assert isinstance(reasons, list)
        assert len(reasons) > 0

    def test_high_quality_candidate_passes(self, scorer, good_candidate):
        score, _ = scorer.score(good_candidate)
        assert scorer.is_acceptable(score)

    def test_correction_candidate_scores_higher(self, scorer, good_candidate, correction_candidate):
        good_score, _ = scorer.score(good_candidate)
        correction_score, _ = scorer.score(correction_candidate)
        assert correction_score > good_score

    def test_low_evidence_candidate_scores_low(self, scorer):
        candidate = LearningCandidate(
            instruction="What is something?",
            output="It is a thing that does stuff. Basically it's just "
            "something that kind of works. Like a thing.",
            source="test",
            domains=["uncategorized"],
        )
        score, _reasons = scorer.score(candidate)
        assert score < 0.70

    def test_vague_terms_penalize_score(self, scorer):
        candidate = LearningCandidate(
            instruction="What is something?",
            output="It is basically just something that is very simple. "
            "It kind of does stuff. It is like a thing.",
            source="test",
            domains=["uncategorized"],
        )
        _score, _ = scorer.score(candidate)
        # Vague terms should lower the score
        assert "specificity" in " ".join(str(r) for r in scorer.score(candidate)[1])

    def test_min_quality_threshold(self, scorer):
        assert scorer.threshold == 0.50

    def test_evidence_terms_list_is_non_empty(self):
        assert len(AGENTCORE_EVIDENCE_TERMS) > 10

    def test_vague_terms_list_is_non_empty(self):
        assert len(VAGUE_TERMS) > 5

    def test_too_short_output_fails(self, scorer):
        candidate = LearningCandidate(
            instruction="What is this?",
            output="Short.",
            source="test",
            domains=[],
        )
        score, _reasons = scorer.score(candidate)
        assert score < 0.50
