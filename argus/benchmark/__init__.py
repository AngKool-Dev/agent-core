"""ARGUS Benchmark Package - Scientific evaluation framework."""

from argus.benchmark.aggregation import ResultAggregator
from argus.benchmark.baselines import RegressionDetector
from argus.benchmark.comparison import BaselineManager, ExperimentComparator
from argus.benchmark.dataset import DatasetManager, get_default_dataset
from argus.benchmark.evaluator import BenchmarkEvaluator
from argus.benchmark.experiment import ExperimentManager
from argus.benchmark.export import BenchmarkExporter
from argus.benchmark.failures import FailureAnalyzer
from argus.benchmark.metrics import MetricsCalculator
from argus.benchmark.models import (
    BaselineResult,
    BenchmarkDataset,
    BenchmarkScore,
    BenchmarkStatus,
    BenchmarkTask,
    ComparisonResult,
    ExperimentConfig,
    ExperimentResult,
    FailureRecord,
    FailureType,
    InfrastructureType,
    RegressionCheck,
    ReproducibilityRecord,
    ScoreWeights,
    ScientificInvariant,
    TaskCategory,
    TaskDifficulty,
    TaskRunResult,
    TaskTier,
)
from argus.benchmark.reporter import BenchmarkReporter
from argus.benchmark.reproducibility import ArtifactCapture, ReproducibilityManager
from argus.benchmark.scoring import BenchmarkScorer, create_default_scorer
from argus.benchmark.statistics import BenchmarkStatistics

__all__ = [
    # Core evaluation
    "BenchmarkEvaluator",
    "BenchmarkScorer",
    "create_default_scorer",
    # Models
    "BenchmarkTask",
    "BenchmarkDataset",
    "TaskRunResult",
    "ExperimentConfig",
    "ExperimentResult",
    "BenchmarkScore",
    "ScoreWeights",
    "ComparisonResult",
    "BaselineResult",
    "FailureRecord",
    "RegressionCheck",
    "ReproducibilityRecord",
    "ScientificInvariant",
    # Enums
    "TaskCategory",
    "TaskDifficulty",
    "TaskTier",
    "BenchmarkStatus",
    "FailureType",
    "InfrastructureType",
    # Analysis
    "MetricsCalculator",
    "BenchmarkStatistics",
    "FailureAnalyzer",
    "ResultAggregator",
    "ExperimentComparator",
    "BaselineManager",
    "RegressionDetector",
    # Management
    "DatasetManager",
    "get_default_dataset",
    "ExperimentManager",
    "ReproducibilityManager",
    "ArtifactCapture",
    # Reporting
    "BenchmarkReporter",
    "BenchmarkExporter",
]
