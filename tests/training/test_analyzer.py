"""Tests for Phase 6A analyzer and candidate pipeline."""

import pytest

from agentcore.training.analyzer import (
    ExperienceAnalyzer,
)
from agentcore.training.candidates import (
    CORRECTION_CANDIDATES,
    TRAINING_CANDIDATES,
    get_all_experiences,
)
from agentcore.training.experience import CorrectionPair, Experience


@pytest.fixture
def analyzer():
    return ExperienceAnalyzer()


class TestExperienceAnalyzer:
    def test_valid_experience_produces_candidate(self, analyzer):
        exp = Experience(
            instruction="What is AgentCore memory?",
            output="AgentCore memory is a persistent store that uses "
            "MemoryBackend and MemoryManager. It supports search, "
            "store, update, and retrieval with confidence levels.",
            source="test",
            domains=["memory"],
        )
        candidates = analyzer.analyze(exp)
        assert len(candidates) == 1
        c = candidates[0]
        assert c.instruction == exp.instruction
        assert c.output == exp.output
        assert c.domains == ["memory"]
        assert c.candidate_id != ""

    def test_empty_instruction_rejected(self, analyzer):
        exp = Experience(
            instruction="",
            output="Some output text here that is long enough.",
            source="test",
        )
        candidates = analyzer.analyze(exp)
        assert len(candidates) == 0

    def test_short_output_rejected(self, analyzer):
        exp = Experience(
            instruction="What is this?",
            output="Short.",
            source="test",
            domains=["memory"],
        )
        candidates = analyzer.analyze(exp)
        assert len(candidates) == 0

    def test_uses_explicit_domains(self, analyzer):
        exp = Experience(
            instruction="What is memory?",
            output="Memory is a persistent store with confidence tracking "
            "and provenance management through the backend layer.",
            source="test",
            domains=["memory", "safety"],
        )
        candidates = analyzer.analyze(exp)
        assert candidates[0].domains == ["memory", "safety"]

    def test_falls_back_to_classification_when_empty(self, analyzer):
        exp = Experience(
            instruction="What is memory?",
            output="Memory is a persistent store with confidence tracking "
            "and provenance management through the backend layer.",
            source="test",
            domains=[],
        )
        candidates = analyzer.analyze(exp)
        assert len(candidates[0].domains) > 0
        assert "memory" in candidates[0].domains

    def test_candidate_has_content_hash(self, analyzer):
        exp = Experience(
            instruction="What is memory?",
            output="Memory is a persistent store with confidence tracking "
            "and provenance management through the backend layer.",
            source="test",
            domains=["memory"],
        )
        candidates = analyzer.analyze(exp)
        assert candidates[0].content_hash != ""
        assert len(candidates[0].content_hash) == 16

    def test_candidate_word_counts_populated(self, analyzer):
        exp = Experience(
            instruction="What is memory in AgentCore?",
            output="Memory is a persistent store with confidence tracking "
            "and provenance management through the backend layer.",
            source="test",
            domains=["memory"],
        )
        candidates = analyzer.analyze(exp)
        c = candidates[0]
        assert c.instruction_length == len(exp.instruction.split())
        assert c.output_length == len(exp.output.split())


class TestCorrectionPairAnalysis:
    def test_correction_pair_produces_correct_experience(self, analyzer):
        pair = CorrectionPair(
            instruction="What should happen when cancelling?",
            wrong_output="Just set a flag.",
            correct_output="Propagate cancellation to the runtime by "
            "calling cancel() on the adapter which terminates "
            "the subprocess. This is the actual behavior "
            "described in the architecture.",
            rationale="Cancellation must reach the execution layer.",
            domains=["cancellation", "runtime"],
        )
        candidates = analyzer.analyze_correction_pair(
            pair.instruction,
            pair.wrong_output,
            pair.correct_output,
            pair.rationale,
            pair.domains,
        )
        assert len(candidates) == 1
        assert candidates[0].output == pair.correct_output
        assert candidates[0].is_correction is True


class TestCandidatePool:
    def test_candidate_pool_has_minimum_size(self):
        experiences = get_all_experiences()
        assert len(experiences) >= 150

    def test_all_candidates_are_experiences(self):
        for c in TRAINING_CANDIDATES:
            assert isinstance(c, Experience)
        for c in CORRECTION_CANDIDATES:
            assert isinstance(c, CorrectionPair)

    def test_all_correction_pairs_have_required_fields(self):
        for pair in CORRECTION_CANDIDATES:
            assert pair.instruction
            assert pair.wrong_output
            assert pair.correct_output
            assert pair.rationale
            assert len(pair.domains) > 0

    def test_correction_pairs_have_rationale(self):
        for pair in CORRECTION_CANDIDATES:
            assert pair.rationale.strip(), (
                f"Correction pair missing rationale: {pair.instruction[:50]}"
            )

    def test_correction_count(self):
        assert len(CORRECTION_CANDIDATES) >= 8

    def test_memory_is_best_represented_domain(self):
        experiences = get_all_experiences()
        from collections import Counter

        domain_counts = Counter()
        for e in experiences:
            for d in e.domains:
                domain_counts[d] += 1
        assert domain_counts["memory"] == max(domain_counts.values()), (
            "Memory should be the most represented domain"
        )
