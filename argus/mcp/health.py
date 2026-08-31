"""MCP health monitoring for ARGUS."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISCONNECTED = "disconnected"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    server_id: str
    status: HealthStatus
    response_time: float = 0.0
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server_id": self.server_id,
            "status": self.status.value,
            "response_time": self.response_time,
            "message": self.message,
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class ServerHealth:
    """Health state for an MCP server."""
    server_id: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_check: float = 0.0
    last_healthy: float = 0.0
    consecutive_failures: int = 0
    total_checks: int = 0
    total_failures: int = 0
    average_response_time: float = 0.0
    response_times: List[float] = field(default_factory=list)
    last_error: str = ""

    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    @property
    def uptime_percentage(self) -> float:
        if self.total_checks == 0:
            return 0.0
        return ((self.total_checks - self.total_failures) / self.total_checks) * 100

    def record_check(self, result: HealthCheckResult) -> None:
        """Record a health check result."""
        self.last_check = result.timestamp
        self.total_checks += 1
        self.response_times.append(result.response_time)

        if len(self.response_times) > 100:
            self.response_times = self.response_times[-100:]

        self.average_response_time = sum(self.response_times) / len(self.response_times)

        if result.status == HealthStatus.HEALTHY:
            self.status = HealthStatus.HEALTHY
            self.last_healthy = result.timestamp
            self.consecutive_failures = 0
            self.last_error = ""
        else:
            self.status = result.status
            self.consecutive_failures += 1
            self.total_failures += 1
            self.last_error = result.message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server_id": self.server_id,
            "status": self.status.value,
            "last_check": self.last_check,
            "last_healthy": self.last_healthy,
            "consecutive_failures": self.consecutive_failures,
            "total_checks": self.total_checks,
            "total_failures": self.total_failures,
            "average_response_time": self.average_response_time,
            "uptime_percentage": self.uptime_percentage,
            "last_error": self.last_error,
        }


class MCPHealthMonitor:
    """Monitors health of MCP servers."""

    def __init__(self):
        self._health_states: Dict[str, ServerHealth] = {}
        self._max_response_time_ms: float = 5000.0
        self._degraded_threshold: float = 3
        self._unhealthy_threshold: float = 5

    def register_server(self, server_id: str) -> ServerHealth:
        """Register a server for health monitoring."""
        if server_id not in self._health_states:
            self._health_states[server_id] = ServerHealth(server_id=server_id)
        return self._health_states[server_id]

    def unregister_server(self, server_id: str) -> bool:
        """Unregister a server from health monitoring."""
        if server_id in self._health_states:
            del self._health_states[server_id]
            return True
        return False

    def get_health(self, server_id: str) -> Optional[ServerHealth]:
        """Get health state for a server."""
        return self._health_states.get(server_id)

    def get_all_health(self) -> Dict[str, ServerHealth]:
        """Get health states for all servers."""
        return dict(self._health_states)

    def record_check(self, result: HealthCheckResult) -> None:
        """Record a health check result."""
        if result.server_id not in self._health_states:
            self.register_server(result.server_id)

        self._health_states[result.server_id].record_check(result)

    def check_health(
        self,
        server_id: str,
        is_connected: bool = False,
        response_time: float = 0.0,
        tool_count: int = 0,
        error: str = "",
    ) -> HealthCheckResult:
        """Perform a health check on a server."""
        if not is_connected:
            result = HealthCheckResult(
                server_id=server_id,
                status=HealthStatus.DISCONNECTED,
                response_time=response_time,
                message="Server not connected",
            )
            self.record_check(result)
            return result

        if error:
            result = HealthCheckResult(
                server_id=server_id,
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                message=error,
            )
            self.record_check(result)
            return result

        if response_time > self._max_response_time_ms:
            result = HealthCheckResult(
                server_id=server_id,
                status=HealthStatus.DEGRADED,
                response_time=response_time,
                message=f"Response time {response_time:.0f}ms exceeds threshold",
            )
            self.record_check(result)
            return result

        result = HealthCheckResult(
            server_id=server_id,
            status=HealthStatus.HEALTHY,
            response_time=response_time,
            message="OK",
            details={"tool_count": tool_count},
        )
        self.record_check(result)
        return result

    def get_healthy_servers(self) -> List[str]:
        """Get list of healthy server IDs."""
        return [
            sid for sid, health in self._health_states.items()
            if health.is_healthy
        ]

    def get_unhealthy_servers(self) -> List[str]:
        """Get list of unhealthy server IDs."""
        return [
            sid for sid, health in self._health_states.items()
            if not health.is_healthy and health.status != HealthStatus.UNKNOWN
        ]

    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of all server health."""
        status_counts: Dict[str, int] = {}
        for health in self._health_states.values():
            status = health.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_servers": len(self._health_states),
            "healthy_servers": len(self.get_healthy_servers()),
            "unhealthy_servers": len(self.get_unhealthy_servers()),
            "status_counts": status_counts,
        }

    def clear(self) -> None:
        """Clear all health states."""
        self._health_states.clear()
