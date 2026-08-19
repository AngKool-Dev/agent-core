"""
CLI shared utilities for Phase 5F.

Provides:
- Confidence parsing (float or enum name → float)
- Confidence reverse-mapping (float → enum label)
- JSON output helper
- Human-readable formatting helpers
"""

from __future__ import annotations

import json
import sys
from typing import Any

_CONFIDENCE_FLOAT = {
    "VERIFIED": 1.0,
    "CLAIMED": 0.7,
    "INFERRED": 0.5,
    "UNKNOWN": 0.3,
}


def parse_confidence(value: str) -> tuple[float | None, str | None]:
    """Parse a --min-confidence argument value.

    Accepts either a float (e.g. "0.7") or an enum name (e.g. "VERIFIED", "verified").

    Returns (float_value, error_message).  On success, error_message is None.
    """
    if value is None:
        return None, None
    upper = value.strip().upper()
    if upper in _CONFIDENCE_FLOAT:
        return _CONFIDENCE_FLOAT[upper], None
    try:
        f = float(value)
    except ValueError:
        return None, (
            f"Invalid confidence value: {value!r}\n"
            f"  Use a float in [0, 1] or one of: "
            f"{', '.join(sorted(k for k in _CONFIDENCE_FLOAT if k.isupper()))}"
        )
    if not 0.0 <= f <= 1.0:
        return None, f"Confidence must be in [0, 1], got {f}"
    return f, None


def confidence_label(score: float | None) -> str:
    """Map a confidence float back to a human-readable label."""
    if score is None:
        return "UNKNOWN"
    if score >= 0.9:
        return "VERIFIED"
    if score >= 0.6:
        return "CLAIMED"
    if score >= 0.4:
        return "INFERRED"
    return "UNKNOWN"


def format_observation_row(obs: dict, full: bool = False) -> str:
    """Format a single observation dict into a single table row."""
    seq = obs.get("sequence", 0)
    ts = obs.get("timestamp", "")
    if ts:
        ts_short = ts[11:19] if len(ts) >= 19 else ts
    else:
        ts_short = "-"
    obs_type = obs.get("observation_type", "")
    payload = obs.get("payload", {}) or {}
    name = payload.get("name", "") if isinstance(payload, dict) else ""
    tool = name if name else "-"

    line = f"{seq:<5} {ts_short:<10} {obs_type:<24} {tool}"
    if full:
        line += f"  payload={json.dumps(payload, default=str)[:200]}"
    return line


def print_json(data: Any, indent: int = 2) -> None:
    """Print data as valid JSON without ANSI codes."""
    print(json.dumps(data, indent=indent, default=str, ensure_ascii=False))


def truncate(text: str, width: int = 80) -> str:
    if len(text) <= width:
        return text
    return text[: width - 3] + "..."


def print_error(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
