"""Argus file context helpers."""

from pathlib import Path
from typing import List, Optional


def read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    slice_lines = lines[offset : offset + limit]
    return "\n".join(
        f"{i + 1 + offset}: {line}" for i, line in enumerate(slice_lines)
    )


def write_file(path: str, content: str, mode: str = "overwrite") -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "append":
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)
    else:
        file_path.write_text(content, encoding="utf-8")


def edit_file(path: str, old_string: str, new_string: str) -> None:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    content = file_path.read_text(encoding="utf-8")
    if old_string not in content:
        raise ValueError("old_string not found in file")

    new_content = content.replace(old_string, new_string, 1)
    file_path.write_text(new_content, encoding="utf-8")


def list_dir(path: str = ".") -> List[str]:
    dir_path = Path(path)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    entries = []
    for entry in sorted(dir_path.iterdir()):
        entries.append(f"{'[DIR] ' if entry.is_dir() else '[FILE]'} {entry.name}")
    return entries
