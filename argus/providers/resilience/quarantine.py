"""Quarantine management for provider resilience."""

import time
from typing import Dict, List, Optional

from argus.providers.resilience.models import QuarantineRecord


class QuarantineManager:
    """Manages provider quarantine state."""

    def __init__(
        self,
        quarantine_threshold: int = 5,
        quarantine_duration: float = 300.0,
        auto_recovery: bool = True,
    ):
        self._quarantine_threshold = quarantine_threshold
        self._quarantine_duration = quarantine_duration
        self._auto_recovery = auto_recovery
        self._records: Dict[str, QuarantineRecord] = {}

    def _key(self, provider: str, model: str) -> str:
        return f"{provider}/{model}"

    def record_failure(self, provider: str, model: str, reason: str = "") -> None:
        key = self._key(provider, model)
        record = self._records.get(key)
        if not record:
            record = QuarantineRecord(provider=provider, model=model)
            self._records[key] = record

        record.failure_count += 1
        if record.failure_count >= self._quarantine_threshold:
            record.quarantined_at = time.time()
            record.reason = reason

    def is_quarantined(self, provider: str, model: str) -> bool:
        key = self._key(provider, model)
        record = self._records.get(key)
        if not record or not record.quarantined_at:
            return False

        if record.manually_overridden:
            return False

        if self._auto_recovery:
            elapsed = time.time() - record.quarantined_at
            if elapsed >= self._quarantine_duration:
                return False

        return True

    def get_quarantine_record(self, provider: str, model: str) -> Optional[QuarantineRecord]:
        return self._records.get(self._key(provider, model))

    def manual_override(self, provider: str, model: str) -> None:
        key = self._key(provider, model)
        record = self._records.get(key)
        if record:
            record.manually_overridden = True

    def get_all_quarantines(self) -> List[QuarantineRecord]:
        return [
            r for r in self._records.values()
            if r.quarantined_at is not None
        ]

    def reset(self, provider: str, model: str) -> None:
        key = self._key(provider, model)
        self._records.pop(key, None)
