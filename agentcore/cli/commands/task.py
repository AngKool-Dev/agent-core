"""Task subcommand handlers for the argus CLI (Phase 5F)."""

from __future__ import annotations

from agentcore.cli.service import QueryService
from agentcore.cli.utils import print_error, print_json, truncate
from agentcore.task_registry import TaskRecord


def _task_source(record: TaskRecord) -> str:
    attrs = record.metadata or {}
    return str(attrs.get("source", "agent"))


def _task_runtime(record: TaskRecord) -> str:
    attrs = record.metadata or {}
    return str(attrs.get("runtime", ""))


def _task_attr(record: TaskRecord, key: str) -> str:
    attrs = record.metadata or {}
    return str(attrs.get(key, ""))


def _format_task_summary(record: TaskRecord) -> str:
    return (
        f"TASK ID: {record.task_id}\n"
        f"STATE:   {record.task_state.value}\n"
        f"SOURCE:  {_task_source(record)}\n"
        f"RUNTIME: {_task_runtime(record)}\n"
    )


def list_tasks(svc: QueryService, args) -> int:
    """argus task list"""
    records = svc.task_registry.list_tasks()

    state_filter = getattr(args, "state", None)
    source_filter = getattr(args, "source", None)
    runtime_filter = getattr(args, "runtime", None)

    filtered: list[TaskRecord] = []
    for rec in records:
        if state_filter:
            if rec.task_state.value.lower() != state_filter.lower():
                continue
        if source_filter:
            if _task_source(rec).lower() != source_filter.lower():
                continue
        if runtime_filter:
            if not _task_runtime(rec) or _task_runtime(rec).lower() != runtime_filter.lower():
                continue
        filtered.append(rec)

    if args.json:
        print_json([r.to_dict() for r in filtered])
        return 0

    if not filtered:
        print("No tasks found.")
        return 0

    header = f"{'TASK ID':<40} {'STATE':<12} {'SOURCE':<16} {'RUNTIME':<12}"
    print(header)
    print("-" * len(header))
    for rec in filtered:
        print(
            f"{rec.task_id:<40} {rec.task_state.value:<12} "
            f"{_task_source(rec):<16} {_task_runtime(rec):<12}"
        )

    print(f"\n{len(filtered)} task(s) shown.")
    return 0


def show_task(svc: QueryService, args) -> int:
    """argus task show <task_id>"""
    record = svc.task_registry.get(args.task_id)
    if record is None:
        try:
            task = svc.persistence.load_task(args.task_id)
            if task is not None:
                record = TaskRecord(
                    task_id=task.task_id,
                    user_request=task.user_request,
                    project=task.project,
                    task_state=task.current_state,
                    metadata=task.attributes,
                )
        except Exception:
            pass

    if record is None:
        print_error(f"Task not found: {args.task_id}")
        return 1

    lines = _format_task_summary(record).rstrip().split("\n")
    if record.user_request:
        lines.append(f"REQUEST: {truncate(record.user_request, 200)}")

    if _task_attr(record, "hermes_session_id"):
        lines.append(f"HERMES SESSION: {_task_attr(record, 'hermes_session_id')}")
    if _task_attr(record, "hermes_task_id"):
        lines.append(f"HERMES TASK:    {_task_attr(record, 'hermes_task_id')}")
    if _task_attr(record, "hermes_turn_id"):
        lines.append(f"HERMES TURN:    {_task_attr(record, 'hermes_turn_id')}")
    if _task_attr(record, "hermes_session_key"):
        lines.append(f"HERMES KEY:     {_task_attr(record, 'hermes_session_key')}")

    lines.append(f"CREATED:  {record.created_at}")
    lines.append(f"UPDATED:  {record.updated_at}")

    print("\n".join(lines))
    return 0


def show_task_json(svc: QueryService, args) -> int:
    """argus task show <task_id> --json"""
    record = svc.task_registry.get(args.task_id)
    if record is None:
        try:
            task = svc.persistence.load_task(args.task_id)
            if task is not None:
                record = TaskRecord(
                    task_id=task.task_id,
                    user_request=task.user_request,
                    project=task.project,
                    task_state=task.current_state,
                    metadata=task.attributes,
                )
        except Exception:
            pass

    if record is None:
        print_error(f"Task not found: {args.task_id}")
        return 1

    print_json(record.to_dict())
    return 0


def _resolve_task_record(svc: QueryService, task_id: str) -> TaskRecord | None:
    record = svc.task_registry.get(task_id)
    if record is not None:
        return record
    try:
        task = svc.persistence.load_task(task_id)
        if task is not None:
            return TaskRecord(
                task_id=task.task_id,
                user_request=task.user_request,
                project=task.project,
                task_state=task.current_state,
                metadata=task.attributes,
            )
    except Exception:
        pass
    return None


def task_events(svc: QueryService, args) -> int:
    """argus task events <task_id>"""
    record = _resolve_task_record(svc, args.task_id)
    if record is None:
        print_error(f"Task not found: {args.task_id}")
        return 1

    try:
        observations = svc.observation_store.list_by_task(
            args.task_id, limit=getattr(args, "limit", 1000)
        )
    except Exception as e:
        print_error(f"Failed to query observations: {e}")
        return 1

    observations.sort(key=lambda o: o.get("sequence", 0))

    if args.json:
        print_json(observations)
        return 0

    if not observations:
        print(f"No observations for task: {args.task_id}")
        return 0

    from agentcore.cli.utils import format_observation_row

    header = f"{'SEQ':<5} {'TIME':<10} {'TYPE':<24} {'TOOL':<16}"
    print(header)
    print("-" * len(header))
    for obs in observations:
        print(format_observation_row(obs, full=getattr(args, "full", False)))

    print(f"\n{len(observations)} observation(s).")
    return 0


def task_memories(svc: QueryService, args) -> int:
    """argus task memories <task_id>"""
    record = _resolve_task_record(svc, args.task_id)
    if record is None:
        print_error(f"Task not found: {args.task_id}")
        return 1

    project = args.task_id
    min_conf_str = getattr(args, "min_confidence", None)
    mem_type = getattr(args, "type", None)

    min_conf, err = (None, None)
    if min_conf_str:
        from agentcore.cli.utils import parse_confidence

        min_conf, err = parse_confidence(min_conf_str)
        if err:
            print_error(err)
            return 1

    try:
        memories = svc.memory_backend.list(
            project=project,
            type=mem_type,
            limit=getattr(args, "limit", 50),
        )
    except Exception as e:
        print_error(f"Failed to query memories: {e}")
        return 1

    if min_conf is not None:
        memories = [m for m in memories if m.get("confidence", 0.5) >= min_conf]

    if args.json:
        print_json(memories)
        return 0

    if not memories:
        print(f"No memories for task: {args.task_id}")
        return 0

    from agentcore.cli.utils import confidence_label

    for mem in memories:
        mem_id = mem.get("id", "?")
        mem_type_val = mem.get("type", "?")
        conf = mem.get("confidence")
        label = confidence_label(conf)
        conf_str = f"{label} ({conf:.2f})" if conf is not None else label
        content = truncate(mem.get("content", "").strip(), 200)

        lines = [
            f"MEMORY: {mem_id}",
            f"TYPE:   {mem_type_val}",
            f"CONFIDENCE: {conf_str}",
        ]
        created = mem.get("created_at", "")
        if created:
            lines.append(f"CREATED:  {created}")
        print("\n".join(lines))
        print("---")
        print(content)

        source_obs = mem.get("source_observation_ids", [])
        if not source_obs:
            source_obs = (
                mem.get("metadata", {}).get("source_observation_ids", [])
                if isinstance(mem.get("metadata"), dict)
                else []
            )
        if source_obs:
            print("SOURCE OBSERVATIONS:")
            for sid in source_obs:
                print(f"  {sid}")
        print()

    print(f"{len(memories)} memory(s) shown for task: {args.task_id}")
    return 0
