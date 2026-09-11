"""Centralized exception hierarchy shared across the backend.

Consolidating exception types here avoids each module defining its own
ad-hoc error classes and keeps API-layer error translation predictable.
"""

from __future__ import annotations


class GovernedBackendError(Exception):
    """Base class for all deliberately raised backend errors."""


class ConfigurationError(GovernedBackendError):
    """Raised when required, environment-specific configuration is missing."""


class PolicyViolationError(GovernedBackendError):
    """Raised when a requested action fails policy evaluation."""


class AuthorizationError(GovernedBackendError):
    """Raised when a caller lacks the delegated authority for an action."""


class InvalidTransitionError(GovernedBackendError):
    """Raised when a task-state transition is not legal from its current state."""


class ApprovalRequiredError(GovernedBackendError):
    """Raised when an action is attempted without the required HITL approval."""


class SignatureVerificationError(GovernedBackendError):
    """Raised when a cryptographic signature fails verification."""


class SandboxInvocationError(GovernedBackendError):
    """Raised when the sandbox boundary fails to execute a mandate."""


class RetrievalGovernanceError(GovernedBackendError):
    """Raised when a RAG request violates tenant isolation or freshness rules."""


class RepositoryError(GovernedBackendError):
    """Raised when a persistence operation cannot be completed."""


class RateLimitExceededError(GovernedBackendError):
    """Raised when an outbound actuation attempt exceeds its rate limit."""
