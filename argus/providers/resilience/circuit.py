"""Circuit breaker for provider resilience."""

import time
from typing import Dict, Optional

from argus.providers.resilience.models import CircuitConfig, CircuitState


class CircuitBreaker:
    """Circuit breaker pattern for provider calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_requests: int = 1,
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_requests = half_open_max_requests
        self._circuits: Dict[str, CircuitState] = {}
        self._failure_counts: Dict[str, int] = {}
        self._last_failure_time: Dict[str, float] = {}
        self._half_open_requests: Dict[str, int] = {}

    def _key(self, provider: str, model: str) -> str:
        return f"{provider}/{model}"

    def get_state(self, provider: str, model: str) -> CircuitState:
        key = self._key(provider, model)
        state = self._circuits.get(key, CircuitState.CLOSED)

        if state == CircuitState.OPEN:
            last_fail = self._last_failure_time.get(key, 0)
            if time.time() - last_fail >= self._recovery_timeout:
                self._circuits[key] = CircuitState.HALF_OPEN
                self._half_open_requests[key] = 0
                return CircuitState.HALF_OPEN

        return state

    def allow_request(self, provider: str, model: str) -> bool:
        state = self.get_state(provider, model)
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            key = self._key(provider, model)
            requests = self._half_open_requests.get(key, 0)
            return requests < self._half_open_max_requests
        return False

    def record_failure(self, provider: str, model: str) -> None:
        key = self._key(provider, model)
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
        self._last_failure_time[key] = time.time()

        state = self.get_state(provider, model)
        if state == CircuitState.HALF_OPEN:
            self._circuits[key] = CircuitState.OPEN
        elif self._failure_counts[key] >= self._failure_threshold:
            self._circuits[key] = CircuitState.OPEN

    def record_success(self, provider: str, model: str) -> None:
        key = self._key(provider, model)
        state = self.get_state(provider, model)

        if state == CircuitState.HALF_OPEN:
            self._half_open_requests[key] = self._half_open_requests.get(key, 0) + 1
            if self._half_open_requests[key] >= self._half_open_max_requests:
                self._circuits[key] = CircuitState.CLOSED
                self._failure_counts[key] = 0
        else:
            self._failure_counts[key] = 0

    def get_failure_count(self, provider: str, model: str) -> int:
        return self._failure_counts.get(self._key(provider, model), 0)

    def reset(self, provider: str, model: str) -> None:
        key = self._key(provider, model)
        self._circuits[key] = CircuitState.CLOSED
        self._failure_counts[key] = 0
        self._last_failure_time.pop(key, None)
        self._half_open_requests.pop(key, None)

    def get_all_states(self) -> Dict[str, CircuitState]:
        result = {}
        for key in self._circuits:
            provider, model = key.split("/", 1)
            result[key] = self.get_state(provider, model)
        return result
