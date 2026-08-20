"""Argus skill loader."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .skill import Skill


def load_skill_from_path(skill_path: Path) -> Optional[Skill]:
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception:
        return None

    name = skill_path.name
    description = ""
    instructions = content
    triggers: List[str] = []
    metadata: Dict[str, str] = {}

    frontmatter_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if frontmatter_match:
        metadata = _parse_frontmatter(frontmatter_match.group(1))
        instructions = content[frontmatter_match.end():]
        description = metadata.get("description", instructions[:200])
        triggers_str = metadata.get("triggers", "")
        if triggers_str:
            triggers = [t.strip() for t in triggers_str.split(",") if t.strip()]
    else:
        description = content[:200].strip()
        instructions = content

    if not triggers and metadata.get("name"):
        triggers = [metadata["name"]]

    return Skill(
        name=name,
        description=description,
        instructions=instructions.strip(),
        triggers=triggers,
        metadata=metadata,
        path=skill_path,
    )


def load_skills_from_directory(directory: Path) -> List[Skill]:
    if not directory.exists() or not directory.is_dir():
        return []

    skills = []
    for skill_dir in sorted(directory.iterdir()):
        if skill_dir.is_dir():
            skill = load_skill_from_path(skill_dir)
            if skill:
                skills.append(skill)
    return skills


def _parse_frontmatter(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for line in text.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip('"')
    return result
