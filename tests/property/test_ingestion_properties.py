"""Hypothesis property tests for the Upload_Handler (Req 1)."""

import csv
import io

from hypothesis import given, settings
from hypothesis import strategies as st

from profiler.core.validation import load_dataset
from profiler.domain import Dataset, ErrorCode, ValidationError
from tests.strategies import datasets


def encode(header: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> bytes:
    """Write rows as RFC 4180 CSV bytes."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _error(data: bytes) -> ValidationError:
    try:
        load_dataset(data)
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")


# Feature: dataset-profiling, Property 1: Valid datasets load unchanged
@settings(max_examples=200)
@given(dataset=datasets())
def test_load_dataset_round_trips_valid_datasets(dataset: Dataset) -> None:
    assert load_dataset(encode(dataset.header, dataset.rows)) == dataset


# Feature: dataset-profiling, Property 2: Header errors report all problem positions
@settings(max_examples=200)
@given(
    header=st.lists(
        st.sampled_from(("a", "b", "A", "", " ", "\t", "c d")), min_size=1, max_size=6
    ).map(tuple)
)
def test_load_dataset_header_positions_match_reference(header: tuple[str, ...]) -> None:
    expected = [
        i + 1 for i, name in enumerate(header) if name.strip() == "" or header.count(name) > 1
    ]
    if header == ("",):
        return  # a single empty field is indistinguishable from a blank line
    if not expected:
        assert load_dataset(encode(header, ())).header == header
        return

    error = _error(encode(header, ()))

    assert (error.code, list(error.positions)) == (ErrorCode.INVALID_HEADER, expected)


# Feature: dataset-profiling, Property 3: First row-length mismatch is reported
@settings(max_examples=200)
@given(data=st.data(), dataset=datasets(min_rows=1))
def test_load_dataset_reports_first_mismatch(data: st.DataObject, dataset: Dataset) -> None:
    indices = data.draw(st.sets(st.integers(0, len(dataset.rows) - 1), min_size=1), label="mutated")
    rows = tuple((*row, "extra") if i in indices else row for i, row in enumerate(dataset.rows))

    error = _error(encode(dataset.header, rows))

    assert (error.code, error.row_number) == (ErrorCode.ROW_LENGTH_MISMATCH, min(indices) + 2)
