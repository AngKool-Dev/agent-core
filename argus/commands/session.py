"""Argus session command."""

from typing import List


def handle(repl, args: List[str]) -> str:
    if not args:
        return "Usage: /session <new|list|load|save|delete> [args]"

    sub = args[0]
    if sub == "new":
        name = args[1] if len(args) > 1 else None
        if not name:
            return "Usage: /session new <name>"
        session = repl.session_manager.create(name, str(repl.project_path))
        repl.session = session
        return f"Created session: {name}"

    elif sub == "list":
        sessions = repl.session_manager.list_sessions()
        return "\n".join(sessions) if sessions else "No sessions found"

    elif sub == "load":
        name = args[1] if len(args) > 1 else None
        if not name:
            return "Usage: /session load <name>"
        try:
            session = repl.session_manager.load(name)
            repl.session = session
            return f"Loaded session: {name} ({len(session.messages)} messages)"
        except FileNotFoundError:
            return f"Session not found: {name}"

    elif sub == "save":
        repl.session_manager.save_current()
        return "Session saved"

    elif sub == "delete":
        name = args[1] if len(args) > 1 else None
        if not name:
            return "Usage: /session delete <name>"
        repl.session_manager.delete(name)
        return f"Deleted session: {name}"

    return f"Unknown session command: {sub}"
