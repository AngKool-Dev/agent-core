"""Tests for Phase 6A Experience and CorrectionPair data models."""

from agentcore.training.experience import CorrectionPair, Experience


class TestExperience:
    def test_experience_creation(self):
        exp = Experience(
            instruction="What is memory?",
            output="Memory is a persistent store.",
            source="test",
            domains=["memory"],
        )
        assert exp.instruction == "What is memory?"
        assert exp.output == "Memory is a persistent store."
        assert exp.source == "test"
        assert exp.domains == ["memory"]
        assert exp.experience_id != ""

    def test_experience_id_is_deterministic(self):
        exp1 = Experience(instruction="Test", output="Answer", source="test")
        exp2 = Experience(instruction="Test", output="Answer", source="test")
        assert exp1.experience_id == exp2.experience_id

    def test_experience_to_dict(self):
        exp = Experience(
            instruction="Test?",
            output="Test answer.",
            source="test",
            domains=["memory"],
            metadata={"key": "value"},
        )
        d = exp.to_dict()
        assert d["instruction"] == "Test?"
        assert d["output"] == "Test answer."
        assert d["source"] == "test"
        assert d["domains"] == ["memory"]
        assert d["metadata"]["key"] == "value"
        assert d["experience_id"] != ""

    def test_experience_from_dict(self):
        exp = Experience(
            instruction="Test?",
            output="Test answer.",
            source="test",
            domains=["memory"],
            metadata={"key": "value"},
            experience_id="abc123",
        )
        d = exp.to_dict()
        restored = Experience.from_dict(d)
        assert restored.instruction == "Test?"
        assert restored.experience_id == "abc123"

    def test_auto_generated_id_when_empty(self):
        exp = Experience(instruction="Test", output="Answer")
        assert exp.experience_id != ""
        assert len(exp.experience_id) == 16


class TestCorrectionPair:
    def test_correction_pair_creation(self):
        pair = CorrectionPair(
            instruction="What is memory?",
            wrong_output="Memory is just RAM.",
            correct_output="Memory is a persistent store.",
            rationale="RAM is volatile, memory is not.",
            domains=["memory"],
        )
        assert pair.instruction == "What is memory?"
        assert pair.wrong_output == "Memory is just RAM."
        assert pair.correct_output == "Memory is a persistent store."
        assert pair.rationale == "RAM is volatile, memory is not."

    def test_correction_to_experience_correct(self):
        pair = CorrectionPair(
            instruction="Test?",
            wrong_output="Wrong answer.",
            correct_output="Correct answer.",
            rationale="Because reasons.",
            domains=["memory"],
        )
        exp = pair.to_experience_correct()
        assert exp.instruction == "Test?"
        assert exp.output == "Correct answer."
        assert exp.metadata["is_correction"] is True

    def test_correction_pair_ids_are_different(self):
        pair = CorrectionPair(
            instruction="Test?",
            wrong_output="Wrong answer.",
            correct_output="Correct answer.",
            rationale="Because.",
            domains=["memory"],
        )
        correct_exp = pair.to_experience_correct()
        wrong_exp = pair.to_experience_wrong()
        assert correct_exp.experience_id != wrong_exp.experience_id

    def test_correction_pair_has_verified_outcome(self):
        pair = CorrectionPair(
            instruction="Test?",
            wrong_output="Wrong.",
            correct_output="Correct.",
            rationale="Because.",
            domains=["memory"],
        )
        exp = pair.to_experience_correct()
        assert exp.metadata.get("has_verified_outcome") is True
