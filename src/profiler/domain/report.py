"""Quality_Report types (Req 2, 3.5, 4.3, 5, 6.1). All immutable."""

from dataclasses import dataclass
from typing import Literal

from profiler.domain.rules import Rule, RuleKind

InferredType = Literal["integer", "float", "boolean", "datetime", "string", "null"]
RuleStatus = Literal["PASS", "FAIL", "SKIPPED"]
RuleSource = Literal["user", "suggested"]
KeyStatus = Literal["WHOLE_ROW", "OK", "MISSING_COLUMNS"]

MAX_LISTED_ROWS = 10


@dataclass(frozen=True)
class ColumnProfile:
    """Column-level metrics (Req 2.2). ``min``/``max`` are trimmed source strings."""

    name: str
    inferred_type: InferredType
    null_count: int
    null_pct: float
    unique_count: int
    unique_pct: float
    invalid_count: int
    min: str | None
    max: str | None


@dataclass(frozen=True)
class RuleResult:
    """Outcome of one rule on one column (Req 3.5). Never holds cell values."""

    column: str
    rule: Rule
    kind: RuleKind
    source: RuleSource
    status: RuleStatus
    evaluated_count: int
    failed_count: int
    failed_rows: tuple[int, ...]


@dataclass(frozen=True)
class DuplicateResult:
    """Deduplicator output (Req 4.3)."""

    key: tuple[str, ...] | None
    key_status: KeyStatus
    missing_columns: tuple[str, ...]
    total_records: int
    unique_records: int
    duplicate_records: int
    duplicate_rows: tuple[int, ...]


@dataclass(frozen=True)
class Dimensions:
    """Quality dimensions as Percentages (Req 5.1)."""

    completeness: float
    uniqueness: float
    validity: float
    consistency: float


@dataclass(frozen=True)
class Summary:
    """Dataset-level metrics (Req 2.1)."""

    row_count: int
    column_count: int
    null_count: int
    duplicate_count: int
    potential_issues: int


@dataclass(frozen=True)
class QualityReport:
    """Full report for one Valid_Dataset, fields in Req 6.1 order."""

    dataset: str
    score: float
    issues: int
    dimensions: Dimensions
    summary: Summary
    columns: tuple[ColumnProfile, ...]
    rules: tuple[RuleResult, ...]
    duplicates: DuplicateResult


@dataclass(frozen=True)
class FileError:
    """Per-file validation failure (Req 6.4)."""

    dataset: str
    code: str
    message: str
    line: int | None = None
    positions: tuple[int, ...] = ()
    row_number: int | None = None


FileResult = QualityReport | FileError
