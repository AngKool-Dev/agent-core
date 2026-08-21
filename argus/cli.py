"""Argus CLI entry point."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from argus import __version__
from argus.agent import ArgusAgent
from argus.config import ArgusConfig
from argus.model import GatewayModelProvider, create_model_from_config, create_router_from_config
from argus.model.provider import ModelProvider
from argus.model.providers.gateway import GatewayClient
from argus.model.credentials import CredentialManager
from argus.model.usage import UsageTracker
from argus.repl import ArgusREPL


FREE_PROVIDERS = [
    ("gemini", "Gemini", ["gemini-2.0-flash", "gemini-1.5-flash"]),
    ("groq", "Groq", ["llama-3.1-8b-instant", "gemma2-9b-it"]),
    ("cerebras", "Cerebras", ["llama-3.1-8b", "llama-3.3-70b"]),
    ("openrouter", "OpenRouter", ["mistralai/mistral-7b-instruct", "meta-llama/llama-3.1-8b-instruct"]),
]


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
        "--version",
        action="version",
        version=f"argus {__version__}",
    )
    parser.add_argument(
        "--session",
        type=str,
        default=None,
        help="Session name to load",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        choices=["free", "byok", "local"],
        help="Force AI mode: free (Argus Gateway), byok (your keys), local (Ollama)",
    )
    parser.add_argument(
        "--serve-gateway",
        action="store_true",
        help="Start the Argus Free Gateway server locally",
    )
    parser.add_argument(
        "request",
        nargs="?",
        default=None,
        help="Task or request for the agent (non-interactive mode)",
    )
    return parser.parse_args(args)


def _build_router(config: ArgusConfig, credentials: Optional[CredentialManager] = None, usage: Optional[UsageTracker] = None):
    hub_config = config.get("model_hub", {})
    if not hub_config:
        return None
    if credentials:
        hub_config = dict(hub_config)
        providers = dict(hub_config.get("providers", {}))
        for name, pconfig in providers.items():
            if not pconfig.get("api_key") and credentials.has(name):
                pconfig = dict(pconfig)
                pconfig["api_key"] = credentials.get(name)
                providers[name] = pconfig
        hub_config["providers"] = providers
    try:
        return create_router_from_config(hub_config, usage_tracker=usage)
    except Exception:
        return None


def _build_gateway_model(config: ArgusConfig) -> Optional[GatewayModelProvider]:
    gateway_config = config.get("gateway", {})
    if not gateway_config or not gateway_config.get("base_url"):
        return None
    return GatewayModelProvider(
        base_url=gateway_config.get("base_url", ""),
        api_key=gateway_config.get("api_key", ""),
    )


def _build_fallback_model(config: ArgusConfig) -> Optional[ModelProvider]:
    model_config = {
        "provider": config.get("model.provider", "ollama"),
        "name": config.get("model.name", "llama3"),
    }
    if config.get("model.api_key"):
        model_config["api_key"] = config.get("model.api_key")
    if config.get("model.base_url"):
        model_config["base_url"] = config.get("model.base_url")
    try:
        return create_model_from_config(model_config)
    except Exception:
        return None


def _has_byok_credentials(config: ArgusConfig, credentials: CredentialManager) -> bool:
    if credentials.list_providers():
        return True
    hub_config = config.get("model_hub", {})
    providers = hub_config.get("providers", {})
    for name, pconfig in providers.items():
        if pconfig.get("api_key"):
            return True
    model_config = config.get("model", {})
    if model_config.get("api_key"):
        return True
    return False


def cmd_providers(config: ArgusConfig, router=None, credentials: Optional[CredentialManager] = None) -> int:
    print("ARGUS MODEL PROVIDERS")
    print()

    if router:
        for state in router._registry.list_states():
            cap = state.capability
            tag = "FREE" if cap.free else "PAID"
            status = "available" if cap.available else "unavailable"
            cred = "configured" if credentials and credentials.has(cap.name) else "not configured"
            print(f"[{tag}] {cap.name} ({status}, {cred})")
            print(f"  models: {', '.join(cap.models[:5])}")
            if cap.rate_limit:
                print(f"  rate limit: {cap.rate_limit}")
            if cap.reset_info:
                print(f"  reset: {cap.reset_info}")
        return 0

    print("[LOCAL]")
    print("  Ollama (configured)")
    providers = config.get("providers", {})
    for name, pconfig in providers.items():
        if not pconfig.get("enabled", True):
            continue
        tag = "FREE" if pconfig.get("free", True) else "PAID"
        cred = "configured" if credentials and credentials.has(name) else "not configured"
        print(f"[{tag}] {name} ({cred})")
        print(f"  models: {', '.join(pconfig.get('models', [])[:5])}")
    return 0


def cmd_models(config: ArgusConfig, router=None) -> int:
    print("ARGUS MODELS")
    print()

    if router:
        seen = set()
        for state in router._registry.list_states():
            cap = state.capability
            tag = "FREE" if cap.free else "PAID"
            for model in cap.models:
                if model not in seen:
                    seen.add(model)
                    print(f"[{tag}] {model}")
        return 0

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


def cmd_gateway(config: ArgusConfig) -> int:
    gateway_config = config.get("gateway", {})
    if not gateway_config or not gateway_config.get("base_url"):
        print("Gateway is not configured.")
        print("Set [gateway] base_url in argus.toml to enable Argus Free Gateway.")
        print(f"Default gateway: {GatewayClient.DEFAULT_BASE_URL}")
        return 0

    provider = GatewayModelProvider(
        base_url=gateway_config.get("base_url", ""),
        api_key=gateway_config.get("api_key", ""),
    )

    print("ARGUS GATEWAY")
    print()

    try:
        health = provider.health()
        print(f"Status: {health.status}")
        print(f"Anonymous available: {health.anonymous_available}")
        print(f"Providers: {', '.join(health.providers)}")
        print()
    except Exception as e:
        print(f"Health check failed: {e}")
        print()

    try:
        models = provider.list_models()
        if models:
            print("Available models:")
            for m in models:
                tag = "FREE" if m.free else "PAID"
                print(f"  [{tag}] {m.id} ({m.provider})")
        else:
            print("No models available.")
    except Exception as e:
        print(f"Failed to list models: {e}")

    return 0


def cmd_gateway_serve(config: ArgusConfig) -> int:
    from argus.gateway import GatewayServer, GatewayServerConfig

    free_pool = config.get("free_pool", {})
    free_pool_providers = free_pool.get("providers", {})

    server_config = GatewayServerConfig(
        host=config.get("gateway_server.host", "127.0.0.1"),
        port=int(config.get("gateway_server.port", 8787)),
        free_requests=int(config.get("gateway_server.free_requests", 20)),
        free_window_seconds=float(config.get("gateway_server.free_window_seconds", 3600)),
        providers=free_pool_providers,
        strategy=free_pool.get("strategy", "free_first"),
    )
    server = GatewayServer(config=server_config)
    print(f"Argus Gateway Server starting on http://{server_config.host}:{server_config.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    return 0


def cmd_onboard(config: ArgusConfig, credentials: CredentialManager) -> int:
    print()
    print("Welcome to Argus")
    print()
    print("Choose how Argus gets its AI:")
    print()
    print("1. Free models (Argus Gateway - no API key needed)")
    print("2. Connect a paid provider (OpenAI, Anthropic)")
    print("3. Local Ollama")
    print("4. Configure later")
    print()

    choice = input("Enter choice [1-4]: ").strip()
    if choice == "1":
        print()
        print("Free models selected.")
        print("Argus will use the Argus Free Gateway.")
        print("No API key needed.")
        config.set("model.provider", "gateway")
        config.set("model.name", "auto")
        try:
            config.save()
        except Exception:
            pass
        return 0
    elif choice == "2":
        _onboard_paid(credentials)
    elif choice == "3":
        print()
        print("Local Ollama selected.")
        print("Make sure Ollama is running at http://localhost:11434")
        config.set("model.provider", "ollama")
        config.set("model.name", "llama3")
        try:
            config.save()
        except Exception:
            pass
        return 0
    else:
        print("Skipping setup. You can run 'argus onboard' later.")
        return 0

    try:
        config.save()
    except Exception:
        pass
    return 0


def _onboard_free(credentials: CredentialManager) -> None:
    print()
    print("Free models")
    print("Configure any providers you have API keys for.")
    print("You can skip any provider and add more later.")
    print()

    for provider_id, provider_name, models in FREE_PROVIDERS:
        key = input(f"{provider_name} API key (leave blank to skip): ").strip()
        if key:
            credentials.set(provider_id, key)
            print(f"  {provider_name} saved.")
        else:
            print(f"  {provider_name} skipped.")

    print()
    print("Credentials saved to:", credentials._path)


def _onboard_paid(credentials: CredentialManager) -> None:
    print()
    print("Paid providers")
    print("Enter your API keys. You can skip any provider.")
    print()

    for provider_id, label in [("openai", "OpenAI"), ("anthropic", "Anthropic")]:
        key = input(f"{label} API key (leave blank to skip): ").strip()
        if key:
            credentials.set(provider_id, key)
            print(f"  {label} saved.")
        else:
            print(f"  {label} skipped.")


def cmd_usage(config: ArgusConfig, usage: Optional[UsageTracker] = None) -> int:
    print("ARGUS AI USAGE")
    print()

    if not usage:
        print("Usage tracking is not available.")
        return 0

    entries = usage.today()
    stats = usage.provider_stats(entries)

    print("TODAY")
    print()
    if stats:
        for provider, data in sorted(stats.items()):
            print(f"{provider}")
            print(f"  requests: {data['requests']}")
            print(f"  tokens: {data['tokens']}")
            print(f"  cost: ${data['cost']:.2f}")
            if data["errors"]:
                print(f"  errors: {data['errors']}")
            print()
    else:
        print("No usage recorded today.")
        print()

    strategy = config.get("model_hub.strategy", "free_first")
    daily_limit = config.get("model_hub.budget.daily_limit", 0.0)
    print(f"Strategy: {strategy}")
    print(f"Budget daily limit: ${daily_limit:.2f}")
    return 0


def main(args=None) -> int:
    parsed = parse_args(args)
    setup_logging("DEBUG" if parsed.verbose else "INFO")

    project_path = Path(parsed.project).resolve() if parsed.project else Path.cwd()
    config = ArgusConfig(parsed.config)
    credentials = CredentialManager()
    usage = UsageTracker()

    request = parsed.request

    if parsed.serve_gateway:
        return cmd_gateway_serve(config)

    if request == "onboard":
        return cmd_onboard(config, credentials)

    if request == "usage":
        return cmd_usage(config, usage)

    if request == "gateway":
        return cmd_gateway(config)

    mode = parsed.mode
    if not mode:
        gateway_config = config.get("gateway", {})
        if _has_byok_credentials(config, credentials):
            mode = "byok"
        elif gateway_config and gateway_config.get("base_url"):
            mode = "free"
        else:
            mode = "local"

    if request in ("providers", "models", "model"):
        router = _build_router(config, credentials)
        if request == "providers":
            return cmd_providers(config, router, credentials)
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
        if mode == "free":
            model = _build_gateway_model(config)
            if model:
                model = GatewayModelProvider(
                    base_url=config.get("gateway.base_url", ""),
                    api_key=config.get("gateway.api_key", ""),
                    fallback_provider=_build_fallback_model(config),
                )
            else:
                model = _build_fallback_model(config)
        elif mode == "local":
            model_config = {
                "provider": "ollama",
                "name": config.get("model.name", "llama3"),
            }
            if config.get("model.base_url"):
                model_config["base_url"] = config["model.base_url"]
            model = create_model_from_config(model_config)
        else:
            router = _build_router(config, credentials)
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
