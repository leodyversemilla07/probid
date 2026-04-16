"""Persistent session management for the probid probing agent harness."""

from __future__ import annotations

from pathlib import Path

from probid_agent.session_manager import JsonlSessionManager


class ProbidSessionManager(JsonlSessionManager):
    def __init__(self, base_dir: Path | None = None):
        super().__init__(base_dir or (Path.home() / ".probid" / "sessions"))
