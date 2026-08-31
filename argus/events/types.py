"""ARGUS event taxonomy and types."""

from enum import Enum
from typing import Any, Dict, Optional


class EventCategory(str, Enum):
    """Top-level event categories."""
    AGENT = "agent"
    TASK = "task"
    CONTEXT = "context"
    MODEL = "model"
    CAPABILITY = "capability"
    SECURITY = "security"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    RECOVERY = "recovery"
    MCP = "mcp"
    SYSTEM = "system"


class EventType(str, Enum):
    """Canonical event types for ARGUS."""

    # Agent lifecycle
    AGENT_STARTED = "agent.started"
    AGENT_PAUSED = "agent.paused"
    AGENT_RESUMED = "agent.resumed"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_ESCALATED = "agent.escalated"

    # Task / Planning
    TASK_RECEIVED = "task.received"
    PLAN_CREATED = "plan.created"
    PLAN_REVISED = "plan.revised"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"

    # Context
    CONTEXT_REQUESTED = "context.requested"
    CONTEXT_BUILT = "context.built"
    MEMORY_RETRIEVED = "memory.retrieved"
    REPOSITORY_MAPPED = "repository.mapped"

    # Model
    MODEL_REQUESTED = "model.requested"
    MODEL_COMPLETED = "model.completed"
    MODEL_FAILED = "model.failed"
    MODEL_FALLBACK = "model.fallback"

    # Capabilities
    CAPABILITY_REQUESTED = "capability.requested"
    CAPABILITY_SELECTED = "capability.selected"
    CAPABILITY_STARTED = "capability.started"
    CAPABILITY_COMPLETED = "capability.completed"
    CAPABILITY_FAILED = "capability.failed"

    # Security
    SECURITY_ALLOWED = "security.allowed"
    SECURITY_DENIED = "security.denied"
    SECURITY_APPROVAL_REQUESTED = "security.approval_requested"
    SECURITY_APPROVED = "security.approved"
    SECURITY_REJECTED = "security.rejected"
    SECURITY_INJECTION_DETECTED = "security.injection_detected"

    # Execution
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"

    # Verification
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_CRITERION_COMPLETED = "verification.criterion_completed"
    VERIFICATION_COMPLETED = "verification.completed"
    VERIFICATION_FAILED = "verification.failed"

    # Recovery
    RECOVERY_STARTED = "recovery.started"
    RECOVERY_CLASSIFIED = "recovery.classified"
    RECOVERY_STRATEGY_SELECTED = "recovery.strategy_selected"
    RECOVERY_COMPLETED = "recovery.completed"
    RECOVERY_EXHAUSTED = "recovery.exhausted"

    # MCP
    MCP_CONNECTED = "mcp.connected"
    MCP_DISCONNECTED = "mcp.disconnected"
    MCP_TOOL_REQUESTED = "mcp.tool_requested"
    MCP_TOOL_COMPLETED = "mcp.tool_completed"
    MCP_TOOL_FAILED = "mcp.tool_failed"
    MCP_HEALTH_CHANGED = "mcp.health_changed"

    # System
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"


class EventStatus(str, Enum):
    """Event status values."""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DENIED = "denied"
    ALLOWED = "allowed"
    REQUESTED = "requested"
    GRANTED = "granted"
    REJECTED = "rejected"
    DETECTED = "detected"
    CLASSIFIED = "classified"
    SELECTED = "selected"
    EXHAUSTED = "exhausted"


class EventSource(str, Enum):
    """Event sources."""
    AGENT = "agent"
    CONTEXT_ENGINE = "context_engine"
    MODEL_ROUTER = "model_router"
    CAPABILITY_ROUTER = "capability_router"
    SECURITY_KERNEL = "security_kernel"
    EXECUTION_ENGINE = "execution_engine"
    VERIFICATION_ENGINE = "verification_engine"
    RECOVERY_ENGINE = "recovery_engine"
    MCP_CLIENT = "mcp_client"
    MCP_SERVER = "mcp_server"
    STATE_MANAGER = "state_manager"
    MEMORY_MANAGER = "memory_manager"
    SYSTEM = "system"


# Mapping of event types to categories
EVENT_CATEGORY_MAP: Dict[EventType, str] = {
    # Agent
    EventType.AGENT_STARTED: EventCategory.AGENT,
    EventType.AGENT_PAUSED: EventCategory.AGENT,
    EventType.AGENT_RESUMED: EventCategory.AGENT,
    EventType.AGENT_COMPLETED: EventCategory.AGENT,
    EventType.AGENT_FAILED: EventCategory.AGENT,
    EventType.AGENT_ESCALATED: EventCategory.AGENT,

    # Task
    EventType.TASK_RECEIVED: EventCategory.TASK,
    EventType.PLAN_CREATED: EventCategory.TASK,
    EventType.PLAN_REVISED: EventCategory.TASK,
    EventType.STEP_STARTED: EventCategory.TASK,
    EventType.STEP_COMPLETED: EventCategory.TASK,

    # Context
    EventType.CONTEXT_REQUESTED: EventCategory.CONTEXT,
    EventType.CONTEXT_BUILT: EventCategory.CONTEXT,
    EventType.MEMORY_RETRIEVED: EventCategory.CONTEXT,
    EventType.REPOSITORY_MAPPED: EventCategory.CONTEXT,

    # Model
    EventType.MODEL_REQUESTED: EventCategory.MODEL,
    EventType.MODEL_COMPLETED: EventCategory.MODEL,
    EventType.MODEL_FAILED: EventCategory.MODEL,
    EventType.MODEL_FALLBACK: EventCategory.MODEL,

    # Capability
    EventType.CAPABILITY_REQUESTED: EventCategory.CAPABILITY,
    EventType.CAPABILITY_SELECTED: EventCategory.CAPABILITY,
    EventType.CAPABILITY_STARTED: EventCategory.CAPABILITY,
    EventType.CAPABILITY_COMPLETED: EventCategory.CAPABILITY,
    EventType.CAPABILITY_FAILED: EventCategory.CAPABILITY,

    # Security
    EventType.SECURITY_ALLOWED: EventCategory.SECURITY,
    EventType.SECURITY_DENIED: EventCategory.SECURITY,
    EventType.SECURITY_APPROVAL_REQUESTED: EventCategory.SECURITY,
    EventType.SECURITY_APPROVED: EventCategory.SECURITY,
    EventType.SECURITY_REJECTED: EventCategory.SECURITY,
    EventType.SECURITY_INJECTION_DETECTED: EventCategory.SECURITY,

    # Verification
    EventType.VERIFICATION_STARTED: EventCategory.VERIFICATION,
    EventType.VERIFICATION_CRITERION_COMPLETED: EventCategory.VERIFICATION,
    EventType.VERIFICATION_COMPLETED: EventCategory.VERIFICATION,
    EventType.VERIFICATION_FAILED: EventCategory.VERIFICATION,

    # Recovery
    EventType.RECOVERY_STARTED: EventCategory.RECOVERY,
    EventType.RECOVERY_CLASSIFIED: EventCategory.RECOVERY,
    EventType.RECOVERY_STRATEGY_SELECTED: EventCategory.RECOVERY,
    EventType.RECOVERY_COMPLETED: EventCategory.RECOVERY,
    EventType.RECOVERY_EXHAUSTED: EventCategory.RECOVERY,

    # MCP
    EventType.MCP_CONNECTED: EventCategory.MCP,
    EventType.MCP_DISCONNECTED: EventCategory.MCP,
    EventType.MCP_TOOL_REQUESTED: EventCategory.MCP,
    EventType.MCP_TOOL_COMPLETED: EventCategory.MCP,
    EventType.MCP_TOOL_FAILED: EventCategory.MCP,
    EventType.MCP_HEALTH_CHANGED: EventCategory.MCP,

    # System
    EventType.SYSTEM_ERROR: EventCategory.SYSTEM,
    EventType.SYSTEM_WARNING: EventCategory.SYSTEM,
}


def get_category(event_type: EventType) -> str:
    """Get the category for an event type."""
    return EVENT_CATEGORY_MAP.get(event_type, EventCategory.SYSTEM)
