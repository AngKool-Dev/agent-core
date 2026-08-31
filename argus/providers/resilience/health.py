"""Health tracking for provider resilience."""

import time
from typing import Dict, List, Optional

from argus.providers.resilience.models import FailureClass, HealthRecord


class HealthTracker:
    """Tracks provider health metrics."""

    def __init__(self, window_size: int = 100):
        self._window_size = window_size
        self._records: Dict[str, HealthRecord] = {}
        self._latencies: Dict[str, List[float]] = {}

    def _key(self, provider: str, model: str) -> str:
        return f"{provider}/{model}"

    def record_request(
        self,
        provider: str,
        model: str,
        success: bool,
        latency_ms: float = 0.0,
        failure_class: Optional[FailureClass] = None,
    ) -> None:
        key = self._key(provider, model)
        record = self._records.get(key)
        if not record:
            record = HealthRecord(provider=provider, model=model)
            self._records[key] = record

        record.total_requests += 1
        if success:
            record.successful_requests += 1
        else:
            record.failed_requests += 1
            record.last_failure = failure_class.value if failure_class else None

        # Update rates
        record.success_rate = record.successful_requests / record.total_requests
        record.failure_rate = record.failed_requests / record.total_requests

        # Track latency
        if key not in self._latencies:
            self._latencies[key] = []
        self._latencies[key].append(latency_ms)
        if len(self._latencies[key]) > self._window_size:
            self._latencies[key] = self._latencies[key][-self._window_size:]
        record.avg_latency_ms = sum(self._latencies[key]) / len(self._latencies[key])

    def get_health(self, provider: str, model: str) -> HealthRecord:
        key = self._key(provider, model)
        return self._records.get(key, HealthRecord(provider=provider, model=model))

    def is_healthy(
        self,
        provider: str,
        model: str,
        min_success_rate: float = 0.5,
    ) -> bool:
        record = self.get_health(provider, model)
        if record.total_requests == 0:
            return True
        return record.success_rate >= min_success_rate

    def get_most_healthy(self) -> Optional[str]:
        if not self._records:
            return None
        best = max(self._records.values(), key=lambda r: r.success_rate)
        return f"{best.provider}/{best.model}"

    def get_least_healthy(self) -> Optional[str]:
        if not self._records:
            return None
        worst = min(self._records.values(), key=lambda r: r.success_rate)
        return f"{worst.provider}/{worst.model}"

    def reset(self, provider: str, model: str) -> None:
        key = self._key(provider, model)
        self._records.pop(key, None)
        self._latencies.pop(key, None)
