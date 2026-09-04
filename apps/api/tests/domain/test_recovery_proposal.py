"""Tests for RecoveryProposal and strict separation from authorization."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.entities.recovery_action import RecoveryAction, RecoveryActionState
from app.domain.entities.recovery_proposal import RecoveryProposal, RecoveryStrategy
from app.domain.exceptions import InvalidConfidenceError, UnauthorizedActionTransitionError
from app.domain.types import RecoveryActionId, RecoveryCaseId, RecoveryProposalId
from app.domain.values.confidence import Confidence
from app.domain.values.decision import ProposalSource

NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)


def test_proposal_instantiation() -> None:
    proposal = RecoveryProposal(
        id=RecoveryProposalId("prop_123"),
        recovery_case_id=RecoveryCaseId("rc_123"),
        strategy=RecoveryStrategy.RETRY_SAME_METHOD,
        rationale="Transient network error detected; issuer uptime restored.",
        confidence=Confidence.from_percentage_int(90),
        source=ProposalSource.AI,
        created_at=NOW,
    )
    assert proposal.strategy == RecoveryStrategy.RETRY_SAME_METHOD
    assert proposal.confidence.basis_points == 9000
    assert proposal.confidence.as_fraction() == Decimal("0.9")
    assert proposal.source == ProposalSource.AI


def test_proposal_confidence_bounds() -> None:
    c1 = Confidence(0)
    assert c1.as_percentage_str() == "0.00%"

    c2 = Confidence(10000)
    assert c2.as_percentage_str() == "100.00%"

    with pytest.raises(InvalidConfidenceError):
        Confidence(-1)

    with pytest.raises(InvalidConfidenceError):
        Confidence(10001)

    with pytest.raises(InvalidConfidenceError):
        Confidence(95.5)  # type: ignore


def test_proposal_does_not_authorize_action_execution() -> None:
    """CRITICAL ACCEPTANCE TEST: Proposal cannot execute action without separate authorization."""
    proposal = RecoveryProposal(
        id=RecoveryProposalId("prop_123"),
        recovery_case_id=RecoveryCaseId("rc_123"),
        strategy=RecoveryStrategy.CREATE_PAYMENT_LINK,
        rationale="High confidence AI recommendation",
        confidence=Confidence(9900),
        source=ProposalSource.AI,
        created_at=NOW,
    )

    action = RecoveryAction(
        id=RecoveryActionId("act_123"),
        recovery_case_id=proposal.recovery_case_id,
        strategy=proposal.strategy,
        state=RecoveryActionState.PROPOSED,
        created_at=NOW,
        updated_at=NOW,
    )

    # Merely having a proposal does NOT allow execution
    assert not action.is_authorized
    with pytest.raises(UnauthorizedActionTransitionError):
        action.transition_to(RecoveryActionState.EXECUTING, NOW)
