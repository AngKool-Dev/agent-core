import pytest
from pathlib import Path
from agentcore.context import ProjectContext, discover_project_context


class TestProjectContextDiscovery:
    def test_discover_rust_project(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'test'\n")
        
        ctx = ProjectContext(tmp_path)
        result = ctx.discover()
        
        assert result["language"] == "rust"
        assert result["project_root"] == str(tmp_path)

    def test_discover_python_project(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        
        ctx = ProjectContext(tmp_path)
        result = ctx.discover()
        
        assert result["language"] == "python"

    def test_discover_javascript_project(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test"}')
        
        ctx = ProjectContext(tmp_path)
        result = ctx.discover()
        
        assert result["language"] == "typescript" or result["language"] == "javascript"

    def test_detect_readme(self, tmp_path):
        (tmp_path / "README.md").write_text("# Test Project\n")
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        
        ctx = ProjectContext(tmp_path)
        result = ctx.discover()
        
        assert result["readme"] == "README.md"

    def test_detect_config_files(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        (tmp_path / "config.yaml").write_text("key: value\n")
        
        ctx = ProjectContext(tmp_path)
        result = ctx.discover()
        
        assert len(result["config_files"]) >= 2

    def test_compact_context(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        
        ctx = ProjectContext(tmp_path)
        ctx.discover()
        
        compact = ctx.get_compact_context(max_chars=1000)
        assert "language:" in compact or "Language" in compact

    def test_project_context_function(self, tmp_path):
        (tmp_path / "Cargo.toml").write_text("[package]\n")
        
        result = discover_project_context(tmp_path)
        
        assert result["language"] == "rust"


class TestProjectContextEdgeCases:
    def test_nonexistent_path(self):
        ctx = ProjectContext("/nonexistent/path")
        result = ctx.discover()
        
        assert "project_root" in result

    def test_git_status_non_repo(self, tmp_path):
        ctx = ProjectContext(tmp_path)
        result = ctx.discover()
        
        assert "git_status" in result
        assert result["git_status"]["is_git_repo"] == False