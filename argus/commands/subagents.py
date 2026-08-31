"""Subagents command for ARGUS."""

from typing import List

from argus.subagents.cli import handle as subagents_handle


def handle(repl, args: List[str]) -> str:
    """Handle /subagents command."""
    return subagents_handle(repl, args)
