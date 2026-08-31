"""Argus release command - release engineering qualification."""

from typing import List

from argus.release import run_release_qualification, generate_release_report


def handle(repl, args: List[str]) -> str:
    """Handle /release command."""
    if not args:
        return _run_release(repl)
    sub = args[0]
    if sub == "--json":
        return _run_release(repl, output_json=True)
    elif sub == "--help":
        return _help_text()
    return f"Unknown release command: {sub}"


def _run_release(repl, output_json: bool = False) -> str:
    """Run the release qualification suite."""
    run = run_release_qualification()
    return generate_release_report(run, format="json" if output_json else "text")


def _help_text() -> str:
    """Return help text for /release command."""
    return """Release command help:
/release                  Run release qualification suite
/release --json           Output the report as JSON
/release --help           Show this help"""
