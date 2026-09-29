"""Example-based tests for type inference (Req 4)."""

import pytest

from profiler.core.type_inference import infer_type
from profiler.domain import InferredType


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([], "null"),
        (["", "  "], "null"),
        (["true", " FALSE ", ""], "boolean"),
        (["1", "0"], "integer"),
        (["yes", "no"], "string"),
        (["+1", "-20", " 3 "], "integer"),
        (["1", "2.5"], "float"),
        (["1e3", ".5", "7."], "float"),
        (["NaN"], "string"),
        (["Infinity"], "string"),
        (["0x1F"], "string"),
        (["1,000"], "string"),
        (["١٢"], "string"),
        (["2024-02-29", "2024-03-01T10:30", "2024-03-01T10:30:59.123+05:30"], "datetime"),
        (["2023-02-30"], "string"),
        (["2024-13-01"], "string"),
        (["2024-01-01T24:00"], "string"),
        (["2024-01-01T10:00+24:00"], "string"),
        (["2024-01-01", "1"], "string"),
    ],
)
def test_infer_type_examples(values: list[str], expected: InferredType) -> None:
    assert infer_type(values) == expected
