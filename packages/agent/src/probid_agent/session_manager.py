"""Generic JSONL session persistence manager for probid agent runtimes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class JsonlSessionManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self) -> tuple[str, Path]:
        session_id = uuid4().hex
        path = self.base_dir / f"{session_id}.jsonl"
        header = {
            "type": "session_start",
            "session_id": session_id,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        path.write_text(json.dumps(header, ensure_ascii=False) + "\n", encoding="utf-8")
        return session_id, path

    def list_sessions(self) -> list[dict[str, Any]]:
        sessions: list[dict[str, Any]] = []
        for path in sorted(self.base_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            sessions.append(
                {
                    "session_id": path.stem,
                    "path": path,
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime, UTC)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            )
        return sessions

    def continue_recent(self) -> tuple[str, Path] | None:
        sessions = self.list_sessions()
        if not sessions:
            return None
        newest = sessions[0]
        return newest["session_id"], newest["path"]

    def append_turn(self, session_id: str, turn: dict[str, Any]) -> Path:
        path = self.base_dir / f"{session_id}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(turn, ensure_ascii=False) + "\n")
        return path

    def read_session(self, session_id: str) -> list[dict[str, Any]]:
        path = self.base_dir / f"{session_id}.jsonl"
        return self.read_session_file(path)

    def read_session_file(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Malformed JSONL in session file '{path}' at line {line_no}") from exc
                rows.append(row)
        return rows
