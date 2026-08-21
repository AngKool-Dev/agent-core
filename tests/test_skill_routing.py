import pytest
import os
from pathlib import Path
from agentcore.skills import Skill, SkillRegistry
from agentcore.router import SkillRouter, RoutingResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_PATH = str(PROJECT_ROOT / "unified_folder" / "ObsidianVault" / "agent-skills" / "skills")


class TestSkillRegistryDiscovery:
    def test_discover_existing_skills(self):
        registry = SkillRegistry()
        skills = registry.discover([SKILLS_PATH])
        
        assert len(skills) > 0
        skill_names = [s.name for s in skills]
        assert "skill-router" in skill_names
        assert "debugging-and-error-recovery" in skill_names

    def test_skill_has_required_fields(self):
        registry = SkillRegistry()
        skills = registry.discover([SKILLS_PATH])
        
        for skill in skills:
            assert skill.name
            assert skill.path
            assert isinstance(skill.trigger_keywords, list)

    def test_find_skill_by_name(self):
        registry = SkillRegistry()
        registry.discover([SKILLS_PATH])
        
        skill = registry.find("debugging-and-error-recovery")
        assert skill is not None
        assert skill.name == "debugging-and-error-recovery"

    def test_list_all_skills(self):
        registry = SkillRegistry()
        registry.discover([SKILLS_PATH])
        
        skills = registry.list()
        assert len(skills) >= 20

    def test_nonexistent_skill_not_found(self):
        registry = SkillRegistry()
        registry.discover([SKILLS_PATH])
        
        skill = registry.find("nonexistent-skill")
        assert skill is None


class TestSkillRouter:
    def test_route_bug_fix(self):
        skills = [Skill("debugging-and-error-recovery", "/path"), Skill("test-driven-development", "/path")]
        router = SkillRouter(skills)
        
        result = router.route("Fix the crash in the launcher")
        
        assert "debugging-and-error-recovery" in result.selected_skills

    def test_route_testing_request(self):
        skills = [Skill("test-driven-development", "/path"), Skill("debugging-and-error-recovery", "/path")]
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