"""Build a Quality_Report from raw bytes or a Dataset (Req 2-6 orchestration)."""

from collections import defaultdict
from dataclasses import replace

from profiler.core.dedup import detect_duplicates
from profiler.core.percent import to_percentage
from profiler.core.profiling import null_cell_count, profile_columns
from profiler.core.rules import evaluate, suggest_rules
from profiler.core.scoring import compute_dimensions
from profiler.core.validation import MAX_BYTES, load_dataset
from profiler.domain import (
    Dataset,
    FileError,
    FileResult,
    QualityReport,
    RuleSet,
    Summary,
    ValidationError,
)


def build_report(name: str, dataset: Dataset, rule_set: RuleSet | None = None) -> QualityReport:
    """Run the pipeline for one Valid_Dataset.

    Args:
        name: the dataset's file name (base name only).
        dataset: a Valid_Dataset.
        rule_set: user rules, or None to use suggested rules (Req 3.6).

    Returns:
        The QualityReport.
    """
    columns = profile_columns(dataset)
    if rule_set is None:
        evaluations = evaluate(dataset, suggest_rules(columns, len(dataset.rows)), "suggested")
        key = None
    else:
        evaluations = evaluate(dataset, rule_set, "user")
        key = rule_set.business_key

    invalid_rows: defaultdict[str, set[int]] = defaultdict(set)
    for evaluation in evaluations:
        if evaluation.result.kind == "validity":
            invalid_rows[evaluation.result.column] |= evaluation.failing_rows
    columns = tuple(
        replace(c, invalid_count=len(invalid_rows.get(c.name, ()))) for c in columns
    )  # Req 2.6

    rules = tuple(e.result for e in evaluations)
    duplicates = detect_duplicates(dataset, key)
    exact = compute_dimensions(dataset, rules, duplicates)
    failed = [r for r in rules if r.status == "FAIL"]
    return QualityReport(
        dataset=name,
        score=to_percentage(exact.score()),
        issues=sum(r.failed_count for r in failed) + duplicates.duplicate_records,  # Req 6.2
        dimensions=exact.rounded(),
        summary=Summary(
            row_count=len(dataset.rows),
            column_count=len(dataset.header),
            null_count=null_cell_count(dataset),
            duplicate_count=duplicates.duplicate_records,
            potential_issues=len(failed) + (1 if duplicates.duplicate_records else 0),  # Req 6.3
        ),
        columns=columns,
        rules=rules,
        duplicates=duplicates,
    )


def process_file(
    name: str, data: bytes, rule_set: RuleSet | None = None, *, max_bytes: int = MAX_BYTES
) -> FileResult:
    """Validate and report one file; validation failures become a FileError (Req 1.10, 6.4)."""
    try:
        dataset = load_dataset(data, max_bytes=max_bytes)
    except ValidationError as exc:
        return file_error(name, exc)
    return build_report(name, dataset, rule_set)


def file_error(name: str, exc: ValidationError) -> FileError:
    """Convert a ValidationError into a per-file FileError."""
    return FileError(
        dataset=name,
        code=exc.code.value,
        message=exc.message,
        line=exc.line,
        positions=exc.positions,
        row_number=exc.row_number,
    )
