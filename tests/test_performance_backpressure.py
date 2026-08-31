"""Tests for ARGUS Performance backpressure and isolation."""

import threading
import time

import pytest

from argus.performance.backpressure import BackpressureController, BackpressureError
from argus.performance.isolation import ExecutionContext, IsolationError, IsolationManager
from argus.performance.models import (
    BackpressureAction,
    PerformanceBudget,
    ResourceType,
)
from argus.performance.resources import ResourceController


class TestBackpressureController:
    """Tests for BackpressureController."""

    def setup_method(self):
        self.budget = PerformanceBudget(max_concurrent_runs=2)
        self.resource_controller = ResourceController(self.budget)
        self.backpressure = BackpressureController(self.resource_controller)

    def test_accept_when_available(self):
        action = self.backpressure.check_capacity(ResourceType.CONCURRENT_RUNS)
        assert action == BackpressureAction.ACCEPT

    def test_queue_when_exhausted(self):
        self.resource_controller.acquire(ResourceType.CONCURRENT_RUNS)
        self.resource_controller.acquire(ResourceType.CONCURRENT_RUNS)
        action = self.backpressure.check_capacity(
            ResourceType.CONCURRENT_RUNS,
            BackpressureAction.QUEUE,
        )
        assert action == BackpressureAction.QUEUE

    def test_reject_when_exhausted(self):
        self.resource_controller.acquire(ResourceType.CONCURRENT_RUNS)
        self.resource_controller.acquire(ResourceType.CONCURRENT_RUNS)
        action = self.backpressure.check_capacity(
            ResourceType.CONCURRENT_RUNS,
            BackpressureAction.REJECT,
        )
        assert action == BackpressureAction.REJECT

    def test_throttle_when_exhausted(self):
        self.resource_controller.acquire(ResourceType.CONCURRENT_RUNS)
        self.resource_controller.acquire(ResourceType.CONCURRENT_RUNS)
        action = self.backpressure.check_capacity(
            ResourceType.CONCURRENT_RUNS,
            BackpressureAction.THROTTLE,
        )
        assert action == BackpressureAction.THROTTLE

    def test_cancel_action(self):
        # Exhaust the resource first
        self.resource_controller.acquire(ResourceType.CONCURRENT_RUNS)
        self.resource_controller.acquire(ResourceType.CONCURRENT_RUNS)
        action = self.backpressure.check_capacity(
            ResourceType.CONCURRENT_RUNS,
            BackpressureAction.CANCEL,
        )
        assert action == BackpressureAction.CANCEL

    def test_wait_for_capacity(self):
        # Resource is available
        result = self.backpressure.wait_for_capacity(
            ResourceType.CONCURRENT_RUNS,
            timeout=0.1,
        )
        assert result is True

    def test_wait_for_capacity_timeout(self):
        # Exhaust the resource
        self.resource_controller.acquire(ResourceType.CONCURRENT_RUNS)
        self.resource_controller.acquire(ResourceType.CONCURRENT_RUNS)
        result = self.backpressure.wait_for_capacity(
            ResourceType.CONCURRENT_RUNS,
            timeout=0.01,
        )
        assert result is False

    def test_get_stats(self):
        stats = self.backpressure.get_stats()
        assert "wait_count" in stats
        assert "reject_count" in stats
        assert "throttle_count" in stats

    def test_reset_stats(self):
        self.backpressure.check_capacity(
            ResourceType.CONCURRENT_RUNS,
            BackpressureAction.QUEUE,
        )
        self.backpressure.reset_stats()
        stats = self.backpressure.get_stats()
        assert stats["wait_count"] == 0


class TestExecutionContext:
    """Tests for ExecutionContext."""

    def test_create_context(self):
        context = ExecutionContext("run-001")
        assert context.run_id == "run-001"

    def test_set_and_get(self):
        context = ExecutionContext("run-001")
        context.set("key", "value")
        assert context.get("key") == "value"

    def test_get_default(self):
        context = ExecutionContext("run-001")
        assert context.get("nonexistent", "default") == "default"

    def test_update(self):
        context = ExecutionContext("run-001")
        context.set("key", "old")
        context.update("key", "new")
        assert context.get("key") == "new"

    def test_delete(self):
        context = ExecutionContext("run-001")
        context.set("key", "value")
        context.delete("key")
        assert context.get("key") is None

    def test_clear(self):
        context = ExecutionContext("run-001")
        context.set("key1", "value1")
        context.set("key2", "value2")
        context.clear()
        assert context.get("key1") is None
        assert context.get("key2") is None

    def test_to_dict(self):
        context = ExecutionContext("run-001")
        context.set("key", "value")
        d = context.to_dict()
        assert d == {"key": "value"}

    def test_isolation_between_contexts(self):
        ctx1 = ExecutionContext("run-001")
        ctx2 = ExecutionContext("run-002")
        ctx1.set("key", "value1")
        ctx2.set("key", "value2")
        assert ctx1.get("key") == "value1"
        assert ctx2.get("key") == "value2"


class TestIsolationManager:
    """Tests for IsolationManager."""

    def test_create_context(self):
        manager = IsolationManager()
        context = manager.create_context("run-001")
        assert context.run_id == "run-001"

    def test_create_duplicate_raises_error(self):
        manager = IsolationManager()
        manager.create_context("run-001")
        with pytest.raises(IsolationError):
            manager.create_context("run-001")

    def test_get_context(self):
        manager = IsolationManager()
        manager.create_context("run-001")
        context = manager.get_context("run-001")
        assert context is not None
        assert context.run_id == "run-001"

    def test_get_nonexistent_context(self):
        manager = IsolationManager()
        assert manager.get_context("nonexistent") is None

    def test_remove_context(self):
        manager = IsolationManager()
        manager.create_context("run-001")
        assert manager.remove_context("run-001") is True
        assert manager.get_context("run-001") is None

    def test_remove_nonexistent_context(self):
        manager = IsolationManager()
        assert manager.remove_context("nonexistent") is False

    def test_has_context(self):
        manager = IsolationManager()
        manager.create_context("run-001")
        assert manager.has_context("run-001") is True
        assert manager.has_context("run-002") is False

    def test_list_contexts(self):
        manager = IsolationManager()
        manager.create_context("run-001")
        manager.create_context("run-002")
        contexts = manager.list_contexts()
        assert len(contexts) == 2
        assert "run-001" in contexts
        assert "run-002" in contexts

    def test_clear_all(self):
        manager = IsolationManager()
        manager.create_context("run-001")
        manager.create_context("run-002")
        manager.clear_all()
        assert manager.list_contexts() == []
