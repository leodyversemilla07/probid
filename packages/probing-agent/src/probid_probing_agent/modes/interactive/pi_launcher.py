"""Launch real pi TUI for full parity when available."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _candidate_workspace_pi() -> list[list[str]]:
    """Return possible commands for local pi-mono checkout."""
    home = Path.home()
    cli_js = home / "workspace" / "pi-mono" / "packages" / "coding-agent" / "dist" / "cli.js"
    if cli_js.exists():
        return [["node", str(cli_js)]]
    return []


def maybe_launch_pi_tui() -> bool:
    """Launch pi TUI if available and running in a real interactive terminal.

    Returns True if control was handed to pi (process finished), False if caller
    should use internal fallback TUI.
    """
    if os.environ.get("PROBID_FORCE_INTERNAL_TUI", "0").strip() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return False

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False

    commands: list[list[str]] = []

    pi_bin = shutil.which("pi")
    if pi_bin:
        commands.append([pi_bin])

    commands.extend(_candidate_workspace_pi())

    for cmd in commands:
        try:
            subprocess.call(cmd)
            return True
        except Exception:
            continue

    return False
