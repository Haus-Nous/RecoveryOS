"""Bi-directional mapper for RecoveryOutcome domain entity and RecoveryOutcomeModel."""

import uuid
from datetime import UTC

from app.application.exceptions import DataCorruptionError
from app.domain.entities.recovery_outcome import OutcomeStatus, RecoveryOutcome, VerificationStatus
from app.domain.types import RecoveryActionId, RecoveryCaseId
from app.domain.values.currency import Currency
from app.domain.values.money import Money
from app.infrastructure.persistence.models.recovery_outcome import RecoveryOutcomeModel


class RecoveryOutcomeMapper:
    """Explicit mapper between RecoveryOutcome domain and RecoveryOutcomeModel ORM."""

    @staticmethod
    def to_domain(model: RecoveryOutcomeModel) -> RecoveryOutcome:
        """Map ORM RecoveryOutcomeModel to pure RecoveryOutcome domain entity."""
        try:
            observed_at = model.observed_at
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=UTC)

            verified_at = model.verified_at
            if verified_at is not None and verified_at.tzinfo is None:
                verified_at = verified_at.replace(tzinfo=UTC)

            currency = Currency.from_str(model.currency)
            money = Money.from_minor(model.amount_recovered_minor, currency)
            status = OutcomeStatus(model.status)
            verification_status = VerificationStatus(model.verification_status)

            return RecoveryOutcome(
                recovery_case_id=RecoveryCaseId(model.recovery_case_id),
                recovery_action_id=RecoveryActionId(model.recovery_action_id),
                status=status,
                amount_recovered=money,
                observed_at=observed_at,
                verification_status=verification_status,
                verification_reference=model.verification_reference,
                verified_at=verified_at,
            )
        except Exception as exc:
            raise DataCorruptionError("RecoveryOutcome", model.id, str(exc)) from exc

    @staticmethod
    def to_model(
        domain: RecoveryOutcome, merchant_id: str, model_id: str | None = None
    ) -> RecoveryOutcomeModel:
        """Map pure RecoveryOutcome domain entity to ORM RecoveryOutcomeModel."""
        mid = model_id or f"out_{uuid.uuid4().hex}"
        return RecoveryOutcomeModel(
            id=mid,
            merchant_id=merchant_id,
            recovery_case_id=str(domain.recovery_case_id),
            recovery_action_id=str(domain.recovery_action_id),
            status=domain.status.value,
            amount_recovered_minor=domain.amount_recovered.amount_minor,
            currency=domain.amount_recovered.currency.value,
            observed_at=domain.observed_at,
            verification_status=domain.verification_status.value,
            verification_reference=domain.verification_reference,
            verified_at=domain.verified_at,
        )
