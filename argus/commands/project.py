"""Argus /project command."""

from argus.context.project import ProjectProfile


def handle(repl, args) -> str:
    profile = repl.agent._project_context
    if not isinstance(profile, ProjectProfile):
        return "Project profile not available."

    lines = [
        f"Project: {profile.name or profile.root}",
        f"Path: {profile.root}",
    ]
    if profile.languages:
        lines.append(f"Languages: {', '.join(profile.languages)}")
    if profile.frameworks:
        lines.append(f"Frameworks: {', '.join(profile.frameworks)}")
    if profile.build_system:
        lines.append(f"Build system: {profile.build_system}")
    if profile.package_manager:
        lines.append(f"Package manager: {profile.package_manager}")
    if profile.test_system:
        lines.append(f"Test system: {profile.test_system}")
    if profile.test_command:
        lines.append(f"Test command: {profile.test_command}")
    if profile.formatter_command:
        lines.append(f"Formatter: {profile.formatter_command}")
    if profile.linter_command:
        lines.append(f"Linter: {profile.linter_command}")
    git_status = "clean" if profile.git_clean else "dirty"
    lines.append(f"Git: {profile.git_branch or 'unknown'} ({git_status})")
    if profile.conventions:
        lines.append(f"Conventions: {', '.join(profile.conventions)}")
    return "\n".join(lines)
