"""Security errors for ARGUS."""

from typing import Optional


class SecurityError(Exception):
    """Base security error."""

    def __init__(self, message: str, reason: str = "", capability_id: str = ""):
        super().__init__(message)
        self.reason = reason
        self.capability_id = capability_id


class PermissionDeniedError(SecurityError):
    """Raised when a capability is denied by policy."""
    pass


class ApprovalRequiredError(SecurityError):
    """Raised when user approval is required."""

    def __init__(self, message: str, request_id: str = "", capability_id: str = "", command: str = ""):
        super().__init__(message, capability_id=capability_id)
        self.request_id = request_id
        self.command = command


class RiskTooHighError(SecurityError):
    """Raised when the risk level exceeds the threshold."""
    pass


class TrustBoundaryError(SecurityError):
    """Raised when external content attempts to cross trust boundary."""
    pass


class SecretAccessError(SecurityError):
    """Raised on unauthorized secret access."""
    pass


class PolicyViolationError(SecurityError):
    """Raised when a policy is violated."""

    def __init__(self, message: str, violation_type: str = "", capability_id: str = ""):
        super().__init__(message, capability_id=capability_id)
        self.violation_type = violation_type


class SandboxError(SecurityError):
    """Raised when a sandbox violation occurs."""
    pass


class PromptInjectionDetectedError(SecurityError):
    """Raised when prompt injection is detected in external content."""

    def __init__(self, message: str, source: str = "", content_preview: str = ""):
        super().__init__(message)
        self.source = source
        self.content_preview = content_preview