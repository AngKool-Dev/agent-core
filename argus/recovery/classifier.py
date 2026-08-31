"""Failure classifier - classifies failures into categories."""

import re
from typing import Any, Dict, List, Optional

from argus.recovery.result import FailureClass, FailureEvidence


# Patterns for classifying failures
TRANSIENT_PATTERNS = [
    r"timeout",
    r"timed?\s*out",
    r"rate\s*limit",
    r"429",
    r"503",
    r"502",
    r"504",
    r"temporary\s*(?:unavailable|failure)",
    r"connection\s*(?:reset|refused|closed)",
    r"network\s*(?:error|unreachable|down)",
    r"dns\s*(?:error|failure|not\s*found)",
    r"ssl\s*(?:error|handshake)",
    r"temporarily\s*unavailable",
    r"retry",
    r"throttl",
]

BACKEND_PATTERNS = [
    r"provider\s*(?:unavailable|down|error)",
    r"api\s*(?:unavailable|down|error)",
    r"service\s*(?:unavailable|down|error)",
    r"authentication\s*(?:failed|error|required)",
    r"unauthorized",
    r"401",
    r"403",
    r"forbidden",
    r"invalid\s*(?:api\s*)?key",
    r"credential",
    r"token\s*(?:expired|invalid|revoked)",
    r"oauth",
    r"permission\s*denied",
    r"access\s*denied",
]

EXECUTION_PATTERNS = [
    r"command\s*(?:not\s*found|failed)",
    r"process\s*(?:crashed|exited|killed)",
    r"segmentation\s*fault",
    r"segfault",
    r"core\s*dumped",
    r"signal",
    r"abort",
    r"assertion\s*failed",
    r"dependency\s*(?:missing|not\s*found)",
    r"module\s*not\s*found",
    r"import\s*error",
    r"package\s*not\s*found",
    r"library\s*not\s*found",
    r"shared\s*object",
]

CODE_PATTERNS = [
    r"compilation\s*(?:error|failed)",
    r"compile\s*error",
    r"syntax\s*error",
    r"parse\s*error",
    r"type\s*error",
    r"type\s*check",
    r"lint\s*error",
    r"test\s*(?:failed|failure)",
    r"assertion\s*(?:error|failed)",
    r"pytest.*failed",
    r"failures?=\s*\d+",
    r"error[s]?\s*=\s*\d+",
    r"expected.*but\s*got",
    r"mismatch",
]

LOGICAL_PATTERNS = [
    r"verification\s*(?:failed|error)",
    r"criterion\s*failed",
    r"does\s*not\s*satisfy",
    r"requirement\s*not\s*met",
    r"incorrect\s*result",
    r"wrong\s*(?:output|result|answer)",
    r"not\s*as\s*expected",
    r"doesn'?t\s*match",
    r"implementation\s*(?:incorrect|wrong|invalid)",
]

ENVIRONMENT_PATTERNS = [
    r"no\s*such\s*file\s*or\s*directory",
    r"file\s*not\s*found",
    r"directory\s*not\s*found",
    r"wrong\s*(?:working\s*directory|path)",
    r"missing\s*(?:runtime|interpreter|executable)",
    r"python\s*not\s*found",
    r"node\s*not\s*found",
    r"java\s*not\s*found",
    r"incompatible\s*(?:platform|version|architecture)",
    r"unsupported\s*(?:platform|os)",
    r"wrong\s*architecture",
    r"cannot\s*execute\s*binary",
]

USER_REQUIRED_PATTERNS = [
    r"ambiguous",
    r"unclear",
    r"please\s*clarify",
    r"need\s*more\s*information",
    r"missing\s*(?:credential|password|token|key)",
    r"requires?\s*(?:approval|confirmation|permission)",
    r"destructive\s*operation",
    r"irreversible",
    r"cannot\s*proceed\s*without",
    r"user\s*(?:input|confirmation|approval)\s*required",
    r"ask\s*the\s*user",
    r"escalate",
]


class FailureClassifier:
    """Classifies failures into categories for recovery."""

    def __init__(self):
        self._patterns: Dict[FailureClass, List[re.Pattern]] = {
            FailureClass.TRANSIENT: [re.compile(p, re.IGNORECASE) for p in TRANSIENT_PATTERNS],
            FailureClass.BACKEND: [re.compile(p, re.IGNORECASE) for p in BACKEND_PATTERNS],
            FailureClass.EXECUTION: [re.compile(p, re.IGNORECASE) for p in EXECUTION_PATTERNS],
            FailureClass.CODE: [re.compile(p, re.IGNORECASE) for p in CODE_PATTERNS],
            FailureClass.LOGICAL: [re.compile(p, re.IGNORECASE) for p in LOGICAL_PATTERNS],
            FailureClass.ENVIRONMENT: [re.compile(p, re.IGNORECASE) for p in ENVIRONMENT_PATTERNS],
            FailureClass.USER_REQUIRED: [re.compile(p, re.IGNORECASE) for p in USER_REQUIRED_PATTERNS],
        }

    def classify(
        self,
        message: str,
        command: str = "",
        return_code: int = 0,
        context: Dict[str, Any] = None,
    ) -> FailureEvidence:
        """Classify a failure and return evidence."""
        # Combine message and stderr for classification
        full_text = message
        if context:
            stderr = context.get("stderr", "")
            stdout = context.get("stdout", "")
            full_text = f"{message} {stderr} {stdout}"

        # Score each failure class
        scores: Dict[FailureClass, float] = {}
        for failure_class, patterns in self._patterns.items():
            score = 0.0
            for pattern in patterns:
                if pattern.search(full_text):
                    score += 1.0
            if score > 0:
                scores[failure_class] = score

        # Select the class with highest score
        if scores:
            best_class = max(scores, key=scores.get)
        else:
            best_class = FailureClass.UNKNOWN

        # Extract relevant context
        extracted_context = self._extract_context(message, command, return_code, context)

        return FailureEvidence(
            failure_class=best_class,
            message=message,
            command=command,
            return_code=return_code,
            context=extracted_context,
        )

    def _extract_context(
        self,
        message: str,
        command: str,
        return_code: int,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Extract relevant context from the failure."""
        extracted: Dict[str, Any] = {}

        if context:
            # Include relevant fields
            for key in ["stdout", "stderr", "capability_id", "backend", "project_path"]:
                if key in context:
                    value = context[key]
                    if isinstance(value, str) and len(value) > 1000:
                        extracted[key] = value[:1000]
                    else:
                        extracted[key] = value

        extracted["return_code"] = return_code
        if command:
            extracted["command"] = command

        return extracted

    def classify_from_result(self, result: Dict[str, Any]) -> FailureEvidence:
        """Classify from a result dict (e.g., from capability execution)."""
        return self.classify(
            message=result.get("error", ""),
            command=result.get("command", ""),
            return_code=result.get("return_code", 0),
            context=result,
        )