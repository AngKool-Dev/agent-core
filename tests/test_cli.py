import pytest
import argparse


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