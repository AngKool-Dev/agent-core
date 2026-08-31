"""Backoff strategies for provider resilience."""

import random
import time
from typing import Callable, Optional


class BackoffStrategy:
    """Exponential backoff with jitter."""

    def __init__(
        self,
        min_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter: bool = True,
        max_attempts: int = 3,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ):
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._multiplier = multiplier
        self._jitter = jitter
        self._max_attempts = max_attempts
        self._sleep_fn = sleep_fn or time.sleep

    def get_delay(self, attempt: int) -> float:
        delay = self._min_delay * (self._multiplier ** attempt)
        delay = min(delay, self._max_delay)

        if self._jitter:
            delay = random.uniform(0, delay)

        return delay

    def should_retry(self, attempt: int) -> bool:
        return attempt < self._max_attempts

    def sleep(self, attempt: int) -> None:
        self._sleep_fn(self.get_delay(attempt))


class LinearBackoff:
    """Linear backoff strategy."""

    def __init__(
        self,
        min_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        max_attempts: int = 3,
    ):
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._jitter = jitter
        self._max_attempts = max_attempts

    def get_delay(self, attempt: int) -> float:
        delay = self._min_delay * (attempt + 1)
        delay = min(delay, self._max_delay)

        if self._jitter:
            delay = random.uniform(0, delay)

        return delay

    def should_retry(self, attempt: int) -> bool:
        return attempt < self._max_attempts


class FixedBackoff:
    """Fixed delay backoff strategy."""

    def __init__(
        self,
        delay: float = 5.0,
        max_attempts: int = 3,
    ):
        self._delay = delay
        self._max_attempts = max_attempts

    def get_delay(self, attempt: int) -> float:
        return self._delay

    def should_retry(self, attempt: int) -> bool:
        return attempt < self._max_attempts
