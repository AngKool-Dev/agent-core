"""Reach capability adapter - integrates reach subsystem with capability system."""

from typing import Any, Dict, List, Optional

from argus.capabilities import (
    Capability,
    CapabilityMetadata,
    CapabilitySchema,
    CapabilityType,
)
from argus.capabilities.reach import ReachSubsystem, ReachResult


class ReachCapability(Capability):
    """Capability wrapper for reach subsystem operations."""

    def __init__(
        self,
        metadata: CapabilityMetadata,
        reach: ReachSubsystem,
        capability_name: str,
    ):
        super().__init__(metadata)
        self._reach = reach
        self._capability_name = capability_name

    def check_availability(self) -> bool:
        return self.metadata.availability

    def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "message": "Reach subsystem available"}

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            result = self._reach.execute(self._capability_name, **input_data)
            duration = time.time() - start
            return {
                "success": result.success,
                "output": result.to_dict(),
                "error": result.error,
                "execution_time": duration,
                "backend": f"reach.{self._capability_name}",
                "fallback_used": False,
            }
        except Exception as e:
            duration = time.time() - start
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "execution_time": duration,
                "backend": f"reach.{self._capability_name}",
                "fallback_used": False,
            }


def register_reach_capabilities(
    capability_registry: Any,
    github_token: str = "",
) -> None:
    """Register all reach capabilities into the capability registry."""
    reach = ReachSubsystem(github_token=github_token)

    reach_capabilities = [
        # Web capabilities
        ("web.read", "Read Web Page", "Read and extract content from a web page URL"),
        ("web.search", "Web Search", "Search the web using DuckDuckGo"),
        # GitHub capabilities
        ("github.search_repos", "Search GitHub Repos", "Search GitHub repositories"),
        ("github.search_issues", "Search GitHub Issues", "Search GitHub issues"),
        ("github.get_repo", "Get Repository", "Get GitHub repository information"),
        ("github.get_readme", "Get README", "Get repository README"),
        ("github.list_issues", "List Issues", "List repository issues"),
        ("github.get_issue", "Get Issue", "Get a specific GitHub issue"),
        ("github.create_issue", "Create Issue", "Create a GitHub issue"),
        # YouTube capabilities
        ("youtube.get_info", "Get Video Info", "Get YouTube video information"),
        ("youtube.search", "Search YouTube", "Search YouTube videos"),
        ("youtube.transcript", "Get Transcript", "Get YouTube video transcript"),
        # Reddit capabilities
        ("reddit.search", "Search Reddit", "Search Reddit posts"),
        ("reddit.get_subreddit", "Get Subreddit", "Get subreddit posts"),
        ("reddit.get_post", "Get Post", "Get a specific Reddit post"),
        ("reddit.get_user", "Get User", "Get Reddit user information"),
    ]

    for cap_id, name, description in reach_capabilities:
        schema = CapabilitySchema(
            name=name,
            description=description,
            parameters={"type": "object"},
            required_parameters=[],
        )

        metadata = CapabilityMetadata(
            id=cap_id,
            name=name,
            description=description,
            type=CapabilityType.REACH,
            schema=schema,
        )

        cap = ReachCapability(metadata, reach, cap_id)
        capability_registry.register(cap)


def get_reach_subsystem(github_token: str = "") -> ReachSubsystem:
    """Get or create the reach subsystem."""
    return ReachSubsystem(github_token=github_token)