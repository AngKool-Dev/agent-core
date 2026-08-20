"""Argus message formatting for model providers."""

from typing import Any, Dict, List, Optional

from argus.model.provider import Message, ToolCall


def build_messages(
    user_request: str,
    conversation: List[Dict[str, Any]],
    project_context: Dict[str, Any],
    available_tools: List[Dict[str, Any]],
    recent_observations: List[str],
    current_step: str = "investigate",
    active_skills: Optional[List[Dict[str, Any]]] = None,
    skill_instructions: str = "",
    memory_context: str = "",
) -> List[Message]:
    system = _build_system_prompt(
        project_context,
        available_tools,
        current_step,
        active_skills=active_skills,
        skill_instructions=skill_instructions,
        memory_context=memory_context,
    )
    messages = [Message(role="system", content=system)]

    for msg in conversation[-20:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant", "system"):
            messages.append(Message(role=role, content=content))

    if recent_observations:
        obs_text = "\n".join(f"- {o}" for o in recent_observations[-3:])
        messages.append(Message(role="user", content=f"[Recent observations]\n{obs_text}\nContinue based on these results."))

    messages.append(Message(role="user", content=user_request))

    return messages


def _build_system_prompt(
    project_context: Dict[str, Any],
    available_tools: List[Dict[str, Any]],
    current_step: str,
    active_skills: Optional[List[Dict[str, Any]]] = None,
    skill_instructions: str = "",
    memory_context: str = "",
) -> str:
    lines = [
        "You are Argus, an autonomous coding agent.",
        "Your goal is to complete the user's task by reasoning, using tools, and observing results.",
        "",
        "## Current Step",
        current_step,
        "",
        "## Project Context",
    ]

    name = project_context.get("name", "unknown")
    language = project_context.get("language", "unknown")
    path = project_context.get("path", ".")
    lines.append(f"- Project: {name}")
    lines.append(f"- Language: {language}")
    lines.append(f"- Path: {path}")

    readme = project_context.get("readme")
    if readme:
        lines.append(f"- README: {readme[:500]}")

    git = project_context.get("git_status")
    if git:
        lines.append(f"- Git branch: {git.get('branch', 'unknown')}")
        changes = git.get("changes", [])
        if changes:
            lines.append(f"- Git changes: {len(changes)} files")

    lines.extend([
        "",
        "## Available Tools",
        "You have access to the following tools. Use them when needed.",
    ])

    for tool in available_tools:
        lines.append(f"- {tool.get('name')}: {tool.get('description', '')}")

    if active_skills:
        lines.extend([
            "",
            "## Active Skills",
            "The following skills are active for this task. Follow their guidance when relevant:",
        ])
        for skill in active_skills:
            lines.append(f"- {skill.get('name')}: {skill.get('description', '')}")

    if skill_instructions:
        lines.extend([
            "",
            "## Skill Instructions",
            skill_instructions,
        ])

    if memory_context:
        lines.extend([
            "",
            "## Relevant Project Memory",
            memory_context,
        ])

    lines.extend([
        "",
        "## Output Format",
        "When you need to use tools, return tool calls in this exact JSON format:",
        '{"tool_calls": [{"tool_name": "tool_name", "arguments": {"key": "value"}}]}',
        "",
        "When the task is complete, return a final response explaining what you did.",
        "Be concise. Focus on results.",
        "",
        "## Important Rules",
        "- Always verify changes with tests when possible.",
        "- Read files before modifying them.",
        "- If a tool fails, try a different approach.",
        "- Do not repeat the same tool call more than twice without changing strategy.",
        "- When finished, provide a clear summary of changes.",
    ])

    return "\n".join(lines)


def parse_model_output(content: str) -> tuple[str, List[ToolCall]]:
    tool_calls: List[ToolCall] = []
    text = content

    try:
        import json
        import re

        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            raw_calls = data.get("tool_calls", [])
            for i, call in enumerate(raw_calls):
                tool_calls.append(ToolCall(
                    tool_name=call.get("tool_name") or call.get("tool") or "",
                    arguments=call.get("arguments", {}),
                    call_id=call.get("call_id") or f"call_{i}",
                ))
            text = data.get("content") or data.get("response") or content
            if not tool_calls and text:
                tool_calls = []
    except Exception:
        pass

    return text, tool_calls
