"""HTML Reporter: one self-contained, accessible document (Req 6.6-6.9).

Every value from the upload or the Rule_Set passes through ``_e`` (``html.escape``).
Status is always written as text; colour is only a supplementary cue.
"""

import json
from collections.abc import Iterable, Sequence
from html import escape

from profiler.domain import FileError, FileResult, QualityReport
from profiler.domain.rules import rule_params

_STYLE = """
body{font-family:system-ui,sans-serif;margin:2rem;color:#1a1a1a;line-height:1.4}
table{border-collapse:collapse;margin:1rem 0;min-width:40%}
caption{text-align:left;font-weight:600;padding:.25rem 0}
th,td{border:1px solid #767676;padding:.3rem .6rem;text-align:left}
th{background:#f0f0f0}
.score{font-size:2.5rem;font-weight:700;margin:.5rem 0}
.PASS{color:#0a6b2d}.FAIL{color:#a40e26;font-weight:700}.SKIPPED{color:#555}
.error{border-left:4px solid #a40e26;padding-left:1rem}
""".strip()


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _cell(value: object) -> str:
    return "—" if value is None else _e(value)


def _table(caption: str, headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    head = "".join(f'<th scope="col">{_e(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return (
        f"<table><caption>{_e(caption)}</caption>"
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


def _pairs(caption: str, pairs: Sequence[tuple[str, object]]) -> str:
    rows = "".join(f'<tr><th scope="row">{_e(k)}</th><td>{_cell(v)}</td></tr>' for k, v in pairs)
    return f"<table><caption>{_e(caption)}</caption><tbody>{rows}</tbody></table>"


def _rows(values: Sequence[int]) -> str:
    return ", ".join(str(v) for v in values) or "—"


def _report_section(report: QualityReport) -> str:
    d, s = report.dimensions, report.summary
    dimensions = _pairs(
        "Quality dimensions (%)",
        [
            ("Completeness", d.completeness),
            ("Uniqueness", d.uniqueness),
            ("Validity", d.validity),
            ("Consistency", d.consistency),
        ],
    )
    summary = _pairs(
        "Summary",
        [
            ("Rows", s.row_count),
            ("Columns", s.column_count),
            ("Null values", s.null_count),
            ("Duplicate rows", s.duplicate_count),
            ("Potential issues", s.potential_issues),
            ("Issues (failing records)", report.issues),
        ],
    )
    columns = _table(
        "Columns",
        ["Column", "Type", "Null %", "Unique %", "Invalid", "Min", "Max"],
        (
            [
                _e(c.name),
                _e(c.inferred_type),
                _e(c.null_pct),
                _e(c.unique_pct),
                _e(c.invalid_count),
                _cell(c.min),
                _cell(c.max),
            ]
            for c in report.columns
        ),
    )
    rules = _table(
        "Validation rules",
        ["Status", "Column", "Rule", "Source", "Evaluated", "Failed", "First failing rows"],
        (
            [
                f'<span class="{r.status}">{r.status}</span>',
                _e(r.column),
                f"<code>{_e(json.dumps(rule_params(r.rule), ensure_ascii=False))}</code>",
                _e(r.source),
                _e(r.evaluated_count),
                _e(r.failed_count),
                _rows(r.failed_rows),
            ]
            for r in report.rules
        ),
    )
    dup = report.duplicates
    duplicates = _pairs(
        "Duplicate detection",
        [
            ("Business key", ", ".join(dup.key) if dup.key else "whole row"),
            ("Key status", dup.key_status),
            ("Missing key columns", ", ".join(dup.missing_columns) or None),
            ("Total records", dup.total_records),
            ("Unique records", dup.unique_records),
            ("Duplicate records", dup.duplicate_records),
            ("First duplicate rows", _rows(dup.duplicate_rows)),
        ],
    )
    return (
        f"<section><h2>{_e(report.dataset)}</h2>"
        f'<p class="score">Data quality score: {_e(report.score)} <small>/ 100</small></p>'
        f"{dimensions}{summary}{columns}{rules}{duplicates}</section>"
    )


def _error_section(error: FileError) -> str:
    details = [
        ("Code", error.code),
        ("Message", error.message),
        ("Line", error.line),
        ("Positions", ", ".join(str(p) for p in error.positions) or None),
        ("Row number", error.row_number),
    ]
    return (
        f'<section class="error"><h2>{_e(error.dataset)}</h2>'
        f"<p>Validation failed.</p>{_pairs('Error', details)}</section>"
    )


def to_html(results: Sequence[FileResult]) -> bytes:
    """Render all file results as one UTF-8 HTML5 document."""
    sections = "".join(
        _error_section(r) if isinstance(r, FileError) else _report_section(r) for r in results
    )
    document = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Scrubby quality report</title><style>{_STYLE}</style></head>"
        f"<body><main><h1>Scrubby quality report</h1>{sections}</main></body></html>"
    )
    return document.encode("utf-8")
