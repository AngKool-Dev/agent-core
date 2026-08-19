from .models import Skill


class SkillLoader:
    def __init__(self):
        self._loaded_skills: dict[str, str] = {}

    def load(self, skill: Skill) -> str:
        if not skill.path:
            raise ValueError(f"Skill {skill.name} has no path")

        skill_md = f"{skill.path}/SKILL.md"
        try:
            content = open(skill_md, encoding="utf-8").read()
        except FileNotFoundError:
            raise ValueError(f"Cannot find SKILL.md at {skill_md}")

        self._loaded_skills[skill.name] = content
        return content

    def get_loaded(self, name: str) -> str | None:
        return self._loaded_skills.get(name)

    def is_loaded(self, name: str) -> bool:
        return name in self._loaded_skills

    def unload(self, name: str) -> bool:
        if name in self._loaded_skills:
            del self._loaded_skills[name]
            return True
        return False
