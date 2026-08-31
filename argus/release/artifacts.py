"""Build artifact validation for ARGUS release qualification."""

import hashlib
import os
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from argus.release.models import (
    ArtifactFile,
    ArtifactManifest,
    ArtifactStatus,
    ArtifactType,
    ArtifactValidationResult,
)

# Required modules that must be present in the artifact
REQUIRED_MODULES = [
    "argus",
    "argus/cli.py",
    "argus/agent.py",
    "argus/config.py",
    "argus/repl.py",
    "argus/security",
    "argus/events",
    "argus/durable",
    "argus/recovery",
    "argus/state",
    "argus/validation",
    "argus/reality",
    "argus/release",
]

# Files that should NOT be in the artifact
FORBIDDEN_FILES = [
    ".env",
    ".gitignore",
    "credentials.json",
    "secrets.json",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
]

# Directories that should NOT be in the artifact
FORBIDDEN_DIRS = [
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
    ".idea",
    "__pycache__",
    "tests",
    "docs",
    "config",
    "logs",
]


def calculate_sha256(filepath: str) -> str:
    """Calculate SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_file_size(filepath: str) -> int:
    """Get file size in bytes."""
    return os.path.getsize(filepath)


def validate_wheel(wheel_path: str) -> ArtifactValidationResult:
    """Validate a wheel artifact."""
    result = ArtifactValidationResult(
        artifact_type=ArtifactType.WHEEL,
        artifact_path=wheel_path,
        status=ArtifactStatus.PENDING,
    )

    try:
        # Check file exists
        if not os.path.exists(wheel_path):
            result.status = ArtifactStatus.INVALID
            result.errors.append(f"Wheel not found: {wheel_path}")
            return result

        # Calculate hash and size
        result.sha256 = calculate_sha256(wheel_path)
        result.size = get_file_size(wheel_path)

        # Validate wheel contents
        manifest = ArtifactManifest(
            artifact_type=ArtifactType.WHEEL,
            artifact_path=wheel_path,
        )

        with zipfile.ZipFile(wheel_path, "r") as zf:
            for info in zf.infolist():
                # Add to manifest
                try:
                    content = zf.read(info.filename)
                    file_hash = hashlib.sha256(content).hexdigest()
                except Exception:
                    file_hash = ""

                manifest.files.append(ArtifactFile(
                    path=info.filename,
                    size=info.file_size,
                    sha256=file_hash,
                    is_directory=info.is_dir(),
                ))

            # Check required modules
            wheel_files = [f.filename for f in zf.infolist()]
            for required in REQUIRED_MODULES:
                # Check if any file starts with the required path
                found = any(f.startswith(required) for f in wheel_files)
                if not found:
                    result.warnings.append(f"Required module not found: {required}")

            # Check for forbidden files
            for f in wheel_files:
                for forbidden in FORBIDDEN_FILES:
                    if forbidden.startswith("*"):
                        if f.endswith(forbidden[1:]):
                            result.errors.append(f"Forbidden file type: {f}")
                    elif f.endswith(forbidden):
                        result.errors.append(f"Forbidden file: {f}")

            # Check for forbidden directories
            for f in wheel_files:
                for forbidden in FORBIDDEN_DIRS:
                    if f.startswith(forbidden + "/") or f"/{forbidden}/" in f:
                        result.warnings.append(f"Forbidden directory in artifact: {forbidden}")

        manifest.total_files = len(manifest.files)
        manifest.total_size = sum(f.size for f in manifest.files if not f.is_directory)
        result.manifest = manifest

        # Final status
        if result.errors:
            result.status = ArtifactStatus.INVALID
        else:
            result.status = ArtifactStatus.VALID

    except zipfile.BadZipFile:
        result.status = ArtifactStatus.INVALID
        result.errors.append("Invalid wheel file (bad zip)")
    except Exception as e:
        result.status = ArtifactStatus.ERROR
        result.errors.append(f"Error validating wheel: {e}")

    return result


def validate_sdist(sdist_path: str) -> ArtifactValidationResult:
    """Validate a sdist artifact."""
    result = ArtifactValidationResult(
        artifact_type=ArtifactType.SDIST,
        artifact_path=sdist_path,
        status=ArtifactStatus.PENDING,
    )

    try:
        if not os.path.exists(sdist_path):
            result.status = ArtifactStatus.INVALID
            result.errors.append(f"SDist not found: {sdist_path}")
            return result

        result.sha256 = calculate_sha256(sdist_path)
        result.size = get_file_size(sdist_path)

        # Basic validation - check it's a valid tar.gz
        import tarfile
        try:
            with tarfile.open(sdist_path, "r:gz") as tf:
                members = tf.getmembers()
                result.manifest = ArtifactManifest(
                    artifact_type=ArtifactType.SDIST,
                    artifact_path=sdist_path,
                )
                for member in members:
                    result.manifest.files.append(ArtifactFile(
                        path=member.name,
                        size=member.size,
                        sha256="",
                        is_directory=member.isdir(),
                    ))
                result.manifest.total_files = len(result.manifest.files)
                result.manifest.total_size = sum(
                    f.size for f in result.manifest.files if not f.is_directory
                )
        except tarfile.TarError as e:
            result.errors.append(f"Invalid sdist: {e}")

        if result.errors:
            result.status = ArtifactStatus.INVALID
        else:
            result.status = ArtifactStatus.VALID

    except Exception as e:
        result.status = ArtifactStatus.ERROR
        result.errors.append(f"Error validating sdist: {e}")

    return result


def find_artifacts(dist_dir: str) -> Dict[ArtifactType, str]:
    """Find build artifacts in the dist directory."""
    artifacts = {}
    dist_path = Path(dist_dir)

    if not dist_path.exists():
        return artifacts

    for f in dist_path.iterdir():
        if f.suffix == ".whl":
            artifacts[ArtifactType.WHEEL] = str(f)
        elif f.suffix == ".gz" and ".tar" in f.name:
            artifacts[ArtifactType.SDIST] = str(f)

    return artifacts


def validate_all_artifacts(dist_dir: str) -> Dict[str, ArtifactValidationResult]:
    """Validate all artifacts in the dist directory."""
    results = {}
    artifacts = find_artifacts(dist_dir)

    for artifact_type, path in artifacts.items():
        if artifact_type == ArtifactType.WHEEL:
            result = validate_wheel(path)
        elif artifact_type == ArtifactType.SDIST:
            result = validate_sdist(path)
        else:
            continue
        results[artifact_type.value] = result

    return results
