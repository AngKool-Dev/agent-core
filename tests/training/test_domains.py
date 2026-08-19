"""
Tests for Phase 6A domain classification.

Covers:
- domain classification
- multi-domain classification
"""

from agentcore.training.domains import (
    DOMAIN_KEYWORDS,
    classify_domains,
    classify_domains_set,
)

ALL_DOMAINS = [
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


class TestDomainClassification:
    """Tests for deterministic domain classification."""

    def test_single_domain_classification(self):
        domains = classify_domains("What is AgentCore memory?")
        assert "memory" in domains
        assert "architecture" in domains

    def test_multi_domain_classification(self):
        text = "Cancel memory and propagate to runtime"
        domains = classify_domains(text)
        assert "cancellation" in domains
        assert "memory" in domains
        assert "runtime" in domains

    def test_all_domains_have_keywords(self):
        for domain in ALL_DOMAINS:
            assert domain in DOMAIN_KEYWORDS, f"Domain '{domain}' missing from DOMAIN_KEYWORDS"
            assert len(DOMAIN_KEYWORDS[domain]) > 0, f"Domain '{domain}' has no keywords"

    def test_empty_text_returns_empty(self):
        domains = classify_domains("")
        assert domains == []

    def test_unrelated_text_returns_empty(self):
        domains = classify_domains("banana purple elephant purplebanana")
        assert domains == []

    def test_domain_set_matches_list(self):
        text = "AgentCore memory runtime cancellation"
        as_list = classify_domains(text)
        as_set = classify_domains_set(text)
        assert set(as_list) == as_set

    def test_memory_keyword_classification(self):
        text = "memory backend retrieval storage confidence"
        domains = classify_domains(text)
        assert "memory" in domains

    def test_cancellation_keyword_classification(self):
        text = "cancellation propagate terminate interrupt"
        domains = classify_domains(text)
        assert "cancellation" in domains

    def test_runtime_keyword_classification(self):
        text = "runtime adapter execution backend subprocess"
        domains = classify_domains(text)
        assert "runtime" in domains
        assert "runtime_adapter" in domains
