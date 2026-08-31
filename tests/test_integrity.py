"""Tests for ARGUS Durable snapshot corruption handling."""

import json
import os
import tempfile

import pytest

from argus.durable.checkpoints import CheckpointManager
from argus.durable.integrity import IntegrityVerifier
from argus.durable.models import (
    Checkpoint,
    CheckpointPhase,
    OperationJournal,
    OperationRecord,
    OperationStatus,
)


class TestSnapshotCorruption:
    """Tests for snapshot corruption handling."""

    def test_corrupt_checkpoint_detected(self):
        """Test that corrupt checkpoint is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(checkpoint_dir=tmpdir)
            verifier = IntegrityVerifier()

            # Create a checkpoint
            checkpoint = manager.create_checkpoint(
                run_id="run-test",
                phase=CheckpointPhase.BEFORE_EXECUTION,
                state_snapshot={"step": 1},
            )

            # Verify it's valid
            assert verifier.verify_checkpoint(checkpoint)

            # Corrupt it
            checkpoint.integrity_hash = "corrupted_hash"
            assert not verifier.verify_checkpoint(checkpoint)

    def test_corrupt_json_detected(self):
        """Test that corrupt JSON is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(checkpoint_dir=tmpdir)

            # Create a valid checkpoint
            checkpoint = manager.create_checkpoint(
                run_id="run-test",
                phase=CheckpointPhase.AFTER_EXECUTION,
                state_snapshot={"step": 2},
            )

            # Corrupt the file
            path = os.path.join(tmpdir, f"{checkpoint.checkpoint_id}.json")
            with open(path, "w") as f:
                f.write("not valid json{")

            # Loading should fail
            loaded = manager.get_checkpoint(checkpoint.checkpoint_id)
            assert loaded is None

    def test_missing_checkpoint_returns_none(self):
        """Test that missing checkpoint returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(checkpoint_dir=tmpdir)
            loaded = manager.get_checkpoint("nonexistent")
            assert loaded is None

    def test_partial_snapshot_handled(self):
        """Test that partial snapshot is handled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            verifier = IntegrityVerifier()

            # Create a checkpoint with missing fields
            checkpoint = Checkpoint(
                checkpoint_id="chk-1",
                run_id="run-1",
                phase=CheckpointPhase.BEFORE_EXECUTION,
                # Missing other fields
            )

            # Should still be verifiable (integrity hash will be computed)
            checkpoint.integrity_hash = verifier._compute_checkpoint_hash(checkpoint)
            assert verifier.verify_checkpoint(checkpoint)

    def test_old_schema_detected(self):
        """Test that old schema version is detected."""
        verifier = IntegrityVerifier()

        # Incompatible versions
        assert not verifier.verify_snapshot_compatibility("1.0.0", "2.0.0")

        # Compatible versions
        assert verifier.verify_snapshot_compatibility("1.0.0", "1.5.0")

        # Empty versions
        assert not verifier.verify_snapshot_compatibility("", "1.0.0")
        assert not verifier.verify_snapshot_compatibility("1.0.0", "")


class TestJournalIntegrity:
    """Tests for journal integrity verification."""

    def test_valid_journal(self):
        """Test that valid journal passes verification."""
        verifier = IntegrityVerifier()
        journal = OperationJournal(run_id="run-test")

        for i in range(5):
            from argus.durable.models import OperationIdentity, OperationType
            identity = OperationIdentity(
                operation_id=f"op-{i}",
                run_id="run-test",
                session_id="sess-1",
                capability_id="cap-1",
                operation_type=OperationType.FILESYSTEM_WRITE,
                target=f"/workspace/test{i}.py",
            )
            record = OperationRecord(
                identity=identity,
                status=OperationStatus.COMPLETED,
            )
            journal.add_operation(record)

        results = verifier.verify_journal(journal)
        assert results["valid"] is True
        assert results["total_operations"] == 5

    def test_orphaned_child_detected(self):
        """Test that orphaned child operations are detected."""
        verifier = IntegrityVerifier()
        from argus.durable.models import OperationIdentity, OperationType

        journal = OperationJournal(run_id="run-test")
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-test",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.COMPLETED,
            child_operation_ids=["op-nonexistent"],
        )
        journal.add_operation(record)

        results = verifier.verify_journal(journal)
        assert len(results["warnings"]) > 0

    def test_orphaned_parent_detected(self):
        """Test that orphaned parent references are detected."""
        verifier = IntegrityVerifier()
        from argus.durable.models import OperationIdentity, OperationType

        journal = OperationJournal(run_id="run-test")
        identity = OperationIdentity(
            operation_id="op-1",
            run_id="run-test",
            session_id="sess-1",
            capability_id="cap-1",
            operation_type=OperationType.FILESYSTEM_WRITE,
            target="/workspace/test.py",
        )
        record = OperationRecord(
            identity=identity,
            status=OperationStatus.COMPLETED,
            parent_operation_id="op-nonexistent",
        )
        journal.add_operation(record)

        results = verifier.verify_journal(journal)
        assert len(results["warnings"]) > 0


class TestDataCorruptionDetection:
    """Tests for data corruption detection."""

    def test_null_byte_detection(self):
        """Test that null bytes in data are detected."""
        verifier = IntegrityVerifier()
        data = {
            "valid": "data",
            "corrupted": "has\x00null",
        }
        results = verifier.detect_corruption(data)
        assert results["corrupted"] is True
        assert len(results["issues"]) > 0

    def test_valid_data_passes(self):
        """Test that valid data passes corruption check."""
        verifier = IntegrityVerifier()
        data = {
            "valid": "data",
            "number": 42,
            "nested": {"key": "value"},
        }
        results = verifier.detect_corruption(data)
        assert results["corrupted"] is False

    def test_non_dict_detected(self):
        """Test that non-dict data is detected as corrupted."""
        verifier = IntegrityVerifier()
        results = verifier.detect_corruption("not a dict")
        assert results["corrupted"] is True

    def test_nested_null_bytes(self):
        """Test that nested null bytes are detected."""
        verifier = IntegrityVerifier()
        data = {
            "level1": {
                "level2": {
                    "corrupted": "has\x00null"
                }
            }
        }
        results = verifier.detect_corruption(data)
        assert results["corrupted"] is True
