"""Benchmark data models for ARGUS scientific evaluation."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid


class TaskTier(Enum):
    """Task difficulty tiers."""
    TIER_1 = "tier_1"  # Single-file deterministic fixes
    TIER_2 = "tier_2"  # Multi-file modifications
    TIER_3 = "tier_3"  # Repository-level reasoning
    TIER_4 = "tier_4"  # Ambiguous engineering tasks
    TIER_5 = "tier_5"  # Adversarial / failure-heavy tasks


class TaskCategory(Enum):
    """Task categories for benchmark evaluation."""
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    TESTING = "testing"
    DEBUGGING = "debugging"
    MULTI_FILE = "multi_file"
    REGRESSION = "regression"
    EDGE_CASE = "edge_case"
    DEPENDENCY = "dependency"
    SECURITY = "security"
    PERFORMANCE = "performance"
    REPOSITORY_NAVIGATION = "repository_navigation"


class TaskDifficulty(Enum):
    """Task difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class BenchmarkStatus(Enum):
    """Status of a benchmark run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"
    TIMED_OUT = "timed_out"
    INVALID = "invalid"


class FailureType(Enum):
    """Classification of failure types."""
    PLANNING_FAILURE = "planning_failure"
    CONTEXT_FAILURE = "context_failure"
    MODEL_FAILURE = "model_failure"
    PROVIDER_FAILURE = "provider_failure"
    TOOL_FAILURE = "tool_failure"
    SECURITY_BLOCK = "security_block"
    VERIFICATION_FAILURE = "verification_failure"
    REVIEW_FAILURE = "review_failure"
    RECOVERY_EXHAUSTION = "recovery_exhaustion"
    DURABILITY_FAILURE = "durability_failure"
    ENVIRONMENT_FAILURE = "environment_failure"
    HARNESS_FAILURE = "harness_failure"
    UNKNOWN_FAILURE = "unknown_failure"


class InfrastructureType(Enum):
    """Distinguishes infrastructure from agent failures."""
    AGENT_FAILURE = "agent_failure"
    PROVIDER_FAILURE = "provider_failure"
    BENCHMARK_FAILURE = "benchmark_failure"
    ENVIRONMENT_FAILURE = "environment_failure"
    HARNESS_FAILURE = "harness_failure"


@dataclass
class BenchmarkTask:
    """A single benchmark task definition."""
    task_id: str
    name: str
    description: str
    category: TaskCategory
    difficulty: TaskDifficulty
    tier: TaskTier
    language: str = "python"
    repository_state: Dict[str, str] = field(default_factory=dict)
    initial_state: Dict[str, str] = field(default_factory=dict)
    success_criteria: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    expected_behavior: str = ""
    tags: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    hidden_tests: List[str] = field(default_factory=list)
    reference_solution: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkDataset:
    """A collection of benchmark tasks."""
    dataset_id: str
    name: str
    version: str
    description: str = ""
    tasks: List[BenchmarkTask] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def get_task_by_id(self, task_id: str) -> Optional[BenchmarkTask]:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None

    def get_tasks_by_category(self, category: TaskCategory) -> List[BenchmarkTask]:
        return [t for t in self.tasks if t.category == category]

    def get_tasks_by_difficulty(self, difficulty: TaskDifficulty) -> List[BenchmarkTask]:
        return [t for t in self.tasks if t.difficulty == difficulty]

    def get_tasks_by_tier(self, tier: TaskTier) -> List[BenchmarkTask]:
        return [t for t in self.tasks if t.tier == tier]


@dataclass
class TaskRunResult:
    """Result of a single task run within an experiment."""
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    experiment_id: str = ""
    status: BenchmarkStatus = BenchmarkStatus.PENDING
    success: bool = False
    duration_seconds: float = 0.0
    iterations: int = 0
    tool_calls: int = 0
    model_calls: int = 0
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    tests_passed: int = 0
    tests_failed: int = 0
    verification_passed: bool = False
    review_passed: bool = False
    recovery_attempts: int = 0
    security_blocks: int = 0
    score: float = 0.0
    findings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    failure_type: Optional[FailureType] = None
    infrastructure_type: Optional[InfrastructureType] = None
    provider_failures: int = 0
    provider_fallbacks: int = 0
    provider_switches: int = 0
    circuit_openings: int = 0
    quarantines: int = 0
    crash_resumes: int = 0
    duplicate_executions: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class ExperimentConfig:
    """Configuration for a benchmark experiment."""
    experiment_id: str = field(default_factory=lambda: f"exp-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    benchmark_version: str = "v1.0"
    agent_version: str = ""
    provider: str = ""
    model: str = ""
    temperature: float = 0.7
    seed: int = 42
    task_selection: List[str] = field(default_factory=list)
    repeat_count: int = 1
    timeout: int = 300
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, bool] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ExperimentResult:
    """Complete result of a benchmark experiment."""
    config: ExperimentConfig = field(default_factory=ExperimentConfig)
    run_results: List[TaskRunResult] = field(default_factory=list)
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    timed_out_tasks: int = 0
    error_tasks: int = 0
    total_duration: float = 0.0
    total_iterations: int = 0
    total_tool_calls: int = 0
    total_model_calls: int = 0
    total_tokens: int = 0
    total_recovery_attempts: int = 0
    total_security_blocks: int = 0
    total_provider_failures: int = 0
    total_crash_resumes: int = 0
    completed_at: Optional[str] = None

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks

    @property
    def average_duration(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.total_duration / self.total_tasks

    @property
    def average_tool_calls(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.total_tool_calls / self.total_tasks


@dataclass
class ScoreWeights:
    """Configurable weights for aggregate scoring."""
    task_success: float = 0.40
    verification: float = 0.20
    review: float = 0.15
    security: float = 0.15
    efficiency: float = 0.10

    def validate(self) -> bool:
        total = (
            self.task_success
            + self.verification
            + self.review
            + self.security
            + self.efficiency
        )
        return abs(total - 1.0) < 0.001


@dataclass
class BenchmarkScore:
    """A comprehensive benchmark score with raw metrics and weighted aggregate."""
    experiment_id: str = ""
    raw_metrics: Dict[str, float] = field(default_factory=dict)
    weighted_components: Dict[str, float] = field(default_factory=dict)
    weights: ScoreWeights = field(default_factory=ScoreWeights)
    final_score: float = 0.0
    confidence_interval: Optional[tuple] = None
    sample_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureRecord:
    """Record of a benchmark failure for analysis."""
    task_id: str = ""
    experiment_id: str = ""
    failure_type: FailureType = FailureType.UNKNOWN_FAILURE
    infrastructure_type: Optional[InfrastructureType] = None
    initial_failure: str = ""
    fatal_failure: str = ""
    recovery_attempted: bool = False
    recovery_succeeded: bool = False
    error_message: str = ""
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Result of comparing two experiments."""
    experiment_a_id: str = ""
    experiment_b_id: str = ""
    metrics_comparison: Dict[str, Dict[str, float]] = field(default_factory=dict)
    absolute_differences: Dict[str, float] = field(default_factory=dict)
    relative_differences: Dict[str, float] = field(default_factory=dict)
    statistically_significant: Dict[str, bool] = field(default_factory=dict)
    conclusion: str = ""


@dataclass
class BaselineResult:
    """A baseline measurement for comparison."""
    name: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    success_rate: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactManifest:
    """Manifest of captured benchmark artifacts."""
    experiment_id: str = ""
    run_id: str = ""
    task_id: str = ""
    artifacts: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ReproducibilityRecord:
    """Record of experiment reproducibility metadata."""
    experiment_id: str = ""
    run_id: str = ""
    task_id: str = ""
    benchmark_version: str = ""
    argus_version: str = ""
    argus_commit: str = ""
    provider: str = ""
    model: str = ""
    configuration: Dict[str, Any] = field(default_factory=dict)
    random_seed: int = 42
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    python_version: str = ""
    os_info: str = ""
    dependency_versions: Dict[str, str] = field(default_factory=dict)
    nondeterminism_sources: List[str] = field(default_factory=list)


@dataclass
class RegressionCheck:
    """Result of a regression check."""
    metric: str = ""
    baseline_value: float = 0.0
    current_value: float = 0.0
    absolute_change: float = 0.0
    relative_change: float = 0.0
    is_regression: bool = False
    threshold: float = 0.0
    confidence: float = 0.0


@dataclass
class ScientificInvariant:
    """An executable scientific invariant for benchmarking."""
    invariant_id: str = ""
    description: str = ""
    category: str = ""
    check_fn: Optional[Any] = None

    def check(self, *args, **kwargs) -> bool:
        if self.check_fn:
            return self.check_fn(*args, **kwargs)
        return True
