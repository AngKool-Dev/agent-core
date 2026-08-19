#!/usr/bin/env python3
"""AgentCore CLI - Universal AI coding agent framework.

Entry points:
- agent: main agent execution CLI (preserved for backward compatibility)
- argus: observability/query CLI for tasks, observations, and memory
"""

import argparse
import logging
import sys
from pathlib import Path

from agentcore import (
    Agent,  # noqa: F401 (patched by tests)
    ConfigLoader,
    MemoryManager,
    create_agent,
    get_default_registry,
)

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="AgentCore - Universal AI coding-agent framework",
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="The task or request for the agent to perform",
    )
    parser.add_argument(
        "-p",
        "--project",
        type=str,
        default=None,
        help="Project directory path (default: current directory)",
    )
    parser.add_argument(
        "-r",
        "--runtime",
        type=str,
        default="hermes",
        help=(
            "Runtime adapter to use (default: hermes). "
            "Use --list-runtimes to see available options."
        ),
    )
    parser.add_argument(
        "--list-runtimes",
        action="store_true",
        help="List available runtime adapters and exit",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default=None,
        help="Override the model to use",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip automatic verification after task completion",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="~/.agentcore/memory.db",
        help="Path to the memory database",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to agentcore.toml configuration file",
    )

    return parser.parse_args(args)


def main(args: argparse.Namespace | None = None) -> int:
    parsed_args = parse_args(args)
    setup_logging("DEBUG" if parsed_args.verbose else "INFO")
    project_path = Path(parsed_args.project) if parsed_args.project else Path.cwd()

    registry = get_default_registry()

    if parsed_args.list_runtimes:
        print("Available runtimes:\n")
        for name in registry.list_runtimes():
            info = registry.get_info(name)
            caps = info.get("capabilities", {})
            print(f"  {name}")
            print(f"    description: {info.get('description', 'No description')}")
            print("    capabilities:")
            print(f"      text generation:       {'yes' if caps.get('text_generation') else 'no'}")
            print(f"      structured tool calls: {'yes' if caps.get('tool_calls') else 'no'}")
            print(
                f"      external tool exec:    "
                f"{'yes' if caps.get('external_tool_execution') else 'no'}"
            )
            print(f"      streaming:             {'yes' if caps.get('streaming') else 'no'}")
            print(f"      cancellation:          {'yes' if caps.get('cancellation') else 'no'}")
            print()
        return 0

    if not parsed_args.request:
        print("Error: No request provided", file=sys.stderr)
        print("Usage: agent <request> [-p /path/to/project]", file=sys.stderr)
        print("       agent --list-runtimes", file=sys.stderr)
        return 1

    # Load configuration
    if parsed_args.config:
        core_config = ConfigLoader.load(Path(parsed_args.config))
    else:
        core_config = ConfigLoader.discover(project_path)

    # Build AgentConfig from the discovered/loaded config
    agent_config = core_config.to_agent_config()
    agent_config.enable_verification = not parsed_args.no_verify

    # Override model if specified on CLI
    if parsed_args.model:
        agent_config.model = parsed_args.model

    memory_path = (
        Path(core_config.memory_db_path).expanduser()
        if core_config.memory_db_path
        else Path(parsed_args.db_path).expanduser()
    )
    memory_path.parent.mkdir(parents=True, exist_ok=True)

    db_backend = None
    memory_manager = None
    try:
        from agentcore.adapters.memory_dbobsidian import DBObsidianBackend

        db_backend = DBObsidianBackend(memory_path)
        memory_manager = MemoryManager(db_backend)
    except (ImportError, Exception):
        from agentcore.memory import MemoryBackend

        class InMemoryBackend(MemoryBackend):
            def __init__(self):
                self._store: list[dict] = []

            def search(self, query, project=None, limit=20, **kwargs):
                return [m for m in self._store if query.lower() in m.get("content", "").lower()]

            def get(self, memory_id):
                for m in self._store:
                    if m.get("id") == memory_id:
                        return m
                return None

            def store(self, type, content, project=None, importance=0.5, **kwargs):
                mem = {
                    "id": f"mem-{len(self._store)}",
                    "type": type,
                    "content": content,
                    "project": project,
                }
                self._store.append(mem)
                return mem

            def update(self, memory_id, content):
                for m in self._store:
                    if m["id"] == memory_id:
                        m["content"] = content
                        return m
                return {}

            def list(self, project=None, type=None, limit=50):
                return self._store

        memory_manager = MemoryManager(InMemoryBackend())

    try:
        runtime = registry.create(
            parsed_args.runtime,
            model=agent_config.model,
            provider=agent_config.provider,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Use --list-runtimes to see available options.", file=sys.stderr)
        return 1

    agent = create_agent(
        runtime=runtime,
        memory=memory_manager,
        project_path=project_path,
        config=agent_config,
        agentcore_config=core_config,
    )

    try:
        result = agent.execute(parsed_args.request, str(project_path))

        print(f"\n{'=' * 60}")
        print(f"Task: {result['task']['task_id']}")
        print(f"State: {result['task']['current_state']}")
        print(f"Skills: {', '.join(result['task']['selected_skills']) or 'None'}")
        print(f"Tools used: {result['tools_used']}")
        print(f"{'=' * 60}\n")

        if (
            result["verification"]["format_check"]
            and not result["verification"]["format_check"]["passed"]
        ):
            print("Format check: FAILED")
        if (
            result["verification"]["build_check"]
            and not result["verification"]["build_check"]["passed"]
        ):
            print("Build check: FAILED")
        if (
            result["verification"]["test_results"]
            and not result["verification"]["test_results"]["passed"]
        ):
            print("Test results: FAILED")

        if result["success"]:
            print("Verification PASSED")
            return 0
        else:
            print("Verification FAILED")
            return 1

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as e:
        logger.exception("Agent execution failed")
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        if db_backend and hasattr(db_backend, "close"):
            db_backend.close()


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------------------
# argus — observability/query CLI (Phase 5F)
# ---------------------------------------------------------------------------


def _build_argus_parser() -> argparse.ArgumentParser:
    """Build the argus subcommand parser."""
    parser = argparse.ArgumentParser(
        prog="argus",
        description="Argus — inspect tasks, observations, and memory",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # --- task ---
    task_parser = subparsers.add_parser("task", help="Inspect tasks")
    task_sub = task_parser.add_subparsers(dest="action", metavar="<action>")

    p_list = task_sub.add_parser("list", help="List registered tasks")
    p_list.add_argument("--state", default=None, help="Filter by task state")
    p_list.add_argument("--source", default=None, help="Filter by source")
    p_list.add_argument("--runtime", default=None, help="Filter by runtime")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")

    p_show = task_sub.add_parser("show", help="Show details for a task")
    p_show.add_argument("task_id", help="Task ID")
    p_show.add_argument("--json", action="store_true", help="Output as JSON")

    p_events = task_sub.add_parser("events", help="Show observations for a task")
    p_events.add_argument("task_id", help="Task ID")
    p_events.add_argument("--limit", type=int, default=1000, help="Maximum observations")
    p_events.add_argument("--full", action="store_true", help="Show full payload")
    p_events.add_argument("--json", action="store_true", help="Output as JSON")

    p_mem = task_sub.add_parser("memories", help="Show memories for a task")
    p_mem.add_argument("task_id", help="Task ID")
    p_mem.add_argument(
        "--min-confidence",
        default=None,
        help="Minimum confidence (float or enum: VERIFIED/CLAIMED/INFERRED/UNKNOWN)",
    )
    p_mem.add_argument("--type", default=None, help="Filter by memory type")
    p_mem.add_argument("--limit", type=int, default=50, help="Maximum memories")
    p_mem.add_argument("--json", action="store_true", help="Output as JSON")

    # --- memory ---
    mem_parser = subparsers.add_parser("memory", help="Query memory")
    mem_sub = mem_parser.add_subparsers(dest="action", metavar="<action>")

    p_search = mem_sub.add_parser("search", help="Search memories")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--limit", type=int, default=20, help="Maximum results")
    p_search.add_argument(
        "--min-confidence", default=None, help="Minimum confidence (float or enum)"
    )
    p_search.add_argument("--type", default=None, help="Filter by memory type")
    p_search.add_argument("--json", action="store_true", help="Output as JSON")

    p_mshow = mem_sub.add_parser("show", help="Show a single memory")
    p_mshow.add_argument("memory_id", help="Memory ID")
    p_mshow.add_argument("--json", action="store_true", help="Output as JSON")

    p_conf = mem_sub.add_parser("confidence", help="Show confidence diagnostic for a memory")
    p_conf.add_argument("memory_id", help="Memory ID")
    p_conf.add_argument("--json", action="store_true", help="Output as JSON")

    return parser


def argus_main(args: list[str] | None = None) -> int:
    """Entry point for the argus observability CLI."""
    parser = _build_argus_parser()
    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 0

    if parsed.command == "task":
        return _handle_task_command(parsed)
    elif parsed.command == "memory":
        return _handle_memory_command(parsed)

    parser.print_help()
    return 0


def _handle_task_command(args: argparse.Namespace) -> int:
    from agentcore.cli.commands.task import (
        list_tasks,
        show_task,
        show_task_json,
        task_events,
        task_memories,
    )
    from agentcore.cli.service import close_query_service, create_query_service

    action = args.action
    if action is None:
        print("Error: task subcommand required (list, show, events, memories)", file=sys.stderr)
        return 1

    try:
        svc = create_query_service()
    except Exception as e:
        print(f"Error: Failed to initialize query service: {e}", file=sys.stderr)
        return 1

    try:
        if action == "list":
            return list_tasks(svc, args)
        elif action == "show":
            if getattr(args, "json", False):
                return show_task_json(svc, args)
            return show_task(svc, args)
        elif action == "events":
            return task_events(svc, args)
        elif action == "memories":
            return task_memories(svc, args)
        else:
            print(f"Error: Unknown task action: {action}", file=sys.stderr)
            return 1
    except Exception:
        print("Error: Internal CLI error — backend failure or unexpected state.", file=sys.stderr)
        return 1
    finally:
        close_query_service(svc)


def _handle_memory_command(args: argparse.Namespace) -> int:
    from agentcore.cli.commands.memory import (
        memory_confidence,
        memory_search,
        memory_show,
    )
    from agentcore.cli.service import close_query_service, create_query_service

    action = args.action
    if action is None:
        print("Error: memory subcommand required (search, show, confidence)", file=sys.stderr)
        return 1

    try:
        svc = create_query_service()
    except Exception as e:
        print(f"Error: Failed to initialize query service: {e}", file=sys.stderr)
        return 1

    try:
        if action == "search":
            return memory_search(svc, args)
        elif action == "show":
            return memory_show(svc, args)
        elif action == "confidence":
            return memory_confidence(svc, args)
        else:
            print(f"Error: Unknown memory action: {action}", file=sys.stderr)
            return 1
    except Exception:
        print("Error: Internal CLI error — backend failure or unexpected state.", file=sys.stderr)
        return 1
    finally:
        close_query_service(svc)


if __name__ == "__main__":
    sys.exit(main())
