"""Provider resilience data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class FailureClass(Enum):
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    DNS_ERROR = "dns_error"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    SERVER_ERROR = "server_error"
    MALFORMED_RESPONSE = "malformed_response"
    STREAM_INTERRUPTED = "stream_interrupted"
    CONTEXT_OVERFLOW = "context_overflow"
    MODEL_UNAVAILABLE = "model_unavailable"
    SCHEMA_ERROR = "schema_error"
    TOOL_CALL_ERROR = "tool_call_error"
    UNKNOWN_PROVIDER_ERROR = "unknown_provider_error"


class RetryPolicy(Enum):
    SAFE_RETRY = "safe_retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    RETRY_AFTER = "retry_after"
    FALLBACK_ONLY = "fallback_only"
    DO_NOT_RETRY = "do_not_retry"


class StreamState(Enum):
    IDLE = "idle"
    ACTIVE = "active"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    ERROR = "error"


@dataclass
class ProviderResponse:
    content: str
    model: str
    provider: str
    finish_reason: Optional[str] = None
    tool_calls: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    request_id: Optional[str] = None
    valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "finish_reason": self.finish_reason,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "metadata": self.metadata,
            "request_id": self.request_id,
            "valid": self.valid,
        }


@dataclass
class ProviderError:
    provider: str
    model: str
    failure_class: FailureClass
    request_id: Optional[str] = None
    run_id: Optional[str] = None
    operation_id: Optional[str] = None
    retryable: bool = True
    fallback_eligible: bool = True
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "failure_class": self.failure_class.value,
            "request_id": self.request_id,
            "run_id": self.run_id,
            "operation_id": self.operation_id,
            "retryable": self.retryable,
            "fallback_eligible": self.fallback_eligible,
            "message": self.message,
        }


@dataclass
class TimeoutConfig:
    connect_timeout: float = 10.0
    request_timeout: float = 120.0
    stream_timeout: float = 300.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connect_timeout": self.connect_timeout,
            "request_timeout": self.request_timeout,
            "stream_timeout": self.stream_timeout,
        }


@dataclass
class HealthRecord:
    provider: str
    model: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 1.0
    failure_rate: float = 0.0
    avg_latency_ms: float = 0.0
    last_failure: Optional[str] = None
    circuit_state: CircuitState = CircuitState.CLOSED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "last_failure": self.last_failure,
            "circuit_state": self.circuit_state.value,
        }


@dataclass
class ProviderHealth:
    provider: str
    model: str
    success_rate: float = 1.0
    failure_rate: float = 0.0
    circuit_state: CircuitState = CircuitState.CLOSED
    total_requests: int = 0
    failed_requests: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "circuit_state": self.circuit_state.value,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
        }


@dataclass
class QuarantineRecord:
    provider: str
    model: str
    failure_count: int = 0
    quarantined_at: Optional[float] = None
    reason: str = ""
    manually_overridden: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "failure_count": self.failure_count,
            "quarantined_at": self.quarantined_at,
            "reason": self.reason,
            "manually_overridden": self.manually_overridden,
        }


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    jitter: bool = True


@dataclass
class CircuitConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_requests: int = 1


def classify_exception(exc: Exception) -> FailureClass:
    """Classify an exception into a FailureClass."""
    msg = str(exc).lower()

    if "timed out" in msg or "timeout" in msg:
        return FailureClass.TIMEOUT
    if "connection" in msg or "connect" in msg:
        return FailureClass.CONNECTION_ERROR
    if "dns" in msg:
        return FailureClass.DNS_ERROR
    if "rate limit" in msg:
        return FailureClass.RATE_LIMIT
    if "authentication" in msg or "auth" in msg:
        return FailureClass.AUTHENTICATION
    if "authorization" in msg:
        return FailureClass.AUTHORIZATION
    if "500" in msg or "server error" in msg:
        return FailureClass.SERVER_ERROR
    if "context" in msg and ("too long" in msg or "overflow" in msg):
        return FailureClass.CONTEXT_OVERFLOW
    if "malformed" in msg:
        return FailureClass.MALFORMED_RESPONSE
    if "stream" in msg:
        return FailureClass.STREAM_INTERRUPTED
    if "model" in msg and "unavailable" in msg:
        return FailureClass.MODEL_UNAVAILABLE

    return FailureClass.UNKNOWN_PROVIDER_ERROR


def is_retryable(failure_class: FailureClass) -> bool:
    """Determine if a failure class is retryable."""
    retryable_classes = {
        FailureClass.TIMEOUT,
        FailureClass.CONNECTION_ERROR,
        FailureClass.DNS_ERROR,
        FailureClass.RATE_LIMIT,
        FailureClass.SERVER_ERROR,
        FailureClass.STREAM_INTERRUPTED,
        FailureClass.MODEL_UNAVAILABLE,
    }
    return failure_class in retryable_classes


def get_retry_policy(failure_class: FailureClass) -> RetryPolicy:
    """Get the retry policy for a failure class."""
    policy_map = {
        FailureClass.TIMEOUT: RetryPolicy.RETRY_WITH_BACKOFF,
        FailureClass.CONNECTION_ERROR: RetryPolicy.RETRY_WITH_BACKOFF,
        FailureClass.DNS_ERROR: RetryPolicy.RETRY_WITH_BACKOFF,
        FailureClass.RATE_LIMIT: RetryPolicy.RETRY_AFTER,
        FailureClass.AUTHENTICATION: RetryPolicy.DO_NOT_RETRY,
        FailureClass.AUTHORIZATION: RetryPolicy.DO_NOT_RETRY,
        FailureClass.SERVER_ERROR: RetryPolicy.SAFE_RETRY,
        FailureClass.MALFORMED_RESPONSE: RetryPolicy.FALLBACK_ONLY,
        FailureClass.STREAM_INTERRUPTED: RetryPolicy.RETRY_WITH_BACKOFF,
        FailureClass.CONTEXT_OVERFLOW: RetryPolicy.FALLBACK_ONLY,
        FailureClass.MODEL_UNAVAILABLE: RetryPolicy.FALLBACK_ONLY,
        FailureClass.SCHEMA_ERROR: RetryPolicy.DO_NOT_RETRY,
        FailureClass.TOOL_CALL_ERROR: RetryPolicy.DO_NOT_RETRY,
        FailureClass.UNKNOWN_PROVIDER_ERROR: RetryPolicy.RETRY_WITH_BACKOFF,
    }
    return policy_map.get(failure_class, RetryPolicy.RETRY_WITH_BACKOFF)
