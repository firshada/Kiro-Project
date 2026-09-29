"""Hypothesis property tests for profiling, rules, dedup, scoring, and reporting."""

import math
import re
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from html import escape

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from profiler.core.dedup import detect_duplicates
from profiler.core.profiling import profile_columns
from profiler.core.render_html import to_html
from profiler.core.render_json import to_json
from profiler.core.report import build_report
from profiler.core.rules import evaluate
from profiler.core.scoring import compute_dimensions
from profiler.domain import Dataset, RuleSet
from profiler.domain.rules import (
    AcceptedValuesRule,
    ColumnRules,
    InRangeRule,
    NotNullRule,
    RegexRule,
    TypeIsRule,
    UniqueRule,
    ValidEmailRule,
)
from tests.strategies import complete_rows, datasets, rule_sets, rules

NUMBER = re.compile(r"[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?")
DATE_SHAPE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
    r"(T[0-9]{2}:[0-9]{2}(:[0-9]{2}(\.[0-9]+)?)?(Z|[+-][0-9]{2}:[0-9]{2})?)?"
)


# Feature: dataset-profiling, Property 5: Column profile matches a reference model
@settings(max_examples=200)
@given(dataset=datasets())
def test_profile_columns_match_reference(dataset: Dataset) -> None:
    profiles = profile_columns(dataset)

    for index, column in enumerate(profiles):
        cells = [row[index] for row in dataset.rows]
        present = [c.strip() for c in cells if len(c.strip()) > 0]
        assert column.name == dataset.header[index]
        assert column.null_count == len(cells) - len(present)
        assert column.unique_count == len(dict.fromkeys(present))
        assert column.unique_count <= len(cells) - column.null_count
        assert 0 <= column.null_pct <= 100 and 0 <= column.unique_pct <= 100
        if column.min is not None and column.max is not None:
            numbers = [Decimal(v) for v in present]
            assert Decimal(column.min) == min(numbers)
            assert Decimal(column.max) == max(numbers)


def _reference_fails(rule: object, cell: str) -> bool:
    """Naive per-cell reference predicates (unique handled separately)."""
    value = cell.strip()
    if isinstance(rule, NotNullRule):
        return value == ""
    if value == "":
        return False
    if isinstance(rule, ValidEmailRule):
        local, at, domain = value.partition("@")
        labels = domain.split(".")
        ok_local = local != "" and all(
            ch.isascii() and (ch.isalnum() or ch in ".!#$%&'*+/=?^_`{|}~-") for ch in local
        )
        ok_labels = len(labels) >= 2 and all(
            label != ""
            and all(ch.isascii() and (ch.isalnum() or ch == "-") for ch in label)
            and label[0] != "-"
            and label[-1] != "-"
            for label in labels
        )
        return not (at and ok_local and ok_labels)
    if isinstance(rule, RegexRule):
        return re.fullmatch(rule.pattern, value) is None
    if isinstance(rule, AcceptedValuesRule):
        return value not in rule.values
    if isinstance(rule, InRangeRule):
        if not _numeric(value):
            return True
        number = Decimal(value)
        return (rule.min is not None and number < rule.min) or (
            rule.max is not None and number > rule.max
        )
    if isinstance(rule, TypeIsRule):
        return not _reference_type(value, rule.type)
    raise AssertionError(rule)


def _numeric(value: str) -> bool:
    return NUMBER.fullmatch(value) is not None and math.isfinite(float(value))


def _reference_type(value: str, expected: str) -> bool:
    if expected == "string":
        return True
    if expected == "boolean":
        return value.lower() in ("true", "false")
    if expected == "integer":
        return re.fullmatch(r"[+-]?[0-9]+", value) is not None
    if expected == "float":
        return _numeric(value)
    try:  # datetime: stdlib parser as the reference, restricted to the documented shapes
        parsed_ok = bool(DATE_SHAPE.fullmatch(value)) and datetime.fromisoformat(value) is not None
    except ValueError:
        parsed_ok = False
    return parsed_ok


# Feature: dataset-profiling, Property 7: Rule results match reference predicates
@settings(max_examples=200)
@given(dataset=datasets(), rule=rules)
def test_rule_results_match_reference(dataset: Dataset, rule: object) -> None:
    column = dataset.header[0]
    rule_set = RuleSet(columns=(ColumnRules(column=column, rules=(rule,)),))  # type: ignore[arg-type]

    result = evaluate(dataset, rule_set, "user")[0].result

    cells = [row[0] for row in dataset.rows]
    if isinstance(rule, UniqueRule):
        seen: set[str] = set()
        expected = []
        for number, cell in enumerate(cells, start=2):
            if cell.strip():
                if cell.strip() in seen:
                    expected.append(number)
                seen.add(cell.strip())
    else:
        expected = [n for n, c in enumerate(cells, start=2) if _reference_fails(rule, c)]

    assert 0 <= result.failed_count <= result.evaluated_count <= len(cells)
    assert result.status == ("FAIL" if result.failed_count else "PASS")
    assert result.failed_count == len(expected)
    assert list(result.failed_rows) == expected[:10]


# Feature: dataset-profiling, Property 8: Duplicate invariants
@settings(max_examples=200)
@given(data=st.data(), dataset=datasets())
def test_duplicate_invariants(data: st.DataObject, dataset: Dataset) -> None:
    key = data.draw(
        st.none() | st.lists(st.sampled_from(dataset.header), min_size=1, unique=True).map(tuple),
        label="key",
    )

    result = detect_duplicates(dataset, key)

    if key is None:
        records = list(dataset.rows)
    else:
        idx = [dataset.header.index(k) for k in key]
        records = [tuple(row[i].strip() for i in idx) for row in dataset.rows]
    first = [r for i, r in enumerate(records) if r not in records[:i]]
    assert result.total_records == len(records)
    assert result.unique_records == len(first)
    assert result.duplicate_records == result.total_records - result.unique_records
    assert result.unique_records <= result.total_records
    assert (result.unique_records >= 1) == (result.total_records >= 1)


def _reference_dimensions(dataset: Dataset, rule_set: RuleSet) -> tuple[Fraction, ...]:
    results = [e.result for e in evaluate(dataset, rule_set, "user")]
    cells = [c for row in dataset.rows for c in row]
    filled = [c for c in cells if c.strip()]
    completeness = Fraction(len(filled), len(cells)) if cells else Fraction(1)
    dup = detect_duplicates(dataset, rule_set.business_key)
    uniqueness = (
        Fraction(dup.unique_records, dup.total_records) if dup.total_records else Fraction(1)
    )
    validity_rules = [
        r for r in results if r.rule.name not in ("not_null", "unique") and r.status != "SKIPPED"
    ]
    evaluated = sum(r.evaluated_count for r in validity_rules)
    failed = sum(r.failed_count for r in validity_rules)
    validity = Fraction(evaluated - failed, evaluated) if evaluated else Fraction(1)
    return completeness, uniqueness, validity


# Feature: dataset-profiling, Property 9: Score bounds and reference formula
@settings(max_examples=200)
@given(data=st.data(), dataset=datasets())
def test_score_bounds_and_reference(data: st.DataObject, dataset: Dataset) -> None:
    rule_set = data.draw(rule_sets(dataset.header), label="rules")
    results = [e.result for e in evaluate(dataset, rule_set, "user")]

    exact = compute_dimensions(dataset, results, detect_duplicates(dataset, rule_set.business_key))
    report = build_report("d.csv", dataset, rule_set)

    completeness, uniqueness, validity = _reference_dimensions(dataset, rule_set)
    assert (exact.completeness, exact.uniqueness, exact.validity) == (
        completeness,
        uniqueness,
        validity,
    )
    assert 0 <= exact.consistency <= 1
    assert exact.score() == (completeness + uniqueness + validity + exact.consistency) / 4
    values = [report.score, *vars(report.dimensions).values()]
    assert all(0 <= v <= 100 for v in values)


# Feature: dataset-profiling, Property 10: Clean record never lowers dimensions
@settings(max_examples=200)
@given(data=st.data(), dataset=datasets())
def test_clean_record_never_lowers_dimensions(data: st.DataObject, dataset: Dataset) -> None:
    rule_set = data.draw(rule_sets(dataset.header), label="rules")
    record = data.draw(complete_rows(len(dataset.header)), label="record")
    extended = Dataset(header=dataset.header, rows=(*dataset.rows, record))
    new_row = len(extended.rows) + 1
    evaluations = evaluate(extended, rule_set, "user")
    assume(all(new_row not in e.failing_rows for e in evaluations if e.result.kind == "validity"))
    before = build_report("d.csv", dataset, rule_set)
    after = build_report("d.csv", extended, rule_set)
    assume(after.duplicates.duplicate_records == before.duplicates.duplicate_records)

    for name in ("completeness", "uniqueness", "validity"):
        assert getattr(after.dimensions, name) >= getattr(before.dimensions, name)


# Feature: dataset-profiling, Property 11: Report determinism
@settings(max_examples=100)
@given(data=st.data(), dataset=datasets())
def test_report_rendering_is_deterministic(data: st.DataObject, dataset: Dataset) -> None:
    rule_set = data.draw(st.none() | rule_sets(dataset.header), label="rules")

    first = build_report("d.csv", dataset, rule_set)
    second = build_report("d.csv", dataset, rule_set)

    assert to_json([first]) == to_json([second])
    assert to_html([first]) == to_html([second])


# Feature: dataset-profiling, Property 12: HTML escaping
@settings(max_examples=200)
@given(
    name=st.text(alphabet="<>&\"'ab/ ", min_size=1, max_size=12),
    column=st.text(alphabet="<>&\"'cd", min_size=1, max_size=8),
)
def test_html_never_contains_unescaped_input(name: str, column: str) -> None:
    assume(any(ch in "<>&\"'" for ch in name + column))
    name, column = f"ZQ{name}QZ", f"ZQ{column}QZ"  # sentinels make matches unambiguous
    dataset = Dataset(header=(column,), rows=(("x",),))
    rule_set = RuleSet(
        columns=(
            ColumnRules(
                column=column, rules=(AcceptedValuesRule(name="accepted_values", values=(column,)),)
            ),
        )
    )

    html = to_html([build_report(name, dataset, rule_set)]).decode("utf-8")

    for value in (name, column):
        assert escape(value, quote=True) in html
        if any(ch in value for ch in "<>&\"'"):
            assert value not in html
