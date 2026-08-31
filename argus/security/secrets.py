"""Secrets management for ARGUS."""

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# Patterns that indicate secrets
SECRET_PATTERNS: List[tuple] = [
    (r"(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?", "api_key"),
    (r"(?:secret[_-]?key|secretkey)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?", "secret_key"),
    (r"(?:access[_-]?token|accesstoken)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?", "access_token"),
    (r"(?:auth[_-]?token|authtoken)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?", "auth_token"),
    (r"(?:password|passwd)\s*[:=]\s*['\"]?([^\s'\"]{8,})['\"]?", "password"),
    (r"(?:private[_-]?key|privatekey)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-+/=]{32,})['\"]?", "private_key"),
    (r"(?:bearer)\s+([a-zA-Z0-9_\-\.]{16,})", "bearer_token"),
    (r"gh[pousr]_[A-Za-z0-9_]{36,}", "github_token"),
    (r"sk-[a-zA-Z0-9]{48}", "openai_key"),
    (r"xox[baprs]-[A-Za-z0-9-]+", "slack_token"),
]

# Environment variable names that typically contain secrets
SECRET_ENV_VARS: Set[str] = {
    "API_KEY", "APIKEY", "SECRET_KEY", "SECRETKEY",
    "ACCESS_TOKEN", "AUTH_TOKEN", "PASSWORD", "PASSWD",
    "PRIVATE_KEY", "PRIVATEKEY", "CLIENT_SECRET",
    "GITHUB_TOKEN", "GH_TOKEN", "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY", "SLACK_TOKEN", "AWS_SECRET",
    "DATABASE_URL", "DB_PASSWORD", "REDIS_PASSWORD",
}


@dataclass
class SecretReference:
    """Reference to a secret (without the actual value)."""
    name: str
    type: str
    source: str = ""

    def __str__(self) -> str:
        return f"[REDACTED:{self.type}:{self.name}]"


class SecretManager:
    """Manages secrets access and redaction."""

    def __init__(self):
        self._secrets: Dict[str, str] = {}
        self._loaded_from_env: Set[str] = set()

    def load_from_env(self, prefix: str = "") -> None:
        """Load secrets from environment variables."""
        for key, value in os.environ.items():
            if self._is_secret_var(key):
                name = key.lower()
                if prefix:
                    name = f"{prefix}:{name}"
                self._secrets[name] = value
                self._loaded_from_env.add(name)

    def set_secret(self, name: str, value: str) -> None:
        """Set a secret."""
        self._secrets[name.lower()] = value

    def get_secret(self, name: str) -> Optional[str]:
        """Get a secret."""
        return self._secrets.get(name.lower())

    def get_secret_for_capability(self, capability_id: str) -> Optional[Dict[str, str]]:
        """Get secrets needed for a capability."""
        # Return relevant secrets based on capability
        secrets = {}
        for name, value in self._secrets.items():
            if self._is_relevant_secret(name, capability_id):
                secrets[name] = value
        return secrets if secrets else None

    def redact(self, text: str) -> str:
        """Redact secrets from text."""
        redacted = text
        for pattern, secret_type in SECRET_PATTERNS:
            redacted = re.sub(pattern, f"[REDACTED:{secret_type}]", redacted, flags=re.IGNORECASE)

        # Also redact known secret values
        for name, value in self._secrets.items():
            if value and len(value) > 8:
                # Escape special regex characters
                escaped = re.escape(value)
                redacted = re.sub(escaped, f"[REDACTED:{name}]", redacted)

        return redacted

    def redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact secrets from a dictionary."""
        redacted = {}
        for key, value in data.items():
            if isinstance(value, str):
                redacted[key] = self.redact(value)
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value)
            else:
                redacted[key] = value
        return redacted

    def _is_secret_var(self, name: str) -> bool:
        """Check if an environment variable name suggests a secret."""
        upper = name.upper()
        for secret_name in SECRET_ENV_VARS:
            if secret_name in upper:
                return True
        return False

    def _is_relevant_secret(self, secret_name: str, capability_id: str) -> bool:
        """Check if a secret is relevant for a capability."""
        # Map capabilities to likely needed secrets
        secret_mappings = {
            "github.get_repo": ["github_token", "gh_token", "api_key"],
            "github.search_repos": ["github_token", "gh_token"],
            "github.create_issue": ["github_token", "gh_token"],
            "web.read": ["api_key"],
            "youtube.get_info": ["api_key", "youtube_api_key"],
        }
        relevant = secret_mappings.get(capability_id, [])
        for r in relevant:
            if r in secret_name:
                return True
        return False

    @property
    def secret_names(self) -> List[str]:
        """Get list of secret names (not values)."""
        return list(self._secrets.keys())

    def __len__(self) -> int:
        return len(self._secrets)

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._secrets