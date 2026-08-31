"""Context engine with relevance-based capability selection."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from argus.capabilities import (
    Capability,
    CapabilityRegistry,
    CapabilityRouter,
    CapabilityType,
)


# Keywords associated with each capability type
TYPE_KEYWORDS: Dict[CapabilityType, List[str]] = {
    CapabilityType.READ: [
        "read", "show", "view", "display", "cat", "get", "fetch", "open",
        "see", "look", "check", "find", "search", "list", "contents",
    ],
    CapabilityType.WRITE: [
        "write", "create", "make", "add", "edit", "modify", "change",
        "update", "save", "delete", "remove", "rename", "move", "copy",
    ],
    CapabilityType.EXECUTE: [
        "run", "execute", "command", "shell", "bash", "terminal", "cli",
        "build", "compile", "start", "stop", "restart", "install",
    ],
    CapabilityType.SEARCH: [
        "search", "find", "grep", "glob", "pattern", "locate", "discover",
        "lookup", "query",
    ],
    CapabilityType.BROWSER: [
        "browser", "web", "url", "website", "page", "click", "navigate",
        "screenshot", "scrape", "online",
    ],
    CapabilityType.GIT: [
        "git", "commit", "branch", "push", "pull", "merge", "status",
        "diff", "log", "checkout", "stage", "stash", "clone",
    ],
    CapabilityType.MODEL: [
        "ask", "question", "chat", "generate", "complete", "respond",
        "think", "reason", "analyze", "summarize", "explain",
    ],
    CapabilityType.MEMORY: [
        "remember", "memory", "recall", "note", "save", "store",
        "history", "previous", "before", "earlier",
    ],
    CapabilityType.REACH: [
        "web", "internet", "url", "github", "youtube", "reddit",
        "online", "remote", "api", "fetch", "download", "scrape",
    ],
    CapabilityType.COMMANDS: [
        "command", "help", "info", "status", "config", "setting",
    ],
}


# Specific capability patterns (regex-based matching)
CAPABILITY_PATTERNS: Dict[str, List[str]] = {
    "filesystem.read": [
        r"read\s+(?:file|the\s+file)",
        r"show\s+(?:file|contents|me)",
        r"cat\s+",
        r"view\s+(?:file|the)",
        r"open\s+(?:file|the)",
        r"display\s+(?:file|contents)",
    ],
    "filesystem.write": [
        r"write\s+(?:to\s+)?(?:file|the\s+file)",
        r"create\s+(?:file|a\s+file)",
        r"save\s+(?:to\s+)?(?:file|the\s+file)",
        r"new\s+file",
    ],
    "filesystem.edit": [
        r"edit\s+(?:file|the\s+file)",
        r"modify\s+(?:file|the\s+file)",
        r"change\s+(?:file|the\s+file)",
        r"update\s+(?:file|the\s+file)",
        r"replace\s+(?:in\s+)?(?:file|the\s+file)",
    ],
    "filesystem.list_dir": [
        r"list\s+(?:files?|directory|dir)",
        r"ls\s+",
        r"show\s+(?:files|directory|folders?)",
        r"what(?:'s|\s+is)\s+in\s+(?:the\s+)?(?:folder|dir|directory)",
        r"contents\s+of\s+(?:the\s+)?(?:folder|dir|directory)",
    ],
    "shell.execute": [
        r"run\s+(?:command|the\s+command)",
        r"execute\s+(?:command|the\s+command)",
        r"bash\s+",
        r"shell\s+",
        r"terminal\s+",
        r"command\s+line",
        r"^!\s*\w+",
    ],
    "search.grep": [
        r"grep\s+",
        r"search\s+(?:for\s+)?(?:in\s+)?(?:files?|the\s+files?)",
        r"find\s+(?:in\s+)?(?:files?|the\s+files?)",
        r"look\s+for\s+(?:in\s+)?(?:files?|the\s+files?)",
    ],
    "search.glob": [
        r"find\s+(?:files?|the\s+files?)",
        r"glob\s+",
        r"files?\s+(?:named?|called|with\s+name)",
        r"pattern\s+(?:files?|match)",
    ],
    "git.status": [
        r"git\s+status",
        r"status\s+of\s+(?:the\s+)?(?:repo|repository|project)",
        r"(?:repo|repository|git)\s+status",
        r"what(?:'s|\s+is)\s+(?:changed|modified|different)",
        r"working\s+tree\s+status",
    ],
    "git.diff": [
        r"git\s+diff",
        r"diff\s+(?:of|for)",
        r"(?:what|show)\s+(?:changed|diff|difference)",
        r"changes\s+(?:in|to|from)",
        r"compare\s+(?:with|to|against)",
    ],
    "git.log": [
        r"git\s+log",
        r"commit\s+history",
        r"(?:recent|latest|previous)\s+commits?",
        r"commit\s+log",
        r"what\s+(?:has|was)\s+(?:been\s+)?committed",
    ],
    "git.add": [
        r"git\s+add",
        r"stage\s+(?:files?|changes?)",
        r"add\s+(?:files?|changes?)\s+(?:to\s+)?(?:the\s+)?(?:staging|index)",
        r"prepare\s+(?:files?|changes?)\s+for\s+commit",
    ],
    "git.commit": [
        r"git\s+commit",
        r"commit\s+(?:changes?|the\s+changes?)",
        r"record\s+(?:changes?|the\s+changes?)",
        r"create\s+(?:a\s+)?commit",
    ],
    "memory.store": [
        r"remember\s+(?:that|this|to)",
        r"save\s+(?:this|that)?\s+to\s+memory",
        r"store\s+(?:this|that)?\s+(?:in\s+)?memory",
        r"note\s+(?:that|this|down)",
        r"keep\s+in\s+mind",
    ],
    "memory.search": [
        r"what\s+(?:did|have)\s+(?:we|I)\s+(?:do|say|discuss|talk\s+about)",
        r"recall\s+(?:the|last|previous)",
        r"search\s+(?:the\s+)?memory",
        r"find\s+(?:in\s+)?(?:the\s+)?memory",
        r"remember\s+(?:when|what|the)",
        r"previous(?:ly)?\s+(?:we|I|discussed|did|said)",
    ],
    "browser.navigate": [
        r"open\s+(?:the\s+)?(?:url|website|page|site)",
        r"visit\s+(?:the\s+)?(?:url|website|page|site)",
        r"go\s+to\s+(?:the\s+)?(?:url|website|page|site)",
        r"browse\s+(?:to\s+)?(?:the\s+)?(?:url|website|page|site)",
        r"navigate\s+(?:to\s+)?(?:the\s+)?(?:url|website|page|site)",
    ],
    "web.read": [
        r"read\s+(?:the\s+)?(?:web|page|url|website)",
        r"fetch\s+(?:the\s+)?(?:page|url|website|content)",
        r"get\s+(?:the\s+)?(?:content|page)\s+(?:from|of)",
        r"what(?:'s|\s+is)\s+(?:on|at)\s+(?:the\s+)?(?:url|page|site)",
    ],
    "web.search": [
        r"search\s+(?:the\s+)?web\s+for",
        r"look\s+(?:up|for)\s+(?:on\s+)?(?:the\s+)?web",
        r"find\s+(?:on\s+)?(?:the\s+)?web",
        r"google\s+",
        r"duckduckgo\s+",
    ],
    "github.search_repos": [
        r"search\s+(?:for\s+)?(?:github|repos?)",
        r"find\s+(?:github|repos?)",
        r"github\s+(?:repo|repository|repositories)\s+search",
        r"look\s+for\s+(?:github|repos?)",
    ],
    "github.get_repo": [
        r"(?:get|show|info\s+about)\s+(?:github|the\s+)?repo",
        r"github\s+(?:repo|repository)\s+(?:info|details)",
        r"details\s+(?:of|about)\s+(?:github|the\s+)?repo",
    ],
    "github.search_issues": [
        r"search\s+(?:for\s+)?(?:github|issues?)",
        r"find\s+(?:github|issues?)",
        r"github\s+issues?\s+search",
        r"list\s+(?:github|open)\s+issues?",
    ],
    "github.list_issues": [
        r"list\s+(?:the\s+)?(?:open\s+)?issues?",
        r"show\s+(?:the\s+)?(?:open\s+)?issues?",
        r"what\s+issues?\s+(?:are\s+)?open",
        r"open\s+issues?\s+(?:list|in)",
    ],
    "github.create_issue": [
        r"create\s+(?:a\s+)?(?:github\s+)?issue",
        r"(?:file|report)\s+(?:a\s+)?(?:bug|issue)",
        r"open\s+(?:a\s+)?(?:github\s+)?issue",
        r"new\s+(?:github\s+)?issue",
    ],
    "youtube.search": [
        r"search\s+(?:for\s+)?(?:youtube|videos?)",
        r"find\s+(?:youtube|videos?)",
        "look for .* video",
        r"youtube\s+(?:search|find|look\s+for)",
    ],
    "youtube.get_info": [
        r"(?:get|show|info\s+about)\s+(?:youtube|the\s+)?video",
        r"video\s+(?:info|details|about)",
        r"what(?:'s|\s+is)\s+(?:this|the)\s+video\s+about",
    ],
    "reddit.search": [
        r"search\s+(?:for\s+)?reddit",
        r"find\s+(?:on\s+)?reddit",
        r"reddit\s+(?:search|find|look\s+for)",
        r"look\s+(?:up|for)\s+(?:on\s+)?reddit",
    ],
    "reddit.get_subreddit": [
        r"(?:get|show|list)\s+(?:the\s+)?(?:subreddit|r/\w+)",
        r"what(?:'s|\s+is)\s+(?:on|in)\s+(?:the\s+)?(?:subreddit|r/\w+)",
        r"show\s+(?:me\s+)?(?:the\s+)?(?:subreddit|r/\w+)\s+posts",
    ],
}


@dataclass
class RelevanceScore:
    """Score indicating how relevant a capability is to a query."""
    capability_id: str
    score: float
    reasons: List[str] = field(default_factory=list)


@dataclass
class ContextAnalysis:
    """Analysis of a user query in context."""
    query: str
    suggested_capabilities: List[RelevanceScore]
    primary_type: Optional[CapabilityType] = None
    keywords: List[str] = field(default_factory=list)
    confidence: float = 0.0


class ContextEngine:
    """Engine for relevance-based capability selection."""

    def __init__(self, registry: CapabilityRegistry):
        self._registry = registry

    def analyze(self, query: str) -> ContextAnalysis:
        """Analyze a query and return relevance scores for capabilities."""
        query_lower = query.lower()
        words = set(re.findall(r"\b\w+\b", query_lower))

        # Determine primary capability type
        type_scores = self._score_types(words, query_lower)
        primary_type = max(type_scores, key=type_scores.get) if type_scores else None

        # Score each capability
        cap_scores: Dict[str, RelevanceScore] = {}

        for cap in self._registry.list():
            cap_id = cap.get_id()
            score = self._score_capability(cap, query_lower, words, type_scores)
            if score.score > 0:
                cap_scores[cap_id] = score

        # Sort by score descending
        sorted_scores = sorted(cap_scores.values(), key=lambda s: s.score, reverse=True)

        # Calculate overall confidence
        confidence = sorted_scores[0].score if sorted_scores else 0.0

        return ContextAnalysis(
            query=query,
            suggested_capabilities=sorted_scores[:10],
            primary_type=primary_type,
            keywords=list(words),
            confidence=min(confidence, 1.0),
        )

    def select_capability(
        self,
        query: str,
        capability_type: CapabilityType = None,
        min_score: float = 0.1,
    ) -> Optional[RelevanceScore]:
        """Select the best capability for a query."""
        analysis = self.analyze(query)

        candidates = analysis.suggested_capabilities
        if capability_type:
            candidates = [
                c for c in candidates
                if self._registry.get(c.capability_id)
                and self._registry.get(c.capability_id).get_type() == capability_type
            ]

        if not candidates or candidates[0].score < min_score:
            return None

        return candidates[0]

    def get_capability_recommendations(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get capability recommendations for a query."""
        analysis = self.analyze(query)

        recommendations = []
        for score in analysis.suggested_capabilities[:max_results]:
            cap = self._registry.get(score.capability_id)
            if cap:
                recommendations.append({
                    "id": score.capability_id,
                    "name": cap.get_name(),
                    "type": cap.get_type().value,
                    "score": round(score.score, 3),
                    "reasons": score.reasons,
                    "available": cap.check_availability(),
                })

        return recommendations

    def _score_types(self, words: set, query_lower: str) -> Dict[CapabilityType, float]:
        """Score each capability type based on keyword matches."""
        scores: Dict[CapabilityType, float] = {}

        for cap_type, keywords in TYPE_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                if kw in words:
                    score += 0.2
                elif kw in query_lower:
                    score += 0.1
            if score > 0:
                scores[cap_type] = min(score, 1.0)

        return scores

    def _score_capability(
        self,
        cap: Capability,
        query_lower: str,
        words: set,
        type_scores: Dict[CapabilityType, float],
    ) -> RelevanceScore:
        """Score a single capability for relevance."""
        cap_id = cap.get_id()
        cap_type = cap.get_type()
        score = 0.0
        reasons: List[str] = []

        # Type-based score
        type_score = type_scores.get(cap_type, 0.0)
        if type_score > 0:
            score += type_score * 0.3
            reasons.append(f"type_match:{cap_type.value}")

        # Pattern-based score
        patterns = CAPABILITY_PATTERNS.get(cap_id, [])
        for pattern in patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                score += 0.4
                reasons.append(f"pattern_match:{pattern[:30]}")
                break  # Only count pattern match once

        # Name/description keyword match
        cap_words = set(re.findall(r"\b\w+\b", (cap.get_name() + " " + cap.get_description()).lower()))
        common_words = words & cap_words
        if common_words:
            word_score = len(common_words) / max(len(words), 1) * 0.3
            score += word_score
            reasons.append(f"keyword_match:{','.join(list(common_words)[:3])}")

        # Availability bonus
        if cap.check_availability():
            score *= 1.1
        else:
            score *= 0.5

        return RelevanceScore(
            capability_id=cap_id,
            score=min(score, 1.0),
            reasons=reasons,
        )

    def build_context_summary(self, query: str) -> str:
        """Build a human-readable context summary."""
        analysis = self.analyze(query)

        lines = [f"Query analysis: '{query}'"]
        lines.append(f"Primary type: {analysis.primary_type.value if analysis.primary_type else 'unknown'}")
        lines.append(f"Confidence: {analysis.confidence:.1%}")

        if analysis.suggested_capabilities:
            lines.append("Suggested capabilities:")
            for score in analysis.suggested_capabilities[:5]:
                lines.append(f"  - {score.capability_id} (score: {score.score:.2f})")

        return "\n".join(lines)