"""Tests for Phase 6A leakage detection."""

import json
import os

import pytest

from agentcore.training.leakage import (
    EvalCase,
    LeakageDetector,
    _content_hash,
    _jaccard_similarity,
    _normalize_text,
    _overlap_coefficient,
)


@pytest.fixture
def eval_file(tmp_path):
    """Create a temporary eval file for testing."""
    cases = [
        {"id": "test-001", "category": "memory", "prompt": "What is memory?"},
        {"id": "test-002", "category": "runtime", "prompt": "What is a runtime?"},
        {
            "id": "test-003",
            "category": "cancellation",
            "prompt": "How does cancellation work?",
        },
    ]
    path = tmp_path / "eval_cases.jsonl"
    with open(path, "w") as f:
        f.writelines(json.dumps(case) + "\n" for case in cases)
    return str(path)


@pytest.fixture
def real_eval_file():
    return r"C:\EraAI\evaluation\eval_cases.jsonl"


class TestLeakageDetector:
    def test_exact_match_detected(self, eval_file):
        detector = LeakageDetector(eval_path=eval_file)
        detector.load()
        result = detector.check("What is memory?", "")
        assert result.leaked is True
        assert result.match_type == "exact"
        assert result.eval_case_id == "test-001"

    def test_exact_match_case_insensitive(self, eval_file):
        detector = LeakageDetector(eval_path=eval_file)
        detector.load()
        result = detector.check("WHAT IS MEMORY?", "")
        assert result.leaked is True
        assert result.match_type == "exact"

    def test_no_match_returns_clean(self, eval_file):
        detector = LeakageDetector(eval_path=eval_file)
        detector.load()
        result = detector.check("This is a completely different question", "")
        assert result.leaked is False
        assert result.reason == ""

    def test_normalized_match_detected(self, eval_file):
        detector = LeakageDetector(eval_path=eval_file)
        detector.load()
        result = detector.check("  What   is  memory?  ", "")
        assert result.leaked is True
        assert result.match_type == "normalized"

    def test_near_duplicate_detected(self, eval_file):
        detector = LeakageDetector(
            eval_path=eval_file,
            near_duplicate_threshold=0.80,
        )
        detector.load()
        # "what is memory" vs "what is memory in agent" — high token overlap
        result = detector.check("what is memory in agentcore", "")
        assert result.leaked is True
        assert result.match_type == "near_duplicate"

    def test_different_prompt_not_flagged(self, eval_file):
        detector = LeakageDetector(eval_path=eval_file)
        detector.load()
        result = detector.check("Describe the memory backend abstraction", "")
        assert result.leaked is False

    def test_real_eval_cases_loaded(self, real_eval_file):
        if not os.path.exists(real_eval_file):
            pytest.skip("Real eval file not available")
        detector = LeakageDetector(eval_path=real_eval_file)
        detector.load()
        assert detector.eval_case_count == 55

    def test_eval_categories_loaded(self, real_eval_file):
        if not os.path.exists(real_eval_file):
            pytest.skip("Real eval file not available")
        detector = LeakageDetector(eval_path=real_eval_file)
        detector.load()
        cats = detector.eval_categories
        assert len(cats) >= 10
        assert "memory" in cats

    def test_training_candidates_have_zero_leakage(self, real_eval_file):
        if not os.path.exists(real_eval_file):
            pytest.skip("Real eval file not available")
        from agentcore.training.candidates import get_all_experiences

        detector = LeakageDetector(eval_path=real_eval_file)
        detector.load()
        for exp in get_all_experiences():
            result = detector.check(exp.instruction)
            assert not result.leaked, (
                f"Leakage detected: {result.reason} for: {exp.instruction[:60]}"
            )

    def test_file_not_found_raises(self):
        detector = LeakageDetector(eval_path="/nonexistent/path.jsonl")
        with pytest.raises(FileNotFoundError):
            detector.load()


class TestEvalCase:
    def test_from_dict(self):
        data = {
            "id": "test-001",
            "category": "memory",
            "prompt": "What is memory?",
            "expected_concepts": ["memory"],
            "forbidden_concepts": ["runtime"],
        }
        case = EvalCase.from_dict(data)
        assert case.case_id == "test-001"
        assert case.category == "memory"
        assert case.prompt == "What is memory?"
        assert case.normalized_prompt == "what is memory"
        assert case.tokens == {"what", "is", "memory"}

    def test_from_dict_with_alternate_keys(self):
        data = {
            "case_id": "test-002",
            "instruction": "What is this?",
        }
        case = EvalCase.from_dict(data)
        assert case.case_id == "test-002"
        assert case.prompt == "What is this?"


class TestNormalization:
    def test_lowercase(self):
        assert _normalize_text("HELLO World") == "hello world"

    def test_remove_punctuation(self):
        assert _normalize_text("What? Is this...") == "what is this"

    def test_collapse_whitespace(self):
        assert _normalize_text("hello    world") == "hello world"

    def test_strip(self):
        assert _normalize_text("  hello  ") == "hello"


class TestContentHash:
    def test_same_text_same_hash(self):
        assert _content_hash("hello") == _content_hash("hello")

    def test_different_text_different_hash(self):
        assert _content_hash("hello") != _content_hash("world")

    def test_normalized_text_same_hash(self):
        assert _content_hash("hello") == _content_hash("  HELLO  ")


class TestJaccardSimilarity:
    def test_identical_sets(self):
        tokens = {"a", "b", "c"}
        assert _jaccard_similarity(tokens, tokens) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard_similarity({"a"}, {"b"}) == 0.0

    def test_partial_overlap(self):
        sim = _jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert sim == 2 / 4  # intersection=2, union=4

    def test_empty_sets(self):
        assert _jaccard_similarity(set(), set()) == 1.0
        assert _jaccard_similarity(set(), {"a"}) == 0.0


class TestOverlapCoefficient:
    def test_identical_sets(self):
        tokens = {"a", "b", "c"}
        assert _overlap_coefficient(tokens, tokens) == 1.0

    def test_disjoint_sets(self):
        assert _overlap_coefficient({"a"}, {"b"}) == 0.0

    def test_subset_detected_as_duplicate(self):
        superset = {"what", "is", "memory", "in", "agentcore"}
        subset = {"what", "is", "memory"}
        assert _overlap_coefficient(superset, subset) == 1.0

    def test_empty_sets(self):
        assert _overlap_coefficient(set(), set()) == 1.0
        assert _overlap_coefficient(set(), {"a"}) == 0.0
