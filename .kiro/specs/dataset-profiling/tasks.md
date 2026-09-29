# Implementation Plan: Scrubby

## Overview

Extend the existing pure core (validation, type inference, profiling) with a Rule_Engine, business-key deduplication, a four-dimension Scorer, and JSON/HTML reporting. Then add the FastAPI and CLI adapters. Items marked `(reuse)` already exist and only need changes.

## Tasks

- [x] 1. Domain and shared utilities
  - [x] 1.1 Update domain models
    - `domain/report.py`: ColumnProfile (with pct, min/max, invalid_count), RuleResult, DuplicateResult, Dimensions, Summary, QualityReport, FileError
    - `domain/rules.py`: Rule discriminated union, ColumnRules, RuleSet; `domain/errors.py`: add `RulesError`/`INVALID_RULES`
    - Remove the old `domain/models.py` ProfileResult once nothing uses it
    - _Requirements: 2.2, 3.1, 3.5, 4.3, 6.1_
  - [x] 1.2 Implement `core/percent.py` `to_percentage` (Fraction → 1 dp, half-even, local Decimal context)
    - _Requirements: Glossary "Percentage", 5.4_
  - [x]* 1.3 Unit tests for `to_percentage` rounding examples

- [x] 2. Upload_Handler (reuse, done)
  - [x] 2.1 `load_dataset` with Req 1.3–1.9, 1.11
  - [x]* 2.2 Property 1: Valid datasets load unchanged
  - [x]* 2.3 Property 2: Header errors report all problem positions
  - [x]* 2.4 Property 3: First row-length mismatch is reported
  - [ ]* 2.5 Property 4: Error precedence

- [x] 3. Type inference (reuse)
  - [x] 3.1 Add `value_type` and `satisfies` to `core/type_inference.py`
    - _Requirements: 2.7, 2.8, 3.3 (`type_is`), 5.1 (consistency)_
  - [ ]* 3.2 Property 6: Type inference matches a reference classifier

- [x] 4. Profiler (reuse)
  - [x] 4.1 Extend `core/profiling.py` with null_pct, unique_pct, min/max (Decimal compare), invalid_count input
    - _Requirements: 2.1–2.6_
  - [x]* 4.2 Property 5: Column profile matches a reference model

- [x] 5. Rule_Engine
  - [x] 5.1 `parse_rule_set` with `INVALID_RULES` mapping (unknown rule, bad params, pattern ≤ 200 chars, min ≤ max, unknown fields)
    - _Requirements: 3.1, 3.2_
  - [x] 5.2 Rule predicates and `evaluate` (PASS/FAIL/SKIPPED, failed_rows ≤ 10, ordering)
    - _Requirements: 3.3, 3.4, 3.5, 3.7_
  - [x] 5.3 `suggest_rules` from the profile
    - _Requirements: 3.6_
  - [x]* 5.4 Property 7: Rule results match reference predicates
  - [x]* 5.5 Unit tests: each rule PASS/FAIL, SKIPPED columns, suggested-rule matrix, INVALID_RULES cases

- [x] 6. Deduplicator (reuse)
  - [x] 6.1 Replace `core/quality.detect_duplicates` with `core/dedup.py` supporting a business key and a missing-column fallback
    - _Requirements: 4.1–4.5_
  - [x]* 6.2 Property 8: Duplicate invariants

- [x] 7. Scorer (reuse)
  - [x] 7.1 Replace `core/quality.calculate_quality_score` with `core/scoring.py` (four dimensions, equal weights, Dominant_Type)
    - _Requirements: 5.1–5.4_
  - [x]* 7.2 Property 9: Score bounds and reference formula
  - [x]* 7.3 Property 10: Adding a clean record never lowers completeness, uniqueness, or validity

- [x] 8. Checkpoint: ensure all tests pass, ask the user if questions arise

- [x] 9. Reporter
  - [x] 9.1 `core/report.py` `build_report` orchestration, issues and potential_issues
    - _Requirements: 2.1, 6.1–6.4_
  - [x] 9.2 `core/render_json.py`
    - _Requirements: 6.5, 6.9_
  - [x] 9.3 `core/render_html.py` (self-contained, escaped, accessible tables)
    - _Requirements: 6.6–6.9_
  - [x]* 9.4 Property 11: Report determinism
  - [x]* 9.5 Property 12: HTML escaping

- [x] 10. Adapters
  - [x] 10.1 FastAPI `adapters/api.py`: `POST /v1/reports`, `GET /health`, limits, error mapping, no-auth docstring; add pinned `fastapi`, `uvicorn`, `python-multipart`, `httpx` (tests)
    - _Requirements: 1.1, 1.2, 1.10, 7.1–7.7_
  - [x] 10.2 CLI `adapters/cli.py` + `__main__.py`, dated report names, no overwrite
    - _Requirements: 6.10_
  - [x] 10.3 Update the optional MCP adapter and the `data-engineering-power` skills to use `build_report`
  - [x]* 10.4 Integration tests: TestClient (status codes, multi-file with a bad file, HTML, escaping) and CLI
  - [x] 10.5 Fixtures: synthetic `customers.csv`, `transactions.csv`, `products.csv`, and a sample `rules.json`. Ask the user for a real sample first (small, no personal data).

- [x] 11. Quality gates
  - [x] 11.1 Add pinned `pytest-cov`, enforce ≥ 90% on `core`
  - [x] 11.2 `.github/workflows/ci.yml`: ruff check/format, mypy --strict, pytest, two-process determinism diff

- [x] 12. Final checkpoint: ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked `*` are optional for a faster MVP, but the property tests are the main correctness guarantee.
- The earlier `quality.py` (two-dimension score) and its Properties 12–14 are superseded by Properties 8–10 and will be removed in tasks 6.1 and 7.1.
- JSON input is out of scope. CSV only.
