"""Tests for ARGUS Performance resource control."""

import pytest

from argus.performance.resources import ResourceController, ResourceError
from argus.performance.models import (
    PerformanceBudget,
    ResourceBudget,
    ResourceType,
)


class TestResourceController:
    """Tests for ResourceController."""

    def setup_method(self):
        self.budget = PerformanceBudget(
            max_concurrent_runs=2,
            max_tool_calls=10,
            max_tokens=1000,
        )
        self.controller = ResourceController(self.budget)

    def test_check_available(self):
        assert self.controller.check_available(ResourceType.CONCURRENT_RUNS) is True

    def test_acquire_resource(self):
        assert self.controller.acquire(ResourceType.CONCURRENT_RUNS) is True
        assert self.controller.usage.current_concurrent_runs == 1

    def test_acquire_until_exhausted(self):
        assert self.controller.acquire(ResourceType.CONCURRENT_RUNS) is True
        assert self.controller.acquire(ResourceType.CONCURRENT_RUNS) is True
        assert self.controller.acquire(ResourceType.CONCURRENT_RUNS) is False

    def test_release_resource(self):
        self.controller.acquire(ResourceType.CONCURRENT_RUNS)
        self.controller.release(ResourceType.CONCURRENT_RUNS)
        assert self.controller.usage.current_concurrent_runs == 0

    def test_release_below_zero(self):
        self.controller.release(ResourceType.CONCURRENT_RUNS)
        assert self.controller.usage.current_concurrent_runs == 0

    def test_measure(self):
        self.controller.acquire(ResourceType.CONCURRENT_RUNS)
        measurement = self.controller.measure(ResourceType.CONCURRENT_RUNS)
        assert measurement.current_usage == 1
        assert measurement.max_usage == 2

    def test_tool_calls_budget(self):
        assert self.controller.acquire(ResourceType.TOOL_CALLS, 5) is True
        assert self.controller.usage.current_tool_calls == 5

    def test_tokens_budget(self):
        assert self.controller.acquire(ResourceType.TOKENS, 500) is True
        assert self.controller.usage.current_tokens == 500

    def test_multiple_resource_types(self):
        self.controller.acquire(ResourceType.CONCURRENT_RUNS)
        self.controller.acquire(ResourceType.TOOL_CALLS, 3)
        self.controller.acquire(ResourceType.TOKENS, 100)
        assert self.controller.usage.current_concurrent_runs == 1
        assert self.controller.usage.current_tool_calls == 3
        assert self.controller.usage.current_tokens == 100


class TestResourceBudget:
    """Tests for ResourceBudget model."""

    def test_is_exhausted(self):
        budget = PerformanceBudget(max_concurrent_runs=2)
        usage = ResourceBudget(
            limits=budget,
            current_concurrent_runs=2,
        )
        assert usage.is_exhausted(ResourceType.CONCURRENT_RUNS) is True

    def test_is_not_exhausted(self):
        budget = PerformanceBudget(max_concurrent_runs=5)
        usage = ResourceBudget(
            limits=budget,
            current_concurrent_runs=2,
        )
        assert usage.is_exhausted(ResourceType.CONCURRENT_RUNS) is False

    def test_not_exhausted_at_zero(self):
        budget = PerformanceBudget(max_concurrent_runs=5)
        usage = ResourceBudget(limits=budget)
        assert usage.is_exhausted(ResourceType.CONCURRENT_RUNS) is False

    def test_exceeds_limit(self):
        budget = PerformanceBudget(max_concurrent_runs=2)
        usage = ResourceBudget(
            limits=budget,
            current_concurrent_runs=5,
        )
        assert usage.is_exhausted(ResourceType.CONCURRENT_RUNS) is True
