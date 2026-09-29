"""JSON Reporter (Req 6.1, 6.4, 6.5, 6.9). Keys are emitted in documented order."""

import json
from collections.abc import Sequence

from profiler.domain import (
    ColumnProfile,
    DuplicateResult,
    FileError,
    FileResult,
    QualityReport,
    RuleResult,
)
from profiler.domain.rules import rule_params


def result_to_dict(result: FileResult) -> dict[str, object]:
    """Return an ordered, JSON-ready dict for one file result."""
    if isinstance(result, FileError):
        return {
            "dataset": result.dataset,
            "error": {
                "code": result.code,
                "message": result.message,
                "line": result.line,
                "positions": list(result.positions),
                "row_number": result.row_number,
            },
        }
    return report_to_dict(result)


def report_to_dict(report: QualityReport) -> dict[str, object]:
    """Ordered dict for a QualityReport (Req 6.1)."""
    d = report.dimensions
    s = report.summary
    return {
        "dataset": report.dataset,
        "score": report.score,
        "issues": report.issues,
        "dimensions": {
            "completeness": d.completeness,
            "uniqueness": d.uniqueness,
            "validity": d.validity,
            "consistency": d.consistency,
        },
        "summary": {
            "row_count": s.row_count,
            "column_count": s.column_count,
            "null_count": s.null_count,
            "duplicate_count": s.duplicate_count,
            "potential_issues": s.potential_issues,
        },
        "columns": [_column(c) for c in report.columns],
        "rules": [_rule(r) for r in report.rules],
        "duplicates": duplicates_to_dict(report.duplicates),
    }


def _column(c: ColumnProfile) -> dict[str, object]:
    return {
        "name": c.name,
        "inferred_type": c.inferred_type,
        "null_count": c.null_count,
        "null_pct": c.null_pct,
        "unique_count": c.unique_count,
        "unique_pct": c.unique_pct,
        "invalid_count": c.invalid_count,
        "min": c.min,
        "max": c.max,
    }


def _rule(r: RuleResult) -> dict[str, object]:
    return {
        "column": r.column,
        "rule": rule_params(r.rule),
        "source": r.source,
        "status": r.status,
        "evaluated_count": r.evaluated_count,
        "failed_count": r.failed_count,
        "failed_rows": list(r.failed_rows),
    }


def duplicates_to_dict(d: DuplicateResult) -> dict[str, object]:
    """Ordered dict for a DuplicateResult (Req 4.3)."""
    return {
        "key": list(d.key) if d.key is not None else None,
        "key_status": d.key_status,
        "missing_columns": list(d.missing_columns),
        "total_records": d.total_records,
        "unique_records": d.unique_records,
        "duplicate_records": d.duplicate_records,
        "duplicate_rows": list(d.duplicate_rows),
    }


def to_json(results: Sequence[FileResult]) -> bytes:
    """Render ``{"reports": [...]}`` as compact UTF-8 JSON without a BOM."""
    payload = {"reports": [result_to_dict(r) for r in results]}
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return text.encode("utf-8")
