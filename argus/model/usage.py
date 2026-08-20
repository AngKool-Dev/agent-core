"""Argus usage and budget tracking."""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_USAGE_PATH = Path.home() / ".argus" / "usage.json"


@dataclass
class UsageEntry:
    provider: str
    model: str
    timestamp: float
    tokens: int = 0
    cost: float = 0.0
    success: bool = True
    error: Optional[str] = None


class UsageTracker:
    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or DEFAULT_USAGE_PATH
        self._entries: List[UsageEntry] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._entries = [UsageEntry(**entry) for entry in data.get("entries", [])]
            except Exception:
                self._entries = []
        else:
            self._entries = []

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": [
                {
                    "provider": entry.provider,
                    "model": entry.model,
                    "timestamp": entry.timestamp,
                    "tokens": entry.tokens,
                    "cost": entry.cost,
                    "success": entry.success,
                    "error": entry.error,
                }
                for entry in self._entries[-1000:]
            ]
        }
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def record(self, entry: UsageEntry) -> None:
        self._entries.append(entry)
        self.save()

    def today(self) -> List[UsageEntry]:
        today_start = time.time() - (time.time() % 86400)
        return [e for e in self._entries if e.timestamp >= today_start]

    def provider_stats(self, entries: Optional[List[UsageEntry]] = None) -> Dict[str, Dict[str, Any]]:
        entries = entries or self._entries
        stats: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            if entry.provider not in stats:
                stats[entry.provider] = {"requests": 0, "tokens": 0, "cost": 0.0, "errors": 0}
            stats[entry.provider]["requests"] += 1
            stats[entry.provider]["tokens"] += entry.tokens
            stats[entry.provider]["cost"] += entry.cost
            if not entry.success:
                stats[entry.provider]["errors"] += 1
        return stats

    def clear(self) -> None:
        self._entries = []
        self.save()
