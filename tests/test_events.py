"""Tests for ARGUS canonical event and observability subsystem."""

import time
from unittest.mock import MagicMock, patch

import pytest

from argus.events import (
    AgentEvent,
    AlertSubscriber,
    AndFilter,
    AuditTrailSink,
    CallbackSink,
    CallbackSubscriber,
    CapabilityFilter,
    CollectingSubscriber,
    ConsoleSink,
    CountingSubscriber,
    CorrelationTracker,
    CustomFilter,
    EventBus,
    EventEmitter,
    EventCategory,
    EventFilter,
    EventSink,
    EventSource,
    EventSourceFilter,
    EventStatus,
    EventStatusFilter,
    EventType,
    EventTypeFilter,
    EventTimedContext,
    FailureFilter,
    JsonSink,
    LoggingSubscriber,
    MCPFilter,
    MemorySink,
    MultiSink,
    NotFilter,
    OrFilter,
    PassthroughFilter,
    RecoveryFilter,
    RunFilter,
    SecurityFilter,
    SessionFilter,
    SuccessFilter,
    TimeRangeFilter,
    create_event,
    get_category,
    get_correlation_tracker,
    get_event_bus,
    reset_correlation_tracker,
    reset_event_bus,
)


class TestEventTypes:
    """Tests for event type enums."""

    def test_event_category_values(self):
        assert EventCategory.AGENT == "agent"
        assert EventCategory.TASK == "task"
        assert EventCategory.CONTEXT == "context"
        assert EventCategory.MODEL == "model"
        assert EventCategory.CAPABILITY == "capability"
        assert EventCategory.SECURITY == "security"
        assert EventCategory.EXECUTION == "execution"
        assert EventCategory.VERIFICATION == "verification"
        assert EventCategory.RECOVERY == "recovery"
        assert EventCategory.MCP == "mcp"
        assert EventCategory.SYSTEM == "system"

    def test_event_type_values(self):
        assert EventType.AGENT_STARTED == "agent.started"
        assert EventType.AGENT_COMPLETED == "agent.completed"
        assert EventType.TASK_RECEIVED == "task.received"
        assert EventType.PLAN_CREATED == "plan.created"
        assert EventType.MODEL_REQUESTED == "model.requested"
        assert EventType.CAPABILITY_STARTED == "capability.started"
        assert EventType.SECURITY_DENIED == "security.denied"
        assert EventType.EXECUTION_STARTED == "execution.started"
        assert EventType.VERIFICATION_COMPLETED == "verification.completed"
        assert EventType.RECOVERY_STARTED == "recovery.started"
        assert EventType.MCP_CONNECTED == "mcp.connected"
        assert EventType.SYSTEM_ERROR == "system.error"

    def test_event_status_values(self):
        assert EventStatus.STARTED == "started"
        assert EventStatus.IN_PROGRESS == "in_progress"
        assert EventStatus.COMPLETED == "completed"
        assert EventStatus.FAILED == "failed"
        assert EventStatus.DENIED == "denied"
        assert EventStatus.ALLOWED == "allowed"
        assert EventStatus.EXHAUSTED == "exhausted"

    def test_event_source_values(self):
        assert EventSource.AGENT == "agent"
        assert EventSource.CONTEXT_ENGINE == "context_engine"
        assert EventSource.MODEL_ROUTER == "model_router"
        assert EventSource.CAPABILITY_ROUTER == "capability_router"
        assert EventSource.SECURITY_KERNEL == "security_kernel"
        assert EventSource.EXECUTION_ENGINE == "execution_engine"
        assert EventSource.VERIFICATION_ENGINE == "verification_engine"
        assert EventSource.RECOVERY_ENGINE == "recovery_engine"
        assert EventSource.MCP_CLIENT == "mcp_client"
        assert EventSource.STATE_MANAGER == "state_manager"
        assert EventSource.SYSTEM == "system"


class TestGetCategory:
    """Tests for category mapping."""

    def test_agent_category(self):
        assert get_category(EventType.AGENT_STARTED) == EventCategory.AGENT
        assert get_category(EventType.AGENT_COMPLETED) == EventCategory.AGENT

    def test_task_category(self):
        assert get_category(EventType.TASK_RECEIVED) == EventCategory.TASK
        assert get_category(EventType.PLAN_CREATED) == EventCategory.TASK

    def test_model_category(self):
        assert get_category(EventType.MODEL_REQUESTED) == EventCategory.MODEL
        assert get_category(EventType.MODEL_COMPLETED) == EventCategory.MODEL

    def test_capability_category(self):
        assert get_category(EventType.CAPABILITY_STARTED) == EventCategory.CAPABILITY
        assert get_category(EventType.CAPABILITY_COMPLETED) == EventCategory.CAPABILITY

    def test_security_category(self):
        assert get_category(EventType.SECURITY_DENIED) == EventCategory.SECURITY
        assert get_category(EventType.SECURITY_APPROVED) == EventCategory.SECURITY

    def test_mcp_category(self):
        assert get_category(EventType.MCP_CONNECTED) == EventCategory.MCP
        assert get_category(EventType.MCP_TOOL_COMPLETED) == EventCategory.MCP

    def test_system_category_for_unknown(self):
        # All defined types should have a category
        for event_type in EventType:
            category = get_category(event_type)
            assert category is not None
            assert isinstance(category, str)


class TestAgentEvent:
    """Tests for AgentEvent dataclass."""

    def test_create_basic_event(self):
        event = AgentEvent(
            event_type=EventType.AGENT_STARTED,
            source=EventSource.AGENT,
        )
        assert event.event_type == EventType.AGENT_STARTED
        assert event.source == EventSource.AGENT
        assert event.status == EventStatus.COMPLETED
        assert event.event_id is not None
        assert len(event.event_id) == 12

    def test_event_with_run_id(self):
        event = AgentEvent(
            event_type=EventType.TASK_RECEIVED,
            source=EventSource.AGENT,
            run_id="run-123",
        )
        assert event.run_id == "run-123"

    def test_event_with_session_id(self):
        event = AgentEvent(
            event_type=EventType.TASK_RECEIVED,
            source=EventSource.AGENT,
            session_id="session-456",
        )
        assert event.session_id == "session-456"

    def test_event_with_metadata(self):
        event = AgentEvent(
            event_type=EventType.CAPABILITY_STARTED,
            source=EventSource.CAPABILITY_ROUTER,
            capability="web_search",
            metadata={"query": "test"},
        )
        assert event.capability == "web_search"
        assert event.metadata["query"] == "test"

    def test_event_with_duration(self):
        event = AgentEvent(
            event_type=EventType.CAPABILITY_COMPLETED,
            source=EventSource.CAPABILITY_ROUTER,
            duration=1.5,
        )
        assert event.duration == 1.5

    def test_event_category_property(self):
        event = AgentEvent(
            event_type=EventType.AGENT_STARTED,
            source=EventSource.AGENT,
        )
        assert event.category == EventCategory.AGENT

    def test_event_is_success(self):
        event = AgentEvent(
            event_type=EventType.AGENT_COMPLETED,
            source=EventSource.AGENT,
            status=EventStatus.COMPLETED,
        )
        assert event.is_success is True
        assert event.is_failure is False

    def test_event_is_failure(self):
        event = AgentEvent(
            event_type=EventType.AGENT_FAILED,
            source=EventSource.AGENT,
            status=EventStatus.FAILED,
        )
        assert event.is_success is False
        assert event.is_failure is True

    def test_event_to_dict(self):
        event = AgentEvent(
            event_type=EventType.TASK_RECEIVED,
            source=EventSource.AGENT,
            run_id="run-123",
        )
        data = event.to_dict()
        assert data["event_type"] == "task.received"
        assert data["source"] == "agent"
        assert data["run_id"] == "run-123"
        assert "event_id" in data
        assert "timestamp" in data

    def test_event_to_json(self):
        event = AgentEvent(
            event_type=EventType.TASK_RECEIVED,
            source=EventSource.AGENT,
        )
        json_str = event.to_json()
        assert "task.received" in json_str
        assert "agent" in json_str

    def test_event_fingerprint(self):
        event = AgentEvent(
            event_type=EventType.TASK_RECEIVED,
            source=EventSource.AGENT,
            run_id="run-123",
        )
        fp = event.fingerprint()
        assert len(fp) == 16

    def test_event_with_parent(self):
        parent = AgentEvent(
            event_type=EventType.TASK_RECEIVED,
            source=EventSource.AGENT,
            run_id="run-123",
            session_id="session-456",
        )
        child = AgentEvent(
            event_type=EventType.CAPABILITY_STARTED,
            source=EventSource.CAPABILITY_ROUTER,
        ).with_parent(parent)
        assert child.parent_event_id == parent.event_id
        assert child.run_id == "run-123"
        assert child.session_id == "session-456"

    def test_event_with_status(self):
        event = AgentEvent(
            event_type=EventType.CAPABILITY_STARTED,
            source=EventSource.CAPABILITY_ROUTER,
            status=EventStatus.STARTED,
        )
        completed = event.with_status(EventStatus.COMPLETED)
        assert completed.status == EventStatus.COMPLETED
        assert event.status == EventStatus.STARTED  # Original unchanged

    def test_event_with_duration(self):
        event = AgentEvent(
            event_type=EventType.CAPABILITY_STARTED,
            source=EventSource.CAPABILITY_ROUTER,
        )
        with_duration = event.with_duration(2.5)
        assert with_duration.duration == 2.5
        assert event.duration is None  # Original unchanged

    def test_event_immutability(self):
        event = AgentEvent(
            event_type=EventType.TASK_RECEIVED,
            source=EventSource.AGENT,
        )
        with pytest.raises(AttributeError):
            event.run_id = "new-run-id"


class TestCreateEvent:
    """Tests for create_event factory function."""

    def test_create_basic_event(self):
        event = create_event(
            event_type=EventType.AGENT_STARTED,
            source=EventSource.AGENT,
        )
        assert event.event_type == EventType.AGENT_STARTED
        assert event.source == EventSource.AGENT

    def test_create_event_with_parent(self):
        parent = create_event(
            event_type=EventType.TASK_RECEIVED,
            source=EventSource.AGENT,
            run_id="run-123",
            session_id="session-456",
        )
        child = create_event(
            event_type=EventType.CAPABILITY_STARTED,
            source=EventSource.CAPABILITY_ROUTER,
            parent=parent,
        )
        assert child.parent_event_id == parent.event_id
        assert child.run_id == "run-123"
        assert child.session_id == "session-456"

    def test_create_event_with_all_params(self):
        event = create_event(
            event_type=EventType.MODEL_REQUESTED,
            source=EventSource.MODEL_ROUTER,
            status=EventStatus.STARTED,
            run_id="run-789",
            session_id="session-012",
            operation_id="op-345",
            attempt_id="attempt-678",
            capability_call_id="cap-901",
            capability="gpt-4",
            metadata={"tokens": 100},
            payload={"prompt": "Hello"},
        )
        assert event.run_id == "run-789"
        assert event.session_id == "session-012"
        assert event.operation_id == "op-345"
        assert event.attempt_id == "attempt-678"
        assert event.capability_call_id == "cap-901"
        assert event.capability == "gpt-4"
        assert event.metadata == {"tokens": 100}
        assert event.payload == {"prompt": "Hello"}


class TestEventBus:
    """Tests for EventBus."""

    def test_create_bus(self):
        bus = EventBus()
        assert bus.is_active is True
        assert bus.subscriber_count == 0
        assert bus.event_count == 0
        assert bus.error_count == 0

    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe(lambda e: received.append(e))
        event = create_event(EventType.AGENT_STARTED, EventSource.AGENT)
        count = bus.publish(event)
        assert count == 1
        assert len(received) == 1
        assert received[0].event_type == EventType.AGENT_STARTED

    def test_subscribe_with_filter(self):
        bus = EventBus()
        received = []
        bus.subscribe(
            lambda e: received.append(e),
            filter_fn=EventTypeFilter([EventType.AGENT_STARTED]),
        )
        bus.publish(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        bus.publish(create_event(EventType.TASK_RECEIVED, EventSource.AGENT))
        assert len(received) == 1
        assert received[0].event_type == EventType.AGENT_STARTED

    def test_unsubscribe(self):
        bus = EventBus()
        sub_id = bus.subscribe(lambda e: None)
        assert bus.subscriber_count == 1
        assert bus.unsubscribe(sub_id) is True
        assert bus.subscriber_count == 0

    def test_unsubscribe_unknown(self):
        bus = EventBus()
        assert bus.unsubscribe("unknown") is False

    def test_clear_subscribers(self):
        bus = EventBus()
        bus.subscribe(lambda e: None)
        bus.subscribe(lambda e: None)
        assert bus.subscriber_count == 2
        bus.clear_subscribers()
        assert bus.subscriber_count == 0

    def test_shutdown(self):
        bus = EventBus()
        bus.subscribe(lambda e: None)
        bus.shutdown()
        assert bus.is_active is False
        assert bus.subscriber_count == 0

    def test_publish_when_inactive(self):
        bus = EventBus()
        bus.shutdown()
        count = bus.publish(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        assert count == 0

    def test_subscriber_error_doesnt_crash(self):
        bus = EventBus()
        good_received = []
        bus.subscribe(lambda e: 1 / 0)  # Will raise
        bus.subscribe(lambda e: good_received.append(e))
        event = create_event(EventType.AGENT_STARTED, EventSource.AGENT)
        count = bus.publish(event)
        assert count == 1  # Only good subscriber notified
        assert bus.error_count == 1
        assert len(good_received) == 1

    def test_get_subscriber_ids(self):
        bus = EventBus()
        id1 = bus.subscribe(lambda e: None)
        id2 = bus.subscribe(lambda e: None)
        ids = bus.get_subscriber_ids()
        assert id1 in ids
        assert id2 in ids

    def test_event_count(self):
        bus = EventBus()
        bus.subscribe(lambda e: None)
        bus.publish(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        bus.publish(create_event(EventType.TASK_RECEIVED, EventSource.AGENT))
        assert bus.event_count == 2


class TestGlobalEventBus:
    """Tests for global event bus singleton."""

    def test_get_event_bus(self):
        reset_event_bus()
        bus = get_event_bus()
        assert isinstance(bus, EventBus)
        assert bus.is_active is True

    def test_reset_event_bus(self):
        bus = get_event_bus()
        reset_event_bus()
        new_bus = get_event_bus()
        assert new_bus is not bus


class TestEventFilters:
    """Tests for event filters."""

    def test_passthrough_filter(self):
        f = PassthroughFilter()
        event = create_event(EventType.AGENT_STARTED, EventSource.AGENT)
        assert f.matches(event) is True

    def test_event_type_filter(self):
        f = EventTypeFilter([EventType.AGENT_STARTED])
        assert f.matches(create_event(EventType.AGENT_STARTED, EventSource.AGENT)) is True
        assert f.matches(create_event(EventType.TASK_RECEIVED, EventSource.AGENT)) is False

    def test_event_source_filter(self):
        f = EventSourceFilter([EventSource.AGENT])
        assert f.matches(create_event(EventType.AGENT_STARTED, EventSource.AGENT)) is True
        assert f.matches(create_event(EventType.MODEL_REQUESTED, EventSource.MODEL_ROUTER)) is False

    def test_event_status_filter(self):
        f = EventStatusFilter([EventStatus.COMPLETED])
        assert f.matches(create_event(EventType.AGENT_COMPLETED, EventSource.AGENT, status=EventStatus.COMPLETED)) is True
        assert f.matches(create_event(EventType.AGENT_FAILED, EventSource.AGENT, status=EventStatus.FAILED)) is False

    def test_capability_filter(self):
        f = CapabilityFilter(["web_search"])
        assert f.matches(create_event(EventType.CAPABILITY_STARTED, EventSource.CAPABILITY_ROUTER, capability="web_search")) is True
        assert f.matches(create_event(EventType.CAPABILITY_STARTED, EventSource.CAPABILITY_ROUTER, capability="file_read")) is False

    def test_run_filter(self):
        f = RunFilter(["run-123"])
        assert f.matches(create_event(EventType.TASK_RECEIVED, EventSource.AGENT, run_id="run-123")) is True
        assert f.matches(create_event(EventType.TASK_RECEIVED, EventSource.AGENT, run_id="run-456")) is False

    def test_session_filter(self):
        f = SessionFilter(["session-123"])
        assert f.matches(create_event(EventType.TASK_RECEIVED, EventSource.AGENT, session_id="session-123")) is True
        assert f.matches(create_event(EventType.TASK_RECEIVED, EventSource.AGENT, session_id="session-456")) is False

    def test_success_filter(self):
        f = SuccessFilter()
        assert f.matches(create_event(EventType.AGENT_COMPLETED, EventSource.AGENT, status=EventStatus.COMPLETED)) is True
        assert f.matches(create_event(EventType.AGENT_FAILED, EventSource.AGENT, status=EventStatus.FAILED)) is False

    def test_failure_filter(self):
        f = FailureFilter()
        assert f.matches(create_event(EventType.AGENT_FAILED, EventSource.AGENT, status=EventStatus.FAILED)) is True
        assert f.matches(create_event(EventType.AGENT_COMPLETED, EventSource.AGENT, status=EventStatus.COMPLETED)) is False

    def test_security_filter(self):
        f = SecurityFilter()
        assert f.matches(create_event(EventType.SECURITY_DENIED, EventSource.SECURITY_KERNEL)) is True
        assert f.matches(create_event(EventType.AGENT_STARTED, EventSource.AGENT)) is False

    def test_recovery_filter(self):
        f = RecoveryFilter()
        assert f.matches(create_event(EventType.RECOVERY_STARTED, EventSource.RECOVERY_ENGINE)) is True
        assert f.matches(create_event(EventType.AGENT_STARTED, EventSource.AGENT)) is False

    def test_mcp_filter(self):
        f = MCPFilter()
        assert f.matches(create_event(EventType.MCP_CONNECTED, EventSource.MCP_CLIENT)) is True
        assert f.matches(create_event(EventType.AGENT_STARTED, EventSource.AGENT)) is False

    def test_and_filter(self):
        f = AndFilter(
            EventSourceFilter([EventSource.AGENT]),
            EventTypeFilter([EventType.AGENT_STARTED]),
        )
        assert f.matches(create_event(EventType.AGENT_STARTED, EventSource.AGENT)) is True
        assert f.matches(create_event(EventType.TASK_RECEIVED, EventSource.AGENT)) is False

    def test_or_filter(self):
        f = OrFilter(
            EventTypeFilter([EventType.AGENT_STARTED]),
            EventTypeFilter([EventType.TASK_RECEIVED]),
        )
        assert f.matches(create_event(EventType.AGENT_STARTED, EventSource.AGENT)) is True
        assert f.matches(create_event(EventType.TASK_RECEIVED, EventSource.AGENT)) is True
        assert f.matches(create_event(EventType.MODEL_REQUESTED, EventSource.MODEL_ROUTER)) is False

    def test_not_filter(self):
        f = NotFilter(EventTypeFilter([EventType.AGENT_STARTED]))
        assert f.matches(create_event(EventType.AGENT_STARTED, EventSource.AGENT)) is False
        assert f.matches(create_event(EventType.TASK_RECEIVED, EventSource.AGENT)) is True

    def test_custom_filter(self):
        f = CustomFilter(lambda e: e.run_id == "run-123")
        assert f.matches(create_event(EventType.TASK_RECEIVED, EventSource.AGENT, run_id="run-123")) is True
        assert f.matches(create_event(EventType.TASK_RECEIVED, EventSource.AGENT, run_id="run-456")) is False

    def test_time_range_filter(self):
        now = time.time()
        f = TimeRangeFilter(start=now - 60, end=now + 60)
        # Create events directly to control timestamp
        event_in_range = AgentEvent(
            event_type=EventType.TASK_RECEIVED,
            source=EventSource.AGENT,
            timestamp=now,
        )
        event_out_of_range = AgentEvent(
            event_type=EventType.TASK_RECEIVED,
            source=EventSource.AGENT,
            timestamp=now + 120,
        )
        assert f.matches(event_in_range) is True
        assert f.matches(event_out_of_range) is False


class TestEventSinks:
    """Tests for event sinks."""

    def test_console_sink(self):
        sink = ConsoleSink()
        event = create_event(EventType.AGENT_STARTED, EventSource.AGENT)
        sink.emit(event)  # Should not raise
        sink.flush()
        sink.close()

    def test_memory_sink(self):
        sink = MemorySink()
        event = create_event(EventType.AGENT_STARTED, EventSource.AGENT)
        sink.emit(event)
        assert sink.event_count == 1
        events = sink.get_events()
        assert len(events) == 1
        sink.close()

    def test_memory_sink_max_events(self):
        sink = MemorySink(max_events=2)
        sink.emit(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        sink.emit(create_event(EventType.TASK_RECEIVED, EventSource.AGENT))
        sink.emit(create_event(EventType.MODEL_REQUESTED, EventSource.MODEL_ROUTER))
        assert sink.event_count == 2
        sink.close()

    def test_memory_sink_clear(self):
        sink = MemorySink()
        sink.emit(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        sink.clear()
        assert sink.event_count == 0

    def test_memory_sink_get_by_type(self):
        sink = MemorySink()
        sink.emit(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        sink.emit(create_event(EventType.TASK_RECEIVED, EventSource.AGENT))
        sink.emit(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        events = sink.get_events_by_type("agent.started")
        assert len(events) == 2

    def test_memory_sink_get_by_run(self):
        sink = MemorySink()
        event = create_event(EventType.TASK_RECEIVED, EventSource.AGENT, run_id="run-123")
        sink.emit(event)
        events = sink.get_events_by_run("run-123")
        assert len(events) == 1

    def test_memory_sink_get_by_session(self):
        sink = MemorySink()
        event = create_event(EventType.TASK_RECEIVED, EventSource.AGENT, session_id="session-456")
        sink.emit(event)
        events = sink.get_events_by_session("session-456")
        assert len(events) == 1

    def test_memory_sink_get_by_capability(self):
        sink = MemorySink()
        event = create_event(EventType.CAPABILITY_STARTED, EventSource.CAPABILITY_ROUTER, capability="web_search")
        sink.emit(event)
        events = sink.get_events_by_capability("web_search")
        assert len(events) == 1

    def test_json_sink(self):
        sink = JsonSink()
        event = create_event(EventType.AGENT_STARTED, EventSource.AGENT)
        sink.emit(event)  # Should not raise
        sink.flush()
        sink.close()

    def test_callback_sink(self):
        received = []
        sink = CallbackSink(callback=received.append)
        event = create_event(EventType.AGENT_STARTED, EventSource.AGENT)
        sink.emit(event)
        assert len(received) == 1
        sink.close()

    def test_multi_sink(self):
        sink1 = MemorySink()
        sink2 = MemorySink()
        multi = MultiSink(sink1, sink2)
        event = create_event(EventType.AGENT_STARTED, EventSource.AGENT)
        multi.emit(event)
        assert sink1.event_count == 1
        assert sink2.event_count == 1
        multi.flush()
        multi.close()

    def test_audit_trail_sink_no_audit(self):
        sink = AuditTrailSink(audit_trail=None)
        event = create_event(EventType.SECURITY_DENIED, EventSource.SECURITY_KERNEL)
        sink.emit(event)  # Should not raise
        sink.close()


class TestEventSubscribers:
    """Tests for event subscribers."""

    def test_callback_subscriber(self):
        received = []
        sub = CallbackSubscriber(callback=received.append)
        event = create_event(EventType.AGENT_STARTED, EventSource.AGENT)
        sub.on_event(event)
        assert len(received) == 1

    def test_logging_subscriber(self):
        sub = LoggingSubscriber()
        event = create_event(EventType.AGENT_STARTED, EventSource.AGENT)
        sub.on_event(event)  # Should not raise

    def test_counting_subscriber(self):
        sub = CountingSubscriber()
        sub.on_event(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        sub.on_event(create_event(EventType.TASK_RECEIVED, EventSource.AGENT))
        sub.on_event(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        assert sub.get_count("agent.started") == 2
        assert sub.get_count("task.received") == 1
        assert sub.total_count == 3
        assert sub.get_counts() == {"agent.started": 2, "task.received": 1}

    def test_counting_subscriber_reset(self):
        sub = CountingSubscriber()
        sub.on_event(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        sub.reset()
        assert sub.total_count == 0

    def test_collecting_subscriber(self):
        sub = CollectingSubscriber()
        event = create_event(EventType.AGENT_STARTED, EventSource.AGENT)
        sub.on_event(event)
        assert sub.event_count == 1
        assert len(sub.get_events()) == 1

    def test_collecting_subscriber_max(self):
        sub = CollectingSubscriber(max_events=2)
        sub.on_event(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        sub.on_event(create_event(EventType.TASK_RECEIVED, EventSource.AGENT))
        sub.on_event(create_event(EventType.MODEL_REQUESTED, EventSource.MODEL_ROUTER))
        assert sub.event_count == 2

    def test_collecting_subscriber_clear(self):
        sub = CollectingSubscriber()
        sub.on_event(create_event(EventType.AGENT_STARTED, EventSource.AGENT))
        sub.clear()
        assert sub.event_count == 0

    def test_alert_subscriber(self):
        alerts = []
        sub = AlertSubscriber(alert_fn=alerts.append)
        event = create_event(EventType.AGENT_FAILED, EventSource.AGENT, status=EventStatus.FAILED)
        sub.on_event(event)
        assert len(alerts) == 1

    def test_subscriber_matches(self):
        sub = CallbackSubscriber(
            callback=lambda e: None,
            filter_fn=EventTypeFilter([EventType.AGENT_STARTED]),
        )
        assert sub.matches(create_event(EventType.AGENT_STARTED, EventSource.AGENT)) is True
        assert sub.matches(create_event(EventType.TASK_RECEIVED, EventSource.AGENT)) is False


class TestEventEmitter:
    """Tests for EventEmitter."""

    def test_emit_event(self):
        bus = EventBus()
        emitter = EventEmitter(bus)
        event = emitter.emit(
            event_type=EventType.AGENT_STARTED,
            source=EventSource.AGENT,
        )
        assert event.event_type == EventType.AGENT_STARTED
        assert bus.event_count == 1

    def test_emit_with_run_id(self):
        bus = EventBus()
        emitter = EventEmitter(bus, run_id="run-123")
        event = emitter.emit(
            event_type=EventType.TASK_RECEIVED,
            source=EventSource.AGENT,
        )
        assert event.run_id == "run-123"

    def test_timed_context(self):
        bus = EventBus()
        emitter = EventEmitter(bus)
        with EventTimedContext(emitter, EventType.CAPABILITY_STARTED, EventSource.CAPABILITY_ROUTER) as ctx:
            pass  # Events emitted on enter and exit
        # Two events: STARTED on enter, COMPLETED on exit
        assert bus.event_count == 2
        assert ctx.event is not None
        assert ctx.event.status == EventStatus.STARTED

    def test_timed_context_with_exception(self):
        bus = EventBus()
        emitter = EventEmitter(bus)
        with pytest.raises(ValueError):
            with EventTimedContext(emitter, EventType.CAPABILITY_STARTED, EventSource.CAPABILITY_ROUTER) as ctx:
                raise ValueError("test error")
        # Two events: STARTED on enter, FAILED on exit
        assert bus.event_count == 2


class TestCorrelationTracker:
    """Tests for CorrelationTracker."""

    def test_create_tracker(self):
        tracker = CorrelationTracker()
        assert tracker.event_count == 0
        assert tracker.run_count == 0
        assert tracker.session_count == 0

    def test_track_event(self):
        tracker = CorrelationTracker()
        event = create_event(EventType.TASK_RECEIVED, EventSource.AGENT, run_id="run-123")
        tracker.track(event)
        assert tracker.event_count == 1
        assert tracker.run_count == 1

    def test_get_event(self):
        tracker = CorrelationTracker()
        event = create_event(EventType.TASK_RECEIVED, EventSource.AGENT)
        tracker.track(event)
        retrieved = tracker.get_event(event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == event.event_id

    def test_get_run_events(self):
        tracker = CorrelationTracker()
        event1 = create_event(EventType.TASK_RECEIVED, EventSource.AGENT, run_id="run-123")
        event2 = create_event(EventType.MODEL_REQUESTED, EventSource.MODEL_ROUTER, run_id="run-123")
        tracker.track(event1)
        tracker.track(event2)
        events = tracker.get_run_events("run-123")
        assert len(events) == 2

    def test_get_session_events(self):
        tracker = CorrelationTracker()
        event = create_event(EventType.TASK_RECEIVED, EventSource.AGENT, session_id="session-456")
        tracker.track(event)
        events = tracker.get_session_events("session-456")
        assert len(events) == 1

    def test_get_children(self):
        tracker = CorrelationTracker()
        parent = create_event(EventType.TASK_RECEIVED, EventSource.AGENT, run_id="run-123")
        child = create_event(EventType.CAPABILITY_STARTED, EventSource.CAPABILITY_ROUTER, parent=parent)
        tracker.track(parent)
        tracker.track(child)
        children = tracker.get_children(parent.event_id)
        assert len(children) == 1
        assert children[0].event_id == child.event_id

    def test_get_root_events(self):
        tracker = CorrelationTracker()
        parent = create_event(EventType.TASK_RECEIVED, EventSource.AGENT, run_id="run-123")
        child = create_event(EventType.CAPABILITY_STARTED, EventSource.CAPABILITY_ROUTER, parent=parent)
        tracker.track(parent)
        tracker.track(child)
        roots = tracker.get_root_events("run-123")
        assert len(roots) == 1
        assert roots[0].event_id == parent.event_id

    def test_get_event_tree(self):
        tracker = CorrelationTracker()
        parent = create_event(EventType.TASK_RECEIVED, EventSource.AGENT, run_id="run-123")
        child = create_event(EventType.CAPABILITY_STARTED, EventSource.CAPABILITY_ROUTER, parent=parent)
        tracker.track(parent)
        tracker.track(child)
        tree = tracker.get_event_tree(parent.event_id)
        assert tree["event"].event_id == parent.event_id
        assert len(tree["children"]) == 1

    def test_get_ancestors(self):
        tracker = CorrelationTracker()
        parent = create_event(EventType.TASK_RECEIVED, EventSource.AGENT)
        child = create_event(EventType.CAPABILITY_STARTED, EventSource.CAPABILITY_ROUTER, parent=parent)
        tracker.track(parent)
        tracker.track(child)
        ancestors = tracker.get_ancestors(child.event_id)
        assert len(ancestors) == 1
        assert ancestors[0].event_id == parent.event_id

    def test_get_descendants(self):
        tracker = CorrelationTracker()
        parent = create_event(EventType.TASK_RECEIVED, EventSource.AGENT)
        child = create_event(EventType.CAPABILITY_STARTED, EventSource.CAPABILITY_ROUTER, parent=parent)
        tracker.track(parent)
        tracker.track(child)
        descendants = tracker.get_descendants(parent.event_id)
        assert len(descendants) == 1
        assert descendants[0].event_id == child.event_id

    def test_clear(self):
        tracker = CorrelationTracker()
        event = create_event(EventType.TASK_RECEIVED, EventSource.AGENT, run_id="run-123")
        tracker.track(event)
        tracker.clear()
        assert tracker.event_count == 0
        assert tracker.run_count == 0

    def test_global_tracker(self):
        reset_correlation_tracker()
        tracker = get_correlation_tracker()
        assert isinstance(tracker, CorrelationTracker)
        reset_correlation_tracker()
