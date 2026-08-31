"""Release data models for ARGUS release qualification."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ArtifactType(Enum):
    """Types of release artifacts."""
    WHEEL = "wheel"
    SDIST = "sdist"
    EGG_INFO = "egg_info"


class ArtifactStatus(Enum):
    """Status of artifact validation."""
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    ERROR = "error"
    SKIPPED = "skipped"


class InvariantId(Enum):
    """Release invariant identifiers."""
    REL_001 = "rel_001"
    REL_002 = "rel_002"
    REL_003 = "rel_003"
    REL_004 = "rel_004"
    REL_005 = "rel_005"
    REL_006 = "rel_006"
    REL_007 = "rel_007"
    REL_008 = "rel_008"
    REL_009 = "rel_009"
    REL_010 = "rel_010"
    REL_011 = "rel_011"
    REL_012 = "rel_012"
    REL_013 = "rel_013"
    REL_014 = "rel_014"
    REL_015 = "rel_015"
    REL_016 = "rel_016"
    REL_017 = "rel_017"
    REL_018 = "rel_018"
    REL_019 = "rel_019"
    REL_020 = "rel_020"


class InvariantStatus(Enum):
    """Status of an invariant check."""
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    INCONCLUSIVE = "inconclusive"


@dataclass
class ArtifactFile:
    """A file within a release artifact."""
    path: str
    size: int
    sha256: str
    is_directory: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "size": self.size,
            "sha256": self.sha256,
            "is_directory": self.is_directory,
        }


@dataclass
class ArtifactManifest:
    """Manifest of files in a release artifact."""
    artifact_type: ArtifactType
    artifact_path: str
    files: List[ArtifactFile] = field(default_factory=list)
    total_size: int = 0
    total_files: int = 0
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact_type.value,
            "artifact_path": self.artifact_path,
            "files": [f.to_dict() for f in self.files],
            "total_size": self.total_size,
            "total_files": self.total_files,
            "generated_at": self.generated_at,
        }


@dataclass
class ArtifactValidationResult:
    """Result of artifact validation."""
    artifact_type: ArtifactType
    artifact_path: str
    status: ArtifactStatus
    sha256: str = ""
    size: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    manifest: Optional[ArtifactManifest] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    validated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact_type.value,
            "artifact_path": self.artifact_path,
            "status": self.status.value,
            "sha256": self.sha256,
            "size": self.size,
            "errors": self.errors,
            "warnings": self.warnings,
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "metadata": self.metadata,
            "validated_at": self.validated_at,
        }


@dataclass
class VersionInfo:
    """Version information from various sources."""
    package_version: str = ""
    cli_version: str = ""
    wheel_version: str = ""
    sdist_version: str = ""
    metadata_version: str = ""
    is_consistent: bool = False
    sources: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_version": self.package_version,
            "cli_version": self.cli_version,
            "wheel_version": self.wheel_version,
            "sdist_version": self.sdist_version,
            "metadata_version": self.metadata_version,
            "is_consistent": self.is_consistent,
            "sources": self.sources,
        }


@dataclass
class CleanInstallationResult:
    """Result of clean installation test."""
    status: ArtifactStatus
    venv_path: str = ""
    install_path: str = ""
    import_path: str = ""
    cli_works: bool = False
    version_works: bool = False
    help_works: bool = False
    neutral_dir_works: bool = False
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tested_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "venv_path": self.venv_path,
            "install_path": self.install_path,
            "import_path": self.import_path,
            "cli_works": self.cli_works,
            "version_works": self.version_works,
            "help_works": self.help_works,
            "neutral_dir_works": self.neutral_dir_works,
            "errors": self.errors,
            "metadata": self.metadata,
            "tested_at": self.tested_at,
        }


@dataclass
class ContaminationFinding:
    """A finding from contamination scanning."""
    file_path: str
    finding_type: str
    description: str
    severity: str = "warning"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "finding_type": self.finding_type,
            "description": self.description,
            "severity": self.severity,
        }


@dataclass
class ContaminationScanResult:
    """Result of contamination scanning."""
    status: ArtifactStatus
    findings: List[ContaminationFinding] = field(default_factory=list)
    files_scanned: int = 0
    canary_found: bool = False
    canary_locations: List[str] = field(default_factory=list)
    scanned_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "findings": [f.to_dict() for f in self.findings],
            "files_scanned": self.files_scanned,
            "canary_found": self.canary_found,
            "canary_locations": self.canary_locations,
            "scanned_at": self.scanned_at,
        }


@dataclass
class SmokeTestResult:
    """Result of a smoke test."""
    test_name: str
    status: ArtifactStatus
    command: str = ""
    return_code: int = -1
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "status": self.status.value,
            "command": self.command,
            "return_code": self.return_code,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
        }


@dataclass
class StabilityResult:
    """Result of stability testing."""
    status: ArtifactStatus
    iterations: int = 0
    duration_seconds: float = 0.0
    memory_samples: List[float] = field(default_factory=list)
    thread_samples: List[int] = field(default_factory=list)
    event_counts: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "iterations": self.iterations,
            "duration_seconds": self.duration_seconds,
            "memory_samples": self.memory_samples,
            "thread_samples": self.thread_samples,
            "event_counts": self.event_counts,
            "errors": self.errors,
            "metadata": self.metadata,
        }


@dataclass
class ConcurrencyResult:
    """Result of concurrency testing."""
    status: ArtifactStatus
    num_runs: int = 0
    run_ids: List[str] = field(default_factory=list)
    isolated_state: bool = True
    isolated_events: bool = True
    isolated_journals: bool = True
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "num_runs": self.num_runs,
            "run_ids": self.run_ids,
            "isolated_state": self.isolated_state,
            "isolated_events": self.isolated_events,
            "isolated_journals": self.isolated_journals,
            "errors": self.errors,
            "metadata": self.metadata,
        }


@dataclass
class InvariantResult:
    """Result of a release invariant check."""
    invariant_id: InvariantId
    description: str
    status: InvariantStatus = InvariantStatus.SKIPPED
    evidence: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invariant_id": self.invariant_id.value,
            "description": self.description,
            "status": self.status.value,
            "evidence": self.evidence,
            "metadata": self.metadata,
            "checked_at": self.checked_at,
        }


@dataclass
class ReleaseRun:
    """A complete release qualification run."""
    run_id: str = field(default_factory=lambda: f"release-{uuid.uuid4().hex[:8]}")
    version: str = "1.0.0"
    artifact_results: Dict[str, ArtifactValidationResult] = field(default_factory=dict)
    version_info: Optional[VersionInfo] = None
    clean_install: Optional[CleanInstallationResult] = None
    contamination: Optional[ContaminationScanResult] = None
    smoke_results: List[SmokeTestResult] = field(default_factory=list)
    stability: Optional[StabilityResult] = None
    concurrency: Optional[ConcurrencyResult] = None
    invariant_results: Dict[str, InvariantResult] = field(default_factory=dict)
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    inconclusive: int = 0
    total_duration: float = 0.0
    started_at: str = ""
    completed_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        if self.total_checks == 0:
            return 0.0
        return self.passed / self.total_checks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "version": self.version,
            "artifact_results": {k: v.to_dict() for k, v in self.artifact_results.items()},
            "version_info": self.version_info.to_dict() if self.version_info else None,
            "clean_install": self.clean_install.to_dict() if self.clean_install else None,
            "contamination": self.contamination.to_dict() if self.contamination else None,
            "smoke_results": [s.to_dict() for s in self.smoke_results],
            "stability": self.stability.to_dict() if self.stability else None,
            "concurrency": self.concurrency.to_dict() if self.concurrency else None,
            "invariant_results": {k: v.to_dict() for k, v in self.invariant_results.items()},
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "inconclusive": self.inconclusive,
            "total_duration": self.total_duration,
            "pass_rate": self.pass_rate,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }
