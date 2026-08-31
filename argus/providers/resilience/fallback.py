"""Fallback management for provider resilience."""

from typing import Any, Dict, List, Optional

from argus.providers.resilience.errors import AllProvidersExhaustedError


class FallbackManager:
    """Manages fallback provider selection."""

    def __init__(self, providers: List[Dict[str, Any]]):
        self._providers = providers
        self._failed: Dict[str, bool] = {}

    def _key(self, provider: str, model: str) -> str:
        return f"{provider}/{model}"

    def select_provider(self) -> Dict[str, Any]:
        for p in self._providers:
            key = self._key(p["provider"], p["model"])
            if not self._failed.get(key, False):
                return p

        raise AllProvidersExhaustedError("All providers exhausted")

    def mark_failed(self, key: str) -> None:
        self._failed[key] = True

    def reset_failure(self, key: str) -> None:
        self._failed.pop(key, None)

    def reset_all(self) -> None:
        self._failed.clear()
