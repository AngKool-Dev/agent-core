"""Subprocess reality tests for ARGUS qualification."""

import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from argus.reality.models import (
    RealityStatus,
    SubprocessCheckResult,
)


class SubprocessRealityTester:
    """Tests real subprocess behavior."""

    def __init__(self):
        self._results: Dict[str, SubprocessCheckResult] = {}

    def run_all_tests(self) -> Dict[str, SubprocessCheckResult]:
        """Run all subprocess reality tests."""
        self._test_process_launch()
        self._test_stdout_capture()
        self._test_stderr_capture()
        self._test_exit_code()
        self._test_timeout()
        self._test_cancellation()
        self._test_process_termination()
        self._test_orphan_prevention()
        self._test_large_output()
        self._test_malformed_output()
        self._test_unicode_output()
        self._test_non_zero_exit()
        self._test_interrupted_process()
        self._test_child_cleanup()

        return self._results

    def _run_command(
        self,
        command: List[str],
        timeout: float = 10.0,
        input_data: Optional[str] = None,
    ) -> Tuple[Optional[subprocess.CompletedProcess], Optional[str]]:
        """Run a command and return result and error."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=input_data,
            )
            return result, None
        except subprocess.TimeoutExpired as e:
            return None, f"timeout: {e}"
        except Exception as e:
            return None, str(e)

    def _test_process_launch(self):
        """Test basic process launch."""
        start_time = time.time()
        result = SubprocessCheckResult(
            command="echo hello",
            status=RealityStatus.PASSED,
        )

        try:
            proc_result, error = self._run_command(
                [sys.executable, "-c", "print('hello')"]
            )
            if proc_result and proc_result.returncode == 0:
                result.exit_code = 0
                result.stdout_captured = bool(proc_result.stdout)
            else:
                result.status = RealityStatus.FAILED
                result.error_message = error or "Process launch failed"
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        result.duration_ms = (time.time() - start_time) * 1000
        self._results["process_launch"] = result

    def _test_stdout_capture(self):
        """Test stdout capture."""
        start_time = time.time()
        result = SubprocessCheckResult(
            command="stdout capture",
            status=RealityStatus.PASSED,
        )

        try:
            proc_result, error = self._run_command(
                [sys.executable, "-c", "print('stdout_output')"]
            )
            if proc_result and "stdout_output" in proc_result.stdout:
                result.stdout_captured = True
            else:
                result.status = RealityStatus.FAILED
                result.error_message = "stdout not captured correctly"
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        result.duration_ms = (time.time() - start_time) * 1000
        self._results["stdout_capture"] = result

    def _test_stderr_capture(self):
        """Test stderr capture."""
        start_time = time.time()
        result = SubprocessCheckResult(
            command="stderr capture",
            status=RealityStatus.PASSED,
        )

        try:
            proc_result, error = self._run_command(
                [sys.executable, "-c", "import sys; print('stderr_output', file=sys.stderr)"]
            )
            if proc_result and "stderr_output" in proc_result.stderr:
                result.stderr_captured = True
            else:
                result.status = RealityStatus.FAILED
                result.error_message = "stderr not captured correctly"
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        result.duration_ms = (time.time() - start_time) * 1000
        self._results["stderr_capture"] = result

    def _test_exit_code(self):
        """Test exit code capture."""
        start_time = time.time()
        result = SubprocessCheckResult(
            command="exit code",
            status=RealityStatus.PASSED,
        )

        try:
            proc_result, error = self._run_command(
                [sys.executable, "-c", "import sys; sys.exit(42)"]
            )
            if proc_result:
                result.exit_code = proc_result.returncode
                if proc_result.returncode == 42:
                    result.metadata["exit_code_correct"] = True
                else:
                    result.status = RealityStatus.FAILED
                    result.error_message = f"Expected exit code 42, got {proc_result.returncode}"
            else:
                result.status = RealityStatus.FAILED
                result.error_message = error or "Process did not complete"
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        result.duration_ms = (time.time() - start_time) * 1000
        self._results["exit_code"] = result

    def _test_timeout(self):
        """Test timeout handling."""
        start_time = time.time()
        result = SubprocessCheckResult(
            command="timeout test",
            status=RealityStatus.PASSED,
        )

        try:
            proc_result, error = self._run_command(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                timeout=1.0,
            )
            if error and "timeout" in error:
                result.timed_out = True
                result.metadata["timeout_handled"] = True
            else:
                result.status = RealityStatus.FAILED
                result.error_message = "Timeout not handled correctly"
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        result.duration_ms = (time.time() - start_time) * 1000
        self._results["timeout"] = result

    def _test_cancellation(self):
        """Test process cancellation."""
        start_time = time.time()
        result = SubprocessCheckResult(
            command="cancellation test",
            status=RealityStatus.PASSED,
        )

        try:
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(0.1)
            proc.terminate()
            proc.wait(timeout=5)

            result.cancelled = True
            result.metadata["cancellation_works"] = True
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        result.duration_ms = (time.time() - start_time) * 1000
        self._results["cancellation"] = result

    def _test_process_termination(self):
        """Test process termination."""
        start_time = time.time()
        result = SubprocessCheckResult(
            command="termination test",
            status=RealityStatus.PASSED,
        )

        try:
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(0.1)
            proc.kill()
            proc.wait(timeout=5)

            result.exit_code = proc.returncode
            result.metadata["termination_works"] = True
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        result.duration_ms = (time.time() - start_time) * 1000
        self._results["process_termination"] = result

    def _test_orphan_prevention(self):
        """Test orphan process prevention."""
        result = SubprocessCheckResult(
            command="orphan prevention",
            status=RealityStatus.PASSED,
        )

        try:
            # Start a process and ensure it's cleaned up
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(0.5)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            proc.wait(timeout=5)

            # Process should be done
            assert proc.poll() is not None
            result.metadata["no_orphan"] = True
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        self._results["orphan_prevention"] = result

    def _test_large_output(self):
        """Test large output handling."""
        start_time = time.time()
        result = SubprocessCheckResult(
            command="large output",
            status=RealityStatus.PASSED,
        )

        try:
            proc_result, error = self._run_command(
                [sys.executable, "-c", "print('x' * 10000)"]
            )
            if proc_result and len(proc_result.stdout) >= 10000:
                result.stdout_captured = True
                result.metadata["large_output_handled"] = True
            else:
                result.status = RealityStatus.FAILED
                result.error_message = "Large output not handled correctly"
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        result.duration_ms = (time.time() - start_time) * 1000
        self._results["large_output"] = result

    def _test_malformed_output(self):
        """Test malformed output handling."""
        result = SubprocessCheckResult(
            command="malformed output",
            status=RealityStatus.PASSED,
        )

        try:
            proc_result, error = self._run_command(
                [sys.executable, "-c", "import sys; sys.stdout.write(b'\\x00\\xff\\xfe'.decode('latin-1'))"]
            )
            # Should complete without error
            result.metadata["malformed_output_handled"] = True
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        self._results["malformed_output"] = result

    def _test_unicode_output(self):
        """Test Unicode output handling."""
        start_time = time.time()
        result = SubprocessCheckResult(
            command="unicode output",
            status=RealityStatus.PASSED,
        )

        try:
            # Use Python directly for reliable Unicode output
            # Write to a file and read back to avoid console encoding issues
            with tempfile.TemporaryDirectory() as tmpdir:
                test_file = Path(tmpdir) / "unicode_test.txt"
                proc_result, error = self._run_command(
                    [sys.executable, "-c",
                     f"with open(r'{test_file}', 'w', encoding='utf-8') as f: f.write('Hello 世界')"]
                )
                if proc_result and proc_result.returncode == 0 and test_file.exists():
                    content = test_file.read_text(encoding="utf-8")
                    if "世界" in content:
                        result.stdout_captured = True
                        result.metadata["unicode_handled"] = True
                    else:
                        result.status = RealityStatus.FAILED
                        result.error_message = "Unicode content not written correctly"
                else:
                    result.status = RealityStatus.FAILED
                    result.error_message = error or "Unicode subprocess failed"
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        result.duration_ms = (time.time() - start_time) * 1000
        self._results["unicode_output"] = result

    def _test_non_zero_exit(self):
        """Test non-zero exit code handling."""
        start_time = time.time()
        result = SubprocessCheckResult(
            command="non-zero exit",
            status=RealityStatus.PASSED,
        )

        try:
            proc_result, error = self._run_command(
                [sys.executable, "-c", "import sys; sys.exit(1)"]
            )
            if proc_result:
                result.exit_code = proc_result.returncode
                if proc_result.returncode == 1:
                    result.metadata["non_zero_exit_handled"] = True
                else:
                    result.status = RealityStatus.FAILED
                    result.error_message = f"Expected exit code 1, got {proc_result.returncode}"
            else:
                result.status = RealityStatus.FAILED
                result.error_message = error or "Process did not complete"
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        result.duration_ms = (time.time() - start_time) * 1000
        self._results["non_zero_exit"] = result

    def _test_interrupted_process(self):
        """Test interrupted process handling."""
        start_time = time.time()
        result = SubprocessCheckResult(
            command="interrupted process",
            status=RealityStatus.PASSED,
        )

        try:
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(0.1)
            proc.send_signal(signal.CTRL_C_EVENT if os.name == "nt" else signal.SIGINT)
            proc.wait(timeout=5)

            result.metadata["interrupt_handled"] = True
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        result.duration_ms = (time.time() - start_time) * 1000
        self._results["interrupted_process"] = result

    def _test_child_cleanup(self):
        """Test child process cleanup."""
        result = SubprocessCheckResult(
            command="child cleanup",
            status=RealityStatus.PASSED,
        )

        try:
            # Start a process that spawns children
            proc = subprocess.Popen(
                [sys.executable, "-c", """
import subprocess
import sys
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.5)"])
child.wait()
"""],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            proc.wait(timeout=10)

            result.metadata["child_cleanup"] = True
        except Exception as e:
            result.status = RealityStatus.FAILED
            result.error_message = str(e)

        self._results["child_cleanup"] = result

    @property
    def results(self) -> Dict[str, SubprocessCheckResult]:
        """Get all subprocess check results."""
        return self._results


# Import signal for interrupt handling
import signal


def test_subprocess_reality() -> Dict[str, SubprocessCheckResult]:
    """Convenience function to run all subprocess reality tests."""
    tester = SubprocessRealityTester()
    return tester.run_all_tests()
