"""Recovery proposal entity representing diagnostic recommendations.

CRITICAL ARCHITECTURAL BOUNDARY:
AI PROPOSES != POLICY AUTHORIZES.
A RecoveryProposal is an advisory analysis and has ZERO authority to execute actions directly.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.types import RecoveryCaseId, RecoveryProposalId, ensure_utc_datetime
from app.domain.values.confidence import Confidence
from app.domain.values.decision import ProposalSource


class RecoveryStrategy(StrEnum):
    """Finite, allow-listed recovery strategies."""

    NO_ACTION = "NO_ACTION"
    WAIT = "WAIT"
    RETRY_SAME_METHOD = "RETRY_SAME_METHOD"
    REQUEST_ALTERNATE_METHOD = "REQUEST_ALTERNATE_METHOD"
    CREATE_PAYMENT_LINK = "CREATE_PAYMENT_LINK"
    CUSTOMER_NUDGE = "CUSTOMER_NUDGE"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"


@dataclass(frozen=True, slots=True)
class RecoveryProposal:
    """Advisory diagnostic proposal for recovering a failed payment.

    INVARIANT: Contains no executable payload or bypass mechanisms.
    """

    id: RecoveryProposalId
    recovery_case_id: RecoveryCaseId
    strategy: RecoveryStrategy
    rationale: str
    confidence: Confidence
    source: ProposalSource
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        if not isinstance(self.strategy, RecoveryStrategy):
            object.__setattr__(self, "strategy", RecoveryStrategy(str(self.strategy)))
        if not isinstance(self.source, ProposalSource):
            object.__setattr__(self, "source", ProposalSource(str(self.source)))
        if not isinstance(self.confidence, Confidence):
            raise TypeError("RecoveryProposal confidence must be a Confidence instance.")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("RecoveryProposal rationale must be a non-empty string.")
