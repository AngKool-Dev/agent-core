"""Argus replay command - run reconstruction and forensics."""

import json
from typing import List

from argus.replay import (
    ReplayEngine,
    ReplayTimeline,
    ReplayDiff,
    ReplayConsistencyChecker,
    ForensicReport,
    load_run,
    load_partial_run,
)


def handle(repl, args: List[str]) -> str:
    """Handle /replay command."""
    if not args:
        return _show_help()

    sub = args[0]

    if sub == "--timeline":
        if len(args) < 2:
            return "Usage: /replay --timeline <run_id>"
        return _show_timeline(args[1])
    elif sub == "--tree":
        if len(args) < 2:
            return "Usage: /replay --tree <run_id>"
        return _show_tree(args[1])
    elif sub == "--state":
        if len(args) < 2:
            return "Usage: /replay --state <run_id>"
        return _show_state(args[1])
    elif sub == "--security":
        if len(args) < 2:
            return "Usage: /replay --security <run_id>"
        return _show_security(args[1])
    elif sub == "--recovery":
        if len(args) < 2:
            return "Usage: /replay --recovery <run_id>"
        return _show_recovery(args[1])
    elif sub == "--verification":
        if len(args) < 2:
            return "Usage: /replay --verification <run_id>"
        return _show_verification(args[1])
    elif sub == "--review":
        if len(args) < 2:
            return "Usage: /replay --review <run_id>"
        return _show_review(args[1])
    elif sub == "--json":
        if len(args) < 2:
            return "Usage: /replay --json <run_id>"
        return _show_json(args[1])
    elif sub == "--consistency":
        if len(args) < 2:
            return "Usage: /replay --consistency <run_id>"
        return _show_consistency(args[1])
    elif sub == "--diff":
        if len(args) < 2:
            return "Usage: /replay --diff <run_id>"
        return _show_diff(args[1])
    elif sub == "--forensics" or sub == "--full":
        if len(args) < 2:
            return "Usage: /replay --forensics <run_id>"
        return _show_forensics(args[1])
    elif sub == "--help":
        return _show_help()

    # If first arg is not a flag, treat it as run_id for full forensics
    return _show_forensics(args[0])


def _load_run_safe(run_id: str):
    """Load a run safely, returning error message on failure."""
    try:
        return load_run(run_id)
    except Exception as e:
        return None


def _show_help() -> str:
    """Show replay command help."""
    return """Replay command help:
/replay <run_id>                  Full forensic report
/replay --timeline <run_id>       Show event timeline
/replay --tree <run_id>           Show execution tree
/replay --state <run_id>          Show reconstructed state
/replay --security <run_id>       Show security decisions
/replay --recovery <run_id>       Show recovery actions
/replay --verification <run_id>   Show verification results
/replay --review <run_id>         Show review results
/replay --json <run_id>           Full report as JSON
/replay --consistency <run_id>    Run consistency check
/replay --diff <run_id>           Show state diff
/replay --forensics <run_id>      Full forensic report
/replay --help                    Show this help

Note: /trace shows events.
      /replay reconstructs state and analyzes the run."""


def _show_timeline(run_id: str) -> str:
    """Show event timeline for a run."""
    run = _load_run_safe(run_id)
    if run is None:
        return f"Could not load run: {run_id}"

    timeline = ReplayTimeline(run)
    entries = timeline.all()

    if not entries:
        return f"No events found for run: {run_id}"

    lines = [f"Timeline for run {run_id}:", "-" * 60]
    lines.append(f"Status: {run.status.value}")
    lines.append(f"Events: {len(entries)}")
    lines.append("")

    for entry in entries:
        ts = _format_timestamp(entry.timestamp)
        line = f"{ts} [{entry.sequence:04d}] {entry.event_type}"
        if entry.status:
            line += f" [{entry.status}]"
        if entry.capability:
            line += f" ({entry.capability})"
        lines.append(line)

    return "\n".join(lines)


def _show_tree(run_id: str) -> str:
    """Show execution tree for a run."""
    run = _load_run_safe(run_id)
    if run is None:
        return f"Could not load run: {run_id}"

    from argus.replay.tree import build_execution_tree, format_execution_tree

    tree = build_execution_tree(run)
    if tree is None:
        return f"No events found for run: {run_id}"

    lines = [f"Execution tree for run {run_id}:", "-" * 60]
    lines.append(format_execution_tree(tree))
    return "\n".join(lines)


def _show_state(run_id: str) -> str:
    """Show reconstructed state for a run."""
    run = _load_run_safe(run_id)
    if run is None:
        return f"Could not load run: {run_id}"

    from argus.replay.reducer import StateReducer

    reducer = StateReducer()
    state = reducer.reduce(run)

    lines = [f"Reconstructed state for run {run_id}:", "-" * 60]
    lines.append(json.dumps(state, indent=2, default=str))
    return "\n".join(lines)


def _show_security(run_id: str) -> str:
    """Show security decisions for a run."""
    run = _load_run_safe(run_id)
    if run is None:
        return f"Could not load run: {run_id}"

    lines = [f"Security decisions for run {run_id}:", "-" * 60]

    if not run.security_decisions:
        lines.append("No security decisions recorded.")
        return "\n".join(lines)

    for decision in run.security_decisions:
        lines.append(f"  [{decision.decision.upper()}] {decision.capability}")
        lines.append(f"    Risk: {decision.risk_level}")
        if decision.reason:
            lines.append(f"    Reason: {decision.reason}")
        lines.append("")

    return "\n".join(lines)


def _show_recovery(run_id: str) -> str:
    """Show recovery actions for a run."""
    run = _load_run_safe(run_id)
    if run is None:
        return f"Could not load run: {run_id}"

    lines = [f"Recovery actions for run {run_id}:", "-" * 60]

    if not run.recovery_actions:
        lines.append("No recovery actions recorded.")
        return "\n".join(lines)

    for action in run.recovery_actions:
        status = "SUCCESS" if action.success else "FAILED"
        lines.append(f"  [{status}] Attempt {action.attempt_number}")
        lines.append(f"    Strategy: {action.strategy}")
        lines.append(f"    Failure class: {action.failure_class}")
        lines.append(f"    Budget: {action.budget_before} -> {action.budget_after}")
        lines.append("")

    return "\n".join(lines)


def _show_verification(run_id: str) -> str:
    """Show verification results for a run."""
    run = _load_run_safe(run_id)
    if run is None:
        return f"Could not load run: {run_id}"

    lines = [f"Verification results for run {run_id}:", "-" * 60]

    if not run.verification_results:
        lines.append("No verification results recorded.")
        return "\n".join(lines)

    for result in run.verification_results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"  [{status}] {result.criteria_name}")
        if result.details:
            lines.append(f"    Details: {result.details}")
        lines.append("")

    return "\n".join(lines)


def _show_review(run_id: str) -> str:
    """Show review results for a run."""
    run = _load_run_safe(run_id)
    if run is None:
        return f"Could not load run: {run_id}"

    lines = [f"Review results for run {run_id}:", "-" * 60]

    if not run.review_results:
        lines.append("No review results recorded.")
        return "\n".join(lines)

    for result in run.review_results:
        lines.append(f"  Status: {result.status}")
        lines.append(f"  Findings: {result.findings_count}")
        lines.append(f"  Criteria: {result.criteria_passed} passed, {result.criteria_failed} failed")
        if result.summary:
            lines.append(f"  Summary: {result.summary}")
        lines.append("")

    return "\n".join(lines)


def _show_json(run_id: str) -> str:
    """Show full report as JSON."""
    run = _load_run_safe(run_id)
    if run is None:
        return f"Could not load run: {run_id}"

    report = ForensicReport(run)
    return report.to_json()


def _show_consistency(run_id: str) -> str:
    """Run consistency check for a run."""
    run = _load_run_safe(run_id)
    if run is None:
        return f"Could not load run: {run_id}"

    checker = ReplayConsistencyChecker(run)
    issues = checker.check()

    lines = [f"Consistency check for run {run_id}:", "-" * 60]

    if not issues:
        lines.append("No issues found. Run is consistent.")
        return "\n".join(lines)

    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")

    lines.append(f"Found {len(issues)} issues: {errors} errors, {warnings} warnings")
    lines.append("")

    for issue in issues:
        lines.append(f"  [{issue.severity.upper()}] {issue.description}")
        if issue.event_sequence is not None:
            lines.append(f"    At sequence: {issue.event_sequence}")

    return "\n".join(lines)


def _show_diff(run_id: str) -> str:
    """Show state diff for a run."""
    run = _load_run_safe(run_id)
    if run is None:
        return f"Could not load run: {run_id}"

    diff = ReplayDiff()
    state_diff = diff.diff_run_states(run)

    lines = [f"State diff for run {run_id}:", "-" * 60]
    lines.append(diff.format_diff(state_diff))
    return "\n".join(lines)


def _show_forensics(run_id: str) -> str:
    """Show full forensic report for a run."""
    run = _load_run_safe(run_id)
    if run is None:
        return f"Could not load run: {run_id}"

    report = ForensicReport(run)
    return report.to_text()


def _format_timestamp(timestamp: float) -> str:
    """Format a timestamp for display."""
    from datetime import datetime
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%H:%M:%S.%f")[:-3]
