import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from .base import RuntimeAdapter, ToolCall, ToolResult, HermesAPI


class HermesRuntime(RuntimeAdapter):
    def __init__(self, model: Optional[str] = None, provider: Optional[str] = None, timeout: int = 300):
        self.model = model
        self.provider = provider
        self.timeout = timeout
        self._response_text = ""
        self._last_tool_call: Optional[ToolCall] = None
        self._complete = False
        self._tool_result: Optional[ToolResult] = None

    def respond(self, context: dict[str, Any]) -> Any:
        full_prompt = HermesAPI.build_prompt(context)
        
        hermes_args = ["hermes", "-z"]
        
        if self.model:
            hermes_args.extend(["-m", self.model])
        if self.provider:
            hermes_args.extend(["--provider", self.provider])

        try:
            result = subprocess.run(
                hermes_args + [full_prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            response = result.stdout.strip() if result.stdout else ""
            self._response_text = response
            self._complete = result.returncode != 0 or "COMPLETE" in response.upper()
            
            self._parse_tool_calls(response)
            
            return response

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Hermes call timed out after {self.timeout}s")
        except Exception as e:
            raise RuntimeError(f"Hermes call failed: {str(e)}")

    def _parse_tool_calls(self, response: str) -> None:
        tool_pattern = r'TOOL_CALL:\s*(\w+)\s*\{([^}]+)\}'
        matches = re.findall(tool_pattern, response, re.IGNORECASE)
        
        if matches:
            tool_name = matches[-1][0]
            args_str = matches[-1][1]
            
            args = {}
            for arg_match in re.finditer(r'"(\w+)":\s*"([^"]*)"', args_str):
                args[arg_match.group(1)] = arg_match.group(2)
            
            self._last_tool_call = ToolCall(
                tool=tool_name,
                arguments=args,
            )

    def get_response_text(self) -> str:
        return self._response_text

    def is_complete(self) -> bool:
        return self._complete

    def get_pending_tool_call(self) -> Optional[ToolCall]:
        return self._last_tool_call

    def clear_tool_call(self) -> None:
        self._last_tool_call = None

    def execute_tool(self, tool_call: ToolCall, cwd: Optional[Path] = None) -> ToolResult:
        import time
        start = time.time()
        work_dir = cwd or Path.cwd()

        try:
            if tool_call.tool == "read_file":
                path = tool_call.arguments.get("path", "")
                full_path = Path(path)
                if full_path.is_absolute():
                    content = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
                else:
                    full_path = work_dir / path
                    content = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
                return ToolResult(
                    success=True,
                    tool=tool_call.tool,
                    stdout=content,
                    duration=time.time() - start,
                )
            
            elif tool_call.tool == "write_file":
                path = tool_call.arguments.get("path", "")
                content = tool_call.arguments.get("content", "")
                full_path = Path(path)
                if not full_path.is_absolute():
                    full_path = work_dir / path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")
                return ToolResult(
                    success=True,
                    tool=tool_call.tool,
                    stdout=f"Wrote {len(content)} bytes to {path}",
                    duration=time.time() - start,
                )
            
            elif tool_call.tool == "run_command":
                cmd = tool_call.arguments.get("command", "")
                timeout = int(tool_call.arguments.get("timeout", 30))
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=work_dir,
                    timeout=timeout,
                )
                return ToolResult(
                    success=result.returncode == 0,
                    tool=tool_call.tool,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode,
                    duration=time.time() - start,
                )
            
            elif tool_call.tool == "search_files":
                query = tool_call.arguments.get("query", "")
                pattern = re.compile(query, re.IGNORECASE) if query else None
                results = []
                for f in work_dir.rglob("*"):
                    if f.is_file() and ".git" not in str(f) and "node_modules" not in str(f):
                        try:
                            content = f.read_text(encoding="utf-8", errors="ignore")
                            for i, line in enumerate(content.split("\n"), 1):
                                if pattern and pattern.search(line):
                                    results.append(f"{f.relative_to(work_dir)}:{i}: {line[:100]}")
                        except Exception:
                            continue
                        if len(results) >= 50:
                            break
                return ToolResult(
                    success=True,
                    tool=tool_call.tool,
                    stdout="\n".join(results),
                    duration=time.time() - start,
                )
            
            elif tool_call.tool == "git_status":
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    cwd=work_dir,
                )
                return ToolResult(
                    success=True,
                    tool=tool_call.tool,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode,
                    duration=time.time() - start,
                )
            
            elif tool_call.tool == "git_diff":
                result = subprocess.run(
                    ["git", "diff"],
                    capture_output=True,
                    text=True,
                    cwd=work_dir,
                )
                return ToolResult(
                    success=True,
                    tool=tool_call.tool,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode,
                    duration=time.time() - start,
                )
            
            elif tool_call.tool == "run_tests":
                if (work_dir / "Cargo.toml").exists():
                    cmd = "cargo test"
                elif (work_dir / "pyproject.toml").exists():
                    cmd = "pytest"
                elif (work_dir / "package.json").exists():
                    cmd = "npm test"
                else:
                    return ToolResult(
                        success=False,
                        tool=tool_call.tool,
                        error="No test runner found for this project",
                        duration=time.time() - start,
                    )
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=work_dir, timeout=60)
                return ToolResult(
                    success=result.returncode == 0,
                    tool=tool_call.tool,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode,
                    duration=time.time() - start,
                )
            
            else:
                return ToolResult(
                    success=False,
                    tool=tool_call.tool,
                    error=f"Unknown tool: {tool_call.tool}",
                    duration=time.time() - start,
                )
        
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                tool=tool_call.tool,
                error=f"Tool execution timed out",
                duration=time.time() - start,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                tool=tool_call.tool,
                error=str(e),
                duration=time.time() - start,
            )


def create_hermes_runtime(model: Optional[str] = None, provider: Optional[str] = None) -> HermesRuntime:
    return HermesRuntime(model=model, provider=provider)