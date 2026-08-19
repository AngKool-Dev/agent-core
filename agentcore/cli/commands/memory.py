"""Memory subcommand handlers for the argus CLI (Phase 5F)."""

from __future__ import annotations

from agentcore.cli.service import QueryService
from agentcore.cli.utils import (
    confidence_label,
    parse_confidence,
    print_error,
    print_json,
    truncate,
)


def _filter_by_confidence(memories: list[dict], min_conf: float | None) -> list[dict]:
    if min_conf is None:
        return memories
    return [m for m in memories if m.get("confidence", 0.5) >= min_conf]


def _filter_by_type(memories: list[dict], mem_type: str | None) -> list[dict]:
    if mem_type is None:
        return memories
    return [m for m in memories if m.get("type") == mem_type]


def memory_search(svc: QueryService, args) -> int:
    """argus memory search <query>"""
    if not args.query:
        print_error("A search query is required.")
        return 1

    min_conf, err = (None, None)
    if getattr(args, "min_confidence", None):
        min_conf, err = parse_confidence(args.min_confidence)
        if err:
            print_error(err)
            return 1

    mem_type = getattr(args, "type", None)
    limit = getattr(args, "limit", 20)

    try:
        results = svc.memory_backend.search(
            args.query,
            project=None,
            limit=limit,
            min_confidence=min_conf,
            memory_type=mem_type,
        )
    except TypeError:
        results = svc.memory_backend.search(args.query, limit=limit)
        results = _filter_by_type(results, mem_type)
        results = _filter_by_confidence(results, min_conf)
    except Exception as e:
        print_error(f"Search failed: {e}")
        return 1

    if args.json:
        print_json(results)
        return 0

    if not results:
        print(f"No memories found matching: {args.query}")
        return 0

    for i, mem in enumerate(results, 1):
        mem_id = mem.get("id", "?")
        mem_type_val = mem.get("type", "?")
        conf = mem.get("confidence")
        label = confidence_label(conf)
        conf_str = f"{label} ({conf:.2f})" if conf is not None else label
        content = truncate(mem.get("content", "").strip(), 200)
        project = mem.get("project", "")

        print(f"{i}. {mem_id}")
        print(f"   TYPE:      {mem_type_val}")
        print(f"   CONFIDENCE: {conf_str}")
        if project:
            print(f"   TASK:      {project}")
        created = mem.get("created_at", "")
        if created:
            print(f"   CREATED:   {created}")
        print(f"   '{content}'")
        print()

    print(f"{len(results)} result(s).")
    return 0


def memory_show(svc: QueryService, args) -> int:
    """argus memory show <memory_id>"""
    try:
        mem = svc.memory_backend.get(args.memory_id)
    except Exception as e:
        print_error(f"Failed to retrieve memory: {e}")
        return 1

    if mem is None:
        print_error(f"Memory not found: {args.memory_id}")
        return 1

    if args.json:
        print_json(mem)
        return 0

    conf = mem.get("confidence")
    label = confidence_label(conf)
    conf_str = f"{label} ({conf:.2f})" if conf is not None else label

    lines = [
        "─" * 60,
        f"Memory:  {mem.get('id', '?')}",
        f"Type:    {mem.get('type', '?')}",
        f"Confidence: {conf_str}",
    ]

    reason = mem.get("confidence_reason")
    if not reason:
        reason = (
            mem.get("metadata", {}).get("confidence_reason")
            if isinstance(mem.get("metadata"), dict)
            else None
        )
    if reason:
        lines.append(f"Reason:  {reason}")

    project = mem.get("project", "")
    if project:
        lines.append(f"Task:    {project}")
    session = mem.get("session_id", "")
    if session:
        lines.append(f"Session: {session}")
    source = mem.get("source", "")
    if source:
        lines.append(f"Source:  {source}")
    created = mem.get("created_at", "")
    if created:
        lines.append(f"Created: {created}")
    updated = mem.get("updated_at", "")
    if updated:
        lines.append(f"Updated: {updated}")
    lines.append("─" * 60)

    print("\n".join(lines))
    content = mem.get("content", "").strip()
    if content:
        print()
        print(content)

    print("\n─" * 60)
    return 0


def memory_confidence(svc: QueryService, args) -> int:
    """argus memory confidence <memory_id>"""
    try:
        mem = svc.memory_backend.get(args.memory_id)
    except Exception as e:
        print_error(f"Failed to retrieve memory: {e}")
        return 1

    if mem is None:
        print_error(f"Memory not found: {args.memory_id}")
        return 1

    conf = mem.get("confidence")
    label = confidence_label(conf)

    reason = mem.get("confidence_reason")
    if not reason:
        reason = (
            mem.get("metadata", {}).get("confidence_reason")
            if isinstance(mem.get("metadata"), dict)
            else None
        )
    if not reason:
        reason = "not available"

    project = mem.get("project", "")
    source_obs = mem.get("source_observation_ids", [])
    if not source_obs:
        source_obs = (
            mem.get("metadata", {}).get("source_observation_ids", [])
            if isinstance(mem.get("metadata"), dict)
            else []
        )

    if args.json:
        print_json(
            {
                "memory_id": mem.get("id", ""),
                "confidence": conf,
                "confidence_level": label,
                "confidence_reason": reason,
                "task_id": project,
                "source_observation_ids": source_obs,
            }
        )
        return 0

    lines = [
        f"Memory:  {mem.get('id', '?')}",
        f"Confidence: {label}",
    ]
    if conf is not None:
        lines.append(f"Score:   {conf:.2f}")
    lines.append(f"Reason:  {reason}")
    if project:
        lines.append(f"Task:    {project}")

    print("\n".join(lines))

    if source_obs:
        print("\nSource observations:")
        for sid in source_obs:
            print(f"  - {sid}")

    return 0
