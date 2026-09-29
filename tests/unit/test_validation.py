"""Example-based tests for the Upload_Handler (Req 1)."""

import pytest

from profiler.core.validation import load_dataset
from profiler.domain import ErrorCode, ValidationError


def _error(data: bytes, max_bytes: int = 1_000) -> ValidationError:
    with pytest.raises(ValidationError) as info:
        load_dataset(data, max_bytes=max_bytes)
    return info.value


def test_load_dataset_keeps_raw_cells() -> None:
    dataset = load_dataset(b'a,b\r\n" x ",NA\r\n', max_bytes=1_000)

    assert dataset.header == ("a", "b")
    assert dataset.rows == ((" x ", "NA"),)


def test_load_dataset_header_only_is_valid() -> None:
    dataset = load_dataset(b"a,b\n")

    assert dataset.rows == ()


def test_load_dataset_too_large() -> None:
    assert _error(b"a\n1\n", max_bytes=3).code is ErrorCode.FILE_TOO_LARGE


def test_load_dataset_empty_file() -> None:
    assert _error(b"").code is ErrorCode.EMPTY_DATASET


def test_load_dataset_blank_header_line() -> None:
    assert _error(b"\n").code is ErrorCode.EMPTY_DATASET


def test_load_dataset_invalid_utf8_reports_line() -> None:
    error = _error(b"a\nok\n\xff\n")

    assert (error.code, error.line) == (ErrorCode.INVALID_FORMAT, 3)


def test_load_dataset_bad_quoting_is_invalid_format() -> None:
    assert _error(b'a,b\n1,"x"y\n').code is ErrorCode.INVALID_FORMAT


def test_load_dataset_header_positions_empty_and_duplicate() -> None:
    error = _error(b"id,name,id, \n1,2,3,4\n")

    assert (error.code, error.positions) == (ErrorCode.INVALID_HEADER, (1, 3, 4))


def test_load_dataset_header_duplicates_are_case_sensitive() -> None:
    dataset = load_dataset(b"Id,id\n1,2\n")

    assert dataset.header == ("Id", "id")


def test_load_dataset_first_row_mismatch() -> None:
    error = _error(b"a,b\n1,2\n3\n4,5,6\n")

    assert (error.code, error.row_number) == (ErrorCode.ROW_LENGTH_MISMATCH, 3)


def test_load_dataset_format_error_wins_over_header_error() -> None:
    assert _error(b'a,a\n1,"x"y\n').code is ErrorCode.INVALID_FORMAT


def test_load_dataset_size_wins_over_everything() -> None:
    assert _error(b'a,a\n1,"x"y\n', max_bytes=2).code is ErrorCode.FILE_TOO_LARGE
