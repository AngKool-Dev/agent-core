import os

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "real_runtime: marks tests that require a real runtime binary (Hermes, Kilo, OpenCode)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip real_runtime tests unless AGENTCORE_REAL_RUNTIME is set."""
    skip_real = not os.environ.get("AGENTCORE_REAL_RUNTIME")
    reason = "Skipping real-runtime test (set AGENTCORE_REAL_RUNTIME=1 to enable)"
    for item in items:
        if "real_runtime" in item.keywords and skip_real:
            item.add_marker(pytest.mark.skip(reason=reason))
