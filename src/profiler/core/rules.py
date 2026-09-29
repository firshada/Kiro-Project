"""Rule_Engine: parse, suggest, and evaluate validation rules (Req 3)."""

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

import pydantic

from profiler.core.profiling import column_cells, is_null
from profiler.core.type_inference import is_numeric, satisfies
from profiler.domain import MAX_LISTED_ROWS, ColumnProfile, Dataset, Rule, RuleResult, RuleSet
from profiler.domain.errors import RulesError
from profiler.domain.report import RuleSource
from profiler.domain.rules import (
    AcceptedValuesRule,
    ColumnRules,
    InRangeRule,
    NotNullRule,
    RegexRule,
    TypeIsRule,
    UniqueRule,
    ValidEmailRule,
    rule_kind,
)

# Req 3.3: pragmatic RFC 5322 subset (ASCII local part, dotted domain labels).
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+"
)


@dataclass(frozen=True)
class Evaluation:
    """A RuleResult plus every failing row number (used for invalid_count)."""

    result: RuleResult
    failing_rows: frozenset[int]


def parse_rule_set(text: bytes | str) -> RuleSet:
    """Parse Rule_Set JSON; bare rule names become ``{"name": ...}`` (Req 3.1, 3.2).

    Raises:
        RulesError: naming the offending entry.
    """
    try:
        raw = json.loads(text, parse_float=Decimal, parse_constant=_reject_constant)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise RulesError(None, "rules must be valid JSON") from exc
    try:
        return RuleSet.model_validate(_normalize(raw))
    except pydantic.ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or None
        raise RulesError(field, first["msg"]) from exc


def _reject_constant(name: str) -> object:
    raise ValueError(f"{name} is not allowed")


def _normalize(raw: object) -> object:
    if not isinstance(raw, dict) or not isinstance(raw.get("columns"), list):
        return raw
    columns = []
    for entry in raw["columns"]:
        if isinstance(entry, dict) and isinstance(entry.get("rules"), list):
            rules = [{"name": r} if isinstance(r, str) else r for r in entry["rules"]]
            entry = {**entry, "rules": rules}
        columns.append(entry)
    return {**raw, "columns": columns}


def suggest_rules(columns: Sequence[ColumnProfile], row_count: int) -> RuleSet:
    """Derive rules from the profile only (Req 3.6), in header order."""
    entries: list[ColumnRules] = []
    for column in columns:
        if column.null_count == row_count:  # no non-null cells (includes zero rows)
            continue
        rules: list[Rule] = []
        if column.null_count == 0:
            rules.append(NotNullRule(name="not_null"))
            if column.unique_count == row_count:
                rules.append(UniqueRule(name="unique"))
        inferred = column.inferred_type
        if inferred != "string" and inferred != "null":
            rules.append(TypeIsRule(name="type_is", type=inferred))
        if "email" in column.name.lower():
            rules.append(ValidEmailRule(name="valid_email"))
        if rules:
            entries.append(ColumnRules(column=column.name, rules=tuple(rules)))
    return RuleSet(columns=tuple(entries))


def evaluate(dataset: Dataset, rule_set: RuleSet, source: RuleSource) -> tuple[Evaluation, ...]:
    """Evaluate every rule; results ordered by header position, then declaration (Req 3.7).

    Columns missing from the Dataset give SKIPPED results, placed after known columns.
    """
    positions = {name: index for index, name in enumerate(dataset.header)}
    ordered: list[tuple[int, int, Evaluation]] = []
    sequence = 0
    for entry in rule_set.columns:
        index = positions.get(entry.column)
        for rule in entry.rules:
            if index is None:
                evaluation = _skipped(entry.column, rule, source)
            else:
                cells = column_cells(dataset, index)
                evaluation = _evaluate_rule(entry.column, rule, cells, source)
            rank = index if index is not None else len(dataset.header)
            ordered.append((rank, sequence, evaluation))
            sequence += 1
    ordered.sort(key=lambda item: (item[0], item[1]))
    return tuple(evaluation for _, _, evaluation in ordered)


def _skipped(column: str, rule: Rule, source: RuleSource) -> Evaluation:
    result = RuleResult(column, rule, rule_kind(rule), source, "SKIPPED", 0, 0, ())
    return Evaluation(result, frozenset())


def _evaluate_rule(
    column: str, rule: Rule, cells: tuple[str, ...], source: RuleSource
) -> Evaluation:
    failing: list[int] = []
    evaluated = 0
    if isinstance(rule, NotNullRule):
        evaluated = len(cells)
        failing = [row for row, cell in _numbered(cells) if is_null(cell)]
    elif isinstance(rule, UniqueRule):
        seen: set[str] = set()
        for row, cell in _numbered(cells):
            if is_null(cell):
                continue
            evaluated += 1
            value = cell.strip()
            if value in seen:
                failing.append(row)
            seen.add(value)
    else:
        check = _validity_check(rule)
        for row, cell in _numbered(cells):
            if is_null(cell):
                continue
            evaluated += 1
            if not check(cell.strip()):
                failing.append(row)
    result = RuleResult(
        column=column,
        rule=rule,
        kind=rule_kind(rule),
        source=source,
        status="FAIL" if failing else "PASS",
        evaluated_count=evaluated,
        failed_count=len(failing),
        failed_rows=tuple(failing[:MAX_LISTED_ROWS]),
    )
    return Evaluation(result, frozenset(failing))


def _numbered(cells: tuple[str, ...]) -> list[tuple[int, str]]:
    """Pair cells with row numbers where the header is row 1."""
    return list(enumerate(cells, start=2))


def _validity_check(rule: Rule) -> Callable[[str], bool]:
    """Return a predicate over a Trimmed_Value; True means the value passes."""
    if isinstance(rule, ValidEmailRule):
        return lambda v: EMAIL_PATTERN.fullmatch(v) is not None
    if isinstance(rule, RegexRule):
        pattern = re.compile(rule.pattern)
        return lambda v: pattern.fullmatch(v) is not None
    if isinstance(rule, InRangeRule):
        return lambda v: _in_range(v, rule.min, rule.max)
    if isinstance(rule, AcceptedValuesRule):
        accepted = frozenset(rule.values)
        return lambda v: v in accepted
    if isinstance(rule, TypeIsRule):
        expected = rule.type
        return lambda v: satisfies(v, expected)
    raise TypeError(f"not a validity rule: {rule.name}")


def _in_range(value: str, low: Decimal | None, high: Decimal | None) -> bool:
    if not is_numeric(value):
        return False
    number = Decimal(value)
    return (low is None or number >= low) and (high is None or number <= high)
