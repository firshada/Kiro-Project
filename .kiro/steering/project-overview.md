---
inclusion: always
---

# Project Overview

## Purpose

Scrubby: a stateless data quality service. Users upload one or more CSV files (with optional validation rules), and each gets a deterministic quality report as JSON or HTML.

- F1 Ingestion: strict CSV validation, several files per request
- F2 Profiling: per-column type, null %, unique %, min/max, invalid count
- F3 Validation rules: user-supplied or suggested; PASS/FAIL/SKIPPED with failing counts
- F4 Duplicate detection: by business key or whole row
- F5 Quality score: 0-100 from completeness, uniqueness, validity, and consistency (equal weights)
- F6 Quality report: JSON or self-contained HTML; no database, nothing stored

Spec: #[[file:.kiro/specs/dataset-profiling/requirements.md]]

## Stack (free and open source only)

- Python 3.12
- FastAPI + Uvicorn (HTTP adapter), CLI via `python -m profiler`
- Pydantic v2 for result models
- uv for dependency management (exact pinned versions, committed lockfile)
- Ruff, mypy `--strict`, pytest, Hypothesis
- GitHub Actions (free tier) for CI

## Layout

- `src/profiler/domain/` - immutable data types and error codes
- `src/profiler/core/` - pure business logic (validation, type inference, profiling, rules, dedup, scoring, rendering); no I/O
- `src/profiler/adapters/` - FastAPI app and CLI; thin wrappers over `core`
- `tests/` - unit, property, and integration tests

Dependencies point inward: `adapters` -> `core` -> `domain`.

## Commands

- Install: `uv sync`
- Lint: `uv run ruff check .` and `uv run ruff format --check .`
- Type check: `uv run mypy --strict src`
- Test: `uv run pytest`