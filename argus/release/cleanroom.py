"""Clean installation testing for ARGUS release qualification."""

import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Optional

from argus.release.models import ArtifactStatus, CleanInstallationResult


def create_clean_venv(base_dir: str) -> Optional[str]:
    """Create a clean virtual environment."""
    venv_dir = os.path.join(base_dir, "test_venv")
    try:
        import venv
        venv.create(venv_dir, with_pip=True)
        return venv_dir
    except Exception:
        return None


def get_venv_python(venv_dir: str) -> str:
    """Get the Python executable in a venv."""
    if sys.platform == "win32":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def get_venv_pip(venv_dir: str) -> str:
    """Get the pip executable in a venv."""
    if sys.platform == "win32":
        return os.path.join(venv_dir, "Scripts", "pip.exe")
    return os.path.join(venv_dir, "bin", "pip")


def install_wheel(venv_dir: str, wheel_path: str) -> bool:
    """Install a wheel into a venv."""
    pip = get_venv_pip(venv_dir)
    try:
        result = subprocess.run(
            [pip, "install", wheel_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except Exception:
        return False


def test_clean_installation(wheel_path: str, base_dir: str) -> CleanInstallationResult:
    """Test clean installation of ARGUS."""
    result = CleanInstallationResult(
        status=ArtifactStatus.PENDING,
    )

    try:
        # Create clean venv
        venv_dir = create_clean_venv(base_dir)
        if not venv_dir:
            result.status = ArtifactStatus.ERROR
            result.errors.append("Failed to create clean venv")
            return result

        result.venv_path = venv_dir

        # Install wheel
        if not install_wheel(venv_dir, wheel_path):
            result.status = ArtifactStatus.INVALID
            result.errors.append("Failed to install wheel")
            return result

        # Get Python executable
        python = get_venv_python(venv_dir)

        # Test import
        proc = subprocess.run(
            [python, "-c", "import argus; print(argus.__file__)"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            result.import_path = proc.stdout.strip()
            # Verify import is from venv, not source tree
            if venv_dir in result.import_path:
                result.metadata["import_from_venv"] = True
            else:
                result.errors.append(f"Import not from venv: {result.import_path}")
        else:
            result.errors.append(f"Import failed: {proc.stderr}")

        # Test CLI version
        proc = subprocess.run(
            [python, "-m", "argus.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        result.version_works = proc.returncode == 0

        # Test CLI help
        proc = subprocess.run(
            [python, "-m", "argus.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        result.help_works = proc.returncode == 0

        # Test neutral directory execution
        neutral_dir = os.path.join(base_dir, "neutral")
        os.makedirs(neutral_dir, exist_ok=True)
        proc = subprocess.run(
            [python, "-m", "argus.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=neutral_dir,
        )
        result.neutral_dir_works = proc.returncode == 0
        result.cli_works = result.version_works and result.help_works

        # Final status
        if result.errors:
            result.status = ArtifactStatus.INVALID
        elif result.cli_works and result.metadata.get("import_from_venv"):
            result.status = ArtifactStatus.VALID
        else:
            result.status = ArtifactStatus.INVALID

    except Exception as e:
        result.status = ArtifactStatus.ERROR
        result.errors.append(f"Error during clean installation test: {e}")

    return result
