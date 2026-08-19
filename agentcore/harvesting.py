"""
Memory harvesting layer — distills observations into durable memory candidates.

Architecture
------------
    ObservationStore
        ↓
    MemoryHarvester  (deterministic extraction)
        ↓
    MemoryCandidate[]
        ↓
    MemoryBackend  (existing persistence abstraction)

The harvester does NOT import db_obsidian.
It depends only on ObservationStore and MemoryBackend.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from agentcore.memory import MemoryBackend, MemoryConfidence, MemoryType
from agentcore.observations import ObservationStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Memory candidate model
# ---------------------------------------------------------------------------


@dataclass
class MemoryCandidate:
    """A candidate memory extracted from observations."""

    id: str
    task_id: str
    session_id: str
    source_observation_ids: list[str]
    memory_type: str
    content: str
    metadata: dict[str, Any]
    created_at: str
    confidence: MemoryConfidence = MemoryConfidence.UNKNOWN
    confidence_reason: str = ""


# ---------------------------------------------------------------------------
# Harvest result
# ---------------------------------------------------------------------------


@dataclass
class HarvestResult:
    """Result of a harvesting operation."""

    task_id: str
    candidates: list[MemoryCandidate]
    observations_processed: int
    skipped_count: int
    errors: list[str]
    harvested_at: str


# ---------------------------------------------------------------------------
# Confidence mapping
# ---------------------------------------------------------------------------

_CONFIDENCE_FLOAT = {
    MemoryConfidence.VERIFIED: 1.0,
    MemoryConfidence.CLAIMED: 0.7,
    MemoryConfidence.INFERRED: 0.5,
    MemoryConfidence.UNKNOWN: 0.3,
}


def _confidence_to_float(confidence: MemoryConfidence) -> float:
    """Map a MemoryConfidence enum value to its canonical float."""
    return _CONFIDENCE_FLOAT.get(confidence, 0.5)


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------


def _normalize_content(content: str) -> str:
    """Normalize content for deterministic idempotency keys."""
    content = content.strip().lower()
    content = re.sub(r"\s+", " ", content)
    content = re.sub(r"[^\w\s]", "", content)
    return content


def _is_low_information(content: str) -> bool:
    """Filter out low-information content that should not become a memory."""
    if not content or not content.strip():
        return True
    normalized = content.strip().lower()
    low_info_patterns = [
        "ok",
        "ok.",
        "success",
        "success.",
        "done",
        "done.",
        "completed",
        "completed.",
        "finished",
        "finished.",
        "heartbeat",
        "status: ok",
        "no errors",
        "no issues",
    ]
    if normalized in low_info_patterns:
        return True
    if len(normalized) < 10:
        return True
    return False


def _extract_text_from_payload(payload: dict[str, Any]) -> str:
    """Extract meaningful text from an observation payload."""
    if not payload:
        return ""

    candidates = []
    for key in ("result", "output", "content", "message", "error", "summary", "response", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
        elif isinstance(value, dict):
            for sub_key in ("text", "content", "message"):
                sub_value = value.get(sub_key)
                if isinstance(sub_value, str) and sub_value.strip():
                    candidates.append(sub_value.strip())

    if not candidates:
        for key, value in payload.items():
            if isinstance(value, str) and value.strip() and len(value.strip()) > 5:
                candidates.append(value.strip())

    return " ".join(candidates)


def _generate_candidate_id(task_id: str, memory_type: str, content: str) -> str:
    """Generate a deterministic candidate ID for idempotency."""
    normalized = _normalize_content(content)
    key = f"{task_id}:{memory_type}:{normalized}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"mem-{digest}"


# ---------------------------------------------------------------------------
# Confidence classification
# ---------------------------------------------------------------------------

_VERIFIED_SIGNALS = [
    "verified",
    "verification",
    "test passed",
    "tests passed",
    "validation passed",
    "exit_code",
    "exit code",
    "status_code",
    "status code",
    "successfully completed",
    "completed successfully",
    "passed",
    "passed.",
]


def _has_verification_signal(payload: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Check for explicit verification signals in payload.
    Returns (has_signal, reason).
    """
    if not payload:
        return False, None

    payload_lower = {}
    for k, v in payload.items():
        payload_lower[k.lower()] = v

    for signal in _VERIFIED_SIGNALS:
        for key, value in payload_lower.items():
            if signal in key:
                if isinstance(value, bool) and value is True:
                    return True, f"structured field '{key}' is true"
                if isinstance(value, int) and value == 0 and "exit" in key:
                    return True, f"structured field '{key}' == 0"
                if isinstance(value, str) and signal in value.lower():
                    return True, f"structured field '{key}' contains '{signal}'"

    text_fields = []
    for key in ("result", "output", "content", "message", "summary", "response"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            text_fields.append(value.strip().lower())

    for text in text_fields:
        for signal in _VERIFIED_SIGNALS:
            if signal in text:
                return True, f"text contains '{signal}'"

    return False, None


def _has_structured_success(payload: dict[str, Any]) -> bool:
    """Check for structured success indicators."""
    if not payload:
        return False

    payload_lower = {}
    for k, v in payload.items():
        payload_lower[k.lower()] = v

    for key in (
        "exit_code",
        "exit code",
        "status_code",
        "status code",
        "return_code",
        "return code",
    ):
        value = payload_lower.get(key)
        if isinstance(value, int) and value == 0:
            return True
        if isinstance(value, str) and value.strip() == "0":
            return True

    for key in ("success", "passed", "verified", "validated"):
        value = payload_lower.get(key)
        if isinstance(value, bool) and value is True:
            return True

    return False


class MemoryConfidenceClassifier:
    """
    Deterministic classifier for memory candidate confidence.

    Uses observation provenance and payload evidence to assign one of:
    - VERIFIED: execution evidence independently supports the result
    - CLAIMED: explicit statement/result without independent verification
    - INFERRED: derived from multiple observations
    - UNKNOWN: insufficient evidence
    """

    def classify(
        self,
        observation: dict[str, Any],
        memory_type: str,
        content: str,
        related_observation_count: int = 1,
    ) -> tuple[MemoryConfidence, str]:
        """
        Classify confidence for a memory candidate.

        Args:
            observation: The source observation dict
            memory_type: The memory type being classified
            content: The extracted memory content
            related_observation_count: Number of observations contributing

        Returns:
            Tuple of (MemoryConfidence, confidence_reason)
        """
        if not isinstance(observation, dict):
            return MemoryConfidence.UNKNOWN, "malformed observation"

        payload = observation.get("payload", {}) or {}
        if not isinstance(payload, dict):
            return MemoryConfidence.UNKNOWN, "malformed payload"

        observation_type = str(observation.get("observation_type", ""))

        # INFERRED: derived from multiple observations
        if related_observation_count > 1:
            return (
                MemoryConfidence.INFERRED,
                f"derived from {related_observation_count} related observations",
            )

        # VERIFIED checks
        if observation_type == "tool_call.completed":
            has_verified, reason = _has_verification_signal(payload)
            if has_verified:
                return MemoryConfidence.VERIFIED, reason
            if _has_structured_success(payload):
                return (
                    MemoryConfidence.VERIFIED,
                    "tool returned structured success indicator",
                )

        # CLAIMED: explicit statement/result
        if observation_type in ("task.completed", "task.failed", "task.cancelled"):
            text = _extract_text_from_payload(payload)
            if text and not _is_low_information(text):
                return MemoryConfidence.CLAIMED, "explicit task completion result"

        if observation_type == "tool_call.completed":
            text = _extract_text_from_payload(payload)
            if text and not _is_low_information(text):
                return MemoryConfidence.CLAIMED, "explicit tool result"

        if observation_type == "runtime.error":
            text = _extract_text_from_payload(payload)
            if text and not _is_low_information(text):
                return MemoryConfidence.CLAIMED, "explicit error report"

        return MemoryConfidence.UNKNOWN, "insufficient evidence"


# ---------------------------------------------------------------------------
# Extraction rules
# ---------------------------------------------------------------------------

_classifier = MemoryConfidenceClassifier()


def _classify_and_build_candidate(
    observation: dict[str, Any],
    memory_type: str,
    content: str,
    candidate_id: str,
    metadata: dict[str, Any],
) -> MemoryCandidate:
    """Build a MemoryCandidate with confidence classification."""
    confidence, reason = _classifier.classify(
        observation=observation,
        memory_type=memory_type,
        content=content,
        related_observation_count=1,
    )
    meta = dict(metadata)
    meta["confidence"] = confidence.value
    meta["confidence_reason"] = reason
    return MemoryCandidate(
        id=candidate_id,
        task_id=observation.get("task_id", ""),
        session_id=observation.get("session_id", ""),
        source_observation_ids=[observation.get("id", "")],
        memory_type=memory_type,
        content=content,
        metadata=meta,
        created_at=datetime.now(UTC).isoformat(),
        confidence=confidence,
        confidence_reason=reason,
    )


def _extract_task_completed(observation: dict[str, Any]) -> MemoryCandidate | None:
    """Extract a task summary or outcome from a completed task."""
    payload = observation.get("payload", {}) or {}
    metadata = observation.get("metadata", {}) or {}
    task_id = observation.get("task_id", "")
    observation.get("id", "")

    text = _extract_text_from_payload(payload)
    if not text:
        data_text = _extract_text_from_payload(observation.get("data", {}) or {})
        text = data_text

    if _is_low_information(text):
        return None

    content = f"Task completed: {text}"
    return _classify_and_build_candidate(
        observation=observation,
        memory_type=MemoryType.TASK.value,
        content=content,
        candidate_id=_generate_candidate_id(task_id, MemoryType.TASK.value, content),
        metadata={
            "source": "observation",
            "observation_type": "task.completed",
            **{k: v for k, v in metadata.items() if k in ("turn_id", "tool_call_id")},
        },
    )


def _extract_task_failed(observation: dict[str, Any]) -> MemoryCandidate | None:
    """Extract an outcome from a failed task."""
    payload = observation.get("payload", {}) or {}
    metadata = observation.get("metadata", {}) or {}
    task_id = observation.get("task_id", "")
    observation.get("id", "")

    error_text = payload.get("error") or payload.get("message") or ""
    if not error_text:
        error_text = _extract_text_from_payload(payload)

    if not error_text or _is_low_information(error_text):
        return None

    content = f"Task failed: {error_text}"
    return _classify_and_build_candidate(
        observation=observation,
        memory_type=MemoryType.OUTCOME.value,
        content=content,
        candidate_id=_generate_candidate_id(task_id, MemoryType.OUTCOME.value, content),
        metadata={
            "source": "observation",
            "observation_type": "task.failed",
            **{k: v for k, v in metadata.items() if k in ("turn_id", "tool_call_id")},
        },
    )


def _extract_task_cancelled(observation: dict[str, Any]) -> MemoryCandidate | None:
    """Extract an outcome from a cancelled task."""
    payload = observation.get("payload", {}) or {}
    metadata = observation.get("metadata", {}) or {}
    task_id = observation.get("task_id", "")
    observation.get("id", "")

    reason = payload.get("reason") or payload.get("message") or ""
    if not reason:
        reason = _extract_text_from_payload(payload)

    if not reason:
        reason = "Task was cancelled"

    content = f"Task cancelled: {reason}"
    return _classify_and_build_candidate(
        observation=observation,
        memory_type=MemoryType.OUTCOME.value,
        content=content,
        candidate_id=_generate_candidate_id(task_id, MemoryType.OUTCOME.value, content),
        metadata={
            "source": "observation",
            "observation_type": "task.cancelled",
            **{k: v for k, v in metadata.items() if k in ("turn_id", "tool_call_id")},
        },
    )


def _extract_tool_completed(observation: dict[str, Any]) -> MemoryCandidate | None:
    """Extract a fact from a completed tool call, but only if substantive."""
    payload = observation.get("payload", {}) or {}
    metadata = observation.get("metadata", {}) or {}
    task_id = observation.get("task_id", "")
    observation.get("id", "")

    tool_name = payload.get("name") or metadata.get("tool_name") or ""
    result_text = _extract_text_from_payload(payload)

    if not tool_name or not result_text or _is_low_information(result_text):
        return None

    if len(result_text) > 200:
        result_text = result_text[:200] + "..."

    content = f"Tool {tool_name} returned: {result_text}"
    return _classify_and_build_candidate(
        observation=observation,
        memory_type=MemoryType.FACT.value,
        content=content,
        candidate_id=_generate_candidate_id(task_id, MemoryType.FACT.value, content),
        metadata={
            "source": "observation",
            "observation_type": "tool_call.completed",
            "tool_name": tool_name,
            **{k: v for k, v in metadata.items() if k in ("turn_id", "tool_call_id")},
        },
    )


def _extract_runtime_error(observation: dict[str, Any]) -> MemoryCandidate | None:
    """Extract an error memory from a runtime error observation."""
    payload = observation.get("payload", {}) or {}
    metadata = observation.get("metadata", {}) or {}
    task_id = observation.get("task_id", "")
    observation.get("id", "")

    error_text = payload.get("error") or payload.get("message") or ""
    if not error_text:
        error_text = _extract_text_from_payload(payload)

    if not error_text or _is_low_information(error_text):
        return None

    content = f"Runtime error: {error_text}"
    return _classify_and_build_candidate(
        observation=observation,
        memory_type=MemoryType.ERROR.value,
        content=content,
        candidate_id=_generate_candidate_id(task_id, MemoryType.ERROR.value, content),
        metadata={
            "source": "observation",
            "observation_type": "runtime.error",
            **{k: v for k, v in metadata.items() if k in ("turn_id", "tool_call_id")},
        },
    )


# Map observation types to extractors
_EXTRACTION_RULES = {
    "task.completed": _extract_task_completed,
    "task.failed": _extract_task_failed,
    "task.cancelled": _extract_task_cancelled,
    "tool_call.completed": _extract_tool_completed,
    "runtime.error": _extract_runtime_error,
}


# ---------------------------------------------------------------------------
# MemoryHarvester
# ---------------------------------------------------------------------------


class MemoryHarvester:
    """
    Deterministic memory harvester that consumes observations and produces
    MemoryCandidate objects.

    The harvester is safe to call repeatedly.  It does not modify the
    underlying observation store.
    """

    def __init__(
        self,
        observation_store: ObservationStore,
        memory_backend: MemoryBackend | None = None,
    ) -> None:
        self._observation_store = observation_store
        self._memory_backend = memory_backend
        self._lock = __import__("threading").Lock()

    def harvest_task(self, task_id: str) -> HarvestResult:
        """Harvest memories from all observations for a task."""
        try:
            observations = self._observation_store.list_by_task(task_id, limit=1000)
        except Exception as e:
            logger.debug("MemoryHarvester failed to list observations", exc_info=True)
            return HarvestResult(
                task_id=task_id,
                candidates=[],
                observations_processed=0,
                skipped_count=0,
                errors=[str(e)],
                harvested_at=datetime.now(UTC).isoformat(),
            )
        return self.harvest_observations(observations)

    def harvest_observations(self, observations: list[dict[str, Any]]) -> HarvestResult:
        """
        Harvest memories from a list of observation dicts.

        Returns a HarvestResult with candidates, counts, and any errors.
        Never raises.
        """
        task_id = ""
        candidates: list[MemoryCandidate] = []
        errors: list[str] = []
        skipped = 0
        seen_ids = set()

        for obs in observations:
            try:
                if not isinstance(obs, dict):
                    skipped += 1
                    continue

                observation_type = str(obs.get("observation_type", ""))
                task_id = obs.get("task_id", task_id) or task_id

                extractor = _EXTRACTION_RULES.get(observation_type)
                if extractor is None:
                    skipped += 1
                    continue

                candidate = extractor(obs)
                if candidate is None:
                    skipped += 1
                    continue

                if candidate.id in seen_ids:
                    skipped += 1
                    continue

                seen_ids.add(candidate.id)
                candidates.append(candidate)

            except Exception as e:
                errors.append(f"Failed to extract from observation: {e}")
                logger.debug("MemoryHarvester extraction error", exc_info=True)
                skipped += 1

        # Persist if backend is available
        if self._memory_backend is not None:
            self._persist_candidates(candidates, errors)

        return HarvestResult(
            task_id=task_id or "",
            candidates=candidates,
            observations_processed=len(observations),
            skipped_count=skipped,
            errors=errors,
            harvested_at=datetime.now(UTC).isoformat(),
        )

    def _persist_candidates(self, candidates: list[MemoryCandidate], errors: list[str]) -> None:
        """Persist candidates to the memory backend. Never raises.

        Implements monotonic confidence upgrades: if a memory already exists
        for the same content (deduped by the backend) and the new candidate
        has higher confidence, the stored confidence is upgraded via
        ``update_confidence``.

        Confidence reason is stored via ``update_confidence`` (when called)
        and in the candidate's metadata. It is NOT appended to the content
        to keep content clean and preserve dedupe fidelity.
        """
        if not candidates:
            return
        try:
            has_update_confidence = hasattr(self._memory_backend, "update_confidence")
            for candidate in candidates:
                try:
                    confidence_float = _confidence_to_float(candidate.confidence)
                    try:
                        stored = self._memory_backend.store(
                            type=candidate.memory_type,
                            content=candidate.content,
                            project=candidate.task_id or None,
                            importance=0.5,
                            confidence=confidence_float,
                        )
                    except TypeError:
                        stored = self._memory_backend.store(
                            type=candidate.memory_type,
                            content=candidate.content,
                            project=candidate.task_id or None,
                            importance=0.5,
                        )

                    existing_conf = stored.get("confidence", 0.0) if stored else 0.0
                    if has_update_confidence and stored and confidence_float > existing_conf:
                        try:
                            self._memory_backend.update_confidence(
                                stored["id"], confidence_float, candidate.confidence_reason
                            )
                        except Exception:
                            logger.debug(
                                "Failed to upgrade confidence for %s",
                                stored.get("id", ""),
                                exc_info=True,
                            )
                except Exception as e:
                    errors.append(f"Failed to persist {candidate.id}: {e}")
                    logger.debug("MemoryHarvester persistence error", exc_info=True)
        except Exception:
            logger.debug("MemoryHarvester persistence batch failed", exc_info=True)
