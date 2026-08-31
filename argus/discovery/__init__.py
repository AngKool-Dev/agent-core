"""ARGUS capability discovery subsystem."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class CapabilityMetadata:
    """Metadata for a discovered capability."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    source: str = "unknown"
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    health_check: Optional[str] = None
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "source": self.source,
            "tags": list(self.tags),
            "dependencies": list(self.dependencies),
            "config": dict(self.config),
            "health_check": self.health_check,
            "priority": self.priority,
        }


class CapabilityDiscoverySource(ABC):
    """Abstract base class for capability discovery sources."""

    @abstractmethod
    def discover(self) -> List[CapabilityMetadata]:
        """Discover capabilities from this source."""
        ...

    @abstractmethod
    def source_name(self) -> str:
        """Get the name of this source."""
        ...


class StaticDiscoverySource(CapabilityDiscoverySource):
    """Discovery source for statically defined capabilities."""

    def __init__(self, capabilities: List[CapabilityMetadata], name: str = "static"):
        self._capabilities = capabilities
        self._name = name

    def discover(self) -> List[CapabilityMetadata]:
        return list(self._capabilities)

    def source_name(self) -> str:
        return self._name


class ModuleDiscoverySource(CapabilityDiscoverySource):
    """Discovery source that scans Python modules for capabilities."""

    def __init__(self, module_paths: List[str], name: str = "module"):
        self._module_paths = module_paths
        self._name = name

    def discover(self) -> List[CapabilityMetadata]:
        capabilities = []
        for path in self._module_paths:
            caps = self._scan_module(path)
            capabilities.extend(caps)
        return capabilities

    def _scan_module(self, module_path: str) -> List[CapabilityMetadata]:
        """Scan a module for capability definitions."""
        import importlib
        import importlib.util

        try:
            spec = importlib.util.spec_from_file_location("cap_module", module_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return self._extract_capabilities(module)
        except Exception:
            pass
        return []

    def _extract_capabilities(self, module: Any) -> List[CapabilityMetadata]:
        """Extract capability metadata from a module."""
        capabilities = []
        if hasattr(module, "CAPABILITIES"):
            for cap_def in module.CAPABILITIES:
                if isinstance(cap_def, dict):
                    capabilities.append(CapabilityMetadata(**cap_def))
                elif isinstance(cap_def, CapabilityMetadata):
                    capabilities.append(cap_def)
        return capabilities

    def source_name(self) -> str:
        return self._name


class DirectoryDiscoverySource(CapabilityDiscoverySource):
    """Discovery source that scans directories for capability plugins."""

    def __init__(self, directories: List[str], pattern: str = "*.py", name: str = "directory"):
        self._directories = directories
        self._pattern = pattern
        self._name = name

    def discover(self) -> List[CapabilityMetadata]:
        import glob
        import os

        capabilities = []
        module_source = ModuleDiscoverySource([], self._name)

        for directory in self._directories:
            if not os.path.isdir(directory):
                continue
            for filepath in glob.glob(os.path.join(directory, self._pattern)):
                caps = module_source._scan_module(filepath)
                capabilities.extend(caps)

        return capabilities

    def source_name(self) -> str:
        return self._name


class CapabilityDiscoveryRegistry:
    """Registry that manages multiple discovery sources."""

    def __init__(self):
        self._sources: Dict[str, CapabilityDiscoverySource] = {}
        self._discovered: Dict[str, CapabilityMetadata] = {}
        self._errors: Dict[str, str] = {}

    def register_source(self, source: CapabilityDiscoverySource) -> None:
        """Register a discovery source."""
        self._sources[source.source_name()] = source

    def unregister_source(self, name: str) -> bool:
        """Unregister a discovery source."""
        if name in self._sources:
            del self._sources[name]
            return True
        return False

    def discover_all(self) -> List[CapabilityMetadata]:
        """Discover capabilities from all sources."""
        self._discovered.clear()
        self._errors.clear()

        for name, source in self._sources.items():
            try:
                capabilities = source.discover()
                for cap in capabilities:
                    # Set source to discovery source name if not already set
                    if cap.source == "unknown":
                        cap.source = name
                    self._discovered[cap.name] = cap
            except Exception as e:
                self._errors[name] = str(e)

        return list(self._discovered.values())

    def get_discovered(self) -> Dict[str, CapabilityMetadata]:
        """Get all discovered capabilities."""
        return dict(self._discovered)

    def get_capability(self, name: str) -> Optional[CapabilityMetadata]:
        """Get a specific discovered capability."""
        return self._discovered.get(name)

    def get_errors(self) -> Dict[str, str]:
        """Get any errors encountered during discovery."""
        return dict(self._errors)

    def get_sources(self) -> List[str]:
        """Get names of all registered sources."""
        return list(self._sources.keys())

    def filter_by_tag(self, tag: str) -> List[CapabilityMetadata]:
        """Filter discovered capabilities by tag."""
        return [c for c in self._discovered.values() if tag in c.tags]

    def filter_by_source(self, source: str) -> List[CapabilityMetadata]:
        """Filter discovered capabilities by source."""
        return [c for c in self._discovered.values() if c.source == source]


def discover_capabilities(
    sources: Optional[List[CapabilityDiscoverySource]] = None,
) -> List[CapabilityMetadata]:
    """Convenience function to discover capabilities."""
    registry = CapabilityDiscoveryRegistry()
    if sources:
        for source in sources:
            registry.register_source(source)
    return registry.discover_all()
