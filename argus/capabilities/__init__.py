"""Argus capability abstraction."""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from argus.discovery import CapabilityDiscoveryRegistry, CapabilityMetadata as DiscoveryCapabilityMetadata


class CapabilityType(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    SEARCH = "search"
    BROWSER = "browser"
    MODEL = "model"
    MEMORY = "memory"
    GIT = "git"
    REACH = "reach"
    COMMANDS = "commands"


@dataclass
class CapabilitySchema:
    name: str
    description: str
    input_type: str = "object"
    output_type: str = "object"
    parameters: Optional[Dict[str, Any]] = None
    required_parameters: List[str] = field(default_factory=list)


@dataclass
class CapabilityMetadata:
    id: str
    name: str
    description: str
    type: CapabilityType
    schema: CapabilitySchema
    permissions: Dict[str, str] = field(default_factory=dict)
    cost: Dict[str, float] = field(default_factory=dict)
    fallback: Optional[Dict[str, Any]] = None
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_checked: float = field(default_factory=time.time)
    health_status: str = "unknown"
    availability: bool = True


@dataclass
class CapabilityExecution:
    capability_id: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    success: bool = False
    error: Optional[str] = None
    execution_time: float = 0.0
    backend: str = ""
    fallback_used: bool = False
    timestamp: float = field(default_factory=time.time)


class Capability(ABC):
    def __init__(self, metadata: CapabilityMetadata):
        self.metadata = metadata

    @abstractmethod
    def check_availability(self) -> bool:
        """Check if capability is available."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform health check and return status."""
        pass

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute capability with input data."""
        pass

    def get_id(self) -> str:
        return self.metadata.id

    def get_name(self) -> str:
        return self.metadata.name

    def get_description(self) -> str:
        return self.metadata.description

    def get_type(self) -> CapabilityType:
        return self.metadata.type

    def can_execute(self, input_data: Dict[str, Any]) -> bool:
        """Check if capability can execute with given input."""
        if not self.check_availability():
            return False
        if self.metadata.schema.parameters:
            for param in self.metadata.schema.required_parameters:
                if param not in input_data:
                    return False
        return True

    def validate_input(self, input_data: Dict[str, Any]) -> List[str]:
        """Validate input and return list of errors."""
        errors = []
        if not self.check_availability():
            errors.append(f"Capability {self.get_name()} is not available")

        if self.metadata.schema.parameters:
            for param in self.metadata.schema.required_parameters:
                if param not in input_data:
                    errors.append(f"Required parameter '{param}' is missing")

        return errors


class ToolCapability(Capability):
    def __init__(
        self,
        metadata: CapabilityMetadata,
        tool_registry_ref: Any,
        permissions_ref: Any,
    ):
        super().__init__(metadata)
        self._tool_registry = tool_registry_ref
        self._permissions = permissions_ref

    def check_availability(self) -> bool:
        """Check if tool is available and permission granted."""
        if not self.metadata.availability:
            return False
        # Check if tool exists
        tool = self._tool_registry.get(self.metadata.id)
        if not tool:
            return False
        # Check permission
        if self._permissions and not self._permissions.allows(self.metadata.id):
            return False
        return True

    def health_check(self) -> Dict[str, Any]:
        """Check tool health."""
        tool = self._tool_registry.get(self.metadata.id)
        if not tool:
            return {"status": "error", "message": "Tool not found"}

        if not self.check_availability():
            return {"status": "error", "message": "Tool unavailable or permission denied"}

        try:
            # Try a minimal validation
            tool_result = self._tool_registry.execute(self.metadata.id, **{})
            return {
                "status": "healthy" if tool_result.success else "error",
                "message": "Tool available and responded",
                "last_check": time.time(),
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "last_check": time.time()}

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool via registry."""
        start_time = time.time()
        try:
            result = self._tool_registry.execute(self.metadata.id, **input_data)
            execution_time = time.time() - start_time

            execution = CapabilityExecution(
                capability_id=self.get_id(),
                input_data=input_data,
                output_data=result.to_dict(),
                success=result.success,
                error=result.error,
                execution_time=execution_time,
                backend="tool_registry",
            )

            return {
                "success": execution.success,
                "output": execution.output_data,
                "error": execution.error,
                "execution_time": execution.execution_time,
                "backend": execution.backend,
                "fallback_used": execution.fallback_used,
            }
        except Exception as e:
            execution_time = time.time() - start_time
            execution = CapabilityExecution(
                capability_id=self.get_id(),
                input_data=input_data,
                success=False,
                error=str(e),
                execution_time=execution_time,
                backend="tool_registry",
            )
            return {
                "success": False,
                "output": None,
                "error": execution.error,
                "execution_time": execution.execution_time,
                "backend": execution.backend,
                "fallback_used": execution.fallback_used,
            }


class ModelCapability(Capability):
    def __init__(self, metadata: CapabilityMetadata, model_provider_ref: Any):
        super().__init__(metadata)
        self._model_provider = model_provider_ref

    def check_availability(self) -> bool:
        return self.metadata.availability and self._model_provider is not None

    def health_check(self) -> Dict[str, Any]:
        try:
            # Try to get provider health/status
            if hasattr(self._model_provider, "health"):
                health = self._model_provider.health()
                return {"status": "healthy", "provider": health}
            return {"status": "unknown", "message": "No health check available"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        try:
            # Model capability execution
            messages = input_data.get("messages", [])
            model = input_data.get("model", "")
            tools = input_data.get("tools", [])

            response = self._model_provider.complete(
                messages=messages,
                model=model,
                tools=tools,
                request=input_data.get("request", ""),
            )

            execution_time = time.time() - start_time
            return {
                "success": True,
                "output": {
                    "content": response.content,
                    "tool_calls": response.tool_calls,
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


class CapabilityRegistry:
    def __init__(self):
        self._capabilities: Dict[str, Capability] = {}
        self._tool_registry_ref = None
        self._permissions_ref = None
        self._model_provider_ref = None

    def register(self, capability: Capability) -> None:
        self._capabilities[capability.get_id()] = capability

    def register_tool_capability(
        self,
        capability_id: str,
        name: str,
        description: str,
        tool_name: str,
        capabilities: List[str] = None,
        permissions: Dict[str, str] = None,
        cost: Dict[str, float] = None,
        fallback: Dict[str, Any] = None,
    ) -> None:
        capability_type = self._infer_type_from_tool_name(tool_name)

        schema = CapabilitySchema(
            name=name,
            description=description,
            parameters={},
            required_parameters=[],
        )

        metadata = CapabilityMetadata(
            id=capability_id,
            name=name,
            description=description,
            type=capability_type,
            schema=schema,
            permissions=permissions or {},
            cost=cost or {},
            fallback=fallback,
        )

        capability = ToolCapability(metadata, self._tool_registry_ref, self._permissions_ref)
        self.register(capability)

    def register_model_capability(
        self,
        capability_id: str,
        name: str,
        description: str,
        capabilities: List[str] = None,
        permissions: Dict[str, str] = None,
        cost: Dict[str, float] = None,
        fallback: Dict[str, Any] = None,
    ) -> None:
        schema = CapabilitySchema(
            name=name,
            description=description,
            parameters={"messages": [], "model": "", "tools": []},
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

        capability = ModelCapability(metadata, self._model_provider_ref)
        self.register(capability)

    def set_registry_references(self, tool_registry=None, permissions=None, model_provider=None):
        self._tool_registry_ref = tool_registry
        self._permissions_ref = permissions
        self._model_provider_ref = model_provider

    def get(self, capability_id: str) -> Optional[Capability]:
        return self._capabilities.get(capability_id)

    def list(self) -> List[Capability]:
        return list(self._capabilities.values())

    def search(self, query: str) -> List[Capability]:
        query_lower = query.lower()
        results = []
        for capability in self._capabilities.values():
            if (query_lower in capability.get_name().lower() or
                query_lower in capability.get_description().lower() or
                query_lower in capability.get_type().value.lower()):
                results.append(capability)
        return results

    def get_by_type(self, capability_type: CapabilityType) -> List[Capability]:
        return [c for c in self._capabilities.values() if c.get_type() == capability_type]

    def _infer_type_from_tool_name(self, tool_name: str) -> CapabilityType:
        if tool_name in ("read_file", "list_dir"):
            return CapabilityType.READ
        elif tool_name in ("write_file", "edit_file"):
            return CapabilityType.WRITE
        elif tool_name in ("bash",):
            return CapabilityType.EXECUTE
        elif tool_name in ("grep", "glob"):
            return CapabilityType.SEARCH
        elif tool_name in ("browser",):
            return CapabilityType.BROWSER
        elif tool_name in ("git_status", "git_diff", "git_log", "git_add", "git_commit", "git_workflow"):
            return CapabilityType.GIT
        else:
            return CapabilityType.EXECUTE


class CapabilityRouter:
    def __init__(self, registry: CapabilityRegistry):
        self._registry = registry
        self._execution_history: Dict[str, List[CapabilityExecution]] = {}

    def route(self, capability_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        capability = self._registry.get(capability_id)
        if not capability:
            return {
                "success": False,
                "error": f"Capability not found: {capability_id}",
                "fallback_used": False,
            }

        if not capability.can_execute(input_data):
            # Try fallback if available
            if capability.metadata.fallback:
                return self._handle_fallback(capability, input_data)
            return {
                "success": False,
                "error": f"Capability cannot execute with given input",
                "fallback_used": False,
            }

        return self._execute_with_fallbacks(capability, input_data)

    def _execute_with_fallbacks(self, capability: Capability, input_data: Dict[str, Any]) -> Dict[str, Any]:
        fallback_chain = [capability]
        if capability.metadata.fallback:
            fallback_chain.append(capability.metadata.fallback)

        last_error = None
        for fallback_cap in fallback_chain:
            try:
                result = fallback_cap.execute(input_data)
                self._record_execution(capability.get_id(), result)

                if result.get("success"):
                    return {**result, "fallback_used": fallback_cap.get_id() != capability.get_id()}
                last_error = result.get("error")
            except Exception as e:
                last_error = str(e)

        return {
            "success": False,
            "error": f"All backends failed. Last error: {last_error}",
            "fallback_used": False,
        }

    def _handle_fallback(self, capability: Capability, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "error": "Primary capability unavailable, fallback configured but not implemented",
            "fallback_used": True,
        }

    def _record_execution(self, capability_id: str, result: Dict[str, Any]) -> None:
        execution = CapabilityExecution(
            capability_id=capability_id,
            input_data=result.get("input_data", {}),
            output_data=result.get("output"),
            success=result.get("success", False),
            error=result.get("error"),
            execution_time=result.get("execution_time", 0.0),
            backend=result.get("backend", ""),
            fallback_used=result.get("fallback_used", False),
        )

        if capability_id not in self._execution_history:
            self._execution_history[capability_id] = []
        self._execution_history[capability_id].append(execution)

    def get_execution_history(self, capability_id: str, limit: int = 10) -> List[CapabilityExecution]:
        history = self._execution_history.get(capability_id, [])
        return history[-limit:]

    def get_health_status(self) -> Dict[str, Any]:
        health_status = {}
        for capability_id, capability in self._registry._capabilities.items():
            health = capability.health_check()
            health_status[capability_id] = {
                "name": capability.get_name(),
                "type": capability.get_type().value,
                "health": health,
                "available": capability.check_availability(),
            }
        return health_status

    def route_by_query(
        self,
        query: str,
        input_data: Dict[str, Any],
        capability_type: CapabilityType = None,
    ) -> Dict[str, Any]:
        candidates = self._registry.search(query)
        if capability_type:
            candidates = [c for c in candidates if c.get_type() == capability_type]

        if not candidates:
            return {
                "success": False,
                "error": f"No capabilities found matching query: {query}",
                "fallback_used": False,
            }

        # Sort by ranking (available first, then by execution history)
        ranked = self._rank_capabilities(candidates)
        primary = ranked[0]

        result = self._execute_with_fallbacks(primary, input_data)
        result["routed_capability"] = primary.get_id()
        result["candidates_tried"] = len(ranked)
        return result

    def _rank_capabilities(self, capabilities: List[Capability]) -> List[Capability]:
        """Rank capabilities by availability, health, and execution history."""

        def score(cap: Capability) -> float:
            score_val = 0.0

            # Availability score
            if cap.check_availability():
                score_val += 100.0
            else:
                return score_val  # Unavailable gets lowest score

            # Health score
            health = cap.health_check()
            health_status = health.get("status", "unknown")
            if health_status == "healthy":
                score_val += 50.0
            elif health_status == "degraded":
                score_val += 25.0

            # Execution history score
            history = self._execution_history.get(cap.get_id(), [])
            if history:
                success_count = sum(1 for h in history if h.success)
                total_count = len(history)
                success_rate = success_count / total_count if total_count > 0 else 0.5
                score_val += success_rate * 30.0

                # Recency bonus
                recent = [h for h in history if time.time() - h.timestamp < 300]
                if recent:
                    score_val += 10.0

            return score_val

        return sorted(capabilities, key=score, reverse=True)

    def route_fallback(
        self,
        capability_id: str,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Route to a fallback capability when primary fails."""
        capability = self._registry.get(capability_id)
        if not capability:
            return {
                "success": False,
                "error": f"Capability not found: {capability_id}",
                "fallback_used": False,
            }

        # Find alternative capabilities of the same type
        same_type = self._registry.get_by_type(capability.get_type())
        alternatives = [c for c in same_type if c.get_id() != capability_id and c.check_availability()]

        if not alternatives:
            return {
                "success": False,
                "error": f"No fallback available for {capability_id}",
                "fallback_used": False,
            }

        ranked = self._rank_capabilities(alternatives)
        fallback = ranked[0]

        result = self._execute_with_fallbacks(fallback, input_data)
        result["routed_capability"] = fallback.get_id()
        result["fallback_used"] = True
        result["original_capability"] = capability_id
        return result

    def discover_capabilities(
        self,
        query: str = "",
        capability_type: CapabilityType = None,
        available_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Discover and return capabilities matching criteria."""
        if query:
            candidates = self._registry.search(query)
        else:
            candidates = self._registry.list()

        if capability_type:
            candidates = [c for c in candidates if c.get_type() == capability_type]

        if available_only:
            candidates = [c for c in candidates if c.check_availability()]

        results = []
        for cap in candidates:
            results.append({
                "id": cap.get_id(),
                "name": cap.get_name(),
                "description": cap.get_description(),
                "type": cap.get_type().value,
                "available": cap.check_availability(),
                "health": cap.health_check(),
            })

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics for all capabilities."""
        stats = {}
        for cap_id, history in self._execution_history.items():
            if not history:
                continue
            total = len(history)
            successful = sum(1 for h in history if h.success)
            failed = total - successful
            avg_time = sum(h.execution_time for h in history) / total if total > 0 else 0

            stats[cap_id] = {
                "total_executions": total,
                "successful": successful,
                "failed": failed,
                "success_rate": successful / total if total > 0 else 0.0,
                "avg_execution_time": avg_time,
            }
        return stats

    def clear_history(self, capability_id: str = None) -> None:
        """Clear execution history for a specific capability or all."""
        if capability_id:
            self._execution_history.pop(capability_id, None)
        else:
            self._execution_history.clear()


class CapabilityDiscoveryIntegration:
    """Integrates the discovery subsystem with the capability registry."""

    def __init__(self, registry: CapabilityRegistry):
        self._registry = registry
        self._discovery_registry = CapabilityDiscoveryRegistry()

    def register_discovery_source(self, source: Any) -> None:
        """Register a discovery source."""
        self._discovery_registry.register_source(source)

    def discover_and_register(self) -> List[str]:
        """Discover capabilities and register them with the capability registry."""
        discovered = self._discovery_registry.discover_all()
        registered_ids = []

        for cap_meta in discovered:
            # Convert discovery metadata to capability metadata
            capability_type = self._infer_capability_type(cap_meta)
            schema = CapabilitySchema(
                name=cap_meta.name,
                description=cap_meta.description,
                parameters=cap_meta.config,
                required_parameters=[],
            )
            metadata = CapabilityMetadata(
                id=cap_meta.name,
                name=cap_meta.name,
                description=cap_meta.description,
                type=capability_type,
                schema=schema,
                tags=cap_meta.tags,
                version=cap_meta.version,
            )

            # Create a placeholder capability
            capability = _DiscoveredCapability(metadata, cap_meta)
            self._registry.register(capability)
            registered_ids.append(cap_meta.name)

        return registered_ids

    def _infer_capability_type(self, cap_meta: DiscoveryCapabilityMetadata) -> CapabilityType:
        """Infer capability type from discovery metadata."""
        tags_lower = [t.lower() for t in cap_meta.tags]
        if "read" in tags_lower or "search" in tags_lower:
            return CapabilityType.READ
        elif "write" in tags_lower or "edit" in tags_lower:
            return CapabilityType.WRITE
        elif "execute" in tags_lower or "bash" in tags_lower:
            return CapabilityType.EXECUTE
        elif "browser" in tags_lower:
            return CapabilityType.BROWSER
        elif "model" in tags_lower or "ai" in tags_lower:
            return CapabilityType.MODEL
        elif "git" in tags_lower:
            return CapabilityType.GIT
        elif "web" in tags_lower or "reach" in tags_lower:
            return CapabilityType.REACH
        return CapabilityType.EXECUTE

    def get_discovery_registry(self) -> CapabilityDiscoveryRegistry:
        """Get the discovery registry."""
        return self._discovery_registry


class _DiscoveredCapability(Capability):
    """A capability discovered from an external source."""

    def __init__(self, metadata: CapabilityMetadata, discovery_meta: DiscoveryCapabilityMetadata):
        super().__init__(metadata)
        self._discovery_meta = discovery_meta

    def check_availability(self) -> bool:
        return True

    def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "source": self._discovery_meta.source}

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "error": f"Discovered capability {self.get_name()} is a placeholder - not yet implemented",
            "output": None,
        }