"""Pi-style TUI for probid interactive mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class Message:
    """A chat message."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: str | None = None


@dataclass
class ToolCall:
    """A tool call in the conversation."""

    name: str
    args: dict[str, Any]
    result: str | None = None


@dataclass
class Session:
    """Session state for TUI."""

    id: str = "session-1"
    model: str = "deterministic"
    provider: str = "deterministic"
    messages: list[Message] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)


class Sidebar:
    """Pi-style sidebar."""

    def __init__(self, session: Session):
        self.session = session

    def render(self) -> Panel:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="cyan")
        table.add_column(style="white")

        # Model
        table.add_row("model:", f"[bold]{self.session.model}[/bold]")

        # Provider
        table.add_row("provider:", self.session.provider)

        # Session
        table.add_row("session:", self.session.id)

        # Tools enabled
        table.add_row("tools:", "✓ enabled")

        # Stats
        table.add_row("messages:", str(len(self.session.messages)))

        return Panel(
            table,
            title="[bold cyan]probid[/]",
            border_style="cyan",
            padding=(1, 1),
            width=20,
        )


class ChatView:
    """Chat message view."""

    def __init__(self, session: Session):
        self.session = session

    def render(self) -> Group:
        items = []

        for msg in self.session.messages:
            if msg.role == "user":
                # User messages on right (blue)
                items.append(
                    Panel(
                        msg.content,
                        border_style="blue",
                        padding=(0, 1),
                        width=60,
                    )
                )
            elif msg.role == "assistant":
                # Assistant messages on left
                items.append(
                    Panel(
                        msg.content,
                        border_style="green",
                        padding=(0, 1),
                        width=60,
                    )
                )

        return Group(*items)


class InputBar:
    """Bottom input bar."""

    def __init__(self, prompt: str = "Ask anything..."):
        self.prompt = prompt

    def render(self) -> Panel:
        return Panel(
            f"[dim]>[/dim] {self.prompt}",
            border_style="white",
            padding=(0, 1),
        )


class ProbidTUI:
    """Pi-style TUI for probid."""

    def __init__(self, session: Session | None = None):
        self.session = session or Session()
        self.sidebar = Sidebar(self.session)
        self.chat = ChatView(self.session)
        self.input_bar = InputBar()

    def add_user_message(self, content: str) -> None:
        self.session.messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        self.session.messages.append(Message(role="assistant", content=content))

    def render(self) -> None:
        """Render the full TUI."""
        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(name="sidebar", size=20),
            Layout(name="main"),
        )
        layout["sidebar"].update(self.sidebar.render())
        layout["main"].update(
            Group(
                self.chat.render(),
                self.input_bar.render(),
            )
        )

        console.print(layout)

    def render_simple(self) -> None:
        """Simple render without complex layout."""
        # Sidebar
        console.print(self.sidebar.render())

        # Chat
        console.print(self.chat.render())

        # Input
        console.print(self.input_bar.render())


def create_tui(session: Session | None = None) -> ProbidTUI:
    """Create a new TUI instance."""
    return ProbidTUI(session)


if __name__ == "__main__":
    # Demo
    session = Session(model="gpt-4", provider="ai")
    session.messages = [
        Message(role="user", content="probe laptops for DICT"),
        Message(
            role="assistant",
            content="I'll probe PhilGEPS for laptop procurement data for DICT...",
        ),
    ]

    tui = ProbidTUI(session)
    tui.render_simple()
