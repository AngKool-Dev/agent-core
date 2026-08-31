"""Tests for repository map."""

import os
import tempfile
from pathlib import Path

import pytest

from argus.capabilities.repo_map import (
    FileMap,
    RepoMap,
    RepositoryMapper,
    SymbolInfo,
    format_file_detail,
    format_repo_map,
    search_repo_map,
)


class TestSymbolInfo:
    def test_symbol_creation(self):
        sym = SymbolInfo(name="test", kind="function", line_start=1)
        assert sym.name == "test"
        assert sym.kind == "function"
        assert sym.line_start == 1

    def test_symbol_with_signature(self):
        sym = SymbolInfo(
            name="test",
            kind="function",
            line_start=1,
            signature="def test(x: int)",
            docstring="A test function",
        )
        assert sym.signature == "def test(x: int)"


class TestFileMap:
    def test_file_map_creation(self):
        fm = FileMap(path="test.py", language="python", line_count=10)
        assert fm.path == "test.py"
        assert fm.language == "python"
        assert fm.line_count == 10
        assert fm.symbols == []
        assert fm.imports == []


class TestRepoMap:
    def test_repo_map_creation(self):
        rm = RepoMap(root="/test")
        assert rm.root == "/test"
        assert rm.files == {}
        assert rm.total_files == 0


class TestRepositoryMapper:
    def _create_test_dir(self):
        """Create a temporary test directory with sample files."""
        tmpdir = tempfile.mkdtemp()

        # Python file
        py_file = Path(tmpdir) / "main.py"
        py_file.write_text('"""Main module."""\nimport os\nfrom sys import path\n\nclass MyClass:\n    """A test class."""\n    def method(self):\n        pass\n\ndef hello(name: str) -> str:\n    """Say hello."""\n    return f"Hello {name}"\n\ndef add(a: int, b: int) -> int:\n    return a + b\n')

        # JavaScript file
        js_file = Path(tmpdir) / "app.js"
        js_file.write_text('import React from "react";\nimport { useState } from "react";\n\nexport function App() {\n    return <div>Hello</div>;\n}\n\nconst helper = (x) => x * 2;\n')

        # TypeScript file
        ts_file = Path(tmpdir) / "utils.ts"
        ts_file.write_text('export interface User {\n    name: string;\n    age: number;\n}\n\nexport function greet(user: User): string {\n    return `Hello ${user.name}`;\n}\n')

        # Subdirectory
        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()
        sub_file = subdir / "helper.py"
        sub_file.write_text('def helper():\n    pass\n')

        # File in excluded dir
        node_modules = Path(tmpdir) / "node_modules"
        node_modules.mkdir()
        excluded = node_modules / "lib.js"
        excluded.write_text('const x = 1;\n')

        return tmpdir

    def test_map_repository(self):
        mapper = RepositoryMapper()
        tmpdir = self._create_test_dir()
        try:
            result = mapper.map_repository(tmpdir)
            assert isinstance(result, RepoMap)
            assert result.total_files >= 3  # py, js, ts files
            assert result.total_lines > 0
            assert "python" in result.languages
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_map_repository_nonexistent(self):
        mapper = RepositoryMapper()
        result = mapper.map_repository("/nonexistent/path")
        assert result.total_files == 0

    def test_parse_python_file(self):
        mapper = RepositoryMapper()
        tmpdir = self._create_test_dir()
        try:
            result = mapper.map_repository(tmpdir)
            main_py = result.files.get("main.py")
            assert main_py is not None
            assert main_py.language == "python"
            assert len(main_py.classes) >= 1  # MyClass
            assert len(main_py.functions) >= 3  # hello, add, MyClass.method
            assert "os" in main_py.imports
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_parse_js_file(self):
        mapper = RepositoryMapper()
        tmpdir = self._create_test_dir()
        try:
            result = mapper.map_repository(tmpdir)
            app_js = result.files.get("app.js")
            assert app_js is not None
            assert app_js.language == "javascript"
            assert len(app_js.functions) >= 1  # App
            assert any("react" in imp.lower() for imp in app_js.imports)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_exclude_dirs(self):
        mapper = RepositoryMapper()
        tmpdir = self._create_test_dir()
        try:
            result = mapper.map_repository(tmpdir)
            # node_modules should be excluded
            assert not any("node_modules" in path for path in result.files)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_language_detection(self):
        mapper = RepositoryMapper()
        tmpdir = self._create_test_dir()
        try:
            result = mapper.map_repository(tmpdir)
            assert "python" in result.languages
            assert "javascript" in result.languages
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestFormatRepoMap:
    def test_format_empty_repo(self):
        rm = RepoMap(root="/test")
        output = format_repo_map(rm)
        assert "Repository Map" in output
        assert "Files: 0" in output

    def test_format_with_files(self):
        rm = RepoMap(root="/test", total_files=2, total_lines=100)
        rm.files["main.py"] = FileMap(path="main.py", language="python", line_count=50)
        rm.files["app.js"] = FileMap(path="app.js", language="javascript", line_count=50)
        rm.languages = {"python": 1, "javascript": 1}
        output = format_repo_map(rm)
        assert "main.py" in output
        assert "app.js" in output


class TestFormatFileDetail:
    def test_format_existing_file(self):
        rm = RepoMap(root="/test")
        rm.files["main.py"] = FileMap(
            path="main.py",
            language="python",
            line_count=20,
            classes=[SymbolInfo(name="MyClass", kind="class", line_start=5, docstring="A class")],
            functions=[SymbolInfo(name="hello", kind="function", line_start=10, signature="def hello(name)")],
            imports=["os", "sys"],
        )
        output = format_file_detail(rm, "main.py")
        assert "MyClass" in output
        assert "hello" in output
        assert "os" in output

    def test_format_missing_file(self):
        rm = RepoMap(root="/test")
        output = format_file_detail(rm, "missing.py")
        assert "not found" in output.lower()


class TestSearchRepoMap:
    def test_search_by_class_name(self):
        rm = RepoMap(root="/test")
        rm.files["main.py"] = FileMap(
            path="main.py",
            language="python",
            classes=[SymbolInfo(name="MyClass", kind="class", line_start=1)],
            functions=[SymbolInfo(name="hello", kind="function", line_start=5)],
        )
        results = search_repo_map(rm, "MyClass")
        assert len(results) >= 1
        assert any("MyClass" in str(matches) for _, matches in results)

    def test_search_by_function_name(self):
        rm = RepoMap(root="/test")
        rm.files["main.py"] = FileMap(
            path="main.py",
            language="python",
            functions=[SymbolInfo(name="hello", kind="function", line_start=5)],
        )
        results = search_repo_map(rm, "hello")
        assert len(results) >= 1

    def test_search_by_file_path(self):
        rm = RepoMap(root="/test")
        rm.files["src/main.py"] = FileMap(path="src/main.py", language="python")
        rm.files["lib/utils.py"] = FileMap(path="lib/utils.py", language="python")
        results = search_repo_map(rm, "main")
        assert len(results) >= 1

    def test_search_no_match(self):
        rm = RepoMap(root="/test")
        rm.files["main.py"] = FileMap(path="main.py", language="python")
        results = search_repo_map(rm, "nonexistent")
        assert len(results) == 0

    def test_search_case_insensitive(self):
        rm = RepoMap(root="/test")
        rm.files["main.py"] = FileMap(
            path="main.py",
            language="python",
            classes=[SymbolInfo(name="MyClass", kind="class", line_start=1)],
        )
        results = search_repo_map(rm, "myclass")
        assert len(results) >= 1