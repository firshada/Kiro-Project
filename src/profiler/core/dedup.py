"""Deduplicator: duplicate records by business key or whole row (Req 4)."""

from profiler.domain import MAX_LISTED_ROWS, Dataset, DuplicateResult
from profiler.domain.report import KeyStatus


def detect_duplicates(dataset: Dataset, key: tuple[str, ...] | None = None) -> DuplicateResult:
    """Count unique and duplicate records; the first occurrence is not a duplicate.

    Args:
        dataset: a Valid_Dataset.
        key: Business_Key columns. None compares whole raw rows (Req 4.1).

    Returns:
        A DuplicateResult. Missing key columns fall back to whole-row (Req 4.2).
    """
    missing = tuple(name for name in key or () if name not in dataset.header)
    status: KeyStatus
    if key is None or missing:
        indexes = None
        status = "MISSING_COLUMNS" if missing else "WHOLE_ROW"
        used_key = None
    else:
        indexes = tuple(dataset.header.index(name) for name in key)
        status = "OK"
        used_key = key

    seen: set[tuple[str, ...]] = set()
    duplicates: list[int] = []
    for row_number, row in enumerate(dataset.rows, start=2):
        record = row if indexes is None else tuple(row[i].strip() for i in indexes)
        if record in seen:
            duplicates.append(row_number)
        seen.add(record)

    return DuplicateResult(
        key=used_key,
        key_status=status,
        missing_columns=missing,
        total_records=len(dataset.rows),
        unique_records=len(seen),
        duplicate_records=len(duplicates),
        duplicate_rows=tuple(duplicates[:MAX_LISTED_ROWS]),
    )
