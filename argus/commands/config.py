"""Argus config command."""

import tomli_w
from typing import List


def handle(repl, args: List[str]) -> str:
    if not args:
        return "Usage: /config <get|set|show> [args]"

    sub = args[0]
    if sub == "show":
        return tomli_w.dumps(repl.config.raw)

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
