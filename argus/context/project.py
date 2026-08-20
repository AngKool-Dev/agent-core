"""Argus project context discovery."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ProjectContext:
    path: str
    name: str = ""
    language: str = ""
    files: List[str] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    readme: Optional[str] = None
    git_status: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "language": self.language,
            "files": self.files[:20],
            "config_files": self.config_files,
            "readme": self.readme[:500] if self.readme else None,
            "git_status": self.git_status,
        }


def discover_project_context(project_path: str, max_files: int = 50) -> ProjectContext:
    path = Path(project_path)
    if not path.exists():
        return ProjectContext(path=project_path, name="unknown", language="unknown")

    name = path.name
    language = _detect_language(path)
    files = _discover_files(path, max_files)
    config_files = _discover_config_files(path)
    readme = _discover_readme(path)
    git_status = _discover_git_status(path)

    return ProjectContext(
        path=str(path),
        name=name,
        language=language,
        files=files,
        config_files=config_files,
        readme=readme,
        git_status=git_status,
    )


def _detect_language(path: Path) -> str:
    indicators = {
        "python": ["pyproject.toml", "requirements.txt", "setup.py", "Pipfile", "poetry.lock"],
        "rust": ["Cargo.toml", "Cargo.lock"],
        "javascript": ["package.json", "package-lock.json", "yarn.lock"],
        "typescript": ["tsconfig.json"],
        "go": ["go.mod", "go.sum"],
        "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
        "ruby": ["Gemfile"],
        "php": ["composer.json"],
    }

    for lang, files in indicators.items():
        for f in files:
            if (path / f).exists():
                return lang
    return "unknown"


def _discover_files(path: Path, limit: int) -> List[str]:
    exclude = {
        ".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
        "dist", "build", ".tox", ".mypy_cache", ".ruff_cache", "unified_folder",
    }
    files = []
    for root, dirs, filenames in os.walk(path):
        dirs[:] = [d for d in dirs if d not in exclude]
        for f in filenames:
            full = Path(root) / f
            rel = full.relative_to(path)
            files.append(str(rel))
            if len(files) >= limit:
                return files
    return files


def _discover_config_files(path: Path) -> List[str]:
    config_patterns = [
        "*.toml", "*.yaml", "*.yml", "*.json", "*.ini", "*.cfg",
        "Makefile", "Dockerfile", ".env*",
    ]
    configs = []
    for pattern in config_patterns:
        for f in path.glob(f"**/{pattern}"):
            rel = f.relative_to(path)
            configs.append(str(rel))
    return sorted(configs)[:20]


def _discover_readme(path: Path) -> Optional[str]:
    for candidate in ["README.md", "README.rst", "README.txt", "readme.md"]:
        readme_path = path / candidate
        if readme_path.exists():
            try:
                return readme_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return None
    return None


def _discover_git_status(path: Path) -> Optional[Dict[str, Any]]:
    git_dir = path / ".git"
    if not git_dir.exists():
        return None

    try:
        import subprocess
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            branch = ""
            changes = []
            for line in lines:
                if line.startswith("##"):
                    branch = line[3:].strip()
                else:
                    changes.append(line.strip())
            return {"branch": branch, "changes": changes}
    except Exception:
        pass
    return None
