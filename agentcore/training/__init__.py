"""
Phase 6A training pipeline: experience intelligence for EraAI dataset building.

Pipeline:

    Experience
        ↓
    ExperienceAnalyzer          → LearningCandidate
        ↓
    QualityScorer               → scored candidate
        ↓
    DatasetBuilder              → TrainingExample (quality gate)
        ↓
    Dataset stats / versioning

Safety invariants:
    - Training is never invoked from this module.
    - Evaluation cases remain held out (LeakageDetector enforces).
    - Rejected candidates cannot enter the final dataset.
"""

from .analyzer import ExperienceAnalyzer, LearningCandidate, TrainingExample
from .build import build_dataset
from .dataset import DatasetBuilder, DatasetConfig, DatasetValidationResult
from .domains import DOMAIN_KEYWORDS, classify_domains, classify_domains_set
from .experience import CorrectionPair, Experience
from .leakage import EvalCase, LeakageCheckResult, LeakageDetector
from .scorer import QualityScorer
from .stats import DatasetStats, compute_stats

__all__ = [
    "DOMAIN_KEYWORDS",
    "CorrectionPair",
    "DatasetBuilder",
    "DatasetConfig",
    "DatasetStats",
    "DatasetValidationResult",
    "EvalCase",
    "Experience",
    "ExperienceAnalyzer",
    "LeakageCheckResult",
    "LeakageDetector",
    "LearningCandidate",
    "QualityScorer",
    "TrainingExample",
    "build_dataset",
    "classify_domains",
    "classify_domains_set",
    "compute_stats",
]

__version__ = "0.1.0"
