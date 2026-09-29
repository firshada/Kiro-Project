# Scrubby

Scrubby is a stateless data quality service for CSV files. You upload one or more CSVs, optionally with validation rules. For each file it validates the CSV, profiles every column, checks the rules, detects duplicates, computes a deterministic quality score from 0 to 100, and returns a report as JSON or HTML. Nothing is stored.

```
CSV ─► Validation ─► Profiling ─┬─► Rules ────────┐
                                └─► Deduplication ─┴─► Quality score ─► Report (JSON | HTML)
```

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn profiler.adapters.api:app          # API on http://127.0.0.1:8000
uv run python -m profiler tests/fixtures/customers.csv --rules tests/fixtures/rules.json --format html
```

Web UI (Next.js, in `web/`), with the API running on port 8000:

```bash
cd web
npm install
npm run dev                                       # http://localhost:3000
```

The UI calls `/api/*`, which Next.js forwards to the API. Set `SCRUBBY_API_URL` to point it elsewhere.

The CLI writes `reports/quality-report-YYYY-MM-DD.html` and never overwrites an existing report. Add `--stdout` to print the report instead.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/reports?format=json\|html` | Multipart `files` (1–10 CSVs) and optional `rules` (Rule_Set JSON) |
| `GET` | `/health` | Liveness check |

Example Rule_Set:

```json
{"business_key": ["customer_id"],
 "columns": [{"column": "email", "rules": ["not_null", "valid_email"]},
             {"column": "customer_id", "rules": ["unique", {"name": "in_range", "min": 10000, "max": 19999}]}]}
```

Supported rules: `not_null`, `unique`, `valid_email`, `regex`, `in_range`, `accepted_values`, `type_is`. Without a Rule_Set, Scrubby suggests rules from the profile.

**Security:** the API has no authentication or rate limiting in v1. Don't expose it publicly without an authenticating proxy.

## Quality score

The score is the equal-weight mean (25% each) of four dimensions. It's computed with exact fractions and rounded half-even to 1 decimal, so the same input always gives the same score.

- **Completeness:** non-null cells ÷ all cells
- **Uniqueness:** unique records ÷ all records, by business key or whole row
- **Validity:** passing checks ÷ evaluated checks, over validity rules
- **Consistency:** cells matching their column's most common type ÷ non-null cells

## How Kiro is used in this project

| Kiro feature | Where |
|---|---|
| Spec (EARS requirements, design, tasks) | `.kiro/specs/dataset-profiling/` |
| Steering | `.kiro/steering/` (project overview, coding, data engineering, testing) |
| Hooks | `.kiro/hooks/` (Ruff on Python save, pytest after a spec task completes) |
| Property-based testing | 11 Hypothesis properties from the design, in `tests/property/` |
| Power | `data-engineering-power/` (`plugin.json`, 3 skills, MCP config) |
| MCP | `scrubby` server in `src/profiler/adapters/mcp_server.py` (stdio, read-only, 4 tools) |
| Custom agent | `.kiro/agents/data-quality-analyst.json` |

To register the MCP server for the workspace, create `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "scrubby": {
      "command": "uv",
      "args": ["run", "python", "-m", "profiler.adapters.mcp_server", "--root", "."],
      "env": { "PYTHONPATH": "src" },
      "autoApprove": ["validate_dataset", "profile_dataset", "check_duplicates", "quality_report"]
    }
  }
}
```

## Development

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict src
uv run pytest                 # unit, property, and integration tests; ≥ 90% coverage on core
```

## Layout

- `src/profiler/domain/`: immutable types and error codes
- `src/profiler/core/`: pure logic (validation, profiling, rules, dedup, scoring, rendering), no I/O
- `src/profiler/adapters/`: FastAPI app, CLI, MCP server
- `tests/`: unit, property, and integration tests, plus fixtures
