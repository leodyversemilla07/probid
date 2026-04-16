"""Pod management helpers for probid."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Pod:
    """A compute pod for running AI models."""

    name: str
    model: str
    status: str = "stopped"  # stopped, starting, running, error
    endpoint: str | None = None
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class PodConfig:
    """Configuration for a pod."""

    name: str
    model: str
    gpu: str | None = None
    memory: str | None = None
    replicas: int = 1


class PodManager:
    """Manages compute pods for running models."""

    def __init__(self):
        self.pods: dict[str, Pod] = {}

    def create_pod(self, config: PodConfig) -> Pod:
        """Create a new pod."""
        pod = Pod(name=config.name, model=config.model)
        self.pods[config.name] = pod
        return pod

    def get_pod(self, name: str) -> Pod | None:
        """Get a pod by name."""
        return self.pods.get(name)

    def list_pods(self) -> list[Pod]:
        """List all pods."""
        return list(self.pods.values())

    def start_pod(self, name: str) -> bool:
        """Start a pod."""
        pod = self.pods.get(name)
        if pod is None:
            return False
        pod.status = "running"
        pod.endpoint = f"http://localhost:8080/{name}"
        return True

    def stop_pod(self, name: str) -> bool:
        """Stop a pod."""
        pod = self.pods.get(name)
        if pod is None:
            return False
        pod.status = "stopped"
        pod.endpoint = None
        return True

    def delete_pod(self, name: str) -> bool:
        """Delete a pod."""
        if name in self.pods:
            del self.pods[name]
            return True
        return False


# Global manager instance
_manager: PodManager | None = None


def get_manager() -> PodManager:
    """Get the global pod manager instance."""
    global _manager
    if _manager is None:
        _manager = PodManager()
    return _manager


__all__ = [
    "Pod",
    "PodConfig",
    "PodManager",
    "get_manager",
]
