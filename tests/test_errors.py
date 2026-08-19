"""
Tests for AgentCore structured error taxonomy (Phase 8).
"""

import pytest

from agentcore.errors import (
    AgentCoreError,
    ConfigurationError,
    ShutdownError,
    TaskAlreadyRunningError,
    TaskLockError,
    TaskNotFoundError,
    TaskRecoveryError,
)


class TestAgentCoreError:
    def test_base_error_message(self):
        err = AgentCoreError("something failed")
        assert str(err) == "something failed"

    def test_base_error_with_details(self):
        err = AgentCoreError("failed", details={"key": "value"})
        assert err.details == {"key": "value"}

    def test_to_dict(self):
        err = AgentCoreError("test", details={"field": "x"})
        d = err.to_dict()
        assert d["error"] == "AgentCoreError"
        assert d["message"] == "test"
        assert d["details"]["field"] == "x"

    def test_is_exception(self):
        with pytest.raises(AgentCoreError):
            raise AgentCoreError("test")


class TestTaskAlreadyRunningError:
    def test_default_message(self):
        err = TaskAlreadyRunningError("task-123")
        assert "task-123" in str(err)
        assert err.details["task_id"] == "task-123"

    def test_custom_message(self):
        err = TaskAlreadyRunningError("task-123", "Custom message")
        assert str(err) == "Custom message"


class TestTaskNotFoundError:
    def test_default_message(self):
        err = TaskNotFoundError("task-456")
        assert "task-456" in str(err)
        assert err.details["task_id"] == "task-456"

    def test_custom_message(self):
        err = TaskNotFoundError("task-456", "Not here")
        assert str(err) == "Not here"


class TestTaskRecoveryError:
    def test_default_message(self):
        err = TaskRecoveryError("task-789", "corrupt data")
        assert "task-789" in str(err)
        assert "corrupt data" in str(err)
        assert err.details["task_id"] == "task-789"
        assert err.details["reason"] == "corrupt data"


class TestTaskLockError:
    def test_default_message(self):
        err = TaskLockError("task-abc", "acquire")
        assert "task-abc" in str(err)
        assert "acquire" in str(err)
        assert err.details["task_id"] == "task-abc"
        assert err.details["operation"] == "acquire"

    def test_custom_message(self):
        err = TaskLockError("task-abc", "release", "Custom lock error")
        assert str(err) == "Custom lock error"


class TestShutdownError:
    def test_default_message(self):
        err = ShutdownError("persistence failure")
        assert "persistence failure" in str(err)
        assert err.details["reason"] == "persistence failure"

    def test_custom_message(self):
        err = ShutdownError("timeout", "Shutdown timed out")
        assert str(err) == "Shutdown timed out"


class TestConfigurationError:
    def test_default_message(self):
        err = ConfigurationError("max_iterations", "must be positive")
        assert "max_iterations" in str(err)
        assert "must be positive" in str(err)
        assert err.details["field"] == "max_iterations"
        assert err.details["reason"] == "must be positive"

    def test_custom_message(self):
        err = ConfigurationError("timeout", "too small", "Custom config error")
        assert str(err) == "Custom config error"


class TestErrorHierarchy:
    def test_all_errors_are_agent_core_errors(self):
        errors = [
            TaskAlreadyRunningError("t"),
            TaskNotFoundError("t"),
            TaskRecoveryError("t", "r"),
            TaskLockError("t", "op"),
            ShutdownError("r"),
            ConfigurationError("f", "r"),
        ]
        for err in errors:
            assert isinstance(err, AgentCoreError)
            assert isinstance(err, Exception)
