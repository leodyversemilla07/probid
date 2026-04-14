"""Simple local auth store for agent REPL login/logout commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def normalize_provider_name(provider: str) -> str:
    key = " ".join(provider.strip().lower().replace("_", "-").split())
    aliases = {
        "copilot": "github-copilot",
        "github copilot": "github-copilot",
        "github-copilot": "github-copilot",
        "github_copilot": "github-copilot",
    }
    return aliases.get(key, key.replace(" ", "-"))


class AgentAuthStore:
    def __init__(self, path: Path | None = None):
        env_path = os.environ.get("PROBID_AUTH_FILE", "").strip()
        default_path = Path.home() / ".probid" / "auth.json"
        self.path = path or (Path(env_path) if env_path else default_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"providers": {}}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"providers": {}}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def login(self, provider: str, token: str) -> str:
        normalized_provider = normalize_provider_name(provider)
        payload = self._read()
        payload.setdefault("providers", {})[normalized_provider] = {"token": token.strip()}
        self._write(payload)
        return normalized_provider

    def logout(self, provider: str | None = None) -> tuple[bool, str | None]:
        payload = self._read()
        providers = payload.setdefault("providers", {})
        if provider is None:
            had_any = bool(providers)
            payload["providers"] = {}
            self._write(payload)
            return had_any, None

        normalized_provider = normalize_provider_name(provider)
        if normalized_provider in providers:
            del providers[normalized_provider]
            self._write(payload)
            return True, normalized_provider
        return False, normalized_provider

    def list_logged_in_providers(self) -> list[str]:
        payload = self._read()
        providers = payload.get("providers", {})
        return sorted(providers.keys())
