"""Run the probid monorepo test suites with the correct PYTHONPATH."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHONPATH_PARTS = [
    str(ROOT / "packages" / "probing-agent" / "src"),
    str(ROOT / "packages" / "agent" / "src"),
    str(ROOT / "packages" / "ai" / "src"),
    str(ROOT / "packages" / "tui" / "src"),
    str(ROOT / "packages" / "web-ui" / "src"),
    str(ROOT / "packages" / "mom" / "src"),
    str(ROOT / "packages" / "pods" / "src"),
]


def main() -> int:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(PYTHONPATH_PARTS + ([existing] if existing else []))

    suites = [
        "packages/agent/tests",
        "packages/ai/tests",
        "packages/tui/tests",
        "packages/web-ui/tests",

        "packages/probing-agent/tests",
    ]

    for suite in suites:
        if not (ROOT / suite).is_dir():
            continue
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", suite, "-v"]
        code = subprocess.call(cmd, cwd=ROOT, env=env)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
