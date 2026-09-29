# Profile: {dataset_name}

## Summary

| Metric | Value |
|---|---|
| Rows | {row_count} |
| Columns | {column_count} |
| Duplicate rows | {duplicate_count} ({duplicate_pct}%) |

## Schema

| # | Column | Type | Nulls | Null % | Unique | Candidate key |
|---|---|---|---|---|---|---|
| {position} | {name} | {inferred_type} | {null_count} | {null_pct} | {unique_count} | {yes/no} |

## Findings

- {one line per warning: high nulls, all-null columns, duplicates, header issues, null-like strings}

## Suggested quality rules

| Rule name | Column(s) | Validation logic | Failure condition | Severity |
|---|---|---|---|---|
| {rule_name} | {columns} | {logic} | {failure} | {error/warn} |
