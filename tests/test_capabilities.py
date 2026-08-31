"""Tests for the Argus capability abstraction."""

import pytest
from pathlib import Path

from argus.capabilities import (
    Capability,
    CapabilityMetadata,
    CapabilityRegistry,
    CapabilityRouter,
    CapabilitySchema,
    CapabilityType,
    ModelCapability,
    ToolCapability,
)
from argus.capabilities.adapter import create_tool_capability, register_default_tool_capabilities
from argus.tools import Tool, ToolResult
from argus.tools.file import ListDirTool, ReadFileTool
from argus.tools.bash import BashTool


class FakeTool(Tool):
    name = "fake_tool"
    description = "A fake tool for testing"

    def __init__(self, result: ToolResult = None):
        self._result = result or ToolResult(tool=self.name, success=True, output="fake result")

    def execute(self, **kwargs) -> ToolResult:
        return self._result


class TestCapabilityMetadata:
    def test_metadata_creation(self):
        schema = CapabilitySchema(name="test", description="Test cap")
        metadata = CapabilityMetadata(
            id="test.cap",
            name="Test",
            description="Test capability",
            type=CapabilityType.READ,
            schema=schema,
        )

        assert metadata.id == "test.cap"
        assert metadata.name == "Test"
        assert metadata.type == CapabilityType.READ
        assert metadata.health_status == "unknown"
        assert metadata.availability is True

    def test_metadata_with_permissions(self):
        schema = CapabilitySchema(name="test", description="Test")
        metadata = CapabilityMetadata(
            id="test",
            name="Test",
            description="d",
            type=CapabilityType.WRITE,
            schema=schema,
            permissions={"read": "allow", "write": "ask"},
            cost={"tokens": 0.001},
        )

        assert metadata.permissions == {"read": "allow", "write": "ask"}
        assert metadata.cost == {"tokens": 0.001}


class TestToolCapabilityAdapter:
    def test_adapter_creation(self):
        tool = FakeTool()
        cap = create_tool_capability(tool, "test.cap")
        assert cap.get_id() == "test.cap"
        assert cap.get_description() == "A fake tool for testing"

    def test_execute_success(self):
        tool = FakeTool()
        cap = create_tool_capability(tool, "test.cap")
        result = cap.execute({})
        assert result["success"] is True
        assert result["output"]["output"] == "fake result"
        assert result["execution_time"] >= 0

    def test_execute_failure(self):
        tool = FakeTool(ToolResult(tool="fake", success=False, error="boom"))
        cap = create_tool_capability(tool, "test.cap")
        result = cap.execute({})
        assert result["success"] is False
        assert result["error"] == "boom"

    def test_health_check(self):
        tool = FakeTool()
        cap = create_tool_capability(tool, "test.cap")
        health = cap.health_check()
        assert health["status"] in ("healthy", "unhealthy")
        assert "last_check" in health


class TestCapabilityRegistry:
    def test_register_and_get(self):
        registry = CapabilityRegistry()
        tool = FakeTool()
        cap = create_tool_capability(tool, "test.cap")
        registry.register(cap)

        assert registry.get("test.cap") is cap
        assert len(registry.list()) == 1

    def test_search(self):
        registry = CapabilityRegistry()
        cap1 = create_tool_capability(FakeTool(), "read.file")
        cap2 = create_tool_capability(FakeTool(), "write.file")
        registry.register(cap1)
        registry.register(cap2)

        results = registry.search("read")
        assert len(results) == 1
        assert results[0].get_id() == "read.file"

    def test_get_by_type(self):
        registry = CapabilityRegistry()
        tool = FakeTool()
        cap = create_tool_capability(tool, "test")
        cap.metadata.type = CapabilityType.SEARCH
        registry.register(cap)

        results = registry.get_by_type(CapabilityType.SEARCH)
        assert len(results) == 1

        results = registry.get_by_type(CapabilityType.READ)
        assert len(results) == 0

    def test_register_default_tools(self):
        from argus.tools import ToolRegistry
        from argus.permissions import PermissionConfig

        tool_registry = ToolRegistry(permissions=PermissionConfig())
        cap_registry = CapabilityRegistry()
        cap_registry.set_registry_references(
            tool_registry=tool_registry,
            permissions=PermissionConfig(),
        )

        register_default_tool_capabilities(cap_registry, tool_registry)

        assert cap_registry.get("filesystem.read") is not None
        assert cap_registry.get("shell.execute") is not None
        assert cap_registry.get("git.status") is not None
        assert cap_registry.get("memory.search") is not None

    def test_infer_type(self):
        from argus.capabilities.adapter import _infer_type
        assert _infer_type("read_file") == CapabilityType.READ
        assert _infer_type("write_file") == CapabilityType.WRITE
        assert _infer_type("bash") == CapabilityType.EXECUTE
        assert _infer_type("grep") == CapabilityType.SEARCH
        assert _infer_type("browser") == CapabilityType.BROWSER
        assert _infer_type("git_status") == CapabilityType.GIT


class TestCapabilityRouter:
    def test_route_existing_capability(self):
        registry = CapabilityRegistry()
        tool = FakeTool()
        cap = create_tool_capability(tool, "test.cap")
        registry.register(cap)

        router = CapabilityRouter(registry)
        result = router.route("test.cap", {})

        assert result["success"] is True

    def test_route_missing_capability(self):
        registry = CapabilityRegistry()
        router = CapabilityRouter(registry)
        result = router.route("nonexistent.cap", {})

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_execution_history(self):
        registry = CapabilityRegistry()
        tool = FakeTool()
        cap = create_tool_capability(tool, "test.cap")
        registry.register(cap)

        router = CapabilityRouter(registry)
        router.route("test.cap", {})
        router.route("test.cap", {})

        history = router.get_execution_history("test.cap")
        assert len(history) == 2

    def test_health_status(self):
        registry = CapabilityRegistry()
        tool = FakeTool()
        cap = create_tool_capability(tool, "test.cap")
        registry.register(cap)

        router = CapabilityRouter(registry)
        health = router.get_health_status()

        assert "test.cap" in health
        assert "name" in health["test.cap"]
        assert "type" in health["test.cap"]
        assert "health" in health["test.cap"]
        assert "available" in health["test.cap"]


class TestToolCapabilityInRegistry:
    def test_tool_capability_requires_validation(self):
        from argus.tools import ToolRegistry
        from argus.permissions import PermissionConfig

        tool_registry = ToolRegistry(permissions=PermissionConfig())
        cap_registry = CapabilityRegistry()
        cap_registry.set_registry_references(
            tool_registry=tool_registry,
            permissions=PermissionConfig(),
        )
        register_default_tool_capabilities(cap_registry, tool_registry)

        # filesystem.read requires 'path' param
        cap = cap_registry.get("filesystem.read")
        assert cap is not None
        assert cap.can_execute({}) is False
        assert cap.can_execute({"path": "/tmp"}) is True
