"""Upload_Handler: validate raw bytes and build a Dataset (Req 1)."""

import csv
import io

from profiler.domain import Dataset, ErrorCode, ValidationError

MAX_BYTES = 104_857_600


def load_dataset(data: bytes, *, max_bytes: int = MAX_BYTES) -> Dataset:
    """Validate CSV bytes and return a Dataset of raw, untrimmed cells.

    Checks run in the precedence order of Req 1.7. The full parse finishes before
    header or row checks, so INVALID_FORMAT anywhere wins over header problems.

    Args:
        data: the uploaded file content.
        max_bytes: size limit; larger inputs are rejected without parsing (Req 1.6).

    Returns:
        The validated Dataset.

    Raises:
        ValidationError: with the single highest-precedence failing code.
    """
    if len(data) > max_bytes:
        raise ValidationError(ErrorCode.FILE_TOO_LARGE, f"file exceeds {max_bytes} bytes")
    if not data:
        raise ValidationError(ErrorCode.EMPTY_DATASET, "file is empty")  # Req 1.3

    records = _parse(data)
    if not records or not records[0]:
        raise ValidationError(ErrorCode.EMPTY_DATASET, "no header row")

    header = tuple(records[0])
    _check_header(header)
    rows = tuple(tuple(record) for record in records[1:])
    _check_row_lengths(header, rows)
    return Dataset(header=header, rows=rows)


def _parse(data: bytes) -> list[list[str]]:
    """Decode strict UTF-8 and parse RFC 4180 CSV (Req 1.2)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        line = data[: exc.start].count(b"\n") + 1
        raise ValidationError(
            ErrorCode.INVALID_FORMAT, f"invalid UTF-8 on line {line}", line=line
        ) from exc
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        return list(reader)
    except csv.Error as exc:
        raise ValidationError(
            ErrorCode.INVALID_FORMAT, f"malformed CSV: {exc}", line=reader.line_num or None
        ) from exc


def _check_header(header: tuple[str, ...]) -> None:
    """Reject empty or exact-duplicate names, listing every position (Req 1.4)."""
    positions = tuple(
        index
        for index, name in enumerate(header, start=1)
        if not name.strip() or header.count(name) > 1
    )
    if positions:
        raise ValidationError(
            ErrorCode.INVALID_HEADER,
            f"empty or duplicate column names at positions {list(positions)}",
            positions=positions,
        )


def _check_row_lengths(header: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> None:
    """Report the first row whose width differs from the header (Req 1.5)."""
    for row_number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            raise ValidationError(
                ErrorCode.ROW_LENGTH_MISMATCH,
                f"row {row_number} has {len(row)} fields, expected {len(header)}",
                row_number=row_number,
            )
