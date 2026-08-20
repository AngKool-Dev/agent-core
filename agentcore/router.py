import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from agentcore.skills.models import Skill


TRIGGER_KEYWORDS = {
    "debugging-and-error-recovery": ["debug", "bug", "error", "fail", "crash", "traceback", "broken", "not working", "fix"],
    "test-driven-development": ["test", "tdd", "pytest", "jest", "verify", "test failure", "test passes", "test"],
    "spec-driven-development": ["spec", "specification", "requirements", "acceptance criteria", "define", "plan"],
    "incremental-implementation": ["implement", "feature", "build", "create", "add", "new feature", "change"],
    "code-review-and-quality": ["review", "quality", "pr", "merge", "pull request", "pre-merge", "check"],
    "code-simplification": ["refactor", "simplify", "clean", "reduce complexity", "technical debt", "simplify"],
    "api-and-interface-design": ["api", "rest", "graphql", "endpoint", "interface", "contract", "module"],
    "frontend-ui-engineering": ["ui", "frontend", "component", "react", "vue", "angular", "tailwind", "css"],
    "git-workflow-and-versioning": ["git", "commit", "branch", "merge", "conflict", "version"],
    "security-and-hardening": ["security", "auth", "authorship", "vulnerability", "xss", "injection", "secret"],
    "performance-optimization": ["performance", "optimize", "slow", "bottleneck", "profile", "latency"],
    "documentation-and-adrs": ["document", "adr", "readme", "architecture decision", "record decision"],
    "ci-cd-and-automation": ["ci", "cd", "pipeline", "github actions", "deployment", "build"],
    "shipping-and-launch": ["ship", "launch", "deploy", "release", "production", "publish", "version"],
    "planning-and-task-breakdown": ["plan", "breakdown", "estimate", "tasks", "scope", "parallel"],
    "source-driven-development": ["source", "docs", "official", "documentation", "reference", "authoritative"],
    "observability-and-instrumentation": ["log", "metric", "trace", "monitoring", "observability", "instrument"],
    "context-engineering": ["context", "session", "history", "previous work", "remember"],
    "db-obsidian": ["memory", "vault", "obsidian", "remember", "session history", "persistent"],
    "idea-refine": ["idea", "brainstorm", "concept", "refine", "expand options", "variant"],
    "interview-me": ["interview", "clarify", "requirements", "what do you need", "underspecified"],
    "deprecation-and-migration": ["migrate", "deprecate", "sunset", "remove old", "upgrade", "replace"],
    "doubt-driven-development": ["adversarial", "review", "verify", "cross-examine", "high stakes", "adversarial"],
    "using-agent-skills": ["skill", "discover", "invoke", "which skill", "workflow", "meta"],
    "browser-testing-with-devtools": ["browser", "DOM", "Chrome DevTools", "network request", "console error", "performance"],
}


@dataclass
class SkillMatch:
    skill: str
    confidence: float
    reason: str
    weight: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill": self.skill,
            "confidence": self.confidence,
            "reason": self.reason,
            "weight": self.weight,
        }


@dataclass
class RoutingResult:
    selected_skills: List[str]
    loaded_skills: List[Skill] = field(default_factory=list)
    explanation: str = ""
    confidence: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_skills": self.selected_skills,
            "loaded_skills": [s.to_dict() for s in self.loaded_skills],
            "explanation": self.explanation,
            "confidence": self.confidence,
            "attributes": self.attributes,
        }


class SkillRouter:
    def __init__(self, skills: List[Skill]):
        self.skills = {s.name: s for s in skills}
        self._keyword_to_skill = self._build_keyword_index()

    def _build_keyword_index(self) -> Dict[str, str]:
        index = {}
        for skill_name, keywords in TRIGGER_KEYWORDS.items():
            for kw in keywords:
                index[kw.lower()] = skill_name
        return index

    def route(self, user_prompt: str, project_context: Optional[Dict[str, Any]] = None) -> RoutingResult:
        prompt_lower = user_prompt.lower()
        matched_skills: List[SkillMatch] = []
        
        project_type = project_context.get("language") if project_context else None
        
        for skill_name, keywords in TRIGGER_KEYWORDS.items():
            score = self._score_skill(skill_name, keywords, prompt_lower, project_type)
            if score > 0:
                matched_skills.append(SkillMatch(
                    skill=skill_name,
                    confidence=score,
                    reason=self._build_skill_reason(skill_name, keywords, prompt_lower),
                    weight=score,
                ))

        matched_skills.sort(key=lambda m: m.weight, reverse=True)
        
        selected = [m.skill for m in matched_skills[:4]]
        loaded = [self.skills.get(m.skill) for m in matched_skills[:4] if m.skill in self.skills]
        loaded = [s for s in loaded if s is not None]
        
        confidence = max([m.confidence for m in matched_skills], default=0.0)
        explanation = self._build_overall_explanation(matched_skills[:4], prompt_lower)
        
        attributes = {
            "project_type": project_type,
            "total_matched": len(matched_skills),
        }

        return RoutingResult(
            selected_skills=selected,
            loaded_skills=loaded,
            explanation=explanation,
            confidence=min(1.0, confidence),
            attributes=attributes,
        )

    def _score_skill(self, skill_name: str, keywords: List[str], prompt: str, project_type: Optional[str]) -> float:
        keyword_matches = sum(1 for kw in keywords if kw in prompt)
        
        base_score = keyword_matches / max(len(keywords), 1)
        
        if project_type:
            project_keyword_scores = {
                "rust": {"debugging-and-error-recovery": 0.2, "test-driven-development": 0.15, "incremental-implementation": 0.15},
                "python": {"test-driven-development": 0.2, "debugging-and-error-recovery": 0.15, "spec-driven-development": 0.1},
                "javascript": {"frontend-ui-engineering": 0.15, "test-driven-development": 0.15, "incremental-implementation": 0.15},
            }
            if skill_name in project_keyword_scores.get(project_type, {}):
                base_score += project_keyword_scores[project_type][skill_name]
        
        return min(1.0, base_score)

    def _build_skill_reason(self, skill_name: str, keywords: List[str], prompt: str) -> str:
        matched = [kw for kw in keywords if kw in prompt][:3]
        return f"{skill_name} (matched: {', '.join(matched)})" if matched else skill_name

    def _build_overall_explanation(self, matches: List[SkillMatch], prompt: str) -> str:
        if not matches:
            return "No skills matched the user prompt"
        
        reasons = [f"{m.skill} (confidence: {m.confidence:.2f})" for m in matches]
        return "Selected skills: " + "; ".join(reasons)

    def get_routing_report(self, result: RoutingResult) -> Dict[str, Any]:
        all_skill_names = list(self.skills.keys())
        not_loaded = [s for s in all_skill_names if s not in result.selected_skills]

        return {
            "selected": result.selected_skills,
            "loaded": [s.name for s in result.loaded_skills],
            "not_selected": not_loaded[:10],
            "confidence": result.confidence,
            "explanation": result.explanation,
            "attributes": result.attributes,
        }