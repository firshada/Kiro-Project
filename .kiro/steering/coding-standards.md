---
inclusion: always
---

# Coding Standards

## General

- Target Python 3.12. Use type hints on every function signature; code must pass `mypy --strict`.
- Format and lint with Ruff. No unused imports, variables, or commented-out code.
- Prefer small, pure functions. Keep functions focused on one responsibility.
- Prefer immutable data (`@dataclass(frozen=True)`, tuples, frozen Pydantic models).

## Naming

- `snake_case` for functions, variables, and modules; `PascalCase` for classes; `UPPER_SNAKE_CASE` for constants.
- Use names from the spec glossary (Profiler, Upload_Handler, Serializer, Parser, Dataset, Profile_Result) in code and docstrings.

## Architecture

- `core` must not import FastAPI, perform file/network I/O, or read environment variables.
- Adapters handle I/O, map domain errors to transport responses, and contain no business rules.
- Inject limits and configuration (e.g. `max_bytes`) as parameters rather than reading globals.

## Error Handling

- Raise typed domain errors (`ValidationError`, `ProfileParseError`) with a machine-readable code.
- Never swallow exceptions silently. Never leak file contents or stack traces in API responses.
- Validate all external input at the adapter/core boundary.

## Security

- Never hardcode secrets or credentials; read them from environment variables in adapters only.
- Flag any endpoint without authentication in its module docstring.
- Pin exact dependency versions; avoid unmaintained or unknown packages.

## Documentation

- Public functions get a concise docstring stating purpose, inputs, outputs, and raised errors.
- Reference requirement IDs (e.g. `Req 4.7`) in comments where logic implements a specific rule.