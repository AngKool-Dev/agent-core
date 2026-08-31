"""Real provider smoke tests for ARGUS qualification.

These tests are opt-in and only run when explicitly enabled.
They make actual API calls to configured providers.

Set ARGUS_REAL_PROVIDER_TESTS=1 to enable.
"""

import os
import sys

import pytest

# Skip all tests in this module unless explicitly enabled
pytestmark = pytest.mark.skipif(
    os.environ.get("ARGUS_REAL_PROVIDER_TESTS") != "1",
    reason="Real provider tests require ARGUS_REAL_PROVIDER_TESTS=1",
)


class TestRealProviders:
    """Tests that make actual API calls to configured providers."""

    def test_provider_discovery(self):
        """Test that configured providers can be discovered."""
        from argus.config import ArgusConfig
        config = ArgusConfig()

        hub_providers = config.get("model_hub.providers", {})
        assert isinstance(hub_providers, dict)

        # Check which providers are configured
        configured = []
        for name, pconfig in hub_providers.items():
            if pconfig.get("enabled", False):
                configured.append(name)

        # At least ollama should be available locally
        print(f"Configured providers: {configured}")

    def test_ollama_health_check(self):
        """Test Ollama health check if available."""
        try:
            from argus.model import create_model_from_config
            model = create_model_from_config({
                "provider": "ollama",
                "name": "llama3",
            })
            if model is None:
                pytest.skip("Ollama model could not be created")

            if hasattr(model, "health"):
                try:
                    health = model.health()
                    print(f"Ollama health: {health}")
                except Exception as e:
                    pytest.skip(f"Ollama health check failed: {e}")
        except Exception as e:
            pytest.skip(f"Ollama not available: {e}")

    def test_ollama_list_models(self):
        """Test Ollama list models if available."""
        try:
            from argus.model import create_model_from_config
            model = create_model_from_config({
                "provider": "ollama",
                "name": "llama3",
            })
            if model is None:
                pytest.skip("Ollama model could not be created")

            if hasattr(model, "list_models"):
                try:
                    models = model.list_models()
                    print(f"Ollama models: {models}")
                except Exception as e:
                    pytest.skip(f"Ollama list models failed: {e}")
        except Exception as e:
            pytest.skip(f"Ollama not available: {e}")

    def test_openrouter_health_check(self):
        """Test OpenRouter health check if configured."""
        from argus.config import ArgusConfig
        config = ArgusConfig()

        hub_providers = config.get("model_hub.providers", {})
        if "openrouter" not in hub_providers:
            pytest.skip("Openrouter not configured")

        openrouter_config = hub_providers["openrouter"]
        if not openrouter_config.get("enabled", False):
            pytest.skip("Openrouter not enabled")

        # Check for API key
        api_key = openrouter_config.get("api_key", "")
        if not api_key:
            # Check environment
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            pytest.skip("OpenRouter API key not configured")

        try:
            from argus.model import create_model_from_config
            model = create_model_from_config({
                "provider": "openrouter",
                "name": "auto",
                "api_key": api_key,
            })
            if model is None:
                pytest.skip("OpenRouter model could not be created")

            if hasattr(model, "health"):
                try:
                    health = model.health()
                    print(f"OpenRouter health: {health}")
                except Exception as e:
                    pytest.skip(f"OpenRouter health check failed: {e}")
        except Exception as e:
            pytest.skip(f"OpenRouter not available: {e}")

    def test_gemini_health_check(self):
        """Test Gemini health check if configured."""
        from argus.config import ArgusConfig
        config = ArgusConfig()

        hub_providers = config.get("model_hub.providers", {})
        if "gemini" not in hub_providers:
            pytest.skip("Gemini not configured")

        gemini_config = hub_providers["gemini"]
        if not gemini_config.get("enabled", False):
            pytest.skip("Gemini not enabled")

        # Check for API key
        api_key = gemini_config.get("api_key", "")
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            pytest.skip("Gemini API key not configured")

        try:
            from argus.model import create_model_from_config
            model = create_model_from_config({
                "provider": "gemini",
                "name": "gemini-2.0-flash",
                "api_key": api_key,
            })
            if model is None:
                pytest.skip("Gemini model could not be created")

            if hasattr(model, "health"):
                try:
                    health = model.health()
                    print(f"Gemini health: {health}")
                except Exception as e:
                    pytest.skip(f"Gemini health check failed: {e}")
        except Exception as e:
            pytest.skip(f"Gemini not available: {e}")


class TestProviderClassification:
    """Tests that verify provider availability classification."""

    def test_provider_availability_classification(self):
        """Test that providers are correctly classified."""
        from argus.reality.models import ProviderAvailability

        # Verify all availability states exist
        availabilities = [a.value for a in ProviderAvailability]
        assert "available" in availabilities
        assert "unavailable" in availabilities
        assert "misconfigured" in availabilities
        assert "auth_failed" in availabilities
        assert "rate_limited" in availabilities
        assert "network_failed" in availabilities
        assert "invalid_response" in availabilities
        assert "timeout" in availabilities
        assert "quarantined" in availabilities
        assert "skipped" in availabilities

    def test_failure_category_classification(self):
        """Test that failure categories are correctly classified."""
        from argus.reality.models import FailureCategory

        # Verify all failure categories exist
        categories = [c.value for c in FailureCategory]
        assert "agent_failure" in categories
        assert "infrastructure_failure" in categories
        assert "external_provider_failure" in categories
        assert "configuration_failure" in categories
        assert "security_block" in categories
        assert "expected_denial" in categories
        assert "skipped" in categories
