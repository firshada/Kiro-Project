"""Optional MCP adapter: exposes Scrubby as read-only MCP tools for Kiro.

Security: no authentication. It only speaks stdio, so the launching process (e.g. Kiro)
is the only client and no network port is opened. Tools read files inside the injected
workspace root only, never modify them, and never return cell values.

Run: ``python -m profiler.adapters.mcp_server [--root DIR] [--max-bytes N]``
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from profiler.core.dedup import detect_duplicates
from profiler.core.render_json import duplicates_to_dict, report_to_dict, result_to_dict
from profiler.core.report import build_report, file_error
from profiler.core.rules import parse_rule_set
from profiler.core.validation import MAX_BYTES, load_dataset
from profiler.domain import Dataset, ErrorCode, QualityReport, RulesError, RuleSet, ValidationError

READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class PathOutsideRootError(Exception):
    """The requested path is missing, not a file, or escapes the workspace root."""


@dataclass(frozen=True)
class ToolContext:
    """Configuration injected into every tool."""

    root: Path
    max_bytes: int = MAX_BYTES


def read_dataset(ctx: ToolContext, path: str) -> Dataset:
    """Resolve ``path`` inside the root, enforce the size limit, and load the Dataset.

    Raises:
        PathOutsideRootError: if the path escapes the root or is not a regular file.
        ValidationError: for any Upload_Handler failure.
    """
    root = ctx.root.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise PathOutsideRootError(f"not a file inside the workspace root: {path}")
    if target.stat().st_size > ctx.max_bytes:
        raise ValidationError(ErrorCode.FILE_TOO_LARGE, f"file exceeds {ctx.max_bytes} bytes")
    return load_dataset(target.read_bytes(), max_bytes=ctx.max_bytes)


def _load(ctx: ToolContext, path: str) -> Dataset:
    try:
        return read_dataset(ctx, path)
    except ValidationError as exc:
        raise ToolError(f"{exc.code.value}: {exc.message}") from exc
    except PathOutsideRootError as exc:
        raise ToolError(str(exc)) from exc


def _rules(rules: str | None) -> RuleSet | None:
    try:
        return parse_rule_set(rules) if rules else None
    except RulesError as exc:
        raise ToolError(f"{exc.code}: {exc.message}") from exc


def _report(ctx: ToolContext, path: str, rules: str | None) -> QualityReport:
    rule_set = _rules(rules)
    return build_report(Path(path).name, _load(ctx, path), rule_set)


def validate_dataset(ctx: ToolContext, path: str) -> dict[str, object]:
    """Check a CSV against the ingestion rules; validation errors are returned."""
    try:
        dataset = read_dataset(ctx, path)
    except ValidationError as exc:
        return {"valid": False, **result_to_dict(file_error(Path(path).name, exc))}
    except PathOutsideRootError as exc:
        raise ToolError(str(exc)) from exc
    return {"valid": True, "row_count": len(dataset.rows), "column_count": len(dataset.header)}


def profile_dataset(ctx: ToolContext, path: str) -> dict[str, object]:
    """Return the summary and column profiles of a CSV."""
    report = report_to_dict(_report(ctx, path, None))
    return {
        "dataset": report["dataset"],
        "summary": report["summary"],
        "columns": report["columns"],
    }


def check_duplicates(
    ctx: ToolContext, path: str, business_key: list[str] | None = None
) -> dict[str, object]:
    """Count duplicate records by business key, or whole row when no key is given."""
    key = tuple(business_key) if business_key else None
    return duplicates_to_dict(detect_duplicates(_load(ctx, path), key))


def quality_report(ctx: ToolContext, path: str, rules: str | None = None) -> dict[str, object]:
    """Return the full quality report; ``rules`` is optional Rule_Set JSON."""
    return report_to_dict(_report(ctx, path, rules))


def build_server(ctx: ToolContext) -> MCPServer:
    """Create the MCP server with all tools bound to ``ctx``."""
    server: MCPServer = MCPServer(
        name="scrubby",
        instructions=(
            "Data-quality tools for CSV files in the workspace. Paths are relative to the "
            "workspace root. Call validate_dataset first when a file may be malformed."
        ),
    )

    @server.tool(name="validate_dataset", annotations=READ_ONLY)
    def validate_dataset_tool(path: str) -> dict[str, object]:
        """Validate a CSV file: size, UTF-8, RFC 4180 quoting, header, row widths."""
        return validate_dataset(ctx, path)

    @server.tool(name="profile_dataset", annotations=READ_ONLY)
    def profile_dataset_tool(path: str) -> dict[str, object]:
        """Profile a CSV: per-column type, null %, unique %, min/max, invalid counts."""
        return profile_dataset(ctx, path)

    @server.tool(name="check_duplicates", annotations=READ_ONLY)
    def check_duplicates_tool(
        path: str, business_key: list[str] | None = None
    ) -> dict[str, object]:
        """Count duplicate records by business key columns, or whole rows if omitted."""
        return check_duplicates(ctx, path, business_key)

    @server.tool(name="quality_report", annotations=READ_ONLY)
    def quality_report_tool(path: str, rules: str | None = None) -> dict[str, object]:
        """Full quality report: score 0-100, dimensions, rule results, duplicates.

        ``rules`` is optional Rule_Set JSON; without it, rules are suggested.
        """
        return quality_report(ctx, path, rules)

    return server


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and serve over stdio."""
    parser = argparse.ArgumentParser(prog="scrubby-mcp")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="workspace root")
    parser.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    args = parser.parse_args(argv)
    build_server(ToolContext(root=args.root, max_bytes=args.max_bytes)).run("stdio")


if __name__ == "__main__":
    main()
