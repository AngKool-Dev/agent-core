import re
from pathlib import Path
from typing import Any, List, Optional

from .models import Skill


KEYWORD_MAP = {
    "debugging-and-error-recovery": ["debug", "bug", "error", "fail", "crash", "traceback", "root cause", "fix"],
    "test-driven-development": ["test", "tdd", "pytest", "jest", "verify", "coverage", "failing test", "reproduce"],
    "spec-driven-development": ["spec", "specification", "requirements", "acceptance criteria", "define", "plan"],
    "incremental-implementation": ["implement", "feature", "build", "create", "change", "add", "new"],
    "code-review-and-quality": ["review", "quality", "pr", "merge", "pull request", "pre-merge", "check"],
    "code-simplification": ["refactor", "simplify", "clean", "complexity", "reduce", "debt"],
    "api-and-interface-design": ["api", "rest", "graphql", "endpoint", "interface", "contract", "module"],
    "frontend-ui-engineering": ["ui", "frontend", "component", "react", "vue", "angular", "tailwind", "css", "page"],
    "git-workflow-and-versioning": ["git", "commit", "branch", "merge", "conflict", "version", "tag", "release"],
    "security-and-hardening": ["security", "auth", "authorship", "vulnerability", "xss", "injection", "secret", "password"],
    "performance-optimization": ["performance", "optimize", "slow", "bottleneck", "profile", "latency", "speed"],
    "documentation-and-adrs": ["document", "adr", "readme", "architecture decision", "record decision", "docs"],
    "ci-cd-and-automation": ["ci", "cd", "pipeline", "github actions", "deployment", "build", "automation"],
    "shipping-and-launch": ["ship", "launch", "deploy", "release", "production", "publish", "version"],
    "planning-and-task-breakdown": ["plan", "breakdown", "estimate", "tasks", "scope", "parallel", "work"],
    "source-driven-development": ["source", "docs", "official", "documentation", "reference", "authoritative"],
    "observability-and-instrumentation": ["log", "metric", "trace", "monitoring", "observability", "instrumentation"],
    "context-engineering": ["context", "session", "history", "previous work", "prompt engineering"],
    "db-obsidian": ["memory", "vault", "obsidian", "remember", "session history", "persistent"],
    "idea-refine": ["idea", "brainstorm", "concept", "refine", "expand options", "variant"],
    "interview-me": ["interview", "clarify", "requirements", "what do you need", "underspecified"],
    "deprecation-and-migration": ["migrate", "deprecate", "sunset", "remove old", "upgrade", "replace"],
    "doubt-driven-development": ["adversarial", "review", "verify", "cross-examine", "high stakes", "adversarial review"],
    "using-agent-skills": ["skill", "discover", "invoke", "which skill", "workflow", "meta"],
    "browser-testing-with-devtools": ["browser", "DOM", "Chrome DevTools", "network request", "console error", "performance"],
}


class SkillRegistry:
    def __init__(self, skill_paths: Optional[List[str]] = None):
        self._skills: dict[str, Skill] = {}
        self._skill_paths = [Path(p) for p in skill_paths] if skill_paths else []

    def discover(self, skill_paths: Optional[List[str]] = None) -> List[Skill]:
        paths = [Path(p) for p in skill_paths] if skill_paths else self._skill_paths
        if not paths:
            return []

        discovered = []
        for skill_path in paths:
            if not skill_path.exists():
                continue
            for skill_dir in skill_path.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skill = self._load_skill_metadata(skill_dir)
                    if skill:
                        self._skills[skill.name] = skill
                        discovered.append(skill)

        return discovered

    def _load_skill_metadata(self, skill_dir: Path) -> Optional[Skill]:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        content = skill_md.read_text(encoding="utf-8")
        
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        metadata = {}
        description = ""
        
        if frontmatter_match:
            metadata_str = frontmatter_match.group(1)
            metadata = self._parse_frontmatter(metadata_str)
            description = content[frontmatter_match.end():].strip()
        else:
            description = content.strip()

        name = skill_dir.name
        trigger_keywords = self._extract_keywords(name, description)

        return Skill(
            name=name,
            path=str(skill_dir),
            description=metadata.get("description", "") or description[:200],
            metadata=metadata,
            trigger_keywords=trigger_keywords,
        )

    def _parse_frontmatter(self, text: str) -> dict:
        result = {}
        for line in text.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip().strip('"')
        return result

    def _extract_keywords(self, name: str, description: str) -> List[str]:
        return KEYWORD_MAP.get(name, [])[:10]

    def list(self) -> List[Skill]:
        return list(self._skills.values())

    def find(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def load(self, name: str) -> bool:
        skill = self._skills.get(name)
        if skill:
            skill.loaded = True
            return True
        return False