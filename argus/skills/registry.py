"""Argus skill registry."""

from pathlib import Path
from typing import Dict, List, Optional

from .loader import load_skills_from_directory
from .skill import Skill


class SkillRegistry:
    def __init__(self, skill_paths: Optional[List[Path]] = None):
        self._skill_paths = list(skill_paths) if skill_paths else []
        self._skills: Dict[str, Skill] = {}

    def discover(self, skill_paths: Optional[List[Path]] = None) -> List[Skill]:
        paths = [Path(p) for p in skill_paths] if skill_paths else self._skill_paths
        discovered = []

        for path in paths:
            for skill in load_skills_from_directory(path):
                if skill.name not in self._skills:
                    self._skills[skill.name] = skill
                    discovered.append(skill)

        return discovered

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list(self) -> List[Skill]:
        return list(self._skills.values())

    def search(self, query: str) -> List[Skill]:
        query_lower = query.lower()
        matches = []
        for skill in self._skills.values():
            score = 0
            if any(trigger.lower() in query_lower for trigger in skill.triggers):
                score += 10
            if query_lower in skill.name.lower():
                score += 5
            if query_lower in skill.description.lower():
                score += 3
            if score > 0:
                matches.append((score, skill))
        matches.sort(key=lambda x: x[0], reverse=True)
        return [skill for _, skill in matches]
