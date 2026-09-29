"""Example-based tests for the Profiler (Req 2)."""

from profiler.core.profiling import null_cell_count, profile_columns
from profiler.domain import Dataset


def test_profile_columns_trimmed_uniques_are_case_sensitive() -> None:
    dataset = Dataset(header=("v",), rows=((" Abc",), ("Abc",), ("abc",)))

    column = profile_columns(dataset)[0]

    assert (column.unique_count, column.unique_pct) == (2, 66.7)


def test_profile_columns_all_null_column() -> None:
    dataset = Dataset(header=("v",), rows=(("",), ("  ",)))

    column = profile_columns(dataset)[0]

    assert (column.null_count, column.null_pct, column.unique_pct) == (2, 100.0, 0.0)
    assert column.inferred_type == "null"


def test_profile_columns_zero_rows() -> None:
    column = profile_columns(Dataset(header=("a",), rows=()))[0]

    assert (column.null_count, column.null_pct, column.unique_count) == (0, 0.0, 0)


def test_profile_columns_numeric_min_max_by_value() -> None:
    dataset = Dataset(header=("n",), rows=(("10",), (" 9.5 ",), ("1e3",), ("-2",), ("1e3",)))

    column = profile_columns(dataset)[0]

    assert (column.inferred_type, column.min, column.max) == ("float", "-2", "1e3")


def test_profile_columns_min_max_ties_keep_first() -> None:
    dataset = Dataset(header=("n",), rows=(("1.0",), ("1",)))

    column = profile_columns(dataset)[0]

    assert (column.min, column.max) == ("1.0", "1.0")


def test_profile_columns_string_has_no_min_max() -> None:
    column = profile_columns(Dataset(header=("s",), rows=(("b",), ("a",))))[0]

    assert (column.min, column.max) == (None, None)


def test_profile_columns_uses_invalid_counts() -> None:
    column = profile_columns(Dataset(header=("s",), rows=(("b",),)), {"s": 1})[0]

    assert column.invalid_count == 1


def test_null_cell_count_counts_whitespace_not_na() -> None:
    dataset = Dataset(header=("a", "b"), rows=(("", "NA"), (" ", "null")))

    assert null_cell_count(dataset) == 2
