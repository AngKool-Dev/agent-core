"""Retry handler for provider resilience."""

import time
from typing import Callable, Optional, TypeVar

from argus.providers.resilience.backoff import BackoffStrategy
from argus.providers.resilience.errors import AuthenticationError

T = TypeVar("T")


class RetryHandler:
    """Handles retry logic with backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        backoff: Optional[BackoffStrategy] = None,
        retryable_exceptions: Optional[tuple] = None,
        non_retryable_exceptions: Optional[tuple] = None,
    ):
        self._max_retries = max_retries
        self._backoff = backoff or BackoffStrategy(max_attempts=max_retries)
        self._retryable_exceptions = retryable_exceptions or (Exception,)
        self._non_retryable_exceptions = non_retryable_exceptions or (
            AuthenticationError,
            ValueError,
            TypeError,
        )

    def execute_with_retry(self, operation: Callable[[], T]) -> T:
        last_exception = None

        for attempt in range(self._max_retries + 1):
            try:
                return operation()
            except self._non_retryable_exceptions as e:
                raise
            except self._retryable_exceptions as e:
                last_exception = e
                if attempt < self._max_retries and self._backoff.should_retry(attempt):
                    self._backoff.sleep(attempt)
                else:
                    raise

        raise last_exception
