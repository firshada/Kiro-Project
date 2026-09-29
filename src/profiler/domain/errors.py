"""Typed domain errors with machine-readable codes."""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Upload_Handler error codes, listed in precedence order (Req 1.8)."""

    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    EMPTY_DATASET = "EMPTY_DATASET"
    INVALID_FORMAT = "INVALID_FORMAT"
    INVALID_HEADER = "INVALID_HEADER"
    ROW_LENGTH_MISMATCH = "ROW_LENGTH_MISMATCH"


class ValidationError(Exception):
    """A Dataset failed validation. Carries exactly one ErrorCode.

    Attributes:
        code: the ErrorCode.
        message: human-readable description (never contains cell values).
        line: 1-based line for INVALID_FORMAT, when known.
        positions: 1-based, ascending column positions for INVALID_HEADER.
        row_number: first mismatched row for ROW_LENGTH_MISMATCH (header = 1).
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        line: int | None = None,
        positions: tuple[int, ...] = (),
        row_number: int | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.line = line
        self.positions = positions
        self.row_number = row_number


class RulesError(Exception):
    """The Rule_Set is invalid (Req 3.2). Always code ``INVALID_RULES``.

    Attributes:
        field: dotted location of the offending entry, or None for a parse failure.
        reason: human-readable reason.
    """

    code = "INVALID_RULES"

    def __init__(self, field: str | None, reason: str) -> None:
        super().__init__(f"{field}: {reason}" if field else reason)
        self.field = field
        self.reason = reason

    @property
    def message(self) -> str:
        """Single stable message naming the offending entry."""
        return str(self)
