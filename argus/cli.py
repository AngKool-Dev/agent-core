"""Argus CLI entry point."""

import argparse
import logging
import sys
from pathlib import Path

from argus.config import ArgusConfig
from argus.repl import ArgusREPL


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        prog="argus",
        description="Argus - Kilo-like CLI built on AgentCore",
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="Task or request for the agent (non-interactive mode)",
    )
    parser.add_argument(
        "-p",
        "--project",
        type=str,
        default=None,
        help="Project directory path (default: current directory)",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to argus.toml config file",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--session",
        type=str,
        default=None,
        help="Session name to load",
    )
    return parser.parse_args(args)


def main(args=None) -> int:
    parsed = parse_args(args)
    setup_logging("DEBUG" if parsed.verbose else "INFO")

    project_path = Path(parsed.project).resolve() if parsed.project else Path.cwd()
    config = ArgusConfig(parsed.config)

    repl = ArgusREPL(project_path=project_path, config=config)

    if parsed.session:
        try:
            repl.session = repl.session_manager.load(parsed.session)
        except FileNotFoundError:
            print(f"Session not found: {parsed.session}", file=sys.stderr)
            return 1

    if parsed.request:
        from argus.agent import ArgusAgent

        agent = ArgusAgent(
            project_path=project_path,
            config=repl._build_agent_config(),
        )
        result = agent.execute(parsed.request)
        print(repl._format_result(result))
        return 0 if result.get("success") else 1

    return repl.run()


if __name__ == "__main__":
    sys.exit(main())
