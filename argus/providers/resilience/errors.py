"""Provider resilience errors."""


class ProviderError(Exception):
    """Base provider error."""
    pass


class AuthenticationError(ProviderError):
    """Authentication failure."""
    pass


class RateLimitError(ProviderError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: float = 0.0):
        super().__init__(message)
        self.retry_after = retry_after


class TimeoutError(ProviderError):
    """Request timeout."""
    pass


class ServerError(ProviderError):
    """Server-side error."""
    pass


class NetworkError(ProviderError):
    """Network connectivity error."""
    pass


class EmptyResponseError(ProviderError):
    """Empty response received."""
    pass


class MalformedResponseError(ProviderError):
    """Malformed response received."""
    pass


class SecurityViolationError(ProviderError):
    """Security violation detected."""
    pass


class CircuitOpenError(ProviderError):
    """Circuit breaker is open."""
    pass


class QuarantinedError(ProviderError):
    """Provider is quarantined."""
    pass


class BudgetExceededError(ProviderError):
    """Rate budget exceeded."""
    pass


class AllProvidersExhaustedError(ProviderError):
    """All fallback providers exhausted."""
    pass
