"""ARGUS Deterministic Replay + Run Forensics.

Provides the ability to reconstruct any ARGUS run for forensic analysis.

Architecture:
    ARGUS RUN → EVENTS + STATE + SNAPSHOTS → REPLAY ENGINE → FORENSICS

The replay engine is observational only - it NEVER executes tools,
calls models, or mutates production state.
"""

from argus.replay.models import (
    EventIntegrity,
    ExecutionNode,
    ReplayCheckpoint,
    ReplayEvent,
    ReplayRun,
    ReplaySnapshot,
    RecoveryAction,
    ReviewResult,
    RunStatus,
    SecurityDecision,
    StateDiff,
    TimelineEntry,
    VerificationResult,
    ConsistencyIssue,
)
from argus.replay.loader import ReplayLoader, ReplayLoadError, load_run, load_partial_run
from argus.replay.timeline import ReplayTimeline
from argus.replay.reducer import StateReducer, reduce_run
from argus.replay.checkpoint import CheckpointManager
from argus.replay.replay import ReplayEngine, ReplayResult
from argus.replay.tree import build_execution_tree, format_execution_tree
from argus.replay.diff import ReplayDiff
from argus.replay.consistency import ReplayConsistencyChecker, check_consistency
from argus.replay.forensic import ForensicReport, generate_forensic_report
from argus.replay.report import (
    format_timeline_text,
    format_security_text,
    format_recovery_text,
    format_consistency_text,
)

__all__ = [
    # Models
    "EventIntegrity",
    "ExecutionNode",
    "ReplayCheckpoint",
    "ReplayEvent",
    "ReplayRun",
    "ReplaySnapshot",
    "RecoveryAction",
    "ReviewResult",
    "RunStatus",
    "SecurityDecision",
    "StateDiff",
    "TimelineEntry",
    "VerificationResult",
    "ConsistencyIssue",
    # Loader
    "ReplayLoader",
    "ReplayLoadError",
    "load_run",
    "load_partial_run",
    # Timeline
    "ReplayTimeline",
    # Reducer
    "StateReducer",
    "reduce_run",
    # Checkpoint
    "CheckpointManager",
    # Replay Engine
    "ReplayEngine",
    "ReplayResult",
    # Tree
    "build_execution_tree",
    "format_execution_tree",
    # Diff
    "ReplayDiff",
    # Consistency
    "ReplayConsistencyChecker",
    "check_consistency",
    # Forensic
    "ForensicReport",
    "generate_forensic_report",
    # Report formatting
    "format_timeline_text",
    "format_security_text",
    "format_recovery_text",
    "format_consistency_text",
]
