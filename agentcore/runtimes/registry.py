"""
Runtime registry and factory for AgentCore.

Allows registration and creation of runtime adapters by name.
Third-party runtimes can register themselves without modifying AgentCore core.
"""

from collections.abc import Callable
from typing import Any

from .base import RuntimeAdapter, RuntimeCapabilities


class RuntimeRegistry:
    """
    Registry of available runtime adapters.

    Runtimes are registered by name with a factory callable and optional metadata.
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[..., RuntimeAdapter]] = {}
        self._info: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        factory: Callable[..., RuntimeAdapter],
        info: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a runtime factory.

        Args:
            name: Runtime identifier (e.g. "hermes", "kilo").
            factory: Callable that returns a RuntimeAdapter instance.
            info: Optional metadata dict (description, capabilities, etc.).
        """
        self._factories[name] = factory
        self._info[name] = info or {}

    def create(self, name: str, **kwargs: Any) -> RuntimeAdapter:
        """
        Create a runtime adapter by name.

        Args:
            name: Runtime identifier.
            **kwargs: Arguments forwarded to the factory.

        Returns:
            RuntimeAdapter instance.

        Raises:
            ValueError: If the runtime is not registered.
        """
        if name not in self._factories:
            available = ", ".join(sorted(self._factories.keys())) or "none"
            raise ValueError(f"Unknown runtime '{name}'. Available runtimes: {available}")
        return self._factories[name](**kwargs)

    def list_runtimes(self) -> list[str]:
        """Return sorted list of registered runtime names."""
        return sorted(self._factories.keys())

    def get_info(self, name: str) -> dict[str, Any]:
        """
        Return metadata for a registered runtime.

        Raises:
            ValueError: If the runtime is not registered.
        """
        if name not in self._info:
            raise ValueError(f"Unknown runtime '{name}'")
        return dict(self._info[name])

    def get_capabilities(self, name: str) -> RuntimeCapabilities:
        """
        Query capabilities for a runtime without instantiating it.

        Returns the capabilities from the registered info dict, if available.
        """
        info = self.get_info(name)
        caps = info.get("capabilities", {})
        return RuntimeCapabilities(**caps)

    def is_registered(self, name: str) -> bool:
        """Check if a runtime is registered."""
        return name in self._factories


_default_registry: RuntimeRegistry | None = None


def get_default_registry() -> RuntimeRegistry:
    """Return the global default runtime registry, registering built-in runtimes."""
    global _default_registry
    if _default_registry is None:
        _default_registry = RuntimeRegistry()
        _register_builtin_runtimes(_default_registry)
    return _default_registry


def _register_builtin_runtimes(registry: RuntimeRegistry) -> None:
    """Register the built-in Hermes runtime."""
    try:
        from .hermes import create_hermes_runtime

        registry.register(
            "hermes",
            create_hermes_runtime,
            info={
                "description": "Hermes CLI runtime (hermes -z)",
                "adapter": "hermes",
                "capabilities": {
                    "text_generation": True,
                    "tool_calls": False,
                    "external_tool_execution": False,
                    "streaming": False,
                    "cancellation": True,
                },
            },
        )
    except ImportError:
        pass
