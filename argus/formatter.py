"""Argus result formatter for user-facing output."""

from typing import Any, Dict


def format_agent_result(result: Dict[str, Any], verbose: bool = False) -> str:
    """Format agent execution result for user display."""
    if verbose:
        return _format_verbose(result)
    return _format_normal(result)


def _format_normal(result: Dict[str, Any]) -> str:
    lines = []

    tool_results = result.get("tool_results", [])
    if tool_results:
        lines.append("Tool execution:")
        for tr in tool_results:
            tool_name = tr.get("tool", "")
            if tr.get("success"):
                lines.append(f"  [ok] {tool_name}")
            else:
                error_preview = (tr.get("error") or "")[:80]
                lines.append(f"  [FAIL] {tool_name}: {error_preview}")

    verification = result.get("verification", {})
    if verification:
        checks = []
        if verification.get("format_check"):
            checks.append("format" if verification["format_check"].get("passed") else "format FAIL")
        if verification.get("build_check"):
            checks.append("build" if verification["build_check"].get("passed") else "build FAIL")
        if verification.get("test_results"):
            tr = verification["test_results"]
            if tr.get("passed"):
                total = tr.get("total", "?")
                checks.append(f"Tests: {total} passed")
            else:
                checks.append("tests FAIL")
        if checks:
            lines.append("Verification: " + ", ".join(checks))

    if result.get("success"):
        lines.append("Completed successfully.")
    else:
        error = result.get("error", "")
        if error:
            lines.append(f"Completed with issues: {error[:100]}")
        else:
            lines.append("Completed with issues.")

    return "\n".join(lines) if lines else "Done."


def _format_verbose(result: Dict[str, Any]) -> str:
    lines = [
        f"Task: {result.get('task_id', 'N/A')}",
        f"State: {result.get('status', 'N/A')}",
        f"Iterations: {result.get('iterations', 0)}",
        f"Tools used: {result.get('tools_used', 0)}",
    ]

    plan = result.get("plan", [])
    if plan:
        lines.append("Plan:")
        for step in plan:
            status = "done" if step.get("completed") else "pending"
            lines.append(f"  [{status}] {step.get('action')}: {step.get('description')}")

    tool_results = result.get("tool_results", [])
    if tool_results:
        lines.append("Recent tool results:")
        for tr in tool_results[-3:]:
            status = "ok" if tr.get("success") else "FAIL"
            output_preview = (tr.get("output") or tr.get("error", ""))[:100]
            lines.append(f"  [{status}] {tr.get('tool')}: {output_preview}")

    verification = result.get("verification", {})
    if verification.get("format_check"):
        passed = verification["format_check"].get("passed")
        lines.append(f"Format check: {'PASSED' if passed else 'FAILED'}")
    if verification.get("build_check"):
        passed = verification["build_check"].get("passed")
        lines.append(f"Build check: {'PASSED' if passed else 'FAILED'}")
    if verification.get("test_results"):
        passed = verification["test_results"].get("passed")
        lines.append(f"Tests: {'PASSED' if passed else 'FAILED'}")

    if result.get("success"):
        lines.append("Verification PASSED")
    else:
        lines.append("Verification FAILED")

    return "\n".join(lines)
