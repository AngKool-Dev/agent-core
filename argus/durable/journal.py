"""ARGUS Durable Execution Journal.

Provides durable operation lifecycle tracking.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from argus.durable.models import (
    OperationJournal,
    OperationRecord,
    OperationStatus,
    generate_operation_id,
)

logger = logging.getLogger(__name__)

JOURNAL_DIR = os.path.join(os.path.expanduser("~"), ".argus", "journals")


class ExecutionJournal:
    """Manages the durable execution journal.

    Every externally meaningful operation has lifecycle information:
    INTENT -> STARTED -> PROGRESS -> COMPLETED/FAILED/UNKNOWN
    """

    def __init__(self, journal_dir: str = JOURNAL_DIR):
        self._journal_dir = journal_dir
        self._journals: Dict[str, OperationJournal] = {}
        os.makedirs(self._journal_dir, exist_ok=True)

    def create_journal(self, run_id: str) -> OperationJournal:
        """Create a new journal for a run."""
        journal = OperationJournal(run_id=run_id)
        self._journals[run_id] = journal
        self._save_journal(journal)
        return journal

    def get_journal(self, run_id: str) -> Optional[OperationJournal]:
        """Get the journal for a run."""
        if run_id in self._journals:
            return self._journals[run_id]
        journal = self._load_journal(run_id)
        if journal:
            self._journals[run_id] = journal
            return journal
        return None

    def record_intent(
        self,
        run_id: str,
        session_id: str,
        capability_id: str,
        operation_type: str,
        target: str,
        arguments: Dict[str, Any] = None,
        parent_operation_id: str = None,
    ) -> OperationRecord:
        """Record the intent to perform an operation."""
        from argus.durable.models import OperationIdentity, OperationType

        journal = self.get_journal(run_id)
        if not journal:
            journal = self.create_journal(run_id)

        identity = OperationIdentity(
            operation_id=generate_operation_id(),
            run_id=run_id,
            session_id=session_id,
            capability_id=capability_id,
            operation_type=OperationType(operation_type),
            target=target,
            normalized_arguments=arguments or {},
        )

        record = OperationRecord(
            identity=identity,
            status=OperationStatus.INTENT,
            parent_operation_id=parent_operation_id,
        )

        journal.add_operation(record)
        self._save_journal(journal)
        logger.debug(f"Recorded intent: {identity.operation_id} for {operation_type}")
        return record

    def record_start(self, run_id: str, operation_id: str) -> Optional[OperationRecord]:
        """Record that an operation has started."""
        return self._update_status(run_id, operation_id, OperationStatus.STARTED)

    def record_progress(
        self,
        run_id: str,
        operation_id: str,
        evidence: Dict[str, Any] = None,
    ) -> Optional[OperationRecord]:
        """Record progress on an operation."""
        return self._update_status(
            run_id, operation_id, OperationStatus.PROGRESS, evidence=evidence
        )

    def record_completion(
        self,
        run_id: str,
        operation_id: str,
        evidence: Dict[str, Any] = None,
    ) -> Optional[OperationRecord]:
        """Record that an operation has completed."""
        return self._update_status(
            run_id, operation_id, OperationStatus.COMPLETED, evidence=evidence
        )

    def record_failure(
        self,
        run_id: str,
        operation_id: str,
        error: str = "",
        evidence: Dict[str, Any] = None,
    ) -> Optional[OperationRecord]:
        """Record that an operation has failed."""
        return self._update_status(
            run_id, operation_id, OperationStatus.FAILED, error=error, evidence=evidence
        )

    def mark_unknown(
        self,
        run_id: str,
        operation_id: str,
    ) -> Optional[OperationRecord]:
        """Mark an operation as UNKNOWN (e.g., after a crash)."""
        return self._update_status(run_id, operation_id, OperationStatus.UNKNOWN)

    def mark_all_started_as_unknown(self, run_id: str) -> List[OperationRecord]:
        """Mark all STARTED operations as UNKNOWN (used after crash detection)."""
        journal = self.get_journal(run_id)
        if not journal:
            return []

        updated = []
        for op in journal.operations:
            if op.status == OperationStatus.STARTED:
                op.status = OperationStatus.UNKNOWN
                op.updated_at = __import__("datetime").datetime.utcnow().isoformat()
                updated.append(op)

        if updated:
            self._save_journal(journal)
        return updated

    def record_reconciliation(
        self,
        run_id: str,
        operation_id: str,
        decision: str,
        final_status: OperationStatus,
        evidence: Dict[str, Any] = None,
    ) -> Optional[OperationRecord]:
        """Record the reconciliation decision for an UNKNOWN operation."""
        journal = self.get_journal(run_id)
        if not journal:
            return None

        op = journal.get_operation(operation_id)
        if not op:
            return None

        op.status = final_status
        op.reconciliation = decision
        op.updated_at = __import__("datetime").datetime.utcnow().isoformat()
        if evidence:
            op.evidence.update(evidence)

        self._save_journal(journal)
        return op

    def get_unknown_operations(self, run_id: str) -> List[OperationRecord]:
        """Get all UNKNOWN operations for a run."""
        journal = self.get_journal(run_id)
        if not journal:
            return []
        return journal.get_unknown_operations()

    def get_operations_by_status(
        self, run_id: str, status: OperationStatus
    ) -> List[OperationRecord]:
        """Get all operations with a given status."""
        journal = self.get_journal(run_id)
        if not journal:
            return []
        return journal.get_operations_by_status(status)

    def get_operation(self, run_id: str, operation_id: str) -> Optional[OperationRecord]:
        """Get a specific operation."""
        journal = self.get_journal(run_id)
        if not journal:
            return None
        return journal.get_operation(operation_id)

    def _update_status(
        self,
        run_id: str,
        operation_id: str,
        status: OperationStatus,
        error: str = "",
        evidence: Dict[str, Any] = None,
    ) -> Optional[OperationRecord]:
        """Update the status of an operation."""
        journal = self.get_journal(run_id)
        if not journal:
            return None

        op = journal.get_operation(operation_id)
        if not op:
            return None

        op.status = status
        op.updated_at = __import__("datetime").datetime.utcnow().isoformat()
        if error:
            op.error = error
        if evidence:
            op.evidence.update(evidence)

        self._save_journal(journal)
        return op

    def _save_journal(self, journal: OperationJournal):
        """Save journal to disk."""
        path = self._journal_path(journal.run_id)
        with open(path, "w") as f:
            json.dump(journal.to_dict(), f, indent=2)

    def _load_journal(self, run_id: str) -> Optional[OperationJournal]:
        """Load journal from disk."""
        path = self._journal_path(run_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return OperationJournal.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load journal for run {run_id}: {e}")
            return None

    def _journal_path(self, run_id: str) -> str:
        """Get the file path for a journal."""
        return os.path.join(self._journal_dir, f"{run_id}.json")

    def delete_journal(self, run_id: str):
        """Delete a journal."""
        path = self._journal_path(run_id)
        if os.path.exists(path):
            os.remove(path)
        self._journals.pop(run_id, None)
