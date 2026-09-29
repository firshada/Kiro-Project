"""Integration tests for the optional MCP adapter."""

import asyncio
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from profiler.adapters.mcp_server import (
    ToolContext,
    build_server,
    check_duplicates,
    profile_dataset,
    quality_report,
    validate_dataset,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"
CTX = ToolContext(root=FIXTURES)


def test_validate_dataset_valid_and_invalid() -> None:
    assert validate_dataset(CTX, "products.csv") == {
        "valid": True,
        "row_count": 4,
        "column_count": 4,
    }
    invalid = validate_dataset(CTX, "duplicate_header.csv")
    assert invalid["valid"] is False
    assert invalid["error"] == {
        "code": "INVALID_HEADER",
        "message": "empty or duplicate column names at positions [1, 3, 4]",
        "line": None,
        "positions": [1, 3, 4],
        "row_number": None,
    }


def test_profile_dataset_returns_summary_and_columns() -> None:
    result = profile_dataset(CTX, "products.csv")

    assert list(result) == ["dataset", "summary", "columns"]


def test_check_duplicates_by_business_key() -> None:
    result = check_duplicates(CTX, "transactions.csv", ["transaction_id"])

    assert (result["key"], result["duplicate_records"], result["duplicate_rows"]) == (
        ["transaction_id"],
        1,
        [5],
    )


def test_quality_report_with_rules_and_bad_rules() -> None:
    rules = (FIXTURES / "rules.json").read_text(encoding="utf-8")

    assert quality_report(CTX, "customers.csv", rules)["dataset"] == "customers.csv"
    with pytest.raises(ToolError, match="INVALID_RULES"):
        quality_report(CTX, "customers.csv", "{bad")


@pytest.mark.parametrize("path", ["../unit/test_rules.py", "missing.csv", ".", "/etc/passwd"])
def test_tools_reject_paths_outside_root(path: str) -> None:
    with pytest.raises(ToolError, match="not a file inside the workspace root"):
        check_duplicates(CTX, path)


def test_tools_raise_tool_error_on_invalid_dataset() -> None:
    with pytest.raises(ToolError, match="ROW_LENGTH_MISMATCH"):
        quality_report(CTX, "row_mismatch.csv")


def test_server_lists_read_only_tools() -> None:
    tools = asyncio.run(build_server(CTX).list_tools())

    assert sorted(t.name for t in tools) == [
        "check_duplicates",
        "profile_dataset",
        "quality_report",
        "validate_dataset",
    ]
    assert all(t.annotations is not None and t.annotations.read_only_hint for t in tools)
