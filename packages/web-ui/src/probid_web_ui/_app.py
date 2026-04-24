"""Web UI application placeholder for probid."""

from collections.abc import Callable


class ProbidWebApp:
    """Minimal web application placeholder.

    This is a placeholder for future web-based UI components.
    Currently not implemented - requires frontend framework decision
    (e.g., React, Vue, or plain HTML/JS).
    """

    def __init__(self):
        self.routes: dict[str, Callable] = {}

    def route(self, path: str):
        """Decorator to register a route handler."""

        def decorator(func: Callable):
            self.routes[path] = func
            return func

        return decorator

    def run(self, host: str = "localhost", port: int = 8080):
        """Run the web application."""
        raise NotImplementedError("Web UI not yet implemented")
