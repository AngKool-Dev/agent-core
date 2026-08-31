"""Response validation for provider resilience."""

import json
from typing import Any, Dict, List, Optional, Set

from argus.providers.resilience.errors import EmptyResponseError, MalformedResponseError


class ResponseValidator:
    """Validates provider responses."""

    def __init__(
        self,
        required_fields: Optional[List[str]] = None,
        allow_empty_content: bool = False,
        max_content_length: Optional[int] = None,
        valid_finish_reasons: Optional[Set[str]] = None,
    ):
        self._required_fields = required_fields or ["content", "model"]
        self._allow_empty_content = allow_empty_content
        self._max_content_length = max_content_length
        self._valid_finish_reasons = valid_finish_reasons or {"stop", "length", "tool_calls"}

    def validate_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        errors = []

        # Check required fields
        for field in self._required_fields:
            if field not in response:
                errors.append(f"Missing required field: {field}")

        # Check content
        content = response.get("content", "")
        if not self._allow_empty_content and not content and not response.get("tool_calls"):
            errors.append("Empty content not allowed")

        # Check content length
        if self._max_content_length and len(str(content)) > self._max_content_length:
            errors.append(f"Content exceeds max length of {self._max_content_length}")

        # Check finish reason
        finish_reason = response.get("finish_reason")
        if finish_reason and finish_reason not in self._valid_finish_reasons:
            errors.append(f"Invalid finish reason: {finish_reason}")

        # Check tool calls
        tool_calls = response.get("tool_calls", [])
        for tc in tool_calls:
            if "name" not in tc:
                errors.append("Tool call missing 'name' field")

        # Check usage tokens
        usage = response.get("usage", {})
        for token_field in ["prompt_tokens", "completion_tokens", "total_tokens"]:
            if token_field in usage and usage[token_field] < 0:
                errors.append(f"Negative {token_field}")

        return {
            "valid": len(errors) == 0,
            "validation_errors": errors,
        }

    def is_valid(self, response: Dict[str, Any]) -> bool:
        return self.validate_response(response)["valid"]

    def validate_raw_response(self, raw: str) -> Dict[str, Any]:
        if not raw or not raw.strip():
            raise EmptyResponseError("Empty response received")

        try:
            response = json.loads(raw)
        except json.JSONDecodeError as e:
            raise MalformedResponseError(f"Invalid JSON: {e}")

        return self.validate_response(response)
