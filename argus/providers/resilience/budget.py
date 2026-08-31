"""Rate budget management for provider resilience."""

import time
from typing import Dict, Optional


class RateBudget:
    """Manages rate limits per provider."""

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: Dict[str, list] = {}

    def _key(self, provider: str) -> str:
        return provider

    def _clean_old_requests(self, provider: str) -> None:
        key = self._key(provider)
        if key not in self._requests:
            self._requests[key] = []
            return

        cutoff = time.time() - self._window_seconds
        self._requests[key] = [
            t for t in self._requests[key] if t > cutoff
        ]

    def can_make_request(self, provider: str) -> bool:
        key = self._key(provider)
        self._clean_old_requests(provider)
        return len(self._requests.get(key, [])) < self._max_requests

    def record_request(self, provider: str) -> None:
        key = self._key(provider)
        if key not in self._requests:
            self._requests[key] = []
        self._requests[key].append(time.time())

    def get_remaining(self, provider: str) -> int:
        key = self._key(provider)
        self._clean_old_requests(provider)
        return max(0, self._max_requests - len(self._requests.get(key, [])))

    def get_reset_time(self, provider: str) -> Optional[float]:
        key = self._key(provider)
        self._clean_old_requests(provider)
        requests = self._requests.get(key, [])
        if not requests:
            return None
        return min(requests) + self._window_seconds

    def reset(self, provider: str) -> None:
        key = self._key(provider)
        self._requests.pop(key, None)
