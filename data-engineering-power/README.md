# Data Engineering Power

A Kiro Power for profiling CSV datasets, suggesting data quality rules, and reviewing SQL.

## Skills

| Skill | Purpose |
|---|---|
| `data-profiling` | Analyzes the schema, detects nulls and duplicates, infers types, and generates a report |
| `data-quality` | Turns a profile into fully defined quality rules |
| `sql-review` | Reviews SQL for security, correctness, and performance |

When you say "Profile this dataset", the power runs: analyze schema → detect nulls → detect duplicates → suggest quality rules → generate report.

## Install (local)

1. In Kiro, open the Powers panel and choose Add Custom Power → Import power from a folder.
2. Select this `data-engineering-power/` folder, then choose Install.
3. Test it in chat: "Profile tests/fixtures/customers.csv".

## Requirements

The power uses the `scrubby` MCP server from this repo (`src/profiler/adapters/mcp_server.py`). It runs over stdio, is read-only, and stores nothing.

- Install [uv](https://docs.astral.sh/uv/) and make sure `uv` is on your PATH.
- Open the Scrubby repo as your workspace. `mcp.json` runs the server from the workspace root with `--root .`, so paths are relative to it.

## Layout

- `plugin.json`: the manifest (Agent Plugins format).
- `mcp.json`: the `scrubby` MCP server.
- `skills/`: the three skills.
- `dev.kiro/steering/data-engineering.md`: routing and ground rules.

## Share

Push this repo to a public GitHub repository. Others install the power with Add Custom Power → Import power from GitHub, pointing at the `data-engineering-power/` folder. The MCP server runs from the Scrubby repo, so they need the repo open as their workspace, with `uv` on their PATH.

Run the server by hand:

```bash
uv run python -m profiler.adapters.mcp_server --root .
```

## Tools

| Tool | Returns |
|---|---|
| `validate_dataset` | `{valid, row_count, column_count}` or `{valid: false, error: {code, message, line, positions, row_number}}` |
| `profile_dataset` | `{dataset, summary, columns}` with per-column type, null %, unique %, min/max, invalid count |
| `check_duplicates` | Duplicates by optional `business_key`: `{key, key_status, total_records, unique_records, duplicate_records, duplicate_rows}` |
| `quality_report` | The full Scrubby report (score, dimensions, rules, duplicates); optional `rules` Rule_Set JSON |

## Metric definitions

- Null: the cell is empty or whitespace only. `NA` and `null` are regular strings.
- Duplicate record: an exact, case-sensitive match of all raw cells, or of the trimmed business key columns when a key is given. The first occurrence doesn't count.
- Score: the equal-weight mean of completeness, uniqueness, validity, and consistency, from 0 to 100.
- Unique count: distinct trimmed non-null values.
- Type: the first match in the order boolean → integer → float → datetime → string, over non-null values.

These match the `dataset-profiling` spec in this repo.
