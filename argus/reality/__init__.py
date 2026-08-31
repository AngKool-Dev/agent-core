"""ARGUS Production Reality Qualification - External-system validation and RC2 qualification.

This package provides production-reality qualification for ARGUS, validating behavior
when connected to real external systems and running as an actually installed application.
"""

from argus.reality.models import (
    CrashResumeResult,
    EnvironmentInfo,
    FailureCategory,
    InvariantId,
    InvariantResult,
    MCPCheckResult,
    ProviderAvailability,
    ProviderCheckResult,
    RealityRun,
    RealityScenarioResult,
    RealityStatus,
    ReleaseDecision,
    SecretCanaryResult,
    SubprocessCheckResult,
    WindowsCheckResult,
)
from argus.reality.environment import (
    ProductionEnvironment,
    capture_environment,
    get_safe_summary,
)
from argus.reality.providers import (
    RealProviderValidator,
    validate_provider,
    validate_providers,
)
from argus.reality.mcp import (
    RealMCPValidator,
    validate_mcp,
)
from argus.reality.subprocesses import (
    SubprocessRealityTester,
    test_subprocess_reality,
)
from argus.reality.windows import (
    WindowsHardeningTester,
    test_windows_hardening,
)
from argus.reality.secrets import (
    SecretSafetyAuditor,
    run_secret_audit,
)
from argus.reality.invariants import (
    InvariantTester,
    run_invariant_tests,
)
from argus.reality.scenarios import (
    RealityScenarioRunner,
    run_reality_scenarios,
)
from argus.reality.runner import (
    RealityRunner,
    run_reality_suite,
)
from argus.reality.evaluator import (
    RealityEvaluator,
    evaluate_reality_run,
)
from argus.reality.reporter import (
    RealityReporter,
    generate_reality_report,
)

__all__ = [
    # Models
    "CrashResumeResult",
    "EnvironmentInfo",
    "FailureCategory",
    "InvariantId",
    "InvariantResult",
    "MCPCheckResult",
    "ProviderAvailability",
    "ProviderCheckResult",
    "RealityRun",
    "RealityScenarioResult",
    "RealityStatus",
    "ReleaseDecision",
    "SecretCanaryResult",
    "SubprocessCheckResult",
    "WindowsCheckResult",
    # Environment
    "ProductionEnvironment",
    "capture_environment",
    "get_safe_summary",
    # Providers
    "RealProviderValidator",
    "validate_provider",
    "validate_providers",
    # MCP
    "RealMCPValidator",
    "validate_mcp",
    # Subprocess
    "SubprocessRealityTester",
    "test_subprocess_reality",
    # Windows
    "WindowsHardeningTester",
    "test_windows_hardening",
    # Secrets
    "SecretSafetyAuditor",
    "run_secret_audit",
    # Invariants
    "InvariantTester",
    "run_invariant_tests",
    # Scenarios
    "RealityScenarioRunner",
    "run_reality_scenarios",
    # Runner
    "RealityRunner",
    "run_reality_suite",
    # Evaluator
    "RealityEvaluator",
    "evaluate_reality_run",
    # Reporter
    "RealityReporter",
    "generate_reality_report",
]
