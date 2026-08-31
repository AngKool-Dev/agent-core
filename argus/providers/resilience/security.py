"""Security integration for provider resilience."""

import re
from typing import Any, Dict, List, Optional, Set

from argus.providers.resilience.errors import SecurityViolationError


class PoisoningDetector:
    """Detects data poisoning attempts in responses."""

    SUSPICIOUS_PATTERNS = [
        r"ignore\s+(previous|all)?\s*instructions",
        r"reveal\s+(your|the)?\s*(system\s+)?prompt",
        r"system\s+prompt\s+is",
        r"new\s+instructions?:",
        r"you\s+are\s+now\s+(in\s+)?",
        r"DAN\s+mode",
        r"jailbreak",
        r"override\s+safety",
    ]

    def __init__(self, custom_patterns: Optional[List[str]] = None):
        self._patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (self.SUSPICIOUS_PATTERNS + (custom_patterns or []))
        ]

    def check_response(self, response: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
        content = response.get("content", "")
        matches = []

        for pattern in self._patterns:
            if pattern.search(content):
                matches.append(pattern.pattern)

        return {
            "suspicious": len(matches) > 0,
            "matches": matches,
        }


class PromptInjectionGuard:
    """Guards against prompt injection in responses."""

    INJECTION_PATTERNS = [
        r"new\s+instructions?\s*:",
        r"ignore\s+(previous|above|all)\s+instructions?",
        r"you\s+are\s+now\s+(in\s+)?(admin|root|debug)",
        r"system\s+override",
        r"access\s+granted",
        r"reveal\s+(all\s+)?(secrets?|passwords?|keys?)",
    ]

    def __init__(self, custom_patterns: Optional[List[str]] = None):
        self._patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (self.INJECTION_PATTERNS + (custom_patterns or []))
        ]

    def check_response(self, response: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
        content = response.get("content", "")
        matches = []

        for pattern in self._patterns:
            if pattern.search(content):
                matches.append(pattern.pattern)

        return {
            "injected": len(matches) > 0,
            "matches": matches,
        }


class ResponseSanitizer:
    """Sanitizes sensitive data from responses."""

    SENSITIVE_PATTERNS = [
        (r"sk-[a-zA-Z0-9]{20,}", "***API_KEY***"),
        (r"(?i)password\s*[:=]\s*\S+", "password=***"),
        (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "***EMAIL***"),
        (r"https?://[^\s]+token=[^\s&]+", "***URL_WITH_TOKEN***"),
        (r"https?://[^\s]+api[_-]?key=[^\s&]+", "***URL_WITH_KEY***"),
    ]

    def __init__(self, custom_patterns: Optional[List[tuple]] = None):
        self._patterns = [
            (re.compile(pattern), replacement)
            for pattern, replacement in (self.SENSITIVE_PATTERNS + (custom_patterns or []))
        ]

    def sanitize(self, response: Dict[str, Any]) -> Dict[str, Any]:
        content = response.get("content", "")
        for pattern, replacement in self._patterns:
            content = pattern.sub(replacement, content)

        result = response.copy()
        result["content"] = content
        return result
