"""Reproducibility and artifact capture for benchmark experiments."""

import hashlib
import json
import os
import platform
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from argus.benchmark.models import (
    ArtifactManifest,
    ExperimentConfig,
    ReproducibilityRecord,
    TaskRunResult,
)


class ReproducibilityManager:
    """Manages reproducibility metadata for experiments."""

    def __init__(self):
        self._records: Dict[str, ReproducibilityRecord] = {}

    def create_record(
        self,
        config: ExperimentConfig,
        run_id: str,
        task_id: str,
    ) -> ReproducibilityRecord:
        """Create a reproducibility record for a run."""
        record = ReproducibilityRecord(
            experiment_id=config.experiment_id,
            run_id=run_id,
            task_id=task_id,
            benchmark_version=config.benchmark_version,
            argus_version=config.agent_version,
            argus_commit=self._get_git_commit(),
            provider=config.provider,
            model=config.model,
            configuration={
                "temperature": config.temperature,
                "features": config.features,
                "resource_limits": config.resource_limits,
            },
            random_seed=config.seed,
            timestamp=datetime.utcnow().isoformat(),
            python_version=sys.version,
            os_info=platform.platform(),
            dependency_versions=self._get_dependency_versions(),
            nondeterminism_sources=self._identify_nondeterminism(config),
        )

        self._records[run_id] = record
        return record

    def get_record(self, run_id: str) -> Optional[ReproducibilityRecord]:
        """Get a reproducibility record by run_id."""
        return self._records.get(run_id)

    def _get_git_commit(self) -> str:
        """Get current git commit hash."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    def _get_dependency_versions(self) -> Dict[str, str]:
        """Get versions of key dependencies."""
        versions = {}
        try:
            import importlib.metadata
            for pkg in ["pytest", "pydantic", "httpx"]:
                try:
                    versions[pkg] = importlib.metadata.version(pkg)
                except Exception:
                    versions[pkg] = "not installed"
        except Exception:
            pass
        return versions

    def _identify_nondeterminism(self, config: ExperimentConfig) -> List[str]:
        """Identify sources of nondeterminism."""
        sources = []

        if config.provider or config.model:
            sources.append("external_model_calls")

        if config.temperature and config.temperature > 0:
            sources.append("model_temperature")

        if not config.seed:
            sources.append("no_random_seed")

        return sources


class ArtifactCapture:
    """Captures and manages benchmark artifacts."""

    def __init__(self, output_dir: Optional[str] = None):
        self._output_dir = output_dir or "benchmark_artifacts"
        self._manifests: Dict[str, ArtifactManifest] = {}

    def capture_task_artifacts(
        self,
        experiment_id: str,
        run_id: str,
        task_id: str,
        artifacts: Dict[str, Any],
    ) -> ArtifactManifest:
        """Capture artifacts for a task run."""
        manifest = ArtifactManifest(
            experiment_id=experiment_id,
            run_id=run_id,
            task_id=task_id,
        )

        for name, content in artifacts.items():
            # Redact secrets before storing
            safe_content = self._redact_secrets(str(content))
            manifest.artifacts[name] = safe_content

        self._manifests[run_id] = manifest
        return manifest

    def get_manifest(self, run_id: str) -> Optional[ArtifactManifest]:
        """Get artifact manifest for a run."""
        return self._manifests.get(run_id)

    def _redact_secrets(self, content: str) -> str:
        """Redact potential secrets from content."""
        import re

        # Redact API keys
        content = re.sub(
            r"(sk-|api-|key-)[a-zA-Z0-9]{20,}",
            "***REDACTED***",
            content,
        )

        # Redact passwords
        content = re.sub(
            r"(password|passwd|pwd)\s*[:=]\s*\S+",
            r"\1=***REDACTED***",
            content,
            flags=re.IGNORECASE,
        )

        return content

    def save_artifacts(self, run_id: str, output_dir: Optional[str] = None) -> str:
        """Save artifacts to disk."""
        manifest = self._manifests.get(run_id)
        if not manifest:
            return ""

        dir_path = output_dir or self._output_dir
        run_dir = os.path.join(dir_path, manifest.experiment_id, run_id)
        os.makedirs(run_dir, exist_ok=True)

        for name, content in manifest.artifacts.items():
            file_path = os.path.join(run_dir, f"{name}.txt")
            with open(file_path, "w") as f:
                f.write(content)

        return run_dir


def compute_fingerprint(data: Any) -> str:
    """Compute a deterministic fingerprint for data."""
    content = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:16]
