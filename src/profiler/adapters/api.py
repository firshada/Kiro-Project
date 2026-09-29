"""Scrubby HTTP adapter (Req 7).

SECURITY: this API has NO authentication or rate limiting in v1. Do not expose it
publicly; put it behind an authenticating reverse proxy or add an API-key
dependency first. User-supplied ``regex`` rules run on the server; patterns are
capped at 200 characters, but a pathological pattern can still be slow (ReDoS).

Run: ``uv run uvicorn profiler.adapters.api:app``
"""

import logging
import re
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from profiler.core.render_html import to_html
from profiler.core.render_json import to_json
from profiler.core.report import file_error, process_file
from profiler.core.rules import parse_rule_set
from profiler.core.validation import MAX_BYTES
from profiler.domain import ErrorCode, FileResult, RulesError, ValidationError

MAX_FILES = 10
MAX_REQUEST_BYTES = MAX_FILES * MAX_BYTES + 1_048_576  # files plus form overhead (Req 7.4)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

logger = logging.getLogger(__name__)


class _BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    """Reject bodies over ``max_bytes`` with 413 before they are parsed (Req 7.4)."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await _too_large()(scope, receive, send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.max_bytes:
                raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await _too_large()(scope, receive, send)


def _too_large() -> JSONResponse:
    return _error(413, "REQUEST_TOO_LARGE", "request body is too large")


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


def safe_name(filename: str | None) -> str:
    """Base name only, no directories (Req 6.1); never empty."""
    return re.split(r"[\\/]", filename or "")[-1] or "upload.csv"


def create_app(
    *, max_bytes: int = MAX_BYTES, max_request_bytes: int = MAX_REQUEST_BYTES
) -> FastAPI:
    """Create the FastAPI app with injectable limits."""
    app = FastAPI(title="Scrubby", version="1.0.0")

    @app.exception_handler(RequestValidationError)
    async def _invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(422, "INVALID_REQUEST", "request is missing or has invalid fields")

    @app.exception_handler(Exception)
    async def _internal(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")  # server-side only; never sent to clients
        return _error(500, "INTERNAL_ERROR", "internal error")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/reports", response_model=None)
    async def create_reports(
        files: list[UploadFile] | None = File(default=None),  # noqa: B008
        rules: str | None = Form(default=None),
        format: str = Query(default="json"),
    ) -> Response:
        if format not in ("json", "html"):
            return _error(422, "INVALID_FORMAT_PARAM", "format must be 'json' or 'html'")
        uploads = files or []
        if not uploads:
            return _error(422, "NO_FILES", "upload at least one file in 'files'")
        if len(uploads) > MAX_FILES:
            return _error(422, "TOO_MANY_FILES", f"at most {MAX_FILES} files per request")
        try:
            rule_set = parse_rule_set(rules) if rules else None  # before any file (Req 3.2)
        except RulesError as exc:
            return _error(422, exc.code, exc.message)

        results: list[FileResult] = []
        for upload in uploads:
            name = safe_name(upload.filename)
            if upload.size is not None and upload.size > max_bytes:  # Req 1.3: never parsed
                too_large = ValidationError(
                    ErrorCode.FILE_TOO_LARGE, f"file exceeds {max_bytes} bytes"
                )
                results.append(file_error(name, too_large))
                continue
            data = await upload.read()
            results.append(process_file(name, data, rule_set, max_bytes=max_bytes))

        if format == "html":
            return Response(to_html(results), media_type="text/html; charset=utf-8")
        return Response(to_json(results), media_type="application/json")

    app.add_middleware(BodyLimitMiddleware, max_bytes=max_request_bytes)
    return app


app = create_app()
