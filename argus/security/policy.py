"""Security policy engine - the main security gatekeeper."""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from argus.security.audit import AuditEventType, AuditTrail
from argus.security.errors import (
    ApprovalRequiredError,
    PermissionDeniedError,
    RiskTooHighError,
    SecurityError,
    TrustBoundaryError,
)
from argus.security.permissions import Permission, SecurityPolicy, create_default_policy
from argus.security.risk import RiskAssessment, RiskClassifier, RiskLevel
from argus.security.sandbox import Sandbox, SandboxConfig
from argus.security.secrets import SecretManager
from argus.security.trust import TrustAssessment, TrustBoundary, TrustLevel


class SecurityAction(str, Enum):
    """Possible security actions."""
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"
    SANDBOX = "sandbox"
    REDACT = "redact"


@dataclass
class SecurityDecision:
    """Result of a security evaluation."""
    allowed: bool
    action: SecurityAction
    risk_level: RiskLevel
    reason: str
    policy: str = ""
    scopes: List[str] = field(default_factory=list)
    requires_approval: bool = False
    audit_id: str = ""
    request_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "action": self.action.value,
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "policy": self.policy,
            "scopes": self.scopes,
            "requires_approval": self.requires_approval,
            "audit_id": self.audit_id,
            "request_id": self.request_id,
        }


class SecurityPolicyEngine:
    """Main security policy engine - the gatekeeper."""

    def __init__(
        self,
        policy: Optional[SecurityPolicy] = None,
        risk_classifier: Optional[RiskClassifier] = None,
        trust_boundary: Optional[TrustBoundary] = None,
        secret_manager: Optional[SecretManager] = None,
        sandbox: Optional[Sandbox] = None,
        audit_trail: Optional[AuditTrail] = None,
    ):
        self._policy = policy or create_default_policy()
        self._risk_classifier = risk_classifier or RiskClassifier()
        self._trust_boundary = trust_boundary or TrustBoundary()
        self._secret_manager = secret_manager or SecretManager()
        self._sandbox = sandbox or Sandbox()
        self._audit = audit_trail or AuditTrail()

    @property
    def audit(self) -> AuditTrail:
        return self._audit

    @property
    def policy(self) -> SecurityPolicy:
        return self._policy

    def evaluate(
        self,
        capability_id: str,
        input_data: Dict[str, Any],
        run_id: str = "",
    ) -> SecurityDecision:
        """Evaluate whether a capability invocation is allowed."""
        # 1. Check if capability is denied entirely
        if capability_id in self._policy.denied_capabilities:
            self._audit.record(
                AuditEventType.PERMISSION_DENIED,
                capability_id=capability_id,
                run_id=run_id,
                reason="Capability denied by policy",
            )
            return SecurityDecision(
                allowed=False,
                action=SecurityAction.DENY,
                risk_level=RiskLevel.CRITICAL,
                reason=f"Capability {capability_id} is denied by policy",
                policy="denied_capabilities",
            )

        # 2. Get capability permission
        permission = self._policy.get_capability_permission(capability_id)

        # 3. Assess risk
        risk_assessment = self._risk_classifier.assess_invocation(capability_id, input_data)

        # 4. Check sandbox
        sandbox_allowed, sandbox_reason = self._sandbox.validate_invocation(capability_id, input_data)
        if not sandbox_allowed:
            self._audit.record(
                AuditEventType.POLICY_VIOLATION,
                capability_id=capability_id,
                run_id=run_id,
                reason=sandbox_reason,
                risk_level=risk_assessment.level.value,
            )
            return SecurityDecision(
                allowed=False,
                action=SecurityAction.DENY,
                risk_level=risk_assessment.level,
                reason=f"Sandbox violation: {sandbox_reason}",
                policy="sandbox",
            )

        # 5. Evaluate based on permission and risk
        if permission == Permission.DENY:
            return SecurityDecision(
                allowed=False,
                action=SecurityAction.DENY,
                risk_level=risk_assessment.level,
                reason=f"Capability {capability_id} is denied",
                policy="capability_permission",
            )

        if permission == Permission.ALLOW:
            # Even allowed capabilities have risk limits
            max_risk = RiskLevel(self._policy.max_risk_level) if hasattr(self._policy, 'max_risk_level') else RiskLevel.HIGH
            if risk_assessment.level > max_risk:
                return SecurityDecision(
                    allowed=False,
                    action=SecurityAction.DENY,
                    risk_level=risk_assessment.level,
                    reason=f"Risk level {risk_assessment.level.value} exceeds maximum {max_risk.value}",
                    policy="risk_limit",
                )

            self._audit.record(
                AuditEventType.PERMISSION_GRANTED,
                capability_id=capability_id,
                run_id=run_id,
                decision="allow",
                risk_level=risk_assessment.level.value,
            )
            return SecurityDecision(
                allowed=True,
                action=SecurityAction.ALLOW,
                risk_level=risk_assessment.level,
                reason="Allowed by policy",
                policy="capability_permission",
            )

        if permission == Permission.ASK:
            return SecurityDecision(
                allowed=False,
                action=SecurityAction.ASK,
                risk_level=risk_assessment.level,
                reason=f"Capability {capability_id} requires approval",
                policy="capability_permission",
                requires_approval=True,
            )

        # Default: deny
        return SecurityDecision(
            allowed=False,
            action=SecurityAction.DENY,
            risk_level=risk_assessment.level,
            reason="Default deny",
            policy="default",
        )

    def evaluate_content(self, content: str, source: str = "") -> TrustAssessment:
        """Evaluate trustworthiness of external content."""
        assessment = self._trust_boundary.check_content(content, source)

        if assessment.injection_detected:
            self._audit.record(
                AuditEventType.INJECTION_DETECTED,
                details={"source": source, "type": assessment.injection_type},
            )

        return assessment

    def redact_secrets(self, text: str) -> str:
        """Redact secrets from text."""
        return self._secret_manager.redact(text)

    def get_secret(self, name: str) -> Optional[str]:
        """Get a secret."""
        secret = self._secret_manager.get_secret(name)
        if secret:
            self._audit.record(
                AuditEventType.SECRET_ACCESSED,
                details={"secret_name": name},
            )
        return secret

    def check_path(self, path: str) -> Permission:
        """Check path permission."""
        return self._policy.check_path(path)

    def check_command(self, command: str) -> Permission:
        """Check command permission."""
        return self._policy.check_command(command)


def create_security_engine(
    policy: Optional[SecurityPolicy] = None,
) -> SecurityPolicyEngine:
    """Create a security policy engine with defaults."""
    return SecurityPolicyEngine(
        policy=policy or create_default_policy(),
    )