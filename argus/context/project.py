"""Argus project context discovery."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ProjectProfile:
    root: str
    name: str = ""
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    build_system: Optional[str] = None
    package_manager: Optional[str] = None
    test_system: Optional[str] = None
    test_command: Optional[str] = None
    formatter_command: Optional[str] = None
    linter_command: Optional[str] = None
    git_repository: bool = False
    git_branch: str = ""
    git_clean: bool = True
    configuration_files: List[str] = field(default_factory=list)
    conventions: List[str] = field(default_factory=list)
    readme: Optional[str] = None

    @property
    def path(self) -> str:
        return self.root

    @property
    def language(self) -> str:
        return self.languages[0] if self.languages else "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": self.root,
            "name": self.name,
            "languages": self.languages,
            "frameworks": self.frameworks,
            "build_system": self.build_system,
            "package_manager": self.package_manager,
            "test_system": self.test_system,
            "test_command": self.test_command,
            "formatter_command": self.formatter_command,
            "linter_command": self.linter_command,
            "git_repository": self.git_repository,
            "git_branch": self.git_branch,
            "git_clean": self.git_clean,
            "configuration_files": self.configuration_files,
            "conventions": self.conventions,
            "readme": self.readme[:500] if self.readme else None,
        }

    def to_context(self) -> str:
        lines = [
            f"Project: {self.name or self.root}",
            f"Path: {self.root}",
        ]
        if self.languages:
            lines.append(f"Languages: {', '.join(self.languages)}")
        if self.frameworks:
            lines.append(f"Frameworks: {', '.join(self.frameworks)}")
        if self.build_system:
            lines.append(f"Build system: {self.build_system}")
        if self.package_manager:
            lines.append(f"Package manager: {self.package_manager}")
        if self.test_system:
            lines.append(f"Test system: {self.test_system}")
        if self.test_command:
            lines.append(f"Test command: {self.test_command}")
        if self.formatter_command:
            lines.append(f"Formatter: {self.formatter_command}")
        if self.linter_command:
            lines.append(f"Linter: {self.linter_command}")
        if self.git_repository:
            status = "clean" if self.git_clean else "dirty"
            lines.append(f"Git: {self.git_branch or 'unknown'} ({status})")
        if self.conventions:
            lines.append(f"Conventions: {', '.join(self.conventions)}")
        return "\n".join(lines)


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


def discover_project_context(project_path: str, max_files: int = 50) -> ProjectProfile:
    path = Path(project_path)
    if not path.exists():
        return ProjectProfile(root=project_path, name="unknown")

    name = path.name
    readme = _discover_readme(path)
    config_files = _discover_config_files(path)
    languages, frameworks = _detect_ecosystems(path, config_files)
    build_system, package_manager = _detect_build_package(path, languages, config_files)
    test_system, test_command = _detect_testing(path, languages, config_files)
    formatter_command = _detect_formatter(path, languages, config_files)
    linter_command = _detect_linter(path, languages, config_files)
    git_branch, git_clean, is_git = _detect_git(path)
    conventions = _detect_conventions(path, config_files)

    return ProjectProfile(
        root=str(path.resolve()),
        name=name,
        languages=languages,
        frameworks=frameworks,
        build_system=build_system,
        package_manager=package_manager,
        test_system=test_system,
        test_command=test_command,
        formatter_command=formatter_command,
        linter_command=linter_command,
        git_repository=is_git,
        git_branch=git_branch,
        git_clean=git_clean,
        configuration_files=config_files[:20],
        conventions=conventions,
        readme=readme,
    )


def _detect_ecosystems(path: Path, config_files: List[str]) -> Tuple[List[str], List[str]]:
    languages: List[str] = []
    frameworks: List[str] = []

    if (path / "Cargo.toml").exists() or (path / "Cargo.lock").exists():
        languages.append("rust")
        frameworks.extend(_detect_rust_frameworks(path))

    if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists() or (path / "setup.py").exists():
        languages.append("python")
        frameworks.extend(_detect_python_frameworks(path))

    if (path / "package.json").exists():
        languages.append("javascript")
        frameworks.extend(_detect_node_frameworks(path))
        if (path / "tsconfig.json").exists():
            languages.append("typescript")

    if (path / "go.mod").exists() or (path / "go.sum").exists():
        languages.append("go")

    if (path / "pom.xml").exists():
        languages.append("java")
        frameworks.append("maven")
    elif any((path / f).exists() for f in ["build.gradle", "build.gradle.kts"]):
        languages.append("java")
        frameworks.append("gradle")

    return languages, frameworks


def _detect_rust_frameworks(path: Path) -> List[str]:
    frameworks: List[str] = []
    cargo = path / "Cargo.toml"
    if not cargo.exists():
        return frameworks
    try:
        text = cargo.read_text(encoding="utf-8", errors="ignore")
        for name in ["actix-web", "axum", "rocket", "tokio", "serde", "reqwest", "tower"]:
            if name in text:
                frameworks.append(name)
    except Exception:
        pass
    return frameworks


def _detect_python_frameworks(path: Path) -> List[str]:
    frameworks: List[str] = []
    for candidate in ["requirements.txt", "pyproject.toml"]:
        target = path / candidate
        if not target.exists():
            continue
        try:
            text = target.read_text(encoding="utf-8", errors="ignore").lower()
            for name in ["django", "flask", "fastapi", "pytest", "sqlalchemy", "celery", "uvicorn"]:
                if name in text:
                    frameworks.append(name)
        except Exception:
            pass
    return frameworks


def _detect_node_frameworks(path: Path) -> List[str]:
    frameworks: List[str] = []
    package = path / "package.json"
    if not package.exists():
        return frameworks
    try:
        data = json.loads(package.read_text(encoding="utf-8", errors="ignore"))
        deps = {}
        for key in ["dependencies", "devDependencies", "peerDependencies"]:
            deps.update(data.get(key, {}))
        for name in ["react", "vue", "angular", "express", "next", "vite", "jest", "mocha", "typescript"]:
            if name in deps:
                frameworks.append(name)
    except Exception:
        pass
    return frameworks


def _detect_build_package(path: Path, languages: List[str], config_files: List[str]) -> Tuple[Optional[str], Optional[str]]:
    build_system: Optional[str] = None
    package_manager: Optional[str] = None

    if "rust" in languages:
        build_system = "cargo"
        package_manager = "cargo"

    if "python" in languages:
        if (path / "pyproject.toml").exists():
            build_system = "pyproject"
            try:
                text = (path / "pyproject.toml").read_text(encoding="utf-8", errors="ignore").lower()
                if "poetry" in text:
                    package_manager = "poetry"
                elif "flit" in text:
                    package_manager = "flit"
                else:
                    package_manager = "pip"
            except Exception:
                package_manager = "pip"
        elif (path / "requirements.txt").exists():
            build_system = "requirements"
            package_manager = "pip"
        elif (path / "setup.py").exists():
            build_system = "setuptools"
            package_manager = "pip"

    if "javascript" in languages or "typescript" in languages:
        if (path / "package.json").exists():
            build_system = "npm"
            if (path / "yarn.lock").exists():
                package_manager = "yarn"
            elif (path / "pnpm-lock.yaml").exists():
                package_manager = "pnpm"
            elif (path / "package-lock.json").exists():
                package_manager = "npm"

    if "go" in languages:
        build_system = "go"
        package_manager = "go modules"

    if "java" in languages:
        if (path / "pom.xml").exists():
            build_system = "maven"
        elif any((path / f).exists() for f in ["build.gradle", "build.gradle.kts"]):
            build_system = "gradle"

    return build_system, package_manager


def _detect_testing(path: Path, languages: List[str], config_files: List[str]) -> Tuple[Optional[str], Optional[str]]:
    test_system: Optional[str] = None
    test_command: Optional[str] = None

    if "rust" in languages:
        test_system = "cargo test"
        test_command = "cargo test"

    if "python" in languages:
        if (path / "pytest.ini").exists() or any("pytest" in f for f in config_files):
            test_system = "pytest"
            test_command = "pytest"
        elif (path / "tox.ini").exists():
            test_system = "tox"
            test_command = "tox"
        elif (path / "pyproject.toml").exists():
            test_system = "pytest"
            test_command = "python -m pytest"
        else:
            test_system = "unittest"
            test_command = "python -m unittest discover"

    if "javascript" in languages or "typescript" in languages:
        package = path / "package.json"
        if package.exists():
            try:
                data = json.loads(package.read_text(encoding="utf-8", errors="ignore"))
                scripts = data.get("scripts", {})
                if "test" in scripts:
                    test_system = "npm test"
                    test_command = scripts["test"]
                else:
                    test_system = "unknown"
                    test_command = None
            except Exception:
                pass
        else:
            test_system = "unknown"
            test_command = None

    if "go" in languages:
        test_system = "go test"
        test_command = "go test ./..."

    if "java" in languages:
        if (path / "pom.xml").exists():
            test_system = "maven test"
            test_command = "mvn test"
        elif any((path / f).exists() for f in ["build.gradle", "build.gradle.kts"]):
            test_system = "gradle test"
            test_command = "./gradlew test"

    return test_system, test_command


def _detect_formatter(path: Path, languages: List[str], config_files: List[str]) -> Optional[str]:
    if "rust" in languages:
        return "cargo fmt"
    if "python" in languages:
        if any("black" in f for f in config_files) or (path / "pyproject.toml").exists():
            return "black"
        return None
    if "javascript" in languages or "typescript" in languages:
        if any("prettier" in f for f in config_files) or (path / "package.json").exists():
            try:
                data = json.loads((path / "package.json").read_text(encoding="utf-8", errors="ignore"))
                if "prettier" in data.get("devDependencies", {}) or "prettier" in data.get("dependencies", {}):
                    return "prettier"
            except Exception:
                pass
        return None
    if "go" in languages:
        return "gofmt"
    return None


def _detect_linter(path: Path, languages: List[str], config_files: List[str]) -> Optional[str]:
    if "rust" in languages:
        return "cargo clippy"
    if "python" in languages:
        if any("ruff" in f for f in config_files):
            return "ruff"
        if any("flake8" in f for f in config_files):
            return "flake8"
        if (path / "pyproject.toml").exists():
            return "ruff"
        return None
    if "javascript" in languages or "typescript" in languages:
        if any("eslint" in f for f in config_files):
            return "eslint"
        if (path / "package.json").exists():
            try:
                data = json.loads((path / "package.json").read_text(encoding="utf-8", errors="ignore"))
                if "eslint" in data.get("devDependencies", {}) or "eslint" in data.get("dependencies", {}):
                    return "eslint"
            except Exception:
                pass
        return None
    if "go" in languages:
        return "go vet"
    return None


def _detect_git(path: Path) -> Tuple[str, bool, bool]:
    git_dir = path / ".git"
    if not git_dir.exists():
        return "", True, False

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
            branch = ""
            clean = True
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("##"):
                    branch = line[3:].strip()
                elif line:
                    clean = False
            return branch, clean, True
    except Exception:
        pass
    return "", True, False


def _detect_conventions(path: Path, config_files: List[str]) -> List[str]:
    conventions: List[str] = []
    if any(f == ".editorconfig" for f in config_files):
        conventions.append("editorconfig")
    if any(f.startswith(".pre-commit") for f in config_files):
        conventions.append("pre-commit")
    if any(f.startswith("rustfmt") for f in config_files):
        conventions.append("rustfmt")
    if any(f.startswith(".clang-format") for f in config_files):
        conventions.append("clang-format")
    if any(f.startswith("pyproject.toml") for f in config_files):
        conventions.append("pyproject")
    if any(f.startswith(".eslintrc") for f in config_files):
        conventions.append("eslint")
    if any(f.startswith(".prettierrc") for f in config_files) or any(f == ".prettierrc" for f in config_files):
        conventions.append("prettier")
    return conventions


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
            try:
                rel = full.relative_to(path)
                files.append(str(rel))
            except ValueError:
                pass
            if len(files) >= limit:
                return files
    return files


def _discover_config_files(path: Path) -> List[str]:
    exclude = {
        ".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
        "dist", "build", ".tox", ".mypy_cache", ".ruff_cache", "unified_folder",
    }
    config_patterns = [
        "*.toml", "*.yaml", "*.yml", "*.json", "*.ini", "*.cfg",
        "Makefile", "Dockerfile", ".env*", ".editorconfig",
    ]
    configs = []
    for root, dirs, filenames in os.walk(path):
        dirs[:] = [d for d in dirs if d not in exclude]
        for f in filenames:
            for pattern in config_patterns:
                if Path(f).match(pattern):
                    full = Path(root) / f
                    try:
                        rel = full.relative_to(path)
                        configs.append(str(rel))
                    except ValueError:
                        pass
                    break
            if len(configs) >= 50:
                return sorted(configs)[:20]
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
