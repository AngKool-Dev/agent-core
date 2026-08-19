from pathlib import Path

from agentcore.router import RoutingResult, SkillRouter
from agentcore.skills import Skill, SkillRegistry


def _create_temp_skills(tmp_path: Path, names: list[str]) -> Path:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    for name in names:
        skill_dir = skills_dir / name
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            f"---\nname: {name}\ndescription: {name} workflow and guidance\n---\n\n# {name}\n",
            encoding="utf-8",
        )
    return skills_dir


class TestSkillRegistryDiscovery:
    def test_discover_existing_skills(self, tmp_path):
        names = ["skill-router", "debugging-and-error-recovery"]
        skills_dir = _create_temp_skills(tmp_path, names)
        registry = SkillRegistry()
        skills = registry.discover([str(skills_dir)])

        assert len(skills) > 0
        skill_names = [s.name for s in skills]
        assert "skill-router" in skill_names
        assert "debugging-and-error-recovery" in skill_names

    def test_skill_has_required_fields(self, tmp_path):
        names = ["skill-router", "debugging-and-error-recovery"]
        skills_dir = _create_temp_skills(tmp_path, names)
        registry = SkillRegistry()
        skills = registry.discover([str(skills_dir)])

        for skill in skills:
            assert skill.name
            assert skill.path
            assert isinstance(skill.trigger_keywords, list)

    def test_find_skill_by_name(self, tmp_path):
        names = ["debugging-and-error-recovery"]
        skills_dir = _create_temp_skills(tmp_path, names)
        registry = SkillRegistry()
        registry.discover([str(skills_dir)])

        skill = registry.find("debugging-and-error-recovery")
        assert skill is not None
        assert skill.name == "debugging-and-error-recovery"

    def test_list_all_skills(self, tmp_path):
        names = [
            "debugging-and-error-recovery",
            "test-driven-development",
            "spec-driven-development",
            "incremental-implementation",
            "code-review-and-quality",
            "code-simplification",
            "api-and-interface-design",
            "frontend-ui-engineering",
            "git-workflow-and-versioning",
            "security-and-hardening",
            "performance-optimization",
            "documentation-and-adrs",
            "ci-cd-and-automation",
            "shipping-and-launch",
            "planning-and-task-breakdown",
            "source-driven-development",
            "observability-and-instrumentation",
            "context-engineering",
            "db-obsidian",
            "idea-refine",
            "interview-me",
            "deprecation-and-migration",
            "doubt-driven-development",
            "using-agent-skills",
            "browser-testing-with-devtools",
        ]
        skills_dir = _create_temp_skills(tmp_path, names)
        registry = SkillRegistry()
        registry.discover([str(skills_dir)])

        skills = registry.list()
        assert len(skills) >= 20

    def test_nonexistent_skill_not_found(self, tmp_path):
        names = ["debugging-and-error-recovery"]
        skills_dir = _create_temp_skills(tmp_path, names)
        registry = SkillRegistry()
        registry.discover([str(skills_dir)])

        skill = registry.find("nonexistent-skill")
        assert skill is None


class TestSkillRouter:
    def test_route_bug_fix(self):
        skills = [
            Skill("debugging-and-error-recovery", "/path"),
            Skill("test-driven-development", "/path"),
        ]
        router = SkillRouter(skills)

        result = router.route("Fix the crash in the launcher")

        assert "debugging-and-error-recovery" in result.selected_skills

    def test_route_testing_request(self):
        skills = [
            Skill("test-driven-development", "/path"),
            Skill("debugging-and-error-recovery", "/path"),
        ]
        router = SkillRouter(skills)

        result = router.route("Write tests for the parser")

        assert "test-driven-development" in result.selected_skills

    def test_route_with_multiple_keywords(self):
        skills = [
            Skill("debugging-and-error-recovery", "/path"),
            Skill("test-driven-development", "/path"),
            Skill("code-review-and-quality", "/path"),
        ]
        router = SkillRouter(skills)

        result = router.route("Write tests and debug the failing build")

        assert len(result.selected_skills) >= 1
        assert result.confidence > 0

    def test_confidence_calculation(self):
        skills = [Skill("debugging-and-error-recovery", "/path")]
        router = SkillRouter(skills)

        result = router.route("debug the issue")

        assert 0.0 <= result.confidence <= 1.0

    def test_no_matched_skills(self):
        skills = [Skill("unrelated-skill", "/path")]
        router = SkillRouter(skills)

        result = router.route("some completely unrelated request")

        assert len(result.selected_skills) == 0

    def test_routing_result_structure(self):
        skills = [Skill("debugging-and-error-recovery", "/path")]
        router = SkillRouter(skills)

        result = router.route("Fix the bug")

        assert isinstance(result, RoutingResult)
        assert hasattr(result, "selected_skills")
        assert hasattr(result, "explanation")
        assert hasattr(result, "confidence")
