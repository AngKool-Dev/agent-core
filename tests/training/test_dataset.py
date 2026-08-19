"""Tests for Phase 6A dataset builder and quality gate."""

import os

from agentcore.training.analyzer import (
    ExperienceAnalyzer,
    LearningCandidate,
)
from agentcore.training.build import _balance_categories, build_dataset
from agentcore.training.candidates import (
    get_all_experiences,
)
from agentcore.training.dataset import DatasetBuilder
from agentcore.training.experience import Experience


class TestDatasetQualityGate:
    """Tests for the dataset quality gate (Step 10)."""

    def test_dataset_has_minimum_examples(self):
        experiences = get_all_experiences()
        assert len(experiences) >= 150

    def test_all_examples_have_required_fields(self):
        from agentcore.training.build import build_dataset

        examples, _rejected, _stats = build_dataset(apply_quality_gate=True)
        for ex in examples:
            assert ex.instruction, "Example has empty instruction"
            assert ex.output, "Example has empty output"
            assert ex.source, "Example has empty source"
            assert ex.quality_score >= 0.50, f"Example quality {ex.quality_score} below threshold"
            assert ex.content_hash, "Example has no content hash"
            assert ex.example_id, "Example has no example_id"

    def test_no_duplicates_in_final_dataset(self):
        examples, _rejected, stats = build_dataset(apply_quality_gate=True)
        hashes = [ex.content_hash for ex in examples]
        assert len(hashes) == len(set(hashes)), "Duplicate content hashes found"
        assert stats.duplicate_count == 0

    def test_rejected_candidates_excluded(self):
        examples, rejected, _stats = build_dataset(apply_quality_gate=True)
        # No rejected candidate should appear in the final dataset
        example_hashes = {ex.content_hash for ex in examples}
        for r in rejected:
            assert r.content_hash not in example_hashes, (
                f"Rejected candidate {r.candidate_id} found in dataset"
            )


class TestDatasetVersioning:
    """Tests for dataset versioning (Step 11)."""

    def test_version_is_agentcore_v016(self):
        _, _, stats = build_dataset(apply_quality_gate=True)
        assert stats.version == "agentcore-v016"

    def test_version_increments_correctly(self):
        builder = DatasetBuilder()
        version = builder.get_version(["agentcore-v015", "agentcore-v014"])
        assert version == "agentcore-v016"

    def test_previous_dataset_preserved(self):
        # agentcore_train.json should still exist
        assert os.path.exists(r"C:\EraAI\data\agentcore_train.json")


class TestDatasetBalancing:
    """Tests for category balancing (Step 9)."""

    def test_balance_preserves_memory_examples(self):
        experiences = get_all_experiences()
        analyzer = ExperienceAnalyzer()
        candidates = []
        for exp in experiences:
            candidates.extend(analyzer.analyze(exp))

        # Count memory examples before balancing
        memory_before = sum(1 for c in candidates if "memory" in c.domains)
        memory_after = sum(
            1
            for c in _balance_categories(
                [
                    LearningCandidate(
                        instruction=c.instruction,
                        output=c.output,
                        source=c.source,
                        domains=c.domains,
                        quality_score=c.quality_score,
                        quality_reasons=c.quality_reasons,
                        content_hash=c.content_hash,
                        candidate_id=c.candidate_id,
                    )
                    for c in candidates
                ]
            )
            if "memory" in c.domains
        )

        assert memory_after == memory_before, "Memory examples should not be reduced by balancing"

    def test_balance_cap_overrepresented_categories(self):
        experiences = get_all_experiences()
        analyzer = ExperienceAnalyzer()
        candidates = []
        for exp in experiences:
            candidates.extend(analyzer.analyze(exp))

        balanced = _balance_categories(candidates)
        # No non-memory category should be excessively over-represented
        from collections import Counter

        counts = Counter()
        for c in balanced:
            primary = c.domains[0] if c.domains else "uncategorized"
            counts[primary] += 1

        total = len(balanced)
        for cat, count in counts.items():
            if cat != "memory":
                # No single non-memory category should exceed 30% of total
                assert count / total < 0.30, (
                    f"Category {cat} comprises {count / total:.1%} of dataset"
                )


class TestDatasetStatistics:
    """Tests for dataset statistics (Step 12)."""

    def test_stats_command_shows_all_fields(self):
        from agentcore.training.build import build_dataset

        _examples, _, stats = build_dataset(apply_quality_gate=True)
        assert stats.total_examples > 0
        assert stats.avg_quality > 0
        assert stats.min_quality >= 0.50
        assert stats.correction_count >= 8  # 8 correction pairs
        assert stats.success_count > 0

    def test_stats_ready_flag(self):
        _, _, stats = build_dataset(apply_quality_gate=True)
        assert stats.ready is True


class TestMemoryPrioritization:
    """Tests that memory examples are prioritized (Step 6)."""

    def test_memory_is_high_priority_in_distribution(self):
        experiences = get_all_experiences()
        memory_count = sum(1 for e in experiences if "memory" in e.domains)
        total = len(experiences)
        # Memory should be at least 30% of examples
        assert memory_count / total >= 0.30, (
            f"Memory coverage {memory_count}/{total} = {memory_count / total:.1%} below 30%"
        )

    def test_memory_examples_cover_all_subtopics(self):
        experiences = get_all_experiences()
        memory_examples = [e for e in experiences if "memory" in e.domains]

        # Check coverage of memory subtopics
        memory_text = " ".join(e.output for e in memory_examples)

        subtopics = [
            "MemoryManager",
            "MemoryBackend",
            "confidence",
            "provenance",
            "MemoryHarvester",
            "retrieve_relevant_memory",
            "MemoryType",
            "DBObsidianBackend",
            "sensitive",
            "memory.error",
        ]
        for subtopic in subtopics:
            assert subtopic in memory_text, (
                f"Memory subtopic '{subtopic}' not covered in training data"
            )

    def test_memory_examples_exceed_baseline(self):
        # v1 had memory at 2/3 = 66.7% (regression) or 0.3889
        # Phase 6A should have far more memory examples
        experiences = get_all_experiences()
        memory_count = sum(1 for e in experiences if "memory" in e.domains)
        # v1 had at most ~10 memory-related examples across 55 eval cases
        # Phase 6A should have 50+ explicit memory examples
        assert memory_count >= 50, f"Only {memory_count} memory examples (need 50+)"


class TestLeakagePrevention:
    """Tests for evaluation leakage prevention (Step 8)."""

    def test_no_exact_prompt_matches_with_eval(self):
        from agentcore.training.leakage import LeakageDetector

        detector = LeakageDetector(eval_path=r"C:\EraAI\evaluation\eval_cases.jsonl")
        detector.load()

        experiences = get_all_experiences()
        for exp in experiences:
            result = detector.check(exp.instruction)
            assert not result.leaked, (
                f"Training example matches eval case {result.eval_case_id} "
                f"({result.match_type}): {exp.instruction[:80]}..."
            )

    def test_no_normalized_prompt_matches_with_eval(self):
        from agentcore.training.leakage import LeakageDetector

        detector = LeakageDetector(eval_path=r"C:\EraAI\evaluation\eval_cases.jsonl")
        detector.load()

        experiences = get_all_experiences()
        for exp in experiences:
            result = detector.check(exp.instruction)
            assert result.match_type != "normalized", (
                f"Normalized prompt match detected for: {exp.instruction[:80]}..."
            )

    def test_no_hash_matches_with_eval(self):
        from agentcore.training.leakage import LeakageDetector

        detector = LeakageDetector(eval_path=r"C:\EraAI\evaluation\eval_cases.jsonl")
        detector.load()

        experiences = get_all_experiences()
        for exp in experiences:
            result = detector.check(exp.instruction)
            assert result.match_type != "hash", (
                f"Hash match detected for: {exp.instruction[:80]}..."
            )

    def test_no_near_duplicates_with_eval(self):
        from agentcore.training.leakage import LeakageDetector

        detector = LeakageDetector(
            eval_path=r"C:\EraAI\evaluation\eval_cases.jsonl",
            near_duplicate_threshold=0.85,
        )
        detector.load()

        experiences = get_all_experiences()
        for exp in experiences:
            result = detector.check(exp.instruction)
            assert not result.leaked, (
                f"Near-duplicate match ({result.match_type}) for: {exp.instruction[:80]}..."
            )

    def test_leakage_detection_loads_eval_cases(self):
        from agentcore.training.leakage import LeakageDetector

        detector = LeakageDetector(eval_path=r"C:\EraAI\evaluation\eval_cases.jsonl")
        detector.load()
        assert detector.eval_case_count == 55
        assert len(detector.eval_categories) > 0


class TestDuplicateDetection:
    """Tests for duplicate detection (Step 8)."""

    def test_identical_experiences_produce_same_hash(self):
        exp1 = Experience(
            instruction="Test question about memory?",
            output="AgentCore memory is a persistent store.",
            source="test",
            domains=["memory"],
        )
        exp2 = Experience(
            instruction="Test question about memory?",
            output="AgentCore memory is a persistent store.",
            source="test",
            domains=["memory"],
        )
        assert exp1.experience_id == exp2.experience_id

    def test_different_experiences_have_different_hashes(self):
        exp1 = Experience(
            instruction="Question A?",
            output="Answer A.",
            source="test",
            domains=["memory"],
        )
        exp2 = Experience(
            instruction="Question B?",
            output="Answer B.",
            source="test",
            domains=["memory"],
        )
        assert exp1.experience_id != exp2.experience_id

    def test_content_hash_normalizes_whitespace(self):
        from agentcore.training.leakage import _content_hash

        hash1 = _content_hash("hello world")
        hash2 = _content_hash("  hello   world  ")
        assert hash1 == hash2


class TestNormalizedPromptMatching:
    """Tests for normalized prompt matching (Step 8)."""

    def test_normalize_lowercases(self):
        from agentcore.training.leakage import _normalize_text

        assert _normalize_text("HELLO World") == "hello world"

    def test_normalize_removes_punctuation(self):
        from agentcore.training.leakage import _normalize_text

        assert _normalize_text("What? Is this...") == "what is this"

    def test_normalize_collapses_whitespace(self):
        from agentcore.training.leakage import _normalize_text

        assert _normalize_text("hello    world") == "hello world"

    def test_normalize_strips_leading_trailing(self):
        from agentcore.training.leakage import _normalize_text

        assert _normalize_text("  hello  ") == "hello"


class TestSecretDetection:
    """Tests for secret detection (quality gate)."""

    def test_dataset_contains_no_secrets(self):
        examples, _, _ = build_dataset(apply_quality_gate=True)
        import re

        secret_patterns = [
            r"(?i)api[_-]?key\s*[:=]\s*['\"][a-zA-Z0-9]{20,}",
            r"(?i)secret\s*[:=]\s*['\"][a-zA-Z0-9]{8,}",
            r"(?i)password\s*[:=]\s*['\"][^\s'\"]+",
            r"sk-[a-zA-Z0-9]{20,}",
        ]
        for ex in examples:
            text = ex.instruction + " " + ex.output
            for pattern in secret_patterns:
                matches = re.findall(pattern, text)
                assert not matches, (
                    f"Secret pattern {pattern} found in example {ex.example_id}: {matches}"
                )

    def test_dataset_contains_no_pii(self):
        examples, _, _ = build_dataset(apply_quality_gate=True)
        import re

        pii_patterns = [
            r"\b\d{3}-\d{2}-\d{4}\b",
            r"\b\d{3}-\d{3}-\d{4}\b",
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        ]
        for ex in examples:
            text = ex.instruction + " " + ex.output
            for pattern in pii_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                assert not matches, f"PII pattern {pattern} found in example {ex.example_id}"


class TestDeterministicGeneration:
    """Tests that dataset generation is deterministic."""

    def test_repeated_builds_produce_same_candidates(self):
        experiences = get_all_experiences()
        ids1 = sorted(e.experience_id for e in experiences)

        experiences2 = get_all_experiences()
        ids2 = sorted(e.experience_id for e in experiences2)

        assert ids1 == ids2, "get_all_experiences() is not deterministic"

    def test_build_dataset_is_idempotent(self):
        examples1, _, stats1 = build_dataset(apply_quality_gate=True)
        examples2, _, stats2 = build_dataset(apply_quality_gate=True)

        assert len(examples1) == len(examples2)
        assert stats1.total_examples == stats2.total_examples
        assert stats1.avg_quality == stats2.avg_quality
