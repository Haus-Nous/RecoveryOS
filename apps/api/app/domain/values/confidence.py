"""Bounded Confidence score value object."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.exceptions import InvalidConfidenceError


@dataclass(frozen=True, slots=True)
class Confidence:
    """Confidence score bounded strictly between 0 and 10000 basis points (0.00% to 100.00%).

    CRITICAL: Confidence score is purely diagnostic and NEVER grants authorization.
    """

    basis_points: int

    def __post_init__(self) -> None:
        if isinstance(self.basis_points, bool) or not isinstance(self.basis_points, int):
            raise InvalidConfidenceError(
                f"Confidence basis_points must be an integer, got "
                f"{type(self.basis_points).__name__} (floats prohibited)."
            )
        if self.basis_points < 0 or self.basis_points > 10000:
            raise InvalidConfidenceError(
                f"Confidence basis_points must be between 0 and 10000, got {self.basis_points}."
            )

    @classmethod
    def from_percentage_int(cls, percent: int) -> "Confidence":
        """Create from integer percent [0, 100]."""
        if isinstance(percent, bool) or not isinstance(percent, int):
            raise InvalidConfidenceError(
                f"Percent must be an integer, got {type(percent).__name__}"
            )
        return cls(basis_points=percent * 100)

    @classmethod
    def from_decimal(cls, dec: Decimal) -> "Confidence":
        """Create from Decimal fraction between 0.0000 and 1.0000."""
        if isinstance(dec, float):
            raise InvalidConfidenceError(
                "Float confidence prohibited. Use Decimal or int basis points."
            )
        bps = int(dec * 10000)
        return cls(basis_points=bps)

    def as_fraction(self) -> Decimal:
        return Decimal(self.basis_points) / Decimal(10000)

    def as_percentage_str(self) -> str:
        pct = Decimal(self.basis_points) / Decimal(100)
        return f"{pct:.2f}%"

    def __str__(self) -> str:
        return self.as_percentage_str()
