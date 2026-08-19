import subprocess
from pathlib import Path
from typing import Any


class ProjectContext:
    def __init__(self, project_path: str | Path | None = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self._context: dict[str, Any] = {}

    def discover(self) -> dict[str, Any]:
        self._context = {
            "project_root": str(self.project_path),
            "language": self._detect_language(),
            "framework": self._detect_framework(),
            "build_system": self._detect_build_system(),
            "package_manager": self._detect_package_manager(),
            "git_status": self._get_git_status(),
            "git_diff": self._get_git_diff(),
            "config_files": self._find_config_files(),
            "test_files": self._find_test_files(),
            "readme": self._find_readme(),
            "documentation": self._find_documentation(),
        }
        return self._context

    def _detect_language(self) -> str | None:
        markers = {
            "rust": ["Cargo.toml", "rust-toolchain"],
            "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
            "typescript": ["tsconfig.json", "package.json"],
            "javascript": ["package.json", "jsconfig.json"],
            "go": ["go.mod", "go.sum"],
            "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
            "c": ["Makefile", "CMakeLists.txt"],
            "cpp": ["CMakeLists.txt", "Makefile", ".clang-format"],
        }

        for lang, files in markers.items():
            for f in files:
                if (self.project_path / f).exists():
                    return lang
        return None

    def _detect_framework(self) -> str | None:
        framework_markers = {
            "react": ["package.json", "src/index.tsx", "src/index.jsx"],
            "next.js": ["package.json", "next.config.js", "pages/_app.tsx"],
            "vue": ["package.json", "vue.config.js", "src/main.ts"],
            "angular": ["angular.json", "src/main.ts"],
            "fastapi": ["main.py", "app.py"],
            "flask": ["app.py", "main.py"],
            "django": ["manage.py", "settings.py"],
            "spring": ["pom.xml", "build.gradle"],
            "rails": ["Gemfile", "config/application.rb"],
            "express": ["app.js", "server.js"],
        }

        for framework, files in framework_markers.items():
            for f in files:
                if (self.project_path / f).exists():
                    return framework
        return None

    def _detect_build_system(self) -> str | None:
        build_markers = {
            "cargo": ["Cargo.toml"],
            "make": ["Makefile"],
            "cmake": ["CMakeLists.txt"],
            "gradle": ["build.gradle", "build.gradle.kts"],
            "maven": ["pom.xml"],
            "npm": ["package.json"],
            "pip": ["pyproject.toml", "setup.py", "requirements.txt"],
        }

        for system, files in build_markers.items():
            for f in files:
                if (self.project_path / f).exists():
                    return system
        return None

    def _detect_package_manager(self) -> str | None:
        if (self.project_path / "Cargo.toml").exists():
            return "cargo"
        if (self.project_path / "requirements.txt").exists():
            return "pip"
        if (self.project_path / "package-lock.json").exists():
            return "npm"
        if (self.project_path / "yarn.lock").exists():
            return "yarn"
        if (self.project_path / "pyproject.toml").exists():
            return "pip/poetry"
        return None

    def _get_git_status(self) -> dict[str, Any]:
        if not (self.project_path / ".git").exists():
            return {"is_git_repo": False}

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = [line for line in result.stdout.strip().split("\n") if line]
            return {
                "is_git_repo": True,
                "changed_files": len(lines),
                "staged": len(
                    [line for line in lines if line.startswith("M") or line.startswith("A")]
                ),
                "unstaged": len([line for line in lines if line.startswith(" M")]),
            }
        except Exception:
            return {"is_git_repo": True, "error": "Could not read git status"}

    def _get_git_diff(self) -> str:
        if not (self.project_path / ".git").exists():
            return ""

        try:
            result = subprocess.run(
                ["git", "diff", "--check"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout + result.stderr
        except Exception:
            return "Could not read git diff"

    def _find_config_files(self) -> list[str]:
        patterns = ["*.toml", "*.yaml", "*.yml", "*.json", "*.cfg", "*.ini", "*.env"]
        configs = []
        for pattern in patterns:
            for f in self.project_path.rglob(pattern):
                if ".git" not in str(f) and "node_modules" not in str(f):
                    configs.append(str(f.relative_to(self.project_path)))
                    if len(configs) >= 20:
                        return configs
        return configs

    def _find_test_files(self) -> list[str]:
        test_patterns = [
            "test_*.py",
            "*_test.py",
            "tests/*.py",
            "*_test.ts",
            "*.test.ts",
            "tests/*.rs",
            "*_test.go",
        ]
        tests = []
        for pattern in test_patterns:
            for f in self.project_path.rglob(pattern):
                tests.append(str(f.relative_to(self.project_path)))
        return tests[:20]

    def _find_readme(self) -> str | None:
        readme_names = ["README.md", "README.rst", "README.txt", "readme.md"]
        for name in readme_names:
            if (self.project_path / name).exists():
                return name
        return None

    def _find_documentation(self) -> list[str]:
        doc_dirs = ["docs", "doc", "documentation"]
        docs = []
        for d in doc_dirs:
            doc_path = self.project_path / d
            if doc_path.exists() and doc_path.is_dir():
                for f in doc_path.iterdir():
                    if f.suffix in [".md", ".rst", ".txt"]:
                        docs.append(str(f.relative_to(self.project_path)))
        return docs

    def get_compact_context(self, max_chars: int = 5000) -> str:
        if not self._context:
            self.discover()

        lines = []
        for key, value in self._context.items():
            if isinstance(value, (str, int, bool)):
                lines.append(f"{key}: {value}")
            elif isinstance(value, list):
                lines.append(f"{key}: {len(value)} items")
            elif isinstance(value, dict):
                lines.append(f"{key}: {list(value.keys())}")

        result = "\n".join(lines)
        if len(result) > max_chars:
            result = result[:max_chars] + "... (truncated)"
        return result


def discover_project_context(project_path: str | Path | None = None) -> dict[str, Any]:
    ctx = ProjectContext(project_path)
    return ctx.discover()
