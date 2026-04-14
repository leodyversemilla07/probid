"""Session logging for probid agent."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class AgentSessionLogger:
    def __init__(self, path: Path | None = None):
        default_path = Path.home() / ".probid" / "agent-sessions.jsonl"
        self.path = path or default_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_turn(self, user_input: str, result: dict[str, Any]) -> str:
        turn_id = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        record = {
            "turn_id": turn_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
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
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("turn_id") == turn_id:
                    return row
        return None
