"""Post-release metadata consistency tests.

Verifies POSTREL-001 and POSTREL-002 invariants.
"""

import importlib.metadata
import re
from pathlib import Path

import pytest


class TestVersionConsistency:
    """POSTREL-001: Every authoritative version source resolves to 1.0.0."""

    def test_package_version(self):
        """Package __version__ is 1.0.0."""
        from argus import __version__
        assert __version__ == "1.0.0", f"Package version is {__version__}, expected 1.0.0"

    def test_pyproject_version(self):
        """pyproject.toml version is 1.0.0."""
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        assert match is not None, "version not found in pyproject.toml"
        assert match.group(1) == "1.0.0", f"pyproject.toml version is {match.group(1)}, expected 1.0.0"

    def test_cli_version(self):
        """CLI --version reports 1.0.0."""
        import subprocess
        import sys
        proc = subprocess.run(
            [sys.executable, "-m", "argus.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"CLI version failed: {proc.stderr}"
        assert "1.0.0" in proc.stdout, f"CLI version output: {proc.stdout}"

    def test_release_metadata_version(self):
        """Release metadata version is 1.0.0."""
        from argus.release.metadata import check_version_consistency
        info = check_version_consistency()
        assert info.is_consistent, f"Version sources inconsistent: {info.sources}"
        assert info.package_version == "1.0.0"

    def test_release_reporter_version(self):
        """Release reporter generates 1.0.0 reports."""
        from argus.release.reporter import ReleaseReporter
        from argus.release.models import ReleaseRun
        reporter = ReleaseReporter()
        run = ReleaseRun()
        report = reporter.generate_text_report(run)
        assert "ARGUS 1.0.0" in report

    def test_reality_reporter_version(self):
        """Reality reporter generates 1.0.0 reports."""
        from argus.reality.reporter import RealityReporter
        from argus.reality.models import RealityRun
        reporter = RealityReporter()
        run = RealityRun()
        report = reporter.generate_text_report(run)
        assert "ARGUS 1.0.0" in report

    def test_release_run_default_version(self):
        """ReleaseRun default version is 1.0.0."""
        from argus.release.models import ReleaseRun
        run = ReleaseRun()
        assert run.version == "1.0.0", f"ReleaseRun default version is {run.version}"

    def test_release_decision_default_version(self):
        """ReleaseDecision default version is 1.0.0."""
        from argus.reality.models import ReleaseDecision
        decision = ReleaseDecision()
        assert decision.version == "1.0.0", f"ReleaseDecision default version is {decision.version}"


class TestArtifactMetadata:
    """POSTREL-002: Published artifact metadata matches the source release version."""

    def test_wheel_version_matches(self):
        """Wheel filename contains 1.0.0."""
        dist_dir = Path(__file__).parent.parent / "dist"
        if not dist_dir.exists():
            pytest.skip("dist/ directory does not exist")
        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) > 0, "No wheel found in dist/"
        for wheel in wheels:
            assert "1.0.0" in wheel.name, f"Wheel name {wheel.name} does not contain 1.0.0"

    def test_sdist_version_matches(self):
        """Sdist filename contains 1.0.0."""
        dist_dir = Path(__file__).parent.parent / "dist"
        if not dist_dir.exists():
            pytest.skip("dist/ directory does not exist")
        sdists = list(dist_dir.glob("*.tar.gz"))
        assert len(sdists) > 0, "No sdist found in dist/"
        for sdist in sdists:
            assert "1.0.0" in sdist.name, f"Sdist name {sdist.name} does not contain 1.0.0"

    def test_sha256sums_exists(self):
        """SHA256SUMS file exists in dist/."""
        dist_dir = Path(__file__).parent.parent / "dist"
        if not dist_dir.exists():
            pytest.skip("dist/ directory does not exist")
        sha256sums = dist_dir / "SHA256SUMS"
        assert sha256sums.exists(), "SHA256SUMS file not found in dist/"

    def test_release_manifest_exists(self):
        """RELEASE_MANIFEST.json exists in dist/."""
        dist_dir = Path(__file__).parent.parent / "dist"
        if not dist_dir.exists():
            pytest.skip("dist/ directory does not exist")
        manifest = dist_dir / "RELEASE_MANIFEST.json"
        assert manifest.exists(), "RELEASE_MANIFEST.json not found in dist/"

    def test_release_manifest_version(self):
        """RELEASE_MANIFEST.json version is 1.0.0."""
        import json
        dist_dir = Path(__file__).parent.parent / "dist"
        manifest_path = dist_dir / "RELEASE_MANIFEST.json"
        if not manifest_path.exists():
            pytest.skip("RELEASE_MANIFEST.json does not exist")
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert manifest.get("version") == "1.0.0", f"Manifest version is {manifest.get('version')}"
