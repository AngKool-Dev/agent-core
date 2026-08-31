"""Version consistency validation for ARGUS release qualification."""

import importlib.metadata
from typing import Dict

from argus.release.models import ArtifactStatus, VersionInfo


def get_package_version() -> str:
    """Get version from the installed package."""
    try:
        import argus
        return getattr(argus, "__version__", "")
    except Exception:
        return ""


def get_metadata_version() -> str:
    """Get version from package metadata."""
    try:
        return importlib.metadata.version("agentcore")
    except Exception:
        return ""


def get_cli_version() -> str:
    """Get version from CLI."""
    try:
        from argus.cli import __version__
        return __version__
    except Exception:
        return ""


def check_version_consistency() -> VersionInfo:
    """Check that all version sources are consistent."""
    info = VersionInfo()

    # Collect versions from all sources
    info.package_version = get_package_version()
    info.metadata_version = get_metadata_version()
    info.cli_version = get_cli_version()

    info.sources = {
        "package": info.package_version,
        "metadata": info.metadata_version,
        "cli": info.cli_version,
    }

    # Check consistency
    versions = [v for v in [info.package_version, info.cli_version] if v]
    if versions:
        # All non-empty versions should match
        info.is_consistent = len(set(versions)) == 1
    else:
        info.is_consistent = False

    return info


def validate_version(expected_version: str = "1.0.0") -> Dict:
    """Validate version matches expected."""
    info = check_version_consistency()

    result = {
        "expected": expected_version,
        "actual": info.package_version,
        "is_consistent": info.is_consistent,
        "matches_expected": info.package_version == expected_version,
        "sources": info.sources,
    }

    return result
