"""Model provider capability adapter."""

from typing import Any, Dict, List, Optional

from argus.capabilities import (
    Capability,
    CapabilityMetadata,
    CapabilitySchema,
    CapabilityType,
    ModelCapability,
)
from argus.model import ModelProvider
from argus.model.hub import ModelRouter, ProviderRegistry, TaskClassifier
from argus.model.factory import create_model_from_config


class ModelCapabilityAdapter(Capability):
    """Adapter that wraps Argus ModelProvider as a Capability."""

    def __init__(self, metadata: CapabilityMetadata, model_provider: ModelProvider):
        super().__init__(metadata)
        self._model_provider = model_provider

    def check_availability(self) -> bool:
        return self.metadata.availability and self._model_provider is not None

    def health_check(self) -> Dict[str, Any]:
        try:
            # Try to get provider health/status if available
            if hasattr(self._model_provider, "health"):
                health = self._model_provider.health()
                return {"status": "healthy", "provider": health}
            elif hasattr(self._model_provider, "list_models"):
                models = self._model_provider.list_models()
                return {"status": "healthy", "models_available": len(models)}
            elif hasattr(self._model_provider, "complete"):
                # Try a simple completion to test
                test_response = self._model_provider.complete(
                    messages=[{"role": "user", "content": "ping"}], model="", tools=[]
                )
                return {"status": "healthy", "can_complete": True}
            else:
                return {"status": "unknown", "message": "No health check available"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        import time
        start_time = time.time()

        try:
            # Model capability execution
            messages = input_data.get("messages", [])
            model = input_data.get("model", "")
            tools = input_data.get("tools", [])
            request = input_data.get("request", "")

            # Execute via the model provider
            response = self._model_provider.complete(
                messages=messages,
                model=model,
                tools=tools,
                request=request,
            )

            # Handle both dict and ModelResponse outputs
            if isinstance(response, dict):
                output_content = response.get("content", "")
                tool_calls = response.get("tool_calls", [])
            else:
                output_content = response.content
                tool_calls = response.tool_calls

            execution_time = time.time() - start_time
            return {
                "success": True,
                "output": {
                    "content": output_content,
                    "tool_calls": tool_calls,
                    "usage": getattr(response, "usage", {}),
                },
                "error": None,
                "execution_time": execution_time,
                "backend": "model_provider",
            }

        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "execution_time": execution_time,
                "backend": "model_provider",
            }


def create_model_capability(
    capability_id: str,
    name: str,
    description: str,
    model_provider: ModelProvider,
    capabilities: List[str] = None,
    permissions: Dict[str, str] = None,
    cost: Dict[str, float] = None,
    fallback: Dict[str, Any] = None,
) -> Capability:
    """Create a model capability from an existing ModelProvider."""
    schema = CapabilitySchema(
        name=name,
        description=description,
        parameters={
            "type": "object",
            "properties": {
                "messages": {"type": "array", "description": "List of message objects"},
                "model": {"type": "string", "description": "Model name"},
                "tools": {"type": "array", "description": "List of tools to use"},
                "request": {"type": "string", "description": "Original user request"},
            },
            "required": ["messages"],
        },
        required_parameters=["messages"],
    )

    metadata = CapabilityMetadata(
        id=capability_id,
        name=name,
        description=description,
        type=CapabilityType.MODEL,
        schema=schema,
        permissions=permissions or {},
        cost=cost or {},
        fallback=fallback,
    )

    return ModelCapabilityAdapter(metadata, model_provider)


def create_model_router_capability(
    capability_id: str,
    name: str,
    description: str,
    registry: ProviderRegistry,
    strategy: Any = None,
    budget: Any = None,
    preferred_model: Optional[str] = None,
    usage_tracker: Any = None,
    capabilities: List[str] = None,
    permissions: Dict[str, str] = None,
    cost: Dict[str, float] = None,
    fallback: Dict[str, Any] = None,
) -> Capability:
    """Create a model router capability from an existing ModelRouter."""
    # Create a ModelRouter instance
    from argus.model.hub import Strategy

    model_router = ModelRouter(
        registry=registry,
        strategy=strategy or Strategy.FREE_FIRST,
        budget=budget,
        preferred_model=preferred_model,
        usage_tracker=usage_tracker,
    )

    return create_model_capability(
        capability_id=capability_id,
        name=name,
        description=description,
        model_provider=model_router,
        capabilities=capabilities,
        permissions=permissions,
        cost=cost,
        fallback=fallback,
    )


def create_gateway_model_capability(
    capability_id: str,
    name: str,
    description: str,
    base_url: str,
    api_key: str = "",
    timeout: int = 120,
    capabilities: List[str] = None,
    permissions: Dict[str, str] = None,
    cost: Dict[str, float] = None,
    fallback: Dict[str, Any] = None,
) -> Capability:
    """Create a gateway model capability from Argus Gateway configuration."""
    from argus.model.providers.gateway import GatewayModelProvider

    gateway_provider = GatewayModelProvider(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
    )

    return create_model_capability(
        capability_id=capability_id,
        name=name,
        description=description,
        model_provider=gateway_provider,
        capabilities=capabilities,
        permissions=permissions,
        cost=cost,
        fallback=fallback,
    )


def register_default_model_capabilities(
    registry: Any,
    config: Dict[str, Any] = None,
) -> None:
    """Register default model provider capabilities based on configuration."""
    from argus.model.hub import ProviderRegistry

    # This would typically load from config
    # For now, return without registering to maintain compatibility
    # with existing model loading mechanism
    pass


def adapt_existing_model_routing(
    capability_registry: Any,
    model_hub_config: Dict[str, Any],
    credentials: Any = None,
    usage_tracker: Any = None,
) -> None:
    """Adapt existing Argus ModelRouter to work within capability system."""
    from argus.model.hub import ProviderRegistry
    from argus.model.factory import create_router_from_config

    # Create a model router from the existing configuration
    try:
        model_router = create_router_from_config(model_hub_config, usage_tracker)

        # Get all capabilities from the registry
        capability_registry.set_registry_references(
            tool_registry=None,
            permissions=None,
            model_provider=model_router,
        )

        # Create a model capability from the router
        model_cap = create_model_capability(
            capability_id="argus.model_router",
            name="Argus Model Router",
            description="Argus intelligent model selection and routing",
            model_provider=model_router,
            capabilities=["chat", "coding", "reasoning", "tool_use"],
            permissions={"use": "allow"},
        )

        capability_registry.register(model_cap)
    except Exception:
        # If model router creation fails, fall back to direct capabilities
        pass


def create_capability_from_model_config(
    config: Dict[str, Any],
    provider_name: str = None,
) -> Optional[Capability]:
    """Create a model capability from a model configuration."""
    if not config:
        return None

    provider_type = config.get("provider", "ollama")
    provider_name = provider_name or provider_type
    name = config.get("name", "")
    api_key = config.get("api_key", "")
    base_url = config.get("base_url", "")

    if provider_type == "gateway":
        return create_gateway_model_capability(
            capability_id=f"model.{provider_name}",
            name=f"{name} (Gateway)",
            description=f"Argus Gateway model: {name}",
            base_url=base_url or "http://localhost:8787",
            api_key=api_key,
            capabilities=["chat", "coding"],
        )

    # For local model providers (ollama, etc.), we'd need to create
    # model instances and wrap them
    # This maintains compatibility with existing model loading
    return None
