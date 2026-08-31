"""Real subprocess crash/resume test for ARGUS durable execution.

This test starts a real worker subprocess, kills it, and verifies that
ARGUS can recover and resume the operation correctly.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from argus.durable.detector import CrashDetector
from argus.durable.journal import ExecutionJournal
from argus.durable.locks import LockManager
from argus.durable.models import (
    CrashPoint,
    OperationStatus,
    OperationType,
    ReconciliationDecision,
    ResumeMode,
    RunStatus,
)
from argus.durable.reconciler import Reconciler
from argus.durable.resume import ResumeEngine


WORKER_TEMPLATE = '''
import json
import os
import sys

run_dir = os.environ["ARGUS_RUN_DIR"]
journal_dir = os.environ["ARGUS_JOURNAL_DIR"]
target_file = os.environ["ARGUS_TARGET_FILE"]
crash_point = os.environ.get("ARGUS_CRASH_POINT", "AFTER_OPERATION")

from argus.durable.detector import CrashDetector
from argus.durable.journal import ExecutionJournal
from argus.durable.lifecycle import LifecycleManager
from argus.durable.executor import DurableExecutor
from argus.durable.models import CrashPoint, OperationType

detector = CrashDetector(run_dir=run_dir)
journal = ExecutionJournal(journal_dir=journal_dir)
lifecycle = LifecycleManager(detector=detector, journal=journal)

run = lifecycle.create_run(
    session_id="sess-test",
    task="Write a file and crash mid-execution",
)
print(json.dumps({"run_id": run.run_id}), flush=True)

executor = DurableExecutor(
    journal=journal,
    crash_points=[CrashPoint[crash_point]],
)

def write_file():
    with open(target_file, "w") as f:
        f.write("hello durable world")
    return "done"

result = executor.execute_with_journal(
    run_id=run.run_id,
    session_id="sess-test",
    capability_id="cap-filewriter",
    operation_type=OperationType.FILESYSTEM_WRITE,
    target=target_file,
    operation=write_file,
    arguments={"content": "hello durable world"},
)
# Never reached - os._exit(1) kills the process
print(json.dumps({"result": result}), flush=True)
'''


class TestSubprocessCrashResume:
    """Tests that start a real worker subprocess, kill it, and resume."""

    def test_worker_crash_after_operation_then_resume(self, tmp_path):
        """Worker crashes after operation completes but before journal records completion.

        The file IS written, but the journal shows STARTED (not COMPLETED).
        Recovery should detect the file exists and mark as RECONCILED_COMPLETED.
        """
        # 1. Set up shared directories
        run_dir = str(tmp_path / "runs")
        journal_dir = str(tmp_path / "journals")
        lock_dir = str(tmp_path / "locks")
        target_file = str(tmp_path / "output.txt")

        env = {
            **os.environ,
            "ARGUS_RUN_DIR": run_dir,
            "ARGUS_JOURNAL_DIR": journal_dir,
            "ARGUS_LOCK_DIR": lock_dir,
            "ARGUS_TARGET_FILE": target_file,
            "ARGUS_CRASH_POINT": "AFTER_OPERATION",
        }

        # 2. Write worker script
        worker_script = tmp_path / "worker.py"
        worker_script.write_text(WORKER_TEMPLATE)

        # 3. Start worker subprocess
        proc = subprocess.Popen(
            [sys.executable, "-u", str(worker_script)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # 4. Wait for the worker to crash and get all output
        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 1  # os._exit(1)

        # Debug output
        print(f"\nDEBUG: stdout={repr(stdout)}")
        print(f"DEBUG: stderr={repr(stderr)}")
        print(f"DEBUG: returncode={proc.returncode}")

        # Parse run_id from stdout
        first_line = stdout.strip().split("\n")[0]
        info = json.loads(first_line.strip())
        run_id = info["run_id"]

        # 6. Verify the crash left the journal in an incomplete state
        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)

        run = detector.get_run(run_id)
        assert run.status == RunStatus.RUNNING  # Not yet detected as crashed

        # Journal should have STARTED ops (not COMPLETED)
        started_ops = journal.get_operations_by_status(run_id, OperationStatus.STARTED)
        assert len(started_ops) == 1

        # 7. Detect crash (manual — avoids 5-min heartbeat wait)
        detector.mark_crashed(run_id)

        # 8. Mark STARTED ops as UNKNOWN
        unknown_ops = journal.mark_all_started_as_unknown(run_id)
        assert len(unknown_ops) == 1

        # 9. Mark recoverable
        detector.mark_recoverable(run_id)

        # 10. Acquire lock
        locks = LockManager(lock_dir=lock_dir, lock_timeout=10)
        lock = locks.acquire_lock(run_id, owner_id="test-recovery")
        assert lock is not None

        # 11. Resume
        engine = ResumeEngine(
            journal=journal,
            detector=detector,
            reconciler=Reconciler(),
        )
        result = engine.resume(run_id, mode=ResumeMode.NORMAL)
        assert result["success"] is True

        # 12. Verify reconciliation
        # Since the worker wrote the file before crashing,
        # the reconciler should find file_exists=True, content_matches=True
        recon = result["reconciliation_results"][0]
        assert recon["decision"] == ReconciliationDecision.MARK_COMPLETED
        assert recon["final_status"] == OperationStatus.RECONCILED_COMPLETED

        # 13. Verify run is RUNNING again
        run = detector.get_run(run_id)
        assert run.status == RunStatus.RUNNING
        assert run.resume_count == 1
        assert run.crash_count == 1

        # 14. Verify the file was written (side effect happened before crash)
        assert os.path.exists(target_file)
        with open(target_file) as f:
            assert f.read() == "hello durable world"

        # 15. Release lock
        locks.release_lock(run_id, owner_id="test-recovery")

    def test_worker_crash_before_operation_starts(self, tmp_path):
        """Worker crashes before the operation starts — INTENT only, safe to retry."""
        run_dir = str(tmp_path / "runs")
        journal_dir = str(tmp_path / "journals")
        lock_dir = str(tmp_path / "locks")
        target_file = str(tmp_path / "output.txt")

        env = {
            **os.environ,
            "ARGUS_RUN_DIR": run_dir,
            "ARGUS_JOURNAL_DIR": journal_dir,
            "ARGUS_LOCK_DIR": lock_dir,
            "ARGUS_TARGET_FILE": target_file,
            "ARGUS_CRASH_POINT": "BEFORE_START",
        }

        worker_script = tmp_path / "worker.py"
        worker_script.write_text(WORKER_TEMPLATE)

        proc = subprocess.Popen(
            [sys.executable, "-u", str(worker_script)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        first_line = proc.stdout.readline()
        info = json.loads(first_line.strip())
        run_id = info["run_id"]

        proc.wait(timeout=10)
        assert proc.returncode == 1

        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)

        # Journal should have INTENT ops (not STARTED)
        intent_ops = journal.get_operations_by_status(run_id, OperationStatus.INTENT)
        assert len(intent_ops) == 1

        # Mark crashed and recoverable
        detector.mark_crashed(run_id)
        detector.mark_recoverable(run_id)

        # No STARTED ops to mark as UNKNOWN
        unknown_ops = journal.mark_all_started_as_unknown(run_id)
        assert len(unknown_ops) == 0

        # Resume should succeed with no UNKNOWN ops
        locks = LockManager(lock_dir=lock_dir, lock_timeout=10)
        lock = locks.acquire_lock(run_id, owner_id="test-recovery")
        assert lock is not None

        engine = ResumeEngine(
            journal=journal,
            detector=detector,
            reconciler=Reconciler(),
        )
        result = engine.resume(run_id, mode=ResumeMode.NORMAL)
        assert result["success"] is True

        # No reconciliation needed
        assert len(result["reconciliation_results"]) == 0

        # File should NOT exist (operation never ran)
        assert not os.path.exists(target_file)

        locks.release_lock(run_id, owner_id="test-recovery")

    def test_worker_crash_during_operation(self, tmp_path):
        """Worker crashes during operation — STARTED, side effects may or may not have happened."""
        run_dir = str(tmp_path / "runs")
        journal_dir = str(tmp_path / "journals")
        lock_dir = str(tmp_path / "locks")
        target_file = str(tmp_path / "output.txt")

        env = {
            **os.environ,
            "ARGUS_RUN_DIR": run_dir,
            "ARGUS_JOURNAL_DIR": journal_dir,
            "ARGUS_LOCK_DIR": lock_dir,
            "ARGUS_TARGET_FILE": target_file,
            "ARGUS_CRASH_POINT": "DURING_OPERATION",
        }

        worker_script = tmp_path / "worker.py"
        worker_script.write_text(WORKER_TEMPLATE)

        proc = subprocess.Popen(
            [sys.executable, "-u", str(worker_script)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        first_line = proc.stdout.readline()
        info = json.loads(first_line.strip())
        run_id = info["run_id"]

        proc.wait(timeout=10)
        assert proc.returncode == 1

        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)

        # Mark crashed and recoverable
        detector.mark_crashed(run_id)
        unknown_ops = journal.mark_all_started_as_unknown(run_id)
        assert len(unknown_ops) == 1
        detector.mark_recoverable(run_id)

        locks = LockManager(lock_dir=lock_dir, lock_timeout=10)
        lock = locks.acquire_lock(run_id, owner_id="test-recovery")
        assert lock is not None

        engine = ResumeEngine(
            journal=journal,
            detector=detector,
            reconciler=Reconciler(),
        )
        result = engine.resume(run_id, mode=ResumeMode.NORMAL)
        assert result["success"] is True

        # For FILESYSTEM_WRITE where file doesn't exist, should be RETRY
        recon = result["reconciliation_results"][0]
        assert recon["decision"] == ReconciliationDecision.RETRY
        assert recon["final_status"] == OperationStatus.RECONCILED_NOT_EXECUTED

        # File should NOT exist (operation was interrupted)
        assert not os.path.exists(target_file)

        locks.release_lock(run_id, owner_id="test-recovery")

    def test_worker_crash_after_completion(self, tmp_path):
        """Worker crashes after completion — COMPLETED on disk, no reconciliation needed."""
        run_dir = str(tmp_path / "runs")
        journal_dir = str(tmp_path / "journals")
        lock_dir = str(tmp_path / "locks")
        target_file = str(tmp_path / "output.txt")

        env = {
            **os.environ,
            "ARGUS_RUN_DIR": run_dir,
            "ARGUS_JOURNAL_DIR": journal_dir,
            "ARGUS_LOCK_DIR": lock_dir,
            "ARGUS_TARGET_FILE": target_file,
            "ARGUS_CRASH_POINT": "AFTER_COMPLETION",
        }

        worker_script = tmp_path / "worker.py"
        worker_script.write_text(WORKER_TEMPLATE)

        proc = subprocess.Popen(
            [sys.executable, "-u", str(worker_script)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        first_line = proc.stdout.readline()
        info = json.loads(first_line.strip())
        run_id = info["run_id"]

        proc.wait(timeout=10)
        assert proc.returncode == 1

        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)

        # Journal should have COMPLETED ops
        completed_ops = journal.get_operations_by_status(run_id, OperationStatus.COMPLETED)
        assert len(completed_ops) == 1

        detector.mark_crashed(run_id)
        detector.mark_recoverable(run_id)

        locks = LockManager(lock_dir=lock_dir, lock_timeout=10)
        lock = locks.acquire_lock(run_id, owner_id="test-recovery")
        assert lock is not None

        engine = ResumeEngine(
            journal=journal,
            detector=detector,
            reconciler=Reconciler(),
        )
        result = engine.resume(run_id, mode=ResumeMode.NORMAL)
        assert result["success"] is True

        # No reconciliation needed (already COMPLETED)
        assert len(result["reconciliation_results"]) == 0

        # File should exist
        assert os.path.exists(target_file)

        locks.release_lock(run_id, owner_id="test-recovery")

    def test_killed_process_not_equal_success(self, tmp_path):
        """REAL-DUR-001: Killed process ≠ successful operation."""
        run_dir = str(tmp_path / "runs")
        journal_dir = str(tmp_path / "journals")
        target_file = str(tmp_path / "output.txt")

        env = {
            **os.environ,
            "ARGUS_RUN_DIR": run_dir,
            "ARGUS_JOURNAL_DIR": journal_dir,
            "ARGUS_TARGET_FILE": target_file,
            "ARGUS_CRASH_POINT": "AFTER_OPERATION",
        }

        worker_script = tmp_path / "worker.py"
        worker_script.write_text(WORKER_TEMPLATE)

        proc = subprocess.Popen(
            [sys.executable, "-u", str(worker_script)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        first_line = proc.stdout.readline()
        info = json.loads(first_line.strip())
        run_id = info["run_id"]

        proc.wait(timeout=10)

        # Process was killed (not a successful exit)
        assert proc.returncode == 1
        assert proc.poll() is not None

        # Journal should NOT show COMPLETED
        journal = ExecutionJournal(journal_dir=journal_dir)
        completed_ops = journal.get_operations_by_status(run_id, OperationStatus.COMPLETED)
        assert len(completed_ops) == 0

        # Operation should be STARTED (incomplete)
        started_ops = journal.get_operations_by_status(run_id, OperationStatus.STARTED)
        assert len(started_ops) == 1

    def test_unknown_cannot_silently_complete(self, tmp_path):
        """REAL-DUR-002: UNKNOWN operation cannot silently become COMPLETED."""
        run_dir = str(tmp_path / "runs")
        journal_dir = str(tmp_path / "journals")
        target_file = str(tmp_path / "output.txt")

        env = {
            **os.environ,
            "ARGUS_RUN_DIR": run_dir,
            "ARGUS_JOURNAL_DIR": journal_dir,
            "ARGUS_TARGET_FILE": target_file,
            "ARGUS_CRASH_POINT": "AFTER_OPERATION",
        }

        worker_script = tmp_path / "worker.py"
        worker_script.write_text(WORKER_TEMPLATE)

        proc = subprocess.Popen(
            [sys.executable, "-u", str(worker_script)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        first_line = proc.stdout.readline()
        info = json.loads(first_line.strip())
        run_id = info["run_id"]

        proc.wait(timeout=10)

        detector = CrashDetector(run_dir=run_dir)
        journal = ExecutionJournal(journal_dir=journal_dir)

        # Mark crashed
        detector.mark_crashed(run_id)

        # Mark STARTED as UNKNOWN
        unknown_ops = journal.mark_all_started_as_unknown(run_id)
        assert len(unknown_ops) == 1

        # Verify UNKNOWN status
        unknown_after = journal.get_operations_by_status(run_id, OperationStatus.UNKNOWN)
        assert len(unknown_after) == 1

        # UNKNOWN should NOT be silently COMPLETED without reconciliation
        completed_ops = journal.get_operations_by_status(run_id, OperationStatus.COMPLETED)
        assert len(completed_ops) == 0

    def test_recovery_budget_survives_process_death(self, tmp_path):
        """REAL-DUR-003: Recovery budget survives process death."""
        run_dir = str(tmp_path / "runs")
        journal_dir = str(tmp_path / "journals")
        target_file = str(tmp_path / "output.txt")

        env = {
            **os.environ,
            "ARGUS_RUN_DIR": run_dir,
            "ARGUS_JOURNAL_DIR": journal_dir,
            "ARGUS_TARGET_FILE": target_file,
            "ARGUS_CRASH_POINT": "AFTER_OPERATION",
        }

        worker_script = tmp_path / "worker.py"
        worker_script.write_text(WORKER_TEMPLATE)

        proc = subprocess.Popen(
            [sys.executable, "-u", str(worker_script)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        first_line = proc.stdout.readline()
        info = json.loads(first_line.strip())
        run_id = info["run_id"]

        proc.wait(timeout=10)

        detector = CrashDetector(run_dir=run_dir)

        # Mark crashed — this increments crash_count
        run = detector.mark_crashed(run_id)
        assert run.crash_count == 1

        # Recovery budget should be tracked
        assert run.recovery_budget_used == 0  # No recovery yet

        # After marking recoverable, budget should still be preserved
        detector.mark_recoverable(run_id)
        run = detector.get_run(run_id)
        assert run.crash_count == 1

    def test_concurrent_recovery_prevented(self, tmp_path):
        """REAL-DUR-006: Concurrent recovery of the same run is prevented."""
        run_dir = str(tmp_path / "runs")
        journal_dir = str(tmp_path / "journals")
        lock_dir = str(tmp_path / "locks")

        locks = LockManager(lock_dir=lock_dir, lock_timeout=60)

        # First recovery acquires lock
        lock1 = locks.acquire_lock("run-test", owner_id="recovery-1")
        assert lock1 is not None

        # Second recovery should be blocked
        lock2 = locks.acquire_lock("run-test", owner_id="recovery-2")
        assert lock2 is None

        # After releasing, second can acquire
        locks.release_lock("run-test", owner_id="recovery-1")
        lock3 = locks.acquire_lock("run-test", owner_id="recovery-2")
        assert lock3 is not None

        locks.release_lock("run-test", owner_id="recovery-2")
