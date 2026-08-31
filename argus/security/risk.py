"""Risk classification for ARGUS capabilities."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class RiskLevel(str, Enum):
    """Risk levels for capabilities."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def numeric(self) -> int:
        levels = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }
        return levels[self]

    def __ge__(self, other):
        if isinstance(other, RiskLevel):
            return self.numeric >= other.numeric
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, RiskLevel):
            return self.numeric > other.numeric
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, RiskLevel):
            return self.numeric <= other.numeric
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, RiskLevel):
            return self.numeric < other.numeric
        return NotImplemented


# Default risk levels for common capability types
DEFAULT_CAPABILITY_RISKS: Dict[str, RiskLevel] = {
    # Read operations - LOW
    "filesystem.read": RiskLevel.LOW,
    "filesystem.list_dir": RiskLevel.LOW,
    "git.status": RiskLevel.LOW,
    "git.diff": RiskLevel.LOW,
    "git.log": RiskLevel.LOW,
    "search.grep": RiskLevel.LOW,
    "search.glob": RiskLevel.LOW,
    "memory.search": RiskLevel.LOW,
    "web.read": RiskLevel.LOW,
    "web.search": RiskLevel.LOW,
    "github.get_repo": RiskLevel.LOW,
    "github.get_readme": RiskLevel.LOW,
    "github.search_repos": RiskLevel.LOW,
    "github.search_issues": RiskLevel.LOW,
    "github.list_issues": RiskLevel.LOW,
    "github.get_issue": RiskLevel.LOW,
    "youtube.get_info": RiskLevel.LOW,
    "youtube.search": RiskLevel.LOW,
    "reddit.search": RiskLevel.LOW,
    "reddit.get_subreddit": RiskLevel.LOW,
    "reddit.get_post": RiskLevel.LOW,
    "reddit.get_user": RiskLevel.LOW,

    # Write operations - MEDIUM
    "filesystem.write": RiskLevel.MEDIUM,
    "filesystem.edit": RiskLevel.MEDIUM,
    "git.add": RiskLevel.MEDIUM,
    "memory.store": RiskLevel.LOW,

    # Commit operations - MEDIUM/HIGH
    "git.commit": RiskLevel.MEDIUM,
    "git.workflow": RiskLevel.MEDIUM,
    "github.create_issue": RiskLevel.MEDIUM,

    # Browser - varies
    "browser.navigate": RiskLevel.MEDIUM,
    "browser.screenshot": RiskLevel.LOW,

    # Shell - HIGH
    "shell.execute": RiskLevel.HIGH,

    # Model - LOW
    "model.generate": RiskLevel.LOW,
}


# Risk levels for common command patterns
COMMAND_RISK_PATTERNS: List[tuple] = [
    # CRITICAL patterns
    (r"\brm\s+(-[rfRF]+\s+)+/", RiskLevel.CRITICAL, "destructive filesystem operation"),
    (r"\brm\s+(-[rfRF]+\s+)+\*", RiskLevel.CRITICAL, "destructive filesystem operation"),
    (r"\brm\s+(-[rfRF]+\s+)+\.", RiskLevel.CRITICAL, "destructive filesystem operation"),
    (r"\bdd\s+", RiskLevel.CRITICAL, "disk operation"),
    (r"\bmkfs\b", RiskLevel.CRITICAL, "filesystem creation"),
    (r"\bfdisk\b", RiskLevel.CRITICAL, "disk partitioning"),
    (r":\(\)\{\s*:\|:\s*&\s*\};", RiskLevel.CRITICAL, "fork bomb"),
    (r"\bchmod\s+777\b", RiskLevel.CRITICAL, "dangerous permissions"),
    (r"\bchmod\s+-R\s+777\b", RiskLevel.CRITICAL, "dangerous recursive permissions"),

    # HIGH patterns
    (r"\bsudo\b", RiskLevel.HIGH, "privilege escalation"),
    (r"\bcurl\b.*\|\s*(sh|bash|zsh)", RiskLevel.HIGH, "pipe to shell"),
    (r"\bwget\b.*\|\s*(sh|bash|zsh)", RiskLevel.HIGH, "pipe to shell"),
    (r"\bnc\b", RiskLevel.HIGH, "netcat"),
    (r"\bnmap\b", RiskLevel.HIGH, "network scanning"),
    (r"\bscp\b", RiskLevel.HIGH, "secure copy"),
    (r"\brsync\b.*--delete", RiskLevel.HIGH, "destructive sync"),
    (r"\bgit\s+push\s+--force\b", RiskLevel.HIGH, "force push"),
    (r"\bgit\s+push\s+-f\b", RiskLevel.HIGH, "force push"),
    (r"\bdocker\s+rm\b", RiskLevel.HIGH, "docker remove"),
    (r"\bdocker\s+rmi\b", RiskLevel.HIGH, "docker remove image"),
    (r"\bkubectl\s+delete\b", RiskLevel.HIGH, "kubernetes delete"),
    (r"\bterraform\s+destroy\b", RiskLevel.HIGH, "terraform destroy"),

    # MEDIUM patterns
    (r"\bnpm\s+install\b", RiskLevel.MEDIUM, "package installation"),
    (r"\bpip\s+install\b", RiskLevel.MEDIUM, "package installation"),
    (r"\bcargo\s+install\b", RiskLevel.MEDIUM, "package installation"),
    (r"\bapt\s+install\b", RiskLevel.MEDIUM, "package installation"),
    (r"\byum\s+install\b", RiskLevel.MEDIUM, "package installation"),
    (r"\bnpm\s+run\b", RiskLevel.MEDIUM, "npm script"),
    (r"\bpython\s+\w+\.py\b", RiskLevel.MEDIUM, "python script execution"),
    (r"\bnode\s+\w+\.js\b", RiskLevel.MEDIUM, "node script execution"),
    (r"\bwget\b", RiskLevel.MEDIUM, "download"),
    (r"\bcurl\b", RiskLevel.MEDIUM, "download"),
    (r"\bwscat\b", RiskLevel.MEDIUM, "websocket tool"),
]


@dataclass
class RiskAssessment:
    """Result of a risk assessment."""
    level: RiskLevel
    reasons: List[str] = field(default_factory=list)
    factors: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_safe(self) -> bool:
        return self.level <= RiskLevel.LOW

    @property
    def requires_approval(self) -> bool:
        return self.level >= RiskLevel.HIGH

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "reasons": self.reasons,
            "factors": self.factors,
        }


class RiskClassifier:
    """Classifies risk of capabilities and commands."""

    def __init__(self):
        self._capability_risks: Dict[str, RiskLevel] = dict(DEFAULT_CAPABILITY_RISKS)
        self._command_patterns = COMMAND_RISK_PATTERNS

    def register_capability_risk(self, capability_id: str, risk: RiskLevel) -> None:
        """Register a risk level for a capability."""
        self._capability_risks[capability_id] = risk

    def assess_capability(self, capability_id: str) -> RiskAssessment:
        """Assess risk of a capability."""
        level = self._capability_risks.get(capability_id, RiskLevel.MEDIUM)
        return RiskAssessment(
            level=level,
            reasons=[f"Capability {capability_id} has default risk level: {level.value}"],
            factors={"capability_id": capability_id},
        )

    def assess_command(self, command: str) -> RiskAssessment:
        """Assess risk of a shell command."""
        max_risk = RiskLevel.LOW
        reasons = []

        for pattern, risk, description in self._command_patterns:
            import re
            if re.search(pattern, command):
                if risk.numeric > max_risk.numeric:
                    max_risk = risk
                    reasons.append(f"{description}: matches pattern '{pattern}'")

        # Check for shell metacharacters that could indicate injection
        if self._has_shell_injection(command):
            if RiskLevel.HIGH.numeric > max_risk.numeric:
                max_risk = RiskLevel.HIGH
                reasons.append("Potential shell injection detected")

        if not reasons:
            reasons.append("No risky patterns detected")

        return RiskAssessment(
            level=max_risk,
            reasons=reasons,
            factors={"command": command[:200]},
        )

    def assess_invocation(
        self,
        capability_id: str,
        input_data: Dict[str, Any],
    ) -> RiskAssessment:
        """Assess risk of a specific capability invocation."""
        # Start with base capability risk
        base_assessment = self.assess_capability(capability_id)
        max_risk = base_assessment.level
        reasons = list(base_assessment.reasons)

        # For shell commands, assess the command itself
        if capability_id == "shell.execute":
            command = input_data.get("command", "")
            command_assessment = self.assess_command(command)
            if command_assessment.level.numeric > max_risk.numeric:
                max_risk = command_assessment.level
                reasons.extend(command_assessment.reasons)

        # For filesystem operations, check paths
        if capability_id.startswith("filesystem."):
            path = input_data.get("path", "")
            path_risk = self._assess_path_risk(path)
            if path_risk.level.numeric > max_risk.numeric:
                max_risk = path_risk.level
                reasons.extend(path_risk.reasons)

        return RiskAssessment(
            level=max_risk,
            reasons=reasons,
            factors={"capability_id": capability_id, "input": {k: str(v)[:100] for k, v in input_data.items()}},
        )

    def _assess_path_risk(self, path: str) -> RiskAssessment:
        """Assess risk of a filesystem path."""
        import re
        # Check for path traversal
        if ".." in path:
            return RiskAssessment(
                level=RiskLevel.HIGH,
                reasons=["Path traversal detected"],
            )

        # Check for system directories
        system_paths = [
            r"^/etc/",
            r"^/sys/",
            r"^/proc/",
            r"^/dev/",
            r"^/boot/",
            r"^/Windows/",
            r"^/Program Files/",
            r"^/Users/[^/]+/Documents",
        ]
        for pattern in system_paths:
            if re.search(pattern, path, re.IGNORECASE):
                return RiskAssessment(
                    level=RiskLevel.CRITICAL,
                    reasons=[f"System directory access: {path}"],
                )

        return RiskAssessment(level=RiskLevel.LOW, reasons=["Path appears safe"])

    def _has_shell_injection(self, command: str) -> bool:
        """Check for potential shell injection."""
        import re
        # Check for command chaining
        dangerous_patterns = [
            r"[;&|]\s*\w+",  # command chaining
            r"\$\(",  # command substitution
            r"`[^`]+`",  # backtick command substitution
            r"\$\{",  # variable expansion
            r">\s*>",  # append redirect
            r"<\s*\(",  # process substitution input
            r">\s*\(",  # process substitution output
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                return True
        return False