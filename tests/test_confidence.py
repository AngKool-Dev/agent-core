"""
Tests for MemoryConfidence and MemoryConfidenceClassifier (Phase 5E).

Verifies:
* MemoryConfidence enum values
* MemoryCandidate contains confidence fields
* Confidence serialization roundtrip
* Classification rules: verified, claimed, inferred, unknown
* Safety: confident text does not imply verified
* Determinism: same observations produce same confidence
* Candidate ID stability: confidence does not change identity
* Persistence: confidence survives through metadata
* Integration: automatic harvest includes confidence
"""

import uuid
from typing import Any

from agentcore.harvesting import (
    MemoryCandidate,
    MemoryConfidenceClassifier,
    MemoryHarvester,
    _confidence_to_float,
    _generate_candidate_id,
)
from agentcore.memory import InMemoryBackend, MemoryConfidence, MemoryType
from agentcore.observations import (
    InMemoryObservationStore,
    Observation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _CapturingBackend(InMemoryBackend):
    """Backend that captures stored metadata for assertions."""

    def __init__(self):
        super().__init__()
        self.stored: list[dict[str, Any]] = []

    def store(self, type, content, project=None, importance=0.5, confidence=0.5):
        result = super().store(type, content, project, importance, confidence)
        self.stored.append(result)
        return result


class _DedupingCapturingBackend(_CapturingBackend):
    """Backend that mimics db_obsidian dedupe: same content_hash + project + type
    returns the existing record instead of creating a new one."""

    def store(self, type, content, project=None, importance=0.5, confidence=0.5):
        for existing in self._records.values():
            if (
                existing.get("content") == content
                and existing.get("project") == project
                and existing.get("type") == type
            ):
                self.stored.append(dict(existing))
                return dict(existing)
        return super().store(type, content, project, importance, confidence)


def _make_observation(
    task_id="task-1",
    session_id="session-1",
    observation_type="task.completed",
    payload=None,
    metadata=None,
    observation_id=None,
):
    return {
        "id": observation_id or f"obs-{uuid.uuid4().hex[:12]}",
        "task_id": task_id,
        "session_id": session_id,
        "observation_type": observation_type,
        "payload": payload or {},
        "metadata": metadata or {},
        "timestamp": "2024-01-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Enum/model tests
# ---------------------------------------------------------------------------


def test_memory_confidence_values():
    assert MemoryConfidence.CLAIMED.value == "claimed"
    assert MemoryConfidence.VERIFIED.value == "verified"
    assert MemoryConfidence.INFERRED.value == "inferred"
    assert MemoryConfidence.UNKNOWN.value == "unknown"


def test_memory_candidate_contains_confidence():
    candidate = MemoryCandidate(
        id="mem-1",
        task_id="task-1",
        session_id="session-1",
        source_observation_ids=["obs-1"],
        memory_type=MemoryType.TASK.value,
        content="Task completed: test",
        metadata={},
        created_at="2024-01-01T00:00:00+00:00",
        confidence=MemoryConfidence.VERIFIED,
        confidence_reason="test reason",
    )
    assert candidate.confidence == MemoryConfidence.VERIFIED
    assert candidate.confidence_reason == "test reason"


def test_confidence_serialization_roundtrip():
    candidate = MemoryCandidate(
        id="mem-1",
        task_id="task-1",
        session_id="session-1",
        source_observation_ids=["obs-1"],
        memory_type=MemoryType.TASK.value,
        content="Task completed: test",
        metadata={"confidence": "verified", "confidence_reason": "test"},
        created_at="2024-01-01T00:00:00+00:00",
        confidence=MemoryConfidence.VERIFIED,
        confidence_reason="test reason",
    )
    meta = dict(candidate.metadata)
    assert meta["confidence"] == "verified"
    assert meta["confidence_reason"] == "test"
    assert candidate.confidence.value == "verified"


# ---------------------------------------------------------------------------
# Classification: VERIFIED
# ---------------------------------------------------------------------------


def test_verified_tool_result_with_explicit_signal():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="tool_call.completed",
        payload={
            "name": "test_runner",
            "result": "All tests passed",
            "verified": True,
        },
    )
    confidence, reason = classifier.classify(
        obs, MemoryType.FACT.value, "Tool test_runner returned: All tests passed"
    )
    assert confidence == MemoryConfidence.VERIFIED
    assert "verified" in reason.lower()


def test_verified_structured_exit_code():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="tool_call.completed",
        payload={
            "name": "shell",
            "result": "done",
            "exit_code": 0,
        },
    )
    confidence, reason = classifier.classify(
        obs, MemoryType.FACT.value, "Tool shell returned: done"
    )
    assert confidence == MemoryConfidence.VERIFIED
    assert "exit_code" in reason


def test_verified_explicit_verification_in_text():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="tool_call.completed",
        payload={
            "name": "validator",
            "result": "validation passed successfully",
        },
    )
    confidence, reason = classifier.classify(
        obs, MemoryType.FACT.value, "Tool validator returned: validation passed successfully"
    )
    assert confidence == MemoryConfidence.VERIFIED
    assert "validation passed" in reason


def test_verified_success_in_result_key():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="tool_call.completed",
        payload={
            "name": "builder",
            "result": "build completed successfully",
        },
    )
    confidence, reason = classifier.classify(
        obs, MemoryType.FACT.value, "Tool builder returned: build completed successfully"
    )
    assert confidence == MemoryConfidence.VERIFIED
    assert "completed successfully" in reason


# ---------------------------------------------------------------------------
# Classification: CLAIMED
# ---------------------------------------------------------------------------


def test_claimed_task_completion():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="task.completed",
        payload={"result": "File processed successfully"},
    )
    confidence, reason = classifier.classify(
        obs, MemoryType.TASK.value, "Task completed: File processed successfully"
    )
    assert confidence == MemoryConfidence.CLAIMED
    assert "completion result" in reason


def test_claimed_tool_result_without_verification():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="tool_call.completed",
        payload={
            "name": "reader",
            "output": "File contains 42 lines of text",
        },
    )
    confidence, reason = classifier.classify(
        obs, MemoryType.FACT.value, "Tool reader returned: File contains 42 lines of text"
    )
    assert confidence == MemoryConfidence.CLAIMED
    assert "explicit tool result" in reason


def test_claimed_runtime_error():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="runtime.error",
        payload={"error": "Connection timeout"},
    )
    confidence, reason = classifier.classify(
        obs, MemoryType.ERROR.value, "Runtime error: Connection timeout"
    )
    assert confidence == MemoryConfidence.CLAIMED
    assert "error report" in reason


# ---------------------------------------------------------------------------
# Classification: INFERRED
# ---------------------------------------------------------------------------


def test_inferred_multi_observation_memory():
    classifier = MemoryConfidenceClassifier()
    obs1 = _make_observation(
        observation_type="tool_call.completed",
        payload={"name": "reader", "result": "File read successfully with data"},
    )
    obs2 = _make_observation(
        observation_type="tool_call.completed",
        payload={"name": "writer", "result": "File written successfully"},
    )
    confidence1, _reason1 = classifier.classify(
        obs1, MemoryType.FACT.value, "Tool reader returned: File read successfully with data"
    )
    confidence2, reason2 = classifier.classify(
        obs2,
        MemoryType.FACT.value,
        "Tool writer returned: File written successfully",
        related_observation_count=2,
    )
    assert confidence1 == MemoryConfidence.CLAIMED
    assert confidence2 == MemoryConfidence.INFERRED
    assert "2 related observations" in reason2


# ---------------------------------------------------------------------------
# Classification: UNKNOWN
# ---------------------------------------------------------------------------


def test_unknown_malformed_observation():
    classifier = MemoryConfidenceClassifier()
    confidence, reason = classifier.classify(
        "not-a-dict",
        MemoryType.FACT.value,
        "Some content",
    )
    assert confidence == MemoryConfidence.UNKNOWN
    assert "malformed" in reason


def test_unknown_insufficient_evidence():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="tool_call.completed",
        payload={"name": "reader", "result": "ok"},
    )
    confidence, reason = classifier.classify(obs, MemoryType.FACT.value, "Tool reader returned: ok")
    assert confidence == MemoryConfidence.UNKNOWN
    assert "insufficient evidence" in reason


def test_unknown_empty_payload():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="tool_call.completed",
        payload={},
    )
    confidence, reason = classifier.classify(obs, MemoryType.FACT.value, "Tool  returned: ")
    assert confidence == MemoryConfidence.UNKNOWN
    assert "insufficient evidence" in reason


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------


def test_confident_text_does_not_imply_verified():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="task.completed",
        payload={"result": "Everything is verified and all tests passed!"},
    )
    confidence, reason = classifier.classify(
        obs, MemoryType.TASK.value, "Task completed: Everything is verified and all tests passed!"
    )
    assert confidence == MemoryConfidence.CLAIMED
    assert "completion result" in reason


def test_done_message_is_not_verified():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="task.completed",
        payload={"result": "Done"},
    )
    confidence, _reason = classifier.classify(obs, MemoryType.TASK.value, "Task completed: Done")
    assert confidence == MemoryConfidence.UNKNOWN


def test_ambiguous_result_is_not_verified():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="tool_call.completed",
        payload={"name": "tool", "result": "operation success"},
    )
    confidence, reason = classifier.classify(
        obs, MemoryType.FACT.value, "Tool tool returned: operation success"
    )
    assert confidence == MemoryConfidence.CLAIMED
    assert "explicit tool result" in reason


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


def test_same_observations_produce_same_confidence():
    classifier = MemoryConfidenceClassifier()
    obs1 = _make_observation(
        observation_type="tool_call.completed",
        payload={"name": "reader", "result": "File contains data", "exit_code": 0},
    )
    obs2 = _make_observation(
        observation_type="tool_call.completed",
        payload={"name": "reader", "result": "File contains data", "exit_code": 0},
    )
    c1, r1 = classifier.classify(
        obs1, MemoryType.FACT.value, "Tool reader returned: File contains data"
    )
    c2, r2 = classifier.classify(
        obs2, MemoryType.FACT.value, "Tool reader returned: File contains data"
    )
    assert c1 == c2
    assert r1 == r2


def test_candidate_id_does_not_change_with_confidence():
    classifier = MemoryConfidenceClassifier()
    obs = _make_observation(
        observation_type="tool_call.completed",
        payload={"name": "reader", "result": "File contains data"},
    )
    content = "Tool reader returned: File contains data"
    candidate_id = _generate_candidate_id("task-1", MemoryType.FACT.value, content)
    confidence1, _ = classifier.classify(obs, MemoryType.FACT.value, content)
    confidence2, _ = classifier.classify(obs, MemoryType.FACT.value, content)
    assert confidence1 == confidence2
    assert candidate_id == _generate_candidate_id("task-1", MemoryType.FACT.value, content)


def test_repeated_harvest_preserves_identity():
    store = InMemoryObservationStore()
    backend = _CapturingBackend()
    harvester = MemoryHarvester(store, backend)

    store.add(
        Observation(
            id="obs-1",
            task_id="task-1",
            session_id="session-1",
            observation_type="tool_call.completed",
            payload={"name": "reader", "result": "File contains data", "exit_code": 0},
        )
    )

    result1 = harvester.harvest_task("task-1")
    result2 = harvester.harvest_task("task-1")

    assert len(result1.candidates) == 1
    assert len(result2.candidates) == 1
    assert result1.candidates[0].id == result2.candidates[0].id
    assert result1.candidates[0].confidence == result2.candidates[0].confidence


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------


def test_confidence_survives_through_metadata():
    store = InMemoryObservationStore()
    backend = _CapturingBackend()
    harvester = MemoryHarvester(store, backend)

    store.add(
        Observation(
            id="obs-1",
            task_id="task-1",
            session_id="session-1",
            observation_type="tool_call.completed",
            payload={"name": "reader", "result": "File contains data", "exit_code": 0},
        )
    )

    result = harvester.harvest_task("task-1")
    assert len(result.candidates) == 1
    assert len(backend.stored) == 1
    assert backend.stored[0]["confidence"] == 1.0


def test_confidence_reason_survives_through_metadata():
    store = InMemoryObservationStore()
    backend = _CapturingBackend()
    harvester = MemoryHarvester(store, backend)

    store.add(
        Observation(
            id="obs-1",
            task_id="task-1",
            session_id="session-1",
            observation_type="task.completed",
            payload={"result": "File processed successfully"},
        )
    )

    result = harvester.harvest_task("task-1")
    assert len(result.candidates) == 1
    assert len(backend.stored) == 1
    candidate = result.candidates[0]
    assert candidate.confidence == MemoryConfidence.CLAIMED
    assert "explicit task completion result" in candidate.confidence_reason
    # Confidence reason should NOT pollute the stored content
    assert "confidence:" not in backend.stored[0]["content"]
    assert "reason:" not in backend.stored[0]["content"]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


def test_harvest_includes_confidence():
    store = InMemoryObservationStore()
    backend = _CapturingBackend()
    harvester = MemoryHarvester(store, backend)

    store.add(
        Observation(
            id="obs-1",
            task_id="task-1",
            session_id="session-1",
            observation_type="task.completed",
            payload={"result": "Export finished"},
        )
    )

    result = harvester.harvest_task("task-1")
    assert len(result.candidates) == 1
    assert result.candidates[0].confidence in (
        MemoryConfidence.CLAIMED,
        MemoryConfidence.VERIFIED,
        MemoryConfidence.INFERRED,
        MemoryConfidence.UNKNOWN,
    )
    assert result.candidates[0].confidence_reason != ""


def test_harvest_failure_still_isolated():
    class FailingBackend(InMemoryBackend):
        def store(self, type, content, project=None, importance=0.5, confidence=0.5):
            raise RuntimeError("db dead")

    store = InMemoryObservationStore()
    backend = FailingBackend()
    harvester = MemoryHarvester(store, backend)

    store.add(
        Observation(
            id="obs-1",
            task_id="task-1",
            session_id="session-1",
            observation_type="task.completed",
            payload={"result": "Export finished"},
        )
    )

    result = harvester.harvest_task("task-1")
    assert len(result.candidates) == 1
    assert len(result.errors) >= 1
    assert "db dead" in result.errors[0]


def test_terminal_task_state_unchanged_by_classification():
    store = InMemoryObservationStore()
    backend = _CapturingBackend()
    harvester = MemoryHarvester(store, backend)

    store.add(
        Observation(
            id="obs-1",
            task_id="task-1",
            session_id="session-1",
            observation_type="task.completed",
            payload={"result": "Export finished"},
        )
    )

    result = harvester.harvest_task("task-1")
    assert len(result.candidates) == 1
    assert result.task_id == "task-1"


# ---------------------------------------------------------------------------
# Confidence ordering tests
# ---------------------------------------------------------------------------


def test_confidence_ordering():
    """Verify confidence levels have a defined ordering."""
    levels = [
        MemoryConfidence.UNKNOWN,
        MemoryConfidence.INFERRED,
        MemoryConfidence.CLAIMED,
        MemoryConfidence.VERIFIED,
    ]
    for i in range(len(levels) - 1):
        assert levels[i].value != levels[i + 1].value


# ---------------------------------------------------------------------------
# Confidence float mapping tests
# ---------------------------------------------------------------------------


def test_confidence_to_float_mapping():
    assert _confidence_to_float(MemoryConfidence.VERIFIED) == 1.0
    assert _confidence_to_float(MemoryConfidence.CLAIMED) == 0.7
    assert _confidence_to_float(MemoryConfidence.INFERRED) == 0.5
    assert _confidence_to_float(MemoryConfidence.UNKNOWN) == 0.3


# ---------------------------------------------------------------------------
# Monotonic confidence upgrade tests
# ---------------------------------------------------------------------------


def test_confidence_upgrade_on_repeated_harvest():
    """A second store with higher confidence should upgrade the stored memory.

    Uses a deduping backend so that the second store() returns the existing
    memory (with old, lower confidence).  _persist_candidates should then
    call update_confidence to raise the confidence.
    """
    backend = _DedupingCapturingBackend()
    harvester = MemoryHarvester(InMemoryObservationStore(), backend)

    base_content = "Task completed: Export finished successfully"
    candidate_low = MemoryCandidate(
        id=_generate_candidate_id("task-1", MemoryType.TASK.value, base_content),
        task_id="task-1",
        session_id="session-1",
        source_observation_ids=["obs-1"],
        memory_type=MemoryType.TASK.value,
        content=base_content,
        metadata={"source": "observation", "observation_type": "task.completed"},
        created_at="2024-01-01T00:00:00+00:00",
        confidence=MemoryConfidence.CLAIMED,
        confidence_reason="explicit task completion result",
    )
    harvester._persist_candidates([candidate_low], [])
    assert backend.stored[0]["confidence"] == 0.7

    # Second: same content, higher confidence — backend dedupes, upgrade triggers
    candidate_high = MemoryCandidate(
        id=_generate_candidate_id("task-1", MemoryType.TASK.value, base_content),
        task_id="task-1",
        session_id="session-1",
        source_observation_ids=["obs-2"],
        memory_type=MemoryType.TASK.value,
        content=base_content,
        metadata={
            "source": "observation",
            "observation_type": "task.completed",
            "confidence": "verified",
            "confidence_reason": "exit_code == 0",
        },
        created_at="2024-01-01T00:01:00+00:00",
        confidence=MemoryConfidence.VERIFIED,
        confidence_reason="tool returned structured success indicator",
    )
    harvester._persist_candidates([candidate_high], [])

    all_records = list(backend._records.values())
    assert len(all_records) == 1
    assert all_records[0]["confidence"] == 1.0


def test_confidence_upgrade_via_update_confidence():
    """Direct update_confidence should raise stored confidence."""
    backend = InMemoryBackend()
    result = backend.store("fact", "Test memory", confidence=0.5)
    memory_id = result["id"]

    updated = backend.update_confidence(memory_id, 1.0, "verification signal detected")
    assert updated is not None
    assert updated["confidence"] == 1.0
    assert updated.get("confidence_reason") == "verification signal detected"


def test_update_confidence_on_unknown_id_returns_none():
    backend = InMemoryBackend()
    result = backend.update_confidence("nonexistent-id", 1.0)
    assert result is None


def test_update_confidence_does_not_downgrade():
    """Monotonic upgrades only go up; existing higher confidence is preserved on dedupe."""
    store = InMemoryObservationStore()
    backend = _DedupingCapturingBackend()
    harvester = MemoryHarvester(store, backend)

    # First harvest with VERIFIED confidence (1.0)
    obs_verified = Observation(
        id="obs-v",
        task_id="task-1",
        session_id="session-1",
        observation_type="tool_call.completed",
        payload={"name": "tool", "result": "All tests passed", "exit_code": 0},
    )
    store.add(obs_verified)
    result1 = harvester.harvest_task("task-1")
    assert result1.candidates[0].confidence == MemoryConfidence.VERIFIED
    assert backend.stored[0]["confidence"] == 1.0

    # Second harvest with same content but CLAIMED confidence — should NOT downgrade
    obs_claimed = Observation(
        id="obs-c",
        task_id="task-1",
        session_id="session-1",
        observation_type="tool_call.completed",
        payload={"name": "tool", "result": "All tests passed"},
    )
    store.add(obs_claimed)
    harvester.harvest_task("task-1")

    final = backend.stored[-1]
    assert final["confidence"] == 1.0


# ---------------------------------------------------------------------------
# Content identity tests
# ---------------------------------------------------------------------------


def test_candidate_id_independent_of_confidence():
    """Different confidence levels for same content must produce same candidate ID."""
    content = "Tool reader returned: File contains data"
    candidate_id = _generate_candidate_id("task-1", MemoryType.FACT.value, content)

    obs_verified = _make_observation(
        observation_type="tool_call.completed",
        payload={"name": "reader", "result": "File contains data", "exit_code": 0},
    )
    conf1, _ = MemoryConfidenceClassifier().classify(obs_verified, MemoryType.FACT.value, content)

    obs_claimed = _make_observation(
        observation_type="tool_call.completed",
        payload={"name": "reader", "result": "File contains data"},
    )
    conf2, _ = MemoryConfidenceClassifier().classify(obs_claimed, MemoryType.FACT.value, content)

    assert conf1 != conf2
    assert _generate_candidate_id("task-1", MemoryType.FACT.value, content) == candidate_id


# ---------------------------------------------------------------------------
# Failure isolation tests
# ---------------------------------------------------------------------------


def test_confidence_upgrade_failure_is_isolated():
    """If update_confidence fails, it must not crash the harvest or lose the store result."""

    class BrokenUpdateBackend(_DedupingCapturingBackend):
        def update_confidence(self, memory_id, confidence, reason=""):
            raise RuntimeError("update_confidence broken")

    store = InMemoryObservationStore()
    backend = BrokenUpdateBackend()
    harvester = MemoryHarvester(store, backend)

    obs = Observation(
        id="obs-1",
        task_id="task-1",
        session_id="session-1",
        observation_type="tool_call.completed",
        payload={"name": "tool", "result": "All tests passed", "exit_code": 0},
    )
    store.add(obs)

    result = harvester.harvest_task("task-1")
    assert len(result.candidates) == 1
    assert len(result.errors) == 0
    assert backend.stored[0]["confidence"] == 1.0


# ---------------------------------------------------------------------------
# MemoryBackend.update_confidence interface test
# ---------------------------------------------------------------------------


def test_update_confidence_optional_on_interface():
    """MemoryBackend.update_confidence should have a default no-op implementation."""
    from agentcore.memory import MemoryBackend

    class MinimalBackend(MemoryBackend):
        def search(self, query, project=None, limit=20):
            return []

        def store(self, type, content, project=None, importance=0.5, confidence=0.5):
            return {"id": "x"}

        def update(self, memory_id, content):
            return {}

        def list(self, project=None, type=None, limit=50):
            return []

    backend = MinimalBackend()
    assert backend.update_confidence("x", 1.0) is None


def test_in_memory_backend_update_confidence_roundtrip():
    """InMemoryBackend.update_confidence should persist the new confidence."""
    backend = InMemoryBackend()
    result = backend.store("fact", "test content", confidence=0.3)
    mid = result["id"]

    updated = backend.update_confidence(mid, 0.9, "upgraded")
    assert updated["confidence"] == 0.9
    assert updated["confidence_reason"] == "upgraded"

    listed = backend.list()
    found = next(m for m in listed if m["id"] == mid)
    assert found["confidence"] == 0.9
