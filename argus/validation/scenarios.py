"""Real-world validation scenarios for ARGUS agent validation."""

from typing import Optional

from argus.validation.models import (
    ValidationCategory,
    ValidationConstraint,
    ValidationScenario,
    ValidationTier,
)


def scenario_a_file_creation() -> ValidationScenario:
    """Scenario A: Create a Python module with proper structure."""
    return ValidationScenario(
        scenario_id="val-a-file-creation",
        name="Python Module Creation",
        description="Create a well-structured Python module with classes, docstrings, and type hints",
        category=ValidationCategory.FILE_MANIPULATION,
        tier=ValidationTier.TIER_1,
        prompt="Create a Python module named 'calculator.py' in the current directory. "
        "It should implement a Calculator class with add, subtract, multiply, divide methods. "
        "Include proper docstrings, type hints, and error handling for division by zero.",
        expected_outcome="A calculator.py file exists with a Calculator class containing "
        "add, subtract, multiply, divide methods with docstrings and type hints",
        success_criteria=[
            "calculator.py file exists",
            "Calculator class is defined",
            "add method exists with type hints",
            "subtract method exists with type hints",
            "multiply method exists with type hints",
            "divide method exists with type hints",
            "divide method handles division by zero",
            "All methods have docstrings",
        ],
        expected_files=["calculator.py"],
        expected_tools=["write_file", "create_file"],
        timeout_seconds=120,
        tags=["file-creation", "python", "basic"],
    )


def scenario_b_debugging() -> ValidationScenario:
    """Scenario B: Debug and fix a broken Python script."""
    return ValidationScenario(
        scenario_id="val-b-debugging",
        name="Debug Broken Script",
        description="Identify and fix bugs in a provided Python script",
        category=ValidationCategory.DEBUGGING,
        tier=ValidationTier.TIER_2,
        prompt="There is a file 'broken_sort.py' with a bubble sort implementation that has "
        "three bugs. Find and fix all bugs. The bugs are: off-by-one error in the outer loop, "
        "incorrect comparison operator, and missing return statement.",
        expected_outcome="broken_sort.py is fixed with all three bugs resolved and the sort works correctly",
        success_criteria=[
            "Off-by-one error in outer loop is fixed",
            "Comparison operator is corrected",
            "Return statement is added",
            "Function returns sorted list",
        ],
        initial_state={
            "broken_sort.py": '''def bubble_sort(arr):
    """Sort a list using bubble sort."""
    n = len(arr)
    for i in range(n):  # Bug 1: should be n-1
        for j in range(n - i - 1):
            if arr[j] < arr[j + 1]:  # Bug 2: should be >
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    # Bug 3: missing return

# Test
print(bubble_sort([3, 1, 4, 1, 5, 9, 2, 6]))
'''
        },
        expected_files=["broken_sort.py"],
        expected_tools=["read_file", "write_file", "edit_file"],
        timeout_seconds=180,
        tags=["debugging", "python", "algorithms"],
    )


def scenario_c_refactoring() -> ValidationScenario:
    """Scenario C: Refactor a monolithic function into clean code."""
    return ValidationScenario(
        scenario_id="val-c-refactoring",
        name="Refactor Monolithic Function",
        description="Refactor a large monolithic function into smaller, well-named functions",
        category=ValidationCategory.REFACTORING,
        tier=ValidationTier.TIER_2,
        prompt="Refactor the 'process_data' function in 'data_processor.py' into smaller, "
        "single-responsibility functions. The function currently handles validation, "
        "transformation, and output formatting all in one place. Separate these concerns "
        "into distinct functions while maintaining the same external behavior.",
        expected_outcome="data_processor.py is refactored with separate functions for "
        "validation, transformation, and formatting",
        success_criteria=[
            "Original process_data function is refactored",
            "Separate validation function exists",
            "Separate transformation function exists",
            "Separate formatting function exists",
            "External behavior is preserved",
            "Each function has a single responsibility",
        ],
        initial_state={
            "data_processor.py": '''def process_data(data):
    """Process input data - does everything."""
    # Validation
    if not data:
        raise ValueError("Data cannot be empty")
    if not isinstance(data, list):
        raise TypeError("Data must be a list")
    for item in data:
        if not isinstance(item, dict):
            raise TypeError("Each item must be a dict")
        if "value" not in item:
            raise ValueError("Each item must have a 'value' key")

    # Transformation
    result = []
    for item in data:
        transformed = {
            "original": item["value"],
            "doubled": item["value"] * 2,
            "squared": item["value"] ** 2,
        }
        result.append(transformed)

    # Formatting
    output = "=== Results ===\\n"
    for i, r in enumerate(result):
        output += f"{i+1}. original={r['original']}, doubled={r['doubled']}, squared={r['squared']}\\n"
    output += f"Total: {len(result)} items\\n"
    return output
'''
        },
        expected_files=["data_processor.py"],
        expected_tools=["read_file", "write_file", "edit_file"],
        timeout_seconds=180,
        tags=["refactoring", "python", "clean-code"],
    )


def scenario_d_testing() -> ValidationScenario:
    """Scenario D: Write comprehensive tests for existing code."""
    return ValidationScenario(
        scenario_id="val-d-testing",
        name="Write Unit Tests",
        description="Write comprehensive unit tests for an existing module",
        category=ValidationCategory.TESTING,
        tier=ValidationTier.TIER_2,
        prompt="Write comprehensive unit tests for the 'string_utils.py' module. "
        "Create a file 'test_string_utils.py' with tests for all functions, "
        "including edge cases, error cases, and parameterized tests where appropriate.",
        expected_outcome="test_string_utils.py exists with comprehensive tests covering "
        "all functions, edge cases, and error cases",
        success_criteria=[
            "test_string_utils.py file exists",
            "Tests for reverse_string function",
            "Tests for count_vowels function",
            "Tests for is_palindrome function",
            "Tests for truncate function",
            "Edge cases are covered (empty strings, None, etc.)",
            "Error cases are tested",
        ],
        initial_state={
            "string_utils.py": '''def reverse_string(s):
    """Reverse a string."""
    return s[::-1]

def count_vowels(s):
    """Count vowels in a string."""
    return sum(1 for c in s.lower() if c in "aeiou")

def is_palindrome(s):
    """Check if a string is a palindrome."""
    cleaned = "".join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]

def truncate(s, max_length):
    """Truncate a string to max_length."""
    if len(s) <= max_length:
        return s
    return s[:max_length - 3] + "..."
'''
        },
        expected_files=["test_string_utils.py"],
        expected_tools=["read_file", "write_file"],
        timeout_seconds=180,
        tags=["testing", "python", "unit-tests"],
    )


def scenario_e_git_workflow() -> ValidationScenario:
    """Scenario E: Execute a proper Git workflow."""
    return ValidationScenario(
        scenario_id="val-e-git-workflow",
        name="Git Workflow Execution",
        description="Execute a proper Git workflow with branching, committing, and merging",
        category=ValidationCategory.GIT_WORKFLOW,
        tier=ValidationTier.TIER_3,
        prompt="Initialize a git repository, create a feature branch called 'feature/add-logging', "
        "add logging to the 'app.py' file, commit the changes with a proper commit message, "
        "then merge the feature branch back into main. Ensure the commit message follows "
        "conventional commits format.",
        expected_outcome="Git repo initialized, feature branch created with logging changes, "
        "committed with conventional commit message, and merged to main",
        success_criteria=[
            "Git repository is initialized",
            "Feature branch 'feature/add-logging' is created",
            "Logging is added to app.py",
            "Changes are committed with conventional commit message",
            "Feature branch is merged to main",
            "Main branch contains the logging changes",
        ],
        initial_state={
            "app.py": '''def main():
    print("Application started")
    # Application logic here
    print("Application finished")

if __name__ == "__main__":
    main()
'''
        },
        expected_files=[".git", "app.py"],
        expected_tools=["git_init", "git_branch", "git_add", "git_commit", "git_merge", "write_file"],
        timeout_seconds=240,
        tags=["git", "workflow", "version-control"],
    )


def scenario_f_dependency_management() -> ValidationScenario:
    """Scenario F: Manage project dependencies."""
    return ValidationScenario(
        scenario_id="val-f-dependency-management",
        name="Dependency Management",
        description="Add, update, and resolve project dependencies",
        category=ValidationCategory.DEPENDENCY_MANAGEMENT,
        tier=ValidationTier.TIER_2,
        prompt="Create a requirements.txt file with the following dependencies: "
        "requests>=2.28.0, pytest>=7.0.0, black>=22.0.0. Then create a setup.py "
        "that reads from requirements.txt and configures the package metadata.",
        expected_outcome="requirements.txt and setup.py are created with proper dependency specifications",
        success_criteria=[
            "requirements.txt exists with correct dependencies",
            "requests>=2.28.0 is specified",
            "pytest>=7.0.0 is specified",
            "black>=22.0.0 is specified",
            "setup.py exists and reads from requirements.txt",
            "Package metadata is configured",
        ],
        expected_files=["requirements.txt", "setup.py"],
        expected_tools=["write_file"],
        timeout_seconds=120,
        tags=["dependencies", "python", "packaging"],
    )


def scenario_g_security_review() -> ValidationScenario:
    """Scenario G: Security review and hardening."""
    return ValidationScenario(
        scenario_id="val-g-security-review",
        name="Security Review and Hardening",
        description="Review code for security vulnerabilities and apply fixes",
        category=ValidationCategory.SECURITY,
        tier=ValidationTier.TIER_3,
        prompt="Review the 'auth.py' file for security vulnerabilities. Fix any issues found "
        "including: hardcoded secrets, weak hashing, missing input validation, and "
        "improper error handling that could leak information. Ensure the fixes follow "
        "security best practices.",
        expected_outcome="auth.py is hardened with no hardcoded secrets, strong hashing, "
        "input validation, and proper error handling",
        success_criteria=[
            "No hardcoded secrets remain",
            "Strong hashing algorithm is used (bcrypt/scrypt/argon2)",
            "Input validation is implemented",
            "Error messages don't leak sensitive information",
            "Security best practices are followed",
        ],
        initial_state={
            "auth.py": '''import hashlib

SECRET_KEY = "my-secret-key-123"

def hash_password(password):
    """Hash a password."""
    return hashlib.md5(password.encode()).hexdigest()

def authenticate(username, password):
    """Authenticate a user."""
    if username == "admin" and hash_password(password) == "5f4dcc3b5aa765d61d8327deb882cf99":
        return True
    raise Exception(f"Authentication failed for user {username} with password length {len(password)}")

def get_user_data(user_id):
    """Get user data - no validation."""
    return query_database(f"SELECT * FROM users WHERE id = {user_id}")
'''
        },
        expected_files=["auth.py"],
        expected_tools=["read_file", "write_file", "edit_file"],
        timeout_seconds=240,
        tags=["security", "hardening", "authentication"],
    )


def scenario_h_multi_step_reasoning() -> ValidationScenario:
    """Scenario H: Multi-step reasoning across domains."""
    return ValidationScenario(
        scenario_id="val-h-multi-step-reasoning",
        name="Multi-Step API Implementation",
        description="Design and implement a REST API with multiple components",
        category=ValidationCategory.MULTI_STEP_REASONING,
        tier=ValidationTier.TIER_3,
        prompt="Create a simple REST API for a todo list application. The API should have: "
        "1) A 'models.py' with a TodoItem class, 2) A 'routes.py' with CRUD endpoints, "
        "3) A 'main.py' that sets up the Flask/FastAPI app. Include proper error handling, "
        "input validation, and JSON responses.",
        expected_outcome="A working REST API with models, routes, and main app file",
        success_criteria=[
            "models.py exists with TodoItem class",
            "routes.py exists with CRUD endpoints",
            "main.py exists with app setup",
            "Error handling is implemented",
            "Input validation is present",
            "JSON responses are used",
        ],
        expected_files=["models.py", "routes.py", "main.py"],
        expected_tools=["write_file", "create_file"],
        timeout_seconds=300,
        tags=["api", "multi-file", "reasoning"],
    )


def scenario_i_documentation() -> ValidationScenario:
    """Scenario I: Generate comprehensive documentation."""
    return ValidationScenario(
        scenario_id="val-i-documentation",
        name="Generate Documentation",
        description="Generate comprehensive documentation for a codebase",
        category=ValidationCategory.DOCUMENTATION,
        tier=ValidationTier.TIER_2,
        prompt="Generate comprehensive documentation for the 'math_ops.py' module. "
        "Create a 'README.md' that includes: overview, installation, usage examples, "
        "API reference for all functions, and contribution guidelines.",
        expected_outcome="README.md exists with comprehensive documentation covering all required sections",
        success_criteria=[
            "README.md file exists",
            "Overview section is present",
            "Installation section is present",
            "Usage examples are provided",
            "API reference covers all functions",
            "Contribution guidelines are included",
        ],
        initial_state={
            "math_ops.py": '''def add(a, b):
    """Add two numbers."""
    return a + b

def subtract(a, b):
    """Subtract b from a."""
    return a - b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b

def divide(a, b):
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def power(base, exponent):
    """Raise base to the power of exponent."""
    return base ** exponent

def factorial(n):
    """Calculate factorial of n."""
    if n < 0:
        raise ValueError("Factorial not defined for negative numbers")
    if n == 0:
        return 1
    return n * factorial(n - 1)
'''
        },
        expected_files=["README.md"],
        expected_tools=["read_file", "write_file"],
        timeout_seconds=180,
        tags=["documentation", "readme", "api-reference"],
    )


def scenario_j_recovery_task() -> ValidationScenario:
    """Scenario J: Task requiring recovery from failures."""
    return ValidationScenario(
        scenario_id="val-j-recovery-task",
        name="Recovery from Failures",
        description="Complete a task that involves recovering from expected failures",
        category=ValidationCategory.MULTI_STEP_REASONING,
        tier=ValidationTier.TIER_4,
        prompt="Create a 'data_pipeline.py' that reads from 'input.csv', processes the data "
        "(convert all names to uppercase, calculate average of numeric columns), and writes "
        "to 'output.csv'. The input file may have missing values, incorrect types, or be "
        "malformed. Handle all these cases gracefully with proper error handling and logging.",
        expected_outcome="data_pipeline.py is created with robust error handling that processes "
        "valid rows and logs/skips invalid ones",
        success_criteria=[
            "data_pipeline.py file exists",
            "Reads from input.csv",
            "Converts names to uppercase",
            "Calculates average of numeric columns",
            "Handles missing values gracefully",
            "Handles incorrect types gracefully",
            "Writes to output.csv",
            "Includes logging for skipped rows",
        ],
        initial_state={
            "input.csv": '''name,age,score
Alice,25,85.5
Bob,30,92.0
Charlie,,78.5
David,abc,88.0
Eve,28,
Frank,35,95.5
'''
        },
        expected_files=["data_pipeline.py", "output.csv"],
        expected_tools=["read_file", "write_file"],
        timeout_seconds=300,
        tags=["recovery", "error-handling", "data-processing"],
    )


def get_all_scenarios() -> list:
    """Get all validation scenarios."""
    return [
        scenario_a_file_creation(),
        scenario_b_debugging(),
        scenario_c_refactoring(),
        scenario_d_testing(),
        scenario_e_git_workflow(),
        scenario_f_dependency_management(),
        scenario_g_security_review(),
        scenario_h_multi_step_reasoning(),
        scenario_i_documentation(),
        scenario_j_recovery_task(),
    ]


def get_scenario_by_id(scenario_id: str) -> Optional[ValidationScenario]:
    """Get a scenario by its ID."""
    for scenario in get_all_scenarios():
        if scenario.scenario_id == scenario_id:
            return scenario
    return None


def get_scenarios_by_tier(tier: ValidationTier) -> list:
    """Get all scenarios for a given tier."""
    return [s for s in get_all_scenarios() if s.tier == tier]


def get_scenarios_by_category(category: ValidationCategory) -> list:
    """Get all scenarios for a given category."""
    return [s for s in get_all_scenarios() if s.category == category]
