"""
Hermes Desktop → Argus EventBus observation bridge.

This module provides a thin, failure-isolated adapter that translates
Hermes lifecycle events into Argus (AgentCore) EventBus events.

Architecture
------------
    Hermes AIAgent / TUI Gateway
        |
        |  event_callback, tool_start_callback, tool_complete_callback,
        |  hermes_cli.lifecycle.invoke_hook
        v
    HermesEventBridge.emit(event_name, session_id, task_id, metadata)
        |
        |  translates to Argus EventType
        v
    Argus EventBus

Design goals
------------
* Tiny import surface — Hermes does not need to import the full AgentCore.
* Failure-isolated — any exception in the bridge is caught and logged;
  Hermes execution continues normally.
* Best-effort — if the EventBus is unavailable, events are silently dropped.
* No control — this is observation only.  Argus cannot (yet) command Hermes.
"""

from __future__ import annotations

import logging
from typing import Any

from agentcore.events import AgentEvent, EventBus, EventType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event name mapping: Hermes event name → Argus EventType
# ---------------------------------------------------------------------------

_EVENT_MAP: dict[str, EventType] = {
    # Hermes lifecycle hooks (hermes_cli.lifecycle)
    "on_session_start": EventType.TASK_REGISTERED,
    "on_session_end": EventType.TASK_COMPLETED,
    "on_session_finalize": EventType.TASK_STATE_CHANGED,
    "on_session_reset": EventType.TASK_STATE_CHANGED,
    "pre_llm_call": EventType.MODEL_REQUEST_STARTED,
    "pre_api_request": EventType.MODEL_REQUEST_STARTED,
    "pre_tool_call": EventType.TOOL_CALL_STARTED,
    "post_tool_call": EventType.TOOL_CALL_COMPLETED,
    "post_approval_response": EventType.TOOL_CALL_COMPLETED,
    "post_api_request": EventType.MODEL_RESPONSE_RECEIVED,
    "api_request_error": EventType.MODEL_ERROR,
    "on_skill_lifecycle": EventType.SKILL_LOADED,
    "subagent_stop": EventType.TASK_COMPLETED,
    # Hermes tool progress callbacks (codex_runtime._fire_tool_started/completed)
    "tool.started": EventType.TOOL_CALL_STARTED,
    "tool.completed": EventType.TOOL_CALL_COMPLETED,
    # Hermes event_callback custom events
    "session:compress": EventType.TASK_STATE_CHANGED,
    "execution:start": EventType.TASK_STARTED,
    "execution:complete": EventType.TASK_COMPLETED,
    "execution:failed": EventType.TASK_FAILED,
    "execution:cancelled": EventType.TASK_CANCELLED,
    # Gateway events
    "session.info": EventType.TASK_STATE_CHANGED,
    "error": EventType.RUNTIME_ERROR,
    "review.summary": EventType.OBSERVATION_CREATED,
    "notification.show": EventType.OBSERVATION_CREATED,
    "notification.clear": EventType.OBSERVATION_CREATED,
    "clarify.request": EventType.OBSERVATION_CREATED,
    "terminal.read.request": EventType.OBSERVATION_CREATED,
    "preview.read.request": EventType.OBSERVATION_CREATED,
    "window.read.request": EventType.OBSERVATION_CREATED,
    "mcp.setup.request": EventType.OBSERVATION_CREATED,
    "thinking.delta": EventType.OBSERVATION_CREATED,
    "reasoning.delta": EventType.OBSERVATION_CREATED,
    "reaction": EventType.OBSERVATION_CREATED,
    "message.interim": EventType.OBSERVATION_CREATED,
    "tool.generating": EventType.TOOL_CALL_STARTED,
}


class HermesEventBridge:
    """Failure-isolated bridge from Hermes lifecycle events to Argus EventBus.

    Usage from Hermes (minimal import)::

        from agentcore.adapters.hermes_event_bridge import HermesEventBridge
        from agentcore.events import EventBus

        bus = EventBus()
        bridge = HermesEventBridge(event_bus=bus)

        # As AIAgent event_callback:
        agent.event_callback = bridge.emit

        # Or from lifecycle hooks:
        from hermes_cli.lifecycle import invoke_hook
        # wrap invoke_hook to also call bridge.emit(...)
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus
        self._enabled = True

    def emit(
        self,
        event_name: str,
        session_id: str,
        task_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Translate a Hermes event into an Argus EventBus event.

        Args:
            event_name: Hermes event name (e.g. ``"on_session_start"``).
            session_id: Hermes session identifier.
            task_id: Optional task identifier.  Falls back to ``session_id``.
            metadata: Optional additional event data.
        """
        if not self._enabled:
            return
        try:
            event_type = _EVENT_MAP.get(event_name)
            if event_type is None:
                return
            if self._event_bus is None or self._event_bus.subscriber_count == 0:
                return
            event = AgentEvent(
                event_type=event_type,
                task_id=task_id or session_id,
                data=metadata or {},
                metadata={"session_id": session_id, "task_id": task_id or session_id},
            )
            self._event_bus.emit(event)
        except Exception:
            logger.warning(
                "HermesEventBridge dropped event %s for session %s",
                event_name,
                session_id,
                exc_info=True,
            )

    def enable(self) -> None:
        """Re-enable the bridge after a previous disable."""
        self._enabled = True

    def disable(self) -> None:
        """Disable the bridge without tearing down the EventBus binding."""
        self._enabled = False

    @property
    def event_bus(self) -> EventBus | None:
        """The bound Argus EventBus (may be None)."""
        return self._event_bus

    @event_bus.setter
    def event_bus(self, value: EventBus | None) -> None:
        self._event_bus = value
