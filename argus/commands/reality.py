"""Argus reality command - production-reality qualification."""

from typing import List

from argus.reality import run_reality_suite, generate_reality_report


def handle(repl, args: List[str]) -> str:
    """Handle /reality command."""
    if not args:
        return _run_reality(repl)
    sub = args[0]
    if sub in ("--run", "run"):
        return _run_reality(repl)
    elif sub == "--json":
        return _run_reality(repl, output_json=True)
    elif sub == "--help":
        return _help_text()
    return f"Unknown reality command: {sub}"


def _run_reality(repl, output_json: bool = False) -> str:
    """Run the reality qualification suite."""
    run = run_reality_suite()
    return generate_reality_report(run, format="json" if output_json else "text")


def _help_text() -> str:
    """Return help text for /reality command."""
    return """Reality command help:
/reality                  Run the full production-reality qualification suite
/reality --json           Output the report as JSON
/reality --help           Show this help"""
