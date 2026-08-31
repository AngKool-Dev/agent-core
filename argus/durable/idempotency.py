"""ARGUS Durable Execution Idempotency Classifier.

Classifies operations by their idempotency properties.
"""

from typing import Dict

from argus.durable.models import (
    IdempotencyClass,
    OperationType,
    RetryPolicy,
)


class IdempotencyClassifier:
    """Classifies operations by their idempotency.

    Categories:
    - IDEMPOTENT: Safe to retry (e.g., read operations)
    - CONDITIONALLY_IDEMPOTENT: Safe to retry with conditions (e.g., write exact content)
    - NON_IDEMPOTENT: Not safe to retry (e.g., send message, financial transaction)
    - UNKNOWN: Cannot determine - treat as non-idempotent
    """

    def __init__(self):
        self._operation_classifications: Dict[OperationType, IdempotencyClass] = {
            OperationType.FILESYSTEM_READ: IdempotencyClass.IDEMPOTENT,
            OperationType.FILESYSTEM_WRITE: IdempotencyClass.CONDITIONALLY_IDEMPOTENT,
            OperationType.FILESYSTEM_DELETE: IdempotencyClass.CONDITIONALLY_IDEMPOTENT,
            OperationType.SHELL_EXECUTE: IdempotencyClass.NON_IDEMPOTENT,
            OperationType.GIT_OPERATION: IdempotencyClass.CONDITIONALLY_IDEMPOTENT,
            OperationType.MCP_TOOL: IdempotencyClass.UNKNOWN,
            OperationType.MODEL_CALL: IdempotencyClass.IDEMPOTENT,
            OperationType.VERIFICATION: IdempotencyClass.IDEMPOTENT,
            OperationType.RECOVERY: IdempotencyClass.CONDITIONALLY_IDEMPOTENT,
            OperationType.REVIEW: IdempotencyClass.IDEMPOTENT,
            OperationType.CAPABILITY: IdempotencyClass.UNKNOWN,
            OperationType.STATE_COMMIT: IdempotencyClass.CONDITIONALLY_IDEMPOTENT,
            OperationType.CHECKPOINT: IdempotencyClass.IDEMPOTENT,
        }

    def classify(self, operation_type: OperationType) -> IdempotencyClass:
        """Classify an operation type by idempotency."""
        return self._operation_classifications.get(
            operation_type, IdempotencyClass.UNKNOWN
        )

    def set_classification(
        self,
        operation_type: OperationType,
        classification: IdempotencyClass,
    ):
        """Set the classification for an operation type."""
        self._operation_classifications[operation_type] = classification

    def is_idempotent(self, operation_type: OperationType) -> bool:
        """Check if an operation type is idempotent."""
        return self.classify(operation_type) == IdempotencyClass.IDEMPOTENT

    def is_conditionally_idempotent(self, operation_type: OperationType) -> bool:
        """Check if an operation type is conditionally idempotent."""
        return self.classify(operation_type) == IdempotencyClass.CONDITIONALLY_IDEMPOTENT

    def is_non_idempotent(self, operation_type: OperationType) -> bool:
        """Check if an operation type is non-idempotent."""
        return self.classify(operation_type) == IdempotencyClass.NON_IDEMPOTENT

    def is_unknown(self, operation_type: OperationType) -> bool:
        """Check if an operation type has unknown idempotency."""
        return self.classify(operation_type) == IdempotencyClass.UNKNOWN

    def determine_retry_policy(
        self,
        operation_type: OperationType,
        reconciliation_decision: str = None,
    ) -> RetryPolicy:
        """Determine the retry policy for an operation type."""
        classification = self.classify(operation_type)

        if classification == IdempotencyClass.IDEMPOTENT:
            return RetryPolicy.SAFE_RETRY

        if classification == IdempotencyClass.CONDITIONALLY_IDEMPOTENT:
            if reconciliation_decision == "retry":
                return RetryPolicy.RECONCILIATION_REQUIRED
            return RetryPolicy.RECONCILIATION_REQUIRED

        if classification == IdempotencyClass.NON_IDEMPOTENT:
            return RetryPolicy.UNSAFE_RETRY

        # Unknown - require user decision
        return RetryPolicy.USER_DECISION

    def get_all_classifications(self) -> Dict[str, str]:
        """Get all operation type classifications."""
        return {
            op_type.value: classification.value
            for op_type, classification in self._operation_classifications.items()
        }
