"""Example-based tests for the Rule_Engine (Req 3)."""

import pytest

from profiler.core.profiling import profile_columns
from profiler.core.rules import evaluate, parse_rule_set, suggest_rules
from profiler.domain import Dataset, RuleResult, RulesError
from profiler.domain.rules import rule_params


def _single(cells: list[str], rule: object) -> RuleResult:
    dataset = Dataset(header=("c",), rows=tuple((c,) for c in cells))
    rule_set = parse_rule_set(f'{{"columns":[{{"column":"c","rules":[{rule}]}}]}}')
    return evaluate(dataset, rule_set, "user")[0].result


@pytest.mark.parametrize(
    ("cells", "rule", "failed_rows"),
    [
        (["a", " ", ""], '"not_null"', (3, 4)),
        (["a", " a", "b", "", "a"], '"unique"', (3, 6)),
        (["a@example.com", "x@y", "", "bad@", "a.b+c@sub.example.org"], '"valid_email"', (3, 5)),
        (["ab", "AB", "a1"], '{"name":"regex","pattern":"[a-z]+"}', (3, 4)),
        (["5", "10", "11", "abc", "1e1"], '{"name":"in_range","min":5,"max":10}', (4, 5)),
        (["x", "y", "X"], '{"name":"accepted_values","values":["x","y"]}', (4,)),
        (["1", "2.5", "a"], '{"name":"type_is","type":"float"}', (4,)),
        (["1", "2.5"], '{"name":"type_is","type":"integer"}', (3,)),
        (["2024-01-01", "2024-02-30"], '{"name":"type_is","type":"datetime"}', (3,)),
        (["true", "1"], '{"name":"type_is","type":"boolean"}', (3,)),
        (["anything"], '{"name":"type_is","type":"string"}', ()),
    ],
)
def test_evaluate_rule_failing_rows(
    cells: list[str], rule: str, failed_rows: tuple[int, ...]
) -> None:
    result = _single(cells, rule)

    assert result.failed_rows == failed_rows
    assert result.status == ("FAIL" if failed_rows else "PASS")


def test_evaluate_rules_skip_nulls_except_not_null() -> None:
    result = _single(["", " ", "a@example.com"], '"valid_email"')

    assert (result.evaluated_count, result.failed_count) == (1, 0)


def test_evaluate_failed_rows_are_capped_at_ten() -> None:
    result = _single([""] * 15, '"not_null"')

    assert (result.failed_count, len(result.failed_rows)) == (15, 10)


def test_evaluate_missing_column_is_skipped_and_last() -> None:
    dataset = Dataset(header=("a", "b"), rows=(("1", "2"),))
    rule_set = parse_rule_set(
        '{"columns":[{"column":"zzz","rules":["not_null"]},'
        '{"column":"b","rules":["unique","not_null"]},{"column":"a","rules":["not_null"]}]}'
    )

    results = [e.result for e in evaluate(dataset, rule_set, "user")]

    assert [(r.column, r.rule.name, r.status) for r in results] == [
        ("a", "not_null", "PASS"),
        ("b", "unique", "PASS"),
        ("b", "not_null", "PASS"),
        ("zzz", "not_null", "SKIPPED"),
    ]


@pytest.mark.parametrize(
    ("text", "field"),
    [
        ("not json", None),
        ('{"columns":[{"column":"a","rules":["nope"]}]}', "columns.0.rules.0"),
        (
            '{"columns":[{"column":"a","rules":[{"name":"regex"}]}]}',
            "columns.0.rules.0.regex.pattern",
        ),
        (
            '{"columns":[{"column":"a","rules":[{"name":"regex","pattern":"("}]}]}',
            "columns.0.rules.0.regex.pattern",
        ),
        (
            '{"columns":[{"column":"a","rules":[{"name":"regex","pattern":"' + "a" * 201 + '"}]}]}',
            "columns.0.rules.0.regex.pattern",
        ),
        (
            '{"columns":[{"column":"a","rules":[{"name":"in_range","min":5,"max":1}]}]}',
            "columns.0.rules.0.in_range",
        ),
        (
            '{"columns":[{"column":"a","rules":[{"name":"in_range"}]}]}',
            "columns.0.rules.0.in_range",
        ),
        ('{"columns":[{"column":"a","rules":[{"name":"in_range","min":NaN}]}]}', None),
        (
            '{"columns":[{"column":"a","rules":[{"name":"accepted_values","values":[]}]}]}',
            "columns.0.rules.0.accepted_values.values",
        ),
        (
            '{"columns":[{"column":"a","rules":[{"name":"type_is","type":"null"}]}]}',
            "columns.0.rules.0.type_is.type",
        ),
        ('{"columns":[{"column":"a","rules":[]}]}', "columns.0.rules"),
        ('{"extra":1}', "extra"),
        ('{"business_key":[]}', "business_key"),
    ],
)
def test_parse_rule_set_rejects_invalid(text: str, field: str | None) -> None:
    with pytest.raises(RulesError) as info:
        parse_rule_set(text)

    assert info.value.field == field
    assert info.value.code == "INVALID_RULES"


def test_parse_rule_set_keeps_exact_decimal_params() -> None:
    rule_set = parse_rule_set(
        '{"columns":[{"column":"a","rules":[{"name":"in_range","min":0.1}]}]}'
    )

    assert rule_params(rule_set.columns[0].rules[0]) == {"name": "in_range", "min": 0.1}


def test_suggest_rules_matrix() -> None:
    dataset = Dataset(
        header=("id", "contact_EMAIL", "flag", "note", "empty"),
        rows=(("1", "a@x.io", "true", "x", ""), ("2", "", "false", "x", "")),
    )

    suggested = suggest_rules(profile_columns(dataset), len(dataset.rows))

    assert [(c.column, [r.name for r in c.rules]) for c in suggested.columns] == [
        ("id", ["not_null", "unique", "type_is"]),
        ("contact_EMAIL", ["valid_email"]),
        ("flag", ["not_null", "unique", "type_is"]),
        ("note", ["not_null"]),
    ]
