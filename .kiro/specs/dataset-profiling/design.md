# Design Document: Scrubby

## Overview

Scrubby is a stateless service. A request carries one or more CSV files and an optional Rule_Set. Each file goes through a pure pipeline and produces a Quality_Report. The report is rendered as JSON or HTML and returned. Nothing is persisted.

```
bytes ─► Upload_Handler ─► Dataset ─┬─► Profiler ───────┐
                                    ├─► Rule_Engine ────┤
                                    └─► Deduplicator ───┼─► Scorer ─► QualityReport ─► Reporter (JSON | HTML)
```

### Stack (free and open source only)

| Concern | Choice |
|---|---|
| Language | Python 3.12, standard `csv` module (`strict=True`) |
| HTTP | FastAPI + Uvicorn, `python-multipart` for uploads |
| Models | Pydantic v2 (`extra="forbid"`, `strict=True`, `frozen=True`) for the Rule_Set and the report |
| HTML | Standard library `html.escape` and string templates; no template engine or JavaScript |
| Arithmetic | `fractions.Fraction` for all ratios, `decimal.Decimal` for numeric comparison and rounding |
| Tests | pytest, Hypothesis, FastAPI `TestClient` |
| Tooling | uv, Ruff, mypy `--strict`, GitHub Actions |

Design decisions:
- The core is pure. Adapters (FastAPI, CLI, optional MCP) handle I/O, limits, clocks, and file names.
- CSV only. JSON input is out of scope for the MVP.
- Rules are optional. Without a Rule_Set the system suggests rules from the profile, so every upload gets a useful report.
- The report body holds no date. The CLI puts the UTC date in the file name only, which keeps Req 8 intact.
- Several files in a request give one report each, in upload order. A failed file doesn't stop the others.

## Architecture

```
src/profiler/
  domain/
    dataset.py        Dataset (frozen)
    errors.py         ErrorCode, ValidationError, RulesError
    rules.py          Rule models (discriminated union), RuleSet
    report.py         ColumnProfile, RuleResult, DuplicateResult, Dimensions, QualityReport, FileError
  core/
    validation.py     Upload_Handler: load_dataset(data, *, max_bytes) -> Dataset
    type_inference.py value_type(v), satisfies(v, type), infer_type(values)
    profiling.py      Profiler: profile_columns(ds, invalid_counts) -> tuple[ColumnProfile, ...]
    rules.py          Rule_Engine: suggest_rules(ds, columns), evaluate(ds, rule_set, source)
    dedup.py          Deduplicator: detect_duplicates(ds, key) -> DuplicateResult
    scoring.py        Scorer: compute_dimensions(...), score(dimensions)
    percent.py        to_percentage(Fraction) -> float (round-half-even, 1 dp)
    report.py         build_report(name, ds, rule_set) -> QualityReport  (orchestrates the pipeline)
    render_json.py    to_json(reports) -> bytes
    render_html.py    to_html(reports) -> bytes
  adapters/
    api.py            FastAPI app: POST /v1/reports, GET /health
    cli.py, __main__  python -m profiler FILE... [--rules r.json] [--format json|html] [--out reports/]
    mcp_server.py     Optional MCP tools over build_report (kept from the earlier iteration)
```

Dependencies point inward: `adapters` → `core` → `domain`.

## Components

### Upload_Handler (reused)

`load_dataset` is already implemented and tested. Checks run in Req 1.8 order, and the full parse finishes before the header and row checks. Cells stay raw (Req 1.11).

### Type inference (reused, extended)

- `value_type(v) -> ValueType` returns the first match in the order `boolean`, `integer`, `float`, `datetime`, `string` for one Trimmed_Value. It's used for consistency.
- `satisfies(v, t) -> bool` is used by `type_is`. `integer` values satisfy `float`, and everything satisfies `string`.
- `infer_type(values)` is unchanged.

### Profiler

- `null_pct = to_percentage(Fraction(null_count, row_count))`, or 0 when there are no rows.
- `unique_pct = to_percentage(Fraction(unique_count, non_null_count))`, or 0 when there are no non-null cells.
- `min`/`max`: only for `integer` and `float` columns. Compare by `Decimal(trimmed)`. On ties, keep the first occurrence's Trimmed_Value, so `1.0` and `1` give a stable result.
- `invalid_count` comes from the Rule_Engine: the set of failing rows per column over validity rules.

### Rule_Engine

The Rule_Set is a Pydantic model. Each rule is either a bare name (`"not_null"`) or an object with a `name` discriminator:

```python
class RegexRule(BaseModel):      name: Literal["regex"]; pattern: str  # compiled, <= 200 chars
class InRangeRule(BaseModel):    name: Literal["in_range"]; min: Decimal | None; max: Decimal | None
class AcceptedValuesRule(...):   name: Literal["accepted_values"]; values: tuple[str, ...]  # min 1
class TypeIsRule(...):           name: Literal["type_is"]; type: Literal["boolean","integer","float","datetime","string"]
# not_null, unique, valid_email: parameterless
class ColumnRules(BaseModel):    column: str; rules: tuple[Rule, ...]
class RuleSet(BaseModel):        business_key: tuple[str, ...] | None = None; columns: tuple[ColumnRules, ...] = ()
```

- `parse_rule_set(text: bytes) -> RuleSet` raises `RulesError(code=INVALID_RULES, field, reason)`. Pydantic errors are mapped to a single, stable message.
- Each rule becomes a pure predicate over a column: it returns the sorted failing row numbers and the evaluated count. `unique` tracks the first occurrence in a dict.
- ReDoS: Python's `re` has no timeout. We cap pattern length at 200 characters and cells are bounded by the file size. The risk remains for pathological patterns and is documented. The API has no auth in v1, so it must not be exposed publicly as is.
- `suggest_rules(ds, columns)` implements Req 3.6, in header order.

### Deduplicator

`detect_duplicates(ds, key)` builds the key per row: raw tuple when there's no key, and the tuple of trimmed key cells when there is one. A first-seen set gives `unique_records`, and the duplicate row numbers are collected in order. Missing key columns fall back to whole-row comparison and set `key_status` (Req 4.2).

### Scorer

All ratios are `Fraction`. `to_percentage` is only applied for output:

```
completeness = non_null_cells / total_cells
uniqueness   = unique_records / total_records
validity     = Σ(evaluated - failed) / Σ evaluated      over validity rules with status PASS/FAIL
consistency  = Σ_col matches(Dominant_Type) / Σ_col non_null
score        = (completeness + uniqueness + validity + consistency) / 4
```

A zero denominator gives 1 (100%). `to_percentage(f) = float(Decimal(f.numerator) / Decimal(f.denominator)` quantized to `0.1` with `ROUND_HALF_EVEN`), computed in a local `decimal.Context(prec=50)`, so the global context is never used.

Why these four: they map one-to-one to the F5 example, each is a ratio of counts with an obvious meaning, and equal weights avoid arbitrary tuning. The weights are a module constant, so the formula is easy to find and change.

### Reporter

- `QualityReport` field order follows Req 6.1. JSON uses `json.dumps(ensure_ascii=False, separators=(",", ":"), allow_nan=False)` over explicitly ordered dicts.
- HTML is one document per request:
  - `<html lang="en">`, inline `<style>`, a `<section>` per file, and `<table>` elements with `<caption>` and `<th scope>`.
  - Status is shown as text (PASS/FAIL/SKIPPED) plus a color class, never color alone.
  - Every interpolated value goes through `html.escape(value, quote=True)`.

### Scrubby_API

- `POST /v1/reports?format=json|html` takes multipart `files` (1–10) and an optional `rules`.
- An ASGI middleware caps the whole request body (`Content-Length` and streamed bytes) and returns 413 before multipart parsing finishes. Starlette spools each upload to a temporary file. A file whose `size` exceeds `max_bytes` gets `FILE_TOO_LARGE` and is never read or parsed as CSV.
- `rules` is parsed before any file is processed. An error returns 422 `INVALID_RULES`.
- The response is 200 JSON `{"reports": [...]}` or HTML. Other errors: 422 (`NO_FILES`, `TOO_MANY_FILES`, `INVALID_RULES`, `INVALID_FORMAT_PARAM`), 413 (`REQUEST_TOO_LARGE`), and 500 (`INTERNAL_ERROR`, generic).
- `GET /health` returns `{"status":"ok"}`.
- No authentication in v1. It's flagged in the module docstring. Put it behind an authenticating reverse proxy, or add an API-key dependency, before any public deployment.
- The file name in the report is the upload's base name only (no directories) and is escaped in HTML.

### CLI

`python -m profiler customers.csv transactions.csv --rules rules.json --format html --out reports/` writes `reports/quality-report-YYYY-MM-DD.html`. The UTC date is injected by the adapter, and the CLI never overwrites an existing report (Req 6.10). `--stdout` prints instead of writing. The exit code is 0 when every file is valid, 1 when any file failed validation, and 2 for usage or rules errors.

## Data Models (report)

```json
{
  "dataset": "customers.csv",
  "score": 87.4,
  "issues": 61,
  "dimensions": {"completeness": 94.0, "uniqueness": 98.0, "validity": 82.0, "consistency": 89.0},
  "summary": {"row_count": 10000, "column_count": 12, "null_count": 347, "duplicate_count": 29, "potential_issues": 7},
  "columns": [
    {"name": "customer_id", "inferred_type": "integer", "null_count": 0, "null_pct": 0.0,
     "unique_count": 10000, "unique_pct": 100.0, "invalid_count": 0, "min": "10001", "max": "19999"}
  ],
  "rules": [
    {"column": "email", "rule": {"name": "valid_email"}, "source": "user", "status": "FAIL",
     "evaluated_count": 9880, "failed_count": 32, "failed_rows": [14, 88]}
  ],
  "duplicates": {"key": ["customer_id"], "key_status": "OK", "total_records": 10000,
                 "unique_records": 9971, "duplicate_records": 29, "duplicate_rows": [502]}
}
```

## Correctness Properties

### Property 1: Valid datasets load unchanged
For any generated valid header and rows, CSV-encoded, `load_dataset` returns an equal Dataset. **Validates: Req 1.1, 1.9, 1.11**

### Property 2: Header errors report all problem positions
Injected empty or duplicate names give `INVALID_HEADER`, with positions equal to the reference set. **Validates: Req 1.6**

### Property 3: First row-length mismatch is reported
Mutating the widths of random rows gives `ROW_LENGTH_MISMATCH` with the smallest mutated index + 2. **Validates: Req 1.7**

### Property 4: Error precedence
A file built to fail a random subset of checks raises the highest-precedence code. **Validates: Req 1.3–1.8**

### Property 5: Column profile matches a reference model
`null_count`, `unique_count`, the percentages, and `min`/`max` equal a naive reference, with `unique_count <= row_count - null_count`. **Validates: Req 2.1–2.5**

### Property 6: Type inference matches a reference classifier
`infer_type` and `value_type` agree with reference predicates on generated near-misses (NaN, hex, `1,000`, `yes`, 2023-02-30, month 13, padded values). **Validates: Req 2.7, 2.8**

### Property 7: Rule results match reference predicates
For generated columns and rules, `failed_count`, `status`, and the sorted `failed_rows` equal a naive per-row reference, and `failed_count <= evaluated_count`. **Validates: Req 3.3–3.5**

### Property 8: Duplicate invariants
`duplicate_records == total_records - unique_records`, `unique_records <= total_records`, and a first-occurrence reference agrees for both whole-row and business-key modes. **Validates: Req 4.1–4.5**

### Property 9: Score bounds and reference formula
Every dimension and the score are in [0, 100] and equal a reference computed with `Fraction`. **Validates: Req 5.1–5.5**

### Property 10: Clean record never lowers dimensions
Appending a complete record that passes every validity rule and is not a duplicate never lowers completeness, uniqueness, or validity. **Validates: Req 5.6**

### Property 11: Report determinism
Building and rendering (JSON and HTML) twice gives byte-identical output, and the output contains no generated Cell value. **Validates: Req 6.5, 6.9, 8.1, 8.2**

### Property 12: HTML escaping
For generated file names, column names, and rule parameters containing `<`, `>`, `&`, `"`, and `'`, the HTML contains no unescaped copy of the value. **Validates: Req 6.7**

## Error Handling

| Code | Where | HTTP | Scope |
|---|---|---|---|
| `FILE_TOO_LARGE`, `EMPTY_DATASET`, `INVALID_FORMAT`, `INVALID_HEADER`, `ROW_LENGTH_MISMATCH` | Upload_Handler | 200 (per-file `error`) | one file |
| `INVALID_RULES` | Rule_Set parser | 422 | whole request |
| `NO_FILES`, `TOO_MANY_FILES`, `INVALID_FORMAT_PARAM` | API | 422 | whole request |
| `REQUEST_TOO_LARGE` | API | 413 | whole request |
| `INTERNAL_ERROR` | API | 500 | whole request, generic message |

## Testing Strategy

- Property tests: Properties 1–12, one `@given` each, `max_examples >= 100`, tagged `# Feature: dataset-profiling, Property N: <name>`.
- Unit tests: every error code, every rule with PASS/FAIL/SKIPPED, the suggested-rule matrix, zero-row and all-null datasets, percentage rounding (for example 2/3 → 66.7, 1/8 → 12.5 half-even to 12.5, 1/16 → 6.2).
- Integration tests: `TestClient` for each status code, multi-file with one bad file, HTML content type and escaping, and CLI naming without overwriting.
- Fixtures: small synthetic `customers.csv`, `transactions.csv`, `products.csv`, and one file per error in `tests/fixtures/`.
- Coverage of 90% or more on `core` via `pytest-cov`.
- CI runs lint, mypy, tests, and a two-process determinism check.
