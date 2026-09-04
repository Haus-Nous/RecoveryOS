"""Policy authorization decisions and proposal origin sources."""

from enum import StrEnum


class PolicyDecision(StrEnum):
    """Deterministic policy authorization decisions.

    INVARIANT:
    ALLOW  -> Action is permitted for automated infrastructure execution.
    REVIEW -> Action requires human operator review before execution.
    DENY   -> Action is prohibited and cannot be executed.
    """

    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    DENY = "DENY"


class ProposalSource(StrEnum):
    """Source origin of a recovery strategy proposal."""

    RULE = "RULE"
    MODEL = "MODEL"
    AI = "AI"
    OPERATOR = "OPERATOR"
