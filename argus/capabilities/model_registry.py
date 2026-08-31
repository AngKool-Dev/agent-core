"""Model provider capability registry integration with existing Argus model hub."""

from typing import Any, Dict, List, Optional

from argus.capabilities import Capability, CapabilityRegistry, CapabilityType
from argus.capabilities.model_adapter import (
    create_model_capability,
    create_model_router_capability,
)
from argus.model.hub import ModelRouter, ProviderRegistry, ProviderState, Strategy, Budget
from argus.model.provider import ModelProvider


def register_all_provider_capabilities(
    capability_registry: CapabilityRegistry,
    provider_registry: ProviderRegistry,
) -> None:
    """Register all providers from ProviderRegistry as individual capabilities."""
    for state in provider_registry.list_states():
        if state.provider:
            provider_name = state.capability.name
            cap_id = f"model.provider.{provider_name}"

            cap = create_model_capability(
                capability_id=cap_id,
                name=f"Model: {provider_name}",
                description=f"Model provider: {provider_name} with models {state.capability.models}",
                model_provider=state.provider,
                capabilities=state.capability.capabilities or ["chat", "coding"],
                permissions={"use": "allow"},
                cost={},
            )
            capability_registry.register(cap)


def register_model_router_capability(
    capability_registry: CapabilityRegistry,
    provider_registry: ProviderRegistry,
    strategy: Strategy = Strategy.FREE_FIRST,
    budget: Optional[Budget] = None,
    preferred_model: Optional[str] = None,
    usage_tracker: Optional[Any] = None,
) -> Capability:
    """Register a ModelRouter as a capability in the capability registry."""
    model_router = ModelRouter(
        registry=provider_registry,
        strategy=strategy,
        budget=budget,
        preferred_model=preferred_model,
        usage_tracker=usage_tracker,
    )

    cap = create_model_capability(
        capability_id="argus.model_router",
        name="Argus Model Router",
        description="Intelligent model selection and routing across all providers",
        model_provider=model_router,
        capabilities=["chat", "coding", "reasoning", "tool_use", "routing"],
        permissions={"use": "allow"},
        cost={},
    )
    capability_registry.register(cap)
    return cap


def register_model_router_from_config(
    capability_registry: CapabilityRegistry,
    provider_registry: ProviderRegistry,
    config: Dict[str, Any],
    usage_tracker: Optional[Any] = None,
) -> Capability:
    """Register a ModelRouter capability from configuration dict."""
    strategy_str = config.get("strategy", "free_first")
    strategy_map = {
        "free_first": Strategy.FREE_FIRST,
        "balanced": Strategy.BALANCED,
        "quality_first": Strategy.QUALITY_FIRST,
        "manual": Strategy.MANUAL,
        "local_first": Strategy.LOCAL_FIRST,
        "capability_first": Strategy.CAPABILITY_FIRST,
    }
    strategy = strategy_map.get(strategy_str, Strategy.FREE_FIRST)

    budget_config = config.get("budget", {})
    budget = Budget(
        allow_paid=budget_config.get("allow_paid", True),
        daily_limit=budget_config.get("daily_limit", 0.0),
        spent=budget_config.get("spent", 0.0),
    )

    preferred_model = config.get("preferred_model")

    return register_model_router_capability(
        capability_registry=capability_registry,
        provider_registry=provider_registry,
        strategy=strategy,
        budget=budget,
        preferred_model=preferred_model,
        usage_tracker=usage_tracker,
    )


def create_model_capability_from_provider(
    provider_name: str,
    provider: ModelProvider,
    capability_config: Dict[str, Any] = None,
) -> Capability:
    """Create a capability from a single model provider instance."""
    config = capability_config or {}
    return create_model_capability(
        capability_id=f"model.provider.{provider_name}",
        name=config.get("name", f"Model: {provider_name}"),
        description=config.get("description", f"Model provider: {provider_name}"),
        model_provider=provider,
        capabilities=config.get("capabilities", ["chat", "coding"]),
        permissions=config.get("permissions", {"use": "allow"}),
        cost=config.get("cost", {}),
    )


def sync_provider_registry_to_capabilities(
    capability_registry: CapabilityRegistry,
    provider_registry: ProviderRegistry,
) -> Dict[str, int]:
    """Sync ProviderRegistry to CapabilityRegistry.
    
    Returns dict with counts: {'registered': N, 'skipped': M, 'errors': K}
    """
    registered = 0
    skipped = 0
    errors = 0

    for state in provider_registry.list_states():
        if not state.provider:
            skipped += 1
            continue

        provider_name = state.capability.name
        cap_id = f"model.provider.{provider_name}"

        # Check if already registered
        if capability_registry.get(cap_id):
            skipped += 1
            continue

        try:
            cap = create_model_capability_from_provider(
                provider_name=provider_name,
                provider=state.provider,
                capability_config={
                    "name": f"Model: {provider_name}",
                    "description": f"Provider: {provider_name} with models {state.capability.models}",
                    "capabilities": state.capability.capabilities or ["chat", "coding"],
                },
            )
            capability_registry.register(cap)
            registered += 1
        except Exception:
            errors += 1

    return {"registered": registered, "skipped": skipped, "errors": errors}


def get_model_capabilities_summary(capability_registry: CapabilityRegistry) -> Dict[str, Any]:
    """Get summary of all model capabilities in the registry."""
    model_caps = capability_registry.get_by_type(CapabilityType.MODEL)
    
    summary = {
        "total": len(model_caps),
        "providers": [],
        "router": None,
    }

    for cap in model_caps:
        info = {
            "id": cap.get_id(),
            "name": cap.get_name(),
            "description": cap.get_description(),
            "available": cap.check_availability(),
            "health": cap.health_check(),
        }
        
        if "router" in cap.get_id() or "router" in cap.get_name().lower():
            summary["router"] = info
        else:
            summary["providers"].append(info)

    return summary


def get_available_model_capabilities(capability_registry: CapabilityRegistry) -> List[Capability]:
    """Get all available model capabilities (healthy and available)."""
    model_caps = capability_registry.get_by_type(CapabilityType.MODEL)
    return [
        cap for cap in model_caps 
        if cap.check_availability() and cap.health_check().get("status") == "healthy"
    ]


def execute_model_capability(
    capability_registry: CapabilityRegistry,
    capability_id: str,
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    request: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a model capability with standard parameters."""
    cap = capability_registry.get(capability_id)
    if not cap:
        return {"success": False, "error": f"Capability not found: {capability_id}"}

    return cap.execute({
        "messages": messages,
        "model": model or "",
        "tools": tools or [],
        "request": request or "",
    })


def auto_register_model_capabilities(
    capability_registry: CapabilityRegistry,
    provider_registry: ProviderRegistry,
    config: Dict[str, Any] = None,
    usage_tracker: Optional[Any] = None,
) -> Dict[str, Any]:
    """Auto-register all model capabilities from provider registry and config.
    
    This is the main entry point for integrating Argus model hub with capability system.
    """
    results = {
        "providers": {"registered": 0, "skipped": 0, "errors": 0},
        "router": None,
    }

    # Sync provider registry
    sync_result = sync_provider_registry_to_capabilities(
        capability_registry=capability_registry,
        provider_registry=provider_registry,
    )
    results["providers"] = sync_result

    # Register model router from config
    if config:
        router_cap = register_model_router_from_config(
            capability_registry=capability_registry,
            provider_registry=provider_registry,
            config=config,
            usage_tracker=usage_tracker,
        )
        results["router"] = {
            "id": router_cap.get_id(),
            "name": router_cap.get_name(),
        }

    return results