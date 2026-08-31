"""Approval system for ARGUS security."""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"


class ApprovalScope(str, Enum):
    ONCE = "once"           # Single use
    RUN = "run"             # For the duration of the run
    SESSION = "session"     # For the session
    FOREVER = "forever"     # Until revoked


@dataclass
class ApprovalRequest:
    """A request for approval."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    capability_id: str = ""
    command: str = ""
    risk_level: str = ""
    reason: str = ""
    effects: List[str] = field(default_factory=list)
    working_directory: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    scope: ApprovalScope = ApprovalScope.ONCE
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "capability_id": self.capability_id,
            "command": self.command,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "effects": self.effects,
            "working_directory": self.working_directory,
            "status": self.status.value,
            "scope": self.scope.value,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "response": self.response,
        }

    def format_prompt(self) -> str:
        """Format as a user prompt."""
        lines = [
            "ARGUS PERMISSION REQUEST",
            "-" * 40,
            f"Capability: {self.capability_id}",
        ]
        if self.command:
            f"Command: {self.command}"
            lines.append(f"Command: {self.command}")
        if self.risk_level:
            lines.append(f"Risk: {self.risk_level}")
        if self.reason:
            lines.append(f"Reason: {self.reason}")
        if self.effects:
            lines.append("Effects:")
            for effect in self.effects:
                lines.append(f"  - {effect}")
        if self.working_directory:
            lines.append(f"Working directory: {self.working_directory}")
        lines.append("")
        lines.append("[Allow once] [Allow for run] [Deny]")
        return "\n".join(lines)


@dataclass
class Approval:
    """An approval granted."""
    request_id: str
    capability_id: str
    scope: ApprovalScope
    granted_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    command_pattern: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_expired


class ApprovalManager:
    """Manages approval requests and grants."""

    def __init__(self):
        self._pending: Dict[str, ApprovalRequest] = {}
        self._approvals: Dict[str, Approval] = {}
        self._denied: Dict[str, ApprovalRequest] = {}
        self._approval_fn: Optional[Callable[[ApprovalRequest], tuple]] = None

    def set_approval_function(self, fn: Callable[[ApprovalRequest], tuple]) -> None:
        """Set the function to call for approval.
        
        The function should return (approved: bool, scope: ApprovalScope).
        """
        self._approval_fn = fn

    def request_approval(
        self,
        capability_id: str,
        command: str = "",
        risk_level: str = "",
        reason: str = "",
        effects: List[str] = None,
        working_directory: str = "",
    ) -> ApprovalRequest:
        """Create an approval request."""
        request = ApprovalRequest(
            capability_id=capability_id,
            command=command,
            risk_level=risk_level,
            reason=reason,
            effects=effects or [],
            working_directory=working_directory,
        )
        self._pending[request.request_id] = request
        return request

    def resolve_approval(
        self,
        request_id: str,
        approved: bool,
        scope: ApprovalScope = ApprovalScope.ONCE,
    ) -> Optional[Approval]:
        """Resolve an approval request."""
        request = self._pending.pop(request_id, None)
        if not request:
            return None

        request.resolved_at = time.time()

        if approved:
            request.status = ApprovalStatus.GRANTED
            approval = Approval(
                request_id=request_id,
                capability_id=request.capability_id,
                scope=scope,
                command_pattern=request.command if request.command else None,
            )
            self._approvals[request_id] = approval
            return approval
        else:
            request.status = ApprovalStatus.DENIED
            self._denied[request_id] = request
            return None

    def check_approval(self, capability_id: str, command: str = "") -> Optional[Approval]:
        """Check if there's a valid approval for a capability."""
        for approval in self._approvals.values():
            if approval.capability_id == capability_id and approval.is_valid:
                # Check command pattern if present
                if approval.command_pattern and command:
                    import re
                    if not re.search(approval.command_pattern, command):
                        continue
                return approval
        return None

    def revoke_approval(self, request_id: str) -> bool:
        """Revoke an approval."""
        if request_id in self._approvals:
            del self._approvals[request_id]
            return True
        return False

    def clear_all(self) -> None:
        """Clear all approvals."""
        self._approvals.clear()
        self._pending.clear()
        self._denied.clear()

    def get_pending(self) -> List[ApprovalRequest]:
        """Get pending requests."""
        return list(self._pending.values())

    def get_approvals(self) -> List[Approval]:
        """Get all approvals."""
        return list(self._approvals.values())

    def prompt_and_resolve(self, request: ApprovalRequest) -> Optional[Approval]:
        """Prompt for approval and resolve."""
        if self._approval_fn:
            approved, scope = self._approval_fn(request)
            return self.resolve_approval(request.request_id, approved, scope)
        return None