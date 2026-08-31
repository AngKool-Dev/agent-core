"""ARGUS Real-World Task Harness - task repository.

Contains a curated set of real software engineering tasks for benchmarking.
"""

from argus.harness.models import (
    BenchmarkTask,
    SuccessCriteria,
    TaskCategory,
    TaskConstraints,
    TaskDifficulty,
    TaskLanguage,
    TaskState,
)


def get_benchmark_tasks() -> list:
    """Get all benchmark tasks."""
    tasks = []

    # === FIX FAILING TEST ===
    tasks.append(BenchmarkTask(
        task_id="fix_failing_test_01",
        name="Fix Off-By-One Error",
        description="Fix the off-by-one error in the sum_range function. The test expects sum_range(1, 5) to return 15 (1+2+3+4+5) but it currently returns 10 (1+2+3+4).",
        category=TaskCategory.FIX_FAILING_TEST,
        difficulty=TaskDifficulty.EASY,
        language=TaskLanguage.PYTHON,
        initial_state=TaskState(files={
            "src/calculator.py": '''"""Calculator module."""


def sum_range(start: int, end: int) -> int:
    """Sum all integers from start to end (inclusive)."""
    total = 0
    for i in range(start, end):  # Bug: should be end + 1
        total += i
    return total


def product_range(start: int, end: int) -> int:
    """Multiply all integers from start to end (inclusive)."""
    total = 1
    for i in range(start, end + 1):
        total *= i
    return total
''',
            "tests/test_calculator.py": '''"""Tests for calculator module."""

import pytest
from src.calculator import sum_range, product_range


def test_sum_range():
    assert sum_range(1, 5) == 15  # 1+2+3+4+5
    assert sum_range(1, 10) == 55
    assert sum_range(3, 7) == 25  # 3+4+5+6+7


def test_product_range():
    assert product_range(1, 5) == 120  # 1*2*3*4*5
    assert product_range(1, 3) == 6
''',
        }),
        success_criteria=SuccessCriteria(
            expected_files_modified=["src/calculator.py"],
            expected_content_contains={
                "src/calculator.py": ["range(start, end + 1)"],
            },
            expected_tests_pass=["test_sum_range", "test_product_range"],
        ),
        constraints=TaskConstraints(
            allowed_paths=["src/calculator.py"],
            require_tests_pass=True,
        ),
        expected_tests=["tests/test_calculator.py::test_sum_range"],
        tags=["bug-fix", "off-by-one", "arithmetic"],
    ))

    # === FIX COMPILATION ERROR ===
    tasks.append(BenchmarkTask(
        task_id="fix_compilation_01",
        name="Fix Missing Import",
        description="Fix the missing import error. The code tries to use 'datetime' without importing it.",
        category=TaskCategory.FIX_COMPILATION_ERROR,
        difficulty=TaskDifficulty.TRIVIAL,
        language=TaskLanguage.PYTHON,
        initial_state=TaskState(files={
            "src/timestamps.py": '''"""Timestamp utilities."""


def get_current_timestamp() -> str:
    """Get current timestamp as ISO format string."""
    return datetime.datetime.now().isoformat()


def format_timestamp(ts: str) -> str:
    """Format a timestamp string."""
    return datetime.datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
''',
            "tests/test_timestamps.py": '''"""Tests for timestamps module."""

from src.timestamps import get_current_timestamp, format_timestamp


def test_get_current_timestamp():
    result = get_current_timestamp()
    assert isinstance(result, str)
    assert "T" in result  # ISO format


def test_format_timestamp():
    result = format_timestamp("2024-01-15T10:30:00")
    assert "2024-01-15" in result
''',
        }),
        success_criteria=SuccessCriteria(
            expected_files_modified=["src/timestamps.py"],
            expected_content_contains={
                "src/timestamps.py": ["import datetime"],
            },
            expected_tests_pass=["test_get_current_timestamp", "test_format_timestamp"],
        ),
        constraints=TaskConstraints(
            allowed_paths=["src/timestamps.py"],
            require_tests_pass=True,
        ),
        tags=["bug-fix", "missing-import", "compilation"],
    ))

    # === ADD FEATURE ===
    tasks.append(BenchmarkTask(
        task_id="add_feature_01",
        name="Add Power Function",
        description="Add a power(base, exponent) function to the calculator module. It should return base raised to the power of exponent. Handle the case where exponent is 0 (return 1).",
        category=TaskCategory.ADD_FEATURE,
        difficulty=TaskDifficulty.EASY,
        language=TaskLanguage.PYTHON,
        initial_state=TaskState(files={
            "src/calculator.py": '''"""Calculator module."""


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def subtract(a: int, b: int) -> int:
    """Subtract b from a."""
    return a - b


def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


def divide(a: int, b: int) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
''',
            "tests/test_calculator.py": '''"""Tests for calculator module."""

import pytest
from src.calculator import add, subtract, multiply, divide


def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0


def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(1, 1) == 0


def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(0, 5) == 0


def test_divide():
    assert divide(10, 2) == 5.0
    with pytest.raises(ValueError):
        divide(10, 0)
''',
        }),
        success_criteria=SuccessCriteria(
            expected_content_contains={
                "src/calculator.py": ["def power("],
            },
            custom_checks=["check_power_function"],
        ),
        constraints=TaskConstraints(
            allowed_paths=["src/calculator.py", "tests/test_calculator.py"],
        ),
        expected_tests=["tests/test_calculator.py::test_power"],
        tags=["feature", "arithmetic", "new-function"],
    ))

    # === REFACTOR MODULE ===
    tasks.append(BenchmarkTask(
        task_id="refactor_01",
        name="Refactor Duplicate Code",
        description="Refactor the duplicate validation logic. Both get_user and get_order repeat the same validation pattern. Extract this into a shared validate_id function.",
        category=TaskCategory.REFACTOR_MODULE,
        difficulty=TaskDifficulty.MEDIUM,
        language=TaskLanguage.PYTHON,
        initial_state=TaskState(files={
            "src/services.py": '''"""Service module."""


def get_user(user_id: str) -> dict:
    """Get a user by ID."""
    # Validation logic
    if not user_id:
        raise ValueError("user_id cannot be empty")
    if not isinstance(user_id, str):
        raise TypeError("user_id must be a string")
    if len(user_id) != 36:
        raise ValueError("user_id must be a valid UUID")

    return {"id": user_id, "name": "Test User"}


def get_order(order_id: str) -> dict:
    """Get an order by ID."""
    # Same validation logic - duplicate!
    if not order_id:
        raise ValueError("order_id cannot be empty")
    if not isinstance(order_id, str):
        raise TypeError("order_id must be a string")
    if len(order_id) != 36:
        raise ValueError("order_id must be a valid UUID")

    return {"id": order_id, "total": 100.00}
''',
            "tests/test_services.py": '''"""Tests for services module."""

import pytest
from src.services import get_user, get_order


def test_get_user():
    user = get_user("12345678-1234-1234-1234-123456789abc")
    assert user["name"] == "Test User"


def test_get_user_empty_id():
    with pytest.raises(ValueError, match="cannot be empty"):
        get_user("")


def test_get_order():
    order = get_order("12345678-1234-1234-1234-123456789abc")
    assert order["total"] == 100.00


def test_get_order_invalid_type():
    with pytest.raises(TypeError, match="must be a string"):
        get_order(12345)
''',
        }),
        success_criteria=SuccessCriteria(
            expected_content_contains={
                "src/services.py": ["def validate_id("],
            },
            expected_content_not_contains={
                "src/services.py": ["# Same validation logic - duplicate!"],
            },
            expected_tests_pass=["test_get_user", "test_get_order"],
        ),
        constraints=TaskConstraints(
            allowed_paths=["src/services.py"],
            require_tests_pass=True,
        ),
        tags=["refactor", "dry", "extract-function"],
    ))

    # === DIAGNOSE BUG (no modifications) ===
    tasks.append(BenchmarkTask(
        task_id="diagnose_01",
        name="Diagnose Memory Leak",
        description="Diagnose why the process_data function is slow. Do NOT modify any files. Return your diagnosis as text explaining the issue.",
        category=TaskCategory.DIAGNOSE_BUG,
        difficulty=TaskDifficulty.MEDIUM,
        language=TaskLanguage.PYTHON,
        initial_state=TaskState(files={
            "src/processor.py": '''"""Data processor module."""


def process_data(items: list) -> list:
    """Process a list of data items."""
    results = []
    for item in items:
        # Inefficient: loads entire dataset each iteration
        dataset = load_full_dataset()
        result = transform(item, dataset)
        results.append(result)
    return results


def load_full_dataset() -> list:
    """Load the full dataset (simulated expensive operation)."""
    return list(range(100000))


def transform(item: int, dataset: list) -> int:
    """Transform an item using the dataset."""
    return item * len(dataset)
''',
        }),
        success_criteria=SuccessCriteria(
            expected_output_contains=["load_full_dataset", "outside the loop", "cache"],
        ),
        constraints=TaskConstraints(
            blocked_paths=["src/processor.py"],  # Cannot modify
        ),
        tags=["diagnosis", "performance", "no-modification"],
    ))

    # === MODIFY MULTIPLE FILES ===
    tasks.append(BenchmarkTask(
        task_id="multi_file_01",
        name="Add Logging Across Modules",
        description="Add structured logging to both the user service and order service. Each function should log when it's called and when it completes.",
        category=TaskCategory.MODIFY_MULTIPLE_FILES,
        difficulty=TaskDifficulty.MEDIUM,
        language=TaskLanguage.PYTHON,
        initial_state=TaskState(files={
            "src/user_service.py": '''"""User service module."""


def create_user(name: str, email: str) -> dict:
    """Create a new user."""
    return {"name": name, "email": email, "id": "usr-123"}


def get_user(user_id: str) -> dict:
    """Get a user by ID."""
    return {"name": "Test", "email": "test@example.com", "id": user_id}
''',
            "src/order_service.py": '''"""Order service module."""


def create_order(user_id: str, items: list) -> dict:
    """Create a new order."""
    return {"user_id": user_id, "items": items, "id": "ord-456"}


def cancel_order(order_id: str) -> dict:
    """Cancel an order."""
    return {"id": order_id, "status": "cancelled"}
''',
            "tests/test_services.py": '''"""Tests for services."""

from src.user_service import create_user, get_user
from src.order_service import create_order, cancel_order


def test_create_user():
    user = create_user("Test", "test@example.com")
    assert user["name"] == "Test"


def test_get_user():
    user = get_user("usr-123")
    assert user["email"] == "test@example.com"


def test_create_order():
    order = create_order("usr-123", ["item1"])
    assert order["id"] == "ord-456"


def test_cancel_order():
    result = cancel_order("ord-456")
    assert result["status"] == "cancelled"
''',
        }),
        success_criteria=SuccessCriteria(
            expected_content_contains={
                "src/user_service.py": ["log", "logging"],
                "src/order_service.py": ["log", "logging"],
            },
            expected_tests_pass=["test_create_user", "test_get_user", "test_create_order", "test_cancel_order"],
        ),
        constraints=TaskConstraints(
            allowed_paths=["src/user_service.py", "src/order_service.py"],
            require_tests_pass=True,
        ),
        tags=["multi-file", "logging", "cross-cutting"],
    ))

    # === FIX REGRESSION ===
    tasks.append(BenchmarkTask(
        task_id="fix_regression_01",
        name="Fix Broken After Refactor",
        description="The sanitize function was refactored and now breaks the login function. The sanitize function now returns None instead of an empty string when given empty input, causing login to fail.",
        category=TaskCategory.FIX_REGRESSION,
        difficulty=TaskDifficulty.EASY,
        language=TaskLanguage.PYTHON,
        initial_state=TaskState(files={
            "src/auth.py": '''"""Authentication module."""


def sanitize(username: str) -> str:
    """Sanitize username input."""
    if not username:
        return None  # Bug: should return ""
    return username.strip().lower()


def login(username: str, password: str) -> dict:
    """Authenticate a user."""
    clean_user = sanitize(username)
    if clean_user == "":  # This check now fails because None != ""
        raise ValueError("Username required")
    return {"username": clean_user, "authenticated": True}
''',
            "tests/test_auth.py": '''"""Tests for auth module."""

import pytest
from src.auth import login, sanitize


def test_sanitize_normal():
    assert sanitize("  Admin  ") == "admin"


def test_sanitize_empty():
    result = sanitize("")
    assert result == ""  # Should return empty string, not None


def test_login():
    result = login("Admin", "password")
    assert result["authenticated"] is True


def test_login_empty_username():
    with pytest.raises(ValueError, match="Username required"):
        login("", "password")
''',
        }),
        success_criteria=SuccessCriteria(
            expected_files_modified=["src/auth.py"],
            expected_content_contains={
                "src/auth.py": ['return ""'],
            },
            expected_tests_pass=["test_sanitize_normal", "test_sanitize_empty", "test_login", "test_login_empty_username"],
        ),
        constraints=TaskConstraints(
            allowed_paths=["src/auth.py"],
            require_tests_pass=True,
        ),
        tags=["regression", "null-handling", "refactor-break"],
    ))

    # === EDGE CASE HANDLING ===
    tasks.append(BenchmarkTask(
        task_id="edge_case_01",
        name="Handle Edge Cases in Parser",
        description="Fix the parse_numbers function to handle edge cases: empty input, non-numeric strings, and whitespace. Tests are failing for these cases.",
        category=TaskCategory.FIX_FAILING_TEST,
        difficulty=TaskDifficulty.MEDIUM,
        language=TaskLanguage.PYTHON,
        initial_state=TaskState(files={
            "src/parser.py": '''"""Parser module."""


def parse_numbers(text: str) -> list:
    """Parse comma-separated numbers."""
    parts = text.split(",")
    return [int(p) for p in parts]
''',
            "tests/test_parser.py": '''"""Tests for parser module."""

import pytest
from src.parser import parse_numbers


def test_parse_basic():
    assert parse_numbers("1,2,3") == [1, 2, 3]


def test_parse_empty():
    assert parse_numbers("") == []


def test_parse_whitespace():
    assert parse_numbers(" 1 , 2 , 3 ") == [1, 2, 3]


def test_parse_with_invalid():
    assert parse_numbers("1,abc,3") == [1, 3]  # Skip invalid
''',
        }),
        success_criteria=SuccessCriteria(
            expected_files_modified=["src/parser.py"],
            expected_tests_pass=["test_parse_basic", "test_parse_empty", "test_parse_whitespace", "test_parse_with_invalid"],
        ),
        constraints=TaskConstraints(
            allowed_paths=["src/parser.py"],
            require_tests_pass=True,
        ),
        tags=["edge-cases", "parsing", "error-handling"],
    ))

    return tasks


def get_task_by_id(task_id: str) -> BenchmarkTask | None:
    """Get a specific task by ID."""
    for task in get_benchmark_tasks():
        if task.task_id == task_id:
            return task
    return None


def get_tasks_by_category(category: TaskCategory) -> list:
    """Get all tasks in a category."""
    return [t for t in get_benchmark_tasks() if t.category == category]


def get_tasks_by_difficulty(difficulty: TaskDifficulty) -> list:
    """Get all tasks of a difficulty level."""
    return [t for t in get_benchmark_tasks() if t.difficulty == difficulty]
