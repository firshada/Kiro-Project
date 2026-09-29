"""Scrubby command-line adapter (Req 6.10).

Usage: ``python -m profiler FILE [FILE ...] [--rules rules.json] [--format json|html]
[--out reports] [--stdout]``

Exit codes: 0 all files valid, 1 at least one file failed validation, 2 usage or rules error.
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from profiler.core.render_html import to_html
from profiler.core.render_json import to_json
from profiler.core.report import file_error, process_file
from profiler.core.rules import parse_rule_set
from profiler.core.validation import MAX_BYTES
from profiler.domain import ErrorCode, FileError, FileResult, RulesError, RuleSet, ValidationError


def _today_utc() -> date:
    return datetime.now(UTC).date()


def report_path(out_dir: Path, day: date, extension: str) -> Path:
    """Return ``quality-report-YYYY-MM-DD.<ext>``, adding -2, -3, ... to avoid overwriting."""
    stem = f"quality-report-{day.isoformat()}"
    candidate = out_dir / f"{stem}.{extension}"
    suffix = 2
    while candidate.exists():
        candidate = out_dir / f"{stem}-{suffix}.{extension}"
        suffix += 1
    return candidate


def _read(path: Path, rule_set: RuleSet | None) -> FileResult:
    if path.stat().st_size > MAX_BYTES:  # Req 1.3: reject before reading
        error = ValidationError(ErrorCode.FILE_TOO_LARGE, f"file exceeds {MAX_BYTES} bytes")
        return file_error(path.name, error)
    return process_file(path.name, path.read_bytes(), rule_set)


def main(argv: Sequence[str] | None = None, *, today: Callable[[], date] = _today_utc) -> int:
    """Run the CLI and return the exit code."""
    parser = argparse.ArgumentParser(prog="python -m profiler", description="Scrubby reports")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--rules", type=Path, help="Rule_Set JSON file")
    parser.add_argument("--format", choices=("json", "html"), default="json")
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--stdout", action="store_true", help="print instead of writing a file")
    args = parser.parse_args(argv)

    missing = [str(p) for p in args.files if not p.is_file()]
    if missing:
        sys.stderr.write(f"not a file: {', '.join(missing)}\n")
        return 2
    try:
        rule_set = parse_rule_set(args.rules.read_bytes()) if args.rules else None
    except (RulesError, OSError) as exc:
        sys.stderr.write(f"INVALID_RULES: {exc}\n")
        return 2

    results = [_read(path, rule_set) for path in args.files]
    body = to_html(results) if args.format == "html" else to_json(results)
    if args.stdout:
        sys.stdout.buffer.write(body)
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        target = report_path(args.out, today(), args.format)
        with target.open("xb") as handle:  # "x" never overwrites
            handle.write(body)
        sys.stdout.write(f"{target}\n")
    return 1 if any(isinstance(r, FileError) for r in results) else 0
