"""API key storage with file-based auth.json and env var fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Auth file location
AUTH_FILENAME = "auth.json"


def _get_auth_path() -> Path:
    """Get auth.json path from PROBID_HOME or default location."""
    default_dir = Path.home() / ".probid"
    agent_dir = os.environ.get("PROBID_HOME", str(default_dir))
    return Path(agent_dir) / AUTH_FILENAME


def _ensure_auth_dir() -> Path:
    """Ensure auth directory exists."""
    auth_path = _get_auth_path()
    auth_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    return auth_path


def _read_auth_file() -> dict[str, Any]:
    """Read auth.json file."""
    auth_path = _get_auth_path()
    if not auth_path.exists():
        return {}
    try:
        with open(auth_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed auth file at '{auth_path}'") from exc
    except OSError as exc:
        raise ValueError(f"Unable to read auth file at '{auth_path}'") from exc


def _write_auth_file(data: dict[str, Any]) -> None:
    """Write auth.json file."""
    auth_path = _ensure_auth_dir()
    previous_umask = os.umask(0o077)
    try:
        with open(auth_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.chmod(auth_path, 0o600)
    finally:
        os.umask(previous_umask)


def get_api_key(provider: str) -> str | None:
    """Get API key for a provider.
    
    Priority:
    1. Runtime override (check os.environ for provider-specific key)
    2. auth.json file storage
    3. Environment variable
    """
    provider = provider.strip().lower()
    
    # Provider-specific env var takes highest priority
    env_map = {
        "opencode": "OPENCODE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GEMINI_API_KEY",
        "google-vertex": "GOOGLE_CLOUD_API_KEY",
    }
    env_var = env_map.get(provider)
    if env_var and os.environ.get(env_var):
        return os.environ.get(env_var)
    
    # Also check generic OPENAI_API_KEY as fallback for opencode
    if provider == "opencode" and os.environ.get("OPENAI_API_KEY"):
        return os.environ.get("OPENAI_API_KEY")
    
    # Check auth.json file
    auth_data = _read_auth_file()
    if provider in auth_data:
        cred = auth_data[provider]
        if isinstance(cred, dict) and "key" in cred:
            return cred["key"]
        elif isinstance(cred, str):
            return cred
    
    # Fall back to env var
    if env_var:
        return os.environ.get(env_var)
    return None


def set_api_key(provider: str, key: str) -> None:
    """Set API key for a provider in auth.json."""
    provider = provider.strip().lower()
    auth_data = _read_auth_file()
    auth_data[provider] = {"type": "api_key", "key": key}
    _write_auth_file(auth_data)


def remove_api_key(provider: str) -> None:
    """Remove API key for a provider."""
    provider = provider.strip().lower()
    auth_data = _read_auth_file()
    if provider in auth_data:
        del auth_data[provider]
        _write_auth_file(auth_data)


def list_providers() -> list[str]:
    """List all providers with stored credentials."""
    auth_data = _read_auth_file()
    return list(auth_data.keys())


def has_api_key(provider: str) -> bool:
    """Check if API key exists for a provider."""
    return get_api_key(provider) is not None