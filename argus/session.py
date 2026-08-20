"""Argus session management."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class Session:
    def __init__(
        self,
        name: str,
        project_path: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ):
        self.name = name
        self.project_path = project_path or os.getcwd()
        self.messages = messages or []
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at

    def add_message(self, role: str, content: str, **kwargs) -> None:
        self.messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                **kwargs,
            }
        )
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "project_path": self.project_path,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        session = cls(
            name=data["name"],
            project_path=data.get("project_path"),
            messages=data.get("messages", []),
        )
        session.created_at = data.get("created_at", session.created_at)
        session.updated_at = data.get("updated_at", session.updated_at)
        return session


class SessionManager:
    def __init__(self, session_dir: str = "~/.agentcore/sessions"):
        self._session_dir = Path(session_dir).expanduser()
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._current: Optional[Session] = None

    def create(self, name: str, project_path: Optional[str] = None) -> Session:
        session = Session(name=name, project_path=project_path)
        self._current = session
        self._save(session)
        return session

    def load(self, name: str) -> Session:
        path = self._session_dir / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Session '{name}' not found")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        session = Session.from_dict(data)
        self._current = session
        return session

    def save_current(self) -> None:
        if self._current:
            self._save(self._current)

    def list_sessions(self) -> List[str]:
        sessions = []
        for path in self._session_dir.glob("*.json"):
            sessions.append(path.stem)
        return sorted(sessions)

    def delete(self, name: str) -> None:
        path = self._session_dir / f"{name}.json"
        if path.exists():
            path.unlink()
        if self._current and self._current.name == name:
            self._current = None

    @property
    def current(self) -> Optional[Session]:
        return self._current

    def _save(self, session: Session) -> None:
        path = self._session_dir / f"{session.name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2)
