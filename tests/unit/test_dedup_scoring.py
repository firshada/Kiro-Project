"""Example-based tests for the Deduplicator and Scorer (Req 4, 5)."""

from fractions import Fraction

from profiler.core.dedup import detect_duplicates
from profiler.core.rules import evaluate, parse_rule_set
from profiler.core.scoring import compute_dimensions
from profiler.domain import Dataset

ROWS = (("1", "a"), ("1", "b"), (" 1", "a"), ("2", "a"), ("1", "a"))
DATASET = Dataset(header=("id", "v"), rows=ROWS)


def test_detect_duplicates_whole_row_is_raw_and_exact() -> None:
    result = detect_duplicates(DATASET)

    assert (result.key, result.key_status, result.duplicate_records) == (None, "WHOLE_ROW", 1)
    assert result.duplicate_rows == (6,)


def test_detect_duplicates_business_key_trims() -> None:
    result = detect_duplicates(DATASET, ("id",))

    assert (result.unique_records, result.duplicate_records) == (2, 3)
    assert result.duplicate_rows == (3, 4, 6)


def test_detect_duplicates_missing_key_falls_back() -> None:
    result = detect_duplicates(DATASET, ("id", "nope"))

    assert (result.key, result.key_status, result.missing_columns) == (
        None,
        "MISSING_COLUMNS",
        ("nope",),
    )
    assert result.duplicate_records == 1


def test_detect_duplicates_zero_rows() -> None:
    result = detect_duplicates(Dataset(header=("a",), rows=()), ("a",))

    assert (result.total_records, result.unique_records, result.duplicate_records) == (0, 0, 0)


def test_compute_dimensions_empty_dataset_is_perfect() -> None:
    dataset = Dataset(header=("a",), rows=())

    exact = compute_dimensions(dataset, (), detect_duplicates(dataset))

    assert exact.score() == 1


def test_compute_dimensions_formula() -> None:
    dataset = Dataset(
        header=("id", "email", "d"),
        rows=(
            ("1", "a@x.io", "2024-01-01"),
            ("2", "bad", "N/A"),
            ("2", "", "2024-01-02"),
            ("3", "c@x.io", "2024-01-03"),
        ),
    )
    rules = parse_rule_set('{"columns":[{"column":"email","rules":["valid_email","not_null"]}]}')
    results = [e.result for e in evaluate(dataset, rules, "user")]

    exact = compute_dimensions(dataset, results, detect_duplicates(dataset, ("id",)))

    assert exact.completeness == Fraction(11, 12)
    assert exact.uniqueness == Fraction(3, 4)
    assert exact.validity == Fraction(2, 3)  # not_null is completeness, not validity
    assert exact.consistency == Fraction(10, 11)  # "N/A" is not a datetime
    assert (
        exact.score() == (Fraction(11, 12) + Fraction(3, 4) + Fraction(2, 3) + Fraction(10, 11)) / 4
    )


def test_compute_dimensions_integers_count_as_float_in_float_column() -> None:
    dataset = Dataset(header=("n",), rows=(("1",), ("2",), ("2.5",)))

    exact = compute_dimensions(dataset, (), detect_duplicates(dataset))

    assert exact.consistency == 1


def test_compute_dimensions_dominant_type_tie_uses_order() -> None:
    dataset = Dataset(header=("n",), rows=(("true",), ("x",)))

    exact = compute_dimensions(dataset, (), detect_duplicates(dataset))

    assert exact.consistency == Fraction(1, 2)
