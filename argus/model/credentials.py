"""Argus provider credential management."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CREDENTIALS_PATH = Path.home() / ".argus" / "credentials.json"


class CredentialManager:
    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or DEFAULT_CREDENTIALS_PATH
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}
        else:
            self._data = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def get(self, provider: str) -> Optional[str]:
        return self._data.get(provider, {}).get("api_key")

    def set(self, provider: str, api_key: str) -> None:
        if provider not in self._data:
            self._data[provider] = {}
        self._data[provider]["api_key"] = api_key
        self.save()

    def has(self, provider: str) -> bool:
        return bool(self.get(provider))

    def list_providers(self) -> Dict[str, Dict[str, Any]]:
        return {name: {"api_key": bool(data.get("api_key"))} for name, data in self._data.items()}

    def remove(self, provider: str) -> None:
        self._data.pop(provider, None)
        self.save()
