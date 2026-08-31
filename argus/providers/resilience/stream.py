"""Stream handling for provider resilience."""

import time
from typing import Any, Callable, Optional

from argus.providers.resilience.models import ProviderResponse


class StreamHandler:
    """Handles streaming responses."""

    def __init__(
        self,
        timeout: float = 30.0,
        accumulate: bool = False,
    ):
        self._timeout = timeout
        self._accumulate = accumulate
        self._active = True
        self._accumulated_content = ""
        self._chunk_callback: Optional[Callable[[str], None]] = None
        self._complete_callback: Optional[Callable[[ProviderResponse], None]] = None
        self._error_callback: Optional[Callable[[Exception], None]] = None
        self._start_time = time.time()

    def set_chunk_callback(self, callback: Callable[[str], None]) -> None:
        self._chunk_callback = callback

    def set_complete_callback(self, callback: Callable[[ProviderResponse], None]) -> None:
        self._complete_callback = callback

    def set_error_callback(self, callback: Callable[[Exception], None]) -> None:
        self._error_callback = callback

    def handle_chunk(self, chunk: str) -> None:
        if self._accumulate:
            self._accumulated_content += chunk
        if self._chunk_callback:
            self._chunk_callback(chunk)

    def complete(self, response: ProviderResponse) -> None:
        self._active = False
        if self._accumulate and self._accumulated_content:
            response.content = self._accumulated_content
        if self._complete_callback:
            self._complete_callback(response)

    def error(self, exception: Exception) -> None:
        self._active = False
        if self._error_callback:
            self._error_callback(exception)

    def is_active(self) -> bool:
        return self._active

    def is_timed_out(self) -> bool:
        return (time.time() - self._start_time) >= self._timeout

    def get_accumulated(self) -> str:
        return self._accumulated_content
