"""Review command for ARGUS."""

import json
from typing import List

from argus.review.evidence import EvidenceCollector
from argus.review.reviewer import ReviewEngine, run_review


def handle(repl, args: List[str]) -> str:
    """Handle /review command."""
    if not args:
        return _run_review(repl)

    sub = args[0]

    if sub == "--run":
        if len(args) < 2:
            return "Usage: /review --run <run_id>"
        return _run_review(repl, run_id=args[1])

    elif sub == "--json":
        return _run_review(repl, output_json=True)

    elif sub == "--findings":
        return _run_review(repl, show_findings=True)

    elif sub == "--security":
        return _run_review(repl, security_only=True)

    elif sub == "--requirements":
        return _run_review(repl, requirements_only=True)

    elif sub == "--help":
        return _show_help()

    return f"Unknown review option: {sub}"


def _run_review(repl, run_id: str = "", output_json: bool = False,
                show_findings: bool = False, security_only: bool = False,
                requirements_only: bool = False) -> str:
    """Run review and return formatted output."""
    # Collect evidence from the runtime
    collector = EvidenceCollector()
    _collect_evidence(repl, collector, run_id)

    # Run review
    result = run_review(
        evidence=collector.collection,
        task="",
        run_id=run_id,
    )

    # Format output
    if output_json:
        from argus.review.report import format_review_json
        return format_review_json(result)

    from argus.review.report import ReviewReport
    report = ReviewReport(result)
    return report.to_text()


def _collect_evidence(repl, collector: EvidenceCollector, run_id: str = "") -> None:
    """Collect evidence from the runtime."""
    # Collect from capability router if available
    if hasattr(repl, '_cap_router') and repl._cap_router:
        _collect_capability_evidence(repl._cap_router, collector, run_id)

    # Collect from event system if available
    try:
        from argus.events import get_correlation_tracker
        tracker = get_correlation_tracker()
        if run_id:
            events = tracker.get_run_events(run_id)
        else:
            events = list(tracker._events.values())

        for event in events:
            collector.add_evidence(
                source="event_system",
                evidence_type="event",
                data={"event": event.to_dict()},
                summary=f"Event: {event.event_type.value}",
                run_id=event.run_id,
            )
    except ImportError:
        pass


def _collect_capability_evidence(cap_router, collector: EvidenceCollector, run_id: str = "") -> None:
    """Collect evidence from capability router."""
    stats = cap_router.get_statistics()
    collector.add_evidence(
        source="capability_router",
        evidence_type="capability_stats",
        data={"statistics": stats},
        summary=f"Capability stats: {len(stats)} capabilities used",
        run_id=run_id,
    )


def _show_help() -> str:
    """Show review command help."""
    return """Review command help:
/review                 Run review on current run
/review --run <id>      Run review on specific run
/review --json          Output review as JSON
/review --findings      Show detailed findings
/review --security      Show security findings only
/review --requirements  Show requirement findings only
/review --help          Show this help
"""
