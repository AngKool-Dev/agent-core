"""Argus model provider hub."""

import time
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .provider import Message, ModelProvider, ModelResponse, ToolCall
from .usage import UsageEntry


class Strategy(str, Enum):
    FREE_FIRST = "free_first"
    BALANCED = "balanced"
    QUALITY_FIRST = "quality_first"
    MANUAL = "manual"
    LOCAL_FIRST = "local_first"
    CAPABILITY_FIRST = "capability_first"


TASK_TAGS = {
    "general": ["what", "how", "why", "explain", "describe", "summarize", "list"],
    "coding": ["fix", "bug", "error", "compile", "refactor", "implement", "code", "function", "class", "debug"],
    "reasoning": ["analyze", "review", "design", "architecture", "complex", "plan", "strategy"],
    "tool_use": ["run", "execute", "test", "build", "deploy", "bash", "command"],
    "creative": ["write", "generate", "create", "draft", "compose"],
}


class TaskClassifier:
    @staticmethod
    def classify(request: str) -> List[str]:
        request_lower = request.lower()
        tags = []
        for tag, keywords in TASK_TAGS.items():
            if any(kw in request_lower for kw in keywords):
                tags.append(tag)
        if not tags:
            tags.append("general")
        return tags

    @staticmethod
    def requires_tool_calling(request: str) -> bool:
        request_lower = request.lower()
        tool_keywords = ["run", "execute", "test", "build", "bash", "command", "fix", "refactor", "deploy"]
        return any(kw in request_lower for kw in tool_keywords)

    @staticmethod
    def requires_large_context(request: str) -> bool:
        request_lower = request.lower()
        large_keywords = ["entire", "whole", "all files", "module", "refactor", "review", "migrate"]
        return any(kw in request_lower for kw in large_keywords)


@dataclass
class ProviderCapability:
    name: str
    models: List[str]
    free: bool
    tool_calling: bool = True
    streaming: bool = False
    context_window: int = 0
    capabilities: List[str] = field(default_factory=list)
    available: bool = True
    rate_limit: Optional[str] = None
    reset_info: Optional[str] = None
    task_tags: List[str] = field(default_factory=list)


@dataclass
class ProviderState:
    capability: ProviderCapability
    provider: Optional[ModelProvider] = None
    cooldown_until: float = 0
    consecutive_failures: int = 0
    last_error: Optional[str] = None


class Budget:
    def __init__(self, allow_paid: bool = True, daily_limit: float = 0.0, spent: float = 0.0):
        self.allow_paid = allow_paid
        self.daily_limit = daily_limit
        self._spent = spent

    @property
    def spent(self) -> float:
        return self._spent

    def record_spend(self, amount: float) -> None:
        self._spent += amount

    def can_spend(self, amount: float = 0.0) -> bool:
        if not self.allow_paid:
            return amount <= 0.0
        return self._spent + amount <= self.daily_limit

    def remaining(self) -> float:
        return max(0.0, self.daily_limit - self._spent)


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, ProviderState] = {}

    def register(self, state: ProviderState) -> None:
        self._providers[state.capability.name] = state

    def get(self, name: str) -> Optional[ProviderState]:
        return self._providers.get(name)

    def list_capabilities(self) -> List[ProviderCapability]:
        return [s.capability for s in self._providers.values()]

    def list_states(self) -> List[ProviderState]:
        return list(self._providers.values())

    def mark_failure(self, name: str, error: Optional[str] = None, cooldown_seconds: float = 60.0) -> None:
        state = self._providers.get(name)
        if not state:
            return
        state.consecutive_failures += 1
        state.last_error = error
        state.cooldown_until = time.time() + cooldown_seconds * min(state.consecutive_failures, 5)

    def mark_success(self, name: str) -> None:
        state = self._providers.get(name)
        if not state:
            return
        state.consecutive_failures = 0
        state.last_error = None
        state.cooldown_until = 0.0

    def available(self, name: str, allow_paid: bool = True) -> bool:
        state = self._providers.get(name)
        if not state:
            return False
        if not state.capability.available:
            return False
        if time.time() < state.cooldown_until:
            return False
        if not allow_paid and not state.capability.free:
            return False
        return True


class ModelRouter(ModelProvider):
    def __init__(
        self,
        registry: ProviderRegistry,
        strategy: Strategy = Strategy.FREE_FIRST,
        budget: Optional[Budget] = None,
        preferred_model: Optional[str] = None,
        usage_tracker: Optional[Any] = None,
    ) -> None:
        self._registry = registry
        self._strategy = strategy
        self._budget = budget or Budget()
        self._preferred_model = preferred_model
        self._last_used: Optional[str] = None
        self._usage_tracker = usage_tracker

    @property
    def strategy(self) -> Strategy:
        return self._strategy

    @strategy.setter
    def strategy(self, value: Strategy) -> None:
        self._strategy = value

    @property
    def budget(self) -> Budget:
        return self._budget

    def set_strategy(self, strategy: Strategy) -> None:
        self._strategy = strategy

    def set_preferred_model(self, model: Optional[str]) -> None:
        self._preferred_model = model

    def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        request: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        target_model = model or self._preferred_model
        state = self._select_provider(target_model, request=request)
        if not state or not state.provider:
            raise RuntimeError("No available model provider")

        provider_name = state.capability.name
        try:
            response = state.provider.complete(messages=messages, model=target_model or "", tools=tools, **kwargs)
            self._registry.mark_success(provider_name)
            self._last_used = provider_name
            self._record_usage(provider_name, target_model or "", response, True)
            return response
        except Exception as e:
            self._registry.mark_failure(provider_name, str(e))
            self._record_usage(provider_name, target_model or "", None, False, str(e))
            raise

    def stream(self, messages: List[Message], model: Optional[str] = None, request: Optional[str] = None, **kwargs):
        target_model = model or self._preferred_model
        state = self._select_provider(target_model, request=request)
        if not state or not state.provider:
            raise RuntimeError("No available model provider")
        provider_name = state.capability.name
        try:
            stream = state.provider.stream(messages=messages, model=target_model or "", **kwargs)
            self._registry.mark_success(provider_name)
            self._last_used = provider_name
            return stream
        except Exception as e:
            self._registry.mark_failure(provider_name, str(e))
            raise

    def _record_usage(self, provider: str, model: str, response: Optional[ModelResponse], success: bool, error: Optional[str] = None) -> None:
        if not self._usage_tracker:
            return
        tokens = 0
        if response and response.usage:
            tokens = response.usage.get("total_tokens", 0)
        entry = UsageEntry(
            provider=provider,
            model=model,
            timestamp=time.time(),
            tokens=tokens,
            success=success,
            error=error,
        )
        self._usage_tracker.record(entry)

    def _select_provider(self, target_model: Optional[str], request: Optional[str] = None) -> Optional[ProviderState]:
        allow_paid = self._budget.allow_paid
        states = self._registry.list_states()

        if self._strategy == Strategy.MANUAL:
            if self._last_used:
                last = self._registry.get(self._last_used)
                if last and self._registry.available(self._last_used, allow_paid):
                    return last
            for state in states:
                if self._registry.available(state.capability.name, allow_paid):
                    return state
            return None

        candidates = [s for s in states if self._registry.available(s.capability.name, allow_paid)]
        if not candidates:
            return None

        if self._strategy == Strategy.CAPABILITY_FIRST and request:
            task_tags = TaskClassifier.classify(request)
            scored = []
            for state in candidates:
                score = 0
                for tag in task_tags:
                    if tag in state.capability.task_tags:
                        score += 10
                if TaskClassifier.requires_tool_calling(request) and not state.capability.tool_calling:
                    score -= 20
                if TaskClassifier.requires_large_context(request) and state.capability.context_window < 32000:
                    score -= 10
                scored.append((score, state))
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1] if scored else None

        if self._strategy == Strategy.CAPABILITY_FIRST:
            return self._pick_best(candidates, target_model)

        if self._strategy == Strategy.LOCAL_FIRST:
            local = [s for s in candidates if s.capability.name == "ollama"]
            if local:
                return self._pick_best(local, target_model)
            return self._pick_best(candidates, target_model)

        if self._strategy == Strategy.FREE_FIRST:
            free = [s for s in candidates if s.capability.free]
            if free:
                return self._pick_best(free, target_model)
            paid = [s for s in candidates if not s.capability.free]
            if paid and self._budget.can_spend():
                return self._pick_best(paid, target_model)
            return None

        if self._strategy == Strategy.QUALITY_FIRST:
            by_context = sorted(candidates, key=lambda s: s.capability.context_window, reverse=True)
            return self._pick_best(by_context, target_model)

        return self._pick_best(candidates, target_model)

    def _pick_best(self, candidates: List[ProviderState], target_model: Optional[str]) -> Optional[ProviderState]:
        if target_model:
            for state in candidates:
                if target_model in state.capability.models:
                    return state
        return candidates[0] if candidates else None
