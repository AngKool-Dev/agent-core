"""Benchmark dataset management."""

from typing import Dict, List, Optional

from argus.benchmark.models import (
    BenchmarkDataset,
    BenchmarkTask,
    TaskCategory,
    TaskDifficulty,
    TaskTier,
)


class DatasetManager:
    """Manages benchmark datasets."""

    def __init__(self):
        self._datasets: Dict[str, BenchmarkDataset] = {}

    def register_dataset(self, dataset: BenchmarkDataset) -> None:
        self._datasets[dataset.dataset_id] = dataset

    def get_dataset(self, dataset_id: str) -> Optional[BenchmarkDataset]:
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> List[str]:
        return list(self._datasets.keys())

    def validate_dataset(self, dataset: BenchmarkDataset) -> List[str]:
        """Validate a benchmark dataset for integrity issues."""
        issues = []

        if not dataset.tasks:
            issues.append("Dataset has no tasks")

        task_ids = set()
        for task in dataset.tasks:
            if task.task_id in task_ids:
                issues.append(f"Duplicate task ID: {task.task_id}")
            task_ids.add(task.task_id)

            if not task.success_criteria:
                issues.append(f"Task {task.task_id}: missing success criteria")

            if not task.description:
                issues.append(f"Task {task.task_id}: missing description")

            if task.timeout_seconds <= 0:
                issues.append(f"Task {task.task_id}: invalid timeout")

        return issues


def create_default_dataset() -> BenchmarkDataset:
    """Create the default engineering benchmark dataset."""
    tasks = [
        BenchmarkTask(
            task_id="bug_fix_01",
            name="Fix Failing Unit Test",
            description="A unit test is failing due to an off-by-one error in the loop boundary. Identify and fix the bug.",
            category=TaskCategory.BUG_FIX,
            difficulty=TaskDifficulty.EASY,
            tier=TaskTier.TIER_1,
            language="python",
            repository_state={
                "src/calculator.py": "def sum_range(n):\n    total = 0\n    for i in range(n):  # Bug: should be range(1, n+1)\n        total += i\n    return total\n",
                "tests/test_calculator.py": "from src.calculator import sum_range\n\ndef test_sum_range():\n    assert sum_range(5) == 15  # 1+2+3+4+5\n",
            },
            success_criteria=["tests pass", "sum_range(5) == 15"],
            constraints={"max_iterations": 5, "max_tool_calls": 10},
            tags=["unit-test", "off-by-one"],
        ),
        BenchmarkTask(
            task_id="feature_01",
            name="Add Input Validation",
            description="Add input validation to the divide function to handle division by zero gracefully.",
            category=TaskCategory.FEATURE,
            difficulty=TaskDifficulty.EASY,
            tier=TaskTier.TIER_1,
            language="python",
            repository_state={
                "src/math_ops.py": "def divide(a, b):\n    return a / b\n",
                "tests/test_math_ops.py": "from src.math_ops import divide\n\ndef test_divide():\n    assert divide(10, 2) == 5.0\n\ndef test_divide_by_zero():\n    try:\n        divide(10, 0)\n        assert False, 'Should have raised ValueError'\n    except ValueError:\n        pass\n",
            },
            success_criteria=["ValueError raised on divide by zero", "tests pass"],
            constraints={"max_iterations": 5, "max_tool_calls": 10},
            tags=["validation", "error-handling"],
        ),
        BenchmarkTask(
            task_id="refactor_01",
            name="Extract Method Refactoring",
            description="Refactor the process_order function by extracting the discount calculation into a separate function.",
            category=TaskCategory.REFACTOR,
            difficulty=TaskDifficulty.MEDIUM,
            tier=TaskTier.TIER_2,
            language="python",
            repository_state={
                "src/orders.py": "def process_order(items, customer):\n    total = sum(item['price'] for item in items)\n    # Calculate discount\n    if customer.get('vip'):\n        total *= 0.9\n    elif total > 100:\n        total *= 0.95\n    return total\n",
                "tests/test_orders.py": "from src.orders import process_order\n\ndef test_process_order():\n    items = [{'price': 50}, {'price': 60}]\n    assert process_order(items, {}) == 110.0\n    assert process_order(items, {'vip': True}) == 99.0\n",
            },
            success_criteria=["discount logic extracted", "tests pass", "no unrelated changes"],
            constraints={"max_iterations": 8, "max_tool_calls": 15},
            tags=["refactoring", "extract-method"],
        ),
        BenchmarkTask(
            task_id="debugging_01",
            name="Diagnose Intermittent Failure",
            description="A test is failing intermittently due to a race condition. Identify the root cause and fix it.",
            category=TaskCategory.DEBUGGING,
            difficulty=TaskDifficulty.HARD,
            tier=TaskTier.TIER_3,
            language="python",
            repository_state={
                "src/cache.py": "import time\n\n_cache = {}\n\ndef get_data(key):\n    if key not in _cache:\n        time.sleep(0.01)  # Simulates slow fetch\n        _cache[key] = f'data_{key}'\n    return _cache[key]\n",
                "tests/test_cache.py": "from src.cache import get_data\nimport threading\n\ndef test_concurrent_access():\n    results = []\n    def worker():\n        results.append(get_data('key'))\n    threads = [threading.Thread(target=worker) for _ in range(5)]\n    for t in threads:\n        t.start()\n    for t in threads:\n        t.join()\n    assert all(r == 'data_key' for r in results)\n",
            },
            success_criteria=["thread-safe implementation", "tests pass", "no race condition"],
            constraints={"max_iterations": 10, "max_tool_calls": 20},
            tags=["debugging", "concurrency", "race-condition"],
        ),
        BenchmarkTask(
            task_id="security_01",
            name="Fix SQL Injection Vulnerability",
            description="The user lookup function is vulnerable to SQL injection. Fix it using parameterized queries.",
            category=TaskCategory.SECURITY,
            difficulty=TaskDifficulty.MEDIUM,
            tier=TaskTier.TIER_2,
            language="python",
            repository_state={
                "src/database.py": "import sqlite3\n\ndef find_user(username):\n    conn = sqlite3.connect(':memory:')\n    cursor = conn.cursor()\n    # Vulnerable to SQL injection\n    cursor.execute(f\"SELECT * FROM users WHERE username = '{username}'\")\n    return cursor.fetchone()\n",
                "tests/test_database.py": "from src.database import find_user\n\ndef test_find_user():\n    # Should not be injectable\n    result = find_user(\"admin' OR '1'='1\")\n    assert result is None\n",
            },
            success_criteria=["parameterized query used", "tests pass", "no SQL injection"],
            constraints={"max_iterations": 6, "max_tool_calls": 12},
            tags=["security", "sql-injection"],
        ),
        BenchmarkTask(
            task_id="multi_file_01",
            name="Update API Endpoint and Tests",
            description="Add a new field 'email' to the user creation endpoint and update all related tests.",
            category=TaskCategory.MULTI_FILE,
            difficulty=TaskDifficulty.MEDIUM,
            tier=TaskTier.TIER_2,
            language="python",
            repository_state={
                "src/api.py": "def create_user(name):\n    return {'id': 1, 'name': name}\n",
                "src/models.py": "class User:\n    def __init__(self, name):\n        self.name = name\n",
                "tests/test_api.py": "from src.api import create_user\n\ndef test_create_user():\n    user = create_user('Alice')\n    assert user['name'] == 'Alice'\n",
            },
            success_criteria=["email field added", "all files updated", "tests pass"],
            constraints={"max_iterations": 10, "max_tool_calls": 20},
            tags=["multi-file", "api"],
        ),
        BenchmarkTask(
            task_id="edge_case_01",
            name="Handle Empty Input Edge Case",
            description="The parse_config function crashes on empty input. Add proper handling for edge cases.",
            category=TaskCategory.EDGE_CASE,
            difficulty=TaskDifficulty.EASY,
            tier=TaskTier.TIER_1,
            language="python",
            repository_state={
                "src/config.py": "def parse_config(text):\n    lines = text.strip().split('\\n')\n    config = {}\n    for line in lines:\n        key, value = line.split('=')\n        config[key.strip()] = value.strip()\n    return config\n",
                "tests/test_config.py": "from src.config import parse_config\n\ndef test_empty_config():\n    result = parse_config('')\n    assert result == {}\n\ndef test_normal_config():\n    result = parse_config('key=value')\n    assert result == {'key': 'value'}\n",
            },
            success_criteria=["empty input handled", "tests pass", "no crash"],
            constraints={"max_iterations": 5, "max_tool_calls": 10},
            tags=["edge-case", "error-handling"],
        ),
        BenchmarkTask(
            task_id="regression_01",
            name="Fix Regression in Sorting",
            description="A recent change broke the sorting functionality. Identify the regression and fix it without breaking other tests.",
            category=TaskCategory.REGRESSION,
            difficulty=TaskDifficulty.HARD,
            tier=TaskTier.TIER_3,
            language="python",
            repository_state={
                "src/sorter.py": "def sort_items(items):\n    # Bug: reverse=True was accidentally added\n    return sorted(items, reverse=True)\n",
                "tests/test_sorter.py": "from src.sorter import sort_items\n\ndef test_sort_ascending():\n    assert sort_items([3, 1, 2]) == [1, 2, 3]\n\ndef test_sort_empty():\n    assert sort_items([]) == []\n\ndef test_sort_single():\n    assert sort_items([1]) == [1]\n",
            },
            success_criteria=["ascending sort restored", "all tests pass", "no regressions"],
            constraints={"max_iterations": 8, "max_tool_calls": 15},
            tags=["regression", "sorting"],
        ),
        BenchmarkTask(
            task_id="performance_01",
            name="Optimize Fibonacci Calculation",
            description="The recursive fibonacci implementation is slow for large inputs. Add memoization to improve performance.",
            category=TaskCategory.PERFORMANCE,
            difficulty=TaskDifficulty.MEDIUM,
            tier=TaskTier.TIER_2,
            language="python",
            repository_state={
                "src/fibonacci.py": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n",
                "tests/test_fibonacci.py": "from src.fibonacci import fibonacci\n\ndef test_fibonacci():\n    assert fibonacci(0) == 0\n    assert fibonacci(1) == 1\n    assert fibonacci(10) == 55\n    assert fibonacci(20) == 6765\n",
            },
            success_criteria=["memoization added", "tests pass", "performance improved"],
            constraints={"max_iterations": 8, "max_tool_calls": 15},
            tags=["performance", "memoization"],
        ),
        BenchmarkTask(
            task_id="expert_01",
            name="Implement Plugin Architecture",
            description="Refactor the monolithic processor into a plugin-based architecture where new processors can be registered dynamically.",
            category=TaskCategory.REFACTOR,
            difficulty=TaskDifficulty.EXPERT,
            tier=TaskTier.TIER_4,
            language="python",
            repository_state={
                "src/processor.py": "def process(data, method):\n    if method == 'upper':\n        return data.upper()\n    elif method == 'lower':\n        return data.lower()\n    elif method == 'reverse':\n        return data[::-1]\n    else:\n        raise ValueError(f'Unknown method: {method}')\n",
                "tests/test_processor.py": "from src.processor import process\n\ndef test_process():\n    assert process('Hello', 'upper') == 'HELLO'\n    assert process('Hello', 'lower') == 'hello'\n    assert process('Hello', 'reverse') == 'olleH'\n",
            },
            success_criteria=["plugin registry", "dynamic registration", "tests pass", "extensible design"],
            constraints={"max_iterations": 15, "max_tool_calls": 30},
            tags=["expert", "architecture", "plugins"],
        ),
    ]

    return BenchmarkDataset(
        dataset_id="engineering-v1.0",
        name="Engineering Benchmark v1.0",
        version="1.0",
        description="Core software engineering tasks for evaluating ARGUS",
        tasks=tasks,
        metadata={
            "created_for": "phase-24",
            "task_count": len(tasks),
            "categories": list(set(t.category.value for t in tasks)),
            "difficulties": list(set(t.difficulty.value for t in tasks)),
        },
    )


def get_default_dataset() -> BenchmarkDataset:
    """Get the default engineering benchmark dataset."""
    return create_default_dataset()
