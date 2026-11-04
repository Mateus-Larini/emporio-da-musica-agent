"""Persistência do histórico de conversa em arquivos JSON por sessão.

Cada sessão (ex.: um número de WhatsApp) vira sessions/<id>.json com as mensagens
serializadas pelo LangChain. Simples, inspecionável e suficiente para retomar uma
conversa entre execuções da CLI ou da UI.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict

from emporio_agent.config import SESSIONS_DIR

_SAFE_ID = re.compile(r"[^a-zA-Z0-9_.-]+")


class SessionStore:
    def __init__(self, directory: Path = SESSIONS_DIR):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        safe = _SAFE_ID.sub("_", session_id).strip("_") or "default"
        return self.directory / f"{safe}.json"

    def load(self, session_id: str) -> list[BaseMessage]:
        path = self._path(session_id)
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return messages_from_dict(data["messages"])

    def save(self, session_id: str, messages: list[BaseMessage]) -> Path:
        path = self._path(session_id)
        payload = {
            "session_id": session_id,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "messages": messages_to_dict(messages),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        return path

    def append(self, session_id: str, new_messages: list[BaseMessage]) -> list[BaseMessage]:
        history = self.load(session_id) + list(new_messages)
        self.save(session_id, history)
        return history

    def delete(self, session_id: str) -> None:
        self._path(session_id).unlink(missing_ok=True)

    def list_sessions(self) -> list[str]:
        return sorted(p.stem for p in self.directory.glob("*.json"))
