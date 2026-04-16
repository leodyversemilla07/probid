"""Types for future probing-agent extensions."""

from __future__ import annotations

from typing import TypedDict


class ExtensionInfo(TypedDict, total=False):
    name: str
    description: str
