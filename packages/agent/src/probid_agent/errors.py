"""Shared error types for probid agent-core."""

from __future__ import annotations


class PlanValidationError(ValueError):
    """Raised when a plan fails validation."""


class ProviderRegistryError(ValueError):
    """Raised when provider registry lookups fail."""
