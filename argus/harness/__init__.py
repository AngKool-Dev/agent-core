"""ARGUS Real-World Task Harness.

A benchmark framework for evaluating ARGUS on real software engineering tasks.
"""

from argus.harness.models import (
    BenchmarkScorecard,
    BenchmarkTask,
    SuccessCriteria,
    TaskCategory,
    TaskConstraints,
    TaskDifficulty,
    TaskLanguage,
    TaskResult,
    TaskState,
)
from argus.harness.runner import (
    BenchmarkRunner,
    TaskEnvironment,
    TaskVerifier,
)
from argus.harness.tasks import (
    get_benchmark_tasks,
    get_task_by_id,
    get_tasks_by_category,
    get_tasks_by_difficulty,
)

__all__ = [
    # Models
    "BenchmarkScorecard",
    "BenchmarkTask",
    "SuccessCriteria",
    "TaskCategory",
    "TaskConstraints",
    "TaskDifficulty",
    "TaskLanguage",
    "TaskResult",
    "TaskState",
    # Runner
    "BenchmarkRunner",
    "TaskEnvironment",
    "TaskVerifier",
    # Tasks
    "get_benchmark_tasks",
    "get_task_by_id",
    "get_tasks_by_category",
    "get_tasks_by_difficulty",
]
