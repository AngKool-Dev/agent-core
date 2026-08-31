"""Response normalization for provider resilience."""

from typing import Any, Callable, Dict, Optional

from argus.providers.resilience.models import ProviderResponse


NormalizerFn = Callable[[Any, str, str, Optional[str]], ProviderResponse]


class ResponseNormalizer:
    """Normalizes provider responses to canonical format."""

    def __init__(self):
        self._custom_normalizers: Dict[str, NormalizerFn] = {}

    def normalize(
        self,
        response: Any,
        provider: str,
        model: str,
        request_id: Optional[str] = None,
    ) -> ProviderResponse:
        if isinstance(response, ProviderResponse):
            return response

        normalizer = self._custom_normalizers.get(provider)
        if normalizer:
            return normalizer(response, provider, model, request_id)

        if isinstance(response, dict):
            return ProviderResponse(
                content=response.get("content", ""),
                model=response.get("model", model),
                provider=response.get("provider", provider),
                finish_reason=response.get("finish_reason"),
                tool_calls=response.get("tool_calls", []),
                usage=response.get("usage", {}),
                metadata=response.get("metadata", {}),
                request_id=request_id,
            )

        return ProviderResponse(
            content=str(response),
            model=model,
            provider=provider,
            request_id=request_id,
        )

    def register_normalizer(self, provider: str, normalizer: NormalizerFn) -> None:
        self._custom_normalizers[provider] = normalizer
