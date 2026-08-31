"""ARGUS canonical event and observability subsystem."""

from argus.events.bus import EventBus, get_event_bus, reset_event_bus
from argus.events.correlation import CorrelationTracker, get_correlation_tracker, reset_correlation_tracker
from argus.events.event import AgentEvent, create_event
from argus.events.emitter import EventTimedContext, EventEmitter
from argus.events.filters import (
    AndFilter,
    CapabilityFilter,
    CustomFilter,
    EventFilter,
    EventSourceFilter,
    EventStatusFilter,
    EventTypeFilter,
    FailureFilter,
    MCPFilter,
    NotFilter,
    OrFilter,
    PassthroughFilter,
    RecoveryFilter,
    RunFilter,
    SecurityFilter,
    SessionFilter,
    SuccessFilter,
    TimeRangeFilter,
)
from argus.events.sinks import (
    AuditTrailSink,
    CallbackSink,
    ConsoleSink,
    EventSink,
    JsonSink,
    MemorySink,
    MultiSink,
)
from argus.events.subscribers import (
    AlertSubscriber,
    CallbackSubscriber,
    CollectingSubscriber,
    CountingSubscriber,
    EventSubscriber,
    LoggingSubscriber,
)
from argus.events.types import (
    EventCategory,
    EventSource,
    EventStatus,
    EventType,
    get_category,
)

__all__ = [
    # Bus
    "EventBus",
    "get_event_bus",
    "reset_event_bus",
    # Correlation
    "CorrelationTracker",
    "get_correlation_tracker",
    "reset_correlation_tracker",
    # Event
    "AgentEvent",
    "create_event",
    # Emitter
    "EventEmitter",
    "EventTimedContext",
    # Filters
    "EventFilter",
    "PassthroughFilter",
    "EventTypeFilter",
    "EventSourceFilter",
    "EventStatusFilter",
    "CapabilityFilter",
    "RunFilter",
    "SessionFilter",
    "TimeRangeFilter",
    "SuccessFilter",
    "FailureFilter",
    "SecurityFilter",
    "RecoveryFilter",
    "MCPFilter",
    "AndFilter",
    "OrFilter",
    "NotFilter",
    "CustomFilter",
    # Sinks
    "EventSink",
    "ConsoleSink",
    "MemorySink",
    "JsonSink",
    "AuditTrailSink",
    "CallbackSink",
    "MultiSink",
    # Subscribers
    "EventSubscriber",
    "CallbackSubscriber",
    "LoggingSubscriber",
    "CountingSubscriber",
    "CollectingSubscriber",
    "AlertSubscriber",
    # Types
    "EventCategory",
    "EventType",
    "EventSource",
    "EventStatus",
    "get_category",
]
