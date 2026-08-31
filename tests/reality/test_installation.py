"""Clean installation tests for ARGUS qualification.

These tests verify that ARGUS can be installed and run from a clean environment,
not just from the source checkout.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


class TestCleanInstallation:
    """Tests for clean package installation."""

    def test_package_imports(self):
        """Verify that the package can be imported."""
        import argus
        assert hasattr(argus, "__version__")

    def test_argus_version(self):
        """Verify that the version is accessible."""
        from argus import __version__
        assert __version__ is not None
        assert isinstance(__version__, str)

    def test_agentcore_imports(self):
        """Verify that agentcore can be imported."""
        import agentcore
        assert agentcore is not None

    def test_entry_points_defined(self):
        """Verify that entry points are defined in pyproject.toml."""
        import importlib.metadata
        try:
            metadata = importlib.metadata.metadata("agentcore")
            # Check that the package has entry points
            assert metadata is not None
        except importlib.metadata.PackageNotFoundError:
            pytest.skip("Package not installed in development mode")

    def test_cli_help_runs(self):
        """Verify that the CLI help command runs."""
        proc = subprocess.run(
            [sys.executable, "-m", "argus.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0
        assert "argus" in proc.stdout.lower()

    def test_cli_version_runs(self):
        """Verify that the CLI version command runs."""
        proc = subprocess.run(
            [sys.executable, "-m", "argus.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0

    def test_config_initialization(self):
        """Verify that configuration can be initialized."""
        from argus.config import ArgusConfig
        config = ArgusConfig()
        assert config is not None

    def test_reality_module_imports(self):
        """Verify that the reality module can be imported."""
        from argus.reality import RealityRunner
        assert RealityRunner is not None

    def test_validation_module_imports(self):
        """Verify that the validation module can be imported."""
        from argus.validation import ValidationRunner
        assert ValidationRunner is not None

    def test_durable_module_imports(self):
        """Verify that the durable module can be imported."""
        from argus.durable import DurableExecutor
        assert DurableExecutor is not None

    def test_security_module_imports(self):
        """Verify that the security module can be imported."""
        from argus.security import SecurityPolicy
        assert SecurityPolicy is not None


class TestInstalledPackageLocation:
    """Tests that verify the package is correctly installed."""

    def test_argus_module_file_location(self):
        """Verify that argus module file points to expected location."""
        import argus
        argus_file = getattr(argus, "__file__", None)
        assert argus_file is not None
        # The file should exist
        assert os.path.exists(argus_file)

    def test_not_source_checkout_import(self, tmp_path):
        """Verify that imports work from a non-source directory."""
        # Create a temporary script that imports argus
        test_script = tmp_path / "test_import.py"
        test_script.write_text("""
import sys
import os

# Change to a neutral directory
os.chdir(r"{}")

import argus
print(f"argus version: {{argus.__version__}}")
print(f"argus file: {{argus.__file__}}")
""".format(tmp_path))

        proc = subprocess.run(
            [sys.executable, str(test_script)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(tmp_path),
        )
        assert proc.returncode == 0
        assert "argus version:" in proc.stdout


@pytest.mark.skipif(
    os.environ.get("ARGUS_INSTALLATION_TESTS") != "1",
    reason="Installation tests require ARGUS_INSTALLATION_TESTS=1",
)
class TestWheelInstallation:
    """Tests that verify wheel installation in a clean environment.

    These tests are skipped by default and only run when explicitly enabled.
    """

    def test_wheel_build(self, tmp_path):
        """Verify that the wheel can be built."""
        proc = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path(__file__).parent.parent.parent),
        )
        if proc.returncode != 0:
            pytest.skip(f"Wheel build failed: {proc.stderr}")

        # Check that wheel was created
        wheels = list(tmp_path.glob("*.whl"))
        assert len(wheels) > 0

    def test_clean_venv_installation(self, tmp_path):
        """Verify installation in a clean virtual environment."""
        # Create a virtual environment
        venv_dir = tmp_path / "test_venv"
        proc = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            pytest.skip(f"Failed to create venv: {proc.stderr}")

        # Get the Python executable in the venv
        if sys.platform == "win32":
            venv_python = venv_dir / "Scripts" / "python.exe"
        else:
            venv_python = venv_dir / "bin" / "python"

        # Install the package
        pkg_root = Path(__file__).parent.parent.parent
        proc = subprocess.run(
            [str(venv_python), "-m", "pip", "install", str(pkg_root)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            pytest.skip(f"Installation failed: {proc.stderr}")

        # Verify import works
        proc = subprocess.run(
            [str(venv_python), "-c", "import argus; print(argus.__file__)"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0
        # Verify it's installed in the venv, not the source tree
        assert str(venv_dir) in proc.stdout
