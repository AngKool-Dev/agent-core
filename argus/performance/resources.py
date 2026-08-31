"""Resource control and limits for concurrent execution."""

import threading
from typing import Dict, Optional

from argus.performance.models import (
    PerformanceBudget,
    ResourceBudget,
    ResourceMeasurement,
    ResourceType,
)


class ResourceError(Exception):
    """Error when resource limits are exceeded."""
    pass


class ResourceController:
    """Controls and tracks resource usage."""

    def __init__(self, budget: Optional[PerformanceBudget] = None):
        self._budget = budget or PerformanceBudget()
        self._usage = ResourceBudget(limits=self._budget)
        self._lock = threading.Lock()

    @property
    def budget(self) -> PerformanceBudget:
        """Get the performance budget."""
        return self._budget

    @property
    def usage(self) -> ResourceBudget:
        """Get current resource usage."""
        return self._usage

    def check_available(self, resource_type: ResourceType) -> bool:
        """Check if a resource is available."""
        with self._lock:
            return not self._is_exhausted_unsafe(resource_type)

    def acquire(self, resource_type: ResourceType, amount: int = 1) -> bool:
        """Attempt to acquire a resource."""
        with self._lock:
            if self._is_exhausted_unsafe(resource_type):
                return False
            self._increment_unsafe(resource_type, amount)
            return True

    def release(self, resource_type: ResourceType, amount: int = 1) -> None:
        """Release a resource."""
        with self._lock:
            self._decrement_unsafe(resource_type, amount)

    def measure(self, resource_type: ResourceType) -> ResourceMeasurement:
        """Get current measurement for a resource."""
        with self._lock:
            current = self._get_usage_unsafe(resource_type)
            max_val = self._get_limit_unsafe(resource_type)
        return ResourceMeasurement(
            resource_type=resource_type,
            current_usage=current,
            max_usage=max_val,
        )

    def _is_exhausted_unsafe(self, resource_type: ResourceType) -> bool:
        """Check if resource is exhausted (must hold lock)."""
        current = self._get_usage_unsafe(resource_type)
        limit = self._get_limit_unsafe(resource_type)
        return current >= limit

    def _increment_unsafe(self, resource_type: ResourceType, amount: int) -> None:
        """Increment resource usage (must hold lock)."""
        if resource_type == ResourceType.CONCURRENT_RUNS:
            self._usage.current_concurrent_runs += amount
        elif resource_type == ResourceType.CONCURRENT_CAPABILITIES:
            self._usage.current_concurrent_capabilities += amount
        elif resource_type == ResourceType.CONCURRENT_PROVIDER_CALLS:
            self._usage.current_concurrent_provider_calls += amount
        elif resource_type == ResourceType.TOOL_CALLS:
            self._usage.current_tool_calls += amount
        elif resource_type == ResourceType.QUEUED_OPERATIONS:
            self._usage.current_queued_operations += amount
        elif resource_type == ResourceType.TOKENS:
            self._usage.current_tokens += amount
        elif resource_type == ResourceType.RECOVERY_ATTEMPTS:
            self._usage.current_recovery_attempts += amount
        elif resource_type == ResourceType.MCP_CALLS:
            self._usage.current_mcp_calls += amount

    def _decrement_unsafe(self, resource_type: ResourceType, amount: int) -> None:
        """Decrement resource usage (must hold lock)."""
        if resource_type == ResourceType.CONCURRENT_RUNS:
            self._usage.current_concurrent_runs = max(0, self._usage.current_concurrent_runs - amount)
        elif resource_type == ResourceType.CONCURRENT_CAPABILITIES:
            self._usage.current_concurrent_capabilities = max(0, self._usage.current_concurrent_capabilities - amount)
        elif resource_type == ResourceType.CONCURRENT_PROVIDER_CALLS:
            self._usage.current_concurrent_provider_calls = max(0, self._usage.current_concurrent_provider_calls - amount)
        elif resource_type == ResourceType.TOOL_CALLS:
            self._usage.current_tool_calls = max(0, self._usage.current_tool_calls - amount)
        elif resource_type == ResourceType.QUEUED_OPERATIONS:
            self._usage.current_queued_operations = max(0, self._usage.current_queued_operations - amount)
        elif resource_type == ResourceType.TOKENS:
            self._usage.current_tokens = max(0, self._usage.current_tokens - amount)
        elif resource_type == ResourceType.RECOVERY_ATTEMPTS:
            self._usage.current_recovery_attempts = max(0, self._usage.current_recovery_attempts - amount)
        elif resource_type == ResourceType.MCP_CALLS:
            self._usage.current_mcp_calls = max(0, self._usage.current_mcp_calls - amount)

    def _get_usage_unsafe(self, resource_type: ResourceType) -> int:
        """Get current usage (must hold lock)."""
        usage_map = {
            ResourceType.CONCURRENT_RUNS: self._usage.current_concurrent_runs,
            ResourceType.CONCURRENT_CAPABILITIES: self._usage.current_concurrent_capabilities,
            ResourceType.CONCURRENT_PROVIDER_CALLS: self._usage.current_concurrent_provider_calls,
            ResourceType.TOOL_CALLS: self._usage.current_tool_calls,
            ResourceType.QUEUED_OPERATIONS: self._usage.current_queued_operations,
            ResourceType.TOKENS: self._usage.current_tokens,
            ResourceType.RECOVERY_ATTEMPTS: self._usage.current_recovery_attempts,
            ResourceType.MCP_CALLS: self._usage.current_mcp_calls,
        }
        return usage_map.get(resource_type, 0)

    def _get_limit_unsafe(self, resource_type: ResourceType) -> int:
        """Get limit for a resource (must hold lock)."""
        limit_map = {
            ResourceType.CONCURRENT_RUNS: self._budget.max_concurrent_runs,
            ResourceType.CONCURRENT_CAPABILITIES: self._budget.max_concurrent_capabilities,
            ResourceType.CONCURRENT_PROVIDER_CALLS: self._budget.max_concurrent_provider_calls,
            ResourceType.TOOL_CALLS: self._budget.max_tool_calls,
            ResourceType.QUEUED_OPERATIONS: self._budget.max_queued_operations,
            ResourceType.TOKENS: self._budget.max_tokens,
            ResourceType.RECOVERY_ATTEMPTS: self._budget.max_recovery_attempts,
            ResourceType.MCP_CALLS: self._budget.max_mcp_calls,
        }
        return limit_map.get(resource_type, 0)
