"""Argus config command."""

import json
import tomli_w
from typing import List


def _clean_for_display(obj):
    if isinstance(obj, dict):
        return {k: _clean_for_display(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_clean_for_display(v) for v in obj]
    return obj


def handle(repl, args: List[str]) -> str:
    if not args:
        return "Usage: /config <get|set|show> [args]"

    sub = args[0]
    if sub == "show":
        raw = repl.config.raw
        cleaned = _clean_for_display(raw)
        try:
            return tomli_w.dumps(cleaned)
        except Exception:
            return json.dumps(cleaned, indent=2, default=str)

    elif sub == "get":
        key = args[1] if len(args) > 1 else None
        if not key:
            return "Usage: /config get <key>"
        value = repl.config.get(key)
        return f"{key} = {value}"

    elif sub == "set":
        if len(args) < 3:
            return "Usage: /config set <key> <value>"
        key = args[1]
        value = args[2]
        repl.config.set(key, value)
        repl.config.save()
        return f"Set {key} = {value}"

    return f"Unknown config command: {sub}"
