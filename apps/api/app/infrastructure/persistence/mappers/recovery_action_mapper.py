"""Bi-directional mapper for RecoveryAction domain aggregate and RecoveryActionModel."""

from datetime import UTC

from app.application.exceptions import DataCorruptionError
from app.domain.entities.recovery_action import RecoveryAction, RecoveryActionState
from app.domain.entities.recovery_proposal import RecoveryStrategy
from app.domain.types import RecoveryActionId, RecoveryCaseId
from app.domain.values.decision import PolicyDecision
from app.infrastructure.persistence.models.recovery_action import RecoveryActionModel


class RecoveryActionMapper:
    """Explicit mapper between RecoveryAction domain and RecoveryActionModel ORM."""

    @staticmethod
    def to_domain(model: RecoveryActionModel) -> RecoveryAction:
        """Map ORM RecoveryActionModel to pure RecoveryAction domain aggregate."""
        try:
            created_at = model.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)

            updated_at = model.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)

            strategy = RecoveryStrategy(model.strategy)
            state = RecoveryActionState(model.state)
            decision = (
                PolicyDecision(model.authorization_decision)
                if model.authorization_decision
                else None
            )

            return RecoveryAction(
                id=RecoveryActionId(model.id),
                recovery_case_id=RecoveryCaseId(model.recovery_case_id),
                strategy=strategy,
                state=state,
                created_at=created_at,
                updated_at=updated_at,
                authorization_decision=decision,
                authorization_reference=model.authorization_reference,
                attempt_number=model.attempt_number,
                failure_reason=model.failure_reason,
            )
        except Exception as exc:
            raise DataCorruptionError("RecoveryAction", model.id, str(exc)) from exc

    @staticmethod
    def to_model(domain: RecoveryAction, merchant_id: str, version: int = 1) -> RecoveryActionModel:
        """Map pure RecoveryAction domain aggregate to ORM RecoveryActionModel."""
        decision = domain.authorization_decision.value if domain.authorization_decision else None

        return RecoveryActionModel(
            id=str(domain.id),
            merchant_id=merchant_id,
            recovery_case_id=str(domain.recovery_case_id),
            strategy=domain.strategy.value,
            state=domain.state.value,
            authorization_decision=decision,
            authorization_reference=domain.authorization_reference,
            attempt_number=domain.attempt_number,
            failure_reason=domain.failure_reason,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
            version=version,
        )
