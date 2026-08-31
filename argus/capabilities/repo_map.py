"""Repository map (Aider-style) for codebase understanding."""

import ast
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class SymbolInfo:
    """Information about a code symbol."""
    name: str
    kind: str  # function, class, method, variable, import
    line_start: int
    line_end: int = 0
    signature: str = ""
    docstring: str = ""
    parent: str = ""


@dataclass
class FileMap:
    """Map of a single file's structure."""
    path: str
    language: str = ""
    symbols: List[SymbolInfo] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    classes: List[SymbolInfo] = field(default_factory=list)
    functions: List[SymbolInfo] = field(default_factory=list)
    size_bytes: int = 0
    line_count: int = 0


@dataclass
class RepoMap:
    """Repository map containing all file maps."""
    root: str
    files: Dict[str, FileMap] = field(default_factory=dict)
    total_files: int = 0
    total_lines: int = 0
    languages: Dict[str, int] = field(default_factory=dict)


class RepositoryMapper:
    """Creates Aider-style repository maps."""

    def __init__(
        self,
        max_file_size: int = 1_000_000,  # 1MB max per file
        max_files: int = 500,
        max_total_lines: int = 50_000,
    ):
        self._max_file_size = max_file_size
        self._max_files = max_files
        self._max_total_lines = max_total_lines

        # Directories to exclude
        self._exclude_dirs: Set[str] = {
            ".git", "node_modules", "__pycache__", ".pytest_cache",
            ".mypy_cache", ".ruff_cache", ".tox", ".venv", "venv",
            "dist", "build", "target", ".idea", ".vscode",
            "unified_folder", ".kilocode", ".opencode",
        }

        # Files to exclude
        self._exclude_files: Set[str] = {
            ".DS_Store", "Thumbs.db", "package-lock.json",
            "yarn.lock", "pnpm-lock.yaml", "Cargo.lock",
        }

        # File extensions to language mapping
        self._lang_map: Dict[str, str] = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".kt": "kotlin",
            ".scala": "scala",
            ".rb": "ruby",
            ".php": "php",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c-header",
            ".hpp": "cpp-header",
            ".cs": "csharp",
            ".swift": "swift",
            ".md": "markdown",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".sh": "shell",
            ".sql": "sql",
        }

    def map_repository(self, root_path: str) -> RepoMap:
        """Create a repository map from a root path."""
        root = Path(root_path).resolve()
        if not root.exists():
            return RepoMap(root=str(root))

        repo_map = RepoMap(root=str(root))
        total_lines = 0

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            # Check exclusions
            try:
                rel = path.relative_to(root)
            except ValueError:
                continue

            parts = rel.parts
            if any(part in self._exclude_dirs for part in parts[:-1]):
                continue
            if parts[-1] in self._exclude_files:
                continue
            if parts[-1].startswith(".") and parts[-1] in {".env", ".gitignore", ".dockerignore"}:
                continue

            # Check file count limit
            if len(repo_map.files) >= self._max_files:
                break

            # Check file size
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > self._max_file_size:
                continue

            # Parse file
            file_map = self._parse_file(path, root)
            if file_map:
                total_lines += file_map.line_count
                repo_map.files[str(rel)] = file_map

                # Count languages
                lang = file_map.language
                repo_map.languages[lang] = repo_map.languages.get(lang, 0) + 1

            # Check total lines limit
            if total_lines >= self._max_total_lines:
                break

        repo_map.total_files = len(repo_map.files)
        repo_map.total_lines = total_lines
        return repo_map

    def _parse_file(self, path: Path, root: Path) -> Optional[FileMap]:
        """Parse a single file and extract its structure."""
        try:
            rel = path.relative_to(root)
        except ValueError:
            return None

        suffix = path.suffix.lower()
        language = self._lang_map.get(suffix, "")

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None

        lines = content.split("\n")
        line_count = len(lines)

        file_map = FileMap(
            path=str(rel),
            language=language,
            size_bytes=path.stat().st_size,
            line_count=line_count,
        )

        # Parse based on language
        if language == "python":
            self._parse_python(content, file_map)
        elif language in ("javascript", "typescript"):
            self._parse_js_ts(content, file_map)
        elif language == "rust":
            self._parse_rust(content, file_map)
        elif language == "go":
            self._parse_go(content, file_map)

        return file_map

    def _parse_python(self, content: str, file_map: FileMap) -> None:
        """Parse Python source code."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                sig = self._py_func_signature(node)
                docstring = ast.get_docstring(node) or ""
                file_map.functions.append(SymbolInfo(
                    name=node.name,
                    kind="function",
                    line_start=node.lineno,
                    line_end=node.end_lineno if hasattr(node, "end_lineno") else node.lineno,
                    signature=sig,
                    docstring=docstring[:200],
                ))
            elif isinstance(node, ast.AsyncFunctionDef):
                sig = self._py_func_signature(node, async_=True)
                docstring = ast.get_docstring(node) or ""
                file_map.functions.append(SymbolInfo(
                    name=node.name,
                    kind="async_function",
                    line_start=node.lineno,
                    line_end=node.end_lineno if hasattr(node, "end_lineno") else node.lineno,
                    signature=sig,
                    docstring=docstring[:200],
                ))
            elif isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node) or ""
                class_info = SymbolInfo(
                    name=node.name,
                    kind="class",
                    line_start=node.lineno,
                    line_end=node.end_lineno if hasattr(node, "end_lineno") else node.lineno,
                    docstring=docstring[:200],
                )
                file_map.classes.append(class_info)

                # Parse methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        is_async = isinstance(item, ast.AsyncFunctionDef)
                        sig = self._py_func_signature(item, async_=is_async)
                        method_doc = ast.get_docstring(item) or ""
                        file_map.functions.append(SymbolInfo(
                            name=f"{node.name}.{item.name}",
                            kind="method",
                            line_start=item.lineno,
                            line_end=item.end_lineno if hasattr(item, "end_lineno") else item.lineno,
                            signature=sig,
                            docstring=method_doc[:200],
                            parent=node.name,
                        ))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    file_map.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    file_map.imports.append(f"{module}.{alias.name}")

    def _py_func_signature(self, node: ast.FunctionDef, async_: bool = False) -> str:
        """Extract Python function signature."""
        args = []
        for arg in node.args.args:
            name = arg.arg
            if name == "self" or name == "cls":
                continue
            annotation = ""
            if arg.annotation and hasattr(arg.annotation, "id"):
                annotation = f": {arg.annotation.id}"
            args.append(f"{name}{annotation}")

        prefix = "async def " if async_ else "def "
        args_str = ", ".join(args)
        return f"{prefix}{node.name}({args_str})"

    def _parse_js_ts(self, content: str, file_map: FileMap) -> None:
        """Parse JavaScript/TypeScript source code."""
        # Class pattern
        class_pattern = r"(?:export\s+)?(?:abstract\s+)?class\s+(\w+)"
        for match in re.finditer(class_pattern, content):
            file_map.classes.append(SymbolInfo(
                name=match.group(1),
                kind="class",
                line_start=content[:match.start()].count("\n") + 1,
            ))

        # Function patterns
        func_pattern = r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"
        for match in re.finditer(func_pattern, content):
            file_map.functions.append(SymbolInfo(
                name=match.group(1),
                kind="function",
                line_start=content[:match.start()].count("\n") + 1,
                signature=f"function {match.group(1)}({match.group(2)})",
            ))

        # Arrow function / const assignment
        arrow_pattern = r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>"
        for match in re.finditer(arrow_pattern, content):
            file_map.functions.append(SymbolInfo(
                name=match.group(1),
                kind="arrow_function",
                line_start=content[:match.start()].count("\n") + 1,
                signature=f"const {match.group(1)} = ({match.group(2)}) =>",
            ))

        # Import pattern
        import_pattern = r"import\s+(?:{[^}]+}|[\w*]+)\s+from\s+['\"]([^'\"]+)['\"]"
        for match in re.finditer(import_pattern, content):
            file_map.imports.append(match.group(1))

    def _parse_rust(self, content: str, file_map: FileMap) -> None:
        """Parse Rust source code."""
        # Struct pattern
        struct_pattern = r"(?:pub\s+)?struct\s+(\w+)"
        for match in re.finditer(struct_pattern, content):
            file_map.classes.append(SymbolInfo(
                name=match.group(1),
                kind="struct",
                line_start=content[:match.start()].count("\n") + 1,
            ))

        # Function pattern
        fn_pattern = r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"
        for match in re.finditer(fn_pattern, content):
            file_map.functions.append(SymbolInfo(
                name=match.group(1),
                kind="function",
                line_start=content[:match.start()].count("\n") + 1,
                signature=f"fn {match.group(1)}({match.group(2)})",
            ))

        # Impl block methods
        impl_pattern = r"impl\s+(?:<[^>]*>\s+)?(\w+)"
        for match in re.finditer(impl_pattern, content):
            impl_name = match.group(1)
            # Find methods within impl block
            impl_start = match.start()
            impl_region = content[impl_start:impl_start + 5000]
            method_pattern = r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"
            for method in re.finditer(method_pattern, impl_region):
                file_map.functions.append(SymbolInfo(
                    name=f"{impl_name}.{method.group(1)}",
                    kind="method",
                    line_start=content[:impl_start + method.start()].count("\n") + 1,
                    signature=f"fn {method.group(1)}({method.group(2)})",
                    parent=impl_name,
                ))

    def _parse_go(self, content: str, file_map: FileMap) -> None:
        """Parse Go source code."""
        # Struct pattern
        struct_pattern = r"type\s+(\w+)\s+struct"
        for match in re.finditer(struct_pattern, content):
            file_map.classes.append(SymbolInfo(
                name=match.group(1),
                kind="struct",
                line_start=content[:match.start()].count("\n") + 1,
            ))

        # Function pattern
        fn_pattern = r"func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(([^)]*)\)"
        for match in re.finditer(fn_pattern, content):
            file_map.functions.append(SymbolInfo(
                name=match.group(1),
                kind="function",
                line_start=content[:match.start()].count("\n") + 1,
                signature=f"func {match.group(1)}({match.group(2)})",
            ))

        # Interface pattern
        interface_pattern = r"type\s+(\w+)\s+interface"
        for match in re.finditer(interface_pattern, content):
            file_map.classes.append(SymbolInfo(
                name=match.group(1),
                kind="interface",
                line_start=content[:match.start()].count("\n") + 1,
            ))


def format_repo_map(repo_map: RepoMap, max_depth: int = 3) -> str:
    """Format repository map for display."""
    lines = [
        f"Repository Map: {repo_map.root}",
        f"Files: {repo_map.total_files}  Lines: {repo_map.total_lines}",
        f"Languages: {', '.join(f'{k}({v})' for k, v in repo_map.languages.items())}",
        "",
    ]

    # Group files by directory structure
    tree = _build_tree(list(repo_map.files.keys()))

    # Print tree structure
    _print_tree(tree, "", True, lines, repo_map, max_depth)

    return "\n".join(lines)


def _build_tree(paths: List[str]) -> Dict[str, Any]:
    """Build a tree structure from file paths."""
    tree: Dict[str, Any] = {}
    for path in sorted(paths):
        parts = path.split(os.sep)
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
    return tree


def _print_tree(
    tree: Dict[str, Any],
    prefix: str,
    is_last: bool,
    lines: List[str],
    repo_map: RepoMap,
    max_depth: int,
    current_depth: int = 0,
) -> None:
    """Print tree structure recursively."""
    if current_depth >= max_depth:
        remaining = sum(1 for _ in _count_leaves(tree))
        if remaining > 0:
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}[{remaining} more files...]")
        return

    items = list(tree.items())
    for i, (name, subtree) in enumerate(items):
        is_last_item = i == len(items) - 1
        connector = "└── " if is_last_item else "├── "

        if subtree:  # Directory
            lines.append(f"{prefix}{connector}{name}/")
            extension = "    " if is_last_item else "│   "
            _print_tree(subtree, prefix + extension, True, lines, repo_map, max_depth, current_depth + 1)
        else:  # File
            lines.append(f"{prefix}{connector}{name}")


def _count_leaves(tree: Dict[str, Any]) -> int:
    """Count leaf nodes in tree."""
    count = 0
    for name, subtree in tree.items():
        if not subtree:
            count += 1
        else:
            count += _count_leaves(subtree)
    return count


def format_file_detail(repo_map: RepoMap, file_path: str) -> str:
    """Format detailed information about a file."""
    file_map = repo_map.files.get(file_path)
    if not file_map:
        return f"File not found: {file_path}"

    lines = [
        f"File: {file_map.path}",
        f"Language: {file_map.language}  Lines: {file_map.line_count}  Size: {file_map.size_bytes}B",
        "",
    ]

    if file_map.classes:
        lines.append("Classes:")
        for cls in file_map.classes:
            lines.append(f"  L{cls.line_start}: {cls.name}")
            if cls.docstring:
                lines.append(f"    Doc: {cls.docstring[:80]}")

    if file_map.functions:
        lines.append("Functions:")
        for func in file_map.functions:
            sig = func.signature if func.signature else func.name
            lines.append(f"  L{func.line_start}: {sig}")

    if file_map.imports:
        lines.append(f"Imports: {', '.join(file_map.imports[:10])}")
        if len(file_map.imports) > 10:
            lines.append(f"  ... and {len(file_map.imports) - 10} more")

    return "\n".join(lines)


def search_repo_map(repo_map: RepoMap, pattern: str) -> List[Tuple[str, List[str]]]:
    """Search repository map for files/symbols matching pattern."""
    results: List[Tuple[str, List[str]]] = []
    pat_lower = pattern.lower()

    for path, file_map in repo_map.files.items():
        matches: List[str] = []

        # Check file path
        if pat_lower in path.lower():
            matches.append(f"file:{path}")

        # Check classes
        for cls in file_map.classes:
            if pat_lower in cls.name.lower():
                matches.append(f"class:{cls.name}")

        # Check functions
        for func in file_map.functions:
            if pat_lower in func.name.lower():
                matches.append(f"func:{func.name}")

        # Check imports
        for imp in file_map.imports:
            if pat_lower in imp.lower():
                matches.append(f"import:{imp}")

        if matches:
            results.append((path, matches))

    return results