"""Column type inference (Req 4)."""

import math
import re
from collections.abc import Iterable
from datetime import date

from profiler.domain import InferredType, ValueType

_BOOLEAN = re.compile(r"(?i)^(true|false)$")
_INTEGER = re.compile(r"^[+-]?[0-9]+$")
_FLOAT = re.compile(r"^[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?$")
_DATE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")
_DATETIME = re.compile(
    r"^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2})(?::([0-9]{2})(?:\.[0-9]+)?)?(Z|[+-]([0-9]{2}):([0-9]{2}))?$"
)


def is_boolean(value: str) -> bool:
    """Req 4.3: only true/false, case-insensitive."""
    return _BOOLEAN.fullmatch(value) is not None


def is_integer(value: str) -> bool:
    """Req 4.1: optional sign and ASCII digits only."""
    return _INTEGER.fullmatch(value) is not None


def is_float(value: str) -> bool:
    """Req 4.2, 4.8: decimal or exponent form, finite; rejects NaN, Infinity, hex, 1,000."""
    return _FLOAT.fullmatch(value) is not None and math.isfinite(float(value))


def _valid_date(year: str, month: str, day: str) -> bool:
    try:
        date(int(year), int(month), int(day))
    except ValueError:
        return False
    return True


def is_datetime(value: str) -> bool:
    """Req 4.4, 4.9: ISO 8601 date or date-time that is a real calendar value."""
    if (m := _DATE.fullmatch(value)) is not None:
        return _valid_date(*m.groups())
    if (m := _DATETIME.fullmatch(value)) is None:
        return False
    year, month, day, hour, minute, second, _zone, off_h, off_m = m.groups()
    return (
        _valid_date(year, month, day)
        and int(hour) <= 23
        and int(minute) <= 59
        and (second is None or int(second) <= 59)
        and (off_h is None or int(off_h) <= 23)
        and (off_m is None or int(off_m) <= 59)
    )


def value_type(value: str) -> ValueType:
    """Return the first Value_Type a Trimmed_Value satisfies (Req 2.7)."""
    if is_boolean(value):
        return "boolean"
    if is_integer(value):
        return "integer"
    if is_float(value):
        return "float"
    if is_datetime(value):
        return "datetime"
    return "string"


def is_numeric(value: str) -> bool:
    """True for ``integer`` or ``float`` values."""
    return is_integer(value) or is_float(value)


def satisfies(value: str, expected: ValueType) -> bool:
    """Whether a Trimmed_Value satisfies ``expected`` for ``type_is`` (Req 3.3).

    ``integer`` values satisfy ``float``; every value satisfies ``string``.
    """
    match expected:
        case "boolean":
            return is_boolean(value)
        case "integer":
            return is_integer(value)
        case "float":
            return is_numeric(value)
        case "datetime":
            return is_datetime(value)
        case "string":
            return True


def infer_type(values: Iterable[str]) -> InferredType:
    """Return the first type, in Req 4.7 order, that every non-null trimmed value satisfies.

    Args:
        values: raw cells of one column.

    Returns:
        One Inferred_Type; ``null`` when every cell is null or there are none (Req 4.6).
    """
    present = [v.strip() for v in values if v.strip()]
    if not present:
        return "null"
    if all(is_boolean(v) for v in present):
        return "boolean"
    if all(is_integer(v) for v in present):
        return "integer"
    if all(is_numeric(v) for v in present):
        return "float"
    if all(is_datetime(v) for v in present):
        return "datetime"
    return "string"
