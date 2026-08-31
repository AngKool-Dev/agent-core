"""ARGUS security subsystem."""

from argus.security.errors import (
    ApprovalRequiredError,
    PermissionDeniedError,
    PolicyViolationError,
    PromptInjectionDetectedError,
    RiskTooHighError,
    SandboxError,
    SecretAccessError,
    SecurityError,
    TrustBoundaryError,
)
from argus.security.permissions import (
    PathScope,
    Permission,
    SecurityPolicy,
    create_default_policy,
    create_permissive_policy,
    create_restrictive_policy,
)
from argus.security.policy import (
    SecurityAction,
    SecurityDecision,
    SecurityPolicyEngine,
    create_security_engine,
)
from argus.security.risk import (
    RiskAssessment,
    RiskClassifier,
    RiskLevel,
)
from argus.security.trust import (
    TrustAssessment,
    TrustBoundary,
    TrustLevel,
)
from argus.security.approval import (
    Approval,
    ApprovalManager,
    ApprovalRequest,
    ApprovalScope,
    ApprovalStatus,
)
from argus.security.secrets import SecretManager, SecretReference
from argus.security.audit import AuditEvent, AuditEventType, AuditTrail
from argus.security.sandbox import Sandbox, SandboxConfig

__all__ = [
    # Errors
    "ApprovalRequiredError",
    "PermissionDeniedError",
    "PolicyViolationError",
    "PromptInjectionDetectedError",
    "RiskTooHighError",
    "SandboxError",
    "SecretAccessError",
    "SecurityError",
    "TrustBoundaryError",
    # Permissions
    "PathScope",
    "Permission",
    "SecurityPolicy",
    "create_default_policy",
    "create_permissive_policy",
    "create_restrictive_policy",
    # Policy engine
    "SecurityAction",
    "SecurityDecision",
    "SecurityPolicyEngine",
    "create_security_engine",
    # Risk
    "RiskAssessment",
    "RiskClassifier",
    "RiskLevel",
    # Trust
    "TrustAssessment",
    "TrustBoundary",
    "TrustLevel",
    # Approval
    "Approval",
    "ApprovalManager",
    "ApprovalRequest",
    "ApprovalScope",
    "ApprovalStatus",
    # Secrets
    "SecretManager",
    "SecretReference",
    # Audit
    "AuditEvent",
    "AuditEventType",
    "AuditTrail",
    # Sandbox
    "Sandbox",
    "SandboxConfig",
]