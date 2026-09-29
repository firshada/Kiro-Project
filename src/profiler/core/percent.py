"""Percentage rounding (Glossary "Percentage", Req 5.4)."""

from decimal import ROUND_HALF_EVEN, Context, Decimal
from fractions import Fraction

_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)
_ONE_DP = Decimal("0.1")


def ratio(numerator: int, denominator: int, *, empty: Fraction) -> Fraction:
    """Return ``numerator / denominator`` exactly, or ``empty`` when the denominator is 0."""
    return Fraction(numerator, denominator) if denominator else empty


def to_percentage(value: Fraction) -> float:
    """Convert a ratio in [0, 1] to a 0-100 Percentage rounded half-even to 1 decimal.

    Uses a local Decimal context, so the result never depends on global state.
    """
    scaled = _CONTEXT.divide(Decimal(value.numerator * 100), Decimal(value.denominator))
    return float(scaled.quantize(_ONE_DP, context=_CONTEXT))
