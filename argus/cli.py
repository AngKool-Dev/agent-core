"""Argus CLI entry point."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from argus.agent import ArgusAgent
from argus.config import ArgusConfig
from argus.model import create_model_from_config, create_router_from_config
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
    parser.add_argument(
        "request",
        nargs="?",
        default=None,
        help="Task or request for the agent (non-interactive mode)",
    )
    return parser.parse_args(args)


def _build_router(config: ArgusConfig):
    hub_config = config.get("model_hub", {})
    if not hub_config:
        return None
    return create_router_from_config(hub_config)


def cmd_providers(config: ArgusConfig, router=None) -> int:
    if router:
        print("ARGUS MODEL PROVIDERS")
        print()
        for state in router._registry.list_states():
            cap = state.capability
            tag = "FREE" if cap.free else "PAID"
            status = "available" if cap.available else "unavailable"
            print(f"[{tag}] {cap.name} ({status})")
            print(f"  models: {', '.join(cap.models[:5])}")
            if cap.rate_limit:
                print(f"  rate limit: {cap.rate_limit}")
            if cap.reset_info:
                print(f"  reset: {cap.reset_info}")
        return 0

    print("ARGUS MODEL PROVIDERS")
    print()
    print("[LOCAL]")
    print("  Ollama (configured)")
    providers = config.get("providers", {})
    for name, pconfig in providers.items():
        if not pconfig.get("enabled", True):
            continue
        tag = "FREE" if pconfig.get("free", True) else "PAID"
        print(f"[{tag}] {name}")
        print(f"  models: {', '.join(pconfig.get('models', [])[:5])}")
    return 0


def cmd_models(config: ArgusConfig, router=None) -> int:
    if router:
        seen = set()
        print("ARGUS MODELS")
        print()
        for state in router._registry.list_states():
            cap = state.capability
            tag = "FREE" if cap.free else "PAID"
            for model in cap.models:
                if model not in seen:
                    seen.add(model)
                    print(f"[{tag}] {model}")
        return 0

    print("ARGUS MODELS")
    print()
    provider = config.get("model.provider", "ollama")
    name = config.get("model.name", "llama3")
    print(f"[ACTIVE] {provider}/{name}")
    return 0


def cmd_model(config: ArgusConfig, name: Optional[str] = None, router=None) -> int:
    if name:
        config.set("model.name", name)
        try:
            config.save()
        except Exception:
            pass
        print(f"Model set to: {name}")
        return 0

    provider = config.get("model.provider", "ollama")
    name = config.get("model.name", "llama3")
    strategy = config.get("model_hub.strategy", "free_first")
    print(f"Provider: {provider}")
    print(f"Model: {name}")
    print(f"Strategy: {strategy}")
    return 0


def main(args=None) -> int:
    parsed = parse_args(args)
    setup_logging("DEBUG" if parsed.verbose else "INFO")

    project_path = Path(parsed.project).resolve() if parsed.project else Path.cwd()
    config = ArgusConfig(parsed.config)

    request = parsed.request
    if request in ("providers", "models", "model"):
        router = _build_router(config)
        if request == "providers":
            return cmd_providers(config, router)
        if request == "models":
            return cmd_models(config, router)
        if request == "model":
            return cmd_model(config, router=router)
        return 0

    repl = ArgusREPL(project_path=project_path, config=config)

    if parsed.session:
        try:
            repl.session = repl.session_manager.load(parsed.session)
        except FileNotFoundError:
            print(f"Session not found: {parsed.session}", file=sys.stderr)
            return 1

    if request:
        router = _build_router(config)
        if router:
            model = router
        else:
            model_config = {
                "provider": config.get("model.provider", "ollama"),
                "name": config.get("model.name", "llama3"),
            }
            if config.get("model.api_key"):
                model_config["api_key"] = config.get("model.api_key")
            if config.get("model.base_url"):
                model_config["base_url"] = config.get("model.base_url")
            model = create_model_from_config(model_config)

        agent = ArgusAgent(
            project_path=project_path,
            config=repl._build_agent_config(),
            model=model,
        )
        result = agent.execute(request)
        print(repl._format_result(result))
        return 0 if result.get("success") else 1

    return repl.run()


if __name__ == "__main__":
    sys.exit(main())
