"""Provider resilience package for ARGUS."""

from .backoff import BackoffStrategy, FixedBackoff, LinearBackoff
from .budget import RateBudget
from .circuit import CircuitBreaker
from .errors import (
    AllProvidersExhaustedError,
    AuthenticationError,
    BudgetExceededError,
    CircuitOpenError,
    EmptyResponseError,
    MalformedResponseError,
    NetworkError,
    ProviderError as ProviderErrorExc,
    QuarantinedError,
    RateLimitError,
    SecurityViolationError,
    ServerError,
    TimeoutError as TimeoutErrorExc,
)
from .fallback import FallbackManager
from .health import HealthTracker
from .models import (
    CircuitConfig,
    CircuitState,
    FailureClass,
    HealthRecord,
    ProviderError,
    ProviderHealth,
    ProviderResponse,
    QuarantineRecord,
    RetryConfig,
    RetryPolicy,
    StreamState,
    TimeoutConfig,
    classify_exception,
    get_retry_policy,
    is_retryable,
)
from .normalizer import ResponseNormalizer
from .quarantine import QuarantineManager
from .reporting import ResilienceReporter
from .retry import RetryHandler
from .security import (
    PoisoningDetector,
    PromptInjectionGuard,
    ResponseSanitizer,
)
from .stream import StreamHandler
from .validator import ResponseValidator

__all__ = [
    "BackoffStrategy",
    "FixedBackoff",
    "LinearBackoff",
    "RateBudget",
    "CircuitBreaker",
    "AllProvidersExhaustedError",
    "AuthenticationError",
    "BudgetExceededError",
    "CircuitOpenError",
    "EmptyResponseError",
    "MalformedResponseError",
    "NetworkError",
    "ProviderError",
    "ProviderErrorExc",
    "QuarantinedError",
    "RateLimitError",
    "SecurityViolationError",
    "ServerError",
    "TimeoutErrorExc",
    "FallbackManager",
    "HealthTracker",
    "CircuitConfig",
    "CircuitState",
    "FailureClass",
    "HealthRecord",
    "ProviderResponse",
    "ProviderHealth",
    "QuarantineRecord",
    "RetryConfig",
    "RetryPolicy",
    "StreamState",
    "TimeoutConfig",
    "classify_exception",
    "get_retry_policy",
    "is_retryable",
    "ResponseNormalizer",
    "QuarantineManager",
    "ResilienceReporter",
    "RetryHandler",
    "PoisoningDetector",
    "PromptInjectionGuard",
    "ResponseSanitizer",
    "StreamHandler",
    "ResponseValidator",
]
