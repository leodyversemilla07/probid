"""Configuration helpers for probid probing agent."""

from __future__ import annotations

from pathlib import Path

VERSION = "0.1.0"
APP_NAME = "probid"


def get_agent_dir() -> Path:
    path = Path.home() / ".probid"
    path.mkdir(parents=True, exist_ok=True)
    return path
