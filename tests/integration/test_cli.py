"""Integration tests for the CLI adapter (Req 6.10)."""

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from profiler.adapters.cli import main

FIXTURES = Path(__file__).parent.parent / "fixtures"
DAY = date(2026, 9, 28)


def test_cli_writes_dated_report_without_overwriting(tmp_path: Path) -> None:
    args = [str(FIXTURES / "products.csv"), "--format", "html", "--out", str(tmp_path)]

    first = main(args, today=lambda: DAY)
    second = main(args, today=lambda: DAY)

    assert (first, second) == (0, 0)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "quality-report-2026-09-28-2.html",
        "quality-report-2026-09-28.html",
    ]


def test_cli_stdout_json_and_exit_code_for_bad_file(
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    code = main([str(FIXTURES / "products.csv"), str(FIXTURES / "bad_quote.csv"), "--stdout"])

    reports = json.loads(capsysbinary.readouterr().out)["reports"]
    assert code == 1
    assert reports[1]["error"]["code"] == "INVALID_FORMAT"


def test_cli_invalid_rules_exit_2(tmp_path: Path) -> None:
    rules = tmp_path / "r.json"
    rules.write_text('{"columns":[{"column":"a","rules":["nope"]}]}', encoding="utf-8")

    assert main([str(FIXTURES / "products.csv"), "--rules", str(rules), "--stdout"]) == 2


def test_cli_missing_file_exit_2(tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope.csv"), "--stdout"]) == 2


def test_cli_rules_file(tmp_path: Path, capsysbinary: pytest.CaptureFixture[bytes]) -> None:
    shutil.copy(FIXTURES / "customers.csv", tmp_path / "customers.csv")

    main([str(tmp_path / "customers.csv"), "--rules", str(FIXTURES / "rules.json"), "--stdout"])

    report = json.loads(capsysbinary.readouterr().out)["reports"][0]
    assert report["dataset"] == "customers.csv"
    assert report["duplicates"]["key"] == ["customer_id"]
