"""ARGUS Durable Execution - Crash Safety and Resume.

Makes ARGUS capable of safely surviving process crashes, reconstructing
execution state, and resuming incomplete work without corrupting state,
bypassing security, duplicating unsafe operations, or falsely claiming success.
"""

from argus.durable.models import (
    Checkpoint,
    CheckpointCapability,
    CheckpointExecution,
    CheckpointPhase,
    CheckpointPhaseData,
    CheckpointRecovery,
    CheckpointReview,
    CheckpointVerification,
    CrashPoint,
    ExecutionRun,
    IdempotencyClass,
    LockState,
    OperationIdentity,
    OperationJournal,
    OperationRecord,
    OperationStatus,
    OperationType,
    ReconciliationDecision,
    ResumeMode,
    RetryPolicy,
    RunStatus,
)
from argus.durable.journal import ExecutionJournal
from argus.durable.checkpoints import CheckpointManager
from argus.durable.recovery import CrashRecovery
from argus.durable.detector import CrashDetector
from argus.durable.reconciler import Reconciler
from argus.durable.idempotency import IdempotencyClassifier
from argus.durable.executor import DurableExecutor
from argus.durable.resume import ResumeEngine
from argus.durable.lifecycle import LifecycleManager
from argus.durable.locks import LockManager
from argus.durable.integrity import IntegrityVerifier
from argus.durable.reporting import DurableReporter

__all__ = [
    # Models
    "Checkpoint",
    "CheckpointCapability",
    "CheckpointExecution",
    "CheckpointPhase",
    "CheckpointRecovery",
    "CheckpointReview",
    "CheckpointVerification",
    "CrashPoint",
    "ExecutionRun",
    "IdempotencyClass",
    "LockState",
    "OperationIdentity",
    "OperationJournal",
    "OperationRecord",
    "OperationStatus",
    "OperationType",
    "ReconciliationDecision",
    "ResumeMode",
    "RetryPolicy",
    "RunStatus",
    # Core
    "ExecutionJournal",
    "CheckpointManager",
    "CrashRecovery",
    "CrashDetector",
    "Reconciler",
    "IdempotencyClassifier",
    "DurableExecutor",
    "ResumeEngine",
    "LifecycleManager",
    "LockManager",
    "IntegrityVerifier",
    "DurableReporter",
]
