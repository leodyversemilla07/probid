"""Non-blocking pi-style interactive TUI mode for probid."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable

from probid_tui import Editor, OverlayOptions, ProcessTerminal, TUI, parse_key, truncate_to_width, visible_width
from probid_tui.core.component import Component

SLASH_COMMANDS = (
    ("/help", "Show help"),
    ("/json", "Toggle JSON mode"),
    ("/why", "Toggle caveats view"),
    ("/prompt", "Show system prompt"),
    ("/tools", "Show CLI-parity tools"),
    ("/mode", "Show mode/session state"),
    ("/steer", "Queue steering message"),
    ("/followup", "Queue follow-up message"),
    ("/reset", "Start a new session"),
    ("/clear", "Clear transcript"),
    ("/exit", "Quit"),
)


def _resolve_app_version() -> str:
    try:
        return version("probid")
    except PackageNotFoundError:
        return "0.1.0"


APP_VERSION = _resolve_app_version()

# pi-mono dark-style ANSI palette
ACCENT = "38;2;138;190;183"
BORDER = "38;2;95;135;255"
MUTED = "38;2;128;128;128"
DIM = "38;2;102;102;102"
SUCCESS = "38;2;181;189;104"
WARNING = "38;2;255;255;0"
ERROR = "38;2;204;102;102"
CYAN = "38;2;0;215;255"


def _paint(text: str, *codes: str) -> str:
    if not text or not codes:
        return text
    return f"\x1b[{';'.join(codes)}m{text}\x1b[0m"


class HeaderComponent(Component):
    def render(self, width: int) -> list[str]:
        title = truncate_to_width(f"probid v{APP_VERSION}", width, pad=True)
        subtitle = truncate_to_width(
            "Probid can explain its features and docs. Ask how to use or extend probid.",
            width,
            pad=True,
        )
        return [_paint(title, "1", ACCENT), _paint(subtitle, MUTED), ""]


class SlashCommandDropdownComponent(Component):
    def __init__(self, editor: Editor, max_visible: int = 6):
        self.editor = editor
        self.max_visible = max(1, max_visible)
        self._query = ""
        self._matches: list[tuple[str, str]] = []
        self._selected_index = 0

    def _update(self) -> None:
        text = self.editor.get_value().lstrip()
        if not text.startswith("/"):
            self._query = ""
            self._matches = []
            self._selected_index = 0
            return

        # Keep dropdown open only while editing the command token itself.
        if any(ch.isspace() for ch in text[1:]):
            self._query = ""
            self._matches = []
            self._selected_index = 0
            return

        token = text.split(maxsplit=1)[0].lower()
        if token == "/":
            matches = list(SLASH_COMMANDS)
        else:
            matches = [entry for entry in SLASH_COMMANDS if entry[0].startswith(token)]

        if token != self._query:
            self._selected_index = 0
        self._query = token
        self._matches = matches
        if self._matches:
            self._selected_index = min(self._selected_index, len(self._matches) - 1)
        else:
            self._selected_index = 0

    def is_open(self) -> bool:
        self._update()
        return bool(self._query)

    def move_selection(self, delta: int) -> bool:
        self._update()
        if not self._matches:
            return False
        self._selected_index = (self._selected_index + delta) % len(self._matches)
        return True

    def apply_selected(self) -> bool:
        self._update()
        if not self._matches:
            return False

        selected = self._matches[self._selected_index][0]
        self.editor.set_value(f"{selected} ")
        self._update()
        return True

    def _pad_visible(self, text: str, width: int) -> str:
        return text + (" " * max(0, width - visible_width(text)))

    def render(self, width: int) -> list[str]:
        self._update()
        if not self._query:
            return []

        width = max(30, width)
        divider = _paint("─" * width, BORDER)

        if not self._matches:
            no_match = self._pad_visible(_paint("No matching commands", WARNING), width)
            return [divider, no_match, ""]

        start = max(0, self._selected_index - (self.max_visible // 2))
        end = min(len(self._matches), start + self.max_visible)
        start = max(0, end - self.max_visible)
        visible_matches = self._matches[start:end]
        cmd_col = min(24, max(len(cmd) for cmd, _desc in visible_matches) + 2)

        lines = [divider]
        for i in range(start, end):
            selected = i == self._selected_index
            cmd, desc = self._matches[i]
            prefix_plain = "❯ " if selected else "  "
            cmd_plain = truncate_to_width(cmd, cmd_col, pad=True)
            desc_width = max(0, width - len(prefix_plain) - cmd_col - 1)
            desc_plain = truncate_to_width(desc, desc_width, pad=False)

            if selected:
                row = (
                    _paint(prefix_plain, ACCENT)
                    + _paint(cmd_plain, "1", ACCENT)
                    + " "
                    + _paint(desc_plain, CYAN)
                )
            else:
                row = prefix_plain + _paint(cmd_plain, MUTED) + " " + _paint(desc_plain, DIM)
            lines.append(self._pad_visible(row, width))

        count = self._pad_visible(_paint(f"({self._selected_index + 1}/{len(self._matches)})", DIM), width)
        lines.extend([count, ""])
        return lines


class TranscriptComponent(Component):
    def __init__(self, max_lines: int = 120):
        self._lines: list[str] = []
        self.max_lines = max_lines

    def clear(self) -> None:
        self._lines.clear()

    def append(self, line: str) -> None:
        self._lines.append(line)
        if len(self._lines) > self.max_lines:
            self._lines = self._lines[-self.max_lines :]

    def extend(self, lines: list[str]) -> None:
        for line in lines:
            self.append(line)

    def render(self, width: int) -> list[str]:
        width = max(20, width)
        if not self._lines:
            return ["".ljust(width)]
        return [self._style_line(line, width) for line in self._lines]

    def _style_line(self, line: str, width: int) -> str:
        plain = truncate_to_width(line, width, pad=True)
        if line.startswith("harness>"):
            return _paint(plain, ACCENT)
        if line.startswith("Error:"):
            return _paint(plain, ERROR)
        if line.startswith("Caveat:") or line.startswith("! Caveat:"):
            return _paint(plain, WARNING)
        if line.startswith("Intent:") or line.startswith("Commands:"):
            return _paint(plain, CYAN)
        if line.startswith("Next actions:"):
            return _paint(plain, ACCENT)
        if line.startswith("Busy:"):
            return _paint(plain, WARNING)
        return plain


class FooterComponent(Component):
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.json_mode = False
        self.why_mode = False
        self._git_segment_cache = ""
        self._git_segment_checked_at = 0.0

    def render(self, width: int) -> list[str]:
        width = max(20, width)
        cwd_line = f"{self._display_cwd()} {self._git_segment()}".rstrip()
        cwd = truncate_to_width(cwd_line, width, pad=True)

        left = f"json={self.json_mode} why={self.why_mode}"
        right = f"({self.provider}) {self.model}"

        lw = visible_width(left)
        rw = visible_width(right)
        spacer = max(1, width - lw - rw)
        row = truncate_to_width(left + (" " * spacer) + right, width, pad=True)

        return ["", _paint(cwd, DIM), _paint(row, MUTED)]

    def _display_cwd(self) -> str:
        cwd = Path.cwd()
        home = Path.home()
        try:
            rel = cwd.relative_to(home)
        except ValueError:
            return str(cwd)
        rel_text = str(rel)
        return "~" if rel_text == "." else f"~/{rel_text}"

    def _run_git(self, args: list[str]) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(Path.cwd()), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=0.15,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def _git_segment(self) -> str:
        now = time.monotonic()
        if now - self._git_segment_checked_at < 1.0:
            return self._git_segment_cache

        self._git_segment_checked_at = now
        branch = self._run_git(["symbolic-ref", "--short", "-q", "HEAD"])
        if not branch:
            branch = self._run_git(["rev-parse", "--short", "HEAD"])
        if not branch:
            self._git_segment_cache = ""
            return self._git_segment_cache

        status = self._run_git(["status", "--porcelain"]) or ""
        lines = [line for line in status.splitlines() if line]
        has_changes = any(not line.startswith("??") for line in lines)
        has_untracked = any(line.startswith("??") for line in lines)

        suffix = ""
        if has_changes:
            suffix += "*"
        if has_untracked:
            suffix += "%"

        self._git_segment_cache = f"[⎇ {branch}{suffix}]"
        return self._git_segment_cache


class PendingComponent(Component):
    def __init__(self):
        self.status = "idle"
        self.lines: list[str] = []

    def set_status(self, status: str) -> None:
        self.status = status

    def push(self, line: str) -> None:
        self.lines.append(line)
        if len(self.lines) > 4:
            self.lines = self.lines[-4:]

    def clear(self) -> None:
        self.status = "idle"
        self.lines = []

    def render(self, width: int) -> list[str]:
        width = max(24, width)
        inner = max(10, width - 4)
        top = "┌" + ("─" * (width - 2)) + "┐"
        title = "│ " + truncate_to_width(f"Pending: {self.status}", inner, pad=True) + " │"
        body = ["│ " + truncate_to_width(line, inner, pad=True) + " │" for line in self.lines]
        while len(body) < 3:
            body.append("│ " + (" " * inner) + " │")
        bottom = "└" + ("─" * (width - 2)) + "┘"
        status_color = SUCCESS if self.status in {"idle", "turn complete"} else WARNING
        return [
            _paint(top, BORDER),
            _paint(title, status_color),
            *[_paint(line, DIM) for line in body[:3]],
            _paint(bottom, BORDER),
        ]


class InteractiveController:
    def __init__(
        self,
        runtime: Any,
        loop: asyncio.AbstractEventLoop,
        editor: Editor,
        transcript: TranscriptComponent,
        footer: FooterComponent,
        pending: PendingComponent,
        pending_overlay_handle: Any,
        tui: TUI,
        stop: Callable[[str | None], None],
    ):
        self.runtime = runtime
        self.loop = loop
        self.editor = editor
        self.transcript = transcript
        self.footer = footer
        self.pending = pending
        self.pending_overlay_handle = pending_overlay_handle
        self.tui = tui
        self.stop = stop

        self._busy = False
        self._unsubscribe = self.runtime.session.subscribe(self._on_session_event)

    def close(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def on_submit(self, text: str) -> None:
        text = text.strip()
        if not text:
            self.tui.request_render()
            return

        cmd = text.lower()
        if self._handle_command(cmd, text):
            self.tui.request_render(force=True)
            return

        if self._busy:
            self.transcript.append("Busy: wait for current turn to finish.")
            self.tui.request_render(force=True)
            return

        self._busy = True
        self.pending.clear()
        self.pending.set_status("running")
        self.pending.push("Planning and executing tools...")
        self.pending_overlay_handle.set_hidden(False)

        self.transcript.append(f"harness> {text}")
        self.loop.create_task(self._run_turn(text))
        self.tui.request_render(force=True)

    async def _run_turn(self, text: str) -> None:
        try:
            result = await self.loop.run_in_executor(None, self.runtime.handle_input, text)
            if self.footer.json_mode and isinstance(result, dict):
                self.transcript.append(json.dumps(result, indent=2, ensure_ascii=False))
            elif isinstance(result, dict):
                self.transcript.extend(_format_result(result))
                if self.footer.why_mode and result.get("caveats"):
                    for caveat in result["caveats"][:5]:
                        self.transcript.append(f"! Caveat: {caveat}")
            else:
                self.transcript.append(str(result))
        except Exception as exc:  # pragma: no cover - defensive
            self.transcript.append(f"Error: {exc}")
        finally:
            self._busy = False
            self.pending.set_status("idle")
            self.pending.push("Done")
            self.pending_overlay_handle.set_hidden(True)
            self.tui.request_render(force=True)

    def _on_session_event(self, event: dict[str, Any]) -> None:
        self.loop.call_soon_threadsafe(self._apply_session_event, event)

    def _apply_session_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "turn_start":
            turn_id = event.get("turn_id", "")
            self.pending.set_status("turn started")
            if turn_id:
                self.pending.push(f"turn={turn_id}")
        elif event_type == "tool_execution_start":
            tool = event.get("tool", "tool")
            self.pending.push(f"tool start: {tool}")
        elif event_type == "tool_execution_end":
            tool = event.get("tool", "tool")
            status = event.get("status", "ok")
            self.pending.push(f"tool end: {tool} [{status}]")
        elif event_type == "turn_end":
            trace = event.get("tool_trace") or []
            self.pending.set_status("turn complete")
            self.pending.push(f"trace items: {len(trace)}")

        self.tui.request_render()

    def _handle_command(self, cmd: str, raw: str) -> bool:
        if cmd in {"exit", "quit", "q", "/exit", "/quit"}:
            self.stop("Session ended")
            return True

        if cmd == "/help":
            self.transcript.extend(
                [
                    "Commands:",
                    "  /help                 show this help",
                    "  /json                 toggle json mode",
                    "  /why                  toggle caveats view",
                    "  /prompt               show system prompt",
                    "  /tools                show CLI-parity tools",
                    "  /mode                 show mode/session state",
                    "  /steer <text>         queue steering message",
                    "  /followup <text>      queue follow-up message",
                    "  /reset                start a new session",
                    "  /clear                clear transcript",
                    "  /exit                 quit",
                ]
            )
            return True

        if cmd == "/json":
            self.footer.json_mode = not self.footer.json_mode
            self.transcript.append(f"json_mode={self.footer.json_mode}")
            return True

        if cmd == "/why":
            self.footer.why_mode = not self.footer.why_mode
            self.transcript.append(f"why_mode={self.footer.why_mode}")
            return True

        if cmd == "/prompt":
            self.transcript.append("System prompt:")
            self.transcript.append(self.runtime.system_prompt)
            return True

        if cmd == "/tools":
            self.transcript.append("CLI-parity tools:")
            for tool_cmd in self.runtime.available_tools():
                self.transcript.append(f"  - {tool_cmd}")
            return True

        if cmd == "/mode":
            state = self.runtime.session.snapshot_state()
            self.transcript.append(
                "mode=interactive "
                f"json_mode={self.footer.json_mode} why_mode={self.footer.why_mode} cache_only={self.runtime.default_cache_only} "
                f"session_id={state['session_id']} queued_steering={state['queued_steering']} "
                f"queued_follow_up={state['queued_follow_up']}"
            )
            return True

        if cmd.startswith("/steer "):
            self.runtime.session.steer(raw[len("/steer ") :])
            self.transcript.append("Queued steering message.")
            return True

        if cmd.startswith("/followup "):
            self.runtime.session.follow_up(raw[len("/followup ") :])
            self.transcript.append("Queued follow-up message.")
            return True

        if cmd == "/clear":
            self.transcript.clear()
            return True

        if cmd == "/reset":
            self.runtime.new_session()
            self.transcript.append("Started a new harness session.")
            return True

        return False


def _format_result(result: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    intent = result.get("intent", "unknown")
    query = result.get("query", "")
    lines.append(f"Intent: {intent} | Query: {query}")

    evidence = result.get("evidence", [])
    if evidence:
        lines.append("Evidence: " + " | ".join(str(e) for e in evidence[:4]))

    findings = result.get("findings", [])
    for idx, finding in enumerate(findings[:8], 1):
        code = finding.get("code", "?") if isinstance(finding, dict) else "?"
        summary = finding.get("summary", str(finding)) if isinstance(finding, dict) else str(finding)
        lines.append(f"{idx}. [{code}] {summary}")

    caveats = result.get("caveats", [])
    for caveat in caveats[:3]:
        lines.append(f"Caveat: {caveat}")

    actions = result.get("next_actions", [])
    if actions:
        lines.append("Next actions:")
        for action in actions[:5]:
            lines.append(f"  - {action}")

    turn_id = result.get("turn_id")
    if turn_id:
        lines.append(f"Turn ID: {turn_id}")

    return lines


def run_interactive(
    runtime: Any,
    model: str = "deterministic",
    provider: str = "deterministic",
) -> None:
    """Run non-blocking interactive TUI with differential rendering."""

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        # Test/non-tty fallback keeps existing REPL compatibility and output contract.
        from probid_probing_agent.modes.interactive.repl import run_agent_repl

        run_agent_repl(runtime)
        return

    terminal = ProcessTerminal()
    tui = TUI(terminal)

    header = HeaderComponent()
    transcript = TranscriptComponent()
    footer = FooterComponent(provider=provider, model=model)
    pending = PendingComponent()
    editor = Editor(max_visible_lines=5)
    slash_dropdown = SlashCommandDropdownComponent(editor)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    controller_ref: dict[str, InteractiveController | None] = {"value": None}

    def stop(message: str | None = None) -> None:
        if message:
            transcript.append(message)
        if controller_ref["value"] is not None:
            controller_ref["value"].close()
        tui.stop()
        loop.stop()

    pending_overlay = tui.show_overlay(
        pending,
        OverlayOptions(
            width="45%",
            max_height=6,
            anchor="top-right",
            margin=1,
        ),
    )
    pending_overlay.set_hidden(True)

    controller = InteractiveController(runtime, loop, editor, transcript, footer, pending, pending_overlay, tui, stop)
    controller_ref["value"] = controller
    editor.set_on_submit(controller.on_submit)

    original_editor_handle_input = editor.handle_input

    def editor_handle_input_with_slash_dropdown(data: bytes) -> bool:
        key = parse_key(data)
        if slash_dropdown.is_open():
            if key in {"up", "ctrl+p"}:
                if slash_dropdown.move_selection(-1):
                    tui.request_render(force=True)
                    return True
            if key in {"down", "ctrl+n"}:
                if slash_dropdown.move_selection(1):
                    tui.request_render(force=True)
                    return True
            if key in {"tab", "enter"}:
                if slash_dropdown.apply_selected():
                    tui.request_render(force=True)
                    return True
        consumed = original_editor_handle_input(data)
        if consumed:
            tui.request_render()
        return consumed

    editor.handle_input = editor_handle_input_with_slash_dropdown  # type: ignore[assignment]

    def on_unhandled_input(data: bytes) -> None:
        key = parse_key(data)
        if key in {"ctrl+c", "escape"}:
            stop("Session ended")

    tui.set_input_handler(on_unhandled_input)

    tui.add_child(header)
    tui.add_child(transcript)
    tui.add_child(editor)
    tui.add_child(slash_dropdown)
    tui.add_child(footer)
    tui.set_focus(editor)

    try:
        tui.start()
        loop.run_forever()
    finally:
        try:
            if controller_ref["value"] is not None:
                controller_ref["value"].close()
            tui.stop()
        finally:
            loop.close()
