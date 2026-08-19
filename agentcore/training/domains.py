"""
Deterministic domain classification for Phase 6A.

Maps instructions/responses to AgentCore architectural domains using
explicit keyword/concept mappings. No LLM involved.

Domains mirror the EraAI evaluation categories:

    architecture
    orchestration
    runtime
    runtime_adapter
    cancellation
    task_lifecycle
    failure_handling
    memory
    routing
    execution
    extensibility
    safety
    events
    persistence
    shutdown

Each domain has a keyword list. Classification is case-insensitive
substring matching.  An example can map to multiple domains.
"""

from __future__ import annotations

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "architecture": [
        "agentcore",
        "orchestration layer",
        "orchestrator",
        "orchestration",
        "architecture",
        "design perspective",
        "high-level",
        "structured",
        "ai agent",
        "decision-maker",
        "decision making",
        "control plane",
        "management layer",
        "framework",
        "universal",
    ],
    "orchestration": [
        "orchestration layer",
        "orchestrator",
        "orchestration",
        "scheduling",
        "scheduler",
        "task queue",
        "queue",
        "state management",
        "persistence",
        "store",
        "durable storage",
        "memory",
        "resource management",
        "resource limit",
        "cpu",
        "throttl",
        "quota",
    ],
    "runtime": [
        "runtime",
        "execution backend",
        "execution engine",
        "executor",
        "runtime adapter",
        "execution environment",
        "subprocess",
        "process",
        "hermes",
        "kilo",
        "opencode",
        "capabilities",
        "capability",
    ],
    "runtime_adapter": [
        "adapter interface",
        "adapter",
        "interface contract",
        "contract",
        "runtime adapter",
        "adapter pattern",
        "lifecycle methods",
        "isolation",
        "process boundary",
        "separate process",
        "separate container",
    ],
    "cancellation": [
        "cancellation",
        "cancel",
        "propagat",
        "terminate",
        "interrupt",
        "abort",
        "stop",
        "signal",
        "cancelled state",
        "cannot go back",
        "terminal state",
        "graceful shutdown",
        "draining",
    ],
    "task_lifecycle": [
        "lifecycle",
        "life cycle",
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
        "state transition",
        "terminal",
        "task states",
        "task state",
        "state machine",
        "transition",
    ],
    "failure_handling": [
        "error",
        "exception",
        "failure",
        "failed",
        "swallow",
        "not swallow",
        "retry",
        "backoff",
        "attempts",
        "exponential",
        "crash",
        "runtime failure",
        "recovery",
        "durable storage",
    ],
    "memory": [
        "memory",
        "shared memory",
        "memory context",
        "state store",
        "memory backend",
        "memory abstraction",
        "memory persistence",
        "memory retrieval",
        "memory updates",
        "confidence",
        "memory provenance",
        "memory lifecycle",
        "memory harvesting",
        "memory manager",
        "memory bank",
        "durable memory",
        "memory safety",
        "memory observability",
    ],
    "routing": [
        "routing",
        "route",
        "dispatcher",
        "dispatch",
        "match",
        "capability",
        "requirements",
        "skill",
        "skill router",
        "routing strategy",
        "custom routing",
    ],
    "execution": [
        "execution delegation",
        "delegate",
        "delegation",
        "perform work",
        "actual work",
        "execution",
        "runtime",
        "adapter interface",
        "tool manager",
        "tool execution",
        "tool call",
        "finish reason",
    ],
    "extensibility": [
        "extensible",
        "extension",
        "plugin",
        "pluggable",
        "modify core",
        "core component",
        "separation",
        "adapter interface",
        "runtime adapter",
        "third-party",
        "custom runtime",
    ],
    "safety": [
        "safety",
        "isolation",
        "process isolation",
        "process",
        "container",
        "crash",
        "resource limit",
        "resource limits",
        "exhaustion",
        "prevent",
        "security boundary",
        "resource guard",
        "limit",
        "throttl",
    ],
    "events": [
        "event",
        "event-driven",
        "push",
        "not poll",
        "not polling",
        "reactive",
        "subscribe",
        "notification",
        "event bus",
        "eventbus",
        "lifecycle event",
        "observation",
    ],
    "persistence": [
        "persist",
        "persistent",
        "durable",
        "storage",
        "flushed",
        "saved",
        "filesystem",
        "atomic write",
        "checkpoint",
        "recovery",
        "recover",
        "durability",
    ],
    "shutdown": [
        "graceful",
        "shutdown",
        "draining",
        "no new tasks",
        "flush",
        "exit",
        "interrupt",
        "terminate",
        "cancelled",
        "stop",
        "signal",
    ],
}


def classify_domains(text: str) -> list[str]:
    """Classify text into one or more domains.

    Deterministic, keyword-based. Returns a sorted list of domain names.
    """
    text_lower = text.lower()
    domains: list[str] = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            domains.append(domain)
    return domains


def classify_domains_set(text: str) -> set[str]:
    """Like classify_domains, but returns a set."""
    return set(classify_domains(text))
