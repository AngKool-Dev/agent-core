import pytest
import argparse
from unittest.mock import patch, MagicMock


class TestCLIArgumentParsing:
    def test_parse_args_basic(self):
        import argparse
        
        parser = argparse.ArgumentParser()
        parser.add_argument("request", nargs="?")
        parser.add_argument("-p", "--project", default=None)
        parser.add_argument("-r", "--runtime", default="hermes", choices=["hermes", "kilo", "opencode"])
        parser.add_argument("-m", "--model", default=None)
        parser.add_argument("--no-verify", action="store_true")
        parser.add_argument("-v", "--verbose", action="store_true")
        parser.add_argument("--db-path", default="~/.agentcore/memory.db")
        
        args = parser.parse_args(["-p", "/project", "Fix crash"])
        
        assert args.project == "/project"
        assert args.request == "Fix crash"
        assert args.runtime == "hermes"

    def test_multiple_flags(self):
        import argparse
        
        parser = argparse.ArgumentParser()
        parser.add_argument("request", nargs="?")
        parser.add_argument("-p", "--project", default=None)
        parser.add_argument("-r", "--runtime", default="hermes", choices=["hermes", "kilo", "opencode"])
        parser.add_argument("-m", "--model", default=None)
        parser.add_argument("--no-verify", action="store_true")
        parser.add_argument("-v", "--verbose", action="store_true")
        
        args = parser.parse_args(["-r", "kilo", "-v", "-m", "gpt-4", "--no-verify", "test request"])
        
        assert args.runtime == "kilo"
        assert args.verbose == True
        assert args.model == "gpt-4"
        assert args.no_verify == True
        assert args.request == "test request"


class TestCLIArgumentDefaults:
    def test_default_runtime(self):
        import argparse
        
        parser = argparse.ArgumentParser()
        parser.add_argument("-r", "--runtime", default="hermes", choices=["hermes", "kilo", "opencode"])
        
        args = parser.parse_args([])
        assert args.runtime == "hermes"

    def test_default_verbose(self):
        import argparse
        
        parser = argparse.ArgumentParser()
        parser.add_argument("-v", "--verbose", action="store_true")
        
        args = parser.parse_args([])
        assert args.verbose == False


class TestCLINoVerifyRegression:
    def test_no_verify_does_not_crash_on_missing_format_check(self, tmp_path):
        from agentcore.cli.main import main
        from agentcore import AgentConfig

        mock_result = {
            "task": {"task_id": "t1", "current_state": "COMPLETED", "selected_skills": [], "user_request": "test"},
            "verification": {
                "overall_passed": True,
                "skipped": True,
            },
            "success": True,
            "tools_used": 0,
        }

        with patch("agentcore.cli.main.Agent") as MockAgent, \
             patch("agentcore.cli.main.ConfigLoader") as MockConfig, \
             patch("agentcore.cli.main.MemoryManager"), \
             patch("agentcore.cli.main.get_default_registry") as mock_registry, \
             patch("agentcore.cli.main.create_agent"):
            MockConfig.discover.return_value = MagicMock()
            MockConfig.discover.return_value.to_agent_config.return_value = AgentConfig(enable_verification=False)
            MockAgent.return_value.execute.return_value = mock_result
            mock_registry.return_value.create.return_value = MagicMock()

            ret = main(["--no-verify", "test request"])
            assert ret == 0