---
name: data-profiling
description: Profile a CSV dataset. Analyze its schema, count nulls and duplicates, score its quality, and generate a report. Use when the user asks to profile, inspect, or summarize a dataset.
---

# Data Profiling

All numbers come from the `scrubby` MCP tools. Paths are relative to the workspace root.

## Step 1: Validate the input

- Confirm the file path with the user if it's ambiguous.
- Call `validate_dataset(path)`. If `valid` is false, report `error.code` and whichever of `line`, `positions`, or `row_number` is set, then stop.

## Step 2: Analyze schema

Call `profile_dataset(path)`. Each column has `inferred_type`, `null_count`, `null_pct`, `unique_count`, `unique_pct`, `invalid_count`, and `min`/`max` for numeric columns.

List each column's position, name, and type. Flag these header problems:
- names with leading or trailing spaces
- names that differ only in letter case
- names that aren't `snake_case`

## Step 3: Detect nulls

- A cell is null when it's empty or whitespace only. `NA`, `null`, and `None` count as values, not nulls.
- Report `null_pct` for each column. Flag 20% or more as a warning, and 100% as a candidate for dropping.

## Step 4: Detect duplicates

- Ask whether there's a business key (e.g. `customer_id`). Call `check_duplicates(path, business_key)`, or omit the key for whole-row comparison.
- Report `total_records`, `unique_records`, `duplicate_records`, and the first `duplicate_rows`. If `key_status` is `MISSING_COLUMNS`, say which columns are missing.
- Columns with `unique_pct == 100` and `null_count == 0` are candidate keys.

## Step 5: Score and suggest rules

- Call `quality_report(path)` for the score with suggested rules, or pass `rules` (Rule_Set JSON from the `data-quality` skill) to score against the user's rules.
- Report `score`, the four `dimensions`, `issues`, and every `FAIL` rule with `failed_count` and `failed_rows`.

## Step 6: Generate report

Fill in `references/report-template.md` with exact numbers from the tools, keeping columns in file order. Save it as `<dataset-name>.profile.md` next to the input only if the user agrees. Otherwise, show it in chat.

For an HTML report, tell the user to run `python -m profiler <file> --format html`, which writes `reports/quality-report-<date>.html`.
