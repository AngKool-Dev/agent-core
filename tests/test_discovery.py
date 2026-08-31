"""Tests for ARGUS capability discovery subsystem."""

import os
import tempfile
from pathlib import Path

import pytest

from argus.discovery import (
    CapabilityDiscoveryRegistry,
    CapabilityMetadata,
    DirectoryDiscoverySource,
    ModuleDiscoverySource,
    StaticDiscoverySource,
    discover_capabilities,
)


class TestCapabilityMetadata:
    """Tests for CapabilityMetadata."""

    def test_create_metadata(self):
        meta = CapabilityMetadata(
            name="web_search",
            version="1.0.0",
            description="Search the web",
            source="builtin",
            tags=["web", "search"],
        )
        assert meta.name == "web_search"
        assert meta.version == "1.0.0"
        assert meta.description == "Search the web"
        assert meta.source == "builtin"
        assert "web" in meta.tags

    def test_default_values(self):
        meta = CapabilityMetadata(name="test")
        assert meta.version == "1.0.0"
        assert meta.description == ""
        assert meta.source == "unknown"
        assert meta.tags == []
        assert meta.dependencies == []
        assert meta.config == {}
        assert meta.health_check is None
        assert meta.priority == 0

    def test_to_dict(self):
        meta = CapabilityMetadata(
            name="test",
            version="2.0.0",
            tags=["tag1", "tag2"],
            dependencies=["dep1"],
            config={"key": "value"},
        )
        d = meta.to_dict()
        assert d["name"] == "test"
        assert d["version"] == "2.0.0"
        assert d["tags"] == ["tag1", "tag2"]
        assert d["dependencies"] == ["dep1"]
        assert d["config"] == {"key": "value"}


class TestStaticDiscoverySource:
    """Tests for StaticDiscoverySource."""

    def test_discover(self):
        caps = [
            CapabilityMetadata(name="cap1"),
            CapabilityMetadata(name="cap2"),
        ]
        source = StaticDiscoverySource(caps)
        discovered = source.discover()
        assert len(discovered) == 2
        assert discovered[0].name == "cap1"
        assert discovered[1].name == "cap2"

    def test_source_name(self):
        source = StaticDiscoverySource([], name="my_source")
        assert source.source_name() == "my_source"

    def test_default_name(self):
        source = StaticDiscoverySource([])
        assert source.source_name() == "static"

    def test_empty_list(self):
        source = StaticDiscoverySource([])
        assert source.discover() == []


class TestModuleDiscoverySource:
    """Tests for ModuleDiscoverySource."""

    def test_discover_from_module(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
CAPABILITIES = [
    {
        "name": "test_cap",
        "version": "1.0.0",
        "description": "A test capability",
        "tags": ["test"],
    }
]
""")
            f.flush()
            temp_path = f.name
        try:
            source = ModuleDiscoverySource([temp_path])
            discovered = source.discover()
            assert len(discovered) == 1
            assert discovered[0].name == "test_cap"
            assert discovered[0].description == "A test capability"
        finally:
            import os
            import time
            time.sleep(0.1)  # Allow file handle to be released
            try:
                os.unlink(temp_path)
            except PermissionError:
                pass  # Windows file locking

    def test_discover_from_nonexistent_module(self):
        source = ModuleDiscoverySource(["/nonexistent/path.py"])
        discovered = source.discover()
        assert discovered == []

    def test_discover_from_invalid_module(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("invalid python syntax {{{")
            f.flush()
            temp_path = f.name
        try:
            source = ModuleDiscoverySource([temp_path])
            discovered = source.discover()
            assert discovered == []
        finally:
            import os
            import time
            time.sleep(0.1)
            try:
                os.unlink(temp_path)
            except PermissionError:
                pass

    def test_source_name(self):
        source = ModuleDiscoverySource([], name="my_module_source")
        assert source.source_name() == "my_module_source"


class TestDirectoryDiscoverySource:
    """Tests for DirectoryDiscoverySource."""

    def test_discover_from_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a capability file
            cap_file = Path(tmpdir) / "my_capability.py"
            cap_file.write_text("""
CAPABILITIES = [
    {
        "name": "dir_cap",
        "description": "Discovered from directory",
    }
]
""")
            source = DirectoryDiscoverySource([tmpdir])
            discovered = source.discover()
            assert len(discovered) == 1
            assert discovered[0].name == "dir_cap"

    def test_discover_from_nonexistent_directory(self):
        source = DirectoryDiscoverySource(["/nonexistent/dir"])
        discovered = source.discover()
        assert discovered == []

    def test_discover_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                cap_file = Path(tmpdir) / f"cap_{i}.py"
                cap_file.write_text(f"""
CAPABILITIES = [
    {{
        "name": "cap_{i}",
        "description": "Capability {i}",
    }}
]
""")
            source = DirectoryDiscoverySource([tmpdir])
            discovered = source.discover()
            assert len(discovered) == 3

    def test_source_name(self):
        source = DirectoryDiscoverySource([], name="my_dir_source")
        assert source.source_name() == "my_dir_source"


class TestCapabilityDiscoveryRegistry:
    """Tests for CapabilityDiscoveryRegistry."""

    def test_create_registry(self):
        registry = CapabilityDiscoveryRegistry()
        assert registry.get_sources() == []
        assert registry.get_discovered() == {}

    def test_register_source(self):
        registry = CapabilityDiscoveryRegistry()
        source = StaticDiscoverySource([CapabilityMetadata(name="test")])
        registry.register_source(source)
        assert "static" in registry.get_sources()

    def test_unregister_source(self):
        registry = CapabilityDiscoveryRegistry()
        source = StaticDiscoverySource([])
        registry.register_source(source)
        assert registry.unregister_source("static") is True
        assert "static" not in registry.get_sources()

    def test_unregister_unknown_source(self):
        registry = CapabilityDiscoveryRegistry()
        assert registry.unregister_source("unknown") is False

    def test_discover_all(self):
        registry = CapabilityDiscoveryRegistry()
        registry.register_source(StaticDiscoverySource([
            CapabilityMetadata(name="cap1"),
            CapabilityMetadata(name="cap2"),
        ]))
        discovered = registry.discover_all()
        assert len(discovered) == 2

    def test_get_discovered(self):
        registry = CapabilityDiscoveryRegistry()
        registry.register_source(StaticDiscoverySource([
            CapabilityMetadata(name="cap1"),
        ]))
        registry.discover_all()
        discovered = registry.get_discovered()
        assert "cap1" in discovered

    def test_get_capability(self):
        registry = CapabilityDiscoveryRegistry()
        registry.register_source(StaticDiscoverySource([
            CapabilityMetadata(name="cap1", description="Test"),
        ]))
        registry.discover_all()
        cap = registry.get_capability("cap1")
        assert cap is not None
        assert cap.description == "Test"

    def test_get_nonexistent_capability(self):
        registry = CapabilityDiscoveryRegistry()
        assert registry.get_capability("nonexistent") is None

    def test_get_errors(self):
        registry = CapabilityDiscoveryRegistry()
        # No errors initially
        assert registry.get_errors() == {}

    def test_filter_by_tag(self):
        registry = CapabilityDiscoveryRegistry()
        registry.register_source(StaticDiscoverySource([
            CapabilityMetadata(name="cap1", tags=["web", "search"]),
            CapabilityMetadata(name="cap2", tags=["file", "read"]),
            CapabilityMetadata(name="cap3", tags=["web", "scrape"]),
        ]))
        registry.discover_all()
        web_caps = registry.filter_by_tag("web")
        assert len(web_caps) == 2

    def test_filter_by_source(self):
        registry = CapabilityDiscoveryRegistry()
        registry.register_source(StaticDiscoverySource(
            [CapabilityMetadata(name="cap1")],
            name="source1",
        ))
        registry.register_source(StaticDiscoverySource(
            [CapabilityMetadata(name="cap2")],
            name="source2",
        ))
        registry.discover_all()
        source1_caps = registry.filter_by_source("source1")
        assert len(source1_caps) == 1
        assert source1_caps[0].name == "cap1"

    def test_multiple_sources(self):
        registry = CapabilityDiscoveryRegistry()
        registry.register_source(StaticDiscoverySource([
            CapabilityMetadata(name="cap1"),
        ], name="source1"))
        registry.register_source(StaticDiscoverySource([
            CapabilityMetadata(name="cap2"),
        ], name="source2"))
        discovered = registry.discover_all()
        assert len(discovered) == 2

    def test_deduplication_by_name(self):
        registry = CapabilityDiscoveryRegistry()
        registry.register_source(StaticDiscoverySource([
            CapabilityMetadata(name="cap1", version="1.0"),
        ], name="source1"))
        registry.register_source(StaticDiscoverySource([
            CapabilityMetadata(name="cap1", version="2.0"),
        ], name="source2"))
        discovered = registry.discover_all()
        # Last one wins
        assert len(discovered) == 1
        assert discovered[0].version == "2.0"


class TestDiscoverCapabilities:
    """Tests for discover_capabilities convenience function."""

    def test_discover_with_sources(self):
        sources = [
            StaticDiscoverySource([CapabilityMetadata(name="cap1")], name="source1"),
            StaticDiscoverySource([CapabilityMetadata(name="cap2")], name="source2"),
        ]
        discovered = discover_capabilities(sources)
        assert len(discovered) == 2

    def test_discover_without_sources(self):
        discovered = discover_capabilities()
        assert discovered == []
