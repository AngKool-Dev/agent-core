"""Argus agent command."""

from typing import List


def handle(repl, args: List[str]) -> str:
    if not args:
        return "Usage: /agent <request>"

    request = " ".join(args)
    try:
        result = repl.agent.execute(request)
        status = repl.agent.status()

        lines = [
            f"Task: {result.get('task', {}).get('task_id', 'N/A')}",
            f"State: {status['status']}",
            f"Skills: {', '.join(status.get('skills', [])) or 'None'}",
            f"Tools used: {status.get('tools_used', 0)}",
            f"Success: {status.get('success', False)}",
        ]

        verification = result.get("verification", {})
        if verification.get("format_check"):
            lines.append(f"Format check: {'PASSED' if verification['format_check'].get('passed') else 'FAILED'}")
        if verification.get("build_check"):
            lines.append(f"Build check: {'PASSED' if verification['build_check'].get('passed') else 'FAILED'}")
        if verification.get("test_results"):
            lines.append(f"Tests: {'PASSED' if verification['test_results'].get('passed') else 'FAILED'}")

        return "\n".join(lines)
    except Exception as e:
        return f"Agent error: {e}"
