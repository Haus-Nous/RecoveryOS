"""Bi-directional mapper for RecoveryProposal domain entity and RecoveryProposalModel."""

from datetime import UTC

from app.application.exceptions import DataCorruptionError
from app.domain.entities.recovery_proposal import RecoveryProposal, RecoveryStrategy
from app.domain.types import RecoveryCaseId, RecoveryProposalId
from app.domain.values.confidence import Confidence
from app.domain.values.decision import ProposalSource
from app.infrastructure.persistence.models.recovery_proposal import RecoveryProposalModel


class RecoveryProposalMapper:
    """Explicit mapper between RecoveryProposal domain and RecoveryProposalModel ORM."""

    @staticmethod
    def to_domain(model: RecoveryProposalModel) -> RecoveryProposal:
        """Map ORM RecoveryProposalModel to pure RecoveryProposal domain entity."""
        try:
            created_at = model.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)

            strategy = RecoveryStrategy(model.strategy)
            confidence = Confidence(basis_points=model.confidence_bps)
            source = ProposalSource(model.source)

            return RecoveryProposal(
                id=RecoveryProposalId(model.id),
                recovery_case_id=RecoveryCaseId(model.recovery_case_id),
                strategy=strategy,
                rationale=model.rationale,
                confidence=confidence,
                source=source,
                created_at=created_at,
            )
        except Exception as exc:
            raise DataCorruptionError("RecoveryProposal", model.id, str(exc)) from exc

    @staticmethod
    def to_model(domain: RecoveryProposal, merchant_id: str) -> RecoveryProposalModel:
        """Map pure RecoveryProposal domain entity to ORM RecoveryProposalModel."""
        return RecoveryProposalModel(
            id=str(domain.id),
            merchant_id=merchant_id,
            recovery_case_id=str(domain.recovery_case_id),
            strategy=domain.strategy.value,
            rationale=domain.rationale,
            confidence_bps=domain.confidence.basis_points,
            source=domain.source.value,
            created_at=domain.created_at,
        )
