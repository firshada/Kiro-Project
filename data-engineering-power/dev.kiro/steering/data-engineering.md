---
inclusion: always
---

# Data Engineering Power

Workflows for inspecting tabular data and SQL. Each workflow is a skill in `skills/`.

## When to use which skill

| User asks for | Skill |
|---|---|
| "Profile this dataset", "what's in this CSV", schema, nulls, duplicates | `data-profiling` |
| "Suggest quality rules", "validate this data", "write checks" | `data-quality` |
| "Review this SQL", "is this query safe/fast" | `sql-review` |

## Default pipeline: "Profile this dataset"

1. Analyze schema: `data-profiling`, Step 2
2. Detect nulls: `data-profiling`, Step 3
3. Detect duplicates: `data-profiling`, Step 4
4. Suggest quality rules: hand the profile to `data-quality`
5. Generate report: `data-profiling`, Step 6, using the report template

Run the steps in this order. Only skip a step if the user asks you to.

## Ground rules for every skill

- Get numbers from the `scrubby` MCP tools (`validate_dataset`, `profile_dataset`, `check_duplicates`, `quality_report`). Don't estimate them by reading the file.
- Treat every cell as a raw string. Don't coerce `NA`, `null`, `0`, or leading zeros.
- The tools never return cell values. If you show examples, show at most 5 per column and mask emails, phone numbers, IDs, and secrets.
- Keep the data read-only. Never modify, move, or delete the input file.
- If the file is too large or malformed, stop and report the error code with its line number.
