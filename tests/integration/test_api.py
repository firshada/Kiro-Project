"""Integration tests for the Scrubby HTTP API (Req 7)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from profiler.adapters.api import create_app, safe_name

FIXTURES = Path(__file__).parent.parent / "fixtures"
CLIENT = TestClient(create_app())


def _file(name: str) -> tuple[str, tuple[str, bytes, str]]:
    return ("files", (name, (FIXTURES / name).read_bytes(), "text/csv"))


def test_health() -> None:
    response = CLIENT.get("/health")

    assert (response.status_code, response.json()) == (200, {"status": "ok"})


def test_reports_multi_file_with_one_bad_file() -> None:
    response = CLIENT.post(
        "/v1/reports",
        files=[_file("customers.csv"), _file("row_mismatch.csv"), _file("products.csv")],
    )

    reports = response.json()["reports"]
    assert response.status_code == 200
    assert [r["dataset"] for r in reports] == ["customers.csv", "row_mismatch.csv", "products.csv"]
    assert reports[1]["error"]["code"] == "ROW_LENGTH_MISMATCH"
    assert "score" in reports[0] and "score" in reports[2]


def test_reports_with_rules() -> None:
    rules = (FIXTURES / "rules.json").read_text(encoding="utf-8")

    response = CLIENT.post("/v1/reports", files=[_file("customers.csv")], data={"rules": rules})

    report = response.json()["reports"][0]
    assert report["duplicates"]["key"] == ["customer_id"]
    assert {r["source"] for r in report["rules"]} == {"user"}


def test_reports_html() -> None:
    response = CLIENT.post("/v1/reports?format=html", files=[_file("customers.csv")])

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "<!DOCTYPE html>" in response.text


@pytest.mark.parametrize(
    ("kwargs", "status", "code"),
    [
        ({"files": []}, 422, "NO_FILES"),
        ({"files": [_file("products.csv")] * 11}, 422, "TOO_MANY_FILES"),
        ({"files": [_file("products.csv")], "data": {"rules": "{bad"}}, 422, "INVALID_RULES"),
    ],
)
def test_reports_request_errors(kwargs: dict[str, object], status: int, code: str) -> None:
    response = CLIENT.post("/v1/reports", **kwargs)  # type: ignore[arg-type]

    assert (response.status_code, response.json()["code"]) == (status, code)


def test_reports_unknown_format() -> None:
    response = CLIENT.post("/v1/reports?format=xml", files=[_file("products.csv")])

    assert (response.status_code, response.json()["code"]) == (422, "INVALID_FORMAT_PARAM")


def test_reports_file_too_large_is_not_parsed() -> None:
    client = TestClient(create_app(max_bytes=10))

    response = client.post("/v1/reports", files=[_file("products.csv")])

    assert response.json()["reports"][0]["error"]["code"] == "FILE_TOO_LARGE"


def test_reports_request_too_large() -> None:
    client = TestClient(create_app(max_request_bytes=100))

    response = client.post("/v1/reports", files=[_file("customers.csv")])

    assert (response.status_code, response.json()["code"]) == (413, "REQUEST_TOO_LARGE")


def test_reports_internal_error_is_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: object, **__: object) -> object:
        raise RuntimeError("secret detail")

    monkeypatch.setattr("profiler.adapters.api.process_file", boom)
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post("/v1/reports", files=[_file("products.csv")])

    assert response.status_code == 500
    assert response.json() == {"code": "INTERNAL_ERROR", "message": "internal error"}


def test_reports_are_deterministic() -> None:
    first = CLIENT.post("/v1/reports", files=[_file("transactions.csv")]).content
    second = CLIENT.post("/v1/reports", files=[_file("transactions.csv")]).content

    assert first == second


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("a/b/c.csv", "c.csv"), ("C:\\x\\d.csv", "d.csv"), ("", "upload.csv"), (None, "upload.csv")],
)
def test_safe_name_strips_directories(raw: str | None, expected: str) -> None:
    assert safe_name(raw) == expected
