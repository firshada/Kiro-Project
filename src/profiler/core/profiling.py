"""Profiler: column-level metrics (Req 2)."""

from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction

from profiler.core.percent import ratio, to_percentage
from profiler.core.type_inference import infer_type
from profiler.domain import ColumnProfile, Dataset


def is_null(cell: str) -> bool:
    """Return True when a cell is a Null_Value: empty or whitespace only."""
    return cell.strip() == ""


def column_cells(dataset: Dataset, index: int) -> tuple[str, ...]:
    """Return the raw cells of column ``index`` in row order."""
    return tuple(row[index] for row in dataset.rows)


def null_cell_count(dataset: Dataset) -> int:
    """Total Null_Value cells in the Dataset (Req 2.1)."""
    return sum(1 for row in dataset.rows for cell in row if is_null(cell))


def profile_columns(
    dataset: Dataset, invalid_counts: Mapping[str, int] | None = None
) -> tuple[ColumnProfile, ...]:
    """Compute a ColumnProfile per header column, in header order (Req 2.2-2.6).

    Args:
        dataset: a Valid_Dataset.
        invalid_counts: rows failing a validity rule, per column name (Req 2.6).

    Returns:
        One ColumnProfile per column.
    """
    counts = invalid_counts or {}
    return tuple(
        _profile_column(name, column_cells(dataset, index), counts.get(name, 0))
        for index, name in enumerate(dataset.header)
    )


def _profile_column(name: str, cells: tuple[str, ...], invalid_count: int) -> ColumnProfile:
    present = [cell.strip() for cell in cells if not is_null(cell)]
    null_count = len(cells) - len(present)
    unique_count = len(set(present))
    inferred = infer_type(cells)
    low, high = _min_max(present) if inferred in ("integer", "float") else (None, None)
    return ColumnProfile(
        name=name,
        inferred_type=inferred,
        null_count=null_count,
        null_pct=to_percentage(ratio(null_count, len(cells), empty=Fraction(0))),  # Req 2.3
        unique_count=unique_count,
        unique_pct=to_percentage(ratio(unique_count, len(present), empty=Fraction(0))),  # Req 2.4
        invalid_count=invalid_count,
        min=low,
        max=high,
    )


def _min_max(values: list[str]) -> tuple[str, str]:
    """Req 2.5: compare by exact decimal value; ties keep the first occurrence."""
    low = high = values[0]
    for value in values[1:]:
        number = Decimal(value)
        if number < Decimal(low):
            low = value
        elif number > Decimal(high):
            high = value
    return low, high
