"""ARGUS Release Engineering - Artifact qualification and clean-room testing.

This package provides release engineering qualification for ARGUS, validating
build artifacts, clean installation, and release invariants.
"""

from argus.release.models import (
    ArtifactFile,
    ArtifactManifest,
    ArtifactStatus,
    ArtifactType,
    ArtifactValidationResult,
    CleanInstallationResult,
    ConcurrencyResult,
    ContaminationFinding,
    ContaminationScanResult,
    InvariantId,
    InvariantResult,
    InvariantStatus,
    ReleaseRun,
    SmokeTestResult,
    StabilityResult,
    VersionInfo,
)
from argus.release.artifacts import (
    calculate_sha256,
    find_artifacts,
    validate_sdist,
    validate_wheel,
    validate_all_artifacts,
)
from argus.release.metadata import (
    check_version_consistency,
    get_cli_version,
    get_metadata_version,
    get_package_version,
    validate_version,
)
from argus.release.cleanroom import (
    create_clean_venv,
    get_venv_pip,
    get_venv_python,
    install_wheel,
    test_clean_installation,
)
from argus.release.invariants import (
    ReleaseInvariantTester,
    run_release_invariants,
)
from argus.release.runner import (
    ReleaseRunner,
    run_release_qualification,
)
from argus.release.reporter import (
    ReleaseReporter,
    generate_release_report,
)

__all__ = [
    # Models
    "ArtifactFile",
    "ArtifactManifest",
    "ArtifactStatus",
    "ArtifactType",
    "ArtifactValidationResult",
    "CleanInstallationResult",
    "ConcurrencyResult",
    "ContaminationFinding",
    "ContaminationScanResult",
    "InvariantId",
    "InvariantResult",
    "InvariantStatus",
    "ReleaseRun",
    "SmokeTestResult",
    "StabilityResult",
    "VersionInfo",
    # Artifacts
    "calculate_sha256",
    "find_artifacts",
    "validate_sdist",
    "validate_wheel",
    "validate_all_artifacts",
    # Metadata
    "check_version_consistency",
    "get_cli_version",
    "get_metadata_version",
    "get_package_version",
    "validate_version",
    # Cleanroom
    "create_clean_venv",
    "get_venv_pip",
    "get_venv_python",
    "install_wheel",
    "test_clean_installation",
    # Invariants
    "ReleaseInvariantTester",
    "run_release_invariants",
    # Runner
    "ReleaseRunner",
    "run_release_qualification",
    # Reporter
    "ReleaseReporter",
    "generate_release_report",
]
