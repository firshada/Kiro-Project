"""Example-based tests for report building and rendering (Req 6)."""

import json

from profiler.core.render_html import to_html
from profiler.core.render_json import to_json
from profiler.core.report import build_report, process_file
from profiler.core.rules import parse_rule_set
from profiler.domain import Dataset, FileError

DATASET = Dataset(
    header=("id", "email"),
    rows=(("1", "a@x.io"), ("2", "bad"), ("2", "worse"), ("3", "")),
)
RULES = parse_rule_set(
    '{"business_key":["id"],"columns":[{"column":"email","rules":["valid_email","not_null"]}]}'
)


def test_build_report_issues_and_potential_issues() -> None:
    report = build_report("c.csv", DATASET, RULES)

    assert report.issues == 2 + 1 + 1  # invalid emails + null email + duplicate id
    assert report.summary.potential_issues == 3
    assert report.summary.duplicate_count == 1
    assert report.columns[1].invalid_count == 2


def test_build_report_without_rules_uses_suggestions() -> None:
    report = build_report("c.csv", DATASET)

    assert {r.source for r in report.rules} == {"suggested"}
    assert report.duplicates.key is None


def test_to_json_key_order() -> None:
    payload = json.loads(to_json([build_report("c.csv", DATASET, RULES)]))

    report = payload["reports"][0]
    assert list(report) == [
        "dataset",
        "score",
        "issues",
        "dimensions",
        "summary",
        "columns",
        "rules",
        "duplicates",
    ]
    assert list(report["dimensions"]) == ["completeness", "uniqueness", "validity", "consistency"]


def test_process_file_error_shape() -> None:
    result = process_file("bad.csv", b"a,a\n1,2\n")

    assert isinstance(result, FileError)
    assert json.loads(to_json([result]))["reports"][0] == {
        "dataset": "bad.csv",
        "error": {
            "code": "INVALID_HEADER",
            "message": "empty or duplicate column names at positions [1, 2]",
            "line": None,
            "positions": [1, 2],
            "row_number": None,
        },
    }


def test_to_html_escapes_and_labels_status() -> None:
    dataset = Dataset(header=("<script>alert(1)</script>",), rows=(("",),))
    report = build_report(
        'x"<y>.csv',
        dataset,
        parse_rule_set('{"columns":[{"column":"<script>alert(1)</script>","rules":["not_null"]}]}'),
    )

    html = to_html([report, process_file("e&.csv", b"")]).decode("utf-8")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "x&quot;&lt;y&gt;.csv" in html
    assert ">FAIL<" in html
    assert "e&amp;.csv" in html
    assert '<html lang="en">' in html
    assert "<link" not in html and "src=" not in html
