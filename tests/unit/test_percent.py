"""Tests for Percentage rounding."""

from fractions import Fraction

import pytest

from profiler.core.percent import ratio, to_percentage


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Fraction(0), 0.0),
        (Fraction(1), 100.0),
        (Fraction(2, 3), 66.7),
        (Fraction(1, 8), 12.5),
        (Fraction(1, 16), 6.2),  # 6.25 -> half-even -> 6.2
        (Fraction(3, 16), 18.8),  # 18.75 -> half-even -> 18.8
        (Fraction(1, 3), 33.3),
    ],
)
def test_to_percentage_rounds_half_even(value: Fraction, expected: float) -> None:
    assert to_percentage(value) == expected


def test_ratio_uses_empty_value_for_zero_denominator() -> None:
    assert ratio(0, 0, empty=Fraction(1)) == 1
