"""Generic JSONL turn logger for agent runtimes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JsonlTurnLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_turn(self, user_input: str, result: dict[str, Any], turn_id: str | None = None) -> str:
        turn_id = turn_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        record = {
            "turn_id": turn_id,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "session_id": result.get("session_id"),
            "user_input": user_input,
            "intent": result.get("intent"),
            "query": result.get("query"),
            "tool_trace": result.get("tool_trace", []),
            "finding_count": len(result.get("findings", [])),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return turn_id

    def get_record(self, turn_id: str) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        with self.path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Malformed JSONL in turn log '{self.path}' at line {line_no}") from exc
                if row.get("turn_id") == turn_id:
                    return row
        return None
