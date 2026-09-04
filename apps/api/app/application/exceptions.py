"""Application layer exceptions for persistence and domain operations."""


class ApplicationError(Exception):
    """Base exception for all application layer errors."""


class PersistenceError(ApplicationError):
    """Base exception for database and persistence failures."""


class EntityNotFoundError(PersistenceError):
    """Raised when an entity is not found in the persistence store."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with ID '{entity_id}' was not found.")


class DuplicateEntityError(PersistenceError):
    """Raised when inserting an entity that violates uniqueness constraints."""

    def __init__(self, entity_type: str, entity_id: str, details: str | None = None) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        msg = f"{entity_type} with ID '{entity_id}' already exists."
        if details:
            msg += f" {details}"
        super().__init__(msg)


class ConcurrencyConflictError(PersistenceError):
    """Raised when an optimistic concurrency check fails (version mismatch)."""

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        expected_version: int,
        actual_version: int | None = None,
    ) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        msg = (
            f"Concurrency conflict on {entity_type} [{entity_id}]: "
            f"expected version {expected_version}"
        )
        if actual_version is not None:
            msg += f", found version {actual_version}."
        else:
            msg += " (record modified or deleted by concurrent transaction)."
        super().__init__(msg)


class DataCorruptionError(PersistenceError):
    """Raised when persisted data cannot be mapped to a valid domain entity."""

    def __init__(self, entity_type: str, entity_id: str, reason: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.reason = reason
        super().__init__(f"Data corruption in {entity_type} [{entity_id}]: {reason}")
