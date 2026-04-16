"""ANSI-aware width, truncation and wrapping utilities."""

from __future__ import annotations

import re

try:
    import grapheme  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    grapheme = None

try:
    import wcwidth  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    wcwidth = None

ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\\\))")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def _graphemes(text: str):
    if grapheme is not None:
        return grapheme.graphemes(text)
    return list(text)


def _wcw(ch: str) -> int:
    if wcwidth is None:
        return 1
    return max(0, wcwidth.wcwidth(ch))


def visible_width(text: str) -> int:
    plain = strip_ansi(text)
    return sum(_wcw(ch) for ch in _graphemes(plain))


def truncate_to_width(text: str, max_width: int, pad: bool = False) -> str:
    plain = strip_ansi(text)
    result = ""
    width = 0
    for g in _graphemes(plain):
        gw = _wcw(g)
        if width + gw > max_width:
            break
        result += g
        width += gw
    if pad and width < max_width:
        result += " " * (max_width - width)
    return result


def wrap_text_with_ansi(text: str, width: int) -> list[str]:
    if width <= 0:
        return [""]

    lines: list[str] = []
    current = ""
    current_w = 0

    for token in re.split(r"(\s+)", text):
        if not token:
            continue
        token_w = visible_width(token)

        if current and current_w + token_w > width:
            lines.append(current)
            current = ""
            current_w = 0

        if token_w > width and not token.isspace():
            # hard-wrap very long token
            chunk = ""
            chunk_w = 0
            for g in _graphemes(token):
                gw = _wcw(g)
                if chunk and chunk_w + gw > width:
                    if current:
                        lines.append(current)
                        current = ""
                        current_w = 0
                    lines.append(chunk)
                    chunk = ""
                    chunk_w = 0
                chunk += g
                chunk_w += gw
            if chunk:
                current = chunk
                current_w = chunk_w
            continue

        current += token
        current_w += token_w

    if current:
        lines.append(current)

    return lines or [""]


def truncate_to_width_with_ellipsis(text: str, max_width: int, ellipsis: str = "...") -> str:
    """pi-tui compatible truncation helper with configurable ellipsis."""
    if max_width <= 0:
        return ""
    plain = strip_ansi(text)
    if visible_width(plain) <= max_width:
        return truncate_to_width(plain, max_width, pad=False)
    ell = ellipsis or ""
    ell_w = visible_width(ell)
    if ell_w >= max_width:
        return truncate_to_width(ell, max_width, pad=False)
    return truncate_to_width(plain, max_width - ell_w, pad=False) + ell


# pi-tui style aliases
visibleWidth = visible_width
truncateToWidth = truncate_to_width_with_ellipsis
wrapTextWithAnsi = wrap_text_with_ansi
