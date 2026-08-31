"""ARGUS UX Package - Product layer for human interaction."""

from argus.ux.models import (
    EventSeverity,
    ExecutionPlan,
    LifecyclePhase,
    PanelView,
    PlanStep,
    ProviderStatus,
    SecurityStatus,
    PerformanceStatus,
    RecoveryStatus,
    ReviewStatus,
    SessionInfo,
    StepStatus,
    UIEvent,
    UXConfiguration,
    VerificationStatus,
)
from argus.ux.state import UXState
from argus.ux.events import UXEventSubscriber
from argus.ux.formatting import UXFormatter
from argus.ux.themes import ThemeManager, UXTheme
from argus.ux.commands import CommandInfo, CommandPalette
from argus.ux.controller import UXController

__all__ = [
    # Models
    "EventSeverity",
    "ExecutionPlan",
    "LifecyclePhase",
    "PanelView",
    "PlanStep",
    "ProviderStatus",
    "SecurityStatus",
    "PerformanceStatus",
    "RecoveryStatus",
    "ReviewStatus",
    "SessionInfo",
    "StepStatus",
    "UIEvent",
    "UXConfiguration",
    "VerificationStatus",
    # State
    "UXState",
    # Events
    "UXEventSubscriber",
    # Formatting
    "UXFormatter",
    # Themes
    "ThemeManager",
    "UXTheme",
    # Commands
    "CommandInfo",
    "CommandPalette",
    # Controller
    "UXController",
]
