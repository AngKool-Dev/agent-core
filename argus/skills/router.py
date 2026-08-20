"""Argus skill router."""

from typing import List, Optional

from .registry import SkillRegistry
from .skill import Skill


class SkillRouter:
    def __init__(self, registry: Optional[SkillRegistry] = None):
        self._registry = registry or SkillRegistry()

    def route(self, request: str, project_context: Optional[dict] = None, max_skills: int = 5) -> List[Skill]:
        deterministic = self._route_deterministic(request, project_context)
        if deterministic:
            return self._deduplicate(deterministic)[:max_skills]

        return self._route_fallback(request)[:max_skills]

    def _route_deterministic(self, request: str, project_context: Optional[dict]) -> List[Skill]:
        request_lower = request.lower()
        candidates: List[tuple[int, Skill]] = []

        for skill in self._registry.list():
            score = 0
            if skill.matches(request):
                score += 10
                for trigger in skill.triggers:
                    if trigger.lower() in request_lower:
                        score += 5

            if project_context:
                language = project_context.get("language", "")
                if language and language in skill.name:
                    score += 3

            if score > 0:
                candidates.append((score, skill))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [skill for _, skill in candidates]

    def _route_fallback(self, request: str) -> List[Skill]:
        words = request.lower().split()
        matches = []

        for skill in self._registry.list():
            for trigger in skill.triggers:
                if any(trigger.lower() in word for word in words):
                    matches.append(skill)
                    break

        return matches

    def _deduplicate(self, skills: List[Skill]) -> List[Skill]:
        seen = set()
        unique = []
        for skill in skills:
            if skill.name not in seen:
                seen.add(skill.name)
                unique.append(skill)
        return unique
